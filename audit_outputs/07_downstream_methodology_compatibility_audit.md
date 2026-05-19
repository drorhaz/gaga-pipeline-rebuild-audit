# Phase 7 — Downstream Methodology Compatibility Audit

**Date:** 2026-05-14
**Auditor:** Phase 7 Agent (Claude Sonnet 4.6)
**Mode:** Read-only. No code changes.

**Status:** COMPLETE

---

## Scope

This audit answers one question: **can METHODOLOGY_SPEC_v2.md (v3.0) features F1 ATF, F2 TM, F4 D_eff, F5 Joint Gini be correctly computed from the current `kinematics_master.parquet` schema using `src/v2_feature_engine.py`?**

Documents examined:
- `docs/METHODOLOGY_SPEC_v2.md` (v3.0, primary authority for Layer C)
- `src/v2_feature_engine.py` (current implementation)
- `src/pulsicity.py` (`compute_noise_floor` — imported by v2 engine)
- `docs/KINEMATIC_FEATURES_README.md` (parquet schema contract)
- Phase 6 audit findings (`06_master_parquet_ml_readiness_audit.md`)
- Phase 5.5 findings (dead session + fallback reference)

Canonical parquet inspected: `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002__kinematics_master.parquet`
Available parquets: 15 sessions (6 × 651, 9 × 671) in `derivatives/step_06_kinematics/`.

---

## 1. Column Compatibility Matrix

### F1 — Active Time Fraction (ATF)

| Required column | Present in parquet | Notes |
|----------------|-------------------|-------|
| `{Joint}__lin_vel_rel_mag` × 19 | ✓ All 19 present | Phase 6 confirmed |
| `{Joint}__is_artifact` × 19 | ✓ All 19 present | Phase 6 confirmed |
| `{Joint}__lin_rel_px/py/pz` × 19 | ✓ All present | Used by `compute_noise_floor` for static window detection |

**Overall: PASS on column presence** — with one critical structural caveat (§2 below).

### F2 — Total Movement (TM)

| Required column | Present | Notes |
|----------------|---------|-------|
| `LeftHand__lin_rel_px/py/pz` | ✓ | Range ±770 mm confirmed |
| `RightHand__lin_rel_px/py/pz` | ✓ | Present |
| `LeftFoot__lin_rel_px/py/pz` | ✓ | Present |
| `RightFoot__lin_rel_px/py/pz` | ✓ | Present |
| `{Endpoint}__is_artifact` × 4 | ✓ | All 4 endpoint flags present |

**Overall: PASS on column presence.** TM computation is structurally sound.

### F4 — Effective Dimensionality (D_eff) — Dynamics Branch

| Required column | Present | Notes |
|----------------|---------|-------|
| `{Joint}__zeroed_rel_omega_mag` × 19 | ✓ All 19 present | Phase 6 confirmed |
| `{Joint}__is_artifact` × 19 | ✓ | All-joint AND clean mask |
| `time_s` | ✓ | Uniform 1/120 s, std=0 |

**Overall: PASS on column presence.** D_eff dynamics branch is ready to run.

### F5 — Joint Gini Coefficient

F5 reads exclusively from the shared `PCAEngine` output (§3 Key Pipeline Rules). No additional parquet columns beyond F4. Column compatibility is inherited from F4.

**Overall: PASS** — contingent on F4 PCAEngine construction.

---

## 2. CRITICAL: Hips ATF = 0 Permanently (Structural Bias)

**Severity: CRITICAL** | **Affects: F1 ATF — axial group**

### Root cause

`Hips` is the skeleton root joint. Root-relative positions are defined as:
```
pos_rel(t) = pos_world(t) − pos_root(t)
```

For Hips itself, `pos_rel = 0` by construction. Confirmed in Phase 6:
- `Hips__lin_rel_px/py/pz` = 0.000 for all 16,914 frames
- `Hips__lin_vel_rel_mag` = 0.000 for all frames

### Propagation through F1

`compute_atf` calls `compute_noise_floor(df, "Hips", cfg_nf, ...)` which:
1. Finds zero position variance in static window → `score ≈ 0` everywhere
2. Extracts mean velocity in best window ≈ 0 mm/s
3. Computes `V = 0 + 2×0 = 0`; Phase 3 guard raises to `V = noise_floor_guard_mms = 1.0 mm/s`
4. `noise_floor_low_confidence = False` (no warning raised)

Then ATF for Hips = proportion of frames where `lin_vel_rel_mag > 1.0 mm/s` = **0 / 16,914 = 0.000**.

The result is `Hips__ATF = 0.0` for every session, every subject. This is mathematically correct (relative velocity of a reference frame to itself is zero) but **physically meaningless and misleading**: Hips does move in space; only its root-relative representation is trivially zero.

### Downstream effect

```
ATF_axial = median(Hips=0.0, Spine=?, Spine1=?, Neck=?, Head=?)
```

Median of 5 values with one always-zero pulls the median downward, particularly if the other axial ATFs are also low (e.g., in an early-training session). This biases the "axial activation" trend.

**Neither `METHODOLOGY_SPEC_v2.md` §F1 nor `v2_feature_engine.py` acknowledge or handle this.**

### Recommended action

Add a documented exception: either (a) exclude `Hips` from ATF computation and the axial group median, replacing with global pelvis velocity from `wbc_com_{x,y,z}` or the WBCoM velocity magnitude; or (b) document Hips ATF = 0 as expected and remove it from the axial group for the summary statistic.

---

## 3. CRITICAL: ref_is_fallback Sessions — F4/F5 Silently Biased

**Severity: CRITICAL** | **Affects: F4 D_eff, F5 Gini** | **Found in: Phase 5.5 F-651-4**

### Root cause

For `651_T3_P2_R2`, the Step 05 reference detection found subject moving at recording start → fallback to `least_motion_window_fallback` → `ref_is_fallback = True`. Kinematics in the parquet (`zeroed_rel_*` columns) are computed relative to a wrong reference pose (an arbitrary non-T-pose window instead of true T-pose).

**F4 D_eff** and **F5 Joint Gini** consume `{Joint}__zeroed_rel_omega_mag` — angular velocity in the zeroed (reference-subtracted) frame. If the reference is wrong, the angular velocity baseline is shifted: the "zero point" in SO(3) is not the T-pose, so the magnitude of deviation from reference is systematically incorrect.

**F1 ATF** and **F2 TM** are NOT affected:
- ATF uses `lin_vel_rel_mag` (linear velocity, not zeroed)
- TM uses `lin_rel_px/py/pz` (absolute root-relative position, not zeroed)

### Gap in methodology spec

Block 0 quality gates (§2 Reliability Gates) do NOT include a gate for `ref_is_fallback`. The parquet metadata confirmed in Phase 6 does not contain `ref_is_fallback`. The quality gate `compute_quality_gates()` in `v2_feature_engine.py` has no check for fallback reference sessions.

`651_T3_P2_R2` would enter F4/F5 PCA with biased omega_mag values, producing D_eff and Gini results that are not comparable to T-pose-anchored sessions.

### Recommended action

1. **Short-term:** Add `ref_is_fallback` to parquet metadata (Phase 6, §10 decision). Read from S05 JSON derivative at parquet write time.
2. **Block 0:** Add gate check: if `ref_is_fallback = True` in parquet metadata → set `pca_unreliable = True` (or new field `ref_fallback_flag = True`) and exclude from primary F4/F5 analysis. Document in quality table.
3. **Spec amendment:** Add `ref_fallback_flag` to Block 0 Reliability Gates table.

---

## 4. HIGH: Artifact Fraction Computation — max() vs OR-Union

**Severity: HIGH** | **Affects: Block 0 session-level hard exclusion gate**

### Discrepancy

**Spec** (Block 0, §2 Reliability Gates):
> "Session artifact fraction = (1/T) Σ 1[any_joint_is_artifact(t)]"
This is the **OR-union** fraction — fraction of frames where **at least one** joint is dirty.

**Code** (`v2_feature_engine.py:compute_quality_gates`, line 219):
```python
global_artifact_frac = max(joint_art_rates.values()) if joint_art_rates else 0.0
```
This is the **maximum per-joint rate** — the worst single joint's artifact fraction.

### Why they differ

If different joints have non-overlapping artifact windows:
- Joint A: 15% artifact in frames 1–100
- Joint B: 15% artifact in frames 101–200
- **OR-union** fraction = up to 30% (frames 1–200)
- **max()** = 15%

The implementation can produce `hard_exclude=False` when the spec would produce `hard_exclude=True`. Sessions with spatially distributed artifact contamination (common in floor work with occlusion) may evade the hard exclusion gate.

### True OR-union is already computable

`clean_fraction_pca` in `compute_quality_gates` correctly computes the all-joint AND mask. Its complement gives the OR-union artifact fraction: `any_artifact_frac = 1.0 - clean_fraction_pca`.

However: `pca_clean_fraction` uses NOT(all-clean) = any-dirty, which is equivalent to OR-union artifact. So `global_artifact_frac = 1.0 - clean_fraction_pca` would implement the spec correctly. Currently, the `clean_fraction_pca` is computed and stored but is NOT used for `global_artifact_frac` / `hard_exclude`.

### Recommended fix

Replace:
```python
global_artifact_frac = max(joint_art_rates.values()) if joint_art_rates else 0.0
```
With:
```python
global_artifact_frac = 1.0 - clean_fraction_pca  # OR-union, per spec
```

---

## 5. HIGH: Reference Session Validation — Wrong Threshold

**Severity: HIGH** | **Affects: PCA reference quality gate**

### Discrepancy

**Spec** (§3 Key Pipeline Rules, Block 0 Reference session validation table):
> `ref_max_artifact_fraction = 0.20` — stricter than generic sessions (0.30)

**Code** (`v2_feature_engine.py:validate_reference`, line 276):
```python
if ref["hard_exclude"]:
    issues.append(...)
```
`hard_exclude` is set when `global_artifact_frac > 0.30` (the generic threshold, not 0.20).

A reference session with 25% artifact contamination would pass `validate_reference()` (25% < 30%) but should fail per spec (25% > 20%). If a biased reference corrupts the PCA basis, all downstream D_eff and Gini values for all sessions become unreliable.

### Recommended fix

Add explicit check in `validate_reference()`:
```python
ref_max_art = 0.20  # from CONFIG.get("ref_max_artifact_fraction", 0.20)
if ref["global_artifact_frac"] > ref_max_art:
    issues.append(f"artifact_frac={ref['global_artifact_frac']:.3f} > ref threshold {ref_max_art}")
```

---

## 6. HIGH: Dead Session Gate — `short_session` Flag, Not Hard Exclude

**Severity: HIGH** | **Affects: 651_T2_P2_R2 (5 frames, 0.04s)**

### Discrepancy

**Spec** (Block 0, quality table and dead_recording gate):
> `dead_recording=True` → **"Hard exclude — omit from all F1–F5 and PCA."**
> Default thresholds: `dead_recording_max_frames = 1000`, `dead_recording_max_duration_s = 8.0`

**Code** (`v2_feature_engine.py:compute_quality_gates`):
```python
short_session = duration_s < min_dur    # min_dur = 60.0
```
For 651_T2_P2_R2 (5 frames, 0.04s):
- `duration_s = 0.04 < 60.0` → `short_session = True`
- `global_artifact_frac = 0` (no artifact flags) → `hard_exclude = False`

The dead session is `short_session=True` but **`hard_exclude=False`**. No `dead_recording` field exists in `quality_df`. The session would be passed to `build_pca_engine()` and fail only if it happens to be the reference session (validator check on `clean_duration_s < 60.0`). If used as a non-reference session, `build_pca_engine` would attempt to transform 5 frames through the 19-component PCA — producing a numerically degenerate var_per_pc.

**Additionally:** `var_score = inf` was serialized as a JSON Infinity value in S05 for this session (F-651-2, Phase 5.5), invalidating JSON parsing.

### Recommended fix

Add explicit `dead_recording` check in `compute_quality_gates`:
```python
dead_recording = (n_frames <= config.get("dead_recording_max_frames", 1000)
                  or duration_s <= config.get("dead_recording_max_duration_s", 8.0))
hard_exclude = hard_exclude or dead_recording
```
And include `dead_recording` as a column in the returned DataFrame.

---

## 7. MEDIUM: REVIEW_OVERSMOOTHING — Impact on F1 and F2

**Severity: MEDIUM** | **Affects: F1 ATF (noise floor), F2 TM (path length)**

### Background

Phase 5.5 confirmed REVIEW_OVERSMOOTHING is UNIVERSAL: all 57 position columns across ALL live sessions for both subjects 651 and 671. Mean dance-band attenuation ≈ −4.7 to −5.4 dB (worst: Hips__py ≈ −24 to −27 dB). This means positions are systematically smoothed beyond the dance frequency band.

### F1 ATF impact

ATF input `{Joint}__lin_vel_rel_mag` is the SavGol derivative of over-smoothed positions. Over-smoothing removes high-frequency content from positions → resulting velocity magnitude underestimates true movement magnitude, particularly for high-velocity segments (accents, fast gestures). This:
1. **Compresses the velocity dynamic range** — high-velocity peaks are attenuated
2. **Lowers the noise floor estimate** — `compute_noise_floor` uses first 8s position variance; over-smoothed positions have lower variance → lower V
3. **Potential ATF inflation** — if V is artificially low, more frames register as "active"

Net effect direction depends on whether the noise floor reduction outweighs the velocity attenuation. Not cleanly predictable without session-specific analysis.

### F2 TM impact

TM = cumulative Euclidean path length of 4 endpoints. Over-smoothed positions produce shorter paths (smoothing "cuts corners" in Euclidean space). TM **underestimates true movement**.

Direction: systematic downward bias in TM across all sessions. Since all sessions are equally affected (universal REVIEW_OVERSMOOTHING), relative longitudinal comparisons (T3 vs T1) may be less affected. But absolute TM values are uninterpretable as ground-truth path lengths.

### Recommended action

1. Add `filter_psd_verdict` and `mean_dance_delta_dB` to parquet metadata (Phase 6, §10 decision already listed).
2. In `notebooks/11_METH_SPEC_v2_Features.ipynb` Block 0, check parquet metadata for `filter_psd_verdict = "REVIEW_OVERSMOOTHING"` and flag sessions accordingly in quality_df.
3. For thesis reporting: add caveat that TM values reflect over-smoothed path lengths; frame as relative comparisons only.

---

## 8. MEDIUM: Session-Native D_eff — `ddof` Inconsistency

**Severity: MEDIUM** | **Affects: Dual-mode sensitivity table for F4**

### Discrepancy

**T1-anchored D_eff** (`compute_d_eff`, line 620):
```python
var_per_pc = np.var(Y_s, axis=0)    # ddof=0 (population variance)
```

**Session-native D_eff** (`compute_d_eff`, lines 643–647):
```python
pca_native.fit(X_ss)
ev_native = pca_native.explained_variance_   # ddof=1 (sample variance, sklearn default)
```

`sklearn.decomposition.PCA.explained_variance_` = sample variance (n-1 denominator) = `np.var(axis=0, ddof=1)`. This is **not the same** as `np.var(axis=0)` (ddof=0).

When comparing T1-anchored D_eff to session-native D_eff in the dual-mode sensitivity table (§F4 Mandatory Dual-Mode Sensitivity Analysis), the two values are computed with different normalizations. For large N (>10,000 frames), the difference is negligible (n/(n-1) ≈ 1.0001). But the inconsistency should be documented.

The same issue applies to F5 session-native Gini (`ev_nat = pca_nat.explained_variance_` vs T1-anchored path using `np.var(ddof=0)`).

### Recommended fix

For consistency, use `np.var(Y_native, axis=0)` in session-native paths instead of `pca_native.explained_variance_`. At 120 Hz over 100+ seconds, the numerical impact is minimal, but consistency is important for reproducibility.

---

## 9. MEDIUM: `dead_recording` Field Absent from quality_df

**Severity: MEDIUM** | **Affects: Block 0 completeness**

The spec's Block 0 quality table schema requires `dead_recording` as a diagnostic column:

| Column spec | In `compute_quality_gates` output | Status |
|------------|----------------------------------|--------|
| `dead_recording` | Absent | **ABSENT** |

The quality_df returned by `compute_quality_gates()` has columns: `run_id`, `n_frames`, `duration_s`, `global_artifact_frac`, `clean_fraction_pca`, `clean_duration_s`, `hard_exclude`, `soft_warning`, `pca_low_confidence`, `short_session`, `joints_excluded`, `endpoints_flagged`, `joint_artifact_rates`.

No `dead_recording` column. No `reference_session` column (required in core gate columns). No `pca_unreliable` column (spec uses this name; code uses `pca_low_confidence`). These are naming inconsistencies between spec and implementation.

---

## 10. MEDIUM: `v2_longitudinal.py` Absent

**Severity: MEDIUM** | **Affects: longitudinal delta computation, T2 isolation gate**

The spec requires `src/v2_longitudinal.py` for:
- Longitudinal delta computation (T3 − T1 per metric)
- T2 Isolation Gate (§Appendix E) — requires `CONFIG['run_t2_isolation']`
- Longitudinal delta bootstrap (§Appendix D.2)

`v2_longitudinal.py` **does not exist** on disk. This is marked as deferred in §3.8 (MVP scope), so this is expected. However, without it, the pipeline cannot produce thesis-grade longitudinal comparisons or the T2 isolation table.

**Status:** Expected deferral, not a bug. Requires implementation before thesis submission.

---

## 11. LOW: Only `dynamics` Branch Implemented (MVP)

**Severity: LOW** | **Affects: F4/F5 sensitivity analysis branches**

`_get_dynamics_columns()` in `v2_feature_engine.py`:
```python
def _get_dynamics_columns(branch: str = "dynamics") -> List[str]:
    if branch == "dynamics":
        return [f"{j}__zeroed_rel_omega_mag" for j in ALL_19_JOINTS]
    raise ValueError(f"Unsupported kinematic branch: '{branch}'. MVP supports 'dynamics' only.")
```

The spec (§F4) specifies two additional sensitivity branches:
- `pose` (57D — `{Joint}__zeroed_rel_rotvec_{x,y,z}`)
- `reach` (57D — `{Joint}__lin_rel_p{x,y,z}`)

Both columns exist in the parquet. Branch support is a §3.8 deferred item.

---

## 12. LOW: `is_hampel_outlier = 0` — F1/F2/F4/F5 Cannot Identify Hampel-Repaired Frames

**Severity: LOW** | **Affects: data provenance tracking** | **Phase 6 finding confirmed**

1163 Hampel-corrected position frame-column pairs from S04 have no provenance flag in the parquet. The feature engine uses `is_artifact` for masking, which is correctly populated from the rotation/velocity threshold checks. Hampel-repaired frames (0.12% of frames) are treated as clean by all features. This is a minor provenance gap with negligible numerical impact at 0.12%.

---

## 13. LOW: Session Registry — Two P2 Candidates per Timepoint

**Severity: LOW** | **Affects: notebook run setup**

For both subjects, each timepoint has two P2 repetitions (R1 and R2). The spec's ambiguity rule (§Block 0) requires the analyst to set `CONFIG['run_ids_by_timepoint']` explicitly before running, or the notebook must halt with an error listing competing candidates. This is correct per the spec — not a code bug, but a required notebook preamble step.

Special case: `651_T2_P2_R2` is a dead session (5 frames). It will appear in the scan of `derivatives/step_06_kinematics/` as a candidate. The `dead_recording` gate (once implemented) would automatically exclude it.

---

## 14. Feature Engine Implementation — What Works

| Check | Status |
|-------|--------|
| F1 ATF: velocity + artifact column loading | ✓ PASS |
| F1 ATF: `compute_noise_floor` interface compatible with pulsicity.py | ✓ PASS — confirmed signature match |
| F1 ATF: NaN-safe computation (artifacts excluded, not zero-filled) | ✓ PASS |
| F1 ATF: group medians (axial/peripheral/transitional) | ✓ PASS (Hips issue noted §2) |
| F2 TM: contiguous-run normative logic (not mask-then-diff) | ✓ PASS — correctly implemented |
| F2 TM: per-endpoint path length summation | ✓ PASS |
| F2 TM: rate normalization | ✓ PASS |
| F4 PCAEngine: reference-anchored StandardScaler + PCA.fit on reference only | ✓ PASS |
| F4 PCAEngine: pca.transform() (not manual matrix multiply) for all sessions | ✓ PASS |
| F4 D_eff: participation ratio formula `1/Σp²` | ✓ PASS |
| F4/F5: anti-double-dipping (single PCAEngine fit, both features read from it) | ✓ PASS |
| F5 Gini: sorted-form formula correct | ✓ PASS |
| F5 Gini: T1-anchored vs session-native dual-mode | ✓ PASS (ddof inconsistency noted §8) |
| F5 Gini session-native: mean-centering (not StandardScaler) | ✓ PASS — correctly documented |
| ALL_19_JOINTS list matches parquet joint names | ✓ PASS — exact match confirmed |
| TM_ENDPOINTS (LeftHand, RightHand, LeftFoot, RightFoot) match parquet | ✓ PASS |
| `apply_time_window` utility | ✓ PASS |
| `load_session` Parquet loader | ✓ PASS |
| `assemble_feature_row` tidy output | ✓ PASS |
| `compute_ap_ratio` A/P ratio computation | ✓ PASS |

---

## 15. Summary Table

| Finding | ID | Severity | Feature(s) | Status |
|---------|-----|---------|-----------|--------|
| Hips ATF = 0 (root joint structural bias) | F7-1 | **CRITICAL** | F1 ATF axial | Spec + code gap |
| ref_is_fallback absent → F4/F5 silently biased | F7-2 | **CRITICAL** | F4, F5 | Parquet gap (Phase 6 F-INT3 extension) |
| Artifact fraction: max() vs OR-union | F7-3 | HIGH | All (session gate) | Code-spec divergence |
| Reference threshold 0.30 not 0.20 | F7-4 | HIGH | F4, F5 (PCA basis) | Code-spec divergence |
| Dead session: short_session not hard_exclude | F7-5 | HIGH | All | Code-spec divergence |
| REVIEW_OVERSMOOTHING affects F1/F2 | F7-6 | MEDIUM | F1, F2 | Parquet metadata gap (Phase 6) |
| Session-native ddof inconsistency | F7-7 | MEDIUM | F4, F5 native | Code inconsistency |
| `dead_recording` absent from quality_df | F7-8 | MEDIUM | Block 0 | Code-spec gap |
| `v2_longitudinal.py` absent | F7-9 | MEDIUM | Longitudinal | MVP deferral (expected) |
| Only `dynamics` branch implemented | F7-10 | LOW | F4, F5 sensitivity | MVP deferral (expected) |
| `is_hampel_outlier = 0` → no Hampel provenance | F7-11 | LOW | All (provenance) | Phase 6 finding |
| Two P2 candidates per timepoint (analyst decision needed) | F7-12 | LOW | All | Workflow requirement |

---

## 16. Decisions Triggered

| Finding | Recommended action | Priority |
|---------|-------------------|----------|
| F7-1: Hips ATF = 0 | Exclude Hips from ATF axial group median; document in spec §F1 | **Critical** |
| F7-2: ref_is_fallback absent | Add `ref_is_fallback` to parquet metadata + Block 0 gate | **Critical** |
| F7-3: Artifact fraction computation | Replace `max(joint_art_rates)` with `1.0 − clean_fraction_pca` in `compute_quality_gates` | High |
| F7-4: Reference threshold | Add explicit 0.20 artifact check in `validate_reference()` reading from `CONFIG` | High |
| F7-5: Dead session gate | Add `dead_recording` hard-exclude flag in `compute_quality_gates` | High |
| F7-6: REVIEW_OVERSMOOTHING caveat | Add metadata check + warning in notebook Block 0; add thesis caveat for TM absolute values | Medium |
| F7-7: ddof inconsistency | Use `np.var(ddof=0)` in session-native paths for consistency | Medium |
| F7-8: quality_df column naming | Add `dead_recording`, rename `pca_low_confidence` → `pca_unreliable`, add `reference_session` | Medium |
| F7-9: v2_longitudinal.py | Implement before thesis submission; required for delta tables + T2 isolation | Medium |
| F7-10: Branch support | Implement pose/reach branches per §3.8 v3.1 | Low |
| F7-11: Hampel provenance | Fix S06 Hampel propagation (Phase 6 §10) | Low |

---

*Phase 7 audit complete. Next phase: Phase 8 — Fast post-collection QC requirements.*
