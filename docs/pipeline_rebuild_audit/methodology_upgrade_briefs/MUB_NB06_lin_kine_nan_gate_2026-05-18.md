# Methodology Upgrade Brief — NB06 Linear Kinematics NaN Gate

**Ticket:** Pre-Batch-1 (discovered during Dev Set readiness audit)
**Date:** 2026-05-18
**Agent:** Claude Sonnet 4.6
**Status:** APPROVED — Option A integrated into Ticket 007b (CLOSED 2026-05-19)

**ADDENDUM 2026-05-19 (from Ticket 009 investigation):** Stage-by-stage NaN tracing
of `651_T1_P1_R1` revealed that **S01/S02/S03 parquets are all CLEAN** (zero NaN
in position columns), but **S04 filtered parquet introduces NaN** in 6 upper-body
`__py` columns (Head: 34, Neck: 36, LeftShoulder: 26, RightShoulder: 25, LeftArm: 17,
RightArm: 4 NaN frames respectively, ~0.01–0.12% per column). For `651_T2_P1_R1`,
S04 introduces NaN in 4 axial `__px` columns (Hips/Spine/LeftUpLeg/RightUpLeg).
For `671_T1_P2_R1` and `671_T3_P2_R1`, S04 produces no NaN.

**Root cause of NaN INTRODUCTION:** S04 Winter/Butterworth zero-phase filter
boundary effects on certain signal characteristics. Not yet investigated mechanically.

**Implication:** The MUB-NB06 NaN gate is reacting to S04-introduced NaN, NOT
upstream artifacts. Fixing the gate (post-Minimal-v1) requires understanding why
S04 introduces NaN. A follow-up MUB on S04 boundary handling may be warranted.

---

## 1. Affected Method

- **Function:** NB06 `notebooks/06_ultimate_kinematics.ipynb` Cell 7 — `pos_cols` construction
- **File:** `notebooks/06_ultimate_kinematics.ipynb`
- **Pipeline stage:** S06 (kinematics master parquet write)
- **Current ticket:** None — pre-Batch-1 finding

---

## 2. Current Behavior

NB06 Cell 7 builds the list of segments that receive linear kinematics columns with this filter:

```python
pos_cols = [c for c in df_in.columns
            if c.endswith(('__px', '__py', '__pz'))
            and df_in[c].notna().all()]   # hard NaN gate — per axis column
```

**Effect:** If a position axis column contains even **one NaN frame** out of tens of thousands, that joint's entire axis is excluded from `pos_cols`. This silently drops the following 5 derived columns for that joint+axis combination:

- `{joint}__lin_rel_p{axis}`
- `{joint}__lin_vel_rel_{axis}`
- `{joint}__lin_vel_rel_mag`  ← shared magnitude column, dropped if ANY axis fails
- `{joint}__lin_acc_rel_{axis}`
- `{joint}__lin_acc_rel_mag`  ← same

The dropped columns produce **no warning, no log entry, no field in `validation_report.json`, no flag in the parquet metadata.** They simply do not appear in `kinematics_master.parquet`.

---

## 3. Evidence Triggering Concern

- [x] Code inspection (NB06 Cell 7 — confirmed)
- [x] Downstream feature distortion (WBCoM, path length, linear feature reliability affected)
- [x] Regression diff (different column counts across sessions — 179 vs 189 vs 209 LIN_KINE cols)

### Empirical observations on 4 Dev Set sessions

| Session | NaN source | Joints affected | Axis lost | Cols silently dropped |
|---------|-----------|----------------|-----------|----------------------|
| 651_T1_P1_R1 | `__py` NaN in 6 joints | Head (34), Neck (36), LeftArm (17), RightArm (4), LeftShoulder (26), RightShoulder (25) | Y-axis | 30 cols |
| 651_T2_P1_R1 | `__px` NaN in 4 joints | Hips (9), Spine (9), LeftUpLeg (5), RightUpLeg (8) | X-axis | 20 cols |
| 671_T1_P2_R1 | None | — | — | 0 cols dropped |
| 671_T3_P2_R1 | None | — | — | 0 cols dropped |

---

## 4. Issue Type

- [x] Logging deficiency (no warning when columns are silently dropped)
- [x] Validation deficiency (no test for column count consistency across sessions)
- [x] Methodological limitation (1 NaN out of 32,000 frames = 100% column loss for that axis)
- [x] Downstream feature distortion (WBCoM missing key segments; path length = 0 for affected joints)

---

## 5. Relevant Scientific / Technical Support

- **Gonabadi et al. (2022)** — nonlinear features sensitive to gap location; per `REFERENCE_GUARDRAILS_FOR_PHASE13.md`: "gap duration, gap location, and the interpolation method used must be strictly tracked"
- **Ticket 009** (planned) — will add artifact/gap segment logging to S02; but the NaN that reaches S06 may survive S02 interpolation (e.g. if it was introduced at S04 filtering boundary)
- **ACTIVE_METHOD_REVIEW_PROTOCOL.md §5** — any finding causing downstream feature distortion requires a Methodology Upgrade Brief (this document)

---

## 6. Risks of Keeping Current Method

1. **Silent schema divergence:** ML training code assuming a fixed set of linear kinematics columns will silently fail or produce wrong features for sessions with any positional NaN.
2. **WBCoM undercount:** `compute_whole_body_com()` uses `__lin_rel_p*` columns; missing Hips/Spine/LeftUpLeg/RightUpLeg makes CoM computation incorrect for `651_T2`.
3. **Feature reliability cannot be properly computed** (Ticket 014b) without knowing which linear columns were dropped and why.
4. **Completely invisible:** no log, no sidecar field, no parquet metadata indicates that columns were dropped.

---

## 7. Risks of Changing Method

- Changing the gate logic (e.g. to interpolate NaN before computing, or to use a fractional threshold) would change derived feature values across ALL sessions → full PARQUET_REGEN.
- Could introduce new boundary artefacts if NaN interpolation is incorrect.
- Would require new synthetic tests and golden baseline re-lock.
- Touches NB06, which is the most complex notebook in the pipeline.

---

## 8. Candidate Alternatives

| Option | Description | Blast radius | Recommendation |
|--------|-------------|-------------|----------------|
| **A — Log only (Minimal v1)** | Add a WARNING log and a sidecar field listing dropped columns whenever the gate fires. No gate change. | LOCAL | **Implement now within Ticket 009 or a dedicated logging pass** |
| **B — Fractional NaN threshold** | Allow a segment axis into `pos_cols` if `notna()` fraction > 0.99 (i.e. < 1% NaN); fill NaN before SavGol. | PARQUET_REGEN | Candidate post-Minimal v1; requires 3 synthetic tests |
| **C — Per-axis interpolate-then-compute** | Fill NaN with linear interpolation before computing `pos_cols`; always produce all columns. | PARQUET_REGEN | Same as B; stronger guarantee |
| **D — Status quo, document only** | Accept variable column counts; document in feature_reliability_table.csv (Ticket 014b). | None | Acceptable only if logging is added (Option A in parallel) |

---

## 9. Required Tests Before Any Upgrade (Options B or C)

- Unit: synthetic joint with 1% random NaN → verify `lin_rel_py` is still produced
- Unit: verify NaN-filled derivative does not produce spike at fill boundary
- Synthetic: WBCoM with vs without missing Hips segment — verify mass redistribution works
- Regression: full 14-session run; document before/after column counts and WBCoM values
- Feature drift: `lin_vel_rel_mag` values for Hips across all sessions (expect near-zero for root)

---

## 10. Expected Output Impact (if gate changed)

- `kinematics_master.parquet`: +20–30 cols for affected sessions (consistent with 671 sessions)
- Column count would be 807 for all sessions (uniform schema)
- WBCoM values for sessions with previously-missing Hips/Spine may change
- Golden baselines must be re-locked

---

## 11. Recommendation

**Implement Option A immediately (within the logging scope of Ticket 009 or the Ticket 007b sidecar additions) — without changing the gate logic.**

Specifically: whenever a column is excluded from `pos_cols` by the NaN gate, write to `validation_report.json` a `lin_kine_dropped_columns` field listing: joint name, axis, NaN count, and NaN fraction.

Defer Options B/C to post-Minimal v1 as a separate approved ticket requiring full regression and synthetic validation.

---

## 12. User Decision Needed

> **Decision:** Should Option A (logging of dropped columns) be added to the scope of Ticket 009 (S02 artifact/gap logging) or Ticket 007b (validation_report.json sidecar additions), or should it be a new ticket? No gate change is proposed. The logging addition is `LOCAL` blast radius and does not affect parquet values.

**Until this decision is made:** Batch 1 (Tickets 005, 006, 007a, 007b) may proceed as planned. None of those tickets touch the linear kinematics NaN gate. The variable column count across sessions is a pre-existing condition that will be surfaced to feature_reliability_table.csv (Ticket 014b).
