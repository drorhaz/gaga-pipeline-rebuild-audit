# S-05 Reference Detection — Stage Audit

**Date:** 2026-05-14
**Auditor:** Per-Stage Audit Agent (Phase 4 batch)
**Sources read:**
- `src/reference.py` (full — 315 lines)
- `derivatives/step_05_reference/671_T1_P1_R1_Take 2026-01-06 03.57.12 PM_001__reference_metadata.json` (representative)
- All 9 `__reference_metadata.json` via grep
**Status:** COMPLETE

---

## 1. What Step 05 does

`notebooks/05_reference_detection.ipynb` calls `src/reference.py` to:
1. Search the first `REF_SEARCH_SEC` seconds of the recording for the most-static upright window of duration `REF_WINDOW_SEC`.
2. Apply the **Gravity Guard**: reject candidate windows where Head is not at least `MIN_HEAD_PELVIS_VERTICAL_M` above Pelvis (prevents reference on crouched/lying positions).
3. Compute mean reference quaternion per joint using **Markley's eigendecomposition** (numerically stable, geodesic mean).
4. Flag the result with `ref_is_fallback` and `method`.
5. Write `__reference_metadata.json`, `__reference_map.json`, `__offsets_map.json`, `__reference_euler.json`, `__biomechanical_audit.json`, `__reference_summary.json`, `__reference_summary.csv`.

---

## 2. Fallback reference mechanism — flagging assessment

**Question:** Is the fallback reference mechanism properly flagged?

**Answer: YES — Fallback flagging is robust and multi-tier. Current data shows 0/9 fallbacks.**

### 2.1 Fallback paths coded in `reference.py`

| Method value | Condition | `ref_is_fallback` |
|---|---|---|
| `"criteria"` | Mean motion < thr_low AND std < thr_std AND gravity guard passed | False |
| `"strict_motion_and_gravity"` | Same, with gravity guard | False |
| `"fallback_min_motion"` | No window meets criteria; use window with lowest motion | **True** |
| `"fallback_first_window"` | No valid window, no gravity guard | **True** |
| `"fallback_insufficient_search"` | Fewer than 3 frames in search period | **True** |
| `"fallback_identity_gravity_guard_failed"` | No upright window found, gravity guard active | **True** |

All fallback paths set `ref_is_fallback = True`. The identity fallback (`t_pose_failed = True`) sets all joint quaternions to `[0,0,0,1]` (identity) with an explicit logger.warning. These are well-designed failure modes.

### 2.2 Current data: all 9 sessions use clean detection

| Session | ref_is_fallback | confidence_level | detection_method | time_window |
|---|---|---|---|---|
| 671_T1_P1_R1 | false | HIGH | auto_stable_window | [1.5, 2.5] |
| 671_T2_P1_R1 | false | HIGH | auto_stable_window | [1.5, 2.5] |
| 671_T3_P1_R1 | false | HIGH | auto_stable_window | [≈1.5, 2.5] |
| 671_T1_P2_R1 | false | HIGH | auto_stable_window | [1.5, 2.5] |
| 671_T1_P2_R2 | false | **MEDIUM** | auto_stable_window | — |
| 671_T2_P2_R1 | false | **MEDIUM** | auto_stable_window | — |
| 671_T2_P2_R2 | false | HIGH | auto_stable_window | — |
| 671_T3_P2_R1 | false | HIGH | auto_stable_window | — |
| 671_T3_P2_R2 | false | HIGH | auto_stable_window | — |

- 7/9 sessions: HIGH confidence
- 2/9 sessions: MEDIUM confidence (`671_T1_P2_R2`, `671_T2_P2_R1`)
- 0/9 sessions: fallback activated

**MEDIUM confidence** is defined in `reference_validation.py` (not inspected in full) and logged in `__reference_metadata.json`. It appears to correspond to the "fallback_min_motion" method where a window meets motion criteria but the gravity guard is less certain or the motion scores are borderline.

---

## 3. Markley mean quaternion

`reference.py::markley_mean_quat()` uses the eigendecomposition of the accumulation matrix:
```python
A += np.outer(q, q)
vals, vecs = np.linalg.eigh(A)
q_mean = vecs[:, np.argmax(vals)]
```
This is the correct, geodesic-consistent mean for unit quaternions. It handles the double-cover problem (sign ambiguity) by taking the eigenvector corresponding to the largest eigenvalue. The sign is then fixed: `if q_mean[3] < 0: q_mean *= -1.0` (ensures scalar-last convention and positive w).

This implementation is mathematically correct and robust, matching industry-standard rotation averaging techniques.

---

## 4. Additional findings

### F1: MEDIUM confidence level not defined in `__reference_metadata.json`
The `confidence_level` field ("HIGH" or "MEDIUM") appears in `__reference_metadata.json` but the JSON does not explain the threshold that triggered MEDIUM. For reproducibility, the JSON should log the `mean_motion` and `std_motion` thresholds alongside the achieved values, so MEDIUM can be explained quantitatively without re-running the notebook.

T1_P2_R2 shows:
- `mean_motion: 0.054 rad/s` (below `MOTION_THR_LOW = 0.3`) — this looks fine for HIGH
- But `variance_score: 19.76` vs `variance_threshold: 100.0` — both sessions below threshold

The exact MEDIUM trigger mechanism is in `reference_validation.py` (not audited here). This should be documented.

### F2: `t_pose_failed` fallback is an identity quaternion — undocumented risk
When `t_pose_failed = True`, all joints are set to `[0,0,0,1]`. This means downstream kinematics would produce angular velocity computed relative to the identity pose rather than the subject's anatomical neutral. This is a silent quality degradation that would affect all computed angles in session. The `t_pose_failed` field IS logged, but there is no downstream gate or QC flag that would stop the pipeline or alert the user.

### F3: REF_SEARCH_SEC hardcoded to first N seconds
The reference window is always searched in the first `REF_SEARCH_SEC` seconds. If a recording does not start with a calibration pose (e.g., subject is already moving), there is no fallback search later in the session. The existing fallbacks (`fallback_min_motion`, `fallback_first_window`) will use the first window regardless of quality.

### F4: No downstream QC gate on `ref_is_fallback`
`ref_is_fallback = True` is logged but does not trigger any downstream warning or FAIL status in the pipeline. A fallback reference would silently propagate to kinematics with potentially large angular offsets. A `gate_05_status` field analogous to `gate_02_status` would be appropriate.

### F5: `ref_quality_score = 0.8216` for T1_P1_R1 — units unclear
The `ref_quality_score` is the median standard deviation of rotation vector magnitudes during the reference window (in radians). Higher values mean MORE movement, which is WORSE. This counterintuitive naming ("quality" high = bad) should be clarified or renamed to `ref_motion_std_rad`.

---

## 5. Summary table

| Check | Status | Severity |
|---|---|---|
| Fallback flagging coded | PASS — 5 distinct fallback methods | — |
| Fallback flagging logged in JSON | PASS — `ref_is_fallback`, `method`, `t_pose_failed` | — |
| Current data: fallback triggered | 0/9 sessions | PASS |
| MEDIUM confidence explanation | ABSENT from JSON | Low |
| Downstream gate on fallback | ABSENT | Medium |
| `t_pose_failed` propagation guard | ABSENT | Medium |
| Markley mean quat implementation | PASS (correct eigendecomposition) | — |
| ref_quality_score naming | CONFUSING (higher = worse) | Low |

---

## 6. Decisions triggered

| Issue | Recommended action | Priority |
|---|---|---|
| No downstream gate on `ref_is_fallback` | Add `gate_05_status: WARN` when `ref_is_fallback=True`; surface in pipeline summary | Medium |
| `t_pose_failed` propagation | Add explicit annotation in kinematics output; add `ref_quality_flag` column to parquet | Medium |
| MEDIUM confidence explanation | Log `mean_motion`, `std_motion`, `variance_score`, and threshold values in metadata JSON | Low |
| `ref_quality_score` naming | Rename to `ref_motion_std_rad` | Low |
