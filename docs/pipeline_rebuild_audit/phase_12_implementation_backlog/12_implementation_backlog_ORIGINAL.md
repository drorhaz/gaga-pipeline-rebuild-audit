# Phase 12 — Implementation Backlog

**Status:** COMPLETE (planning only)
**Date:** 2026-05-17
**Supersedes:** Phase 3 draft skeleton, Phase 11 ticket list
**Incorporates:** Phase 11 final target skeleton, Phase 11.5 required corrections R1–R6

---

## Anti-Overengineering Commitments

Before any ticket: the following constraints apply to ALL 15 tickets.

1. **Do not refactor working algorithms.** Every algorithm in the KEEP_AS_IS list (25 items) is touched ONLY if a specific audit finding requires a fix. Do not improve, rename, or reorganize working code.
2. **Do not add abstraction layers.** No new base classes, no new factory patterns, no new plugin systems. Add functions only when a ticket explicitly requires a new function.
3. **Do not touch forensic subsystem.** `forensic_report.py`, `forensic_plots.py`, `interpolation_logger.py`, `interpolation_tracking.py`, `gate_integration.py`, `burst_classification.py`, `_run_forensic_batch.py`, `forensic_config.py` — ZERO changes unless a ticket explicitly targets one of these files.
4. **Do not reorganize the repository.** No folder moves, no file renames, no `__init__.py` restructuring beyond what tickets require.
5. **Minimal v1 scope is final.** 15 tickets. No ticket additions without a new audit phase.
6. **Every ticket ends with a regression check** against the frozen golden parquet before proceeding to the next ticket.

---

## Step 02 Interpolation Policy Decision

**Decision date:** 2026-05-17
**Status:** RESOLVED — linear retained as default; PCHIP is `candidate_pending_tests`

### Current method
`src/preprocessing.py` uses `np.interp` (linear) for gap-filling in Step 02 (S02).

### Decision

| Option | Decision | Rationale |
|--------|----------|-----------|
| Linear interpolation (`np.interp`) | **RETAIN AS DEFAULT** | Adequate for short artifact segments; consistent with current validated outputs; no regressions introduced |
| PCHIP interpolation | `candidate_pending_tests` | Monotone cubic; better for longer segments; not activated until 3 specific synthetic tests pass |
| SLERP (quaternion spherical linear) | `future_v2` | Quaternion-specific; not needed for position data; deferred to v2 |

### Activation criteria for PCHIP (NOT Minimal v1)

PCHIP activation requires ALL of the following before it may be enabled:
1. **Trigger metric available:** `max_artifact_segment_frames_positions` per joint must be logged (added in Ticket 009)
2. **Trigger condition:** `max_artifact_segment_frames_positions > 10` frames for any joint in any session
3. **Three synthetic tests must pass:**
   - Test A: Short segment (≤5 frames) — PCHIP and linear must produce < 0.1 mm mean difference
   - Test B: Long segment (>10 frames) — PCHIP must outperform linear by > 1.0 mm mean absolute error against ground truth
   - Test C: Edge-of-segment continuity — PCHIP must show no velocity discontinuity at segment boundaries (C1 continuity check)
4. **No regressions** in golden parquet comparison after substitution

### Ticket responsibility
- Ticket 009 adds the required logging (`max_artifact_segment_frames_positions`, `mean_artifact_segment_frames_positions`, `n_interpolated_frames_per_joint`).
- PCHIP activation is NOT Ticket 009 scope. It is a separate future decision, gated by the 3 tests above.

### What this means for implementation
- Do NOT add PCHIP code in Ticket 009 or any Minimal v1 ticket.
- Do NOT add a PCHIP flag or config option in Ticket 001.
- The logging added in Ticket 009 is the ONLY action on interpolation in Minimal v1.

---

## Backlog Overview

**Total tickets:** 15 (Minimal v1)
**Ordering:** strict — each ticket must pass regression check before next begins

| Ticket | Title | Priority | Size | Prerequisites | Blast Radius |
|--------|-------|----------|------|---------------|--------------|
| 001 | Per-run config snapshot | P0 | XS | none | LOCAL |
| 002 | S01 hard FAIL gate | P0 | S | 001 | LOCAL |
| 003 | S03 frame count fix | P0 | M | 001, 002 | PARQUET_REGEN |
| 004 | ref_is_fallback + session labels | P0 | M | 003 | PARQUET_REGEN |
| 005 | var_score + t_pose_failed guards | P0 | XS | 002 | LOCAL |
| 006 | hard_exclude in feature engine | P0 | S | 002, 005 | LOCAL |
| 007 | Parquet metadata + quat diagnostics + Hampel summary | P1 | S | none | PARQUET_REGEN |
| — | **TIER 1 CHECKPOINT** | — | — | 001–007 | — |
| 008 | Artifact fraction + reference threshold | P1 | S | 006 | PARQUET_REGEN |
| 009 | S02 labels + enhanced logging | P1 | XS | none | LOCAL |
| 010 | Hips ATF_axial exclusion + spec amendment | P1 | M | 008 | PARQUET_REGEN |
| — | **TIER 2 CHECKPOINT** | — | — | 008–010 | — |
| 011 | is_hampel_outlier propagation | P1 | M | pre-investigation | PARQUET_REGEN |
| 012 | Fast QC script | P2 | L | none | LOCAL |
| 013 | NB08 session count sync | P3 | S | none | LOCAL |
| 014 | QC sidecar outputs (S06-post aggregation) | P3 | M | 007, 008 | LOCAL |
| — | **TIER 3 CHECKPOINT + PRE-015 GATE** | — | — | 011–014 | — |
| 015 | S04 adaptive dance-band correction loop | P1 | XL | ALL 001–014 | MAXIMUM |

**Priority key:** P0=safety/reproducibility, P1=pipeline reliability, P2=fast QC/scale, P3=important not blocking, P4=deferred, DO_NOT_DO=rejected

---

## Ticket Specifications

---

### Ticket 001 — Per-Run Config Snapshot

| Field | Value |
|-------|-------|
| **ID** | 001 |
| **Title** | Per-run config snapshot |
| **Priority** | P0 |
| **Size** | XS |
| **Prerequisites** | none |
| **Blast radius** | LOCAL (no parquet changes) |

**Source audit refs:**
- Phase 5 cross-stage audit: "no config snapshot → cannot reproduce any run"
- Phase 11 skeleton §8 (stage contracts): config_snapshot.json required
- Phase 11.5: no correction required for this ticket

**Rationale:**
Every pipeline run currently produces results with no record of which config values were active. Reproducibility requires a per-run frozen config copy. This is the smallest-blast-radius foundational ticket and must be first.

**Files to change:**
- `src/pipeline.py` — add `save_config_snapshot(config, run_output_dir)` call at pipeline entry
- `config/config_v1.yaml` — no changes; this file is the source
- Optionally `src/utils.py` — add `save_config_snapshot()` function if not already present

**Scope:**
- Write a copy of the active config dict (post-load, post-merge) to `{run_output_dir}/config_snapshot_{timestamp}.json`
- Include: pipeline version string, timestamp, all config keys and values
- Do NOT add new config keys in this ticket
- Do NOT add PCHIP, dance-band threshold, or any new config option

**Non-goals:**
- Config schema validation (deferred)
- Config diff between runs (deferred)
- Centralized config registry (rejected)

**Expected behavior after ticket:**
- Every pipeline run produces `config_snapshot_{timestamp}.json` in the run output directory
- File is valid JSON, human-readable
- File includes at minimum: `pipeline_version`, `run_timestamp`, all keys from `config_v1.yaml`

**Tests required:**
- Unit: `test_001_config_snapshot.py` — run pipeline on one golden session; assert `config_snapshot_*.json` exists; assert it is valid JSON; assert it contains `pipeline_version` and `run_timestamp`
- Regression: golden parquet unchanged after ticket (no parquet columns added or removed)

**Regression comparison:**
- Load golden parquet before ticket; load after ticket; assert column list identical; assert row count identical; assert all numeric columns equal within 1e-9

**Rollback plan:**
- Remove the `save_config_snapshot()` call from `src/pipeline.py`; delete `src/utils.py` additions (or restore previous version)
- Rollback does not affect any parquet

**Stop condition:**
- `config_snapshot_*.json` exists for every run; regression check passes; test passes; PR approved

---

### Ticket 002 — S01 Hard FAIL Gate

| Field | Value |
|-------|-------|
| **ID** | 002 |
| **Title** | S01 hard FAIL gate |
| **Priority** | P0 |
| **Size** | S |
| **Prerequisites** | 001 |
| **Blast radius** | LOCAL (raises exception; no parquet schema change) |

**Source audit refs:**
- Phase 4 S01 audit: "S01 currently warns and continues on malformed input"
- Phase 5 cross-stage audit: "corrupt input propagates silently through all stages"
- Phase 10 decision: gate chain confirmed S01-only (UD-003)
- Phase 11 skeleton §4 (S01 stage skeleton): hard FAIL at S01

**Rationale:**
`parse_optitrack_csv()` (defined in `src/preprocessing.py`, called from `src/pipeline.py` line 197) currently emits warnings and continues when column counts, frame counts, or marker labels are invalid. This allows corrupt data to silently propagate. A hard FAIL at S01 prevents downstream contamination.

**Files to change:**
- `src/preprocessing.py` — add explicit validation block in `parse_optitrack_csv()` before returning; raise `ValueError` with structured message on: missing required columns, frame count < minimum threshold (from config), unexpected marker label count
- `src/pipeline.py` — wrap S01 call in try/except; catch `ValueError`; log structured FAIL message; halt session (do not continue to S02)

**Scope:**
- FAIL conditions: missing required marker columns; frame count below `config.min_frames_threshold`; marker label mismatch > `config.max_label_mismatch_fraction`
- FAIL must produce a structured error dict written to `{run_output_dir}/s01_fail_report.json`
- Do NOT add FAIL gates to S02–S06 in this ticket
- Do NOT change the parsing algorithm; only add the validation check

**Non-goals:**
- S02–S06 FAIL gates (deferred, not in Minimal v1)
- Automatic retry or fallback on FAIL (rejected)
- GUI/dashboard FAIL display (not in scope)

**Expected behavior after ticket:**
- Session with corrupt/malformed CSV: pipeline halts at S01; writes `s01_fail_report.json`; logs `FAIL` at ERROR level; no parquet produced
- Session with valid CSV: behavior unchanged; pipeline continues normally

**Tests required:**
- Unit: `test_002_s01_fail_gate.py` — inject malformed CSV (missing columns, wrong frame count); assert `ValueError` raised; assert `s01_fail_report.json` written; assert no parquet produced
- Integration: valid session passes S01 and produces identical parquet to golden

**Regression comparison:**
- Valid session: golden parquet unchanged (column list, row count, values identical within 1e-9)
- Confirm no new columns added to parquet

**Rollback plan:**
- Revert `src/preprocessing.py` validation block
- Revert `src/pipeline.py` try/except wrapper
- No parquet changes to revert

**Stop condition:**
- Malformed CSV triggers FAIL + `s01_fail_report.json`; valid CSV produces identical golden parquet; regression check passes; PR approved

---

### Ticket 003 — S03 Frame Count Fix

| Field | Value |
|-------|-------|
| **ID** | 003 |
| **Title** | S03 frame count fix |
| **Priority** | P0 |
| **Size** | M |
| **Prerequisites** | 001, 002 |
| **Blast radius** | PARQUET_REGEN (row count may change; all downstream must be regenerated) |

**Source audit refs:**
- Phase 4 S03 audit: "resampled frame count can diverge from expected by ±1 frame"
- Phase 5 cross-stage integration audit: "frame count chain inconsistency across S01→S03→S06"
- Phase 11 skeleton §4 (S03 stage skeleton): frame count must be deterministic

**Rationale:**
S03 resampling produces a frame count that can differ from the expected value by ±1 due to floating-point edge effects in the resampling grid. This causes downstream inconsistencies in alignment and feature extraction. Fix must be deterministic: same input always produces same output frame count.

**Files to change:**
- `src/preprocessing.py` (or wherever S03 resampling lives — verify by grep before implementing)
- Identify the resampling function; add explicit frame count enforcement using `np.linspace` with integer endpoint
- After resampling, assert `len(output_frames) == expected_n_frames`; raise `ValueError` if mismatch

**Scope:**
- Fix the resampling grid to be fully deterministic
- Add post-resample assertion
- Regenerate ALL golden parquets after fix (full parquet regen protocol — see below)
- Update frozen golden parquet checksums after regen

**Parquet regen protocol (required for this ticket and any PARQUET_REGEN ticket):**
1. Freeze current parquet checksums BEFORE implementing fix
2. Implement fix
3. Run pipeline on ALL sessions in `data/` directory
4. Compute new checksums
5. Record before/after diff in ticket implementation log
6. Update `tests/golden_checksums.json` (or equivalent) with new checksums
7. Confirm regression test passes against NEW golden parquets

**Non-goals:**
- Changing the resampling algorithm (only fix frame count edge case)
- Changing the target sample rate (config value; not modified here)
- PCHIP resampling (rejected for Minimal v1)

**Expected behavior after ticket:**
- Same C3D input always produces identical frame count in S03 output
- No ±1 frame variation across runs
- All downstream stages receive consistent frame count

**Tests required:**
- Unit: `test_003_frame_count_determinism.py` — run S03 on 3 sessions with known frame counts; assert output frame count matches expected exactly; run twice; assert identical
- Regression: all sessions produce parquets with same row counts as new golden; no numeric drift beyond 1e-9

**Regression comparison:**
- Before/after diff must be documented in implementation log
- Expected: row count changes by 0 or ±1 for affected sessions; values change only in affected sessions
- If any session changes by > 1 row: STOP and investigate before proceeding

**Rollback plan:**
- Revert `src/preprocessing.py` resampling fix
- Restore previous golden parquet checksums
- Requires full parquet regen on rollback

**Stop condition:**
- All sessions produce deterministic frame counts; regression test passes against new golden parquets; implementation log records before/after diff; PR approved

---

### Ticket 004 — ref_is_fallback + Session Labels

| Field | Value |
|-------|-------|
| **ID** | 004 |
| **Title** | ref_is_fallback + session labels |
| **Priority** | P0 |
| **Size** | M |
| **Prerequisites** | 003 |
| **Blast radius** | PARQUET_REGEN (new columns added) |
| **BLOCKED ON** | UD-006: session label naming convention must be resolved before implementation |

**Source audit refs:**
- Phase 4 S05 audit: "no flag when fallback reference is used"
- Phase 6 master parquet ML readiness: "session label column required for ML grouping"
- Phase 11 skeleton §7 (parquet schema v2.0): `ref_is_fallback` + session label columns
- Phase 11.5 R2: `fallback_path_used` required in session_qc_report.json (handled by Ticket 014, not here)

**Rationale:**
ML models trained on this data need to know which sessions used a fallback reference pose (lower quality) vs. the true reference. Without `ref_is_fallback`, contamination is silent. Session label columns (`subject_id`, `session_id`, `phase_id`, `rep_id`) are required for cross-session grouped analysis.

**Files to change:**
- `src/pipeline.py` or `src/reference.py` — propagate `ref_is_fallback` boolean from S05 output into parquet metadata and per-row column
- `src/feature_engine.py` (or wherever parquet columns are written) — add session label columns
- Parquet schema updated: add `ref_is_fallback` (bool), `subject_id` (str), `session_id` (str), `phase_id` (str), `rep_id` (str) per schema v2.0

**UD-006 naming decision (REQUIRED before implementation):**
The session label columns must follow a consistent naming convention. Two options:

| Option | subject_id value | session_id value |
|--------|-----------------|-----------------|
| Abbreviated | `651` | `T1` |
| Expanded | `Subject_651` | `Session_T1` |

**User must confirm UD-006 before Ticket 004 begins.** Implementation is blocked until this is resolved.

**Scope:**
- Add `ref_is_fallback` as both a PyArrow metadata field AND a per-row boolean column
- Add 4 session label columns (naming per UD-006 decision)
- Do NOT change the reference algorithm (S05 KEEP_AS_IS)

**Non-goals:**
- Changing the fallback reference logic (KEEP_AS_IS)
- Adding additional metadata beyond what schema v2.0 specifies
- `fallback_path_used` in session_qc_report.json (Ticket 014)

**Expected behavior after ticket:**
- All parquets contain `ref_is_fallback` column: `True` for sessions that used fallback, `False` otherwise
- All parquets contain 4 session label columns with consistent naming
- ML groupby operations on session label columns work without extra parsing

**Tests required:**
- Unit: `test_004_session_labels.py` — load output parquet; assert all 5 new columns present; assert `ref_is_fallback` dtype is bool; assert session label columns are strings; assert no null values
- Regression: all previously-valid numeric columns unchanged within 1e-9

**Regression comparison:**
- New columns added (expected); existing columns unchanged; row count unchanged

**Rollback plan:**
- Remove new columns from parquet write path
- Requires full parquet regen on rollback

**Stop condition:**
- UD-006 resolved; all parquets contain correct new columns; regression check passes; PR approved

---

### Ticket 005 — var_score + t_pose_failed Guards

| Field | Value |
|-------|-------|
| **ID** | 005 |
| **Title** | var_score + t_pose_failed guards |
| **Priority** | P0 |
| **Size** | XS |
| **Prerequisites** | 002 |
| **Blast radius** | LOCAL (no parquet changes) |

**Source audit refs:**
- Phase 4 S05 audit: "var_score accessed without None check"
- Phase 5 cross-stage: "t_pose_failed not propagated when T-pose detection fails"
- Phase 11 skeleton §4 (S05 stage skeleton): explicit guards required

**Rationale:**
`var_score` and `t_pose_failed` can be `None` in edge cases (T-pose detection failure). Downstream code accesses these without None checks, causing AttributeError or silent NaN propagation. Guards must be explicit, not silent.

**Files to change:**
- `src/reference.py` (or wherever T-pose detection runs) — add explicit None check for `var_score` before use; set `t_pose_failed = True` when `var_score is None`
- Propagate `t_pose_failed` flag to S05 output dict

**Scope:**
- Add `if var_score is None: t_pose_failed = True; log WARNING` pattern
- Do NOT change the T-pose detection algorithm (KEEP_AS_IS)
- Do NOT add new fallback logic; just guard + flag

**Non-goals:**
- Changing T-pose detection (KEEP_AS_IS)
- Adding new fallback reference logic (deferred)

**Expected behavior after ticket:**
- When T-pose detection fails: `t_pose_failed = True` in S05 output; WARNING logged; `var_score` handled safely (not accessed as None)
- When T-pose detection succeeds: behavior identical to current

**Tests required:**
- Unit: `test_005_tpose_guards.py` — mock T-pose detection to return None; assert `t_pose_failed = True`; assert no AttributeError; assert WARNING logged
- Regression: golden parquet unchanged (no parquet changes in this ticket)

**Regression comparison:**
- Parquet unchanged (no parquet changes expected)

**Rollback plan:**
- Revert None checks in `src/reference.py`; no parquet changes

**Stop condition:**
- T-pose failure handled gracefully; regression passes; PR approved

---

### Ticket 006 — hard_exclude in Feature Engine

| Field | Value |
|-------|-------|
| **ID** | 006 |
| **Title** | hard_exclude in feature engine |
| **Priority** | P0 |
| **Size** | S |
| **Prerequisites** | 002, 005 |
| **Blast radius** | LOCAL (no parquet changes if hard_exclude list unchanged) |

**Source audit refs:**
- Phase 4 S06/S11 audit: "hard_exclude markers not enforced in feature engine"
- Phase 10 decision matrix: KEEP hard_exclude logic; fix propagation
- Phase 11 skeleton §4 (S11 stage skeleton): hard_exclude must be applied before any feature computation

**Rationale:**
The `hard_exclude` marker list in config is not currently enforced in the feature engine. Markers on the exclude list may contribute to features they should not. This is a correctness fix, not an algorithm change.

**Files to change:**
- `src/feature_engine.py` (or equivalent) — add `hard_exclude` filter at feature computation entry point; skip excluded markers before any loop over joints/markers

**Scope:**
- Read `hard_exclude` list from config
- Skip excluded markers at the TOP of the feature computation loop (before any computation)
- Add log entry: `Excluding {n} markers from feature computation per hard_exclude config`
- Do NOT change which features are computed; only which markers contribute

**Non-goals:**
- Changing feature definitions (KEEP_AS_IS)
- Adding new exclusion logic beyond `hard_exclude` list

**Expected behavior after ticket:**
- Excluded markers contribute to zero features
- Feature values for non-excluded markers: unchanged if they were not receiving contamination from excluded markers
- If excluded markers WERE contributing: feature values may change (document in implementation log)

**Tests required:**
- Unit: `test_006_hard_exclude.py` — set `hard_exclude = ["LFoot"]`; run feature engine; assert no LFoot-dependent features in output; assert other markers unaffected
- Regression: if no markers were previously leaking through, parquet values unchanged

**Regression comparison:**
- If feature values change: document which features changed and by how much; this is expected if exclusion was previously broken

**Rollback plan:**
- Remove hard_exclude filter from feature engine entry point

**Stop condition:**
- hard_exclude enforced; tests pass; implementation log documents any value changes; PR approved

---

### Ticket 007 — Parquet Metadata + Quaternion Diagnostics + Hampel Summary

| Field | Value |
|-------|-------|
| **ID** | 007 |
| **Title** | Parquet metadata + quaternion diagnostics + Hampel summary |
| **Priority** | P1 |
| **Size** | S |
| **Prerequisites** | none (can run in parallel with 001–006 if needed, but run after for clean baseline) |
| **Blast radius** | PARQUET_REGEN (new metadata fields and columns) |

**Source audit refs:**
- Phase 6 master parquet ML readiness: "PyArrow metadata fields missing"
- Phase 11 skeleton §7 (parquet schema v2.0): 5 metadata fields required
- Phase 11.5 R1: `hampel_modification_fraction_per_joint` required in filtering_summary.json
- Phase 11.5 R3: S06 graceful handling of missing JSON

**Rationale:**
ML/DL workflows require parquet metadata (pipeline version, schema version, session identifiers, processing timestamp) to be embedded in the file, not inferred from filename. Quaternion diagnostics enable rotation plausibility checks without re-running the pipeline. Hampel outlier summary enables per-joint QC without recomputing.

**Files to change:**
- `src/pipeline.py` or `src/feature_engine.py` — add 5 PyArrow metadata fields at parquet write time: `pipeline_version`, `schema_version`, `session_id`, `processing_timestamp`, `config_hash`
- `src/kinematics.py` or `src/preprocessing.py` — add quaternion diagnostic computation (5 fields per Phase 11 skeleton §9): `quat_norm_mean`, `quat_norm_std`, `quat_norm_min`, `quat_norm_max`, `quat_norm_gt5pct_warning`
- `src/filtering.py` — add `hampel_modification_fraction_per_joint` to filtering_summary.json output (Phase 11.5 R1)
- Add S06 graceful error handling: if filtering_summary.json is missing, log WARNING and continue (not FAIL); populate with `null` values (Phase 11.5 R3)

**Scope:**
- PyArrow metadata: embedded in parquet file footer, not per-row columns
- Quaternion diagnostics: written to `{run_output_dir}/quat_diagnostics.json` AND as per-row columns in parquet
- Hampel summary: added to existing `filtering_summary.json` structure
- S06 JSON missing: graceful WARNING + null fill (not FAIL)

**Non-goals:**
- Changing quaternion computation algorithm (KEEP_AS_IS: `quat_log` method)
- Adding new quaternion methods (deferred)
- Renaming `finite_difference_5point()` (deferred, not Minimal v1)

**Expected behavior after ticket:**
- All parquets contain 5 PyArrow metadata fields
- All runs produce `quat_diagnostics.json`
- `filtering_summary.json` contains `hampel_modification_fraction_per_joint` dict
- Sessions where `quat_norm_gt5pct_warning = True` are flagged in QC output

**Tests required:**
- Unit: `test_007_parquet_metadata.py` — load parquet with PyArrow; assert all 5 metadata keys present; assert non-empty values
- Unit: `test_007_quat_diagnostics.py` — run kinematics on golden session; assert `quat_diagnostics.json` exists; assert all 5 fields present; assert `quat_norm_mean` ≈ 1.0 within 0.01
- Unit: `test_007_hampel_summary.py` — run filtering on golden session; assert `hampel_modification_fraction_per_joint` present in `filtering_summary.json`
- Unit: `test_007_missing_json_graceful.py` — delete `filtering_summary.json`; run S06; assert WARNING logged; assert no exception; assert null values in output

**Regression comparison:**
- Existing numeric columns unchanged; new metadata + diagnostic columns added (expected); row count unchanged

**Rollback plan:**
- Remove PyArrow metadata fields from parquet write
- Remove `quat_diagnostics.json` write
- Remove `hampel_modification_fraction_per_joint` from filtering_summary.json
- Requires parquet regen on rollback

**Stop condition:**
- All 4 unit tests pass; regression check passes; PR approved

---

## TIER 1 CHECKPOINT

**After tickets 001–007 are complete and regression-checked:**

| Check | Required result |
|-------|----------------|
| Config snapshot exists for every run | PASS |
| S01 FAIL gate works on malformed input | PASS |
| S03 frame count is deterministic | PASS |
| Session label columns in parquet | PASS (UD-006 resolved) |
| t_pose_failed guard active | PASS |
| hard_exclude enforced | PASS |
| PyArrow metadata in parquet | PASS |
| Quaternion diagnostics logged | PASS |
| Hampel summary in filtering_summary.json | PASS |
| Golden parquet regression: all Tier 1 tickets | PASS |

**Gate:** Do NOT begin Ticket 008 until all Tier 1 checks pass.

---

### Ticket 008 — Artifact Fraction + Reference Threshold

| Field | Value |
|-------|-------|
| **ID** | 008 |
| **Title** | Artifact fraction + reference threshold |
| **Priority** | P1 |
| **Size** | S |
| **Prerequisites** | 006 |
| **Blast radius** | PARQUET_REGEN (new columns) |

**Source audit refs:**
- Phase 4 S04 filtering audit: "artifact fraction not logged per-joint"
- Phase 4 S05 reference audit: "reference quality threshold not enforced"
- Phase 11 skeleton §4 (S04 and S05 skeletons): artifact fraction + reference threshold required

**Rationale:**
Without per-joint artifact fraction, QC cannot identify which joints are most affected by artifacts. Without a reference quality threshold, poor-quality reference poses are used silently. Both are required before Ticket 010 (ATF_axial exclusion depends on artifact fraction).

**Files to change:**
- `src/filtering.py` — compute and log `artifact_fraction_per_joint` dict (fraction of frames flagged as artifact per joint); add to filtering_summary.json
- `src/reference.py` — enforce `min_reference_quality_threshold` from config; if reference quality below threshold: set `ref_is_fallback = True` (for Ticket 004 propagation)

**Scope:**
- `artifact_fraction_per_joint`: fraction of frames where Hampel flag = True, per joint
- Reference threshold: read from `config.min_reference_quality_threshold`; compare to `var_score`
- Do NOT change artifact detection algorithm (KEEP_AS_IS)
- Do NOT change reference algorithm (KEEP_AS_IS)

**Non-goals:**
- Changing Hampel filter parameters (KEEP_AS_IS)
- Changing reference computation (KEEP_AS_IS)
- Changing fallback reference logic (KEEP_AS_IS)

**Expected behavior after ticket:**
- `filtering_summary.json` contains `artifact_fraction_per_joint` for every session
- Sessions where reference quality < threshold: `ref_is_fallback = True`
- Sessions where reference quality ≥ threshold: behavior unchanged

**Tests required:**
- Unit: `test_008_artifact_fraction.py` — run filtering on golden session; assert `artifact_fraction_per_joint` dict present; assert all joints have values in [0, 1]
- Unit: `test_008_reference_threshold.py` — mock low-quality T-pose (var_score below threshold); assert `ref_is_fallback = True`; assert WARNING logged

**Regression comparison:**
- New fields in filtering_summary.json (expected); existing parquet columns unchanged; row count unchanged

**Rollback plan:**
- Remove `artifact_fraction_per_joint` from filtering_summary.json
- Remove reference threshold check from `src/reference.py`

**Stop condition:**
- Artifact fraction logged per-joint; reference threshold enforced; tests pass; regression passes; PR approved

---

### Ticket 009 — S02 Labels + Enhanced Logging

| Field | Value |
|-------|-------|
| **ID** | 009 |
| **Title** | S02 labels + enhanced logging |
| **Priority** | P1 |
| **Size** | XS |
| **Prerequisites** | none |
| **Blast radius** | LOCAL (no parquet schema changes; log/sidecar additions only) |

**Source audit refs:**
- Phase 4 S02 preprocessing audit: "label mismatch warnings not structured"
- Phase 11.5: interpolation logging required before PCHIP decision can be made
- Phase 12 interpolation policy decision: `max_artifact_segment_frames_positions` must be logged

**Rationale:**
S02 currently logs label mismatches as unstructured warnings. Enhanced logging enables systematic QC and is a prerequisite for the PCHIP activation decision (not Minimal v1, but logging must exist first). The interpolation segment statistics are required by the Step 02 interpolation policy decision above.

**Files to change:**
- `src/preprocessing.py` — in Step 02 (gap-filling / interpolation):
  - Add structured log entry for label mismatches: `{"stage": "S02", "type": "label_mismatch", "expected": [...], "found": [...], "n_missing": N}`
  - Compute and log per-joint interpolation statistics:
    - `n_interpolated_frames_per_joint`: dict of joint → count of interpolated frames
    - `max_artifact_segment_frames_positions`: dict of joint → length of longest contiguous artifact segment (in frames)
    - `mean_artifact_segment_frames_positions`: dict of joint → mean artifact segment length
  - Write these to `{run_output_dir}/s02_interpolation_stats.json`

**Scope:**
- Logging only; do NOT change the interpolation algorithm
- Do NOT add PCHIP code
- Do NOT add a PCHIP config flag
- Stats are written to JSON sidecar (not parquet columns) to preserve parquet as ML-clean

**Non-goals:**
- Switching to PCHIP (candidate_pending_tests — NOT Minimal v1)
- Adding interpolation to parquet columns (deferred)
- SLERP for quaternion interpolation (future_v2)

**Expected behavior after ticket:**
- Every run produces `s02_interpolation_stats.json` with all 3 stat fields
- Label mismatch logs are structured JSON-like entries (parseable by QC tooling)
- No change to interpolation results or parquet values

**Tests required:**
- Unit: `test_009_s02_logging.py` — run S02 on golden session; assert `s02_interpolation_stats.json` exists; assert all 3 fields present; assert `n_interpolated_frames_per_joint` sum > 0 for sessions with gaps
- Regression: parquet unchanged (no parquet changes)

**Regression comparison:**
- Parquet unchanged; new JSON sidecar added (expected)

**Rollback plan:**
- Remove structured logging additions from `src/preprocessing.py`
- Delete `s02_interpolation_stats.json` output

**Stop condition:**
- `s02_interpolation_stats.json` produced for every run; tests pass; regression passes; PR approved

---

### Ticket 010 — Hips ATF_axial Exclusion + Spec Amendment

| Field | Value |
|-------|-------|
| **ID** | 010 |
| **Title** | Hips excluded from ATF_axial + spec amendment |
| **Priority** | P1 |
| **Size** | M |
| **Prerequisites** | 008 |
| **Blast radius** | PARQUET_REGEN (feature values change for ATF_axial) |

**Source audit refs:**
- Phase 4 S06 kinematics audit: "Hips marker included in ATF_axial calculation; biomechanically invalid"
- Phase 7 downstream methodology compatibility: "ATF_axial contamination from Hips affects all derived axial metrics"
- Phase 11 skeleton §4 (S06 skeleton): Hips excluded from ATF_axial

**Rationale:**
The Hips marker is a pelvis-level reference point, not a peripheral limb endpoint. Including it in ATF_axial (axial transfer function) is biomechanically invalid. All sessions must be regenerated after this fix. A spec amendment is required to formally document the exclusion.

**Files to change:**
- `src/kinematics.py` or `src/feature_engine.py` — in ATF_axial computation: exclude Hips marker from the joint list before computing axial energy transfer
- `METHODOLOGY_SPEC.md` or equivalent spec document — add amendment: "Hips excluded from ATF_axial computation effective Ticket 010"
- Full parquet regen required

**Scope:**
- Exclude Hips from ATF_axial loop (single-line change in most implementations)
- Add spec amendment document entry
- Do NOT change ATF_axial algorithm otherwise (KEEP_AS_IS for the computation itself)
- Do NOT change ATF_peripheral or any other metric

**Non-goals:**
- Excluding other markers from other metrics
- Changing the ATF_axial algorithm beyond the exclusion
- Changing the spec document structure

**Expected behavior after ticket:**
- ATF_axial values change for all sessions (Hips excluded)
- ATF_peripheral values: unchanged
- All other features: unchanged
- Spec document records the amendment

**Tests required:**
- Unit: `test_010_hips_exclusion.py` — run ATF_axial computation with and without Hips; assert values differ; assert Hips contribution is zero in new output
- Regression: ATF_axial columns change (expected, document magnitude); all other columns unchanged within 1e-9

**Regression comparison:**
- ATF_axial change: expected and documented
- All other features: must be unchanged within 1e-9

**Rollback plan:**
- Restore Hips to ATF_axial joint list
- Revert spec amendment (add note: "rolled back")
- Requires full parquet regen on rollback

**Stop condition:**
- Hips excluded from ATF_axial; ATF_axial values change by expected amount; all other features unchanged; spec amendment written; regression documented; PR approved

---

## TIER 2 CHECKPOINT

**After tickets 008–010 are complete and regression-checked:**

| Check | Required result |
|-------|----------------|
| Artifact fraction logged per-joint | PASS |
| Reference threshold enforced | PASS |
| S02 interpolation stats logged | PASS |
| Hips excluded from ATF_axial | PASS |
| ATF_axial value change documented | PASS |
| All other features unchanged | PASS |
| Golden parquet regression: Tier 2 tickets | PASS |

**Gate:** Do NOT begin Ticket 011 until Tier 2 checks pass. Also: resolve UD-006 before Ticket 004 if not yet done.

---

### Ticket 011 — is_hampel_outlier Propagation

| Field | Value |
|-------|-------|
| **ID** | 011 |
| **Title** | is_hampel_outlier propagation |
| **Priority** | P1 |
| **Size** | M |
| **Prerequisites** | Pre-investigation required (see below) |
| **Blast radius** | PARQUET_REGEN (new per-row boolean columns) |

**Source audit refs:**
- Phase 4 S04 filtering audit: "is_hampel_outlier flag not propagated to parquet"
- Phase 6 master parquet ML readiness: "outlier mask required for ML training quality control"
- Phase 11 skeleton §7 (schema v2.0): `is_hampel_outlier_{joint}` per-row columns

**Rationale:**
The Hampel filter identifies outlier frames during filtering (S04). This flag is computed but not written to the parquet. ML models trained without access to the outlier mask may train on contaminated frames. Per-row propagation enables downstream masking.

**Pre-investigation required (before implementing):**
Before writing any code:
1. Grep for `hampel_outlier` or `is_outlier` in `src/filtering.py` — confirm where the flag is currently stored
2. Confirm the flag is per-frame and per-joint (not just a summary statistic)
3. Confirm the column count: one boolean column per joint marker (e.g., `is_hampel_outlier_LWrist`)
4. Check if `hampel_modification_fraction_per_joint` (added in Ticket 007) uses the same underlying flag or a separate computation
5. Document findings in implementation log BEFORE making any changes

**Files to change (tentative — verify in pre-investigation):**
- `src/filtering.py` — collect `is_outlier` per-frame per-joint array after Hampel computation; pass to output dict
- `src/pipeline.py` or `src/feature_engine.py` — write `is_hampel_outlier_{joint}` boolean columns to parquet

**Scope:**
- Per-row, per-joint boolean columns: `is_hampel_outlier_{joint}` for each joint in marker set
- Do NOT change Hampel filter algorithm (KEEP_AS_IS)
- Do NOT change filter parameters

**Non-goals:**
- Changing Hampel filter (KEEP_AS_IS)
- Using outlier flag to automatically exclude frames (deferred)
- Adding outlier fraction columns (that's Ticket 007/008)

**Expected behavior after ticket:**
- All parquets contain `is_hampel_outlier_{joint}` columns (one per joint)
- Frames flagged by Hampel: True; non-flagged: False; no NaN
- ML workflows can filter training data using these columns

**Tests required:**
- Unit: `test_011_hampel_propagation.py` — run S04 on session with known Hampel flags; load output parquet; assert `is_hampel_outlier_*` columns present for all joints; assert dtype is bool; assert no NaN
- Regression: all non-outlier-flag columns unchanged within 1e-9

**Regression comparison:**
- New columns added (expected); existing columns unchanged

**Rollback plan:**
- Remove `is_hampel_outlier_{joint}` columns from parquet write path
- Requires full parquet regen on rollback

**Stop condition:**
- Pre-investigation complete and documented; is_hampel_outlier propagated; tests pass; regression passes; PR approved

---

### Ticket 012 — Fast QC Script

| Field | Value |
|-------|-------|
| **ID** | 012 |
| **Title** | Fast QC script |
| **Priority** | P2 |
| **Size** | L |
| **Prerequisites** | none (but benefits from Ticket 007 outputs) |
| **Blast radius** | LOCAL (new script; no changes to existing pipeline) |

**Source audit refs:**
- Phase 8 fast post-collection QC requirements: full Fast QC spec
- Phase 11 skeleton §3 (Fast QC stage): T3-01 through T3-10 checks
- Phase 11.5: T3-07 (early reference QC) confirmed appropriate for Fast QC; no pipeline stage split needed

**Rationale:**
Currently there is no fast check at data collection time. A researcher must run the full pipeline to detect missing markers, bad T-poses, or corrupt files. Fast QC runs in < 60 seconds on a laptop and catches the most common collection errors before the researcher leaves the lab.

**Files to change (create new file):**
- `src/fast_qc.py` (new file) — implement 10 checks:
  - T3-01: File exists and is readable (INFO only — NEVER raise FAIL)
  - T3-02: Expected marker count present
  - T3-03: Frame count within expected range
  - T3-04: No all-zero marker trajectories
  - T3-05: T-pose frame identifiable
  - T3-06: T-pose var_score above minimum threshold
  - T3-07: Early reference plausibility (reference pose gross check without full S04)
  - T3-08: Sampling rate matches expected
  - T3-09: No excessive NaN fraction in any joint trajectory
  - T3-10: File timestamp plausible (not future-dated, not >6 months old)
- `run_fast_qc.py` (new script at project root) — CLI entry point: `python run_fast_qc.py --session {session_path}`

**Scope:**
- Fast QC is read-only: it reads C3D/CSV files and prints/writes a report; it does NOT modify any data
- Output: `fast_qc_report.json` in a specified output directory
- T3-01 MUST be INFO-only: a readable file is not a FAIL condition
- All FAIL conditions must write a structured `fast_qc_report.json` even on FAIL (so the report is always present)
- Runtime target: < 60 seconds per session on a modern laptop

**Non-goals:**
- Running the full pipeline (Fast QC is independent)
- Replacing NB08 (Fast QC is pre-pipeline; NB08 is post-pipeline)
- Modifying data based on QC results (read-only)

**Expected behavior after ticket:**
- `python run_fast_qc.py --session data/651/T1/...` produces `fast_qc_report.json` in < 60 seconds
- Report contains pass/warn/fail status for each of 10 checks
- At least one synthetic FAIL session triggers FAIL status correctly

**Tests required:**
- Unit: `test_012_fast_qc_checks.py` — 10 sub-tests, one per check; inject synthetic FAIL conditions; assert correct status for each
- Integration: run Fast QC on all golden sessions; assert all pass T3-01 through T3-04 (basic validity); assert runtime < 60 seconds

**Regression comparison:**
- No pipeline changes; no parquet changes; regression check is runtime check only

**Rollback plan:**
- Delete `src/fast_qc.py` and `run_fast_qc.py`
- No pipeline or parquet impact

**Stop condition:**
- All 10 checks implemented and tested; runtime < 60 seconds on golden sessions; PR approved

---

### Ticket 013 — NB08 Session Count Sync

| Field | Value |
|-------|-------|
| **ID** | 013 |
| **Title** | NB08 session count sync |
| **Priority** | P3 |
| **Size** | S |
| **Prerequisites** | none |
| **Blast radius** | LOCAL (notebook changes only; no pipeline or parquet changes) |

**Source audit refs:**
- Phase 4 S08 audit: "NB08 session count hardcoded; does not reflect actual processed sessions"
- Phase 11 skeleton §6 (notebook strategy): NB08 must auto-detect session count
- Phase 11.5: confirmed NB08 is forensic-free (0 forensic imports in grep); Ticket 013 not blocked by forensic dependency

**Rationale:**
NB08 currently uses a hardcoded session count for summary statistics. When sessions are added or removed, the hardcoded count produces misleading denominators in group statistics. Auto-detection from the parquet directory eliminates this.

**Files to change:**
- `notebooks/NB08_*.ipynb` (identify exact filename by glob before implementing) — replace hardcoded `N_SESSIONS = ...` with dynamic count derived from parquet directory listing; add assertion that dynamic count matches expected count from `data/subject_metadata.json`

**Scope:**
- Replace hardcoded count with `len([f for f in parquet_dir.glob("*.parquet") if f.is_file()])`
- Add assertion: `assert n_sessions_found == n_sessions_expected` where expected comes from metadata
- Do NOT change any analysis cells; only the session count derivation

**Non-goals:**
- Changing NB08 analysis logic (KEEP_AS_IS)
- Adding new visualizations to NB08
- Touching any forensic notebooks

**Expected behavior after ticket:**
- NB08 runs without modification when sessions are added or removed
- Session count assertion passes for current dataset
- Fails loudly (assertion error) if parquet count ≠ metadata count

**Tests required:**
- Manual run: execute NB08 end-to-end; assert no errors; assert session count matches metadata
- Regression: all NB08 output cells unchanged in value (session count was wrong before; new count may differ if previous count was wrong — document)

**Regression comparison:**
- If previous hardcoded count was wrong: output changes (expected and documented)
- All computation cells using session count: must be verified manually

**Rollback plan:**
- Restore hardcoded `N_SESSIONS = ...` value in NB08

**Stop condition:**
- NB08 runs end-to-end; session count auto-detected correctly; PR approved

---

### Ticket 014 — QC Sidecar Outputs (S06-post QC Aggregation)

| Field | Value |
|-------|-------|
| **ID** | 014 |
| **Title** | QC sidecar outputs (S06-post QC Aggregation) |
| **Priority** | P3 |
| **Size** | M |
| **Prerequisites** | 007, 008 |
| **Blast radius** | LOCAL (new JSON/CSV outputs; no parquet changes) |

**Source audit refs:**
- Phase 11 skeleton §8 (post-pipeline QC sidecar): `session_qc_report.json` required
- Phase 11.5 R2: `fallback_path_used` required in `session_qc_report.json`
- Phase 11.5 R4: Ticket 014 is "S06-post QC Aggregation" — NOT a pipeline stage
- Phase 11.5 R5: Ticket 014 must be batch-callable

**Rationale:**
Sidecar QC outputs aggregate per-session quality metrics into a structured report, enabling cross-session QC without re-running the pipeline. The sidecar is NOT a pipeline stage — it is a post-pipeline aggregation step. It must be callable independently in batch mode.

**Files to change:**
- `src/qc_aggregator.py` (new file) — aggregate quality metrics from existing pipeline outputs into `session_qc_report.json`
- `run_qc_sidecar.py` (new script at project root) — CLI: `python run_qc_sidecar.py --session-dir {dir}` and `python run_qc_sidecar.py --batch-dir {dir}`
- `session_qc_report.json` schema (document in implementation log)

**`session_qc_report.json` required fields (per Phase 11.5 R2):**
- `session_id`
- `subject_id`
- `pipeline_version`
- `processing_timestamp`
- `ref_is_fallback` (bool)
- `fallback_path_used` (str or null) — REQUIRED per Phase 11.5 R2
- `t_pose_failed` (bool)
- `var_score` (float or null)
- `artifact_fraction_per_joint` (dict)
- `hampel_modification_fraction_per_joint` (dict)
- `quat_norm_gt5pct_warning` (bool)
- `s01_fail` (bool)
- `fast_qc_pass` (bool or null — null if Fast QC not run)
- `overall_qc_status`: "PASS" | "WARN" | "FAIL"

**Batch mode requirement (Phase 11.5 R5):**
- `--batch-dir` argument processes all sessions in a directory tree
- Produces `batch_qc_summary.csv` with one row per session
- Produces `batch_qc_report.json` with all session reports aggregated

**Scope:**
- Read from existing pipeline output files (parquet metadata, filtering_summary.json, quat_diagnostics.json, s01_fail_report.json)
- Do NOT re-run any pipeline stages
- Do NOT modify any existing pipeline code
- Read-only aggregation

**Non-goals:**
- Real-time pipeline integration (sidecar runs post-pipeline)
- Dashboard or visualization (Ticket 012 / NB08)
- Changing any pipeline stage

**Expected behavior after ticket:**
- `python run_qc_sidecar.py --session-dir {dir}` produces `session_qc_report.json` for that session
- `python run_qc_sidecar.py --batch-dir {dir}` produces reports for all sessions + `batch_qc_summary.csv`
- Reports contain all required fields including `fallback_path_used`

**Tests required:**
- Unit: `test_014_qc_sidecar.py` — run QC aggregator on golden session output; assert `session_qc_report.json` contains all required fields; assert `fallback_path_used` present; assert `overall_qc_status` is one of PASS/WARN/FAIL
- Integration: run batch mode on `data/` directory; assert `batch_qc_summary.csv` has one row per session; assert no missing values in required columns

**Regression comparison:**
- No parquet changes; no pipeline changes; only new files produced

**Rollback plan:**
- Delete `src/qc_aggregator.py`, `run_qc_sidecar.py`
- No pipeline or parquet impact

**Stop condition:**
- Single-session and batch modes work; all required fields present including `fallback_path_used`; tests pass; PR approved

---

## TIER 3 CHECKPOINT + PRE-015 GATE

**After tickets 011–014 are complete and regression-checked:**

| Check | Required result |
|-------|----------------|
| is_hampel_outlier in parquet | PASS |
| Fast QC script runs < 60s | PASS |
| NB08 session count auto-detected | PASS |
| session_qc_report.json with all required fields | PASS |
| fallback_path_used in session_qc_report.json | PASS |
| Batch mode callable | PASS |
| Golden parquet regression: all Tier 3 tickets | PASS |

**PRE-015 GATE (additional requirements):**

| Gate item | Required result |
|-----------|----------------|
| UD-001 resolved: dance band threshold confirmed | REQUIRED |
| All 001–014 regression checks documented | REQUIRED |
| Implementation log for all 14 tickets complete | REQUIRED |
| Frozen golden parquet checksums updated | REQUIRED |
| Reviewer sign-off (Opus-level or human) | STRONGLY RECOMMENDED |

**Gate:** Do NOT begin Ticket 015 until ALL Tier 3 checks AND PRE-015 gates pass.

---

### Ticket 015 — S04 Adaptive Dance-Band Correction Loop

| Field | Value |
|-------|-------|
| **ID** | 015 |
| **Title** | S04 adaptive dance-band correction loop |
| **Priority** | P1 |
| **Size** | XL |
| **Prerequisites** | ALL 001–014 (absolute requirement — see blast radius) |
| **Blast radius** | MAXIMUM (ALL parquets regenerated; ALL features changed; ALL golden tests must be re-frozen) |

**Source audit refs:**
- Phase 4 S04 filtering audit: "dance-band threshold is static; no adaptive correction"
- Phase 10 anti-overengineering: "S04 adaptive loop is the one algorithm change approved for Minimal v1"
- Phase 11 skeleton §4 (S04 stage skeleton): adaptive loop spec
- Phase 10 decision: blast radius = MAXIMUM; requires all prior tickets complete

**UD-001 dependency:**
- The dance-band threshold default value must be confirmed (UD-001) before Ticket 015 begins
- Default proposed: -3 dB attenuation at target frequency band
- User must explicitly confirm this value in writing before implementation

**Rationale:**
The current static dance-band threshold produces suboptimal filtering for sessions with highly variable movement amplitude. An adaptive threshold that adjusts based on session-level signal statistics improves artifact rejection without introducing bias. This is the ONE algorithm change in Minimal v1.

**Files to change:**
- `src/filtering.py` — implement adaptive threshold loop:
  1. Compute initial artifact fraction with static threshold
  2. If `artifact_fraction > config.dance_band_high_water_mark`: relax threshold by step
  3. If `artifact_fraction < config.dance_band_low_water_mark`: tighten threshold by step
  4. Repeat until artifact fraction within target band or max iterations reached
  5. Log: threshold used, iterations, artifact fraction at convergence, convergence status
- `config/config_v1.yaml` — add: `dance_band_threshold`, `dance_band_high_water_mark`, `dance_band_low_water_mark`, `dance_band_step`, `dance_band_max_iterations`

**Full pre-implementation protocol (REQUIRED before any code change):**
1. Confirm UD-001 value in writing
2. Run full pipeline on all sessions with current static threshold; record all parquet checksums
3. Write pre-implementation brief in implementation log: expected changes, sessions likely affected, convergence criteria
4. Get reviewer sign-off on pre-implementation brief

**Full post-implementation protocol:**
1. Run full pipeline on all sessions with adaptive threshold
2. Compute before/after diff for every numeric column in every parquet
3. Document: which sessions changed, by how much, which features were most affected
4. Freeze new golden parquet checksums
5. Confirm all downstream notebooks (NB08 etc.) still produce valid output
6. Run all regression tests against new golden parquets
7. Write post-implementation brief

**Scope:**
- Adaptive loop in `src/filtering.py` only
- Config values added for threshold parameters
- Do NOT change any other filtering algorithm
- Do NOT change Hampel filter (KEEP_AS_IS)

**Non-goals:**
- Per-joint adaptive thresholds (future_v2)
- ML-based threshold selection (future_v2)
- Changing any other pipeline stage

**Expected behavior after ticket:**
- Sessions with highly variable amplitude: adaptive threshold converges within max_iterations
- All sessions: artifact fraction at convergence within [low_water_mark, high_water_mark]
- Sessions where static threshold was already optimal: minimal or no change

**Tests required:**
- Unit: `test_015_adaptive_loop_convergence.py` — synthetic session with known artifact pattern; assert convergence within max_iterations; assert artifact fraction at convergence within target band
- Unit: `test_015_static_compatible.py` — session where static threshold is optimal; assert adaptive loop produces same threshold as static (within 0.1 dB)
- Regression: document ALL parquet changes; confirm no unexpected changes beyond filtering columns

**Regression comparison:**
- ALL parquets regenerated; ALL checksums updated
- Before/after diff documented for every session
- Expected changes: filtering columns, derived features; unexpected changes: any non-filtering column change

**Rollback plan:**
- Remove adaptive loop from `src/filtering.py`
- Remove new config keys from `config_v1.yaml`
- Restore previous golden parquet checksums
- Requires full parquet regen on rollback

**Stop condition:**
- UD-001 confirmed; pre-implementation brief approved; adaptive loop converges for all sessions; post-implementation diff documented; new golden parquets frozen; all tests pass; PR approved

---

## POST-TICKET-015 CHECKPOINT

| Check | Required result |
|-------|----------------|
| Adaptive loop converges for all sessions | PASS |
| Before/after diff documented for all sessions | PASS |
| All downstream notebooks valid | PASS |
| New golden parquet checksums frozen | PASS |
| All 15 implementation logs complete | PASS |

---

## Tier Checkpoint Summary

| Tier | Tickets | Gate condition |
|------|---------|---------------|
| Tier 1 | 001–007 | All 9 checks pass; no parquet regression |
| Tier 2 | 008–010 | All 6 checks pass; ATF_axial change documented |
| Tier 3 | 011–014 | All 6 checks pass + PRE-015 gate |
| Tier 4 | 015 | UD-001 confirmed; all 001–014 complete; pre-impl brief approved |
| Post-015 | — | All 5 checks pass; thesis-ready parquets |

---

## User Decisions Required

| ID | Decision | Blocks | Status |
|----|----------|--------|--------|
| UD-001 | S04 dance-band threshold value (proposed: -3 dB at target frequency) | Ticket 015 | **OPEN — must resolve before Ticket 015** |
| UD-003 | Gate chain scope (S01 only, or S01+S02+S03) | Ticket 002 | **CONFIRMED: S01-only** |
| UD-004 | QC sidecar timing (inline vs. post-pipeline) | Ticket 014 | **CONFIRMED: post-pipeline, two separate steps** |
| UD-005 | Study N (N=2 subjects or N=3 subjects) | Thesis release | **OPEN — does not block Minimal v1** |
| UD-006 | Session label naming convention (`651` vs `Subject_651`) | Ticket 004 | **OPEN — must resolve before Ticket 004** |

**UD-006 detail:** The session label columns (`subject_id`, `session_id`, `phase_id`, `rep_id`) must follow one consistent naming convention across all parquets. Options:
- Abbreviated: `subject_id = "651"`, `session_id = "T1"`, `phase_id = "P1"`, `rep_id = "R1"`
- Expanded: `subject_id = "Subject_651"`, `session_id = "Session_T1"`, `phase_id = "Phase_P1"`, `rep_id = "Rep_R1"`
User must confirm which convention before Ticket 004 implementation begins.

---

## Repository Classification Update

The following 8 files are reclassified from `DEPENDENCY_UNVERIFIED` to `FORENSIC_SUBSYSTEM_ONLY` (confirmed by targeted grep in Phase 11.5):

| File | Previous classification | New classification | Evidence |
|------|------------------------|-------------------|---------|
| `src/forensic_report.py` | DEPENDENCY_UNVERIFIED | FORENSIC_SUBSYSTEM_ONLY | Only imports itself and forensic_config |
| `src/forensic_config.py` | DEPENDENCY_UNVERIFIED | FORENSIC_SUBSYSTEM_ONLY | Config for forensic subsystem only |
| `src/forensic_plots.py` | DEPENDENCY_UNVERIFIED | FORENSIC_SUBSYSTEM_ONLY | Only imported by forensic_report.py |
| `src/interpolation_logger.py` | DEPENDENCY_UNVERIFIED | FORENSIC_SUBSYSTEM_ONLY | Only imported by forensic_report.py |
| `src/interpolation_tracking.py` | DEPENDENCY_UNVERIFIED | FORENSIC_SUBSYSTEM_ONLY | Only imported by forensic_report.py |
| `src/gate_integration.py` | DEPENDENCY_UNVERIFIED | FORENSIC_SUBSYSTEM_ONLY | Only imported by forensic_report.py and __init__.py |
| `src/burst_classification.py` | DEPENDENCY_UNVERIFIED | FORENSIC_SUBSYSTEM_ONLY | Only imported by gate_integration.py and forensic_report.py |
| `src/_run_forensic_batch.py` | DEPENDENCY_UNVERIFIED | FORENSIC_SUBSYSTEM_ONLY | Forensic batch runner; no active pipeline imports |

**Confirmed:** NB08 has 0 forensic imports (grep result). Forensic subsystem does not touch active pipeline. Ticket 013 is NOT blocked by forensic dependency checks.

**Policy:** These 8 files receive ZERO changes in Minimal v1. Forensic subsystem is preserved as-is for future use.

---

## Implementation Log Template

*(To be used for each ticket in Phase 13)*

```markdown
# Ticket {NNN} Implementation Log

**Date:** YYYY-MM-DD
**Implementer:** [name or agent]
**Status:** IN_PROGRESS | COMPLETE | BLOCKED | ROLLED_BACK

## Pre-Implementation Statement

I have read:
- [ ] Ticket {NNN} spec (this document, §Ticket {NNN})
- [ ] All files listed in "Files to change"
- [ ] All prerequisite ticket implementation logs

I confirm:
- [ ] Prerequisite tickets {list} are complete and regression-checked
- [ ] Golden parquet checksums frozen before this ticket: [checksum file path]
- [ ] I will not modify any file not listed in "Files to change" except for test files

## Changes Made

| File | Change type | Description |
|------|-------------|-------------|
| | | |

## Tests Run

| Test | Command | Result |
|------|---------|--------|
| | | |

## Regression Comparison

**Before checksum:** [hash or file path]
**After checksum:** [hash or file path]
**Diff summary:** [unchanged / N rows changed / N columns added]

## Issues Encountered

[Any blockers, unexpected behaviors, or decisions made during implementation]

## Post-Implementation Sign-Off

- [ ] All tests pass
- [ ] Regression check passes
- [ ] Implementation log complete
- [ ] PR approved
```

---

## Phase 13 Pre-Implementation Statement Template

*(To be completed at the START of each Phase 13 ticket implementation — before any code is written)*

```markdown
## Pre-Implementation Statement — Ticket {NNN}

I am about to implement Ticket {NNN}: {title}.

**I have read:**
- Ticket {NNN} specification in 12_implementation_backlog.md
- All files listed as "Files to change": {list}
- Prerequisite ticket logs: {list}

**I confirm:**
- The prerequisite tickets {list} are complete and their regression checks pass
- The golden parquet checksums are frozen at: {checksum path or hash}
- The blast radius is: {LOCAL | PARQUET_REGEN | MAXIMUM}
- The stop condition is: {copy from ticket spec}

**Expected changes:**
{1-3 sentences describing what will change and what will not change}

**If I encounter anything not covered by the spec, I will STOP and ask before proceeding.**
```

---

## Rejected Items (DO_NOT_DO)

These items were evaluated and explicitly rejected. Do not reopen without a new audit phase.

| Item | Rationale |
|------|-----------|
| Merge S01 + S02 into single stage | Independent failure modes; frame count chain requires separation |
| Add FAIL gates to S02, S03, S04, S05, S06 | Only S01 FAIL gate approved (UD-003); downstream gates rejected as over-engineering |
| PCHIP interpolation in Minimal v1 | Candidate pending tests; 3 specific synthetic tests required first |
| SLERP quaternion interpolation | future_v2; not needed for position data |
| Rename `finite_difference_5point()` | Deferred; not Minimal v1 |
| Centralized config registry / config schema validation | Over-engineering |
| Per-joint adaptive dance-band thresholds | future_v2 |
| ML-based threshold selection | future_v2 |
| Real-time pipeline integration for Fast QC | Fast QC is pre-pipeline and independent |
| Dashboard or QC visualization | Not in Minimal v1 |
| Automatic retry or fallback on S01 FAIL | Rejected; FAIL must halt |
| Forensic subsystem integration into active pipeline | FORENSIC_SUBSYSTEM_ONLY; no active pipeline integration |
| Reorganize repository structure | Deferred; not Minimal v1 |
| Add new base classes or factory patterns | Rejected as over-engineering |
| Plugin system for stages | Rejected as over-engineering |
| Backward-compatibility shims | Rejected; just change the code |
| Unused variable underscore renaming | Rejected as noise |
| Docstring/comment additions to unchanged code | Rejected as noise |
| S06 split into S06a/S06b | future_v2 |
| "Data Intake / Scientific Analysis / Feature Extraction" folder reorganization | optional_improvement, not Minimal v1 |

---

## Deferred Items

These items are valid but deferred to v2 or post-thesis.

| Item | Target | Notes |
|------|--------|-------|
| PCHIP interpolation activation | Post-Minimal v1 | Requires 3 synthetic tests; logging added in Ticket 009 |
| SLERP quaternion interpolation | v2 | For quaternion-specific interpolation |
| Per-joint adaptive dance-band thresholds | v2 | Global adaptive loop first (Ticket 015) |
| S06 split into S06a/S06b | v2 | Kinematics vs feature extraction split |
| `finite_difference_5point()` rename | v2 | Not a priority; not misleading for current use |
| Config schema validation | v2 | Centralized validation system |
| Forensic subsystem integration | Post-thesis decision | Evaluate after thesis submission |
| Additional gate checks (S02-S06) | v2 | S01-only confirmed for Minimal v1 |
| Cross-session grouped analysis framework | Post-Minimal v1 | Session labels (Ticket 004) enable this |
| Dashboard / visualization tools | Post-Minimal v1 | Fast QC report + NB08 sufficient for thesis |
| Automatic parquet migration / versioning | v2 | schema_version field (Ticket 007) enables future migration |
| Per-subject golden parquet sets | Post-Minimal v1 | Single golden set sufficient for now |
| CI/CD pipeline integration | Post-thesis | Manual regression checks for Minimal v1 |

---

## Implementation-Readiness Verdict

**VERDICT: IMPLEMENTATION-READY WITH CONDITIONS**

The Minimal v1 backlog is complete. Implementation may begin when the following conditions are satisfied:

**Immediate blockers (must resolve FIRST):**
1. **UD-006:** Confirm session label naming convention (`651` vs `Subject_651`) — blocks Ticket 004
2. **Freeze golden parquet checksums** before Ticket 001 implementation begins

**Recommended before starting:**
3. Opus-level review of Ticket 015 spec (blast radius is MAXIMUM; review strongly recommended but not mandatory if human oversight is available)
4. Confirm `data/subject_metadata.json` contains expected session counts (needed for Ticket 013)

**Can proceed without:**
- UD-001 (dance-band threshold) — not needed until Ticket 015; can be deferred to Tier 3 checkpoint
- UD-005 (study N) — does not block any Minimal v1 ticket

**First ticket to implement:** Ticket 001 (config snapshot) — smallest blast radius, no prerequisites, foundational for all others

**Implementation order is strict:** 001 → 002 → (003, then 004 after UD-006 resolved) → 005 → 006 → 007 → [TIER 1] → 008 → 009 → 010 → [TIER 2] → 011 → 012 → 013 → 014 → [TIER 3 + PRE-015 GATE] → 015 → [POST-015]

**Implementation agent guidance:**
- Read the full ticket spec before touching any file
- Complete the Pre-Implementation Statement template before writing code
- Run regression check before marking any ticket complete
- If anything unexpected is found, STOP and document before proceeding
- Ticket 015 requires pre-implementation brief approval before any code is written

---

*Phase 12 complete. Proceed to Phase 13 for implementation, one ticket at a time.*
