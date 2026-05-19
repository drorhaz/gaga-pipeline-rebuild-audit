# 08 Fast Post-Collection QC Requirements

**Date:** 2026-05-15
**Auditor:** Phase 8 Agent (Claude Sonnet 4.6)
**Mode:** Design-only. No code changes.

**Status:** COMPLETE

---

## Purpose

The Fast Post-Collection QC script (`fast_qc.py` / `NB08_Fast_QC`) runs immediately after each motion-capture recording to determine whether the session is worth processing or must be repeated while the participant is still in the lab and the marker set is undisturbed.

This is the **earliest possible safety net** in the pipeline. It runs on the raw OptiTrack CSV export before any preprocessing, filtering, or kinematics. Its sole deliverable is an actionable verdict: the data collection team must be told **immediately** whether to re-record.

All checks in this document are grounded in concrete findings from Phases 4–7 of the audit. Each check maps to a specific pipeline risk already observed in the dataset.

---

## Non-goals

This script **must NOT**:

- Replace or replicate Steps 01–06 of the full pipeline
- Compute kinematics, angular velocities, or filtered signals
- Apply any Butterworth, PCHIP, or SLERP processing
- Produce the `kinematics_master.parquet`
- Compute scientific metrics (ATF, TM, D_eff, Gini)
- Take more than ~30 seconds on a standard laptop for a 3-minute recording

If a check requires more than a simple NumPy/pandas pass over raw data, it belongs in the full pipeline — not here.

---

## Runtime target

| Recording length | Expected runtime | Method |
|-----------------|-----------------|--------|
| 30s (minimum) | < 3 s | Pure NumPy on header + first 30s |
| 160s (typical) | < 10 s | NumPy over full raw positions + quats |
| 300s (maximum expected) | < 20 s | Same |

No SciPy, no sklearn, no filtering. Only `numpy`, `pandas`, `json`, and `pathlib`.

---

## Inputs

| Input | Description | Required? |
|-------|-------------|-----------|
| `{RUN_ID}.csv` | Raw OptiTrack Motive CSV export | **REQUIRED** |
| `config_v1.yaml` | Pipeline config (for fs_target, joint list) | OPTIONAL (use defaults if absent) |
| `{RUN_ID}.mcal` (exported calibration) | Wand error, pointer tip RMS | OPTIONAL |

The script must be callable with only the CSV path. All other inputs are optional enhancements.

---

## Outputs

### Primary output: status verdict

```text
PASS              — All hard checks passed. Safe to proceed to full pipeline.
PASS_WITH_WARNINGS — Hard checks passed; soft issues found. Proceed with caution.
FAIL              — At least one hard check failed. Re-record before participant leaves.
```

### Secondary outputs

| File | Format | Description |
|------|--------|-------------|
| `{RUN_ID}__fast_qc_report.txt` | Plain text | Human-readable per-check summary |
| `{RUN_ID}__fast_qc_result.json` | JSON | Machine-readable check catalog (see §Machine-readable JSON schema) |

Both outputs written to `qc/fast_qc/` by default.

---

## PASS / WARN / FAIL Rules

```
FAIL   if ANY Tier 1 hard check fails.
FAIL   if ANY Tier 2 critical check fails.
WARN   if ANY Tier 2 soft check flags, with all hards passing.
WARN   if ANY Tier 3 check flags, with all Tier 1 and Tier 2 hards passing.
PASS   if all checks pass (Tier 3 may have notes but no flags).
```

A `FAIL` always prints the failed check(s) first and suggests re-recording. It does **not** abort silently.

---

## Check Catalog

### Tier 1 — Raw File Checks (run on CSV path + header only)

| ID | Check | Severity | Threshold / Rule | Failure message | Maps to pipeline risk |
|----|-------|----------|-----------------|-----------------|----------------------|
| T1-01 | File exists and is non-empty | **FAIL** | File size > 0 bytes | "CSV file not found or empty" | Dead session passes pipeline |
| T1-02 | File size plausible | WARN | > 100 KB (< 100 KB suggests < 5 s of data at 120 Hz) | "File size {N} KB seems too small for a valid session" | Dead session (651_T2_P2_R2 was 5 frames) |
| T1-03 | Filename parseable | WARN | Regex matches `{subject}_{T}_{P}_{R}_` | "Cannot extract subject/timepoint/protocol/rep from filename" | Manual session registry required |
| T1-04 | CSV header contains `Frame` and `Time` columns | **FAIL** | Both columns present in row 1–6 | "Header missing Frame or Time column — invalid OptiTrack export" | Parse stage S01 would fail |
| T1-05 | **Session duration ≥ 30 seconds** | **FAIL** | `max(Time) − min(Time) >= 30.0 s` | "Session duration {N}s < 30s minimum. This is a botched recording — re-record immediately." | **USER DIRECTIVE. Dead session (651_T2_P2_R2, 0.03s) passed all 6 pipeline stages silently.** |
| T1-06 | **Frame count ≥ 3600** | **FAIL** | `max(Frame) − min(Frame) >= 3600` | "Frame count {N} < 3600 (30s × 120Hz minimum). Re-record." | Same as T1-05. Aliases duration check for CSV with missing Time. |
| T1-07 | Approximate frame rate plausible | WARN | Estimated fs from Time column within ±10% of 120 Hz | "Estimated frame rate {N} Hz deviates >10% from expected 120 Hz" | Resampling assumption; S01 Q-EXT3b |
| T1-08 | Time column monotonically increasing | **FAIL** | `all(diff(Time) > 0)` on sample of first 500 rows | "Time column is not monotonically increasing — corrupted export" | Breaks all downstream interpolation |
| T1-09 | Capture frame rate = export frame rate | WARN | If `Capture Frame Rate` and `Export Frame Rate` rows found in header, check equality | "Capture rate {A} Hz ≠ Export rate {B} Hz — downsampling occurred before pipeline" | Q-EXT3b: field not currently extracted by S01 |
| T1-10 | Export rotation type is Quaternion | WARN | Header row `Rotation Type` = `Quaternion` if present | "Rotation type is '{T}', expected Quaternion — pipeline will misinterpret rotations" | Q-EXT3b: field not currently extracted |
| T1-11 | All 19 required joint names in CSV header | **FAIL** | All names in `ALL_19_JOINTS` appear at least once in the column headers | "Missing joints: {list}. Marker set incomplete — re-marker and re-record." | S01 segments_missing_count; ATF/TM/PCA will be unavailable for missing joints |
| T1-12 | No duplicate joint columns | WARN | Each joint name appears exactly once (not twice or more) | "Duplicate columns for: {list} — possible marker ID collision" | Silent averaging / shadowing in S01 CSV parse |
| T1-13 | Calibration metadata present | WARN | `wand_error_mm` or `pointer_tip_rms_error_mm` row found in header export | "Calibration metadata absent — cannot verify tracking quality" | S01 calibration=null (universal finding, Phases 4+5.5) |

> **Note on T1-05/T1-06:** The 30-second (3600-frame) threshold is a **hard user directive** (HANDOFF_CURRENT.md Phase 5.5 decision). A genuine dance phrase in this study protocol takes >140 seconds. Anything under 30 seconds is definitionally a botched recording and must not enter the pipeline. The threshold is conservative; it is not intended to flag legitimate sub-optimal sessions — only completely failed recording attempts.

---

### Tier 2 — Parsed Structural Checks (require reading the data body, not full pipeline)

| ID | Check | Severity | Threshold / Rule | Failure message | Maps to pipeline risk |
|----|-------|----------|-----------------|-----------------|----------------------|
| T2-01 | Positions array shape | **FAIL** | Exactly 19 joints × 3 columns (x, y, z) parse cleanly | "Position array malformed — expected (N, 19, 3)" | S01 segments_found_count; pipeline cannot proceed |
| T2-02 | Quaternions array shape | **FAIL** | Exactly 19 joints × 4 columns (w, x, y, z or x, y, z, w) parse cleanly | "Quaternion array malformed — expected (N, 19, 4)" | S01 parse; S06 kinematics will error |
| T2-03 | NaN fraction per joint — WARNING band | WARN | Any joint: `nan_fraction > 0.10` | "Joint {J}: {P}% NaN frames — high dropout, verify marker attachment" | Methodology spec: per-joint NaN flag threshold = 10% (F1 risk table) |
| T2-04 | NaN fraction per joint — CRITICAL band | **FAIL** | Any joint: `nan_fraction > 0.30` | "Joint {J}: {P}% NaN frames — joint unusable. Re-marker if possible." | Methodology spec: hard exclusion at 30%; PCA 19-feature constraint invalidated |
| T2-05 | All-NaN joint detected | **FAIL** | Any joint column is 100% NaN | "Joint {J} is entirely NaN — marker absent or rigid body ID lost. Re-marker." | PCA 19-feature rule broken; ATF/TM/Gini all fail for this joint |
| T2-06 | Long consecutive NaN gaps | WARN | Any gap of `> 120 frames` (1 second at 120 Hz) for any joint | "Joint {J}: gap of {N} consecutive NaN frames ({T}s) — risk of invalid gap-fill in S02" | S02 gap detection bug (gapfill_positions.py:134 boundary condition) |
| T2-07 | Boundary NaN gaps (start/end) | WARN | NaN frames in first or last 120 frames for any joint | "Joint {J}: NaN frames at recording boundary — reference detection window may be compromised" | S05 ref detection searches first 8s; NaN at start → no valid static window |
| T2-08 | Quaternion norm sanity — WARNING | WARN | Any non-NaN quaternion: `0.90 < |q| < 1.10` required; flag if outside this | "Joint {J}: quaternion norms deviate from unit ({min:.3f}–{max:.3f}) — possible export error" | Q-EXT4a FAIL: no |q|≈1.0 assertion in S06; normalization silently applied |
| T2-09 | Quaternion norm sanity — CRITICAL | **FAIL** | Any non-NaN quaternion: `|q| < 0.5` | "Joint {J}: severely corrupted quaternion norms ({min:.3f}) — rotation data invalid. Re-record." | Same; quaternion with |q|<0.5 is physically impossible from OptiTrack |
| T2-10 | Timestamp jitter | WARN | `std(diff(Time)) > 0.5 ms` | "Timestamp jitter {N}ms exceeds 0.5ms — irregular sampling, check Motive settings" | S02 jitter check (confirmed 0.0005ms in current data = PASS; threshold is ×10 of current) |
| T2-11 | Frame number continuity | WARN | `all(diff(Frame) == 1)` — no skipped or repeated frame numbers | "Frame number gap detected at frame {N}: jumped by {D} — frames may be dropped" | Q-EXT3c FAIL: no frame continuity check in S01; confirmed universal absence |
| T2-12 | Position coordinate range | WARN | All non-NaN position values within ±5000 mm of median Hips position | "Joint {J} has positions outside ±5m range — possible marker ID swap or scene contamination" | Marker swap risk; S04 Hampel may not catch a sustained swap |
| T2-13 | Velocity spike detection (raw) | WARN | Frame-to-frame position delta > 50 mm for any joint in any frame | "Joint {J}: {N} single-frame position jumps > 50mm detected — tracking glitches present" | S04 Hampel filter; 50mm/frame = 6 m/s at 120Hz; clearly non-physiological |
| T2-14 | TM endpoint NaN fraction — WARNING | WARN | Any of LeftHand, RightHand, LeftFoot, RightFoot: `nan_fraction > 0.20` | "Endpoint {E}: {P}% NaN — TM computation will be compromised for this endpoint" | Methodology spec F2 TM: endpoint flag threshold = 20% |
| T2-15 | TM endpoint NaN fraction — CRITICAL | **FAIL** | Any of LeftHand, RightHand, LeftFoot, RightFoot: `nan_fraction > 0.50` | "Endpoint {E}: {P}% NaN — TM for this endpoint is unusable. Consider re-taping." | F2 TM: endpoint with >50% NaN provides no reliable path length |
| T2-16 | Estimated all-joint-clean fraction | WARN | `product(1 - nan_i) < 0.70` across all 19 joints | "Estimated PCA-clean frame fraction {P:.1%} < 70% — D_eff and Joint Gini may be unreliable" | Methodology spec §F4: min_clean_fraction_pca = 0.70; PCA low-confidence flag |

> **Implementation note on T2-08/T2-09:** The quaternion norm check must use `||q||₂ = sqrt(w² + x² + y² + z²)`. The scalar-last convention used by the pipeline (`[x,y,z,w]`) vs OptiTrack's export convention must be identified from the header. The norm is convention-independent.

---

### Tier 3 — Lightweight Scientific Sanity Checks

These checks do not require any pipeline processing. They use only raw parsed positions and rotations. They are the "is this recording scientifically usable?" layer.

| ID | Check | Severity | Threshold / Rule | Failure message | Maps to pipeline risk |
|----|-------|----------|-----------------|-----------------|----------------------|
| T3-01 | **T-pose window plausibility** ⚠️ **DRAFT_PENDING_RESEARCH** | WARN | ⚠️ **THRESHOLD NOT FINALIZED.** Candidate approach: in first 8 seconds (960 frames), find the 1-second window with minimum mean joint angular velocity (raw quat log-differences). If that minimum exceeds 0.10 rad/s for ≥15 of 19 joints → WARN. **User feedback: 0.10 rad/s threshold and fixed 8s window are too strict on real data and produce false alarms even when subject is known to be static. Logic requires further research before implementation.** See deferred task ADV-T3-01 in HANDOFF_CURRENT.md. | "⚠️ T-pose stability check is DRAFT — threshold not validated. Results are indicative only." | **F-651-4 + F7-2**: 651_T3_P2_R2 had ref_is_fallback=True due to movement at start. The need for a fast pre-check is confirmed; the correct algorithm requires calibration. |
| T3-02 | Motion magnitude during recording (session too slow) | WARN | Mean position RMS across all joints < 5 mm across entire session — subject appears stationary | "Subject appears stationary throughout. Check that recording started at the right time." | Inverted dead-session check: not too short, but too inactive to be a dance session |
| T3-03 | **Bone length stability** | WARN | For each adjacent joint pair (19 bones), compute length per frame. If CV > 2.0% for any bone → WARN; if CV > 5.0% → FAIL | WARN: "Bone {B}: length CV {P:.1f}% > 2% — marker slip likely. Check tape before re-taping." FAIL: "Bone {B}: length CV {P:.1f}% > 5% — marker severely unstable. Re-marker and re-record." | **F-651-3 + bone QC findings**: 651_T2_P2_R1 reached SILVER (mean_cv = 1.011); universal Hips→Spine alert; inter-session CV drift. Early detection prevents invalid bone QC reaching analysis. |
| T3-04 | Hands/feet dropout risk | WARN | Any of LeftHand, RightHand, LeftFoot, RightFoot has `nan_fraction > 0.10` | "Endpoint {E}: {P}% dropout. If hand/foot movement is the primary scientific signal, re-tape and re-record." | ATF peripheral group (F7-1); TM (F2); methodology spec endpoint flags |
| T3-05 | Hips vertical displacement range | WARN | `std(Hips_py) < 5 mm` over entire session | "Hips vertical displacement std < 5mm — subject appears not to have varied height. Check if marker is on pelvis (not floor/wall)." | Structural sanity; REVIEW_OVERSMOOTHING worst column = Hips__py (−24 to −27 dB) suggests Hips__py should have meaningful signal in dance |
| T3-06 | Session too short for thesis analysis | WARN | Duration < 140 seconds (but >= 30s) | "Session duration {N}s < 140s (minimum typical dance phrase). This may be re-recordable if participant is still present. ATF/TM metrics will be noisy on short sessions." | Methodology spec: `min_session_duration_s = 60.0` (soft gate); user directive: 140s = minimum genuine dance phrase |
| T3-07 | Estimated reference confidence (**linked to T3-01, also DRAFT**) | WARN | If T3-01 fires, also check whether any 2s window in first 8s has Hips position variance < 100 mm². **Note: this check is only as reliable as T3-01; both are DRAFT_PENDING_RESEARCH.** Hips position variance is less sensitive to the threshold calibration problem than angular velocity. | "No reference window found with Hips variance < 100mm² in first 8s. Same trigger as S05 ref_is_fallback. Re-recording from T-pose may resolve this." | S05 var_score threshold = 100.0; F-651-4; confirmed threshold. Hips position variance branch is more stable than angular velocity branch — can be implemented independently of T3-01. |
| T3-08 | Bone pair completeness for ATF axial | INFO | Check that Hips, Spine, Spine1, Neck, Head all have nan_fraction < 0.05 | "Axial joints {J}: {P}% NaN — ATF axial group will be unreliable. Also note: Hips ATF is structurally 0 (root joint). ATF axial relies on Spine/Spine1/Neck/Head only." | **F7-1**: Hips ATF = 0 permanently. This is the earliest point to communicate this to the user. |

> ⚠️ **Note on T3-01 (T-pose check) — DRAFT_PENDING_RESEARCH:**
> The 0.10 rad/s threshold and fixed 8-second search window are **not validated** on the full dataset. User feedback confirmed that the threshold fires false alarms on sessions known to have a valid static period. Three candidate improvements are deferred to the implementation phase (see HANDOFF_CURRENT.md, ADV-T3-01):
> 1. **Threshold loosening:** Explore the range 0.15–0.30 rad/s; derive from all 15 known-good sessions rather than from a single failure case.
> 2. **Global minimum search:** Instead of a fixed threshold, flag only when the global session minimum falls in the "expected static" range but still exceeds a dynamically calibrated floor (e.g., 2× inter-session minimum).
> 3. **"Double-back" stability verification:** After finding the minimum-motion window, verify that the preceding and following windows show increasing motion (i.e., the subject was transitioning to/from a static pose), not that the entire recording is uniformly low-motion.
> Until this research is complete, T3-01 is emitted as an informational output only (INFO, not WARN) and must not trigger a FAIL verdict.

> **Note on T3-03 (bone length stability):** The bone pair list and expected lengths come from `config_v1.yaml` (anthropometric measurements). If config is absent, use the first-frame lengths as nominal. CV = std/mean × 100%. Threshold 2% = WARN, 5% = FAIL. The NB02 bone QC uses 1.0% as the SILVER boundary; 2% is conservative for fast QC purposes (allows for OptiTrack raw noise without filtering). Bones to check: Hips→Spine, Spine→Spine1, Spine1→Neck, Neck→Head, Spine1→LeftShoulder, LeftShoulder→LeftArm, LeftArm→LeftForeArm, LeftForeArm→LeftHand (and symmetric right), Hips→LeftUpLeg, LeftUpLeg→LeftLeg, LeftLeg→LeftFoot (and symmetric right).

---

## Bone Pair Definitions (T3-03)

The 18 structural bone pairs expected in the 19-joint skeleton:

| Bone | Proximal | Distal |
|------|---------|--------|
| Lumbar | Hips | Spine |
| Thoracic | Spine | Spine1 |
| Cervical | Spine1 | Neck |
| Cranial | Neck | Head |
| L shoulder girdle | Spine1 | LeftShoulder |
| L upper arm | LeftShoulder | LeftArm |
| L forearm | LeftArm | LeftForeArm |
| L hand | LeftForeArm | LeftHand |
| R shoulder girdle | Spine1 | RightShoulder |
| R upper arm | RightShoulder | RightArm |
| R forearm | RightArm | RightForeArm |
| R hand | RightForeArm | RightHand |
| L hip | Hips | LeftUpLeg |
| L thigh | LeftUpLeg | LeftLeg |
| L shank | LeftLeg | LeftFoot |
| R hip | Hips | RightUpLeg |
| R thigh | RightUpLeg | RightLeg |
| R shank | RightLeg | RightFoot |

---

## Human-Readable Report Design

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAGA FAST QC — 671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subject : 671        Timepoint : T1    Protocol : P2    Rep : R1
Duration : 140.95 s  Frames   : 16,915  Rate : 120.0 Hz

VERDICT: ✓ PASS

─── TIER 1 (Raw file) ──────────────────────────────────────
  ✓ T1-01  File exists and non-empty
  ✓ T1-02  File size plausible (98.4 MB)
  ✓ T1-03  Filename parsed: subject=671 T=1 P=2 R=1
  ✓ T1-04  Frame and Time columns found
  ✓ T1-05  Duration 140.95s ≥ 30s minimum
  ✓ T1-06  Frame count 16,915 ≥ 3600 minimum
  ✓ T1-07  Frame rate 120.0 Hz ≈ expected
  ✓ T1-08  Time monotonically increasing
  ⚠ T1-09  Capture frame rate not found in header (WARN)
  ⚠ T1-10  Rotation type not found in header (WARN)
  ✓ T1-11  All 19 joints found in header
  ✓ T1-12  No duplicate joint columns
  ⚠ T1-13  Calibration metadata absent (WARN)

─── TIER 2 (Structural) ─────────────────────────────────────
  ✓ T2-01  Position array: (16915, 19, 3) ✓
  ✓ T2-02  Quaternion array: (16915, 19, 4) ✓
  ✓ T2-03  Max joint NaN fraction: 0.11% (LeftHand) ✓
  ✓ T2-04  No joint exceeds 30% NaN
  ✓ T2-05  No all-NaN joint
  ✓ T2-06  Max consecutive NaN gap: 3 frames (0.025s) ✓
  ✓ T2-07  No boundary NaN gaps
  ✓ T2-08  Quaternion norms: 0.999–1.001 ✓
  ✓ T2-09  No critically corrupted quaternions
  ✓ T2-10  Timestamp jitter: 0.0005ms std ✓
  ⚠ T2-11  Frame continuity: not verified (header scan only)
  ✓ T2-12  Position range: −1823 to +1742 mm ✓
  ✓ T2-13  Velocity spikes: 0 frames > 50mm ✓
  ✓ T2-14  Endpoint NaN: max 0.11% (LeftHand) ✓
  ✓ T2-15  No endpoint exceeds 50% NaN
  ✓ T2-16  Est. PCA-clean fraction: ~99.9% ≥ 70% ✓

─── TIER 3 (Scientific) ─────────────────────────────────────
  ✓ T3-01  Static window found in first 8s (min motion: 0.039 rad/s)
  ✓ T3-02  Session has adequate motion for dance analysis
  ✓ T3-03  Bone length stability: max CV 0.52% < 2% ✓
  ✓ T3-04  Endpoint dropout: max 0.11% ✓
  ✓ T3-05  Hips vertical displacement: std 42.3 mm ✓
  ⚠ T3-06  Duration 140.95s (≥30s hard gate ✓; just above 140s minimum phrase)
  ✓ T3-07  Reference confidence: Hips variance in best window = 7.2 mm² ✓
  ℹ T3-08  NOTE: Hips ATF will be 0 by construction (root joint). Axial ATF = Spine/Spine1/Neck/Head only.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OVERALL: PASS (3 warnings, 0 fails)
Time elapsed: 6.2s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**FAIL example (dead session):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAGA FAST QC — 651_T2_P2_R2_Take 2026-01-26 05.24.12 PM_003
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subject : 651        Timepoint : T2    Protocol : P2    Rep : R2
Duration : 0.03 s    Frames   : 5      Rate : 120.0 Hz

VERDICT: ✗ FAIL — RE-RECORD IMMEDIATELY

─── TIER 1 (Raw file) ──────────────────────────────────────
  ✗ T1-05  FAIL: Session duration 0.03s < 30s minimum.
            This is a botched recording. Re-record before participant leaves.
  ✗ T1-06  FAIL: Frame count 5 < 3600 minimum.

  [Tier 2 and Tier 3 checks skipped — hard gate failure in Tier 1]

OVERALL: FAIL (2 hard fails)
```

---

## Machine-Readable JSON Schema

```json
{
  "fast_qc_schema_version": "1.0",
  "run_id": "671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002",
  "subject_id": "671",
  "timepoint": "T1",
  "protocol": "P2",
  "repetition": "R1",
  "csv_path": "data/671/T1/671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002.csv",
  "run_timestamp_utc": "2026-05-15T14:23:00Z",
  "overall_verdict": "PASS",
  "n_fail": 0,
  "n_warn": 3,
  "duration_s": 140.95,
  "n_frames": 16915,
  "estimated_fs_hz": 120.0,
  "checks": [
    {
      "check_id": "T1-05",
      "tier": 1,
      "name": "session_duration_minimum",
      "severity": "FAIL",
      "status": "PASS",
      "value": 140.95,
      "threshold": 30.0,
      "unit": "seconds",
      "message": null,
      "maps_to_pipeline_risk": "F-651-1: dead session passes all 6 pipeline stages silently"
    },
    {
      "check_id": "T3-01",
      "tier": 3,
      "name": "t_pose_window_plausibility",
      "severity": "WARN",
      "status": "PASS",
      "value": 0.039,
      "threshold": 0.10,
      "unit": "rad/s (mean motion in best static window)",
      "message": null,
      "maps_to_pipeline_risk": "F-651-4: ref_is_fallback triggers when subject moves at recording start"
    }
  ],
  "per_joint_summary": {
    "LeftHand": {"nan_fraction": 0.0011, "max_vel_spike_mm": 12.3, "bone_cv_pct": 0.31},
    "Hips": {"nan_fraction": 0.0, "note": "Hips ATF will be 0 by construction (root joint)"}
  },
  "bone_lengths": {
    "Hips_Spine": {"mean_mm": 198.4, "cv_pct": 0.41},
    "Spine1_Neck": {"mean_mm": 145.2, "cv_pct": 0.22}
  },
  "t_pose_check": {
    "best_window_start_s": 1.2,
    "best_window_end_s": 2.2,
    "mean_motion_rad_s": 0.039,
    "hips_variance_mm2": 7.2,
    "ref_fallback_predicted": false
  }
}
```

---

## Integration with Batch Processing

The fast QC must be callable from three contexts:

### 1. Standalone (field use, immediately after collection)
```bash
python fast_qc.py data/671/T1/671_T1_P2_R1_Take_2026-01-06.csv
```
Exits with code 0 (PASS/WARN) or 1 (FAIL).

### 2. Integrated into `run_pipeline.py` (automatic pre-check)
```python
# In run_pipeline.py, before papermill execution:
qc_result = run_fast_qc(csv_path, config)
if qc_result.verdict == "FAIL":
    logger.error(f"Fast QC FAIL for {run_id}: {qc_result.fail_reasons}")
    batch_summary.mark_failed(run_id, reason="fast_qc_fail")
    continue  # skip full pipeline for this session
```
This prevents the full pipeline from wasting time processing a dead session (F-651-1 fix).

### 3. Batch pre-screen (new sessions discovered in data/)
```bash
python fast_qc.py --batch batch_configs/subject_671_p2_all.json
```
Produces a summary table: one row per session with verdict and top flags.

---

## What Must Not Be Included Yet

The following items are **explicitly excluded** from this script version:

| Excluded item | Reason |
|--------------|--------|
| Butterworth or any digital filtering | Too slow; belongs in Step 04 |
| PCHIP or SLERP gap filling | Too slow; belongs in Step 02 |
| Angular velocity from quat_log method | Too slow; raw quat diff approximation is sufficient for T3-01 |
| S05 reference detection (full algorithm) | Too slow; T3-01 is a fast approximation only |
| Bone QC with full NB02 logic | Too slow; T3-03 raw CV is sufficient |
| PCA / ATF / TM computation | Layer C metrics; not a QC concern |
| Any write to `derivatives/` | QC must not pollute pipeline artifacts |
| ML/DL readiness checks | Phase 6 scope; not field QC |
| Parquet I/O | Only CSV input |

---

## Future Implementation Plan

Phase 8 is requirements-only. Implementation lives in Phase 13 (ticket-by-ticket).

### Suggested implementation order

| Step | Task | Effort |
|------|------|--------|
| 13-QC-01 | Skeleton: `fast_qc.py` with argument parsing, JSON output stub, basic Tier 1 file/header checks | Small |
| 13-QC-02 | Tier 1 complete: duration gate, frame count, header field extraction (T1-01 through T1-13) | Small |
| 13-QC-03 | Tier 2 complete: parse positions/quaternions, NaN checks, norm check, velocity spikes (T2-01 through T2-16) | Medium |
| 13-QC-04 | Tier 3: T-pose window detection (raw quat diff), bone length CV, endpoint dropout (T3-01 through T3-08) | Medium |
| 13-QC-05 | Human-readable report formatter (color-coded terminal output) | Small |
| 13-QC-06 | Integration into `run_pipeline.py` as pre-check | Small |
| 13-QC-07 | Batch mode (`--batch` flag) | Small |
| 13-QC-08 | Regression test: dead session (651_T2_P2_R2) must FAIL; canonical session (671_T1_P2_R1) must PASS | Small |

### Test fixtures

Two sessions should serve as regression fixtures for the fast QC:

| Session | Expected verdict | Primary check exercised |
|---------|-----------------|------------------------|
| `651_T2_P2_R2` (5 frames) | **FAIL** (T1-05, T1-06) | Minimum duration/frame gate |
| `671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002` | **PASS** | Nominal good session |
| `651_T3_P2_R2` (movement at start) | **PASS_WITH_WARNINGS** (T3-01, T3-07) | T-pose stability detection |

---

## Audit Evidence Chain

| Check | Source finding |
|-------|---------------|
| T1-05/T1-06: 30s/3600-frame minimum | Phase 5.5 F-651-1 (dead session passes all 6 pipeline stages); HANDOFF_CURRENT.md user directive |
| T1-09/T1-10: Capture/Export rate and rotation type | Phase 4 Q-EXT3b FAIL |
| T2-11: Frame continuity | Phase 4 Q-EXT3c FAIL |
| T2-08/T2-09: Quaternion norm | Phase 4 Q-EXT4a FAIL (no |q|≈1.0 assertion in S06) |
| T3-01/T3-07: T-pose plausibility | Phase 5.5 F-651-4 (ref_is_fallback=True, 651_T3_P2_R2); Phase 7 F7-2 |
| T3-03: Bone length stability | Phase 5.5 F-651-3 (bone CV rises T1→T2→T3); Phase 4 S02 bone QC three-system finding |
| T3-08: Hips ATF note | Phase 7 F7-1 (Hips ATF = 0 permanently, root joint structural bias) |
| T2-16: PCA clean fraction estimate | Phase 7 F7-5 (dead session clean_fraction gate); Methodology spec min_clean_fraction_pca=0.70 |

---

*Phase 8 complete. Next phase: Phase 9 — Testing and regression plan.*
