"""
Center of Mass (CoM) Engine
============================
Computes per-segment and whole-body center of mass from 3-D joint positions.

Segment mass fractions and proximal CoM ratios from:
    de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment inertia
    parameters. Journal of Biomechanics, 29(9), 1223-1230.

These values supersede the original Winter (2009) Table 3.1 with improved
accuracy for marker-based motion capture applications.

Author: Gaga Motion Analysis Pipeline
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ============================================================
# DE LEVA (1996) SEGMENT PARAMETERS  (male, adjusted Zatsiorsky)
# ============================================================
# Each entry:
#   proximal_joint : joint name at the proximal end of the segment
#   distal_joint   : joint name at the distal end
#   mass_frac      : segment mass as fraction of total body mass
#   com_prox_ratio : CoM position measured from proximal end,
#                    expressed as a fraction of segment length
#
# The 16 segments below sum to 1.0 (100% body mass).
# ============================================================

SEGMENT_PARAMS: Dict[str, dict] = {
    # --- Head & Trunk (4 segments) ---
    "head": {
        "proximal": "Neck",
        "distal": "Head",
        "mass_frac": 0.0694,
        "com_prox_ratio": 0.5002,
    },
    "upper_trunk": {
        "proximal": "Spine1",
        "distal": "Neck",
        "mass_frac": 0.1596,
        "com_prox_ratio": 0.5066,
    },
    "middle_trunk": {
        "proximal": "Spine",
        "distal": "Spine1",
        "mass_frac": 0.1633,
        "com_prox_ratio": 0.4502,
    },
    "lower_trunk": {
        "proximal": "Hips",
        "distal": "Spine",
        "mass_frac": 0.1117,
        "com_prox_ratio": 0.6115,
    },

    # --- Left Upper Limb (3 segments) ---
    "left_upper_arm": {
        "proximal": "LeftArm",
        "distal": "LeftForeArm",
        "mass_frac": 0.0271,
        "com_prox_ratio": 0.5772,
    },
    "left_forearm": {
        "proximal": "LeftForeArm",
        "distal": "LeftHand",
        "mass_frac": 0.0162,
        "com_prox_ratio": 0.4574,
    },
    "left_hand": {
        "proximal": "LeftHand",
        "distal": "LeftHand",  # terminal segment
        "mass_frac": 0.0061,
        "com_prox_ratio": 0.0,  # CoM at wrist (terminal approx)
    },

    # --- Right Upper Limb (3 segments) ---
    "right_upper_arm": {
        "proximal": "RightArm",
        "distal": "RightForeArm",
        "mass_frac": 0.0271,
        "com_prox_ratio": 0.5772,
    },
    "right_forearm": {
        "proximal": "RightForeArm",
        "distal": "RightHand",
        "mass_frac": 0.0162,
        "com_prox_ratio": 0.4574,
    },
    "right_hand": {
        "proximal": "RightHand",
        "distal": "RightHand",  # terminal segment
        "mass_frac": 0.0061,
        "com_prox_ratio": 0.0,
    },

    # --- Left Lower Limb (3 segments) ---
    "left_thigh": {
        "proximal": "LeftUpLeg",
        "distal": "LeftLeg",
        "mass_frac": 0.1416,
        "com_prox_ratio": 0.4095,
    },
    "left_shank": {
        "proximal": "LeftLeg",
        "distal": "LeftFoot",
        "mass_frac": 0.0433,
        "com_prox_ratio": 0.4459,
    },
    "left_foot": {
        "proximal": "LeftFoot",
        "distal": "LeftToeBase",
        "mass_frac": 0.0137,
        "com_prox_ratio": 0.4415,
    },

    # --- Right Lower Limb (3 segments) ---
    "right_thigh": {
        "proximal": "RightUpLeg",
        "distal": "RightLeg",
        "mass_frac": 0.1416,
        "com_prox_ratio": 0.4095,
    },
    "right_shank": {
        "proximal": "RightLeg",
        "distal": "RightFoot",
        "mass_frac": 0.0433,
        "com_prox_ratio": 0.4459,
    },
    "right_foot": {
        "proximal": "RightFoot",
        "distal": "RightToeBase",
        "mass_frac": 0.0137,
        "com_prox_ratio": 0.4415,
    },
}

# Sanity: mass fractions must sum to 1.0
_TOTAL_MASS = sum(s["mass_frac"] for s in SEGMENT_PARAMS.values())
assert abs(_TOTAL_MASS - 1.0) < 1e-6, (
    f"Segment mass fractions sum to {_TOTAL_MASS}, expected 1.0"
)


def _get_joint_positions(
    df: pd.DataFrame,
    joint: str,
    col_template: str = "{joint}__lin_rel_p{axis}",
) -> Optional[np.ndarray]:
    """
    Extract (T, 3) position array for *joint* from DataFrame columns.

    Parameters
    ----------
    df : pd.DataFrame
        Master kinematic DataFrame.
    joint : str
        Joint name (e.g. "Hips").
    col_template : str
        Column naming pattern.  Must contain ``{joint}`` and ``{axis}``
        placeholders.  Default matches the parquet convention
        ``{joint}__lin_rel_px``.

    Returns
    -------
    np.ndarray of shape (T, 3) or None if any axis column is missing.
    """
    cols = [
        col_template.format(joint=joint, axis=ax)
        for ax in ("x", "y", "z")
    ]
    if not all(c in df.columns for c in cols):
        return None
    return df[cols].values


def compute_segment_com(
    pos_proximal: np.ndarray,
    pos_distal: np.ndarray,
    com_prox_ratio: float,
) -> np.ndarray:
    """
    Compute segment centre-of-mass position.

    CoM_seg = pos_proximal + com_prox_ratio * (pos_distal - pos_proximal)

    Parameters
    ----------
    pos_proximal : (T, 3)
    pos_distal   : (T, 3)
    com_prox_ratio : float in [0, 1]

    Returns
    -------
    (T, 3) segment CoM positions.
    """
    return pos_proximal + com_prox_ratio * (pos_distal - pos_proximal)


def compute_whole_body_com(
    df: pd.DataFrame,
    col_template: str = "{joint}__lin_rel_p{axis}",
    segments: Optional[Dict[str, dict]] = None,
) -> Tuple[np.ndarray, Dict[str, object]]:
    """
    Compute whole-body centre of mass (WBCoM) with missing-segment compensation.

    WBCoM = sum(m_i * CoM_i) / sum(m_i)   (over available segments)

    When a segment is missing (joint not found in *df*), its mass fraction
    is redistributed proportionally across the remaining segments so that
    WBCoM never becomes NaN and the effective total mass stays at 100 %.

    Parameters
    ----------
    df : pd.DataFrame
        Master kinematic DataFrame with position columns.
    col_template : str
        Column naming pattern (default: ``{joint}__lin_rel_p{axis}``).
    segments : dict, optional
        Override for SEGMENT_PARAMS (testing / alternate models).

    Returns
    -------
    wbcom : np.ndarray, shape (T, 3)
        Whole-body CoM position per frame.
    report : dict
        Audit dictionary with per-segment availability, mass redistribution,
        and warnings.
    """
    if segments is None:
        segments = SEGMENT_PARAMS

    T = len(df)
    weighted_sum = np.zeros((T, 3))
    total_mass_used = 0.0

    per_segment: Dict[str, dict] = {}
    missing_segments: List[str] = []
    missing_mass = 0.0

    for seg_name, params in segments.items():
        prox = params["proximal"]
        dist = params["distal"]
        mass = params["mass_frac"]
        ratio = params["com_prox_ratio"]

        pos_prox = _get_joint_positions(df, prox, col_template)
        pos_dist = _get_joint_positions(df, dist, col_template)

        if pos_prox is None:
            missing_segments.append(seg_name)
            missing_mass += mass
            per_segment[seg_name] = {"available": False, "reason": f"proximal joint '{prox}' missing"}
            continue

        # Terminal segments (proximal == distal): CoM at the joint itself
        if prox == dist or pos_dist is None:
            seg_com = pos_prox.copy()
            if pos_dist is None and prox != dist:
                per_segment[seg_name] = {
                    "available": True,
                    "note": f"distal joint '{dist}' missing; CoM placed at proximal '{prox}'",
                }
            else:
                per_segment[seg_name] = {"available": True}
        else:
            seg_com = compute_segment_com(pos_prox, pos_dist, ratio)
            per_segment[seg_name] = {"available": True}

        weighted_sum += mass * seg_com
        total_mass_used += mass

    # --- Missing-Segment Compensation ---
    # Redistribute missing mass proportionally across available segments
    if total_mass_used > 0 and total_mass_used < 1.0:
        scale = 1.0 / total_mass_used
        wbcom = weighted_sum * scale
        logger.info(
            "CoM: %d/%d segments available (%.1f%% mass). "
            "Missing mass (%.2f%%) redistributed proportionally.",
            len(segments) - len(missing_segments),
            len(segments),
            total_mass_used * 100,
            missing_mass * 100,
        )
    elif total_mass_used > 0:
        wbcom = weighted_sum  # all segments present -> already normalised
    else:
        wbcom = np.full((T, 3), np.nan)
        logger.error("CoM: NO segments available. Returning NaN.")

    report = {
        "segments_total": len(segments),
        "segments_available": len(segments) - len(missing_segments),
        "segments_missing": missing_segments,
        "mass_available_pct": round(total_mass_used * 100, 2),
        "mass_redistributed_pct": round(missing_mass * 100, 2),
        "compensation_applied": missing_mass > 0,
        "per_segment": per_segment,
    }

    return wbcom, report


def add_com_to_dataframe(
    df: pd.DataFrame,
    col_template: str = "{joint}__lin_rel_p{axis}",
    prefix: str = "wbc_com",
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """
    Convenience wrapper: compute WBCoM and append columns to *df*.

    Adds ``{prefix}_x``, ``{prefix}_y``, ``{prefix}_z`` columns.

    Parameters
    ----------
    df : pd.DataFrame
        Master kinematic DataFrame (modified in-place AND returned).
    col_template : str
        Position column naming pattern.
    prefix : str
        Column name prefix for the CoM columns (default ``wbc_com``).

    Returns
    -------
    df : pd.DataFrame
        Same DataFrame with 3 new columns.
    report : dict
        CoM computation audit report.
    """
    wbcom, report = compute_whole_body_com(df, col_template=col_template)

    df[f"{prefix}_x"] = wbcom[:, 0]
    df[f"{prefix}_y"] = wbcom[:, 1]
    df[f"{prefix}_z"] = wbcom[:, 2]

    # --- CoM Integrity Validation ---
    # Verify that WBCoM varies logically: not constant, not NaN-dominated,
    # and has physiologically plausible range.
    com_nan_pct = float(np.isnan(wbcom).any(axis=1).mean() * 100)
    com_range_x = float(np.nanmax(wbcom[:, 0]) - np.nanmin(wbcom[:, 0]))
    com_range_y = float(np.nanmax(wbcom[:, 1]) - np.nanmin(wbcom[:, 1]))
    com_range_z = float(np.nanmax(wbcom[:, 2]) - np.nanmin(wbcom[:, 2]))
    com_std_x = float(np.nanstd(wbcom[:, 0]))
    com_std_y = float(np.nanstd(wbcom[:, 1]))
    com_std_z = float(np.nanstd(wbcom[:, 2]))

    report["com_integrity"] = {
        "nan_pct": round(com_nan_pct, 4),
        "range_x": round(com_range_x, 6),
        "range_y": round(com_range_y, 6),
        "range_z": round(com_range_z, 6),
        "std_x": round(com_std_x, 6),
        "std_y": round(com_std_y, 6),
        "std_z": round(com_std_z, 6),
    }

    if com_nan_pct > 1.0:
        logger.warning(
            "CoM INTEGRITY WARNING: %.2f%% of frames have NaN in WBCoM. "
            "Check segment availability (%d/%d segments).",
            com_nan_pct, report["segments_available"], report["segments_total"],
        )

    # Constant CoM check: if std is near-zero on all axes, data is suspect
    if com_std_x < 1e-6 and com_std_y < 1e-6 and com_std_z < 1e-6:
        logger.error(
            "CoM INTEGRITY FAILURE: WBCoM is CONSTANT (std ≈ 0 on all axes). "
            "This indicates no segment positions were available or all segments "
            "are stationary. Check input data."
        )
        report["com_integrity"]["status"] = "FAIL_CONSTANT"
    elif com_nan_pct > 50.0:
        report["com_integrity"]["status"] = "FAIL_NAN_DOMINATED"
    else:
        report["com_integrity"]["status"] = "PASS"

    logger.info(
        "CoM columns added: %s_x/y/z  (%d/%d segments, %.1f%% mass). "
        "Range: x=%.4f y=%.4f z=%.4f | Integrity: %s",
        prefix,
        report["segments_available"],
        report["segments_total"],
        report["mass_available_pct"],
        com_range_x, com_range_y, com_range_z,
        report["com_integrity"]["status"],
    )

    return df, report
