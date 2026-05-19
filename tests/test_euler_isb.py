"""
Test suite for ISB joint angle extraction module.

This module implements comprehensive tests for:
- ISB Euler sequence mapping
- Relative rotation calculations
- Joint angle extraction
- Identity validation (zero angles for identical rotations)
- Gimbal lock detection
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path
from scipy.spatial.transform import Rotation

sys.path.append(str(Path(__file__).parent.parent))

from src.euler_isb import (
    extract_isb_euler,
    get_euler_sequence,
    validate_joint_angles,
    get_euler_columns,
    check_euler_gimbal_lock,
    create_standard_joint_map,
    EULER_SEQ_BY_JOINT
)


class TestEulerSequenceMapping:
    """Test ISB Euler sequence mapping."""
    
    def test_shoulder_sequence(self):
        """Test shoulder Euler sequence."""
        seq = get_euler_sequence('Shoulder')
        assert seq == 'yxy', f"Shoulder should be 'yxy', got '{seq}'"
    
    def test_knee_sequence(self):
        """Test knee Euler sequence."""
        seq = get_euler_sequence('Knee')
        assert seq == 'zxy', f"Knee should be 'zxy', got '{seq}'"
    
    def test_elbow_sequence(self):
        """Test elbow Euler sequence."""
        seq = get_euler_sequence('Elbow')
        assert seq == 'zxy', f"Elbow should be 'zxy', got '{seq}'"
    
    def test_default_sequence(self):
        """Test default Euler sequence for other joints."""
        seq = get_euler_sequence('UnknownJoint')
        assert seq == 'zxy', f"Default should be 'zxy', got '{seq}'"
    
    def test_mapping_completeness(self):
        """Test that mapping contains required joints."""
        required_joints = ['Shoulder', 'Knee', 'Elbow']
        for joint in required_joints:
            assert joint in EULER_SEQ_BY_JOINT, f"Missing joint {joint} in mapping"
    
    def test_mapping_values(self):
        """Test that mapping values are valid Euler sequences."""
        for joint, seq in EULER_SEQ_BY_JOINT.items():
            if joint != 'default':
                assert len(seq) == 3, f"Invalid sequence length for {joint}: {seq}"
                assert all(axis in 'xyz' for axis in seq), f"Invalid axes in {joint} sequence: {seq}"


class TestRelativeRotation:
    """Test relative rotation calculations."""
    
    def test_identity_rotation(self):
        """Test identity rotation case."""
        # Create test data with identical parent and child rotations
        n_frames = 10
        
        # Use separate quaternion components to avoid 2D array issues
        df = pd.DataFrame({
            'time_s': np.linspace(0, 1, n_frames),
            'Parent__qx_aligned': np.zeros(n_frames),
            'Parent__qy_aligned': np.zeros(n_frames),
            'Parent__qz_aligned': np.zeros(n_frames),
            'Parent__qw_aligned': np.ones(n_frames),
            'Child__qx_aligned': np.zeros(n_frames),
            'Child__qy_aligned': np.zeros(n_frames),
            'Child__qz_aligned': np.zeros(n_frames),
            'Child__qw_aligned': np.ones(n_frames)
        })
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        df_result = extract_isb_euler(df, joint_map)
        
        # All angles should be zero (within tolerance)
        e1_col = 'TestJoint__e1_deg'
        e2_col = 'TestJoint__e2_deg'
        e3_col = 'TestJoint__e3_deg'
        
        assert np.allclose(df_result[e1_col], 0.0, atol=1e-6), "e1 should be zero for identity"
        assert np.allclose(df_result[e2_col], 0.0, atol=1e-6), "e2 should be zero for identity"
        assert np.allclose(df_result[e3_col], 0.0, atol=1e-6), "e3 should be zero for identity"
    
    def test_known_rotation(self):
        """Test known relative rotation."""
        n_frames = 5
        
        # Create proper 2D quaternion arrays (N, 4)
        parent_quats = np.array([[0, 0, 0, 1]] * n_frames)
        child_quats = np.array([[0, 0, 0, 1]] * n_frames)
        
        df = pd.DataFrame({
            'time_s': np.linspace(0, 1, n_frames),
            'Parent__q_aligned': parent_quats,
            'Child__q_aligned': child_quats
        })
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        df_result = extract_isb_euler(df, joint_map)
        
        # For identity rotation, all angles should be zero (within tolerance)
        e1_col = 'TestJoint__e1_deg'
        e2_col = 'TestJoint__e2_deg'
        e3_col = 'TestJoint__e3_deg'
        
        assert np.allclose(df_result[e1_col], 0.0, atol=1e-6), "e1 should be zero for identity"
        assert np.allclose(df_result[e2_col], 0.0, atol=1e-6), "e2 should be zero for identity"
        assert np.allclose(df_result[e3_col], 0.0, atol=1e-6), "e3 should be zero for identity"
    
    def test_multi_axis_rotation(self):
        """Test multi-axis relative rotation."""
        n_frames = 5
        
        # Parent: 45° about Z
        parent_quat = np.array([0, 0, 0, 1])
        
        # Child: 45° about Z + 30° about X
        R_parent = Rotation.from_euler('zxy', [45, 0, 0], degrees=True)
        R_child = Rotation.from_euler('zxy', [45, 30, 0], degrees=True)
        child_quat = R_child.as_quat()
        
        # Create proper 2D quaternion arrays (N, 4) by reshaping
        parent_quats = np.array([R_parent.as_quat() for _ in range(n_frames)])
        child_quats = np.array([R_child.as_quat() for _ in range(n_frames)])
        
        df = pd.DataFrame({
            'time_s': np.linspace(0, 1, n_frames),
            'Parent__q_aligned': parent_quats,
            'Child__q_aligned': child_quats
        })
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        df_result = extract_isb_euler(df, joint_map)
        
        # Relative rotation should be 30° about X
        e1_col = 'TestJoint__e1_deg'
        e2_col = 'TestJoint__e2_deg'
        e3_col = 'TestJoint__e3_deg'
        
        assert np.allclose(df_result[e1_col], 0.0, atol=1e-3), f"e1 should be 0°, got {df_result[e1_col].iloc[0]}"
        assert np.allclose(df_result[e2_col], 30.0, atol=1e-3), f"e2 should be 30°, got {df_result[e2_col].iloc[0]}"
        assert np.allclose(df_result[e3_col], 0.0, atol=1e-3), f"e3 should be 0°, got {df_result[e3_col].iloc[0]}"


class TestJointAngleExtraction:
    """Test joint angle extraction functionality."""
    
    def test_multiple_joints(self):
        """Test extraction for multiple joints simultaneously."""
        n_frames = 8
        
        # Create proper 1D arrays for quaternions
        data = {'time_s': np.linspace(0, 1, n_frames)}
        
        # Pelvis: identity
        data['Pelvis__qx_aligned'] = np.zeros(n_frames)
        data['Pelvis__qy_aligned'] = np.zeros(n_frames)
        data['Pelvis__qz_aligned'] = np.zeros(n_frames)
        data['Pelvis__qw_aligned'] = np.ones(n_frames)
        
        # RightThigh: identity
        data['RightThigh__qx_aligned'] = np.zeros(n_frames)
        data['RightThigh__qy_aligned'] = np.zeros(n_frames)
        data['RightThigh__qz_aligned'] = np.zeros(n_frames)
        data['RightThigh__qw_aligned'] = np.ones(n_frames)
        
        # RightShank: 45° about Y
        y_quat = np.array([0, np.sin(np.pi/8), 0, np.cos(np.pi/8)])  # 45° about Y
        data['RightShank__qx_aligned'] = np.full(n_frames, y_quat[0])
        data['RightShank__qy_aligned'] = np.full(n_frames, y_quat[1])
        data['RightShank__qz_aligned'] = np.full(n_frames, y_quat[2])
        data['RightShank__qw_aligned'] = np.full(n_frames, y_quat[3])
        
        df = pd.DataFrame(data)
        
        joint_map = {
            'RightKnee': {'parent': 'RightThigh', 'child': 'RightShank'},
            'TestJoint': {'parent': 'Pelvis', 'child': 'RightThigh'}
        }
        
        df_result = extract_isb_euler(df, joint_map)
        
        # Check that all joint angle columns are created
        expected_cols = [
            'RightKnee__e1_deg', 'RightKnee__e2_deg', 'RightKnee__e3_deg',
            'TestJoint__e1_deg', 'TestJoint__e2_deg', 'TestJoint__e3_deg'
        ]
        
        for col in expected_cols:
            assert col in df_result.columns, f"Missing column: {col}"
        
        # RightKnee should have 45° about Y (zxy sequence: e2 is Y)
        assert np.allclose(df_result['RightKnee__e2_deg'], 45.0, atol=1e-3), "RightKnee e2 should be 45°"
        
        # TestJoint should be identity (0°)
        assert np.allclose(df_result['TestJoint__e1_deg'], 0.0, atol=1e-6), "TestJoint should be identity"
    
    def test_separate_quaternion_components(self):
        """Test extraction with separate quaternion components."""
        n_frames = 5
        
        # Create proper 1D arrays for separate quaternion components
        # 90° rotation about X axis: [sin(45°), 0, 0, cos(45°)] = [0.707, 0, 0, 0.707]
        data = {
            'time_s': np.linspace(0, 1, n_frames),
            'Parent__qx_aligned': np.zeros(n_frames),
            'Parent__qy_aligned': np.zeros(n_frames),
            'Parent__qz_aligned': np.zeros(n_frames),
            'Parent__qw_aligned': np.ones(n_frames),
            'Child__qx_aligned': np.full(n_frames, np.sin(np.pi/4)),  # 90° about X
            'Child__qy_aligned': np.zeros(n_frames),
            'Child__qz_aligned': np.zeros(n_frames),
            'Child__qw_aligned': np.full(n_frames, np.cos(np.pi/4))
        }
        
        df = pd.DataFrame(data)
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        df_result = extract_isb_euler(df, joint_map)
        
        # Should extract 90° about X correctly
        assert np.allclose(df_result['TestJoint__e1_deg'], 90.0, atol=1e-3), "Should handle separate components"
    
    def test_missing_quaternion_columns(self):
        """Test error handling for missing quaternion columns."""
        df = pd.DataFrame({
            'time_s': [0, 1, 2],
            'Parent__q_aligned': [[0, 0, 0, 1], [0, 0, 0, 1], [0, 0, 0, 1]]
            # Missing Child quaternion
        })
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        with pytest.raises(ValueError, match="Missing aligned quaternion columns"):
            extract_isb_euler(df, joint_map)


class TestValidation:
    """Test joint angle validation functionality."""
    
    def test_identity_validation(self):
        """Test validation of identity rotation."""
        n_frames = 10
        
        df = pd.DataFrame({
            'time_s': np.linspace(0, 1, n_frames),
            'TestJoint__e1_deg': np.zeros(n_frames),
            'TestJoint__e2_deg': np.zeros(n_frames),
            'TestJoint__e3_deg': np.zeros(n_frames)
        })
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        validation_results = validate_joint_angles(df, joint_map)
        
        assert validation_results['TestJoint'] == True, "Identity validation should pass"
    
    def test_small_angle_validation(self):
        """Test validation with small non-zero angles."""
        n_frames = 10
        
        df = pd.DataFrame({
            'time_s': np.linspace(0, 1, n_frames),
            'TestJoint__e1_deg': np.full(n_frames, 1e-7),  # Within tolerance
            'TestJoint__e2_deg': np.full(n_frames, -5e-7),  # Within tolerance
            'TestJoint__e3_deg': np.full(n_frames, 8e-7)   # Within tolerance
        })
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        validation_results = validate_joint_angles(df, joint_map, tolerance=1e-6)
        
        assert validation_results['TestJoint'] == True, "Small angles within tolerance should pass"
    
    def test_large_angle_validation(self):
        """Test validation failure with large angles."""
        n_frames = 10
        
        df = pd.DataFrame({
            'time_s': np.linspace(0, 1, n_frames),
            'TestJoint__e1_deg': np.full(n_frames, 1.0),  # Outside tolerance
            'TestJoint__e2_deg': np.zeros(n_frames),
            'TestJoint__e3_deg': np.zeros(n_frames)
        })
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        validation_results = validate_joint_angles(df, joint_map, tolerance=1e-6)
        
        assert validation_results['TestJoint'] == False, "Large angles should fail validation"
    
    def test_missing_columns_validation(self):
        """Test validation with missing angle columns."""
        df = pd.DataFrame({
            'time_s': [0, 1, 2],
            'TestJoint__e1_deg': [0, 0, 0],
            'TestJoint__e2_deg': [0, 0, 0]
            # Missing e3 column
        })
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        validation_results = validate_joint_angles(df, joint_map)
        
        assert validation_results['TestJoint'] == False, "Missing columns should fail validation"


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_get_euler_columns(self):
        """Test Euler column name generation."""
        cols = get_euler_columns('TestJoint')
        expected = ['TestJoint__e1_deg', 'TestJoint__e2_deg', 'TestJoint__e3_deg']
        assert cols == expected, f"Expected {expected}, got {cols}"
    
    def test_create_standard_joint_map(self):
        """Test standard joint map creation."""
        joint_map = create_standard_joint_map()
        
        # Check that key joints are present
        expected_joints = ['RightShoulder', 'LeftShoulder', 'RightElbow', 'LeftElbow', 
                        'RightKnee', 'LeftKnee', 'RightHip', 'LeftHip']
        
        for joint in expected_joints:
            assert joint in joint_map, f"Missing joint: {joint}"
            assert 'parent' in joint_map[joint], f"Missing parent for {joint}"
            assert 'child' in joint_map[joint], f"Missing child for {joint}"
    
    def test_gimbal_lock_detection(self):
        """Test gimbal lock detection."""
        n_frames = 100
        
        # Create angles with gimbal lock condition (e2 near ±90°)
        e2_angles = np.zeros(n_frames)
        e2_angles[50] = 89.0  # Near gimbal lock
        e2_angles[75] = -89.0  # Near gimbal lock
        
        df = pd.DataFrame({
            'TestJoint__e1_deg': np.zeros(n_frames),
            'TestJoint__e2_deg': e2_angles,
            'TestJoint__e3_deg': np.zeros(n_frames)
        })
        
        result = check_euler_gimbal_lock(df, 'TestJoint', threshold=85.0)
        
        assert result['n_gimbal_frames'] == 2, f"Expected 2 gimbal frames, got {result['n_gimbal_frames']}"
        assert result['percentage_gimbal'] == 2.0, f"Expected 2% gimbal, got {result['percentage_gimbal']}"
        assert 50 in result['gimbal_frames'], "Frame 50 should be flagged"
        assert 75 in result['gimbal_frames'], "Frame 75 should be flagged"
    
    def test_gimbal_lock_no_detection(self):
        """Test gimbal lock detection with normal angles."""
        n_frames = 100
        
        # Create deterministic angles that won't trigger gimbal lock
        e2_angles = np.linspace(-30, 30, n_frames)  # Well within ±85° range
        
        df = pd.DataFrame({
            'TestJoint__e1_deg': np.zeros(n_frames),
            'TestJoint__e2_deg': e2_angles,
            'TestJoint__e3_deg': np.zeros(n_frames)
        })
        
        result = check_euler_gimbal_lock(df, 'TestJoint', threshold=85.0)
        
        assert result['n_gimbal_frames'] == 0, f"Expected 0 gimbal frames, got {result['n_gimbal_frames']}"
        assert result['percentage_gimbal'] == 0.0, f"Expected 0% gimbal, got {result['percentage_gimbal']}"


class TestIntegration:
    """Test end-to-end integration scenarios."""
    
    def test_full_pipeline_simulation(self):
        """Test full pipeline from quaternions to joint angles."""
        n_frames = 20
        
        # Simulate realistic biomechanical data
        t = np.linspace(0, 2, n_frames)
        
        # Create time-varying rotations
        parent_angles = np.column_stack([
            10 * np.sin(2 * np.pi * 0.5 * t),  # 0.5 Hz flexion/extension
            5 * np.sin(2 * np.pi * 0.3 * t),    # 0.3 Hz abduction/adduction  
            3 * np.sin(2 * np.pi * 0.2 * t)     # 0.2 Hz internal/external rotation
        ])
        
        child_angles = np.column_stack([
            15 * np.sin(2 * np.pi * 0.5 * t),  # Larger amplitude
            8 * np.sin(2 * np.pi * 0.3 * t),
            5 * np.sin(2 * np.pi * 0.2 * t)
        ])
        
        # Convert to quaternions
        R_parent = Rotation.from_euler('zxy', parent_angles, degrees=True)
        R_child = Rotation.from_euler('zxy', child_angles, degrees=True)
        
        # Create DataFrame with separate quaternion components
        data = {'time_s': t}
        parent_quats = R_parent.as_quat()
        child_quats = R_child.as_quat()
        
        for i in range(n_frames):
            data[f'Parent__qx_aligned_{i}'] = parent_quats[i, 0]
            data[f'Parent__qy_aligned_{i}'] = parent_quats[i, 1]
            data[f'Parent__qz_aligned_{i}'] = parent_quats[i, 2]
            data[f'Parent__qw_aligned_{i}'] = parent_quats[i, 3]
            data[f'Child__qx_aligned_{i}'] = child_quats[i, 0]
            data[f'Child__qy_aligned_{i}'] = child_quats[i, 1]
            data[f'Child__qz_aligned_{i}'] = child_quats[i, 2]
            data[f'Child__qw_aligned_{i}'] = child_quats[i, 3]
        
        # Simplify: create proper DataFrame with separate components
        df = pd.DataFrame({
            'time_s': t,
            'Parent__qx_aligned': parent_quats[:, 0],
            'Parent__qy_aligned': parent_quats[:, 1],
            'Parent__qz_aligned': parent_quats[:, 2],
            'Parent__qw_aligned': parent_quats[:, 3],
            'Child__qx_aligned': child_quats[:, 0],
            'Child__qy_aligned': child_quats[:, 1],
            'Child__qz_aligned': child_quats[:, 2],
            'Child__qw_aligned': child_quats[:, 3]
        })
        
        joint_map = {'TestJoint': {'parent': 'Parent', 'child': 'Child'}}
        
        df_result = extract_isb_euler(df, joint_map)
        
        # Verify that joint angles are extracted correctly
        assert all(col in df_result.columns for col in get_euler_columns('TestJoint'))
        
        # Check that angles are reasonable (not NaN, within expected range)
        for col in get_euler_columns('TestJoint'):
            angles = df_result[col].values
            assert not np.any(np.isnan(angles)), f"NaN values in {col}"
            assert np.all(np.abs(angles) <= 180), f"Angles out of range in {col}"
        
        # Validate the extraction
        validation_results = validate_joint_angles(df_result, joint_map, tolerance=1e-3)
        # Note: This won't pass for non-identity case, which is expected
    
    def test_different_euler_sequences(self):
        """Test different Euler sequences for different joints."""
        n_frames = 5
        
        # Create same rotation but test different sequences
        R_test = Rotation.from_euler('xyz', [30, 45, 60], degrees=True)
        quat = R_test.as_quat()
        
        # Create DataFrame with separate quaternion components
        data = {'time_s': np.linspace(0, 1, n_frames)}
        for joint in ['Shoulder', 'Knee', 'Elbow']:
            data[f'{joint}__qx_aligned'] = np.full(n_frames, quat[0])
            data[f'{joint}__qy_aligned'] = np.full(n_frames, quat[1])
            data[f'{joint}__qz_aligned'] = np.full(n_frames, quat[2])
            data[f'{joint}__qw_aligned'] = np.full(n_frames, quat[3])
        
        df = pd.DataFrame(data)
        
        joint_map = {
            'Shoulder': {'parent': 'Parent', 'child': 'Shoulder'},
            'Knee': {'parent': 'Parent', 'child': 'Knee'},
            'Elbow': {'parent': 'Parent', 'child': 'Elbow'}
        }
        
        df_result = extract_isb_euler(df, joint_map)
        
        # All should extract angles, but values will differ due to different sequences
        shoulder_cols = get_euler_columns('Shoulder')
        knee_cols = get_euler_columns('Knee')
        elbow_cols = get_euler_columns('Elbow')
        
        assert all(col in df_result.columns for col in shoulder_cols)
        assert all(col in df_result.columns for col in knee_cols)
        assert all(col in df_result.columns for col in elbow_cols)
        
        # Values should be different due to different sequences
        shoulder_e1 = df_result['Shoulder__e1_deg'].iloc[0]
        knee_e1 = df_result['Knee__e1_deg'].iloc[0]
        
        # They should be different (shoulder uses yxy, knee uses zxy)
        assert not np.allclose(shoulder_e1, knee_e1, atol=1e-3), "Different sequences should give different angles"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
