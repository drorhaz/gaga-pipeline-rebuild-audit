"""
Comprehensive pytest suite for the Single-Pass PCHIP position resampler.

Covers: clean signal, gap < 1.0s, gap > 1.0s, boundary (no extrapolation),
< 2 points edge case, and per-joint axis rule (all-or-nothing validity).
"""

import pytest
import numpy as np
from src.resampling import resample_pos_pchip, resample_time_grid


# -----------------------------------------------------------------------------
# Fixtures and helpers
# -----------------------------------------------------------------------------

@pytest.fixture
def max_gap_pos_sec():
    return 1.0


@pytest.fixture
def fs_target():
    return 120.0


def build_grid(time_s, fs_target=120.0):
    """Build uniform 120 Hz grid over [time_s[0], time_s[-1]]."""
    return resample_time_grid(time_s, fs_target)


# -----------------------------------------------------------------------------
# 1. Clean signal: no NaNs, uniform or jittered time
# -----------------------------------------------------------------------------

class TestCleanSignal:
    """No NaNs; output should have no unexpected NaNs in interior."""

    def test_clean_uniform_time_no_nans_in_interior(self, fs_target, max_gap_pos_sec):
        """Clean signal with uniform time -> no NaNs in interior."""
        n_raw = 50
        time_s = np.linspace(0.0, 1.0, n_raw)
        # One joint, linear trajectory
        pos = np.zeros((n_raw, 1, 3))
        pos[:, 0, 0] = np.linspace(0.0, 1.0, n_raw)
        pos[:, 0, 1] = 0.0
        pos[:, 0, 2] = 0.0

        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        assert out.shape == (len(t_dst), 1, 3)
        # All grid points are within [0, 1] and within 0.5s of some valid sample -> no interior NaN
        assert np.all(np.isfinite(out[:, 0, :])), "Clean signal should have no NaN in interior"

    def test_clean_jittered_time_no_nans(self, fs_target, max_gap_pos_sec):
        """Jittered raw timestamps still produce finite output in range."""
        np.random.seed(42)
        n_raw = 60
        time_s = np.sort(np.random.uniform(0.0, 1.0, n_raw))
        pos = np.zeros((n_raw, 1, 3))
        pos[:, 0, 0] = np.linspace(0.0, 2.0, n_raw)
        pos[:, 0, 1] = np.sin(np.linspace(0, 4 * np.pi, n_raw))
        pos[:, 0, 2] = 0.0

        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        # Interior grid points (excluding possible boundary) should be finite
        t0, t1 = time_s[0], time_s[-1]
        interior = (t_dst >= t0) & (t_dst <= t1)
        assert np.all(np.isfinite(out[interior, 0, :])), "Interior of clean jittered signal should be finite"

    def test_clean_signal_values_close_to_expected(self, fs_target, max_gap_pos_sec):
        """Resampled values should match trajectory (e.g. linear) within tolerance."""
        time_s = np.array([0.0, 0.5, 1.0])
        pos = np.zeros((3, 1, 3))
        pos[:, 0, 0] = [0.0, 0.5, 1.0]
        pos[:, 0, 1] = [0.0, 0.0, 0.0]
        pos[:, 0, 2] = [0.0, 0.0, 0.0]

        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        # At t_dst == 0.5 we expect x ≈ 0.5
        mid = np.argmin(np.abs(t_dst - 0.5))
        assert np.isfinite(out[mid, 0, 0])
        assert np.allclose(out[mid, 0, 0], 0.5, atol=1e-5)


# -----------------------------------------------------------------------------
# 2. Gap < 1.0 s: all grid points in gap get values
# -----------------------------------------------------------------------------

class TestGapLessThanOneSecond:
    """Gap duration < max_gap_pos_sec -> grid points in gap are filled (within half-gap)."""

    def test_small_gap_all_filled(self, fs_target, max_gap_pos_sec):
        """One gap of 0.5 s: all grid points within gap should be non-NaN."""
        # Valid at t=0, 0.5, 1.0; gap in between 0.25..0.75 is only 0.5s total
        time_s = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        pos = np.full((5, 1, 3), np.nan)
        pos[0, 0, :] = [0.0, 0.0, 0.0]
        pos[2, 0, :] = [0.5, 0.0, 0.0]
        pos[4, 0, :] = [1.0, 0.0, 0.0]
        # Frames 1 and 3 are NaN -> two gaps of 0.25s each; each is < 1s so interior gets filled
        # Actually: valid indices 0, 2, 4. Gaps: 0.25s and 0.25s. So any grid point is at most 0.25s from a valid sample -> within 0.5s.
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        # All grid points in [0, 1] are within 0.5s of at least one of 0, 0.5, 1.0
        in_range = (t_dst >= 0.0) & (t_dst <= 1.0)
        assert np.all(np.isfinite(out[in_range, 0, :])), "Gap < 1s: points in range should be filled"

    def test_half_second_gap_filled(self, fs_target, max_gap_pos_sec):
        """Single contiguous gap of 0.5 s in middle: filled."""
        time_s = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        pos = np.zeros((11, 1, 3))
        pos[:, 0, 0] = np.linspace(0, 1, 11)
        pos[3, 0, :] = np.nan
        pos[4, 0, :] = np.nan
        pos[5, 0, :] = np.nan
        # Valid at 0, 0.1, 0.2, 0.6, 0.7, 0.8, 0.9, 1.0. Gap from 0.3 to 0.5 (0.2s) + 0.5 to 0.6 (0.1s) -> one gap 0.3s. All within 0.5s.
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        in_range = (t_dst >= time_s[0]) & (t_dst <= time_s[-1])
        assert np.all(np.isfinite(out[in_range, 0, :])), "0.3s gap should be filled"


# -----------------------------------------------------------------------------
# 3. Gap > 1.0 s: grid points in middle of gap are NaN
# -----------------------------------------------------------------------------

class TestGapGreaterThanOneSecond:
    """Gap > max_gap_pos_sec -> grid points beyond half-gap from valid samples are NaN."""

    def test_large_gap_middle_nan(self, fs_target, max_gap_pos_sec):
        """Gap of 1.5 s: grid points in middle (>.5s from either side) must be NaN."""
        time_s = np.array([0.0, 0.5, 1.0, 2.5, 3.0, 3.5, 4.0])
        pos = np.zeros((7, 1, 3))
        pos[:, 0, 0] = [0, 0.5, 1, np.nan, np.nan, np.nan, 4]
        pos[:, 0, 1] = 0.0
        pos[:, 0, 2] = 0.0
        pos[3:6, 0, :] = np.nan
        # Valid at t=0, 0.5, 1.0 and t=4.0. Gap 1.0 to 4.0 = 3s. So grid points with t in (1.5, 3.5) are >0.5 from 1.0 and >0.5 from 4.0 -> NaN.
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        # Points strictly between 1.5 and 3.5 should be NaN (more than 0.5 from 1.0 and 4.0)
        mid_gap = (t_dst > 1.0 + 0.5) & (t_dst < 4.0 - 0.5)
        assert np.any(mid_gap), "Test should have some grid points in the gap middle"
        assert np.all(np.isnan(out[mid_gap, 0, :])), "Grid points in middle of >1s gap must be NaN"

    def test_exactly_one_second_gap_boundary(self, fs_target, max_gap_pos_sec):
        """Gap exactly 1.0 s: boundary at 0.5s from each side; points at exactly 0.5 from valid are still valid."""
        time_s = np.array([0.0, 1.0, 2.0])
        pos = np.zeros((3, 1, 3))
        pos[0, 0, :] = [0, 0, 0]
        pos[1, 0, :] = np.nan
        pos[2, 0, :] = [2, 0, 0]
        # Valid at 0 and 2. Midpoint t=1.0 is exactly 1.0 from 0 and 1.0 from 2. So distance = 1.0 > 0.5 -> t=1.0 should be NaN.
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        at_one = np.abs(t_dst - 1.0) < 1e-9
        assert np.any(at_one)
        assert np.all(np.isnan(out[at_one, 0, :])), "t=1.0 is 1.0s from both ends -> NaN (half-gap 0.5)"


# -----------------------------------------------------------------------------
# 4. Boundary: no extrapolation
# -----------------------------------------------------------------------------

class TestBoundaryNoExtrapolation:
    """Grid points before first valid or after last valid timestamp must be NaN."""

    def test_leading_trailing_nan(self, fs_target, max_gap_pos_sec):
        """Valid data only in [0.2, 0.8]; grid 0..1 -> leading and trailing NaN."""
        time_s = np.linspace(0.0, 1.0, 11)
        pos = np.full((11, 1, 3), np.nan)
        pos[2:9, 0, 0] = np.linspace(0.2, 0.8, 7)
        pos[2:9, 0, 1] = 0.0
        pos[2:9, 0, 2] = 0.0
        # Valid times: 0.2, 0.28, ..., 0.8
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        assert np.all(np.isnan(out[t_dst < 0.2, 0, :])), "Before first valid must be NaN"
        assert np.all(np.isnan(out[t_dst > 0.8, 0, :])), "After last valid must be NaN"

    def test_first_last_valid_preserved(self, fs_target, max_gap_pos_sec):
        """At first and last valid time, output should match input (no extrapolation)."""
        time_s = np.array([0.0, 0.5, 1.0])
        pos = np.zeros((3, 1, 3))
        pos[:, 0, :] = [[0, 0, 0], [0.5, 1, 0], [1, 2, 0]]
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        i0 = np.argmin(np.abs(t_dst - 0.0))
        i1 = np.argmin(np.abs(t_dst - 1.0))
        assert np.allclose(out[i0, 0, :], [0, 0, 0], atol=1e-9)
        assert np.allclose(out[i1, 0, :], [1, 2, 0], atol=1e-9)


# -----------------------------------------------------------------------------
# 5. < 2 points: joint returns all NaN
# -----------------------------------------------------------------------------

class TestInsufficientData:
    """Joint with 0 or 1 valid sample -> entire column NaN."""

    def test_zero_valid_points_all_nan(self, fs_target, max_gap_pos_sec):
        """Joint with no valid frames -> all NaN."""
        time_s = np.array([0.0, 0.5, 1.0])
        pos = np.full((3, 2, 3), np.nan)
        pos[:, 0, :] = [[0, 0, 0], [0.5, 0, 0], [1, 0, 0]]
        # Joint 1: all NaN
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        assert np.all(np.isnan(out[:, 1, :])), "Joint with 0 valid points must be all NaN"
        assert np.all(np.isfinite(out[:, 0, :])), "Joint 0 should still be filled"

    def test_one_valid_point_all_nan(self, fs_target, max_gap_pos_sec):
        """Joint with exactly one valid frame -> all NaN for that joint."""
        time_s = np.array([0.0, 0.5, 1.0])
        pos = np.zeros((3, 2, 3))
        pos[:, 0, :] = [[0, 0, 0], [0.5, 0, 0], [1, 0, 0]]
        pos[0, 1, :] = [1, 1, 1]
        pos[1, 1, :] = np.nan
        pos[2, 1, :] = np.nan
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        assert np.all(np.isnan(out[:, 1, :])), "Joint with 1 valid point must be all NaN"


# -----------------------------------------------------------------------------
# 6. Per-joint axis rule: all-or-nothing validity
# -----------------------------------------------------------------------------

class TestPerJointAxisRule:
    """A timestamp is valid for a joint only if X, Y, Z are all non-NaN."""

    def test_frame_with_nan_z_excluded_from_valid_set(self, fs_target, max_gap_pos_sec):
        """One frame has X,Y valid but Z NaN -> that frame excluded; PCHIP uses other timestamps only."""
        time_s = np.array([0.0, 0.5, 1.0, 1.5])
        pos = np.zeros((4, 1, 3))
        pos[:, 0, 0] = [0, 1, 2, 3]
        pos[:, 0, 1] = [0, 0, 0, 0]
        pos[:, 0, 2] = [0, 0, np.nan, 0]
        # Valid for joint 0: indices 0, 1, 3 (t=0, 0.5, 1.5). t=1.0 excluded.
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        # At t≈1.0 the interpolant should be between t=0.5 and t=1.5 (linear 1 and 3 -> 2), not using the (2,0,nan) sample
        idx_1 = np.argmin(np.abs(t_dst - 1.0))
        assert np.isfinite(out[idx_1, 0, 0])
        assert np.allclose(out[idx_1, 0, 0], 2.0, atol=1e-5), "Interpolation should use t=0.5 and t=1.5 only"

    def test_two_joints_one_with_partial_nan(self, fs_target, max_gap_pos_sec):
        """Two joints: one has all valid; other has one frame with Z NaN -> that joint has 2 valid points, other 3."""
        time_s = np.array([0.0, 0.5, 1.0])
        pos = np.zeros((3, 2, 3))
        pos[:, 0, :] = [[0, 0, 0], [0.5, 0, 0], [1, 0, 0]]
        pos[:, 1, 0] = [1, 2, 3]
        pos[:, 1, 1] = [0, 0, 0]
        pos[:, 1, 2] = [0, 0, np.nan]
        # Joint 1: valid only at t=0 and t=0.5 (t=1.0 has Z NaN). So 2 points -> PCHIP still fits.
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)

        assert np.all(np.isfinite(out[:, 0, :]))
        # Joint 1: valid at 0 and 0.5 only; at t=1.0 we are outside [0, 0.5] so NaN (extrapolation)
        assert np.all(np.isnan(out[t_dst > 0.5 + 1e-9, 1, :])), "Joint 1 valid only up to 0.5; beyond is NaN"


# -----------------------------------------------------------------------------
# Shape and API
# -----------------------------------------------------------------------------

class TestShapeAndAPI:
    """Output shape, t_dst optional, max_gap_pos_sec half-gap."""

    def test_output_shape(self, fs_target, max_gap_pos_sec):
        """Output shape is (len(t_dst), J, 3)."""
        time_s = np.linspace(0, 1, 20)
        pos = np.zeros((20, 3, 3))
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=max_gap_pos_sec)
        assert out.shape == (len(t_dst), 3, 3)

    def test_t_dst_optional_builds_grid(self, max_gap_pos_sec):
        """When t_dst is None, grid is built from time_s and fs_target."""
        time_s = np.array([0.0, 1.0])
        pos = np.zeros((2, 1, 3))
        pos[:, 0, :] = [[0, 0, 0], [1, 0, 0]]
        out = resample_pos_pchip(time_s, pos, t_dst=None, max_gap_pos_sec=max_gap_pos_sec, fs_target=100.0)
        expected_len = 101
        assert out.shape[0] == expected_len
        assert out.shape[1] == 1 and out.shape[2] == 3

    def test_half_gap_rule_used(self, fs_target):
        """max_dist = max_gap_pos_sec / 2 is used (e.g. 0.5 for 1.0)."""
        time_s = np.array([0.0, 1.0, 2.0])
        pos = np.zeros((3, 1, 3))
        pos[0, 0, :] = [0, 0, 0]
        pos[1, 0, :] = np.nan
        pos[2, 0, :] = [2, 0, 0]
        t_dst = build_grid(time_s, fs_target)
        out = resample_pos_pchip(time_s, pos, t_dst=t_dst, max_gap_pos_sec=1.0)
        at_one = np.abs(t_dst - 1.0) < 1e-9
        assert np.all(np.isnan(out[at_one, 0, :]))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
