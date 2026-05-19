# PROJECT MEMORY FOR IMPLEMENTATION

**Purpose:** Concise operational memory for any agent implementing Phase 13 tickets.
**Date:** 2026-05-17
**Last updated by:** Phase 12.5 Agent (Claude Opus 4.6)

---

## Current Status

- **Phase 12.5:** COMPLETE — Opus Backlog Alignment Review, Corrected Backlog, Source Cleanup Readiness Map all written.
- **Phase 13:** NOT STARTED. Implementation has not begun.
- **Blockers before starting:** UD-006 (session label naming) blocks Ticket 004. UD-001 (dance-band threshold) blocks Ticket 015. NEW-D1 (Hampel column design) blocks Ticket 011.
- **First ticket to implement after approval:** Ticket 001 (per-run config snapshot).

---

## Approved Strategy

**`hybrid_modular_rebuild`** — Preserve all 25 validated algorithms. Rebuild only the infrastructure layer: config snapshots, stage contracts, gates, metadata propagation, QC sidecars, Fast QC. No algorithm rewrites. No new frameworks. No repository reorganization.

---

## Authority Order (Later Supersedes Earlier)

| Priority | Document | Location |
|----------|----------|----------|
| 1 (highest) | 12_implementation_backlog_CORRECTED.md | `audit_outputs/` and `docs/pipeline_rebuild_audit/phase_12_implementation_backlog/` |
| 2 | 12.5_opus_backlog_alignment_review.md | same |
| 3 | 12_implementation_backlog_ORIGINAL.md (DO NOT implement from) | same |
| 4 | 11.5_architecture_compression_and_logging_review.md | `audit_outputs/` and `docs/pipeline_rebuild_audit/phase_11_target_skeleton/` |
| 5 | 11_final_target_skeleton.md | same |
| 6 | 10_rewrite_decision_gate.md | `audit_outputs/` and `docs/pipeline_rebuild_audit/phase_10_decision_gate/` |
| 7 | 10_anti_overengineering_review.md | same |
| 8 | GAGA_PIPELINE_AGENT_WORK_PLAN.md | project root and `docs/pipeline_rebuild_audit/` |
| 9 | audit_index.md | `audit_outputs/` |
| 10 | Earlier audit evidence (Phases 4.5–9.5) | `docs/pipeline_rebuild_audit/earlier_audit_evidence/` |

**Contradiction-handling rule:** If two documents disagree, the higher-priority (later) document wins. If still ambiguous, ask the user.

---

## Locked Decisions (Do Not Revisit)

| ID | Decision | Source | Details |
|----|----------|--------|---------|
| LD-1 | hybrid_modular_rebuild strategy | Phase 10 | No full rewrites, no new frameworks |
| LD-2 | 15-ticket Minimal v1 scope | Phase 10, corrected Phase 12.5 | No additions without new audit phase |
| LD-3 | Strict ticket ordering | Phase 12 | Each ticket regression-checked before next begins |
| LD-4 | Anti-overengineering commitments (7 rules) | Phase 10, Phase 12 | See corrected backlog §Anti-Overengineering Commitments |
| LD-5 | S01 FAIL gate: conservative scope only | Phase 12.5 M5 | FAIL = dead/too-short + unrecoverable parse. Label mismatch/column count = WARN only. |
| LD-6 | Duration < 30s and frames < 3600 → FAIL | Phase 5.5 USER DIRECTIVE | Locked by user |
| LD-7 | ref_is_fallback = metadata only, not per-row | Phase 12.5 M2 | Session-constant → PyArrow schema.metadata |
| LD-8 | 5 approved PyArrow metadata fields | Phase 10, Phase 12.5 M3 | ref_is_fallback, filter_psd_verdict, pipeline_version, gate_01_status, bone_qc_status |
| LD-9 | Quaternion diagnostics → sidecar JSON, not parquet | Phase 12.5 M4 | validation_report.json under quaternion_diagnostics key |
| LD-10 | Ticket 015 = PSD/dance-band method, NOT artifact-fraction | Phase 12.5 M1 | See Ticket 015 filtering policy below |
| LD-11 | Session label column names: subject_id, timepoint, piece, rep | Phase 10 | NOT session_id/phase_id/rep_id |
| LD-12 | Hips excluded from ATF_axial | Phase 7, Phase 10 F-012 | Root joint; lin_vel_rel_mag = 0 by definition |
| LD-13 | Reference threshold: 0.30 → 0.20 | Phase 7 F7-4 | In v2_feature_engine.py validate_reference() |
| LD-14 | Forensic subsystem: ZERO changes in Minimal v1 | Phase 11.5, Phase 12.5 | 8 files, self-contained, not imported by active pipeline |

---

## Rejected / Deferred Items

| Item | Status | Rationale |
|------|--------|-----------|
| Full algorithm rewrite | REJECTED | hybrid_modular_rebuild preserves 25 validated algorithms |
| Plugin/factory architecture | REJECTED | Anti-overengineering commitment |
| PCHIP/SLERP activation | DEFERRED (candidate_pending_tests) | Needs 3 synthetic tests each; not Minimal v1 |
| SO(3)-aware quaternion smoothing | DEFERRED | candidate_pending_tests; not Minimal v1 |
| Per-joint Hampel columns (~51 cols) | DEFERRED pending NEW-D1 | Option B (single OR column) recommended |
| Repository reorganization | REJECTED for Minimal v1 | Cleanup tickets C1–C5 are post-core |
| Forensic subsystem changes | DEFERRED to post-thesis | Self-contained; no active pipeline impact |
| T3-01 T-pose threshold | DRAFT_PENDING_RESEARCH | INFO-only in Fast QC; no hard gate |
| New frameworks (Pydantic, dataclass contracts) | REJECTED | Anti-overengineering commitment |

---

## Parquet Schema Policy

**Rule:** kinematics_master.parquet stays numeric and ML-ready. Sidecar-first QC.

**Schema v2.0 (after all 15 tickets):**
- ~803 existing numeric columns (unchanged)
- +4 per-row data columns: `subject_id`, `timepoint`, `piece`, `rep` (Ticket 004)
- +1 corrected column: `is_hampel_outlier` (boolean OR across joints; Ticket 011)
- 5 PyArrow metadata fields (Ticket 007a): `ref_is_fallback`, `filter_psd_verdict`, `pipeline_version`, `gate_01_status`, `bone_qc_status`
- Optional 6th metadata: `schema_version` (recommended, not required)

**What does NOT go in parquet:**
- Per-feature reliability columns (→ feature_reliability_table.csv sidecar)
- Quaternion diagnostics (→ validation_report.json sidecar)
- Per-joint Hampel masks (→ filtering_summary.json or sidecar)
- Diagnostic strings or JSON blobs
- Any session-constant data that can be in PyArrow metadata

---

## Sidecar Policy

| Sidecar | Created by | Content |
|---------|-----------|---------|
| `{RUN_ID}__config_snapshot.yaml` | Ticket 001 | Frozen config before mutation |
| `{RUN_ID}__s01_fail_report.json` | Ticket 002 | FAIL details (only on FAIL) |
| `{RUN_ID}__s02_interpolation_stats.json` | Ticket 009 | 9 artifact/gap statistics |
| `{RUN_ID}__filtering_summary.json` | Existing + Ticket 007b | Existing fields + Hampel summary |
| `{RUN_ID}__validation_report.json` | Existing + Ticket 007b | Existing fields + quaternion_diagnostics |
| `session_qc_report.json` | Ticket 014a | Aggregated per-session QC from all stage JSONs |
| `feature_reliability_table.csv` | Ticket 014b | Per-feature reliability ratings |
| `fast_qc_report.json` | Ticket 012 | 37 checks (T1/T2/T3 tiers) |

---

## Step 02 Interpolation Policy

**Active path (artifact masking):** `np.interp` (linear) in `src/preprocessing.py::detect_and_mask_artifacts()`. Label in logs: `linear_interp` (corrected from `pchip_single_pass` by Ticket 009).

**Inactive path (genuine gap fill):** PCHIP in `src/gapfill_positions.py`, SLERP placeholder in `src/gapfill_quaternions.py`. Never triggered on any of 15 current sessions.

**Minimal v1 scope:** Ticket 009 logs artifact statistics. No PCHIP/SLERP code added.

---

## Ticket 015 Filtering Policy

**Method:** PSD/dance-band correction loop (NOT artifact-fraction control).
**How it works:**
1. Run existing `apply_adaptive_winter_filter()` (inner loop, lines 636–790 in filtering.py)
2. Call `compute_psd_comparison()` (line 2382 in filtering.py) → produces `psd_verdict`
3. If `psd_verdict == REVIEW_OVERSMOOTHING`: dance-band loss exceeded threshold
4. Raise `region_max_hz` by `correction_step_hz` (0.5 Hz)
5. Re-run the Winter+Butterworth pipeline
6. Repeat until `psd_verdict != REVIEW_OVERSMOOTHING` or `max_correction_iterations` (10) reached

**Parameters:** `dance_band_threshold_db` (-3.0 dB), `correction_step_hz` (0.5), `region_max_hz` (per-region ceilings), `max_correction_iterations` (10).

**Key distinction:** The outer PSD loop wraps AROUND the existing inner adaptive Winter loop. They are NOT the same loop.

**UD-001 (BLOCKING):** Exact dance-band threshold value must be confirmed by user before Ticket 015 begins.

---

## Source Cleanup Policy

**During Minimal v1:** No files moved, deleted, or renamed. ~15 of 53 src/ files may be touched by tickets.

**After Minimal v1:** 5 cleanup tickets (C1–C5) in `12_source_cleanup_readiness_map.md`. Require user approval.

**Do NOT touch during Minimal v1:**
- 8 FORENSIC_SUBSYSTEM_ONLY files
- 5 KEEP_AS_IS algorithm files (gapfill_positions.py, gapfill_quaternions.py, com_engine.py, euler_isb.py, pulsicity.py)
- 5 LEGACY_ARCHIVE_CANDIDATE files
- 5 DEPENDENCY_UNVERIFIED files
- Core math: quaternion_ops.py, quaternion_normalization.py, quaternions.py, skeleton_defs.py

---

## Phase 13 Implementation Rules

1. **One ticket at a time.** No batch implementation.
2. **Pre-implementation statement** written in implementation log BEFORE any code is touched.
3. **Regression check** before next ticket begins (golden parquet comparison).
4. **Implementation logs** in `docs/pipeline_rebuild_audit/implementation_logs/`, one file per ticket.
5. **No log file = no implementation** for that ticket.
6. **Tickets 011–014 must complete** before Ticket 015 begins.
7. **Ticket 015 requires pre-implementation brief** approved by user.
8. **Do not refactor working algorithms** unless a ticket explicitly requires a fix.
9. **Do not add abstraction layers, factories, or new base classes.**
10. **Every ticket ends with:** files changed list, tests run, regression comparison, issues, sign-off.

---

## Required Reading Before Implementing Any Ticket

Every implementation agent MUST read these before writing any code:

1. This file (`PROJECT_MEMORY_FOR_IMPLEMENTATION.md`)
2. `12_implementation_backlog_CORRECTED.md` — the specific ticket being implemented
3. `12.5_opus_backlog_alignment_review.md` — correction context
4. `12_source_cleanup_readiness_map.md` — which files can be touched
5. The source files named in the ticket's "Files to change" section

---

## Stop Conditions

**Stop implementing and ask the user if:**
- A ticket's prerequisite has not been completed
- A USER DECISION (UD-xxx) blocking the ticket has not been resolved
- Regression check fails (golden parquet values changed unexpectedly)
- A file not listed in the ticket's "Files to change" needs modification
- The ticket requires touching a file classified as KEEP_AS_IS, FORENSIC_SUBSYSTEM_ONLY, or LEGACY_ARCHIVE_CANDIDATE
- The implementer disagrees with the ticket specification

**Stop implementing and escalate if:**
- Two governing documents contradict and neither clearly supersedes
- A code finding invalidates the ticket's assumptions (e.g., feature doesn't exist, function signature changed)
- Implementing the ticket would break another ticket's assumptions

---

## Key Source Code Facts

| Fact | Location | Verified |
|------|----------|----------|
| `parse_optitrack_csv()` | `src/preprocessing.py` line 130 | Yes |
| `detect_and_mask_artifacts()` uses `np.interp` | `src/preprocessing.py` line 489 | Yes |
| `resample_time_grid()` | `src/resampling.py` line 169; n_target at line 172 | Yes |
| n_target formula already has `+1` | `src/resampling.py` line 172 | Yes (PATH_VERIFY_REQUIRED by Ticket 003) |
| `ref_quality_score` (NOT `var_score`) | `src/reference.py` line 278 | Yes |
| `t_pose_failed` | `src/reference.py` multiple lines | Yes |
| `apply_hampel_filter()` | `src/filtering.py` line 990 | Yes |
| `apply_adaptive_winter_filter()` | `src/filtering.py` line 1172 | Yes |
| Existing adaptive Winter loop | `src/filtering.py` lines 636–790 | Yes |
| `compute_psd_comparison()` | `src/filtering.py` line 2382 | Yes |
| dance_band range | `src/filter_validation.py`: (1.0, 15.0) Hz | Yes |
| `REVIEW_OVERSMOOTHING` verdict | `src/filter_validation.py` | Yes |
| JOINT_GROUPS["axial"] includes Hips | `src/v2_feature_engine.py` line 58 | Yes |
| `compute_quality_gates()` | `src/v2_feature_engine.py` line 181 | Yes |
| `validate_reference()` threshold 0.30 | `src/v2_feature_engine.py` line 261 | Yes |
| `build_pca_engine()` | `src/v2_feature_engine.py` line 514 | Yes |
| `quaternion_log_angular_velocity()` | `src/angular_velocity.py` line 43 | Yes |
| run_pipeline.py uses papermill | `run_pipeline.py` | Yes |
| 53 Python files in src/ | src/ directory | Yes |

---

## Open User Decisions

| ID | Decision | Blocks | Options |
|----|----------|--------|---------|
| UD-006 | Session label naming and value format | Ticket 004 | `651` vs `Subject_651`; `T1` vs `1`; etc. |
| UD-001 | S04 dance-band threshold value (-3.0 dB default) | Ticket 015 | Accept default or specify different value |
| NEW-D1 | Hampel outlier column design | Ticket 011 | Option A (sidecar mask), Option B (single OR column, recommended), Option C (per-joint ~51 cols) |

---

*This document is a living reference. Update it as tickets are completed and decisions are resolved.*
