#!/usr/bin/env python3
"""
run_qc_aggregator.py — Ticket 014b: Feature Reliability Table Aggregator.

Reads all session_qc_report.json files from audit_outputs/sessions/ and produces:
  audit_outputs/feature_reliability_table.csv
  audit_outputs/feature_family_reliability.csv

Includes Ticket 015 filter-ceiling saturation telemetry (reads filtering sidecars).
"""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

DEFAULT_SESSIONS_DIR = "audit_outputs/sessions"
DEFAULT_OUTPUT_DIR = "audit_outputs"
DEFAULT_FILTER_DIR = "derivatives/step_04_filtering"

_REGION_TO_FAMILIES = {
    "trunk":          ["ATF_axial", "TM_total_movement", "ATF_whole_body"],
    "head":           ["ATF_axial", "ATF_whole_body"],
    "upper_proximal": ["ATF_transitional", "ATF_whole_body", "Gini_angular_velocity", "D_eff_pca"],
    "upper_distal":   ["ATF_peripheral", "ATF_whole_body"],
    "lower_proximal": ["ATF_transitional", "ATF_whole_body", "Gini_angular_velocity", "D_eff_pca"],
    "lower_distal":   ["ATF_peripheral", "ATF_whole_body"],
}

FEATURE_FAMILIES = {
    "ATF_whole_body": {
        "description": "Active Time Fraction — whole-body median over all 19 joints",
        "requires_lin_vel": True,
        "requires_omega": False,
        "axial_sensitive": False,
        "thesis_critical": True,
    },
    "ATF_axial": {
        "description": "ATF axial chain (Spine, Spine1, Neck, Head — Hips excluded per T010)",
        "requires_lin_vel": True,
        "requires_omega": False,
        "axial_sensitive": True,
        "thesis_critical": True,
    },
    "ATF_peripheral": {
        "description": "ATF peripheral joints (hands, feet)",
        "requires_lin_vel": True,
        "requires_omega": False,
        "axial_sensitive": False,
        "thesis_critical": True,
    },
    "ATF_transitional": {
        "description": "ATF transitional joints (arms, legs)",
        "requires_lin_vel": True,
        "requires_omega": False,
        "axial_sensitive": False,
        "thesis_critical": False,
    },
    "TM_total_movement": {
        "description": "Total Movement — integral of linear velocity over session",
        "requires_lin_vel": True,
        "requires_omega": False,
        "axial_sensitive": False,
        "thesis_critical": True,
    },
    "Gini_angular_velocity": {
        "description": "Gini coefficient of PCA-attributed angular velocity variance",
        "requires_lin_vel": False,
        "requires_omega": True,
        "axial_sensitive": False,
        "thesis_critical": True,
    },
    "D_eff_pca": {
        "description": "Effective dimensionality from PCA on angular velocity (omega_mag)",
        "requires_lin_vel": False,
        "requires_omega": True,
        "axial_sensitive": False,
        "thesis_critical": True,
    },
}


def _load_filter_ceiling_saturation(session_id: str, filter_dir: str) -> dict:
    sidecar = Path(filter_dir) / f"{session_id}__filtering_summary.json"
    if not sidecar.exists():
        return {}
    try:
        with open(sidecar, encoding="utf-8") as f:
            sd = json.load(f)
    except Exception:
        return {}
    loop = sd.get("filter_params", {}).get("psd_correction_loop", {})
    if not loop:
        return {}
    final_hz = loop.get("final_region_min_cutoff_hz", {})
    ceiling_hz = loop.get("region_ceiling_hz", {})
    if not final_hz or not ceiling_hz:
        return {}
    saturated_regions = [
        r for r in final_hz
        if r in ceiling_hz and float(final_hz[r]) >= float(ceiling_hz[r])
    ]
    saturated_families: set = set()
    for r in saturated_regions:
        saturated_families.update(_REGION_TO_FAMILIES.get(r, []))
    return {
        "saturated_regions": saturated_regions,
        "saturated_families": sorted(saturated_families),
        "final_region_min_cutoff_hz": final_hz,
        "region_ceiling_hz": ceiling_hz,
        "convergence_status": loop.get("convergence_status"),
        "n_iterations": loop.get("n_iterations"),
    }


def load_sessions(sessions_dir: str, filter_dir: str = DEFAULT_FILTER_DIR) -> pd.DataFrame:
    sessions_path = Path(sessions_dir)
    json_files = sorted(sessions_path.glob("*_qc_report.json"))
    if not json_files:
        print(f"[WARNING] No session QC reports found in: {sessions_dir}")
        return pd.DataFrame()

    records = []
    for jf in json_files:
        try:
            with open(jf, encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print(f"[WARNING] Could not load {jf.name}: {e}")
            continue

        rec = {}
        _sess_id = raw.get("session_id", "")
        _sat = _load_filter_ceiling_saturation(_sess_id, filter_dir)
        rec["filter_ceiling_saturated_regions"] = (
            ";".join(_sat.get("saturated_regions", [])) if _sat else ""
        )
        rec["filter_ceiling_saturated_families"] = (
            ";".join(_sat.get("saturated_families", [])) if _sat else ""
        )
        rec["filter_loop_convergence_status"] = _sat.get("convergence_status") if _sat else None
        rec["filter_loop_n_iterations"] = _sat.get("n_iterations") if _sat else None

        scalar_fields = [
            "session_id", "subject_id", "timepoint", "piece", "rep",
            "processing_timestamp", "pipeline_version",
            "gate_01_status", "ref_is_fallback", "fallback_path_used",
            "t_pose_failed", "ref_quality_score",
            "filter_psd_verdict", "bone_qc_status",
            "frame_loss_rate",
            "n_artifact_segments_positions",
            "max_artifact_segment_frames_positions",
            "n_artifact_segments_above_10_frames",
            "n_gap_fill_events_positions",
            "max_gap_duration_frames_positions",
            "hampel_max_fraction_any_joint",
            "quat_norm_gt5pct_warning",
            "total_hemisphere_flips_corrected",
            "lin_kine_n_joints_with_dropped_axes",
            "overall_qc_status",
        ]
        for k in scalar_fields:
            rec[k] = raw.get(k)

        ps = raw.get("pipeline_steps_confirmed", {})
        for step in ("S01", "S02", "S03", "S04", "S05", "S06"):
            rec[f"step_{step}_complete"] = bool(ps.get(step, False))

        apj = raw.get("artifact_fraction_per_joint") or {}
        rec["artifact_frac_max_joint"] = max(apj.values()) if apj else None
        rec["artifact_frac_mean_joint"] = (
            float(np.mean(list(apj.values()))) if apj else None
        )

        hpj = raw.get("hampel_modification_fraction_per_joint") or {}
        rec["hampel_frac_mean_joint"] = (
            float(np.mean(list(hpj.values()))) if hpj else None
        )

        records.append(rec)

    df = pd.DataFrame(records)

    if "session_id" in df.columns:
        n_before = len(df)
        df = df.drop_duplicates(subset=["session_id"], keep="last")
        if len(df) < n_before:
            print(f"[WARNING] Dropped {n_before - len(df)} duplicate session_id rows (kept latest)")
        df = df.set_index("session_id", drop=False).reset_index(drop=True)

    return df


def _derive_reliability(row: dict, family_name: str, family_cfg: dict):
    reasons = []
    gate = row.get("gate_01_status", "UNKNOWN")
    overall = row.get("overall_qc_status", "UNKNOWN")
    psd = row.get("filter_psd_verdict") or ""
    lin_dropped = row.get("lin_kine_n_joints_with_dropped_axes") or 0
    quat_warn = bool(row.get("quat_norm_gt5pct_warning", False))
    hampel_max = row.get("hampel_max_fraction_any_joint") or 0.0
    pipeline_complete = all(
        row.get(f"step_{s}_complete", False)
        for s in ("S01", "S02", "S03", "S04", "S05", "S06")
    )

    if gate == "FAIL":
        return "UNRELIABLE", ["gate_01_status=FAIL"], False
    if not pipeline_complete:
        return "UNRELIABLE", ["pipeline_incomplete"], False

    _sat_families_raw = row.get("filter_ceiling_saturated_families") or ""
    _sat_families = set(_sat_families_raw.split(";")) if _sat_families_raw else set()
    _sat_families.discard("")
    if family_name in _sat_families:
        reasons.append("FILTER_CEILING_SATURATED_HIGH_RISK_DERIVATIVES")

    if family_cfg["requires_lin_vel"]:
        if lin_dropped >= 10:
            return "NOT_AVAILABLE", [f"lin_kine_dropped={lin_dropped}_joints_>=10"], False
        if lin_dropped > 0:
            reasons.append(f"lin_kine_dropped={lin_dropped}_joints")
        if psd == "REVIEW_OVERSMOOTHING":
            reasons.append("filter_psd=REVIEW_OVERSMOOTHING")
        if family_cfg["axial_sensitive"] and lin_dropped > 0:
            reasons.append("axial_lin_kine_risk")

    if family_cfg["requires_omega"]:
        if quat_warn:
            reasons.append("quat_norm_gt5pct_warning")
        if hampel_max > 0.05:
            reasons.append(f"hampel_max={hampel_max:.3f}>0.05")

    if overall == "WARN" and not reasons:
        reasons.append("overall_qc=WARN")

    if reasons:
        return "USE_WITH_CAUTION", reasons, False
    return "RELIABLE", [], True


def build_feature_family_table(session_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in session_df.iterrows():
        row_dict = row.to_dict()
        for family_name, family_cfg in FEATURE_FAMILIES.items():
            status, reasons, safe_ml = _derive_reliability(row_dict, family_name, family_cfg)
            rows.append({
                "session_id":       row_dict.get("session_id"),
                "subject_id":       row_dict.get("subject_id"),
                "timepoint":        row_dict.get("timepoint"),
                "piece":            row_dict.get("piece"),
                "rep":              row_dict.get("rep"),
                "feature_family":   family_name,
                "description":      family_cfg["description"],
                "reliability_status": status,
                "reason_codes":     "; ".join(reasons) if reasons else "",
                "thesis_critical":  family_cfg["thesis_critical"],
                "safe_for_ml":      safe_ml,
                "overall_qc_status": row_dict.get("overall_qc_status"),
                "filter_psd_verdict": row_dict.get("filter_psd_verdict"),
                "lin_kine_n_joints_with_dropped_axes": row_dict.get("lin_kine_n_joints_with_dropped_axes"),
                "quat_norm_gt5pct_warning": row_dict.get("quat_norm_gt5pct_warning"),
            })
    return pd.DataFrame(rows)


def print_summary(session_df: pd.DataFrame, family_df: pd.DataFrame):
    print(f"\n{'='*70}")
    print("SESSION-LEVEL SUMMARY")
    print(f"{'='*70}")

    if session_df.empty:
        print("  No sessions found.")
        return

    tally = session_df["overall_qc_status"].value_counts().to_dict()
    for status in ("PASS", "WARN", "FAIL"):
        count = tally.get(status, 0)
        print(f"  {status:<8}: {count:>3} session(s)")

    print(f"\n{'='*70}")
    print("FILTER CEILING SATURATION (Ticket 015)")
    print(f"{'='*70}")
    flagged = session_df[
        session_df["filter_ceiling_saturated_regions"].astype(str).str.len() > 0
    ]
    if flagged.empty:
        print("  No sessions with regional filter cutoff at ceiling.")
    else:
        for _, r in flagged.iterrows():
            print(f"  {r['session_id'][:70]}")
            print(f"    regions: {r['filter_ceiling_saturated_regions']}")
            print(f"    families: {r['filter_ceiling_saturated_families']}")

    if family_df.empty:
        return
    ceiling_mask = family_df["reason_codes"].str.contains(
        "FILTER_CEILING_SATURATED", na=False
    )
    n_ceiling = ceiling_mask.sum()
    print(f"\n  Feature-family rows with FILTER_CEILING_SATURATED_HIGH_RISK_DERIVATIVES: {int(n_ceiling)}")

    print(f"\n{'='*70}")
    print("FEATURE FAMILY RELIABILITY — OVERVIEW")
    print(f"{'='*70}")
    pivot = (
        family_df.groupby(["feature_family", "reliability_status"])
        .size()
        .unstack(fill_value=0)
    )
    for col in ("RELIABLE", "USE_WITH_CAUTION", "UNRELIABLE", "NOT_AVAILABLE"):
        if col not in pivot.columns:
            pivot[col] = 0
    print(f"\n  {'Feature Family':<30} {'RELIABLE':>9} {'CAUTION':>9} {'UNRELIABLE':>11} {'N/A':>5}")
    print(f"  {'-'*64}")
    for family, row in pivot.iterrows():
        print(f"  {family:<30} {row['RELIABLE']:>9} {row['USE_WITH_CAUTION']:>9} "
              f"{row['UNRELIABLE']:>11} {row.get('NOT_AVAILABLE', 0):>5}")


def main():
    parser = argparse.ArgumentParser(description="Ticket 014b — QC aggregator")
    parser.add_argument("--sessions-dir", default=DEFAULT_SESSIONS_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--filter-dir", default=DEFAULT_FILTER_DIR)
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print("GAGA Pipeline — QC Aggregator (Ticket 014b)")
    print(f"Timestamp   : {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"Sessions dir: {args.sessions_dir}")
    print(f"Filter dir  : {args.filter_dir}")
    print(f"Output dir  : {args.output_dir}")
    print(f"{'='*70}\n")

    session_df = load_sessions(args.sessions_dir, filter_dir=args.filter_dir)
    n = len(session_df)
    print(f"Loaded {n} session(s)")
    if n == 0:
        print("Nothing to aggregate. Exiting.")
        sys.exit(0)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    session_csv = out / "feature_reliability_table.csv"
    session_df.to_csv(session_csv, index=False)
    print(f"Written: {session_csv}  ({n} rows × {len(session_df.columns)} columns)")

    family_df = build_feature_family_table(session_df)
    family_csv = out / "feature_family_reliability.csv"
    family_df.to_csv(family_csv, index=False)
    print(f"Written: {family_csv}  ({len(family_df)} rows)")

    print_summary(session_df, family_df)
    print(f"\n{'='*70}\nDone.\n{'='*70}\n")


if __name__ == "__main__":
    main()
