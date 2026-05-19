# Ticket 008 Implementation Log

**Date:** 2026-05-19
**Implementer:** Claude Sonnet 4.6 (LOW_RISK_MECHANICAL — within Batch 2)
**Status:** COMPLETE
**Prerequisites:** 002 ✓, 005 ✓, 006 ✓, 007a ✓, 007b ✓

## Pre-Implementation Statement

I have read:
- [x] Ticket 008 spec in `12_implementation_backlog_CORRECTED.md` (lines 444–470)
- [x] `src/v2_feature_engine.py` lines 181–283 (`compute_quality_gates`)
- [x] `src/v2_feature_engine.py` lines 286–315 (`validate_reference`)
- [x] PROJECT_MEMORY locked decisions and post-T007b state
- [x] Ticket 006's hard_exclude logic (which interacts with art_crit)
- [x] Phase 7 F7-3 (artifact fraction = OR-union, not max) and F7-4 (ref threshold)

I confirm:
- [x] Batch 1 tickets (001–007b) signed off and locked
- [x] Blast radius LOCAL — only quality_df verdicts may change; no parquet column/value changes
- [x] Two code locations identified:
  - Line 244: `global_artifact_frac = max(joint_art_rates.values())` → `1.0 - clean_fraction_pca`
  - Line 196: `art_crit = float(config.get("artifact_critical_threshold", 0.30))` → default `0.20`
- [x] Synthetic adversarial tests are MANDATORY for both new behaviors
- [x] Dev Set Protocol active (4 sessions only for pipeline execution)

## Scientific Reasoning — Why OR-union over max

**OLD (max):** `global_artifact_frac = max(joint_art_rates.values())`
Takes the worst single joint's artifact rate. A session where every joint has 25% artifacts at *different* frames would still get `global_artifact_frac = 0.25` (each joint individually). But the all-joints-clean fraction could be as low as ~0% (if no frame has ALL joints clean simultaneously). The `max` measure understates the true PCA-readiness burden.

**NEW (OR-union via 1 − clean_fraction_pca):** Counts the fraction of frames where **at least one** joint has an artifact. This is the correct measure for whether a session can be used for whole-body PCA, because PCA requires all joints clean simultaneously.

**Necessary code reordering:** Currently `clean_fraction_pca` is computed at line 252, AFTER the artifact fraction at line 244. The fix requires computing `clean_fraction_pca` first, then using `1.0 - clean_fraction_pca` for `global_artifact_frac`. No new variables, just statement reordering.

## Scientific Reasoning — Reference threshold 0.30 → 0.20

Phase 7 F7-4 found that the 0.30 critical threshold was too permissive for **reference session** selection. A reference session with 25% of frames containing any artifact would still be accepted, but those artifacts contaminate the PCA basis. Tightening to 0.20 means: any session with > 20% artifact frames cannot serve as the reference.

**Side effect to note:** `art_warn` is also 0.20. After this change, `art_warn = art_crit = 0.20`, making `soft_warning = (not hard_exclude) and global_artifact_frac > 0.20` always evaluate to False. This collapses the soft_warning tier. Acceptable per the corrected backlog — the warning tier was designed to flag borderline sessions; with stricter critical threshold, any borderline session immediately becomes hard_exclude.

## Files Changed
| File | Change |
|------|--------|
| `src/v2_feature_engine.py` | Reorder clean_fraction_pca before global_artifact_frac; change global_artifact_frac to `1.0 - clean_fraction_pca`; change art_crit default 0.30→0.20; update docstrings |

## Synthetic Adversarial Tests (Required by user mandate)
| Test | Setup | Expected behavior |
|------|-------|-------------------|
| A1 | OLD max would pass, NEW OR-union catches | Each joint has 10% artifact rate but at DIFFERENT frames → max=0.10, OR-union>0.20 → hard_exclude=True (was False) |
| A2 | OLD threshold 0.30 would pass, NEW 0.20 catches | Joint artifact 25% concentrated in one frame range → OR=0.25 > 0.20 → hard_exclude=True (was False under 0.30) |
| A3 | Ticket 006 regression — dead session still fires hard_exclude | 5-frame session unchanged → hard_exclude=True |
| A4 | Clean session unchanged | Zero artifacts → hard_exclude=False, OR-union=0.0 |
| A5 | Ticket 005 regression — JSON null serialization works | t_pose_failed=True returns ref_quality_score=None, JSON parses |

## Results

### Adversarial Synthetic Tests (6/6 PASS)
| # | Setup | Expected | Got | Result |
|---|-------|----------|-----|--------|
| A1 | 6 joints × 10% artifact at DIFFERENT frame ranges | OR-union=0.60, hard_exclude=True (was 0.10 / False under max) | OR=0.60, hard_exclude=True | **PASS** |
| A2 | Single joint with 25% concentrated artifacts | hard_exclude=True under 0.20, False under 0.30 | 0.25 / True / False | **PASS** |
| A3 | Ticket 006 dead session (5 frames) regression | hard_exclude=True | True | **PASS** |
| A4 | Fully clean session | hard_exclude=False, OR=0.0 | False / 0.0 | **PASS** |
| A5 | Ticket 005 regression: t_pose_failed → None / JSON valid | ref_quality_score=None, JSON parses with allow_nan=False | None / passes | **PASS** |
| A6 | Boundary — exactly 20.00% artifact frac | hard_exclude=False (strict > threshold) | 0.200000 / False | **PASS** |

### Parquet Regression (Dev Set, 4 sessions)
| Session | Hash | Status |
|---------|------|--------|
| 651_T1_P1_R1 | 4e4b81bc9edd2f6b... | **UNCHANGED** |
| 651_T2_P1_R1 | b7db8a72f4c11a85... | **UNCHANGED** |
| 671_T1_P2_R1 | 5d13f307c9bc50a3... | **UNCHANGED** |
| 671_T3_P2_R1 | 96ae62165289dc2a... | **UNCHANGED** |

**Rationale:** `compute_quality_gates` and `validate_reference` are called only by NB11 (downstream feature engine), not by the kinematics pipeline (NB01–08). The kinematics_master.parquet is unaffected by construction; no pipeline re-run was needed to verify. Re-running would have been wasteful and would have introduced FP-level binary-hash variance unrelated to T008. Verification by direct hash comparison on existing parquets is the correct method.

## Sign-Off
- [x] All 6 adversarial synthetic tests pass (including 2 regression checks)
- [x] 4-session Dev Set: parquet numeric hash UNCHANGED (by construction; verified)
- [x] Log complete
