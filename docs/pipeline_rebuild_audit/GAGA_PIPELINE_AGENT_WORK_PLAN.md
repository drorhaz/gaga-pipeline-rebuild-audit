# Gaga Motion Analysis Pipeline - Agent Work Plan

**Document type:** Operational agent work plan / audit protocol / implementation control manual  
**Intended tools:** Claude Code, Cursor, or equivalent code-aware AI agents  
**Project:** Gaga Motion Analysis Pipeline / Gaga Motion Capture Kinematics  
**Primary goal:** Build a disciplined, thesis-grade, scalable process for auditing, improving, and, only if justified, refactoring or rebuilding the motion-processing pipeline.  
**Status:** Working plan v1.0  

---

## 0. First instruction to any AI agent

If you are an AI agent reading this file inside Claude Code, Cursor, or another coding assistant environment, follow this instruction before doing anything else.

### 0.1 Read-first rule

Read this entire plan before inspecting the repository or proposing any code changes.

Then produce a short **Plan Understanding Check** for the user with exactly these sections:

1. **Overall mission** - one paragraph.
2. **Current phase** - identify the first phase you should run.
3. **What you are forbidden to do right now** - especially whether code edits are allowed.
4. **Required output file for the current phase**.
5. **Stop condition for the current phase**.
6. **Files or directories you expect to inspect first**.

After writing the Plan Understanding Check, **stop and wait for user approval**.

Do not inspect the codebase before the user approves the first phase.

---

## 1. Executive summary

This plan defines a staged, auditable workflow for reviewing and improving a complex motion-capture preprocessing and kinematics pipeline. The pipeline transforms raw OptiTrack/Motive CSV recordings into a canonical `kinematics_master.parquet` dataset, which must be suitable for:

- thesis-grade kinematic analysis;
- longitudinal within-subject research;
- statistical modeling;
- machine learning;
- deep learning and sequence modeling;
- batch processing at scale;
- reproducible publication-ready outputs;
- post-collection quality control.

The plan is designed for work with one or more AI agents. Each agent must operate in small, controlled phases. Each phase produces a clear audit or design document. Each phase ends with a stop condition. No agent should silently continue into the next phase.

The plan explicitly prevents common AI-agent failure modes:

- jumping into refactoring too early;
- acting as a yes-man;
- over-engineering a working system;
- rewriting code without understanding scientific intent;
- deleting complex but justified algorithms;
- mixing legacy methodology with current methodology;
- losing context in a long chat;
- making large untestable changes;
- changing downstream analytical semantics accidentally;
- confusing an audit with an implementation task.

The workflow starts in read-only mode, builds a complete audit evidence base, then uses that evidence to decide whether to:

1. keep and harden the current pipeline;
2. refactor incrementally;
3. rebuild selected stages around a cleaner skeleton;
4. or, only if strongly justified, rewrite the pipeline stage-by-stage with regression comparisons.

A full rewrite is allowed only after audit evidence shows it is safer, clearer, and more reliable than hardening the existing system.

---

## 2. Core mission

The mission is not simply to make the code cleaner.

The mission is to create a reliable, inspectable, reproducible, scalable, and scientifically defensible motion-analysis pipeline that can support a biomechanics / movement-science thesis and future publication-quality research.

The final system should:

- preserve validated scientific and mathematical methods;
- remove or simplify unnecessary complexity;
- maintain a modular layered architecture;
- expose clear inputs and outputs for each stage;
- generate useful logs, metadata, and QC artifacts;
- support batch processing across many subjects and sessions;
- produce a canonical `kinematics_master.parquet` dataset per session;
- make that master dataset ML/DL-ready;
- preserve downstream compatibility with thesis metrics;
- support a fast post-collection QC script;
- make failures obvious early;
- allow every result to be traced back to raw data, config, code version, and QC decisions.

---

## 3. Scope of the system being audited

The project has at least three conceptual layers.

### 3.1 Layer A - Motion processing and kinematic pipeline

This layer transforms raw OptiTrack CSV recordings into structured kinematic data.

Typical stages include:

1. Setup and configuration.
2. Parse and load raw OptiTrack CSV.
3. Gap filling and preprocessing.
4. Timebase normalization / resampling.
5. Filtering and signal cleaning.
6. Reference pose detection.
7. Kinematic feature computation.
8. Engineering and physical audit.
9. Orchestration / batch execution.

The current final output of this layer is:

```text
kinematics_master.parquet
```

### 3.2 Layer B - Canonical master dataset contract

`kinematics_master.parquet` must be treated as a canonical analytical dataset, not merely an intermediate file.

It should contain stable, interpretable, high-quality, per-session kinematic data ready for downstream modeling and analysis.

It must support:

- frame-level analysis;
- window-level feature extraction;
- sequence models;
- statistical models;
- longitudinal analysis;
- artifact masking;
- model input selection;
- reproducibility;
- provenance.

### 3.3 Layer C - Downstream research metrics and methodology

Downstream methodology may compute metrics such as:

- Active Time Fraction (ATF);
- Total Movement (TM);
- Effective Dimensionality / Participation Ratio (`D_eff`);
- Joint Gini;
- possibly legacy or exploratory metrics such as entropy, Sample Entropy, RQA, A/P Ratio, or centroid displacement.

The current methodology should be reconciled against the latest specification. Legacy methodology must not be silently revived unless explicitly justified.

---

## 4. Known project documents and expected source-of-truth hierarchy

The repository may contain multiple documents and specifications. Some may be current; some may be legacy; some may describe different layers.

The agent must not assume that every document is equally authoritative.

### 4.1 Expected document roles

Use this initial hierarchy unless repository evidence or user instruction says otherwise:

1. **Processing / kinematic pipeline reference**  
   Governs raw CSV -> preprocessing -> filtering -> reference detection -> Step 06 kinematics -> engineering audit.

2. **Kinematic features / master parquet reference**  
   Governs the schema, units, feature families, metadata, and semantics of `kinematics_master.parquet`.

3. **Methodology Spec v2**  
   Governs the current streamlined downstream thesis feature extraction pipeline, especially ATF, TM, D_eff, and Joint Gini.

4. **Thesis Analytical Pipeline / older 3+3+1 or dashboard specs**  
   Treat as historical / legacy / broader conceptual background unless explicitly reactivated by the user. It may contain valuable risks, cautions, and methodological rationale, but should not automatically override the newer streamlined spec.

### 4.2 Source-of-truth rule

Before any code audit or implementation, the agent must create a source-of-truth map:

```text
audit_outputs/01_specs_source_of_truth.md
```

This file must state:

- which document governs each layer;
- which documents are current;
- which documents are legacy;
- known contradictions;
- unresolved questions;
- which spec should win when conflicts occur.

### 4.3 Conflict examples the agent must check

The agent must explicitly check for conflicts such as:

- `Chest` vs `Spine1` naming;
- quaternion PCA vs rotation-vector PCA;
- combined PCA vs T1-anchored PCA;
- 7-feature or 3+3+1 legacy analysis vs streamlined v2 feature blocks;
- branch-local artifact masking vs all-joint-clean PCA masking;
- raw matrix multiplication vs `pca.transform()`;
- old dashboard logic vs new thin-notebook / library-first design;
- units stated as mm vs meters;
- artifact flags before vs after repair;
- skeleton definitions in code vs documentation.

If conflicts are found, do not resolve them silently. Record them and stop for user decision if they affect architecture or results.

---

## 5. Global agent behavior rules

These rules apply to every agent in every phase.

### 5.1 Default mode is read-only

No code editing is allowed unless the current phase explicitly says implementation is allowed.

Most phases are audit, design, or planning phases.

Forbidden before implementation phases:

- modifying source code;
- rewriting notebooks;
- changing config;
- moving files;
- deleting files;
- reformatting code;
- adding tests unless specifically approved;
- applying refactors;
- running destructive commands;
- changing data outputs.

### 5.2 Stop after every phase

Every phase has an output file and a stop condition.

After writing the required output file, the agent must stop and say:

```text
Phase complete. I wrote: <output file path>. I will not proceed until you approve the next phase.
```

### 5.3 No yes-man behavior

The agent must not simply agree with the user, the previous agent, or the existing code.

For every major finding, classify confidence:

- High confidence;
- Medium confidence;
- Low confidence;
- Unknown / needs inspection.

The agent must explicitly state uncertainty when it cannot verify something from code or data.

### 5.4 No change-for-change's-sake

The default decision is **do not change code**.

A change is justified only if there is:

1. a concrete problem;
2. evidence of the problem;
3. a clear benefit;
4. a bounded implementation scope;
5. a regression or validation check;
6. low or acceptable scientific risk.

If a component is complex but justified, the correct recommendation may be:

```text
Keep as-is.
```

or:

```text
Keep as-is; add documentation/tests only.
```

### 5.5 Anti-overengineering rule

Every proposed change must pass this gate:

- Does it solve a real problem?
- Is the problem observed or only theoretical?
- Can documentation, tests, or logging solve it without code redesign?
- Does the change reduce complexity or increase it?
- Could it alter scientific results?
- Does it preserve downstream compatibility?
- Is there a simpler local fix?
- Is the change necessary now, or should it be deferred?

If the answer is weak, recommend no change or defer.

### 5.6 Context management rule

Do not let one agent accumulate too much context.

If a phase requires reading many files, split the phase by topic or stage.

After each phase, create a concise handoff note:

```text
audit_outputs/HANDOFF_CURRENT.md
```

The handoff note should contain:

- phase completed;
- output files produced;
- key findings;
- open questions;
- recommended next phase;
- exact prompt for the next agent or next chat.

A new agent should read:

1. this plan;
2. `audit_outputs/audit_index.md`;
3. `audit_outputs/HANDOFF_CURRENT.md`;
4. only the audit files needed for its phase;
5. only the code files relevant to its assigned task.

### 5.7 Evidence chain rule

Every later recommendation must trace back to earlier evidence.

A final implementation task must reference:

- audit file where the issue was identified;
- decision matrix row;
- target skeleton section;
- regression check.

If this chain is missing, do not implement.

### 5.8 Critical evaluation addendum

In addition to the general audit workflow, every relevant agent must explicitly evaluate four cross-cutting risks:

1. **Quantitative redundancy and over-processing**  
   The audit must not merely state that interpolation, filtering, smoothing, or repair may be excessive. It must attempt to quantify how much of the data was modified and whether multiple stages are correcting the same problem.

2. **Traceability and iterative post-batch optimization**  
   The audit must verify that run IDs, stage IDs, configuration snapshots, parameter values, input/output hashes or equivalent fingerprints, logs, and decision records are sufficient to reconstruct how each output was produced and to refine logic after batch processing.

3. **Gold-standard dataset readiness**  
   `kinematics_master.parquet` must not be described as gold-standard, thesis-ready, publication-ready, or ML/DL-ready until the final certification gate passes. Before that point, it is only a candidate analytical dataset.

4. **Literature and theoretical assumption gaps**  
   Major methodological assumptions must be classified by evidence level. Assumptions that are exploratory or insufficiently supported must be flagged for deeper literature review, conceptual clarification, sensitivity analysis, or limitation-register inclusion.

These concerns must not be treated as optional qualitative impressions. Each must produce structured evidence, tables, logs, or explicit “instrumentation missing” notes.

---

## 6. Required audit workspace

At the beginning of Phase 0, create this directory structure if it does not already exist:

```text
audit_outputs/
  audit_index.md
  HANDOFF_CURRENT.md
  00_project_orientation.md
  01_specs_source_of_truth.md
  01_spec_conflicts_register.md
  02_current_pipeline_map.md
  03_target_skeleton_draft.md
  04_stage_audits/
  05_cross_stage_integration_audit.md
  06_master_parquet_ml_readiness_audit.md
  07_downstream_methodology_compatibility_audit.md
  08_fast_post_collection_qc_requirements.md
  09_testing_and_regression_plan.md
  10_anti_overengineering_review.md
  10_keep_change_remove_decision_matrix.md
  10_rewrite_decision_gate.md
  11_final_target_skeleton.md
  12_implementation_backlog.md
  13_implementation_logs/
  14_release_and_thesis_readiness_checklist.md
```

Do not invent new output locations unless justified.

Update `audit_outputs/audit_index.md` after every phase.

---

# Phase 6B - Scientific Reference Gap Analysis

## Goal
Identify all methodological, mathematical, and biomechanical assumptions made in the current pipeline that lack explicit literature support or reference code. Produce a targeted "shopping list" of scientific references the user needs to find before the pipeline can be certified.

## Mode
Audit-only.

## Agent role
Scientific Dependencies Auditor.

## Inputs
- Stage audits (04_stage_audits/)
- Cross-stage integration audit (05)
- Draft target skeleton (03)

## Required actions
1. Scan the audits for mathematical or physiological assumptions (e.g., filter cutoff frequencies, gap-filling limits, quaternion unrolling methods, zero-velocity thresholds).
2. Identify where the pipeline currently relies on "magic numbers" or undocumented heuristics.
3. Determine what specific type of external reference is needed to validate or replace each heuristic.
4. Generate a highly specific list of topics, keywords, and reference types (papers vs. reference code) for the user to research.

## Required output
`audit_outputs/06B_scientific_reference_requirements.md`

## Output template
# 06B Scientific Reference Requirements

## Executive Summary
(Brief summary of how dependent the current pipeline is on undocumented heuristics).

## Literature and Reference "Shopping List"
| Pipeline Component | Current Assumption / Magic Number | Risk if incorrect | Required Reference Type | Recommended Search Terms / Topics |
|---|---|---|---|---|
| e.g., Low-pass filter | Uses 6Hz Butterworth | Oversmoothing subtle movement | Academic Paper | "OptiTrack marker filtering cutoff frequency", "Kinematic analysis fast improvisational movement" |
| e.g., Gap filling | Spline interpolation up to 10 frames | Synthesizing fake motion | Academic Paper / Guideline | "Motion capture gap filling maximum acceptable window" |
| e.g., Quaternion distance | Simple Euclidean distance | Mathematically invalid | Reference Code / Paper | "Quaternion shortest path metric python", "Markley mean implementation" |

## Stop condition
After writing the file, stop. The user will use this list to fetch PDFs, papers, or specific GitHub repositories, and inject them into the workspace before proceeding to Phase 7 and Phase 10.

## 7. Decision categories for every component

Every audited component must receive one of these decisions:

| Decision | Meaning |
|---|---|
| `KEEP_AS_IS` | Component is necessary, clear, scientifically justified, and sufficiently integrated. No change recommended. |
| `KEEP_DOCUMENT` | Component is basically good but needs clearer docs or comments. |
| `KEEP_TEST` | Component appears correct but needs tests or regression checks. |
| `KEEP_LOG_QC` | Component is good but needs better logging, metadata, or QC reporting. |
| `MOVE_TO_FAST_QC` | A check or subset of logic should be exposed earlier in post-collection QC. |
| `SIMPLIFY` | Component is more complex than needed; reduce complexity without changing behavior. |
| `LOCAL_REFACTOR` | Small bounded refactor with no intended output change. |
| `MERGE_OR_SPLIT_STAGE` | Stage boundary is wrong; merge or split responsibilities. Requires architecture review. |
| `REMOVE_CANDIDATE` | Component may be unnecessary; removal requires proof and regression comparison. |
| `REDESIGN_CANDIDATE` | Component may need deeper redesign; do not implement without skeleton approval. |
| `REWRITE_CANDIDATE` | Current implementation may be safer to replace. Requires rewrite decision gate. |
| `UNKNOWN_NEEDS_EVIDENCE` | Insufficient evidence. Do not act yet. |

No component should be described only as "good" or "bad". It needs a decision and justification.

---

## 8. Phase overview

The full workflow has fourteen phases.

| Phase | Name | Mode | Main output | Stop? |
|---:|---|---|---|---|
| 0 | Project orientation | Read-only | `00_project_orientation.md` | Yes |
| 1 | Specs source-of-truth and conflict map | Read-only | `01_specs_source_of_truth.md` | Yes |
| 2 | Current pipeline map | Read-only | `02_current_pipeline_map.md` | Yes |
| 3 | Draft target skeleton | Design-only | `03_target_skeleton_draft.md` | Yes |
| 4 | Per-stage audits | Read-only | files under `04_stage_audits/` | Yes after each stage |
| 5 | Cross-stage integration audit | Read-only | `05_cross_stage_integration_audit.md` | Yes |
| 6 | Master parquet ML/DL readiness audit | Read-only | `06_master_parquet_ml_readiness_audit.md` | Yes |
| 7 | Downstream methodology compatibility audit | Read-only | `07_downstream_methodology_compatibility_audit.md` | Yes |
| 8 | Fast post-collection QC requirements | Design-only | `08_fast_post_collection_qc_requirements.md` | Yes |
| 9 | Testing and regression plan | Design-only | `09_testing_and_regression_plan.md` | Yes |
| 10 | Anti-overengineering review and decision gate | Review-only | `10_keep_change_remove_decision_matrix.md` | Yes |
| 11 | Final target skeleton | Architecture-only | `11_final_target_skeleton.md` | Yes |
| 12 | Implementation backlog | Planning-only | `12_implementation_backlog.md` | Yes |
| 13 | Implementation, one ticket at a time | Code changes allowed per ticket | logs under `13_implementation_logs/` | Yes after each ticket |
| 14 | Thesis-grade release and scale validation | Validation-only / limited fixes | `14_release_and_thesis_readiness_checklist.md` | Yes |

---

# Phase 0 - Project orientation

## Goal

Create a high-level map of the repository without making judgments or changes.

## Mode

Read-only.

## Agent role

Repository Orientation Agent.

## Inputs

- This work plan.
- Repository tree.
- Existing docs, notebooks, modules, configs, scripts, tests, batch configs, and results directories.

## Required actions

1. Confirm clean working tree if possible using `git status`.
2. Create `audit_outputs/` structure if missing.
3. Inspect top-level repository structure.
4. Identify major documents/specs.
5. Identify major notebooks.
6. Identify major source modules.
7. Identify configs.
8. Identify expected data input and output directories.
9. Identify tests if present.
10. Identify legacy-looking components vs current-looking components, but do not judge yet.

## Required output

```text
audit_outputs/00_project_orientation.md
```

## Output template

```markdown
# 00 Project Orientation

## Repository snapshot
- Date:
- Agent:
- Git branch:
- Git status summary:

## Top-level directory tree

## Major documents/specs found
| File | Apparent role | Current/legacy/unknown | Notes |

## Major source modules found
| File | Apparent role | Related pipeline layer | Notes |

## Major notebooks found
| Notebook | Apparent role | Current/legacy/unknown | Notes |

## Config files
| File | Apparent role | Notes |

## Data/output directories
| Directory | Apparent contents | Notes |

## Tests found
| Path | Apparent coverage | Notes |

## Initial risks / unknowns

## Recommended next phase

## Prompt for next agent
```

## Stop condition

After writing `00_project_orientation.md`, stop.

---

# Phase 1 - Specs source-of-truth and conflict map

## Goal

Determine which documents govern which parts of the system, and identify conflicts before auditing code.

## Mode

Read-only.

## Agent role

Specification Reconciliation Agent.

## Inputs

- This plan.
- `00_project_orientation.md`.
- All major specs and README files identified in Phase 0.

## Required actions

1. Read the major specs.
2. Classify each spec by layer:
   - processing pipeline;
   - master parquet contract;
   - downstream thesis methodology;
   - legacy analytical dashboard;
   - background/references.
3. Identify the expected authority hierarchy.
4. Identify direct conflicts.
5. Identify unresolved ambiguities.
6. Identify which legacy components must not be revived without explicit approval.

## Required outputs

```text
audit_outputs/01_specs_source_of_truth.md
audit_outputs/01_spec_conflicts_register.md
```

## Required checks

Explicitly check for:

- current vs legacy methodology;
- 19-joint schema conflicts;
- naming conflicts;
- units conflicts;
- artifact semantics conflicts;
- PCA methodology conflicts;
- notebook vs library architecture conflicts;
- feature inclusion/exclusion conflicts;
- differences between thesis analysis v1.x and v2.x.

## Stop condition

After writing both files, stop.

If a conflict affects downstream results or architecture, ask the user for a decision before proceeding.

---

# Phase 2 - Current pipeline map

## Goal

Map how the current pipeline actually works in code, without proposing improvements yet.

## Mode

Read-only.

## Agent role

Current Pipeline Mapper.

## Inputs

- This plan.
- `00_project_orientation.md`.
- `01_specs_source_of_truth.md`.
- Source modules, notebooks, configs, orchestration scripts.

## Required actions

Map the current pipeline from raw input to final outputs.

For each stage, document:

- stage name;
- source files and notebooks;
- input files;
- output files;
- config keys used;
- major functions/classes;
- key algorithms;
- logs/reports emitted;
- failure behavior;
- downstream dependencies.

Do not recommend changes in this phase.

## Required output

```text
audit_outputs/02_current_pipeline_map.md
```

## Suggested stage inventory

Include at least:

1. Setup/config.
2. Raw CSV parsing.
3. Preprocessing/gap filling.
4. Resampling.
5. Filtering.
6. Reference detection.
7. Kinematics/master parquet construction.
8. Engineering audit.
9. Orchestration/batch runner.
10. Downstream feature extraction if present.

## Output template

```markdown
# 02 Current Pipeline Map

## Executive map

## Stage table
| Stage | Code/notebook | Input | Output | Config | Reports/QC | Notes |

## Data flow diagram in text

## Config flow

## Artifact/report flow

## Master parquet creation path

## Current downstream analysis path

## Unknowns requiring later audit

## Recommended next phase
```

## Stop condition

After writing the file, stop.

---

# Phase 3 - Draft target skeleton

## Goal

Propose a preliminary ideal-but-pragmatic target skeleton based on requirements, before deep stage-level audit.

This is not a final architecture and not a code task.

## Mode

Design-only. No code changes.

## Agent role

Target Skeleton Drafting Agent.

## Inputs

- This plan.
- Source-of-truth map.
- Current pipeline map.
- User goals captured in this plan.

## Required actions

Propose a layered target skeleton that separates:

1. raw intake and post-collection QC;
2. parsing;
3. raw structural validation;
4. minimal preprocessing and gap policy;
5. timebase normalization;
6. signal cleaning/filtering;
7. reference pose detection and validation;
8. kinematic state computation;
9. ML-ready master dataset construction;
10. master dataset contract validation;
11. physical/engineering audit;
12. downstream research feature extraction;
13. longitudinal/statistical analysis;
14. visualization/export/provenance.

The skeleton must be minimal and pragmatic.

It must not assume that all current stages should remain.

It must not assume that rewriting is required.

## Required output

```text
audit_outputs/03_target_skeleton_draft.md
```

## Required sections

```markdown
# 03 Target Skeleton Draft

## Design principles

## Proposed layers

## Proposed stages
| Stage | Responsibility | Input | Output | QC/logs | Notes |

## What appears already aligned with current pipeline

## What may need audit before deciding

## What must remain downstream, not in master parquet

## What must remain out of scope for now

## Known risks of this skeleton

## Questions for later audits
```

## Stop condition

After writing the draft skeleton, stop.

---

# Phase 4 - Per-stage audit loop

## Goal

Audit each pipeline stage in depth. Determine whether it is necessary, scientifically valid, engineered well, testable, observable, and appropriately integrated.

## Mode

Read-only unless explicitly approved otherwise. No code changes.

## Agent roles

Each stage may be audited by one agent or by multiple role-specific agents.

Recommended roles:

1. Stage Mapper.
2. Scientific/Biomechanics Reviewer.
3. Software Architecture Reviewer.
4. QC and Reliability Reviewer.
5. Downstream Compatibility Reviewer.
6. Anti-Overengineering Reviewer.

For context control, prefer one stage per chat or one role per chat if the stage is complex.

## Required outputs

Create one file per stage under:

```text
audit_outputs/04_stage_audits/
```

Suggested files:

```text
04_00_setup_config_audit.md
04_01_parse_load_audit.md
04_02_preprocess_gapfill_audit.md
04_03_resampling_audit.md
04_04_filtering_audit.md
04_05_reference_detection_audit.md
04_06_kinematics_master_audit.md
04_08_engineering_audit_audit.md
04_run_pipeline_orchestration_audit.md
04_config_system_audit.md
04_downstream_feature_engine_audit.md
```

## Stage audit questions

For each stage, answer all of these.

### A. Purpose and necessity

- What problem does this stage solve?
- Is the problem real in this dataset?
- Is this stage still needed?
- Is it duplicated elsewhere?
- What would break if this stage were removed?

### B. Scientific validity

- Are the algorithms appropriate for OptiTrack motion capture data?
- Are they appropriate for Gaga / improvisational movement?
- Are assumptions explicit?
- Are thresholds scientifically justified or empirically validated?
- Could the stage distort true motion?
- Could it hide artifacts that should remain visible?

### C. Engineering quality

- Is the code modular?
- Are IO, computation, validation, and reporting separated?
- Are functions testable independently?
- Is there hidden global state?
- Is config handling clean?
- Are names and units clear?
- Are notebooks acting as thin orchestrators or holding core logic?
- Are there unnecessary external dependencies (e.g., using a niche third-party library when native Python, NumPy, or SciPy would suffice)?

### D. Data contract

- What are exact inputs?
- What are exact outputs?
- What schema is expected?
- What units are used?
- What metadata is required?
- Does the stage preserve ordering, time, and index semantics?

### E. Observability and audit trail

- What logs does the stage emit?
- What QC reports does it emit?
- Does it report how much data it changed?
- Does it record thresholds used?
- Does it make failures actionable?
- Can a researcher inspect what happened?

### E2. Quantitative over-processing and redundancy metrics

For any stage that interpolates, repairs, filters, smooths, masks, resamples, detects artifacts, or otherwise alters data, the agent must report quantitative metrics whenever possible:

- percentage of frames affected;
- percentage of joints/segments affected;
- number of gaps detected;
- gap duration distribution;
- maximum gap duration;
- number of gaps filled versus left unfilled;
- number of frames interpolated;
- number of frames repaired;
- number of frames filtered or smoothed;
- number of filtering/smoothing passes applied before this stage and including this stage;
- raw-to-processed deviation summary;
- signal energy or spectral change before versus after filtering, if available;
- per-joint or per-segment alteration load;
- whether this stage duplicates artifact, repair, interpolation, or filtering logic from another stage;
- whether cumulative alteration could make the final signal look cleaner than the measured data justifies.

If these metrics cannot currently be computed, the agent must explicitly state what instrumentation, logs, metadata, or intermediate outputs are missing.

### F. Validation and tests

- What tests exist?
- What synthetic tests should exist?
- What regression tests should exist?
- What edge cases are missing?
- Are before/after plots needed?
- What tolerance would be acceptable for regression?

### G. Fast QC extraction

- Can any check from this stage be run immediately after collection?
- Can it run on raw CSV?
- Does it require parsed data?
- Does it require full preprocessing?
- Should it be part of the fast QC script or not?

### H. Downstream impact

- Does this stage affect `kinematics_master.parquet` schema?
- Does it affect units?
- Does it affect artifact flags?
- Does it affect ATF/TM/D_eff/Gini?
- Does it affect ML/DL readiness?

### I. Overengineering review

- Is the complexity justified?
- Is there a simpler equivalent?
- Is this a case where complexity is necessary, e.g. quaternion geometry?
- Should it remain untouched?

### J. Decision

Use one of the decision categories from Section 7.

## Stage audit output template

```markdown
# Stage Audit: <Stage Name>

## Files inspected

## Current behavior summary

## Purpose and necessity

## Scientific validity

## Engineering quality

## Data contract

## Observability/logging/QC

## Validation and testing gaps

## Quantitative over-processing / redundancy metrics

| Metric | Value | How measured | Concern level | Notes |
|---|---:|---|---|---|
| Frames interpolated | TBD | TBD | TBD | TBD |
| Frames repaired | TBD | TBD | TBD | TBD |
| Gaps filled | TBD | TBD | TBD | TBD |
| Longest filled gap | TBD | TBD | TBD | TBD |
| Filtering/smoothing passes affecting this output | TBD | TBD | TBD | TBD |
| Raw-to-processed deviation | TBD | TBD | TBD | TBD |
| Spectral change after filtering | TBD | TBD | TBD | TBD |
| Duplicated logic with other stages | TBD | TBD | TBD | TBD |
| Missing instrumentation | TBD | TBD | TBD | TBD |

## Fast post-collection QC opportunities

## Downstream methodology impact

## ML/DL master parquet impact

## Overengineering review

## What is already good and should be preserved

## Risks and failure modes

## Decision matrix
| Component | Decision | Evidence | Benefit if changed | Risk if changed | Required validation |

## Recommended action

## Stop / next prompt
```

## Stop condition

After each stage audit file is written, stop.

Do not continue to the next stage until user approval.

---

# Phase 5 - Cross-stage integration audit

## Goal

Evaluate the pipeline as a connected system, not just individual stages.

## Mode

Read-only.

## Agent role

Cross-Stage Integration Reviewer.

## Inputs

- All stage audits.
- Current pipeline map.
- Draft skeleton.

## Required actions

Analyze:

1. repeated artifact detection and repair across stages;
2. repeated smoothing/interpolation/filtering;
3. whether early stages hide problems from later stages;
4. whether later stages compensate for earlier uncertainty;
5. whether data modifications are traceable;
6. whether units remain consistent;
7. whether config is coherent;
8. whether logs and reports are scattered or unified;
9. whether stage boundaries are right;
10. whether notebooks and scripts share responsibilities cleanly.

## Required output

```text
audit_outputs/05_cross_stage_integration_audit.md
```

## Required sections

```markdown
# 05 Cross-Stage Integration Audit

## Executive summary

## Stage interaction map

## Data modification ledger
| Stage | Modification | Quantity reported? | Risk | Needed report |

## Artifact detection / repair overlap

## Interpolation / smoothing / filtering overlap

## Unit and coordinate consistency

## Config and parameter flow

## Logging and provenance flow

## Stage boundary concerns

## Recommended keep/change/remove candidates

## Risks that require regression tests
```

## Stop condition

After writing the file, stop.

---

# Phase 6 - Master parquet ML/DL readiness audit

## Goal

Determine whether `kinematics_master.parquet` is a stable, canonical, high-quality, ML/DL-ready analytical dataset.

## Mode

Read-only.

## Agent role

ML/DL Dataset Contract Reviewer.

## Inputs

- Kinematic features spec.
- Step 06 code.
- Example parquet schema if available.
- Validation reports if available.
- Stage 06 audit.

## Required actions

Audit the master dataset contract.

### 6.1 Schema consistency

Check:

- same columns across sessions;
- stable 19-joint schema;
- feature families present;
- artifact flags present;
- `time_s` present and uniform;
- metadata present;
- no unexpected legacy names.

### 6.2 Units and conventions

Check:

- position units;
- velocity units;
- acceleration units;
- angular velocity units;
- angular acceleration units;
- rotvec units;
- Euler units;
- coordinate frame;
- quaternion convention.

### 6.3 Data quality

Check:

- NaNs;
- Infs;
- zero-variance features;
- impossible values;
- outlier ranges;
- artifact mask coverage;
- frames repaired but not marked;
- missing joints;
- inconsistent lengths.

### 6.4 ML/DL usability

Check:

- ability to construct fixed windows;
- sequence lengths;
- frame-level masks;
- joint-level masks;
- subject/session/timepoint metadata;
- labels vs features separation;
- QC columns vs model input columns;
- leakage risks;
- normalization should be downstream/train-only, not baked into master;
- whether master contains canonical state, not model-specific transforms.

### 6.5 Output design

Recommend whether master parquet should include:

- core kinematic state;
- derived but stable features;
- artifact masks;
- data quality companion columns;
- metadata/provenance;
- optional feature families;
- excluded or unreliable columns.

## Required output

```text
audit_outputs/06_master_parquet_ml_readiness_audit.md
```

## Stop condition

After writing the file, stop.

---

# Phase 7 - Downstream methodology compatibility audit

## Goal

Ensure that any processing or master-parquet changes preserve compatibility with current downstream methodology.

## Mode

Read-only.

## Agent role

Downstream Methodology Compatibility Reviewer.

## Inputs

- Source-of-truth map.
- Methodology v2 spec.
- Kinematic features spec.
- Master parquet audit.
- Downstream code if present.

## Required actions

Check that the master parquet supports:

### ATF

- `{Joint}__lin_vel_rel_mag` exists;
- `{Joint}__is_artifact` exists;
- units are mm/s;
- noise floor function expectations are met;
- artifact frames are excluded, not interpolated or zeroed.

### TM

- endpoint root-relative positions exist for hands and feet;
- units are mm;
- artifact flags exist for endpoints;
- contiguous clean-run handling can be implemented;
- no mask-then-diff gap bridging.

### D_eff and Joint Gini

- 19 exact joint names exist;
- `{Joint}__zeroed_rel_omega_mag` exists;
- artifact masks allow all-joint-clean filtering;
- reference session can be validated;
- PCA fit can be T1-anchored;
- `StandardScaler` and `PCA` can be frozen from reference;
- `pca.transform()` semantics are preserved.

### Legacy compatibility

- identify legacy features that should not be reintroduced;
- identify legacy code that must remain isolated;
- identify any old dashboard assumptions that conflict with v2.

## Required output

```text
audit_outputs/07_downstream_methodology_compatibility_audit.md
```

## Stop condition

After writing the file, stop.

---

# Phase 8 - Fast post-collection QC script requirements

## Goal

Design requirements for a fast script that runs shortly after data collection and determines whether raw data is good enough to proceed.

This is a requirements phase, not implementation.

## Mode

Design-only.

## Agent role

Fast QC Requirements Architect.

## Key principle

The fast QC script must not become a second full pipeline.

It should be fast, focused, interpretable, and actionable.

## Desired status outputs

The script should return one of:

```text
PASS
PASS_WITH_WARNINGS
FAIL
```

## Required actions

Classify checks into three tiers.

### Tier 1 - Raw file checks

Can run on raw CSV and metadata:

- file exists;
- file size plausible;
- filename parseable;
- subject/session/protocol/run present;
- expected metadata rows present;
- Frame and Time columns found;
- duration sufficient;
- frame count sufficient;
- time monotonic;
- approximate sampling rate plausible;
- required segments appear in header;
- calibration metadata available if exported;
- no obvious dead recording.

### Tier 2 - Parsed structural checks

Require parsing but not full processing:

- positions array shape;
- quaternion array shape;
- required joints present;
- NaN fraction per joint;
- all-NaN joints;
- long gaps;
- boundary gaps;
- missing quaternions;
- quaternion norm sanity;
- timestamp jitter;
- basic coordinate range;
- basic velocity spikes from raw positions;
- possible marker/rigid body dropout.

### Tier 3 - Lightweight scientific sanity checks

Still fast, not full pipeline:

- estimated static/T-pose window plausibility;
- motion during expected reference period;
- basic bone-length stability from raw/parsed positions if feasible;
- hands/feet dropout risk;
- session likely to fail later PCA/metrics gates;
- whether recording should be repeated while participant is still available.

## Required output

```text
audit_outputs/08_fast_post_collection_qc_requirements.md
```

Also create a check catalog if useful:

```text
audit_outputs/08_fast_qc_check_catalog.md
```

## Required sections

```markdown
# 08 Fast Post-Collection QC Requirements

## Purpose

## Non-goals

## Runtime target

## Inputs

## Outputs

## PASS/WARN/FAIL rules

## Check catalog
| Check | Tier | Input needed | Severity | Threshold | Message | Maps to pipeline risk |

## Human-readable report design

## Machine-readable JSON schema

## Integration with batch processing

## What must not be included yet

## Future implementation plan
```

## Stop condition

After writing the file(s), stop.

---

# Phase 9 - Testing and regression plan

## Goal

Define tests and regression checks needed before any implementation changes.

## Mode

Design-only.

## Agent role

Testing and Regression Architect.

## Inputs

- All audits so far.
- Current tests if present.
- Example outputs if present.

## Required actions

Design a test pyramid and regression strategy.

### 9.1 Unit tests

For pure functions:

- parser functions;
- gap detection;
- bounded interpolation;
- quaternion normalization;
- SLERP/continuity;
- resampling grid;
- artifact detection;
- filtering utilities;
- reference detection utilities;
- angular velocity;
- SavGol derivatives;
- CoM reliability;
- schema validation;
- QC gate functions.

### 9.2 Synthetic tests

Design synthetic signals with known truth:

- all-zero signal;
- constant velocity;
- single gap shorter than threshold;
- gap longer than threshold;
- boundary gap;
- quaternion sign flip;
- known rotation rate;
- known static T-pose window;
- known artifact spike;
- known bone-length constant skeleton;
- known PCA spectrum;
- known Gini distribution.

### 9.3 Golden-data regression

Choose one or more representative sessions and store summaries, not necessarily huge binary outputs:

- schema hash;
- row count;
- time range;
- NaN summaries;
- artifact summaries;
- cutoff summaries;
- reference window;
- key feature distributions;
- master parquet metadata;
- downstream metric outputs.

### 9.4 Old-vs-new comparison

For refactor/rewrite:

- compare stage outputs;
- compare key summary statistics;
- define tolerances;
- categorize expected vs unexpected differences;
- require explanation for any change in scientific outputs.

## Required output

```text
audit_outputs/09_testing_and_regression_plan.md
```

## Stop condition

After writing the file, stop.

---

# Phase 10 - Anti-overengineering review and rewrite decision gate

## Goal

Challenge all proposed changes. Decide what to keep, what to simplify, and whether a rewrite is justified.

## Mode

Review-only.

## Agent role

Anti-Overengineering Reviewer / Rewrite Decision Reviewer.

## Inputs

- All previous audit files.
- Draft target skeleton.
- Testing plan.

## Required actions

1. Aggregate all recommendations.
2. Remove duplicate recommendations.
3. Challenge each proposed change.
4. Identify changes that only improve aesthetics.
5. Identify changes that add complexity without clear benefit.
6. Identify components that should be explicitly preserved.
7. Produce a keep/change/remove matrix.
8. Decide whether to:
   - harden current pipeline;
   - refactor incrementally;
   - rebuild selected stages;
   - perform full stage-by-stage rewrite.

## Required outputs

```text
audit_outputs/10_anti_overengineering_review.md
audit_outputs/10_keep_change_remove_decision_matrix.md
audit_outputs/10_rewrite_decision_gate.md
```

## Rewrite decision criteria

A rewrite may be justified if several of these are true:

- current code cannot be tested reliably;
- notebooks contain too much hidden logic;
- global state makes behavior unpredictable;
- outputs are inconsistent across sessions;
- legacy and current methodology are deeply mixed;
- changes require touching many unrelated files;
- stage boundaries are fundamentally wrong;
- it is impossible to trace data modifications;
- master parquet contract is unstable;
- incremental hardening would be riskier than rebuilding.

A rewrite is not justified merely because:

- code style is imperfect;
- functions are longer than ideal;
- algorithms are complex but scientifically justified;
- a cleaner architecture is imaginable;
- an agent prefers modern patterns;
- abstractions would look elegant.

## Stop condition

After writing all three files, stop.

The user must approve the strategic path before Phase 11.

---

# Phase 11 - Final target skeleton

## Goal

Build the final target architecture based on audit evidence and the approved strategic path.

## Mode

Architecture-only. No code changes.

## Agent role

Final Skeleton Architect.

## Inputs

- All audits.
- Anti-overengineering review.
- User-approved rewrite/refactor strategy.

## Required actions

Define the final target pipeline skeleton.

For each stage, specify:

- responsibility;
- input contract;
- output contract;
- config contract;
- validation/QC checks;
- logs/reports;
- failure behavior;
- downstream dependencies;
- whether it is current, refactored, new, removed, or deferred.

## Required output

```text
audit_outputs/11_final_target_skeleton.md
```

## Required sections

```markdown
# 11 Final Target Skeleton

## Approved strategy

## Design principles

## Final pipeline layers

## Final stages
| Stage | Status | Responsibility | Input | Output | QC/logs | Implementation notes |

## Master parquet contract

## Fast QC script contract

## Downstream methodology contract

## Removed or deprecated components

## Deferred components

## Architecture decisions

## Risks and required tests
```

## Stop condition

After writing the file, stop.

---

# Phase 12 - Implementation backlog

## Goal

Translate the final skeleton into small, ordered, testable implementation tasks.

## Mode

Planning-only.

## Agent role

Implementation Planner.

## Inputs

- Final target skeleton.
- Testing plan.
- Decision matrix.

## Required actions

Create a backlog of implementation tickets.

Each ticket must include:

- ID;
- title;
- source audit reference;
- rationale;
- files likely touched;
- exact scope;
- non-goals;
- expected behavior;
- required tests;
- required regression comparison;
- rollback plan;
- stop condition.

## Required output

```text
audit_outputs/12_implementation_backlog.md
```

## Priority levels

Use:

- P0: safety/reproducibility blocker;
- P1: required for reliable current pipeline;
- P2: required for fast QC or scale;
- P3: important but not blocking;
- P4: optional/deferred;
- DO_NOT_DO: rejected by anti-overengineering review.

## Stop condition

After writing the backlog, stop.

The user must approve each ticket before implementation.

---

# Phase 13 - Implementation, one ticket at a time

## Goal

Implement approved changes safely and incrementally.

## Mode

Code changes allowed only for the single approved ticket.

## Agent role

Implementation Agent + Regression Agent.

## Non-negotiable rule

Implement exactly one ticket at a time.

Do not batch multiple unrelated changes.

## Required pre-implementation statement

Before editing code, the agent must write:

```markdown
# Implementation Pre-Check: <Ticket ID>

## Ticket

## Audit evidence

## Files expected to change

## Files that must not change

## Intended behavior change

## Expected no-change areas

## Tests/regressions to run

## Rollback plan
```

Then stop and wait for user approval if requested.

## Required implementation behavior

- create or confirm a git branch if user wants;
- inspect only relevant files;
- make minimal changes;
- avoid broad reformatting;
- keep behavior unchanged unless ticket says otherwise;
- update docs only if ticket includes docs;
- add tests if ticket requires tests;
- run relevant tests;
- run regression checks;
- record outputs.

## Required output per ticket

```text
audit_outputs/13_implementation_logs/<ticket_id>_implementation_log.md
```

## Implementation log template

```markdown
# Implementation Log: <Ticket ID>

## Summary

## Files changed

## Why changed

## Exact behavior change

## Tests run

## Regression checks run

## Results

## Differences from old output

## Known residual risks

## Follow-up tickets

## Stop condition
```

## Stop condition

After one ticket is implemented and logged, stop.

Do not start the next ticket without approval.

---

# Phase 14 - Thesis-grade release and scale validation

## Goal

Confirm that the final or improved pipeline is ready for thesis-scale use, batch processing, and publication-quality outputs.

## Mode

Validation-only, with small fixes only if approved.

## Agent role

Release Validation Agent.

## Required checks

### 14.1 Reproducibility

- git commit recorded;
- environment recorded;
- config snapshot recorded;
- input manifest recorded;
- run metadata exported;
- parameters locked for thesis runs.

### 14.2 Batch scalability

- process multiple subjects/sessions;
- dead recordings handled;
- failures do not crash whole batch silently;
- summaries generated;
- QC reports generated;
- reruns deterministic.

### 14.3 Master parquet readiness

- schema consistent;
- metadata complete;
- no unexpected NaNs/Infs;
- artifact flags present;
- units clear;
- downstream columns present.

### 14.4 Downstream methodology readiness

- ATF runs;
- TM runs;
- D_eff/Gini run;
- reference session validation works;
- hard/soft gates work;
- session registry works;
- outputs serialized.

### 14.5 Fast QC readiness

- script or requirements complete;
- PASS/WARN/FAIL logic clear;
- human report clear;
- machine report clear;
- runtime acceptable.

### 14.6 Thesis defense package

- methodology decisions documented;
- limitations documented;
- null result handling documented;
- no untracked manual choices;
- audit trail exists from raw data to results.

## Required output

```text
audit_outputs/14_release_and_thesis_readiness_checklist.md
```

## Stop condition

After writing the release checklist, stop.

---

# Phase 14B - Gold-standard dataset certification and assumption gap review

## Goal

Determine whether the current pipeline outputs can legitimately be described as a gold-standard, thesis-ready, publication-ready, ML/DL-ready analytical dataset.

This phase does not implement changes. It certifies readiness or explicitly labels the dataset as not yet ready.

## Mode

Read-only certification review.

## Agent role

Gold-standard dataset certifier and methodological robustness reviewer.

## Required inputs

- `audit_outputs/11_final_target_skeleton.md`
- `audit_outputs/12_implementation_backlog.md`
- all completed stage audit files
- master parquet validation outputs
- QC reports
- regression reports
- downstream methodology compatibility audit
- testing and regression plan
- final implementation logs, if implementation has begun
- relevant methodology/specification documents

## Gold-standard dataset certification gate

`kinematics_master.parquet` must not be described as gold-standard, thesis-ready, publication-ready, or ML/DL-ready until all of the following pass:

- schema validation;
- stable column naming across sessions;
- unit and coordinate convention validation;
- time-axis validation;
- NaN/Inf validation;
- missingness and artifact audit;
- interpolation, repair, filtering, and smoothing provenance audit;
- per-stage QC report completeness;
- per-stage logs sufficient for reconstruction;
- config snapshot and parameter provenance;
- input/output lineage;
- regression comparison against previous trusted outputs;
- downstream methodology compatibility checks;
- ML/DL readiness checks;
- batch scalability checks;
- reproducibility checks;
- known limitations register;
- unresolved assumption review.

If any item fails, the dataset must be labeled only as one of:

- `candidate_dataset`
- `experimental_dataset`
- `needs_review`
- `not_publication_ready`

The certifying agent must not use stronger language than the evidence supports.

## Literature and assumption gap register

Every major methodological assumption must be entered into an assumption register.

| Assumption | Pipeline module | Current justification | Evidence level | Risk if wrong | Required action |
|---|---|---|---|---|---|
| Example: 0.175s SavGol window preserves Gaga movement dynamics | Filtering / derivatives | Internal rationale + Winter-style filtering logic | internally_justified | Over-smoothing true fast movement | Literature review + sensitivity analysis |

Allowed evidence levels:

- `validated_on_project_data`
- `literature_supported`
- `internally_justified`
- `exploratory`
- `unsupported_needs_review`

Rules:

- Any assumption marked `validated_on_project_data` must cite the validation output or audit file.
- Any assumption marked `literature_supported` must cite the relevant literature or methodology document.
- Any assumption marked `internally_justified` must include the internal rationale and a recommended sensitivity check.
- Any assumption marked `exploratory` must appear in the final limitation register.
- Any assumption marked `unsupported_needs_review` must block publication-ready certification unless explicitly scoped out or resolved.

## Required output

Write:

```text
audit_outputs/14B_gold_standard_certification.md

# 15. Agent prompt templates

Use these prompts to start new chats or new agent roles.

## Model Selection Guidance: Sonnet vs Opus

The default model for this workflow should be Claude Sonnet. Sonnet is the preferred model for most repository inspection, audit writing, documentation, local refactoring, test writing, QC implementation, and routine debugging.

Claude Opus should be used selectively for high-stakes judgment, not simply because a task involves writing or coding.

### Default rule

Use the following rule:

> Sonnet does the work. Opus reviews the high-stakes decisions.

### Use Sonnet for

- repository orientation;
- reading code structure;
- mapping pipeline stages;
- generating stage audit files;
- routine code review;
- writing documentation drafts;
- producing structured audit tables;
- local refactors;
- adding tests;
- implementing QC scripts;
- debugging implementation tickets;
- summarizing individual audit outputs;
- updating logs and changelogs;
- checking straightforward schema or config issues.

### Consider Opus for

Use Opus when the task requires broad judgment, methodological risk assessment, or architectural synthesis, especially when a wrong decision could affect scientific validity, thesis claims, or the long-term pipeline structure.

Consider Opus for:

- deciding whether to keep, refactor, simplify, remove, or rewrite a major component;
- final target skeleton synthesis;
- refactor-vs-rewrite decision;
- anti-overengineering review of accumulated recommendations;
- methodology robustness review;
- downstream compatibility review with thesis metrics;
- final ML/DL readiness review of `kinematics_master.parquet`;
- gold-standard dataset certification;
- reviewing major Step 06 / master parquet design changes;
- reviewing large refactors before merge;
- resolving conflicts between specs, legacy code, and current methodology;
- final thesis/publication readiness assessment.

### Coding policy

For implementation work:

1. Use Sonnet to implement one small ticket at a time.
2. Use Sonnet to run tests, debug, and update logs.
3. Use Opus only if the ticket affects:
   - pipeline architecture;
   - data validity;
   - artifact semantics;
   - filtering/interpolation/repair logic;
   - `kinematics_master.parquet`;
   - downstream methodology outputs;
   - thesis-grade reproducibility;
   - or publication-level claims.

### Writing policy

For writing tasks:

- Use Sonnet for ordinary audit reports, summaries, documentation drafts, prompts, and logs.
- Consider Opus for final synthesis documents, especially:
  - final target skeleton;
  - implementation backlog prioritization;
  - refactor-vs-rewrite decision;
  - gold-standard certification;
  - methodology limitation register;
  - final thesis-grade readiness review.

### Required model decision note

At the start of every phase, the active agent must include a short model decision note:

```md
## Model decision

Recommended model for this phase: Sonnet / Opus

Reason:
- ...
- ...

Is Opus required before proceeding? yes/no

If yes, explain what high-stakes decision requires Opus review.

## 15.1 First agent prompt

```text
Read GAGA_PIPELINE_AGENT_WORK_PLAN.md fully.

Do not inspect the repository yet.
Do not edit code.
Do not refactor.
Do not propose fixes.

First, produce the Plan Understanding Check required in Section 0.1 of the plan:
1. Overall mission
2. Current phase
3. What you are forbidden to do right now
4. Required output file for the current phase
5. Stop condition for the current phase
6. Files or directories you expect to inspect first

Then stop and wait for my approval.
```

## 15.2 Phase execution prompt

```text
You are executing Phase <N>: <phase name> from GAGA_PIPELINE_AGENT_WORK_PLAN.md.

Read only these context files:
- GAGA_PIPELINE_AGENT_WORK_PLAN.md
- audit_outputs/audit_index.md
- audit_outputs/HANDOFF_CURRENT.md
- <specific files needed for this phase>

Follow the phase instructions exactly.
Do not perform work from later phases.
Do not edit code unless this phase explicitly allows it.
Write the required output file(s).
Update audit_outputs/audit_index.md and audit_outputs/HANDOFF_CURRENT.md.
Then stop.
```

## 15.3 Stage audit prompt

```text
You are a stage audit agent for the Gaga Motion Analysis Pipeline.

Assigned stage: <stage name>

Read:
- GAGA_PIPELINE_AGENT_WORK_PLAN.md
- audit_outputs/01_specs_source_of_truth.md
- audit_outputs/02_current_pipeline_map.md
- audit_outputs/03_target_skeleton_draft.md
- the code/notebooks/configs relevant only to <stage name>

Do not edit code.
Do not refactor.
Do not propose broad redesigns.

Produce the stage audit file using the template in Phase 4:
audit_outputs/04_stage_audits/<file_name>.md

For every component, classify it as one of the decision categories in Section 7.
If no change is needed, say so explicitly.
Challenge complexity, but do not remove scientifically justified methods.
After writing the file, stop.
```

## 15.4 Scientific reviewer prompt

```text
You are the Scientific/Biomechanics Reviewer.

Your job is to evaluate whether the assigned pipeline stage is scientifically appropriate for OptiTrack full-body movement data and Gaga improvisational movement.

Do not edit code.
Do not focus on code style.
Do not propose simpler methods unless they preserve scientific validity.

Evaluate:
- assumptions;
- thresholds;
- interpolation/smoothing/filtering risks;
- quaternion/rotation geometry;
- reference pose validity;
- artifact semantics;
- physiological plausibility;
- downstream impact.

Write findings into the assigned audit file section.
If the current method is complex but justified, say: KEEP_AS_IS or KEEP_TEST, not simplify.
Stop after writing your section.
```

## 15.5 Software architecture reviewer prompt

```text
You are the Software Architecture Reviewer.

Your job is to evaluate modularity, stage boundaries, IO separation, configuration, logging, testability, and maintainability. 
You must also explicitly identify and flag unnecessary external dependencies (e.g., using a niche third-party library when native Python, NumPy, or SciPy would suffice).

Do not edit code.
Do not redesign the entire project.
Prefer local improvements over large abstractions.

For each recommendation, state:
- concrete problem;
- evidence;
- minimal fix (including dependency removal if applicable);
- risk;
- required test.

If the current code is good enough, recommend no code change.
Stop after writing your section.


```

## 15.6 QC/reliability reviewer prompt

```text
You are the Data Quality and Reliability Reviewer.

Your job is to identify failure modes, missing validations, missing logs, missing alerts, and checks that could move into the fast post-collection QC script.

Do not edit code.
Do not turn the fast QC script into a second full pipeline.

Classify checks as:
- raw-file QC;
- parsed-data QC;
- in-pipeline validation;
- final audit;
- downstream metric gate.

Write findings to the assigned audit file.
Stop after writing.
```

## 15.7 Anti-overengineering reviewer prompt

```text
You are the Anti-Overengineering Reviewer.

Your job is to challenge every proposed change.

For each recommendation, ask:
- Is the problem real?
- Is there evidence?
- Is code change necessary?
- Would documentation/tests/logging be enough?
- Does this add complexity?
- Does this risk changing scientific outputs?
- Is there a smaller fix?
- Should it be deferred?

You must also identify things that should remain unchanged.

Write:
- rejected recommendations;
- keep-as-is recommendations;
- minimal alternatives;
- final decision matrix updates.

Stop after writing.
```

## 15.8 Final skeleton architect prompt

```text
You are the Final Skeleton Architect.

Read:
- all audit outputs;
- anti-overengineering review;
- rewrite decision gate;
- user-approved strategy.

Do not edit code.
Do not invent new features.
Do not include legacy metrics unless explicitly approved.

Build audit_outputs/11_final_target_skeleton.md.
Every stage in the skeleton must trace to audit evidence.
Every removed or changed stage must have justification.
Every retained complex component must be explicitly marked as retained and why.
Stop after writing the skeleton.
```

## 15.9 Implementation prompt

```text
You are the Implementation Agent.

Assigned ticket: <ticket id>

Read:
- GAGA_PIPELINE_AGENT_WORK_PLAN.md
- audit_outputs/11_final_target_skeleton.md
- audit_outputs/12_implementation_backlog.md
- audit evidence referenced by the ticket
- tests/regression plan relevant to this ticket

Implement only this ticket.
Do not combine with other tickets.
Do not reformat unrelated files.
Do not change scientific behavior unless the ticket explicitly says so.

Before editing, write the Implementation Pre-Check.
After editing, run the required tests/regressions.
Write the implementation log.
Then stop.
```

---

# 16. Required file templates

## 16.1 Audit index template

```markdown
# Audit Index

| Phase | Output file | Status | Date | Agent | Notes |
|---|---|---|---|---|---|
```

## 16.2 Handoff template

```markdown
# Current Handoff

## Last completed phase

## Output files produced

## Key findings

## Open questions

## User decisions needed

## Recommended next phase

## Exact prompt for next agent
```

## 16.3 Decision matrix template

```markdown
# Keep / Change / Remove Decision Matrix

| ID | Component | Current location | Decision | Evidence | Proposed action | Risk | Validation required | Priority |
|---|---|---|---|---|---|---|---|---|
```

## 16.4 Architecture decision record template

```markdown
# ADR: <Title>

## Status
Proposed / Accepted / Rejected / Deferred

## Context

## Decision

## Alternatives considered

## Why not overengineered

## Consequences

## Required validation
```

## 16.5 Fast QC check catalog template

```markdown
# Fast QC Check Catalog

| Check ID | Check name | Tier | Input | Severity | Threshold | PASS | WARN | FAIL | Output field | Pipeline risk addressed |
|---|---|---|---|---|---|---|---|---|---|---|
```

---

# 17. Special technical focus areas

These areas require special attention during audits.

## 17.1 Artifact semantics

The pipeline appears to detect, mask, repair, and flag artifacts at multiple stages. The audit must determine:

- where artifacts are detected;
- whether detections are duplicated;
- whether flags represent original corruption, repaired frames, or final anomalies;
- whether repaired frames remain flagged;
- whether downstream metrics interpret flags correctly;
- whether a data modification ledger exists.

## 17.2 Interpolation, repair, smoothing, and filtering load

The pipeline may include multiple layers of interpolation and smoothing:

- gap filling;
- quaternion interpolation;
- resampling;
- artifact replacement;
- Hampel filtering;
- Butterworth filtering;
- Savitzky-Golay smoothing/derivatives;
- surgical repair.

The audit must answer:

- how much final data is measured vs reconstructed;
- whether every modification is logged;
- whether thresholds are justified;
- whether true movement could be oversmoothed;
- whether downstream models need masks indicating reconstructed data.

## 17.3 Reference detection

Reference/T-pose detection is a high-risk stage.

Audit:

- detection logic;
- fallback behavior;
- reference quality metrics;
- visualization/reporting;
- downstream impact of bad reference;
- how reference failure should appear in QC and master parquet.

## 17.4 Units and coordinate conventions

Audit end-to-end units:

- raw OptiTrack units;
- internal processing units;
- final parquet units;
- thresholds matched to units;
- CoM units;
- velocity/acceleration units;
- rotation units.

A mm/m mismatch is a critical failure.

## 17.5 Quaternion and rotation geometry

Do not simplify quaternion processing without expert justification.

Audit:

- normalization;
- shortest path;
- temporal continuity;
- SLERP;
- Markley mean;
- quaternion log angular velocity;
- rotation vector features;
- Euler sequences.

Complexity here may be scientifically necessary.

## 17.6 Master parquet as canonical ML dataset

Master parquet must not be filled with every experimental metric. It should contain stable canonical kinematic representations, masks, flags, metadata, and provenance.

Downstream model-specific transforms should usually remain downstream.

## 17.7 Legacy/current separation

Do not mix legacy 3+3+1 analytical dashboard code with the streamlined methodology unless explicitly approved.

Legacy code may be useful for:

- risk register;
- rationale;
- cautionary tests;
- historical context.

It should not automatically drive current architecture.

---

# 18. When to open a new chat or new agent

Open a new chat / agent when:

- moving from one phase to another major phase;
- switching role, e.g. from scientific reviewer to architecture reviewer;
- auditing a complex stage such as filtering or Step 06 kinematics;
- context exceeds what can be summarized cleanly;
- the current agent starts proposing implementation during audit;
- the agent appears biased toward changing everything;
- the agent is losing track of source-of-truth hierarchy;
- a fresh adversarial review is needed.

Every new chat should start with:

1. this plan;
2. `audit_outputs/audit_index.md`;
3. `audit_outputs/HANDOFF_CURRENT.md`;
4. the specific audit files needed;
5. one prompt from Section 15.

Do not paste the entire conversation history. Use the audit files as the memory system.

---

# 19. Implementation philosophy if rewrite is chosen

If the audit supports a rewrite, do not write the whole pipeline in one pass.

A rewrite must proceed stage by stage:

1. Build new parser.
2. Compare to old parser output.
3. Build QC checks.
4. Compare raw/parsed diagnostics.
5. Build gap policy.
6. Compare gap summaries.
7. Build resampling.
8. Compare time grid and values.
9. Build filtering.
10. Compare spectra, cutoffs, trajectories, artifact counts.
11. Build reference detection.
12. Compare reference windows and reference quaternions.
13. Build kinematics.
14. Compare schema, units, feature distributions, artifact flags.
15. Build master parquet validation.
16. Run downstream methods.
17. Batch test.

Do not delete the old pipeline until the new one has passed stage-level regression and downstream compatibility checks.

The old pipeline is the comparison oracle until proven otherwise.

---

# 20. Final success criteria

The process is successful only if, at the end, the project has:

1. A clear source-of-truth hierarchy.
2. A complete current pipeline map.
3. Stage-by-stage audit files.
4. A cross-stage integration audit.
5. A master parquet ML/DL readiness audit.
6. A downstream methodology compatibility audit.
7. Fast post-collection QC requirements.
8. A test and regression plan.
9. An anti-overengineering review.
10. A keep/change/remove decision matrix.
11. A final target skeleton.
12. A prioritized implementation backlog.
13. Implementation logs for every code change.
14. Regression evidence for every behavior-changing change.
15. A final thesis-grade release checklist.

The pipeline itself should be:

- modular;
- reproducible;
- configurable;
- scientifically justified;
- not over-engineered;
- observable through logs and reports;
- safe for batch processing;
- compatible with downstream thesis metrics;
- capable of producing ML/DL-ready master parquets;
- defensible in a thesis or publication review.

---

# 21. Final reminder to agents

Your job is not to be impressive.

Your job is to be accurate, skeptical, disciplined, and useful.

Do not change code just because you can.

Do not remove complexity just because it looks complex.

Do not preserve complexity just because it already exists.

Do not add features because they are interesting.

Do not mix legacy methodology with current methodology.

Do not proceed without writing the required audit file.

Do not continue after a stop condition.

When in doubt, stop, document the uncertainty, and ask the user for a decision.
