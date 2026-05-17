
# Unified Session QC & Validation Plan

## For the OptiTrack Kinematic Pipeline Rebuild

## Scope Guardrail

This document is a **design reference** for Phase 9.5 and Phase 10.

It must **not** be interpreted as a direct implementation order.

Before any part of this plan is implemented, the agent must classify each proposed QC component as one of:

- already covered by Fast QC;
- already covered by the Testing and Regression Plan;
- candidate for Phase 10 decision matrix;
- Minimal v1 candidate;
- future v2;
- too heavy for now;
- rejected / do not adopt.

The default implementation target, if approved later, is **Minimal v1 only**.

The purpose of this document is to help design a unified QC and validation framework while avoiding unnecessary complexity, duplicated checks, bloated outputs, or overengineering.

---

# Document Purpose

Evaluate and align a generic and unified QC/Validation system for every movement session entering the kinematic pipeline.

The system must support the following session types:

```text
1. Fixed exercise sessions of approximately 4 minutes
2. Free-dance sessions
3. Historical sessions that have already been collected
4. Future sessions with newly added protocol components
````

The central principle is:

> Every session passes through the same QC architecture.
> Tests that depend on a specific QC anchor — such as quiet standing or cyclic movement — are applied only if that anchor actually exists.
> The absence of such an anchor does not invalidate historical sessions.

The goal is not only to extract kinematic features, but to produce:

```text
kinematic features
+ documented reliability
+ QC reasons
+ downstream-use decisions
```

In other words, every final feature must be traceable to an explicit reliability status, the source of any warning, and whether it is allowed to be used in downstream analysis.

---

# General System Structure

The QC system should be organized into three conceptual stages:

```text
Stage 1 — Raw Data QC
Determines whether the raw recording is sufficiently valid to enter the pipeline.

Stage 2 — Pipeline Processing QC
Determines whether cleaning, gap filling, filtering, and anatomical constraints preserved signal and skeleton integrity.

Stage 3 — Final Feature QC
Determines whether the final kinematic features are reliable, plausible, and suitable for scientific use.
```

In addition, the system may include summary layers:

```text
Session-Level Decision
Day / Experiment-Level Aggregation
Downstream Feature Reliability Flags
```

However, these layers should be implemented progressively.

For Phase 10 planning, the priority is:

```text
1. Session-level QC
2. Feature reliability sidecar outputs
3. Minimal downstream-use flags
4. Day-level aggregation only after session-level QC is stable
```

---

# Key Principle: A Generic System for Every Session

Do not build separate QC logic for “4-minute sessions” versus “free-dance sessions.”

Instead, every session should conceptually pass through the same entry point:

```text
run_unified_session_qc(session)
```

This function checks which sources of information are available in the session:

```text
raw data available?
processed data available?
features available?
static anchor detected?
cyclic anchor detected?
structured-task evidence available?
video available?
calibration metadata available?
gap filling log available?
filtering log available?
anatomical constraints log available?
```

Then it activates only the relevant QC modules.

A test that cannot be run because the required information does not exist should receive:

```text
NOT_AVAILABLE
```

and not:

```text
FAIL
```

This rule is essential for backward compatibility with historical recordings.

---

# Known Experiment Structure

Each experiment / recording day may include four recorded sessions:

```text
Experiment / Recording Day
├── Session 1: fixed exercise session, approximately 4 minutes
├── Session 2: free-dance session
├── Session 3: fixed exercise session, approximately 4 minutes
└── Session 4: free-dance session
```

However, the QC system should not assume the session type in advance.

Each session receives independent QC.

A day-level aggregation layer may be added later, after the session-level QC is stable.

---

# Required Inputs

For each session, the system should receive or attempt to locate:

```text
session_id
participant_id
experiment_id / day_id
session_order_within_day
recording_date
sampling_rate

raw_mocap_file
processed_mocap_file
final_kinematic_features_file

camera_calibration_metadata
ROM_calibration_metadata
pipeline_config

gap_filling_log
filtering_log
anatomical_constraints_log

video_file, if available
event_markers, if available
manual_annotations, if available
```

Not all fields are required to exist for every session.

Every missing field must be documented in the QC report or sidecar metadata.

Missing optional information should affect `qc_evidence_level`, not automatically reduce the session’s reliability score or invalidate the session.

---

# Recommended Outputs Per Session

The full conceptual output set is:

```text
session_qc_report.json
session_qc_summary.csv
joint_quality_table.csv
segment_quality_table.csv
processing_artifacts_table.csv
feature_reliability_table.csv
time_window_flags.csv
downstream_flags.csv
qc_plots/
```

However, this is too large for a first implementation.

## Recommended Minimal v1 outputs

For Minimal v1, prefer:

```text
session_qc_report.json
joint_quality_table.csv
segment_quality_table.csv
feature_reliability_table.csv
```

Optional / generated only when needed:

```text
processing_artifacts_table.csv
time_window_flags.csv
downstream_flags.csv
qc_plots/
```

Recommended output policy:

```text
PASS sessions:
  generate compact JSON + tables only

PASS_WITH_WARNINGS / FAIL sessions:
  generate expanded tables and selected plots

Golden regression sessions:
  generate full QC plots for regression comparison
```

The central file is:

```text
session_qc_report.json
```

It must answer:

```text
1. Can this session be used?
2. Which joints are reliable?
3. Which segments are reliable?
4. Which features are reliable?
5. Which features, joints, or time windows should be excluded?
6. What is the source of the issue: raw data, processing, or final feature artifact?
7. What is the QC evidence level for this session?
8. What downstream action is recommended?
```

---

# Unified Status Labels

To remain consistent with the existing Fast QC plan, top-level session statuses should be:

```text
PASS
PASS_WITH_WARNINGS
FAIL
REVIEW_REQUIRED
NOT_AVAILABLE
```

At lower levels, joint / segment / feature labels may use:

```text
RELIABLE
WARNING
LOW_CONFIDENCE
UNRELIABLE
EXCLUDE
NOT_AVAILABLE
```

Recommended status levels:

```text
session_qc_status
raw_data_qc_status
processing_qc_status
final_feature_qc_status

joint_quality_status
segment_quality_status
feature_reliability_status
time_window_quality_status
```

Avoid introducing additional status vocabularies unless Phase 10 explicitly approves them.

---

# Reliability Score and Evidence Level

Each session should receive two separate values.

## 1. session_reliability_score

A score between 0 and 1:

```text
0.85–1.00 = high reliability
0.65–0.85 = usable with warnings
<0.65 = low reliability / possible fail
```

This score reflects the quality of the data based only on QC tests that were actually available.

It should not automatically penalize a historical session for missing optional anchors.

## 2. qc_evidence_level

The strength of QC evidence:

```text
LOW
MEDIUM
HIGH
```

This is important so historical sessions without a cyclic anchor are not unfairly penalized.

Example:

```text
Session A:
  reliability_score = 0.82
  qc_evidence_level = MEDIUM
  reason = static anchor available, cyclic anchor not available

Session B:
  reliability_score = 0.86
  qc_evidence_level = HIGH
  reason = static and cyclic anchors available
```

The absence of a cyclic anchor should not automatically reduce the reliability score, but it may reduce the QC evidence level.

---

# Threshold Policy

All thresholds in this document are starting hypotheses, not final scientific constants.

Any threshold used to exclude data must be:

```text
configurable
logged
versioned
calibrated later on known-good sessions
```

Thresholds must be stored in configuration, for example:

```text
qc_thresholds.yaml
```

and not hard-coded.

Examples:

```text
missing_percent_warning
missing_percent_fail
longest_gap_warning_seconds
longest_gap_fail_seconds
segment_length_cv_warning
segment_length_cv_fail
static_noise_speed_threshold
hard_speed_bound_core
hard_speed_bound_distal
hard_acceleration_bound_core
hard_acceleration_bound_distal
gap_boundary_window_seconds
```

---

# Runtime Classification

Every QC check must be classified as one of:

```text
fast_post_collection_qc
normal_pipeline_qc
deep_diagnostic_qc
offline_batch_audit_only
```

No expensive check should run by default unless it directly protects data validity.

Recommended interpretation:

```text
fast_post_collection_qc:
  runs immediately after recording
  should be quick
  protects against re-recordable failures

normal_pipeline_qc:
  runs as part of Steps 01–06
  writes stage-level quality metadata

deep_diagnostic_qc:
  runs only when a warning/failure is detected or when debugging

offline_batch_audit_only:
  runs across many sessions after processing
  used for calibration, thesis reporting, or regression analysis
```

---

# Optional QC Anchors

The system must support optional QC anchors.

## Static Anchor

A segment in which the participant stands without meaningful movement.

It may be:

```text
explicitly marked
manually annotated
automatically detected
```

If available, it may be used to compute:

```text
static noise floor
static drift
fake movement during no-motion
baseline jitter
```

If unavailable:

```text
static_anchor_status = NOT_AVAILABLE
```

Not FAIL.

Minimal v1 recommendation:

```text
Use an existing reference/static window if already available from the pipeline.
Do not build complex automatic static-anchor detection in v1 unless already supported by existing Step 05 logic.
```

---

## Cyclic Anchor

A short cyclic movement, for example:

```text
raising both arms up and down
short bend-rise movement
side-to-side weight shift
```

This may be added to future sessions when possible.

If available, it can be used to test:

```text
dynamic tracking stability
segment consistency during movement
gap filling under motion
filter overshoot under motion
basic periodicity
left-right symmetry if relevant
```

If unavailable:

```text
cyclic_anchor_status = NOT_AVAILABLE
```

Not FAIL.

Important methodological wording:

```text
The cyclic anchor improves QC evidence strength for future sessions, but its absence in historical recordings is not treated as a failure.
```

Minimal v1 recommendation:

```text
Do not implement automatic cyclic-anchor detection in v1.
Only use cyclic-anchor QC if event markers or manual annotations are already available.
```

---

## Structured-Task Evidence

If a fixed 4-minute exercise session exists and its exercises can be identified, it may be used as an additional evidence layer.

However:

```text
structured_task_checks are optional
structured_task_checks are not required for session validity
structured_task_checks should not be hard-coded by exact timestamps
```

If these checks are activated, they should use:

```text
soft windows
event markers
manual annotations
```

rather than rigid timestamps.

Minimal v1 recommendation:

```text
Do not implement a structured-task module in v1 unless reliable annotations already exist.
```

---

# Core vs Peripheral Joints

A joint criticality map must be defined in advance.

## Core Joints

Joints whose failure may affect the entire session or whole-body features:

```text
pelvis / Hips
trunk / Spine / Spine1
Head / Neck
left hip / LeftUpLeg
right hip / RightUpLeg
left shoulder / LeftShoulder
right shoulder / RightShoulder
```

## Peripheral Joints

Joints whose failure usually does not invalidate the entire session, but affects local features:

```text
LeftArm / RightArm
LeftForeArm / RightForeArm
LeftHand / RightHand
LeftLeg / RightLeg
LeftFoot / RightFoot
hands / feet / toes, if available
```

This definition should be stored in configuration, for example:

```text
joint_metadata.yaml
```

or derived from an existing canonical skeleton configuration if one already exists.

Do not create a second conflicting joint taxonomy if an authoritative mapping already exists in the repository.

---

# Stage 1 — Raw Data QC

## Purpose

Determine whether the raw recording is eligible to enter the processing pipeline.

Central question:

```text
Can the raw recording enter the processing pipeline?
```

Stage 1 overlaps with Fast Post-Collection QC.

During Phase 9.5 / Phase 10, the agent must classify each Stage 1 check as either:

```text
already covered by Fast QC
needs to be added to Fast QC
normal pipeline QC
future-only
```

---

## Stage 1.1 — Metadata & Calibration Check

Check and document:

```text
camera_calibration_id
camera_calibration_time
camera_calibration_quality_metric
ROM_calibration_id
ROM_calibration_time
ROM_completion_status
ROM_quality_notes
capture_volume_status
calibration_to_recording_time_gap
Capture Frame Rate
Export Frame Rate
Rotation Type
Length Units
Total Frames in Take
Total Exported Frames
Coordinate Space
```

## Decisions

| Condition                                       | Decision                             |
| ----------------------------------------------- | ------------------------------------ |
| All metadata exists and is valid                | PASS                                 |
| Non-critical metadata is missing                | PASS_WITH_WARNINGS                   |
| ROM metadata is missing                         | PASS_WITH_WARNINGS / REVIEW_REQUIRED |
| ROM was not completed                           | FAIL or REVIEW_REQUIRED              |
| Calibration quality is low                      | PASS_WITH_WARNINGS / FAIL            |
| Long time gap between calibration and recording | PASS_WITH_WARNINGS                   |

Minimal v1 recommendation:

```text
Prioritize metadata fields already known to be missing from the audit:
Capture Frame Rate
Export Frame Rate
Rotation Type
Length Units
frame number continuity
calibration fields if available
```

---

## Stage 1.2 — Missing Data

Compute for each joint:

```text
missing_frames
missing_percent
valid_frames
valid_percent
```

Compute at the session level:

```text
total_missing_percent
mean_joint_missing_percent
worst_joint_missing_percent
num_joints_above_missing_threshold
```

## Decisions

| Condition                                   | Decision                        |
| ------------------------------------------- | ------------------------------- |
| Low missing data across all joints          | PASS                            |
| Moderate missing data in a peripheral joint | PASS_WITH_WARNINGS              |
| High missing data in a peripheral joint     | EXCLUDE joint-specific features |
| High missing data in a core joint           | REVIEW_REQUIRED / FAIL          |
| High missing data across multiple joints    | FAIL or REVIEW_REQUIRED         |

---

## Stage 1.3 — Longest Continuous Gap

Compute for each joint:

```text
num_gaps
longest_gap_frames
longest_gap_seconds
mean_gap_duration_seconds
gap_duration_distribution
```

Thresholds must be stored in seconds, not only in frames.

If the sampling rate is 120 Hz:

```text
0.5 sec ≈ 60 frames
```

## Initial Gap Classification

|                Gap duration | Classification | Action                |
| --------------------------: | -------------- | --------------------- |
|                 Up to 0.08s | short          | usually acceptable    |
|                  0.08–0.25s | moderate       | warning               |
|                  0.25–0.50s | long           | low confidence        |
|                 Above 0.50s | severe         | exclude segment/joint |
| Above 0.50s in a core joint | critical       | possible session FAIL |

## Example Decision Logic

```text
if core_joint.longest_gap_seconds > 0.5:
    session_status = REVIEW_REQUIRED or FAIL
    core_based_features = LOW_CONFIDENCE

if peripheral_joint.longest_gap_seconds > 0.5:
    joint_status = UNRELIABLE
    derivative_features_for_joint = EXCLUDE
```

---

## Stage 1.4 — Raw Jump / Outlier Detection

Compute:

```text
frame_to_frame_displacement
instantaneous_raw_speed
raw_jump_count
raw_jump_locations
```

The goal is to detect implausible raw jumps before the pipeline “fixes” them.

## Decisions

| Condition                            | Action                                              |
| ------------------------------------ | --------------------------------------------------- |
| Single jump in a peripheral joint    | PASS_WITH_WARNINGS                                  |
| Multiple jumps in a peripheral joint | EXCLUDE joint-specific derivative features          |
| Jump in a core joint                 | REVIEW_REQUIRED                                     |
| Multiple jumps in core joints        | FAIL                                                |
| Jump near a gap                      | Forward to Stage 2 as suspected processing artifact |

Minimal v1 recommendation:

```text
Use broad hard artifact bounds.
Do not tune these bounds aggressively.
They should catch physically implausible events, not classify unusual Gaga movement as abnormal.
```

---

## Stage 1.5 — Raw Eligibility Decision

At the end of Stage 1, produce:

```text
raw_data_qc_status = PASS / PASS_WITH_WARNINGS / REVIEW_REQUIRED / FAIL
```

If Stage 1 fails:

```text
full processing may stop
or continue in diagnostic-only mode
all final features must be marked as unreliable unless explicitly reviewed
```

This must align with the existing Fast QC policy.

---

# Stage 2 — Pipeline Processing QC

## Purpose

Determine whether the pipeline preserved skeleton and signal integrity after:

```text
cleaning
gap filling
filtering
anatomical constraints
joint reconstruction
```

Central question:

```text
Did processing preserve anatomical and signal integrity?
```

Stage 2 should rely on existing stage outputs when possible, rather than recomputing expensive checks.

---

## Stage 2.1 — Anatomical Segment Consistency

Focus only on anatomically meaningful rigid or semi-rigid segments.

Do not use the following as primary rigid-body checks:

```text
shoulder-to-shoulder
hip-to-hip
shoulder-to-hip
head-to-pelvis
```

In the first implementation, focus on:

```text
left_upper_arm: LeftShoulder → LeftArm
right_upper_arm: RightShoulder → RightArm

left_forearm: LeftArm → LeftForeArm / LeftForeArm → LeftHand depending on schema
right_forearm: RightArm → RightForeArm / RightForeArm → RightHand depending on schema

left_thigh: LeftUpLeg → LeftLeg
right_thigh: RightUpLeg → RightLeg

left_shin: LeftLeg → LeftFoot
right_shin: RightLeg → RightFoot
```

The exact segment definitions must use the project’s canonical skeleton hierarchy.

## Metrics

```text
segment_length_mean
segment_length_std
segment_length_cv = std / mean
segment_length_min
segment_length_max
segment_length_range_percent = (max - min) / mean
segment_length_spike_count
```

## Initial Thresholds

| segment_length_cv | Status          |
| ----------------: | --------------- |
|            < 2–3% | GOOD            |
|              3–5% | WARNING         |
|              > 5% | BAD             |
|             > 10% | SEVERE_ARTIFACT |

These thresholds are initial only.

They should be calibrated after reviewing 10–20 high-quality sessions.

## Decisions

```text
if segment_length_cv > bad_threshold:
    segment_status = BAD
    related_limb_features = LOW_CONFIDENCE

if segment_length_range_percent > severe_threshold:
    mark_possible_marker_swap_or_gap_artifact
```

Minimal v1 recommendation:

```text
Use segment length CV as a warning and reliability signal.
Do not use it as a hard session-fail gate unless the affected segment is core-critical or the deviation is severe.
```

---

## Stage 2.2 — Raw-to-Processed Correction

Measure how much the pipeline changed the data.

For each joint:

```text
correction_vector = processed_position - raw_position
mean_correction_magnitude
median_correction_magnitude
max_correction_magnitude
correction_magnitude_p95
correction_in_gap_regions
correction_in_non_gap_regions
```

## Principle

Large correction inside a gap may be justified.

Large correction in regions that were not missing or flagged is suspicious.

## Decisions

| Condition                           | Action                                              |
| ----------------------------------- | --------------------------------------------------- |
| Small correction in valid regions   | PASS                                                |
| Large correction inside a gap       | PASS_WITH_WARNINGS / continue to gap-boundary tests |
| Large correction in non-gap regions | REVIEW_REQUIRED                                     |
| Large correction in a core joint    | REVIEW_REQUIRED / possible FAIL                     |

Minimal v1 recommendation:

```text
This check is useful, but it may require careful alignment between raw and processed coordinate frames.
If alignment is non-trivial, implement a simplified version first:
- correction counts and magnitudes only where gap/interpolation logs exist;
- do not require full raw-to-filtered signal comparison in v1.
```

---

## Stage 2.3 — Gap Boundary Artifact Test

For every filled gap, inspect windows around the gap boundaries:

```text
gap_start ± 0.25 sec
gap_end ± 0.25 sec
```

If the sampling rate is 120 Hz:

```text
±30 frames
```

## Metrics

```text
position_discontinuity_at_gap_start
position_discontinuity_at_gap_end
velocity_jump_at_gap_boundary
acceleration_peak_near_gap_boundary
jerk_peak_near_gap_boundary
overshoot_score
```

## Decisions

```text
if acceleration_peak_time within gap_boundary_window:
    acceleration_feature_for_joint = LOW_CONFIDENCE or EXCLUDE

if jerk_peak_time within gap_boundary_window:
    jerk_feature_for_joint = EXCLUDE

if position_discontinuity is high:
    processed_trajectory_segment = BAD

if artifact occurs in core joint:
    session_status = REVIEW_REQUIRED or FAIL
```

Minimal v1 recommendation:

```text
Implement only if gap/interpolation logs are available.
If no gaps were filled, write a simple PASS/NOT_APPLICABLE result.
```

---

## Stage 2.4 — Filter Artifact / Overshoot Test

Check whether filtering introduced distortions, especially around:

```text
start/end of signal
sharp motion transitions
gap-filled regions
high acceleration events
```

Possible metrics:

```text
edge_artifacts_at_start_end
ringing_after_sharp_motion
overshoot_after_gap_fill
derivative_amplification
```

A filter sensitivity test may compare nearby cutoff values:

```text
filter_cutoff = 5Hz
filter_cutoff = 6Hz
filter_cutoff = 8Hz
```

and compute:

```text
feature_sensitivity_to_filter
```

However, this should not run by default.

## Decisions

| Condition                                      | Action                   |
| ---------------------------------------------- | ------------------------ |
| Mean speed is stable across filter settings    | RELIABLE                 |
| Acceleration changes slightly                  | ACCEPTABLE               |
| Acceleration changes substantially             | WARNING                  |
| Jerk changes substantially                     | LOW_CONFIDENCE / EXCLUDE |
| Burst count depends strongly on filter setting | UNRELIABLE               |

Minimal v1 recommendation:

```text
Do not run full filter sensitivity analysis on every session in v1.
Use existing PSD validation and filtering summary first.
Classify full sensitivity analysis as deep_diagnostic_qc or offline_batch_audit_only.
```

---

## Stage 2.5 — Processing QC Decision

At the end of Stage 2, produce:

```text
processing_qc_status = PASS / PASS_WITH_WARNINGS / REVIEW_REQUIRED / FAIL
```

Also produce:

```text
joint_processing_flags
segment_processing_flags
gap_artifact_flags
filter_artifact_flags
```

Minimal v1 recommendation:

```text
Prefer compact sidecar outputs and metadata summaries.
Do not add many per-frame flags to kinematics_master.parquet unless Phase 10 approves them.
```

---

# Stage 3 — Final Feature QC

## Purpose

Determine whether the final features are reliable enough for scientific use.

Central question:

```text
Which extracted kinematic features are reliable enough for downstream analysis?
```

Stage 3 should primarily produce sidecar reliability tables.

It should not automatically expand `kinematics_master.parquet` with reliability columns for every feature.

---

## Stage 3.1 — Static Noise Floor, if available

If a static anchor is available, compute for each joint:

```text
static_mean_speed
static_median_speed
static_p95_speed
static_max_speed

static_mean_acceleration
static_median_acceleration
static_p95_acceleration
static_max_acceleration

static_drift_distance
static_position_std
```

Goal:

```text
How much motion does the system invent when there should be almost no motion?
```

## Use

The static noise floor may affect movement interpretation:

```text
movement_detected_only_if speed > 3 * static_noise_floor
```

or:

```text
feature_reliable_only_if feature_magnitude > noise_floor_threshold
```

If no static anchor exists:

```text
static_noise_floor_status = NOT_AVAILABLE
```

Not FAIL.

Minimal v1 recommendation:

```text
Use an existing static/reference window if available.
Do not build a new complex static detector in v1.
```

---

## Stage 3.2 — Cyclic Anchor QC, if available

If a cyclic anchor exists, compute:

```text
periodicity_score
cycle_consistency
dynamic_segment_stability
left_right_symmetry_if_relevant
gap_rate_during_cyclic_motion
peak_reliability_during_cyclic_motion
```

The goal is to test basic dynamic reliability under simple movement.

If no cyclic anchor exists:

```text
cyclic_anchor_status = NOT_AVAILABLE
```

Not FAIL.

Minimal v1 recommendation:

```text
Classify cyclic-anchor QC as future_v2 unless event markers or annotations already exist.
```

---

## Stage 3.3 — Hard Artifact Bounds

Define broad bounds for values that almost certainly represent artifacts.

Important: do not call these “normal movement bounds.” Use:

```text
Hard Artifact Bounds
```

because Gaga and free movement can be unusual, fast, and non-standard.

Check:

```text
joint_speed
joint_acceleration
joint_jerk
instantaneous_displacement
segment_length_change
pelvis_speed
distal_joint_speed
```

Separate:

```text
core joints
distal joints
```

because distal joints such as wrists and ankles can move faster than the pelvis/trunk.

## Decisions

```text
if core_joint_speed exceeds hard_bound:
    core_feature = EXCLUDE
    session_status may become FAIL

if distal_joint_speed exceeds hard_bound:
    joint_feature = ARTIFACT_SUSPECTED

if acceleration exceeds hard_bound near gap:
    derivative_features = EXCLUDE

if jerk exceeds hard_bound:
    jerk_feature = LOW_CONFIDENCE or EXCLUDE
```

Minimal v1 recommendation:

```text
Use broad, conservative bounds only.
The goal is to catch impossible values, not unusual but valid dance movement.
```

---

## Stage 3.4 — Peak Event Reliability

For each peak-type feature:

```text
peak_speed
peak_acceleration
peak_jerk
burst_count
max_range_event
```

Store:

```text
peak_time
peak_value
nearest_gap_distance_seconds
interpolation_status_at_peak
processing_artifact_near_peak
raw_quality_at_peak
```

## Decisions

| Condition                                    | Action               |
| -------------------------------------------- | -------------------- |
| Peak far from gap and in high-quality region | RELIABLE             |
| Peak close to gap                            | LOW_CONFIDENCE       |
| Peak inside interpolation                    | UNRELIABLE / EXCLUDE |
| Peak occurs at gap boundary                  | EXCLUDE              |
| Peak exceeds hard bound                      | ARTIFACT / EXCLUDE   |

Minimal v1 recommendation:

```text
Apply peak-event reliability only to downstream scalar features that depend on peaks.
Do not compute peak reliability for every time-series column in v1.
```

---

## Stage 3.5 — Feature Reliability Label

Every final downstream feature should receive one label:

```text
RELIABLE
WARNING
LOW_CONFIDENCE
UNRELIABLE
EXCLUDE
NOT_AVAILABLE
```

The label should be based on combined evidence from all three QC stages.

Example:

```text
feature: right_wrist_peak_acceleration
raw_status: WARNING
longest_gap = 0.42s
processing_status: gap_boundary_overshoot detected
final_status: EXCLUDE
reason: peak acceleration occurs within 0.1s of filled gap boundary
```

Minimal v1 recommendation:

```text
Feature reliability labels should be produced in a sidecar table, not necessarily inside kinematics_master.parquet.
```

---

# Confidence Propagation

Flags must propagate from earlier stages to later stages.

That is:

```text
Stage 1 issue
→ Stage 2 processing risk
→ Stage 3 feature reliability impact
```

## Example

```text
Stage 1:
right_wrist longest_gap = 0.7s

Stage 2:
gap filling creates acceleration overshoot at gap boundary

Stage 3:
right_wrist acceleration = EXCLUDE
right_wrist jerk = EXCLUDE
right_wrist position range = WARNING
upper limb symmetry = LOW_CONFIDENCE
```

## Additional Example

```text
Stage 1:
pelvis missing = high

Stage 2:
pelvis processed trajectory has large corrections

Stage 3:
whole-body movement volume = UNRELIABLE
center-of-mass proxy = EXCLUDE
session_quality = FAIL or REVIEW_REQUIRED
```

Minimal v1 recommendation:

```text
Implement propagation at the level of:
- joint
- segment
- feature
- session

Do not implement highly granular per-frame propagation unless Phase 10 approves it.
```

---

# Unified Session Decision Logic

## PASS

A session receives PASS when:

```text
raw data quality acceptable
core joints stable
no severe core gaps
segment lengths stable
no severe gap-boundary artifacts
no severe hard artifact bounds exceeded
feature reliability sufficient for planned analysis
```

## PASS_WITH_WARNINGS

A session receives PASS_WITH_WARNINGS when:

```text
some peripheral joints are unreliable
some features need exclusion
noise floor is elevated but manageable
gap filling is acceptable for position but not derivatives
some peak features are low confidence
session is usable with restrictions
```

## REVIEW_REQUIRED

A session receives REVIEW_REQUIRED when:

```text
a core issue exists but may not invalidate all features
reference confidence is questionable
filtering status is unresolved
feature reliability depends on user/analyst decision
metadata is incomplete in a way that affects interpretation
```

## FAIL

A session receives FAIL when:

```text
core joints are unreliable
camera/ROM calibration invalid or missing
large continuous gaps occur in core joints
processed skeleton is anatomically unstable
hard artifact bounds are exceeded in central body trajectories
static drift/noise is too high if static anchor exists
too many key features are unreliable for planned analysis
recording is too short or dead
```

---

# Downstream Flags and Master Dataset Policy

Before saving or using features downstream, each feature should have associated reliability information:

```text
reliability_label
qc_status
qc_reason
source_qc_stage
recommended_action
```

Example:

```text
right_wrist_peak_acceleration_value
right_wrist_peak_acceleration_reliability
right_wrist_peak_acceleration_qc_reason
```

However, reliability must not automatically be stored as one additional column per feature inside `kinematics_master.parquet`.

## Default policy

```text
kinematics_master.parquet should remain primarily numeric and model-ready.

Detailed reliability labels, QC reasons, and downstream-use decisions should be stored in sidecar outputs such as:

session_qc_report.json
feature_reliability_table.csv/parquet
downstream_flags.csv
```

Only a small number of canonical QC fields should be added directly to `kinematics_master.parquet`, and only after Phase 10 approves them as part of the master dataset contract.

Examples of candidate canonical fields may include:

```text
session_id
subject_id
timepoint
piece
rep
filter_psd_verdict
ref_is_fallback
bone_qc_status
nan_guard_status
gate_status
```

Per-feature reliability columns should be sidecar by default.

---

# Day / Experiment-Level Aggregation

After all sessions are processed independently, QC may be aggregated at the day / experiment level.

## Inputs

```text
session_qc_report for all sessions in experiment/day
```

## Outputs

```text
day_qc_report.json
day_qc_summary.csv
```

## Metrics

```text
num_sessions
num_sessions_pass
num_sessions_warning
num_sessions_fail

mean_session_reliability_score
min_session_reliability_score
day_qc_evidence_level

joint_reliability_across_sessions
feature_reliability_across_sessions
quality_drift_across_day
calibration_stability_across_day
```

## Central Question

```text
Was the recording day reliable enough for the planned analysis?
```

## Example Decisions

```text
day_status = PASS
reason = all 4 sessions usable; only minor peripheral warnings

day_status = PASS_WITH_WARNINGS
reason = 1 free-dance session has low-confidence wrist derivatives

day_status = FAIL
reason = core joint tracking degraded across multiple sessions
```

Minimal v1 recommendation:

```text
Do not implement day-level aggregation before session-level QC is stable.
Classify day-level aggregation as future_v2 unless Phase 10 explicitly promotes it.
```

---

# Historical vs Future Sessions

The system must be backward-compatible.

## Historical Sessions

These may include:

```text
static only
no cyclic anchor
no event markers
limited metadata
```

In such cases:

```text
cyclic_anchor_status = NOT_AVAILABLE
qc_evidence_level may be LOW or MEDIUM
session is not failed because cyclic anchor is absent
```

## Future Sessions

For future recordings, it is recommended to add at the beginning of every session:

```text
5–10 seconds quiet standing
3–5 repetitions of a simple cyclic movement
```

However, this is an additional evidence layer, not a mandatory validity condition.

Important wording:

```text
Future cyclic anchors improve QC evidence strength but are not required for historical session validity.
```

---

# Suggested File Schemas

These schemas are conceptual. Phase 10 must decide which files are required in Minimal v1.

## session_qc_report.json

```json
{
  "session_id": "S001",
  "participant_id": "P001",
  "experiment_id": "E001",
  "sampling_rate": 120,
  "session_qc_status": "PASS_WITH_WARNINGS",
  "session_reliability_score": 0.82,
  "qc_evidence_level": "MEDIUM",
  "available_qc_anchors": {
    "static_anchor": true,
    "cyclic_anchor": false,
    "structured_task_evidence": false
  },
  "raw_data_qc": {
    "status": "PASS",
    "total_missing_percent": 2.4,
    "core_joint_failures": [],
    "peripheral_joint_warnings": ["RightHand"]
  },
  "processing_qc": {
    "status": "PASS_WITH_WARNINGS",
    "segment_consistency": {
      "right_forearm": {
        "cv": 0.047,
        "status": "WARNING"
      }
    },
    "gap_boundary_artifacts": [
      {
        "joint": "RightHand",
        "time": 72.4,
        "artifact": "acceleration_overshoot",
        "status": "WARNING"
      }
    ]
  },
  "final_feature_qc": {
    "status": "PASS_WITH_WARNINGS",
    "static_noise_floor": {
      "Hips_mean_speed": 0.003,
      "RightHand_p95_speed": 0.021
    },
    "feature_reliability": [
      {
        "feature": "RightHand_peak_acceleration",
        "status": "EXCLUDE",
        "reason": "peak occurs near filled gap boundary"
      },
      {
        "feature": "whole_body_mean_speed",
        "status": "RELIABLE",
        "reason": "core joints stable and noise floor acceptable"
      }
    ]
  },
  "downstream_actions": {
    "use_session": true,
    "exclude_joints": [],
    "low_confidence_joints": ["RightHand"],
    "exclude_features": [
      "RightHand_peak_acceleration",
      "RightHand_jerk"
    ],
    "notes": "Session usable for whole-body speed and range features, but distal right hand derivative features should be excluded."
  }
}
```

---

## joint_quality_table.csv

```text
session_id
participant_id
joint
joint_group
missing_percent
longest_gap_seconds
num_gaps
raw_jump_count
static_noise_speed_p95
status
recommended_action
reason
```

---

## segment_quality_table.csv

```text
session_id
participant_id
segment
proximal_joint
distal_joint
mean_length
std_length
cv
range_percent
spike_count
status
recommended_action
reason
```

---

## processing_artifacts_table.csv

```text
session_id
participant_id
joint
artifact_type
time_start
time_end
related_gap_id
severity
affected_features
recommended_action
reason
```

---

## feature_reliability_table.csv

```text
session_id
participant_id
feature_name
joint_or_segment
time_window_start
time_window_end
feature_value
raw_quality_flag
processing_quality_flag
noise_floor_flag
hard_bound_flag
peak_reliability_flag
final_reliability
recommended_action
reason
```

---

## downstream_flags.csv

```text
session_id
participant_id
joint
feature
time_window
flag
reason
source_qc_stage
recommended_action
```

---

## day_qc_summary.csv

```text
experiment_id
participant_id
recording_date
num_sessions
num_pass
num_warning
num_fail
mean_reliability_score
min_reliability_score
day_qc_status
day_evidence_level
main_limitations
recommended_downstream_action
```

---

# QC Plots

Plots are useful, but should not become a default burden for every routine run.

## Recommended v1 plot policy

```text
Generate plots by default for:
- FAIL sessions
- PASS_WITH_WARNINGS sessions
- golden regression sessions
- explicit diagnostic runs

For routine PASS sessions:
- plots may be skipped
- or generated on demand
```

## Candidate plots

```text
missing_percent_per_joint.png
longest_gap_per_joint.png
segment_length_cv.png
hard_artifact_events.png
feature_reliability_summary.png
```

## If a static anchor exists

```text
static_noise_floor_per_joint.png
static_drift_per_joint.png
```

## If a cyclic anchor exists

```text
cyclic_periodicity_summary.png
cyclic_segment_stability.png
```

## If gap filling exists

```text
gap_boundary_artifacts.png
acceleration_spikes_near_gaps.png
```

## Recommended only for diagnostics or batch audit

```text
raw_vs_processed_trajectory_examples.png
joint_quality_heatmap.png
day_quality_across_sessions.png
```

---

# Minimal v1 Implementation Candidate

For Phase 10 planning, Minimal v1 should be treated as the default candidate scope.

Full v2 additions are future work unless Phase 10 explicitly promotes a specific item.

If an initial version needs to be implemented, start with a small, useful, and testable set.

## Stage 1

```text
1. metadata / calibration availability check
2. missing_percent per joint
3. longest_gap per joint
4. raw jump detection
5. dead / too-short session gate
6. frame continuity check
```

## Stage 2

```text
7. segment_length_cv for key anatomical segments
8. segment_length_range_percent
9. raw-to-processed correction size, if alignment/logs permit
10. gap-boundary acceleration/jerk artifact, if gap logs exist
11. filter PSD verdict propagation
12. reference fallback propagation
```

## Stage 3

```text
13. static noise floor, if static/reference anchor exists
14. hard artifact bounds
15. peak-event reliability for downstream scalar features only
16. feature reliability labeling via sidecar table
```

This is strong enough for a first version and is backward-compatible with historical sessions.

Phase 10 should decide whether this list is too large and should be reduced further.

---

# Full v2 / Future Additions

After Minimal v1 is working and validated, consider:

```text
automatic static anchor detection
automatic cyclic anchor detection
filter sensitivity analysis
structured-task evidence module
video-mocap sync check
human tag validation layer
personal baseline comparison
group baseline comparison
automatic QC dashboard
semantic movement tags
day-level QC aggregation
per-frame reliability propagation
full raw-to-filtered signal comparison
```

These are not Minimal v1 requirements.

---

# Key Implementation Requirements

## 1. Do not hard-code logic by session type

Do not write:

```text
if session_type == "4min":
    run special QC
```

Instead:

```text
if static_anchor_available:
    run_static_qc()

if cyclic_anchor_available:
    run_cyclic_qc()

if structured_task_evidence_available:
    run_structured_task_qc()
```

---

## 2. A missing optional test is not a failure

If no cyclic anchor exists:

```text
cyclic_anchor_status = NOT_AVAILABLE
```

Not:

```text
FAIL
```

---

## 3. Every downstream feature needs a reliability label

Do not use final downstream features without a reliability label.

However, this reliability label should default to a sidecar table rather than expanding `kinematics_master.parquet`.

---

## 4. Flags must propagate downstream

If Stage 1 identifies a joint-level issue, Stage 3 must know about it.

If Stage 2 identifies a processing artifact, affected features must know about it.

If Step 05 uses fallback reference, downstream PCA / angular features must know about it.

If Step 04 reports REVIEW_OVERSMOOTHING, downstream feature interpretation must know about it.

---

## 5. Thresholds must be configurable

All thresholds should be stored in configuration, for example:

```text
qc_thresholds.yaml
```

not hard-coded.

---

## 6. Preserve the current architecture unless Phase 10 approves a change

Do not migrate away from:

```text
pandas
parquet
existing step-based pipeline
existing master parquet concept
```

Do not turn this into a generalized biomechanics toolbox.

---

# Summary for the Development Agent

```text
Evaluate how to integrate a unified session-level QC and validation system into the OptiTrack kinematic pipeline without overengineering.

Do not implement this plan directly unless it has passed the Phase 10 decision gate.

The QC system should apply the same architecture to every recorded session, regardless of whether the session is a fixed 4-minute exercise session, a free-dance session, a historical session, or a future session.

The QC system should be organized conceptually into three stages:

Stage 1, Raw Data QC, determines whether the raw recording is eligible for processing. It evaluates calibration metadata, tracking completeness, missing data, longest gaps, raw jumps, frame continuity, and joint criticality.

Stage 2, Pipeline Processing QC, evaluates whether cleaning, anatomical constraints, gap filling, and filtering preserved skeleton and signal integrity. It focuses on rigid anatomical segment consistency, raw-to-processed displacement, gap-boundary artifacts, filter-induced overshoot, derivative contamination, PSD verdict propagation, and reference fallback propagation.

Stage 3, Final Feature QC, evaluates whether extracted kinematic features are reliable enough for downstream analysis. It estimates static noise floor when a static/reference anchor is available, applies broad hard artifact bounds, checks peak-event reliability for relevant downstream scalar features, and assigns reliability labels to final features.

The system must be backward-compatible with historical sessions. Optional QC anchors such as static standing, cyclic movement, or structured-task evidence should strengthen the QC evidence level when available, but their absence must not automatically invalidate a session.

Each session should receive a session_qc_status, session_reliability_score, qc_evidence_level, joint-level flags, segment-level flags, and feature-level reliability labels.

Detailed reliability should be stored primarily in sidecar outputs such as session_qc_report.json and feature_reliability_table.csv/parquet. kinematics_master.parquet should remain primarily numeric and model-ready unless Phase 10 explicitly approves adding canonical QC fields.
```

---

# Final Principle

The rebuilt pipeline should not output only a table of features.

It should output:

```text
features
+ reliability labels
+ QC reasons
+ downstream-use decisions
```

In other words:

> Every kinematic number that enters analysis must also answer the question:
> “How much can we trust this value, and why?”

But this must be achieved with a minimal, staged, evidence-based design — not by adding unnecessary complexity to every pipeline run.

```

