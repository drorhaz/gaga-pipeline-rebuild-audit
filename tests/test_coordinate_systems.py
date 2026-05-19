"""
Tests for Coordinate Systems Module

Tests verify that:
1. Frame definitions are correct
2. Transformations preserve geometry
3. Validation detects frame mismatches
4. ISB sequences are correctly mapped
"""

import pytest
import numpy as np
from scipy.spatial.transform import Rotation as R

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from coordinate_systems import (
    COORDINATE_FRAMES,
    ISB_EULER_SEQUENCES,
    optitrack_to_isb_position,
    optitrack_to_isb_orientation,
    validate_coordinate_frame,
    validate_quaternion_frame,
    get_joint_euler_sequence,
    get_coordinate_system_metadata
)


class TestFrameDefinitions:
    """Test coordinate frame definitions."""
    
    def test_all_frames_have_required_fields(self):
        """Test that all frame definitions have required fields."""
        required_fields = ['name', 'x_axis', 'y_axis', 'z_axis', 'handedness', 'units']
        
        for frame_id, frame_info in COORDINATE_FRAMES.items():
            for field in required_fields:
                assert field in frame_info, f"Frame {frame_id} missing field {field}"
    
    def test_all_frames_right_handed(self):
        """Test that all frames are right-handed."""
        for frame_id, frame_info in COORDINATE_FRAMES.items():
            assert frame_info['handedness'] == 'right-handed', f"Frame {frame_id} not right-handed"


class TestPositionTransformation:
    """Test position transformations."""
    
    def test_optitrack_to_isb_axes(self):
        """Test that OptiTrack to ISB correctly reorders axes."""
        # OptiTrack: [1,2,3] = [X_right=1, Y_up=2, Z_forward=3]
        pos_ot = np.array([[1000, 2000, 3000]])  # mm
        
        # ISB should be: [X_forward, Y_up, Z_right] = [3, 2, 1] in meters
        pos_isb = optitrack_to_isb_position(pos_ot)
        
        assert np.isclose(pos_isb[0, 0], 3.0), "ISB X should be OptiTrack Z"
        assert np.isclose(pos_isb[0, 1], 2.0), "ISB Y should be OptiTrack Y"
        assert np.isclose(pos_isb[0, 2], 1.0), "ISB Z should be OptiTrack X"
    
    def test_unit_conversion(self):
        """Test mm to m conversion."""
        pos_ot = np.array([[1000, 2000, 3000]])  # mm
        pos_isb = optitrack_to_isb_position(pos_ot)
        
        # Should be in meters
        assert np.all(pos_isb < 10), "Positions should be in meters, not mm"
        assert np.all(pos_isb > 0.1), "Positions should have reasonable magnitude"


class TestOrientationTransformation:
    """Test orientation transformations."""
    
    def test_identity_quaternion(self):
        """Test that identity quaternion transforms correctly."""
        q_identity = R.identity().as_quat()
        q_ot = np.array([q_identity])
        
        q_isb = optitrack_to_isb_orientation(q_ot)
        
        # Should still be unit quaternions
        norms = np.linalg.norm(q_isb, axis=1)
        assert np.allclose(norms, 1.0), "Transformed quaternions should be normalized"


class TestFrameValidation:
    """Test coordinate frame validation."""
    
    def test_optitrack_frame_detection(self):
        """Test that OptiTrack data is detected correctly."""
        # OptiTrack data in mm (large magnitudes)
        pos = np.random.randn(100, 3) * 500 + 1000  # Around 1000mm
        
        result = validate_coordinate_frame(pos, 'optitrack_world')
        
        assert result['unit_check'] == 'PASS'
        assert result['units'] == 'millimeters'
    
    def test_isb_frame_detection(self):
        """Test that ISB data is detected correctly."""
        # ISB data in meters (small magnitudes)
        pos = np.random.randn(100, 3) * 0.5 + 1.0  # Around 1m
        
        result = validate_coordinate_frame(pos, 'isb_anatomical')
        
        assert result['unit_check'] == 'PASS'
        assert result['units'] == 'meters'


class TestQuaternionValidation:
    """Test quaternion validation."""
    
    def test_normalized_quaternions_pass(self):
        """Test that normalized quaternions pass validation."""
        q = np.array([R.identity().as_quat() for _ in range(100)])
        
        result = validate_quaternion_frame(q)
        
        assert result['norm_status'] == 'PASS'
        assert result['max_norm_error'] < 1e-10
    
    def test_denormalized_quaternions_fail(self):
        """Test that denormalized quaternions fail validation."""
        q = np.random.randn(100, 4) * 2  # Not normalized
        
        result = validate_quaternion_frame(q)
        
        assert result['norm_status'] in ['WARN', 'FAIL']
        assert result['max_norm_error'] > 0.1


class TestEulerSequences:
    """Test ISB Euler sequence mapping."""
    
    def test_shoulder_sequence(self):
        """Test that shoulder uses YXY sequence."""
        seq_info = get_joint_euler_sequence('shoulder')
        
        assert seq_info['sequence'] == 'YXY'
        assert len(seq_info['angles']) == 3
    
    def test_knee_sequence(self):
        """Test that knee uses ZXY sequence."""
        seq_info = get_joint_euler_sequence('knee')
        
        assert seq_info['sequence'] == 'ZXY'
    
    def test_default_sequence(self):
        """Test that unknown joints get default sequence."""
        seq_info = get_joint_euler_sequence('unknown_joint')
        
        assert seq_info['sequence'] == 'ZXY'


class TestMetadata:
    """Test coordinate system metadata."""
    
    def test_metadata_complete(self):
        """Test that metadata contains required fields."""
        metadata = get_coordinate_system_metadata()
        
        required_fields = [
            'coordinate_system_documented',
            'input_frame',
            'angle_frame',
            'units_input',
            'units_processing'
        ]
        
        for field in required_fields:
            assert field in metadata, f"Metadata missing field: {field}"
    
    def test_coordinate_system_documented(self):
        """Test that coordinate system is marked as documented."""
        metadata = get_coordinate_system_metadata()
        
        assert metadata['coordinate_system_documented'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
