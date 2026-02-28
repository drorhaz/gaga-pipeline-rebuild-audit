"""
Winter Residual Analysis & Position Filtering Module

This module implements objective low-pass cutoff selection using Winter residual analysis
and zero-lag Butterworth filtering for position data only.

Pipeline placement: After resampling to perfect grid, before derivative computation.

References:
    Winter, D. A. (2009). Biomechanics and motor control of human movement. 4th ed.
    Wren et al. (2006). Efficacy of clinical gait analysis. Gait & Posture, 22(4), 295-305.
"""

import numpy as np
import pandas as pd
import logging
from typing import Tuple, List, Dict, Optional, Union
from scipy.signal import butter, filtfilt, savgol_filter

logger = logging.getLogger(__name__)

# Import PSD validation (optional - only if module exists)
try:
    # Try relative import first (when used as package)
    from .filter_validation import (
        validate_winter_filter_multi_signal,
        check_filter_cutoff_validity,
        analyze_filter_psd_preservation
    )
    PSD_VALIDATION_AVAILABLE = True
except ImportError:
    try:
        # Fallback to absolute import (when run from notebook)
        from filter_validation import (
            validate_winter_filter_multi_signal,
            check_filter_cutoff_validity,
            analyze_filter_psd_preservation
        )
        PSD_VALIDATION_AVAILABLE = True
    except ImportError:
        PSD_VALIDATION_AVAILABLE = False
        logger.warning("PSD validation module not available - validation metrics will be skipped")


# =============================================================================
# GATE 3: PER-REGION BODY DEFINITIONS (Fixed Cutoffs for Research Reproducibility)
# =============================================================================
# Fixed per-region cutoffs based on biomechanical literature (Winter, 2009; Robertson, 2014)
# Rationale: Distal segments move faster than proximal; dance/athletic movements need
# higher cutoffs than walking gait. Fixed values ensure reproducibility across sessions.
#
# Literature support:
#   - Walking: 6 Hz (Winter 2009)
#   - Running: 6-12 Hz (Robertson 2014)
#   - Athletic/Dance: 8-15 Hz (sports biomechanics consensus)
#   - Hand manipulation: up to 20 Hz (upper extremity studies)

BODY_REGIONS = {
    'trunk': {
        'patterns': ['Pelvis', 'Spine', 'Torso', 'Hips', 'Abdomen', 'Chest', 'Back'],
        'fixed_cutoff': 6,            # Conservative: 6 Hz for core stability (Winter 2009 gait standard)
        'cutoff_range': (4, 10),      # Range for validation only
        'rationale': 'Core movements - 6 Hz based on gait literature, conservative for trunk stability'
    },
    'head': {
        'patterns': ['Head', 'Neck'],
        'fixed_cutoff': 8,            # Moderate: 8 Hz for head dynamics
        'cutoff_range': (6, 12),      # Range for validation only
        'rationale': 'Head dynamics - 8 Hz preserves head movements while reducing noise'
    },
    'upper_proximal': {
        'patterns': ['Shoulder', 'Clavicle', 'Scapula', 'UpperArm', 'Arm'],
        'fixed_cutoff': 8,            # Moderate: 8 Hz for shoulder/arm
        'cutoff_range': (6, 12),      # Range for validation only
        'rationale': 'Shoulder/upper arm - 8 Hz preserves arm swings and reaches'
    },
    'upper_distal': {
        'patterns': ['Elbow', 'Forearm', 'ForeArm', 'Wrist', 'Hand', 'Finger', 'Thumb', 'Index', 'Middle', 'Ring', 'Pinky'],
        'fixed_cutoff': 12,           # Higher: 12 Hz for fast hand/finger movements in Gaga dance
        'cutoff_range': (8, 14),      # Range for validation only
        'rationale': 'Hands/fingers - 12 Hz preserves hand flicks and finger articulation (Gaga dance standard)'
    },
    'lower_proximal': {
        'patterns': ['Thigh', 'UpLeg', 'UpperLeg', 'Knee'],
        'fixed_cutoff': 8,            # Moderate: 8 Hz for leg dynamics
        'cutoff_range': (6, 12),      # Range for validation only
        'rationale': 'Upper leg - 8 Hz preserves leg swings and knee movements'
    },
    'lower_distal': {
        'patterns': ['Ankle', 'Leg', 'LowerLeg', 'Foot', 'Toe', 'ToeBase', 'Heel'],
        'fixed_cutoff': 10,           # Higher: 10 Hz for foot strikes and toe movements
        'cutoff_range': (8, 14),      # Range for validation only
        'rationale': 'Lower leg/foot - 10 Hz preserves foot strikes and toe articulation'
    }
}

# Global search range for Winter analysis (Gate 3)
WINTER_FMIN = 1   # Minimum cutoff frequency (Hz)
WINTER_FMAX = 16  # Maximum cutoff frequency (Hz) - expanded from 12 for Gaga


def classify_marker_region(marker_name: str) -> str:
    """
    Classify a marker into a body region based on name patterns.
    
    Args:
        marker_name: Marker column name (e.g., 'RightHand__px')
        
    Returns:
        Region name ('trunk', 'head', 'upper_proximal', 'upper_distal', 
                     'lower_proximal', 'lower_distal', 'unknown')
                     
    Note:
        Unknown markers default to 'upper_proximal' (8 Hz) to avoid
        frequency compression. The previous default of 'upper_distal'
        (12 Hz) caused all unrecognized markers to receive a high-frequency
        floor, compressing the 6-12 Hz dynamic range into 10-12 Hz.
    """
    # Extract base marker name (remove axis suffix)
    base_name = marker_name.replace('__px', '').replace('__py', '').replace('__pz', '')
    
    # Check each region's patterns
    for region, config in BODY_REGIONS.items():
        for pattern in config['patterns']:
            if pattern.lower() in base_name.lower():
                return region
    
    # Default to upper_proximal (8 Hz) for unknown markers.
    # Rationale: upper_proximal sits at the midpoint of the 6-12 Hz Smart Bias
    # range, avoiding the frequency compression that occurred when defaulting
    # to upper_distal (12 Hz). This preserves the Trunk-Distal decoupling.
    logger.warning(f"Marker '{marker_name}' not matched to any region, "
                   f"defaulting to 'upper_proximal' (8 Hz). "
                   f"Consider adding this marker to BODY_REGIONS patterns.")
    return 'upper_proximal'


# =============================================================================
# CHUNKING GUARD — NaN-safe filtfilt for gappy signals
# =============================================================================

def _find_contiguous_finite_segments(x: np.ndarray):
    """
    Return list of (start, end) slices for contiguous runs of finite values in *x*.
    Each segment covers x[start:end] (end is exclusive).
    """
    finite = np.isfinite(x)
    diff = np.diff(np.concatenate(([0], finite.astype(np.int8), [0])))
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]
    return list(zip(starts.tolist(), ends.tolist()))


def chunked_filtfilt(b: np.ndarray,
                     a: np.ndarray,
                     x: np.ndarray,
                     padlen: Optional[int] = None,
                     return_meta: bool = False):
    """
    NaN-safe wrapper around ``scipy.signal.filtfilt``.

    Finds contiguous segments of finite data and applies ``filtfilt`` to each
    segment independently.  Segments shorter than or equal to *padlen* are
    returned **unfiltered but valid** (no scipy call, no ringing).  NaN
    positions in the input are preserved as NaN in the output.

    Parameters
    ----------
    b, a : array_like
        Numerator / denominator of the IIR filter (e.g. from ``butter``).
    x : np.ndarray
        1-D signal, may contain NaNs.
    padlen : int, optional
        Padding length passed to ``filtfilt``.  If *None* the scipy default
        ``3 * max(len(a), len(b))`` is used.
    return_meta : bool
        If True return ``(out, meta_dict)`` instead of just ``out``.

    Returns
    -------
    np.ndarray  or  (np.ndarray, dict)
        Filtered signal, same shape as *x*.  NaNs where *x* was NaN;
        unfiltered where segment was too short.
        When *return_meta* is True the second element is a dict with:
        ``n_chunks``, ``n_chunks_filtered``, ``n_chunks_too_short``,
        ``short_chunk_frames`` (total frames left unfiltered due to padlen).
    """
    if padlen is None:
        padlen = 3 * max(len(a), len(b))

    out = np.full_like(x, np.nan, dtype=float)
    segments = _find_contiguous_finite_segments(x)

    n_filtered = 0
    n_too_short = 0
    short_chunk_frames = 0

    for s, e in segments:
        seg = x[s:e].astype(float)
        if len(seg) > padlen:
            out[s:e] = filtfilt(b, a, seg, padlen=padlen)
            n_filtered += 1
        else:
            out[s:e] = seg
            n_too_short += 1
            short_chunk_frames += len(seg)

    if return_meta:
        meta = {
            "n_chunks": len(segments),
            "n_chunks_filtered": n_filtered,
            "n_chunks_too_short": n_too_short,
            "short_chunk_frames": short_chunk_frames,
        }
        return out, meta
    return out


# =============================================================================
# CHUNKING GUARD — NaN-safe Savitzky-Golay for gappy signals
# =============================================================================

def chunked_savgol(x: np.ndarray,
                   window_length: int,
                   polyorder: int,
                   deriv: int = 0,
                   delta: float = 1.0,
                   mode: str = 'interp',
                   return_meta: bool = False):
    """
    NaN-safe wrapper around ``scipy.signal.savgol_filter``.

    Finds contiguous segments of finite data and applies the Savitzky-Golay
    filter to each segment independently, preventing NaN bleed where the
    filter window would otherwise bridge a data gap.

    Three-tier segment handling:

    * **Tier 1** (``seg_len >= window_length``): full SavGol with the
      requested window.
    * **Tier 2** (``min_window <= seg_len < window_length``): SavGol with
      the window reduced to the largest odd integer ``<= seg_len``.
    * **Tier 3** (``seg_len < min_window``): raw pass-through for
      ``deriv == 0`` (smoothing only); NaN for ``deriv > 0`` (derivative
      is undefined with too few points).

    ``min_window`` is the smallest odd integer ``>= polyorder + 2``, which
    is the absolute minimum scipy allows for ``savgol_filter``.

    Parameters
    ----------
    x : np.ndarray
        1-D signal, may contain NaNs / Infs.
    window_length : int
        Nominal SavGol window (odd, ``>= polyorder + 1``).
    polyorder : int
        Polynomial order.
    deriv : int
        Derivative order (0 = smooth, 1 = velocity, 2 = acceleration).
    delta : float
        Sample spacing (``1.0 / fs``).
    mode : str
        Boundary mode passed to ``savgol_filter`` (default ``'interp'``).
    return_meta : bool
        If True return ``(out, meta_dict)`` instead of just ``out``.

    Returns
    -------
    np.ndarray  or  (np.ndarray, dict)
        Filtered signal, same shape as *x*.  NaN where *x* was non-finite
        or where the segment was too short for the requested derivative.
    """
    out = np.full_like(x, np.nan, dtype=float)
    segments = _find_contiguous_finite_segments(x)

    # Smallest usable odd window for this polyorder
    min_window = polyorder + 2 if (polyorder + 2) % 2 == 1 else polyorder + 3

    n_full = 0
    n_reduced = 0
    n_too_short = 0
    too_short_frames = 0

    for s, e in segments:
        seg = x[s:e].astype(float)
        seg_len = len(seg)

        if seg_len >= window_length:
            # Tier 1 — nominal window
            out[s:e] = savgol_filter(seg, window_length, polyorder,
                                     deriv=deriv, delta=delta, mode=mode)
            n_full += 1

        elif seg_len >= min_window:
            # Tier 2 — reduced window (largest odd <= seg_len)
            reduced_w = seg_len if seg_len % 2 == 1 else seg_len - 1
            out[s:e] = savgol_filter(seg, reduced_w, polyorder,
                                     deriv=deriv, delta=delta, mode=mode)
            n_reduced += 1

        else:
            # Tier 3 — too short for any polynomial fit
            if deriv == 0:
                out[s:e] = seg  # pass-through raw values
            # else: leave as NaN — derivative is undefined
            n_too_short += 1
            too_short_frames += seg_len

    if return_meta:
        meta = {
            "n_chunks": len(segments),
            "n_full": n_full,
            "n_reduced": n_reduced,
            "n_too_short": n_too_short,
            "too_short_frames": too_short_frames,
        }
        return out, meta
    return out


# =============================================================================
# ADAPTIVE SAVGOL WINDOWING — per-joint frequency-aware W_LEN
# =============================================================================

def _round_to_odd(x: float) -> int:
    """Round to nearest odd integer.  e.g. 15.625 → 15, 20.83 → 21."""
    return 2 * int(round((x - 1) / 2)) + 1


def compute_adaptive_sg_windows(
    per_joint_cutoffs: dict,
    fs: float,
    polyorder: int = 3,
    multiplier: float = 1.2,
    floor_w: int = 7,
    ceiling_w: int = 21,
) -> tuple:
    """
    Compute per-segment Savitzky-Golay window lengths from Butterworth cutoffs.

    For each segment (e.g. ``Hips``), the window is chosen so that the SavGol
    effective cutoff is approximately ``multiplier * f_butter``, preventing the
    differentiator from discarding bandwidth preserved by Step 04.

    Formula (inverted from the SavGol 3-dB approximation)::

        W = round_odd( (polyorder + 1) * fs / (3.2 * multiplier * f_butter) )

    Per-axis cutoffs (``Hips__px``, ``Hips__py``, ``Hips__pz``) are aggregated
    per segment via ``max`` so that all three axes share one window.

    Parameters
    ----------
    per_joint_cutoffs : dict
        ``{column_name: cutoff_hz}`` — e.g. ``{"Hips__px": 6.0, ...}``.
        May also contain quaternion columns (``__qx`` etc.) which are ignored.
    fs : float
        Sampling rate in Hz.
    polyorder : int
        SavGol polynomial order.
    multiplier : float
        Target SavGol F_3dB = multiplier * f_butter.
    floor_w : int
        Minimum allowed window length (odd, >= polyorder + 2).
    ceiling_w : int
        Maximum allowed window length (odd).

    Returns
    -------
    w_len_map : dict
        ``{segment_name: window_length}`` — odd integers in [floor_w, ceiling_w].
    audit : dict
        ``{segment_name: {butter_cutoff_hz, sg_w_len, sg_f3db_hz, actual_multiplier}}``.
    """
    if floor_w % 2 == 0:
        floor_w += 1
    if ceiling_w % 2 == 0:
        ceiling_w -= 1
    floor_w = max(floor_w, polyorder + 2 if (polyorder + 2) % 2 == 1 else polyorder + 3)

    seg_cutoffs: dict = {}
    for col, cutoff in per_joint_cutoffs.items():
        if cutoff is None:
            continue
        # Only position columns (__px, __py, __pz)
        for suffix in ('__px', '__py', '__pz'):
            if col.endswith(suffix):
                seg = col[: -len(suffix)]
                seg_cutoffs.setdefault(seg, []).append(float(cutoff))
                break

    w_len_map = {}
    audit = {}
    for seg, cutoffs in seg_cutoffs.items():
        f_butter = max(cutoffs)
        f_target = multiplier * f_butter
        raw_w = (polyorder + 1) * fs / (3.2 * f_target)
        w = _round_to_odd(raw_w)
        w = max(floor_w, min(ceiling_w, w))
        if w % 2 == 0:
            w += 1
        f3db = (polyorder + 1) * fs / (3.2 * w)
        actual_mult = f3db / f_butter if f_butter > 0 else 0.0

        w_len_map[seg] = w
        audit[seg] = {
            "butter_cutoff_hz": round(f_butter, 2),
            "sg_w_len": w,
            "sg_f3db_hz": round(f3db, 2),
            "actual_multiplier": round(actual_mult, 2),
        }

    return w_len_map, audit


def compute_adaptive_sg_windows_from_regions(
    region_cutoffs: dict,
    joint_names: list,
    fs: float,
    polyorder: int = 3,
    multiplier: float = 1.2,
    floor_w: int = 7,
    ceiling_w: int = 21,
) -> tuple:
    """
    Fallback: compute per-segment SavGol windows from region-level cutoffs.

    Maps each joint to its body region via :func:`classify_marker_region`,
    then uses the region's mean Butterworth cutoff.

    Parameters
    ----------
    region_cutoffs : dict
        ``{region_name: mean_cutoff_hz}`` from filtering_summary.json.
    joint_names : list
        Segment names present in the dataset (e.g. ``["Hips", "Head", ...]``).
    fs, polyorder, multiplier, floor_w, ceiling_w :
        Same as :func:`compute_adaptive_sg_windows`.

    Returns
    -------
    w_len_map, audit : same structure as :func:`compute_adaptive_sg_windows`.
    """
    per_joint_cutoffs = {}
    for seg in joint_names:
        region = classify_marker_region(f"{seg}__px")
        cutoff = region_cutoffs.get(region)
        if cutoff is not None:
            for axis in ('px', 'py', 'pz'):
                per_joint_cutoffs[f"{seg}__{axis}"] = float(cutoff)
    return compute_adaptive_sg_windows(
        per_joint_cutoffs, fs, polyorder, multiplier, floor_w, ceiling_w,
    )


# =============================================================================
# DYNAMIC RMS WINDOWING — energetic-mask builder for non-stationary signals
# =============================================================================

def compute_energetic_mask(signal: np.ndarray,
                           fs: float,
                           window_sec: float = 1.0,
                           energy_quantile: float = 0.80,
                           min_valid_frac: float = 0.50) -> np.ndarray:
    """
    Build a boolean mask that is *True* for samples inside the most energetic
    windows of a 1-D signal.

    Used by ``winter_residual_analysis`` so that the residual RMS is computed
    only where the joint is actively moving, preventing long stillness from
    dragging the optimal cutoff to artificially low frequencies.

    Parameters
    ----------
    signal : np.ndarray
        1-D position signal (may contain NaNs).
    fs : float
        Sampling rate (Hz).
    window_sec : float
        Sliding-window length in seconds (default 1.0 s).
    energy_quantile : float
        Percentile threshold (0–1).  Windows with energy above this quantile
        are selected (default 0.80 = top 20 %).
    min_valid_frac : float
        Minimum fraction of finite samples required in a window for its energy
        to be considered valid (default 0.50).

    Returns
    -------
    np.ndarray
        Boolean mask of shape ``(len(signal),)``.  *True* for every sample that
        falls inside at least one top-energy window.  If no windows pass
        validity or the signal is too short, returns an all-True mask (fallback
        to global RMS behaviour).
    """
    T = len(signal)
    win = max(1, int(round(window_sec * fs)))

    if T < win:
        return np.ones(T, dtype=bool)

    n_windows = T - win + 1
    finite = np.isfinite(signal).astype(float)

    finite_cumsum = np.concatenate(([0.0], np.cumsum(finite)))
    valid_counts = finite_cumsum[win:] - finite_cumsum[:n_windows]
    min_count = min_valid_frac * win

    sig = signal.copy().astype(float)
    sig[~np.isfinite(sig)] = 0.0

    cumsum = np.concatenate(([0.0], np.cumsum(sig)))
    cumsum2 = np.concatenate(([0.0], np.cumsum(sig ** 2)))

    window_sum = cumsum[win:] - cumsum[:n_windows]
    window_sum2 = cumsum2[win:] - cumsum2[:n_windows]
    with np.errstate(invalid="ignore"):
        energy = (window_sum2 / valid_counts) - (window_sum / valid_counts) ** 2

    energy[valid_counts < min_count] = np.nan

    finite_energies = energy[np.isfinite(energy)]
    if len(finite_energies) == 0:
        return np.ones(T, dtype=bool)

    threshold = np.percentile(finite_energies, energy_quantile * 100)
    top_windows = np.where(np.isfinite(energy) & (energy >= threshold))[0]

    if len(top_windows) == 0:
        return np.ones(T, dtype=bool)

    mask = np.zeros(T, dtype=bool)
    for start in top_windows:
        mask[start:start + win] = True
    return mask


def winter_residual_analysis(signal: np.ndarray, 
                       fs: float, 
                       fmin: int = 1, 
                       fmax: int = 16,
                       min_cutoff: Optional[float] = None,
                       body_region: str = "general",
                       return_details: bool = False,
                       validation_mode: bool = False,
                       energetic_mask: Optional[np.ndarray] = None) -> Union[float, Dict]:
    """
    Perform Winter residual analysis to determine optimal low-pass cutoff frequency.
    
    Gate 3 Implementation: Expanded search range [1, 16] Hz for Gaga high-intensity.
    
    The method analyzes residual RMS across different cutoff frequencies to find the
    knee point where further filtering provides diminishing returns.
    
    Args:
        signal: Input signal array (1D)
        fs: Sampling frequency in Hz
        fmin: Minimum cutoff frequency to test (Hz)
        fmax: Maximum cutoff frequency to test (Hz) - 16Hz for Gaga dynamics
        min_cutoff: Biomechanically-informed minimum cutoff (Hz). If provided, 
                   Winter result will be clamped to this minimum with logging
        body_region: Body region for biomechanical context ("trunk", "distal", "general")
        return_details: If True, return dict with full analysis details instead of just cutoff
        validation_mode: If True, return raw Winter result without weighted compromise (for validation)
        energetic_mask: Optional boolean array, same length as *signal*.  When
            provided, residual RMS is computed only at positions where the mask
            is True **and** the residual is finite (Dynamic RMS Windowing).
            When *None*, global RMS is used (legacy behaviour).
        
    Returns:
        If return_details=False: Optimal cutoff frequency (Hz)
        If return_details=True: Dict with {
            'cutoff_hz': final cutoff,
            'raw_cutoff_hz': pre-guardrail cutoff,
            'method_used': detection method,
            'guardrail_applied': bool,
            'guardrail_delta_hz': how much guardrail changed the cutoff,
            'knee_point_found': bool (True if real knee point was found),
            'rms_values': array of RMS at each test frequency,
            'test_frequencies': array of test frequencies,
            'residual_rms_final': RMS at final cutoff,
            'search_range_hz': [fmin, fmax]
        }
        
    Reference:
        Winter, D. A. (2009). Biomechanics and motor control of human movement.
        Note: fmax=16Hz for Gaga. If cutoff=fmax, method failed - investigate pipeline.
    """
    # Safety net: filtfilt with a 2nd-order Butterworth requires padlen = 3*max(len(a),len(b)) = 9.
    # Signal must be strictly longer than padlen. Use 15 as safe floor (margin for edge effects).
    _MIN_WINTER_LEN = 15
    if len(signal) < _MIN_WINTER_LEN:
        logger.warning(
            f"Signal too short ({len(signal)} frames, need >= {_MIN_WINTER_LEN}) "
            f"for Winter residual analysis. Returning fmax={fmax} Hz fallback."
        )
        if return_details:
            return {
                'cutoff_hz': float(fmax),
                'raw_cutoff_hz': float(fmax),
                'method_used': 'signal_too_short_fallback',
                'guardrail_applied': False,
                'guardrail_delta_hz': 0.0,
                'knee_point_found': False,
                'rms_values': [],
                'test_frequencies': [],
                'residual_rms_final': 0.0,
                'search_range_hz': [fmin, fmax],
                'failure_reason': f"Signal too short ({len(signal)} frames < {_MIN_WINTER_LEN})"
            }
        return float(fmax)

    # Convert to float and detrend
    x = signal.astype(float)
    x = x - np.mean(x)
    
    # Check for completely flat signal (no variation) - this should cause failure
    if np.std(x) < 1e-10:  # Essentially zero variation
        logger.error(f"WINTER ANALYSIS FAILED: signal has no variation (std={np.std(x):.2e}). "
                    f"Cannot perform meaningful residual analysis.")
        if return_details:
            return {
                'cutoff_hz': float(fmax),
                'raw_cutoff_hz': float(fmax),
                'method_used': 'flat_signal_failure',
                'guardrail_applied': False,
                'guardrail_delta_hz': 0.0,
                'knee_point_found': False,
                'rms_values': [],
                'test_frequencies': [],
                'residual_rms_final': 0.0,
                'failure_reason': f"Signal has no variation (std={np.std(x):.2e}), cannot perform residual analysis"  # GATE 3
            }
        return float(fmax)
    
    # Test cutoff frequencies
    cutoffs = np.arange(fmin, fmax + 1)
    rms_values = np.zeros(len(cutoffs))

    # Dynamic RMS Windowing tracking
    _MIN_ENERGETIC_SAMPLES = 50
    _dynamic_rms_used = energetic_mask is not None
    _dynamic_rms_fallback = False

    if energetic_mask is None:
        _rms_mask = np.ones(len(x), dtype=bool)
    else:
        _rms_mask = energetic_mask
    _rms_mask = _rms_mask & np.isfinite(x)

    if _rms_mask.sum() < _MIN_ENERGETIC_SAMPLES:
        logger.info("Energetic mask has < %d valid samples; falling back to global RMS.", _MIN_ENERGETIC_SAMPLES)
        _rms_mask = np.isfinite(x)
        if _dynamic_rms_used:
            _dynamic_rms_fallback = True

    for i, fc in enumerate(cutoffs):
        b, a = butter(N=2, Wn=fc/(0.5*fs), btype='low')
        xf = chunked_filtfilt(b, a, x)
        residual = x - xf
        valid = _rms_mask & np.isfinite(residual)
        if valid.sum() > 0:
            rms_values[i] = np.sqrt(np.mean(residual[valid]**2))
        else:
            rms_values[i] = 0.0
    
    # Enhanced knee rule: find optimal cutoff using multiple criteria
    r_floor = rms_values[-1]  # RMS at fmax
    r_ceiling = rms_values[0]  # RMS at fmin
    
    # Check if RMS curve is essentially flat (no clear knee point)
    rms_range_ratio = (r_ceiling - r_floor) / (r_ceiling + 1e-10)
    curve_is_flat = rms_range_ratio < 0.15  # Less than 15% variation = flat curve
    
    # Method 1: Strict knee rule (1.05 * r_floor)
    knee_candidates_strict = np.where(rms_values <= 1.05 * r_floor)[0]
    
    # Method 2: Relaxed knee rule (1.10 * r_floor) for smooth curves
    knee_candidates_relaxed = np.where(rms_values <= 1.10 * r_floor)[0]
    
    # Method 3: Point of diminishing returns (largest relative drop)
    rms_drops = np.diff(rms_values) / (rms_values[:-1] + 1e-10)  # Relative drop between consecutive cutoffs
    best_drop_idx = np.argmax(np.abs(rms_drops)) + 1  # Index after the largest drop
    max_drop_magnitude = np.abs(rms_drops[best_drop_idx - 1]) if len(rms_drops) > 0 else 0
    
    # Collect all candidate cutoffs from different methods
    candidates = []
    knee_point_found = False
    
    # Only use strict/relaxed knee if the curve isn't flat
    if not curve_is_flat:
        # Add strict knee candidates (prefer lowest)
        if len(knee_candidates_strict) > 0:
            candidates.append((cutoffs[knee_candidates_strict[0]], "strict_knee"))
            knee_point_found = True
        
        # Add relaxed knee candidates (prefer lowest)
        if len(knee_candidates_relaxed) > 0:
            candidates.append((cutoffs[knee_candidates_relaxed[0]], "relaxed_knee"))
            knee_point_found = True
    
    # Method 3: Point of diminishing returns - only if there's a significant drop
    if max_drop_magnitude > 0.05:  # At least 5% relative drop
        diminishing_cutoff = max(4, cutoffs[best_drop_idx])
        if diminishing_cutoff <= 10:  # Only add if in reasonable dance range
            candidates.append((diminishing_cutoff, "diminishing_returns"))
            knee_point_found = True
    
    # Choose cutoff from candidates
    if candidates:
        candidates.sort(key=lambda x: x[0])  # Sort by cutoff frequency (lowest first)
        
        if validation_mode:
            # VALIDATION MODE: Return the strict_knee (where RMS flattens) - most meaningful for validation
            # This tells us "Winter says you need at least X Hz to capture useful signal"
            # Also capture diminishing_returns for reference (where biggest RMS drop happens)
            strict_knee = next((c for c in candidates if c[1] == "strict_knee"), None)
            relaxed_knee = next((c for c in candidates if c[1] == "relaxed_knee"), None)
            diminishing = next((c for c in candidates if c[1] == "diminishing_returns"), None)
            
            # Store both values for reporting
            # Note: diminishing_returns has max(4, ...) floor in the candidate generation
            # Get the raw best_drop_idx value for true diminishing_returns
            raw_diminishing_hz = float(cutoffs[best_drop_idx]) if 'best_drop_idx' in dir() else None
            
            # Prefer strict_knee for validation (where RMS actually stabilizes)
            if strict_knee:
                optimal_fc, method_used = strict_knee
                method_used = f"validation_strict_knee"
            elif relaxed_knee:
                optimal_fc, method_used = relaxed_knee
                method_used = f"validation_relaxed_knee"
            else:
                optimal_fc, method_used = candidates[0]
                method_used = f"validation_raw_{method_used}"
        else:
            # DATA-DRIVEN MODE: Use weighted compromise when needed
            # Get region configuration for biomechanical minimum
            # Default range (6, 12) aligns with the Smart Bias Lerp bounds
            region_config = BODY_REGIONS.get(body_region, {'cutoff_range': (6, 12)})
            min_cutoff_region = region_config['cutoff_range'][0]
            
            # Find the diminishing_returns and strict_knee candidates
            diminishing_candidate = next((c for c in candidates if c[1] == "diminishing_returns"), None)
            strict_knee_candidate = next((c for c in candidates if c[1] == "strict_knee"), None)
            relaxed_knee_candidate = next((c for c in candidates if c[1] == "relaxed_knee"), None)
            
            # Use higher knee candidate if available (prefer strict over relaxed)
            higher_knee_candidate = strict_knee_candidate or relaxed_knee_candidate
            
            # CONTINUOUS BIAS (Smart Weighting): region-aware weighted compromise
            # when diminishing_returns is below minimum and a higher knee-point exists.
            # Weights are derived from the body region's biomechanical expectation
            # (min_cutoff_region), NOT hardcoded. This prevents a single "gravity well"
            # cutoff across all body parts.
            if (diminishing_candidate and higher_knee_candidate and
                diminishing_candidate[0] < min_cutoff_region and
                higher_knee_candidate[0] > diminishing_candidate[0]):

                # --- Continuous Bias via Linear Interpolation (Lerp) ---
                # 1. Define the "Trust Range" based on human physiology
                #    6.0 Hz = Core/Stable regions (trust the low-freq diminishing_returns candidate)
                #    12.0 Hz = Distal/Agile regions (trust the high-freq strict_knee candidate)
                low_bound = 6.0
                high_bound = 12.0

                # 2. Calculate the "High-Freq Trust Factor" (0.0 to 1.0)
                #    Uses min_cutoff_region from BODY_REGIONS cutoff_range
                trust_factor = (min_cutoff_region - low_bound) / (high_bound - low_bound)
                trust_factor = np.clip(trust_factor, 0.0, 1.0)

                # 3. Map to Weighting (clamped for safety: never 100% of either extreme)
                #    Range: knee_weight 0.2 (core/trunk) to 0.8 (distal)
                knee_weight = 0.2 + (0.6 * trust_factor)
                diminishing_weight = 1.0 - knee_weight

                # 4. Calculate Final Weighted Cutoff
                weighted_cutoff = (diminishing_candidate[0] * diminishing_weight) + (higher_knee_candidate[0] * knee_weight)
                optimal_fc = round(weighted_cutoff, 1)
                method_used = (f"smart_bias(dim={diminishing_candidate[0]:.1f}*{diminishing_weight:.2f}"
                               f"+knee={higher_knee_candidate[0]:.1f}*{knee_weight:.2f})")

                logger.info(f"SMART BIAS for {body_region}: min_cutoff_region={min_cutoff_region}Hz -> "
                           f"trust_factor={trust_factor:.2f}, knee_weight={knee_weight:.2f}. "
                           f"diminishing={diminishing_candidate[0]:.1f}Hz, strict_knee={higher_knee_candidate[0]:.1f}Hz. "
                           f"Result: {optimal_fc:.1f}Hz")
            else:
                # Original behavior: pick the lowest candidate
                optimal_fc, method_used = candidates[0]
    else:
        # NO KNEE POINT FOUND - Use Standard Protocol (fixed_cutoff) as fallback
        # When adaptive analysis fails, fall back to the literature-based fixed cutoff
        # for the body region, NOT the upper range limit.
        # Default fallback uses upper_proximal (8 Hz) to avoid frequency compression.
        region_config = BODY_REGIONS.get(body_region, {'fixed_cutoff': 8, 'cutoff_range': (6, 12)})
        optimal_fc = region_config.get('fixed_cutoff', region_config['cutoff_range'][1])
        method_used = f"no_knee_point_standard_protocol_{body_region}"
        knee_point_found = False
        logger.warning(f"WINTER KNEE-POINT NOT FOUND for {body_region}: RMS curve is flat (range ratio={rms_range_ratio:.2%}). "
                      f"Using Standard Protocol fixed cutoff {optimal_fc} Hz (literature-based). "
                      f"This may indicate pre-smoothed data.")
    
    raw_optimal_fc = optimal_fc  # Store pre-guardrail value
    
    # Final validation: if we still get fmax, it means the data is very smooth
    if optimal_fc >= fmax - 1:
        optimal_fc = fmax
        method_used = "fmax_fallback"
        knee_point_found = False
        logger.info(f"RMS analysis suggests fmax ({optimal_fc} Hz) - fixed literature cutoff will be used instead. "
                   f"(This is expected with clean/pre-filtered data)")
    else:
        if knee_point_found:
            logger.info(f"Winter analysis: selected cutoff {optimal_fc} Hz ({method_used})")
        else:
            logger.warning(f"Winter analysis: using fallback cutoff {optimal_fc} Hz ({method_used}) - no clear knee point")
    
    # Apply biomechanical guardrails if min_cutoff is specified
    guardrail_applied = False
    guardrail_delta = 0.0
    
    if min_cutoff is not None:
        original_fc = optimal_fc
        optimal_fc = max(optimal_fc, min_cutoff)
        guardrail_delta = optimal_fc - original_fc
        
        if optimal_fc > original_fc:
            guardrail_applied = True
            logger.warning(f"BIOMECHANICAL GUARDRAIL OVERRIDE: Winter cutoff {original_fc:.1f} Hz "
                          f"clamped to {optimal_fc:.1f} Hz (min_cutoff={min_cutoff:.1f} Hz) "
                          f"for {body_region} region. Delta = +{guardrail_delta:.1f} Hz. "
                          f"This may indicate the data is pre-smoothed or contains low dynamics.")
        else:
            logger.info(f"BIOMECHANICAL GUARDRAIL: Winter cutoff {original_fc:.1f} Hz "
                        f"within acceptable range (>= {min_cutoff:.1f} Hz) for {body_region} region.")
    
    # Get final residual RMS at the chosen cutoff
    cutoff_idx = np.argmin(np.abs(cutoffs - optimal_fc))
    residual_rms_final = float(rms_values[cutoff_idx])
    
    # Calculate residual slope at the knee-point to assess convergence quality
    # Slope indicates how quickly the residual is decreasing at the selected cutoff
    if cutoff_idx > 0 and cutoff_idx < len(rms_values) - 1:
        # Use central difference for slope estimate
        residual_slope = (rms_values[cutoff_idx + 1] - rms_values[cutoff_idx - 1]) / 2.0
    elif cutoff_idx == 0:
        # Forward difference at boundary
        residual_slope = rms_values[1] - rms_values[0]
    else:
        # Backward difference at boundary
        residual_slope = rms_values[-1] - rms_values[-2]
    
    residual_slope = float(residual_slope)
    
    if return_details:
        # GATE 3 FIX: Generate human-readable failure reason for audit transparency
        failure_reason_detail = None
        if not knee_point_found:
            if curve_is_flat:
                failure_reason_detail = f"RMS curve is flat (range={rms_range_ratio:.1%}), no clear knee-point detected in {fmin}-{fmax}Hz range"
            elif optimal_fc >= fmax - 1:
                failure_reason_detail = f"Cutoff at fmax ({optimal_fc}Hz), residual slope did not plateau in {fmin}-{fmax}Hz range"
            else:
                failure_reason_detail = f"No knee-point found, using {method_used} fallback cutoff"
        elif guardrail_applied and guardrail_delta >= 2.0:
            failure_reason_detail = f"Biomechanical guardrail override: +{guardrail_delta:.1f}Hz from {raw_optimal_fc:.1f}Hz to {optimal_fc:.1f}Hz"
        
        # Extract all candidate values for detailed reporting
        strict_knee_hz = next((c[0] for c in candidates if c[1] == "strict_knee"), None) if candidates else None
        relaxed_knee_hz = next((c[0] for c in candidates if c[1] == "relaxed_knee"), None) if candidates else None
        diminishing_returns_hz = next((c[0] for c in candidates if c[1] == "diminishing_returns"), None) if candidates else None
        # Get raw diminishing_returns (before max(4, ...) floor)
        raw_diminishing_hz = float(cutoffs[best_drop_idx]) if 'best_drop_idx' in dir() and best_drop_idx < len(cutoffs) else None
        
        return {
            'cutoff_hz': float(optimal_fc),
            'raw_cutoff_hz': float(raw_optimal_fc),
            'method_used': method_used,
            'guardrail_applied': guardrail_applied,
            'guardrail_delta_hz': float(guardrail_delta),
            'knee_point_found': knee_point_found,
            'rms_values': rms_values.tolist(),
            'test_frequencies': cutoffs.tolist(),
            'residual_rms_final': residual_rms_final,
            'residual_slope': residual_slope,  # NEW: Slope at knee-point for convergence quality
            'rms_range_ratio': float(rms_range_ratio),
            'curve_is_flat': curve_is_flat,
            'search_range_hz': [fmin, fmax],
            'body_region': body_region,
            'failure_reason': failure_reason_detail,  # GATE 3: Detailed failure reason
            # Winter analysis breakdown for audit report
            'strict_knee_hz': float(strict_knee_hz) if strict_knee_hz else None,
            'relaxed_knee_hz': float(relaxed_knee_hz) if relaxed_knee_hz else None,
            'diminishing_returns_hz': float(diminishing_returns_hz) if diminishing_returns_hz else None,
            'raw_diminishing_hz': float(raw_diminishing_hz) if raw_diminishing_hz else None,
            'dynamic_rms_used': _dynamic_rms_used,
            'dynamic_rms_fallback_to_global': _dynamic_rms_fallback,
        }
    
    return float(optimal_fc)


# =============================================================================
# 3-STAGE SIGNAL CLEANING PIPELINE
# =============================================================================
# Generic "Gatekeeper" Architecture for handling artifacts and noise separately
# Stage 1: Artifact Detector (Z-Score + Velocity) - identifies tracking spikes
# Stage 2: Hampel Filter (Sliding Window Median) - removes outliers
# Stage 3: Adaptive Low-Pass (Winter's Residual Method) - per-joint optimal cutoff


def detect_artifact_gaps(signal: np.ndarray, 
                        fs: float,
                        velocity_limit: float = 1800.0,
                        zscore_threshold: float = 5.0) -> Tuple[np.ndarray, Dict]:
    """
    Stage 1: Artifact Detector using Z-Score + Velocity thresholds.

    Used by: 3-stage method (Stage 1). Detects position spikes via frame-to-frame
    velocity (diff(position)/dt) and flags frames for interpolation.

    Detects tracking artifacts (spikes) by identifying frames where:
    1. Velocity exceeds physiological limit (e.g. 5000 mm/s for position)
    2. Velocity is > zscore_threshold standard deviations from session mean

    Rationale: Configurable velocity_limit and zscore_threshold (config_v1.yaml)
    allow tuning; 5000 mm/s ≈ 5 m/s (very fast for body markers); 5σ flags
    extreme outliers while sparing normal dynamics. Validate with printed
    breakdown (velocity vs zscore) and frame counts.

    Args:
        signal: 1D position signal
        fs: Sampling frequency (Hz)
        velocity_limit: Physiological velocity limit in signal units per second
                       (e.g., 5000 mm/s for position, 1800 deg/s for angles)
        zscore_threshold: Z-score threshold for outlier detection (default: 5.0)

    Returns:
        artifact_mask: Boolean mask where True = frame marked for interpolation
        stats: Dict with n_velocity_spikes, n_zscore_spikes, n_frames_marked
    """
    if len(signal) < 3:
        return np.zeros(len(signal), dtype=bool), {
            "n_velocity_spikes": 0, "n_zscore_spikes": 0, "n_frames_marked": 0
        }

    # Compute velocity (change per frame, then convert to per-second)
    dt = 1.0 / fs
    velocity = np.diff(signal) / dt  # Units: signal_units/s

    # Compute session statistics
    velocity_mean = np.nanmean(velocity)
    velocity_std = np.nanstd(velocity)

    # Avoid division by zero
    if velocity_std < 1e-10:
        velocity_std = 1e-10

    # Compute z-scores
    z_scores = np.abs((velocity - velocity_mean) / velocity_std)

    # For position data, use absolute velocity magnitude
    abs_velocity = np.abs(velocity)

    # Mark frames where velocity spike detected
    velocity_spikes = abs_velocity > velocity_limit
    zscore_spikes = z_scores > zscore_threshold

    # Combine: artifact if EITHER condition is met
    spike_mask = velocity_spikes | zscore_spikes

    # Mark the frame AFTER the spike (where the gap occurs) and the frame WITH the spike
    artifact_mask = np.zeros(len(signal), dtype=bool)
    artifact_mask[1:][spike_mask] = True
    artifact_mask[:-1][spike_mask] = True

    n_vel = int(np.sum(velocity_spikes))
    n_z = int(np.sum(zscore_spikes))
    # Frames marked can double-count where both conditions hit same transition
    n_marked = int(np.sum(artifact_mask))

    stats = {
        "n_velocity_spikes": n_vel,
        "n_zscore_spikes": n_z,
        "n_frames_marked": n_marked,
    }
    return artifact_mask, stats


def apply_hampel_filter(signal: np.ndarray, 
                       window_size: int = 5,
                       n_sigma: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Stage 2: Hampel Filter - Universal outlier "snipper" using sliding window median.
    
    Slides a window across data and replaces any point that is an outlier compared to
    its immediate neighbors with the median of that window.
    
    Generic Rule: A window of 5-7 frames is usually enough to "snip" MoCap artifacts
    while preserving 5-10 Hz dance dynamics.
    
    Args:
        signal: 1D signal array
        window_size: Size of sliding window (default: 5, recommended: 5-7)
        n_sigma: Number of standard deviations for outlier threshold (default: 3.0)
        
    Returns:
        Tuple of (filtered_signal, outlier_mask)
        - filtered_signal: Signal with outliers replaced by window median
        - outlier_mask: Boolean mask indicating which points were replaced
    """
    if len(signal) < window_size:
        return signal.copy(), np.zeros(len(signal), dtype=bool)
    
    filtered = signal.copy().astype(float)
    outlier_mask = np.zeros(len(signal), dtype=bool)
    
    half_window = window_size // 2
    
    for i in range(len(signal)):
        # Define window boundaries
        start_idx = max(0, i - half_window)
        end_idx = min(len(signal), i + half_window + 1)
        
        window_data = signal[start_idx:end_idx]
        
        # Skip if all NaN
        if np.all(np.isnan(window_data)):
            continue
        
        # Compute median and MAD (Median Absolute Deviation)
        window_median = np.nanmedian(window_data)
        mad = np.nanmedian(np.abs(window_data - window_median))
        
        # Convert MAD to standard deviation equivalent
        # MAD ≈ 0.6745 * std for normal distribution
        sigma = mad / 0.6745 if mad > 1e-10 else 1e-10
        
        # Check if current point is an outlier
        deviation = np.abs(signal[i] - window_median)
        if deviation > n_sigma * sigma:
            filtered[i] = window_median
            outlier_mask[i] = True
    
    return filtered, outlier_mask


def apply_quaternion_median_filter(df: pd.DataFrame,
                                   quat_cols: List[str],
                                   window_size: int = 5) -> Tuple[pd.DataFrame, Dict]:
    """
    Apply scipy.signal.medfilt to quaternion columns to remove flipping artifacts.
    
    This is a "surgical" clean that:
    1. Applies scipy.signal.medfilt to each quaternion component (qx, qy, qz, qw)
    2. Renormalizes quaternions after filtering to maintain unit length
    3. Does NOT apply low-pass filtering (which would break quaternion geometry)
    
    Use case: Fixes quaternion "flips" (e.g., 330° Hip ROM issues) without 
    distorting orientation data.
    
    Args:
        df: Input DataFrame with quaternion columns
        quat_cols: List of quaternion column names (ending in __qx, __qy, __qz, __qw)
        window_size: Median filter window size (default: 5, must be odd)
        
    Returns:
        Tuple of (filtered_dataframe, metadata_dict)
    """
    from scipy.signal import medfilt
    
    df_out = df.copy()
    
    # Ensure window_size is odd (required by medfilt)
    if window_size % 2 == 0:
        window_size += 1
        logger.info(f"Adjusted window_size to {window_size} (must be odd for medfilt)")
    
    # Group quaternion columns by joint
    joint_quats = {}
    for col in quat_cols:
        # Extract joint name (everything before __qx, __qy, __qz, __qw)
        for suffix in ['__qx', '__qy', '__qz', '__qw']:
            if col.endswith(suffix):
                joint_name = col[:-len(suffix)]
                if joint_name not in joint_quats:
                    joint_quats[joint_name] = {}
                component = suffix[2:]  # 'qx', 'qy', 'qz', 'qw'
                joint_quats[joint_name][component] = col
                break
    
    metadata = {
        'method': 'scipy.signal.medfilt',
        'window_size': window_size,
        'total_joints': len(joint_quats),
        'total_columns_filtered': 0,
        'per_joint_results': {}
    }
    
    total_cols_filtered = 0
    
    for joint_name, components in joint_quats.items():
        # Check if we have all 4 components
        if len(components) != 4:
            logger.warning(f"Joint {joint_name} missing quaternion components, skipping")
            continue
        
        # Apply medfilt to each component
        for comp_name, col in components.items():
            signal = df[col].values.astype(float)
            
            # Skip if all NaN
            if np.all(np.isnan(signal)):
                df_out[col] = signal
                continue
            
            # Handle NaNs: fill temporarily, filter, restore NaN positions
            nan_mask = np.isnan(signal)
            if np.any(nan_mask):
                # Fill NaNs with interpolated values for filtering
                signal_filled = pd.Series(signal).interpolate(limit_direction='both').values
                signal_filled = np.nan_to_num(signal_filled, nan=0.0)
            else:
                signal_filled = signal
            
            # Apply scipy.signal.medfilt
            filtered = medfilt(signal_filled, kernel_size=window_size)
            
            # Restore NaN positions
            if np.any(nan_mask):
                filtered[nan_mask] = np.nan
            
            df_out[col] = filtered
            total_cols_filtered += 1
        
        # Renormalize quaternions to unit length
        qx_col = components.get('qx')
        qy_col = components.get('qy')
        qz_col = components.get('qz')
        qw_col = components.get('qw')
        
        if all([qx_col, qy_col, qz_col, qw_col]):
            qx = df_out[qx_col].values
            qy = df_out[qy_col].values
            qz = df_out[qz_col].values
            qw = df_out[qw_col].values
            
            # Compute quaternion magnitude
            mag = np.sqrt(qx**2 + qy**2 + qz**2 + qw**2)
            
            # Avoid division by zero
            mag = np.where(mag < 1e-10, 1.0, mag)
            
            # Renormalize
            df_out[qx_col] = qx / mag
            df_out[qy_col] = qy / mag
            df_out[qz_col] = qz / mag
            df_out[qw_col] = qw / mag
        
        metadata['per_joint_results'][joint_name] = {
            'components_filtered': list(components.keys()),
            'renormalized': True
        }
    
    metadata['total_columns_filtered'] = int(total_cols_filtered)
    
    logger.info(f"Quaternion medfilt complete: {total_cols_filtered} columns filtered across {len(joint_quats)} joints")
    
    return df_out, metadata


def apply_adaptive_winter_filter(signal: np.ndarray,
                                fs: float,
                                fmin: float = 1.0,
                                fmax: float = 20.0,
                                min_cutoff: Optional[float] = None,
                                body_region: str = "general") -> Tuple[np.ndarray, Dict]:
    """
    Stage 3: Adaptive Low-Pass using Winter's Residual Method.
    
    Automatically calculates optimal cutoff for each joint/session by finding the
    "elbow" in the residual curve - where you stop removing noise and start removing signal.
    
    The script tries every cutoff from fmin to fmax Hz and looks for the knee point.
    
    Args:
        signal: 1D signal array (already artifact-cleaned)
        fs: Sampling frequency (Hz)
        fmin: Minimum cutoff to test (Hz, default: 1.0)
        fmax: Maximum cutoff to test (Hz, default: 20.0)
        min_cutoff: Biomechanical minimum cutoff (Hz, optional)
        body_region: Body region name for Smart Bias context. CRITICAL: must be
                    passed from the caller to enable per-region frequency decoupling.
                    Without this, Smart Bias uses a generic trust_factor that
                    compresses the 6-12 Hz range into ~10 Hz.
        
    Returns:
        Tuple of (filtered_signal, metadata_dict)
        - filtered_signal: Low-pass filtered signal
        - metadata_dict: Contains cutoff_hz, method_used, etc.
    """
    # Safety net: signal must be long enough for filtfilt (padlen=9 for 2nd-order Butterworth)
    _MIN_FILTER_LEN = 15
    if len(signal) < _MIN_FILTER_LEN:
        logger.warning(
            f"Signal too short ({len(signal)} frames, need >= {_MIN_FILTER_LEN}) "
            f"for adaptive Winter filter. Returning unfiltered signal."
        )
        metadata = {
            'cutoff_hz': None,
            'method_used': 'signal_too_short_skipped',
            'filter_applied': False,
            'knee_point_found': False,
            'failure_reason': f"Signal too short ({len(signal)} frames < {_MIN_FILTER_LEN})"
        }
        return signal.copy(), metadata

    # Build dynamic RMS energetic mask for this signal
    em = compute_energetic_mask(signal, fs)

    # Run Winter residual analysis with body_region context for Smart Bias
    winter_result = winter_residual_analysis(
        signal, fs, fmin=int(fmin), fmax=int(fmax),
        min_cutoff=min_cutoff, body_region=body_region,
        return_details=True,
        energetic_mask=em,
    )
    
    if isinstance(winter_result, dict):
        cutoff_hz = winter_result['cutoff_hz']
        metadata = winter_result.copy()
    else:
        cutoff_hz = float(winter_result)
        metadata = {'cutoff_hz': cutoff_hz}
    
    # Apply Butterworth filter with optimal cutoff
    if cutoff_hz >= fs * 0.5 - 1:
        logger.warning(f"Cutoff {cutoff_hz:.1f} Hz too close to Nyquist ({fs*0.5:.1f} Hz), skipping filter")
        return signal.copy(), metadata
    
    b, a = butter(N=2, Wn=cutoff_hz/(0.5*fs), btype='low')

    filtered, chunk_meta = chunked_filtfilt(b, a, signal.astype(float), return_meta=True)
    
    metadata['filter_applied'] = True
    metadata['filter_type'] = 'Butterworth 2nd-order (zero-phase, chunked)'
    metadata['chunking_guard'] = chunk_meta
    
    return filtered, metadata


def apply_signal_cleaning_pipeline(df: pd.DataFrame,
                                  fs: float,
                                  pos_cols: List[str],
                                  velocity_limit: float = 1800.0,
                                  zscore_threshold: float = 5.0,
                                  hampel_window: int = 5,
                                  hampel_n_sigma: float = 3.0,
                                  winter_fmin: float = 1.0,
                                  winter_fmax: float = 20.0,
                                  per_joint_winter: bool = True,
                                  stage1_interpolation_method: str = 'pchip') -> Tuple[pd.DataFrame, Dict]:
    """
    Apply 3-Stage Signal Cleaning Pipeline: Artifact Detection → Hampel → Adaptive Winter.

    Used by: 3-stage method (config_v1.yaml filtering.method = "3_stage").
    Does: Stage 1 artifact detection (velocity + z-score) → Stage 2 Hampel → Stage 3
    adaptive Winter per column; returns cleaned dataframe and pipeline metadata.

    Why cleaning before low-pass: Savitzky-Golay (used in notebook 06 for derivatives)
    smooths when differentiating; it does not remove spikes. A spike in position would
    remain and be smoothed into a bump, affecting derivatives. Stage 1+2 remove or
    correct spikes and outliers first; Winter (Stage 3) then low-pass filters the
    cleaned signal. So all three stages are needed when data has artifacts.

    This generic "Gatekeeper" architecture treats artifacts (spikes) and noise (jitter)
    as two separate problems, and can be applied to any joint in any session.

    Pipeline:
    1. Stage 1 (Artifact Detector): Identifies tracking spikes using velocity + z-score
    2. Stage 2 (Hampel Filter): Removes outliers using sliding window median
    3. Stage 3 (Adaptive Winter): Finds optimal cutoff per-joint using residual analysis

    Args:
        df: Input DataFrame with position columns
        fs: Sampling frequency (Hz)
        pos_cols: List of position column names to process
        velocity_limit: Physiological velocity limit in signal units per second
                       (e.g., 5000 mm/s for position data, 1800 deg/s for angular)
        zscore_threshold: Z-score threshold for outlier detection (default: 5.0)
        hampel_window: Hampel filter window size (default: 5, recommended: 5-7)
        hampel_n_sigma: Hampel filter outlier threshold (default: 3.0)
        winter_fmin: Minimum cutoff for Winter analysis (Hz)
        winter_fmax: Maximum cutoff for Winter analysis (Hz)
        per_joint_winter: Stored in pipeline metadata only. The implementation
                         always runs Winter analysis per column (adaptive cutoff per
                         joint); there is no single-global-Winter path when False.
        stage1_interpolation_method: Method for filling artifact gaps: 'pchip' (default),
                         'linear', or 'cubic'. PCHIP is shape-preserving (no overshoot),
                         smooth; linear is most conservative; cubic can overshoot.

    Returns:
        Tuple of (cleaned_dataframe, pipeline_metadata)
    """
    # Duration gate: reject DataFrames too short for meaningful filtering
    _MIN_FRAMES_FOR_FILTERING = 30  # ~0.25 sec at 120 Hz
    if len(df) < _MIN_FRAMES_FOR_FILTERING:
        logger.warning(
            f"DataFrame too short for 3-stage pipeline ({len(df)} frames, "
            f"need >= {_MIN_FRAMES_FOR_FILTERING}). Returning unfiltered data."
        )
        return df.copy(), {
            'pipeline_type': '3_stage_signal_cleaning',
            'skipped': True,
            'skip_reason': f"DataFrame too short ({len(df)} frames < {_MIN_FRAMES_FOR_FILTERING})",
            'summary': {'total_columns_processed': 0},
        }

    df_out = df.copy()
    pipeline_metadata = {
        'pipeline_type': '3_stage_signal_cleaning',
        'stages': {
            'stage1_artifact_detector': {
                'method': 'Z-Score + Velocity Threshold',
                'velocity_limit': velocity_limit,
                'zscore_threshold': zscore_threshold,
                'interpolation_method': stage1_interpolation_method
            },
            'stage2_hampel': {
                'method': 'Sliding Window Median',
                'window_size': hampel_window,
                'n_sigma': hampel_n_sigma
            },
            'stage3_adaptive_winter': {
                'method': "Winter's Residual Method",
                'fmin': winter_fmin,
                'fmax': winter_fmax,
                'per_joint': per_joint_winter
            }
        },
        'per_joint_results': {}
    }
    
    # Validate position columns
    pos_cols_valid = [col for col in pos_cols if col in df.columns and not df[col].isna().all()]
    
    if not pos_cols_valid:
        raise ValueError(f"No valid position columns found in {len(pos_cols)} provided columns")
    
    logger.info(f"Applying 3-stage signal cleaning pipeline to {len(pos_cols_valid)} position columns")
    
    # Helper: count contiguous True segments in a boolean mask
    def _count_segments(mask: np.ndarray) -> int:
        if not np.any(mask):
            return 0
        padded = np.concatenate([[False], mask, [False]])
        runs = np.diff(padded.astype(int))
        return int(np.sum(runs == 1))

    # Process each position column
    total_artifacts = 0
    total_artifact_segments = 0
    total_velocity_spikes = 0
    total_zscore_spikes = 0
    total_hampel_outliers = 0
    n_frames_total = len(df) if len(pos_cols_valid) > 0 else 0

    for col in pos_cols_valid:
        signal = df[col].values.astype(float)

        # Skip if all NaN
        if np.all(np.isnan(signal)):
            continue

        col_metadata = {}

        # Stage 1: Artifact Detection
        artifact_mask, artifact_stats = detect_artifact_gaps(
            signal, fs,
            velocity_limit=velocity_limit,
            zscore_threshold=zscore_threshold
        )
        n_artifacts = artifact_stats["n_frames_marked"]
        n_segments = _count_segments(artifact_mask)
        total_artifacts += n_artifacts
        total_artifact_segments += n_segments
        total_velocity_spikes += artifact_stats["n_velocity_spikes"]
        total_zscore_spikes += artifact_stats["n_zscore_spikes"]

        # Interpolate artifacts with gap-size plausibility limit.
        # At 120 Hz, 30 frames = 0.25 s — the same threshold used for
        # quaternion gap filling (max_gap_quat_sec).  Gaps beyond this are
        # physically implausible to reconstruct and are left as NaN so
        # downstream stages (Winter LP) see them as missing data rather
        # than hallucinated trajectories.
        _MAX_INTERP_FRAMES = int(fs * 0.25)  # 0.25 s plausibility threshold
        signal_stage1 = signal.copy()
        max_artifact_gap_frames = 0
        n_unreliable_gaps = 0
        if n_artifacts > 0:
            signal_series = pd.Series(signal_stage1)
            signal_series.loc[artifact_mask] = np.nan

            # Measure contiguous NaN runs to enforce gap limit
            is_nan = signal_series.isna()
            nan_groups = (is_nan != is_nan.shift()).cumsum()
            gap_sizes = is_nan.groupby(nan_groups).sum()
            gap_sizes = gap_sizes[gap_sizes > 0]
            if len(gap_sizes) > 0:
                max_artifact_gap_frames = int(gap_sizes.max())
                n_unreliable_gaps = int((gap_sizes > _MAX_INTERP_FRAMES).sum())

            if n_unreliable_gaps > 0:
                logger.warning(
                    f"[GAP_GUARD] {col}: {n_unreliable_gaps} artifact gap(s) exceed "
                    f"{_MAX_INTERP_FRAMES} frames ({_MAX_INTERP_FRAMES/fs:.2f}s). "
                    f"Largest gap: {max_artifact_gap_frames} frames "
                    f"({max_artifact_gap_frames/fs:.2f}s). "
                    f"These gaps will use bounded interpolation only."
                )

            signal_stage1 = signal_series.interpolate(
                method=stage1_interpolation_method,
                limit=_MAX_INTERP_FRAMES,
                limit_direction='both'
            ).values
            # Edge fill only for small boundary NaNs (1 frame)
            s1_series = pd.Series(signal_stage1)
            signal_stage1 = s1_series.bfill(limit=1).ffill(limit=1).values

        col_metadata['stage1_artifacts_detected'] = int(n_artifacts)
        col_metadata['stage1_segments_interpolated'] = n_segments
        col_metadata['stage1_max_gap_frames'] = max_artifact_gap_frames
        col_metadata['stage1_unreliable_gaps'] = n_unreliable_gaps
        col_metadata['stage1_velocity_spikes'] = artifact_stats["n_velocity_spikes"]
        col_metadata['stage1_zscore_spikes'] = artifact_stats["n_zscore_spikes"]
        
        # Stage 2: Hampel Filter
        signal_stage2, hampel_outliers = apply_hampel_filter(
            signal_stage1,
            window_size=hampel_window,
            n_sigma=hampel_n_sigma
        )
        n_hampel = np.sum(hampel_outliers)
        total_hampel_outliers += n_hampel
        col_metadata['stage2_hampel_outliers'] = int(n_hampel)
        
        # Stage 3: Adaptive Winter Filter
        # Determine minimum cutoff based on body region
        marker_region = classify_marker_region(col)
        region_config = BODY_REGIONS.get(marker_region, BODY_REGIONS['upper_proximal'])
        min_cutoff = region_config.get('fixed_cutoff', 6.0)  # Use fixed cutoff as minimum
        
        signal_stage3, winter_meta = apply_adaptive_winter_filter(
            signal_stage2,
            fs=fs,
            fmin=winter_fmin,
            fmax=winter_fmax,
            min_cutoff=min_cutoff,
            body_region=marker_region
        )
        
        col_metadata['stage3_winter_cutoff'] = winter_meta.get('cutoff_hz', None)
        col_metadata['stage3_winter_method'] = winter_meta.get('method_used', 'unknown')
        col_metadata['marker_region'] = marker_region
        col_metadata['stage3_dynamic_rms_used'] = winter_meta.get('dynamic_rms_used', False)
        col_metadata['stage3_dynamic_rms_fallback'] = winter_meta.get('dynamic_rms_fallback_to_global', False)
        col_metadata['stage3_chunking_guard'] = winter_meta.get('chunking_guard', {})
        
        # [FILTER_DEBUG] Smart Bias traceability log
        _fc_result = winter_meta.get('cutoff_hz', None)
        _region_low = region_config.get('cutoff_range', (6, 12))[0]
        _region_high = region_config.get('cutoff_range', (6, 12))[1]
        _agility = (_region_low - 6.0) / (12.0 - 6.0) if 12.0 > 6.0 else 0.0
        logger.info(f"[FILTER_DEBUG] Marker: {col} | Region: {marker_region} | "
                    f"Agility: {_agility:.2f} | Weighted_Fc: {_fc_result}")
        
        # Store result
        df_out[col] = signal_stage3
        pipeline_metadata['per_joint_results'][col] = col_metadata
    
    # Summary statistics (frames = samples; segments = contiguous interpolated runs)
    pipeline_metadata['summary'] = {
        'total_columns_processed': len(pos_cols_valid),
        'n_frames_total': n_frames_total,
        'total_artifact_frames': int(total_artifacts),
        'total_artifact_segments': int(total_artifact_segments),
        'total_velocity_spikes': int(total_velocity_spikes),
        'total_zscore_spikes': int(total_zscore_spikes),
        'total_hampel_outliers': int(total_hampel_outliers),
        'stage1_interpolation_method': stage1_interpolation_method,
        'avg_artifacts_per_column': total_artifacts / len(pos_cols_valid) if pos_cols_valid else 0,
        'avg_hampel_outliers_per_column': total_hampel_outliers / len(pos_cols_valid) if pos_cols_valid else 0,
        'artifact_frames_pct': (100.0 * total_artifacts / (len(pos_cols_valid) * n_frames_total)) if pos_cols_valid and n_frames_total else 0.0,
        'hampel_frames_pct': (100.0 * total_hampel_outliers / (len(pos_cols_valid) * n_frames_total)) if pos_cols_valid and n_frames_total else 0.0,
        'stage1_max_interp_limit_frames': int(fs * 0.25),
        'stage1_gap_guard': {
            'max_gap_across_all_cols': int(max(
                (m.get('stage1_max_gap_frames', 0)
                 for m in pipeline_metadata['per_joint_results'].values()),
                default=0
            )),
            'cols_with_unreliable_gaps': [
                col for col, m in pipeline_metadata['per_joint_results'].items()
                if m.get('stage1_unreliable_gaps', 0) > 0
            ],
            'total_unreliable_gaps': sum(
                m.get('stage1_unreliable_gaps', 0)
                for m in pipeline_metadata['per_joint_results'].values()
            ),
        },
    }
    
    # Compute cutoff statistics
    cutoffs = [meta.get('stage3_winter_cutoff') for meta in pipeline_metadata['per_joint_results'].values()
               if meta.get('stage3_winter_cutoff') is not None]
    if cutoffs:
        pipeline_metadata['summary']['winter_cutoff_stats'] = {
            'min': float(np.min(cutoffs)),
            'max': float(np.max(cutoffs)),
            'mean': float(np.mean(cutoffs)),
            'median': float(np.median(cutoffs)),
            'std': float(np.std(cutoffs))
        }

    # Dynamic RMS Windowing & Chunking Guard aggregate statistics
    pj = pipeline_metadata['per_joint_results']
    n_drms = sum(1 for m in pj.values() if m.get('stage3_dynamic_rms_used'))
    n_drms_fb = sum(1 for m in pj.values() if m.get('stage3_dynamic_rms_fallback'))
    total_chunks = sum(m.get('stage3_chunking_guard', {}).get('n_chunks', 0) for m in pj.values())
    total_short = sum(m.get('stage3_chunking_guard', {}).get('n_chunks_too_short', 0) for m in pj.values())
    total_short_frames = sum(m.get('stage3_chunking_guard', {}).get('short_chunk_frames', 0) for m in pj.values())
    pipeline_metadata['summary']['dynamic_rms_windowing'] = {
        'enabled': True,
        'energy_quantile': 0.80,
        'joints_with_dynamic_rms': n_drms,
        'joints_fallback_to_global_rms': n_drms_fb,
        'fallback_joints': [col for col, m in pj.items() if m.get('stage3_dynamic_rms_fallback')],
    }
    pipeline_metadata['summary']['chunking_guard'] = {
        'total_chunks_all_joints': total_chunks,
        'total_chunks_too_short': total_short,
        'total_unfiltered_frames': total_short_frames,
        'joints_with_short_chunks': [
            col for col, m in pj.items()
            if m.get('stage3_chunking_guard', {}).get('n_chunks_too_short', 0) > 0
        ],
    }
    
    logger.info(
        f"3-stage pipeline complete: Stage1 interpolated {total_artifacts} frames in {total_artifact_segments} segments "
        f"(velocity_spikes={total_velocity_spikes}, zscore_spikes={total_zscore_spikes}), method={stage1_interpolation_method}; "
        f"Stage2 Hampel replaced {total_hampel_outliers} frames ({pipeline_metadata['summary'].get('hampel_frames_pct', 0):.2f}% of samples)"
    )
    return df_out, pipeline_metadata


def print_pipeline_debug_logs(pipeline_metadata: Dict, 
                              top_n_joints: int = 20,
                              show_all: bool = False) -> None:
    """
    Print detailed debug logs for the 3-stage signal cleaning pipeline.
    
    Args:
        pipeline_metadata: Metadata dictionary from apply_signal_cleaning_pipeline
        top_n_joints: Number of top joints to show in detail (default: 20)
        show_all: If True, show all joints regardless of top_n_joints
    """
    print(f"\n{'='*80}")
    print(f"📊 DETAILED PIPELINE DEBUG LOGS")
    print(f"{'='*80}\n")
    
    # Pipeline configuration
    stages = pipeline_metadata.get('stages', {})
    print("🔧 PIPELINE CONFIGURATION:")
    print(f"   Stage 1 (Artifact Detector):")
    stage1 = stages.get('stage1_artifact_detector', {})
    print(f"     - Velocity limit: {stage1.get('velocity_limit', 'N/A')} mm/s")
    print(f"     - Z-score threshold: {stage1.get('zscore_threshold', 'N/A')}σ")
    print(f"     - Interpolation method: {stage1.get('interpolation_method', 'linear')} (documented)")
    print(f"   Stage 2 (Hampel Filter):")
    stage2 = stages.get('stage2_hampel', {})
    print(f"     - Window size: {stage2.get('window_size', 'N/A')} frames")
    print(f"     - Outlier threshold: {stage2.get('n_sigma', 'N/A')}σ")

    # Stage 1 & 2 impact: frames and segments (all numbers are frame counts)
    summary = pipeline_metadata.get('summary', {})
    n_frames = summary.get('n_frames_total', 0)
    n_cols = summary.get('total_columns_processed', 1)
    total_pos_samples = n_frames * n_cols if n_frames and n_cols else 1
    print(f"\n📈 STAGE 1 & 2 IMPACT (all numbers in frames = samples):")
    print(f"   Stage 1 (interpolation):")
    print(f"     - Frames interpolated: {summary.get('total_artifact_frames', 0)} ({summary.get('artifact_frames_pct', 0):.2f}% of position samples)")
    print(f"     - Contiguous segments interpolated: {summary.get('total_artifact_segments', 0)}")
    print(f"     - Triggered by velocity limit: {summary.get('total_velocity_spikes', 0)} frame transitions")
    print(f"     - Triggered by z-score: {summary.get('total_zscore_spikes', 0)} frame transitions")
    print(f"   Stage 2 (Hampel):")
    print(f"     - Frames replaced (outliers): {summary.get('total_hampel_outliers', 0)} ({summary.get('hampel_frames_pct', 0):.2f}% of position samples)")
    print(f"   Stage 3 (Adaptive Winter):")
    stage3 = stages.get('stage3_adaptive_winter', {})
    print(f"     - Frequency range: {stage3.get('fmin', 'N/A')} - {stage3.get('fmax', 'N/A')} Hz")
    print(f"     - Per-joint analysis: {stage3.get('per_joint', 'N/A')}")
    
    # Summary statistics
    summary = pipeline_metadata.get('summary', {})
    print(f"\n📈 SUMMARY STATISTICS:")
    print(f"   Total columns processed: {summary.get('total_columns_processed', 0)}")
    print(f"   Total artifacts detected: {summary.get('total_artifact_frames', 0)}")
    print(f"   Total Hampel outliers: {summary.get('total_hampel_outliers', 0)}")
    print(f"   Avg artifacts per column: {summary.get('avg_artifacts_per_column', 0):.2f}")
    print(f"   Avg Hampel outliers per column: {summary.get('avg_hampel_outliers_per_column', 0):.2f}")
    
    # Winter cutoff statistics
    if 'winter_cutoff_stats' in summary:
        cutoff_stats = summary['winter_cutoff_stats']
        print(f"\n🎯 ADAPTIVE WINTER CUTOFF STATISTICS:")
        print(f"   Range: {cutoff_stats['min']:.2f} - {cutoff_stats['max']:.2f} Hz")
        print(f"   Mean: {cutoff_stats['mean']:.2f} Hz")
        print(f"   Median: {cutoff_stats['median']:.2f} Hz")
        print(f"   Std Dev: {cutoff_stats['std']:.2f} Hz")
    
    # Per-joint detailed results
    per_joint = pipeline_metadata.get('per_joint_results', {})
    if per_joint:
        print(f"\n{'='*80}")
        print(f"🔍 PER-JOINT DETAILED RESULTS")
        print(f"{'='*80}\n")
        
        # Sort joints by total issues (artifacts + hampel outliers)
        joint_scores = []
        for col, meta in per_joint.items():
            artifacts = meta.get('stage1_artifacts_detected', 0)
            hampel = meta.get('stage2_hampel_outliers', 0)
            total_issues = artifacts + hampel
            joint_scores.append((col, meta, total_issues))
        
        # Sort by total issues (descending)
        joint_scores.sort(key=lambda x: x[2], reverse=True)
        
        # Determine how many to show
        n_to_show = len(joint_scores) if show_all else min(top_n_joints, len(joint_scores))
        
        print(f"Showing top {n_to_show} joints (sorted by total issues detected):\n")
        print(f"{'Joint':<40} {'Region':<15} {'Artifacts':<12} {'Hampel':<12} {'Winter Cutoff':<15} {'Method':<15}")
        print(f"{'-'*40} {'-'*15} {'-'*12} {'-'*12} {'-'*15} {'-'*15}")
        
        for col, meta, total_issues in joint_scores[:n_to_show]:
            joint_name = col.replace('__px', '').replace('__py', '').replace('__pz', '')[:38]
            region = meta.get('marker_region', 'unknown')
            artifacts = meta.get('stage1_artifacts_detected', 0)
            hampel = meta.get('stage2_hampel_outliers', 0)
            cutoff = meta.get('stage3_winter_cutoff', None)
            method = meta.get('stage3_winter_method', 'unknown')
            
            cutoff_str = f"{cutoff:.2f} Hz" if cutoff is not None else "N/A"
            method_str = method[:14] if method else "N/A"
            
            print(f"{joint_name:<40} {region:<15} {artifacts:<12} {hampel:<12} {cutoff_str:<15} {method_str:<15}")
        
        if len(joint_scores) > n_to_show:
            print(f"\n   ... and {len(joint_scores) - n_to_show} more joints (set show_all=True to see all)")
        
        # Statistics by region
        print(f"\n{'='*80}")
        print(f"📊 STATISTICS BY BODY REGION")
        print(f"{'='*80}\n")
        
        region_stats = {}
        for col, meta in per_joint.items():
            region = meta.get('marker_region', 'unknown')
            if region not in region_stats:
                region_stats[region] = {
                    'count': 0,
                    'artifacts': 0,
                    'hampel': 0,
                    'cutoffs': []
                }
            
            region_stats[region]['count'] += 1
            region_stats[region]['artifacts'] += meta.get('stage1_artifacts_detected', 0)
            region_stats[region]['hampel'] += meta.get('stage2_hampel_outliers', 0)
            cutoff = meta.get('stage3_winter_cutoff')
            if cutoff is not None:
                region_stats[region]['cutoffs'].append(cutoff)
        
        print(f"{'Region':<20} {'Joints':<10} {'Artifacts':<12} {'Hampel':<12} {'Cutoff Range':<20} {'Mean Cutoff':<15}")
        print(f"{'-'*20} {'-'*10} {'-'*12} {'-'*12} {'-'*20} {'-'*15}")
        
        for region, stats in sorted(region_stats.items()):
            count = stats['count']
            artifacts = stats['artifacts']
            hampel = stats['hampel']
            cutoffs = stats['cutoffs']
            
            if cutoffs:
                cutoff_range = f"{min(cutoffs):.1f} - {max(cutoffs):.1f} Hz"
                mean_cutoff = f"{np.mean(cutoffs):.2f} Hz"
            else:
                cutoff_range = "N/A"
                mean_cutoff = "N/A"
            
            print(f"{region:<20} {count:<10} {artifacts:<12} {hampel:<12} {cutoff_range:<20} {mean_cutoff:<15}")
        
        # Joints with most issues
        print(f"\n{'='*80}")
        print(f"⚠️  JOINTS WITH MOST ISSUES (Top 10)")
        print(f"{'='*80}\n")
        
        top_issues = sorted(joint_scores, key=lambda x: x[2], reverse=True)[:10]
        for i, (col, meta, total_issues) in enumerate(top_issues, 1):
            joint_name = col.replace('__px', '').replace('__py', '').replace('__pz', '')
            artifacts = meta.get('stage1_artifacts_detected', 0)
            hampel = meta.get('stage2_hampel_outliers', 0)
            cutoff = meta.get('stage3_winter_cutoff', None)
            region = meta.get('marker_region', 'unknown')
            
            print(f"{i:2d}. {joint_name}")
            print(f"     Region: {region} | Artifacts: {artifacts} | Hampel: {hampel} | Total: {total_issues}")
            if cutoff:
                print(f"     Winter Cutoff: {cutoff:.2f} Hz ({meta.get('stage3_winter_method', 'unknown')})")
            print()
        
        # Joints with Winter analysis issues
        winter_issues = []
        for col, meta in per_joint.items():
            method = meta.get('stage3_winter_method', '')
            cutoff = meta.get('stage3_winter_cutoff', None)
            if 'failure' in method.lower() or cutoff is None or (cutoff and cutoff >= 19.0):
                winter_issues.append((col, meta))
        
        if winter_issues:
            print(f"\n{'='*80}")
            print(f"⚠️  WINTER ANALYSIS ISSUES ({len(winter_issues)} joints)")
            print(f"{'='*80}\n")
            for col, meta in winter_issues[:10]:
                joint_name = col.replace('__px', '').replace('__py', '').replace('__pz', '')
                method = meta.get('stage3_winter_method', 'unknown')
                cutoff = meta.get('stage3_winter_cutoff', None)
                print(f"   {joint_name}: {method}")
                if cutoff:
                    print(f"     Cutoff: {cutoff:.2f} Hz")
            if len(winter_issues) > 10:
                print(f"\n   ... and {len(winter_issues) - 10} more joints with Winter issues")
    
    print(f"\n{'='*80}")
    print(f"✅ DEBUG LOGS COMPLETE")
    print(f"{'='*80}\n")


def apply_winter_filter(df: pd.DataFrame, 
                     fs: float, 
                     pos_cols: List[str], 
                     rep_col: Optional[str] = None,
                     fmax: int = 12,
                     allow_fmax: bool = False,
                     min_cutoff_trunk: Optional[float] = 6.0,
                     min_cutoff_distal: Optional[float] = 8.0,
                     use_trunk_global: bool = False,
                     per_region_filtering: bool = False,
                     fixed_cutoff_hz: Optional[float] = None) -> Tuple[pd.DataFrame, Dict]:
    """
    Apply Winter low-pass filter to position columns only.
    
    Uses Winter residual analysis to determine optimal cutoff frequency,
    then applies zero-lag 2nd-order Butterworth filtering.
    
    Args:
        df: Input DataFrame with perfect time grid
        fs: Sampling frequency in Hz
        pos_cols: List of position column names to filter
        rep_col: Representative column for cutoff analysis (optional)
        fmax: Maximum cutoff frequency for Winter analysis (Hz)
        allow_fmax: If False, raises ValueError when Winter returns fmax (method failure)
        min_cutoff_trunk: Biomechanical minimum cutoff for trunk markers (Hz)
        min_cutoff_distal: Biomechanical minimum cutoff for distal markers (Hz)
        use_trunk_global: If True, run Winter on trunk markers only and apply to all columns
        per_region_filtering: If True, apply different cutoffs per body region (recommended for dance)
        fixed_cutoff_hz: If set (e.g. 8.0), skip Winter analysis and apply this cutoff to all columns (single-global).
        
    Returns:
        Tuple of (filtered DataFrame, metadata dict)
        
    Raises:
        ValueError: If NaNs exist in position columns or Winter analysis fails
        
    Note:
        For dance/mocap: Distal segments (hands/feet) need higher cutoffs than trunk
        because they contain faster real motion. Typical: Trunk=6-8Hz, Distal=10-12Hz
        
        Per-region filtering (new feature):
        - Trunk: 6-8 Hz (slow core movements)
        - Head: 7-9 Hz (moderate dynamics)
        - Upper proximal: 8-10 Hz (shoulders)
        - Upper distal: 10-12 Hz (hands - rapid gestures)
        - Lower proximal: 8-10 Hz (thighs, knees)
        - Lower distal: 9-11 Hz (feet, ankles)
    """
    # Ticket 10.5: Build valid position columns list and log exclusions
    pos_cols_valid = []
    excluded_cols = []
    
    for col in pos_cols:
        if col not in df.columns:
            excluded_cols.append(f"{col} (missing)")
        elif df[col].isna().any():
            excluded_cols.append(f"{col} (NaNs)")
        else:
            pos_cols_valid.append(col)
    
    if excluded_cols:
        logger.warning(f"Excluding columns with issues: {excluded_cols}")
    
    if not pos_cols_valid:
        raise ValueError(f"No valid position columns found. All {len(pos_cols)} columns excluded: {excluded_cols}")
    
    # Single-global fixed cutoff from config (skip Winter analysis)
    if fixed_cutoff_hz is not None:
        fc = float(fixed_cutoff_hz)
        chosen_rep_col = "config_fixed"
        logger.info(f"Using config fixed cutoff: {fc:.1f} Hz (single-global)")
    # Smart representative column selection with multi-signal fallback
    elif rep_col is not None:
        if rep_col not in df.columns:
            raise ValueError(f"Representative column '{rep_col}' not found in DataFrame")
        if df[rep_col].isna().any():
            raise ValueError(f"Representative column '{rep_col}' contains NaNs")
        chosen_rep_col = rep_col
        cutoffs = [winter_residual_analysis(df[chosen_rep_col].values, fs, fmax=fmax)]
        fc = float(cutoffs[0])  # Bug fix: assign fc from cutoffs[0]
        logger.info(f"Using user-specified representative column: {chosen_rep_col}")
    else:
        # Determine analysis strategy based on use_trunk_global flag
        if use_trunk_global:
            logger.info("Using trunk-based global cutoff strategy...")
            
            # Identify trunk markers (pelvis, spine, torso)
            trunk_patterns = ['Pelvis', 'Spine', 'Torso', 'Hips', 'Abdomen', 'Chest', 'Neck']
            trunk_cols = [col for col in pos_cols_valid 
                        if any(pattern in col for pattern in trunk_patterns)]
            
            if not trunk_cols:
                logger.warning("No trunk markers found. Falling back to multi-signal analysis.")
                trunk_cols = pos_cols_valid  # Fallback to all columns
            
            logger.info(f"Trunk markers identified: {len(trunk_cols)} columns")
            
            # Compute dynamics score for trunk columns only
            col_scores = {}
            for col in trunk_cols:
                signal = df[col].values
                dynamics_score = np.nanstd(np.diff(signal))
                col_scores[col] = dynamics_score
            
            # Sort by dynamics score and pick top 3 trunk columns
            sorted_cols = sorted(col_scores.items(), key=lambda x: x[1], reverse=True)
            top_trunk_cols = [col for col, _ in sorted_cols[:3]]
            
            logger.info(f"Top 3 most dynamic trunk columns: {top_trunk_cols}")
            
            # Run Winter analysis on trunk columns with trunk minimum cutoff
            cutoffs = []
            for col in top_trunk_cols:
                cutoff = winter_residual_analysis(
                    df[col].values, fs, fmax=fmax, 
                    min_cutoff=min_cutoff_trunk, body_region="trunk"
                )
                cutoffs.append(cutoff)
                logger.info(f"  {col}: {cutoff:.1f} Hz (trunk)")
            
            # Use median trunk cutoff as global cutoff for all columns
            fc = np.median(cutoffs)
            chosen_rep_col = f"trunk_global_median({len(cutoffs)}_cols)"
            
            logger.info(f"Trunk-based global cutoff: median = {fc:.1f} Hz")
            logger.info(f"Individual trunk cutoffs: {[f'{c:.1f}' for c in cutoffs]}")
            logger.info(f"Applying trunk-based cutoff to all {len(pos_cols_valid)} columns")
            
        else:
            # Standard multi-signal Winter analysis: pick top 5 most dynamic columns
            logger.info("Performing multi-signal Winter analysis...")
            
            # Compute dynamics score for each valid position column
            col_scores = {}
            for col in pos_cols_valid:
                signal = df[col].values
                # Dynamics ranking: score = nanstd(diff(x))
                dynamics_score = np.nanstd(np.diff(signal))
                col_scores[col] = dynamics_score
            
            # Sort by dynamics score (descending) and pick top 5
            sorted_cols = sorted(col_scores.items(), key=lambda x: x[1], reverse=True)
            top_5_cols = [col for col, _ in sorted_cols[:5]]
            
            logger.info(f"Top 5 most dynamic columns: {top_5_cols}")
            
            # Run Winter analysis on each of the top 5 columns with appropriate guardrails
            cutoffs = []
            for col in top_5_cols:
                # Determine if this is a trunk or distal marker
                is_trunk = any(pattern in col for pattern in ['Pelvis', 'Spine', 'Torso', 'Hips', 'Abdomen', 'Chest', 'Neck'])
                min_cutoff = min_cutoff_trunk if is_trunk else min_cutoff_distal
                body_region = "trunk" if is_trunk else "distal"
                
                cutoff = winter_residual_analysis(
                    df[col].values, fs, fmax=fmax, 
                    min_cutoff=min_cutoff, body_region=body_region
                )
                cutoffs.append(cutoff)
                logger.info(f"  {col}: {cutoff:.1f} Hz ({body_region})")
            
            # Use median cutoff as global cutoff
            fc = np.median(cutoffs)
            chosen_rep_col = f"multi_signal_median({len(cutoffs)}_cols)"
            
            logger.info(f"Multi-signal Winter analysis: median cutoff = {fc:.1f} Hz")
            logger.info(f"Individual cutoffs: {[f'{c:.1f}' for c in cutoffs]}")
    
    # PER-REGION FILTERING WITH FIXED CUTOFFS (Literature-Based)
    # Reference: Winter (2009), Robertson (2014) - Fixed cutoffs for research reproducibility
    if per_region_filtering:
        logger.info("=== PER-REGION FILTERING WITH FIXED CUTOFFS ===")
        logger.info("Using literature-based fixed cutoffs per body region (Winter 2009, Robertson 2014)")
        logger.info("Winter analysis runs as VALIDATION only - not for cutoff selection")
        
        # Classify all markers by region
        marker_regions = {}
        region_columns = {region: [] for region in BODY_REGIONS.keys()}
        region_columns['unknown'] = []
        
        for col in pos_cols_valid:
            region = classify_marker_region(col)
            marker_regions[col] = region
            if region in region_columns:
                region_columns[region].append(col)
            else:
                region_columns['unknown'].append(col)
        
        # Log region classification
        for region, cols in region_columns.items():
            if cols:
                logger.info(f"  {region}: {len(cols)} markers")
        
        # Apply FIXED cutoffs per region with Winter validation
        df_out = df.copy()
        region_cutoffs = {}
        region_analysis_details = {}  # Store Winter validation results
        
        for region, cols in region_columns.items():
            if not cols or region == 'unknown':
                continue
            
            # Get region configuration with FIXED cutoff
            # Default uses 8 Hz (upper_proximal) to preserve 6-12 Hz range
            region_config = BODY_REGIONS.get(region, {'fixed_cutoff': 8, 'cutoff_range': (6, 12), 'rationale': 'default_upper_proximal'})
            fc_region = region_config.get('fixed_cutoff', 10)  # Use fixed cutoff
            min_cutoff_region, max_cutoff_region = region_config['cutoff_range']
            
            # Select representative column for this region (most dynamic) - for validation
            col_scores = {col: np.nanstd(np.diff(df[col].values)) for col in cols}
            rep_col_region = max(col_scores, key=col_scores.get)
            
            # Run Winter analysis as VALIDATION (not for cutoff selection)
            # validation_mode=True skips weighted compromise to get raw knee-point
            validation_details = winter_residual_analysis(
                df[rep_col_region].values, fs, fmax=fmax,
                min_cutoff=None,  # No guardrail - we want to see raw Winter result
                body_region=region,
                return_details=True,
                validation_mode=True  # Get raw knee-point, no weighted compromise
            )
            
            # Check if fixed cutoff is appropriate
            # VALID = fixed cutoff >= Winter suggested (we preserve at least as much signal)
            # AGGRESSIVE = fixed cutoff < Winter suggested (we filter more than Winter recommends)
            winter_suggested = validation_details.get('raw_cutoff_hz', validation_details.get('cutoff_hz', 0))
            if fc_region >= winter_suggested:
                validation_status = "VALID"  # Fixed preserves more signal than Winter's minimum
            else:
                validation_status = "AGGRESSIVE"  # Fixed removes signal Winter thinks is valid
            
            region_cutoffs[region] = fc_region
            region_analysis_details[region] = {
                'cutoff_hz': fc_region,
                'cutoff_method': 'fixed_winter_validated',
                'winter_strict_knee_hz': validation_details.get('strict_knee_hz'),  # Where RMS flattens
                'winter_diminishing_hz': validation_details.get('raw_diminishing_hz'),  # Where biggest drop happens
                'winter_suggested_hz': winter_suggested,  # The chosen validation value (strict_knee)
                'validation_status': validation_status,
                'knee_point_found': validation_details.get('knee_point_found'),
                'method_used': validation_details.get('method_used'),
                'rms_range_ratio': validation_details.get('rms_range_ratio'),
                'curve_is_flat': validation_details.get('curve_is_flat'),
                'rep_col': rep_col_region,
                'rationale': region_config.get('rationale', 'N/A'),
                'residual_rms_mm': validation_details.get('residual_rms_final', 0)  # RMS at the applied cutoff
            }
            
            strict_knee = validation_details.get('strict_knee_hz', 'N/A')
            diminishing = validation_details.get('raw_diminishing_hz', 'N/A')
            # Compute agility factor for this region (same formula as Smart Bias Lerp)
            _agility_region = (min_cutoff_region - 6.0) / (12.0 - 6.0) if 12.0 > 6.0 else 0.0
            logger.info(f"  {region}: FIXED={fc_region:.0f} Hz | Winter RMS knee: {strict_knee} Hz, diminishing: {diminishing} Hz | {validation_status}")
            logger.info(f"  [FILTER_DEBUG] Region: {region} | Agility: {_agility_region:.2f} | Weighted_Fc: {fc_region:.1f}")
            
            # Design and apply filter for this region
            b_region, a_region = butter(N=2, Wn=fc_region/(0.5*fs), btype='low')
            
            for col in cols:
                df_out[col] = filtfilt(b_region, a_region, df[col].values.astype(float))
        
        # Handle unknown markers with median cutoff
        if region_columns['unknown']:
            median_cutoff = np.median(list(region_cutoffs.values()))
            logger.warning(f"  unknown: {len(region_columns['unknown'])} markers, using median cutoff={median_cutoff:.1f} Hz")
            b_unknown, a_unknown = butter(N=2, Wn=median_cutoff/(0.5*fs), btype='low')
            for col in region_columns['unknown']:
                df_out[col] = filtfilt(b_unknown, a_unknown, df[col].values.astype(float))
            region_cutoffs['unknown'] = median_cutoff
        
        # Compute statistics for audit reports
        valid_cutoffs = [v for k, v in region_cutoffs.items() if k != 'unknown']
        weighted_avg_cutoff = float(np.mean(valid_cutoffs)) if valid_cutoffs else 0.0
        
        # Check Winter validation status for all regions
        aggressive_regions = []
        for region, details in region_analysis_details.items():
            if details.get('validation_status') == 'AGGRESSIVE':
                winter_hz = details.get('winter_suggested_hz', 0)
                fixed_hz = details.get('cutoff_hz', 0)
                aggressive_regions.append(f"{region} (fixed={fixed_hz}Hz < winter={winter_hz:.1f}Hz)")
        
        # Winter validation summary (informational only - not a failure)
        if aggressive_regions:
            winter_validation_note = f"Fixed cutoffs are AGGRESSIVE for {len(aggressive_regions)} region(s): {', '.join(aggressive_regions)}. This filters more than Winter suggests - some signal may be removed."
        else:
            winter_validation_note = "All fixed cutoffs validated by Winter analysis (fixed >= Winter suggested)"
        
        # Compute aggregate residual RMS (mean across all regions)
        all_region_rms = [details.get('residual_rms_mm', 0) for details in region_analysis_details.values()]
        mean_residual_rms = float(np.mean(all_region_rms)) if all_region_rms else 0.0
        
        # Update metadata for per-region filtering with FIXED cutoffs
        metadata = {
            "filtering_mode": "per_region_fixed",
            "cutoff_method": "fixed_literature_based",
            "literature_reference": "Winter (2009), Robertson (2014)",
            "region_cutoffs": region_cutoffs,
            "marker_regions": marker_regions,
            "region_analysis_details": region_analysis_details,
            "n_regions": len([r for r in region_cutoffs.keys() if r != 'unknown']),
            "cutoff_range": (min(region_cutoffs.values()), max(region_cutoffs.values())),
            "fmax": fmax,
            "fmin": 1,
            "pos_cols_valid": pos_cols_valid,
            "pos_cols_excluded": excluded_cols,
            "total_pos_cols": len(pos_cols),
            # Audit report compatibility
            "filter_cutoff_hz": weighted_avg_cutoff,
            "filter_range_hz": [1, fmax],
            "residual_rms_mm": mean_residual_rms,  # Aggregate residual RMS across all regions
            # Fixed cutoff approach - Winter is validation only, not failure indicator
            "winter_analysis_failed": False,  # Fixed cutoffs don't "fail" - they're intentional
            "winter_failure_reason": None,
            "winter_validation_note": winter_validation_note,
            "decision_reason": f"Fixed per-region cutoffs based on biomechanical literature. Trunk: 6Hz, Head/Proximal: 8Hz, Distal: 10Hz (Winter 2009, Robertson 2014)"
        }
        
        logger.info(f"Per-region FIXED filtering complete: {len(region_cutoffs)} regions")
        logger.info(f"  Cutoffs applied: {region_cutoffs}")
        logger.info(f"  Validation: {winter_validation_note}")
    
    else:
        # SINGLE GLOBAL CUTOFF (ORIGINAL BEHAVIOR)
        # Check for Winter analysis failure
        if not allow_fmax and fc >= fmax - 1:
            raise ValueError(f"WINTER ANALYSIS FAILED: cutoff = {fc:.1f} Hz (at fmax). "
                            f"This indicates data is already oversmoothed or method applied too late. "
                            f"Expected dance cutoff: 4-10 Hz. "
                            f"To override, set allow_fmax=True.")
        
        # Design filter with optimal cutoff
        b, a = butter(N=2, Wn=fc/(0.5*fs), btype='low')
        
        # Apply filter to valid position columns only
        df_out = df.copy()
        for col in pos_cols_valid:
            df_out[col] = filtfilt(b, a, df[col].values.astype(float))
        
        # Run detailed analysis on a representative column for metadata
        # (Pick the most dynamic column from top_5)
        detailed_analysis = None
        if rep_col is None and not use_trunk_global:
            # Use multi-signal approach - get details from most dynamic column
            col_scores = {col: np.nanstd(np.diff(df[col].values)) for col in pos_cols_valid}
            most_dynamic_col = max(col_scores, key=col_scores.get)
            is_trunk = any(pattern in most_dynamic_col for pattern in ['Pelvis', 'Spine', 'Torso', 'Hips', 'Abdomen', 'Chest', 'Neck'])
            min_cutoff_for_rep = min_cutoff_trunk if is_trunk else min_cutoff_distal
            detailed_analysis = winter_residual_analysis(
                df[most_dynamic_col].values, fs, fmax=fmax,
                min_cutoff=min_cutoff_for_rep, body_region="trunk" if is_trunk else "distal",
                return_details=True
            )
        
        # Determine if Winter analysis actually failed
        # Failure conditions:
        # 1. No knee point found (curve is flat)
        # 2. Guardrail significantly changed the cutoff (>2Hz delta)
        # 3. Cutoff at fmax
        winter_analysis_failed = False
        failure_reason = None
        
        if detailed_analysis:
            # GATE 3 FIX: Use the detailed failure_reason from analysis if available
            if detailed_analysis.get('failure_reason'):
                winter_analysis_failed = True
                failure_reason = detailed_analysis['failure_reason']
            elif not detailed_analysis['knee_point_found']:
                winter_analysis_failed = True
                failure_reason = f"No knee-point found (RMS curve flat, range={detailed_analysis['rms_range_ratio']:.1%})"
            elif detailed_analysis['guardrail_applied'] and detailed_analysis['guardrail_delta_hz'] >= 2.0:
                winter_analysis_failed = True
                failure_reason = f"Guardrail override (+{detailed_analysis['guardrail_delta_hz']:.1f}Hz from {detailed_analysis['raw_cutoff_hz']:.1f}Hz)"
        
        if fc >= fmax - 1:
            winter_analysis_failed = True
            if not failure_reason:  # Only override if not already set
                failure_reason = f"Cutoff at fmax ({fc:.1f}Hz) - data may be pre-smoothed"
        
        # Prepare metadata
        metadata = {
            "filtering_mode": "single_global",
            "cutoff_hz": fc,
            "rep_col": chosen_rep_col,
            "fmin": 1,
            "fmax": fmax,
            "multi_signal_analysis": rep_col is None,
            "individual_cutoffs": cutoffs if rep_col is None else [fc],
            "allow_fmax": allow_fmax,
            "pos_cols_valid": pos_cols_valid,
            "pos_cols_excluded": excluded_cols,
            "total_pos_cols": len(pos_cols),
            # Winter analysis success/failure tracking (Cereatti et al., 2024 - No Silent Fixes)
            "winter_analysis_failed": winter_analysis_failed,
            "winter_failure_reason": failure_reason,
            "winter_details": detailed_analysis,
            # Biomechanical guardrails metadata
            "biomechanical_guardrails": {
                "enabled": True,
                "min_cutoff_trunk": min_cutoff_trunk,
                "min_cutoff_distal": min_cutoff_distal,
                "use_trunk_global": use_trunk_global,
                "strategy": "trunk_global" if use_trunk_global else "multi_signal_with_guardrails"
            }
        }
        
        # Log warning if Winter failed
        if winter_analysis_failed:
            logger.warning(f"WINTER ANALYSIS FAILURE DETECTED: {failure_reason}. "
                          f"Using cutoff={fc:.1f}Hz but flagging as failed for traceability.")
        
        # TASK 3: Filter Ceiling + Residual RMS Synergy Check
        # If filter is at ceiling (16Hz) AND RMS is high (>20mm), flag it
        if detailed_analysis:
            residual_rms = detailed_analysis.get('residual_rms_final', 0)
            residual_slope = detailed_analysis.get('residual_slope', 0)
            
            if fc >= 16.0 and residual_rms > 20.0:
                synergy_warning = (f"High-frequency intensity exceeding filter bounds: "
                                 f"Cutoff at ceiling ({fc:.1f}Hz) with RMS={residual_rms:.2f}mm > 20mm threshold. "
                                 f"This suggests movement contains genuine high-frequency content beyond filter capacity.")
                logger.warning(synergy_warning)
                
                # Add to metadata for audit logging
                metadata['filter_ceiling_warning'] = {
                    'triggered': True,
                    'cutoff_hz': fc,
                    'residual_rms_mm': residual_rms,
                    'residual_slope': residual_slope,
                    'decision_reason': synergy_warning
                }
            else:
                metadata['filter_ceiling_warning'] = {
                    'triggered': False,
                    'cutoff_hz': fc,
                    'residual_rms_mm': residual_rms,
                    'residual_slope': residual_slope
                }
    
    # Ensure quaternion columns are unchanged (both modes)
    quat_cols = [col for col in df.columns if col.endswith(('__qx', '__qy', '__qz', '__qw'))]
    for col in quat_cols:
        if col in df.columns:
            df_out[col] = df[col].values
    
    # PSD Validation (Research Validation Phase 1 - Item 1)
    if PSD_VALIDATION_AVAILABLE:
        try:
            logger.info("Running PSD validation to verify filter quality...")
            
            if per_region_filtering:
                # Per-region PSD validation: validate sample markers from each region
                all_metrics = []
                regions_validated = set()
                
                # Sample up to 2 markers per region for validation
                for region_name, region_cutoff in region_cutoffs.items():
                    region_markers = [m for m in pos_cols_valid 
                                     if marker_regions.get(m) == region_name][:2]
                    
                    for marker in region_markers:
                        if marker in df.columns and marker in df_out.columns:
                            signal_raw = df[marker].values
                            signal_filt = df_out[marker].values
                            
                            if not np.any(np.isnan(signal_raw)) and not np.any(np.isnan(signal_filt)):
                                metrics = analyze_filter_psd_preservation(
                                    signal_raw, signal_filt, fs, region_cutoff
                                )
                                metrics['column'] = marker
                                metrics['region'] = region_name
                                metrics['cutoff_hz'] = region_cutoff
                                all_metrics.append(metrics)
                                regions_validated.add(region_name)
                
                if all_metrics:
                    # Aggregate metrics
                    dance_preservations = [m.get('dance_preservation_pct', 0) for m in all_metrics]
                    noise_attenuations = [m.get('noise_attenuation_pct', 0) for m in all_metrics]
                    
                    psd_validation = {
                        'status': 'VALIDATED',
                        'mode': 'per_region',
                        'regions_validated': list(regions_validated),
                        'n_markers_validated': len(all_metrics),
                        'dance_preservation_mean': float(np.mean(dance_preservations)),
                        'dance_preservation_min': float(np.min(dance_preservations)),
                        'noise_attenuation_mean': float(np.mean(noise_attenuations)),
                        'per_marker_metrics': all_metrics,
                        'overall_filter_quality': 'GOOD' if np.mean(dance_preservations) >= 80 else 'MARGINAL'
                    }
                else:
                    psd_validation = {'status': 'NO_VALID_MARKERS', 'mode': 'per_region'}
                    
                metadata['psd_validation'] = psd_validation
                logger.info(f"Per-region PSD Validation: Dance preservation={psd_validation.get('dance_preservation_mean', 0):.1f}%, "
                           f"Quality={psd_validation.get('overall_filter_quality', 'UNKNOWN')}, "
                           f"Regions={list(regions_validated)}")
            else:
                # Single-cutoff validation
                cutoff_validity = check_filter_cutoff_validity(fc, fs, fmax)
                metadata['cutoff_validity'] = cutoff_validity
                
                psd_validation = validate_winter_filter_multi_signal(
                    df, df_out, pos_cols_valid, fs, fc, n_samples=5
                )
                metadata['psd_validation'] = psd_validation
                
                logger.info(f"PSD Validation Complete: Dance preservation={psd_validation.get('dance_preservation_mean', 0):.1f}%, "
                           f"Filter quality={psd_validation.get('overall_filter_quality', 'UNKNOWN')}")
            
        except Exception as e:
            logger.warning(f"PSD validation failed: {e}")
            metadata['psd_validation'] = {'status': 'ERROR', 'error': str(e)}
    else:
        logger.info("PSD validation skipped (module not available)")
        metadata['psd_validation'] = {'status': 'SKIPPED', 'reason': 'module_not_available'}
    
    # Log completion
    if per_region_filtering:
        logger.info(f"Per-region Winter filtering complete: {len(pos_cols_valid)}/{len(pos_cols)} position columns filtered")
    else:
        logger.info(f"Winter filtering applied: cutoff={fc} Hz, {len(pos_cols_valid)}/{len(pos_cols)} position columns filtered")
    
    return df_out, metadata


def get_position_columns(df: pd.DataFrame) -> List[str]:
    """
    Extract position column names from DataFrame.
    
    Args:
        df: Input DataFrame
        
    Returns:
        List of position column names
    """
    return [col for col in df.columns if col.endswith(('__px', '__py', '__pz'))]


def get_quaternion_columns(df: pd.DataFrame) -> List[str]:
    """
    Extract quaternion column names from DataFrame.
    
    Args:
        df: Input DataFrame
        
    Returns:
        List of quaternion column names
    """
    return [col for col in df.columns if col.endswith(('__qx', '__qy', '__qz', '__qw'))]


def validate_filtering_input(df: pd.DataFrame, 
                         fs: float,
                         pos_cols: Optional[List[str]] = None) -> None:
    """
    Validate input data for filtering operations.
    
    Args:
        df: Input DataFrame
        fs: Sampling frequency
        pos_cols: Position columns to validate
        
    Raises:
        ValueError: If validation fails
    """
    if fs <= 0:
        raise ValueError(f"Sampling frequency must be positive, got {fs}")
    
    if 'time_s' not in df.columns:
        raise ValueError("DataFrame must contain 'time_s' column")
    
    if pos_cols is None:
        pos_cols = get_position_columns(df)
    
    if not pos_cols:
        raise ValueError("No position columns found for filtering")
    
    missing_cols = [col for col in pos_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Position columns not found: {missing_cols}")
    
    # Check time grid regularity (should be constant dt)
    time_diffs = np.diff(df['time_s'].values)
    if not np.allclose(time_diffs, time_diffs[0], rtol=1e-6):
        logger.warning("Time grid is not perfectly regular - filtering may be suboptimal")


def compute_filter_characteristics(fc: float, fs: float) -> Dict[str, float]:
    """
    Compute filter characteristics for documentation.
    
    Args:
        fc: Cutoff frequency in Hz
        fs: Sampling frequency in Hz
        
    Returns:
        Dictionary with filter characteristics
    """
    # Normalized cutoff frequency
    wn = fc / (0.5 * fs)
    
    # Phase delay at different frequencies (approximate for 2nd-order Butterworth)
    freqs = np.array([0.1, 0.5, 1.0, 5.0, 10.0]) * fc
    phase_delays = []
    
    for freq in freqs:
        if freq < fc:
            # Below cutoff: minimal phase delay
            phase_delay = 0.0
        else:
            # Above cutoff: increasing phase delay
            phase_delay = np.degrees(np.arctan(freq/fc))
        phase_delays.append(phase_delay)
    
    return {
        "cutoff_hz": fc,
        "normalized_wn": wn,
        "filter_order": 2,
        "phase_delay_10pct_fc": phase_delays[0] if len(phase_delays) > 0 else 0,
        "phase_delay_50pct_fc": phase_delays[1] if len(phase_delays) > 1 else 0,
        "phase_delay_fc": phase_delays[2] if len(phase_delays) > 2 else 0,
        "phase_delay_5x_fc": phase_delays[3] if len(phase_delays) > 3 else 0,
        "phase_delay_10x_fc": phase_delays[4] if len(phase_delays) > 4 else 0
    }


# =============================================================================
# POST-FILTER PSD COMPARISON — "No Oversmoothing" GUARANTEE
# =============================================================================

def compute_psd_comparison(
    signal_raw: np.ndarray,
    signal_filtered: np.ndarray,
    fs: float,
    dance_band_hz: Tuple[float, float] = (1.0, 13.0),
    noise_band_hz: Tuple[float, float] = (20.0, 50.0),
    nperseg: int = 256,
) -> Dict:
    """
    Compare power spectral density between raw and filtered signals.

    Provides an explicit "No Oversmoothing" guarantee by verifying:
    1. Signal power in the dance band (1-13 Hz) is preserved (delta < 3 dB).
    2. Noise power above the cutoff is attenuated by >= 20 dB.
    3. No spectral leakage from interpolation artifacts.

    Uses Welch's method for robust PSD estimation.

    Parameters
    ----------
    signal_raw : np.ndarray
        Original (pre-filter) signal, 1-D.
    signal_filtered : np.ndarray
        Post-filter signal, same length as *signal_raw*.
    fs : float
        Sampling frequency in Hz.
    dance_band_hz : tuple
        (low, high) frequency bounds for the Gaga movement band.
    noise_band_hz : tuple
        (low, high) frequency bounds for the noise reference band.
    nperseg : int
        Welch segment length (default 256 ~ 2.1 s at 120 Hz).

    Returns
    -------
    dict with keys:
        psd_verdict : str
            "PASS", "REVIEW_OVERSMOOTHING", or "REVIEW_NOISE_RESIDUAL"
        dance_band_delta_dB : float
            Mean power change in dance band (negative = power lost).
        noise_band_attenuation_dB : float
            Mean attenuation in noise band (positive = noise reduced).
        max_dance_band_loss_dB : float
            Worst-case power loss at any frequency in dance band.
        freqs : np.ndarray
            Frequency vector (for optional plotting).
        psd_raw_dB : np.ndarray
            Raw signal PSD in dB (for optional plotting).
        psd_filt_dB : np.ndarray
            Filtered signal PSD in dB (for optional plotting).
    """
    from scipy.signal import welch as scipy_welch

    # Guard: skip if signals are too short or identical
    if len(signal_raw) < nperseg:
        nperseg = max(16, len(signal_raw) // 2)

    # Remove NaNs (Welch cannot handle them)
    valid = np.isfinite(signal_raw) & np.isfinite(signal_filtered)
    if valid.sum() < nperseg:
        return {
            "psd_verdict": "SKIP_INSUFFICIENT_DATA",
            "dance_band_delta_dB": 0.0,
            "noise_band_attenuation_dB": 0.0,
            "max_dance_band_loss_dB": 0.0,
        }

    sig_r = signal_raw[valid]
    sig_f = signal_filtered[valid]

    freqs, psd_raw = scipy_welch(sig_r, fs=fs, nperseg=nperseg)
    _, psd_filt = scipy_welch(sig_f, fs=fs, nperseg=nperseg)

    # Convert to dB (floor at -120 dB to avoid log(0))
    eps = 1e-12
    psd_raw_dB = 10 * np.log10(np.maximum(psd_raw, eps))
    psd_filt_dB = 10 * np.log10(np.maximum(psd_filt, eps))
    delta_dB = psd_filt_dB - psd_raw_dB  # positive = gain, negative = loss

    # Dance band analysis (1-13 Hz)
    dance_mask = (freqs >= dance_band_hz[0]) & (freqs <= dance_band_hz[1])
    if dance_mask.any():
        dance_delta = float(np.mean(delta_dB[dance_mask]))
        max_dance_loss = float(np.min(delta_dB[dance_mask]))
    else:
        dance_delta = 0.0
        max_dance_loss = 0.0

    # Noise band analysis (20-50 Hz)
    noise_mask = (freqs >= noise_band_hz[0]) & (freqs <= noise_band_hz[1])
    if noise_mask.any():
        noise_attenuation = float(-np.mean(delta_dB[noise_mask]))
    else:
        noise_attenuation = 0.0

    # Verdict
    if max_dance_loss < -3.0:
        verdict = "REVIEW_OVERSMOOTHING"
    elif noise_attenuation < 20.0 and noise_mask.any():
        verdict = "REVIEW_NOISE_RESIDUAL"
    else:
        verdict = "PASS"

    return {
        "psd_verdict": verdict,
        "dance_band_delta_dB": round(dance_delta, 2),
        "noise_band_attenuation_dB": round(noise_attenuation, 2),
        "max_dance_band_loss_dB": round(max_dance_loss, 2),
        "freqs": freqs,
        "psd_raw_dB": psd_raw_dB,
        "psd_filt_dB": psd_filt_dB,
    }


def run_psd_audit(
    df_raw: pd.DataFrame,
    df_filtered: pd.DataFrame,
    fs: float,
    pos_cols: Optional[List[str]] = None,
    dance_band_hz: Tuple[float, float] = (1.0, 13.0),
    noise_band_hz: Tuple[float, float] = (20.0, 50.0),
) -> Dict:
    """
    Run PSD comparison across all position columns (batch audit).

    Aggregates per-column PSD verdicts into a session-level summary
    for the Engineering Profile.

    Parameters
    ----------
    df_raw : pd.DataFrame
        DataFrame BEFORE 3-stage filtering.
    df_filtered : pd.DataFrame
        DataFrame AFTER 3-stage filtering.
    fs : float
        Sampling frequency.
    pos_cols : list, optional
        Position columns to audit. Auto-detected if None.
    dance_band_hz, noise_band_hz : tuple
        Frequency band boundaries.

    Returns
    -------
    dict with:
        session_psd_verdict : str
            Overall verdict ("PASS" / "REVIEW_OVERSMOOTHING" / "REVIEW_NOISE_RESIDUAL").
        n_columns_audited : int
        n_oversmoothing : int
            Columns where dance-band power loss > 3 dB.
        n_noise_residual : int
            Columns where noise attenuation < 20 dB.
        mean_dance_delta_dB : float
        mean_noise_attenuation_dB : float
        worst_column : str or None
        worst_dance_loss_dB : float
        per_column : dict
            Per-column PSD results (without raw arrays to keep JSON-safe).
    """
    if pos_cols is None:
        pos_cols = [c for c in df_raw.columns
                    if c.endswith(('__px', '__py', '__pz'))]

    per_column = {}
    dance_deltas = []
    noise_attenuations = []
    n_oversmoothing = 0
    n_noise_residual = 0
    worst_col = None
    worst_loss = 0.0

    for col in pos_cols:
        if col not in df_raw.columns or col not in df_filtered.columns:
            continue

        result = compute_psd_comparison(
            df_raw[col].values.astype(float),
            df_filtered[col].values.astype(float),
            fs,
            dance_band_hz=dance_band_hz,
            noise_band_hz=noise_band_hz,
        )

        # Store JSON-safe subset (no numpy arrays)
        per_column[col] = {
            "psd_verdict": result["psd_verdict"],
            "dance_band_delta_dB": result["dance_band_delta_dB"],
            "noise_band_attenuation_dB": result["noise_band_attenuation_dB"],
            "max_dance_band_loss_dB": result["max_dance_band_loss_dB"],
        }

        if result["psd_verdict"] == "REVIEW_OVERSMOOTHING":
            n_oversmoothing += 1
        elif result["psd_verdict"] == "REVIEW_NOISE_RESIDUAL":
            n_noise_residual += 1

        dance_deltas.append(result["dance_band_delta_dB"])
        noise_attenuations.append(result["noise_band_attenuation_dB"])

        if result["max_dance_band_loss_dB"] < worst_loss:
            worst_loss = result["max_dance_band_loss_dB"]
            worst_col = col

    # Session-level verdict
    if n_oversmoothing > 0:
        session_verdict = "REVIEW_OVERSMOOTHING"
    elif n_noise_residual > len(pos_cols) * 0.5:
        session_verdict = "REVIEW_NOISE_RESIDUAL"
    else:
        session_verdict = "PASS"

    return {
        "session_psd_verdict": session_verdict,
        "n_columns_audited": len(per_column),
        "n_oversmoothing": n_oversmoothing,
        "n_noise_residual": n_noise_residual,
        "mean_dance_delta_dB": round(float(np.mean(dance_deltas)), 2) if dance_deltas else 0.0,
        "mean_noise_attenuation_dB": round(float(np.mean(noise_attenuations)), 2) if noise_attenuations else 0.0,
        "worst_column": worst_col,
        "worst_dance_loss_dB": round(worst_loss, 2),
        "per_column": per_column,
    }
