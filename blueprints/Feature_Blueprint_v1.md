# Master Feature Blueprint
**Domain:** Measuring creativity and motor learning during Gaga dance and psilocybin interventions.
**Generated:** 2026-04-02T14:09:05.547742

## Committee quote audit (post-check vs full source document)

_All committee quotes verified against the full extracted source text (`audit_committee_quotes` in `pipeline_core.py`: substring check after whitespace normalization)._

### Cross-check vs `verified_extractions.json`

Each `committee_verbatim_quote` was compared to `raw_quote` for the same paper. Paper ids were matched with Unicode NFC normalization (the blueprint uses the same filename form as `papers/` for Sánchez—NFD for “á”—while `verified_extractions.json` may store NFC; quotes are unchanged).

| Feature | Match to stored `raw_quote` |
| --- | --- |
| Narrative_vs_visual_endpoint_amplitude_delta | Exact (MATH; line breaks preserved, e.g. after `92,` and `measur-`) |
| Narrative_vs_visual_endpoint_path_length_delta | Exact (same MATH `raw_quote`) |
| Narrative_vs_visual_posterior_stability_risk_proxy | Exact (same MATH `raw_quote`) |
| Narrative_imagery_movement_energy_proxy | Exact (THEORY; line breaks preserved) |
| Constraint_driven_exploration_breadth_attractor_transitions | Exact |
| Intensity_inequality_index_endpoint_and_trunk_speed | Exact |

**Discrepancies:** None. All six `committee_verbatim_quote` strings match character-for-character a `raw_quote` in `verified_extractions.json` for the corresponding paper.

## Do not compute (schema feasibility + strategist drops)

| Metric / idea | Grounded in | Reason |
| --- | --- | --- |
| Broken-ergodicity persistence index from dynamic-overlap surrogate | strategist_drop | Only one verified raw_quote exists for Creativityinsportanddance.docx (exploration requisite for creative behaviour); it does not anchor the paper-specific power-law overlap / broken-ergodicity implementation, so this mapping is not emitted under the verbatim committee-quote rule. |
| RQA Shannon entropy (ENTR) on hand translational speed for individual movement variability | strategist_drop | verified_extractions.json contains no ResearchExtraction for source_paper_id rqa_w_shEn.pdf; committee_verbatim_quote cannot be set to a verified raw_quote character-for-character. |
| RQA Shannon entropy (ENTR) on forearm angular speed (IMU-kinematic analog) | strategist_drop | Same as other rqa_w_shEn.pdf mappings: no verified extraction object in verified_extractions.json for that source_paper_id. |
| RQA Shannon entropy (ENTR) on single-axis hand root-relative position (task-aligned swing component) | strategist_drop | Same as other rqa_w_shEn.pdf mappings: no verified extraction object in verified_extractions.json for that source_paper_id. |
| Any EMG-based metric (for example muscle activation amplitude, median frequency) | schema_feasibility | Any EMG-based metric (for example muscle activation amplitude, median frequency) |
| Any force-plate or pressure metric (for example ground reaction force, COP, plantar pressure) | schema_feasibility | Any force-plate or pressure metric (for example ground reaction force, COP, plantar pressure) |
| Any metric requiring sampling above 120 Hz | schema_feasibility | Any metric requiring sampling above 120 Hz |
| Any metric requiring non-existent columns | schema_feasibility | Any metric requiring non-existent columns |

## Narrative_vs_visual_endpoint_amplitude_delta
**Plausibility:** 8/10
**Source paper:** `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf`
**Schema field(s):** `LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz,wbc_com_x,wbc_com_y,wbc_com_z`
**Derivation formula:** `A_t = ||p_lh,t - p_com,t|| + ||p_rh,t - p_com,t|| + ||p_lf,t - p_com,t|| + ||p_rf,t - p_com,t|| using root-relative hand/foot coordinates and wbc_com; A_condition = mean_t(A_t) within condition windows; delta_A = A_NR - A_VR.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf#027ae25dff099e5e` |
| verbatim_quote | cant differences were found in amplitude ( t23 = 2.73, p = 0.012), risk ( Wilcoxon, S = 92,
p = 0.0057), and total movement (Wilcoxon, S = 68, p = 0.0497), indicating significant measur-
able effects of the condition on postural parameters (Table 2, Figure 2). |
| mechanism (one sentence) | Significant NR–VR differences in summed limb-to-COG amplitude motivate a comparable endpoint-and-COM amplitude contrast when imagery or instruction type differs within our study. |

### Segment / trial inclusion

Compute only on contiguous windows where trial_type or instruction encodes narrative-like versus visual-like imagery (or pre-registered Gaga vs free blocks); minimum length per schema nonlinear rules; stratify by session, placebo vs psilocybin, and quality flags.

### Academic justification
The source study paired narrative versus visual mental imagery during dance and found larger summed limb-to-centre-of-gravity amplitude under narrative imagery; mapping the same contrast onto OptiTrack root-relative endpoints and whole-body COM tests whether instruction-linked imagery shifts scale of motion in Gaga-style improvisation versus structured segments.

### Implementation logic
Segment trials by VR vs NR (or your Gaga vs free labels); compute A_t per frame from schema columns; aggregate mean A per condition per session; take within-subject delta. Report alongside speed and missing-data rates because amplitude confounds with tempo and tracking gaps.

### Domain shift risk analysis
Sánchez Martz et al. used inertial estimates of limb and COM positions in centimetres; we use rigid-body pelvis-rooted kinematics without EMG or force plates. Task was controlled imagery-dance trials with professional dancers, not open Gaga with psilocybin—interpret deltas as analogy, not replication.

---
## Narrative_vs_visual_endpoint_path_length_delta
**Plausibility:** 8/10
**Source paper:** `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf`
**Schema field(s):** `LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz`
**Derivation formula:** `TM = sum_{t=2..n}(||p_lh,t - p_lh,t-1|| + ||p_rh,t - p_rh,t-1|| + ||p_lf,t - p_lf,t-1|| + ||p_rf,t - p_rf,t-1||); TM_condition computed per condition window; delta_TM = TM_NR - TM_VR.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf#027ae25dff099e5e` |
| verbatim_quote | cant differences were found in amplitude ( t23 = 2.73, p = 0.012), risk ( Wilcoxon, S = 92,
p = 0.0057), and total movement (Wilcoxon, S = 68, p = 0.0497), indicating significant measur-
able effects of the condition on postural parameters (Table 2, Figure 2). |
| mechanism (one sentence) | The same statistical result bundle (amplitude, risk, total movement) supports tracking NR–VR change in cumulative endpoint path length as a movement-quantity analog. |

### Segment / trial inclusion

Same condition labels as amplitude feature; require full segment coverage for TM integration; document if music or instruction duration differs across conditions.

### Academic justification
The paper reports larger total movement (sum of endpoint displacements) under narrative imagery; the same construction from hand and foot root-relative trajectories proxies overall movement quantity for within-subject comparisons when conditions are defined in metadata.

### Implementation logic
Sum Euclidean step lengths per endpoint for each condition window; delta within subject. Align time base at 120 Hz; exclude gaps with NaNs or drop segments below minimum length per pipeline policy.

### Domain shift risk analysis
Source used four endpoints and inertial kinematics; we use OptiTrack solve. Total path length scales with duration—normalize by segment duration when comparing blocks of unequal length.

---
## Narrative_vs_visual_posterior_stability_risk_proxy
**Plausibility:** 6/10
**Source paper:** `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf`
**Schema field(s):** `wbc_com_x,wbc_com_y,wbc_com_z,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz`
**Derivation formula:** `p_midfeet,t = 0.5*(p_lf,t + p_rf,t); p_com_proj,t = [wbc_com_x,wbc_com_z]; p_midfeet_proj,t = [midfeet_x,midfeet_z]; R_proxy,t = ||p_com_proj,t - p_midfeet_proj,t||; R_proxy_condition = mean_t(R_proxy,t); delta_R = R_proxy_NR - R_proxy_VR. Note: posterior-base reference is approximated by midpoint due missing explicit support-polygon landmarks.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf#027ae25dff099e5e` |
| verbatim_quote | cant differences were found in amplitude ( t23 = 2.73, p = 0.012), risk ( Wilcoxon, S = 92,
p = 0.0057), and total movement (Wilcoxon, S = 68, p = 0.0497), indicating significant measur-
able effects of the condition on postural parameters (Table 2, Figure 2). |
| mechanism (one sentence) | Reported NR–VR increases in risk-related postural statistics motivate a coarse stability proxy when only marker-based COM and feet are available. |

### Segment / trial inclusion

Prefer segments with both feet tracked; exclude large jumps or crawling if they violate standing-dance assumptions underlying the paper's risk construct.

### Academic justification
The paper found higher risk (COP–posterior base-of-support distance) under narrative imagery; the proxy uses COM-to-midfeet horizontal distance in the mocap frame as a feasibility-aligned stand-in without force-plate COP.

### Implementation logic
Project COM and bilateral foot midpoints to floor plane (x,z); compute mean R_proxy per condition; within-subject delta. Flag marginal validity when feet tracking is poor or during single-support phases.

### Domain shift risk analysis
True COP and PBF are not in the schema; proxy is MARGINAL and confounded by model COM vs true COP and by foot placement. Use as exploratory stratifier, not as clinical balance metric.

### Defensible claim, discrepancies, and recommendations (Gaga + your data)

**Defensible claim.** You can treat this feature as a **kinematic description of how whole-body mass (via model-based CoM) is carried relative to a foot-based reference on the floor plane**—i.e. **support–mass geometry** or **CoM excursion relative to base-of-support cues**—within Gaga (and condition) segments. That supports questions about **postural exploration**, **shifts of mass over the feet**, and **edge-of-support** behaviour without asserting replication of Sánchez et al.’s published **R** value or their inertial fusion pipeline.

**Discrepancies vs their R statistic (why 6/10 stays appropriate).**

| Area | Their paper (as extracted) | This blueprint |
| --- | --- | --- |
| “COP” in R | Described as **CoM projected to the ground** in the verified extraction; estimated via **their** inertial setup (cm). | **`wbc_com_*`** from **OptiTrack / IK**—same *idea* (mass trajectory → floor), **different estimator** and filtering. |
| Posterior base of support | **Midpoint between feet** in the extraction. | Same **heuristic** (mid-feet from foot positions)—**coarse** if the narrative is “posterior” risk; **not** heel or support polygon unless you add it. |
| Task | Controlled **imagery–dance** trials. | **Gaga / your protocol**—different movement ensemble. |
| Force-based COP | Not required **for the extracted formula** if it is truly CoM-on-floor vs feet. | You still **must not** overclaim **pressure-based COP** unless you add force/insole data. |

**Recommendations.**

1. **Name the construct in writing** (e.g. “CoM–foot-reference distance on the floor plane,” “support–mass proxy”) when interpreting results; cite Sánchez as **inspiration** for a **postural-challenge** reading, not as **numerical replication** of **R**.
2. **Use leg-plate / foot markers** (if available in your raw pipeline) to **fix the foot reference**: e.g. **bilateral heel midpoint**, **ankle midpoint**, or **plate centroid**—and run **sensitivity** vs simple mid-feet to show robustness.
3. **Pre-specify inclusion**: prefer **double-support** windows where the geometric story holds; flag or exclude **single-support / flight** where the scalar is hard to defend.
4. **Gaga alignment**: frame **hypotheses** in terms of **willingness to carry mass toward/away from support** or **explore off-vertical strategy**—consistent with pedagogy—while keeping **claims** at the level of **observed kinematics**.

Keeping **plausibility at 6** remains honest: **transport** from their operationalisation is **partial**; the **value** is in a **clear, labelled** kinematic analogue plus the steps above.

---
## Narrative_imagery_movement_energy_proxy
**Plausibility:** 7/10
**Source paper:** `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf`
**Schema field(s):** `LeftHand__lin_vel_rel_mag,RightHand__lin_vel_rel_mag,LeftFoot__lin_vel_rel_mag,RightFoot__lin_vel_rel_mag,LeftHand__lin_acc_rel_mag,RightHand__lin_acc_rel_mag,LeftFoot__lin_acc_rel_mag,RightFoot__lin_acc_rel_mag`
**Derivation formula:** `MovementEnergy_condition = mean_t(sum(endpoint_lin_vel_rel_mag^2)) + lambda*mean_t(sum(endpoint_lin_acc_rel_mag^2)); compare NR vs VR using within-subject delta per session/segment.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf#e5d300c3a9e684d3` |
| verbatim_quote | Accordingly, the primary
purpose of the study was to assess the effects of these distinct mental representations on
amplitude, risk-taking behavior, and overall movement quantity, using inertial sensor data
as an objective measure of postural and kinematic change. |
| mechanism (one sentence) | The authors explicitly tied distinct mental representations to amplitude, risk-taking, and movement quantity—motivating a scalar movement-energy-style summary from endpoint kinematics under the same contrast logic. |

### Segment / trial inclusion

Apply when trial metadata supports representation-type or instruction contrasts; otherwise do not claim mapping to Sanchez's NR/VR operationalisation.

### Academic justification
The verified theory extraction states the study targeted effects of mental representation type on amplitude, risk-taking, and overall movement quantity; a quadratic energy-style summary of endpoint speeds and accelerations links that hypothesis to continuous kinematic intensity in our schema.

### Implementation logic
Choose lambda from scale matching or pre-registration; compute per condition; control for segment duration and mean speed. Optional sensitivity without acceleration term.

### Domain shift risk analysis
Energy proxy is not identical to inertial movement quantity in the paper; accelerations from mocap are model-smoothed. Narrative/visual conditions in our study may not mirror Sanchez episodic imagery tasks.

---
## Constraint_driven_exploration_breadth_attractor_transitions
**Plausibility:** 6/10
**Source paper:** `Creativityinsportanddance.docx`
**Schema field(s):** `Hips__zeroed_rel_rotvec_x,Hips__zeroed_rel_rotvec_y,Hips__zeroed_rel_rotvec_z,Spine__zeroed_rel_rotvec_x,Spine__zeroed_rel_rotvec_y,Spine__zeroed_rel_rotvec_z,Spine1__zeroed_rel_rotvec_x,Spine1__zeroed_rel_rotvec_y,Spine1__zeroed_rel_rotvec_z,LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz`
**Derivation formula:** `Build state vector x_t from selected trunk rotvec + endpoint positions; cluster x_t into K metastable states; ExplorationBreadth = (# unique visited states / K) and TransitionRate = count(state_t != state_t-1)/duration_s; higher values indicate broader exploration dynamics.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `Creativityinsportanddance.docx#76c7996cfd96a6b8` |
| verbatim_quote | This modeling shows how exploration is a requisite of creative behaviour, i.e. inventing novel or innovating extant movement forms and actions with respect to the extant socio-cultural milieu (for details see Hristovski et al., 2011). |
| mechanism (one sentence) | The committee-quoted claim that exploration is requisite for creative behaviour aligns with measuring how often and how broadly the system leaves discrete metastable states built from trunk and hand configuration. |

### Segment / trial inclusion

Use long enough segments for stable clustering (per schema minima); separate structured Gaga from free improvisation when labels exist; avoid comparing segments with vastly different duration without normalization.

### Academic justification
Ecological-dynamics accounts cast creative movement as exploration across metastable attractors; clustering reconstructed posture-endpoint vectors yields discrete-state occupancy and transition rates comparable in spirit to hopping between basins under soft-assembled constraints.

### Implementation logic
Pre-specify K, clustering method, and window length; compute per Gaga or free segment; stratify placebo vs psilocybin; report sensitivity to K and to trunk versus hand weighting.

### Domain shift risk analysis
The paper's empirical analyses used different observables (e.g. configuration vectors from their recording); our clustering is a heuristic on OptiTrack streams—interpret as exploratory texture, not identification of true attractors.

---
## Intensity_inequality_index_endpoint_and_trunk_speed
**Plausibility:** 6/10
**Source paper:** `A New Metric for Integrative Analysis of Movement.txt`
**Schema field(s):** `LeftHand__lin_vel_rel_mag,RightHand__lin_vel_rel_mag,LeftFoot__lin_vel_rel_mag,RightFoot__lin_vel_rel_mag,Hips__zeroed_rel_omega_mag,Spine__zeroed_rel_omega_mag`
**Derivation formula:** `Ineq = Gini({I_t}); I_t = weighted_sum(endpoint linear-speed magnitudes and trunk angular-speed magnitudes) per frame; compute Lorenz curve of cumulative time vs cumulative intensity and return Gini coefficient; aggregate by segment/session for group comparisons.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `A New Metric for Integrative Analysis of Movement.txt#f0fad5d4cc5d2787` |
| verbatim_quote | When differentiating between groups, I≠ halved the sample size required for a statistical power of 80% at α = .05, in comparison to the alternative metrics of intensity gradient or log ratio of minutes at low and moderate to high intensity. |
| mechanism (one sentence) | The cited inequality metric's advantage in group discrimination motivates summarizing how unevenly movement intensity is distributed in time within Gaga or free blocks. |

### Segment / trial inclusion

Aggregate within pre-defined session or trial windows; require sufficient frames for stable Gini; pair with segment duration and mean intensity as controls.

### Academic justification
I≠ summarizes inequality of time spent across intensity levels; the verified quote supports its discriminative utility versus other intensity summaries—here instantiated on mocap-derived speed magnitudes for Gaga sessions rather than 24-hour accelerometer traces.

### Implementation logic
Build per-frame intensity I_t from schema; sort time spent; compute Gini on the empirical distribution; one value per segment or session per pre-analysis plan.

### Domain shift risk analysis
Original work used child cohorts and wearable acceleration over days; we use laboratory mocap at high rate over minutes—claim ceiling is distributional structure of intensity within segment, not clinical PA classification.

---
