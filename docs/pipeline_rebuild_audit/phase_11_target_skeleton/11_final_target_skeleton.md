# 11 Final Target Skeleton

**Date:** 2026-05-17
**Phase:** 11 — Final Target Skeleton
**Auditor:** Phase 11 Agent (Claude Sonnet 4.6)
**Mode:** Architecture-only. No code changes. No notebook edits. No file moves.
**Inputs:** `10_rewrite_decision_gate.md`, `10_keep_change_remove_decision_matrix.md`, `10_anti_overengineering_review.md`, `10.5_phase10_correction_notes.md`, `GAGA_PIPELINE_AGENT_WORK_PLAN.md`
**Supersedes:** `audit_outputs/03_target_skeleton_draft.md` (Phase 3 draft)

---

## Design Principles

These principles govern all decisions in this document:

1. **Evidence-first:** Every architectural decision traces back to observed session evidence (15 sessions, 2 subjects), not theoretical preference.
2. **Computation layer is sacred:** The algorithms are validated and correct. The infrastructure layer is what requires rebuilding.
3. **Sidecar-first QC:** `kinematics_master.parquet` stays numeric and ML-ready. QC summary metadata goes to PyArrow `schema.metadata`. Detailed QC goes to JSON/CSV sidecars.
4. **Minimal v1 scope is fixed:** 15 tickets, no more, no less. Any expansion requires explicit user approval with new evidence.
5. **Anti-overengineering:** Every item not in the 15-ticket set has an explicit "not now" rationale in Section 13.
6. **Reproducibility over convenience:** Config snapshots, stage JSONs, and version tags are mandatory, not optional.
7. **Notebook-friendly but not notebook-trapped:** Core logic lives in `src/`. Notebooks call src functions — they do not define authoritative computational logic.

---

## 1. Executive Verdict

**Strategy: `hybrid_modular_rebuild` — CONFIRMED**

Phase 10 recommended `hybrid_modular_rebuild`. This skeleton confirms that decision without modification.

**The evidence is clear:**

- All 25 validated algorithms in the computation chain are correct by external standards (Phase 4.5) and confirmed against all 15 sessions (Phases 5, 5.5, 6, 7).
- All 6 infrastructure gaps (config management, stage contracts, gate chain, metadata propagation, QC sidecars, method labeling) are absent or broken — confirmed consistently across all sessions, not from isolated anomalies.
- Dead session (651_T2_P2_R2, 5 frames, 0.03 s) passed all 6 pipeline stages silently — not a bug in one module, but the consequence of having no infrastructure layer.
- The pipeline's outputs are not wrong — they are unfinished at the infrastructure level.

**Alternative strategies are ruled out:**

| Alternative | Why ruled out |
|---|---|
| `targeted_fixes_only` | Patches symptoms; does not build the infrastructure layer that prevented these from being visible for 15 sessions |
| `full_rewrite_from_scratch` | Computation layer is correct; rewrite criteria from work plan §Phase 10 are not met; thesis timeline incompatible with baseline re-validation |
| `partial_stage_rebuild` | Misidentifies the problem; stage boundaries are correctly defined; infrastructure gaps span stages |

**Phase 10.5 correction applied:** The anti-overengineering review Executive Verdict erroneously states "13 core items." The correct count is **15 tickets** across 4 tiers. The four-tier structure is:
- Tier 1 (7): Data integrity
- Tier 2 (3): Methodology correctness
- Tier 3 (4): Traceability and QC
- Tier 4 (1): Algorithm fix

**Concise formulation:** The pipeline is not broken. It is unfinished. `hybrid_modular_rebuild` adds the provenance, safety, and QC metadata layers that transform a working research script into a thesis-grade, reproducible, auditable analysis pipeline — without touching what is already correct.

---

## 2. Final Target Architecture

```
[RAW DATA — OptiTrack CSV / C3D]
     │
     ▼
[FAST QC — src/fast_qc.py]
  Pre-pipeline check; T1-01 through T3-08
  HARD FAIL on duration < 30s; all else WARN
  Output: {RUN_ID}__fast_qc_report.json
     │
     ▼
[S00 CONFIG — run_pipeline.py + src/config.py]
  Per-run config snapshot written before any mutation
  pipeline_version injected into all downstream outputs
  Output: derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml
     │
     ▼
[S01 PARSE — src/preprocessing.py + src/pipeline.py]
  parse_optitrack_csv(); gate_01_status = FAIL if duration < 30s → STOP
  Output: S01 stage summary JSON (n_frames, duration, gate_01_status)
     │  (STOP if gate_01_status = FAIL)
     ▼
[S02 PREPROCESS — src/preprocessing.py]
  Artifact masking (np.interp linear + scalar quat normalize)
  Bone QC; corrected method labels
  Output: S02 stage summary JSON (bone_qc_status, artifact fractions)
     │
     ▼
[S03 RESAMPLE — src/resampling.py]
  CubicSpline (positions) + SciPy Slerp (quaternions)
  Frame count corrected (+1 frame fix)
  Output: resample_summary.json (n_frames_input, n_frames_output, time_grid_std)
     │
     ▼
[S04 FILTER — src/filtering.py + src/filter_validation.py]
  Stage 1: velocity + Z-score artifact detection (KEEP_AS_IS)
  Stage 2: Hampel 5-frame 3σ (KEEP_AS_IS; fix is_hampel_outlier propagation)
  Stage 3: Winter Butterworth + adaptive feedback loop [Ticket 015, last]
  Stage 4: quaternion median filter (KEEP_AS_IS)
  Output: filtering_summary.json (filter_psd_verdict, dance_band_status)
     │
     ▼
[S05 REFERENCE — src/reference.py + src/reference_validation.py]
  Markley quaternion mean; static window detection; 5-path fallback
  var_score guard (None, not Infinity); t_pose_failed guard (False, not None)
  Output: reference_metadata.json (ref_is_fallback, var_score, t_pose_failed)
     │
     ▼
[S06 KINEMATICS — src/angular_velocity.py, src/com_engine.py, src/euler_isb.py, ...]
  quat_log angular velocity; SavGol derivatives; ISB Euler; de Leva CoM
  Reads all stage JSONs at write time; aggregates QC metadata into parquet
  Quaternion diagnostic logging; is_hampel_outlier propagation
  Output: kinematics_master.parquet (schema v2.0)
         {RUN_ID}__validation_report.json (quaternion_diagnostics)
     │
     ▼
[QC SIDECAR — new generation function]
  Reads all stage JSONs; produces session_qc_report.json
  Output: {RUN_ID}__session_qc_report.json
     │
     ▼
[S11 FEATURE ENGINE — src/v2_feature_engine.py + src/pulsicity.py]
  NB11; 5 spec fixes; T1-anchored PCA; hard_exclude dead sessions
  Output: feature scalars per session; {RUN_ID}__feature_reliability_table.csv
     │
     ▼
[S08 ENGINEERING AUDIT — notebooks/08_engineering_physical_audit.ipynb]
  Engineering physical plausibility check; session count synced
```

**Two execution modes:**

| Mode | Entry point | Who uses it |
|---|---|---|
| Interactive | Notebooks NB01–NB11 | Researcher; step-by-step inspection and analysis |
| Batch | `run_pipeline.py` (project root) | Automated multi-session processing |

**Architectural rule:** The batch runner calls the same `src/` functions as the notebooks. Logic must live in `src/`. Notebooks are human-readable interfaces to `src/` functions — they must not define new computational logic that is not also available in batch mode.

---

## 3. Algorithm Preservation Decisions

**All 25 algorithms below must not be modified. Any change requires extraordinary evidence and explicit user approval before it enters any Phase 13 ticket.**

| Algorithm | Module | Evidence | What must not change |
|---|---|---|---|
| `parse_optitrack_csv()` | `src/preprocessing.py` | 51/51 joints, 0 NaN, 0 parse errors, all 15 sessions | Parsing, joint extraction, NaN detection |
| PCHIP gap fill (positions) | `src/gapfill_positions.py` | C1-continuous; 0 active gap events in 15 sessions; boundary bug at line 134 DEFERRED | Algorithm, API contract |
| SLERP quaternion gap fill | `src/gapfill_quaternions.py` | Never called in 15 sessions; placeholder implementation correct | Do not touch; do not call |
| CubicSpline resampling (positions) | `src/resampling.py` | C2-continuous; `time_grid_std = 0.0` | Interpolation method, continuity order |
| SciPy Slerp resampling (quaternions) | `src/resampling.py` | Geodesically correct; confirmed Phase 3 | SLERP path computation |
| Stage 1 velocity + Z-score artifact detection | `src/filtering.py` | 0.12% modification rate; surgical only | Detection thresholds, masking logic |
| Stage 2 Hampel filter (5-frame 3σ) | `src/filtering.py` | 0.09% modification rate; 42 ms window cannot distort dance dynamics | Window size (5 frames), sigma threshold (3) |
| Stage 3 Winter Butterworth (algorithm only) | `src/filtering.py` | Correct Butterworth per Winter 2009 | Filter coefficient computation, `filtfilt()` call |
| Stage 4 quaternion median filter | `src/filtering.py` | Hemisphere flip removal; geodesic error negligible | Window size, median computation |
| Markley quaternion mean (T-pose reference) | `src/reference.py` | Geodesic mean on S³; Markley et al. 2007 | Optimization algorithm |
| Static window fallback detection (5 paths) | `src/reference.py` | All 5 paths confirmed; 1 correctly triggered in 15 sessions | Fallback hierarchy |
| Root-relative position computation | `src/com_engine.py` / S06 | Correct by definition; Hips-zeroed | Subtraction logic |
| SavGol velocity/acceleration derivatives | `src/angular_velocity.py` | Standard for 120 Hz mocap | Window, polynomial order |
| `quat_log` angular velocity method | `src/angular_velocity.py` | Respects SO(3) manifold; standard in biomechanics | Default method selection |
| ISB Euler angles (Wu et al. 2005) | `src/euler_isb.py` | Correct joint-specific ZYX/XYZ sequences | Joint-specific rotation sequences |
| de Leva CoM model (1996) | `src/com_engine.py` | Standard 16-segment model | Segment fractions, landmark mapping |
| NaN Guard + Continuity enforcement | S06 | < 0.1% threshold; 0 NaN, 0 flips in all sessions | Guard thresholds |
| P2-only filter in v2_feature_engine | `src/v2_feature_engine.py` | Explicit gate confirmed; prevents session-type contamination | Filter logic |
| T1-anchored PCA | `src/v2_feature_engine.py` | Fit on T1, transform T2/T3; anti-double-dipping confirmed | Train/transform split |
| `pulsicity.compute_noise_floor` | `src/pulsicity.py` | `noise_floor_guard_mms=1.0` guard correct; interface confirmed | Parameter values, return contract |
| ATF NaN-safe computation | `src/v2_feature_engine.py` | `v_mag > V` check confirmed; Phase 7 confirmed | NaN guard logic |
| Contiguous-run TM path length | `src/v2_feature_engine.py` | Avoids artifact-masked discontinuities | Contiguous-run segmentation |
| D_eff participation ratio formula | `src/v2_feature_engine.py` | Poggio et al.; `epsilon_deff` guard confirmed | Formula, epsilon guard |
| Joint Gini (session-native; NOT standardized) | `src/v2_feature_engine.py` | StandardScaler must NOT be applied; confirmed | No scaling before Gini |
| T1-anchored Gini (frozen PCA loadings) | `src/v2_feature_engine.py` | Loadings frozen at T1; anti-double-dipping | Freezing mechanism |

**Three algorithm-level locked decisions (Phase 3 + Phase 4 confirmation):**
1. Do NOT adopt Pose2Sim `zero == missing` convention — zero is valid (Hips root = 0 by definition)
2. Do NOT switch `omega_method` to `5pt` as default — `finite_difference_5point()` is a weighted smoother, not a true 5-point stencil (Phase 4 confirmed); rename the function first, then reconsider default
3. Do NOT set `enforce_cleaning = true` as default — silent in-place SLERP-repair of critical frames violates ground truth integrity (LOCKED USER DIRECTIVE)

---

## 4. Stage-by-Stage Target Skeleton

### S00 — Configuration and Provenance

**Target responsibility:** Capture pipeline configuration state before any run; inject `pipeline_version` into all downstream outputs.

**Active files (verified):**
- `run_pipeline.py` (project root) — entry point; calls `update_config()` and all stages
- `src/config.py` — config loading
- `src/pipeline_config.py` — config schema

**Expected outputs (after Ticket 001):**
- `derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml` — full YAML snapshot written before any mutation

**Required metadata/logging:**
- Snapshot must contain full `config_v1.yaml` state at moment of run start
- `pipeline_version: "v4.0"` field added to `config_v1.yaml`
- `pipeline_version` propagated to parquet PyArrow metadata at S06 write time

**Gate behavior:** None — S00 is provenance only.

**Computation changes:** None. Pure infrastructure addition (~5 lines in `run_pipeline.py`).

**What must not change:** All existing config loading and update logic.

**Ticket:** 001

---

### Fast QC — Pre-Pipeline Quality Check

**Target responsibility:** Detect fatal data quality problems before any pipeline resources are spent. Operates on raw files.

**Active files (new file):**
- `src/fast_qc.py` — new; Phase 8 spec T1-01 through T3-08

**Expected outputs:**
- `{RUN_ID}__fast_qc_report.json` — per-session check results
- Console summary with PASS/WARN/FAIL per check

**Check categories (Phase 8 spec):**
- T1 (raw file validation): duration, frame count, sampling rate, joint completeness
- T2 (structural validation): marker gaps, continuity, metadata fields
- T3 (session-type-specific): T3-01 **INFO-only** (threshold uncalibrated per ADV-T3-01 DRAFT_PENDING_RESEARCH), T3-07 (Hips variance proxy), T3-08

**Gate behavior:**
- HARD FAIL on T1-01 (duration < 30s) — prevents wasted batch processing
- WARN on all other checks — informational; does not block pipeline
- T3-01 remains INFO-only until ≥15 session calibration is available

**Execution:** Callable standalone or triggered by `run_pipeline.py` as pre-flight check.

**Computation changes:** New file only. Does not modify any existing stage.

**Ticket:** 012

---

### S01 — Parse

**Target responsibility:** Load raw OptiTrack files, extract joint positions and quaternions, validate structure, apply minimum-session gate, emit stage summary JSON.

**Active files (verified — `src/parse.py` does not exist):**
- `src/preprocessing.py` — contains `parse_optitrack_csv()` definition (confirmed by grep)
- `src/pipeline.py` — imports `parse_optitrack_csv` from preprocessing; calls it at line 197
- `notebooks/01_Load_Inspect.ipynb` — interactive interface; calls S01 functions

**Expected outputs:**
- Parsed position array (frames × joints × 3), quaternion array (frames × joints × 4)
- S01 stage summary JSON with `gate_01_status` field (after Ticket 002)

**Gate behavior (after Ticket 002):**
- `gate_01_status = "PASS"` if duration ≥ 30 s (≥ 3,600 frames at 120 Hz)
- `gate_01_status = "FAIL"` if duration < 30 s — processing STOPS immediately; `run_pipeline.py` does not call S02
- This is the only pipeline gate for thesis scope (full gate chain deferred; see UD-003 and Section 13)

**Required metadata/logging:**
- `n_frames_parsed`, `n_joints_parsed`, `duration_s`, `gate_01_status`, `gate_01_reason`

**Computation changes:** None — `parse_optitrack_csv()` is KEEP_AS_IS.

**Infrastructure changes:** Add `gate_01_status` field to S01 stage summary JSON; `run_pipeline.py` reads this field and stops before S02 on FAIL.

**What must not change:** Parsing algorithm, joint extraction, NaN detection, quaternion loading.

**Ticket:** 002

---

### S02 — Preprocess

**Target responsibility:** Detect artifacts, apply artifact masking, run bone QC. Log method labels correctly.

**Active files (verified):**
- `src/preprocessing.py` — artifact detection, masking (`np.interp` linear for positions, scalar normalization for quaternions); contains Q-EXT1b label mismatch
- `src/gapfill_positions.py` — genuine PCHIP gap fill; NOT in active code path (0 gap fill events in 15 sessions)
- `src/gapfill_quaternions.py` — SLERP quaternion gap fill placeholder; NEVER called
- `src/qc.py` — one of three bone QC threshold systems (consolidation DEFERRED)
- `src/bone_length_validation.py` — bone length QC

**Two distinct code paths (Phase 10.5 Correction A — must not be conflated):**

| Code path | File | Actual method | Action |
|---|---|---|---|
| Artifact masking (positions) | `src/preprocessing.py` | `np.interp` (linear interpolation) — currently logged as `pchip_single_pass` (WRONG) | Fix label → `linear_interp` |
| Artifact masking (quaternions) | `src/preprocessing.py` | Scalar quaternion normalization — currently logged as `slerp` (WRONG) | Fix label → `quaternion_normalize` |
| True gap fill (positions) | `src/gapfill_positions.py` | Genuine PCHIP — correct and KEEP_AS_IS | Do not trigger; boundary bug at line 134 DEFERRED |
| True gap fill (quaternions) | `src/gapfill_quaternions.py` | SLERP placeholder — correct and KEEP_AS_IS | Never call; do not touch |

**Expected outputs:**
- Artifact-masked position and quaternion arrays
- S02 stage summary JSON with `bone_qc_status`, corrected method labels, artifact fractions

**Gate behavior:** No gate (S02 gate DEFERRED). `bone_qc_status` logged only.

**Computation changes:** None. Label string fix only (log field strings in `preprocessing.py`).

**What must not change:** `np.interp` masking logic, quaternion normalization, bone QC thresholds, PCHIP algorithm (untriggered), SLERP placeholder (untriggered).

**Tickets:** 009 (label fix), 007 (bone_qc_status propagated to parquet at S06 write time)

---

### S03 — Resample

**Target responsibility:** Normalize all sessions to a common 120 Hz temporal grid. Correct off-by-one frame drop. Log frame counts in/out.

**Active files (verified):**
- `src/resampling.py` — CubicSpline + SciPy Slerp; contains F-INT1 off-by-one in `n_target` formula

**Frame count fix (Ticket 003):**
- Current: `n_target = round(duration × fs)` — drops last frame silently (S01=16,915 → S04=16,914, universal)
- Fixed: `n_target = int(duration × fs) + 1`
- Impact: ALL session parquets must be regenerated; golden test frame counts change +1; must re-lock all golden tests

**Parquet regeneration protocol (required after Ticket 003):**
1. Implement fix; re-run all 15 live sessions (dead session excluded by gate_01_status FAIL from Ticket 002)
2. Verify each session: `n_frames_output_S03 = n_frames_S01`
3. Re-lock all golden session parquet fixtures (frame count assertion +1 from current values)
4. Re-compute feature scalars for affected sessions (ATF, TM are frame-count-sensitive)
5. Ticket 004 (ref_is_fallback) verification must be performed on corrected parquets

**Gate behavior:** None. Frame counts logged.

**Required metadata/logging:**
- `n_frames_input`, `n_frames_output`, `time_grid_std` (must = 0.0) — add to `resample_summary.json`

**Computation changes:** One formula change only. No other changes.

**What must not change:** CubicSpline algorithm, SciPy Slerp algorithm, temporal grid construction.

**Ticket:** 003

---

### S04 — Filter

**Target responsibility:** Apply the 4-stage filter chain. After Ticket 015, add adaptive Stage 3 feedback loop to correct universal oversmoothing.

**Active files (verified):**
- `src/filtering.py` — all 4 filter stages; Stage 3 is target for adaptive loop addition
- `src/filter_validation.py` — PSD validation; produces `REVIEW_OVERSMOOTHING` verdict

**Four-stage filter chain — status and action:**

| Stage | Algorithm | Status | Action |
|---|---|---|---|
| 1 — Velocity + Z-score | `filtering.py` Stage 1 | KEEP_AS_IS | NaN logging deferred (0 NaN in all sessions) |
| 2 — Hampel (5-frame 3σ) | `filtering.py` Stage 2 | KEEP_AS_IS algorithm | Fix is_hampel_outlier propagation (Ticket 011) |
| 3 — Winter Butterworth | `filtering.py` Stage 3 | KEEP algorithm; ADD adaptive loop | Ticket 015 (last) |
| 4 — Quaternion median | `filtering.py` Stage 4 | KEEP_AS_IS | No changes |

**Current oversmoothing finding:** ALL 57 position columns flagged `REVIEW_OVERSMOOTHING`. Mean dance-band attenuation -4.68 to -5.51 dB (Phase 4). All thesis features affected.

**Gate behavior:** No S04 gate (deferred). `filter_psd_verdict` logged and propagated to parquet.

**Required metadata/logging:**
- `filter_psd_verdict` — in `filtering_summary.json`; propagated to parquet metadata at S06 write time (Ticket 007)
- `dance_band_status` per session after adaptive loop is active (Ticket 015)
- `is_hampel_outlier` per-frame column correctly populated in parquet (Ticket 011)

**Ticket 015 — Adaptive Dance-Band Correction Loop:**

Implementation scope: bounded addition inside `src/filtering.py` Stage 3, around the existing `filtfilt()` call. Does NOT restructure the file or stage.

Algorithm (per Phase 3 §S-04.3):
1. After `filtfilt()` at current cutoff, measure dance-band delta dB
2. If delta < threshold (-3 dB default): raise cutoff by step (0.5 Hz), refilter
3. Repeat until delta ≥ threshold OR cutoff ≥ regional ceiling OR max iterations (10) reached
4. Log `dance_band_status`: `PASS` / `CORRECTED` / `UNRESOLVED_AT_CEILING`

Config parameters to expose in `config_v1.yaml` (new fields):
- `dance_band_threshold_db` (default: -3.0)
- `correction_step_hz` (default: 0.5)
- `region_max_hz` (per-region ceilings; existing fields)
- `max_correction_iterations` (default: 10)

**Blast radius of Ticket 015 (per Phase 10.5 Correction B — authoritative framing):**
Implementation scope = `LOCAL_REFACTOR` (bounded addition inside filtering.py).
Scientific blast radius = MAXIMUM among all 15 tickets: ALL session parquets regenerated; ALL thesis feature values (ATF, TM, D_eff, Gini) change; ALL golden regression tests must be re-locked.

**Ordering:** Ticket 015 is LAST. Must be implemented after Tickets 001–014 are implemented, verified, and golden tests are re-locked on the pre-adaptive-loop baseline.

**Ticket 015 pre/post protocol:**
- Pre-condition: Tickets 001–014 implemented and verified; golden tests re-locked on pre-loop baseline; one clean parquet set archived as regression reference
- Implementation: Ticket 015 code change in `src/filtering.py`
- Post: Regenerate ALL session parquets → re-compute ALL feature scalars → re-lock ALL golden tests
- Validation: Verify `dance_band_status = PASS or CORRECTED` for all sessions; verify no `REVIEW_OVERSMOOTHING_UNRESOLVED` before accepting as new baseline

**Note on Ticket 003 / Ticket 015 ordering:** Both tickets trigger full parquet regeneration. They must be implemented and validated SEQUENTIALLY — do not overlap.

**What must not change:** Stage 1 detection logic, Stage 2 Hampel window and sigma, Stage 3 filtfilt algorithm, Stage 4 quaternion median.

**Tickets:** 011 (is_hampel_outlier propagation), 007 (filter_psd_verdict → parquet), 015 (adaptive loop — last)

---

### S05 — Reference Detection

**Target responsibility:** Detect T-pose reference window using Markley quaternion mean. Apply fallback if primary fails. Guard against invalid JSON for dead sessions.

**Active files (verified):**
- `src/reference.py` — Markley mean, static window detection, fallback; contains F-651-2 (`var_score = Infinity`) and F-651-5 (`t_pose_failed = None`) bugs
- `src/reference_validation.py` — reference quality validation; contains F7-4 threshold bug (0.30 → 0.20)

**Bug fixes required:**

| Bug | Problem | Fix | Ticket |
|---|---|---|---|
| F-651-2 | `var_score = Infinity` for dead session — invalid JSON | Guard: `if n_frames == 0: var_score = None` | 005 |
| F-651-5 | `t_pose_failed = null` (None) for fallback — gate logic misses it | Set `t_pose_failed = False` explicitly for non-identity fallbacks | 005 |
| F7-4 | `validate_reference()` threshold 0.30 vs spec 0.20 | Change constant to 0.20 | 008 |

**Gate behavior:** No hard gate for S05 (thesis scope; only S01 gate active). `ref_is_fallback` logged and propagated.

**Required metadata/logging:**
- `ref_is_fallback` (bool) — propagated to parquet at S06 write time (Ticket 004)
- `var_score` (float or None, never Infinity)
- `t_pose_failed` (bool, never None)
- `reference_window_frames` (start, end frame indices)

**Computation changes:** None — Markley mean algorithm and fallback hierarchy are KEEP_AS_IS. Only guard conditions added.

**What must not change:** Markley quaternion mean algorithm, static window detection, fallback hierarchy.

**Tickets:** 005 (var_score + t_pose_failed guards), 008 (threshold fix)

---

### S06 — Kinematics

**Target responsibility:** Compute full kinematic state; write `kinematics_master.parquet` schema v2.0; aggregate QC metadata from all stages; write quaternion diagnostic log.

**Active files (verified):**
- `src/angular_velocity.py` — `quat_log` and `finite_difference_5point` (weighted smoother); quaternion diagnostics
- `src/com_engine.py` — de Leva CoM
- `src/euler_isb.py` — ISB Euler angles (Wu 2005)
- `src/skeleton_defs.py` — canonical skeleton hierarchy
- `src/quaternion_ops.py` — quaternion math
- `src/quaternion_normalization.py` — renormalization
- `src/quaternions.py` — quaternion utilities
- `src/qc_columns.py` — QC column definitions
- `src/kinematics_alignment.py` — kinematics alignment
- `src/kinematic_repair.py` — SLERP/PCHIP surgical repair; NOT called in default runs (`enforce_cleaning = false`)
- `src/coordinate_systems.py` — coordinate system transforms
- `notebooks/06_ultimate_kinematics.ipynb` — interactive interface

**Expected outputs:**
- `kinematics_master.parquet` — schema v2.0 (803 existing + 4 data cols + 5 metadata fields)
- `{RUN_ID}__validation_report.json` — quaternion diagnostics under `quaternion_diagnostics` key

**New parquet metadata fields — read from prior stage JSONs at S06 write time:**

| Field | Source JSON | Ticket |
|---|---|---|
| `ref_is_fallback` | S05 `reference_metadata.json` | 004 |
| `filter_psd_verdict` | S04 `filtering_summary.json` | 007 |
| `bone_qc_status` | S02 stage summary JSON | 007 |
| `gate_01_status` | S01 stage summary JSON | 007 (requires Ticket 002 to exist first) |
| `pipeline_version` | config snapshot | 007 (bundle with Ticket 001) |

**New per-row data columns — parsed from run_id at S06 write time:**

| Column | Type | Source | Ticket |
|---|---|---|---|
| `subject_id` | str | run_id | 004 |
| `timepoint` | str | run_id | 004 |
| `piece` | str | run_id | 004 |
| `rep` | str | run_id | 004 |

Note: naming convention (abbreviated vs. expanded) requires user confirmation — see UD-006.

**Quaternion diagnostic logging (expanded per Phase 10.5 Clarification A):**

Written to `{RUN_ID}__validation_report.json` under key `quaternion_diagnostics`. LOGGING_ONLY — no computation changes.

| Diagnostic | What to log |
|---|---|
| Pre-renormalization norm deviation | Per-joint: mean, max, p99 of `|‖q‖ − 1|` before any renormalization |
| Post-SavGol norm status | Per-joint: max norm deviation after SavGol smoothing |
| Renormalization burden | Per-joint: count of frames where `|‖q‖ − 1| > 0.05` |
| Hemisphere/sign continuity | Per-joint: count of flips detected and corrected |
| SavGol norm impact | Per-joint: max norm deviation introduced by SavGol smoothing |

Warning threshold: log WARNING if >5% of frames per joint require renormalization.

Purpose statement (must appear in implementation comments): *"These diagnostic logs produce sufficient evidence to decide post-thesis whether SO(3)-aware smoothing is warranted, without changing any default behavior."*

**Gate behavior:** No hard gate on quaternion norm (could fail clean sessions). S06 always completes; all issues are logged.

**Computation changes:** None. All algorithms KEEP_AS_IS.

**Infrastructure changes:** Read stage JSONs at parquet write time; add 5 metadata fields + 4 data columns; quaternion diagnostic logging; is_hampel_outlier propagation.

**What must not change:** `quat_log` default, SavGol parameters, ISB Euler sequences, de Leva fractions, NaN guard thresholds, continuity enforcement, `enforce_cleaning = false`.

**Tickets:** 004 (ref_is_fallback + session labels), 007 (filter_psd_verdict + bone_qc_status + gate_01_status + pipeline_version), 011 (is_hampel_outlier propagation investigation + fix)

---

### S08 — Engineering Physical Audit

**Target responsibility:** Post-pipeline engineering validation of physical plausibility, session counts, and distribution of QC verdicts.

**Active files:**
- `notebooks/08_engineering_physical_audit.ipynb` — active; needs session count sync

**Current problem:** NB08 references 16 runs but only 9 derivatives exist.

**Fix:** Update NB08 to read current derivatives directory at runtime. No algorithm change. No papermill parameterization (deferred).

**What must not change:** Physical audit logic, plausibility thresholds.

**Ticket:** 013

---

### S11 — Feature Engine

**Target responsibility:** Extract all thesis features from `kinematics_master.parquet`. Apply T1-anchored PCA. Hard-exclude dead sessions. Fix 5 spec deviations.

**Active files (verified):**
- `src/v2_feature_engine.py` — contains 5 spec deviations requiring fixes
- `src/pulsicity.py` — ATF computation; KEEP_AS_IS
- `notebooks/11_METH_SPEC_v2_Features.ipynb` — interactive interface

**Five spec deviations requiring fixes:**

| Deviation | Current | Spec | Ticket |
|---|---|---|---|
| Artifact fraction computation | `max(joint_art_rates)` | `1.0 - clean_fraction_pca` (OR-union) | 008 |
| Reference quality threshold | 0.30 | 0.20 | 008 (also in reference_validation.py) |
| Dead session classification | `short_session=True` | `hard_exclude=True` | 006 |
| Hips in ATF_axial joint group | Included (ATF_axial biased downward permanently) | Exclude Hips | 010 |
| METHODOLOGY_SPEC_v2.md §ATF_axial | Hips listed in axial group | Amend spec to exclude Hips explicitly | 010 |

**What must not change:** PCA architecture, P2-only filter, pulsicity interface, ATF NaN-safe computation, contiguous-run TM, D_eff formula, Gini (no StandardScaler), T1-anchored Gini, `noise_floor_guard_mms=1.0`.

**Tickets:** 006 (hard_exclude), 008 (artifact fraction + reference threshold), 010 (Hips fix + spec amendment)

---

### Post-Pipeline — QC Sidecar Generation

**Target responsibility:** Aggregate all stage QC signals into human-readable sidecars for thesis reviewers and downstream analysis.

**New files (Ticket 014):**
- `{RUN_ID}__session_qc_report.json` — generated after S06 completes; reads all stage JSONs
- `{RUN_ID}__feature_reliability_table.csv` — generated after v2_feature_engine completes

**Timing (UD-004 default):** Two separate generation steps. `session_qc_report.json` at end of pipeline run; `feature_reliability_table.csv` at end of feature engine run.

**`session_qc_report.json` schema:**
```json
{
  "run_id": "...",
  "pipeline_version": "v4.0",
  "gate_01_status": "PASS|FAIL",
  "duration_s": 0.0,
  "n_frames": 0,
  "bone_qc_status": "PASS|WARN|FAIL",
  "filter_psd_verdict": "PASS|REVIEW_OVERSMOOTHING",
  "dance_band_status": "PASS|CORRECTED|UNRESOLVED_AT_CEILING",
  "ref_is_fallback": false,
  "t_pose_failed": false,
  "artifact_fraction_positions": 0.0,
  "artifact_fraction_quaternions": 0.0,
  "session_verdict": "PASS|WARN|FAIL",
  "warn_reasons": [],
  "quaternion_diagnostics": {
    "{joint}__renorm_burden_pct": 0.0,
    "{joint}__max_norm_dev": 0.0,
    "hemisphere_flips_detected": 0
  }
}
```

**`feature_reliability_table.csv` schema:**

| Column | Type | Notes |
|---|---|---|
| `feature_name` | str | e.g., `ATF_axial`, `TM`, `D_eff` |
| `n_sessions_computed` | int | Sessions where feature was successfully computed |
| `n_sessions_excluded` | int | Sessions excluded (hard_exclude or dead session) |
| `exclusion_reasons` | str | Comma-separated reasons |
| `distribution_verdict` | str | `PASS` / `WARN` / `FAIL` |

Note: Categorical labels only — no numeric `session_reliability_score` (rejected; see Section 13).

**Ticket:** 014

---

## 5. Repository Architecture and Cleanup Plan

**Phase 11 classifies files — it does NOT move or delete them. File moves happen in Phase 13 with explicit per-file user approval.**

**Classification key:**
- `ACTIVE_PIPELINE` — called in the main pipeline sequence
- `ACTIVE_DOWNSTREAM` — called by feature engine or analysis notebooks
- `ACTIVE_SUPPORT` — utility/config used by multiple modules
- `DEPENDENCY_UNVERIFIED` — not yet confirmed as active or legacy; must verify before any ticket touches adjacent code
- `LEGACY_ARCHIVE_CANDIDATE` — confirmed unused or superseded; archive in Phase 13 with user approval
- `ALREADY_ARCHIVED` — already in `legacy/`

### Source Modules (`src/`)

| File | Classification | Stage | Notes |
|---|---|---|---|
| `src/preprocessing.py` | `ACTIVE_PIPELINE` | S01, S02 | Defines `parse_optitrack_csv()`; contains Q-EXT1b label mismatch (Ticket 009) |
| `src/gapfill_positions.py` | `ACTIVE_PIPELINE` | S02 | Genuine PCHIP; never triggered; boundary bug line 134 DEFERRED |
| `src/gapfill_quaternions.py` | `ACTIVE_PIPELINE` | S02 | SLERP placeholder; never called; KEEP_AS_IS |
| `src/resampling.py` | `ACTIVE_PIPELINE` | S03 | Contains F-INT1 off-by-one (Ticket 003) |
| `src/filtering.py` | `ACTIVE_PIPELINE` | S04 | 4 filter stages; target for Ticket 015 adaptive loop |
| `src/filter_validation.py` | `ACTIVE_PIPELINE` | S04 | PSD validation; REVIEW_OVERSMOOTHING verdict |
| `src/reference.py` | `ACTIVE_PIPELINE` | S05 | Markley mean; fallback detection; bugs F-651-2, F-651-5 (Ticket 005) |
| `src/reference_validation.py` | `ACTIVE_PIPELINE` | S05 | Threshold bug F7-4 (Ticket 008) |
| `src/angular_velocity.py` | `ACTIVE_PIPELINE` | S06 | `quat_log`; `finite_difference_5point` (mislabeled smoother) |
| `src/com_engine.py` | `ACTIVE_PIPELINE` | S06 | de Leva CoM |
| `src/euler_isb.py` | `ACTIVE_PIPELINE` | S06 | ISB Euler (Wu 2005) |
| `src/skeleton_defs.py` | `ACTIVE_PIPELINE` | S06 | Canonical skeleton |
| `src/quaternion_ops.py` | `ACTIVE_PIPELINE` | S06 | Quaternion math |
| `src/quaternion_normalization.py` | `ACTIVE_PIPELINE` | S06 | Renormalization |
| `src/quaternions.py` | `ACTIVE_PIPELINE` | S06 | Quaternion utilities |
| `src/qc_columns.py` | `ACTIVE_PIPELINE` | S06 | QC column definitions |
| `src/kinematics_alignment.py` | `ACTIVE_PIPELINE` | S06 | Kinematics alignment |
| `src/kinematic_repair.py` | `ACTIVE_PIPELINE` | S06 | SLERP/PCHIP surgical repair; not called in default runs |
| `src/pulsicity.py` | `ACTIVE_DOWNSTREAM` | S11 | ATF; KEEP_AS_IS |
| `src/v2_feature_engine.py` | `ACTIVE_DOWNSTREAM` | S11 | 5 spec fixes required |
| `src/config.py` | `ACTIVE_SUPPORT` | S00 | Config loading |
| `src/pipeline_config.py` | `ACTIVE_SUPPORT` | S00 | Config schema |
| `src/pipeline.py` | `ACTIVE_SUPPORT` | All | Stage orchestration; imports `parse_optitrack_csv` from preprocessing |
| `src/utils.py` | `ACTIVE_SUPPORT` | All | General utilities |
| `src/qc.py` | `ACTIVE_SUPPORT` | S02 | One of three bone QC systems; consolidation DEFERRED |
| `src/bone_length_validation.py` | `ACTIVE_SUPPORT` | S02 | Bone length QC |
| `src/__init__.py` | `ACTIVE_SUPPORT` | All | Package init |
| `src/units.py` | `ACTIVE_SUPPORT` | All | Unit conversions |
| `src/validation.py` | `ACTIVE_SUPPORT` | Multiple | General validation |
| `src/artifact_validation.py` | `ACTIVE_SUPPORT` | S02, S04 | Artifact validation |
| `src/artifacts.py` | `ACTIVE_SUPPORT` | S02 | Artifact definitions |
| `src/coordinate_systems.py` | `ACTIVE_SUPPORT` | S06 | Coordinate transforms |
| `src/export_tables.py` | `ACTIVE_SUPPORT` | S06, S11 | Table export |
| `src/filter_export.py` | `ACTIVE_SUPPORT` | S04 | Filter result export |
| `src/joint_statistics.py` | `ACTIVE_SUPPORT` | S06, S11 | Joint statistics |
| `src/sg_filter_validation.py` | `ACTIVE_SUPPORT` | S06 | SavGol validation |
| `src/snr_analysis.py` | `ACTIVE_SUPPORT` | S04, S06 | SNR analysis |
| `src/subject_validation.py` | `ACTIVE_SUPPORT` | All | Subject-level validation |
| `src/time_alignment.py` | `ACTIVE_SUPPORT` | S03 | Temporal alignment |
| `src/winter_export.py` | `ACTIVE_SUPPORT` | S04 | Winter filter export |
| `src/utils_nb07.py` | `ACTIVE_SUPPORT` | NB07 | NB07-specific utilities |
| `src/calibration.py` | `ACTIVE_SUPPORT` | S00, S01 | Calibration loading |
| `src/forensic_report.py` | `DEPENDENCY_UNVERIFIED` | S08? | One of three bone QC systems; may be called from NB08; verify before any cleanup |
| `src/forensic_config.py` | `DEPENDENCY_UNVERIFIED` | S08? | May be dependency of forensic_report.py |
| `src/forensic_plots.py` | `DEPENDENCY_UNVERIFIED` | S08? | May be dependency of forensic_report.py |
| `src/_run_forensic_batch.py` | `DEPENDENCY_UNVERIFIED` | S08? | Batch runner; may be used by NB08 |
| `src/burst_classification.py` | `DEPENDENCY_UNVERIFIED` | Unknown | Unknown active usage |
| `src/interactive_viz.py` | `DEPENDENCY_UNVERIFIED` | NB09? | Legacy visualization; may be from NB09 |
| `src/lcs_visualization.py` | `DEPENDENCY_UNVERIFIED` | NB06? | LCS visualization; may be active in NB06 |
| `src/gate_integration.py` | `DEPENDENCY_UNVERIFIED` | Unknown | Gate integration module; unclear if active |
| `src/interpolation_logger.py` | `DEPENDENCY_UNVERIFIED` | S02? | May be called from preprocessing.py |
| `src/interpolation_tracking.py` | `DEPENDENCY_UNVERIFIED` | S02? | May overlap with interpolation_logger.py |
| `src/init.py` | `DEPENDENCY_UNVERIFIED` | All | Possible duplicate of `src/__init__.py`; verify |

**Dependency verification requirement for all `DEPENDENCY_UNVERIFIED` files:**
Before any Phase 13 cleanup action: (1) grep for import statements across all notebooks and src files; (2) identify call site or confirm orphaned; (3) if orphaned, present to user for archival decision. Do not mark any file as `LEGACY_ARCHIVE_CANDIDATE` without this check.

### Notebooks (`notebooks/`)

| Notebook | Classification | Stage | Notes |
|---|---|---|---|
| `notebooks/00_setup.ipynb` | `ACTIVE_PIPELINE` | S00 | Environment setup |
| `notebooks/01_Load_Inspect.ipynb` | `ACTIVE_PIPELINE` | S01 | Calls `parse_optitrack_csv()` from src/preprocessing.py |
| `notebooks/02_preprocess.ipynb` | `ACTIVE_PIPELINE` | S02 | Artifact masking, bone QC |
| `notebooks/03_resample.ipynb` | `ACTIVE_PIPELINE` | S03 | Resampling |
| `notebooks/04_filtering.ipynb` | `ACTIVE_PIPELINE` | S04 | Filtering |
| `notebooks/05_reference_detection.ipynb` | `ACTIVE_PIPELINE` | S05 | Reference detection |
| `notebooks/06_ultimate_kinematics.ipynb` | `ACTIVE_PIPELINE` | S06 | Kinematics master computation; produces parquet |
| `notebooks/08_engineering_physical_audit.ipynb` | `ACTIVE_DOWNSTREAM` | S08 | Engineering audit; Ticket 013 session count sync |
| `notebooks/11_METH_SPEC_v2_Features.ipynb` | `ACTIVE_DOWNSTREAM` | S11 | Thesis feature extraction |
| `notebooks/qa_master_pipeline_validation.ipynb` | `DEPENDENCY_UNVERIFIED` | QA | Status unclear; verify before any action |
| `notebooks/07_pulsicity_flow.ipynb` | `LEGACY_ARCHIVE_CANDIDATE` | — | Pulsicity archived; algorithms preserved in FUTURE_FEATURES_SALVAGE.md; verify no active imports before archiving |
| `notebooks/09_Subject_Exploration_Dashboard.ipynb` | `LEGACY_ARCHIVE_CANDIDATE` | — | Legacy dashboard; designs preserved; verify no active imports |
| `notebooks/10_EDA_PCA.ipynb` | `LEGACY_ARCHIVE_CANDIDATE` | — | Broken import (`from legacy.EDA_PCA import`); math preserved; add deprecation header (Q8) before archiving |

**Already archived:**
- `legacy/core_kinematics_engine.py`
- `legacy/EDA_PCA.py`
- Other files in `legacy/` directory — must not be revived without explicit user decision

---

## 6. Notebook Strategy

**Active user-facing interfaces (must remain functional):**
- NB01–NB06: Primary pipeline sequence; one per stage; researcher runs interactively for inspection
- NB11: Thesis feature extraction; analytical output; must implement spec exactly

**Production-critical (must work correctly for thesis):**
- NB06 (`06_ultimate_kinematics.ipynb`) — produces `kinematics_master.parquet`; must stay tightly coupled to `src/` functions
- NB11 (`11_METH_SPEC_v2_Features.ipynb`) — produces thesis features; must implement METHODOLOGY_SPEC_v2.md exactly

**QA/reporting only:**
- NB08 (`08_engineering_physical_audit.ipynb`) — engineering validation; not in primary analysis path; needs session count fix (Ticket 013)
- `qa_master_pipeline_validation.ipynb` — status DEPENDENCY_UNVERIFIED; do not touch until verified

**Legacy/archive candidates (do not move in Phase 11; archive in Phase 13 with user approval):**
- NB07 (`07_pulsicity_flow.ipynb`) — pulsicity archived; archive after confirming no imports
- NB09 (`09_Subject_Exploration_Dashboard.ipynb`) — legacy dashboard; archive after confirming no imports
- NB10 (`10_EDA_PCA.ipynb`) — broken import; add deprecation header; archive after header added

**Key architectural rule:** Logic that produces thesis outputs or is called by the batch runner MUST live in `src/`. Notebooks call `src/` functions; they must not define new computational logic that bypasses batch execution. This rule must be enforced in Phase 13 ticket reviews.

---

## 7. Three-Layer QC Architecture

### Layer 1 — Fast Post-Collection QC

- **Implementation:** `src/fast_qc.py` (new; Ticket 012)
- **Timing:** Before any pipeline stage; as soon as raw files are available
- **Scope:** T1-01 through T3-08; T3-01 INFO-only until calibrated
- **Output:** `{RUN_ID}__fast_qc_report.json`
- **Purpose:** Catch fatal recording problems before expensive pipeline processing

### Layer 2 — Pipeline Processing QC

- **Implementation:** Stage summary JSONs produced by S01–S06
- **Scope:** `gate_01_status`, `bone_qc_status`, `filter_psd_verdict`, `dance_band_status`, `ref_is_fallback`, quaternion diagnostics, frame counts
- **Aggregation:** `{RUN_ID}__session_qc_report.json` sidecar generated at end of pipeline run (Ticket 014)
- **Purpose:** Full traceability for every session's processing quality

### Layer 3 — Final Feature QC

- **Implementation:** Post-feature-engine sidecar generation (Ticket 014)
- **Scope:** Feature completeness, hard-exclude flags, session-level feature availability
- **Output:** `{RUN_ID}__feature_reliability_table.csv`
- **Purpose:** Allow thesis reviewers to identify which sessions contributed to each feature

**Integration principle:** The three layers are independent and do not gate each other for thesis scope. Layer 1 FAIL prevents batch processing. Layer 2 WARN propagates to parquet metadata and session_qc_report.json. Layer 3 WARN propagates to sidecar only. The parquet stays clean and numeric.

---

## 8. kinematics_master.parquet and Sidecar Contract

### Schema v2.0

**Existing schema (v1.x — KEEP_AS_IS):**
- 803 kinematic feature columns (all per-frame joint data)
- RangeIndex (no session labels as data columns yet)
- No PyArrow `schema.metadata` QC fields yet

**New per-row data columns (4 additions — Ticket 004):**

| Column | Type | Source | Naming decision |
|---|---|---|---|
| `subject_id` | str | parsed from run_id | `651` vs `Subject_651` — USER DECISION REQUIRED (UD-006) |
| `timepoint` | str | parsed from run_id | `T1` vs `1` — USER DECISION REQUIRED |
| `piece` | str | parsed from run_id | `P2` vs `2` — USER DECISION REQUIRED |
| `rep` | str | parsed from run_id | `R1` vs `1` — USER DECISION REQUIRED |

**New PyArrow schema.metadata fields (5 additions — Tickets 001, 004, 007):**

| Field | Type | Source | Ticket |
|---|---|---|---|
| `ref_is_fallback` | bool | S05 `reference_metadata.json` | 004 |
| `filter_psd_verdict` | str | S04 `filtering_summary.json` | 007 |
| `pipeline_version` | str | config snapshot | 001 (bundle with 007) |
| `gate_01_status` | str | S01 stage summary JSON | 007 (requires Ticket 002) |
| `bone_qc_status` | str | S02 stage summary JSON | 007 (bundle) |

**Total schema v2.0:** 807 per-row data columns + 5 metadata fields.

**Schema version tag:** `pipeline_version = "v4.0"` stored in `config_v1.yaml` and propagated to parquet metadata at S06 write time (Ticket 001).

### Sidecar-First Policy (CONFIRMED)

**What belongs in parquet:**
- All 803 kinematic feature columns (per-frame numeric data)
- 4 per-row session label columns (`subject_id`, `timepoint`, `piece`, `rep`)
- 1 per-row QC flag column (`is_hampel_outlier` — corrected by Ticket 011)
- 5 PyArrow metadata fields (summary provenance and QC signals)

**What belongs in sidecars — not parquet:**
- `{RUN_ID}__fast_qc_report.json` — pre-pipeline raw data check
- `{RUN_ID}__config_snapshot.yaml` — config provenance
- Stage-level JSONs (S01–S06, already existing)
- `{RUN_ID}__session_qc_report.json` — full pipeline QC summary
- `{RUN_ID}__validation_report.json` — quaternion diagnostics
- `{RUN_ID}__feature_reliability_table.csv` — feature-level QC

### Rejected Parquet Additions

| Item | Reason |
|---|---|
| `{joint}__bone_qc_flag` per-frame columns | Constant columns; no information content; use `bone_qc_status` metadata field |
| `{feature}__reliability` per-feature columns | Schema bloat (803 → 1000+); destroys ML/DL readiness; use sidecar |
| `session_reliability_score` numeric | Not calibrated; categorical PASS/WARN/FAIL is safer and sufficient |
| Per-stage `n_nan_frames` columns | All 15 sessions = 0; premature infrastructure |

---

## 9. Stage JSON / Metadata Contracts

### S01 Stage Summary JSON (required fields after Ticket 002)
```json
{
  "stage": "S01",
  "run_id": "...",
  "pipeline_version": "...",
  "n_frames_parsed": 0,
  "n_joints_parsed": 51,
  "duration_s": 0.0,
  "gate_01_status": "PASS|FAIL",
  "gate_01_reason": "..."
}
```

### S02 Stage Summary JSON (required fields after Ticket 009)
```json
{
  "stage": "S02",
  "run_id": "...",
  "artifact_fraction_positions": 0.0,
  "artifact_fraction_quaternions": 0.0,
  "interpolation_method": "linear_interp",
  "quaternion_repair_method": "quaternion_normalize",
  "bone_qc_status": "PASS|WARN|FAIL",
  "bone_qc_details": {}
}
```

### S03 Resample Summary JSON (required fields after Ticket 003)
```json
{
  "stage": "S03",
  "run_id": "...",
  "n_frames_input": 0,
  "n_frames_output": 0,
  "time_grid_std": 0.0,
  "resample_rate_hz": 120
}
```

### S04 Filtering Summary JSON (required fields after Tickets 007 and 015)
```json
{
  "stage": "S04",
  "run_id": "...",
  "filter_psd_verdict": "PASS|REVIEW_OVERSMOOTHING",
  "dance_band_status": "PASS|CORRECTED|UNRESOLVED_AT_CEILING",
  "dance_band_delta_db_mean": 0.0,
  "cutoff_hz_final": 0.0,
  "n_correction_iterations": 0,
  "n_nan_frames_at_filter_input": 0
}
```

### S05 Reference Metadata JSON (required fields after Ticket 005)
```json
{
  "stage": "S05",
  "run_id": "...",
  "ref_is_fallback": false,
  "var_score": 0.0,
  "t_pose_failed": false,
  "reference_window_frames": [0, 0],
  "fallback_path_used": "none|..."
}
```

### S06 Validation Report JSON (expanded — quaternion diagnostics section added in Ticket 007)
```json
{
  "stage": "S06",
  "run_id": "...",
  "n_frames_final": 0,
  "session_verdict": "PASS|WARN|FAIL",
  "quaternion_diagnostics": {
    "{joint}__renorm_burden_pct": 0.0,
    "{joint}__max_norm_dev_pre_savgol": 0.0,
    "{joint}__max_norm_dev_post_savgol": 0.0,
    "hemisphere_flips_detected": 0,
    "joints_exceeding_renorm_threshold": []
  }
}
```

### Config Snapshot Contract
Written to `derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml` before any run starts.
- Contains the full state of `config_v1.yaml` at run start time
- Must include `pipeline_version: "v4.0"` (new field added by Ticket 001)
- Immutable after writing — never modified during a run

---

## 10. Rotation / Quaternion Diagnostics

**Decision: `LOGGING_ONLY` (expanded scope per Phase 10.5 Clarification A)**

**What is added:**
Quaternion diagnostic fields added to `{RUN_ID}__validation_report.json` under key `quaternion_diagnostics`. Bundled into Ticket 007 (or as a standalone LOGGING_ONLY sub-ticket if scope warrants). Full field specification in Section 9 (S06 Validation Report JSON schema above).

**What must NOT change:**
- `quat_log` remains the default angular velocity method — confirmed correct
- Do NOT switch `omega_method` to `5pt` as default — `finite_difference_5point()` is a weighted smoother, not a true 5-point stencil (Phase 4 confirmed); rename the function first (DEFERRED), then reconsider default
- Do NOT add a hard gate on quaternion norm — could fail clean sessions
- Do NOT implement SO(3)-aware smoothing (geodesic SavGol) — future v2 candidate; requires diagnostic evidence first

**How the logs support a future SO(3) decision:**
After Ticket 007 logs are collected across all 15 sessions, renormalization burden data will reveal whether any joints show systematically high correction demand (>5% of frames, `|‖q‖ − 1| > 0.05`). If yes, this is the prerequisite evidence for proposing geodesic SavGol smoothing as a post-thesis feature. If no joint exceeds the threshold, the diagnostic confirms the current approach is adequate.

**Key reminder:** Do not confuse the two `omega_method` options:
- `quat_log` — correct; respects SO(3); current default; do not change
- `finite_difference_5point()` — a weighted smoother (not a true 5-point stencil); do not use as default until renamed

---

## 11. Filtering Policy

**Four-stage filter chain — policy per stage:**

| Stage | Algorithm | Policy | Ticket |
|---|---|---|---|
| 1 — Velocity + Z-score | `filtering.py` | KEEP_AS_IS | NaN logging: defer until NaN observed (0 NaN in all sessions) |
| 2 — Hampel (5-frame 3σ) | `filtering.py` | KEEP_AS_IS algorithm; fix is_hampel_outlier propagation | 011 |
| 3 — Winter Butterworth | `filtering.py` | KEEP algorithm; ADD adaptive feedback loop around `filtfilt()` | 015 (last) |
| 4 — Quaternion median | `filtering.py` | KEEP_AS_IS | None |

**What filtering must NOT become:**
- A generalized filter framework with pluggable strategies or per-joint parameter tuning
- A multi-backend filter system (multiple filter types to choose from)
- A session-level sensitivity analysis (filter sensitivity analysis is rejected — offline_batch_audit_only)

**Universal oversmoothing:** ALL 57 position columns flagged `REVIEW_OVERSMOOTHING` in all 15 sessions (Phase 4). This is the known quality limitation that Ticket 015 resolves. Until Ticket 015 is implemented, the limitation is documented in `filter_psd_verdict` and propagated to parquet metadata.

**Ordering constraints:**
1. Ticket 003 (frame count fix) triggers full parquet regeneration — implement and re-lock before Ticket 015
2. Ticket 015 (adaptive loop) also triggers full parquet regeneration — implement LAST, after Tickets 001–014 are all verified
3. The two parquet-regenerating tickets (003 and 015) must be sequential, not concurrent

---

## 12. Phase 12 Preparation

### 15-Ticket Implementation Map

Phase 12 must convert these 15 items into atomic implementation tickets. Each ticket must specify: exact file diff, test gate, golden session update requirement, parquet regeneration requirement, and user confirmation requirements.

| Ticket | Summary | Files | Blast radius | Prerequisite | Notes |
|---|---|---|---|---|---|
| 001 | Per-run config snapshot + `pipeline_version` field | `run_pipeline.py`, `config_v1.yaml` | XS — no output change | None | First ticket; zero risk |
| 002 | S01 hard FAIL gate (`gate_01_status`) | `src/preprocessing.py`, `src/pipeline.py` | S — S01 JSON + stop-on-FAIL in run_pipeline | 001 | Gate logic in preprocessing.py or pipeline.py — investigate before writing |
| 003 | S03 frame count fix + golden test re-lock | `src/resampling.py` | M — ALL parquets regenerated; golden +1 frame | 001, 002 | Must re-lock before Ticket 004 |
| 004 | ref_is_fallback + 4 session label columns | S06 write code (in `src/pipeline.py` or NB06) | M — parquet schema change | 003 | Naming convention needs user decision (UD-006) |
| 005 | var_score guard + t_pose_failed guard | `src/reference.py` | XS — S05 JSON only | 002 | Bundle both guards in same ticket |
| 006 | hard_exclude in feature engine | `src/v2_feature_engine.py` | S — quality_df change | 002, 005 | |
| 007 | filter_psd_verdict + bone_qc_status + gate_01_status + pipeline_version + quaternion diagnostics → parquet | S06 write code; `src/angular_velocity.py` | S — parquet metadata additions | 001, 002 | Bundle 4 metadata fields + quat diagnostic logging |
| 008 | Artifact fraction fix + reference threshold fix | `src/v2_feature_engine.py`, `src/reference_validation.py` | S — quality_df verdicts may change | 006 | Verify no unexpected session category changes after fix |
| 009 | S02 label strings fix | `src/preprocessing.py` | XS — log strings only; no computation change | None | Pure label fix; safe to implement at any point |
| 010 | Hips excluded from ATF_axial + spec amendment | `src/v2_feature_engine.py`, `docs/METHODOLOGY_SPEC_v2.md` | M — ATF_axial recomputed; thesis H3 values change | 008 | Must re-lock ATF_axial golden values after fix |
| 011 | is_hampel_outlier propagation fix | `src/filtering.py` → S06 write path (propagation path requires investigation) | M — investigate first; affects one parquet column | None | Pre-ticket investigation step required |
| 012 | Fast QC script | `src/fast_qc.py` (new file) | L — new file; no existing stage changes | None | T3-01 must remain INFO-only |
| 013 | NB08 session count sync | `notebooks/08_engineering_physical_audit.ipynb` | S — notebook change only | None | No papermill parameterization |
| 014 | QC sidecar outputs | New generation function (location TBD) | M — new output files per session | 007, 008 | Two separate generation functions (session_qc_report.json after S06; feature_reliability_table.csv after feature engine) |
| 015 | S04 adaptive dance-band correction loop | `src/filtering.py` Stage 3 | XL — ALL parquets + ALL features change | ALL 001–014 verified and re-locked | Implement LAST; pre/post protocol mandatory |

**Size legend:** XS < 30 min · S < 2h · M half-day · L 1 day · XL 2+ days

### Items Requiring Pre-Ticket Investigation (Phase 12 must include)

1. **Ticket 002 — S01 gate location:** `parse_optitrack_csv()` is defined in `src/preprocessing.py` and called from `src/pipeline.py`. Phase 12 must decide whether `gate_01_status` is assigned inside `parse_optitrack_csv()` (in preprocessing.py) or in `src/pipeline.py` after the call returns. The stop-on-FAIL logic must live in `run_pipeline.py` or `src/pipeline.py`.

2. **Ticket 011 — is_hampel_outlier propagation path:** The S04 Hampel mask output path into S06 parquet write is not yet traced. Phase 12 must investigate this path before writing Ticket 011. The fix may require tracing through `src/filtering.py`, `src/qc_columns.py`, and S06 parquet write code.

3. **Ticket 014 — sidecar generation location:** The `session_qc_report.json` generation function does not exist yet. Phase 12 must decide where it lives (new file in `src/`, or in `run_pipeline.py`, or in `src/pipeline.py`).

4. **DEPENDENCY_UNVERIFIED files:** Before Phase 12 writes tickets that touch adjacent modules, all 12 `DEPENDENCY_UNVERIFIED` files in `src/` must be classified by grep analysis.

### Regeneration Gates Phase 12 Must Track

| Gate | Triggered by | Sessions affected | Must precede |
|---|---|---|---|
| Parquet regeneration #1 | Ticket 003 (frame count fix) | All 15 live sessions | Ticket 004 verification |
| Parquet regeneration #2 | Ticket 015 (adaptive loop) | All 15 live sessions | Final thesis analysis runs |
| Golden test re-lock #1 | Ticket 003 | 4 golden sessions | Ticket 004 |
| Golden test re-lock #2 | Ticket 010 (ATF_axial) | ATF_axial feature values in all sessions | Thesis H3 analysis |
| Golden test re-lock #3 | Ticket 015 | All golden sessions | Final analysis |

---

## 13. Rejected and Deferred Items

### Explicitly Rejected — Must Not Enter Phase 13

These items are closed. Do not revisit without new evidence and explicit user approval.

| Item | Decision | Reason |
|---|---|---|
| Per-feature reliability columns in parquet | `REJECT_DO_NOT_ADOPT` | Schema bloat; destroys ML/DL readiness |
| `{joint}__bone_qc_flag` per-frame parquet columns | `REJECT_DO_NOT_ADOPT` | Constant columns; no ML information |
| QC plots for every PASS session | `REJECT_DO_NOT_ADOPT` | No automated value; WARN/FAIL/golden only |
| Filter sensitivity analysis per session | `REJECT_DO_NOT_ADOPT` | 3–5× runtime; offline_batch_audit_only |
| Automatic cyclic anchor detection | `REJECT_DO_NOT_ADOPT` | No algorithm, no calibration, no data |
| Structured-task QC module | `REJECT_DO_NOT_ADOPT` | No reliable annotations |
| Automatic QC dashboard (new build) | `REJECT_DO_NOT_ADOPT` | Fix existing NB08/NB09 first |
| ROM calibration as hard FAIL gate | `REJECT_DO_NOT_ADOPT` | .mcal files deleted for historical sessions |
| Adopting Pose2Sim `zero == missing` convention | `REJECT_DO_NOT_ADOPT` | Zero is valid (Hips root = 0 by definition) |
| Adopting scikit-kinematics quaternion convention | `REJECT_DO_NOT_ADOPT` | Convention mismatch corrupts all quaternion computations |
| Full raw-to-processed trajectory comparison in v1 | `REJECT for v1` | Requires coordinate-frame alignment; premature before F-INT1 fix |
| Full gap-boundary artifact test in v1 | `REJECT for v1` | Requires gap logs S02 doesn't produce |
| `enforce_cleaning = true` as default | `REJECT_DO_NOT_ADOPT` | LOCKED USER DIRECTIVE — ground truth integrity |
| External library adoption (Pose2Sim, scikit-kinematics) | `REJECT_DO_NOT_ADOPT` | Quaternion convention hazard |
| Any new kinematic feature columns in parquet | `DEFER` | Out of scope; requires separate spec approval |

### Explicitly Deferred — Document and Log, Do Not Implement

| Item | Source | Reason |
|---|---|---|
| S02 velocity estimator upgrade (3-pt central diff) | Phase 3 | MAD is dormant; 0 detections in 15 sessions |
| S01 two-tier FAIL/SUSPICIOUS flagging | Phase 3 | Hard FAIL gate sufficient |
| S02 genuine SLERP gap fill implementation | Phase 4 | Never called; boundary bug at line 134 unresolved |
| Full gate chain S03–S06 | Phase 5 | 0 failures below S01 in current data |
| NaN tracking chain per stage | Phase 4 | All 15 sessions = 0 NaN frames |
| T3-01 T-pose threshold calibration | Phase 8 | DRAFT_PENDING_RESEARCH; needs ≥15 session calibration |
| Day-level QC aggregation | Phase 9.5 | Requires stable session-level QC first |
| Numeric `session_reliability_score` formula | Phase 9.5 | Needs N≥20 calibration; categorical labels sufficient |
| Unified per-stage `pipeline_version` field | Phase 5 | Config snapshot provides sufficient provenance |
| `optitrack_version` extraction | Phase 4 | Always "unknown"; requires Motive version mapping |
| Anti-aliasing filter before downsampling | Phase 4 | Not applicable (120→120 Hz) |
| `finite_difference_5point()` rename | Phase 4 | Deferred cleanup; rename before reconsidering default |
| NB07, NB09, NB10 archival | Phases 1–2 | Verify no active imports first; archive in Phase 13 |
| `v2_longitudinal.py` | Phase 7 | Post-thesis scope |
| Pose/reach branches in v2_feature_engine | Phase 7 | MVP-deferred; raises ValueError |
| NB08 papermill parameterization | Phase 4 | Session count fix (Ticket 013) is sufficient |
| SO(3)-aware smoothing (geodesic SavGol) | Phase 4.5 | Await diagnostic evidence from Ticket 007 |
| `v2_longitudinal.py` implementation | Phase 7 | Post-thesis scope; session-level integrity must be confirmed first |
| `qa_master_pipeline_validation.ipynb` | Phase 2 | Status unverified; do not touch until verified |

---

## 14. Open User Decisions

The following decisions cannot be resolved in Phase 11. Phase 12 ticket writing must await resolution of those marked as blocking.

| ID | Decision | Blocking for | Default recommendation |
|---|---|---|---|
| UD-001 | S04 adaptive loop threshold: -3 dB (Phase 3 default) vs. tighter threshold for high-velocity sessions | Ticket 015 config spec | Implement at -3 dB as designed; expose as `dance_band_threshold_db` config parameter; revisit after post-implementation review |
| UD-002 | `omega_method = '5pt'` as default (after rename)? | None for Phase 13 — `quat_log` is the correct current default | Keep `quat_log` as default; defer rename of `finite_difference_5point()` to separate cleanup ticket; do not change default before rename |
| UD-003 | Gate chain scope: S01 gate only vs. expanding to S02–S06? | None — S01-only confirmed for thesis scope | Gate at S01 only; full gate chain is Phase 14+ |
| UD-004 | QC sidecar timing: two separate steps vs. combined post-processing pass? | Ticket 014 implementation design | Two separate steps: `session_qc_report.json` after S06; `feature_reliability_table.csv` after feature engine |
| UD-005 | Study N: is a third subject in scope? N=2 or N=3? | Batch runner scope in Phase 12; Ticket 015 regeneration scope | Cannot be resolved here; user must confirm N before Phase 12 writes batch runner tickets |
| UD-006 | Column naming for session labels: abbreviated (`651`, `T1`, `P2`, `R1`) vs. expanded (`Subject_651`, `Timepoint_1`, etc.)? | Ticket 004 implementation | Abbreviated format preferred for ML use; user must confirm before Ticket 004 is written |

---

## Architecture Decisions Summary

| Decision | Rationale |
|---|---|
| `hybrid_modular_rebuild` | Computation layer validated; infrastructure layer systematically absent |
| 15 tickets as complete Minimal v1 scope | Evidence-based; bounded; thesis-timeline compatible |
| `sidecar_first` QC policy | Parquet stays ML-ready; QC in JSON/CSV sidecars |
| `gate_01_status` S01 only for thesis | 0 gate failures below S01 in current data |
| Schema v2.0: 803 + 4 data cols + 5 metadata fields | Minimal approved additions; all others rejected |
| `quat_log` as permanent default | Respects SO(3); correct; `finite_difference_5point()` mislabeled |
| `enforce_cleaning = false` locked | Ground truth integrity; USER DIRECTIVE LOCKED |
| Ticket 015 last, after full re-lock | Highest blast radius; must not interfere with other fixes |
| Hips excluded from ATF_axial | Hips cannot have non-zero relative velocity by definition |
| No SO(3)-aware smoothing in v1 | Await diagnostic evidence from quaternion logging |
| No numeric session_reliability_score | Not calibrated; categorical PASS/WARN/FAIL is safer |
| Notebook logic must live in `src/` | Batch execution requires all logic to be callable from run_pipeline.py |

---

*Phase 11 final target skeleton complete.*
*This document supersedes `audit_outputs/03_target_skeleton_draft.md`.*
*Phase 12 (implementation backlog) must not begin until user approves this skeleton.*
