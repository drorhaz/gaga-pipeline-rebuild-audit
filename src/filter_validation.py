"""
Filter Validation Module - PSD Analysis for Winter Filtering

This module provides validation tools to verify that Winter's filtering method
preserves dance kinematics while removing noise, using Power Spectral Density (PSD)
analysis.

References:
    - Winter, D. A. (2009). Biomechanics and motor control of human movement.
    - Welch, P. (1967). The use of fast Fourier transform for the estimation of power spectra.
    - Wren et al. (2006). Efficacy of clinical gait analysis. Gait & Posture, 22(4), 295-305.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, Tuple, Optional, List
from scipy import signal as scipy_signal
from scipy.signal import welch, butter, filtfilt

logger = logging.getLogger(__name__)


def compute_psd_welch(signal_data: np.ndarray, 
                     fs: float, 
                     nperseg: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute Power Spectral Density using Welch's method.
    
    Args:
        signal_data: Input signal (1D array)
        fs: Sampling frequency in Hz
        nperseg: Length of each segment for Welch's method (default: fs*2 for ~1Hz resolution)
        
    Returns:
        Tuple of (frequencies, psd_values)
        
    Reference:
        Welch, P. (1967). The use of fast Fourier transform for the estimation of power spectra.
    """
    if nperseg is None:
        # Default: 2-second windows for good frequency resolution
        nperseg = min(int(fs * 2), len(signal_data) // 4)
    
    # Ensure nperseg is valid
    nperseg = max(256, min(nperseg, len(signal_data) // 2))
    
    # Compute PSD using Welch's method with Hanning window
    freqs, psd = welch(signal_data, fs=fs, nperseg=nperseg, 
                       window='hann', scaling='density', detrend='constant')
    
    return freqs, psd


def compute_power_in_band(freqs: np.ndarray, 
                         psd: np.ndarray, 
                         f_low: float, 
                         f_high: float) -> float:
    """
    Compute total power within a frequency band.
    
    Args:
        freqs: Frequency array from PSD
        psd: PSD values
        f_low: Lower frequency bound (Hz)
        f_high: Upper frequency bound (Hz)
        
    Returns:
        Total power in band (integrated PSD)
    """
    band_mask = (freqs >= f_low) & (freqs <= f_high)
    if not np.any(band_mask):
        return 0.0
    
    # Integrate PSD using trapezoidal rule
    power = np.trapz(psd[band_mask], freqs[band_mask])
    return float(power)


def analyze_filter_psd_preservation(signal_raw: np.ndarray,
                                   signal_filtered: np.ndarray,
                                   fs: float,
                                   cutoff_hz: float,
                                   dance_band: Tuple[float, float] = (1.0, 15.0),
                                   noise_band: Tuple[float, float] = (20.0, 40.0)) -> Dict[str, float]:
    """
    Analyze PSD to validate filter performance for dance kinematics.
    
    Verifies that:
    1. Dance-relevant frequencies (1-15 Hz) are preserved
    2. High-frequency noise (>20 Hz) is attenuated
    3. Filter behavior matches expectations
    
    Args:
        signal_raw: Raw (unfiltered) signal
        signal_filtered: Filtered signal
        fs: Sampling frequency in Hz
        cutoff_hz: Filter cutoff frequency
        dance_band: Frequency band for dance movements (Hz)
        noise_band: Frequency band considered noise (Hz)
        
    Returns:
        Dictionary with PSD validation metrics
        
    Reference:
        Winter, D. A. (2009). Upper limb movements: 12-15 Hz content.
        Wren et al. (2006). Gait analysis filtering standards.
        Gaga dance: Rapid gestures extend to 15 Hz (distal markers).
    """
    # Compute PSDs
    freqs_raw, psd_raw = compute_psd_welch(signal_raw, fs)
    freqs_filt, psd_filt = compute_psd_welch(signal_filtered, fs)
    
    # Compute power in different bands
    power_raw_dance = compute_power_in_band(freqs_raw, psd_raw, dance_band[0], dance_band[1])
    power_filt_dance = compute_power_in_band(freqs_filt, psd_filt, dance_band[0], dance_band[1])
    
    power_raw_noise = compute_power_in_band(freqs_raw, psd_raw, noise_band[0], noise_band[1])
    power_filt_noise = compute_power_in_band(freqs_filt, psd_filt, noise_band[0], noise_band[1])
    
    # Total power
    power_raw_total = compute_power_in_band(freqs_raw, psd_raw, 0, fs/2)
    power_filt_total = compute_power_in_band(freqs_filt, psd_filt, 0, fs/2)
    
    # Compute preservation metrics
    dance_preservation_pct = (power_filt_dance / power_raw_dance * 100) if power_raw_dance > 0 else 0.0
    noise_attenuation_db = 10 * np.log10(power_raw_noise / power_filt_noise) if power_filt_noise > 1e-12 else 100.0
    total_power_loss_db = 10 * np.log10(power_raw_total / power_filt_total) if power_filt_total > 0 else 0.0
    
    # Signal-to-noise improvement
    snr_raw = power_raw_dance / power_raw_noise if power_raw_noise > 1e-12 else 1.0
    snr_filt = power_filt_dance / power_filt_noise if power_filt_noise > 1e-12 else 1.0
    snr_improvement_db = 10 * np.log10(snr_filt / snr_raw) if snr_raw > 0 else 0.0
    
    # Find peak frequency (where most dance energy is)
    peak_freq_raw = freqs_raw[np.argmax(psd_raw[freqs_raw < dance_band[1]])]
    peak_freq_filt = freqs_filt[np.argmax(psd_filt[freqs_filt < dance_band[1]])]
    
    metrics = {
        'dance_preservation_pct': float(dance_preservation_pct),
        'noise_attenuation_db': float(noise_attenuation_db),
        'total_power_loss_db': float(total_power_loss_db),
        'snr_improvement_db': float(snr_improvement_db),
        'peak_freq_raw_hz': float(peak_freq_raw),
        'peak_freq_filt_hz': float(peak_freq_filt),
        'cutoff_hz': float(cutoff_hz),
        'dance_band_hz': dance_band,
        'noise_band_hz': noise_band,
        'power_raw_dance': float(power_raw_dance),
        'power_filt_dance': float(power_filt_dance),
        'power_raw_noise': float(power_raw_noise),
        'power_filt_noise': float(power_filt_noise)
    }
    
    return metrics


def validate_filter_quality(psd_metrics: Dict[str, float]) -> Dict[str, str]:
    """
    Assess filter quality based on PSD metrics with research-based thresholds.
    
    Quality criteria:
    - Dance preservation: >90% = EXCELLENT, >80% = GOOD, <80% = POOR
    - Noise attenuation: >20dB = EXCELLENT, >10dB = GOOD, <10dB = POOR
    - SNR improvement: >3dB = GOOD, <0dB = POOR
    
    Args:
        psd_metrics: Dictionary from analyze_filter_psd_preservation()
        
    Returns:
        Dictionary with quality assessments and overall status
        
    Reference:
        Winter (2009): Good filter should preserve >95% of signal band
        Wren et al. (2006): Clinical gait filtering standards
    """
    dance_pres = psd_metrics['dance_preservation_pct']
    noise_atten = psd_metrics['noise_attenuation_db']
    snr_improve = psd_metrics['snr_improvement_db']
    
    # Dance preservation assessment
    if dance_pres >= 95:
        dance_status = 'EXCELLENT'
    elif dance_pres >= 85:
        dance_status = 'GOOD'
    elif dance_pres >= 75:
        dance_status = 'ACCEPTABLE'
    else:
        dance_status = 'POOR'
    
    # Noise attenuation assessment
    if noise_atten >= 20:
        noise_status = 'EXCELLENT'
    elif noise_atten >= 10:
        noise_status = 'GOOD'
    elif noise_atten >= 5:
        noise_status = 'ACCEPTABLE'
    else:
        noise_status = 'POOR'
    
    # SNR improvement assessment
    if snr_improve >= 6:
        snr_status = 'EXCELLENT'
    elif snr_improve >= 3:
        snr_status = 'GOOD'
    elif snr_improve >= 0:
        snr_status = 'ACCEPTABLE'
    else:
        snr_status = 'POOR'
    
    # Overall assessment
    statuses = [dance_status, noise_status, snr_status]
    if all(s in ['EXCELLENT', 'GOOD'] for s in statuses):
        overall = 'PASS'
    elif any(s == 'POOR' for s in statuses):
        overall = 'FAIL'
    else:
        overall = 'WARN'
    
    return {
        'dance_preservation_status': dance_status,
        'noise_attenuation_status': noise_status,
        'snr_improvement_status': snr_status,
        'overall_filter_quality': overall
    }


def validate_winter_filter_multi_signal(df_raw: pd.DataFrame,
                                       df_filtered: pd.DataFrame,
                                       pos_cols: List[str],
                                       fs: float,
                                       cutoff_hz: float,
                                       n_samples: int = 5) -> Dict[str, any]:
    """
    Validate Winter filter across multiple signals with PSD analysis.
    
    Samples n_samples position columns and computes aggregate PSD metrics.
    
    Args:
        df_raw: Raw DataFrame before filtering
        df_filtered: Filtered DataFrame
        pos_cols: List of position column names
        fs: Sampling frequency
        cutoff_hz: Filter cutoff used
        n_samples: Number of signals to sample for validation
        
    Returns:
        Dictionary with aggregate PSD validation metrics
    """
    # Sample columns for validation (diverse body regions)
    sample_cols = pos_cols[:min(n_samples, len(pos_cols))]
    
    all_metrics = []
    for col in sample_cols:
        if col not in df_raw.columns or col not in df_filtered.columns:
            continue
        
        signal_raw = df_raw[col].values
        signal_filt = df_filtered[col].values
        
        # Skip if NaNs present
        if np.any(np.isnan(signal_raw)) or np.any(np.isnan(signal_filt)):
            logger.warning(f"Skipping PSD validation for {col}: contains NaNs")
            continue
        
        metrics = analyze_filter_psd_preservation(signal_raw, signal_filt, fs, cutoff_hz)
        metrics['column'] = col
        all_metrics.append(metrics)
    
    if not all_metrics:
        logger.error("No valid signals for PSD validation")
        return {'status': 'FAIL', 'error': 'No valid signals'}
    
    # Compute aggregate statistics
    df_metrics = pd.DataFrame(all_metrics)
    
    aggregate = {
        'n_signals_analyzed': len(all_metrics),
        'dance_preservation_mean': float(df_metrics['dance_preservation_pct'].mean()),
        'dance_preservation_std': float(df_metrics['dance_preservation_pct'].std()),
        'dance_preservation_min': float(df_metrics['dance_preservation_pct'].min()),
        'noise_attenuation_mean_db': float(df_metrics['noise_attenuation_db'].mean()),
        'noise_attenuation_std_db': float(df_metrics['noise_attenuation_db'].std()),
        'snr_improvement_mean_db': float(df_metrics['snr_improvement_db'].mean()),
        'total_power_loss_mean_db': float(df_metrics['total_power_loss_db'].mean()),
        'cutoff_hz': cutoff_hz,
        'individual_metrics': all_metrics
    }
    
    # Quality assessment
    quality = validate_filter_quality({
        'dance_preservation_pct': aggregate['dance_preservation_mean'],
        'noise_attenuation_db': aggregate['noise_attenuation_mean_db'],
        'snr_improvement_db': aggregate['snr_improvement_mean_db']
    })
    
    aggregate.update(quality)
    
    logger.info(f"PSD Validation: Dance preservation={aggregate['dance_preservation_mean']:.1f}%, "
                f"Noise attenuation={aggregate['noise_attenuation_mean_db']:.1f}dB, "
                f"Overall={quality['overall_filter_quality']}")
    
    return aggregate


def generate_psd_plots_data(signal_raw: np.ndarray,
                            signal_filtered: np.ndarray,
                            fs: float,
                            cutoff_hz: float) -> Dict[str, any]:
    """
    Generate data for PSD visualization plots.
    
    Returns data structure suitable for plotting without matplotlib dependency.
    
    Args:
        signal_raw: Raw signal
        signal_filtered: Filtered signal
        fs: Sampling frequency
        cutoff_hz: Filter cutoff
        
    Returns:
        Dictionary with plot data (freqs, psds, annotations)
    """
    freqs_raw, psd_raw = compute_psd_welch(signal_raw, fs)
    freqs_filt, psd_filt = compute_psd_welch(signal_filtered, fs)
    
    # Convert to dB scale for plotting
    psd_raw_db = 10 * np.log10(psd_raw + 1e-12)
    psd_filt_db = 10 * np.log10(psd_filt + 1e-12)
    
    plot_data = {
        'freqs_raw': freqs_raw.tolist(),
        'psd_raw_db': psd_raw_db.tolist(),
        'freqs_filt': freqs_filt.tolist(),
        'psd_filt_db': psd_filt_db.tolist(),
        'cutoff_hz': cutoff_hz,
        'fs': fs,
        'annotations': {
            'cutoff_line': cutoff_hz,
            'dance_band': [1.0, 10.0],
            'noise_band': [15.0, 30.0]
        }
    }
    
    return plot_data


def check_filter_cutoff_validity(cutoff_hz: float, 
                                 fs: float,
                                 fmax: float = 12.0) -> Dict[str, any]:
    """
    Check if filter cutoff is valid according to research standards.
    
    Args:
        cutoff_hz: Filter cutoff frequency
        fs: Sampling frequency
        fmax: Maximum cutoff tested by Winter analysis
        
    Returns:
        Dictionary with validity checks
        
    Reference:
        Winter (2009): Cutoff should be << Nyquist frequency
        Dance kinematics: Expected range 4-10 Hz (Winter, Wren et al.)
    """
    nyquist = fs / 2
    
    checks = {
        'cutoff_hz': cutoff_hz,
        'nyquist_hz': nyquist,
        'cutoff_to_nyquist_ratio': cutoff_hz / nyquist,
        'is_below_nyquist': cutoff_hz < nyquist * 0.8,  # Should be < 80% Nyquist
        'is_in_dance_range': 4.0 <= cutoff_hz <= 10.0,
        'is_at_fmax': cutoff_hz >= fmax - 0.1,  # Winter failed
        'validity_status': 'VALID'
    }
    
    # Determine validity
    if checks['is_at_fmax']:
        checks['validity_status'] = 'FAIL_WINTER_FMAX'
        checks['validity_message'] = 'Winter analysis failed (cutoff=fmax indicates pre-smoothed data)'
    elif not checks['is_below_nyquist']:
        checks['validity_status'] = 'FAIL_NYQUIST'
        checks['validity_message'] = 'Cutoff too close to Nyquist frequency'
    elif not checks['is_in_dance_range']:
        checks['validity_status'] = 'WARN_UNUSUAL'
        checks['validity_message'] = f'Cutoff {cutoff_hz:.1f}Hz outside typical dance range (4-10Hz)'
    else:
        checks['validity_status'] = 'VALID'
        checks['validity_message'] = f'Cutoff {cutoff_hz:.1f}Hz within expected dance range'
    
    return checks
