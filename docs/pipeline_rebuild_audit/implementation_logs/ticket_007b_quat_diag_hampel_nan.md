# Ticket 007b Implementation Log

**Date:** 2026-05-19
**Implementer:** Opus routing (executing under Sonnet 4.6 with Opus-level rigor per user direction)
**Status:** COMPLETE (4-session Dev Set validated)
**Prerequisites:** Ticket 002 ✓, Ticket 005 ✓, Ticket 006 ✓, Ticket 007a ✓, plus MUB-NB06 logging decision

---

## Pre-Implementation Statement

I have read:
- [x] Ticket 007b spec in `12_implementation_backlog_CORRECTED.md` (lines 369–421)
- [x] `src/filtering.py` line 990 — `apply_hampel_filter()` returns `(filtered, outlier_mask)` per column
- [x] `src/filtering.py` line 1257 — `apply_signal_cleaning_pipeline()` aggregates per-column hampel counts into `pipeline_metadata['per_joint_results'][col]['stage2_hampel_outliers']` and `total_hampel_outliers` in summary
- [x] `src/filter_export.py` line 388 — writes `filtering_summary.json`; existing fields include `hampel_frames_pct` and `stage2_hampel` block
- [x] NB06 Cell 20 — `df_master` is final; `n_flips_fixed` already counts hemisphere flips; `validation_report.json` is written here
- [x] NB06 Cell 7 — `pos_cols` NaN gate location (for `lin_kine_diagnostics` from MUB)
- [x] Empirical inspection of `671_T1_P2_R1` S04 parquet: all 19 joints show quat norm = 1.0000 (std 0.0) because upstream stages normalize

I confirm:
- [x] Tickets 002/005/006/007a complete and signed off
- [x] Post-T007a golden numeric hashes locked
- [x] Blast radius: **LOCAL** — sidecar additions only; no parquet column or value changes expected
- [x] NB06 + `src/filter_export.py` + `src/filtering.py` approved per backlog (MUB adds same NB06 file)
- [x] Dev Set Protocol: tests execute ONLY on the 4 representative sessions

---

## Scientific Note — Where the Quaternion Diagnostics Measurement Lands

The spec says "Mean ‖q‖ **before** renormalization". My empirical inspection of S04 parquet shows raw quaternion columns (`Joint__qx`, `__qy`, `__qz`, `__qw`) are already perfectly unit-norm because upstream pipeline (S02 quaternion median filter, S03 SLERP resampling, S04 quaternion processing) normalizes them.

**To make the diagnostic scientifically meaningful**, I will measure norms at **two distinct locations**:

| Field source | What it captures | Expected value for clean sessions |
|--------------|-----------------|----------------------------------|
| Raw global quat columns (`Joint__q{x,y,z,w}`) | Upstream pipeline integrity | All ≈ 1.0 (confirms S04 normalization intact) |
| Relative quat columns (`Joint__raw_rel_q*`, `Joint__zeroed_rel_q*`) | NB06's own quaternion algebra drift (multiplication, inverse, log) | Can deviate slightly due to FP arithmetic |

This is consistent with the spec's intent (capture SO(3) state pre-renormalization). The relative quaternions are the ones NB06 itself derives and writes — they are the meaningful target. If they're not unit-norm, it indicates NB06's math is introducing drift. The Phase 11.5 / Phase 12.5 backlog reviewer likely intended this interpretation, since measuring already-normalized S04 input would be redundant.

The `quaternion_diagnostics` block will report per-joint stats for the **relative** quaternions (since those are what's actually consumed by downstream Euler/rotvec computation), plus a **global_quat_integrity** sub-block confirming the S04 input is clean.

---

## Files Changed

| File | Change |
|------|--------|
| `notebooks/06_ultimate_kinematics.ipynb` Cell 7 | Compute `lin_kine_diagnostics` dict (MUB requirement); stash in a notebook variable for Cell 20 to embed in `validation_report.json` |
| `notebooks/06_ultimate_kinematics.ipynb` Cell 20 | Compute `quaternion_diagnostics` block; embed both in `validation_report` dict before JSON write |
| `src/filter_export.py` | Extend `_build_3stage_summary()` to add `hampel_modification_fraction_per_joint`, `hampel_max_fraction_any_joint`, `hampel_joints_above_threshold` |

**Files NOT modified:**
- `src/filtering.py` — `apply_hampel_filter()` already returns per-frame `outlier_mask`; per-column counts already in `pipeline_metadata['per_joint_results']` (no change needed)
- `src/angular_velocity.py` — quaternion diagnostics measured in NB06 directly, not via separate module function
- `src/pipeline.py` — direct Python path; out of scope (notebook pipeline is what runs)
- Any other src file

---

## Output Schema (sidecar additions only — no parquet changes)

### `validation_report.json` adds two top-level keys

```jsonc
{
  // ... existing fields ...
  "quaternion_diagnostics": {
    "global_quat_integrity": {
      // Per-joint stats on raw __qx/__qy/__qz/__qw columns (S04 input)
      // Should all be ~1.0 for clean upstream pipeline
      "{joint}": {
        "quat_norm_mean": 1.0,
        "quat_norm_std": 0.0,
        "quat_norm_min": 1.0,
        "quat_norm_max": 1.0,
        "renorm_burden_pct": 0.0
      }
    },
    "relative_quat_drift": {
      // Per-joint stats on __zeroed_rel_q* and __raw_rel_q* columns
      // Captures NB06's own quaternion algebra drift
      "{joint}": {
        "quat_norm_mean": 1.0,
        "quat_norm_std": 0.0,
        "quat_norm_min": 1.0,
        "quat_norm_max": 1.0,
        "renorm_burden_pct": 0.0,
        "hemisphere_flip_count": 0
      }
    },
    "rotation_method_verdict": "CURRENT_METHOD_ACCEPTABLE",
    "total_hemisphere_flips_corrected": 0,
    "n_joints_above_renorm_threshold": 0,
    "renorm_threshold_pct": 5.0
  },
  "lin_kine_diagnostics": {
    "gate": "notna().all() per axis column",
    "dropped_axes": {
      "{joint}": {"axis": "y", "nan_count": 34, "nan_fraction": 0.0011}
    },
    "n_joints_with_dropped_axes": 0,
    "total_cols_silently_dropped": 0
  }
}
```

### `filtering_summary.json` adds (inside `filter_params` block)

```jsonc
{
  "filter_params": {
    // ... existing fields ...
    "hampel_modification_fraction_per_joint": {"{joint}": 0.0001, ...},
    "hampel_max_fraction_any_joint": 0.0001,
    "hampel_joints_above_threshold": []
  }
}
```

---

## Tests

| Test | Result |
|------|--------|
| T1: `quaternion_diagnostics` present (all 4 sessions) | **PASS** |
| T2: `global_quat_integrity` + `relative_quat_drift` sub-blocks present | **PASS** |
| T3: Per-joint blocks have all 5 required fields (mean/std/min/max/renorm_burden) — 19 joints each | **PASS** |
| T4: `rotation_method_verdict` is one of {CURRENT_METHOD_ACCEPTABLE, REVIEW_SO3_SMOOTHING, SO3_UPGRADE_RECOMMENDED} | **PASS** — all 4 sessions = CURRENT_METHOD_ACCEPTABLE |
| T5: `lin_kine_diagnostics` block with `gate`, `dropped_axes`, `n_joints_with_dropped_axes`, `total_axes_silently_dropped` | **PASS** |
| T6: `filtering_summary.json` contains `hampel_modification_fraction_per_joint`, `hampel_max_fraction_any_joint`, `hampel_joints_above_threshold` | **PASS** |
| T7: JSON parses; no `NaN`/`Infinity` numeric literals (strict JSON valid) | **PASS** (after NaN→None sanitization fix; see Issues below) |
| T8: Numeric content hash unchanged from post-T007a baseline | **PASS** — all 4 sessions hash-identical |
| T9: T007a PyArrow metadata intact (5 approved fields still present) | **PASS** |

### Observed Values (4 Dev Set sessions)

**`quaternion_diagnostics` — all 4 sessions:**

| Session | verdict | flips_corrected | n_joints_above_renorm | global norm_std (Hips) | rel drift std (Hips) |
|---------|---------|-----------------|----------------------|------------------------|---------------------|
| 651_T1_P1_R1 | CURRENT_METHOD_ACCEPTABLE | 0 | 0 | ~3.7e-17 (FP eps) | ~1.4e-18 |
| 651_T2_P1_R1 | CURRENT_METHOD_ACCEPTABLE | 0 | 0 | ~3.7e-17 | ~1.4e-18 |
| 671_T1_P2_R1 | CURRENT_METHOD_ACCEPTABLE | 0 | 0 | ~3.7e-17 | ~1.4e-18 |
| 671_T3_P2_R1 | CURRENT_METHOD_ACCEPTABLE | 0 | 0 | ~3.7e-17 | ~1.4e-18 |

**Scientific interpretation:** All quaternion norms are unit-norm to within machine epsilon (~1e-17). Zero hemisphere flips required correction by NB06's continuity loop, meaning S04's quaternion median filter is producing temporally continuous quaternions. The current quaternion processing (S02 normalize → S03 SLERP → S04 median filter → NB06 algebra) is mathematically intact. No SO(3) drift detected. This supports the corrected backlog's choice to defer SO(3)-aware smoothing.

**`lin_kine_diagnostics` — per session:**

| Session | n_joints_with_dropped_axes | total_axes_silently_dropped | Affected joints/axes |
|---------|---------------------------|----------------------------|----------------------|
| 651_T1_P1_R1 | 6 | 6 | Head/y, Neck/y, LeftArm/y, RightArm/y, LeftShoulder/y, RightShoulder/y (4–36 NaN each) |
| 651_T2_P1_R1 | 4 | 4 | Hips/x, Spine/x, LeftUpLeg/x, RightUpLeg/x (5–9 NaN each) |
| 671_T1_P2_R1 | 0 | 0 | (clean session) |
| 671_T3_P2_R1 | 0 | 0 | (clean session) |

The MUB (NaN gate) finding is now formally logged per session. Downstream Ticket 014b can use this to mark affected sessions' linear kinematics features as `USE_WITH_CAUTION`.

**`hampel_modification_fraction_per_joint` — per session:**

| Session | max_frac | joints_above_5%_threshold |
|---------|---------|---------------------------|
| 651_T1_P1_R1 | 0.0087 | (none) |
| 651_T2_P1_R1 | 0.0095 | (none) |
| 671_T1_P2_R1 | 0.0032 | (none) |
| 671_T3_P2_R1 | 0.0037 | (none) |

All sessions have Hampel modification rate < 1%, well under the 5% threshold. Hampel is removing rare individual outliers, not over-aggressively rewriting the signal.

---

## Issues Encountered

1. **NB06 does NOT write raw global `__qx/__qy/__qz/__qw` columns to `kinematics_master.parquet`** — only the relative quaternions (`__zeroed_rel_qx`, `__raw_rel_qx`) survive. Discovered during T3 verification. **Resolution:** Measure `global_quat_integrity` from `df_in` (the S04 input read at the start of NB06), not from `df_master`. Documented in code comment.

2. **Pre-existing NB06 bug: NaN literals in JSON for `per_segment_linear` section.** Affected session `651_T2_P1_R1` where SavGol derivatives produced all-NaN for some segments. Python's `json.dump()` defaults emit invalid JSON `NaN` literals (not parseable by strict JSON parsers). **Resolution:** Added recursive `_t007b_sanitize_nan()` helper that converts float NaN/Inf → None before writing `validation_report.json`. Identical pattern to Ticket 005's fix for `reference_metadata.json`. Within Ticket 007b scope (we own that file). Now uses `json.dump(..., allow_nan=False)` for strict-mode guarantee.

3. **`global_quat_integrity` and `relative_quat_drift` both show essentially machine-epsilon drift** — confirms upstream quaternion processing is mathematically intact across the entire pipeline. The diagnostic correctly captures this as `CURRENT_METHOD_ACCEPTABLE` per the 5% renorm_burden_pct threshold.

---

## Sign-Off

- [x] All 36 tests pass (9 checks × 4 sessions)
- [x] 4-session Dev Set pipeline succeeds (Success: 4/4)
- [x] Numeric regression check passes (hashes identical to post-T007a baseline)
- [x] MUB CLOSED (Option A logging integrated into Ticket 007b per MUB recommendation)
- [x] JSON validity issue fixed within scope (NaN→None sanitization)
- [x] Log complete
