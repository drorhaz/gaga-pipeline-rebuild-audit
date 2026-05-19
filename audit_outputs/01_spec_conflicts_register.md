# 01 Spec Conflicts Register

**Phase:** 1
**Date:** 2026-05-14
**Agent:** Claude Sonnet 4.6 — Audit Mode, Read-only
**Mode:** Read-only

This register lists every identified conflict, ambiguity, or inconsistency between specification documents and/or code. Each entry includes:
- Evidence (file + line number where available)
- Severity classification (Critical / High / Medium / Low)
- Whether it can be resolved by the agent or requires user decision
- Recommended action (for Phase 10 decision matrix)

---

## Conflict Classification Key

| Severity | Meaning |
|----------|---------|
| **Critical** | May produce incorrect scientific results or cause pipeline failure |
| **High** | Creates ambiguity that could lead to incorrect analysis or silent inconsistency |
| **Medium** | Creates maintenance confusion or contradicts documentation but does not corrupt results |
| **Low** | Residual dead code or documentation gap with no immediate impact |

---

## C1 — Three-generation methodology coexistence without formal archival

**Severity:** High
**Confidence:** High
**Layer:** C (Downstream Methodology)
**Requires user decision:** NO — the authority is clear (v3.0 wins), but archival needs explicit action

**Evidence:**
- `docs/Thesis_Analytical_Pipeline.md` v1.4 (2026-03-25): Self-declares as "the single authoritative reference for every analytical decision in this thesis." Governs N=2 study. Defines 3+3+1 framework.
- `docs/METHODOLOGY_SPEC.md` v2.0 (2026-04-06): Self-declares as "the self-contained execution manual for implementing, debugging, and defending all seven primary features." Defines 7-feature architecture.
- `docs/METHODOLOGY_SPEC_v2.md` v3.0 (2026-04-06): Explicitly supersedes v2.0. Defines current 4-feature architecture. States: "Supersedes: `METHODOLOGY_SPEC.md` (v2.0, 7-feature architecture)."

**Problem:** v3.0 explicitly supersedes v2.0. But neither v3.0 nor v2.0 explicitly supersedes v1.4 (`Thesis_Analytical_Pipeline.md`). The v1.4 file still declares itself the single authority. An agent or collaborator reading the repository could follow v1.4 as authoritative.

**Resolution:** Mark `docs/Thesis_Analytical_Pipeline.md` header as "LEGACY — superseded by METHODOLOGY_SPEC_v2.md v3.0." Mark `docs/METHODOLOGY_SPEC.md` header as "ARCHIVED — superseded by METHODOLOGY_SPEC_v2.md v3.0." This is a documentation-only action.

**Recommended decision-matrix action:** `KEEP_DOCUMENT` (mark legacy files with supersession headers)

---

## C2 — Two active downstream engine implementations for conflicting specs

**Severity:** Critical
**Confidence:** High
**Layer:** C (Downstream Methodology)
**Requires user decision:** YES — which engine governs active development?

**Evidence:**
- `src/core_kinematics_engine.py` (line 3 docstring): "Pure analytical backend for the **3+3+1** Thesis Kinematic Pipeline." Implements: ATF, T1-anchored PCA, 3-branch (dynamics + pose + reach), D_eff, Gini, State-Space Entropy, SampEn, A/P Ratio, RQA. Governs `notebooks/09_Subject_Exploration_Dashboard.ipynb`.
- `src/v2_feature_engine.py` (line 3 docstring): "Implements the four-feature pipeline specified in METHODOLOGY_SPEC_v2.md." Implements: ATF, TM, D_eff, Gini. Single dynamics branch. No Entropy, SampEn, A/P, RQA. Governs `notebooks/11_METH_SPEC_v2_Features.ipynb`.
- `src/core_kinematics_engine.py` was added in the same commit as `src/v2_feature_engine.py` (PR #7, commit `c66c6ea`), meaning BOTH were added together — this was a deliberate side-by-side addition, not a replacement.

**Problem:** Both engines exist simultaneously in `src/`. There is no deprecation signal on `core_kinematics_engine.py`. Both are importable. Future code could accidentally call either.

**Impact:** If someone runs `notebooks/09_Subject_Exploration_Dashboard.ipynb`, they execute the 3+3+1 legacy analysis. If they run `notebooks/11_METH_SPEC_v2_Features.ipynb`, they execute the v2 analysis. The results are methodologically incomparable. No warning exists to prevent this.

**Resolution options:**
1. Mark `core_kinematics_engine.py` as legacy (rename to `_legacy_core_kinematics_engine.py` or add a deprecation header). [Safest.]
2. Delete `core_kinematics_engine.py` and `EDA_PCA.py` entirely. [Risky without user approval — potential loss of working legacy analysis.]
3. Keep both, document the distinction clearly in headers. [Interim minimum viable action.]

**Recommended decision-matrix action:** `UNKNOWN_NEEDS_EVIDENCE` pending user decision on Q1 (open question in source-of-truth document). Do not touch until Phase 10.

---

## C3 — Import path errors in `src/core_kinematics_engine.py`

**Severity:** Critical (runtime failure)
**Confidence:** High
**Layer:** C implementation
**Requires user decision:** NO — clear bug, but low priority given C2 (engine is legacy)

**Evidence:**
- `src/core_kinematics_engine.py` line 59: `from pulsicity import compute_noise_floor`
- `src/core_kinematics_engine.py` line 60: `from EDA_PCA import (`
- `src/v2_feature_engine.py` line 41 (correct): `from src.pulsicity import compute_noise_floor`

**Problem:** `core_kinematics_engine.py` uses bare module names (`pulsicity`, `EDA_PCA`) without the `src.` prefix. These imports will fail with `ModuleNotFoundError` unless the working directory is `src/` at runtime. When called via the project root (the standard way), these imports break.

**Impact:** `notebooks/09_Subject_Exploration_Dashboard.ipynb` will fail to import `core_kinematics_engine` when run from project root. This may already be a known silent failure.

**Resolution:** Fix to `from src.pulsicity import ...` and `from src.EDA_PCA import ...`. Low priority if the module is being deprecated (C2).

**Recommended decision-matrix action:** `LOCAL_REFACTOR` (1-line fix per import) — but defer to after C2 decision is made. If `core_kinematics_engine.py` is being archived, no fix needed.

---

## C4 — Manual matrix multiply `X @ pca.components_.T` in `src/EDA_PCA.py` skips PCA centering

**Severity:** Critical (scientific correctness)
**Confidence:** High
**Layer:** C implementation (legacy engine only)
**Requires user decision:** NO — this is a concrete bug against a clear spec

**Evidence:**
- `src/EDA_PCA.py` line 830: `Y = X @ pca.components_.T`
- `src/EDA_PCA.py` line 1674: `Y = X @ pca_obj.components_.T`
- `METHODOLOGY_SPEC_v2.md` (§F4, Strategic Crossroads): "Always use `pca.transform()`, never manual `X @ W.T`" — explicit warning that these two produce different results when `pca.mean_ != 0`.
- `src/EDA_PCA.py` lines 652–659: `pca.transform()` IS used for the fit-data assertion check, and a consistency assertion is added. But lines 830 and 1674 then bypass it.

**Problem:** `pca.transform(X)` computes `(X - pca.mean_) @ pca.components_.T`. The manual `X @ pca.components_.T` skips the subtraction of `pca.mean_` (which is the reference/T1 session mean). When projecting T2 or T3 sessions, the T1-derived mean is NOT subtracted, which shifts all projected coordinates by a fixed vector equal to `pca.mean_ @ pca.components_.T`. This changes the variance distribution across PCs and therefore corrupts D_eff and Gini values for all non-reference sessions.

**Quantitative impact estimate:** The magnitude of the error is `||pca.mean_|| * ||pca.components_||` projected onto each PC. For standardized data (`StandardScaler` was applied), `pca.mean_` should be near zero — but only if the reference session is the one the scaler was fit on. If the scaler was fit on the reference session and then applied to all sessions, non-reference sessions' scaled means are NOT zero, so `pca.mean_` is non-trivially positive/negative.

**This bug exists in `src/EDA_PCA.py` which is used only by `src/core_kinematics_engine.py` (legacy 3+3+1 engine).**

**`src/v2_feature_engine.py` does NOT have this bug** — it uses `pca.transform()` correctly.

**Resolution:** Replace `X @ pca.components_.T` with `pca.transform(X)` at lines 830 and 1674 of `src/EDA_PCA.py`. If the legacy engine is being archived, this may be moot. If any 3+3+1 results have already been reported, they should be validated against re-run with the fix.

**Recommended decision-matrix action:** `REWRITE_CANDIDATE` for the specific lines IF `EDA_PCA.py` / `core_kinematics_engine.py` remain in active use. `REMOVE_CANDIDATE` if the legacy engine is archived per C2 decision.

---

## C5 — `Chest` as dead matching pattern in `src/filtering.py` trunk classification

**Severity:** Low
**Confidence:** High
**Layer:** A implementation
**Requires user decision:** NO

**Evidence:**
- `src/filtering.py` lines 60, 1837, 1900, 2096: `Chest` included in trunk pattern lists, e.g., `['Pelvis', 'Spine', 'Torso', 'Hips', 'Abdomen', 'Chest', 'Back']`
- `src/preprocessing.py` lines 35: `"Chest": "Spine1"` — OptiTrack name `Chest` is renamed to `Spine1` at parse time (Step 01).
- Therefore, by the time Step 04 (filtering) runs, no column named `Chest*` exists. The pattern never matches.

**Impact:** No incorrect behavior. `Spine1` is still matched via the `Spine` substring pattern in the same list. The `Chest` entry is dead code.

**Resolution:** Remove `Chest` from the pattern lists in `src/filtering.py`. Pure cleanup — zero risk.

**Recommended decision-matrix action:** `LOCAL_REFACTOR` (cosmetic, defer to cleanup phase)

---

## C6 — Task restriction: `Thesis_Analytical_Pipeline.md` mandates P2-only; current derivatives are P1-only

**Severity:** Critical (methodological validity)
**Confidence:** High
**Layer:** C (Downstream Methodology) + Data
**Requires user decision:** YES — fundamental design question

**Evidence:**
- `docs/Thesis_Analytical_Pipeline.md` §1.2: "Task analyzed: P2 only — the unstructured free improvisation task. P1 (structured) and P3 are excluded from this pipeline to maintain task homogeneity."
- `derivatives/step_06_kinematics/` — all 3 existing outputs are for subject 671, task P1_R1 (e.g., `671_T1_P1_R1_Take 2026-01-06 03.57.12 PM_001__kinematics_master.parquet`)
- Current batch configs that remain: `batch_configs/subject_671_all.json` and `subject_651_all.json` include P1, P2, P3 sessions.

**Problem:** The methodology mandates P2 (free improvisation) for the longitudinal comparison. All available baseline derivatives are P1 (structured). Any downstream feature extraction run on the current derivatives would be computing the metrics on the wrong task condition.

**`METHODOLOGY_SPEC_v2.md`** does not explicitly restrict to P2 — it inherits this constraint from the study design described in `Thesis_Analytical_Pipeline.md`. The omission of an explicit P2-only gate in v3.0 is a documentation gap.

**Impact:** If a downstream analysis notebook loads `derivatives/step_06_kinematics/*.parquet` without filtering to P2 sessions, it will compute ATF, TM, D_eff, and Gini on P1 (structured) data and silently report results for the wrong task.

**Resolution:** METHODOLOGY_SPEC_v2.md should explicitly state the task filter. The `build_pca_engine` and `load_session` functions in `v2_feature_engine.py` should receive session IDs that are already task-filtered by the analyst. This is a workflow question more than a code bug, but the code lacks a task-type metadata guard.

**Recommended decision-matrix action:** `KEEP_DOCUMENT` (add explicit P2 statement to METHODOLOGY_SPEC_v2.md) + `KEEP_LOG_QC` (add session task-type validation to `v2_feature_engine.py` load_session). Requires user confirmation of task-filtering policy.

---

## C7 — N=2 vs N=3 across specification generations

**Severity:** Medium
**Confidence:** High
**Layer:** C (Downstream Methodology)
**Requires user decision:** YES

**Evidence:**
- `docs/Thesis_Analytical_Pipeline.md` §1.3: "N=2 is not a statistical limitation to be apologized for" — explicitly lists only subjects 651 and 671.
- `docs/METHODOLOGY_SPEC.md` v2.0 header: "N=3 pilot"
- `docs/METHODOLOGY_SPEC_v2.md` v3.0 header: "N=3 pilot"
- Active data: `data/651/`, `data/671/` only. Batch configs for 734, 763, 505, 621 were deleted in the current branch.
- No derivatives exist for any subject beyond 651 and 671.

**Problem:** The two newer methodology specs claim N=3, but there is no evidence of a third subject in the processed data. Either (a) the third subject's data has not yet been collected or processed, (b) the third subject was removed from the study after the docs were written, or (c) the N=3 claim is aspirational/prospective.

**Impact:** If `METHODOLOGY_SPEC_v2.md` is implemented assuming N=3 and only N=2 subjects have data, the `reference_run_id` parameter for PCA anchoring needs to be confirmed per subject. No functional blocking issue, but results section N should be accurate.

**Resolution:** User must clarify the actual study N before the thesis methods section is finalized.

**Recommended decision-matrix action:** `UNKNOWN_NEEDS_EVIDENCE` — record in open questions.

---

## C8 — `config_v1.yaml` is overwritten per run (reproducibility risk)

**Severity:** High
**Confidence:** High
**Layer:** A (Pipeline Operation)
**Requires user decision:** NO for audit; YES for engineering fix

**Evidence:**
- `run_pipeline.py` lines 140–180: `update_config()` reads `config_v1.yaml`, overwrites `current_csv`, `subject_id`, `subject_height_cm`, `subject_mass_kg`, `subject_height_source`, `subject_weight_source`, then writes back via `yaml.dump()`.
- Current `config_v1.yaml` line 4: `current_csv: 671/T3/671_T3_P1_R1_Take 2026-02-03 08.05.01 PM_000.csv` — this is the last processed session.

**Problem:** The YAML config file serves as both the processing configuration AND the runtime state journal. Overwriting it per run means:
1. The config file does NOT represent the configuration used for any specific run — it represents the last run.
2. The `current_csv` field read by notebooks from `config_v1.yaml` at startup may conflict with the `current_csv` parameter injected via papermill (which is more reliable).
3. Re-running the pipeline on any session will silently change what `config_v1.yaml` reports.
4. Diffs of `config_v1.yaml` in git reflect only the last-processed session, masking all parameter changes.

**This is the origin of the "M config/config_v1.yaml" entry in `git status`.**

**Resolution:** Separate the stable configuration (filter params, thresholds, etc.) from the per-run runtime state (`current_csv`, `subject_id`, anthropometrics). Options: (a) write a separate `run_state.yaml` per run; (b) pass all run-specific parameters exclusively via papermill and never write them back to config; (c) version the config with a git-tracked `config_v1.yaml.base` and a gitignored `config_v1_runtime.yaml`.

**Recommended decision-matrix action:** `LOCAL_REFACTOR` or `REDESIGN_CANDIDATE` — medium priority. Does not affect correctness of current derivatives but creates a reproducibility audit trail gap.

---

## C9 — `Chest` in `METHODOLOGY_SPEC.md` v2.0 Axial group (already resolved in v3.0)

**Severity:** Low — already resolved
**Confidence:** High
**Layer:** C (Downstream Methodology)

**Evidence:**
- `docs/METHODOLOGY_SPEC.md` (v2.0) §F1, Step 4: "Axial | Hips, Spine, Spine1, Neck, Head, **Chest**" — 6 joints
- `docs/METHODOLOGY_SPEC_v2.md` (v3.0) §F1, Step 4: "Axial | Hips, Spine, Spine1, Neck, Head" with explicit note "no `Chest` column — use **Spine1** for mid-thorax" — 5 joints
- `src/core_kinematics_engine.py` line 91: `AXIAL_JOINTS = ("Hips", "Spine", "Spine1", "Neck", "Head")  # 5 joints; no "Chest"` — aligned with v3.0
- `src/v2_feature_engine.py` lines 57–61: `"axial": ["Hips", "Spine", "Spine1", "Neck", "Head"]` — aligned with v3.0

**Status:** Both active engines use the correct 5-joint Axial group (no Chest). The v2.0 doc error is superseded. **No action required beyond noting it.**

**Recommended decision-matrix action:** `KEEP_AS_IS` — already correct in both current implementations.

---

## C10 — 3-branch PCA (dynamics + pose + reach) vs single-primary-branch

**Severity:** Medium — deliberate methodological change, not a conflict
**Confidence:** High
**Layer:** C (Downstream Methodology)

**Evidence:**
- `src/core_kinematics_engine.py` line 129: `BRANCHES = ("dynamics", "pose", "reach")`
- `src/EDA_PCA.py` (called by core engine): Implements `run_3branch_pca()` — runs PCA on all 3 branches
- `docs/METHODOLOGY_SPEC_v2.md` §F4 Implementation Parameters, `kinematic_branch`: "Primary narrative: `dynamics`... Alternatives for sensitivity only: `pose`... or `reach`"
- `src/v2_feature_engine.py`: No branches constant — single `dynamics` branch in `build_pca_engine()`

**Status:** This is a deliberate architectural change between the legacy 3+3+1 spec and the current v2 spec — not a bug. The 3-branch approach in the legacy engine is retained there for completeness (3+3+1 framework uses branch sensitivity as a primary output). The v2 spec rationalizes this to single primary branch with sensitivity checks.

**Impact:** When using the v2 engine: results will differ from the legacy engine because (a) only dynamics branch is primary, and (b) the PCA feature space is 19-dimensional (omega_mag scalars) vs potentially 57-dimensional (pose/reach use 3D vectors per joint). D_eff values from the two engines are NOT comparable.

**Recommended decision-matrix action:** `KEEP_AS_IS` in both engines (intentional design choice). Document explicitly in thesis methods section which branch was used.

---

## C11 — `METHODOLOGY_SPEC_v2.md` references "Class 1" as PCA reference; data uses T1 as terminology

**Severity:** Low — naming only
**Confidence:** High
**Layer:** C (Downstream Methodology)

**Evidence:**
- `docs/METHODOLOGY_SPEC_v2.md` §F4: `reference_session = Class 1 (T1)`
- `docs/Thesis_Analytical_Pipeline.md` §1.2: Timepoints labeled T1 (baseline), T2 (post-training), T3 (afterglow)
- `src/v2_feature_engine.py`: Uses `reference_run_id` parameter — run ID string, not "T1" label
- Batch configs: Sessions are labeled `T1`, `T2`, `T3` per timepoint in file names and paths

**Status:** "Class 1" in METHODOLOGY_SPEC.md v2.0 referred to "Gaga class 1 of 10 sessions" (10-class longitudinal design). "T1" in Thesis_Analytical_Pipeline.md refers to the first timepoint in the 3-timepoint study (baseline). In the current study context, Class 1 ≈ T1, but these were originally different study designs. For the current pipeline, the reference session is T1 (the baseline recording).

**Impact:** Potential confusion when reading v2.0 vs v3.0 vs Thesis docs side-by-side. No code impact if the `reference_run_id` parameter is correctly set to a T1 session ID.

**Recommended decision-matrix action:** `KEEP_DOCUMENT` — clarify "Class 1 = T1 baseline" in METHODOLOGY_SPEC_v2.md comment.

---

## Summary table

| ID | Description | Severity | User decision needed | Action |
|----|-------------|----------|---------------------|--------|
| C1 | Three methodology gens without formal archival | High | No | `KEEP_DOCUMENT` (add supersession headers) |
| C2 | Two active downstream engine implementations | Critical | **YES** | `UNKNOWN_NEEDS_EVIDENCE` pending Q1 |
| C3 | Import path errors in `core_kinematics_engine.py` | Critical | No (but moot if C2 → archive) | `LOCAL_REFACTOR` or defer |
| C4 | Manual `X @ W.T` skips PCA centering in `EDA_PCA.py` | Critical | No (scientific bug) | `REWRITE_CANDIDATE` if legacy kept; `REMOVE_CANDIDATE` if archived |
| C5 | Dead `Chest` pattern in `filtering.py` | Low | No | `LOCAL_REFACTOR` (defer) |
| C6 | P2-only policy not enforced; derivatives are P1-only | Critical | **YES** | `KEEP_LOG_QC` + `KEEP_DOCUMENT` |
| C7 | N=2 vs N=3 across docs | Medium | **YES** | `UNKNOWN_NEEDS_EVIDENCE` |
| C8 | `config_v1.yaml` mutated per run | High | No | `LOCAL_REFACTOR` / `REDESIGN_CANDIDATE` |
| C9 | `Chest` in Axial group in METHODOLOGY_SPEC v2.0 | Low (resolved) | No | `KEEP_AS_IS` |
| C10 | 3-branch vs 1-branch PCA (deliberate change) | Medium | No | `KEEP_AS_IS` (documented intent) |
| C11 | "Class 1" vs "T1" terminology | Low | No | `KEEP_DOCUMENT` (clarify in comment) |

### Critical conflicts requiring user decisions (stop for input):
- **C2**: Which engine is authoritative? Should `core_kinematics_engine.py` be archived?
- **C6**: Confirm P2-only policy; process P2 sessions before downstream analysis runs
- **C7**: Confirm study N (is the third subject coming, or is it N=2?)
