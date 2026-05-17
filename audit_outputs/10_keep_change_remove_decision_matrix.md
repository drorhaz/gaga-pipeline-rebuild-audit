# 10 Keep / Change / Remove Decision Matrix

**Date:** 2026-05-17
**Phase:** 10 — Anti-Overengineering Review
**Mode:** Decision-only. No code changes.

---

## Model Decision Note

- **Recommended model for this phase:** Sonnet (decision matrix produced at this tier)
- **Is Opus review required before Phase 11?** Yes — recommended
- **Reason:** This matrix governs all Phase 13 implementation tickets. An Opus review is recommended if the user wants independent challenge of the DEFER vs. REJECT vs. LOW_RISK_FIX classifications before final skeleton writing. Sonnet produced this with evidence from all 15 sessions and 27 source findings.

---

## Decision Category Legend

| Decision | Meaning |
|---|---|
| `KEEP_AS_IS` | Correct, validated, do not touch |
| `KEEP_WITH_DOCUMENTATION` | Correct but needs explicit documentation or spec note |
| `KEEP_WITH_TESTS` | Appears correct; add test coverage |
| `LOGGING_ONLY` | Add logging or metadata field; no computation change |
| `LOW_RISK_FIX` | Targeted fix; small blast radius; no scientific risk |
| `LOCAL_REFACTOR` | Bounded internal change; may have limited output change |
| `CHANGE_TARGETED` | Specific change with bounded scope; may change computed values |
| `CHANGE_STRUCTURAL` | Changes stage contracts or cross-stage data flow |
| `DESIGN_DECISION_REQUIRED` | Cannot decide without user input |
| `CANDIDATE_PENDING_EVIDENCE` | Change may be warranted; need more data |
| `DEFER_POST_THESIS` | Defer; not blocking for thesis claims |
| `REJECT_DO_NOT_ADOPT` | Explicitly rejected; must not enter Phase 13 |
| `REMOVE_CANDIDATE` | May be removable; requires proof |

---

## Full Decision Matrix

| finding_id | source_phase | affected_stage | current_state | proposed_change | decision | severity | confidence | thesis_required | overengineering_risk | implementation_risk | test_required | affects_kinematics_master | affects_downstream_methodology | belongs_in_fast_qc | rationale |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F-651-1-gate | 5.5 | S01 | No minimum session gate; dead session (5 frames) passes all stages | Add gate_01_status = FAIL if duration < 30s / 3600 frames | `LOW_RISK_FIX` | CRITICAL | HIGH | YES | NONE | LOW | U-NEW-04 | NO (gate field to S01 JSON only) | YES | YES (T1-05) | USER DIRECTIVE LOCKED. 651_T2_P2_R2 confirmed dead. Cannot publish kinematics from 0.03s session. |
| F-INT1-frame | 5 | S03 | n_target formula drops last frame silently; S01=16,915 → S04=16,914 universal | Fix n_target to int(duration × fs) + 1; add frame count logging to resample_summary | `LOW_RISK_FIX` | HIGH | HIGH | YES | NONE | MEDIUM | U-NEW-12 | YES (all parquets regenerated; golden frame counts change +1) | NO | NO | Universal on all 7+ sessions confirmed. Frame count integrity is basic provenance. All golden tests must be re-locked after fix. |
| F-651-4-fallback | 5.5, 7 | S05→S06 | ref_is_fallback=True not in kinematics parquet | Read S05 JSON at S06 write time; add ref_is_fallback to parquet PyArrow metadata | `LOW_RISK_FIX` | CRITICAL | HIGH | YES | NONE | LOW | U-NEW-09 | YES (one parquet metadata field) | YES | YES (T3-07) | 651_T3_P2_R2 confirmed fallback. T3 in thesis dataset. Biased features must be flagged. |
| F-651-2-varinf | 5.5 | S05 | var_score = Infinity in reference_metadata.json for dead session — invalid JSON | Guard: if n_frames == 0: var_score = None | `LOW_RISK_FIX` | HIGH | HIGH | YES | NONE | LOW | U-NEW-06 | NO | NO | NO | Invalid JSON causes parse failures. One-line fix. |
| F-651-5-tpose | 5.5 | S05 | t_pose_failed = null (None) for fallback sessions; gate logic if t_pose_failed: silently misses fallbacks | Set explicitly t_pose_failed = False for non-identity fallback sessions | `LOW_RISK_FIX` | HIGH | HIGH | YES | NONE | LOW | U-NEW-08 | NO | NO | NO | 651_T3_P2_R2 confirmed. Null vs False is a silent logic error in any downstream gate. |
| F7-5-hardexclude | 7 | v2_feature_engine | Dead session gets short_session=True not hard_exclude=True; PCA engine may process it | Add dead_recording check: hard_exclude=True; skip in build_pca_engine() | `LOW_RISK_FIX` | HIGH | HIGH | YES | NONE | LOW | U-NEW-03, U-NEW-05 | NO | YES | NO | Dead session cannot bias group PCA statistics. |
| F-INT2-config | 5 | S00 | config_v1.yaml mutated in-place after every run; previous config permanently lost | Write YAML snapshot to derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml before mutation | `LOW_RISK_FIX` | HIGH | HIGH | YES | NONE | LOW | NONE | NO | NO | NO | Reproducibility is thesis-grade requirement. 5 lines. ~1 KB per session. FIRST TICKET. |
| F-INT3-psdverd | 5 | S04→S06 | REVIEW_OVERSMOOTHING verdict not propagated to parquet; universal finding, all 15 sessions | Read __filtering_summary.json at S06 write time; add filter_psd_verdict to parquet PyArrow metadata | `LOW_RISK_FIX` | HIGH | HIGH | YES | NONE | LOW | U-NEW-10 | YES (one parquet metadata field) | YES | NO | Universal finding; downstream consumers cannot detect over-smoothed input. |
| F7-3-artfrac | 7 | v2_feature_engine | compute_quality_gates uses max(joint_art_rates); less strict than spec; should use 1.0 - clean_fraction_pca | Change one expression in compute_quality_gates | `LOCAL_REFACTOR` | HIGH | HIGH | YES | NONE | LOW | U-NEW-01 | NO (quality_df may change verdicts) | YES | NO | Code confirmed. Quality gate must match spec for methodology defensibility. |
| F7-4-refthresh | 7 | v2_feature_engine | validate_reference() threshold = 0.30; spec requires 0.20 | Change constant to 0.20 | `LOW_RISK_FIX` | HIGH | HIGH | YES | NONE | LOW | U-NEW-02 | NO | YES | NO | Code confirmed. Wrong threshold can pass a poor reference. |
| Q-EXT1b-label | 4, 5.5 | S02 | Logs say pchip_single_pass and slerp; code uses np.interp and scalar-normalize; 15 sessions mislabeled | Update label strings to linear_interp and quaternion_normalize | `LOW_RISK_FIX` | HIGH | HIGH | YES | NONE | LOW | NONE | NO | NO | NO | Methodological misrepresentation. Critical for thesis methods section. |
| F7-1-hipsatf | 7 | v2_feature_engine + spec | Hips ATF = 0 permanently (root joint); spec includes Hips in axial group; ATF_axial biased downward | (a) Amend METHODOLOGY_SPEC_v2.md §ATF_axial to exclude Hips. (b) Remove Hips from axial group in feature engine. (c) Recompute ATF_axial. | `CHANGE_TARGETED` | CRITICAL | HIGH | YES | NONE | MEDIUM | U-NEW-01 extended | NO (feature scalars recompute) | YES (ATF_axial changes all sessions; thesis H3 affected) | NO | Structural constraint. Hips cannot have non-zero relative velocity by definition. Spec and code must be amended together. |
| Phase6-hampel | 6 | S04→S06 | is_hampel_outlier = all-False in parquet despite Hampel activity in S04 | Trace S04 Hampel mask; propagate to S06 parquet per-frame | `LOCAL_REFACTOR` | MEDIUM | HIGH | MEDIUM | NONE | MEDIUM | U-NEW-11 | YES (one column corrected) | NO | NO | Column is misleading; correct it for traceability. |
| parquet-labels | 6 | S06 | subject_id, timepoint, piece, rep absent as per-row data columns; index is RangeIndex only | Add as per-row data columns at S06 write time, parsed from run_id | `CHANGE_STRUCTURAL` | HIGH | HIGH | YES | NONE | MEDIUM | NONE | YES (4 new columns per session) | YES | NO | Phase 6 Critical gap. ML windowing and longitudinal analysis require session labels co-located with data rows. Confirm naming convention with user before implementing. |
| F-INT5-version | 5 | All stages | No consistent pipeline_version field; S01=v2.6, S04=v3.1, S06=none | Config snapshot (F-INT2) provides version provenance; add single field to config_v1.yaml | `KEEP_WITH_DOCUMENTATION` | MEDIUM | HIGH | MEDIUM | LOW | LOW | NONE | NO | NO | NO | Per-run config snapshot already captures full pipeline state. Per-stage inconsistency is cosmetic. |
| Q-EXT3b-meta | 4.5 | S01 | Capture Frame Rate, Export Frame Rate, Rotation Type, Length Units not extracted from CSV header | Fast QC T1-09 and T1-10 already cover pre-pipeline check; no S01 internal duplication needed | `DEFER_POST_THESIS` | MEDIUM | MEDIUM | LOW | LOW | LOW | NONE | NO | NO | YES | Fast QC covers this at pre-pipeline level. S01 duplication adds complexity. |
| Q-EXT3c-cont | 4.5 | S01 | No frame number continuity check in S01 | Fast QC T2-11 covers pre-pipeline; S01 can add as LOGGING_ONLY (log but not gate) | `LOGGING_ONLY` | MEDIUM | MEDIUM | LOW | NONE | LOW | NONE | NO | NO | YES | Fast QC T2-11 is primary coverage. S01 logging is optional provenance. |
| S04-adaptive | 3 | S04 | No post-filter feedback loop; ALL 57 columns REVIEW_OVERSMOOTHING; mean dance-band delta -4.68 to -5.51 dB | Implement adaptive dance-band correction loop per Phase 3 S-04.3 design; raise cutoff until delta >= -3 dB or hit ceiling | `LOCAL_REFACTOR` | CRITICAL | HIGH | YES | LOW | HIGH | U-NEW-10 re-lock | YES (ALL parquets regenerated; ALL features change) | YES (ALL thesis features affected) | NO | Universal quality issue. Phase 3 design is complete and bounded. Implement last — after all Tier 1-3 fixes. Re-lock all golden tests. |
| FastQC-impl | 8 | Pre-pipeline | No pre-collection QC script; problems discovered post-pipeline | Implement src/fast_qc.py per Phase 8 spec T1-01 through T3-08; T3-01 stays INFO-only | `LOCAL_REFACTOR` | HIGH | HIGH | MEDIUM | LOW | MEDIUM | Phase 8 fixtures | NO | NO | YES | High practical value for future data. Doesn't modify existing pipeline. |
| T3-01-adv | 8 | Fast QC | T3-01 threshold 0.10 rad/s produces false alarms; DRAFT_PENDING_RESEARCH | Calibrate from >=15 sessions; INFO-only until calibrated | `DEFER_POST_THESIS` | MEDIUM | LOW | LOW | NONE | LOW | NONE | NO | NO | YES | ADV-T3-01 confirmed DRAFT_PENDING_RESEARCH. Cannot implement without calibration data. |
| S02-velest | 3 | S02 | Single-frame diff velocity estimator; MAD dormant (0 detections all 15 sessions) | Upgrade to 3-pt central diff — DEFER | `DEFER_POST_THESIS` | MEDIUM | MEDIUM | LOW | LOW | MEDIUM | U-NEW-07 | NO | NO | NO | MAD is dormant. Upgrading solves a non-observable problem. Defer until sessions with active artifact detection appear (N>20+). |
| Q-EXT4a-qnorm | 4.5 | S06 | No |q|≈1.0 assertion with logging; silent per-frame renormalization | Add logging assertion (warn if |q| outside 0.95-1.05 after SavGol); NO hard gate | `LOGGING_ONLY` | LOW | HIGH | LOW | NONE | LOW | None | NO | NO | NO | 0 norm issues observed. Logging sufficient. Hard gate could fail clean sessions. |
| Q-EXT1a-nanlog | 4.5 | S04 | n_nan_frames_at_filter_input not logged | Add field to __filtering_summary.json; value = 0 for all current sessions | `LOGGING_ONLY` | LOW | HIGH | LOW | NONE | LOW | NONE | NO | NO | NO | All 15 sessions have 0 NaN at filter input. Add for future-session coverage. |
| QC-sidecar | 9.5 | Post-S06 | No session QC sidecar outputs | Implement {RUN_ID}__session_qc_report.json and {RUN_ID}__feature_reliability_table.csv | `LOCAL_REFACTOR` | MEDIUM | HIGH | MEDIUM | LOW | MEDIUM | NONE | NO | NO | NO | Sidecar-first policy confirmed. Keep parquet numeric. |
| NB08-sync | 4, S08 | NB08 | NB08 references 16 runs but 9 derivatives exist | Update NB08 to read from current derivatives; no algorithm change; NO papermill | `LOCAL_REFACTOR` | MEDIUM | HIGH | MEDIUM | NONE | LOW | NONE | NO | NO | NO | Engineering audit notebook used in thesis. Fix session count. Papermill deferred. |
| gate-chain | 5 | S03-S06 | Only S02 has gate_02_status; no downstream gate chain | No action for thesis scope | `DEFER_POST_THESIS` | MEDIUM | HIGH | LOW | MEDIUM | HIGH | NONE | NO | NO | NO | 0 failures in current data below S01. Full chain is post-thesis infrastructure. |
| M-spec-medconf | 5 | METHODOLOGY_SPEC | MEDIUM confidence trigger criteria not explained | Add clarifying note to spec only | `KEEP_WITH_DOCUMENTATION` | LOW | HIGH | LOW | NONE | LOW | NONE | NO | NO | NO | Documentation gap only. No code change. |
| parquet-boneqc | 6 | S06 | bone_qc_status absent from parquet metadata | Add bone_qc_status to parquet metadata at S06 write time; read from S02 JSON | `LOGGING_ONLY` | LOW | HIGH | LOW | NONE | LOW | NONE | YES (one metadata field) | NO | NO | Low priority; enables one-file analysis without reading S02 JSON separately. |
| parquet-gate01 | 9.5 | S06 | gate_01_status absent from parquet metadata | Add to parquet metadata; implement after F-651-1-gate exists in S01 JSON | `LOGGING_ONLY` | LOW | HIGH | LOW | NONE | LOW | NONE | YES (one metadata field) | NO | NO | Bundle with Ticket 007. Implement after Ticket 002. |
| parquet-ver | 9.5 | S06 | pipeline_version absent from parquet metadata | Add from config snapshot; bundle with Ticket 001 | `LOGGING_ONLY` | LOW | HIGH | LOW | NONE | LOW | NONE | YES (one metadata field) | NO | NO | Config snapshot provides version provenance. Propagate to parquet. |
| parquet-boneqcflag | 3 | S06 | Phase 3 proposed per-joint {joint}__bone_qc_flag columns (constant per-frame columns) | REJECTED | `REJECT_DO_NOT_ADOPT` | LOW | HIGH | NO | HIGH | LOW | NONE | — | — | — | Phase 3 proposal rejected. One bone_qc_status metadata field is sufficient. Constant columns have no ML value. |
| per-feat-reli | 9.5 | parquet | Per-feature reliability columns inside kinematics_master.parquet | REJECTED | `REJECT_DO_NOT_ADOPT` | — | HIGH | NO | CRITICAL | LOW | NONE | — | — | — | Core overengineering risk. 803 → 1000+ columns. Destroys ML/DL readiness. Use sidecar. |
| plots-every-pass | 9.5 | Output | QC plots for every PASS session | REJECTED | `REJECT_DO_NOT_ADOPT` | — | HIGH | NO | HIGH | LOW | NONE | — | — | — | No automated value for PASS sessions. WARN/FAIL/golden only. |
| filter-sensit | 9.5 | S04 | Filter sensitivity analysis on every session | REJECTED | `REJECT_DO_NOT_ADOPT` | — | HIGH | NO | HIGH | HIGH | NONE | — | — | — | 3-5x runtime per session. offline_batch_audit_only. |
| cyclic-anchor | 9.5 | Fast QC | Automatic cyclic anchor detection | REJECTED | `REJECT_DO_NOT_ADOPT` | — | HIGH | NO | HIGH | HIGH | NONE | — | — | — | No algorithm, no calibration, no data. Speculative engineering. |
| ROM-hard-gate | 9.5 | Fast QC | ROM calibration as hard FAIL gate | REJECTED | `REJECT_DO_NOT_ADOPT` | — | HIGH | NO | MEDIUM | MEDIUM | NONE | — | — | — | .mcal files deleted for historical sessions. Hard gate would immediately fail historical data. |
| numeric-score | 9.5 | QC sidecar | Numeric session_reliability_score 0-1 formula | REJECTED for thesis | `DEFER_POST_THESIS` | — | HIGH | NO | HIGH | MEDIUM | NONE | — | — | — | Needs calibration on N>=20 sessions. Categorical PASS/WARN/FAIL sufficient. |
| S02-SLERP | 4 | S02 | Genuine SLERP gap fill; currently placeholder, never called | DEFER | `DEFER_POST_THESIS` | LOW | HIGH | LOW | LOW | HIGH | NONE | NO | NO | NO | Never called in 15 sessions. Touching gap fill risks pristine data. Defer until N>20 with active gaps. |
| S01-twotier | 3 | S01 | Two-tier FAIL/SUSPICIOUS flagging in S01 | DEFER | `DEFER_POST_THESIS` | LOW | MEDIUM | LOW | MEDIUM | MEDIUM | NONE | NO | NO | NO | S01 hard FAIL gate is sufficient. SUSPICIOUS adds schema complexity for no current use case. |
| omega-5pt-default | 3, 4 | S06 | omega_method = '5pt' as default; finite_difference_5point() is actually a weighted smoother | Do NOT change default until function is renamed. Keep quat_log as default. | `KEEP_WITH_DOCUMENTATION` | LOW | HIGH | LOW | LOW | LOW | NONE | NO | NO | NO | Phase 4 confirmed: function name misleading. Rename first, then reconsider default. quat_log is geometrically correct. |
| v2-longit | 7 | src/ | v2_longitudinal.py absent; MVP-deferred | DEFER | `DEFER_POST_THESIS` | LOW | HIGH | LOW | LOW | HIGH | NONE | NO | YES | NO | Post-thesis scope. Session-level data integrity must be confirmed first. |
| NB10-broken | 2 | NB10 | NB10 imports legacy/EDA_PCA.py; import fails | Add deprecation header to NB10 | `KEEP_WITH_DOCUMENTATION` | LOW | HIGH | LOW | NONE | LOW | NONE | NO | NO | NO | Q8 from Phase 1. NB10 is archived; add header only. |
| day-agg | 9.5 | Post-processing | Day-level QC aggregation | DEFER | `DEFER_POST_THESIS` | LOW | HIGH | NO | HIGH | MEDIUM | NONE | NO | NO | NO | Requires stable session-level QC first. Not needed for thesis N. |

---

## Approved Parquet Changes Summary

### Metadata fields (PyArrow schema.metadata — no new data columns)

| Field | Type | Source JSON | Ticket |
|---|---|---|---|
| `ref_is_fallback` | bool | S05 reference_metadata.json | 004 |
| `filter_psd_verdict` | str | S04 filtering_summary.json | 007 |
| `pipeline_version` | str | config_v1.yaml / config snapshot | 001 (bundle) |
| `gate_01_status` | str | S01 stage summary JSON | 007 (after 002) |
| `bone_qc_status` | str | S02 kinematics_map.json | 007 (bundle) |

### New per-row data columns

| Column | Type | Source | Ticket | User decision needed |
|---|---|---|---|---|
| `subject_id` | str | parse from run_id | 004 | Naming: confirm `651` vs `Subject_651` |
| `timepoint` | str | parse from run_id | 004 | Naming: confirm `T1` vs `1` |
| `piece` | str | parse from run_id | 004 | Naming: confirm `P2` vs `2` |
| `rep` | str | parse from run_id | 004 | Naming: confirm `R1` vs `1` |

### Rejected parquet additions

| Item | Reason |
|---|---|
| `{joint}__bone_qc_flag` per-frame columns | Overengineering; constant columns |
| `{feature}__reliability` per-feature columns | Overengineering; use sidecar |
| `session_reliability_score` | Not calibrated |

---

## Phase 13 Ticket Ordering

| Ticket | Findings | Decision | Category | Blast Radius | Must Precede |
|---|---|---|---|---|---|
| **001** | F-INT2-config | LOW_RISK_FIX | PROVENANCE | XS — no output change | All others |
| **002** | F-651-1-gate | LOW_RISK_FIX | SAFETY | S — S01 gate field only | 004, 006 |
| **003** | F-INT1-frame | LOW_RISK_FIX | SAFETY | M — all parquets regenerated; golden +1 frame | All parquet regen |
| **004** | F-651-4-fallback + parquet-labels | LOW_RISK_FIX + CHANGE_STRUCTURAL | SAFETY + PROVENANCE | M — adds 4 data cols + 1 metadata field | 008, 014 |
| **005** | F-651-2-varinf + F-651-5-tpose | LOW_RISK_FIX | SAFETY | XS — S05 JSON only | 006 |
| **006** | F7-5-hardexclude | LOW_RISK_FIX | SAFETY | S — quality_df change | 008 |
| **007** | F-INT3-psdverd + parquet-boneqc + parquet-gate01 + parquet-ver | LOW_RISK_FIX | PROVENANCE | S — parquet metadata additions | 014 |
| **008** | F7-3-artfrac + F7-4-refthresh | LOCAL_REFACTOR | CORRECTNESS | S — quality_df verdicts may change | 010, 014 |
| **009** | Q-EXT1b-label | LOW_RISK_FIX | CORRECTNESS | XS — S02 log strings only | None |
| **010** | F7-1-hipsatf + M-spec-hips | CHANGE_TARGETED | CORRECTNESS | M — ATF_axial recomputed all sessions | Final analysis |
| **011** | Phase6-hampel | LOCAL_REFACTOR | CORRECTNESS | M — investigate propagation path | None |
| **012** | FastQC-impl | LOCAL_REFACTOR | QUALITY | L — new file; no existing changes | None |
| **013** | NB08-sync | LOCAL_REFACTOR | QUALITY | S — NB08 session count update | None |
| **014** | QC-sidecar | LOCAL_REFACTOR | QUALITY | M — new output files | 007, 008 |
| **015** | S04-adaptive | LOCAL_REFACTOR (bounded) | QUALITY | XL — ALL parquets + ALL features change | Final analysis |

**Size legend:** XS < 30 min · S < 2h · M half-day · L 1 day · XL 2+ days

---

*Phase 10 decision matrix complete.*
