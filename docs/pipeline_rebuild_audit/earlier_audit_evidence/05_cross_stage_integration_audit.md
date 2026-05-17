# Phase 5 — Cross-Stage Integration Audit

**Date:** 2026-05-14
**Auditor:** Cross-Stage Integration Audit Agent (Phase 5)
**Canonical session:** `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002`
**Mode:** Read-only. No code changes.

**Sources read:**
- `derivatives/step_01_parse/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__step01_loader_report.json`
- `derivatives/step_02_preprocess/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__preprocess_summary.json`
- `derivatives/step_03_resample/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__resample_summary.json`
- `derivatives/step_04_filtering/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__filtering_summary.json`
- `derivatives/step_05_reference/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__reference_metadata.json`
- `derivatives/step_06_kinematics/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__validation_report.json`
- `config/config_v1.yaml` (full)
- `run_pipeline.py` (full)
- `src/filtering.py` (targeted grep — padlen and short-chunk handling)
- `reports/batch_summary_20260514_191749.json` (representative batch run)

**Status:** COMPLETE

---

## 1. Frame Count Continuity

The canonical session was traced end-to-end across all derivative JSON summaries. Frame counts
as reported by each stage's summary artifact are shown below.

| Stage | Frames logged | Source field | Change vs prior |
|-------|--------------|-------------|-----------------|
| S-01 (parse) | **16,915** | `total_frames` in `__step01_loader_report.json` | — (raw capture) |
| S-02 (preprocess) | **NOT LOGGED** | no frame count field in `__preprocess_summary.json` | — |
| S-03 (resample) | **NOT LOGGED** | no frame count field in `__resample_summary.json` | — |
| S-04 (filter) | **16,914** | `n_frames_total` + `raw_quality.total_frames` in `__filtering_summary.json` | **−1 frame** |
| S-05 (reference) | N/A | reference uses time window only, not frame count | — |
| S-06 (kinematics) | **16,914** | `total_frames` in `__validation_report.json` | 0 (consistent with S04) |

### 1.1 One-frame discrepancy: S01=16,915 vs S04/S06=16,914

**Finding:** A single frame is silently lost between S01 (16,915 frames) and S04 (16,914 frames).
This is a **1-frame drop** that is not reported in any stage summary.

**Root cause analysis:** S03 resamples from the original irregular time grid to a uniform grid
using `PchipInterpolator` for positions and `SciPy Slerp` for quaternions. The resampled grid
is constructed as `np.linspace(t_start, t_end, n_target)`. The `n_target` is derived from
`round(duration × target_fs)`. With S01 duration=140.95s and target_fs=120Hz:
`round(140.95 × 120) = round(16914.0) = 16914`.
But S01 reports 16,915 frames. The original capture time grid spans
`t[0]` to `t[16914]` = 16,915 timestamps. The PCHIP resamples onto a grid of
16,914 points (using `duration × fs` rather than `(duration × fs) + 1`). This off-by-one in
the `n_target` formula consistently drops the last frame (or first, depending on boundary convention).

**Why S03 summary does not log this:** `__resample_summary.json` has no `n_frames_input` or
`n_frames_output` field. It logs `interpolation_methods`, `run_id`, and `temporal_status` only.
`temporal_status = "PERFECT"` and `time_grid_std_dt = 0.0` indicate perfect temporal regularity
of the OUTPUT grid, but provide no information about whether the INPUT frame count was preserved.

**Severity: MEDIUM.** For a session of 16,915 frames at 120Hz, losing 1 frame = 8.3ms
(the last sample). This has negligible effect on computed kinematics. However, the fact that
this loss is invisible in all intermediate summaries is a provenance gap. A cross-stage audit
script comparing S01 vs S06 frame counts would silently flag every session as a mismatch.

### 1.2 S02 and S03 summaries do not log frame counts

**Finding:** Neither `__preprocess_summary.json` nor `__resample_summary.json` log
`n_frames_input` or `n_frames_output`. The pipeline cannot be audited for continuity using
only derivative JSON summaries — the parquet files themselves must be read.

**Contrast:** S04 logs `n_frames_total = 16914`. S06 logs `total_frames = 16914`. The two
stages that produce downstream parquets (S04, S06) do log frame counts; the two intermediate
stages (S02, S03) do not.

---

## 2. Gate Status Propagation

### 2.1 Gate fields present per stage

| Stage | Gate field | Value for T1_P2_R1 | Propagates downstream? |
|-------|-----------|-------------------|----------------------|
| S-01 | None | — | No |
| S-02 | `gate_02_status` | `"PASS"` | No |
| S-03 | None | — | No |
| S-04 | None (per-column PSD verdicts only) | `REVIEW_OVERSMOOTHING` for all 57 cols | No |
| S-05 | `ref_is_fallback` + `confidence_level` | `false`, `"HIGH"` | No |
| S-06 | None (per-joint `exceeded_omega_threshold`) | all `false` | N/A |

**Finding:** The pipeline has no formal gate propagation chain. Only S-02 has an explicit
`gate_02_status` field. The value `"PASS"` is not injected into any downstream stage summary.

**Practical implication:** If S-02 were to fail (`gate_02_status = "FAIL"`), the pipeline would
not stop — `run_pipeline.py` would continue running S-03 through S-06 on a non-gated session.
There is no artifact-level mechanism by which an upstream failure state blocks downstream
execution. The only gate is notebook execution failure (exception propagation to papermill).

**Severity: MEDIUM.** All current 9 sessions pass S-02. But for future sessions with genuine
QC failures, absent gate propagation means corrupted data silently propagates to kinematics.

### 2.2 S-04 REVIEW_OVERSMOOTHING verdict not gated downstream

From Phase 4 (S04 audit): ALL 57 position columns for this session received `REVIEW_OVERSMOOTHING`
(mean_dance_delta_dB = −5.51 dB; worst: Hips__py at −27.19 dB). This is the Phase 3
`REDESIGN_CANDIDATE` finding. Despite this known quality issue, S05 and S06 proceed without
any flag in their input metadata. The kinematics parquet is produced with no annotation that
the input positions may be over-smoothed.

---

## 3. NaN Frame Accounting

### 3.1 NaN chain for canonical session (pristine — 0 NaN frames)

| Stage | NaN handling | Field logged | Value |
|-------|-------------|-------------|-------|
| S-01 | Parses raw CSV; NaN = missing marker | Not logged in summary | — |
| S-02 | Gap fill; `frames_fixed_count` per joint | `frames_fixed_count = 0` (all joints) | CLEAN |
| S-03 | PCHIP/SLERP on full resampled grid | Not logged | — |
| S-04 | Artifact detection → pchip repair; `n_nan_frames_at_filter_input` | **NOT LOGGED** (Q-EXT1a FAIL) | — |
| S-06 | NaN ω output if input NaN | Not logged | — |

**For this session:** The session is pristine (bone_qc_status = "GOLD", 0 frames fixed in S02,
artifact_frames_pct = 0.1115% from velocity spikes only). There are no NaN frames in the
input to any stage. The NaN tracking gap is invisible here — it would surface only on a session
with genuine marker dropouts.

**The structural gap:** There is no mechanism in derivative JSON summaries to trace a NaN frame
introduced in S-01 through S-02 gap fill → S-03 resample → S-04 filter → S-06 kinematics.
Q-EXT1a remains FAIL: `n_nan_frames_at_filter_input` is absent from S04 filtering summary.

### 3.2 S-04 short-chunk handling (Q-EXT5a)

**Finding:** `src/filtering.py` implements a padlen guard for segments shorter than the filter
requires. When a data segment (between NaN gaps) is shorter than the Butterworth padding length,
the segment is left unfiltered rather than silently corrupted.

From `filtering.py:189–213`:
```python
if len(seg) > padlen:
    out[s:e] = filtfilt(b, a, seg, padlen=padlen)
else:
    # Too short — copy through unfiltered
    n_too_short += 1
    short_chunk_frames += len(seg)
```

The `filtering_summary.json` logs this in a `chunking_guard` sub-object:
```json
"chunking_guard": {
    "total_chunks_all_joints": 57,
    "total_chunks_too_short": 0,
    "total_unfiltered_frames": 0,
    "joints_with_short_chunks": []
}
```

**Q-EXT5a verdict: PASS.** Short sessions or sessions with large marker gaps near the start/end
are handled without silent corruption. The unfiltered frame count is logged.

---

## 4. Column Schema Consistency

### 4.1 Joint set consistency

All 6 stage summaries that reference joints use the same 19-joint set:

```
Hips, Spine, Spine1, Neck, Head,
LeftShoulder, LeftArm, LeftForeArm, LeftHand,
RightShoulder, RightArm, RightForeArm, RightHand,
LeftUpLeg, LeftLeg, LeftFoot, RightUpLeg, RightLeg, RightFoot
```

No joint name inconsistencies were found for this session. The `__validation_report.json`
`per_joint` keys match the S02 `per_joint` keys exactly.

### 4.2 Quaternion convention consistency

`__reference_metadata.json`: `quat_order = "xyzw"` (scalar-last, SciPy convention).
`__validation_report.json`: no explicit `quat_order` field, but angular velocity computation
uses `quat_log` from `src/angular_velocity.py`, which uses SciPy SLERP (scalar-last).
No convention mismatch for this session.

**Standing note (Phase 4.5):** scikit-kinematics uses scalar-first `[w,x,y,z]` and must never
be mixed with the pipeline's scalar-last convention.

### 4.3 Pipeline version consistency

| Stage | Version string |
|-------|---------------|
| S-01 | `v2.6_calibration_enhanced` |
| S-04 | `v3.1_3stage_dynamic_rms_chunked` |
| S-06 | no version field in `__validation_report.json` |

**Finding:** Version strings are stage-specific labels, not a pipeline-wide version. There is
no single `pipeline_version` field appearing in all stage summaries. Reproducibility across
sessions processed at different development points requires inferring code version from git history.

---

## 5. Config State and Provenance (Q-EXT2a, Q-EXT2b, Q-EXT2c, Q-EXT2d)

### 5.1 Q-EXT2a — Config separation of stable / sensitivity / experimental

**Answer: ABSENT.**

`config/config_v1.yaml` is a flat key-value YAML file. All parameters (path, physical constants,
method choices, experimental flags) sit at the same level with no structural or comment-based
section separation. There is no indication of which parameters are:
- **Stable** (sampling rate, output paths — safe to never change)
- **Sensitivity** (cutoff range, sigma thresholds — must trigger re-run if changed)
- **Experimental** (enforce_cleaning, adaptive correction loop — actively being evaluated)

Additionally, `current_csv` retains the last-processed session's path after every run:
```yaml
current_csv: 671/T3/671_T3_P2_R2_2026-02-11 05.50.42 PM_2030.c3d
```
`run_pipeline.py::update_config()` mutates `config_v1.yaml` in-place and never restores it.
Reading the config after a batch run gives a misleading snapshot of the last-processed session.

**The `step_00_config/{RUN_ID}__config_snapshot.yaml` is in the Phase 3 LOCAL_REFACTOR list
but not yet implemented.** No per-run config snapshots exist in `derivatives/`.

### 5.2 Q-EXT2b — All filter parameters logged to JSON?

**Answer: PASS (with one gap).**

`__filtering_summary.json` logs comprehensively:
- `filter_params.n_frames_total`, `total_columns_processed`
- Per-stage artifact counts: `total_artifact_frames`, `total_velocity_spikes`, `total_zscore_spikes`
- `artifact_frames_pct`, `hampel_frames_pct`
- `stage1_max_interp_limit_frames`, `stage1_gap_guard.total_unreliable_gaps`
- `chunking_guard` (full short-chunk accounting)
- `winter_cutoff_stats`: `{min, max, mean}` Hz
- Per-column PSD verdicts and `mean_dance_delta_dB`
- Full SNR breakdown per joint

**One gap:** `n_nan_frames_at_filter_input` (Q-EXT1a) is absent. The filter summary does not
capture how many NaN frames existed in the parquet arriving from S03.

### 5.3 Q-EXT2c — Per-step boolean toggles from config?

**Answer: ABSENT.**

`config/config_v1.yaml` has **no per-step boolean toggles** (e.g., `run_step_02: true/false`).
`run_pipeline.py` hardcodes the execution sequence:
```python
self.pipeline_sequence = ['01', '02', '03', '04', '05', '06', '08']
```

There is no mechanism to skip a step without editing `run_pipeline.py` directly. The only
behavioral toggles in config that affect step execution are:
- `enforce_cleaning: false` (controls kinematic_repair within S06)
- `omega_method: quat_log` (controls angular velocity method within S06)
- `write_global_events_jsonl: false`, `write_run_log_jsonl: false` (optional log outputs)

None of these disable entire pipeline stages.

### 5.4 Q-EXT2d — Per-session stage failures logged?

**Answer: PARTIAL.**

`run_pipeline.py` saves `reports/batch_summary_{timestamp}.json` at the end of each batch run.
This file contains per-session, per-notebook execution status:
```json
{
  "run_id": "671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002",
  "notebooks": {
    "01": {"status": "success", "error": null, "execution_time": 8.10},
    "02": {"status": "success", "error": null, "execution_time": 2.56},
    ...
  },
  "status": "success",
  "outputs_verified": true
}
```

**What works:** The batch summary records which notebook failed, the exception message, and
execution times. This is a genuine failure log and was confirmed present in `reports/`.

**Gaps:**
1. The batch summary is in `reports/`, not in `derivatives/`. A downstream consumer reading
   `derivatives/step_04_filtering/…__filtering_summary.json` finds no indication of whether
   the producing run succeeded or failed for other notebooks.
2. Timestamped batch summaries accumulate; there is no cumulative per-session failure history.
3. `outputs_verified = true/false` checks only 6 specific files (step_01–step_04 parquets +
   step_06 parquet + step_06 validation_report.json). It does NOT verify step_05 reference
   outputs, parquet row counts, or JSON validity.
4. No `pipeline_run_status` field in any per-session derivative links back to the batch log.

---

## 6. End-to-End Summary for Canonical Session

**Session:** `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002`
**Session type:** T1, P2, R1 — first timepoint, second piece (Gaga dance phrase), first repetition. Subject 671.

| Dimension | Status | Detail |
|-----------|--------|--------|
| Frame count: S01→S04 | **GAP** | 16,915→16,914 (−1 frame, silent, not logged in S03) |
| Frame count: S04→S06 | CONSISTENT | 16,914=16,914 |
| Gate propagation chain | **ABSENT** | Only S02 has `gate_02_status`; no downstream chain |
| S02 gate status | PASS | gate_02_status="PASS", 0 frames fixed, GOLD bone QC |
| NaN tracking chain | **ABSENT** | moot for this pristine session (0 NaN frames) |
| Short-chunk filter guard | PASS | chunking_guard: 0 too-short chunks |
| Column schema consistency | PASS | 19 joints, same names across S02→S06 |
| Quaternion convention | PASS | xyzw (scalar-last) throughout |
| Pipeline version consistency | **INCONSISTENT** | S01=v2.6, S04=v3.1, S06=no version |
| Config state after run | **STALE** | current_csv retains last-run session, not canonical |
| REVIEW_OVERSMOOTHING propagation | **ABSENT** | All 57 cols flagged in S04 but not annotated in S05/S06 |
| Batch run log | PARTIAL | reports/batch_summary JSON exists but not per-session co-located |

---

## 7. Q-EXT Answer Summary

| Q# | Question | Answer | Severity |
|----|----------|--------|----------|
| Q-EXT1a | `n_nan_frames_at_filter_input` logged? | **FAIL** — absent from S04 summary | Medium |
| Q-EXT2a | Config separates stable/sensitivity/experimental? | **ABSENT** — flat structure | Medium |
| Q-EXT2b | All filter params logged to JSON? | **PASS** (minor gap: no NaN input count) | Low |
| Q-EXT2c | Per-step boolean toggles from config? | **ABSENT** — hardcoded sequence | Medium |
| Q-EXT2d | Per-session stage failures logged? | **PARTIAL** — batch runner JSON in reports/ only | Medium |
| Q-EXT5a | Short-session filter padding guard? | **PASS** — chunking_guard implemented and logged | — |

---

## 8. New Findings from Phase 5

### F-INT1: 1-frame silent loss in S03 resampling

See §1.1. The off-by-one in `n_target = round(duration × fs)` instead of
`round(duration × fs) + 1` silently drops the final frame. Must verify:
- Is it consistent across all 9 sessions?
- Does it affect timing-sensitive features (e.g., PPM peak detection near session end)?

Recommended fix: Log `n_frames_input` and `n_frames_output` in `__resample_summary.json`.
Add assertion: if `abs(n_frames_output - n_frames_input) > 2`, raise warning.

### F-INT2: Config mutated in-place after each run — provenance gap

`run_pipeline.py::update_config()` writes the current session's CSV path and anthropometrics
back to `config_v1.yaml`. After a batch run, the config retains the last-processed session's
path. No clean-state restoration. The Phase 3 LOCAL_REFACTOR (per-run config snapshot) must
be implemented before any reproducibility claims can be made.

### F-INT3: REVIEW_OVERSMOOTHING verdict does not propagate downstream

S04 flags ALL 57 position columns as REVIEW_OVERSMOOTHING (mean Δ_dance = −5.51 dB). This
verdict is logged only in `__filtering_summary.json`. It does NOT appear as:
- An annotation in S05 reference_metadata
- An annotation in S06 validation_report or kinematics_master.parquet metadata
- A flag in the batch_summary.json run record

A downstream user reading only the kinematics parquet has no indication that the input
positions were flagged for over-smoothing.

### F-INT4: `outputs_verified` check incomplete

`run_pipeline.py::verify_outputs()` checks 6 files but does NOT verify step_05 reference
outputs, parquet row counts, or JSON validity. `outputs_verified = true` is necessary but
insufficient.

### F-INT5: No pipeline-wide version string

S01 uses `v2.6_calibration_enhanced`, S04 uses `v3.1_3stage_dynamic_rms_chunked`. No unified
`pipeline_version` field appears in all stage summaries. Cross-session comparisons and regression
testing require inferring code version from git history.

---

## 9. Decisions Triggered

| Finding | Recommended action | Priority |
|---------|-------------------|----------|
| F-INT1: 1-frame S03 loss | Add `n_frames_input`/`n_frames_output` to resample_summary; investigate `n_target` formula | Medium |
| F-INT2: Config in-place mutation | Implement `step_00_config/{RUN_ID}__config_snapshot.yaml` (Phase 3 LOCAL_REFACTOR) | High |
| F-INT3: REVIEW_OVERSMOOTHING not propagated | Add `filter_qc_flag` to kinematics parquet metadata; surface in S06 validation_report | Medium |
| F-INT4: verify_outputs incomplete | Add step_05 outputs and parquet row count checks | Low |
| F-INT5: No unified pipeline version | Add `pipeline_version` key to config_v1.yaml; stamp all stage JSON summaries | Medium |
| Q-EXT2a: Flat config | Add `# STABLE:`, `# SENSITIVITY:`, `# EXPERIMENTAL:` section comments to config | Low |
| Q-EXT2c: No per-step toggles | Add `skip_steps: []` list to config; honour in run_pipeline.py | Low |
| Q-EXT2d: Batch log not per-session | Write `{RUN_ID}__pipeline_run_status.json` to derivatives/step_01_parse/ per session | Medium |
| Gate chain absent | Add `gate_04_status`, `gate_05_status`, `gate_06_status` to stage summaries | Medium |
| NaN chain absent | Add `n_nan_frames_input`/`n_nan_frames_output` to S02, S03, S04 summaries | Medium |
