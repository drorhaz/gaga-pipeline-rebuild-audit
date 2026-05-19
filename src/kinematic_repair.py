"""
Surgical repair for step 06 kinematics: root-cause repair when Critical thresholds are exceeded.

- Angular (ω, α, or rotation magnitude Critical): SLERP on raw-relative quaternions at
  critical frames, then re-derive ω and α (and zeroed quat/ω/α).
- Linear (v or a Critical): PCHIP on root-relative positions at critical frames, then
  re-derive v and a.

Repairs only the joint/segment that failed. Used when config step_06.enforce_cleaning is True.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
from scipy.signal import savgol_filter
from scipy.stats import pearsonr
from scipy.interpolate import PchipInterpolator
from typing import Dict, List, Set, Tuple, Any

# Optional: avoid hard dependency on angular_velocity at import time
try:
    from .angular_velocity import quaternion_log_angular_velocity
except ImportError:
    from angular_velocity import quaternion_log_angular_velocity


def _unroll_quat(q: np.ndarray) -> np.ndarray:
    """Ensure temporal continuity (shortest path); q shape (T, 4)."""
    q = np.asarray(q, dtype=float)
    if q.ndim == 1:
        q = q.reshape(1, -1)
    out = q.copy()
    for i in range(1, len(out)):
        if np.dot(out[i], out[i - 1]) < 0:
            out[i] *= -1
    return out


def _renormalize_quat(q: np.ndarray) -> np.ndarray:
    """Unit norm per row; q shape (T, 4)."""
    n = np.linalg.norm(q, axis=1, keepdims=True)
    n = np.where(n < 1e-12, 1.0, n)
    return q / n


def identify_critical_units(
    df_rot: Any,
    df_omega: Any,
    df_alpha: Any,
    df_linvel: Any,
    df_linacc: Any,
) -> Tuple[Set[str], Set[str]]:
    """
    Identify joints with any CRITICAL angular outlier and segments with any CRITICAL linear outlier.

    Expects DataFrames with 'joint' or 'segment' column and 'n_frames_CRITICAL' column.

    Returns:
        (angular_critical_joints, linear_critical_segments)
    """
    angular_critical_joints: Set[str] = set()
    for df, name_col in [(df_rot, "joint"), (df_omega, "joint"), (df_alpha, "joint")]:
        for _, row in df.iterrows():
            if row.get("n_frames_CRITICAL", 0) > 0:
                angular_critical_joints.add(row[name_col])

    linear_critical_segments: Set[str] = set()
    for df in [df_linvel, df_linacc]:
        for _, row in df.iterrows():
            if row.get("n_frames_CRITICAL", 0) > 0:
                linear_critical_segments.add(row["segment"])

    return angular_critical_joints, linear_critical_segments


def apply_surgical_repair(
    result: Dict[str, np.ndarray],
    pos_rel: Dict[str, np.ndarray],
    validation_rows: List[Dict[str, Any]],
    lin_audit: List[Dict[str, Any]],
    angular_critical_joints: Set[str],
    linear_critical_segments: Set[str],
    rot_mag_per_joint: Dict[str, np.ndarray],
    omega_mag_per_joint: Dict[str, np.ndarray],
    alpha_mag_per_joint: Dict[str, np.ndarray],
    lin_vel_mag: Dict[str, np.ndarray],
    lin_acc_mag: Dict[str, np.ndarray],
    thresh: Dict[str, Dict[str, float]],
    kinematics_map: Dict[str, Any],
    ref_pose: Dict[str, float],
    fs: float,
    w_len: int,
    sg_polyorder: int,
    dt: float,
    omega_thresh: float,
    lin_acc_thresh: float,
    w_len_map: Dict[str, int] | None = None,
) -> None:
    """
    Apply surgical repair in-place: modify result, pos_rel, validation_rows, lin_audit.

    - Angular: for each joint in angular_critical_joints, SLERP-repair raw_rel quat at
      critical frames, re-derive ω/α and zeroed quat/ω/α, update validation_rows.
    - Linear: for each segment in linear_critical_segments, PCHIP-repair root-relative
      position at critical frames, re-derive v/a, update lin_audit.

    When *w_len_map* is provided, the per-joint adaptive window is used for
    re-derivation.  Falls back to *w_len* for joints/segments not in the map.
    """
    if w_len_map is None:
        w_len_map = {}
    T = len(result.get("time_s", []))
    if T == 0:
        return

    # --- Angular: SLERP on raw_rel quat at critical frames, re-derive ω/α and zeroed ---
    for joint_name in angular_critical_joints:
        _jw = w_len_map.get(joint_name, w_len)
        qc = [
            f"{joint_name}__raw_rel_qx",
            f"{joint_name}__raw_rel_qy",
            f"{joint_name}__raw_rel_qz",
            f"{joint_name}__raw_rel_qw",
        ]
        if not all(c in result for c in qc):
            continue
        rot_crit = (
            rot_mag_per_joint.get(joint_name) or np.zeros(T)
        ) > thresh["rotation_mag_deg"]["CRITICAL"]
        om_crit = (
            omega_mag_per_joint.get(joint_name) or np.zeros(T)
        ) > thresh["angular_velocity_deg_s"]["CRITICAL"]
        al_crit = (
            alpha_mag_per_joint.get(joint_name) or np.zeros(T)
        ) > thresh["angular_acceleration_deg_s2"]["CRITICAL"]
        critical_idx = np.where(rot_crit | om_crit | al_crit)[0]
        if len(critical_idx) == 0:
            continue

        q = np.column_stack([np.asarray(result[c], dtype=float) for c in qc])
        q = _unroll_quat(q)
        for i in critical_idx:
            if i <= 0:
                q[i] = q[1] if T > 1 else q[0]
            elif i >= T - 1:
                q[i] = q[T - 2]
            else:
                r_ends = R.from_quat(np.stack([q[i - 1], q[i + 1]]))
                slerp = Slerp([0, 1], r_ends)
                q[i] = slerp(0.5).as_quat()
        q = _renormalize_quat(q)
        for ax, c in enumerate(qc):
            result[c] = q[:, ax]

        omega_raw_rad = quaternion_log_angular_velocity(q, fs, frame="local")
        omega_raw_deg = np.degrees(omega_raw_rad)
        for ax, letter in enumerate(["x", "y", "z"]):
            result[f"{joint_name}__raw_rel_omega_{letter}"] = omega_raw_deg[:, ax]
        alpha_raw = np.column_stack(
            [
                savgol_filter(
                    omega_raw_deg[:, j], _jw, sg_polyorder, deriv=1, delta=dt, mode="interp"
                )
                for j in range(3)
            ]
        )
        for ax, letter in enumerate(["x", "y", "z"]):
            result[f"{joint_name}__raw_rel_alpha_{letter}"] = alpha_raw[:, ax]

        parent_name = kinematics_map.get(joint_name, {}).get("parent")
        q_ref_c = np.array(
            [
                ref_pose[f"{joint_name}__qx"],
                ref_pose[f"{joint_name}__qy"],
                ref_pose[f"{joint_name}__qz"],
                ref_pose[f"{joint_name}__qw"],
            ]
        )
        if parent_name:
            q_ref_p = np.array(
                [
                    ref_pose[f"{parent_name}__qx"],
                    ref_pose[f"{parent_name}__qy"],
                    ref_pose[f"{parent_name}__qz"],
                    ref_pose[f"{parent_name}__qw"],
                ]
            )
            q_rel_ref = (R.from_quat(q_ref_p).inv() * R.from_quat(q_ref_c)).as_quat()
        else:
            q_rel_ref = q_ref_c
        q_zeroed = (R.from_quat(q_rel_ref).inv() * R.from_quat(q)).as_quat()
        q_zeroed = _renormalize_quat(q_zeroed)
        for ax, letter in enumerate(["x", "y", "z", "w"]):
            result[f"{joint_name}__zeroed_rel_q{letter}"] = q_zeroed[:, ax]
        omega_zeroed_rad = quaternion_log_angular_velocity(q_zeroed, fs, frame="local")
        omega_zeroed_deg = np.degrees(omega_zeroed_rad)
        for ax, letter in enumerate(["x", "y", "z"]):
            result[f"{joint_name}__zeroed_rel_omega_{letter}"] = omega_zeroed_deg[:, ax]
        alpha_zeroed = np.column_stack(
            [
                savgol_filter(
                    omega_zeroed_deg[:, j],
                    _jw,
                    sg_polyorder,
                    deriv=1,
                    delta=dt,
                    mode="interp",
                )
                for j in range(3)
            ]
        )
        for ax, letter in enumerate(["x", "y", "z"]):
            result[f"{joint_name}__zeroed_rel_alpha_{letter}"] = alpha_zeroed[:, ax]

        mag_omega_raw = np.linalg.norm(omega_raw_deg, axis=1)
        mag_omega_zeroed = np.linalg.norm(omega_zeroed_deg, axis=1)
        geodesic_deg = np.degrees(
            2 * np.arccos(np.clip(np.abs((q * q_zeroed).sum(axis=1)), 0, 1))
        )
        vel_align = (
            100.0 * pearsonr(mag_omega_raw, mag_omega_zeroed)[0]
            if np.std(mag_omega_raw) > 1e-10
            else 100.0
        )
        for vr in validation_rows:
            if vr["joint"] == joint_name:
                vr.update(
                    geodesic_offset_std=round(float(np.std(geodesic_deg)), 6),
                    velocity_alignment_pct=round(vel_align, 2),
                    max_omega_deg_s=round(float(np.max(mag_omega_raw)), 2),
                    mean_omega_deg_s=round(float(np.mean(mag_omega_raw)), 2),
                    median_omega_deg_s=round(float(np.median(mag_omega_raw)), 2),
                    exceeded_omega_threshold=bool(np.max(mag_omega_raw) > omega_thresh),
                )
                break

    # --- Linear: PCHIP on root-relative position at critical frames, re-derive v, a ---
    for seg in linear_critical_segments:
        _sw = w_len_map.get(seg, w_len)
        lv = lin_vel_mag.get(seg)
        la = lin_acc_mag.get(seg)
        if lv is None and la is None:
            continue
        crit = np.zeros(T, dtype=bool)
        if lv is not None:
            crit |= lv > thresh["linear_velocity_mm_s"]["CRITICAL"]
        if la is not None:
            crit |= la > thresh["linear_acceleration_mm_s2"]["CRITICAL"]
        critical_idx = np.where(crit)[0]
        if len(critical_idx) == 0:
            continue
        good_idx = np.where(~crit)[0]
        if len(good_idx) < 2:
            continue
        for _axis, suffix in [("x", "__px"), ("y", "__py"), ("z", "__pz")]:
            col = f"{seg}{suffix}"
            if col not in pos_rel:
                continue
            arr = np.asarray(pos_rel[col], dtype=float).copy()
            interp = PchipInterpolator(good_idx, arr[good_idx])
            arr[critical_idx] = interp(critical_idx)
            pos_rel[col] = arr

        vel_x = savgol_filter(
            pos_rel[f"{seg}__px"], _sw, sg_polyorder, deriv=1, delta=dt, mode="interp"
        )
        vel_y = savgol_filter(
            pos_rel[f"{seg}__py"], _sw, sg_polyorder, deriv=1, delta=dt, mode="interp"
        )
        vel_z = savgol_filter(
            pos_rel[f"{seg}__pz"], _sw, sg_polyorder, deriv=1, delta=dt, mode="interp"
        )
        acc_x = savgol_filter(
            pos_rel[f"{seg}__px"], _sw, sg_polyorder, deriv=2, delta=dt, mode="interp"
        )
        acc_y = savgol_filter(
            pos_rel[f"{seg}__py"], _sw, sg_polyorder, deriv=2, delta=dt, mode="interp"
        )
        acc_z = savgol_filter(
            pos_rel[f"{seg}__pz"], _sw, sg_polyorder, deriv=2, delta=dt, mode="interp"
        )
        for ax, letter in enumerate(["x", "y", "z"]):
            result[f"{seg}__lin_vel_rel_{letter}"] = [vel_x, vel_y, vel_z][ax]
            result[f"{seg}__lin_acc_rel_{letter}"] = [acc_x, acc_y, acc_z][ax]
        mag_acc = np.linalg.norm(np.column_stack([acc_x, acc_y, acc_z]), axis=1)
        for a in lin_audit:
            if a["segment"] == seg:
                a["max_lin_acc_mm_s2"] = round(float(np.max(mag_acc)), 2)
                a["exceeded_lin_acc_threshold"] = bool(np.max(mag_acc) > lin_acc_thresh)
                break
