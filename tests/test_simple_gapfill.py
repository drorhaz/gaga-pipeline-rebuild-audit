#!/usr/bin/env python3
"""Simple test for gap filling."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from gapfill_positions import gap_fill_positions

def test_simple():
    """Simple test without pandas complexity."""
    # Create simple test data
    time_s = np.array([0.0, 0.1, 0.2, 0.3])
    data = np.array([[0, 1, 2], [0, 1, 3, 4], [0, 1, 4]])
    
    # Create DataFrame
    df = pd.DataFrame({
        'time_s': time_s,
        'test__px': data[:, 0],
        'test__py': data[:, 1],
        'test__pz': data[:, 2]
    })
    
    # Fill gaps
    df_filled = gap_fill_positions(df, time_s, max_gap_s=0.1)
    
    # Check results
    assert not np.isnan(df_filled.loc[1, 'test__px'])
    assert np.isclose(df_filled.loc[1, 'test__px'], 2.0, atol=0.1)
    
    print("✅ Simple gap filling test passed!")

if __name__ == "__main__":
    test_simple()
