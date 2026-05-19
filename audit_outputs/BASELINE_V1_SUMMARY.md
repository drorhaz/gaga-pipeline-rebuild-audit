# GAGA Pipeline — Baseline V1 Dev Set Summary

**Date locked:** 2026-05-19
**Phase:** Phase 13 — Minimal v1 implementation, Tier 2 Checkpoint
**Session:** Phase 13 implementation run, Tickets 001–011 complete
**Locked by:** Phase 13 implementation agent (Sonnet 4.6, Opus routing for complex tickets)

---

## Purpose

This document serves as the authoritative quick-reference sheet for the Minimal v1 baseline state of the `kinematics_master.parquet` files for the 4-session Dev Set. Any future V2 feature development, algorithm upgrade, or regression check MUST compare against the hashes and schema described here.

---

## Dev Set Definition (4 Representative Sessions)

| Label | Subject | Timepoint | Piece | Rep | CSV |
|-------|---------|----------|-------|-----|-----|
| 651_T1_P1_R1 | 651 | T1 | P1 | R1 | `data/651/T1/651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002.csv` |
| 651_T2_P1_R1 | 651 | T2 | P1 | R1 | `data/651/T2/651_T2_P1_R1_Take 2026-01-26 05.24.12 PM.csv` |
| 671_T1_P2_R1 | 671 | T1 | P2 | R1 | `data/671/T1/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002.csv` |
| 671_T3_P2_R1 | 671 | T3 | P2 | R1 | `data/671/T3/671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001.csv` |

**Coverage:** 2 subjects × 3 timepoints × 2 pieces = diverse sample across recording conditions and joint availability.

---

## Locked Numeric Content Hashes (post Ticket 011)

These hashes cover all **numeric (float/int) columns** in `kinematics_master.parquet`. Boolean columns (`__is_artifact`, `__is_hampel_outlier`) are excluded from the hash by design — they do not carry kinematic signal and may update in future tickets. The hash function: SHA256 over column values rounded to 9 decimal places, sorted by column name.

| Session | Parquet shape | Numeric content hash (SHA256 prefix, 16 chars) |
|---------|--------------|-----------------------------------------------|
| `651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002` | **(30423, 777)** | **`4e4b81bc9edd2f6b`** |
| `651_T2_P1_R1_Take 2026-01-26 05.24.12 PM` | **(32110, 787)** | **`b7db8a72f4c11a85`** |
| `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002` | **(16915, 807)** | **`5d13f307c9bc50a3`** |
| `671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001` | **(21773, 807)** | **`96ae62165289dc2a`** |

> **Note on varying column counts:** 777/787/807 columns are all correct. The variation (documented in MUB_NB06_lin_kine_nan_gate_2026-05-18.md) reflects the S04-introduced NaN gate in NB06 that silently drops `lin_rel_*` columns for joints with NaN in their position axes. This is a known pre-existing condition, not a regression.

---

## Schema at Baseline (per session)

### Column families present in all Dev Set sessions

| Family | Column pattern | Count per session | dtype |
|--------|---------------|-------------------|-------|
| Identity | `run_id`, `frame_idx`, `time_s`, `qc_frame_valid` | 4 | various |
| Session labels (T004) | `subject_id`, `timepoint`, `piece`, `rep` | 4 | object (str) |
| Quaternions | `{joint}__q{x,y,z,w}`, `{joint}__raw_rel_q*`, `{joint}__zeroed_rel_q*` | 152 | float64 |
| Rotation vectors | `{joint}__zeroed_rel_rotvec_*`, `{joint}__zeroed_rel_rotmag` | 76 | float64 |
| Angular kinematics | `{joint}__zeroed_rel_omega_*`, `{joint}__zeroed_rel_alpha_*`, `{joint}__zeroed_rel_omega_mag`, `{joint}__zeroed_rel_alpha_mag` | 152 | float64 |
| Linear kinematics (variable) | `{seg}__lin_rel_p*`, `{seg}__lin_vel_rel_*`, `{seg}__lin_acc_rel_*`, magnitudes | **179/189/209** | float64 |
| Euler angles | `{joint}__euler_{x,y,z}` | 57 | float64 |
| Artifact flags | `{joint}__is_artifact` | 19–38 | bool |
| Hampel flags (T011) | `{joint}__is_hampel_outlier` | 19 | bool |
| WBCoM | `wbc_com_x`, `wbc_com_y`, `wbc_com_z`, `com_reliability_score` | 4 | float64 |
| Other | SavGol, path length, etc. | varies | float64 |

### PyArrow metadata fields present (T007a)

| Field | Value example |
|-------|--------------|
| `ref_is_fallback` | `"false"` |
| `filter_psd_verdict` | `"REVIEW_OVERSMOOTHING"` |
| `pipeline_version` | `"v4.0"` |
| `gate_01_status` | `"PASS"` |
| `bone_qc_status` | `"GOLD"` or `"SILVER"` |

---

## Sidecars Present Per Session at Baseline

| Stage | Sidecar file | Ticket that created it |
|-------|-------------|------------------------|
| S00 | `{RUN_ID}__config_snapshot.yaml` | 001 |
| S01 | `{RUN_ID}__step01_loader_report.json` | NB01 (pre-existing) |
| S02 | `{RUN_ID}__interpolation_log.json` (labels corrected) | 009 |
| S02 | `{RUN_ID}__preprocess_summary.json` (labels corrected) | 009 |
| S02 | `{RUN_ID}__s02_interpolation_stats.json` (9 fields) | 009 |
| S02 | `{RUN_ID}__kinematics_map.json` | NB02 (pre-existing) |
| S03 | `{RUN_ID}__resample_summary.json` (incl. n_frames_input/output/delta) | 003 |
| S04 | `{RUN_ID}__filtering_summary.json` (incl. Hampel fractions from 007b) | 007b |
| S04 | `{RUN_ID}__s04_hampel_or_mask.npy` | 011 |
| S05 | `{RUN_ID}__reference_metadata.json` | NB05 (pre-existing) |
| S06 | `{RUN_ID}__kinematics_master.parquet` | NB06 |
| S06 | `{RUN_ID}__validation_report.json` (incl. quaternion_diagnostics, lin_kine_diagnostics from 007b) | 007b |

---

## Known Scientific Anomalies at Baseline (Deferred to Post-Minimal-v1)

| ID | Finding | Tickets that documented it | Deferred until |
|----|---------|--------------------------|----------------|
| MUB-NB06 | S04 filtering introduces NaN in select position axis columns (boundary effects). NB06 silently drops `lin_rel_*` columns for affected joints, causing variable column counts (777–807). | 007b (initial), 009 (root cause), addendum in MUB | Post-Minimal-v1 |
| `filter_psd_verdict = REVIEW_OVERSMOOTHING` | All 4 Dev Set sessions are over-smoothing the dance frequency band. Ticket 015 (S04 PSD correction loop) will address this. | 007a (confirmed via metadata) | Ticket 015 |
| `is_hampel_outlier` OR mask vs per-joint mask | Option B (single OR boolean) chosen for Minimal v1. Per-joint resolution is available in `filtering_summary.json` (Ticket 007b). Option A/C upgrade deferred. | 011 | Post-Minimal-v1 |

---

## Regression Check Script (Reproducible)

To verify any future parquet against this baseline:

```python
import hashlib, numpy as np, pandas as pd

def verify_baseline(path, expected_hash_prefix):
    df = pd.read_parquet(path)
    num_cols = df.select_dtypes(include='number').columns.tolist()
    h = hashlib.sha256()
    for col in sorted(num_cols):
        vals = df[col].values
        rounded = np.round(vals[~np.isnan(vals)], 9)
        h.update(col.encode())
        h.update(rounded.tobytes())
    actual = h.hexdigest()
    return actual.startswith(expected_hash_prefix), actual

BASELINE = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002__kinematics_master.parquet': '4e4b81bc9edd2f6b',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM__kinematics_master.parquet':     'b7db8a72f4c11a85',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__kinematics_master.parquet': '5d13f307c9bc50a3',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001__kinematics_master.parquet': '96ae62165289dc2a',
}
```

---

## Tickets Implemented to Reach This Baseline

| Ticket | Title | Blast Radius | Key outcome |
|--------|-------|-------------|-------------|
| 001 | Config snapshot | LOCAL | Every run now has a frozen YAML config before mutation |
| 002 | S01 hard FAIL gate | LOCAL | Dead/short sessions halt at NB01 |
| 003 | S03 1-frame resampling fix | PARQUET_REGEN | 12/14 sessions gained +1 frame; `resample_time_grid()` now endpoint-inclusive |
| 004 | Session labels + ref_is_fallback | PARQUET_REGEN | 4 label columns + metadata field in every parquet |
| 005 | ref_quality_score / t_pose_failed guards | LOCAL | JSON null instead of NaN literal |
| 006 | hard_exclude in v2_feature_engine | LOCAL | Dead sessions excluded from PCA |
| 007a | 5 PyArrow metadata fields | PARQUET_REGEN (metadata) | filter_psd_verdict, gate_01_status, bone_qc_status, pipeline_version, ref_is_fallback |
| 007b | Quaternion diagnostics + Hampel + NaN gate logging | LOCAL | quaternion_diagnostics + lin_kine_diagnostics in validation_report.json; Hampel fractions in filtering_summary.json |
| 008 | Artifact fraction OR-union + ref threshold 0.20 | LOCAL | atf fraction = 1-clean_fraction_pca; critical gate tightened |
| 009 | S02 label correction + 9 artifact/gap stats | LOCAL | Correct labels; new s02_interpolation_stats.json sidecar |
| 010 | Hips excluded from ATF_axial | LOCAL (feature engine) | +0.0–1.28% uplift in atf_axial; root-joint bias removed |
| 011 | is_hampel_outlier propagation (Option B OR) | PARQUET_REGEN (bool) | is_hampel_outlier column now reflects actual S04 Hampel activity |

---

*Baseline V1 locked. All future work builds on this foundation.*
