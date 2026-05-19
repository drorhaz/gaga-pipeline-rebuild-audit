# Ticket 007a Implementation Log

**Date:** 2026-05-18
**Implementer:** Claude Sonnet 4.6 (LOW_RISK_MECHANICAL)
**Status:** COMPLETE (4-session validation)
**Prerequisites:** Ticket 002 ✓

## Pre-Implementation Statement
- [x] Read Ticket 007a spec
- [x] Inspected NB06 Cell 20 — `pipeline_version` and `ref_is_fallback` already present
- [x] Confirmed actual source files for remaining fields (backlog had wrong paths)
- [x] Blast radius: PARQUET_REGEN (metadata only, no data values change)

## Path Corrections vs Backlog
| Field | Backlog said | Actual source |
|-------|-------------|---------------|
| `bone_qc_status` | S02 kinematics_map.json | `preprocess_summary.json → bone_qc_status` (value: "GOLD"/"PASS"/"WARN"/"ALERT") |
| `gate_01_status` | S01 stage summary JSON | Not present for PASS sessions; inferred "PASS" for any session reaching S06 |
| `filter_psd_verdict` | S04 filtering_summary.json | `filtering_summary.json → filter_params.psd_audit.session_psd_verdict` ✓ |
| `pipeline_version` | config snapshot | Already present in custom_metadata from Ticket 001 ✓ |
| `ref_is_fallback` | S05 reference_info.json | Already added in Ticket 004 ✓ |

## Changes
| File | Change |
|------|--------|
| `notebooks/06_ultimate_kinematics.ipynb` Cell 20 | Add `filter_psd_verdict`, `gate_01_status`, `bone_qc_status` to `custom_metadata` |

## Tests
| Test | Result |
|------|--------|
| All 5 fields in metadata (ref_is_fallback, filter_psd_verdict, pipeline_version, gate_01_status, bone_qc_status) | **PASS** — all 4 sessions |
| Values are non-null and meaningful | **PASS** — e.g. filter_psd_verdict=REVIEW_OVERSMOOTHING, bone_qc_status=GOLD/SILVER |
| Graceful missing-file handling (code present, no error on run) | **PASS** |
| Numeric content hash unchanged from post-T004 baseline | **PASS** — all 4 sessions |
| Label columns still present (T004 regression) | **PASS** |

## Observed Values
| Field | 651_T1 | 651_T2 | 671_T1 | 671_T3 |
|-------|--------|--------|--------|--------|
| ref_is_fallback | false | false | false | false |
| filter_psd_verdict | REVIEW_OVERSMOOTHING | REVIEW_OVERSMOOTHING | REVIEW_OVERSMOOTHING | REVIEW_OVERSMOOTHING |
| pipeline_version | v4.0 | v4.0 | v4.0 | v4.0 |
| gate_01_status | PASS | PASS | PASS | PASS |
| bone_qc_status | GOLD | SILVER | GOLD | SILVER |

**Scientific note:** `filter_psd_verdict=REVIEW_OVERSMOOTHING` for all 4 Dev Set sessions indicates the current filter settings are over-smoothing the dance frequency band. This is the motivation for Ticket 015 (S04 PSD/dance-band correction loop). The metadata correctly captures this pre-correction state.

## Sign-Off
- [x] All tests pass  - [x] 4-session regen successful  - [x] Log complete
