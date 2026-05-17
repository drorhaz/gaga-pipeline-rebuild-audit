# 01 Specs Source-of-Truth and Authority Map

**Phase:** 1
**Date:** 2026-05-14
**Agent:** Claude Sonnet 4.6 — Audit Mode, Read-only
**Mode:** Read-only

---

## 1. Document inventory and layer classification

Every document that could govern any part of the system is classified below by layer, currency, and authority weight.

### Layer A — Motion Processing and Kinematic Pipeline (Steps 01–06 + 08)

Governs: raw CSV parsing → gap-filling → resampling → filtering → reference detection → kinematics computation → `kinematics_master.parquet`.

| Document | Role | Status | Authority |
|----------|------|--------|-----------|
| `docs/PIPELINE_PROCESSING_README.md` | Step-by-step algorithmic reference for Steps 00–08. Describes parsing, gap-fill, resampling, 3-stage filter, reference detection, kinematics, engineering audit. | **Current** | **PRIMARY AUTHORITY for Layer A** |
| `docs/KINEMATIC_FEATURES_README.md` | Column-level schema contract for `kinematics_master.parquet`. Specifies feature categories A–F, units, naming convention, coordinate frames, metadata. | **Current** | **PRIMARY AUTHORITY for Layer B (parquet schema)** |
| `docs/JOINT_NAMING_CONVENTION.md` | Canonical joint names and hierarchy (51 joints; BVH-compatible). Includes bilateral pairs. | **Current** | **PRIMARY AUTHORITY for joint naming** |
| `docs/ANATOMICAL_REGION_MAPPING.md` | Joint-to-anatomical-region aggregation | Current | Secondary (supplements JOINT_NAMING_CONVENTION) |
| `docs/PIPELINE_RUN_CONVENTION.md` | RUN_ID propagation, file naming convention | Current | Secondary (operational) |
| `config/config_v1.yaml` | Live runtime configuration. Single YAML file consumed by all notebooks. | **Current — MUTABLE** | Runtime authority for parameter values, but physically mutable per run (see Conflict C8) |
| `config/skeleton_schema.json` | Machine-readable skeleton joint hierarchy | Current | Technical reference for skeleton structure |
| `config/biomechanical_config.json` | Biomechanical constants | Current | Technical reference for physical constants |
| `docs/STEP_07_MISSION_PLAN.md` | Implementation plan for Step 07 (Pulsicity/Flow) | **Planned — not in production** | Step 07 is excluded from the default `run_pipeline.py` sequence |

### Layer B — Canonical Master Dataset Contract

Governs: `kinematics_master.parquet` schema, units, metadata, quality flags, and downstream read contract.

| Document | Role | Status | Authority |
|----------|------|--------|-----------|
| `docs/KINEMATIC_FEATURES_README.md` | Full column schema: categories A–F. Metadata keys embedded in Parquet. Units: positions in mm, velocities in mm/s and deg/s, rotation vectors in radians. | **Current** | **PRIMARY AUTHORITY for Layer B** |
| `docs/ROM_DOCUMENTATION.md` | Range-of-motion analysis layer | Current | Secondary (supplementary layer B) |
| `docs/HEIGHT_ESTIMATION_DOCUMENTATION.md` | Anthropometric height estimation and COM reliability | Current | Secondary (supplements COM metadata) |

### Layer C — Downstream Thesis Methodology

Governs: which features are computed from `kinematics_master.parquet`, their mathematical definitions, PCA strategy, and longitudinal comparison logic.

| Document | Role | Status | Authority |
|----------|------|--------|-----------|
| `docs/METHODOLOGY_SPEC_v2.md` | **v3.0 (2026-04-06).** Streamlined 4-feature pipeline: F1 ATF, F2 TM, F4 D_eff, F5 Joint Gini. Explicitly supersedes v2.0. Defines reference-anchored PCA on dynamics branch (`omega_mag`), dual-mode sensitivity, block bootstrap, 4 consolidated parameter namespaces. | **Current** | **PRIMARY AUTHORITY for Layer C** |
| `docs/METHODOLOGY_SPEC.md` | **v2.0 (2026-04-06).** 7-feature architecture: F1 ATF, F2 TM, F3 Amplitude A, F4 D_eff, F5 Gini, F6 JcvPCA, F7 JsvCRP. Three narrative layers. | **Superseded** | No authority — explicitly superseded by v3.0 |
| `docs/Thesis_Analytical_Pipeline.md` | **v1.4 (2026-03-25).** 3+3+1 framework: ATF, D_eff, Gini, State-Space Entropy, SampEn, A/P Ratio, RQA. N=2 study. T1-anchored 3-branch PCA. Governs `src/core_kinematics_engine.py` and `notebooks/09_Subject_Exploration_Dashboard.ipynb`. | **Legacy** | **No current authority for new implementation.** Retained as historical record only. NOT explicitly archived in its own file header — this is a documentation gap. |
| `blueprints/Feature_Blueprint_v2.md` | Machine-generated design artifact. Committee quote traceability audit. 15 features audited with literature quote verification. | Legacy/Design reference | Literature traceability reference only |
| `blueprints/Feature_Blueprint_v1.md` | Earlier feature blueprint | Legacy | No current authority |
| `blueprints/Feature_Blueprint_v0.md` | Earliest feature blueprint | Legacy | No current authority |
| `blueprints/verified_extractions_v2.json` | Machine-verified literature quote extractions | Current reference | Literature provenance lookup |

### Layer D — Quality Control and Testing

| Document | Role | Status | Authority |
|----------|------|--------|-----------|
| `docs/quality_control/00_OVERVIEW.md` | QC framework overview | Current | QC authority |
| `docs/quality_control/01_RECORDING_AUDIT_CHECKLIST.md` | Pre-processing recording audit | Current | Operational |
| `docs/quality_control/03_JOINT_LEVEL_TRACKING.md` | Joint-level debugging guide | Current | Operational |
| `docs/QA_NB06_TEST_PLAN.md` | Test plan for notebook 06 | Current | Test authority |
| `docs/QA_PIPELINE_GLASSBOX_MASTERPLAN.md` | Full pipeline QA masterplan | Current | QA authority |
| `docs/STEP_0_AUDIT_REPORT.md` | Prior Step 0 audit report | Historical | Background |

---

## 2. Authority hierarchy (when documents conflict — winner order)

### For processing pipeline (Layer A):

```
1. docs/PIPELINE_PROCESSING_README.md    ← WINS
2. docs/KINEMATIC_FEATURES_README.md     ← WINS for schema questions
3. config/config_v1.yaml                 ← WINS for current parameter values
4. Notebook code (01–06 ipynb)           ← Implementation; must match above
5. src/ Python modules                   ← Implementation; must match above
```

### For downstream methodology (Layer C):

```
1. docs/METHODOLOGY_SPEC_v2.md (v3.0)   ← WINS on all questions
2. src/v2_feature_engine.py              ← Current implementation
3. docs/METHODOLOGY_SPEC.md (v2.0)      ← ARCHIVED — do not use
4. docs/Thesis_Analytical_Pipeline.md   ← LEGACY — do not revive without user approval
5. src/core_kinematics_engine.py        ← LEGACY implementation — do not add to; do not migrate forward without explicit decision
```

### For joint naming:

```
1. docs/JOINT_NAMING_CONVENTION.md      ← WINS
2. config/skeleton_schema.json           ← Machine-readable ground truth
3. src/preprocessing.py correct_motive_name() ← Runtime mapping (OptiTrack names → schema names)
```

---

## 3. Implementation-to-spec mapping

This table maps each live source module to its governing specification.

| Module | Governs | Governing spec | Status |
|--------|---------|---------------|--------|
| `src/preprocessing.py` | Step 01 CSV parsing, name mapping | `PIPELINE_PROCESSING_README.md` §3 | Current |
| `src/gapfill_positions.py`, `src/gapfill_quaternions.py` | Step 02 gap filling | `PIPELINE_PROCESSING_README.md` §4 | Current |
| `src/resampling.py` | Step 03 resampling | `PIPELINE_PROCESSING_README.md` §5 | Current |
| `src/filtering.py` | Step 04 3-stage filter | `PIPELINE_PROCESSING_README.md` §6 | Current |
| `src/reference.py` | Step 05 T-pose reference | `PIPELINE_PROCESSING_README.md` §7 | Current |
| `src/pipeline.py` | Steps 01–06 execution engine (notebook-driven) | `PIPELINE_PROCESSING_README.md` §8 | Current |
| `src/angular_velocity.py`, `src/com_engine.py` | Step 06 kinematics | `KINEMATIC_FEATURES_README.md` | Current |
| `src/v2_feature_engine.py` | Layer C downstream features | `METHODOLOGY_SPEC_v2.md` (v3.0) | **Current — governs new implementations** |
| `src/EDA_PCA.py` | 3-branch PCA backend | `Thesis_Analytical_Pipeline.md` (v1.4) + `core_kinematics_engine.py` | **Legacy** (used by core_kinematics_engine only) |
| `src/core_kinematics_engine.py` | 3+3+1 analytical backend | `Thesis_Analytical_Pipeline.md` (v1.4) | **Legacy** — docstring explicitly states this |
| `src/pulsicity.py` | Noise floor computation (shared by both engines) | `METHODOLOGY_SPEC_v2.md` §F1 + `STEP_07_MISSION_PLAN.md` | **Shared — current for ATF noise floor** |

---

## 4. Open questions (for user decision before Phase 4+ audits)

| Q# | Question | Blocking | Impact |
|----|----------|----------|--------|
| Q1 | Should `src/core_kinematics_engine.py` and `src/EDA_PCA.py` be **formally archived** (moved to `legacy/` or marked in header as superseded)? Right now they are active source files that could be accidentally imported or edited. | No — but clarifies Phase 2 scope | Medium |
| Q2 | Should `docs/Thesis_Analytical_Pipeline.md` be **formally marked as superseded** in its file header? It currently claims to be "the single authoritative reference" for decisions. | No | Low |
| Q3 | The `config_v1.yaml` is overwritten per run. Does the project plan to version or snapshot configs? | No — audit risk only | High for reproducibility |
| Q4 | Who is the "third subject" in the N=3 pilot? `Thesis_Analytical_Pipeline.md` says N=2 (651, 671). No derivatives or batch configs exist for a third subject. | Yes — affects methodology scope | High |
| Q5 | Should `notebooks/09_Subject_Exploration_Dashboard.ipynb` (which uses `core_kinematics_engine.py` / 3+3+1) be **kept as-is as a legacy diagnostic tool** or **replaced** with a v2-spec dashboard? | No — audit question | Medium |
