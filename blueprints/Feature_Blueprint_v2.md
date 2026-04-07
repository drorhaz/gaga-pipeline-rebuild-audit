# Master Feature Blueprint
**Domain:** Measuring creativity and motor learning during Gaga dance and psilocybin interventions.
**Generated:** 2026-04-06T19:28:56.319241

## Committee quote audit (`committee_verbatim_quote` vs `verified_extractions.json` `raw_quote`)

Each `ProductFeature.committee_verbatim_quote` was compared **character-for-character** to every `raw_quote` sharing the same `source_paper_id` in `pipeline_artifacts/verified_extractions.json`. A feature passes if it equals at least one such `raw_quote` (papers may have multiple verified rows, e.g. MATH and THEORY).

| Feature | Source paper | Exact match to verified `raw_quote` |
| --- | --- | --- |
| Intensity inequality index (I≠) on OptiTrack-derived intensity | `A New Metric for Integrative Analysis of Movement.txt` | yes |
| Ecological-dynamics framing: exploration as requisite for creative behaviour | `Creativityinsportanddance.docx` | yes |
| Exploratory breadth Q from discretized whole-body configuration | `Creativityinsportanddance.docx` | yes |
| Successive-configuration Hamming distance (barrier-height proxy) | `Creativityinsportanddance.docx` | yes |
| Average dynamic overlap <qd(τ)> of binary configurations | `Creativityinsportanddance.docx` | yes |
| Hierarchical PCA (hPCA) on configuration vectors | `Creativityinsportanddance.docx` | yes |
| Endpoint amplitude A (limb-to-COM distance sum) | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf` | yes |
| Total movement TM (summed endpoint path lengths) | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf` | yes |
| Postural risk R (COM vs mid-feet proxy) | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf` | yes |
| Mental-representation contrast (narrative- vs visual-episodic) for motor outcomes | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf` | yes |
| RQA Shannon entropy ENTR on forearm angular-speed embedding | `rqa_w_shEn.pdf` | yes |
| JcvPCA: joint contribution variation vs reference PCs | `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf` | yes |
| JsvCRP: Hips–Spine continuous relative-phase area vs reference | `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf` | yes |
| JsvCRP: LeftArm–LeftForeArm continuous relative-phase area vs reference | `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf` | yes |
| JsvCRP: RightArm–RightForeArm continuous relative-phase area vs reference | `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf` | yes |

**Discrepancies:** none (15/15 exact matches).

## Committee quote audit (supplementary: normalized substring vs full `papers/` text)

Same check as `audit_committee_quotes` in `pipeline_core.py` (whitespace-collapsed substring in the on-disk paper text loaded by `load_papers()`). The repository currently exposes only a subset of source files under `papers/`, so some titles cannot be located; the RQA row also fails this automated substring test against the extracted PDF text (the verified `raw_quote` may synthesize wording not present verbatim in the extraction).

| Feature | Source paper | Issue |
| --- | --- | --- |
| Endpoint amplitude A (limb-to-COM distance sum) | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf` | no_matching_paper_file_in_papers_folder |
| Total movement TM (summed endpoint path lengths) | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf` | no_matching_paper_file_in_papers_folder |
| Postural risk R (COM vs mid-feet proxy) | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf` | no_matching_paper_file_in_papers_folder |
| Mental-representation contrast (narrative- vs visual-episodic) for motor outcomes | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf` | no_matching_paper_file_in_papers_folder |
| RQA Shannon entropy ENTR on forearm angular-speed embedding | `rqa_w_shEn.pdf` | committee_verbatim_quote_not_found_in_full_source_text |

## Do not compute (schema feasibility + strategist drops)

| Metric / idea | Grounded in | Reason |
| --- | --- | --- |
| Any EMG-based metric (for example muscle activation amplitude, median frequency) | schema_feasibility | Any EMG-based metric (for example muscle activation amplitude, median frequency) |
| Any force-plate or pressure metric (for example ground reaction force, COP, plantar pressure) | schema_feasibility | Any force-plate or pressure metric (for example ground reaction force, COP, plantar pressure) |
| Any metric requiring sampling above 120 Hz | schema_feasibility | Any metric requiring sampling above 120 Hz |
| Any metric requiring non-existent columns | schema_feasibility | Any metric requiring non-existent columns |

## Intensity inequality index (I≠) on OptiTrack-derived intensity
**Plausibility:** 6/10
**Source paper:** `A New Metric for Integrative Analysis of Movement.txt`
**Schema field(s):** `LeftHand__lin_vel_rel_mag,RightHand__lin_vel_rel_mag,LeftFoot__lin_vel_rel_mag,RightFoot__lin_vel_rel_mag,Hips__zeroed_rel_omega_mag,Spine__zeroed_rel_omega_mag,Spine1__zeroed_rel_omega_mag`
**Derivation formula:** `Define scalar intensity I_t per frame as a weighted sum or mean of listed endpoint linear-speed magnitudes and trunk angular-speed magnitudes (same weights within a study wave). Sort I_t, build cumulative time vs cumulative intensity (Lorenz construction on the empirical intensity histogram over the segment); I≠ = Gini coefficient of that curve (inequality of time spent across intensity levels). Compare sessions/segments/groups; domain shift: source used 24h wrist accelerometer traces; here I_t is derived from OptiTrack root-relative kinematics at 120 Hz, not raw accelerometer counts.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `A New Metric for Integrative Analysis of Movement.txt#f0fad5d4cc5d2787` |
| verbatim_quote | When differentiating between groups, I≠ halved the sample size required for a statistical power of 80% at α = .05, in comparison to the alternative metrics of intensity gradient or log ratio of minutes at low and moderate to high intensity. |
| mechanism (one sentence) | I≠ summarizes how unevenly movement time is spread across intensity levels, supporting integrative comparisons when the intensity axis is operationalized consistently. |

### Segment / trial inclusion

Apply to contiguous segments meeting minimum length for stable histograms (prespecified); stratify by Gaga vs free improvisation, session, and placebo vs psilocybin when labels exist; exclude gaps with missing markers.

### Academic justification
Evidence trace: The verified extraction ties I≠ to superior group discrimination and sample efficiency versus other intensity summaries; implementing the same Gini-on-cumulative-time construction on a mocap-derived intensity scalar transfers the inequality-of-effort interpretation while acknowledging sensor and timescale shift from 24 h accelerometry to short Gaga segments.

### Implementation logic
Per analyzed segment, compute I_t from prespecified schema columns, build the empirical intensity distribution, apply the Lorenz/Gini construction as in the source methodology, and export I≠ for contrasts (e.g. phase, drug, pre/post).

### Domain shift risk analysis
Wrist accelerometer counts vs rigid-body speeds; 24 h habitual activity vs minutes of studio capture; intensity definition must be frozen per wave and reported with speed/amplitude covariates.

---
## Ecological-dynamics framing: exploration as requisite for creative behaviour
**Plausibility:** 8/10
**Source paper:** `Creativityinsportanddance.docx`
**Schema field(s):** `time_s,Hips__zeroed_rel_rotvec_x,Hips__zeroed_rel_rotvec_y,Hips__zeroed_rel_rotvec_z,Spine__zeroed_rel_rotvec_x,Spine__zeroed_rel_rotvec_y,Spine__zeroed_rel_rotvec_z,Spine1__zeroed_rel_rotvec_x,Spine1__zeroed_rel_rotvec_y,Spine1__zeroed_rel_rotvec_z,Neck__zeroed_rel_rotvec_x,Neck__zeroed_rel_rotvec_y,Neck__zeroed_rel_rotvec_z,Head__zeroed_rel_rotvec_x,Head__zeroed_rel_rotvec_y,Head__zeroed_rel_rotvec_z,LeftShoulder__zeroed_rel_rotvec_x,LeftShoulder__zeroed_rel_rotvec_y,LeftShoulder__zeroed_rel_rotvec_z,LeftArm__zeroed_rel_rotvec_x,LeftArm__zeroed_rel_rotvec_y,LeftArm__zeroed_rel_rotvec_z,LeftForeArm__zeroed_rel_rotvec_x,LeftForeArm__zeroed_rel_rotvec_y,LeftForeArm__zeroed_rel_rotvec_z,LeftHand__zeroed_rel_rotvec_x,LeftHand__zeroed_rel_rotvec_y,LeftHand__zeroed_rel_rotvec_z,RightShoulder__zeroed_rel_rotvec_x,RightShoulder__zeroed_rel_rotvec_y,RightShoulder__zeroed_rel_rotvec_z,RightArm__zeroed_rel_rotvec_x,RightArm__zeroed_rel_rotvec_y,RightArm__zeroed_rel_rotvec_z,RightForeArm__zeroed_rel_rotvec_x,RightForeArm__zeroed_rel_rotvec_y,RightForeArm__zeroed_rel_rotvec_z,RightHand__zeroed_rel_rotvec_x,RightHand__zeroed_rel_rotvec_y,RightHand__zeroed_rel_rotvec_z,LeftUpLeg__zeroed_rel_rotvec_x,LeftUpLeg__zeroed_rel_rotvec_y,LeftUpLeg__zeroed_rel_rotvec_z,LeftLeg__zeroed_rel_rotvec_x,LeftLeg__zeroed_rel_rotvec_y,LeftLeg__zeroed_rel_rotvec_z,LeftFoot__zeroed_rel_rotvec_x,LeftFoot__zeroed_rel_rotvec_y,LeftFoot__zeroed_rel_rotvec_z,RightUpLeg__zeroed_rel_rotvec_x,RightUpLeg__zeroed_rel_rotvec_y,RightUpLeg__zeroed_rel_rotvec_z,RightLeg__zeroed_rel_rotvec_x,RightLeg__zeroed_rel_rotvec_y,RightLeg__zeroed_rel_rotvec_z,RightFoot__zeroed_rel_rotvec_x,RightFoot__zeroed_rel_rotvec_y,RightFoot__zeroed_rel_rotvec_z,LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz`
**Derivation formula:** `THEORY extraction ties metastable landscape dynamics to exploratory time-series structure; operational quantitative analogs are the sibling MATH rows (binary configuration, Hamming reconfigurations, <qd(τ)>, hPCA). Verbatim anchor quote in extraction: exploration as requisite for creative behaviour. Do not treat any single scalar as a global creativity score; combine with claim ceiling in study_framing_for_agents.md.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `Creativityinsportanddance.docx#76c7996cfd96a6b8` |
| verbatim_quote | This modeling shows how exploration is a requisite of creative behaviour, i.e. inventing novel or innovating extant movement forms and actions with respect to the extant socio-cultural milieu (for details see Hristovski et al., 2011). |
| mechanism (one sentence) | Exploration is framed as necessary for inventing or innovating movement forms within socio-cultural constraints, motivating multi-metric state-space analyses rather than one scalar creativity score. |

### Segment / trial inclusion

Applies at study-design level to all movement segments used for sibling metrics; segment by Gaga vs free and drug condition when available.

### Academic justification
Evidence trace: The committee quote states that exploration is requisite for creative behaviour; the same paper's quantitative case operationalizes exploration via configuration dynamics, so this feature is the interpretive bridge linking Gaga/psilocybin contrasts to those metrics without over-claiming a single creativity index.

### Implementation logic
Use this row to pre-register interpretation: report exploratory-family metrics (Q, Hamming, <qd>, hPCA) alongside task labels; no standalone numeric output beyond documenting which derived quantities instantiate exploration in a given analysis plan.

### Domain shift risk analysis
Source: contact improvisation with observational codes; here: full-body OptiTrack with different discretization; task match differs from Gaga/free labels—state explicitly in every comparison.

---
## Exploratory breadth Q from discretized whole-body configuration
**Plausibility:** 5/10
**Source paper:** `Creativityinsportanddance.docx`
**Schema field(s):** `Hips__zeroed_rel_rotvec_x,Hips__zeroed_rel_rotvec_y,Hips__zeroed_rel_rotvec_z,Spine__zeroed_rel_rotvec_x,Spine__zeroed_rel_rotvec_y,Spine__zeroed_rel_rotvec_z,Spine1__zeroed_rel_rotvec_x,Spine1__zeroed_rel_rotvec_y,Spine1__zeroed_rel_rotvec_z,Neck__zeroed_rel_rotvec_x,Neck__zeroed_rel_rotvec_y,Neck__zeroed_rel_rotvec_z,Head__zeroed_rel_rotvec_x,Head__zeroed_rel_rotvec_y,Head__zeroed_rel_rotvec_z,LeftShoulder__zeroed_rel_rotvec_x,LeftShoulder__zeroed_rel_rotvec_y,LeftShoulder__zeroed_rel_rotvec_z,LeftArm__zeroed_rel_rotvec_x,LeftArm__zeroed_rel_rotvec_y,LeftArm__zeroed_rel_rotvec_z,LeftForeArm__zeroed_rel_rotvec_x,LeftForeArm__zeroed_rel_rotvec_y,LeftForeArm__zeroed_rel_rotvec_z,LeftHand__zeroed_rel_rotvec_x,LeftHand__zeroed_rel_rotvec_y,LeftHand__zeroed_rel_rotvec_z,RightShoulder__zeroed_rel_rotvec_x,RightShoulder__zeroed_rel_rotvec_y,RightShoulder__zeroed_rel_rotvec_z,RightArm__zeroed_rel_rotvec_x,RightArm__zeroed_rel_rotvec_y,RightArm__zeroed_rel_rotvec_z,RightForeArm__zeroed_rel_rotvec_x,RightForeArm__zeroed_rel_rotvec_y,RightForeArm__zeroed_rel_rotvec_z,RightHand__zeroed_rel_rotvec_x,RightHand__zeroed_rel_rotvec_y,RightHand__zeroed_rel_rotvec_z,LeftUpLeg__zeroed_rel_rotvec_x,LeftUpLeg__zeroed_rel_rotvec_y,LeftUpLeg__zeroed_rel_rotvec_z,LeftLeg__zeroed_rel_rotvec_x,LeftLeg__zeroed_rel_rotvec_y,LeftLeg__zeroed_rel_rotvec_z,LeftFoot__zeroed_rel_rotvec_x,LeftFoot__zeroed_rel_rotvec_y,LeftFoot__zeroed_rel_rotvec_z,RightUpLeg__zeroed_rel_rotvec_x,RightUpLeg__zeroed_rel_rotvec_y,RightUpLeg__zeroed_rel_rotvec_z,RightLeg__zeroed_rel_rotvec_x,RightLeg__zeroed_rel_rotvec_y,RightLeg__zeroed_rel_rotvec_z,RightFoot__zeroed_rel_rotvec_x,RightFoot__zeroed_rel_rotvec_y,RightFoot__zeroed_rel_rotvec_z,LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz`
**Derivation formula:** `Per frame t, form continuous posture vector z_t by concatenating every listed joint zeroed rotation-vector component (T-pose–relative, radians) and every listed root-relative endpoint position (mm). Discretize each scalar channel independently with prespecified bin edges (e.g. quantiles within segment or fixed physics-based bins); encode each channel as one or more bits so z_t maps to a binary configuration vector b_t ∈ {0,1}^D (D = total bit width). Optionally downsample to Δt ≥ 1/120 s to match paper's 1 Hz summary rate for comparability. Estimate Markov-style persistence: Wc = P(b_{t+1}=b_t | b_t) from empirical counts (or same-basin proxy via Hamming ≤ k); We = 1 − Wc; exploratory breadth Q = E[We] averaged over visited states or time. Domain shift: source used 52 observational posture codes; here bits come from OptiTrack-derived kinematics with explicit binning policy.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `Creativityinsportanddance.docx#bcf960b622c485f4` |
| verbatim_quote | Here we describe some results of an analysis of a typical contact improvisation session lasting 450 seconds under no special instructional constraints, except those provided by the contact with the partner, i.e. visual and haptic information, and the force of gravity. Sequences of actions/postures were analyzed to determine their complex dynamical characteristics. Actions/postures were defined on a coarse-grained scale containing 52 movement/posture components, such as support/contact characteristics and directions and planes of motion of body segments according to established observational methodology (see Torrents, et al, 2010; Castañer, et al, 2009). To the active components a value of 1 was ascribed and to the inactive components a value of 0. Hence, a binary matrix was formed with a time resolution of 1 second. Each 1 second window was defined as a 52-component binary vector representing the action configuration during the same time interval. Reconfigurations, i.e. mutations, of action patterns were calculated as Hamming distances between any two binary vectors. For example, the change of one component of the vector from 1 to 0 or vice versa has a Hamming distance equal to 1. Hence, the Hamming distance actually measures the height of the potential barrier between two configurations. Overlap order parameter q was used to determine the structure of the potential landscape of the dancer and its dynamic properties. The overlap was defined in two intrinsically-related association measures: as a cosine similarity and as a Pearson correlation between two binary configuration vectors. A hierarchical principal component analysis (hPCA) was performed on the data using the second measure (for the plausibility of using the PCA on binary variables see Joliffe, 2002, p.339) with the aim to detect the possible nested attractor basin structure of the dancer’s action landscape. The dynamic overlap <qd(t)> was calculated as an average cosine auto-similarity of the overlap between configurations with increasing time lag to determine the dynamic properties of dancer’s complex movement patterns. |
| mechanism (one sentence) | The empirical case treats binary configurations as states in a landscape; Q quantifies tendency to leave the current configuration, i.e. exploratory breadth under the chosen discretization. |

### Segment / trial inclusion

Prefer segments ≥450 s only when emulating published overlap/hPCA analyses; otherwise prespecify shorter windows and interpret accordingly; label Gaga vs free and drug session.

### Academic justification
Evidence trace: The verified MATH text defines binary configuration vectors, Hamming reconfigurations, overlap, hPCA, and dynamic overlap; Q is the paper's escape-probability summary of exploration, so estimating We from persistence of b_t implements the same logic on mocap-derived bits.

### Implementation logic
Binarize z_t, estimate transition persistence to obtain Wc and Q per segment; log binning policy and downsampling rate in the analysis record.

### Domain shift risk analysis
Source used 52 binary observational codes at 1 Hz; we substitute OptiTrack-derived posture bits with prespecified binning—coarseness directly scales Hamming, Q, overlap, and hPCA; contact-partner constraints differ from solo Gaga.

---
## Successive-configuration Hamming distance (barrier-height proxy)
**Plausibility:** 5/10
**Source paper:** `Creativityinsportanddance.docx`
**Schema field(s):** `Hips__zeroed_rel_rotvec_x,Hips__zeroed_rel_rotvec_y,Hips__zeroed_rel_rotvec_z,Spine__zeroed_rel_rotvec_x,Spine__zeroed_rel_rotvec_y,Spine__zeroed_rel_rotvec_z,Spine1__zeroed_rel_rotvec_x,Spine1__zeroed_rel_rotvec_y,Spine1__zeroed_rel_rotvec_z,Neck__zeroed_rel_rotvec_x,Neck__zeroed_rel_rotvec_y,Neck__zeroed_rel_rotvec_z,Head__zeroed_rel_rotvec_x,Head__zeroed_rel_rotvec_y,Head__zeroed_rel_rotvec_z,LeftShoulder__zeroed_rel_rotvec_x,LeftShoulder__zeroed_rel_rotvec_y,LeftShoulder__zeroed_rel_rotvec_z,LeftArm__zeroed_rel_rotvec_x,LeftArm__zeroed_rel_rotvec_y,LeftArm__zeroed_rel_rotvec_z,LeftForeArm__zeroed_rel_rotvec_x,LeftForeArm__zeroed_rel_rotvec_y,LeftForeArm__zeroed_rel_rotvec_z,LeftHand__zeroed_rel_rotvec_x,LeftHand__zeroed_rel_rotvec_y,LeftHand__zeroed_rel_rotvec_z,RightShoulder__zeroed_rel_rotvec_x,RightShoulder__zeroed_rel_rotvec_y,RightShoulder__zeroed_rel_rotvec_z,RightArm__zeroed_rel_rotvec_x,RightArm__zeroed_rel_rotvec_y,RightArm__zeroed_rel_rotvec_z,RightForeArm__zeroed_rel_rotvec_x,RightForeArm__zeroed_rel_rotvec_y,RightForeArm__zeroed_rel_rotvec_z,RightHand__zeroed_rel_rotvec_x,RightHand__zeroed_rel_rotvec_y,RightHand__zeroed_rel_rotvec_z,LeftUpLeg__zeroed_rel_rotvec_x,LeftUpLeg__zeroed_rel_rotvec_y,LeftUpLeg__zeroed_rel_rotvec_z,LeftLeg__zeroed_rel_rotvec_x,LeftLeg__zeroed_rel_rotvec_y,LeftLeg__zeroed_rel_rotvec_z,LeftFoot__zeroed_rel_rotvec_x,LeftFoot__zeroed_rel_rotvec_y,LeftFoot__zeroed_rel_rotvec_z,RightUpLeg__zeroed_rel_rotvec_x,RightUpLeg__zeroed_rel_rotvec_y,RightUpLeg__zeroed_rel_rotvec_z,RightLeg__zeroed_rel_rotvec_x,RightLeg__zeroed_rel_rotvec_y,RightLeg__zeroed_rel_rotvec_z,RightFoot__zeroed_rel_rotvec_x,RightFoot__zeroed_rel_rotvec_y,RightFoot__zeroed_rel_rotvec_z,LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz`
**Derivation formula:** `Using the same binarization map as the Q row, obtain b_t. Stepwise Hamming distance H_t = d_H(b_t, b_{t-1}) = sum_k |b_t^k − b_{t-1}^k| (L1 on binary components). Summarize per segment: mean H, quantiles, or histogram (barrier-height distribution). For non-consecutive pairs (t, t′), d_H(b_t, b_{t′}) measures barrier cumulant between distant configurations. Confounds: binning coarseness sets the metric scale; report binning policy alongside.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `Creativityinsportanddance.docx#bcf960b622c485f4` |
| verbatim_quote | Here we describe some results of an analysis of a typical contact improvisation session lasting 450 seconds under no special instructional constraints, except those provided by the contact with the partner, i.e. visual and haptic information, and the force of gravity. Sequences of actions/postures were analyzed to determine their complex dynamical characteristics. Actions/postures were defined on a coarse-grained scale containing 52 movement/posture components, such as support/contact characteristics and directions and planes of motion of body segments according to established observational methodology (see Torrents, et al, 2010; Castañer, et al, 2009). To the active components a value of 1 was ascribed and to the inactive components a value of 0. Hence, a binary matrix was formed with a time resolution of 1 second. Each 1 second window was defined as a 52-component binary vector representing the action configuration during the same time interval. Reconfigurations, i.e. mutations, of action patterns were calculated as Hamming distances between any two binary vectors. For example, the change of one component of the vector from 1 to 0 or vice versa has a Hamming distance equal to 1. Hence, the Hamming distance actually measures the height of the potential barrier between two configurations. Overlap order parameter q was used to determine the structure of the potential landscape of the dancer and its dynamic properties. The overlap was defined in two intrinsically-related association measures: as a cosine similarity and as a Pearson correlation between two binary configuration vectors. A hierarchical principal component analysis (hPCA) was performed on the data using the second measure (for the plausibility of using the PCA on binary variables see Joliffe, 2002, p.339) with the aim to detect the possible nested attractor basin structure of the dancer’s action landscape. The dynamic overlap <qd(t)> was calculated as an average cosine auto-similarity of the overlap between configurations with increasing time lag to determine the dynamic properties of dancer’s complex movement patterns. |
| mechanism (one sentence) | Single-bit flips correspond to unit barrier crossings in the source formalism; larger Hamming steps imply larger landscape moves. |

### Segment / trial inclusion

Prefer segments ≥450 s only when emulating published overlap/hPCA analyses; otherwise prespecify shorter windows and interpret accordingly; label Gaga vs free and drug session.

### Academic justification
Evidence trace: The verified quote defines reconfigurations as Hamming distances and interprets distance as potential-barrier height between configurations; applying d_H to successive b_t from mocap implements that measurement chain.

### Implementation logic
Compute Hamming on aligned binary vectors per timestep; aggregate distribution per segment; always ship binning metadata.

### Domain shift risk analysis
Source used 52 binary observational codes at 1 Hz; we substitute OptiTrack-derived posture bits with prespecified binning—coarseness directly scales Hamming, Q, overlap, and hPCA; contact-partner constraints differ from solo Gaga.

---
## Average dynamic overlap <qd(τ)> of binary configurations
**Plausibility:** 5/10
**Source paper:** `Creativityinsportanddance.docx`
**Schema field(s):** `Hips__zeroed_rel_rotvec_x,Hips__zeroed_rel_rotvec_y,Hips__zeroed_rel_rotvec_z,Spine__zeroed_rel_rotvec_x,Spine__zeroed_rel_rotvec_y,Spine__zeroed_rel_rotvec_z,Spine1__zeroed_rel_rotvec_x,Spine1__zeroed_rel_rotvec_y,Spine1__zeroed_rel_rotvec_z,Neck__zeroed_rel_rotvec_x,Neck__zeroed_rel_rotvec_y,Neck__zeroed_rel_rotvec_z,Head__zeroed_rel_rotvec_x,Head__zeroed_rel_rotvec_y,Head__zeroed_rel_rotvec_z,LeftShoulder__zeroed_rel_rotvec_x,LeftShoulder__zeroed_rel_rotvec_y,LeftShoulder__zeroed_rel_rotvec_z,LeftArm__zeroed_rel_rotvec_x,LeftArm__zeroed_rel_rotvec_y,LeftArm__zeroed_rel_rotvec_z,LeftForeArm__zeroed_rel_rotvec_x,LeftForeArm__zeroed_rel_rotvec_y,LeftForeArm__zeroed_rel_rotvec_z,LeftHand__zeroed_rel_rotvec_x,LeftHand__zeroed_rel_rotvec_y,LeftHand__zeroed_rel_rotvec_z,RightShoulder__zeroed_rel_rotvec_x,RightShoulder__zeroed_rel_rotvec_y,RightShoulder__zeroed_rel_rotvec_z,RightArm__zeroed_rel_rotvec_x,RightArm__zeroed_rel_rotvec_y,RightArm__zeroed_rel_rotvec_z,RightForeArm__zeroed_rel_rotvec_x,RightForeArm__zeroed_rel_rotvec_y,RightForeArm__zeroed_rel_rotvec_z,RightHand__zeroed_rel_rotvec_x,RightHand__zeroed_rel_rotvec_y,RightHand__zeroed_rel_rotvec_z,LeftUpLeg__zeroed_rel_rotvec_x,LeftUpLeg__zeroed_rel_rotvec_y,LeftUpLeg__zeroed_rel_rotvec_z,LeftLeg__zeroed_rel_rotvec_x,LeftLeg__zeroed_rel_rotvec_y,LeftLeg__zeroed_rel_rotvec_z,LeftFoot__zeroed_rel_rotvec_x,LeftFoot__zeroed_rel_rotvec_y,LeftFoot__zeroed_rel_rotvec_z,RightUpLeg__zeroed_rel_rotvec_x,RightUpLeg__zeroed_rel_rotvec_y,RightUpLeg__zeroed_rel_rotvec_z,RightLeg__zeroed_rel_rotvec_x,RightLeg__zeroed_rel_rotvec_y,RightLeg__zeroed_rel_rotvec_z,RightFoot__zeroed_rel_rotvec_x,RightFoot__zeroed_rel_rotvec_y,RightFoot__zeroed_rel_rotvec_z,LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz,time_s`
**Derivation formula:** `Define overlap order parameter between two binary states as cosine similarity q(b,b′) = (b·b′) / (||b|| ||b′||) (equivalent to Pearson correlation when vectors are centered; paper also relates Pearson for hPCA). For each lag τ in frames or seconds: <qd(τ)> = (1/(T−τ)) sum_t q(b_t, b_{t+τ}) — the average cosine auto-similarity of configuration overlap vs time lag. Fit initial power-law regime on log–log plot and estimate plateau at large τ; requires long segments (paper: 450 s session). Uses same b_t as Q/Hamming rows.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `Creativityinsportanddance.docx#bcf960b622c485f4` |
| verbatim_quote | Here we describe some results of an analysis of a typical contact improvisation session lasting 450 seconds under no special instructional constraints, except those provided by the contact with the partner, i.e. visual and haptic information, and the force of gravity. Sequences of actions/postures were analyzed to determine their complex dynamical characteristics. Actions/postures were defined on a coarse-grained scale containing 52 movement/posture components, such as support/contact characteristics and directions and planes of motion of body segments according to established observational methodology (see Torrents, et al, 2010; Castañer, et al, 2009). To the active components a value of 1 was ascribed and to the inactive components a value of 0. Hence, a binary matrix was formed with a time resolution of 1 second. Each 1 second window was defined as a 52-component binary vector representing the action configuration during the same time interval. Reconfigurations, i.e. mutations, of action patterns were calculated as Hamming distances between any two binary vectors. For example, the change of one component of the vector from 1 to 0 or vice versa has a Hamming distance equal to 1. Hence, the Hamming distance actually measures the height of the potential barrier between two configurations. Overlap order parameter q was used to determine the structure of the potential landscape of the dancer and its dynamic properties. The overlap was defined in two intrinsically-related association measures: as a cosine similarity and as a Pearson correlation between two binary configuration vectors. A hierarchical principal component analysis (hPCA) was performed on the data using the second measure (for the plausibility of using the PCA on binary variables see Joliffe, 2002, p.339) with the aim to detect the possible nested attractor basin structure of the dancer’s action landscape. The dynamic overlap <qd(t)> was calculated as an average cosine auto-similarity of the overlap between configurations with increasing time lag to determine the dynamic properties of dancer’s complex movement patterns. |
| mechanism (one sentence) | Auto-similarity decay shape encodes whether configurations remain in a correlated non-ergodic shell versus mixing rapidly. |

### Segment / trial inclusion

Prefer segments ≥450 s only when emulating published overlap/hPCA analyses; otherwise prespecify shorter windows and interpret accordingly; label Gaga vs free and drug session.

### Academic justification
Evidence trace: The verified text defines <qd(t)> as average cosine auto-similarity across lags to capture dynamical structure of configuration sequences; implementing that on b_t reproduces the paper's overlap-based dynamics test (plateau/power-law readouts).

### Implementation logic
Compute pairwise cosine for each lag, average, extract slope and plateau parameters with prespecified lag ranges; require minimum segment length in samples.

### Domain shift risk analysis
Source used 52 binary observational codes at 1 Hz; we substitute OptiTrack-derived posture bits with prespecified binning—coarseness directly scales Hamming, Q, overlap, and hPCA; contact-partner constraints differ from solo Gaga.

---
## Hierarchical PCA (hPCA) on configuration vectors
**Plausibility:** 6/10
**Source paper:** `Creativityinsportanddance.docx`
**Schema field(s):** `Hips__zeroed_rel_rotvec_x,Hips__zeroed_rel_rotvec_y,Hips__zeroed_rel_rotvec_z,Spine__zeroed_rel_rotvec_x,Spine__zeroed_rel_rotvec_y,Spine__zeroed_rel_rotvec_z,Spine1__zeroed_rel_rotvec_x,Spine1__zeroed_rel_rotvec_y,Spine1__zeroed_rel_rotvec_z,Neck__zeroed_rel_rotvec_x,Neck__zeroed_rel_rotvec_y,Neck__zeroed_rel_rotvec_z,Head__zeroed_rel_rotvec_x,Head__zeroed_rel_rotvec_y,Head__zeroed_rel_rotvec_z,LeftShoulder__zeroed_rel_rotvec_x,LeftShoulder__zeroed_rel_rotvec_y,LeftShoulder__zeroed_rel_rotvec_z,LeftArm__zeroed_rel_rotvec_x,LeftArm__zeroed_rel_rotvec_y,LeftArm__zeroed_rel_rotvec_z,LeftForeArm__zeroed_rel_rotvec_x,LeftForeArm__zeroed_rel_rotvec_y,LeftForeArm__zeroed_rel_rotvec_z,LeftHand__zeroed_rel_rotvec_x,LeftHand__zeroed_rel_rotvec_y,LeftHand__zeroed_rel_rotvec_z,RightShoulder__zeroed_rel_rotvec_x,RightShoulder__zeroed_rel_rotvec_y,RightShoulder__zeroed_rel_rotvec_z,RightArm__zeroed_rel_rotvec_x,RightArm__zeroed_rel_rotvec_y,RightArm__zeroed_rel_rotvec_z,RightForeArm__zeroed_rel_rotvec_x,RightForeArm__zeroed_rel_rotvec_y,RightForeArm__zeroed_rel_rotvec_z,RightHand__zeroed_rel_rotvec_x,RightHand__zeroed_rel_rotvec_y,RightHand__zeroed_rel_rotvec_z,LeftUpLeg__zeroed_rel_rotvec_x,LeftUpLeg__zeroed_rel_rotvec_y,LeftUpLeg__zeroed_rel_rotvec_z,LeftLeg__zeroed_rel_rotvec_x,LeftLeg__zeroed_rel_rotvec_y,LeftLeg__zeroed_rel_rotvec_z,LeftFoot__zeroed_rel_rotvec_x,LeftFoot__zeroed_rel_rotvec_y,LeftFoot__zeroed_rel_rotvec_z,RightUpLeg__zeroed_rel_rotvec_x,RightUpLeg__zeroed_rel_rotvec_y,RightUpLeg__zeroed_rel_rotvec_z,RightLeg__zeroed_rel_rotvec_x,RightLeg__zeroed_rel_rotvec_y,RightLeg__zeroed_rel_rotvec_z,RightFoot__zeroed_rel_rotvec_x,RightFoot__zeroed_rel_rotvec_y,RightFoot__zeroed_rel_rotvec_z,LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz`
**Derivation formula:** `Source applied hPCA to binary 52-vectors with Pearson overlap; here apply hPCA to either (a) b_t from the same discretization as Q, or (b) continuous z_t before binning, per prespecified protocol. Standard PCA on T×D matrix; hierarchical level groups PCs to expose nested slow vs fast structure (variance thresholds, secondary PCA on PC scores). Report % variance, dwell times on discrete configuration labels derived from low-dimensional scores. Matches paper's nested-basin interpretation only under compatible window length and stationarity assumptions.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `Creativityinsportanddance.docx#bcf960b622c485f4` |
| verbatim_quote | Here we describe some results of an analysis of a typical contact improvisation session lasting 450 seconds under no special instructional constraints, except those provided by the contact with the partner, i.e. visual and haptic information, and the force of gravity. Sequences of actions/postures were analyzed to determine their complex dynamical characteristics. Actions/postures were defined on a coarse-grained scale containing 52 movement/posture components, such as support/contact characteristics and directions and planes of motion of body segments according to established observational methodology (see Torrents, et al, 2010; Castañer, et al, 2009). To the active components a value of 1 was ascribed and to the inactive components a value of 0. Hence, a binary matrix was formed with a time resolution of 1 second. Each 1 second window was defined as a 52-component binary vector representing the action configuration during the same time interval. Reconfigurations, i.e. mutations, of action patterns were calculated as Hamming distances between any two binary vectors. For example, the change of one component of the vector from 1 to 0 or vice versa has a Hamming distance equal to 1. Hence, the Hamming distance actually measures the height of the potential barrier between two configurations. Overlap order parameter q was used to determine the structure of the potential landscape of the dancer and its dynamic properties. The overlap was defined in two intrinsically-related association measures: as a cosine similarity and as a Pearson correlation between two binary configuration vectors. A hierarchical principal component analysis (hPCA) was performed on the data using the second measure (for the plausibility of using the PCA on binary variables see Joliffe, 2002, p.339) with the aim to detect the possible nested attractor basin structure of the dancer’s action landscape. The dynamic overlap <qd(t)> was calculated as an average cosine auto-similarity of the overlap between configurations with increasing time lag to determine the dynamic properties of dancer’s complex movement patterns. |
| mechanism (one sentence) | Nested PCs summarize slow collective variables subsuming faster configuration modes, matching the soft-assembled landscape narrative. |

### Segment / trial inclusion

Prefer segments ≥450 s only when emulating published overlap/hPCA analyses; otherwise prespecify shorter windows and interpret accordingly; label Gaga vs free and drug session.

### Academic justification
Evidence trace: The verified passage specifies hPCA on binary configuration vectors using Pearson association to reveal nested attractor structure; repeating that hierarchy on our b_t (or continuous z_t if prespecified) carries the same inferential goal.

### Implementation logic
Run PCA on stacked configurations, then secondary decomposition on primary PC coordinates; report variance explained and dwell statistics on discretized scores.

### Domain shift risk analysis
Source used 52 binary observational codes at 1 Hz; we substitute OptiTrack-derived posture bits with prespecified binning—coarseness directly scales Hamming, Q, overlap, and hPCA; contact-partner constraints differ from solo Gaga.

---
## Endpoint amplitude A (limb-to-COM distance sum)
**Plausibility:** 9/10
**Source paper:** `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf`
**Schema field(s):** `LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz,wbc_com_x,wbc_com_y,wbc_com_z`
**Derivation formula:** `A_t = ||p_lh,t - p_com,t|| + ||p_rh,t - p_com,t|| + ||p_lf,t - p_com,t|| + ||p_rf,t - p_com,t|| with p_* from root-relative hand/foot segment positions (mm) and p_com = [wbc_com_x,wbc_com_y,wbc_com_z]; segment mean A_condition = mean_t(A_t); compare conditions (e.g. narrative vs visual imagery) with paired tests on within-subject means. Unit note: schema positions are mm; paper reported cm—scale or convert for numeric comparison to published effect sizes.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf#9f4ccabbca16c3ad` |
| verbatim_quote | cant differences were found in amplitude ( t23 = 2.73, p = 0.012), risk ( Wilcoxon, S = 92,
p = 0.0057), and total movement (Wilcoxon, S = 68, p = 0.0497), indicating significant measur-
able effects of the condition on postural parameters (Table 2, Figure 2). |
| mechanism (one sentence) | Paired tests showed measurable condition effects on amplitude, risk, and total movement, motivating the same kinematic summaries when representation conditions are available in metadata. |

### Segment / trial inclusion

Requires trial-level labels for representation or instruction contrasts; minimum segment length for stable mean A; stratify session and drug when applicable.

### Academic justification
Evidence trace: The verified statistics show significant amplitude differences between imagery conditions with prespecified paired t-tests; the formula matches the paper's limb-to-COM sum, so OptiTrack positions plus whole-body COM implement the same contrast logic.

### Implementation logic
Compute A_t frame-wise, average per trial/segment, run paired comparisons mirroring the paper's design when metadata encodes VR vs NR (or study analogues).

### Domain shift risk analysis
Inertial-derived COM vs mocap wbc_com; studio Gaga may lack VR/NR manipulation—only valid when trial labels exist.

---
## Total movement TM (summed endpoint path lengths)
**Plausibility:** 9/10
**Source paper:** `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf`
**Schema field(s):** `LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz`
**Derivation formula:** `TM = sum_{t=2..n}(||p_lh,t-p_lh,t-1|| + ||p_rh,t-p_rh,t-1|| + ||p_lf,t-p_lf,t-1|| + ||p_rf,t-p_rf,t-1||) per trial/segment window; compare NR vs VR with Wilcoxon on paired TM differences. Units: mm summed; paper used cm—convert if comparing to published magnitudes.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf#9f4ccabbca16c3ad` |
| verbatim_quote | cant differences were found in amplitude ( t23 = 2.73, p = 0.012), risk ( Wilcoxon, S = 92,
p = 0.0057), and total movement (Wilcoxon, S = 68, p = 0.0497), indicating significant measur-
able effects of the condition on postural parameters (Table 2, Figure 2). |
| mechanism (one sentence) | Paired tests showed measurable condition effects on amplitude, risk, and total movement, motivating the same kinematic summaries when representation conditions are available in metadata. |

### Segment / trial inclusion

Same as amplitude; ensure equal window duration or include duration covariate.

### Academic justification
Evidence trace: Wilcoxon results in the verified quote establish significant total-movement shifts with imagery condition; summing endpoint displacements reproduces the paper's TM construct on our columns.

### Implementation logic
Sum Euclidean step lengths for four endpoints per segment; paired nonparametric tests when distributions skew.

### Domain shift risk analysis
Same as amplitude row; TM scales with segment duration—normalize by time if comparing unequal-length windows.

---
## Postural risk R (COM vs mid-feet proxy)
**Plausibility:** 6/10
**Source paper:** `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf`
**Schema field(s):** `wbc_com_x,wbc_com_y,wbc_com_z,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz`
**Derivation formula:** `p_midfeet,t = 0.5*(p_lf,t + p_rf,t); project to horizontal plane used in paper: p_com_proj,t = [wbc_com_x,wbc_com_z], p_midfeet_proj,t = [midfeet_x,midfeet_z] from foot root-relative positions; R_proxy,t = ||p_com_proj,t - p_midfeet_proj,t||; R_condition = mean_t(R_proxy,t). Posterior base of support (PBF) is not a native column—mid-feet proxy is an approximation; MARGINAL feasibility.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf#9f4ccabbca16c3ad` |
| verbatim_quote | cant differences were found in amplitude ( t23 = 2.73, p = 0.012), risk ( Wilcoxon, S = 92,
p = 0.0057), and total movement (Wilcoxon, S = 68, p = 0.0497), indicating significant measur-
able effects of the condition on postural parameters (Table 2, Figure 2). |
| mechanism (one sentence) | Paired tests showed measurable condition effects on amplitude, risk, and total movement, motivating the same kinematic summaries when representation conditions are available in metadata. |

### Segment / trial inclusion

Same as sibling Sánchez-derived metrics; flag trials with poor foot tracking.

### Academic justification
Evidence trace: The same verified significance block includes risk (Wilcoxon), so the inferential target is supported; replacing COP/PBF with COM-to-midfeet horizontal distance preserves a stability-expansion proxy but not the paper's exact geometry.

### Implementation logic
Compute horizontal COM–midfeet distance per frame, average per segment, use paired Wilcoxon when comparing conditions.

### Domain shift risk analysis
PBF and COP operationalization differ from native schema; foot placement and capture volume affect proxy validity.

---
## Mental-representation contrast (narrative- vs visual-episodic) for motor outcomes
**Plausibility:** 8/10
**Source paper:** `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf`
**Schema field(s):** `LeftHand__lin_rel_px,LeftHand__lin_rel_py,LeftHand__lin_rel_pz,RightHand__lin_rel_px,RightHand__lin_rel_py,RightHand__lin_rel_pz,LeftFoot__lin_rel_px,LeftFoot__lin_rel_py,LeftFoot__lin_rel_pz,RightFoot__lin_rel_px,RightFoot__lin_rel_py,RightFoot__lin_rel_pz,wbc_com_x,wbc_com_y,wbc_com_z`
**Derivation formula:** `Operationalize representation condition (NR vs VR or study-specific labels) from session/trial metadata outside this parquet (not a column in kinematics_master). Jointly interpret A, TM, and R_proxy (see sibling mappings) as dependent kinematic summaries; theory row ties narrative–visual contrast to the same OptiTrack-derived features as the MATH extraction.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `17. Unlocking Creative Movement with Inertial Technology – Sánchez Martz et al., 2025.pdf#3fa6100ee799ea51` |
| verbatim_quote | Accordingly, the primary
purpose of the study was to assess the effects of these distinct mental representations on
amplitude, risk-taking behavior, and overall movement quantity, using inertial sensor data
as an objective measure of postural and kinematic change. |
| mechanism (one sentence) | Representation-type manipulations are hypothesized to shift postural and kinematic outcomes measured objectively from motion data. |

### Segment / trial inclusion

Only sessions with reliable representation-condition labels; align label timing with kinematic windows.

### Academic justification
Evidence trace: The committee quote states the study aimed to assess distinct mental representations on amplitude, risk-taking, and movement quantity using wearable kinematics; that justifies encoding condition labels and pairing them with the sibling scalar features.

### Implementation logic
Merge metadata labels with kinematic feature table; prespecify which instructional contrasts substitute for NR/VR in Gaga studies.

### Domain shift risk analysis
Task is structured imagery in pro dancers, not open Gaga; claims must reference the actual induction labels collected.

---
## RQA Shannon entropy ENTR on forearm angular-speed embedding
**Plausibility:** 7/10
**Source paper:** `rqa_w_shEn.pdf`
**Schema field(s):** `LeftForeArm__zeroed_rel_omega_mag`
**Derivation formula:** `Build scalar series s(t) = LeftForeArm__zeroed_rel_omega_mag (deg/s) at time_s; form delay embedding Y_t = [s(t), s(t-τ), …, s(t-(m-1)τ)] with m=6, τ=8 samples (match paper m0, tau0 at 120 Hz); recurrence plot with ε=1 in embedded space; ENTR = Shannon entropy of diagonal-line-length distribution (standard RQA). Minimum contiguous segment length ≳ (m-1)τ + 50 samples. Domain shift: paper used wrist-mounted sensor streams; this uses rigid-body angular-speed magnitude from the mocap solve. Mirror with RightForeArm__zeroed_rel_omega_mag for symmetry. Alternative univariate proxies: LeftHand__lin_vel_rel_mag if emphasizing endpoint translation variability.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `rqa_w_shEn.pdf#48d9c78ca54c5969` |
| verbatim_quote | RQA Shannon entropy (ENTR) is highlighted as a robust RQA metric for individual differences in movement variability versus REC/DET/RATIO patterns in wrist-mounted sensor streams analyzed with pooled embedding m0=6, tau0=8 and recurrence threshold epsilon=1 (Figure 5 setting). |
| mechanism (one sentence) | Diagonal-line entropy summarizes recurrence-structure complexity linked to movement variability differences between individuals or conditions. |

### Segment / trial inclusion

Minimum window per schema judge; apply per segment with quality flags; stratify Gaga vs free and drug session.

### Academic justification
Evidence trace: Verified text highlights ENTR as the robust RQA metric versus REC/DET/RATIO under pooled embedding m0=6, tau0=8, epsilon=1; applying the same embedding and threshold to a mocap angular-speed channel implements that recommendation for variability contrasts.

### Implementation logic
Run standard RQA library pipeline on embedded series; record m, tau, epsilon, and window length in metadata.

### Domain shift risk analysis
Wrist linear/acceleration vs forearm angular speed; joint selection affects texture; report speed and SNR covariates.

---
## JcvPCA: joint contribution variation vs reference PCs
**Plausibility:** 8/10
**Source paper:** `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf`
**Schema field(s):** `Hips__zeroed_rel_rotvec_x,Hips__zeroed_rel_rotvec_y,Hips__zeroed_rel_rotvec_z,Spine__zeroed_rel_rotvec_x,Spine__zeroed_rel_rotvec_y,Spine__zeroed_rel_rotvec_z,Spine1__zeroed_rel_rotvec_x,Spine1__zeroed_rel_rotvec_y,Spine1__zeroed_rel_rotvec_z,LeftShoulder__zeroed_rel_rotvec_x,LeftShoulder__zeroed_rel_rotvec_y,LeftShoulder__zeroed_rel_rotvec_z,LeftArm__zeroed_rel_rotvec_x,LeftArm__zeroed_rel_rotvec_y,LeftArm__zeroed_rel_rotvec_z,LeftForeArm__zeroed_rel_rotvec_x,LeftForeArm__zeroed_rel_rotvec_y,LeftForeArm__zeroed_rel_rotvec_z,RightShoulder__zeroed_rel_rotvec_x,RightShoulder__zeroed_rel_rotvec_y,RightShoulder__zeroed_rel_rotvec_z,RightArm__zeroed_rel_rotvec_x,RightArm__zeroed_rel_rotvec_y,RightArm__zeroed_rel_rotvec_z,RightForeArm__zeroed_rel_rotvec_x,RightForeArm__zeroed_rel_rotvec_y,RightForeArm__zeroed_rel_rotvec_z,LeftUpLeg__zeroed_rel_rotvec_x,LeftUpLeg__zeroed_rel_rotvec_y,LeftUpLeg__zeroed_rel_rotvec_z,LeftLeg__zeroed_rel_rotvec_x,LeftLeg__zeroed_rel_rotvec_y,LeftLeg__zeroed_rel_rotvec_z,RightUpLeg__zeroed_rel_rotvec_x,RightUpLeg__zeroed_rel_rotvec_y,RightUpLeg__zeroed_rel_rotvec_z,RightLeg__zeroed_rel_rotvec_x,RightLeg__zeroed_rel_rotvec_y,RightLeg__zeroed_rel_rotvec_z`
**Derivation formula:** `Let θ be the column vector per frame formed by stacking listed joint rotvec components (T-pose–relative rotation vectors in deg). Dataset A = reference trials, B = comparison trials. Center θ to zero mean (per paper: no range normalization for PCA step). PCA on A yields loadings a_u,i and PCs; express B in A's PC basis (joint-wise projection / JRW); second PCA on projected B trajectories yields b^A_u,i; JcvPCA_u,i = |a_u,i| − |b^A_u,i|. Optional variance-weighted reporting uses explained variance per PC. Compare conditions (e.g. Gaga vs free, drug vs placebo) with prespecified reference A.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf#4e5cf0cdb43e5faf` |
| verbatim_quote | In conclusion, the JsvCRP , defined as the area between 2 CRP curves, provides a valuable
indication of the extent of the changes in coordination strategy. A larger area between the
curves indicates a more substantial difference in the joint coordination patterns. |
| mechanism (one sentence) | JcvPCA highlights whether joints gain or lose contribution to shared PCs relative to a reference strategy. |

### Segment / trial inclusion

Requires prespecified reference set A (e.g. placebo session) and comparison B; equal trial counts or weighted protocol per analysis plan.

### Academic justification
Evidence trace: Verified methodology describes JcvPCA as the change in absolute joint loadings between reference and test PCs after joint reprojection; executing PCA on reference trials and comparing loadings for test trials implements the published spatial coordination contrast (complementary to JsvCRP). The single verified raw_quote for this file states the JsvCRP area interpretation; JcvPCA is grounded in the same extraction's methodology block.

### Implementation logic
Stack trajectories, center, run two-stage PCA as specified, output per-joint-per-PC JcvPCA matrix for each contrast.

### Domain shift risk analysis
Exoskeleton joint angles vs rotvec stacks; interpret signs as over/under-use only with task context.

---
## JsvCRP: Hips–Spine continuous relative-phase area vs reference
**Plausibility:** 6/10
**Source paper:** `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf`
**Schema field(s):** `Hips__zeroed_rel_rotmag,Hips__zeroed_rel_omega_mag,Spine__zeroed_rel_rotmag,Spine__zeroed_rel_omega_mag,time_s`
**Derivation formula:** `Per joint i, scalar θ_i(t) = joint__zeroed_rel_rotmag (deg); θ̇_i(t) = numerical time derivative dθ_i/dt (e.g. Savitzky–Golay on rotmag) or consistent band-limited derivative; range-normalize θ_i and θ̇_i to [-1,1] over movement window using min/max per trial; phase φ_i(t) = atan2(θ̇_i,norm, θ_i,norm); CRP(Hips,Spine) = φ_Spine − φ_Hips; time-normalize to 0–100% movement duration; JsvCRP_A,B = ∫|CRP_B − CRP_A| dt (paper L¹ area between mean CRP curves). Requires paired reference condition A and test B.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf#4e5cf0cdb43e5faf` |
| verbatim_quote | In conclusion, the JsvCRP , defined as the area between 2 CRP curves, provides a valuable
indication of the extent of the changes in coordination strategy. A larger area between the
curves indicates a more substantial difference in the joint coordination patterns. |
| mechanism (one sentence) | Larger JsvCRP area means continuous relative-phase trajectories differ more between test and reference, indicating altered temporal coordination. |

### Segment / trial inclusion

Paired reference vs test segments of equal normalized duration (or registered); prespecify joint pairs; exclude gaps.

### Academic justification
Evidence trace: The committee quote defines JsvCRP as the area between two CRP curves and links larger area to stronger coordination-pattern change; integrating absolute CRP differences implements that definition once phases are built from normalized angle and velocity.

### Implementation logic
Compute mean CRP curves per condition after normalization, integrate absolute difference over normalized time.

### Domain shift risk analysis
Paper used exoskeleton angles; we use OptiTrack rotmag and derived velocity—phase portraits differ in noise structure; establish reference condition A per contrast (e.g. baseline session).

---
## JsvCRP: LeftArm–LeftForeArm continuous relative-phase area vs reference
**Plausibility:** 6/10
**Source paper:** `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf`
**Schema field(s):** `LeftArm__zeroed_rel_rotmag,LeftArm__zeroed_rel_omega_mag,LeftForeArm__zeroed_rel_rotmag,LeftForeArm__zeroed_rel_omega_mag,time_s`
**Derivation formula:** `Same as JsvCRP Hips–Spine but joint pair (LeftArm, LeftForeArm) to capture shoulder–elbow coordination; θ_i = rotmag, φ from normalized position–velocity phase portrait; integrate |ΔCRP| over normalized time. Mirrors exoskeleton shoulder/elbow validation in source paper.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf#4e5cf0cdb43e5faf` |
| verbatim_quote | In conclusion, the JsvCRP , defined as the area between 2 CRP curves, provides a valuable
indication of the extent of the changes in coordination strategy. A larger area between the
curves indicates a more substantial difference in the joint coordination patterns. |
| mechanism (one sentence) | Larger JsvCRP area means continuous relative-phase trajectories differ more between test and reference, indicating altered temporal coordination. |

### Segment / trial inclusion

Paired reference vs test segments of equal normalized duration (or registered); prespecify joint pairs; exclude gaps.

### Academic justification
Evidence trace: The committee quote defines JsvCRP as the area between two CRP curves and links larger area to stronger coordination-pattern change; integrating absolute CRP differences implements that definition once phases are built from normalized angle and velocity.

### Implementation logic
Identical pipeline to Hips–Spine on the left-chain rotmag signals.

### Domain shift risk analysis
Paper used exoskeleton angles; we use OptiTrack rotmag and derived velocity—phase portraits differ in noise structure; establish reference condition A per contrast (e.g. baseline session).

---
## JsvCRP: RightArm–RightForeArm continuous relative-phase area vs reference
**Plausibility:** 6/10
**Source paper:** `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf`
**Schema field(s):** `RightArm__zeroed_rel_rotmag,RightArm__zeroed_rel_omega_mag,RightForeArm__zeroed_rel_rotmag,RightForeArm__zeroed_rel_omega_mag,time_s`
**Derivation formula:** `Same procedure as LeftArm–LeftForeArm JsvCRP for the contralateral chain.`

### Committee evidence trace

| Field | Value |
| --- | --- |
| quote_id | `JcvPCA and JsvCRP A set of metrics to evaluate changes in joint coordination strategies.pdf#4e5cf0cdb43e5faf` |
| verbatim_quote | In conclusion, the JsvCRP , defined as the area between 2 CRP curves, provides a valuable
indication of the extent of the changes in coordination strategy. A larger area between the
curves indicates a more substantial difference in the joint coordination patterns. |
| mechanism (one sentence) | Larger JsvCRP area means continuous relative-phase trajectories differ more between test and reference, indicating altered temporal coordination. |

### Segment / trial inclusion

Paired reference vs test segments of equal normalized duration (or registered); prespecify joint pairs; exclude gaps.

### Academic justification
Evidence trace: The committee quote defines JsvCRP as the area between two CRP curves and links larger area to stronger coordination-pattern change; integrating absolute CRP differences implements that definition once phases are built from normalized angle and velocity.

### Implementation logic
Identical pipeline on right-chain signals.

### Domain shift risk analysis
Paper used exoskeleton angles; we use OptiTrack rotmag and derived velocity—phase portraits differ in noise structure; establish reference condition A per contrast (e.g. baseline session).

---
