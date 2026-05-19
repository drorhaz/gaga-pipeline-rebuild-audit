# 12 Source Cleanup Readiness Map

**Date:** 2026-05-17
**Phase:** 12.5 — Source Cleanup Readiness (companion to Opus Backlog Alignment Review)
**Reviewer:** Phase 12.5 Agent (Claude Opus 4.6)
**Mode:** Classification-only. No files moved, deleted, or modified.
**Method:** Targeted import/reference checks via grep across src/, notebooks/, tests/, and run_pipeline.py.

---

## Executive Summary

53 Python files exist in `src/`. Of these:
- **22** are confirmed ACTIVE_PIPELINE (called by the main processing chain)
- **3** are confirmed ACTIVE_DOWNSTREAM (called by feature engine or analysis notebooks)
- **8** are confirmed ACTIVE_SUPPORT (config, utilities, shared definitions)
- **8** are confirmed FORENSIC_SUBSYSTEM_ONLY (Phase 11.5 verified: self-contained, no active pipeline imports)
- **5** are DEPENDENCY_UNVERIFIED (used by notebooks or tests only; not on the main pipeline path)
- **5** are LEGACY_ARCHIVE_CANDIDATE (no active imports found; specialized/historical code)
- **2** have other classifications (duplicate init, specialized)

**Policy:**
- Do NOT move, delete, or modify any file during Phase 12.5.
- Source cleanup is a SEPARATE activity from the 15 scientific/pipeline tickets.
- Cleanup tickets must not be mixed with core pipeline tickets.
- Any archival move requires: dependency check, notebook reference check, scientific salvage note, user approval.

---

## Classification Legend

| Classification | Meaning | Cleanup timing |
|----------------|---------|----------------|
| `ACTIVE_PIPELINE` | Called by the main pipeline processing chain (run_pipeline.py → notebooks → src/pipeline.py) | Do not touch in Minimal v1 unless a ticket explicitly requires it |
| `ACTIVE_DOWNSTREAM` | Called by feature engine, analysis notebooks, or downstream workflows | Do not touch unless a ticket targets it |
| `ACTIVE_SUPPORT` | Utility/config used by multiple modules | Do not touch |
| `FORENSIC_SUBSYSTEM_ONLY` | Part of the forensic analysis subsystem; confirmed not imported by any active pipeline stage or NB08 | Do not touch in Minimal v1 |
| `DEPENDENCY_UNVERIFIED` | Used by notebooks or tests but not on the main pipeline path; needs full dependency audit before any action | Verify after core tickets |
| `LEGACY_ARCHIVE_CANDIDATE` | No active imports found; may be historical/exploratory code | After core tickets, with user approval |
| `REMOVE_CANDIDATE_AFTER_TESTS` | Likely duplicate or obsolete; confirm with tests before removal | Post-thesis |

---

## src/ File Classification Table

### Active Pipeline Files (22)

| File | Stage | Role | Called by pipeline.py | Called by notebooks | Tickets that touch it | Cleanup timing |
|------|-------|------|----------------------|--------------------|-----------------------|----------------|
| `preprocessing.py` | S01/S02 | CSV parse (`parse_optitrack_csv`), artifact masking, gap detection | YES (line 12) | NB01, NB02 | 002, 009 | During core tickets |
| `gapfill_positions.py` | S02 | PCHIP position gap fill (never triggered on 15 sessions) | YES (indirect) | NB02 | None (KEEP_AS_IS) | Do not touch |
| `gapfill_quaternions.py` | S02 | SLERP quaternion gap fill placeholder (never called) | YES (indirect) | NB02 | None (KEEP_AS_IS) | Do not touch |
| `qc.py` | S02 | Bone length QC | YES (line 16) | NB02 | None | Do not touch |
| `bone_length_validation.py` | S02 | Bone length validation | indirect | NB02 | None | Do not touch |
| `resampling.py` | S03 | CubicSpline + SLERP resampling; `resample_time_grid()` | YES (line 13) | NB03 | 003 | During core tickets |
| `filtering.py` | S04 | 3-stage cleaning pipeline; Butterworth + PSD validation | indirect | NB04 | 007b (Hampel summary), 011, 015 | During core tickets |
| `filter_validation.py` | S04 | PSD analysis; dance-band/noise-band metrics; produces `psd_verdict` | indirect (via filtering.py) | NB04 | 015 (PSD check loop) | During core tickets |
| `filter_export.py` | S04 | Export `__filtering_summary.json` | indirect | NB04 | 007b (add Hampel fields) | During core tickets |
| `winter_export.py` | S04 | Export Winter residual curve data | indirect (via filter_export) | NB04 | None | Do not touch |
| `reference.py` | S05 | Markley mean, static window detection, `t_pose_failed` | YES (line 15) | NB05 | 005 | During core tickets |
| `reference_validation.py` | S05 | Reference quality validation | indirect | NB05 | None | Do not touch |
| `angular_velocity.py` | S06 | `quaternion_log_angular_velocity()`, SavGol window | indirect | NB06 | 007b (quat diagnostics) | During core tickets |
| `com_engine.py` | S06 | de Leva CoM computation | indirect | NB06 | None (KEEP_AS_IS) | Do not touch |
| `euler_isb.py` | S06 | ISB Euler angles (Wu et al. 2005) | YES (line 18) | NB06 | None (KEEP_AS_IS) | Do not touch |
| `quaternion_ops.py` | S06 | Quaternion math operations | YES (line 14) | NB06 | None | Do not touch |
| `quaternion_normalization.py` | S06 | Quaternion renormalization | indirect | NB06 | None | Do not touch |
| `quaternions.py` | S06 | Quaternion utilities | indirect | NB06 | None | Do not touch |
| `skeleton_defs.py` | S06 | Canonical skeleton hierarchy (joint names, parent-child) | indirect | NB06 | None | Do not touch |
| `export_tables.py` | S06 | Build master parquet tables | YES (line 17) | NB06 | 004 (session labels), 007a (metadata) | During core tickets |
| `pipeline.py` | Orchestration | Pipeline orchestration; imports from all stages | N/A (is the pipeline) | Via run_pipeline.py | 001, 002, 004, 007a | During core tickets |
| `artifacts.py` | S02/S04 | Velocity artifact detection, truncation | via __init__.py | NB02 | None | Do not touch |

### Active Downstream Files (3)

| File | Used by | Role | Tickets that touch it | Cleanup timing |
|------|---------|------|----------------------|----------------|
| `v2_feature_engine.py` | NB11 | All thesis features (ATF, TM, D_eff, Gini, PCA) | 006, 008, 010 | During core tickets |
| `pulsicity.py` | NB07/NB11 | ATF, noise floor computation | None (KEEP_AS_IS) | Do not touch |
| `utils_nb07.py` | NB08 | JSON loading, parameter extraction for audit notebook | 013 (may need update) | During core tickets if needed |

### Active Support Files (8)

| File | Role | Used by | Cleanup timing |
|------|------|---------|----------------|
| `__init__.py` | Package init; exports from artifacts, time_alignment, resampling, euler_isb, burst_classification, gate_integration | Module system | Do not touch |
| `config.py` | Re-export of pipeline_config.CONFIG | All modules | Do not touch |
| `pipeline_config.py` | Master config loader from config_v1.yaml | All modules | 001 (add pipeline_version) |
| `utils.py` | General utilities | Multiple modules | 001 (may add snapshot function) |
| `qc_columns.py` | QC column builder | Tests, pipeline | Do not touch |
| `calibration.py` | Anatomical calibration, V-pose correction | NB05, tests | Do not touch |
| `time_alignment.py` | Temporal resampling with artifact awareness | NB03, kinematics_alignment | Do not touch |
| `coordinate_systems.py` | Frame definitions and validation | Tests | Do not touch |

### Forensic Subsystem Only (8)

Confirmed self-contained by Phase 11.5 targeted grep. Not imported by NB08 or any active pipeline stage.

| File | Role | Evidence | Cleanup timing |
|------|------|----------|----------------|
| `forensic_report.py` | Forensic analysis report generation | Only imports forensic_config, forensic_plots, interpolation_logger | Post-thesis |
| `forensic_config.py` | Configuration for forensic subsystem | Only imported by forensic_report | Post-thesis |
| `forensic_plots.py` | Plots for forensic analysis | Only imported by forensic_report | Post-thesis |
| `_run_forensic_batch.py` | Batch runner for forensic analysis | Standalone script; no active imports | Post-thesis |
| `interpolation_logger.py` | Interpolation event logging | Only imported by forensic_report | Post-thesis |
| `interpolation_tracking.py` | Interpolation tracking state | Only referenced within forensic subsystem | Post-thesis |
| `gate_integration.py` | Gate integration logic | Only in forensic_report and __init__.py re-export | Post-thesis |
| `burst_classification.py` | Burst event classification | Only in gate_integration and forensic_report | Post-thesis |

### Dependency-Unverified Files (5)

These files are used by specific notebooks or tests but are NOT on the main pipeline execution path. Full dependency audit needed before any cleanup action.

| File | Apparent role | Known importers | What would be needed to classify |
|------|--------------|-----------------|----------------------------------|
| `kinematic_repair.py` | SLERP/PCHIP surgical repair (enforce_cleaning=false means not called in default runs) | No active imports found | Check if NB06 conditionally imports it; check enforce_cleaning code path |
| `kinematics_alignment.py` | Apply reference offsets using offsets_map.json | time_alignment.py imports assert_time_monotonic; tests/test_reference_alignment.py | Check if NB05 or NB06 uses it; may be part of alternative reference pipeline |
| `validation.py` | General validation (bone length CV, angular velocity checks) | tests/test_validation.py | Check if any notebook calls it |
| `subject_validation.py` | Subject metadata validation (height/mass sanity) | No imports found | Check if NB00 or config loading uses it |
| `units.py` | Mass normalization / per-kg suffix enforcement | tests/test_units.py | Check if v2_feature_engine or NB11 uses it |

### Legacy/Archive Candidates (5)

No active imports found. These appear to be historical, exploratory, or notebook-specific utilities that are no longer in the active processing chain.

| File | Apparent role | Evidence for legacy status | Scientific salvage needed | User approval required | Cleanup timing |
|------|--------------|---------------------------|--------------------------|----------------------|----------------|
| `interactive_viz.py` | ISB compliance visualization, stick figures with LCS | No imports found in any .py or notebook | YES — ISB verification visualization logic may be useful for thesis figures | YES | After core tickets |
| `lcs_visualization.py` | Local Coordinate System skeleton visualization | No imports found | YES — LCS axis visualization may be useful for thesis figures | YES | After core tickets |
| `sg_filter_validation.py` | Savitzky-Golay filter parameter validation | No imports found | Moderate — SG parameter selection logic is documented but not actively used | YES | After core tickets |
| `snr_analysis.py` | Signal-to-Noise Ratio quantification (Cereatti 2024) | No imports found | YES — SNR computation methodology should be salvaged | YES | After core tickets |
| `joint_statistics.py` | ROM and angular velocity statistics | No imports found | Moderate — ROM computation may be useful for future analysis | YES | After core tickets |

### Other (2)

| File | Classification | Notes |
|------|---------------|-------|
| `init.py` | REMOVE_CANDIDATE_AFTER_TESTS | Duplicate of `__init__.py`? Contains only "# Marks src as a Python package." Likely a leftover from manual package init. Verify that removing it doesn't break imports. |
| `artifact_validation.py` | LEGACY_ARCHIVE_CANDIDATE | MAD threshold validation, ROC analysis. No imports found. Research tool, not pipeline code. Salvage methodology notes. |

---

## Cleanup Tickets Recommended

These are SEPARATE from the 15 Minimal v1 tickets. They should be executed AFTER all core tickets are complete and regression-checked.

| # | Cleanup ticket | Files affected | Prerequisites | Priority |
|---|---------------|----------------|---------------|----------|
| C1 | Archive legacy visualization modules | interactive_viz.py, lcs_visualization.py | Core tickets complete; salvage ISB/LCS visualization methods | Post-core |
| C2 | Archive research validation tools | sg_filter_validation.py, snr_analysis.py, artifact_validation.py, joint_statistics.py | Core tickets complete; salvage methodology notes | Post-core |
| C3 | Resolve dependency-unverified files | kinematic_repair.py, kinematics_alignment.py, validation.py, subject_validation.py, units.py | Full import/notebook audit | Post-core |
| C4 | Remove duplicate init.py | init.py | Test that removal doesn't break imports | Post-core |
| C5 | Evaluate forensic subsystem for archival or integration | All 8 FORENSIC_SUBSYSTEM_ONLY files | Core tickets complete; user decision on forensic future | Post-thesis |

---

## What Must Not Be Touched in Minimal v1

The following files must receive ZERO changes during the 15-ticket implementation unless a ticket explicitly names them:

1. All FORENSIC_SUBSYSTEM_ONLY files (8 files)
2. All KEEP_AS_IS algorithm files: `gapfill_positions.py`, `gapfill_quaternions.py`, `com_engine.py`, `euler_isb.py`, `pulsicity.py`
3. All LEGACY_ARCHIVE_CANDIDATE files (5 files)
4. All DEPENDENCY_UNVERIFIED files (5 files)
5. `__init__.py` (unless a ticket requires adding a new export)
6. `quaternion_ops.py`, `quaternion_normalization.py`, `quaternions.py`, `skeleton_defs.py` (core math — KEEP_AS_IS)

**Total files that may be touched by Minimal v1 tickets:** ~15 out of 53

---

*Source cleanup readiness map complete. No files moved, deleted, or modified.*
