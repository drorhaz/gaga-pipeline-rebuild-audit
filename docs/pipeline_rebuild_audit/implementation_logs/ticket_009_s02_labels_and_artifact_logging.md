# Ticket 009 Implementation Log

**Date:** 2026-05-19
**Implementer:** Claude Sonnet 4.6 (LOW_RISK_MECHANICAL — within Batch 2)
**Status:** COMPLETE (with one additional scientific finding flagged)
**Prerequisites:** None — independent ticket within Batch 2

## Pre-Implementation Statement

I have read:
- [x] Ticket 009 spec in `12_implementation_backlog_CORRECTED.md` (lines 474–515)
- [x] `src/preprocessing.py::detect_and_mask_artifacts()` lines 312–370
- [x] `notebooks/02_preprocess.ipynb` Cells 2–10 (data loading, gap fill, summary writes)
- [x] `src/interpolation_logger.py` — `InterpolationLogger.get_summary()` returns per-joint stats including `fallback_count`, `max_gap_size`, `total_frames_interpolated`
- [x] Existing `__interpolation_log.json` (NB02 Cell 9) and `__preprocess_summary.json` (NB02 Cell 10)
- [x] PROJECT_MEMORY locked decisions

## Path Correction vs Backlog

The backlog spec says: *"In `src/preprocessing.py::detect_and_mask_artifacts()` — change log labels"*.

**Actual location of the wrong labels:** NB02 Cells 9 and 10 (not in `src/preprocessing.py`). `detect_and_mask_artifacts()` returns masked numpy arrays — it does not write any string labels.

The wrong labels in NB02 come from reading `CONFIG['POS_RESAMPLE_METHOD'] = 'pchip_single_pass'` and `CONFIG['QUAT_RESAMPLE_METHOD'] = 'slerp'` — but those CONFIG values describe **S03 resampling**, not **S02 artifact masking**. NB02 mislabels them as S02 methods.

**Same precedent as Tickets 003/004/007a/007b:** Notebook edits authorized for ticket-implementation when src-only spec misses the actual locations.

## Two-Site Label Fix

| File | Cell | OLD | NEW |
|------|------|-----|-----|
| NB02 Cell 9 (`__interpolation_log.json`) | `position_method` | `pchip_single_pass` (from CONFIG) | `linear_interp` (actual S02 method via `np.interp`) |
| NB02 Cell 9 | `quaternion_method` | `slerp` (from CONFIG) | `quaternion_normalize` (actual S02 method) |
| NB02 Cell 10 (`__preprocess_summary.json`) | `interpolation_method.positions` | `pchip_single_pass` | `linear_interp` |
| NB02 Cell 10 | `interpolation_method.rotations` | `slerp` | `quaternion_normalize` |

CONFIG values for resampling (S03) remain untouched — they correctly describe S03's PCHIP+SLERP behavior.

## 9 Required Statistics — Schema for `{RUN_ID}__s02_interpolation_stats.json`

| Field | Source | How computed |
|-------|--------|--------------|
| `n_artifact_segments_positions` | df_raw `__p*` cols | Total NaN-run count across all position axis columns |
| `max_artifact_segment_frames_positions` | df_raw | Longest contiguous NaN-run across all position cols |
| `mean_artifact_segment_frames_positions` | df_raw | Mean length of NaN-runs |
| `n_artifact_segments_above_5_frames` | df_raw | Count of NaN-runs longer than 5 frames |
| `n_artifact_segments_above_10_frames` | df_raw | Count of NaN-runs longer than 10 frames (PCHIP activation trigger) |
| `n_gap_fill_events_positions` | interp_logger | Total interpolation events that fired (sum across joints) |
| `n_gap_fill_events_quaternions` | interp_logger | Same for quaternion joints (expected = 0 — no quat gap fill active) |
| `max_gap_duration_frames_positions` | interp_logger | max(max_gap_size) across position joints |
| `max_gap_duration_frames_quaternions` | interp_logger | max(max_gap_size) across quat joints (expected = 0) |

## Files Changed

| File | Change |
|------|--------|
| `src/preprocessing.py` | Add `compute_artifact_segment_stats(df, axis_suffixes)` helper — pure-function, testable in isolation |
| `notebooks/02_preprocess.ipynb` Cell 9 | Fix labels; compute 9 stats; write `__s02_interpolation_stats.json` |
| `notebooks/02_preprocess.ipynb` Cell 10 | Fix labels in preprocess_summary |

**Files NOT modified:**
- `src/interpolation_logger.py` — already returns what we need via `get_summary()`
- Any other file outside this scope
- No PCHIP/SLERP gap-fill code added (per Anti-Overengineering reminder)

## Adversarial Synthetic Tests Plan

1. **A1 — Known NaN counts:** Inject DataFrame with 3 NaN runs of lengths [2, 7, 12] in a single column → assert exact stats
2. **A2 — Multi-column aggregation:** Inject 2 columns with different NaN patterns → assert aggregated counts
3. **A3 — Threshold edge:** NaN runs of exactly 5 and 10 frames → assert correct `> 5` and `> 10` strict count
4. **A4 — Empty/clean dataframe:** Zero NaN → assert all stats are 0
5. **A5 — Single isolated NaN:** 1 NaN frame → 1 segment of length 1
6. **A6 — Boundary NaN:** NaN at very first and last frames → run-length must include them
7. **A7 — Label sanity:** Verify the new label strings (`linear_interp`, `quaternion_normalize`) appear in the JSON

## Results

### Adversarial Synthetic Tests (9/9 PASS — helper function proven in isolation)
| # | Setup | Result |
|---|-------|--------|
| A1 | Single-col runs of lengths [2, 7, 12] | PASS (n=3, max=12, mean=7.0, above_5=2, above_10=1) |
| A2 | Multi-column aggregation (5 segments across 3 cols, lengths [1, 5, 11, 3, 5]) | PASS |
| A3 | Boundary at exactly 5 and 10 (strict > comparison) | PASS |
| A4 | Empty/clean DataFrame | PASS (all zeros) |
| A5 | Single isolated NaN | PASS |
| A6 | NaN at frame 0 (start) and frame N-1 (end) | PASS |
| A7 | Suffix filter — qx ignored when only px/py/pz scanned | PASS |
| A8 | Adjacent NaN runs separated by 1 valid frame — must be 2 segments, NOT merged | PASS |
| A9 | All-NaN column | PASS (n=1, len=100) |

### 4 Dev Set Sessions — All Pipelines PASS, All Verifications PASS
| Session | T1 (sidecar+9 fields) | T2 (interp_log labels) | T3 (preprocess_summary labels) | T5 (numeric hash unchanged) |
|---------|----------------------|------------------------|--------------------------------|----------------------------|
| 651_T1_P1_R1 | PASS | PASS (linear_interp, quaternion_normalize) | PASS | PASS |
| 651_T2_P1_R1 | PASS | PASS | PASS | PASS |
| 671_T1_P2_R1 | PASS | PASS | PASS | PASS |
| 671_T3_P2_R1 | PASS | PASS | PASS | PASS |

### Observed 9 Stats Per Session (all 4 sessions report all zeros)
All 9 fields = 0 for all 4 Dev Set sessions. This is **scientifically meaningful** — see Critical Finding below.

## Critical Scientific Finding (Per Mandate)

The 9 artifact/gap stats all read `0` for the 4 Dev Set sessions. This is initially surprising given that the MUB-NB06 investigation showed `651_T1_P1_R1` has 6 columns with 4–36 NaN frames each in the **S04 filtered parquet**, triggering the lin_kine gate.

**Stage-by-stage NaN tracing (this ticket):**

| Stage | Parquet | NaN columns | Conclusion |
|-------|--------|-------------|-----------|
| S01 (parsed) | `__parsed_run.parquet` | 0 (clean) | MoCap data ARRIVES clean |
| S02 (preprocessed) | `__preprocessed.parquet` | 0 (clean) | S02 preserves cleanness |
| S03 (resampled) | `__resampled.parquet` | 0 (clean) | S03 PCHIP+SLERP preserves cleanness |
| **S04 (filtered)** | `__filtered.parquet` | **6 cols with 4–36 NaN each** | **S04 INTRODUCES NaN** |

**Conclusion:** The NaN that breaks NB06's linear kinematics gate is **introduced by S04's Winter/Butterworth filtering**, not by upstream artifact masking. This is the actual root cause of the MUB-NB06 finding.

**Action taken:**
1. Updated `MUB_NB06_lin_kine_nan_gate_2026-05-18.md` with an addendum documenting the S01→S04 trace
2. Updated `PROJECT_MEMORY_FOR_IMPLEMENTATION.md` to add S04 NaN introduction as a known scientific anomaly
3. **Ticket 009's `0` artifact stats are CORRECT** — S02 truly has no artifacts. The sidecar accurately reflects S02's clean state.

**Implication for future work:** Any future investigation of the linear kinematics drop (the deferred NB06 gate fix) must focus on S04, not S02. A potential follow-up MUB on S04 boundary handling is warranted (deferred to post-Minimal-v1).

## Sign-Off

- [x] Helper function added to `src/preprocessing.py` and unit-tested in isolation (9/9 pass)
- [x] Labels corrected in NB02 Cell 9 (`__interpolation_log.json`) and Cell 10 (`__preprocess_summary.json`)
- [x] 9 stats fields present in new `__s02_interpolation_stats.json` for all 4 Dev Set sessions
- [x] 4-session Dev Set: parquet numeric hash unchanged (LOCAL blast radius confirmed)
- [x] Anti-overengineering preserved: no PCHIP or SLERP gap-fill code added
- [x] Critical scientific finding (S04 NaN introduction) flagged and documented in MUB + PROJECT_MEMORY
- [x] Log complete
