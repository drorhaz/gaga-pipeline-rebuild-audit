# ROM (Range of Motion) Documentation - Complete Guide

## ⚠️ CRITICAL: ROM IS FOR QUALITY CONTROL ONLY

**THIS ROM METRIC IS NOT CLINICAL/ANATOMICAL ROM!**

- ✅ **Valid for**: Tracking quality, outlier detection, data QC
- ❌ **NOT valid for**: Clinical assessment, anatomical analysis, literature comparison

**Type**: Rotation vector magnitude (QC metric)  
**NOT**: Anatomical Euler angles (clinical ROM)

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Overview & What is ROM](#overview--what-is-rom)
3. [Data Files & Schema](#data-files--schema)
4. [Accessing ROM Data](#accessing-rom-data)
5. [Quality Control Thresholds](#quality-control-thresholds)
6. [Computation Method](#computation-method)
7. [Implementation Summary](#implementation-summary)
8. [Literature Analysis](#literature-analysis)
9. [Method Comparison](#method-comparison)
10. [FAQ](#faq)
11. [References](#references)

---

# Quick Start

## TL;DR

ROM calculations are now saved in Parquet format for easy access:

```python
import pandas as pd

# Load ROM data
df_rom = pd.read_parquet(
    'derivatives/step_06_kinematics/{RUN_ID}__joint_statistics.parquet'
)

# View joints sorted by ROM
print(df_rom.sort_values('rom', ascending=False)[['joint_name', 'rom']])
```

## Where is ROM Saved?

**Location:** `derivatives/step_06_kinematics/`

**Files:**
- `{RUN_ID}__joint_statistics.parquet` ← **Use this for analysis**
- `{RUN_ID}__joint_statistics.json` ← Human-readable version
- `{RUN_ID}__kinematics_summary.json` ← Audit trail with file paths

## Common Tasks

### 1. Find Joints with Highest ROM

```python
top_5 = df_rom.nlargest(5, 'rom')
print(top_5[['joint_name', 'rom']])
```

### 2. Check for Suspicious ROM Values

```python
# ROM > 200° = needs review
suspicious = df_rom[df_rom['rom'] > 200]
print(f"Found {len(suspicious)} joints with ROM > 200°")
print(suspicious[['joint_name', 'rom']])
```

### 3. Compare Left vs Right

```python
left_shoulder = df_rom[df_rom['joint_name'] == 'LeftShoulder']['rom'].values[0]
right_shoulder = df_rom[df_rom['joint_name'] == 'RightShoulder']['rom'].values[0]
asymmetry = abs(left_shoulder - right_shoulder)
print(f"Shoulder asymmetry: {asymmetry:.1f}°")
```

### 4. Visualize ROM Distribution

```python
import matplotlib.pyplot as plt

df_rom_sorted = df_rom.sort_values('rom', ascending=False)
plt.figure(figsize=(12, 6))
plt.barh(df_rom_sorted['joint_name'], df_rom_sorted['rom'])
plt.axvline(x=200, color='orange', linestyle='--', label='Review Threshold')
plt.axvline(x=300, color='red', linestyle='--', label='Reject Threshold')
plt.xlabel('ROM (degrees)')
plt.title('Joint Range of Motion')
plt.legend()
plt.tight_layout()
plt.show()
```

---

# Overview & What is ROM

## What is ROM?

**ROM (Range of Motion) - QC VERSION** is the maximum angular excursion (in degrees) computed from rotation vectors. It quantifies "how much the joint moved" for quality control purposes.

⚠️ **This is NOT the same as clinical ROM** which measures flexion/abduction/rotation separately using anatomical Euler angles.

## What You're Measuring

### Your Method
```
ROM from rotation vectors = "How much did the joint move?"
```
- Single number per joint
- Good for QC and outlier detection
- **Cannot** separate flexion from abduction from rotation

### Literature Standard (Wu et al., ISB)
```
ROM from Euler angles = "How much flexion? Abduction? Rotation?"
```
- Three numbers per joint (one per anatomical plane)
- Standard in clinical and biomechanics research
- Anatomically interpretable

## Key Features

- ✅ **Gimbal-lock free**: Computed from quaternion-derived rotation vectors
- ✅ **Continuous**: No ±180° wrapping artifacts  
- ✅ **Per-joint metrics**: Individual ROM calculated for all 27 joints
- ✅ **Quality control**: Perfect for detecting tracking errors
- ⚠️ **NOT anatomical**: Cannot separate flexion from abduction from rotation
- ⚠️ **NOT comparable**: To clinical ROM norms in literature

## What You CAN Conclude

✅ **Tracking quality**
- ROM > 300° → Tracking error
- ROM = 0° → Data processing issue
- ROM spikes → Marker jumps

✅ **Relative comparisons**
- Left vs Right shoulder
- Pre vs Post intervention
- Session 1 vs Session 2

✅ **Movement intensity**
- High ROM = More movement
- Low ROM = Less movement

✅ **Dataset QC**
- Reject bad recordings
- Flag suspicious joints
- Identify asymmetries

## What You CANNOT Conclude

❌ **Anatomical breakdown**
- Cannot determine flexion ROM
- Cannot determine abduction ROM
- Cannot determine rotation ROM

❌ **Clinical comparison**
- Cannot compare to "normal shoulder flexion is 180°"
- Cannot compare to clinical norms
- Cannot use for diagnosis

❌ **Literature comparison**
- Cannot compare to other dance studies
- Cannot compare to sports biomechanics
- Other studies use Euler angles

❌ **Functional assessment**
- Cannot relate to functional tasks
- Cannot assess impairment
- Cannot track rehabilitation progress

---

# Data Files & Schema

## Files Generated

| File | Format | Purpose |
|------|--------|---------|
| `{RUN_ID}__joint_statistics.json` | JSON | Human-readable ROM metrics |
| `{RUN_ID}__joint_statistics.parquet` | Parquet | Fast programmatic access |
| `{RUN_ID}__kinematics_summary.json` | JSON | Audit trail with file references |

## Data Schema

### Joint Statistics Files

Both JSON and Parquet contain the same data with this structure:

```python
{
    "joint_name": "LeftShoulder",
    "rom": 145.32,                    # degrees
    "max_angular_velocity": 678.45,  # deg/s
    "mean_angular_velocity": 234.12, # deg/s
    "p95_angular_velocity": 589.23   # deg/s (95th percentile)
}
```

### Fields Explained

- **`rom`**: Maximum angular excursion in degrees
  - Computed from quaternion-derived rotation vectors
  - Represents maximum range across X, Y, Z axes
  - Gimbal-lock free (no ±180° wrapping artifacts)

- **`max_angular_velocity`**: Peak rotational speed (deg/s)
  - Useful for detecting tracking errors (marker jumps)
  - Typical range for dance: 200-800 deg/s
  - Alert threshold: >1200 deg/s

- **`mean_angular_velocity`**: Average rotational speed (deg/s)
  - Indicates overall movement intensity
  - Typical range: 30-200 deg/s

- **`p95_angular_velocity`**: 95th percentile velocity (deg/s)
  - Robust measure of typical high-velocity movements
  - Less sensitive to outliers than max

---

# Accessing ROM Data

## Python (Parquet - Recommended)

```python
import pandas as pd

# Load ROM statistics
df_rom = pd.read_parquet(
    'derivatives/step_06_kinematics/734_T1_P1_R1_Take 2025-12-01 02.18.27 PM__joint_statistics.parquet'
)

# View all joints with ROM
print(df_rom[['joint_name', 'rom', 'max_angular_velocity']])

# Find joints with highest ROM
top_rom = df_rom.nlargest(5, 'rom')
print(top_rom)

# Filter by ROM threshold
high_rom_joints = df_rom[df_rom['rom'] > 200]
print(f"Joints with ROM > 200°: {len(high_rom_joints)}")
```

## Python (JSON)

```python
import json

# Load ROM statistics
with open('derivatives/step_06_kinematics/734_T1_P1_R1_Take 2025-12-01 02.18.27 PM__joint_statistics.json') as f:
    rom_data = json.load(f)

# Access specific joint
left_shoulder_rom = rom_data['LeftShoulder']['rom']
print(f"Left Shoulder ROM: {left_shoulder_rom}°")
```

## From Audit Trail

```python
import json

# Load kinematics summary (audit trail)
with open('derivatives/step_06_kinematics/734_T1_P1_R1_Take 2025-12-01 02.18.27 PM__kinematics_summary.json') as f:
    summary = json.load(f)

# Get ROM file locations
rom_files = summary['rom_files']
print(f"ROM JSON: {rom_files['json']}")
print(f"ROM Parquet: {rom_files['parquet']}")
print(f"Description: {rom_files['description']}")
```

## How to Generate ROM Files

**Run Notebook 06** (`06_rotvec_omega.ipynb`):

1. Execute **Cell 0-16** in order
2. Check output confirms files saved:
   ```
   ✅ Joint statistics JSON saved: ...
   ✅ Joint statistics Parquet saved: ...
   ```

## Verify Files Exist

```python
import os

run_id = "734_T1_P1_R1_Take 2025-12-01 02.18.27 PM"  # Your run ID
base_path = "derivatives/step_06_kinematics"

json_path = f"{base_path}/{run_id}__joint_statistics.json"
parquet_path = f"{base_path}/{run_id}__joint_statistics.parquet"

print(f"JSON exists: {os.path.exists(json_path)}")
print(f"Parquet exists: {os.path.exists(parquet_path)}")
```

---

# Quality Control Thresholds

## Typical ROM Ranges (Gaga Dance)

| Joint Type | Good ROM Range | Suspicious | Bad |
|-----------|----------------|------------|-----|
| Shoulders | 100-180° | >200° | >300° or 0° |
| Hips | 60-120° | >200° | >300° or 0° |
| Spine | 50-100° | >200° | >300° or 0° |
| Elbows/Knees | 80-150° | >200° | >300° or 0° |

## Angular Velocity Ranges

| Category | Good Range | Suspicious | Bad |
|----------|-----------|------------|-----|
| Max Velocity | 200-800 deg/s | >1000 deg/s | >1200 deg/s or 0 |

## Red Flags

⚠️ **Review Recommended:**
- ROM > 200° (possible tracking issue)
- Max velocity > 1000 deg/s (possible marker jump)
- Asymmetry: Left/Right ROM difference > 100°

❌ **Reject Data:**
- ROM > 300° (physically impossible)
- Max velocity > 1200 deg/s (exceeds physiological limits)
- ROM = 0° or velocity = 0 (processing error)

---

# Computation Method

## Cell Execution Order

The ROM computation follows this workflow in **Notebook 06** (`06_rotvec_omega.ipynb`):

1. **Cell 15**: Compute ROM from quaternions
   - Loads quaternion data from `df_in`
   - Applies reference pose calibration
   - Computes rotation vectors (axis-angle representation)
   - Calculates ROM = max - min per axis
   - Computes angular velocity statistics

2. **Cell 16**: Save ROM to files
   - Exports to JSON (human-readable)
   - Exports to Parquet (fast access)
   - Displays summary statistics

3. **Cell 14**: Update audit trail
   - Adds `rom_files` field to kinematics_summary.json
   - Documents file locations and descriptions

## Algorithm Details

```python
# Pseudo-code for ROM computation
for each joint:
    # 1. Get quaternion time series
    q_child = df_in[[f'{joint}__qx', ...]]
    q_parent = df_in[[f'{parent}__qx', ...]]
    
    # 2. Apply reference pose calibration
    q_rel = inv(q_parent) * q_child
    q_rel_ref = inv(q_parent_ref) * q_child_ref
    q_final = inv(q_rel_ref) * q_rel
    
    # 3. Convert to rotation vectors (axis-angle)
    rotvec = scipy.spatial.transform.Rotation.from_quat(q_final).as_rotvec()
    
    # 4. Unwrap to remove ±180° discontinuities
    rotvec_unwrapped = np.unwrap(rotvec, axis=0)
    
    # 5. Convert to degrees
    rotvec_deg = np.degrees(rotvec_unwrapped)
    
    # 6. Compute ROM per axis
    rom_x = max(rotvec_deg[:, 0]) - min(rotvec_deg[:, 0])
    rom_y = max(rotvec_deg[:, 1]) - min(rotvec_deg[:, 1])
    rom_z = max(rotvec_deg[:, 2]) - min(rotvec_deg[:, 2])
    
    # 7. Total ROM = maximum across axes
    rom = max(rom_x, rom_y, rom_z)
```

## Why Quaternions?

Traditional Euler angles suffer from:
- **Gimbal lock**: Loss of one degree of freedom at ±90°
- **Wrapping artifacts**: ±180° discontinuities cause incorrect ROM
- **Order dependency**: Different rotation orders give different results

Quaternion-based ROM computation avoids these issues by:
- Using rotation vectors (axis-angle representation)
- Applying `np.unwrap()` to remove discontinuities
- Computing ROM directly from continuous angle time series

## Why the Difference?

### Rotation Vectors (Your Method)

```python
# Rotation vector = axis-angle representation
rotvec = [rx, ry, rz]

# rx, ry, rz are:
# - Components of a 3D rotation vector
# - NOT flexion, abduction, rotation
# - Arbitrary mathematical axes
```

**Advantage:** No gimbal lock, continuous  
**Disadvantage:** Not anatomically meaningful

### Euler Angles (Literature Standard)

```python
# Euler angles = ordered rotations around anatomical axes
euler = [flexion, abduction, rotation]  # Example for shoulder

# Each angle corresponds to:
# - Flexion/extension (sagittal plane)
# - Abduction/adduction (frontal plane)  
# - Internal/external rotation (transverse plane)
```

**Advantage:** Anatomically interpretable  
**Disadvantage:** Gimbal lock at ±90°, ±180° wrapping

## Analogy

**Your ROM** = "How far did you drive?" (total distance)  
**Clinical ROM** = "How far North? East? Up?" (per direction)

Both are correct measures of movement, but they answer different questions!

---

# Implementation Summary

## Changes Made

### ✅ Completed

1. **Added ROM Export Cell (Cell 16)**
   - Saves joint statistics to dedicated files
   - Exports both JSON and Parquet formats
   - Includes ROM and angular velocity metrics

2. **Updated Audit Trail (Cell 14)**
   - Added `rom_files` field to `kinematics_summary.json`
   - Documents file paths and descriptions
   - Ensures traceability

3. **Added ROM File References (Cell 15)**
   - Quick access instructions
   - Example code for loading ROM data
   - Audit trail reference

4. **Created Documentation**
   - Complete user guide (this file)
   - Covers data schema, access methods, QC thresholds
   - Includes code examples and FAQ

## File Structure

```
derivatives/step_06_kinematics/
├── {RUN_ID}__kinematics.parquet              # Time-series kinematics
├── {RUN_ID}__kinematics_summary.json         # Audit trail with ROM references
├── {RUN_ID}__joint_statistics.json           # ROM data (human-readable)
├── {RUN_ID}__joint_statistics.parquet        # ROM data (fast access)
└── {RUN_ID}__outlier_report.json             # Outlier analysis
```

## Notebook 06 Cell Order

To ensure proper ROM saving, execute cells in this order:

1. **Cells 0-13**: Standard kinematics processing
2. **Cell 14**: Final export with outlier flags
3. **Cell 15**: ROM file references (displays access info)
4. **Cell 16**: Compute ROM from quaternions
5. **Cell 17**: Save ROM to JSON and Parquet files

**Important:** If you run Cell 14 before Cells 16-17, re-run Cell 14 to update the audit trail.

## Audit Trail

### Automatic Documentation

ROM file locations are automatically documented in:

```json
{
    "run_id": "734_T1_P1_R1_Take 2025-12-01 02.18.27 PM",
    "rom_files": {
        "json": "734_T1_P1_R1_Take 2025-12-01 02.18.27 PM__joint_statistics.json",
        "parquet": "734_T1_P1_R1_Take 2025-12-01 02.18.27 PM__joint_statistics.parquet",
        "location": "derivatives/step_06_kinematics/",
        "description": "Per-joint ROM and angular velocity statistics computed from quaternion-derived angles"
    }
}
```

### Traceability

Every ROM calculation is traceable to:
1. **Input data**: `{RUN_ID}__filtered.parquet` (Cell 0)
2. **Reference pose**: `{RUN_ID}__reference_map.json` (Step 05)
3. **Processing parameters**: `CONFIG['SG_WINDOW_SEC']`, `CONFIG['SG_POLYORDER']`
4. **Output files**: Documented in `kinematics_summary.json`

## Benefits

### Before This Change

❌ ROM computed but NOT saved  
❌ Re-computation required for each analysis  
❌ No audit trail for ROM files  
❌ Difficult to share ROM data  

### After This Change

✅ ROM saved in Parquet (fast access)  
✅ Saved in JSON (human-readable)  
✅ Documented in audit trail  
✅ Easy to load and share  
✅ Supports downstream QC and analysis  

## Technical Details

### Why Parquet?

- **Fast**: Columnar format optimized for DataFrames
- **Compact**: Compressed binary format
- **Type-safe**: Preserves float precision
- **Ecosystem**: Native pandas/arrow support

### Why Also JSON?

- **Human-readable**: Easy inspection without code
- **Portable**: Works with any JSON parser
- **Debugging**: Quick visual verification

---

# Literature Analysis

## Is ROM Calculated According to Literature?

### Short Answer

**Partially** - Your method is:
- ✅ **Correct** for quality control
- ✅ **Gimbal-lock free** (better than naive Euler)
- ⚠️ **Non-standard** (uses rotation vectors, not anatomical Euler angles)
- ⚠️ **Not comparable** to clinical ROM literature

## Current Implementation Analysis

### Method Used in Notebook 06

```python
# 1. Compute relative rotation (joint relative to parent)
rot_rel = rot_parent.inv() * rot_child

# 2. Apply reference calibration
rot_final = rot_rel_ref.inv() * rot_rel

# 3. Convert to rotation vectors (axis-angle)
rotvec = rot_final.as_rotvec()  # Radians

# 4. Unwrap to remove discontinuities
rotvec_x_unwrapped = np.unwrap(rotvec[:, 0])
rotvec_y_unwrapped = np.unwrap(rotvec[:, 1])
rotvec_z_unwrapped = np.unwrap(rotvec[:, 2])

# 5. Compute ROM per axis
rom_x = max(rotvec_x) - min(rotvec_x)
rom_y = max(rotvec_y) - min(rotvec_y)
rom_z = max(rotvec_z) - min(rotvec_z)

# 6. Total ROM = maximum across axes
rom = max(rom_x, rom_y, rom_z)
```

## Comparison to Biomechanical Literature

### Standard Clinical ROM Definition (ISB/Wu et al. 2002, 2005)

**Literature standard:**
1. Define anatomical coordinate systems using ISB conventions
2. Express joint angles as **ordered Euler angles** (e.g., XYZ intrinsic)
3. ROM = max - min for **each Euler angle component**
4. Report ROM **per anatomical plane**:
   - Flexion/Extension (sagittal plane)
   - Abduction/Adduction (frontal plane)
   - Internal/External rotation (transverse plane)

**Example (Shoulder):**
- Flexion ROM: 180° (from 0° extension to 180° flexion)
- Abduction ROM: 180° (from 0° to 180° abduction)
- External rotation ROM: 90° (from 0° to 90° external rotation)

### Current Implementation

**What we're doing:**
1. ✅ Compute relative rotations (joint to parent) - **CORRECT**
2. ✅ Apply reference calibration - **CORRECT**
3. ⚠️ Convert to **rotation vectors** (axis-angle) - **NON-STANDARD**
4. ⚠️ Compute ROM from rotation vector components - **NON-STANDARD**
5. ⚠️ Report maximum ROM across all axes - **NON-STANDARD**

**Key difference:**
- **Literature**: ROM from **Euler angles** (anatomically interpretable)
- **Our method**: ROM from **rotation vectors** (mathematically simpler but less interpretable)

## What This Method Measures

### Rotation Vector (Axis-Angle) Representation

A rotation vector `(rx, ry, rz)` represents:
- **Direction**: Axis of rotation (normalized vector)
- **Magnitude**: Angle of rotation around that axis

**Mathematical properties:**
- ✅ Gimbal-lock free
- ✅ No ±180° discontinuities (after unwrapping)
- ✅ Smooth time derivatives
- ❌ **Not anatomically interpretable** (not flexion/extension/etc.)

### What ROM from Rotation Vectors Means

**Physical interpretation:**
- `rom_x`: Max excursion in rotation vector's X component
- `rom_y`: Max excursion in rotation vector's Y component  
- `rom_z`: Max excursion in rotation vector's Z component
- `rom_total`: Maximum excursion across all components

**⚠️ Critical Issue:**
Rotation vector components **do not** correspond to:
- Flexion/extension
- Abduction/adduction
- Internal/external rotation

They are **arbitrary axes** defined by the rotation vector representation.

## Conclusion

### Is ROM Calculated According to Literature?

**Partially:**
- ✅ Quaternion-based approach is **correct** and **recommended**
- ✅ Reference calibration is **appropriate**
- ❌ Using rotation vectors instead of Euler angles is **non-standard**

### What Can We Conclude?

✅ **Valid for:**
- Quality control (tracking artifacts, marker jumps)
- Outlier detection (ROM > 300° = bad)
- Relative comparisons (pre/post, left/right)
- Movement intensity assessment
- Data rejection criteria

### What Can't We Conclude?

❌ **Cannot:**
- Compare to clinical ROM norms
- Interpret anatomically (flexion vs. abduction)
- Use for medical diagnosis
- Compare to other studies using Euler angles
- Assess functional capacity

---

# Method Comparison

## Side-by-Side Comparison

### Literature Standard (Wu et al., ISB)

```
┌─────────────────────────────────────────┐
│ 1. Compute relative rotation            │
│    (joint relative to parent)           │
│    ✅ Same as your method               │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 2. Convert to EULER ANGLES              │
│    e.g., XYZ intrinsic (body-axis)      │
│    - X = Flexion/Extension              │
│    - Y = Abduction/Adduction            │
│    - Z = Internal/External Rotation     │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 3. Compute ROM per Euler angle          │
│    ROM_flex = max(X) - min(X)           │
│    ROM_abduct = max(Y) - min(Y)         │
│    ROM_rot = max(Z) - min(Z)            │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ OUTPUT (Anatomically Interpretable)     │
│ - Flexion ROM: 152°                     │
│ - Abduction ROM: 138°                   │
│ - Rotation ROM: 87°                     │
│                                         │
│ ✅ Can compare to clinical norms        │
│ ✅ Anatomically meaningful              │
│ ⚠️ Gimbal lock at ±90°                  │
│ ⚠️ ±180° wrapping artifacts             │
└─────────────────────────────────────────┘
```

### Your Method (Rotation Vectors)

```
┌─────────────────────────────────────────┐
│ 1. Compute relative rotation            │
│    (joint relative to parent)           │
│    ✅ Same as literature                │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 2. Convert to ROTATION VECTORS          │
│    (axis-angle representation)          │
│    - rx = Rotation around X axis        │
│    - ry = Rotation around Y axis        │
│    - rz = Rotation around Z axis        │
│    ⚠️ NOT flexion/abduction/rotation    │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 3. Unwrap to remove discontinuities     │
│    rx_unwrapped = np.unwrap(rx)         │
│    ry_unwrapped = np.unwrap(ry)         │
│    rz_unwrapped = np.unwrap(rz)         │
│    ✅ Removes axis flips                │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 4. Compute ROM per rotvec component     │
│    ROM_x = max(rx) - min(rx)            │
│    ROM_y = max(ry) - min(ry)            │
│    ROM_z = max(rz) - min(rz)            │
│    ROM_total = max(ROM_x, ROM_y, ROM_z) │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ OUTPUT (QC Metric)                      │
│ - Total ROM: 145°                       │
│                                         │
│ ✅ Good for quality control             │
│ ✅ No gimbal lock                       │
│ ✅ No wrapping artifacts                │
│ ⚠️ NOT anatomically interpretable       │
│ ⚠️ Cannot compare to clinical norms     │
└─────────────────────────────────────────┘
```

## What Each Method Is Good For

### Your Method (Rotation Vectors)

**✅ EXCELLENT FOR:**

| Use Case | Why It Works |
|----------|--------------|
| Tracking quality | Large ROM (>300°) = tracking error |
| Marker jumps | Sudden ROM spike = marker jump |
| Zero motion detection | ROM = 0° = data processing error |
| Left/Right symmetry | Compare ROM values directly |
| Relative comparisons | Same joint across sessions |
| Automated QC | Single metric, easy thresholds |

**❌ NOT SUITABLE FOR:**

| Use Case | Why It Fails |
|----------|--------------|
| Clinical assessment | Can't measure "flexion ROM" |
| Literature comparison | Other studies use Euler angles |
| Functional capacity | Need anatomical movements |
| Rehabilitation | Can't track "increased flexion" |
| Impairment rating | Clinical standards use Euler |

### Literature Method (Euler Angles)

**✅ EXCELLENT FOR:**

| Use Case | Why It Works |
|----------|--------------|
| Clinical assessment | "Flexion ROM = 120°" is meaningful |
| Literature comparison | Standard in all studies |
| Anatomical analysis | Which plane moves most? |
| Functional tasks | Relate to ADL requirements |
| Rehabilitation | Track improvement per movement |

**❌ POTENTIAL ISSUES:**

| Problem | Impact |
|---------|--------|
| Gimbal lock | Loses DOF at ±90° |
| Wrapping artifacts | ±180° jumps can inflate ROM |
| Order dependency | XYZ ≠ ZXY sequences |
| Interpretation complexity | Need domain knowledge |

## Practical Implications

### For Your Gaga Dance Study

**Current method is GOOD for:**
- ✅ Quality control: "This recording has no tracking errors"
- ✅ Outlier detection: "Joint X has suspicious ROM > 200°"
- ✅ Dataset selection: "Include only recordings with ROM < 300°"
- ✅ Symmetry checks: "Left shoulder ROM = 145°, Right = 152° → OK"

**Current method CANNOT:**
- ❌ Compare to dance literature: "Ballet dancers have 180° hip flexion ROM"
- ❌ Describe movement: "Gaga dancers use more flexion than abduction"
- ❌ Relate to function: "This ROM allows reaching overhead"
- ❌ Diagnose: "Limited ROM indicates pathology"

## Recommendations

### Option 1: Keep Current Method (Recommended for QC)

**Use case:** Quality control and outlier detection

**Advantages:**
- ✅ Already implemented
- ✅ Mathematically sound
- ✅ Good for tracking quality
- ✅ Avoids gimbal lock issues

**Label clearly:**
- "ROM from rotation vectors (QC metric)"
- "Not comparable to clinical ROM norms"
- "For tracking quality assessment only"

### Option 2: Add Anatomical ROM (For Clinical Comparison)

**Use case:** Comparisons to literature, clinical assessment

**Implementation:**
```python
# Compute Euler angles using ISB conventions
from scipy.spatial.transform import Rotation as R

# Convert to Euler angles (e.g., XYZ intrinsic for shoulder)
euler_angles = rot_final.as_euler('XYZ', degrees=True)  # Shape: (T, 3)

# ROM per anatomical plane
rom_flexion = np.max(euler_angles[:, 0]) - np.min(euler_angles[:, 0])
rom_abduction = np.max(euler_angles[:, 1]) - np.min(euler_angles[:, 1])
rom_rotation = np.max(euler_angles[:, 2]) - np.min(euler_angles[:, 2])
```

**Advantages:**
- ✅ Comparable to clinical literature
- ✅ Anatomically interpretable
- ✅ Standard in biomechanics

**Disadvantages:**
- ⚠️ Gimbal lock at ±90°
- ⚠️ ±180° wrapping artifacts possible
- ⚠️ Euler sequence must be chosen per joint (per ISB)

### Option 3: Report Both Metrics

**Best of both worlds:**
- Rotation vector ROM for QC (current method)
- Anatomical Euler ROM for clinical comparison (new method)

**Output:**
```json
{
    "joint_name": "LeftShoulder",
    "rom_qc": 145.3,  // From rotation vectors (QC metric)
    "rom_anatomical": {
        "flexion_extension": 152.4,  // From Euler X (ISB convention)
        "abduction_adduction": 138.7,  // From Euler Y
        "internal_external_rotation": 87.2  // From Euler Z
    }
}
```

---

# FAQ

## Q: Why are Parquet files not in git?

**A:** Parquet files are excluded via `.gitignore` (line 43: `*.parquet`) because they contain large binary data. They are regenerated each time the pipeline runs.

## Q: How do I regenerate ROM data?

**A:** Run Notebook 06, Cells 15-16:
1. Cell 15: Computes ROM from quaternions
2. Cell 16: Saves to JSON and Parquet

## Q: Can I load ROM without running the full pipeline?

**A:** Yes! If `{RUN_ID}__joint_statistics.parquet` exists, you can load it directly:

```python
df_rom = pd.read_parquet('derivatives/step_06_kinematics/{RUN_ID}__joint_statistics.parquet')
```

## Q: What if Cell 15 runs after Cell 14?

**A:** The audit trail (`kinematics_summary.json`) will show `"joint_statistics": {}` (empty). To fix:
1. Re-run Cell 14 after Cell 15 has completed
2. The summary will update with ROM data

## Q: How do I verify ROM is saved correctly?

**A:** Check for these files:

```bash
ls derivatives/step_06_kinematics/*joint_statistics*
```

Expected output:
```
734_T1_P1_R1_Take 2025-12-01 02.18.27 PM__joint_statistics.json
734_T1_P1_R1_Take 2025-12-01 02.18.27 PM__joint_statistics.parquet
```

## Q: Why Parquet?

**A:** Fast loading, compact storage, preserves float precision.

## Q: Can I use JSON instead?

**A:** Yes! Same data, just slower to load for large datasets.

## Q: What if files don't exist?

**A:** Run Notebook 06, Cells 15-17 to generate them.

## Q: How is ROM computed?

**A:** From quaternion-derived angles using rotation vectors (gimbal-lock free).

---

# References

## Literature Standards

- **Wu et al. (2002, 2005)**: ISB recommendations for joint coordinate systems
  - Location: `references/Wu et al J Biomech 38 (2005) 981–992.pdf`
  - Standard for anatomical ROM measurement

- **Winter (2009)**: Biomechanics and Motor Control
  - Location: `references/Biomechanics and Motor Control...pdf`
  - Fundamental definitions of ROM

- **Longo et al. (2022)**: High-intensity dance biomechanics
  - Gaga-specific movement ranges
  - Used for QC thresholds

## Your Implementation

- **Notebook**: `06_rotvec_omega.ipynb` (Cells 15-17)
- **Method**: Rotation vector (axis-angle) based ROM
- **Purpose**: Quality control for motion capture tracking
- **Validity**: Excellent for QC, not for clinical comparison

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-23 | 1.0 | Initial implementation: ROM saved to Parquet + audit trail |
| 2026-01-23 | 2.0 | Merged all ROM documentation into single comprehensive guide |

---

**Last Updated:** 2026-01-23  
**Author:** Pipeline Enhancement (Cell 15-17 modifications)  
**Status:** ✅ Implemented and Documented
