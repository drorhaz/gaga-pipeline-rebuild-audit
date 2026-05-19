# Study framing for pipeline agents (generalized)

Use this file for **every** paper you run through the manual or automated pipeline. Attach it in Cursor (or paste into prompts) wherever the runbook asks for study context—**in addition to** a short `RESEARCH_DOMAIN` line if you use one.

---

## A. Research mission (one paragraph)

We measure **creativity-relevant and learning-relevant change in movement** during **Gaga dance** and related **free/improvised movement**, including **psilocybin versus placebo** sessions when applicable. The motion-capture pipeline yields **OptiTrack-derived kinematics** (marker-based rigid bodies; **no EMG or force plates**). Features derived from external papers must be **mapped to real schema columns** and challenged for **domain shift** (source task, sensors, population, and analysis choices vs our open-ended, whole-body Gaga context).

---

## B. Primary contrasts (fill or edit per grant / wave)

Agents should assume features may eventually support **within-subject comparisons** such as:

- **Instruction / phase:** structured Gaga class segments vs **free movement** (or improvisation) segments, defined by trial or event labels when present.
- **Intervention:** **placebo vs psilocybin** (or absence vs presence), when applicable, with session-level stratification.
- **Time:** **pre vs post** exposure (e.g. before vs after a class block) only when the study design and metadata support it.

**Held constant (whenever possible):** space, music, instruction script, segment duration class, and processing version—state explicitly when comparing sessions.

---

## C. Claim ceiling (how we are allowed to describe features)

- **Allowed without extra metrics:** change in **nonlinear dynamical structure** / **recurrence-based texture** (e.g. RQA metrics, embedding-based summaries) **under fixed, prespecified preprocessing and parameters**; **joint- or segment-specific** effects; sensitivity to **window length, smoothing, ε, m, τ** when reported as robustness.
- **Requires explicit companion metrics and pre-spec:** “**repertoire expansion**,” “**novelty**,” “**exploration**” in a behavioral sense—use **state-space occupancy, distributional overlap, motif/discrete-state diversity**, or similar, not a single scalar alone.
- **Avoid unless separately justified:** treating any one index as a **global “creativity score”** or **whole-body repertoire index** without a **predefined aggregation rule** over named segments/channels.

---

## D. Per-paper / per-feature questions agents must address

For **each** candidate mapping or `ProductFeature`, answer briefly in prose (e.g. in `domain_shift_compromise`, `segment_or_trial_inclusion`, or mapper notes):

1. **Task match:** What did the source paper **actually** ask participants to do (one movement vs several conditions vs free movement)? How does that differ from **Gaga / free movement** here?
2. **Sensor match:** What signal did they use (IMU axis, marker, derived speed, etc.) vs our **OptiTrack kinematic columns**?
3. **Comparison unit:** Should this metric be computed **per segment / per joint (or segment)**, or do we need a **predefined whole-body summary**? If summary, **which columns enter it and why**?
4. **Confounds:** What could change ENTR (or similar) without a change in “exploration” (**speed, amplitude, missing data, segment length**)? What should be **controlled, stratified, or reported alongside**?
5. **Trial inclusion:** **Which phases** (Gaga vs free vs rest), **minimum segment length**, **quality flags**, and **drug / session labels** apply?

---

## E. Schema and feasibility reminders

- Respect **declared sampling rate** and **minimum window lengths** for nonlinear metrics (see schema judge backstory in `pipeline_core.py`).
- **Do not invent columns.** If a paper requires unavailable modalities, mark **INFEASIBLE** or **strategist_drop** with a clear reason.

---

## Where to include this in your workflow

| Location | What to do |
|----------|------------|
| **This file** (`study_framing_for_agents.md`) | Keep as the **canonical long-form** framing; edit **Section B** per study wave. |
| **`.env` → `RESEARCH_DOMAIN`** | Optional: set to **one tight sentence** (same as first sentence of Section A) so automated `run_stepwise.py` picks it up. For a longer block, use a single line or quoted multiline if your dotenv supports it—or rely on manual paste below. |
| **`CURSOR_MANUAL_AGENT_RUNBOOK.md` §5 Agent 8** | Replace or extend `<study_context>` with: **first line = `RESEARCH_DOMAIN`**, then **full contents of this file** (or `@study_framing_for_agents.md`). |
| **Agent 7 (mapper)** | Paste into the prompt after **GLOBAL RULES**, e.g. `<study_framing>...</study_framing>`, so mappings respect claim ceiling and contrasts. |
| **Agent 5–6 (architect / feasibility)** | Attach when asking for **new metrics** so “impossible on marker-only MoCap” and window constraints stay aligned with Gaga + OptiTrack. |

---

## Optional one-line `RESEARCH_DOMAIN` (for `.env` or defaults)

`Measuring creativity and motor learning during Gaga dance and psilocybin interventions using OptiTrack kinematics; features must respect domain shift and claim ceiling in study_framing_for_agents.md.`
