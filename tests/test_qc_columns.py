import pytest
import pandas as pd
import numpy as np
from src.qc_columns import build_pos_cols_valid


class TestBuildPosColsValid:
    """Test suite for build_pos_cols_valid function."""
    
    def test_keeps_only_nan_free_columns(self):
        """Test that only columns with zero NaNs are kept."""
        # Create test data with one column having NaNs
        df = pd.DataFrame({
            'LeftHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],
            'LeftHand__py': [1.0, 2.0, np.nan, 4.0, 5.0],  # Has 1 NaN
            'LeftHand__pz': [1.0, 2.0, 3.0, 4.0, 5.0],
            'RightHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],
            'RightHand__py': [1.0, 2.0, 3.0, 4.0, 5.0],
            'RightHand__pz': [1.0, 2.0, 3.0, 4.0, 5.0],
        })
        
        pos_cols = [col for col in df.columns if col.endswith(("__px", "__py", "__pz"))]
        pos_cols_valid, excluded_report = build_pos_cols_valid(df, pos_cols)
        
        # With joint_complete_axes=True (default), LeftHand should be completely excluded
        # because it has partial axes (py has NaNs)
        expected_valid = ['RightHand__px', 'RightHand__py', 'RightHand__pz']
        assert pos_cols_valid == expected_valid
        assert len(excluded_report['excluded_joints']) == 1
        assert excluded_report['excluded_joints'][0]['joint'] == 'LeftHand'
        assert excluded_report['excluded_joints'][0]['reason'] == 'partial_axes'
    
    def test_joint_completeness_enforcement(self):
        """Test that joints with partial axes are completely excluded."""
        # Create test data where LeftHand has px and py valid but pz has NaNs
        df = pd.DataFrame({
            'LeftHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
            'LeftHand__py': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
            'LeftHand__pz': [1.0, 2.0, np.nan, 4.0, 5.0],  # Has NaNs
            'RightHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
            'RightHand__py': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
            'RightHand__pz': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
        })
        
        pos_cols = [col for col in df.columns if col.endswith(("__px", "__py", "__pz"))]
        pos_cols_valid, excluded_report = build_pos_cols_valid(
            df, pos_cols, joint_complete_axes=True
        )
        
        # Should exclude ALL LeftHand columns due to joint completeness
        expected_valid = ['RightHand__px', 'RightHand__py', 'RightHand__pz']
        assert pos_cols_valid == expected_valid
        
        # Should have one excluded joint (LeftHand) with reason "partial_axes"
        assert len(excluded_report['excluded_joints']) == 1
        assert excluded_report['excluded_joints'][0]['joint'] == 'LeftHand'
        assert excluded_report['excluded_joints'][0]['reason'] == 'partial_axes'
        assert set(excluded_report['excluded_joints'][0]['cols']) == {
            'LeftHand__px', 'LeftHand__py', 'LeftHand__pz'
        }
    
    def test_joint_completeness_disabled(self):
        """Test that joint completeness can be disabled."""
        # Create test data where LeftHand has px and py valid but pz has NaNs
        df = pd.DataFrame({
            'LeftHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
            'LeftHand__py': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
            'LeftHand__pz': [1.0, 2.0, np.nan, 4.0, 5.0],  # Has NaNs
            'RightHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
            'RightHand__py': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
            'RightHand__pz': [1.0, 2.0, 3.0, 4.0, 5.0],  # Valid
        })
        
        pos_cols = [col for col in df.columns if col.endswith(("__px", "__py", "__pz"))]
        pos_cols_valid, excluded_report = build_pos_cols_valid(
            df, pos_cols, joint_complete_axes=False
        )
        
        # Should keep valid LeftHand columns when joint completeness is disabled
        expected_valid = ['LeftHand__px', 'LeftHand__py', 'RightHand__px', 'RightHand__py', 'RightHand__pz']
        assert pos_cols_valid == expected_valid
        
        # Should have no excluded joints when joint completeness is disabled
        assert len(excluded_report['excluded_joints']) == 0
    
    def test_strict_mode_missing_columns(self):
        """Test that strict_mode=True raises error for missing columns."""
        df = pd.DataFrame({
            'LeftHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],
            'LeftHand__py': [1.0, 2.0, 3.0, 4.0, 5.0],
        })
        
        pos_cols = ['LeftHand__px', 'LeftHand__py', 'LeftHand__pz', 'MissingCol__px']
        
        # Should raise ValueError in strict mode
        with pytest.raises(ValueError, match="Columns not found in DataFrame"):
            build_pos_cols_valid(df, pos_cols, strict_mode=True)
    
    def test_non_strict_mode_missing_columns(self):
        """Test that strict_mode=False handles missing columns gracefully."""
        df = pd.DataFrame({
            'LeftHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],
            'LeftHand__py': [1.0, 2.0, 3.0, 4.0, 5.0],
        })
        
        pos_cols = ['LeftHand__px', 'LeftHand__py', 'LeftHand__pz', 'MissingCol__px']
        
        pos_cols_valid, excluded_report = build_pos_cols_valid(
            df, pos_cols, strict_mode=False
        )
        
        # Should keep only existing valid columns
        # Note: LeftHand has only px and py, so with joint_complete_axes=True,
        # it will be excluded due to incomplete axes
        expected_valid = []  # LeftHand excluded due to missing pz axis
        assert pos_cols_valid == expected_valid
        
        # Should report missing columns
        missing_exclusions = [
            exc for exc in excluded_report['excluded_cols'] 
            if exc['reason'] == 'missing_column'
        ]
        assert len(missing_exclusions) == 2  # LeftHand__pz and MissingCol__px
        assert missing_exclusions[0]['nan_rate'] == 1.0
        assert missing_exclusions[1]['nan_rate'] == 1.0
        
        # Should also report LeftHand as excluded due to partial_axes
        joint_exclusions = [
            exc for exc in excluded_report['excluded_joints']
            if exc['reason'] == 'partial_axes'
        ]
        assert len(joint_exclusions) == 1
        assert joint_exclusions[0]['joint'] == 'LeftHand'
    
    def test_empty_pos_cols_raises_error(self):
        """Test that empty pos_cols raises ValueError."""
        df = pd.DataFrame({'col1': [1, 2, 3]})
        
        with pytest.raises(ValueError, match="pos_cols cannot be empty"):
            build_pos_cols_valid(df, [])
    
    def test_invalid_dataframe_raises_error(self):
        """Test that non-DataFrame input raises TypeError."""
        with pytest.raises(TypeError, match="df must be a pandas DataFrame"):
            build_pos_cols_valid("not_a_dataframe", ['col1'])
    
    def test_report_schema_correctness(self):
        """Test that the excluded_report has the correct schema."""
        df = pd.DataFrame({
            'LeftHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],
            'LeftHand__py': [1.0, 2.0, np.nan, 4.0, 5.0],  # Has NaNs
            'LeftHand__pz': [1.0, 2.0, 3.0, 4.0, 5.0],
        })
        
        pos_cols = [col for col in df.columns if col.endswith(("__px", "__py", "__pz"))]
        pos_cols_valid, excluded_report = build_pos_cols_valid(df, pos_cols)
        
        # Check schema
        required_keys = ["n_frames", "pos_cols_total", "pos_cols_valid", "excluded_cols", "excluded_joints"]
        assert all(key in excluded_report for key in required_keys)
        
        # Check types
        assert isinstance(excluded_report["n_frames"], int)
        assert isinstance(excluded_report["pos_cols_total"], int)
        assert isinstance(excluded_report["pos_cols_valid"], int)
        assert isinstance(excluded_report["excluded_cols"], list)
        assert isinstance(excluded_report["excluded_joints"], list)
        
        # Check excluded_col schema
        if excluded_report["excluded_cols"]:
            col_exclusion = excluded_report["excluded_cols"][0]
            required_col_keys = ["col", "joint", "nan_count", "nan_rate", "reason"]
            assert all(key in col_exclusion for key in required_col_keys)
        
        # Check excluded_joint schema
        if excluded_report["excluded_joints"]:
            joint_exclusion = excluded_report["excluded_joints"][0]
            required_joint_keys = ["joint", "reason", "cols", "max_nan_rate"]
            assert all(key in joint_exclusion for key in required_joint_keys)
    
    def test_all_columns_valid(self):
        """Test behavior when all columns are valid."""
        df = pd.DataFrame({
            'LeftHand__px': [1.0, 2.0, 3.0, 4.0, 5.0],
            'LeftHand__py': [1.0, 2.0, 3.0, 4.0, 5.0],
            'LeftHand__pz': [1.0, 2.0, 3.0, 4.0, 5.0],
        })
        
        pos_cols = [col for col in df.columns if col.endswith(("__px", "__py", "__pz"))]
        pos_cols_valid, excluded_report = build_pos_cols_valid(df, pos_cols)
        
        # Should keep all columns
        assert pos_cols_valid == pos_cols
        assert excluded_report["pos_cols_valid"] == 3
        assert len(excluded_report["excluded_cols"]) == 0
        assert len(excluded_report["excluded_joints"]) == 0
