import pytest
import pandas as pd
import numpy as np
from src.units import (
    MassMode,
    get_mass_mode,
    enforce_per_kg_suffix,
    validate_kinetics_columns,
    normalize_kinetics_data,
    get_mass_mode_summary
)


class TestGetMassMode:
    def test_mass_none_results_in_unit_mass(self):
        """Test: mass=None must result in UNIT_MASS mode."""
        result = get_mass_mode(None)
        assert result == MassMode.UNIT_MASS

    def test_mass_zero_results_in_unit_mass(self):
        """Test: mass=0 must result in UNIT_MASS mode."""
        result = get_mass_mode(0.0)
        assert result == MassMode.UNIT_MASS

    def test_mass_negative_results_in_unit_mass(self):
        """Test: mass<0 must result in UNIT_MASS mode."""
        result = get_mass_mode(-5.0)
        assert result == MassMode.UNIT_MASS

    def test_valid_mass_results_in_absolute(self):
        """Test: valid positive mass must result in ABSOLUTE mode."""
        result = get_mass_mode(75.5)
        assert result == MassMode.ABSOLUTE

    def test_mass_exactly_zero_results_in_unit_mass(self):
        """Test: mass=0.0 must result in UNIT_MASS mode."""
        result = get_mass_mode(0.0)
        assert result == MassMode.UNIT_MASS


class TestEnforcePerKgSuffix:
    def test_unit_mass_mode_adds_suffix(self):
        """Test: UNIT_MASS mode adds _per_kg suffix to power/torque columns."""
        columns = ['knee_power', 'hip_torque', 'position_x', 'time']
        result = enforce_per_kg_suffix(columns, MassMode.UNIT_MASS)
        
        expected = ['knee_power_per_kg', 'hip_torque_per_kg', 'position_x', 'time']
        assert result == expected

    def test_absolute_mode_no_change(self):
        """Test: ABSOLUTE mode doesn't modify column names."""
        columns = ['knee_power', 'hip_torque', 'position_x']
        result = enforce_per_kg_suffix(columns, MassMode.ABSOLUTE)
        
        assert result == columns

    def test_already_has_suffix_no_change(self):
        """Test: Columns already ending with _per_kg are not modified."""
        columns = ['knee_power_per_kg', 'hip_torque_per_kg']
        result = enforce_per_kg_suffix(columns, MassMode.UNIT_MASS)
        
        assert result == columns

    def test_case_insensitive_detection(self):
        """Test: Power/torque detection is case insensitive."""
        columns = ['KNEE_POWER', 'Hip_Torque', 'Work_Joules']
        result = enforce_per_kg_suffix(columns, MassMode.UNIT_MASS)
        
        expected = ['KNEE_POWER_per_kg', 'Hip_Torque_per_kg', 'Work_Joules_per_kg']
        assert result == expected


class TestValidateKineticsColumns:
    def test_unit_mass_mode_validation_pass(self):
        """Test: UNIT_MASS mode validation passes with proper suffixes."""
        df = pd.DataFrame({
            'knee_power_per_kg': [1.0, 2.0],
            'position_x': [0.1, 0.2]
        })
        result = validate_kinetics_columns(df, MassMode.UNIT_MASS)
        
        assert result['valid'] == True
        assert len(result['violations']) == 0

    def test_unit_mass_mode_validation_fails(self):
        """Test: UNIT_MASS mode validation fails without proper suffixes."""
        df = pd.DataFrame({
            'knee_power': [1.0, 2.0],  # Missing _per_kg
            'position_x': [0.1, 0.2]
        })
        result = validate_kinetics_columns(df, MassMode.UNIT_MASS)
        
        assert result['valid'] == False
        assert len(result['violations']) == 1
        assert 'Missing _per_kg suffix' in result['violations'][0]['issue']

    def test_absolute_mode_validation_pass(self):
        """Test: ABSOLUTE mode validation passes without _per_kg suffixes."""
        df = pd.DataFrame({
            'knee_power': [1.0, 2.0],
            'position_x': [0.1, 0.2]
        })
        result = validate_kinetics_columns(df, MassMode.ABSOLUTE)
        
        assert result['valid'] == True
        assert len(result['violations']) == 0

    def test_absolute_mode_validation_warning(self):
        """Test: ABSOLUTE mode gives warning for _per_kg suffixes."""
        df = pd.DataFrame({
            'knee_power_per_kg': [1.0, 2.0],
            'position_x': [0.1, 0.2]
        })
        result = validate_kinetics_columns(df, MassMode.ABSOLUTE)
        
        assert result['valid'] == True  # Still valid, just warning
        assert len(result['violations']) == 1
        assert result['violations'][0]['severity'] == 'WARNING'


class TestNormalizeKineticsData:
    def test_normalize_with_valid_mass(self):
        """Test: Normalization with valid mass uses ABSOLUTE mode."""
        df = pd.DataFrame({
            'knee_power': [100.0, 200.0],
            'position_x': [0.1, 0.2]
        })
        mass_kg = 80.0
        
        normalized_df, mass_mode, validation = normalize_kinetics_data(df, mass_kg)
        
        assert mass_mode == MassMode.ABSOLUTE
        assert normalized_df['knee_power'].iloc[0] == 100.0  # No normalization

    def test_normalize_with_none_mass(self):
        """Test: Normalization with None mass uses UNIT_MASS mode."""
        df = pd.DataFrame({
            'knee_power': [100.0, 200.0],
            'position_x': [0.1, 0.2]
        })
        mass_kg = None
        
        normalized_df, mass_mode, validation = normalize_kinetics_data(df, mass_kg)
        
        assert mass_mode == MassMode.UNIT_MASS
        # Column should be renamed with _per_kg suffix
        assert 'knee_power_per_kg' in normalized_df.columns
        assert 'knee_power' not in normalized_df.columns

    def test_normalize_with_invalid_mass(self):
        """Test: Normalization with invalid mass uses UNIT_MASS mode."""
        df = pd.DataFrame({
            'knee_power': [100.0, 200.0],
            'position_x': [0.1, 0.2]
        })
        mass_kg = -5.0
        
        normalized_df, mass_mode, validation = normalize_kinetics_data(df, mass_kg)
        
        assert mass_mode == MassMode.UNIT_MASS
        assert 'knee_power_per_kg' in normalized_df.columns


class TestGetMassModeSummary:
    def test_summary_with_none_mass(self):
        """Test: Summary correctly explains None mass case."""
        result = get_mass_mode_summary(None)
        
        assert result['mass_kg'] is None
        assert result['mass_mode'] == MassMode.UNIT_MASS.value
        assert 'None' in result['reason']
        assert result['ethics_guard_active'] == True

    def test_summary_with_invalid_mass(self):
        """Test: Summary correctly explains invalid mass case."""
        result = get_mass_mode_summary(-10.0)
        
        assert result['mass_kg'] == -10.0
        assert result['mass_mode'] == MassMode.UNIT_MASS.value
        assert 'invalid' in result['reason'].lower()
        assert result['ethics_guard_active'] == True

    def test_summary_with_valid_mass(self):
        """Test: Summary correctly explains valid mass case."""
        result = get_mass_mode_summary(75.0)
        
        assert result['mass_kg'] == 75.0
        assert result['mass_mode'] == MassMode.ABSOLUTE.value
        assert 'valid' in result['reason'].lower()
        assert result['ethics_guard_active'] == False


class TestEthicsGuardFunctionality:
    def test_ethics_guard_prevents_absolute_reporting(self):
        """Test: Ethics guard prevents absolute reporting with invalid mass."""
        # Test edge cases that should trigger ethics guard
        invalid_masses = [None, 0.0, -1.0, -100.0]
        
        for mass in invalid_masses:
            mass_mode = get_mass_mode(mass)
            assert mass_mode == MassMode.UNIT_MASS, f"Failed for mass: {mass}"

    def test_power_torque_keywords_comprehensive(self):
        """Test: All power/torque keywords are properly detected."""
        keywords = [
            'power', 'torque', 'moment', 'work', 'energy',
            'force', 'watts', 'nm', 'newton', 'joule'
        ]
        
        for keyword in keywords:
            columns = [f'test_{keyword}_column']
            result = enforce_per_kg_suffix(columns, MassMode.UNIT_MASS)
            assert result[0].endswith('_per_kg'), f"Failed for keyword: {keyword}"


if __name__ == "__main__":
    pytest.main([__file__])
