"""
Logged Interpolation Fallback Tracker
=====================================
Per Winter (2009) and Cereatti et al. (2024) - "No Silent Fixes"

CRITICAL: Every fallback from high-fidelity to low-fidelity interpolation
must be logged and reported. Linear interpolation "flattens" acceleration
and is a scientific compromise that must be transparent.

Author: Gaga Motion Analysis Pipeline
Date: 2026-01-22
"""

import numpy as np
import pandas as pd
from datetime import datetime

# ============================================================
# INTERPOLATION METHOD HIERARCHY
# ============================================================

INTERPOLATION_HIERARCHY = {
    'pristine': {
        'rank': 0,
        'description': 'No interpolation required',
        'impact': 'None',
        'color': '✅',
        'accept': True
    },
    'cubic_spline': {
        'rank': 1,
        'description': 'Cubic spline interpolation',
        'impact': 'Minimal - preserves derivatives',
        'color': '✅',
        'accept': True
    },
    'slerp': {
        'rank': 1,
        'description': 'Spherical linear interpolation (quaternions)',
        'impact': 'Minimal - smooth rotation',
        'color': '✅',
        'accept': True
    },
    'linear': {
        'rank': 2,
        'description': 'Linear interpolation (FALLBACK)',
        'impact': 'MODERATE - acceleration artifacts',
        'color': '🟠',
        'accept': True  # Accept with warning
    },
    'linear_quaternion': {
        'rank': 2,
        'description': 'Linear quaternion + renormalization (FALLBACK)',
        'impact': 'MODERATE - rotation smoothness compromised',
        'color': '🟠',
        'accept': True  # Accept with warning
    },
    'failed': {
        'rank': 3,
        'description': 'Interpolation failed',
        'impact': 'CRITICAL - data gap remains',
        'color': '❌',
        'accept': False
    }
}


class InterpolationLogger:
    """
    Logger for tracking interpolation methods and fallbacks.
    """
    
    def __init__(self, run_id):
        self.run_id = run_id
        self.events = []
        self.per_joint_summary = {}
        
    def log_event(self, joint, column, method, gap_size, gap_start, gap_end, 
                  intended_method=None, reason=None):
        """
        Log an interpolation event.
        
        Parameters:
        -----------
        joint : str
            Joint name
        column : str
            Column name (e.g., 'Hips__px')
        method : str
            Method used (e.g., 'linear', 'cubic_spline')
        gap_size : int
            Size of gap in frames
        gap_start : int
            Start frame index
        gap_end : int
            End frame index
        intended_method : str, optional
            Method that was intended but failed
        reason : str, optional
            Reason for fallback
        """
        is_fallback = intended_method is not None and intended_method != method
        
        event = {
            'timestamp': datetime.now().isoformat(),
            'joint': joint,
            'column': column,
            'method_used': method,
            'intended_method': intended_method,
            'is_fallback': is_fallback,
            'gap_size': gap_size,
            'gap_start': gap_start,
            'gap_end': gap_end,
            'reason': reason if is_fallback else None
        }
        
        self.events.append(event)
        
        # Update per-joint summary
        if joint not in self.per_joint_summary:
            self.per_joint_summary[joint] = {
                'total_gaps': 0,
                'total_frames_interpolated': 0,
                'methods_used': set(),
                'fallback_count': 0,
                'max_gap_size': 0
            }
        
        summary = self.per_joint_summary[joint]
        summary['total_gaps'] += 1
        summary['total_frames_interpolated'] += gap_size
        summary['methods_used'].add(method)
        summary['max_gap_size'] = max(summary['max_gap_size'], gap_size)
        if is_fallback:
            summary['fallback_count'] += 1
    
    def get_fallback_events(self):
        """Get all fallback events."""
        return [e for e in self.events if e['is_fallback']]
    
    def get_summary(self):
        """
        Get summary report of all interpolation.
        
        Returns:
        --------
        dict : Summary with per-joint statistics and overall status
        """
        if not self.events:
            return {
                'run_id': self.run_id,
                'total_events': 0,
                'total_fallbacks': 0,
                'joints_with_fallbacks': [],
                'per_joint': {},
                'overall_status': 'PRISTINE'
            }
        
        fallback_events = self.get_fallback_events()
        joints_with_fallbacks = list(set(e['joint'] for e in fallback_events))
        
        # Determine overall status
        if len(fallback_events) == 0:
            overall_status = 'GOLD'
        elif len(fallback_events) < 5:
            overall_status = 'ACCEPTABLE'
        elif len(joints_with_fallbacks) < 3:
            overall_status = 'REVIEW'
        else:
            overall_status = 'CAUTION'
        
        # Convert per-joint summary
        per_joint_export = {}
        for joint, summary in self.per_joint_summary.items():
            per_joint_export[joint] = {
                'total_gaps': summary['total_gaps'],
                'total_frames_interpolated': summary['total_frames_interpolated'],
                'methods_used': list(summary['methods_used']),
                'fallback_count': summary['fallback_count'],
                'max_gap_size': summary['max_gap_size'],
                'primary_method': self._get_primary_method(summary['methods_used'])
            }
        
        return {
            'run_id': self.run_id,
            'total_events': len(self.events),
            'total_fallbacks': len(fallback_events),
            'joints_with_fallbacks': joints_with_fallbacks,
            'fallback_rate': len(fallback_events) / len(self.events) if self.events else 0,
            'per_joint': per_joint_export,
            'overall_status': overall_status,
            'fallback_events': fallback_events[:20]  # Limit to first 20 for JSON size
        }
    
    def _get_primary_method(self, methods_used):
        """Determine primary method from set of methods used."""
        if 'linear' in methods_used or 'linear_quaternion' in methods_used:
            return 'linear_fallback'
        elif 'cubic_spline' in methods_used:
            return 'cubic_spline'
        elif 'slerp' in methods_used:
            return 'slerp'
        else:
            return list(methods_used)[0] if methods_used else 'unknown'
    
    def print_report(self):
        """Print human-readable report."""
        summary = self.get_summary()
        
        print("\n" + "="*80)
        print("INTERPOLATION TRANSPARENCY REPORT (Winter 2009: No Silent Fixes)")
        print("="*80)
        print(f"Run ID: {self.run_id}")
        print(f"Total Interpolation Events: {summary['total_events']}")
        print(f"Fallback Events (High→Low Fidelity): {summary['total_fallbacks']}")
        print(f"Overall Status: {summary['overall_status']}")
        print()
        
        if summary['total_fallbacks'] > 0:
            print("🟠 FALLBACK EVENTS DETECTED:")
            print("-" * 80)
            for event in summary['fallback_events']:
                print(f"  Joint: {event['joint']}")
                print(f"    Intended: {event['intended_method']} → Used: {event['method_used']}")
                print(f"    Gap: {event['gap_size']} frames ({event['gap_start']}-{event['gap_end']})")
                print(f"    Reason: {event['reason']}")
                print()
        
        print("Per-Joint Summary:")
        print("-" * 80)
        for joint, stats in summary['per_joint'].items():
            if stats['fallback_count'] > 0:
                icon = "🟠"
            elif stats['total_gaps'] > 0:
                icon = "✅"
            else:
                icon = "⭐"
            print(f"{icon} {joint}:")
            print(f"    Total gaps: {stats['total_gaps']}, Frames interpolated: {stats['total_frames_interpolated']}")
            print(f"    Methods: {', '.join(stats['methods_used'])}")
            if stats['fallback_count'] > 0:
                print(f"    ⚠️  Fallbacks: {stats['fallback_count']}")
        
        print("="*80)
        
        return summary


def track_interpolation_with_logging(df, column, max_gap, method='cubic', logger=None, joint=None):
    """
    Perform interpolation with automatic fallback logging.
    
    Parameters:
    -----------
    df : pd.DataFrame or pd.Series
        Data to interpolate
    column : str
        Column name
    max_gap : int
        Maximum gap size to interpolate
    method : str
        Preferred method ('cubic', 'linear', 'slerp')
    logger : InterpolationLogger, optional
        Logger instance
    joint : str, optional
        Joint name for logging
        
    Returns:
    --------
    pd.Series : Interpolated data
    """
    series = df[column] if isinstance(df, pd.DataFrame) else df
    
    # Find gaps
    mask = series.isna()
    if not mask.any():
        return series  # No gaps
    
    # Identify gap regions
    gap_starts = np.where(mask & ~mask.shift(1, fill_value=False))[0]
    gap_ends = np.where(mask & ~mask.shift(-1, fill_value=False))[0]
    
    result = series.copy()
    
    for start, end in zip(gap_starts, gap_ends):
        gap_size = end - start + 1
        
        if gap_size > max_gap:
            # Gap too large, skip
            if logger and joint:
                logger.log_event(joint, column, 'failed', gap_size, start, end,
                               intended_method=method, reason=f'Gap size {gap_size} > max {max_gap}')
            continue
        
        # Try preferred method
        try:
            if method == 'cubic':
                # Cubic spline requires at least 4 points
                # Check if we have enough surrounding points
                before_points = (~mask[:start]).sum()
                after_points = (~mask[end+1:]).sum()
                
                if before_points >= 2 and after_points >= 2:
                    # Sufficient points for cubic
                    result = result.interpolate(method='cubic', limit=max_gap, limit_area='inside')
                    if logger and joint:
                        logger.log_event(joint, column, 'cubic_spline', gap_size, start, end)
                else:
                    # Fallback to linear
                    result = result.interpolate(method='linear', limit=max_gap, limit_area='inside')
                    if logger and joint:
                        logger.log_event(joint, column, 'linear', gap_size, start, end,
                                       intended_method='cubic_spline',
                                       reason='Insufficient surrounding points for cubic')
            else:
                # Linear interpolation
                result = result.interpolate(method='linear', limit=max_gap, limit_area='inside')
                if logger and joint:
                    logger.log_event(joint, column, 'linear', gap_size, start, end)
                    
        except Exception as e:
            # Interpolation failed
            if logger and joint:
                logger.log_event(joint, column, 'failed', gap_size, start, end,
                               intended_method=method, reason=str(e))
    
    return result
