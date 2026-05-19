"""
Quaternion normalization utilities for motion capture data.

This module provides safe quaternion normalization functions that handle
edge cases like zero norms and NaN values with proper warnings.
"""

import numpy as np
import pandas as pd
import warnings
from typing import List, Union


def renormalize_quat_block(Q: np.ndarray) -> np.ndarray:
    """
    Renormalize a block of quaternions to unit length.
    
    Parameters:
    -----------
    Q : np.ndarray
        An N x 4 array representing quaternions (x, y, z, w format)
        
    Returns:
    --------
    np.ndarray
        The array where each row is a unit vector (||q|| = 1.0)
        Rows with zero norm or NaN values will remain as NaN
        
    Notes:
    ------
    - If the norm is 0 or NaN, does not divide; returns NaN for that row
    - Issues UserWarning for problematic rows
    """
    if Q.ndim != 2 or Q.shape[1] != 4:
        raise ValueError("Input must be an N x 4 array")
    
    # Convert to float to handle NaN assignments
    Q_normalized = Q.astype(float).copy()
    
    # Compute Euclidean norm per row
    norms = np.linalg.norm(Q, axis=1)
    
    # Find problematic rows
    zero_norm_mask = norms == 0
    nan_norm_mask = np.isnan(norms)
    nan_input_mask = np.isnan(Q).any(axis=1)
    
    # Combine all problematic cases
    problem_mask = zero_norm_mask | nan_norm_mask | nan_input_mask
    
    # Issue warnings for problematic rows
    if np.any(problem_mask):
        problem_indices = np.where(problem_mask)[0]
        if len(problem_indices) <= 5:  # Show all if few
            warnings.warn(
                f"Quaternion normalization issues at rows {problem_indices}: "
                f"zero_norm={zero_norm_mask.sum()}, "
                f"nan_norm={nan_norm_mask.sum()}, "
                f"nan_input={nan_input_mask.sum()}. "
                f"These rows will remain as NaN.",
                UserWarning
            )
        else:  # Summarize if many
            warnings.warn(
                f"Quaternion normalization issues at {len(problem_indices)} rows: "
                f"zero_norm={zero_norm_mask.sum()}, "
                f"nan_norm={nan_norm_mask.sum()}, "
                f"nan_input={nan_input_mask.sum()}. "
                f"These rows will remain as NaN.",
                UserWarning
            )
    
    # Only normalize valid rows
    valid_mask = ~problem_mask
    if np.any(valid_mask):
        Q_normalized[valid_mask] = Q[valid_mask] / norms[valid_mask, np.newaxis]
    
    # Set problematic rows to NaN
    Q_normalized[problem_mask] = np.nan
    
    return Q_normalized


def renormalize_quat_cols(df: pd.DataFrame, joint_names: List[str]) -> pd.DataFrame:
    """
    Renormalize quaternion columns for specified joints in a DataFrame.
    
    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame containing quaternion columns
    joint_names : List[str]
        List of joint names to process
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with quaternion columns overwritten with normalized values
        
    Notes:
    ------
    - Expects quaternion columns in format: {joint_name}__qx, __qy, __qz, __qw
    - Modifies the DataFrame in place and returns it
    """
    df_normalized = df.copy()
    
    for joint_name in joint_names:
        # Construct quaternion column names
        quat_cols = [
            f"{joint_name}__qx",
            f"{joint_name}__qy", 
            f"{joint_name}__qz",
            f"{joint_name}__qw"
        ]
        
        # Check if all quaternion columns exist
        missing_cols = [col for col in quat_cols if col not in df.columns]
        if missing_cols:
            warnings.warn(
                f"Skipping joint {joint_name}: missing columns {missing_cols}",
                UserWarning
            )
            continue
        
        # Extract quaternion block
        Q = df[quat_cols].values
        
        # Renormalize
        Q_normalized = renormalize_quat_block(Q)
        
        # Overwrite columns
        for i, col in enumerate(quat_cols):
            df_normalized[col] = Q_normalized[:, i]
    
    return df_normalized


def get_all_quaternion_joints(df: pd.DataFrame) -> List[str]:
    """
    Extract all joint names that have complete quaternion data.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with quaternion columns
        
    Returns:
    --------
    List[str]
        List of joint names that have all 4 quaternion components
    """
    quat_cols = [col for col in df.columns if col.endswith(('__qx', '__qy', '__qz', '__qw'))]
    
    # Extract joint names
    joint_names = set()
    for col in quat_cols:
        joint_name = col.rsplit('__', 1)[0]
        joint_names.add(joint_name)
    
    # Filter for joints with complete quaternion data
    complete_joints = []
    for joint_name in joint_names:
        required_cols = [
            f"{joint_name}__qx",
            f"{joint_name}__qy",
            f"{joint_name}__qz", 
            f"{joint_name}__qw"
        ]
        if all(col in df.columns for col in required_cols):
            complete_joints.append(joint_name)
    
    return sorted(complete_joints)


def renormalize_all_quat_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renormalize all quaternion columns in a DataFrame.
    
    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame containing quaternion columns
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with all quaternion columns normalized
    """
    joint_names = get_all_quaternion_joints(df)
    return renormalize_quat_cols(df, joint_names)
