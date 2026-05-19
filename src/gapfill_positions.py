"""
Gap filling for positional data using bounded cubic splines.

This module provides functions to identify and fill gaps in motion capture data
while respecting temporal constraints and preventing extrapolation.
"""

import numpy as np
from scipy.interpolate import CubicSpline
from artifacts import detect_velocity_artifacts, expand_artifact_mask


def find_contiguous_runs(df, time_s, min_run_length=5):
    """
    Find contiguous runs of valid data.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with time and position columns
    time_s : np.ndarray
        Time vector
    min_run_length : int
        Minimum frames for a valid run
        
    Returns:
    --------
    runs : list of dict
        List of (start_idx, end_idx) tuples
    """
    # Find NaN indices
    pos_cols = [c for c in df.columns if c.endswith(('__px', '__py', '__pz'))]
    
    if not pos_cols:
        return []
    
    # Create boolean mask for valid data
    valid_mask = ~np.isnan(df[pos_cols].values).any(axis=1)
    
    # Find contiguous runs
    runs = []
    in_run = False
    start_idx = None
    
    for i, is_valid in enumerate(valid_mask):
        if is_valid and not in_run:
            start_idx = i
            in_run = True
        elif not is_valid and in_run:
            end_idx = i - 1
            runs.append((start_idx, end_idx))
            in_run = False
    
    # Filter by minimum length
    runs = [(s, e) for s, e in runs if e - s >= min_run_length]
    
    return runs


def gap_fill_positions(df, time_s, max_gap_s=0.1, min_run_length=5):
    """
    Fill gaps in positional data using bounded cubic splines.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with time and position columns
    time_s : np.ndarray
        Time vector
    max_gap_s : float
        Maximum gap duration to fill (seconds)
    min_run_length : int
        Minimum frames for a valid run
        
    Returns:
    --------
    df_filled : pd.DataFrame
        DataFrame with gaps filled
    """
    # Find contiguous runs
    runs = find_contiguous_runs(df, time_s, min_run_length)
    
    # Initialize filled DataFrame
    df_filled = df.copy()
    
    # Process each run
    for start_idx, end_idx in runs:
        # Extract run data
        run_data = df.iloc[start_idx:end_idx + 1]
        run_time = time_s[start_idx:end_idx + 1]
        
        # Find gaps within this run
        pos_cols = [c for c in run_data.columns if c.endswith(('__px', '__py', '__pz'))]
        run_positions = run_data[pos_cols].values
        
        # Fill gaps for each column
        for i, col in enumerate(pos_cols):
            filled = bounded_spline_interpolation(run_time, run_positions[:, i], max_gap_s)
            df_filled.loc[start_idx:end_idx + 1, col] = filled
    
    return df_filled


def bounded_spline_interpolation(time_points, data, max_gap_s=0.1):
    """
    Fill gaps using bounded cubic spline interpolation.
    
    Parameters:
    -----------
    time_points : np.ndarray
        Time vector
    data : np.ndarray
        Data with NaN gaps
    max_gap_s : float
        Maximum gap duration to fill (seconds)
        
    Returns:
    --------
    filled_data : np.ndarray
        Data with gaps filled
    """
    # Find valid points
    valid_mask = ~np.isnan(data)
    
    if not np.any(valid_mask):
        return data  # No valid points
    
    valid_time = time_points[valid_mask]
    valid_data = data[valid_mask]
    
    # Find gaps
    nan_mask = np.isnan(data)
    gap_starts = np.where(~nan_mask[:-1] & nan_mask[1:])[0] + 1
    gap_ends = np.where(nan_mask[:-1] & nan_mask[1:])[0] + 1
    
    # Fill gaps
    filled_data = data.copy()
    
    for start, end in zip(gap_starts, gap_ends):
        gap_duration = time_points[end] - time_points[start]
        
        # Only fill if gap is small enough
        if gap_duration <= max_gap_s:
            # Interpolate
            interp_time = np.linspace(time_points[start], time_points[end], 100)
            interp_data = np.interp(interp_time, valid_time, valid_data)
            
            # Update only the gap indices (not the full range)
            filled_data[start+1:end] = interp_data[1:-1]
    
    # Strict contract: must return full-length array
    assert len(filled_data) == len(data), f"bounded_spline_interpolation must return full-length vector: got {len(filled_data)}, expected {len(data)}"
    
    return filled_data
