# S-03 Resample — Stage Audit

**Date:** 2026-05-14
**Auditor:** Per-Stage Audit Agent (Phase 4 batch)
**Sources read:**
- `src/resampling.py` (full — 313 lines)
- `derivatives/step_03_resample/671_T1_P1_R1_Take 2026-01-06 03.57.12 PM_001__resample_summary.json` (representative)
- All 9 `__resample_summary.json` via grep
**Status:** COMPLETE

---

## 1. What Step 03 does

`notebooks/03_resample.ipynb` calls `src/resampling.py` to:
1. Build a uniform time grid at `target_fs = 120.0 Hz` from the preprocessed timestamps.
2. Resample positions using `resample_pos_pchip()` — genuine PCHIP via `PchipInterpolator`.
3. Resample quaternions using `resample_quat_slerp()` — genuine SciPy `Slerp` with hemisphere continuity enforcement.
4. Write `__resampled.parquet` and `__resample_summary.json`.

**Note on S-02 vs S-03 method labels:** Both stages output `"pchip_single_pass"` / `"slerp"` in their summary JSONs, but the actual algorithms are different:
- Step 02: uses `np.interp` (linear) for positions and `pandas.Series.interpolate(method="linear")` for quaternions — the labels are WRONG.
- Step 03: uses genuine `PchipInterpolator` and SciPy `Slerp` — the labels are CORRECT here.

This is the label mismatch finding from S-02 (F6, F1) seen from the other side.

---

## 2. Q-EXT3a — Anti-aliasing before downsampling

**Question:** Does Step 3 apply anti-aliasing before downsampling? Is cutoff at Nyquist?

**Answer: NO anti-aliasing filter present — but currently NOT applicable.**

`resampling.py` contains no lowpass pre-filter before resampling. PCHIP is a cubic interpolator (Piecewise Cubic Hermite Interpolating Polynomial); it passes high-frequency content unattenuated when the sample rates match.

**Currently not a problem because no downsampling occurs in this dataset:**
- All 9 sessions: `target_fs = 120.0 Hz`, `sampling_rate_actual = 120.0048 Hz`
- Temporal status: `"PERFECT"` for all 9 sessions
- This is resample-to-uniform-grid, not decimation. Input and output sample rates are equal (within 0.004%).

**When anti-aliasing WOULD be required:** If a future session is captured at 200 Hz and resampled to 120 Hz (decimation factor ≈ 1.67×), the Nyquist of the target grid is 60 Hz. Without a lowpass pre-filter at ≤60 Hz, spectral aliasing would fold frequencies 60–100 Hz back into the 0–60 Hz band. PCHIP without an anti-aliasing filter cannot prevent this.

**Reference confirmation (Phase 4.5):** optitrack-main confirmed anti-aliasing before downsampling. The pipeline has this structural gap for non-uniform-rate sessions.

---

## 3. PCHIP and SLERP implementations — code quality

### 3.1 Position: `resample_pos_pchip()`
```python
pchip_x = PchipInterpolator(tv_j, xv_j)
```
- Genuine PCHIP from `scipy.interpolate`. NaN-safe: only valid frames contribute to the interpolant.
- Gap masking with half-gap rule (`max_dist = max_gap_pos_sec / 2.0`): outputs NaN for target grid points farther than `max_gap_pos_sec / 2` from any valid input timestamp. Default `max_gap_pos_sec = 1.0s`.
- No extrapolation beyond first/last valid frame.
- **Strong implementation.** Contrast with Step 02's `gapfill_positions.py` which uses `np.interp` (linear) and has a gap-boundary detection bug.

### 3.2 Rotation: `resample_quat_slerp()`
```python
qv = quat_enforce_continuity(quat_normalize(qj[valid]))
rot = R.from_quat(qv)
s = Slerp(tv, rot)
out[mask, j, :] = s(t_dst[mask]).as_quat()
out[:, j, :] = quat_shortest(quat_normalize(out[:, j, :]))
```
- Genuine geodesic SLERP via `scipy.spatial.transform.Slerp`.
- Hemisphere continuity enforced BEFORE Slerp to prevent shortest-path sign flips.
- Post-SLERP `quat_shortest` + `quat_normalize` pass for additional safety.
- No extrapolation (only interpolates within `[tv[0], tv[-1]]`).
- **Strong implementation.**

---

## 4. Data observations across 9 sessions

| Session | target_fs | temporal_status |
|---|---|---|
| 671_T1_P1_R1 | 120.0 | PERFECT |
| 671_T2_P1_R1 | 120.0 | PERFECT |
| 671_T3_P1_R1 | 120.0 | PERFECT |
| 671_T1_P2_R1 | 120.0 | PERFECT |
| 671_T1_P2_R2 | 120.0 | PERFECT |
| 671_T2_P2_R1 | 120.0 | PERFECT |
| 671_T2_P2_R2 | 120.0 | PERFECT |
| 671_T3_P2_R1 | 120.0 | PERFECT |
| 671_T3_P2_R2 | 120.0 | PERFECT |

All sessions: `time_grid_std_dt = 0.0` (perfectly uniform grid after resampling). Gate 2 temporal status: PERFECT for all.

---

## 5. Additional findings

### F1: Resample summary does not log NaN frame counts
The `__resample_summary.json` contains only: `run_id`, `target_fs`, `time_grid_std_dt`, `temporal_status`, `interpolation_methods`. It does NOT log:
- How many NaN frames were present at resample input per joint
- How many NaN frames were introduced (via the half-gap mask) or preserved
- Which joints had gaps requiring interpolation

This is the Q-EXT1a counterpart for Step 03 (Phase 4.5 question Q-EXT1a was directed at Stage 3/filtering, but the same logging gap exists at the resample stage). The NaN accounting is opaque.

### F2: `resample_pos()` fallback (not called by NB03)
`resampling.py` also contains `resample_pos()` (line 266), a multi-method fallback supporting `"linear"`, `"cubic_spline"`. This function is not called by NB03 (which uses `resample_pos_pchip()` exclusively). Dead code in active path. Risk: confusion if someone calls the wrong function.

### F3: Gate 2 jitter code is in `resampling.py` but labeled "step_02"
The function `compute_sample_jitter()` (line 38) returns keys prefixed `step_02_*` and is called from NB02, not NB03. This is a module organization issue: jitter measurement code lives in the resampling module but serves the preprocessing step.

### F4: No annotation of which frames were gap-filled vs original
After resampling, all frames in the uniform grid are treated equally in downstream stages. There is no `is_interpolated_frame` boolean column in the resampled parquet to distinguish original timestamps from PCHIP-interpolated ones. This limits provenance tracking.

---

## 6. Summary table

| Check | Status | Severity |
|---|---|---|
| Q-EXT3a: Anti-aliasing before downsampling | ABSENT (not applicable at 120→120Hz) | Low (design gap for future) |
| Position resampling implementation | PASS (genuine PCHIP) | — |
| Quaternion resampling implementation | PASS (genuine SciPy SLERP) | — |
| Hemisphere continuity pre-SLERP | PASS | — |
| NaN frame count logged | FAIL | Low |
| Interpolated-frame provenance | ABSENT | Low |
| Gate 2 temporal status | PASS (all PERFECT) | — |

---

## 7. Decisions triggered

| Issue | Recommended action | Priority |
|---|---|---|
| No anti-aliasing guard | Add `if target_fs < input_fs: apply_lowpass(input_data, cutoff=target_fs/2)` branch; log `antialiasing_applied` | Low (design gap) |
| Resample summary missing NaN counts | Log `n_nan_frames_at_resample_input`, `n_nan_frames_in_output` per joint | Low |
| No interpolated-frame provenance | Add `{joint}__is_interpolated` boolean column or bitflag to resampled parquet | Low |
