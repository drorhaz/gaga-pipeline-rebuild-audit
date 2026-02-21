# QA Pipeline Glassbox Integration — Revised Masterplan (Parameterized Arsenal)

**Notebook:** `qa_pipeline_glassbox_integration.ipynb`  
**Purpose:** Data-driven, stage-by-stage verification of the Gaga Motion Analysis Pipeline using a **Test Arsenal** of parameterized scenarios, including negative tests.  
**Reference:** `docs/PIPELINE_PROCESSING_README.md`

---

## Part 1: SDET Review — Arsenal vs Pipeline Failure Points

### Do the three scenarios accurately target the most critical pipeline failure points?

**Yes, with one gap.**

| Scenario | Target | Critical? | Notes |
|----------|--------|-----------|--------|
| **Standard Dirty** | Short gap + MAD spike + Hampel bump + static window | **Yes** | Covers the “happy path” with real anomalies: Step 02 MAD masks spike and fills short gap; Step 04 catches the milder bump; Step 05 finds static window; full pipeline succeeds. |
| **Fatal Gap** | 1.5 s position NaN gap | **Yes** | Directly tests the **bounded** in “bounded cubic spline”: `max_gap_pos_sec = 1.0` (README §4.2). The pipeline must **refuse** to fill gaps > 1 s. Asserting that NaNs remain is the correct negative test. |
| **Quat Nightmare** | Hemisphere jump (dot < 0) | **Yes** | Targets Step 03/06 **temporal continuity** (README §5.5, §8.12). Uncorrected flips cause wrong SLERP path and spurious angular velocity; this is a high-impact failure mode. |

**Gap:** The current three do not stress **reference-detection fallback** or **health-score self-diagnostics**. The README explicitly defines fallback when no window meets strict criteria and a health cap when reference is fallback (§7.1, §10). That is a critical operational behavior and should be covered by a 4th scenario.

---

### Parameter recommendations

1. **Standard Dirty — short gap**  
   - Use a gap **&lt; 0.5 s** (e.g. 5 frames at 120 Hz ≈ 0.042 s) so it is well below `max_gap_pos_sec = 1.0` and **below** `max_gap_quat_sec = 0.25` if the same gap is applied to quaternions.  
   - If the same 5-frame gap is used for both position and quaternion, duration ≈ 0.042 s &lt; 0.25 s → both get filled. No change needed.

2. **Standard Dirty — “Hampel bump”**  
   - Design a **3-frame** statistical bump that stays **below** Step 02 MAD (so it is not masked in Step 02) but **above** Step 04 Hampel/Z-score.  
   - Suggested construction: add a small position offset (e.g. 2–3× local std, or tuned so velocity &lt; 5000 mm/s and Z &lt; 5) on 3 consecutive frames on one axis. Verify in test that Step 02 does not mask it and Step 04 metadata reports Hampel/Stage1 corrections.

3. **Fatal Gap — duration and placement**  
   - **1.5 s** is correct (&gt; 1.0 s).  
   - Place the gap **in the middle** of the segment (not at start/end) so the “boundary skip” logic does not hide the “too long” behavior.  
   - At 120 Hz, 1.5 s = 180 frames. Assert: after Step 02, the same 180-frame region still has NaNs and (optionally) that no spline was applied for that gap (e.g. via interpolation logger if available).

4. **Quat Nightmare — which joint and when**  
   - Apply the flip to **one** joint (e.g. Spine) at a **single frame** in the middle (e.g. `q[t] = -q[t-1]`).  
   - Assert after Step 03: resampled quaternion has continuity at that time (e.g. no π rad rotvec jump). Assert after Step 06: no anomalous omega spike at that frame.

5. **Winter/Smart Bias (Cell 4)**  
   - **Spine** → trunk → fixed cutoff **6 Hz**; **RightHand** (or a hand joint present in the arsenal schema) → upper_distal → **12 Hz**.  
   - Assert: filter metadata assigns Spine ≤ 6 Hz (or region trunk) and RightHand (or chosen distal) ≥ 12 Hz (or region upper_distal). If the pipeline stores per-column cutoff, assert those values.

---

### 4th “Boss Level” scenario (recommended)

Add a fourth scenario that exercises **reference-detection fallback** and **health/self-diagnostics** (README §7.1, §10):

**Scenario D — `no_static_window` (reference fallback + health cap)**

- **Content:** Same duration and joints as standard (e.g. Hips, Spine, Head), but **no** 2 s static window at the start. For example: low-amplitude motion (e.g. 0.2 rad/s) for the first 8 s so no window meets `mean_motion < motion_thr_low` and `std_motion < motion_thr_std`.
- **Expected:**  
  - Step 05 returns `ref_is_fallback = True` and `method` like `"fallback_min_motion"`.  
  - Pipeline still completes; reference is the minimum-motion window.  
  - When running Cell 7 (Gates + health): **health score ≤ health_fallback_cap** (e.g. 59 per README), or a clear indicator that reference was fallback.
- **Why “Boss Level”:** It validates that the pipeline degrades gracefully (no crash), that self-diagnostics reflect reduced confidence, and that downstream consumers can use the fallback flag and health score.

**Alternative 4th options (for later expansion):**

- **Teleportation flag:** Inject a brief segment with linear velocity &gt; 3000 mm/s (README §8.9); pass through to Step 06 and assert the teleportation/artifact flag column is set on those frames.  
- **Missing required joint:** DataFrame with only two of `[Hips, Spine, Head]`; assert pipeline or Gate rejects or flags (requires knowing where `required_joints` is enforced).  
- **Missing anthropometrics:** Run with `subject_height_cm`/`subject_mass_kg` = None (or default 170/70) and assert `metadata_quality` in validation output is `MISSING_ANTHRO` or `UNRELIABLE_COM_DEFAULT_ANTHRO`. This is more of a config/context test than an arsenal DataFrame.

**Recommendation:** Implement **no_static_window** as the 4th arsenal entry; keep teleportation and missing-joint as optional future additions.

---

## Part 2: Test Arsenal — `generate_test_arsenal()`

### Contract (Cell 1)

- **Function:** `generate_test_arsenal(fs=120, duration_sec=8.0) -> dict`
- **Returns:** A dictionary of DataFrames and shared metadata, keyed by scenario name.
- **Shared schema (per DataFrame):** Mimics Step 01 parsed output:
  - `time_s`: float, strictly increasing.
  - `frame_idx`: integer index (optional for some steps).
  - For each joint in `[Hips, Spine, Head]` (and optionally RightHand for Winter):  
    `{Joint}__px`, `{Joint}__py`, `{Joint}__pz` (mm); `{Joint}__qx`, `{Joint}__qy`, `{Joint}__qz`, `{Joint}__qw` (xyzw).
- **Shared constants:** Store in a small `arsenal_meta` dict (or as attributes) so cells can assert without magic numbers:
  - `fs`, `duration_sec`, `max_gap_pos_sec` (1.0), `ref_window_sec` (1.0), indices or times for injected anomalies.

### Scenario definitions

| Key | Name | Description | Injected anomalies |
|-----|------|-------------|---------------------|
| `standard_dirty` | Standard Dirty | Full pipeline success path | (1) 5-frame NaN gap (pos + quat), mid-recording. (2) Single-frame 5000 mm/s position spike (one axis). (3) 3-frame “Hampel bump” (mild offset, below MAD, above Hampel/Z). (4) First 2 s static (angular velocity ≈ 0). |
| `fatal_gap` | Fatal Gap | Step 02 must refuse to fill | (1) Single 1.5 s (180-frame) NaN gap in position (and optionally quat), **mid-recording**. (2) First 2 s static (so ref detection still works if we run later steps). No spike/bump. |
| `quat_nightmare` | Quaternion Nightmare | Continuity restoration | (1) One joint (e.g. Spine): at one frame, `q[t] = -q[t-1]`. (2) First 2 s static. No long gap, no position spike. |
| `no_static_window` | No Static Window (Boss) | Reference fallback + health cap | (1) First 8 s: low but non-zero motion (e.g. ~0.2 rad/s) so no window meets strict criteria. (2) Optional: same short gap as standard_dirty to keep structure. No spike. |

### Optional: RightHand in arsenal

- For **Winter/Smart Bias** we need at least one **distal** joint (e.g. RightHand). Options:
  - Add RightHand to **all** arsenal DataFrames (same schema, 4 joints), or  
  - Add RightHand only to `standard_dirty` and use that in Cell 4 for the “distal” cutoff assertion.  
- Recommendation: Add RightHand to `standard_dirty` (and optionally to others) so one joint is “Spine” (trunk) and one “RightHand” (upper_distal).

---

## Part 3: Cell-by-Cell Plan — How Each Cell Uses the Arsenal

### Strategy: scenario-specific branching, not a single loop

- **Not** a single loop over all scenarios in every cell: some scenarios are **step-specific** (e.g. fatal_gap only needs Step 02; quat_nightmare needs Step 03 and 06; no_static_window needs Step 05 and 07).
- Each cell:
  1. Determines **which scenario(s)** apply to that step.
  2. Runs the **production** step (import from `src`) on the chosen scenario’s DataFrame.
  3. Asserts **expected outcome per scenario** (pass, fail, or specific metadata).

### Cell 1: Setup and `generate_test_arsenal()`

| Item | Detail |
|------|--------|
| **Input** | None (optional: `fs`, `duration_sec`). |
| **Output** | `arsenal = generate_test_arsenal()` and `arsenal_meta` (or equivalent) with indices/times for gaps, spike, bump, flip, static window. |
| **Logic** | Build 4 DataFrames (standard_dirty, fatal_gap, quat_nightmare, no_static_window) with the anomaly table above. Use consistent `time_s` length (e.g. `duration_sec * fs`). |
| **Assertions** | (1) `time_s` strictly increasing for each. (2) standard_dirty: one 5-frame gap at expected indices; one frame with velocity ≈ 5000 mm/s; 3-frame bump; first 2 s motion &lt; 0.1 rad/s. (3) fatal_gap: one contiguous 1.5 s NaN gap in the middle. (4) quat_nightmare: one frame with dot(q[t-1], q[t]) &lt; 0 for Spine. (5) no_static_window: first 8 s mean motion ≥ motion_thr_low (e.g. 0.2). |

---

### Cell 2: Step 02 (Gap Filling) — Production with MAD masker

| Item | Detail |
|------|--------|
| **Scenarios** | **standard_dirty**, **fatal_gap**. (quat_nightmare and no_static_window can be run here too for “no regression” but are not the focus.) |
| **Data in** | `arsenal["standard_dirty"]`, `arsenal["fatal_gap"]` (and optionally others). |
| **Functions** | From `src`: `preprocessing.detect_and_mask_artifacts` (per-axis or as used in production), then `preprocessing.bounded_spline_interpolation` or `gapfill_positions.gap_fill_positions`, and `gapfill_quaternions.gapfill_all_quaternions`. Use **config** `max_gap_pos_sec = 1.0`, `max_gap_quat_sec = 0.25`. |
| **Processing** | For each scenario, run **full** Step 02 (MAD mask → then gap fill). Pass `time_s` and `max_gap_s` from config. |
| **Assertions** | **standard_dirty:** (1) No NaNs in position/quat (short gap filled). (2) The 5000 mm/s spike frame was masked and then filled (value at spike frame is interpolated, not 5000 mm/s). (3) The 3-frame bump is **not** removed here (it remains for Step 04). **fatal_gap:** (4) The 1.5 s gap **remains** NaN (at least one position column has NaNs in that interval). (5) Optional: gap duration &gt; 1.0 s confirmed. |

---

### Cell 3: Step 03 (Resampling)

| Item | Detail |
|------|--------|
| **Scenarios** | **standard_dirty**, **quat_nightmare** (and optionally fatal_gap if we resample “as-is” with NaNs; otherwise skip fatal_gap for resampling or handle NaN-safe). |
| **Data in** | Output of Cell 2 for standard_dirty and quat_nightmare (and optionally no_static_window). For fatal_gap, either skip or use preprocessed output with NaNs. |
| **Functions** | `src.resampling.estimate_fs`, `resample_time_grid`, `resample_pos`, `resample_quat_slerp`. |
| **Processing** | For each scenario, compute `t_dst = resample_time_grid(time_s, fs_target)`; resample positions and quaternions. |
| **Assertions** | **All:** (1) `time_s` out strictly monotonic. (2) `np.allclose(np.diff(time_s_out), 1/fs_target, atol=1e-9)`. (3) Length matches `round((t1-t0)*fs_target)+1`. **quat_nightmare:** (4) At the flip frame/time, resampled quaternion does **not** show a π rad discontinuity (continuity restored by enforce_continuity / shortest path). |

---

### Cell 4: Step 04 (Filtering) — 3-stage + Winter/Smart Bias

| Item | Detail |
|------|--------|
| **Scenarios** | **standard_dirty** (primary), optionally no_static_window. (fatal_gap has NaNs → may skip or test that filter handles NaN; quat_nightmare can be run for “no crash” only.) |
| **Data in** | Resampled DataFrame from Cell 3 for standard_dirty (positions in mm). |
| **Functions** | `src.filtering.apply_signal_cleaning_pipeline` with config (velocity_limit=5000, zscore_threshold=5.0, etc.). |
| **Processing** | Run full 3-stage pipeline on standard_dirty position columns. |
| **Assertions** | **standard_dirty:** (1) The **3-frame Hampel bump** is reduced/replaced (compare value at bump frames to neighbors or check metadata for Hampel/Stage2 replacements). (2) Stage 1 did **not** see a 5000 mm/s spike on this run (spike was already removed in Step 02). (3) **Winter/Smart Bias:** From filter metadata, assert **Spine** (trunk) has cutoff ≥ 6 Hz (or region trunk); **RightHand** (or chosen distal) has cutoff ≥ 12 Hz (or region upper_distal). |

---

### Cell 5: Step 05 (Reference Detection)

| Item | Detail |
|------|--------|
| **Scenarios** | **standard_dirty**, **quat_nightmare**, **no_static_window** (and optionally fatal_gap if we have valid q_local). |
| **Data in** | Filtered (or resampled) data with `time_s` and `q_local` (T, J, 4) for viz joints. Build `q_local` from DataFrame quaternion columns and minimal schema. |
| **Functions** | `src.reference.detect_static_reference(time_s, q_local, joints_viz_idx, cfg)`. |
| **Processing** | For each scenario, run `detect_static_reference` with config (REF_SEARCH_SEC, REF_WINDOW_SEC, MOTION_THR_LOW, MOTION_THR_STD). |
| **Assertions** | **standard_dirty / quat_nightmare:** (1) `ref_start` and `ref_end` within first 2 s. (2) `ref_end - ref_start` ≈ REF_WINDOW_SEC. (3) `method == "criteria"` (or not fallback). (4) `ref_is_fallback` is False. **no_static_window:** (5) `ref_is_fallback` is True. (6) `method` in `("fallback_min_motion", "fallback_first_window", ...)`. (7) ref window is in first 8 s. |

---

### Cell 6: Step 06 (Kinematics Output)

| Item | Detail |
|------|--------|
| **Scenarios** | **standard_dirty**, **quat_nightmare** (and optionally no_static_window). Skip fatal_gap if NaNs would break kinematics. |
| **Data in** | Filtered + referenced: time_s, pos (m), q_global/q_local, q_ref, schema, config. |
| **Functions** | `src.pipeline.compute_q_local`, `compute_kinematics`; `src.reference.compute_q_ref_and_ref_qc`; optionally the same export path as 06 (build_master_tables or notebook logic). |
| **Processing** | Run kinematics for each scenario; obtain master DataFrame (or equivalent). |
| **Assertions** | **standard_dirty:** (1) No NaN in kinematic columns (or &lt; 0.1%). (2) Expected columns exist: e.g. `{joint}__zeroed_rel_omega_x` (or actual naming) for Hips, Spine, Head. **quat_nightmare:** (3) At the former flip frame, no anomalous omega spike (continuity fix carried through). **no_static_window:** (4) Pipeline completes; master table has same column set (ref was still computed via fallback). |

---

### Cell 7: Gates and Health Score

| Item | Detail |
|------|--------|
| **Scenarios** | **standard_dirty** (expect PASS/health high), **no_static_window** (expect fallback + health cap). Optionally quat_nightmare. |
| **Data in** | From previous cells: time_s, interpolation_summary (if any), filter_summary (Step 04), Step 06 outputs; ref_info (ref_is_fallback). |
| **Functions** | `src.gate_integration.run_gate_2`, `run_gate_3`, `run_gate_4`, `run_gate_5`, `run_all_gates`, `get_overall_decision`. If health score is computed elsewhere (e.g. validation_report), call that or replicate the formula from README §10. |
| **Processing** | Run Gate 2 (with jitter + optional interpolation summary), Gate 3 (filter_summary), Gate 4 (joint names + quat norm err), Gate 5 (angular velocity). Combine and get overall decision. Compute or read health score. |
| **Assertions** | **standard_dirty:** (1) Gate 2/3/4/5 return expected keys; (2) overall status PASS or REVIEW (not REJECT). (3) Health score in [0, 100]. (4) If ref was criteria, health not capped by fallback. **no_static_window:** (5) ref_is_fallback True. (6) Health score ≤ health_fallback_cap (e.g. 59) or a clear “fallback” indicator in the combined result. (7) Overall status may be REVIEW due to fallback. |

---

## Part 4: Summary — Scenario × Cell Matrix

| Cell | standard_dirty | fatal_gap | quat_nightmare | no_static_window |
|------|----------------|-----------|----------------|------------------|
| 1 | Generated | Generated | Generated | Generated |
| 2 Step 02 | Run; assert gap filled, spike masked+filled, bump remains | Run; assert 1.5 s gap **not** filled | Run (optional) | Run (optional) |
| 3 Resample | Run; assert 120 Hz grid | Skip or NaN-safe | Run; assert continuity at flip | Run (optional) |
| 4 Filter | Run; assert Hampel catches bump; Winter Spine/RightHand | Skip or NaN-safe | Optional | Optional |
| 5 Reference | Run; assert criteria, 2 s window | Optional | Run; assert criteria | Run; assert **fallback** |
| 6 Kinematics | Run; assert no NaN, columns exist | Skip | Run; assert no flip artifact | Run; assert completes |
| 7 Gates | Run; assert PASS, health | — | Optional | Run; assert fallback, health cap |

---

## Part 5: Implementation Notes

- **Config:** Load once (e.g. from `src.pipeline_config`) and pass the same `cfg` (and `max_gap_pos_sec`, etc.) into Step 02, 05, and filtering so production behavior is matched.
- **Loop vs parallel:** Per-cell loop over the **relevant** scenario keys (e.g. `for key in ["standard_dirty", "fatal_gap"]` in Cell 2). No need to run all four in every cell.
- **Failure handling:** Use `pytest` or plain `assert`; on failure, print scenario key and which assertion failed. Optional: collect results in a small dict and print a table at the end of each cell.
- **RightHand:** Include in `standard_dirty` (and optionally in no_static_window) so Cell 4 can assert Winter/Smart Bias for both Spine (trunk) and RightHand (distal).

This revised masterplan is ready for implementation in `qa_pipeline_glassbox_integration.ipynb` once approved.
