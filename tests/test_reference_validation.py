"""
Tests for Reference Detection Validation Module

Tests verify that reference validation correctly:
1. Computes motion profiles
2. Validates reference window quality
3. Checks reference stability
4. Compares with ground truth
"""

import pytest
import numpy as np
from scipy.spatial.transform import Rotation as R

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from reference_validation import (
    compute_motion_profile,
    validate_reference_window,
    validate_reference_stability,
    compare_reference_with_ground_truth,
    generate_motion_profile_plot_data
)


def create_test_quaternions(n_frames, n_joints, motion_mag=0.1, seed=42):
    """Create synthetic quaternion data for testing."""
    np.random.seed(seed)
    q_local = np.zeros((n_frames, n_joints, 4))
    
    for j in range(n_joints):
        for t in range(n_frames):
            # Small random rotations
            rotvec = np.random.randn(3) * motion_mag
            q_local[t, j] = R.from_rotvec(rotvec).as_quat()
    
    return q_local


def create_static_quaternions(n_frames, n_joints):
    """Create static (no motion) quaternions."""
    q_local = np.zeros((n_frames, n_joints, 4))
    q_identity = R.identity().as_quat()
    
    for j in range(n_joints):
        for t in range(n_frames):
            q_local[t, j] = q_identity
    
    return q_local


class TestMotionProfile:
    """Test motion profile computation."""
    
    def test_motion_profile_static(self):
        """Test that static pose shows zero motion."""
        fs = 120.0
        duration = 5.0
        n_frames = int(fs * duration)
        n_joints = 10
        
        time_s = np.arange(n_frames) / fs
        q_local = create_static_quaternions(n_frames, n_joints)
        joint_indices = list(range(n_joints))
        
        profile = compute_motion_profile(time_s, q_local, joint_indices, fs)
        
        # Static should have near-zero motion
        assert np.nanmean(profile['motion_smooth']) < 0.01
        
    def test_motion_profile_moving(self):
        """Test that moving pose shows non-zero motion."""
        fs = 120.0
        duration = 5.0
        n_frames = int(fs * duration)
        n_joints = 10
        
        time_s = np.arange(n_frames) / fs
        q_local = create_test_quaternions(n_frames, n_joints, motion_mag=0.5)
        joint_indices = list(range(n_joints))
        
        profile = compute_motion_profile(time_s, q_local, joint_indices, fs)
        
        # Moving should have significant motion
        assert np.nanmean(profile['motion_smooth']) > 0.1


class TestReferenceWindowValidation:
    """Test reference window validation."""
    
    def test_good_reference_passes(self):
        """Test that a good static window passes validation."""
        fs = 120.0
        duration = 10.0
        n_frames = int(fs * duration)
        n_joints = 10
        
        time_s = np.arange(n_frames) / fs
        # Create mostly static data
        q_local = create_static_quaternions(n_frames, n_joints)
        joint_indices = list(range(n_joints))
        
        # Reference window: 1-3 seconds (static)
        ref_start, ref_end = 1.0, 3.0
        
        result = validate_reference_window(
            time_s, q_local, ref_start, ref_end, joint_indices, fs,
            strict_thresholds=True
        )
        
        assert result['status'] == 'PASS'
        assert result['mean_motion_rad_s'] < 0.3
        assert result['duration_sec'] >= 1.0
        
    def test_poor_reference_fails(self):
        """Test that a moving window fails validation."""
        fs = 120.0
        duration = 10.0
        n_frames = int(fs * duration)
        n_joints = 10
        
        time_s = np.arange(n_frames) / fs
        # Create moving data
        q_local = create_test_quaternions(n_frames, n_joints, motion_mag=1.0)
        joint_indices = list(range(n_joints))
        
        # Reference window: 1-3 seconds (but moving)
        ref_start, ref_end = 1.0, 3.0
        
        result = validate_reference_window(
            time_s, q_local, ref_start, ref_end, joint_indices, fs,
            strict_thresholds=True
        )
        
        assert result['status'] in ['FAIL', 'WARN_MOTION']
        assert result['mean_motion_rad_s'] > 0.5
        
    def test_short_window_warning(self):
        """Test that short window gets warning."""
        fs = 120.0
        duration = 10.0
        n_frames = int(fs * duration)
        n_joints = 10
        
        time_s = np.arange(n_frames) / fs
        q_local = create_static_quaternions(n_frames, n_joints)
        joint_indices = list(range(n_joints))
        
        # Very short window (0.5 seconds)
        ref_start, ref_end = 1.0, 1.5
        
        result = validate_reference_window(
            time_s, q_local, ref_start, ref_end, joint_indices, fs,
            strict_thresholds=True
        )
        
        # Should warn about short duration
        assert result['duration_sec'] < 1.0


class TestReferenceStability:
    """Test reference stability validation."""
    
    def test_stable_reference(self):
        """Test stability metrics for a good reference."""
        n_frames = 600  # 5 seconds @ 120 Hz
        n_joints = 10
        fs = 120.0
        
        time_s = np.arange(n_frames) / fs
        q_local = create_static_quaternions(n_frames, n_joints)
        
        # Create reference quaternions (identity)
        q_ref = np.zeros((n_joints, 4))
        q_identity = R.identity().as_quat()
        for j in range(n_joints):
            q_ref[j] = q_identity
        
        joint_indices = list(range(n_joints))
        
        result = validate_reference_stability(
            q_ref, q_local, 1.0, 3.0, time_s, joint_indices
        )
        
        # Static data should have very low identity error
        assert result['identity_error_mean_rad'] < 0.1
        assert result['reference_std_mean_rad'] < 0.05
        assert result['n_joints_validated'] == n_joints


class TestGroundTruthComparison:
    """Test ground truth comparison."""
    
    def test_identical_references(self):
        """Test that identical references show zero error."""
        n_joints = 10
        
        # Create identical reference quaternions
        q_ref = np.zeros((n_joints, 4))
        q_identity = R.identity().as_quat()
        for j in range(n_joints):
            q_ref[j] = q_identity
        
        q_ground_truth = q_ref.copy()
        joint_indices = list(range(n_joints))
        
        result = compare_reference_with_ground_truth(
            q_ref, q_ground_truth, joint_indices
        )
        
        assert result['status'] == 'EXCELLENT'
        assert result['mean_error_deg'] < 1.0
        
    def test_different_references(self):
        """Test that different references show error."""
        n_joints = 10
        
        # Create different references (10 degree rotation)
        q_ref = np.zeros((n_joints, 4))
        q_ground_truth = np.zeros((n_joints, 4))
        
        for j in range(n_joints):
            q_ref[j] = R.identity().as_quat()
            # Rotate by 15 degrees around Y axis
            q_ground_truth[j] = R.from_euler('y', 15, degrees=True).as_quat()
        
        joint_indices = list(range(n_joints))
        
        result = compare_reference_with_ground_truth(
            q_ref, q_ground_truth, joint_indices
        )
        
        # Should detect ~15 degree error
        assert result['mean_error_deg'] > 10.0
        assert result['status'] in ['ACCEPTABLE', 'POOR']


class TestMotionProfilePlotData:
    """Test plot data generation."""
    
    def test_plot_data_generation(self):
        """Test that plot data is generated correctly."""
        fs = 120.0
        duration = 10.0
        n_frames = int(fs * duration)
        n_joints = 10
        
        time_s = np.arange(n_frames) / fs
        q_local = create_static_quaternions(n_frames, n_joints)
        joint_indices = list(range(n_joints))
        
        profile = compute_motion_profile(time_s, q_local, joint_indices, fs)
        
        plot_data = generate_motion_profile_plot_data(
            profile, ref_start=1.0, ref_end=3.0, search_window_sec=5.0
        )
        
        assert 'time' in plot_data
        assert 'motion_smooth' in plot_data
        assert 'reference_window' in plot_data
        assert plot_data['reference_window']['start'] == 1.0
        assert plot_data['reference_window']['end'] == 3.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
