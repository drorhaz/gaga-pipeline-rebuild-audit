# Phase 6 — Master Parquet ML/DL Readiness Audit

**Date:** 2026-05-14
**Auditor:** ML/DL Readiness Audit Agent (Phase 6)
**Canonical session:** `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002`
**File audited:** `derivatives/step_06_kinematics/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__kinematics_master.parquet`
**Mode:** Read-only. No code changes.

**Status:** COMPLETE

---

## 1. Shape and Structure

| Property | Value |
|---------|-------|
| Rows | 16,914 frames |
| Columns | 803 |
| In-memory size | 104.2 MB |
| On-disk (parquet) size | 126.3 MB |
| Compression ratio | **0.8× (file is larger than uncompressed in-memory)** |

**Index:** 0-based `RangeIndex` (int64, contiguous [0, 16913]). Not time-indexed.
The `time_s` column carries the actual timestamp (see §3.2).

---

## 2. Column Schema

### 2.1 Feature inventory

The schema is: **5 global scalar columns + 42 per-joint feature types × 19 joints = 803 columns**.

| Feature group | Feature types | Per joint | Total cols |
|--------------|--------------|----------|----------|
| Angular velocity | `raw_rel_omega_{x,y,z}`, `zeroed_rel_omega_{x,y,z}`, `zeroed_rel_omega_mag` | 7 | 133 |
| Angular acceleration | `raw_rel_alpha_{x,y,z}`, `zeroed_rel_alpha_{x,y,z}`, `zeroed_rel_alpha_mag` | 7 | 133 |
| Quaternions | `raw_rel_{qx,qy,qz,qw}`, `zeroed_rel_{qx,qy,qz,qw}` | 8 | 152 |
| Rotation vector | `zeroed_rel_rotvec_{x,y,z}`, `zeroed_rel_rotmag` | 4 | 76 |
| Linear position | `lin_rel_{px,py,pz}` | 3 | 57 |
| Linear velocity | `lin_vel_rel_{x,y,z}`, `lin_vel_rel_mag` | 4 | 76 |
| Linear acceleration | `lin_acc_rel_{x,y,z}`, `lin_acc_rel_mag` | 4 | 76 |
| Euler angles | `euler_{x,y,z}` (ISB convention) | 3 | 57 |
| Quality flags | `is_artifact`, `is_hampel_outlier` | 2 (bool) | 38 |
| **Scalar globals** | `time_s`, `wbc_com_{x,y,z}`, `com_reliability_score` | — | 5 |
| **TOTAL** | | | **803** |

Column naming convention: `{JointName}__{feature_type}` — clean and parseable with `.split('__', 1)`.

### 2.2 Schema asymmetry: raw vs zeroed features

The parquet is asymmetric between raw-relative and zeroed-relative representations:

| Feature | Raw-relative | Zeroed-relative |
|---------|-------------|----------------|
| omega_{x,y,z} | ✓ 57 cols | ✓ 57 cols |
| **omega_mag** | **ABSENT** | ✓ 19 cols |
| alpha_{x,y,z} | ✓ 57 cols | ✓ 57 cols |
| **alpha_mag** | **ABSENT** | ✓ 19 cols |
| q{x,y,z,w} | ✓ 76 cols | ✓ 76 cols |
| **rotvec_{x,y,z}** | **ABSENT** | ✓ 57 cols |
| **rotmag** | **ABSENT** | ✓ 19 cols |

`raw_rel_omega_mag`, `raw_rel_alpha_mag`, `raw_rel_rotvec_{x,y,z}`, and `raw_rel_rotmag` are
absent. Only the zeroed (reference-subtracted) representations have magnitude and rotation-vector
columns. ML models requiring raw angular velocity magnitude must compute it from raw_rel_omega_xyz
at load time.

### 2.3 Root joint constant-zero columns

`Hips` is the skeleton root. All hip-relative linear features are identically zero:
- `Hips__lin_rel_{px,py,pz}` = 0.000 (all 16,914 frames)
- `Hips__lin_vel_rel_{x,y,z,mag}` = 0.000 (all frames)
- `Hips__lin_acc_rel_{x,y,z,mag}` = 0.000 (all frames)

This totals **10 constant-zero columns** out of 803. They carry no information for ML.
They should be excluded from feature sets or documented in the pipeline schema.

---

## 3. Data Types and Value Ranges

### 3.1 dtype inventory

| dtype | Count | Columns |
|-------|-------|---------|
| `float64` | 765 | All numeric features |
| `bool` | 38 | `is_artifact`, `is_hampel_outlier` per joint |

No object, categorical, or int64 data columns. The schema is clean with no dtype fragmentation.

**Float64 vs float32:** All 765 numeric columns are float64 (8 bytes each). For ML/DL,
float32 (4 bytes) is typically sufficient for biomechanical data. Casting to float32 would
reduce in-memory footprint from 104 MB to ~52 MB per session. No downcast has been applied.

### 3.2 Key value ranges

| Column | Min | Max | Mean | Std | Units |
|--------|-----|-----|------|-----|-------|
| `time_s` | 0.0 | 140.94 | 70.47 | 40.69 | seconds |
| `Hips__zeroed_rel_omega_mag` | 0.22 | 374.44 | 93.93 | 56.23 | deg/s |
| `Hips__zeroed_rel_alpha_mag` | 0.44 | 2054.84 | 472.41 | 323.13 | deg/s² |
| `Hips__euler_x` | −26.29 | 29.64 | −0.99 | 8.28 | degrees |
| `Hips__euler_y` | −20.26 | 32.35 | 2.69 | 7.31 | degrees |
| `Hips__euler_z` | −179.38 | 179.35 | −1.96 | 45.98 | degrees |
| `Hips__raw_rel_qw` | −0.23 | 1.00 | 0.92 | 0.14 | dimensionless |
| `LeftHand__lin_rel_px` | −774.30 | 770.25 | — | — | mm (relative to Hips) |
| `wbc_com_x` | −135.70 | 162.47 | −0.93 | 53.00 | mm |
| `wbc_com_y` | −11.78 | 99.56 | 47.01 | 13.01 | mm |
| `wbc_com_z` | −120.33 | 172.90 | 46.72 | 45.54 | mm |

**Position units: millimetres.** LeftHand range ≈ ±770 mm (~77 cm reach radius from Hips).
WBCoM range ≈ 300 mm lateral and 110 mm vertical — consistent with dance.

**Data is NOT normalized.** Euler angles in degrees, omega in deg/s, positions in mm.
No z-score or min-max normalization applied. Raw physical units throughout.

### 3.3 Time uniformity

`time_s` is perfectly uniform: `dt_mean = 0.008333s = 1/120 Hz`, `std = 0.000000s`.
Suitable for FFT, time-series windowing, and convolution-based ML without resampling.

---

## 4. NaN Density

**Zero NaN frames** across all 803 columns for this session.

Parquet metadata: `nan_pct_before_guard: 0.0000`, `nan_guard_status: CLEAN`.

**Structural gap (inherited from Phase 5):** The pipeline has no mechanism to track NaN
propagation through stages. A session with marker dropouts would produce NaN ω/α values in
the parquet without any column-level NaN count logged. ML code must include `df.isnull().any()`
checks before training — particularly for 651-style sessions that may have dropouts.

---

## 5. Parquet Metadata

### 5.1 Fields present

| Field | Value | Assessment |
|-------|-------|-----------|
| `run_id` | `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002` | ✓ |
| `subject_id` | `671` | ✓ |
| `subject_height_cm` | `179.0` | ✓ measured |
| `subject_mass_kg` | `72.0` | ✓ measured |
| `subject_height_source` | `measured` | ✓ |
| `pipeline_version` | `v3.0_com_enhanced` | ⚠ see §5.3 |
| `processing_timestamp` | `2026-05-14 19:11:56` | ✓ |
| `com_segments_available` | `16` | ✓ (16/19 with mass fractions) |
| `com_mass_coverage_pct` | `100.0` | ✓ |
| `com_reliability_flag` | `RELIABLE` | ✓ |
| `nan_guard_status` | `CLEAN` | ✓ |
| `metadata_quality` | `SUBJECT_SPECIFIC` | ✓ (not default anthropometrics) |
| `euler_standard` | `ISB` | ✓ |
| `derivative_method` | `savgol_chunked_adaptive` | ✓ |
| `sg_window_len_global` | `21` | ✓ |
| `sg_polyorder` | `3` | ✓ |

### 5.2 Metadata fields absent — ML/DL gaps

| Missing field | Why it matters |
|--------------|---------------|
| `filter_psd_verdict` | ALL 57 position columns are REVIEW_OVERSMOOTHING. A model trained without this flag learns over-smoothed dynamics as ground truth (F-INT3). |
| `ref_is_fallback` | 2 sessions in 651 used fallback reference. Systematic angle offset not annotated (F-651-4). |
| `bone_qc_status` | T2 SILVER sessions have higher segment CV; CoM reliability may be lower. |
| `timepoint` | No T1/T2/T3 label in data rows — critical for longitudinal ML. |
| `piece` | No P1/P2 label in data rows. |
| `rep` | No R1/R2 label in data rows. |
| `gate_02_status` | Pipeline QC pass/fail not recorded in output artifact. |

**Session-level labels (timepoint, piece, rep, subject_id) exist only in the parquet file-level
metadata and in the filename.** For multi-session ML training — loading N sessions into a single
DataFrame — these must be added as explicit data columns per row, or they are lost in concat.

### 5.3 Pipeline version inconsistency (F-INT5 confirmed)

| Stage artifact | Version string |
|---------------|---------------|
| S01 loader report | `v2.6_calibration_enhanced` |
| S04 filtering summary | `v3.1_3stage_dynamic_rms_chunked` |
| S06 kinematics parquet metadata | `v3.0_com_enhanced` |
| S06 validation report | (no version field) |

**Four stage artifacts, three different version strings, no unified version.** Regression
testing and reproducibility require inferring code version from git history.

---

## 6. Quality Flag Columns

### 6.1 `is_artifact` (True = position spike-repaired by Stage 1 in S04)

| Joint | True frames | % |
|-------|------------|---|
| Hips | 241 | 1.425% |
| LeftForeArm | 316 | 1.868% |
| LeftHand | 761 | 4.499% |
| RightForeArm | 4 | 0.024% |
| RightHand | 536 | 3.169% |
| LeftLeg | 8 | 0.047% |
| LeftFoot | 37 | 0.219% |
| RightFoot | 106 | 0.627% |
| (11 other joints) | 0 | 0.000% |
| **Grand total** | **2,009 frame-joint pairs** | — |

Artifact flags concentrate at distal joints (hands, feet) as expected. **Hips having 241 artifact
frames (1.4%) is notable** — root joint artifact propagates to all relative kinematics downstream.

`is_artifact` is the only per-frame quality signal in the parquet and is useful for ML
masking strategies.

### 6.2 `is_hampel_outlier` — propagation failure

`is_hampel_outlier = False` for ALL 19 joints across ALL 16,914 frames.

This conflicts with S04 `__filtering_summary.json`:
- `total_hampel_outliers: 1163` (frame-column pairs across 57 position columns)
- `hampel_frames_pct: 0.1206%`

**Finding:** The Hampel outlier flag from S04 was NOT propagated to S06. The Stage 2 Hampel
filter modifies positions and counts outliers, but the per-joint `is_hampel_outlier` column
in the kinematics parquet is 0 for all joints. Provenance of 1163 Hampel-corrected positions
is lost at the kinematics output stage.

---

## 7. Storage Efficiency

The parquet file is **126.3 MB on disk vs 104.2 MB in-memory** (0.8× compression ratio).
The parquet is LARGER on disk than uncompressed in-memory. This indicates no effective
compression is being applied (likely Snappy encoding on dense float64 data, which can inflate
rather than compress).

At this size, **50 sessions would be ~6.3 GB on disk**. For a thesis dataset targeting N≥50
sessions, this is manageable but suboptimal. Switching to:
- float32 (instead of float64): ~3.1 GB
- zstd level 3 (instead of Snappy): ~1–2 GB estimated for float data with this structure

---

## 8. ML/DL Readiness Summary

### 8.1 What works well

| Property | Assessment |
|---------|-----------|
| NaN density | Zero (this pristine session) |
| Time uniformity | Perfect 120Hz, std=0 |
| dtype consistency | All float64/bool, no fragmentation |
| Column naming | `{Joint}__{feature}` — clean, parseable |
| Units | mm, deg/s, degrees — consistent, documented |
| Euler standard | ISB — documented in metadata |
| CoM | Full coverage, RELIABLE, 100% mass |
| `is_artifact` flag | Present, correct, useful for masking |
| Subject metadata | Height, mass, quality level in parquet metadata |
| No scaling applied | Raw units preserved (model can apply its own normalisation) |

### 8.2 Gaps requiring action before ML/DL use

| Gap | Severity | Impact |
|-----|---------|--------|
| `filter_psd_verdict` absent from metadata | **High** | Model trained on over-smoothed positions without knowing it |
| `ref_is_fallback` absent from metadata | **High** | Systematic angle offset for fallback sessions undetected |
| Session labels (timepoint/piece/rep) absent from data rows | **High** | Multi-session DataFrame concat loses session identity |
| `is_hampel_outlier` = 0 despite S04 activity | Medium | 1163 corrected position frames have no provenance in output |
| Parquet compression 0.8× (inflated) | Medium | Storage cost 2–3× higher than achievable |
| All float64 — float32 would suffice | Low | 2× memory overhead |
| 10 constant-zero columns (root linear) | Low | Wasted dimensions |
| Euler ±180° discontinuity (Hips__euler_z) | Medium | Spurious gradients near gimbal lock for models using Euler targets |
| Raw omega/alpha magnitude absent | Low | Must recompute from xyz at load time |
| No unified pipeline_version | Medium | Reproducibility unclear |

### 8.3 Euler angle discontinuity — ML warning

`Hips__euler_z` spans −179.38° to +179.35°. YZX Euler angles have a discontinuity at ±180°.
Near-boundary transitions produce apparent 358° jumps in one frame — spurious large-gradient
events for regression or sequence models.

**Recommendation:** Use `zeroed_rel_rotvec_{x,y,z}` (rotation vectors) or
`zeroed_rel_{qx,qy,qz,qw}` (quaternions) as ML training targets. Retain Euler angles for
human-interpretable reporting only.

---

## 9. Summary Table

| Check | Status | Severity |
|-------|--------|----------|
| Column schema completeness | PASS — all expected features present | — |
| NaN density | PASS — 0 NaN (pristine session) | — |
| dtype consistency | PASS — float64/bool throughout | — |
| Float32 downcast applied | ABSENT — all float64 | Low |
| Time-based index | ABSENT — RangeIndex; use time_s column | Low |
| Parquet compression | **FAIL** — 0.8× ratio (larger than uncompressed) | Medium |
| Metadata: core fields | PASS — run_id, subject, height, mass, CoM, euler_standard | — |
| Metadata: QC fields | **ABSENT** — no filter_psd, ref_fallback, bone_qc | High |
| Session label columns in rows | **ABSENT** — timepoint/piece/rep not in data | High |
| Pipeline version consistency | **INCONSISTENT** — 3 strings across 4 artifacts | Medium |
| `is_artifact` propagation | PASS — correctly populated | — |
| `is_hampel_outlier` propagation | **FAIL** — 0 for all joints despite S04 activity | Medium |
| Euler angle continuity | **WARNING** — gimbal lock near ±180° | Medium |
| Root joint zero columns | PRESENT — 10 constant-zero cols documented | Low |
| Raw vs zeroed schema symmetry | **ASYMMETRIC** — magnitude/rotvec zeroed-only | Low |
| F-INT3 (REVIEW_OVERSMOOTHING not in parquet) | **CONFIRMED ABSENT** | High |
| F-651-4 (ref_fallback not in parquet) | **CONFIRMED ABSENT** | High |
| Normalization state | Raw physical units (appropriate — model applies own) | — |

---

## 10. Decisions Triggered

| Finding | Recommended action | Priority |
|---------|-------------------|----------|
| filter_psd_verdict absent | Add `filter_psd_verdict` and `mean_dance_delta_dB` to parquet file metadata in S06 | High |
| ref_is_fallback absent | Add `ref_is_fallback` and `ref_confidence_level` to parquet file metadata in S06 | High |
| Session labels absent from rows | Add `subject_id`, `timepoint`, `piece`, `rep` as DATA COLUMNS (one value per row) in S06 output | High |
| is_hampel_outlier = 0 | Fix S06 notebook to propagate Hampel flags from S04 filtered parquet per joint | Medium |
| Parquet compression 0.8× | Switch from Snappy to zstd level 3 in `pq.write_table()` call | Medium |
| float64 throughout | Add `parquet_dtype: float32` config toggle in S06 notebook | Low |
| 10 zero-constant columns | Add schema note; consider `exclude_root_linear` flag in ML export utility | Low |
| Euler ±180° discontinuity | Add documentation warning; default ML-export should include rotvec/quat; Euler is secondary | Low |
| Raw omega_mag absent | Add `{joint}__raw_rel_omega_mag` columns (L2 norm of raw_rel_omega_xyz) per joint | Low |
| bone_qc_status absent | Add to parquet file metadata in S06 | Low |
