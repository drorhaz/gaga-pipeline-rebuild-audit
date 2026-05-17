# HANDOFF — Current Session State

**Last updated:** 2026-05-15
**Last completed phase:** Phase 9 — Testing and Regression Plan (COMPLETE)
**Next phase:** Phase 10 — Anti-overengineering review and decision gate

**End-of-Day Handoff Lock created:** `audit_outputs/HANDOFF_END_OF_DAY_BEFORE_PHASE_10.md`
All phases 0–9 verified complete. Full findings synthesis, Phase 10 input list (27 items), and draft Phase 10 prompt are in that file. Read it first before starting Phase 10.

---

## Phases completed

| Phase | Output |
|-------|--------|
| 0 | `00_project_orientation.md` |
| 1 | `01_specs_source_of_truth.md`, `01_spec_conflicts_register.md` |
| 2 | `02_current_pipeline_map.md` |
| 3 | `03_target_skeleton_draft.md` |
| 4 (ALL) | `04_stage_audits/S01_parse.md`, `S02_preprocess.md`, `S03_resample.md`, `S04_filtering.md`, `S05_reference.md`, `S06_kinematics.md`, `S08_audit.md` |
| 4.5 | `04.5_external_standards_alignment.md` |
| 5 | `05_cross_stage_integration_audit.md` |
| 5.5 | `05.5_subject_651_evidence_expansion.md` |
| 6 | `06_master_parquet_ml_readiness_audit.md` |
| 7 | `07_downstream_methodology_compatibility_audit.md` |
| 8 | `08_fast_post_collection_qc_requirements.md` |
| 9 | `09_testing_and_regression_plan.md` |

---

## Key decisions locked in Phase 3

| Component | Decision | Priority |
|-----------|----------|---------|
| Per-run config snapshot (`step_00_config/{RUN_ID}__config_snapshot.yaml`) | `LOCAL_REFACTOR` | High |
| Bone QC warning/flagging policy + new `{joint}__bone_qc_flag` column in parquet | `KEEP_LOG_QC` | High |
| Stage 3 adaptive dance-band correction loop (self-corrects if Δ_dance < -3 dB) | `REDESIGN_CANDIDATE` | **Critical** |
| Step 02 velocity estimator upgrade (3-pt central diff) | `LOCAL_REFACTOR` | Medium — pending Phase 4 confirmation |
| Stage 1 two-tier flagging (FAIL vs SUSPICIOUS) | `LOCAL_REFACTOR` | Medium — pending Phase 4 confirmation |
| `omega_method = '5pt'` as default | `LOCAL_REFACTOR` (config) | Low |
| `enforce_cleaning = true` as default + repair log | **DECISION REVERSED — `enforce_cleaning` will remain `false` by default. Phase 3 recommendation rejected. Rationale: enforce_cleaning=true causes silent data mutations (SLERP-repair of critical frames in-place). Ground Truth integrity takes priority. kinematic_repair.py stays as an opt-in diagnostic tool only.** | — |
| Step 05 fallback reference warning flag | `KEEP_LOG_QC` | Low |
| Legacy archive (C2, C4) | Already done | — |

---

## Phase 4 — Consolidated findings across all 7 stage audits

### S-01 (Parse)
- **Q-EXT3b FAIL:** `Capture Frame Rate`, `Export Frame Rate`, `Rotation Type`, `Length Units` not extracted from CSV header
- **Q-EXT3c FAIL:** No frame number continuity check; `frame_number_continuity_status` absent
- `optitrack_version` always "unknown" (extraction silently fails on all 9 sessions)
- Calibration fields (pointer_tip_rms_error_mm, wand_error_mm) always null

### S-02 (Preprocess)
- **Q-QC7:** 0/9 sessions REJECT bone QC. T1/T2=GOLD, T3=SILVER (mean_cv~1.4%). Hips→Spine alert in all 9.
- **Q-EXT1b FAIL:** Method labels wrong — logs "pchip_single_pass"/"slerp" but actual code uses np.interp/linear-normalize
- **Q-S02:** Step 02 MAD at 6.0σ is dormant (0 detections). Cannot assess false positive rate.
- Gap detection bug in gapfill_positions.py:134 (wrong boundary condition)
- gapfill_quaternions.py SLERP is a placeholder; never called
- Three inconsistent bone QC threshold systems (NB02, qc.py, forensic_report.py)

### S-03 (Resample)
- **Q-EXT3a:** No anti-aliasing filter. Currently not applicable (all sessions 120→120Hz). Design gap for future.
- Step 03 uses GENUINE PCHIP and GENUINE SciPy SLERP (contrast with Step 02 which is linear)
- Resample summary doesn't log NaN frame counts
- No interpolated-frame provenance flag in resampled parquet

### S-04 (Filtering) [previously audited]
- Adaptive Butterworth ("smart bias"), Winter residual analysis, dance band PSD validation
- REDESIGN_CANDIDATE: adaptive dance-band correction loop (Δ_dance < -3 dB)
- Missing: n_nan_frames_at_filter_input log (Q-EXT1a)
- NaN position restoration after filtering not verified (Q-EXT1c)

### S-05 (Reference)
- All 9/9 sessions: ref_is_fallback=false, confidence=HIGH (7) or MEDIUM (2)
- 5 fallback paths coded and flagged; none triggered in current data
- No downstream gate on ref_is_fallback or t_pose_failed propagation
- MEDIUM confidence trigger criteria not explained in JSON metadata
- ref_quality_score naming counterintuitive (higher = worse)

### S-06 (Kinematics)
- **Q-EXT4a FAIL:** No |q|≈1.0 assertion with logging. Silent per-frame renormalization only.
- **Q-S06a PARTIAL:** Method comparison logged (aggregate noise only), no per-joint Δω JSON
- `finite_difference_5point()` is a weighted smoother, NOT a true 5-point stencil
- **Q-S06b N/A:** enforce_cleaning=False, kinematic_repair inactive
- quat_log is the default method (correct). SavGol smoothing of quat components is geometrically approximate.
- No NaN frame count at kinematics input

### S-08 (Engineering Audit)
- 16 runs × 140 measurements, Smart Bias confirmed dominant (74–84% of columns)
- Pre-processing SNR, filter audit, CoM coverage all documented
- **CRITICAL: NB08 output references 16 runs but current derivatives have 9.** Out-of-sync state.
- No per-session pass/fail gates; no papermill parameterization
- No per-session HTML report

---

## Key findings from Phase 4.5 (External Standards Alignment)

| Q# | Question | Target stage | Answer |
|----|----------|-------------|--------|
| Q-EXT1a | Does Stage 3 log `n_nan_frames_at_filter_input`? | S-04 | FAIL |
| Q-EXT1b | PCHIP-repaired vs Hampel-replaced frames distinct? | S-02, S-04 | FAIL (label mismatch in S-02) |
| Q-EXT1c | Does Stage 3 verify NaN positions preserved? | S-04 | FAIL |
| Q-EXT2a | Does config separate stable/sensitivity/experimental? | S-00 | **ABSENT** — flat structure |
| Q-EXT2b | All filter params logged to JSON? | S-04 | **PASS** (gap: no NaN input count) |
| Q-EXT2c | Per-step boolean toggles from config? | S-00 | **ABSENT** — hardcoded sequence |
| Q-EXT2d | Per-session stage failures logged? | All | **PARTIAL** — batch runner JSON in reports/ only |
| Q-EXT3a | Anti-aliasing before downsampling? | S-03 | ABSENT (not applicable at 120Hz→120Hz) |
| Q-EXT3b | Config snapshot logs Capture/Export Frame Rate, Rotation Type, Length Units? | S-01 | FAIL |
| Q-EXT3c | Frame number continuity check? | S-01 | FAIL |
| Q-EXT4a | Stage 6 asserts |q|≈1.0 after loading and smoothing? | S-06 | FAIL |
| Q-EXT4b | Pipeline checks quaternion hemisphere flips before SLERP? | S-02 | PARTIAL (Step 03 SLERP does; Step 02 does not) |
| Q-EXT5a | Stage 3 handles sessions shorter than filter padding? | S-04 | **PASS** — chunking_guard implemented and logged |

Key external conventions (never forget):
- **scikit-kinematics uses scalar-FIRST `[w,x,y,z]`** — our SciPy is `[x,y,z,w]` — never copy quaternion code
- **pose2sim `zero == missing` hazard**: must NOT adopt — zero is valid in our pipeline
- **optitrack-main confirms**: anti-aliasing before downsampling; metadata provenance fields

---

## [RECONSIDER_LATER] registry

| Tag | Stage | Text |
|-----|-------|------|
| Q-ADP | S-04.3 | Verify if -3 dB dance band threshold is sufficient for high-velocity sessions. Evaluate after Phase 4 frequency audit on ≥10 P2 sessions. |
| Q-QC7 | S-02.2 | Quantify CoM and ω_mag uncertainty from bone length CV > 5% for N > 20 sessions. Pending before thesis-grade CoM claims. |
| Q-S02 | S-02.1 | Measure Step 02 false-positive masking rate against 1–13 Hz dance band. If >10% of masked frames are physiological, upgrade velocity estimator. (Currently moot — Step 02 MAD is dormant with 0 detections.) |

---

## Open user questions (accumulated)

| Q# | Question | Phase origin |
|----|----------|-------------|
| Q2 | Add supersession header to `Thesis_Analytical_Pipeline.md`? | Phase 1 |
| Q3 | Plan to version/snapshot `config_v1.yaml`? (Addressed by S-00 LOCAL_REFACTOR in Phase 3) | Phase 1 |
| Q4 | Who is the third subject? Is study N=2 or N=3? | Phase 1 |
| Q5 | Keep `09_Subject_Exploration_Dashboard.ipynb` as legacy, or replace with v2? | Phase 1 |
| Q6 | PSD REVIEW_OVERSMOOTHING (-5.40 dB): addressed by adaptive correction loop (Phase 3) | Phase 2 → Phase 3 resolved |
| Q7 | Bone QC FAIL: addressed by Warning & Flagging policy (Phase 3) | Phase 2 → Phase 3 resolved |
| Q8 | NB10 broken (imports `legacy/EDA_PCA.py`): add deprecation header OR update import? | Phase 2 |

---

## Phase 5 — Consolidated findings (Cross-Stage Integration Audit)

**Canonical session traced:** `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002`

### Frame count chain
- S01=16,915 → S04=16,914 (**−1 frame silent loss in S03 resampling**)
- S04=16,914 → S06=16,914 (consistent)
- S02 and S03 summaries do NOT log `n_frames_input`/`n_frames_output`

### Gate chain
- Only S02 has `gate_02_status = "PASS"` (no downstream chain)
- S03, S04, S05, S06 have no explicit gate field
- REVIEW_OVERSMOOTHING verdict (S04) does not propagate to S05/S06

### NaN accounting
- This session: 0 NaN frames (pristine). NaN chain tracking ABSENT structurally.
- `n_nan_frames_at_filter_input` absent from S04 (Q-EXT1a FAIL confirmed)

### Q-EXT answers finalized
- Q-EXT2a: ABSENT (flat config)
- Q-EXT2b: PASS (minor gap: no NaN input count)
- Q-EXT2c: ABSENT (hardcoded pipeline_sequence, no per-step toggles)
- Q-EXT2d: PARTIAL (batch runner saves reports/batch_summary JSON but not per-session derivatives)
- Q-EXT5a: PASS (chunking_guard implemented in filtering.py and logged)

### New findings from Phase 5
- **F-INT1:** Off-by-one in S03 `n_target = round(duration × fs)` drops last frame silently
- **F-INT2:** `config_v1.yaml` mutated in-place after each run — `current_csv` retains last session; no per-run config snapshot implemented yet
- **F-INT3:** REVIEW_OVERSMOOTHING not propagated to S06 kinematics parquet metadata
- **F-INT4:** `outputs_verified` check in run_pipeline.py is insufficient (misses S05 outputs, parquet row counts)
- **F-INT5:** No unified `pipeline_version` field across stage summaries (S01=v2.6, S04=v3.1, S06=none)

---

## Phase 5.5 — Consolidated findings (Subject 651 Evidence Expansion)

**6 P2 sessions across T1/T2/T3 analysed. 1 session is DEAD (T2_P2_R2, 5 frames, 0.03s).**

### Confirmed universal findings (across both subjects, all 15 sessions)
- S01 metadata gaps (optitrack_version=unknown, calibration=null): **UNIVERSAL**
- S02 MAD dormant (0 artifact detections): **UNIVERSAL**
- S02 label mismatch (Q-EXT1b, pchip_single_pass/slerp mislabeled): **UNIVERSAL**
- Hips→Spine bone QC alert: fires in 100% of live sessions for both subjects
- S03 PERFECT temporal status: **UNIVERSAL**
- F-INT1 (1-frame loss S01→S04): **UNIVERSAL** — confirmed on all 5 live non-trivial 651 sessions
- REVIEW_OVERSMOOTHING all 57 cols: **UNIVERSAL** — confirmed on all live 651 sessions
- Worst PSD column = Hips__py: **UNIVERSAL**
- Winter cutoff mean ≈ 8.55 Hz, Smart Bias 48/57 cols: **UNIVERSAL**

### New critical findings from 651 not visible in 671
- **F-651-1 CRITICAL:** Dead session (5 frames) passes ALL 6 pipeline stages silently. No gate exists for minimum session length. T2_P2_R2 produced kinematics artifacts on 4 frames.
- **F-651-2:** `var_score = inf` (Infinity) in S05 JSON for dead session — invalid JSON, numeric instability
- **F-651-3:** Bone QC CV rises T1→T2→T3 (0.35 → 1.01 → 0.69), with T2 reaching SILVER (3 alerts)
- **F-651-4 HIGH:** First genuine fallback reference in dataset — T3_P2_R2 `ref_is_fallback=True` due to movement at recording start. Kinematics offset from wrong reference pose; not annotated in parquet.
- **F-651-5:** `t_pose_failed = null` (not `false`) for `least_motion_window_fallback` sessions — code checking `if t_pose_failed:` would miss these cases

### Priority additions from Phase 5.5
| Finding | Action | Priority |
|---------|--------|---------|
| F-651-1: Dead session passes all gates | **USER DIRECTIVE LOCKED:** S01 minimum session gate = **30 seconds / 3600 frames at 120Hz**. Hard FAIL on `gate_01_status`. Anything under 30s is a botched recording. (A genuine dance phrase takes >140s.) | **CRITICAL** |
| F-651-4: Fallback not propagated downstream | Add `ref_fallback_flag` to kinematics parquet | High |
| F-651-2: var_score=inf | Guard variance calc; serialize as null | High |
| F-651-5: t_pose_failed=null vs false | Set explicitly False for non-identity fallbacks | Medium |

---

## Phase 7 — Consolidated findings (Downstream Methodology Compatibility Audit)

**Scope:** Can METHODOLOGY_SPEC_v2.md (v3.0) F1 ATF, F2 TM, F4 D_eff, F5 Gini be correctly computed from the current parquet using v2_feature_engine.py?

### Column compatibility
- F1 ATF: all 19 `{Joint}__lin_vel_rel_mag` + `is_artifact` PRESENT ✓
- F2 TM: all 4 endpoints × 3 position axes + 4 `is_artifact` flags PRESENT ✓
- F4 D_eff dynamics branch: all 19 `{Joint}__zeroed_rel_omega_mag` PRESENT ✓
- F5 Gini: inherited from F4 PCAEngine ✓

### Critical findings
- **F7-1 CRITICAL:** Hips ATF = 0 permanently. `Hips__lin_vel_rel_mag = 0` always (root joint). ATF_axial biased downward. Spec includes Hips in axial group but doesn't address this.
- **F7-2 CRITICAL:** `ref_is_fallback` absent from parquet → F4/F5 silently biased for `651_T3_P2_R2` (wrong reference pose). No gate in Block 0.
- **F7-3 HIGH:** Artifact fraction in `compute_quality_gates` uses `max(joint_art_rates)` not OR-union. Implementation is LESS strict than spec. Use `1.0 - clean_fraction_pca` instead.
- **F7-4 HIGH:** `validate_reference()` checks 0.30 threshold, spec requires 0.20 for reference sessions.
- **F7-5 HIGH:** Dead session (651_T2_P2_R2, 5 frames) gets `short_session=True` not `hard_exclude=True`. Spec requires hard exclusion for dead recordings.
- **F7-6 MEDIUM:** REVIEW_OVERSMOOTHING (universal) affects F2 TM (shorter paths) and F1 ATF noise floor (compressed dynamic range). No warning in parquet metadata.
- **F7-7 MEDIUM:** Session-native D_eff/Gini use `explained_variance_` (ddof=1) while T1-anchored uses `np.var(ddof=0)`. Minor inconsistency.
- **F7-8 MEDIUM:** `dead_recording` field absent from quality_df; naming inconsistencies (`pca_low_confidence` vs spec's `pca_unreliable`).
- **F7-9 MEDIUM:** `src/v2_longitudinal.py` absent (MVP deferral — expected).
- **F7-10 LOW:** Only `dynamics` branch implemented; `pose`/`reach` branches raise ValueError (MVP deferral).

### What works
pulsicity.compute_noise_floor interface is compatible ✓; anti-double-dipping PCAEngine ✓; contiguous-run TM logic ✓; ALL_19_JOINTS list matches parquet ✓; ATF NaN-safe computation ✓; PCA.transform() used (not manual multiply) ✓

---

## Next phase context

**Phase 6 goal:** Master parquet ML/DL readiness audit. Inspect the final `kinematics_master.parquet`
for one or more sessions and verify:
1. Column schema completeness (all expected ω, α, position, linear velocity columns present)
2. Parquet metadata fields (pipeline_version, run_id, subject_id, anthropometrics)
3. NaN density per column — which joints/features have NaN frames and at what rate
4. Data type consistency (float32 vs float64, no object columns)
5. Index structure (frame-based or time-based; appropriate for ML windowing)
6. REVIEW_OVERSMOOTHING annotation absent from parquet metadata (F-INT3)
7. Scaling / normalization state (raw or pre-normalized?)

**Prompt for next agent:**
```
You are the ML/DL Readiness Audit Agent running Phase 6 of the Gaga Pipeline audit.

Phases 0–5 are complete. Phase 5 key finding: 1-frame silent loss in S03 resampling (16,915→16,914);
no gate chain beyond S02; REVIEW_OVERSMOOTHING verdict not propagated to kinematics parquet.

Read first:
1. audit_outputs/HANDOFF_CURRENT.md (this file)
2. audit_outputs/05_cross_stage_integration_audit.md
3. audit_outputs/04_stage_audits/S06_kinematics.md

Your task: Phase 6 — Master parquet ML/DL readiness audit.
Canonical session: 671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002

Read:
- derivatives/step_06_kinematics/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__kinematics_master.parquet
  (use pandas or pyarrow: inspect .dtypes, .columns, .shape, .isnull().sum(), parquet metadata)

Verify: column schema completeness, NaN density, data types, index structure, parquet metadata fields,
any annotation of upstream QC flags (e.g., filter_qc_flag from REVIEW_OVERSMOOTHING verdict).
Mode: Read-only. No code changes.
Write: audit_outputs/06_master_parquet_ml_readiness_audit.md
Stop after writing and await user approval.
```

---

## Phase 8 — Consolidated findings (Fast Post-Collection QC Requirements)

**Mode:** Design-only. Produced: `08_fast_post_collection_qc_requirements.md`

### Three-tier check structure

| Tier | Description | Checks | Hard FAILs |
|------|-------------|--------|-----------|
| 1 | Raw file checks (CSV header + Time/Frame columns) | T1-01 to T1-13 | File missing, duration < 30s, frame count < 3600, time non-monotonic, missing joints |
| 2 | Parsed structural checks (positions + quaternion body) | T2-01 to T2-16 | Malformed arrays, all-NaN joint, quat norm < 0.5, any endpoint >50% NaN |
| 3 | Scientific sanity (raw quat-diff + bone geometry) | T3-01 to T3-08 | Bone CV > 5% (severe slippage); WARNs for T-pose, ref-fallback risk |

### Key requirements locked by audit evidence

| Check | Evidence source | Threshold |
|-------|----------------|-----------|
| T1-05: 30s/3600-frame hard FAIL | F-651-1 user directive | 30s = 3600 frames at 120Hz |
| T1-09/T1-10: Capture rate + rotation type | Q-EXT3b FAIL | Extract from CSV header row |
| T2-11: Frame number continuity | Q-EXT3c FAIL | diff(Frame) must all = 1 |
| T2-08/T2-09: Quaternion norm | Q-EXT4a FAIL | WARN if |q| outside 0.90–1.10; FAIL if |q| < 0.5 |
| T3-01/T3-07: T-pose window check | F-651-4 (ref_is_fallback) | **DRAFT_PENDING_RESEARCH — threshold not validated; see ADV-T3-01 below** |
| T3-03: Bone length CV | F-651-3 bone CV drift | WARN > 2%; FAIL > 5% |
| T3-08: Hips ATF note | F7-1 (Hips ATF = 0) | Info message always shown |

### Key design constraints
- Runtime: < 10s on a 160s session; no SciPy/sklearn/filtering/PCHIP
- Verdict: PASS / PASS_WITH_WARNINGS / FAIL (exit code 0 vs 1)
- Outputs: `{RUN_ID}__fast_qc_report.txt` + `{RUN_ID}__fast_qc_result.json` → `qc/fast_qc/`
- Callable standalone, from `run_pipeline.py` pre-check, or `--batch` mode
- Test fixtures: 651_T2_P2_R2 → FAIL; 671_T1_P2_R1 → PASS; 651_T3_P2_R2 → PASS_WITH_WARNINGS

### Deferred advanced research task

**ADV-T3-01: Advanced T-pose / static window detection** *(deferred to implementation phase)*

Status: **DRAFT_PENDING_RESEARCH**

Problem: The 0.10 rad/s angular velocity threshold and fixed 8-second search window for check T3-01 are too strict on real data and produce false alarms even when the subject is known to be statically posed. The check must be redesigned before implementation.

User-identified candidate approaches for implementation phase:
1. **Threshold loosening:** Explore the range 0.15–0.30 rad/s; derive threshold empirically from all 15 known-good sessions (not from a single failure case, 651_T3_P2_R2).
2. **Global minimum search instead of absolute threshold:** Identify the minimum-motion window globally across the recording; compare it to a dynamically calibrated floor (e.g., 2× inter-session mean minimum) rather than a fixed absolute threshold. This handles subjects with naturally higher baseline angular velocity.
3. **"Double-back" stability verification:** After finding the minimum-motion window, verify that the surrounding ±2s windows show increasing motion (subject transitioning toward/away from pose), not that the entire recording is uniformly low-motion (which would indicate a recording artifact, not a genuine T-pose). This distinguishes "brief T-pose at start" from "subject already moving throughout."

Until calibrated: T3-01 emits INFO only, not WARN or FAIL. T3-07 (Hips position variance branch) may be implemented independently as a more stable proxy.

Evidence sources: Phase 5.5 F-651-4; Phase 7 F7-2; user feedback on Phase 8 requirements.

---

## Phase 9 — Consolidated findings (Testing and Regression Plan)

**Mode:** Design-only. Produced: `09_testing_and_regression_plan.md`

### Test pyramid (4 layers)

| Layer | Type | Speed | Data needed |
|-------|------|-------|------------|
| 1 | Unit tests (pure functions) | < 1s each | None |
| 2 | Synthetic signal tests | < 5s | Constructed in-code |
| 3 | Stage-level integration | Seconds | Small derivative fixtures |
| 4 | Golden-data regression | Minutes | Full real sessions |

### Existing test coverage (21 files in tests/)
Covers: artifacts, calibration, coordinate systems, Euler ISB, filtering, gap fill, gates, kinematics, preprocessing, QC columns, quaternion ops, reference alignment, resampling, time alignment, units, validation.

### 12 new unit tests required (U-NEW-01 to U-NEW-12)

| ID | What | Finding |
|----|------|---------|
| U-NEW-01 | OR-union artifact fraction > max per-joint | F7-3 |
| U-NEW-02 | validate_reference() threshold = 0.20 not 0.30 | F7-4 |
| U-NEW-03 | dead_recording=True + hard_exclude=True for 5 frames | F7-5, F-651-1 |
| U-NEW-04 | S01 gate_01_status=FAIL for < 3600 frames | User directive |
| U-NEW-05 | build_pca_engine() skips dead non-reference session cleanly | F7-5 |
| U-NEW-06 | var_score=null (not Infinity) on dead session reference | F-651-2 |
| U-NEW-07 | Bone CV > 2% when marker slip simulated | F-651-3, T3-03 |
| U-NEW-08 | t_pose_failed=False (not None) for fallback sessions | F-651-5 |
| U-NEW-09 | ref_is_fallback in parquet metadata from S05 JSON | F-651-4, F7-2 |
| U-NEW-10 | filter_psd_verdict in parquet metadata from S04 | F-INT3 |
| U-NEW-11 | is_hampel_outlier=True for Hampel-modified frames | Phase 6 |
| U-NEW-12 | S03 output frame count = S01 frame count after fix | F-INT1 |

### 4 golden sessions

| Session | Expected verdict |
|---------|----------------|
| `671_T1_P2_R1` | Canonical PASS — all fields locked |
| `651_T1_P2_R1` | Secondary PASS — cross-subject regression |
| `651_T2_P2_R2` (5 frames) | gate_01_status=FAIL after fix |
| `651_T3_P2_R2` (fallback ref) | ref_is_fallback=True in parquet after fix |

### Critical tolerance rules

- Frame counts: **exact match** (0 tolerance)
- Gate statuses: **exact match**
- Feature scalars (ATF, TM, D_eff, Gini): **±1% relative** after first lock-in
- Any unexpected scientific scalar change requires **written justification in implementation log**
