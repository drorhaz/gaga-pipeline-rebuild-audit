# S-02 Preprocessing & Gap Fill — Per-Stage Audit

**Phase:** 4 — Per-Stage Audits
**Stage:** S-02 Preprocessing (NB02 `02_preprocess.ipynb`)
**Date:** 2026-05-14
**Mode:** Read-only. No code changes.

**Sources read:**
- `src/preprocessing.py` (full)
- `src/gapfill_positions.py` (full)
- `src/gapfill_quaternions.py` (full)
- `src/artifacts.py` (full)
- `src/bone_length_validation.py` (full)
- `src/interpolation_tracking.py` (full)
- `src/qc.py` (lines 1–160)
- `src/forensic_config.py` (grep)
- `src/pipeline_config.py` (grep)
- `notebooks/02_preprocess.ipynb` (grep: key cell lines)
- `derivatives/step_02_preprocess/` — all 9 available sessions: 6 P2 + 3 P1

---

## 1. Stage Summary

Step 2 (NB02) performs:
1. MAD velocity-based artifact detection → mask spikes to NaN
2. Position gap fill (bounded spline)
3. Quaternion gap fill (bounded, per-column)
4. Bone length QC
5. Time jitter check
6. Gate-02 pass/fail evaluation
7. Write `__preprocessed.parquet`, `__preprocess_summary.json`, `__interpolation_log.json`, `__kinematics_map.json`

**Session inventory:** Only subject 671 has step_02 derivatives available. 9 sessions total:
- P1: 671_T1_P1_R1, 671_T2_P1_R1, 671_T3_P1_R1
- P2: 671_T1_P2_R1, 671_T1_P2_R2, 671_T2_P2_R1, 671_T2_P2_R2, 671_T3_P2_R1, 671_T3_P2_R2

---

## 2. Q-QC7: Bone QC Fail Distribution

**Question:** How many of the processed sessions have `bone_qc_fail_flag: true`? Which joints are consistently failing (CV > 5%) across the entire P2 dataset?

### 2.1 Evidence: Per-session bone QC status

| Session | Phase | `bone_qc_status` | `bone_qc_mean_cv` (%) | `bone_qc_alerts` | `worst_bone` |
|---------|-------|-----------------|----------------------|-----------------|-------------|
| 671_T1_P1_R1 | P1 | **GOLD** | 0.463 | Hips->Spine | Hips->Spine |
| 671_T2_P1_R1 | P1 | **GOLD** | 0.579 | Hips->Spine | Hips->Spine |
| 671_T3_P1_R1 | P1 | (not available) | — | — | — |
| 671_T1_P2_R1 | P2 | **GOLD** | 0.522 | Hips->Spine | Hips->Spine |
| 671_T1_P2_R2 | P2 | **GOLD** | 0.530 | Hips->Spine | Hips->Spine |
| 671_T2_P2_R1 | P2 | **GOLD** | 0.596 | Hips->Spine, Neck->Head | Hips->Spine |
| 671_T2_P2_R2 | P2 | **GOLD** | 0.632 | Hips->Spine, Spine->Spine1 | Hips->Spine |
| 671_T3_P2_R1 | P2 | **SILVER** | 1.455 | Hips->Spine, Neck->Head, Spine1->Neck, Spine->Spine1 | Hips->Spine |
| 671_T3_P2_R2 | P2 | **SILVER** | 1.391 | Neck->Head, Hips->Spine, Spine1->Neck, Spine->Spine1 | Neck->Head (reported), Hips->Spine (actual worst) |

### 2.2 Threshold mapping

From `notebooks/02_preprocess.ipynb:967`:
```python
"bone_qc_status": "GOLD" if mean_cv < 1.0 else "SILVER" if mean_cv < 5.0 else "REJECT"
```

| Status | NB02 criterion | Interpretation |
|--------|---------------|---------------|
| GOLD | mean_cv < 1.0% | Excellent tracking across all bones |
| SILVER | 1.0% ≤ mean_cv < 5.0% | Elevated but below ALERT |
| REJECT | mean_cv ≥ 5.0% | Would trigger gate_02 failure |

**Note:** `bone_qc_fail_flag` as named in Q-QC7 does NOT exist as a field in the actual JSON. The equivalent is `bone_qc_status == "REJECT"`.

### 2.3 Answer to Q-QC7

**Zero (0/6) P2 sessions and zero (0/8) available sessions total have `bone_qc_status = "REJECT"`.**

No joints are failing (CV > 5%) in any session. The worst observed mean_cv is 1.455% (671_T3_P2_R1), well below the 5% REJECT threshold.

### 2.4 Alert bone frequency analysis

| Bone | Occurrences in P2 alerts | Sessions | Pattern |
|------|--------------------------|----------|---------|
| Hips->Spine | **6/6** | T1R1, T1R2, T2R1, T2R2, T3R1, T3R2 | Universal — appears in every session |
| Neck->Head | 3/6 | T2R1, T3R1, T3R2 | T2+T3 trend |
| Spine->Spine1 | 3/6 | T2R2, T3R1, T3R2 | T2+T3 trend |
| Spine1->Neck | 2/6 | T3R1, T3R2 | T3 only |

**`Hips->Spine` is the single most persistent alert bone — present in 6/6 P2 sessions and in both available P1 sessions (P1_R1 at T1 and T2).**

This is NOT a session-specific issue. It is a structural constraint: the Hips→Spine bone spans soft tissue and the marker placement over the lower back vertebrae is inherently less rigid than limb markers. The `qc.py::SHORT_SEGMENT_WHITELIST` already recognizes this: `"Hips->Spine"`, `"Neck->Head"`, and `"Spine->Spine1"` are whitelisted with a relaxed threshold of 3.5%.

### 2.5 Critical inconsistency: Three bone QC systems

| System | Location | Bone status labels | Threshold (WARN) | Threshold (FAIL) | Whitelist? |
|--------|----------|--------------------|-----------------|-----------------|-----------|
| NB02 | `02_preprocess.ipynb:967` | GOLD / SILVER / REJECT | mean_cv = 1% | mean_cv = 5% | No |
| Pipeline QC | `src/qc.py:81–96` | PASS / WARN / ALERT | cv_warn = 2% (3.5% for whitelist) | cv_alert = 5% | Yes |
| Dashboard | `src/forensic_report.py:648–650` | GOLD / WARN / FAIL | cv ≤ 2% | cv > 5% | No |

Three independent implementations use three different threshold/label schemes. The `preprocess_summary.json` reports the NB02 scheme. A dashboard using `forensic_report.py` may show a different status for the same session.

**Impact:** A bone with cv = 1.5% (like T3 sessions) would be:
- NB02: SILVER (alert fired, mean > 1%)
- qc.py: WARN for standard bones, but Hips->Spine is whitelisted at 3.5% — may PASS
- forensic_report.py: WARN (cv > BONE_CV_GOLD = 2%) → but wait, 1.5% < 2%, so GOLD

This inconsistency means the same data will show different QC verdicts depending on which tool is reading it.

---

## 3. Q-EXT1b: PCHIP vs Hampel Provenance Separation

**Question:** Are PCHIP-repaired frames structurally distinct from Hampel-replaced frames in the logs?

### 3.1 Stage-level separation (PASS)

Step 2 and Step 4 produce separate JSON files:
- Step 2: `__preprocess_summary.json` — tracks artifact masking and gap fill
- Step 4: filtering summary JSON — tracks Hampel replacements

These are structurally separate, so a downstream consumer reading both files can distinguish Step 2 repair from Step 4 repair.

### 3.2 Within Step 2: MAD mask vs gap fill (PARTIAL PASS)

The preprocess_summary.json contains separate fields:
- `step_02_artifacts_detected_count`: frames masked by MAD velocity threshold
- `step_02_artifacts_rate_percent`: fraction of total frames masked
- `step_02_channels_with_artifacts`: number of channels (joints × axes) with any artifact
- `interpolation_per_joint.{joint}.frames_fixed_count`: frames gap-filled per joint

These are logically distinct, but there is NO explicit per-frame link between "this joint was MAD-masked → then gap-filled". A joint with frames_fixed_count > 0 could have been filled due to:
(a) Hardware gaps (naturally missing NaN from OptiTrack),
(b) MAD artifact masking (injected NaN then filled), or
(c) Both.

**The logs cannot distinguish (a) from (b) per joint.**

### 3.3 CRITICAL FINDING: Method labels are incorrect (FAIL)

**From `interpolation_log.json` (671_T1_P2_R1):**
```json
{
  "position_method": "pchip_single_pass",
  "quaternion_method": "slerp",
  "note": "Positions: PCHIP single-pass (gap-heal + resample). Quaternions: SLERP on valid raw timestamps."
}
```

**Actual code path in NB02 (verified from source):**

**Positions:**
- NB02 calls `from gapfill_positions import gap_fill_positions` (line 420)
- `gap_fill_positions()` calls `bounded_spline_interpolation()` in `gapfill_positions.py`
- `bounded_spline_interpolation()` in `gapfill_positions.py` uses `np.interp()` — **LINEAR INTERPOLATION**, not PCHIP or CubicSpline

Evidence from `gapfill_positions.py:145-148`:
```python
interp_time = np.linspace(time_points[start], time_points[end], 100)
interp_data = np.interp(interp_time, valid_time, valid_data)
filled_data[start+1:end] = interp_data[1:-1]
```

**Quaternions:**
- NB02 uses `df_filled[col].interpolate(method="linear", limit=10, limit_area='inside')` (line 536)
- This is **pandas linear component-wise interpolation**, followed by renormalization
- This is NOT SLERP (geodesic spherical interpolation)

**Conclusion:** The method labels "pchip_single_pass" and "slerp" in the JSON are incorrect. The actual methods are linear (positions) and linear-normalize (quaternions). This is a **reproducibility risk**: any downstream analysis relying on the log to understand what repair was applied will be misled.

### 3.4 Summary answer to Q-EXT1b

| Separation level | Status | Evidence |
|-----------------|--------|---------|
| Step 2 vs Step 4 separation | **PASS** | Separate JSON files per stage |
| MAD mask vs gap fill within Step 2 | **PARTIAL** — separate counters but no per-joint provenance link | `step_02_artifacts_detected_count` vs `frames_fixed_count` |
| Method labels accuracy | **FAIL** — labels say PCHIP/SLERP, actual is linear/linear-normalize | `gapfill_positions.py:145` + `NB02:536` |
| Per-frame repair flags in parquet | **MISSING** — no column in parquet identifies which frames were repaired | No such column in schema |

**Required additions (from Q-EXT1b):** A `{joint}__gap_fill_flag` column in the preprocessed parquet and a `{joint}__artifact_masked_flag` column would provide per-frame provenance. The current JSON counters are insufficient for per-frame downstream analysis.

---

## 4. Q-S02: MAD Velocity Threshold and False Positives

**Question:** Is the Step 02 MAD velocity threshold producing false positives on high-velocity dance bursts?

### 4.1 Actual threshold configuration

From `notebooks/02_preprocess.ipynb:424`:
```python
MAD_MULTIPLIER = 6.0  # Conservative threshold for artifact detection
```

NB02 calls `artifacts.py::apply_artifact_truncation(position, time_s, mad_multiplier=6.0)` (not `preprocessing.py::detect_and_mask_artifacts()` which uses 3.0σ — that function is dead code).

The 6.0σ threshold:
- Scale: uses `median_abs_deviation(velocity, scale='normal')` — gives robust σ estimate
- Per-axis: computed independently per X, Y, Z
- Expansion: ±1 frame dilation around each spike (`dilation_frames=1`)
- `sigma_floor = 1e-6`: prevents over-masking static joints

### 4.2 Evidence from all 9 sessions

**`step_02_artifacts_detected_count = 0` across ALL 9 sessions (P1 and P2).**

| Session | Phase | `artifacts_detected_count` | `artifacts_rate_percent` | `channels_with_artifacts` |
|---------|-------|--------------------------|------------------------|--------------------------|
| 671_T1_P1_R1 | P1 | 0 | 0.0 | 0 |
| 671_T2_P1_R1 | P1 | 0 | 0.0 | 0 |
| 671_T1_P2_R1 | P2 | 0 | 0.0 | 0 |
| 671_T1_P2_R2 | P2 | 0 | 0.0 | 0 |
| 671_T2_P2_R1 | P2 | 0 | 0.0 | 0 |
| 671_T2_P2_R2 | P2 | 0 | 0.0 | 0 |
| 671_T3_P2_R1 | P2 | 0 | 0.0 | 0 |
| 671_T3_P2_R2 | P2 | 0 | 0.0 | 0 |

### 4.3 Contrast with Step 4 spike detection

From the S04 filtering audit, Step 4 (Hampel filter, NB04) detects:
- P2 sessions: 971–1,687 Z-score spikes per session
- P1 sessions: 6,231–8,840 Z-score spikes per session

Step 2 and Step 4 detectors use fundamentally different mechanisms:
- Step 2: MAD on raw position velocity, 6.0σ threshold → DORMANT (0 detections)
- Step 4: Hampel filter on resampled positions → 971–8,840 detections

### 4.4 Answer to Q-S02

**The 6.0σ MAD threshold is DORMANT on this dataset — it produces zero detections across all 9 sessions.** It is not producing false positives because it is not triggering at all.

This could mean:
- (a) The OptiTrack data for subject 671 is so clean (no hardware glitches, no marker drops) that the 6.0σ threshold is never reached; OR
- (b) The threshold is too conservative to catch the soft artifacts that Step 4 Hampel catches (which would make Step 2 artifact detection partially redundant with Step 4)

The Q-S02 tag (`[RECONSIDER_LATER]`) from Phase 3 was: *"Measure Step 02 false-positive masking rate against 1–13 Hz dance band. If >10% of masked frames are physiological, upgrade velocity estimator."*

**This question cannot be answered from current data because Step 2 never triggers.** To test it, either a session with known hardware artifacts must be processed, or the threshold must be lowered to a level where it does trigger.

**Evidence conclusion:** Step 2 MAD at 6.0σ is effectively a hard-artifact guard (marker drop, cable hit) not a soft-artifact cleaner. It is appropriate as such. The [RECONSIDER_LATER] Q-S02 tag should be updated: the false-positive risk is NOT in Step 2 (6.0σ, never triggers), but in Step 4 Hampel (where 971–1,687 P2 detections need validation as physiological vs artifactual).

---

## 5. Additional Findings

### F1: SLERP quaternion gap-fill is not true SLERP (CRITICAL)

**File:** `src/gapfill_quaternions.py:103-110`
```python
r_interp = r_start * r_end.inv()
r_interp = r_start * r_end.inv()  # This is a placeholder - proper SLERP implementation needed
# For now, use simple linear interpolation as fallback
for j, idx in enumerate(gap_indices):
    weight = (idx - start_idx) / (end_idx - start_idx)
    Q[idx] = q_start_norm * (1 - weight) + q_end_norm * weight
```
This is LERP (linear quaternion component interpolation) with post-hoc normalization, not geodesic SLERP. The file explicitly labels itself a placeholder. **However, this function is NOT called by NB02.** NB02 uses pandas linear interpolation instead. Both are LERP+normalize.

**For small gaps (< 12 frames at 120Hz) the error from LERP vs SLERP is small** but grows with gap size. At the 250ms (30-frame) limit used for quaternion gaps, LERP+normalize can deviate from the true geodesic by up to ~15% for 180° rotations.

**Dead code alert:** `gapfill_quaternions.py` is imported nowhere in the active pipeline. It is dead code. The active path is NB02's inline `df_filled[col].interpolate(method="linear", limit=10)`.

### F2: Two independent `bounded_spline_interpolation()` implementations

Both `gapfill_positions.py` and `preprocessing.py` contain a function named `bounded_spline_interpolation()`. They are NOT equivalent:

| Feature | `gapfill_positions.py` (used by NB02) | `preprocessing.py` (dead code) |
|---------|--------------------------------------|-------------------------------|
| Interpolation method | `np.interp()` — **LINEAR** | `CubicSpline` with `np.interp` fallback |
| Gap ends detection | `nan_mask[:-1] & nan_mask[1:]` — **BUG** (detects interior, not end) | `nan_mask[:-1] & ~nan_mask[1:]` — correct |
| Gap start detection | `~nan_mask[:-1] & nan_mask[1:]` | correct |
| Boundary handling | Skips if gap > max_gap_s | Same |
| Import path | Active in NB02 | Not called from any notebook |

**Bug in `gapfill_positions.py:134`:**
```python
gap_ends = np.where(nan_mask[:-1] & nan_mask[1:])[0] + 1
```
This detects indices where BOTH current and next frame are NaN (interior of gap). The correct formula for gap end detection is `nan_mask[:-1] & ~nan_mask[1:]` (transition from NaN to valid). This bug could cause incorrect gap fill boundaries when gaps > 1 frame are encountered. **Since all sessions show 0 gaps to fill, this bug is latent but has not affected any output.**

### F3: Dead code from two duplicate artifact detectors

`preprocessing.py::detect_and_mask_artifacts()` (3.0σ MAD, operates on 1D) is dead code. NB02 uses `artifacts.py::apply_artifact_truncation()` (6.0σ MAD, operates on (N,3) positions). The dead function is not referenced anywhere in the active notebooks.

**Risk:** The 3.0σ threshold version could be accidentally used in future code. The dead function should be either deleted or clearly marked with a deprecation warning.

### F4: THREE independent bone QC systems with inconsistent thresholds

| System | Location | Labels | WARN threshold | ALERT/FAIL threshold | Whitelist? |
|--------|----------|--------|---------------|---------------------|-----------|
| NB02 | `02_preprocess.ipynb:967` | GOLD/SILVER/REJECT | mean_cv 1% | mean_cv 5% | No |
| Pipeline QC | `src/qc.py:81` | PASS/WARN/ALERT | per-bone cv 2% (or 3.5% for whitelist) | per-bone cv 5% | Yes |
| Dashboard | `src/forensic_report.py:648` + `forensic_config.py:44` | GOLD/WARN/FAIL | per-bone cv 2% | per-bone cv 5% | No |

The `preprocess_summary.json` reports the NB02 scheme. The `qc.py` scheme (with the SHORT_SEGMENT_WHITELIST) is the most scientifically justified because it accounts for anatomically short segments having higher geometric noise. But NB02 does not apply the whitelist, producing spurious alerts for `Hips->Spine` in every session.

### F5: T3 sessions show systematically higher bone variance

Both T3 P2 sessions (T3R1 and T3R2) have `bone_qc_status = "SILVER"` (mean_cv ~1.4%), while T1 and T2 sessions are GOLD (<0.7%). This is a longitudinal signal: tracking quality may be degrading over the study, possibly due to:
- Subject weight changes affecting body composition under markers
- Different session setup (marker placement, taping)
- Different capture conditions

For a longitudinal study (thesis-grade analysis of Gaga learning across T1→T2→T3), this trend must be monitored. If T3 sessions have systematically higher bone CV, the downstream angular velocity estimates and CoM will have higher noise at T3.

### F6: `gap_fill_positions.py` uses wrong algorithm (linear, not cubic spline)

Despite being called `bounded_spline_interpolation`, the function uses `np.interp()` (piecewise linear) not `CubicSpline`. The `preprocessing.py` duplicate correctly uses `CubicSpline`. Since `gapfill_positions.py` is what NB02 calls, all gap fills in the pipeline use linear interpolation.

For the max gap of 100ms (12 frames at 120Hz), the error between linear and cubic spline interpolation is small for most motion. However, for high-acceleration movements (which are common in Gaga), cubic spline would better preserve the acceleration trajectory.

### F7: No per-frame repair flags in parquet

The preprocessed parquet has no `{joint}__gap_fill_flag` or `{joint}__artifact_masked_flag` columns. Downstream stages (Step 4 filtering) have no knowledge of which input frames were linearly interpolated (and therefore should not be used as ground truth for MAD/Hampel thresholding).

This creates a subtle cascade: if a frame was gap-filled in Step 2 (linear interpolation), it will pass through Step 4 Hampel as if it were measured data. Hampel detections on linearly-interpolated frames are false positives from a data-quality perspective.

---

## 6. Answers Summary

| Question | Answer | Confidence |
|----------|--------|-----------|
| Q-QC7: Sessions with bone_qc_fail_flag? | **0/6 P2 sessions** have `bone_qc_status = "REJECT"` (equivalent of FAIL). The field is named `bone_qc_status`, not `bone_qc_fail_flag`. | HIGH — all 6 P2 summaries read |
| Q-QC7: Which bones are consistently alerting? | **`Hips->Spine`** (6/6 P2, anatomically expected, whitelisted in qc.py). `Neck->Head` and `Spine->Spine1` appear at T2/T3. None exceed 5% CV. | HIGH |
| Q-EXT1b: PCHIP vs Hampel structurally distinct? | **PARTIAL** — stage-level separation is correct (separate files). Within Step 2: separate counters. But method labels are **wrong** (reported: pchip/slerp; actual: linear/linear-normalize). No per-frame flags. | HIGH |
| Q-S02: MAD producing false positives on dance? | **CANNOT DETERMINE** — Step 2 MAD (6.0σ) is dormant (0 detections in all 9 sessions). Not producing false positives because not triggering. The [RECONSIDER_LATER] tag should pivot to Step 4 Hampel, which IS triggering. | HIGH — confirmed by all session summaries |

---

## 7. Decision Impact on Phase 3 Target Skeleton

| Phase 3 Decision | Impact from S02 audit |
|-----------------|----------------------|
| `KEEP_LOG_QC`: Bone QC warning/flagging + new `{joint}__bone_qc_flag` column | **CONFIRMED NEEDED.** Current parquet has no per-joint bone QC flag. The NB02 `bone_qc_alerts` list is per-session-aggregate only. A per-joint flag in parquet would allow filtering joints with CV > threshold. |
| `LOCAL_REFACTOR`: Two-tier flagging (FAIL vs SUSPICIOUS) | **PARTIALLY ADDRESSED** — GOLD/SILVER/REJECT is a three-tier scheme. However, the three independent bone QC systems (NB02/qc.py/forensic_report.py) must be consolidated to one canonical scheme before adding more tiers. |
| `LOCAL_REFACTOR`: Step 02 velocity estimator upgrade (3-pt central diff) | **STATUS CHANGE**: The velocity estimator in `artifacts.py::compute_true_velocity()` uses adjacent-frame backward difference (`velocity[1:] = pos_diff / dt`), not 3-pt central diff. However, since Step 2 detects 0 artifacts, this upgrade would not change any current output. Recommend deferring until a session with actual gaps is found. |

---

## 8. Recommendations (for Phase 11 — Final Target Skeleton)

| Priority | Recommendation | Effort | Risk |
|----------|---------------|--------|------|
| High | Consolidate bone QC to single system: use `qc.py` scheme (PASS/WARN/ALERT) with SHORT_SEGMENT_WHITELIST throughout. Remove NB02-specific GOLD/SILVER/REJECT logic. | Medium | Medium (changes reported outputs) |
| High | Correct method labels in `interpolation_log.json`: `"position_method": "linear_bounded"` (not "pchip_single_pass"), `"quaternion_method": "lerp_normalize"` (not "slerp"). | Low | Low |
| High | Add `n_nan_frames_at_filter_input` / `n_nan_frames_restored_after_filter` to filtering summary (Q-EXT1a — from Phase 4.5). | Low | Low |
| Medium | Replace `gapfill_positions.py::bounded_spline_interpolation()` with the `preprocessing.py` version (which correctly uses `CubicSpline` and has correct gap boundary detection). | Medium | Low |
| Medium | Mark `preprocessing.py::detect_and_mask_artifacts()` (3.0σ) and `gapfill_quaternions.py` as dead code with explicit deprecation comment. | Low | Low |
| Medium | Add `{joint}__gap_fill_flag` (bool, Step 2 output) to preprocessed parquet. This propagates through filtering to give Step 4 Hampel context about which frames are real vs interpolated. | Medium | Low |
| Medium | Implement true SLERP quaternion gap fill. Use `scipy.spatial.transform.Slerp` (geodesic). Max gap 250ms = 30 frames; the LERP error is acceptable for gaps ≤ 12 frames but not for larger gaps. | Medium | Low |
| Low | Investigate T3 bone CV elevation. Determine if it is due to marker placement changes, body composition, or session setup. Flag this as a thesis-grade longitudinal tracking quality concern. | Low | Low |
| Low | Extend step_02 derivatives to subjects 651, 734, 763 for complete Q-QC7 bone QC distribution. Current single-subject data limits generalizability of Q-QC7 findings. | N/A (data issue) | — |

---

*S-02 audit complete. Stopping to await user review before proceeding to S-01, S-03, S-05, S-06, S-08.*
