"""
Joint Statistics Computation for Quality Control (QC)

This module computes ROM and angular velocity statistics from quaternion data.
These metrics are for QUALITY CONTROL ONLY, not clinical/anatomical assessment.

ROM Computation Method:
    - Uses rotation vectors (axis-angle representation) from quaternions
    - Gimbal-lock free (no singularities at ±90°)
    - Continuous (no ±180° wrapping artifacts)
    - NOT anatomically interpretable (cannot separate flexion/abduction/rotation)

Quality Control Thresholds (Gaga Dance):
    - ROM: 50-180° (good), >200° (suspicious), >300° (bad)
    - Max Velocity: 200-800 °/s (good), >1000 °/s (suspicious), >1200 °/s (bad)

Reference: Longo et al. (2022) - Gaga dance movement ranges
"""

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any


def compute_joint_statistics(
    df_in: pd.DataFrame,
    df_final: pd.DataFrame,
    kinematics_map: Dict[str, Any],
    ref_pose: Dict[str, float]
) -> Dict[str, Dict[str, float]]:
    """
    Compute joint statistics (ROM and angular velocity) for quality control.
    
    ⚠️ IMPORTANT: ROM computed here is for QUALITY CONTROL purposes ONLY.
    It is NOT comparable to clinical ROM or anatomical ROM in literature.
    
    Parameters
    ----------
    df_in : pd.DataFrame
        Input dataframe with quaternion columns (joint__qx, joint__qy, joint__qz, joint__qw)
    df_final : pd.DataFrame
        Final dataframe with angular velocity columns (angle_X_vel, angle_Y_vel, angle_Z_vel)
    kinematics_map : dict
        Mapping of joint names to their kinematics info (parent, angle_name, etc.)
    ref_pose : dict
        Reference pose quaternions for zeroing calibration
        
    Returns
    -------
    joint_statistics : dict
        Dictionary with joint statistics per joint:
        {
            'joint_name': {
                'max_angular_velocity': float,  # deg/s
                'mean_angular_velocity': float,  # deg/s
                'p95_angular_velocity': float,  # deg/s
                'rom': float  # degrees (from quaternion-derived rotation vectors)
            }
        }
    """
    joint_statistics = {}
    joint_names_list = list(kinematics_map.keys())
    
    for joint in joint_names_list:
        # Use angle_name from kinematics_map
        angle_name = kinematics_map[joint]['angle_name']
        
        # Angular velocity columns (already computed correctly from quaternions)
        omega_x_col = f'{angle_name}_X_vel'
        omega_y_col = f'{angle_name}_Y_vel'
        omega_z_col = f'{angle_name}_Z_vel'
        
        # ========================================================================
        # ANGULAR VELOCITY (from quaternion derivatives - already correct)
        # ========================================================================
        if all(col in df_final.columns for col in [omega_x_col, omega_y_col, omega_z_col]):
            omega_x = df_final[omega_x_col].values
            omega_y = df_final[omega_y_col].values
            omega_z = df_final[omega_z_col].values
            
            omega_mag = np.sqrt(omega_x**2 + omega_y**2 + omega_z**2)
            omega_mag_clean = omega_mag[~np.isnan(omega_mag)]
            
            if len(omega_mag_clean) > 0:
                max_angular_velocity = float(np.max(omega_mag_clean))
                mean_angular_velocity = float(np.mean(omega_mag_clean))
                p95_angular_velocity = float(np.percentile(omega_mag_clean, 95))
            else:
                max_angular_velocity = 0.0
                mean_angular_velocity = 0.0
                p95_angular_velocity = 0.0
        else:
            max_angular_velocity = 0.0
            mean_angular_velocity = 0.0
            p95_angular_velocity = 0.0
        
        # ========================================================================
        # ROM (from QUATERNIONS - gimbal-lock free, no wrapping artifacts)
        # ========================================================================
        rom = _compute_rom_from_quaternions(joint, df_in, kinematics_map, ref_pose)
        
        # Store joint statistics
        joint_statistics[joint] = {
            'max_angular_velocity': round(max_angular_velocity, 2),  # deg/s
            'mean_angular_velocity': round(mean_angular_velocity, 2),  # deg/s
            'p95_angular_velocity': round(p95_angular_velocity, 2),  # deg/s
            'rom': round(rom, 2)  # degrees (from quaternion-derived angles)
        }
    
    return joint_statistics


def _compute_rom_from_quaternions(
    joint: str,
    df_in: pd.DataFrame,
    kinematics_map: Dict[str, Any],
    ref_pose: Dict[str, float]
) -> float:
    """
    Compute ROM directly from quaternions using rotation vectors.
    
    This method:
    - Uses rotation vectors (axis-angle) which don't have ±180° wrapping
    - Replicates the relative rotation logic with zeroing calibration
    - Is gimbal-lock free and continuous
    
    Parameters
    ----------
    joint : str
        Joint name
    df_in : pd.DataFrame
        Input dataframe with quaternion columns
    kinematics_map : dict
        Mapping of joint names to kinematics info
    ref_pose : dict
        Reference pose quaternions
        
    Returns
    -------
    rom : float
        Range of motion in degrees (QC metric, NOT anatomical ROM)
    """
    # Get quaternion columns for this joint
    quat_cols = [f'{joint}__qx', f'{joint}__qy', f'{joint}__qz', f'{joint}__qw']
    
    if not all(col in df_in.columns for col in quat_cols):
        return 0.0
    
    try:
        # Get child quaternions
        q_c = df_in[quat_cols].values
        
        # Get child reference quaternion
        q_c_ref = np.array([
            ref_pose[f'{joint}__qx'], ref_pose[f'{joint}__qy'],
            ref_pose[f'{joint}__qz'], ref_pose[f'{joint}__qw']
        ])
        
        # Get parent info from kinematics_map
        parent_name = kinematics_map[joint].get('parent')
        
        if parent_name is not None:
            # Get parent quaternions
            p_quat_cols = [f'{parent_name}__qx', f'{parent_name}__qy', 
                           f'{parent_name}__qz', f'{parent_name}__qw']
            
            if all(col in df_in.columns for col in p_quat_cols):
                q_p = df_in[p_quat_cols].values
                
                # Get parent reference quaternion
                q_p_ref = np.array([
                    ref_pose[f'{parent_name}__qx'], ref_pose[f'{parent_name}__qy'],
                    ref_pose[f'{parent_name}__qz'], ref_pose[f'{parent_name}__qw']
                ])
                
                # Current relative rotation: inv(Parent) * Child
                rot_c = R.from_quat(q_c)
                rot_p = R.from_quat(q_p)
                rot_rel = rot_p.inv() * rot_c
                
                # Reference relative rotation
                r_c_ref = R.from_quat(q_c_ref)
                r_p_ref = R.from_quat(q_p_ref)
                rot_rel_ref = r_p_ref.inv() * r_c_ref
            else:
                # Parent columns missing, use global rotation
                rot_rel = R.from_quat(q_c)
                rot_rel_ref = R.from_quat(q_c_ref)
        else:
            # Root joint - use global rotation
            rot_rel = R.from_quat(q_c)
            rot_rel_ref = R.from_quat(q_c_ref)
        
        # Apply zeroing calibration: inv(Reference) * Current
        rot_final = rot_rel_ref.inv() * rot_rel
        
        # Convert to rotation vectors (axis-angle representation)
        # This is gimbal-lock free and doesn't have ±180° wrapping
        rotvec = rot_final.as_rotvec()  # Shape: (T, 3) in radians
        
        # Unwrap each axis to handle any discontinuities
        # (rotation vectors can flip axis direction)
        rotvec_x = np.unwrap(rotvec[:, 0]) 
        rotvec_y = np.unwrap(rotvec[:, 1])
        rotvec_z = np.unwrap(rotvec[:, 2])
        
        # Convert unwrapped values to degrees
        rotvec_x_deg = np.degrees(rotvec_x)
        rotvec_y_deg = np.degrees(rotvec_y)
        rotvec_z_deg = np.degrees(rotvec_z)
        
        # Remove NaN values
        rotvec_x_clean = rotvec_x_deg[~np.isnan(rotvec_x_deg)]
        rotvec_y_clean = rotvec_y_deg[~np.isnan(rotvec_y_deg)]
        rotvec_z_clean = rotvec_z_deg[~np.isnan(rotvec_z_deg)]
        
        # ROM = max - min per axis (QC metric from rotation vectors)
        # ⚠️ This ROM is for quality control, NOT anatomical/clinical ROM
        if len(rotvec_x_clean) > 0 and len(rotvec_y_clean) > 0 and len(rotvec_z_clean) > 0:
            rom_x = float(np.max(rotvec_x_clean) - np.min(rotvec_x_clean))
            rom_y = float(np.max(rotvec_y_clean) - np.min(rotvec_y_clean))
            rom_z = float(np.max(rotvec_z_clean) - np.min(rotvec_z_clean))
            
            # Total ROM = maximum ROM across all axes
            rom = float(np.max([rom_x, rom_y, rom_z]))
        else:
            rom = 0.0
            
    except Exception as e:
        # Fallback if quaternion computation fails
        print(f"Warning: ROM computation failed for joint '{joint}': {e}")
        rom = 0.0
    
    return rom


def print_joint_statistics_summary(joint_statistics: Dict[str, Dict[str, float]]) -> None:
    """
    Print a formatted summary of joint statistics with quality flags.
    
    Parameters
    ----------
    joint_statistics : dict
        Dictionary of joint statistics from compute_joint_statistics()
    """
    print("\n" + "="*80)
    print("JOINT STATISTICS FOR QUALITY CONTROL (QC ONLY)")
    print("="*80)
    print("⚠️  IMPORTANT: ROM is a QC metric, NOT clinical/anatomical ROM")
    print("Purpose: Detect tracking errors, marker jumps, and data quality issues")
    print("Method: ROM from rotation vectors (gimbal-lock free, QC-optimized)")
    print("Reference: Longo et al. (2022) - Gaga dance ranges for QC thresholds")
    print("Documentation: docs/ROM_DOCUMENTATION.md for complete ROM documentation")
    print("="*80)
    print()
    
    print(f"✅ Computed statistics for {len(joint_statistics)} joints")
    print()
    
    # Interpretation guide
    print("="*80)
    print("HOW TO READ THIS TABLE (QUALITY CONTROL METRICS):")
    print("="*80)
    print("⚠️  ROM = Movement magnitude (QC), NOT anatomical ROM (clinical)")
    print()
    print("• ROM (°): Total joint movement magnitude")
    print("  - ⚠️ NOT flexion/abduction/rotation (use Euler angles for that)")
    print("  - ✅ VALID for: Tracking quality, outlier detection")
    print("  - Good: 50-180° for most joints")
    print("  - Suspicious: >200° (check for tracking errors)")
    print("  - Bad: >300° or 0° (data quality issue)")
    print()
    print("• Max Vel (°/s): Peak rotational speed")
    print("  - Good: 200-800 °/s for dance")
    print("  - Suspicious: >1000 °/s (possible marker jump)")
    print("  - Bad: >1200 °/s or 0 °/s (tracking failure)")
    print()
    print("• Mean Vel (°/s): Average rotational speed")
    print("  - Good: 30-200 °/s depending on joint")
    print("  - Use to check overall movement intensity")
    print("="*80)
    print()
    
    # Show sample of joints with highest ROM
    print("Sample Joint Statistics (Top 5 by ROM):")
    print("-" * 80)
    print(f"{'Joint':<30} | {'ROM (°)':<10} | {'Max Vel (°/s)':<15} | {'Mean Vel (°/s)':<15}")
    print("-" * 80)
    
    # Sort by ROM
    sorted_joints = sorted(joint_statistics.items(), key=lambda x: x[1]['rom'], reverse=True)
    
    for joint, stats in sorted_joints[:5]:
        print(f"{joint:<30} | {stats['rom']:<10.1f} | {stats['max_angular_velocity']:<15.1f} | {stats['mean_angular_velocity']:<15.1f}")
    
    print()
    
    # Automatic quality flags
    print("="*80)
    print("AUTOMATIC QUALITY FLAGS:")
    print("="*80)
    
    # Count suspicious values
    suspicious_rom = [j for j, s in joint_statistics.items() if s['rom'] > 200 and s['rom'] < 300]
    bad_rom = [j for j, s in joint_statistics.items() if s['rom'] >= 300 or s['rom'] == 0]
    suspicious_vel = [j for j, s in joint_statistics.items() if s['max_angular_velocity'] > 1000 and s['max_angular_velocity'] < 1200]
    bad_vel = [j for j, s in joint_statistics.items() if s['max_angular_velocity'] >= 1200 or (s['max_angular_velocity'] == 0 and s['rom'] > 0)]
    
    if not suspicious_rom and not bad_rom and not suspicious_vel and not bad_vel:
        print("✅ ALL CLEAR: No quality issues detected")
        print("   All joints within expected Gaga dance ranges")
    else:
        if suspicious_rom:
            print(f"⚠️  REVIEW: {len(suspicious_rom)} joint(s) with high ROM (200-300°):")
            for j in suspicious_rom:
                print(f"   - {j}: {joint_statistics[j]['rom']:.1f}° (check for tracking issues)")
        
        if bad_rom:
            print(f"❌ REJECT: {len(bad_rom)} joint(s) with impossible ROM (>300° or 0°):")
            for j in bad_rom:
                print(f"   - {j}: {joint_statistics[j]['rom']:.1f}° (tracking failure)")
        
        if suspicious_vel:
            print(f"⚠️  REVIEW: {len(suspicious_vel)} joint(s) with high velocity (1000-1200 °/s):")
            for j in suspicious_vel:
                print(f"   - {j}: {joint_statistics[j]['max_angular_velocity']:.1f} °/s (check for marker jump)")
        
        if bad_vel:
            print(f"❌ REJECT: {len(bad_vel)} joint(s) with impossible velocity (>1200 °/s):")
            for j in bad_vel:
                print(f"   - {j}: {joint_statistics[j]['max_angular_velocity']:.1f} °/s (tracking failure)")
    
    print("="*80)
    print()
    
    # Next steps
    print("="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Check the table above for any ⚠️ REVIEW or ❌ REJECT flags")
    print("2. If flags exist, inspect those joints in Section 5 visualization (nb07)")
    print("3. Joint statistics exported to kinematics_summary.json")
    print("4. Section 6 (Master Audit) will apply Gaga-aware QC thresholds")
    print("5. Final decision (ACCEPT/REVIEW/REJECT) in Section 8")
    print("="*80)
    print()
    print("✅ ROM computed from quaternion-derived angles (gimbal-lock free)")
    print("Joint statistics will be included in kinematics_summary.json")
    print("These metrics enable Section 6 (Gaga-Aware Biomechanics) QC")
    print("="*80)
