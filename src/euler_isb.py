"""
ISB-Compliant Euler Angle Extraction
=====================================
Per Wu et al. (2002, 2005) and the International Society of Biomechanics (ISB) standards.

CRITICAL: Joint-specific sequences prevent Gimbal Lock and ensure anatomical validity.
Generic XYZ sequences are NOT appropriate for biomechanics.

References:
- Wu et al. (2002): Shoulder and elbow
- Wu et al. (2005): Hip and knee  
- ISB recommendations for ankle and spine

RESOLVED (Phase 4 refactor, 2026-02-21):
    NB06 now calls get_euler_sequence() from this module for all joints.
    The legacy ZYX (axial) / XYZ (limbs) hardcode has been retired.
    Both the NB06 notebook path and the src/pipeline.py path are now
    ISB-compliant, using the sequences defined in ISB_EULER_SEQUENCES.

Author: Gaga Motion Analysis Pipeline
Date: 2026-01-22
"""

import numpy as np
from scipy.spatial.transform import Rotation as R

# ============================================================
# ISB-RECOMMENDED EULER SEQUENCES PER JOINT
# ============================================================

ISB_EULER_SEQUENCES = {
    # SPINE & TORSO (Flexion/Extension, Lateral Bending, Axial Rotation)
    # Sequence: Z-X-Y per ISB spine recommendations
    'Hips': 'ZXY',           # Root/Pelvis orientation
    'Spine': 'ZXY',          # Lower spine
    'Spine1': 'ZXY',         # Mid-spine/thorax
    'Neck': 'ZXY',           # Cervical spine
    'Head': 'ZXY',           # Head orientation
    
    # SHOULDER (Per Wu et al. 2002, 2005)
    # Y-X-Y sequence prevents gimbal lock during arm elevation
    # Y1: Plane of elevation, X: Elevation angle, Y2: Axial rotation
    'LeftShoulder': 'YXY',
    'RightShoulder': 'YXY',
    
    # UPPER LIMB (Per Wu et al. 2002)
    # Elbow: Z-X-Y (Flexion/Extension, Carrying Angle, Pronation/Supination)
    'LeftArm': 'ZXY',        # Humerus
    'LeftForeArm': 'ZXY',    # Radius/Ulna (includes pronation/supination)
    'LeftHand': 'ZXY',       # Wrist and hand
    
    'RightArm': 'ZXY',
    'RightForeArm': 'ZXY',
    'RightHand': 'ZXY',
    
    # HAND SEGMENTS (Finger joints)
    # Z-X-Y: Flexion/Extension, Ab/Adduction, Rotation
    'LeftHandThumb1': 'ZXY',
    'LeftHandThumb2': 'ZXY',
    'LeftHandThumb3': 'ZXY',
    'LeftHandIndex1': 'ZXY',
    'LeftHandIndex2': 'ZXY',
    'LeftHandIndex3': 'ZXY',
    'LeftHandMiddle1': 'ZXY',
    'LeftHandMiddle2': 'ZXY',
    'LeftHandMiddle3': 'ZXY',
    'LeftHandRing1': 'ZXY',
    'LeftHandRing2': 'ZXY',
    'LeftHandRing3': 'ZXY',
    'LeftHandPinky1': 'ZXY',
    'LeftHandPinky2': 'ZXY',
    'LeftHandPinky3': 'ZXY',
    
    'RightHandThumb1': 'ZXY',
    'RightHandThumb2': 'ZXY',
    'RightHandThumb3': 'ZXY',
    'RightHandIndex1': 'ZXY',
    'RightHandIndex2': 'ZXY',
    'RightHandIndex3': 'ZXY',
    'RightHandMiddle1': 'ZXY',
    'RightHandMiddle2': 'ZXY',
    'RightHandMiddle3': 'ZXY',
    'RightHandRing1': 'ZXY',
    'RightHandRing2': 'ZXY',
    'RightHandRing3': 'ZXY',
    'RightHandPinky1': 'ZXY',
    'RightHandPinky2': 'ZXY',
    'RightHandPinky3': 'ZXY',
    
    # LOWER LIMB (Per Wu et al. 2005)
    # Hip: Z-X-Y (Flexion/Extension, Ab/Adduction, Internal/External Rotation)
    # Knee: Z-X-Y (Flexion/Extension, Ab/Adduction, Internal/External Rotation)
    # Ankle: Z-X-Y (Plantar/Dorsiflexion, Inversion/Eversion, Ab/Adduction)
    'LeftUpLeg': 'ZXY',      # Femur (hip joint)
    'LeftLeg': 'ZXY',        # Tibia (knee joint)
    'LeftFoot': 'ZXY',       # Foot (ankle joint)
    'LeftToeBase': 'ZXY',    # Toe joints
    
    'RightUpLeg': 'ZXY',
    'RightLeg': 'ZXY',
    'RightFoot': 'ZXY',
    'RightToeBase': 'ZXY',
}

# ============================================================
# ANATOMICAL RANGE OF MOTION LIMITS (Degrees)
# ============================================================
# Per Ryu et al. (2022) and standard anatomical references
# Format: (min, max) for primary axis (first rotation in sequence)

ANATOMICAL_ROM_LIMITS = {
    # SPINE (Flexion/Extension as primary)
    'Hips': (-30, 30),           # Pelvis tilt
    'Spine': (-45, 45),          # Lumbar flexion/extension
    'Spine1': (-45, 45),         # Thoracic flexion/extension
    'Neck': (-60, 60),           # Cervical flexion/extension
    'Head': (-70, 70),           # Head flexion/extension
    
    # SHOULDER (Elevation angle)
    'LeftShoulder': (0, 180),    # 0-180° arm elevation
    'RightShoulder': (0, 180),
    
    # ELBOW (Flexion/Extension)
    'LeftArm': (-180, 180),      # Full rotation possible
    'LeftForeArm': (0, 150),     # Elbow flexion: 0-150°
    'LeftHand': (-90, 90),       # Wrist flexion/extension
    
    'RightArm': (-180, 180),
    'RightForeArm': (0, 150),
    'RightHand': (-90, 90),
    
    # FINGERS (MCP, PIP, DIP flexion)
    'LeftHandThumb1': (0, 90),   # Thumb MCP
    'LeftHandThumb2': (0, 90),   # Thumb IP
    'LeftHandThumb3': (0, 90),
    'LeftHandIndex1': (0, 90),   # Index MCP
    'LeftHandIndex2': (0, 110),  # Index PIP
    'LeftHandIndex3': (0, 90),   # Index DIP
    # ... (similar for other fingers)
    
    'RightHandThumb1': (0, 90),
    'RightHandThumb2': (0, 90),
    'RightHandThumb3': (0, 90),
    'RightHandIndex1': (0, 90),
    'RightHandIndex2': (0, 110),
    'RightHandIndex3': (0, 90),
    
    # HIP (Flexion/Extension)
    'LeftUpLeg': (-20, 125),     # Hip: 20° extension to 125° flexion
    'LeftLeg': (0, 140),         # Knee: 0-140° flexion
    'LeftFoot': (-30, 50),       # Ankle: 30° plantarflexion to 50° dorsiflexion
    'LeftToeBase': (-45, 90),    # Toe flexion/extension
    
    'RightUpLeg': (-20, 125),
    'RightLeg': (0, 140),
    'RightFoot': (-30, 50),
    'RightToeBase': (-45, 90),
}

# Gaga-specific adjustments (higher intensity movements)
GAGA_ROM_TOLERANCE = 1.15  # Allow 15% beyond normal ROM for expressive dance


def get_euler_sequence(joint_name):
    """
    Get ISB-compliant Euler sequence for a joint.
    
    Parameters:
    -----------
    joint_name : str
        Standardized joint name
        
    Returns:
    --------
    str : Euler sequence (e.g., 'ZXY', 'YXY')
    """
    return ISB_EULER_SEQUENCES.get(joint_name, 'ZXY')  # Default to ZXY if not specified


def quaternion_to_isb_euler(quat, joint_name):
    """
    Convert quaternion to ISB-compliant Euler angles for a specific joint.
    
    Parameters:
    -----------
    quat : array-like, shape (4,) or (N, 4)
        Quaternion(s) in [x, y, z, w] format
    joint_name : str
        Joint name to determine appropriate sequence
        
    Returns:
    --------
    euler : np.ndarray
        Euler angles in degrees, shape (3,) or (N, 3)
        Order depends on joint-specific ISB sequence
    """
    sequence = get_euler_sequence(joint_name)
    
    # Handle single quaternion or array
    quat = np.asarray(quat)
    single = quat.ndim == 1
    
    if single:
        quat = quat.reshape(1, -1)
    
    # Convert using scipy Rotation
    rot = R.from_quat(quat)
    euler = rot.as_euler(sequence, degrees=True)
    
    return euler[0] if single else euler


def check_anatomical_validity(euler_angles, joint_name, allow_gaga_tolerance=True):
    """
    Check if Euler angles are within anatomically valid ranges.
    
    Parameters:
    -----------
    euler_angles : np.ndarray
        Euler angles in degrees, shape (3,) or (N, 3)
    joint_name : str
        Joint name
    allow_gaga_tolerance : bool
        If True, apply Gaga-specific tolerance for expressive movements
        
    Returns:
    --------
    dict : Validation results with keys:
        - is_valid : bool
        - primary_angle : float (first angle in sequence)
        - violations : list of str (descriptions of violations)
        - rom_limits : tuple (min, max) used for validation
    """
    euler_angles = np.asarray(euler_angles)
    single = euler_angles.ndim == 1
    
    if single:
        euler_angles = euler_angles.reshape(1, -1)
    
    # Get ROM limits for this joint
    rom_limits = ANATOMICAL_ROM_LIMITS.get(joint_name, (-180, 180))
    
    # Apply Gaga tolerance if requested
    if allow_gaga_tolerance:
        range_width = rom_limits[1] - rom_limits[0]
        extension = range_width * (GAGA_ROM_TOLERANCE - 1.0) / 2
        rom_limits = (rom_limits[0] - extension, rom_limits[1] + extension)
    
    # Check primary angle (first in sequence)
    primary_angles = euler_angles[:, 0]
    
    violations = []
    for i, angle in enumerate(primary_angles):
        if angle < rom_limits[0] or angle > rom_limits[1]:
            violations.append(f"Frame {i}: {angle:.1f}° outside range {rom_limits}")
    
    is_valid = len(violations) == 0
    
    result = {
        'is_valid': is_valid,
        'primary_angle_mean': float(np.mean(primary_angles)),
        'primary_angle_range': (float(np.min(primary_angles)), float(np.max(primary_angles))),
        'violations': violations[:10],  # Limit to first 10 violations
        'violation_count': len(violations),
        'rom_limits': rom_limits,
        'sequence': get_euler_sequence(joint_name)
    }
    
    return result


def convert_dataframe_to_isb_euler(df, joint_names, verbose=True):
    """
    Convert all quaternions in a DataFrame to ISB-compliant Euler angles.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with quaternion columns (__qx, __qy, __qz, __qw)
    joint_names : list
        List of joint names to process
    verbose : bool
        Print progress
        
    Returns:
    --------
    df_euler : pd.DataFrame
        New DataFrame with ISB Euler angles (__euler_0, __euler_1, __euler_2)
    validation_report : dict
        Per-joint validation results
    """
    import pandas as pd
    
    euler_data = {}
    validation_report = {}
    
    for joint in joint_names:
        quat_cols = [f'{joint}__qx', f'{joint}__qy', f'{joint}__qz', f'{joint}__qw']
        
        # Check if all quaternion columns exist
        if not all(col in df.columns for col in quat_cols):
            if verbose:
                print(f"⚠️  Skipping {joint}: Missing quaternion columns")
            continue
        
        # Extract quaternions
        quats = df[quat_cols].values
        
        # Convert to ISB Euler
        euler = quaternion_to_isb_euler(quats, joint)
        
        # Store with descriptive names
        sequence = get_euler_sequence(joint)
        euler_data[f'{joint}__euler_0_{sequence[0]}'] = euler[:, 0]
        euler_data[f'{joint}__euler_1_{sequence[1]}'] = euler[:, 1]
        euler_data[f'{joint}__euler_2_{sequence[2]}'] = euler[:, 2]
        
        # Validate
        validation = check_anatomical_validity(euler, joint)
        validation_report[joint] = validation
        
        if verbose and not validation['is_valid']:
            print(f"⚠️  {joint}: {validation['violation_count']} frames outside anatomical range")
    
    df_euler = pd.DataFrame(euler_data, index=df.index)
    
    return df_euler, validation_report


# =============================================================================
# GATE 4: ISB COMPLIANCE AUDIT FUNCTIONS
# =============================================================================

def get_euler_sequences_audit(joint_list: list) -> dict:
    """
    Get ISB Euler sequences used for each joint (Gate 4 audit).
    
    Parameters
    ----------
    joint_list : list
        List of joint names
        
    Returns
    -------
    dict with:
        - step_06_euler_sequences_used: Dict of joint -> sequence
        - step_06_isb_compliant: True if all joints use ISB sequences
    """
    sequences = {}
    for joint in joint_list:
        sequences[joint] = get_euler_sequence(joint)
    
    # Check if all joints use ISB-recommended sequences
    # (ISB_EULER_SEQUENCES contains the recommended ones)
    non_isb_joints = [j for j in joint_list if j not in ISB_EULER_SEQUENCES]
    
    return {
        "step_06_euler_sequences_used": sequences,
        "step_06_isb_compliant": len(non_isb_joints) == 0,
        "step_06_non_isb_joints": non_isb_joints if non_isb_joints else None
    }


def assess_quaternion_health(max_quat_norm_err: float) -> dict:
    """
    Determine Gate 4 status based on quaternion normalization error.
    
    Parameters
    ----------
    max_quat_norm_err : float
        Maximum quaternion normalization error across all frames/joints
        
    Returns
    -------
    dict with:
        - step_06_quat_norm_err: The error value
        - step_06_math_status: PASS/REVIEW/REJECT
        - step_06_math_decision_reason: Explanation string
        
    Thresholds
    ----------
    - err <= 0.01: PASS (quaternion math stable)
    - err 0.01-0.05: REVIEW (drift detected)
    - err > 0.05: REJECT (Gimbal Lock likely)
    """
    QUAT_WARN_THRESHOLD = 0.01
    QUAT_REJECT_THRESHOLD = 0.05
    
    if max_quat_norm_err > QUAT_REJECT_THRESHOLD:
        status = "REJECT"
        reason = f"REJECT: Quaternion Math Failure — norm_err = {max_quat_norm_err:.6f} > 0.05 (Gimbal Lock likely)"
    elif max_quat_norm_err > QUAT_WARN_THRESHOLD:
        status = "REVIEW"
        reason = f"REVIEW: Quaternion Drift — norm_err = {max_quat_norm_err:.6f} > 0.01"
    else:
        status = "PASS"
        reason = f"Quaternion health excellent: norm_err = {max_quat_norm_err:.6f}"
    
    return {
        "step_06_quat_norm_err": max_quat_norm_err,
        "step_06_math_status": status,
        "step_06_math_decision_reason": reason if status != "PASS" else None
    }
