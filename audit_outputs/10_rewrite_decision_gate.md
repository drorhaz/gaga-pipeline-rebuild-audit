# 10 Rewrite Decision Gate

**Date:** 2026-05-17
**Phase:** 10 — Anti-Overengineering Review and Rewrite Decision Gate
**Mode:** Strategic decision. No code changes.
**Governing document:** GAGA_PIPELINE_AGENT_WORK_PLAN.md §Phase 10

---

## Model Decision Note

- **Recommended model for this phase:** Sonnet (strategic decision produced at this tier)
- **Is Opus review required before Phase 11?** Yes — recommended
- **Reason:** This file determines the implementation strategy for the entire pipeline. The hybrid_modular_rebuild classification is supported by evidence from all 15 sessions and all 10 audit phases, but an Opus review of this file before Phase 11 final skeleton writing is recommended if the user wants independent challenge of this strategic judgment. The decision is not close — full rewrite and targeted patches only are both clearly wrong — but the exact scope of "what to rebuild vs. what to preserve" has long-term consequences for Phase 13 implementation effort and thesis timeline.

---

## A. Recommended Implementation Strategy

**`hybrid_modular_rebuild`**

This is the confirmed recommendation. It was the entering hypothesis and is supported by the evidence.

---

## B. Why hybrid_modular_rebuild

### Why NOT `targeted_fixes_only`

Targeted fixes would address the individual bugs (dead session gate, ref_is_fallback propagation, var_score guard, etc.) but would not address the systematic architectural gaps that allowed these bugs to exist and be invisible for 15 sessions:

- No per-run config snapshot (F-INT2): means every run's configuration is permanently lost — a systemic reproducibility failure, not an isolated bug.
- No gate chain beyond S02 (F-INT1, F-INT3): a dead session passed all 6 stages silently because there is no architecture for stage-level safety contracts. Fixing one gate without the surrounding contract layer will leave the next class of failures equally invisible.
- No QC metadata propagation pattern: ref_is_fallback, filter_psd_verdict, is_hampel_outlier are independently missing for the same structural reason — there is no established pattern for how stage-level QC signals become parquet-level provenance fields.
- Method label mislabeling (Q-EXT1b): S02 logs a different method than what the code implements — this is not an isolated mistake; it reflects an absent standard for how stage implementations document themselves.
- Three inconsistent bone QC threshold systems (S02): NB02, qc.py, forensic_report.py each independently implement the same check. This redundancy without consolidation is a structural pattern.

Targeted fixes alone would produce a pipeline that has the same underlying architecture but with some patches bolted on. The next feature addition or new session type would encounter the same missing infrastructure.

### Why NOT `full_rewrite_from_scratch`

Full rewrite is not justified because:

1. **The core algorithms are validated and correct.** Every algorithm in the computation chain — PCHIP, SLERP, CubicSpline, Markley mean, Winter Butterworth, quat_log, SavGol derivatives, de Leva CoM, ISB Euler, T1-anchored PCA — has been independently confirmed against external standards (Phase 4.5) and against session data (Phases 5, 5.5, 6, 7). A full rewrite risks introducing errors in algorithms that are currently correct.

2. **The pipeline produces valid scientific outputs for clean sessions.** `671_T1_P2_R1` and `651_T1_P2_R1` produce consistent, physically plausible kinematics. The outputs are not fundamentally wrong — they lack provenance, safety gates, and QC metadata.

3. **The stage structure is sound.** The six-stage pipeline (Parse → Preprocess → Resample → Filter → Reference → Kinematics) is the correct conceptual decomposition for this problem. The stage boundaries are appropriate.

4. **A rewrite would destroy the N=15 session baseline.** All validated outputs would be regenerated from scratch, requiring complete re-validation. Thesis timeline would be severely impacted.

5. **The rewrite criteria from GAGA_PIPELINE_AGENT_WORK_PLAN.md §Phase 10 are not met.** Specifically:
   - The pipeline CAN be tested reliably (21 existing test files; 12 new tests designed in Phase 9).
   - Global state is limited (config mutation in F-INT2 is fixable without rewrite).
   - Outputs are not inconsistent across sessions — they are consistently produced, with some systematic missing metadata.
   - Stage boundaries are not fundamentally wrong.
   - Incremental hardening is less risky than rebuilding for a thesis-timeline project.

### Why `hybrid_modular_rebuild` is correct

The pattern of problems across 15 sessions and 10 audit phases consistently shows that:

- The computation layer (algorithms, per-frame transformations, feature math) is correct.
- The infrastructure layer (config management, stage contracts, gate chain, metadata propagation, QC sidecars, provenance fields, method labeling) is systematically absent or incorrect.

`hybrid_modular_rebuild` means: preserve the computation layer entirely; rebuild the infrastructure layer around it. Concretely:

**Preserve:** All algorithms listed in §What Should Be Kept As-Is (10_anti_overengineering_review.md).

**Rebuild/add around them:**
- Stage-level gate contracts (beginning with S01; extending to S03 only as needed)
- Per-run config snapshots (S00)
- Stage JSON output schema standardization (add missing fields to existing JSONs rather than replacing JSON structure)
- QC metadata propagation pattern (establish once for ref_is_fallback + filter_psd_verdict; apply to subsequent fields)
- v2_feature_engine.py spec compliance (5 targeted fixes)
- S04 adaptive feedback loop (bounded redesign inside filtering.py)
- Fast QC script (new file, no existing changes)
- QC sidecar outputs (new files, no parquet changes)

The total is 15 implementation tickets. The architecture does not change. The algorithms do not change. The parquet schema changes only by adding 4 data columns and ~5 metadata fields.

---

## C. Which Algorithms Should Be Preserved

**Preserve without modification:**

| Algorithm | Location | Validation status |
|---|---|---|
| `parse_optitrack_csv()` | S01 | 51/51 joints, 0 NaN, all 15 sessions |
| PCHIP gap fill (positions) | S02 | C1-continuous; 0 active events in 15 sessions |
| `gapfill_quaternions.py` SLERP (quaternions) | S02 | Never called; implementation correct; do not touch |
| CubicSpline resampling (positions) | S03 | C2-continuous; `time_grid_std = 0.0` |
| SciPy Slerp resampling (quaternions) | S03 | Geodesically correct; confirmed Phase 3 |
| Stage 1 velocity + Z-score artifact detection | S04 | 0.12% modification rate; keep with logging |
| Stage 2 Hampel filter 5-frame 3σ | S04 | 0.09% modification rate; surgical only |
| Stage 3 Winter Butterworth (algorithm, not loop) | S04 | Correct algorithm; add feedback loop around it |
| Stage 4 quaternion median filter | S04 | Hemisphere flip removal; negligible geodesic error |
| Markley quaternion mean (T-pose reference) | S05 | Geodesic optimum; Markley et al. 2007 |
| Static window fallback detection | S05 | 5 fallback paths coded; 1 triggered correctly |
| Root-relative position computation | S06 | Correct by definition |
| SavGol velocity/acceleration derivatives | S06 | Standard for smooth mocap; confirmed |
| quat_log angular velocity | S06 | Respects SO(3); correct default |
| ISB Euler angles | S06 | Wu et al. 2005; correct joint sequences |
| de Leva CoM model | S06 | Standard 16-segment model |
| NaN Guard + Continuity enforcement | S06 | 0 NaN, 0 flips confirmed |
| P2-only filter | v2_feature_engine | Explicit gate; confirmed |
| T1-anchored PCA (fit on T1, transform T2/T3) | v2_feature_engine | Anti-double-dipping; correct |
| `pulsicity.compute_noise_floor` | pulsicity.py | Interface confirmed compatible |
| ATF NaN-safe computation | v2_feature_engine | NaN-safe; confirmed |
| Contiguous-run TM path length | v2_feature_engine | Avoids discontinuities; confirmed |
| D_eff participation ratio formula | v2_feature_engine | Poggio et al.; confirmed with `epsilon_deff` guard |
| Joint Gini coefficient (session-native: mean-centered, NOT standardized) | v2_feature_engine | StandardScaler must NOT be applied; confirmed |
| T1-anchored Gini (frozen PCA loadings) | v2_feature_engine | Correctly anchored; confirmed |

---

## D. Which Architectural Layers Should Be Rebuilt or Wrapped

### Layer 1: Configuration management (S00)

**Current state:** Single mutable `config_v1.yaml`; overwritten in-place per run.
**Target:** Add per-run YAML snapshot before mutation. Add `pipeline_version` field to config.
**Implementation approach:** 5 lines in `run_pipeline.py::update_config()`. No stage changes.

### Layer 2: Stage output JSON contracts

**Current state:** Each stage writes a summary JSON but no consistent schema across stages. Missing fields: `n_frames_input`, `n_frames_output` (S03), `filter_psd_verdict` in parquet (S04→S06), `ref_is_fallback` in parquet (S05→S06), `is_hampel_outlier` propagation (S04→S06).
**Target:** Add missing fields to existing JSONs. Establish a pattern: every stage that modifies frame count logs input/output counts. Every stage that sets a quality flag that affects downstream analysis also writes it to the parquet metadata at S06.
**Implementation approach:** Targeted additions to each stage's JSON write call. No structural change to JSON format.

### Layer 3: Gate chain (minimal — S01 only for thesis)

**Current state:** Only S02 has `gate_02_status`. Dead session passes all stages.
**Target:** Add `gate_01_status` to S01. Hard FAIL for duration < 30s / 3600 frames. Stop processing immediately on FAIL.
**Implementation approach:** One condition, one field in S01. Run_pipeline.py checks gate_01_status before proceeding to S02.

### Layer 4: v2_feature_engine.py spec compliance

**Current state:** 5 spec deviations confirmed in code.
**Target:** Fix each deviation independently: (a) artifact fraction OR-union, (b) validate_reference threshold 0.20, (c) dead session hard_exclude, (d) remove Hips from ATF_axial group, (e) amend METHODOLOGY_SPEC_v2.md.
**Implementation approach:** 5 targeted code changes. Each is < 10 lines.

### Layer 5: QC sidecar outputs

**Current state:** No session-level QC sidecar.
**Target:** `{RUN_ID}__session_qc_report.json` (aggregate stage JSONs at end of pipeline run); `{RUN_ID}__feature_reliability_table.csv` (after v2_feature_engine run).
**Implementation approach:** New generation function that reads existing stage JSONs and writes a summary. No changes to existing stages.

### Layer 6: Fast QC script

**Current state:** Absent.
**Target:** `src/fast_qc.py` implementing Phase 8 design T1-01 through T3-08. T3-01 INFO-only.
**Implementation approach:** New file. Called from run_pipeline.py pre-check and as standalone. No existing code changes.

---

## E. Which Stages Are Genuine Rebuild Candidates

**S04 (filtering.py) — Partial rebuild of the Stage 3 feedback loop only.**

S04 is the one stage with a genuine algorithm redesign candidate (REDESIGN_CANDIDATE from Phase 3). The redesign is:
- Keep Stage 1 (velocity + Z-score), Stage 2 (Hampel), Stage 4 (quaternion median) unchanged.
- Add a post-filter feedback loop to Stage 3: after applying Butterworth, measure dance-band delta dB; if below -3 dB, raise cutoff by 0.5 Hz and refilter; repeat until target met or ceiling reached.
- The loop design is fully specified in `03_target_skeleton_draft.md §S-04.3`.
- This is NOT a rewrite of filtering.py — it is an addition of one iterative loop around the existing `filtfilt()` call.
- **Blast radius:** ALL 15 session parquets must be regenerated. ALL feature scalars change. ALL golden regression tests must be re-locked. This is the highest blast-radius change in Phase 13.
- **Ordering:** Implement last (Ticket 015), after all other fixes are verified and re-locked on the pre-adaptive-loop baseline.

**No other stage is a rebuild candidate.** S01, S02, S03, S05, S06 require only targeted fixes and additions, not rebuild.

---

## F. Which Stages Should Explicitly NOT Be Rewritten

| Stage | Reason |
|---|---|
| S01 (Parse) | Correct parser; only addition needed is gate_01_status |
| S02 (Preprocess) | Correct gap fill and bone QC; only fix needed is label strings |
| S03 (Resample) | Correct algorithm; only fix needed is off-by-one in n_target |
| S05 (Reference) | Correct algorithm; only fixes needed are var_score guard and t_pose_failed guard |
| **S06 (Kinematics)** | **Most technically correct stage. Do not touch algorithms.** Only additions: read stage JSONs at write time to populate parquet metadata fields. Fix is_hampel_outlier propagation. Add session labels as data columns. |
| v2_feature_engine.py | Correct overall architecture; only 5 targeted spec-compliance fixes needed |
| pulsicity.py | Correct interface and algorithm; KEEP_AS_IS |

---

## G. Minimal Thesis-Grade Implementation Set

These 15 tickets constitute the complete implementation set required before thesis-grade claims are defensible. Nothing beyond this list should be implemented in Phase 13 without explicit user approval.

| Ticket | What it fixes | Why thesis-required |
|---|---|---|
| 001 | Per-run config snapshot | Reproducibility is a thesis-grade requirement |
| 002 | S01 hard FAIL gate | USER DIRECTIVE LOCKED; dead session in published dataset is a factual error |
| 003 | S03 frame count fix | Frame count integrity; all golden tests need re-locking |
| 004 | ref_is_fallback propagation + session labels | Biased T3 features for 651 must be flagged; longitudinal analysis needs session labels |
| 005 | var_score guard + t_pose_failed guard | Invalid JSON causes parse failures; null vs False is a logic error |
| 006 | Hard exclude flag in feature engine | Dead session cannot bias group PCA statistics |
| 007 | filter_psd_verdict + bone_qc_status + gate_01_status + pipeline_version in parquet | Provenance fields for one-file audit |
| 008 | Artifact fraction fix + reference threshold fix | Quality gates and feature engine must match spec |
| 009 | S02 label strings fix | Thesis methods section accuracy |
| 010 | Hips excluded from ATF_axial + spec amendment | Core feature definition error affecting thesis H3 |
| 011 | is_hampel_outlier propagation | Flag column must be correct for traceability |
| 012 | Fast QC script | Pre-pipeline safety for future data collection |
| 013 | NB08 session count sync | Engineering audit notebook used in thesis |
| 014 | QC sidecar outputs | Session-level QC traceability for thesis reviewers |
| 015 | S04 adaptive dance-band loop | ALL features affected by universal oversmoothing |

---

## H. First Phase 13 Implementation Ticket

**Ticket 001: Per-run config snapshot**

**Why first:** Zero scientific risk. Zero output change. Pure provenance gain. Enables reproducibility for all subsequent tickets. Takes ~30 minutes. The absence of config snapshots means that if any subsequent ticket introduces a regression, we may not know which configuration state was active at any given run.

**What it implements:**
- In `run_pipeline.py`, before calling `update_config()`, write the current state of `config_v1.yaml` to:
  `derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml`
- Add `pipeline_version` field to `config_v1.yaml` (e.g., `"v4.0"` to reflect the rebuild version)
- Add `pipeline_version` to parquet PyArrow metadata at S06 write time (read from config snapshot)

**Test required:** None for the snapshot itself. Verify that the snapshot file exists after a test run and contains the correct configuration state.

---

## I. What Phase 11 Final Target Skeleton Should Contain

Phase 11 must produce a revised `11_final_target_skeleton.md` that supersedes the Phase 3 draft. It should contain:

1. **Algorithm preservation table** — comprehensive list of all algorithms certified KEEP_AS_IS with their evidence source.

2. **Infrastructure additions** — exactly what is added to each stage (JSON fields, parquet metadata fields, per-row data columns, gate logic) without rewriting the stage.

3. **15-ticket implementation map** — mapping each ticket to affected files, expected output changes, and golden test update requirements.

4. **Parquet schema contract v2** — final approved schema: existing 803 columns + 4 new data columns + ~5 new metadata fields.

5. **Stage JSON contract** — list of required fields per stage summary JSON after all fixes.

6. **QC sidecar schema** — schema for session_qc_report.json and feature_reliability_table.csv.

7. **Fast QC script architecture** — final T1-01 through T3-08 check list with T3-01 INFO-only status confirmed.

8. **METHODOLOGY_SPEC amendments** — explicit diff of what changes in METHODOLOGY_SPEC_v2.md (Hips excluded from ATF_axial, MEDIUM confidence criteria note).

9. **Rejected items** — explicit list of what Phase 11 must NOT include, to prevent scope creep during skeleton writing.

---

## J. What Phase 11 Must Avoid

Phase 11 must explicitly exclude the following to avoid scope creep:

| What to avoid | Why |
|---|---|
| Per-feature reliability columns inside parquet | Overengineering; sidecar is correct |
| Full gate chain S03–S06 | 0 current failures below S01; premature |
| Step 02 velocity estimator upgrade | MAD is dormant; solving non-observable problem |
| Numeric session_reliability_score | Not calibrated; wrong formula is worse than no score |
| Cyclic anchor QC | No data, no algorithm, no calibration |
| Filter sensitivity analysis per session | 3-5× runtime; offline_batch_audit_only |
| Full raw-to-processed trajectory comparison | Requires F-INT1 fix first; then alignment is complex |
| Full gap-boundary artifact test | Requires gap logs S02 doesn't produce |
| Day-level aggregation | Session-level QC must be stable first |
| v2_longitudinal.py | Post-thesis scope |
| Papermill parameterization of NB08 | NB08 session count fix is sufficient |
| S01 two-tier FAIL/SUSPICIOUS | Hard FAIL gate is sufficient |
| omega_method = '5pt' as default | Function name misleading; rename first |
| Automatic QC dashboard | Fix existing NB08/NB09 before building new |
| Any new kinematic features in kinematics_master.parquet | Out of scope; feature additions need separate spec approval |
| `enforce_cleaning = true` as default | LOCKED decision — ground truth integrity takes priority |
| Any external library adoption (pose2sim, scikit-kinematics conventions) | Quaternion convention hazard |

---

## Summary

The Gaga pipeline requires `hybrid_modular_rebuild`: preserve all validated algorithms; rebuild the surrounding infrastructure layer (gates, config snapshots, stage contracts, metadata propagation, QC sidecars). 15 implementation tickets. First ticket is per-run config snapshot (30 minutes, zero risk). Last ticket is S04 adaptive dance-band correction loop (highest blast radius; regenerates all parquets). Total scope is bounded, evidence-based, and thesis-timeline compatible.

**The pipeline is not broken. It is unfinished.**

Specifically: it lacks the provenance, safety, and QC metadata layers that transform a research script into a thesis-grade, reproducible, auditable analysis pipeline. `hybrid_modular_rebuild` adds exactly those layers without touching what is already correct.

---

*Phase 10 rewrite decision gate complete. Stop condition reached.*
*Do not start Phase 11 until user approves this Phase 10 output.*
