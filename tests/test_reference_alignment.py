"""
Test suite for reference alignment module.

This module implements comprehensive tests for quaternion reference alignment including:
- Identity on static alignment verification
- Known rotation alignment tests
- No Euler operation verification
- Input validation and error handling
"""

import numpy as np
import pandas as pd
import pytest
import tempfile
import json
from pathlib import Path
from scipy.spatial.transform import Rotation as R

import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.kinematics_alignment import (
    apply_reference_offsets,
    get_aligned_quaternion_columns,
    validate_alignment_quality
)


class TestReferenceAlignment:
    """Test core reference alignment functionality."""
    
    def test_identity_on_static(self):
        """Test that if R_raw == inv(R_offset) then R_aligned is identity within 1e-6."""
        # Create test data
        n_frames = 100
        fs = 120.0
        time_s = np.linspace(0, n_frames/fs, n_frames)
        
        # Create a static rotation (10° about X)
        R_static = R.from_euler('x', 10, degrees=True)
        static_quat_xyzw = R_static.as_quat()
        
        # The offset should be the inverse of the static rotation
        R_offset = R_static.inv()
        offset_quat_xyzw = R_offset.as_quat()
        
        # Create DataFrame where raw quaternions equal the static rotation
        data = {
            'time_s': time_s,
            'TestJoint_quat_x': np.full(n_frames, static_quat_xyzw[0]),
            'TestJoint_quat_y': np.full(n_frames, static_quat_xyzw[1]),
            'TestJoint_quat_z': np.full(n_frames, static_quat_xyzw[2]),
            'TestJoint_quat_w': np.full(n_frames, static_quat_xyzw[3])
        }
        
        df = pd.DataFrame(data)
        offsets_map = {'TestJoint': offset_quat_xyzw.tolist()}
        
        # Apply reference offsets
        df_aligned = apply_reference_offsets(df, offsets_map)
        
        # Check that aligned quaternions are identity
        aligned_cols = [col for col in df_aligned.columns if col.endswith('__q_aligned')]
        assert len(aligned_cols) == 4
        
        aligned_quat = df_aligned[['TestJoint_quat_x__q_aligned', 
                                   'TestJoint_quat_y__q_aligned',
                                   'TestJoint_quat_z__q_aligned', 
                                   'TestJoint_quat_w__q_aligned']].values
        
        # Should be identity quaternions (0, 0, 0, 1) within tolerance
        identity_quat = np.array([0.0, 0.0, 0.0, 1.0])
        for i in range(n_frames):
            assert np.allclose(aligned_quat[i], identity_quat, atol=1e-6), \
                f"Frame {i}: {aligned_quat[i]} not close to identity"
    
    def test_known_rotation_alignment(self):
        """Test static = 10° about X, raw = 40° about X ⇒ aligned ≈ 30° about X."""
        n_frames = 50
        fs = 120.0
        time_s = np.linspace(0, n_frames/fs, n_frames)
        
        # Static rotation: 10° about X
        R_static = R.from_euler('x', 10, degrees=True)
        static_quat_xyzw = R_static.as_quat()
        
        # Raw rotation: 40° about X
        R_raw = R.from_euler('x', 40, degrees=True)
        raw_quat_xyzw = R_raw.as_quat()
        
        # Offset is inverse of static
        R_offset = R_static.inv()
        offset_quat_xyzw = R_offset.as_quat()
        
        # Expected result: 30° about X (40° - 10°)
        R_expected = R.from_euler('x', 30, degrees=True)
        expected_quat_xyzw = R_expected.as_quat()
        
        # Create DataFrame
        data = {
            'time_s': time_s,
            'TestJoint_quat_x': np.full(n_frames, raw_quat_xyzw[0]),
            'TestJoint_quat_y': np.full(n_frames, raw_quat_xyzw[1]),
            'TestJoint_quat_z': np.full(n_frames, raw_quat_xyzw[2]),
            'TestJoint_quat_w': np.full(n_frames, raw_quat_xyzw[3])
        }
        
        df = pd.DataFrame(data)
        offsets_map = {'TestJoint': offset_quat_xyzw.tolist()}
        
        # Apply reference offsets
        df_aligned = apply_reference_offsets(df, offsets_map)
        
        # Check aligned quaternions
        aligned_quat = df_aligned[['TestJoint_quat_x__q_aligned', 
                                   'TestJoint_quat_y__q_aligned',
                                   'TestJoint_quat_z__q_aligned', 
                                   'TestJoint_quat_w__q_aligned']].values
        
        # Should be approximately 30° about X
        for i in range(n_frames):
            assert np.allclose(aligned_quat[i], expected_quat_xyzw, atol=1e-5), \
                f"Frame {i}: expected {expected_quat_xyzw}, got {aligned_quat[i]}"
    
    def test_multi_joint_alignment(self):
        """Test alignment with multiple joints."""
        n_frames = 30
        time_s = np.linspace(0, 1, n_frames)
        
        # Create different rotations for different joints
        joints = ['LeftShoulder', 'RightShoulder', 'Pelvis']
        data = {'time_s': time_s}
        offsets_map = {}
        
        for joint in joints:
            # Static rotation varies by joint
            static_angle = np.random.uniform(5, 15)  # Random angle 5-15°
            R_static = R.from_euler('z', static_angle, degrees=True)
            R_offset = R_static.inv()
            
            # Raw rotation is static + additional rotation
            raw_angle = static_angle + 20  # Add 20°
            R_raw = R.from_euler('z', raw_angle, degrees=True)
            
            # Store data
            raw_quat = R_raw.as_quat()
            for i, axis in enumerate(['x', 'y', 'z', 'w']):
                data[f"{joint}_quat_{axis}"] = np.full(n_frames, raw_quat[i])
            
            offsets_map[joint] = R_offset.as_quat().tolist()
        
        df = pd.DataFrame(data)
        df_aligned = apply_reference_offsets(df, offsets_map)
        
        # Check that all joints have aligned columns
        aligned_cols = get_aligned_quaternion_columns(df_aligned)
        expected_cols = len(joints) * 4  # 4 quaternion components per joint
        assert len(aligned_cols) == expected_cols
        
        # Verify alignment quality for each joint
        for joint in joints:
            metrics = validate_alignment_quality(df_aligned, joint)
            assert metrics['mean_norm'] > 0.99  # Should be close to 1.0
            assert metrics['norm_std'] < 1e-6
            assert metrics['frames_with_invalid_norm'] == 0
    
    def test_dynamic_quaternions(self):
        """Test alignment with time-varying quaternions."""
        n_frames = 100
        time_s = np.linspace(0, 2, n_frames)
        
        # Create time-varying rotation (sinusoidal motion)
        angles = 10 * np.sin(2 * np.pi * time_s)  # ±10° sinusoid
        R_raw_array = R.from_euler('y', angles, degrees=True)
        raw_quats = R_raw_array.as_quat()  # Shape: (n_frames, 4)
        
        # Static offset: 5° about Y
        R_static = R.from_euler('y', 5, degrees=True)
        R_offset = R_static.inv()
        offset_quat = R_offset.as_quat()
        
        # Create DataFrame
        data = {'time_s': time_s}
        for i, axis in enumerate(['x', 'y', 'z', 'w']):
            data[f"TestJoint_quat_{axis}"] = raw_quats[:, i]
        
        df = pd.DataFrame(data)
        offsets_map = {'TestJoint': offset_quat.tolist()}
        
        # Apply reference offsets
        df_aligned = apply_reference_offsets(df, offsets_map)
        
        # Check that aligned quaternions are properly normalized
        aligned_quats = df_aligned[['TestJoint_quat_x__q_aligned', 
                                    'TestJoint_quat_y__q_aligned',
                                    'TestJoint_quat_z__q_aligned', 
                                    'TestJoint_quat_w__q_aligned']].values
        
        norms = np.linalg.norm(aligned_quats, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-10)
        
        # Verify the offset was applied correctly
        # The result should be the original motion minus the static offset
        for i in range(n_frames):
            R_aligned = R.from_quat(aligned_quats[i])
            # This should equal the original rotation minus the static offset
            R_expected = R_offset * R.from_euler('y', angles[i], degrees=True)
            expected_quat = R_expected.as_quat()
            
            assert np.allclose(aligned_quats[i], expected_quat, atol=1e-5)


class TestInputValidation:
    """Test input validation and error handling."""
    
    def test_time_monotonic_assertion(self):
        """Test that non-monotonic time raises AssertionError."""
        # Create data with non-monotonic time
        time_s = np.array([0.0, 0.1, 0.05, 0.2])  # Not monotonic
        quat_xyzw = R.from_euler('x', 10, degrees=True).as_quat()
        
        data = {
            'time_s': time_s,
            'TestJoint_quat_x': np.full(4, quat_xyzw[0]),
            'TestJoint_quat_y': np.full(4, quat_xyzw[1]),
            'TestJoint_quat_z': np.full(4, quat_xyzw[2]),
            'TestJoint_quat_w': np.full(4, quat_xyzw[3])
        }
        
        df = pd.DataFrame(data)
        offsets_map = {'TestJoint': quat_xyzw.tolist()}
        
        # Should raise AssertionError due to non-monotonic time
        with pytest.raises(AssertionError, match="Time column must be strictly monotonic"):
            apply_reference_offsets(df, offsets_map)
    
    def test_missing_quaternion_columns(self):
        """Test that missing quaternion columns raise ValueError."""
        n_frames = 10
        time_s = np.linspace(0, 1, n_frames)
        
        # Create DataFrame with missing quaternion component
        data = {
            'time_s': time_s,
            'TestJoint_quat_x': np.random.randn(n_frames),
            'TestJoint_quat_y': np.random.randn(n_frames),
            'TestJoint_quat_z': np.random.randn(n_frames),
            # Missing 'TestJoint_quat_w'
        }
        
        df = pd.DataFrame(data)
        offsets_map = {'TestJoint': [0, 0, 0, 1]}
        
        # Should raise ValueError due to missing columns
        with pytest.raises(ValueError, match="Missing quaternion columns"):
            apply_reference_offsets(df, offsets_map)
    
    def test_nan_quaternion_data(self):
        """Test that NaN quaternion data raises ValueError."""
        n_frames = 10
        time_s = np.linspace(0, 1, n_frames)
        quat_xyzw = R.from_euler('x', 10, degrees=True).as_quat()
        
        # Create DataFrame with NaN values
        data = {
            'time_s': time_s,
            'TestJoint_quat_x': np.full(n_frames, quat_xyzw[0]),
            'TestJoint_quat_y': np.full(n_frames, quat_xyzw[1]),
            'TestJoint_quat_z': np.full(n_frames, quat_xyzw[2]),
            'TestJoint_quat_w': np.full(n_frames, quat_xyzw[3])
        }
        
        # Introduce NaN values
        data['TestJoint_quat_y'][5] = np.nan
        
        df = pd.DataFrame(data)
        offsets_map = {'TestJoint': quat_xyzw.tolist()}
        
        # Should raise ValueError due to NaN values
        with pytest.raises(ValueError, match="Non-finite quaternion data"):
            apply_reference_offsets(df, offsets_map)
    
    def test_joint_not_in_offsets_map(self):
        """Test handling when joint is not in offsets_map."""
        n_frames = 10
        time_s = np.linspace(0, 1, n_frames)
        quat_xyzw = R.from_euler('x', 10, degrees=True).as_quat()
        
        data = {
            'time_s': time_s,
            'TestJoint_quat_x': np.full(n_frames, quat_xyzw[0]),
            'TestJoint_quat_y': np.full(n_frames, quat_xyzw[1]),
            'TestJoint_quat_z': np.full(n_frames, quat_xyzw[2]),
            'TestJoint_quat_w': np.full(n_frames, quat_xyzw[3])
        }
        
        df = pd.DataFrame(data)
        offsets_map = {'OtherJoint': quat_xyzw.tolist()}  # Different joint name
        
        # Should not raise error, but should skip the joint
        df_aligned = apply_reference_offsets(df, offsets_map)
        
        # No aligned columns should be created
        aligned_cols = get_aligned_quaternion_columns(df_aligned)
        assert len(aligned_cols) == 0


class TestNoEulerOperations:
    """Test that no Euler operations are used in the alignment process."""
    
    def test_no_euler_imports(self):
        """Test that the module doesn't import Euler functions."""
        import src.kinematics_alignment as alignment_module
        
        # Check that no Euler-related methods are imported or used
        module_source = alignment_module.__file__
        with open(module_source, 'r') as f:
            source_code = f.read()
        
        # Should not contain Euler-related operations
        euler_terms = ['from_euler', 'as_euler', 'euler', 'Euler']
        for term in euler_terms:
            assert term not in source_code, f"Found Euler term '{term}' in source code"
    
    def test_no_euler_in_alignment_function(self):
        """Test that the alignment function doesn't use Euler operations."""
        # This is a grep-based test as specified in requirements
        import subprocess
        import os
        
        module_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'kinematics_alignment.py')
        
        # Use grep to search for Euler-related terms
        try:
            result = subprocess.run(
                ['grep', '-i', 'euler', module_path],
                capture_output=True,
                text=True
            )
            # Should find no matches
            assert result.returncode == 1, "Found Euler operations in alignment module"
        except FileNotFoundError:
            # If grep is not available, check manually
            with open(module_path, 'r') as f:
                source_code = f.read()
            assert 'euler' not in source_code.lower(), "Found Euler operations in alignment module"


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_get_aligned_quaternion_columns(self):
        """Test getting aligned quaternion column names."""
        df = pd.DataFrame({
            'time_s': [0, 1, 2],
            'Joint1_quat_x__q_aligned': [1, 2, 3],
            'Joint1_quat_y__q_aligned': [4, 5, 6],
            'Joint2_quat_x': [7, 8, 9],
            'Joint2_quat_x__q_aligned': [10, 11, 12],
            'other_column': [13, 14, 15]
        })
        
        aligned_cols = get_aligned_quaternion_columns(df)
        expected_cols = ['Joint1_quat_x__q_aligned', 'Joint1_quat_y__q_aligned', 'Joint2_quat_x__q_aligned']
        
        assert len(aligned_cols) == 3
        for col in expected_cols:
            assert col in aligned_cols
    
    def test_validate_alignment_quality(self):
        """Test alignment quality validation."""
        n_frames = 50
        time_s = np.linspace(0, 1, n_frames)
        
        # Create perfect identity quaternions
        identity_quat = np.array([0.0, 0.0, 0.0, 1.0])
        
        data = {
            'time_s': time_s,
            'TestJoint_quat_x__q_aligned': np.full(n_frames, identity_quat[0]),
            'TestJoint_quat_y__q_aligned': np.full(n_frames, identity_quat[1]),
            'TestJoint_quat_z__q_aligned': np.full(n_frames, identity_quat[2]),
            'TestJoint_quat_w__q_aligned': np.full(n_frames, identity_quat[3])
        }
        
        df = pd.DataFrame(data)
        
        metrics = validate_alignment_quality(df, 'TestJoint')
        
        assert metrics['mean_norm'] == pytest.approx(1.0, rel=1e-10)
        assert metrics['norm_std'] == pytest.approx(0.0, abs=1e-10)
        assert metrics['norm_range'] == pytest.approx(0.0, abs=1e-10)
        assert metrics['frames_with_invalid_norm'] == 0
        assert metrics['total_frames'] == n_frames


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
