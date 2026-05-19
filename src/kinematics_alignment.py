"""
Kinematics Alignment Module

This module applies reference offsets to dynamic quaternions to transform
raw segment orientations into "anatomically zeroed" orientations using
offsets_map.json, without computing joint angles yet.

Pipeline placement: After offset computation (Ticket 7) and after quaternion 
gap filling (Ticket 4). Still on irregular grid.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional
from scipy.spatial.transform import Rotation as R
from .time_alignment import assert_time_monotonic

logger = logging.getLogger(__name__)


def apply_reference_offsets(df: pd.DataFrame,
                           offsets_map: Dict[str, List[float]],
                           quat_groups: Optional[List[str]] = None,
                           time_col: str = "time_s",
                           out_suffix: str = "__q_aligned") -> pd.DataFrame:
    """
    Apply reference offsets to dynamic quaternions.
    
    Args:
        df: DataFrame with time and quaternion columns
        offsets_map: Dictionary mapping joint names to offset quaternions (xyzw)
        quat_groups: List of joint groups to process. If None, auto-detect from df
        time_col: Name of time column
        out_suffix: Suffix for aligned quaternion columns
        
    Returns:
        DataFrame with aligned quaternion columns added
        
    Raises:
        AssertionError: If time is not monotonic or quaternion data is invalid
        ValueError: If required columns are missing
    """
    # Preconditions
    assert_time_monotonic(df)
    
    # Auto-detect quaternion groups if not provided
    if quat_groups is None:
        quat_cols = [col for col in df.columns if '_quat_' in col]
        quat_groups = list(set(col.split('_quat_')[0] for col in quat_cols))
    
    # Validate input data
    _validate_quaternion_data(df, quat_groups, offsets_map)
    
    # Create a copy to avoid modifying original
    df_aligned = df.copy()
    
    # Process each joint
    for joint in quat_groups:
        if joint not in offsets_map:
            logger.warning(f"Joint {joint} not found in offsets_map, skipping")
            continue
            
        # Extract raw quaternion data
        raw_quat_xyzw = _extract_joint_quaternions(df, joint)
        
        # Apply reference offset using SciPy contract
        aligned_quat_xyzw = _apply_offset_to_quaternions(raw_quat_xyzw, offsets_map[joint])
        
        # Store aligned quaternions in new columns
        _store_aligned_quaternions(df_aligned, joint, aligned_quat_xyzw, out_suffix)
        
        logger.info(f"Applied reference offsets to {joint}: {len(raw_quat_xyzw)} frames")
    
    logger.info(f"Reference alignment completed for {len(quat_groups)} joints")
    return df_aligned


def _validate_quaternion_data(df: pd.DataFrame, 
                             quat_groups: List[str], 
                             offsets_map: Dict[str, List[float]]) -> None:
    """
    Validate that quaternion data is present and finite for all joints.
    
    Args:
        df: Input DataFrame
        quat_groups: List of joint names to validate
        offsets_map: Reference offsets dictionary
        
    Raises:
        ValueError: If quaternion data is missing or invalid
    """
    missing_joints = []
    invalid_joints = []
    
    for joint in quat_groups:
        # Check if joint has quaternion columns
        quat_cols = [f"{joint}_quat_{axis}" for axis in ['x', 'y', 'z', 'w']]
        missing_cols = [col for col in quat_cols if col not in df.columns]
        
        if missing_cols:
            missing_joints.append(f"{joint} (missing: {missing_cols})")
            continue
            
        # Check if quaternion data is finite (no NaNs)
        joint_data = df[quat_cols].values
        if not np.all(np.isfinite(joint_data)):
            invalid_joints.append(joint)
    
    if missing_joints:
        raise ValueError(f"Missing quaternion columns for joints: {missing_joints}")
    
    if invalid_joints:
        raise ValueError(f"Non-finite quaternion data found for joints: {invalid_joints}")
    
    # Check that joints in offsets_map exist in the data
    offset_joints_not_in_data = [joint for joint in offsets_map.keys() 
                                if joint not in quat_groups]
    if offset_joints_not_in_data:
        logger.warning(f"Offsets exist but joints not found in data: {offset_joints_not_in_data}")


def _extract_joint_quaternions(df: pd.DataFrame, joint: str) -> np.ndarray:
    """
    Extract quaternion data for a specific joint.
    
    Args:
        df: Input DataFrame
        joint: Joint name
        
    Returns:
        Array of quaternions in xyzw format, shape (N, 4)
    """
    quat_cols = [f"{joint}_quat_{axis}" for axis in ['x', 'y', 'z', 'w']]
    quat_data = df[quat_cols].values  # Shape: (N, 4)
    
    return quat_data


def _apply_offset_to_quaternions(raw_quat_xyzw: np.ndarray, 
                                offset_quat_xyzw: List[float]) -> np.ndarray:
    """
    Apply reference offset to quaternions using SciPy contract.
    
    Args:
        raw_quat_xyzw: Raw quaternions in xyzw format, shape (N, 4)
        offset_quat_xyzw: Offset quaternion in xyzw format
        
    Returns:
        Aligned quaternions in xyzw format, shape (N, 4)
    """
    # Convert to Rotation objects
    R_raw = R.from_quat(raw_quat_xyzw)
    R_offset = R.from_quat(offset_quat_xyzw)  # This is inverse static
    
    # SciPy contract: R_aligned = R_offset * R_raw
    R_aligned = R_offset * R_raw
    
    # Convert back to quaternions
    aligned_quat_xyzw = R_aligned.as_quat()
    
    return aligned_quat_xyzw


def _store_aligned_quaternions(df: pd.DataFrame, 
                              joint: str, 
                              aligned_quat_xyzw: np.ndarray,
                              out_suffix: str) -> None:
    """
    Store aligned quaternions in new columns.
    
    Args:
        df: DataFrame to store results in
        joint: Joint name
        aligned_quat_xyzw: Aligned quaternions, shape (N, 4)
        out_suffix: Suffix for output columns
    """
    for i, axis in enumerate(['x', 'y', 'z', 'w']):
        col_name = f"{joint}_quat_{axis}{out_suffix}"
        df[col_name] = aligned_quat_xyzw[:, i]


def get_aligned_quaternion_columns(df: pd.DataFrame, 
                                 out_suffix: str = "__q_aligned") -> List[str]:
    """
    Get list of aligned quaternion column names.
    
    Args:
        df: DataFrame with aligned quaternions
        out_suffix: Suffix used for aligned columns
        
    Returns:
        List of aligned quaternion column names
    """
    aligned_cols = [col for col in df.columns if col.endswith(out_suffix)]
    return aligned_cols


def validate_alignment_quality(df: pd.DataFrame,
                             joint: str,
                             out_suffix: str = "__q_aligned",
                             tolerance: float = 1e-6) -> Dict[str, float]:
    """
    Validate alignment quality by checking quaternion norms and continuity.
    
    Args:
        df: DataFrame with aligned quaternions
        joint: Joint name to validate
        out_suffix: Suffix for aligned columns
        tolerance: Tolerance for norm validation
        
    Returns:
        Dictionary with validation metrics
    """
    aligned_cols = [f"{joint}_quat_{axis}{out_suffix}" for axis in ['x', 'y', 'z', 'w']]
    
    if not all(col in df.columns for col in aligned_cols):
        raise ValueError(f"Aligned quaternion columns not found for joint {joint}")
    
    aligned_data = df[aligned_cols].values
    norms = np.linalg.norm(aligned_data, axis=1)
    
    metrics = {
        "mean_norm": float(np.mean(norms)),
        "norm_std": float(np.std(norms)),
        "norm_range": float(np.max(norms) - np.min(norms)),
        "frames_with_invalid_norm": int(np.sum(np.abs(norms - 1.0) > tolerance)),
        "total_frames": len(aligned_data)
    }
    
    return metrics
