import numpy as np
from scipy.spatial.transform import Rotation as R
import logging

from .quaternion_ops import (
    quat_normalize,
    quat_shortest,
    quat_enforce_continuity,
    quat_mul,
    quat_inv,
)

logger = logging.getLogger(__name__)

# Import reference validation (optional - only if module exists)
try:
    from .reference_validation import (
        validate_reference_window,
        validate_reference_stability,
        compute_motion_profile
    )
    REF_VALIDATION_AVAILABLE = True
except ImportError:
    REF_VALIDATION_AVAILABLE = False
    logger.warning("Reference validation module not available - validation metrics will be skipped")

def markley_mean_quat(Q):
    A = np.zeros((4, 4))
    for q in Q:
        A += np.outer(q, q)
    vals, vecs = np.linalg.eigh(A)
    q_mean = vecs[:, np.argmax(vals)]
    if q_mean[3] < 0:
        q_mean *= -1.0
    return quat_shortest(quat_normalize(q_mean))

_GRAVITY_AXIS_MAP = {"x": 0, "y": 1, "z": 2}


def detect_static_reference(time_s, q_local, joints_viz_idx, cfg,
                            pos_m=None, schema=None):
    """Detect the most-static upright window in the first REF_SEARCH_SEC seconds.

    When *pos_m* and *schema* are supplied the Gravity Guard is activated:
    a candidate window must have Head above Pelvis by at least
    MIN_HEAD_PELVIS_VERTICAL_M on the configured gravity axis.

    Args:
        time_s:  1-D array of timestamps (seconds).
        q_local: (T, J, 4) local quaternions (xyzw).
        joints_viz_idx: joint indices used for motion scoring.
        cfg:     pipeline config dict (uppercase keys).
        pos_m:   (T, J, 3) positional data **in metres** (not mm).
                 Required for the Gravity Guard; if None the guard is skipped.
        schema:  skeleton schema dict with ``joint_names`` and ``root_joint``.

    Returns:
        dict with keys: ref_start, ref_end, ref_is_fallback, method,
        t_pose_failed, gravity_guard_passed, metrics.
    """
    fs = cfg["FS_TARGET"]
    dt = 1.0 / fs
    search_sec = cfg["REF_SEARCH_SEC"]
    win_sec = cfg["REF_WINDOW_SEC"]
    step_sec = cfg["STATIC_SEARCH_STEP_SEC"]

    thr_low = cfg["MOTION_THR_LOW"]
    thr_std = cfg["MOTION_THR_STD"]

    # --- Gravity Guard setup ---
    gravity_guard_enabled = False
    head_idx = pelvis_idx = gravity_axis_idx = None
    min_vertical = cfg.get("MIN_HEAD_PELVIS_VERTICAL_M", 0.5)

    if pos_m is not None and schema is not None:
        gravity_axis_idx = _GRAVITY_AXIS_MAP.get(
            str(cfg.get("GRAVITY_AXIS", "y")).lower(), 1
        )
        joint_names = list(schema["joint_names"])
        _j2i = {j: i for i, j in enumerate(joint_names)}
        head_idx = _j2i.get("Head")
        pelvis_idx = _j2i.get(schema.get("root_joint", "Hips"))

        if head_idx is not None and pelvis_idx is not None:
            gravity_guard_enabled = True

            # Unit-scale sanity check (>50 m suggests mm, not m)
            median_pelvis = np.nanmedian(
                pos_m[:, pelvis_idx, gravity_axis_idx]
            )
            if median_pelvis > 50.0:
                logger.warning(
                    "Gravity Guard: median pelvis position on gravity axis "
                    "= %.1f.  This suggests positions may be in millimetres, "
                    "not metres.  The min_head_pelvis_vertical_m threshold "
                    "(%.3f) assumes metres.",
                    median_pelvis, min_vertical,
                )
        else:
            logger.warning(
                "Gravity Guard disabled: 'Head' or root joint not found in "
                "schema joint_names. Falling back to stillness-only detection."
            )

    # --- Insufficient search window ---
    mask_search = time_s <= (time_s[0] + search_sec)
    idxs = np.where(mask_search)[0]
    if len(idxs) < 3:
        return {
            "ref_start": float(time_s[0]),
            "ref_end": float(time_s[min(len(time_s) - 1,
                                         int(round(win_sec * fs)))]),
            "ref_is_fallback": True,
            "t_pose_failed": False,
            "gravity_guard_passed": not gravity_guard_enabled,
            "method": "fallback_insufficient_search",
            "metrics": {"mean_motion": np.nan, "std_motion": np.nan},
        }

    # --- Compute per-frame motion (angular velocity) ---
    T = len(time_s)
    motion = np.full(T - 1, np.nan)

    for t in range(T - 1):
        if not (mask_search[t] and mask_search[t + 1]):
            continue
        mags = []
        for j in joints_viz_idx:
            q0 = q_local[t, j]
            q1 = q_local[t + 1, j]
            if np.isfinite(q0).all() and np.isfinite(q1).all():
                dq = quat_mul(quat_inv(q0), q1)
                dq = quat_shortest(quat_normalize(dq))
                rv = R.from_quat(dq).as_rotvec()
                mags.append(float(np.linalg.norm(rv) / dt))
        if mags:
            motion[t] = np.median(mags)

    win_n = int(round(win_sec * fs))
    step_n = max(1, int(round(step_sec * fs)))

    best = None
    best_mean = float("inf")
    start_min = idxs[0]
    start_max = idxs[-1] - win_n
    if start_max <= start_min:
        start_max = start_min

    # --- Sliding window search ---
    for start in range(start_min, start_max + 1, step_n):
        end = start + win_n
        mwin = motion[start:end]
        mwin = mwin[np.isfinite(mwin)]
        if len(mwin) < max(3, win_n // 3):
            continue
        mean_m = float(np.mean(mwin))
        std_m = float(np.std(mwin))

        # --- Gravity Guard rejection ---
        if gravity_guard_enabled:
            head_y = pos_m[start:end, head_idx, gravity_axis_idx]
            pelvis_y = pos_m[start:end, pelvis_idx, gravity_axis_idx]
            if np.all(np.isnan(head_y)) or np.all(np.isnan(pelvis_y)):
                continue
            vertical = float(np.nanmean(head_y) - np.nanmean(pelvis_y))
            if vertical < min_vertical:
                continue

        if mean_m < thr_low and std_m < thr_std:
            best = (start, end, mean_m, std_m, False,
                    "strict_motion_and_gravity" if gravity_guard_enabled
                    else "criteria")
            break

        if mean_m < best_mean:
            best_mean = mean_m
            best = (start, end, mean_m, std_m, True, "fallback_min_motion")

    # --- No valid window found ---
    if best is None:
        if gravity_guard_enabled:
            logger.warning(
                "Gravity Guard: no upright static window found in the first "
                "%.1f s. Flagging t_pose_failed=True for identity fallback.",
                search_sec,
            )
            return {
                "ref_start": float(time_s[start_min]),
                "ref_end": float(
                    time_s[min(start_min + win_n, len(time_s) - 1)]
                ),
                "ref_is_fallback": True,
                "t_pose_failed": True,
                "gravity_guard_passed": False,
                "method": "fallback_identity_gravity_guard_failed",
                "metrics": {"mean_motion": np.nan, "std_motion": np.nan},
            }
        return {
            "ref_start": float(time_s[start_min]),
            "ref_end": float(
                time_s[min(start_min + win_n, len(time_s) - 1)]
            ),
            "ref_is_fallback": True,
            "t_pose_failed": False,
            "gravity_guard_passed": False,
            "method": "fallback_first_window",
            "metrics": {"mean_motion": np.nan, "std_motion": np.nan},
        }

    start, end, mean_m, std_m, is_fb, method = best

    return {
        "ref_start": float(time_s[start]),
        "ref_end": float(time_s[min(end, len(time_s) - 1)]),
        "ref_is_fallback": bool(is_fb),
        "t_pose_failed": False,
        "gravity_guard_passed": gravity_guard_enabled,
        "method": method,
        "metrics": {"mean_motion": mean_m, "std_motion": std_m},
    }


def compute_q_ref_and_ref_qc(time_s, q_local, ref_info, joints_export_idx, joints_viz_idx, cfg):
    # --- Identity fallback when Gravity Guard flagged t_pose_failed ---
    if ref_info.get("t_pose_failed", False):
        J = q_local.shape[1]
        q_ref = np.tile(np.array([0.0, 0.0, 0.0, 1.0]), (J, 1))
        qc = {
            "identity_error_ref_med": float("nan"),
            "ref_quality_score": float("nan"),
            "identity_errors_by_joint_idx": {},
            "ref_std_by_joint_idx": {},
            "t_pose_failed": True,
            "gravity_guard_passed": False,
            "method": ref_info.get("method", "fallback_identity"),
        }
        logger.warning(
            "Gravity Guard: t_pose_failed=True — using identity quaternion "
            "[0,0,0,1] for ALL %d joints. Downstream kinematics are offset "
            "from true neutral.",
            J,
        )
        return q_ref, qc

    t0, t1 = ref_info["ref_start"], ref_info["ref_end"]
    mask = (time_s >= t0) & (time_s <= t1)
    idxs = np.where(mask)[0]

    if len(idxs) < 3:
        idxs = np.arange(min(len(time_s), int(round(cfg["REF_WINDOW_SEC"] * cfg["FS_TARGET"]))))

    J = q_local.shape[1]
    q_ref = np.full((J, 4), np.nan)

    for j in joints_export_idx:
        Q = q_local[idxs, j, :]
        Q = Q[np.isfinite(Q).all(axis=1)]
        if len(Q) < 3:
            continue
        Q = quat_shortest(quat_normalize(Q))
        Q = quat_enforce_continuity(Q)
        q_ref[j] = markley_mean_quat(Q)

    identity_errors = {}
    ref_stds = {}

    for j in joints_viz_idx:
        if not np.isfinite(q_ref[j]).all():
            continue
        qd = quat_mul(quat_inv(q_ref[j]), q_local[idxs, j])
        qd = quat_shortest(quat_normalize(qd))
        rv = R.from_quat(qd).as_rotvec()
        mag = np.linalg.norm(rv, axis=1)
        identity_errors[j] = float(np.mean(mag))
        ref_stds[j] = float(np.std(mag))

    identity_med = np.median(list(identity_errors.values())) if identity_errors else float("nan")
    ref_quality_score = np.median(list(ref_stds.values())) if ref_stds else float("nan")

    qc = {
        "identity_error_ref_med": float(identity_med),
        "ref_quality_score": float(ref_quality_score),
        "identity_errors_by_joint_idx": identity_errors,
        "ref_std_by_joint_idx": ref_stds,
    }
    
    # Reference Validation (Research Validation Phase 1 - Item 2)
    if REF_VALIDATION_AVAILABLE:
        try:
            logger.info("Running reference validation to verify reference quality...")
            
            # Validate reference window quality
            window_validation = validate_reference_window(
                time_s, q_local, ref_info["ref_start"], ref_info["ref_end"],
                joints_viz_idx, cfg["FS_TARGET"], strict_thresholds=True
            )
            qc['reference_window_validation'] = window_validation
            
            # Validate reference stability
            stability_validation = validate_reference_stability(
                q_ref, q_local, ref_info["ref_start"], ref_info["ref_end"],
                time_s, joints_viz_idx
            )
            qc['reference_stability_validation'] = stability_validation
            
            logger.info(f"Reference Validation: Window status={window_validation.get('status', 'UNKNOWN')}, "
                       f"Mean motion={window_validation.get('mean_motion_rad_s', 0):.3f} rad/s")
            
        except Exception as e:
            logger.warning(f"Reference validation failed: {e}")
            qc['reference_validation'] = {'status': 'ERROR', 'error': str(e)}
    else:
        logger.info("Reference validation skipped (module not available)")

    return q_ref, qc