import numpy as np
import pandas as pd


def compute_bone_length_cv(df, bones):
    """
    Compute coefficient of variation for bone lengths.
    
    Args:
        df: DataFrame with marker positions (columns: marker_x, marker_y, marker_z)
        bones: List of tuples [(parent_marker, child_marker), ...]
    
    Returns:
        DataFrame with bone length statistics and status classification
    """
    results = []
    
    for parent, child in bones:
        parent_cols = [f"{parent}_x", f"{parent}_y", f"{parent}_z"]
        child_cols = [f"{child}_x", f"{child}_y", f"{child}_z"]
        
        # Check if all required columns exist
        if not all(col in df.columns for col in parent_cols + child_cols):
            continue
            
        # Extract positions
        parent_pos = df[parent_cols].values
        child_pos = df[child_cols].values
        
        # Remove rows with NaN values
        valid_mask = ~(np.isnan(parent_pos).any(axis=1) | np.isnan(child_pos).any(axis=1))
        
        if valid_mask.sum() < 2:  # Need at least 2 valid points
            continue
            
        parent_pos_valid = parent_pos[valid_mask]
        child_pos_valid = child_pos[valid_mask]
        
        # Calculate distances: Dist = sqrt(Δx² + Δy² + Δz²)
        delta = child_pos_valid - parent_pos_valid
        distances = np.sqrt(np.sum(delta**2, axis=1))
        
        # Calculate statistics
        mean_length = np.mean(distances)
        std_length = np.std(distances)
        
        if mean_length == 0:
            cv_percent = float('inf')
        else:
            cv_percent = (std_length / mean_length) * 100
        
        # Classify status based on CV%
        if cv_percent <= 2.0:
            status = "GOLD"
        elif cv_percent <= 5.0:
            status = "WARN"
        else:
            status = "FAIL"
        
        results.append({
            'bone': f"{parent}->{child}",
            'parent_marker': parent,
            'child_marker': child,
            'mean_length_m': mean_length,
            'std_length_m': std_length,
            'cv_percent': cv_percent,
            'status': status,
            'n_valid_frames': len(distances)
        })
    
    return pd.DataFrame(results)


def check_angular_velocity(df, fs):
    """
    Check angular velocity for physiological plausibility.
    
    Args:
        df: DataFrame with angle data (columns containing angle values)
        fs: Sampling frequency in Hz
    
    Returns:
        DataFrame with angular velocity statistics and warnings
    """
    results = []
    dt = 1.0 / fs
    
    # Find angle columns (assuming they contain 'angle' in the name)
    angle_cols = [col for col in df.columns if 'angle' in col.lower()]
    
    for col in angle_cols:
        angle_data = df[col].values
        valid_mask = ~np.isnan(angle_data)
        
        if valid_mask.sum() < 2:
            continue
            
        angle_valid = angle_data[valid_mask]
        
        # Calculate angular velocity: Vel = gradient(angle, 1/fs)
        angular_velocity = np.gradient(angle_valid, dt)
        
        max_abs_velocity = np.max(np.abs(angular_velocity))
        mean_abs_velocity = np.mean(np.abs(angular_velocity))
        
        # Check if velocity exceeds physiological threshold
        if max_abs_velocity > 2000:
            warning = "FAIL"
        elif max_abs_velocity > 1500:
            warning = "WARN"
        else:
            warning = "PASS"
        
        results.append({
            'angle_column': col,
            'max_angular_velocity_deg_s': max_abs_velocity,
            'mean_angular_velocity_deg_s': mean_abs_velocity,
            'status': warning,
            'n_valid_frames': len(angle_valid)
        })
    
    return pd.DataFrame(results)


def validate_bone_length_change(df_original, df_modified, bones, threshold_percent=10.0):
    """
    Test that a specified percentage change in bone length triggers FAIL status.
    
    Args:
        df_original: Original DataFrame with marker positions
        df_modified: Modified DataFrame with changed bone lengths
        bones: List of bone tuples to check
        threshold_percent: Percentage change that should trigger FAIL
    
    Returns:
        Dictionary with validation results
    """
    original_results = compute_bone_length_cv(df_original, bones)
    modified_results = compute_bone_length_cv(df_modified, bones)
    
    validation_results = {
        'test_passed': True,
        'details': []
    }
    
    for _, original_row in original_results.iterrows():
        bone_name = original_row['bone']
        original_length = original_row['mean_length_m']
        
        # Find corresponding modified bone
        modified_row = modified_results[modified_results['bone'] == bone_name]
        
        if len(modified_row) == 0:
            continue
            
        modified_row = modified_row.iloc[0]
        modified_length = modified_row['mean_length_m']
        
        # Calculate percentage change
        if original_length > 0:
            percent_change = abs((modified_length - original_length) / original_length) * 100
        else:
            percent_change = 0
        
        # Check if change exceeds threshold and status is FAIL
        exceeds_threshold = percent_change >= threshold_percent
        status_is_fail = modified_row['status'] == 'FAIL'
        
        test_result = exceeds_threshold and status_is_fail
        
        validation_results['details'].append({
            'bone': bone_name,
            'original_length_m': original_length,
            'modified_length_m': modified_length,
            'percent_change': percent_change,
            'exceeds_threshold': exceeds_threshold,
            'status_is_fail': status_is_fail,
            'test_passed': test_result
        })
        
        if not test_result:
            validation_results['test_passed'] = False
    
    return validation_results


def check_hicks_residuals(df, peak_force):
    """
    Check Hicks residual forces and moments for dynamic consistency.
    
    Args:
        df: DataFrame with force plate and residual data
        peak_force: Peak force value for threshold calculation
    
    Returns:
        DataFrame with Hicks residual analysis results
        
    Force Threshold: ≤ 5% of peak_force
    Moment Threshold: ≤ 1% of (peak_force × 1.0m)
    Returns SKIPPED if Force Plate data is missing
    """
    # Check for force plate data columns
    force_plate_cols = [col for col in df.columns if 'force_plate' in col.lower() or 'fp' in col.lower()]
    residual_force_cols = [col for col in df.columns if 'residual' in col.lower() and 'force' in col.lower()]
    residual_moment_cols = [col for col in df.columns if 'residual' in col.lower() and 'moment' in col.lower()]
    
    # Calculate thresholds
    if peak_force is None or peak_force <= 0:
        force_threshold = 0.0
        moment_threshold = 0.0
    else:
        force_threshold = 0.05 * peak_force  # 5% of peak force
        moment_threshold = 0.01 * peak_force * 1.0  # 1% of (peak_force × 1.0m)
    
    # If no force plate data found, return SKIPPED status
    if len(force_plate_cols) == 0:
        return pd.DataFrame([{
            'test': 'hicks_residuals',
            'status': 'SKIPPED',
            'reason': 'Force plate data missing',
            'peak_force_N': peak_force,
            'force_threshold_N': force_threshold,
            'moment_threshold_Nm': moment_threshold,
            'max_residual_force_N': None,
            'max_residual_moment_Nm': None
        }])
    
    results = []
    
    # Analyze residual forces
    for col in residual_force_cols:
        if col in df.columns:
            residual_data = df[col].values
            valid_mask = ~np.isnan(residual_data)
            
            if valid_mask.sum() > 0:
                max_residual_force = np.max(np.abs(residual_data[valid_mask]))
                mean_residual_force = np.mean(np.abs(residual_data[valid_mask]))
                
                # Determine status based on force threshold
                if max_residual_force <= force_threshold:
                    force_status = "PASS"
                elif max_residual_force <= 2 * force_threshold:
                    force_status = "WARN"
                else:
                    force_status = "FAIL"
                
                results.append({
                    'test': f'hicks_residual_force_{col}',
                    'status': force_status,
                    'column': col,
                    'peak_force_N': peak_force,
                    'force_threshold_N': force_threshold,
                    'moment_threshold_Nm': moment_threshold,
                    'max_residual_force_N': max_residual_force,
                    'mean_residual_force_N': mean_residual_force,
                    'max_residual_moment_Nm': None,
                    'mean_residual_moment_Nm': None,
                    'threshold_exceeded': max_residual_force > force_threshold
                })
    
    # Analyze residual moments
    for col in residual_moment_cols:
        if col in df.columns:
            residual_data = df[col].values
            valid_mask = ~np.isnan(residual_data)
            
            if valid_mask.sum() > 0:
                max_residual_moment = np.max(np.abs(residual_data[valid_mask]))
                mean_residual_moment = np.mean(np.abs(residual_data[valid_mask]))
                
                # Determine status based on moment threshold
                if max_residual_moment <= moment_threshold:
                    moment_status = "PASS"
                elif max_residual_moment <= 2 * moment_threshold:
                    moment_status = "WARN"
                else:
                    moment_status = "FAIL"
                
                results.append({
                    'test': f'hicks_residual_moment_{col}',
                    'status': moment_status,
                    'column': col,
                    'peak_force_N': peak_force,
                    'force_threshold_N': force_threshold,
                    'moment_threshold_Nm': moment_threshold,
                    'max_residual_force_N': None,
                    'mean_residual_force_N': None,
                    'max_residual_moment_Nm': max_residual_moment,
                    'mean_residual_moment_Nm': mean_residual_moment,
                    'threshold_exceeded': max_residual_moment > moment_threshold
                })
    
    # If no residual data found but force plate exists
    if len(results) == 0:
        return pd.DataFrame([{
            'test': 'hicks_residuals',
            'status': 'SKIPPED',
            'reason': 'Residual force/moment data missing',
            'peak_force_N': peak_force,
            'force_threshold_N': force_threshold,
            'moment_threshold_Nm': moment_threshold,
            'max_residual_force_N': None,
            'max_residual_moment_Nm': None
        }])
    
    return pd.DataFrame(results)


def generate_qc_validation_report(df, bones, fs, peak_force=None):
    """
    Generate comprehensive QC validation report.
    
    Args:
        df: DataFrame with marker positions and angles
        bones: List of bone tuples for bone length analysis
        fs: Sampling frequency for angular velocity analysis
        peak_force: Peak force for Hicks residual analysis
    
    Returns:
        Dictionary containing complete QC report
    """
    bone_length_results = compute_bone_length_cv(df, bones)
    angular_velocity_results = check_angular_velocity(df, fs)
    hicks_results = check_hicks_residuals(df, peak_force)
    
    # Summary statistics
    n_bones = len(bone_length_results)
    n_bones_gold = (bone_length_results['status'] == 'GOLD').sum()
    n_bones_warn = (bone_length_results['status'] == 'WARN').sum()
    n_bones_fail = (bone_length_results['status'] == 'FAIL').sum()
    
    n_angles = len(angular_velocity_results)
    n_angles_pass = (angular_velocity_results['status'] == 'PASS').sum()
    n_angles_warn = (angular_velocity_results['status'] == 'WARN').sum()
    n_angles_fail = (angular_velocity_results['status'] == 'FAIL').sum()
    
    # Hicks summary
    n_hicks = len(hicks_results)
    n_hicks_pass = (hicks_results['status'] == 'PASS').sum()
    n_hicks_warn = (hicks_results['status'] == 'WARN').sum()
    n_hicks_fail = (hicks_results['status'] == 'FAIL').sum()
    n_hicks_skipped = (hicks_results['status'] == 'SKIPPED').sum()
    
    report = {
        'bone_length_analysis': {
            'results': bone_length_results.to_dict('records'),
            'summary': {
                'total_bones': n_bones,
                'gold_status': n_bones_gold,
                'warn_status': n_bones_warn,
                'fail_status': n_bones_fail
            }
        },
        'angular_velocity_analysis': {
            'results': angular_velocity_results.to_dict('records'),
            'summary': {
                'total_angles': n_angles,
                'pass_status': n_angles_pass,
                'warn_status': n_angles_warn,
                'fail_status': n_angles_fail
            }
        },
        'hicks_residual_analysis': {
            'results': hicks_results.to_dict('records'),
            'summary': {
                'total_tests': n_hicks,
                'pass_status': n_hicks_pass,
                'warn_status': n_hicks_warn,
                'fail_status': n_hicks_fail,
                'skipped_status': n_hicks_skipped
            }
        },
        'overall_status': 'FAIL' if (n_bones_fail > 0 or n_angles_fail > 0 or n_hicks_fail > 0) else 
                         'WARN' if (n_bones_warn > 0 or n_angles_warn > 0 or n_hicks_warn > 0) else 
                         'GOLD' if n_hicks_skipped == n_hicks else 'GOLD'
    }
    
    return report
