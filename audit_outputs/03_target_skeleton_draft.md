# 03 Target Skeleton Draft

**Phase:** 3
**Date:** 2026-05-14
**Agent:** Claude Sonnet 4.6 — Audit Mode (Design-only)
**Mode:** No code changes. Design decisions only.
**Governing document:** `GAGA_PIPELINE_AGENT_WORK_PLAN.md` §Phase 3
**Evidence base:** Phases 0–2 audit outputs, `PIPELINE_PROCESSING_README.md`, `KINEMATIC_FEATURES_README.md`, `METHODOLOGY_SPEC_v2.md` (v3.0)

---

## Preamble: Four Mandatory Architectural Filters

The user mandated four cross-cutting filters that override the default "keep-if-working" principle for this phase. Every stage design must explicitly address each filter.

| Filter | Mandate |
|--------|---------|
| **F-LOG** | Logical Foundation Check — challenge velocity extraction and artifact detection logic; propose more robust approach if current one leans on weak data points |
| **F-MIN** | Filter Minimalism — identify redundant or over-aggressive filters; bring data as close to Ground Truth as possible |
| **F-ADP** | Adaptive Pipeline (Q6) — automatic per-joint adaptive filter: if Dance Band (1–13 Hz) attenuation > -3 dB, self-correct |
| **F-QC7** | Bone QC Policy (Q7) — implement Warning & Flagging policy for CV > 5% |

Legacy components C2 (`core_kinematics_engine.py`) and C4 (`EDA_PCA.py`) remain archived in `legacy/`. They are excluded from all target skeleton stages.

---

## 1. Design principles

These principles govern all stage design decisions in this skeleton.

1. **Ground Truth Proximity (F-MIN):** The goal of preprocessing is to *remove artifacts*, not to smooth the signal. Every filter stage must be able to justify its modification rate. The ideal pipeline leaves the data as close to the physical ground truth as possible with the minimal number of interventions.

2. **Detect Once, Repair Once:** Artifact detection across multiple pipeline stages for the same artifact class introduces compounding error. Where two stages address the same problem, one should be primary and the other should act as a safety net — and this should be explicitly documented and logged.

3. **Self-Calibrating Where Possible (F-ADP):** Adaptive stages must validate their own output against domain-specific spectral requirements and self-correct rather than silently over-processing.

4. **Provenance is a First-Class Output:** Every modification to the data (gap-fill, artifact repair, filtering) must be logged quantitatively (counts, rates, parameter values) in the associated metadata artifact for that step. Not for debugging — for thesis-grade reproducibility.

5. **Hard Stops Must Be Earning Their Keep:** A QC gate that stops processing is justified only if continued processing would produce scientifically misleading results. Low bone length CV does not corrupt kinematics; it should warn and flag, not stop.

6. **Config Snapshot is Mandatory:** The live `config_v1.yaml` must be snapshotted per run before any field is overwritten. (Addresses C8 / R-08a.)

7. **Minimalist Engineering:** If the current implementation of a stage is correct and producing valid outputs, the decision is `KEEP_AS_IS`. The PSD oversmoothing flag does not mean the three-stage filter is wrong — it means the cutoff selection feedback loop needs one additional check.

---

## 2. Proposed layers

The system has three logical layers. This skeleton defines the target state for each.

### Layer A — Motion Processing Pipeline (Steps 01–06, 08)
**Responsibility:** Transform raw CSV → `kinematics_master.parquet`.
**Current state:** Functional. One confirmed quality risk (PSD oversmoothing). One display bug. One reproducibility gap.
**Target:** Functionally equivalent pipeline with adaptive filter correction loop, bone QC provenance tagging, and config snapshotting.

### Layer B — Canonical Master Dataset (`kinematics_master.parquet`)
**Responsibility:** Provide a stable, thesis-grade analytical dataset.
**Current state:** Categories A–F correctly populated. NaN Guard PASS. Continuity PASS.
**Target:** Add `{joint}__bone_qc_flag` column (new Category F member) for joints with CV > 5% bone length instability. All other columns unchanged.

### Layer C — Downstream Research Features (NB11)
**Responsibility:** Extract F1–F5 from `kinematics_master.parquet` for thesis analysis.
**Current state:** Correct. P2 filter explicit. T1-anchor PCA correctly applied.
**Target:** KEEP_AS_IS. Add `bone_qc_fail_flag` sensitivity check before PCA fit.

---

## 3. Proposed stages

### Stage summary table

| Stage | Target responsibility | Decision | Priority |
|-------|----------------------|----------|---------|
| S-00 | Config load + per-run snapshot | `LOCAL_REFACTOR` | High |
| S-01 | Parse OptiTrack CSV | `KEEP_AS_IS` | — |
| S-02 | Gap fill + bone QC flagging | `KEEP_LOG_QC` + `LOCAL_REFACTOR` (cosmetic) | Medium |
| S-03 | Uniform resampling | `KEEP_AS_IS` | — |
| S-04 | 3-stage filtering + adaptive dance-band correction | `REDESIGN_CANDIDATE` (Stage 3 feedback loop only) | **Critical** |
| S-05 | T-pose reference detection | `KEEP_AS_IS` | — |
| S-06 | Kinematics master computation | `KEEP_AS_IS` + minor `LOCAL_REFACTOR` (surgical repair default) | Low |
| S-08 | Engineering physical audit | `KEEP_LOG_QC` | Low |
| S-11 | v2 feature extraction (P2-only) | `KEEP_AS_IS` + `KEEP_TEST` | — |

---

## 4. Stage-by-stage target design

---

### S-00 — Setup and Config Snapshot

**Current state:** `run_pipeline.py:140` calls `update_config()` which overwrites `config_v1.yaml` in-place with `subject_id`, `subject_height_cm`, `subject_mass_kg`, and `current_csv`. Config history is lost.

**Target state:**
Before overwriting `config_v1.yaml`, write a frozen snapshot:
```
derivatives/step_00_config/{RUN_ID}__config_snapshot.yaml
```
This snapshot captures the full YAML state at the time of the run. The in-place overwrite of `config_v1.yaml` can still happen (backward-compatible), but the snapshot exists for reproducibility.

**Decision:** `LOCAL_REFACTOR`
**Scientific rationale:** Reproducibility is a thesis-grade requirement. If a parameter is changed between runs and `config_v1.yaml` is overwritten, the earlier run's configuration cannot be recovered without git archaeology. A per-run config snapshot costs ~1 KB and is free to add.
**Confidence:** High.

---

### S-01 — Parse & Load (NB01)

**Current state:** `parse_optitrack_csv()` correctly handles the two-header CSV format, maps OptiTrack names to canonical schema via `correct_motive_name()`, extracts 51 joints in mm + xyzw quaternion convention, validates time monotonicity and quaternion completeness.

**Target state:** No change.

**Decision:** `KEEP_AS_IS`
**Scientific rationale:** Stage is provably correct on reference run (51/51 joints found, 0 NaN, 0 missing). Name mapping is canonically correct (Chest→Spine1, Ab→Spine, etc., per `JOINT_NAMING_CONVENTION.md`). Duration gatekeeper (< 5s → SKIP) is appropriate.
**Confidence:** High.

---

### S-02 — Preprocessing / Gap Fill (NB02)

#### S-02.1 — Artifact masking (F-LOG architectural filter)

**Current state:** `detect_and_mask_artifacts()` computes frame-to-frame velocity as a single-frame finite difference:
```
vel[t] = diff(data[t]) / diff(time[t])
```
then applies `MAD × mad_multiplier (=3.0)` threshold. Flagged frames → NaN → gap-filled.

**Logical foundation analysis (F-LOG):**
Single-frame finite differences have a fundamental weakness: a single noisy frame at time `t` produces TWO anomalous velocity estimates (at `t-1→t` and at `t→t+1`). This causes the mask to expand to the adjacent clean frames via the `±expand_frames = 1` rule, potentially masking genuinely valid data on either side.

More critically, the Z-score threshold in this stage uses `MAD/0.6745` which assumes velocity is approximately normally distributed. For Gaga dance motion, velocity distributions are heavy-tailed (heavy concentration at low velocity with occasional high-velocity bursts during explosive movements). A Z-score threshold will incorrectly flag genuine fast bursts as artifacts.

**Target for velocity-based threshold (F-LOG):**
Replace the raw single-frame diff with a **3-frame central difference velocity estimate** before thresholding:
```
vel_est[t] = (pos[t+1] - pos[t-1]) / (2 × dt)   [central 3-point difference]
```
This is 2nd-order accurate and averages out single-frame noise before the threshold is applied. For edge frames, fall back to single-frame diff.

Retain MAD-based threshold (robust to outliers). Remove the Z-score re-check inside this function — Z-score on dance velocities is unreliable (non-normal distribution). The Z-score check is separately applied in Stage 1 of Step 04 on the uniform grid; it is redundant here.

**Decision for S-02.1:** `LOCAL_REFACTOR` (velocity estimator upgrade)
**Confidence for velocity issue:** Medium. The 1-frame diff is a known source of false positives on fast motion, but we do not yet have quantitative evidence of false-positive artifact masking in the current data. Defer implementation until Stage 4 audit (Phase 4) confirms the rate.
**[RECONSIDER_LATER]** — Q-S02: "Measure the false-positive artifact masking rate in Step 02 vs Step 04 by comparing their respective flag sets on the same sessions. If >10% of Step 02 flags are reversed by downstream processing (i.e., flagged regions show no spectral anomaly), upgrade velocity estimator to 3-point central diff."

#### S-02.2 — Bone length QC (F-QC7 architectural filter)

**Current state:**
- Computes bone length CV per joint pair using Skurowski (2021) thresholds: warn > 2%, fail > 5%.
- FAIL verdict is printed but does not affect processing — the pipeline continues unconditionally.
- Display unit bug: `mean_l * 1000` on already-mm data produces nonsensical values (~31,502 mm).

**Confirmed failures in reference run:**
- Hips→Spine: CV = 10.22% → FAIL
- Neck→Head: CV = 8.43% → FAIL

**Target state (F-QC7):**

**Warning & Flagging policy:**

| CV threshold | Action |
|---|---|
| CV > 2% (warn) | Log `WARN` to `{RUN_ID}__kinematics_map.json` under `bone_qc_warnings` list. No processing gate. |
| CV > 5% (fail) | Log `FAIL` to `{RUN_ID}__kinematics_map.json` under `bone_qc_failures` list with `{joint_pair, cv_pct, n_frames_used}`. Set `bone_qc_fail_flag: true` in metadata. **Do not stop processing.** |

**New Category F column in `kinematics_master.parquet`:** For each joint appearing in `bone_qc_failures`, add a binary flag column:
```
{joint}__bone_qc_flag    [bool, 0/1, per-frame constant = 1 for all frames]
```
This allows downstream users and NB11 to conditionally exclude or weight these joints.

**Sensitivity checkpoint in NB11:** Before the PCA anchor fit, check if the anchor session contains `bone_qc_fail_flag: true`. If yes, print a warning listing the failing joints and their CV%. Do not block the fit, but log the warning to `run_metadata.json`.

**Fix display unit bug:** Remove the `× 1000` multiplier. Bone lengths computed from mm positions should be reported directly in mm. Add a conversion to display in cm for readability: `mean_cm = mean_l / 10`.

**Decision:** `KEEP_LOG_QC` + `LOCAL_REFACTOR` (cosmetic unit fix)
**Scientific rationale:** Bone length instability above 5% CV indicates rigid body marker tracking failure (marker slippage, marker loss, or algorithm error). This degrades the accuracy of segment coordinate frame estimation and propagates into CoM position and angular velocity. It does not make the data unusable, but it must be flagged for users making quantitative claims about specific joints. The de Leva CoM model assumes rigid segments — CV > 5% violates this assumption for those segments.

**[RECONSIDER_LATER]** — Q-QC7: "Quantify the propagated uncertainty in CoM position (mm) and angular velocity magnitude (deg/s) attributable to bone length CV > 5% for the failing joints (Hips→Spine, Neck→Head) across N > 20 sessions. Hypothesis: 10% CV in Hips→Spine introduces ~50–100 mm CoM uncertainty at the pelvis. This must be quantified before thesis-grade claims about CoM trajectory are made."

---

### S-03 — Resampling (NB03)

**Current state:** CubicSpline for positions, SciPy Slerp for quaternions. Uniform 120 Hz grid. `time_grid_std = 0.0` (perfect). Well-tested and correct.

**Target state:** No change.

**Decision:** `KEEP_AS_IS`
**Scientific rationale:** True SLERP (SciPy implementation) is geometrically correct for quaternion interpolation — it traverses the geodesic arc on S³ with uniform angular speed, preserving angular velocity. CubicSpline produces C2-continuous position trajectories, essential for clean velocity and acceleration computation downstream. The single trailing frame loss (21773 → 21772) is a known and acceptable grid boundary behavior.
**Confidence:** High.

---

### S-04 — Filtering (NB04)

This is the most critical stage in the target skeleton. It contains the confirmed pipeline quality risk (PSD `REVIEW_OVERSMOOTHING`) and requires redesign of the Stage 3 feedback loop.

#### S-04.0 — Architecture review (F-MIN architectural filter)

**Three-stage filter interaction analysis:**

| Stage | What it targets | Method | Modification rate (reference run) |
|-------|----------------|--------|----------------------------------|
| Stage 1 | Velocity/Z-score tracking spikes (post-resample) | Velocity_limit + Z-score → NaN → PCHIP | 0.12% frames |
| Stage 2 | Local statistical outliers surviving Stage 1 | Hampel sliding window (5-frame, 3σ) | 0.09% frames |
| Stage 3 | Broadband measurement noise | Adaptive Winter Butterworth (6–12 Hz mean cutoff) | 100% of signal |

**F-MIN analysis:**

*Stage 1 vs Step 02 redundancy:* Step 02 performs velocity-based MAD artifact masking on the raw irregular timestamp data before resampling. Stage 1 performs velocity + Z-score masking after resampling. These operate on the same artifact class (tracking spikes) but at different points in the pipeline. The question is: after CubicSpline resampling of a step-02-cleaned signal, can new velocity spikes appear?

**Assessment:** Unlikely for clean data. CubicSpline of a gap-filled, valid-segment signal should not introduce velocity spikes. However, if Step 02 fails to mask a spike (because the MAD threshold is generous with large-velocity natural bursts), Stage 1 provides a second catch. For data with mean SNR = 52.7 dB (EXCELLENT), Stage 1 typically catches very few frames (0.12%).

**Decision for Stage 1:** `KEEP_AS_IS` but document explicitly as "safety net for Step 02 misses, not primary artifact removal." The combined modification rate (Step 02 + Stage 1 + Stage 2) should be logged in `__filtering_summary.json` with a new field `total_data_modified_pct` for cross-run comparison.

*Stage 1 + Stage 2 complementarity:* Stage 1 PCHIP repairs produce smooth trajectories at artifact sites. Stage 2 Hampel cannot detect PCHIP-introduced inaccuracies (since they look smooth). These stages target different artifact signatures and are NOT redundant.

*Stage 3 (Winter + Butterworth) — the critical concern:*
Stage 3 is not an artifact detector. It is a low-pass filter applied to 100% of the signal. A mean cutoff of 8.6 Hz with `winter_fmax = 20 Hz` and `per_joint_winter = True` means every position column gets a Butterworth filter that removes content above ~8–12 Hz. The dance frequency domain extends to 13 Hz. The PSD audit confirms -5.40 dB attenuation in the 1–13 Hz dance band.

**Ground Truth Proximity (F-MIN) analysis:**
The goal is to remove sensor noise above the motion signal, not to smooth the motion signal itself. For Gaga dance, the meaningful frequency content extends to ~13 Hz (fast hand gestures, percussive foot strikes, head shakes). The current Smart Bias architecture biases distal joints toward 12 Hz and proximal joints toward 6 Hz. The 6 Hz cutoff for trunk joints (Hips, Spine, Spine1) may be over-aggressive for a dance context — Winter (2009) recommends 6 Hz for gait (a lower-frequency activity) and the pipeline inherits this without dance-specific adjustment.

**F-MIN conclusion:** Stage 3 as designed is not over-engineered — the adaptive Winter approach is scientifically sound. The problem is that the current floor values in Smart Bias were calibrated for clinical gait, not dance. The target is not to remove Stage 3 but to add a post-application feedback loop (see S-04.3 below).

#### S-04.1 — Stage 1: Artifact Detector (F-LOG architectural filter)

**Current state:** `vel[t] = (pos[t+1] - pos[t]) / dt` → velocity_limit OR Z-score → NaN + PCHIP.

**F-LOG analysis:**
The Z-score threshold (`zscore_threshold = 5.0`) is applied to velocities. Velocity distributions in dance motion are heavy-tailed, not normal. A 5σ threshold on a heavy-tailed distribution underestimates the probability that a high-velocity frame is genuine. For example, a powerful jump or explosive arm gesture may produce a 5–6σ velocity event that is completely physiological.

**Mitigation:** The `velocity_limit = 5000 mm/s` (5 m/s) is the primary gate. 5 m/s exceeds the physiological maximum for any body segment marker in normal Gaga improvisation. The Z-score gate is a secondary catch for more moderate anomalies.

**Proposed refinement (F-LOG):**
Apply the Z-score threshold only to velocities **below** the `velocity_limit`. Frames above `velocity_limit` are clear hardware failures. Frames below `velocity_limit` but above the Z-score threshold should receive a **`suspicious_flag`** rather than immediate NaN masking — for a follow-up decision. This two-tier approach preserves potentially genuine high-velocity frames while still flagging them for downstream review.

Concretely:
- `|vel| > velocity_limit` → NaN immediately (hardware tracking failure — unambiguous)
- `velocity_limit > |vel|` AND `Z-score > zscore_threshold` → mark as `STAGE1_SUSPICIOUS` flag in a new `artifact_flags` column; repair with PCHIP but record in metadata

**Decision for Stage 1:** `LOCAL_REFACTOR` (two-tier flagging)
**Confidence:** Medium. The single-step mask → repair is pragmatic and the current 0.12% rate suggests it's not causing systematic damage. But the false-positive risk on high-velocity dance bursts is real and should be quantified.

#### S-04.2 — Stage 2: Hampel Filter

**Current state:** 5-frame window, 3σ. 1142 outliers (0.09% of frames).

**Target state:** No change to algorithm. Add modification rate to `__filtering_summary.json` with per-joint breakdown.

**Decision:** `KEEP_LOG_QC`
**Scientific rationale:** The Hampel filter is a surgical, non-linear outlier replacer. At 0.09% modification rate with 5-frame (42 ms) window, it cannot introduce systematic signal distortion. It only fires on frames that deviate > 3σ from their local neighborhood — a strong criterion. The window is short enough (42 ms) that it cannot smooth out dance dynamics (minimum dance event timescale ~80–100 ms at 10 Hz).
**Confidence:** High.

#### S-04.3 — Stage 3: Adaptive Winter Filter with Dance-Band Correction Loop (F-ADP architectural filter)

**Current state:** Winter's residual analysis selects per-joint cutoffs. Smart Bias applies per-region floors. Butterworth `filtfilt` applied. No post-application feedback loop.

**Confirmed problem:** Dance band delta = -5.40 dB, threshold > -3 dB. 57/57 columns flagged as `REVIEW_OVERSMOOTHING`.

**Target state — Dance-Band Adaptive Correction Loop (F-ADP):**

The target architecture adds a single post-filter feedback step. The Winter analysis and Smart Bias selection remain unchanged. After the Butterworth filter is applied, the pipeline evaluates the spectral dance band delta and adjusts the cutoff upward if the threshold is not met.

```
Algorithm: adaptive_winter_with_dance_correction()

  Phase 1 — Initial cutoff selection (unchanged from current):
    fc_initial = winter_residual_analysis(signal, fmin, fmax)
    fc_biased  = smart_bias_blend(fc_initial, region_floor)

  Phase 2 — Apply filter and evaluate:
    fc_current = fc_biased
    max_iterations = 10
    correction_applied = False

    for iter in range(max_iterations):
      filtered = filtfilt(*butter(2, fc_current / (0.5*fs), 'low'), signal)

      # Welch PSD in dance band [1, 13 Hz]:
      Δ_dance_dB = PSD_band_ratio(filtered, signal, flo=1.0, fhi=13.0, fs=fs)

      if Δ_dance_dB >= DANCE_BAND_THRESHOLD_DB:  # default: -3.0 dB
        break  # target met

      # Increase cutoff:
      fc_new = min(fc_current + CORRECTION_STEP_HZ, region_max_hz)
      if fc_new == fc_current:
        status = 'REVIEW_OVERSMOOTHING_UNRESOLVED'
        break
      fc_current = fc_new
      correction_applied = True

  Phase 3 — Log:
    Write to __filtering_summary.json:
      fc_initial_hz, fc_biased_hz, fc_final_hz,
      dance_band_delta_dB, noise_band_delta_dB,
      correction_applied (bool), correction_iterations,
      dance_band_status: 'PASS' | 'CORRECTED' | 'REVIEW_OVERSMOOTHING_UNRESOLVED'
```

**Key parameters for target config:**

| Parameter | Proposed value | Rationale |
|-----------|---------------|-----------|
| `dance_band_threshold_db` | -3.0 dB | Current spec. -3 dB = preserving ≥71% of dance band energy. |
| `correction_step_hz` | 0.5 Hz | Fine enough to find the minimal passing cutoff without overshoot. |
| `region_max_hz` | Per-region floor + 6 Hz (e.g., trunk: 6→12 Hz max; distal: 12→18 Hz max) | Prevents runaway; upper bound is the Nyquist-safe ceiling. |
| `max_correction_iterations` | 10 | At 0.5 Hz/step, max +5 Hz correction before declaring unresolved. |

**Proposed per-region max cutoff floors (target):**

| Region | Current floor | Proposed correction ceiling |
|--------|-------------|--------------------------|
| Trunk (Hips, Spine, Spine1) | 6 Hz | 12 Hz |
| Head/Neck | 8 Hz | 14 Hz |
| Upper Proximal (Shoulder, Upper Arm) | 8 Hz | 14 Hz |
| Upper Distal (Forearm, Hand) | 12 Hz | 18 Hz |
| Lower Proximal (Thigh, UpperLeg) | 8 Hz | 14 Hz |
| Lower Distal (Shin, Foot) | 10 Hz | 16 Hz |

These ceilings are set at `floor + 6 Hz`. They are conservative — the true measurement noise floor for an OptiTrack passive marker system at 120 Hz typically lies above 20 Hz, so any content below 18 Hz is likely genuine motion, not hardware noise.

**Decision:** `REDESIGN_CANDIDATE` (Stage 3 feedback loop)
**Scientific rationale:** The adaptive Winter cutoff selection is a well-established biomechanical method (Winter 2009). The problem is not the method itself but the absence of a domain-specific acceptance criterion. Adding a post-filter validation loop that elevates the cutoff until the dance band is preserved is a minimal, contained modification: the same Butterworth filter, the same filtfilt, the same Smart Bias logic — the only addition is an iterative cutoff correction conditioned on spectral domain knowledge. This does not change the algorithm paradigm; it closes the feedback loop.

**Confidence:** High that the loop design is correct. Medium that -3 dB is the right threshold.

**[RECONSIDER_LATER]** — Q-ADP: "Verify whether the -3 dB dance band preservation threshold is sufficient for high-velocity Gaga sessions. High-velocity bursts (explosive jumps, fast arm gestures) concentrate energy at 8–13 Hz. A -3 dB threshold allows up to 29% energy loss in this band. For biomechanical analysis of peak angular velocities and Total Movement (F2 TM), a tighter threshold (-1 dB) may be required at distal joints. Evaluate after Stage 4 per-joint frequency audit on ≥10 P2 sessions."

#### S-04.4 — Quaternion Median Filter

**Current state:** `scipy.signal.medfilt` on each quaternion component, kernel=5. Purpose: remove hemisphere flips.

**Target state:** No change.

**Decision:** `KEEP_AS_IS`
**Scientific rationale:** Component-wise median filter on quaternions is not geometrically ideal (quaternion space is curved), but for a 5-frame (42 ms) window targeting single-frame hemisphere flips, the geodesic error introduced is negligible (< 0.1° for typical joint angles). The correct approach would be a geodesic sliding window median on SO(3), but the added complexity is not justified given the low flip rate and the subsequent SavGol smoothing in Step 06.
**Confidence:** High.

---

### S-05 — Reference Detection (NB05)

**Current state:** Markley mean quaternion (eigendecomposition of the 4×4 outer-product accumulator matrix) over the best 1.5-second static window in the first 8 seconds. Cross-validates skeletal height against registry.

**Target state:** No change to algorithm. One documentation gap to address.

**Algorithmic assessment:**
The Markley mean is the maximum-likelihood estimator for the mean rotation on S³ under a geodesic-symmetric noise model. It is strictly superior to component-wise averaging for quaternions. Its use here is scientifically justified (Markley et al. 2007, J. Guidance Control Dynamics).

The static window detection using median of joint angular velocities with strict + fallback criteria is robust.

**One edge case to document:** If the T-pose is not reliably present in the first 8 seconds (e.g., subject moves immediately), the fallback "minimum variance window" may return a non-neutral pose. This would corrupt the T-pose zeroing in Step 06. The `reference_metadata.json` already records `method: criteria | fallback`. NB05 should emit a `WARNING_FALLBACK_REFERENCE` flag in metadata when `method = fallback` and `ref_quality_score > 0.05 rad`.

**Decision:** `KEEP_AS_IS` + `KEEP_LOG_QC` (fallback warning flag)
**Confidence:** High.

---

### S-06 — Kinematics Master Computation (NB06)

#### Angular velocity (F-LOG architectural filter)

**Current state:** Quaternion logarithm method: `dR = inv(R(t)) × R(t+1)`, `ω = rotvec_delta / dt`. Input quaternions are SavGol-smoothed before ω is computed. `α` is SavGol derivative of `ω`. An alternative `5pt` stencil method is configurable via `omega_method`.

**F-LOG analysis:**
The quaternion logarithm method is mathematically correct for SO(3) and is the standard in biomechanics (Muller et al. 2017, Sola 2017). The key question: is the adjacent-frame finite difference `dR = inv(R(t)) × R(t+1)` a weak point?

For smoothed input quaternions (SavGol pre-smoothing applied), the adjacent-frame difference is a 1st-order backward difference with dt = 1/120s = 8.3 ms. This is equivalent to a derivative estimated at the Nyquist-limit resolution. The `5pt` finite difference stencil available in `omega_method` offers noise resistance by weighting 5 adjacent frames.

**Target:** Set `omega_method = '5pt'` as the default in `config_v1.yaml`. The 5-point stencil provides 4th-order accuracy vs 1st-order for the adjacent-frame method. Given that the input quaternions are already SavGol-smoothed, the gain is modest, but it eliminates single-frame noise amplification in ω at no additional algorithmic cost.

**Decision for ω method:** `LOCAL_REFACTOR` (config default only — `omega_method: '5pt'`)
**Confidence:** Medium. Both methods produce valid ω. The `5pt` method is strictly more accurate for smooth signals. The change is a config key, not a code change.

#### Surgical repair policy

**Current state:** `step_06.enforce_cleaning = true` is optional. When enabled, joints with CRITICAL outliers undergo SLERP (rotational) or PCHIP (linear) repair.

**Target:** Make `enforce_cleaning = true` the default. Add `surgical_repair_log` to `__validation_report.json` recording per-joint repair events (joint name, frame range, repair method, count). This does not change the algorithm — it ensures the cleanup is always applied and logged.

**Decision:** `LOCAL_REFACTOR` (change default + log)
**Confidence:** High.

#### Remaining S-06 assessment

| Component | Decision | Rationale |
|-----------|----------|-----------|
| Root-relative position | `KEEP_AS_IS` | Removes global translation correctly |
| SavGol linear velocity/acceleration | `KEEP_AS_IS` | SavGol derivative is the standard for clean mocap data |
| ISB Euler angles (Wu et al. 2005) | `KEEP_AS_IS` | Correct joint-specific rotation sequences |
| de Leva CoM (1996) | `KEEP_AS_IS` | Standard 16-segment model; flagged by `bone_qc_fail_flag` if segments are unreliable |
| NaN Guard (< 0.1%) | `KEEP_AS_IS` | Correct threshold. Log NaN locations to validation report |
| Continuity enforcement | `KEEP_AS_IS` | Final quaternion hemisphere-flip removal |
| Parquet metadata embedding | `KEEP_AS_IS` | PyArrow schema metadata is correct |

---

### S-08 — Engineering Physical Audit (NB08)

**Current state:** Produces Excel workbook with height/mass validation, methodology passport, bone QC verdict, SNR analysis. Reads all available runs (P1+P2+P3).

**Target additions:**
1. Read the new `bone_qc_fail_flag` from kinematics_map.json and include in the audit workbook's QC_Summary sheet.
2. Read `dance_band_delta_dB` and `dance_band_status` from `__filtering_summary.json` and include in a new `Filter_Audit` sheet.

**Decision:** `KEEP_LOG_QC` (add two new data sources to existing audit)
**Confidence:** High.

---

### S-11 — v2 Feature Extraction (NB11)

**Current state:** Explicit `if phase == "P2"` filter. T1-anchored PCA. 4 features (F1 ATF, F2 TM, F4 D_eff, F5 Joint Gini). `validate_reference()` before fit. Manual scientist anchor selection.

**Target additions:**
1. After loading each session, check `kinematics_map.json` for `bone_qc_fail_flag: true`. If true, print and log a warning listing failing joints and their CV%. Do not block the feature extraction.
2. Check `dance_band_status` from `__filtering_summary.json`. If any session has `REVIEW_OVERSMOOTHING_UNRESOLVED`, log as a sensitivity flag in `run_metadata.json`.

**Decision:** `KEEP_AS_IS` + `KEEP_LOG_QC` (sensitivity checks only)
**Confidence:** High.

---

## 5. What is already aligned with the current pipeline

The following components require **no redesign** and are consistent with the target skeleton. Each is certified `KEEP_AS_IS`:

| Component | Evidence |
|-----------|---------|
| OptiTrack CSV parser (`parse_optitrack_csv`) | 51/51 joints, correct name mapping, 0 NaN on reference run |
| PCHIP gap filling (positions) | Monotonicity preserved, C1-continuous at boundaries |
| SciPy Slerp resampling (quaternions) | Geodesically correct, `time_grid_std = 0.0` |
| Cubic spline resampling (positions) | C2-continuous, needed for clean velocity derivatives |
| Hampel filter | 0.09% modification rate, surgical action only |
| Markley mean quaternion (T-pose reference) | Geodesic mean on S³, mathematically optimal |
| Quaternion logarithm angular velocity | Respects SO(3) manifold, standard in biomechanics |
| SavGol velocity/acceleration derivatives | Standard noise-robust derivative estimator |
| ISB Euler angles (Wu et al. 2005) | Correct joint-specific ZYX/XYZ sequences |
| de Leva CoM model | Standard 16-segment model |
| NaN Guard + Continuity enforcement | Correct. 0 NaN, 0 flips in reference run |
| P2-only filter in NB11 | Explicit code gate confirmed in Phase 2 |
| T1-anchored PCA in NB11 | Correctly implements METHODOLOGY_SPEC_v2.md §PCA |
| Legacy archive (C2, C4) | `core_kinematics_engine.py` + `EDA_PCA.py` → `legacy/` |

---

## 6. What must be audited in Phase 4 before deciding

These items cannot be decided without deeper per-stage evidence:

| Item | Why deferred |
|------|-------------|
| False-positive rate of Step 02 MAD artifact masking on high-velocity frames | Need per-session frequency analysis of masked regions |
| Stage 1 Z-score false-positive rate | Need to cross-check masked frames against PSD of surrounding data |
| Actual per-session dance band delta distribution | Current -5.40 dB is one reference run. Need N > 6 sessions to determine whether oversmoothing is session-invariant or run-dependent |
| `5pt` vs adjacent-frame ω method difference in practice | Need to compare ω_mag distributions from both methods on same session |
| Bone QC CV% distribution across all 12 processed sessions | Need to quantify how many sessions have bone_qc_fail_flag: true |
| Step 02 bone length unit bug impact on FAIL determination | CV% computation is correct, but need to verify that the FAIL labels are not threshold artifacts |

---

## 7. What must remain downstream, not in `kinematics_master.parquet`

| Item | Why |
|------|-----|
| F1–F5 feature scalars (ATF, TM, D_eff, Joint Gini) | Session-aggregate summary statistics; not frame-level. Master parquet is frame-level only. |
| PCA scores / PC coordinates | Session-aggregate. Belongs in NB11 `feature_scalars.csv`. |
| Longitudinal comparisons (T1 vs T2 vs T3 delta) | Research product, not preprocessing output. |
| NB09/NB10 legacy outputs | Legacy outputs from archived engines. Not part of current pipeline. |
| Excel engineering audit reports | Reporting artifact, not analytical data. |

---

## 8. What must remain out of scope for this skeleton

| Item | Reason |
|------|--------|
| Replacing the 3-stage filter architecture | The architecture is sound; only the feedback loop is missing. Replacing the entire filter is over-engineering. |
| Adding new kinematic features to `kinematics_master.parquet` | Out of scope for Phase 3. Feature additions require separate spec approval. |
| Reviving NB09 (legacy dashboard) or NB10 (3-branch PCA) | Legacy engines are archived. Revival requires explicit user decision and science review. |
| Step 07 Pulsicity/Flow | Marked "Planned — not in production" in `STEP_07_MISSION_PLAN.md`. Out of scope. |
| Multi-subject scaling / batch optimization | N=2 subjects. Scale optimization is premature. |
| Deep learning / ML model integration | Layer C downstream concern. Out of Phase 3 scope. |

---

## 9. Known risks of this skeleton

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Adaptive correction loop may raise cutoff too high** — if the dance band check passes at fc = 16 Hz (distal), we may be letting genuine noise through. | Medium | The correction ceiling (`region_max_hz`) is bounded. At 16 Hz for distal joints with 120 Hz sampling, there is a 104 Hz noise margin. OptiTrack rigid body tracking noise typically starts above 20 Hz. Risk is low but should be validated in Phase 4 per-stage audit with noise band comparison. |
| **Bone QC flags may under-report** — the FAIL criterion (CV > 5%) uses Skurowski (2021) gait thresholds which may be too lenient or too strict for a dance context. | Medium | [RECONSIDER_LATER] Q-QC7 above. Pending N > 20 data. |
| **Config snapshot adds a new file per run** — `step_00_config/` derivatives directory will accumulate one YAML per session. For N=12 sessions, this is 12 files (~12 KB total). No practical concern at current scale. | Low | Negligible. |
| **5pt ω method as default may interact with SavGol pre-smoothing** — if the input quaternions are already SavGol-smoothed, applying a 5-point stencil may produce slightly over-damped ω at discontinuities. | Low | The SavGol window is 21 frames; the 5pt stencil spans 5 frames. The interaction is minor. The 5pt method is a strict improvement over adjacent-frame for smooth input. |
| **NB10 remains broken** — `10_EDA_PCA.ipynb` imports from `legacy/EDA_PCA.py`. Not in automated sequence, but a researcher may run it manually and get a confusing error. | Low | Should either add explicit deprecation header to NB10 or update import to `legacy/`. Pending user decision (Q8). |

---

## 10. Decision matrix summary

| Component | Decision | Priority | Confidence |
|-----------|----------|---------|------------|
| Per-run config snapshot (`step_00_config/`) | `LOCAL_REFACTOR` | High | High |
| Bone QC warning/flagging policy (S-02.2) | `KEEP_LOG_QC` | High | High |
| Bone QC display unit fix (mm not ×1000) | `LOCAL_REFACTOR` | Low | High |
| Step 02 velocity estimator (3-pt central diff) | `LOCAL_REFACTOR` | Medium | Medium |
| Stage 1 two-tier flagging (FAIL vs SUSPICIOUS) | `LOCAL_REFACTOR` | Medium | Medium |
| Stage 2 Hampel (add per-joint log) | `KEEP_LOG_QC` | Low | High |
| Stage 3 adaptive dance-band correction loop | `REDESIGN_CANDIDATE` | **Critical** | High |
| Stage 4 quaternion median filter | `KEEP_AS_IS` | — | High |
| Step 05 fallback reference warning flag | `KEEP_LOG_QC` | Low | High |
| Step 06 default `omega_method = '5pt'` | `LOCAL_REFACTOR` (config) | Low | Medium |
| Step 06 `enforce_cleaning = true` default | `LOCAL_REFACTOR` (config + log) | Low | High |
| Step 08 audit — add filter audit sheet | `KEEP_LOG_QC` | Low | High |
| NB11 bone QC sensitivity check | `KEEP_LOG_QC` | Low | High |
| Legacy archive (C2, C4) | Already done | — | — |

---

## 11. Questions for Phase 4 audits

| Q# | Question | Phase 4 stage |
|----|----------|--------------|
| Q-S02 | Is the Step 02 MAD velocity threshold producing false positives on high-velocity dance bursts? What fraction of Step 02 masked frames are in the 1–13 Hz dance band? | Stage 02 audit |
| Q-S04a | What is the distribution of dance band delta dB across all 12 processed P2 sessions? Is -5.40 dB session-invariant? | Stage 04 audit |
| Q-S04b | For the reference session, what is the noise band (20–50 Hz) delta post-filter? Is noise attenuation meeting the ≥95% threshold? | Stage 04 audit |
| Q-S04c | What is the per-joint correction iteration count needed to meet -3 dB threshold? Which joints require the largest cutoff adjustment? | Stage 04 audit |
| Q-S06a | What is the practical ω_mag difference between `adjacent_frame` and `5pt` methods on the reference session? Is the difference > 1 deg/s for any joint? | Stage 06 audit |
| Q-S06b | In how many sessions does `enforce_cleaning` repair any frames? What is the per-session repair rate? | Stage 06 audit |
| Q-QC7 | How many of the 12 processed sessions have bone_qc_fail_flag: true? Which joints are consistently failing? | Stage 02 audit |

---

## 12. [RECONSIDER_LATER] registry

| Tag | Stage | Text |
|-----|-------|------|
| Q-ADP | S-04.3 | Verify whether the -3 dB dance band preservation threshold is sufficient for high-velocity Gaga sessions. High-velocity bursts concentrate energy at 8–13 Hz. A tighter threshold (-1 dB) may be required at distal joints. Evaluate after Stage 4 per-joint frequency audit on ≥10 P2 sessions. |
| Q-QC7 | S-02.2 | Quantify propagated uncertainty in CoM position (mm) and angular velocity magnitude (deg/s) from bone length CV > 5% for failing joints across N > 20 sessions. Hypothesis: 10% CV in Hips→Spine introduces ~50–100 mm CoM uncertainty. Required before thesis-grade CoM claims. |
| Q-S02 | S-02.1 | Measure the false-positive artifact masking rate in Step 02 (MAD velocity) vs Step 04 Stage 1 (Z-score) by comparing masked frame sets on the same sessions. If >10% of Step 02 flags occur in the 1–13 Hz dance band (physiological range), upgrade velocity estimator to 3-point central diff. |

---

*End of Phase 3 — Draft Target Skeleton*
