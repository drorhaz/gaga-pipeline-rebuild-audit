# GAGA Pipeline — Baseline V1 Dev Set Summary

**Date locked:** 2026-05-19 (Dev Set quick-reference); full production 14-session lock is in **Full 14-Session V1 Baseline Lock** below.
**Phase:** Phase 13 — Minimal v1 implementation, Tier 2 Checkpoint
**Session:** Phase 13 implementation run, Tickets 001–011 complete
**Locked by:** Phase 13 implementation agent (Sonnet 4.6, Opus routing for complex tickets)

---

## Purpose

This document serves as the authoritative quick-reference for Minimal v1 `kinematics_master.parquet` baselines: the **4-session Dev Set** (early Tier 2 checkpoint) and the **full 14-session production lock** (see **Full 14-Session V1 Baseline Lock**). Any V2 feature work or regression check should compare against the appropriate hash table below.

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

## Full 14-Session V1 Baseline Lock (post Ticket 015 + Emergency Valve)

**Date locked:** 2026-05-19  
**Batch list:** `_ticket_003_regen_list.txt`  
**Filter loop:** `correction_step_hz=0.25`, `max_correction_iterations=20` (see `config/config_v1.yaml`).

### Derivative leakage audit (distal linear acceleration magnitudes)

Rule: **PASS (Organic)** if max < 15,000 mm/s² **and** spike ratio (max/std) ≥ 4.0 (or std≈0 with max<15000).  
Otherwise **HIGH RISK (Noise Leakage)**.

| Session ID (truncated) | Filter iters (max 20) | Distal max (mm/s²) | Joint | Spike ratio | Leakage verdict |
|---|---:|---:|---|---:|---|
| `651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002` | 19 | 46276.48 | RightFoot | 12.5583 | HIGH RISK (Noise Leakage) |
| `651_T1_P2_R1_Take 2026-01-15 04.35.25 PM_002` | 18 | 26805.44 | LeftFoot | 9.2102 | HIGH RISK (Noise Leakage) |
| `651_T1_P2_R2_Take 2026-01-15 04.35.25 PM_005` | 18 | 30409.8 | LeftFoot | 7.8931 | HIGH RISK (Noise Leakage) |
| `651_T2_P1_R1_Take 2026-01-26 05.24.12 PM` | 19 | 63988.99 | LeftFoot | 12.4073 | HIGH RISK (Noise Leakage) |
| `651_T2_P2_R1_Take 2026-01-26 05.24.12 PM_000` | 18 | 45629.79 | LeftFoot | 12.1434 | HIGH RISK (Noise Leakage) |
| `651_T3_P1_R1_2026-02-11 05.50.42 PM_2026` | 19 | 37626.9 | LeftFoot | 11.5286 | HIGH RISK (Noise Leakage) |
| `651_T3_P2_R1_2026-02-11 05.50.42 PM_2027` | None | 17794.25 | RightFoot | 8.1980 | HIGH RISK (Noise Leakage) |
| `651_T3_P2_R2_2026-02-11 05.50.42 PM_2030` | None | 34873.51 | LeftFoot | 12.0099 | HIGH RISK (Noise Leakage) |
| `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002` | None | 49306.86 | LeftHand | 8.7408 | HIGH RISK (Noise Leakage) |
| `671_T1_P2_R2_Take 2026-01-06 03.57.12 PM_004` | None | 43812.3 | RightHand | 6.6895 | HIGH RISK (Noise Leakage) |
| `671_T2_P2_R1_Take 2026-01-15 04.35.25 PM_006` | None | 44647.72 | LeftHand | 6.7280 | HIGH RISK (Noise Leakage) |
| `671_T2_P2_R2_Take 2026-01-15 04.35.25 PM_010` | None | 44832.53 | LeftFoot | 11.2817 | HIGH RISK (Noise Leakage) |
| `671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001` | None | 57959.39 | LeftHand | 6.6601 | HIGH RISK (Noise Leakage) |
| `671_T3_P2_R2_Take 2026-02-03 08.05.01 PM_006` | None | 69413.95 | RightHand | 9.9026 | HIGH RISK (Noise Leakage) |

*Note:* `Filter iters` is read from `psd_correction_loop` in `__filtering_summary.json` when present; `None` means that sidecar predates Ticket 015 export or the loop block was absent for that run. Distal acceleration metrics still come from `kinematics_master.parquet` (same rule as `acceleration_sensitivity_index`).

### Numeric content hashes — all 14 `kinematics_master.parquet` files

Algorithm: SHA256 over every **numeric** column, sorted by name; values rounded to 9 decimals; NaNs excluded. Boolean columns excluded.

| Session | Shape (rows × cols) | Numeric content SHA256 (full) |
|---|---|---|
| `651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002` | **30423 × 777** | `a57bc13e8e8064e2d828f60c7038bb63e94694ae9872fabbdae6e98a41227b26` |
| `651_T1_P2_R1_Take 2026-01-15 04.35.25 PM_002` | **19304 × 807** | `19185471bae2846a846ba94b74d87d6bf389d51e1c9f117d2ff48d420a6511cf` |
| `651_T1_P2_R2_Take 2026-01-15 04.35.25 PM_005` | **19895 × 807** | `b6b8752fe79ab3e489664953b317157346cbbc674515bf65bf4790d68b9b1975` |
| `651_T2_P1_R1_Take 2026-01-26 05.24.12 PM` | **32110 × 787** | `80e749d60e2758d2f50931ec86498c2a183c365f00f400480efb86d071e6ce0d` |
| `651_T2_P2_R1_Take 2026-01-26 05.24.12 PM_000` | **21602 × 807** | `c840931fef77bc2416865217b4a63b2369a614ab5fe363b7e08ee06e09a92e79` |
| `651_T3_P1_R1_2026-02-11 05.50.42 PM_2026` | **30835 × 807** | `3be43590f794794982317355e0ae1854c7a081fcbc9925b90be2a371102bba5c` |
| `651_T3_P2_R1_2026-02-11 05.50.42 PM_2027` | **22487 × 807** | `131a2139ed33e189d9d6c79c58595e6e4834898942d614ddee387a26baf20aa7` |
| `651_T3_P2_R2_2026-02-11 05.50.42 PM_2030` | **22961 × 807** | `ba88f4045134e8845452b6044c18c4bf642b1c3443dd2389b66a766e7e9cc8fb` |
| `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002` | **16915 × 807** | `5d13f307c9bc50a345f1f4620bc342ecb4fa40bad65b4fca2ef835e939463ca8` |
| `671_T1_P2_R2_Take 2026-01-06 03.57.12 PM_004` | **17686 × 807** | `345df38e3e8411a1fe87177957a8d751416333c72e5a9db3b76de0dc00d1edd9` |
| `671_T2_P2_R1_Take 2026-01-15 04.35.25 PM_006` | **20047 × 807** | `eeba923f38dac083c7450f9739ce52faaaa85a79025b3b7158d3a817c4552350` |
| `671_T2_P2_R2_Take 2026-01-15 04.35.25 PM_010` | **20765 × 807** | `57d5838134a986b32695e7b8384bfeb38386bf13d62d239fa49f7ffb3e86a2f7` |
| `671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001` | **21773 × 807** | `96ae62165289dc2ab1509808cec5bd9235ba1f48f0056332815d5ce6c21bf320` |
| `671_T3_P2_R2_Take 2026-02-03 08.05.01 PM_006` | **22215 × 807** | `687f01621ed20d5844210bc7aa344eee019109fc872ed31af12cca1620c2784d` |

### QC aggregation

Re-run after batch: `python run_qc_aggregator.py`  
`feature_reliability_table.csv` includes `filter_ceiling_saturated_*` columns from S04 sidecars.  
`FILTER_CEILING_SATURATED_HIGH_RISK_DERIVATIVES` appears in `feature_family_reliability.csv` when any body region hits its ceiling.

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
| 015 + pre-batch | PSD MEAN criterion, raised ceilings, emergency valve (0.25 Hz / 20 iters), ASI telemetry, QC ceiling flags | PARQUET_REGEN | Full 14-session batch; `scripts/v1_baseline_lock.py` locks hashes + leakage table |

---

*Baseline V1 locked (4-session Dev Set + full 14-session production). All future work builds on this foundation.*
