# PROJECT MEMORY FOR IMPLEMENTATION

**Purpose:** Concise operational memory for any agent implementing Phase 13 tickets.
**Date:** 2026-05-17 (created), last update 2026-05-18 (post Ticket 003).
**Last updated by:** Phase 13 implementer (Opus routing for Ticket 003)

---

## Current Status

- **Phase 12.5:** COMPLETE
- **Phase 13:** IN PROGRESS
  - Ticket 001 (config snapshot) — COMPLETE, signed off
  - Ticket 002 (S01 hard FAIL gate) — COMPLETE, signed off
  - Ticket 003 (S03 1-frame fix) — COMPLETE, signed off
  - Ticket 004 (session labels + ref_is_fallback metadata) — COMPLETE, signed off (4-session Dev Set)
  - Ticket 005 (ref_quality_score / t_pose_failed guards) — COMPLETE, signed off
  - Ticket 006 (hard_exclude in v2_feature_engine) — COMPLETE, signed off
  - Ticket 007a (5 PyArrow metadata fields) — COMPLETE, signed off
  - Ticket 007b (quaternion diagnostics + Hampel + NaN gate logging) — COMPLETE, signed off
  - **TIER 1 CHECKPOINT PASSED** (Dev Set)
  - Ticket 008 (artifact fraction OR-union + ref threshold 0.20) — COMPLETE, signed off
  - Ticket 009 (S02 labels + 9 artifact/gap stats) — COMPLETE, signed off
  - Ticket 010 (Hips excluded from ATF_axial) — COMPLETE, signed off
  - **TIER 2 CHECKPOINT PASSED** (Dev Set; see ATF_axial magnitude in T010 log)
  - Ticket 011 (is_hampel_outlier propagation, Option B) — COMPLETE, signed off
  - **TIER 1 + TIER 2 CHECKPOINTS: BOTH CLOSED** (Dev Set baseline locked 2026-05-19)
- **Active blockers:** UD-001 blocks Ticket 015.
- **Baseline reference:** `audit_outputs/BASELINE_V1_SUMMARY.md`
- **Next tickets available:** 012 (Fast QC — MODERATE_COMPLEXITY, Opus/Max), 013 (NB08 sync — LOCAL, Sonnet), 014a (session_qc_report — LOCAL, Sonnet).

---

## Known Scientific Anomalies (Deferred)

- **NB06 linear kinematics NaN gate:** NB06 Cell 7 drops entire joint axes silently due to a hard `notna().all()` gate on position data. Even 1 NaN frame out of 32,000 removes all linear kinematic derivatives (`lin_rel_p*`, `lin_vel_rel_*`, `lin_acc_rel_*`, magnitude columns) for that joint and axis. This causes session column counts to vary (e.g., 777 vs 807 across Dev Set). Fix is **deferred to post-Minimal-v1**. See full investigation: `docs/pipeline_rebuild_audit/methodology_upgrade_briefs/MUB_NB06_lin_kine_nan_gate_2026-05-18.md`.

- **S04 filtering introduces NaN (discovered during Ticket 009):** Stage-by-stage NaN tracing shows S01/S02/S03 parquets are CLEAN but S04 introduces NaN in select upper-body or axial position columns (Winter/Butterworth boundary effects). This is the ROOT SOURCE of the NaN that triggers the NB06 gate above — not the upstream artifact masking. Mechanical investigation deferred to post-Minimal-v1. See MUB addendum dated 2026-05-19.

---

## Regression Method (post-Ticket-001 finding, enforced from Ticket 002 onward)

**Binary SHA256 of parquet files is NOT a reliable regression indicator** — the pipeline is non-deterministic at the file-encoding level (three runs of the same session produce three different binary hashes; shape and numeric values are stable).

**Authoritative regression mechanism:** content-based SHA256 over sorted numeric column values rounded to 9 decimal places. See `ticket_001_config_snapshot.md` for the helper recipe.

---

## Tier 2 Checkpoint Summary: Baseline Locked — CLOSED

**Status:** CLOSED 2026-05-19
**Tickets:** 008, 009, 010, 011 (all complete, all signed off)
**Dev Set:** 4 sessions (651_T1_P1_R1, 651_T2_P1_R1, 671_T1_P2_R1, 671_T3_P2_R1)

### What Tier 2 Changed

| Ticket | What changed in the data |
|--------|-------------------------|
| 008 | `compute_quality_gates` uses OR-union artifact fraction; art_crit tightened to 0.20 — affects quality_df verdicts in NB11, NOT parquet |
| 009 | S02 method labels corrected in 2 sidecars; new `s02_interpolation_stats.json` with 9 stats; S04 discovered as NaN source (see MUB addendum) |
| 010 | `JOINT_GROUPS["axial"]` no longer includes Hips; atf_axial values increase by 0–1.28% in NB11 — NOT in parquet |
| 011 | `{joint}__is_hampel_outlier` boolean columns corrected from all-False to actual Hampel OR mask; 976–3925 True frames per Dev Set session |

### Dev Set Complexity Summary

| Session | Frames | Col count | Label | Hampel True | Lin_kine drop (joints) |
|---------|--------|-----------|-------|-------------|----------------------|
| 651_T1_P1_R1 | 30,423 | 777 | 651/T1/P1/R1 | 3,925 | 6 joints (y-axis NaN from S04) |
| 651_T2_P1_R1 | 32,110 | 787 | 651/T2/P1/R1 | 3,729 | 4 joints (x-axis NaN from S04) |
| 671_T1_P2_R1 | 16,915 | 807 | 671/T1/P2/R1 | 1,031 | 0 (clean) |
| 671_T3_P2_R1 | 21,773 | 807 | 671/T3/P2/R1 | 976 | 0 (clean) |

### Key Architectural Insight (Tier 2)

Tickets 008 and 010 were labeled `PARQUET_REGEN` in the corrected backlog, but the modified functions (`compute_quality_gates`, `compute_atf`) are called ONLY by NB11 (downstream feature engine), not the kinematics pipeline (NB01–08). `kinematics_master.parquet` is unaffected by those tickets. The "PARQUET_REGEN" label applies to the downstream NB11 feature parquet, which is not part of the Minimal v1 active pipeline sequence. This architectural pattern is now documented here for all future tickets touching `v2_feature_engine.py`.

See full baseline reference: `audit_outputs/BASELINE_V1_SUMMARY.md`

---

## TIER 2 CHECKPOINT LOCK (post Ticket 010, 2026-05-19)

**`kinematics_master.parquet` numeric content hashes — UNCHANGED through entire Tier 1 + Tier 2 (Tickets 001–010):**

| Session | Shape | Numeric content hash (first 16) |
|---------|-------|---------------------------------|
| 651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002 | (30423, 777) | `4e4b81bc9edd2f6b` |
| 651_T2_P1_R1_Take 2026-01-26 05.24.12 PM | (32110, 787) | `b7db8a72f4c11a85` |
| 671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002 | (16915, 807) | `5d13f307c9bc50a3` |
| 671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001 | (21773, 807) | `96ae62165289dc2a` |

**Architectural finding (from Tickets 006/008/010):** Several "PARQUET_REGEN" tickets in the corrected backlog modify functions in `v2_feature_engine.py` that are called ONLY by NB11 / NB09 (downstream feature engine), NOT by the kinematics pipeline (NB01–08). For those tickets, `kinematics_master.parquet` is unaffected by construction — verification is by hash comparison alone, no re-run is needed. The "PARQUET_REGEN" label in those cases refers to the downstream feature parquet from NB11 (not part of Minimal v1 active pipeline).

**Ticket 010 — ATF_axial change magnitude on Dev Set:**

| Session | atf_axial OLD (with Hips) | atf_axial NEW (no Hips) | Δ | % change |
|---------|---------------------------|--------------------------|---|----------|
| 651_T1_P1_R1 | 0.8098 | 0.8202 | +0.0104 | **+1.28 %** |
| 651_T2_P1_R1 | 0.8537 | 0.8537 | 0.0000 | +0.00 % (Hips already absent — see MUB-NB06 / S04 NaN note) |
| 671_T1_P2_R1 | 0.9667 | 0.9676 | +0.0009 | +0.09 % |
| 671_T3_P2_R1 | 0.9264 | 0.9300 | +0.0036 | +0.38 % |

All deltas positive — confirms Hips's structural 0 (root joint, `lin_vel_rel_mag = 0` by definition) was biasing the axial median downward. Magnitude is small (≤ 1.3 %) but real and consistent. See `ticket_010_hips_atf_axial.md` for the per-joint breakdown.

---

## Authoritative Golden Baseline (post Ticket 003)

After Ticket 003 PARQUET_REGEN, all 14 sessions have new content hashes. These are now the regression reference for Tickets 004+.

| Session | Shape | Content hash (first 16 chars) |
|---------|-------|-------------------------------|
| 651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002 | (30423, 773) | `4e4b81bc9edd2f6b` |
| 651_T1_P2_R1_Take 2026-01-15 04.35.25 PM_002 | (19304, 803) | `e535bcaa60457039` |
| 651_T1_P2_R2_Take 2026-01-15 04.35.25 PM_005 | (19895, 803) | `47f62f817a727259` |
| 651_T2_P1_R1_Take 2026-01-26 05.24.12 PM | (32110, 783) | `b7db8a72f4c11a85` |
| 651_T2_P2_R1_Take 2026-01-26 05.24.12 PM_000 | (21602, 803) | `f794c1546332f957` |
| 651_T3_P1_R1_2026-02-11 05.50.42 PM_2026 | (30835, 803) | `f0c431e956d64fa5` |
| 651_T3_P2_R1_2026-02-11 05.50.42 PM_2027 | (22487, 803) | `131a2139ed33e189` |
| 651_T3_P2_R2_2026-02-11 05.50.42 PM_2030 | (22961, 803) | `ba88f4045134e884` |
| 671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002 | (16915, 803) | `5d13f307c9bc50a3` |
| 671_T1_P2_R2_Take 2026-01-06 03.57.12 PM_004 | (17686, 803) | `345df38e3e8411a1` |
| 671_T2_P2_R1_Take 2026-01-15 04.35.25 PM_006 | (20047, 803) | `eeba923f38dac083` |
| 671_T2_P2_R2_Take 2026-01-15 04.35.25 PM_010 | (20765, 803) | `57d5838134a986b3` |
| 671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001 | (21773, 803) | `96ae62165289dc2a` |
| 671_T3_P2_R2_Take 2026-02-03 08.05.01 PM_006 | (22215, 803) | `687f01621ed20d58` |

**Frame-count delta from pre-Ticket-003 baseline:**
- 12 of 14 sessions gained exactly +1 frame (the off-by-one bug was active)
- 2 of 14 sessions kept the same frame count (`651_T1_P1_R1` and `671_T3_P2_R2` — see Ticket 003 implementation log for the float-precision explanation)

**Ticket 003 source-code state:**
- `notebooks/03_resample.ipynb` Cell 3 now calls `src/resampling.py::resample_time_grid()` instead of the inline `np.arange` formula.
- `src/resampling.py::resample_time_grid()` has a defensive clamp: `grid[-1] = min(grid[-1], t1)` to prevent SLERP boundary errors due to FP rounding.
- `resample_summary.json` now logs `n_frames_input`, `n_frames_output`, `frame_count_delta`.

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

| ID | Decision | Blocks | Status | Resolution |
|----|----------|--------|--------|-----------|
| UD-006 | Session label naming and value format | Ticket 004 | **RESOLVED 2026-05-18** | **Option A — Abbreviated values:** `subject_id='651'`, `timepoint='T1'`, `piece='P2'`, `rep='R1'`. All four columns are `str` type. Parsed directly from RUN_ID stem using `re.match(r'^(\d+)_(T\d+)_(P\d+)_(R\d+)', run_id)`. No stripping, no prefix, no type casting. Registry key `'651'` matches `subject_id` value directly. |
| UD-001 | S04 dance-band threshold value (-3.0 dB default) | Ticket 015 | OPEN | Accept default or specify different value |
| NEW-D1 | Hampel outlier column design | Ticket 011 | OPEN | Option A (sidecar mask), Option B (single OR column, recommended), Option C (per-joint ~51 cols) |

---

*This document is a living reference. Update it as tickets are completed and decisions are resolved.*
