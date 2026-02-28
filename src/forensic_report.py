"""
Forensic QA & Reporting Engine  —  v3.1
========================================
Generates a structured forensic audit proving that the data-cleaning
pipeline distinguished between **technical noise** (removed) and
**high-velocity Gaga movements** (preserved).

Every quantitative metric follows a consistent *raw / clean / delta*
triplet so a supervisor can see what changed at a glance.

Public API
----------
    generate_cleaning_report(original_df, cleaned_df, config, ...)
        → dict   (and optionally writes JSON + PNG plots to *output_dir*)

Author : Gaga Motion Analysis Pipeline
Date   : 2026-02-17
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import welch

from forensic_config import (
    ACCEL_SPIKE_THRESHOLD_MM_S2,
    BONE_CV_GOLD,
    BONE_CV_WARN,
    FALLBACK_JOINTS,
    GAP_HEATMAP_BIN_SEC,
    MIN_FRAMES_FACTOR,
    PSD_MIN_SEGMENT_FRAMES,
    PSD_NOISE_FLOOR_HZ,
    PSD_NPERSEG,
    PSD_SIGNAL_BAND_HZ,
    REPRESENTATIVE_JOINTS,
)

logger = logging.getLogger(__name__)

# =====================================================================
# helpers
# =====================================================================

def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    """Division guarded against zero / NaN."""
    if b == 0 or np.isnan(b):
        return default
    return a / b


def _config_hash(cfg: dict) -> str:
    """SHA-256 of the serialised config for reproducibility anchoring."""
    try:
        import yaml
        blob = yaml.dump(cfg, sort_keys=True).encode()
    except Exception:
        blob = json.dumps(cfg, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _pos_cols(df: pd.DataFrame) -> List[str]:
    """Return all position columns (__px / __py / __pz)."""
    return [c for c in df.columns if c.endswith(("__px", "__py", "__pz"))]


def _quat_cols(df: pd.DataFrame) -> List[str]:
    """Return all quaternion columns."""
    return [c for c in df.columns if c.endswith(("__qx", "__qy", "__qz", "__qw"))]


def _joint_names_from_pos(df: pd.DataFrame) -> List[str]:
    """Unique joint names extracted from position columns."""
    return sorted({c.rsplit("__", 1)[0] for c in _pos_cols(df)})


def _resolve_joint(joint: str, available: List[str]) -> Optional[str]:
    """Return *joint* if present, else first available fallback."""
    if joint in available:
        return joint
    for fb in FALLBACK_JOINTS.get(joint, []):
        if fb in available:
            return fb
    return None


def _contiguous_valid_runs(arr: np.ndarray) -> List[Tuple[int, int]]:
    """Return (start, end) of every contiguous block of finite values."""
    finite = np.isfinite(arr)
    runs: List[Tuple[int, int]] = []
    in_run = False
    start = 0
    for i, v in enumerate(finite):
        if v and not in_run:
            start = i
            in_run = True
        elif not v and in_run:
            runs.append((start, i))
            in_run = False
    if in_run:
        runs.append((start, len(arr)))
    return runs


def _nan_gap_runs(arr: np.ndarray) -> List[Tuple[int, int]]:
    """Return (start, end) of every contiguous NaN block."""
    is_nan = np.isnan(arr) if np.issubdtype(arr.dtype, np.floating) else pd.isna(arr)
    runs: List[Tuple[int, int]] = []
    in_run = False
    start = 0
    for i, v in enumerate(is_nan):
        if v and not in_run:
            start = i
            in_run = True
        elif not v and in_run:
            runs.append((start, i))
            in_run = False
    if in_run:
        runs.append((start, len(arr)))
    return runs


# =====================================================================
# Block A — Inventory
# =====================================================================

def _block_a_inventory(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    config: dict,
    fs: float,
) -> dict:
    """Global data inventory: NaN counts, recovery rate, logged thresholds."""
    analysis_cols = _pos_cols(original_df) + _quat_cols(original_df)
    total_cells = len(original_df) * len(analysis_cols)

    nans_raw = int(original_df[analysis_cols].isna().sum().sum()) if analysis_cols else 0
    nans_clean = int(cleaned_df[analysis_cols].isna().sum().sum()) if analysis_cols else 0

    missing_pct_raw = round(100.0 * _safe_div(nans_raw, total_cells), 4)
    missing_pct_clean = round(100.0 * _safe_div(nans_clean, total_cells), 4)

    # Recovery rate: handle edge case where raw has zero NaN
    if nans_raw == 0:
        if nans_clean == 0:
            recovery_rate = 1.0   # Perfect: no missing data in either
        else:
            recovery_rate = -1.0  # Sentinel: cleaning introduced NaN (gap guard)
    else:
        recovery_rate = round(1.0 - _safe_div(nans_clean, nans_raw, default=1.0), 6)

    # Pull actual thresholds from config
    filt = config.get("filtering", {})
    thresholds_logged = {
        "max_gap_pos_sec": config.get("max_gap_pos_sec"),
        "max_gap_quat_sec": config.get("max_gap_quat_sec"),
        "stage1_interp_limit_sec": 0.25,
        "stage1_velocity_limit_mm_s": filt.get("velocity_limit"),
        "stage1_zscore_threshold": filt.get("zscore_threshold"),
        "hampel_window": filt.get("hampel_window"),
        "hampel_n_sigma": filt.get("hampel_n_sigma"),
        "fs_hz": fs,
    }

    return {
        "total_cells": total_cells,
        "total_analysis_columns": len(analysis_cols),
        "total_frames": len(original_df),
        "raw": {
            "total_nans": nans_raw,
            "missing_percent": missing_pct_raw,
        },
        "clean": {
            "total_nans": nans_clean,
            "missing_percent": missing_pct_clean,
        },
        "delta": {
            "nans_recovered": nans_raw - nans_clean,
            "recovery_rate": recovery_rate,
            "interpretation": (
                (
                    f"Raw data was complete (0 NaN). Cleaning identified "
                    f"{nans_clean} cells ({missing_pct_clean}%) as unreliable "
                    f"(gap guard / artifact NaN injection)."
                )
                if recovery_rate == -1.0
                else (
                    "Perfect capture and perfect cleaning — zero NaN throughout."
                    if recovery_rate == 1.0 and nans_raw == 0
                    else (
                        f"{recovery_rate*100:.1f}% of missing data recovered. "
                        f"Remaining NaNs are gaps > threshold, intentionally preserved "
                        f"to avoid hallucinating data."
                    )
                )
            ),
        },
        "thresholds_logged": thresholds_logged,
        "config_hash": _config_hash(config),
    }


# =====================================================================
# Block B — Gap Analysis
# =====================================================================

def _block_b_gaps(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    fs: float,
    config: dict,
) -> dict:
    """Gap analysis: raw vs clean gap state, boundary gaps, topology data."""
    pos_cols = _pos_cols(original_df)
    gap_threshold_sec = 0.25  # Stage-1 interpolation cap
    gap_threshold_frames = int(fs * gap_threshold_sec)
    n_frames = len(original_df)
    bin_sec = GAP_HEATMAP_BIN_SEC
    n_bins = max(1, int(np.ceil(n_frames / (fs * bin_sec))))

    # --- per-joint gap census (raw & clean) ---
    raw_gaps_all: List[dict] = []
    clean_gaps_all: List[dict] = []
    topology_raw: Dict[str, List[float]] = {}  # joint → list[fraction per bin]
    topology_clean: Dict[str, List[float]] = {}
    boundary_gaps = 0

    joints = _joint_names_from_pos(original_df)

    for joint in joints:
        jcols = [c for c in pos_cols if c.startswith(joint + "__")]
        if not jcols:
            continue

        # Combine: a frame is "missing" if ANY axis is NaN
        raw_missing = original_df[jcols].isna().any(axis=1).values
        clean_missing = cleaned_df[jcols].isna().any(axis=1).values if all(c in cleaned_df.columns for c in jcols) else raw_missing

        # Find raw gap runs
        for start, end in _nan_gap_runs(raw_missing.astype(float)):
            dur_frames = end - start
            dur_sec = round(dur_frames / fs, 4)
            is_boundary = (start == 0) or (end >= n_frames)
            if is_boundary:
                boundary_gaps += 1
            raw_gaps_all.append({
                "joint": joint,
                "start_frame": int(start),
                "end_frame": int(end),
                "duration_frames": int(dur_frames),
                "duration_sec": dur_sec,
                "category": "small" if dur_frames <= gap_threshold_frames else "large",
                "is_boundary": is_boundary,
            })

        # Clean gap runs
        for start, end in _nan_gap_runs(clean_missing.astype(float)):
            dur_frames = end - start
            dur_sec = round(dur_frames / fs, 4)
            clean_gaps_all.append({
                "joint": joint,
                "start_frame": int(start),
                "end_frame": int(end),
                "duration_frames": int(dur_frames),
                "duration_sec": dur_sec,
            })

        # Topology heatmap data (fraction missing per time bin)
        raw_bins = []
        clean_bins = []
        for b in range(n_bins):
            s = int(b * fs * bin_sec)
            e = min(int((b + 1) * fs * bin_sec), n_frames)
            raw_bins.append(round(float(raw_missing[s:e].mean()), 4))
            clean_bins.append(round(float(clean_missing[s:e].mean()), 4))
        topology_raw[joint] = raw_bins
        topology_clean[joint] = clean_bins

    # Aggregate
    small_raw = [g for g in raw_gaps_all if g["category"] == "small"]
    large_raw = [g for g in raw_gaps_all if g["category"] == "large"]
    total_gap_dur_raw = sum(g["duration_sec"] for g in raw_gaps_all)
    total_gap_dur_clean = sum(g["duration_sec"] for g in clean_gaps_all)

    return {
        "gap_threshold_sec": gap_threshold_sec,
        "gap_threshold_frames": gap_threshold_frames,
        "raw": {
            "total_gaps": len(raw_gaps_all),
            "small_gaps": len(small_raw),
            "large_gaps": len(large_raw),
            "boundary_gaps": boundary_gaps,
            "total_gap_duration_sec": round(total_gap_dur_raw, 3),
            "longest_gap_sec": round(max((g["duration_sec"] for g in raw_gaps_all), default=0.0), 4),
        },
        "clean": {
            "total_gaps": len(clean_gaps_all),
            "total_gap_duration_sec": round(total_gap_dur_clean, 3),
            "longest_gap_sec": round(max((g["duration_sec"] for g in clean_gaps_all), default=0.0), 4),
        },
        "delta": {
            "gaps_resolved": len(raw_gaps_all) - len(clean_gaps_all),
            "duration_recovered_sec": round(total_gap_dur_raw - total_gap_dur_clean, 3),
            "interpretation": (
                f"{len(small_raw)} small gaps (≤{gap_threshold_sec}s) safely interpolated. "
                f"{len(large_raw)} large gaps intentionally preserved as NaN. "
                f"{boundary_gaps} boundary gaps (frame 0 or end) left as NaN — "
                f"causal interpolation would extrapolate."
            ),
        },
        "topology_raw": topology_raw,
        "topology_clean": topology_clean,
        "bin_sec": bin_sec,
        "n_bins": n_bins,
    }


# =====================================================================
# Block C — Noise Reduction
# =====================================================================

def _segment_welch(signal: np.ndarray, fs: float) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Compute weighted-average Welch PSD across contiguous valid segments."""
    runs = _contiguous_valid_runs(signal)
    runs = [(s, e) for s, e in runs if (e - s) >= PSD_MIN_SEGMENT_FRAMES]
    if not runs:
        return None

    psd_accum = None
    total_weight = 0
    freqs = None

    for s, e in runs:
        seg = signal[s:e]
        nperseg = min(PSD_NPERSEG, len(seg))
        f, p = welch(seg, fs=fs, nperseg=nperseg)
        weight = len(seg)
        if psd_accum is None:
            freqs = f
            psd_accum = p * weight
        else:
            if len(f) == len(freqs):
                psd_accum += p * weight
            else:
                continue  # skip mismatched segment
        total_weight += weight

    if psd_accum is None or total_weight == 0:
        return None
    return freqs, psd_accum / total_weight


def _psd_ratio(f: np.ndarray, psd: np.ndarray, band: Tuple[float, float]) -> float:
    """Fraction of total power inside *band*."""
    mask = (f >= band[0]) & (f <= band[1])
    total = float(np.trapz(psd, f)) if len(f) > 1 else 1e-12
    in_band = float(np.trapz(psd[mask], f[mask])) if mask.any() else 0.0
    return round(_safe_div(in_band, total), 4)


def _block_c_noise(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    fs: float,
    snr_report: Optional[dict],
) -> dict:
    """Noise reduction metrics: per-joint RMS, SNR, PSD comparison."""
    pos_cols = _pos_cols(original_df)
    common_cols = [c for c in pos_cols if c in cleaned_df.columns]

    # --- per-joint RMS (raw / clean / residual) ---
    rms_records: Dict[str, dict] = {}
    for col in common_cols:
        raw = original_df[col].values.astype(float)
        cln = cleaned_df[col].values.astype(float)
        valid = np.isfinite(raw) & np.isfinite(cln)
        n_valid = int(valid.sum())
        if n_valid < 10:
            continue

        raw_v = raw[valid]
        cln_v = cln[valid]
        residual = raw_v - cln_v

        raw_rms = float(np.sqrt(np.mean(raw_v ** 2)))
        cln_rms = float(np.sqrt(np.mean(cln_v ** 2)))
        res_rms = float(np.sqrt(np.mean(residual ** 2)))
        max_res = float(np.max(np.abs(residual)))
        res_pct = round(100.0 * _safe_div(res_rms, raw_rms), 2)

        rms_records[col] = {
            "raw_rms": round(raw_rms, 4),
            "clean_rms": round(cln_rms, 4),
            "residual_rms": round(res_rms, 4),
            "max_residual": round(max_res, 4),
            "residual_percent": res_pct,
            "n_valid_frames": n_valid,
        }

    # Aggregate by body-region (simple heuristic on joint name)
    region_agg: Dict[str, List[float]] = {}
    for col, rec in rms_records.items():
        joint = col.rsplit("__", 1)[0]
        region = _classify_region_simple(joint)
        region_agg.setdefault(region, []).append(rec["residual_rms"])
    region_summary = {r: round(float(np.mean(v)), 4) for r, v in region_agg.items()}

    # --- SNR ---
    snr_block: dict = {}
    if snr_report is not None:
        snr_block = snr_report
    else:
        # Attempt to compute SNR on-the-fly using existing module
        try:
            from snr_analysis import compute_per_joint_snr, generate_snr_report as _gen_snr
            joints = _joint_names_from_pos(original_df)
            per_joint_snr_raw = compute_per_joint_snr(original_df, cleaned_df, joints, fs=fs, method="true_raw")
            snr_block = _gen_snr(per_joint_snr_raw)
        except Exception as exc:
            logger.warning("SNR computation skipped: %s", exc)

    # --- PSD comparison (3 representative joints) ---
    psd_comparison: Dict[str, dict] = {}
    available_joints = _joint_names_from_pos(original_df)
    for target in REPRESENTATIVE_JOINTS:
        joint = _resolve_joint(target, available_joints)
        if joint is None:
            psd_comparison[target] = {"status": "JOINT_NOT_AVAILABLE"}
            continue

        col = f"{joint}__px"
        if col not in original_df.columns or col not in cleaned_df.columns:
            psd_comparison[target] = {"status": "COLUMN_MISSING"}
            continue

        raw_sig = original_df[col].values.astype(float)
        cln_sig = cleaned_df[col].values.astype(float)

        res_raw = _segment_welch(raw_sig, fs)
        res_cln = _segment_welch(cln_sig, fs)

        if res_raw is None:
            valid_runs = _contiguous_valid_runs(raw_sig)
            longest = max((e - s for s, e in valid_runs), default=0) if valid_runs else 0
            psd_comparison[target] = {
                "status": "INSUFFICIENT_CONTIGUOUS_DATA",
                "joint_used": joint,
                "longest_valid_run_sec": round(longest / fs, 2),
                "note": f"No contiguous segment >= {PSD_MIN_SEGMENT_FRAMES/fs:.2f}s for Welch PSD",
            }
            continue

        f_raw, psd_raw = res_raw
        ratio_raw = _psd_ratio(f_raw, psd_raw, PSD_SIGNAL_BAND_HZ)

        if res_cln is not None:
            f_cln, psd_cln = res_cln
            ratio_cln = _psd_ratio(f_cln, psd_cln, PSD_SIGNAL_BAND_HZ)
        else:
            f_cln, psd_cln = None, None
            ratio_cln = None

        n_seg_raw = len([r for r in _contiguous_valid_runs(raw_sig) if (r[1] - r[0]) >= PSD_MIN_SEGMENT_FRAMES])
        n_seg_cln = len([r for r in _contiguous_valid_runs(cln_sig) if (r[1] - r[0]) >= PSD_MIN_SEGMENT_FRAMES]) if res_cln else 0
        total_sec_raw = round(sum((e - s) for s, e in _contiguous_valid_runs(raw_sig) if (e - s) >= PSD_MIN_SEGMENT_FRAMES) / fs, 2)

        psd_comparison[target] = {
            "status": "OK",
            "joint_used": joint,
            "psd_ratio_raw": ratio_raw,
            "psd_ratio_clean": ratio_cln,
            "n_segments_raw": n_seg_raw,
            "n_segments_clean": n_seg_cln,
            "total_analyzable_sec_raw": total_sec_raw,
            # Store arrays as lists for JSON (used by plots)
            "_freqs_raw": f_raw.tolist(),
            "_psd_raw": psd_raw.tolist(),
            "_freqs_clean": f_cln.tolist() if f_cln is not None else None,
            "_psd_clean": psd_cln.tolist() if psd_cln is not None else None,
        }

    return {
        "per_column_rms": rms_records,
        "region_mean_residual_rms": region_summary,
        "snr": snr_block,
        "psd_comparison": psd_comparison,
    }


def _classify_region_simple(joint: str) -> str:
    """Lightweight body-region classifier (no dependency on filtering.py)."""
    jl = joint.lower()
    if any(k in jl for k in ("hips", "spine", "pelvis", "torso")):
        return "trunk"
    if any(k in jl for k in ("head", "neck")):
        return "head"
    if any(k in jl for k in ("shoulder", "arm", "clavicle")):
        return "upper_proximal"
    if any(k in jl for k in ("forearm", "hand", "finger", "thumb", "index", "middle", "ring", "pinky", "wrist")):
        return "upper_distal"
    if any(k in jl for k in ("upleg", "thigh")):
        return "lower_proximal"
    if any(k in jl for k in ("leg", "foot", "toe", "ankle")):
        return "lower_distal"
    return "other"


# =====================================================================
# Block D — Artifact Discrimination
# =====================================================================

def _block_d_artifacts(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    fs: float,
    artifact_log: Optional[dict],
    burst_log: Optional[dict],
) -> dict:
    """Artifact discrimination: actions taken + before/after outcomes."""
    pos_cols = _pos_cols(original_df)
    common_cols = [c for c in pos_cols if c in cleaned_df.columns]

    # --- Signal-level outcomes (velocity / z-score distributions) ---
    vel_limit = 5000.0  # default; overridden from artifact_log if available
    zscore_thr = 5.0
    if artifact_log:
        s1 = artifact_log.get("stages", artifact_log.get("stage1_artifact_detector", {}))
        if isinstance(s1, dict):
            vel_limit = s1.get("velocity_limit", vel_limit)
            zscore_thr = s1.get("zscore_threshold", zscore_thr)

    raw_above_vlimit = 0
    clean_above_vlimit = 0
    raw_p99_vel = []
    clean_p99_vel = []

    for col in common_cols:
        raw = original_df[col].values.astype(float)
        cln = cleaned_df[col].values.astype(float)
        dt = 1.0 / fs

        # Raw velocity
        raw_vel = np.abs(np.diff(raw) / dt)
        finite_raw = raw_vel[np.isfinite(raw_vel)]
        if len(finite_raw) > 0:
            raw_above_vlimit += int(np.sum(finite_raw > vel_limit))
            raw_p99_vel.append(float(np.percentile(finite_raw, 99)))

        # Clean velocity
        cln_vel = np.abs(np.diff(cln) / dt)
        finite_cln = cln_vel[np.isfinite(cln_vel)]
        if len(finite_cln) > 0:
            clean_above_vlimit += int(np.sum(finite_cln > vel_limit))
            clean_p99_vel.append(float(np.percentile(finite_cln, 99)))

    outcomes = {
        "velocity_distribution": {
            "raw": {
                "frames_above_physiological_limit": raw_above_vlimit,
                "p99_velocity_mm_s": round(float(np.mean(raw_p99_vel)), 1) if raw_p99_vel else None,
            },
            "clean": {
                "frames_above_physiological_limit": clean_above_vlimit,
                "p99_velocity_mm_s": round(float(np.mean(clean_p99_vel)), 1) if clean_p99_vel else None,
            },
            "delta": {
                "spikes_eliminated": raw_above_vlimit - clean_above_vlimit,
                "interpretation": (
                    f"All supraphysiological velocity spikes eliminated"
                    if clean_above_vlimit == 0
                    else f"{raw_above_vlimit - clean_above_vlimit} of {raw_above_vlimit} spikes resolved"
                ),
            },
            "threshold_mm_s": vel_limit,
        },
    }

    # --- 3-stage action counts (from artifact_log) ---
    actions: dict = {"source": "not_provided"}
    if artifact_log:
        summary = artifact_log.get("summary", artifact_log)
        stages = artifact_log.get("stages", {})
        actions = {
            "source": "pipeline_metadata",
            "stage1_velocity_spikes": summary.get("total_velocity_spikes", None),
            "stage1_zscore_spikes": summary.get("total_zscore_spikes", None),
            "stage1_artifact_frames": summary.get("total_artifact_frames", None),
            "stage1_artifact_pct": summary.get("artifact_frames_pct", None),
            "stage2_hampel_outliers": summary.get("total_hampel_outliers", None),
            "stage2_hampel_pct": summary.get("hampel_frames_pct", None),
            "stage3_winter_cutoff_stats": summary.get("winter_cutoff_stats", None),
        }

    # --- Burst classification (Tier 1/2/3) ---
    burst: dict = {"status": "not_provided", "note": "Burst classification not yet run or not passed in"}
    if burst_log:
        bsummary = burst_log.get("summary", {})
        burst = {
            "status": "available",
            "tier1_artifact_count": bsummary.get("artifact_count", 0),
            "tier1_artifact_frames": bsummary.get("artifact_frames", 0),
            "tier2_burst_count": bsummary.get("burst_count", 0),
            "tier2_burst_frames": bsummary.get("burst_frames", 0),
            "tier3_flow_count": bsummary.get("flow_count", 0),
            "tier3_flow_frames": bsummary.get("flow_frames", 0),
            "gaga_snaps_preserved": bsummary.get("flow_count", 0),
            "artifact_rate_percent": bsummary.get("artifact_rate_percent", 0),
            "decision": burst_log.get("decision", {}),
            "events": burst_log.get("events", [])[:100],
        }

    return {
        "outcomes": outcomes,
        "actions_taken": actions,
        "burst_classification": burst,
    }


# =====================================================================
# Block E — Kinematic Integrity
# =====================================================================

def _compute_bone_cv(df: pd.DataFrame, bones: list) -> Dict[str, dict]:
    """Compute bone length CV for a dataframe (raw or clean)."""
    results: Dict[str, dict] = {}
    for parent, child in bones:
        pcols = [f"{parent}__p{a}" for a in "xyz"]
        ccols = [f"{child}__p{a}" for a in "xyz"]
        if not all(c in df.columns for c in pcols + ccols):
            continue
        P = df[pcols].values.astype(float)
        C = df[ccols].values.astype(float)
        valid = np.isfinite(P).all(axis=1) & np.isfinite(C).all(axis=1)
        if valid.sum() < 10:
            continue
        L = np.linalg.norm(C[valid] - P[valid], axis=1)
        mean_L = float(np.mean(L))
        std_L = float(np.std(L))
        cv = _safe_div(std_L, mean_L)
        if cv <= BONE_CV_GOLD:
            status = "GOLD"
        elif cv <= BONE_CV_WARN:
            status = "WARN"
        else:
            status = "FAIL"
        results[f"{parent}->{child}"] = {
            "mean_length": round(mean_L, 4),
            "std_length": round(std_L, 6),
            "cv": round(cv, 6),
            "cv_percent": round(cv * 100, 3),
            "status": status,
        }
    return results


def _quat_quality_per_joint(df: pd.DataFrame, fs: float) -> Dict[str, dict]:
    """Per-joint quaternion quality: norm deviation, hemisphere flips, angular velocity."""
    qcols = _quat_cols(df)
    joints = sorted({c.rsplit("__", 1)[0] for c in qcols})
    results: Dict[str, dict] = {}
    dt = 1.0 / fs

    for jq in joints:
        cols = [f"{jq}__q{a}" for a in "xyzw"]
        if not all(c in df.columns for c in cols):
            continue
        q = df[cols].values.astype(float)  # (N, 4) — xyzw
        valid = np.isfinite(q).all(axis=1)
        n_valid = int(valid.sum())
        if n_valid < 10:
            results[jq] = {"status": "INSUFFICIENT_DATA", "valid_frames": n_valid}
            continue

        q_v = q[valid]

        # Norm deviation
        norms = np.linalg.norm(q_v, axis=1)
        norm_dev_max = float(np.max(np.abs(norms - 1.0)))
        norm_dev_mean = float(np.mean(np.abs(norms - 1.0)))

        # Hemisphere flips: dot(q[t], q[t-1]) < 0
        dots = np.sum(q_v[1:] * q_v[:-1], axis=1)
        n_flips = int(np.sum(dots < 0))

        # Angular velocity magnitude from quaternion finite differences
        # ω ≈ 2 * ‖dq/dt‖ / ‖q‖  (small-angle approx, in rad/s → deg/s)
        dq = np.diff(q_v, axis=0) / dt
        dq_mag = np.linalg.norm(dq, axis=1)
        q_norms_mid = np.linalg.norm(q_v[:-1], axis=1)
        q_norms_mid = np.where(q_norms_mid > 1e-8, q_norms_mid, 1.0)
        omega_rad = 2.0 * dq_mag / q_norms_mid
        omega_deg = omega_rad * (180.0 / np.pi)
        fin = np.isfinite(omega_deg)

        if fin.sum() > 0:
            omega_p50 = float(np.percentile(omega_deg[fin], 50))
            omega_p95 = float(np.percentile(omega_deg[fin], 95))
            omega_p99 = float(np.percentile(omega_deg[fin], 99))
            omega_max = float(np.max(omega_deg[fin]))
            omega_mean = float(np.mean(omega_deg[fin]))
        else:
            omega_p50 = omega_p95 = omega_p99 = omega_max = omega_mean = None

        results[jq] = {
            "valid_frames": n_valid,
            "norm_dev_max": round(norm_dev_max, 8),
            "norm_dev_mean": round(norm_dev_mean, 8),
            "hemisphere_flips": n_flips,
            "angular_velocity_deg_s": {
                "mean": round(omega_mean, 2) if omega_mean is not None else None,
                "p50": round(omega_p50, 2) if omega_p50 is not None else None,
                "p95": round(omega_p95, 2) if omega_p95 is not None else None,
                "p99": round(omega_p99, 2) if omega_p99 is not None else None,
                "max": round(omega_max, 2) if omega_max is not None else None,
            },
        }
    return results


def _velocity_profile_per_joint(df: pd.DataFrame, fs: float) -> Dict[str, dict]:
    """Per-joint positional velocity distribution (mm/s)."""
    pos_cols = _pos_cols(df)
    joints = sorted({c.rsplit("__", 1)[0] for c in pos_cols})
    dt = 1.0 / fs
    results: Dict[str, dict] = {}

    for joint in joints:
        pcols = [f"{joint}__p{a}" for a in "xyz"]
        if not all(c in df.columns for c in pcols):
            continue
        pos = df[pcols].values.astype(float)
        vel = np.diff(pos, axis=0) / dt          # (N-1, 3) mm/s
        speed = np.linalg.norm(vel, axis=1)       # scalar speed
        fin = np.isfinite(speed)
        n_fin = int(fin.sum())
        if n_fin < 10:
            results[joint] = {"status": "INSUFFICIENT_DATA", "analyzable_frames": n_fin}
            continue

        sp = speed[fin]
        results[joint] = {
            "analyzable_frames": n_fin,
            "mean_mm_s": round(float(np.mean(sp)), 2),
            "p50_mm_s": round(float(np.percentile(sp, 50)), 2),
            "p95_mm_s": round(float(np.percentile(sp, 95)), 2),
            "p99_mm_s": round(float(np.percentile(sp, 99)), 2),
            "max_mm_s": round(float(np.max(sp)), 2),
        }
    return results


def _block_e_kinematic(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    skeleton_schema: dict,
    fs: float,
    bone_qc: Optional[dict],
    quat_flip_count: Optional[int],
) -> dict:
    """Kinematic integrity: bones, quaternions, velocity — all per-joint, raw vs clean."""
    bones = skeleton_schema.get("bones", [])
    all_schema_joints = set(skeleton_schema.get("joint_names", []))
    data_joints = set(_joint_names_from_pos(original_df))
    excluded_joints = sorted(all_schema_joints - data_joints)

    # ── Coverage ──────────────────────────────────────────────────────
    coverage = {
        "joints_in_schema": len(all_schema_joints),
        "joints_in_data": len(data_joints),
        "joints_excluded": excluded_joints,
        "exclusion_reason": "Excluded by pipeline config (exclude_fingers / exclude_groups)",
        "bones_in_schema": len(bones),
        "bones_computable": sum(
            1 for p, c in bones
            if p in data_joints and c in data_joints
        ),
        "bones_not_computable_reason": "Parent or child joint excluded from data",
    }

    # ── Bone CV (raw vs clean) ────────────────────────────────────────
    bone_cv_raw = _compute_bone_cv(original_df, bones)
    if bone_qc and "per_bone_cv" in bone_qc:
        bone_cv_clean_map = bone_qc["per_bone_cv"]
        bone_cv_clean = {}
        for bname, cv_val in bone_cv_clean_map.items():
            if cv_val <= BONE_CV_GOLD:
                st = "GOLD"
            elif cv_val <= BONE_CV_WARN:
                st = "WARN"
            else:
                st = "FAIL"
            bone_cv_clean[bname] = {"cv": round(cv_val, 6), "cv_percent": round(cv_val * 100, 3), "status": st}
    else:
        bone_cv_clean = _compute_bone_cv(cleaned_df, bones)

    def _status_counts(d: dict) -> dict:
        statuses = [v["status"] for v in d.values() if "status" in v]
        return {"GOLD": statuses.count("GOLD"), "WARN": statuses.count("WARN"), "FAIL": statuses.count("FAIL")}

    raw_counts = _status_counts(bone_cv_raw)
    clean_counts = _status_counts(bone_cv_clean)
    worst_bone = max(bone_cv_clean.items(), key=lambda x: x[1].get("cv", 0)) if bone_cv_clean else (None, {"cv": 0})

    # ── Quaternion quality (per-joint, raw vs clean) ──────────────────
    quat_raw = _quat_quality_per_joint(original_df, fs)
    quat_clean = _quat_quality_per_joint(cleaned_df, fs)

    total_flips_raw = sum(v.get("hemisphere_flips", 0) for v in quat_raw.values())
    total_flips_clean = sum(v.get("hemisphere_flips", 0) for v in quat_clean.values())
    max_norm_dev_raw = max((v.get("norm_dev_max", 0) for v in quat_raw.values()), default=0)
    max_norm_dev_clean = max((v.get("norm_dev_max", 0) for v in quat_clean.values()), default=0)

    # ── Velocity profile (per-joint, raw vs clean) ────────────────────
    vel_raw = _velocity_profile_per_joint(original_df, fs)
    vel_clean = _velocity_profile_per_joint(cleaned_df, fs)

    return {
        "coverage": coverage,
        "bone_cv_raw": bone_cv_raw,
        "bone_cv_clean": bone_cv_clean,
        "raw_status_counts": raw_counts,
        "clean_status_counts": clean_counts,
        "delta": {
            "gold_gained": clean_counts["GOLD"] - raw_counts["GOLD"],
            "fail_eliminated": raw_counts["FAIL"] - clean_counts["FAIL"],
            "interpretation": (
                f"Bones: {raw_counts['GOLD']} GOLD → {clean_counts['GOLD']} GOLD, "
                f"{raw_counts['FAIL']} FAIL → {clean_counts['FAIL']} FAIL. "
                f"Coverage: {coverage['bones_computable']}/{coverage['bones_in_schema']} bones "
                f"({len(excluded_joints)} joints excluded by config)."
            ),
        },
        "worst_bone_clean": {
            "name": worst_bone[0],
            "cv_percent": worst_bone[1].get("cv_percent", 0),
        },
        "quaternion_quality": {
            "per_joint_raw": quat_raw,
            "per_joint_clean": quat_clean,
            "summary": {
                "raw_total_hemisphere_flips": total_flips_raw,
                "clean_total_hemisphere_flips": total_flips_clean,
                "flips_delta": total_flips_raw - total_flips_clean,
                "raw_max_norm_deviation": round(max_norm_dev_raw, 8),
                "clean_max_norm_deviation": round(max_norm_dev_clean, 8),
                "quaternion_flips_fixed_upstream": quat_flip_count,
            },
        },
        "velocity_profile": {
            "per_joint_raw": vel_raw,
            "per_joint_clean": vel_clean,
        },
    }


# =====================================================================
# Block F — Advanced Forensics
# =====================================================================

def _compute_jerk_rms(signal_3d: np.ndarray, fs: float) -> Tuple[float, float]:
    """Return (jerk_rms, analyzable_fraction) for a (N,3) position array."""
    vel = np.diff(signal_3d, axis=0) * fs
    acc = np.diff(vel, axis=0) * fs
    jrk = np.diff(acc, axis=0) * fs
    mag = np.linalg.norm(jrk, axis=1)
    finite = np.isfinite(mag)
    frac = float(finite.sum()) / len(mag) if len(mag) > 0 else 0.0
    rms = float(np.sqrt(np.mean(mag[finite] ** 2))) if finite.sum() > 0 else np.nan
    return rms, frac


def _block_f_advanced(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    fs: float,
) -> dict:
    """Advanced forensics: jerk smoothness, acceleration spike census."""
    available = _joint_names_from_pos(original_df)

    # --- Jerk per representative joint ---
    jerk_records: Dict[str, dict] = {}
    for target in REPRESENTATIVE_JOINTS:
        joint = _resolve_joint(target, available)
        if joint is None:
            jerk_records[target] = {"status": "JOINT_NOT_AVAILABLE"}
            continue
        pcols = [f"{joint}__p{a}" for a in "xyz"]
        if not all(c in original_df.columns and c in cleaned_df.columns for c in pcols):
            jerk_records[target] = {"status": "COLUMN_MISSING"}
            continue

        raw_3d = original_df[pcols].values.astype(float)
        cln_3d = cleaned_df[pcols].values.astype(float)

        jrms_raw, frac_raw = _compute_jerk_rms(raw_3d, fs)
        jrms_cln, frac_cln = _compute_jerk_rms(cln_3d, fs)

        jerk_records[target] = {
            "joint_used": joint,
            "raw": {"jerk_rms": round(jrms_raw, 2) if np.isfinite(jrms_raw) else None, "analyzable_fraction": round(frac_raw, 4)},
            "clean": {"jerk_rms": round(jrms_cln, 2) if np.isfinite(jrms_cln) else None, "analyzable_fraction": round(frac_cln, 4)},
            "delta": {
                "reduction_percent": round(100.0 * (1.0 - _safe_div(jrms_cln, jrms_raw)), 1) if (np.isfinite(jrms_raw) and np.isfinite(jrms_cln) and jrms_raw > 0) else None,
                "interpretation": "Lower jerk RMS = smoother trajectory",
            },
        }

    # --- Acceleration spike census (all position cols) ---
    threshold = ACCEL_SPIKE_THRESHOLD_MM_S2
    pos_cols = _pos_cols(original_df)
    common_cols = [c for c in pos_cols if c in cleaned_df.columns]

    total_raw_spikes = 0
    total_clean_spikes = 0
    total_raw_analyzable = 0
    total_clean_analyzable = 0
    total_accel_frames = 0

    for col in common_cols:
        raw = original_df[col].values.astype(float)
        cln = cleaned_df[col].values.astype(float)

        raw_acc = np.diff(np.diff(raw)) * (fs ** 2)
        cln_acc = np.diff(np.diff(cln)) * (fs ** 2)

        fin_raw = np.isfinite(raw_acc)
        fin_cln = np.isfinite(cln_acc)

        total_raw_spikes += int(np.sum(np.abs(raw_acc[fin_raw]) > threshold))
        total_clean_spikes += int(np.sum(np.abs(cln_acc[fin_cln]) > threshold))
        total_raw_analyzable += int(fin_raw.sum())
        total_clean_analyzable += int(fin_cln.sum())
        total_accel_frames += len(raw_acc)

    frac_raw = round(_safe_div(total_raw_analyzable, total_accel_frames), 4)
    frac_cln = round(_safe_div(total_clean_analyzable, total_accel_frames), 4)
    reduction = round(100.0 * (1.0 - _safe_div(total_clean_spikes, total_raw_spikes)), 1) if total_raw_spikes > 0 else 100.0

    accel_block = {
        "threshold_mm_s2": threshold,
        "raw": {
            "total_spikes": total_raw_spikes,
            "analyzable_fraction": frac_raw,
        },
        "clean": {
            "total_spikes": total_clean_spikes,
            "analyzable_fraction": frac_cln,
        },
        "delta": {
            "reduction_percent": reduction,
            "interpretation": (
                f"{total_raw_spikes} impossible acceleration frames in raw → "
                f"{total_clean_spikes} in clean ({reduction}% reduction)"
            ),
        },
    }
    if frac_raw < 0.70:
        accel_block["raw"]["note"] = "Analyzable fraction <70%: raw spike count is a lower bound"

    return {
        "jerk": jerk_records,
        "acceleration_spikes": accel_block,
    }


# =====================================================================
# Executive Summary
# =====================================================================

def _executive_summary(
    block_a: dict,
    block_b: dict,
    block_c: dict,
    block_d: dict,
    block_e: dict,
    block_f: dict,
) -> dict:
    """Top-level glance table: one raw/clean/delta line per domain."""
    snr_raw_mean = block_c.get("snr", {}).get("mean_snr_all_joints", None)
    burst = block_d.get("burst_classification", {})
    gaga_preserved = burst.get("gaga_snaps_preserved", "N/A (burst log not provided)")
    tier1_removed = burst.get("tier1_artifact_count", "N/A")

    # Build verdict
    fails_clean = block_e.get("clean_status_counts", {}).get("FAIL", 0)
    clean_spikes = block_f.get("acceleration_spikes", {}).get("clean", {}).get("total_spikes", 0)
    recovery = block_a.get("delta", {}).get("recovery_rate", 0)

    issues = []
    if fails_clean > 0:
        issues.append(f"{fails_clean} bone(s) FAIL")
    if clean_spikes > 10:
        issues.append(f"{clean_spikes} residual accel spikes")
    if recovery >= 0 and recovery < 0.5:
        issues.append(f"low recovery rate ({recovery*100:.0f}%)")

    verdict = "PASS — Data integrity preserved. Noise removed. Fast movements retained." if not issues else f"REVIEW — {'; '.join(issues)}"

    return {
        "data_recovery": {
            "raw_missing_percent": block_a["raw"]["missing_percent"],
            "clean_missing_percent": block_a["clean"]["missing_percent"],
            "recovery_rate_percent": round(recovery * 100, 1) if recovery >= 0 else "N/A (raw had 0 NaN; cleaning introduced NaN via gap guard)",
        },
        "noise_reduction": {
            "mean_snr_raw_db": snr_raw_mean,
            "mean_residual_rms": round(float(np.mean(list(block_c["region_mean_residual_rms"].values()))), 4) if block_c["region_mean_residual_rms"] else None,
        },
        "signal_preservation": {
            "gaga_snaps_preserved": gaga_preserved,
            "artifacts_removed": tier1_removed,
        },
        "skeleton_integrity": {
            "bones_gold_raw": block_e.get("raw_status_counts", {}).get("GOLD", 0),
            "bones_gold_clean": block_e.get("clean_status_counts", {}).get("GOLD", 0),
            "worst_bone_cv_clean_percent": block_e.get("worst_bone_clean", {}).get("cv_percent", None),
        },
        "acceleration_quality": {
            "impossible_spikes_raw": block_f.get("acceleration_spikes", {}).get("raw", {}).get("total_spikes", 0),
            "impossible_spikes_clean": block_f.get("acceleration_spikes", {}).get("clean", {}).get("total_spikes", 0),
        },
        "gap_resolution": {
            "raw_gaps": block_b.get("raw", {}).get("total_gaps", 0),
            "clean_gaps": block_b.get("clean", {}).get("total_gaps", 0),
            "gaps_resolved": block_b.get("delta", {}).get("gaps_resolved", 0),
        },
        "verdict": verdict,
    }


# =====================================================================
# Public API
# =====================================================================

def generate_cleaning_report(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    config: dict,
    skeleton_schema: dict,
    fs: float,
    *,
    gaps_log: Optional[dict] = None,
    artifact_log: Optional[dict] = None,
    burst_log: Optional[dict] = None,
    bone_qc: Optional[dict] = None,
    snr_report: Optional[dict] = None,
    quat_flip_count: Optional[int] = None,
    output_dir: Optional[Path] = None,
    run_id: Optional[str] = None,
) -> dict:
    """
    Generate a forensic QA report comparing raw vs cleaned data.

    Parameters
    ----------
    original_df : DataFrame
        Pre-cleaning positions + quaternions (e.g. step_03 output).
    cleaned_df : DataFrame
        Post-cleaning DataFrame (e.g. step_04 output).
    config : dict
        Pipeline configuration (config_v1.yaml contents).
    skeleton_schema : dict
        Joint names, bones, parent_map from skeleton_schema.json.
    fs : float
        Sampling frequency (Hz).
    gaps_log : dict, optional
        Output from interpolation_tracking or InterpolationLogger.
    artifact_log : dict, optional
        Pipeline metadata from 3-stage cleaning.
    burst_log : dict, optional
        Output from classify_burst_events().
    bone_qc : dict, optional
        Output from bone_length_qc() — summary dict.
    snr_report : dict, optional
        Output from generate_snr_report().
    quat_flip_count : int, optional
        Number of quaternion hemisphere flips corrected.
    output_dir : Path, optional
        If set, write JSON report and PNG plots to this directory.
    run_id : str, optional
        Recording identifier for file naming.

    Returns
    -------
    dict
        Structured forensic report with blocks A–F + executive summary.
    """
    # Guard: minimum data
    if len(original_df) < fs * MIN_FRAMES_FACTOR:
        return {
            "status": "INSUFFICIENT_DATA",
            "frames": len(original_df),
            "minimum_required": int(fs * MIN_FRAMES_FACTOR),
            "note": "Cannot generate forensic report on < 2 s of data.",
        }

    logger.info("Generating forensic QA report (%d frames, %d cols) ...", len(original_df), len(original_df.columns))

    block_a = _block_a_inventory(original_df, cleaned_df, config, fs)
    block_b = _block_b_gaps(original_df, cleaned_df, fs, config)
    block_c = _block_c_noise(original_df, cleaned_df, fs, snr_report)
    block_d = _block_d_artifacts(original_df, cleaned_df, fs, artifact_log, burst_log)
    block_e = _block_e_kinematic(original_df, cleaned_df, skeleton_schema, fs, bone_qc, quat_flip_count)
    block_f = _block_f_advanced(original_df, cleaned_df, fs)

    summary = _executive_summary(block_a, block_b, block_c, block_d, block_e, block_f)

    report = {
        "report_version": "3.1",
        "generated_at": datetime.now().isoformat(),
        "run_id": run_id,
        "executive_summary": summary,
        "block_a_inventory": block_a,
        "block_b_gaps": block_b,
        "block_c_noise": block_c,
        "block_d_artifacts": block_d,
        "block_e_kinematic": block_e,
        "block_f_advanced": block_f,
        "metadata": {
            "config_hash": block_a.get("config_hash"),
            "fs_hz": fs,
            "n_joints": len(_joint_names_from_pos(original_df)),
            "n_bones": len(skeleton_schema.get("bones", [])),
        },
    }

    # --- persist ---
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = run_id or "forensic"

        # Write JSON (strip numpy-internal PSD arrays for clean JSON)
        json_path = output_dir / f"{prefix}__forensic_report.json"
        _write_json(report, json_path)
        logger.info("Forensic report JSON → %s", json_path)

        # Write CSV tables
        try:
            _write_csvs(report, output_dir, prefix)
            logger.info("Forensic CSV tables written to %s", output_dir)
        except Exception as exc:
            logger.warning("CSV export failed: %s", exc)

        # Generate plots
        try:
            from forensic_plots import generate_all_plots
            generate_all_plots(report, original_df, cleaned_df, skeleton_schema, fs, output_dir, prefix)
            logger.info("Forensic plots written to %s", output_dir)
        except Exception as exc:
            logger.warning("Plot generation failed: %s", exc)

    return report


# =====================================================================
# JSON serialiser
# =====================================================================

class _NumpyEncoder(json.JSONEncoder):
    """Handle numpy types when serialising to JSON."""

    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return super().default(obj)


def _write_json(report: dict, path: Path) -> None:
    """Write report dict to JSON, stripping internal PSD arrays to keep file size sane."""
    # Deep-copy-light: only strip keys starting with '_'
    def _strip(obj):
        if isinstance(obj, dict):
            return {k: _strip(v) for k, v in obj.items() if not k.startswith("_")}
        if isinstance(obj, list):
            return [_strip(i) for i in obj]
        return obj

    clean = _strip(report)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2, cls=_NumpyEncoder)


# =====================================================================
# CSV export
# =====================================================================

def _write_csvs(report: dict, output_dir: Path, prefix: str) -> List[Path]:
    """
    Flatten the forensic report into supervisor-friendly CSV tables.

    Produces:
        1. executive_summary.csv     — one-row glance table
        2. inventory.csv             — Block A
        3. gaps.csv                  — Block B aggregate
        4. noise_rms.csv             — Block C per-column RMS triplets
        5. noise_psd.csv             — Block C PSD comparison
        6. artifacts.csv             — Block D velocity outcomes + burst tiers
        7. bone_integrity.csv        — Block E raw vs clean CV per bone
        8. advanced_jerk.csv         — Block F jerk per joint
        9. advanced_accel.csv        — Block F accel spike summary
    """
    created: List[Path] = []

    def _save_csv(df: pd.DataFrame, name: str) -> Optional[Path]:
        p = output_dir / f"{prefix}__forensic_{name}.csv"
        try:
            df.to_csv(str(p), index=False, encoding="utf-8-sig")
            created.append(p)
            return p
        except PermissionError:
            logger.warning("CSV write skipped (file open?): %s", p.name)
            return None

    # --- 1. Executive Summary ---
    es = report.get("executive_summary", {})
    rows_es = []
    for section, vals in es.items():
        if isinstance(vals, dict):
            for k, v in vals.items():
                rows_es.append({"section": section, "metric": k, "value": v})
        else:
            rows_es.append({"section": "overall", "metric": section, "value": vals})
    if rows_es:
        _save_csv(pd.DataFrame(rows_es), "executive_summary")

    # --- 2. Inventory ---
    a = report.get("block_a_inventory", {})
    inv_rows = [
        {"metric": "total_cells", "value": a.get("total_cells")},
        {"metric": "total_frames", "value": a.get("total_frames")},
        {"metric": "total_analysis_columns", "value": a.get("total_analysis_columns")},
        {"metric": "raw_total_nans", "value": a.get("raw", {}).get("total_nans")},
        {"metric": "raw_missing_percent", "value": a.get("raw", {}).get("missing_percent")},
        {"metric": "clean_total_nans", "value": a.get("clean", {}).get("total_nans")},
        {"metric": "clean_missing_percent", "value": a.get("clean", {}).get("missing_percent")},
        {"metric": "nans_recovered", "value": a.get("delta", {}).get("nans_recovered")},
        {"metric": "recovery_rate", "value": a.get("delta", {}).get("recovery_rate")},
        {"metric": "interpretation", "value": a.get("delta", {}).get("interpretation")},
        {"metric": "config_hash", "value": a.get("config_hash")},
    ]
    # Add all logged thresholds
    for tk, tv in a.get("thresholds_logged", {}).items():
        inv_rows.append({"metric": f"threshold_{tk}", "value": tv})
    _save_csv(pd.DataFrame(inv_rows), "inventory")

    # --- 3. Gaps ---
    b = report.get("block_b_gaps", {})
    gap_rows = [
        {"metric": "gap_threshold_sec", "value": b.get("gap_threshold_sec")},
        {"metric": "raw_total_gaps", "value": b.get("raw", {}).get("total_gaps")},
        {"metric": "raw_small_gaps", "value": b.get("raw", {}).get("small_gaps")},
        {"metric": "raw_large_gaps", "value": b.get("raw", {}).get("large_gaps")},
        {"metric": "raw_boundary_gaps", "value": b.get("raw", {}).get("boundary_gaps")},
        {"metric": "raw_total_gap_duration_sec", "value": b.get("raw", {}).get("total_gap_duration_sec")},
        {"metric": "raw_longest_gap_sec", "value": b.get("raw", {}).get("longest_gap_sec")},
        {"metric": "clean_total_gaps", "value": b.get("clean", {}).get("total_gaps")},
        {"metric": "clean_total_gap_duration_sec", "value": b.get("clean", {}).get("total_gap_duration_sec")},
        {"metric": "clean_longest_gap_sec", "value": b.get("clean", {}).get("longest_gap_sec")},
        {"metric": "gaps_resolved", "value": b.get("delta", {}).get("gaps_resolved")},
        {"metric": "duration_recovered_sec", "value": b.get("delta", {}).get("duration_recovered_sec")},
        {"metric": "interpretation", "value": b.get("delta", {}).get("interpretation")},
    ]
    _save_csv(pd.DataFrame(gap_rows), "gaps")

    # --- 4. Noise RMS (per column) ---
    rms = report.get("block_c_noise", {}).get("per_column_rms", {})
    if rms:
        rms_rows = []
        for col, rec in rms.items():
            joint = col.rsplit("__", 1)[0]
            axis = col.rsplit("__", 1)[1] if "__" in col else ""
            row = {"column": col, "joint": joint, "axis": axis}
            row.update(rec)
            rms_rows.append(row)
        _save_csv(pd.DataFrame(rms_rows), "noise_rms")

    # --- 5. Noise PSD ---
    psd = report.get("block_c_noise", {}).get("psd_comparison", {})
    if psd:
        psd_rows = []
        for target, d in psd.items():
            row = {"target_joint": target}
            row.update({k: v for k, v in d.items() if not k.startswith("_")})
            psd_rows.append(row)
        _save_csv(pd.DataFrame(psd_rows), "noise_psd")

    # --- 6. Artifacts ---
    dd = report.get("block_d_artifacts", {})
    art_rows = []
    vel = dd.get("outcomes", {}).get("velocity_distribution", {})
    art_rows.append({"metric": "velocity_threshold_mm_s", "raw": vel.get("threshold_mm_s"), "clean": None, "delta": None})
    art_rows.append({"metric": "frames_above_physiological_limit",
                      "raw": vel.get("raw", {}).get("frames_above_physiological_limit"),
                      "clean": vel.get("clean", {}).get("frames_above_physiological_limit"),
                      "delta": vel.get("delta", {}).get("spikes_eliminated")})
    art_rows.append({"metric": "p99_velocity_mm_s",
                      "raw": vel.get("raw", {}).get("p99_velocity_mm_s"),
                      "clean": vel.get("clean", {}).get("p99_velocity_mm_s"),
                      "delta": None})

    actions = dd.get("actions_taken", {})
    for k, v in actions.items():
        if k != "source" and v is not None:
            art_rows.append({"metric": k, "raw": None, "clean": None, "delta": v})

    burst = dd.get("burst_classification", {})
    if burst.get("status") == "available":
        for k in ("tier1_artifact_count", "tier1_artifact_frames",
                   "tier2_burst_count", "tier2_burst_frames",
                   "tier3_flow_count", "tier3_flow_frames",
                   "gaga_snaps_preserved", "artifact_rate_percent"):
            art_rows.append({"metric": k, "raw": None, "clean": None, "delta": burst.get(k)})

    _save_csv(pd.DataFrame(art_rows), "artifacts")

    # --- 7. Bone Integrity (raw vs clean per bone) ---
    e = report.get("block_e_kinematic", {})
    bone_raw = e.get("bone_cv_raw", {})
    bone_clean = e.get("bone_cv_clean", {})
    all_bones = sorted(set(bone_raw.keys()) | set(bone_clean.keys()))
    if all_bones:
        bone_rows = []
        for bname in all_bones:
            r = bone_raw.get(bname, {})
            c = bone_clean.get(bname, {})
            bone_rows.append({
                "bone": bname,
                "raw_cv_percent": r.get("cv_percent"),
                "raw_status": r.get("status"),
                "raw_mean_length": r.get("mean_length"),
                "clean_cv_percent": c.get("cv_percent"),
                "clean_status": c.get("status"),
            })
        _save_csv(pd.DataFrame(bone_rows), "bone_integrity")

    # --- 7b. Coverage ---
    cov = e.get("coverage", {})
    if cov:
        cov_rows = [{"metric": k, "value": v} for k, v in cov.items() if k != "joints_excluded"]
        for jx in cov.get("joints_excluded", []):
            cov_rows.append({"metric": "excluded_joint", "value": jx})
        _save_csv(pd.DataFrame(cov_rows), "coverage")

    # --- 7c. Quaternion Quality (per joint, raw vs clean) ---
    quat_q = e.get("quaternion_quality", {})
    quat_raw_pj = quat_q.get("per_joint_raw", {})
    quat_cln_pj = quat_q.get("per_joint_clean", {})
    all_q_joints = sorted(set(quat_raw_pj.keys()) | set(quat_cln_pj.keys()))
    if all_q_joints:
        q_rows = []
        for jq in all_q_joints:
            rq = quat_raw_pj.get(jq, {})
            cq = quat_cln_pj.get(jq, {})
            raw_av = rq.get("angular_velocity_deg_s", {})
            cln_av = cq.get("angular_velocity_deg_s", {})
            q_rows.append({
                "joint": jq,
                "raw_valid_frames": rq.get("valid_frames"),
                "raw_norm_dev_max": rq.get("norm_dev_max"),
                "raw_hemisphere_flips": rq.get("hemisphere_flips"),
                "raw_omega_mean_deg_s": raw_av.get("mean"),
                "raw_omega_p95_deg_s": raw_av.get("p95"),
                "raw_omega_p99_deg_s": raw_av.get("p99"),
                "raw_omega_max_deg_s": raw_av.get("max"),
                "clean_valid_frames": cq.get("valid_frames"),
                "clean_norm_dev_max": cq.get("norm_dev_max"),
                "clean_hemisphere_flips": cq.get("hemisphere_flips"),
                "clean_omega_mean_deg_s": cln_av.get("mean"),
                "clean_omega_p95_deg_s": cln_av.get("p95"),
                "clean_omega_p99_deg_s": cln_av.get("p99"),
                "clean_omega_max_deg_s": cln_av.get("max"),
            })
        _save_csv(pd.DataFrame(q_rows), "quaternion_quality")

    # --- 7d. Velocity Profile (per joint, raw vs clean) ---
    vel_raw_pj = e.get("velocity_profile", {}).get("per_joint_raw", {})
    vel_cln_pj = e.get("velocity_profile", {}).get("per_joint_clean", {})
    all_v_joints = sorted(set(vel_raw_pj.keys()) | set(vel_cln_pj.keys()))
    if all_v_joints:
        v_rows = []
        for jv in all_v_joints:
            rv = vel_raw_pj.get(jv, {})
            cv = vel_cln_pj.get(jv, {})
            v_rows.append({
                "joint": jv,
                "raw_mean_mm_s": rv.get("mean_mm_s"),
                "raw_p50_mm_s": rv.get("p50_mm_s"),
                "raw_p95_mm_s": rv.get("p95_mm_s"),
                "raw_p99_mm_s": rv.get("p99_mm_s"),
                "raw_max_mm_s": rv.get("max_mm_s"),
                "clean_mean_mm_s": cv.get("mean_mm_s"),
                "clean_p50_mm_s": cv.get("p50_mm_s"),
                "clean_p95_mm_s": cv.get("p95_mm_s"),
                "clean_p99_mm_s": cv.get("p99_mm_s"),
                "clean_max_mm_s": cv.get("max_mm_s"),
            })
        _save_csv(pd.DataFrame(v_rows), "velocity_profile")

    # --- 8. Advanced Jerk ---
    jerk = report.get("block_f_advanced", {}).get("jerk", {})
    if jerk:
        jerk_rows = []
        for target, jr in jerk.items():
            if "status" in jr:
                jerk_rows.append({"target_joint": target, "joint_used": None, "status": jr["status"],
                                   "raw_jerk_rms": None, "raw_analyzable_fraction": None,
                                   "clean_jerk_rms": None, "clean_analyzable_fraction": None,
                                   "reduction_percent": None})
            else:
                jerk_rows.append({
                    "target_joint": target,
                    "joint_used": jr.get("joint_used"),
                    "status": "OK",
                    "raw_jerk_rms": jr.get("raw", {}).get("jerk_rms"),
                    "raw_analyzable_fraction": jr.get("raw", {}).get("analyzable_fraction"),
                    "clean_jerk_rms": jr.get("clean", {}).get("jerk_rms"),
                    "clean_analyzable_fraction": jr.get("clean", {}).get("analyzable_fraction"),
                    "reduction_percent": jr.get("delta", {}).get("reduction_percent"),
                })
        _save_csv(pd.DataFrame(jerk_rows), "advanced_jerk")

    # --- 9. Advanced Accel Spikes ---
    acc = report.get("block_f_advanced", {}).get("acceleration_spikes", {})
    if acc:
        acc_rows = [{
            "metric": "acceleration_spikes",
            "threshold_mm_s2": acc.get("threshold_mm_s2"),
            "raw_total_spikes": acc.get("raw", {}).get("total_spikes"),
            "raw_analyzable_fraction": acc.get("raw", {}).get("analyzable_fraction"),
            "clean_total_spikes": acc.get("clean", {}).get("total_spikes"),
            "clean_analyzable_fraction": acc.get("clean", {}).get("analyzable_fraction"),
            "reduction_percent": acc.get("delta", {}).get("reduction_percent"),
            "interpretation": acc.get("delta", {}).get("interpretation"),
        }]
        _save_csv(pd.DataFrame(acc_rows), "advanced_accel")

    logger.info("Forensic CSV tables: %d files written", len(created))
    return created
