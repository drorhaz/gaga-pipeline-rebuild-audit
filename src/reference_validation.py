"""
Reference Detection Validation Module

This module provides validation tools to verify static reference pose detection quality,
including ground-truth validation, motion profile analysis, and visual verification support.

References:
    - Kok, M. et al. (2017). Using inertial sensors for position and orientation estimation.
    - Roetenberg, D. et al. (2009). Compensation of magnetic disturbances improves IMU calibration.
    - Sabatini, A. M. (2006). Quaternion-based extended Kalman filter for determining orientation.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, Tuple, Optional, List
from scipy.spatial.transform import Rotation as R

logger = logging.getLogger(__name__)


def compute_motion_profile(time_s: np.ndarray,
                          q_local: np.ndarray,
                          joint_indices: List[int],
                          fs: float,
                          window_sec: float = 0.5) -> Dict[str, np.ndarray]:
    """
    Compute continuous motion profile from quaternions for reference validation.
    
    Args:
        time_s: Time vector in seconds
        q_local: Local quaternions (T, J, 4)
        joint_indices: Indices of joints to analyze
        fs: Sampling frequency
        window_sec: Smoothing window size in seconds
        
    Returns:
        Dictionary with motion metrics over time
        
    Reference:
        Kok et al. (2017): Motion magnitude from rotation rate
    """
    T = len(time_s)
    dt = 1.0 / fs
    
    # Compute angular velocity magnitude for each joint
    omega_mag = np.full((T-1, len(joint_indices)), np.nan)
    
    for idx, j in enumerate(joint_indices):
        for t in range(T-1):
            q0 = q_local[t, j]
            q1 = q_local[t+1, j]
            
            if np.isfinite(q0).all() and np.isfinite(q1).all():
                # Compute relative rotation
                dq = _quat_mul(_quat_inv(q0), q1)
                dq = _quat_shortest(_quat_normalize(dq))
                
                # Convert to rotation vector and compute magnitude
                rotvec = R.from_quat(dq).as_rotvec()
                omega_mag[t, idx] = np.linalg.norm(rotvec) / dt
    
    # Compute median across joints (robust to outliers)
    motion_profile = np.nanmedian(omega_mag, axis=1)
    
    # Smooth with moving average
    window_n = int(window_sec * fs)
    motion_smooth = _moving_average(motion_profile, window_n)
    
    return {
        'time': time_s[:-1],  # One less due to diff
        'motion_raw': motion_profile,
        'motion_smooth': motion_smooth,
        'omega_per_joint': omega_mag
    }


def validate_reference_window(time_s: np.ndarray,
                             q_local: np.ndarray,
                             ref_start: float,
                             ref_end: float,
                             joint_indices: List[int],
                             fs: float,
                             strict_thresholds: bool = True) -> Dict[str, any]:
    """
    Validate quality of detected reference window with research-based criteria.
    
    Quality criteria (Kok et al. 2017, Roetenberg et al. 2009):
    - Strict: Mean motion < 0.3 rad/s, STD < 0.1 rad/s
    - Relaxed: Mean motion < 0.5 rad/s, STD < 0.15 rad/s
    - Window duration: >1.0 seconds preferred
    - Temporal placement: Prefer early in recording (first 10s)
    
    Args:
        time_s: Time vector
        q_local: Local quaternions
        ref_start: Reference window start time
        ref_end: Reference window end time
        joint_indices: Joints to validate
        fs: Sampling frequency
        strict_thresholds: Use strict validation criteria
        
    Returns:
        Dictionary with validation metrics and pass/fail status
    """
    # Extract reference window
    ref_mask = (time_s >= ref_start) & (time_s <= ref_end)
    ref_indices = np.where(ref_mask)[0]
    
    if len(ref_indices) < 3:
        return {
            'status': 'FAIL',
            'reason': 'insufficient_samples',
            'n_samples': len(ref_indices),
            'duration_sec': 0.0
        }
    
    # Compute motion in reference window
    motion_profile = compute_motion_profile(
        time_s, q_local, joint_indices, fs
    )
    
    # Find corresponding motion indices (motion is one shorter than time)
    motion_ref_mask = (motion_profile['time'] >= ref_start) & (motion_profile['time'] <= ref_end)
    motion_ref = motion_profile['motion_smooth'][motion_ref_mask]
    
    if len(motion_ref) == 0:
        return {
            'status': 'FAIL',
            'reason': 'no_motion_data',
            'n_samples': 0
        }
    
    # Compute statistics
    mean_motion = float(np.nanmean(motion_ref))
    std_motion = float(np.nanstd(motion_ref))
    max_motion = float(np.nanmax(motion_ref))
    duration_sec = float(ref_end - ref_start)
    
    # Apply thresholds
    if strict_thresholds:
        mean_thresh = 0.3  # rad/s (Kok et al. 2017)
        std_thresh = 0.1   # rad/s
        dur_thresh = 1.0   # seconds
    else:
        mean_thresh = 0.5  # rad/s (relaxed)
        std_thresh = 0.15  # rad/s
        dur_thresh = 0.5   # seconds
    
    # Validate
    pass_mean = mean_motion < mean_thresh
    pass_std = std_motion < std_thresh
    pass_duration = duration_sec >= dur_thresh
    pass_early = ref_start < 10.0  # Prefer first 10 seconds
    
    # Overall status
    if pass_mean and pass_std and pass_duration:
        status = 'PASS'
    elif pass_mean and pass_std:
        status = 'WARN_SHORT'
    elif pass_duration:
        status = 'WARN_MOTION'
    else:
        status = 'FAIL'
    
    return {
        'status': status,
        'mean_motion_rad_s': mean_motion,
        'std_motion_rad_s': std_motion,
        'max_motion_rad_s': max_motion,
        'duration_sec': duration_sec,
        'n_samples': len(motion_ref),
        'window_start_sec': float(ref_start),
        'window_end_sec': float(ref_end),
        'pass_mean_threshold': pass_mean,
        'pass_std_threshold': pass_std,
        'pass_duration': pass_duration,
        'is_early_in_recording': pass_early,
        'thresholds': {
            'mean_thresh_rad_s': mean_thresh,
            'std_thresh_rad_s': std_thresh,
            'dur_thresh_sec': dur_thresh
        }
    }


def validate_reference_stability(q_ref: np.ndarray,
                                 q_local: np.ndarray,
                                 ref_start: float,
                                 ref_end: float,
                                 time_s: np.ndarray,
                                 joint_indices: List[int]) -> Dict[str, float]:
    """
    Validate internal consistency of reference quaternions.
    
    Checks:
    - Quaternions in ref window are close to reference (identity error)
    - Low variability within window (self-consistency)
    - No sudden jumps or discontinuities
    
    Args:
        q_ref: Reference quaternions (J, 4)
        q_local: Local quaternions (T, J, 4)
        ref_start: Window start
        ref_end: Window end
        time_s: Time vector
        joint_indices: Joints to check
        
    Returns:
        Dictionary with stability metrics
    """
    ref_mask = (time_s >= ref_start) & (time_s <= ref_end)
    ref_idxs = np.where(ref_mask)[0]
    
    identity_errors = []
    ref_stds = []
    max_jumps = []
    
    for j in joint_indices:
        if not np.isfinite(q_ref[j]).all():
            continue
        
        # Compute deviation from reference
        q_window = q_local[ref_idxs, j]
        q_window_valid = q_window[np.isfinite(q_window).all(axis=1)]
        
        if len(q_window_valid) < 3:
            continue
        
        # Identity error: deviation from reference
        qd = _quat_mul(_quat_inv(q_ref[j]), q_window_valid)
        qd = _quat_shortest(_quat_normalize(qd))
        rotvec = R.from_quat(qd).as_rotvec()
        mag = np.linalg.norm(rotvec, axis=1)
        
        identity_errors.append(np.mean(mag))
        ref_stds.append(np.std(mag))
        
        # Check for jumps (consecutive frame differences)
        if len(q_window_valid) > 1:
            jumps = []
            for i in range(len(q_window_valid) - 1):
                dq = _quat_mul(_quat_inv(q_window_valid[i]), q_window_valid[i+1])
                dq = _quat_shortest(_quat_normalize(dq))
                rv = R.from_quat(dq).as_rotvec()
                jumps.append(np.linalg.norm(rv))
            max_jumps.append(np.max(jumps) if jumps else 0.0)
    
    return {
        'identity_error_mean_rad': float(np.nanmedian(identity_errors)) if identity_errors else np.nan,
        'reference_std_mean_rad': float(np.nanmedian(ref_stds)) if ref_stds else np.nan,
        'max_jump_rad': float(np.nanmax(max_jumps)) if max_jumps else np.nan,
        'n_joints_validated': len(identity_errors)
    }


def compare_reference_with_ground_truth(q_ref_detected: np.ndarray,
                                       q_ref_ground_truth: np.ndarray,
                                       joint_indices: List[int]) -> Dict[str, any]:
    """
    Compare automatically detected reference with ground truth (e.g., T-pose).
    
    Use this when you have a known calibration pose for validation.
    
    Args:
        q_ref_detected: Detected reference quaternions (J, 4)
        q_ref_ground_truth: Ground truth reference quaternions (J, 4)
        joint_indices: Joints to compare
        
    Returns:
        Dictionary with comparison metrics
        
    Reference:
        Sabatini (2006): Static pose calibration validation
    """
    errors = []
    
    for j in joint_indices:
        if not (np.isfinite(q_ref_detected[j]).all() and 
                np.isfinite(q_ref_ground_truth[j]).all()):
            continue
        
        # Compute relative rotation between detected and ground truth
        q_error = _quat_mul(_quat_inv(q_ref_ground_truth[j]), q_ref_detected[j])
        q_error = _quat_shortest(_quat_normalize(q_error))
        
        # Convert to angle
        rotvec = R.from_quat(q_error).as_rotvec()
        error_rad = np.linalg.norm(rotvec)
        error_deg = np.degrees(error_rad)
        
        errors.append({
            'joint_idx': j,
            'error_rad': float(error_rad),
            'error_deg': float(error_deg)
        })
    
    if not errors:
        return {
            'status': 'FAIL',
            'reason': 'no_valid_joints',
            'n_joints': 0
        }
    
    error_vals = [e['error_deg'] for e in errors]
    mean_error = np.mean(error_vals)
    max_error = np.max(error_vals)
    
    # Classification (Sabatini 2006: <5° excellent, <10° good)
    if mean_error < 5.0:
        status = 'EXCELLENT'
    elif mean_error < 10.0:
        status = 'GOOD'
    elif mean_error < 15.0:
        status = 'ACCEPTABLE'
    else:
        status = 'POOR'
    
    return {
        'status': status,
        'mean_error_deg': float(mean_error),
        'max_error_deg': float(max_error),
        'std_error_deg': float(np.std(error_vals)),
        'n_joints': len(errors),
        'per_joint_errors': errors
    }


def generate_motion_profile_plot_data(motion_profile: Dict[str, np.ndarray],
                                     ref_start: float,
                                     ref_end: float,
                                     search_window_sec: float = 10.0) -> Dict[str, any]:
    """
    Generate data structure for plotting motion profile with reference window.
    
    Returns data suitable for visualization without matplotlib dependency.
    
    Args:
        motion_profile: Output from compute_motion_profile()
        ref_start: Reference window start
        ref_end: Reference window end
        search_window_sec: Time window to plot
        
    Returns:
        Dictionary with plot data
    """
    # Limit to search window
    time = motion_profile['time']
    mask = time <= search_window_sec
    
    plot_data = {
        'time': time[mask].tolist(),
        'motion_smooth': motion_profile['motion_smooth'][mask].tolist(),
        'motion_raw': motion_profile['motion_raw'][mask].tolist(),
        'reference_window': {
            'start': float(ref_start),
            'end': float(ref_end)
        },
        'annotations': {
            'search_end': float(search_window_sec),
            'mean_motion_in_ref': float(np.nanmean(
                motion_profile['motion_smooth'][
                    (time >= ref_start) & (time <= ref_end)
                ]
            ))
        }
    }
    
    return plot_data


# Helper functions (quaternion operations)

def _quat_normalize(q, eps=1e-12):
    """Normalize quaternion to unit length."""
    n = np.linalg.norm(q, axis=-1, keepdims=True)
    n = np.maximum(n, eps)
    return q / n


def _quat_inv(q):
    """Quaternion inverse/conjugate."""
    q_inv = q.copy()
    q_inv[..., :3] *= -1.0
    return q_inv


def _quat_mul(q1, q2):
    """Multiply two quaternions."""
    r1 = R.from_quat(q1)
    r2 = R.from_quat(q2)
    return (r1 * r2).as_quat()


def _quat_shortest(q):
    """Enforce shortest path (w >= 0)."""
    q_out = q.copy()
    neg_w = q_out[..., 3] < 0
    q_out[neg_w] *= -1.0
    return q_out


def _moving_average(data, window_size):
    """Compute moving average with edge handling."""
    if window_size < 1:
        return data
    
    if len(data) < window_size:
        return np.full_like(data, np.nanmean(data))
    
    # Use convolution for efficient moving average
    kernel = np.ones(window_size) / window_size
    
    # Pad edges to handle boundaries
    pad_width = window_size // 2
    data_padded = np.pad(data, pad_width, mode='edge')
    
    # Apply convolution
    smoothed = np.convolve(data_padded, kernel, mode='same')
    
    # Remove padding
    return smoothed[pad_width:-pad_width]
