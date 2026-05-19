# 00 Project Orientation

## Repository snapshot
- **Date:** 2026-05-14
- **Agent:** Claude Sonnet 4.6 (claude-sonnet-4-6) — Audit Mode, Read-only
- **Git branch:** `claude-audit-session`
- **Main branch:** `main`
- **Git status summary:** DIRTY. Working tree has:
  - ~30 modified binary `.c3d` files (subjects 651 and 671 — likely dataset refresh, not code change)
  - 10 deleted `batch_configs/` JSON files (all_sessions, all_subjects, and subject-specific files for 505, 621, 734, 763)
  - 13 deleted `qc/step_03_resample/` PNG validation images
  - 8 deleted `results/Subject_671_p2_r1/` HTML/PNG outputs
  - 2 deleted calibration files: `data/734/T3/Cal*.mcal`, `data/763/T2/Cal*.mcal`
  - `config/config_v1.yaml` modified (last run mutated it — see Risk R2 below)
  - `data/subject_metadata.json` modified
  - 2 **untracked** new files: `.mcp.json`, `GAGA_PIPELINE_AGENT_WORK_PLAN.md`

  **Risk: The working tree is not clean. The audit baseline is this dirty state. Subjects 734, 763, 505, 621 have had their batch configs deleted and are absent from recent derivatives. Only subjects 651 and 671 appear active.**

---

## Top-level directory tree

```
gaga_pipeline_audit/
├── run_pipeline.py              # Main CLI orchestrator (papermill-based)
├── requirements.txt             # Python deps (numpy, pandas, scipy, sklearn, papermill, etc.)
├── test_pipeline_setup.py       # Environment smoke test
├── qa_nb06_sdet_validation.py   # Step 06 validation script
├── generate_batch_config.py     # Batch config generator utility
├── _check_json.py               # JSON validation utility
├── GAGA_PIPELINE_AGENT_WORK_PLAN.md  # [UNTRACKED] This audit's work plan
├── .mcp.json                    # [UNTRACKED] MCP config
├── config/
│   ├── config_v1.yaml           # Single config file (MUTABLE — mutated per run)
│   ├── biomechanical_config.json
│   ├── report_schema.json
│   └── skeleton_schema.json
├── notebooks/                   # 12 notebooks (00–11 + qa_master)
├── src/                         # ~40 Python source modules
├── tests/                       # 21 pytest test files
├── data/                        # Raw CSV input + binary C3D + metadata
│   ├── 651/ (T1, T2, T3)
│   ├── 671/ (T1, T2, T3)
│   └── subject_metadata.json, subjects_registry.json
├── derivatives/                 # Intermediate pipeline outputs (steps 01–06)
│   └── [only subject 671 P1_R1 sessions have outputs]
├── batch_configs/               # JSON batch configs (reduced — several deleted in this branch)
├── blueprints/                  # Design evolution documents (v0, v1, v2)
├── docs/                        # Documentation (spec docs, guides, QC, technical)
├── references/                  # Scientific PDFs and papers
├── reports/                     # Excel engineering audit reports + JSON batch summaries
├── logs/                        # Pipeline execution logs
├── qc/                          # QC validation images (step 02 and 03)
├── examples/                    # Biomechanical guardrails example
├── analysis/                    # [Mostly empty — dashboard PNG deleted]
├── results/                     # [Mostly empty — Subject_671_p2_r1 outputs deleted]
└── audit_outputs/               # [NEW — created by this phase]
```

---

## Major documents/specs found

| File | Apparent role | Current/legacy/unknown | Notes |
|------|--------------|------------------------|-------|
| `docs/PIPELINE_PROCESSING_README.md` | Authoritative reference for pipeline steps 01–06+08 | **Current** | Claims to be "the authoritative reference" for CSV→kinematics_master.parquet. Describes 3-stage filtering, reference detection, kinematics. |
| `docs/KINEMATIC_FEATURES_README.md` | Master parquet schema contract | **Current** | Documents all feature columns in kinematics_master.parquet — categories A through F. |
| `docs/METHODOLOGY_SPEC_v2.md` | Downstream feature extraction spec (4-feature, v3.0) | **Current** | Dated 2026-04-06. Explicitly supersedes METHODOLOGY_SPEC.md. Defines ATF, D_eff, TM, Joint Gini. |
| `docs/METHODOLOGY_SPEC.md` | Previous downstream spec (7-feature, v2.0) | **Superseded / Semi-legacy** | Dated 2026-04-06. Explicitly superseded by v2.md. Contains 7 features including dropped F3 (Amplitude), F6 (JcvPCA), F7 (JsvCRP). |
| `docs/Thesis_Analytical_Pipeline.md` | Original thesis analysis pipeline (3+3+1, v1.4) | **Legacy** | Dated 2026-03-25. References N=2 study, git branch `pipeline_v6.3_qa`. Contains 3+3+1 feature set including state-space entropy, centroid displacement, Sample Entropy, RQA. |
| `docs/STEP_07_MISSION_PLAN.md` | Step 07 (Pulsicity/Flow) implementation plan | **Planned / not implemented in default run** | Notebook 07 exists (`07_pulsicity_flow.ipynb`) but is NOT in `run_pipeline.py` default sequence `['01','02','03','04','05','06','08']`. |
| `blueprints/Feature_Blueprint_v2.md` | Feature audit and committee quote verification | **Current design artifact** | Machine-generated blueprint with 15 features audited. Contains literature traceability matrix. |
| `blueprints/Feature_Blueprint_v0.md` | Early feature blueprint | **Legacy design artifact** | Unknown |
| `blueprints/Feature_Blueprint_v1.md` | Intermediate feature blueprint | **Legacy design artifact** | Unknown |
| `blueprints/architcture.md` | Architecture document [note: typo in filename] | **Unknown** | Not yet read |
| `blueprints/study_framing_for_agents.md` | Study framing for agents | **Unknown** | Not yet read |
| `blueprints/verified_extractions_v2.json` | Verified literature extractions | **Current reference** | JSON — literature quotes matched to features |
| `docs/JOINT_NAMING_CONVENTION.md` | Joint naming standard | **Current** | Not yet read in detail |
| `docs/ANATOMICAL_REGION_MAPPING.md` | Joint-to-region aggregation mapping | **Current** | Not yet read in detail |
| `docs/ROM_DOCUMENTATION.md` | Range of Motion analysis doc | **Current** | Not yet read |
| `docs/HEIGHT_ESTIMATION_DOCUMENTATION.md` | Anthropometric height estimation | **Current** | Not yet read |
| `docs/PIPELINE_RUN_CONVENTION.md` | RUN_ID propagation convention | **Current** | Not yet read |
| `docs/guides/PIPELINE_USAGE.md` | User pipeline guide | **Current** | Not yet read |
| `docs/technical/METHODS_DOCUMENTATION.md` | Scientific methods documentation | **Current** | Not yet read |
| `docs/STEP_0_AUDIT_REPORT.md` | Previous audit report for Step 0 | **Unknown** | Possibly a prior audit pass |
| `docs/QA_NB06_TEST_PLAN.md` | QA test plan for notebook 06 | **Current** | Not yet read |
| `docs/QA_PIPELINE_GLASSBOX_MASTERPLAN.md` | Full pipeline QA master plan | **Current / important** | Not yet read — likely important for Phase 4 |
| `GAGA_PIPELINE_AGENT_WORK_PLAN.md` | This audit's operational work plan | **Current / governing** | Untracked. The source of truth for this audit session. |

---

## Major source modules found

| File | Apparent role | Related pipeline layer | Notes |
|------|--------------|----------------------|-------|
| `src/pipeline.py` | Monolithic pipeline execution engine | Layer A — Steps 01–06 | Contains `RunCtx`, `compute_q_local()`. Uses papermill notebook execution. Imports from many submodules. |
| `src/pipeline_config.py` | Config loader / setup | Step 00 | Not yet read in detail |
| `src/config.py` | `CONFIG` singleton | Shared across all stages | Used by nearly every module |
| `src/preprocessing.py` | CSV parsing and gap-fill preprocessing | Step 01–02 | Contains `parse_optitrack_csv()` |
| `src/gapfill_positions.py` | Position gap filling | Step 02 | Separate from quaternion gap fill |
| `src/gapfill_quaternions.py` | Quaternion gap filling (SLERP) | Step 02 | |
| `src/resampling.py` | Time-grid resampling | Step 03 | Contains `estimate_fs`, PCHIP, SLERP resamplers |
| `src/filtering.py` | 3-stage Butterworth + Hampel + median filter | Step 04 | Per `config_v1.yaml`: `method: 3_stage` |
| `src/filter_validation.py` | Filter quality validation | Step 04 QC | |
| `src/sg_filter_validation.py` | Savitzky-Golay filter validation | Step 04 / SG derivative | |
| `src/reference.py` | Static T-pose reference detection | Step 05 | Contains `detect_static_reference`, `compute_q_ref_and_ref_qc` |
| `src/reference_validation.py` | Reference quality validation | Step 05 QC | |
| `src/quaternion_ops.py` | Core quaternion math | Shared | Contains `quat_normalize`, `quat_shortest`, `quat_enforce_continuity`, `quat_mul`, `quat_inv` |
| `src/quaternions.py` | Additional quaternion utilities | Shared | Two separate quaternion modules — potential confusion |
| `src/quaternion_normalization.py` | Quaternion normalization | Shared | Third quaternion module |
| `src/euler_isb.py` | ISB Euler angle conventions | Step 06 | `get_euler_sequence()` — ISB compliance |
| `src/angular_velocity.py` | Angular velocity computation | Step 06 | Omega in child body frame |
| `src/com_engine.py` | Whole-body center of mass | Step 06 | Segment mass weighting |
| `src/core_kinematics_engine.py` | Core kinematics computation | Step 06 / Layer B | Added in most recent commit — possibly the new clean engine |
| `src/v2_feature_engine.py` | V2 feature extraction | Layer C — Methodology v2 | Added in most recent commit — implements METHODOLOGY_SPEC_v2.md |
| `src/skeleton_defs.py` | Skeleton joint hierarchy definitions | Shared | Parent map, depth order |
| `src/artifact_validation.py` | Artifact detection and flagging | Step 02/06 QC | |
| `src/artifacts.py` | Artifact definitions | Step 02/06 | Another artifact module |
| `src/kinematic_repair.py` | Kinematic repair logic | Post-step 06 | |
| `src/bone_length_validation.py` | Bone length QC | Step 02 | |
| `src/burst_classification.py` | Movement burst classification | Step 07? | |
| `src/pulsicity.py` | Pulsicity metric | Step 07 | Not in default pipeline |
| `src/EDA_PCA.py` | EDA and PCA analysis | Layer C / Notebook 10 | |
| `src/joint_statistics.py` | Joint-level statistics | Step 06 / reporting | |
| `src/interpolation_logger.py` | Logging of interpolation events | Step 02 QC | |
| `src/interpolation_tracking.py` | Interpolation tracking | Step 02 QC | |
| `src/calibration.py` | Calibration utilities | Step 05? | |
| `src/coordinate_systems.py` | Coordinate system transforms | Shared | |
| `src/export_tables.py` | Master table export | Step 06 / reporting | `build_master_tables()` |
| `src/forensic_report.py` / `forensic_plots.py` / `forensic_config.py` | Forensic reporting module | Reporting | `_run_forensic_batch.py` entry point |
| `src/gate_integration.py` | QC gate integration | Step 06 QC | |
| `src/interactive_viz.py` | Interactive visualization | Dashboard | |
| `src/lcs_visualization.py` | Local coordinate system visualization | Visualization | |
| `src/qc.py` / `src/qc_columns.py` | QC logic and column definitions | Multiple steps | |
| `src/snr_analysis.py` | SNR / signal quality analysis | Step 04 | |
| `src/time_alignment.py` | Time alignment utilities | Step 03 | |
| `src/units.py` | Unit conversion utilities | Shared | |
| `src/utils.py` / `src/utils_nb07.py` | General utilities | Shared | Two utils files — `utils_nb07.py` specific to step 07 |
| `src/validation.py` | General validation | Multiple steps | |
| `src/subject_validation.py` | Subject-level validation | Step 01 | |
| `src/winter_export.py` | Winter residual analysis export | Step 04 QC | |

---

## Major notebooks found

| Notebook | Apparent role | Current/legacy/unknown | Notes |
|----------|--------------|----------------------|-------|
| `00_setup.ipynb` | Environment setup and config check | Current | Step 00 |
| `01_Load_Inspect.ipynb` | Parse and load raw CSV | Current | Step 01 |
| `02_preprocess.ipynb` | Gap filling, bone length QC | Current | Step 02 |
| `03_resample.ipynb` | Uniform time grid resampling | Current | Step 03 |
| `04_filtering.ipynb` | 3-stage Butterworth + Hampel filter | Current | Step 04 |
| `05_reference_detection.ipynb` | Static T-pose reference detection | Current | Step 05 |
| `06_ultimate_kinematics.ipynb` | Master kinematics feature computation | Current | Step 06 — produces kinematics_master.parquet |
| `07_pulsicity_flow.ipynb` | Pulsicity / behavioral metrics | Planned / partial | **NOT in default `pipeline_sequence`** in `run_pipeline.py`. Has own mission plan. |
| `08_engineering_physical_audit.ipynb` | Engineering and physical audit report | Current | Step 08 — in default sequence |
| `09_Subject_Exploration_Dashboard.ipynb` | Subject exploration dashboard | Legacy / current? | Mentioned in Thesis_Analytical_Pipeline. May contain legacy logic. |
| `10_EDA_PCA.ipynb` | EDA and PCA analysis | Current / exploratory | Not in README's notebook list. New. |
| `11_METH_SPEC_v2_Features.ipynb` | METHODOLOGY_SPEC_v2 feature implementation | Current — v2 features | Not in README's notebook list. Implements new 4-feature spec. |
| `qa_master_pipeline_validation.ipynb` | Master pipeline QA validation | Current | Referenced in QA plan |

**Note:** `run_pipeline.py` sequence is `['01', '02', '03', '04', '05', '06', '08']`. Notebooks 07, 09, 10, 11 are NOT automated. This is a significant gap between the notebook inventory and the automated pipeline.

---

## Config files

| File | Apparent role | Notes |
|------|--------------|-------|
| `config/config_v1.yaml` | Single pipeline configuration file | **MUTABLE** — `run_pipeline.py` overwrites `current_csv`, `subject_id`, `subject_height_cm`, `subject_mass_kg` on every run. This means the config reflects the LAST run, not a stable snapshot. Currently points to `671/T3/671_T3_P1_R1_...`. **Reproducibility risk.** |
| `config/biomechanical_config.json` | Biomechanical constants | Not yet read in detail |
| `config/report_schema.json` | Report output schema | Not yet read in detail |
| `config/skeleton_schema.json` | Skeleton joint hierarchy schema | Not yet read in detail |

---

## Data/output directories

| Directory | Apparent contents | Notes |
|-----------|------------------|-------|
| `data/651/T1/`, `T2/`, `T3/` | CSV + C3D files for subject 651 | 5–6 sessions per timepoint (P1R1, P1R2, P2R1, P2R2, P3R1, TEST). All C3D files are git-modified. CSVs are the pipeline inputs. |
| `data/671/T1/`, `T2/`, `T3/` | CSV + C3D files for subject 671 | 4–5 sessions per timepoint. All C3D files git-modified. |
| `data/subject_metadata.json` | Subject-level metadata | Modified in working tree |
| `data/subjects_registry.json` | Per-subject anthropometrics (height/weight) | Used by `run_pipeline.py` |
| `derivatives/step_01_parse/` | Parsed parquet outputs | Only 3 files — subject 671 T1, T2, T3 (P1_R1 only) |
| `derivatives/step_02_preprocess/` | Preprocessed parquets + interpolation logs | Subject 671 P1_R1 T1/T2/T3 |
| `derivatives/step_03_resample/` | Resampled parquets | Subject 671 P1_R1 T1/T2/T3 |
| `derivatives/step_04_filtering/` | Filtered parquets + PSD validation PNGs + Winter residual data | Subject 671 P1_R1 T1/T2/T3 |
| `derivatives/step_05_reference/` | Reference maps, Euler reference, biomechanical audit | Subject 671 P1_R1 T1/T2/T3 |
| `derivatives/step_06_kinematics/` | `kinematics_master.parquet` + outlier/validation reports | Subject 671 P1_R1 T1/T2/T3. **No step_07 directory exists.** |
| `reports/` | Engineering audit Excel files + batch JSON summaries | 3 Excel files + 3 batch JSON, all dated 2026-05-14 |
| `logs/` | Execution logs | 2 log files dated 2026-05-14 |
| `qc/step_02_preprocess/` | QC images (empty or minimal) | Not inspected in detail |
| `qc/step_03_resample/` | Resample validation PNGs | Only 3 remain for 671 T1/T2/T3 P1_R1; others deleted |
| `references/` | Scientific PDFs (Winter, Wu, Cereatti, OptiTrack validation, etc.) | 7 PDFs + papers.zip + `papers2/` subdir with 4 more papers |
| `batch_configs/` | JSON batch configs | Only 651 and 671 configs remain; 734/763/505/621 configs deleted |

---

## Tests found

| Path | Apparent coverage | Notes |
|------|------------------|-------|
| `tests/test_artifacts.py` | Artifact detection | |
| `tests/test_calibration.py` | Calibration | |
| `tests/test_coordinate_systems.py` | Coordinate transforms | |
| `tests/test_euler_isb.py` | ISB Euler angles | Critical — ISB compliance |
| `tests/test_filter_validation.py` | Filter validation | |
| `tests/test_filtering.py` | 3-stage filter | |
| `tests/test_gapfill_positions.py` | Position gap filling | |
| `tests/test_gates_verification.py` | QC gate verification | |
| `tests/test_phase2_filtering.py` | Phase 2 filtering | |
| `tests/test_phase4_kinematics.py` | Phase 4 kinematics | |
| `tests/test_preprocessing.py` | CSV parsing / preprocessing | |
| `tests/test_qc_columns.py` | QC column definitions | |
| `tests/test_quat_norm.py` | Quaternion normalization | |
| `tests/test_reference_alignment.py` | Reference pose alignment | |
| `tests/test_reference_gravity_guard.py` | Reference gravity guard | Critical — T-pose quality gate |
| `tests/test_reference_validation.py` | Reference validation | |
| `tests/test_resample.py` | Resampling | |
| `tests/test_resample_pchip.py` | PCHIP resampling | |
| `tests/test_simple_gapfill.py` | Simple gap filling | |
| `tests/test_time_alignment.py` | Time alignment | |
| `tests/test_units.py` | Unit conversion | |
| `tests/test_validation.py` | General validation | |

**Summary:** 21 test files present. Good coverage signal at this level. Test contents not yet inspected. No test runner output available.

---

## Initial risks / unknowns

| ID | Risk | Confidence | Priority |
|----|------|-----------|----------|
| R1 | **Dirty git state with no clean baseline.** ~30 modified binary C3D files and ~25 deleted files. The derivative outputs available for audit are from an unclear pipeline version. We cannot confirm these derivatives were produced by the code currently in the repo. | High | Critical |
| R2 | **`config/config_v1.yaml` is mutable per-run.** `run_pipeline.py` overwrites `current_csv`, `subject_id`, height, weight on every file. A re-run would silently change the config, making the config file an unreliable record of what produced any given derivative. | High | High |
| R3 | **Three generations of downstream methodology documents** (`Thesis_Analytical_Pipeline.md` v1.4, `METHODOLOGY_SPEC.md` v2.0, `METHODOLOGY_SPEC_v2.md` v3.0) coexist. Clear formal supersession exists (v3.0 supersedes v2.0), but v1.4 (3+3+1 legacy) is not explicitly marked superseded in the file itself. `notebook/09_Subject_Exploration_Dashboard.ipynb` likely contains legacy logic. | Medium–High | High |
| R4 | **Notebooks 07, 09, 10, 11 are not in the automated pipeline sequence.** The README describes an 8-notebook pipeline (01–06, 08). Notebooks 10 and 11 are not mentioned in README. Step 07 (pulsicity/flow) has a detailed mission plan but is decoupled from the automated run. It is unclear whether these notebooks produce outputs that downstream analysis depends on. | Medium | High |
| R5 | **Three separate quaternion utility modules** (`src/quaternion_ops.py`, `src/quaternions.py`, `src/quaternion_normalization.py`). Risk of divergent implementations or duplicate/conflicting functions. | Medium | Medium |
| R6 | **`core_kinematics_engine.py` and `v2_feature_engine.py`** were added in the most recent commit (PR #7), together with `METHODOLOGY_SPEC_v2.md`. These are new modules whose integration with the existing pipeline (which runs via notebook 06) is unknown. The relationship between the old `src/pipeline.py` engine and the new `core_kinematics_engine.py` is unclear. | Medium | High |
| R7 | **Only subject 671 P1_R1 sessions have derivatives** (T1, T2, T3 — 3 sessions). No derivatives exist for 651, 734, 763, or any other 671 session. The audit baseline is extremely narrow. Whether results generalize to other subjects/sessions is unknown. | High | High |
| R8 | **`config_v1.yaml` contains multiple magic numbers** (e.g., `cutoff_hz: 8.0`, `max_gap_pos_sec: 1.0`, `max_gap_quat_sec: 0.25`, `ref_search_sec: 8.0`, `sg_window_sec: 0.175`, `omega_p99_alert: 60.0`). Whether these are literature-justified or empirically chosen is not documented in the config file. Needs Phase 1 and Phase 4 scrutiny. | High | High |
| R9 | **`step_07_behavioral/` directory does not exist in derivatives.** Step 07 has never been run in the current data. | Low (confirmed) | Medium |
| R10 | **`GAGA_PIPELINE_AGENT_WORK_PLAN.md` is untracked** — not committed to git. Should be committed before the audit produces permanent outputs, to ensure the governing document is version-controlled alongside the audit artifacts. | Low | Low |

---

## Recommended next phase

**Phase 1 — Specs source-of-truth and conflict map.**

The most urgent risk is the coexistence of three generations of downstream methodology documents and the ambiguous role of `notebook/09_Subject_Exploration_Dashboard.ipynb` and `src/core_kinematics_engine.py` (new). Before auditing any code, the authority hierarchy must be formally established.

Specific conflicts to resolve in Phase 1:
1. `Thesis_Analytical_Pipeline.md` (v1.4) vs `METHODOLOGY_SPEC.md` (v2.0) vs `METHODOLOGY_SPEC_v2.md` (v3.0): which features are live vs archived?
2. `src/pipeline.py` vs `src/core_kinematics_engine.py`: which engine governs Step 06?
3. Joint naming: does `Chest` appear in any code/config, or has it been fully replaced by `Spine1`?
4. PCA methodology: combined PCA vs T1-anchored PCA — which does the current code implement?
5. What does `notebooks/09_Subject_Exploration_Dashboard.ipynb` depend on — is it legacy?

---

## Prompt for next agent

```
You are the Specification Reconciliation Agent for Phase 1 of the Gaga Pipeline audit.

Read first:
1. GAGA_PIPELINE_AGENT_WORK_PLAN.md (the governing work plan — full read required)
2. audit_outputs/audit_index.md
3. audit_outputs/00_project_orientation.md (Phase 0 output — read fully)

Your task is Phase 1 — Specs source-of-truth and conflict map.

The key documents to read and reconcile are:
- docs/Thesis_Analytical_Pipeline.md
- docs/METHODOLOGY_SPEC.md
- docs/METHODOLOGY_SPEC_v2.md
- docs/PIPELINE_PROCESSING_README.md
- docs/KINEMATIC_FEATURES_README.md
- blueprints/Feature_Blueprint_v2.md (selectively)

Key conflicts already identified in Phase 0 (Risk R3, R5, R6):
- Three methodology generations coexist.
- Two kinematics engines (src/pipeline.py vs src/core_kinematics_engine.py).
- Three quaternion modules.

Produce: audit_outputs/01_specs_source_of_truth.md and audit_outputs/01_spec_conflicts_register.md

Mode: Read-only. No code changes.
Stop after writing both files.
```
