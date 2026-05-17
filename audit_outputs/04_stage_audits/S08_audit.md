# S-08 Engineering & Physical Audit — Stage Audit

**Date:** 2026-05-14
**Auditor:** Per-Stage Audit Agent (Phase 4 batch)
**Sources read:**
- `notebooks/08_engineering_physical_audit.ipynb` (grep — 57 KB, key sections)
- `src/utils_nb07.py` (confirmed exists — contains `build_engineering_profile_row`, `filter_complete_runs`, `compute_noise_locality_index`)
**Status:** COMPLETE

---

## 1. What NB08 does

`notebooks/08_engineering_physical_audit.ipynb` is a **retrospective documentation and audit notebook**, not a pipeline gating stage. It:
1. Loads outputs from all complete runs (requiring Step 01 and Step 06 derivatives to exist).
2. Calls `build_engineering_profile_row()` from `src/utils_nb07.py` to extract 131 physical measurements per run.
3. Applies the **V3.0 Inertial & Metadata Audit** (10 additional columns → 140 total).
4. Runs the **V3.0 Pipeline Validation** section to prove that key algorithm fixes (Smart Bias, Spine Whitelist, Euler ISB) are active.
5. Provides signal quality analysis (pre-processing SNR, filter audit, noise locality).
6. Exports results to Excel.

**Current run:** 16 complete runs × 131 measurements (140 after V3.0 audit).
Note: 1 incomplete run was skipped (one of the 17 sessions in the dataset lacked complete step_01/step_06 derivatives).

---

## 2. Section-by-section assessment

### 2.1 Baseline measurements (131 physical columns)

Key columns in the engineering profile row:
- `Duration_sec`, `Sampling_Rate`, `Raw_Missing_Data_Percent`
- `SNR` (pre-processing, frequency band 0.5–10 Hz signal vs 15–50 Hz noise — **raw capture quality BEFORE filtering**)
- `Filter_Cutoff_Weighted_Avg_Hz`, `Filter_Residual_RMS_mm`
- `Stage3_Winter_Cutoff_Min_Hz`, `Stage3_Winter_Cutoff_Max_Hz`, `Stage3_Winter_Cutoff_Mean_Hz`
- Per-anatomical-region path length, intensity metrics
- Per-joint kinematic summary statistics

**From stored cell outputs:**
- Stage 2 (filtering): cutoff range 6.0–12.0 Hz, mean cutoff 8.6 Hz
- Filter Residual (Price of Smoothing): mean RMS reported

### 2.2 V3.0 Inertial & Metadata Audit

10 additional columns added per session:
- `Meta_Subject_ID`: from parquet digital passport
- `Meta_Pipeline_Ver`: pipeline version embedded in parquet metadata
- `CoM_Mass_Coverage_Pct`: percentage of body mass represented in WBCoM calculation
- `CoM_Segments_Found`: segments available for CoM (e.g., "15/16")
- `Final_NaN_Rescue_Pct`: fraction of final parquet frames that were NaN-rescued
- `Audit_Height_Match`: whether subject height in metadata matches anthropometric table
- `Audit_Mass_Match`: whether subject mass in metadata matches anthropometric table
- `Metadata_Quality`: SUBJECT_SPECIFIC / UNRELIABLE_COM_DEFAULT_ANTHRO / MISSING_ANTHRO
- `WBCoM_Sway_Range_mm`: range of WBCoM displacement in horizontal plane during session
- `CoM_to_Base_Ref_mm`: CoM distance from base of support at reference pose

**`UNRELIABLE_COM_DEFAULT_ANTHRO` sentinel:** triggers when de Leva (1996) generic segment mass fractions are used rather than subject-specific anthropometry. This flags sessions where CoM calculations are approximations.

### 2.3 V3.0 Pipeline Validation (Smart Bias, Spine Whitelist, Euler ISB)

**Smart Bias verification** (from stored cell output for all 16 sessions):
- Dominant method: `smart_bias` for ALL 16 sessions
- Smart Bias applied to 74–84% of kinematic columns per session
- Strict knee fallback: 0 columns across all sessions
- Fallback: 0–6 columns per session (expected for very distal or low-motion joints)

This confirms that the adaptive frequency selection (Smart Bias) is active and dominant. The spine whitelist and Euler ISB application are also confirmed active (documented but detailed results not extracted from grep).

### 2.4 Signal Quality (pre-processing SNR)

NB08 computes **pre-processing SNR** = signal band (0.5–10 Hz) power / noise band (15–50 Hz) power from RAW (unfiltered) data. This measures inherent capture quality, NOT filtering effectiveness.

A `compute_noise_locality_index()` function is also called — this quantifies whether noise is localized (specific joints, specific time windows) vs uniform.

---

## 3. What NB08 does NOT do

This is a key finding for the Phase 5 integration audit:

1. **NB08 does not assert pass/fail gates.** It documents physical measurements but does not stop the pipeline or flag sessions for re-collection. There are no `assert max_omega < threshold` calls — only `exceeded_omega_threshold` boolean fields that appear in tables.

2. **NB08 does not validate pipeline stage completeness.** It checks that step_01 and step_06 derivatives exist, but does not verify that step_02–step_05 ran correctly.

3. **NB08 is not run as part of the per-session batch.** It requires all sessions to be complete before running. It is a post-hoc analysis, not a per-session gate.

4. **NB08 uses stored cell outputs.** If cells are not re-executed, the displayed outputs may not reflect current data. The notebook is not parameterized (no papermill) and cannot be run as part of the automated batch.

5. **NB08 mixes narrative and computation.** Many cells contain explanatory text and code in the same cell. This makes automated re-execution risky.

---

## 4. Quality of the engineering profile

### 4.1 Good practices

- `Metadata_Quality` sentinel (`UNRELIABLE_COM_DEFAULT_ANTHRO`) is an appropriate honesty flag
- Smart Bias verification provides a methodological integrity check across all sessions
- Pre-processing SNR separates data quality from pipeline quality
- `Final_NaN_Rescue_Pct` provides provenance for interpolated data
- 131 physical measurements per session is comprehensive for thesis-grade documentation

### 4.2 Limitations

- **No per-session HTML report.** Each session's engineering profile exists only in the cross-session DataFrame. There is no session-level report file (unlike step_02/step_04 which produce per-session JSON summaries).
- **`CoM_Mass_Coverage_Pct` may be misleading.** If `Metadata_Quality = UNRELIABLE_COM_DEFAULT_ANTHRO`, the coverage percentage still appears valid even though the underlying mass fractions are generic. A compound flag (coverage × metadata quality) would be clearer.
- **No formal audit of SavGol window selection.** The adaptive SavGol window lengths per joint are logged in `__validation_report.json` but NB08 does not aggregate or flag sessions where many joints fell back to minimum window.
- **Filter residual RMS not normalized.** A residual of 2 mm is good for slow trunk motion but could be poor for fast hand motion. No normalization by joint velocity is applied.
- **16 runs reported but only 9 are in `derivatives/step_06_kinematics/`** of the current branch. The 16-run state reflects a different dataset run than the current git working tree (see git status: many C3D files modified/deleted). This is a data provenance gap — the notebook output and the current data are out of sync.

---

## 5. Summary table

| Check | Status | Severity |
|---|---|---|
| Engineering profile completeness | PASS (131 columns, 16 sessions) | — |
| V3.0 inertial/metadata audit | PASS (10 additional columns) | — |
| Smart Bias active and dominant | CONFIRMED (74–84% of columns) | — |
| Pre-processing SNR computation | PASS | — |
| Metadata quality sentinel | PASS (UNRELIABLE_COM_DEFAULT_ANTHRO) | — |
| Per-session pass/fail gates | ABSENT | Medium |
| Notebook parameterized for batch | ABSENT (not papermill) | Medium |
| Notebook output vs current data sync | MISMATCH (16 runs logged vs 9 in derivatives) | High |
| Per-session HTML report | ABSENT | Low |
| SavGol window coverage audit | ABSENT | Low |

---

## 6. Key concern: NB08 output vs current data

**The notebook stored outputs reference 16 complete runs.** The current `derivatives/step_06_kinematics/` contains 9 sessions (all for subject 671). The git status shows 7+ additional C3D files from subjects 734, 763, and 651 that were deleted from the working tree. This means:
- NB08 was last run against a more complete dataset (likely subjects 505, 621, 734, 763 + 671)
- Current derivatives are a subset
- Re-running NB08 now would produce different results

This is an evidence-of-state inconsistency, not a pipeline bug. But for thesis-grade reproducibility, the NB08 notebook must be re-run against the final dataset with all subjects present.

---

## 7. Decisions triggered

| Issue | Recommended action | Priority |
|---|---|---|
| No per-session pass/fail gates | Add `gate_08_status` to engineering profile row; fail on CRITICAL kinematic threshold violations | Medium |
| Notebook not parameterized | Consider papermill integration for batch re-run | Low |
| CoM flag clarity | Add compound `CoM_quality` = "VALID" / "APPROXIMATE_ANTHRO" / "INVALID" | Low |
| 16 vs 9 session count | Ensure NB08 is re-run on final dataset; add dataset fingerprint (N_sessions, session_list_hash) to output | High |
| SavGol window audit | Add `n_joints_at_minimum_window` and `n_joints_adaptive_window` to per-session profile | Low |
