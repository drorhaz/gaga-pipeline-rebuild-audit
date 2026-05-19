"""
Anatomical Calibration & V-Pose Correction Module

This module implements the anatomical zero reference establishment by:
1. Finding a stable calibration window (quiet stand)
2. Correcting V-Pose arm elevation using geometry-safe rotation
3. Exporting inverse quaternion offsets for kinematic alignment
"""

import numpy as np
import pandas as pd
import json
import logging
from typing import Dict, Tuple, Optional, List
from scipy.spatial.transform import Rotation
from pathlib import Path

logger = logging.getLogger(__name__)


def find_stable_window(df: pd.DataFrame, 
                      pelvis_joint: str = "Hips",
                      left_wrist_joint: str = "LeftHand", 
                      right_wrist_joint: str = "RightHand",
                      search_duration_sec: float = 5.0,
                      window_duration_sec: float = 1.0,
                      step_sec: float = 0.1,
                      fs: float = 120.0,
                      variance_threshold: float = 100.0,
                      motion_thr_low: float = 0.30) -> Tuple[pd.DataFrame, Dict]:
    """
    Find the most stable window in the first N seconds of recording.
    
    ENHANCED: Now includes quality metrics for confidence assessment.
    
    Args:
        df: DataFrame with position data
        pelvis_joint: Name of pelvis joint
        left_wrist_joint: Name of left wrist joint  
        right_wrist_joint: Name of right wrist joint
        search_duration_sec: Maximum duration to search (min of this and recording length)
        window_duration_sec: Duration of analysis window
        step_sec: Step size for sliding window
        fs: Sampling frequency
        variance_threshold: Max acceptable variance score (above = low confidence fallback)
        motion_thr_low: Angular-velocity threshold (rad/s) used to compute
            Reference_Quality_Index = 1.0 - (mean_motion / motion_thr_low).
            Should match config ``motion_thr_low`` (default 0.30 rad/s).
        
    Returns:
        Tuple of (reference DataFrame slice, metadata dict with quality metrics)
    """
    # Limit search to first min(search_duration_sec, duration) seconds
    actual_search_duration = min(search_duration_sec, len(df) / fs)
    search_samples = int(actual_search_duration * fs)
    window_samples = int(window_duration_sec * fs)
    step_samples = int(step_sec * fs)
    
    # Get position columns for target joints using actual naming convention
    position_cols = []
    for joint in [pelvis_joint, left_wrist_joint, right_wrist_joint]:
        # Try both naming conventions: __px and _pos_x
        joint_cols = []
        for axis in ['x', 'y', 'z']:
            # First try the double underscore convention
            col = f"{joint}__p{axis}"
            if col in df.columns:
                joint_cols.append(col)
            else:
                # Fallback to single underscore convention
                col_alt = f"{joint}_pos_{axis}"
                if col_alt in df.columns:
                    joint_cols.append(col_alt)
                else:
                    logger.warning(f"Position column for {joint} axis {axis} not found")
        
        position_cols.extend(joint_cols)
    
    if not position_cols:
        raise ValueError("No position columns found for stability analysis")
    
    # Slide window and compute variance score
    min_score = float('inf')
    best_start_idx = 0
    all_scores = []
    
    for start_idx in range(0, search_samples - window_samples + 1, step_samples):
        end_idx = start_idx + window_samples
        window_df = df.iloc[start_idx:end_idx]
        
        # Compute 3D variance score: sum of variances for all axes
        variance_score = 0.0
        for col in position_cols:
            variance_score += window_df[col].var()
        
        all_scores.append(variance_score)
        
        if variance_score < min_score:
            min_score = variance_score
            best_start_idx = start_idx
    
    # Extract reference window
    ref_df = df.iloc[best_start_idx:best_start_idx + window_samples].copy()
    
    # ============================================================
    # ENHANCED: Compute Quality Metrics for Reference Confidence
    # ============================================================
    
    # 1. Mean Motion: Average frame-to-frame displacement during reference window
    #    Lower = better (subject was stationary)
    mean_motion = 0.0
    motion_count = 0
    for col in position_cols:
        if col in ref_df.columns:
            diff = ref_df[col].diff().abs()
            mean_motion += diff.mean()
            motion_count += 1
    if motion_count > 0:
        mean_motion = float(mean_motion / motion_count)  # Average across all position columns
    
    # 2. Max Motion: Maximum single-frame displacement (detects sudden movements)
    max_motion = 0.0
    for col in position_cols:
        if col in ref_df.columns:
            diff = ref_df[col].diff().abs()
            max_motion = max(max_motion, float(diff.max()))
    
    # 3. Detection Method & Fallback Flag
    #    If variance_score > threshold, confidence is low but we keep the
    #    least-motion window (best_start_idx already points to it).
    ref_is_fallback = min_score > variance_threshold
    detection_method = "auto_stable_window" if not ref_is_fallback else "least_motion_window_fallback"
    
    if ref_is_fallback:
        logger.warning(
            f"Low confidence reference detection (variance={min_score:.2f} > "
            f"threshold={variance_threshold}). Keeping least-motion window at "
            f"idx={best_start_idx} instead of falling back to frame 0."
        )
    
    # 4. Reference Quality Index (physically interpretable)
    #    Formula: 1.0 - (actual_mean_velocity / MOTION_THR_LOW)
    #      1.0  = perfectly still (mean_motion == 0)
    #      0.0  = at threshold    (mean_motion == MOTION_THR_LOW)
    #      <0   = clamped to 0    (above threshold)
    if motion_thr_low > 0 and np.isfinite(mean_motion):
        ref_quality_score = float(np.clip(1.0 - (mean_motion / motion_thr_low), 0.0, 1.0))
    elif min_score <= 0:
        ref_quality_score = 1.0
    else:
        ref_quality_score = float(np.clip(1.0 - (min_score / (2 * variance_threshold)), 0.0, 1.0))
    
    # 5. Determine confidence level for user display
    if ref_quality_score >= 0.8:
        confidence_level = "HIGH"
    elif ref_quality_score >= 0.5:
        confidence_level = "MEDIUM"
    else:
        confidence_level = "LOW"
    
    metadata = {
        "start_time_sec": best_start_idx / fs,
        "end_time_sec": (best_start_idx + window_samples) / fs,
        "duration_sec": window_duration_sec,
        "variance_score": float(min_score),
        "searched_duration_sec": actual_search_duration,
        "joints_used": [pelvis_joint, left_wrist_joint, right_wrist_joint],
        "time_window": [best_start_idx / fs, (best_start_idx + window_samples) / fs],
        # NEW: Quality metrics for confidence assessment
        "mean_motion": mean_motion,
        "max_motion": max_motion,
        "ref_quality_score": ref_quality_score,
        "confidence_level": confidence_level,
        "ref_is_fallback": ref_is_fallback,
        "detection_method": detection_method,
        "variance_threshold": variance_threshold,
        "all_window_scores_min": float(min(all_scores)) if all_scores else min_score,
        "all_window_scores_max": float(max(all_scores)) if all_scores else min_score,
        "motion_thr_low": motion_thr_low,
    }
    
    logger.info(f"Found stable window: {metadata['start_time_sec']:.2f}-{metadata['end_time_sec']:.2f}s, "
                f"score: {min_score:.6f}, confidence: {confidence_level} ({ref_quality_score:.2f})")
    
    return ref_df, metadata


def detect_v_pose(ref_df: pd.DataFrame,
                  shoulder_joint: str = "LeftShoulder", 
                  elbow_joint: str = "LeftElbow",
                  elevation_threshold_deg: float = 5.0) -> Tuple[bool, float, np.ndarray]:
    """
    Detect V-Pose arm elevation and compute correction if needed.
    
    Args:
        ref_df: Reference DataFrame with position data
        shoulder_joint: Name of shoulder joint
        elbow_joint: Name of elbow joint  
        elevation_threshold_deg: Threshold for applying correction
        
    Returns:
        Tuple of (correction_applied, elevation_degrees, correction_rotation_xyzw)
    """
    # Get mean positions within the reference window using actual naming convention
    shoulder_pos = np.array([0.0, 0.0, 0.0])
    elbow_pos = np.array([0.0, 0.0, 0.0])
    
    # Try double underscore convention first
    for i, axis in enumerate(['x', 'y', 'z']):
        shoulder_col = f"{shoulder_joint}__p{axis}"
        elbow_col = f"{elbow_joint}__p{axis}"
        
        if shoulder_col in ref_df.columns:
            shoulder_pos[i] = ref_df[shoulder_col].mean()
        else:
            # Fallback to single underscore convention
            shoulder_col_alt = f"{shoulder_joint}_pos_{axis}"
            if shoulder_col_alt in ref_df.columns:
                shoulder_pos[i] = ref_df[shoulder_col_alt].mean()
            else:
                logger.warning(f"Shoulder position column for axis {axis} not found")
        
        if elbow_col in ref_df.columns:
            elbow_pos[i] = ref_df[elbow_col].mean()
        else:
            # Fallback to single underscore convention
            elbow_col_alt = f"{elbow_joint}_pos_{axis}"
            if elbow_col_alt in ref_df.columns:
                elbow_pos[i] = ref_df[elbow_col_alt].mean()
            else:
                logger.warning(f"Elbow position column for axis {axis} not found")
    
    # Calculate arm vector and elevation
    arm_vector = elbow_pos - shoulder_pos
    v_x, v_y, v_z = arm_vector
    
    # Elevation angle: degrees(atan2(v_y, sqrt(v_x^2 + v_z^2)))
    horizontal_magnitude = np.sqrt(v_x**2 + v_z**2)
    elevation_rad = np.arctan2(v_y, horizontal_magnitude)
    elevation_deg = np.degrees(elevation_rad)
    
    correction_applied = False
    correction_quat_xyzw = np.array([0.0, 0.0, 0.0, 1.0])  # Identity quaternion
    
    if abs(elevation_deg) > elevation_threshold_deg:
        # Degeneracy guard: check horizontal component
        if horizontal_magnitude < 1e-8:
            logger.warning("Insufficient horizontal component for V-Pose correction")
            return False, elevation_deg, correction_quat_xyzw
        
        # Define target vector (remove vertical component)
        v_target = np.array([v_x, 0.0, v_z])
        
        # Normalize both vectors
        v_normalized = arm_vector / np.linalg.norm(arm_vector)
        v_target_normalized = v_target / np.linalg.norm(v_target)
        
        # Find correction rotation using align_vectors
        R_corr, _ = Rotation.align_vectors([v_target_normalized], [v_normalized])
        correction_quat_xyzw = R_corr.as_quat()  # xyzw format
        correction_applied = True
        
        logger.info(f"V-Pose correction applied: elevation={elevation_deg:.2f}°, threshold={elevation_threshold_deg}°")
    else:
        logger.info(f"V-Pose correction not needed: elevation={elevation_deg:.2f}°, threshold={elevation_threshold_deg}°")
    
    return correction_applied, elevation_deg, correction_quat_xyzw


def compute_quaternion_offsets(ref_df: pd.DataFrame,
                              correction_quat_xyzw: np.ndarray,
                              shoulder_joints: List[str] = ["LeftShoulder", "RightShoulder"],
                              fs: float = 120.0) -> Tuple[Dict, Dict]:
    """
    Compute quaternion offsets for all joints with hemisphere alignment.
    
    Args:
        ref_df: Reference DataFrame with quaternion data
        correction_quat_xyzw: V-Pose correction quaternion in xyzw format (stored separately, NOT baked into offsets)
        shoulder_joints: List of shoulder joint names that get V-pose correction
        fs: Sampling frequency
        
    Returns:
        Tuple of (offsets_map_dict, metadata_dict)
    """
    # Get all quaternion columns using actual naming convention
    quat_cols = []
    for col in ref_df.columns:
        if '__q' in col and any(col.endswith(ax) for ax in ['x', 'y', 'z', 'w']):
            quat_cols.append(col)
    
    # Extract joint names from quaternion columns
    joint_names = list(set(col.split('__q')[0] for col in quat_cols))
    
    offsets_map = {}
    metadata = {
        "fs": fs,
        "window_duration_sec": len(ref_df) / fs,
        "quat_order": "xyzw",
        "hemisphere_alignment_applied": True,
        "v_pose_correction_applied": not np.allclose(correction_quat_xyzw, [0, 0, 0, 1]),
        "v_pose_correction_quat_xyzw": correction_quat_xyzw.tolist() if not np.allclose(correction_quat_xyzw, [0, 0, 0, 1]) else None,
        "shoulder_joints": shoulder_joints
    }
    
    for joint in joint_names:
        # Extract quaternion time series for this joint using actual naming convention
        quat_series = []
        for axis in ['x', 'y', 'z', 'w']:
            # Try double underscore convention first
            col = f"{joint}__q{axis}"
            if col in ref_df.columns:
                quat_series.append(ref_df[col].values)
            else:
                # Fallback to single underscore convention
                col_alt = f"{joint}_quat_{axis}"
                if col_alt in ref_df.columns:
                    quat_series.append(ref_df[col_alt].values)
                else:
                    logger.warning(f"Quaternion column {joint} axis {axis} not found")
                    break
        
        if len(quat_series) != 4:
            logger.warning(f"Incomplete quaternion data for joint {joint}")
            continue
            
        # Stack into (N, 4) array in xyzw order
        quats = np.stack(quat_series, axis=1)  # Shape: (N, 4)
        
        # Hemisphere alignment: ensure all quaternions are in same hemisphere
        # OPTIMIZED: Vectorized operation instead of loop
        q0 = quats[0]  # Reference quaternion
        dot_products = np.dot(quats, q0)
        flip_mask = dot_products < 0
        quats[flip_mask] = -quats[flip_mask]
        
        # Compute mean quaternion and normalize
        q_mean = quats.mean(axis=0)
        q_mean = q_mean / np.linalg.norm(q_mean)
        
        # Convert to Rotation object
        R_static_avg = Rotation.from_quat(q_mean)
        
        # IMPORTANT CHANGE: DO NOT bake V-pose correction into quaternion offsets
        # Store pure static reference offsets only
        R_refined = R_static_avg  # No R_corr applied here!
        
        # Store inverse quaternion as offset
        R_offset = R_refined.inv()
        offset_quat_xyzw = R_offset.as_quat()
        
        offsets_map[joint] = offset_quat_xyzw.tolist()
    
    return offsets_map, metadata


def compute_residual_rotation_degrees(R_offset: Rotation, R_raw: Rotation) -> float:
    """
    Compute residual rotation in degrees using the correct formula.
    
    Args:
        R_offset: Offset rotation (stored as inverse of refined rotation)
        R_raw: Raw rotation from data
        
    Returns:
        Residual rotation angle in degrees
    """
    # Apply offset: R_aligned = R_offset * R_raw (LEFT-multiply)
    R_aligned = R_offset * R_raw
    
    # Get quaternion scalar component (w) from aligned rotation
    q_aligned = R_aligned.as_quat()  # xyzw format
    qw = abs(q_aligned[3])  # w is the last component in xyzw
    
    # Ensure qw is clipped to valid range [0, 1]
    qw_clipped = np.clip(qw, 0.0, 1.0)
    
    # Compute angle: degrees(2 * arccos(qw))
    angle_rad = 2.0 * np.arccos(qw_clipped)
    angle_deg = np.degrees(angle_rad)
    
    return angle_deg


def validate_offsets_identity(df_ref: pd.DataFrame,
                           offsets_map: Dict[str, List[float]],
                           quat_cols_map: Optional[Dict[str, List[str]]] = None,
                           quat_order: str = "xyzw",
                           tol_deg: float = 5.0) -> pd.DataFrame:
    """
    Calibration Offset Validation: Verify R_offset ⊗ R_raw ≈ Identity on reference window.
    No V-pose involved - this is the only PASS/FAIL gate.
    """
    from scipy.spatial.transform import Rotation as R
    
    results = []
    
    for joint_name, offset_quat in offsets_map.items():
        # Auto-detect quaternion columns if not provided
        if quat_cols_map is None:
            quat_cols = []
            for axis in ['x', 'y', 'z', 'w']:
                col = f"{joint_name}__q{axis}"
                if col in df_ref.columns:
                    quat_cols.append(col)
                else:
                    col_alt = f"{joint_name}_quat_{axis}"
                    if col_alt in df_ref.columns:
                        quat_cols.append(col_alt)
        else:
            quat_cols = quat_cols_map.get(joint_name, [])
        
        if len(quat_cols) != 4:
            continue
            
        # Extract raw quaternions
        raw_quats = np.stack([df_ref[col].values for col in quat_cols], axis=1)
        
        # Hemisphere alignment
        q0 = raw_quats[0]
        dot_products = np.dot(raw_quats, q0)
        flip_mask = dot_products < 0
        raw_quats[flip_mask] = -raw_quats[flip_mask]
        
        # Apply offset: q_corr = q_offset ⊗ q_raw
        R_offset = Rotation.from_quat(offset_quat)
        offset_angle_deg = np.degrees(R_offset.magnitude())
        
        residuals = []
        for raw_quat in raw_quats:
            R_raw = Rotation.from_quat(raw_quat)
            R_aligned = R_offset * R_raw  # Should be ≈ Identity
            residual_deg = np.degrees(R_aligned.magnitude())
            residuals.append(residual_deg)
        
        residuals = np.array(residuals)
        median_resid = np.median(residuals)
        max_resid = np.max(residuals)
        status = "PASS" if median_resid < tol_deg else "FAIL"
        
        results.append({
            'joint_name': joint_name,
            'median_resid_deg': median_resid,
            'max_resid_deg': max_resid,
            'offset_angle_deg': offset_angle_deg,
            'status': status
        })
    
    return pd.DataFrame(results)


def validate_vpose_anatomy(df_ref: pd.DataFrame,
                          offsets_map: Dict[str, List[float]],
                          vpose_quat_xyzw: np.ndarray,
                          shoulder_joints: List[str],
                          quat_order: str = "xyzw",
                          euler_order: str = "XYZ") -> pd.DataFrame:
    """
    Anatomy / V-pose Validation: Check shoulder orientation in anatomical frame.
    This is NOT an identity check - it's an anatomical alignment check.
    """
    from scipy.spatial.transform import Rotation as R
    
    results = []
    
    for joint_name in shoulder_joints:
        if joint_name not in offsets_map:
            continue
            
        # Auto-detect quaternion columns
        quat_cols = []
        for axis in ['x', 'y', 'z', 'w']:
            col = f"{joint_name}__q{axis}"
            if col in df_ref.columns:
                quat_cols.append(col)
            else:
                col_alt = f"{joint_name}_quat_{axis}"
                if col_alt in df_ref.columns:
                    quat_cols.append(col_alt)
        
        if len(quat_cols) != 4:
            continue
            
        # Extract raw quaternions
        raw_quats = np.stack([df_ref[col].values for col in quat_cols], axis=1)
        
        # Hemisphere alignment
        q0 = raw_quats[0]
        dot_products = np.dot(raw_quats, q0)
        flip_mask = dot_products < 0
        raw_quats[flip_mask] = -raw_quats[flip_mask]
        
        # Apply calibration offset
        R_offset = Rotation.from_quat(offsets_map[joint_name])
        R_vpose = Rotation.from_quat(vpose_quat_xyzw)
        
        euler_angles = []
        for raw_quat in raw_quats:
            R_raw = Rotation.from_quat(raw_quat)
            R_corr = R_offset * R_raw
            # Apply V-pose: q_anat = q_vpose ⊗ q_corr (left multiplication)
            R_anat = R_vpose * R_corr
            euler = R_anat.as_euler(euler_order, degrees=True)
            euler_angles.append(euler)
        
        euler_angles = np.array(euler_angles)
        euler_mean = np.mean(euler_angles, axis=0)
        euler_median = np.median(euler_angles, axis=0)
        
        # Simple anatomy deviation score (distance from neutral)
        neutral_angles = np.array([0.0, 0.0, 0.0])  # Expected neutral shoulder
        anatomy_deviation_score = np.linalg.norm(euler_mean - neutral_angles)
        
        results.append({
            'joint_name': joint_name,
            'euler_mean_deg_x': euler_mean[0],
            'euler_mean_deg_y': euler_mean[1], 
            'euler_mean_deg_z': euler_mean[2],
            'euler_median_deg_x': euler_median[0],
            'euler_median_deg_y': euler_median[1],
            'euler_median_deg_z': euler_median[2],
            'anatomy_deviation_score': anatomy_deviation_score,
            'note': 'V-pose applied' if not np.allclose(vpose_quat_xyzw, [0, 0, 0, 1]) else 'No V-pose'
        })
    
    return pd.DataFrame(results)


def apply_shoulder_vpose_correction(R_joint: Rotation, 
                                 correction_quat_xyzw: np.ndarray,
                                 joint_name: str,
                                 shoulder_joints: List[str]) -> Rotation:
    """
    Apply shoulder V-pose correction in the appropriate coordinate frame.
    
    This function should be called during kinematics computation (NB06) rather than
    during offset computation to avoid frame mixing issues.
    
    Args:
        R_joint: Joint rotation in world space
        correction_quat_xyzw: V-Pose correction quaternion in xyzw format
        joint_name: Name of the joint
        shoulder_joints: List of shoulder joint names that need correction
        
    Returns:
        Corrected joint rotation
    """
    if joint_name not in shoulder_joints or np.allclose(correction_quat_xyzw, [0, 0, 0, 1]):
        return R_joint
    
    R_corr = Rotation.from_quat(correction_quat_xyzw)
    
    # Apply correction in world space (or whatever space R_joint is in)
    # This should be applied consistently with the space where kinematics are computed
    R_corrected = R_corr * R_joint
    
    return R_corrected


def export_calibration_offsets(offsets_map: Dict, 
                             metadata: Dict, 
                             output_path: str) -> None:
    """
    Export calibration offsets to JSON file.
    
    Args:
        offsets_map: Dictionary of joint names to offset quaternions
        metadata: Metadata dictionary
        output_path: Path to save the JSON file
    """
    export_data = {
        "offsets_map": offsets_map,
        "metadata": metadata
    }
    
    # Ensure directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    logger.info(f"Calibration offsets exported to {output_path}")


def run_anatomical_calibration(df: pd.DataFrame,
                              output_dir: str,
                              fs: float = 120.0,
                              pelvis_joint: str = "Hips",
                              left_wrist_joint: str = "LeftHand", 
                              right_wrist_joint: str = "RightHand",
                              left_shoulder: str = "LeftShoulder",
                              left_elbow: str = "LeftElbow",
                              right_shoulder: str = "RightShoulder",
                              right_elbow: str = "RightElbow",
                              elevation_threshold_deg: float = 5.0) -> Dict:
    """
    Complete anatomical calibration pipeline.
    
    Args:
        df: Input DataFrame with position and quaternion data
        output_dir: Directory to save calibration outputs
        fs: Sampling frequency
        pelvis_joint: Pelvis joint name
        left_wrist_joint: Left wrist joint name
        right_wrist_joint: Right wrist joint name
        left_shoulder: Left shoulder joint name
        left_elbow: Left elbow joint name
        right_shoulder: Right shoulder joint name
        right_elbow: Right elbow joint name
        elevation_threshold_deg: V-Pose elevation threshold
        
    Returns:
        Dictionary with calibration results and metadata
    """
    # Step 1: Find stable window
    ref_df, window_metadata = find_stable_window(
        df, pelvis_joint, left_wrist_joint, right_wrist_joint, fs=fs
    )
    
    # Step 2: Detect and correct V-Pose for both arms
    left_correction_applied, left_elevation, left_correction_quat = detect_v_pose(
        ref_df, left_shoulder, left_elbow, elevation_threshold_deg
    )
    
    right_correction_applied, right_elevation, right_correction_quat = detect_v_pose(
        ref_df, right_shoulder, right_elbow, elevation_threshold_deg
    )
    
    # Use the correction that was applied (if any), otherwise identity
    if left_correction_applied or right_correction_applied:
        # If both corrections applied, use average (they should be similar)
        if left_correction_applied and right_correction_applied:
            R_left = Rotation.from_quat(left_correction_quat)
            R_right = Rotation.from_quat(right_correction_quat)
            R_avg = R_left * R_right.inv()  # Relative rotation
            # For simplicity, use left correction as primary
            final_correction_quat = left_correction_quat
        elif left_correction_applied:
            final_correction_quat = left_correction_quat
        else:
            final_correction_quat = right_correction_quat
    else:
        final_correction_quat = np.array([0.0, 0.0, 0.0, 1.0])  # Identity
    
    # Step 3: Compute quaternion offsets
    offsets_map, quat_metadata = compute_quaternion_offsets(
        ref_df, final_correction_quat, [left_shoulder, right_shoulder], fs=fs
    )
    
    # Add time_window to metadata
    quat_metadata["time_window"] = window_metadata["time_window"]
    
    # Step 4: Export results
    output_path = Path(output_dir) / "offsets_map.json"
    export_calibration_offsets(offsets_map, quat_metadata, str(output_path))
    
    # Compile results
    results = {
        "window_metadata": window_metadata,
        "v_pose_detection": {
            "left_arm": {
                "elevation_deg": left_elevation,
                "correction_applied": left_correction_applied
            },
            "right_arm": {
                "elevation_deg": right_elevation, 
                "correction_applied": right_correction_applied
            }
        },
        "offsets_map": offsets_map,
        "quat_metadata": quat_metadata,
        "output_path": str(output_path)
    }
    
    logger.info("Anatomical calibration completed successfully")
    return results
