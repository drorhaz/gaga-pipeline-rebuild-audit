# Ticket 010 Implementation Log

**Date:** 2026-05-19
**Implementer:** Claude Sonnet 4.6 (MODERATE_COMPLEXITY — final ticket of Batch 2)
**Status:** COMPLETE
**Prerequisites:** 008 ✓

## Pre-Implementation Statement

I have read:
- [x] Ticket 010 spec in `12_implementation_backlog_CORRECTED.md` (lines 519–545)
- [x] `src/v2_feature_engine.py` line 57 (`JOINT_GROUPS`), line 331 (`compute_atf`), line 430 (`_group_median` usage)
- [x] PROJECT_MEMORY LD-12: Hips excluded from ATF_axial (root joint; `lin_vel_rel_mag = 0` by definition)
- [x] Verified: `compute_atf` is called ONLY by NB11 and NB09 (downstream), NOT by NB01–08 (kinematics pipeline)
- [x] Pre-implementation magnitude analysis completed on all 4 Dev Set sessions (see Results below)

## Architectural Note (Critical — Same as Ticket 008)

The backlog labels Ticket 010 as `PARQUET_REGEN`. However, `compute_atf` lives in `v2_feature_engine.py` which is called only by NB11 (downstream feature engine), NOT by the active pipeline (NB01–08). Therefore:

- **`kinematics_master.parquet` is UNAFFECTED** — its numeric hash will be identical to post-T007b baseline. No re-run of the kinematics pipeline is needed or meaningful.
- **The "PARQUET_REGEN" reference in the backlog applies to the downstream feature parquet** produced by NB11 (which is not part of the Minimal v1 active pipeline sequence).
- The ATF_axial value change is real and impacts NB11 feature outputs.

This is the same architectural finding established and accepted under Ticket 008.

## Pre-Implementation Magnitude (computed directly via `compute_atf` on Dev Set kinematics_master)

| Session | atf_axial OLD (with Hips) | atf_axial NEW (no Hips) | Δ | % change |
|---------|---------------------------|--------------------------|---|----------|
| 651_T1_P1_R1 | 0.8098 | 0.8202 | +0.0104 | **+1.28%** |
| 651_T2_P1_R1 | 0.8537 | 0.8537 | 0.0000 | +0.00% (see note below) |
| 671_T1_P2_R1 | 0.9667 | 0.9676 | +0.0009 | +0.09% |
| 671_T3_P2_R1 | 0.9264 | 0.9300 | +0.0036 | +0.38% |

**All deltas are positive** — confirms the spec's rationale: including Hips (which always has `lin_vel_rel_mag = 0` because it's the root joint) biased the median DOWN. Removing it raises atf_axial.

**Why session 651_T2 shows 0% change:** Per the MUB-NB06 finding (updated in Ticket 009), session 651_T2's S04 filtering introduced NaN in `Hips__px` and `Spine__px`, which silently dropped `Hips__lin_vel_rel_mag` and `Spine__lin_vel_rel_mag` columns from kinematics_master. `compute_atf` therefore already returned NaN for those joints and they were excluded from the median by the `if not np.isnan(...)` filter. The OLD median was already (effectively) computed without Hips for this session. This is **another downstream consequence of the deferred S04 NaN issue**.

**Per-joint axial ATF values that drove the medians:**

| Session | Hips | Spine | Spine1 | Neck | Head | OLD median input | NEW median input |
|---------|------|-------|--------|------|------|------------------|------------------|
| 651_T1_P1_R1 | 0.0000 | 0.8305 | 0.8098 | NaN | NaN | [0, 0.8098, 0.8305] | [0.8098, 0.8305] |
| 651_T2_P1_R1 | NaN | NaN | 0.8537 | 0.8459 | 0.8569 | [0.8459, 0.8537, 0.8569] | (same) |
| 671_T1_P2_R1 | 0.0000 | 0.9651 | 0.9667 | 0.9685 | 0.9775 | [0, 0.9651, 0.9667, 0.9685, 0.9775] | [0.9651, 0.9667, 0.9685, 0.9775] |
| 671_T3_P2_R1 | 0.0000 | 0.9239 | 0.9264 | 0.9335 | 0.9470 | [0, 0.9239, 0.9264, 0.9335, 0.9470] | [0.9239, 0.9264, 0.9335, 0.9470] |

## Files Changed

| File | Change |
|------|--------|
| `src/v2_feature_engine.py` line 58 | Remove `'Hips'` from `JOINT_GROUPS['axial']` list |
| `docs/METHODOLOGY_SPEC_v2.md` | Append amendment explaining the exclusion (if file exists) |

## Adversarial Synthetic Test Plan

1. **A1 — Synthetic median with known values:** Build mock atf_per_joint dict; verify `_group_median` returns expected median for OLD and NEW group lists
2. **A2 — Hips=0 bias confirmation:** Synthetic atf values [0, 0.5, 0.6, 0.7, 0.8] (Hips first) → OLD median = 0.6, NEW median (no Hips) = 0.65
3. **A3 — Regression: kinematics_master hash unchanged** (LOCAL to feature engine)

## Results — All Tests Pass

| Test | Result |
|------|--------|
| A0: `JOINT_GROUPS["axial"]` = `['Spine','Spine1','Neck','Head']` | **PASS** |
| A1: Synthetic median [0,0.5,0.6,0.7,0.8] → OLD=0.6, NEW=0.65 | **PASS** |
| A2: Real `compute_atf` matches pre-impl predicted NEW values (all 4 Dev Set sessions) | **PASS** |
| A3: `kinematics_master.parquet` numeric hashes unchanged | **PASS** (all 4 sessions byte-identical) |

## Sign-Off
- [x] Code change applied (`src/v2_feature_engine.py` line ~58)
- [x] Spec amendment added to `docs/METHODOLOGY_SPEC_v2.md`
- [x] Adversarial + real-data tests pass
- [x] Magnitude documented (per-session table, per-joint inputs)
- [x] kinematics_master hashes verified unchanged (LOCAL to feature engine)
- [x] Tier 2 PROJECT_MEMORY checkpoint locked with NEW state
- [x] Log complete
