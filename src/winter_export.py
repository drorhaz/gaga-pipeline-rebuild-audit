"""
Enhancement 3: Winter Residual Curve Data Export
Required for Section 4: Winter's Residual Validation

Exports the RMS residual vs. cutoff frequency curve data
so the Master Audit can plot it inline with knee point marked.
"""

import numpy as np
import json
import os

def export_winter_residual_data(winter_metadata, run_id, save_dir):
    """
    Export Winter residual analysis curve data for Master Audit plotting.
    
    Parameters:
    -----------
    winter_metadata : dict
        Metadata from apply_winter_filter containing:
        - cutoff_hz: Selected cutoff frequency
        - fmin, fmax: Frequency search range  
        - residual_curve: RMS residuals at each tested frequency (if available)
        - rep_col: Representative column used
        
    run_id : str
        Run identifier
        
    save_dir : str
        Output directory
        
    Returns:
    --------
    str : Path to saved JSON file
    """
    
    # Extract residual curve data if available
    # Note: This requires the filtering module to store the residual curve
    # If not available, we'll note that for future enhancement
    
    cutoff_hz = winter_metadata.get('cutoff_hz', None)
    fmin = winter_metadata.get('fmin', 1)
    fmax = winter_metadata.get('fmax', 12)
    
    # Check if residual curve data is available
    if 'residual_curve' in winter_metadata:
        # Residual curve is available - use it directly
        residual_curve = winter_metadata['residual_curve']
        cutoff_frequencies = residual_curve.get('frequencies', list(range(fmin, fmax + 1)))
        rms_residuals = residual_curve.get('residuals', [])
    else:
        # Residual curve not available - create placeholder structure
        # This will be populated when filtering module is enhanced
        cutoff_frequencies = list(range(fmin, fmax + 1))
        rms_residuals = []  # Empty - needs to be added to filtering module
    
    # Determine if knee point was found
    knee_point_found = (cutoff_hz is not None and 
                       cutoff_hz < fmax - 1 and 
                       not winter_metadata.get('winter_analysis_failed', False))
    
    winter_data = {
        'run_id': run_id,
        'cutoff_frequencies_hz': cutoff_frequencies,
        'rms_residuals': rms_residuals,
        'knee_point_hz': float(cutoff_hz) if cutoff_hz is not None else None,
        'knee_point_found': knee_point_found,
        'representative_signal': winter_metadata.get('rep_col', 'N/A'),
        'analysis_method': 'kneedle_algorithm',
        'frequency_range': [int(fmin), int(fmax)],
        'data_available': len(rms_residuals) > 0,
        'note': 'Residual curve data populated by filtering module' if len(rms_residuals) > 0 
                else 'Placeholder - residual curve to be added to filtering module'
    }
    
    # Save to JSON
    output_path = os.path.join(save_dir, f"{run_id}__winter_residual_data.json")
    with open(output_path, 'w') as f:
        json.dump(winter_data, f, indent=2)
    
    return output_path


def save_residual_curve_to_metadata(frequencies, residuals, winter_metadata):
    """
    Helper function to add residual curve data to winter_metadata.
    This should be called within the filtering module.
    
    Parameters:
    -----------
    frequencies : list
        List of tested cutoff frequencies
    residuals : list  
        RMS residual values at each frequency
    winter_metadata : dict
        Winter metadata dict to update
        
    Returns:
    --------
    dict : Updated winter_metadata with residual_curve added
    """
    winter_metadata['residual_curve'] = {
        'frequencies': frequencies,
        'residuals': residuals
    }
    return winter_metadata
