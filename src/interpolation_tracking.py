"""
Enhancement 2: Per-Joint Interpolation Tracking
Required for Section 3: Gap & Interpolation Transparency (Winter, 2009)
"""

import numpy as np
import pandas as pd

def compute_per_joint_interpolation_stats(df_pre, df_post, max_gap):
    """
    Track interpolation method and statistics per joint.
    
    Parameters:
    -----------
    df_pre : pd.DataFrame
        DataFrame before interpolation
    df_post : pd.DataFrame  
        DataFrame after interpolation
    max_gap : int
        Maximum gap size allowed for interpolation (frames)
        
    Returns:
    --------
    dict : Per-joint interpolation statistics
        Keys are joint names, values are dicts with:
        - method: Interpolation method used
        - frames_fixed_percent: Percentage of frames interpolated
        - frames_fixed_count: Number of values interpolated
        - max_gap_frames: Largest gap for this joint
        - nans_remaining: Remaining NaN values
    """
    interpolation_per_joint = {}
    
    # Get all joints from columns
    pos_cols = [c for c in df_pre.columns if c.endswith(('__px', '__py', '__pz'))]
    joints = set(c.split('__')[0] for c in pos_cols)
    
    for joint in joints:
        joint_cols = [f"{joint}__{suffix}" for suffix in ['px', 'py', 'pz', 'qx', 'qy', 'qz', 'qw']]
        # CRITICAL: Check that columns exist in BOTH dataframes
        # Some joints may be filtered out during standardization (Cell 03)
        joint_cols = [c for c in joint_cols if c in df_pre.columns and c in df_post.columns]
        
        if not joint_cols:
            continue
        
        # Calculate missing data for this joint
        joint_pre = df_pre[joint_cols]
        joint_post = df_post[joint_cols]
        
        total_values = joint_pre.size
        nans_pre = joint_pre.isna().sum().sum()
        nans_post = joint_post.isna().sum().sum()
        frames_fixed = nans_pre - nans_post
        frames_fixed_percent = (frames_fixed / total_values) * 100 if total_values > 0 else 0.0
        
        has_quaternions = any(c.endswith(('__qx', '__qy', '__qz', '__qw')) for c in joint_cols)
        
        if frames_fixed > 0:
            if has_quaternions:
                method = "slerp"
            else:
                method = "pchip_single_pass"
            method_note = method
        else:
            method = "none_required"
            method_note = "pristine"
        
        # Find maximum gap size for this joint
        max_gap_frames = 0
        for col in joint_cols:
            if col in df_pre.columns:
                # Find consecutive NaN runs
                is_nan = df_pre[col].isna().astype(int)
                nan_groups = (is_nan != is_nan.shift()).cumsum()
                gap_sizes = is_nan.groupby(nan_groups).sum()
                if len(gap_sizes) > 0:
                    max_gap_frames = max(max_gap_frames, gap_sizes.max())
        
        interpolation_per_joint[joint] = {
            'method': method,
            'method_category': method_note,
            'frames_fixed_percent': round(frames_fixed_percent, 2),
            'frames_fixed_count': int(frames_fixed),
            'max_gap_frames': int(max_gap_frames),
            'nans_remaining': int(nans_post)
        }
    
    return interpolation_per_joint
