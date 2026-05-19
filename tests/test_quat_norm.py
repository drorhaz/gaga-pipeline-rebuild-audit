"""
Tests for quaternion normalization utilities in src/quaternions.py.
"""

import pytest
import numpy as np
import pandas as pd
import warnings
from src.quaternions import (
    renormalize_quat_block,
    renormalize_quat_cols,
    renormalize_all_quat_cols,
    get_all_quaternion_joints
)


class TestRenormalizeQuatBlock:
    """Test renormalize_quat_block function."""
    
    def test_basic_normalization(self):
        """Test basic quaternion normalization."""
        # Create a "dirty" quaternion with norm != 1
        Q = np.array([[0, 0, 0.7, 0.7]])  # norm = 0.9899
        
        Q_norm = renormalize_quat_block(Q)
        
        # Check that the output is normalized
        norm = np.linalg.norm(Q_norm[0])
        assert np.isclose(norm, 1.0, atol=1e-6), f"Expected norm 1.0, got {norm}"
        
        # Check that the direction is preserved
        expected = np.array([0, 0, 0.7071, 0.7071])  # approximately
        assert np.allclose(Q_norm[0], expected, atol=1e-4), f"Expected {expected}, got {Q_norm[0]}"
    
    def test_multiple_quaternions(self):
        """Test normalization of multiple quaternions."""
        Q = np.array([
            [1, 0, 0, 0],      # norm = 1 (already normalized)
            [0, 2, 0, 0],      # norm = 2
            [0, 0, 3, 4],      # norm = 5
            [0.5, 0.5, 0.5, 0.5]  # norm = 1.0
        ])
        
        Q_norm = renormalize_quat_block(Q)
        
        # Check that all rows are normalized
        for i in range(Q_norm.shape[0]):
            norm = np.linalg.norm(Q_norm[i])
            assert np.isclose(norm, 1.0, atol=1e-6), f"Row {i} not normalized: norm = {norm}"
    
    def test_zero_norm_handling(self):
        """Test handling of zero norm quaternions."""
        Q = np.array([
            [0, 0, 0, 0],      # zero norm
            [1, 0, 0, 0]       # normal
        ])
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Q_norm = renormalize_quat_block(Q)
            
            # Check that warning was issued
            assert len(w) > 0
            assert any("zero_norm" in str(warning.message) for warning in w)
            
            # Check that zero norm row remains NaN
            assert np.all(np.isnan(Q_norm[0])), "Zero norm row should be NaN"
            
            # Check that normal row is normalized
            norm = np.linalg.norm(Q_norm[1])
            assert np.isclose(norm, 1.0, atol=1e-6), "Normal row should be normalized"
    
    def test_nan_handling(self):
        """Test handling of NaN values."""
        Q = np.array([
            [np.nan, 0, 0, 1],     # NaN in input
            [0, np.nan, 0, 1],     # NaN in input
            [0, 0, np.nan, 1],     # NaN in input
            [0, 0, 0, np.nan],     # NaN in input
            [1, 0, 0, 0]           # normal
        ])
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Q_norm = renormalize_quat_block(Q)
            
            # Check that warning was issued
            assert len(w) > 0
            assert any("nan_input" in str(warning.message) for warning in w)
            
            # Check that NaN rows remain NaN
            for i in range(4):
                assert np.all(np.isnan(Q_norm[i])), f"Row {i} with NaN should remain NaN"
            
            # Check that normal row is normalized
            norm = np.linalg.norm(Q_norm[4])
            assert np.isclose(norm, 1.0, atol=1e-6), "Normal row should be normalized"
    
    def test_input_validation(self):
        """Test input validation."""
        # Test wrong shape
        with pytest.raises(ValueError, match="Input must be an N x 4 array"):
            renormalize_quat_block(np.array([1, 2, 3]))  # 1D
        
        with pytest.raises(ValueError, match="Input must be an N x 4 array"):
            renormalize_quat_block(np.array([[1, 2, 3]]))  # 1 x 3
        
        with pytest.raises(ValueError, match="Input must be an N x 4 array"):
            renormalize_quat_block(np.array([[1, 2, 3, 4, 5]]))  # 1 x 5


class TestRenormalizeQuatCols:
    """Test renormalize_quat_cols function."""
    
    def test_single_joint(self):
        """Test normalization of a single joint."""
        df = pd.DataFrame({
            'time_s': [0, 1, 2],
            'Hips__qx': [0, 0, 0],
            'Hips__qy': [0, 0, 0],
            'Hips__qz': [0.7, 0.7, 0.7],
            'Hips__qw': [0.7, 0.7, 0.7],
            'Spine__px': [1, 2, 3]
        })
        
        df_norm = renormalize_quat_cols(df, ['Hips'])
        
        # Check that Hips quaternion is normalized
        for i in range(len(df_norm)):
            quat = df_norm[['Hips__qx', 'Hips__qy', 'Hips__qz', 'Hips__qw']].iloc[i].values
            norm = np.linalg.norm(quat)
            assert np.isclose(norm, 1.0, atol=1e-6), f"Row {i} not normalized"
        
        # Check that other columns are unchanged
        assert np.array_equal(df_norm['time_s'], df['time_s'])
        assert np.array_equal(df_norm['Spine__px'], df['Spine__px'])
    
    def test_multiple_joints(self):
        """Test normalization of multiple joints."""
        df = pd.DataFrame({
            'time_s': [0, 1],
            'Hips__qx': [0, 0],
            'Hips__qy': [0, 0],
            'Hips__qz': [0.7, 0.7],
            'Hips__qw': [0.7, 0.7],
            'Spine__qx': [0, 0],
            'Spine__qy': [0, 0],
            'Spine__qz': [3, 3],
            'Spine__qw': [4, 4]
        })
        
        df_norm = renormalize_quat_cols(df, ['Hips', 'Spine'])
        
        # Check that both joints are normalized
        for joint in ['Hips', 'Spine']:
            for i in range(len(df_norm)):
                quat = df_norm[[f'{joint}__qx', f'{joint}__qy', f'{joint}__qz', f'{joint}__qw']].iloc[i].values
                norm = np.linalg.norm(quat)
                assert np.isclose(norm, 1.0, atol=1e-6), f"{joint} row {i} not normalized"
    
    def test_missing_columns_warning(self):
        """Test warning for missing quaternion columns."""
        df = pd.DataFrame({
            'time_s': [0, 1],
            'Hips__qx': [0, 0],
            'Hips__qy': [0, 0],
            # Missing Hips__qz and Hips__qw
            'Spine__qx': [0, 0],
            'Spine__qy': [0, 0],
            'Spine__qz': [0, 0],
            'Spine__qw': [1, 1]
        })
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            df_norm = renormalize_quat_cols(df, ['Hips', 'Spine'])
            
            # Check that warning was issued for Hips
            assert len(w) > 0
            assert any("Hips" in str(warning.message) and "missing columns" in str(warning.message) for warning in w)
            
            # Check that Spine was processed
            for i in range(len(df_norm)):
                quat = df_norm[['Spine__qx', 'Spine__qy', 'Spine__qz', 'Spine__qw']].iloc[i].values
                norm = np.linalg.norm(quat)
                assert np.isclose(norm, 1.0, atol=1e-6), f"Spine row {i} should be normalized"


class TestGetAllQuaternionJoints:
    """Test get_all_quaternion_joints function."""
    
    def test_complete_joints(self):
        """Test extraction of joints with complete quaternion data."""
        df = pd.DataFrame({
            'time_s': [0, 1],
            'Hips__qx': [0, 0],
            'Hips__qy': [0, 0],
            'Hips__qz': [0, 0],
            'Hips__qw': [1, 1],
            'Spine__qx': [0, 0],
            'Spine__qy': [0, 0],
            'Spine__qz': [0, 0],
            'Spine__qw': [1, 1],
            'LeftArm__qx': [0, 0],  # Missing other components
            'LeftArm__px': [1, 2]
        })
        
        joints = get_all_quaternion_joints(df)
        
        # Should only return complete joints
        assert 'Hips' in joints
        assert 'Spine' in joints
        assert 'LeftArm' not in joints
        assert len(joints) == 2
    
    def test_no_quaternion_data(self):
        """Test when no quaternion data is present."""
        df = pd.DataFrame({
            'time_s': [0, 1],
            'Hips__px': [0, 0],
            'Hips__py': [0, 0],
            'Hips__pz': [0, 0]
        })
        
        joints = get_all_quaternion_joints(df)
        assert len(joints) == 0


class TestRenormalizeAllQuatCols:
    """Test renormalize_all_quat_cols function."""
    
    def test_normalize_all_joints(self):
        """Test normalization of all quaternion columns."""
        df = pd.DataFrame({
            'time_s': [0, 1],
            'Hips__qx': [0, 0],
            'Hips__qy': [0, 0],
            'Hips__qz': [0.7, 0.7],
            'Hips__qw': [0.7, 0.7],
            'Spine__qx': [0, 0],
            'Spine__qy': [0, 0],
            'Spine__qz': [3, 3],
            'Spine__qw': [4, 4],
            'LeftArm__px': [1, 2]  # Non-quaternion column
        })
        
        df_norm = renormalize_all_quat_cols(df)
        
        # Check that all quaternion joints are normalized
        for joint in ['Hips', 'Spine']:
            for i in range(len(df_norm)):
                quat = df_norm[[f'{joint}__qx', f'{joint}__qy', f'{joint}__qz', f'{joint}__qw']].iloc[i].values
                norm = np.linalg.norm(quat)
                assert np.isclose(norm, 1.0, atol=1e-6), f"{joint} row {i} not normalized"
        
        # Check that non-quaternion columns are unchanged
        assert np.array_equal(df_norm['time_s'], df['time_s'])
        assert np.array_equal(df_norm['LeftArm__px'], df['LeftArm__px'])


if __name__ == "__main__":
    pytest.main([__file__])
