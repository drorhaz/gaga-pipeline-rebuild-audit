"""
Comprehensive pytest suite for Phase 2 filtering upgrades:
  1. Chunking Guard (chunked_filtfilt)
  2. Dynamic RMS Windowing (compute_energetic_mask)
  3. Integration: Winter residual analysis with energetic mask + chunked filtfilt

All tests import and exercise the real production functions in src/filtering.py.
"""

import pytest
import numpy as np
from scipy.signal import butter

from src.filtering import (
    _find_contiguous_finite_segments,
    chunked_filtfilt,
    compute_energetic_mask,
    winter_residual_analysis,
    apply_adaptive_winter_filter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fs():
    return 120.0


@pytest.fixture
def butter_ba():
    """2nd-order Butterworth at 8 Hz / 120 Hz."""
    b, a = butter(N=2, Wn=8 / 60.0, btype="low")
    return b, a


def _make_clean_signal(fs=120.0, duration=2.0, freq=5.0):
    """Sine wave at *freq* Hz, sampled at *fs* for *duration* seconds."""
    t = np.arange(0, duration, 1.0 / fs)
    return np.sin(2 * np.pi * freq * t), t


# =========================================================================
# 1. Chunking Guard — _find_contiguous_finite_segments
# =========================================================================

class TestFindContiguousSegments:

    def test_no_nans(self):
        x = np.array([1.0, 2.0, 3.0, 4.0])
        segs = _find_contiguous_finite_segments(x)
        assert segs == [(0, 4)]

    def test_all_nan(self):
        x = np.full(5, np.nan)
        segs = _find_contiguous_finite_segments(x)
        assert segs == []

    def test_leading_trailing_nan(self):
        x = np.array([np.nan, np.nan, 1.0, 2.0, 3.0, np.nan])
        segs = _find_contiguous_finite_segments(x)
        assert segs == [(2, 5)]

    def test_middle_gap(self):
        x = np.array([1.0, 2.0, np.nan, np.nan, 5.0, 6.0])
        segs = _find_contiguous_finite_segments(x)
        assert segs == [(0, 2), (4, 6)]

    def test_single_sample_segments(self):
        x = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
        segs = _find_contiguous_finite_segments(x)
        assert segs == [(0, 1), (2, 3), (4, 5)]


# =========================================================================
# 2. Chunking Guard — chunked_filtfilt
# =========================================================================

class TestChunkedFiltfilt:

    def test_no_nans_matches_scipy(self, butter_ba):
        """Without NaNs, chunked_filtfilt should match scipy.signal.filtfilt."""
        from scipy.signal import filtfilt as scipy_filtfilt
        b, a = butter_ba
        sig, _ = _make_clean_signal()
        out_chunked = chunked_filtfilt(b, a, sig)
        out_scipy = scipy_filtfilt(b, a, sig)
        np.testing.assert_allclose(out_chunked, out_scipy, atol=1e-12)

    def test_nans_preserved(self, butter_ba):
        """NaN positions in input must be NaN in output."""
        b, a = butter_ba
        sig, _ = _make_clean_signal()
        sig[50:70] = np.nan
        out = chunked_filtfilt(b, a, sig)
        assert np.all(np.isnan(out[50:70])), "NaN gap must be preserved"

    def test_valid_segments_finite(self, butter_ba):
        """Valid segments around a NaN gap must remain finite."""
        b, a = butter_ba
        sig, _ = _make_clean_signal()
        sig[50:70] = np.nan
        out = chunked_filtfilt(b, a, sig)
        assert np.all(np.isfinite(out[:50])), "Segment before gap must be finite"
        assert np.all(np.isfinite(out[70:])), "Segment after gap must be finite"

    def test_short_segment_unfiltered(self, butter_ba):
        """Segment shorter than padlen is returned unchanged (not filtered)."""
        b, a = butter_ba
        padlen = 3 * max(len(a), len(b))
        short_len = padlen - 1
        sig = np.full(100, np.nan)
        sig[10:10 + short_len] = np.arange(short_len, dtype=float)
        out = chunked_filtfilt(b, a, sig)
        np.testing.assert_array_equal(out[10:10 + short_len], np.arange(short_len, dtype=float))

    def test_all_nan_returns_all_nan(self, butter_ba):
        """Entirely NaN signal returns entirely NaN."""
        b, a = butter_ba
        sig = np.full(50, np.nan)
        out = chunked_filtfilt(b, a, sig)
        assert np.all(np.isnan(out))

    def test_multiple_gaps(self, butter_ba):
        """Multiple NaN gaps: each valid segment filtered independently."""
        b, a = butter_ba
        sig, _ = _make_clean_signal(duration=3.0)
        sig[40:60] = np.nan
        sig[200:220] = np.nan
        out = chunked_filtfilt(b, a, sig)
        assert np.all(np.isnan(out[40:60]))
        assert np.all(np.isnan(out[200:220]))
        assert np.all(np.isfinite(out[:40]))
        assert np.all(np.isfinite(out[60:200]))
        assert np.all(np.isfinite(out[220:]))


# =========================================================================
# 3. Dynamic RMS Windowing — compute_energetic_mask
# =========================================================================

class TestComputeEnergeticMask:

    def test_all_still_returns_all_true_fallback(self, fs):
        """Flat signal (zero variance everywhere) falls back to all-True."""
        sig = np.ones(int(fs * 3))
        mask = compute_energetic_mask(sig, fs)
        assert mask.dtype == bool
        assert np.all(mask), "Flat signal should fall back to all-True mask"

    def test_burst_selected(self, fs):
        """A short burst in a mostly-still signal: burst region must be True."""
        duration = 5.0
        n = int(fs * duration)
        sig = np.zeros(n)
        burst_start = int(2.0 * fs)
        burst_end = int(2.5 * fs)
        sig[burst_start:burst_end] = np.sin(np.linspace(0, 10 * np.pi, burst_end - burst_start)) * 10
        mask = compute_energetic_mask(sig, fs)
        assert np.all(mask[burst_start:burst_end]), "Burst region must be in energetic mask"

    def test_quiet_region_excluded(self, fs):
        """Quiet region in a mostly-active signal should be excluded from mask."""
        duration = 10.0
        n = int(fs * duration)
        np.random.seed(99)
        sig = np.random.randn(n) * 10
        quiet_start = int(4.0 * fs)
        quiet_end = int(6.0 * fs)
        sig[quiet_start:quiet_end] = 0.001
        mask = compute_energetic_mask(sig, fs, energy_quantile=0.80)
        quiet_frac = mask[quiet_start:quiet_end].mean()
        assert quiet_frac < 0.5, f"Quiet region should mostly be excluded; got {quiet_frac:.2f}"

    def test_nan_windows_excluded(self, fs):
        """Windows dominated by NaN should not inflate the energetic mask."""
        n = int(fs * 4)
        sig = np.ones(n)
        sig[0:int(fs * 2)] = np.nan
        mask = compute_energetic_mask(sig, fs)
        assert mask.shape == (n,)
        assert mask.dtype == bool

    def test_short_signal_fallback(self, fs):
        """Signal shorter than one window falls back to all-True."""
        sig = np.array([1.0, 2.0, 3.0])
        mask = compute_energetic_mask(sig, fs, window_sec=1.0)
        assert np.all(mask)

    def test_shape_preserved(self, fs):
        sig = np.random.randn(500)
        mask = compute_energetic_mask(sig, fs)
        assert mask.shape == sig.shape


# =========================================================================
# 4. Integration — winter_residual_analysis with energetic mask
# =========================================================================

class TestWinterWithEnergeticMask:

    def test_burst_signal_higher_cutoff_than_global(self, fs):
        """
        Signal with burst + stillness: dynamic RMS (energetic mask) should
        select a cutoff >= the global-RMS cutoff, because the stillness no
        longer drags the residual curve down.
        """
        duration = 5.0
        n = int(fs * duration)
        t = np.arange(n) / fs
        sig = np.zeros(n)
        burst_start = int(2.0 * fs)
        burst_end = int(3.0 * fs)
        sig[burst_start:burst_end] = np.sin(2 * np.pi * 8 * t[burst_start:burst_end]) * 5
        np.random.seed(7)
        sig += np.random.randn(n) * 0.3

        global_result = winter_residual_analysis(
            sig, fs, fmin=1, fmax=16, return_details=True,
            energetic_mask=None,
        )
        em = compute_energetic_mask(sig, fs)
        dynamic_result = winter_residual_analysis(
            sig, fs, fmin=1, fmax=16, return_details=True,
            energetic_mask=em,
        )
        fc_global = global_result["cutoff_hz"]
        fc_dynamic = dynamic_result["cutoff_hz"]
        assert fc_dynamic >= fc_global, (
            f"Dynamic cutoff ({fc_dynamic}) should be >= global ({fc_global})"
        )

    def test_energetic_mask_none_is_legacy(self, fs):
        """energetic_mask=None gives same result as not passing it at all."""
        sig, _ = _make_clean_signal(fs=fs, duration=2.0, freq=5.0)
        np.random.seed(42)
        sig += np.random.randn(len(sig)) * 0.1
        r1 = winter_residual_analysis(sig, fs, fmin=1, fmax=16, return_details=True)
        r2 = winter_residual_analysis(sig, fs, fmin=1, fmax=16, return_details=True,
                                      energetic_mask=None)
        assert r1["cutoff_hz"] == r2["cutoff_hz"]

    def test_winter_with_nan_gap(self, fs):
        """Winter + chunked_filtfilt handles a gappy signal without error."""
        sig, _ = _make_clean_signal(fs=fs, duration=3.0, freq=5.0)
        np.random.seed(11)
        sig += np.random.randn(len(sig)) * 0.2
        sig[100:150] = np.nan
        result = winter_residual_analysis(sig, fs, fmin=1, fmax=16, return_details=True)
        assert "cutoff_hz" in result
        assert result["cutoff_hz"] > 0


# =========================================================================
# 5. Integration — apply_adaptive_winter_filter end-to-end
# =========================================================================

class TestApplyAdaptiveWinterFilter:

    def test_clean_signal_filters_without_error(self, fs):
        sig, _ = _make_clean_signal(fs=fs, duration=2.0, freq=5.0)
        np.random.seed(0)
        sig += np.random.randn(len(sig)) * 0.1
        filtered, meta = apply_adaptive_winter_filter(sig, fs, fmax=16)
        assert meta.get("filter_applied", False)
        assert np.all(np.isfinite(filtered))

    def test_gappy_signal_nans_preserved(self, fs):
        """NaN gap should survive the full adaptive-Winter pipeline."""
        sig, _ = _make_clean_signal(fs=fs, duration=3.0, freq=5.0)
        np.random.seed(1)
        sig += np.random.randn(len(sig)) * 0.2
        sig[80:130] = np.nan
        filtered, meta = apply_adaptive_winter_filter(sig, fs, fmax=16)
        assert np.all(np.isnan(filtered[80:130])), "NaN gap must be preserved after filtering"
        assert np.all(np.isfinite(filtered[:80]))
        assert np.all(np.isfinite(filtered[130:]))

    def test_short_signal_returned_unfiltered(self, fs):
        """Signal shorter than _MIN_FILTER_LEN is returned unfiltered."""
        sig = np.array([1.0, 2.0, 3.0])
        filtered, meta = apply_adaptive_winter_filter(sig, fs)
        np.testing.assert_array_equal(filtered, sig)
        assert meta.get("filter_applied", True) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
