# STEP_07_MISSION_PLAN.md
## Behavioral Metrics: Pulsicity & Flow
### Gaga Motion Analysis Pipeline — Step 07

**Status:** Finalized v3 — Step 0 Audit Complete (Pass 1 + Pass 2) — Ready for Step 1 Implementation
**Author:** Biomechanical Engineering & Python Development
**Date:** 2026-02-27
**Pipeline Branch:** `pipeline_V6.2`
**Config source:** `config/config_v1.yaml`

---

## 0. All Clarifying Questions — Resolved

| # | Question | Decision |
|---|----------|----------|
| Q1 | Noise floor method | Session-adaptive: Step 05 static window first, 5th-percentile fallback |
| Q2 | Secondary filter trigger | PSD recommends only; Butterworth application requires **explicit human approval** in notebook |
| Q3 | Artifact gap handling | Bridge-and-Discard: interpolate Search Signal across gaps; reject any peak index on an artifact frame |
| Q4 | Reporting units | `mm/s` throughout — match Step 06 master Parquet |
| Q5 | Segment scope | Primary: `LeftHand`, `RightHand`, `LeftFoot`, `RightFoot`, `Head`; code is dynamic for arbitrary segments |
| Q6 | SPARC frequency cap | Cap at SG effective cutoff (~2.3 Hz, computed dynamically from config) — not the standard 20 Hz |
| Q7 | Output format | One Parquet per recording in `derivatives/step_07_behavioral/` — matching Step 06 convention |

---

## 1. Input Constraints — Confirmed and Locked

### 1.1 Config Inheritance from `config/config_v1.yaml`

The following Step 06 parameters are inherited by Step 07 and must be **explicitly printed and logged** in the notebook before any computation begins:

| Config Key | Value | Role in Step 07 |
|------------|-------|----------------|
| `fs_target` | `120.0` Hz | Sample rate, used for all time ↔ frame conversions |
| `sg_window_sec` | `0.175` s | SavGol window (21 frames @ 120 Hz) — determines SG effective cutoff |
| `sg_polyorder` | `3` | SavGol polynomial order — combined with window to compute SPARC cap |
| `deriv_method` | `savgol` | Confirms derivative type in Step 06 — validates our non-differentiation constraint |
| `ref_search_sec` | `8.0` s | Upper bound for static window search — used in noise floor fallback logic |
| `ref_window_sec` | `1.0` s | Duration of detected static window |
| `step_06.enforce_cleaning` | `false` | **Must trigger a provenance warning in `src/pulsicity.py` if True** (see §1.6 below) |

Step 07–specific parameters (not in the existing config) will be managed via an **interactive override block** in the Jupyter notebook (Section 5.2).

### 1.2 The SG Effective Cutoff — Computed Dynamically

The SPARC frequency cap and PSD diagnostic reference frequency are derived from config, not hardcoded:

```
W_LEN   = round(sg_window_sec × fs_target) → 21 frames   (forced odd, min 5)
SG effective cutoff (f_eff) ≈ documented as ~2.3 Hz in METHODS_DOCUMENTATION.md
    [verified against: sg_window_sec=0.175s, sg_polyorder=3, fs_target=120Hz]
```

The value `2.3 Hz` is the canonical figure from Section 5.2 of `docs/technical/METHODS_DOCUMENTATION.md`. Step 07 will compute it analytically via frequency-response simulation at runtime.

### 1.3 Measurement Signal

**Column:** `{segment}__lin_vel_rel_mag` (units: **mm/s**)

**Derivation chain (verified against NB06 and `src/kinematic_repair.py`):**

```
root-relative position [mm] (per axis)
  → savgol_filter(pos, W_LEN=21, polyorder=3, deriv=1, delta=1/120, mode='interp')
  → [vx, vy, vz] in mm/s
  → ||[vx, vy, vz]||₂  →  lin_vel_rel_mag
```

**Do not re-differentiate.** Do not apply `filtfilt` to this signal for measurement purposes.

### 1.4 Artifact Mask

**Column:** `{segment}__is_artifact` (bool)

Applied before all computations. Detection criteria:

| Criterion | Threshold |
|-----------|-----------|
| Rotation magnitude | > 140° |
| Angular velocity | > 800 deg/s |
| Linear velocity | > 3,000 mm/s |

A frame is `True` if **any** criterion is breached. Artifact frames are set to `NaN` in the Measurement Signal before the noise floor, PSD, SPARC, and peak detection steps.

### 1.5 `step_06.enforce_cleaning` Provenance Warning — Formal Code Requirement

> **Origin:** Audit Pass 1, Finding F2 (DISCREPANCY MEDIUM — `src/kinematic_repair.py`)
> **Explicit user instruction:** "ensure that the step_06.enforce_cleaning warning is added to the requirements for our final Step 07 code"

**The bug found:** `apply_surgical_repair()` in `kinematic_repair.py` updates `lin_vel_rel_x/y/z` component columns after PCHIP + SavGol repair, but does **not** recompute `lin_vel_rel_mag`. If any session was processed with `ENFORCE_CLEANING=True` and a segment was surgically repaired, the `lin_vel_rel_mag` column in that session's `kinematics_master.parquet` would reflect **pre-repair velocity components**, not the repaired ones. The magnitude column would be silently stale.

**Current exposure:** Zero — all 16 existing recordings have `ENFORCE_CLEANING=False`. The bug is dormant.

**Required implementation in `src/pulsicity.py`:**

The following logic must execute at the top of each per-recording processing call, before any metric computation:

```python
# --- Provenance Check: enforce_cleaning ---
enforce_cleaning = cfg.get('step_06', {}).get('enforce_cleaning', False)
if enforce_cleaning:
    logger.warning(
        "[PROVENANCE WARNING] step_06.enforce_cleaning=True detected. "
        "lin_vel_rel_mag may be STALE for surgically repaired segments. "
        "src/kinematic_repair.py updates lin_vel_rel_x/y/z after PCHIP repair "
        "but does NOT recompute lin_vel_rel_mag. "
        "Verify magnitude consistency for segments flagged as repaired before "
        "interpreting pulsicity metrics."
    )
```

This warning must also be:
1. **Printed visibly** in the notebook Section 1 (Config Audit Block) whenever `enforce_cleaning=True` — not just logged
2. **Stored** in the output Parquet as a `enforce_cleaning_was_active` boolean column (always written, regardless of value)

**Output schema addition** (append to §3.3 schema table):

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `enforce_cleaning_was_active` | bool | — | Value of `step_06.enforce_cleaning` at time of Step 07 processing; True means lin_vel_rel_mag provenance should be manually verified |

---

### 1.6 Step 05 Static Window — Architectural Note & Corrected Replica Algorithm

#### What exists on disk

The `derivatives/step_05_reference/{RUN_ID}__reference_summary.csv` files store **joint quaternion offsets only**. The `derivatives/` directory contains no JSON sidecars (no `validation_report.json`, no `reference_map.json`). The static window time bounds (`start_time_sec`, `time_window`) live exclusively in Python memory during Step 05 execution and are **not persisted to disk in the current pipeline**.

**Consequence:** Step 07 must reconstruct the static baseline window by re-running equivalent logic on data available in the kinematics_master.parquet.

#### Code-Audit Finding — Correction of Stated Thresholds

> **Important:** The refinement proposal referenced `motion_thr_low` (0.30 rad/s) and `motion_thr_std` (0.15 rad/s) as the window *selection* criteria. Audit of `src/calibration.py` (lines 87–100) reveals this is **incorrect**. These parameters serve different roles:
>
> | Parameter | Actual Role in `find_stable_window()` | Used for selection? |
> |-----------|--------------------------------------|---------------------|
> | `motion_thr_low: 0.3` | Normalizer in `ref_quality_score = 1.0 - (mean_motion / motion_thr_low)` | **No** — quality index only |
> | `motion_thr_std: 0.15` | Not present in `find_stable_window()` at all | **No** |
> | `reference_variance_threshold: 100.0` | Confidence flag: `ref_is_fallback = min_score > threshold` | Yes — confidence only |
>
> The **actual selection criterion** is: **minimum sum of position variances** (Σ var across all axis columns for Hips, LeftHand, RightHand) across the sliding window search. Window selection uses no angular velocity threshold.

#### Correct 1:1 Replica of Step 05 Selection Logic

The Step 07 noise floor algorithm must replicate this position-variance minimization using the root-relative position columns available in `kinematics_master.parquet`:

```
ALGORITHM: compute_noise_floor(df, segment, cfg)

Config parameters read:
  search_sec   = cfg["ref_search_sec"]        # 8.0 s → 960 frames
  window_sec   = cfg["ref_window_sec"]         # 1.0 s → 120 frames
  step_sec     = cfg["static_search_step_sec"] # 0.1 s → 12 frames
  var_thresh   = cfg["reference_variance_threshold"]  # 100.0
  fs           = cfg["fs_target"]              # 120.0

Step 1 — Position variance sliding window (mirrors calibration.find_stable_window):
  position_cols = [{segment}__lin_rel_px, __lin_rel_py, __lin_rel_pz]
                  [Hips cols excluded: root-relative Hips position is always ~0]
                  Use the target segment's own position cols instead.

  min_variance = ∞;  best_start = 0
  For start_frame in range(0, search_frames - window_frames, step_frames):
      window = df.iloc[start_frame : start_frame + window_frames]
      score  = Σ window[col].var()  for col in position_cols
      If score < min_variance:
          min_variance = score
          best_start   = start_frame

  ref_is_fallback = (min_variance > var_thresh)   # LOW confidence flag

Step 2 — Extract noise floor from static window:
  static_v = lin_vel_rel_mag[best_start : best_start + window_frames]
  static_v = static_v[ ~is_artifact[best_start : best_start + window_frames] ]

  If mean(static_v) < static_baseline_guard [default 50 mm/s]:
      V      = mean(static_v) + 2 × std(static_v)
      source = "step05_position_variance_replica"
      if ref_is_fallback: source += "_LOW_CONFIDENCE"
  Else:
      V      = percentile(v_clean_session, 5)
      source = "5th_percentile_fallback"

Step 3 — Guard:
  V = max(V, V_floor)   [V_floor = cfg.get("noise_floor_guard_mms", 1.0)]

Step 4 — Log: V, source, best_start timing, min_variance, ref_is_fallback
```

**Rationale for using target segment's own position columns:** In `kinematics_master.parquet`, all positions are root-relative (Hips subtracted). The Hips segment position is identically zero — it cannot contribute to variance. Step 07 therefore computes variance over the target segment's own `px/py/pz` columns, which measures that segment's positional stability during the candidate static window. This is a valid and consistent adaptation of the original multi-joint variance logic.

**Both source values must be logged per segment per session.** The `ref_is_fallback` flag propagates to the output schema as `noise_floor_low_confidence`.

---

## 2. Algorithm Architecture

### Step 0 — Kinematic Integrity Audit

**Objective:** Verify that the actual `/src` code matches the mathematical documentation. Produce a Discrepancy Table. This is a **read-only audit** — no code is modified.

**Audit targets:**

| File | What to Verify |
|------|---------------|
| `notebooks/06_ultimate_kinematics.ipynb` | SavGol params (`W_LEN`, `polyorder`, `dt`), Euclidean norm cell, artifact flag thresholds (140°, 800°/s, 3000 mm/s) |
| `src/kinematic_repair.py` | PCHIP repair path SavGol call — does it use the same `W_LEN` and `polyorder`? Does it re-derive `lin_vel_rel_mag`? |
| `src/filtering.py` | Per-region cutoffs: trunk 6 Hz, head/upper_prox 8 Hz, upper_distal 12 Hz, lower_prox 8 Hz, lower_distal 10 Hz |
| `src/artifacts.py` | MAD multiplier = 6×, binary dilation = ±1 frame |
| `config/config_v1.yaml` | `sg_window_sec: 0.175`, `sg_polyorder: 3`, `fs_target: 120.0` |
| `docs/technical/METHODS_DOCUMENTATION.md` | SG effective cutoff ~2.3 Hz claim (Section 5.2) |

**Deliverable:** Markdown table with columns:

```
| Module | Parameter | Documented Value | Code Value | Status | Risk |
```

Status values: `MATCH` / `DISCREPANCY` / `UNDOCUMENTED`
Risk levels: `LOW` / `MEDIUM` / `HIGH` (HIGH = would invalidate Step 07 metric validity)

---

### Step 1 — Diagnostics & Search Strategy

#### 1a. Noise Floor Threshold V

**Algorithm (per segment per session):**

```
1. Extract clean velocity:
       v_clean = lin_vel_rel_mag[ ~is_artifact ]

2. Search for static baseline window:
       For w in stride(0, ref_search_sec, step=static_search_step_sec):
           candidate = v_clean[ w : w + ref_window_sec ]
           record mean(candidate)
       Select w_min = window with minimum mean velocity

3. Compute noise floor:
       If mean(v_clean[w_min]) < 50 mm/s:        # Static pose confirmed
           V = mean(v_clean[w_min]) + 2 × std(v_clean[w_min])
           source = "step05_static_window"
       Else:                                       # No static pose found
           V = percentile(v_clean, 5)
           source = "5th_percentile_fallback"

4. Guard: V = max(V, 1.0)   # Absolute floor — never zero
5. Log: V, source, w_min timing, static_mean
```

Units: mm/s. The guard ensures numerical stability (prevents division-related edge cases in PPM).

#### 1b. PSD Diagnostic

**Method:** Welch's PSD via `scipy.signal.welch`

**Parameters (computed from config):**
- `fs = fs_target = 120.0` Hz
- `nperseg = min(512, len(v_clean) // 4)` — adaptive to recording length
- `window = 'hann'`
- `noverlap = nperseg // 2`

**Noise ratio metric:**

```
band_signal = integral of PSD from 0.5 Hz to f_eff    (SG effective cutoff)
band_noise  = integral of PSD from f_eff to 10 Hz
noise_ratio = band_noise / band_signal
```

**Recommendation logic (output only — no automatic filtering):**

| `noise_ratio` | PSD Recommendation |
|---------------|--------------------|
| < 0.05 | No secondary filter needed |
| 0.05 – 0.15 | Filter may improve peak localization (marginal) |
| > 0.15 | Secondary Butterworth filter recommended |

This recommendation is printed in the notebook. **No filter is applied without explicit human confirmation** (see Section 5.2).

#### 1c. SPARC

SPARC is an **output metric** — computed unconditionally for every session, for every target segment.

**Mathematical definition:**

Given the clean velocity signal $v(t)$ (artifact frames set to NaN, then interpolated across gaps for spectral continuity):

$$\hat{V}(f) = \frac{|\mathcal{F}[v](f)|}{|\mathcal{F}[v](0)|}$$

$$\text{SPARC} = -\int_0^{f_\text{cap}} \sqrt{\left(\frac{1}{f_\text{cap}}\right)^2 + \left(\frac{d\hat{V}}{df}\right)^2} \, df$$

**Frequency cap:** $f_\text{cap} = f_\text{eff}$ (the SG effective cutoff, ~2.3 Hz, computed dynamically).

**Rationale for cap:** Since `lin_vel_rel_mag` was derived using a SavGol filter with effective cutoff ~2.3 Hz, all spectral content above this frequency is attenuated SG filter rolloff — not genuine movement. Integrating beyond $f_\text{eff}$ would measure the filter's own frequency response, not the dancer's movement complexity.

**Interpretation:** More negative SPARC = more fragmented/pulsive movement. A SPARC of 0 would indicate a perfectly smooth single-lobe velocity profile.

**Implementation note:** Use `scipy.fft.rfft` on the **PCHIP-interpolated** velocity signal (NaN gaps bridged — see below). Normalize the magnitude spectrum by its DC component. Compute the arc length numerically using the trapezoidal rule.

**Gap bridging strategy for SPARC — PCHIP required:**

Linear interpolation must not be used when preparing the velocity signal for SPARC. Linear bridges produce triangular waveforms at gap endpoints, which have discontinuous first derivatives. These corners inject sinc-like high-frequency energy into the spectrum, directly inflating the spectral arc length and producing an artificially negative (rough) SPARC score.

**PCHIP (Piecewise Cubic Hermite Interpolating Polynomial) must be used instead.** PCHIP:
- Produces $C^1$ curves (continuous first derivative at all points, including gap endpoints)
- Preserves local monotonicity — no overshoot or ringing artifacts
- Is already the standard for gap bridging in this pipeline (Step 02 preprocessing, `src/kinematic_repair.py`)

PCHIP bridges are used **only for the SPARC spectral computation** — not for the Measurement Signal or the peak detection Search Signal. Any peak that falls within a bridged gap region is still discarded per the Bridge-and-Discard protocol (Section 2.1).

---

### Step 2 — Unified Peak Detection Engine (Split-Signal Search)

#### 2.1 Signal Architecture

| Signal | Source | Role |
|--------|--------|------|
| **Measurement Signal** $v_m(t)$ | `lin_vel_rel_mag`, artifact frames → NaN | Ground truth magnitude |
| **Search Signal** $v_s(t)$ | $v_m$ with artifact gaps linearly interpolated, then optionally Butterworth-smoothed | Peak index localization only |

**Bridge-and-Discard Protocol:**
1. Identify contiguous artifact spans: runs of `is_artifact == True`
2. For the Search Signal: linearly interpolate across artifact spans ≤ max gap of `max_gap_pos_sec = 1.0 s` (from config). Longer spans are left as NaN.
3. Run `find_peaks` on $v_s(t)$, obtaining candidate peak indices $\{t_k\}$
4. **Discard** any $t_k$ where `is_artifact[t_k] == True`
5. **Discard** any $t_k$ where `v_m[t_k]` is NaN (landed inside a bridged gap)
6. Report $v_m(t_k)$ as the peak magnitude — never the Search Signal value

#### 2.2 Optional Secondary Butterworth (Human-Gated)

If the researcher approves the filter recommendation (Section 5.2):

```
sos = scipy.signal.butter(N=2, Wn=cutoff/(fs/2), btype='low', output='sos')
v_s_filtered = scipy.signal.sosfiltfilt(sos, v_s_interpolated)
```

where `cutoff` is an interactive parameter (default 1.0 Hz, range 0.5–2.0 Hz).

**This filtered signal replaces $v_s$ for peak localization only.** The Measurement Signal $v_m$ is never modified.

#### 2.3 Physiological Constraints

Applied via `scipy.signal.find_peaks`:

**Prominence:**

$$p > 0.5 \cdot \sigma_v$$

where $\sigma_v = \text{std}(v_m[\text{non-artifact frames}])$ — computed once per segment per session before peak detection. Units: mm/s.

**Minimum inter-peak distance:**

$$d > 100 \text{ ms} = 12 \text{ frames} \quad @ 120 \text{ Hz}$$

`find_peaks` parameter: `distance=12` (integer, samples).

**Minimum height above noise floor (optional, interactive):**

$$v_m(t_k) > V$$

Can be toggled in the notebook UI (default: enabled).

**Parameter summary passed to `find_peaks`:**

```python
find_peaks(
    v_s,
    prominence = 0.5 * sigma_v,    # adaptive to session
    distance   = 12,                # 100 ms at 120 Hz
    height     = V                  # noise floor (optional)
)
```

---

### Step 3 — Aggregation & Normalization

#### 3.1 Metric Definitions (Locked)

**Active time:**

$$T_a = \frac{1}{f_s} \cdot \#\{t : v_m(t) > V \text{ and } \neg \text{artifact}(t)\}$$

**Peaks Per Minute:**

$$\text{PPM} = \frac{N_p}{T_a} \times 60 \qquad [N_p = \text{total detected peaks}]$$

**Mean Peak Velocity:**

$$\bar{v}_p = \frac{1}{N_p} \sum_{k=1}^{N_p} v_m(t_k) \qquad [\text{mm/s}]$$

**IPI Coefficient of Variation:**

$$\text{IPI}_k = t_{k+1} - t_k \quad [s] \qquad \text{CV}_{\text{IPI}} = \frac{\sigma_{\text{IPI}}}{\mu_{\text{IPI}}}$$

$\text{CV}_\text{IPI}$ is dimensionless. High CV indicates arrhythmic/fragmented movement; CV near 0 indicates metronomic regularity.

**SPARC:** Computed per Section 1c. Dimensionless, negative-valued.

#### 3.2 Edge Case Guards & Statistical Validity Flag

| Condition | Handling |
|-----------|---------|
| $N_p = 0$ | PPM = 0, $\bar{v}_p$ = NaN, CV_IPI = NaN — recorded with `peak_count_zero = True` flag |
| $N_p = 1$ | PPM computed, CV_IPI = NaN (undefined for single interval) |
| $T_a = 0$ | PPM = NaN — segment was entirely below noise floor or all artifact |
| Segment missing from parquet | Skip with warning; logged in output metadata |
| $T_a < \text{min\_run\_seconds}$ | `valid_movement_flag = False` — metrics are computed but flagged as statistically unreliable |

**`valid_movement_flag` — Definition and Rationale:**

$$\text{valid\_movement\_flag} = \begin{cases} \text{True} & \text{if } T_a \geq \text{min\_run\_seconds} \\ \text{False} & \text{if } T_a < \text{min\_run\_seconds} \end{cases}$$

**Threshold source:** `min_run_seconds: 5.0` from `config/config_v1.yaml`. This is the same threshold already used as the pipeline-wide minimum viable recording length. Applying it to $T_a$ (active time per segment) ensures consistency: a segment that was in motion for fewer than 5 seconds does not provide a statistically meaningful basis for PPM, IPI CV, or SPARC estimation. The threshold is **read from config**, not hardcoded, ensuring it propagates consistently if the config value changes.

**Disambiguation — "zero peaks" is ambiguous without this flag:**
- A fluid performer may produce 0 peaks in a specific segment (e.g., a slow continuous arm arc never forms a velocity peak above the prominence threshold). This is a **valid result** and `valid_movement_flag = True`.
- A segment that was stationary (e.g., the subject kept one foot planted) may also produce 0 peaks but with $T_a < 5$ s. This is a **non-session** and `valid_movement_flag = False`.

The flag enables downstream R/SPSS analysis to `filter(valid_movement_flag == TRUE)` without manual per-recording data cleaning.

#### 3.3 Output Schema

**File:** `derivatives/step_07_behavioral/{RUN_ID}__pulsicity_metrics.parquet`

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `run_id` | str | — | Recording identifier |
| `segment` | str | — | Body segment name |
| `noise_floor_V_mms` | float64 | mm/s | Adaptive noise floor threshold |
| `noise_floor_source` | str | — | `"step05_static_window"` or `"5th_percentile_fallback"` |
| `active_time_s` | float64 | s | Total duration above noise floor (excl. artifacts) |
| `n_peaks` | int64 | count | Total detected peaks |
| `ppm` | float64 | peaks/min | Peaks per minute |
| `mean_peak_velocity_mms` | float64 | mm/s | Mean peak speed |
| `ipi_mean_s` | float64 | s | Mean inter-peak interval |
| `ipi_std_s` | float64 | s | IPI standard deviation |
| `ipi_cv` | float64 | — | IPI coefficient of variation |
| `sparc` | float64 | — | Spectral Arc Length (≤ 0) |
| `sparc_freq_cap_hz` | float64 | Hz | SG effective cutoff used for SPARC |
| `psd_noise_ratio` | float64 | — | Noise-to-signal ratio from PSD diagnostic |
| `psd_filter_recommended` | bool | — | True if noise_ratio > 0.15 |
| `secondary_filter_applied` | bool | — | True if researcher approved Butterworth |
| `secondary_filter_cutoff_hz` | float64 | Hz | Cutoff if filter applied, else NaN |
| `valid_movement_flag` | bool | — | False if T_a < min_run_seconds (5.0 s from config); use to filter non-sessions in batch analysis |
| `noise_floor_low_confidence` | bool | — | True if static window variance exceeded reference_variance_threshold (100.0); inherited from Step 05 replica logic |
| `artifact_frames_pct` | float64 | % | Fraction of frames masked |
| `prominence_threshold_mms` | float64 | mm/s | Actual prominence value used |
| `min_distance_frames` | int64 | frames | Distance constraint used |
| `sg_window_sec` | float64 | s | Inherited from config |
| `sg_polyorder` | int64 | — | Inherited from config |
| `fs_target_hz` | float64 | Hz | Inherited from config |
| `processing_timestamp` | str | — | ISO 8601 |
| `pipeline_version` | str | — | Git branch/tag |

---

### Step 4 — Command Center Notebook (`notebooks/07_pulsicity_flow.ipynb`)

#### 5.1 Structure

The notebook is the **primary validation interface** — decisions are made here, not just wrapped. It is organized into five numbered sections:

**Section 1 — Config Audit Block**

Before any computation, print the inherited Step 06 parameters in a formatted table:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 07 — CONFIG INHERITANCE AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  fs_target       : 120.0 Hz        [config/config_v1.yaml]
  sg_window_sec   : 0.175 s  → 21 frames
  sg_polyorder    : 3
  sg_eff_cutoff   : ~2.3 Hz  (computed from window+polyorder)
  deriv_method    : savgol
  ref_search_sec  : 8.0 s
  ref_window_sec  : 1.0 s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Target segments : LeftHand, RightHand, LeftFoot, RightFoot, Head
  Input parquets  : derivatives/step_06_kinematics/  [N recordings found]
  Output dir      : derivatives/step_07_behavioral/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Section 2 — Step 07 Interactive Parameter Overrides**

An `ipywidgets` panel exposing only Step 07–specific parameters. These are not in `config_v1.yaml` and are set here:

| Widget | Type | Default | Range | Parameter |
|--------|------|---------|-------|-----------|
| Noise floor guard | FloatSlider | 1.0 mm/s | 0–50 | Minimum V |
| Prominence multiplier | FloatSlider | 0.5 | 0.1–2.0 | Multiplier on σ |
| Min distance | IntSlider | 100 ms | 50–500 | IPI floor |
| Static baseline guard | FloatSlider | 50 mm/s | 0–200 | Max mean velocity to accept Step 05 window |
| Segment selector | MultiSelect | 5 defaults | all available | Which segments to process |

**Section 3 — Diagnostics Panel (per segment)**

For each selected segment and recording:
- **PSD plot:** Power spectral density with vertical line at `f_eff`, noise ratio printed
- **Recommendation banner:** Green (`No filter needed`) / Yellow (`Filter marginal`) / Red (`Filter recommended`)
- **Noise floor summary:** V value, source, static window timing

**Section 4 — Human-Triggered Filter Gate** *(Only rendered if any segment has `psd_filter_recommended = True`)*

```
┌──────────────────────────────────────────────────────────┐
│ ⚠  PSD DIAGNOSTIC: Secondary filter recommended          │
│    Segment: RightHand   Noise ratio: 0.23                 │
│                                                           │
│  Apply secondary Butterworth filter to Search Signal?     │
│  [  Cutoff: ──●── 1.0 Hz  ]   [ YES, APPLY ]  [ SKIP ]  │
└──────────────────────────────────────────────────────────┘
```

The `find_peaks` call **will not execute** until the researcher makes a choice. A boolean flag `apply_secondary_filter` is set by the widget — the cell containing `find_peaks` reads this flag before proceeding.

**Section 5 — Windowed Visual Audit**

For each segment, a signal inspector with:
- `start_time` slider (seconds)
- `window_duration` slider (default 10 s, range 2–60 s)
- Velocity trace plot with:
  - Measurement Signal $v_m(t)$ in blue
  - Search Signal $v_s(t)$ in orange (if different from $v_m$)
  - Detected peaks as red inverted triangles
  - Artifact regions shaded in grey
  - Noise floor V as horizontal dashed line

The researcher can pan through the full recording, zoom into suspicious peaks, and flag manual overrides (see Section 5.6).

**Section 6 — Batch Output Table**

A `pandas` styled table showing all segments × all recordings, with columns: `segment`, `PPM`, `mean_peak_velocity_mms`, `ipi_cv`, `sparc`, `artifact_frames_pct`. Sortable by any column. Includes a "WRITE PARQUETS" button that triggers the final batch output.

**Section 7 — Manual Validation Sidecar**

The researcher can flag individual peaks as false positives or false negatives via an annotation cell. These are written to `derivatives/step_07_behavioral/{RUN_ID}__pulsicity_validation.json` as a reproducibility audit trail.

---

## 3. Execution Roadmap

| Step | Task | Module / File | Dependencies |
|------|------|---------------|--------------|
| **0** | Kinematic Integrity Audit | Read-only audit notebook | None |
| **1a** | Noise floor function `compute_noise_floor()` | `src/pulsicity.py` | Step 0 complete |
| **1b** | PSD diagnostic `compute_psd_diagnostic()` | `src/pulsicity.py` | Step 0 complete |
| **1c** | SPARC metric `compute_sparc()` | `src/pulsicity.py` | Step 0 complete |
| **2** | Peak detection `detect_velocity_peaks()` | `src/pulsicity.py` | Steps 1a–1c |
| **3** | Aggregation `aggregate_pulsicity_metrics()` | `src/pulsicity.py` | Step 2 |
| **4** | Command Center notebook | `notebooks/07_pulsicity_flow.ipynb` | Step 3 |
| **T** | Unit tests with synthetic signals | `tests/test_pulsicity.py` | Steps 1–3 |

**Parallelism:** Steps 1a, 1b, and 1c are independent and can be implemented simultaneously once Step 0 clears.

---

## 4. File & Directory Conventions

| Path | Purpose |
|------|---------|
| `src/pulsicity.py` | All Step 07 computation functions |
| `notebooks/07_pulsicity_flow.ipynb` | Command Center UI |
| `derivatives/step_07_behavioral/` | Output Parquet files (one per recording) |
| `derivatives/step_07_behavioral/{RUN_ID}__pulsicity_metrics.parquet` | Per-recording metrics |
| `derivatives/step_07_behavioral/{RUN_ID}__pulsicity_validation.json` | Manual override sidecar |
| `tests/test_pulsicity.py` | Unit tests |
| `docs/STEP_07_MISSION_PLAN.md` | This document |

---

## 5. Pipeline Lineage Diagram

```
Step 01: Parse CSV (OptiTrack)
    ↓
Step 02: Preprocess (PCHIP gap fill, Hampel filter, MAD artifact detection)
    ↓
Step 03: Resample → 120 Hz uniform grid
    ↓
Step 04: Adaptive Winter Butterworth filter (per-region floors, not fixed cutoffs — see Audit P2-F2)
    ↓
Step 05: Reference pose detection (T-pose zeroing)
    └── Outputs:  {RUN_ID}__reference_summary.csv   [quaternion offsets only]
                  Static window time bounds NOT persisted ← architectural note
    ↓
Step 06: Ultimate Kinematics → kinematics_master.parquet
              │
              ├── {segment}__lin_vel_rel_mag    [mm/s]    ← MEASUREMENT SIGNAL
              └── {segment}__is_artifact        [bool]    ← ARTIFACT MASK
    ↓
Step 07: Pulsicity & Flow  ← THIS STEP
    │
    ├── Config Audit Block (inherits from config_v1.yaml)
    ├── Noise Floor V (session-adaptive: Step05-proxy first, 5th-pct fallback)
    ├── PSD Diagnostic (Welch, capped at f_eff)
    ├── SPARC (every session, capped at f_eff ~2.3 Hz)
    ├── Human-Gated Filter Decision (notebook widget)
    ├── Split-Signal Peak Detection (Bridge-and-Discard, prominence>0.5σ, d>12 frames)
    ├── Aggregation (PPM, mean peak velocity, IPI CV)
    └── Output → derivatives/step_07_behavioral/{RUN_ID}__pulsicity_metrics.parquet
```

---

## 6. Locked Mathematical Definitions

$$V_\text{adaptive} = \begin{cases} \mu_\text{static} + 2\sigma_\text{static} & \text{if } \mu_\text{static} < 50 \text{ mm/s} \\ \text{percentile}_5(v_\text{clean}) & \text{otherwise} \end{cases}$$

$$T_a = \frac{1}{f_s} \cdot \#\bigl\{t : v_m(t) > V \wedge \neg\text{artifact}(t)\bigr\}$$

$$\text{PPM} = \frac{N_p}{T_a} \times 60$$

$$\bar{v}_p = \frac{1}{N_p}\sum_{k=1}^{N_p} v_m(t_k) \qquad [\text{mm/s}]$$

$$\text{CV}_\text{IPI} = \frac{\sigma_\text{IPI}}{\mu_\text{IPI}}$$

$$\text{Prominence constraint:} \quad p_k > 0.5 \cdot \sigma_v$$

$$\text{Distance constraint:} \quad |t_{k+1} - t_k| > 0.1 \text{ s} \equiv 12 \text{ frames at 120 Hz}$$

$$\text{SPARC} = -\int_0^{f_\text{eff}} \sqrt{\frac{1}{f_\text{eff}^2} + \left(\frac{d\hat{V}}{df}\right)^2} \, df \qquad \hat{V}(f) = \frac{|\mathcal{F}[v](f)|}{|\mathcal{F}[v](0)|}$$

---

---

## 7. Technical Refinements Applied (v2)

| # | Refinement | Status | Key Finding |
|---|-----------|--------|-------------|
| R1 | Noise Floor Consistency | **Applied with correction** | `motion_thr_low`/`motion_thr_std` are quality metrics, not selection criteria. Correct replica uses position-variance minimization matching `calibration.find_stable_window()` lines 87–100. Threshold is `reference_variance_threshold: 100.0`. |
| R2 | SPARC PCHIP bridging | **Applied** | Linear interpolation rejected for SPARC signal preparation due to spectral leakage from gap-endpoint corners. PCHIP required (C¹ continuity, pipeline-consistent). Search Signal and Measurement Signal unaffected. |
| R3 | `valid_movement_flag` | **Applied** | Threshold bound to `min_run_seconds: 5.0` from config — not hardcoded. Disambiguates "zero peaks from fluid movement" vs "non-session (segment stationary)". |

---

*All clarifying questions and technical refinements resolved. No open decisions remain.*
*Step 0 Audit (Pass 1 + Pass 2) complete — see `docs/STEP_0_AUDIT_REPORT.md`. Ready to proceed to Step 1: implementation of `src/pulsicity.py`.*
