"""
Gate Integration Module
=======================
Consolidates all gate checks into a single interface for notebook integration.

This module provides:
- run_gate_2(): Temporal quality assessment
- run_gate_3(): Filtering quality assessment  
- run_gate_4(): ISB compliance check
- run_gate_5(): Burst classification
- combine_gate_decisions(): Aggregate all gate decisions

Usage in notebooks:
    from src.gate_integration import run_all_gates, get_overall_decision
    
    gate_results = run_all_gates(
        time_s=time_s,
        angular_velocity=omega_mag,
        joint_names=joint_names,
        interpolation_summary=interp_summary,
        filter_summary=filter_summary,
        quat_norm_err=max_quat_norm_err,
        fs=fs
    )
    
    overall_decision = get_overall_decision(gate_results)

Author: Gaga Motion Analysis Pipeline
Date: 2026-01-23
"""

import numpy as np
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Import gate modules
from .resampling import compute_sample_jitter, get_interpolation_fallback_metrics
from .euler_isb import get_euler_sequences_audit, assess_quaternion_health
from .burst_classification import classify_burst_events, generate_burst_audit_fields


def run_gate_2(
    time_s: np.ndarray,
    interpolation_summary: Optional[Dict] = None,
    total_frames: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run Gate 2: Signal Integrity & Temporal Quality.
    
    Parameters
    ----------
    time_s : np.ndarray
        Raw timestamps in seconds
    interpolation_summary : dict, optional
        Output from InterpolationLogger.get_summary()
    total_frames : int, optional
        Total number of frames (for fallback calculation)
        
    Returns
    -------
    dict with all step_02_* audit fields
    """
    logger.info("Running Gate 2: Signal Integrity & Temporal Quality")
    
    # Compute jitter
    jitter_result = compute_sample_jitter(time_s)
    
    # Compute interpolation fallback metrics if available
    if interpolation_summary is not None and total_frames is not None:
        interp_result = get_interpolation_fallback_metrics(interpolation_summary, total_frames)
    else:
        interp_result = {
            "step_02_fallback_count": 0,
            "step_02_fallback_frames": 0,
            "step_02_fallback_rate_percent": 0.0,
            "step_02_max_gap_frames": 0,
            "step_02_joints_with_fallbacks": [],
            "step_02_interpolation_status": "UNKNOWN",
            "step_02_interpolation_decision_reason": None
        }
    
    # Combine results
    result = {**jitter_result, **interp_result}
    
    # Determine overall Gate 2 status
    statuses = [jitter_result.get('step_02_jitter_status', 'PASS'),
                interp_result.get('step_02_interpolation_status', 'PASS')]
    
    if 'REJECT' in statuses:
        result['gate_02_status'] = 'REJECT'
    elif 'REVIEW' in statuses:
        result['gate_02_status'] = 'REVIEW'
    else:
        result['gate_02_status'] = 'PASS'
    
    # Collect decision reasons
    reasons = []
    if jitter_result.get('step_02_jitter_decision_reason'):
        reasons.append(jitter_result['step_02_jitter_decision_reason'])
    if interp_result.get('step_02_interpolation_decision_reason'):
        reasons.append(interp_result['step_02_interpolation_decision_reason'])
    
    result['gate_02_decision_reasons'] = reasons if reasons else None
    
    logger.info(f"  Gate 2 Result: {result['gate_02_status']}")
    
    return result


def run_gate_3(filter_summary: Dict) -> Dict[str, Any]:
    """
    Run Gate 3: Filtering Quality Assessment.
    
    Parameters
    ----------
    filter_summary : dict
        The filtering summary JSON (step_04)
        
    Returns
    -------
    dict with gate_03_* assessment fields
    """
    logger.info("Running Gate 3: Filtering Quality Assessment")
    
    filter_params = filter_summary.get('filter_params', {})
    
    winter_failed = filter_params.get('winter_analysis_failed', False)
    winter_reason = filter_params.get('winter_failure_reason')
    cutoff_hz = filter_params.get('filter_cutoff_hz', 0)
    filter_range = filter_params.get('filter_range_hz', [1, 16])
    
    # Determine status
    if winter_failed:
        status = 'REVIEW'
        reason = f"REVIEW: Filter Failure — {winter_reason}"
    elif cutoff_hz >= filter_range[1] - 1:
        status = 'REVIEW'
        reason = f"REVIEW: Filter at Maximum — Cutoff = {cutoff_hz} Hz"
    else:
        status = 'PASS'
        reason = None
    
    result = {
        'gate_03_status': status,
        'gate_03_decision_reason': reason,
        'gate_03_cutoff_hz': cutoff_hz,
        'gate_03_winter_failed': winter_failed,
        'gate_03_search_range_hz': filter_range
    }
    
    logger.info(f"  Gate 3 Result: {status}")
    
    return result


def run_gate_4(
    joint_names: List[str],
    max_quat_norm_err: float
) -> Dict[str, Any]:
    """
    Run Gate 4: ISB & Mathematical Compliance.
    
    Parameters
    ----------
    joint_names : list
        List of joint names
    max_quat_norm_err : float
        Maximum quaternion normalization error
        
    Returns
    -------
    dict with all step_06_euler_* and step_06_math_* fields
    """
    logger.info("Running Gate 4: ISB & Mathematical Compliance")
    
    # Get Euler sequences
    euler_result = get_euler_sequences_audit(joint_names)
    
    # Assess quaternion health
    quat_result = assess_quaternion_health(max_quat_norm_err)
    
    # Combine results
    result = {**euler_result, **quat_result}
    
    # Determine overall Gate 4 status
    result['gate_04_status'] = quat_result['step_06_math_status']
    result['gate_04_decision_reason'] = quat_result.get('step_06_math_decision_reason')
    
    logger.info(f"  Gate 4 Result: {result['gate_04_status']}")
    
    return result


def run_gate_5(
    angular_velocity: np.ndarray,
    fs: float,
    joint_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Run Gate 5: Gaga-Aware Burst Classification.
    
    Parameters
    ----------
    angular_velocity : np.ndarray
        Angular velocity array (N,) or (N, J) in deg/s
    fs : float
        Sampling frequency in Hz
    joint_names : list, optional
        Joint names corresponding to columns
        
    Returns
    -------
    dict with all step_06_burst_* fields
    """
    logger.info("Running Gate 5: Burst Classification")
    
    # Run classification
    classification_result = classify_burst_events(angular_velocity, fs, joint_names)
    
    # Generate audit fields
    audit_fields = generate_burst_audit_fields(classification_result)
    
    # Add overall gate status
    decision = classification_result['decision']
    audit_fields['gate_05_status'] = decision['overall_status']
    audit_fields['gate_05_decision_reason'] = decision['primary_reason']
    
    # Include raw classification result for advanced use
    audit_fields['_classification_result'] = classification_result
    
    logger.info(f"  Gate 5 Result: {audit_fields['gate_05_status']}")
    
    return audit_fields


def run_all_gates(
    time_s: np.ndarray,
    angular_velocity: np.ndarray,
    joint_names: List[str],
    fs: float,
    interpolation_summary: Optional[Dict] = None,
    filter_summary: Optional[Dict] = None,
    max_quat_norm_err: float = 0.0,
    total_frames: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run all gates (2-5) and return combined results.
    
    Parameters
    ----------
    time_s : np.ndarray
        Raw timestamps
    angular_velocity : np.ndarray
        Angular velocity (N, J) in deg/s
    joint_names : list
        Joint names
    fs : float
        Sampling frequency
    interpolation_summary : dict, optional
        From InterpolationLogger
    filter_summary : dict, optional
        Step 04 filtering summary
    max_quat_norm_err : float
        Maximum quaternion norm error
    total_frames : int, optional
        Total frames for fallback calculation
        
    Returns
    -------
    dict with all gate results combined
    """
    logger.info("="*60)
    logger.info("RUNNING ALL GATES (2-5)")
    logger.info("="*60)
    
    if total_frames is None:
        total_frames = len(time_s)
    
    results = {}
    
    # Gate 2: Temporal Quality
    gate_2 = run_gate_2(time_s, interpolation_summary, total_frames)
    results.update(gate_2)
    
    # Gate 3: Filtering (if filter_summary provided)
    if filter_summary is not None:
        gate_3 = run_gate_3(filter_summary)
        results.update(gate_3)
    
    # Gate 4: ISB Compliance
    gate_4 = run_gate_4(joint_names, max_quat_norm_err)
    results.update(gate_4)
    
    # Gate 5: Burst Classification
    gate_5 = run_gate_5(angular_velocity, fs, joint_names)
    results.update(gate_5)
    
    # Compute overall decision
    results['overall_gate_decision'] = get_overall_decision(results)
    
    logger.info("="*60)
    logger.info(f"OVERALL DECISION: {results['overall_gate_decision']['status']}")
    logger.info("="*60)
    
    return results


def get_overall_decision(gate_results: Dict) -> Dict[str, Any]:
    """
    Aggregate all gate decisions into final status.
    
    Priority: REJECT > REVIEW > PASS
    
    Parameters
    ----------
    gate_results : dict
        Combined gate results from run_all_gates()
        
    Returns
    -------
    dict with:
        - status: Overall status (PASS/REVIEW/REJECT)
        - reasons: List of all decision reasons
        - gate_statuses: Per-gate status summary
    """
    gate_statuses = {
        'gate_02': gate_results.get('gate_02_status', 'UNKNOWN'),
        'gate_03': gate_results.get('gate_03_status', 'UNKNOWN'),
        'gate_04': gate_results.get('gate_04_status', 'UNKNOWN'),
        'gate_05': gate_results.get('gate_05_status', 'UNKNOWN')
    }
    
    statuses = list(gate_statuses.values())
    
    # Collect all reasons
    reasons = []
    for key in ['gate_02_decision_reasons', 'gate_03_decision_reason', 
                'gate_04_decision_reason', 'gate_05_decision_reason']:
        val = gate_results.get(key)
        if val:
            if isinstance(val, list):
                reasons.extend(val)
            else:
                reasons.append(val)
    
    # Determine overall status
    if 'REJECT' in statuses:
        overall_status = 'REJECT'
    elif 'REVIEW' in statuses:
        overall_status = 'REVIEW'
    elif 'ACCEPT_HIGH_INTENSITY' in statuses:
        overall_status = 'ACCEPT_HIGH_INTENSITY'
    else:
        overall_status = 'PASS'
    
    return {
        'status': overall_status,
        'reasons': reasons if reasons else None,
        'gate_statuses': gate_statuses
    }


def print_gate_summary(gate_results: Dict):
    """Print human-readable gate summary."""
    print("\n" + "="*70)
    print("GATE QUALITY ASSESSMENT SUMMARY")
    print("="*70)
    
    overall = gate_results.get('overall_gate_decision', {})
    gate_statuses = overall.get('gate_statuses', {})
    
    print(f"\nGate 2 (Temporal Quality):    {gate_statuses.get('gate_02', 'N/A')}")
    print(f"Gate 3 (Filtering):           {gate_statuses.get('gate_03', 'N/A')}")
    print(f"Gate 4 (ISB Compliance):      {gate_statuses.get('gate_04', 'N/A')}")
    print(f"Gate 5 (Burst Classification): {gate_statuses.get('gate_05', 'N/A')}")
    
    print(f"\n{'='*70}")
    print(f"OVERALL: {overall.get('status', 'UNKNOWN')}")
    print(f"{'='*70}")
    
    reasons = overall.get('reasons')
    if reasons:
        print("\nDecision Reasons:")
        for r in reasons:
            print(f"  - {r}")
    
    print()
