# S-01 Parse — Stage Audit

**Date:** 2026-05-14
**Auditor:** Per-Stage Audit Agent (Phase 4 batch)
**Sources read:**
- `src/preprocessing.py` (full — parse section)
- `notebooks/01_Load_Inspect.ipynb` (key cell grep)
- `derivatives/step_01_parse/671_T1_P1_R1_Take 2026-01-06 03.57.12 PM_001__step01_loader_report.json` (representative)
- All 9 `__step01_loader_report.json` implied by grep
**Status:** COMPLETE

---

## 1. What Step 01 does

`notebooks/01_Load_Inspect.ipynb` calls `preprocessing.py::parse_optitrack_csv()` to:
1. Read an OptiTrack Motive CSV, skip header rows, extract calibration metadata from the header block.
2. Rename raw segment labels via `correct_motive_name()` mapping (lines 31–77).
3. Compute `sampling_rate_actual` from median inter-frame Δt.
4. Write `__parsed_run.parquet` and `__step01_loader_report.json`.

The output parquet contains: timestamp column `Time (Seconds)`, position columns `{Segment}_{x/y/z}`, quaternion columns `{Segment}_q{x/y/z/w}`.

---

## 2. Q-EXT3b — Metadata provenance fields

**Question:** Does config snapshot log `Capture Frame Rate`, `Export Frame Rate`, `Rotation Type`, `Length Units`?

**Answer: FAIL — 4 OptiTrack provenance fields are absent from all reports.**

Step 01 loader report fields (actual, from T1_P1_R1 sample):

| Field logged | Value |
|---|---|
| `total_frames` | 30604 |
| `missing_data_percent` | "0.00%" |
| `sampling_rate_actual` | 120.0048 Hz |
| `optitrack_version` | "unknown" |
| `pointer_tip_rms_error_mm` | null |
| `wand_error_mm` | null |
| `export_date` | null |
| `segments_found_count` | 51 |
| `duration_sec` | 255.025 |

**Missing (not extracted anywhere):**
- `Capture Frame Rate` — the nominal camera rate configured in Motive
- `Export Frame Rate` — the rate at which frames were exported (may differ from capture)
- `Rotation Type` — OptiTrack's rotation convention (typically `XYZ Euler` or `Quaternion`)
- `Length Units` — `mm` vs `m` (critical for position scaling)

**Root cause:** `preprocessing.py::parse_optitrack_csv()` only extracts:
```python
"pointer_tip_rms_error_mm", "wand_error_mm", "optitrack_version", "export_date"
```
The OptiTrack CSV header contains lines like:
```
Capture Frame Rate,120
Export Frame Rate,120
Rotation Type,Quaternion
Length Units,m
```
These are not parsed. The `optitrack_version` field returns `"unknown"` on all 9 sessions (extraction silently fails).

**Risk:** Without `Length Units`, the pipeline cannot programmatically verify that positions are in metres (not mm). Currently assumed to be metres everywhere, with a manual note in the Gravity Guard (`"median_pelvis > 50.0 suggests mm, not m"`). Without `Export Frame Rate`, there is no machine-verifiable proof that the 120 Hz rate used in Steps 3–6 matches what Motive actually exported.

---

## 3. Q-EXT3c — Frame number continuity check

**Question:** Does Step 1 check frame number continuity? Is `frame_number_continuity_status` logged?

**Answer: FAIL — No frame number continuity check exists.**

The `__step01_loader_report.json` contains **no** `frame_number_continuity_status` field. Grep of `notebooks/01_Load_Inspect.ipynb` for `frame_number`, `frame_continuity`, `Frame Rate` found zero matches.

OptiTrack CSVs include a `Frame` column with monotonic integer frame numbers. If the MoCap software dropped frames, this column will have gaps (e.g., 1001, 1002, 1004 — missing 1003). The pipeline does not:
- Read the `Frame` column
- Check for monotonicity or gaps
- Log any continuity status

Existing `total_frames` is a row count, not a continuity check. A recording with 1000 rows could have 10 dropped frames with no detection.

**Risk level: Low for current sessions** (all 9 show `missing_data_percent=0.00%` which means no NaN in the data columns, but this is a *value* check, not a *frame index* check). Medium for future sessions at high-speed capture where CPU load may cause Motive to drop frames.

---

## 4. Additional findings

### F1: `optitrack_version` silently defaults to "unknown"
All 9 sessions report `"optitrack_version": "unknown"`. The extraction code in `preprocessing.py` seeks a specific header line and returns "unknown" if not found. The CSV headers from this dataset appear to use a slightly different format than expected, so extraction always fails. This makes version-controlled analysis (e.g., "was the quaternion convention changed in Motive 2.x vs 3.x?") impossible.

### F2: Calibration fields uniformly null
`pointer_tip_rms_error_mm`, `wand_error_mm`, `export_date` are all null for all 9 sessions. The extraction logic is present but not matching. Calibration quality cannot be assessed from the logs.

### F3: Label mapping `correct_motive_name()` not logged
The segment renaming map (lines 31–77 in preprocessing.py) translates OptiTrack output names to canonical pipeline names. No audit trail of which names were renamed is preserved in the loader report. If a future Motive version changes naming, silent mapping failures would not be detectable from the report alone.

### F4: `sampling_rate_actual` drift across sessions
- T1/T2 sessions: 120.0048 Hz (consistent)
- This 0.004% offset (0.048 mHz) is negligible for the pipeline but is not flagged anywhere

---

## 5. Summary table

| Check | Status | Severity |
|---|---|---|
| Q-EXT3b: Capture/Export Frame Rate extracted | FAIL | Medium |
| Q-EXT3b: Rotation Type extracted | FAIL | Low |
| Q-EXT3b: Length Units extracted | FAIL | Medium |
| Q-EXT3c: Frame number continuity check | FAIL | Low |
| optitrack_version extraction | FAIL (always "unknown") | Low |
| Calibration metadata extraction | FAIL (always null) | Low |
| Segment rename audit trail | ABSENT | Low |

---

## 6. Decisions triggered

| Issue | Recommended action | Priority |
|---|---|---|
| Missing Capture/Export Frame Rate | Add parsing of `Capture Frame Rate` and `Export Frame Rate` lines from CSV header; log to loader report | Medium |
| Missing Length Units | Add parsing of `Length Units`; add assertion `length_units == "m"` (or auto-scale if mm) | Medium |
| Missing frame continuity check | Add `Frame` column monotonicity check; log `frame_number_continuity_status` | Low |
| optitrack_version always "unknown" | Fix regex to match actual header format; log to loader report | Low |
