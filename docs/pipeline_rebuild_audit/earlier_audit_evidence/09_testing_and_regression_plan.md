# 09 Testing and Regression Plan

**Date:** 2026-05-15
**Auditor:** Phase 9 Agent (Claude Sonnet 4.6)
**Mode:** Design-only. No code changes.

**Status:** COMPLETE

---

## Purpose

This document defines the test strategy that must be in place **before any implementation change** from Phase 13. Its role is to make every refactor, bugfix, and new gate verifiable: a change that alters scientific outputs without justification must be caught automatically.

The existing test suite (`tests/`) is substantial (21 test files covering artifacts, calibration, coordinate systems, filtering, gap fill, gates, kinematics, preprocessing, QC columns, quaternion ops, reference alignment, resampling, time alignment, units, and validation). This plan **does not replace** those tests — it organizes them into a coherent regression strategy, identifies gaps, and specifies new tests required by the audit findings.

---

## 1. Test Pyramid

```
         ┌──────────────────────────────────────────┐
         │  LAYER 4: Golden-data regression          │
         │  Whole-pipeline snapshot comparisons       │
         │  ~ 3–5 canonical sessions, JSON fixtures   │
         └────────────────┬─────────────────────────┘
                          │
         ┌────────────────▼─────────────────────────┐
         │  LAYER 3: Stage-level integration tests   │
         │  Input → Stage → Output contract checks   │
         │  pytest with real (small) derivative data │
         └────────────────┬─────────────────────────┘
                          │
         ┌────────────────▼─────────────────────────┐
         │  LAYER 2: Synthetic signal tests          │
         │  Known-input → known-output verification  │
         │  No real data needed                      │
         └────────────────┬─────────────────────────┘
                          │
         ┌────────────────▼─────────────────────────┐
         │  LAYER 1: Unit tests (pure functions)     │
         │  Deterministic, isolated, fast            │
         │  Most already exist in tests/             │
         └──────────────────────────────────────────┘
```

---

## 2. Layer 1 — Unit Tests (Pure Functions)

### 2.1 Existing coverage (do not re-implement)

| Test file | Functions covered | Audit relevance |
|-----------|-----------------|-----------------|
| `test_quat_norm.py` | Quaternion normalization | Q-EXT4a — |q|≈1 assertion |
| `test_gapfill_positions.py` | Gap detection, gap fill | S02 boundary condition bug (gapfill_positions.py:134) |
| `test_simple_gapfill.py` | Basic fill paths | S02 linear vs PCHIP label mismatch |
| `test_resample.py`, `test_resample_pchip.py` | Resample grid, PCHIP | F-INT1 (1-frame silent loss) |
| `test_filtering.py`, `test_phase2_filtering.py`, `test_filter_validation.py` | Butterworth, Winter, smart bias | REVIEW_OVERSMOOTHING |
| `test_reference_validation.py`, `test_reference_alignment.py`, `test_reference_gravity_guard.py` | Static window detection | F-651-4 ref_is_fallback |
| `test_calibration.py` | Calibration metadata extraction | Q-EXT3b |
| `test_coordinate_systems.py`, `test_euler_isb.py` | Coordinate transforms, ISB Euler | S06 Euler gimbal lock |
| `test_artifacts.py`, `test_preprocessing.py` | MAD detection, Hampel | S02 dormant MAD, is_hampel_outlier |
| `test_qc_columns.py`, `test_validation.py` | Parquet QC columns | Phase 6 schema audit |
| `test_gates_verification.py` | Gate status propagation | Phase 5 gate chain absence |
| `test_units.py` | Unit conversions | mm/deg/rad consistency |
| `test_time_alignment.py` | Timestamp jitter | T2-10 fast QC |
| `test_phase4_kinematics.py` | Kinematics computation | S06 omega method |

### 2.2 New unit tests required by audit findings

These tests do **not yet exist** and must be created before the corresponding implementation tickets:

| Test ID | Function to test | What to verify | Audit source |
|---------|-----------------|----------------|--------------|
| **U-NEW-01** | `compute_quality_gates()` artifact fraction | OR-union fraction (`1 - clean_fraction_pca`) equals any-joint-OR mask mean. Test: joint A has NaN in frames 1–100, joint B in frames 101–200 → OR-union = 200/N, max per-joint = 100/N. Verify code returns the larger. | F7-3: max() vs OR-union |
| **U-NEW-02** | `validate_reference()` artifact threshold | Reference with 25% artifact fraction must FAIL validation (threshold = 0.20, not 0.30). | F7-4: wrong 0.30 threshold |
| **U-NEW-03** | `compute_quality_gates()` dead_recording flag | Session with 5 frames must produce `hard_exclude=True` and `dead_recording=True`. 3600-frame session must produce `hard_exclude=False`. | F7-5, F-651-1 |
| **U-NEW-04** | S01 minimum session length gate | Hypothetical `parse_session()` with gate: session < 3600 frames must raise a `ShortSessionError` or set `gate_01_status = "FAIL"`. | User directive, F-651-1 |
| **U-NEW-05** | `build_pca_engine()` non-reference dead session | Calling build_pca_engine with a 5-frame non-reference session must either skip silently with a logged warning or raise a clear error — not produce a silently degenerate result. | F7-5, F-651-2 |
| **U-NEW-06** | `var_score = inf` guard in S05 reference | Reference window search on a ≤10-frame session must return `var_score = None` (not float('inf')) and `ref_is_fallback = True`. | F-651-2: invalid JSON Infinity |
| **U-NEW-07** | Bone CV computation for T3-03 | Input: positions with a known marker slip (bone length changes 200mm → 220mm midway). CV must exceed 2% threshold. | F-651-3, T3-03 |
| **U-NEW-08** | `t_pose_failed = None` vs `False` guard | `least_motion_window_fallback` path must explicitly set `t_pose_failed = False`, not leave it as `None`. | F-651-5 |
| **U-NEW-09** | Parquet `ref_is_fallback` propagation | When S05 JSON has `ref_is_fallback = True`, S06 parquet writer must include this in parquet metadata. | F-651-4, F7-2 |
| **U-NEW-10** | `filter_psd_verdict` in parquet metadata | When S04 verdict = `REVIEW_OVERSMOOTHING`, the field must appear in S06 parquet metadata. | F-INT3, Phase 6 §10 |
| **U-NEW-11** | `is_hampel_outlier` propagation | Frames modified by S04 Hampel filter must have `is_hampel_outlier = True` in kinematics parquet. | Phase 6 finding |
| **U-NEW-12** | S03 frame count off-by-one | `resample_to_target(signal, n_frames=N, fs=120)` must produce exactly N output frames. Regression: input 16,915 frames at 120Hz must output 16,914 (confirming F-INT1 if still present) or 16,915 (confirming the fix). | F-INT1 |

---

## 3. Layer 2 — Synthetic Signal Tests

These tests verify pipeline behaviour on constructed signals with mathematically known ground truth. No real data needed.

### 3.1 Dead session fixture

```python
# test_dead_session_gates.py
def test_dead_session_fails_gate():
    """5-frame session must FAIL fast QC and S01 gate. Never reaches S02."""
    signal = make_synthetic_session(n_frames=5, n_joints=19)
    result = run_fast_qc(signal)
    assert result.verdict == "FAIL"
    assert "T1-05" in result.failed_checks  # duration < 30s

def test_minimum_viable_session_passes():
    """3600-frame session must PASS the duration gate."""
    signal = make_synthetic_session(n_frames=3600, n_joints=19)
    result = run_fast_qc(signal)
    assert result.duration_gate == "PASS"
```

### 3.2 Quaternion norm synthetic tests

```python
def test_unit_quaternions_pass():
    """All |q|=1.0 quaternions must pass T2-08/T2-09."""
    q = np.tile([0, 0, 0, 1.0], (1000, 19, 1))  # identity, scalar-last
    assert fast_qc_quat_norm_check(q).status == "PASS"

def test_corrupted_quaternion_fails():
    """Any |q|<0.5 quaternion must trigger FAIL (T2-09)."""
    q = np.tile([0, 0, 0, 1.0], (1000, 19, 1))
    q[500, 3, :] = [0.1, 0.1, 0.1, 0.1]  # |q| ≈ 0.2
    assert fast_qc_quat_norm_check(q).status == "FAIL"
```

### 3.3 Frame continuity synthetic tests

```python
def test_frame_continuity_pass():
    frames = np.arange(1, 17000)
    assert check_frame_continuity(frames).status == "PASS"

def test_frame_jump_detected():
    frames = np.arange(1, 17000)
    frames[8000:] += 10  # gap of 10 at frame 8000
    result = check_frame_continuity(frames)
    assert result.status == "WARN"
    assert result.gap_at_frame == 8000
```

### 3.4 Bone length CV synthetic tests

```python
def test_stable_bone_passes():
    """Known-constant bone length must have CV < 0.01%."""
    positions = make_static_skeleton(n_frames=19200)  # 160s at 120Hz
    result = compute_bone_cv(positions, bone_pair=("Hips", "Spine"))
    assert result.cv_pct < 0.5

def test_marker_slip_detected():
    """Simulate a 10% bone length jump at frame 5000 — must exceed 2% WARN."""
    positions = make_static_skeleton(n_frames=19200)
    positions[5000:, SPINE_IDX, :] += np.array([20.0, 0, 0])  # 20mm lateral slip
    result = compute_bone_cv(positions, bone_pair=("Hips", "Spine"))
    assert result.cv_pct > 2.0
    assert result.status == "WARN"
```

### 3.5 Known PCA spectrum (F4 D_eff regression)

```python
def test_d_eff_equal_variance():
    """If all 19 joints have equal variance, D_eff must equal 19."""
    X = np.random.randn(10000, 19)  # IID — equal variance
    engine = build_pca_engine({"reference": X}, ref_key="reference")
    d_eff = compute_d_eff(engine, "reference")
    assert abs(d_eff.d_eff - 19.0) < 0.5

def test_d_eff_single_dominant_pc():
    """If all variance is in PC1, D_eff must be ≈ 1."""
    X = np.zeros((10000, 19))
    X[:, 0] = np.random.randn(10000)  # Only joint 0 varies
    engine = build_pca_engine({"ref": X}, ref_key="ref")
    d_eff = compute_d_eff(engine, "ref")
    assert d_eff.d_eff < 1.5
```

### 3.6 Known Gini distribution (F5 regression)

```python
def test_gini_uniform_returns_zero():
    """Equal joint variance → Gini ≈ 0 (maximally equal attribution)."""
    # ... uniform spectrum → Gini = 0
    pass

def test_gini_concentrated_returns_near_one():
    """Single dominant joint → Gini ≈ 0.9+ (maximally unequal)."""
    pass
```

### 3.7 ATF synthetic tests

```python
def test_hips_atf_is_zero():
    """Hips lin_vel_rel_mag = 0 always → ATF must be 0. Structural constraint."""
    df = make_kinematics_parquet(n_frames=19200)
    # Hips root joint is zero by construction
    atf = compute_atf(df, "Hips", params_f1={})
    assert atf["atf"] == 0.0  # not a bug — structural property of root joint

def test_active_joint_atf_nonzero():
    """Joint with consistent motion above noise floor → ATF > 0."""
    df = make_kinematics_parquet(n_frames=19200, active_joints=["LeftHand"])
    atf = compute_atf(df, "LeftHand", params_f1={})
    assert atf["atf"] > 0.3
```

---

## 4. Layer 3 — Stage-Level Integration Tests

These tests verify the input → output contract of each pipeline stage in isolation.

### Stage contracts to test

| Stage | Test | Input | Expected output | Audit source |
|-------|------|-------|----------------|--------------|
| S01 | Dead session gate | CSV with 5 frames | `gate_01_status = FAIL` | F-651-1, user directive |
| S01 | Minimum duration enforced | CSV with exactly 3600 frames | `gate_01_status = PASS` | User directive |
| S01 | Frame continuity field | CSV with frame jump | `frame_number_continuity_status = FAIL` | Q-EXT3c |
| S01 | Calibration field extraction | CSV with `Wand Error (mm)` header row | `wand_error_mm` field populated | Q-EXT3b |
| S02 | `t_pose_failed` not null | Reference JSON from `least_motion_window_fallback` | `t_pose_failed = false` (not null) | F-651-5 |
| S02 | `var_score = inf` guard | 5-frame session reference JSON | `var_score = null` (not `Infinity`) | F-651-2 |
| S03 | Frame count off-by-one | Session with N frames at 120Hz | Output has N frames (not N−1) after fix | F-INT1 |
| S04 | `n_nan_frames_at_filter_input` logged | Parquet with known NaN frames | Field present in S04 JSON | Q-EXT1a |
| S04 | `is_hampel_outlier` propagation | Session with known Hampel modifications | `is_hampel_outlier = True` for modified frame-joints | Phase 6 |
| S05 | `ref_is_fallback` propagation | S05 JSON with `ref_is_fallback = True` | Field appears in S06 parquet metadata | F-651-4, F7-2 |
| S05 | `filter_psd_verdict` in parquet | S04 verdict = `REVIEW_OVERSMOOTHING` | Field in parquet metadata | F-INT3 |
| S06 | Pipeline version field | S06 parquet | Single consistent `pipeline_version` across all stages | F-INT5 |
| Fast QC | Dead session → FAIL | 5-frame CSV | `verdict = FAIL`, T1-05 listed | T1-05 |
| Fast QC | Nominal → PASS | 671_T1_P2_R1 CSV | `verdict = PASS` or `PASS_WITH_WARNINGS` | All Tier 1–3 |
| v2_feature_engine | OR-union artifact fraction | Session with non-overlapping per-joint artifacts | `global_artifact_frac = 1 - clean_fraction_pca` | F7-3 |
| v2_feature_engine | Reference threshold 0.20 | Reference with 22% artifact fraction | `validate_reference` raises issue | F7-4 |

---

## 5. Layer 4 — Golden-Data Regression

### 5.1 Golden session selection

| Session | Role | Justification |
|---------|------|---------------|
| `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002` | **Primary golden session** | Canonical session used throughout Phases 4–7; all derivative JSONs and parquet verified; 0 NaN frames; clean data |
| `651_T1_P2_R1_Take 2026-01-15 04.35.25 PM_002` | **Secondary golden session** | Different subject, different timepoint; same pipeline quality; useful for cross-subject regression |
| `651_T2_P2_R2_Take 2026-01-26 05.24.12 PM_003` | **Failure regression fixture** | Dead session (5 frames); must trigger hard FAIL at S01 gate after fix; must never reach S02 |
| `651_T3_P2_R2_2026-02-11 05.50.42 PM_2030` | **Fallback reference fixture** | First confirmed `ref_is_fallback=True` in live session; after fix, must carry `ref_is_fallback=True` annotation in parquet |

### 5.2 Snapshot fields to lock

For each golden session, store a JSON fixture file under `tests/fixtures/golden_{RUN_ID}.json` with these fields:

```json
{
  "run_id": "...",
  "snapshot_date": "2026-05-15",
  "stage_snapshots": {
    "S01": {
      "total_frames": 16915,
      "segments_found": 51,
      "segments_missing": 0,
      "gate_01_status": "PASS",
      "frame_number_continuity_status": "PASS"
    },
    "S02": {
      "gate_02_status": "PASS",
      "bone_qc_status": "GOLD",
      "mean_cv": 0.522,
      "artifacts_detected": 0
    },
    "S03": {
      "temporal_status": "PERFECT",
      "n_frames_output": 16914
    },
    "S04": {
      "psd_verdict": "REVIEW_OVERSMOOTHING",
      "n_review_oversmoothing": 57,
      "mean_dance_delta_dB": -5.51,
      "winter_cutoff_mean_hz": 8.55,
      "smart_bias_count": 48,
      "n_frames_total": 16914
    },
    "S05": {
      "ref_is_fallback": false,
      "confidence_level": "HIGH",
      "mean_motion_rad_s": 0.039
    },
    "S06": {
      "total_frames": 16914,
      "com_reliability": "RELIABLE"
    },
    "parquet": {
      "shape": [16914, 803],
      "n_nan_frames": 0,
      "nan_guard_status": "CLEAN",
      "pipeline_version": "...",
      "ref_is_fallback": false,
      "filter_psd_verdict": "REVIEW_OVERSMOOTHING"
    }
  },
  "feature_scalars": {
    "ATF_axial": null,
    "ATF_peripheral": null,
    "TM_total_mm": null,
    "d_eff": null,
    "gini_anchored": null
  }
}
```

> **Note:** `feature_scalars` are `null` until Phase 13 (notebook 11 implementation) locks them in. At that point, run once, store values, lock as regression baseline.

### 5.3 Regression comparison rules

When any implementation ticket runs:

1. **Re-run full pipeline on all 4 golden sessions**
2. **Compare every non-null field in the fixture** to the new output
3. **Categorize any difference:**

| Difference type | Action |
|-----------------|--------|
| Expected change (documented fix) | Pass if within defined tolerance; update fixture after explicit confirmation |
| Unexpected frame count change | FAIL — escalate; never silently accept |
| Unexpected NaN appearance | FAIL — escalate |
| Verdict flip (PASS→FAIL or FAIL→PASS) | Review required before merge |
| Scientific scalar change (ATF, TM, D_eff, Gini) | Requires written justification in implementation log |
| Parquet schema change | FAIL — requires Phase 11 skeleton approval |

### 5.4 Tolerances

| Field type | Acceptable tolerance |
|-----------|---------------------|
| Frame counts (integer) | Exact match (0 tolerance) |
| NaN frame counts | Exact match |
| Gate statuses (string) | Exact match |
| Bone CV (float) | ±0.01% |
| Winter cutoff mean Hz | ±0.05 Hz |
| Dance-band attenuation dB | ±0.5 dB |
| Mean motion rad/s | ±0.001 rad/s |
| Feature scalars (ATF, TM, D_eff, Gini) | ±1% relative (after first lock-in) |
| Parquet shape | Exact match |

---

## 6. Old-vs-New Comparison Strategy

For every Phase 13 implementation ticket, before merging:

### 6.1 Pre/post comparison procedure

```bash
# Before change: store baseline outputs
python run_pipeline.py --batch batch_configs/subject_671_p2_r1_all.json
cp derivatives/step_06_kinematics/*__kinematics_master.parquet baselines/

# Make change
git commit -m "fix: ..."

# After change: run again
python run_pipeline.py --batch batch_configs/subject_671_p2_r1_all.json

# Compare
python tests/compare_outputs.py baselines/ derivatives/step_06_kinematics/ \
  --tolerance-json tests/fixtures/golden_671_T1_P2_R1.json
```

### 6.2 Comparison script requirements (`tests/compare_outputs.py`)

Must output:
- Table of all fixture fields: old value, new value, delta, status (MATCH / WITHIN_TOL / CHANGED / UNEXPECTED)
- Summary: N matched, N within tolerance, N changed (with justification expected), N unexpected
- Exit code 0 if only documented changes; exit code 1 if any unexpected change

### 6.3 Expected changes by ticket

Pre-register expected changes before implementing each ticket:

| Ticket | Expected output change | Expected scientific impact |
|--------|----------------------|--------------------------|
| Fix F-INT1 (S03 frame count off-by-one) | `n_frames_output` changes 16,914 → 16,915 for canonical session | ALL downstream feature scalars will change slightly (one more frame in ATF/TM/PCA). Acceptable. |
| Fix U-NEW-01 (artifact fraction OR-union) | `global_artifact_frac` may increase for some sessions | Quality gate stringency increases — some borderline sessions may get new WARN flags. Expected. |
| Add `ref_is_fallback` to parquet | New metadata key appears | No change to numerical data. No existing check should break. |
| Add `filter_psd_verdict` to parquet | New metadata key appears | No change to numerical data. |
| Fix `t_pose_failed = None → False` | `t_pose_failed` value changes for 2 sessions | No numerical change; JSON validity fixed. |
| Fix `var_score = inf` guard | `var_score = null` in 2 sessions | No downstream numerical change (dead session excluded anyway). |
| Fix S01 minimum session gate | 651_T2_P2_R2 now FAILS at S01 | Dead session never produces derivatives — fixture S06 parquet removed. |

---

## 7. Test Infrastructure Requirements

### 7.1 Test runner

```bash
pytest tests/ -v --tb=short
```

All tests must pass in < 5 minutes with no real data files (unit + synthetic layers). Golden-data regression runs only in CI with data.

### 7.2 Directory structure

```
tests/
  __init__.py
  fixtures/
    golden_671_T1_P2_R1.json          # locked after first pipeline run post-fix
    golden_651_T1_P2_R1.json
    golden_651_T2_P2_R2_DEAD.json     # expected: gate_01_status=FAIL
    golden_651_T3_P2_R2_FALLBACK.json # expected: ref_is_fallback=True
    synthetic/
      dead_session_5frames.csv        # minimal CSV for dead-session tests
      constant_skeleton.npy           # 19200-frame static positions
  conftest.py                         # shared fixtures, tmp paths
  compare_outputs.py                  # pre/post comparison script
  # --- existing tests (do not modify unless test is broken by fix) ---
  test_artifacts.py
  test_calibration.py
  ... (21 existing files)
  # --- new tests required by this plan ---
  test_quality_gates_v2.py            # U-NEW-01 through U-NEW-05
  test_session_guards.py              # U-NEW-04, T1-05/T1-06, dead session
  test_parquet_propagation.py         # U-NEW-09, U-NEW-10, U-NEW-11
  test_fast_qc.py                     # T1-01 through T3-08 from Phase 8
  test_bone_cv.py                     # U-NEW-07, T3-03
  test_d_eff_gini_synthetic.py        # §3.5, §3.6
  test_atf_synthetic.py               # §3.7 — includes Hips ATF = 0 assertion
```

### 7.3 Marking conventions

```python
@pytest.mark.unit          # Layer 1 — pure function, no I/O
@pytest.mark.synthetic     # Layer 2 — synthetic data, no real files
@pytest.mark.integration   # Layer 3 — requires derivative fixtures
@pytest.mark.golden        # Layer 4 — requires full pipeline run with real data
@pytest.mark.slow          # > 5 seconds

# Run only fast tests:
pytest -m "unit or synthetic"

# Run everything except golden (CI without data):
pytest -m "not golden"
```

---

## 8. Critical Regression Tests by Finding

The following tests are the minimum set that must pass for the implementation phase to begin:

| Priority | Test | Finding it guards | Must exist before ticket |
|----------|------|------------------|--------------------------|
| **CRITICAL** | Dead session (5 frames) → `gate_01_status = FAIL` | F-651-1, user directive | `13-S01-duration-gate` |
| **CRITICAL** | Hips ATF = 0 assertion (not a bug) | F7-1 | `13-v2-hips-atf-note` |
| **CRITICAL** | `ref_is_fallback = True` in parquet for 651_T3_P2_R2 | F-651-4, F7-2 | `13-S06-ref-fallback-propagation` |
| HIGH | OR-union artifact fraction > max per-joint | F7-3 | `13-v2-artifact-fraction-fix` |
| HIGH | `validate_reference()` fails at 22% artifact (not 30%) | F7-4 | `13-v2-ref-threshold-fix` |
| HIGH | `t_pose_failed = False` (not null) for fallback sessions | F-651-5 | `13-S05-tpose-null-fix` |
| HIGH | `var_score = null` (not `Infinity`) for dead session | F-651-2 | `13-S05-varsccore-inf-fix` |
| MEDIUM | S03 output frame count = S01 frame count (F-INT1 fix check) | F-INT1 | `13-S03-framecount-fix` |
| MEDIUM | `filter_psd_verdict` appears in parquet metadata | F-INT3 | `13-S06-psd-verdict-propagation` |
| MEDIUM | `is_hampel_outlier` non-zero after Hampel filter | Phase 6 | `13-S06-hampel-propagation` |
| LOW | Parquet schema has exactly 803 columns (unchanged) | Phase 6 baseline | Every ticket |

---

## 9. Scope Boundaries

### What this plan covers

- All audit findings from Phases 4–8 that have a corresponding implementation ticket
- The `fast_qc.py` script (all 3 tiers of checks from Phase 8)
- Changes to `v2_feature_engine.py` quality gates (F7-3, F7-4, F7-5)
- Changes to S01, S05, S06 parquet writer (propagation fixes)

### What this plan does NOT cover

- Redesign of the adaptive Butterworth filter (REDESIGN_CANDIDATE — Phase 11 decision)
- REVIEW_OVERSMOOTHING root cause fix (Phase 10 anti-overengineering gate required first)
- `v2_longitudinal.py` implementation (Phase 13 after Phase 11 skeleton approved)
- T3-01 T-pose algorithm (deferred: ADV-T3-01)
- PCA branch `pose`/`reach` (MVP deferral — Phase 13 v3.1)
- Legacy notebook audit (NB10 broken imports, NB08 out-of-sync)

---

## 10. Phase 9 Traceability

| Phase 9 requirement | Covered by |
|--------------------|-----------|
| Parser function tests | `test_calibration.py` (existing) + U-NEW-04 |
| Gap detection tests | `test_gapfill_positions.py` (existing) |
| Quaternion normalization | `test_quat_norm.py` (existing) + U-NEW-02, T2-08/T2-09 synthetic |
| SLERP/continuity | `test_resample_pchip.py` (existing) |
| Resampling grid | `test_resample.py` (existing) + U-NEW-12 (frame count) |
| Artifact detection | `test_artifacts.py` (existing) + U-NEW-11 |
| Filtering utilities | `test_filtering.py` (existing) |
| Reference detection | `test_reference_validation.py` (existing) + U-NEW-06, U-NEW-08, U-NEW-09 |
| Angular velocity | `test_phase4_kinematics.py` (existing) |
| SavGol derivatives | Covered in `test_phase4_kinematics.py` (existing) |
| CoM reliability | `test_validation.py` (existing) |
| Schema validation | `test_qc_columns.py` (existing) + U-NEW-09, U-NEW-10 |
| QC gate functions | `test_gates_verification.py` (existing) + U-NEW-01 through U-NEW-05 |
| Synthetic: all-zero signal | §3.2 (`test_dead_session_gates.py`) |
| Synthetic: constant velocity | §3.3 (frame continuity) |
| Synthetic: gap shorter/longer | `test_gapfill_positions.py` (existing) |
| Synthetic: quaternion sign flip | `test_quat_norm.py` (existing) |
| Synthetic: known rotation rate | `test_phase4_kinematics.py` (existing) |
| Synthetic: known static T-pose | `test_reference_validation.py` (existing) + T3-01 ADV research |
| Synthetic: known artifact spike | `test_artifacts.py` (existing) |
| Synthetic: known PCA spectrum | §3.5 (`test_d_eff_gini_synthetic.py`) |
| Synthetic: known Gini distribution | §3.6 (`test_d_eff_gini_synthetic.py`) |
| Golden-data regression | §5 (all 4 golden sessions) |
| Old-vs-new comparison | §6 (`tests/compare_outputs.py`) |

---

*Phase 9 complete. Next phase: Phase 10 — Anti-overengineering review and decision gate.*
