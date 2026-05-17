# End-of-Day Handoff Lock — Before Phase 10

**Created:** 2026-05-15
**Last completed phase:** Phase 9 — Testing and Regression Plan
**Next phase:** Phase 10 — Anti-Overengineering Review and Decision Gate
**Mode:** Read-only planning / handoff. No implementation has started.

---

## A. Current Status

### Phase completion table

| Phase | Name | Status | Output file(s) |
|-------|------|--------|---------------|
| 0 | Project Orientation | **COMPLETE** | `00_project_orientation.md` |
| 1 | Specs source-of-truth and conflict map | **COMPLETE** | `01_specs_source_of_truth.md`, `01_spec_conflicts_register.md` |
| 2 | Current pipeline map | **COMPLETE** | `02_current_pipeline_map.md` |
| 3 | Draft target skeleton | **COMPLETE** | `03_target_skeleton_draft.md` |
| 4 | Per-stage audits (S01–S08) | **COMPLETE** | `04_stage_audits/S01_parse.md` through `S08_audit.md` |
| 4.5 | External Reference Alignment | **COMPLETE** | `04.5_external_standards_alignment.md` |
| 5 | Cross-stage integration audit | **COMPLETE** | `05_cross_stage_integration_audit.md` |
| 5.5 | Subject 651 evidence expansion | **COMPLETE** | `05.5_subject_651_evidence_expansion.md` |
| 6 | Master parquet ML/DL readiness audit | **COMPLETE** | `06_master_parquet_ml_readiness_audit.md` |
| 7 | Downstream methodology compatibility audit | **COMPLETE** | `07_downstream_methodology_compatibility_audit.md` |
| 8 | Fast post-collection QC requirements | **COMPLETE** | `08_fast_post_collection_qc_requirements.md` |
| 9 | Testing and regression plan | **COMPLETE** | `09_testing_and_regression_plan.md` |
| **10** | **Anti-overengineering review and decision gate** | **PENDING** | `10_*.md` |
| 11 | Final target skeleton | Pending | `11_final_target_skeleton.md` |
| 12 | Implementation backlog | Pending | `12_implementation_backlog.md` |
| 13 | Implementation, one ticket at a time | Pending | `13_implementation_logs/` |
| 14 | Thesis-grade release and scale validation | Pending | `14_release_and_thesis_readiness_checklist.md` |

### Audit corpus size
- **15 sessions** examined: 6 × Subject 651 (T1/T2/T3, two repetitions each; one T3 fallback ref; one T2 dead); 9 × Subject 671 (T1/T2/T3, one or two reps; canonical = `671_T1_P2_R1`)
- **7 stage audits** (S01–S06, S08) completed
- **Canonical session parquet:** `671_T1_P2_R1` → (16,914 rows × 803 columns), 126.3 MB on disk
- **Code read:** `src/v2_feature_engine.py`, `src/pulsicity.py`, `src/filtering.py`, `src/angular_velocity.py`, `run_pipeline.py`, `config/config_v1.yaml`, 21 existing test files in `tests/`

---

## B. Most Important Findings — Grouped by Category

### B1. Safety and Data Integrity (CRITICAL/HIGH)

| Finding ID | Stage | Description | Evidence |
|-----------|-------|-------------|---------|
| **F-651-1** | S01 | Dead session (5 frames, 0.03s) passes ALL 6 pipeline stages silently. Kinematics computed on 4 frames. **User directive locked: 30s / 3600-frame hard FAIL gate on S01.** | `651_T2_P2_R2` parquet exists with kinematics artifacts |
| **F-651-4** | S05→S06 | First genuine fallback reference in dataset: `651_T3_P2_R2` uses wrong reference pose (`ref_is_fallback=True`). Not annotated in kinematics parquet. F4/F5 features biased. | `651_T3_P2_R2__reference_metadata.json` → `ref_is_fallback: true`; parquet has no such field |
| **F7-2** | S06 | `ref_is_fallback` absent from kinematics parquet metadata → downstream feature engine (Block 0 gate) cannot detect biased sessions. | Phase 6 parquet metadata inspection: key absent |
| **F-INT1** | S03 | Off-by-one in `n_target = round(duration × fs)` silently drops last frame universally. S01=16,915, S04=16,914. Not logged in S03 summary. Confirmed on all 5 live non-trivial 651 sessions AND canonical 671 session. | All S01 vs S04 frame count comparisons; `__resample_summary.json` logs no frame counts |
| **F-651-2** | S05 | `var_score = inf` (Infinity) in `reference_metadata.json` for dead session — invalid JSON, numeric instability from empty frame set. | `651_T2_P2_R2__reference_metadata.json` → `"var_score": Infinity` |
| **F7-5** | v2_feature_engine | Dead session gets `short_session=True` not `hard_exclude=True`. Spec requires hard exclusion. Engine may still attempt PCA on dead session. | `v2_feature_engine.py` `build_pca_engine()` logic |

### B2. Universal Quality Issues (HIGH/MEDIUM — affects all 15 sessions)

| Finding ID | Stage | Description | Evidence |
|-----------|-------|-------------|---------|
| **REVIEW_OVERSMOOTHING** | S04 | ALL 57 position columns universally flagged REVIEW_OVERSMOOTHING. Mean dance-band attenuation −4.68 to −5.51 dB. Worst: `Hips__py` at −24 to −27 dB. Affects F1 ATF noise floor and F2 TM path lengths. | All 15 sessions, all filtering_summary JSONs |
| **F-INT3** | S04→S06 | REVIEW_OVERSMOOTHING verdict not propagated to S05/S06 or kinematics parquet metadata. Downstream consumers cannot detect over-smoothed input. | S06 validation_report.json and parquet metadata: no `filter_psd_verdict` field |
| **S02 dormant** | S02 | MAD artifact detection is dormant: 0 detections across all 15 sessions. Cannot assess false-positive rate. True masking rate unknown. | All `__preprocess_summary.json` → `frames_fixed_count=0` universally |
| **Q-EXT1b label mismatch** | S02 | Logs say `pchip_single_pass` and `slerp` but actual code uses `np.interp` (linear) and scalar-normalize only. Methodological misrepresentation in all 15 session logs. | `src/preprocessing.py` vs log field `interpolation_method` |
| **Hips→Spine bone QC** | S02 | `Hips→Spine` segment fires a bone QC alert in 100% of live sessions for both subjects. Alert appears systematic, not data-quality signal. | All 15 sessions; Phase 4 S02 audit |
| **F-INT2** | S00 | `config_v1.yaml` mutated in-place by `run_pipeline.py::update_config()` after every run. After batch run, config retains last-processed session's path. No per-run config snapshots exist. | `run_pipeline.py:update_config()` code; config snapshot absent from `derivatives/step_00_config/` |

### B3. Scientific/Methodology Validity Issues

| Finding ID | Source | Description |
|-----------|--------|-------------|
| **F7-1 CRITICAL** | v2_feature_engine / parquet schema | Hips ATF = 0 permanently. `Hips__lin_vel_rel_mag` is identically 0 (root joint). `compute_noise_floor` returns V=1.0 mm/s guard, ATF=0/N=0.0. ATF_axial group biased. Spec includes Hips in axial group without addressing this. **Structural constraint, not a code bug.** Spec amendment needed. |
| **F7-3 HIGH** | v2_feature_engine | `compute_quality_gates` uses `max(joint_art_rates)` not OR-union. Implementation is LESS strict than spec. Should use `1.0 - clean_fraction_pca`. |
| **F7-4 HIGH** | v2_feature_engine | `validate_reference()` checks threshold 0.30; spec requires 0.20 for reference sessions specifically. |
| **F7-7 MEDIUM** | v2_feature_engine | Session-native D_eff/Gini use `sklearn explained_variance_` (ddof=1); T1-anchored uses `np.var(ddof=0)`. Minor inconsistency across analyses. |
| **F-651-3** | S02 | Bone QC CV rises T1→T2→T3 (0.35→1.01→0.69%). T2 reaches SILVER (3 alerts). Gradual drift over measurement timepoints — plausibly real marker placement inconsistency. |
| **F-651-5** | S05 | `t_pose_failed = null` (not `false`) for `least_motion_window_fallback` sessions. Code checking `if t_pose_failed:` would miss these cases. |

### B4. Parquet Schema / ML Readiness Issues

| Finding ID | Description |
|-----------|-------------|
| **10 constant-zero columns** | `Hips__lin_{rel,vel,acc}_{x,y,z,mag}` = 0.000 for all 16,914 frames. No ML information content. Should be documented or excluded. |
| **Schema asymmetry** | `raw_rel_omega_mag`, `raw_rel_alpha_mag`, `raw_rel_rotvec_*`, `raw_rel_rotmag` absent. Only zeroed representations have magnitudes. ML models needing raw-relative magnitudes must compute from components. |
| **No time index** | Index is `RangeIndex(0…16913)`, not time-indexed. `time_s` column carries actual timestamps. Must document window-slicing convention for ML. |
| **No parquet metadata fields** | `filter_psd_verdict`, `ref_is_fallback`, `pipeline_version` absent from parquet file metadata. Downstream provenance is invisible. |
| **On-disk larger than uncompressed** | 126.3 MB on disk vs 104.2 MB in-memory. Compression ratio 0.8×. Consider `snappy` compression or float32 downcast for float64 columns. |
| **is_hampel_outlier = 0 universally** | Despite Hampel filtering activity in S04, `is_hampel_outlier` column is all-False. Bug in flag propagation from S04 to S06 parquet. |

### B5. Code / Spec Alignment Gaps

| Finding ID | Description |
|-----------|-------------|
| **C1 HIGH** | Three-generation methodology coexistence: v1.4 / v2.0 / v3.0. `Thesis_Analytical_Pipeline.md` (v1.4) is out of date but still present and linked. |
| **C2 CRITICAL** | Two active downstream engines: `core_kinematics_engine.py` (3+3+1 legacy features) and `v2_feature_engine.py` (v3.0 features). Both exist in `src/`. |
| **C3 CRITICAL** | `core_kinematics_engine.py` uses bare `from pulsicity import` (not `from src.pulsicity import`) — import will fail if called from outside notebook context. |
| **Q-EXT3b/3c FAIL** | S01 does not extract `Capture Frame Rate`, `Export Frame Rate`, `Rotation Type`, `Length Units` from CSV header; no frame number continuity check. |
| **Q-EXT4a FAIL** | S06 has no `|q|≈1.0` assertion with logging. Silent per-frame renormalization only. |
| **F-INT5** | No unified `pipeline_version` field. S01=`v2.6_calibration_enhanced`, S04=`v3.1_3stage_dynamic_rms_chunked`, S06=no version. |
| **NB08 out-of-sync** | S08 Engineering Audit references 16 runs but current derivatives have only 9. No papermill parameterization. |
| **v2_longitudinal.py absent** | `src/v2_longitudinal.py` not yet created. MVP-deferred. |
| **F7-10 LOW** | Only `dynamics` branch in v2_feature_engine. `pose` and `reach` branches raise `ValueError`. MVP-deferred. |

### B6. ADV-T3-01 — Deferred Research Task

**T3-01 T-pose window plausibility check status: DRAFT_PENDING_RESEARCH**

The 0.10 rad/s angular velocity threshold and fixed 8-second search window for the T-pose check in the fast QC system produce false alarms on real data (e.g., `651_T3_P2_R2`) even when the subject is known to be statically posed at recording start. The check must be redesigned before implementation.

Three user-identified candidate approaches:
1. **Threshold loosening:** Explore 0.15–0.30 rad/s; derive empirically from all 15 known-good sessions (not from a single failure case).
2. **Global minimum search:** Find the minimum-motion window globally; compare to a dynamically calibrated floor (e.g., 2× inter-session mean minimum) rather than a fixed absolute threshold.
3. **"Double-back" stability verification:** After finding the minimum-motion window, verify that surrounding ±2s windows show increasing motion (subject transitioning toward/away from pose), distinguishing "genuine T-pose" from "uniformly low-motion artifact."

Until calibrated: T3-01 emits INFO only. T3-07 (Hips position variance branch) may be implemented independently as a more stable proxy.

---

## C. Findings Already Evidence-Backed — Strong Phase 10 Candidates

These findings have concrete, session-specific evidence from ≥1 real recording and are ready for the keep/change/remove decision.

| Finding | Evidence sessions | Proposed action | Confidence |
|---------|-----------------|----------------|-----------|
| F-651-1: Dead session → hard FAIL gate | `651_T2_P2_R2` (5 frames, confirmed) | Add S01 `gate_01_status` = FAIL for < 30s / 3600 frames | **LOCKED BY USER DIRECTIVE** |
| F-INT1: S03 off-by-one frame drop | All 6 live 651 sessions + canonical 671 = 7/15 confirmed | Fix `n_target` formula to `+1`; add frame count logging to resample_summary | High confidence |
| F-651-4 / F7-2: ref_is_fallback not in parquet | `651_T3_P2_R2` (confirmed fallback, T3 timepoint) | Propagate `ref_is_fallback` from S05 JSON to S06 parquet metadata | High confidence |
| F-651-2: var_score=inf | `651_T2_P2_R2` reference_metadata.json confirmed | Guard variance calc; serialize as null | High confidence |
| F-651-5: t_pose_failed=null | `651_T3_P2_R2` reference_metadata.json confirmed | Set explicitly `False` for non-identity fallbacks | High confidence |
| F7-3: artifact fraction max() vs OR-union | v2_feature_engine.py code confirmed | Use `1.0 - clean_fraction_pca` instead of `max(joint_art_rates)` | Code confirmed |
| F7-4: validate_reference threshold 0.30 vs 0.20 | v2_feature_engine.py code confirmed | Change threshold constant to 0.20 | Code confirmed |
| F-INT3: REVIEW_OVERSMOOTHING not in parquet | S04 filtering_summary JSON confirms flag; S06 parquet confirmed absent | Write `filter_psd_verdict` to parquet metadata at S06 write time | Medium confidence |
| F-INT2: config mutation in-place | run_pipeline.py code confirmed | Implement per-run config snapshot `derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml` | Code confirmed |
| is_hampel_outlier all-False | Phase 6 parquet inspection confirmed | Fix S04→S06 flag propagation | High confidence |
| F7-1: Hips ATF=0 permanently | Root-joint physics + pulsicity code confirmed | Amend METHODOLOGY_SPEC_v2.md §ATF_axial to exclude Hips; add INFO annotation in fast QC output | Structural, confirmed |

---

## D. Findings That Must NOT Be Implemented Yet

These items are blocked pending Phase 10 decision gate. Do not write code for any of the following until Phase 10 classifies them.

| Item | Reason to hold |
|------|---------------|
| **S04 adaptive filtering loop (REDESIGN_CANDIDATE)** | Phase 3 designated this a REDESIGN_CANDIDATE. Scope may require partial rewrite of filtering.py. Phase 10 must decide: minor tweak vs. structural rebuild. |
| **Step 02 velocity estimator upgrade (3-pt central diff)** | Phase 3 listed as LOCAL_REFACTOR with "pending Phase 4 confirmation." Phase 4 audit found MAD is dormant (0 detections), which changes the impact assessment. Phase 10 must decide if upgrade is still warranted. |
| **S01 two-tier FAIL/SUSPICIOUS flagging** | Phase 3 LOCAL_REFACTOR. Phase 4 found `optitrack_version=unknown` always. May not need two-tier if gate check is simpler. Phase 10 must confirm scope. |
| **omega_method = '5pt' as default** | Phase 3 LOCAL_REFACTOR (Low priority). Phase 4 noted `finite_difference_5point()` is actually a weighted smoother not a true 5-point stencil. The upstream naming is wrong. Phase 10 must decide rename vs. fix vs. leave. |
| **S02 gap fill SLERP** | Phase 4 found `gapfill_quaternions.py` SLERP is a placeholder, never called. Also gap detection has a boundary-condition bug at line 134. Touching S02 gap fill could break pristine sessions. Phase 10 must decide scope. |
| **QC sidecar vs. in-parquet contract** | Phase 6 recommended against adding many QC columns to the parquet before deciding the sidecar pattern. Phase 10 must decide where per-session QC metadata lives. |
| **T3-01 T-pose threshold** | ADV-T3-01 DRAFT_PENDING_RESEARCH. Needs empirical calibration across ≥10 sessions. Do not implement. |
| **v2_longitudinal.py** | Absent. MVP-deferred. Phase 10 must decide if timeline justifies implementation before thesis. |
| **Fast QC (NB08_Fast_QC) full implementation** | Phase 8 designed the spec. Phase 10 must decide priority against other tickets. The dead-session gate (T1-05) is the only item with a user directive that could jump the queue. |
| **F7-10: pose/reach branches in v2_feature_engine** | MVP-deferred. Not needed unless study adds non-dynamics analysis paths. |
| **Anti-aliasing filter in S03** | Phase 4 found it currently not applicable (120→120Hz). Design gap for future, not current ticket. |

---

## E. Known Overengineering Risks

These are areas where it would be easy to build too much. Phase 10 must challenge each.

| Risk | Description | Challenge question |
|------|-------------|------------------|
| **Gate chain** | Adding `gate_04_status`, `gate_05_status`, `gate_06_status` to all stage summaries is a large change for a study that currently has 0 failures below S02. | Is a sequential gate chain needed now, or is the S01 hard FAIL + batch_summary log sufficient for thesis N? |
| **NaN tracking chain** | Adding `n_nan_frames_input`/`n_nan_frames_output` to S02, S03, S04 summaries is thorough but all current 15 sessions are pristine (0 NaN frames after S02). | Is NaN tracking provenance worth implementing before any session shows non-zero NaN frames? |
| **Parquet metadata fields (many)** | A comprehensive metadata approach could add a dozen fields. | Which two or three metadata fields are genuinely required for the thesis claim? (Candidates: `ref_is_fallback`, `filter_psd_verdict`.) |
| **Config restructuring** | Adding section comments and skip_steps toggle to config_v1.yaml is low effort but could trigger a refactor cascade if tests use the config. | Is inline commenting (`# STABLE:`) sufficient, or does a structural YAML overhaul add real value? |
| **Per-session run status JSON** | Writing `{RUN_ID}__pipeline_run_status.json` to `derivatives/` adds infrastructure for a use case that is currently served by the batch summary. | Does the downstream audit or ML workflow actually need per-session co-located status, or is batch summary sufficient? |
| **F-INT5 unified version** | Adding `pipeline_version` to every stage summary is systemic. | Is a single `pipeline_version` in the per-run config snapshot sufficient? |
| **Two-tier S01 flagging** | FAIL vs. SUSPICIOUS is a schema addition that affects all downstream consumers. | Given the user directive for a hard 30s FAIL, is SUSPICIOUS a useful third state? |
| **SLERP in S02** | Implementing genuine quaternion SLERP for gap fill is technically correct but affects 0 frames across all 15 sessions (no gaps). | Is SLERP needed before N=20+? |
| **S08 papermill parameterization** | NB08 references 16 runs but has 9. Full fix requires papermill integration. | Is a parameterized NB08 needed for thesis, or is the batch_summary JSON adequate for the engineering audit section? |

---

## F. "Do Not Lose" Decisions — Locked Architecture

These decisions were made or confirmed during the audit. They must survive Phase 10 unchanged.

| Decision | Rationale | Where locked |
|----------|-----------|-------------|
| **`enforce_cleaning = false` (default)** | `enforce_cleaning=true` causes silent in-place SLERP-repair of critical frames. Ground truth integrity takes priority. `kinematic_repair.py` stays opt-in diagnostic only. | Phase 3 decision reversed and locked |
| **Scalar-last quaternions `[x,y,z,w]`** | SciPy convention throughout. scikit-kinematics uses scalar-first `[w,x,y,z]`. Never copy quaternion code from scikit-kinematics without transposing. | Phase 4.5 confirmed on all 9+ sessions |
| **Do NOT adopt Pose2Sim `zero == missing` logic** | Zero is a valid position in the Gaga pipeline (Hips root = 0 by definition). Adopting this convention would corrupt all root-relative features. | Phase 4.5 external standards audit |
| **Do NOT switch `omega_method` to `5pt` as default** | `finite_difference_5point()` in the codebase is a weighted smoother, not a true 5-point stencil. Default is `quat_log` (geometrically correct). Changing default requires renaming or fixing the 5pt function first. | Phase 3 LOW priority; Phase 4 S06 audit |
| **Do not add many QC columns to parquet before deciding sidecar contract** | Adding columns has compression and schema-versioning implications. Decide the QC data contract in Phase 10 before writing columns. | Phase 6 ML readiness recommendation |
| **Do not rewrite Step 06 (kinematics engine)** | Step 06 is the most technically correct stage. `quat_log` is the correct default method. `wbc_com` and all velocity/acceleration features are structurally sound. Only specific flag propagation fixes needed. | Phase 4 S06 audit; Phase 6 confirmation |
| **Do not implement adaptive filtering loop until Phase 10 classifies it** | The loop is a REDESIGN_CANDIDATE (Phase 3). Implementation scope is unknown. REVIEW_OVERSMOOTHING verdict is universal — the fix affects all 15 sessions and could change all features. | Phase 3 explicit |
| **Keep pandas/parquet architecture** | 16,914 × 803 in 104 MB fits in RAM. Parquet gives compression + typed schema. No case for switching to HDF5 or Zarr at current N. | Phase 6 ML readiness |
| **Hips excluded from axial ATF group** | Hips ATF = 0 permanently (root joint, `lin_vel_rel_mag = 0` always). Including Hips in axial group biases ATF_axial downward. Spec must be amended, not the pipeline. | Phase 7 F7-1 CRITICAL |
| **`pulsicity.compute_noise_floor` interface is correct** | Signature `(df, segment, cfg, *, static_baseline_guard_mms=50.0, noise_floor_guard_mms=1.0)` is compatible with v2_feature_engine call. Do not change this interface. | Phase 7 confirmed |
| **30s / 3600-frame S01 hard FAIL** | USER DIRECTIVE LOCKED. `gate_01_status = FAIL` for any session under 30 seconds at 120 Hz. Dead sessions are botched recordings, not recoverable. | Phase 5.5 user directive |

---

## G. Phase 10 Input List

Phase 10 must process the following inputs to produce: `10_anti_overengineering_review.md`, `10_keep_change_remove_decision_matrix.md`, and `10_rewrite_decision_gate.md`.

### G1. All audit findings requiring a KEEP/CHANGE/REMOVE/DEFER decision

The following items need an explicit decision. They are NOT yet approved for implementation.

**Safety/data-integrity tier (user-directive-locked or CRITICAL):**
1. S01 hard FAIL gate for < 30s / 3600 frames (F-651-1 user directive → implement)
2. S03 off-by-one frame drop fix + frame count logging in resample_summary (F-INT1 → fix scope?)
3. `ref_is_fallback` propagation from S05 JSON to S06 parquet metadata (F-651-4, F7-2 → implement)
4. `var_score` guard against Infinity (F-651-2 → implement, tiny fix)
5. `t_pose_failed = False` (not null) for fallback sessions (F-651-5 → implement, tiny fix)
6. Hard exclude flag for dead sessions in v2_feature_engine (F7-5 → implement)

**Code-spec gap tier (confirmed in code):**
7. Artifact fraction fix in `compute_quality_gates`: max() → OR-union (F7-3)
8. `validate_reference()` threshold 0.30 → 0.20 (F7-4)
9. `is_hampel_outlier` propagation fix S04→S06 parquet (Phase 6)
10. `filter_psd_verdict` in parquet metadata (F-INT3)

**Config / provenance tier (Medium priority):**
11. Per-run config snapshot `derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml` (F-INT2)
12. Unified `pipeline_version` strategy (F-INT5)
13. S01 metadata extraction: capture frame rate, rotation type, length units (Q-EXT3b)
14. Frame number continuity check in S01 (Q-EXT3c)

**Quality / design tier (REDESIGN_CANDIDATE or deferred):**
15. S04 adaptive dance-band correction loop (REDESIGN_CANDIDATE from Phase 3)
16. Fast QC script full implementation (NB08_Fast_QC, Phase 8 spec)
17. T3-01 ADV research task (DRAFT_PENDING_RESEARCH, ADV-T3-01)
18. Step 02 velocity estimator upgrade (3-pt central diff, Phase 3 LOCAL_REFACTOR)
19. S02 gap fill label mismatch fix (Q-EXT1b)
20. `|q|≈1.0` assertion with logging in S06 (Q-EXT4a)
21. NaN frame count logging in S04 input (Q-EXT1a)
22. QC sidecar vs. in-parquet metadata contract decision
23. S08 NB08 out-of-sync fix + papermill parameterization
24. Gate chain (S04/S05/S06 gate fields)

**METHODOLOGY_SPEC amendments needed:**
25. Amend METHODOLOGY_SPEC_v2.md §ATF_axial: exclude Hips from axial group
26. Resolve Hips D_eff bias note (structural, not code)
27. Clarify MEDIUM confidence trigger criteria in reference session spec

### G2. Open questions from earlier phases

| Q# | Question |
|----|---------|
| Q2 | Add supersession header to `Thesis_Analytical_Pipeline.md`? |
| Q4 | Who is the third subject? Is study N=2 or N=3? |
| Q5 | Keep `09_Subject_Exploration_Dashboard.ipynb` as legacy, or replace with v2? |
| Q8 | NB10 broken (imports `legacy/EDA_PCA.py`): deprecation header or update import? |

### G3. Key architectural questions for Phase 10 to answer

1. **Harden vs. Rebuild decision:** Does the pipeline need a partial rebuild of S02/S03, or are targeted fixes to S01 gate + S03 frame count + S06 metadata sufficient for thesis-grade claims?
2. **Parquet schema contract:** Is the current 803-column schema stable for implementation tickets, or does Phase 10 want to add/remove columns before locking?
3. **QC data placement:** Does QC metadata (REVIEW_OVERSMOOTHING verdict, ref_is_fallback, etc.) go into parquet file metadata (PyArrow `schema.metadata`), a sidecar JSON, or new parquet columns?
4. **Test framework priority:** Which of the 12 new unit tests (U-NEW-01 to U-NEW-12) must pass before any implementation ticket can be merged?
5. **v2_longitudinal.py priority:** Is longitudinal analysis in scope for the thesis pipeline, or deferred to post-submission?
6. **S04 adaptive loop gate:** Is the REVIEW_OVERSMOOTHING finding a blocker for thesis claims, or a known limitation to document?

### G4. "Do not lose" intellectual property

FUTURE_FEATURES_SALVAGE.md records:
- NB07 (Pulsicity metrics: PPM, IPI_CV, SPARC, noise floor V) — archived to `legacy/`, parameters preserved
- NB09 (ATF heatmap, longitudinal summary plots) — archived, visual design preserved
- NB10 (3D convex hull, SampEn, centroid displacement, density shift) — archived, mathematical specs preserved
- Key parameters: `noise_floor_guard_mms=1.0`, `prominence_multiplier=0.5σv`, T1-anchored PCA design

These are not in scope for Phase 10 implementation decisions but must not be deleted.

---

## H. Draft Prompt for Tomorrow — Phase 10

```
You are the Anti-Overengineering Review Agent running Phase 10 of the Gaga Pipeline audit.

Phases 0–9 are fully complete. The audit has produced a comprehensive set of findings across
all pipeline stages, the parquet schema, and the methodology spec. You now face a decision gate:
before implementation begins, challenge every proposed change for necessity, scope, and thesis
relevance.

Read first (in order):
1. audit_outputs/HANDOFF_END_OF_DAY_BEFORE_PHASE_10.md  ← primary input (this file)
2. audit_outputs/HANDOFF_CURRENT.md  ← per-phase summaries
3. audit_outputs/03_target_skeleton_draft.md  ← Phase 3 architectural decisions
4. audit_outputs/09_testing_and_regression_plan.md  ← 12 new tests and 4 golden sessions

Phase 10 goal: produce an honest, adversarial classification of every proposed change using
the "what is the minimum required to support thesis-grade claims?" lens.

Your task is to produce THREE output files:

### File 1: audit_outputs/10_anti_overengineering_review.md
For every finding in Section G1 of the handoff document (items 1–27), write one paragraph:
- What problem does this fix?
- What breaks if we do NOT fix it?
- What is the blast radius if we DO fix it?
- Is this required for thesis claims, or "nice to have"?
- Recommendation: IMPLEMENT_NOW / IMPLEMENT_LATER / DOCUMENT_ONLY / REMOVE

### File 2: audit_outputs/10_keep_change_remove_decision_matrix.md
A table with columns:
  Finding ID | Category | Current state | Proposed change | Decision | Rationale | Ticket size

Categories: SAFETY | CORRECTNESS | PROVENANCE | QUALITY | PERFORMANCE | COSMETIC

Decision values: KEEP_AS_IS | CHANGE_TARGETED | CHANGE_STRUCTURAL | REMOVE | DEFER_POST_THESIS

### File 3: audit_outputs/10_rewrite_decision_gate.md
Answer the four strategic questions:
1. Is a targeted fix strategy (CHANGE_TARGETED for individual findings) sufficient for thesis
   claims, or is a partial stage rebuild required?
2. Which stage, if any, is a genuine rebuild candidate? (S02, S03, S04, S08 are the candidates.)
3. What is the minimum implementation set that lets 671_T1_P2_R1 and 651_T1_P2_R1 pass all
   12 new unit tests with correct golden values?
4. What is the FIRST implementation ticket (Phase 13 ticket 001)?

Mode: Read-only analysis and decision writing. No code changes.
Stop after writing all three files. Update audit_outputs/audit_index.md to mark Phase 10 COMPLETE.
```

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Total audit phases completed | 10 (Phases 0–9) |
| Stages fully audited | 7 (S01–S06, S08) |
| Sessions examined | 15 (6×651, 9×671) |
| CRITICAL findings | 4 (F-651-1, F-651-4/F7-2, F7-1, C2/C3) |
| HIGH findings | 8 (F7-3, F7-4, F7-5, F-INT2, Q-EXT1b, C1, F-651-2, REVIEW_OVERSMOOTHING propagation) |
| MEDIUM findings | 10+ (F-INT1, F-INT3-5, F-651-3/5, F7-6–8, Q-EXT3b/3c, Q-EXT4a, etc.) |
| New unit tests specified | 12 (U-NEW-01 to U-NEW-12) |
| Golden regression sessions | 4 |
| Locked user directives | 2 (30s/3600-frame hard FAIL; enforce_cleaning=false) |
| Phase 10 input items (G1) | 27 |
| Open questions | 4 (Q2, Q4, Q5, Q8) |
