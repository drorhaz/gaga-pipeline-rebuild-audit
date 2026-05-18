# ACTIVE_METHOD_REVIEW_PROTOCOL.md

**Purpose:**  
Ensure that every data manipulation, signal transformation, QC rule, and feature characterization in Phase 13 is actively reviewed for scientific validity, without allowing uncontrolled algorithm rewrites or scope expansion.

**Status:** Methodological review protocol for Phase 13 implementation.  
**Scope:** Applies to Phase 13 tickets and any future implementation work that touches motion data processing, filtering, interpolation, kinematic derivation, QC, or feature reliability.  
**Important:** This protocol does **not** add new Phase 13 tickets. It defines when the implementation agent must pause, inspect, document, test, or escalate methodological concerns.

---

## 1. Core Principle

Minimal v1 must preserve the approved `hybrid_modular_rebuild` strategy:

- preserve validated scientific and computational logic by default;
- do not rewrite working algorithms without evidence;
- keep pandas/parquet architecture;
- keep `kinematics_master.parquet` rich in continuous kinematic state;
- avoid parquet bloat from QC/reliability/reporting summaries;
- prefer logs, tests, documentation, sidecars, reason codes, and reliability labels over method replacement.

However:

> Preserving algorithms by default does **not** mean ignoring evidence that a method may be scientifically insufficient.

If code inspection, QC outputs, regression diffs, synthetic tests, or scientific references suggest that an existing method may need methodological upgrade, the agent must **pause and escalate** rather than silently modifying the method.

---

## 2. What Counts as a Methodological Operation?

A methodological operation is any step that changes, derives, filters, interpolates, masks, normalizes, summarizes, labels, or classifies motion data.

Examples include:

- raw OptiTrack/Motive parsing;
- session label normalization;
- calibration metadata interpretation;
- artifact detection;
- artifact masking;
- interpolation;
- gap filling;
- resampling;
- quaternion normalization;
- SLERP;
- reference orientation estimation;
- Markley mean / orientation averaging;
- Euler/ISB angle derivation;
- angular velocity computation;
- velocity / acceleration / tangential velocity derivation;
- Butterworth / Winter filtering;
- Hampel outlier detection;
- PSD / dance-band validation;
- CoM computation;
- bone-length / segment consistency QC;
- feature extraction;
- feature reliability labeling;
- QC gates;
- session/day-level QC aggregation.

---

## 3. Active Review Checklist

For every methodological operation touched by a ticket, the implementation agent must answer these questions in the implementation log before modifying code:

1. **What is the input?**  
   Raw data, processed data, sidecar, config, metadata, parquet, feature table, etc.

2. **What is the output?**  
   Parquet column, sidecar field, QC flag, feature value, metadata field, test result, etc.

3. **Does this step modify measured data, derive new data, or only log/report?**

4. **What assumptions does the step make?**  
   Examples: short gaps only, uniform sampling, valid quaternions, stationary noise, anatomical rigidity, no long occlusions, root-relative coordinate convention.

5. **What known failure modes exist?**  
   Examples: oversmoothing, derivative noise amplification, gap-boundary artifacts, quaternion sign flips, gimbal lock, long-gap interpolation drift, Hampel false positives, missing calibration metadata.

6. **Which downstream outputs can be affected?**  
   Examples: velocity, angular velocity, ATF, TM, Gini, D_eff, PCA, feature reliability, spectral features, nonlinear metrics, ML/DL tensors.

7. **Is the current behavior already covered by golden tests or regression checks?**

8. **Is there a relevant reference guardrail?**  
   Use `REFERENCE_GUARDRAILS_FOR_PHASE13.md` to identify relevant scientific constraints.

9. **Are there comparable methods in established biomechanics / mocap papers, official documentation, or libraries?**

10. **Is the current method sufficient for Minimal v1, or is there evidence that it needs review?**

The goal is not to force algorithm changes. The goal is to make methodological assumptions visible and testable.

---

## 4. Acceptable Use of References, Documentation, and Similar Libraries

The agent may consult scientific references, official documentation, or established biomechanics/mocap libraries to clarify:

- terminology;
- assumptions;
- coordinate conventions;
- quaternion handling;
- filtering validation;
- gap/interpolation logging;
- artifact taxonomy;
- QC sidecar design;
- feature reliability reporting;
- metadata/provenance structures;
- validation and testing approaches.

Acceptable examples:

- compare quaternion convention and sign-continuity handling;
- verify that SLERP is the correct interpolation method for orientation resampling;
- compare filtering/cutoff validation practices;
- compare artifact reason-code taxonomies;
- compare gap duration / gap-location logging practices;
- compare how feature reliability is reported outside the frame-level data table.

Not acceptable without explicit approval:

- adopting a new dependency;
- replacing current algorithms;
- changing quaternion convention;
- changing filtering method;
- activating PCHIP or SLERP gap filling;
- implementing Kalman smoothing;
- implementing PCA / low-rank / tensor completion;
- implementing autoencoder / GNN / transformer / diffusion correction;
- implementing automatic artifact repair;
- implementing full Skurowski-style spatial-correlation artifact detection;
- changing `kinematics_master.parquet` schema beyond the approved backlog;
- moving QC/reliability summaries into per-row parquet columns;
- expanding Phase 13 beyond the approved ticket scope.

References are guardrails, not automatic implementation instructions.

---

## 5. Methodology Upgrade Decision Gate

If the agent finds evidence that a current method may be scientifically insufficient, the agent must **not** change the method inside the current ticket.

Instead, the agent must stop and create a **Methodology Upgrade Brief**.

This applies when concerns arise from:

- code inspection;
- failed tests;
- QC log anomalies;
- regression diffs;
- synthetic/golden mismatch;
- scientific reference guardrails;
- comparison with established libraries or pipelines;
- ambiguity in the approved backlog;
- evidence that downstream features are being distorted.

---

## 6. Methodology Upgrade Brief Template

Create a brief under:

```text
docs/pipeline_rebuild_audit/methodology_upgrade_briefs/
```

Suggested filename:

```text
MUB_{ticket_id}_{method_name}_{YYYY-MM-DD}.md
```

Template:

```markdown
# Methodology Upgrade Brief — {method_name}

**Ticket:** {ticket_id}  
**Date:** YYYY-MM-DD  
**Agent:** {agent/model}  
**Status:** DRAFT | USER_REVIEW_REQUIRED | APPROVED | DEFERRED | REJECTED

---

## 1. Affected Method

- Function(s):
- File(s):
- Pipeline stage:
- Current ticket:

## 2. Current Behavior

Describe what the current method does and where it appears in the pipeline.

## 3. Evidence Triggering Concern

Mark all that apply:

- [ ] Code inspection
- [ ] Failed test
- [ ] QC log anomaly
- [ ] Regression diff
- [ ] Synthetic/golden mismatch
- [ ] Reference guardrail
- [ ] Similar-library comparison
- [ ] Backlog ambiguity
- [ ] Downstream feature distortion

Details:

## 4. Issue Type

Classify the concern:

- [ ] Bug
- [ ] Logging deficiency
- [ ] Validation deficiency
- [ ] Documentation deficiency
- [ ] Methodological limitation
- [ ] Architecture limitation
- [ ] Scope ambiguity

## 5. Relevant Scientific / Technical Support

List relevant sources:

- Reference paper(s):
- Official documentation:
- Similar libraries / pipelines:
- Prior audit findings:

## 6. Risks of Keeping Current Method

Explain what may go wrong if nothing changes.

## 7. Risks of Changing Method

Explain how changing the method could affect:

- parquet schema;
- feature values;
- golden baselines;
- downstream analysis;
- thesis claims;
- historical-session compatibility;
- runtime / complexity.

## 8. Candidate Alternatives

List possible alternatives, including “log/test only” or “defer.”

For each alternative:
- description;
- implementation complexity;
- blast radius;
- validation required;
- pros;
- cons.

## 9. Required Tests Before Any Upgrade

- Unit tests:
- Synthetic tests:
- Golden regression tests:
- Feature drift tests:
- Runtime tests:
- Backward-compatibility checks:

## 10. Expected Output Impact

- Parquet columns:
- PyArrow metadata:
- JSON sidecars:
- CSV sidecars:
- Feature tables:
- QC reports:
- Golden checksums:

## 11. Recommendation

Choose one:

- [ ] Fix now within current ticket
- [ ] Add logs/tests now, defer method change
- [ ] Defer to post-Minimal v1
- [ ] Open new approved ticket
- [ ] Reject upgrade; current method acceptable

Rationale:

## 12. User Decision Needed

State the exact decision needed from the user.
```

No methodological upgrade may be implemented until the brief is reviewed and explicitly approved.

---

## 7. Ticket-Specific Application

This protocol applies most strongly to the following tickets and layers:

### Ticket 007b — Quaternion diagnostics sidecar + Hampel summary

Review focus:

- quaternion norm behavior;
- sign / hemisphere continuity;
- SLERP validity;
- Markley/eigenvector averaging assumptions;
- quaternion-log angular velocity assumptions;
- whether diagnostics are sidecar-only;
- Hampel burden as a limitation marker, not ground truth.

Escalate if:

- quaternion convention appears inconsistent;
- angular velocity appears derived from Euler angles;
- sign flips affect downstream outputs;
- the agent thinks SO(3)-aware smoothing is needed.

Do not implement SO(3)-aware smoothing in Minimal v1 without a Methodology Upgrade Brief and approval.

---

### Ticket 009 — S02 label correction + artifact/gap logging

Review focus:

- active artifact masking path vs inactive genuine gap-fill path;
- `linear_interp` label correctness;
- gap duration;
- gap location/context if available;
- gap multiplicity;
- position vs quaternion gap events;
- artifact reason codes;
- whether gaps are being repaired or merely logged.

Escalate if:

- long gaps are common enough to invalidate downstream features;
- interpolation is being applied to long or feature-sensitive segments;
- the current logging cannot distinguish artifact masking from genuine gap filling;
- PCHIP or SLERP gap filling appears necessary.

Do not activate PCHIP or SLERP gap filling in Minimal v1 without approval.

---

### Ticket 011 — `is_hampel_outlier` correction

Review focus:

- whether Hampel returns a per-frame mask;
- whether the mask represents actual modifications or candidate outliers;
- whether the OR-column behavior matches the approved design;
- per-joint Hampel burden in `filtering_summary.json`;
- avoiding interpretation of Hampel as full artifact ground truth.

Escalate if:

- Hampel appears to remove true movement peaks;
- Hampel masks are inconsistent across joints;
- per-frame OR mask is insufficient for ML exclusion;
- sidecar mask is needed for scientific traceability.

Do not change Hampel algorithm or thresholds inside Ticket 011 unless explicitly approved.

---

### Ticket 014b — `feature_reliability_table.csv`

Review focus:

- how gap burden affects feature reliability;
- how filter verdict affects feature reliability;
- how reference fallback affects feature reliability;
- how artifact burden affects feature reliability;
- which feature families are derivative-sensitive;
- which features are sensitive to nonlinear/gap effects;
- whether feature reliability is in CSV sidecar, not parquet.

Escalate if:

- a feature cannot be reliably classified with available QC inputs;
- a feature family depends on missing or unreliable upstream signals;
- nonlinear metrics are proposed without strict gap/interpolation validation.

Do not add per-feature reliability columns to parquet.

---

### Ticket 015 — S04 PSD/dance-band correction loop

Review focus:

- cutoff frequency;
- filter order;
- zero-phase status;
- dance-band attenuation;
- noise-band attenuation;
- peak attenuation;
- border effects;
- velocity / angular velocity / acceleration sensitivity;
- inner Winter loop vs outer PSD loop distinction;
- ensuring Stage 1, Stage 2, and quaternion median filter remain unchanged;
- avoiding artifact-fraction control.

Escalate if:

- current cutoff settings appear scientifically insufficient;
- derivative-sensitive features are distorted;
- the PSD loop fails to converge;
- oversmoothing remains unresolved;
- the agent believes Butterworth should be replaced;
- the agent believes GCV/quintic splines, Savitzky-Golay, Kalman, or another filter should become default.

Do not replace Butterworth/Winter filtering inside Ticket 015 without explicit user approval and validation.

---

### S06 — Rich kinematic state extraction

Review focus:

- preserving approved continuous kinematic state;
- avoiding removal of velocity/angular velocity/CoM/orientation-derived variables;
- metadata vs sidecar vs parquet decisions;
- coordinate-system documentation;
- Euler/ISB as derived interpretability/reporting outputs;
- quaternion-first internal representation.

Escalate if:

- schema cleanup would remove scientifically useful kinematic signals;
- Euler/ISB outputs are used as authoritative internal orientation representation;
- angular velocity computation appears inconsistent with quaternion-first principles.

Do not remove rich kinematic signals in the name of parquet minimalism.

---

### S11 — Downstream feature engine

Review focus:

- preserving ability to derive dance-relevant features;
- amplitude;
- turning velocity;
- angular velocity;
- CoM/pelvis motion;
- spectral summaries;
- body expansion;
- balance/hold features;
- whole-body participation;
- feature reliability;
- avoiding aesthetic scoring/classification in Minimal v1.

Escalate if:

- a feature appears scientifically invalid under current QC;
- a feature depends on signals that are unreliable or missing;
- a new feature family is proposed as Minimal v1 requirement.

Do not add aesthetic scoring or dance classification algorithms in Minimal v1.

---

## 8. Active Review Categories

When documenting a concern, classify it into one of these categories:

| Category | Meaning | Allowed action in current ticket |
|----------|---------|----------------------------------|
| `BUG_FIX` | Current behavior contradicts approved spec or code intent | May fix if within ticket scope |
| `LOGGING_DEFICIENCY` | Method may be acceptable but lacks traceability | Add logs/sidecar if ticket allows |
| `VALIDATION_DEFICIENCY` | Method may be acceptable but lacks tests | Add tests if ticket allows |
| `DOCUMENTATION_DEFICIENCY` | Method is acceptable but assumptions unclear | Add docs/metadata if ticket allows |
| `METHODOLOGICAL_LIMITATION` | Current method may be scientifically insufficient | Stop and write Methodology Upgrade Brief |
| `ARCHITECTURE_LIMITATION` | Current architecture blocks safe implementation | Stop and escalate |
| `FUTURE_METHOD_CANDIDATE` | Better method may exist but is not Minimal v1 | Document future candidate only |
| `SCOPE_EXPANSION` | Proposed change exceeds approved ticket | Stop and ask user |

---

## 9. Decision Matrix

| Finding | Default action |
|---------|----------------|
| Missing log or sidecar field | Add if current ticket allows |
| Missing test for approved behavior | Add if current ticket allows |
| Documentation ambiguity | Document in implementation log and/or PROJECT_MEMORY |
| Existing algorithm has suspected limitation but no failure evidence | Document as future candidate |
| Existing algorithm produces wrong output under approved tests | Stop; Methodology Upgrade Brief |
| Reference suggests better method but current method still acceptable | Future candidate; no implementation |
| Reference contradicts current method for this use case | Stop; Methodology Upgrade Brief |
| Similar library uses different convention | Document and compare; do not switch silently |
| QC logs show high artifact/gap/filter burden | Add reliability warning; consider brief |
| Regression diff affects non-target outputs | Stop and investigate |
| Required file not listed in ticket | Stop and ask user |
| Ticket requires touching KEEP_AS_IS file | Stop and ask user |
| Proposed change expands scope | Stop and ask user |

---

## 10. Examples

### Example 1 — Filtering concern during Ticket 015

Finding:

- PSD loop converges, but peak angular velocity is attenuated by 40% in a golden session.

Default action:

- Do not replace Butterworth immediately.
- Document derivative-sensitive failure.
- Add/verify peak attenuation log.
- Create Methodology Upgrade Brief if attenuation affects thesis-critical features.

Possible recommendation:

- log/test now;
- continue Minimal v1 with reliability warning;
- open future filtering validation ticket.

---

### Example 2 — Long artifact segment during Ticket 009

Finding:

- `max_artifact_segment_frames_positions = 42` for wrist in several sessions.

Default action:

- Do not activate PCHIP automatically.
- Log segment length.
- Add reliability warning for features depending on that joint/time window.
- Create Methodology Upgrade Brief if long gaps affect thesis-critical features.

Possible recommendation:

- defer PCHIP until synthetic tests;
- mark affected features `USE_WITH_CAUTION`.

---

### Example 3 — Hampel over-flags true movement peaks

Finding:

- Hampel flags many frames during fast turns that visually appear to be real movement.

Default action:

- Do not change Hampel thresholds inside Ticket 011.
- Log high Hampel burden.
- Mark Hampel as incomplete for that session/joint.
- Create Methodology Upgrade Brief if feature reliability is affected.

Possible recommendation:

- keep OR mask for ML exclusion;
- add reason code;
- future artifact taxonomy validation.

---

### Example 4 — Quaternion sign discontinuity

Finding:

- Adjacent frames have alternating quaternion signs for a joint.

Default action:

- Verify whether hemisphere continuity correction exists.
- Add diagnostic count if Ticket 007b scope allows.
- Do not change quaternion convention silently.
- Create Methodology Upgrade Brief if correction changes angular velocity.

Possible recommendation:

- preserve current convention;
- add tests for `q` and `-q` equivalence;
- add sidecar diagnostic.

---

### Example 5 — “Parquet cleanup” would remove velocity fields

Finding:

- Agent proposes removing tangential velocity or angular velocity fields to reduce schema size.

Default action:

- Reject inside current ticket.
- Parquet minimalism applies to QC/reliability bloat, not approved continuous kinematic state.
- Preserve signals needed for downstream scientific and ML/DL analysis.

Possible recommendation:

- document feature families that require those signals.

---

## 11. Required Language in Implementation Logs

For any ticket touching methodological operations, include this section:

```markdown
## Active Method Review

### Methodological operations touched
- [list]

### Assumptions reviewed
- [list]

### Relevant reference guardrails
- [REFERENCE_GUARDRAILS_FOR_PHASE13.md sections / papers]

### Comparable methods or libraries checked
- [none / list]
- Reason if none:

### Downstream outputs potentially affected
- [list]

### Review outcome
- [ ] Current method remains acceptable
- [ ] Logging/test/documentation added
- [ ] Future candidate documented
- [ ] Methodology Upgrade Brief created
- [ ] User decision required

### Notes
[free text]
```

This section is required for tickets:

- 007b
- 009
- 011
- 014b
- 015

It is recommended for:

- 003
- 004
- 006
- 008
- 010
- S06/S11-related changes

It is optional for:

- 001
- 002
- 005
- 012
- 013
- 014a

---

## 12. Final Rule

The implementation agent must remain scientifically alert but operationally conservative.

> Do not ignore methodological problems.  
> Do not fix them silently.  
> Review, document, test, and escalate.

Minimal v1 succeeds only if it is both:

1. stable enough to run reproducibly across all sessions; and  
2. honest enough to expose uncertainty, limitations, and future methodological upgrade needs.
