# Future Features Salvage Register

**Purpose:** Catalog of scientific concepts, formulas, and visualization strategies extracted from NB07 (Pulsicity & Flow), NB09 (Subject Exploration Dashboard), NB10 (EDA & PCA), and `src/v2_feature_engine.py` before these notebooks are archived into `legacy/`. This document is the intellectual-property record: the notebooks will be moved, but these ideas will not be lost.

**Date extracted:** 2026-05-14
**Sources:** `notebooks/07_pulsicity_flow.ipynb`, `notebooks/09_Subject_Exploration_Dashboard.ipynb`, `notebooks/10_EDA_PCA.ipynb`, `src/pulsicity.py`, `src/v2_feature_engine.py`, `src/utils_nb07.py`

---

## Part 1 — Pulsicity & Flow Metrics (NB07 + pulsicity.py)

### 1.1 Core Concept

Pulsicity quantifies the **temporal structure of motion bursts** in a segment's linear velocity magnitude signal. The central idea: Gaga movement is not continuous — it is episodic. The metrics below characterize *how many times per minute the body crosses the noise threshold*, *how rhythmic those bursts are*, and *how smooth or fragmented the velocity profile is*.

The input signal is always `{segment}__lin_vel_rel_mag` (linear velocity magnitude in mm/s, root-relative).

---

### 1.2 Noise Floor V (session-adaptive threshold)

**Concept:** Per-session, per-segment baseline velocity level below which motion is considered "resting." This replaces a fixed threshold with a data-driven one derived from the static reference window at the session start.

**Algorithm:**
1. Find the static reference window (first stable ~2s of the session, same window as Step 05).
2. Compute mean velocity in that window: `V_static = mean(v[t_ref])`.
3. Fallback: if no stable window, use 5th percentile of whole-session velocity.
4. Apply floor guard: `V = max(V, 1.0 mm/s)`.

```python
# Pseudocode (from pulsicity.py::compute_noise_floor)
static_window = find_static_reference_window(df, cfg)  # same as Step 05
V_static = np.mean(v[static_window])
V = max(V_static, noise_floor_guard_mms)  # guard: 1.0 mm/s
```

**Thesis use:** Floor V separates "resting" from "active" frames without manual threshold setting. Enables cross-session and cross-subject comparison.

---

### 1.3 Active Time Fraction (ATF)

**Concept:** Proportion of clean frames where velocity exceeds the noise floor. Whole-body ATF is the median over all 19 joints. Sub-group ATFs are provided for axial, peripheral, and transitional joint groups.

**Formula (from v2_feature_engine.py::compute_atf):**

```
ATF_joint = |{t : v(t) > V  AND  ¬artifact(t)}| / N_clean
ATF_wb    = median(ATF_joint  for  joint ∈ all_19_joints)
ATF_axial = median(ATF_joint  for  joint ∈ {Hips, Spine, Spine1, Neck, Head})
ATF_peripheral = median(ATF_joint  for  joint ∈ {LeftForeArm, LeftHand, RightForeArm, RightHand, LeftFoot, RightFoot})
```

```python
# Pseudocode
active = np.sum((vel > V) & ~artifact)
atf = active / n_clean_frames
```

**Joint groups defined in v2_feature_engine.py:**
- `axial`: Hips, Spine, Spine1, Neck, Head
- `peripheral`: LeftForeArm, LeftHand, RightForeArm, RightHand, LeftFoot, RightFoot
- `transitional`: LeftShoulder, RightShoulder, LeftArm, RightArm, LeftUpLeg, RightUpLeg, LeftLeg, RightLeg

**Thesis use:** ATF is the primary "movement activity" index. Hypothesis H3 (NB09): *ATF increases from T1 to T2 as dancer learns Gaga movement vocabulary.*

---

### 1.4 Peaks Per Minute (PPM)

**Concept:** Count of distinct velocity peaks above the noise floor per minute of *active time* (not total time). A peak is detected using `scipy.signal.find_peaks` with adaptive prominence threshold.

**Formula (from pulsicity.py::aggregate_pulsicity_metrics):**

```
T_a = |{t : v(t) > V  AND  ¬artifact(t)}| / fs   [seconds of active time]

PPM = (N_peaks / T_a) × 60

Special cases:
  N_p = 0,  T_a > 0  →  PPM = 0.0   (fluid, non-pulsive movement is valid)
  N_p = 0,  T_a = 0  →  PPM = NaN   (no active movement)
```

**Peak detection parameters:**
- Prominence threshold: `prominence_multiplier × σ_v` (adaptive to session)
- Minimum inter-peak distance: configurable (default ~100ms)
- Height gate: peaks must be above noise floor V

```python
# Core peak detection (from detect_velocity_peaks)
prominence_threshold = prominence_multiplier * sigma_v  # sigma_v = std(v_m) above floor
peaks, properties = find_peaks(
    v_search,
    prominence=prominence_threshold,
    height=V,
    distance=min_dist_frames
)
```

**Thesis use:** PPM captures rhythmic structure. High PPM = many discrete impulses (punchy Gaga style); low PPM with high ATF = fluid movement (wave-like Gaga style).

---

### 1.5 Inter-Peak Interval (IPI) and IPI_CV

**Concept:** Time intervals between consecutive velocity peaks. IPI_CV (coefficient of variation) measures *rhythmic regularity*: low IPI_CV = metronomic pulsing; high IPI_CV = irregular, unpredictable timing.

**Formula:**

```
IPI_k = (peak_index[k+1] - peak_index[k]) / fs   [seconds]
μ_IPI = mean(IPI_k)
σ_IPI = std(IPI_k)
CV_IPI = σ_IPI / μ_IPI       (NaN when N_peaks < 2 or μ_IPI = 0)
```

**Thesis use:** CV_IPI distinguishes *rhythmic pulsicity* (low CV, likely music-locked) from *arrhythmic pulsicity* (high CV, internally driven improvisation).

---

### 1.6 Mean Peak Velocity

```
v̄_peak = (1/N_peaks) Σ v(t_k)   [mm/s]
```

**Thesis use:** Characterizes the *intensity of individual impulses*, independent of their frequency.

---

### 1.7 SPARC — Spectral Arc Length (Movement Smoothness)

**Concept:** SPARC measures movement smoothness in the frequency domain. More negative SPARC = more fragmented/pulsive movement. SPARC → 0 when movement approaches a single-lobe velocity profile (maximally smooth).

**Formula (from pulsicity.py::compute_sparc, following Balasubramanian et al. 2012):**

```
V̂(f) = |FFT(v_m(t))| / |FFT(v_m(t))[f=0]|   (normalized amplitude spectrum)

f_cap  = SavGol effective cutoff (99% amplitude threshold — first frequency where
         SavGol attenuates by >1%)

SPARC = -∫₀^{f_cap} √((1/f_cap)² + (dV̂/df)²) df
```

**Key implementation details:**
- f_cap is the SavGol effective cutoff, NOT the Winter filter cutoff — this prevents over-estimation of SPARC due to filtering artifacts.
- The amplitude threshold (0.05) trims the integration range to where V̂(f) ≥ 0.05 (replicates original SPARC paper).
- **PCHIP gap bridging:** NaN gaps in v_m are bridged with PCHIP before SPARC computation (to avoid FFT artifacts). The PCHIP-bridged signal is used ONLY for SPARC — the Measurement Signal is never altered.

```python
# Compute SavGol effective cutoff (99% amplitude threshold)
magnitude = np.abs(freq_response)  # SavGol frequency response
threshold = dc_gain * 0.99
f_eff = first_frequency_where_magnitude_crosses_below(threshold)

# SPARC integration
v_hat = normalized_spectrum_up_to_f_cap
arc_length_elements = np.sqrt((1.0 / f_cap)**2 + np.gradient(v_hat, df)**2)
sparc = -np.trapz(arc_length_elements, freqs)
```

**Thesis use:** SPARC complements PPM. High PPM + very negative SPARC = highly pulsive and fragmented. High ATF + SPARC near 0 = fluid continuous movement.

---

### 1.8 PSD Diagnostic

**Concept:** Welch power spectral density estimate of velocity signal, used as a human-readable quality check. Computes `noise_ratio = P_noise / P_signal` where:
- Signal band: 0.5–10 Hz
- Noise band: 15–50 Hz

If `noise_ratio ≥ 0.15`, a secondary Butterworth filter is recommended for that segment (human-triggered, per-segment).

**Thesis use:** Justifies per-segment secondary filtering decisions in thesis methods section.

---

### 1.9 Total Movement (TM) — from v2_feature_engine.py

**Concept:** Summed 3D path length of the four distal endpoints (LeftHand, RightHand, LeftFoot, RightFoot) across the session, excluding artifact frames. Uses contiguous-run logic to avoid artifact-masked frame discontinuities.

**Formula:**

```
For each endpoint ep:
  Build contiguous clean runs (no artifact)
  For each run: TM_ep += Σ ||p(t+1) - p(t)||
TM_total = Σ TM_ep    [mm]
TM_rate  = TM_total / clean_duration_s   [mm/s]
```

**Endpoints:** LeftHand, RightHand, LeftFoot, RightFoot (TM_ENDPOINTS in v2_feature_engine.py)

**Thesis use:** TM_total is the "how much the body moved" measure, independent of timing structure. Pairs with ATF for an activity × intensity characterization.

---

## Part 2 — Subject Exploration & Longitudinal Analysis (NB09)

### 2.1 T1-Anchored PCA

**Concept:** PCA basis fitted on the T1 (baseline) session; subsequent sessions (T2, T3) are projected into the same T1 space. This anchors the reference frame so that changes in PC scores reflect *real movement changes*, not reorientation of the PCA axes.

**Implementation (v2_feature_engine.py::build_pca_engine):**
1. Fit `StandardScaler` on clean T1 reference frames.
2. Fit `PCA(n_components=19)` on scaled T1 data.
3. Freeze scaler and PCA. Transform T2/T3 using frozen scaler + frozen PCA.
4. Compute `var_per_pc` per session = variance of projected scores in each PC.

```python
# Reference-anchored PCA
scaler.fit(X_ref_T1)       # fit on T1 only
X_ref_scaled = scaler.transform(X_ref_T1)
pca.fit(X_ref_scaled)      # fit on T1 only
# For T2/T3:
X_t2_scaled = scaler.transform(X_t2)   # frozen scaler
Y_t2 = pca.transform(X_t2_scaled)      # frozen PCA
```

**Feature space:** 19-dimensional (`{joint}__zeroed_rel_omega_mag` for all 19 joints) — the "dynamics branch."

---

### 2.2 ATF Heatmap Visualization

**Concept:** 2D heatmap: rows = joints (19), columns = time windows within session. Color = ATF value in each window. Shows which joints are active at which times within a session.

**Used in NB09:** `plot_atf_heatmap(atf_by_run, subjects, save_path)` from `src/v2_feature_engine.py` or a visualization module.

```python
# Pseudocode for ATF heatmap
atf_matrix = np.zeros((n_joints, n_windows))
for w, (t_start, t_end) in enumerate(time_windows):
    window_df = df[(df.time_s >= t_start) & (df.time_s < t_end)]
    for j_idx, joint in enumerate(ALL_19_JOINTS):
        atf_matrix[j_idx, w] = compute_atf_single_joint(window_df, joint, V[joint])

plt.imshow(atf_matrix, aspect='auto', cmap='YlOrRd')
plt.yticks(range(n_joints), ALL_19_JOINTS)
plt.xlabel("Time window")
plt.colorbar(label="ATF")
```

---

### 2.3 Longitudinal Summary Plot

**Concept:** Line plot showing key metrics (ATF_wb, TM_rate, D_eff, Gini) across T1→T2→T3 for one or both subjects. Visual representation of longitudinal change trajectory.

**Used in NB09:** `plot_longitudinal_summary(delta_df, save_path)` — returns both Plotly (interactive) and Matplotlib (static/PDF-ready) figures.

---

### 2.4 Cross-Subject Trajectories Plot

**Concept:** Scatter plot in PC1–PC2 space showing T1, T2, T3 positions for each subject as connected arrows. Visualizes whether subjects' motor repertoires diverge or converge over time.

**Used in NB09:** `plot_cross_subject_trajectories(delta_df, save_path)`

---

### 2.5 Hypothesis Testing Framework (NB09 Section 6)

NB09 implements a structured hypothesis assessment for the thesis:

| Hypothesis | Metric | Direction |
|---|---|---|
| H1 | Greater whole-body movement richness (D_eff ↑) | + |
| H2 | More complex joint coordination (Gini ↓) | − |
| H3 | Increased movement activity (ATF ↑) | + |

Assessment uses `cross_subject_consistency` labels per delta metric (whether both subjects show the same directional change T1→T3).

---

## Part 3 — PCA Complexity Metrics (NB10 + v2_feature_engine.py)

### 3.1 Three-Branch PCA Architecture (NB10)

NB10 implements a 3-branch PCA:
- **Branch A (Dynamics):** 19 features = `{joint}__zeroed_rel_omega_mag` — angular velocity magnitudes
- **Branch B (Pose):** quaternion components `q_w, q_x, q_y, q_z` per joint — body shapes
- **Branch C:** (not fully reconstructed from available code)

Combined fit on T1+T2+T3 pooled data (unlike NB09/v2_feature_engine which uses T1-anchored).

---

### 3.2 D_eff — Effective Dimensionality (Participation Ratio)

**Concept:** How many "degrees of freedom" are effectively used by the movement. D_eff = 1 means all variance is in one PC (maximally simple). D_eff = K means variance is distributed equally across all K PCs (maximally complex).

**Formula (v2_feature_engine.py::compute_d_eff — participation ratio, Poggio et al.):**

```
λ_k  = variance in PC_k  (from session projection, not eigenvalue of reference)
p_k  = λ_k / Σλ_k        (proportion)
D_eff = 1 / Σ(p_k²)      (participation ratio)
D_eff_norm = D_eff / K    (normalized to [0, 1])
```

```python
var_per_pc = np.var(Y_session, axis=0)   # variance of scores per PC
p = var_per_pc / np.sum(var_per_pc)
d_eff = 1.0 / np.sum(p ** 2)
d_eff_norm = d_eff / K   # K = n_components = 19
```

**Also:** `n90` = minimum number of PCs explaining ≥90% of variance (alternative dimensionality metric).

```python
cum_var = np.cumsum(np.sort(var_per_pc)[::-1]) / np.sum(var_per_pc)
n90 = np.searchsorted(cum_var, 0.90) + 1
```

**Thesis use:** D_eff_norm tracks whether the dancer's movement repertoire becomes richer (higher D_eff_norm) or more stereotyped (lower) over T1→T2→T3.

---

### 3.3 Joint Gini Coefficient (F5)

**Concept:** Measures *inequality of joint contribution to PCA variance*. High Gini = one or two joints dominate the movement (inequality). Low Gini = all joints contribute equally (distributed coordination).

**Formula (v2_feature_engine.py::compute_joint_gini):**

```
Per-feature variance attribution:
α_f = Σ_k (λ_k · w_{k,f}²)   where w_{k,f} = PCA loading (PC_k, feature_f)

Joint proportion:
π_f = α_f / Σα_f

Gini coefficient (sorted-form):
G = (2 Σ_i i·π_(i)) / (n Σπ) - (n+1)/n
  where π_(i) are sorted in ascending order
```

```python
def _gini_coefficient(values):
    x = np.sort(values)
    n = len(x)
    total = np.sum(x)
    indices = np.arange(1, n + 1)
    return (2.0 * np.sum(indices * x)) / (n * total) - (n + 1.0) / n
```

**T1-anchored mode:** Uses frozen reference PCA loadings + per-session `var_per_pc`. This ensures the Gini measures change in coordination pattern relative to T1 baseline.

**Session-native mode:** Fresh PCA per session using mean-centered (NOT standardized) data. Note: StandardScaler must NOT be applied here — it forces all variances to 1 and makes the attribution formula collapse to identity (Gini = 0).

---

### 3.4 Axial-Peripheral Ratio (A/P Ratio, F5.1)

**Concept:** Are axial joints (spine, neck, hips) or peripheral joints (hands, feet) driving the PCA variance? Ratio > 1 = core-dominated; < 1 = limb-dominated.

**Formula (v2_feature_engine.py::compute_ap_ratio):**

```
π_axial      = Σ(π_f for f in {Hips, Spine, Spine1, Neck, Head})
π_peripheral = Σ(π_f for f in {LeftForeArm, LeftHand, RightForeArm, RightHand, LeftFoot, RightFoot})
AP_ratio = π_axial / π_peripheral
```

---

### 3.5 3D Convex Hull Volume (NB10)

**Concept:** Volume of the convex hull in PC1×PC2×PC3 space. Measures the *spatial extent of the movement state space* — larger volume = more diverse motor repertoire.

**NB10 function:** `calculate_3d_hull_volume(pca_results)` and `calculate_robust_3d_hull_volume(pca_results, trim_pct=5.0)` (5% outlier trimming for robustness).

```python
from scipy.spatial import ConvexHull
scores_3d = Y[:, :3]   # first 3 PCs
hull = ConvexHull(scores_3d)
volume = hull.volume   # in PC-score units³
```

**Robust version:** Trim top/bottom 5% of points per PC before hull computation.

---

### 3.6 State Space Entropy (NB10)

**Concept:** Shannon entropy of the discretized PC score distribution. Measures *uniformity of state space occupation*. High entropy = movement visits many regions of the PC space uniformly; low entropy = movement is concentrated in a few regions (stereotyped).

**NB10 function:** `calculate_state_space_entropy(pca_results, n_bins=25)`

```python
# Pseudocode
hist, _ = np.histogramdd(Y[:, :3], bins=25)
p = hist / hist.sum()
p = p[p > 0]
entropy = -np.sum(p * np.log(p))   # nats
```

---

### 3.7 Sample Entropy (SampEn, NB10)

**Concept:** Sample Entropy of the PC1 time series. Measures *temporal unpredictability* — how likely is it that patterns of m consecutive PC1 values repeat at tolerance r? Low SampEn = highly predictable/repetitive movement; high SampEn = irregular, non-repetitive.

**NB10 function:** `calculate_sample_entropy(pca_results, m=2, r_factor=0.2)` (r = 0.2 × std of PC1)

```python
# SampEn pseudocode (template matching method)
m = 2
r = 0.2 * np.std(pc1_series)
B = count_templates_matching(pc1_series, m=m, r=r)     # m-matches
A = count_templates_matching(pc1_series, m=m+1, r=r)   # (m+1)-matches
sampen = -np.log(A / B)
```

---

### 3.8 Centroid Displacement (NB10)

**Concept:** How far the centroid of the PC score cloud shifts from T1 to T2 to T3. Measures *directional drift* in the movement state space — i.e., whether the dancer's "typical posture" in kinematic space changes over sessions.

**NB10 function:** `calculate_centroid_displacement(pca_results)`

```python
centroid_T1 = np.mean(Y_T1[:, :3], axis=0)
centroid_T2 = np.mean(Y_T2[:, :3], axis=0)
centroid_T3 = np.mean(Y_T3[:, :3], axis=0)
displacement_T1_T2 = np.linalg.norm(centroid_T2 - centroid_T1)
displacement_T1_T3 = np.linalg.norm(centroid_T3 - centroid_T1)
```

---

### 3.9 Density Shift Matrix Visualization (NB10)

**Concept:** For each pair of sessions (T1→T2, T2→T3, T1→T3), compute a 2D kernel density estimate in PC1×PC2 space and plot the density *difference*. Positive regions = new movement patterns gained; negative regions = patterns lost.

**NB10 function:** `plot_density_shift_matrix(pca_results)` — produces a 3×3 matrix of difference plots.

```python
# Pseudocode
from scipy.stats import gaussian_kde
kde_T1 = gaussian_kde(Y_T1[:, :2].T)
kde_T2 = gaussian_kde(Y_T2[:, :2].T)
density_shift = kde_T2(grid) - kde_T1(grid)
plt.contourf(XX, YY, density_shift, cmap='RdBu_r')
```

---

### 3.10 Static Spatial Envelope Visualization (NB10)

**Concept:** Percentile ellipses in PC1×PC2 space per session (25th, 50th, 75th, 95th percentile contours). Visualizes the *size and shape* of the movement envelope. Sessions with larger envelopes = more diverse movement; shifted envelopes = different typical posture.

**NB10 function:** `plot_static_spatial_envelope(pca_results)` — produces per-session envelope overlaid for comparison.

---

### 3.11 Complexity Triptych (NB10)

**Concept:** A three-panel figure summarizing the three complexity axes:
1. **Scree plot** (PC variance distribution per session)
2. **3D trajectory** in PC1×PC2×PC3 space (time-colored)
3. **State space entropy** bar comparison across sessions

**NB10 function:** `plot_complexity_triptych(pca_results, prepared, stats_results)`

---

### 3.12 Anatomical Contribution Index (NB10 Phase 4)

**Concept:** For each joint, sum its squared PCA loadings across PC1, PC2, PC3, then normalize to 100%. Identifies "Top 5 joints" driving variance in the Dynamics and Pose branches.

**Formula:**
```
ACI_j = (Σ_{k=1}^{3} w_{k,j}²) / (Σ_j Σ_{k=1}^{3} w_{k,j}²)  × 100%
```

**NB10 function:** `calculate_joint_loadings(pca_results)` → top-5 contributor table per branch.

**Longitudinal shift version:** `calculate_session_joint_loadings(pca_results, prepared)` + `longitudinal_joint_shift_table(session_loadings, top_n=10)` — shows whether the dominant joints shift from T1 to T3.

---

## Part 4 — Visualization Inventory (High-Value Plots to Recreate)

| Plot | Source | Description | Recreate with |
|---|---|---|---|
| ATF heatmap | NB09 | Joints × time windows; color = ATF | `seaborn.heatmap` or `plt.imshow` |
| Longitudinal line chart | NB09 | ATF/TM/D_eff/Gini over T1→T2→T3 | `px.line` (Plotly) or `plt.plot` |
| Cross-subject trajectory | NB09 | PC1–PC2 scatter with T1→T3 arrows per subject | `plt.quiver` / `px.scatter` |
| PSD with SavGol cutoff | NB07 | Welch PSD + noise floor + f_eff dashed line | `plt.semilogy` |
| Windowed velocity audit | NB07 | v_m time series + detected peaks + V floor | `plt.plot` + `plt.scatter` on peaks |
| 3D convex hull | NB10 | PC1×PC2×PC3 hull overlay per session | `mpl_toolkits.mplot3d` + ConvexHull |
| Density shift matrix | NB10 | KDE difference per session pair | `plt.contourf` + `RdBu_r` |
| Static spatial envelope | NB10 | Percentile contours per session in PC space | `matplotlib.patches.Ellipse` |
| Complexity triptych | NB10 | Scree + 3D trajectory + entropy bar | `plt.subplot` 3-panel |
| Anatomical loading bar | NB10 | Top 5 joint contributors per branch | `plt.barh` |
| Longitudinal joint shift table | NB10 | Rank change of top-10 joints T1→T3 | `pd.DataFrame.style` |

---

## Part 5 — Key Parameters and Thresholds to Preserve

| Parameter | Value | Source | Used for |
|---|---|---|---|
| `noise_floor_guard_mms` | 1.0 mm/s | pulsicity.py | ATF and PPM noise floor minimum |
| `static_baseline_guard_mms` | 50.0 mm/s | v2_feature_engine.py | Reject reference window if > 50 mm/s mean |
| `min_run_seconds` | 5.0 s | pulsicity.py | valid_movement_flag threshold |
| `prominence_multiplier` | 0.5 × σ_v | pulsicity.py | Adaptive PPM peak detection |
| `amplitude_threshold` (SPARC) | 0.05 | pulsicity.py | Trim SPARC integration range |
| SPARC f_cap | SavGol 99% cutoff | pulsicity.py | Prevents filter artifact inflation |
| `n_bins` (entropy) | 25 | NB10 | State space entropy discretization |
| SampEn `m`, `r_factor` | 2, 0.2 | NB10 | SampEn template length and tolerance |
| `trim_pct` (robust hull) | 5% | NB10 | Outlier-robust 3D hull volume |
| PCA n_components | 19 | v2_feature_engine.py | Dynamics branch (1 per joint) |
| `epsilon_deff` | 1e-12 | v2_feature_engine.py | Numerical stability in participation ratio |
| ATF axial joints | Hips, Spine, Spine1, Neck, Head | v2_feature_engine.py | Joint group for ATF_axial |
| ATF peripheral joints | LeftForeArm, LeftHand, RightForeArm, RightHand, LeftFoot, RightFoot | v2_feature_engine.py | Joint group for ATF_peripheral |
| TM endpoints | LeftHand, RightHand, LeftFoot, RightFoot | v2_feature_engine.py | Total movement path length |
| Session-native Gini | mean-centered, NOT standardized | v2_feature_engine.py | Avoid Gini=0 collapse with StandardScaler |
| Noise band (PSD) | 15–50 Hz | pulsicity.py | Noise ratio for secondary filter recommendation |
| Signal band (PSD) | 0.5–10 Hz | pulsicity.py | Dance movement frequency content |

---

## Part 6 — Files to Archive (not delete)

The following notebooks contain the implementations referenced above and should be moved to `legacy/` (not deleted):

| File | Status | What to preserve |
|---|---|---|
| `notebooks/07_pulsicity_flow.ipynb` | Archive | Full NB07 logic; interactive widgets (NB07 Sections 2–5) |
| `notebooks/09_Subject_Exploration_Dashboard.ipynb` | Archive | ATF heatmap, longitudinal summary, cross-subject trajectory |
| `notebooks/10_EDA_PCA.ipynb` | Archive | 3-branch PCA, all complexity metrics, all visualizations |
| `src/pulsicity.py` | **KEEP ACTIVE** — used by NB07 and v2_feature_engine.py | Core backend |
| `src/v2_feature_engine.py` | **KEEP ACTIVE** — implements F1–F5 | Core backend for thesis features |
| `src/utils_nb07.py` | Archive candidate | Engineering profile schema (valuable reference) |
