"""
Phase 4 Test Suite — Ultimate Kinematics Guards

Tests for:
- chunked_savgol: NaN non-bleeding, short segment handling, scipy equivalence
- Quaternion manifold preservation after SavGol + renormalization
- Angular acceleration NaN safety (chunked guard in angular_velocity.py)
- WBCoM reliability scoring
- Chunked omega dispatch (NaN-safe angular velocity)
"""

import pytest
import numpy as np
import sys
from pathlib import Path
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation as R

sys.path.append(str(Path(__file__).parent.parent))

from src.filtering import (
    chunked_savgol,
    _find_contiguous_finite_segments,
    compute_adaptive_sg_windows,
    compute_adaptive_sg_windows_from_regions,
)
from src.angular_velocity import (
    compute_angular_acceleration,
    compute_angular_velocity_enhanced,
    _find_finite_quat_segments,
    _chunked_omega_dispatch,
    quaternion_log_angular_velocity,
)
from src.com_engine import compute_com_reliability


# ============================================================
# Helpers
# ============================================================

def _random_unit_quaternions(n, seed=42):
    """Generate n random unit quaternions (xyzw) via scipy."""
    rng = np.random.RandomState(seed)
    return R.random(n, random_state=rng).as_quat()


def _sine_signal(n=240, freq=5.0, fs=120.0):
    """Clean sine wave at *freq* Hz sampled at *fs*."""
    t = np.arange(n) / fs
    return np.sin(2 * np.pi * freq * t)


# ============================================================
# 1. chunked_savgol — NaN non-bleeding
# ============================================================

class TestChunkedSavgolNanSafety:

    def test_nan_gap_does_not_bleed(self):
        """SavGol output must be NaN only where input is NaN."""
        signal = _sine_signal(240)
        signal[100:120] = np.nan

        result = chunked_savgol(signal, 21, 3, deriv=0)

        assert np.all(np.isnan(result[100:120])), "Gap frames must be NaN"
        assert np.all(np.isfinite(result[:100])), "Pre-gap frames must be finite"
        assert np.all(np.isfinite(result[120:])), "Post-gap frames must be finite"

    def test_deriv1_nan_gap_does_not_bleed(self):
        """Velocity (deriv=1) must not bleed NaN into valid frames."""
        signal = _sine_signal(240)
        signal[100:120] = np.nan

        vel = chunked_savgol(signal, 21, 3, deriv=1, delta=1/120.0)

        assert np.all(np.isnan(vel[100:120])), "Gap frames must be NaN"
        assert np.all(np.isfinite(vel[5:95])), "Interior pre-gap must be finite"
        assert np.all(np.isfinite(vel[125:235])), "Interior post-gap must be finite"

    def test_deriv2_nan_gap_does_not_bleed(self):
        """Acceleration (deriv=2) must not bleed NaN into valid frames."""
        signal = _sine_signal(240)
        signal[100:120] = np.nan

        acc = chunked_savgol(signal, 21, 3, deriv=2, delta=1/120.0)

        assert np.all(np.isnan(acc[100:120])), "Gap frames must be NaN"
        assert np.all(np.isfinite(acc[5:95])), "Interior pre-gap must be finite"
        assert np.all(np.isfinite(acc[125:235])), "Interior post-gap must be finite"

    def test_multiple_gaps(self):
        """Multiple NaN gaps produce isolated chunks; none bleed."""
        signal = _sine_signal(500)
        signal[50:70] = np.nan
        signal[200:250] = np.nan
        signal[400:410] = np.nan

        result = chunked_savgol(signal, 21, 3, deriv=0)

        assert np.all(np.isnan(result[50:70]))
        assert np.all(np.isnan(result[200:250]))
        assert np.all(np.isnan(result[400:410]))
        assert np.all(np.isfinite(result[0:50]))
        assert np.all(np.isfinite(result[70:200]))
        assert np.all(np.isfinite(result[250:400]))
        assert np.all(np.isfinite(result[410:500]))

    def test_all_nan_returns_all_nan(self):
        """Fully NaN signal returns fully NaN output."""
        signal = np.full(100, np.nan)
        result = chunked_savgol(signal, 21, 3, deriv=0)
        assert np.all(np.isnan(result))


# ============================================================
# 2. chunked_savgol — short segment handling (3-tier)
# ============================================================

class TestChunkedSavgolShortSegments:

    def test_short_segment_deriv0_passthrough(self):
        """Segments too short for polyfit pass through raw for deriv=0."""
        signal = np.full(50, np.nan)
        signal[0:3] = [1.0, 2.0, 3.0]  # 3-frame segment (< min_window=5 for poly=3)

        result = chunked_savgol(signal, 21, 3, deriv=0)
        np.testing.assert_array_equal(result[0:3], [1.0, 2.0, 3.0])

    def test_short_segment_deriv1_nan(self):
        """Segments too short for polyfit produce NaN for deriv>0."""
        signal = np.full(50, np.nan)
        signal[0:3] = [1.0, 2.0, 3.0]

        result = chunked_savgol(signal, 21, 3, deriv=1, delta=1/120.0)
        assert np.all(np.isnan(result[0:3])), "3-frame segment cannot produce deriv=1 with poly=3"

    def test_reduced_window_segment(self):
        """Segments between min_window and window_length use reduced window."""
        signal = np.ones(100)
        signal[5:12] = np.nan  # creates two segments: [0:5] and [12:100]
        # [0:5] has 5 frames — exactly min_window for poly=3, should use reduced window

        result, meta = chunked_savgol(signal, 21, 3, deriv=0, return_meta=True)
        assert meta["n_reduced"] >= 1 or meta["n_too_short"] >= 1
        assert np.all(np.isfinite(result[0:5])), "5-frame segment should produce finite output"
        assert np.all(np.isfinite(result[12:100]))


# ============================================================
# 3. chunked_savgol — equivalence with scipy on clean data
# ============================================================

class TestChunkedSavgolEquivalence:

    def test_matches_scipy_deriv0(self):
        """On clean data, chunked_savgol must equal scipy savgol_filter."""
        signal = np.random.RandomState(42).randn(500)
        expected = savgol_filter(signal, 21, 3, deriv=0, mode='interp')
        actual = chunked_savgol(signal, 21, 3, deriv=0)
        np.testing.assert_allclose(actual, expected, atol=1e-12)

    def test_matches_scipy_deriv1(self):
        signal = np.random.RandomState(42).randn(500)
        expected = savgol_filter(signal, 21, 3, deriv=1, delta=1/120.0, mode='interp')
        actual = chunked_savgol(signal, 21, 3, deriv=1, delta=1/120.0)
        np.testing.assert_allclose(actual, expected, atol=1e-12)

    def test_matches_scipy_deriv2(self):
        signal = np.random.RandomState(42).randn(500)
        expected = savgol_filter(signal, 21, 3, deriv=2, delta=1/120.0, mode='interp')
        actual = chunked_savgol(signal, 21, 3, deriv=2, delta=1/120.0)
        np.testing.assert_allclose(actual, expected, atol=1e-12)


# ============================================================
# 4. chunked_savgol — metadata
# ============================================================

class TestChunkedSavgolMetadata:

    def test_metadata_single_chunk(self):
        signal = np.ones(100)
        _, meta = chunked_savgol(signal, 21, 3, deriv=0, return_meta=True)
        assert meta["n_chunks"] == 1
        assert meta["n_full"] == 1
        assert meta["n_reduced"] == 0
        assert meta["n_too_short"] == 0

    def test_metadata_two_chunks(self):
        signal = np.ones(100)
        signal[40:50] = np.nan
        _, meta = chunked_savgol(signal, 21, 3, deriv=0, return_meta=True)
        assert meta["n_chunks"] == 2
        assert meta["n_full"] + meta["n_reduced"] + meta["n_too_short"] == 2

    def test_metadata_mixed_tiers(self):
        signal = np.ones(200)
        signal[3:7] = np.nan    # splits [0:3] (too short) and [7:200] (full)
        _, meta = chunked_savgol(signal, 21, 3, deriv=1, delta=1.0, return_meta=True)
        assert meta["n_chunks"] == 2
        assert meta["n_too_short"] >= 1
        assert meta["too_short_frames"] == 3


# ============================================================
# 5. Quaternion manifold preservation
# ============================================================

class TestQuaternionManifold:

    def test_renorm_after_savgol(self):
        """After SavGol smoothing + renorm, all finite quats must be unit-length."""
        q = _random_unit_quaternions(500)
        q[200:220] = np.nan

        for ax in range(4):
            q[:, ax] = chunked_savgol(q[:, ax], 21, 3, deriv=0)

        # Before renorm: norms likely drift from 1.0
        norms_before = np.linalg.norm(q, axis=1)
        finite_mask = np.isfinite(norms_before)

        # Renormalize (same logic as NB06)
        n = np.linalg.norm(q, axis=1, keepdims=True)
        n = np.where(n < 1e-12, 1.0, n)
        q_normed = q / n

        norms_after = np.linalg.norm(q_normed, axis=1)
        finite_after = np.isfinite(norms_after)

        np.testing.assert_allclose(norms_after[finite_after], 1.0, atol=1e-10)

    def test_nan_gap_preserved_in_quaternions(self):
        """NaN gap rows remain NaN after SavGol on quaternion components."""
        q = _random_unit_quaternions(100)
        q[40:50] = np.nan

        for ax in range(4):
            q[:, ax] = chunked_savgol(q[:, ax], 21, 3, deriv=0)

        assert np.all(np.isnan(q[40:50])), "NaN gap must persist through chunked SavGol"
        assert np.all(np.isfinite(q[0:40])), "Pre-gap quaternions must be finite"
        assert np.all(np.isfinite(q[50:100])), "Post-gap quaternions must be finite"


# ============================================================
# 6. Angular acceleration NaN safety
# ============================================================

class TestAngularAccelerationNanSafety:

    def test_alpha_nan_gap_does_not_bleed(self):
        """Alpha computation must not bleed NaN into valid omega frames."""
        rng = np.random.RandomState(42)
        omega = rng.randn(240, 3) * 0.5
        omega[100:120, :] = np.nan

        alpha = compute_angular_acceleration(omega, 120.0, 21, 3)

        assert np.all(np.isnan(alpha[100:120])), "Gap must be NaN in alpha"
        assert np.all(np.isfinite(alpha[10:90])), "Interior pre-gap must be finite"
        assert np.all(np.isfinite(alpha[130:230])), "Interior post-gap must be finite"

    def test_alpha_all_nan_returns_nan(self):
        omega = np.full((100, 3), np.nan)
        alpha = compute_angular_acceleration(omega, 120.0, 21, 3)
        assert np.all(np.isnan(alpha))


# ============================================================
# 7. Chunked omega dispatch (NaN-safe angular velocity)
# ============================================================

class TestChunkedOmegaDispatch:

    def test_nan_gap_produces_nan_omega(self):
        """Omega must be NaN where quaternions are NaN."""
        q = _random_unit_quaternions(200)
        q[80:100] = np.nan

        omega = _chunked_omega_dispatch(q, 120.0, quaternion_log_angular_velocity, 'local')

        assert np.all(np.isnan(omega[80:100])), "NaN quat frames must produce NaN omega"
        assert np.all(np.isfinite(omega[5:75])), "Pre-gap interior must be finite"
        assert np.all(np.isfinite(omega[105:195])), "Post-gap interior must be finite"

    def test_single_frame_segment_is_nan(self):
        """A 1-frame segment cannot produce omega (needs 2 frames for diff)."""
        q = np.full((10, 4), np.nan)
        q[5] = [0, 0, 0, 1]  # single finite frame

        omega = _chunked_omega_dispatch(q, 120.0, quaternion_log_angular_velocity, 'local')
        assert np.all(np.isnan(omega[5])), "Single frame cannot produce omega"

    def test_clean_data_matches_direct(self):
        """On clean data, chunked dispatch must match direct computation."""
        q = _random_unit_quaternions(300)
        direct = quaternion_log_angular_velocity(q, 120.0, 'local')
        chunked = _chunked_omega_dispatch(q, 120.0, quaternion_log_angular_velocity, 'local')
        np.testing.assert_allclose(chunked, direct, atol=1e-10)

    def test_enhanced_api_uses_chunking(self):
        """compute_angular_velocity_enhanced must use chunked dispatch."""
        q = _random_unit_quaternions(200)
        q[80:100] = np.nan

        omega, meta = compute_angular_velocity_enhanced(q, 120.0, method='quaternion_log')

        assert meta.get('chunked', False), "Enhanced API must report chunked=True"
        assert np.all(np.isnan(omega[80:100])), "NaN gap must propagate"
        assert np.all(np.isfinite(omega[5:75]))

    def test_find_finite_quat_segments(self):
        """Segment finder must correctly identify contiguous finite quaternion runs."""
        q = np.ones((20, 4))
        q[5:8] = np.nan
        q[15:17] = np.nan

        segs = _find_finite_quat_segments(q)
        assert segs == [(0, 5), (8, 15), (17, 20)]


# ============================================================
# 8. WBCoM reliability scoring
# ============================================================

class TestComReliability:

    def test_full_coverage_reliable(self):
        r = compute_com_reliability(100.0)
        assert r["com_reliability_flag"] == "RELIABLE"
        assert r["com_reliability_score"] == 1.0

    def test_threshold_boundary_reliable(self):
        r = compute_com_reliability(90.0)
        assert r["com_reliability_flag"] == "RELIABLE"
        assert r["com_reliability_score"] == 0.9

    def test_below_threshold_unreliable(self):
        r = compute_com_reliability(89.9)
        assert r["com_reliability_flag"] == "UNRELIABLE"

    def test_zero_coverage(self):
        r = compute_com_reliability(0.0)
        assert r["com_reliability_score"] == 0.0
        assert r["com_reliability_flag"] == "UNRELIABLE"

    def test_score_proportional(self):
        r = compute_com_reliability(68.0)
        assert r["com_reliability_score"] == 0.68

    def test_custom_threshold(self):
        r = compute_com_reliability(80.0, threshold_pct=75.0)
        assert r["com_reliability_flag"] == "RELIABLE"
        r2 = compute_com_reliability(74.9, threshold_pct=75.0)
        assert r2["com_reliability_flag"] == "UNRELIABLE"

    def test_clamp_above_100(self):
        r = compute_com_reliability(105.0)
        assert r["com_reliability_score"] == 1.0


# ============================================================
# 9. Contiguous segment finder (unit test for foundation)
# ============================================================

class TestContiguousSegmentFinder:

    def test_no_nans(self):
        x = np.ones(10)
        segs = _find_contiguous_finite_segments(x)
        assert segs == [(0, 10)]

    def test_all_nans(self):
        x = np.full(10, np.nan)
        segs = _find_contiguous_finite_segments(x)
        assert segs == []

    def test_leading_nan(self):
        x = np.ones(10)
        x[0:3] = np.nan
        segs = _find_contiguous_finite_segments(x)
        assert segs == [(3, 10)]

    def test_trailing_nan(self):
        x = np.ones(10)
        x[7:10] = np.nan
        segs = _find_contiguous_finite_segments(x)
        assert segs == [(0, 7)]

    def test_middle_gap(self):
        x = np.ones(20)
        x[8:12] = np.nan
        segs = _find_contiguous_finite_segments(x)
        assert segs == [(0, 8), (12, 20)]

    def test_inf_treated_as_non_finite(self):
        x = np.ones(10)
        x[4] = np.inf
        segs = _find_contiguous_finite_segments(x)
        assert segs == [(0, 4), (5, 10)]


# ============================================================
# 10. Adaptive SavGol window formula correctness
# ============================================================

class TestAdaptiveWindowFormula:

    def test_trunk_6hz_gives_w21(self):
        """Trunk f_butter=6.0 Hz → W=21, F3dB≈7.14 Hz at fs=120."""
        cutoffs = {"Hips__px": 6.0, "Hips__py": 6.0, "Hips__pz": 6.0}
        w_map, audit = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3)
        assert w_map["Hips"] == 21
        assert abs(audit["Hips"]["sg_f3db_hz"] - 7.14) < 0.1

    def test_upper_distal_12hz_gives_w11(self):
        """Upper distal f_butter=12.0 Hz → W=11 at fs=120."""
        cutoffs = {"LeftHand__px": 12.0, "LeftHand__py": 12.0, "LeftHand__pz": 12.0}
        w_map, audit = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3)
        assert w_map["LeftHand"] == 11

    def test_head_8hz_gives_w15(self):
        """Head f_butter=8.0 Hz → W=15 at fs=120."""
        cutoffs = {"Head__px": 8.0, "Head__py": 8.0, "Head__pz": 8.0}
        w_map, audit = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3)
        assert w_map["Head"] == 15

    def test_output_always_odd(self):
        """All computed windows must be odd integers."""
        cutoffs = {
            "A__px": 5.0, "A__py": 5.0, "A__pz": 5.0,
            "B__px": 7.5, "B__py": 7.5, "B__pz": 7.5,
            "C__px": 11.0, "C__py": 11.0, "C__pz": 11.0,
        }
        w_map, _ = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3)
        for seg, w in w_map.items():
            assert w % 2 == 1, f"{seg} has even W={w}"

    def test_actual_multiplier_near_target(self):
        """Effective F3dB / f_butter should be close to 1.2x (within rounding)."""
        cutoffs = {"Spine__px": 6.0, "Spine__py": 6.0, "Spine__pz": 6.0}
        _, audit = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3, multiplier=1.2)
        mult = audit["Spine"]["actual_multiplier"]
        assert 1.0 <= mult <= 1.5, f"Multiplier {mult} out of expected range"


# ============================================================
# 11. Adaptive SavGol window guardrails (floor and ceiling)
# ============================================================

class TestAdaptiveWindowGuardrails:

    def test_floor_clamps_high_cutoff(self):
        """Very high f_butter → formula gives W<7 → clamped to floor=7."""
        cutoffs = {"Fast__px": 30.0, "Fast__py": 30.0, "Fast__pz": 30.0}
        w_map, _ = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3, floor_w=7)
        assert w_map["Fast"] == 7

    def test_ceiling_clamps_low_cutoff(self):
        """Very low f_butter → formula gives W>21 → clamped to ceiling=21."""
        cutoffs = {"Slow__px": 2.0, "Slow__py": 2.0, "Slow__pz": 2.0}
        w_map, _ = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3, ceiling_w=21)
        assert w_map["Slow"] == 21

    def test_floor_respects_polyorder(self):
        """Floor must be >= polyorder + 2 (forced odd)."""
        cutoffs = {"X__px": 50.0, "X__py": 50.0, "X__pz": 50.0}
        w_map, _ = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3, floor_w=3)
        assert w_map["X"] >= 5, "Floor must be at least polyorder + 2"
        assert w_map["X"] % 2 == 1

    def test_custom_ceiling(self):
        """Custom ceiling is respected."""
        cutoffs = {"Mid__px": 6.0, "Mid__py": 6.0, "Mid__pz": 6.0}
        w_map, _ = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3, ceiling_w=15)
        assert w_map["Mid"] <= 15


# ============================================================
# 12. Adaptive SavGol fallback behaviour
# ============================================================

class TestAdaptiveWindowFallback:

    def test_empty_cutoffs_returns_empty(self):
        """Empty per_joint_cutoffs → empty W_LEN_MAP."""
        w_map, audit = compute_adaptive_sg_windows({}, fs=120.0)
        assert w_map == {}
        assert audit == {}

    def test_none_cutoffs_skipped(self):
        """Columns with None cutoff are gracefully skipped."""
        cutoffs = {"A__px": None, "A__py": 8.0, "A__pz": 8.0}
        w_map, audit = compute_adaptive_sg_windows(cutoffs, fs=120.0)
        assert "A" in w_map

    def test_quaternion_columns_ignored(self):
        """Quaternion columns (e.g. __qx) should not produce entries."""
        cutoffs = {"Hips__qx": 6.0, "Hips__qy": 6.0, "Hips__qz": 6.0, "Hips__qw": 6.0}
        w_map, _ = compute_adaptive_sg_windows(cutoffs, fs=120.0)
        assert "Hips" not in w_map

    def test_region_fallback(self):
        """compute_adaptive_sg_windows_from_regions produces valid windows."""
        region_cutoffs = {"trunk": 6.0, "head": 8.0, "upper_distal": 12.0}
        joints = ["Hips", "Head", "LeftHand"]
        w_map, audit = compute_adaptive_sg_windows_from_regions(
            region_cutoffs, joints, fs=120.0, polyorder=3,
        )
        assert "Hips" in w_map
        assert "Head" in w_map
        assert "LeftHand" in w_map
        assert w_map["Hips"] > w_map["LeftHand"]


# ============================================================
# 13. Per-axis aggregation (max strategy)
# ============================================================

class TestPerAxisAggregation:

    def test_max_cutoff_used(self):
        """Per-segment cutoff = max(px, py, pz)."""
        cutoffs = {"Hips__px": 6.0, "Hips__py": 5.5, "Hips__pz": 7.0}
        _, audit = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3)
        assert audit["Hips"]["butter_cutoff_hz"] == 7.0

    def test_single_axis_still_works(self):
        """If only one axis has a cutoff, it still produces a valid entry."""
        cutoffs = {"Arm__px": 9.0}
        w_map, audit = compute_adaptive_sg_windows(cutoffs, fs=120.0, polyorder=3)
        assert "Arm" in w_map
        assert audit["Arm"]["butter_cutoff_hz"] == 9.0


# ============================================================
# 14. Adaptive SavGol — zero phase-delay property
# ============================================================

class TestAdaptiveSavgolNoPhaseJitter:

    def test_zero_crossings_invariant_to_window(self):
        """
        SavGol with different W_LEN on the same sine should preserve
        zero-crossing locations (symmetric FIR → zero phase delay).
        Integer quantization of the crossing detector allows ±1 sample.
        """
        n, fs, freq = 600, 120.0, 5.0
        t = np.arange(n) / fs
        signal = np.sin(2 * np.pi * freq * t)

        smooth_w21 = chunked_savgol(signal, 21, 3, deriv=0)
        smooth_w11 = chunked_savgol(signal, 11, 3, deriv=0)

        def _zero_crossings(x):
            return np.where(np.diff(np.sign(x)))[0]

        zc_21 = _zero_crossings(smooth_w21[30:-30])
        zc_11 = _zero_crossings(smooth_w11[30:-30])

        assert len(zc_21) == len(zc_11), "Same number of zero crossings"
        np.testing.assert_allclose(zc_21, zc_11, atol=1)

    def test_deriv1_peak_locations_invariant(self):
        """
        First derivative (velocity) peak positions must not shift
        between different window lengths for signals within the passband.
        """
        n, fs, freq = 600, 120.0, 3.0
        t = np.arange(n) / fs
        signal = np.sin(2 * np.pi * freq * t)

        vel_w21 = chunked_savgol(signal, 21, 3, deriv=1, delta=1.0/fs)
        vel_w11 = chunked_savgol(signal, 11, 3, deriv=1, delta=1.0/fs)

        interior = slice(50, -50)
        peaks_21 = np.where(np.diff(np.sign(np.diff(vel_w21[interior]))) < 0)[0]
        peaks_11 = np.where(np.diff(np.sign(np.diff(vel_w11[interior]))) < 0)[0]

        # Peaks should align within 1 sample
        assert len(peaks_21) == len(peaks_11), "Different number of peaks"
        np.testing.assert_allclose(peaks_21, peaks_11, atol=1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
