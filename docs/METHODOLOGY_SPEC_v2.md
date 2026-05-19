# Methodology Specification v2 — Streamlined Feature Extraction Pipeline
## Technical Implementation Document for Longitudinal Motor Phenotyping in Gaga Dance

**Document Class:** Master Implementation Specification (Revised)  
**Pipeline Version:** v3.0  
**Author:** Research Software Architecture — Gaga Motion Analysis Project  
**Date:** 2026-04-06  
**Study:** *Longitudinal Kinematic Case Study of Gaga Improvisation (N=3 pilot)*  
**Input:** `derivatives/step_06_kinematics/{RUN_ID}__kinematics_master.parquet` at 120 Hz  
**Supersedes:** `METHODOLOGY_SPEC.md` (v2.0, 7-feature architecture)

> **How to use this document.** This is the self-contained execution manual for implementing, debugging, and defending the **four retained feature blocks** (F1 ATF, F2 TM, F4 D_eff, F5 Joint Gini — three **tier-1 primaries** and one **tier-2 supplementary** block per [Section 0](#section-0-rationale--why-four-features)). Each block reads from the master Parquet and produces one scalar (or small struct) per (subject, session) pair. A **reference Jupyter notebook layout** is specified in [§3.1 Notebook implementation contract](#31-notebook-implementation-contract). When code and this document conflict, this document defines intent. **Scope:** v2 does **not** specify legacy dashboard controls for metrics outside this spec (e.g. state-space entropy, centroid displacement, Sample Entropy, RQA); the v2 orchestrating notebook requires **parity** of the **four parameter dicts** (`CONFIG`, `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5`) with the Implementation Parameters tables for those blocks, plus reliability gates and optional exploratory UI described here.

---

## Table of Contents

- [Section 0: Rationale — Why Four Features](#section-0-rationale--why-four-features)
- [Section 1: Tier 1 — Primary Inference Metrics](#section-1-tier-1--primary-inference-metrics)
  - [F1. Active Time Fraction (ATF)](#f1-active-time-fraction-atf)
  - [F4. Effective Dimensionality (D_eff)](#f4-effective-dimensionality-d_eff)
  - [F2. Total Movement (TM)](#f2-total-movement-tm)
- [Section 2: Tier 2 — Supplementary Evidence & Controls](#section-2-tier-2--supplementary-evidence--controls)
  - [F5. Joint Gini Coefficient](#f5-joint-gini-coefficient)
  - [F5.1 Core-Periphery Integration (A/P Ratio)](#f51-core-periphery-integration-ap-ratio)
  - [Reliability Gates](#reliability-gates)
  - [T2 Isolation Gate (Training vs. Psychedelic Disambiguation)](#t2-isolation-gate-training-vs-psychedelic-disambiguation)
  - [Block 0 — Constraint register & quality-table specification](#block-0--constraint-register--quality-table-specification)
- [Section 3: Data Flow & Pipeline Rules](#section-3-data-flow--pipeline-rules)
  - [3.1 Notebook implementation contract](#31-notebook-implementation-contract)
    - [Notebook preamble — implementation cautions (read first)](#notebook-preamble--implementation-cautions-read-first)
    - [Recommended export bundle (thesis lock-in)](#recommended-export-bundle-thesis-lock-in)
  - [3.2 Session time windowing (`apply_time_window`)](#32-session-time-windowing-apply_time_window)
  - [3.3 Implementation architecture — library, notebook, legacy isolation](#33-implementation-architecture--library-notebook-legacy-isolation)
  - [3.4 Information-first workflow and analyst authority](#34-information-first-workflow-and-analyst-authority)
  - [3.5 Per-block information, tuning contract, and interactive UX](#35-per-block-information-tuning-contract-and-interactive-ux)
  - [3.6 PCA input dimension and joint-level artifact conflict (19-feature rule)](#36-pca-input-dimension-and-joint-level-artifact-conflict-19-feature-rule)
  - [3.7 Tech stack recommendations](#37-tech-stack-recommendations)
  - [3.8 Implementation phasing — MVP scope and deferred items](#38-implementation-phasing--mvp-scope-and-deferred-items)
- [Section 4: Success Matrix, Debugging & Failure Protocol](#section-4-success-matrix-debugging--failure-protocol)
  - [4.5 Single-Session Confidence Intervals (Block Bootstrap) — summary](#45-single-session-confidence-intervals-block-bootstrap--summary)
  - [4.6 Conflict register, automated audit tiering, and analyst acknowledgment](#46-conflict-register-automated-audit-tiering-and-analyst-acknowledgment)
- [Section 5: Companion Metrics & Confound Controls](#section-5-companion-metrics--confound-controls)
  - [5.1 Exploratory visualization — ATF vs joint variance share (optional)](#51-exploratory-visualization--atf-vs-joint-variance-share-optional)
- [Appendix A: Schema Column Quick Reference](#appendix-a-schema-column-quick-reference)
  - [A.1 Normative joint name table (v2 / Parquet prefixes)](#a1-normative-joint-name-table-v2--parquet-prefixes)
- [Appendix B: Master Execution Prompt (verbatim)](#appendix-b-master-execution-prompt-verbatim)
- [Appendix C: Thesis Result Package — export manifest & provenance](#appendix-c-thesis-result-package--export-manifest--provenance)
- [Appendix D: Block Bootstrap — Full Protocol](#appendix-d-block-bootstrap--full-protocol)
  - [D.1 Within-session block bootstrap](#d1-within-session-block-bootstrap)
  - [D.2 Longitudinal delta bootstrap (optional)](#d2-longitudinal-delta-bootstrap-optional)
- [Appendix E: T2 Isolation Gate — Full Protocol](#appendix-e-t2-isolation-gate--full-protocol)

---

## Section 0: Rationale — Why Four Features

### The problem with the previous seven-feature architecture

Version 1 of this specification (`METHODOLOGY_SPEC.md`) defined seven features organized in three narrative layers: physical expansion (ATF, TM, A), structural diversification (D_eff, Joint Gini), and coordination reorganization (JcvPCA, JsvCRP). An independent critical audit exposed three structural liabilities:

1. **Feature redundancy in Layer 1.** Both TM (cumulative endpoint path length) and A (endpoint–COM amplitude) quantify "how much the endpoints move." Their within-session correlation is high, and retaining both inflates the apparent number of independent tests without adding proportional inferential value. This is a pilot with N=3 subjects; every additional comparison must earn its place.

2. **Fragile coordination metrics in Layer 3.** JcvPCA requires a two-stage PCA (fit reference, reproject test, re-fit), making it highly sensitive to noise differences between the reference and test sessions. JsvCRP on unsigned `rotmag` produces a degenerate two-quadrant phase portrait; even with a signed-axis fix, the continuous relative phase between Hips and Spine is dominated by measurement noise when angular velocities are small — a common state in Gaga improvisation, which includes stillness, floor work, and slow exploratory sequences. At N=3 with variable session quality, the probability of producing interpretable JsvCRP values is low, and the risk of reporting noise as coordination change is high.

3. **Statistical multiplicity.** Seven features across three subjects, each with multiple sessions and three PCA branches, generates dozens of comparisons. For a descriptive pilot, this diffuses the narrative without statistical correction to justify it.

### The streamlined architecture

This revision retains **four features in two tiers** that map directly onto two Gaga-pedagogy questions:

| Tier | Feature | Pedagogy question | Math object |
|------|---------|-------------------|-------------|
| **Primary** | **F1: ATF** | "Are dormant joints awakening?" | Threshold-crossing rate per joint |
| **Primary** | **F4: D_eff** | "Are stereotyped habits dissolving?" | Participation ratio on PCA eigenvalues |
| **Primary** | **F2: TM** | "Is the body covering more ground?" | Cumulative endpoint path length |
| **Supplementary** | **F5: Joint Gini** | "Which joints explain the D_eff change?" | Gini on PCA-attributed joint variance |

**Dropped features and rationale:**

| Feature | Reason for removal |
|---------|--------------------|
| **F3: Amplitude A** | Redundant with TM for the "expansion" narrative; depends on COM tracking quality (`com_reliability_flag`), which introduces a session-exclusion risk that TM avoids entirely. TM requires only endpoint positions. |
| **F6: JcvPCA** | Two-stage PCA is unstable at pilot scale; loading-difference matrix is illustrative but not inferentially robust with N=3. The same "who changed?" story is partially told by the per-joint breakdown available within Joint Gini's variance attribution. |
| **F7: JsvCRP** | Phase-portrait noise dominance during low-velocity segments; unsigned `rotmag` degeneracy; session-length normalization artifacts. High probability of garbage-in/garbage-out at N=3. |

### What TM over A buys us

TM (Total Movement) is retained over A (Amplitude) for two reasons:

1. **No COM dependency.** TM uses only root-relative endpoint positions (`{Joint}__lin_rel_p{x,y,z}`). It is never gated or degraded by missing anthropometrics, unreliable COM mass coverage, or foot-tracking loss during floor work. Every session that passes basic artifact thresholds produces a valid TM.

2. **Cleaner confound structure.** TM's primary confound — session duration — is neutralized by duration normalization (TM_rate). A's primary confound — movement speed — is harder to isolate because amplitude conflates reach distance with tempo. For a pilot, the simpler confound story is preferable.

### The narrative sentence

*"Across 10 Gaga classes, the dancer activates more of the body (ATF ↑), covers more distance with the extremities (TM ↑), and distributes movement energy across more independent modes (D_eff ↑), shifting from a specialist motor hierarchy toward a democratic engagement strategy (Gini ↓)."*

---

### Parameter Namespace Consolidation (v3.0)

This revision consolidates the former eight parameter namespaces into **four**:

| Consolidated dict | Former dicts merged | Scope |
|-------------------|---------------------|-------|
| **`CONFIG`** | `PARAMS_GLOBAL` + `PARAMS_GATES` + `PARAMS_LONGITUDINAL` | Cross-cutting: gate thresholds, time windows, session registry, longitudinal flags, bootstrap master seed, `params_locked` |
| **`PARAMS_F1`** | (unchanged) | ATF-specific: noise floor, artifact thresholds, bootstrap toggle |
| **`PARAMS_F2`** | (unchanged) | TM-specific: segment length, normalization, bootstrap toggle |
| **`PARAMS_PCA_F4_F5`** | `PARAMS_PCA` + `PARAMS_F4` + `PARAMS_F5` | Shared PCA engine, D_eff, Joint Gini, A/P Ratio, session-native sensitivity modes, bootstrap toggle |

**Rationale:** The previous eight-namespace scheme created cognitive overhead disproportionate to the system’s four-feature scope. `PARAMS_F4` was effectively an alias of `PARAMS_PCA` (both consumed by the same `PCAEngine`). `PARAMS_GLOBAL`, `PARAMS_GATES`, and `PARAMS_LONGITUDINAL` all held cross-cutting settings that the analyst needed to review together. Consolidation reduces the parameter surface without losing any tunable.

**Implementation:** `CONFIG` may use flat keys or nested sub-dicts (e.g. `CONFIG['gates']`, `CONFIG['longitudinal']`) at the implementer’s discretion; the normative requirement is that **one import and one dict** provides all cross-cutting settings.

---

## Section 1: Tier 1 — Primary Inference Metrics

### Architecture Principles

1. **One scalar per session.** Each feature produces one primary number (or a small fixed-size struct) per (subject, session) pair. Longitudinal comparison is always `metric(Class_10) − metric(Class_1)`.
2. **NaN-safe by design.** Every computation explicitly handles artifact frames via the `{Joint}__is_artifact` boolean columns. Artifact frames are **excluded** before any aggregation — never interpolated, never zeroed.
3. **Parameter externalization.** All tunable parameters are defined in a `params` dict at the top of each module. No magic numbers embedded in computation logic.
4. **Anti-double-dipping rule.** D_eff (F4) and Joint Gini (F5) share the **identical** internal PCA pipeline — the same `StandardScaler`, the same `pca.fit()`, the same `pca.transform()` call. They are two read-outs of one mathematical event. This is enforced architecturally: a single `PCAEngine` object is instantiated once and passed to both feature extractors. See [Section 3: Data Flow](#section-3-data-flow--pipeline-rules).

---

### F1. Active Time Fraction (ATF)

#### Scientific Definition & Defense

> **Thesis-ready:** Active Time Fraction quantifies the proportion of time each joint generates kinematic output above its session-specific noise floor, providing a full-body engagement profile that directly operationalizes the Gaga instruction to "find the body parts you habitually ignore." ATF is the least epistemologically risky metric in this framework — it is a threshold-crossing rate, a concept that appears in virtually every domain of movement science.

**Primary citations:** Movement quantity (Roetenberg et al., 2007); EMG recruitment duration analog (Thoroughman & Shadmehr, 2000); session-adaptive noise floor from pipeline Step 05 calibration logic.

**Gaga-pedagogy anchor:** Gaga teachers explicitly instruct practitioners to "wake up" neglected body parts — to move the spine independently of the arms, to articulate individual toes, to find the shoulder blades. ATF is the direct kinematic translation of that instruction: a joint that was below its noise floor at Class 1 and rises above it at Class 10 has, in Gaga terms, been "found." The per-joint profile and the axial/peripheral group breakdown make this mapping specific rather than merely global.

#### Mathematical Formulation

**Input columns:** `{Joint}__lin_vel_rel_mag` (mm/s), `{Joint}__is_artifact` (bool), for all 19 joints.

**Step 1 — Session-adaptive noise floor.** For each joint $i$ and session $s$:

$$V_{i,s} = \text{compute\_noise\_floor}(v_i, \text{cfg})$$

> **Import directive (v3.0):** `compute_noise_floor` is imported from **`src/pulsicity.py`** — do not reimplement. See [§3.3 Noise-floor import](#fresh-code-mandate-v30).

Three-phase guard:
- Phase A: Detect quietest 2-second static window; use its mean velocity. **Implementation note:** sliding-window minima may use **pandas** / **NumPy** rolling reductions; **`scipy.signal`** is **optional** and not required for v2.
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
| Axial | Hips, Spine, Spine1, Neck, Head | Core engagement (same five as **Axial** in [A.1](#a1-normative-joint-name-table-v2--parquet-prefixes); no `Chest` column — use **Spine1** for mid-thorax) |
| Peripheral | LeftForeArm, LeftHand, RightForeArm, RightHand, LeftFoot, RightFoot | Distal awakening |
| Transitional | LeftShoulder, RightShoulder, LeftArm, RightArm, LeftUpLeg, RightUpLeg, LeftLeg, RightLeg | Bridge |

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
| `run_bootstrap` | `False` | If `True`, run [Appendix D](#appendix-d-block-bootstrap--full-protocol) CIs for ATF |
| `bootstrap_block_frames` | `240` | Block length ($L$) when `run_bootstrap` |
| `bootstrap_n_draws` | `1000` | $B$ replicates when `run_bootstrap` |
| `bootstrap_ci_level` | `0.95` | Percentile CI when `run_bootstrap` |
| `bootstrap_seed` | e.g. `42` | RNG seed for reproducibility |
| `noise_floor_override_mms_by_joint` | `{}` (empty dict) | **Optional.** Per-joint manual floor overrides (mm/s), keyed by schema joint name. Use **only** after the noise-floor audit ([§4.6](#46-conflict-register-automated-audit-tiering-and-analyst-acknowledgment), F1 row) and analyst review; must be serialized in exports. |

#### Noise-floor audit (mandatory structured output per session)

For each session, F1 exports (table or nested columns) **per joint**:

- **`noise_floor_method`:** `static` (Phase A) vs `percentile_fallback` (Phase B) vs `override` if `noise_floor_override_mms_by_joint` is set for that joint.
- **`noise_floor_mms`:** Final threshold used (after guards and optional override).
- **Integrity:** Phase A/B thresholds must be computed **only** on **clean** frames (`a_i(t)=0` for that joint); never on raw rows that include artifact spikes for the percentile path.

**Auto-flag (recommended):** Flag joints for review when Phase B is used, when the floor exceeds `static_baseline_guard_mms` unexpectedly, or when an override materially exceeds the automated estimate — document thresholds in `PARAMS_F1` if implemented (e.g. `noise_floor_review_flag_rules`).

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

#### Risk Assessment

| Risk | Severity | Impact | Mitigation |
|------|----------|--------|------------|
| Noise floor too low (tremor-free tracking) | Medium | ATF inflated; near 1.0 for all joints | Absolute minimum 1.0 mm/s guard; report noise floor per joint |
| High artifact rate in one session | Medium | Denominator shrinks; ATF may become unreliable | Exclude if artifact_fraction > 0.30; soft warn above 0.20 |
| Session duration mismatch | Low | Longer sessions may differ due to fatigue/warm-up | Report clean_duration_s alongside ATF |
| OptiTrack dropout on specific joint | Medium | Systematic NaN → artificial low ATF for that joint | Check per-joint NaN rates; flag if >10% NaN on any joint |

**N-survivability rating: LOW RISK.** ATF is a per-joint threshold-crossing rate. It requires no embedding, no projection, no reference basis, and no minimum time-series length beyond a few hundred frames. It is robust at any N.

---

### F4. Effective Dimensionality — Participation Ratio (D_eff)

#### Scientific Definition & Defense

> **Thesis-ready:** Effective Dimensionality quantifies how many independent kinematic modes share the movement energy, computed as the Participation Ratio on the PCA eigenvalue spectrum — a standard measure from computational neuroscience (Cunningham & Yu, 2014, *Nature Neuroscience*) applied here to joint angular velocity kinematics. The metric bridges motor behavior and neural population dimensionality analysis: the same mathematical object (covariance eigenvalue concentration) measured on joint kinematics rather than neural spike rates.

**Primary citations:**
- Cunningham & Yu (2014), *Nature Neuroscience* — Participation Ratio in motor cortex population analysis.
- Abbott, Rajan & Sompolinsky (2011), *Neuron* — PR as the correct dimensionality measure.
- Daffertshofer et al. (2004), *Clinical Biomechanics* — Canonical reference for PCA on movement kinematics.

**Gaga-pedagogy anchor:** Gaga training targets the dissolution of habitual coordination patterns — breaking the dominance of "favorite" movement strategies and replacing them with a broader repertoire of kinematic modes. D_eff translates this directly: a motor system locked into one dominant coordination pattern (PC1 explains 80%+ of variance) has $D_{\text{eff}} \approx 1$; a system using many patterns equally has $D_{\text{eff}} \to K$. The predicted Gaga training effect is $D_{\text{eff}}(Class_{10}) > D_{\text{eff}}(Class_1)$: more independent modes, less stereotypy.

**Defense (re: I≠ / Gini paper):** D_eff uses the **same mathematical inequality logic** as the Gini coefficient (both summarize concentration in a nonnegative allocation), but D_eff operates on **variance proportions across PCA modes** (not time across intensity levels). The I≠ paper demonstrates that Gini-family inequality indices are effective for movement analysis; D_eff extends that principle to the eigenvalue domain.

#### Mathematical Formulation

**Input columns (dynamics branch):** All 19 `{Joint}__zeroed_rel_omega_mag` columns (deg/s).

**Step 0 — Artifact masking:**

$$\text{clean\_mask} = \bigwedge_{j=1}^{19} \neg \text{is\_artifact}_j$$

Only frames where **all** 19 joints are clean are included. This guarantees that PCA operates on complete observation vectors with no imputation.

**Step 1 — Standardization (fit on reference session only):**

For reference session (Class 1), compute per-feature mean $\mu_f$ and std $\sigma_f$ over clean frames. Apply the same frozen scaler to all sessions:

$$x_{f,t}^{\text{scaled}} = \frac{x_{f,t} - \mu_f}{\sigma_f}$$

**Step 2 — PCA (fit on reference session only):**

Fit PCA on scaled reference data: $X_{\text{ref}} \in \mathbb{R}^{T_{\text{ref}} \times 19}$, yielding loading matrix $W \in \mathbb{R}^{K \times 19}$ where $K = 19$.

**Step 3 — Project all sessions using `pca.transform()`:**

$$Y_s = \texttt{pca.transform}(X_s^{\text{scaled}})$$

This internally computes $(X_s^{\text{scaled}} - \texttt{pca.mean\_}) \cdot W^\top$. Always use `pca.transform()`, never manual matrix multiplication, to prevent centering mismatches.

**Step 4 — Per-session variance along each PC:**

$$\lambda_{k,s} = \text{Var}(Y_s[:, k])$$

**Step 5 — Participation Ratio:**

$$p_{k,s} = \frac{\lambda_{k,s}}{\sum_{j=1}^{K} \lambda_{j,s}}, \quad D_{\text{eff}}(s) = \frac{1}{\sum_{k=1}^{K} p_{k,s}^2}$$

**Range:** $D_{\text{eff}} \in [1, K]$. Normalized: $\tilde{D}_{\text{eff}} = D_{\text{eff}} / K \in [1/K, 1]$.

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `n_components` | `min(n_samples, n_features)` = 19 | Full spectrum required for D_eff; truncation underestimates by cutting tail |
| `kinematic_branch` | `dynamics` | **Primary narrative:** `dynamics` — 19 × `{Joint}__zeroed_rel_omega_mag` (deg/s). Alternatives for **sensitivity only:** `pose` (e.g. `rotvec`-based features, 57-D) or `reach` (e.g. `lin_rel_p`, 57-D). Each branch requires its **own** `StandardScaler` + `PCA` fit and **`PCAEngine`**; do not mix branches in one anchored basis. Expose in **`PARAMS_PCA_F4_F5['kinematic_branch']`**; thesis tables must label the branch. |
| `reference_session` | Class 1 (T1) | Anchors the PCA basis so all sessions are compared in the same coordinate system |
| `scaler` | `StandardScaler` fit on reference only | Prevents future sessions from influencing the scaling |
| `epsilon_deff` | 1e-12 | Numerical guard against division by zero in degenerate spectra |
| `min_clean_fraction` | 0.70 | Minimum fraction of all-joint-clean frames required for reliable PCA |
| `run_bootstrap` | `False` | If `True`, run [Appendix D](#appendix-d-block-bootstrap--full-protocol) CIs for $D_{\text{eff}}$ (frozen PCA) |
| `bootstrap_block_frames` | `240` | Block length ($L$) when `run_bootstrap` |
| `bootstrap_n_draws` | `1000` | $B$ replicates when `run_bootstrap` |
| `bootstrap_ci_level` | `0.95` | Percentile CI when `run_bootstrap` |
| `bootstrap_seed` | e.g. `42` | RNG seed for reproducibility |

#### Execution Logic

```
FUNCTION build_pca_engine(parquet_paths_by_session, params) → PCAEngine:
    1. Load all sessions' feature columns per params.kinematic_branch (default: 19 × zeroed_rel_omega_mag) + artifact flags.
    2. Build clean_mask per session (all-joint AND).
    3. Fit StandardScaler on reference session clean frames → scaler.
    4. Scale all sessions with frozen scaler.
    5. Fit PCA(n_components=19) on reference scaled data → pca.
    6. FOR each session s:
         a. Y_s = pca.transform(X_s_scaled)
         b. var_per_pc[s] = np.var(Y_s, axis=0)
    7. RETURN PCAEngine(scaler, pca, Y_per_session, var_per_pc)
    
FUNCTION compute_d_eff(pca_engine, params) → DeffResult:
    1. FOR each session s:
         a. p = var_per_pc[s] / (np.sum(var_per_pc[s]) + eps)
         b. d_eff = 1.0 / (np.sum(p**2) + eps)
         c. d_eff_norm = d_eff / K
    2. RETURN DeffResult(d_eff_per_session, d_eff_norm_per_session, 
                         explained_variance_ratio, n90_per_session)
```

> **Anti-double-dipping note:** `build_pca_engine()` is called **once**. Its output is passed to both `compute_d_eff()` and `compute_joint_gini()`. There is no second PCA fit for the T1-anchored pathway. See Section 3.

#### Strategic Crossroads

- **Reference-anchored vs combined-fit PCA:** Reference-anchored (fit on Class 1) ensures that Class 10's D_eff is measured in the **same basis**, making longitudinal comparison valid. Combined-fit PCA (fit on all sessions stacked) lets later sessions influence the basis, potentially masking real changes. **Use reference-anchored.**
- **`pca.transform()` vs manual `X @ W.T`:** These produce **different results** when `pca.mean_ != 0`. Always use `pca.transform()` to ensure consistent centering. This is a documented pitfall.
- **Branch choice:** For the **primary** narrative, report the **dynamics branch** (`omega_mag`, 19 features). Pose (`rotvec`, 57 features) and reach (`lin_rel_p`, 57 features) go in a supplement if desired. This avoids multiplicity in claims. **`PARAMS_PCA_F4_F5['kinematic_branch']`** must match the columns loaded in step 1 of `build_pca_engine`; changing branches changes $K$ and invalidates comparison with a dynamics-based reference basis.

#### Risk Assessment

| Risk | Severity | Impact | Mitigation |
|------|----------|--------|------------|
| Reference session is atypical | High | All downstream projections are distorted | Verify reference session has artifact_fraction < 0.20 and duration > 60s |
| Few clean frames in a session | Medium | Variance estimates noisy | Require min_clean_fraction ≥ 0.70 |
| All features highly correlated | Low | D_eff ≈ 1 for all sessions (ceiling stereotypy) | Check: if D_eff < 2 for reference, consider supplementary branch |
| New modes at Class 10 orthogonal to Class 1 basis | Medium | D_eff underestimates true dimensionality | Report session-specific D_eff alongside reference-anchored as sensitivity |

**N-survivability rating: MEDIUM RISK.** PCA requires enough clean frames for a stable covariance estimate. With ~14,000–19,000 clean frames at 120 Hz and 19 features, the sample-to-feature ratio exceeds 700:1, which is well above PCA stability thresholds. The risk is not frame count but **reference-session quality**: if Class 1 is anomalous, all downstream projections are distorted. Mitigation: verify reference session quality gates before running the pipeline.

#### Mandatory Dual-Mode Sensitivity Analysis (D_eff)

Parallel to the Joint Gini dual-mode check ([§F5](#f5-joint-gini-coefficient)), D_eff is reported in **two** modes to guard against the orthogonal-mode blind spot:

1. **T1-anchored D_eff** (primary): Uses the shared `PCAEngine` (reference-fitted `StandardScaler` + `PCA`). Projects session $s$ into the T1 basis via `pca.transform()`, computes per-PC variance, then Participation Ratio. Comparable across sessions.
2. **Session-specific D_eff** (sensitivity): Fits a **fresh** `StandardScaler` + `PCA` on session $s$ alone; computes D_eff from that session's own eigenvalues. Not directly comparable across sessions, but detects new kinematic modes that are **orthogonal** to the T1 basis and therefore invisible to the anchored path.

| T1-Anchored | Session-Specific | Inference |
|-------------|-----------------|-----------|
| ↑ Increase | ↑ Increase | **Genuine expansion** — both bases detect more independent modes |
| ↑ Increase | No change / ↓ | **T1-basis diffusion artifact** — variance redistributes across T1 PCs but does not represent new independent structure |
| No change / ↓ | ↑ Increase | **Orthogonal new modes** — Class 10 has structure invisible in T1's coordinate system; report as finding, do not suppress |
| No change / ↓ | No change / ↓ | **Null finding** — no dimensionality expansion detected |

**Implementation control:** Toggle via **`CONFIG['run_session_native_deff']`** (default **`True`**). If **`False`**, skip session-native PCA fits for D_eff; set **`session_native_deff_skipped=True`** in F4 exports and `run_metadata.json`. Session-native D_eff uses the **same** fresh-PCA-per-session machinery as F5's session-native Gini — share the fit when both are enabled.

---

### F2. Total Movement — Endpoint Path Length (TM)

#### Scientific Definition & Defense

> **Thesis-ready:** Total Movement quantifies the cumulative Euclidean distance traveled by four distal endpoints (both hands, both feet) in root-relative coordinates, providing a direct, physically interpretable measure of overall movement quantity. Sanchez Martz et al. (2025) found significant TM differences between imagery conditions in professional dancers (Wilcoxon S = 68, p = 0.0497), establishing TM as a sensitive kinematic summary for creative-movement contrasts.

**Primary citation:** Sanchez Martz et al. (2025) — *Unlocking Creative Movement with Inertial Technology*.  
**Committee-verified quote:** *"significant measurable effects of the condition on postural parameters (Table 2, Figure 2)."*

**Gaga-pedagogy anchor:** Gaga instruction repeatedly directs practitioners to "use the space," to "let the movement travel," and to extend limbs into unfamiliar spatial territory. TM is the simplest possible quantification of whether the extremities are in fact traveling more. It requires no model, no projection, no basis — only position differences summed over time. It is the "odometer reading" of the hands and feet.

**Why TM over Amplitude (A):** Both TM and A quantify spatial expansion. TM is preferred for this pilot because (1) it does not depend on whole-body COM tracking, eliminating an entire class of data-quality exclusions; and (2) its primary confound (session duration) is neutralized by a simple rate normalization, whereas A's confound (movement speed) is harder to disentangle.

#### Mathematical Formulation

**Input columns (4 endpoints × 3 axes = 12 columns):**

| Endpoint | X | Y | Z |
|----------|---|---|---|
| Left Hand | `LeftHand__lin_rel_px` | `LeftHand__lin_rel_py` | `LeftHand__lin_rel_pz` |
| Right Hand | `RightHand__lin_rel_px` | `RightHand__lin_rel_py` | `RightHand__lin_rel_pz` |
| Left Foot | `LeftFoot__lin_rel_px` | `LeftFoot__lin_rel_py` | `LeftFoot__lin_rel_pz` |
| Right Foot | `RightFoot__lin_rel_px` | `RightFoot__lin_rel_py` | `RightFoot__lin_rel_pz` |

All positions are root-relative (pelvis origin), in millimeters.

**Raw total movement:**

$$\text{TM}_s = \sum_{t=2}^{T} \sum_{e \in \{LH, RH, LF, RF\}} \| \mathbf{p}_{e}(t) - \mathbf{p}_{e}(t-1) \|_2 \quad \text{[mm]}$$

where the sum is taken only over **clean frame pairs** (both $t$ and $t-1$ must have `is_artifact = False` for endpoint $e$'s corresponding joint).

**Duration-normalized form (primary for longitudinal comparison):**

$$\text{TM}_{\text{rate}} = \frac{\text{TM}_s}{T_{\text{clean}} / f_s} \quad \text{[mm/s]}$$

**Normative duration for TM_rate:** Let $N_e$ be the number of **valid consecutive steps** for endpoint $e$ after the contiguous-segment **Execution Logic** for F2 below ( **`min_segment_frames`** applied per endpoint). Define **$\text{clean\_duration\_tm\_s} = \frac{1}{4 f_s}\sum_e N_e$** (mean per-endpoint duration contributed by valid steps). Then **$\text{TM}_{\text{rate}} = \text{TM}_s / \text{clean\_duration\_tm\_s}$** with $f_s = 120$ Hz. Export **`clean_duration_tm_s`** alongside TM for audit.

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `fs` | 120 Hz | System rate |
| `min_segment_frames` | 3 | Minimum consecutive clean frames for a valid segment; shorter fragments skipped |
| `normalize_by_duration` | True | Always report TM_rate for longitudinal comparison; raw TM in supplement |
| `run_bootstrap` | `False` | If `True`, run [Appendix D](#appendix-d-block-bootstrap--full-protocol) CIs for TM / TM_rate |
| `bootstrap_block_frames` | `240` | Block length ($L$) when `run_bootstrap` |
| `bootstrap_n_draws` | `1000` | $B$ replicates when `run_bootstrap` |
| `bootstrap_ci_level` | `0.95` | Percentile CI when `run_bootstrap` |
| `bootstrap_seed` | e.g. `42` | RNG seed for reproducibility |

#### Execution Logic

**Forbidden:** Do **not** implement TM as **mask-then-`diff`** on compressed rows (`pos_clean = positions[mask]` then `diff`). That **bridges gaps** across artifact blocks and can **inflate** path length.

**Normative:** Work in **original time order** (aligned with `time_s`). For each endpoint $e$, build **maximal contiguous runs** of frames where **`is_artifact` is False** for that endpoint. **Drop** runs with fewer than **`min_segment_frames`** frames (default 3). Within each kept run, for consecutive row indices $t-1,t$ in **clock time**, add $\|\mathbf{p}_e(t)-\mathbf{p}_e(t-1)\|_2$ to **tm_e**. Sum runs to get per-endpoint **TM**; **TM_total** = sum over endpoints.

```
FUNCTION compute_total_movement(parquet_path, params) → TMResult:
    1. Load 12 position columns + 4 artifact columns (one per endpoint).
    2. FOR each endpoint e (in original DataFrame row order):
         a. Label contiguous clean runs (is_artifact False); drop runs with len < params.min_segment_frames
         b. FOR each kept run: sum Euclidean step length over consecutive rows inside the run only
         c. tm_e = sum of (b) across runs; N_e = total valid step count for rate denominator
    3. TM_total = sum_e tm_e
    4. clean_duration_tm_s = (N_LH + N_RH + N_LF + N_RF) / (4 * fs)
    5. TM_rate = TM_total / clean_duration_tm_s
    6. RETURN TMResult(tm_total_mm, tm_rate_mm_per_s, per_endpoint, clean_duration_tm_s, step_counts_by_endpoint)
```

#### Strategic Crossroads

- **Artifact-pair handling:** Steps across artifact boundaries are **never** included; only **within-run** consecutive pairs (normative above). The deprecated mask-then-diff pattern is **not** valid for primary exports.
- **Root-relative vs global:** Root-relative positions remove locomotion (translation of pelvis through space). If Gaga sessions include walking/traveling, root-relative TM captures **limb articulation relative to body center**, not room-level translation. This is the correct choice for creative movement analysis.

#### Risk Assessment

| Risk | Severity | Impact | Mitigation |
|------|----------|--------|------------|
| TM scales with session duration | High | Longer sessions artificially higher TM | Always use TM_rate (duration-normalized) |
| High-frequency tracking noise inflates step sums | Medium | Small jitter accumulated over ~19K frames | Data is pre-filtered (Step 04 Butterworth); verify median step > 0.5 mm |
| One endpoint with persistent artifacts | Medium | That endpoint contributes fewer steps | Report per-endpoint TM; flag if any endpoint has >20% artifact |
| Marker swap (left/right confusion) | Low | Massive single-frame jump | Step 04 filtering + artifact flags should catch this; verify no single step > 50 mm |

**N-survivability rating: LOW RISK.** TM is a summation of Euclidean distances. It requires no embedding, no phase portrait, no reference basis. It is robust at any N and degrades gracefully with artifact contamination (affected endpoints contribute less, but the metric does not become meaningless).

---

## Section 2: Tier 2 — Supplementary Evidence & Controls

### F5. Joint Gini Coefficient

#### Role in the Architecture

Joint Gini is **not** a co-primary metric. It is the **physical explanation** for changes observed in D_eff. Where D_eff answers "did the movement become less stereotyped?", Joint Gini answers "**which joints** drove that change?" It translates the abstract eigenvalue summary into an anatomically interpretable story: "the variance that was concentrated in shoulders and arms at Class 1 became more evenly distributed across all 19 joints by Class 10."

Joint Gini uses the **exact same** PCA pipeline as D_eff. It is a second read-out of the same internal `PCAEngine` object — not an independent analysis.

#### Scientific Definition & Defense

> **Thesis-ready:** The Joint Gini coefficient summarizes the inequality in how kinematic variance is distributed across the 19 joints of the skeleton, using PCA-based variance attribution and the standard Gini inequality index. It directly operationalizes the core Gaga pedagogical instruction: dissolve the hierarchy between body parts, shifting from a "specialist" (few joints dominate) to a "democratic" (all joints contribute equally) motor strategy.

**Primary citations:**
- Variance attribution via squared PCA loadings: Jolliffe (2002); Daffertshofer et al. (2004).
- Gini coefficient: Damgaard & Weiner (2000), economics; Wittebolle et al. (2009), ecology.
- Gini validated for movement analysis: I≠ paper — *"halved the sample size required for a statistical power of 80%."*

**One-sentence defense:** *"The Gini coefficient is a standard inequality index validated for movement analysis (I≠); we apply it to the nonnegative shares of kinematic variance attributed to each joint after PCA-based attribution, yielding a single summary of how concentrated whole-body movement is in a few joints versus distributed across the skeleton."*

#### Mathematical Formulation

**Input:** PCA results from the **same** `PCAEngine` as D_eff.

**Step 1 — Per-feature variance attribution:**

$$\alpha_{f,s} = \sum_{k=1}^{K} \lambda_{k,s} \cdot w_{k,f}^2$$

where $\lambda_{k,s}$ = session $s$ variance along PC $k$ (from `pca_engine.var_per_pc[s]`); $w_{k,f}$ = loading of feature $f$ on PC $k$ (from `pca_engine.pca.components_`).

**Step 2 — Aggregate to joints (19 joints):**

Map each feature $f$ to its anatomical joint $j$ (e.g., `LeftArm__zeroed_rel_omega_mag` → `LeftArm`):

$$A_{j,s} = \sum_{f \in \text{joint}_j} \alpha_{f,s}$$

Since the dynamics branch uses one feature per joint (`omega_mag`), this mapping is one-to-one: $A_{j,s} = \alpha_{j,s}$.

**Step 3 — Normalize to proportions:**

$$\pi_{j,s} = \frac{A_{j,s}}{\sum_{j'=1}^{19} A_{j',s}}$$

**Step 4 — Gini coefficient (sorted form):**

Sort $\pi_1 \leq \pi_2 \leq \cdots \leq \pi_{19}$, then:

$$\text{Gini}(s) = \frac{2\sum_{i=1}^{19} i \cdot \pi_{(i)}}{19 \cdot \sum \pi_{(i)}} - \frac{20}{19}$$

**Range:** $\text{Gini} \in [0, 1]$. 0 = perfectly equal (all joints contribute identically). 1 = maximally unequal (one joint has all variance).

#### Mandatory Dual-Mode Sensitivity Analysis

**Thesis / lock-in:** Joint Gini is reported in **two** modes (below) for primary exports unless **`PARAMS_PCA_F4_F5['run_session_native_gini']`** is **`False`** (fast iteration: anchored Gini + D_eff only). If **`False`**, set **`session_native_gini_skipped=True`** in F5 exports and **`run_metadata.json`** so a reviewer cannot confuse a fast run with full dual-mode.

Compute Joint Gini in **two** modes to guard against T1-basis projection artifacts:

1. **T1-anchored Gini** (primary): Uses T1 PCA loadings and per-session projected variances from the shared `PCAEngine`. Comparable across sessions because the basis is fixed.
2. **Session-specific Gini** (sensitivity): Fits a **fresh** PCA on session $s$ data alone; computes Gini from that session's own loadings and eigenvalues. Not directly comparable across sessions, but serves as a reality check.

| T1-Anchored | Session-Specific | Inference |
|-------------|-----------------|-----------|
| ↓ Decrease | ↓ Decrease | **Genuine democratization** — both bases agree |
| ↓ Decrease | No change / ↑ | **T1-basis artifact** — new modes diffuse across T1 components but do not represent genuine redistribution |
| No change / ↑ | ↓ Decrease | **Cautious** — redistribution is invisible in the T1 basis; report but do not over-claim |
| No change / ↑ | No change / ↑ | **Null finding** — no democratization detected |

#### Implementation Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| `n_joints` | 19 | Full skeleton |
| `reference_session` | Class 1 (T1) | Same anchor as D_eff (shared `PCAEngine`) |
| `run_session_native_gini` | `True` | If **`True`** (default for thesis), compute **both** T1-anchored and session-native Gini. If **`False`**, skip native PCA fits; set **`session_native_gini_skipped=True`** in exports. |
| `sensitivity_mode` | Both modes when `run_session_native_gini` is `True` | Dual-mode inference requires both when enabled |
| `compute_ap_ratio` | `False` | If `True`, compute [F5.1](#f51-core-periphery-integration-ap-ratio) and append to F5 export |
| `ap_ratio_epsilon` | `1e-12` | Denominator guard in A/P Ratio |
| `run_bootstrap` | `False` | If `True`, run [Appendix D](#appendix-d-block-bootstrap--full-protocol) for Gini / A/P (anchored) after F5 |
| `bootstrap_block_frames` | `240` | Block length ($L$) when `run_bootstrap` |
| `bootstrap_n_draws` | `1000` | $B$ replicates when `run_bootstrap` |
| `bootstrap_ci_level` | `0.95` | Percentile CI when `run_bootstrap` |
| `bootstrap_seed` | e.g. `42` | RNG seed for reproducibility |

#### Execution Logic

```
FUNCTION compute_joint_gini(pca_engine, session_data, params) → GiniResult:
    # T1-ANCHORED MODE (uses shared PCAEngine — no new fit)
    1. FROM pca_engine: extract loadings W (K×F), per-session var_per_pc.
    2. FOR each session s:
         a. alpha_f = sum_k( var_per_pc[k,s] * W[k,f]^2 )  for each feature f
         b. Map features to joints → A_j for each of 19 joints
         c. pi_j = A_j / sum(A_j)
         d. gini_anchored = gini_coefficient(pi)
    
    # SESSION-SPECIFIC MODE (independent fresh PCA per session) — skip if params.run_session_native_gini is False
    3. IF params.run_session_native_gini:
         FOR each session s:
           a. Fit fresh PCA on session s scaled data alone
           b. Compute alpha, A_j, pi_j with session-specific loadings
           c. gini_native = gini_coefficient(pi_native)
       ELSE:
           set session_native_gini_skipped=True; omit gini_native columns
    4. Apply inference table (dual-mode convergence check) when both modes present
    5. RETURN GiniResult(gini_anchored, gini_native or NA, joint_proportions, 
                         sensitivity_flag, inference_label, session_native_gini_skipped)
```

#### Risk Assessment

| Risk | Severity | Impact | Mitigation |
|------|----------|--------|------------|
| T1-basis artifact (see sensitivity table) | High | Spurious Gini decrease | Mandatory dual-mode computation; report both |
| Single dominant joint (e.g., Hips artifact) | Medium | Gini inflated by one outlier joint | Check per-joint artifact rates; exclude joints with >30% artifact |
| Branch choice affects Gini | Low | Dynamics vs pose branches give different joint rankings | Report primary branch (dynamics); note if supplementary branches disagree |

**N-survivability rating: MEDIUM RISK.** Same as D_eff (shared pipeline). The Gini computation itself is trivial; the risk is entirely in the PCA basis quality.

### F5.1 Core-Periphery Integration (A/P Ratio)

The **A/P Ratio** is a supplementary scalar that maps directly to the Gaga pedagogical instruction to **dissolve the boundary between the core and the periphery.** It reuses the **T1-anchored** per-joint variance proportions $\{\pi_{j,s}\}$ computed during the Joint Gini step (F5): **no additional PCA fit** and no new input columns beyond those already in the F5 anchored path.

#### Mathematical definition

Using $\pi_{j,s}$ from F5 (normalized joint variance shares in the reference basis):

$$\Pi_{\text{axial}}(s) = \sum_{j \in \mathcal{J}_{\text{axial}}} \pi_{j,s}, \qquad \Pi_{\text{periph}}(s) = \sum_{j \in \mathcal{J}_{\text{periph}}} \pi_{j,s}$$

$$\text{A/P Ratio}(s) = \frac{\Pi_{\text{axial}}(s)}{\Pi_{\text{periph}}(s) + \varepsilon}$$

where $\varepsilon$ is a numerical guard (e.g. `1e-12`) to avoid division by zero when peripheral share is nil.

#### Joint sets (maximize core vs. distal contrast)

| Set | Members (schema names) |
|-----|-------------------------|
| **Axial (core)** | Hips, Spine, Spine1, Neck, Head |
| **Peripheral (distal)** | LeftForeArm, LeftHand, RightForeArm, RightHand, LeftFoot, RightFoot |
| **Transitional (excluded from A/P)** | LeftShoulder, RightShoulder, LeftArm, RightArm, LeftUpLeg, RightUpLeg, LeftLeg, RightLeg |

Transitional joints are **omitted** from both $\Pi_{\text{axial}}$ and $\Pi_{\text{periph}}$ so the ratio contrasts trunk/head vs. hands/forearms/feet only. They remain in the **denominator of $\pi$** normalization in F5 (all 19 joints) unless a joint was dropped by quality gates.

#### Predicted direction

Longitudinally, **A/P Ratio $\to 1.0$** as axial and peripheral shares of movement variance **equalize** (boundary dissolution). This is a **directional hypothesis**, not a significance claim at N=3.

#### Implementation control

- Executed as a **sub-step inside Block 5** immediately after $\pi_{j,s}$ is available for the T1-anchored mode.
- **Toggle:** `PARAMS_PCA_F4_F5['compute_ap_ratio']` (Boolean). Default **`False`**. If **`True`**, append `ap_ratio` (and optionally $\Pi_{\text{axial}}$, $\Pi_{\text{periph}}$) to the F5 export (e.g. `f5_results.csv`).

---

### Reliability Gates

Every session must pass the following quality gates before its feature values enter the longitudinal comparison. Gates are reported per session in a standardized quality table.

| Gate | Threshold | Features Affected | Action on Failure |
|------|-----------|-------------------|-------------------|
| **Artifact fraction** | > 0.30 of total frames flagged as artifact (any joint) | All features | **Hard exclude** — session removed from all comparisons |
| **Artifact soft warning** | > 0.20 but ≤ 0.30 | All features | **Soft flag** — session retained but flagged in results table |
| **Per-joint artifact rate** | > 0.30 for any single joint | ATF (that joint), Joint Gini (that joint) | **Joint exclusion** — that joint dropped from ATF and Gini for the session |
| **Per-endpoint artifact rate** | > 0.20 for any TM endpoint | TM (that endpoint) | **Endpoint flag** — report per-endpoint TM; flag if any endpoint exceeds threshold |
| **Clean frame fraction (PCA)** | < 0.70 of frames where all 19 joints are simultaneously clean | D_eff, Joint Gini | **PCA unreliable** — session D_eff/Gini reported with low-confidence flag |
| **Reference session quality** | Reference (Class 1) fails any hard gate above | D_eff, Joint Gini | **Pipeline halt** — reference session must be replaced or data must be re-examined |
| **Session duration** | Clean duration < 60 s | All features | **Short-session flag** — retain but flag; interpret with caution |
| **Noise floor stability** | Noise floor varies > 3× across sessions for same joint (within subject) | ATF | **Noise-floor instability flag** — report noise floors per session; consider fixed threshold sensitivity |

### T2 Isolation Gate (Training vs. Psychedelic Disambiguation) — summary

This gate addresses a **high-risk interpretive confound:** directional change at **T3** (e.g. afterglow) could reflect demand characteristics rather than a neuroplastic effect distinct from **Gaga training alone**. The internal control compares **T1→T2** (pure training) vs. **T2→T3** (psilocybin on top of training).

This module is **optional** (default **off**). Toggle via **`CONFIG['run_t2_isolation']`** (default **`False`**). Full protocol, formulas, narrative truth table, and parameter control are specified in [Appendix E](#appendix-e-t2-isolation-gate--full-protocol). Implementation lives in **`src/v2_longitudinal.py`**.

### Block 0 — Constraint register & quality-table specification

This subsection is the **single authoritative checklist** for **Step 1** of the build sequence (`notebooks/11_METH_SPEC_v2_Features.ipynb`: Preamble, Loaders, Reliability Gates). The implementing agent must satisfy **every** row below before writing F1–F5. Numeric thresholds are **normative**; they duplicate §2 Reliability Gates, §3 Key Pipeline Rules (reference validation), feature-level parameters, and risk mitigations so nothing is missed.

#### Master Execution Prompt (reference)

The lead developer initiates the notebook build with the **Master Execution Prompt** (iterative blocks, double math verification, Steps 1–6 order). That prompt is **not** repeated in full here; this register is the **spec-side companion** that the prompt requires the agent to quote when implementing Block 0.

#### Global inputs & invariants

| Item | Requirement |
|------|-------------|
| **Input path pattern** | `derivatives/step_06_kinematics/{RUN_ID}__kinematics_master.parquet` |
| **Sampling rate** | $f_s = 120$ Hz — validate with `np.diff(time_s)`: median $\Delta t \approx 1/120$ s (tunable tolerance in `CONFIG`, e.g. `fs_expected=120.0`, `dt_rtol`) |
| **Artifact policy (global)** | Frames with artifacts are **excluded** from aggregations — **never** interpolated, **never** zero-filled for gate counts (use boolean masks only) |
| **Joint count** | 19 joints for PCA / ATF / Gini dynamics branch; **exact** `{Joint}` strings are normative in [Appendix A.1](#a1-normative-joint-name-table-v2--parquet-prefixes) (same order as pipeline `ALL_19_JOINTS`). There is **no** `Chest` column in v2; trunk coverage uses **`Spine1`** (and Spine). Do not infer names from abbreviated group tables elsewhere in this document. |
| **TM endpoints (4)** | LeftHand, RightHand, LeftFoot, RightFoot — artifact flag per endpoint = `{Endpoint}__is_artifact` (same entity as position columns) |
| **`CONFIG` (preamble)** | Optional: per-`run_id` time windows ([§3.2](#32-session-time-windowing-apply_time_window)); `atf_pi_mask_policy` ([§5.1](#51-exploratory-visualization--atf-vs-joint-variance-share-optional)); optional `bootstrap_block_sec` for UI; optional **`bootstrap_master_seed`** (derivation of per-feature bootstrap seeds — [Appendix D](#appendix-d-block-bootstrap--full-protocol)); **`params_locked`** after final tuning ([§3.4](#34-information-first-workflow-and-analyst-authority)); thresholds for bootstrap pre-run acknowledgment ([§4.6](#46-conflict-register-automated-audit-tiering-and-analyst-acknowledgment)); session registry keys below. |

#### Session registry and run selection

Before reliability gates, the notebook must resolve **which Parquet file** corresponds to each analytic timepoint (e.g. T1/T2/T3 or Class 1…10).

- **Discovery:** Scan `derivatives/step_06_kinematics/` for `*__kinematics_master.parquet` files and build a table of candidate sessions with **`run_id`**, **`subject_id`**, **protocol** / task label (parsed from filename conventions), and path.

> **Data file clarification (v3.0):** `data/subject_metadata.json` contains **anthropometric data only** (height, weight, body type) — it does **not** contain session-to-timepoint mappings or run identifiers. `data/subjects_registry.json` is a study-level registry but also does not provide the per-session Parquet path mapping needed here. The **normative source** for session discovery is the `batch_configs/*.json` files (e.g. `batch_configs/subject_671_p2_all.json`), which list CSV paths organized by subject/timepoint/protocol/repetition. The analyst must **manually construct** the `CONFIG['run_ids_by_timepoint']` mapping from these batch configs and the scanned Parquet directory. This mapping must appear in the **notebook preamble** and be serialized in `run_metadata.json`.

- **`protocol_filter` (optional):** If the study analyzes **one task only** (e.g. free improvisation P2), set **`CONFIG['protocol_filter']`** (e.g. `"P2"`) so discovery excludes other tasks. If omitted, **all** step-06 sessions for the subject are candidates; the analyst must then exclude irrelevant rows via **`quality_df`** / decisions.
- **Choosing one session per timepoint when repeats exist:**
  - **Manual (default for thesis lock-in):** The analyst sets an explicit ordered list **`CONFIG['run_ids_by_timepoint']`** or equivalent mapping `{timepoint_label → run_id}` after reviewing the batch configs, scanned directory, and **`quality_df`**.
  - **Automated helper (optional):** A strategy such as **lowest artifact fraction** or **longest clean duration** may pre-rank candidates; the **committed** `run_id` must still appear in the preamble / export metadata. Do not silently swap sessions without recording the mapping.
- **Ambiguity failure mode (normative):** If **`run_ids_by_timepoint`** is **unset** or **incomplete** (missing a required timepoint key) **and** the discovery table contains **more than one** candidate row for the same intended label (e.g. two P2 runs for “Class 5”), the notebook **must halt with a clear error** that lists the competing `run_id`s and expected keys. **Automatic selection of a winning session is forbidden** for primary exports unless the study protocol is amended and the auto-rule is named in **`run_metadata.json`**. Manual resolution: set the mapping explicitly, then re-run.
- **Multi-subject:** Primary v2 analysis is **per subject**. Concatenating multiple subjects in one notebook run is **exploratory** unless the study protocol pre-specifies a pooled table.

#### Tunable parameter dict — `CONFIG` (Block 0 gate thresholds)

All thresholds below should appear in **`CONFIG`** (consolidated from the former `PARAMS_GLOBAL` and `PARAMS_GATES` namespaces; see [Parameter Namespace Consolidation](#parameter-namespace-consolidation-v30)) so Block 0 has no literals in logic cells.

| Key | Default | Source in this spec |
|-----|---------|---------------------|
| `artifact_critical_threshold` | `0.30` | F1 Implementation Parameters; Reliability Gates |
| `artifact_warning_threshold` | `0.20` | F1 Implementation Parameters; Reliability Gates |
| `per_joint_artifact_exclude_threshold` | `0.30` | Reliability Gates (ATF, Joint Gini joint drop) |
| `per_endpoint_artifact_flag_threshold` | `0.20` | Reliability Gates (TM endpoint flag) |
| `min_clean_fraction_pca` | `0.70` | F4 Implementation Parameters; Reliability Gates |
| `min_clean_duration_s` | `60.0` | Reliability Gates; reference validation §3 |
| `ref_max_artifact_fraction` | `0.20` | §3 Key Pipeline Rules (reference session **strict** — must be **below** warning band) |
| `ref_min_clean_fraction_pca` | `0.70` | §3 Key Pipeline Rules |
| `ref_min_clean_duration_s` | `60.0` | §3 Key Pipeline Rules |
| `nan_fraction_flag_threshold` | `0.10` | F1 Risk Assessment (per-joint NaN rate → flag) |
| `noise_floor_ratio_flag_threshold` | `3.0` | Reliability Gates (noise-floor stability across sessions, within subject) |
| `dead_recording_max_frames` | `1000` | If **`n_frames_loaded`** ≤ this value **or** raw duration ≤ `dead_recording_max_duration_s`, mark **`dead_recording`** — session unusable for all metrics (see gate table) |
| `dead_recording_max_duration_s` | `8.0` | Paired with `dead_recording_max_frames` for dead-session rule (tunable to match study QA) |

#### Tunable parameter dict — `CONFIG` (longitudinal keys, post–F1–F5)

Longitudinal keys live in the same **`CONFIG`** dict under a `longitudinal` sub-section. Use for **contrast logic** and **optional** longitudinal bootstrap — **not** for Block 0 thresholds. Implemented in **`src/v2_longitudinal.py`**.

| Key | Default | Source / behavior |
|-----|---------|-------------------|
| `run_t2_isolation` | `False` | [T2 Isolation Gate](#t2-isolation-gate-training-vs-psychedelic-disambiguation) — if **`True`**, require T1/T2/T3 rows in registry and export isolation table |
| `longitudinal_bootstrap_seed` | e.g. `42` | Optional; [Appendix D.2](#d2-longitudinal-delta-bootstrap-optional) — **independent** from per-feature **`bootstrap_seed`** |

#### Per-session derived booleans (definitions)

Let $T$ be the number of rows (frames) in the session DataFrame **after** optional time-window cropping (see [§3.2](#32-session-time-windowing-apply_time_window)). When reporting **`raw_duration_s`**, use the span of the loaded table **before** cropping.

**Gatekeeper role:** Block 0 is the **single audit gate** before F1–F5. It **must** emit the full session-level summary (minimum schema below) so the analyst can review diagnostics **before** tuning parameters, choosing time windows, or committing exclusions. Automated flags are **recommendations**; the analyst’s committed choices are applied in [§3.4](#34-information-first-workflow-and-analyst-authority) and must be serialized with exports.

1. **`any_joint_artifact[t]`** — `OR` over all 19 joints of `{Joint}__is_artifact[t]`.  
   - **Session artifact fraction (gate row):**  
     $$\text{artifact\_fraction} = \frac{1}{T}\sum_{t=1}^{T} \mathbf{1}[\texttt{any\_joint\_artifact}(t)]$$  
   - **Interpretation:** “> 0.30 of total frames flagged as artifact (**any joint**)” — matches F1 execution logic `mean(any_joint_is_artifact)`.

2. **`all_joints_clean[t]`** — `AND` over all 19 joints of `NOT {Joint}__is_artifact[t]`.  
   - **PCA clean frame fraction:**  
     $$\text{pca\_clean\_fraction} = \frac{1}{T}\sum_{t=1}^{T} \mathbf{1}[\texttt{all\_joints\_clean}(t)]$$  
   - **Count (mandatory diagnostic):** **`n_frames_pca_clean`** $= T \times \text{pca\_clean\_fraction}$ (report as integer frame count; store float only if needed for auditing).  
   - **Gate:** if $\text{pca\_clean\_fraction} < 0.70$ → **`pca_unreliable_flag`** for D_eff / Joint Gini (T1-anchored path).  
   - **Analyst visibility:** Block 0 **must** surface **`n_frames_pca_clean`**, **`pca_clean_fraction`**, and the **distance to the gate** (e.g. **`pca_clean_margin`** $=$ `pca_clean_fraction` − `CONFIG['min_clean_fraction_pca']`) in the displayed `quality_df` (sortable / styled). The intersection mask is **stricter** than per-joint artifact rates imply; analysts should inspect this row **before** interpreting borderline PCA sessions.

3. **Per-joint artifact rate (joint $j$):**  
   $$\text{artifact\_rate}_j = \frac{1}{T}\sum_{t=1}^{T} \mathbf{1}[\texttt{is\_artifact}_j(t)]$$  
   - **Gate:** if $\text{artifact\_rate}_j > 0.30$ → record **`joint_exclude_j`** (drop joint $j$ from ATF summary and from Joint Gini input for that session, per Reliability Gates).

4. **Per-endpoint artifact rate (endpoint $e \in \{\text{LH,RH,LF,RF}\}$):** same formula on `{Endpoint}__is_artifact`.  
   - **Gate:** if $> 0.20$ → **`tm_endpoint_flag_e`** (retain TM computation but flag that endpoint in results).

5. **`clean_duration_s` (companion / short-session gate):**  
   $$\text{clean\_duration\_s} = \frac{1}{f_s}\sum_{t=1}^{T} \mathbf{1}[\neg\texttt{any\_joint\_artifact}(t)]$$  
   - **Gate:** if $\text{clean\_duration\_s} < 60$ → **`short_session_flag`** (all features: retain, flag, interpret with caution).

6. **Per-joint NaN fraction (auxiliary, from F1 risks):**  
   For each joint velocity column `{Joint}__lin_vel_rel_mag`, compute fraction of frames where value is non-finite. If $> 0.10$ → **`joint_nan_flag_j`** (aligns with ATF mitigation; does not replace artifact gates).

7. **Dead recording (integrity gate):** On the **loaded** table **before** optional time-window crop, let **`n_frames_loaded`** be the row count and **`raw_duration_loaded_s`** = `n_frames_loaded / f_s` (or span of `time_s`). If **`n_frames_loaded` ≤ `CONFIG['dead_recording_max_frames']`** OR **`raw_duration_loaded_s` ≤ `CONFIG['dead_recording_max_duration_s']`**, set **`dead_recording=True`**. Such sessions are **not** valid for F1–F5; they must be **omitted** from all feature computation and longitudinal tables unless the analyst explicitly documents an override (not recommended).

#### Session-level gate actions (decision table)

| Condition | Field(s) in quality table | Action |
|-----------|---------------------------|--------|
| `artifact_fraction > CONFIG['artifact_critical_threshold']` | `hard_exclude=True`, `exclude_reason` | Session **omitted** from longitudinal comparison tables; F4/F5 must not use this session in stacked analyses |
| `artifact_warning_threshold < artifact_fraction ≤ artifact_critical_threshold` | `soft_warning=True` | Session **kept**; all outputs carry warning |
| `pca_clean_fraction < min_clean_fraction_pca` | `pca_unreliable=True` | D_eff / Gini (T1-anchored) computed only if pipeline allows; must carry low-confidence flag |
| `clean_duration_s < min_clean_duration_s` | `short_session=True` | Retain; flag |
| Any `joint_exclude_j` | list or bitmask | ATF: recompute or exclude that joint from medians; Gini: exclude joint from $\pi$ normalization for that session |
| Any `tm_endpoint_flag_e` | per-endpoint columns | TM: report per-endpoint breakdown with flag |
| Reference session fails §3 checks | `reference_invalid=True` | **Halt** before `PCA.fit` (see below) |
| `dead_recording=True` | `dead_recording`, `exclude_reason` | **Hard exclude** — omit from all F1–F5 and PCA; do not use as reference |

#### Reference session validation (must run inside Block 0 or immediately before Block 3)

Before building the shared PCA engine, the session designated **`reference_run_id`** (Class 1 / T1 per study) must satisfy **all** of:

| Check | Threshold | On failure |
|-------|-----------|------------|
| `artifact_fraction` | $<$ `ref_max_artifact_fraction` (0.20) | **`reference_invalid=True`** — do not `PCA.fit`; user must pick another reference or repair data |
| `pca_clean_fraction` | $\geq$ `ref_min_clean_fraction_pca` (0.70) | **`reference_invalid=True`** |
| `clean_duration_s` | $\geq$ `ref_min_clean_duration_s` (60 s) | **`reference_invalid=True`** |

These are **stricter** than generic sessions (0.20 vs 0.30 on artifacts) because a bad reference corrupts **all** projected sessions.

#### Noise-floor stability flag (within subject, ATF prelude)

After Block 0 loads all sessions for one subject, for each joint $j$ compare noise-floor estimates $V_{j,s}$ across sessions $s$ (noise floors themselves are computed in **F1**, not Block 0). **Block 0** may either: (a) omit this row until F1 runs, or (b) document in the quality table that `noise_floor_stability_checked=False` until F1 merges results. **Normative rule:** if $\max_s V_{j,s} / \min_s V_{j,s} > 3$ (over sessions where $V_{j,s}>0$) → **`noise_floor_instability_flag_j`**. This implements the Reliability Gates row on noise-floor stability.

**Recommended:** Block 0 outputs a **stub** column; F1 fills it after `compute_noise_floor` runs, or F1 writes a second small table merged by `run_id`.

#### Quality table — column schema (one row per session)

Implementers should produce a DataFrame `quality_df`. The table is split into **core gate columns** (required for all downstream logic) and **diagnostic columns** (emitted as a separate print/table for analyst inspection).

##### Core gate columns (8 columns — used by F1–F5 downstream)

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | str | Session identifier |
| `artifact_fraction` | float | Fraction of frames with any-joint artifact (any-joint OR) |
| `pca_clean_fraction` | float | Fraction of frames where all 19 joints are simultaneously clean |
| `clean_duration_s` | float | Clean duration on the analysis interval (seconds) |
| `hard_exclude` | bool | `artifact_fraction > 0.30` |
| `pca_unreliable` | bool | `pca_clean_fraction < 0.70` |
| `short_session` | bool | `clean_duration_s < 60` |
| `reference_session` | bool | True for the single reference row |

##### Diagnostic columns (emitted for analyst review, not consumed by feature math)

These columns are printed or displayed in a companion table for inspection but are **not** required inputs to F1–F5 functions. Implementations may emit them as wide columns, a nested dict, or a separate DataFrame.

| Column | Type | Description |
|--------|------|-------------|
| `n_frames_loaded` | int | Row count before optional crop (dead-session check) |
| `dead_recording` | bool | True if session ≤1000 frames or ≤8 s |
| `n_frames` | int | $T$ (rows after optional time-window crop) |
| `raw_duration_s` | float | Duration before crop |
| `time_window_applied` | `None` or `[float, float]` | If [§3.2](#32-session-time-windowing-apply_time_window) is used |
| `per_joint_artifact_rates` | wide or struct | One rate per joint (19 values) |
| `n_frames_pca_clean` | int | Count of all-joint-clean frames |
| `joints_excluded_gt_30pct` | str or list | Joints with artifact_rate > 0.30 |
| `tm_endpoint_flags_gt_20pct` | str or dict | Endpoints with rate > 0.20 |
| `soft_warning` | bool | 0.20 < frac ≤ 0.30 |
| `reference_invalid` | bool | Only meaningful after ref checks |

#### Block 0 — verification plan (double-check before merge)

1. **Shapes:** For each session, `len(any_joint_artifact) == T` and matches `time_s` length.  
2. **Monotonicity:** `time_s` strictly increasing (or document resampling).  
3. **Artifact fraction:** Manually verify on one session: `artifact_fraction == any_joint_artifact.mean()` (within float tolerance).  
4. **PCA fraction:** `pca_clean_fraction <= 1 - artifact_fraction` is **not** required (any-joint dirty ⊇ not-all-clean); do not confuse the two masks.  
5. **No interpolation:** Counts use raw boolean columns only.  
6. **Reference row:** Exactly one `reference_session==True` per subject analysis; `reference_invalid` gates Block 3.

#### Block 0 outputs (downstream contract)

- **F1, F2** may read **only** `quality_df` + parquet paths (and loaders). They **must not** depend on PCA.  
- **F4, F5** read `quality_df` to respect `hard_exclude`, `pca_unreliable`, and joint exclusions.  
- **Block 3** **must not** start if `reference_invalid==True`.
- **Block 3 (shared PCA) diagnostic:** Immediately before **`PCA.fit`**, echo the reference session’s **`n_frames_pca_clean`**, **`pca_clean_fraction`**, and **`pca_clean_margin`** next to the [Pre-PCA anchor checklist](#pre-pca-anchor-checklist-normative) (same values as Block 0 for that `run_id`, after any time-window crop). If any non-reference session is borderline, optionally print the same triplet per session in a small table so analysts see **effective** clean-frame counts under the all-joint mask.

---

## Section 3: Data Flow & Pipeline Rules

### Order of Operations

```
┌─────────────────────────────────────────────────────────┐
│                  MASTER PARQUET (per session)            │
│  derivatives/step_06_kinematics/{RUN_ID}__kinematics_   │
│  master.parquet @ 120 Hz                                │
└────────────┬──────────────────┬──────────────┬──────────┘
             │                  │              │
    ┌────────▼────────┐  ┌─────▼──────┐  ┌───▼──────────┐
    │  QUALITY GATES  │  │   F1: ATF  │  │   F2: TM     │
    │  (all sessions) │  │ (per sess) │  │  (per sess)  │
    │                 │  │            │  │              │
    │ artifact frac   │  │ vel_mag    │  │ endpoint pos │
    │ per-joint rates │  │ noise floor│  │ step sums    │
    │ clean duration  │  │ threshold  │  │ rate norm    │
    └────────┬────────┘  └─────┬──────┘  └───┬──────────┘
             │                 │              │
             │  ┌──────────────▼──────────────▼──────────┐
             │  │    INDEPENDENT: ATF and TM produce     │
             │  │    one scalar per session with NO       │
             │  │    shared state.                        │
             │  └────────────────────────────────────────┘
             │
    ┌────────▼─────────────────────────────────────────────┐
    │                SHARED PCA ENGINE                      │
    │  Input: 19 × omega_mag (dynamics branch)             │
    │                                                       │
    │  1. StandardScaler.fit(reference_session_clean)       │
    │  2. Scale ALL sessions with frozen scaler             │
    │  3. PCA.fit(reference_session_scaled)                 │
    │  4. Y_s = PCA.transform(session_s_scaled) for all s  │
    │  5. var_per_pc[s] = Var(Y_s, axis=0) for all s       │
    │                                                       │
    │  Output: PCAEngine object containing scaler, pca,    │
    │          Y_per_session, var_per_pc                    │
    └──────┬───────────────────────────┬───────────────────┘
           │                           │
    ┌──────▼──────────┐     ┌──────────▼───────────────────┐
    │  F4: D_eff      │     │  F5: Joint Gini              │
    │  (per session)  │     │  (per session)               │
    │                 │     │                               │
    │  Reads:         │     │  Reads:                       │
    │  var_per_pc     │     │  var_per_pc + pca.components_ │
    │                 │     │                               │
    │  Produces:      │     │  Produces:                    │
    │  d_eff scalar   │     │  gini_anchored scalar         │
    │  d_eff_norm     │     │  gini_native scalar           │
    │  n90            │     │  joint_proportions            │
    │                 │     │  sensitivity_flag              │
    └─────────────────┘     └───────────────────────────────┘
```

### Key Pipeline Rules

1. **Single PCA instantiation.** The `PCAEngine` is built **once** per (subject, branch) combination. Both D_eff and Joint Gini (T1-anchored mode) consume its outputs. There is no second `PCA.fit()` for the anchored pathway. Joint Gini's session-specific sensitivity mode fits a separate, independent PCA per session — this is intentional and documented.

2. **Feature independence for ATF and TM.** ATF and TM read directly from the parquet and have no shared computational state with each other or with the PCA pipeline. They can be computed in any order, in parallel, or on different machines.

3. **Quality gates run first.** All reliability gates are evaluated on the analysis interval (after optional time window) **before** F1–F5. Recommended exclusions from automated thresholds are applied only after merging with [§3.4](#34-information-first-workflow-and-analyst-authority) **analyst decisions**; a session with `hard_exclude` recommended may still be retained only if the analyst explicitly overrides and the override is serialized.

4. **Reference session validation.** Before `PCAEngine` construction, the reference session (Class 1) is validated: artifact_fraction < 0.20, clean_frame_fraction ≥ 0.70, clean_duration > 60 s. Failure halts the pipeline with a diagnostic message.

5. **Unified artifact semantics (v2 primary path).** Unlike legacy UIs that offer **branch-local artifact filtering** toggles, v2’s **primary** path uses the **same** artifact column definitions for gates and features as specified in Block 0 and §§F1–F5. Optional **sensitivity** analyses that vary masking must be labeled as such and must not replace the primary exported scalars without explicit analyst choice.

6. **PCA 19-feature constraint.** The T1-anchored `StandardScaler` and `PCA` are fit on **exactly 19** joint features. **Dropping** a joint column for a test session while still calling `pca.transform()` with a 19-D model is **invalid.** See [§3.6](#36-pca-input-dimension-and-joint-level-artifact-conflict-19-feature-rule).

### 3.1 Notebook implementation contract

This subsection **binds** the methodology to a **single new Jupyter notebook** intended for transparent, per-feature execution with **tunable parameters** and **independent result artifacts**. It does not replace the mathematical definitions in §§1–2; it specifies **how** they should be organized in the notebook so independence and anti–double-dipping remain auditable.

> **Design principle (v3.0).** The notebook is a **thin orchestrator** — it imports library functions from `src/v2_feature_engine.py`, holds the four parameter dicts, calls functions in the prescribed order, and displays results. It is **not** a specification enforcement layer. Heavy logic (gates, feature math, PCA construction) lives in the library module; the notebook's role is sequencing, parameter injection, and analyst-facing display. This keeps cells short, testable outside Jupyter, and resistant to hidden-state bugs.

#### Canonical artifact

| Item | Convention |
|------|------------|
| **Notebook path** | `notebooks/11_METH_SPEC_v2_Features.ipynb` (or equivalent name committed beside this spec) |
| **Input** | Same as document header: `derivatives/step_06_kinematics/{RUN_ID}__kinematics_master.parquet` @ 120 Hz |
| **Outputs** | Each feature section writes **its own** tables/figures (and optional CSV/JSON) under a clearly labeled prefix, e.g. `results/meth_v2/{subject_id}/F1_atf_*.csv`, `.../F2_tm_*.csv`, `.../F4_F5_pca_*.csv` |

#### Notebook preamble — implementation cautions (read first)

Place a short **markdown cell at the top** of `notebooks/11_METH_SPEC_v2_Features.ipynb` (after the title, before imports) so future implementers and analysts see these **before** optional / heavy paths:

| Topic | Guidance |
|-------|----------|
| **Branch D** ([§3.6](#branch-d--reduced-dimension-fallback-for-systematically-artifacted-joints-pre-registered)) | Technically complex (reduced skeleton, relabeled exports). Treat as a **safety net**: **defer implementation** until a first pass on your data shows **widespread** marker loss on **hands/feet** (common in floor work). If cohorts are clean on 19 joints, keep Branch D **off** and use branches A–C only. |
| **Block bootstrap** ([Appendix D](#appendix-d-block-bootstrap--full-protocol)) | Resampling 120 Hz traces **$B$** times (default 1000) is **computationally expensive**; keep `run_bootstrap=False` during development. Implement **`bootstrap_ci`** with **vectorized block-index resampling** (e.g. `numpy.random.Generator.choice` on **block start indices**, then assemble views — **not** a Python loop over frames for each replicate). Profile before large $B$ × many sessions. |
| **`v2_viz_engine.py`** ([§3.3](#33-implementation-architecture--library-notebook-legacy-isolation), [§5.1](#51-exploratory-visualization--atf-vs-joint-variance-share-optional)) | Keep viz **tidy-data–only**: pass **aggregated** tables (session rows, per-joint summaries). **Do not** pass raw 120 Hz MoCap arrays into Plotly — HTML can balloon to **hundreds of megabytes** and become impossible to share or version-control. |

These rows are **advisory** for engineering priority; normative math remains in the linked sections.

#### Recommended export bundle (thesis lock-in)

For reproducibility, the notebook (or a final **Export** cell after F1–F5) should write a **coherent bundle** under `results/meth_v2/{subject_id}/` (paths are illustrative):

| Artifact | Contents | Notes |
|----------|----------|--------|
| **Tidy session table** | One row per `run_id` with F1–F5 scalars + key companions | e.g. `Subject_{id}_meth_v2_metrics.parquet` or `.csv` |
| **Parameters snapshot** | JSON or YAML: merged `CONFIG`, `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5`, analyst overrides | Required for committee audit |
| **Delta / longitudinal table** | Paired contrasts (e.g. Class 10 − Class 1, or T3 − T1) per metric | e.g. `Subject_{id}_deltas.json` (array of records) — optional if computed in notebook |
| **Bootstrap outputs** | Only if run: within-session CIs per [Appendix D.1](#d1-within-session-block-bootstrap), or longitudinal delta bootstrap per [Appendix D.2](#d2-longitudinal-delta-bootstrap-optional) — **never conflate filenames** | Separate files, e.g. `*_block_bootstrap_ci.parquet` vs `*_longitudinal_delta_bootstrap.parquet` |
| **Figures (optional)** | HTML/PNG exports of exploratory plots | Must record `atf_pi_mask_policy` in caption or sidecar JSON |
| **Provenance sidecars** | `environment_specs.json`, `execution_audit.json` per [Appendix C](#appendix-c-thesis-result-package--export-manifest--provenance) | Required for thesis-grade reproducibility |

The exact filenames are project-fixed; the **normative list** and schemas are [Appendix C](#appendix-c-thesis-result-package--export-manifest--provenance); a short “files produced” table must still appear in the methods supplement or appendix.

#### Notebook structure (mandatory section order — 7 blocks)

> **v3.0 simplification.** The previous 14-section layout is collapsed into **7 logical blocks** to keep the notebook a thin orchestrator. Deferred items (T2 isolation, exploratory UI, longitudinal viz, full Appendix C export) are omitted from the MVP notebook and added in v3.1 when the core pipeline is validated. See [§3.8](#38-implementation-phasing--mvp-scope-and-deferred-items).

1. **Block 0 — Preamble, loaders, gates, analyst decisions.** Imports, `DATA_ROOT`, `CONFIG` (with `run_ids_by_timepoint` manually constructed from `batch_configs/`), shared loaders (pure I/O only), optional `apply_time_window` calls ([§3.2](#32-session-time-windowing-apply_time_window)), reliability gates (`quality_df`), reference validation, and analyst decision cell ([§3.4](#34-information-first-workflow-and-analyst-authority)). This block emits diagnostics **before** any feature computation.
2. **Block 1 — F1: ATF.** Self-contained: **`PARAMS_F1`** at section top. Calls `compute_atf` from `v2_feature_engine`. Displays ATF outputs only. **Must not** read any variable produced by F2, F4, or F5.
3. **Block 2 — F2: TM.** Self-contained: **`PARAMS_F2`** at section top. Calls `compute_total_movement` from `v2_feature_engine`. **Must not** depend on PCA or ATF arrays.
4. **Block 3 — Shared PCA engine.** Builds `pca_engine` **exactly once** via `build_pca_engine` from `v2_feature_engine`. **`PARAMS_PCA_F4_F5`** holds all PCA, D_eff, and Gini keys. Runs pre-PCA anchor checklist ([§4.6](#46-conflict-register-automated-audit-tiering-and-analyst-acknowledgment)). Respects [§3.6](#36-pca-input-dimension-and-joint-level-artifact-conflict-19-feature-rule) (no dropped columns for `transform`).
5. **Block 4 — F4: D_eff + F5: Joint Gini.** Reads from `pca_engine` only. Computes D_eff (participation ratio), Joint Gini (T1-anchored + session-native when enabled), and optional A/P ratio. **Must not** refit PCA for anchored mode.
6. **Block 5 — Summary & export.** Assembles tidy session table (`feature_scalars.csv`), writes `run_metadata.json` (parameter snapshot + quality summary), and emits the [§3.4](#34-information-first-workflow-and-analyst-authority) master session summary (pandas `Styler` for notebook display + static Markdown/HTML for archive).
7. **Block 6 — Optional viz (v3.1).** Deferred in MVP. When implemented: call `v2_viz_engine.py` for Plotly HTML from tidy tables only. **Must not** refit PCA or embed raw kinematics.

**Former sections 11–14** (T2 isolation, exploratory UI, longitudinal viz, full Appendix C export) are **deferred to v3.1** per [§3.8](#38-implementation-phasing--mvp-scope-and-deferred-items). They may be added as Blocks 7–8 when the MVP is validated.

#### Tunable parameters

- Each feature block exposes a **single dict** at the start of its section. The consolidated namespace uses **four dicts** total: `CONFIG` (gates, global settings, longitudinal), `PARAMS_F1` (ATF), `PARAMS_F2` (TM), `PARAMS_PCA_F4_F5` (shared PCA, D_eff, Joint Gini).
- **`CONFIG`** (preamble) holds cross-cutting keys: time windows, `atf_pi_mask_policy`, optional `bootstrap_block_sec`, and UI acknowledgment thresholds — see [§3.5](#35-per-block-information-tuning-contract-and-interactive-ux).
- **Modular toggles** (defaults **`False`** unless noted): **`CONFIG['run_t2_isolation']`**; **`PARAMS_PCA_F4_F5['run_session_native_gini']`** (default **`True`**); `PARAMS_PCA_F4_F5['compute_ap_ratio']`; `PARAMS_PCA_F4_F5['run_session_native_deff']`** (default **`True`**); `run_bootstrap` inside `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5` per [Appendix D](#appendix-d-block-bootstrap--full-protocol).
- **No magic numbers** inside computation cells: cells read only from these four dicts (or from constants imported from a `meth_v2_params.py` module if the notebook is kept thin).
- Changing parameters **re-runs only** the sections that depend on them (user executes top-to-bottom or uses a “Run F1 only” note below).

#### Independence and anti–double-dipping (notebook-level)

| Rule | Enforcement |
|------|-------------|
| **F1 ⟂ F2** | No shared mutable state between ATF and TM sections except read-only inputs (parquet paths, gate table, analyst decision dict). |
| **F1, F2 ⟂ PCA** | ATF and TM cells never call `PCA` or read `pca_engine`. |
| **F4 ⟂ F5 (fit)** | Exactly **one** `PCA.fit` for the reference-anchored basis in the notebook; F4 and F5 anchored paths use **only** `transform` + stored loadings + `var_per_pc`. |
| **F5 native mode** | Additional `PCA.fit` **per session** only in the F5 subsection, clearly labeled “sensitivity — session-native.” |

#### Minimal run orders (for debugging)

| Goal | Run |
|------|-----|
| **Gates only** | Preamble → loaders → optional `apply_time_window` → Reliability gates → analyst decisions |
| **ATF only** | Above + **F1** |
| **TM only** | Above + **F2** |
| **D_eff + Gini only** | Preamble → loaders → optional window → gates → decisions → **Shared PCA** → **F4** → **F5** (ATF/TM cells skipped) |

#### Per-feature results bundle (recommended)

Each feature section should assign a **small namespace** for export, e.g. `results_f1 = {"per_session": df, "per_joint": ..., "params": dict(PARAMS_F1)}` so that (1) parameters used for that run are **serialized with outputs**, and (2) committee or thesis appendices can cite **exactly** what was tuned.

#### Clarification vs. “independent modules”

The notebook may call **shared library functions** in `src/` for readability — in particular **`v2_feature_engine`**, **`v2_longitudinal`**, and **`v2_viz_engine`** per [§3.3](#33-implementation-architecture--library-notebook-legacy-isolation) — but **orchestration** (order of fit, single `pca_engine`, parameter dicts) must remain visible in the notebook so a reviewer can see **no double-dipping** without reading the full package tree.

### 3.2 Session time windowing (`apply_time_window`)

- **Placement:** Time windowing is **not** applied inside Parquet loaders. After `load_parquet(path)` returns the full session table, the **notebook** may optionally narrow the analysis to `[t_{\text{start}}, t_{\text{end}}]` on `time_s` (e.g. minutes 10–15).
- **Library vs notebook:** Implement **`apply_time_window(df, time_col, t_start_s, t_end_s)`** (names may vary) as a **pure convenience function** in the v2 backend library module ([§3.3](#33-implementation-architecture--library-notebook-legacy-isolation)). The **notebook** calls it and passes the result to every downstream block so F1–F5 all see the **same** rows.
- **Default / missing bounds:** If **`t_start_s` and `t_end_s` are both omitted** (`None`) or not provided, the helper **must return the input `DataFrame` unchanged** (full recording span) — no error. If **only one** bound is `None`, interpret as an **open-ended** interval: `t_start_s=None` → from `time_s.min()`; `t_end_s=None` → through `time_s.max()`. If **both** are provided but invalid (`t_start_s >= t_end_s` or empty selection after filter), return an **empty** `DataFrame` **or** raise a **clear, actionable error** after logging `time_s` range; document the chosen behavior in the notebook preamble.
- **Reproducibility:** Serialize `time_window_applied` per `run_id` in `quality_df` and in feature export metadata.
- **Downstream:** Noise floors, gate metrics, and PCA are computed on the **cropped** series; `raw_duration_s` in Block 0 still refers to the **pre-crop** span.

### 3.3 Implementation architecture — library, notebook, legacy isolation

This subsection defines a **strict modular contract** so committee-facing math stays auditable: **feature math** is isolated from **longitudinal statistics** and from **visualization** (no Plotly or HTML inside the core feature calculator).

#### Normative module map (`src/`)

| Module | Responsibility | Forbidden |
|--------|----------------|-----------|
| **`src/v2_feature_engine.py`** | **Frames → reliability gates → tidy session-level scalars** for F1–F5: loaders (pure I/O), **`apply_time_window`**, **`build_pca_engine`**, and all per-session feature computations and optional **within-session** block bootstrap per [Appendix D](#appendix-d-block-bootstrap--full-protocol). | Plotly, HTML export, ipywidgets, **longitudinal** pairing, **delta** contrasts, **longitudinal delta bootstrap** ([Appendix D.2](#d2-longitudinal-delta-bootstrap-optional)) |
| **`src/v2_longitudinal.py`** | **Session pairing**, Class 1 → Class 10 (or T1→T3) **deltas**, **[T2 isolation](#t2-isolation-gate-training-vs-psychedelic-disambiguation)** ($\Delta_{T1\to T2}$ vs $\Delta_{T2\to T3}$), and **longitudinal delta bootstrap** when enabled — **pure functions** on tidy tables produced upstream. | Plotly/HTML; **no** re-reading of 120 Hz Parquet for math; **no** `PCA.fit` unless explicitly a sensitivity path pre-specified outside the primary v2 notebook contract |
| **`src/v2_viz_engine.py`** | **Plotly** figure construction and **HTML** export **from tidy inputs only** (session tables, delta tables, precomputed CI columns). **No raw 120 Hz MoCap arrays** — only aggregated rows; otherwise HTML size explodes ([notebook preamble](#notebook-preamble--implementation-cautions-read-first)). Joint-level figures must carry hover metadata: joint name, metric value, artifact rate, session id — sourced from merged tidy columns, not raw kinematics. | Feature extraction, gate logic, PCA fit, bootstrap resampling of frames (consume outputs from the modules above) |

**Implementation order (normative):** Build **`src/v2_feature_engine.py`** first — reliability gates, per-session feature math, and **tidy session-level tables** are prerequisites. Implement **`src/v2_longitudinal.py`** only after those tidy exports exist; it consumes **rows**, not raw Parquet. **`src/v2_viz_engine.py`** may follow or parallel longitudinal once tidy inputs are stable. Referencing `v2_longitudinal.py` in Block 0 / `CONFIG` is **roadmap** only; do not block feature extraction on longitudinal code.

- **Notebook role:** The orchestrating notebook **imports** these modules, holds the **four parameter dicts** (`CONFIG`, `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5`), and runs cells in the order prescribed in [§3.1](#31-notebook-implementation-contract). It is the only layer that may combine outputs for display — but **statistical definitions** for deltas and longitudinal bootstrap live in **`v2_longitudinal.py`**, not in **`v2_viz_engine.py`**.

#### Fresh-code mandate (v3.0)

> **All v2 code must be written from scratch.** `src/v2_feature_engine.py`, `src/v2_longitudinal.py`, and `src/v2_viz_engine.py` must be **newly authored** — no copy-paste, no refactoring, and no structural inheritance from `src/core_kinematics_engine.py` or `src/EDA_PCA.py`. The mathematical definitions in §§1–2 of this spec are the sole source of truth for implementation. This ensures clean provenance, auditable logic, and zero risk of carrying forward legacy assumptions (e.g. combined-fit PCA, seven-feature orchestration, legacy metric side effects).
>
> **The sole exception** is importing `compute_noise_floor` from `src/pulsicity.py` — see below.

- **Legacy freeze:** Do **not** modify **`src/EDA_PCA.py`** or **`src/core_kinematics_engine.py`** for v2; those files support the legacy seven-feature pipeline and older notebooks.

- **Legacy PCA incompatibility (critical note):** `src/EDA_PCA.py`'s `run_3branch_pca` function uses **combined-fit PCA** (fit on all sessions stacked together). This is **fundamentally different** from v2's **reference-anchored PCA** (fit on T1 only, `transform` all sessions). The `run_3branch_pca` function **cannot be reused** for v2. The `build_pca_engine` function in `v2_feature_engine.py` must be written fresh, implementing the reference-anchored approach specified in [§F4](#f4-effective-dimensionality--d_eff).

- **Noise-floor import (mandatory):** `v2_feature_engine.py` **shall import `compute_noise_floor` from `src/pulsicity.py`** for the F1 ATF noise-floor computation. `pulsicity.py` is a pure function with no side effects, already validated and used by the legacy pipeline. **Do not reimplement** the three-phase noise-floor guard; import and call the existing function. Document this import in the `v2_feature_engine.py` module docstring.

- **Shared state:** Functions **must not** use hidden module-level **mutable** singletons. Passing a constructed **`pca_engine`** from `build_pca_engine` into `compute_d_eff` / `compute_joint_gini` is **required** and is **not** forbidden shared state, provided the object is not mutated after construction by unrelated code.

- **Optional UI phase:** After Blocks 0–5 (gates + F1–F5 + export) are verified, a **separate** notebook section may add ipywidgets or dashboards; that layer **consumes** computed tables only and **must not** silently refit PCA or change committed parameters without re-running upstream cells.

### 3.4 Information-first workflow and analyst authority

- **Information before decision:** Any cell that sets **`CONFIG`**, **`PARAMS_F1`**, **`PARAMS_F2`**, **`PARAMS_PCA_F4_F5`**, time windows, or inclusion/exclusion lists **must** run **after** Block 0 has emitted the session summary table (and, where useful, plots). The analyst reviews diagnostics **before** committing choices.
- **Recommendations vs final authority:** Automated gates produce **recommended** flags (`hard_exclude` *recommended*, `reference_invalid` *recommended*, etc.). The notebook **must** include an explicit **analyst decision** structure (e.g. `ANALYST_EXCLUDE_RUN_IDS`, `ANALYST_FORCE_INCLUDE_RUN_IDS`, `ANALYST_REFERENCE_RUN_ID`, optional notes string) that merges with recommendations into **`effective_exclude`** / **`effective_reference_run_id`** used by F1–F5. The analyst may **override** a recommended exclusion or choose a different reference **only** with the full Block 0 table in view; such overrides **must** be serialized next to exports.
- **Audit trail:** Exported artifacts should record both **system recommendations** and **analyst-committed** decisions (machine-readable + short free-text rationale optional).

- **Locked parameter re-run (thesis-grade reproducibility):** ipywidgets (§3.5) **do not** define the source of truth for committed parameters — their state is session-dependent and easy to desynchronize from the **four parameter dicts**. Normative workflow for the **archival** run that backs **Appendix C**:
  1. Run through Block 0 and analyst decisions; use widgets only to **edit** dicts that are also printed or mirrored in code cells.
  2. When choices are final, set **`CONFIG['params_locked'] = True`** (or write an equivalent **`locked_params.json`** / merged YAML snapshot of all parameter dicts plus analyst overrides).
  3. **Re-execute the notebook top-to-bottom** (recommended: **Restart kernel → Run All**) so no cell depends on hidden widget state; every tunable must be read from dicts or the locked snapshot.
  4. Emit exports from this run only. **`run_metadata.json`** must record **`params_locked: true`**, the **`spec_revision`**, and either the full parameter snapshot or a **SHA-256** of the locked file.

- **Post-run master session summary (final notebook cell):** After F1–F5 (and optional longitudinal/viz blocks), emit a **single human-readable summary** combining Block 0 gatekeeper stats with **Tier 1** primary outcomes, with **concern badges** per row or per session: **`OK` / `WARNING` / `CRITICAL`** (color-coded). This summary is **normative** in **two forms**:
  1. **Interactive (notebook work)** — e.g. pandas **`Styler`** (or equivalent) in the notebook for sorting, inspection, and defense sessions — **display-only**; not a second source of truth for exported scalars.
  2. **Static (permanent archive)** — the **same** logical table serialized to disk as **`Markdown`** and/or **`HTML`** (project-fixed path under `results/meth_v2/{subject_id}/`, named in [Appendix C](#appendix-c-thesis-result-package--export-manifest--provenance)) so the thesis committee and future you see **exactly** what was reviewed without re-executing the notebook.

### 3.5 Per-block information, tuning contract, and interactive UX

This subsection makes the [§3.4](#34-information-first-workflow-and-analyst-authority) principle **operational** for implementers building the orchestrating notebook (widgets or structured cells).

- **Global rule:** No block that **commits** tunables, exclusions, or branches may run **without** the diagnostics required to justify the **next** block. Each stage emits **evidence first**, then the user/analyst sets keys in the **four parameter dicts** (`CONFIG`, `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5`) or analyst override structures that downstream code consumes.
- **Per-block contract (minimum):** For each notebook section (Block 0 → analyst decisions → F1 → F2 → shared PCA → F4 → F5 → optional [§5.1](#51-exploratory-visualization--atf-vs-joint-variance-share-optional)), the spec expects:
  1. **Diagnostics emitted** — tables, audit rows, and where useful plots (e.g. `quality_df`, F1 noise-floor audit, pre-PCA anchor checklist [§4.6](#46-conflict-register-automated-audit-tiering-and-analyst-acknowledgment)).
  2. **Tunable keys** — every value that changes results appears under exactly one of the four dicts: **`CONFIG`** (gates, global, longitudinal), **`PARAMS_F1`**, **`PARAMS_F2`**, **`PARAMS_PCA_F4_F5`** (shared PCA, D_eff, Gini, A/P), with defaults stated in §§1–2 and extensions in this document.
  3. **Invalidation note** — changing a parameter in block \(k\) requires re-running block \(k\) and **all** downstream blocks that consume its outputs (documented per section in the notebook).
- **Interactive UX (recommended):** Bind each control (slider, checkbox, text field) to **one named key** in the correct dict among `CONFIG`, `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5`; display **inline** the relevant rows of `quality_df` or audit tables so tuning is not blind. The frontend is a **binding layer**; the backend library remains free of widget code ([§3.3](#33-implementation-architecture--library-notebook-legacy-isolation)).
- **Completeness:** Parameter dicts must include previously “notebook-only” tunables named in this spec: e.g. `noise_floor_override_mms_by_joint`, `atf_pi_mask_policy` ([§5.1](#51-exploratory-visualization--atf-vs-joint-variance-share-optional)), bootstrap settings ([Appendix D](#appendix-d-block-bootstrap--full-protocol)), and conflict policies ([§3.6](#36-pca-input-dimension-and-joint-level-artifact-conflict-19-feature-rule)).

### 3.6 PCA input dimension and joint-level artifact conflict (19-feature rule)

The reference-anchored pipeline fits **`StandardScaler`** and **`PCA(n_components=19)`** on **19** joint features (`zeroed_rel_omega_mag` per joint). `pca.transform()` expects a **19-dimensional** feature vector per row after scaling.

| Situation | Forbidden | Allowed branches (normative) |
|-----------|-----------|------------------------------|
| Joint \(j\) has artifact rate \(> \) `per_joint_artifact_exclude_threshold` for session \(s\) | Silently **dropping** column \(j\) from \(X\) for that session and calling the **same** fitted `pca` | **A (default):** Exclude session \(s\) from **F4/F5** (and shared PCA stack) for primary exports; still allow F1/F2 on that session if analyst permits. **B:** Exclude the **whole session** from all metrics. **C (sensitivity only):** Imputation / alternative PCA dimension — **out of scope** for primary v2 unless pre-registered; do not mix with primary tables. |
| Analyst needs PCA despite borderline joint | N/A | Keep **all 19 columns** in \(X\); rows remain **all-joint-clean** only. Per Reliability Gates, high–artifact-rate joints trigger **joint_exclude** for **ATF/Gini joint lists**, not silent removal of PCA columns. |

**Implementation note (Branches A–C):** `build_pca_engine` receives 19 columns per session under the default 19-joint rule. Session rows use the global all-joint-clean mask (§F4). If a joint is excluded from Gini’s \(\pi\) normalization for that session, that is a **post-transform** bookkeeping rule on attribution — it does **not** change the PCA input width.

#### Branch D — Reduced-dimension fallback for systematically artifacted joints (pre-registered)

Gaga improvisation includes floor work, inversions, and foot-contact sequences that can cause **systematic** marker loss on specific joints (commonly `LeftFoot`, `RightFoot`, or `LeftHand`) across **most or all** sessions for a subject. When this occurs, branches A–C either exclude too many sessions (leaving insufficient data for longitudinal comparison) or ignore the problem entirely.

**Trigger:** If **≥3 joints** exceed `per_joint_artifact_exclude_threshold` (0.30) in **≥50% of sessions** for the subject under analysis, Branch D activates.

**Procedure:**

1. **Identify excluded joints:** List all joints that exceed the artifact threshold in ≥50% of sessions. These are **systematically unreliable** for this subject.
2. **Build reduced joint set:** Remove systematically unreliable joints from the 19-joint list. The reduced set must retain **≥14 joints** to preserve PCA stability (sample-to-feature ratio remains >1000:1). If fewer than 14 remain, **halt** with a data-quality failure for PCA metrics (F1/F2 still run normally).
3. **Refit PCA at reduced dimension:** `StandardScaler` and `PCA(n_components=K_reduced)` are fit on the reference session using only the reduced joint set. All sessions are projected into this reduced basis.
4. **D_eff and Gini recalculated:** $D_{\text{eff}}$ range becomes $[1, K_{\text{reduced}}]$; normalize as $\tilde{D}_{\text{eff}} = D_{\text{eff}} / K_{\text{reduced}}$. Gini operates on the reduced joint proportions. **Values are NOT directly comparable** to 19-joint results from other subjects.
5. **Export labeling:** All F4/F5 exports must include **`pca_joint_count`** ($K$), **`joints_excluded_branch_d`** (list), and **`branch_d_active=True`** so reviewers immediately see the reduced basis.

| Guard | Threshold | Rationale |
|-------|-----------|----------|
| Minimum retained joints | 14 | Preserves >70% of skeletal coverage; smaller sets lose body-region representativeness |
| Trigger: joints over threshold | ≥3 joints in ≥50% sessions | Prevents activation on transient single-session artifacts |
| Reference session under Branch D | Must still pass §3 gates on the **reduced** joint set | Reference quality applies to the working feature set |

**Normative:** Branch D is a **pre-registered fallback**, not a default. `CONFIG['pca_fallback_branch_d']` (default **`False`**; set **`True`** when systematic artifacts are confirmed in Block 0 review). When active, label all results as “Branch D — reduced skeleton” in exports and figures.

**Implementation priority:** Branch D is a strong **safety net** but adds branching complexity. **Recommended:** implement the **default 19-joint path** (branches A–C) first; add Branch D **only if** exploratory review shows **persistent** hand/foot marker loss across sessions (see [notebook preamble cautions](#notebook-preamble--implementation-cautions-read-first)). If Branch D code is deferred, record `branch_d_implemented: false` (or equivalent) in `run_metadata.json`.

### 3.7 Tech stack recommendations

Normative library choices for v2 implementation (pin versions in `environment_specs.json` per [Appendix C](#appendix-c-thesis-result-package--export-manifest--provenance)):

| Layer | Libraries | Role |
|-------|-----------|------|
| **Storage** | **pyarrow** | Parquet engine for reading/writing `kinematics_master.parquet` and tidy exports (pandas uses pyarrow as the Parquet backend when available). |
| **Math** | **NumPy**, **pandas** | Array math, `DataFrame` operations, time-aligned masks, tidy session tables. |
| **ML / stats** | **scikit-learn** | `PCA`, `StandardScaler` — reference-anchored basis and scaling per §F4/F5 (`sklearn.decomposition`, `sklearn.preprocessing`). |
| **ML / stats** | **scipy.stats** | Percentile confidence intervals (e.g. block-bootstrap CIs in [Appendix D](#appendix-d-block-bootstrap--full-protocol)); prefer explicit helpers over ad hoc percentile code where applicable. |
| **Viz** | **plotly.graph_objects** | Interactive figures (e.g. joint radar, ATF vs variance-share quadrant views per [§5.1](#51-exploratory-visualization--atf-vs-joint-variance-share-optional)); HTML export with `include_plotlyjs='cdn'` per spec. |
| **Viz / UX** | **ipywidgets** | Optional **Analyst Decision** cell: bind controls to keys in `CONFIG`, `PARAMS_F1`, `PARAMS_F2`, or `PARAMS_PCA_F4_F5` alongside visible `quality_df` ([§3.5](#35-per-block-information-tuning-contract-and-interactive-ux)). |

**Isolation:** `v2_feature_engine.py` imports **none** of Plotly or ipywidgets; visualization and widgets stay in the orchestrating notebook and `v2_viz_engine.py` ([§3.3](#33-implementation-architecture--library-notebook-legacy-isolation)).

**Visualization contract:** `v2_viz_engine.py` must remain **tidy-data–hungry only** — inputs are **aggregated** tidy tables (e.g. one row per session, or long-form joint × session). Embedding **full-resolution 120 Hz** series in Plotly traces inflates HTML to **hundreds of megabytes** and breaks sharing and Git hygiene; that path is **forbidden** for v2 exports ([§5.1](#51-exploratory-visualization--atf-vs-joint-variance-share-optional), [notebook preamble](#notebook-preamble--implementation-cautions-read-first)).

### 3.8 Implementation phasing — MVP scope and deferred items

To prevent implementation paralysis from over-specification, the v2 pipeline is built in **two phases**. Phase boundaries are **normative**: an implementer must not block MVP delivery on deferred items.

#### Phase 1 — MVP (v3.0)

The minimum viable pipeline that produces defensible thesis results:

| Priority | Deliverable | Scope |
|----------|-------------|-------|
| **P0** | `v2_feature_engine.py`: dataclasses, `apply_time_window`, `compute_quality_gates`, `validate_reference` | Quality gates and session loading |
| **P1** | `v2_feature_engine.py`: `compute_atf` (with `pulsicity.py` noise-floor import) | F1: Active Time Fraction |
| **P2** | `v2_feature_engine.py`: `compute_total_movement` | F2: Total Movement |
| **P3** | `v2_feature_engine.py`: `build_pca_engine`, `compute_d_eff`, `compute_joint_gini` | F4 + F5: PCA-based features |
| **P4** | `notebooks/11_METH_SPEC_v2_Features.ipynb` + tidy export | Orchestrating notebook with `feature_scalars.csv` + `run_metadata.json` |

**MVP export bundle (two files):**

| File | Contents |
|------|----------|
| **`feature_scalars.csv`** | One row per `run_id` with F1–F5 scalars + key companions |
| **`run_metadata.json`** | Merged parameter snapshot (`CONFIG`, `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5`), analyst overrides, `quality_df` summary, spec revision identifier |

#### Phase 2 — Deferred to v3.1 (do not implement until MVP is validated)

| Item | Rationale for deferral |
|------|------------------------|
| **Block bootstrap** ([Appendix D](#appendix-d-block-bootstrap--full-protocol)) | Computationally expensive; default off; does not change point estimates; implement as standalone utility post-hoc |
| **Branch D** (reduced skeleton, [§3.6](#36-pca-input-dimension-and-joint-level-artifact-conflict-19-feature-rule)) | Adds branching complexity; recommended only after Block 0 review shows persistent hand/foot marker loss |
| **T2 Isolation Gate** ([Appendix E](#appendix-e-t2-isolation-gate--full-protocol)) | Requires T1/T2/T3 rows; default off; ~50 lines of delta arithmetic on tidy tables |
| **Full Appendix C export manifest** (6+ files with provenance sidecars) | MVP's two-file export is sufficient for pilot; expand to full manifest for final thesis submission |
| **`v2_viz_engine.py`** (Plotly interactive figures) | Build after tidy exports are stable; consumes outputs only |
| **`v2_longitudinal.py`** (session pairing, longitudinal delta bootstrap) | Delta computation is trivial on tidy tables; defer to notebook inline or standalone module |

**Normative rule:** If `run_metadata.json` does not contain a key for a deferred item (e.g. `bootstrap_run`, `t2_isolation_run`, `branch_d_active`), the item was **not implemented** in that run. Reviewers must not infer results from missing files.

---

## Section 4: Success Matrix, Debugging & Failure Protocol

### 4.1 Developer Success Criteria (Technical)

| Feature | Synthetic test | Expected output | Boundary check |
|---------|---------------|-----------------|----------------|
| **ATF** | All-zero velocity → ATF = 0; constant velocity above threshold → ATF = 1.0 | Exact match | 0 ≤ ATF ≤ 1 per joint |
| **TM** | Stationary endpoints → TM = 0; constant velocity v → TM = v × duration × 4 endpoints | Within 1% of analytical | TM ≥ 0; TM_rate > 0 if any movement |
| **D_eff** | Identity covariance (equal variance all PCs) → D_eff = K; one-hot covariance → D_eff = 1 | Within eps of K and 1 | 1 ≤ D_eff ≤ K |
| **Joint Gini** | Equal variance all joints → Gini = 0; all variance in one joint → Gini approaches (n-1)/n | Within eps | 0 ≤ Gini ≤ 1 |

### 4.2 Researcher Success Criteria (Scientific)

| Feature | Expected range (Gaga data) | Red flag | Sensitivity check |
|---------|---------------------------|----------|-------------------|
| **ATF** | 0.3–0.9 per joint; whole-body median 0.5–0.8 | ATF > 0.95 for all joints (noise floor too low) or < 0.1 (noise floor too high) | Compare noise floors across sessions: should be stable within-subject |
| **TM** | 50–500 mm/s per endpoint (scaled to session) | TM_rate < 10 mm/s (virtually no movement) or > 2000 mm/s (likely artifact) | Compare per-endpoint rates; check for bilateral symmetry |
| **D_eff** | 2–10 for dynamics branch | D_eff > 15 (near K=19; possibly noise-driven flat spectrum) or < 1.5 | Compare to N90; D_eff and N90 should be positively correlated |
| **Joint Gini** | 0.15–0.65 | Gini > 0.8 (single-joint domination; check artifact) or < 0.05 (unrealistic equality) | T1-anchored vs session-specific must agree in direction |

### 4.3 Technical Debugging Checklist

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

PCA-SPECIFIC:
  [ ] PCAEngine built exactly once per (subject, branch)
  [ ] StandardScaler fit on reference session only
  [ ] PCA fit on reference session only
  [ ] pca.transform() used (not manual X @ W.T)
  [ ] D_eff and Joint Gini (T1-anchored) use the same PCAEngine instance
  [ ] Session-specific Gini uses a separate, fresh PCA per session
```

### 4.4 Feature Fit Check — The Failure Protocol

**When a feature shows zero sensitivity across all 3 subjects despite correct technical implementation:**

```
STEP 1: Verify technical correctness
  - Run synthetic test (§4.1). If synthetic fails → BUG.
  - Check that input columns have meaningful variance (std > 0).

STEP 2: Check data quality
  - Artifact fraction per session. If > 30% in critical sessions → data limitation.
  - Session durations. If < 60 seconds → insufficient data.
  - Noise floor audit (for ATF): are thresholds reasonable?

STEP 3: Check parameter sensitivity
  - Vary key parameters ±50% (window sizes, thresholds).
  - If metric becomes sensitive with different params → report as parameter-dependent.

STEP 4: Theoretical misfit assessment
  - Does the metric's predicted direction assume a mechanism Gaga doesn't activate?
  - Action: Report as "null finding" in Results. Do NOT suppress.

STEP 5: Decision
  IF synthetic passes AND data quality OK AND parameters explored AND still null:
    → KEEP in results as a null finding.
    → Label: "Feature X showed no detectable Class 1 → Class 10 change
       in any subject (delta < [threshold]; see Table Y)."
    → Do NOT drop from the paper. A pre-registered null is informative.
```

### 4.5 Single-Session Confidence Intervals (Block Bootstrap) — summary

In an **N=3** design, **within-session sampling variability** matters: a metric shift should be interpreted relative to how stable the metric is under resampling of that same recording.

**Key rules:**
- **Never** resample individual frames i.i.d. (falsely narrow CIs due to autocorrelation).
- Use **non-overlapping block bootstrap** with $L = 240$ frames (2.0 s at 120 Hz), $B = 1000$ replicates, 95% percentile CIs.
- For PCA-dependent metrics (D_eff, Gini), **freeze** the T1-anchored `StandardScaler` and `PCA`; only `transform` bootstrap samples.
- Toggle per feature via `run_bootstrap` keys in `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5` (all default **`False`**).

Full protocol, seed management, and the within-session vs. longitudinal delta bootstrap distinction are specified in [Appendix D](#appendix-d-block-bootstrap--full-protocol).

### 4.6 Conflict register, automated audit tiering, and analyst acknowledgment

Normative **tiering**: always emit **structured audit artifacts**; **block** or require **explicit analyst acknowledgment** only for high-risk branches. This replaces open-ended chat-style prompts with reproducible tables and parameters.

| Condition | Always emit (audit) | Tier — analyst acknowledgment |
|-----------|---------------------|---------------------------------|
| **Joint artifact vs 19-D PCA** ([§3.6](#36-pca-input-dimension-and-joint-level-artifact-conflict-19-feature-rule)) | Session/joint table: rates, chosen branch (exclude F4/F5 vs exclude session) | **Acknowledge** if overriding default branch A/B |
| **F1 noise floor** ([F1 noise-floor audit](#noise-floor-audit-mandatory-structured-output-per-session)) | Per joint: method (static / percentile / override), `noise_floor_mms`, clean-frame-only confirmation | **Warn** on Phase B or auto-flags; **acknowledge** if any `noise_floor_override_mms_by_joint` non-empty |
| **Bootstrap** ([Appendix D](#appendix-d-block-bootstrap--full-protocol)) | Log $B$, $L$ (frames), `bootstrap_seed`, block_sec if used | **Acknowledge** before long runs if $B \times$ sessions is large (project-specific threshold in notebook preamble) |
| **ATF vs \(\pi_j\) mask** ([§5.1](#51-exploratory-visualization--atf-vs-joint-variance-share-optional)) | Caption + `CONFIG['atf_pi_mask_policy']` value | **Acknowledge** when switching policy for publication figures |
| **Pre-PCA anchor** | [Checklist below](#pre-pca-anchor-checklist-normative) | **Acknowledge** before first `PCA.fit` if reference changed since last run |

#### Pre-PCA anchor checklist (normative)

Immediately before **`build_pca_engine` / `PCA.fit`**:

1. **`reference_run_id`** matches analyst-committed effective reference ([§3.4](#34-information-first-workflow-and-analyst-authority)).
2. **Reference row** passes Block 0 strict gates: `artifact_fraction_total` \(< 0.20\), `pca_clean_fraction` \(\geq 0.70\), `clean_duration_s` \(\geq 60\) s.
3. **Intent:** `StandardScaler` and `PCA` will be **frozen** from this reference; all other sessions are **only** `transform`ed into this basis for anchored F4/F5.
4. Serialize this checklist (boolean flags + ids) next to PCA outputs.

---

## Section 5: Companion Metrics & Confound Controls

Every primary feature has one pre-specified companion that addresses the most obvious confound interpretation.

| Primary feature | Companion (report alongside) | What it rules out |
|-----------------|------------------------------|-------------------|
| **ATF** (whole-body) | Session artifact fraction + clean duration (s) | "More active" is artifact of shorter/cleaner recording |
| **ATF** (peripheral) | Median `*_lin_vel_rel_mag` over peripheral joints | ATF ↑ only because noise floor dropped, not real activation |
| **TM** | Clean duration (s) + session-level mean endpoint speed | "More path" is just longer recording or faster overall |
| **D_eff** | N90 (same branch) + mean RMS omega_mag | "Flatter spectrum" from global amplitude rescaling, not genuine redistribution |
| **Joint Gini** | T1-anchored vs session-specific dual-mode comparison | Gini ↓ is a T1-basis artifact, not genuine democratization |
| **A/P Ratio** (F5.1) | $\Pi_{\text{axial}}$, $\Pi_{\text{periph}}$ alongside ratio | Ratio ↑ or ↓ driven by a single group’s share collapse |
| **T2 isolation** | $\Delta_{T1\to T2}$ vs. $\Delta_{T2\to T3}$ narrative table | T3 change attributed to psilocybin without checking training-only slope |
| **Block bootstrap** (Appendix D) | CI width vs. point estimate | Apparent shift smaller than within-session CI (if bootstrap enabled) |

### 5.1 Exploratory visualization — ATF vs joint variance share (optional)

This block is **not** a fifth primary feature. It is an **optional, exploratory** figure for regional interpretation when F1 and F5 are both available.

- **Quantities:** Per joint \(j\), session \(s\): **ATF\(_{j,s}\)** from F1 vs **\(\pi_{j,s}\)** from F5 (T1-anchored normalized joint variance shares; see [F5](#f5-joint-gini-coefficient)). \(\pi_{j,s}\) is **not** literal mechanical energy — it is **variance allocation** in the reference-anchored PCA attribution after per-feature standardization. Informal “energy” language in captions is allowed **only** with that one-line caveat.
- **Inferential status:** **Descriptive / exploratory** unless a small family of tests is pre-specified. Plotting does not add a new PCA fit. Heuristic quadrant labels (e.g. “Whip / Hum / Anchor / Driver”) are **interpretive only**, not cluster outputs.
- **Multiplicity:** Applies to **hypothesis claims**, not to descriptive plots; avoid over-claiming from 19 joints unless pre-registered.
- **Mask co-registration policy (`CONFIG`):** Expose **`atf_pi_mask_policy`** in the notebook preamble or `CONFIG`:
  - **`strict_pca_mask`** — For this plot only, compute ATF\(_{j}\) **restricted to the all-19-joint-clean frame mask** used for PCA so “time” and “variance share” align mathematically (recommended for committee-facing figures unless noted otherwise).
  - **`independent_definitions`** — Keep canonical F1 ATF\(_j\) (per-joint clean mask) alongside \(\pi_j\); the figure caption **must** state that denominators differ; see [§4.6](#46-conflict-register-automated-audit-tiering-and-analyst-acknowledgment).
- **Radar charts:** Overlaying two timepoints (e.g. Class 1 vs Class 10) on \(\pi_j\) and/or ATF\(_j\) is acceptable as descriptive comparison in the same anchored framework.
- **Export:** If used, include **`pi_<Joint>`** (or tidy long format) per session in `f5_results.csv` or a companion file; serialize **`atf_pi_mask_policy`** alongside figure exports.

#### Interactive Plotly HTML (normative)

- **Primary interactive deliverable:** For exploratory figures in this block (e.g. ATF vs joint variance share, joint radar overlays, longitudinal delta views when driven from tidy tables), **Plotly HTML** is the **primary** interactive export format unless the thesis committee requests static PDF/PNG only.
- **Weight limit (repository health):** **Interactive HTML is generated from tidy exports only** — aggregated or per-joint×session tables. **Full-resolution 120 Hz kinematics must never be embedded** in Plotly figures or serialized into HTML traces. Violating this risks **gigabyte-scale** artifacts and invalidates the “clean break” from raw pipeline stores.
- **Plotly JS:** HTML export **must** use **`include_plotlyjs='cdn'`** (or project-equivalent) so each file does not duplicate the full Plotly bundle; large multi-figure batches stay tractable.
- **Hover contract (joint-level plots):** Traces must expose hover metadata including **joint name**, **metric value**, **artifact rate** (session- and joint-level as applicable), and **session id** — via **columns present in the tidy table** passed into `v2_viz_engine`, not by joining back to wide Parquet inside the viz module.

---

## Appendix A: Schema Column Quick Reference

### Velocity & Position Columns (per joint)

| Column | Units | Use |
|--------|-------|-----|
| `{J}__lin_vel_rel_mag` | mm/s | ATF noise floor input |
| `{J}__lin_rel_px`, `_py`, `_pz` | mm | TM endpoint positions (TM uses four endpoints only; see [A.1](#a1-normative-joint-name-table-v2--parquet-prefixes)) |
| `{J}__zeroed_rel_omega_mag` | deg/s | D_eff, Joint Gini (dynamics branch) |
| `{J}__is_artifact` | bool | All features — artifact exclusion mask |
| `time_s` | seconds | All features — time axis |

Replace `{J}` with the **exact** joint strings in [A.1](#a1-normative-joint-name-table-v2--parquet-prefixes) (case-sensitive; matches column prefixes in `derivatives/step_06_kinematics/...__kinematics_master.parquet`).

### A.1 Normative joint name table (v2 / Parquet prefixes)

These **19** strings are the **only** valid `{Joint}` prefixes for F1, F4, F5 (dynamics branch), and Block 0’s all-joint masks. Order is the **canonical v2 column-major order** for stacked features (match **`ALL_19_JOINTS`** in `src/core_kinematics_engine.py` and implementing code).

| Index | `{Joint}` (exact string) | Example dynamics column |
|------:|--------------------------|-------------------------|
| 1 | `Hips` | `Hips__zeroed_rel_omega_mag` |
| 2 | `Spine` | `Spine__zeroed_rel_omega_mag` |
| 3 | `Spine1` | `Spine1__zeroed_rel_omega_mag` |
| 4 | `Neck` | `Neck__zeroed_rel_omega_mag` |
| 5 | `Head` | `Head__zeroed_rel_omega_mag` |
| 6 | `LeftShoulder` | `LeftShoulder__zeroed_rel_omega_mag` |
| 7 | `LeftArm` | `LeftArm__zeroed_rel_omega_mag` |
| 8 | `LeftForeArm` | `LeftForeArm__zeroed_rel_omega_mag` |
| 9 | `LeftHand` | `LeftHand__zeroed_rel_omega_mag` |
| 10 | `RightShoulder` | `RightShoulder__zeroed_rel_omega_mag` |
| 11 | `RightArm` | `RightArm__zeroed_rel_omega_mag` |
| 12 | `RightForeArm` | `RightForeArm__zeroed_rel_omega_mag` |
| 13 | `RightHand` | `RightHand__zeroed_rel_omega_mag` |
| 14 | `LeftUpLeg` | `LeftUpLeg__zeroed_rel_omega_mag` |
| 15 | `LeftLeg` | `LeftLeg__zeroed_rel_omega_mag` |
| 16 | `LeftFoot` | `LeftFoot__zeroed_rel_omega_mag` |
| 17 | `RightUpLeg` | `RightUpLeg__zeroed_rel_omega_mag` |
| 18 | `RightLeg` | `RightLeg__zeroed_rel_omega_mag` |
| 19 | `RightFoot` | `RightFoot__zeroed_rel_omega_mag` |

**Schema note:** Full `config/skeleton_schema.json` may list additional nodes (fingers, toes). **v2 kinematics features use only the 19 rows above.** There is **no** separate `Chest` joint in this table; **`Spine1`** is the mid-thoracic segment used in code. If a legacy notebook refers to “Chest,” map it to **`Spine1`** for column resolution or treat as out-of-spec for v2.

### Joint group definitions (same spelling as A.1)

| Group | Members | Feature use |
|-------|---------|-------------|
| **Axial** | Hips, Spine, Spine1, Neck, Head | ATF group summary (5 joints) |
| **Peripheral** | LeftForeArm, LeftHand, RightForeArm, RightHand, LeftFoot, RightFoot | ATF group summary |
| **Transitional** | LeftShoulder, RightShoulder, LeftArm, RightArm, LeftUpLeg, RightUpLeg, LeftLeg, RightLeg | ATF group summary |
| **TM endpoints** | LeftHand, RightHand, LeftFoot, RightFoot | F2 TM path integration |

---

## Appendix B: Master Execution Prompt (verbatim)

The lead developer provides the following prompt **verbatim** when initiating the notebook build with an AI agent:

---

**Act as a Senior Research Software Engineer.** We are going to build the feature extraction notebook (`notebooks/11_METH_SPEC_v2_Features.ipynb`) for my biomechanics thesis exactly as specified in `METHODOLOGY_SPEC_v2.md`.

**CRITICAL DIRECTIVE 1: STRICT ITERATIVE IMPLEMENTATION**  
You will **NOT** write the entire notebook at once. We will build, run, and verify this notebook **ONE block at a time**. After you provide the code for a block, you **MUST STOP** and wait for my confirmation before moving to the next one.

**CRITICAL DIRECTIVE 2: DOUBLE MATH VERIFICATION & MODULARITY**  
Before writing the Python logic for any feature block, you must:

1. **Quote** the exact mathematical formulation and constraints from `METHODOLOGY_SPEC_v2.md`.
2. **Write** a brief verification plan detailing how your NumPy/Pandas logic matches the requirement (e.g., verifying array shapes, ensuring artifacts are dropped and **NOT** interpolated, checking normalization denominators).
3. **Parameter check:** Explicitly list which **modular toggles** appear in the appropriate parameter dict (`CONFIG`, `PARAMS_F1`, `PARAMS_F2`, or `PARAMS_PCA_F4_F5`) for that block and confirm their **defaults** — including, where applicable: `run_bootstrap` (default **`False`**), `compute_ap_ratio` in `PARAMS_PCA_F4_F5` (default **`False`**), **`run_session_native_gini`** in `PARAMS_PCA_F4_F5` (default **`True`**), **`run_t2_isolation`** in **`CONFIG`** (default **`False`**), `noise_floor_override_mms_by_joint` in `PARAMS_F1` (default **`{}`**), **`kinematic_branch`** in `PARAMS_PCA_F4_F5` (default **`dynamics`**), `atf_pi_mask_policy` in `CONFIG` (when §5.1 is used), and keys in [§3.5](#35-per-block-information-tuning-contract-and-interactive-ux). State any deviation from these defaults if the lead developer requests it.

**The Build Sequence (Strictly Enforced):**  
We will proceed in this exact order. **Do not skip ahead.**

1. **Step 1:** Block 0 — Preamble, **`CONFIG`**, shared loaders (pure I/O), optional per-session **`apply_time_window`** calls (**library** function, **notebook** orchestration; see §3.2), Reliability Gates (`quality_df` gatekeeper table per [Block 0](#block-0--constraint-register--quality-table-specification)), Analyst decision cell (§3.4). Emit diagnostics **before** downstream parameter commits ([§3.5](#35-per-block-information-tuning-contract-and-interactive-ux)).
2. **Step 2:** Block 1 (F1: ATF). Needs `PARAMS_F1` (including noise-floor audit export and optional overrides; §F1, [§4.6](#46-conflict-register-automated-audit-tiering-and-analyst-acknowledgment)).
3. **Step 3:** Block 2 (F2: TM). Needs `PARAMS_F2`.
4. **Step 4:** Block 3 (Shared PCA Engine). Needs `PARAMS_PCA_F4_F5`. Run **[§4.6](#46-conflict-register-automated-audit-tiering-and-analyst-acknowledgment) Pre-PCA anchor checklist** immediately before **`PCA.fit`**. Respect **[§3.6](#36-pca-input-dimension-and-joint-level-artifact-conflict-19-feature-rule)** (no dropped columns for `transform`). Must be a **single** `fit` on T1 / reference session.
5. **Step 5:** Block 4 (F4: D_eff). Reads from Block 3. Needs `PARAMS_PCA_F4_F5`.
6. **Step 6:** Block 5 (F5: Joint Gini). Reads from Block 3. Needs `PARAMS_PCA_F4_F5`.
7. **Step 7 (optional):** Exploratory visualization / ipywidgets (§3.3, §5.1) — **after** Steps 1–6 validate; must not change PCA fits without re-running upstream.

**Library contract:** Implement `apply_time_window` in `src/v2_feature_engine.py` (or project-fixed module); **do not** embed windowing inside loaders. If `t_start_s` and `t_end_s` are both omitted, return the full recording unchanged (§3.2).

**UX contract:** Where interactive controls are used, bind **one widget per key** in `CONFIG`, `PARAMS_F1`, `PARAMS_F2`, or `PARAMS_PCA_F4_F5` and keep **`quality_df` / audit tables visible** next to decisions ([§3.5](#35-per-block-information-tuning-contract-and-interactive-ux)).

**Modular contract:** Implement feature math in **`src/v2_feature_engine.py`**, longitudinal deltas and longitudinal delta bootstrap in **`src/v2_longitudinal.py`**, and Plotly/HTML in **`src/v2_viz_engine.py`** per [§3.3](#33-implementation-architecture--library-notebook-legacy-isolation). Do not embed visualization or longitudinal contrast logic inside pure feature functions.

**Parameter contract:** Use **four consolidated parameter dicts**: `CONFIG` (gates + global + longitudinal), `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5` (shared PCA + D_eff + Gini + A/P). Do not create additional parameter namespaces.

---

## Appendix C: Thesis Result Package — export manifest & provenance

This appendix is **normative** for a **thesis-grade** export bundle per subject analysis. Paths are illustrative under `results/meth_v2/{subject_id}/`; filenames may be project-fixed but **roles** must match.

### C.1 Core artifacts (minimum set)

| File / directory | Role |
|------------------|------|
| **`quality_audit.csv`** | One row per `run_id`: Block 0 gatekeeper fields (`artifact_fraction`, `clean_duration_s`, `dead_recording`, flags, etc.) — audit trail for exclusions. |
| **`feature_scalars.parquet`** | **Tidy** session table: one row per session with F1–F5 primary scalars and key companions (machine-readable; CSV allowed if parquet unavailable). |
| **`longitudinal_deltas.json`** | Array of records: paired contrasts (e.g. Class 10 − Class 1) per metric; optional CI columns if bootstrap run ([Appendix D.2](#d2-longitudinal-delta-bootstrap-optional)). |
| **`viz/`** (or project-fixed name) | **Interactive** Plotly HTML exports only — built from tidy inputs per [§5.1](#51-exploratory-visualization--atf-vs-joint-variance-share-optional); **no** raw kinematics embedded. |
| **`run_metadata.json`** | Merged **parameter snapshot**: all four parameter dicts (`CONFIG`, `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5`), analyst overrides, spec identifier (`METHODOLOGY_SPEC_v2`), and **pointers** to `environment_specs.json` and `execution_audit.json`. |

### C.2 `environment_specs.json` (environment provenance)

**Purpose:** “Time capsule” for the **software environment** so results can be interpreted or replayed years later.

| Field (recommended) | Description |
|---------------------|-------------|
| `python_version` | e.g. `3.11.x` |
| `package_versions` | At minimum: `numpy`, `pandas`, `scikit-learn`, `plotly`, `pyarrow` (if parquet) — pinned versions or full **`pip freeze`** / lockfile hash |
| `git_commit` | Full **Git** commit hash of the repo at run time; optional `git_branch`, `is_dirty` |
| `spec_revision` | Reference to this document (e.g. file hash or commit + path) |

### C.3 `execution_audit.json` (run identity)

**Purpose:** Audit **who ran what, when**, with which **stochastic** settings.

| Field (recommended) | Description |
|---------------------|-------------|
| `utc_timestamp` | ISO-8601 end (or start) of run |
| `analyst_id` | Short identifier (initials, ORCID, or project id — no PII beyond project policy) |
| `bootstrap_seeds` | All seeds used: global, per-feature **`bootstrap_seed`** ([Appendix D.1](#d1-within-session-block-bootstrap)), longitudinal delta bootstrap if any ([Appendix D.2](#d2-longitudinal-delta-bootstrap-optional)) |
| `input_manifest` | List of input Parquet paths + optional **content hashes** (SHA-256) or size/mtime for traceability |

### C.4 Post-run summary artifacts

| File | Role |
|------|------|
| **`session_summary.md`** and/or **`session_summary.html`** | Static copy of the [§3.4](#34-information-first-workflow-and-analyst-authority) master summary table with **OK / WARNING / CRITICAL** badges |

### C.5 Repository policy

Large HTML trees under `results/` should **not** bloat Git: use **`.gitignore`** or LFS per lab policy; the **manifest JSON/CSV** and **`run_metadata.json`** are the minimum committed record of what was produced.

### C.6 Optional artifacts and skipped blocks (normative)

Readers of `results/meth_v2/{subject_id}/` must be able to tell **what was not run** from machine-readable metadata, not from missing-file guesswork.

| Situation | Required behavior |
|-----------|-------------------|
| **Bootstrap not run** (`run_bootstrap` **False** everywhere; no longitudinal delta bootstrap) | **Omit** `*_block_bootstrap_ci.parquet` / equivalent CI sidecars. **`run_metadata.json`** must set **`bootstrap_run: false`** (or list per-feature `run_bootstrap` flags). Do **not** write empty CI files unless the analyst enables an explicit **`write_placeholder_exports`** flag for committee packaging. |
| **T2 isolation not run** | **Omit** `t2_isolation_summary.csv` (or project-fixed name). **`run_metadata.json`** must include **`t2_isolation_run: false`** (mirror **`CONFIG['run_t2_isolation']`**). |
| **Session-native Gini skipped** (`run_session_native_gini` **False**) | Native Gini columns omitted or marked **`session_native_gini_skipped: true`** in F5 export and **`run_metadata.json`**. |
| **Session-native D_eff skipped** (`run_session_native_deff` **False**) | Native D_eff columns omitted or marked **`session_native_deff_skipped: true`** in F4 export and **`run_metadata.json`**. |
| **Exploratory viz not run** | **Omit** or leave `viz/` empty; **`run_metadata.json`** lists **`viz_exported: false`** or enumerates produced HTML paths. |
| **Any optional block skipped** | Prefer a single **`export_manifest.json`** (or equivalent keys inside **`run_metadata.json`**) with **`artifacts_produced`**, **`artifacts_skipped`**, and **`skip_reason`** per skipped role — e.g. `{ "bootstrap_ci": "skipped_run_bootstrap_false" }`. |

This does not replace **`execution_audit.json`** stochastic logging; it complements it for static directory inspection.

---


## Appendix D: Block Bootstrap — Full Protocol

This appendix contains the complete block bootstrap specification. The main body (Appendix D) provides a summary; this is the normative reference for implementation.

### D.1 Within-session block bootstrap

In an **N=3** design, **within-session sampling variability** matters: a shift (e.g. $D_{\text{eff}}$ from 4.0 to 5.5) should be interpreted relative to how stable the metric is **under resampling of that same recording**.

#### Forbidden: naive frame-wise bootstrap

**Do not** resample individual frames i.i.d. Kinematic series at 120 Hz are **strongly autocorrelated**; i.i.d. resampling yields **falsely narrow** confidence intervals.

#### Protocol (non-overlapping block bootstrap)

1. **Segment:** Partition the session (clean frames or full frames per feature’s spec) into **contiguous non-overlapping blocks** of length $L$ frames. Default **`L = 240`** (2.0 s at 120 Hz), exceeding the dominant autocorrelation scale for many full-body kinematic summaries. Expose as `run_bootstrap`, `bootstrap_block_frames` in the relevant feature dict (`PARAMS_F1`, `PARAMS_F2`, or `PARAMS_PCA_F4_F5`). **Frontend in seconds:** interactive sliders may use `bootstrap_block_sec`; convert with $L = \texttt{round}(\texttt{bootstrap\_block\_sec} \times f_s)$ (e.g. 2.0 s → 240 frames at 120 Hz). Document both in export metadata if seconds are used in the UI.
2. **Resample:** Draw blocks **with replacement** until the synthetic series length matches the original (or a pre-specified target). Repeat **$B$** times. Default **`B = 1000`**. Expose as `bootstrap_n_draws`. Set **`numpy` / `random` seed** via `bootstrap_seed` for reproducibility.
3. **Recompute metric** on each synthetic replicate:
   - **ATF, TM:** Recompute from the **bootstrap-resampled frame sequence** using the same formulas as F1/F2 (artifact masks applied **within** each replicate).
   - **$D_{\text{eff}}$, Joint Gini (T1-anchored), A/P Ratio:** **Do not** `PCA.fit` on bootstrap data. **Freeze** the **T1-anchored** `StandardScaler` and `PCA` from Block 3; **only** `transform` the bootstrap sample (scaled with the **frozen** scaler) and recompute `var_per_pc` → $D_{\text{eff}}$, $\pi_{j,s}$ → Gini / A/P. This preserves the **reference basis** across replicates.
   - **Session-native Gini / D_eff:** If bootstrapped, requires a **separate policy** (e.g. skip or refit PCA per replicate — **expensive and unstable**); default recommendation: **bootstrap only anchored metrics** unless pre-registered.
4. **Extract CI:** For a $(1-\alpha)$ interval (default **95%**, $\alpha=0.05$), use the **percentile method**: e.g. **[2.5th, 97.5th]** percentiles of the $B$ replicate values. Expose `bootstrap_ci_level` (default `0.95`).

#### Implementation control

- Expose as an optional utility, e.g. `bootstrap_ci(metric_name, session_df, pca_engine_frozen, params)`.
- **Toggle per feature:** `PARAMS_F1['run_bootstrap']`, `PARAMS_F2['run_bootstrap']`, `PARAMS_PCA_F4_F5['run_bootstrap']` — each default **`False`** for fast iteration; set **`True`** only for **final thesis export** or sensitivity figures.
- **Cost / performance:** $B \times$ metric cost per session; keep off during development. Implementations should prefer **vectorized or batched** resampling where feasible; avoid naive Python loops over all $B$ draws on full 120 Hz series without profiling. For large $B$ or many sessions, **document** estimated runtime and memory before launching (see [§4.6](#46-conflict-register-automated-audit-tiering-and-analyst-acknowledgment)).

#### Performance bottleneck and vectorization (normative for `bootstrap_ci`)

- **Bottleneck:** Block bootstrap at **120 Hz**, **$B=1000$**, and multi-joint / PCA metrics can dominate runtime. Expect **seconds to minutes** per session when enabled; scale roughly with $B$ × (cost of one metric evaluation on a synthetic index sequence).
- **Simplification:** Implement **`bootstrap_ci`** (or equivalent) by resampling **block indices**, not by nested Python loops over **frames** for each of $B$ replicates. **Normative pattern:** partition into non-overlapping blocks; draw $B$ replicate **lists of block ids** with `numpy.random.Generator.choice` (or batch draws), then **index** the underlying arrays in vectorized chunks. Avoid `for b in range(B): for t in range(T):` over raw timeline when profiling shows it is hot.
- **Notebook:** Surface this in the [preamble cautions](#notebook-preamble--implementation-cautions-read-first) cell so users know bootstrap is optional and expensive.

**Bootstrap seed scope (audit trail):** Each feature dict may define its own **`bootstrap_seed`** when `run_bootstrap` is **True**. **Default:** seeds are **independent per feature block** (do not silently reuse one integer across F1 and PCA unless the analyst explicitly sets them equal). **Optional:** `CONFIG['bootstrap_master_seed']` may be used to **derive** per-block seeds deterministically (e.g. `master + hash(feature_id)`); if present, document the derivation in **`run_metadata.json`**. Longitudinal delta bootstrap (D.2) uses **`CONFIG['longitudinal_bootstrap_seed']`** (or project-fixed key) **separate** from within-session seeds. **`execution_audit.json`** / **`run_metadata.json`** must list **every** seed used in the run.

### D.2 Longitudinal delta bootstrap (optional)

Two different bootstrap **targets** must not be confused:

| | **D.1 Within-session block bootstrap** | **Longitudinal / delta bootstrap (optional)** |
|---|----------------------------------------|-----------------------------------------------|
| **Question** | How stable is metric $m$ **under resampling of one session’s frames**? | How uncertain is a **contrast** between sessions (e.g. $\Delta m = m_{T3} - m_{T1}$) given within-session variability? |
| **Inputs** | One session’s data + frozen PCA for anchored metrics | Per-session point estimates and/or nested resampling policy defined in notebook |
| **Typical output** | CI for $m_s$ for session $s$ | CI for $\Delta m$ or for trajectory slope |
| **Parameters** | `PARAMS_F1`, `PARAMS_F2`, `PARAMS_PCA_F4_F5` bootstrap keys | **`CONFIG`** longitudinal keys — e.g. `run_longitudinal_delta_bootstrap` (default **`False`**), block length, $B$, seed — **pre-specify** if used for thesis claims |
| **Relation to D.1** | Uses the **same** block-bootstrap machinery for **single-session** resampling | **Additional** layer; may call D.1 per session as a building block or use a separate implementation — document which |

**Normative:** Primary F1–F5 scalars and pre-registered longitudinal deltas may be reported **without** any bootstrap. If **both** are run, export to **separate files** (see [export bundle](#recommended-export-bundle-thesis-lock-in)) and label figures/tables unambiguously.

---

## Appendix E: T2 Isolation Gate — Full Protocol

This appendix contains the full T2 Isolation Gate specification. The main body (§2 Reliability Gates) provides a summary; this is the normative reference for implementation.

### Rationale

This gate addresses a **high-risk interpretive confound:** directional change at **T3** (e.g. afterglow) could reflect **demand characteristics** or voluntary “moving more freely” because the participant knows they received psilocybin, rather than a neuroplastic effect distinct from **Gaga training alone**.

**Internal control:** **T2** = post-training, **pre-psilocybin**. Comparing **T1→T2** (pure training) vs. **T2→T3** (psilocybin on top of training) helps **disambiguate** training-only trajectories from post-intervention shifts.

### Execution logic

This module is **optional**. Implementation lives in **`src/v2_longitudinal.py`** (contrast logic on tidy session scalars — **not** Block 0 gates). It runs **only if**:

1. **`CONFIG['run_t2_isolation']`** is **`True`**, and
2. **`quality_df`** (or equivalent session registry) contains valid, non–hard-excluded rows for **T1, T2, and T3** for the subject under analysis.

For any scalar metric $m \in \{\text{ATF}, D_{\text{eff}}, \text{TM}, \text{Gini}\}$ (use the **same session-level summary** already defined for F1–F5; specify which ATF aggregate, e.g. whole-body median, in the analysis record):

$$\Delta_{T1 \to T2}^{(m)} = m_{T2} - m_{T1}, \qquad \Delta_{T2 \to T3}^{(m)} = m_{T3} - m_{T2}$$

Also report the **total** trajectory when useful: $\Delta_{T1 \to T3}^{(m)} = m_{T3} - m_{T1}$.

### Narrative truth table

| Condition on deltas | Inference label |
|---------------------|-----------------|
| $\Delta_{T1 \to T2}$ and $\Delta_{T2 \to T3}$ have the **same sign** (both positive, both negative, or both zero) | **Monotonic** — training and post-psilocybin segments **reinforce** the same direction; **cannot cleanly dissociate** training contribution from psilocybin contribution from kinematics alone. |
| $\Delta_{T2 \to T3}$ **reverses** the sign of $\Delta_{T1 \to T2}$ (e.g. training increased $m$ but T2→T3 decreased $m$, or conversely) | **Reversal** — **non-monotonic** trajectory; interpret as possible **redirecting** effect of psilocybin (or strategy shift) relative to training-only trend. **Do not over-claim** mechanism; N is small. |

### Parameter control

| Key | Type | Default | Behavior |
|-----|------|---------|----------|
| `run_t2_isolation` | `bool` | **`False`** | If **`False`**, skip all $\Delta_{T1 \to T2}$ / $\Delta_{T2 \to T3}$ rows; report only $\Delta_{T1 \to T3}$ (or Class 1→10) as pre-specified for the primary narrative. If **`True`**, compute the table above for each metric and export (e.g. `t2_isolation_summary.csv`). |

**Normative:** `run_t2_isolation` lives in **`CONFIG`** (longitudinal section). The notebook preamble should state one line: *T2 isolation is controlled by **`CONFIG['run_t2_isolation']`*** so implementers do not search other dicts for this flag.

---

## Amendment — Ticket 010 (2026-05-19): Hips Excluded from ATF_axial

**Change:** `JOINT_GROUPS["axial"]` in `src/v2_feature_engine.py` updated from
`["Hips", "Spine", "Spine1", "Neck", "Head"]` to `["Spine", "Spine1", "Neck", "Head"]`.

**Rationale:** Hips is the **root joint** of the skeleton hierarchy. ATF is computed
from `__lin_vel_rel_mag` columns, which are derived from **root-relative** position
columns. By construction, the root joint's root-relative position is identically zero,
hence its root-relative velocity magnitude is identically zero, hence `Hips__atf = 0`
for every session.

Including this structural zero in the **median** over the axial group systematically
biased `atf_axial` downward — not as a measurement of dance dynamics, but as a
mathematical artifact of using the root joint as one of the medianed values.

**Empirical impact on the Dev Set (4 sessions):**
- 651_T1_P1_R1: atf_axial 0.8098 → 0.8202 (+1.28 %)
- 651_T2_P1_R1: 0.8537 → 0.8537 (+0.00 % — Hips already absent from this session's
  per-joint dict due to a separate downstream S04 NaN issue documented in
  `MUB_NB06_lin_kine_nan_gate_2026-05-18.md`)
- 671_T1_P2_R1: 0.9667 → 0.9676 (+0.09 %)
- 671_T3_P2_R1: 0.9264 → 0.9300 (+0.38 %)

All impacts are positive (median rises) and ≤ 1.3 %, confirming the magnitude is
small but the bias was real.

**Reference:** Phase 7 F-012, Phase 10 LD-12, Ticket 010 implementation log
`docs/pipeline_rebuild_audit/implementation_logs/ticket_010_hips_atf_axial.md`.

---

*End of Methodology Specification v2.*
