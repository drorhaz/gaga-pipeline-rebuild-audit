# Master Feature Blueprint
**Domain:** Measuring creativity and motor learning during Gaga dance and psilocybin interventions.
**Generated:** 2026-03-30T20:35:17.173072

## Committee quote audit (post-check vs full source document)

_All committee quotes verified against the full extracted source text._

## Do not compute (schema feasibility + strategist drops)

_None recorded._

## RQA_ENTR_LeftHand_lin_speed_Gaga_psilocybin_variability
**Plausibility:** 8/10
**Source paper:** `rqa_w_shEn.pdf`
**Schema field(s):** `LeftHand__lin_vel_rel_mag`
**Derivation formula:** `ENTR = RQA_Shannon_entropy(diagonal_line_length_distribution(RP(Y_t, epsilon=1))); Y_t = UTDE(s, m=m0=6, tau=tau0=8) with Y_t = [s(t), s(t-8), ..., s(t-40)] in samples; s(t) = LeftHand__lin_vel_rel_mag at time_s (mm/s, SavGol derivative of root-relative LeftHand__lin_rel_px, LeftHand__lin_rel_py, LeftHand__lin_rel_pz vs pelvis); epsilon=1 is the recurrence threshold in embedded-distance units as in the paper (not mm). Requires contiguous segment length >= 100 samples (~0.83 s at 120 Hz). Mirror with RightHand__lin_vel_rel_mag if analyzing the contralateral limb.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `rqa_w_shEn.pdf#b353d6ec6822353a` |
| verbatim_quote | We conclude that Shannon Entropy with RQA is a robust method that helps to quantify activities, types
of sensors, windows lengths and level of smoothness. |
| mechanism (one sentence) | Shannon entropy of RQA diagonal-line length distributions summarizes how recurrence structure varies across operational choices, motivating ENTR as a variability-sensitive descriptor when we apply the same nonlinear reconstruction to Gaga hand-speed trajectories from motion capture. |

### Segment / trial inclusion

Compute on within-session contiguous Gaga movement segments ≥100 samples at 120 Hz after NaN-safe chunking; carry session identifiers (`run_id`, `subject_id`) and intervention labels (placebo vs psilocybin) from your study registry, and restrict to frames passing quality flags so ENTR is not dominated by tracking gaps; if no trial column exists yet, use full cleaned continuous recordings per session and document that phase stratification is a limitation.

### Academic justification
The source study used wrist-mounted inertial streams during repetitive horizontal versus vertical imitation at controlled tempos; your protocol instead probes exploratory, non-linear Gaga phrase-work where hands carry much of the task’s spatial invention and where psilocybin may broaden the effective motor search space. Shannon entropy of diagonal-line lengths in recurrence quantification (RQA ENTR) summarizes how richly the hand-speed trajectory revisits nearby regions of reconstructed state space—higher ENTR aligns with more heterogeneous recurrence microstructure, which the cited work argues is especially informative for individual differences in movement variability when recurrence thresholds and smoothing are varied. For Gaga creativity and motor learning, hand translational speed magnitude is a natural scalar summary of how vigorously and irregularly the distal chain explores volume around the root, so ENTR on this channel tests whether between-person differences in ‘movement texture’ under placebo versus psilocybin parallel the paper’s claim that ENTR is robust across sensor and analysis choices—here instantiated as OptiTrack-derived speed rather than wrist IMU.

### Implementation logic
For each subject and session, slice the master kinematics Parquet to continuous runs where `time_s` is strictly increasing and artifact or NaN guards (per `nan_guard_status` / chunking policy) allow Savitzky–Golay derivatives already baked into `LeftHand__lin_vel_rel_mag`. Within each included Gaga task block (define blocks from your trial table or event markers; keep placebo and psilocybin days as separate strata), extract segments of at least 100 samples; drop shorter gaps. On s(t) = `LeftHand__lin_vel_rel_mag`, build UTDE with m=6, τ=8 samples, compute the recurrence plot in embedded space with ε=1 in distance units as in the paper’s Figure 5 setting, then compute ENTR from the diagonal-line length histogram (e.g., nonlinearTseries or equivalent). Log segment_id, drug condition, and replicate with `RightHand__lin_vel_rel_mag` for symmetry or handedness contrasts. Sensitivity analysis: optional ε grid {1,2,3} and window-length sweeps echo the paper’s robustness narrative without claiming replication of their exact HS01/RS01 numeric contrasts.

### Domain shift risk analysis
The paper contrasted human versus robot performers on stereotyped swing tasks; Gaga under psilocybin emphasizes sensory imagery, non-periodic phrasing, and whole-body coupling, so ENTR on hand speed indexes distributional complexity of one distal channel—not a full model of ‘creativity.’ IMU wrist data mixes orientation and linear acceleration in a sensor-fixed frame, whereas `lin_vel_rel_mag` is a pelvis-rooted kinematic speed from marker-based solve; translation is strong for gross hand exploration but misses high-frequency IMU-specific components and soft-tissue artifact tradeoffs that differ from OptiTrack dropouts.

---
## RQA_ENTR_LeftForeArm_omega_mag_Gaga_psilocybin_variability
**Plausibility:** 6/10
**Source paper:** `rqa_w_shEn.pdf`
**Schema field(s):** `LeftForeArm__zeroed_rel_omega_mag`
**Derivation formula:** `ENTR = RQA_Shannon_entropy(diagonal_line_length_distribution(RP(Y_t, epsilon=1))); Y_t = UTDE(s, m=m0=6, tau=tau0=8) with Y_t = [s(t), s(t-8), ..., s(t-40)] in samples; s(t) = LeftForeArm__zeroed_rel_omega_mag at time_s (deg/s, quaternion-log angular velocity magnitude in zeroed child-body frame); epsilon=1 as in the paper in embedded-distance units. Requires contiguous segment length >= 100 samples. Domain shift: paper used wrist IMU scalar channels; this uses rigid-body joint omega from OptiTrack solve—not raw marker XYZ. Mirror with RightForeArm__zeroed_rel_omega_mag if needed.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `rqa_w_shEn.pdf#b353d6ec6822353a` |
| verbatim_quote | We conclude that Shannon Entropy with RQA is a robust method that helps to quantify activities, types
of sensors, windows lengths and level of smoothness. |
| mechanism (one sentence) | Because Shannon RQA entropy tracks how sensitive recurrence-based variability is to sensor stream and preprocessing choices, it offers a principled way to quantify rotational-speed recurrence texture for forearm Gaga motion captured optically rather than inertially. |

### Segment / trial inclusion

Same inclusion as hand-speed ENTR: contiguous Gaga segments ≥100 samples, per-session placebo/psilocybin stratification, quality-flagged frames only; prefer blocks labeled as active Gaga instruction versus standing rest when your event file provides those codes, otherwise note mixing of micro-rests as noise in ENTR.

### Academic justification
Gaga coaching often manipulates rotation quality (‘bones soft, flesh heavy’) and multi-joint waves that change how the forearm rolls independently of the hand path; psilocybin may amplify exploratory rotation or, conversely, produce sticky postural attractors that show up as altered temporal structure in angular speed. The verified extraction highlights ENTR as the RQA measure most aligned with individual differences in movement variability under varying smoothness and recurrence thresholds. Mapping ENTR to `LeftForeArm__zeroed_rel_omega_mag` tests whether rotational variability in the T-pose-normalized child frame carries individual signatures analogous to the paper’s wrist IMU scalars, while speaking directly to Gaga-relevant articulation strategies that are invisible if one only tracks hand translation.

### Implementation logic
Mirror the hand-speed pipeline but set s(t) = `LeftForeArm__zeroed_rel_omega_mag` (deg/s magnitude from zeroed relative quaternion kinematics). Use identical UTDE (m=6, τ=8), ε=1, and minimum 100-sample segments. Because feasibility is MARGINAL, pre-register a comparison against `LeftHand__lin_vel_rel_mag` ENTR to see whether rotation versus translation channels diverge under drug—consistent with Gaga’s emphasis on twisting versus reaching. Apply the same session/block filters and duplicate for `RightForeArm__zeroed_rel_omega_mag` when testing lateralization.

### Domain shift risk analysis
Wrist IMU scalar series in the paper are not the same physical observable as a model-based forearm angular-speed magnitude: the IMU blends gravitational and rotational components in a sensor frame, while OptiTrack ω comes from a rigid-body inverse kinematics chain with its own smoothing and T-pose zeroing. Complex Gaga motion may violate the stationarity assumptions implicit in fixed delay embedding more often than repetitive swings, so ENTR should be interpreted as a phenomenological texture measure rather than a literal replication of the published human–robot separation.

---
## RQA_ENTR_LeftHand_vertical_component_task_aligned_Gaga
**Plausibility:** 5/10
**Source paper:** `rqa_w_shEn.pdf`
**Schema field(s):** `LeftHand__lin_rel_py`
**Derivation formula:** `ENTR = RQA_Shannon_entropy(diagonal_line_length_distribution(RP(Y_t, epsilon=1))); Y_t = UTDE(s, m=m0=6, tau=tau0=8); s(t) = LeftHand__lin_rel_py (mm, root-relative Y in OptiTrack Y-up frame). Choose LeftHand__lin_rel_px or LeftHand__lin_rel_pz instead when the choreography emphasizes horizontal sagittal/frontal swing rather than vertical; epsilon=1 per paper in embedded space. Segment >= 100 samples.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `rqa_w_shEn.pdf#b353d6ec6822353a` |
| verbatim_quote | We conclude that Shannon Entropy with RQA is a robust method that helps to quantify activities, types
of sensors, windows lengths and level of smoothness. |
| mechanism (one sentence) | Shannon RQA entropy’s robustness across windows, smoothness, and sensor contexts supports using it on a vertically aligned hand position stream to capture orientation-tagged variability in Gaga, analogous to the paper’s horizontal-versus-vertical movement contrasts. |

### Segment / trial inclusion

Apply to Gaga segments ≥100 samples with the same session and drug stratification; when instructional blocks specify vertical quality, restrict ENTR computation to those labeled intervals to reduce mixing with horizontal-dominant phrases; if labels are absent, report ENTR on full-session streams as exploratory and acknowledge confounding with multi-planar movement.

### Academic justification
The original work explicitly contrasted horizontal versus vertical arm swings, showing that several RQA summaries depend on movement orientation and tempo. Gaga classes frequently alternate vertical ‘lifting’ qualities with sagittal and frontal scanning; a single root-relative axis (`lin_rel_py` as vertical in your Y-up lab frame) therefore functions as a task-aligned scalar analogous to the paper’s orientation-dependent analyses, while remaining sensitive to Gaga’s non-periodic phrasing. ENTR on this coordinate probes whether psilocybin alters how richly vertical hand paths recur in embedded space—potentially reflecting changed spatial risk-taking or ‘floating’ quality—while staying tied to the committee’s conclusion that Shannon entropy with RQA tolerates comparing streams defined in different operational regimes when threshold and window choices are tracked.

### Implementation logic
Use s(t) = `LeftHand__lin_rel_py` without additional differentiation unless you add a derivative feature; apply UTDE m=6, τ=8, ε=1, ENTR on ≥100-sample contiguous segments. For sessions emphasizing lateral or sagittal exploration, compute sibling features on `LeftHand__lin_rel_px` or `LeftHand__lin_rel_pz` using the same recipe and align interpretation with that session’s coach cues. Document axis choice per segment to preserve the paper’s spirit of orientation-specific comparisons in a Gaga context where orientation is choreographic rather than metronome-driven.

### Domain shift risk analysis
A single position axis omits coupling with other coordinates and with orientation, so it is a deliberate projection of full-hand state; repetitive swing tasks in the paper enforced quasi-1D structure, whereas Gaga’s vertical motion is embedded in rich 3D phrases, making ENTR more sensitive to projection artifacts and to pelvis-rooting choices than the wrist-speed channel. IMU-to-OptiTrack translation is weaker here than for velocity magnitude because scalar position depends on global scaling and T-pose reference, not just local inertial dynamics.

---
