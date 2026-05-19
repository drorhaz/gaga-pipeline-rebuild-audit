"""
Tests for Filter Validation Module - PSD Analysis

Tests verify that PSD analysis correctly:
1. Computes power spectral density
2. Measures frequency band preservation
3. Validates filter quality
4. Detects filter failures
"""

import pytest
import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from filter_validation import (
    compute_psd_welch,
    compute_power_in_band,
    analyze_filter_psd_preservation,
    validate_filter_quality,
    check_filter_cutoff_validity,
    validate_winter_filter_multi_signal
)


class TestPSDComputation:
    """Test PSD computation basics."""
    
    def test_psd_sine_wave_peak(self):
        """Test that PSD correctly identifies sine wave frequency."""
        fs = 120.0
        duration = 10.0
        freq_target = 5.0  # 5 Hz sine wave
        
        t = np.arange(0, duration, 1/fs)
        signal = np.sin(2 * np.pi * freq_target * t)
        
        freqs, psd = compute_psd_welch(signal, fs)
        
        # Find peak frequency
        peak_idx = np.argmax(psd)
        peak_freq = freqs[peak_idx]
        
        # Peak should be at target frequency ±0.5 Hz
        assert abs(peak_freq - freq_target) < 0.5
        
    def test_psd_output_shapes(self):
        """Test that PSD returns correct shapes."""
        fs = 120.0
        signal = np.random.randn(1200)  # 10 seconds
        
        freqs, psd = compute_psd_welch(signal, fs)
        
        assert len(freqs) == len(psd)
        assert freqs[0] >= 0
        assert freqs[-1] <= fs / 2
        assert all(psd >= 0)  # PSD should be non-negative


class TestPowerInBand:
    """Test power integration in frequency bands."""
    
    def test_power_in_band_basic(self):
        """Test power computation in a frequency band."""
        freqs = np.linspace(0, 60, 1000)
        psd = np.ones_like(freqs)  # Flat PSD
        
        # Power in 1-10 Hz band
        power = compute_power_in_band(freqs, psd, 1.0, 10.0)
        
        # Should be approximately 9 (9 Hz bandwidth * 1 power density)
        assert 8.0 < power < 10.0
        
    def test_power_in_band_zero(self):
        """Test power in empty band."""
        freqs = np.linspace(0, 60, 1000)
        psd = np.ones_like(freqs)
        
        # Band outside frequency range
        power = compute_power_in_band(freqs, psd, 100.0, 200.0)
        
        assert power == 0.0


class TestFilterPSDPreservation:
    """Test PSD-based filter validation."""
    
    def test_good_filter_preservation(self):
        """Test that a good filter shows high dance preservation."""
        fs = 120.0
        duration = 10.0
        t = np.arange(0, duration, 1/fs)
        
        # Create signal with dance frequencies (5 Hz) + noise (25 Hz)
        signal_raw = (np.sin(2*np.pi*5*t) +  # Dance component
                     0.3 * np.sin(2*np.pi*25*t))  # Noise component
        
        # Apply 10 Hz low-pass filter (should preserve 5 Hz, remove 25 Hz)
        b, a = butter(2, 10.0/(fs/2), btype='low')
        signal_filt = filtfilt(b, a, signal_raw)
        
        metrics = analyze_filter_psd_preservation(
            signal_raw, signal_filt, fs, cutoff_hz=10.0
        )
        
        # Should preserve most dance band power (5 Hz)
        assert metrics['dance_preservation_pct'] > 85.0
        
        # Should attenuate noise (25 Hz)
        assert metrics['noise_attenuation_db'] > 5.0
        
        # SNR should improve
        assert metrics['snr_improvement_db'] > 0.0
        
    def test_oversmoothed_filter_detection(self):
        """Test that over-smoothing is detected."""
        fs = 120.0
        duration = 10.0
        t = np.arange(0, duration, 1/fs)
        
        # Dance signal at 5 Hz
        signal_raw = np.sin(2*np.pi*5*t)
        
        # Over-smooth with 2 Hz cutoff (too low for dance)
        b, a = butter(2, 2.0/(fs/2), btype='low')
        signal_filt = filtfilt(b, a, signal_raw)
        
        metrics = analyze_filter_psd_preservation(
            signal_raw, signal_filt, fs, cutoff_hz=2.0
        )
        
        # Should lose significant dance band power
        assert metrics['dance_preservation_pct'] < 70.0


class TestFilterQualityAssessment:
    """Test filter quality classification."""
    
    def test_excellent_filter_quality(self):
        """Test excellent filter classification."""
        metrics = {
            'dance_preservation_pct': 97.0,
            'noise_attenuation_db': 25.0,
            'snr_improvement_db': 8.0
        }
        
        quality = validate_filter_quality(metrics)
        
        assert quality['dance_preservation_status'] == 'EXCELLENT'
        assert quality['noise_attenuation_status'] == 'EXCELLENT'
        assert quality['overall_filter_quality'] == 'PASS'
        
    def test_poor_filter_quality(self):
        """Test poor filter detection."""
        metrics = {
            'dance_preservation_pct': 60.0,  # Too low
            'noise_attenuation_db': 3.0,     # Too low
            'snr_improvement_db': -2.0       # Negative!
        }
        
        quality = validate_filter_quality(metrics)
        
        assert quality['dance_preservation_status'] == 'POOR'
        assert quality['overall_filter_quality'] == 'FAIL'


class TestCutoffValidity:
    """Test filter cutoff validity checks."""
    
    def test_valid_cutoff(self):
        """Test valid dance cutoff."""
        result = check_filter_cutoff_validity(
            cutoff_hz=6.0, fs=120.0, fmax=12.0
        )
        
        assert result['validity_status'] == 'VALID'
        assert result['is_in_dance_range'] is True
        assert result['is_at_fmax'] is False
        
    def test_winter_failure_detection(self):
        """Test detection of Winter analysis failure (cutoff=fmax)."""
        result = check_filter_cutoff_validity(
            cutoff_hz=12.0, fs=120.0, fmax=12.0
        )
        
        assert result['validity_status'] == 'FAIL_WINTER_FMAX'
        assert result['is_at_fmax'] is True
        
    def test_unusual_cutoff_warning(self):
        """Test warning for unusual cutoff."""
        result = check_filter_cutoff_validity(
            cutoff_hz=2.0, fs=120.0, fmax=12.0
        )
        
        assert result['validity_status'] == 'WARN_UNUSUAL'
        assert result['is_in_dance_range'] is False


class TestMultiSignalValidation:
    """Test validation across multiple signals."""
    
    def test_multi_signal_validation(self):
        """Test PSD validation across multiple columns."""
        fs = 120.0
        duration = 5.0
        n_samples = int(fs * duration)
        
        # Create test DataFrames
        t = np.arange(n_samples) / fs
        df_raw = pd.DataFrame({
            'col1__px': np.sin(2*np.pi*5*t) + 0.2*np.random.randn(n_samples),
            'col2__py': np.sin(2*np.pi*6*t) + 0.2*np.random.randn(n_samples),
            'col3__pz': np.sin(2*np.pi*4*t) + 0.2*np.random.randn(n_samples)
        })
        
        # Apply filter
        b, a = butter(2, 8.0/(fs/2), btype='low')
        df_filt = df_raw.copy()
        for col in df_raw.columns:
            df_filt[col] = filtfilt(b, a, df_raw[col].values)
        
        # Validate
        result = validate_winter_filter_multi_signal(
            df_raw, df_filt, list(df_raw.columns), fs, cutoff_hz=8.0, n_samples=3
        )
        
        assert result['n_signals_analyzed'] == 3
        assert 'dance_preservation_mean' in result
        assert result['dance_preservation_mean'] > 75.0
        assert 'overall_filter_quality' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
