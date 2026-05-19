# Ticket 002 Implementation Log

**Date:** 2026-05-18
**Implementer:** Claude Sonnet 4.6 (Phase 13 agent)
**Status:** COMPLETE
**Prerequisite:** Ticket 001 — COMPLETE (signed off)

---

## Pre-Implementation Statement

I have read:
- [x] Ticket 002 spec in `12_implementation_backlog_CORRECTED.md`
- [x] `src/preprocessing.py` (full file — `parse_optitrack_csv()` at line 130; `T` at line 179; existing unrecoverable-parse ValueError at line 153; `loader_report` at lines 264–288)
- [x] `src/pipeline.py` (full file — `run_pipeline()` at line 136; broad except block at line 336; existing 5s duration guard at lines 199–207 — KEEP_AS_IS)
- [x] `run_pipeline.py` (full file — `process_single_csv()` at line 276; notebook loop at lines 312–320; failure detection at lines 317–320)
- [x] `notebooks/01_Load_Inspect.ipynb` (inspected — Cell 5 calls `parse_optitrack_csv()`; Cell 14 writes step01_loader_report.json via `enhanced_report`)
- [x] `notebooks/06_ultimate_kinematics.ipynb` (inspected — confirms `run_pipeline()` from src/pipeline.py is NOT called by NB06; kinematics computed inline; OUT_DIR = `derivatives/step_06_kinematics/`)
- [x] All prerequisite ticket implementation logs — Ticket 001 COMPLETE
- [x] `PROJECT_MEMORY_FOR_IMPLEMENTATION.md`

I confirm:
- [x] Ticket 001 is complete and regression-checked
- [x] Content-based golden hashes locked from Ticket 001 implementation log (14 sessions)
- [x] Blast radius understood: **LOCAL** — for valid sessions, no parquet data changes; for FAIL sessions, no parquet is produced
- [x] I will not modify files not listed in the approved Ticket 002 file list

### Key findings from NB06 inspection

`src/pipeline.py::run_pipeline()` is **not called by the notebook pipeline**. NB06 implements kinematics fully inline. The `run_pipeline()` function is a legacy direct-Python path only. Therefore:
- The FAIL halt for the notebook pipeline is achieved by `parse_optitrack_csv()` raising → NB01 fails → `run_pipeline.py` stops subsequent notebooks
- The fail report for the notebook pipeline is written by `run_pipeline.py::_write_s01_fail_report()` (new helper method)
- The fail report for the direct Python path is written by `src/pipeline.py::run_pipeline()` except block

### Design decisions confirmed

- **Fail report path:** `derivatives/step_01_parse/{RUN_ID}__s01_fail_report.json` (user-approved)
- **Approved files:** `src/preprocessing.py`, `src/pipeline.py`, `run_pipeline.py` (user-approved Option B)
- **gate_01_status in S01 stage JSON:** Added to `loader_report` returned by `parse_optitrack_csv()`. NB01's `enhanced_report` (Cell 14) does NOT automatically forward it, but `loader_report` is pprint'd in NB01 Cell 7. This is acceptable for Minimal v1; Ticket 007a handles PyArrow metadata.

### Existing 5s guard in src/pipeline.py

Lines 199–207 contain an existing `min_run_seconds = 5.0` duration guard. This is KEEP_AS_IS per anti-overengineering rules. The new 30s/3600-frame gate in `parse_optitrack_csv()` will trigger before `run_pipeline()` is even reached in the direct Python path (since it raises at parse time). The 5s guard remains for any edge case where `run_pipeline()` is called directly without going through `parse_optitrack_csv()`.

---

## Approved FAIL Conditions

| Condition | Source |
|-----------|--------|
| Frame count T < 3600 | USER DIRECTIVE — LD-6 |
| Duration < 30.0 seconds | USER DIRECTIVE — LD-6 |
| Missing Frame/Time columns (file unreadable) | Already raises ValueError at line 153 — no change needed |

## WARN Conditions (must NOT become FAIL)

| Condition | Handling |
|-----------|----------|
| Marker label mismatch | Already tracked in `loader_report['segments_missing_list']`; no exception raised |
| Column count deviations | Already logged; no exception raised |

---

## Files Changed

| File | Change type | Description |
|------|-------------|-------------|
| `src/preprocessing.py` | Addition | Gate check in `parse_optitrack_csv()` after T computed; adds `gate_01_status` to `loader_report`; raises `ValueError("S01_GATE_FAIL:...")` on FAIL |
| `src/pipeline.py` | Addition | In `run_pipeline()` except block: detect S01_GATE_FAIL, write `s01_fail_report.json`, return FAIL status |
| `run_pipeline.py` | Addition | New `_write_s01_fail_report()` method; call it in `process_single_csv()` when NB01 fails with S01_GATE_FAIL |

---

## Tests Run

| Test | Input | Result |
|------|-------|--------|
| T1: 5-frame CSV (0.033s) → `ValueError: S01_GATE_FAIL` raised | Synthetic: 5 frames, 0.033s | **PASS** — `reason=frame_count_too_short` |
| T2: 3700-frame, 28s CSV → FAIL (duration_too_short) | Synthetic: 3700 frames, 28s | **PASS** — `reason=duration_too_short` |
| T3: 3700-frame, 35s CSV → PASS | Synthetic: 3700 frames, 35s | **PASS** — `gate_01_status=PASS` in loader_report |
| T4: Missing Frame/Time header → original `CRITICAL` ValueError | Bad CSV, no header | **PASS** — existing behavior preserved |
| T5: Full pipeline run of dead session halts at NB01 | `651_T1_DEAD_TEST.csv` (5 frames) | **PASS** — NB01 fails; NB02-NB08 not run |
| T6: Fail report written to correct path | After T5 | **PASS** — `derivatives/step_01_parse/651_T1_DEAD_TEST__s01_fail_report.json` |
| T7: `gate_01_status: FAIL` in fail report | After T5 | **PASS** |
| T8: `fail_reason: frame_count_too_short` in fail report | After T5 | **PASS** |
| T9: `n_frames: 5` in fail report | After T5 | **PASS** |
| T10: `threshold_frames: 3600` and `threshold_duration_sec: 30.0` | After T5 | **PASS** |
| T11: No kinematics parquet produced for FAIL session | After T5 | **PASS** — `step_06_kinematics/651_T1_DEAD_TEST__kinematics_master.parquet` absent |
| T12: No step_01 parquet for FAIL session | After T5 | **PASS** — `step_01_parse/651_T1_DEAD_TEST__parsed_run.parquet` absent |
| T13: Valid session (651_T1_P2_R1) runs end-to-end, no regression | Real session | **PASS** — Success: 1/1 |
| T14: Content-based regression — 14 golden sessions | All 14 sessions | **PASS** — ALL 14 MATCH |

**Note on label mismatch:** The current `parse_optitrack_csv()` already handles label mismatches by populating `segments_missing_list` without raising — this behavior is unchanged. Tested implicitly through T3/T13 which use sessions with known marker sets.

---

## Regression Comparison

**Baseline content hashes (14 sessions — from Ticket 001 log):** See Ticket 001 implementation log.
**After content-based hashes:** All 14 sessions match Ticket 001 baseline exactly — shapes and rounded numeric values identical.

---

## Issues Encountered

1. **Regex false-match in `_write_s01_fail_report()`:** First attempt used `re.search(r"n_frames=([^:]+)", error_str)` on the full papermill traceback. The traceback includes the f-string SOURCE code (`n_frames={T}`) alongside the actual error message (`n_frames=5`). The regex matched `{T}` first, causing `int('{T}')` to raise. **Fixed** by extracting the `ValueError: S01_GATE_FAIL:...` line specifically before applying field regex.

2. **NB06 does not call `run_pipeline()`:** Confirmed during pre-implementation inspection. NB06 implements kinematics inline. `src/pipeline.py::run_pipeline()` is a legacy path only. The fail report for the notebook pipeline path is correctly handled by `run_pipeline.py::_write_s01_fail_report()`.

---

## Post-Implementation Sign-Off

- [x] All 14 tests pass (T1–T14)
- [x] Content-based regression passes — 14/14 sessions unchanged
- [x] Implementation log complete
