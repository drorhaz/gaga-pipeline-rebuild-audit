# Methodology Specification — Feature Extraction Pipeline
## Technical Implementation Document for Longitudinal Motor Phenotyping in Gaga Dance

**Document Class:** Master Implementation Specification  
**Pipeline Version:** v2.0  
**Author:** Research Software Architecture — Gaga Motion Analysis Project  
**Date:** 2026-04-06  
**Study:** *Longitudinal Kinematic Case Study of Gaga Improvisation (N=3 pilot)*  
**Input:** `derivatives/step_06_kinematics/{RUN_ID}__kinematics_master.parquet` at 120 Hz  

> **How to use this document.** This is the self-contained execution manual for implementing, debugging, and defending all seven primary features. Each feature is an **independent module**: it reads from the master Parquet, computes one scalar (or small struct) per session, and writes its own output. No feature depends on another feature's output at runtime. When code and this document conflict, this document defines intent.

---

## Table of Contents

- [Section 0: The Scientific Story — Three Narrative Layers](#section-0-the-scientific-story--three-narrative-layers)
- [Section 1: Modular Architecture & Feature Specifications](#section-1-modular-architecture--feature-specifications)
  - [F1. Active Time Fraction (ATF)](#f1-active-time-fraction-atf)
  - [F2. Total Movement — Endpoint Path Length (TM)](#f2-total-movement--endpoint-path-length-tm)
  - [F3. Endpoint–COM Amplitude (A)](#f3-endpointcom-amplitude-a)
  - [F4. Effective Dimensionality — Participation Ratio (D_eff)](#f4-effective-dimensionality--participation-ratio-d_eff)
  - [F5. Joint Gini Coefficient](#f5-joint-gini-coefficient)
  - [F6. JcvPCA — Joint Contribution Variation](#f6-jcvpca--joint-contribution-variation)
  - [F7. JsvCRP — Hips–Spine Continuous Relative Phase](#f7-jsvcrp--hipsspine-continuous-relative-phase)
- [Section 2: Success Matrix, Debugging & Failure Protocol](#section-2-success-matrix-debugging--failure-protocol)
- [Section 3: Companion Metrics & Confound Controls](#section-3-companion-metrics--confound-controls)

---

## Section 0: The Scientific Story — Three Narrative Layers

The seven features form a **three-layer narrative** of motor change across 10 Gaga classes. Each layer answers a different question; together they describe a full trajectory from "how much" to "how organized."

### Layer 1 — Physical Expansion: "The dancer moves more, reaches further, awakens dormant joints."

| Feature | Question answered | Predicted Class 1 → Class 10 |
|---------|-------------------|-------------------------------|
| **ATF** | What fraction of time is each body part actively moving? | ↑ More joints cross their noise floor, more of the time |
| **TM** | How much total distance do the hands and feet cover? | ↑ Greater cumulative path length (normalized by duration) |
| **Amplitude A** | How far do the limbs reach from the body's center of mass? | ↑ Larger spatial envelope |

**Narrative:** Before Gaga training, habitual movers rely on a few "favorite" joints (typically arms) while the rest of the body is either passive or mechanically entrained. Layer 1 captures the **quantitative expansion** — more body parts moving, covering more distance, reaching further from center. This is the most **immediately visible** change and the **least epistemologically risky** to claim: it requires no model, no embedding, no projection — only counting, summing, and averaging.

### Layer 2 — Structural Diversification: "The motor system uses more independent modes and distributes variance more democratically."

| Feature | Question answered | Predicted Class 1 → Class 10 |
|---------|-------------------|-------------------------------|
| **D_eff** | How many independent kinematic modes share the movement energy? | ↑ Flatter eigenvalue spectrum |
| **Joint Gini** | Is variance dominated by a few joints or shared across the skeleton? | ↓ More equal joint contributions |

**Narrative:** Expansion alone does not capture **how** the motor system reorganizes. A dancer could double their path length while remaining locked in one dominant coordination pattern (PC1 explains 80% of variance). Layer 2 moves from *amount* to *structure*: D_eff captures the **dimensionality** of the coordination manifold (how many independent movement patterns are active), while Joint Gini captures the **anatomical distribution** (which body parts contribute variance). Together they test the Gaga hypothesis that training dissolves motor hierarchy — shifting from "arms lead, body follows" to "every joint participates."

### Layer 3 — Coordination Reorganization: "The joints reweight their contributions and re-phase their temporal coupling."

| Feature | Question answered | Predicted Class 1 → Class 10 |
|---------|-------------------|-------------------------------|
| **JcvPCA** | Which joints gained or lost loading weight on the dominant PCs? | Detectable per-joint, per-PC loading shifts |
| **JsvCRP** | Did the temporal phasing between pelvis and spine change? | Larger area between Class 1 and Class 10 CRP curves |

**Narrative:** Layer 3 is the **most specific** and the **most theoretically anchored in motor learning**. JcvPCA reveals *which* joints reorganized their contribution to the shared coordination patterns — it is a **per-joint, per-PC "who changed?" matrix**. JsvCRP captures *temporal coupling*: whether the trunk segments (pelvis and spine) — the core of Gaga's "find the baby" instruction — changed their phase relationship. This layer connects kinematics to **coordination science** and gives the committee a named, published methodology (JcvPCA/JsvCRP) rather than a novel index.

**The full sentence:** *"The dancer expands physically (Layer 1), while simultaneously diversifying their dynamic range (Layer 2) and reorganizing inter-joint coordination strategy (Layer 3)."*

---

## Section 1: Modular Architecture & Feature Specifications

### Architecture Principles

1. **Independence Rule.** Each feature reads from `kinematics_master.parquet` directly. No feature imports or calls another feature's function. Shared utilities (parquet loading, artifact masking, column selection) live in a common `utils` layer, not in feature modules.
2. **One scalar per session.** Each feature produces one primary number (or a small fixed-size struct) per (subject, session) pair. Longitudinal comparison is always `metric(Class_10) − metric(Class_1)`.
3. **NaN-safe by design.** Every computation explicitly handles artifact frames via the `{Joint}__is_artifact` boolean columns. Artifact frames are **excluded** before any aggregation — never interpolated, never zeroed.
4. **Parameter externalization.** All tunable parameters are defined in a `params` dict at the top of each module. No magic numbers embedded in computation logic.

---

### F1. Active Time Fraction (ATF)

#### Scientific Definition & Defense

> **Thesis-ready:** Active Time Fraction quantifies the proportion of time each joint generates kinematic output above its session-specific noise floor, providing a full-body engagement profile that directly operationalizes the Gaga instruction to "find the body parts you habitually ignore." ATF is the least epistemologically risky metric in this framework — it is a threshold-crossing rate, a concept that appears in virtually every domain of movement science.

**Primary citations:** Movement quantity (Roetenberg et al., 2007); EMG recruitment duration analog (Thoroughman & Shadmehr, 2000); session-adaptive noise floor from pipeline Step 05 calibration logic.

#### Mathematical Formulation

**Input columns:** `{Joint}__lin_vel_rel_mag` (mm/s), `{Joint}__is_artifact` (bool), for all 19 joints.

**Step 1 — Session-adaptive noise floor.** For each joint $i$ and session $s$:

$$V_{i,s} = \text{compute\_noise\_floor}(v_i, \text{cfg})$$

Three-phase guard:
- Phase A: Detect quietest 2-second static window; use its mean velocity.
- Phase B (fallback): If no static window found, use 5th percentile of $v_i$ over clean frames.
- Phase C (absolute minimum): $V_{i,s} \geq 1.0$ mm/s (prevents zero thresholds from tremor-free tracking).

**Step 2 — Per-joint ATF:**

$$\text{ATF}_{i,s} = \frac{\sum_{t=1}^{T} \mathbb{1}[ v_i(t) > V_{i,s} \;\wedge\; a_i(t) = 0 ]}{\sum_{t=1}^{T} \mathbb{1}[ a_i(t) = 0 ]}$$

**Step 3 — Whole-body summary:**

$$\text{ATF}_{\text{wb}} = \text{median}_{i \in \{1..19\}}(\text{ATF}_{i,s})$$

Median (not mean) for robustness to single-joint artifact outliers.

**Step 4 — Group summaries:**

| Group | Joints | Purpose |
|-------|--------|---------|
| Axial | Hips, Spine, Spine1, Neck, Head, Chest | Core engagement |
| Peripheral | LForeArm, LHand, RForeArm, RHand, LFoot, RFoot | Distal awakening |
| Transitional | Shoulders, UpperArms, Thighs, Shins | Bridge |

$$\text{ATF}_{\text{group}} = \text{median}_{i \in \text{group}}(\text{ATF}_{i,s})$$

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `noise_floor_guard_mms` | 1.0 mm/s | ~1/10th resting hand tremor (~10 mm/s); ensures any voluntary movement exceeds threshold |
| `static_baseline_guard_mms` | 50.0 mm/s | Maximum velocity in a static window; above physiological tremor, below intentional movement |
| `static_window_sec` | 2.0 s | Minimum window to estimate noise floor; 240 frames at 120 Hz provides stable mean |
| `artifact_warning_threshold` | 0.20 | Soft warning when >20% frames are artifacts |
| `artifact_critical_threshold` | 0.30 | Hard exclusion above 30% artifact |
| `fs` | 120 Hz | OptiTrack system rate |

#### Execution Logic

```
FUNCTION compute_atf(parquet_path, params) → ATFResult:
    1. Load parquet; extract time_s, all {Joint}__lin_vel_rel_mag, all {Joint}__is_artifact.
    2. Validate: assert fs ≈ 120 Hz from diff(time_s); assert ≥ 19 joints present.
    3. Compute artifact_fraction = mean(any_joint_is_artifact).
       IF artifact_fraction > params.critical → RETURN status="EXCLUDED".
    4. FOR each joint i:
         a. mask = ~is_artifact[i]
         b. v_clean = vel_mag[i][mask]
         c. V_i = noise_floor(v_clean, params)  # 3-phase guard
         d. ATF_i = sum(v_clean > V_i) / len(v_clean)
    5. ATF_wb = median(all ATF_i)
    6. ATF_peripheral = median(ATF over peripheral joints)
    7. ATF_axial = median(ATF over axial joints)
    8. RETURN ATFResult(per_joint, whole_body, by_group, noise_floors, clean_duration_s)
```

#### Strategic Crossroads

- **Noise floor method:** Static-window detection vs 5th-percentile fallback. If no static window exists (continuous movement), the fallback is more conservative (lower threshold → higher ATF). Document which method was used per session.
- **Artifact exclusion vs interpolation:** This spec excludes artifact frames. Interpolating through artifacts would inflate ATF by inserting smooth transitions that cross the threshold. Never interpolate for ATF.

#### Risk Points & Consequences

| Risk | Impact | Mitigation |
|------|--------|------------|
| Noise floor too low (tremor-free tracking) | ATF inflated; near 1.0 for all joints | Absolute minimum 1.0 mm/s guard; report noise floor per joint |
| High artifact rate in one session | Denominator shrinks; ATF may become unreliable | Exclude if artifact_fraction > 0.30; soft warn above 0.20 |
| Session duration mismatch | Longer sessions may have different ATF due to fatigue/warm-up | Report clean_duration_s alongside ATF; normalize comparison by noting durations |
| OptiTrack tracking dropout on specific joint | Systematic NaN → artificial low ATF for that joint | Check per-joint NaN rates before computing; flag if >10% NaN on any joint |

---

### F2. Total Movement — Endpoint Path Length (TM)

#### Scientific Definition & Defense

> **Thesis-ready:** Total Movement quantifies the cumulative Euclidean distance traveled by four distal endpoints (both hands, both feet) in root-relative coordinates, providing a direct, physically interpretable measure of overall movement quantity. Sanchez Martz et al. (2025) found significant TM differences between imagery conditions in professional dancers (Wilcoxon S = 68, p = 0.0497), establishing TM as a sensitive kinematic summary for creative-movement contrasts.

**Primary citation:** Sanchez Martz et al. (2025) — `17. Unlocking Creative Movement with Inertial Technology`.  
**Committee-verified quote:** *"significant measurable effects of the condition on postural parameters (Table 2, Figure 2)."*

#### Mathematical Formulation

**Input columns (4 endpoints × 3 axes = 12 columns):**

| Endpoint | X | Y | Z |
|----------|---|---|---|
| Left Hand | `LeftHand__lin_rel_px` | `LeftHand__lin_rel_py` | `LeftHand__lin_rel_pz` |
| Right Hand | `RightHand__lin_rel_px` | `RightHand__lin_rel_py` | `RightHand__lin_rel_pz` |
| Left Foot | `LeftFoot__lin_rel_px` | `LeftFoot__lin_rel_py` | `LeftFoot__lin_rel_pz` |
| Right Foot | `RightFoot__lin_rel_px` | `RightFoot__lin_rel_py` | `RightFoot__lin_rel_pz` |

All positions are root-relative (pelvis origin), in millimeters.

**Formula:**

$$\text{TM}_s = \sum_{t=2}^{T} \sum_{e \in \{LH, RH, LF, RF\}} \| \mathbf{p}_{e}(t) - \mathbf{p}_{e}(t-1) \|_2 \quad \text{[mm]}$$

where the sum is taken only over **clean frame pairs** (both $t$ and $t-1$ must have `is_artifact = False` for endpoint $e$'s corresponding joint).

**Duration-normalized form (primary for longitudinal comparison):**

$$\text{TM}_{\text{rate}} = \frac{\text{TM}_s}{T_{\text{clean}} / f_s} \quad \text{[mm/s]}$$

where $T_{\text{clean}}$ is the number of clean frame-pairs and $f_s = 120$ Hz.

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `fs` | 120 Hz | System rate; defines temporal resolution of step integration |
| `min_segment_frames` | 3 | Minimum consecutive clean frames for a valid segment; shorter fragments are skipped |
| `normalize_by_duration` | True | Always report TM_rate for longitudinal comparison; raw TM in supplement |

#### Execution Logic

```
FUNCTION compute_total_movement(parquet_path, params) → TMResult:
    1. Load 12 position columns + 4 artifact columns (one per endpoint's parent joint).
    2. FOR each endpoint e:
         a. mask = ~is_artifact for that joint
         b. pos_clean = positions[e][mask]  # shape: (N_clean, 3)
         c. step_lengths = norm(diff(pos_clean, axis=0), axis=1)  # Euclidean step
         d. tm_e = sum(step_lengths)
    3. TM_total = sum over 4 endpoints
    4. clean_duration = sum(clean_frame_pairs) / fs
    5. TM_rate = TM_total / clean_duration
    6. RETURN TMResult(tm_total_mm, tm_rate_mm_per_s, per_endpoint, clean_duration_s)
```

#### Strategic Crossroads

- **Artifact-pair handling:** A step between a clean frame and an artifact frame can produce a teleportation spike (>100 mm in one step). This spec **skips** any step where either endpoint is artifact-flagged. Alternative: use only contiguous clean segments. Both are valid; the contiguous-segment approach is more conservative.
- **Root-relative vs global:** Root-relative positions remove locomotion (translation of pelvis through space). If Gaga sessions include walking/traveling, root-relative TM captures **limb articulation relative to body center**, not room-level translation. This is the correct choice for creative movement analysis.

#### Risk Points & Consequences

| Risk | Impact | Mitigation |
|------|--------|------------|
| TM scales with session duration | Longer sessions artificially higher TM | Always use TM_rate (duration-normalized) for comparison |
| High-frequency tracking noise inflates step sums | Small jitter accumulated over 19K frames | Data is pre-filtered (Step 04 Butterworth); verify no residual high-frequency noise by checking that median step length > 0.5 mm |
| One endpoint with persistent artifacts | That endpoint contributes fewer steps → its TM is lower | Report per-endpoint TM; flag if any endpoint has >20% artifact |
| Marker swap (left/right confusion) | Massive single-frame jump | Step 04 filtering + artifact flags should catch this; verify no single step > 50 mm |

---

### F3. Endpoint–COM Amplitude (A)

#### Scientific Definition & Defense

> **Thesis-ready:** Endpoint–COM Amplitude measures the mean summed Euclidean distance from four distal endpoints to the whole-body center of mass, quantifying the spatial reach envelope of the body at each instant. Sanchez Martz et al. (2025) found significant amplitude differences between imagery conditions (t(23) = 2.73, p = 0.012), grounding this metric as a sensitive indicator of spatial movement strategy.

**Primary citation:** Sanchez Martz et al. (2025); committee-verified quote (same as TM).  
**Domain shift note:** Sanchez used inertial-derived COM in cm; we use OptiTrack `wbc_com_*` in mm with a `com_reliability_flag` gate.

#### Mathematical Formulation

**Input columns:** Same 12 endpoint position columns as TM, plus `wbc_com_x`, `wbc_com_y`, `wbc_com_z` (mm).

**Per-frame amplitude:**

$$A(t) = \sum_{e \in \{LH, RH, LF, RF\}} \| \mathbf{p}_e(t) - \mathbf{p}_{\text{com}}(t) \|_2 \quad \text{[mm]}$$

**Session summary:**

$$\bar{A}_s = \frac{1}{T_{\text{clean}}} \sum_{t \in \text{clean}} A(t) \quad \text{[mm]}$$

Also report: $A_{\text{median}}$, $A_{\text{95th}}$ (spatial envelope at near-maximum reach), $\sigma_A$ (variability of reach).

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `com_reliability_required` | True | Skip sessions where `com_reliability_flag == "UNRELIABLE"` (missing anthropometrics corrupt COM estimate) |
| `com_reliability_threshold` | 0.90 | From parquet metadata: `com_mass_coverage_pct ≥ 90%` |

#### Execution Logic

```
FUNCTION compute_amplitude(parquet_path, params) → AmplitudeResult:
    1. Load endpoint positions + wbc_com columns + artifact flags.
    2. CHECK com_reliability_flag in parquet metadata.
       IF "UNRELIABLE" → RETURN status="COM_UNRELIABLE", skip.
    3. Build clean_mask = NOT any_endpoint_artifact AND NOT com_artifact (if exists).
    4. FOR each clean frame t:
         A_t = sum of ||p_e(t) - p_com(t)|| for 4 endpoints
    5. A_mean = mean(A_t over clean frames)
    6. A_median, A_95th, A_std = quantiles and spread.
    7. RETURN AmplitudeResult(A_mean, A_median, A_95th, A_std, n_clean_frames)
```

#### Strategic Crossroads

- **COM quality:** If subject anthropometrics are missing or default, `wbc_com_*` uses generic body segment parameters (170 cm, 70 kg). This **corrupts** the COM estimate. The `com_reliability_flag` gate is mandatory, not optional.
- **Root-relative vs global positions:** Endpoint positions are already root-relative; COM is computed in root-relative coordinates. This means A captures limb-to-COM distance **relative to pelvis origin**, which is appropriate for measuring spatial envelope around the body center.

#### Risk Points & Consequences

| Risk | Impact | Mitigation |
|------|--------|------------|
| COM reliability failure | Amplitude values are meaningless | Gate on `com_reliability_flag`; report anthropometric source |
| Foot tracking loss during floor work | Foot-COM distance drops to near zero | Check per-endpoint artifact rates; flag floor-work segments separately if metadata available |
| Amplitude conflates with body size | Taller subjects have higher A | Within-subject longitudinal design eliminates this; never compare A between subjects |

---

### F4. Effective Dimensionality — Participation Ratio (D_eff)

#### Scientific Definition & Defense

> **Thesis-ready:** Effective Dimensionality quantifies how many independent kinematic modes share the movement energy, computed as the Participation Ratio on the PCA eigenvalue spectrum — a standard measure from computational neuroscience (Cunningham & Yu, 2014, *Nature Neuroscience*) applied here to joint angular velocity kinematics. The metric bridges motor behavior and neural population dimensionality analysis: the same mathematical object (covariance eigenvalue concentration) measured on joint kinematics rather than neural spike rates.

**Primary citations:**
- Cunningham & Yu (2014), *Nature Neuroscience* — Participation Ratio in motor cortex population analysis.
- Abbott, Rajan & Sompolinsky (2011), *Neuron* — PR as the correct dimensionality measure.
- Daffertshofer et al. (2004), *Clinical Biomechanics* — Canonical reference for PCA on movement kinematics.

**Defense (re: I≠ / Gini paper):** D_eff uses the **same mathematical inequality logic** as the Gini coefficient (both summarize concentration in a nonnegative allocation), but D_eff operates on **variance proportions across PCA modes** (not time across intensity levels). The I≠ paper demonstrates that Gini-family inequality indices are effective for movement analysis; D_eff extends that principle to the eigenvalue domain.

#### Mathematical Formulation

**Input columns (dynamics branch):** All 19 `{Joint}__zeroed_rel_omega_mag` columns (deg/s).

**Step 0 — Artifact masking:**

$$\text{clean\_mask} = \bigwedge_{j=1}^{19} \neg \text{is\_artifact}_j$$

**Step 1 — Standardization (fit on reference session):**

For reference session (Class 1), compute per-feature mean $\mu_f$ and std $\sigma_f$ over clean frames. Apply same scaler to all sessions:

$$x_{f,t}^{\text{scaled}} = \frac{x_{f,t} - \mu_f}{\sigma_f}$$

**Step 2 — PCA (fit on reference session):**

Fit PCA on scaled reference data: $X_{\text{ref}} \in \mathbb{R}^{T_{\text{ref}} \times 19}$, yielding loading matrix $W \in \mathbb{R}^{K \times 19}$ where $K = 19$.

**Step 3 — Project all sessions:**

$$Y_s = (X_s^{\text{scaled}} - \bar{X}_{\text{ref}}) \cdot W^\top$$

**Step 4 — Per-session variance along each PC:**

$$\lambda_{k,s} = \text{Var}(Y_s[:, k])$$

**Step 5 — Participation Ratio:**

$$p_{k,s} = \frac{\lambda_{k,s}}{\sum_{j=1}^{K} \lambda_{j,s}}, \quad D_{\text{eff}}(s) = \frac{1}{\sum_{k=1}^{K} p_{k,s}^2}$$

**Range:** $D_{\text{eff}} \in [1, K]$. Normalized: $\tilde{D}_{\text{eff}} = D_{\text{eff}} / K \in [1/K, 1]$.

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `n_components` | `min(n_samples, n_features)` = 19 | Full spectrum required for D_eff; truncation underestimates by cutting tail |
| `reference_session` | Class 1 (T1) | Anchors the PCA basis so all sessions are compared in the same coordinate system |
| `scaler` | `StandardScaler` fit on reference only | Prevents future sessions from influencing the scaling; ensures comparable projections |
| `epsilon_deff` | 1e-12 | Numerical guard against division by zero in degenerate spectra |

#### Execution Logic

```
FUNCTION compute_d_eff(parquet_paths_by_session, params) → DeffResult:
    1. Load all sessions' omega_mag columns + artifact flags.
    2. Build clean_mask per session (all-joint AND).
    3. Fit StandardScaler on reference session clean frames.
    4. Scale all sessions with reference scaler.
    5. Fit PCA(n_components=19) on reference scaled data.
    6. FOR each session s:
         a. Y_s = pca.transform(X_s_scaled)    # NOT X @ W^T (must subtract pca.mean_)
         b. var_per_pc = np.var(Y_s, axis=0)
         c. p = var_per_pc / (np.sum(var_per_pc) + eps)
         d. d_eff = 1.0 / (np.sum(p**2) + eps)
         e. d_eff_norm = d_eff / K
    7. RETURN DeffResult(d_eff_per_session, d_eff_norm_per_session, explained_variance_ratio)
```

#### Strategic Crossroads

- **Reference-anchored vs combined-fit PCA:** Reference-anchored (fit on Class 1) ensures that Class 10's D_eff is measured in the **same basis**, making longitudinal comparison valid. Combined-fit PCA (fit on all sessions stacked) lets later sessions influence the basis, potentially masking real changes. **Use reference-anchored.**
- **`pca.transform()` vs manual `X @ W.T`:** These produce **different results** when `pca.mean_ != 0`. Always use `pca.transform()` to ensure consistent centering. This is a documented pitfall in the thesis pipeline.
- **Branch choice (dynamics vs pose vs reach):** For the **primary** narrative, report **dynamics branch** (omega_mag). Pose (rotvec) and reach (lin_rel_p) go in supplement. This avoids 3× multiplicity in claims.

#### Risk Points & Consequences

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reference session is atypical (very noisy or very quiet) | All downstream projections are distorted | Verify reference session has artifact_fraction < 0.20 and duration > 60s |
| Few clean frames in a session | PCA projection unreliable; variance estimates noisy | Require min_clean_fraction ≥ 0.70 (see threshold dictionary) |
| All 19 features highly correlated | D_eff ≈ 1 for all sessions (ceiling effect for stereotypy) | Check: if D_eff < 2 for reference, the dynamics branch may lack dimensionality; consider pose/reach branches |
| New movement modes at Class 10 orthogonal to Class 1 basis | D_eff underestimates true dimensionality (new variance projected onto noise PCs) | Report session-specific D_eff alongside reference-anchored (sensitivity analysis, same as Joint Gini §2.3.4) |

---

### F5. Joint Gini Coefficient

#### Scientific Definition & Defense

> **Thesis-ready:** The Joint Gini coefficient summarizes the inequality in how kinematic variance is distributed across the 19 joints of the skeleton, using PCA-based variance attribution and the standard Gini inequality index. It directly operationalizes the core Gaga pedagogical instruction: dissolve the hierarchy between body parts, shifting from a "specialist" (few joints dominate) to a "democratic" (all joints contribute equally) motor strategy.

**Primary citations:**
- Variance attribution via squared PCA loadings: Jolliffe (2002); Daffertshofer et al. (2004); JcvPCA paper.
- Gini coefficient: Damgaard & Weiner (2000), economics; Wittebolle et al. (2009), ecology.

**Defense (re: I≠ paper):** The I≠ paper (A New Metric for Integrative Analysis of Movement) demonstrates that the Gini coefficient — originally an econometric tool — is a valid and statistically powerful summary for inequality in movement data, specifically that it halved the required sample size for group discrimination compared to alternative intensity metrics. Joint Gini applies the **same inequality tool** to a **different allocation**: instead of time distributed across intensity levels, we measure **variance distributed across joints**. The mathematical machinery is identical; the domain of application differs. This is **analogous use**, not replication.

**One-sentence defense statement:** *"The Gini coefficient is a standard inequality index validated for movement analysis (I≠, halving required sample sizes for group discrimination); we apply it to the nonnegative shares of kinematic variance attributed to each joint after PCA-based attribution, yielding a single summary of how concentrated whole-body movement is in a few joints versus distributed across the skeleton."*

#### Mathematical Formulation

**Input:** PCA results from the **same** reference-anchored PCA as D_eff (shared preprocessing; independent metric computation).

**Step 1 — Per-feature variance attribution:**

$$\alpha_{f,s} = \sum_{k=1}^{K} \lambda_{k,s} \cdot w_{k,f}^2$$

where $\lambda_{k,s}$ = session $s$ variance along PC $k$; $w_{k,f}$ = loading of feature $f$ on PC $k$.

**Step 2 — Aggregate to joints (19 joints):**

Map each feature $f$ to its anatomical joint $j$ (e.g., `LeftArm__zeroed_rel_omega_mag` → `LeftArm`):

$$A_{j,s} = \sum_{f \in \text{joint}_j} \alpha_{f,s}$$

**Step 3 — Normalize to proportions:**

$$\pi_{j,s} = \frac{A_{j,s}}{\sum_{j'=1}^{19} A_{j',s}}$$

**Step 4 — Gini coefficient:**

$$\text{Gini}(s) = \frac{\sum_{i=1}^{n}\sum_{j=1}^{n}|\pi_i - \pi_j|}{2n\sum_{i=1}^{n}\pi_i}$$

Equivalently (sorted form): sort $\pi_1 \leq \pi_2 \leq \cdots \leq \pi_{19}$, then:

$$\text{Gini}(s) = \frac{2\sum_{i=1}^{19} i \cdot \pi_{(i)}}{19 \cdot \sum \pi_{(i)}} - \frac{20}{19}$$

**Range:** $\text{Gini} \in [0, 1]$. 0 = perfectly equal (all joints contribute identically). 1 = maximally unequal (one joint has all variance).

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `n_joints` | 19 | Full skeleton |
| `reference_session` | Class 1 (T1) | Same anchor as D_eff |
| `sensitivity_mode` | Both T1-anchored AND session-specific | Mandatory: check whether Gini decrease is genuine or a T1-basis representation artifact (see Sensitivity Analysis below) |

#### Mandatory Sensitivity Analysis

Compute Joint Gini in **two** modes:

1. **T1-anchored Gini** (primary): Uses T1 PCA loadings for attribution. Comparable across sessions.
2. **Session-specific Gini** (sensitivity): Fits fresh PCA per session; computes Gini from that session's own loadings.

| T1-Anchored | Session-Specific | Inference |
|-------------|-----------------|-----------|
| ↓ Decrease | ↓ Decrease | **Genuine democratization** — both bases agree |
| ↓ Decrease | No change / ↑ | **T1-basis artifact** — new modes diffuse across T1 components |
| No change / ↑ | ↓ Decrease | Cautious — redistribution invisible in T1 basis |
| No change / ↑ | No change / ↑ | **Null finding** |

#### Execution Logic

```
FUNCTION compute_joint_gini(pca_results, session_data, params) → GiniResult:
    1. FROM pca_results: extract loadings W (K×F), per-session var_per_pc.
    2. FOR each session s:
         a. alpha_f = sum_k( var_per_pc[k,s] * W[k,f]^2 )  for each feature f
         b. Map features to joints → A_j for each of 19 joints
         c. pi_j = A_j / sum(A_j)
         d. gini_anchored = gini_coefficient(pi)
    3. FOR session-specific sensitivity:
         a. Fit fresh PCA on session s data alone
         b. Repeat steps 2a-2d with session-specific loadings
         c. gini_native = gini_coefficient(pi_native)
    4. RETURN GiniResult(gini_anchored, gini_native, joint_proportions, sensitivity_flag)
```

#### Risk Points & Consequences

| Risk | Impact | Mitigation |
|------|--------|------------|
| T1-basis artifact (see sensitivity table) | Spurious Gini decrease | Mandatory dual-mode computation; report both |
| Single dominant joint (e.g., Hips artifact) | Gini inflated by one outlier joint | Check per-joint artifact rates; exclude joints with >30% artifact from Gini input |
| Branch choice affects Gini | Dynamics vs pose vs reach give different joint rankings | Report primary branch (dynamics); note differences in supplement |

---

### F6. JcvPCA — Joint Contribution Variation

#### Scientific Definition & Defense

> **Thesis-ready:** JcvPCA quantifies how each joint's contribution to the dominant coordination patterns changed between a reference condition (Class 1) and a test condition (Class 10), providing a per-joint, per-PC matrix of "who reorganized?" JcvPCA is a published methodology for evaluating changes in joint coordination strategies, validated on both simulated and experimental exoskeleton data (JcvPCA paper).

**Primary citation:** "A set of metrics to evaluate changes in joint coordination strategies" — JcvPCA/JsvCRP paper.  
**Committee-verified quote:** *"the JsvCRP, defined as the area between 2 CRP curves, provides a valuable indication of the extent of the changes in coordination strategy."*

#### Mathematical Formulation

**Input columns (pose branch):** All 19 joints × 3 rotvec components = 57 `{Joint}__zeroed_rel_rotvec_{x,y,z}` columns (radians). Convert to degrees as per paper convention.

**Step 1 — Reference PCA (dataset A = Class 1):**

Stack all Class 1 clean frames into $\Theta_A \in \mathbb{R}^{T_A \times 57}$. Center to zero mean (no range normalization per paper).

PCA on $\Theta_A$ yields $m$ PCs with loadings $a_{u,i}$ (loading of PC $u$ on feature $i$).

$m$ selection: $m = \min(N_{90}+1, 10)$, capturing at least 90% variance plus one additional PC. Cap at 10 for tractability.

**Step 2 — Joint Reprojection Weight (JRW):**

Project test dataset B (Class 10) per joint into A's PC basis:

$$\theta^A_{B,i} = R_A \cdot \theta_{B,i}$$

where $R_A = [PC_{A,1}, \ldots, PC_{A,m}]$ is the reference PC frame.

**Step 3 — Second PCA on projected B:**

PCA on the joint-reprojected $\theta^A_B$ yields loadings $b^A_{u,i}$.

**Step 4 — JcvPCA matrix:**

$$\text{JcvPCA}_{u,i} = |a_{u,i}| - |b^A_{u,i}|$$

- **Positive:** Joint $i$ contributed **more** to PC $u$ in the reference than in the test (i.e., the joint **lost** contribution after training).
- **Negative:** Joint $i$ **gained** contribution to that PC after training.

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `m_pcs` | `min(N90 + 1, 10)` | Per paper recommendation: p+1 PCs where p = task DoF; N90+1 as proxy; cap at 10 |
| `center_data` | True | Per paper: center to zero mean |
| `range_normalize` | False | Per paper: do NOT range-normalize — preserves relative joint contribution magnitudes |
| `input_units` | degrees | Paper convention; convert from radians in parquet |

#### Execution Logic

```
FUNCTION compute_jcvpca(ref_parquet, test_parquet, params) → JcvPCAResult:
    1. Load rotvec columns for reference (A) and test (B) sessions.
    2. Convert radians → degrees.
    3. Apply artifact masks; drop artifact frames.
    4. Center A and B to zero mean (A's mean subtracted from both, per paper).
    5. PCA on A → loadings a[u,i], m PCs.
    6. Project B per joint into A's PC frame:
         FOR each joint j (group of 3 columns):
           theta_B_projected[j] = B[j_cols] @ PC_A.T
    7. Stack projected joint trajectories → theta^A_B matrix.
    8. PCA on theta^A_B → loadings b^A[u,i].
    9. JcvPCA[u,i] = |a[u,i]| - |b^A[u,i]|   for u=1..m, i=1..57
    10. Aggregate per joint: JcvPCA_joint[u,j] = mean over 3 rotvec axes of joint j.
    11. RETURN JcvPCAResult(matrix, per_joint_summary, explained_variance_A, explained_variance_B)
```

#### Strategic Crossroads

- **Feature grouping:** The paper uses joint angles directly; we use rotvec triplets. Each joint has 3 features. We can either (a) treat all 57 features independently in the JcvPCA matrix, or (b) aggregate per joint (19 joints) after computing per-feature JcvPCA. Option (b) is more interpretable for the thesis; option (a) preserves per-axis detail. **Recommend: compute at 57 features, aggregate per joint for the main table, keep per-axis detail in supplement.**
- **Number of PCs (m):** Too few → misses real coordination patterns. Too many → includes noise PCs. The N90+1 heuristic is conservative; if N90 is very high (>10), cap at 10 and report.

#### Risk Points & Consequences

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reference session (Class 1) has very different noise than test | JcvPCA reflects noise-floor change, not coordination | Verify comparable artifact rates and clean durations between A and B |
| Centering error (subtracting B's mean instead of A's) | Entire projection is in wrong coordinate system | Code review: verify A's mean is subtracted from both A and B before PCA |
| Small m misses important PCs | Large coordination changes in PC6+ are invisible | Report cumulative explained variance of first m PCs; flag if < 80% |

---

### F7. JsvCRP — Hips–Spine Continuous Relative Phase

#### Scientific Definition & Defense

> **Thesis-ready:** JsvCRP quantifies the change in temporal coordination between the pelvis and lower spine by computing the L¹ area between continuous relative-phase curves from a reference session (Class 1) and a test session (Class 10). This directly operationalizes the Gaga instruction "find the baby" — the re-coupling of the deep axial chain — using a published coordination metric validated on exoskeleton data.

**Primary citation:** JcvPCA/JsvCRP paper — committee-verified quote: *"the JsvCRP, defined as the area between 2 CRP curves, provides a valuable indication of the extent of the changes in coordination strategy. A larger area between the curves indicates a more substantial difference in the joint coordination patterns."*

#### Mathematical Formulation

**Input columns:**

| Signal | Column | Units |
|--------|--------|-------|
| Hips rotation magnitude | `Hips__zeroed_rel_rotmag` | degrees |
| Hips angular velocity magnitude | `Hips__zeroed_rel_omega_mag` | deg/s |
| Spine rotation magnitude | `Spine__zeroed_rel_rotmag` | degrees |
| Spine angular velocity magnitude | `Spine__zeroed_rel_omega_mag` | deg/s |
| Time | `time_s` | seconds |

**Step 1 — Range normalization (per trial):**

For each joint $i \in \{\text{Hips}, \text{Spine}\}$ and each session:

$$\theta_{i,\text{norm}}(t) = \frac{2(\theta_i(t) - \theta_{i,\min})}{\theta_{i,\max} - \theta_{i,\min}} - 1 \in [-1, 1]$$

$$\dot{\theta}_{i,\text{norm}}(t) = \frac{2(\dot{\theta}_i(t) - \dot{\theta}_{i,\min})}{\dot{\theta}_{i,\max} - \dot{\theta}_{i,\min}} - 1 \in [-1, 1]$$

**Step 2 — Phase angle (from position–velocity phase portrait):**

$$\phi_i(t) = \arctan2\!\left(\dot{\theta}_{i,\text{norm}}(t),\; \theta_{i,\text{norm}}(t)\right)$$

**Step 3 — Continuous Relative Phase:**

$$\text{CRP}(t) = \phi_{\text{Spine}}(t) - \phi_{\text{Hips}}(t)$$

Wrap to $[-\pi, \pi]$: $\text{CRP}(t) = \text{atan2}(\sin(\text{CRP}), \cos(\text{CRP}))$.

**Step 4 — Time normalization:**

Resample CRP to 101 points (0%–100% of session duration) using linear interpolation, producing $\text{CRP}_A[0..100]$ and $\text{CRP}_B[0..100]$.

**Step 5 — JsvCRP area:**

$$\text{JsvCRP}_{A,B} = \sum_{k=0}^{100} |\text{CRP}_B[k] - \text{CRP}_A[k]| \cdot \Delta_{\%}$$

where $\Delta_{\%} = 1/100$. Units: radians (or convert to degrees by multiplying by $180/\pi$).

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `n_time_points` | 101 | 0%–100% in 1% steps; standard time normalization |
| `smooth_crp` | True | Optional Savitzky–Golay (window=11, order=3) on CRP before area computation; reduces high-frequency phase noise |
| `min_clean_fraction` | 0.70 | Minimum clean frames for reliable phase portrait |
| `joint_pair` | (Hips, Spine) | Primary pair; arm pairs (LeftArm–LeftForeArm) in supplement |

#### Execution Logic

```
FUNCTION compute_jsvcrp(ref_parquet, test_parquet, params) → JsvCRPResult:
    1. Load rotmag + omega_mag for Hips and Spine, both sessions.
    2. Apply artifact masks (OR of Hips and Spine is_artifact).
    3. FOR each session (A=reference, B=test):
         a. Range-normalize theta and theta_dot to [-1,1] within session.
         b. phi_hips = atan2(theta_dot_hips_norm, theta_hips_norm)
         c. phi_spine = atan2(theta_dot_spine_norm, theta_spine_norm)
         d. CRP = wrap_to_pi(phi_spine - phi_hips)
         e. Resample CRP to 101 points (linear interpolation over normalized time).
    4. area = sum(|CRP_B - CRP_A|) / 100
    5. RETURN JsvCRPResult(area_rad, area_deg, crp_A, crp_B, time_normalized)
```

#### Strategic Crossroads

- **Rotmag (scalar) vs single rotvec axis:** `rotmag` is unsigned (≥ 0), so the phase portrait only covers **two quadrants**. Using a **signed** rotvec axis (e.g., `_rotvec_y` for sagittal flexion) gives a full four-quadrant phase portrait. **Recommendation:** Use `zeroed_rel_rotvec_y` (sagittal component) instead of `rotmag` for the primary analysis; report `rotmag`-based CRP in supplement as sensitivity. Document the axis choice.
- **Mean CRP vs trial-level CRP:** With N=3 and a few sessions per subject, compute CRP per session and compare Class 1 vs Class 10. If multiple recordings exist per class, average CRP curves within class, then compute area between class means.
- **Wrap ambiguity at ±π:** Phase differences near ±π can flip sign between adjacent frames, creating artificial spikes. The `atan2(sin, cos)` wrap handles this correctly; verify no discontinuities in the CRP trace.

#### Risk Points & Consequences

| Risk | Impact | Mitigation |
|------|--------|------------|
| `rotmag` unsigned → half-plane phase portrait | CRP loses directional information | Use signed rotvec axis as primary (see Strategic Crossroads) |
| Low angular velocity magnitude (quiet spine) | Phase angle becomes noise-dominated near origin | Exclude frames where both theta_norm and theta_dot_norm are < 0.05 (near-origin exclusion zone) |
| Session length mismatch | Time normalization stretches/compresses differently | Normalize to 0–100%; report raw duration alongside |
| High-frequency phase jumps | Area inflated by noise | Apply optional SavGol smoothing on CRP before area computation |

---

## Section 2: Success Matrix, Debugging & Failure Protocol

### 2.1 Developer Success Criteria (Technical)

| Feature | Synthetic test | Expected output | Boundary check |
|---------|---------------|-----------------|----------------|
| **ATF** | All-zero velocity → ATF = 0; constant velocity above threshold → ATF = 1.0 | Exact match | 0 ≤ ATF ≤ 1 per joint |
| **TM** | Stationary endpoints (no movement) → TM = 0; constant velocity v → TM = v × duration × 4 endpoints | Within 1% of analytical | TM ≥ 0; TM_rate > 0 if any movement |
| **Amplitude A** | All endpoints at COM → A = 0; endpoints at fixed distance d → A = 4d | Exact match | A ≥ 0 |
| **D_eff** | Identity covariance (equal variance all PCs) → D_eff = K; one-hot covariance → D_eff = 1 | Within eps of K and 1 | 1 ≤ D_eff ≤ K |
| **Joint Gini** | Equal variance all joints → Gini = 0; all variance in one joint → Gini approaches (n-1)/n | Within eps | 0 ≤ Gini ≤ 1 |
| **JcvPCA** | Identical datasets A = B → JcvPCA matrix = 0 | All entries < eps | No constraint on sign |
| **JsvCRP** | Identical CRP curves → area = 0; anti-phase CRP → area = π | Within eps | area ≥ 0 |

### 2.2 Researcher Success Criteria (Scientific)

| Feature | Expected range (Gaga data) | Red flag | Sensitivity check |
|---------|---------------------------|----------|-------------------|
| **ATF** | 0.3–0.9 per joint; whole-body median 0.5–0.8 | ATF > 0.95 for all joints (noise floor too low) or < 0.1 (noise floor too high) | Compare noise floors across sessions: should be stable within-subject |
| **TM** | 50–500 mm/s per endpoint (scaled to session) | TM_rate < 10 mm/s (virtually no movement) or > 2000 mm/s (likely artifact) | Compare per-endpoint rates; check for bilateral symmetry |
| **Amplitude A** | 200–1000 mm mean (depends on body size) | A < 50 mm (all limbs near COM, improbable) | Check A_95th vs A_mean ratio: should be 1.5–3× |
| **D_eff** | 2–10 for dynamics branch | D_eff > 15 (near K=19; possibly noise-driven flat spectrum) or < 1.5 | Compare to N90; D_eff and N90 should be positively correlated |
| **Joint Gini** | 0.15–0.65 | Gini > 0.8 (single-joint domination; check artifact) or < 0.05 (unrealistic equality) | T1-anchored vs session-specific sensitivity must agree in direction |
| **JcvPCA** | Per-joint absolute values 0.01–0.30 | All entries < 0.001 (no detectable change) or > 0.5 (likely data issue) | Check explained variance of reference PCA; must be > 70% for first m PCs |
| **JsvCRP** | 0.1–2.0 radians (depends on coupling change magnitude) | Area > 3.0 rad (extreme; check for phase-wrap errors) or exactly 0 (identical sessions unlikely) | Verify CRP curves are smooth after optional filtering |

### 2.3 Technical Debugging Checklist

```
FOR EACH FEATURE:
  [ ] Output is finite (no NaN, no Inf)
  [ ] Output is in expected range (see table above)
  [ ] Artifact frames are excluded (verify: count clean frames vs total)
  [ ] Per-session outputs sorted chronologically (Class 1 → Class 10)
  [ ] Duration-dependent metrics are normalized (TM_rate, not raw TM)
  [ ] Schema columns exist in parquet (validate before computation)
  [ ] Units are correct (mm not m; deg/s not rad/s where specified)
  [ ] Random seed set for any stochastic operations (bootstrap, subsampling)
```

### 2.4 Feature Fit Check — The Failure Protocol

**When a feature shows zero sensitivity across all 3 subjects despite correct technical implementation:**

```
STEP 1: Verify technical correctness
  - Run synthetic test (§2.1). If synthetic fails → BUG, not theoretical misfit.
  - Check that input columns have meaningful variance (std > 0).

STEP 2: Check data quality
  - Artifact fraction per session. If > 30% in critical sessions → data limitation.
  - Session durations. If < 60 seconds → insufficient data.
  - Noise floor audit (for ATF): are thresholds reasonable?

STEP 3: Check parameter sensitivity
  - Vary key parameters ±50% (window sizes, thresholds, n_bins).
  - If metric becomes sensitive with different params → report as parameter-dependent.

STEP 4: Theoretical misfit assessment
  - Does the metric's predicted direction assume a mechanism Gaga doesn't activate?
  - Example: JsvCRP Hips–Spine assumes axial re-coupling. If Gaga classes
    focused on extremity work → Hips–Spine CRP may not change.
  - Action: Report as "null finding for this joint pair under this class sequence"
    in Results. Do NOT suppress. Add to Discussion: "the specific Gaga
    curriculum in these 10 classes may not have targeted axial coordination."

STEP 5: Decision
  IF synthetic passes AND data quality OK AND parameters explored AND still null:
    → KEEP in results as a null finding.
    → Label: "Feature X showed no detectable Class 1 → Class 10 change
       in any subject (delta < [threshold]; see Table Y)."
    → Do NOT drop from the paper. A pre-registered null is informative.
```

---

## Section 3: Companion Metrics & Confound Controls

Every primary feature has one pre-specified companion that addresses the most obvious confound interpretation.

| Primary feature | Companion (report alongside) | What it rules out |
|-----------------|------------------------------|-------------------|
| **ATF** | Session artifact fraction + clean duration (s) | "More active" is artifact of shorter/cleaner recording |
| **ATF peripheral** | Median `*_lin_vel_rel_mag` over peripheral joints | ATF ↑ only because noise floor dropped, not real activation |
| **TM** | Clean duration (s) + session-level mean speed | "More path" is just longer recording or faster overall |
| **Amplitude A** | Mean endpoint speed (mm/s) | "Reaching further" is just moving faster, not actually extending |
| **D_eff** | N90 (same branch) + mean RMS omega_mag | "Flatter spectrum" from global amplitude rescaling |
| **Joint Gini** | T1-anchored vs session-specific sensitivity analysis | Gini ↓ is a T1-basis artifact, not genuine democratization |
| **JcvPCA** | Explained variance of reference PCA (% in first m PCs) | Loading changes are in noise PCs that carry no real variance |
| **JsvCRP** | Near-origin frame exclusion count + CRP smoothness | Phase noise near zero velocity inflates area |

---

## Appendix: Schema Column Quick Reference

### Velocity & Position Columns (per joint)

| Column | Units | Use |
|--------|-------|-----|
| `{J}__lin_vel_rel_mag` | mm/s | ATF noise floor input |
| `{J}__lin_rel_px`, `_py`, `_pz` | mm | TM, Amplitude, JcvPCA (reach branch) |
| `{J}__zeroed_rel_omega_mag` | deg/s | D_eff, Joint Gini (dynamics branch) |
| `{J}__zeroed_rel_rotvec_x`, `_y`, `_z` | radians | JcvPCA (pose branch) |
| `{J}__zeroed_rel_rotmag` | degrees | JsvCRP angle input |
| `{J}__is_artifact` | bool | All features — artifact exclusion mask |
| `wbc_com_x`, `_y`, `_z` | mm | Amplitude A |
| `time_s` | seconds | All features — time axis |

### Joint Inventory (19 joints)

Hips, Spine, Spine1, Chest, Neck, Head, LeftShoulder, RightShoulder, LeftArm, RightArm, LeftForeArm, RightForeArm, LeftHand, RightHand, LeftUpLeg, RightUpLeg, LeftLeg, RightLeg, LeftFoot, RightFoot.

> **Note:** 20 names listed but Chest is often aliased to Spine1 in some skeleton configs. Verify against your `skeleton_schema.json`. The thesis pipeline uses 19 unique joints for ATF/Gini/D_eff.

---

*End of Methodology Specification.*
