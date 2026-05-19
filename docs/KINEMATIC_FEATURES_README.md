# Kinematic Features Reference — Master Kinematics Parquet

> **Pipeline:** Gaga Motion Analysis Pipeline (Step 06 — Ultimate Kinematics)
> **Output file:** `derivatives/step_06_kinematics/{RUN_ID}__kinematics_master.parquet`
> **Source code:** `notebooks/06_ultimate_kinematics.ipynb`, `src/angular_velocity.py`, `src/com_engine.py`, `src/pipeline.py`

This document is the authoritative reference for every kinematic feature stored in the master Parquet file. Each feature is described with its **physical meaning**, **mathematical computation**, **units**, and **downstream use cases** (ML/HMM, RQA, clinical reporting).

---

## Table of Contents

1. [Overview & Naming Convention](#1-overview--naming-convention)
2. [Metadata & Time Axis](#2-metadata--time-axis)
3. [Category A — Orientation (Posture) Features](#3-category-a--orientation-posture-features)
4. [Category B — Angular Kinematics Features](#4-category-b--angular-kinematics-features)
5. [Category C — Linear Kinematics Features](#5-category-c--linear-kinematics-features)
6. [Category D — Whole-Body Center of Mass (WBCoM)](#6-category-d--whole-body-center-of-mass-wbcom)
7. [Category E — Euler Angles](#7-category-e--euler-angles)
8. [Category F — Artifact & Quality Flags](#8-category-f--artifact--quality-flags)
9. [Smoothing & Derivative Method](#9-smoothing--derivative-method)
10. [Reference Pose (T-Pose Zeroing)](#10-reference-pose-t-pose-zeroing)
11. [Coordinate Frame & Conventions](#11-coordinate-frame--conventions)
12. [Joint & Segment Inventory](#12-joint--segment-inventory)
13. [Configuration Parameters](#13-configuration-parameters)
14. [References](#14-references)

---

## 1. Overview & Naming Convention

Every column in `kinematics_master.parquet` follows the pattern:

```
{entity}__{feature_group}_{axis_or_qualifier}
```

| Token | Meaning | Examples |
|-------|---------|----------|
| `{entity}` | Joint or segment name from the skeleton hierarchy | `Hips`, `LeftArm`, `RightFoot` |
| `__` | Double-underscore separator | — |
| `{feature_group}` | Semantic block (see categories below) | `raw_rel_q`, `zeroed_rel_omega`, `lin_vel_rel` |
| `_{axis}` | Cartesian component or scalar qualifier | `x`, `y`, `z`, `w`, `mag` |

**Example:** `LeftArm__zeroed_rel_omega_x` = angular velocity around the X-axis of the LeftArm joint, in the zeroed (T-pose normalized) reference frame.

---

## 2. Metadata & Time Axis

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `time_s` | float64 | seconds | Monotonic time axis, resampled to a uniform grid at `FS_TARGET` Hz (default 120 Hz). Starts from the cropped window beginning. |

### Parquet-Embedded Metadata (PyArrow schema)

The following are stored as key-value pairs in the Parquet file's schema metadata:

| Key | Description |
|-----|-------------|
| `run_id` | Unique recording session identifier |
| `subject_id` | Subject identifier from the registry |
| `subject_height_cm` | Subject height in cm (or empty if unknown) |
| `subject_mass_kg` | Subject mass in kg (or empty if unknown) |
| `pipeline_version` | Pipeline version string (e.g., `v3.0_com_enhanced`) |
| `processing_timestamp` | ISO timestamp of when the file was generated |
| `com_segments_available` | Number of body segments used for CoM computation |
| `com_mass_coverage_pct` | Percentage of total body mass covered by available segments |
| `nan_guard_status` | `CLEAN`, `MINOR`, or `CRITICAL` — NaN integrity status |
| `metadata_quality` | `SUBJECT_SPECIFIC`, `UNRELIABLE_COM_DEFAULT_ANTHRO`, or `MISSING_ANTHRO` |
| `derivative_method` | `savgol_chunked` — NaN-safe Savitzky-Golay via contiguous-segment dispatch |
| `chunking_guard` | `true` — confirms NaN-safe chunking is active |
| `sg_window_len` | SavGol window length in samples (e.g., `21`) |
| `sg_polyorder` | SavGol polynomial order (e.g., `3`) |
| `subject_height_source` | `measured`, `mocap_corrected`, or `unknown` |
| `com_reliability_score` | 0.0–1.0 score based on mass coverage (< 0.90 = UNRELIABLE) |
| `com_reliability_flag` | `RELIABLE` or `UNRELIABLE` |
| `euler_standard` | `ISB` — confirms ISB-compliant Euler sequences are used |

---

## 3. Category A — Orientation (Posture) Features

Orientation features describe the **rotational posture** of each joint relative to its parent in the kinematic chain, both in raw form and zeroed to a static T-pose reference.

### A1. Raw Relative Quaternions

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{joint}__raw_rel_qx` | unitless | X component of the hierarchical quaternion (parent → child) |
| `{joint}__raw_rel_qy` | unitless | Y component |
| `{joint}__raw_rel_qz` | unitless | Z component |
| `{joint}__raw_rel_qw` | unitless | W (scalar) component |

**How computed:**

1. For each joint with a parent: `q_rel = inv(q_parent) * q_child` — the rotation from parent's frame to child's frame.
2. For root joints (e.g., Hips with no parent): `q_rel = q_global` (the global orientation).
3. The quaternion sequence is **unrolled** (temporal continuity enforced by flipping signs when `dot(q[t-1], q[t]) < 0` to prevent hemisphere jumps on SO(3)).
4. Each component is individually **smoothed** with a Savitzky-Golay filter (window = `SG_WINDOW_SEC * FS`, polynomial order = `SG_POLYORDER`).
5. After smoothing, quaternions are **renormalized** to unit length: `q = q / ||q||`.

**What it represents:** The smoothed, hierarchical orientation of each joint relative to its immediate parent segment. This encodes the joint's 3D rotational state at each frame, without reference pose subtraction. Useful as a comparison track against the zeroed quaternions for validation.

**Format:** SciPy `xyzw` convention (Hamilton scalar-last).

---

### A2. Zeroed (T-Pose Normalized) Quaternions

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{joint}__zeroed_rel_qx` | unitless | X component of the T-pose zeroed quaternion |
| `{joint}__zeroed_rel_qy` | unitless | Y component |
| `{joint}__zeroed_rel_qz` | unitless | Z component |
| `{joint}__zeroed_rel_qw` | unitless | W (scalar) component |

**How computed:**

1. Compute the **reference relative quaternion** from the static T-pose:
   - If joint has a parent: `q_rel_ref = inv(q_ref_parent) * q_ref_child`
   - If root joint: `q_rel_ref = q_ref_global`
2. Subtract the reference by left-multiplying with the inverse:
   ```
   q_zeroed(t) = inv(q_rel_ref) * q_raw_smooth(t)
   ```
3. Renormalize to unit length.

**What it represents:** The rotation of the joint **away from its T-pose neutral position** at each frame. When the subject stands in perfect T-pose, all zeroed quaternions equal the identity `[0, 0, 0, 1]`. Any deviation indicates joint movement. This is the **primary orientation representation for ML/HMM analysis** because it removes the arbitrary static offset of each joint's rest position.

---

### A3. Zeroed Rotation Vector

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{joint}__zeroed_rel_rotvec_x` | radians | X component of the rotation vector |
| `{joint}__zeroed_rel_rotvec_y` | radians | Y component |
| `{joint}__zeroed_rel_rotvec_z` | radians | Z component |

**How computed:**

```
rotvec(t) = RotationToRotvec(q_zeroed(t))
```

Using SciPy's `Rotation.from_quat(q_zeroed).as_rotvec()`. The rotation vector is the product of the unit rotation axis and the rotation angle: `rotvec = angle * axis`, where `angle = 2 * arccos(|qw|)` and `axis = [qx, qy, qz] / sin(angle/2)`.

**What it represents:** A 3D vector whose **direction** is the axis of rotation from T-pose and whose **magnitude** is the angle of rotation in radians. Unlike quaternions (which live on a 4D hypersphere), rotation vectors live in Euclidean R³, making them ideal for:
- **HMM state features** (continuous, unbounded)
- **PCA / dimensionality reduction** (linear operations are meaningful)
- **Clustering** (Euclidean distance is a valid metric)

---

### A4. Zeroed Rotation Magnitude (Geodesic Distance)

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{joint}__zeroed_rel_rotmag` | degrees | Scalar geodesic distance from T-pose |

**How computed:**

```
rotmag(t) = degrees( ||rotvec(t)||₂ )
```

Equivalently: `rotmag = degrees(2 * arccos(|qw|))`, which is the geodesic distance on SO(3) from the identity rotation.

**What it represents:** A **single scalar** summarizing how far the joint has rotated from its T-pose position, regardless of direction. A `rotmag` of 0° means the joint is exactly at T-pose; 90° means a quarter-turn deviation.

**Use cases:**
- **RQA (Recurrence Quantification Analysis):** Rotationally invariant input signal.
- **Complexity indices:** Threshold-based state counting.
- **Clinical Range of Motion (ROM):** Direct comparison to anatomical limits.

---

## 4. Category B — Angular Kinematics Features

Angular kinematics features describe the **rate and acceleration of rotational change** at each joint.

### B1. Angular Velocity (ω)

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{joint}__zeroed_rel_omega_x` | deg/s | Angular velocity around X-axis (zeroed track) |
| `{joint}__zeroed_rel_omega_y` | deg/s | Angular velocity around Y-axis |
| `{joint}__zeroed_rel_omega_z` | deg/s | Angular velocity around Z-axis |
| `{joint}__zeroed_rel_omega_mag` | deg/s | Angular velocity magnitude (Euclidean norm) |
| `{joint}__raw_rel_omega_x` | deg/s | Angular velocity around X-axis (raw track) |
| `{joint}__raw_rel_omega_y` | deg/s | Angular velocity around Y-axis (raw track) |
| `{joint}__raw_rel_omega_z` | deg/s | Angular velocity around Z-axis (raw track) |

**How computed (Quaternion Logarithm Method — default):**

The primary method is `quaternion_log_angular_velocity()` from `src/angular_velocity.py`, based on Muller et al. (2017) and Sola (2017):

```
For each frame t:
    1. Normalize q(t) and q(t+1) to unit quaternions
    2. Ensure shortest path: if dot(q(t), q(t+1)) < 0, flip q(t+1)
    3. Compute differential rotation: dR = inv(R(t)) * R(t+1)       [body-local frame]
                               or: dR = R(t+1) * inv(R(t))          [global frame]
    4. Convert to rotation vector: rotvec_delta = dR.as_rotvec()
    5. Angular velocity: ω(t) = rotvec_delta / dt                   [rad/s]
    6. Convert to degrees: ω_deg(t) = degrees(ω(t))
```

The last frame is forward-filled from the penultimate frame.

**Magnitude:** `omega_mag(t) = ||[ωx, ωy, ωz]||₂`

**What it represents:** The instantaneous rotational speed and direction of the joint. Computed in the **body-local frame** (default `omega_frame: child_body`), meaning the axes are attached to the moving segment, not the lab.

**Why quaternion logarithm?** This method:
- Respects the manifold structure of SO(3) (no linearization error)
- Is more robust to noise than finite differences
- Avoids numerical issues with very small rotations

**Alternative methods** (configurable via `omega_method`):
- `5pt`: 5-point finite difference stencil with Gaussian-like weighting (noise-resistant)
- `central`: Central finite difference (baseline, 2nd-order accurate)

---

### B2. Angular Acceleration (α)

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{joint}__zeroed_rel_alpha_x` | deg/s² | Angular acceleration around X-axis (zeroed track) |
| `{joint}__zeroed_rel_alpha_y` | deg/s² | Angular acceleration around Y-axis |
| `{joint}__zeroed_rel_alpha_z` | deg/s² | Angular acceleration around Z-axis |
| `{joint}__zeroed_rel_alpha_mag` | deg/s² | Angular acceleration magnitude |
| `{joint}__raw_rel_alpha_x` | deg/s² | Angular acceleration around X-axis (raw track) |
| `{joint}__raw_rel_alpha_y` | deg/s² | Angular acceleration around Y-axis (raw track) |
| `{joint}__raw_rel_alpha_z` | deg/s² | Angular acceleration around Z-axis (raw track) |

**How computed:**

Angular acceleration is the **Savitzky-Golay first derivative of angular velocity**:

```
α(t) = d(ω)/dt ≈ SavGol(ω, window=W_LEN, polyorder=SG_POLYORDER, deriv=1, delta=dt)
```

This is applied component-wise to `ω_x`, `ω_y`, `ω_z` independently. The SavGol filter simultaneously smooths and differentiates, providing better noise rejection than raw finite differences.

**Magnitude:** `alpha_mag(t) = ||[αx, αy, αz]||₂`

**What it represents:** The rate of change of angular velocity — how quickly the joint is speeding up or slowing down its rotation. High angular acceleration indicates rapid changes in movement direction (e.g., jerky transitions, impacts, or dance accents).

---

## 5. Category C — Linear Kinematics Features

Linear kinematics features describe the **translational motion** of each body segment relative to the root segment (Hips/Pelvis).

### C1. Root-Relative Position

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{segment}__lin_rel_px` | mm | X position relative to root segment |
| `{segment}__lin_rel_py` | mm | Y position relative to root segment |
| `{segment}__lin_rel_pz` | mm | Z position relative to root segment |

**How computed:**

```
pos_rel(t) = pos_world(t) - pos_root(t)
```

Where `pos_root` is the 3D world position of the root segment (Hips or Pelvis) at each frame. The subtraction removes global translation (walking, drifting), isolating the body's internal postural configuration.

**What it represents:** The spatial position of each segment in a body-centered coordinate system. The root segment is always at the origin `[0, 0, 0]`. For example, `Head__lin_rel_py` tells you how far above the pelvis the head is.

**Note:** Positions arrive in the input data from OptiTrack in millimeters and are internally converted to meters during earlier pipeline steps (steps 01–04). In the master Parquet, root-relative positions are stored in the unit system inherited from the filtered data (typically mm, verify via inspection of magnitude ranges).

---

### C2. Linear Velocity

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{segment}__lin_vel_rel_x` | mm/s | X velocity component (root-relative) |
| `{segment}__lin_vel_rel_y` | mm/s | Y velocity component |
| `{segment}__lin_vel_rel_z` | mm/s | Z velocity component |
| `{segment}__lin_vel_rel_mag` | mm/s | Velocity magnitude (speed) |

**How computed:**

```
vel(t) = d(pos_rel)/dt ≈ SavGol(pos_rel, window=W_LEN, polyorder=SG_POLYORDER, deriv=1, delta=dt)
```

The Savitzky-Golay derivative is applied axis-by-axis to the root-relative position time series. This simultaneously differentiates and smooths, avoiding the noise amplification of raw finite differences.

**Magnitude:** `vel_mag(t) = ||[vx, vy, vz]||₂`

**What it represents:** How fast each body segment is moving relative to the pelvis. A high `LeftHand__lin_vel_rel_mag` means the hand is swinging quickly, regardless of whether the whole body is translating through space.

---

### C3. Linear Acceleration

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{segment}__lin_acc_rel_x` | mm/s² | X acceleration component (root-relative) |
| `{segment}__lin_acc_rel_y` | mm/s² | Y acceleration component |
| `{segment}__lin_acc_rel_z` | mm/s² | Z acceleration component |
| `{segment}__lin_acc_rel_mag` | mm/s² | Acceleration magnitude |

**How computed:**

```
acc(t) = d²(pos_rel)/dt² ≈ SavGol(pos_rel, window=W_LEN, polyorder=SG_POLYORDER, deriv=2, delta=dt)
```

Second-order Savitzky-Golay derivative of root-relative positions. Computed directly from position (not from velocity) to avoid cascading differentiation noise.

**Magnitude:** `acc_mag(t) = ||[ax, ay, az]||₂`

**What it represents:** The rate of change of segment velocity. High acceleration indicates rapid starts/stops or direction changes — the "punch" or "whip" quality of movement. Directly proportional to the force required to produce the motion (F = m * a).

---

## 6. Category D — Whole-Body Center of Mass (WBCoM)

| Column | Units | Description |
|--------|-------|-------------|
| `wbc_com_x` | mm | Whole-body center of mass, X (root-relative) |
| `wbc_com_y` | mm | Whole-body center of mass, Y (root-relative) |
| `wbc_com_z` | mm | Whole-body center of mass, Z (root-relative) |
| `com_reliability_score` | 0.0–1.0 | Mass coverage fraction; < 0.90 indicates UNRELIABLE WBCoM |

**How computed:**

Implemented in `src/com_engine.py` using the de Leva (1996) anthropometric model (adjusted Zatsiorsky-Seluyanov parameters):

```
For each of 16 body segments:
    1. Identify proximal and distal joint positions from the master data
    2. Compute segment CoM: CoM_seg = pos_proximal + ratio * (pos_distal - pos_proximal)
       where 'ratio' is the segment's proximal CoM ratio from de Leva (1996)
    3. Weight by segment mass fraction: weighted_seg = mass_frac * CoM_seg

Whole-body CoM = Σ(weighted_seg) / Σ(mass_frac_available)
```

### Segment Mass Fractions (de Leva, 1996 — Male)

| Segment | Mass Fraction | Proximal Joint | Distal Joint | CoM Proximal Ratio |
|---------|--------------|----------------|--------------|-------------------|
| Head | 6.94% | Neck | Head | 0.5002 |
| Upper trunk | 15.96% | Spine1 | Neck | 0.5066 |
| Middle trunk | 16.33% | Spine | Spine1 | 0.4502 |
| Lower trunk | 11.17% | Hips | Spine | 0.6115 |
| Upper arm (L/R) | 2.71% each | Arm | ForeArm | 0.5772 |
| Forearm (L/R) | 1.62% each | ForeArm | Hand | 0.4574 |
| Hand (L/R) | 0.61% each | Hand | Hand (terminal) | 0.0 |
| Thigh (L/R) | 14.16% each | UpLeg | Leg | 0.4095 |
| Shank (L/R) | 4.33% each | Leg | Foot | 0.4459 |
| Foot (L/R) | 1.37% each | Foot | ToeBase | 0.4415 |

**Total:** 100.0% body mass across 16 segments.

### Missing-Segment Compensation

When a segment's joints are not available in the data, its mass fraction is **redistributed proportionally** across remaining segments:

```
WBCoM = Σ(m_i * CoM_i) / Σ(m_i)    [sum over available segments only]
```

This ensures the WBCoM never becomes NaN and the effective total mass remains 100%.

**What it represents:** The mass-weighted average position of the entire body relative to the pelvis. WBCoM is a fundamental measure in biomechanics: its trajectory reflects overall balance, postural stability, and movement efficiency. In Gaga movement, shifts in WBCoM relate to weight distribution, grounding, and spatial reach.

---

## 7. Category E — Euler Angles

| Column Pattern | Units | Description |
|----------------|-------|-------------|
| `{joint}__euler_x` | degrees | First Euler angle (rotation order depends on joint) |
| `{joint}__euler_y` | degrees | Second Euler angle |
| `{joint}__euler_z` | degrees | Third Euler angle |

**How computed:**

Decomposition from the zeroed quaternion into ISB-standard Euler angles using joint-specific rotation orders defined in `src/euler_isb.py`:

```
seq = get_euler_sequence(joint_name)   # e.g., 'ZXY' for spine, 'YXY' for shoulder
euler = Rotation.from_quat(q_zeroed).as_euler(seq, degrees=True)
```

| Joint Group | ISB Sequence | Anatomical Meaning |
|-------------|-------------|-------------------|
| Spine/Pelvis/Head (Hips, Spine, Spine1, Neck, Head) | ZXY | Z: Flex/Ext, X: Lat. Bend, Y: Axial Rot. |
| Shoulders (LeftShoulder, RightShoulder) | YXY | Y1: Plane of elev., X: Elevation, Y2: Axial Rot. |
| All other limbs | ZXY | Z: Flex/Ext, X: Ab/Adduction, Y: Int/Ext Rot. |

**What it represents:** Joint angles decomposed into anatomically meaningful planes per ISB recommendations (Wu et al. 2002, 2005). Euler angles are more interpretable than quaternions for clinical reporting (e.g., "the knee is flexed 45°"), but suffer from gimbal lock at extreme angles. The YXY sequence for shoulders prevents gimbal lock during arm elevation.

**Column naming:** `euler_x`, `euler_y`, `euler_z` are positional labels (1st, 2nd, 3rd decomposition angle in the sequence). The physical axis meaning depends on the joint's ISB sequence — consult the table above or the `euler_sequences_used` field in the validation report JSON.

---

## 8. Category F — Artifact & Quality Flags

### F1. Artifact Detection Flags

| Column Pattern | Type | Description |
|----------------|------|-------------|
| `{joint}__is_artifact` | bool | True if frame is flagged as a motion capture artifact |
| `{segment}__is_artifact` | bool | True if frame is flagged (includes linear teleportation) |

**Detection criteria (dual-criteria, threshold-based):**

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Rotation magnitude | > 140° | Near anatomical limits; likely sensor error |
| Angular velocity | > 800 deg/s | Exceeds ballistic human movement; gimbal/sensor issue |
| Linear velocity | > 3000 mm/s | "Teleportation detector" for marker swaps and tracking loss |

A frame is flagged if **any** criterion is exceeded. Joint-level flags combine rotation and angular velocity; segment-level flags additionally include linear velocity.

### F2. Hampel Outlier Flags

| Column Pattern | Type | Description |
|----------------|------|-------------|
| `{joint}__is_hampel_outlier` | bool | Placeholder for Hampel filter outlier flags (computed in Step 04) |
| `{segment}__is_hampel_outlier` | bool | Placeholder (currently all False in Step 06 output) |

---

## 9. Smoothing & Derivative Method

All derivatives and smoothing in the master kinematics pipeline use the **NaN-safe chunked Savitzky-Golay filter** (`chunked_savgol` in `src/filtering.py`), which applies `scipy.signal.savgol_filter` strictly within contiguous segments of finite data. This prevents "NaN bleeding" where the filter window would bridge a data gap and destroy valid data near the gap boundary.

### Chunking Guard (Phase 4)

The `chunked_savgol` function implements three-tier segment handling:

| Tier | Condition | Behavior |
|------|-----------|----------|
| **1 (Full)** | `seg_len >= window_length` | Standard SavGol with nominal window |
| **2 (Reduced)** | `min_window <= seg_len < window_length` | SavGol with window shrunk to largest odd ≤ seg_len |
| **3 (Too short)** | `seg_len < min_window` | Pass-through for deriv=0; NaN for deriv>0 (derivative undefined) |

Where `min_window = polyorder + 2` (forced odd) — the minimum SciPy allows.

### Parameters

| Parameter | Config Key | Default | Description |
|-----------|-----------|---------|-------------|
| Window duration | `sg_window_sec` | 0.175 s | Physical window duration |
| Window length | computed | 21 samples @ 120 Hz | `round(sg_window_sec * FS)`, forced odd, min 5 |
| Polynomial order | `sg_polyorder` | 3 | Degree of fitted polynomial |
| Boundary mode | — | `interp` | How boundaries are handled within each chunk |

### What the SavGol filter is applied to

| Target | Derivative Order | Purpose | Direct? |
|--------|-----------------|---------|---------|
| Raw-relative quaternion components (qx, qy, qz, qw) | 0 (smoothing only) | Noise reduction before kinematic derivation | — |
| Root-relative positions (px, py, pz) | 1 | Linear velocity | Yes |
| Root-relative positions (px, py, pz) | 2 | Linear acceleration | Yes (directly from position, no cascade) |
| Angular velocity (ωx, ωy, ωz) | 1 | Angular acceleration | Yes (directly from ω, no cascade) |

**Quaternion manifold preservation:** After SavGol smoothing of quaternion components (deriv=0), all quaternions are renormalized to unit length (`||q|| = 1`). A manifold guard rejects any row where `||q|| < 0.99` post-renorm.

---

## 10. Reference Pose (T-Pose Zeroing)

The "zeroing" process removes the arbitrary rest-state orientation of each joint, making all joints start from a common identity reference.

### How the reference is computed (Step 05)

1. **Static window detection:** The pipeline searches the first `ref_search_sec` seconds (default 8s) for the most quiescent period — the window with minimum angular velocity variance across all visualization joints.
2. **Reference quaternion extraction:** Within the detected static window (`ref_window_sec` = 1s), the average quaternion per joint is computed.
3. **Stored in:** `{RUN_ID}__reference_map.json` with keys `{joint}__qx`, `{joint}__qy`, `{joint}__qz`, `{joint}__qw`.

### How it's applied in Step 06

For each joint, the hierarchical reference quaternion is computed:
```
q_ref_rel = inv(q_ref_parent) * q_ref_child    (for joints with parents)
q_ref_rel = q_ref_global                        (for root joints)
```

Then the zeroed quaternion at each frame:
```
q_zeroed(t) = inv(q_ref_rel) * q_raw_smooth(t)
```

This means: "What is the rotation of this joint, relative to where it was during the T-pose?"

---

## 11. Coordinate Frame & Conventions

| Property | Convention |
|----------|-----------|
| **Internal frame** | OptiTrack frame (Y-Up, Z-Forward) |
| **Quaternion format** | SciPy `xyzw` (scalar-last / Hamilton) |
| **Hierarchy direction** | `q_rel = inv(parent) * child` |
| **Angular velocity frame** | Body-local (child segment frame) by default (`omega_frame: child_body`) |
| **Position units** | Millimeters (mm) in master Parquet |
| **Angular units** | Degrees for Euler, omega, alpha, rotmag; Radians for rotvec |
| **Time** | Seconds, uniform grid at `FS_TARGET` Hz |

---

## 12. Joint & Segment Inventory

The joints processed depend on the skeleton configuration and `exclude_groups` settings. A typical full-body skeleton (excluding Fingers and Toes) includes:

### Axial Chain
| Joint | Parent | Description |
|-------|--------|-------------|
| Hips | — (root) | Pelvis / root segment |
| Spine | Hips | Lower spine (lumbar) |
| Spine1 | Spine | Mid-spine (thoracic) |
| Neck | Spine1 | Cervical spine |
| Head | Neck | Head |

### Left Upper Limb
| Joint | Parent | Description |
|-------|--------|-------------|
| LeftShoulder | Spine1 | Left clavicle / shoulder girdle |
| LeftArm | LeftShoulder | Left humerus (upper arm) |
| LeftForeArm | LeftArm | Left radius/ulna (forearm) |
| LeftHand | LeftForeArm | Left wrist / hand |

### Right Upper Limb
| Joint | Parent | Description |
|-------|--------|-------------|
| RightShoulder | Spine1 | Right clavicle / shoulder girdle |
| RightArm | RightShoulder | Right humerus (upper arm) |
| RightForeArm | RightArm | Right radius/ulna (forearm) |
| RightHand | RightForeArm | Right wrist / hand |

### Left Lower Limb
| Joint | Parent | Description |
|-------|--------|-------------|
| LeftUpLeg | Hips | Left femur (thigh) |
| LeftLeg | LeftUpLeg | Left tibia/fibula (shank) |
| LeftFoot | LeftLeg | Left foot (ankle joint) |

### Right Lower Limb
| Joint | Parent | Description |
|-------|--------|-------------|
| RightUpLeg | Hips | Right femur (thigh) |
| RightLeg | RightUpLeg | Right tibia/fibula (shank) |
| RightFoot | RightLeg | Right foot (ankle joint) |

---

## 13. Configuration Parameters

Key parameters that control the kinematic feature computation (from `config/config_v1.yaml`):

| Parameter | Value | Description |
|-----------|-------|-------------|
| `fs_target` | 120.0 Hz | Uniform sampling rate for the resampled grid |
| `sg_window_sec` | 0.175 s | Savitzky-Golay smoothing window duration |
| `sg_polyorder` | 3 | Savitzky-Golay polynomial order |
| `omega_method` | `quat_log` | Angular velocity computation method (quaternion logarithm) |
| `omega_frame` | `child_body` | Angular velocity reference frame (body-local) |
| `deriv_method` | `savgol` | Derivative computation method |
| `sg_targets` | `derivatives_only` | Apply SavGol to derivatives only (not raw signals) |
| `rotation_rep` | `rotvec_relative_reference` | Rotation representation choice |
| `shortest_rotation` | `true` | Enforce shortest-path quaternion continuity |
| `crop_sec` | `[10.0, 110.0]` | Time window to export (seconds from recording start) |
| `step_06.enforce_cleaning` | `false` | Whether to apply surgical repair on critical outliers |

### Surgical Repair (when `enforce_cleaning: true`)

When enabled, joints/segments with CRITICAL outliers undergo targeted repair:
- **Angular outliers:** SLERP interpolation on the raw-relative quaternions at critical frames, then re-derive ω, α, and zeroed quantities.
- **Linear outliers:** PCHIP (Piecewise Cubic Hermite Interpolating Polynomial) on root-relative positions at critical frames, then re-derive v, a.

---

## 14. References

1. **de Leva, P.** (1996). Adjustments to Zatsiorsky-Seluyanov's segment inertia parameters. *Journal of Biomechanics*, 29(9), 1223–1230. — Segment mass fractions and CoM ratios.

2. **Muller, P., Roithner, R., & Gatterer, H.** (2017). On the angular velocity estimation from orientation data. — Quaternion logarithm method for angular velocity.

3. **Sola, J.** (2017). Quaternion kinematics for the error-state Kalman filter. — Quaternion kinematics framework.

4. **Savitzky, A. & Golay, M. J. E.** (1964). Smoothing and differentiation of data by simplified least squares procedures. *Analytical Chemistry*, 36(8), 1627–1639. — Savitzky-Golay filter theory.

5. **Wu, G. et al.** (2002). ISB recommendation on definitions of joint coordinate system. *Journal of Biomechanics*, 35(4), 543–548. — ISB Euler angle standards for upper body.

6. **Wu, G. et al.** (2005). ISB recommendation on definitions of joint coordinate systems (lower body). *Journal of Biomechanics*, 38(5), 981–992. — ISB Euler angle standards for lower body.

7. **Diebel, J.** (2006). Representing attitude: Euler angles, unit quaternions, and rotation vectors. — Rotation representation theory.

---

## Feature Count Summary

For a typical 19-joint skeleton, the master Parquet contains approximately:

| Category | Features per Entity | Entities | Total Columns |
|----------|-------------------|----------|---------------|
| A. Orientation (quaternions + rotvec + rotmag) | 12 | 19 joints | 228 |
| B. Angular kinematics (ω + α, both tracks) | 14 | 19 joints | 266 |
| C. Linear kinematics (pos + vel + acc) | 11 | 19 segments | 209 |
| D. Whole-body CoM | 3 | 1 (global) | 3 |
| E. Euler angles | 3 | 19 joints | 57 |
| F. Artifact flags | 2 | 19 entities | 38 |
| Metadata (time_s) | 1 | — | 1 |
| **Total** | | | **~800** |

---

*Document generated for the Gaga Motion Analysis Pipeline. Last updated: 2026-02-17.*
