"""
Resampling Module with Temporal Quality Assessment
===================================================
Provides resampling functions and Gate 2 temporal quality metrics.

Gate 2: Signal Integrity & Temporal Quality
- compute_sample_jitter(): Detect clock instability
- Thresholds: jitter > 2ms = REVIEW

Author: Gaga Motion Analysis Pipeline
"""

import numpy as np
from scipy.interpolate import CubicSpline, interp1d, PchipInterpolator
from scipy.spatial.transform import Rotation as R, Slerp
from typing import Dict, Optional

from .quaternion_ops import (
    quat_normalize,
    quat_shortest,
    quat_enforce_continuity
)


def estimate_fs(time_s):
    """Estimate sampling frequency from timestamps."""
    dt = np.diff(time_s)
    dt = dt[np.isfinite(dt)]
    if len(dt) == 0:
        return float("nan")
    return float(1.0 / np.median(dt))


# =============================================================================
# GATE 2: TEMPORAL QUALITY ASSESSMENT
# =============================================================================

def compute_sample_jitter(time_s: np.ndarray) -> Dict:
    """
    Compute timing jitter statistics from raw timestamps.
    
    Gate 2 Implementation: Detect "hallucinated" velocities caused by 
    sampling clock instability.
    
    Parameters
    ----------
    time_s : np.ndarray
        Raw timestamps in seconds
        
    Returns
    -------
    dict with:
        - step_02_sample_time_jitter_ms: StdDev of Δt (milliseconds)
        - step_02_dt_mean_ms: Mean frame duration
        - step_02_dt_max_ms: Maximum frame duration
        - step_02_dt_min_ms: Minimum frame duration
        - step_02_jitter_status: PASS/REVIEW based on 2ms threshold
        - step_02_jitter_decision_reason: Explanation string
        
    Thresholds
    ----------
    - jitter_ms <= 2.0: PASS (clock stability acceptable)
    - jitter_ms > 2.0: REVIEW (check PC performance during capture)
    """
    dt = np.diff(time_s)
    dt = dt[np.isfinite(dt)]
    
    if len(dt) == 0:
        return {
            "step_02_sample_time_jitter_ms": float("nan"),
            "step_02_dt_mean_ms": float("nan"),
            "step_02_dt_max_ms": float("nan"),
            "step_02_dt_min_ms": float("nan"),
            "step_02_jitter_status": "UNKNOWN",
            "step_02_jitter_decision_reason": "No valid timestamps"
        }
    
    dt_ms = dt * 1000  # Convert to milliseconds
    jitter_ms = float(np.std(dt_ms))
    dt_mean_ms = float(np.mean(dt_ms))
    dt_max_ms = float(np.max(dt_ms))
    dt_min_ms = float(np.min(dt_ms))
    
    # Gate 2 threshold: 2ms jitter
    JITTER_THRESHOLD_MS = 2.0
    
    if jitter_ms > JITTER_THRESHOLD_MS:
        status = "REVIEW"
        reason = f"REVIEW: Temporal Jitter — StdDev(Δt) = {jitter_ms:.2f} ms > {JITTER_THRESHOLD_MS} ms threshold. Check PC performance during capture."
    else:
        status = "PASS"
        reason = f"Clock stability acceptable: jitter = {jitter_ms:.2f} ms"
    
    return {
        "step_02_sample_time_jitter_ms": round(jitter_ms, 4),
        "step_02_dt_mean_ms": round(dt_mean_ms, 4),
        "step_02_dt_max_ms": round(dt_max_ms, 4),
        "step_02_dt_min_ms": round(dt_min_ms, 4),
        "step_02_jitter_status": status,
        "step_02_jitter_decision_reason": reason if status == "REVIEW" else None
    }


def get_interpolation_fallback_metrics(interpolation_summary: Dict, total_frames: int) -> Dict:
    """
    Extract Gate 2 interpolation fallback metrics from InterpolationLogger summary.
    
    Parameters
    ----------
    interpolation_summary : dict
        Output from InterpolationLogger.get_summary()
    total_frames : int
        Total number of frames in recording
        
    Returns
    -------
    dict with:
        - step_02_fallback_count: Total fallback events
        - step_02_fallback_rate_percent: Percentage of frames with fallback
        - step_02_max_gap_frames: Largest gap that was interpolated
        - step_02_joints_with_fallbacks: List of affected joints
        - step_02_interpolation_status: PASS/REVIEW/REJECT
        - step_02_interpolation_decision_reason: Explanation string
        
    Thresholds
    ----------
    - fallback_rate <= 5%: PASS
    - fallback_rate > 5%: REVIEW
    - fallback_rate > 15%: REJECT
    """
    total_fallbacks = interpolation_summary.get('total_fallbacks', 0)
    joints_with_fallbacks = interpolation_summary.get('joints_with_fallbacks', [])
    
    # Calculate total frames interpolated via fallback
    fallback_frames = 0
    max_gap = 0
    per_joint = interpolation_summary.get('per_joint', {})
    for joint, stats in per_joint.items():
        if stats.get('fallback_count', 0) > 0:
            fallback_frames += stats.get('total_frames_interpolated', 0)
        max_gap = max(max_gap, stats.get('max_gap_size', 0))
    
    fallback_rate = 100 * fallback_frames / total_frames if total_frames > 0 else 0
    
    # Gate 2 thresholds
    FALLBACK_WARN_THRESHOLD = 5.0
    FALLBACK_REJECT_THRESHOLD = 15.0
    
    if fallback_rate > FALLBACK_REJECT_THRESHOLD:
        status = "REJECT"
        reason = f"REJECT: Excessive Interpolation — {fallback_rate:.2f}% frames compromised by linear fallback."
    elif fallback_rate > FALLBACK_WARN_THRESHOLD:
        status = "REVIEW"
        reason = f"REVIEW: Interpolation Fallback — {fallback_rate:.2f}% frames used linear fallback instead of spline."
    else:
        status = "PASS"
        reason = None
    
    return {
        "step_02_fallback_count": total_fallbacks,
        "step_02_fallback_frames": fallback_frames,
        "step_02_fallback_rate_percent": round(fallback_rate, 4),
        "step_02_max_gap_frames": max_gap,
        "step_02_joints_with_fallbacks": joints_with_fallbacks,
        "step_02_interpolation_status": status,
        "step_02_interpolation_decision_reason": reason
    }

def resample_time_grid(time_s, fs_target):
    t0 = float(time_s[0])
    t1 = float(time_s[-1])
    n = int(round((t1 - t0) * fs_target)) + 1
    return t0 + np.arange(n) / fs_target


def _min_distance_to_valid_timestamps(t_dst: np.ndarray, tv: np.ndarray) -> np.ndarray:
    """
    Vectorized: for each t_dst[i], return min over tv of |t_dst[i] - tv[k]|.
    tv must be sorted ascending.
    """
    if len(tv) == 0:
        return np.full(len(t_dst), np.inf)
    idx = np.searchsorted(tv, t_dst, side="left")
    left_idx = np.maximum(0, idx - 1)
    right_idx = np.minimum(len(tv) - 1, idx)
    dist_left = np.abs(t_dst - tv[left_idx])
    dist_right = np.abs(t_dst - tv[right_idx])
    return np.minimum(dist_left, dist_right)


def resample_pos_pchip(
    time_s: np.ndarray,
    pos: np.ndarray,
    t_dst: Optional[np.ndarray] = None,
    max_gap_pos_sec: float = 1.0,
    fs_target: float = 120.0,
) -> np.ndarray:
    """
    Single-pass PCHIP position resampler: gap-healing and uniform resampling in one step.

    Uses only valid (t, x) per joint (all three axes must be non-NaN for a timestamp
    to count as valid). No extrapolation; grid points outside [first_valid_t, last_valid_t]
    or farther than max_gap_pos_sec/2 from any valid timestamp are set to NaN.

    Parameters
    ----------
    time_s : np.ndarray
        Raw timestamps in seconds, shape (T,).
    pos : np.ndarray
        Positions in meters, shape (T, J, 3). May contain NaNs.
    t_dst : np.ndarray, optional
        Target grid times. If None, built from time_s[0], time_s[-1] and fs_target.
    max_gap_pos_sec : float
        Maximum gap (seconds) to consider "trusted"; half-gap rule uses max_gap_pos_sec / 2.
    fs_target : float
        Used only when t_dst is None to build the uniform grid.

    Returns
    -------
    out : np.ndarray
        Shape (len(t_dst), J, 3). NaN where extrapolated or beyond half-gap.
    """
    T, J, C = pos.shape
    assert C == 3, "pos must have shape (T, J, 3)"
    if t_dst is None:
        t_dst = resample_time_grid(time_s, fs_target)
    N = len(t_dst)
    out = np.full((N, J, 3), np.nan)

    max_dist = max_gap_pos_sec / 2.0

    for j in range(J):
        valid_j = (
            np.isfinite(pos[:, j, 0])
            & np.isfinite(pos[:, j, 1])
            & np.isfinite(pos[:, j, 2])
            & np.isfinite(time_s)
        )
        tv_j = time_s[valid_j]
        xv_j = pos[valid_j, j, 0]
        yv_j = pos[valid_j, j, 1]
        zv_j = pos[valid_j, j, 2]
        n_valid = len(tv_j)

        if n_valid < 2:
            continue

        pchip_x = PchipInterpolator(tv_j, xv_j)
        pchip_y = PchipInterpolator(tv_j, yv_j)
        pchip_z = PchipInterpolator(tv_j, zv_j)
        out[:, j, 0] = pchip_x(t_dst)
        out[:, j, 1] = pchip_y(t_dst)
        out[:, j, 2] = pchip_z(t_dst)

        min_dist = _min_distance_to_valid_timestamps(t_dst, tv_j)
        mask_j = (
            (t_dst < tv_j[0])
            | (t_dst > tv_j[-1])
            | (min_dist > max_dist)
        )
        out[mask_j, j, :] = np.nan

    return out


def resample_pos(time_s, pos, t_dst, method):
    T, J, C = pos.shape
    out = np.full((len(t_dst), J, C), np.nan)
    for j in range(J):
        for c in range(C):
            x = pos[:, j, c]
            valid = np.isfinite(x) & np.isfinite(time_s)
            if valid.sum() < 4:
                if valid.sum() >= 2:
                    f = interp1d(time_s[valid], x[valid],
                                 kind="linear",
                                 bounds_error=False,
                                 fill_value=np.nan,
                                 assume_sorted=True)
                    out[:, j, c] = f(t_dst)
                continue
            tv = time_s[valid]
            xv = x[valid]
            if method == "linear":
                f = interp1d(tv, xv, kind="linear",
                             bounds_error=False,
                             fill_value=np.nan,
                             assume_sorted=True)
                out[:, j, c] = f(t_dst)
            elif method == "cubic_spline":
                cs = CubicSpline(tv, xv, extrapolate=False)
                out[:, j, c] = cs(t_dst)
            else:
                raise ValueError(f"Unknown resample method: {method}")
    return out

def resample_quat_slerp(time_s, q, t_dst):
    T, J, _ = q.shape
    out = np.full((len(t_dst), J, 4), np.nan)
    for j in range(J):
        qj = q[:, j, :]
        valid = np.isfinite(qj).all(axis=1)
        if valid.sum() < 2:
            continue
        tv = time_s[valid]
        qv = quat_enforce_continuity(quat_normalize(qj[valid]))
        rot = R.from_quat(qv)
        s = Slerp(tv, rot)
        mask = (t_dst >= tv[0]) & (t_dst <= tv[-1])
        if mask.any():
            out[mask, j, :] = s(t_dst[mask]).as_quat()
        out[:, j, :] = quat_shortest(quat_normalize(out[:, j, :]))
    return out