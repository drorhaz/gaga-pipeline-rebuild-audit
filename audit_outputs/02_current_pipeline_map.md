# 02 Current Pipeline Map

**Phase:** 2
**Date:** 2026-05-14
**Agent:** Claude Sonnet 4.6 — Audit Mode
**Mode:** Read-only (legacy archive action completed per Phase 1 decisions)
**Reference session used for tracing:** Subject 671, T3, P2, R1 (`671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001`)

---

## 1. Pipeline overview

The pipeline transforms raw OptiTrack CSV files into `kinematics_master.parquet` (Steps 01–06, 08) and then into v2 feature scalars for downstream thesis analysis (Notebook 11).

### Stage summary table

| Stage | Notebook | Input | Output directory | Output files |
|-------|----------|-------|-----------------|--------------|
| 01 Parse | `01_Load_Inspect.ipynb` | Raw OptiTrack CSV | `step_01_parse/` | `{RUN_ID}__parsed_run.parquet` |
| 02 Preprocess | `02_preprocess.ipynb` | `step_01_parse/` parquet | `step_02_preprocess/` | `__preprocessed.parquet`, `__kinematics_map.json` |
| 03 Resample | `03_resample.ipynb` | `step_02_preprocess/` parquet | `step_03_resample/` | `__resampled.parquet`, forwarded `__kinematics_map.json` |
| 04 Filter | `04_filtering.ipynb` | `step_03_resample/` parquet | `step_04_filtering/` | `__filtered.parquet`, `__filtering_summary.json`, `__winter_residual_data.json`, `__filter_psd_validation.png` |
| 05 Reference | `05_reference_detection.ipynb` | `step_04_filtering/` parquet | `step_05_reference/` | `__offsets_map.json`, `__reference_map.json`, `__reference_euler.json`, `__reference_summary.csv`, `__reference_metadata.json`, `qc_plots/__stability_audit.png` |
| 06 Kinematics | `06_ultimate_kinematics.ipynb` | `step_04_filtering/` + `step_05_reference/` | `step_06_kinematics/` | `__kinematics_master.parquet`, `__validation_report.json`, `__outlier_validation.json`, interactive HTML dashboard |
| 08 Audit | `08_engineering_physical_audit.ipynb` | `step_06_kinematics/` (all runs) | `reports/` | `Engineering_Audit_{timestamp}.xlsx` |

**Automated sequence** (via `run_pipeline.py`): `['01', '02', '03', '04', '05', '06', '08']`

**Notebook orchestrator:** `run_pipeline.py` uses `papermill.execute_notebook()`, injecting `RUN_ID` and `current_csv` as parameters per notebook. Steps 07, 09, 10, 11 are **not in the automated sequence.**

---

## 2. Stage-by-stage code trace

### Stage 01 — Parse (NB01: `01_Load_Inspect.ipynb`)

**Governing spec:** `docs/PIPELINE_PROCESSING_README.md` §3
**Implementation:** `src/preprocessing.py` → `parse_optitrack_csv()`

**What it does:**
1. Reads raw OptiTrack CSV (exported from Motive). File has two header rows (device header + column header).
2. Calls `correct_motive_name()` to map OptiTrack column names → canonical JOINT_NAMING_CONVENTION names (e.g., `Chest` → `Spine1`).
3. Extracts per-joint position columns (`_x`, `_y`, `_z` in mm) and quaternion columns (`_qx`, `_qy`, `_qz`, `_qw`) in scipy xyzw convention.
4. Adds `frame_idx` (integer) and `time_s` (float seconds) columns.
5. Validates: 51 joints expected; 0 missing confirmed on reference run.
6. Saves `{RUN_ID}__parsed_run.parquet` to `step_01_parse/`.

**Observed output (reference run 671_T3_P2_R1):**
- Frames: 21,773 at 120.0 Hz → 181.4 s
- Joints found: 51/51 (PASS)
- Shape: (21773, 369) [51 joints × 7 cols + frame_idx + time_s]

**Task/phase filter:** None. Parses any CSV unconditionally.

---

### Stage 02 — Preprocess (NB02: `02_preprocess.ipynb`)

**Governing spec:** `docs/PIPELINE_PROCESSING_README.md` §4
**Implementation:** `src/gapfill_positions.py`, `src/gapfill_quaternions.py`

**What it does:**
1. Loads `step_01_parse/` parquet.
2. **Joint exclusion:** Drops 32 finger/toe joints (`CONFIG['exclude_fingers']=True`). Retains 19 working joints.
3. **Temporal validation (Gate 1):** Checks time monotonicity. Confirmed: `dt_std = 0.0005 ms` (jitter is sub-sample, PASS).
4. **Gap filling:**
   - Positions: PCHIP interpolation if gap ≤ `CONFIG['max_gap_ms'] = 100 ms`. Outlier threshold: `MAD × 6.0`.
   - Quaternions: Linear + SLERP for short gaps.
5. **Bone length QC:** Skurowski (2021) thresholds — CV% warn=2%, fail=5%.
   - Hips→Spine: CV=10.22% → **FAIL**
   - Neck→Head: CV=8.43% → **FAIL**
   - ⚠️ **Display unit bug:** The QC cell does `mean_l * 1000` assuming positions are in meters, but positions are already in mm. This produces nonsensical `Mean_mm` display values (~31,502 mm ≈ 31 m for Hips→Spine). The CV% values are computed from the raw data and remain valid for FAIL/PASS determination. The FAIL verdicts are genuine bone-length instability (likely short-segment tracking noise), not artifacts of the display bug.
6. **Gate 2 (temporal quality):** Checks jitter after gap-fill. PASS.
7. Saves `__preprocessed.parquet` (19 joints) and `__kinematics_map.json` to `step_02_preprocess/`.

**Observed output shape:** (21773, 135) [19 joints × 7 cols + frame_idx + time_s]

**Task/phase filter:** None.

---

### Stage 03 — Resample (NB03: `03_resample.ipynb`)

**Governing spec:** `docs/PIPELINE_PROCESSING_README.md` §5
**Implementation:** `src/resampling.py`

**What it does:**
1. Loads `step_02_preprocess/` parquet.
2. Builds uniform 120 Hz time grid covering the original time span.
3. Positions: CubicSpline interpolation per coordinate.
4. Quaternions: `scipy.spatial.transform.Slerp` per joint.
5. Validates: `time_grid_std = 0.0` → PERFECT uniformity.
6. Saves `__resampled.parquet` (identical schema) and forwards `__kinematics_map.json`.

**Observed output:**
- Frames: 21,773 → 21,772 (uniform grid loses 1 frame at trailing boundary — expected)
- Shape: (21772, 135)

**Task/phase filter:** None.

---

### Stage 04 — Filtering (NB04: `04_filtering.ipynb`)

**Governing spec:** `docs/PIPELINE_PROCESSING_README.md` §6
**Implementation:** `src/filtering.py`
**Config params:** `filtering.method = 3_stage`, `winter_fmin = 1.0 Hz`, `winter_fmax = 20.0 Hz`, `per_joint_winter = True`

**What it does:**

*Pre-filter SNR audit:* Welch PSD per joint. Reference run: mean SNR = 52.7 dB, all 19 joints classified EXCELLENT (>30 dB threshold). Confirms clean raw signal.

**Stage 1 — Velocity/Z-score artifact detector:**
- Flags frames where velocity exceeds `velocity_limit = 5000.0 mm/s` OR Z-score exceeds `zscore_threshold = 5.0`.
- Reference run: 1,447 artifact frames flagged (0.12% of total). Linear interpolation over flagged spans.

**Stage 2 — Hampel sliding window:**
- Window = 5 frames, threshold = 3.0σ.
- Reference run: 1,142 outliers removed (0.09%).

**Stage 3 — Adaptive per-joint Winter filter:**
- Butterworth zero-phase `filtfilt` (forward–backward, no phase distortion).
- Cutoff frequency computed per joint by optimizing knee of Welch spectrum between `winter_fmin=1.0` and `winter_fmax=20.0 Hz`.
- Reference run: cutoffs ranged 6.0–12.0 Hz (mean 8.6 Hz).

**Quaternion median filter:** 5-frame sliding window to remove hemisphere flips.

**PSD validation (post-filter):**
- Dance band (1–13 Hz): preservation target ≥80%.
- Noise band (20–50 Hz): attenuation target ≥95%.
- **⚠️ CRITICAL FINDING — REVIEW_OVERSMOOTHING:**
  - Dance band delta = **-5.40 dB** (threshold: must be > -3 dB).
  - **57/57 position and velocity columns flagged.**
  - Verdict: `REVIEW_OVERSMOOTHING`.
  - Interpretation: The adaptive Winter filter is removing 5.4 dB of content in the 1–13 Hz dance-relevant frequency band. This exceeds the spec-defined acceptable loss of 3 dB. This is the most significant signal-quality risk identified in this audit.

**Outputs:**
- `__filtered.parquet` — shape (21772, 135), same schema.
- `__filtering_summary.json` — per-joint cutoffs, stage counts, PSD verdict.
- `__winter_residual_data.json` — residual signal data for QC.
- `__filter_psd_validation.png` — before/after spectral comparison.

**Task/phase filter:** None.

---

### Stage 05 — Reference Detection (NB05: `05_reference_detection.ipynb`)

**Governing spec:** `docs/PIPELINE_PROCESSING_README.md` §7
**Implementation:** `src/reference.py`

**What it does:**
1. Loads `step_04_filtering/` filtered parquet.
2. Searches first `CONFIG['ref_search_sec'] = 8.0 s` for static T-pose window.
3. Finds minimum-variance 1.5-second segment (joint position variance minimized).
4. **Height estimation from skeleton geometry:** Computes skeletal height from joint chain (heel → ankle → knee → hip → spine → neck → head). Cross-validates against `CONFIG['subject_height_cm']` from registry. PASS/FAIL based on deviation threshold (~1–5%).
5. **Per-joint quaternion offset computation:** For each of the 19 joints, computes the quaternion rotation needed to align observed T-pose orientation to canonical neutral pose. Writes `__offsets_map.json`.
6. **Reference map:** Stores refined reference rotations (post-offset-corrected) in `__reference_map.json`.
7. **Euler angle extraction (ISB-compliant):** Converts reference rotations to Euler angles per ISB Wu et al. (2005) joint conventions. Writes `__reference_euler.json`.
8. **Stability audit visualization:** `qc_plots/__stability_audit.png` shows variance over time with selected T-pose segment highlighted.

**Validation gates:**
- Height cross-validation: PASS/FAIL (registry vs mocap estimate).
- Post-offset residual: < 5° per joint for PASS.

**Outputs:**
```
step_05_reference/
├── {RUN_ID}__offsets_map.json
├── {RUN_ID}__reference_map.json
├── {RUN_ID}__reference_euler.json
├── {RUN_ID}__reference_summary.csv
├── {RUN_ID}__reference_metadata.json
└── qc_plots/{RUN_ID}__stability_audit.png
```

**Task/phase filter:** None. Works on individual `{RUN_ID}` without P1/P2 discrimination.

---

### Stage 06 — Kinematics (NB06: `06_ultimate_kinematics.ipynb`)

**Governing spec:** `docs/KINEMATIC_FEATURES_README.md` (schema, categories A–F)
**Implementation:** `src/angular_velocity.py`, `src/com_engine.py`

**Inputs:**
- `step_04_filtering/{RUN_ID}__filtered.parquet` (position + quaternion timeseries)
- `step_05_reference/{RUN_ID}__reference_map.json` (T-pose reference rotations)
- `step_02_preprocess/{RUN_ID}__kinematics_map.json` (joint metadata, carried forward)

**What it does:**

**Track A — Quaternion channels (raw + T-pose normalized):**
- `{joint}__raw_rel_qx/y/z/w`: original joint quaternions.
- `{joint}__zeroed_rel_qx/y/z/w`: T-pose offset–corrected (canonical neutral).

**Track B — Angular kinematics per joint (19 joints):**
- Angular velocity (`omega_x/y/z`, `omega_mag` in rad/s) via quaternion logarithm derivative.
- Angular acceleration (`alpha_x/y/z` in rad/s²).
- ISB-compliant Euler angles (`euler_x/y/z` in degrees) — dynamic rotation orders per joint class per Wu et al. (2005).
- Rotation vector magnitude (`rotvec_mag` in radians).

**Track C — Linear kinematics per joint:**
- Linear velocity (`vel_x/y/z`, `vel_mag` in mm/s) via Savitzky-Golay derivative of positions.
- Linear acceleration (`acc_x/y/z`, `acc_mag` in mm/s²).

**Track D — Whole-body CoM:**
- de Leva (1996) segment mass fractions applied to 19 working segments.
- CoM position (`com_x/y/z` in mm), velocity, acceleration.

**Track E — Engineering metrics:**
- Cumulative path length per segment (mm).
- Intensity index (path length / duration).
- Bilateral symmetry indices (left vs right paired segments).
- Burst analysis (movement clustering by threshold crossing).

**Validation gates:**
- `[NaN Guard] PASS`: zero NaN cells in output parquet.
- `[Continuity] PASS`: no hemisphere flips in quaternion channels.
- Geodesic distance stability proof at T-pose reference window.
- Outlier detection per joint (writes `__outlier_validation.json`).

**Outputs:**
```
step_06_kinematics/
├── {RUN_ID}__kinematics_master.parquet   ← primary output
├── {RUN_ID}__validation_report.json
├── {RUN_ID}__outlier_validation.json
└── {RUN_ID}__dashboard.html              ← interactive Plotly
```

**Confirmed P2 sessions in `step_06_kinematics/` (subject 671):**

| Session | Parquet present |
|---------|----------------|
| 671_T1_P2_R1 | ✓ |
| 671_T1_P2_R2 | ✓ |
| 671_T2_P2_R1 | ✓ |
| 671_T2_P2_R2 | ✓ |
| 671_T3_P2_R1 | ✓ |
| 671_T3_P2_R2 | ✓ |

All 6 P2 sessions for subject 671 are fully processed through Step 06.

**Task/phase filter:** None in NB06 itself. P2 selection happens upstream via batch config at `run_pipeline.py` invocation.

---

### Stage 08 — Engineering Physical Audit (NB08: `08_engineering_physical_audit.ipynb`)

**Not in automated sequence.** Run manually for documentation and reporting.

**What it does:**
1. Scans `derivatives/` for all completed runs (requires both `step_01_parse/` and `step_06_kinematics/` outputs present).
2. Loads each `kinematics_master.parquet`.
3. Produces multi-sheet Excel workbook documenting:
   - Height/mass validation (registry vs mocap estimate) — PASS/FAIL per session.
   - Mathematical methodology passport (algorithms, parameters, citations).
   - Data lineage: raw filename, processing steps, modifications.
   - Skeleton hierarchy verification.
   - Per-joint SNR profiles before/after filtering.
   - Bone QC verdict.
4. **Task/phase filter:** Processes all runs (P1, P2, P3) without filtering. Displays session labels with phase suffix in report rows.

**Output:** `reports/Engineering_Audit_{timestamp}.xlsx`

---

## 3. Downstream analysis notebooks (outside automated sequence)

### NB10: `10_EDA_PCA.ipynb` — 3-branch exploratory PCA

**Status: BROKEN since Phase 2 legacy archive action.**
- Imports `from EDA_PCA import ...` pointing to `src/EDA_PCA.py`.
- `src/EDA_PCA.py` has been moved to `legacy/EDA_PCA.py` per Phase 1 user decision.
- NB10 will fail with `ModuleNotFoundError: No module named 'EDA_PCA'` unless the import is updated.
- Uses the legacy 3-branch PCA approach (dynamics + pose + reach). Governed by the superseded `Thesis_Analytical_Pipeline.md` (v1.4), not `METHODOLOGY_SPEC_v2.md` (v3.0).
- Role: exploratory visualization only (Plotly HTML dashboards). Not used for thesis feature extraction.

### NB09: `09_Subject_Exploration_Dashboard.ipynb` — Legacy diagnostic

**Status: BROKEN since Phase 2 legacy archive action.**
- Imports from `core_kinematics_engine` (moved to `legacy/`).
- Will fail to import unless `sys.path` includes `legacy/`.
- Not in automated sequence.

### NB11: `11_METH_SPEC_v2_Features.ipynb` — v2 Feature Extraction

**Status: Current. Governing spec: `docs/METHODOLOGY_SPEC_v2.md` (v3.0).**
**Not in automated sequence.** Run manually after all sessions are processed.

**What it does:**
1. Scans `step_06_kinematics/` for available `kinematics_master.parquet` files.
2. **Explicit P2 filter:** `if phase == "P2"` — selects only P2 (free improvisation) runs across all timepoints (T1, T2, T3).
3. **Reference anchor selection:** User manually designates one T1 session as the PCA anchor (default: `{subject}_T1_P2_R1`). This is the source of truth for anchor selection per user Phase 1 decision.
4. Extracts 4 features per session:
   - **F1 ATF** (Anatomically Transformed Frequency): whole-body movement frequency envelope.
   - **F2 TM** (Total Movement): cumulative path length across 19 segments (mm).
   - **F4 D_eff** (Effective Dimensionality): PCA-based complexity metric. PCA fitted on T1 anchor only; all sessions projected into T1 basis. `N90` metric (cumulative variance ≥ 90%).
   - **F5 Joint Gini**: Gini coefficient on per-joint PCA variance fractions (inequality of joint contribution).
5. Validates each session before feature computation (`validate_reference()` — checks ATF and path length quality gates).
6. Writes `results/meth_v2/feature_scalars.csv` (one row per session, 43 columns) and `run_metadata.json`.

**P2 flow confirmation:** ✓ Explicit code filter `if phase == "P2"`. All T1/T2/T3 timepoints included; only P2 protocol.

---

## 4. Full data lineage (CSV → feature scalars)

```
data/{subject}/{T-session}/{RUN_ID}.csv
    │
    ▼  NB01: parse_optitrack_csv()
derivatives/step_01_parse/{RUN_ID}__parsed_run.parquet
    │  51 joints, mm + xyzw quat, 21773 frames @ 120 Hz
    │
    ▼  NB02: gap-fill (PCHIP+SLERP), exclude 32 fingers/toes
derivatives/step_02_preprocess/{RUN_ID}__preprocessed.parquet
    │  19 joints, (21773, 135)
    │  + __kinematics_map.json
    │
    ▼  NB03: CubicSpline (positions) + Slerp (quat) → 120 Hz uniform grid
derivatives/step_03_resample/{RUN_ID}__resampled.parquet
    │  19 joints, (21772, 135) [1 trailing frame dropped]
    │
    ▼  NB04: 3-stage filter (artifact+Hampel+adaptive Winter) + quat median
derivatives/step_04_filtering/{RUN_ID}__filtered.parquet
    │  19 joints, (21772, 135)
    │  ⚠️ PSD verdict: REVIEW_OVERSMOOTHING (-5.40 dB dance band delta)
    │
    ▼  NB05: T-pose detection, height estimate, quaternion offset calibration
derivatives/step_05_reference/{RUN_ID}__offsets_map.json
                              {RUN_ID}__reference_map.json
                              {RUN_ID}__reference_metadata.json
    │
    ▼  NB06: angular velocity, Euler angles, CoM, engineering metrics
derivatives/step_06_kinematics/{RUN_ID}__kinematics_master.parquet
    │  Categories A–F per KINEMATIC_FEATURES_README
    │  ✓ NaN Guard PASS, ✓ Continuity PASS
    │
    ▼  NB08: cross-run engineering audit (all runs, P1+P2+P3 mixed)
reports/Engineering_Audit_{timestamp}.xlsx
    │
    ▼  NB11: v2 feature extraction (P2-only filter; T1-anchored PCA)
results/meth_v2/feature_scalars.csv
```

---

## 5. P2-only constraint: verification

**Question:** Is the "P2-only" analysis constraint correctly implemented?

**Finding:** The constraint operates at two independent levels:

| Level | Mechanism | Status |
|-------|-----------|--------|
| Batch input selection | `batch_configs/subject_671_p2_all.json` selects only P2 CSV files | ✓ Correct |
| NB11 explicit filter | `if phase == "P2"` code filter before feature extraction | ✓ Correct |
| NB06 and earlier steps | No P1/P2 filter — process any RUN_ID unconditionally | ✓ Correct (by design: Steps 01–06 are protocol-agnostic) |

**Conclusion:** The P2 constraint is correctly implemented. Steps 01–06 and 08 are protocol-agnostic by design. P2 selection happens at the batch configuration level (which CSVs are fed to `run_pipeline.py`) and at NB11 (which reads all available parquets but filters to P2 explicitly). Both P1 and P2 sessions exist in `step_06_kinematics/` for subject 671, consistent with the Phase 1 decision that "both P1 and P2 must produce `kinematics_master.parquet` files."

---

## 6. Pipeline risks and findings

| ID | Stage | Finding | Severity |
|----|-------|---------|----------|
| R-04a | NB04 | **PSD REVIEW_OVERSMOOTHING.** Dance band delta = -5.40 dB. Threshold: must be > -3 dB. 57/57 columns flagged. The adaptive Winter filter removes meaningful energy in the 1–13 Hz dance-relevant band, exceeding the spec-defined acceptable loss. | **Critical** |
| R-02a | NB02 | **Bone QC: 2 joints FAIL.** Hips→Spine CV=10.22%, Neck→Head CV=8.43% (fail threshold: CV>5%). Genuine short-segment tracking instability. Pipeline does not gate on bone QC failure — processing continues regardless. | High |
| R-08a | `run_pipeline.py:140` | **Config overwrite per run.** `update_config()` overwrites `config_v1.yaml` (subject_id, height, weight, current_csv) on every run. Reproducibility risk. (Previously C8.) | High |
| R-11a | NB11 | **Manual PCA anchor selection.** No code-enforced gate ensuring the anchor session passed all QC gates before use as PCA reference. | Medium |
| R-02b | NB02 | **Bone QC display unit bug.** `mean_l * 1000` applied to positions already in mm → nonsensical `Mean_mm` display values. CV% computation unaffected. | Low |
| R-10 | NB10 | **NB10 broken** (expected). Imports `src/EDA_PCA.py` now in `legacy/`. Will fail with `ModuleNotFoundError`. Not in automated sequence — no pipeline regression. | Low |
| R-09 | NB09 | **NB09 broken** (expected). Imports `src/core_kinematics_engine.py` now in `legacy/`. Will fail to import. Not in automated sequence. | Low |

---

## 7. Config parameters confirmed from reference run

| Parameter | Value | Consuming stage |
|-----------|-------|----------------|
| `fs_target` | 120.0 Hz | NB03 |
| `exclude_fingers` | True | NB02 |
| `gap_fill.max_gap_ms` | 100 ms | NB02 |
| `gap_fill.mad_threshold` | 6.0 | NB02 |
| `ref_search_sec` | 8.0 s | NB05 |
| `filtering.method` | `3_stage` | NB04 |
| `filtering.velocity_limit` | 5000.0 mm/s | NB04 Stage 1 |
| `filtering.zscore_threshold` | 5.0 | NB04 Stage 1 |
| `filtering.hampel_window` | 5 frames | NB04 Stage 2 |
| `filtering.hampel_n_sigma` | 3.0 | NB04 Stage 2 |
| `filtering.winter_fmin` | 1.0 Hz | NB04 Stage 3 |
| `filtering.winter_fmax` | 20.0 Hz | NB04 Stage 3 |
| `filtering.per_joint_winter` | True | NB04 Stage 3 |
| `filtering.apply_quaternion_median_filter` | True | NB04 |
| `filtering.quaternion_window_size` | 5 frames | NB04 |

---

## 8. Corrections to Phase 1 conflict register

| Conflict ID | Original finding | Correction |
|-------------|-----------------|------------|
| C6 | "All current derivatives are P1 sessions" | **Incorrect.** `step_06_kinematics/` contains both P1 and P2 sessions for subject 671. All 6 P2 sessions (T1/T2/T3 × R1/R2) are fully processed through kinematics. P2 `kinematics_master.parquet` files exist and are available for NB11. |

---

*End of Phase 2 — Current Pipeline Map*
