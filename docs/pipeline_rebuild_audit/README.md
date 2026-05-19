# Pipeline Rebuild Audit — Source of Truth

**Current status:** Phase 12.5 COMPLETE — Ready for user approval of corrected backlog, then Phase 13
**Date:** 2026-05-17
**Approved strategy:** `hybrid_modular_rebuild`

---

## CRITICAL: Do Not Start Phase 13 Without User Approval

Phase 12.5 (Opus Backlog Alignment Review) is **COMPLETE**. The corrected backlog exists.

**Do NOT implement any ticket from the ORIGINAL backlog** (`12_implementation_backlog_ORIGINAL.md`).

**Implement ONLY from:** `12_implementation_backlog_CORRECTED.md` (highest authority).

**Before Phase 13 begins:**
1. User must approve the corrected backlog
2. UD-006 (session label naming) must be resolved before Ticket 004
3. NEW-D1 (Hampel column design) must be resolved before Ticket 011
4. UD-001 (dance-band threshold) must be resolved before Ticket 015

---

## Approved Strategy

**`hybrid_modular_rebuild`**: Preserve all 25 validated algorithms. Rebuild only the
infrastructure layer — config snapshots, stage contracts, gates, metadata propagation,
QC sidecars, Fast QC. No algorithm rewrites. No new frameworks.

**Scope:** 15 tickets (Minimal v1). Strict ordering. One ticket at a time. Regression
check after every ticket before the next begins.

---

## Authority Order

When documents conflict, the later document supersedes the earlier one:

1. `phase_12_implementation_backlog/12_implementation_backlog_CORRECTED.md` ← **highest authority for implementation** (once written)
2. `phase_12_implementation_backlog/12.5_opus_backlog_alignment_review.md` ← correction source
3. `phase_12_implementation_backlog/12_implementation_backlog_ORIGINAL.md` ← Phase 12 draft (do not implement directly)
4. `phase_11_target_skeleton/11.5_architecture_compression_and_logging_review.md` ← architecture corrections R1–R6
5. `phase_11_target_skeleton/11_final_target_skeleton.md` ← architectural blueprint
6. `phase_10_decision_gate/10_rewrite_decision_gate.md` ← rewrite decision and scope
7. `phase_10_decision_gate/10_anti_overengineering_review.md` ← anti-overengineering policy
8. `GAGA_PIPELINE_AGENT_WORK_PLAN.md` ← phase-by-phase agent instructions
9. `audit_index.md` ← audit completion status
10. `earlier_audit_evidence/` ← supporting evidence (Phases 4.5–9.5)

---

## Implementation Rules

- Implementation is ticket-by-ticket only. No batch implementation.
- Every ticket requires a pre-implementation statement written before any code is touched.
- Every ticket requires a regression check before the next ticket begins.
- Implementation logs live in `implementation_logs/`, one file per ticket.
- No ticket log file = no implementation for that ticket.
- Tickets 011–014 must be complete and regression-checked before Ticket 015 begins.
- Ticket 015 requires pre-implementation brief approval before any code is written.

---

## Open User Decisions (Blocking)

| ID | Decision | Blocks |
|----|----------|--------|
| UD-006 | Session label naming convention (`651` vs `Subject_651`) | Ticket 004 |
| UD-001 | S04 dance-band threshold value | Ticket 015 |
| NEW-D1 | Hampel outlier column design (Option B recommended) | Ticket 011 |

These must be resolved before the blocked tickets begin. See the corrected backlog for details.

---

## Folder Structure

```
docs/pipeline_rebuild_audit/
├── README.md                          ← this file (start here)
├── GAGA_PIPELINE_AGENT_WORK_PLAN.md   ← agent phase instructions
├── PROJECT_MEMORY_FOR_IMPLEMENTATION.md ← operational memory for Phase 13 agents
├── audit_index.md                     ← audit phase completion status
│
├── phase_10_decision_gate/
│   ├── 10_anti_overengineering_review.md
│   ├── 10_keep_change_remove_decision_matrix.md
│   ├── 10_rewrite_decision_gate.md
│   └── 10.5_phase10_correction_notes.md
│
├── phase_11_target_skeleton/
│   ├── 11_final_target_skeleton.md
│   └── 11.5_architecture_compression_and_logging_review.md
│
├── phase_12_implementation_backlog/
│   ├── 12_implementation_backlog_ORIGINAL.md   ← draft; do not implement from this
│   ├── 12.5_opus_backlog_alignment_review.md   ← correction source (COMPLETE)
│   ├── 12_implementation_backlog_CORRECTED.md  ← authoritative for Phase 13 (COMPLETE)
│   └── 12_source_cleanup_readiness_map.md      ← src/ file classifications (COMPLETE)
│
├── earlier_audit_evidence/
│   ├── 04.5_external_standards_alignment.md
│   ├── 05_cross_stage_integration_audit.md
│   ├── 05.5_subject_651_evidence_expansion.md
│   ├── 06_master_parquet_ml_readiness_audit.md
│   ├── 07_downstream_methodology_compatibility_audit.md
│   ├── 08_fast_post_collection_qc_requirements.md
│   ├── 09_testing_and_regression_plan.md
│   └── 09.5_unified_qc_plan_alignment.md
│
└── implementation_logs/
    └── README.md                      ← log naming convention and rules
```

---

## What Is Not Here

The following remain in `audit_outputs/` (the original audit working directory):
- Phases 0–3 orientation documents
- Phase 4 per-stage audit files (`04_stage_audits/`)
- Handoff documents (`HANDOFF_*.md`)
- Future features salvage list

These are supporting context, not implementation authority. Consult `audit_outputs/`
if you need to trace a decision back to its original evidence.
