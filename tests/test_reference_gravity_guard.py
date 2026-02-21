"""
Tests for Phase 3 Gravity Guard in detect_static_reference.

Scenarios:
1. Standing pose  — passes both stillness and gravity guard.
2. Floor pose     — fails gravity guard, triggers identity fallback.
3. NaN occlusion  — Head fully occluded, triggers identity fallback.
4. Unit-scale warning — mm-scale positions trigger the >50 m warning.
5. Backwards compat — no pos_m/schema → old behaviour, no crash.
"""

import logging
import pytest
import numpy as np
from scipy.spatial.transform import Rotation as R

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.reference import detect_static_reference, compute_q_ref_and_ref_qc


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mini_schema():
    return {
        "joint_names": ["Hips", "Spine", "Spine1", "Neck", "Head"],
        "root_joint": "Hips",
        "parent_map": {
            "Hips": None, "Spine": "Hips", "Spine1": "Spine",
            "Neck": "Spine1", "Head": "Neck",
        },
        "depth_order": ["Hips", "Spine", "Spine1", "Neck", "Head"],
    }


@pytest.fixture
def base_cfg():
    return {
        "FS_TARGET": 120.0,
        "REF_SEARCH_SEC": 8.0,
        "REF_WINDOW_SEC": 1.0,
        "STATIC_SEARCH_STEP_SEC": 0.1,
        "MOTION_THR_LOW": 0.3,
        "MOTION_THR_STD": 0.15,
        "GRAVITY_AXIS": "y",
        "MIN_HEAD_PELVIS_VERTICAL_M": 0.5,
    }


def _make_static_quats(n_frames, n_joints, noise=1e-4, seed=0):
    """Identity quaternions with tiny noise — mimics a perfectly still subject."""
    rng = np.random.RandomState(seed)
    q = np.zeros((n_frames, n_joints, 4))
    for j in range(n_joints):
        for t in range(n_frames):
            rv = rng.randn(3) * noise
            q[t, j] = R.from_rotvec(rv).as_quat()
    return q


def _make_time(n_frames, fs):
    return np.arange(n_frames) / fs


# ---------------------------------------------------------------------------
# 1. Standing pose — gravity guard passes
# ---------------------------------------------------------------------------

class TestStandingPose:

    def test_upright_window_found(self, mini_schema, base_cfg):
        fs = base_cfg["FS_TARGET"]
        n_frames = int(10 * fs)
        n_joints = len(mini_schema["joint_names"])

        time_s = _make_time(n_frames, fs)
        q_local = _make_static_quats(n_frames, n_joints)

        pos_m = np.zeros((n_frames, n_joints, 3))
        head_idx = 4
        pelvis_idx = 0
        pos_m[:, pelvis_idx, 1] = 0.95
        pos_m[:, head_idx, 1] = 1.60

        viz_idx = list(range(n_joints))
        ref = detect_static_reference(
            time_s, q_local, viz_idx, base_cfg,
            pos_m=pos_m, schema=mini_schema,
        )

        assert ref["t_pose_failed"] is False
        assert ref["gravity_guard_passed"] is True
        assert ref["ref_is_fallback"] is False
        assert "gravity" in ref["method"] or ref["method"] == "criteria"

    def test_qref_is_markley_not_identity(self, mini_schema, base_cfg):
        """When gravity guard passes, q_ref should come from Markley mean."""
        fs = base_cfg["FS_TARGET"]
        n_frames = int(10 * fs)
        n_joints = len(mini_schema["joint_names"])

        time_s = _make_time(n_frames, fs)
        q_local = _make_static_quats(n_frames, n_joints)

        pos_m = np.zeros((n_frames, n_joints, 3))
        pos_m[:, 0, 1] = 0.95
        pos_m[:, 4, 1] = 1.60

        viz_idx = list(range(n_joints))
        ref = detect_static_reference(
            time_s, q_local, viz_idx, base_cfg,
            pos_m=pos_m, schema=mini_schema,
        )

        export_idx = list(range(n_joints))
        q_ref, qc = compute_q_ref_and_ref_qc(
            time_s, q_local, ref, export_idx, viz_idx, base_cfg,
        )

        assert q_ref.shape == (n_joints, 4)
        assert qc.get("t_pose_failed") is not True
        identity = np.array([0.0, 0.0, 0.0, 1.0])
        for j in range(n_joints):
            assert np.isfinite(q_ref[j]).all()
            assert np.allclose(q_ref[j], identity, atol=0.05)


# ---------------------------------------------------------------------------
# 2. Floor pose — gravity guard rejects, identity fallback
# ---------------------------------------------------------------------------

class TestFloorPose:

    def test_floor_triggers_fallback(self, mini_schema, base_cfg):
        fs = base_cfg["FS_TARGET"]
        n_frames = int(10 * fs)
        n_joints = len(mini_schema["joint_names"])

        time_s = _make_time(n_frames, fs)
        q_local = _make_static_quats(n_frames, n_joints)

        pos_m = np.zeros((n_frames, n_joints, 3))
        pos_m[:, 0, 1] = 0.10   # pelvis on floor
        pos_m[:, 4, 1] = 0.15   # head on floor

        viz_idx = list(range(n_joints))
        ref = detect_static_reference(
            time_s, q_local, viz_idx, base_cfg,
            pos_m=pos_m, schema=mini_schema,
        )

        assert ref["t_pose_failed"] is True
        assert ref["gravity_guard_passed"] is False
        assert ref["ref_is_fallback"] is True
        assert "fallback_identity" in ref["method"]

    def test_identity_qref_on_floor(self, mini_schema, base_cfg):
        """compute_q_ref_and_ref_qc must return [0,0,0,1] for every joint."""
        fs = base_cfg["FS_TARGET"]
        n_frames = int(10 * fs)
        n_joints = len(mini_schema["joint_names"])

        time_s = _make_time(n_frames, fs)
        q_local = _make_static_quats(n_frames, n_joints)

        pos_m = np.zeros((n_frames, n_joints, 3))
        pos_m[:, 0, 1] = 0.10
        pos_m[:, 4, 1] = 0.15

        viz_idx = list(range(n_joints))
        ref = detect_static_reference(
            time_s, q_local, viz_idx, base_cfg,
            pos_m=pos_m, schema=mini_schema,
        )
        assert ref["t_pose_failed"] is True

        export_idx = list(range(n_joints))
        q_ref, qc = compute_q_ref_and_ref_qc(
            time_s, q_local, ref, export_idx, viz_idx, base_cfg,
        )

        identity = np.array([0.0, 0.0, 0.0, 1.0])
        for j in range(n_joints):
            np.testing.assert_array_equal(q_ref[j], identity)

        assert qc["t_pose_failed"] is True
        assert qc["gravity_guard_passed"] is False


# ---------------------------------------------------------------------------
# 3. NaN occlusion — Head fully occluded
# ---------------------------------------------------------------------------

class TestNaNOcclusion:

    def test_occluded_head_triggers_fallback(self, mini_schema, base_cfg):
        fs = base_cfg["FS_TARGET"]
        n_frames = int(10 * fs)
        n_joints = len(mini_schema["joint_names"])

        time_s = _make_time(n_frames, fs)
        q_local = _make_static_quats(n_frames, n_joints)

        pos_m = np.zeros((n_frames, n_joints, 3))
        pos_m[:, 0, 1] = 0.95
        pos_m[:, 4, :] = np.nan   # Head fully occluded

        viz_idx = list(range(n_joints))
        ref = detect_static_reference(
            time_s, q_local, viz_idx, base_cfg,
            pos_m=pos_m, schema=mini_schema,
        )

        assert ref["t_pose_failed"] is True
        assert ref["gravity_guard_passed"] is False
        assert ref["ref_is_fallback"] is True

    def test_occluded_head_identity_qref(self, mini_schema, base_cfg):
        fs = base_cfg["FS_TARGET"]
        n_frames = int(10 * fs)
        n_joints = len(mini_schema["joint_names"])

        time_s = _make_time(n_frames, fs)
        q_local = _make_static_quats(n_frames, n_joints)

        pos_m = np.zeros((n_frames, n_joints, 3))
        pos_m[:, 0, 1] = 0.95
        pos_m[:, 4, :] = np.nan

        viz_idx = list(range(n_joints))
        ref = detect_static_reference(
            time_s, q_local, viz_idx, base_cfg,
            pos_m=pos_m, schema=mini_schema,
        )

        export_idx = list(range(n_joints))
        q_ref, qc = compute_q_ref_and_ref_qc(
            time_s, q_local, ref, export_idx, viz_idx, base_cfg,
        )

        identity = np.array([0.0, 0.0, 0.0, 1.0])
        for j in range(n_joints):
            np.testing.assert_array_equal(q_ref[j], identity)


# ---------------------------------------------------------------------------
# 4. Unit-scale warning — mm positions trigger the >50 m heuristic
# ---------------------------------------------------------------------------

class TestUnitScaleWarning:

    def test_mm_scale_logs_warning(self, mini_schema, base_cfg, caplog):
        """Positions in mm (pelvis ~950) should trigger the >50 m warning."""
        fs = base_cfg["FS_TARGET"]
        n_frames = int(10 * fs)
        n_joints = len(mini_schema["joint_names"])

        time_s = _make_time(n_frames, fs)
        q_local = _make_static_quats(n_frames, n_joints)

        pos_mm = np.zeros((n_frames, n_joints, 3))
        pos_mm[:, 0, 1] = 950.0   # pelvis in mm
        pos_mm[:, 4, 1] = 1600.0  # head in mm

        viz_idx = list(range(n_joints))
        with caplog.at_level(logging.WARNING, logger="src.reference"):
            detect_static_reference(
                time_s, q_local, viz_idx, base_cfg,
                pos_m=pos_mm, schema=mini_schema,
            )

        warning_msgs = [r.message for r in caplog.records
                        if r.levelno >= logging.WARNING]
        assert any("millimetres" in m or "millimeters" in m
                    for m in warning_msgs), (
            f"Expected unit-scale warning, got: {warning_msgs}"
        )


# ---------------------------------------------------------------------------
# 5. Backwards compatibility — no pos_m/schema → old behaviour
# ---------------------------------------------------------------------------

class TestBackwardsCompatibility:

    def test_no_pos_no_schema(self, base_cfg):
        """Calling without pos_m/schema must not crash and must omit gravity guard."""
        fs = base_cfg["FS_TARGET"]
        n_frames = int(10 * fs)
        n_joints = 5

        time_s = _make_time(n_frames, fs)
        q_local = _make_static_quats(n_frames, n_joints)

        viz_idx = list(range(n_joints))
        ref = detect_static_reference(time_s, q_local, viz_idx, base_cfg)

        assert ref["t_pose_failed"] is False
        assert ref["gravity_guard_passed"] is False
        assert "fallback_identity" not in ref["method"]
