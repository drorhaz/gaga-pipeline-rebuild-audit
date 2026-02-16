import numpy as np
import pandas as pd
import os
import gc
import json
import logging
from scipy.spatial.transform import Rotation as R
from scipy.signal import savgol_filter

from .config import CONFIG
from .utils import ensure_dirs, fingerprint_file, write_json, log_event
from .preprocessing import parse_optitrack_csv
from .resampling import estimate_fs, resample_time_grid, resample_pos, resample_quat_slerp
from .quaternion_ops import quat_normalize, quat_shortest, quat_enforce_continuity, quat_mul, quat_inv
from .reference import detect_static_reference, compute_q_ref_and_ref_qc
from .qc import bone_length_qc
from .export_tables import build_master_tables
from .euler_isb import get_euler_sequence

logger = logging.getLogger(__name__)

class RunCtx:
    def __init__(self, run_id, out_dir):
        self.run_id = run_id
        self.out_dir = out_dir
        self.warnings = []
        self.alerts = {}
        self.stage_status = {}
        self.metrics = {}
        self.meta = {}

def compute_q_local(q_global, schema):
    joint_names = schema["joint_names"]
    parent_map = schema["parent_map"]
    depth_order = schema["depth_order"]
    idx = {j: i for i, j in enumerate(joint_names)}
    T, J, _ = q_global.shape
    q_local = np.full_like(q_global, np.nan)

    for t in range(T):
        for jname in depth_order:
            j = idx[jname]
            parent = parent_map.get(jname, None)
            if parent is None:
                q_local[t, j] = q_global[t, j]
            else:
                p = idx[parent]
                if (np.isfinite(q_global[t, p]).all() and np.isfinite(q_global[t, j]).all()):
                    q_local[t, j] = quat_mul(quat_inv(q_global[t, p]), q_global[t, j])
    
    return quat_enforce_continuity(quat_shortest(quat_normalize(q_local)))

def compute_kinematics(q_local, q_ref, fs):
    dt = 1.0 / fs
    T, J, _ = q_local.shape
    rotvec = np.full((T, J, 3), np.nan)
    rv_mag = np.full((T, J), np.nan)
    omega = np.full((T, J, 3), np.nan)
    omega_mag = np.full((T, J), np.nan)

    for j in range(J):
        if not np.isfinite(q_ref[j]).all(): continue
        
        # Rotvec
        qd = quat_mul(quat_inv(q_ref[j]), q_local[:, j])
        qd = quat_shortest(quat_normalize(qd))
        rv = R.from_quat(qd).as_rotvec()
        rotvec[:, j, :] = rv
        rv_mag[:, j] = np.linalg.norm(rv, axis=1)

        # Omega
        qj = q_local[:, j]
        for t in range(T - 1):
            q0, q1 = qj[t], qj[t+1]
            if np.isfinite(q0).all() and np.isfinite(q1).all():
                dq = quat_mul(quat_inv(q0), q1)
                dq = quat_shortest(quat_normalize(dq))
                om = R.from_quat(dq).as_rotvec() / dt
                omega[t, j] = om
                omega_mag[t, j] = np.linalg.norm(om)
    return rotvec, rv_mag, omega, omega_mag

def compute_euler_angles(q_local, q_ref, joint_names):
    """
    Compute ISB-compliant Euler angles from reference-relative quaternions.

    Uses euler_isb.get_euler_sequence() per joint to select the correct
    decomposition (e.g. YXY for shoulders, ZXY for hips/spine/limbs).

    Args:
        q_local: Local quaternions, shape (T, J, 4) in xyzw format.
        q_ref: Reference quaternions, shape (J, 4) in xyzw format.
        joint_names: List of joint name strings, length J.

    Returns:
        euler_deg: Euler angles in degrees, shape (T, J, 3).
        euler_sequences: Dict mapping joint_name -> sequence string used.
    """
    T, J, _ = q_local.shape
    euler_deg = np.full((T, J, 3), np.nan)
    euler_sequences = {}

    for j, joint_name in enumerate(joint_names):
        if not np.isfinite(q_ref[j]).all():
            continue

        # Reference-relative quaternion
        qd = quat_mul(quat_inv(q_ref[j]), q_local[:, j])
        qd = quat_shortest(quat_normalize(qd))

        # ISB-compliant sequence for this joint
        sequence = get_euler_sequence(joint_name)
        euler_sequences[joint_name] = sequence

        # Decompose using the correct sequence
        rot = R.from_quat(qd)
        euler_deg[:, j, :] = rot.as_euler(sequence, degrees=True)

    logger.info(
        "ISB Euler angles computed for %d joints. "
        "Sequences used: %s",
        len(euler_sequences),
        {s: sum(1 for v in euler_sequences.values() if v == s)
         for s in set(euler_sequences.values())}
    )

    return euler_deg, euler_sequences


def compute_derivatives(pos, fs, cfg):
    win = int(round(cfg["SG_WINDOW_SEC"] * fs))
    if win < 5: win = 5
    if win % 2 == 0: win += 1
    return savgol_filter(pos, window_length=win, polyorder=cfg["SG_POLYORDER"], deriv=1, delta=1.0/fs, axis=0, mode='interp')

def run_pipeline(csv_path, schema, seg_map, run_id="run1", cfg=CONFIG, output_root="analysis"):
    """
    Run the full MoCap processing pipeline for a single recording.

    NOTE: Pipeline operates in OptiTrack Frame (Y-Up, Z-Forward) for internal
    consistency. ISB Frame conversion is performed only during final export if
    requested. All positions are converted from mm to meters but axis ordering
    remains OptiTrack convention throughout.
    """
    out_dir = os.path.join(output_root, run_id)
    ensure_dirs(out_dir, os.path.join(out_dir, "debug"))
    ctx = RunCtx(run_id, out_dir)
    logger.info(
        "NOTE: Pipeline operates in OptiTrack Frame (Y-Up, Z-Forward) for "
        "internal consistency. ISB Frame conversion is performed only during "
        "final export if requested."
    )
    
    try:
        # 0. Anthropometric metadata integrity gate (Metadata Sentinel)
        # Detects default / missing anthropometric values that make de Leva (1996)
        # CoM calculations generic rather than subject-specific.
        _height = cfg.get("SUBJECT_HEIGHT_CM") or cfg.get("subject_height_cm")
        _mass = cfg.get("SUBJECT_MASS_KG") or cfg.get("subject_mass_kg")
        _metadata_quality = "SUBJECT_SPECIFIC"  # Assume good until proven otherwise
        
        if (_height is not None and _mass is not None
                and abs(float(_height) - 170.0) < 0.1
                and abs(float(_mass) - 70.0) < 0.1):
            _metadata_quality = "UNRELIABLE_COM_DEFAULT_ANTHRO"
            logger.critical(
                "*** METADATA SENTINEL — CRITICAL WARNING ***\n"
                "  Default anthropometric values detected (height=170.0cm, mass=70.0kg).\n"
                "  de Leva (1996) CoM calculations are GENERIC, not subject-specific.\n"
                "  All WBCoM, intensity normalization, and segment inertia values\n"
                "  should be treated as UNRELIABLE for individual-level inference.\n"
                "  ACTION: Provide measured values in data/subjects_registry.json\n"
                "  for subject '%s', run '%s'.",
                cfg.get("subject_id", "unknown"), run_id,
            )
        elif _height is None or _mass is None:
            _metadata_quality = "MISSING_ANTHRO"
            logger.critical(
                "*** METADATA SENTINEL — CRITICAL WARNING ***\n"
                "  Subject anthropometrics MISSING (height=%s, mass=%s).\n"
                "  WBCoM and intensity normalization are UNRELIABLE.\n"
                "  ACTION: Add height_cm and weight_kg to subjects_registry.json.",
                _height, _mass,
            )
        else:
            logger.info(
                "Metadata Sentinel PASS: subject-specific anthropometrics "
                "confirmed (height=%.1f cm, mass=%.1f kg).",
                float(_height), float(_mass),
            )
        
        ctx.meta["metadata_quality"] = _metadata_quality
        ctx.meta["subject_height_cm"] = float(_height) if _height is not None else None
        ctx.meta["subject_mass_kg"] = float(_mass) if _mass is not None else None

        # 1. Load
        frame_idx, time_s, pos_mm, q_global, loader_report = parse_optitrack_csv(csv_path, schema)

        # 1b. Duration gatekeeper -- reject files too short for meaningful analysis
        min_run_seconds = cfg.get("MIN_RUN_SECONDS", 5.0)
        n_frames = len(time_s)
        duration_s = time_s[-1] - time_s[0] if n_frames > 1 else 0.0
        if duration_s < min_run_seconds:
            msg = (f"File rejected: duration {duration_s:.2f}s ({n_frames} frames) "
                   f"is below minimum {min_run_seconds}s. Skipping run '{run_id}'.")
            logger.warning(msg)
            return {"status": "SKIP", "reason": msg, "duration_s": duration_s}

        pos_m = pos_mm / 1000.0
        q_global = quat_enforce_continuity(quat_shortest(quat_normalize(q_global)))
        
        # 2. Resample
        fs_target = cfg["FS_TARGET"]
        t_dst = resample_time_grid(time_s, fs_target)
        if cfg["TIME_REG_POLICY"] == "resample_to_fs_target":
            pos_m = resample_pos(time_s, pos_m, t_dst, method=cfg["POS_RESAMPLE_METHOD"])
            q_global = resample_quat_slerp(time_s, q_global, t_dst)
            frame_idx = np.arange(len(t_dst))
            time_s = t_dst

        # 3. Local & Ref
        q_local = compute_q_local(q_global, schema)
        
        joint_names = list(schema["joint_names"])
        j2i = {j: i for i, j in enumerate(joint_names)}
        viz_idx = [j2i[j] for j in cfg["JOINTS_VIZ"] if j in j2i]
        
        ref_info = detect_static_reference(time_s, q_local, viz_idx, cfg)
        export_idx = [i for i, g in enumerate(seg_map["group"]) if g not in cfg["EXCLUDE_GROUPS"]]
        q_ref, ref_qc = compute_q_ref_and_ref_qc(time_s, q_local, ref_info, export_idx, viz_idx, cfg)

        # 4. Kinematics & QC
        rotvec, rv_mag, omega, omega_mag = compute_kinematics(q_local, q_ref, fs_target)
        euler_deg, euler_sequences = compute_euler_angles(q_local, q_ref, joint_names)
        df_bones, bone_sum = bone_length_qc(pos_m, schema, np.ones(len(joint_names), dtype=bool), cfg)

        # 4b. Bone QC status -- transparent logging with Spine Whitelist awareness
        bone_n_alert = bone_sum.get("bone_n_alert", 0)
        bone_n_warn  = bone_sum.get("bone_n_warn", 0)
        worst_name   = bone_sum.get("worst_bone_name")
        worst_cv     = bone_sum.get("worst_bone_cv", 0.0)

        if bone_n_alert > 0:
            bone_qc_status = "ALERT"
            logger.warning("Bone QC ALERT: %d segments exceed alert threshold. "
                           "Worst: %s CV=%.2f%%", bone_n_alert, worst_name, worst_cv * 100)
        elif bone_n_warn > 0:
            bone_qc_status = "WARN"
            logger.warning("Bone QC WARN: %d segments exceed warn threshold. "
                           "Worst: %s CV=%.2f%%", bone_n_warn, worst_name, worst_cv * 100)
        else:
            bone_qc_status = "PASS"
            if worst_name:
                logger.info("Bone QC PASS: all segments within thresholds. "
                            "Highest CV: %s at %.2f%%", worst_name, worst_cv * 100)

        bone_sum["bone_qc_status"] = bone_qc_status

        # 5. Crop
        t0, t1 = cfg["CROP_SEC"]
        mask = (time_s >= (time_s[0] + t0)) & (time_s <= (time_s[0] + t1))
        idxs = np.where(mask)[0]
        if len(idxs) < 5: idxs = np.arange(len(time_s)) # Fallback
        
        # Helper to crop
        crop = lambda x: x[idxs] if x is not None else None
        
        # 6. Derivatives
        vpos_world = compute_derivatives(crop(pos_m), fs_target, cfg)
        root_idx = j2i.get(schema.get("root_joint", "Hips"), 0)
        pos_rootrel = crop(pos_m) - crop(pos_m)[:, root_idx:root_idx+1, :]
        vpos_rootrel = compute_derivatives(pos_rootrel, fs_target, cfg)

        # 7. Export
        qc_valid = np.ones(len(idxs), dtype=bool) # Simplified validity
        joints_export_mask = np.array([g not in cfg["EXCLUDE_GROUPS"] for g in seg_map["group"]])
        joints_viz_mask = np.array([j in cfg["JOINTS_VIZ"] for j in joint_names])

        df_full, df_viz = build_master_tables(
            run_id, crop(time_s), crop(frame_idx), joint_names,
            joints_export_mask, joints_viz_mask, qc_valid,
            crop(pos_m), pos_rootrel, crop(rotvec), crop(rv_mag),
            crop(omega), crop(omega_mag), vpos_world, vpos_rootrel
        )
        
        if cfg["WRITE_FULL_CSV"]: df_full.to_csv(os.path.join(out_dir, f"{run_id}__full.csv"), index=False)
        if cfg["WRITE_VIZ_CSV"]: df_viz.to_csv(os.path.join(out_dir, f"{run_id}__viz.csv"), index=False)
        
        ctx.metrics.update(ref_qc)
        ctx.metrics.update(bone_sum)
        ctx.metrics["euler_sequences_used"] = euler_sequences
        ctx.metrics["metadata_quality"] = _metadata_quality
        ctx.metrics["subject_height_cm"] = float(_height) if _height is not None else None
        ctx.metrics["subject_mass_kg"] = float(_mass) if _mass is not None else None
        # Write to __validation_report.json so NB08's discover_json_files
        # (which matches PARAMETER_SCHEMA file_suffix for step_06) can find it.
        write_json(os.path.join(out_dir, f"{run_id}__validation_report.json"), ctx.metrics)
        
        return {
            "status": "PASS",
            "out_dir": out_dir,
            "bone_qc_status": bone_qc_status,
            "worst_bone": worst_name,
            "worst_bone_cv": worst_cv,
            "metadata_quality": _metadata_quality,
        }

    except Exception as e:
        print(f"Pipeline failed: {e}")
        return {"status": "FAIL", "error": str(e)}
    finally:
        gc.collect()