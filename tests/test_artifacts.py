"""
Tests for artifact detection module (src/artifacts.py).
"""

import pytest
import numpy as np
from artifacts import (
    detect_velocity_artifacts,
    expand_artifact_mask,
    compute_true_velocity,
    apply_artifact_truncation
)


class TestVelocityArtifactDetection:
    """Test velocity-based artifact detection."""
    
    def test_detects_spike(self):
        """Test that velocity spike is detected."""
        # Create velocity with obvious spike and some normal variation
        velocity = np.array([[0.1, 0.1, 0.1],    # Normal
                           [0.1, 5.0, 0.1],    # Spike in Y
                           [0.1, 0.1, 0.1]])   # Normal
        
        mask = detect_velocity_artifacts(velocity, mad_multiplier=6.0)
        
        # Should detect spike in Y axis only
        assert not mask[0, 0]  # No spike in first frame
        assert not mask[0, 1]  # No spike in X
        assert mask[0, 2]      # Spike in Y
    
    def test_mad_scaling(self):
        """Test MAD-based threshold scaling."""
        # Create velocity with known standard deviation
        velocity = np.random.RandomState(42).normal(0, 1, (100, 3))
        
        # Add a large spike
        velocity[50, 1] = 10.0
        
        mask = detect_velocity_artifacts(velocity, mad_multiplier=6.0)
        
        # Should detect the spike
        assert mask[50, 1]


class TestMaskExpansion:
    """Test artifact mask expansion."""
    
    def test_captures_ramp(self):
        """Test that mask expansion captures ramp up/down."""
        # Create mask with single spike
        mask = np.zeros((10, 3), dtype=bool)
        mask[4, 1] = True  # Spike at frame 4, Y axis
        
        expanded = expand_artifact_mask(mask, dilation_frames=3)
        
        # Should capture frames 2-6 in Y axis (4 ± 2, but clipped at bounds)
        assert expanded[2:6, 1].all()
        # Other axes should not be affected
        assert not expanded[:, 0].any()
        assert not expanded[:, 2].any()


class TestTrueVelocity:
    """Test true velocity computation with irregular time."""
    
    def test_handles_jitter(self):
        """Test velocity computation with jittery timestamps."""
        # Create position with jittery time
        time_s = np.array([0.0, 0.007, 0.009, 0.008, 0.020])
        position = np.array([[0, 0, 0],
                           [1, 0, 0],
                           [2, 0, 0],
                           [3, 0, 0],
                           [4, 0, 0]])
        
        velocity = compute_true_velocity(position, time_s)
        
        # Should handle variable dt correctly
        assert not np.any(np.isnan(velocity))
        assert velocity.shape == (5, 3)
    
    def test_division_by_zero_guard(self):
        """Test guard against division by zero."""
        time_s = np.array([0.0, 0.0, 0.1])  # Zero dt
        position = np.array([[0, 0, 0],
                           [1, 0, 0],
                           [2, 0, 0]])
        
        velocity = compute_true_velocity(position, time_s)
        
        # First velocity should be zero (division by zero prevented)
        assert np.allclose(velocity[0], 0, atol=1e-9)
        # Later velocities should be computed normally
        assert not np.allclose(velocity[1:], 0, atol=1e-9)


class TestArtifactTruncation:
    """Test complete artifact truncation pipeline."""
    
    def test_full_pipeline(self):
        """Test end-to-end artifact truncation."""
        # Create test data with spike
        fs = 120.0
        time_s = np.arange(0, 1.0, 1/fs)
        position = np.zeros((int(fs), 3))
        position[:, 1] = np.linspace(0, 1, int(fs))  # Smooth Y
        position[60, 1] = 5.0  # Add spike
        
        # Apply truncation
        pos_clean, mask = apply_artifact_truncation(position, time_s, mad_multiplier=6.0)
        
        # Spike should be masked
        assert np.isnan(pos_clean[60, 1])
        # Other points should remain
        assert not np.isnan(pos_clean[59, 1])
        assert not np.isnan(pos_clean[61, 1])
        
        # Mask should detect spike
        assert mask[60, 1]


if __name__ == "__main__":
    pytest.main([__file__])
