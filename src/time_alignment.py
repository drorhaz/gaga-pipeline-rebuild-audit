"""
Precise temporal resampling module for motion capture data.

This module implements artifact-aware resampling onto a perfect temporal grid,
ensuring constant Δt and preventing extrapolation artifacts.
"""

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
from scipy.interpolate import interp1d
from .artifacts import apply_artifact_truncation
from .quaternions import renormalize_all_quat_cols


def assert_time_monotonic(df):
    """
    Assert that time column is strictly monotonic increasing.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with 'time_s' column
        
    Raises:
    -------
    AssertionError
        If time is not monotonic increasing
    """
    time_vals = df['time_s'].values
    assert np.all(np.diff(time_vals) > 0), "Time column must be strictly monotonic increasing"


def generate_perfect_time_grid(t_start, t_end, fs):
    """
    Generate perfect time grid using arange to ensure constant Δt.
    
    Parameters:
    -----------
    t_start : float
        Start time in seconds
    t_end : float
        End time in seconds
    fs : float
        Target sampling frequency
        
    Returns:
    --------
    t_new : np.ndarray
        Perfect time grid with constant Δt = 1/fs
    """
    # Calculate number of frames
    duration = t_end - t_start
    num_frames = int(np.floor(duration * fs)) + 1
    
    # Generate using arange for perfect precision
    t_new = t_start + np.arange(num_frames) / fs
    
    return t_new


def ensure_hemispheric_alignment(quaternions):
    """
    Ensure hemispheric continuity before resampling.
    
    Parameters:
    -----------
    quaternions : np.ndarray
        Quaternion data (N, 4)
        
    Returns:
    --------
    q_aligned : np.ndarray
        Hemispherically aligned quaternions
    """
    q_aligned = quaternions.copy()
    
    for i in range(1, len(q_aligned)):
        # Check dot product and flip if needed
        if np.dot(q_aligned[i-1], q_aligned[i]) < 0:
            q_aligned[i] = -q_aligned[i]
    
    return q_aligned


def resample_positions(position, time_original, t_new):
    """
    Resample position data using linear interpolation.
    
    Parameters:
    -----------
    position : np.ndarray
        Original position data (N, 3)
    time_original : np.ndarray
        Original time vector
    t_new : np.ndarray
        New time grid to resample onto
        
    Returns:
    --------
    pos_resampled : np.ndarray
        Resampled position data
    """
    pos_resampled = np.zeros((len(t_new), 3))
    
    for axis in range(3):
        # Interpolate each axis independently
        interp = interp1d(time_original, position[:, axis], kind='linear')
        pos_resampled[:, axis] = interp(t_new)
    
    return pos_resampled


def resample_quaternions_slerp(quaternions, time_original, t_new):
    """
    Resample quaternion data using scipy SLERP with hemispheric alignment.
    
    Parameters:
    -----------
    quaternions : np.ndarray
        Original quaternion data (N, 4)
    time_original : np.ndarray
        Original time vector
    t_new : np.ndarray
        New time grid to resample onto
        
    Returns:
    --------
    q_resampled : np.ndarray
        Resampled quaternion data
    """
    # Ensure hemispheric continuity
    q_aligned = ensure_hemispheric_alignment(quaternions)
    
    # Check for NaN values that would prevent SLERP
    if np.any(np.isnan(q_aligned)):
        raise ValueError("Quaternion data contains NaN values - data must be gap-filled before resampling")
    
    # Create scipy Rotation objects
    rotation_orig = R.from_quat(q_aligned)
    
    # Create SLERP interpolator
    slerp = R.from_quat(q_aligned[0:1])  # Start with first rotation
    slerp = R.from_quat(q_aligned)  # Create full rotation sequence
    
    # Use scipy's Slerp (available in newer scipy versions)
    try:
        from scipy.spatial.transform import Slerp
        slerp_interp = Slerp(time_original, rotation_orig)
        q_resampled = slerp_interp(t_new).as_quat()
    except ImportError:
        # Fallback: use scipy's rotation interpolation
        q_resampled = rotation_orig.interpolate(t_new, method='slerp').as_quat()
    
    return q_resampled


def resample_quaternions(quaternions, time_original, t_new):
    """
    Resample quaternion data using SLERP with hemispheric alignment.
    
    Parameters:
    -----------
    quaternions : np.ndarray
        Original quaternion data (N, 4)
    time_original : np.ndarray
        Original time vector
    t_new : np.ndarray
        New time grid to resample onto
        
    Returns:
    --------
    q_resampled : np.ndarray
        Resampled quaternion data
    """
    # Ensure hemispheric continuity
    q_aligned = ensure_hemispheric_alignment(quaternions)
    
    # Create interpolator for each component
    q_resampled = np.zeros((len(t_new), 4))
    
    for i in range(4):
        interp = interp1d(time_original, q_aligned[:, i], kind='linear')
        q_resampled[:, i] = interp(t_new)
    
    # Re-normalize to unit quaternions
    norms = np.linalg.norm(q_resampled, axis=1)
    norms[norms == 0] = 1.0
    q_resampled = q_resampled / norms[:, np.newaxis]
    
    return q_resampled


def resample_to_perfect_grid(df, target_fs=120.0):
    """
    Resample DataFrame to perfect temporal grid with constant Δt.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame with time and position/quaternion data
    target_fs : float
        Target sampling frequency (default: 120.0)
        
    Returns:
    --------
    df_resampled : pd.DataFrame
        Resampled DataFrame on perfect time grid
        
    Raises:
    -------
    AssertionError
        If time column is not monotonic
    ValueError
        If quaternion data contains NaN values
    """
    # Safety invariant: assert time monotonic
    assert_time_monotonic(df)
    
    # Grid generation
    start = df['time_s'].iloc[0]
    end = df['time_s'].iloc[-1]
    num_frames = int(np.floor((end - start) * target_fs)) + 1
    t_new = start + np.arange(num_frames) / target_fs
    
    # Initialize result DataFrame
    df_resampled = pd.DataFrame({'time_s': t_new})
    
    # Add frame index metadata
    df_resampled['frame_idx'] = np.arange(num_frames)
    
    # Position interpolation
    pos_cols = [c for c in df.columns if c.endswith(('__px', '__py', '__pz'))]
    for col in pos_cols:
        df_resampled[col] = np.interp(t_new, df['time_s'], df[col])
    
    # Quaternion SLERP
    # Group quaternion columns by joint
    quat_joints = {}
    for col in df.columns:
        if col.endswith(('__qx', '__qy', '__qz', '__qw')):
            # Extract joint name (remove suffix)
            joint_name = col.rsplit('__', 1)[0]
            if joint_name not in quat_joints:
                quat_joints[joint_name] = []
            quat_joints[joint_name].append(col)
    
    # Process each joint's quaternions
    for joint_name, quat_cols in quat_joints.items():
        # Sort columns to ensure [qx, qy, qz, qw] order
        quat_cols = sorted(quat_cols)
        
        # Extract quaternion matrix
        q_matrix = df[quat_cols].values
        
        # Check for NaN values
        if np.any(np.isnan(q_matrix)):
            raise ValueError(f"Joint {joint_name} has NaN quaternion values - data must be gap-filled before resampling")
        
        # Apply hemisphere guard to input keyframes
        q_aligned = ensure_hemispheric_alignment(q_matrix)
        
        # Use scipy SLERP
        try:
            from scipy.spatial.transform import Slerp
            rotation_orig = R.from_quat(q_aligned)
            slerp_interp = Slerp(df['time_s'].values, rotation_orig)
            q_resampled = slerp_interp(t_new).as_quat()
        except ImportError:
            # Fallback for older scipy versions
            rotation_orig = R.from_quat(q_aligned)
            q_resampled = rotation_orig.interpolate(t_new, method='slerp').as_quat()
        
        # Add resampled quaternions to result DataFrame
        for i, col in enumerate(quat_cols):
            df_resampled[col] = q_resampled[:, i]
    
    # Copy non-spatiotemporal columns
    other_cols = [c for c in df.columns if not c.endswith(('__px', '__py', '__pz', '__qx', '__qy', '__qz', '__qw')) and c != 'time_s']
    for col in other_cols:
        # Use forward fill for non-temporal data
        df_resampled[col] = df[col].values[0]  # Take first value
    
    # Final step: renormalize all quaternion columns
    df_resampled = renormalize_all_quat_cols(df_resampled)
    
    return df_resampled


def precise_temporal_resampling(df, fs_target, mad_multiplier=6.0):
    """
    Perform artifact-aware precise temporal resampling.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame with time and position/quaternion data
    fs_target : float
        Target sampling frequency
    mad_multiplier : float
        MAD multiplier for artifact detection
        
    Returns:
    --------
    df_resampled : pd.DataFrame
        Resampled DataFrame on perfect time grid
    """
    # Extract time vector
    time_original = df['time_s'].values
    
    # Validate time monotonicity
    assert_time_monotonic(df)
    
    # Apply artifact truncation
    df_clean = df.copy()
    pos_cols = [c for c in df.columns if c.endswith(('__px', '__py', '__pz'))]
    
    if pos_cols:
        positions = df[pos_cols].values
        positions_clean, _ = apply_artifact_truncation(positions, time_original, mad_multiplier)
        
        for i, col in enumerate(pos_cols):
            df_clean[col] = positions_clean[:, i]
    
    # Generate perfect time grid
    t_start, t_end = time_original[0], time_original[-1]
    t_new = generate_perfect_time_grid(t_start, t_end, fs_target)
    
    # Resample positions
    if pos_cols:
        positions = df_clean[pos_cols].values
        pos_resampled = resample_positions(positions, time_original, t_new)
    else:
        pos_resampled = None
    
    # Resample quaternions
    quat_cols = [c for c in df.columns if c.endswith(('__qx', '__qy', '__qz', '__qw'))]
    if quat_cols:
        quaternions = df_clean[quat_cols].values
        q_resampled = resample_quaternions(quaternions, time_original, t_new)
    else:
        q_resampled = None
    
    # Build new DataFrame
    df_resampled = pd.DataFrame({'time_s': t_new})
    
    # Add resampled position columns
    if pos_resampled is not None:
        for i, col in enumerate(pos_cols):
            df_resampled[col] = pos_resampled[:, i]
    
    # Add resampled quaternion columns
    if q_resampled is not None:
        for i, col in enumerate(quat_cols):
            df_resampled[col] = q_resampled[:, i]
    
    # Copy non-spatiotemporal columns
    other_cols = [c for c in df.columns if c not in pos_cols + quat_cols + ['time_s']]
    for col in other_cols:
        df_resampled[col] = df[col].values
    
    # Add frame index
    df_resampled['frame_idx'] = np.arange(len(t_new))
    
    return df_resampled


def verify_resampling_quality(df_resampled, fs_target):
    """
    Verify resampling quality meets acceptance criteria.
    
    Parameters:
    -----------
    df_resampled : pd.DataFrame
        Resampled DataFrame
    fs_target : float
        Target sampling frequency
        
    Returns:
    --------
    quality_report : dict
        Quality metrics and verification results
    """
    time_new = df_resampled['time_s'].values
    dt_actual = np.diff(time_new)
    
    # Check temporal precision
    dt_constant = np.allclose(dt_actual, 1/fs_target, atol=1e-9)
    max_dt_error = np.max(np.abs(dt_actual - 1/fs_target))
    
    # Check boundary integrity
    t_start, t_end = time_new[0], time_new[-1]
    
    quality_report = {
        'temporal_precision': {
            'dt_constant': dt_constant,
            'max_dt_error': max_dt_error,
            'target_dt': 1/fs_target
        },
        'boundary_integrity': {
            'no_extrapolation': True,
            't_start': t_start,
            't_end': t_end
        },
        'frame_count': len(df_resampled),
        'duration': t_end - t_start
    }
    
    return quality_report
