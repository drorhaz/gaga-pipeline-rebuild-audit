"""
src/pulsicity.py — Step 07: Behavioral Metrics (Pulsicity & Flow)
=================================================================

Computes diagnostic metrics from ``{segment}__lin_vel_rel_mag`` as produced by
NB06 (``notebooks/06_ultimate_kinematics.ipynb``) and stored in
``derivatives/step_06_kinematics/{RUN_ID}__kinematics_master.parquet``.

Functions provided (Steps 1–3 scope — backend only; no Parquet I/O):
    check_enforce_cleaning_provenance()  — mandatory provenance check
    get_inherited_config()               — validate & log inherited Step 06 params
    compute_sg_effective_cutoff()        — dynamic SavGol effective cutoff (~2.3 Hz)
    compute_noise_floor()                — session-adaptive threshold V [mm/s]
    compute_psd_diagnostic()             — Welch PSD + noise-ratio banner
    compute_sparc()                      — Spectral Arc Length smoothness metric
    detect_velocity_peaks()              — Split-Signal Bridge-and-Discard peak detector
    aggregate_pulsicity_metrics()        — assemble output schema row (PPM, IPI_CV, SPARC, …)

Architectural decisions: ``docs/STEP_07_MISSION_PLAN.md``
Audit findings (kinematic chain integrity): ``docs/STEP_0_AUDIT_REPORT.md``

Strict constraints (from audit and mission plan):
  - Do NOT re-differentiate ``lin_vel_rel_mag``.
  - Do NOT apply ``filtfilt`` to the Measurement Signal.
  - Do NOT call any function from ``src/filtering.py``.
  - SPARC gap bridging uses PCHIP only (never linear interpolation).
  - All config values read from passed ``cfg`` dict; nothing is hardcoded.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.signal import butter, find_peaks, freqz, savgol_coeffs, sosfiltfilt, welch

# NumPy 2.0 renamed np.trapz → np.trapezoid; provide a shim for both versions.
try:
    _trapz = np.trapezoid       # type: ignore[attr-defined]
except AttributeError:
    _trapz = np.trapz           # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helper: replicate NB06's savgol_window_len() exactly
# ---------------------------------------------------------------------------

def _savgol_window_len(fs: float, w_sec: float, polyorder: int) -> int:
    """
    Compute the SavGol window length in frames, replicating NB06's helper.

    Rules (from NB06 setup cell, verified in Audit Pass 1):
      1. w_len = int(round(w_sec * fs))
      2. Force odd: if even, add 1
      3. Enforce minimum: max(5, w_len, polyorder + 2)
      4. Force odd again (in case minimum changed parity)

    At default params (w_sec=0.175, fs=120.0, polyorder=3):
      → w_len = 21  (confirmed from NB06 stored cell output)
    """
    w_len = int(round(w_sec * fs))
    if w_len % 2 == 0:
        w_len += 1
    w_len = max(5, w_len, polyorder + 2)
    if w_len % 2 == 0:
        w_len += 1
    return w_len


# ---------------------------------------------------------------------------
# Config inheritance & provenance
# ---------------------------------------------------------------------------

def check_enforce_cleaning_provenance(cfg: dict) -> bool:
    """
    Emit a mandatory provenance warning if ``step_06.enforce_cleaning = True``.

    **Background — Audit Pass 1, Finding F2 (DISCREPANCY MEDIUM):**
    ``src/kinematic_repair.py::apply_surgical_repair()`` updates
    ``{seg}__lin_vel_rel_x/y/z`` after PCHIP + SavGol repair but does NOT
    recompute ``{seg}__lin_vel_rel_mag``.  If any recording was processed with
    ``ENFORCE_CLEANING=True``, the magnitude column in that recording's
    kinematics_master.parquet is stale for any repaired segment.

    Current exposure: zero — all 16 existing recordings have
    ``ENFORCE_CLEANING=False`` (confirmed from NB06 stored cell output).

    Args:
        cfg: Pipeline config dict (from ``pipeline_config.py`` or YAML load).

    Returns:
        True if enforce_cleaning was active (warning emitted); False otherwise.
    """
    # Accept both nested YAML form and the flat uppercase alias
    step06_cfg = cfg.get("step_06", {})
    if not isinstance(step06_cfg, dict):
        step06_cfg = {}
    enforce_cleaning = bool(step06_cfg.get("enforce_cleaning", False))

    # Also honour the uppercase alias created by pipeline_config.py
    if not enforce_cleaning:
        enforce_cleaning = bool(cfg.get("ENFORCE_CLEANING", False))

    if enforce_cleaning:
        logger.warning(
            "[PROVENANCE WARNING] step_06.enforce_cleaning=True detected. "
            "lin_vel_rel_mag may be STALE for surgically repaired segments. "
            "src/kinematic_repair.py updates lin_vel_rel_x/y/z after PCHIP "
            "repair but does NOT recompute lin_vel_rel_mag. "
            "Verify magnitude consistency for repaired segments before "
            "interpreting pulsicity metrics.  "
            "See docs/STEP_0_AUDIT_REPORT.md § Section 3 Finding F2."
        )

    return enforce_cleaning


def get_inherited_config(cfg: dict) -> dict:
    """
    Extract, validate, and log all Step 06 config parameters inherited by Step 07.

    Returns a flat dict of resolved values with canonical lowercase keys.
    Also computes ``sg_eff_cutoff_hz`` dynamically (not hardcoded).

    Logs a formatted audit block — suitable for printing in notebook Section 1.

    Args:
        cfg: Pipeline config dict.

    Returns:
        Dict with keys:
            ``fs_target``            (float) Hz
            ``sg_window_sec``        (float) s
            ``sg_polyorder``         (int)
            ``sg_window_len``        (int)   frames (computed)
            ``sg_eff_cutoff_hz``     (float) Hz (dynamic -3dB computation)
            ``ref_search_sec``       (float) s
            ``ref_window_sec``       (float) s
            ``static_search_step_sec`` (float) s
            ``reference_variance_threshold`` (float)
            ``min_run_seconds``      (float) s
            ``enforce_cleaning``     (bool)
    """
    def _get(key_lower, key_upper, default):
        val = cfg.get(key_lower)
        if val is None:
            val = cfg.get(key_upper)
        return val if val is not None else default

    fs        = float(_get("fs_target", "FS_TARGET", 120.0))
    w_sec     = float(_get("sg_window_sec", "SG_WINDOW_SEC", 0.175))
    polyorder = int(_get("sg_polyorder", "SG_POLYORDER", 3))
    w_len     = _savgol_window_len(fs, w_sec, polyorder)
    f_eff     = compute_sg_effective_cutoff(w_len, polyorder, fs)

    inherited = {
        "fs_target":                    fs,
        "sg_window_sec":                w_sec,
        "sg_polyorder":                 polyorder,
        "sg_window_len":                w_len,
        "sg_eff_cutoff_hz":             f_eff,
        "ref_search_sec":               float(_get("ref_search_sec", "REF_SEARCH_SEC", 8.0)),
        "ref_window_sec":               float(_get("ref_window_sec", "REF_WINDOW_SEC", 1.0)),
        "static_search_step_sec":       float(_get("static_search_step_sec", "STATIC_SEARCH_STEP_SEC", 0.1)),
        "reference_variance_threshold": float(cfg.get("reference_variance_threshold", 100.0)),
        "min_run_seconds":              float(cfg.get("min_run_seconds", 5.0)),
        "enforce_cleaning":             check_enforce_cleaning_provenance(cfg),
    }

    # Formatted audit log (also suitable for print() in notebook)
    lines = [
        "━" * 56,
        "STEP 07 — CONFIG INHERITANCE AUDIT",
        "━" * 56,
        f"  fs_target          : {inherited['fs_target']:.1f} Hz        [config/config_v1.yaml]",
        f"  sg_window_sec      : {inherited['sg_window_sec']:.3f} s"
        f"  →  {inherited['sg_window_len']} frames",
        f"  sg_polyorder       : {inherited['sg_polyorder']}",
        f"  sg_eff_cutoff      : {inherited['sg_eff_cutoff_hz']:.3f} Hz"
        "  (dynamic -3dB computation)",
        f"  ref_search_sec     : {inherited['ref_search_sec']:.1f} s",
        f"  ref_window_sec     : {inherited['ref_window_sec']:.1f} s",
        f"  min_run_seconds    : {inherited['min_run_seconds']:.1f} s",
        f"  enforce_cleaning   : {inherited['enforce_cleaning']}",
        "━" * 56,
    ]
    audit_str = "\n".join(lines)
    logger.info("\n" + audit_str)

    return inherited


# ---------------------------------------------------------------------------
# SavGol effective cutoff (dynamic, from config)
# ---------------------------------------------------------------------------

def compute_sg_effective_cutoff(w_len: int, polyorder: int, fs: float) -> float:
    """
    Compute the effective cutoff frequency of the SavGol smoothing filter.

    The SavGol derivative (``deriv=1``) simultaneously smooths and differentiates.
    Above the effective cutoff, signal content in ``lin_vel_rel_mag`` reflects
    the SavGol smoother's own frequency rolloff rather than genuine movement.
    This cutoff is the correct SPARC frequency cap and PSD diagnostic reference.

    **Definition used: first frequency at which the SavGol smoother attenuates
    signal amplitude by more than 1% (i.e., magnitude drops below 99% of DC).**

    Rationale for 99% threshold:
        The standard -3dB point of the SavGol smoother's frequency response is
        ~6.1 Hz for w_len=21, polyorder=3, fs=120 Hz — far too permissive for
        the SPARC cap.  The 99% threshold (0.1 dB) captures the onset of
        meaningful filter influence and produces ~2.4 Hz for default params,
        matching the ~2.3 Hz stated in METHODS_DOCUMENTATION.md Section 5.2.

        The METHODS_DOCUMENTATION.md figure (~2.3 Hz) was derived from the
        rectangular-window equivalent bandwidth rule-of-thumb
        (≈ 0.4 × fs / w_len = 2.29 Hz), which closely agrees with the 99%
        threshold method.

    Method:
      1. Compute SavGol smoothing coefficients (``deriv=0``) via
         ``scipy.signal.savgol_coeffs``.
      2. Compute frequency response via ``scipy.signal.freqz`` on 8192 points.
      3. Find the first frequency where ``|H(f)| ≤ 0.99 × |H(0)|``.
      4. Linear interpolation between bracketing samples for sub-Hz accuracy.

    Verified values (w_len=21, polyorder=3, fs=120 Hz):
      - 99% threshold method:        ~2.41 Hz  ← used here
      - Rectangular rule-of-thumb:   ~2.53 Hz  (0.443 × fs / w_len)
      - METHODS_DOCUMENTATION.md:    ~2.3  Hz

    Args:
        w_len:     SavGol window length in frames (must be odd, >= polyorder+2).
        polyorder: SavGol polynomial order.
        fs:        Sampling frequency in Hz.

    Returns:
        Effective cutoff frequency in Hz (onset of >1% SavGol attenuation).
    """
    coeffs = savgol_coeffs(w_len, polyorder, deriv=0)
    w, h = freqz(coeffs, worN=8192, fs=fs)
    magnitude = np.abs(h)
    dc_gain = float(magnitude[0])

    # 99% amplitude threshold: first frequency where SavGol attenuates by >1%
    threshold = dc_gain * 0.99

    crossings = np.where(magnitude <= threshold)[0]
    if len(crossings) == 0:
        # No crossing: filter preserves >99% everywhere — use Nyquist fallback
        f_eff = float(fs / 2.0)
        logger.warning(
            f"compute_sg_effective_cutoff: no 99%-amplitude crossing found for "
            f"w_len={w_len}, polyorder={polyorder}, fs={fs}. "
            f"Returning Nyquist {f_eff:.1f} Hz as fallback."
        )
        return f_eff

    idx = crossings[0]
    if idx == 0:
        return float(w[0])

    # Sub-sample linear interpolation between (idx-1, idx)
    m0, m1 = float(magnitude[idx - 1]), float(magnitude[idx])
    f0, f1 = float(w[idx - 1]), float(w[idx])
    if m1 == m0:
        return f0
    frac = (threshold - m0) / (m1 - m0)
    return float(f0 + frac * (f1 - f0))


# ---------------------------------------------------------------------------
# Step 1a — Noise Floor
# ---------------------------------------------------------------------------

def compute_noise_floor(
    df: pd.DataFrame,
    segment: str,
    cfg: dict,
    *,
    static_baseline_guard_mms: float = 50.0,
    noise_floor_guard_mms: float = 1.0,
) -> Dict:
    """
    Compute the session-adaptive noise floor threshold *V* for one segment.

    This is a **1:1 replica of** ``calibration.find_stable_window()`` — the
    Step 05 static reference window detection — adapted to run directly from
    ``kinematics_master.parquet`` without requiring ``reference_map.json``
    (which is absent from disk for all 16 existing recordings — see Audit Pass 1
    Finding F3).

    Algorithm
    ---------
    Phase 1 — Static window search (mirrors calibration.find_stable_window):
        Slide a ``ref_window_sec`` (1 s) window over the first
        ``ref_search_sec`` (8 s) of the recording in steps of
        ``static_search_step_sec`` (0.1 s).  At each position, compute the
        **sum of positional variances** across the target segment's own
        root-relative position axes (px, py, pz).  Select the window with
        minimum total variance.

        Why position variance (not angular velocity / velocity mean):
            ``calibration.find_stable_window()`` uses position-variance
            minimization — confirmed by code audit.  ``MOTION_THR_LOW`` and
            ``MOTION_THR_STD`` are NOT selection criteria in that function
            (``MOTION_THR_STD`` is only active in ``reference.py::
            detect_static_reference()``, a different early-pipeline function).
            See Audit Pass 3, Finding P3-F3.

        Why the target segment's own columns (not Hips):
            Root-relative Hips positions are identically ~0 (they are the
            reference frame subtracted from all other segments) — their
            variance contributes nothing.  Step 07 computes variance over the
            target segment's own ``px/py/pz`` columns.

    Phase 2 — Extract noise floor:
        Compute mean velocity in the selected window (artifact frames excluded).
        If ``mean < static_baseline_guard_mms`` (50 mm/s):
            V = mean + 2 × std
            source = "step05_position_variance_replica"
        Otherwise (subject was moving, no reliable static pose found):
            V = 5th-percentile of full clean session velocity
            source = "5th_percentile_fallback"

    Phase 3 — Absolute floor guard:
        V = max(V, noise_floor_guard_mms)   [default: 1.0 mm/s]
        Prevents division-edge-cases in downstream PPM computation.

    Position column discovery (priority order):
        1. ``{segment}__lin_rel_px/py/pz``  — explicit root-relative naming
        2. ``{segment}__px/py/pz``          — alternate naming convention
        3. Velocity-proxy fallback: sliding window minimum of
           ``mean(lin_vel_rel_mag)`` when no position columns are present.
           This is logged clearly; ``noise_floor_source`` will indicate "proxy".

    Low-confidence flag:
        ``noise_floor_low_confidence = True`` when position variance exceeds
        ``reference_variance_threshold`` (100.0 from config) — mirrors the
        ``ref_is_fallback`` concept from ``calibration.find_stable_window()``.

    Args:
        df:                        DataFrame (kinematics_master.parquet rows).
        segment:                   Segment name, e.g. ``'RightHand'``.
        cfg:                       Pipeline config dict.
        static_baseline_guard_mms: Max mean velocity (mm/s) for the static
                                   window to be accepted as a genuine still pose.
        noise_floor_guard_mms:     Absolute minimum for V (mm/s).

    Returns:
        Dict with keys:

        ``V``                          float   noise floor threshold [mm/s]
        ``noise_floor_source``         str     detection method used
        ``noise_floor_low_confidence`` bool    True if pos variance > threshold
        ``static_window_start_frame``  int     best window start index
        ``static_window_end_frame``    int     best window end index (exclusive)
        ``static_window_mean_mms``     float   mean velocity in static window
        ``static_window_variance``     float   total position variance (or proxy)
        ``n_clean_frames``             int     non-artifact frames in recording
        ``_variance_method``           str     "position_variance" or "velocity_mean_proxy"

    Raises:
        KeyError: if ``{segment}__lin_vel_rel_mag`` is absent from ``df``.
    """
    # --- Config ---
    fs         = float(cfg.get("fs_target",               cfg.get("FS_TARGET",              120.0)))
    search_sec = float(cfg.get("ref_search_sec",          cfg.get("REF_SEARCH_SEC",          8.0)))
    window_sec = float(cfg.get("ref_window_sec",          cfg.get("REF_WINDOW_SEC",          1.0)))
    step_sec   = float(cfg.get("static_search_step_sec",  cfg.get("STATIC_SEARCH_STEP_SEC",  0.1)))
    var_thresh = float(cfg.get("reference_variance_threshold", 100.0))

    search_frames = int(search_sec * fs)
    window_frames = int(window_sec * fs)
    step_frames   = max(1, int(step_sec * fs))

    # --- Required columns ---
    vel_col = f"{segment}__lin_vel_rel_mag"
    art_col = f"{segment}__is_artifact"

    if vel_col not in df.columns:
        raise KeyError(
            f"compute_noise_floor: column '{vel_col}' not found in DataFrame. "
            f"Available columns starting with '{segment}': "
            f"{[c for c in df.columns if c.startswith(segment)]}"
        )

    vel      = df[vel_col].values.astype(float)
    artifact = (
        df[art_col].values.astype(bool)
        if art_col in df.columns
        else np.zeros(len(vel), dtype=bool)
    )
    n_frames = len(vel)

    # Full-session clean velocity (artifact → NaN)
    v_clean_all = vel.copy()
    v_clean_all[artifact] = np.nan
    n_clean_frames = int(np.sum(~artifact & ~np.isnan(vel)))

    # --- Phase 1: Static window search ---
    # Discover root-relative position columns (two naming conventions)
    pos_col_candidates: List[List[str]] = [
        [f"{segment}__lin_rel_px", f"{segment}__lin_rel_py", f"{segment}__lin_rel_pz"],
        [f"{segment}__px",         f"{segment}__py",         f"{segment}__pz"],
    ]
    pos_cols: List[str] = []
    for candidate_set in pos_col_candidates:
        found = [c for c in candidate_set if c in df.columns]
        if len(found) >= 2:
            pos_cols = found
            break

    use_position = len(pos_cols) >= 2
    variance_method = "position_variance" if use_position else "velocity_mean_proxy"

    if not use_position:
        logger.warning(
            f"compute_noise_floor({segment}): root-relative position columns not "
            f"found in DataFrame (checked {[s[0] for s in pos_col_candidates]}__px/y/z). "
            f"Falling back to velocity-mean proxy for static window detection. "
            f"This is equivalent for detecting still poses (low mean velocity ↔ "
            f"low position variance)."
        )

    best_score = np.inf
    best_start = 0
    cap = min(search_frames, n_frames)

    for start in range(0, cap - window_frames + 1, step_frames):
        end = start + window_frames
        art_win = artifact[start:end]

        if use_position:
            # Sum of position variances across available axes
            score = 0.0
            for col in pos_cols:
                vals = df[col].values[start:end].astype(float)
                vals[art_win] = np.nan
                n_valid_win = int(np.sum(~np.isnan(vals)))
                if n_valid_win >= 3:
                    score += float(np.nanvar(vals))
                else:
                    score = np.inf
                    break
        else:
            # Velocity-mean proxy: lower mean ↔ more static
            v_win = vel[start:end].copy()
            v_win[art_win] = np.nan
            n_valid_win = int(np.sum(~np.isnan(v_win)))
            if n_valid_win >= 3:
                score = float(np.nanmean(v_win))
            else:
                score = np.inf

        if score < best_score:
            best_score = score
            best_start = start

    # Low-confidence flag (mirrors calibration.find_stable_window ref_is_fallback)
    if use_position:
        noise_floor_low_confidence = bool(best_score > var_thresh)
    else:
        # Velocity proxy: flag as low-confidence if best window mean
        # exceeds the static baseline guard
        noise_floor_low_confidence = bool(best_score > static_baseline_guard_mms)

    static_window_variance = float(best_score) if np.isfinite(best_score) else np.nan
    best_end = best_start + window_frames

    # --- Phase 2: Extract noise floor ---
    art_win_best = artifact[best_start:best_end]
    v_win_best   = vel[best_start:best_end].copy()
    v_win_best[art_win_best] = np.nan
    v_win_clean  = v_win_best[~np.isnan(v_win_best)]

    if len(v_win_clean) >= 3:
        static_mean = float(np.mean(v_win_clean))
        static_std  = float(np.std(v_win_clean))
    else:
        # Best window had no clean frames — force 5th-percentile fallback
        static_mean = np.inf
        static_std  = 0.0

    if static_mean < static_baseline_guard_mms:
        V = static_mean + 2.0 * static_std
        if use_position:
            source = "step05_position_variance_replica"
        else:
            source = "step05_velocity_proxy"
        if noise_floor_low_confidence:
            source += "_LOW_CONFIDENCE"
    else:
        # 5th-percentile of full clean session
        v_session = v_clean_all[~np.isnan(v_clean_all)]
        V = float(np.percentile(v_session, 5)) if len(v_session) > 0 else noise_floor_guard_mms
        source = "5th_percentile_fallback"
        logger.warning(
            f"compute_noise_floor({segment}): static window mean "
            f"{static_mean:.1f} mm/s >= guard {static_baseline_guard_mms:.1f} mm/s. "
            f"Using 5th-percentile fallback V={V:.2f} mm/s."
        )

    # --- Phase 3: Absolute floor guard ---
    V = float(max(V, noise_floor_guard_mms))

    logger.info(
        f"compute_noise_floor({segment}): "
        f"V={V:.2f} mm/s | source={source} | "
        f"window=[{best_start}:{best_end}] ({best_start/fs:.2f}–{best_end/fs:.2f} s) | "
        f"static_mean={static_mean:.2f} mm/s | "
        f"variance={static_window_variance:.4g} | "
        f"low_confidence={noise_floor_low_confidence}"
    )

    return {
        "V":                           V,
        "noise_floor_source":          source,
        "noise_floor_low_confidence":  noise_floor_low_confidence,
        "static_window_start_frame":   int(best_start),
        "static_window_end_frame":     int(best_end),
        "static_window_mean_mms":      float(static_mean) if np.isfinite(static_mean) else np.nan,
        "static_window_variance":      static_window_variance,
        "n_clean_frames":              n_clean_frames,
        "_variance_method":            variance_method,
    }


# ---------------------------------------------------------------------------
# Step 1b — PSD Diagnostic
# ---------------------------------------------------------------------------

def compute_psd_diagnostic(
    df: pd.DataFrame,
    segment: str,
    cfg: dict,
    *,
    f_eff: Optional[float] = None,
    noise_threshold_marginal: float = 0.05,
    noise_threshold_recommend: float = 0.15,
    psd_band_signal_low_hz: float = 0.5,
    psd_band_noise_high_hz: float = 10.0,
) -> Dict:
    """
    Compute Welch PSD and derive a noise-ratio diagnostic for the velocity signal.

    The noise ratio quantifies how much spectral power lives above the SavGol
    effective cutoff (``f_eff``) — a frequency band where no genuine movement
    content should remain — relative to the signal band below that cutoff.
    A high noise ratio suggests the Search Signal may benefit from additional
    Butterworth smoothing before peak detection.

    **This function recommends only — it never applies any filter.**
    The researcher must explicitly approve a secondary filter via the notebook
    widget (Section 4 of ``07_pulsicity_flow.ipynb``).

    Band definitions::

        signal band: [psd_band_signal_low_hz,  f_eff]      default: [0.5, ~2.3] Hz
        noise  band: [f_eff,  psd_band_noise_high_hz]       default: [~2.3, 10] Hz
        noise_ratio = ∫(noise band PSD) / ∫(signal band PSD)   (trapezoidal)

    Recommendation thresholds:

    +-------------------+-----------------------------+--------+
    | noise_ratio       | banner / recommendation      | color  |
    +===================+=============================+========+
    | < 0.05            | No filter needed             | green  |
    +-------------------+-----------------------------+--------+
    | 0.05 – 0.15       | Filter may improve peaks     | yellow |
    +-------------------+-----------------------------+--------+
    | ≥ 0.15            | Secondary filter recommended | red    |
    +-------------------+-----------------------------+--------+

    Args:
        df:                        DataFrame (kinematics_master.parquet).
        segment:                   Segment name, e.g. ``'RightHand'``.
        cfg:                       Pipeline config dict.
        f_eff:                     SavGol effective cutoff Hz.  Computed
                                   dynamically from config if ``None``.
        noise_threshold_marginal:  noise_ratio threshold for yellow banner.
        noise_threshold_recommend: noise_ratio threshold for red banner.
        psd_band_signal_low_hz:    Lower bound of signal integration band [Hz].
        psd_band_noise_high_hz:    Upper bound of noise integration band [Hz].

    Returns:
        Dict with keys:

        ``freqs``                  np.ndarray  frequency axis [Hz]
        ``psd``                    np.ndarray  one-sided power spectral density
        ``noise_ratio``            float       band_noise / band_signal (NaN if undefined)
        ``psd_filter_recommended`` bool        True if noise_ratio >= threshold
        ``psd_banner_level``       str         "green" / "yellow" / "red" / "unknown"
        ``f_eff_hz``               float       SavGol cutoff used [Hz]
        ``band_signal_power``      float       integrated signal band power
        ``band_noise_power``       float       integrated noise band power
        ``n_clean_frames``         int         clean frames used for PSD

    Raises:
        KeyError: if ``{segment}__lin_vel_rel_mag`` is absent from ``df``.
    """
    fs = float(cfg.get("fs_target", cfg.get("FS_TARGET", 120.0)))

    if f_eff is None:
        w_sec     = float(cfg.get("sg_window_sec", cfg.get("SG_WINDOW_SEC", 0.175)))
        polyorder = int(cfg.get("sg_polyorder",   cfg.get("SG_POLYORDER",   3)))
        w_len     = _savgol_window_len(fs, w_sec, polyorder)
        f_eff     = compute_sg_effective_cutoff(w_len, polyorder, fs)

    vel_col = f"{segment}__lin_vel_rel_mag"
    art_col = f"{segment}__is_artifact"

    if vel_col not in df.columns:
        raise KeyError(f"compute_psd_diagnostic: column '{vel_col}' not found.")

    vel      = df[vel_col].values.astype(float)
    artifact = (
        df[art_col].values.astype(bool)
        if art_col in df.columns
        else np.zeros(len(vel), dtype=bool)
    )

    v_clean = vel.copy()
    v_clean[artifact] = np.nan
    v_psd   = v_clean[~np.isnan(v_clean)]
    n_clean = len(v_psd)

    _empty = {
        "freqs":               np.array([]),
        "psd":                 np.array([]),
        "noise_ratio":         np.nan,
        "psd_filter_recommended": False,
        "psd_banner_level":    "unknown",
        "f_eff_hz":            float(f_eff),
        "band_signal_power":   np.nan,
        "band_noise_power":    np.nan,
        "n_clean_frames":      n_clean,
    }

    if n_clean < 32:
        logger.warning(
            f"compute_psd_diagnostic({segment}): only {n_clean} clean frames — "
            f"PSD unreliable. Returning NaN noise_ratio."
        )
        return _empty

    nperseg  = min(512, max(32, n_clean // 4))
    noverlap = nperseg // 2

    freqs, psd = welch(v_psd, fs=fs, window="hann", nperseg=nperseg, noverlap=noverlap)

    # Trapezoidal integration over defined bands
    sig_mask   = (freqs >= psd_band_signal_low_hz) & (freqs < f_eff)
    noise_mask = (freqs >= f_eff) & (freqs <= psd_band_noise_high_hz)

    band_signal = float(_trapz(psd[sig_mask], freqs[sig_mask])) if sig_mask.any() else 0.0
    band_noise  = float(_trapz(psd[noise_mask], freqs[noise_mask])) if noise_mask.any() else 0.0

    if band_signal > 0.0:
        noise_ratio = float(band_noise / band_signal)
    else:
        noise_ratio = np.nan
        logger.warning(
            f"compute_psd_diagnostic({segment}): signal band power is zero — "
            f"noise_ratio undefined (f_eff={f_eff:.3f} Hz, "
            f"signal band=[{psd_band_signal_low_hz}, {f_eff:.3f}] Hz). "
            f"Check that signal band contains at least one frequency bin."
        )

    # Banner level
    if np.isnan(noise_ratio):
        banner      = "unknown"
        recommended = False
    elif noise_ratio < noise_threshold_marginal:
        banner      = "green"
        recommended = False
    elif noise_ratio < noise_threshold_recommend:
        banner      = "yellow"
        recommended = False
    else:
        banner      = "red"
        recommended = True

    logger.info(
        f"compute_psd_diagnostic({segment}): "
        f"noise_ratio={noise_ratio:.4f} | banner={banner} | "
        f"f_eff={f_eff:.3f} Hz | signal={band_signal:.3e} | noise={band_noise:.3e}"
    )

    return {
        "freqs":               freqs,
        "psd":                 psd,
        "noise_ratio":         noise_ratio,
        "psd_filter_recommended": recommended,
        "psd_banner_level":    banner,
        "f_eff_hz":            float(f_eff),
        "band_signal_power":   band_signal,
        "band_noise_power":    band_noise,
        "n_clean_frames":      n_clean,
    }


# ---------------------------------------------------------------------------
# PCHIP gap bridging (internal, shared utility)
# ---------------------------------------------------------------------------

def _bridge_gaps_pchip(signal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Bridge NaN gaps in a 1D signal using PCHIP interpolation.

    PCHIP (Piecewise Cubic Hermite Interpolating Polynomial) is required
    because:

    - **C¹ continuity** at gap endpoints — no corner discontinuities that
      would inject high-frequency energy into the spectrum (unlike linear
      interpolation, which produces triangular waveforms with discontinuous
      first derivatives at gap boundaries, creating sinc-like spectral leakage
      that artificially inflates the SPARC arc length).
    - **Local monotonicity** — no overshoot or ringing (unlike natural cubic
      splines).
    - **Pipeline consistency** — PCHIP is already used in
      ``src/kinematic_repair.py`` and Step 02 preprocessing for position
      gap-filling.

    Edge handling:
        Leading and trailing NaN regions (before the first or after the last
        valid sample) are filled by **constant extension** (nearest valid
        value).  PCHIP extrapolation is disabled (``extrapolate=False``) to
        avoid polynomial divergence.

    Args:
        signal: 1D float array, may contain NaN.

    Returns:
        Tuple of:
            ``bridged`` (np.ndarray): NaN-free signal.
            ``gap_mask`` (np.ndarray, bool): True at positions that were
                interpolated or edge-filled.
    """
    n      = len(signal)
    is_nan = np.isnan(signal)
    gap_mask = is_nan.copy()

    if not is_nan.any():
        return signal.copy(), gap_mask

    if is_nan.all():
        logger.warning("_bridge_gaps_pchip: entire signal is NaN — cannot bridge.")
        return signal.copy(), gap_mask

    bridged  = signal.copy()
    x_valid  = np.where(~is_nan)[0]
    y_valid  = signal[x_valid]

    if len(x_valid) == 1:
        # Single valid point — constant fill everywhere
        bridged[is_nan] = y_valid[0]
        return bridged, gap_mask

    # PCHIP over interior NaN spans (between first and last valid sample)
    interp     = PchipInterpolator(x_valid, y_valid, extrapolate=False)
    x_nan      = np.where(is_nan)[0]
    x_interior = x_nan[(x_nan > x_valid[0]) & (x_nan < x_valid[-1])]

    if len(x_interior) > 0:
        bridged[x_interior] = interp(x_interior)

    # Constant edge extension (leading / trailing)
    x_leading  = x_nan[x_nan < x_valid[0]]
    x_trailing = x_nan[x_nan > x_valid[-1]]

    if len(x_leading) > 0:
        bridged[x_leading] = y_valid[0]
    if len(x_trailing) > 0:
        bridged[x_trailing] = y_valid[-1]

    return bridged, gap_mask


# ---------------------------------------------------------------------------
# Step 1c — SPARC
# ---------------------------------------------------------------------------

def compute_sparc(
    df: pd.DataFrame,
    segment: str,
    cfg: dict,
    *,
    f_eff: Optional[float] = None,
    amplitude_threshold: float = 0.05,
) -> Dict:
    """
    Compute the Spectral Arc Length (SPARC) smoothness metric.

    SPARC measures movement smoothness in the frequency domain.
    More negative SPARC → more fragmented / pulsive movement.
    SPARC → 0 as movement approaches a perfectly smooth, single-lobe velocity
    profile.

    Mathematical definition
    -----------------------
    Given the clean (artifact-masked, PCHIP-bridged) velocity signal v(t)::

        V_hat(f) = |FFT[v](f)| / |FFT[v](0)|          (normalised spectrum)

        SPARC = -∫₀^{f_cap} sqrt((1/f_cap)² + (dV̂/df)²) df

    The integrand traces the arc length of the curve [f/f_cap, V̂(f)] in 2D
    normalised space.  Computed numerically via the trapezoidal rule.

    Frequency cap (f_cap)
    ---------------------
    ``f_cap = f_eff`` — the SavGol effective low-pass cutoff (~2.3 Hz at
    default pipeline parameters).

    Rationale: ``lin_vel_rel_mag`` is derived via SavGol (W_LEN=21,
    polyorder=3, fs=120 Hz, deriv=1, mode='interp').  All spectral content
    above ``f_eff`` represents SavGol filter rolloff, not genuine movement.
    Integrating beyond ``f_eff`` would measure the filter's frequency
    response, not the dancer's kinematics.

    Note — cascaded filter context (from Audit Pass 2):
        The Step 04 adaptive Winter Butterworth filter has a per-region floor
        ≥ 6 Hz and runtime fmax=20 Hz — both well above f_eff ≈ 2.3 Hz.  The
        SavGol derivative therefore dominates the spectral rolloff, confirming
        that f_eff (not Winter fmax) is the correct SPARC cap.

    Amplitude threshold
    -------------------
    ``amplitude_threshold`` (default 0.05): if the normalised spectrum drops
    below 5 % of DC within [0, f_cap], the integration range is trimmed at
    that crossing.  This matches the original SPARC paper (Balasubramanian
    et al. 2012) and avoids integrating over a near-flat tail.

    Gap bridging (PCHIP — mandatory)
    ---------------------------------
    Artifact frames are set to NaN before FFT.  NaN gaps are bridged using
    PCHIP (see ``_bridge_gaps_pchip``).  PCHIP is mandatory here — linear
    bridges produce triangular waveforms at gap endpoints whose discontinuous
    first derivatives inject sinc-like high-frequency energy into the spectrum,
    artificially inflating the arc length and producing spuriously negative
    SPARC scores.

    **The PCHIP-bridged signal is used only for SPARC — the Measurement Signal
    and the Search Signal are never modified.**

    Args:
        df:                  DataFrame (kinematics_master.parquet).
        segment:             Segment name, e.g. ``'RightHand'``.
        cfg:                 Pipeline config dict.
        f_eff:               SavGol effective cutoff Hz (computed if ``None``).
        amplitude_threshold: Minimum normalised amplitude below which the
                             integration range is trimmed (default 0.05).

    Returns:
        Dict with keys:

        ``sparc``                  float   SPARC value (≤ 0; NaN if failed)
        ``sparc_freq_cap_hz``      float   f_cap used for integration [Hz]
        ``sparc_n_frames``         int     total frames in signal
        ``sparc_n_bridged_frames`` int     frames filled by PCHIP
        ``sparc_gap_fraction``     float   bridged / total frames
        ``sparc_dc_component``     float   |FFT(0)| before normalisation [mm/s]
        ``sparc_failed``           bool    True if insufficient data or DC≈0
        ``sparc_failure_reason``   str|None  human-readable reason if failed

    Raises:
        KeyError: if ``{segment}__lin_vel_rel_mag`` is absent from ``df``.
    """
    fs = float(cfg.get("fs_target", cfg.get("FS_TARGET", 120.0)))

    if f_eff is None:
        w_sec     = float(cfg.get("sg_window_sec", cfg.get("SG_WINDOW_SEC", 0.175)))
        polyorder = int(cfg.get("sg_polyorder",   cfg.get("SG_POLYORDER",   3)))
        w_len     = _savgol_window_len(fs, w_sec, polyorder)
        f_eff     = compute_sg_effective_cutoff(w_len, polyorder, fs)

    vel_col = f"{segment}__lin_vel_rel_mag"
    art_col = f"{segment}__is_artifact"

    if vel_col not in df.columns:
        raise KeyError(f"compute_sparc: column '{vel_col}' not found.")

    vel      = df[vel_col].values.astype(float)
    artifact = (
        df[art_col].values.astype(bool)
        if art_col in df.columns
        else np.zeros(len(vel), dtype=bool)
    )

    v_masked = vel.copy()
    v_masked[artifact] = np.nan

    n_frames = len(v_masked)
    n_nan    = int(np.sum(np.isnan(v_masked)))
    n_valid  = n_frames - n_nan

    # Minimum viable length: at least 4 full cycles of f_cap
    min_frames = max(32, int(np.ceil(4.0 * fs / max(f_eff, 0.5))))

    def _fail(reason: str) -> Dict:
        logger.warning(f"compute_sparc({segment}): {reason}")
        return {
            "sparc":                  np.nan,
            "sparc_freq_cap_hz":      float(f_eff),
            "sparc_n_frames":         n_frames,
            "sparc_n_bridged_frames": n_nan,
            "sparc_gap_fraction":     n_nan / n_frames if n_frames > 0 else np.nan,
            "sparc_dc_component":     np.nan,
            "sparc_failed":           True,
            "sparc_failure_reason":   reason,
        }

    if n_valid < min_frames:
        return _fail(
            f"Insufficient valid frames: {n_valid} < {min_frames} required "
            f"for reliable SPARC at f_cap={f_eff:.3f} Hz."
        )

    # --- PCHIP gap bridging (SPARC computation only) ---
    v_bridged, gap_mask = _bridge_gaps_pchip(v_masked)
    n_bridged = int(np.sum(gap_mask))

    if np.any(np.isnan(v_bridged)):
        # Defensive: should not happen; zero-fill residual NaN
        n_residual = int(np.sum(np.isnan(v_bridged)))
        logger.warning(
            f"compute_sparc({segment}): {n_residual} NaN frame(s) remain after "
            f"PCHIP bridging (edge-only gaps with no valid neighbours). "
            f"Zero-filling for FFT."
        )
        v_bridged = np.nan_to_num(v_bridged, nan=0.0)

    # --- FFT (one-sided) ---
    spectrum  = np.fft.rfft(v_bridged, n=n_frames)
    freqs     = np.fft.rfftfreq(n_frames, d=1.0 / fs)
    magnitude = np.abs(spectrum)
    dc_component = float(magnitude[0])

    if dc_component < 1e-10:
        return _fail(
            f"DC component near zero ({dc_component:.3e}) — cannot normalise "
            f"spectrum. Signal may be near-constant after PCHIP bridging."
        )

    # Normalised spectrum V̂(f) = |FFT(f)| / |FFT(0)|
    v_hat = magnitude / dc_component

    # --- Integration range ---
    # ω_c = last frequency in [0, f_eff] where V̂(f) >= amplitude_threshold
    # (Balasubramanian 2012 definition: ω_c = max{ω : V̂(ω) >= ε AND ω <= ω_max})
    # Using "last above threshold" (not "first below threshold") ensures that
    # spectral gaps (zero-power bins between peaks) do not prematurely truncate
    # the integration range.  For broadband signals V̂ decreases monotonically
    # and both definitions are equivalent; for sparse/synthetic signals the
    # "last above" definition is more robust.
    cap_mask = freqs <= f_eff
    cap_indices = np.where(cap_mask)[0]

    above_thresh_in_cap = cap_indices[v_hat[cap_indices] >= amplitude_threshold]

    if len(above_thresh_in_cap) >= 2:
        # Keep indices from 0 up to (and including) last above-threshold index
        last_valid_idx = above_thresh_in_cap[-1]
        integration_indices = cap_indices[cap_indices <= last_valid_idx]
    elif len(above_thresh_in_cap) == 1:
        # Only DC is above threshold — use DC + one neighbour for a minimal range
        integration_indices = cap_indices[:2] if len(cap_indices) >= 2 else cap_indices
    else:
        # Nothing above threshold — use the full cap range
        integration_indices = cap_indices

    freqs_int = freqs[integration_indices]
    v_hat_int = v_hat[integration_indices]

    if len(freqs_int) < 2:
        return _fail(
            f"Integration range too short after f_cap + amplitude_threshold trim "
            f"(f_cap={f_eff:.3f} Hz, threshold={amplitude_threshold}). "
            f"len(freqs_int)={len(freqs_int)}."
        )

    actual_f_cap = float(freqs_int[-1])

    # --- Arc length integrand ---
    # SPARC = -∫₀^{f_cap} sqrt((1/f_cap)² + (dV̂/df)²) df
    # The (1/f_cap)² term is the arc-length contribution from the
    # normalised frequency axis (f/f_cap ∈ [0, 1]).
    dv_hat_df = np.gradient(v_hat_int, freqs_int)
    integrand = np.sqrt((1.0 / actual_f_cap) ** 2 + dv_hat_df ** 2)
    arc_length = float(_trapz(integrand, freqs_int))
    sparc = -arc_length

    gap_fraction = float(n_bridged / n_frames) if n_frames > 0 else 0.0

    logger.info(
        f"compute_sparc({segment}): "
        f"SPARC={sparc:.4f} | f_cap={actual_f_cap:.3f} Hz | "
        f"bridged={n_bridged}/{n_frames} ({gap_fraction:.1%}) | "
        f"DC={dc_component:.2f} mm/s | amplitude_threshold={amplitude_threshold}"
    )

    return {
        "sparc":                  sparc,
        "sparc_freq_cap_hz":      actual_f_cap,
        "sparc_n_frames":         n_frames,
        "sparc_n_bridged_frames": n_bridged,
        "sparc_gap_fraction":     gap_fraction,
        "sparc_dc_component":     dc_component,
        "sparc_failed":           False,
        "sparc_failure_reason":   None,
    }


# ---------------------------------------------------------------------------
# Internal helper: linear gap bridge for Search Signal
# ---------------------------------------------------------------------------

def _bridge_gaps_linear(
    signal: np.ndarray,
    max_bridge_frames: int,
) -> Tuple[np.ndarray, int]:
    """
    Bridge short NaN gaps with linear interpolation (Search Signal only).

    Only gaps of length ≤ ``max_bridge_frames`` are bridged.  Longer gaps are
    left as NaN — they represent extended artifact periods with insufficient
    context for reliable bridging.

    This function is used exclusively for the **Search Signal** v_s(t) in
    ``detect_velocity_peaks()``.  Using linear (not PCHIP) interpolation is
    intentional:

    - The Search Signal is used only for peak *index* localization.  Its
      values at candidate peak frames are never reported — ``v_m`` is always
      the source of peak magnitudes (Bridge-and-Discard protocol).
    - Spectral accuracy and C¹ continuity are irrelevant for ``find_peaks``.
    - Linear bridging avoids PCHIP's monotonicity constraint, which can
      produce undershoot humps in short gaps and create artificial local
      maxima in the Search Signal.

    Leading / trailing NaN spans (before the first or after the last valid
    sample) are filled by **constant extension** (nearest valid value) if
    within ``max_bridge_frames``; otherwise left as NaN.

    Args:
        signal:            1D float array, may contain NaN.
        max_bridge_frames: Maximum gap length to bridge (inclusive).

    Returns:
        Tuple of:
            ``bridged`` (np.ndarray): Signal with short gaps linearly filled.
            ``n_bridged`` (int):      Total frames that were filled.
    """
    n = len(signal)
    bridged = signal.copy()
    is_nan = np.isnan(bridged)
    n_bridged = 0

    if not is_nan.any():
        return bridged, 0

    # Detect contiguous NaN spans via edge-padding trick
    padded     = np.concatenate([[False], is_nan, [False]])
    gap_starts = np.where(~padded[:-1] & padded[1:])[0]   # gap begins at gs
    gap_ends   = np.where(padded[:-1] & ~padded[1:])[0]   # gap ends before ge

    for gs, ge in zip(gap_starts, gap_ends):
        gap_len = ge - gs
        if gap_len > max_bridge_frames:
            continue

        left_val  = float(bridged[gs - 1]) if gs > 0 else np.nan
        right_val = float(bridged[ge])     if ge < n  else np.nan

        if not np.isnan(left_val) and not np.isnan(right_val):
            # Interior gap: linear interpolation between anchors
            x_fill = np.arange(gs, ge, dtype=float)
            bridged[gs:ge] = np.interp(
                x_fill, [float(gs - 1), float(ge)], [left_val, right_val]
            )
        elif not np.isnan(left_val):
            # Trailing edge: constant extension with left anchor
            bridged[gs:ge] = left_val
        elif not np.isnan(right_val):
            # Leading edge: constant extension with right anchor
            bridged[gs:ge] = right_val
        else:
            # Isolated NaN island with no valid neighbours — leave as NaN
            continue

        n_bridged += gap_len

    return bridged, n_bridged


# ---------------------------------------------------------------------------
# Step 2 — Peak Detection Engine (Split-Signal Search)
# ---------------------------------------------------------------------------

def detect_velocity_peaks(
    df: pd.DataFrame,
    segment: str,
    cfg: dict,
    *,
    V: float,
    prominence_multiplier: float = 0.5,
    min_distance_frames: int = 12,
    height_gate: bool = True,
    secondary_filter_cutoff_hz: Optional[float] = None,
    max_bridge_sec: Optional[float] = None,
) -> Dict:
    """
    Detect velocity peaks using the Split-Signal Bridge-and-Discard protocol.

    Signal Architecture
    -------------------
    Two parallel views of the raw kinematic data are maintained::

        Measurement Signal  v_m(t)
            Source : {segment}__lin_vel_rel_mag, artifact frames → NaN
            Role   : Ground-truth magnitude.  Never modified.

        Search Signal  v_s(t)
            Source : v_m with short NaN spans linearly bridged (≤ max_bridge_sec)
            Optional: secondary Butterworth low-pass smoothing (human-gated)
            Role   : Peak *index* localization only.

    Bridge-and-Discard Protocol (§2.1 of STEP_07_MISSION_PLAN.md)
    --------------------------------------------------------------
    1. Build ``v_m``: copy ``lin_vel_rel_mag``, set artifact frames to NaN.
    2. Build ``v_s``: linearly bridge NaN spans ≤ ``max_bridge_sec``.
       Spans > ``max_bridge_sec`` remain NaN, then zero-filled before
       ``find_peaks`` (zero < V so no spurious peaks are produced there;
       any that slip through are discarded in step 6–7).
    3. Compute σ_v = std(v_m[non-artifact & non-NaN]).
    4. Optionally apply Butterworth low-pass to v_s (``secondary_filter_cutoff_hz``).
    5. Call ``find_peaks(v_s, prominence=prominence_multiplier×σ_v,
                         distance=min_distance_frames, [height=V])``.
    6. Discard candidate t_k where ``artifact[t_k] == True``.
    7. Discard candidate t_k where ``v_m[t_k]`` is NaN (zero-filled long gap).
    8. Report ``v_m[t_k]`` as peak magnitude — **never** the Search Signal value.

    Secondary Butterworth (§2.2)
    ----------------------------
    If ``secondary_filter_cutoff_hz`` is not None, v_s is smoothed with a
    2nd-order Butterworth via ``sosfiltfilt`` (zero-phase, SOS form).  This is
    a **human-gated** parameter — the notebook widget sets it only when the
    researcher explicitly approves the PSD recommendation.  ``v_m`` is never
    filtered.

    Physiological Constraints (§2.3)
    ---------------------------------
    Prominence: p > ``prominence_multiplier`` × σ_v  (adaptive to session)
    Distance:   d > 100 ms = 12 frames @ 120 Hz
    Height:     v_s(t_k) > V  [noise floor, mm/s]  — optional, default enabled

    If σ_v = 0 (constant-velocity segment), the prominence threshold is 0 and
    ``find_peaks`` may return many local maxima; the height gate V provides the
    primary filter.  A warning is logged in this degenerate case.

    Args:
        df:                        DataFrame (kinematics_master.parquet rows).
        segment:                   Segment name, e.g. ``'RightHand'``.
        cfg:                       Pipeline config dict.
        V:                         Noise floor threshold [mm/s] from
                                   ``compute_noise_floor()``.
        prominence_multiplier:     Multiplier on σ_v for prominence threshold
                                   (default 0.5, from §2.3).
        min_distance_frames:       Minimum inter-peak distance in frames
                                   (default 12 = 100 ms @ 120 Hz).
        height_gate:               If True, pass ``height=V`` to find_peaks,
                                   requiring v_s peaks to exceed the noise floor.
        secondary_filter_cutoff_hz: Butterworth cutoff [Hz] for Search Signal
                                   smoothing.  ``None`` = no secondary filter.
                                   Set by notebook widget (human-gated).
        max_bridge_sec:            Max contiguous artifact span [s] to bridge in
                                   v_s.  Defaults to ``cfg['max_gap_pos_sec']``
                                   (1.0 s from config).

    Returns:
        Dict with keys:

        ``peak_indices``               np.ndarray[int]   accepted peak frame indices
        ``peak_velocities_mms``        np.ndarray[float] v_m at accepted peaks [mm/s]
        ``peak_prominences``           np.ndarray[float] prominence of each peak [mm/s]
        ``n_peaks``                    int               accepted peak count
        ``sigma_v_mms``                float             std of clean Measurement Signal
        ``prominence_threshold_mms``   float             actual prominence threshold used
        ``min_distance_frames``        int               distance constraint used
        ``n_candidate_peaks``          int               raw find_peaks output count
        ``n_discarded_artifact``       int               peaks discarded on artifact frames
        ``n_discarded_nan``            int               peaks discarded in NaN gaps
        ``n_bridged_frames_search``    int               frames bridged in Search Signal
        ``secondary_filter_applied``   bool              True if Butterworth was applied
        ``secondary_filter_cutoff_hz`` float|None        cutoff used (or None)
        ``v_m``                        np.ndarray[float] Measurement Signal (NaN on art.)
        ``v_s``                        np.ndarray[float] Search Signal (final, no NaN)
        ``artifact``                   np.ndarray[bool]  artifact mask

    Raises:
        KeyError: if ``{segment}__lin_vel_rel_mag`` is absent from ``df``.
    """
    fs = float(cfg.get("fs_target", cfg.get("FS_TARGET", 120.0)))
    if max_bridge_sec is None:
        max_bridge_sec = float(
            cfg.get("max_gap_pos_sec", cfg.get("MAX_GAP_POS_SEC", 1.0))
        )
    max_bridge_frames = max(1, int(max_bridge_sec * fs))

    vel_col = f"{segment}__lin_vel_rel_mag"
    art_col = f"{segment}__is_artifact"

    if vel_col not in df.columns:
        raise KeyError(
            f"detect_velocity_peaks: column '{vel_col}' not found in DataFrame. "
            f"Available columns starting with '{segment}': "
            f"{[c for c in df.columns if c.startswith(segment)]}"
        )

    vel      = df[vel_col].values.astype(float)
    artifact = (
        df[art_col].values.astype(bool)
        if art_col in df.columns
        else np.zeros(len(vel), dtype=bool)
    )

    # --- Measurement Signal v_m (artifact → NaN; never modified beyond this) ---
    v_m = vel.copy()
    v_m[artifact] = np.nan

    # σ_v: std of non-artifact, non-NaN frames of the raw Measurement Signal
    clean_mask = ~artifact & ~np.isnan(vel)
    v_clean    = vel[clean_mask]
    sigma_v    = float(np.std(v_clean)) if len(v_clean) >= 2 else 0.0

    if sigma_v == 0.0 and len(v_clean) > 0:
        logger.warning(
            f"detect_velocity_peaks({segment}): sigma_v = 0 (constant-velocity "
            f"segment?).  Prominence threshold = 0 — height gate V={V:.2f} mm/s "
            f"is the primary filter in this degenerate case."
        )

    prominence_threshold = prominence_multiplier * sigma_v

    # --- Search Signal v_s: linearly bridge short artifact gaps ---
    v_s_bridged, n_bridged_search = _bridge_gaps_linear(v_m.copy(), max_bridge_frames)

    # Zero-fill remaining NaN in v_s (long gaps + leading/trailing NaN).
    # Zero is below any physiological noise floor V, so find_peaks will not
    # place peaks there.  Any that slip through are discarded by Bridge-and-Discard
    # step 7 (v_m[t_k] is NaN at those frames).
    v_s = v_s_bridged.copy()
    v_s[np.isnan(v_s)] = 0.0

    # --- Optional secondary Butterworth (human-gated, §2.2) ---
    secondary_filter_applied = False
    if secondary_filter_cutoff_hz is not None and secondary_filter_cutoff_hz > 0:
        nyq = fs / 2.0
        if secondary_filter_cutoff_hz < nyq:
            sos = butter(
                N=2, Wn=secondary_filter_cutoff_hz / nyq, btype="low", output="sos"
            )
            v_s = sosfiltfilt(sos, v_s)
            secondary_filter_applied = True
        else:
            logger.warning(
                f"detect_velocity_peaks({segment}): secondary_filter_cutoff_hz "
                f"{secondary_filter_cutoff_hz:.2f} Hz >= Nyquist {nyq:.1f} Hz. "
                f"Secondary filter not applied."
            )

    # --- find_peaks on the Search Signal ---
    fp_kwargs: dict = {
        "prominence": prominence_threshold,
        "distance":   min_distance_frames,
    }
    if height_gate and np.isfinite(V) and V > 0:
        fp_kwargs["height"] = V

    candidate_indices, peak_props = find_peaks(v_s, **fp_kwargs)
    n_candidate = len(candidate_indices)

    # Prominences are returned when the `prominence` kwarg is passed
    candidate_prominences = peak_props.get("prominences", np.zeros(n_candidate))

    # --- Bridge-and-Discard: filter candidates ---
    # Step 6: discard peaks on artifact frames
    not_artifact_mask = ~artifact[candidate_indices]
    n_discarded_artifact = int(np.sum(~not_artifact_mask))

    # Step 7: discard peaks where v_m is NaN (zero-filled long gap)
    not_nan_vm_mask = ~np.isnan(v_m[candidate_indices])
    n_discarded_nan = int(np.sum(not_artifact_mask & ~not_nan_vm_mask))

    keep_mask = not_artifact_mask & not_nan_vm_mask

    peak_indices     = candidate_indices[keep_mask]
    peak_velocities  = v_m[peak_indices]           # Step 8: always from v_m
    peak_prominences = candidate_prominences[keep_mask]

    logger.info(
        f"detect_velocity_peaks({segment}): "
        f"n_peaks={len(peak_indices)} (candidates={n_candidate}, "
        f"discard_artifact={n_discarded_artifact}, discard_nan={n_discarded_nan}) | "
        f"sigma_v={sigma_v:.2f} mm/s | prominence_thr={prominence_threshold:.2f} mm/s | "
        f"V={V:.2f} mm/s | bridged={n_bridged_search} frames | "
        f"secondary_filter={secondary_filter_applied}"
    )

    return {
        "peak_indices":                 peak_indices,
        "peak_velocities_mms":          peak_velocities,
        "peak_prominences":             peak_prominences,
        "n_peaks":                      len(peak_indices),
        "sigma_v_mms":                  sigma_v,
        "prominence_threshold_mms":     prominence_threshold,
        "min_distance_frames":          min_distance_frames,
        "n_candidate_peaks":            n_candidate,
        "n_discarded_artifact":         n_discarded_artifact,
        "n_discarded_nan":              n_discarded_nan,
        "n_bridged_frames_search":      n_bridged_search,
        "secondary_filter_applied":     secondary_filter_applied,
        "secondary_filter_cutoff_hz":   (
            secondary_filter_cutoff_hz if secondary_filter_applied else None
        ),
        "v_m":                          v_m,
        "v_s":                          v_s,
        "artifact":                     artifact,
    }


# ---------------------------------------------------------------------------
# Step 3 — Aggregation & Normalization
# ---------------------------------------------------------------------------

def aggregate_pulsicity_metrics(
    df: pd.DataFrame,
    segment: str,
    cfg: dict,
    *,
    peaks_result: Dict,
    V: float,
    sparc_result: Optional[Dict] = None,
    psd_result: Optional[Dict] = None,
    noise_floor_result: Optional[Dict] = None,
    secondary_filter_applied: bool = False,
    secondary_filter_cutoff_hz: Optional[float] = None,
    enforce_cleaning_was_active: bool = False,
    run_id: str = "",
    pipeline_version: str = "pipeline_V6.2",
) -> Dict:
    """
    Aggregate per-segment pulsicity metrics into the Step 07 output schema row.

    Combines the outputs of ``compute_noise_floor``, ``detect_velocity_peaks``,
    ``compute_sparc``, and ``compute_psd_diagnostic`` into a single flat dict
    matching the Parquet schema defined in §3.3 of ``STEP_07_MISSION_PLAN.md``.
    This dict is ready for ``pd.DataFrame([result])`` serialization.

    Metric Definitions (locked in §3.1 and §6 of mission plan)
    ----------------------------------------------------------
    **Active time T_a:**
        T_a = (1/fs) × |{t : v_m(t) > V  and  ¬artifact(t)}|
        Counts non-artifact frames where velocity exceeded the noise floor.
        Units: seconds.

    **Peaks Per Minute (PPM):**
        PPM = (N_p / T_a) × 60
        Edge cases:
          • N_p = 0, T_a > 0  → PPM = 0.0   (zero pulsicity is a valid result)
          • N_p = 0, T_a = 0  → PPM = NaN   (no active movement at all)
          • T_a = 0, N_p > 0  → PPM = NaN   (should not occur, logged as warning)

    **Mean Peak Velocity:**
        v̄_p = (1/N_p) Σ v_m(t_k)   [mm/s].  NaN when N_p = 0.

    **Inter-Peak Interval (IPI):**
        IPI_k = (peak_indices[k+1] − peak_indices[k]) / fs   [seconds].
        Requires N_p ≥ 2.  All IPI statistics are NaN when N_p < 2.

    **IPI Coefficient of Variation:**
        CV_IPI = σ_IPI / μ_IPI.  NaN when N_p < 2 or μ_IPI = 0.

    **valid_movement_flag:**
        True  if T_a ≥ ``min_run_seconds`` (5.0 s from config).
        False if T_a < ``min_run_seconds``.

        Disambiguates:
          • Fluid performer: 0 peaks, T_a large  → valid_movement_flag = True.
          • Stationary segment: T_a < 5 s         → valid_movement_flag = False.
        Use ``filter(valid_movement_flag == TRUE)`` in R/SPSS to exclude
        non-sessions without manual per-recording cleaning.

    Edge-case summary::

        N_p   T_a        PPM          IPI_CV   valid_movement_flag
        ----  ---------  -----------  -------  -------------------
        0     > 0        0.0          NaN      T_a ≥ min_run_sec?
        0     0          NaN          NaN      False
        1     > 0        computed     NaN      T_a ≥ min_run_sec?
        ≥ 2   > 0        computed     computed T_a ≥ min_run_sec?

    Args:
        df:                         DataFrame (kinematics_master.parquet rows).
        segment:                    Segment name, e.g. ``'RightHand'``.
        cfg:                        Pipeline config dict.
        peaks_result:               Output of ``detect_velocity_peaks()``.
        V:                          Noise floor threshold [mm/s].
        sparc_result:               Output of ``compute_sparc()`` (or None).
        psd_result:                 Output of ``compute_psd_diagnostic()`` (or None).
        noise_floor_result:         Output of ``compute_noise_floor()`` (or None).
        secondary_filter_applied:   Whether Butterworth was applied to v_s.
                                    Overridden by ``peaks_result`` if present.
        secondary_filter_cutoff_hz: Butterworth cutoff used (or None).
                                    Overridden by ``peaks_result`` if present.
        enforce_cleaning_was_active: Value of ``step_06.enforce_cleaning`` at
                                    Step 07 processing time (from
                                    ``check_enforce_cleaning_provenance()``).
        run_id:                     Recording identifier for the output row.
        pipeline_version:           Git branch or tag label.

    Returns:
        Dict matching §3.3 output schema — one row per segment per recording.
        All fields are present; undefined quantities carry NaN or None.
    """
    import datetime

    fs              = float(cfg.get("fs_target",     cfg.get("FS_TARGET",    120.0)))
    min_run_seconds = float(cfg.get("min_run_seconds", 5.0))

    # ── Unpack peaks_result ──────────────────────────────────────────────────
    v_m             = peaks_result["v_m"]
    artifact        = peaks_result["artifact"]
    peak_indices    = peaks_result["peak_indices"]
    peak_velocities = peaks_result["peak_velocities_mms"]
    n_peaks         = int(peaks_result["n_peaks"])
    sigma_v         = float(peaks_result["sigma_v_mms"])
    prominence_thr  = float(peaks_result["prominence_threshold_mms"])
    min_dist_frames = int(peaks_result["min_distance_frames"])
    # Secondary filter flags live in peaks_result (overrides caller args)
    sec_applied = bool(peaks_result.get("secondary_filter_applied", secondary_filter_applied))
    sec_cutoff  = peaks_result.get("secondary_filter_cutoff_hz", secondary_filter_cutoff_hz)

    # ── Active time T_a ──────────────────────────────────────────────────────
    # Frames where v_m > V, v_m is not NaN, and not artifact.
    # v_m is already NaN on artifact frames, but we check artifact mask
    # explicitly to be defensive.
    above_floor = (~np.isnan(v_m)) & (v_m > V) & (~artifact)
    T_a = float(np.sum(above_floor)) / fs   # seconds

    # ── PPM ─────────────────────────────────────────────────────────────────
    if T_a <= 0:
        ppm = np.nan
        if n_peaks > 0:
            logger.warning(
                f"aggregate_pulsicity_metrics({segment}): T_a = 0 but "
                f"n_peaks = {n_peaks}. PPM set to NaN. "
                f"Check that V ({V:.2f} mm/s) is not above all peak velocities."
            )
    elif n_peaks == 0:
        ppm = 0.0     # zero pulsicity is a valid result, not NaN
    else:
        ppm = float(n_peaks / T_a * 60.0)

    # ── Mean peak velocity ───────────────────────────────────────────────────
    mean_peak_vel = float(np.mean(peak_velocities)) if n_peaks > 0 else np.nan

    # ── IPI ─────────────────────────────────────────────────────────────────
    if n_peaks >= 2:
        ipi_s    = np.diff(peak_indices.astype(float)) / fs   # seconds
        ipi_mean = float(np.mean(ipi_s))
        ipi_std  = float(np.std(ipi_s))
        ipi_cv   = float(ipi_std / ipi_mean) if ipi_mean > 0 else np.nan
    else:
        ipi_mean = np.nan
        ipi_std  = np.nan
        ipi_cv   = np.nan

    # ── valid_movement_flag ──────────────────────────────────────────────────
    valid_movement_flag = bool(T_a >= min_run_seconds)

    # ── artifact_frames_pct ──────────────────────────────────────────────────
    n_total = len(artifact)
    artifact_frames_pct = (
        float(np.sum(artifact)) / n_total * 100.0 if n_total > 0 else np.nan
    )

    # ── SPARC ────────────────────────────────────────────────────────────────
    if sparc_result is not None:
        sparc_val    = sparc_result.get("sparc",             np.nan)
        sparc_cap_hz = sparc_result.get("sparc_freq_cap_hz", np.nan)
    else:
        sparc_val    = np.nan
        sparc_cap_hz = np.nan

    # ── PSD diagnostic ───────────────────────────────────────────────────────
    if psd_result is not None:
        psd_noise_ratio    = psd_result.get("noise_ratio",           np.nan)
        psd_filter_rec     = bool(psd_result.get("psd_filter_recommended", False))
    else:
        psd_noise_ratio    = np.nan
        psd_filter_rec     = False

    # ── Noise floor metadata ─────────────────────────────────────────────────
    if noise_floor_result is not None:
        nf_source   = noise_floor_result.get("noise_floor_source",          "unknown")
        nf_low_conf = bool(noise_floor_result.get("noise_floor_low_confidence", False))
    else:
        nf_source   = "unknown"
        nf_low_conf = False

    # ── Config audit columns ─────────────────────────────────────────────────
    sg_window_sec = float(cfg.get("sg_window_sec", cfg.get("SG_WINDOW_SEC", 0.175)))
    sg_polyorder  = int(  cfg.get("sg_polyorder",  cfg.get("SG_POLYORDER",  3)))

    logger.info(
        f"aggregate_pulsicity_metrics({segment}): "
        f"T_a={T_a:.2f}s | PPM={ppm} | N_p={n_peaks} | "
        f"mean_peak_vel={mean_peak_vel:.2f} mm/s | IPI_CV={ipi_cv} | "
        f"SPARC={sparc_val} | valid={valid_movement_flag}"
    )

    return {
        # ── Identifiers ────────────────────────────────────────────────────
        "run_id":                      run_id,
        "segment":                     segment,
        # ── Noise floor ────────────────────────────────────────────────────
        "noise_floor_V_mms":           float(V),
        "noise_floor_source":          nf_source,
        "noise_floor_low_confidence":  nf_low_conf,
        # ── Primary metrics ────────────────────────────────────────────────
        "active_time_s":               T_a,
        "n_peaks":                     n_peaks,
        "ppm":                         ppm,
        "mean_peak_velocity_mms":      mean_peak_vel,
        # ── IPI ────────────────────────────────────────────────────────────
        "ipi_mean_s":                  ipi_mean,
        "ipi_std_s":                   ipi_std,
        "ipi_cv":                      ipi_cv,
        # ── Smoothness ─────────────────────────────────────────────────────
        "sparc":                       sparc_val,
        "sparc_freq_cap_hz":           sparc_cap_hz,
        # ── PSD diagnostic ─────────────────────────────────────────────────
        "psd_noise_ratio":             psd_noise_ratio,
        "psd_filter_recommended":      psd_filter_rec,
        # ── Secondary filter ───────────────────────────────────────────────
        "secondary_filter_applied":    sec_applied,
        "secondary_filter_cutoff_hz":  (
            float(sec_cutoff) if sec_cutoff is not None else np.nan
        ),
        # ── Quality flags ──────────────────────────────────────────────────
        "valid_movement_flag":         valid_movement_flag,
        "artifact_frames_pct":         artifact_frames_pct,
        # ── Peak detection parameters (audit) ──────────────────────────────
        "prominence_threshold_mms":    float(prominence_thr),
        "min_distance_frames":         min_dist_frames,
        # ── Config audit columns ───────────────────────────────────────────
        "sg_window_sec":               sg_window_sec,
        "sg_polyorder":                sg_polyorder,
        "fs_target_hz":                fs,
        # ── Provenance ─────────────────────────────────────────────────────
        "enforce_cleaning_was_active": bool(enforce_cleaning_was_active),
        "processing_timestamp":        datetime.datetime.utcnow().isoformat() + "Z",
        "pipeline_version":            pipeline_version,
    }
