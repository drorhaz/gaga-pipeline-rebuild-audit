# S-04 Filtering Stage Audit

**Phase:** 4
**Date:** 2026-05-14
**Agent:** Claude Sonnet 4.6 — Audit Mode (Read-only)
**Stage:** Step 04 — 3-Stage Signal Cleaning (`src/filtering.py`, `notebooks/04_filtering.ipynb`)
**Evidence base:** 9 `__filtering_summary.json` artifacts (6 P2 sessions + 3 P1 sessions, subject 671, T1/T2/T3)
**Priority questions answered:** Q-S04a (dance band delta distribution), Q-S04b (noise band attenuation), Q-S04c (adaptive correction iterations needed)

---

## 1. Evidence scope

| Dimension | Coverage |
|-----------|---------|
| Sessions analyzed | 9 total: P2 × 6 (T1R1, T1R2, T2R1, T2R2, T3R1, T3R2), P1 × 3 (T1R1, T2R1, T3R1) |
| Subject | 671 only |
| Source files read | `derivatives/step_04_filtering/*__filtering_summary.json`, `src/filtering.py` lines 46–135, 2386–2600 |
| Config confirmed | `filtering.method = 3_stage`, `velocity_limit = 5000 mm/s`, `zscore_threshold = 5.0`, `hampel_window = 5`, `hampel_n_sigma = 3.0`, `winter_fmin = 1.0`, `winter_fmax = 20.0` |

---

## 2. Finding F1 — PSD oversmoothing verdict mechanism is structurally broken

**Severity: Critical (Verdict System Bug)**
**Source: `src/filtering.py` line 2478**
**Confidence: High**

```python
# filtering.py line 2478 — actual code
if max_dance_loss < -3.0:       # max_dance_loss = np.min(delta_dB[dance_mask])
    verdict = "REVIEW_OVERSMOOTHING"
```

`max_dance_loss` is defined as `np.min(delta_dB[dance_mask])` — the **worst single-frequency attenuation** anywhere in the 1–13 Hz dance band. `delta_dB` is computed as `10 * log10(psd_filtered / psd_original)`.

**Why this is structurally broken:**
Any low-pass filter with cutoff fc < 13 Hz will attenuate frequencies near its cutoff. A 2nd-order Butterworth at fc = 12 Hz is at its -3 dB point at exactly 12 Hz, and attenuates ~-5 dB at 13 Hz. This means:
- A hand column at fc = 12 Hz will always have `max_dance_loss ≈ -7 dB` (at the 12–13 Hz bins).
- The -3 dB threshold will ALWAYS be triggered for every column in every session, because the dance band (1–13 Hz) includes frequencies at and above every column's cutoff.

**Observed consequence:**
- 10/57 columns in the reference session have `mean_dance_band_delta_dB > -3.0 dB` (acceptable) yet are still flagged as `REVIEW_OVERSMOOTHING` because their `max_dance_band_loss_dB` is -7.0 to -10.3 dB.
- These columns are the hand columns (fc=12 Hz, mean_delta ≈ -1.87 dB) and some foot columns (fc ≈ 10.2 Hz, mean_delta ≈ -2.9 dB).
- Session verdict `REVIEW_OVERSMOOTHING` is therefore guaranteed for every session regardless of filter quality.

**False-positive columns per session (reference):**

| Column | fc (Hz) | mean_dance_delta | max_loss_dB | Should verdict be? |
|--------|---------|-----------------|-------------|-------------------|
| RightHand__px/y/z | 12.0 | -1.87 to -1.88 | -7.10 | PASS — filter is working correctly |
| LeftHand__px/y/z | 12.0 | -1.85 to -1.87 | -6.95 to -7.01 | PASS |
| RightFoot__px/y/z | 10.4 | -2.91 to -2.94 | -9.98 to -10.30 | PASS (borderline) |
| LeftFoot__px | 10.4 | -2.93 | -10.23 | PASS (borderline) |

**Correct criterion** (per Phase 3 target skeleton design):
```python
if dance_delta < -3.0:       # use MEAN over dance band, not single-frequency minimum
    verdict = "REVIEW_OVERSMOOTHING"
```

**Impact of criterion fix:**
- n_oversmoothing would be reduced from 57/57 → approximately 47/57 per session.
- Session verdict would remain `REVIEW_OVERSMOOTHING` (47 columns still genuinely oversmoothed) — but the source of the problem becomes correctly identified as the trunk and proximal joints, not the correctly-filtered hands.
- This change does NOT suppress a real problem — the trunk/proximal oversmoothing is genuine. It removes false positives for distal joints.

**Decision: `REDESIGN_CANDIDATE`** (verdict criterion fix — change one line in `filtering.py`)

---

## 3. Finding F2 — Dance band oversmoothing is universal, session-invariant, and region-stratified

**Severity: High**
**Q-S04a answered: YES, oversmoothing is consistent across all sessions**
**Confidence: High**

### 3.1 Session-level PSD summary (all 9 sessions)

| Session | Proto | TP | Mean dance Δ (dB) | Noise att. (dB) | Verdict | N_over/57 | Worst col | Worst dB |
|---------|-------|----|--------------------|-----------------|---------|-----------|-----------|---------|
| 671_T1_P1_R1 | P1 | T1 | -5.52 | 45.49 | REVIEW_OVERSMOOTHING | 56/57 | Spine__py | -27.07 |
| 671_T1_P2_R1 | P2 | T1 | -5.51 | 44.83 | REVIEW_OVERSMOOTHING | 57/57 | Hips__py | -27.19 |
| 671_T1_P2_R2 | P2 | T1 | -5.41 | 44.09 | REVIEW_OVERSMOOTHING | 57/57 | Hips__py | -27.62 |
| 671_T2_P1_R1 | P1 | T2 | -5.59 | 42.78 | REVIEW_OVERSMOOTHING | 56/57 | Spine__py | -26.77 |
| 671_T2_P2_R1 | P2 | T2 | -5.39 | 43.16 | REVIEW_OVERSMOOTHING | 57/57 | Spine1__py | -24.73 |
| 671_T2_P2_R2 | P2 | T2 | -5.35 | 42.66 | REVIEW_OVERSMOOTHING | 57/57 | Hips__py | -27.34 |
| 671_T3_P1_R1 | P1 | T3 | -5.49 | 42.04 | REVIEW_OVERSMOOTHING | 57/57 | Hips__py | -26.82 |
| 671_T3_P2_R1 | P2 | T3 | -5.40 | 41.66 | REVIEW_OVERSMOOTHING | 57/57 | Hips__py | -26.66 |
| 671_T3_P2_R2 | P2 | T3 | -5.33 | 40.78 | REVIEW_OVERSMOOTHING | 57/57 | Hips__py | -24.46 |

**P2-only dance band delta:** mean = -5.40 dB, range = -5.51 to -5.33 dB, std ≈ 0.06 dB.

**Finding:** The dance band delta is near-constant across all 9 sessions and both protocols. The range is only 0.26 dB wide (−5.33 to −5.59 dB). This is not a session-dependent signal quality issue — it is a **structural consequence of the fixed regional cutoff values** in `BODY_REGIONS`.

### 3.2 Per-region dance band analysis (reference session: 671_T3_P2_R1)

| Body region | fc (Hz) | Mean dance Δ (dB) | Mean max-loss (dB) | n cols | Versus -3 dB criterion |
|-------------|---------|-------------------|--------------------|--------|----------------------|
| trunk | 6.0 | **-9.67** | -23.46 | 9 | **FAIL — severely oversmoothed** |
| head | 8.0 | -5.55 | -16.41 | 6 | **FAIL** |
| upper_prox (incl. forearms†) | 8.0 | -5.68 | -16.77 | 12 | **FAIL** |
| lower_prox | 8.0 | -5.91 | -17.76 | 6 | **FAIL** |
| lower_dist (feet/shins) | 10.2 | -3.19 | -10.90 | 12 | BORDERLINE (−3.19 vs threshold −3.0) |
| upper_dist (hands only†) | 12.0 | **-1.87** | -12.06 | 6 | **PASS — correctly filtered** |

†See Finding F4 (forearm classification bug) for details on the column assignment.

**Cross-session trunk stability:**

| Session | Trunk mean dance Δ |
|---------|------------------|
| P1 T1 | -9.69 dB |
| P2 T1 | -10.04 dB (R1), -9.51 dB (R2) |
| P1 T2 | -10.22 dB |
| P2 T2 | -9.33 dB (R1), -9.42 dB (R2) |
| P1 T3 | -9.71 dB |
| P2 T3 | -9.67 dB (R1), -9.42 dB (R2) |

Range: -9.33 to -10.22 dB. **Standard deviation < 0.3 dB. Completely invariant.**

**Root cause:** The `BODY_REGIONS` definition in `filtering.py:62` sets `trunk['fixed_cutoff'] = 6` with the explicit rationale `"6 Hz based on gait literature, conservative for trunk stability"` (Winter 2009). Winter (2009) recommends 6 Hz for clinical gait — a periodic, low-frequency activity with minimal content above 4–5 Hz. Gaga dance has substantial trunk content at 6–13 Hz (torso rotations, spinal undulations, percussive rebounds). The 6 Hz gait-based floor is deeply inappropriate for this context.

**Assessment:** The oversmoothing is not a filter algorithm failure — the Butterworth/Winter/Smart Bias pipeline is implemented correctly. The problem is the fixed cutoff floor value for the trunk region. The adaptive correction loop (Phase 3 target design) addresses this directly.

---

## 4. Finding F3 — Noise band attenuation: PASS (Q-S04b)

**Severity: None**
**Q-S04b answered: Noise band attenuation exceeds the 95% threshold by 3×**
**Confidence: High**

The noise band (20–50 Hz) attenuation requirement is ≥95% (≡ ≥13.0 dB).

| Session | Mean noise att. (dB) | n_noise_residual | Verdict |
|---------|---------------------|-----------------|---------|
| P1 T1 | 45.49 | 0 | PASS |
| P2 T1 (R1) | 44.83 | 0 | PASS |
| P2 T1 (R2) | 44.09 | 0 | PASS |
| P1 T2 | 42.78 | 0 | PASS |
| P2 T2 (R1) | 43.16 | 0 | PASS |
| P2 T2 (R2) | 42.66 | 0 | PASS |
| P1 T3 | 42.04 | 0 | PASS |
| P2 T3 (R1) | 41.66 | 0 | PASS |
| P2 T3 (R2) | 40.78 | 0 | PASS |

**All 9 sessions pass by a factor of 3× (40–45 dB achieved vs 13 dB required).**

`n_noise_residual = 0` in all sessions — zero columns with residual noise. The Butterworth filter is performing its core noise rejection function correctly. This is not a concern.

---

## 5. Finding F4 — Forearm classification bug: 8 Hz instead of 12 Hz

**Severity: Medium**
**Source: `src/filtering.py` lines 71–83, 102–135**
**Confidence: High**

**Spec (PIPELINE_PROCESSING_README.md §6.3):** "Upper Distal: Forearm, Hand, Fingers → 12 Hz — Fast hand flicks (Gaga dance)"

**Implementation:** `BODY_REGIONS` defines:
```python
'upper_proximal': {
    'patterns': ['Shoulder', 'Clavicle', 'Scapula', 'UpperArm', 'Arm'],  # ← 'Arm' matches 'ForeArm'
    'fixed_cutoff': 8, ...
}
'upper_distal': {
    'patterns': ['Elbow', 'Forearm', 'ForeArm', 'Wrist', 'Hand', ...],   # ← never reached for ForeArm
    'fixed_cutoff': 12, ...
}
```

`classify_marker_region()` iterates regions in insertion order (Python 3.7+ guaranteed dict order). For `'RightForeArm'`:
1. Checks `trunk` patterns → no match
2. Checks `head` patterns → no match
3. Checks `upper_proximal` patterns → `'Arm' in 'RightForeArm'.lower()` = **True** → **returns 'upper_proximal' immediately**
4. Never reaches `upper_distal`

**Result:** Both `LeftForeArm` and `RightForeArm` are assigned `fixed_cutoff = 8 Hz` instead of the specified `12 Hz`. This is confirmed by `per_joint_cutoffs` in every filtering summary: `RightForeArm__px/y/z: 8.0 Hz`.

**Impact:**
- 6 forearm columns (RightForeArm × 3, LeftForeArm × 3) filtered at 8 Hz instead of 12 Hz.
- At 8 Hz: mean_dance_delta ≈ -5.7 dB (oversmoothed).
- At 12 Hz (correct): mean_dance_delta would be ≈ -1.9 dB (like hands — correctly filtered).
- The adaptive correction loop (Phase 3 target) would correct this, but so would fixing the classification.

**Fix:** Change `'Arm'` to `'UpperArm'` in the `upper_proximal` patterns list:
```python
'upper_proximal': {
    'patterns': ['Shoulder', 'Clavicle', 'Scapula', 'UpperArm'],  # remove bare 'Arm'
```
This prevents the substring match from catching 'ForeArm' before 'upper_distal' can. This is a one-word code fix. **Note: Also requires regression check on 'RightArm', 'LeftArm' — these use the 'Arm' node name in the canonical schema, not 'UpperArm'. Need to add `'RightArm'`, `'LeftArm'` or simply `'Arm__'` (with trailing separator) to `upper_proximal` patterns to maintain correct classification for upper arm nodes.**

**Correct fix:**
```python
'upper_proximal': {
    'patterns': ['Shoulder', 'Clavicle', 'Scapula', 'UpperArm', 'Arm__'],  # 'Arm__' won't match 'ForeArm__'
```
Or more robustly, switch to exact joint-name matching rather than substring matching.

**Decision:** `LOCAL_REFACTOR` (pattern fix in `BODY_REGIONS`)

---

## 6. Finding F5 — Adaptive correction iteration estimates (Q-S04c)

**Severity: Informational (design input)**
**Q-S04c answered**

The Phase 3 target design proposes a correction loop that increases fc in +0.5 Hz steps until `mean_dance_band_delta_dB ≥ -3.0 dB`. Based on the per-region dance delta data and the empirical relationship between fc and dance delta observed in the data:

| Region | Current fc (Hz) | Mean dance Δ | Target fc (Hz) | Estimated iterations |
|--------|----------------|-------------|----------------|---------------------|
| trunk (Hips, Spine, Spine1) | 6.0 | -9.67 | ~10.0 | **~8 iterations** |
| head (Head, Neck) | 8.0 | -5.55 | ~10.0 | ~4 iterations |
| upper_prox (shoulders, arms) | 8.0 | -5.68 | ~10.0 | ~4 iterations |
| lower_prox (thighs) | 8.0 | -5.91 | ~10.0 | ~4 iterations |
| lower_dist (shins, feet) | 10.2 | -3.19 | ~10.5 | ~1 iteration |
| upper_dist/forearms† | 8.0 | -5.7 | ~10.0 | ~4 iterations |
| hands | 12.0 | -1.87 | — | **0 iterations (already passing)** |

†After forearm classification fix. With current bug, forearms are in upper_prox category.

**Empirical reference points used:**
- fc=6 Hz (trunk data) → mean_dance_delta ≈ -9.67 dB
- fc=8 Hz (head/prox data) → mean_dance_delta ≈ -5.6 dB
- fc=10.2 Hz (lower_distal data) → mean_dance_delta ≈ -3.2 dB
- fc=12 Hz (hands data) → mean_dance_delta ≈ -1.87 dB

**Key insight for loop design:** The -3 dB threshold is met at approximately fc = 10 Hz for most regions. The proposed correction ceiling (`fixed_cutoff + 6 Hz`, i.e., trunk: 6→12 Hz max) provides sufficient headroom. All regions would converge within 10 iterations at 0.5 Hz/step.

**[RECONSIDER_LATER] Q-ADP (confirmed from this audit):** The adaptive loop target fc of ~10 Hz for trunk joints represents a significant change from the current 6 Hz. This raises the trunk cutoff by +4 Hz. At the target fc=10 Hz for trunk, frequencies up to ~9 Hz will be largely preserved and 10–13 Hz content will see -3 to -15 dB attenuation. The biomechanical question — whether trunk Gaga dance content above 9 Hz should be preserved — remains open. Per the [RECONSIDER_LATER] tag, this must be validated against high-velocity session frequency analysis before implementing as a permanent default.

---

## 7. Finding F6 — Stage 1 Z-score spikes: P1 vs P2 disparity

**Severity: Medium (Q-S02 confirmation)**
**Confidence: High**

### Stage 1 + Stage 2 counts across all sessions

| Session | Proto | Stage1 frames | Stage1 % | Vel spikes | Z-score spikes | Stage2 outliers | Stage2 % |
|---------|-------|--------------|---------|-----------|---------------|----------------|---------|
| T1_P1_R1 | P1 | 7,453 | 0.427% | 3 | 6,231 | 5,416 | 0.311% |
| T1_P2_R1 | P2 | 1,075 | 0.112% | 4 | 971 | 1,163 | 0.121% |
| T1_P2_R2 | P2 | 1,350 | 0.134% | 17 | 1,180 | 1,046 | 0.104% |
| T2_P1_R1 | P1 | 8,676 | 0.501% | 0 | 7,578 | 4,270 | 0.247% |
| T2_P2_R1 | P2 | 1,443 | 0.126% | 5 | 1,306 | 838 | 0.073% |
| T2_P2_R2 | P2 | 1,862 | 0.157% | 0 | 1,687 | 974 | 0.082% |
| T3_P1_R1 | P1 | 9,880 | 0.547% | 1 | 8,840 | 6,156 | 0.341% |
| T3_P2_R1 | P2 | 1,447 | 0.117% | 19 | 1,320 | 1,142 | 0.092% |
| T3_P2_R2 | P2 | 1,852 | 0.146% | 23 | 1,669 | 1,433 | 0.113% |

**Critical observation:** P1 sessions have 5–8× more Stage 1 Z-score spikes than P2 (6,231–8,840 vs 971–1,687). Velocity spikes (clearly hardware tracking failures) remain low in both protocols (0–23 per session). P1 Stage 1 modification rate: 0.43–0.55%. P2: 0.11–0.16%.

**P1 sessions also progressively accumulate more artifacts**: T1=7,453, T2=8,676, T3=9,880 — a +32% increase from T1 to T3 within the same protocol. This is a session-order effect within P1 that has no obvious physical explanation (different movement patterns at different timepoints?) and warrants investigation.

**Interpretation of Z-score disparity:**
The Z-score threshold (5σ) is computed from the session-wide velocity distribution. If P1 involves sustained or repeated fast movements (high-velocity protocol), the velocity distribution may be bimodal — low-velocity periods and high-velocity periods. A 5σ threshold computed on the mixed distribution would have a lower baseline than the P1 activity warrants, incorrectly flagging genuine P1 velocity bursts as artifacts.

This confirms the Q-S02 concern from Phase 3. The velocity spike count (0–3 for P1) confirms hardware artifact rate is minimal — the Z-score spikes are likely genuine P1 movement, not tracking failures.

**Decision for Stage 1 Z-score:** `REDESIGN_CANDIDATE` (pending Stage 02 audit in Phase 4). The Phase 3 proposed two-tier flagging (hardware failure → immediate NaN; Z-score exceedance → SUSPICIOUS flag only) should be prioritized for P1 data integrity.

---

## 8. Finding F7 — Winter method distribution: Smart Bias dominates

**Severity: Informational**
**Confidence: High**

Per filtering summary: `method_distribution: smart_bias = 48, diminishing_returns = 9` (84% / 16%).

Only 9/57 columns use Winter's diminishing-returns criterion as the primary cutoff selector. The remaining 48 columns are set entirely by the Smart Bias floor — meaning the Winter residual analysis serves primarily as a validation check, not as an adaptive cutoff selector. The pipeline's "adaptive per-joint Winter filter" is in practice a **fixed regional-floor filter with one data-driven component for 16% of columns**.

This is not a bug, but it explains why Winter cutoffs are near-identical across all 9 sessions (min=6.0, max=12.0, mean=8.53–8.60 Hz with std=1.70–1.77). The Smart Bias architecture correctly prevents Winter from selecting sub-biomechanical cutoffs.

---

## 9. Finding F8 — Stage 1 gap guard: 6 unreliable gaps in lower limb columns

**Severity: Low**
**Confidence: High**

Reference session (671_T3_P2_R1):
```
stage1_gap_guard:
    max_gap_across_all_cols: 38 frames (= 317 ms at 120 Hz)
    total_unreliable_gaps: 6
    cols_with_unreliable_gaps: ['LeftLeg__py', 'RightLeg__px', 'RightFoot__px', 'LeftFoot__px', 'LeftFoot__py']
```

Five lower-limb columns have gaps up to 38 frames (317 ms) where Stage 1 PCHIP interpolation is flagged as "unreliable." The max gap limit is `max_gap_pos_sec = 1.0s` (120 frames), so all gaps are within the allowed range. However, PCHIP interpolation over 317 ms in lower limbs (which can undergo complex accelerations during jumps or foot strikes) may produce inaccurate trajectories.

The `stage1_gap_guard` logging exists — this is `KEEP_LOG_QC` as-is. The 6 unreliable gaps are confined to the feet/shins, consistent with higher foot tracking difficulty during dance.

---

## 10. Finding F9 — Winter_fmax config vs code discrepancy

**Severity: Low — needs verification**
**Confidence: Medium**

`filtering.py` line ~101: `WINTER_FMAX = 16`
`config_v1.yaml` key: `filtering.winter_fmax = 20.0`
`filtering_summary.json`: `filter_params.winter_fmax: 20.0`

The runtime value in the summary (20.0 Hz) exceeds the hardcoded constant (16 Hz). The config key likely overrides the constant at runtime. This should be verified in Phase 4 Stage 02/04 code audit: which value actually governs the Winter analysis search range? If the 20 Hz config is active, the Winter analysis searches up to 20 Hz, potentially selecting sub-optimal cutoffs in the 16–20 Hz range. The comment in code says "expanded from 12 for Gaga" — the runtime 20 Hz config is even more expanded.

---

## 11. Summary decision matrix

| Finding | Component | Severity | Decision | Confidence |
|---------|-----------|----------|---------|------------|
| F1 | `filtering.py:2478` — PSD verdict criterion (max vs mean) | **Critical (verdict bug)** | `LOCAL_REFACTOR` (one line) | High |
| F2 | Trunk/proximal oversmoothing (real) — root cause: gait-era cutoff floors | High | `REDESIGN_CANDIDATE` (adaptive loop from Phase 3) | High |
| F3 | Noise band attenuation — PASS | None | `KEEP_AS_IS` | High |
| F4 | Forearm classification bug (`'Arm'` substring match) | Medium | `LOCAL_REFACTOR` (pattern fix) | High |
| F5 | Adaptive correction iterations — trunk needs ~8 iters, all within budget | Informational | Confirms Phase 3 design is feasible | High |
| F6 | Stage 1 Z-score: P1 sessions 5–8× more spikes than P2 | Medium | `REDESIGN_CANDIDATE` (two-tier flag) — DEFER to Stage 02 audit | High |
| F7 | Winter smart_bias dominates (84%) — "adaptive" filter is mostly fixed | Informational | `KEEP_DOCUMENT` | High |
| F8 | Stage 1 gap guard: 6 unreliable lower-limb gaps (317 ms) | Low | `KEEP_LOG_QC` | High |
| F9 | winter_fmax: code=16 Hz vs config/runtime=20 Hz | Low | `UNKNOWN_NEEDS_EVIDENCE` — verify in code audit | Medium |

---

## 12. Answers to Phase 4 priority questions

### Q-S04a: Is dance band oversmoothing consistent across all P2 sessions?

**YES. Unambiguously.** P2 dance band delta: mean = -5.40 dB, range = -5.33 to -5.51 dB, std ≈ 0.06 dB across 6 sessions. Trunk delta is -9.33 to -10.22 dB across all 9 sessions. This is a structural property of the pipeline, not session noise or subject variability. The root cause is the `BODY_REGIONS['trunk']['fixed_cutoff'] = 6` Hz floor value inherited from Winter (2009) clinical gait literature.

### Q-S04b: Is the noise band attenuation meeting the ≥95% threshold?

**YES, by 3×.** All 9 sessions achieve 40–45 dB mean noise attenuation. Threshold requires only 13 dB (for 95%). `n_noise_residual = 0` in all sessions — no columns show noise residual. The noise rejection function of the filter is working perfectly. This is not a concern.

### Q-S04c: How many adaptive correction iterations would trunk joints need?

**~8 iterations (6.0 → 10.0 Hz at +0.5 Hz/step).** Empirically derived from the per-region dance delta data: trunk at 6 Hz gives -9.67 dB; lower_distal at 10.2 Hz gives -3.19 dB (near threshold). Target cutoff for trunk ≈ 10 Hz. All regions converge within the proposed 10-iteration budget. Hands (fc=12 Hz, mean_delta=-1.87 dB) require 0 iterations — already passing. The Phase 3 adaptive loop design is validated as feasible by this evidence.

---

## 13. Additional finding: The PSD audit verdict in NB04 must be re-evaluated

The notebook NB04 printed: `PSD audit = REVIEW_OVERSMOOTHING, dance band delta = -5.40 dB, 57/57 columns flagged`. As now established:
- The **57/57 flag count is a false positive for 10 columns** (hands + some feet) — caused by the max_dance_loss criterion bug (F1).
- The **-5.40 dB session-level mean** includes the correctly-filtered hands, pulling the mean upward. The true oversmoothing is worse: trunk mean = -9.67 dB, head/proximal mean = -5.6 to -5.9 dB.
- Correcting the verdict criterion (F1) would show: **47/57 columns genuinely oversmoothed, 10 columns correctly filtered**.

This does not change the fact that the pipeline has a real and significant oversmoothing problem in trunk and proximal joints. It means the problem is more precisely located and slightly more severe than the session-level -5.40 dB headline suggests.

---

*End of S-04 Filtering Stage Audit*
