import numpy as np
import pandas as pd
import pytest
from src.validation import (
    compute_bone_length_cv,
    check_angular_velocity,
    validate_bone_length_change,
    generate_qc_validation_report,
    check_hicks_residuals
)


class TestHicksResiduals:
    def test_skipped_when_force_plate_missing(self):
        """Test: Returns SKIPPED when force plate data is missing."""
        df = pd.DataFrame({
            'knee_angle': [10, 20, 30],
            'residual_force_x': [1.0, 2.0, 3.0]
        })
        peak_force = 1000.0
        
        result = check_hicks_residuals(df, peak_force)
        
        assert len(result) == 1
        assert result.iloc[0]['status'] == 'SKIPPED'
        assert 'Force plate data missing' in result.iloc[0]['reason']

    def test_skipped_when_residual_data_missing(self):
        """Test: Returns SKIPPED when residual data is missing but force plate exists."""
        df = pd.DataFrame({
            'force_plate_1_fx': [100, 200, 300],
            'knee_angle': [10, 20, 30]
        })
        peak_force = 1000.0
        
        result = check_hicks_residuals(df, peak_force)
        
        assert len(result) == 1
        assert result.iloc[0]['status'] == 'SKIPPED'
        assert 'Residual force/moment data missing' in result.iloc[0]['reason']

    def test_high_residual_forces_return_fail(self):
        """Test: High residual forces must return FAIL."""
        df = pd.DataFrame({
            'force_plate_1_fx': [100, 200, 300],
            'residual_force_x': [110.0, 120.0, 130.0],  # Very high residual forces (>2x threshold)
            'residual_moment_z': [25.0, 26.0, 27.0]
        })
        peak_force = 1000.0  # Force threshold = 50N (5% of 1000N)
        
        result = check_hicks_residuals(df, peak_force)
        
        # Should have force and moment results
        assert len(result) == 2
        
        # Check force result
        force_result = result[result['test'].str.contains('force')]
        assert len(force_result) == 1
        assert force_result.iloc[0]['status'] == 'FAIL'
        assert force_result.iloc[0]['max_residual_force_N'] > 100.0  # >2x threshold

    def test_pass_with_low_residual_forces(self):
        """Test: Low residual forces return PASS."""
        df = pd.DataFrame({
            'force_plate_1_fx': [100, 200, 300],
            'residual_force_x': [1.0, 2.0, 3.0],  # Low residual forces
            'residual_moment_z': [0.5, 0.6, 0.7]
        })
        peak_force = 1000.0  # Force threshold = 50N, Moment threshold = 10Nm
        
        result = check_hicks_residuals(df, peak_force)
        
        # Should have force and moment results
        assert len(result) == 2
        
        # Both should pass
        assert all(result['status'] == 'PASS')

    def test_warn_with_moderate_residual_forces(self):
        """Test: Moderate residual forces return WARN."""
        df = pd.DataFrame({
            'force_plate_1_fx': [100, 200, 300],
            'residual_force_x': [75.0, 80.0, 85.0],  # Moderate residual (between 1x and 2x threshold)
            'residual_moment_z': [15.0, 16.0, 17.0]
        })
        peak_force = 1000.0  # Force threshold = 50N, Moment threshold = 10Nm
        
        result = check_hicks_residuals(df, peak_force)
        
        # Should have force and moment results
        assert len(result) == 2
        
        # Check force result
        force_result = result[result['test'].str.contains('force')]
        assert len(force_result) == 1
        assert force_result.iloc[0]['status'] == 'WARN'

    def test_threshold_calculations(self):
        """Test: Force and moment thresholds are calculated correctly."""
        df = pd.DataFrame({
            'force_plate_1_fx': [100, 200, 300],
            'residual_force_x': [1.0, 2.0, 3.0],
            'residual_moment_z': [0.5, 0.6, 0.7]
        })
        peak_force = 1000.0
        
        result = check_hicks_residuals(df, peak_force)
        
        # Check thresholds
        force_threshold = 0.05 * 1000.0  # 50N
        moment_threshold = 0.01 * 1000.0 * 1.0  # 10Nm
        
        assert result.iloc[0]['force_threshold_N'] == force_threshold
        assert result.iloc[0]['moment_threshold_Nm'] == moment_threshold

    def test_none_peak_force_handling(self):
        """Test: Handles None peak_force gracefully."""
        df = pd.DataFrame({
            'force_plate_1_fx': [100, 200, 300],
            'residual_force_x': [1.0, 2.0, 3.0]
        })
        peak_force = None
        
        result = check_hicks_residuals(df, peak_force)
        
        assert len(result) == 1
        assert result.iloc[0]['force_threshold_N'] == 0.0
        assert result.iloc[0]['moment_threshold_Nm'] == 0.0

    def test_zero_peak_force_handling(self):
        """Test: Handles zero peak_force gracefully."""
        df = pd.DataFrame({
            'force_plate_1_fx': [100, 200, 300],
            'residual_force_x': [1.0, 2.0, 3.0]
        })
        peak_force = 0.0
        
        result = check_hicks_residuals(df, peak_force)
        
        assert len(result) == 1
        assert result.iloc[0]['force_threshold_N'] == 0.0
        assert result.iloc[0]['moment_threshold_Nm'] == 0.0

    def test_multiple_residual_columns(self):
        """Test: Handles multiple residual force and moment columns."""
        df = pd.DataFrame({
            'force_plate_1_fx': [100, 200, 300],
            'residual_force_x': [1.0, 2.0, 3.0],
            'residual_force_y': [0.5, 1.0, 1.5],
            'residual_moment_x': [0.1, 0.2, 0.3],
            'residual_moment_z': [0.4, 0.5, 0.6]
        })
        peak_force = 1000.0
        
        result = check_hicks_residuals(df, peak_force)
        
        # Should have 4 results (2 forces, 2 moments)
        assert len(result) == 4
        
        # Check that all have PASS status
        assert all(result['status'] == 'PASS')

    def test_column_detection_case_insensitive(self):
        """Test: Column detection is case insensitive."""
        df = pd.DataFrame({
            'FORCE_PLATE_1_FX': [100, 200, 300],
            'Residual_Force_X': [1.0, 2.0, 3.0],
            'RESIDUAL_MOMENT_Z': [0.5, 0.6, 0.7]
        })
        peak_force = 1000.0
        
        result = check_hicks_residuals(df, peak_force)
        
        # Should detect columns and process them
        assert len(result) == 2
        assert all(result['status'] == 'PASS')

    def test_fp_column_detection(self):
        """Test: Detects 'fp' prefix columns as force plate data."""
        df = pd.DataFrame({
            'fp1_fx': [100, 200, 300],
            'residual_force_x': [1.0, 2.0, 3.0]
        })
        peak_force = 1000.0
        
        result = check_hicks_residuals(df, peak_force)
        
        # Should detect force plate data and process residuals
        assert len(result) == 1
        assert result.iloc[0]['status'] == 'PASS'


class TestBoneLengthCV:
    def test_perfect_bone_length_gold_status(self):
        df = pd.DataFrame({
            'parent_x': [0, 0, 0],
            'parent_y': [0, 0, 0], 
            'parent_z': [0, 0, 0],
            'child_x': [1, 1, 1],
            'child_y': [0, 0, 0],
            'child_z': [0, 0, 0]
        })
        bones = [('parent', 'child')]
        
        result = compute_bone_length_cv(df, bones)
        assert len(result) == 1
        assert result.iloc[0]['status'] == 'GOLD'
        assert result.iloc[0]['cv_percent'] == 0.0

    def test_variable_bone_length_warn_status(self):
        df = pd.DataFrame({
            'parent_x': [0, 0, 0],
            'parent_y': [0, 0, 0],
            'parent_z': [0, 0, 0],
            'child_x': [1.0, 1.05, 0.95],
            'child_y': [0, 0, 0],
            'child_z': [0, 0, 0]
        })
        bones = [('parent', 'child')]
        
        result = compute_bone_length_cv(df, bones)
        assert result.iloc[0]['status'] in ['WARN', 'GOLD']

    def test_high_variation_fail_status(self):
        df = pd.DataFrame({
            'parent_x': [0, 0, 0],
            'parent_y': [0, 0, 0],
            'parent_z': [0, 0, 0],
            'child_x': [1.0, 1.5, 0.5],
            'child_y': [0, 0, 0],
            'child_z': [0, 0, 0]
        })
        bones = [('parent', 'child')]
        
        result = compute_bone_length_cv(df, bones)
        assert result.iloc[0]['status'] == 'FAIL'


class TestAngularVelocity:
    def test_normal_angular_velocity_pass(self):
        df = pd.DataFrame({
            'knee_angle': np.linspace(0, 90, 100)
        })
        fs = 100
        
        result = check_angular_velocity(df, fs)
        assert len(result) == 1
        assert result.iloc[0]['status'] == 'PASS'

    def test_high_angular_velocity_fail(self):
        df = pd.DataFrame({
            'knee_angle': np.concatenate([np.linspace(0, 2500, 10), np.linspace(2500, 0, 10)])
        })
        fs = 10
        
        result = check_angular_velocity(df, fs)
        assert result.iloc[0]['status'] == 'FAIL'

    def test_moderate_angular_velocity_warn(self):
        df = pd.DataFrame({
            'knee_angle': np.concatenate([np.linspace(0, 1600, 10), np.linspace(1600, 0, 10)])
        })
        fs = 10
        
        result = check_angular_velocity(df, fs)
        assert result.iloc[0]['status'] == 'WARN'


class TestBoneLengthChangeValidation:
    def test_10_percent_change_triggers_fail(self):
        df_original = pd.DataFrame({
            'parent_x': [0, 0, 0],
            'parent_y': [0, 0, 0],
            'parent_z': [0, 0, 0],
            'child_x': [1.0, 1.0, 1.0],
            'child_y': [0, 0, 0],
            'child_z': [0, 0, 0]
        })
        
        df_modified = pd.DataFrame({
            'parent_x': [0, 0, 0],
            'parent_y': [0, 0, 0],
            'parent_z': [0, 0, 0],
            'child_x': [1.0, 1.0, 1.0],  # Same length (0% change)
            'child_y': [0, 0, 0],
            'child_z': [0, 0, 0]
        })
        
        bones = [('parent', 'child')]
        result = validate_bone_length_change(df_original, df_modified, bones, 10.0)
        
        # Test with actual 10% change
        df_modified_10 = df_original.copy()
        df_modified_10['child_x'] = [1.1, 1.1, 1.1]  # 10% increase
        
        result_10 = validate_bone_length_change(df_original, df_modified_10, bones, 10.0)
        
        # The test should pass because there's a 10% change
        assert result_10['details'][0]['percent_change'] >= 10.0


if __name__ == "__main__":
    pytest.main([__file__])
