"""
Quaternion Normalization and Drift Correction Module

This module provides robust quaternion normalization with drift detection and correction
for long motion capture sequences where numerical errors can accumulate.

References:
    - Grassia, F. S. (1998). Practical parameterization of rotations using the exponential map.
    - Shoemake, K. (1985). Animating rotation with quaternion curves. SIGGRAPH.
    - Diebel, J. (2006). Representing attitude: Euler angles, unit quaternions, and rotation vectors.
"""

import numpy as np
import pandas as pd
import logging
from typing import Tuple, Dict, Optional, List
from scipy.spatial.transform import Rotation as R

logger = logging.getLogger(__name__)


def normalize_quaternion_safe(q: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """
    Safely normalize quaternion to unit length with numerical stability.
    
    Args:
        q: Quaternion array (..., 4) in xyzw format
        eps: Minimum norm threshold for numerical stability
        
    Returns:
        Normalized quaternion
        
    Reference:
        Grassia (1998): Safe normalization with epsilon threshold
    """
    norm = np.linalg.norm(q, axis=-1, keepdims=True)
    norm = np.maximum(norm, eps)  # Prevent division by zero
    return q / norm


def detect_quaternion_drift(q: np.ndarray, 
                           time_s: Optional[np.ndarray] = None,
                           drift_threshold: float = 0.01) -> Dict[str, any]:
    """
    Detect cumulative quaternion normalization drift over time.
    
    Drift can occur in long captures due to:
    - Numerical precision errors
    - Repeated interpolation operations
    - Integration of angular velocities
    
    Args:
        q: Quaternion array (T, 4) or (T, J, 4)
        time_s: Optional time vector for temporal analysis
        drift_threshold: Threshold for significant drift (default: 0.01)
        
    Returns:
        Dictionary with drift metrics
        
    Reference:
        Shoemake (1985): Quaternion stability requirements
    """
    # Compute norms
    if q.ndim == 2:  # Single sequence (T, 4)
        norms = np.linalg.norm(q, axis=-1)
    elif q.ndim == 3:  # Multiple sequences (T, J, 4)
        norms = np.linalg.norm(q, axis=-1)
    else:
        raise ValueError(f"Invalid quaternion shape: {q.shape}")
    
    # Compute deviation from unit norm
    norm_errors = np.abs(norms - 1.0)
    
    # Statistics
    max_error = float(np.nanmax(norm_errors))
    mean_error = float(np.nanmean(norm_errors))
    std_error = float(np.nanstd(norm_errors))
    
    # Find frames with significant drift
    drift_frames = np.where(norm_errors > drift_threshold)[0]
    drift_percentage = 100.0 * len(drift_frames) / len(norms) if len(norms) > 0 else 0.0
    
    # Temporal analysis (if time provided)
    drift_over_time = None
    drift_rate = None
    if time_s is not None and len(time_s) > 1:
        # Compute drift rate (error per second)
        duration = time_s[-1] - time_s[0]
        if duration > 0:
            drift_rate = float((norm_errors[-1] - norm_errors[0]) / duration)
        
        # Check if drift increases over time (indicates accumulation)
        if len(norm_errors) > 10:
            # Simple linear trend
            from scipy import stats
            slope, _, _, _, _ = stats.linregress(time_s, norm_errors)
            drift_over_time = float(slope)
    
    # Classification
    if max_error < 1e-6:
        status = 'EXCELLENT'
    elif max_error < 1e-3:
        status = 'GOOD'
    elif max_error < 0.01:
        status = 'ACCEPTABLE'
    else:
        status = 'POOR'
    
    return {
        'max_norm_error': max_error,
        'mean_norm_error': mean_error,
        'std_norm_error': std_error,
        'drift_threshold': drift_threshold,
        'drift_frames_count': len(drift_frames),
        'drift_percentage': drift_percentage,
        'drift_status': status,
        'drift_rate_per_sec': drift_rate,
        'drift_temporal_trend': drift_over_time,
        'requires_correction': max_error > 0.01
    }


def renormalize_quaternions_inplace(q: np.ndarray) -> Tuple[np.ndarray, Dict]:
    """
    Renormalize quaternions in-place with drift statistics.
    
    This should be applied:
    - After loading from file
    - After any quaternion operation (SLERP, multiplication, etc.)
    - After integration from angular velocities
    
    Args:
        q: Quaternion array to normalize (modified in-place)
        
    Returns:
        Tuple of (normalized quaternions, normalization stats)
        
    Reference:
        Grassia (1998): Frame-by-frame renormalization best practice
    """
    # Detect drift before normalization
    drift_before = detect_quaternion_drift(q)
    
    # Normalize
    q_norm = normalize_quaternion_safe(q)
    
    # Detect residual errors after normalization
    norms_after = np.linalg.norm(q_norm, axis=-1)
    residual_error = float(np.nanmax(np.abs(norms_after - 1.0)))
    
    stats = {
        'drift_before_normalization': drift_before,
        'residual_error_after': residual_error,
        'normalization_applied': True,
        'frames_corrected': drift_before['drift_frames_count']
    }
    
    if drift_before['max_norm_error'] > 0.01:
        logger.warning(f"Quaternion drift detected: max error = {drift_before['max_norm_error']:.4f}, "
                      f"{drift_before['drift_percentage']:.1f}% of frames corrected")
    else:
        logger.info(f"Quaternion normalization: max drift = {drift_before['max_norm_error']:.6f} (excellent)")
    
    return q_norm, stats


def apply_hemispheric_continuity(q: np.ndarray, inplace: bool = False) -> np.ndarray:
    """
    Enforce hemispheric continuity to prevent quaternion double-cover jumps.
    
    Quaternions q and -q represent the same rotation. This function ensures
    temporal smoothness by flipping quaternions when needed.
    
    Args:
        q: Quaternion array (T, 4) or (T, J, 4)
        inplace: Modify array in-place
        
    Returns:
        Quaternions with enforced continuity
        
    Reference:
        Shoemake (1985): Quaternion interpolation and continuity
    """
    if not inplace:
        q = q.copy()
    
    if q.ndim == 2:  # Single sequence (T, 4)
        for t in range(1, len(q)):
            if np.dot(q[t-1], q[t]) < 0:
                q[t] *= -1
                
    elif q.ndim == 3:  # Multiple sequences (T, J, 4)
        T, J, _ = q.shape
        for j in range(J):
            for t in range(1, T):
                if np.dot(q[t-1, j], q[t, j]) < 0:
                    q[t, j] *= -1
    
    return q


def validate_quaternion_integrity(q: np.ndarray,
                                 time_s: Optional[np.ndarray] = None,
                                 strict: bool = True) -> Dict[str, any]:
    """
    Comprehensive quaternion integrity validation.
    
    Checks:
    1. Normalization (unit length)
    2. Hemispheric continuity (no jumps)
    3. Drift over time
    4. NaN/Inf detection
    
    Args:
        q: Quaternion array
        time_s: Time vector
        strict: Use strict thresholds
        
    Returns:
        Dictionary with validation results
    """
    # Check for invalid values
    has_nan = np.any(np.isnan(q))
    has_inf = np.any(np.isinf(q))
    
    if has_nan or has_inf:
        return {
            'status': 'FAIL',
            'reason': 'NaN or Inf values detected',
            'has_nan': has_nan,
            'has_inf': has_inf
        }
    
    # Check normalization
    drift_metrics = detect_quaternion_drift(q, time_s)
    
    # Check continuity
    if q.ndim == 2:
        dots = np.sum(q[:-1] * q[1:], axis=1)
        min_dot = float(np.min(dots))
        discontinuities = int(np.sum(dots < 0))
    elif q.ndim == 3:
        T, J, _ = q.shape
        all_dots = []
        all_discontinuities = 0
        for j in range(J):
            dots = np.sum(q[:-1, j] * q[1:, j], axis=1)
            all_dots.extend(dots)
            all_discontinuities += np.sum(dots < 0)
        min_dot = float(np.min(all_dots))
        discontinuities = int(all_discontinuities)
    else:
        min_dot = 1.0
        discontinuities = 0
    
    # Apply thresholds
    if strict:
        norm_ok = drift_metrics['max_norm_error'] < 1e-3
        continuity_ok = discontinuities == 0
    else:
        norm_ok = drift_metrics['max_norm_error'] < 0.01
        continuity_ok = discontinuities < (len(q) * 0.01)  # <1% discontinuities
    
    # Overall status
    if norm_ok and continuity_ok:
        status = 'PASS'
    elif norm_ok or continuity_ok:
        status = 'WARN'
    else:
        status = 'FAIL'
    
    return {
        'status': status,
        'normalization_ok': norm_ok,
        'continuity_ok': continuity_ok,
        'drift_metrics': drift_metrics,
        'min_dot_product': min_dot,
        'discontinuities': discontinuities,
        'has_nan': has_nan,
        'has_inf': has_inf
    }


def correct_quaternion_sequence(q: np.ndarray,
                               time_s: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Dict]:
    """
    Apply all quaternion corrections: renormalization + continuity enforcement.
    
    This is the main entry point for quaternion correction in the pipeline.
    
    Args:
        q: Input quaternions
        time_s: Optional time vector
        
    Returns:
        Tuple of (corrected quaternions, correction statistics)
    """
    # 1. Detect issues
    validation_before = validate_quaternion_integrity(q, time_s, strict=False)
    
    # 2. Renormalize
    q_corrected, norm_stats = renormalize_quaternions_inplace(q)
    
    # 3. Enforce continuity
    q_corrected = apply_hemispheric_continuity(q_corrected, inplace=True)
    
    # 4. Validate after correction
    validation_after = validate_quaternion_integrity(q_corrected, time_s, strict=False)
    
    stats = {
        'validation_before': validation_before,
        'normalization_stats': norm_stats,
        'validation_after': validation_after,
        'correction_successful': validation_after['status'] in ['PASS', 'WARN']
    }
    
    logger.info(f"Quaternion correction: {validation_before['status']} -> {validation_after['status']}")
    
    return q_corrected, stats


def get_quaternion_quality_metrics(q: np.ndarray,
                                  time_s: Optional[np.ndarray] = None) -> Dict[str, any]:
    """
    Extract quaternion quality metrics for QC reporting.
    
    Args:
        q: Quaternion array
        time_s: Time vector
        
    Returns:
        Dictionary with metrics for quality report
    """
    drift_metrics = detect_quaternion_drift(q, time_s)
    validation = validate_quaternion_integrity(q, time_s, strict=False)
    
    return {
        'quat_max_norm_deviation': drift_metrics['max_norm_error'],
        'quat_mean_norm_deviation': drift_metrics['mean_norm_error'],
        'quat_drift_detected': drift_metrics['requires_correction'],
        'quat_drift_status': drift_metrics['drift_status'],
        'quat_drift_percentage': drift_metrics['drift_percentage'],
        'quat_continuity_breaks': validation['discontinuities'],
        'quat_integrity_status': validation['status']
    }
