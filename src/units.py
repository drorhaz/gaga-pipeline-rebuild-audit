"""
Mass Normalization (Ethics Guard) Module

This module prevents incorrect absolute kinetics reporting by enforcing
mass-based unit conventions and naming rules.
"""

from enum import Enum
from typing import Optional, List
import pandas as pd


class MassMode(Enum):
    """Mass mode enumeration for kinetics reporting."""
    UNIT_MASS = "unit_mass"
    ABSOLUTE = "absolute"


def get_mass_mode(mass_kg: Optional[float]) -> MassMode:
    """
    Determine mass mode based on input mass value.
    
    Args:
        mass_kg: Mass in kilograms, or None if unknown
        
    Returns:
        MassMode: UNIT_MASS if mass is None or <= 0, ABSOLUTE otherwise
        
    Ethics Guard: Prevents incorrect absolute kinetics reporting by
    defaulting to unit mass mode when mass is invalid or unknown.
    """
    if mass_kg is None or mass_kg <= 0:
        return MassMode.UNIT_MASS
    else:
        return MassMode.ABSOLUTE


def enforce_per_kg_suffix(columns: List[str], mass_mode: MassMode) -> List[str]:
    """
    Enforce naming rule: if UNIT_MASS mode, enforce _per_kg suffix on power/torque columns.
    
    Args:
        columns: List of column names to validate/modify
        mass_mode: Current mass mode
        
    Returns:
        List[str]: Column names with proper suffix enforcement
        
    Ethics Guard: Ensures unit mass kinetics are clearly labeled with _per_kg suffix.
    """
    if mass_mode != MassMode.UNIT_MASS:
        return columns
    
    # Identify power and torque related columns
    power_torque_keywords = [
        'power', 'torque', 'moment', 'work', 'energy',
        'force', 'watts', 'nm', 'newton', 'joule'
    ]
    
    modified_columns = []
    
    for col in columns:
        col_lower = col.lower()
        
        # Check if this is a power/torque related column
        is_power_torque = any(keyword in col_lower for keyword in power_torque_keywords)
        
        if is_power_torque and not col_lower.endswith('_per_kg'):
            # Add _per_kg suffix
            modified_columns.append(f"{col}_per_kg")
        else:
            modified_columns.append(col)
    
    return modified_columns


def validate_kinetics_columns(df: pd.DataFrame, mass_mode: MassMode) -> dict:
    """
    Validate that kinetics columns follow naming conventions for the given mass mode.
    
    Args:
        df: DataFrame containing kinetics data
        mass_mode: Current mass mode
        
    Returns:
        dict: Validation results with any violations found
        
    Ethics Guard: Checks for compliance with mass-based naming conventions.
    """
    violations = []
    columns = df.columns.tolist()
    
    if mass_mode == MassMode.UNIT_MASS:
        # In UNIT_MASS mode, all power/torque columns must have _per_kg suffix
        power_torque_keywords = [
            'power', 'torque', 'moment', 'work', 'energy',
            'force', 'watts', 'nm', 'newton', 'joule'
        ]
        
        for col in columns:
            col_lower = col.lower()
            is_power_torque = any(keyword in col_lower for keyword in power_torque_keywords)
            
            if is_power_torque and not col_lower.endswith('_per_kg'):
                violations.append({
                    'column': col,
                    'issue': 'Missing _per_kg suffix in UNIT_MASS mode',
                    'severity': 'ERROR'
                })
    
    else:  # ABSOLUTE mode
        # In ABSOLUTE mode, columns should NOT have _per_kg suffix
        for col in columns:
            if col.lower().endswith('_per_kg'):
                violations.append({
                    'column': col,
                    'issue': 'Unexpected _per_kg suffix in ABSOLUTE mode',
                    'severity': 'WARNING'
                })
    
    # Consider warnings as non-critical, so valid if no errors
    has_errors = any(v['severity'] == 'ERROR' for v in violations)
    
    return {
        'valid': not has_errors,
        'violations': violations,
        'mass_mode': mass_mode.value
    }


def normalize_kinetics_data(df: pd.DataFrame, mass_kg: Optional[float]) -> tuple:
    """
    Normalize kinetics data based on mass mode.
    
    Args:
        df: DataFrame containing kinetics data
        mass_kg: Mass in kilograms, or None if unknown
        
    Returns:
        tuple: (normalized_df, mass_mode, validation_result)
        
    Ethics Guard: Automatically applies appropriate normalization and naming.
    """
    mass_mode = get_mass_mode(mass_kg)
    
    # Create a copy to avoid modifying original
    normalized_df = df.copy()
    
    if mass_mode == MassMode.UNIT_MASS:
        # In UNIT_MASS mode, rename power/torque columns with _per_kg suffix
        power_torque_keywords = [
            'power', 'torque', 'moment', 'work', 'energy',
            'force', 'watts', 'nm', 'newton', 'joule'
        ]
        
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            is_power_torque = any(keyword in col_lower for keyword in power_torque_keywords)
            
            if is_power_torque and not col_lower.endswith('_per_kg'):
                # Rename column with _per_kg suffix
                new_col_name = f"{col}_per_kg"
                column_mapping[col] = new_col_name
        
        # Apply column renaming
        if column_mapping:
            normalized_df = normalized_df.rename(columns=column_mapping)
            
            # Normalize values if mass is available and positive
            if mass_kg is not None and mass_kg > 0:
                for old_col, new_col in column_mapping.items():
                    if new_col in normalized_df.columns and old_col in df.select_dtypes(include=['number']).columns:
                        normalized_df[new_col] = df[old_col] / mass_kg
    
    # Validate naming conventions
    validation_result = validate_kinetics_columns(normalized_df, mass_mode)
    
    return normalized_df, mass_mode, validation_result


def get_mass_mode_summary(mass_kg: Optional[float]) -> dict:
    """
    Get a summary of the mass mode determination.
    
    Args:
        mass_kg: Mass in kilograms, or None if unknown
        
    Returns:
        dict: Summary of mass mode and reasoning
    """
    mass_mode = get_mass_mode(mass_kg)
    
    if mass_kg is None:
        reason = "Mass is None - defaulting to UNIT_MASS for safety"
    elif mass_kg <= 0:
        reason = f"Mass ({mass_kg} kg) is invalid - defaulting to UNIT_MASS for safety"
    else:
        reason = f"Mass ({mass_kg} kg) is valid - using ABSOLUTE mode"
    
    return {
        'mass_kg': mass_kg,
        'mass_mode': mass_mode.value,
        'reason': reason,
        'ethics_guard_active': mass_mode == MassMode.UNIT_MASS
    }
