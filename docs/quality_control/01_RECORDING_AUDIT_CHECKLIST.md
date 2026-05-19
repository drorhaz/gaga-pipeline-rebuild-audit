# 📋 BIOMECHANICAL MOTION CAPTURE RECORDING AUDIT CHECKLIST

## Purpose
This checklist provides a standardized audit protocol for each motion capture recording to ensure compliance with biomechanical research standards and pipeline quality requirements.

---

## 🔍 CHECKLIST STRUCTURE

Each recording must pass through 7 audit stages corresponding to pipeline steps:

- ✅ **PASS**: Meets standard
- ⚠️ **WARN**: Acceptable but monitor
- ❌ **FAIL**: Does not meet standard
- 🔄 **REVIEW**: Manual review required

---

## STAGE 1: DATA ACQUISITION & LOADING

### 1.1 File Integrity
- [ ] CSV file opens without errors
- [ ] File size > 0 bytes
- [ ] Expected skeleton structure detected
- [ ] Time vector is monotonic (no backwards jumps)

**Critical Thresholds:**
- Time monotonicity violations: 0 (FAIL if > 0)

### 1.2 Capture System Quality
- [ ] OptiTrack system error < 1.0 mm (PASS)
- [ ] OptiTrack system error < 2.0 mm (WARN)
- [ ] OptiTrack system error ≥ 2.0 mm (FAIL)

**Data Quality Standards:**
```
✅ GOLD:   System error < 0.5 mm
✅ PASS:   System error < 1.0 mm
⚠️ WARN:   System error < 2.0 mm
❌ FAIL:   System error ≥ 2.0 mm
```

### 1.3 Skeleton Completeness
- [ ] All expected joints detected (51/51)
- [ ] Missing joints documented
- [ ] Critical joints present (Hips, Spine, L/R Hand, L/R Foot)

**Critical Joints (Cannot Proceed Without):**
- Hips (root)
- LeftHand, RightHand
- LeftFoot, RightFoot
- Spine, Spine1, Neck, Head

### 1.4 Recording Duration
- [ ] Duration > 10 seconds (minimum for analysis)
- [ ] Duration < 600 seconds (10 min - typical max)
- [ ] Expected frame count = duration × fps ± 1%

**Standards:**
- Minimum recording: 10 seconds
- Recommended: 30-120 seconds for dance phrases

### 1.5 Sampling Rate Validation
- [ ] Actual FPS = 120 Hz ± 0.5%
- [ ] Frame timestamps are regular (std(dt) < 0.001)
- [ ] No dropped frames detected (missing frame indices)

**Sampling Rate Standards (Wu et al. 2005):**
```
✅ 100-240 Hz: Suitable for human motion
✅ 120 Hz: Standard for dance/expressive movement
⚠️ <100 Hz: May miss rapid movements
❌ <60 Hz: Inadequate temporal resolution
```

### 1.6 Initial Data Quality
- [ ] Missing position data < 5% (PASS)
- [ ] Missing position data < 10% (WARN)
- [ ] Missing position data ≥ 10% (FAIL)
- [ ] Missing rotation data < 5% (PASS)
- [ ] Missing rotation data ≥ 5% (FAIL - critical)

**NaN Tolerance:**
- Position: < 5% PASS, < 10% WARN, ≥ 10% FAIL
- Rotation: < 5% PASS, ≥ 5% FAIL (stricter for quaternions)

---

## STAGE 2: PREPROCESSING & GAP FILLING

### 2.1 Artifact Detection
- [ ] Velocity artifact detection executed
- [ ] MAD multiplier = 6.0 (conservative threshold)
- [ ] Artifact mask percentage < 5% (PASS)
- [ ] Artifact mask percentage < 10% (WARN)
- [ ] Artifact mask percentage ≥ 10% (FAIL - suspect data quality)

**Artifact Standards (Skurowski et al.):**
```
✅ <1%:  Excellent capture quality
✅ <5%:  Normal capture quality
⚠️ <10%: Acceptable with review
❌ ≥10%: Systematic capture issues
```

### 2.2 Gap Filling Quality
- [ ] Maximum gap ≤ 100 ms (12 frames @ 120 Hz) (PASS)
- [ ] Maximum gap ≤ 200 ms (24 frames @ 120 Hz) (WARN)
- [ ] Maximum gap > 200 ms (FAIL - exceeds interpolation limit)

**Gap Filling Standards (Biomechanics Consensus):**
```
✅ ≤ 100 ms (12 frames):  Safe interpolation
⚠️ ≤ 200 ms (24 frames):  Acceptable with caution
❌ > 200 ms:               Unreliable interpolation
```

- [ ] Number of gaps documented
- [ ] Gap distribution analyzed (clustered vs. scattered)
- [ ] Interpolation method documented (Linear/Cubic/SLERP)

### 2.3 Bone Length Stability (Rigid Body QC)
- [ ] Mean bone CV < 1.0% (GOLD - rigid body ideal)
- [ ] Mean bone CV < 1.5% (PASS - acceptable soft tissue)
- [ ] Mean bone CV < 2.5% (WARN - monitor for marker slip)
- [ ] Mean bone CV ≥ 2.5% (FAIL - rigid body assumption violated)

**Bone CV Standards:**
```
✅ GOLD:   CV < 1.0%  (rigid body maintained)
✅ PASS:   CV < 1.5%  (acceptable variation)
⚠️ WARN:   CV < 2.5%  (soft tissue artifact concern)
❌ FAIL:   CV ≥ 2.5%  (marker slippage likely)
```

### 2.4 Skeletal Alert Review
- [ ] Number of bone alerts < 3 (PASS)
- [ ] Number of bone alerts < 5 (WARN)
- [ ] Number of bone alerts ≥ 5 (FAIL - systematic issue)
- [ ] Worst bone identified and documented
- [ ] Alert bones consistent across runs (marker placement issue)

**Common Problem Bones:**
- Head → Neck (soft tissue)
- Hand segments (small bones, rapid motion)
- Spine segments (truncal flexion artifacts)

### 2.5 Post-Processing Data Completeness
- [ ] Post-gap-fill missing data < 2% (PASS)
- [ ] All critical joints have complete trajectories
- [ ] Quaternion normalization errors < 0.01

---

## STAGE 3: RESAMPLING TO UNIFORM GRID

### 3.1 Time Grid Quality
- [ ] Target FPS = 120 Hz achieved
- [ ] Time grid std(dt) < 1e-9 (perfect grid)
- [ ] Temporal status = "PERFECT"
- [ ] No NaN introduction during resampling

**Temporal Grid Standards:**
```
✅ PERFECT: std(dt) < 1e-9 (machine precision)
⚠️ GOOD:    std(dt) < 1e-6 (sub-microsecond)
❌ POOR:    std(dt) ≥ 1e-6 (filter assumption violated)
```

### 3.2 Interpolation Method Validation
- [ ] Position method = CubicSpline (smooth derivatives)
- [ ] Rotation method = SLERP (geodesic path)
- [ ] Extrapolation disabled (boundary protection)

**Method Requirements:**
- Positions: Cubic spline (C² continuity for acceleration)
- Rotations: SLERP only (Euler interpolation forbidden)

---

## STAGE 4: FILTERING (WINTER'S METHOD)

### 4.1 Winter Analysis Execution
- [ ] Winter residual analysis completed successfully
- [ ] Cutoff frequency within expected range (4-10 Hz for dance)
- [ ] Cutoff ≠ fmax (12 Hz) - would indicate method failure
- [ ] Multi-signal analysis used (top 5 dynamic markers)

**Winter Cutoff Standards (Dance Kinematics):**
```
✅ 6-10 Hz:   Expected range for dance
⚠️ 4-6 Hz:    Conservative (may over-smooth rapid motion)
⚠️ 10-12 Hz:  Liberal (may retain noise)
❌ = 12 Hz:   Method failure (data pre-smoothed or static)
```

### 4.2 Biomechanical Guardrails
- [ ] Trunk minimum = 6.0 Hz enforced
- [ ] Distal minimum = 8.0 Hz enforced
- [ ] Guardrail strategy documented (multi-signal vs. trunk-global)
- [ ] Guardrail corrections logged (if applied)

**Guardrail Rationale:**
- Trunk (pelvis, spine): Slower, stable motion → 6 Hz min
- Distal (hands, feet): Faster, expressive motion → 8 Hz min
- Prevents over-smoothing of rapid dance movements

### 4.3 Filter Characteristics
- [ ] Filter order = 2 (2nd-order Butterworth - standard)
- [ ] Zero-phase filtering = TRUE (filtfilt applied)
- [ ] Filter applied to positions only (not quaternions)
- [ ] Representative columns documented

**Filter Standards (Winter 2009):**
```
✅ 2nd-order Butterworth + filtfilt (zero-phase)
✅ Applied to positions only
❌ Never filter quaternion components directly
```

### 4.4 Filtering Quality Metrics
- [ ] Number of valid position columns documented
- [ ] Number of excluded columns < 10% (PASS)
- [ ] Exclusion reasons logged (NaN, missing, etc.)
- [ ] Filter cutoff reasonable for body region

---

## STAGE 5: REFERENCE DETECTION & CALIBRATION

### 5.1 Static Reference Window Detection
- [ ] Reference window found in first 5 seconds
- [ ] Window duration = 1.0 second
- [ ] Motion metric < 0.1 rad/s (mean angular velocity)
- [ ] Motion std < 0.05 rad/s (stability check)
- [ ] Fallback flag = FALSE (criteria-based selection, not fallback)

**Reference Quality Standards:**
```
✅ PASS:     Motion < 0.1 rad/s, std < 0.05 rad/s
⚠️ REVIEW:   Fallback window used (no quiet stance found)
❌ FAIL:     No stable window in first 10 seconds
```

### 5.2 Reference Stability
- [ ] Reference stability < 2.0 mm (PASS - excellent)
- [ ] Reference stability < 4.0 mm (WARN - acceptable)
- [ ] Reference stability ≥ 4.0 mm (FAIL - unstable reference)

**Stability Standards:**
```
✅ < 2 mm:  GOLD - minimal sway
✅ < 4 mm:  PASS - normal quiet stance
⚠️ < 6 mm:  WARN - elevated sway (elderly/fatigue)
❌ ≥ 6 mm:  FAIL - not a stable reference
```

### 5.3 Markley Mean Quaternion QC
- [ ] Identity error < 0.1 rad (5.7°) - reference self-consistency
- [ ] Reference std < 0.05 rad (2.9°) - window stability
- [ ] All visualization joints have valid references

**Identity Error (Reference Self-Consistency):**
- Mean deviation of reference quaternions from identity
- < 0.1 rad: Stable reference pose
- ≥ 0.1 rad: Significant motion during "static" window

### 5.4 V-Pose Calibration (If Applicable)
- [ ] Arm elevation offset detected
- [ ] Left arm offset < 5° (no correction needed) OR corrected
- [ ] Right arm offset < 5° (no correction needed) OR corrected
- [ ] Offsets logged in reference_summary.json
- [ ] Calibration grade assigned (GOLD/SILVER/BRONZE)

**V-Pose Standards (CAST Technique - Rácz et al.):**
```
✅ < 5°:   Acceptable calibration pose
⚠️ 5-15°:  Significant offset (correction applied)
❌ > 15°:  Poor calibration pose (re-capture recommended)
```

### 5.5 Reference Metadata Completeness
- [ ] Reference time window documented (start/end)
- [ ] Joints used in detection listed
- [ ] Window variance score recorded
- [ ] Search parameters logged (duration, step size)

---

## STAGE 6: KINEMATIC FEATURE CALCULATION

### 6.1 Angular Velocity (Omega)
- [ ] Maximum angular velocity < 2000 °/s (physiological limit)
- [ ] Mean angular velocity reasonable for task (20-50 °/s for dance)
- [ ] No NaN values in omega calculations
- [ ] Omega magnitude computed correctly

**Angular Velocity Physiological Limits:**
```
✅ Mean 20-50 °/s:    Typical dance movement
⚠️ Max 1000-2000 °/s: Rapid ballistic movements
⚠️ Max > 2000 °/s:    Suspect noise or artifacts
❌ Max > 5000 °/s:    Unphysiological (filter failure)
```

### 6.2 Linear Acceleration
- [ ] Maximum acceleration < 50 m/s² (5g - reasonable for dance)
- [ ] Mean acceleration reasonable for task (< 10 m/s²)
- [ ] Acceleration spikes investigated (artifacts vs. impacts)

**Acceleration Physiological Limits:**
```
✅ Mean < 5 m/s²:   Normal continuous motion
⚠️ Max < 50 m/s²:   Dance with jumps/impacts
⚠️ Max 50-100 m/s²: Ballistic or impact events
❌ Max > 100 m/s²:  Unphysiological (noise amplification)
```

### 6.3 Rotation Vector (Rotvec) Quality
- [ ] Rotvec magnitude represents joint excursion from reference
- [ ] No gimbal lock artifacts (e2 angle ≠ ±90° for critical joints)
- [ ] Rotvec computed from quaternions (not Euler angles)

### 6.4 Signal Quality Metrics
- [ ] Velocity residual RMS documented
- [ ] Dominant frequency < 10 Hz (dance frequency range)
- [ ] Quaternion normalization error < 0.01 (PASS)
- [ ] Quaternion normalization error < 0.1 (WARN)
- [ ] Quaternion normalization error ≥ 0.1 (FAIL)

**Signal Quality Standards:**
```
✅ Quat norm error < 0.01:  Excellent quaternion handling
⚠️ Quat norm error < 0.10:  Acceptable numerical drift
❌ Quat norm error ≥ 0.10:  Quaternion corruption
```

### 6.5 Effort Metrics
- [ ] Total path length computed (mm)
- [ ] Intensity index calculated (normalized effort)
- [ ] Outlier frame count < 1% of total frames
- [ ] Effort metrics reasonable for task duration

**Effort Metric Standards:**
```
Path Length:     Movement economy indicator
Intensity Index: Normalized by duration (effort/time)
Outlier Frames:  < 1% acceptable, > 5% investigate
```

### 6.6 ISB Euler Angles (If Computed)
- [ ] Correct Euler sequence per joint (ZXY for knee/elbow, YXY for shoulder)
- [ ] Gimbal lock check performed (e2 angle range)
- [ ] Euler angles computed from relative rotations (not global)
- [ ] Anatomical interpretability validated

---

## STAGE 7: FINAL QUALITY ASSURANCE

### 7.1 Pipeline Status
- [ ] Overall pipeline status = "PASS"
- [ ] All processing stages completed without critical errors
- [ ] No manual interventions required
- [ ] Processing timestamp documented

### 7.2 Quality Score Calculation
- [ ] Quality score ≥ 90 (EXCELLENT)
- [ ] Quality score ≥ 75 (GOOD - research acceptable)
- [ ] Quality score ≥ 50 (FAIR - review recommended)
- [ ] Quality score < 50 (POOR - reject or re-capture)

**Quality Score Components:**
```
Base Score: 100
Deductions:
- Missing data: -5 per %
- Gap size: -1 per 10ms
- Bone CV: -10 per %
- Skeletal alerts: -5 per alert
- Poor reference: -15 if stability > 4mm
- Quat errors: -10 if norm error > 0.1
```

### 7.3 Research Decision Rule
- [ ] **ACCEPT**: Pipeline PASS + Score ≥75 + Ref PASS + Bone CV <1.5%
- [ ] **REVIEW**: Pipeline PASS + Score ≥50 (one or more criteria borderline)
- [ ] **REJECT**: Pipeline FAIL or Score <50 (re-capture recommended)

### 7.4 Metadata Completeness Audit
- [ ] Subject ID present
- [ ] Session/timepoint documented
- [ ] Processing version logged
- [ ] All intermediate files saved (step_01 through step_06)
- [ ] Master audit log entry created

---

## 🎯 CRITICAL FAILURE CRITERIA (IMMEDIATE REJECT)

Any of these conditions result in automatic rejection:

❌ **Data Integrity:**
- File corrupted or cannot be parsed
- Time vector not monotonic
- Critical joints missing (> 10% of skeleton)

❌ **Capture Quality:**
- OptiTrack system error ≥ 2.0 mm
- Missing data > 10% after preprocessing

❌ **Biomechanical Validity:**
- Bone CV ≥ 2.5% (rigid body violation)
- Maximum acceleration > 100 m/s² (unphysiological)
- Maximum angular velocity > 5000 °/s (unphysiological)

❌ **Processing Failures:**
- Winter analysis returns fmax (12 Hz) - indicates pre-smoothed data
- Reference window not found in first 10 seconds
- Quaternion normalization error ≥ 0.1

---

## 📊 AUDIT REPORT TEMPLATE

```
RECORDING AUDIT REPORT
======================
Run ID: [RUN_ID]
Date Processed: [DATE]
Auditor: [NAME]

STAGE SUMMARY:
□ Stage 1 - Loading:        [✅/⚠️/❌]
□ Stage 2 - Preprocessing:  [✅/⚠️/❌]
□ Stage 3 - Resampling:     [✅/⚠️/❌]
□ Stage 4 - Filtering:      [✅/⚠️/❌]
□ Stage 5 - Reference:      [✅/⚠️/❌]
□ Stage 6 - Kinematics:     [✅/⚠️/❌]
□ Stage 7 - Final QA:       [✅/⚠️/❌]

QUALITY METRICS:
- Quality Score: [XX]/100
- Research Decision: [ACCEPT/REVIEW/REJECT]
- Bone Stability CV: [X.X]%
- Reference Stability: [X.X] mm
- Filter Cutoff: [X.X] Hz
- Max Gap: [XX] ms

CRITICAL ISSUES:
[List any critical failures or warnings]

RECOMMENDATIONS:
[Accept for research / Review specific issues / Re-capture]

SIGNATURE: ____________  DATE: _______
```

---

## 📚 REFERENCE STANDARDS

This checklist is based on:

1. **Wu et al. (2005)** - ISB recommendations on joint coordinate systems
2. **Winter (2009)** - Biomechanics and Motor Control of Human Movement
3. **Skurowski et al.** - Method for truncating artifacts in optical motion capture
4. **Rácz et al. (2025)** - Static precision of instrumented pointers (CAST)
5. **OptiTrack Validation Studies** - Continuous measurement validation

---

## 🔄 AUDIT WORKFLOW

1. **Automated**: Pipeline generates step_XX_summary.json files
2. **Automated**: Master quality report aggregates metrics
3. **Manual**: Researcher reviews audit checklist for REVIEW cases
4. **Manual**: Final decision documented and signed
5. **Archive**: Audit report saved with recording derivatives

---

**Version:** 1.0  
**Date:** January 2026  
**Next Review:** After first 50 recordings or 6 months
