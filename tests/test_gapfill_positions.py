#!/usr/bin/env python3
"""
Tests for gap filling module (src/gapfill_positions.py).
"""

import pytest
import numpy as np
import pandas as pd
from gapfill_positions import gap_fill_positions, find_contiguous_runs


class TestGapAnalysis:
    """Test gap analysis functions."""
    
    def test_find_contiguous_runs(self):
        """Test finding of contiguous valid runs."""
        # Create test data with known runs
        time_s = np.linspace(0, 1.0, 11)
        df = pd.DataFrame({
            'time_s': time_s,
            'test__px': [0, 1, 2, 3, np.nan, 5, 6, 7],
            'test__py': [0, 1, 2, 3, np.nan, 5, 6, 7],
            'test__pz': [0, 1, 2, 3, np.nan, 5, 6, 7],
        })
        
        runs = find_contiguous_runs(df, time_s, min_run_length=3)
        
        # Should find two runs: (0,3) and (5,10)
        assert len(runs) == 2
        assert (0, 3) in runs
        assert (5, 10) in runs
    
    def test_gap_duration_calculation(self):
        """Test gap duration calculation."""
        time_s = np.array([0.0, 0.1, 0.2, 0.3])
        
        # Gap from index 1 to 2: duration = 0.1s
        gap_1_2 = 0.2 - 0.1
        
        # Test the calculation
        gap_duration = time_s[2] - time_s[1]
        
        assert np.isclose(gap_duration, gap_1_2, atol=1e-6)
    
    def test_max_gap_enforcement(self):
        """Test that gaps larger than max_gap_s are not filled."""
        # Create data with 0.05s gap (should fill) and 0.2s gap (should not fill)
        time_s = np.linspace(0, 1.0, 6)
        df = pd.DataFrame({
            'time_s': time_s,
            'test__px': [0, 1, 2, 3, np.nan, 4, 5],
            'test__py': [0, 1, 2, 3, np.nan, 4, 5],
            'test__pz': [0, 1, 2, 3, np.nan, 4, 5],
        })
        
        df_filled = gap_fill_positions(df, time_s, max_gap_s=0.1)
        
        # 0.05s gap should be filled
        assert not np.isnan(df_filled.loc[1, 'test__px'])
        
        # 0.2s gap should remain NaN
        assert np.isnan(df_filled.loc[4, 'test__px'])
    
    def test_boundary_protection(self):
        """Test that gaps at boundaries remain NaN."""
        # Create data with gap at start
        time_s = np.linspace(0, 1.0, 6)
        df = pd.DataFrame({
            'time_s': time_s,
            'test__px': [np.nan, 1, 2, 3, 4, 5],  # Gap at start
            'test__py': [np.nan, 1, 2, 3, 4, 5],
            'test__pz': [np.nan, 1, 2, 3, 4, 5],
        })
        
        df_filled = gap_fill_positions(df, time_s, max_gap_s=0.1)
        
        # Gap at start should remain NaN
        assert np.isnan(df_filled.loc[0, 'test__px'])
        
        # Gap at end should be filled
        assert not np.isnan(df_filled.loc[5, 'test__px'])


class TestBoundedSplineInterpolation:
    """Test bounded cubic spline interpolation."""
    
    def test_interpolation_accuracy(self):
        """Test that interpolation is accurate."""
        # Test data: parabolic curve
        time_s = np.linspace(0, 1.0, 5)
        data = np.array([0, 1, 4, 9, 16, 25, 36, 49, 64, 81, 100])
        
        # Remove middle point for interpolation
        data_with_gap = data.copy()
        data_with_gap[2] = np.nan
        
        filled = gap_fill_positions.bounded_spline_interpolation(time_s, data_with_gap, max_gap_s=1.0)
        
        # Interpolated value should be close to expected (13)
        assert np.isclose(filled[2], 13.0, atol=0.1)
        
        # Other points should remain unchanged
        for i in [0, 1, 3, 4]:
            if i != 2:
                assert np.isclose(filled[i], data[i], atol=1e-6)
    
    def test_neighbor_requirement(self):
        """Test that interpolation requires neighbors on both sides."""
        # Test data with single valid point surrounded by NaN
        time_s = np.array([0.0, 1.0, 3])
        data = np.array([np.nan, np.nan, np.nan, 1.0, np.nan, np.nan])
        
        filled = gap_fill_positions.bounded_spline_interpolation(time_s, data, max_gap_s=1.0)
        
        # Single point should remain NaN (no neighbors for interpolation)
        assert np.isnan(filled[3])


class TestGapFilling:
    """Test end-to-end gap filling pipeline."""
    
    def test_parabolic_trajectory(self):
        """Test filling of parabolic trajectory."""
        # Create parabolic trajectory: y = x^2
        time_s = np.linspace(0, 1.0, 11)
        df = pd.DataFrame({
            'time_s': time_s,
            'test__px': np.linspace(0, 10, 100, 11),
            'test__py': np.linspace(0, 10, 100, 11),
            'test__pz': np.linspace(0, 10, 100, 11),
        })
        
        # Remove middle point
        df_with_gap = df.copy()
        df_with_gap.loc[5, 'test__px'] = np.nan
        
        df_filled = gap_fill_positions(df, time_s, max_gap_s=0.5)
        
        # Gap should be filled with accurate parabolic interpolation
        filled_x = df_filled['test__px'].values
        expected_x = np.linspace(0, 10, 100, 11)
        expected_x[5] = 25.0  # Expected value at missing point
        
        assert np.isclose(filled_x[5], expected_x, atol=0.5)
        
        # Other points should remain unchanged
        for i in [0, 1, 2, 3, 4, 6, 7, 8, 9, 10]:
            if i != 5:
                assert np.isclose(filled_x[i], expected_x[i], atol=0.1)
    
    def test_mixed_gap_sizes(self):
        """Test handling of mixed gap sizes."""
        # Create data with gaps of different sizes
        time_s = np.linspace(0, 1.0, 11)
        df = pd.DataFrame({
            'time_s': time_s,
            'test__px': [0, 1, 2, 3, np.nan, 5, 6, 7, 8, 9, 10],
            'test__py': [0, 1, 2, 3, np.nan, 5, 6, 7, 8, 9, 10],
        })
        
        df_filled = gap_fill_positions(df, time_s, max_gap_s=0.1)
        
        # Small gaps (0.1s) should be filled
        assert not np.isnan(df_filled.loc[1, 'test__px'])
        assert not np.isnan(df_filled.loc[2, 'test__px'])
        
        # Large gap (0.5s) should remain NaN
        assert np.isnan(df_filled.loc[3, 'test__px'])


if __name__ == "__main__":
    pytest.main([__file__])
