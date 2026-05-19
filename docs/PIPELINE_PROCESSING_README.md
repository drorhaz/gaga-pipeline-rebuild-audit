# Pipeline Processing Reference — Step-by-Step Guide

> **Pipeline:** Gaga Motion Analysis Pipeline (Steps 01–06 + 08)
> **Orchestrator:** `run_pipeline.py`
> **Configuration:** `config/config_v1.yaml`
> **Source code:** `src/` modules + `notebooks/` Jupyter notebooks

This document is the authoritative reference for how raw OptiTrack motion capture CSV files are transformed into the final `kinematics_master.parquet` through a six-step signal processing pipeline. Each step is documented with its **purpose**, **inputs/outputs**, **algorithms and mathematics**, **parameters**, and **quality control gates**.

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [Step 00 — Setup & Configuration](#2-step-00--setup--configuration)
3. [Step 01 — Parse & Load](#3-step-01--parse--load)
4. [Step 02 — Preprocessing (Gap Filling)](#4-step-02--preprocessing-gap-filling)
5. [Step 03 — Resampling (Uniform Time Grid)](#5-step-03--resampling-uniform-time-grid)
6. [Step 04 — Filtering (3-Stage Signal Cleaning)](#6-step-04--filtering-3-stage-signal-cleaning)
7. [Step 05 — Reference Detection (T-Pose)](#7-step-05--reference-detection-t-pose)
8. [Step 06 — Kinematics (Master Feature Computation)](#8-step-06--kinematics-master-feature-computation)
9. [Step 08 — Engineering Physical Audit](#9-step-08--engineering-physical-audit)
10. [Quality Control Gate System](#10-quality-control-gate-system)
11. [Pipeline Orchestration (run_pipeline.py)](#11-pipeline-orchestration)
12. [Configuration Reference](#12-configuration-reference)
13. [File Naming & Directory Convention](#13-file-naming--directory-convention)
14. [References](#14-references)

---

## 1. Pipeline Overview

### What the pipeline does

The Gaga Motion Analysis Pipeline transforms raw OptiTrack motion capture recordings (CSV files containing 3D positions and quaternion orientations of ~50 body segments at ~120 Hz) into a clean, feature-rich kinematic dataset suitable for machine learning, biomechanical analysis, and movement science research.

### Processing flow

```
Raw CSV (OptiTrack)
    │
    ▼
[Step 01] Parse & Load ──────────────► parsed_run.parquet
    │
    ▼
[Step 02] Preprocessing (Gap Fill) ──► preprocessed.parquet
    │
    ▼
[Step 03] Resample (Uniform Grid) ──► resampled.parquet
    │
    ▼
[Step 04] Filter (3-Stage Clean) ───► filtered.parquet
    │
    ▼
[Step 05] Reference Detection ──────► reference_map.json + kinematics_map.json
    │
    ▼
[Step 06] Kinematics ──────────────► kinematics_master.parquet + validation_report.json
    │
    ▼
[Step 08] Engineering Audit ────────► audit_report.json
```

### Key design principles

1. **Immutability:** Each step reads only from the previous step's output and writes a new file. No in-place modification.
2. **Reproducibility:** All parameters come from a single YAML configuration file. No magic numbers in code.
3. **Auditability:** Every step produces metadata/QC reports alongside the data, enabling forensic inspection.
4. **Position-first, then rotation:** Positions are cleaned and filtered before rotational kinematics are computed, because position artifacts propagate into derived velocity/acceleration features.

---

## 2. Step 00 — Setup & Configuration

**Notebook:** `00_setup.ipynb`
**Source:** `src/pipeline_config.py`

### What it does

Loads the project configuration, sets up paths, and prepares the environment. This is not a data processing step — it initializes the processing context.

### Configuration loading chain

```
config/config_v1.yaml                    ← Single source of truth (YAML)
    │
    ▼
src/pipeline_config.py                   ← Loads YAML, applies defaults
    │
    ├─► CONFIG dict (lowercase keys)     ← Direct YAML values
    ├─► CONFIG dict (UPPERCASE aliases)  ← FS_TARGET, SG_POLYORDER, etc.
    └─► CONFIG["THRESH"]                 ← QC thresholds (uppercase keys)
```

### Subject anthropometrics injection

Subject-specific height and weight are looked up from `data/subjects_registry.json`:

```
Priority chain:
  1. YAML explicit values (if set)
  2. subjects_registry.json (measured values)
  3. None (triggers "MISSING_ANTHRO" metadata sentinel)
```

The **Metadata Sentinel** flags unreliable anthropometrics:
- Default values (170 cm, 70 kg) → `UNRELIABLE_COM_DEFAULT_ANTHRO`
- Missing values → `MISSING_ANTHRO`
- Researcher-provided values → `SUBJECT_SPECIFIC`

This affects the reliability of Whole-Body Center of Mass calculations downstream.

---

## 3. Step 01 — Parse & Load

**Notebook:** `01_Load_Inspect.ipynb`
**Source:** `src/preprocessing.py` → `parse_optitrack_csv()`
**Input:** Raw CSV file from OptiTrack/Motive
**Output:** `derivatives/step_01_parse/{RUN_ID}__parsed_run.parquet`

### What it does

Reads the raw OptiTrack CSV export and extracts structured data: frame indices, timestamps, 3D positions, and quaternion orientations for every body segment.

### Algorithm: CSV Parsing

OptiTrack CSVs have a non-standard format with metadata rows, a name row, and a header row before the actual data:

```
Row 0-14:   Metadata (Motive version, calibration info, capture date)
Row N:      Name row ("Name", "", "763:763", "763:Ab", "763:Chest", ...)
Row N+1:    Header row ("Frame", "Time", "X", "Y", "Z", "W", "X", "Y", "Z", ...)
Row N+2:    Data starts
```

**Parsing steps:**

1. **Read first 300 rows** to find the header structure.
2. **Find Header Row:** Scan for a row containing both "Frame" and "Time" (or "Time (Seconds)").
3. **Find Name Row:** Scan rows above the header for a row where column 1 is "Name". This contains the segment names in OptiTrack's format.
4. **Extract calibration metadata** from the first 15 rows (wand error, pointer RMS, Motive version, capture date).

### Name Mapping (Motive → Standard Schema)

OptiTrack uses abbreviated segment names. These are mapped to a standardized skeleton schema:

| OptiTrack Name | Standard Name | Description |
|---------------|---------------|-------------|
| `763:763` (asset == bone) | `Hips` | Root segment (when asset name equals bone name) |
| `Ab` | `Spine` | Abdomen → Lower spine |
| `Chest` | `Spine1` | Chest → Mid/upper spine |
| `LShoulder` | `LeftShoulder` | Left shoulder girdle |
| `LUArm` | `LeftArm` | Left upper arm (humerus) |
| `LFArm` | `LeftForeArm` | Left forearm |
| `LThigh` | `LeftUpLeg` | Left thigh (femur) |
| `LShin` | `LeftLeg` | Left shank (tibia) |
| ... | ... | (full mapping in `correct_motive_name()`) |

### Data extraction

For each mapped segment, the parser extracts columns in groups:
- **Rotation:** 4 consecutive columns `[X, Y, Z, W]` → quaternion `(qx, qy, qz, qw)`
- **Position:** 3 consecutive columns `[X, Y, Z]` → position in millimeters `(px, py, pz)`

Output arrays:
- `pos_mm`: shape `(T, J, 3)` — positions in millimeters
- `q_global`: shape `(T, J, 4)` — global quaternions in SciPy `xyzw` format

### Validation checks

1. **Time vector monotonicity:** Verifies `time_s` is strictly increasing. Raises `ValueError` if violated.
2. **Quaternion completeness:** For each found joint, checks that all 4 quaternion components exist and are not entirely NaN.
3. **NaN inventory:** Reports percentage of NaN values in positions and rotations.

### Duration gatekeeper

Files shorter than `min_run_seconds` (default: 5s) are rejected with status `SKIP`.

---

## 4. Step 02 — Preprocessing (Gap Filling)

**Notebook:** `02_preprocess.ipynb`
**Sources:** `src/preprocessing.py`, `src/gapfill_positions.py`, `src/gapfill_quaternions.py`
**Input:** `step_01_parse/{RUN_ID}__parsed_run.parquet`
**Output:** `step_02_preprocess/{RUN_ID}__preprocessed.parquet`, `{RUN_ID}__kinematics_map.json`

### What it does

Fills gaps (NaN frames) in both position and quaternion data, detects and masks velocity-based artifacts, and builds the kinematic joint hierarchy map.

### 4.1 Artifact Detection & Masking

Before gap filling, the pipeline detects non-physiological spikes using a **velocity-based MAD (Median Absolute Deviation) threshold**:

```
Algorithm: detect_and_mask_artifacts()
  1. Compute frame-to-frame velocity: vel[t] = diff(data[t]) / diff(time[t])
  2. Compute absolute velocity: |vel|
  3. Remove NaN velocities, compute MAD on valid velocities:
     σ = MAD(|vel|) / 0.6745     (convert MAD to standard deviation equivalent)
  4. Threshold = mad_multiplier × σ     (default mad_multiplier = 3.0)
  5. Flag frames where |vel| > threshold
  6. Expand mask by ±expand_frames (default: 1) to catch neighborhood corruption
  7. Replace flagged frames with NaN (these become gaps for the gap filler)
```

**Why MAD instead of standard deviation?** MAD is robust to outliers — a few extreme spikes don't inflate the threshold, so even isolated artifacts are caught.

### 4.2 Position Gap Filling

Fills NaN gaps in position data using **bounded cubic spline interpolation**:

```
Algorithm: bounded_spline_interpolation()
  1. Find all NaN gap regions (contiguous runs of NaN frames)
  2. For each gap:
     a. Compute gap duration = time[end] - time[start]
     b. IF gap_duration > max_gap_pos_sec (default: 1.0s) → skip (gap too large)
     c. IF gap is at the boundary of the recording → skip (can't extrapolate)
     d. Fit a cubic spline through all valid (non-NaN) points
     e. Evaluate spline at the gap timestamps
     f. Fallback: if spline fails, use linear interpolation
  3. Return filled data (same length, NaN gaps ≤ max_gap_s replaced)
```

**Why bounded?** Unbounded spline interpolation can produce wild oscillations when gaps are long. The time limit ensures interpolation only fills gaps where sufficient neighboring data constrains the estimate.

**Parameter:** `max_gap_pos_sec = 1.0` — gaps longer than 1 second are left as NaN.

### 4.3 Quaternion Gap Filling (SLERP)

Fills NaN gaps in quaternion data using **Spherical Linear Interpolation (SLERP)**:

```
Algorithm: gapfill_quaternion_slerp()
  1. For each joint's quaternion time series (qx, qy, qz, qw):
  2. Find pairs of consecutive valid (non-NaN) frames bounding a gap
  3. For each gap:
     a. Compute gap duration
     b. IF gap_duration > max_gap_quat_sec (default: 0.25s) → skip
     c. Normalize the two endpoint quaternions to unit length
     d. Compute interpolation weight: α = (t_gap - t_start) / (t_end - t_start)
     e. Interpolate: q(α) = q_start * (1-α) + q_end * α (linear blend)
     f. Renormalize to unit quaternion: q = q / ||q||
  4. Final pass: renormalize ALL quaternion frames to ensure unit length
```

**Why SLERP for quaternions?** Linear interpolation of quaternion components and renormalization is an approximation of true SLERP that works well for small gaps. True SLERP (using `scipy.spatial.transform.Slerp`) is used in Step 03 for resampling where precision matters more.

**Parameter:** `max_gap_quat_sec = 0.25` — only very short quaternion gaps (250 ms) are filled, because orientation data is more sensitive to interpolation artifacts.

### 4.4 Quaternion Normalization

After all gap filling, a global renormalization pass ensures every quaternion frame has unit length:

```
For each joint, each frame:
    q = q / ||q||
    (with ||q|| clamped to ≥ 1e-12 to avoid division by zero)
```

### 4.5 Kinematics Map Construction

The `kinematics_map.json` defines the **joint hierarchy** used for hierarchical quaternion computation in Step 06:

```json
{
  "Hips": {"parent": null, "angle_name": "Pelvis Tilt"},
  "Spine": {"parent": "Hips", "angle_name": "Lumbar Flexion"},
  "Spine1": {"parent": "Spine", "angle_name": "Thoracic Flexion"},
  "LeftArm": {"parent": "LeftShoulder", "angle_name": "L Shoulder"},
  ...
}
```

This map is built from the available joints in the data (not all skeleton joints may be present in every recording).

### Gate 2: Temporal Quality Assessment

Step 02 includes **Gate 2** quality metrics:

| Metric | Computation | Threshold |
|--------|------------|-----------|
| **Sample jitter** | StdDev(Δt) in milliseconds | > 2.0 ms → REVIEW |
| **Interpolation fallback rate** | % of frames using linear fallback instead of spline | > 5% → REVIEW, > 15% → REJECT |

---

## 5. Step 03 — Resampling (Uniform Time Grid)

**Notebook:** `03_resample.ipynb`
**Source:** `src/resampling.py`
**Input:** `step_02_preprocess/{RUN_ID}__preprocessed.parquet`
**Output:** `step_03_resample/{RUN_ID}__resampled.parquet`, forwarded `kinematics_map.json`

### What it does

OptiTrack captures at a nominal frame rate (e.g., 120 Hz), but the actual timestamps are slightly irregular due to USB/camera timing jitter. This step places all data onto a **perfectly uniform time grid** — a prerequisite for frequency-domain filtering and consistent derivative computation.

### 5.1 Sampling Frequency Estimation

```
Algorithm: estimate_fs()
  1. Compute all inter-frame durations: dt = diff(time_s)
  2. Remove non-finite values
  3. Estimated fs = 1.0 / median(dt)
```

The **median** (not mean) is used because it's robust to occasional dropped frames or timing glitches.

### 5.2 Uniform Time Grid Generation

```
Algorithm: resample_time_grid()
  1. t0 = time_s[0]  (first timestamp)
  2. t1 = time_s[-1]  (last timestamp)
  3. n = round((t1 - t0) * fs_target) + 1  (total frames at target rate)
  4. t_uniform = t0 + arange(n) / fs_target
```

**Parameter:** `fs_target = 120.0 Hz` — the target uniform sampling rate.

### 5.3 Position Resampling (Cubic Spline)

Positions are resampled using **cubic spline interpolation** (default) or linear interpolation:

```
Algorithm: resample_pos()
  For each joint j, each axis c (x, y, z):
    1. Find valid (non-NaN, finite) samples
    2. IF valid samples < 4: use linear interpolation (insufficient for spline)
    3. ELSE: fit CubicSpline(time_valid, pos_valid, extrapolate=False)
    4. Evaluate spline at uniform grid points t_uniform
    5. Points outside the original time range remain NaN (no extrapolation)
```

**Why cubic spline?** It produces smooth trajectories with continuous first and second derivatives, which is critical because velocity and acceleration are computed as derivatives of position in Step 06.

**Parameter:** `pos_resample_method = "cubic_spline"`

### 5.4 Quaternion Resampling (SLERP)

Quaternions are resampled using **SciPy's Slerp** (Spherical Linear Interpolation):

```
Algorithm: resample_quat_slerp()
  For each joint j:
    1. Extract valid (all 4 components finite) quaternion frames
    2. IF valid frames < 2: skip this joint
    3. Normalize and enforce temporal continuity:
       q = enforce_continuity(normalize(q_valid))
    4. Create SciPy Slerp interpolator: Slerp(time_valid, Rotation(q_valid))
    5. Evaluate at uniform grid points (only within valid time range)
    6. Convert back to xyzw quaternion format
    7. Apply shortest-path and normalize
```

**Why true SLERP here (not linear blend)?** The resampling step needs geometric precision because it sets the foundation for all subsequent rotational computations. SciPy's `Slerp` traverses the shortest great-circle arc on the unit quaternion hypersphere, preserving angular velocity and avoiding the slight drift that linear blending introduces.

### 5.5 Quaternion Preprocessing

Before resampling, quaternions are processed to ensure well-behaved interpolation:

1. **Normalization:** `q = q / ||q||` — force unit length
2. **Shortest path:** If `qw < 0`, flip the entire quaternion (`q *= -1`). This ensures the scalar component is non-negative, avoiding unnecessary 360° wrapping.
3. **Temporal continuity:** For consecutive frames, if `dot(q[t-1], q[t]) < 0`, flip `q[t]`. This prevents SLERP from taking the "long way around" (> 180°).

---

## 6. Step 04 — Filtering (3-Stage Signal Cleaning)

**Notebook:** `04_filtering.ipynb` 
**Source:** `src/filtering.py`
**Input:** `step_03_resample/{RUN_ID}__resampled.parquet`
**Output:** `step_04_filtering/{RUN_ID}__filtered.parquet`

### What it does

Removes noise and artifacts from position data using a three-stage cleaning pipeline, and applies a separate median filter to quaternion data. This is the most complex processing step.

### Overview of the 3-Stage Architecture

```
Position Data ─────►┌─────────────────────────┐
                     │  Stage 1: Artifact       │
                     │  Detector (Z-Score +     │
                     │  Velocity)               │
                     │  → NaN flagging + PCHIP  │
                     └───────────┬──────────────┘
                                 │
                     ┌───────────▼──────────────┐
                     │  Stage 2: Hampel Filter   │
                     │  (Sliding Window Median)  │
                     │  → Outlier replacement    │
                     └───────────┬──────────────┘
                                 │
                     ┌───────────▼──────────────┐
                     │  Stage 3: Adaptive        │
                     │  Low-Pass (Winter's       │
                     │  Residual + Butterworth)  │
                     └───────────┬──────────────┘
                                 │
                     ┌───────────▼──────────────┐
Quaternion Data ────►│  Quaternion Median Filter │
                     │  (scipy.signal.medfilt)   │
                     │  → Component-wise + renorm│
                     └──────────────────────────┘
```

### 6.1 Stage 1: Artifact Detector (Z-Score + Velocity)

**Purpose:** Detect and remove tracking spikes — frames where the motion capture system lost track and produced non-physiological position jumps.

```
Algorithm: detect_artifact_gaps()
  1. Compute frame-to-frame velocity: vel[t] = (pos[t+1] - pos[t]) / dt
  2. Compute session-wide statistics: mean(vel), std(vel)
  3. Compute Z-scores: z[t] = |vel[t] - mean(vel)| / std(vel)
  4. Flag frames where EITHER:
     a. |vel[t]| > velocity_limit        (absolute threshold)
     b. z[t] > zscore_threshold          (statistical threshold)
  5. Mark BOTH the frame before AND after each spike (transition corrupts both)
  6. Replace flagged frames with NaN
  7. Interpolate NaN gaps using PCHIP (Piecewise Cubic Hermite Interpolating Polynomial)
```

**Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `velocity_limit` | 5000.0 mm/s | Absolute velocity threshold (≈ 5 m/s — very fast for body markers) |
| `zscore_threshold` | 5.0 | Statistical outlier threshold (5σ catches extreme outliers) |
| `stage1_interpolation_method` | `pchip` | How flagged frames are replaced |

**Why PCHIP interpolation?** PCHIP (Piecewise Cubic Hermite) preserves monotonicity and avoids the Runge's phenomenon (oscillation) that can occur with standard cubic splines at sharp transitions. It produces C1-continuous replacements that blend naturally with surrounding data.

### 6.2 Stage 2: Hampel Filter (Sliding Window Median)

**Purpose:** Remove remaining statistical outliers that passed Stage 1 — these are milder artifacts that don't exceed the velocity threshold but are inconsistent with their local neighborhood.

```
Algorithm: apply_hampel_filter()
  For each frame t:
    1. Define window: [t - half_window, t + half_window]
    2. Compute window median: med = median(window_data)
    3. Compute MAD: mad = median(|window_data - med|)
    4. Convert MAD to σ: σ = mad / 0.6745  (for normal distribution)
    5. IF |signal[t] - med| > n_sigma × σ:
       Replace signal[t] with med
       Mark as outlier
```

**Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `hampel_window` | 5 | Sliding window size in frames |
| `hampel_n_sigma` | 3.0 | Number of σ for outlier threshold |

**Why the Hampel filter?** It's a non-linear filter that acts as a "surgical snipper" — it only modifies frames that deviate significantly from their neighbors, leaving smooth motion untouched. The sliding window of 5–7 frames covers ~42–58 ms at 120 Hz, which is short enough to preserve 5–10 Hz dance dynamics while catching single-frame artifacts.

### 6.3 Stage 3: Adaptive Low-Pass (Winter's Residual Analysis + Butterworth)

**Purpose:** Remove high-frequency measurement noise while preserving the true motion signal. The cutoff frequency is determined **per-joint and per-body-region** using Winter's residual analysis.

#### Winter's Residual Analysis

This method objectively determines the optimal low-pass cutoff frequency by analyzing how much "information" is lost at each candidate frequency:

```
Algorithm: winter_residual_analysis()
  1. For each candidate cutoff fc from fmin to fmax Hz:
     a. Design a 2nd-order Butterworth low-pass filter at fc
     b. Apply zero-phase filtering: x_filtered = filtfilt(b, a, signal)
     c. Compute residual: r = signal - x_filtered
     d. Compute RMS of residual: rms[fc] = sqrt(mean(r²))

  2. The RMS curve decreases as fc increases (more signal passes through)
     At some point, the curve flattens — further increasing fc captures only noise

  3. Find the "knee point" — the lowest fc where RMS stabilizes:
     a. Strict knee: lowest fc where rms ≤ 1.05 × rms[fmax]
     b. Relaxed knee: lowest fc where rms ≤ 1.10 × rms[fmax]
     c. Diminishing returns: fc with largest relative RMS drop

  4. Select final cutoff from candidates (prefer lowest to maximize smoothing)
```

#### Smart Bias (Per-Region Weighting)

Different body regions have different frequency content. The pipeline uses **fixed per-region cutoffs** informed by biomechanical literature, with Winter analysis used for validation:

| Body Region | Joints | Fixed Cutoff | Rationale |
|-------------|--------|-------------|-----------|
| **Trunk** | Pelvis, Spine, Hips | 6 Hz | Core stability — Winter (2009) gait standard |
| **Head** | Head, Neck | 8 Hz | Head dynamics — preserves vestibular movements |
| **Upper Proximal** | Shoulder, Upper Arm | 8 Hz | Arm swings and reaches |
| **Upper Distal** | Forearm, Hand, Fingers | 12 Hz | Fast hand flicks (Gaga dance) |
| **Lower Proximal** | Thigh, Upper Leg | 8 Hz | Leg dynamics |
| **Lower Distal** | Shin, Foot, Toes | 10 Hz | Foot strikes and toe articulation |

When Winter's adaptive analysis suggests a cutoff below the region minimum, a **Smart Bias linear interpolation** blends the Winter result with the biomechanical floor:

```
trust_factor = (min_cutoff_region - 6.0) / (12.0 - 6.0)   [0.0 for trunk, 1.0 for distal]
knee_weight = 0.2 + 0.6 × trust_factor                      [0.2 for trunk, 0.8 for distal]
final_cutoff = diminishing_returns × (1 - knee_weight) + strict_knee × knee_weight
```

#### Butterworth Filter Application

Once the cutoff is determined, the actual filtering uses a **2nd-order zero-phase Butterworth low-pass filter**:

```
Algorithm:
  1. Design filter: b, a = butter(N=2, Wn=fc/(0.5×fs), btype='low')
  2. Apply zero-phase: filtered = filtfilt(b, a, signal)
```

**Why zero-phase (filtfilt)?** Standard filtering introduces a time delay (phase shift). `filtfilt` applies the filter forward and then backward, canceling the phase shift completely. The result has zero group delay — peaks and valleys in the filtered signal align exactly with the original in time. This is essential for computing accurate derivatives.

**Why 2nd-order Butterworth?** Higher orders produce sharper cutoffs but can introduce ringing near discontinuities. 2nd-order provides a gentle rolloff that's appropriate for biomechanical signals, following Winter (2009).

### 6.4 Quaternion Median Filter

**Purpose:** Remove quaternion "flipping" artifacts — frames where the quaternion suddenly jumps to the opposite hemisphere (e.g., 0° to 360°).

```
Algorithm: apply_quaternion_median_filter()
  For each joint:
    1. Apply scipy.signal.medfilt to each component (qx, qy, qz, qw) independently
       with kernel_size=5 (sliding window median)
    2. Renormalize to unit length: q = q / ||q||
```

**Key design decision:** Low-pass filtering is NOT applied to quaternions because Butterworth filtering does not respect the quaternion manifold (SO(3)). Savitzky-Golay smoothing of quaternions is deferred to Step 06 where it's applied with proper renormalization.

**Parameter:** `quaternion_window_size = 5`

---

## 7. Step 05 — Reference Detection (T-Pose)

**Notebook:** `05_reference_detection.ipynb`
**Source:** `src/reference.py`
**Input:** `step_04_filtering/{RUN_ID}__filtered.parquet`, forwarded `kinematics_map.json`
**Output:** `step_05_reference/{RUN_ID}__reference_map.json`, forwarded `kinematics_map.json`

### What it does

Detects the static reference pose (T-pose) at the beginning of the recording and computes the average quaternion for each joint during that window. This reference is used in Step 06 to "zero" all orientations relative to the neutral standing position.

### 7.1 Static Window Detection

The algorithm searches the first `ref_search_sec` seconds of the recording for the most quiescent (motionless) window:

```
Algorithm: detect_static_reference()
  1. Define search region: first ref_search_sec seconds (default: 8s)
  2. For each frame t in the search region:
     a. For each visualization joint j:
        - Compute differential rotation: dq = inv(q_local[t]) × q_local[t+1]
        - Convert to rotation vector: rv = dq.as_rotvec()
        - Compute angular velocity magnitude: |rv| / dt (rad/s)
     b. motion[t] = median of angular velocities across visualization joints
  3. Slide a window of ref_window_sec (default: 1.0s) with step_sec (default: 0.1s):
     For each window position:
        - mean_motion = mean(motion within window)
        - std_motion = std(motion within window)
        - IF mean_motion < motion_thr_low AND std_motion < motion_thr_std:
          → ACCEPT (first window meeting strict criteria)
        - ELSE track the window with minimum mean_motion as fallback
  4. Return: ref_start, ref_end, method (criteria/fallback), metrics
```

**Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `ref_search_sec` | 8.0 s | How far into the recording to search |
| `ref_window_sec` | 1.0 s | Duration of the reference window |
| `static_search_step_sec` | 0.1 s | Step size for sliding window search |
| `motion_thr_low` | 0.3 rad/s | Mean motion threshold for "static" |
| `motion_thr_std` | 0.15 rad/s | Motion variability threshold for "static" |

**Why median of joint velocities?** Median is robust to a single noisy joint. If one joint has a tracking glitch during an otherwise static period, the median still correctly identifies it as static.

### 7.2 Reference Quaternion Computation (Markley Mean)

Once the static window is identified, the reference quaternion for each joint is computed using the **Markley mean quaternion** — the maximum-likelihood estimate of the average orientation:

```
Algorithm: markley_mean_quat()
  1. Collect all valid quaternions Q within the reference window
  2. Normalize and enforce temporal continuity
  3. Build the 4×4 accumulator matrix: A = Σ(q × qᵀ)
  4. Compute eigendecomposition: eigenvalues, eigenvectors = eigh(A)
  5. The mean quaternion = eigenvector corresponding to the largest eigenvalue
  6. Enforce scalar-positive convention: if qw < 0, flip
```

**Why Markley mean instead of simple averaging?** Quaternions cannot be averaged by component-wise mean because they live on a curved manifold (S³). The Markley method finds the quaternion closest to all samples in a geodesic sense — it minimizes the sum of squared angular distances. Simple averaging would produce a sub-unit quaternion biased toward the origin.

### 7.3 Reference Quality Assessment

The quality of the reference pose is assessed by checking how consistent the orientation was during the reference window:

```
For each visualization joint:
  1. Compute relative rotation from reference: qd = inv(q_ref) × q_local[within window]
  2. Convert to rotation vector: rv = Rotation(qd).as_rotvec()
  3. Compute magnitude of deviation: |rv|
  4. identity_error = mean(|rv|)   ← How far each frame was from the reference
  5. ref_std = std(|rv|)            ← How variable the pose was
```

**Quality metrics:**
- `identity_error_ref_med`: Median identity error across joints (should be near zero)
- `ref_quality_score`: Median std of rotation vector magnitude (should be < 0.03 rad)

### 7.4 Output: reference_map.json

The reference pose is stored as a flat JSON dictionary:

```json
{
  "Hips__qx": 0.0012,
  "Hips__qy": -0.0034,
  "Hips__qz": 0.0001,
  "Hips__qw": 0.9999,
  "Spine__qx": 0.0015,
  ...
}
```

---

## 8. Step 06 — Kinematics (Master Feature Computation)

**Notebook:** `06_ultimate_kinematics.ipynb`
**Sources:** `src/angular_velocity.py`, `src/com_engine.py`, `src/kinematic_repair.py`, `src/euler_isb.py`
**Input:** `step_04_filtering/{RUN_ID}__filtered.parquet`, `step_05_reference/{RUN_ID}__reference_map.json`, `kinematics_map.json`
**Output:** `step_06_kinematics/{RUN_ID}__kinematics_master.parquet`, `{RUN_ID}__validation_report.json`

### What it does

This is the core computation step. It computes all kinematic features from the cleaned and referenced data. For a detailed description of each output feature, see [`KINEMATIC_FEATURES_README.md`](./KINEMATIC_FEATURES_README.md).

### 8.1 Root-Relative Position Computation

```
For each segment's position columns (px, py, pz):
  pos_rel[t] = pos_world[t] - pos_root[t]
```

Where `pos_root` is the Hips (or Pelvis) position. This removes global translation, isolating the body's internal postural configuration.

### 8.2 Dual-Track Quaternion Processing

Two parallel quaternion tracks are computed for each joint:

**Track A — Raw Relative (smoothed):**
```
1. Compute hierarchical quaternion: q_rel = inv(q_parent) × q_child
   (For root joints: q_rel = q_global)
2. Unroll: enforce temporal continuity (flip if dot < 0)
3. Smooth each component (qx, qy, qz, qw) with Savitzky-Golay filter
4. Renormalize to unit length: q = q / ||q||
```

**Track B — Zeroed Relative (T-pose normalized):**
```
1. Compute reference relative quaternion:
   q_ref_rel = inv(q_ref_parent) × q_ref_child
2. Subtract reference: q_zeroed = inv(q_ref_rel) × q_raw_smooth
3. Renormalize
```

### 8.3 Angular Velocity (Quaternion Logarithm Method)

```
For each frame t:
  1. dR = inv(R(t)) × R(t+1)           [body-local frame differential rotation]
  2. rotvec_delta = dR.as_rotvec()       [logarithm map to Lie algebra so(3)]
  3. ω(t) = rotvec_delta / dt            [rad/s]
  4. Convert to degrees: ω_deg = degrees(ω)
```

### 8.4 Angular Acceleration (SavGol Derivative of ω)

```
α(t) = d(ω)/dt = SavGol(ω, window=W_LEN, polyorder=3, deriv=1, delta=dt)
```

Applied component-wise to ωx, ωy, ωz.

### 8.5 Linear Velocity and Acceleration (SavGol Derivatives)

```
vel(t) = SavGol(pos_rel, window=W_LEN, polyorder=3, deriv=1, delta=dt)
acc(t) = SavGol(pos_rel, window=W_LEN, polyorder=3, deriv=2, delta=dt)
```

### 8.6 Rotation Vector and Rotation Magnitude

```
rotvec(t) = Rotation(q_zeroed(t)).as_rotvec()     [rad, 3D vector]
rotmag(t) = degrees(||rotvec(t)||₂)                [deg, scalar]
```

### 8.7 Euler Angles

```
Axial chain (Hips, Spine, Spine1, Neck, Head): euler = R(q_zeroed).as_euler('ZYX')
Limbs (all others):                             euler = R(q_zeroed).as_euler('XYZ')
```

### 8.8 Whole-Body Center of Mass

Computed using the de Leva (1996) 16-segment anthropometric model. See `KINEMATIC_FEATURES_README.md` for full details.

### 8.9 Artifact Detection Flags

Per-frame boolean flags based on:
- Rotation magnitude > 140°
- Angular velocity > 800 deg/s
- Linear velocity > 3000 mm/s (teleportation detector)

### 8.10 Surgical Repair (Optional)

When `step_06.enforce_cleaning = true`, joints/segments with CRITICAL outliers undergo targeted repair:
- **Angular outliers:** SLERP interpolation at critical frames on raw-relative quaternions, then re-derive ω, α, and zeroed quantities.
- **Linear outliers:** PCHIP interpolation at critical frames on root-relative positions, then re-derive v, a.

### 8.11 NaN Integrity Guard

Before export, the pipeline checks for remaining NaN values:
- **0% NaN:** `CLEAN` — export as-is
- **< 0.1% NaN:** `MINOR` — fill with linear interpolation + forward/backward fill
- **> 0.1% NaN:** `CRITICAL` — export with warning, offending columns logged

### 8.12 Quaternion Continuity Enforcement

A final global pass checks ALL quaternion columns in the master DataFrame. For each quaternion group, if `dot(q[t-1], q[t]) < 0`, the quaternion is flipped. This prevents hemisphere jumps from surviving into the final Parquet.

### 8.13 Parquet Export with Metadata

The master DataFrame is written to Parquet using PyArrow with custom metadata injected into the schema (run_id, subject_id, pipeline_version, CoM coverage, NaN status, etc.).

---

## 9. Step 08 — Engineering Physical Audit

**Notebook:** `08_engineering_physical_audit.ipynb`
**Source:** `src/utils_nb07.py`
**Input:** `step_06_kinematics/{RUN_ID}__kinematics_master.parquet`, `{RUN_ID}__validation_report.json`
**Output:** Audit report with structural integrity, kinematic extremes, and SNR analysis

### What it does

Performs a post-hoc engineering audit of the master kinematics data. This is a read-only validation step that does not modify data. It checks:

1. **Structural integrity:** Column completeness, data types, NaN patterns
2. **Kinematic extremes:** Maximum angular velocities, accelerations, ROM per joint
3. **SNR analysis:** Signal-to-noise ratio assessment
4. **Bone length QC:** Consistency of virtual bone lengths across the recording

### Bone Length Quality Control

Checks that the Euclidean distance between connected joints remains consistent over time:

```
Algorithm: bone_length_qc()
  For each bone (parent → child):
    1. Compute bone length at each frame: L[t] = ||pos_child[t] - pos_parent[t]||₂
    2. Compute statistics: median, mean, std, CV = std/mean
    3. Compute P95 absolute deviation from median
    4. Compute max frame-to-frame jump

  Thresholds:
    - CV > 2% (5% for alert, 3.5% for short segments) → WARN/ALERT
    - Max jump > 30 mm → ALERT
    - P95 absolute deviation > 10 mm → WARN
```

**Spine Whitelist:** Short segments (Hips→Spine, Neck→Head, Spine→Spine1) have a relaxed CV threshold of 3.5% because their short inter-marker distance amplifies relative noise.

---

## 10. Quality Control Gate System

The pipeline implements a multi-gate quality control system. Each gate evaluates a specific aspect of data quality and produces a PASS/REVIEW/REJECT status.

| Gate | Step | Aspect | Key Metrics |
|------|------|--------|-------------|
| **Gate 2** | Step 02-03 | Temporal quality | Sample jitter (ms), interpolation fallback rate (%) |
| **Gate 3** | Step 04 | Signal filtering | Winter knee-point found, cutoff frequency validity, PSD preservation |
| **Gate 4** | Step 06 | Kinematics integrity | Quaternion norm error, ISB Euler compliance, velocity alignment |
| **Gate 5** | Step 06-08 | Physiological validity | Bone length CV, omega P99, ROM vs anatomical limits |

### Health Score

A composite health score (0–100) is computed from weighted gate metrics:

```
Health = 25% × missing_score + 25% × ref_score + 25% × omega_score + 25% × bone_score
```

If the reference detection used a fallback method, the health score is capped at `health_fallback_cap` (default: 59) to signal reduced confidence.

---

## 11. Pipeline Orchestration

**Script:** `run_pipeline.py`

The `PipelineRunner` class automates processing of single or batch CSV files:

### Execution flow for each CSV

```
1. Update config/config_v1.yaml with:
   - current_csv path
   - subject_id, subject_height_cm, subject_mass_kg (from registry)

2. Execute notebooks in sequence via Papermill:
   01 → 02 → 03 → 04 → 05 → 06 → 08

3. Verify outputs exist in derivatives/

4. Generate batch summary report (JSON)
```

### CLI usage

```bash
python run_pipeline.py --single "data/671/T1/file.csv"    # Single file
python run_pipeline.py --json batch_configs/batch.json     # JSON batch config
python run_pipeline.py --auto-discover                      # All CSVs in data/
python run_pipeline.py --dry-run                            # Simulate without executing
```

### Papermill integration

Each notebook receives injected parameters (`RUN_ID`, `current_csv`) via Papermill, ensuring the correct data file is processed even in batch mode. Notebooks are executed with a 600-second (10-minute) timeout.

---

## 12. Configuration Reference

All parameters are defined in `config/config_v1.yaml`. Here is the complete reference:

### General

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fs_target` | 120.0 | Target uniform sampling rate (Hz) |
| `crop_sec` | [10.0, 110.0] | Time window to process (seconds from recording start) |
| `min_run_seconds` | 5.0 | Minimum recording duration to process (seconds) |
| `data_dir` | `data` | Root directory for raw data |
| `derivatives_dir` | `derivatives` | Root directory for pipeline outputs |

### Smoothing & Derivatives

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sg_window_sec` | 0.175 | Savitzky-Golay window duration (seconds) |
| `sg_polyorder` | 3 | Savitzky-Golay polynomial order |
| `deriv_method` | `savgol` | Derivative computation method |
| `sg_targets` | `derivatives_only` | What to apply SavGol to |

### Angular Velocity

| Parameter | Default | Description |
|-----------|---------|-------------|
| `omega_method` | `quat_log` | Angular velocity method (quat_log, 5pt, central) |
| `omega_frame` | `child_body` | Reference frame for ω (child_body = local) |

### Gap Filling

| Parameter | Default | Description |
|-----------|---------|-------------|
| `missing_policy_pos` | `interp_linear_or_spline` | Position gap fill method |
| `missing_policy_quat` | `interp_slerp` | Quaternion gap fill method |
| `max_gap_pos_sec` | 1.0 | Maximum position gap to fill (seconds) |
| `max_gap_quat_sec` | 0.25 | Maximum quaternion gap to fill (seconds) |

### Filtering (3-Stage)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `filtering.method` | `3_stage` | Filtering pipeline type |
| `filtering.velocity_limit` | 5000.0 | Stage 1: velocity spike threshold (mm/s) |
| `filtering.zscore_threshold` | 5.0 | Stage 1: Z-score outlier threshold |
| `filtering.hampel_window` | 5 | Stage 2: Hampel sliding window size |
| `filtering.hampel_n_sigma` | 3.0 | Stage 2: Hampel outlier sigma threshold |
| `filtering.cutoff_hz` | 8.0 | Stage 3: global default cutoff (Hz) |
| `filtering.winter_fmin` | 1.0 | Stage 3: Winter search range minimum |
| `filtering.winter_fmax` | 20.0 | Stage 3: Winter search range maximum |
| `filtering.per_joint_winter` | true | Stage 3: per-joint adaptive cutoff |
| `filtering.apply_quaternion_median_filter` | true | Apply medfilt to quaternions |
| `filtering.quaternion_window_size` | 5 | Quaternion medfilt window |
| `filtering.stage1_interpolation_method` | `pchip` | How Stage 1 gaps are filled |

### Reference Detection

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ref_search_sec` | 8.0 | How far into recording to search for static pose |
| `ref_window_sec` | 1.0 | Duration of reference window |
| `static_search_step_sec` | 0.1 | Step size for sliding window search |
| `motion_thr_low` | 0.3 | Mean motion threshold for "static" (rad/s) |
| `motion_thr_std` | 0.15 | Motion variability threshold (rad/s) |
| `ref_anchor` | `static_detection_pre_crop` | Reference detection strategy |

### Quality Control Thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `thresh.bone_cv_warn` | 0.02 | Bone length CV warning threshold (2%) |
| `thresh.bone_cv_alert` | 0.05 | Bone length CV alert threshold (5%) |
| `thresh.bone_max_jump_alert_m` | 0.03 | Max bone length jump for alert (30 mm) |
| `thresh.bone_p95_abs_dev_warn_m` | 0.01 | P95 bone deviation for warning (10 mm) |
| `thresh.omega_p99_warn` | 30.0 | Angular velocity P99 warning (rad/s) |
| `thresh.omega_p99_alert` | 60.0 | Angular velocity P99 alert (rad/s) |
| `thresh.missing_warn_frac` | 0.05 | Missing data warning fraction (5%) |
| `thresh.missing_alert_frac` | 0.10 | Missing data alert fraction (10%) |
| `thresh.ref_quality_std_rad_warn` | 0.03 | Reference quality warning (rad) |
| `thresh.ref_quality_std_rad_alert` | 0.05 | Reference quality alert (rad) |

### Skeleton & Export

| Parameter | Default | Description |
|-----------|---------|-------------|
| `exclude_groups` | [Fingers, Toes] | Segment groups to exclude |
| `joints_viz` | [Hips, Spine, ...] | Core visualization joints |
| `required_joints` | [Hips, Spine, Head] | Joints that MUST be present |
| `shortest_rotation` | true | Enforce shortest-path quaternion |
| `rotation_rep` | `rotvec_relative_reference` | Rotation representation |
| `step_06.enforce_cleaning` | false | Enable surgical repair |

---

## 13. File Naming & Directory Convention

### Directory structure

```
derivatives/
├── step_01_parse/
│   └── {RUN_ID}__parsed_run.parquet
├── step_02_preprocess/
│   ├── {RUN_ID}__preprocessed.parquet
│   └── {RUN_ID}__kinematics_map.json
├── step_03_resample/
│   ├── {RUN_ID}__resampled.parquet
│   └── {RUN_ID}__kinematics_map.json        (forwarded)
├── step_04_filtering/
│   └── {RUN_ID}__filtered.parquet
├── step_05_reference/
│   ├── {RUN_ID}__reference_map.json
│   └── {RUN_ID}__kinematics_map.json        (forwarded)
└── step_06_kinematics/
    ├── {RUN_ID}__kinematics_master.parquet   ← Final output
    └── {RUN_ID}__validation_report.json
```

### RUN_ID convention

`RUN_ID` is the CSV filename stem (without extension):

```
Example: 671_T1_P2_R1_Take 2025-12-25 10.51.23 AM_005
  │   │  │  │
  │   │  │  └─ Recording number
  │   │  └──── Protocol number
  │   └─────── Time point (session)
  └─────────── Subject ID
```

---

## 14. References

1. **Winter, D. A.** (2009). *Biomechanics and motor control of human movement*. 4th ed. Wiley. — Residual analysis for cutoff selection, biomechanical filtering standards.

2. **de Leva, P.** (1996). Adjustments to Zatsiorsky-Seluyanov's segment inertia parameters. *J. Biomechanics*, 29(9), 1223–1230. — Segment mass fractions for CoM.

3. **Muller, P., Roithner, R., & Gatterer, H.** (2017). On the angular velocity estimation from orientation data. — Quaternion logarithm method.

4. **Sola, J.** (2017). Quaternion kinematics for the error-state Kalman filter. — Quaternion kinematics.

5. **Savitzky, A. & Golay, M. J. E.** (1964). Smoothing and differentiation of data by simplified least squares procedures. *Anal. Chem.*, 36(8), 1627–1639. — SavGol filter.

6. **Wu, G. et al.** (2002, 2005). ISB recommendation on definitions of joint coordinate systems. *J. Biomechanics*. — Euler angle standards.

7. **Markley, F. L. et al.** (2007). Averaging quaternions. *J. Guidance, Control, and Dynamics*, 30(4), 1193–1197. — Markley mean quaternion.

8. **Robertson, D. G. E.** (2014). *Research Methods in Biomechanics*. 2nd ed. — Per-region cutoff frequency recommendations.

9. **Pearson, K. L.** (1901). On lines and planes of closest fit. *Phil. Mag.*, 2(11), 559–572. — MAD-based outlier detection.

---

*Document generated for the Gaga Motion Analysis Pipeline. Last updated: 2026-02-17.*
