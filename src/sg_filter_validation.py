"""
Savitzky-Golay Filter Validation Module

This module provides validation tools for Savitzky-Golay filter parameters used
in velocity computation, ensuring biomechanically appropriate smoothing.

References:
    - Savitzky, A. & Golay, M. J. E. (1964). Smoothing and differentiation of data by simplified least squares procedures.
    - Woltring, H. J. (1985). On optimal smoothing and derivative estimation from noisy displacement data.
    - Winter, D. A. (2009). Biomechanics and motor control. Chapter on derivative estimation.
"""

import numpy as np
import pandas as pd
import logging
from typing import Tuple, Dict, Optional, List
from scipy.signal import savgol_filter

logger = logging.getLogger(__name__)


def compute_sg_derivative(position: np.ndarray,
                         fs: float,
                         window_sec: float,
                         polyorder: int) -> np.ndarray:
    """
    Compute velocity using Savitzky-Golay filter.
    
    Args:
        position: Position data (N, 3) in meters
        fs: Sampling frequency in Hz
        window_sec: Window size in seconds
        polyorder: Polynomial order
        
    Returns:
        Velocity in m/s
        
    Reference:
        Savitzky & Golay (1964): Original method
    """
    window_frames = int(round(window_sec * fs))
    if window_frames < 5:
        window_frames = 5
    if window_frames % 2 == 0:
        window_frames += 1  # Must be odd
    
    # Ensure polynomial order is valid
    if polyorder >= window_frames:
        polyorder = window_frames - 1
    
    velocity = savgol_filter(
        position, window_length=window_frames, polyorder=polyorder,
        deriv=1, delta=1.0/fs, axis=0, mode='interp'
    )
    
    return velocity


def validate_sg_parameters(position: np.ndarray,
                          velocity_true: np.ndarray,
                          fs: float,
                          window_candidates: Optional[List[float]] = None,
                          polyorder_candidates: Optional[List[int]] = None) -> Dict[str, any]:
    """
    Validate SG filter parameters by comparing with ground truth velocity.
    
    Tests different window sizes and polynomial orders to find optimal parameters.
    
    Args:
        position: Position data from which velocity was computed
        velocity_true: Ground truth velocity (from known motion)
        fs: Sampling frequency
        window_candidates: Window sizes to test (in seconds)
        polyorder_candidates: Polynomial orders to test
        
    Returns:
        Dictionary with optimal parameters and validation metrics
    """
    if window_candidates is None:
        # Test from 0.05s (6 frames @ 120Hz) to 0.5s (60 frames)
        window_candidates = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
    
    if polyorder_candidates is None:
        polyorder_candidates = [2, 3, 4, 5]
    
    results = []
    
    for window_sec in window_candidates:
        for polyorder in polyorder_candidates:
            try:
                # Compute velocity with these parameters
                velocity_sg = compute_sg_derivative(position, fs, window_sec, polyorder)
                
                # Compute error metrics
                error = velocity_sg - velocity_true
                rmse = float(np.sqrt(np.nanmean(error**2)))
                mae = float(np.nanmean(np.abs(error)))
                
                # Correlation with ground truth
                corr = float(np.corrcoef(
                    velocity_true.flatten(), 
                    velocity_sg.flatten()
                )[0, 1])
                
                results.append({
                    'window_sec': window_sec,
                    'window_frames': int(round(window_sec * fs)),
                    'polyorder': polyorder,
                    'rmse': rmse,
                    'mae': mae,
                    'correlation': corr
                })
            except Exception as e:
                logger.warning(f"SG validation failed for window={window_sec}, poly={polyorder}: {e}")
    
    if not results:
        return {'status': 'FAIL', 'error': 'No valid parameter combinations'}
    
    # Find optimal parameters (minimize RMSE)
    best_idx = np.argmin([r['rmse'] for r in results])
    optimal = results[best_idx]
    
    return {
        'optimal_window_sec': optimal['window_sec'],
        'optimal_window_frames': optimal['window_frames'],
        'optimal_polyorder': optimal['polyorder'],
        'optimal_rmse': optimal['rmse'],
        'optimal_mae': optimal['mae'],
        'optimal_correlation': optimal['correlation'],
        'all_results': results,
        'n_combinations_tested': len(results)
    }


def validate_sg_biomechanical(position: np.ndarray,
                             fs: float,
                             window_sec: float,
                             polyorder: int,
                             movement_type: str = 'dance') -> Dict[str, any]:
    """
    Validate that SG parameters are appropriate for biomechanical application.
    
    Criteria (Winter 2009, Woltring 1985):
    - Window size: 0.1-0.3s for dance (preserves dynamics)
    - Polynomial order: 2-4 (higher = more smoothing)
    - Effective cutoff frequency: Should match signal bandwidth
    
    Args:
        position: Position data
        fs: Sampling frequency
        window_sec: Window size used
        polyorder: Polynomial order used
        movement_type: 'dance', 'gait', 'reaching'
        
    Returns:
        Dictionary with biomechanical validation
        
    Reference:
        Woltring (1985): SG filter selection criteria
        Winter (2009): Biomechanical appropriateness
    """
    window_frames = int(round(window_sec * fs))
    
    # Define biomechanical criteria
    if movement_type == 'dance':
        window_range = (0.08, 0.3)  # 0.08-0.3s for dynamic movements
        poly_range = (2, 4)
        expected_bandwidth_hz = (1, 15)  # Dance: 1-15 Hz (rapid gestures to 15 Hz)
    elif movement_type == 'gait':
        window_range = (0.1, 0.5)
        poly_range = (2, 3)
        expected_bandwidth_hz = (0.5, 8)
    else:  # reaching, general
        window_range = (0.1, 0.4)
        poly_range = (2, 4)
        expected_bandwidth_hz = (0.5, 10)
    
    # Check window size
    window_ok = window_range[0] <= window_sec <= window_range[1]
    
    # Check polynomial order
    poly_ok = poly_range[0] <= polyorder <= poly_range[1]
    
    # Estimate effective cutoff frequency (approximation from Woltring 1985)
    # For SG filter: fc_effective ≈ 0.4 * fs / window_frames (rough estimate)
    fc_effective = 0.4 * fs / window_frames
    fc_ok = expected_bandwidth_hz[0] <= fc_effective <= expected_bandwidth_hz[1] * 1.5
    
    # Overall assessment
    if window_ok and poly_ok and fc_ok:
        status = 'PASS'
    elif window_ok and poly_ok:
        status = 'WARN_CUTOFF'
    elif fc_ok:
        status = 'WARN_PARAMETERS'
    else:
        status = 'FAIL'
    
    return {
        'movement_type': movement_type,
        'window_sec': window_sec,
        'window_frames': window_frames,
        'polyorder': polyorder,
        'effective_cutoff_hz': fc_effective,
        'window_in_range': window_ok,
        'polyorder_in_range': poly_ok,
        'cutoff_in_range': fc_ok,
        'biomechanical_status': status,
        'expected_ranges': {
            'window_sec': window_range,
            'polyorder': poly_range,
            'bandwidth_hz': expected_bandwidth_hz
        }
    }


def compare_sg_with_alternatives(position: np.ndarray,
                                 fs: float,
                                 sg_window_sec: float,
                                 sg_polyorder: int) -> Dict[str, any]:
    """
    Compare SG filter with alternative derivative estimation methods.
    
    Methods compared:
    1. Savitzky-Golay (current pipeline)
    2. Simple finite difference
    3. Central difference
    
    Args:
        position: Position data
        fs: Sampling frequency
        sg_window_sec: SG window size
        sg_polyorder: SG polynomial order
        
    Returns:
        Dictionary with method comparison
    """
    # Method 1: SG filter (current)
    vel_sg = compute_sg_derivative(position, fs, sg_window_sec, sg_polyorder)
    
    # Method 2: Simple finite difference
    dt = 1.0 / fs
    vel_simple = np.zeros_like(position)
    vel_simple[1:] = (position[1:] - position[:-1]) / dt
    
    # Method 3: Central difference
    vel_central = np.zeros_like(position)
    vel_central[1:-1] = (position[2:] - position[:-2]) / (2 * dt)
    vel_central[0] = vel_simple[0]
    vel_central[-1] = vel_simple[-1]
    
    # Compute noise (second derivative std)
    mag_sg = np.linalg.norm(vel_sg, axis=1)
    mag_simple = np.linalg.norm(vel_simple, axis=1)
    mag_central = np.linalg.norm(vel_central, axis=1)
    
    noise_sg = float(np.nanstd(np.diff(mag_sg, n=2)))
    noise_simple = float(np.nanstd(np.diff(mag_simple, n=2)))
    noise_central = float(np.nanstd(np.diff(mag_central, n=2)))
    
    return {
        'method_comparison': {
            'savitzky_golay': {
                'mean_magnitude': float(np.nanmean(mag_sg)),
                'noise_metric': noise_sg
            },
            'simple_diff': {
                'mean_magnitude': float(np.nanmean(mag_simple)),
                'noise_metric': noise_simple
            },
            'central_diff': {
                'mean_magnitude': float(np.nanmean(mag_central)),
                'noise_metric': noise_central
            }
        },
        'noise_reduction_sg_vs_simple': noise_simple / noise_sg if noise_sg > 0 else np.inf,
        'noise_reduction_sg_vs_central': noise_central / noise_sg if noise_sg > 0 else np.inf,
        'sg_parameters': {
            'window_sec': sg_window_sec,
            'polyorder': sg_polyorder
        }
    }


def get_sg_validation_metrics(window_sec: float,
                              polyorder: int,
                              fs: float,
                              movement_type: str = 'dance') -> Dict[str, any]:
    """
    Get SG filter validation metrics for QC reporting.
    
    Args:
        window_sec: Window size in seconds
        polyorder: Polynomial order
        fs: Sampling frequency
        movement_type: Type of movement being analyzed
        
    Returns:
        Dictionary with validation metrics
    """
    # Biomechanical validation
    biomech = validate_sg_biomechanical(
        np.random.randn(1000, 3),  # Dummy data for parameter validation
        fs, window_sec, polyorder, movement_type
    )
    
    return {
        'sg_window_sec': window_sec,
        'sg_window_frames': int(round(window_sec * fs)),
        'sg_polyorder': polyorder,
        'sg_effective_cutoff_hz': biomech['effective_cutoff_hz'],
        'sg_biomechanical_status': biomech['biomechanical_status'],
        'sg_parameters_validated': biomech['biomechanical_status'] in ['PASS', 'WARN_CUTOFF']
    }
