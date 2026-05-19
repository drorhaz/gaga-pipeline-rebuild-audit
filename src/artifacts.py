"""
Artifact detection module implementing Skurowski-style truncation.

This module provides functions to detect and mask non-physiological spikes
in motion capture data using robust statistical methods.
"""

import numpy as np
from scipy.stats import median_abs_deviation
from scipy.ndimage import binary_dilation


def detect_velocity_artifacts(velocity, mad_multiplier=6.0, sigma_floor=1e-6):
    """
    Detect velocity artifacts using per-axis MAD scaling.
    
    Parameters:
    -----------
    velocity : np.ndarray
        Velocity data (N, 3) for XYZ axes
    mad_multiplier : float
        Multiplier for MAD threshold (default: 6.0)
    sigma_floor : float
        Minimum sigma to prevent over-masking static markers (default: 1e-6)
        
    Returns:
    --------
    artifact_mask : np.ndarray
        Boolean mask where True indicates artifacts
    """
    # Robust scale per axis (already normalized to std-equivalent)
    sigma = median_abs_deviation(velocity, axis=0, scale='normal')
    sigma = np.maximum(sigma, sigma_floor)

    artifact_mask = np.abs(velocity) > (mad_multiplier * sigma[np.newaxis, :])
    return artifact_mask


def expand_artifact_mask(artifact_mask, dilation_frames=1):
    """
    Expand artifact mask by ±dilation_frames using 1D binary dilation.
    
    Parameters:
    -----------
    artifact_mask : np.ndarray
        Boolean mask of artifact frames (N, 3)
    dilation_frames : int
        Number of frames to expand on each side (default: 1)
        
    Returns:
    --------
    expanded_mask : np.ndarray
        1D dilated mask capturing ramp up/down (N,)
    """
    structure = np.ones(2 * dilation_frames + 1)

    expanded_mask = np.zeros_like(artifact_mask, dtype=bool)
    for axis in range(artifact_mask.shape[1]):
        expanded_mask[:, axis] = binary_dilation(artifact_mask[:, axis], structure=structure)

    return np.any(expanded_mask, axis=1)


def compute_true_velocity(position, time_s):
    """
    Compute true velocity using irregular time stamps.
    
    Parameters:
    -----------
    position : np.ndarray
        Position data (N, 3)
    time_s : np.ndarray
        Time vector in seconds
        
    Returns:
    --------
    velocity : np.ndarray
        True velocity in units/second
    """
    # Compute dt for each frame
    dt = np.diff(time_s)
    
    # Guard against division by zero and jitter
    dt = np.maximum(dt, 1e-9)
    
    # Compute velocity: v[i] = (pos[i] - pos[i-1]) / dt[i-1]
    velocity = np.zeros_like(position)
    dt_expanded = dt.reshape(-1, 1)  # Shape: (N-1, 1) 
    pos_diff = position[1:] - position[:-1]  # Shape: (N-1, 3)
    velocity[1:] = pos_diff / dt_expanded
    
    return velocity


def apply_artifact_truncation(position, time_s, mad_multiplier=6.0, dilation_frames=1):
    """
    Apply Skurowski-style artifact truncation to position data.
    
    Parameters:
    -----------
    position : np.ndarray
        Position data (N, 3)
    time_s : np.ndarray
        Time vector in seconds
    mad_multiplier : float
        Multiplier for MAD threshold (default: 6.0)
    dilation_frames : int
        Number of frames to expand on each side (default: 1)
        
    Returns:
    --------
    position_clean : np.ndarray
        Position data with artifacts masked as NaN
    artifact_mask_raw : np.ndarray
        Raw per-axis artifact mask (N, 3)
    artifact_mask_expanded : np.ndarray
        Expanded 1D artifact mask (N,)
    """
    velocity = compute_true_velocity(position, time_s)

    artifact_mask_raw = detect_velocity_artifacts(velocity, mad_multiplier=mad_multiplier)
    artifact_mask_expanded = expand_artifact_mask(artifact_mask_raw, dilation_frames=dilation_frames)

    position_clean = position.copy().astype(float)
    
    # Apply expanded mask to all axes (broadcast correctly)
    if len(position.shape) == 2:  # 2D case (N, 3)
        position_clean[artifact_mask_expanded, :] = np.nan
    else:  # 1D case (N,)
        position_clean[artifact_mask_expanded] = np.nan
    
    return position_clean, artifact_mask_raw, artifact_mask_expanded
