# Pre-implementation review + implementation plan — METHODOLOGY_SPEC_v2.md

Copy everything below the line into Claude Code (or any coding agent). The document has **two parts**:

| Part | Scope | Writes production code? |
|------|--------|-------------------------|
| **Part 1** (Sections A–J) | Readiness review of `METHODOLOGY_SPEC_v2.md` | **No** — review only |
| **Part 2** | Implementation plan from the spec + Part 1 verdict | **No** — plan only, until the user explicitly approves coding |

In **one** user message, you may output **both** Part 1 (Sections A–J) **and** Part 2 (implementation plan) in order — still **no code** until the user approves implementation.

**After** that combined response, the user sends a **new message** to start coding (e.g. *“Implement according to the plan; start with P0”*). Do not implement until that approval.

---

## Part 1 — Readiness review (Sections A–J)

You are a **Senior Research Software Engineer** and **methodologist**. Perform a **readiness assessment** of our methodology document. **Do not write production code** in Part 1; this is **review only**.

**Document:** [`docs/METHODOLOGY_SPEC_v2.md`](METHODOLOGY_SPEC_v2.md) — streamlined four-feature pipeline (F1 ATF, F2 TM, F4 D_eff, F5 Joint Gini); input: `derivatives/step_06_kinematics/{RUN_ID}__kinematics_master.parquet` @ 120 Hz.

### Before answering: read first, then review

`METHODOLOGY_SPEC_v2.md` is **~1,500 lines**. **Read the entire file** using your file-reading tools (in chunks if needed) before answering any section. Do not answer from partial reads or prior training data — the spec contains project-specific decisions that override general best practices.

### Files to inspect (read as needed)

| File | Role in this review |
|------|---------------------|
| `docs/METHODOLOGY_SPEC_v2.md` | **Primary document under review** |
| `src/core_kinematics_engine.py` | Legacy v1 engine — verify §3.3 fresh-code mandate and legacy freeze claims |
| `src/EDA_PCA.py` | Legacy PCA (`run_3branch_pca`, combined-fit) — verify §3.3 incompatibility claim |
| `src/pulsicity.py` | Noise-floor function — confirm `compute_noise_floor` exists and is the sole permitted import |
| `blueprints/Feature_Blueprint_v2.md` | Academic evidence traces — cross-check retained vs dropped features' scientific grounding |
| `config/config_v1.yaml` | Current pipeline config — context for parameter namespace consolidation |

---

## A. Researcher / user surface ("frontend" vs notebook)

Answer whether the **researcher-facing UX** is well defined:

1. Is it explicit that the **primary** analyst surface is the orchestrating Jupyter notebook (`notebooks/11_METH_SPEC_v2_Features.ipynb`) as a **thin orchestrator** (§3.1), vs. a separate web application?
2. Is the split clear between: **notebook** (orchestration, parameter dicts, tables, optional ipywidgets), **`v2_viz_engine.py`** (Plotly HTML from tidy tables only), and **static exports** (CSV/JSON/MD/HTML under `results/meth_v2/`)?
3. Does the document need a **one-line glossary** (e.g. "researcher UX = notebook + optional Plotly module + exports") to avoid confusion with the word "frontend" in §3.5?
4. For **MVP (v3.0)** per §3.8, is it clear that **Block 6 / `v2_viz_engine`** is deferred and what the analyst still gets without it?

---

## B. Features: definitions and intention

Answer whether the **four features** are **well defined** and have **clear scientific / thesis intention**:

1. Are **F1, F2, F4, F5** unambiguous in: inputs (columns, units), masks (artifacts), primary scalars, and tiering (primary vs supplementary)?
2. Is the **pedagogy / narrative** (Section 0, per-feature "Gaga anchor" text) consistent with the **math** in §§1–2?
3. Are **Appendix A.1** joint names and **§3.6** 19-feature PCA rules sufficient for implementers to build column lists without guessing?
4. Are there **leftover** references to dropped metrics (seven-feature era, legacy dashboards) that could confuse scope?

---

## C. Reuse vs freshly written code

Answer whether **code reuse** is unambiguous. **Verify claims against actual files** (see file inventory above).

1. **Fresh-code mandate (§3.3):** Must `v2_feature_engine.py`, `v2_longitudinal.py`, and `v2_viz_engine.py` be written **from scratch** with **no** copy-paste from `core_kinematics_engine.py` or `EDA_PCA.py`?
2. **Sole exception:** Open `src/pulsicity.py` and confirm `compute_noise_floor` exists with the expected signature. Is the spec correct that this is the **sole** permitted import?
3. **Legacy PCA — verify the incompatibility:** Read `src/EDA_PCA.py`, locate `run_3branch_pca`, and confirm it uses **combined-fit** PCA (all sessions stacked). Cite the specific evidence (e.g. the `fit` call). Then confirm the spec's §3.3 correctly characterizes this as incompatible with **reference-anchored** PCA per §F4.
4. **Legacy freeze:** Must `EDA_PCA.py` and `core_kinematics_engine.py` remain **unmodified** for v2? Check whether `core_kinematics_engine.py` already imports from `EDA_PCA.py` (it does — cite the import block) — would v2 changes to either file risk breaking the legacy pipeline?
5. Is the **upstream pipeline** (Steps 01–06 → master Parquet) clearly **out of scope** for the v2 notebook except as **input files**?

---

## D. Scope: MVP vs deferred

1. What is **in** vs **out** for **Phase 1 (MVP / v3.0)** vs **Phase 2 (v3.1)** per §3.8? List each item explicitly.
2. Are there **conflicts** between the document header, Section 0, §3.1 (7 blocks), **Appendix B** (build sequence / Steps 1–6), and **Appendix C** (full export manifest)?
3. Does **Appendix B's build sequence** (Steps 1–7) align with **§3.8's MVP priorities** (P0–P4)? Flag any ordering or scope mismatches between the two.
4. Does the spec **anywhere** require Appendix C's full 6+ file export for a "minimal" MVP run, or is the two-file bundle (`feature_scalars.csv` + `run_metadata.json`) consistently treated as sufficient for Phase 1?

---

## E. Logical consistency (internal coherence)

1. Do **masks** and **gates** align across Block 0, F1, F2, and PCA (e.g. any-joint artifact vs all-joint clean, reference vs generic thresholds)?
2. Are **PCA** steps internally consistent: scaler fit, PCA fit, `transform`, per-PC variance, D_eff, Gini from loadings — any contradictions?
3. Do **F1/F2 independence** and **F4/F5 shared `PCAEngine`** rules remain consistent with the notebook structure and the four parameter dicts?
4. Does the **19-feature PCA rule** (§3.6) specify **exactly which 19 columns**? Cross-check against the **Appendix A.1 joint name table** — are all 19 joints listed, and is the column suffix (`zeroed_rel_omega_mag`) stated unambiguously?

---

## F. Scientific rigor

Cross-reference `blueprints/Feature_Blueprint_v2.md` for the academic evidence traces underlying the four retained features.

1. For each primary outcome (**ATF, TM, D_eff, Joint Gini**): is the operational definition defensible given **N=3 pilot** scale?
2. Are **confounds** and **companions** (Section 5, reliability gates) adequate?
3. Is **reference-anchored vs session-native** sensitivity framed appropriately, including limitations (orthogonal modes, basis quality)?
4. Are **bootstrap**, **multiplicity**, and **inferential** language framed as **descriptive / exploratory** where appropriate?
5. **Dropped features:** The blueprint proposed 15 features; the spec retains 4. Are the **dropped** features (F3 Amplitude, F6 JcvPCA, F7 JsvCRP, and exploratory-family metrics like Q, Hamming, hPCA, RQA) cleanly removed from the spec with no stale references? Does the **rationale** for each drop (Section 0) hold up?
6. Do the **retained features' math** (§§1–2) match their derivation formulas in the blueprint? Flag any divergence in inputs, formulas, or interpretation.

---

## G. Backend / library implementation

1. **`PCAEngine` carrier object:** Is it fully specified — required fields (scaler, pca, loadings, `var_per_pc`, reference `run_id`, joint list), construction contract via `build_pca_engine`, and **immutability** after construction? Could an implementer build it without guessing?
2. **Function signatures:** Are `compute_atf`, `compute_total_movement`, `build_pca_engine`, `compute_d_eff`, `compute_joint_gini`, `compute_quality_gates`, `validate_reference`, and `apply_time_window` specified with enough detail (inputs, outputs, return types/shapes, gate behavior)?
3. **Edge cases:** What happens when a session has **zero clean frames** after gating? When the **reference session fails** validation? When `time_window` selects an **empty slice**? Are these behaviors defined or left to implementer judgment?
4. **CSV schema:** Does the spec define the **column names and types** for `feature_scalars.csv` (the MVP export), or must the implementer infer them from scattered feature definitions?
5. Any other **missing normative detail** that would block implementation?

---

## H. Exports and provenance

1. Is the **MVP two-file export** (`feature_scalars.csv` + `run_metadata.json`, §3.8) **aligned** with **Appendix C**, or do leftover clauses still imply **full** Appendix C for a "minimal" run?
2. Does **`run_metadata.json`** have a defined schema (required keys, nesting), or only illustrative examples? Could two independent implementers produce structurally identical metadata files from the spec alone?
3. Does **Appendix C.6** (optional artifacts / skipped blocks) create any obligation beyond the two MVP files? Is the "normative" language there scoped to Phase 2 only?

---

## I. Blocking issues and verdict

1. List **specific** ambiguities, contradictions, or missing decisions that would **block** or **risk** implementation. For each, suggest **one** concrete **doc fix** or **explicit implementation assumption**.
2. **Verdict:** **GO** / **GO with minor clarifications** / **NO-GO** — one short paragraph covering **implementation clarity**, **logic**, and **scientific rigor**.

**When citing problems:** name the **section** (e.g. §F4, Block 0, §3.8, Appendix B) and state the **ambiguity** in one sentence.

---

## J. Mandatory follow-up: doc-fix recommendations

Regardless of verdict, produce these concrete recommendations for the document author:

1. If **Section A** flags any UX ambiguity: draft a short **"Researcher UX and code reuse (v3.0)"** box for §3.1 or §3.3 with: (1) primary UX = `11_METH_SPEC_v2_Features.ipynb`, (2) optional Plotly = `v2_viz_engine.py`, (3) a one-row table: **reuse** (`pulsicity.compute_noise_floor` only) vs **fresh** (all v2 modules; no legacy PCA helpers).
2. If **Section G** flags missing function contracts: draft a **function signature table** for `v2_feature_engine.py` (name, inputs, output type, key edge-case behavior) that could be added as a new appendix or §3.3 addendum.
3. If **Section H** flags schema gaps: draft the **column list** for `feature_scalars.csv` with types and brief descriptions.
4. For **every blocking issue** in Section I: provide the **exact one-line doc edit or addition** (with target section) that resolves it.

---

# Part 2 — Implementation plan (after Part 1)

**Intended outcome:** A **recommended implementation plan** that (1) stays within **`docs/METHODOLOGY_SPEC_v2.md`** scope (MVP vs §3.8 deferred items), (2) is **traceable** to spec sections via the matrix below, and (3) is **executable** — ordered steps, files, functions, and verification so the same agent (or a human) can implement by following the plan after approval.

Run Part 2 **only after** completing Part 1 (Sections A–J). In Part 2, produce **only** the implementation plan — **do not** create, edit, or patch `v2_feature_engine.py`, the notebook, or any other implementation files. Coding begins **only** after the user approves in a **separate message** (see Human gate below).


### Preconditions

1. **Verdict gate:** If Section I is **NO-GO**, output a **short Part 2** that states: implementation planning is **deferred** until blocking doc issues are resolved; list **minimum** prerequisites (doc edits or analyst decisions) before replanning.
2. If the verdict is **GO** or **GO with minor clarifications**, produce the **full** implementation plan below.
3. Treat **`docs/METHODOLOGY_SPEC_v2.md`** as the **sole normative source** for what to build, how blocks depend on each other, and what is out of scope. Incorporate **Part 1 findings** (blockers, assumptions, Section J drafts) into risks and open questions — do not ignore them.

### Mandatory: every Part 2 plan item must trace to the spec

**Strict rule:** The implementation plan is a **projection of `docs/METHODOLOGY_SPEC_v2.md` into tasks**. You must **not** invent features, file roles, or sequencing that the spec does not authorize. If something is implied but not written, label it **`ASSUMPTION`** and cite the closest spec section.

1. **Re-ground before Part 2:** After Part 1, re-open or scroll the relevant parts of **`docs/METHODOLOGY_SPEC_v2.md`** (especially §§1–2, §3.1, §3.3, §3.6, §3.8, Appendix B) so the plan is checked against **current** document text, not memory.
2. **Traceability:** For **each** numbered implementation step (P0–P4 / each notebook block), include **at least one** explicit **`docs/METHODOLOGY_SPEC_v2.md` citation** (e.g. §3.8 P2, §F1, Block 0 spec in §3.1). Steps without a citation are **invalid** — fix or remove them.
3. **Forbidden:** Adding metrics, modules, or notebook blocks that the spec lists as **dropped**, **deferred to v3.1**, or **legacy-only** unless the user has explicitly overridden in chat (default: follow the spec).
4. **Conflict check:** If Part 1 flagged a contradiction inside the spec, the plan must **repeat** that conflict and state which interpretation you will implement **until the document is edited** — do not silently pick a branch.

### Deliverable: structured implementation plan

Produce **one** consolidated plan with the following sections (use headings).

#### 0. Spec traceability matrix (required)

A **table** with one row per major task or milestone (at minimum: Block 0, F1, F2, shared PCA, F4, F5, export). Columns:

| Task / milestone | `METHODOLOGY_SPEC_v2.md` citations (§ or appendix) | Out of scope for MVP? (yes/no + cite §3.8 if yes) |

This matrix is the **audit trail** that the plan is reviewed against the methodology document.

#### 1. Scope summary

- **MVP (v3.0)** vs **deferred (v3.1)** — bullet list aligned with §3.8 explicitly naming what you will **not** build in the first pass (`v2_longitudinal.py`, `v2_viz_engine.py`, block bootstrap, Branch D, T2 isolation, full Appendix C, etc.).
- **Artifacts** for MVP: confirm target files (`feature_scalars.csv`, `run_metadata.json`, paths under `results/meth_v2/`) and any **assumed** column/schema choices if the spec is ambiguous (flag them).

#### 2. File and module checklist

| Deliverable | Path | Notes |
|-------------|------|--------|
| Feature engine | `src/v2_feature_engine.py` | Per §3.3; fresh code; `pulsicity.compute_noise_floor` only |
| Notebook | `notebooks/11_METH_SPEC_v2_Features.ipynb` | Thin orchestrator; four dicts; block order §3.1 |
| Optional params module | e.g. `src/meth_v2_params.py` or inline in notebook | If spec allows consolidating dicts |
| **Out of scope for MVP** | `src/v2_longitudinal.py`, `src/v2_viz_engine.py` | State “not created in MVP” unless user overrides |

#### 3. Implementation order (aligned with §3.8 P0–P4 and notebook blocks)

Numbered steps with **dependencies** (e.g. gates before F1; PCA engine before F4/F5). Map each step to:

- Spec section(s)
- Functions to implement or notebook cells to add
- **Verification** for that step (unit-style checks, shape checks, or “run on one sample `RUN_ID`”)

Example shape (adapt to the spec):

1. **P0 / Block 0:** loaders, `apply_time_window`, `compute_quality_gates`, `validate_reference`, analyst-decision plumbing, `quality_df`.
2. **P1 / Block 1:** `compute_atf` + `PARAMS_F1` + noise-floor audit path.
3. **P2 / Block 2:** `compute_total_movement` + `PARAMS_F2`.
4. **P3 / Blocks 3–4:** `build_pca_engine`, `compute_d_eff`, `compute_joint_gini` + `PARAMS_PCA_F4_F5` (single `PCA.fit` on reference; anti–double-dipping).
5. **P4 / Block 5:** assemble tidy table, write `feature_scalars.csv` + `run_metadata.json`.

#### 4. Notebook build strategy (Appendix B alignment)

- State whether you will follow **Appendix B**: **one notebook block at a time**, stop after each block for human confirmation — or a single pass with clear checkpoints. Default recommendation: **iterative** (Appendix B) for first integration.
- List **minimal test inputs**: e.g. one known-good `RUN_ID` and reference session choice (placeholder if TBD).

#### 5. Risks and open questions

- Bullets: **spec ambiguities** from Part 1 not yet resolved, **legacy freeze** constraints, **performance** (bootstrap off), **Branch D** off for first pass.
- **Explicit assumptions** the plan takes for anything underspecified (e.g. empty-session behavior, JSON key names).

#### 6. Definition of done (MVP)

- Checklist: e.g. end-to-end run on at least one subject, two export files present, notebook `Restart & Run All` works with locked params, no edits to `EDA_PCA.py` / `core_kinematics_engine.py`.

### Human gate before coding

After Part 2, **stop**. Do **not** create or edit `v2_feature_engine.py`, the notebook, or other implementation files until the user sends a message such as:

- *“Approve the plan. Implement P0 only.”* or
- *“Implement the full MVP per the plan.”*

A **later message** in the same chat thread (after the review + plan) counts as approval — proceed only from the step the user specifies (e.g. P0 only vs full MVP).

---

*End of prompt document.*
