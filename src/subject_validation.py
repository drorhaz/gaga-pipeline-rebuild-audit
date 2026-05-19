"""
Subject Context Validation Module
===================================
Task 1: Subject Context & Normalization (Step 05)

This module provides validation functions for subject metadata including:
1. Height sanity checks (0 < height <= 250 cm)
2. Mass sanity checks (20 < mass <= 200 kg)
3. Intensity Index normalization (Intensity / Mass)

Author: Gaga Motion Analysis Pipeline
Date: 2026-01-23
"""

import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# VALIDATION THRESHOLDS
# ============================================================================

HEIGHT_MIN_CM = 0.0          # Minimum plausible height (exclusive)
HEIGHT_MAX_CM = 250.0        # Maximum plausible height (inclusive)
HEIGHT_TYPICAL_MIN_CM = 140.0  # Typical adult minimum (for warnings)
HEIGHT_TYPICAL_MAX_CM = 210.0  # Typical adult maximum (for warnings)

MASS_MIN_KG = 20.0           # Minimum plausible mass (exclusive)
MASS_MAX_KG = 200.0          # Maximum plausible mass (inclusive)
MASS_TYPICAL_MIN_KG = 40.0   # Typical adult minimum (for warnings)
MASS_TYPICAL_MAX_KG = 150.0  # Typical adult maximum (for warnings)


# ============================================================================
# HEIGHT VALIDATION
# ============================================================================

def validate_height(height_cm: float) -> Tuple[str, str]:
    """
    Validate subject height with sanity checks.
    
    Task 1 Requirement: If height == 0 or height > 250: status = REVIEW
    
    Args:
        height_cm: Subject height in centimeters
        
    Returns:
        Tuple of (status, reason) where status is 'PASS', 'REVIEW', or 'FAIL'
        
    Status Levels:
        - PASS: Height is within normal range (140-210 cm)
        - REVIEW: Height is unusual but plausible (0-140 or 210-250 cm)
        - FAIL: Height is physically implausible (≤0 or >250 cm)
        
    Examples:
        >>> validate_height(170.0)
        ('PASS', 'Height within normal range: 170.0 cm')
        
        >>> validate_height(0.0)
        ('FAIL', 'Height is zero or negative: 0.0 cm (FAIL)')
        
        >>> validate_height(300.0)
        ('FAIL', 'Height exceeds maximum threshold: 300.0 cm > 250.0 cm (FAIL)')
    """
    # FAIL: Zero or negative height
    if height_cm <= HEIGHT_MIN_CM:
        return ('FAIL', f'Height is zero or negative: {height_cm:.2f} cm (FAIL)')
    
    # FAIL: Height exceeds maximum plausible threshold
    if height_cm > HEIGHT_MAX_CM:
        return ('FAIL', f'Height exceeds maximum threshold: {height_cm:.2f} cm > {HEIGHT_MAX_CM:.1f} cm (FAIL)')
    
    # REVIEW: Height below typical minimum (but above zero)
    if height_cm < HEIGHT_TYPICAL_MIN_CM:
        return ('REVIEW', f'Height below typical range: {height_cm:.2f} cm < {HEIGHT_TYPICAL_MIN_CM:.1f} cm (REVIEW)')
    
    # REVIEW: Height above typical maximum (but below absolute max)
    if height_cm > HEIGHT_TYPICAL_MAX_CM:
        return ('REVIEW', f'Height above typical range: {height_cm:.2f} cm > {HEIGHT_TYPICAL_MAX_CM:.1f} cm (REVIEW)')
    
    # PASS: Height is within normal range
    return ('PASS', f'Height within normal range: {height_cm:.2f} cm')


def validate_mass(mass_kg: float) -> Tuple[str, str]:
    """
    Validate subject mass with sanity checks.
    
    Args:
        mass_kg: Subject mass in kilograms
        
    Returns:
        Tuple of (status, reason) where status is 'PASS', 'REVIEW', or 'FAIL'
        
    Status Levels:
        - PASS: Mass is within normal range (40-150 kg)
        - REVIEW: Mass is unusual but plausible (20-40 or 150-200 kg)
        - FAIL: Mass is physically implausible (≤20 or >200 kg)
    """
    # FAIL: Zero or very low mass
    if mass_kg <= MASS_MIN_KG:
        return ('FAIL', f'Mass is too low or zero: {mass_kg:.2f} kg ≤ {MASS_MIN_KG:.1f} kg (FAIL)')
    
    # FAIL: Mass exceeds maximum plausible threshold
    if mass_kg > MASS_MAX_KG:
        return ('FAIL', f'Mass exceeds maximum threshold: {mass_kg:.2f} kg > {MASS_MAX_KG:.1f} kg (FAIL)')
    
    # REVIEW: Mass below typical minimum
    if mass_kg < MASS_TYPICAL_MIN_KG:
        return ('REVIEW', f'Mass below typical range: {mass_kg:.2f} kg < {MASS_TYPICAL_MIN_KG:.1f} kg (REVIEW)')
    
    # REVIEW: Mass above typical maximum
    if mass_kg > MASS_TYPICAL_MAX_KG:
        return ('REVIEW', f'Mass above typical range: {mass_kg:.2f} kg > {MASS_TYPICAL_MAX_KG:.1f} kg (REVIEW)')
    
    # PASS: Mass is within normal range
    return ('PASS', f'Mass within normal range: {mass_kg:.2f} kg')


# ============================================================================
# INTENSITY INDEX NORMALIZATION
# ============================================================================

def compute_normalized_intensity_index(
    intensity_raw: float,
    mass_kg: float,
    validate_inputs: bool = True
) -> Dict:
    """
    Compute normalized Intensity Index: I_norm = I / m
    
    Task 1 Requirement: Use height/mass data to calculate Intensity_Index
    as a normalized value (Intensity / Mass).
    
    Args:
        intensity_raw: Raw intensity value (mm·deg/s or similar movement metric)
        mass_kg: Subject mass in kilograms
        validate_inputs: If True, validate mass before computation
        
    Returns:
        Dict with:
            - intensity_normalized: I_norm = I / m (units: [intensity_units] / kg)
            - intensity_raw: Original intensity value
            - mass_kg: Subject mass used
            - mass_status: Validation status ('PASS', 'REVIEW', 'FAIL')
            - mass_reason: Validation reason
            - formula: LaTeX formula used
            
    Formula:
        I_norm = I / m
        
        where:
        - I = total path intensity (mm·deg/s)
        - m = subject mass (kg)
        
    Examples:
        >>> compute_normalized_intensity_index(1000.0, 70.0)
        {
            'intensity_normalized': 14.29,
            'intensity_raw': 1000.0,
            'mass_kg': 70.0,
            'mass_status': 'PASS',
            'mass_reason': 'Mass within normal range: 70.0 kg',
            'formula': 'I_norm = I / m'
        }
    """
    result = {
        'intensity_raw': intensity_raw,
        'mass_kg': mass_kg,
        'formula': r'$I_{norm} = \frac{I}{m}$'
    }
    
    # Validate mass if requested
    if validate_inputs:
        mass_status, mass_reason = validate_mass(mass_kg)
        result['mass_status'] = mass_status
        result['mass_reason'] = mass_reason
        
        if mass_status == 'FAIL':
            logger.error(f"Cannot compute normalized intensity: {mass_reason}")
            result['intensity_normalized'] = None
            result['error'] = f"Invalid mass: {mass_reason}"
            return result
        elif mass_status == 'REVIEW':
            logger.warning(f"Computing normalized intensity with unusual mass: {mass_reason}")
    
    # Compute normalized intensity
    if mass_kg > 0:
        intensity_normalized = intensity_raw / mass_kg
        result['intensity_normalized'] = round(intensity_normalized, 4)
    else:
        result['intensity_normalized'] = None
        result['error'] = 'Cannot divide by zero or negative mass'
        logger.error(f"Cannot compute normalized intensity: mass_kg = {mass_kg}")
    
    return result


# ============================================================================
# SUBJECT CONTEXT VALIDATION (COMBINED)
# ============================================================================

def validate_subject_context(
    height_cm: Optional[float] = None,
    mass_kg: Optional[float] = None
) -> Dict:
    """
    Validate complete subject context (height and mass).
    
    Args:
        height_cm: Subject height in centimeters (optional)
        mass_kg: Subject mass in kilograms (optional)
        
    Returns:
        Dict with validation results for height and mass
        
    Example:
        >>> validate_subject_context(height_cm=170.0, mass_kg=70.0)
        {
            'height': {
                'value_cm': 170.0,
                'status': 'PASS',
                'reason': 'Height within normal range: 170.0 cm'
            },
            'mass': {
                'value_kg': 70.0,
                'status': 'PASS',
                'reason': 'Mass within normal range: 70.0 kg'
            },
            'overall_status': 'PASS'
        }
    """
    result = {}
    
    # Validate height
    if height_cm is not None:
        height_status, height_reason = validate_height(height_cm)
        result['height'] = {
            'value_cm': height_cm,
            'status': height_status,
            'reason': height_reason
        }
    else:
        result['height'] = {
            'value_cm': None,
            'status': 'NOT_PROVIDED',
            'reason': 'Height not provided'
        }
    
    # Validate mass
    if mass_kg is not None:
        mass_status, mass_reason = validate_mass(mass_kg)
        result['mass'] = {
            'value_kg': mass_kg,
            'status': mass_status,
            'reason': mass_reason
        }
    else:
        result['mass'] = {
            'value_kg': None,
            'status': 'NOT_PROVIDED',
            'reason': 'Mass not provided'
        }
    
    # Determine overall status
    statuses = []
    if height_cm is not None:
        statuses.append(result['height']['status'])
    if mass_kg is not None:
        statuses.append(result['mass']['status'])
    
    if 'FAIL' in statuses:
        result['overall_status'] = 'FAIL'
    elif 'REVIEW' in statuses:
        result['overall_status'] = 'REVIEW'
    elif 'PASS' in statuses:
        result['overall_status'] = 'PASS'
    else:
        result['overall_status'] = 'NOT_PROVIDED'
    
    return result


# ============================================================================
# LOGGING HELPERS
# ============================================================================

def log_subject_validation(validation_result: Dict, logger_name: Optional[str] = None):
    """
    Log subject validation results in a formatted way.
    
    Args:
        validation_result: Output from validate_subject_context()
        logger_name: Optional logger name (defaults to this module's logger)
    """
    log = logging.getLogger(logger_name) if logger_name else logger
    
    log.info("=" * 70)
    log.info("SUBJECT CONTEXT VALIDATION (Task 1)")
    log.info("=" * 70)
    
    if 'height' in validation_result:
        h = validation_result['height']
        log.info(f"Height: {h['value_cm']} cm | Status: {h['status']}")
        log.info(f"  → {h['reason']}")
    
    if 'mass' in validation_result:
        m = validation_result['mass']
        log.info(f"Mass: {m['value_kg']} kg | Status: {m['status']}")
        log.info(f"  → {m['reason']}")
    
    log.info(f"Overall Status: {validation_result['overall_status']}")
    log.info("=" * 70)
