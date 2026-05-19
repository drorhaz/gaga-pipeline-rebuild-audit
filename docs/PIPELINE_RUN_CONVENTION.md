# Pipeline run convention: same run, same file, unified naming

## 1. Single run = single file

For each pipeline run (one CSV), **every notebook (01 → 08) must process the same run**. The run is identified by:

- **RUN_ID** = the CSV filename without extension (e.g. `671_T1_P1_R1_Take 2026-01-06 03.57.12 PM_001`).
- When the pipeline is started via `run_pipeline.py`, it injects `RUN_ID` and `current_csv` into each notebook via papermill parameters so all steps use the same run.

## 2. How notebooks get RUN_ID

- **When run from pipeline (batch):** The runner injects `RUN_ID` and `current_csv` into a **parameters** cell (tag `parameters`). The notebook must use these when non-empty.
- **When run interactively or without parameters:** The notebook falls back to `RUN_ID = Path(CONFIG['current_csv']).stem` (and `current_csv` from CONFIG).

Every pipeline notebook (01, 02, 03, 04, 05, 06, 08) should have at the top:

```python
# Parameters (injected by run_pipeline.py when running in batch)
RUN_ID = ""
current_csv = ""
```

Then in the first cell that needs RUN_ID:

```python
if not RUN_ID and CONFIG.get('current_csv'):
    RUN_ID = Path(CONFIG['current_csv']).stem
if not current_csv and CONFIG.get('current_csv'):
    current_csv = CONFIG['current_csv']
# Fail fast if still no run context
if not RUN_ID:
    raise ValueError("RUN_ID is required. Set CONFIG['current_csv'] or run via run_pipeline.py.")
```

(Notebook 01 may derive RUN_ID from `current_csv` path when not provided.)

## 3. Parquet and artifact naming convention (unified)

All step outputs use this pattern so every script can find the right file for the current run:

| Step | Directory | Reads (same RUN_ID) | Writes (same RUN_ID) |
|------|-----------|---------------------|----------------------|
| 01 | `step_01_parse/` | — | `{RUN_ID}__parsed_run.parquet`, `{RUN_ID}__step01_loader_report.json` |
| 02 | `step_02_preprocess/` | `{RUN_ID}__parsed_run.parquet` | `{RUN_ID}__preprocessed.parquet`, `{RUN_ID}__kinematics_map.json` |
| 03 | `step_03_resample/` | `{RUN_ID}__preprocessed.parquet` | `{RUN_ID}__resampled.parquet`, `{RUN_ID}__kinematics_map.json` |
| 04 | `step_04_filtering/` | `{RUN_ID}__resampled.parquet` | **`{RUN_ID}__filtered.parquet`** (required for 06), `{RUN_ID}__*.json` |
| 05 | `step_05_reference/` | `{RUN_ID}__filtered.parquet` | `{RUN_ID}__reference_map.json`, `{RUN_ID}__offsets_map.json`, etc. |
| 06 | `step_06_kinematics/` | `{RUN_ID}__filtered.parquet`, `{RUN_ID}__reference_map.json` | `{RUN_ID}__kinematics_master.parquet`, `{RUN_ID}__validation_report.json` |
| 08 | (audit) | Discovers runs from step_01 + step_06 | Uses same `{run_id}__*` naming to build profiles |

- **Convention:** `{RUN_ID}__{artifact_name}.parquet` or `{RUN_ID}__{artifact_name}.json`.
- RUN_ID is the exact CSV stem (e.g. `671_T1_P1_R1_Take 2026-01-06 03.57.12 PM_001`); filenames may contain spaces.
- Step N reads from step N-1 using the same RUN_ID; step N writes to its folder using the same RUN_ID.

## 4. Step 04 → 06 handoff

- **Step 04** must write `derivatives/step_04_filtering/{RUN_ID}__filtered.parquet`.
- **Step 06** reads exactly that path. If the file is missing, 06 raises `FileNotFoundError`.
- Step 04 should verify the parquet exists immediately after writing (see notebook 04).

## 5. Which notebooks are in the pipeline

- `run_pipeline.py` runs, in order: **01, 02, 03, 04, 05, 06, 08** (07 is master report, run after batch).
- For step 04, if both `04_filtering.ipynb` and `04_filtering_output.ipynb` exist, the runner **prefers** `04_filtering_output.ipynb` so the notebook that writes the parquet is used consistently.
