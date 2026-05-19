"""
Signal-to-Noise Ratio (SNR) Quantification
==========================================
Per Cereatti et al. (2024) - Objective signal quality assessment

CRITICAL: SNR provides a numerical "Health Score" for each joint.
Low SNR indicates poor tracking quality that may compromise biomechanical analysis.

Author: Gaga Motion Analysis Pipeline
Date: 2026-01-22
"""

import numpy as np
import pandas as pd
from scipy import signal as sp_signal

# ============================================================
# SNR THRESHOLDS (in dB)
# ============================================================

SNR_THRESHOLDS = {
    'excellent': 30.0,  # SNR > 30 dB: Publication-quality
    'good': 20.0,       # SNR 20-30 dB: Acceptable for research
    'acceptable': 15.0, # SNR 15-20 dB: Review recommended
    'poor': 10.0,       # SNR 10-15 dB: Caution advised
    'reject': 10.0      # SNR < 10 dB: Reject
}


def compute_signal_power(data, axis=0):
    """
    Compute signal power (RMS squared).
    
    Parameters:
    -----------
    data : np.ndarray
        Signal data
    axis : int
        Axis along which to compute power
        
    Returns:
    --------
    float : Signal power
    """
    return np.mean(data**2, axis=axis)


def compute_snr_from_residuals(signal_raw, signal_filtered, method='rms'):
    """
    Compute SNR from raw and filtered signals.
    
    SNR = 10 * log10(Power_signal / Power_noise)
    where noise is the residual: raw - filtered
    
    Parameters:
    -----------
    signal_raw : np.ndarray
        Raw signal
    signal_filtered : np.ndarray
        Filtered signal
    method : str
        'rms' or 'psd' (power spectral density)
        
    Returns:
    --------
    float : SNR in dB
    """
    # Remove NaN values
    valid_mask = ~(np.isnan(signal_raw) | np.isnan(signal_filtered))
    signal_raw = signal_raw[valid_mask]
    signal_filtered = signal_filtered[valid_mask]
    
    if len(signal_raw) < 10:
        return np.nan
    
    # Compute residual (noise)
    residual = signal_raw - signal_filtered
    
    # Compute powers
    signal_power = compute_signal_power(signal_filtered)
    noise_power = compute_signal_power(residual)
    
    # Avoid division by zero
    if noise_power < 1e-12:
        return 100.0  # Essentially no noise
    
    # SNR in dB
    snr_db = 10 * np.log10(signal_power / noise_power)
    
    return float(snr_db)


def compute_true_raw_snr(signal_raw, fs, signal_band=(0.5, 10), noise_band=(15, 50)):
    """
    Compute TRUE SNR from raw data only (no filtering required).
    
    This measures the inherent quality of the captured data by comparing
    power in the movement frequency band vs high-frequency noise band.
    
    Parameters:
    -----------
    signal_raw : np.ndarray
        Raw signal (before any filtering)
    fs : float
        Sampling frequency (Hz)
    signal_band : tuple
        Frequency band for human movement signal (Hz). Default 0.5-10 Hz
        covers voluntary human movement per Winter (2009).
    noise_band : tuple
        Frequency band for noise estimation (Hz). Default 15-50 Hz
        is above voluntary movement but below Nyquist for 120 Hz capture.
        
    Returns:
    --------
    dict : SNR results with signal/noise power breakdown
    """
    # Remove NaN values
    valid_mask = ~np.isnan(signal_raw)
    signal_raw = signal_raw[valid_mask]
    
    if len(signal_raw) < 100:
        return {'snr_db': np.nan, 'signal_power': np.nan, 'noise_power': np.nan}
    
    # Compute PSD using Welch's method on RAW data
    f, psd = sp_signal.welch(signal_raw, fs=fs, nperseg=min(512, len(signal_raw)//4))
    
    # Integrate power in signal band (movement frequencies from RAW)
    signal_mask = (f >= signal_band[0]) & (f <= signal_band[1])
    signal_power = np.trapz(psd[signal_mask], f[signal_mask]) if signal_mask.any() else 0
    
    # Integrate power in noise band (high frequencies from RAW)
    noise_mask = (f >= noise_band[0]) & (f <= noise_band[1])
    noise_power = np.trapz(psd[noise_mask], f[noise_mask]) if noise_mask.any() else 0
    
    # Compute SNR
    if noise_power < 1e-12:
        snr_db = 100.0  # Essentially no noise
    else:
        snr_db = 10 * np.log10(signal_power / noise_power)
    
    return {
        'snr_db': float(snr_db),
        'signal_power': float(signal_power),
        'noise_power': float(noise_power),
        'signal_band_hz': signal_band,
        'noise_band_hz': noise_band
    }


def compute_snr_psd(signal_raw, signal_filtered, fs, signal_band=(1, 15), noise_band=(20, 50)):
    """
    Compute SNR using power spectral density analysis.
    
    More robust for biomechanical signals where signal and noise occupy
    different frequency bands.
    
    Parameters:
    -----------
    signal_raw : np.ndarray
        Raw signal
    signal_filtered : np.ndarray
        Filtered signal
    fs : float
        Sampling frequency (Hz)
    signal_band : tuple
        Frequency band for signal (Hz)
    noise_band : tuple
        Frequency band for noise (Hz)
        
    Returns:
    --------
    dict : SNR results including frequency-domain analysis
    """
    # Remove NaN values
    valid_mask = ~(np.isnan(signal_raw) | np.isnan(signal_filtered))
    signal_raw = signal_raw[valid_mask]
    signal_filtered = signal_filtered[valid_mask]
    
    if len(signal_raw) < 100:
        return {'snr_db': np.nan, 'signal_power': np.nan, 'noise_power': np.nan}
    
    # Compute PSD using Welch's method
    f_raw, psd_raw = sp_signal.welch(signal_raw, fs=fs, nperseg=min(512, len(signal_raw)//4))
    f_filt, psd_filt = sp_signal.welch(signal_filtered, fs=fs, nperseg=min(512, len(signal_filtered)//4))
    
    # Integrate power in signal band
    signal_band_mask = (f_filt >= signal_band[0]) & (f_filt <= signal_band[1])
    signal_power = np.trapz(psd_filt[signal_band_mask], f_filt[signal_band_mask])
    
    # Integrate power in noise band (from raw signal)
    noise_band_mask = (f_raw >= noise_band[0]) & (f_raw <= noise_band[1])
    noise_power = np.trapz(psd_raw[noise_band_mask], f_raw[noise_band_mask])
    
    # Compute SNR
    if noise_power < 1e-12:
        snr_db = 100.0
    else:
        snr_db = 10 * np.log10(signal_power / noise_power)
    
    return {
        'snr_db': float(snr_db),
        'signal_power': float(signal_power),
        'noise_power': float(noise_power),
        'signal_band': signal_band,
        'noise_band': noise_band
    }


def assess_snr_quality(snr_db):
    """
    Assess signal quality based on SNR.
    
    Parameters:
    -----------
    snr_db : float
        SNR in dB
        
    Returns:
    --------
    dict : Quality assessment
    """
    if np.isnan(snr_db):
        return {
            'category': 'UNKNOWN',
            'status': '❓',
            'recommendation': 'Unable to compute SNR',
            'accept': False
        }
    
    if snr_db >= SNR_THRESHOLDS['excellent']:
        return {
            'category': 'EXCELLENT',
            'status': '✅⭐',
            'recommendation': 'Publication quality',
            'accept': True
        }
    elif snr_db >= SNR_THRESHOLDS['good']:
        return {
            'category': 'GOOD',
            'status': '✅',
            'recommendation': 'Acceptable for research',
            'accept': True
        }
    elif snr_db >= SNR_THRESHOLDS['acceptable']:
        return {
            'category': 'ACCEPTABLE',
            'status': '⚠️',
            'recommendation': 'Review recommended',
            'accept': True
        }
    elif snr_db >= SNR_THRESHOLDS['poor']:
        return {
            'category': 'POOR',
            'status': '🟡',
            'recommendation': 'Caution advised',
            'accept': False
        }
    else:
        return {
            'category': 'REJECT',
            'status': '❌',
            'recommendation': 'SNR too low for reliable analysis',
            'accept': False
        }


def compute_per_joint_snr(df_raw, df_filtered, joint_names, fs=120.0, method='true_raw'):
    """
    Compute SNR for all joints in a DataFrame.
    
    Parameters:
    -----------
    df_raw : pd.DataFrame
        Raw (unfiltered) position data
    df_filtered : pd.DataFrame
        Filtered position data (only needed for 'rms' and 'psd' methods)
    joint_names : list
        List of joint names
    fs : float
        Sampling frequency (Hz)
    method : str
        'true_raw' (recommended) - SNR from raw data frequency analysis
        'rms' - filtering effectiveness (signal vs residual)
        'psd' - hybrid method (filtered signal vs raw noise)
        
    Returns:
    --------
    dict : Per-joint SNR results
    """
    snr_results = {}
    
    for joint in joint_names:
        # Get position columns (3D position)
        pos_cols = [f'{joint}__px', f'{joint}__py', f'{joint}__pz']
        
        # For true_raw, only need raw data
        if method == 'true_raw':
            if not all(col in df_raw.columns for col in pos_cols):
                continue
        else:
            if not all(col in df_raw.columns and col in df_filtered.columns for col in pos_cols):
                continue
        
        # Compute SNR for each axis
        axis_snrs = []
        for col in pos_cols:
            if method == 'true_raw':
                snr_result = compute_true_raw_snr(
                    df_raw[col].values,
                    fs=fs
                )
                axis_snrs.append(snr_result['snr_db'])
            elif method == 'psd':
                snr_result = compute_snr_psd(
                    df_raw[col].values,
                    df_filtered[col].values,
                    fs=fs
                )
                axis_snrs.append(snr_result['snr_db'])
            else:
                snr_db = compute_snr_from_residuals(
                    df_raw[col].values,
                    df_filtered[col].values
                )
                axis_snrs.append(snr_db)
        
        # Average across 3D axes
        mean_snr = np.nanmean(axis_snrs)
        min_snr = np.nanmin(axis_snrs)
        
        # Assess quality
        quality = assess_snr_quality(mean_snr)
        
        snr_results[joint] = {
            'mean_snr_db': float(mean_snr),
            'min_snr_db': float(min_snr),
            'axis_snrs': [float(x) for x in axis_snrs],
            'quality': quality['category'],
            'status': quality['status'],
            'recommendation': quality['recommendation'],
            'accept': quality['accept']
        }
    
    return snr_results


def generate_snr_report(snr_results, min_acceptable_snr=15.0):
    """
    Generate summary SNR report.
    
    Parameters:
    -----------
    snr_results : dict
        Per-joint SNR results from compute_per_joint_snr
    min_acceptable_snr : float
        Minimum acceptable SNR (dB)
        
    Returns:
    --------
    dict : Summary report
    """
    if not snr_results:
        return {
            'mean_snr_all_joints': np.nan,
            'joints_excellent': 0,
            'joints_good': 0,
            'joints_acceptable': 0,
            'joints_poor': 0,
            'joints_reject': 0,
            'overall_status': 'NO_DATA',
            'failed_joints': []
        }
    
    # Count by category
    categories = [r['quality'] for r in snr_results.values()]
    
    # Identify failed joints
    failed_joints = [
        joint for joint, result in snr_results.items()
        if result['mean_snr_db'] < min_acceptable_snr
    ]
    
    # Overall status
    all_snrs = [r['mean_snr_db'] for r in snr_results.values()]
    mean_snr = np.nanmean(all_snrs)
    
    if mean_snr >= SNR_THRESHOLDS['excellent']:
        overall_status = 'EXCELLENT'
    elif mean_snr >= SNR_THRESHOLDS['good']:
        overall_status = 'GOOD'
    elif mean_snr >= SNR_THRESHOLDS['acceptable']:
        overall_status = 'ACCEPTABLE'
    elif mean_snr >= SNR_THRESHOLDS['poor']:
        overall_status = 'POOR'
    else:
        overall_status = 'REJECT'
    
    return {
        'mean_snr_all_joints': float(mean_snr),
        'min_snr_all_joints': float(np.nanmin(all_snrs)),
        'max_snr_all_joints': float(np.nanmax(all_snrs)),
        'joints_excellent': categories.count('EXCELLENT'),
        'joints_good': categories.count('GOOD'),
        'joints_acceptable': categories.count('ACCEPTABLE'),
        'joints_poor': categories.count('POOR'),
        'joints_reject': categories.count('REJECT'),
        'overall_status': overall_status,
        'failed_joints': failed_joints,
        'total_joints': len(snr_results)
    }
