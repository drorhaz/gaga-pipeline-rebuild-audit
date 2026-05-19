"""
Tests for resample_to_perfect_grid function in src/time_alignment.py.
"""

import pytest
import numpy as np
import pandas as pd
from src.time_alignment import resample_to_perfect_grid, assert_time_monotonic


class TestResampleToPerfectGrid:
    """Test resample_to_perfect_grid function."""
    
    def test_constant_dt_verification(self):
        """Test that np.diff(df_resampled['time_s']) has standard deviation near zero."""
        # Create test data with irregular sampling
        fs_target = 120.0
        time_orig = np.array([0.0, 0.008, 0.009, 0.020, 0.021, 0.030, 0.031])
        
        df_orig = pd.DataFrame({
            'time_s': time_orig,
            'test__px': np.arange(len(time_orig)),
            'test__py': np.zeros(len(time_orig)),
            'test__pz': np.zeros(len(time_orig)),
            'test__qx': [0, 0, 0, 0, 0, 0, 0],
            'test__qy': [0, 0, 0, 0, 0, 0, 0], 
            'test__qz': [0, 0, 0, 0, 0, 0, 0],
            'test__qw': [1, 1, 1, 1, 1, 1, 1]
        })
        
        # Resample
        df_resampled = resample_to_perfect_grid(df_orig, fs_target)
        
        # Check that time differences have near-zero standard deviation
        dt_values = np.diff(df_resampled['time_s'].values)
        dt_std = np.std(dt_values)
        
        # Should be very close to zero (within floating point precision)
        assert dt_std < 1e-10, f"Time step std dev {dt_std} is not near zero"
        
        # Check that all time steps are exactly equal to 1/fs_target
        expected_dt = 1.0 / fs_target
        assert np.allclose(dt_values, expected_dt, atol=1e-12), "Time steps are not constant"
    
    def test_boundary_preservation(self):
        """Test that position and quaternion values at start and end are preserved."""
        fs_target = 60.0
        n_frames = 10
        time_orig = np.linspace(0.0, 0.15, n_frames)  # 150ms duration
        
        # Create test data with known start and end values
        start_pos = [1.0, 2.0, 3.0]
        end_pos = [10.0, 20.0, 30.0]
        start_quat = [0.0, 0.0, 0.0, 1.0]
        end_quat = [0.0, 0.0, np.sin(np.pi/4), np.cos(np.pi/4)]
        
        pos_data = np.linspace(start_pos, end_pos, n_frames)
        quat_data = np.linspace(start_quat, end_quat, n_frames)
        
        df_orig = pd.DataFrame({
            'time_s': time_orig,
            'test__px': pos_data[:, 0],
            'test__py': pos_data[:, 1], 
            'test__pz': pos_data[:, 2],
            'test__qx': quat_data[:, 0],
            'test__qy': quat_data[:, 1],
            'test__qz': quat_data[:, 2],
            'test__qw': quat_data[:, 3]
        })
        
        # Resample
        df_resampled = resample_to_perfect_grid(df_orig, fs_target)
        
        # Check start values are preserved (within interpolation tolerance)
        assert np.allclose(df_resampled['test__px'].iloc[0], start_pos[0], atol=1e-6)
        assert np.allclose(df_resampled['test__py'].iloc[0], start_pos[1], atol=1e-6)
        assert np.allclose(df_resampled['test__pz'].iloc[0], start_pos[2], atol=1e-6)
        
        # Check end values are preserved (within interpolation tolerance)
        assert np.allclose(df_resampled['test__px'].iloc[-1], end_pos[0], atol=1e-6)
        assert np.allclose(df_resampled['test__py'].iloc[-1], end_pos[1], atol=1e-6)
        assert np.allclose(df_resampled['test__pz'].iloc[-1], end_pos[2], atol=1e-6)
        
        # Check quaternion start/end values
        assert np.allclose(df_resampled['test__qx'].iloc[0], start_quat[0], atol=1e-6)
        assert np.allclose(df_resampled['test__qw'].iloc[-1], end_quat[3], atol=1e-6)
    
    def test_frame_idx_metadata(self):
        """Test that frame_idx column is properly generated."""
        fs_target = 30.0
        time_orig = np.array([0.0, 0.035, 0.067, 0.101, 0.134])
        
        df_orig = pd.DataFrame({
            'time_s': time_orig,
            'test__px': np.arange(len(time_orig)),
            'test__py': np.zeros(len(time_orig)),
            'test__pz': np.zeros(len(time_orig)),
            'test__qx': [0, 0, 0, 0, 0],
            'test__qy': [0, 0, 0, 0, 0],
            'test__qz': [0, 0, 0, 0, 0], 
            'test__qw': [1, 1, 1, 1, 1]
        })
        
        # Resample
        df_resampled = resample_to_perfect_grid(df_orig, fs_target)
        
        # Check frame_idx exists and is correct
        assert 'frame_idx' in df_resampled.columns, "frame_idx column missing"
        expected_frames = len(df_resampled)
        assert np.array_equal(df_resampled['frame_idx'].values, np.arange(expected_frames)), "frame_idx values incorrect"
    
    def test_monotonic_time_assertion(self):
        """Test that non-monotonic time raises AssertionError."""
        # Create data with non-monotonic time
        time_orig = np.array([0.0, 0.010, 0.008, 0.020])  # Non-monotonic at index 2
        
        df_orig = pd.DataFrame({
            'time_s': time_orig,
            'test__px': [0, 1, 2, 3],
            'test__py': [0, 0, 0, 0],
            'test__pz': [0, 0, 0, 0],
            'test__qx': [0, 0, 0, 0],
            'test__qy': [0, 0, 0, 0],
            'test__qz': [0, 0, 0, 0],
            'test__qw': [1, 1, 1, 1]
        })
        
        # Should raise AssertionError
        with pytest.raises(AssertionError, match="Time column must be strictly monotonic increasing"):
            resample_to_perfect_grid(df_orig, 120.0)
    
    def test_nan_quaternion_error(self):
        """Test that NaN quaternion values raise ValueError."""
        fs_target = 60.0
        time_orig = np.array([0.0, 0.017, 0.033, 0.050])
        
        # Create data with NaN in quaternion
        df_orig = pd.DataFrame({
            'time_s': time_orig,
            'test__px': [0, 1, 2, 3],
            'test__py': [0, 0, 0, 0],
            'test__pz': [0, 0, 0, 0],
            'test__qx': [0, 0, np.nan, 0],  # NaN at index 2
            'test__qy': [0, 0, 0, 0],
            'test__qz': [0, 0, 0, 0],
            'test__qw': [1, 1, 1, 1]
        })
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="has NaN quaternion values"):
            resample_to_perfect_grid(df_orig, fs_target)
    
    def test_hemisphere_guard_integration(self):
        """Test hemisphere guard prevents phantom rotations during resampling."""
        fs_target = 10.0
        time_orig = np.arange(0, 1.0, 1/fs_target)
        
        # Create quaternions with sign flip in middle
        n = len(time_orig)
        quat_data = np.zeros((n, 4))
        quat_data[:, 3] = 1  # All w = 1 initially
        quat_data[n//2:, :] = -quat_data[n//2:, :]  # Flip sign in second half
        
        df_orig = pd.DataFrame({
            'time_s': time_orig,
            'test__px': np.arange(n),
            'test__py': np.zeros(n),
            'test__pz': np.zeros(n),
            'test__qx': quat_data[:, 0],
            'test__qy': quat_data[:, 1],
            'test__qz': quat_data[:, 2],
            'test__qw': quat_data[:, 3]
        })
        
        # Resample
        df_resampled = resample_to_perfect_grid(df_orig, fs_target)
        
        # Check that resampled quaternions maintain continuity
        q_resampled = df_resampled[['test__qx', 'test__qy', 'test__qz', 'test__qw']].values
        
        # Verify no large jumps (dot products should be positive)
        for i in range(1, len(q_resampled)):
            dot_product = np.dot(q_resampled[i-1], q_resampled[i])
            assert dot_product >= 0, f"Discontinuity detected at frame {i}: dot = {dot_product}"
    
    def test_perfect_grid_generation(self):
        """Test that arange-based grid generation prevents endpoint jitter."""
        fs_target = 7.0  # Non-integer divisor
        t_start, t_end = 0.0, 1.0
        
        # Create minimal test data
        df_orig = pd.DataFrame({
            'time_s': [t_start, t_end],
            'test__px': [0, 1],
            'test__py': [0, 0], 
            'test__pz': [0, 0],
            'test__qx': [0, 0],
            'test__qy': [0, 0],
            'test__qz': [0, 0],
            'test__qw': [1, 1]
        })
        
        # Resample
        df_resampled = resample_to_perfect_grid(df_orig, fs_target)
        
        # Check grid properties
        time_grid = df_resampled['time_s'].values
        dt_values = np.diff(time_grid)
        
        # All time steps should be identical
        assert np.allclose(dt_values, 1/fs_target, atol=1e-12), "Grid has jitter"
        
        # Should not exceed end time
        assert time_grid[-1] <= t_end + 1e-12, "Grid exceeds end time"
        
        # Should start exactly at t_start
        assert np.isclose(time_grid[0], t_start, atol=1e-12), "Grid start incorrect"


class TestPerfectTimeGrid:
    """Test perfect time grid generation."""
    
    def test_arange_precision(self):
        """Test that arange produces constant Δt."""
        t_start, t_end = 0.0, 1.0
        fs = 10.0
        
        from src.time_alignment import generate_perfect_time_grid
        t_new = generate_perfect_time_grid(t_start, t_end, fs)
        
        # Check that dt is constant
        dt = np.diff(t_new)
        
        assert np.allclose(dt, 0.1, atol=1e-12)
        assert len(t_new) == 11  # 0.0 to 1.0 inclusive
    
    def test_boundary_handling(self):
        """Test that boundaries are handled correctly."""
        # Test case where duration doesn't divide evenly
        t_start, t_end = 0.0, 1.0
        fs = 3.0  # 3.33 frames per second
        
        from src.time_alignment import generate_perfect_time_grid
        t_new = generate_perfect_time_grid(t_start, t_end, fs)
        
        # Should end exactly at t_end
        assert np.isclose(t_new[-1], t_end, atol=1e-12)
        assert t_new[-1] <= t_end


if __name__ == "__main__":
    pytest.main([__file__])
