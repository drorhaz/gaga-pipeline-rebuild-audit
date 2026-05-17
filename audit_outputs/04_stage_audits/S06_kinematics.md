# S-06 Ultimate Kinematics — Stage Audit

**Date:** 2026-05-14
**Auditor:** Per-Stage Audit Agent (Phase 4 batch)
**Sources read:**
- `src/angular_velocity.py` (full — 537 lines)
- `src/kinematic_repair.py` (full — 292 lines)
- `src/kinematics_alignment.py` (grep)
- `notebooks/06_ultimate_kinematics.ipynb` (key cell grep)
- `config/config_v1.yaml` (enforce_cleaning field)
- `derivatives/step_06_kinematics/671_T1_P1_R1_Take 2026-01-06 03.57.12 PM_001__validation_report.json` (full)
- `derivatives/step_06_kinematics/671_T1_P1_R1_Take 2026-01-06 03.57.12 PM_001__outlier_validation.json` (full)
**Status:** COMPLETE

---

## 1. What Step 06 does

`notebooks/06_ultimate_kinematics.ipynb` produces the final `kinematics_master.parquet` by:
1. Loading filtered quaternions and positions from Step 04 output.
2. Computing relative quaternions: `q_rel = inv(parent) * child` for each joint in the hierarchy.
3. Applying SavGol smoothing on the relative quaternion stream, then renormalizing.
4. Computing zeroed quaternions: `q_zeroed = inv(q_ref_rel) * q_raw_smooth`.
5. Computing angular velocity (ω) via OMEGA_METHOD (default: `quat_log`) on zeroed and raw-relative quaternions.
6. Computing angular acceleration (α) as SavGol derivative of ω.
7. Computing linear velocity and acceleration from root-relative positions via SavGol.
8. Running outlier validation against thresholds.
9. Optionally running `kinematic_repair.py::apply_surgical_repair()` if `enforce_cleaning=True`.
10. Writing `__kinematics_master.parquet`, `__validation_report.json`, `__outlier_validation.json`.

---

## 2. Q-S06a — Angular velocity method comparison (5pt vs adjacent)

**Question:** Does NB06 compute ω with both adjacent-frame and 5-point methods and report the Δω_mag difference? Is any joint >1 deg/s?

**Answer: Method comparison IS logged. The "5pt" method is NOT a true 5-point stencil.**

### 2.1 Method comparison output from NB06 (cell output for representative session)

From NB06 stored output (cell line 738–739):
```
Noise (2nd-deriv std): quat_log = 0.0360, 5pt = 0.0177, central = 0.0218
Noise reduction quat_log vs central: 0.61x
```

This comparison runs every session as an audit trail. Three methods are compared:
- `quaternion_log`: relative rotation vector / dt (adjacent frames, body frame)
- `5point`: weighted average of 5 adjacent-frame backward differences
- `central`: central finite difference over 2-frame window

**Counterintuitive result:** `5pt` shows LOWER noise (0.0177) than both `quat_log` (0.0360) and `central` (0.0218). `quat_log vs central = 0.61x` means quat_log is NOISIER than central.

**Root cause — the `finite_difference_5point()` implementation (angular_velocity.py:105–161):**
```python
weights = np.array([0.1, 0.25, 0.3, 0.25, 0.1])  # Gaussian-like
omega[t] = np.average(omegas, axis=0, weights=weights)
```
This is NOT the standard 5-point numerical differentiation stencil. The correct 5-point stencil formula is:
```
ω[t] = (-q[t+2] + 8q[t+1] - 8q[t-1] + q[t-2]) / (12·dt)
```
Instead, the code computes a WEIGHTED AVERAGE of 5 adjacent backward differences. This is a smoothing operation, not a differentiation stencil. It artificially reduces noise by averaging, but also reduces temporal resolution and underestimates peak velocities in high-speed movements.

**Default method is `quat_log`**, not `5pt`. This is correct: `quat_log` is the only method that respects the SO(3) manifold geometry. The lower "noise" of `5pt` is an artifact of averaging, not superior accuracy.

**Q-S06a verdict:** The method comparison does not report joint-level Δω_mag differences. It reports a single aggregate noise metric (second derivative std of magnitude). Per-joint ω differences between methods are NOT logged to JSON artifacts. This gap prevents post-hoc validation of which joints show the largest method disagreement.

### 2.2 Current data: per-joint ω observations (from __validation_report.json, T1_P1_R1)

| Joint | max_omega_deg_s | mean_omega_deg_s | sg_w_len | exceeded_threshold |
|---|---|---|---|---|
| Hips | 345.66 | 34.10 | 21 (adaptive) | false |
| Spine | 230.54 | 16.14 | 21 (adaptive) | false |
| Neck | 305.62 | 25.63 | 15 (adaptive) | false |
| Head | ~300 | ~26 | 15 (adaptive) | false |
| LeftHand | ~800+ | — | — | true (WARNING, ALERT, CRITICAL) |

All core trunk joints remain below the 800°/s WARNING threshold. LeftHand and RightHand show WARNING/ALERT/CRITICAL frames (expected for distal segments in dance).

---

## 3. Q-S06b — `enforce_cleaning` repair rate

**Question:** What is the enforce_cleaning repair rate across sessions?

**Answer: enforce_cleaning = False in config. Kinematic repair is inactive for all current sessions.**

From `config/config_v1.yaml:84`:
```yaml
enforce_cleaning: false
```

`src/kinematic_repair.py::apply_surgical_repair()` is called only when `ENFORCE_CLEANING = True`. Since this is False, the function is never invoked. Repair rate = 0% across all 9 sessions.

The repair mechanism is implemented correctly:
- Angular: SLERP-interpolates CRITICAL frames in raw-relative quaternions, re-derives ω/α
- Linear: PCHIP-interpolates CRITICAL frames in root-relative positions, re-derives v/a
- Only affects joints/segments that exceeded the CRITICAL threshold

**Note:** The Phase 3 decision log listed `enforce_cleaning = true` as a target `LOCAL_REFACTOR`. Current state is `false`. No repair metrics can be measured against current derivatives.

---

## 4. Q-EXT4a — |q| ≈ 1.0 assertion after loading and smoothing

**Question:** Does Stage 6 assert |q| ≈ 1.0 after loading and after smoothing?

**Answer: NO explicit assertion with logging. Only silent per-frame renormalization.**

Three points of quaternion normalization in the Step 06 pipeline:

1. **After resampling (Step 03):** `quat_shortest(quat_normalize(out[:, j, :]))` in `resample_quat_slerp()`.
2. **After SavGol smoothing (Step 06):** `renormalize_quat(q_rel)` and `renormalize_quat(q_zeroed)` — found in NB06 cells 347, 361.
3. **In kinematic_repair.py:** `_renormalize_quat(q)` per-frame.

None of these log the pre-normalization quaternion norm (|q| deviation from 1.0) or assert that |q| < threshold (e.g., `assert |np.linalg.norm(q, axis=1) - 1.0| < 0.01`).

**Risk from SavGol smoothing:** SavGol filtering of quaternion components independently does NOT preserve |q| = 1.0. After SavGol on raw q components (which are done independently per component), the resulting vectors may have |q| ≠ 1 by a small but non-zero amount. The pipeline does renormalize after, but does not log how large the deviation was before renormalization.

**Reference (Phase 4.5):** kineticstoolkit and opensim_pyprocessing both perform explicit norm assertions after smoothing operations on orientations. The pipeline should log max `||q| - 1|` pre-normalization per joint per session.

---

## 5. Additional findings

### F1: SavGol smoothing applied to quaternion components independently
NB06 applies SavGol to each `q{x,y,z,w}` component independently (as confirmed by `renormalize_quat()` being needed afterward). Smoothing quaternion components independently is geometrically incorrect — SavGol does not operate on the SO(3) manifold. The correct approach is to smooth the rotation vector (log map) and then exponentiate back. This is a known approximation that is used in practice because SO(3) SavGol is complex, but the deviation from unit norm should be quantified and logged.

### F2: `finite_difference_5point()` is a weighted-average smoother, not a 5-point stencil
(Detailed in Q-S06a above.) The misleading name suggests mathematical rigor that the implementation does not provide.

### F3: Angular velocity boundary handling
`quaternion_log_angular_velocity()` (line 70–102): the last frame forward-fills from the second-to-last: `omega[-1] = omega[-2]`. This is a step artifact at the boundary. For sequences >100 frames, this is negligible (1 frame), but should be noted in any analysis of session start/end frames.

### F4: `velocity_alignment_pct` is Pearson correlation between omega_mag_raw and omega_mag_zeroed
The `velocity_alignment_pct = 100 * pearsonr(mag_omega_raw, mag_omega_zeroed)[0]` field measures how well the raw-relative and zeroed relative angular velocities agree in magnitude. All core joints show `velocity_alignment_pct = 100.0` in T1_P1_R1. This is a useful internal consistency check.

### F5: Adaptive SavGol window
`sg_w_source = "adaptive"` for all joints — confirms the adaptive window (from `savgol_window_len()`) is active. Window varies by joint: Hips/Spine = 21 frames (≈175ms), Neck/Head = 15 frames (≈125ms). Distal joints may have smaller or larger windows.

### F6: No `n_nan_frames_at_kinematics_input` logging
Step 06 does not log how many frames per joint had NaN quaternion input. NaN frames result in NaN ω/α in the output, but the count is not in the validation report.

---

## 6. Summary table

| Check | Status | Severity |
|---|---|---|
| Q-S06a: Method comparison logged | PARTIAL — aggregate noise metric only, no per-joint Δω | Low |
| Q-S06a: `finite_difference_5pt` implementation correctness | FAIL — weighted average, not true stencil | Medium |
| Q-S06a: Default method (quat_log) is appropriate | PASS | — |
| Q-S06b: enforce_cleaning repair rate | N/A — inactive (enforce_cleaning=False) | — |
| Q-EXT4a: |q|≈1.0 assertion after loading | ABSENT — only silent renormalization | Medium |
| Q-EXT4a: |q|≈1.0 assertion after smoothing | ABSENT — only silent renormalization | Medium |
| SavGol on quaternion components | PRESENT but geometrically approximate | Low |
| Adaptive SavGol window | PASS — active, per-joint | — |
| Gravity Guard integration | PASS — identity fallback when t_pose_failed | — |
| Hand joints ω above WARNING | Expected (distal segments, dance) | Noted |

---

## 7. Decisions triggered

| Issue | Recommended action | Priority |
|---|---|---|
| No |q|≈1.0 assertion | Add `max_quat_norm_deviation_pre_renorm` metric per joint to validation report | Medium |
| `finite_difference_5point` is a smoother | Rename to `weighted_smoothed_diff` or replace with true 5-pt stencil | Medium |
| No per-joint Δω method comparison in JSON | Extend method comparison output to JSON artifact | Low |
| NaN input frames not counted | Add `n_nan_frames_at_kinematics_input` to validation report | Low |
