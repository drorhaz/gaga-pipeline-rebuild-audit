# Phase 12 — Implementation Backlog (CORRECTED)

**Status:** CORRECTED — authoritative for Phase 13 implementation
**Date:** 2026-05-17
**Supersedes:** `12_implementation_backlog.md` (original, do not implement from)
**Corrected by:** Phase 12.5 Opus Backlog Alignment Review
**Incorporates:** Phase 11.5 corrections R1–R6, all Phase 12.5 corrections M1–M6 and C1–C31

---

## Anti-Overengineering Commitments

These constraints apply to ALL 15 tickets. Violation of any commitment requires explicit user approval.

1. **Do not refactor working algorithms.** Every algorithm in the KEEP_AS_IS list (25 items) is touched ONLY if a specific audit finding requires a fix.
2. **Do not add abstraction layers.** No new base classes, no factory patterns, no plugin systems.
3. **Do not touch forensic subsystem.** 8 FORENSIC_SUBSYSTEM_ONLY files receive ZERO changes.
4. **Do not reorganize the repository.** No folder moves, no file renames during Minimal v1.
5. **Minimal v1 scope is final.** 15 tickets. No additions without a new audit phase.
6. **Every ticket ends with a regression check** against the frozen golden parquet.
7. **Parquet stays numeric and ML-ready.** Sidecar-first QC. No per-feature reliability columns in parquet. No diagnostic expansions per row.

---

## Step 02 Interpolation Policy Decision

**Status:** RESOLVED — linear retained as default for artifact masking; PCHIP/SLERP are `candidate_pending_tests`

**Terminology correction (from Phase 12.5):** Step 02 has TWO distinct code paths:
- **Artifact masking** (active path): uses `np.interp` (linear) in `src/preprocessing.py::detect_and_mask_artifacts()` — currently mislabeled as `pchip_single_pass` in logs.
- **Genuine gap fill** (inactive path): uses PCHIP in `src/gapfill_positions.py` and SLERP placeholder in `src/gapfill_quaternions.py` — never triggered on any of the 15 current sessions.

| Method | Active path | Decision | Rationale |
|--------|-------------|----------|-----------|
| Linear interpolation (`np.interp`) | Artifact masking | **RETAIN as Minimal v1 default** | Adequate for short artifact segments |
| PCHIP (positions) | Genuine gap fill | `candidate_pending_tests` | Better for longer gaps; 3 synthetic tests required |
| SLERP (quaternions) | Genuine gap fill | `candidate_pending_tests` | Geodesically correct for quaternion gaps; 3 synthetic tests required |

**PCHIP activation criteria (NOT Minimal v1):**
1. Trigger: `max_artifact_segment_frames_positions > 10` frames for any joint (logged by Ticket 009)
2. Three synthetic tests: (A) short segment equivalence, (B) long segment improvement, (C) edge continuity
3. Golden parquet comparison shows no regression

**SLERP activation criteria (NOT Minimal v1):**
1. Trigger: quaternion gap fill becomes active (currently never triggered)
2. Three synthetic tests analogous to PCHIP tests for quaternion domain

**Ticket 009 responsibility:** Add logging of artifact/gap segment statistics. Do NOT add PCHIP or SLERP code.

---

## Backlog Overview

**Total tickets:** 15 (Minimal v1). Subtask splits (007a/b, 014a/b) do not create new ticket numbers.
**Ordering:** strict — each ticket must pass regression check before next begins.

| Ticket | Title | Priority | Size | Prerequisites | Blast Radius |
|--------|-------|----------|------|---------------|--------------|
| 001 | Per-run config snapshot | P0 | XS | none | LOCAL |
| 002 | S01 hard FAIL gate (conservative) | P0 | S | 001 | LOCAL |
| 003 | S03 frame count verification and fix | P0 | M | 001, 002 | PARQUET_REGEN (if bug exists) or LOCAL (if already fixed) |
| 004 | ref_is_fallback metadata + session labels | P0 | M | 003 | PARQUET_REGEN |
| 005 | ref_quality_score guard + t_pose_failed guard | P0 | XS | 002 | LOCAL |
| 006 | hard_exclude in v2_feature_engine | P0 | S | 002, 005 | LOCAL |
| 007a | PyArrow metadata fields (5 approved) | P1 | S | none | PARQUET_REGEN (metadata only) |
| 007b | Quaternion diagnostics sidecar + Hampel summary | P1 | S | none | LOCAL |
| — | **TIER 1 CHECKPOINT** | — | — | 001–007 | — |
| 008 | Artifact fraction fix + reference threshold fix | P1 | S | 006 | LOCAL (quality_df) |
| 009 | S02 label correction + artifact/gap logging | P1 | S | none | LOCAL |
| 010 | Hips excluded from ATF_axial + spec amendment | P1 | M | 008 | PARQUET_REGEN (features) |
| — | **TIER 2 CHECKPOINT** | — | — | 008–010 | — |
| 011 | is_hampel_outlier correction | P1 | M | pre-investigation + D1 resolved | PARQUET_REGEN |
| 012 | Fast QC script (Phase 8 spec) | P2 | L | none | LOCAL |
| 013 | NB08 session count sync | P3 | S | none | LOCAL |
| 014a | session_qc_report.json + batch mode | P3 | M | 007a, 008 | LOCAL |
| 014b | feature_reliability_table.csv | P3 | M | 014a, v2_feature_engine run | LOCAL |
| — | **TIER 3 CHECKPOINT + PRE-015 GATE** | — | — | 011–014 | — |
| 015 | S04 PSD/dance-band correction loop | P1 | XL | ALL 001–014 + UD-001 | MAXIMUM |

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
| **Blast radius** | LOCAL |

**Source audit refs:** Phase 5 F-INT2; Phase 10 §H
**Rationale:** Config is mutated in-place by `run_pipeline.py::update_config()`. Previous config state is permanently lost after every run.

**Files to change:**
- `run_pipeline.py` — write YAML snapshot BEFORE `update_config()` mutates `config_v1.yaml`
- `config/config_v1.yaml` — add `pipeline_version` field (e.g., `"v4.0"`)
- `src/pipeline_config.py` — ensure `pipeline_version` is exposed in CONFIG dict
- Optionally `src/utils.py` — add `save_config_snapshot()` if helper is useful

**Scope:**
- Write current config dict to `derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml` before any mutation
- Include: `pipeline_version`, timestamp, all config keys and values
- Must work for BOTH execution paths: papermill (run_pipeline.py) and direct Python (src/pipeline.py)

**Non-goals:** Config schema validation, config diff between runs, centralized config registry

**Expected behavior:** Every pipeline run produces a frozen YAML snapshot. No parquet changes.

**Tests:**
- Unit: assert snapshot YAML exists after run; assert valid YAML; assert contains `pipeline_version`
- Regression: golden parquet unchanged

**Rollback:** Remove snapshot write call. No parquet impact.
**Stop condition:** Snapshot exists for every run; regression passes.

---

### Ticket 002 — S01 Hard FAIL Gate (Conservative)

| Field | Value |
|-------|-------|
| **ID** | 002 |
| **Title** | S01 hard FAIL gate (conservative) |
| **Priority** | P0 |
| **Size** | S |
| **Prerequisites** | 001 |
| **Blast radius** | LOCAL |

**Source audit refs:** Phase 5.5 F-651-1 (USER DIRECTIVE LOCKED); Phase 10 §Layer 3
**Rationale:** Dead session (651_T2_P2_R2, 5 frames, 0.03s) passed all 6 stages silently.

**Files to change:**
- `src/preprocessing.py` — add validation in `parse_optitrack_csv()`: check duration and frame count after parsing
- `src/pipeline.py` — check gate_01_status; halt session on FAIL

**FAIL conditions (conservative — Phase 10 approved only):**
- Duration < 30 seconds (USER DIRECTIVE)
- Frame count < 3600 (USER DIRECTIVE)
- Unrecoverable parse failure: file unreadable, missing Frame/Time columns

**NOT approved as FAIL (keep as WARN in stage JSON):**
- Marker label mismatch — recoverable; log as WARNING
- Column count deviations — log as WARNING

**Scope:**
- FAIL produces `{run_output_dir}/{RUN_ID}__s01_fail_report.json`
- FAIL halts session processing; no parquet produced
- gate_01_status: "PASS" or "FAIL" written to S01 stage JSON

**Non-goals:** S02–S06 FAIL gates, two-tier FAIL/SUSPICIOUS, automatic retry

**Tests:**
- Unit: inject 5-frame CSV → assert FAIL; inject valid CSV → assert PASS; assert no parquet on FAIL
- Regression: valid session produces identical golden parquet

**Rollback:** Revert validation block. No parquet changes.
**Stop condition:** Dead sessions FAIL; valid sessions PASS unchanged; regression passes.

---

### Ticket 003 — S03 Frame Count Verification and Fix

| Field | Value |
|-------|-------|
| **ID** | 003 |
| **Title** | S03 frame count verification and fix |
| **Priority** | P0 |
| **Size** | M |
| **Prerequisites** | 001, 002 |
| **Blast radius** | PARQUET_REGEN if bug exists; LOCAL if already fixed |

**Source audit refs:** Phase 5 F-INT1; Phase 10.5 §D
**Rationale:** Phase 10 reported n_target drops last frame. S01=16,915 → S04=16,914 universal.

**PATH_VERIFY_REQUIRED:** Current code at `src/resampling.py` line 172 reads: `n = int(round((t1 - t0) * fs_target)) + 1`. This already includes `+1`. The implementer MUST first verify:
1. Run pipeline on a golden session
2. Compare S01 frame count vs. S03 output frame count
3. Compare against historical derivatives to confirm whether bug still exists
4. If formula already correct: Ticket 003 becomes verification + logging only

**Files to change:**
- `src/resampling.py` — function `resample_time_grid()` at line 169
- If bug exists: fix the n_target formula
- Regardless: add explicit frame count assertion: `assert len(output) == expected_n_frames`
- Add `n_frames_input`, `n_frames_output`, `frame_count_delta` to resample_summary JSON

**If bug exists — Parquet regen protocol:**
1. Freeze current golden checksums
2. Implement fix
3. Run pipeline on ALL sessions
4. Record before/after frame count diff
5. Update golden checksums
6. Confirm regression test passes against NEW golden

**If already fixed:** Add logging + assertion only. No parquet regen needed.

**Non-goals:** Changing resampling algorithm, changing target sample rate

**Tests:**
- Unit: run S03 twice on same input → assert identical frame counts (determinism)
- Regression: document frame count before/after

**Rollback:** Revert formula if changed. Requires parquet regen on rollback.
**Stop condition:** Frame count deterministic; assertion passes; regression documented.

---

### Ticket 004 — ref_is_fallback Metadata + Session Labels

| Field | Value |
|-------|-------|
| **ID** | 004 |
| **Title** | ref_is_fallback metadata + session labels |
| **Priority** | P0 |
| **Size** | M |
| **Prerequisites** | 003 |
| **Blast radius** | PARQUET_REGEN (4 new data columns + 1 metadata field) |
| **BLOCKED ON** | UD-006: session label naming and value format |

**Source audit refs:** Phase 5.5 F-651-4; Phase 6 parquet-labels; Phase 10 §Approved Parquet Changes

**CORRECTION from Phase 12.5 (M2):** `ref_is_fallback` is a **PyArrow metadata field only**, NOT a per-row data column. It is session-constant — adding it per-row is schema bloat.

**Files to change:**
- `src/export_tables.py` (or `src/pipeline.py` S06 write code) — add 4 per-row data columns; add `ref_is_fallback` to PyArrow metadata
- Read `ref_is_fallback` from S05 `reference_info.json` at S06 write time
- R3 (Phase 11.5): graceful handling if S05 JSON is missing (set `ref_is_fallback = null`, log WARNING)

**Per-row data columns (Phase 10 approved names):**

| Column | Type | Source | UD-006 value decision needed |
|--------|------|--------|------------------------------|
| `subject_id` | str | parse from RUN_ID | `651` vs `Subject_651` |
| `timepoint` | str | parse from RUN_ID | `T1` vs `1` |
| `piece` | str | parse from RUN_ID | `P2` vs `2` |
| `rep` | str | parse from RUN_ID | `R1` vs `1` |

**PyArrow metadata addition:** `ref_is_fallback` (bool) — from S05 reference_info.json

**Schema after this ticket:** ~803 existing + 4 data columns = ~807 data columns + existing metadata + `ref_is_fallback`

**Non-goals:** `fallback_path_used` (Ticket 014a), additional metadata beyond Phase 10 list, `ref_is_fallback` as per-row column

**Tests:**
- Unit: load parquet; assert 4 session label columns present with correct dtypes; assert `ref_is_fallback` in PyArrow metadata
- Regression: existing numeric columns unchanged within 1e-9

**Rollback:** Remove new columns/metadata from write path. Requires parquet regen.
**Stop condition:** UD-006 resolved; columns present; metadata present; regression passes.

---

### Ticket 005 — ref_quality_score Guard + t_pose_failed Guard

| Field | Value |
|-------|-------|
| **ID** | 005 |
| **Title** | ref_quality_score guard + t_pose_failed guard |
| **Priority** | P0 |
| **Size** | XS |
| **Prerequisites** | 002 |
| **Blast radius** | LOCAL |

**Source audit refs:** Phase 5.5 F-651-2, F-651-5; Phase 10 F-004, F-005

**Field name correction (Phase 12.5 C11):** Prior audit phases called this `var_score`. The actual field name in source code is `ref_quality_score` (`src/reference.py` line 278: `ref_quality_score = np.median(list(ref_stds.values()))`).

**Files to change:**
- `src/reference.py` — in `compute_q_ref_and_ref_qc()`:
  - When `t_pose_failed=True`: `ref_quality_score` is already `float("nan")` (line 230). Ensure JSON serialization writes `null` not `NaN` string or `Infinity`.
  - For non-identity fallback sessions: set `t_pose_failed = False` explicitly (not `None`/`null`)
  - When n_frames == 0: ensure `ref_quality_score = None` (JSON `null`)

**Scope:**
- Fix JSON serialization of `ref_quality_score` edge cases
- Fix `t_pose_failed` None vs False for non-identity fallbacks

**Non-goals:** Changing T-pose detection algorithm, changing reference computation

**Tests:**
- Unit: mock T-pose failure → assert `t_pose_failed = True`; mock non-identity fallback → assert `t_pose_failed = False` (not None); assert JSON serialization produces valid JSON
- Regression: golden parquet unchanged

**Rollback:** Revert guards. No parquet changes.
**Stop condition:** Edge cases handled; JSON valid; regression passes.

---

### Ticket 006 — hard_exclude in v2_feature_engine

| Field | Value |
|-------|-------|
| **ID** | 006 |
| **Title** | hard_exclude in v2_feature_engine |
| **Priority** | P0 |
| **Size** | S |
| **Prerequisites** | 002, 005 |
| **Blast radius** | LOCAL |

**Source audit refs:** Phase 7 F7-5; Phase 10 F-006

**Files to change:**
- `src/v2_feature_engine.py` — in `build_pca_engine()` (line 514): add dead_recording → `hard_exclude=True` check before PCA fitting; also apply in `compute_quality_gates()` (line 181)

**Scope:** Dead session gets `hard_exclude=True`; skipped in PCA engine and quality gate computation.

**Non-goals:** Changing feature definitions, PCA algorithm, quality gate thresholds (those are Ticket 008)

**Tests:**
- Unit: inject dead session → assert `hard_exclude=True`; assert not included in PCA fit
- Regression: golden parquet unchanged if no dead sessions are in current golden set

**Rollback:** Remove hard_exclude check. No parquet changes.
**Stop condition:** Dead sessions excluded from PCA; tests pass.

---

### Ticket 007a — PyArrow Metadata Fields (5 Approved)

| Field | Value |
|-------|-------|
| **ID** | 007a |
| **Title** | PyArrow metadata fields (5 approved) + graceful JSON handling |
| **Priority** | P1 |
| **Size** | S |
| **Prerequisites** | none (but run after 002 so gate_01_status exists) |
| **Blast radius** | PARQUET_REGEN (metadata additions only; no data value changes) |

**Source audit refs:** Phase 10 §Approved Parquet Changes Summary; Phase 11.5 R3

**CORRECTION from Phase 12.5 (M3):** The 5 metadata fields are those approved by Phase 10, not the fields Phase 12 listed.

**PyArrow metadata fields to add:**

| Field | Type | Source JSON | Read at |
|-------|------|-------------|---------|
| `ref_is_fallback` | bool | S05 reference_info.json | S06 write time |
| `filter_psd_verdict` | str | S04 __filtering_summary.json | S06 write time |
| `pipeline_version` | str | config snapshot / config_v1.yaml | S06 write time |
| `gate_01_status` | str | S01 stage summary JSON | S06 write time |
| `bone_qc_status` | str | S02 kinematics_map.json | S06 write time |

**Optional 6th field:** `schema_version` (str, e.g., `"v2.0"`) — recommended but not required.

**Files to change:**
- `src/export_tables.py` (or wherever parquet write occurs in S06) — read prior stage JSONs; add to PyArrow `schema.metadata`
- R3 (Phase 11.5): if any prior stage JSON is missing or malformed: set field to `null`, log WARNING, do NOT fail

**Scope:** Infrastructure only — read existing JSONs, propagate to parquet metadata.

**Non-goals:** Computing new values, changing stage algorithms, adding per-row columns

**Tests:**
- Unit: load parquet with PyArrow; assert all 5 metadata keys present; assert non-null for valid sessions
- Unit (R3): delete a stage JSON; assert WARNING logged; assert metadata field is null; assert no exception
- Regression: all per-row data unchanged

**Rollback:** Remove metadata fields from parquet write. Requires parquet regen.
**Stop condition:** All 5 fields present; graceful handling works; regression passes.

---

### Ticket 007b — Quaternion Diagnostics Sidecar + Hampel Summary

| Field | Value |
|-------|-------|
| **ID** | 007b |
| **Title** | Quaternion diagnostics sidecar + Hampel summary in filtering_summary.json |
| **Priority** | P1 |
| **Size** | S |
| **Prerequisites** | none |
| **Blast radius** | LOCAL (sidecar additions only; no parquet data changes) |

**Source audit refs:** Phase 10.5 §Clarification A (quaternion diagnostics); Phase 11.5 R1 (Hampel summary)

**CORRECTION from Phase 12.5 (M4):** Quaternion diagnostics go to sidecar JSON, NOT per-row parquet columns.

**Quaternion diagnostics** — write to `{RUN_ID}__validation_report.json` under `quaternion_diagnostics` key:

| Field | Per-joint | Description |
|-------|-----------|-------------|
| `quat_norm_mean` | yes | Mean ‖q‖ before renormalization |
| `quat_norm_std` | yes | Std of ‖q‖ |
| `quat_norm_min` | yes | Min ‖q‖ |
| `quat_norm_max` | yes | Max ‖q‖ |
| `renorm_burden_pct` | yes | % frames where |‖q‖-1| > 0.05 |
| `hemisphere_flip_count` | yes | Flips detected and corrected |
| `rotation_method_verdict` | session | CURRENT_METHOD_ACCEPTABLE / REVIEW_SO3_SMOOTHING / SO3_UPGRADE_RECOMMENDED |

**Warning threshold:** If `renorm_burden_pct > 5%` for any joint, set verdict to `REVIEW_SO3_SMOOTHING`.

**Hampel summary** — add to existing `__filtering_summary.json`:
```json
{
  "hampel_modification_fraction_per_joint": {"joint_name": 0.0, ...},
  "hampel_max_fraction_any_joint": 0.0,
  "hampel_joints_above_threshold": []
}
```

**Files to change:**
- `src/angular_velocity.py` or inline in `src/pipeline.py` — compute quaternion norm diagnostics during S06
- `src/filter_export.py` — add Hampel summary fields to filtering_summary.json export
- `src/filtering.py` — ensure `apply_hampel_filter()` returns per-joint modification counts (may already do via outlier_mask)

**Non-goals:** Changing quat_log algorithm, switching omega_method, adding SO(3)-aware smoothing

**Tests:**
- Unit: run pipeline on golden session; assert `validation_report.json` contains `quaternion_diagnostics`; assert all per-joint fields present; assert `quat_norm_mean` ≈ 1.0
- Unit: assert `filtering_summary.json` contains `hampel_modification_fraction_per_joint`
- Regression: parquet unchanged (sidecar additions only)

**Rollback:** Remove sidecar additions. No parquet impact.
**Stop condition:** Diagnostics logged; Hampel summary logged; tests pass.

---

## TIER 1 CHECKPOINT

| Check | Required |
|-------|----------|
| Config snapshot exists for every run | PASS |
| S01 FAIL gate works (conservative scope) | PASS |
| S03 frame count verified and documented | PASS |
| 4 session label columns in parquet | PASS (UD-006 resolved) |
| ref_is_fallback in PyArrow metadata | PASS |
| ref_quality_score/t_pose_failed guards active | PASS |
| hard_exclude enforced in v2_feature_engine | PASS |
| 5 PyArrow metadata fields in parquet | PASS |
| Quaternion diagnostics in validation_report.json | PASS |
| Hampel summary in filtering_summary.json | PASS |
| Golden parquet regression: all Tier 1 tickets | PASS |

**Gate:** Do NOT begin Ticket 008 until all checks pass.

---

### Ticket 008 — Artifact Fraction Fix + Reference Threshold Fix

| Field | Value |
|-------|-------|
| **ID** | 008 |
| **Title** | Artifact fraction fix + reference threshold fix |
| **Priority** | P1 |
| **Size** | S |
| **Prerequisites** | 006 |
| **Blast radius** | LOCAL (quality_df verdicts may change) |

**Source audit refs:** Phase 7 F7-3 (artifact fraction), F7-4 (reference threshold)

**Files to change:**
- `src/v2_feature_engine.py` — `compute_quality_gates()` (line 181): change artifact fraction from `max(joint_art_rates)` to OR-union / `1.0 - clean_fraction_pca`
- `src/v2_feature_engine.py` — `validate_reference()` (line 261): change threshold from 0.30 to 0.20

**Scope:** Two expression changes. quality_df verdicts may change for some sessions. Document which.

**Non-goals:** Changing other thresholds, adding new quality gates

**Tests:**
- Unit: verify artifact fraction uses OR-union; verify threshold = 0.20
- Regression: document any sessions that change quality gate verdict

**Rollback:** Restore original expressions.
**Stop condition:** Both expressions match spec; verdict changes documented; regression passes.

---

### Ticket 009 — S02 Label Correction + Artifact/Gap Logging

| Field | Value |
|-------|-------|
| **ID** | 009 |
| **Title** | S02 label correction + artifact/gap segment logging |
| **Priority** | P1 |
| **Size** | S |
| **Prerequisites** | none |
| **Blast radius** | LOCAL (log/sidecar additions only) |

**Source audit refs:** Phase 4 Q-EXT1b (label mismatch); Phase 11.5 gaps 2–4; Phase 12.5 C20

**Label correction:**
- In `src/preprocessing.py::detect_and_mask_artifacts()` — change log labels:
  - `pchip_single_pass` → `linear_interp` (positions)
  - `slerp` → `quaternion_normalize` (quaternions)

**Artifact/gap segment statistics** — write to `{RUN_ID}__s02_interpolation_stats.json`:

| Field | Type | Description |
|-------|------|-------------|
| `n_artifact_segments_positions` | int | Total artifact segments detected |
| `max_artifact_segment_frames_positions` | int | Longest contiguous artifact segment (frames) |
| `mean_artifact_segment_frames_positions` | float | Mean artifact segment length |
| `n_artifact_segments_above_5_frames` | int | Segments > 5 frames |
| `n_artifact_segments_above_10_frames` | int | Segments > 10 frames (PCHIP activation trigger) |
| `n_gap_fill_events_positions` | int | True gap fill events (currently 0 for all sessions) |
| `n_gap_fill_events_quaternions` | int | True quaternion gap fills (currently 0) |
| `max_gap_duration_frames_positions` | int | Longest position gap (frames) |
| `max_gap_duration_frames_quaternions` | int | Longest quaternion gap (frames) |

**Scope:** Label strings + JSON sidecar. No computation changes. No PCHIP/SLERP code added.

**Non-goals:** Switching to PCHIP, adding PCHIP config flag, changing interpolation algorithm

**Tests:**
- Unit: assert `s02_interpolation_stats.json` exists; assert all 9 fields present; assert labels are `linear_interp` and `quaternion_normalize`
- Regression: parquet unchanged

**Rollback:** Revert label strings; remove JSON output.
**Stop condition:** Labels correct; stats logged; tests pass.

---

### Ticket 010 — Hips Excluded from ATF_axial + Spec Amendment

| Field | Value |
|-------|-------|
| **ID** | 010 |
| **Title** | Hips excluded from ATF_axial + spec amendment |
| **Priority** | P1 |
| **Size** | M |
| **Prerequisites** | 008 |
| **Blast radius** | PARQUET_REGEN (ATF_axial feature values change) |

**Source audit refs:** Phase 7 F7-1; Phase 10 F-012

**Files to change:**
- `src/v2_feature_engine.py` line 58: change `"axial": ["Hips", "Spine", "Spine1", "Neck", "Head"]` to `"axial": ["Spine", "Spine1", "Neck", "Head"]`
- METHODOLOGY_SPEC_v2.md — add amendment: "Hips excluded from ATF_axial computation. Rationale: Hips ATF = 0 permanently (root joint; lin_vel_rel_mag = 0 by definition). Including Hips biases ATF_axial downward."

**Scope:** One list edit + spec amendment. Full parquet regen required.

**Non-goals:** Excluding Hips from other metrics, changing ATF algorithm

**Tests:**
- Unit: verify "Hips" not in JOINT_GROUPS["axial"]; verify ATF_axial values change
- Regression: ATF_axial changes documented; all other columns unchanged within 1e-9

**Rollback:** Restore "Hips" to axial list; revert spec. Requires parquet regen.
**Stop condition:** Hips excluded; ATF_axial change magnitude documented; regression passes.

---

## TIER 2 CHECKPOINT — **CLOSED 2026-05-19** ✓

| Check | Required | Status |
|-------|----------|--------|
| Artifact fraction uses OR-union | PASS | ✓ DONE (Ticket 008) |
| Reference threshold = 0.20 | PASS | ✓ DONE (Ticket 008) |
| S02 labels corrected | PASS | ✓ DONE (Ticket 009) |
| Interpolation stats logged | PASS | ✓ DONE (Ticket 009) |
| Hips excluded from ATF_axial | PASS | ✓ DONE (Ticket 010, +0.0–1.28% on Dev Set) |
| ATF_axial change documented | PASS | ✓ DONE (see ticket_010_hips_atf_axial.md) |
| Golden parquet regression: Tier 2 | PASS | ✓ DONE (numeric hashes unchanged: 4e4b81bc..., b7db8a72..., 5d13f307..., 96ae6216...) |
| is_hampel_outlier corrected (Ticket 011) | PASS | ✓ DONE (Option B OR mask; 976–3925 True frames per Dev Set session) |

**Baseline locked in `audit_outputs/BASELINE_V1_SUMMARY.md`**

---

### Ticket 011 — is_hampel_outlier Correction

| Field | Value |
|-------|-------|
| **ID** | 011 |
| **Title** | is_hampel_outlier correction |
| **Priority** | P1 |
| **Size** | M |
| **Prerequisites** | pre-investigation required; NEW-D1 design decision resolved |
| **Blast radius** | PARQUET_REGEN (existing column corrected) |

**Source audit refs:** Phase 6 Phase6-hampel; Phase 10 F-014

**DESIGN_DECISION_REQUIRED (NEW-D1):**
- **Option A (sidecar mask):** Per-joint Hampel mask in separate `{RUN_ID}__hampel_mask.parquet`. Single summary column in main parquet.
- **Option B (recommended):** Single `is_hampel_outlier` boolean column = OR across all joints. Per-joint summary in `filtering_summary.json` (already added by Ticket 007b).
- **Option C (per-joint):** ~51 `is_hampel_outlier_{joint}` columns. Significant schema bloat.

**Recommendation:** Option B. Preserves parquet-minimal policy. User must confirm before implementation.

**Pre-investigation (before any code change):**
1. Grep for `is_hampel_outlier` or `outlier_mask` in `src/filtering.py` — confirm where flag is stored
2. Confirm `apply_hampel_filter()` returns per-frame outlier mask
3. Trace propagation path from S04 to S06 parquet write
4. Document findings in implementation log

**Files to change (tentative — verify in pre-investigation):**
- `src/filtering.py` — collect outlier mask from `apply_hampel_filter()` (already returns it)
- `src/pipeline.py` or `src/export_tables.py` — propagate to parquet as single boolean column

**Scope:** Correct existing all-False column to reflect actual Hampel activity.

**Non-goals:** Changing Hampel algorithm or parameters, per-joint columns (unless Option C approved)

**Tests:**
- Unit: run S04 on session with known Hampel flags; assert `is_hampel_outlier` column has True values where expected
- Regression: all non-outlier columns unchanged within 1e-9

**Rollback:** Restore all-False column. Requires parquet regen.
**Stop condition:** NEW-D1 resolved; pre-investigation complete; outlier mask correct; regression passes.

---

### Ticket 012 — Fast QC Script (Phase 8 Spec)

| Field | Value |
|-------|-------|
| **ID** | 012 |
| **Title** | Fast QC script |
| **Priority** | P2 |
| **Size** | L |
| **Prerequisites** | none |
| **Blast radius** | LOCAL (new script; no existing changes) |

**Source audit refs:** Phase 8 fast post-collection QC requirements

**CORRECTION from Phase 12.5 (C25–C26):** Phase 8 specifies 37 checks across 3 tiers, not 10.

**Check tiers (from Phase 8):**
- **T1 (File/Structure):** T1-01 through T1-13 — file validity, header, duration, frame count, joints, metadata
- **T2 (Data Quality):** T2-01 through T2-16 — array shapes, NaN fractions, gaps, quaternion norms, velocity spikes
- **T3 (Methodology Plausibility):** T3-01 through T3-08 — motion magnitude, hands/feet dropout, Hips displacement, session duration, T-pose plausibility

**T3-01 (T-pose threshold):** Must remain INFO-only (DRAFT_PENDING_RESEARCH).

**Files to create:**
- `src/fast_qc.py` — implement all Phase 8 checks
- `run_fast_qc.py` (project root) — CLI: `python run_fast_qc.py --session {path}`

**Implementation priority within ticket:**
1. T1-tier checks (FAIL/WARN/INFO for file structure) — must implement
2. T2-tier checks (FAIL/WARN for data quality) — must implement
3. T3-tier checks (WARN/INFO for methodology) — implement if time permits; all can remain stubs that log "NOT_IMPLEMENTED" if needed

**Output:** `fast_qc_report.json` with per-check status (PASS/WARN/FAIL/INFO/NOT_IMPLEMENTED)

**Scope:** Read-only. Does not modify data. Runtime target: < 60 seconds per session.

**Non-goals:** Full pipeline execution, automatic data repair, dashboard

**Tests:**
- Unit: 1 test per T1 check with synthetic FAIL conditions
- Integration: run on golden sessions; assert all T1 + T2 checks produce results
- Runtime: assert < 60 seconds on golden sessions

**Rollback:** Delete `src/fast_qc.py` and `run_fast_qc.py`. No pipeline impact.
**Stop condition:** T1 + T2 checks implemented and tested; T3 checks at least stubbed; runtime < 60s.

---

### Ticket 013 — NB08 Session Count Sync ✓ COMPLETE (2026-05-19)

| Field | Value |
|-------|-------|
| **ID** | 013 |
| **Title** | NB08 session count sync |
| **Priority** | P3 |
| **Size** | S |
| **Prerequisites** | none |
| **Blast radius** | LOCAL |

**Source audit refs:** Phase 4 S08 audit; Phase 11.5 confirmed NB08 forensic-free

**Files to change:**
- `notebooks/08_engineering_physical_audit.ipynb` — replace hardcoded session count with dynamic count from parquet directory

**Scope:** Replace hardcoded `N_SESSIONS` with `len(list(parquet_dir.glob("*.parquet")))`. Add assertion against `data/subject_metadata.json`.

**Non-goals:** Changing NB08 analysis logic, adding forensic imports, papermill parameterization

**Tests:** Manual NB08 end-to-end execution; assert no errors; assert count matches metadata.

**Rollback:** Restore hardcoded count.
**Stop condition:** NB08 runs end-to-end with correct dynamic count.

---

### Ticket 014a — session_qc_report.json + Batch Mode

| Field | Value |
|-------|-------|
| **ID** | 014a |
| **Title** | session_qc_report.json + batch mode (S06-post QC Aggregation) |
| **Priority** | P3 |
| **Size** | M |
| **Prerequisites** | 007a, 008 |
| **Blast radius** | LOCAL (new output files only) |

**Source audit refs:** Phase 9.5 QC-sidecar; Phase 11.5 R2, R4, R5

**This is NOT a pipeline stage.** It is a post-pipeline read-only aggregation step.

**Files to create:**
- `src/qc_aggregator.py` — read existing stage JSONs; aggregate into session_qc_report.json
- `run_qc_sidecar.py` (project root) — CLI: `--session-dir {dir}` and `--batch-dir {dir}` (R5: batch-callable)

**session_qc_report.json required fields:**

| Field | Type | Source |
|-------|------|--------|
| `session_id` | str | RUN_ID |
| `subject_id` | str | RUN_ID |
| `pipeline_version` | str | config snapshot |
| `processing_timestamp` | str (ISO8601) | run metadata |
| `gate_01_status` | str | S01 JSON |
| `ref_is_fallback` | bool | S05 JSON |
| `fallback_path_used` | str or null | S05 JSON (R2) |
| `t_pose_failed` | bool | S05 JSON |
| `ref_quality_score` | float or null | S05 JSON |
| `filter_psd_verdict` | str | S04 JSON |
| `bone_qc_status` | str | S02 JSON |
| `artifact_fraction_per_joint` | dict | S04 JSON |
| `hampel_modification_fraction_per_joint` | dict | S04 JSON (from 007b) |
| `quat_norm_gt5pct_warning` | bool | validation_report.json |
| `overall_qc_status` | str | "PASS" / "WARN" / "FAIL" |

**Batch mode (R5):** `--batch-dir` produces `batch_qc_summary.csv` (one row per session).

**Scope:** Read-only aggregation. Does not re-run pipeline stages. Does not modify parquet.

**Non-goals:** Real-time integration, dashboard, modifying pipeline stages

**Tests:**
- Unit: run on golden session; assert all required fields present including `fallback_path_used`
- Integration: batch mode on `data/`; assert `batch_qc_summary.csv` has correct row count

**Rollback:** Delete `src/qc_aggregator.py` and `run_qc_sidecar.py`. No pipeline impact.
**Stop condition:** Single-session and batch modes work; all required fields present.

---

### Ticket 014b — feature_reliability_table.csv

| Field | Value |
|-------|-------|
| **ID** | 014b |
| **Title** | feature_reliability_table.csv |
| **Priority** | P3 |
| **Size** | M |
| **Prerequisites** | 014a, v2_feature_engine run completion |
| **Blast radius** | LOCAL |

**Source audit refs:** Phase 10 QC-sidecar

**Output:** `{RUN_ID}__feature_reliability_table.csv`

**Required columns:**
- `feature_name`, `feature_family`, `required_joints`, `required_masks`
- `ref_quality_affects`, `filter_quality_affects`, `artifact_burden_affects`
- `reliability_status`: RELIABLE / USE_WITH_CAUTION / UNRELIABLE / NOT_AVAILABLE
- `reason_codes`, `thesis_critical`, `safe_for_ml`

**Scope:** Read from v2_feature_engine output + session_qc_report.json; compute per-feature reliability. Does not modify parquet or pipeline.

**Non-goals:** Per-feature reliability columns in parquet (REJECTED)

**Tests:**
- Unit: assert CSV has expected columns; assert reliability_status values are valid enum values
- Regression: no parquet changes

**Rollback:** Delete CSV generation code. No pipeline impact.
**Stop condition:** CSV produced with all columns; tests pass.

---

## TIER 3 CHECKPOINT + PRE-015 GATE

| Check | Required |
|-------|----------|
| is_hampel_outlier corrected in parquet | PASS |
| Fast QC T1+T2 checks implemented | PASS |
| NB08 session count auto-detected | PASS |
| session_qc_report.json complete | PASS |
| feature_reliability_table.csv produced | PASS |
| Batch mode callable | PASS |
| Golden parquet regression: Tier 3 | PASS |

**PRE-015 GATE (additional):**

| Gate item | Required |
|-----------|----------|
| UD-001 resolved: dance band threshold confirmed | REQUIRED |
| All 001–014 implementation logs complete | REQUIRED |
| Frozen golden parquet checksums updated | REQUIRED |
| Pre-implementation brief for Ticket 015 approved | STRONGLY RECOMMENDED |

---

### Ticket 015 — S04 PSD/Dance-Band Correction Loop

| Field | Value |
|-------|-------|
| **ID** | 015 |
| **Title** | S04 PSD/dance-band correction loop |
| **Priority** | P1 |
| **Size** | XL |
| **Prerequisites** | ALL 001–014 + UD-001 |
| **Blast radius** | MAXIMUM |

**Source audit refs:** Phase 3 S-04.3 design; Phase 10 §E; Phase 10.5 §Correction B and E

**CRITICAL CORRECTION from Phase 12.5 (M1):** Phase 12 replaced the approved PSD/dance-band method with artifact-fraction control. This has been corrected.

**Existing code context:** `src/filtering.py` already contains an adaptive Winter residual analysis loop (lines 636–790) that selects per-joint optimal cutoff frequencies. Ticket 015 adds an **OUTER loop** that checks PSD dance-band preservation AFTER filtering is complete.

**Algorithm (Phase 10.5 approved):**

```
FOR each session:
  1. Run existing 3-stage cleaning pipeline (unchanged):
     - Stage 1: velocity + z-score artifact detection
     - Stage 2: Hampel filter (5-frame, 3σ)
     - Stage 3: Adaptive Winter low-pass (existing per-joint adaptive cutoff)
     + Quaternion median filter

  2. Compute PSD comparison using compute_psd_comparison():
     psd_verdict = evaluate dance-band (1-15 Hz) preservation

  3. IF psd_verdict == REVIEW_OVERSMOOTHING:
     FOR iteration = 1 to max_correction_iterations:
       Raise region_max_hz by correction_step_hz for affected regions
       Re-run Stage 3 ONLY (Stages 1, 2, quat median unchanged)
       Re-check psd_verdict
       IF psd_verdict != REVIEW_OVERSMOOTHING: BREAK

  4. Log: final_cutoff_hz_per_region, n_correction_iterations,
         final_psd_verdict, dance_band_delta_db_mean,
         convergence_status (PASS / CORRECTED / REVIEW_OVERSMOOTHING_UNRESOLVED)
```

**Approved parameters:**

| Parameter | Default | Source |
|-----------|---------|--------|
| `dance_band_threshold_db` | -3.0 (UD-001 may adjust) | Phase 10.5 §E |
| `correction_step_hz` | 0.5 | Phase 10.5 §E |
| `region_max_hz` | per-region ceilings from BODY_REGIONS | Existing code |
| `max_correction_iterations` | 10 | Phase 10.5 §E |

**What must NOT change:**
- Stage 1 (velocity + z-score): KEEP_AS_IS
- Stage 2 (Hampel): KEEP_AS_IS
- Quaternion median filter: KEEP_AS_IS
- `src/filter_validation.py` PSD analysis functions: KEEP_AS_IS
- Existing Winter residual analysis (inner loop): KEEP_AS_IS — the outer loop wraps around it

**Files to change:**
- `src/filtering.py` — add outer PSD correction loop around `apply_signal_cleaning_pipeline()` or at the level where it is called
- `config/config_v1.yaml` — add `dance_band_threshold_db`, `correction_step_hz`, `max_correction_iterations`

**Full pre/post protocol (Phase 10.5 §E):**
1. Pre: All 001–014 complete; golden tests locked; UD-001 confirmed
2. Pre-implementation brief: expected changes, affected sessions, convergence criteria
3. Implementation: bounded addition to filtering.py
4. Post: regenerate ALL parquets; recompute ALL features; re-lock ALL golden tests
5. Validation: verify convergence for all sessions; no REVIEW_OVERSMOOTHING_UNRESOLVED

**Tests:**
- Unit: synthetic session with known oversmoothing → assert correction loop converges; assert psd_verdict = CORRECTED
- Unit: session already at target → assert loop exits after 0 iterations; assert minimal change
- Regression: ALL parquet changes documented (before/after diff for every session)

**Rollback:** Remove outer loop; restore previous golden checksums. Requires full parquet regen.
**Stop condition:** UD-001 confirmed; pre-impl brief approved; loop converges for all sessions; post-impl diff documented; new golden locked.

---

## User Decisions Required

| ID | Decision | Blocks | Status | Default |
|----|----------|--------|--------|---------|
| UD-001 | Dance-band threshold value | Ticket 015 | OPEN | -3.0 dB |
| UD-006 | Session label column names + value format | Ticket 004 | OPEN | Phase 10 names (`subject_id`, `timepoint`, `piece`, `rep`); abbreviated values (`651`, `T1`, `P2`, `R1`) |
| NEW-D1 | Ticket 011 Hampel column representation | Ticket 011 | DESIGN_DECISION_REQUIRED | Option B (single OR column) |
| UD-005 | Study N (N=2 or N=3) | Thesis release | OPEN | No Minimal v1 impact |

---

## Implementation Log Template

```markdown
# Ticket {NNN} Implementation Log

**Date:** YYYY-MM-DD
**Implementer:** [name or agent]
**Status:** IN_PROGRESS | COMPLETE | BLOCKED | ROLLED_BACK

## Pre-Implementation Statement

I have read:
- [ ] Ticket {NNN} spec in 12_implementation_backlog_CORRECTED.md
- [ ] All files listed in "Files to change"
- [ ] All prerequisite ticket implementation logs
- [ ] PROJECT_MEMORY_FOR_IMPLEMENTATION.md

I confirm:
- [ ] Prerequisite tickets are complete and regression-checked
- [ ] Golden parquet checksums frozen: [path/hash]
- [ ] Blast radius understood: [LOCAL / PARQUET_REGEN / MAXIMUM]
- [ ] I will not modify files not listed in the ticket spec

## Changes Made
| File | Change type | Description |
|------|-------------|-------------|

## Tests Run
| Test | Command | Result |
|------|---------|--------|

## Regression Comparison
**Before checksum:** [hash]
**After checksum:** [hash]
**Diff summary:** [unchanged / N rows changed / N columns added]

## Issues Encountered
[Any blockers or unexpected behaviors]

## Post-Implementation Sign-Off
- [ ] All tests pass
- [ ] Regression check passes
- [ ] Implementation log complete
```

---

## Rejected Items (DO_NOT_DO)

All items from Phase 10 REJECT_DO_NOT_ADOPT list remain rejected:
- Per-feature reliability columns in parquet
- QC plots for every PASS session
- Filter sensitivity analysis per session
- Cyclic anchor detection
- Numeric session_reliability_score
- Pose2Sim zero==missing convention
- scikit-kinematics quaternion convention
- Full gate chain S03–S06
- Per-joint {joint}__bone_qc_flag columns
- ref_is_fallback as per-row data column (Phase 12.5 M2)
- Quaternion diagnostics as per-row parquet columns (Phase 12.5 M4)
- Artifact-fraction-based adaptive control for Ticket 015 (Phase 12.5 M1)

## Deferred Items

All items from Phase 10 DEFER_POST_THESIS list remain deferred:
- PCHIP activation (pending 3 synthetic tests; Ticket 009 adds logging)
- SLERP activation (pending quaternion gap events)
- S02 velocity estimator upgrade (MAD dormant)
- S01 two-tier FAIL/SUSPICIOUS
- Full gate chain beyond S01
- NaN frame count logging at S04 input
- omega_method default change (rename function first)
- v2_longitudinal.py
- Day-level QC aggregation
- Forensic subsystem integration

---

## Implementation-Readiness Verdict

**VERDICT: IMPLEMENTATION-READY AFTER USER APPROVAL**

**Immediate blockers:**
1. User approves this corrected backlog
2. UD-006 resolved (before Ticket 004)
3. Golden parquet checksums frozen (before Ticket 001)

**Deferred blockers:**
4. NEW-D1 resolved (before Ticket 011)
5. UD-001 resolved (before Ticket 015)

**First ticket:** 001 (config snapshot)
**Last ticket:** 015 (PSD/dance-band correction loop)

**Implementation agent must read first:**
1. `PROJECT_MEMORY_FOR_IMPLEMENTATION.md`
2. This file (`12_implementation_backlog_CORRECTED.md`)
3. The specific ticket spec
4. Prerequisite implementation logs

---

*Phase 12 corrected backlog complete. Proceed to Phase 13 only after user approval.*
