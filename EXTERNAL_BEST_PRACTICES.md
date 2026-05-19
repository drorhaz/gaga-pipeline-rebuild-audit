# External Reference & Best-Practice Benchmarking Guidelines

**Context:** Several biomechanics, motion-capture, human-movement, and dataset-publication repositories have been downloaded into the local workspace as ZIP archives or folders.

**Purpose:** These repositories are external references for improving `03_target_skeleton_draft.md` and for sharpening the pipeline audit criteria before the deep-dive Phase 4 audits.

**Mandate:** Extract useful *logic*, *audit questions*, *design patterns*, and *QC/provenance ideas* for cleaning, artifact handling, gap filling, filtering, feature extraction, validation, logging, batch processing, and dataset contracts.

**Critical boundary:** We are **not** replacing the core `pandas` / `parquet` architecture. We are **not** turning the project into a general-purpose biomechanics toolbox. External repositories are references for comparison and audit questions, not authorities for automatic replacement.

This document defines **Phase 4.5: External Reference Alignment**.

---

## 0. Phase 4.5 operating rules

### Mode

Read-only external reference inspection.

### Required output

Write exactly one report:

```text
audit_outputs/04.5_external_standards_alignment.md
```

Do **not** edit project code.  
Do **not** edit external repositories.  
Do **not** edit `03_target_skeleton_draft.md` directly.  
Only propose candidate updates inside the Phase 4.5 report.

### Local availability rule

Only perform local code inspection on repositories that are actually present in the workspace.

If a repository is listed in this document but is not present locally:

1. Mark it as `NOT_FOUND_LOCAL` in the repository inventory.
2. Do not spend time searching the filesystem repeatedly.
3. Do not infer implementation details.
4. If the reference is listed under **Remote / not uploaded references**, use only the summary guidance in this document unless the agent has explicit web access and the user approves browsing.

### Why this phase exists

Before deep-dive audits of the current Gaga Motion Analysis Pipeline, we want to understand how mature external projects handle related concerns:

- missing data;
- temporary interpolation versus true gap filling;
- artifact detection and masking;
- filtering and smoothing;
- time-series representation;
- biomechanical naming and coordinate conventions;
- quaternion / rotation sanity checks;
- acquisition-side QC;
- batch processing;
- reproducible evaluation;
- dataset publication contracts;
- metadata and provenance.

### What counts as a useful finding

A useful finding must become one of the following:

- an audit question for our current pipeline;
- a candidate metric or log field;
- a candidate QC check;
- a candidate design pattern;
- a candidate pseudocode flow;
- a candidate benchmark or synthetic test;
- an explicit `do not adopt` warning;
- a future-work-only note.

### Applicability labels

Every candidate lesson must be labeled as one of:

- `directly_relevant`
- `relevant_with_adaptation`
- `inspiration_only`
- `not_applicable`

### Adoption status labels

Every proposed idea must also be labeled as one of:

- `candidate_for_skeleton_update`
- `audit_question_only`
- `candidate_for_test_or_benchmark`
- `candidate_for_logging_or_provenance`
- `future_work_only`
- `reject_do_not_adopt`

### No fabrication rule

If a claimed pattern is not found in the inspected local repository, write:

```text
not found in inspected files
```

Do not infer or fabricate implementation details.

### Code-copying rule

Do not copy substantial external code.

Prefer logical flow, pseudocode, audit questions, or design translation into our own architecture.

Short illustrative snippets are allowed only when necessary and must include:

- local file path;
- function or class name;
- why the snippet matters;
- whether the logic is being proposed as pseudocode, not copied implementation.

---

## 1. How to locate the downloaded repositories

The folder names may vary depending on how the repositories were cloned or downloaded. First build a repository inventory.

Suggested commands:

```bash
# List nearby directories
ls
find . -maxdepth 3 -type d | sort

# Locate git repositories if the downloads include .git folders
find . -type d -name .git -prune -print

# Show local repo path + remote origin when .git exists
for g in $(find . -type d -name .git -prune); do
  repo=$(dirname "$g")
  echo "--- $repo"
  git -C "$repo" remote -v | head -n 2 || true
  git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null || true
  git -C "$repo" rev-parse --short HEAD 2>/dev/null || true
done
```

For each repository, record:

| Field | Required |
|---|---|
| Expected GitHub name | yes |
| Local path found | yes |
| Remote URL | if available |
| Branch | if available |
| Commit hash | if available |
| Files inspected | yes |
| Relevant modules/functions found | yes |
| Missing / not found notes | yes |

### Expected uploaded local folders

The currently uploaded local ZIP/folder set is expected to include:

| Priority | Expected GitHub repository | Expected local folder name |
|---:|---|---|
| 1 | `kineticstoolkit/kineticstoolkit` | `kineticstoolkit-master` |
| 2 | `perfanalytics/pose2sim` | `pose2sim-main` |
| 3 | `FIL-OPMEG/optitrack` | `optitrack-main` |
| 4 | `Immersive-AI-Systems/optitrack_motive` | `optitrack_motive-main` |
| 5 | `pyomeca/pyomeca` | `pyomeca-master` |
| 6 | `thomas-haslwanter/scikit-kinematics` | `scikit-kinematics-master` |
| 7 | `pyomeca/ezc3d` | `ezc3d-dev` |
| 8 | `samhybois/opensim_pyprocessing` | `opensim_pyprocessing-main` |
| 9 | `vaila-multimodaltoolbox/vaila` | `vaila-main` |

### Explicitly not uploaded because of size

The following repositories were intentionally not uploaded at this stage:

| Expected GitHub repository | Expected local folder if later added | Criticality now | How to treat in Phase 4.5 |
|---|---|---|---|
| `mad-lab-fau/gaitmap` | `gaitmap` / `gaitmap-main` | Not critical for current pipeline audit | Optional remote/documentation reference for evaluation architecture only |
| `drivelineresearch/openbiomechanics` | `openbiomechanics-main` | Useful for final dataset publication packaging, but not required for local code audit | Optional remote/documentation reference for dataset contracts only |

Do **not** block Phase 4.5 because these two are absent.

---

# 2. MUST STUDY DEEPLY — active local references

These repositories are the highest priority for Phase 4.5. They are the most relevant to the Gaga pipeline's immediate concerns: cleaning, filtering, missingness, OptiTrack QC, stage design, configuration, and raw/acquisition validation.

---

## A. `kineticstoolkit/kineticstoolkit`

**Expected local folder:** `kineticstoolkit-master`  
**Reference type:** biomechanics time-series toolkit, filtering, missing-data behavior, marker/geometry utilities.

### Inspect these files first

- `kineticstoolkit/filters.py`
- `kineticstoolkit/timeseries.py`
- `kineticstoolkit/kinematics.py`
- `kineticstoolkit/geometry.py`
- relevant tests under `tests/`
- relevant docs under `docs/`

### Focus

Study Kinetics Toolkit for:

- time-series API concepts;
- time and event management;
- filtering modules;
- missing sample handling;
- marker reconstruction / geometry utilities;
- documentation style for processing behavior.

### Extraction targets

Inspect the filtering implementation and documentation-relevant code. Specifically look for logic that prevents **NaN bleeding** during filtering:

1. detect missing samples;
2. warn the user or record the condition;
3. temporarily fill missing samples only to enable filtering;
4. apply the filter;
5. restore original NaN locations after filtering;
6. avoid silently treating temporary interpolation as measured or truly repaired data.

### Important correction

Do **not** describe Kinetics Toolkit's behavior as our target bounded gap-filling policy.

The relevant lesson is:

```text
missing samples during filtering
→ warn / detect
→ temporary interpolation for filter stability only
→ filtering
→ restore original NaN positions
```

This is different from:

```text
true gap filling / data repair
```

Our pipeline must keep those two concepts separate.

### Questions to answer

- Do they temporarily fill missing values only for filtering stability?
- Do they restore NaNs after filtering?
- Do they warn or log when missing data is present?
- Do they distinguish temporary filter interpolation from true data repair?
- Can this inform our own filtering, NaN-safe SavGol, Butterworth, and provenance design?

### Candidate updates to consider for our pipeline

- Add a standard log distinction between:
  - `temporary_filter_interpolation`
  - `true_gap_fill`
  - `surgical_repair`
  - `resampling_interpolation`
- Add per-stage fields:
  - `temporary_filter_interpolation_used`
  - `nan_restored_after_filtering`
  - `n_original_nan_frames`
  - `n_nan_frames_restored_after_filtering`
- Add tests ensuring filtering never converts original missing data into apparently valid measured data unless explicitly intended.

### Do NOT adopt

- Do not migrate to their TimeSeries data structure.
- Do not replace our `pandas` / `parquet` architecture.
- Do not treat KTK's temporary filter interpolation as evidence that long gaps should be filled.
- Do not introduce a general biomechanics toolbox abstraction unless strongly justified later.

---

## B. `perfanalytics/pose2sim`

**Expected local folder:** `pose2sim-main`  
**Reference type:** multi-stage movement pipeline, configuration management, filter options, batch workflow.

### Inspect these files first

- `Pose2Sim/Demo_Batch/Config.toml`
- `Pose2Sim/Demo_Batch/Trial_1/Config.toml`
- `Pose2Sim/Demo_Batch/Trial_2/Config.toml`
- `Pose2Sim/Demo_SinglePerson/Config.toml`
- `Pose2Sim/Demo_MultiPerson/Config.toml`
- `Pose2Sim/filtering.py`
- orchestration modules under `Pose2Sim/`
- relevant docs / README files

### Focus

Study Pose2Sim for:

- pipeline stage organization;
- configuration management;
- global versus trial-level configuration;
- how multiple algorithms are exposed without making them uncontrolled defaults;
- batch execution patterns;
- stage-specific reporting;
- filtering option organization.

### Extraction targets

Specifically answer:

- How are parameters grouped?
- How are defaults documented?
- Are experimental options separated from primary/default behavior?
- How are global and per-trial settings handled?
- How do they expose filter options such as Butterworth, Gaussian, LOESS, Median, Kalman, etc.?
- Do they generate stage-specific plots or recap outputs that could inspire our QC reports?

### Important warning: `zero == missing`

Some Pose2Sim / markerless pipelines may treat zeros as missing values in filtering paths.

This convention must **not** be adopted for our OptiTrack/root-relative/zeroed data unless explicitly verified.

In our pipeline, zero can be a valid measured or derived value, for example:

- root-relative positions;
- zeroed rotations;
- velocities at rest;
- root-centered features;
- T-pose-normalized quantities.

### Candidate updates to consider for our pipeline

- Clearer separation between primary defaults and experimental/sensitivity options.
- Stage-specific config blocks with stable names.
- A config snapshot written with every stage output.
- A per-run config diff or parameter override report.
- A `default_off_experimental_method` convention for non-primary filters.
- A “do not change defaults silently” policy for batch runs.

### Do NOT adopt

- Do not adopt markerless assumptions.
- Do not adopt `zero == missing` logic without explicit project-specific validation.
- Do not import OpenSim dependencies into the current scope.
- Do not add many filter options unless each option has a clear reason, tests, and a default-off policy.
- Do not turn the Gaga pipeline into a general movement-processing platform.

---

## C. `FIL-OPMEG/optitrack`

**Expected local folder:** `optitrack-main`  
**Reference type:** OptiTrack-specific scripts, SOPs, quick QC, plotting, unit conversion, synchronization.

### Inspect these files first

- `README.md`
- `csv2mat_sm.m`
- `filterOptitrackData.m`
- `getRigidBodyVelocity.m`
- `plot_motive_rotation.m`
- `plot_motive_translation.m`
- `processRigidBodyT.m`
- `optitrack_convert_units.m`
- `resampleOptiTrack.m`
- `readRigidBody.m`
- `make_pos_hist.m`
- `zero_optitrack_data.m`
- `media/` examples if useful

### Focus

Study this repository for OptiTrack-specific QC and post-collection sanity checks.

### Extraction targets

Inspect scripts related to:

- loading OptiTrack data;
- quaternion / Euler rotation handling;
- unit conversion;
- translation and rotation plotting;
- velocity checks;
- marker quality estimates;
- synchronization / resampling;
- fast visual QC.

### Candidate updates to consider for our pipeline

Enhance the planned post-collection QC script with:

- quick translation plots;
- quick rotation plots;
- velocity sanity checks;
- unit sanity checks;
- marker / rigid-body quality summaries;
- basic histograms of displacement or velocity;
- “recording looks usable?” PASS / WARNING / FAIL summary.

### Do NOT adopt

- Do not use this as a full architecture model.
- Do not port MATLAB code directly.
- Do not copy synchronization assumptions unless they match our acquisition setup.
- Do not treat this repository as thesis-grade pipeline validation by itself.

---

## D. `Immersive-AI-Systems/optitrack_motive`

**Expected local folder:** `optitrack_motive-main`  
**Reference type:** OptiTrack NatNet streaming, acquisition diagnostics, dropped-frame detection, rigid body / marker availability.

### Inspect these files first

- `diagnostics/detect_frame_drops.py`
- `examples/print_rigid_body.py`
- `examples/print_markers.py`
- `examples/check_camera_status.py`
- `examples/check_recording_status.py`
- `optitrack_motive/rigid_body.py`
- `optitrack_motive/motive_receiver.py`
- `optitrack_motive/motive_stream.py`
- `tests/` related to stream or receiver behavior

### Focus

Study this repository for acquisition-side QC and possible future live/post-collection validation ideas.

### Extraction targets

Look for:

- dropped frame detection;
- frame number continuity;
- rigid body availability;
- marker availability;
- camera/recording status checks;
- basic acquisition status reporting;
- streaming packet consistency checks.

### Candidate updates to consider for our pipeline

Add raw/acquisition QC fields such as:

- `frame_number_continuity_status`
- `n_dropped_frames_detected`
- `max_frame_number_gap`
- `rigid_body_availability_fraction`
- `marker_availability_fraction`
- `recording_status_detected`
- `streaming_qc_available`

### Do NOT adopt

- Do not add NatNet as a dependency of the offline pipeline.
- Do not redesign the project as a real-time streaming system.
- Do not use this repository for core kinematic feature computation.
- Do not let acquisition-side streaming concerns expand the current thesis scope.

---

# 3. TARGETED LIMITED REVIEW — inspect only selected files

These repositories should be inspected only for specific lessons. Do not deep-dive the full projects.

---

## E. `pyomeca/pyomeca`

**Expected local folder:** `pyomeca-master`  
**Reference type:** clean biomechanics API, coordinate-frame clarity, rotations, biomechanical naming conventions.

### Inspect these files first

- `pyomeca/processing/filter.py`
- `pyomeca/processing/interp.py`
- `pyomeca/processing/angles.py`
- `pyomeca/processing/rototrans.py`
- relevant docs / examples / tests

### Focus

Study API clarity and biomechanical naming, not cleaning architecture.

### Extraction targets

Inspect:

- naming conventions;
- axes / coordinate system functions;
- rototranslation matrix logic;
- Euler / rotation utilities;
- documentation patterns;
- how processing functions are separated from IO.

### Candidate updates to consider for our pipeline

- Improve naming consistency for coordinate frames and axes.
- Add clearer documentation of:
  - OptiTrack frame;
  - root-relative frame;
  - global frame;
  - child/body-local frame;
  - quaternion convention;
  - Euler convention;
  - model-ready feature groups.
- Add schema documentation inspired by labeled dimensions, without changing our parquet layout.

### Do NOT adopt

- Do not inspect Pyomeca for advanced artifact or cleaning logic.
- Do not migrate to xarray or Pyomeca data structures unless a later audit gives strong justification.
- Do not generalize the pipeline into a broad biomechanics API.

---

## F. `thomas-haslwanter/scikit-kinematics`

**Expected local folder:** `scikit-kinematics-master`  
**Reference type:** 3D kinematics, quaternions, rotations, IMU orientation algorithms.

### Inspect these files first

- `skinematics/quat.py`
- `skinematics/rotmat.py`
- `skinematics/imus.py`
- relevant tests under `tests/`

### Focus

Study rotation and quaternion sanity checks only.

### Critical convention warning

Treat scikit-kinematics as a **convention-risk reference**.

Do not copy quaternion code.

Before extracting any lesson, explicitly compare:

- scalar-first versus scalar-last conventions;
- left-multiplication versus right-multiplication assumptions;
- frame convention assumptions;
- angle unit assumptions.

Our pipeline uses SciPy `xyzw` scalar-last quaternion convention.

### Candidate updates to consider for our pipeline

- Add stronger quaternion norm checks.
- Add continuity checks before and after SLERP / median filtering / SavGol smoothing.
- Add explicit convention tests for `xyzw` scalar-last ordering.
- Add documentation stating that quaternion logic must not mix conventions.

### Do NOT adopt

- Do not import IMU/AHRS assumptions.
- Do not add Madgwick/Mahony/Kalman orientation filters to OptiTrack quaternion data unless future work explicitly requires it.
- Do not copy quaternion code without convention translation.

---

## G. `pyomeca/ezc3d`

**Expected local folder:** `ezc3d-dev`  
**Reference type:** C3D file format discipline, metadata, IO separation, tests.

### Inspect these files first

- `README.md`
- `examples/`
- `test/`
- Python binding examples under `binding/`
- docs under `doc/`

### Focus

Study file-format boundaries and metadata handling.

### Extraction targets

Inspect:

- read/write API examples;
- test files;
- metadata conventions;
- error messages;
- separation between file-format logic and analysis logic.

### Candidate updates to consider for our pipeline

- Future C3D interoperability notes.
- Stronger separation between raw file parsing and analytical computation.
- Better input-format validation and error messages.
- A clearer boundary between `raw format parser` and `canonical internal representation`.

### Do NOT adopt

- Do not rebuild the current pipeline around C3D.
- Do not add C3D export/import unless required by a concrete future use case.
- Do not treat IO discipline as a reason to expand scope.

---

## H. `samhybois/opensim_pyprocessing`

**Expected local folder:** `opensim_pyprocessing-main`  
**Reference type:** OpenSim Python batch pipeline, typed config, stage toggles, logging, C3D/OpenSim processing.

### Inspect these files first

- `opensim_pipeline/pipeline.py`
- `opensim_pipeline/config.py`
- `run_pipeline.py`
- `config.yaml`

### Focus

Use as an architecture reference for stage orchestration and typed config only.

### Extraction targets

Inspect:

- typed configuration patterns;
- YAML loading;
- step toggles;
- stage-level logging;
- output folder conventions;
- how pipeline steps are separated.

### Candidate updates to consider for our pipeline

- Stronger stage contracts.
- Cleaner config validation.
- Better stage toggles for optional / experimental behavior.
- More structured logging around each pipeline step.

### Do NOT adopt

- Do not convert the current pipeline to OpenSim.
- Do not add IK/ID/scaling unless a concrete scientific requirement appears later.
- Do not adopt C3D-to-TRC/MOT assumptions as core.
- Do not add physics-engine complexity.

---

## I. `vaila-multimodaltoolbox/vaila`

**Expected local folder:** `vaila-main`  
**Reference type:** multimodal human movement toolbox, batch processing, dataset readiness patterns, filter utilities.

### Inspect only these files if present

- `vaila/filter_utils.py`
- `vaila/fifa_dataset_train_readiness.py`
- selected tests related to dataset validation, if easy to locate
- do not inspect the full repository unless explicitly instructed

### Focus

Use this repository only for:

- batch usability ideas;
- dataset readiness checker patterns;
- simple filter utility structure;
- consistency-check mindset.

### Candidate updates to consider for our pipeline

- Add a master-parquet readiness checker.
- Add batch-level summaries.
- Add simple structured checklist outputs for many sessions.
- Consider whether any filter utility patterns are worth converting into tests, not direct code.

### Do NOT adopt

- Do not inspect the full repository.
- Do not add GUI complexity.
- Do not turn the project into a multimodal toolbox.
- Do not add modalities outside current scope.
- Do not treat Vailá as a core architecture reference.

---

# 4. Remote / not uploaded references — do not inspect locally unless added

The following references were not uploaded because of size or scope. They are useful conceptually but should not block Phase 4.5.

If the agent has no web access, simply include them in the report as `NOT_FOUND_LOCAL` with the summary below. Do not fabricate file-level findings.

---

## J. `mad-lab-fau/gaitmap` — not uploaded

**Expected local folder if later added:** `gaitmap` / `gaitmap-main`  
**Criticality now:** Not critical for the current Gaga/OptiTrack preprocessing audit.  
**Best use:** Optional reference for reproducible evaluation architecture and benchmark design.

### Why it is useful

`gaitmap` is an IMU/gait-analysis ecosystem, not an OptiTrack or free-dance pipeline. Its value for us is not the gait algorithms. Its value is the separation between:

- datasets;
- algorithms;
- evaluations;
- benchmarks;
- reference implementations;
- repeatable tests.

### Use it for

- designing benchmark interfaces for gap filling and filtering variants;
- separating dataset loading from algorithm execution;
- thinking about reproducible evaluation;
- designing synthetic/known-output test suites.

### Do NOT use it for

- gait event detection;
- stride segmentation;
- foot-worn IMU assumptions;
- reframing Gaga movement as gait.

### Upload needed?

Not needed for the current Phase 4.5 unless you want file-level code inspection of its benchmark/evaluation implementation.

If not uploaded, mark as:

```text
NOT_FOUND_LOCAL; optional evaluation-architecture reference only.
```

---

## K. `drivelineresearch/openbiomechanics` — not uploaded

**Expected local folder if later added:** `openbiomechanics-main`  
**Criticality now:** Not required for code-level Phase 4.5, but useful for final thesis/publication dataset packaging.  
**Best use:** Dataset contract, public biomechanics dataset organization, raw/cleaned/processed separation, documentation conventions.

### Why it is useful

OpenBiomechanics is a publication-oriented public biomechanics dataset project. Its value for us is not algorithmic cleaning logic. Its value is the way it exposes:

- raw/cleaned C3D files;
- processed full-signal data;
- point-of-interest metrics;
- documentation of metric definitions;
- variable and file naming conventions;
- processing steps;
- public dataset packaging.

### Use it for

- strengthening `kinematics_master.parquet` as a canonical continuous-sequence dataset;
- designing dataset cards / schema documentation;
- separating raw, cleaned, processed, metrics, QC, and export layers;
- improving naming and documentation for thesis/publication review;
- thinking about external-reader usability.

### Do NOT use it for

- sport-specific baseball metrics;
- point-of-interest-only output;
- replacing continuous sequence data;
- changing our pipeline architecture.

### Upload needed?

Not needed for the current Phase 4.5 unless you want local inspection of its exact folder structure, documentation files, and examples.

For the current plan, the agent can include it as:

```text
NOT_FOUND_LOCAL; optional dataset-contract/publication reference only.
```

---

# 5. Optional references not currently enabled

Do not inspect the following unless they are downloaded and explicitly enabled by the user:

| Expected GitHub repository | Reason to keep optional |
|---|---|
| `mkjung99/gapfill` | useful for gap-filling alternatives, but not uploaded |
| `mgb45/MoGapFill` | useful for Kalman/subspace gap filling benchmarks, but not uploaded and likely overkill now |
| `neurogeriatricskiel/pymocap` | useful for optical mocap preprocessing framing, but not uploaded |
| `markkorput/PyMoCap` | optional motion-capture toolkit reference, not uploaded |
| `Biomechanical-ToolKit/BTKCore` / `BTKPython` / `Mokka` | historical C3D/biomechanics ecosystem, not needed now |
| `keenon/nimblephysics` | future physics-informed validation only, too large/scope-expanding now |
| `mitkof6/opensim_automated_pipeline` | optional OpenSim pipeline reference only |
| `modenaxe/awesome-biomechanics` | index only; do not expand scope during Phase 4.5 |

If any of these are absent, mark `NOT_FOUND_LOCAL` and move on.

---

# 6. Required report structure

The agent must write:

```text
audit_outputs/04.5_external_standards_alignment.md
```

Use this structure:

```md
# 04.5 External Standards Alignment

## 1. Executive summary

## 2. Repository inventory

| Expected GitHub repo | Local path | Remote URL | Branch | Commit | Status |
|---|---|---|---|---|---|

## 3. Per-repository findings

### Repository: owner/name

#### Local inspection

- Local path:
- Remote URL:
- Branch:
- Commit:
- Files inspected:
- Functions/modules inspected:

#### Relevant logic found

#### Candidate lessons for Gaga pipeline

#### Applicability labels

#### What not to adopt

#### Concrete audit questions created

## 4. Cross-repository lessons

## 5. Candidate updates to `03_target_skeleton_draft.md`

| Source repo | Local file/function | Lesson | Applicability | Proposed adaptation | Adoption status | Risk | Do not adopt |
|---|---|---|---|---|---|---|---|

## 6. Candidate QC/logging/provenance fields

| Field | Stage | Why needed | Source inspiration | Required? |
|---|---|---|---|---|

## 7. Candidate over-processing / redundancy metrics

| Metric | Stage | What it detects | Source inspiration | Implementation priority |
|---|---|---|---|---|

## 8. Candidate tests and benchmarks

| Test/benchmark | Target stage | Synthetic or real data | Expected outcome | Source inspiration |
|---|---|---|---|---|

## 9. External logic explicitly rejected

| Source repo | Rejected idea | Why rejected |
|---|---|---|

## 10. Not uploaded references

| Reference | Criticality | Should upload later? | Current treatment |
|---|---|---|---|

## 11. New audit questions for Phase 4

## 12. Risks of over-adopting external patterns

## 13. Final recommendation
```

---

# 7. Specific alignment questions the agent must answer

The Phase 4.5 report must explicitly answer:

1. **NaN-safe filtering:**  
   What external logic should influence our handling of missing samples during filtering?

2. **Temporary interpolation versus true repair:**  
   Which external projects separate temporary technical interpolation from true data repair, and how should we log that distinction?

3. **Gap-filling audit:**  
   What external logic suggests better metrics or benchmarks for assessing our bounded spline / PCHIP / SLERP choices?

4. **Artifact semantics:**  
   Do external projects distinguish raw artifacts, missing data, temporary interpolation, true repair, and final exclusion masks more clearly than we do?

5. **Configuration discipline:**  
   How should our config distinguish stable defaults, sensitivity options, experimental options, and deprecated options?

6. **QC script design:**  
   What should be included in the fast post-collection QC script based on OptiTrack and biomechanics references?

7. **Dataset contract:**  
   What should `kinematics_master.parquet` expose so it is understandable as a canonical continuous sequence dataset for ML/DL and thesis-grade analysis?

8. **Provenance:**  
   What input/output/config/code/parameter hashes or metadata should be logged per stage?

9. **Benchmarking:**  
   What synthetic or real-data tests should be added to compare preprocessing variants without changing scientific conclusions prematurely?

10. **Overengineering risk:**  
    Which external ideas are interesting but should be rejected or deferred to future work?

11. **Not uploaded references:**  
    Do `gaitmap` or `openbiomechanics-main` need to be uploaded before continuing? If not, state why not. If yes, state exactly what additional local inspection would enable.

---

# 8. Strict guardrails for the AI agent

1. **Read-only mode.**  
   Do not edit project code, external code, configs, notebooks, or `03_target_skeleton_draft.md`.

2. **No code replacement.**  
   External repositories are references for comparison and audit questions, not authorities for automatic replacement.

3. **Maintain scope.**  
   Keep the project focused on Gaga / OptiTrack data preparation, `kinematics_master.parquet`, QC, ML/DL readiness, and thesis-grade reproducibility.

4. **Preserve architecture boundary.**  
   Do not propose migrating away from `pandas` / `parquet` unless a later architecture phase explicitly asks for alternatives.

5. **Do not generalize unnecessarily.**  
   Do not turn the project into a general biomechanics toolbox.

6. **Do not import assumptions blindly.**  
   Markerless, gait-specific, OpenSim, IMU, GUI, and physics-engine assumptions must be rejected or marked `future_work_only` unless directly justified.

7. **No broad dependency expansion.**  
   Do not recommend new dependencies unless they solve a concrete, evidenced problem.

8. **No hidden adoption.**  
   Every proposed idea must state what is adopted, what is adapted, and what is rejected.

9. **No fabrication.**  
   If a pattern is not found locally, say so.

10. **No direct skeleton edits.**  
    Propose candidate updates to `03_target_skeleton_draft.md`, but do not edit it.

11. **Do not block on missing optional repositories.**  
    `gaitmap` and `openbiomechanics-main` are useful optional references, but they are not required to complete Phase 4.5.

12. **Stop condition.**  
    Stop immediately after writing:

```text
audit_outputs/04.5_external_standards_alignment.md
```

---

# 9. Recommended Phase 4.5 prompt

Use this prompt with Claude Code / Cursor:

```text
Phase 4 is pending. Before the deep-dive audits, we are inserting Phase 4.5: External Reference Alignment.

Read:

docs/EXTERNAL_BEST_PRACTICES.md

Only inspect the external repositories that are actually present in the local workspace.

Priority order:

1. kineticstoolkit-master
2. pose2sim-main
3. optitrack-main
4. optitrack_motive-main
5. pyomeca-master
6. scikit-kinematics-master
7. ezc3d-dev
8. opensim_pyprocessing-main
9. vaila-main only if time remains, and only selected files

Do not inspect absent optional repositories.

Important: gaitmap and openbiomechanics-main were not uploaded because of size. They are optional remote/documentation references only. Do not block Phase 4.5 because they are absent.

For each inspected repository:

- record local path;
- inspect only the files listed in the directive;
- extract logical patterns, not code;
- identify what is relevant to our pipeline;
- identify what must not be adopted;
- propose audit questions or candidate skeleton updates.

Important corrections:

- In Kinetics Toolkit, distinguish temporary interpolation for filtering from true gap filling.
- In Pose2Sim, do not adopt `zero == missing` logic unless explicitly verified.
- In scikit-kinematics, beware quaternion convention differences.
- In Vailá, inspect only selected dataset-readiness / filter utility files.
- In OpenSim references, inspect only stage orchestration and typed config; do not adopt OpenSim processing assumptions.

Write:

audit_outputs/04.5_external_standards_alignment.md

Do not edit project code.
Do not edit external repositories.
Do not edit 03_target_skeleton_draft.md directly.

Stop after writing the file.
```
