"""
Coordinate Systems Module - Explicit Frame Definitions and Transformations

This module provides explicit documentation and validation of coordinate frames used
throughout the pipeline, ensuring consistent interpretation of orientations and angles.

References:
    - Wu et al. (2005). ISB recommendation on definitions of joint coordinate systems.
    - OptiTrack Motive Documentation (2020). Coordinate system conventions.
    - ISO 8855 (2011). Road vehicles - Vehicle dynamics and road-holding ability.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, Tuple, List, Optional
from scipy.spatial.transform import Rotation as R

logger = logging.getLogger(__name__)


# ============================================================================
# COORDINATE FRAME DEFINITIONS
# ============================================================================

COORDINATE_FRAMES = {
    'optitrack_world': {
        'name': 'OptiTrack World Frame',
        'description': 'OptiTrack Motive global coordinate system',
        'x_axis': 'Right (subject perspective)',
        'y_axis': 'Up (vertical)',
        'z_axis': 'Forward (subject facing direction)',
        'handedness': 'right-handed',
        'units': 'millimeters',
        'reference': 'OptiTrack Motive Documentation (2020)',
        'notes': 'Origin typically at capture volume center'
    },
    
    'isb_anatomical': {
        'name': 'ISB Anatomical Frame',
        'description': 'International Society of Biomechanics standard',
        'x_axis': 'Anterior (forward)',
        'y_axis': 'Superior (upward)',  
        'z_axis': 'Right (lateral)',
        'handedness': 'right-handed',
        'units': 'meters',
        'reference': 'Wu et al. (2005) J Biomech',
        'notes': 'Standard for joint angle reporting'
    },
    
    'segment_local': {
        'name': 'Segment Local Frame',
        'description': 'Body segment-attached coordinate system',
        'x_axis': 'Along segment (proximal to distal)',
        'y_axis': 'Perpendicular to segment plane',
        'z_axis': 'Completes right-handed system',
        'handedness': 'right-handed',
        'units': 'relative',
        'reference': 'Wu et al. (2005)',
        'notes': 'Defined anatomically for each segment'
    }
}


# ISB Joint Coordinate Sequences (Wu et al. 2005)
ISB_EULER_SEQUENCES = {
    'shoulder': {
        'sequence': 'YXY',
        'angles': ['plane of elevation', 'elevation', 'axial rotation'],
        'description': 'ISB shoulder: Y(plane)-X(elev)-Y(axial)',
        'reference': 'Wu et al. (2005) Section 3.2'
    },
    'elbow': {
        'sequence': 'ZXY',
        'angles': ['flexion-extension', 'carrying angle', 'pronation-supination'],
        'description': 'ISB elbow: Z(flex-ext)-X(carry)-Y(pro-sup)',
        'reference': 'Wu et al. (2005) Section 3.3'
    },
    'knee': {
        'sequence': 'ZXY',
        'angles': ['flexion-extension', 'adduction-abduction', 'internal-external rotation'],
        'description': 'ISB knee: Z(flex)-X(abd)-Y(rot)',
        'reference': 'Wu et al. (2005) Section 3.4'
    },
    'hip': {
        'sequence': 'ZXY',
        'angles': ['flexion-extension', 'adduction-abduction', 'internal-external rotation'],
        'description': 'ISB hip: Z(flex)-X(abd)-Y(rot)',
        'reference': 'Wu et al. (2005) Section 3.5'
    },
    'default': {
        'sequence': 'ZXY',
        'angles': ['rotation1', 'rotation2', 'rotation3'],
        'description': 'Default Euler sequence for undefined joints',
        'reference': 'Industry standard'
    }
}


# ============================================================================
# COORDINATE FRAME TRANSFORMATIONS
# ============================================================================

def optitrack_to_isb_position(pos_optitrack_mm: np.ndarray) -> np.ndarray:
    """
    Transform position from OptiTrack world frame to ISB anatomical frame.
    
    OptiTrack: X=Right, Y=Up, Z=Forward
    ISB: X=Anterior(Forward), Y=Superior(Up), Z=Right
    
    Transformation: ISB = [Z_ot, Y_ot, X_ot] with unit conversion
    
    Args:
        pos_optitrack_mm: Position in OptiTrack frame (N, 3) in millimeters
        
    Returns:
        Position in ISB frame (N, 3) in meters
        
    Reference:
        Wu et al. (2005): ISB coordinate system definition
    """
    # Convert mm to m
    pos_m = pos_optitrack_mm / 1000.0
    
    # Reorder axes: OptiTrack [X_right, Y_up, Z_forward] -> ISB [X_forward, Y_up, Z_right]
    pos_isb = np.zeros_like(pos_m)
    pos_isb[..., 0] = pos_m[..., 2]  # ISB X = OptiTrack Z (forward)
    pos_isb[..., 1] = pos_m[..., 1]  # ISB Y = OptiTrack Y (up)
    pos_isb[..., 2] = pos_m[..., 0]  # ISB Z = OptiTrack X (right)
    
    return pos_isb


def optitrack_to_isb_orientation(q_optitrack: np.ndarray) -> np.ndarray:
    """
    Transform orientation quaternion from OptiTrack to ISB frame.
    
    Args:
        q_optitrack: Quaternions in OptiTrack frame (N, 4) in xyzw format
        
    Returns:
        Quaternions in ISB frame (N, 4) in xyzw format
        
    Reference:
        Wu et al. (2005): Frame transformation conventions
    """
    # Create rotation matrix for frame transformation
    # OptiTrack [X,Y,Z] = [Right, Up, Forward]
    # ISB [X,Y,Z] = [Forward, Up, Right]
    # Transformation: rotate 90° around Y axis
    R_transform = R.from_euler('y', 90, degrees=True)
    
    # Apply transformation to quaternions
    R_optitrack = R.from_quat(q_optitrack)
    R_isb = R_transform * R_optitrack
    
    return R_isb.as_quat()


def validate_coordinate_frame(pos: np.ndarray,
                             frame_type: str,
                             expected_range_m: Optional[Tuple[float, float]] = None) -> Dict[str, any]:
    """
    Validate that position data is in expected coordinate frame.
    
    Args:
        pos: Position data (N, 3)
        frame_type: 'optitrack_world' or 'isb_anatomical'
        expected_range_m: Expected position range in meters (min, max)
        
    Returns:
        Dictionary with validation results
    """
    if frame_type not in COORDINATE_FRAMES:
        return {'status': 'FAIL', 'reason': f'Unknown frame type: {frame_type}'}
    
    frame_info = COORDINATE_FRAMES[frame_type]
    
    # Compute statistics
    pos_mean = np.nanmean(pos, axis=0)
    pos_std = np.nanstd(pos, axis=0)
    pos_range = (np.nanmin(pos, axis=0), np.nanmax(pos, axis=0))
    
    # Check units (heuristic based on magnitude)
    magnitude = np.linalg.norm(pos_mean)
    
    if frame_type == 'optitrack_world':
        # OptiTrack typically in mm range (hundreds to thousands)
        expected_magnitude_range = (100, 10000)  # mm
    elif frame_type == 'isb_anatomical':
        # ISB typically in m range (fractions to few meters)
        expected_magnitude_range = (0.1, 10.0)  # m
    else:
        expected_magnitude_range = None
    
    # Validation checks
    checks = {
        'frame_type': frame_type,
        'frame_name': frame_info['name'],
        'handedness': frame_info['handedness'],
        'units': frame_info['units'],
        'mean_position': pos_mean.tolist(),
        'std_position': pos_std.tolist(),
        'range_position': (pos_range[0].tolist(), pos_range[1].tolist()),
        'magnitude': float(magnitude)
    }
    
    # Unit check
    if expected_magnitude_range:
        unit_ok = expected_magnitude_range[0] <= magnitude <= expected_magnitude_range[1]
        checks['unit_check'] = 'PASS' if unit_ok else 'WARN'
        checks['expected_magnitude_range'] = expected_magnitude_range
    
    # Range check (if provided)
    if expected_range_m:
        range_ok = np.all(pos_range[0] >= expected_range_m[0]) and np.all(pos_range[1] <= expected_range_m[1])
        checks['range_check'] = 'PASS' if range_ok else 'FAIL'
    
    return checks


def validate_quaternion_frame(q: np.ndarray) -> Dict[str, any]:
    """
    Validate quaternion properties (normalization, continuity).
    
    Args:
        q: Quaternions (N, 4) in xyzw format
        
    Returns:
        Dictionary with validation metrics
    """
    # Check normalization
    norms = np.linalg.norm(q, axis=-1)
    norm_errors = np.abs(norms - 1.0)
    
    max_norm_error = np.nanmax(norm_errors)
    mean_norm_error = np.nanmean(norm_errors)
    
    # Check for discontinuities (large frame-to-frame changes)
    if len(q) > 1:
        dot_products = np.sum(q[:-1] * q[1:], axis=1)
        min_dot = np.nanmin(dot_products)
        discontinuities = np.sum(dot_products < 0)  # Count hemisphere flips
    else:
        min_dot = 1.0
        discontinuities = 0
    
    return {
        'max_norm_error': float(max_norm_error),
        'mean_norm_error': float(mean_norm_error),
        'norm_status': 'PASS' if max_norm_error < 0.01 else 'WARN' if max_norm_error < 0.1 else 'FAIL',
        'min_dot_product': float(min_dot),
        'discontinuities': int(discontinuities),
        'continuity_status': 'PASS' if discontinuities == 0 else 'WARN'
    }


def get_joint_euler_sequence(joint_name: str) -> Dict[str, any]:
    """
    Get ISB-recommended Euler sequence for a joint.
    
    Args:
        joint_name: Name of joint (e.g., 'shoulder', 'knee', 'elbow')
        
    Returns:
        Dictionary with Euler sequence information
    """
    joint_lower = joint_name.lower()
    
    for key in ISB_EULER_SEQUENCES.keys():
        if key in joint_lower or joint_lower in key:
            return ISB_EULER_SEQUENCES[key].copy()
    
    # Return default if not found
    return ISB_EULER_SEQUENCES['default'].copy()


def document_coordinate_system_pipeline(pipeline_config: Dict) -> Dict[str, any]:
    """
    Document coordinate systems used throughout the pipeline.
    
    Args:
        pipeline_config: Pipeline configuration dictionary
        
    Returns:
        Complete coordinate system documentation
    """
    documentation = {
        'pipeline_version': pipeline_config.get('version', 'unknown'),
        'frames_used': COORDINATE_FRAMES,
        'euler_sequences': ISB_EULER_SEQUENCES,
        'transformations': {
            'raw_to_processing': {
                'input': 'optitrack_world',
                'output': 'optitrack_world',
                'units_conversion': 'mm to m',
                'operations': ['unit conversion', 'resampling', 'filtering']
            },
            'processing_to_kinematics': {
                'input': 'optitrack_world',
                'output': 'segment_local',
                'operations': ['global to local quaternions', 'reference alignment']
            },
            'kinematics_to_angles': {
                'input': 'segment_local',
                'output': 'isb_anatomical',
                'operations': ['relative rotations', 'ISB Euler extraction']
            }
        },
        'validation': {
            'position_frame': 'optitrack_world',
            'orientation_frame': 'optitrack_world (quaternions)',
            'angle_frame': 'isb_anatomical (Euler angles)',
            'units_documented': True,
            'frame_transformations_explicit': True
        }
    }
    
    return documentation


def generate_coordinate_system_report() -> str:
    """
    Generate human-readable coordinate system documentation report.
    
    Returns:
        Formatted string with complete coordinate system documentation
    """
    report_lines = [
        "="*70,
        "COORDINATE SYSTEMS DOCUMENTATION",
        "="*70,
        "",
        "1. COORDINATE FRAMES USED",
        "-"*70,
    ]
    
    for frame_id, frame_info in COORDINATE_FRAMES.items():
        report_lines.extend([
            f"\n{frame_info['name']} ({frame_id}):",
            f"  X-axis: {frame_info['x_axis']}",
            f"  Y-axis: {frame_info['y_axis']}",
            f"  Z-axis: {frame_info['z_axis']}",
            f"  Handedness: {frame_info['handedness']}",
            f"  Units: {frame_info['units']}",
            f"  Reference: {frame_info['reference']}",
            f"  Notes: {frame_info['notes']}"
        ])
    
    report_lines.extend([
        "",
        "\n2. ISB EULER SEQUENCES",
        "-"*70,
    ])
    
    for joint, seq_info in ISB_EULER_SEQUENCES.items():
        if joint != 'default':
            report_lines.extend([
                f"\n{joint.upper()}:",
                f"  Sequence: {seq_info['sequence']}",
                f"  Angles: {', '.join(seq_info['angles'])}",
                f"  Description: {seq_info['description']}",
                f"  Reference: {seq_info['reference']}"
            ])
    
    report_lines.extend([
        "",
        "\n3. PIPELINE FRAME FLOW",
        "-"*70,
        "",
        "Raw Data (OptiTrack Motive)",
        "  |-> OptiTrack World Frame (mm)",
        "       |-> Unit conversion to meters",
        "            |-> Resampling & Filtering (still OptiTrack frame)",
        "                 |-> Global-to-Local quaternions (segment frames)",
        "                      |-> Reference alignment (anatomically zeroed)",
        "                           |-> ISB Euler angles extraction",
        "",
        "="*70
    ])
    
    return "\n".join(report_lines)


# ============================================================================
# QUALITY REPORT INTEGRATION
# ============================================================================

def get_coordinate_system_metadata() -> Dict[str, any]:
    """
    Get coordinate system metadata for quality report.
    
    Returns:
        Dictionary with coordinate system information for QC reporting
    """
    return {
        'coordinate_system_documented': True,
        'input_frame': 'OptiTrack World (X=Right, Y=Up, Z=Forward)',
        'processing_frame': 'OptiTrack World',
        'angle_frame': 'ISB Anatomical',
        'euler_sequences_source': 'Wu et al. (2005)',
        'frame_transformations_explicit': True,
        'units_input': 'millimeters',
        'units_processing': 'meters',
        'handedness': 'right-handed (all frames)'
    }
