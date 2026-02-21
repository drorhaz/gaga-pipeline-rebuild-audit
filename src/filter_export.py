"""
Filter summary and residual export for notebook 04 (filtering step).

Used by: notebooks/04_filtering.ipynb
Exports: __filtering_summary.json (Winter/filter params, SNR, stage stats) and optional Winter residual data.
"""

import json
import os
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def _classify_winter_method(raw_method: str) -> str:
    """Map verbose per-column Winter method strings to canonical categories."""
    m = raw_method.lower()
    if m.startswith("smart_bias"):
        return "smart_bias"
    if "strict_knee" in m:
        return "strict_knee"
    if "relaxed_knee" in m:
        return "relaxed_knee"
    if "diminishing" in m:
        return "diminishing_returns"
    if "no_knee_point" in m or "standard_protocol" in m:
        return "no_knee_standard_protocol"
    if "fmax_fallback" in m:
        return "fmax_fallback"
    if "flat_signal" in m:
        return "flat_signal_failure"
    if "too_short" in m:
        return "signal_too_short"
    return raw_method


def _snr_analysis_dict(snr_report: Dict[str, Any]) -> Dict[str, Any]:
    """Build the SNR block for filtering summary JSON (shared by 3-stage and per-region/single paths)."""
    if snr_report is None:
        return {}
    return {
        "method": "true_raw",
        "description": "Raw data frequency analysis (signal: 0.5-10Hz, noise: 15-50Hz)",
        "mean_snr_db": round(snr_report.get("mean_snr_all_joints", 0), 1),
        "min_snr_db": round(snr_report.get("min_snr_all_joints", 0), 1),
        "max_snr_db": round(snr_report.get("max_snr_all_joints", 0), 1),
        "overall_status": snr_report.get("overall_status", "UNKNOWN"),
        "total_joints": snr_report.get("total_joints", 0),
        "joints_excellent": snr_report.get("joints_excellent", 0),
        "joints_good": snr_report.get("joints_good", 0),
        "joints_acceptable": snr_report.get("joints_acceptable", 0),
        "joints_poor": snr_report.get("joints_poor", 0),
        "joints_reject": snr_report.get("joints_reject", 0),
        "failed_joints": snr_report.get("failed_joints", []),
    }


def export_filter_summary(
    df_orig: pd.DataFrame,
    winter_meta: Dict[str, Any],
    run_id: str,
    save_dir: str,
    fs: float,
    mass: Optional[float],
    height: Optional[float],
    *,
    snr_report: Optional[Dict[str, Any]] = None,
    filter_method: Optional[str] = None,
    filter_config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Write filtering summary JSON for reproducibility and Master Audit.

    Supports: 3_stage_pipeline, per_region / per_region_fixed, single_global.
    Optionally includes true-raw SNR summary (capture quality before filtering).

    Returns:
        Path to the written file (e.g. save_dir/run_id__filtering_summary.json).
    """
    total_frames = len(df_orig)
    missing_pct = float(df_orig.isna().mean().mean() * 100)
    filter_config = filter_config or {}
    filtering_mode = winter_meta.get("filtering_mode", "single_global")

    if filtering_mode == "3_stage_pipeline":
        return _export_3stage(
            winter_meta, run_id, save_dir, total_frames, missing_pct, fs, mass, height,
            filter_method, snr_report,
        )

    # Per-region or single-global path
    winter_failed = winter_meta.get("winter_analysis_failed", False)
    failure_reason = winter_meta.get("winter_failure_reason", None)
    if not winter_failed and "cutoff_hz" in winter_meta:
        if winter_meta["cutoff_hz"] >= winter_meta.get("fmax", 12) - 1:
            winter_failed = True
            failure_reason = f"Cutoff at fmax ({winter_meta['cutoff_hz']:.1f}Hz)"

    cutoff_method = winter_meta.get("cutoff_method", "data_driven")
    if cutoff_method == "fixed_literature_based":
        decision_reason = winter_meta.get(
            "decision_reason", "Fixed per-region cutoffs (Winter 2009, Robertson 2014)"
        )
        winter_failed = False
        failure_reason = None
    elif winter_failed:
        cutoff_display = winter_meta.get("cutoff_hz", "N/A")
        decision_reason = (
            f"Filter: {failure_reason}; using {cutoff_display}Hz default"
            if isinstance(cutoff_display, (int, float)) else f"Filter: {failure_reason}"
        )
        if not failure_reason:
            decision_reason = (
                f"Filter: No optimal knee-point found; using {cutoff_display}Hz default"
                if isinstance(cutoff_display, (int, float)) else "Filter: No optimal knee-point found"
            )
    else:
        cutoff_display = winter_meta.get("cutoff_hz", "per-region cutoffs")
        decision_reason = (
            f"Filter: Winter knee-point detected at {cutoff_display:.1f}Hz"
            if isinstance(cutoff_display, (int, float)) else "Filter: Per-region Winter analysis successful"
        )

    if filtering_mode in ["per_region", "per_region_fixed"]:
        method_key = filter_method or "per_region"
        filter_method_desc = "Fixed Per-Region Cutoffs (Literature-Based)"
        filter_type = "Butterworth Low-pass (Zero-phase) - Winter (2009), Robertson (2014)"
        parameters_applied = {"fmax": int(winter_meta.get("fmax", 12)), "allow_fmax": True}
    else:
        method_key = filter_method or "single_global"
        filter_method_desc = "Single Global Cutoff"
        filter_type = "Butterworth Low-pass (Zero-phase)"
        parameters_applied = {
            "cutoff_hz": float(winter_meta.get("cutoff_hz", filter_config.get("cutoff_hz", 8.0)))
        }

    summary = {
        "run_id": run_id,
        "identity": {
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "pipeline_version": "v2.9_fixed_per_region_cutoffs",
        },
        "subject_metadata": {
            "mass_kg": mass,
            "height_cm": height,
            "units_status": "internal_unscaled",
        },
        "raw_quality": {
            "total_frames": int(total_frames),
            "missing_data_percent": round(missing_pct, 3),
            "sampling_rate_actual": float(fs),
        },
        "filter_params": {
            "selected_method": method_key,
            "parameters_applied": parameters_applied,
            "filter_type": filter_type,
            "filter_method": filter_method_desc,
            "filtering_mode": filtering_mode,
            "filter_order": 2,
            "quaternion_filtering": False,
            "expected_dance_range": "8-12 Hz (Gaga athletic movement)",
        },
    }

    if filtering_mode in ["per_region", "per_region_fixed"]:
        summary["filter_params"]["region_cutoffs"] = {
            k: float(v) for k, v in winter_meta.get("region_cutoffs", {}).items()
        }
        summary["filter_params"]["cutoff_range_hz"] = [
            float(winter_meta["cutoff_range"][0]),
            float(winter_meta["cutoff_range"][1]),
        ]
        summary["filter_params"]["n_regions"] = int(winter_meta.get("n_regions", 0))
        summary["filter_params"]["fmax"] = int(winter_meta.get("fmax", 12))
        marker_regions = winter_meta.get("marker_regions", {})
        region_counts: Dict[str, int] = {}
        for _m, region in marker_regions.items():
            region_counts[region] = region_counts.get(region, 0) + 1
        summary["filter_params"]["region_marker_counts"] = region_counts
        summary["filter_params"]["winter_analysis_failed"] = bool(winter_failed)
        summary["filter_params"]["winter_failure_reason"] = failure_reason
        summary["filter_params"]["decision_reason"] = decision_reason
        summary["filter_params"]["residual_rms_mm"] = float(winter_meta.get("residual_rms_mm", 0))
        if filtering_mode == "per_region_fixed":
            summary["filter_params"]["cutoff_method"] = "fixed_literature_based"
            summary["filter_params"]["literature_reference"] = winter_meta.get(
                "literature_reference", "Winter (2009), Robertson (2014)"
            )
            summary["filter_params"]["winter_validation_note"] = winter_meta.get(
                "winter_validation_note", "N/A"
            )
        region_analysis = winter_meta.get("region_analysis_details", {})
        if region_analysis:
            summary["filter_params"]["region_analysis_details"] = {}
            for region, details in region_analysis.items():
                region_detail = {
                    "cutoff_hz": float(details.get("cutoff_hz", 0)),
                    "rep_col": str(details.get("rep_col", "N/A")),
                }
                if filtering_mode == "per_region_fixed":
                    region_detail["cutoff_method"] = details.get(
                        "cutoff_method", "fixed_winter_validated"
                    )
                    region_detail["winter_strict_knee_hz"] = (
                        float(details["winter_strict_knee_hz"])
                        if details.get("winter_strict_knee_hz") is not None else None
                    )
                    region_detail["winter_diminishing_hz"] = (
                        float(details["winter_diminishing_hz"])
                        if details.get("winter_diminishing_hz") is not None else None
                    )
                    region_detail["winter_suggested_hz"] = (
                        float(details["winter_suggested_hz"])
                        if details.get("winter_suggested_hz") is not None else None
                    )
                    region_detail["validation_status"] = details.get("validation_status", "N/A")
                    region_detail["rationale"] = details.get("rationale", "N/A")
                else:
                    region_detail["raw_cutoff_hz"] = (
                        float(details["raw_cutoff_hz"])
                        if details.get("raw_cutoff_hz") is not None else None
                    )
                    region_detail["knee_point_found"] = bool(details.get("knee_point_found", False))
                    region_detail["failure_reason"] = details.get("failure_reason")
                    region_detail["method_used"] = details.get("method_used")
                region_detail["rms_range_ratio"] = (
                    float(details["rms_range_ratio"])
                    if details.get("rms_range_ratio") is not None else None
                )
                region_detail["curve_is_flat"] = (
                    bool(details["curve_is_flat"])
                    if details.get("curve_is_flat") is not None else None
                )
                summary["filter_params"]["region_analysis_details"][region] = region_detail
    else:
        summary["filter_params"]["filter_cutoff_hz"] = float(winter_meta.get("cutoff_hz", 0))
        summary["filter_params"]["filter_range_hz"] = [
            int(winter_meta.get("fmin", 1)),
            int(winter_meta.get("fmax", 12)),
        ]
        summary["filter_params"]["representative_column"] = str(
            winter_meta.get("rep_col", "N/A")
        )
        summary["filter_params"]["winter_analysis_failed"] = bool(winter_failed)
        summary["filter_params"]["winter_failure_reason"] = failure_reason
        summary["filter_params"]["decision_reason"] = decision_reason
        if "biomechanical_guardrails" in winter_meta:
            g = winter_meta["biomechanical_guardrails"]
            summary["filter_params"]["biomechanical_guardrails"] = {
                "enabled": bool(g["enabled"]),
                "strategy": str(g["strategy"]),
                "min_cutoff_trunk_hz": float(g["min_cutoff_trunk"]) if g.get("min_cutoff_trunk") is not None else None,
                "min_cutoff_distal_hz": float(g["min_cutoff_distal"]) if g.get("min_cutoff_distal") is not None else None,
                "use_trunk_global": bool(g["use_trunk_global"]),
            }

    snr_block = _snr_analysis_dict(snr_report)
    if snr_block:
        summary["snr_analysis"] = snr_block

    out_path = os.path.join(save_dir, f"{run_id}__filtering_summary.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=4)

    _print_summary_non_3stage(
        out_path, missing_pct, mass, height, winter_meta, filtering_mode,
        winter_failed, decision_reason,
    )
    return out_path


def _export_3stage(
    winter_meta: Dict[str, Any],
    run_id: str,
    save_dir: str,
    total_frames: int,
    missing_pct: float,
    fs: float,
    mass: Optional[float],
    height: Optional[float],
    filter_method: Optional[str],
    snr_report: Optional[Dict[str, Any]],
) -> str:
    """Build and write 3-stage pipeline summary JSON."""
    pipeline_meta = winter_meta.get("pipeline_metadata", {})
    summary_stats = pipeline_meta.get("summary", {})
    stages = pipeline_meta.get("stages", {})
    per_joint = pipeline_meta.get("per_joint_results", {})

    region_cutoffs: Dict[str, list] = {}
    region_counts: Dict[str, int] = {}
    method_counts: Dict[str, int] = {}
    for col, meta in per_joint.items():
        region = meta.get("marker_region", "unknown")
        cutoff = meta.get("stage3_winter_cutoff")
        if cutoff is not None:
            if region not in region_cutoffs:
                region_cutoffs[region] = []
                region_counts[region] = 0
            region_cutoffs[region].append(cutoff)
            region_counts[region] += 1
        method = meta.get("stage3_winter_method", "unknown")
        method_key = _classify_winter_method(method)
        method_counts[method_key] = method_counts.get(method_key, 0) + 1
    region_avg_cutoffs = {r: round(float(np.mean(c)), 1) for r, c in region_cutoffs.items()}

    # Per-joint cutoffs for adaptive SavGol windowing in Step 06
    per_joint_cutoffs: Dict[str, float] = {}
    for col, meta in per_joint.items():
        cutoff = meta.get("stage3_winter_cutoff")
        if cutoff is not None:
            per_joint_cutoffs[col] = round(float(cutoff), 2)

    n_frames = summary_stats.get("n_frames_total", 0)
    n_cols = summary_stats.get("total_columns_processed", 1)
    total_position_samples = n_frames * n_cols if n_cols else 0

    summary = {
        "run_id": run_id,
        "identity": {
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "pipeline_version": "v3.1_3stage_dynamic_rms_chunked",
        },
        "subject_metadata": {
            "mass_kg": mass,
            "height_cm": height,
            "units_status": "internal_unscaled",
        },
        "raw_quality": {
            "total_frames": int(total_frames),
            "missing_data_percent": round(missing_pct, 3),
            "sampling_rate_actual": float(fs),
        },
        "filter_params": {
            "selected_method": filter_method or "3_stage",
            "parameters_applied": {
                "velocity_limit": stages.get("stage1_artifact_detector", {}).get("velocity_limit"),
                "zscore_threshold": stages.get("stage1_artifact_detector", {}).get("zscore_threshold"),
                "stage1_interpolation_method": summary_stats.get("stage1_interpolation_method", "pchip"),
                "hampel_window": stages.get("stage2_hampel", {}).get("window_size"),
                "hampel_n_sigma": stages.get("stage2_hampel", {}).get("n_sigma"),
                "winter_fmin": stages.get("stage3_adaptive_winter", {}).get("fmin"),
                "winter_fmax": stages.get("stage3_adaptive_winter", {}).get("fmax"),
                "per_joint_winter": stages.get("stage3_adaptive_winter", {}).get("per_joint"),
            },
            "filter_type": "3-Stage Signal Cleaning Pipeline",
            "filter_method": "Artifact Detection + Hampel + Adaptive Winter (Dynamic RMS, Chunked filtfilt)",
            "filtering_mode": "3_stage_pipeline",
            "filter_order": 2,
            "quaternion_filtering": False,
            "expected_dance_range": "1-20 Hz (Adaptive per-joint)",
            "stage1_artifact_detector": stages.get("stage1_artifact_detector", {}),
            "stage2_hampel": stages.get("stage2_hampel", {}),
            "stage3_adaptive_winter": stages.get("stage3_adaptive_winter", {}),
            "stage1_interpolation_method": summary_stats.get("stage1_interpolation_method", "pchip"),
            "n_frames_total": n_frames,
            "total_position_samples": total_position_samples,
            "total_columns_processed": summary_stats.get("total_columns_processed", 0),
            "total_artifact_frames": summary_stats.get("total_artifact_frames", 0),
            "total_artifact_segments": summary_stats.get("total_artifact_segments", 0),
            "total_velocity_spikes": summary_stats.get("total_velocity_spikes", 0),
            "total_zscore_spikes": summary_stats.get("total_zscore_spikes", 0),
            "artifact_frames_pct": round(summary_stats.get("artifact_frames_pct", 0), 4),
            "total_hampel_outliers": summary_stats.get("total_hampel_outliers", 0),
            "hampel_frames_pct": round(summary_stats.get("hampel_frames_pct", 0), 4),
            "winter_cutoff_stats": summary_stats.get("winter_cutoff_stats", {}),
            "region_cutoffs": region_avg_cutoffs,
            "per_joint_cutoffs": per_joint_cutoffs,
            "region_marker_counts": region_counts,
            "cutoff_range_hz": list(winter_meta.get("cutoff_range", [1.0, 20.0])),
            "method_distribution": method_counts,
            # Gap Guard (Stage 1 interpolation cap)
            "stage1_max_interp_limit_frames": summary_stats.get("stage1_max_interp_limit_frames", 0),
            "stage1_gap_guard": summary_stats.get("stage1_gap_guard", {}),
            # PSD Verification (No-Oversmoothing Guarantee)
            "psd_audit": winter_meta.get("psd_audit", {}),
            # Dynamic RMS Windowing aggregate
            "dynamic_rms_windowing": summary_stats.get("dynamic_rms_windowing", {}),
            # Chunking Guard aggregate
            "chunking_guard": summary_stats.get("chunking_guard", {}),
        },
    }
    snr_block = _snr_analysis_dict(snr_report)
    if snr_block:
        summary["snr_analysis"] = snr_block

    out_path = os.path.join(save_dir, f"{run_id}__filtering_summary.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=4)

    print(f"\n{'='*20} FILTER SUMMARY EXPORTED {'='*20}")
    print(f"✅ Path: {out_path}")
    print(f"📊 Quality: {missing_pct:.2f}% missing data")
    print(f"👤 Subject: {mass}kg, {height}cm")
    print("🔬 Filtering Mode: 3-Stage Signal Cleaning Pipeline")
    print(f"   Stage 1: Artifact Detector (velocity + z-score), interpolation: {summary_stats.get('stage1_interpolation_method', 'pchip')}")
    print(f"      - Frames in data: {n_frames} | Position samples: {total_position_samples}")
    print(f"      - Artifacts: {summary_stats.get('total_artifact_frames', 0)} frames ({summary_stats.get('artifact_frames_pct', 0):.2f}%) | Segments: {summary_stats.get('total_artifact_segments', 0)}")
    print(f"   Stage 2: Hampel Filter (window={stages.get('stage2_hampel', {}).get('window_size', 5)})")
    print(f"      - Outliers replaced: {summary_stats.get('total_hampel_outliers', 0)} frames ({summary_stats.get('hampel_frames_pct', 0):.2f}%)")
    print("   Stage 3: Adaptive Winter (per-joint)")
    cutoff_stats = summary_stats.get("winter_cutoff_stats", {})
    if cutoff_stats:
        print(f"      - Cutoff range: {cutoff_stats.get('min', 0):.1f} - {cutoff_stats.get('max', 0):.1f} Hz")
        print(f"      - Mean cutoff: {cutoff_stats.get('mean', 0):.1f} Hz")
    print("   Region Average Cutoffs:")
    for region in sorted(region_avg_cutoffs):
        avg_cutoff = region_avg_cutoffs[region]
        print(f"      - {region}: {avg_cutoff:.1f} Hz ({region_counts.get(region, 0)} markers)")
    gap_guard = summary_stats.get("stage1_gap_guard", {})
    if gap_guard:
        interp_limit = summary_stats.get("stage1_max_interp_limit_frames", 0)
        print(f"   Gap Guard: interp_limit={interp_limit} frames, "
              f"max_gap={gap_guard.get('max_gap_across_all_cols', 0)} frames, "
              f"unreliable_gaps={gap_guard.get('total_unreliable_gaps', 0)}")
    drms = summary_stats.get("dynamic_rms_windowing", {})
    if drms.get("enabled"):
        n_fb = drms.get("joints_fallback_to_global_rms", 0)
        print(f"   Dynamic RMS Windowing: ON (quantile={drms.get('energy_quantile', 0.80)}), "
              f"joints={drms.get('joints_with_dynamic_rms', 0)}, "
              f"fallback_to_global={n_fb}")
        if n_fb:
            print(f"      Fallback joints: {drms.get('fallback_joints', [])}")
    cg = summary_stats.get("chunking_guard", {})
    if cg:
        print(f"   Chunking Guard: {cg.get('total_chunks_all_joints', 0)} chunks, "
              f"{cg.get('total_chunks_too_short', 0)} too-short, "
              f"{cg.get('total_unfiltered_frames', 0)} unfiltered frames")
        short_joints = cg.get("joints_with_short_chunks", [])
        if short_joints:
            print(f"      Joints with unfiltered segments: {short_joints}")
    print(f"{'='*60}\n")
    return out_path


def _print_summary_non_3stage(
    out_path: str,
    missing_pct: float,
    mass: Optional[float],
    height: Optional[float],
    winter_meta: Dict[str, Any],
    filtering_mode: str,
    winter_failed: bool,
    decision_reason: str,
) -> None:
    """Print filter summary to console for per_region / single_global."""
    print(f"\n{'='*20} FILTER SUMMARY EXPORTED {'='*20}")
    print(f"✅ Path: {out_path}")
    print(f"📊 Quality: {missing_pct:.2f}% missing data")
    print(f"👤 Subject: {mass}kg, {height}cm")

    if filtering_mode == "per_region_fixed":
        print("🔬 Filtering Mode: FIXED Per-Region Cutoffs (Literature-Based)")
        print("📚 Reference: Winter (2009), Robertson (2014)")
        cutoff_range = winter_meta.get("cutoff_range", (0, 0))
        print(f"📈 Cutoff Range: {cutoff_range[0]:.1f} - {cutoff_range[1]:.1f} Hz")
        print("🎯 Fixed Region Cutoffs:")
        region_analysis = winter_meta.get("region_analysis_details", {})
        marker_regions = winter_meta.get("marker_regions", {})
        for region, cutoff in winter_meta.get("region_cutoffs", {}).items():
            n_markers = sum(1 for _m, r in marker_regions.items() if r == region)
            details = region_analysis.get(region, {})
            strict_knee = details.get("winter_strict_knee_hz", details.get("winter_suggested_hz", "N/A"))
            diminishing = details.get("winter_diminishing_hz", "N/A")
            validation = details.get("validation_status", "N/A")
            if isinstance(strict_knee, (int, float)) and isinstance(diminishing, (int, float)):
                print(f"     {region:20s}: {cutoff:4.0f} Hz | RMS knee: {strict_knee:.0f}Hz, diminishing: {diminishing:.0f}Hz | {validation} - {n_markers} markers")
            elif isinstance(strict_knee, (int, float)):
                print(f"     {region:20s}: {cutoff:4.0f} Hz | RMS knee: {strict_knee:.0f}Hz | {validation} - {n_markers} markers")
            else:
                print(f"     {region:20s}: {cutoff:4.0f} Hz - {n_markers} markers")
        validation_note = winter_meta.get("winter_validation_note", "")
        if validation_note:
            print(f"✅ Validation: {validation_note[:100]}...")
    elif filtering_mode == "per_region":
        print("🔬 Filtering Mode: Per-Region (Data-Driven)")
        cutoff_range = winter_meta.get("cutoff_range", (0, 0))
        print(f"📈 Cutoff Range: {cutoff_range[0]:.1f} - {cutoff_range[1]:.1f} Hz")
        print("🎯 Region Cutoffs:")
        marker_regions = winter_meta.get("marker_regions", {})
        for region, cutoff in winter_meta.get("region_cutoffs", {}).items():
            n_markers = sum(1 for _m, r in marker_regions.items() if r == region)
            print(f"     {region:20s}: {cutoff:4.1f} Hz ({n_markers} markers)")
    else:
        print(f"🔬 Winter Cutoff: {winter_meta.get('cutoff_hz', 0):.1f} Hz")
        print(f"📈 Rep Column: {winter_meta.get('rep_col', 'N/A')}")
        print("🔄 Range: 1-12 Hz (Conservative for dance)")
        if "biomechanical_guardrails" in winter_meta:
            g = winter_meta["biomechanical_guardrails"]
            print(f"🛡️  Guardrails: {g['strategy']}")
            print(f"   Min cutoffs: Trunk={g['min_cutoff_trunk']} Hz, Distal={g['min_cutoff_distal']} Hz")
        if winter_failed:
            print("ℹ️  Winter RMS Analysis: Would suggest fmax (diagnostic only)")
            print("   Note: Fixed literature cutoffs are used regardless")
            print(f"   Decision: {decision_reason}")
        else:
            print("ℹ️  Winter RMS Analysis: Agrees with fixed cutoffs")
            print(f"   Decision: {decision_reason}")
    print(f"{'='*60}\n")


def print_audit_preview(summary_path: str, run_id: Optional[str] = None) -> None:
    """
    Print audit preview from the filtering summary JSON (same source as export_filter_summary).
    Used by notebook 04 to show values that will appear in Master Quality Report (NB07).
    Only uses keys written by this module; no duplicate print logic in the notebook.
    """
    with open(summary_path, "r") as f:
        summary = json.load(f)
    run_id = run_id or summary.get("run_id", "N/A")
    print("\n" + "=" * 80)
    print("AUDIT PREVIEW - VALUES FOR MASTER QUALITY REPORT (NB07)")
    print("=" * 80)
    print(f"Run ID: {run_id}")
    print()
    print("[SUBJECT METADATA]")
    print(f"  Subject_Mass_kg: {summary.get('subject_metadata', {}).get('mass_kg', 'N/A')}")
    print()
    fp = summary.get("filter_params", {})
    filtering_mode = fp.get("filtering_mode", "N/A")
    print("[FILTERING PARAMETERS]")
    print(f"  Filtering_Mode: {filtering_mode}")
    if filtering_mode == "3_stage_pipeline":
        print(f"  Filter_Type: {fp.get('filter_type', 'N/A')}")
        print(f"  Stage1_Artifacts_Detected: {fp.get('total_artifact_frames', 0)}")
        print(f"  Stage2_Hampel_Outliers: {fp.get('total_hampel_outliers', 0)}")
        cutoff_stats = fp.get("winter_cutoff_stats", {})
        if cutoff_stats:
            print(f"  Stage3_Cutoff_Range: {cutoff_stats.get('min', 0):.1f} - {cutoff_stats.get('max', 0):.1f} Hz")
            print(f"  Stage3_Mean_Cutoff: {cutoff_stats.get('mean', 0):.1f} Hz")
            print(f"  Stage3_Median_Cutoff: {cutoff_stats.get('median', 0):.1f} Hz")
        print(f"  Region_Cutoffs_Avg: {fp.get('region_cutoffs', {})}")
        print()
        print("[3-STAGE PIPELINE DIAGNOSTICS]")
        s1 = fp.get("stage1_artifact_detector", {})
        s2 = fp.get("stage2_hampel", {})
        s3 = fp.get("stage3_adaptive_winter", {})
        print(f"  Stage1_Velocity_Limit: {s1.get('velocity_limit', 'N/A')} mm/s")
        print(f"  Stage1_ZScore_Threshold: {s1.get('zscore_threshold', 'N/A')}σ")
        print(f"  Stage2_Window_Size: {s2.get('window_size', 'N/A')} frames")
        print(f"  Stage2_N_Sigma: {s2.get('n_sigma', 'N/A')}σ")
        print(f"  Stage3_Freq_Range: {s3.get('fmin', 'N/A')} - {s3.get('fmax', 'N/A')} Hz")
        print(f"  Stage3_Per_Joint: {s3.get('per_joint', 'N/A')}")
        print()
    else:
        print(f"  Region_Cutoffs_Applied: {fp.get('region_cutoffs', 'N/A')}")
        rms_val = fp.get("residual_rms_mm", "N/A")
        print(f"  Residual_RMS_mm: {round(rms_val, 2) if isinstance(rms_val, (int, float)) else rms_val}")
        print()
        print("[PER-REGION DIAGNOSTICS - RMS ANALYSIS]")
        region_details = fp.get("region_analysis_details", {})
        rms_knee = {}
        diminishing = {}
        validation_status = {}
        for region, details in region_details.items():
            rms_knee[region] = details.get("winter_strict_knee_hz") or details.get("winter_suggested_hz", "N/A")
            diminishing[region] = details.get("winter_diminishing_hz", "N/A")
            validation_status[region] = details.get("validation_status", "N/A")
        print(f"  RMS_Knee_Per_Region: {rms_knee}")
        print(f"  Diminishing_Per_Region: {diminishing}")
        print(f"  Region_Validation_Status: {validation_status}")
        print()
    snr = summary.get("snr_analysis", {})
    print("[TRUE RAW SNR - CAPTURE QUALITY]")
    print(f"  Raw_SNR_Mean_dB: {snr.get('mean_snr_db', 'N/A')}")
    print(f"  Raw_SNR_Min_dB: {snr.get('min_snr_db', 'N/A')}")
    print(f"  Raw_SNR_Max_dB: {snr.get('max_snr_db', 'N/A')}")
    print(f"  Raw_SNR_Status: {snr.get('overall_status', 'N/A')}")
    print(f"  Raw_SNR_Joints_Excellent: {snr.get('joints_excellent', 'N/A')}")
    print(f"  Raw_SNR_Failed_Joints: {snr.get('failed_joints', [])}")
    print()
    print("=" * 80)
    print("NOTE: These values will appear in the Master Audit Excel (NB07)")
    print("      Run 07_master_quality_report.ipynb to generate the full report.")
    print("=" * 80)


def export_residuals_if_available(
    winter_metadata: Dict[str, Any],
    run_id: str,
    save_dir: str,
) -> Optional[str]:
    """
    Export Winter residual curve data for Master Audit if present in metadata.

    Returns:
        Path to the residual file if export succeeded, else None.
    """
    try:
        from winter_export import export_winter_residual_data
        path = export_winter_residual_data(winter_metadata, run_id, save_dir)
        print(f"{'='*20} EXPORTING WINTER RESIDUAL DATA {'='*20}")
        print(f"Winter Residual Data: {path}")
        print("Purpose: Enables inline RMS residual plotting in Master Audit")
        print(f"{'='*60}\n")
        return path
    except Exception as e:
        print(f"Winter residual export failed: {e}")
        print("   Note: Residual curve data may not be in winter_metadata")
        print("   Master Audit will use summary data only")
        print(f"{'='*60}\n")
        return None
