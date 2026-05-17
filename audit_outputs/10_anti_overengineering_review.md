# 10 Anti-Overengineering Review

**Date:** 2026-05-17
**Auditor:** Phase 10 Agent (Claude Sonnet 4.6)
**Mode:** Review-only. No code changes. No notebook edits. No parquet modifications.
**Inputs:** All Phase 0–9.5 audit outputs, GAGA_PIPELINE_AGENT_WORK_PLAN.md, HANDOFF_END_OF_DAY_BEFORE_PHASE_10.md
**Governing document:** GAGA_PIPELINE_AGENT_WORK_PLAN.md §Phase 10, §5.4, §5.5, §5.7

---

## Model Decision Note

- **Recommended model for this phase:** Sonnet (analysis and decision writing completed at this tier)
- **Is Opus review required before Phase 11?** Yes — recommended but not mandatory
- **Reason:** Phase 10 produces the strategic rewrite decision and the final keep/change/remove matrix. These decisions gate all Phase 13 implementation tickets. An Opus review of `10_rewrite_decision_gate.md` before Phase 11 final skeleton writing is recommended if the user wants maximum confidence in the hybrid_modular_rebuild classification. It is not mandatory if the user accepts the evidence-based rationale presented here. Sonnet produced this analysis with full access to all 15 sessions of evidence and 27 identified findings.

---

## Executive Verdict

The pipeline is **scientifically sound at the algorithm level but architecturally immature at the infrastructure level.** The core computation chain — PCHIP gap fill, SLERP resampling, Winter Butterworth filtering, Markley quaternion mean, quat_log angular velocity, SavGol derivatives, de Leva CoM, ISB Euler angles, T1-anchored PCA — is validated, correct, and must be preserved. No algorithm should be replaced.

The surrounding architecture — gates, provenance, config snapshots, stage contracts, QC metadata, error propagation, method labeling — has systematic gaps that were confirmed across all 15 sessions and both subjects. These are not cosmetic issues: they allow dead sessions to pass all stages silently (F-651-1), produce features on wrong reference poses without flagging (F-651-4), drop one frame from every session without logging (F-INT1), and lose run configuration permanently after every run (F-INT2).

**Strategic verdict: hybrid_modular_rebuild.** Preserve all validated algorithms. Rebuild the surrounding infrastructure layer: gates, config snapshots, stage contracts, metadata propagation, QC sidecars, and provenance fields. Fix the five code-spec gaps in v2_feature_engine.py. Implement the S04 adaptive dance-band correction loop as a bounded redesign inside filtering.py. Do not rewrite from scratch.

**Anti-overengineering enforcement:** 10 of the 27 input items are rejected or deferred. The Minimal thesis-grade implementation set has 13 core items. Everything else is documented, deferred, or rejected as premature.

---

## What Should Be Kept As-Is

These components are **correct, validated, and must not be modified or rewritten.** Any change here requires extraordinary evidence.

| Component | Location | Evidence | Keep decision |
|---|---|---|---|
| `parse_optitrack_csv()` S01 parser | `src/parse.py` or NB01 | 51/51 joints correct, 0 NaN, 0 parse errors on all 15 sessions | KEEP_AS_IS |
| PCHIP gap fill (positions) | S02 gap fill code | C1-continuous, monotonicity preserved; 0 active gap fill frames in 15 sessions (all pristine) | KEEP_AS_IS |
| SciPy Slerp resampling (quaternions) | S03 | Geodesically correct; `time_grid_std = 0.0` confirmed | KEEP_AS_IS |
| CubicSpline resampling (positions) | S03 | C2-continuous; needed for clean velocity derivatives | KEEP_AS_IS |
| Hampel filter (Stage 2, S04) | `filtering.py` | 0.09% modification rate; surgical action only; complementary to Stage 1 | KEEP_AS_IS |
| Markley quaternion mean (T-pose reference) | S05 | Geodesic mean on S³; mathematically optimal (Markley et al. 2007) | KEEP_AS_IS |
| quat_log angular velocity method | S06 | Respects SO(3) manifold; standard in biomechanics | KEEP_AS_IS |
| SavGol velocity/acceleration derivatives | S06 | Standard noise-robust derivative; well-calibrated for mocap at 120 Hz | KEEP_AS_IS |
| ISB Euler angles (Wu et al. 2005) | S06 | Correct joint-specific ZYX/XYZ sequences | KEEP_AS_IS |
| de Leva CoM model (1996) | S06 | Standard 16-segment model; already flagged by bone_qc_fail_flag | KEEP_AS_IS |
| NaN Guard + Continuity enforcement | S06 | < 0.1% threshold correct; 0 NaN, 0 flips in reference run | KEEP_AS_IS |
| Root-relative position computation | S06 | Correctly removes global translation; Hips-zeroed by definition | KEEP_AS_IS |
| P2-only filter in v2_feature_engine.py | `v2_feature_engine.py` | Explicit code gate confirmed; prevents session-type contamination | KEEP_AS_IS |
| T1-anchored PCA design | `v2_feature_engine.py` | Correctly implements METHODOLOGY_SPEC_v2.md §PCA; prevents double-dipping | KEEP_AS_IS |
| `pulsicity.compute_noise_floor` interface | `pulsicity.py` | Compatible with v2_feature_engine call; `noise_floor_guard_mms=1.0` guard correct | KEEP_AS_IS |
| ATF NaN-safe computation | `v2_feature_engine.py` | NaN-safe check on v_mag > V confirmed; Phase 7 confirmed ✓ | KEEP_AS_IS |
| Contiguous-run TM logic | `v2_feature_engine.py` | Correctly avoids artifact-masked discontinuities in path length | KEEP_AS_IS |
| `enforce_cleaning = false` default | `config_v1.yaml` | LOCKED — silent in-place SLERP-repair of critical frames violates ground truth integrity | KEEP_AS_IS |
| Scalar-last quaternion convention `[x,y,z,w]` | All pipeline stages | SciPy convention throughout; scikit-kinematics is scalar-first — never mix | KEEP_AS_IS |
| Legacy archive (`core_kinematics_engine.py`, `EDA_PCA.py`) | `legacy/` | Already archived; must not be revived without explicit user decision | KEEP_AS_IS |
| Quaternion median filter (Stage 4, S04) | `filtering.py` | Targets hemisphere flips; geodesic error negligible at 5-frame window | KEEP_AS_IS |
| Stage 2 Hampel per-joint 5-frame 3σ window | `filtering.py` | Window size correctly chosen (42 ms < minimum dance event); cannot distort dance dynamics | KEEP_AS_IS |

**Algorithm locked decisions (from Phase 3 + later confirmation):**
- Do NOT adopt `Pose2Sim` zero == missing convention
- Do NOT switch `omega_method` to `5pt` as default until the function is renamed or verified (current `finite_difference_5point()` is a weighted smoother, not a true 5-point stencil — Phase 4 confirmed)
- Do NOT implement `v2_longitudinal.py` in thesis scope (absent and MVP-deferred)

---

## What Should Be Fixed with Low-Risk Targeted Changes

These are fixes with **high thesis necessity, small blast radius, and no scientific risk.** Implement early in Phase 13.

### F-001: S01 Minimum Session Gate (F-651-1 user directive)
**Problem:** Dead session (651_T2_P2_R2, 5 frames, 0.03s) passes all 6 pipeline stages. Kinematics computed on 4 frames.
**What breaks without fix:** Scientific artifacts in published kinematics parquet; feature engine computes meaningless scalars on dead sessions.
**Blast radius of fix:** Add one duration check and one gate field (`gate_01_status`) to S01. The dead session's outputs must be regenerated or marked invalid. No change to any other stage.
**Thesis required:** YES — USER DIRECTIVE LOCKED. Cannot publish a dataset containing kinematics from a 0.03s session.
**Overengineering risk:** None. One condition, one field.
**Recommendation:** LOW_RISK_FIX — Ticket 002 in Phase 13.

---

### F-002: S03 Off-by-One Frame Drop (F-INT1)
**Problem:** `n_target = round(duration × fs)` drops last frame silently. Confirmed universal — S01=16,915 → S04=16,914 across all 7+ confirmed sessions.
**What breaks without fix:** Every downstream parquet has exactly 1 wrong frame count; frame count assertions in golden regression tests fail; published results cannot be exactly reproduced.
**Blast radius of fix:** Fix `n_target` formula to `+1`; add frame count logging to resample_summary. ALL session parquets must be regenerated — this changes all golden test frame counts from 16,914 to 16,915 (or equivalent). The golden baseline must be re-locked after fix.
**Thesis required:** YES — frame count integrity is a basic provenance requirement; wrong frame count is a detectable factual error.
**Overengineering risk:** None. One formula change.
**Recommendation:** LOW_RISK_FIX — Ticket 003 in Phase 13. **Note:** All golden session parquets must be regenerated and re-locked after this fix.

---

### F-003: ref_is_fallback Propagation to Parquet (F-651-4, F7-2)
**Problem:** `ref_is_fallback=True` not in kinematics parquet metadata → downstream feature engine computes ATF, TM, D_eff, Gini on `651_T3_P2_R2` using a wrong reference pose, without any warning.
**What breaks without fix:** One session's features (T3 timepoint for subject 651) are biased by wrong reference. Thesis longitudinal comparison T1→T3 is silent on this bias. Reviewer cannot discover it from outputs.
**Blast radius of fix:** Read S05 JSON at S06 write time; add one PyArrow metadata field. One-line change to S06 parquet write code.
**Thesis required:** YES — the biased session is within the thesis analytical dataset.
**Overengineering risk:** None.
**Recommendation:** LOW_RISK_FIX — Ticket 004.

---

### F-004: var_score Infinity Guard (F-651-2)
**Problem:** `var_score = Infinity` in `reference_metadata.json` for dead session — invalid JSON, causes parse failures.
**What breaks without fix:** Any downstream code reading reference_metadata.json for this session will fail or silently produce wrong values.
**Blast radius of fix:** One guard in variance calculation: `if n_frames == 0: var_score = None`. Tiny.
**Thesis required:** YES (defensive data integrity fix).
**Overengineering risk:** None.
**Recommendation:** LOW_RISK_FIX — Ticket 005.

---

### F-005: t_pose_failed=False Guard (F-651-5)
**Problem:** `t_pose_failed = null` (Python None) for fallback sessions. Code checking `if t_pose_failed:` silently misses these cases.
**What breaks without fix:** Silent error propagation; any quality gate checking `t_pose_failed` will pass fallback sessions incorrectly.
**Blast radius of fix:** Set explicitly `False` for non-identity fallbacks. One assignment.
**Thesis required:** YES (defensive fix; critical path for quality gate correctness).
**Overengineering risk:** None.
**Recommendation:** LOW_RISK_FIX — Ticket 005 (bundle with var_score guard — same function).

---

### F-006: Hard Exclude Flag in v2_feature_engine (F7-5)
**Problem:** Dead session gets `short_session=True` not `hard_exclude=True`; PCA engine may process it.
**What breaks without fix:** Dead session could contaminate group PCA statistics.
**Blast radius of fix:** Add dead_recording → hard_exclude check in `build_pca_engine()`. A few lines.
**Thesis required:** YES — dead sessions must not bias group statistics.
**Overengineering risk:** None.
**Recommendation:** LOW_RISK_FIX — Ticket 006.

---

### F-007: filter_psd_verdict Propagation to Parquet (F-INT3)
**Problem:** REVIEW_OVERSMOOTHING verdict not propagated to parquet. Universal finding (all 15 sessions). Downstream consumers cannot detect over-smoothed input without reading filtering_summary JSON separately.
**What breaks without fix:** Feature engine interprets over-smoothed data without warning; thesis methods section cannot cite filter quality per session from the primary dataset file.
**Blast radius of fix:** Read `filtering_summary.json` at S06 write time; add `filter_psd_verdict` to parquet metadata. One-line addition.
**Thesis required:** YES — universal finding affecting all features.
**Overengineering risk:** None. Single metadata field.
**Recommendation:** LOW_RISK_FIX — Ticket 007.

---

### F-008: Per-Run Config Snapshot (F-INT2)
**Problem:** `run_pipeline.py::update_config()` overwrites `config_v1.yaml` in-place. After any run, previous config state is lost. Cannot reproduce any run without git archaeology.
**What breaks without fix:** Reproducibility is not achievable. Thesis claims "all results reproducible from configuration" cannot be defended.
**Blast radius of fix:** Write YAML snapshot to `derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml` before any mutation. ~5 lines of code. No output changes.
**Thesis required:** YES — reproducibility is a thesis-grade requirement.
**Overengineering risk:** None. Storage cost: ~1 KB per session.
**Recommendation:** LOW_RISK_FIX — **Ticket 001 (first ticket).** Zero scientific risk. Immediate provenance gain.

---

### F-009: Artifact Fraction Fix (F7-3)
**Problem:** `compute_quality_gates` uses `max(joint_art_rates)` not OR-union. Less strict than spec. Should use `1.0 - clean_fraction_pca`.
**What breaks without fix:** Quality gates are systematically more lenient than spec; some multi-joint artifact sessions may pass that should be flagged.
**Blast radius of fix:** One expression change in `compute_quality_gates`. Affects `quality_df` for all sessions — some sessions may get different quality gate verdicts.
**Thesis required:** YES — quality gate must match spec for methodology defensibility.
**Overengineering risk:** None.
**Recommendation:** LOCAL_REFACTOR — Ticket 008. **Note:** Re-run quality_df after fix and verify no sessions change category unexpectedly.

---

### F-010: validate_reference() Threshold 0.20 (F7-4)
**Problem:** `validate_reference()` uses 0.30 threshold; spec requires 0.20 for reference sessions.
**What breaks without fix:** Reference sessions with moderate pose error pass a too-lenient gate; downstream PCA could be anchored on a poor reference.
**Blast radius of fix:** Change one constant. May cause currently-passing sessions to be flagged.
**Thesis required:** YES — reference quality directly affects ATF, D_eff, Gini, Gini_AP_ratio.
**Overengineering risk:** None.
**Recommendation:** LOW_RISK_FIX — Ticket 008 (bundle with F7-3).

---

### F-011: S02 Label Mismatch Fix (Q-EXT1b)
**Problem:** S02 logs say `pchip_single_pass` and `slerp` but actual code uses `np.interp` (linear) and scalar-normalize. Methodological misrepresentation in all 15 session logs.
**What breaks without fix:** Thesis methods section falsely claims PCHIP and SLERP are used in S02. These are actually used in S03, not S02.
**Blast radius of fix:** Update label strings in preprocessing.py. Log-only change. No computational change.
**Thesis required:** YES — methods section accuracy.
**Overengineering risk:** None. Pure label correction.
**Recommendation:** LOW_RISK_FIX — Ticket 009.

---

### F-012: METHODOLOGY_SPEC Amendment — Exclude Hips from ATF_axial (F7-1)
**Problem:** Hips ATF = 0 permanently (root joint, `lin_vel_rel_mag = 0` always). Spec includes Hips in axial group without addressing this. ATF_axial systematically biased downward.
**What breaks without fix:** ATF_axial does not represent axial movement; thesis H3 (ATF increases) may be quantitatively wrong.
**Blast radius of fix:** (a) Amend METHODOLOGY_SPEC_v2.md §ATF_axial definition. (b) Update `axial` joint group in v2_feature_engine.py to exclude Hips. (c) Recompute all ATF_axial values. (d) Re-lock golden test values.
**Thesis required:** YES — core feature definition error.
**Overengineering risk:** None. This is fixing a structural error, not adding complexity.
**Recommendation:** CHANGE_TARGETED — Ticket 010.

---

### F-013: Fast QC Script Implementation (Phase 8 spec)
**Problem:** No pre-pipeline QC script. Dead session (651_T2_P2_R2) was discovered after expensive pipeline runs, not at collection time.
**What breaks without fix:** Future bad recordings will not be caught until after full pipeline processing. The dead session gate (S01, F-001) catches the worst case, but fast QC catches problems before any pipeline step.
**Blast radius of fix:** New standalone file (`src/fast_qc.py`). Does not modify any existing stage.
**Thesis required:** MEDIUM — high practical value for future data collection; not strictly blocking for existing sessions (which are already processed).
**Overengineering risk:** LOW — the Phase 8 design is complete and conservative. Key risk: T3-01 T-pose threshold (ADV-T3-01) is still unvalidated; must remain INFO-only. T3-07 (Hips variance proxy) can be implemented independently.
**Recommendation:** LOCAL_REFACTOR — Ticket 012 (after all critical fixes). T3-01 stays INFO-only per ADV-T3-01 DRAFT_PENDING_RESEARCH.

---

## What Requires Local Refactor

These are bounded internal changes with no intended output change or with predictable, bounded output changes.

### F-014: is_hampel_outlier Propagation Fix (Phase 6)
**Problem:** is_hampel_outlier column = all-False in parquet despite Hampel filtering activity in S04.
**What breaks without fix:** Flag is misleading; users relying on it for frame-level filtering decisions will receive wrong information.
**Blast radius of fix:** Requires tracing the S04 Hampel mask output into S06 parquet write. Medium investigation required — the propagation path may not be straightforward. Affects one column in parquet.
**Thesis required:** MEDIUM — not directly used in F1-F5 but affects traceability.
**Overengineering risk:** None. This is a correctness fix.
**Recommendation:** LOCAL_REFACTOR — Ticket 011. Investigate S04 Hampel mask output path before implementing.

---

### F-015: S04 Adaptive Dance-Band Correction Loop (Phase 3 REDESIGN_CANDIDATE)
**Problem:** ALL 57 position columns flagged REVIEW_OVERSMOOTHING. Mean dance-band attenuation -4.68 to -5.51 dB. This affects ALL downstream features (ATF noise floor, TM path lengths, angular velocity magnitudes).
**What breaks without fix:** All thesis features are computed on systematically over-smoothed data. F1 ATF (suppressed noise floor), F2 TM (shorter paths). This is a known, universal quality limitation.
**Blast radius of fix:** Modify `filtering.py` to add post-filter feedback loop. Regenerate ALL 15 session parquets. ALL feature values change. ALL golden regression tests must be re-locked. This is the highest blast-radius item.
**Thesis required:** YES — but this is a "fix before final analysis" item, not a "fix before any analysis" item. The limitation can be documented as a sensitivity analysis until the fix is implemented.
**Overengineering risk:** LOW — the adaptive loop design is fully specified in Phase 3 S-04.3 and is bounded to filtering.py. The algorithm is: raise cutoff until dance-band delta ≥ -3 dB or reach correction ceiling.
**Recommendation:** REDESIGN_CANDIDATE (implement as bounded Phase 13 ticket after all low-risk fixes are done). This is the last major fix before final thesis analysis runs.

---

### F-016: NB08 Session Count Sync
**Problem:** NB08 references 16 runs but only 9 derivatives exist. Out-of-sync state.
**What breaks without fix:** Engineering audit notebook produces wrong counts; thesis methods section engineering audit is inaccurate.
**Blast radius of fix:** Update NB08 to read from current derivatives; no algorithm change.
**Thesis required:** MEDIUM — NB08 is used in thesis engineering validation section.
**Overengineering risk:** Low. Note: full papermill parameterization is deferred — just fix the session count and run manually.
**Recommendation:** LOCAL_REFACTOR — Ticket 013 (low priority; after critical fixes).

---

## What Requires Structural Change

### F-017: Spec Amendment — Hips D_eff Note (F7-1 downstream)
**Problem:** The 10 constant-zero Hips columns (`Hips__lin_vel_*`) have no ML information content. Phase 6 identified this as a schema asymmetry. The dynamics branch PCA uses `zeroed_rel_omega_mag` (which is non-zero for Hips), so D_eff is not affected. But any ML model using position/velocity features must exclude these constant columns.
**What breaks without fix:** ML models trained on parquet will include constant features (zero information); embeddings will be distorted.
**Blast radius of fix:** DOCUMENTATION ONLY — add explicit note to parquet schema docs and feature engineering notebooks. The zero columns are structurally correct (Hips is the root joint; position is always zero by definition). Do not remove columns from parquet.
**Thesis required:** LOW (for current thesis analysis). MEDIUM (for future ML use).
**Recommendation:** KEEP_WITH_DOCUMENTATION — document in Phase 11 final skeleton.

---

## What Requires User Decision

### UD-001: S04 Adaptive Loop Threshold (-3 dB vs. -1 dB)
The Phase 3 design uses -3 dB as the dance band preservation threshold. Q-ADP asks whether this is tight enough for high-velocity sessions. Phase 10 cannot resolve this without frequency analysis on ≥10 P2 sessions.
**Default recommendation:** Implement at -3 dB as designed. Document as a sensitivity parameter in `qc_thresholds.yaml`. Revisit after implementation.

### UD-002: omega_method = '5pt' as default?
Phase 3 recommended `omega_method = '5pt'` as a config default. Phase 4 found the current `finite_difference_5point()` is a weighted smoother, not a true 5-point stencil. Changing the default requires either: (a) renaming the function to reflect its actual behavior, or (b) implementing a genuine 5-point stencil. The current `quat_log` default is correct.
**Default recommendation:** KEEP quat_log as default. Rename `finite_difference_5point()` to `weighted_smoothing_5frame()` in a future cleanup ticket. Do not change default before rename.

### UD-003: gate_01_status only, or full gate chain?
Phase 10 recommends implementing only gate_01_status (S01 dead session hard FAIL) in Minimal v1. The full gate chain (S03/S04/S05/S06 gates) is deferred. User must confirm this is acceptable — the current pipeline will have gating at S01 only.
**Default recommendation:** Gate at S01 only for thesis. Full chain is Phase 14+ scope.

### UD-004: QC sidecar timing — after S06, or after feature engine?
`session_qc_report.json` aggregates stage JSONs from S01–S06. `feature_reliability_table.csv` needs feature engine output. They cannot be generated at the same time. User decision: separate generation steps, or combine into a single post-processing pass after v2_feature_engine runs?
**Default recommendation:** Two separate generation steps. session_qc_report.json at end of pipeline run; feature_reliability_table.csv at end of feature engine run.

### UD-005: Study N — is a third subject in scope?
Open question Q4 from Phase 1: "Who is the third subject? Is study N=2 or N=3?" This affects thesis scale and batch runner scope. Cannot be resolved in Phase 10.

---

## What Should Be Deferred

These items are explicitly deferred. They must be logged in a DEFERRED register for post-thesis or v2 implementation.

| Item | Source | Reason for deferral |
|---|---|---|
| Step 02 velocity estimator upgrade (3-pt central diff) | Phase 3 LOCAL_REFACTOR | MAD is dormant (0 detections); solving a non-observable problem |
| S01 two-tier FAIL/SUSPICIOUS flagging | Phase 3 LOCAL_REFACTOR | S01 hard FAIL gate (Ticket 002) is sufficient; SUSPICIOUS adds schema complexity for no current use case |
| S02 gap fill SLERP implementation | Phase 4 | SLERP gap fill never called; gap detection bug at line 134; touching gap fill risks pristine sessions |
| Unified pipeline_version field (F-INT5) | Phase 5 | Per-run config snapshot (Ticket 001) provides sufficient version provenance; per-stage version consistency is cosmetic |
| Gate chain S03/S04/S05/S06 | Phase 5 | 0 failures in current data beyond dead session; S01 gate sufficient for thesis N; full chain is post-thesis infrastructure |
| NaN frame count logging at S04 input (Q-EXT1a) | Phase 4.5 | All 15 sessions have 0 NaN frames at S04 input; the log field is correct but the value is always 0 for current data |
| |q|≈1.0 assertion with gate (Q-EXT4a) | Phase 4.5 | Current S06 silent renormalization has produced 0 detected issues; add logging only (see below) |
| T3-01 T-pose threshold calibration (ADV-T3-01) | Phase 8 | DRAFT_PENDING_RESEARCH; needs ≥15 session calibration; remains INFO-only |
| Cyclic anchor QC | Phase 9.5 | No event markers or cyclic annotations exist for any current session |
| Day-level QC aggregation | Phase 9.5 | Requires stable session-level QC first |
| Filter sensitivity analysis (multiple cutoffs per session) | Phase 9.5 | Too expensive per session; offline_batch_audit_only |
| session_reliability_score (numeric 0–1) | Phase 9.5 | Needs calibration on N≥20 sessions; categorical labels sufficient for thesis |
| v2_longitudinal.py | Phase 7 | MVP-deferred; post-thesis scope |
| pose/reach branches in v2_feature_engine (F7-10) | Phase 7 | MVP-deferred; raises ValueError; not needed for dynamics branch |
| S08 papermill parameterization | Phase 4 | NB08 session count fix is sufficient; papermill adds complexity with no current benefit |
| optitrack_version extraction fix (always "unknown") | Phase 4 | The version is not available in the CSV header; would require Motive version mapping; low value |
| Anti-aliasing filter before downsampling | Phase 4 | Currently not applicable (120→120Hz); design note for future |

---

## What Should Be Rejected / Not Adopted

These are explicitly rejected. They must not enter Phase 13 tickets.

| Item | Reason |
|---|---|
| Per-feature reliability columns inside `kinematics_master.parquet` | Overengineering. 803 columns would grow proportionally with feature count. Sidecar is the only correct approach. |
| QC plots for every PASS session | Too many files; no automated value; WARN/FAIL/golden sessions only. |
| Filter sensitivity analysis on every session | 3-5× pipeline runtime per session; offline_batch_audit_only. |
| Automatic cyclic anchor detection | No algorithm; no calibration; no data; not useful for current dataset. |
| Structured-task QC module | No reliable annotations; violates session-type-agnostic principle. |
| Automatic QC dashboard (generalized) | NB08/NB09 dashboards exist; fix the out-of-sync one rather than building new. |
| ROM calibration as hard FAIL gate | .mcal files deleted from repository for historical sessions; would immediately fail historical data. |
| Numeric session_reliability_score formula | Scientifically significant; needs calibration; categorical PASS/WARN/FAIL sufficient for thesis. |
| Adopting Pose2Sim `zero == missing` convention | Zero is valid in this pipeline (Hips root = 0 by definition). Adoption would corrupt all root-relative features. |
| Adopting scikit-kinematics quaternion convention | Scalar-first `[w,x,y,z]` vs our scalar-last `[x,y,z,w]` — silent mismatch would corrupt all quaternion computations. |
| Full raw-to-processed trajectory comparison in v1 | Requires coordinate-frame alignment across F-INT1 frame drop; premature before F-INT1 fix. |
| Full gap boundary acceleration/jerk artifact test in v1 | Requires gap logs S02 doesn't produce; gapfill bug at line 134 unresolved. |
| Building `src/v2_longitudinal.py` before session QC stable | Out of scope; data integrity must be confirmed first. |
| Adding `{joint}__bone_qc_flag` per-frame columns to parquet | Phase 3 proposed this; Phase 10 rejects it as overengineering. A single `bone_qc_status` field in parquet metadata is sufficient. |

---

## Minimal Thesis-Grade Implementation Set

These are the changes required before thesis-grade claims are defensible. Nothing more. Everything else is deferred or rejected.

**Tier 1 — Data integrity (must fix before any analysis):**
1. F-008: Per-run config snapshot (Ticket 001)
2. F-001: S01 hard FAIL gate (Ticket 002)
3. F-002: S03 off-by-one frame fix (Ticket 003)
4. F-003: ref_is_fallback propagation (Ticket 004)
5. F-004 + F-005: var_score guard + t_pose_failed guard (Ticket 005)
6. F-006: Hard exclude flag in v2_feature_engine (Ticket 006)
7. F-007: filter_psd_verdict propagation (Ticket 007)

**Tier 2 — Methodology correctness (must fix before thesis analysis):**
8. F-009 + F-010: Artifact fraction fix + validate_reference threshold (Ticket 008)
9. F-011: S02 label mismatch fix (Ticket 009)
10. F-012: Spec amendment + Hips excluded from ATF_axial computation (Ticket 010)

**Tier 3 — Traceability and QC (must implement before thesis submission):**
11. F-014: is_hampel_outlier propagation fix (Ticket 011)
12. F-013: Fast QC script (Ticket 012)
13. Session QC sidecar outputs: `session_qc_report.json` + `feature_reliability_table.csv` (Ticket 014)
14. NB08 session count fix (Ticket 013)

**Tier 4 — Algorithm fix (implement after Tier 1–3, before final analysis runs):**
15. F-015: S04 adaptive dance-band correction loop (Ticket 015)

Total: 15 implementation tickets. This is the complete Minimal v1 scope.

---

## Overengineering Risks

Ranked by severity:

1. **Adding per-feature reliability columns to parquet** — Schema bloat. 803 → 1000+ columns. Destroys ML/DL readiness. Hard no.
2. **Filter sensitivity analysis on every session** — Would 5× pipeline runtime. No benefit for known-oversmoothed-but-uniform data. `offline_batch_audit_only`.
3. **Full gate chain (S03–S06)** — Zero failures in current data below S01. Gate chain for 9 sessions with 0 failures is premature infrastructure.
4. **Cyclic anchor detection before data exists** — No algorithm, no calibration, no annotations. Building detection before data is the definition of speculative engineering.
5. **session_reliability_score formula** — Scientific risk: formula could produce wrong rankings on thesis data. Categorical labels are safer and sufficient.
6. **NaN tracking chain (n_nan_frames_input/output per stage)** — All 15 sessions have 0 NaN frames after S02. The tracking chain adds infrastructure for a scenario not yet observed.
7. **Two-tier S01 FAIL/SUSPICIOUS** — S01 hard FAIL gate already handles the critical case. SUSPICIOUS adds a schema element with no current use case.
8. **S02 gap fill SLERP** — Never called in 15 sessions. SLERP for zero-frame gap fill events is wasted infrastructure.
9. **Papermill parameterization of NB08** — NB08 fix is a session count update, not a batch automation problem. Papermill adds overhead for a notebook run manually for thesis.
10. **optitrack_version extraction** — This field is always "unknown" because the CSV header doesn't expose it in a standard way. Fixing it requires reverse-engineering Motive version mapping. Low value.

---

## Final Recommendation

**Adopt hybrid_modular_rebuild.** Implement 15 tickets in Phase 13. The order is: Tier 1 (data integrity) → Tier 2 (methodology correctness) → Tier 3 (traceability) → Tier 4 (algorithm fix). Do not begin final thesis analysis runs until the S04 adaptive loop (Ticket 015) is implemented and all golden session parquets are re-locked.

Do not start Phase 11 (final target skeleton) until the user approves this Phase 10 review.

---

*Phase 10 anti-overengineering review complete.*
