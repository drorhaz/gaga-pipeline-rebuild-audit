"""
Artifact Detection Validation Module

This module provides validation tools for artifact detection methods,
including empirical validation of MAD thresholds and ROC curve analysis.

References:
    - Skurowski et al. (2015). Method for truncating artifacts in MoCap data.
    - Feng et al. (2019). Outlier detection for mocap data.
    - Leys et al. (2013). Detecting outliers: Do not use standard deviation around the mean, use absolute deviation around the median.
"""

import numpy as np
import pandas as pd
import logging
from typing import Tuple, Dict, Optional, List
from scipy.stats import median_abs_deviation
from scipy import signal

logger = logging.getLogger(__name__)


def generate_synthetic_artifacts(position: np.ndarray,
                                time_s: np.ndarray,
                                artifact_frames: List[int],
                                artifact_magnitude: float = 100.0) -> np.ndarray:
    """
    Generate synthetic position data with known artifacts for validation.
    
    Args:
        position: Clean position data (N, 3)
        time_s: Time vector
        artifact_frames: Frame indices where artifacts should be injected
        artifact_magnitude: Size of artifact (in position units)
        
    Returns:
        Position data with injected artifacts
    """
    position_artifact = position.copy()
    
    for frame in artifact_frames:
        if 0 <= frame < len(position):
            # Inject spike (sudden jump and return)
            position_artifact[frame] += np.random.randn(3) * artifact_magnitude
    
    return position_artifact


def compute_roc_curve(true_artifacts: np.ndarray,
                     detected_artifacts: np.ndarray) -> Dict[str, float]:
    """
    Compute ROC metrics for artifact detection.
    
    Args:
        true_artifacts: Ground truth artifact mask (N,)
        detected_artifacts: Detected artifact mask (N,)
        
    Returns:
        Dictionary with ROC metrics (TPR, FPR, precision, recall, F1)
    """
    true_positive = np.sum(true_artifacts & detected_artifacts)
    false_positive = np.sum(~true_artifacts & detected_artifacts)
    true_negative = np.sum(~true_artifacts & ~detected_artifacts)
    false_negative = np.sum(true_artifacts & ~detected_artifacts)
    
    # Metrics
    tpr = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0.0
    fpr = false_positive / (false_positive + true_negative) if (false_positive + true_negative) > 0 else 0.0
    
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0.0
    recall = tpr  # Same as TPR
    
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        'true_positive': int(true_positive),
        'false_positive': int(false_positive),
        'true_negative': int(true_negative),
        'false_negative': int(false_negative),
        'tpr': float(tpr),
        'fpr': float(fpr),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1)
    }


def validate_mad_threshold(position_clean: np.ndarray,
                          time_s: np.ndarray,
                          artifact_frames: List[int],
                          artifact_magnitude: float,
                          mad_multipliers: Optional[List[float]] = None) -> Dict[str, any]:
    """
    Validate MAD threshold by testing multiple multipliers on synthetic data.
    
    Args:
        position_clean: Clean position data
        time_s: Time vector
        artifact_frames: Frames where artifacts will be injected
        artifact_magnitude: Size of artifacts
        mad_multipliers: List of MAD multipliers to test (default: [3, 4, 5, 6, 7, 8])
        
    Returns:
        Dictionary with validation results for each multiplier
    """
    if mad_multipliers is None:
        mad_multipliers = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    
    # Generate ground truth
    position_artifact = generate_synthetic_artifacts(
        position_clean, time_s, artifact_frames, artifact_magnitude
    )
    
    # Ground truth artifact mask
    true_mask = np.zeros(len(position_clean), dtype=bool)
    true_mask[artifact_frames] = True
    
    # Compute velocity
    dt = np.diff(time_s)
    dt = np.maximum(dt, 1e-9)
    velocity = np.zeros_like(position_artifact)
    velocity[1:] = (position_artifact[1:] - position_artifact[:-1]) / dt[:, np.newaxis]
    
    # Test each multiplier
    results = []
    for multiplier in mad_multipliers:
        # Detect artifacts
        sigma = median_abs_deviation(velocity, axis=0, scale='normal')
        sigma = np.maximum(sigma, 1e-6)
        artifact_mask_raw = np.abs(velocity) > (multiplier * sigma[np.newaxis, :])
        detected_mask = np.any(artifact_mask_raw, axis=1)
        
        # Compute ROC metrics
        roc = compute_roc_curve(true_mask, detected_mask)
        roc['mad_multiplier'] = multiplier
        
        results.append(roc)
    
    # Find optimal multiplier (maximize F1 score)
    best_idx = np.argmax([r['f1_score'] for r in results])
    optimal_multiplier = results[best_idx]['mad_multiplier']
    
    return {
        'results_per_multiplier': results,
        'optimal_multiplier': optimal_multiplier,
        'optimal_f1_score': results[best_idx]['f1_score'],
        'optimal_precision': results[best_idx]['precision'],
        'optimal_recall': results[best_idx]['recall'],
        'artifact_magnitude_tested': artifact_magnitude,
        'n_artifacts_injected': len(artifact_frames)
    }


def validate_mad_robustness(position: np.ndarray,
                           time_s: np.ndarray,
                           noise_levels: Optional[List[float]] = None,
                           mad_multiplier: float = 6.0) -> Dict[str, any]:
    """
    Test MAD method robustness to different noise levels.
    
    Args:
        position: Clean position data
        time_s: Time vector
        noise_levels: List of noise standard deviations to test
        mad_multiplier: MAD multiplier to use
        
    Returns:
        Dictionary with false positive rates at each noise level
    """
    if noise_levels is None:
        noise_levels = [0.0, 0.01, 0.05, 0.1, 0.5, 1.0]  # mm
    
    results = []
    
    for noise_std in noise_levels:
        # Add Gaussian noise
        position_noisy = position + np.random.randn(*position.shape) * noise_std
        
        # Compute velocity
        dt = np.diff(time_s)
        dt = np.maximum(dt, 1e-9)
        velocity = np.zeros_like(position_noisy)
        velocity[1:] = (position_noisy[1:] - position_noisy[:-1]) / dt[:, np.newaxis]
        
        # Detect "artifacts" (should be mostly false positives in clean data)
        sigma = median_abs_deviation(velocity, axis=0, scale='normal')
        sigma = np.maximum(sigma, 1e-6)
        artifact_mask_raw = np.abs(velocity) > (mad_multiplier * sigma[np.newaxis, :])
        detected_mask = np.any(artifact_mask_raw, axis=1)
        
        false_positive_rate = np.mean(detected_mask)
        
        results.append({
            'noise_std': noise_std,
            'false_positive_rate': float(false_positive_rate),
            'n_false_positives': int(np.sum(detected_mask))
        })
    
    return {
        'mad_multiplier': mad_multiplier,
        'noise_robustness_results': results
    }


def compare_artifact_methods(position: np.ndarray,
                            time_s: np.ndarray,
                            artifact_frames: List[int],
                            artifact_magnitude: float) -> Dict[str, any]:
    """
    Compare MAD method with alternative artifact detection methods.
    
    Methods compared:
    1. MAD (6x threshold)
    2. Z-score (standard deviation, 3σ)
    3. Fixed velocity threshold
    
    Args:
        position: Clean position data
        time_s: Time vector
        artifact_frames: Frame indices with artifacts
        artifact_magnitude: Size of artifacts
        
    Returns:
        Dictionary comparing method performance
    """
    # Generate artifacts
    position_artifact = generate_synthetic_artifacts(
        position, time_s, artifact_frames, artifact_magnitude
    )
    
    # Ground truth
    true_mask = np.zeros(len(position), dtype=bool)
    true_mask[artifact_frames] = True
    
    # Compute velocity
    dt = np.diff(time_s)
    dt = np.maximum(dt, 1e-9)
    velocity = np.zeros_like(position_artifact)
    velocity[1:] = (position_artifact[1:] - position_artifact[:-1]) / dt[:, np.newaxis]
    
    results = {}
    
    # Method 1: MAD (6x)
    sigma_mad = median_abs_deviation(velocity, axis=0, scale='normal')
    sigma_mad = np.maximum(sigma_mad, 1e-6)
    mask_mad = np.any(np.abs(velocity) > (6.0 * sigma_mad[np.newaxis, :]), axis=1)
    results['mad_6x'] = compute_roc_curve(true_mask, mask_mad)
    results['mad_6x']['method'] = 'MAD (6x)'
    
    # Method 2: Z-score (3sigma)
    sigma_std = np.std(velocity, axis=0)
    sigma_std = np.maximum(sigma_std, 1e-6)
    mask_zscore = np.any(np.abs(velocity) > (3.0 * sigma_std[np.newaxis, :]), axis=1)
    results['zscore_3sigma'] = compute_roc_curve(true_mask, mask_zscore)
    results['zscore_3sigma']['method'] = 'Z-score (3-sigma)'
    
    # Method 3: Fixed threshold (velocity > 10 m/s)
    mask_fixed = np.any(np.abs(velocity) > 10.0, axis=1)
    results['fixed_10ms'] = compute_roc_curve(true_mask, mask_fixed)
    results['fixed_10ms']['method'] = 'Fixed (10 m/s)'
    
    # Find best method
    f1_scores = {name: res['f1_score'] for name, res in results.items()}
    best_method = max(f1_scores, key=f1_scores.get)
    
    return {
        'method_comparison': results,
        'best_method': best_method,
        'best_f1_score': f1_scores[best_method]
    }


def recommend_mad_multiplier(position: np.ndarray,
                            time_s: np.ndarray,
                            artifact_types: Optional[Dict[str, any]] = None) -> Dict[str, any]:
    """
    Recommend optimal MAD multiplier based on validation tests.
    
    Args:
        position: Position data for testing
        time_s: Time vector
        artifact_types: Dictionary with artifact scenarios to test
        
    Returns:
        Dictionary with recommendation and justification
        
    Reference:
        Leys et al. (2013): 2.5-3.0 for outlier detection
        Mocap community: 5-7 typical for spike detection
    """
    if artifact_types is None:
        artifact_types = {
            'small_spikes': {'magnitude': 10.0, 'n_artifacts': 10},
            'medium_spikes': {'magnitude': 50.0, 'n_artifacts': 10},
            'large_spikes': {'magnitude': 200.0, 'n_artifacts': 10}
        }
    
    recommendations = []
    
    for artifact_name, params in artifact_types.items():
        # Generate random artifact frames
        n_frames = len(position)
        artifact_frames = np.random.choice(
            np.arange(10, n_frames-10),
            size=params['n_artifacts'],
            replace=False
        ).tolist()
        
        # Validate
        validation = validate_mad_threshold(
            position, time_s, artifact_frames,
            params['magnitude'],
            mad_multipliers=[3, 4, 5, 6, 7, 8]
        )
        
        recommendations.append({
            'artifact_type': artifact_name,
            'optimal_multiplier': validation['optimal_multiplier'],
            'f1_score': validation['optimal_f1_score']
        })
    
    # Aggregate recommendations
    optimal_multipliers = [r['optimal_multiplier'] for r in recommendations]
    median_recommendation = float(np.median(optimal_multipliers))
    
    # Rationale
    if median_recommendation <= 4.0:
        rationale = "Low multiplier (aggressive detection) - suitable for high-quality data"
    elif median_recommendation <= 6.0:
        rationale = "Medium multiplier (balanced) - suitable for typical mocap data"
    else:
        rationale = "High multiplier (conservative) - suitable for noisy data"
    
    return {
        'recommended_multiplier': median_recommendation,
        'rationale': rationale,
        'per_artifact_type': recommendations,
        'multiplier_range': (min(optimal_multipliers), max(optimal_multipliers)),
        'current_pipeline_value': 6.0,
        'recommendation_status': 'VALIDATED' if abs(median_recommendation - 6.0) < 1.5 else 'ADJUST_RECOMMENDED'
    }


def get_artifact_validation_metrics(position: np.ndarray,
                                   time_s: np.ndarray,
                                   detected_artifacts: np.ndarray) -> Dict[str, float]:
    """
    Extract artifact validation metrics for QC reporting.
    
    Args:
        position: Position data
        time_s: Time vector
        detected_artifacts: Boolean mask of detected artifacts
        
    Returns:
        Dictionary with validation metrics
    """
    n_total = len(detected_artifacts)
    n_artifacts = int(np.sum(detected_artifacts))
    artifact_percentage = 100.0 * n_artifacts / n_total if n_total > 0 else 0.0
    
    # Compute artifact clustering (are they isolated or clustered?)
    if n_artifacts > 0:
        artifact_indices = np.where(detected_artifacts)[0]
        gaps = np.diff(artifact_indices)
        mean_gap = float(np.mean(gaps)) if len(gaps) > 0 else 0.0
        
        # Clustered if mean gap < 5 frames
        clustering_metric = 'clustered' if mean_gap < 5 else 'isolated'
    else:
        mean_gap = 0.0
        clustering_metric = 'none'
    
    return {
        'artifact_count': n_artifacts,
        'artifact_percentage': artifact_percentage,
        'artifact_clustering': clustering_metric,
        'artifact_mean_gap_frames': mean_gap,
        'artifact_detection_method': 'MAD_6x'
    }
