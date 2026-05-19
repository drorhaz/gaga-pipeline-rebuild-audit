# Joint Statistics Quality Control Guide
## Quick Reference for Reading ROM & Angular Velocity Tables

**Location:** Notebook 06, Cell 24 (Joint Statistics)  
**Purpose:** Identify tracking errors in high-intensity dance motion capture

---

## 📊 What the Numbers Mean

| Metric | Unit | What It Measures | Example |
|--------|------|------------------|---------|
| **ROM** | degrees (°) | Maximum angular excursion during entire recording | Shoulder: -30° to +120° = **150° ROM** |
| **Max Vel** | deg/s | Fastest rotational speed achieved | Quick arm swing = **800 °/s** |
| **Mean Vel** | deg/s | Average rotational speed throughout | Overall intensity = **85 °/s** |

---

## 🚦 Quick Interpretation Guide

### ✅ GOOD DATA (Accept)

**Typical ranges for Gaga dance:**

```
Shoulders:     ROM 100-180°,    Max Vel 300-800 °/s
Hips:          ROM 60-120°,     Max Vel 200-500 °/s
Spine:         ROM 50-100°,     Max Vel 150-400 °/s
Elbows/Knees:  ROM 80-150°,     Max Vel 200-600 °/s
Hands/Feet:    ROM 30-80°,      Max Vel 150-400 °/s
```

**Example of GOOD data:**
```
Joint: RightShoulder
  ROM: 145.3°
  Max Vel: 685.2 °/s
  Mean Vel: 124.5 °/s

✓ Within expected Gaga range
→ ACCEPT
```

---

### ⚠️ SUSPICIOUS DATA (Review)

**Triggers:**
- ROM > 200° (but < 300°)
- Max Vel > 1000 °/s (but < 1200 °/s)
- Large left/right asymmetry (>100° ROM difference)

**Example:**
```
Joint: RightElbow
  ROM: 215.8°
  Max Vel: 1050.3 °/s
  Mean Vel: 280.1 °/s

⚠ Exceeds typical range but not impossible
⚠ Could be extreme Gaga OR tracking error
→ REVIEW with Section 5 visualization
```

**What to do:**
1. Open Master Audit (notebook 07)
2. Go to Section 5 (Synchronized Visualization)
3. Inspect the flagged joint visually
4. Look for gimbal lock or marker jumps

---

### ❌ BAD DATA (Reject)

**Automatic rejection criteria:**

| Issue | Threshold | What It Indicates |
|-------|-----------|-------------------|
| ROM too high | > 300° | Gimbal lock, marker swap |
| ROM zero | = 0° (but dancer moved) | Data processing error |
| Velocity too high | > 1200 °/s | Marker jump, tracking loss |
| Velocity zero | = 0 °/s (but ROM > 0) | Computation error |
| Impossible anatomy | Elbow >180°, Knee >180° | Marker swap |

**Example:**
```
Joint: RightWrist
  ROM: 340.5°
  Max Vel: 1450.8 °/s
  Mean Vel: 780.2 °/s

✗ ROM exceeds anatomical limits
✗ Velocity exceeds physiological limits
→ REJECT: Tracking failure
```

---

## 🔍 Common Red Flags

### 1. **All Zeros**
```
Hips:   ROM 0.0°, Max Vel 0.0 °/s
Spine:  ROM 0.0°, Max Vel 0.0 °/s
...
```
**Problem:** Data processing error or missing columns  
**Action:** Check earlier cells (3-11), re-run if needed

---

### 2. **Extreme Asymmetry**
```
LeftShoulder:  ROM 165.3°, Max Vel 685.2 °/s
RightShoulder: ROM 23.1°,  Max Vel 45.8 °/s
```
**Problem:** One side has tracking issues (occlusion, marker loss)  
**Action:** REVIEW right shoulder, likely reject this take

---

### 3. **Small Body Parts with Huge ROM**
```
RightHandThumb1: ROM 285.4°, Max Vel 1180.5 °/s
```
**Problem:** Marker swap (thumb marker placed on wrist)  
**Action:** REJECT, check physical marker placement

---

### 4. **Impossible Joint Angles**
```
RightElbow: ROM 195.3° (elbows max ~150°)
LeftKnee:   ROM 185.7° (knees max ~160°)
```
**Problem:** Marker swap or gimbal lock  
**Action:** REJECT

---

## 🎯 The "Gaga-Aware" Thresholds

Traditional motion capture QC was designed for **walking**, not **expressive dance**.

### Why We Need Special Thresholds:

| Joint | Normal Gait | Gaga Dance | Multiplier |
|-------|-------------|------------|------------|
| Shoulder ROM | 80° | 100-180° | **1.5x - 2.25x** |
| Shoulder Velocity | 300 °/s | 300-800 °/s | **1.0x - 2.7x** |
| Hip ROM | 45° | 60-120° | **1.3x - 2.7x** |
| Hip Velocity | 200 °/s | 200-500 °/s | **1.0x - 2.5x** |

**The Strategy:**
- **Normal × 1.5 = PASS** (expected Gaga range)
- **Normal × 2.5 = REVIEW** (extreme but plausible)
- **Beyond anatomical limits = REJECT** (tracking error)

This prevents rejecting valid, intense dance data!

---

## 📋 Step-by-Step: How to Use This Table

### Step 1: Run Notebook 06
Execute all cells in order → Cell 24 generates the statistics table

### Step 2: Check for Automatic Flags
Look at the "AUTOMATIC QUALITY FLAGS" section in the output:
- ✅ ALL CLEAR → proceed to export
- ⚠️ REVIEW → inspect flagged joints
- ❌ REJECT → consider rejecting this take

### Step 3: Manual Inspection (if flags exist)
1. Note which joints are flagged
2. Open Notebook 07 (Master Audit)
3. Go to Section 5 (Synchronized Visualization)
4. Use the slider to inspect flagged joints
5. Look for:
   - Unnatural rotations (gimbal lock)
   - Sudden jumps (marker loss)
   - Flipping/spinning (coordinate system errors)

### Step 4: Make Decision
- **ACCEPT:** All joints look good → proceed
- **REVIEW:** Flag for supervisor inspection
- **REJECT:** Clear tracking failure → exclude from analysis

---

## 🎭 Real-World Examples

### Example 1: Valid Intense Dance ✅
```
================================================================================
Sample Joint Statistics (Top 5 by ROM):
--------------------------------------------------------------------------------
Joint                          | ROM (°)    | Max Vel (°/s)   | Mean Vel (°/s) 
--------------------------------------------------------------------------------
LeftShoulder                   | 165.3      | 685.2           | 124.5          
RightShoulder                  | 158.7      | 712.8           | 118.9          
LeftHip                        | 92.4       | 380.5           | 68.3           
Spine1                         | 78.2       | 245.1           | 42.7           
Neck                           | 54.8       | 198.3           | 35.2           

AUTOMATIC QUALITY FLAGS:
✅ ALL CLEAR: No quality issues detected
   All joints within expected Gaga dance ranges
```
**Verdict:** ACCEPT ✅

---

### Example 2: Suspicious but Reviewable ⚠️
```
================================================================================
Sample Joint Statistics (Top 5 by ROM):
--------------------------------------------------------------------------------
Joint                          | ROM (°)    | Max Vel (°/s)   | Mean Vel (°/s) 
--------------------------------------------------------------------------------
RightElbow                     | 215.8      | 1050.3          | 280.1          
LeftShoulder                   | 172.4      | 820.5           | 135.2          
RightShoulder                  | 168.9      | 795.3           | 128.7          

AUTOMATIC QUALITY FLAGS:
⚠️  REVIEW: 1 joint(s) with high ROM (200-300°):
   - RightElbow: 215.8° (check for gimbal lock)
⚠️  REVIEW: 1 joint(s) with high velocity (1000-1200 °/s):
   - RightElbow: 1050.3 °/s (check for marker jump)
```
**Verdict:** REVIEW ⚠️ (inspect RightElbow visually)

---

### Example 3: Clear Tracking Failure ❌
```
================================================================================
Sample Joint Statistics (Top 5 by ROM):
--------------------------------------------------------------------------------
Joint                          | ROM (°)    | Max Vel (°/s)   | Mean Vel (°/s) 
--------------------------------------------------------------------------------
RightWrist                     | 340.5      | 1450.8          | 780.2          
LeftShoulder                   | 168.3      | 685.7           | 122.8          
RightShoulder                  | 25.4       | 58.2            | 12.3           

AUTOMATIC QUALITY FLAGS:
❌ REJECT: 1 joint(s) with impossible ROM (>300° or 0°):
   - RightWrist: 340.5° (tracking failure)
❌ REJECT: 1 joint(s) with impossible velocity (>1200 °/s):
   - RightWrist: 1450.8 °/s (tracking failure)
```
**Verdict:** REJECT ❌ (right wrist marker swap or loss)

---

## 📚 References

- **Longo et al. (2022):** Biomechanics of high-intensity dance movement
- **Wu et al. (2002, 2005):** ISB standards for joint coordinate systems
- **Winter (2009):** Biomechanics and Motor Control of Human Movement

---

## 💡 Pro Tips

1. **Compare left vs right:** Large asymmetries usually indicate tracking issues on one side
2. **Check hands/feet first:** Small body parts are most prone to marker swaps
3. **Trust the automatic flags:** They're calibrated for Gaga-specific thresholds
4. **When in doubt, REVIEW:** Better safe than analyzing corrupted data
5. **Document your decisions:** Note why you accepted/rejected each take

---

## Need Help?

- **Zero values?** → Check Cell 13 diagnostic output
- **Column naming errors?** → Verify `angle_name` in kinematics_map
- **Kernel hanging?** → Restart kernel, re-run cells 1-24 in order
- **Strange asymmetry?** → Inspect with Section 5 visualization

---

**Last Updated:** 2026-01-22  
**For:** Gaga Motion Analysis Pipeline v2.0
