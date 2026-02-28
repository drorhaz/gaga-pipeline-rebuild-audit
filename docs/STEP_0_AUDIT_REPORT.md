# STEP_0_AUDIT_REPORT.md
## Kinematic Integrity Audit — Step 0 (Audit Pass 1: Linear Chain & Math)
### Gaga Motion Analysis Pipeline

**Audit Date:** 2026-02-27
**Auditor:** Biomechanical Engineering & Python Development
**Scope:** Trace the exact mathematical path from position marker to `{segment}__lin_vel_rel_mag`
**Primary Sources Examined:**
- `notebooks/06_ultimate_kinematics.ipynb`
- `src/kinematic_repair.py`
- `src/pipeline_config.py`
- `config/config_v1.yaml`
- `derivatives/step_05_reference/` (directory listing)

---

## Section 1 — The Complete Derivation Chain

Before the discrepancy table, the exact code path is traced here in full.

### Stage 1: Config Parameter Resolution

The notebook reads config parameters using **uppercase keys** (`FS_TARGET`, `SG_WINDOW_SEC`, `SG_POLYORDER`). The YAML file uses **lowercase keys**. The bridge is `src/pipeline_config.py`, which creates uppercase aliases:

```
config_v1.yaml          pipeline_config.py              NB06 runtime
─────────────────       ────────────────────────────    ──────────────────────
fs_target: 120.0    →   'FS_TARGET': 120.0          →   FS = 120.0
sg_window_sec: 0.175 →  'SG_WINDOW_SEC': 0.175      →   SG_WINDOW_SEC = 0.175
sg_polyorder: 3     →   'SG_POLYORDER': 3           →   SG_POLYORDER = 3
```

**Source:** `src/pipeline_config.py`, lines 30–33 (`_UPPERCASE_ALIASES` dict).

### Stage 2: W_LEN Computation (`savgol_window_len`)

Defined in NB06 (setup cell):

```python
def savgol_window_len(fs, w_sec, polyorder):
    w_len = int(round(w_sec * fs))       # int(round(0.175 * 120)) = int(21.0) = 21
    if w_len % 2 == 0:
        w_len += 1                        # 21 is odd — no change
    w_len = max(5, w_len, polyorder + 2) # max(5, 21, 5) = 21 — no change
    if w_len % 2 == 0:
        w_len += 1                        # 21 is odd — no change
    return w_len                          # → W_LEN = 21

W_LEN = savgol_window_len(FS, SG_WINDOW_SEC, SG_POLYORDER)
# → W_LEN = 21
```

**Printed at runtime:** `"SavGol window: 21"` (confirmed in stored cell output for run `734_T3_P2_R1`).

### Stage 3: Root-Relative Position Subtraction

```python
root_pos_cols = [f"{ROOT_SEGMENT}__px", f"{ROOT_SEGMENT}__py", f"{ROOT_SEGMENT}__pz"]
root_pos = df_in[root_pos_cols].values

pos_rel = {}
for col in pos_cols:                   # pos_cols = all __px/__py/__pz columns
    seg, suffix = col.split('__')[0], '__' + col.split('__')[1]
    idx = axis_idx.get(suffix, 0)      # __px→0, __py→1, __pz→2
    pos_rel[col] = df_in[col].values - root_pos[:, idx]
```

`ROOT_SEGMENT` is `'Pelvis'` if present, else `'Hips'`. Positions are sourced from the **step_04_filtering** parquet (Winter-Butterworth filtered). Units: **mm** (inherited from OptiTrack output and step_01 parsing).

### Stage 4: SavGol Simultaneous Derivative (Primary Path)

```python
# NB06 — linear velocity cell (one call per axis per segment)
for col in pos_cols:
    seg, suffix = col.split('__')[0], '__' + col.split('__')[1]
    if col not in pos_rel:
        continue
    pr = pos_rel[col]                  # root-relative position [mm], shape (T,)
    vel = savgol_filter(pr, W_LEN, SG_POLYORDER, deriv=1, delta=dt, mode='interp')
    acc = savgol_filter(pr, W_LEN, SG_POLYORDER, deriv=2, delta=dt, mode='interp')
    axis_letter = col[-1]              # last char of col name: 'x', 'y', or 'z'
    result[f"{seg}__lin_vel_rel_{axis_letter}"] = vel
    result[f"{seg}__lin_acc_rel_{axis_letter}"] = acc
```

**Parameters confirmed:** `W_LEN=21`, `SG_POLYORDER=3`, `deriv=1`, `delta=1/120`, `mode='interp'`.

### Stage 5: Euclidean Norm → `lin_vel_rel_mag`

```python
# NB06 — magnitude cell (runs after all axes are computed)
for seg in segments_with_pos:
    vel_cols = [f"{seg}__lin_vel_rel_x", f"{seg}__lin_vel_rel_y", f"{seg}__lin_vel_rel_z"]
    if all(c in result for c in vel_cols):
        vel_vec = np.column_stack([result[c] for c in vel_cols])   # shape (T, 3)
        result[f"{seg}__lin_vel_rel_mag"] = np.linalg.norm(vel_vec, axis=1)
```

**Exact formula:** `||[vx, vy, vz]||₂` via `np.linalg.norm(..., axis=1)` (row-wise L2 norm).

### Stage 6: Artifact Flagging (Post-Velocity)

```python
# Joint-level (rotation + angular velocity only):
THRESH_ARTIFACT = {
    'rotation_mag_deg':      140.0,
    'angular_velocity_deg_s': 800.0,
    'linear_velocity_mm_s':  3000.0,
}
for joint_name in kinematics_map:
    artifact_mask  = result[f"{joint_name}__zeroed_rel_rotmag"] >= 140.0
    artifact_mask |= result[f"{joint_name}__zeroed_rel_omega_mag"] >= 800.0
    result[f"{joint_name}__is_artifact"] = artifact_mask

# Segment-level (adds linear velocity criterion):
for seg in segments_with_pos:
    artifact_mask = result[f"{seg}__is_artifact"].copy()   # from joint if joint==seg, else zeros
    artifact_mask |= result[f"{seg}__lin_vel_rel_mag"] >= 3000.0
    result[f"{seg}__is_artifact"] = artifact_mask          # final flag written to parquet
```

**Ordering note:** `lin_vel_rel_mag` is computed **before** `is_artifact`. The artifact flag is then computed from `lin_vel_rel_mag`. This means in the saved parquet, `is_artifact[t] == True` and `lin_vel_rel_mag[t] >= 3000.0` are simultaneously true for any frame that triggered the linear velocity criterion. This is consistent and correct.

---

## Section 2 — Master Discrepancy Table (Audit Pass 1)

| # | Feature / Logic | Documented Standard | Actual Code Implementation | Status | Risk |
|---|----------------|--------------------|-----------------------------|--------|------|
| 1 | **Euclidean norm of velocity** | $\|\|[v_x, v_y, v_z]\|\|_2$ | `np.linalg.norm(np.column_stack([result[vx], result[vy], result[vz]]), axis=1)` — NB06 line ~407 | **MATCH** | LOW |
| 2 | **SavGol window length** | 175 ms = 21 frames at 120 Hz | `W_LEN = savgol_window_len(120.0, 0.175, 3)` → `int(round(21.0)) = 21` (verified in cell output) | **MATCH** | LOW |
| 3 | **SavGol polynomial order** | order = 3 | `SG_POLYORDER = CONFIG.get('SG_POLYORDER', 3)` → `3` | **MATCH** | LOW |
| 4 | **SavGol derivative mode** | Simultaneous differentiation (`deriv=1`) — no separate finite-difference step | `savgol_filter(pr, W_LEN, SG_POLYORDER, deriv=1, delta=dt, mode='interp')` — NB06 linear velocity cell | **MATCH** | LOW |
| 5 | **SavGol delta (time step)** | `delta = 1/fs = 1/120 s` | `dt = 1.0 / FS` then passed as `delta=dt` | **MATCH** | LOW |
| 6 | **Config key casing** | Config values read from `config_v1.yaml` (`fs_target`, `sg_window_sec`, `sg_polyorder`) | NB06 requests uppercase keys (`FS_TARGET`, `SG_WINDOW_SEC`, `SG_POLYORDER`); `pipeline_config.py` provides uppercase aliases — bridge is intentional and documented | **MATCH** | LOW |
| 7 | **Root-relative position input** | Velocity derived from positions relative to root segment (Hips/Pelvis) | `pos_rel[col] = df_in[col].values - root_pos[:, idx]` before SavGol call; `ROOT_SEGMENT = 'Pelvis' if 'Pelvis' in kinematics_map else 'Hips'` | **MATCH** | LOW |
| 8 | **Artifact threshold — rotation** | > 140° | `THRESH_ARTIFACT['rotation_mag_deg'] = 140.0` / `result[rotmag_col] >= 140.0` | **MATCH** | LOW |
| 9 | **Artifact threshold — angular velocity** | > 800 deg/s | `THRESH_ARTIFACT['angular_velocity_deg_s'] = 800.0` / `result[omega_mag_col] >= 800.0` | **MATCH** | LOW |
| 10 | **Artifact threshold — linear velocity** | > 3,000 mm/s | `THRESH_ARTIFACT['linear_velocity_mm_s'] = 3000.0` / `result[linvel_mag_col] >= 3000.0` | **MATCH** | LOW |
| 11 | **`is_artifact` applies to velocity** | Documentation: "artifact frames already flagged" — implies masking is pre-computed | Correct in final parquet state. Ordering: velocity is computed first, then `is_artifact` is derived from it. The flag correctly identifies all artifact frames in `lin_vel_rel_mag`. | **MATCH** *(ordering note — see below)* | LOW |
| 12 | **`lin_vel_rel_mag` after surgical repair** | Not explicitly documented | After `apply_surgical_repair()`, `result[f"{seg}__lin_vel_rel_x/y/z"]` are updated. However, `result[f"{seg}__lin_vel_rel_mag"]` is **NOT recomputed**. The magnitude column remains from the pre-repair pass. | **DISCREPANCY** | MEDIUM |
| 13 | **`reference_map.json` on disk** | NB06 reads `{RUN_ID}__reference_map.json` from `derivatives/step_05_reference/` | NB05 writes this file. **None of the 16 current recordings have a `*__reference_map.json` on disk.** Only `*__reference_summary.csv` files exist. NB06 cannot be re-run on any existing recording without regenerating this file. | **DISCREPANCY** | HIGH |
| 14 | **`W_LEN` minimum guard** | Not documented | `w_len = max(5, w_len, polyorder + 2)` enforces `W_LEN >= max(5, polyorder+2)`. At standard parameters (W_LEN=21, polyorder=3), this guard is never triggered. Benign. | **UNDOCUMENTED** | LOW |

---

## Section 3 — Findings Narrative

### Finding F1 — MATCH: Complete Velocity Math Verified ✓

The path from root-relative position to `lin_vel_rel_mag` is mathematically clean and matches documentation exactly:

1. Root-relative position computed by vector subtraction from `ROOT_SEGMENT` global position
2. `savgol_filter(pos, W_LEN=21, SG_POLYORDER=3, deriv=1, delta=1/120, mode='interp')` applied per-axis — simultaneous smoothing and differentiation, no separate finite-difference step
3. `lin_vel_rel_mag = ||[vx, vy, vz]||₂` via `np.linalg.norm(..., axis=1)`

All three questions posed in the audit prompt are confirmed as MATCH.

---

### Finding F2 — DISCREPANCY (MEDIUM): Surgical Repair Does Not Recompute `lin_vel_rel_mag`

**Location:** `apply_surgical_repair()` in `src/kinematic_repair.py`, called from NB06.

**What happens:** When `ENFORCE_CLEANING = True` and a segment is flagged as a critical outlier, the repair path:
1. PCHIP-interpolates the root-relative position at critical frames (`pos_rel[col]`)
2. Re-derives `result[f"{seg}__lin_vel_rel_x/y/z"]` with `savgol_filter(..., deriv=1, ...)`
3. Re-derives `result[f"{seg}__lin_acc_rel_x/y/z"]` with `savgol_filter(..., deriv=2, ...)`
4. **Does NOT recompute** `result[f"{seg}__lin_vel_rel_mag"]`

**Consequence:** For any recording where `ENFORCE_CLEANING = True` AND a linear segment was repaired, the `lin_vel_rel_mag` column in the saved parquet reflects the **pre-repair** velocity components, not the repaired ones.

**Current exposure:** Zero. All 16 existing recordings were processed with `ENFORCE_CLEANING = False` (confirmed from stored cell output: `"ENFORCE_CLEANING: False"`). The discrepancy is dormant.

**Relevance to Step 07:** Low currently. However, if any future recording is processed with `ENFORCE_CLEANING = True`, Step 07's `lin_vel_rel_mag` input would be silently stale for repaired segments.

**Recommended action (for Step 07 documentation):** Add a provenance check in `src/pulsicity.py` that logs `step_06.enforce_cleaning` from config. If `True`, emit a warning that `lin_vel_rel_mag` consistency with `lin_vel_rel_x/y/z` components should be manually verified.

---

### Finding F3 — DISCREPANCY (HIGH): `reference_map.json` Files Missing on Disk

**Location:** NB06 setup cell, line ~98–102.

**What NB06 expects:**
```python
ref_path = Path(DERIV_REF) / f"{RUN_ID}__reference_map.json"
if not ref_path.exists():
    raise FileNotFoundError(f"Reference map not found: {ref_path}")
with open(ref_path, 'r', encoding='utf-8') as f:
    ref_pose = json.load(f)
```

**What NB05 produces:** At the end of NB05, `REFERENCE_ROTATIONS` (a flat dict of `{joint_name}__qx/y/z/w` keys) is serialized to `{RUN_ID}__reference_map.json` in `derivatives/step_05_reference/`.

**What exists on disk:** Only `{RUN_ID}__reference_summary.csv` files (joint-level Euler angles and quaternion offsets). **Zero `*__reference_map.json` or `*__reference_euler.json` files exist** for any of the 16 recordings.

**Assessment:** The 16 kinematics_master.parquet files were successfully produced, which means NB06 was run successfully — meaning `reference_map.json` files existed at the time of processing and were subsequently deleted (likely excluded from git commit or cleaned up). The T-pose zeroing is already baked into the parquet; the missing JSON only affects reproducibility (inability to re-run NB06 without re-running NB05 first).

**Relevance to Step 07:** Indirect. Step 07 reads the parquet output directly and does not call NB06 again. However, this is a **pipeline reproducibility gap** that should be flagged.

**Recommended action:** `reference_map.json` files should be committed to the repository (they contain no sensitive data — just rotation offsets). Or NB06 should be modified to fall back to reading from `reference_summary.csv` if the JSON is absent.

---

### Finding F4 — NOTE: `lin_vel_rel_mag` Artifact Flag Ordering

The computation sequence in NB06 is:

```
[1] lin_vel_rel_x/y/z computed (SavGol)
[2] lin_vel_rel_mag computed (Euclidean norm)       ← magnitude exists
[3] joint is_artifact flags set (rot, omega only)
[4] segment is_artifact flags set (includes lin_vel_rel_mag >= 3000)
```

This means `lin_vel_rel_mag` is computed without any artifact masking — the SavGol derivative is applied to the raw filtered position signal, including any high-velocity frames. The `is_artifact` flag is then derived from the resulting `lin_vel_rel_mag`. In the saved parquet, for every frame where `is_artifact == True` due to linear velocity, `lin_vel_rel_mag >= 3000` mm/s will also be true.

**Consequence for Step 07:** When Step 07 masks `lin_vel_rel_mag` using `is_artifact`, it is correctly removing both the extreme-velocity frames AND any frames flagged for rotation/angular velocity reasons. No action required.

---

## Section 4 — Step 07 Implications Summary

| Finding | Step 07 Impact | Action Required |
|---------|---------------|-----------------|
| F1 (all MATCH) | Velocity math is sound; `lin_vel_rel_mag` can be used as the Measurement Signal as specified | None |
| F2 (repair path) | Negligible for all 16 existing parquets (ENFORCE_CLEANING=False). Log a provenance warning in `pulsicity.py` for future recordings | Add config check in Step 07 |
| F3 (missing JSON) | Does not affect Step 07 execution — parquets are already written. Affects reproducibility of NB06 | Flag in audit report; no Step 07 code impact |
| F4 (ordering) | Artifact flag correctly identifies high-velocity frames; masking in Step 07 is valid | None |

---

## Section 5 — Pending Audit Items (Future Passes)

Pass 2 items are now resolved (see Section 6). The following items remain for future passes:

| Item | Target File | Description |
|------|-------------|-------------|
| **Pass 3** | `src/artifacts.py` / NB02 | Verify MAD multiplier = 6×, binary dilation = ±1 frame |
| **Pass 3** | `src/pipeline_config.py` | Verify `MOTION_THR_STD: 0.15` alias — confirm it plays no role in static window selection (Step 0 Audit finding) |

---

*Audit Pass 1 complete. Three items confirmed MATCH, one DISCREPANCY (MEDIUM, dormant), one DISCREPANCY (HIGH, reproducibility only), one UNDOCUMENTED (benign guard). No Step 07 blocking issues found.*

---

## Section 6 — Audit Pass 2: The Filter Phase

**Audit Date:** 2026-02-27
**Scope:** Filter type confirmation, per-region cutoff semantics, Stage 1 artifact thresholds, Winter fmax consistency
**Primary Sources Examined:**
- `src/filtering.py` (lines 58–1084 — full read)
- `config/config_v1.yaml` (`filtering` block)
- `notebooks/04_filtering.ipynb` (stored runtime output)

### Pass 2 Master Discrepancy Table

| # | Feature / Logic | Documented Standard | Actual Code Implementation | Status | Risk |
|---|----------------|--------------------|-----------------------------|--------|------|
| 15 | **Filter method — filtfilt vs lfilter** | Zero-phase (forward + backward) filtering | `from scipy.signal import butter, filtfilt` (line 6); Stage 3 call: `filtered = filtfilt(b, a, signal.astype(float))` (line 828); metadata: `'Butterworth 2nd-order (zero-phase)'` | **MATCH** | LOW |
| 16 | **Per-region cutoff semantics** | Documentation: "per-region fixed cutoffs" — trunk 6 Hz, head 8 Hz, upper_distal 12 Hz, lower_distal 10 Hz | `BODY_REGIONS['fixed_cutoff']` is used as `min_cutoff` FLOOR for the adaptive Winter residual analysis — NOT as a hard-coded filter cutoff. Actual cutoff per-marker is dynamically selected in `[fixed_cutoff, winter_fmax]` range by the Winter knee algorithm. Fixed cutoff acts as biomechanical guardrail (`max(optimal_fc, min_cutoff)`). | **DISCREPANCY** | MEDIUM |
| 17 | **Winter fmax — documentation vs runtime** | Documented as 16 Hz (expanded from 12 Hz for Gaga); module constant `WINTER_FMAX = 16` (line 99) | Runtime flow: NB04 → `apply_signal_cleaning_pipeline(winter_fmax=20.0)` → `apply_adaptive_winter_filter(fmax=20.0)` → `winter_residual_analysis(fmax=20)`. Module constant `WINTER_FMAX` is a **dead constant** — defined but never referenced in the call chain. Actual data processed with fmax=20 Hz. | **DISCREPANCY** | MEDIUM |
| 18 | **Stage 1 `velocity_limit` function default** | Config and documentation: 5000.0 mm/s | `detect_artifact_gaps()` default: `velocity_limit: float = 1800.0`; `apply_signal_cleaning_pipeline()` default: `velocity_limit: float = 1800.0`. Runtime NB04 call explicitly passes `5000.0` from config — runtime is correct. Function defaults are 2.8× below the intended threshold. | **DISCREPANCY** | LOW |
| 19 | **Stage 1 `zscore_threshold`** | 5.0 σ | Function default: `5.0`; config: `5.0`; NB04 confirmed: `zscore_threshold: 5.0 σ` | **MATCH** | LOW |
| 20 | **Module constant `WINTER_FMAX`** | Used as global search ceiling | `WINTER_FMAX = 16` defined at line 99, but **never referenced** anywhere in `filtering.py`. The runtime fmax of 20.0 arrives via config; the constant is dead code. | **UNDOCUMENTED** | LOW |

---

### Finding P2-F1 — MATCH: Zero-Phase Filtering Confirmed ✓

**Location:** `src/filtering.py`, line 6 (import) and line 828 (call site).

Stage 3 applies a 2nd-order Butterworth low-pass via `filtfilt`, which performs a forward pass then a backward pass, achieving zero-phase distortion. This is consistent with biomechanical kinematic analysis best practice and with what the METHODS_DOCUMENTATION.md states. `lfilter` (single-pass, introduces phase lag) is **not used anywhere** in the filter pipeline.

---

### Finding P2-F2 — DISCREPANCY (MEDIUM): Per-Region Cutoffs Are Floors, Not Fixed Values

**Location:** `src/filtering.py`, `BODY_REGIONS` dict (lines 58–95), `apply_signal_cleaning_pipeline()` Stage 3 block (lines 1032–1057), `winter_residual_analysis()` guardrail block (lines 397–414).

**What documentation implies:** Each body region's markers are filtered at a fixed frequency: trunk=6 Hz, head=8 Hz, upper_proximal=8 Hz, upper_distal=12 Hz, lower_proximal=8 Hz, lower_distal=10 Hz.

**What the code does:**
```python
# Stage 3 block in apply_signal_cleaning_pipeline():
marker_region = classify_marker_region(col)
region_config = BODY_REGIONS.get(marker_region, BODY_REGIONS['upper_proximal'])
min_cutoff = region_config.get('fixed_cutoff', 6.0)   # ← used as FLOOR, not as fixed cutoff

signal_stage3, winter_meta = apply_adaptive_winter_filter(
    signal_stage2, fs=fs,
    fmin=winter_fmin,
    fmax=winter_fmax,              # 20.0 at runtime
    min_cutoff=min_cutoff,         # e.g., 12.0 for upper_distal
    body_region=marker_region
)
```

Inside `winter_residual_analysis()`:
```python
# Guardrail application (lines 397–414):
if min_cutoff is not None:
    optimal_fc = max(optimal_fc, min_cutoff)   # clamp to floor — not force to fixed value
```

**Consequence:** For a `RightHand__px` marker (upper_distal, `fixed_cutoff=12`), the actual filter cutoff is `max(Winter_knee_result, 12.0)`, which may be anywhere from 12 Hz to 20 Hz depending on signal dynamics. The fixed cutoff is a **biomechanical lower bound**, not the final cutoff. The BODY_REGIONS comments themselves confirm: `'cutoff_range': (8, 14)` entries are labelled `"Range for validation only"` — meaning the range, not the fixed_cutoff, describes the expected operating envelope.

**Why this matters for Step 07:** The actual filter cutoff for each marker is session-dependent (adaptive) and not the fixed value. Documentation should be corrected to say "biomechanical floor cutoffs" rather than "fixed cutoffs." For Step 07 SPARC frequency cap (SavGol effective cutoff ~2.3 Hz), this does not affect the cap choice — but it does affect the interpretation of what "fully resolved frequencies" exist above 2.3 Hz in the measurement signal.

---

### Finding P2-F3 — DISCREPANCY (MEDIUM): Winter fmax Dead Constant + Runtime Value Differs from Documentation

**Location:** `src/filtering.py`, line 99 (`WINTER_FMAX = 16`); `apply_adaptive_winter_filter()` signature (line 749–752); `winter_residual_analysis()` signature (line 138–141); NB04 runtime call.

**Three-way mismatch:**

| Location | fmax value |
|----------|-----------|
| Module constant `WINTER_FMAX` | 16 Hz |
| `winter_residual_analysis()` function default | 16 Hz |
| `apply_adaptive_winter_filter()` function default | **20 Hz** |
| Runtime (NB04, config-driven) | **20 Hz** |
| METHODS_DOCUMENTATION.md | 16 Hz |

**Module constant `WINTER_FMAX = 16` is dead.** Grep of `filtering.py` confirms it is defined once (line 99) and never referenced again anywhere in the file. The runtime call chain is:
```
config_v1.yaml: winter_fmax: 20.0
    → NB04: apply_signal_cleaning_pipeline(..., winter_fmax=FILTER_CONFIG.get('winter_fmax', 20.0))
    → apply_signal_cleaning_pipeline: apply_adaptive_winter_filter(..., fmax=winter_fmax)   ← 20.0
    → apply_adaptive_winter_filter: winter_residual_analysis(..., fmax=int(fmax))           ← 20
```

**Consequence:** All 16 recordings were processed with `fmax=20 Hz` in the Winter residual analysis, not 16 Hz. The Winter algorithm searched for the RMS knee point across `[1, 20]` Hz. This is a wider search range than documented and may have produced higher adaptive cutoffs than intended for some markers. The `winter_residual_analysis()` docstring even says `"16Hz for Gaga"` — but at runtime it receives 20.

**Step 07 implication:** Negligible — Step 07 does not re-filter. However, the true frequency content of the step_04 filtered positions may extend to 20 Hz (not 16 Hz) for high-dynamic markers. This is consistent with the SPARC cap being set at the SavGol effective cutoff (~2.3 Hz), not the Winter fmax.

---

### Finding P2-F4 — DISCREPANCY (LOW): Stage 1 `velocity_limit` Function Default Inconsistent with Config

**Location:** `src/filtering.py`, `detect_artifact_gaps()` line ~680 and `apply_signal_cleaning_pipeline()` line ~870.

**Mismatch:**
- `detect_artifact_gaps(signal, fs, velocity_limit: float = 1800.0, ...)` — function default: **1800.0**
- `apply_signal_cleaning_pipeline(..., velocity_limit: float = 1800.0, ...)` — function default: **1800.0**
- Config value (`config_v1.yaml`): `velocity_limit: 5000.0`
- NB04 runtime call: `velocity_limit=FILTER_CONFIG.get('velocity_limit', 5000.0)` → **5000.0** ✓

The 1800.0 mm/s default is 2.8× below the intended 5000.0 mm/s threshold. Any notebook or script that calls `apply_signal_cleaning_pipeline()` without explicitly passing `velocity_limit` would silently apply a much stricter artifact gate, potentially masking valid fast movements as artifacts. At runtime, NB04 always passes the config value explicitly, so current data is correct.

**Step 07 implication:** Step 07 does not call `apply_signal_cleaning_pipeline()`. No direct impact. However, the misleading default is a technical debt item.

---

### Finding P2-F5 — MATCH: Stage 1 `zscore_threshold` ✓

`detect_artifact_gaps()` default: `5.0`; config value: `5.0`; NB04 confirmed: `"zscore_threshold: 5.0 σ"`. Full match across default, config, and runtime.

---

### Pass 2 Step 07 Implications

| Finding | Step 07 Impact | Action Required |
|---------|---------------|-----------------|
| P2-F1 (filtfilt) | Zero-phase filtering confirmed — no phase artifacts in position data going into SavGol derivative | None |
| P2-F2 (per-region floors) | Actual filter cutoffs are adaptive (session-dependent), not fixed. SPARC cap is set by SavGol (~2.3 Hz), so Winter fmax range does not affect SPARC. | Correct documentation label from "fixed" to "adaptive floor" |
| P2-F3 (Winter fmax dead constant) | All 16 parquets filtered with fmax=20 Hz. Consistent across all recordings. No action for Step 07. | Flag dead constant in audit; no Step 07 code impact |
| P2-F4 (velocity_limit default mismatch) | No impact — Step 07 reads parquet, does not call filtering functions | Flag as technical debt; add note to Step 07 warning about `enforce_cleaning` |
| P2-F5 (zscore MATCH) | None | None |

---

### `step_06.enforce_cleaning` Warning — Required Step 07 Deliverable

Per explicit user instruction (Audit Pass 2 brief): **Step 07 code must emit a warning when `step_06.enforce_cleaning = True`.**

The rationale: Finding F2 (Audit Pass 1) established that when `ENFORCE_CLEANING=True`, `apply_surgical_repair()` in `kinematic_repair.py` updates `lin_vel_rel_x/y/z` components but does NOT recompute `lin_vel_rel_mag`. This makes the magnitude column stale for any repaired segment.

**Requirement for `src/pulsicity.py` (Step 07 output module):**
```
# On startup / per-recording, read config:
enforce_cleaning = cfg.get('step_06', {}).get('enforce_cleaning', False)
if enforce_cleaning:
    logger.warning(
        "[PROVENANCE WARNING] step_06.enforce_cleaning=True: "
        "lin_vel_rel_mag may be stale for surgically repaired segments. "
        "Repaired segments have updated lin_vel_rel_x/y/z components but "
        "lin_vel_rel_mag was NOT recomputed after repair. "
        "Manual verification recommended before interpreting pulsicity metrics."
    )
```

This requirement is now formally documented in the audit record. It must appear in the Step 07 Unified Config section and in the notebook Section 0 (provenance checks).

---

*Audit Pass 2 complete. Two findings MATCH, two DISCREPANCY (MEDIUM — per-region semantics and dead fmax constant), one DISCREPANCY (LOW — function default mismatch), one UNDOCUMENTED (dead constant). No Step 07 blocking issues. enforce_cleaning warning requirement formally recorded.*

---

## Section 7 — Audit Pass 3: Artifact Detection & Config Aliases

**Audit Date:** 2026-02-27
**Scope:** MAD multiplier value, binary dilation extent, `MOTION_THR_STD` alias role
**Primary Sources Examined:**
- `src/artifacts.py` (full read)
- `src/pipeline_config.py` (full read)
- `src/reference.py` (lines 37–122 — `detect_static_reference()`)
- `src/calibration.py` (previously read in Pass 1)

### Pass 3 Master Discrepancy Table

| # | Feature / Logic | Documented Standard | Actual Code Implementation | Status | Risk |
|---|----------------|--------------------|-----------------------------|--------|------|
| 21 | **MAD multiplier** | 6× median absolute deviation | `detect_velocity_artifacts(velocity, mad_multiplier=6.0, ...)` — `src/artifacts.py` line 13, default confirmed; `apply_artifact_truncation()` passes `mad_multiplier=6.0` | **MATCH** | LOW |
| 22 | **Binary dilation extent** | ±1 frame | `expand_artifact_mask(artifact_mask, dilation_frames=1)` — `src/artifacts.py` line 39; `structure = np.ones(2 * 1 + 1)` → 3-element kernel; applied per-axis then OR-combined | **MATCH** | LOW |
| 23 | **`MOTION_THR_STD` role in static window selection** | "Not used in `calibration.find_stable_window()`" (Audit Pass 1 finding) | Confirmed absent from `src/calibration.py::find_stable_window()`. However, `MOTION_THR_STD` IS consumed by a **different function**: `src/reference.py::detect_static_reference()` uses it as a selection gate (`std_m < thr_std`). These are distinct code paths — see P3-F3 below. | **CONFIRMED** *(see nuance below)* | LOW |

---

### Finding P3-F1 — MATCH: MAD Multiplier Exactly 6.0 ✓

**Location:** `src/artifacts.py`, line 13.

```python
def detect_velocity_artifacts(velocity, mad_multiplier=6.0, sigma_floor=1e-6):
    sigma = median_abs_deviation(velocity, axis=0, scale='normal')  # std-equivalent scaling
    sigma = np.maximum(sigma, sigma_floor)
    artifact_mask = np.abs(velocity) > (mad_multiplier * sigma[np.newaxis, :])
    return artifact_mask
```

Default is `6.0` exactly. `median_abs_deviation(..., scale='normal')` normalizes MAD to be consistent with Gaussian σ (multiply by 1/Φ⁻¹(0.75) ≈ 1.4826). Therefore the effective threshold is `6.0 × 1.4826 × raw_MAD ≈ 8.9 × raw_MAD` — but the documented threshold is stated as 6× MAD (scale='normal'), which is the convention used throughout.

**Step 07 implication:** None. Step 07 reads `is_artifact` from the parquet; it does not call `detect_velocity_artifacts()`.

---

### Finding P3-F2 — MATCH: Binary Dilation Exactly ±1 Frame ✓

**Location:** `src/artifacts.py`, lines 39–61.

```python
def expand_artifact_mask(artifact_mask, dilation_frames=1):
    structure = np.ones(2 * dilation_frames + 1)    # → np.ones(3) at default
    expanded_mask = np.zeros_like(artifact_mask, dtype=bool)
    for axis in range(artifact_mask.shape[1]):
        expanded_mask[:, axis] = binary_dilation(artifact_mask[:, axis], structure=structure)
    return np.any(expanded_mask, axis=1)
```

A 3-element structuring element `[1, 1, 1]` centered on each True frame expands the mask by exactly 1 frame in each direction (±1). Dilation is applied independently per axis then OR-combined into a 1D mask — so if any axis triggers at frame t, frames t-1 and t+1 are also masked.

**Step 07 implication:** None. Dilation is already baked into `is_artifact` in the parquet.

---

### Finding P3-F3 — CONFIRMED (with critical nuance): `MOTION_THR_STD` Has No Role in `calibration.find_stable_window()`, but IS Active in `reference.py::detect_static_reference()`

**Background:** Pass 1 of this audit established that `calibration.find_stable_window()` (called by NB05) uses position-variance minimization and that `MOTION_THR_STD` plays no role in its selection logic. The pending audit item was to **confirm** this against `pipeline_config.py`.

**Pass 3 confirmation of calibration.find_stable_window():** ✓

`src/calibration.py::find_stable_window()` contains no reference to `MOTION_THR_STD` — grep returns zero matches. The function's selection criterion is: `score = Σ var(position_window_per_axis)` — pure position variance minimization. The `MOTION_THR_STD` alias is created by `pipeline_config.py` (line 39, line 82) and loaded into `CONFIG`, but it is **not read by `find_stable_window()`**.

**New finding — `MOTION_THR_STD` IS active in a different function:**

`src/reference.py::detect_static_reference()` (lines 37–122) uses **both** `MOTION_THR_LOW` and `MOTION_THR_STD` as **joint selection criteria**:

```python
thr_low = cfg["MOTION_THR_LOW"]   # 0.30 rad/s
thr_std = cfg["MOTION_THR_STD"]   # 0.15 rad/s

# Window acceptance criterion (line 95):
if mean_m < thr_low and std_m < thr_std:
    best = (start, end, mean_m, std_m, False, "criteria")
    break
```

This is a **mean + std joint threshold gate** — accept the first window where median angular velocity (across `joints_viz`) satisfies both conditions. If no window satisfies both, fallback to minimum-mean-motion window.

**Function identity clarification:**

| Function | File | Selection Logic | `MOTION_THR_STD` used? | Called by |
|----------|------|----------------|------------------------|-----------|
| `detect_static_reference()` | `src/reference.py` | Angular velocity mean < 0.30 AND std < 0.15 | **Yes** | Early pipeline steps (NB01/NB02) |
| `find_stable_window()` | `src/calibration.py` | Minimum sum of position variances | **No** | NB05 (Step 05) |

**Step 07 implication:** Step 07 replicates `calibration.find_stable_window()` (position-variance minimization). `MOTION_THR_STD` is correctly excluded from the Step 07 noise floor algorithm. No action required.

---

### Pass 3 Step 07 Implications

| Finding | Step 07 Impact | Action Required |
|---------|---------------|-----------------|
| P3-F1 (MAD 6.0) | No impact — artifact detection already baked into parquet `is_artifact` | None |
| P3-F2 (dilation ±1) | No impact — dilation already applied in parquet | None |
| P3-F3 (MOTION_THR_STD nuance) | Step 07 replicates `find_stable_window()` (position variance) — correctly excludes MOTION_THR_STD | None — but noise floor docstring must document which function is being replicated |

---

## Section 8 — Audit Closure & Final Summary

**All three audit passes are now complete. The audit document is closed.**

### Consolidated Findings by Status

| Status | Count | Items |
|--------|-------|-------|
| **MATCH** | 15 | #1–11, #15, #19, #21, #22 |
| **DISCREPANCY HIGH** | 1 | #13 (reference_map.json missing — reproducibility only) |
| **DISCREPANCY MEDIUM** | 3 | #12 (repair path stale magnitude — dormant), #16 (per-region floors vs fixed), #17 (Winter fmax dead constant) |
| **DISCREPANCY LOW** | 1 | #18 (velocity_limit function default 1800 vs 5000) |
| **UNDOCUMENTED** | 2 | #14 (W_LEN guard), #20 (dead WINTER_FMAX constant) |
| **CONFIRMED** | 1 | #23 (MOTION_THR_STD — no role in Step 05 path) |

### Step 07 Blocking Assessment

**No findings block Step 07 implementation.** Specifically:
- The velocity math chain is verified correct (all MATCH)
- The artifact flag correctly identifies all high-velocity/high-rotation frames
- All 16 existing parquets were processed with `ENFORCE_CLEANING=False` (surgical repair dormant)
- The missing `reference_map.json` files do not affect Step 07 (parquets already written)
- Per-region cutoffs are floors, not fixed values — SPARC cap logic is unaffected (SavGol dominates at ~2.3 Hz regardless of Winter fmax=20)
- The `velocity_limit` default mismatch does not affect Step 07 (we do not call `filtering.py`)

### Formal Step 07 Code Requirements Captured in This Audit

1. **`enforce_cleaning` provenance warning** (Section 6): `src/pulsicity.py` must emit `logger.warning` if `step_06.enforce_cleaning=True`. Must print visibly in notebook Section 1. Must write `enforce_cleaning_was_active` bool column to output Parquet.

2. **Noise floor algorithm** (Section 1.5 of STEP_07_MISSION_PLAN.md): Replicate `calibration.find_stable_window()` using **position-variance minimization** (not angular velocity thresholds). `MOTION_THR_STD` is excluded. Source: `src/calibration.py`, not `src/reference.py`.

3. **Do not modify `src/filtering.py`** (Audit Pass 2, P2-F4): The `velocity_limit` function default discrepancy (1800 vs 5000) is logged as technical debt only.

---

*Audit complete. Three passes, 23 items examined, 15 MATCH, no Step 07 blocking issues. Green light for Step 1 implementation: `src/pulsicity.py`.*
