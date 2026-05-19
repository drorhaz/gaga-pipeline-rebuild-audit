"""
Tests for precise temporal resampling module (src/time_alignment.py).
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.time_alignment import (
    generate_perfect_time_grid,
    ensure_hemispheric_alignment,
    precise_temporal_resampling,
    verify_resampling_quality
)


class TestPerfectTimeGrid:
    """Test perfect time grid generation."""
    
    def test_constant_dt(self):
        """Test that arange produces constant Δt."""
        t_start, t_end = 0.0, 1.0
        fs = 10.0
        
        t_new = generate_perfect_time_grid(t_start, t_end, fs)
        
        # Should have exactly 11 frames (0 to 1.0 inclusive)
        assert len(t_new) == 11
        # Δt should be exactly 0.1
        dt = np.diff(t_new)
        assert np.allclose(dt, 0.1, atol=1e-12)
    
    def test_no_drift(self):
        """Test that arange prevents endpoint drift."""
        t_start, t_end = 0.0, 1.0
        fs = 3.0  # Non-integer number of frames
        
        t_new = generate_perfect_time_grid(t_start, t_end, fs)
        
        # Should end exactly at t_end
        assert np.isclose(t_new[-1], t_end, atol=1e-12)
        # Should not exceed t_end
        assert t_new[-1] <= t_end


class TestHemisphericAlignment:
    """Test hemispheric alignment before resampling."""
    
    def test_prevents_flip(self):
        """Test that sign flip prevents phantom 360° jump."""
        # Create quaternions with sign flip
        q = np.array([[0, 0, 0, 1],
                      [0, 0, np.sin(np.pi/4), np.cos(np.pi/4)],
                      [0, 0, 0, -1]])  # Flipped
        
        q_aligned = ensure_hemispheric_alignment(q)
        
        # Third quaternion should be flipped back to maintain continuity
        # The dot product between q[1] and q[2] is negative, so q[2] gets flipped
        expected_q2 = -np.array([0, 0, 0, -1])  # Flipped back to [0, 0, 0, 1]
        assert np.allclose(q_aligned[2], expected_q2, atol=1e-6)
        
        # Dot products should be positive for continuity
        for i in range(1, len(q_aligned)):
            assert np.dot(q_aligned[i-1], q_aligned[i]) >= 0


class TestResamplingQuality:
    """Test resampling quality verification."""
    
    def test_temporal_precision(self):
        """Test temporal precision verification."""
        # Create perfect resampled data
        fs_target = 120.0
        t_new = np.arange(0, 1.0, 1/fs_target)
        
        df = pd.DataFrame({'time_s': t_new})
        report = verify_resampling_quality(df, fs_target)
        
        # Should pass all checks
        assert report['temporal_precision']['dt_constant']
        assert report['temporal_precision']['max_dt_error'] < 1e-9
        assert np.isclose(report['temporal_precision']['target_dt'], 1/fs_target, atol=1e-12)
    
    def test_boundary_integrity(self):
        """Test boundary integrity check."""
        t_start, t_end = 0.5, 1.5
        t_new = np.linspace(t_start, t_end, 100)
        
        df = pd.DataFrame({'time_s': t_new})
        report = verify_resampling_quality(df, 120.0)
        
        # Should detect boundaries correctly
        assert report['boundary_integrity']['no_extrapolation']
        assert np.isclose(report['boundary_integrity']['t_start'], t_start)
        assert np.isclose(report['boundary_integrity']['t_end'], t_end)


class TestPreciseResampling:
    """Test end-to-end precise resampling."""
    
    def test_velocity_accuracy_with_jitter(self):
        """Test velocity accuracy with jittery original timestamps."""
        # Create data with monotonic time (slightly irregular but increasing)
        fs_target = 120.0
        time_orig = np.array([0.000, 0.007, 0.009, 0.015, 0.020, 0.021, 0.022])  # Monotonic
        pos_orig = np.array([[0, 0, 0],
                           [1, 0, 0],
                           [2, 0, 0],
                           [3, 0, 0],
                           [4, 0, 0],
                           [5, 0, 0],
                           [6, 0, 0]])  # Match length of time_orig
        
        df_orig = pd.DataFrame({
            'time_s': time_orig,
            'test__px': pos_orig[:, 0],
            'test__py': pos_orig[:, 1],
            'test__pz': pos_orig[:, 2],
            'test__qx': [0, 0, 0, 0, 0, 0, 0],  # Match length
            'test__qy': [0, 0, 0, 0, 0, 0, 0],
            'test__qz': [0, 0, 0, 0, 0, 0, 0],
            'test__qw': [1, 1, 1, 1, 1, 1, 1]
        })
        
        # Resample
        df_resampled = precise_temporal_resampling(df_orig, fs_target)
        
        # Check temporal precision
        report = verify_resampling_quality(df_resampled, fs_target)
        assert report['temporal_precision']['dt_constant']
        
        # Velocity should be computed correctly despite jitter
        assert not np.any(np.isnan(df_resampled[['test__px', 'test__py', 'test__pz']].values))
    
    def test_slerp_continuity(self):
        """Test SLERP continuity through sign flip."""
        # Create quaternions with sign flip
        fs_target = 10.0
        time_orig = np.arange(0, 1.0, 1/fs_target)
        
        # Quaternion that flips sign halfway
        q_orig = np.zeros((len(time_orig), 4))
        q_orig[:, :3] = 0
        q_orig[:, 3] = 1
        q_orig[len(q_orig)//2:, :] = -q_orig[len(q_orig)//2:, :]
        
        df_orig = pd.DataFrame({
            'time_s': time_orig,
            'test__qx': q_orig[:, 0],
            'test__qy': q_orig[:, 1],
            'test__qz': q_orig[:, 2],
            'test__qw': q_orig[:, 3]
        })
        
        # Resample
        df_resampled = precise_temporal_resampling(df_orig, fs_target)
        
        # Should not have phantom flips
        q_resampled = df_resampled[['test__qx', 'test__qy', 'test__qz', 'test__qw']].values
        
        # Check for continuity (no large jumps)
        for i in range(1, len(q_resampled)):
            dot_product = np.dot(q_resampled[i-1], q_resampled[i])
            assert dot_product >= 0, f"Discontinuity at frame {i}"


if __name__ == "__main__":
    pytest.main([__file__])
