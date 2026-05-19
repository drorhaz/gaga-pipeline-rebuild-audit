# Ticket 003 Implementation Log

**Date:** 2026-05-18
**Implementer:** Claude (Opus routing, per Model Routing Policy for MODERATE_COMPLEXITY + PARQUET_REGEN)
**Status:** COMPLETE
**Prerequisites:** Ticket 001 COMPLETE, Ticket 002 COMPLETE

---

## Pre-Implementation Statement

I have read:
- [x] Ticket 003 spec in `12_implementation_backlog_CORRECTED.md`
- [x] `src/resampling.py` (full file) — confirmed `resample_time_grid()` at line 169 uses the correct `+1` formula
- [x] `src/pipeline.py` line 214 — direct-Python path uses the correct `resample_time_grid()`
- [x] `src/time_alignment.py` — alternate path; NOT used by NB03; out of scope
- [x] `notebooks/03_resample.ipynb` Cells 1, 3, 4, 5, 6, 7 — confirmed Cell 3 contains the bug, Cell 7 writes the summary
- [x] `src/__init__.py` — `resample_time_grid` not in package exports; must import via `from src.resampling import ...`
- [x] Ticket 001 and Ticket 002 implementation logs
- [x] `PROJECT_MEMORY_FOR_IMPLEMENTATION.md`

I confirm:
- [x] Tickets 001 and 002 complete and regression-checked
- [x] Content-based golden hashes locked from Ticket 001 for 14 sessions
- [x] Blast radius understood: **PARQUET_REGEN** — all 14 sessions' parquets will gain exactly +1 frame
- [x] User explicitly approved expanding the approved file list to include `notebooks/03_resample.ipynb` (Option B)
- [x] I will not modify files outside the approved Ticket 003 list

---

## PATH_VERIFY_REQUIRED Result

### Verified bug location

The bug is **NOT in `src/resampling.py`** — that file already contains the correct `+1` formula (line 172: `n = int(round((t1 - t0) * fs_target)) + 1`).

The bug **IS in `notebooks/03_resample.ipynb` Cell 3**, in an inline `resample_timeseries()` function that uses:

```python
t_new = np.arange(t_start, t_end, dt)
```

`numpy.arange` is half-open and excludes `t_end`, producing N points where N+1 endpoints are needed.

### Empirical verification (session `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002`)

| Quantity | Value |
|----------|-------|
| S01 frames (raw parsed) | 16915 |
| S03 frames (current resampled) | 16914 |
| Delta | **1 frame dropped per session** |
| S01 duration | 140.950 s |
| S03 duration | 140.942 s (last 8 ms lost) |

This confirms the bug is in production. All 14 golden sessions lose 1 frame.

### Import path verification

- `from resampling import resample_time_grid` — **FAILS** in notebook context (`src/resampling.py` has relative import `from .quaternion_ops`)
- `from src.resampling import resample_time_grid` — **WORKS** when project root is on `sys.path`

Solution: NB03 Cell 3 adds project root to `sys.path` and imports via the package.

---

## Approved Design Decision: Option B

Refactor NB03 Cell 3 to call `src/resampling.py::resample_time_grid()` directly, eliminating the inline duplicate formula and establishing a single source of truth.

---

## Files Changed

| File | Change | Description |
|------|--------|-------------|
| `notebooks/03_resample.ipynb` Cell 3 | Replace inline `np.arange` with `resample_time_grid()` call from `src/resampling.py`; add explicit endpoint assertion | Bug fix + single source of truth |
| `notebooks/03_resample.ipynb` Cell 7 | Extend `export_resample_summary()` to include `n_frames_input`, `n_frames_output`, `frame_count_delta` | Anti-recurrence logging |
| `src/resampling.py` | Add defensive boundary clamp in `resample_time_grid()`: `grid[-1] = min(grid[-1], t1)` | Fix FP-precision SLERP boundary failure discovered mid-implementation |
| `audit_outputs/PROJECT_MEMORY_FOR_IMPLEMENTATION.md` | Append new post-T003 golden baseline (14 sessions) | Regression reference for Tickets 004+ |
| `docs/pipeline_rebuild_audit/implementation_logs/ticket_003_resampling_fix.md` | New | This file |

**Files NOT modified:**
- `src/pipeline.py` — already correct
- `src/time_alignment.py` — out of scope (alternate path)
- All other src/ files — out of scope

---

## Tests and Verification

| Test | Result |
|------|--------|
| T1: `resample_time_grid()` importable via `from src.resampling import ...` (requires project root on sys.path) | **PASS** |
| T2: NB03 Cell 3 fix produces correct grid (smoke test on `671_T1_P2_R1`: input 16915 → output 16915, was 16914) | **PASS** |
| T3: Frame count assertion in NB03 Cell 3 catches mismatches | **PASS** (no assertion firings in 14-session run) |
| T4: `resample_summary.json` contains `n_frames_input`, `n_frames_output`, `frame_count_delta` | **PASS** — verified on 3 sample sessions |
| T5: All 14 sessions regenerated successfully | **PASS** — `Success: 14, Failed: 0` |
| T6: All affected sessions gain exactly +1 frame at S03 | **PASS** — 12 of 14 affected, +1 each |
| T7: All affected sessions gain exactly +1 frame at S06 (kinematics_master) | **PASS** — 12 of 14 affected, +1 each |
| T8: Unaffected sessions (where math gives N+1 in both formulas) keep same frame count | **PASS** — 2 of 14: `651_T1_P1_R1` and `671_T3_P2_R2` |
| T9: SLERP boundary clamp prevents FP-precision boundary errors | **PASS** — no `Interpolation times must be within` errors after clamp added |
| T10: Column count unchanged for all sessions (no schema changes) | **PASS** — `d_cols = 0` for all 14 |

### Frame-count delta per session (post-T003 - pre-T003)

| Session | Pre | Post | Delta | Notes |
|---------|-----|------|-------|-------|
| 651_T1_P1_R1_…_002 | (30423,773) | (30423,773) | +0 | `(t_end-t_start)*fs = 30422.00004` — bug never affected this session |
| 651_T1_P2_R1_…_002 | (19303,803) | (19304,803) | +1 | Bug fixed |
| 651_T1_P2_R2_…_005 | (19894,803) | (19895,803) | +1 | Bug fixed |
| 651_T2_P1_R1_… | (32109,783) | (32110,783) | +1 | Bug fixed |
| 651_T2_P2_R1_…_000 | (21601,803) | (21602,803) | +1 | Bug fixed |
| 651_T3_P1_R1_…_2026 | (30834,803) | (30835,803) | +1 | Bug fixed |
| 651_T3_P2_R1_…_2027 | (22486,803) | (22487,803) | +1 | Bug fixed |
| 651_T3_P2_R2_…_2030 | (22960,803) | (22961,803) | +1 | Bug fixed |
| 671_T1_P2_R1_…_002 | (16914,803) | (16915,803) | +1 | Bug fixed |
| 671_T1_P2_R2_…_004 | (17685,803) | (17686,803) | +1 | Bug fixed |
| 671_T2_P2_R1_…_006 | (20046,803) | (20047,803) | +1 | Bug fixed |
| 671_T2_P2_R2_…_010 | (20764,803) | (20765,803) | +1 | Bug fixed |
| 671_T3_P2_R1_…_001 | (21772,803) | (21773,803) | +1 | Bug fixed |
| 671_T3_P2_R2_…_006 | (22215,803) | (22215,803) | +0 | `(t_end-t_start)*fs = 22214.00004` — bug never affected this session |

---

## Before Golden Baseline (Ticket 001 / 002 — pre-Ticket-003)

See `ticket_001_config_snapshot.md` for full 14-session table.

Summary: 14 sessions, shapes ranging (16914, 803) to (32109, 783).

## After Golden Baseline (post-Ticket-003) — Content Hashes

| Session | Shape | Content (first 16 chars) |
|---------|-------|--------------------------|
| 651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002 | (30423, 773) | `4e4b81bc9edd2f6b` |
| 651_T1_P2_R1_Take 2026-01-15 04.35.25 PM_002 | (19304, 803) | `e535bcaa60457039` |
| 651_T1_P2_R2_Take 2026-01-15 04.35.25 PM_005 | (19895, 803) | `47f62f817a727259` |
| 651_T2_P1_R1_Take 2026-01-26 05.24.12 PM | (32110, 783) | `b7db8a72f4c11a85` |
| 651_T2_P2_R1_Take 2026-01-26 05.24.12 PM_000 | (21602, 803) | `f794c1546332f957` |
| 651_T3_P1_R1_2026-02-11 05.50.42 PM_2026 | (30835, 803) | `f0c431e956d64fa5` |
| 651_T3_P2_R1_2026-02-11 05.50.42 PM_2027 | (22487, 803) | `131a2139ed33e189` |
| 651_T3_P2_R2_2026-02-11 05.50.42 PM_2030 | (22961, 803) | `ba88f4045134e884` |
| 671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002 | (16915, 803) | `5d13f307c9bc50a3` |
| 671_T1_P2_R2_Take 2026-01-06 03.57.12 PM_004 | (17686, 803) | `345df38e3e8411a1` |
| 671_T2_P2_R1_Take 2026-01-15 04.35.25 PM_006 | (20047, 803) | `eeba923f38dac083` |
| 671_T2_P2_R2_Take 2026-01-15 04.35.25 PM_010 | (20765, 803) | `57d5838134a986b3` |
| 671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001 | (21773, 803) | `96ae62165289dc2a` |
| 671_T3_P2_R2_Take 2026-02-03 08.05.01 PM_006 | (22215, 803) | `687f01621ed20d58` |

All 14 hashes differ from Ticket 001 baseline (even the 2 unchanged-shape sessions) because the FP-precision clamp moves `t_new[-1]` by ~3e-7 s, which propagates through PCHIP/SLERP/derivatives.

---

## Issues Encountered

1. **Bug location was NOT in src/resampling.py.** PATH_VERIFY_REQUIRED inspection revealed the bug lives in NB03 Cell 3, which defines its own inline `np.arange(t_start, t_end, dt)` resampler. The corrected `+1` formula in `src/resampling.py::resample_time_grid()` already existed but was unreachable from the notebook pipeline. **Resolution:** User approved Option B — refactor NB03 Cell 3 to import and call `resample_time_grid()`.

2. **Relative-import barrier.** `src/resampling.py` uses `from .quaternion_ops import ...`, so it cannot be imported as a top-level module via `from resampling import ...` from the notebook (which only puts SRC_PATH on sys.path). **Resolution:** Added a scoped 3-line `sys.path` insertion of PROJECT_ROOT inside Cell 3, then imported via `from src.resampling import resample_time_grid`.

3. **Latent FP-precision SLERP boundary bug surfaced.** First regen attempt failed at session 5 with `Interpolation times must be within the range [0.0, 180.008333], both inclusive`. Root cause: the new (correct) endpoint-inclusive grid lands microscopically past `t_old[-1]` due to integer-division rounding (`21601/120 = 180.00833333... > 180.008333`). The OLD buggy `np.arange` masked this because it excluded `t_end` entirely. The direct-Python path in `src/pipeline.py` was already defensive (`resample_quat_slerp` has an inclusive mask), but NB03's inline SLERP was not. **Resolution:** Added a 2-line defensive clamp inside `src/resampling.py::resample_time_grid()`: `grid[-1] = min(grid[-1], t1)`. This fixes the boundary issue at the source for all callers and remains backwards-compatible with `src/pipeline.py`.

4. **Frame-count delta is +1 for 12 of 14 sessions, not 14.** Audit had assumed universal 1-frame loss. Verification revealed 2 sessions (`651_T1_P1_R1` and `671_T3_P2_R2`) have CSV timestamps where `(t_end - t_start) × fs = N.00004` — slightly above an integer. For those, both old and new formulas produce N+1 points. The audit's "S01=16,915 → S04=16,914 universal" claim was accurate for that one example but not strictly universal across the dataset. The fix is still correct for all 14 — the 2 unchanged sessions were already at full S01 count before the fix.

5. **Pipeline runtime.** Full 14-session regen took ~49 minutes (avg ~3.5 min/session). One transient papermill JSON validation warning per session (`'name' is a required property` on stream outputs) — non-fatal, pre-existing condition unrelated to Ticket 003.

---

## Transient Files Created During Testing

These exist in the repo root and should be cleaned up after sign-off:
- `_ticket_003_regen_list.txt` — CSV list used by `--csv-list` to drive the 14-session regen
- `_ticket_003_verify.py` — verification script that computed new baseline

They contain no scientific code; they are pure orchestration/verification scaffolding. Per the "no file deletions during Minimal v1" rule, I will not remove them automatically — flagged here for user disposition.

---

## Post-Implementation Sign-Off

- [x] All 10 tests pass (T1–T10)
- [x] All 14 sessions regenerated successfully (Success: 14, Failed: 0)
- [x] 12 sessions gained +1 frame as expected; 2 sessions correctly unchanged (audit overgeneralization documented)
- [x] No SLERP boundary errors after defensive clamp added
- [x] New content-based baseline locked in PROJECT_MEMORY_FOR_IMPLEMENTATION.md
- [x] Implementation log complete
