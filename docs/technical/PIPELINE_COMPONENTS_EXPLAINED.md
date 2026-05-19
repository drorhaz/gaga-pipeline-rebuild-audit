# How Core Pipeline Components Work

## 1. Quaternion Normalization - Detailed Explanation

### **What Problem Does It Solve?**

**Quaternions must be unit length** (norm = 1) to represent valid rotations. However:
- **Numerical drift** accumulates during computations
- **SLERP interpolation** introduces small errors
- **File I/O** can lose precision

### **How It Works (Step-by-Step)**

#### **Step 1: Drift Detection** (`detect_quaternion_drift`)
```python
# Compute norms of all quaternions
norms = np.linalg.norm(q, axis=-1)  # Should all be 1.0

# Measure deviation
norm_errors = np.abs(norms - 1.0)
max_error = np.max(norm_errors)

# Example output:
# max_error = 0.0034 → "ACCEPTABLE" (needs correction)
# max_error = 0.0001 → "EXCELLENT" (no correction needed)
```

**Thresholds**:
- `< 1e-6`: EXCELLENT (perfect)
- `< 1e-3`: GOOD
- `< 0.01`: ACCEPTABLE  
- `> 0.01`: POOR (requires immediate correction)

---

#### **Step 2: Safe Normalization** (`normalize_quaternion_safe`)
```python
# Naive approach (CAN FAIL):
q_norm = q / np.linalg.norm(q)  # Divides by zero if norm ≈ 0!

# Safe approach (CORRECT):
norm = np.linalg.norm(q, axis=-1, keepdims=True)
norm = np.maximum(norm, 1e-12)  # Prevent division by zero
q_norm = q / norm
```

**Why epsilon guard?**
- If quaternion is corrupted (all zeros), naive division crashes
- Epsilon (1e-12) is negligible but prevents divide-by-zero

---

#### **Step 3: Hemispheric Continuity** (`apply_hemispheric_continuity`)

**The Quaternion Double-Cover Problem**:
```
q and -q represent THE SAME rotation!

Example:
q1 = [0, 0, 0, 1]    → 0° rotation
q2 = [0, 0, 0, -1]   → 0° rotation (SAME!)

But temporal jump: ||q2 - q1|| = 2.0 (HUGE!)
```

**Solution**: Enforce continuity by flipping sign when needed

```python
for t in range(1, T):
    # Check if consecutive quaternions are on opposite hemispheres
    dot_product = np.dot(q[t-1], q[t])
    
    if dot_product < 0:
        # On opposite sides → flip to same side
        q[t] *= -1
```

**Before**:
```
Frame 0: [0, 0, 0, +1]
Frame 1: [0, 0, 0, -1]  ← Jump! (same rotation, opposite sign)
dot = +1 * -1 = -1 < 0
```

**After**:
```
Frame 0: [0, 0, 0, +1]
Frame 1: [0, 0, 0, +1]  ← Fixed! (flipped sign)
dot = +1 * +1 = +1 > 0  ✓
```

---

#### **Step 4: Full Correction Pipeline** (`correct_quaternion_sequence`)

```python
# 1. Detect issues
validation_before = validate_quaternion_integrity(q)
# → status: "WARN" (drift=0.008, 12 discontinuities)

# 2. Renormalize
q_corrected, stats = renormalize_quaternions_inplace(q)
# → All norms now within [0.999, 1.001]

# 3. Enforce continuity
q_corrected = apply_hemispheric_continuity(q_corrected)
# → 12 discontinuities fixed (flipped signs)

# 4. Validate after
validation_after = validate_quaternion_integrity(q_corrected)
# → status: "PASS" (drift=0.0001, 0 discontinuities) ✓
```

---

### **When Is This Applied?**

1. **After loading from CSV** (OptiTrack file I/O)
2. **After SLERP interpolation** (gap filling)
3. **After any quaternion math** (multiplication, inverse)
4. **Before computing angles** (ensures valid rotations)

---

### **Real Example from Your Pipeline**

```python
# In parse_optitrack_csv (loading data):
q_global = quat_enforce_continuity(
    quat_shortest(
        quat_normalize(q_global)  # Step 1: Normalize
    )  # Step 2: Shortest path (w >= 0)
)  # Step 3: Continuity

# Result:
# - Norm errors: < 1e-6 (EXCELLENT)
# - Discontinuities: 0
# - Ready for angle computation ✓
```

---

## 2. Coordinate System Transformations

### **The Problem: Two Different Coordinate Conventions**

**OptiTrack World Frame**:
```
      Y (Up)
      |
      |
      +---- X (Right)
     /
    Z (Forward)
```

**ISB Anatomical Frame**:
```
      Y (Up/Superior)
      |
      |
      +---- Z (Right/Lateral)
     /
    X (Forward/Anterior)
```

**They're ROTATED 90° relative to each other!**

---

### **Position Transformation** (`optitrack_to_isb_position`)

```python
# OptiTrack position: [X_right, Y_up, Z_forward] in millimeters
pos_ot = [100, 1500, 200]  # 100mm right, 1500mm up, 200mm forward

# Step 1: Convert units (mm → m)
pos_m = pos_ot / 1000.0  # [0.1, 1.5, 0.2]

# Step 2: Reorder axes
pos_isb = np.zeros(3)
pos_isb[0] = pos_m[2]  # ISB X = OptiTrack Z (forward)
pos_isb[1] = pos_m[1]  # ISB Y = OptiTrack Y (up)
pos_isb[2] = pos_m[0]  # ISB Z = OptiTrack X (right)

# Result: [0.2, 1.5, 0.1] meters
#         [anterior, superior, lateral] ✓
```

---

### **Orientation Transformation** (`optitrack_to_isb_orientation`)

**More complex**: Need to rotate the reference frame itself

```python
# Create rotation matrix for frame change
# This is a 90° rotation around Y-axis
R_transform = np.array([
    [0, 0, 1],   # ISB X ← OptiTrack Z
    [0, 1, 0],   # ISB Y ← OptiTrack Y
    [1, 0, 0]    # ISB Z ← OptiTrack X
])

# Apply to quaternion
q_isb = q_transform ⊗ q_optitrack

# Where q_transform represents R_transform as a quaternion
```

---

### **Validation** (`validate_coordinate_frame`)

```python
# Check if position data is in expected range
def validate_coordinate_frame(pos, expected_frame='optitrack_world'):
    if expected_frame == 'optitrack_world':
        # Y should be positive (up from ground)
        # Magnitude should be in reasonable range (not km!)
        
        checks = {
            'y_mostly_positive': np.mean(pos[:, 1] > 0) > 0.9,
            'magnitude_reasonable': np.median(np.abs(pos)) < 5000,  # < 5m
            'no_invalid_values': not (np.any(np.isnan(pos)) or np.any(np.isinf(pos)))
        }
        
        return all(checks.values())
```

---

### **ISB Euler Angle Sequences** (`ISB_EULER_SEQUENCES`)

**Why different sequences per joint?**

Each joint has **clinically meaningful angles**:

```python
# SHOULDER: Y-X-Y sequence
angles = [
    plane_of_elevation,  # Y: Abduction vs flexion plane
    elevation,            # X: How high the arm is
    axial_rotation       # Y: Internal/external rotation
]

# KNEE: Z-X-Y sequence  
angles = [
    flexion_extension,   # Z: Bending knee
    ab_adduction,        # X: Varus/valgus
    rotation             # Y: Tibial rotation
]
```

**Convention from**: Wu et al. (2005) - ISB standard

---

## 3. Reference Pose Detection & Validation

### **What Is a Reference Pose?**

**Purpose**: Anatomical zero position (calibration)
- **Example**: T-pose, A-pose, or neutral standing
- **Use**: All joint angles computed **relative** to this pose
- **Critical**: Must be truly static (no motion)

---

### **How Automatic Detection Works** (`detect_static_reference`)

```python
# Step 1: Compute motion profile
# For each frame, compute angular velocity magnitude
for t in range(T-1):
    omega = compute_angular_velocity(q[t], q[t+1], dt)
    motion_profile[t] = ||omega||  # rad/s

# Step 2: Sliding window search
window_size = 1.0 second (120 frames @ 120 Hz)
stride = 0.1 second (12 frames)

for window_start in range(0, search_time, stride):
    window_motion = motion_profile[window_start : window_start + window_size]
    
    # Check if sufficiently static
    mean_motion = np.mean(window_motion)
    std_motion = np.std(window_motion)
    
    if mean_motion < 5 deg/s AND std_motion < 2 deg/s:
        # FOUND A STATIC WINDOW!
        ref_start = window_start
        break

# Step 3: Average quaternions in window (Markley method)
q_ref = markley_quaternion_average(q[window])
```

---

### **Motion Profile Example**

```
Time (s)    Motion (deg/s)    Status
0.0         25.3              [MOVING - arms lowering]
0.5         18.7              [MOVING - settling]
1.0         3.2               [STATIC ✓] ← Window starts here
1.5         2.8               [STATIC ✓]
2.0         2.5               [STATIC ✓]
2.5         15.6              [MOVING - starting dance]

Selected: 1.0-2.0s as reference window
Mean motion: 2.8 deg/s < 5 deg/s ✓
```

---

### **Reference Validation** (`validate_reference_window`)

**Research-Based Criteria** (Kok et al. 2017, Roetenberg et al. 2009):

#### **Strict Thresholds**:
```python
mean_motion < 0.3 rad/s  (≈ 17 deg/s)
std_motion  < 0.1 rad/s  (≈ 6 deg/s)
duration    >= 1.0 sec
placement   < 10 sec (early in recording)
```

#### **Relaxed Thresholds**:
```python
mean_motion < 0.5 rad/s  (≈ 29 deg/s)
std_motion  < 0.15 rad/s (≈ 9 deg/s)
duration    >= 0.5 sec
```

---

### **Validation Status Levels**

```python
if pass_mean AND pass_std AND pass_duration:
    status = 'PASS'
    # ✓ Excellent reference pose detected
    
elif pass_mean AND pass_std:
    status = 'WARN_SHORT'
    # ⚠ Static enough, but window too short
    
elif pass_duration:
    status = 'WARN_MOTION'
    # ⚠ Long enough, but too much motion
    
else:
    status = 'FAIL'
    # ✗ No acceptable reference found
```

---

### **Reference Stability Check** (`validate_reference_stability`)

**Internal consistency**: Are quaternions in the window actually similar?

```python
# For each quaternion in reference window:
q_window = q_local[window_frames]

# Compute deviation from average reference
for each q in q_window:
    error = rotation_angle(q, q_ref_average)
    errors.append(error)

# Metrics:
identity_error_mean = np.mean(errors)  # Average deviation
reference_std = np.std(errors)         # Variability within window
max_jump = np.max(consecutive_diffs)   # Largest frame-to-frame change

# Good reference:
# - identity_error_mean < 0.05 rad (< 3°)
# - reference_std < 0.02 rad (< 1.1°)
# - max_jump < 0.01 rad (< 0.6°/frame)
```

---

### **Ground Truth Comparison** (`compare_reference_with_ground_truth`)

**If you have a known calibration pose** (e.g., scanned T-pose):

```python
# Compare detected vs. known
for each joint:
    error_angle = rotation_angle(q_detected[joint], q_ground_truth[joint])
    errors.append(error_angle)

# Classification (Sabatini 2006):
mean_error < 5°  → EXCELLENT
mean_error < 10° → GOOD
mean_error < 15° → ACCEPTABLE
mean_error > 15° → POOR
```

---

## Summary: How These Work Together

```
RAW MOCAP DATA
      ↓
1. QUATERNION NORMALIZATION
   - Correct drift (norms → 1.0)
   - Enforce continuity (no sign flips)
   - Validate integrity
      ↓
2. COORDINATE TRANSFORMATION
   - OptiTrack → ISB
   - Position: reorder + unit conversion
   - Orientation: frame rotation
      ↓
3. REFERENCE DETECTION
   - Find static window (motion < 5°/s)
   - Average quaternions (Markley method)
   - Validate (duration, stability, placement)
      ↓
4. COMPUTE RELATIVE ANGLES
   - All angles relative to reference
   - ISB Euler sequences per joint
   - Biomechanically meaningful output
```

---

## Key Takeaways

### **Quaternion Normalization**:
- **When**: After every quaternion operation
- **Why**: Numerical drift breaks rotation validity
- **How**: Safe division + continuity enforcement
- **Result**: Norm errors < 1e-6, zero discontinuities

### **Coordinate Systems**:
- **OptiTrack**: X=Right, Y=Up, Z=Forward (mm)
- **ISB**: X=Forward, Y=Up, Z=Right (m)
- **Transform**: Axis reordering + 90° rotation + unit conversion
- **Validation**: Check magnitude, sign, and consistency

### **Reference Detection**:
- **Goal**: Find anatomical zero (calibration pose)
- **Method**: Sliding window on motion profile
- **Thresholds**: <5°/s motion, >1s duration, <10s placement
- **Validation**: Stability, consistency, ground truth (optional)

All three work together to ensure **biomechanically valid, reproducible joint angles** for research publication. ✓
