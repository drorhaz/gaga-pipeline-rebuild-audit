# Implementation Logs — Phase 13

Phase 13 implementation logs are written here, one file per ticket.

## Naming convention

```
TICKET_001_config_snapshot.md
TICKET_002_s01_hard_fail_gate.md
TICKET_003_s03_frame_count_fix.md
TICKET_004_ref_is_fallback_session_labels.md
TICKET_005_ref_quality_score_tpose_failed_guards.md
TICKET_006_hard_exclude_feature_engine.md
TICKET_007a_pyarrow_metadata_fields.md
TICKET_007b_quat_diagnostics_hampel_sidecar.md
TICKET_008_artifact_fraction_reference_threshold.md
TICKET_009_s02_labels_enhanced_logging.md
TICKET_010_hips_atf_axial_exclusion.md
TICKET_011_is_hampel_outlier_propagation.md
TICKET_012_fast_qc_script.md
TICKET_013_nb08_session_count_sync.md
TICKET_014a_session_qc_report.md
TICKET_014b_feature_reliability_table.md
TICKET_015_s04_adaptive_dance_band.md
```

## Log file structure

Each log file must include:

- Pre-implementation statement (completed before any code is written)
- List of files changed
- Tests run and results
- Regression comparison (before/after parquet checksums)
- Issues encountered
- Post-implementation sign-off

See `phase_12_implementation_backlog/12_implementation_backlog_CORRECTED.md` for the
full implementation log template.

## Rules

- One file per ticket, created BEFORE any code is written for that ticket
- No log file = no implementation for that ticket
- Every log must reach post-implementation sign-off status before the next ticket begins
- Logs are permanent audit records — do not delete or overwrite

## Status

No logs exist yet. Implementation has not begun.

**Gate:** `12_implementation_backlog_CORRECTED.md` exists. Do not create any log file
until the user approves the corrected backlog and UD-006 is resolved.
