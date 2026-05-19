# 🎯 JOINT-LEVEL TRACKING REQUIREMENTS

## Overview

For effective debugging and quality control, the following metrics must track **which joint** has the problematic/maximum value, along with **when** (frame number) it occurred.

---

## 📊 METRICS REQUIRING JOINT IDENTIFICATION

### **Category 1: Kinematic Extremes**

#### 1.1 Angular Velocity
```python
"Max_Ang_Vel": 1026.98,                    # Current (value only)
"Max_Ang_Vel_Joint": "RightHand",          # NEW - Which joint
"Max_Ang_Vel_Frame": 15234,                # NEW - When (frame #)
```

**Why**: Rapid angular velocities are normal for hands during expressive dance, but abnormal for pelvis/spine.

**Example Use Cases:**
- ✅ `RightHand` @ 1000°/s → Expected (gesture)
- ⚠️ `Hips` @ 1000°/s → Suspicious (marker artifact)
- ❌ `Head` @ 3000°/s → Unphysiological (marker slip)

---

#### 1.2 Angular Acceleration
```python
"Max_Ang_Acc": 42172.89,                   # Current (value only)
"Max_Ang_Acc_Joint": "LeftHandIndex3",     # NEW - Which joint
"Max_Ang_Acc_Frame": 8967,                 # NEW - When (frame #)
```

**Why**: Finger joints naturally have higher angular acceleration than trunk segments.

**Example Use Cases:**
- ✅ `LeftHandIndex3` @ 40,000°/s² → Expected (finger snap)
- ⚠️ `LeftArm` @ 40,000°/s² → Borderline (ballistic movement)
- ❌ `Spine` @ 40,000°/s² → Unphysiological (artifact)

---

#### 1.3 Linear Acceleration
```python
"Max_Lin_Acc": 38536.2,                    # Current (value only)
"Max_Lin_Acc_Joint": "RightToeBase",       # NEW - Which joint
"Max_Lin_Acc_Frame": 12045,                # NEW - When (frame #)
```

**Why**: Impact events (foot strike) produce high accelerations in distal segments.

**Example Use Cases:**
- ✅ `RightToeBase` @ 50 m/s² → Expected (jump landing)
- ⚠️ `RightHand` @ 50 m/s² → Possible (impact with floor/prop)
- ❌ `Hips` @ 50 m/s² → Unphysiological (rigid body violation)

---

### **Category 2: Physiological Validation Flags**

#### 2.1 Unphysiological Acceleration
```python
"Unphysiological_Accel": True,                    # Current (boolean only)
"Unphysiological_Accel_Joint": "LeftHandMiddle3", # NEW - Culprit joint
"Unphysiological_Accel_Value": 152.4,             # NEW - Actual value (m/s²)
"Unphysiological_Accel_Frame": 23401,             # NEW - When it occurred
```

**Why**: Knowing which joint enables targeted investigation.

**Debugging Workflow:**
1. Flag triggered → Check joint name
2. If distal (hands/feet) → Review for impact/artifact
3. If proximal (pelvis/spine) → Likely marker slip → **Automatic rejection**
4. Navigate to frame → Visual inspection

---

#### 2.2 Unphysiological Angular Velocity
```python
"Unphysiological_Ang_Vel": True,              # Current (boolean only)
"Unphysiological_Ang_Vel_Joint": "Neck",      # NEW - Culprit joint
"Unphysiological_Ang_Vel_Value": 8234.5,      # NEW - Actual value (deg/s)
"Unphysiological_Ang_Vel_Frame": 19872,       # NEW - When it occurred
```

**Why**: Different joints have different physiological limits.

**Physiological Context Table:**
| Joint Type | Expected Max ω | Concern Threshold | Critical Threshold |
|------------|----------------|-------------------|-------------------|
| Fingers    | 2000-3000°/s   | > 4000°/s         | > 6000°/s         |
| Hands/Feet | 1000-2000°/s   | > 3000°/s         | > 5000°/s         |
| Arms/Legs  | 500-1000°/s    | > 2000°/s         | > 3000°/s         |
| Trunk      | 100-300°/s     | > 500°/s          | > 1000°/s         |

---

### **Category 3: Signal Quality Issues**

#### 3.1 Quaternion Normalization Error
```python
"Quat_Norm_Error": 0.0523,                # Current (worst case value)
"Quat_Norm_Error_Joint": "LeftForeArm",   # NEW - Which joint
"Quat_Norm_Error_Frame": 7834,            # NEW - When it occurred
```

**Why**: Persistent quaternion drift in specific joints indicates numerical issues.

**Example Use Cases:**
- ✅ All joints < 0.01 → Excellent quaternion handling
- ⚠️ `LeftForeArm` = 0.05 → Isolated issue (investigate that joint's processing)
- ❌ Multiple joints > 0.1 → Systemic quaternion corruption

---

### **Category 4: Preprocessing Issues**

#### 4.1 Gap Filling
```python
"Max_Gap_MS": 145.2,                      # Current (value only)
"Max_Gap_Joint": "RightHandPinky3",       # NEW - Which joint
"Max_Gap_Start_Frame": 8123,              # NEW - Gap start
"Max_Gap_End_Frame": 8140,                # NEW - Gap end (17 frames)
```

**Why**: Occlusion patterns reveal capture environment issues.

**Example Patterns:**
- Single finger occluded → Hand close to body (normal)
- Multiple fingers occluded → Occlusion plane (environment issue)
- Pelvis occluded → Capture volume problem (critical)

---

#### 4.2 Artifact Detection
```python
"Artifact_Percent": 2.3,                  # Current (overall %)
"Artifact_Worst_Joint": "LeftToeBase",    # NEW - Most affected
"Artifact_Worst_Joint_Percent": 8.5,      # NEW - % for that joint
"Artifact_Joints_List": "LeftToeBase, RightToeBase, LeftFoot",  # NEW - All affected > 5%
```

**Why**: Systematic artifacts in foot markers → Floor reflection issue.

**Example Debugging:**
- Both `ToeBases` have artifacts → Floor reflection (environment fix)
- Single finger high artifacts → Marker occlusion (normal)
- Pelvis artifacts → Clothing interference (re-capture)

---

#### 4.3 Bone Stability (Worst Bone)
```python
"Worst_Bone": "Hips->Spine",              # Current (name only)
"Worst_Bone_CV": 1.82,                    # NEW - Actual CV value
"Worst_Bone_Max_Jump_m": 0.023,           # NEW - Maximum single-frame length change
"Worst_Bone_Frame": 12304,                # NEW - When largest jump occurred
```

**Why**: CV alone doesn't show if it's gradual drift vs. sudden jump.

**Example Debugging:**
- CV = 2.0%, max_jump = 0.002m → Gradual soft tissue (acceptable)
- CV = 2.0%, max_jump = 0.05m @ frame 1000 → Sudden marker slip → **Flag frame for review**

---

### **Category 5: Effort & Movement Characterization**

#### 5.1 Outlier Detection
```python
"Outlier_Frames": 42,                     # Current (count only)
"Outlier_Percent": 1.4,                   # NEW - Percentage
"Outlier_Joints_List": "RightHand, LeftHand, RightToeBase",  # NEW - Joints with outliers
"Outlier_Worst_Joint": "RightHand",       # NEW - Joint with most outliers
"Outlier_Worst_Joint_Count": 28,          # NEW - Count for that joint
```

**Why**: Distinguishes choreography (many joints) vs. artifact (single joint).

**Example Patterns:**
- Both hands + feet → Dynamic choreography (normal)
- Single hand only → Possible prop interaction or artifact
- Pelvis/spine outliers → Marker slip (investigate)

---

## 🛠️ IMPLEMENTATION REQUIREMENTS

### Step 1: Update `step_06_kinematics` Summary Generation

The kinematics calculation script must track joint indices when computing maxima.

```python
# Example: Angular velocity tracking
def compute_kinematics_with_tracking(omega, omega_mag, joint_names):
    """Compute max values WITH joint identification."""
    
    # Find maximum angular velocity
    max_omega_idx = np.unravel_index(np.nanargmax(omega_mag), omega_mag.shape)
    frame_idx, joint_idx = max_omega_idx
    
    return {
        "max": float(omega_mag[frame_idx, joint_idx]),
        "max_joint": joint_names[joint_idx],
        "max_frame": int(frame_idx),
        "mean": float(np.nanmean(omega_mag))
    }
```

### Step 2: Update Summary JSON Structure

**Current Structure:**
```json
{
  "metrics": {
    "angular_velocity": {
      "max": 1026.98,
      "mean": 31.98
    }
  }
}
```

**Enhanced Structure:**
```json
{
  "metrics": {
    "angular_velocity": {
      "max": 1026.98,
      "max_joint": "RightHand",
      "max_frame": 15234,
      "mean": 31.98,
      "p95": 456.23,
      "p95_joint": "LeftHand",
      "distribution": {
        "RightHand": {"max": 1026.98, "mean": 234.5},
        "LeftHand": {"max": 987.3, "mean": 221.1},
        "Hips": {"max": 45.2, "mean": 12.3}
      }
    },
    "linear_accel": {
      "max": 38536.2,
      "max_joint": "RightToeBase",
      "max_frame": 12045,
      "mean": 814.07,
      "p95": 12345.6
    },
    "angular_accel": {
      "max": 42172.89,
      "max_joint": "LeftHandIndex3",
      "max_frame": 8967,
      "mean": 564.76
    }
  },
  "signal_quality": {
    "max_quat_norm_error": 0.0523,
    "max_quat_norm_error_joint": "LeftForeArm",
    "max_quat_norm_error_frame": 7834
  }
}
```

---

## 📋 UPDATED CHECKLIST INTEGRATION

### Audit Checklist Section Update

**Old:**
```
- [ ] Maximum angular velocity < 2000 °/s (physiological limit)
```

**New:**
```
- [ ] Maximum angular velocity documented with joint and frame
- [ ] If max_joint is distal (hands/feet/fingers): max_vel < 3000 °/s (acceptable)
- [ ] If max_joint is proximal (pelvis/spine): max_vel < 500 °/s (critical)
- [ ] Frame number recorded for visual verification if needed
```

---

## 🎯 PRIORITY METRICS FOR JOINT TRACKING

### **High Priority (Implement First):**
1. ✅ `Max_Ang_Vel` → `Max_Ang_Vel_Joint`, `Max_Ang_Vel_Frame`
2. ✅ `Max_Lin_Acc` → `Max_Lin_Acc_Joint`, `Max_Lin_Acc_Frame`
3. ✅ `Unphysiological_Accel` → `Unphysiological_Accel_Joint`, `Unphysiological_Accel_Value`, `Unphysiological_Accel_Frame`
4. ✅ `Unphysiological_Ang_Vel` → `Unphysiological_Ang_Vel_Joint`, `Unphysiological_Ang_Vel_Value`, `Unphysiological_Ang_Vel_Frame`
5. ✅ `Quat_Norm_Error` → `Quat_Norm_Error_Joint`, `Quat_Norm_Error_Frame`

### **Medium Priority:**
6. ✅ `Max_Gap_MS` → `Max_Gap_Joint`, `Max_Gap_Start_Frame`, `Max_Gap_End_Frame`
7. ✅ `Worst_Bone` → `Worst_Bone_CV`, `Worst_Bone_Max_Jump_m`, `Worst_Bone_Frame`
8. ✅ `Outlier_Frames` → `Outlier_Joints_List`, `Outlier_Worst_Joint`

### **Lower Priority (Future):**
9. ⏳ `Artifact_Percent` → Per-joint artifact percentages
10. ⏳ Per-joint dominant frequencies
11. ⏳ Per-joint movement quality scores

---

## 📊 EXAMPLE MASTER REPORT ROW (Enhanced)

```python
{
    "Run_ID": "734_T1_P1_R1_Take 2025-12-01 02.18.27 PM",
    
    # Kinematic extremes WITH context
    "Max_Ang_Vel": 1026.98,
    "Max_Ang_Vel_Joint": "RightHand",          # ✅ Normal for hand
    "Max_Ang_Vel_Frame": 15234,
    
    "Max_Lin_Acc": 38536.2,
    "Max_Lin_Acc_Joint": "RightToeBase",       # ✅ Normal for jump landing
    "Max_Lin_Acc_Frame": 12045,
    
    # Physiological validation WITH culprit
    "Unphysiological_Accel": False,            # ✅ All values normal
    "Unphysiological_Accel_Joint": "None",
    "Unphysiological_Accel_Value": 0.0,
    
    "Unphysiological_Ang_Vel": False,          # ✅ All values normal
    "Unphysiological_Ang_Vel_Joint": "None",
    
    # Signal quality WITH problem source
    "Quat_Norm_Error": 0.0,
    "Quat_Norm_Error_Joint": "None",           # ✅ Excellent quaternion handling
    
    # Preprocessing WITH problem source
    "Max_Gap_MS": 83.5,
    "Max_Gap_Joint": "RightHandPinky3",        # ✅ Expected (finger occlusion)
    
    "Worst_Bone": "Hips->Spine",
    "Worst_Bone_CV": 0.72,                     # ✅ GOLD quality
    
    "Research_Decision": "ACCEPT"
}
```

---

## 🔧 NEXT STEPS

### Step 1: Update Kinematics Module (step_06)
Add joint and frame tracking to:
- `compute_kinematics()` function
- `compute_derivatives()` function
- Summary JSON export

### Step 2: Update Preprocessing Module (step_02)
Add joint tracking to:
- Gap detection
- Artifact detection
- Bone length QC

### Step 3: Update Master Report (Notebook 07)
Extract new fields from enhanced summaries

### Step 4: Create Visualization Tools
- Heatmap: Which joints have most issues across runs
- Timeline: When problems occur (early/late in recording)
- Joint comparison: Is RightHand consistently problematic?

---

**VERSION**: 1.0  
**DATE**: January 2026  
**STATUS**: Ready for Implementation
