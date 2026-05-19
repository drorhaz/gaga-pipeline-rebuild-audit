"""
Gaga-Aware 3-Tier Burst Classification Module
==============================================
Gate 5 Implementation: Classifies high angular velocity events by duration AND intensity.

Tier 1: ARTIFACT  (1-3 frames, <25ms)   - Physically impossible, EXCLUDE from stats
Tier 2: BURST     (4-7 frames, 33-58ms) - Potential whip/shake, REVIEW required
Tier 3: FLOW      (8+ frames, >65ms)    - Sustained intentional movement, ACCEPT

The module provides:
- Per-frame, per-joint status masking (0=Normal, 1=Artifact, 2=Burst, 3=Flow)
- Event density assessment (few events = OK, many = problem)
- Frame-level exclusion lists for downstream processing

References:
- Frame durations calculated at 120 Hz (8.33 ms/frame)
- 2000 deg/s threshold based on maximum human joint angular velocity literature
- 5000 deg/s sustained threshold for credibility check

Author: Gaga Motion Analysis Pipeline
Date: 2026-01-23
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

# Velocity thresholds (deg/s)
VELOCITY_TRIGGER = 2000.0      # Threshold to trigger burst analysis
VELOCITY_EXTREME = 5000.0      # Additional credibility check for sustained events

# Frame duration tiers (at 120 Hz: 1 frame = 8.33ms)
TIER_ARTIFACT_MAX = 3          # 1-3 frames = <25ms → ARTIFACT
TIER_BURST_MAX = 7             # 4-7 frames = 33-58ms → BURST
# 8+ frames = FLOW

# Status codes for joint_status_mask
STATUS_NORMAL = 0
STATUS_ARTIFACT = 1
STATUS_BURST = 2
STATUS_FLOW = 3

STATUS_NAMES = {
    STATUS_NORMAL: "NORMAL",
    STATUS_ARTIFACT: "ARTIFACT",
    STATUS_BURST: "BURST",
    STATUS_FLOW: "FLOW"
}

# Event density thresholds (for data quality assessment)
# TASK 2: Updated "Outlier Policy" - >5% outliers triggers REVIEW
EVENT_DENSITY_THRESHOLDS = {
    'outlier_rate_review': 5.0,       # >5% total outlier frames = REVIEW (NEW)
    'artifact_rate_warn': 0.1,        # >0.1% frames as artifact = REVIEW
    'artifact_rate_reject': 1.0,      # >1.0% frames as artifact = REJECT (Overall_Status change)
    'burst_events_per_min_warn': 5,   # >5 burst events/min = REVIEW
    'burst_events_per_min_reject': 15,# >15 burst events/min = REJECT
    'total_events_warn': 20,          # >20 total events = REVIEW
    'total_events_reject': 50,        # >50 total events = REJECT
}


# =============================================================================
# CORE CLASSIFICATION FUNCTIONS
# =============================================================================

def classify_burst_events(
    angular_velocity: np.ndarray,
    fs: float,
    joint_names: Optional[List[str]] = None,
    velocity_trigger: float = VELOCITY_TRIGGER,
    velocity_extreme: float = VELOCITY_EXTREME
) -> Dict[str, Any]:
    """
    Classify high-velocity events into 3 tiers (Gate 5 main function).
    
    Parameters
    ----------
    angular_velocity : np.ndarray
        Angular velocity array (N,) for single joint or (N, J) for multiple joints.
        Units: deg/s (absolute values will be taken internally)
    fs : float
        Sampling frequency in Hz
    joint_names : List[str], optional
        Joint names corresponding to columns. If None, uses indices.
    velocity_trigger : float
        Threshold to trigger analysis (default 2000 deg/s)
    velocity_extreme : float
        Threshold for extreme sustained velocity check (default 5000 deg/s)
        
    Returns
    -------
    dict with:
        - joint_status_mask: (N, J) int8 array (0=Normal, 1=Artifact, 2=Burst, 3=Flow)
        - events: List of event dictionaries with frame details
        - summary: Aggregate statistics
        - density: Event density assessment
        - decision: Overall decision and reason
        - frames_to_exclude: List of frame indices to exclude (Tier 1)
        - frames_to_review: List of frame indices to review (Tier 2/3 flagged)
        - data_validity: Dict with usability assessment
    """
    # Ensure 2D: (frames, joints)
    angular_velocity = np.asarray(angular_velocity)
    if angular_velocity.ndim == 1:
        angular_velocity = angular_velocity[:, np.newaxis]
    
    n_frames, n_joints = angular_velocity.shape
    frame_duration_ms = 1000 / fs
    
    # Default joint names
    if joint_names is None:
        joint_names = [f"Joint_{j}" for j in range(n_joints)]
    
    logger.info(f"Gate 5: Classifying burst events for {n_joints} joints, {n_frames} frames")
    logger.info(f"  Velocity trigger: {velocity_trigger} deg/s, Extreme: {velocity_extreme} deg/s")
    
    # Initialize joint status mask: 0=Normal, 1=Artifact, 2=Burst, 3=Flow
    joint_status_mask = np.zeros((n_frames, n_joints), dtype=np.int8)
    
    # Track all events
    events = []
    
    for j in range(n_joints):
        vel = np.abs(angular_velocity[:, j])
        above_trigger = vel > velocity_trigger
        
        # Find consecutive runs of high velocity
        runs = _find_consecutive_runs(above_trigger)
        
        for start, end in runs:
            duration_frames = end - start
            duration_ms = duration_frames * frame_duration_ms
            max_vel = float(np.nanmax(vel[start:end]))
            mean_vel = float(np.nanmean(vel[start:end]))
            
            # Classify tier based on duration
            if duration_frames <= TIER_ARTIFACT_MAX:
                tier = STATUS_ARTIFACT
                tier_name = "ARTIFACT"
                status = "REVIEW"
                action = "EXCLUDE"
            elif duration_frames <= TIER_BURST_MAX:
                tier = STATUS_BURST
                tier_name = "BURST"
                status = "REVIEW"
                action = "INCLUDE_FLAGGED"
            else:
                tier = STATUS_FLOW
                tier_name = "FLOW"
                # Additional check: extreme sustained velocity is suspicious
                if mean_vel > velocity_extreme:
                    status = "REVIEW"
                    action = "INCLUDE_FLAGGED"
                else:
                    status = "ACCEPT_HIGH_INTENSITY"
                    action = "INCLUDE"
            
            # Mark frames in mask
            joint_status_mask[start:end, j] = tier
            
            events.append({
                'event_id': len(events) + 1,
                'joint': joint_names[j],
                'joint_idx': j,
                'start_frame': int(start),
                'end_frame': int(end),
                'duration_frames': int(duration_frames),
                'duration_ms': round(duration_ms, 2),
                'max_velocity_deg_s': round(max_vel, 2),
                'mean_velocity_deg_s': round(mean_vel, 2),
                'tier': int(tier),
                'tier_name': tier_name,
                'status': status,
                'action': action
            })
    
    # Calculate summary statistics
    summary = _compute_summary(events, n_frames, fs)
    
    # Assess event density
    density = _assess_event_density(events, n_frames, fs)
    
    # Determine overall decision
    decision = _determine_overall_decision(events, density)
    
    # Get frames to exclude (Tier 1 only)
    frames_to_exclude = sorted(set(
        frame 
        for e in events if e['tier'] == STATUS_ARTIFACT 
        for frame in range(e['start_frame'], e['end_frame'])
    ))
    
    # Get frames to review (Tier 2 and Tier 3 with extreme velocity)
    frames_to_review = sorted(set(
        frame 
        for e in events if e['tier'] == STATUS_BURST or (e['tier'] == STATUS_FLOW and e['status'] == 'REVIEW')
        for frame in range(e['start_frame'], e['end_frame'])
    ))
    
    logger.info(f"Gate 5 Results: {len(events)} events detected")
    logger.info(f"  Artifacts: {summary['artifact_count']}, Bursts: {summary['burst_count']}, Flows: {summary['flow_count']}")
    logger.info(f"  Frames to exclude: {len(frames_to_exclude)}, Frames to review: {len(frames_to_review)}")
    logger.info(f"  Decision: {decision['overall_status']} - {decision['primary_reason']}")
    
    return {
        'joint_status_mask': joint_status_mask,
        'events': events,
        'summary': summary,
        'density': density,
        'decision': decision,
        'frames_to_exclude': frames_to_exclude,
        'frames_to_review': frames_to_review,
        'data_validity': {
            'usable': decision['overall_status'] != 'REJECT',
            'excluded_frame_count': len(frames_to_exclude),
            'excluded_frame_percent': round(100 * len(frames_to_exclude) / n_frames, 4) if n_frames > 0 else 0,
            'note': f"{len(frames_to_exclude)} artifact frames excluded; burst/flow frames preserved"
        },
        'config': {
            'velocity_trigger_deg_s': velocity_trigger,
            'velocity_extreme_deg_s': velocity_extreme,
            'tier_artifact_max_frames': TIER_ARTIFACT_MAX,
            'tier_burst_max_frames': TIER_BURST_MAX,
            'fs_hz': fs
        }
    }


def _find_consecutive_runs(mask: np.ndarray) -> List[Tuple[int, int]]:
    """
    Find start/end indices of consecutive True values.
    
    Parameters
    ----------
    mask : np.ndarray
        Boolean mask array
        
    Returns
    -------
    list of (start, end) tuples where end is exclusive
    """
    runs = []
    in_run = False
    start = 0
    
    for i, val in enumerate(mask):
        if val and not in_run:
            start = i
            in_run = True
        elif not val and in_run:
            runs.append((start, i))
            in_run = False
    
    if in_run:
        runs.append((start, len(mask)))
    
    return runs


def _compute_summary(events: List[Dict], n_frames: int, fs: float) -> Dict:
    """Compute aggregate statistics from events."""
    if not events:
        return {
            'total_events': 0,
            'artifact_count': 0,
            'burst_count': 0,
            'flow_count': 0,
            'artifact_frames': 0,
            'burst_frames': 0,
            'flow_frames': 0,
            'artifact_rate_percent': 0.0,
            'outlier_frames_total': 0,
            'outlier_rate_percent': 0.0,
            'max_consecutive_frames': 0,
            'mean_event_duration_ms': 0.0,
            'max_event_duration_ms': 0.0,
            'recording_duration_sec': n_frames / fs if fs > 0 else 0
        }
    
    artifact_events = [e for e in events if e['tier'] == STATUS_ARTIFACT]
    burst_events = [e for e in events if e['tier'] == STATUS_BURST]
    flow_events = [e for e in events if e['tier'] == STATUS_FLOW]
    
    artifact_frames = sum(e['duration_frames'] for e in artifact_events)
    burst_frames = sum(e['duration_frames'] for e in burst_events)
    flow_frames = sum(e['duration_frames'] for e in flow_events)
    
    durations_ms = [e['duration_ms'] for e in events]
    durations_frames = [e['duration_frames'] for e in events]
    
    return {
        'total_events': len(events),
        'artifact_count': len(artifact_events),
        'burst_count': len(burst_events),
        'flow_count': len(flow_events),
        'artifact_frames': artifact_frames,
        'burst_frames': burst_frames,
        'flow_frames': flow_frames,
        'artifact_rate_percent': round(100 * artifact_frames / n_frames, 4) if n_frames > 0 else 0,
        'outlier_frames_total': artifact_frames + burst_frames + flow_frames,
        'outlier_rate_percent': round(100 * (artifact_frames + burst_frames + flow_frames) / n_frames, 4) if n_frames > 0 else 0,
        'max_consecutive_frames': max(durations_frames) if durations_frames else 0,
        'mean_event_duration_ms': round(float(np.mean(durations_ms)), 2) if durations_ms else 0,
        'max_event_duration_ms': round(float(np.max(durations_ms)), 2) if durations_ms else 0,
        'recording_duration_sec': n_frames / fs if fs > 0 else 0
    }


def _assess_event_density(events: List[Dict], n_frames: int, fs: float) -> Dict:
    """
    Assess if event frequency indicates data quality issue.
    
    TASK 2: Updated "Outlier Policy" Implementation
    - >5% total outlier frames = REVIEW
    - >1% artifact rate = Overall_Status FAIL
    
    Logic: Isolated events = OK (real movement), Many events = Problem (noise/sensor issue)
    """
    duration_sec = n_frames / fs if fs > 0 else 0
    duration_min = duration_sec / 60 if duration_sec > 0 else 0
    
    if not events:
        return {
            'status': 'PASS',
            'reason': 'No high-velocity events detected',
            'metrics': {
                'artifact_frames': 0,
                'artifact_rate_percent': 0.0,
                'outlier_frames_total': 0,
                'outlier_rate_percent': 0.0,
                'burst_events': 0,
                'burst_events_per_min': 0.0,
                'total_events': 0,
                'recording_duration_min': round(duration_min, 2)
            }
        }
    
    artifact_frames = sum(e['duration_frames'] for e in events if e['tier'] == STATUS_ARTIFACT)
    burst_frames = sum(e['duration_frames'] for e in events if e['tier'] == STATUS_BURST)
    flow_frames = sum(e['duration_frames'] for e in events if e['tier'] == STATUS_FLOW)
    outlier_frames_total = artifact_frames + burst_frames + flow_frames
    
    burst_events = sum(1 for e in events if e['tier'] == STATUS_BURST)
    
    artifact_rate = 100 * artifact_frames / n_frames if n_frames > 0 else 0
    outlier_rate = 100 * outlier_frames_total / n_frames if n_frames > 0 else 0
    burst_per_min = burst_events / duration_min if duration_min > 0 else 0
    
    flags = []
    
    # TASK 2: Check total outlier percentage (NEW)
    if outlier_rate > EVENT_DENSITY_THRESHOLDS['outlier_rate_review']:
        flags.append(('REVIEW', f'Total outlier rate {outlier_rate:.2f}% > 5% threshold'))
    
    # Check artifact rate - >1% triggers FAIL in Overall_Status
    if artifact_rate > EVENT_DENSITY_THRESHOLDS['artifact_rate_reject']:
        flags.append(('REJECT', f'Artifact rate {artifact_rate:.2f}% > 1% threshold (High Artifact Rate)'))
    elif artifact_rate > EVENT_DENSITY_THRESHOLDS['artifact_rate_warn']:
        flags.append(('REVIEW', f'Artifact rate {artifact_rate:.2f}% > 0.1% threshold'))
    
    # Check burst frequency
    if burst_per_min > EVENT_DENSITY_THRESHOLDS['burst_events_per_min_reject']:
        flags.append(('REJECT', f'Burst frequency {burst_per_min:.1f}/min > 15/min'))
    elif burst_per_min > EVENT_DENSITY_THRESHOLDS['burst_events_per_min_warn']:
        flags.append(('REVIEW', f'Burst frequency {burst_per_min:.1f}/min > 5/min'))
    
    # Check total events
    if len(events) > EVENT_DENSITY_THRESHOLDS['total_events_reject']:
        flags.append(('REJECT', f'Total events {len(events)} > 50'))
    elif len(events) > EVENT_DENSITY_THRESHOLDS['total_events_warn']:
        flags.append(('REVIEW', f'Total events {len(events)} > 20'))
    
    # Determine status
    if any(f[0] == 'REJECT' for f in flags):
        status = 'REJECT'
        reason = 'REJECT: ' + '; '.join(f[1] for f in flags if f[0] == 'REJECT')
    elif any(f[0] == 'REVIEW' for f in flags):
        status = 'REVIEW'
        reason = 'REVIEW: ' + '; '.join(f[1] for f in flags if f[0] == 'REVIEW')
    else:
        status = 'PASS'
        reason = f'Event density acceptable: {len(events)} events in {duration_min:.1f} min'
    
    return {
        'status': status,
        'reason': reason,
        'metrics': {
            'artifact_frames': artifact_frames,
            'artifact_rate_percent': round(artifact_rate, 4),
            'outlier_frames_total': outlier_frames_total,
            'outlier_rate_percent': round(outlier_rate, 4),
            'burst_events': burst_events,
            'burst_events_per_min': round(burst_per_min, 2),
            'total_events': len(events),
            'recording_duration_min': round(duration_min, 2)
        }
    }


def _determine_overall_decision(events: List[Dict], density: Dict) -> Dict:
    """
    Determine overall decision based on events and density.
    
    TASK 2: Updated decision logic - Overall_Status FAIL on High Artifact Rate (>1%)
    """
    if not events:
        return {
            'overall_status': 'PASS',
            'primary_reason': 'No high-velocity events detected'
        }
    
    # TASK 2: Density-based rejection takes priority - High Artifact Rate = FAIL
    if density['status'] == 'REJECT':
        # Check if it's specifically artifact rate that caused rejection
        artifact_rate = density['metrics'].get('artifact_rate_percent', 0)
        if artifact_rate > EVENT_DENSITY_THRESHOLDS['artifact_rate_reject']:
            return {
                'overall_status': 'FAIL',
                'primary_reason': f'High Artifact Rate: {artifact_rate:.2f}% > 1.0% threshold (Overall_Status = FAIL)'
            }
        else:
            return {
                'overall_status': 'REJECT',
                'primary_reason': density['reason']
            }
    
    # Check for artifacts
    artifact_count = sum(1 for e in events if e['tier'] == STATUS_ARTIFACT)
    if artifact_count > 0:
        return {
            'overall_status': 'REVIEW',
            'primary_reason': f'REVIEW: High-Speed Artifact — {artifact_count} events with <25ms duration (physically impossible)'
        }
    
    # Check for bursts
    burst_count = sum(1 for e in events if e['tier'] == STATUS_BURST)
    if burst_count > 0:
        return {
            'overall_status': 'REVIEW',
            'primary_reason': f'REVIEW: High-Speed Burst — {burst_count} events with 33-58ms duration (visual audit required)'
        }
    
    # Check for extreme sustained velocity in flows
    extreme_flows = [e for e in events if e['tier'] == STATUS_FLOW and e['mean_velocity_deg_s'] > VELOCITY_EXTREME]
    if extreme_flows:
        return {
            'overall_status': 'REVIEW',
            'primary_reason': f'REVIEW: Extreme Sustained Velocity — {len(extreme_flows)} flow events with mean > {VELOCITY_EXTREME} deg/s'
        }
    
    # Density-based review
    if density['status'] == 'REVIEW':
        return {
            'overall_status': 'REVIEW',
            'primary_reason': density['reason']
        }
    
    # All flows are acceptable
    flow_count = sum(1 for e in events if e['tier'] == STATUS_FLOW)
    return {
        'overall_status': 'ACCEPT_HIGH_INTENSITY',
        'primary_reason': f'High-intensity movement confirmed: {flow_count} sustained flow events (>65ms each)'
    }


# =============================================================================
# OUTPUT GENERATION FUNCTIONS
# =============================================================================

def generate_burst_audit_fields(classification_result: Dict) -> Dict:
    """
    Generate Gate 5 audit log fields from classification result.
    
    Parameters
    ----------
    classification_result : dict
        Output from classify_burst_events()
        
    Returns
    -------
    dict with step_06_burst_* fields for audit log
    """
    summary = classification_result['summary']
    density = classification_result['density']
    decision = classification_result['decision']
    data_validity = classification_result['data_validity']
    
    return {
        "step_06_burst_analysis": {
            "classification": {
                "artifact_count": summary['artifact_count'],
                "burst_count": summary['burst_count'],
                "flow_count": summary['flow_count'],
                "total_events": summary['total_events']
            },
            "frame_statistics": {
                "total_frames": int(summary['recording_duration_sec'] * classification_result['config']['fs_hz']),
                "artifact_frames": summary['artifact_frames'],
                "burst_frames": summary['burst_frames'],
                "flow_frames": summary['flow_frames'],
                "artifact_rate_percent": summary['artifact_rate_percent'],
                "outlier_frames_total": summary['outlier_frames_total'],
                "outlier_rate_percent": summary['outlier_rate_percent']
            },
            "timing": {
                "recording_duration_sec": summary['recording_duration_sec'],
                "burst_events_per_min": density['metrics']['burst_events_per_min'],
                "max_consecutive_frames": summary['max_consecutive_frames'],
                "mean_event_duration_ms": summary['mean_event_duration_ms'],
                "max_event_duration_ms": summary['max_event_duration_ms']
            },
            "density_assessment": {
                "status": density['status'],
                "reason": density['reason']
            },
            "events": classification_result['events'][:50]  # Limit to first 50 for JSON size
        },
        "step_06_burst_decision": {
            "overall_status": decision['overall_status'],
            "primary_reason": decision['primary_reason']
        },
        "step_06_frames_to_exclude": classification_result['frames_to_exclude'][:1000],  # Limit for JSON
        "step_06_frames_to_review": classification_result['frames_to_review'][:1000],
        "step_06_data_validity": data_validity
    }


def create_joint_status_dataframe(
    time_s: np.ndarray,
    angular_velocity: np.ndarray,
    joint_names: List[str],
    classification_result: Dict
) -> 'pd.DataFrame':
    """
    Generate DataFrame with per-frame joint status for output.
    
    Output columns:
    - frame_idx: Frame number (0-indexed)
    - time_s: Timestamp
    - {Joint}__status: Status code (0=Normal, 1=Artifact, 2=Burst, 3=Flow)
    - {Joint}__velocity_deg_s: Angular velocity at frame
    - any_outlier: True if any joint has status > 0
    - max_tier: Highest tier across all joints
    
    Parameters
    ----------
    time_s : np.ndarray
        Timestamps
    angular_velocity : np.ndarray
        Angular velocity array (N, J)
    joint_names : list
        Joint names
    classification_result : dict
        Output from classify_burst_events()
        
    Returns
    -------
    pd.DataFrame
    """
    import pandas as pd
    
    n_frames = len(time_s)
    mask = classification_result['joint_status_mask']
    
    # Ensure angular_velocity is 2D
    if angular_velocity.ndim == 1:
        angular_velocity = angular_velocity[:, np.newaxis]
    
    data = {
        'frame_idx': np.arange(n_frames),
        'time_s': time_s
    }
    
    for j, joint in enumerate(joint_names):
        data[f'{joint}__status'] = mask[:, j]
        data[f'{joint}__velocity_deg_s'] = np.abs(angular_velocity[:, j])
    
    df = pd.DataFrame(data)
    
    # Add aggregate columns
    status_cols = [f'{j}__status' for j in joint_names]
    df['any_outlier'] = (df[status_cols] > 0).any(axis=1)
    df['max_tier'] = df[status_cols].max(axis=1)
    
    return df


def apply_artifact_exclusion(data: np.ndarray, frames_to_exclude: List[int]) -> np.ndarray:
    """
    Apply artifact frame exclusion by setting excluded frames to NaN.
    
    Use this for computing statistics that should exclude Tier 1 artifacts.
    
    Parameters
    ----------
    data : np.ndarray
        Data array (N,) or (N, J)
    frames_to_exclude : list
        Frame indices to exclude (Tier 1 artifacts)
        
    Returns
    -------
    np.ndarray
        Data with excluded frames set to NaN
    """
    data_clean = data.astype(float).copy()
    
    if len(frames_to_exclude) == 0:
        return data_clean
    
    # Validate indices
    valid_indices = [i for i in frames_to_exclude if 0 <= i < len(data_clean)]
    
    if data_clean.ndim == 1:
        data_clean[valid_indices] = np.nan
    else:
        data_clean[valid_indices, :] = np.nan
    
    return data_clean


def compute_clean_statistics(
    angular_velocity: np.ndarray,
    classification_result: Dict,
    joint_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compute statistics with artifact frames excluded.
    
    This provides "clean" metrics that ignore short noise/artifacts (Tier 1),
    giving a more accurate picture of the actual movement quality.
    
    Parameters
    ----------
    angular_velocity : np.ndarray
        Angular velocity array (N,) or (N, J) in deg/s
    classification_result : dict
        Output from classify_burst_events()
    joint_names : list, optional
        Joint names for per-joint statistics
        
    Returns
    -------
    dict with:
        - raw_statistics: Stats including all frames
        - clean_statistics: Stats with artifacts excluded
        - comparison: Difference between raw and clean
        - per_joint_clean: Per-joint clean statistics (if joint_names provided)
    """
    # Ensure 2D
    angular_velocity = np.asarray(angular_velocity)
    if angular_velocity.ndim == 1:
        angular_velocity = angular_velocity[:, np.newaxis]
    
    n_frames, n_joints = angular_velocity.shape
    frames_to_exclude = classification_result.get('frames_to_exclude', [])
    
    # Default joint names
    if joint_names is None:
        joint_names = [f"Joint_{j}" for j in range(n_joints)]
    
    # Compute RAW statistics (all frames)
    raw_max = float(np.nanmax(np.abs(angular_velocity)))
    raw_mean = float(np.nanmean(np.abs(angular_velocity)))
    raw_std = float(np.nanstd(np.abs(angular_velocity)))
    raw_p95 = float(np.nanpercentile(np.abs(angular_velocity), 95))
    raw_p99 = float(np.nanpercentile(np.abs(angular_velocity), 99))
    
    # Apply artifact exclusion
    vel_clean = apply_artifact_exclusion(angular_velocity, frames_to_exclude)
    
    # Compute CLEAN statistics (artifacts excluded)
    clean_max = float(np.nanmax(np.abs(vel_clean)))
    clean_mean = float(np.nanmean(np.abs(vel_clean)))
    clean_std = float(np.nanstd(np.abs(vel_clean)))
    clean_p95 = float(np.nanpercentile(np.abs(vel_clean), 95))
    clean_p99 = float(np.nanpercentile(np.abs(vel_clean), 99))
    
    # Per-joint clean statistics
    per_joint_clean = {}
    for j, joint in enumerate(joint_names):
        joint_vel = vel_clean[:, j]
        valid_frames = np.sum(~np.isnan(joint_vel))
        if valid_frames > 0:
            per_joint_clean[joint] = {
                'max_deg_s': round(float(np.nanmax(np.abs(joint_vel))), 2),
                'mean_deg_s': round(float(np.nanmean(np.abs(joint_vel))), 2),
                'std_deg_s': round(float(np.nanstd(np.abs(joint_vel))), 2),
                'p95_deg_s': round(float(np.nanpercentile(np.abs(joint_vel), 95)), 2),
                'valid_frames': int(valid_frames),
                'excluded_frames': int(n_frames - valid_frames)
            }
    
    result = {
        'raw_statistics': {
            'max_deg_s': round(raw_max, 2),
            'mean_deg_s': round(raw_mean, 2),
            'std_deg_s': round(raw_std, 2),
            'p95_deg_s': round(raw_p95, 2),
            'p99_deg_s': round(raw_p99, 2),
            'total_frames': n_frames
        },
        'clean_statistics': {
            'max_deg_s': round(clean_max, 2),
            'mean_deg_s': round(clean_mean, 2),
            'std_deg_s': round(clean_std, 2),
            'p95_deg_s': round(clean_p95, 2),
            'p99_deg_s': round(clean_p99, 2),
            'valid_frames': n_frames - len(frames_to_exclude),
            'excluded_frames': len(frames_to_exclude)
        },
        'comparison': {
            'max_reduction_deg_s': round(raw_max - clean_max, 2),
            'max_reduction_percent': round(100 * (raw_max - clean_max) / raw_max, 2) if raw_max > 0 else 0,
            'mean_reduction_deg_s': round(raw_mean - clean_mean, 2),
            'artifacts_removed': len(frames_to_exclude),
            'data_retained_percent': round(100 * (n_frames - len(frames_to_exclude)) / n_frames, 4) if n_frames > 0 else 100
        },
        'per_joint_clean': per_joint_clean
    }
    
    # Log the comparison
    if len(frames_to_exclude) > 0:
        logger.info(f"Clean statistics computed: {len(frames_to_exclude)} artifact frames excluded")
        logger.info(f"  Max velocity: {raw_max:.1f} (raw) → {clean_max:.1f} (clean), "
                   f"reduction: {result['comparison']['max_reduction_percent']:.1f}%")
    
    return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_tier_name(tier_code: int) -> str:
    """Get human-readable tier name from code."""
    return STATUS_NAMES.get(tier_code, "UNKNOWN")


def summarize_classification(classification_result: Dict) -> str:
    """Generate human-readable summary of classification."""
    summary = classification_result['summary']
    decision = classification_result['decision']
    
    lines = [
        "=" * 60,
        "GATE 5: BURST CLASSIFICATION SUMMARY",
        "=" * 60,
        f"Total Events: {summary['total_events']}",
        f"  - Artifacts (Tier 1): {summary['artifact_count']} ({summary['artifact_frames']} frames)",
        f"  - Bursts (Tier 2): {summary['burst_count']} ({summary['burst_frames']} frames)",
        f"  - Flows (Tier 3): {summary['flow_count']} ({summary['flow_frames']} frames)",
        "",
        f"Artifact Rate: {summary['artifact_rate_percent']:.4f}%",
        f"Max Consecutive Frames: {summary['max_consecutive_frames']}",
        f"Mean Event Duration: {summary['mean_event_duration_ms']:.1f} ms",
        "",
        f"DECISION: {decision['overall_status']}",
        f"REASON: {decision['primary_reason']}",
        "=" * 60
    ]
    
    return "\n".join(lines)
