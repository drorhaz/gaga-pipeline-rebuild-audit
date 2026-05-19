import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Any


def build_pos_cols_valid(
    df: pd.DataFrame,
    pos_cols: List[str],
    strict_mode: bool = True,
    joint_complete_axes: bool = True,
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Returns position columns with zero NaNs and an exclusion report.
    
    Args:
        df: DataFrame with position data
        pos_cols: List of position column names (ending with __px, __py, __pz)
        strict_mode: If True, raise error for missing columns. If False, drop missing columns.
        joint_complete_axes: If True, require all 3 axes of a joint to be valid
    
    Returns:
        pos_cols_valid: List of position columns with zero NaNs
        excluded_report: Dictionary with exclusion details
    """
    # Validate inputs
    if not pos_cols:
        raise ValueError("pos_cols cannot be empty")
    
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    
    n_frames = len(df)
    excluded_report = {
        "n_frames": n_frames,
        "pos_cols_total": len(pos_cols),
        "pos_cols_valid": 0,
        "excluded_cols": [],
        "excluded_joints": [],
    }
    
    # Check for missing columns
    missing_cols = [col for col in pos_cols if col not in df.columns]
    if missing_cols:
        if strict_mode:
            raise ValueError(f"Columns not found in DataFrame: {missing_cols}")
        else:
            # Log missing columns and remove them from pos_cols
            for col in missing_cols:
                joint = col.split("__")[0] if "__" in col else "unknown"
                excluded_report["excluded_cols"].append({
                    "col": col,
                    "joint": joint,
                    "nan_count": n_frames,  # All frames are effectively NaN
                    "nan_rate": 1.0,
                    "reason": "missing_column"
                })
            pos_cols = [col for col in pos_cols if col in df.columns]
    
    # Compute NaN counts for each column
    col_nan_info = {}
    for col in pos_cols:
        nan_count = df[col].isna().sum()
        nan_rate = nan_count / n_frames
        col_nan_info[col] = {
            "nan_count": nan_count,
            "nan_rate": nan_rate,
            "joint": col.split("__")[0] if "__" in col else "unknown"
        }
    
    # Build initial list of valid columns (zero NaNs)
    pos_cols_valid = [col for col, info in col_nan_info.items() if info["nan_count"] == 0]
    
    # Apply joint completeness rule if requested
    if joint_complete_axes:
        # Group columns by joint from the original pos_cols (not just valid ones)
        joint_cols = {}
        for col in pos_cols:
            joint = col.split("__")[0]
            if joint not in joint_cols:
                joint_cols[joint] = []
            joint_cols[joint].append(col)
        
        # Check which joints have all 3 axes valid
        joints_to_exclude = []
        for joint, cols in joint_cols.items():
            # Check if we have all 3 axes (px, py, pz) in the valid columns
            valid_axes_for_joint = [col for col in cols if col in pos_cols_valid]
            axes = set(col.split("__")[-1] for col in valid_axes_for_joint)
            if len(axes) < 3:  # Missing some axes in valid columns
                joints_to_exclude.append(joint)
        
        # Remove columns from excluded joints
        cols_to_remove = []
        for col in pos_cols_valid:
            joint = col.split("__")[0]
            if joint in joints_to_exclude:
                cols_to_remove.append(col)
        
        # Add excluded joints to report
        for joint in joints_to_exclude:
            joint_all_cols = joint_cols[joint]  # All columns for this joint from original pos_cols
            joint_nan_rates = [col_nan_info.get(col, {}).get("nan_rate", 0.0) for col in joint_all_cols]
            max_nan_rate = max(joint_nan_rates) if joint_nan_rates else 0.0
            
            # Determine reason for exclusion
            joint_valid_cols = [col for col in joint_all_cols if col in pos_cols_valid]
            if len(joint_valid_cols) > 0:
                reason = "partial_axes"
            else:
                reason = "has_nans"
            
            excluded_report["excluded_joints"].append({
                "joint": joint,
                "reason": reason,
                "cols": joint_all_cols,
                "max_nan_rate": max_nan_rate
            })
        
        # Remove the columns
        pos_cols_valid = [col for col in pos_cols_valid if col not in cols_to_remove]
    
    # Add individual column exclusions to report
    for col, info in col_nan_info.items():
        if col not in pos_cols_valid:
            # Skip if already reported as missing column
            already_reported = any(
                exc["col"] == col and exc["reason"] == "missing_column" 
                for exc in excluded_report["excluded_cols"]
            )
            if not already_reported:
                excluded_report["excluded_cols"].append({
                    "col": col,
                    "joint": info["joint"],
                    "nan_count": info["nan_count"],
                    "nan_rate": info["nan_rate"],
                    "reason": "has_nans" if info["nan_count"] > 0 else "other"
                })
    
    # Update final counts
    excluded_report["pos_cols_valid"] = len(pos_cols_valid)
    
    return pos_cols_valid, excluded_report
