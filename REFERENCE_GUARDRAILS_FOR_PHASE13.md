**A. Paper-derived guardrails mapped to tickets**

*   **Ticket 007b**
    *   **Guardrails**: Quaternion sign/hemisphere continuity constraints and Spherical Linear Interpolation (SLERP) interpolation validation must be preserved and monitored. Univariate statistical thresholding (Hampel) alone is an incomplete artifact detector; track Hampel modification fraction per joint as a basic logging metric, not a definitive ground-truth identifier. 
    *   **Supporting papers**: Challis (2020), Skurowski & Pawlyta (2022).
    *   **Implication type**: LOG_NOW.
    *   **Output destination**: `validation_report.json` and `filtering_summary.json` sidecars.

*   **Ticket 009**
    *   **Guardrails**: Nonlinear dynamic calculations (like Lyapunov exponents) are highly sensitive to missing data; gap duration, gap location, and the interpolation method used must be strictly tracked. Establish an artifact taxonomy and specific reason codes (e.g., single peaks, heavy noise, step changes, slow changes) to properly log occurrences.
    *   **Supporting papers**: Gonabadi et al. (2022), Skurowski & Pawlyta (2022).
    *   **Implication type**: LOG_NOW / DOCUMENT_NOW.
    *   **Output destination**: `s02_interpolation_stats.json` sidecar.

*   **Ticket 011**
    *   **Guardrails**: Standard univariate thresholding (Hampel filter) ignores spatial inter-marker correlation; it is an incomplete artifact detector and should not be used as ground truth. Therefore, Hampel limitations must be logged. (Note: The single OR `is_hampel_outlier` parquet column is a backlog implementation decision, not directly derived from the papers).
    *   **Supporting papers**: Skurowski & Pawlyta (2022).
    *   **Implication type**: LOG_NOW / DOCUMENT_NOW.
    *   **Output destination**: `filtering_summary.json` sidecar.

*   **Ticket 012**
    *   **Guardrails**: OptiTrack system precision is not absolute ground truth due to calibration pointer pivot effects and examiner variance. Missing historical calibration metadata (or anatomical landmark uncertainty) should reduce evidence levels or trigger a WARN flag, but must not automatically fail the session.
    *   **Supporting papers**: Rácz, Seregély & Kiss (2025).
    *   **Implication type**: LOG_NOW / TEST_NOW.
    *   **Output destination**: `fast_qc_report.json` sidecar and tests.

*   **Ticket 014a**
    *   **Guardrails**: REPORTING_VALIDATION_GUARDRAIL: Clearly report the kinematic model, generalized coordinate systems, degrees of freedom, algorithm parameters, and validation references for reproducibility.
    *   **Supporting papers**: Cereatti et al. (2024).
    *   **Implication type**: LOG_NOW.
    *   **Output destination**: `session_qc_report.json` sidecar.

*   **Ticket 014b**
    *   **Guardrails**: Feature reliability status must evaluate gap presence, as nonlinear variability measures degrade based on where the gaps occurred. Feature reliability must warn if peak attenuation or border effects occurred during filter numerical differentiation.
    *   **Supporting papers**: Gonabadi et al. (2022), Crenna et al. (2021).
    *   **Implication type**: LOG_NOW.
    *   **Output destination**: `feature_reliability_table.csv` sidecar.

*   **Ticket 015**
    *   **Guardrails**: Derivative-sensitive feature protection requires that the adaptive loop evaluates, logs, and tests cutoff frequencies, filter order, zero-phase status, dance-band attenuation, noise-band attenuation, peak attenuation, border effects, and velocity/angular-velocity/acceleration sensitivity. Do not apply arbitrary or universal extreme low-pass smoothing (e.g., 1-5 Hz) without evaluating the specific signal content via objective methods like PSD analysis. **The papers support validation of cutoff/filter/derivative risks, but do not prove the current Gaga filtering settings are already valid**.
    *   **Supporting papers**: Crenna et al. (2021), Sinclair et al. (2013), Woltring (1985).
    *   **Implication type**: TEST_NOW / LOG_NOW.
    *   **Output destination**: `filtering_summary.json` sidecar and unit/regression tests.

*   **S06 / kinematics_master.parquet**
    *   **Guardrails**: Preserve a quaternion-first orientation representation internally to avoid mathematical singularities (gimbal lock). Document all angle conventions and rotation orders explicitly. Test quaternion sign/hemisphere continuity, SLERP interpolation validity, Markley eigenvector averaging methods, and quaternion-derivative angular velocity assumptions. Euler/ISB angles may be exported strictly as derived interpretability/reporting signals with explicit coordinate-system and rotation-sequence metadata, but must not act as the authoritative internal representation for averaging, differentiation, or interpolation.
    *   **Supporting papers**: Challis (2020), Wu et al. (2005).
    *   **Implication type**: PRESERVE_NOW / DOCUMENT_NOW / TEST_NOW.
    *   **Output destination**: Parquet columns, PyArrow schema metadata, and tests.

*   **S11 / feature engine**
    *   **Guardrails**: Preserve rich kinematic state for dance-relevant feature families, specifically parameters like amplitude, turning velocity, angular velocity, CoM/pelvis motion, and spectral movement summaries. The paper supports preserving this kinematic state and planning for dance-relevant features, but it does NOT justify implementing aesthetic scoring or new feature families in Minimal v1.
    *   **Supporting papers**: Torrents et al. (2013).
    *   **Implication type**: DOCUMENT_NOW / FUTURE_CANDIDATE.
    *   **Output destination**: Feature engine outputs and future planning specs.

*   **PROJECT_MEMORY**
    *   **Guardrails**: Derivative estimation from noisy displacement data is mathematically ill-posed and highly sensitive to measurement errors; validation is mandatory.
    *   **Supporting papers**: Woltring (1985).
    *   **Implication type**: DOCUMENT_NOW.
    *   **Output destination**: `PROJECT_MEMORY_FOR_IMPLEMENTATION.md`.

***

**B. Backlog constraints, not paper-derived claims**

These constraints are strictly defined by the pipeline planning documents and architecture reviews, rather than scientific literature:
1.  **Scope**: The Minimal v1 implementation backlog is strictly locked to 15 tickets. No additional major algorithms or frameworks are allowed.
2.  **Anti-Overengineering**: Adopt a `hybrid_modular_rebuild` strategy. Preserve all 25 currently working algorithms; rebuild only the infrastructure layer. No broad repository reorganization outside approved source-cleanup tickets; legacy moves must follow the approved cleanup/readiness map.
3.  **Parquet Architecture**: `kinematics_master.parquet` must remain strictly numeric and ML-ready. All QC metrics and diagnostics must be diverted to JSON/CSV sidecars (Sidecar-first QC policy). 
4.  **Ticket 011 Implementation**: The single OR `is_hampel_outlier` parquet column is a backlog design decision (Option B) to provide an essential ML training mask without introducing schema bloat, rather than a requirement directly derived from the papers.
5.  **Ticket 015 Control Loop**: The S04 adaptive loop must use the PSD/dance-band threshold method, explicitly rejecting the artifact-fraction controller proposed previously.
6.  **Metadata Fields**: `ref_is_fallback` must be implemented as a PyArrow schema metadata field, not as a per-row parquet data column.
7.  **Fail Gates**: The S01 hard FAIL gate is strictly limited to dead/too-short sessions (duration < 30s, frames < 3600) and unrecoverable parse failures. Label mismatches or missing columns trigger a WARN, not a FAIL.
8.  **Naming Conventions**: Session label columns must strictly be `subject_id`, `timepoint`, `piece`, and `rep`.
9.  **Kinematic Specifics**: "Hips" are permanently excluded from the `ATF_axial` computation.
10. **Forensic Subsystem**: The 8 forensic subsystem scripts must receive zero changes during Minimal v1.

***

**C. Do-not-implement-now list (Future-only methods)**

*   Kalman smoothing
*   PCA / low-rank / tensor completion
*   autoencoder / neural network / transformer / diffusion correction
*   automatic artifact repair
*   full Skurowski detector / FFNN repair
*   SO(3)-aware smoothing as default
*   automatic long-gap recovery
*   aesthetic scoring
*   dance classification
*   replacing Butterworth without validation
*   Euler-angle derivative angular velocity
*   GCV/quintic splines as Minimal v1 replacement

***

**D. Minimal additions to Phase 13**

The following minor enhancements are permitted to be implemented directly within existing tickets without requiring new backlog entries:
*   **Logs**: Artifact fraction ratios, Hampel modification counts, quaternion continuity flip counts, and gap segment durations.
*   **Tests**: Derivative sensitivity evaluations (peak attenuation checks), boundary effect logging, and structural tests for all new metadata.
*   **Sidecars**: Producing `{RUN_ID}__validation_report.json`, `session_qc_report.json`, and `feature_reliability_table.csv` using read-only aggregation.
*   **Documentation**: Adding explicit schema versions, coordinate-system metadata annotations, and updating `PROJECT_MEMORY_FOR_IMPLEMENTATION.md`.
*   **Reason Codes**: Tagging specific artifact occurrences (e.g., peak, heavy noise, step change) in preprocessing metrics.
*   **Warnings**: Flagging missing anatomical pointer calibration data, label mismatches, and over-smoothing triggers without halting the pipeline.

***

**E. Final Claude CLI summary**

```text
# IMPLEMENTATION SUMMARY - PHASE 13
===================================
1. PAPER-DERIVED GUARDRAILS (SCIENCE)
- Torrents: Preserve amplitude/turning/spectral features for dance analysis. Do not implement aesthetic scoring yet.
- Cereatti/Wu/Challis: Preserve quaternion-first orientations for internal math. Export Euler/ISB angles purely for standard reporting, with explicit metadata. Test sign continuity, SLERP, and Markley mean.
- Crenna/Sinclair: Validate cutoff/filter/derivative risks (border effects, peak attenuation). Do not apply extreme low-pass cutoffs arbitrarily. The current settings are not pre-validated by the papers.
- Gonabadi: Evaluate nonlinear features against strict gap duration/location reliability checks.
- Skurowski: Log reason codes for anomalies. Avoid using Hampel as a sole ground-truth anomaly detector.
- Rácz: Document pointer pivot effects/uncertainty; downgrade missing calibration to WARN, not FAIL.

2. BACKLOG CONSTRAINTS (ARCHITECTURE)
- Locked to 15 tickets (Minimal v1). No broad repository reorganization outside approved source-cleanup tickets; legacy moves must follow the approved cleanup/readiness map.
- Parquet stays numeric/ML-ready. All detailed metadata and QC metrics go to JSON/CSV sidecars.
- Ticket 011 single OR `is_hampel_outlier` column is a backlog decision to avoid schema bloat, not a paper requirement.
- Ticket 015 relies on a PSD/dance-band correction loop, explicitly rejecting artifact-fraction logic.
- S01 FAIL is strictly for dead sessions (<30s) or corrupted parsing.
- ref_is_fallback is PyArrow metadata only (no per-row column).

3. FUTURE-ONLY METHODS (DO NOT IMPLEMENT)
- No ML-based or predictive recovery: FFNN, Autoencoders, Diffusion, Transformers, or full spatial-correlation.
- No dimensionality reduction / PCA gap-filling.
- No GCV quintic splines or Kalman smoothing.
- No aesthetic scoring or dance classification algorithms in the core pipeline.
- No Euler-angle derivative angular velocity computation.
```

Clarification:
These references are scientific guardrails, not automatic instructions to replace algorithms. Minimal v1 should prefer documentation, logs, tests, sidecars, reason codes, and reliability labels over method replacement. Any change to filtering, interpolation, orientation processing, or derivative estimation requires explicit approval, synthetic/golden validation, and regression re-lock.

Clarification:
“Parquet minimal” does not mean removing rich continuous kinematic signals. It means avoiding per-row QC/reliability/reporting bloat. Preserve the approved continuous kinematic state needed for downstream scientific and ML/DL analysis.

Clarification:
Dance feature papers justify preserving the ability to derive dance-relevant features; they do not require implementing new aesthetic, classification, or feature-family algorithms in Minimal v1. Preserve the kinematic state needed to derive amplitude, turning velocity, angular velocity, CoM/pelvis motion, spectral summaries, body expansion, and balance/hold features in downstream analysis.

Clarification:
If an implementation detail is ambiguous, especially in Ticket 007b, 009, 011, 014b, or 015, the agent may consult the original papers for verification from directory /references/REFERENCE_GUARDRAILS_FOR_PHASE13/... However, the papers should be used only to clarify guardrails, limitations, terminology, and validation requirements. Do not use them to introduce new algorithms, expand ticket scope, or override the approved backlog without explicit approval.