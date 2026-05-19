"""
Bone Length Validation: Static vs. Dynamic Comparison
=====================================================
Per Rácz et al. (2025) - Verify skeleton integrity across conditions

CRITICAL: Comparing static calibration bone lengths to dynamic trial bone lengths
detects marker drift, swap, or poor tracking. If a bone "stretches" by >2% during
movement, it indicates a fundamental tracking problem.

Author: Gaga Motion Analysis Pipeline
Date: 2026-01-22
"""

import numpy as np
import pandas as pd

# ============================================================
# VALIDATION THRESHOLDS
# ============================================================

BONE_LENGTH_VARIANCE_THRESHOLD = 2.0  # Percent difference threshold
MARKER_DRIFT_THRESHOLD = 5.0  # Percent - indicates serious drift
SWAP_THRESHOLD = 10.0  # Percent - likely marker swap


def compute_bone_length_timeseries(pos_dict, parent_joint, child_joint):
    """
    Compute bone length over time from position data.
    
    Parameters:
    -----------
    pos_dict : dict
        Dictionary with joint positions {joint_name: (T, 3) array}
    parent_joint : str
        Parent joint name
    child_joint : str
        Child joint name
        
    Returns:
    --------
    np.ndarray : Bone lengths over time (T,)
    """
    if parent_joint not in pos_dict or child_joint not in pos_dict:
        return None
    
    parent_pos = pos_dict[parent_joint]
    child_pos = pos_dict[child_joint]
    
    # Compute Euclidean distance
    diff = child_pos - parent_pos
    lengths = np.sqrt(np.sum(diff**2, axis=1))
    
    return lengths


def compare_static_dynamic_bones(static_lengths, dynamic_lengths, bone_hierarchy):
    """
    Compare bone lengths between static calibration and dynamic trial.
    
    Parameters:
    -----------
    static_lengths : dict
        Static bone lengths {bone_name: length_mm}
    dynamic_lengths : dict
        Dynamic bone length timeseries {bone_name: (T,) array}
    bone_hierarchy : list
        List of (parent, child) bone tuples
        
    Returns:
    --------
    pd.DataFrame : Comparison results with validation status
    """
    results = []
    
    for parent, child in bone_hierarchy:
        bone_name = f"{parent}->{child}"
        
        # Get static length
        static_length = static_lengths.get(bone_name)
        if static_length is None:
            continue
        
        # Get dynamic lengths
        dynamic_ts = dynamic_lengths.get(bone_name)
        if dynamic_ts is None or len(dynamic_ts) == 0:
            continue
        
        # Remove NaN values
        dynamic_ts_clean = dynamic_ts[~np.isnan(dynamic_ts)]
        if len(dynamic_ts_clean) == 0:
            continue
        
        # Compute dynamic statistics
        dynamic_mean = np.mean(dynamic_ts_clean)
        dynamic_std = np.std(dynamic_ts_clean)
        dynamic_min = np.min(dynamic_ts_clean)
        dynamic_max = np.max(dynamic_ts_clean)
        dynamic_cv = (dynamic_std / dynamic_mean) * 100 if dynamic_mean > 0 else 0
        
        # Compute percent difference from static
        percent_diff = abs(dynamic_mean - static_length) / static_length * 100
        
        # Determine validation status
        if percent_diff > SWAP_THRESHOLD:
            status = "❌ SWAP_SUSPECTED"
            notes = f"Bone length differs by {percent_diff:.1f}% - possible marker swap"
        elif percent_diff > MARKER_DRIFT_THRESHOLD:
            status = "🟡 DRIFT"
            notes = f"Significant drift detected ({percent_diff:.1f}%)"
        elif percent_diff > BONE_LENGTH_VARIANCE_THRESHOLD:
            status = "⚠️ REVIEW"
            notes = f"Variance {percent_diff:.1f}% > threshold {BONE_LENGTH_VARIANCE_THRESHOLD}%"
        else:
            status = "✅ PASS"
            notes = "Rigid body integrity confirmed"
        
        results.append({
            'Bone': bone_name,
            'Static_Length_mm': round(static_length, 1),
            'Dynamic_Mean_mm': round(dynamic_mean, 1),
            'Dynamic_Std_mm': round(dynamic_std, 3),
            'Dynamic_CV%': round(dynamic_cv, 3),
            'Percent_Diff%': round(percent_diff, 2),
            'Status': status,
            'Notes': notes
        })
    
    df = pd.DataFrame(results)
    
    # Sort by percent difference (worst first)
    df = df.sort_values('Percent_Diff%', ascending=False).reset_index(drop=True)
    
    return df


def validate_bone_lengths_from_dataframe(df, static_reference, bone_hierarchy):
    """
    Validate bone lengths comparing static reference to dynamic DataFrame.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Dynamic trial DataFrame with position columns (__px, __py, __pz)
    static_reference : dict
        Static bone lengths from calibration {bone_name: length_mm}
    bone_hierarchy : list
        List of (parent, child) bone tuples
        
    Returns:
    --------
    tuple : (df_validation, summary_dict)
    """
    # Extract positions from DataFrame
    pos_dict = {}
    joints = set()
    
    for col in df.columns:
        if col.endswith('__px'):
            joint = col.replace('__px', '')
            joints.add(joint)
            
            px = df[f'{joint}__px'].values
            py = df[f'{joint}__py'].values
            pz = df[f'{joint}__pz'].values
            
            pos_dict[joint] = np.stack([px, py, pz], axis=1)
    
    # Compute dynamic bone lengths
    dynamic_lengths = {}
    for parent, child in bone_hierarchy:
        bone_name = f"{parent}->{child}"
        lengths_ts = compute_bone_length_timeseries(pos_dict, parent, child)
        if lengths_ts is not None:
            dynamic_lengths[bone_name] = lengths_ts
    
    # Compare static vs dynamic
    df_validation = compare_static_dynamic_bones(
        static_reference, dynamic_lengths, bone_hierarchy
    )
    
    # Generate summary
    if len(df_validation) == 0:
        summary = {
            'total_bones': 0,
            'bones_pass': 0,
            'bones_review': 0,
            'bones_drift': 0,
            'bones_swap': 0,
            'overall_status': 'NO_DATA',
            'mean_percent_diff': 0.0,
            'max_percent_diff': 0.0
        }
    else:
        summary = {
            'total_bones': len(df_validation),
            'bones_pass': (df_validation['Status'] == '✅ PASS').sum(),
            'bones_review': (df_validation['Status'] == '⚠️ REVIEW').sum(),
            'bones_drift': (df_validation['Status'] == '🟡 DRIFT').sum(),
            'bones_swap': (df_validation['Status'] == '❌ SWAP_SUSPECTED').sum(),
            'overall_status': determine_overall_status(df_validation),
            'mean_percent_diff': float(df_validation['Percent_Diff%'].mean()),
            'max_percent_diff': float(df_validation['Percent_Diff%'].max()),
            'worst_bone': df_validation.iloc[0]['Bone'] if len(df_validation) > 0 else None
        }
    
    return df_validation, summary


def determine_overall_status(df_validation):
    """Determine overall validation status from results."""
    if (df_validation['Status'] == '❌ SWAP_SUSPECTED').any():
        return 'REJECT'
    elif (df_validation['Status'] == '🟡 DRIFT').any():
        return 'CAUTION'
    elif (df_validation['Status'] == '⚠️ REVIEW').any():
        return 'REVIEW'
    else:
        return 'PASS'


def extract_static_reference_from_json(static_json_path):
    """
    Extract static bone lengths from reference JSON.
    
    Parameters:
    -----------
    static_json_path : str
        Path to reference_metadata.json or calibration_summary.json
        
    Returns:
    --------
    dict : Static bone lengths {bone_name: length_mm}
    """
    import json
    
    with open(static_json_path) as f:
        data = json.load(f)
    
    # Extract static bone lengths if available
    # Format depends on your specific JSON structure
    # This is a template - adjust based on actual format
    
    static_lengths = {}
    
    if 'static_bone_lengths' in data:
        static_lengths = data['static_bone_lengths']
    elif 'calibration' in data and 'bone_lengths' in data['calibration']:
        static_lengths = data['calibration']['bone_lengths']
    
    return static_lengths


def export_bone_validation_report(df_validation, summary, run_id, save_path):
    """
    Export bone length validation report to JSON.
    
    Parameters:
    -----------
    df_validation : pd.DataFrame
        Validation results
    summary : dict
        Summary statistics
    run_id : str
        Run identifier
    save_path : str
        Output path for JSON file
    """
    import json
    
    report = {
        'run_id': run_id,
        'validation_summary': summary,
        'per_bone_validation': df_validation.to_dict('records'),
        'thresholds': {
            'variance_threshold_percent': BONE_LENGTH_VARIANCE_THRESHOLD,
            'drift_threshold_percent': MARKER_DRIFT_THRESHOLD,
            'swap_threshold_percent': SWAP_THRESHOLD
        }
    }
    
    with open(save_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    return save_path
