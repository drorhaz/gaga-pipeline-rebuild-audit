"""
Forensic QA Visualisations  —  v3.1
=====================================
Companion to ``forensic_report.py``.  Produces five standalone plots
and one composite dashboard PNG.

Public API
----------
    generate_all_plots(report, original_df, cleaned_df, ...)

Individual plot functions are also public so they can be called
from notebooks independently.

Author : Gaga Motion Analysis Pipeline
Date   : 2026-02-17
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # headless-safe
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from forensic_config import (
    BONE_CV_GOLD,
    BONE_CV_WARN,
    COLOR_CLEAN,
    COLOR_FAIL_ZONE,
    COLOR_GOLD_ZONE,
    COLOR_HIGH_VEL,
    COLOR_RAW,
    COLOR_TIER1,
    COLOR_TIER2,
    COLOR_TIER3,
    COLOR_WARN_ZONE,
    PLOT_DPI,
    PLOT_FIGSIZE_DASHBOARD,
    PLOT_FIGSIZE_SINGLE,
    PLOT_STYLE,
    REPRESENTATIVE_JOINTS,
    FALLBACK_JOINTS,
)

logger = logging.getLogger(__name__)

# Safe style application (fallback if seaborn style unavailable)
try:
    plt.style.use(PLOT_STYLE)
except OSError:
    plt.style.use("ggplot")


# =====================================================================
# helpers
# =====================================================================

def _save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(str(path), dpi=PLOT_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("Plot saved → %s", path)


def _resolve_joint(joint: str, available: list) -> Optional[str]:
    if joint in available:
        return joint
    for fb in FALLBACK_JOINTS.get(joint, []):
        if fb in available:
            return fb
    return None


def _joint_names_from_pos(df: pd.DataFrame) -> list:
    return sorted({c.rsplit("__", 1)[0] for c in df.columns if c.endswith(("__px", "__py", "__pz"))})


def _classify_region_simple(joint: str) -> str:
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
# Plot 1 — Bone Integrity Bar Chart
# =====================================================================

def plot_bone_integrity(
    report: dict,
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    skeleton_schema: dict,
    fs: float,
    output_path: Path,
) -> None:
    """
    Grouped bar chart: Raw CV% / Cleaned CV% / High-Velocity Subset CV%
    per bone, with GOLD / WARN / FAIL zone shading.
    """
    bone_raw = report.get("block_e_kinematic", {}).get("bone_cv_raw", {})
    bone_clean = report.get("block_e_kinematic", {}).get("bone_cv_clean", {})
    bones = skeleton_schema.get("bones", [])

    if not bone_raw and not bone_clean:
        logger.warning("No bone data — skipping bone integrity plot")
        return

    # Compute high-velocity subset CV for each bone
    bone_names = sorted(set(bone_raw.keys()) | set(bone_clean.keys()))
    # Filter out finger bones for readability
    finger_kw = ("thumb", "index", "middle", "ring", "pinky")
    bone_names = [b for b in bone_names if not any(k in b.lower() for k in finger_kw)]

    if not bone_names:
        logger.warning("No non-finger bones — skipping bone integrity plot")
        return

    raw_cvs = []
    clean_cvs = []
    hv_cvs = []

    # Build velocity magnitude per frame for high-vel detection
    pos_cols = [c for c in cleaned_df.columns if c.endswith(("__px", "__py", "__pz"))]
    vel_mag = np.zeros(max(len(cleaned_df) - 1, 1))
    dt = 1.0 / fs
    for col in pos_cols:
        v = np.abs(np.diff(cleaned_df[col].values.astype(float)) / dt)
        finite = np.isfinite(v)
        v_safe = np.where(finite, v, 0.0)
        vel_mag = np.maximum(vel_mag, v_safe)
    # High velocity mask: frames where max marker velocity > 2000 mm/s
    hv_mask_vel = vel_mag > 2000.0
    # Extend mask to full length (add False for last frame)
    hv_mask = np.append(hv_mask_vel, False)

    for bname in bone_names:
        raw_cvs.append(bone_raw.get(bname, {}).get("cv_percent", 0.0))
        clean_cvs.append(bone_clean.get(bname, {}).get("cv_percent", 0.0))

        # High-velocity bone CV
        parts = bname.split("->")
        if len(parts) == 2:
            parent, child = parts
            pcols = [f"{parent}__p{a}" for a in "xyz"]
            ccols = [f"{child}__p{a}" for a in "xyz"]
            if all(c in cleaned_df.columns for c in pcols + ccols):
                P = cleaned_df[pcols].values.astype(float)
                C = cleaned_df[ccols].values.astype(float)
                valid = np.isfinite(P).all(axis=1) & np.isfinite(C).all(axis=1) & hv_mask
                if valid.sum() >= 10:
                    L = np.linalg.norm(C[valid] - P[valid], axis=1)
                    m = float(np.mean(L))
                    s = float(np.std(L))
                    hv_cvs.append(round((s / m) * 100 if m > 0 else 0, 3))
                else:
                    hv_cvs.append(0.0)
            else:
                hv_cvs.append(0.0)
        else:
            hv_cvs.append(0.0)

    # Sort by raw CV descending
    order = np.argsort(raw_cvs)[::-1]
    bone_names = [bone_names[i] for i in order]
    raw_cvs = [raw_cvs[i] for i in order]
    clean_cvs = [clean_cvs[i] for i in order]
    hv_cvs = [hv_cvs[i] for i in order]

    # Limit to top 25 for readability
    max_show = 25
    bone_names = bone_names[:max_show]
    raw_cvs = raw_cvs[:max_show]
    clean_cvs = clean_cvs[:max_show]
    hv_cvs = hv_cvs[:max_show]

    n = len(bone_names)
    x = np.arange(n)
    w = 0.25

    fig, ax = plt.subplots(figsize=(max(12, n * 0.5), 7))

    # Zone shading
    ax.axhspan(0, BONE_CV_GOLD * 100, color=COLOR_GOLD_ZONE, alpha=0.3, label="GOLD (≤2%)")
    ax.axhspan(BONE_CV_GOLD * 100, BONE_CV_WARN * 100, color=COLOR_WARN_ZONE, alpha=0.3, label="WARN (2–5%)")
    ax.axhspan(BONE_CV_WARN * 100, max(max(raw_cvs, default=6) * 1.1, 6), color=COLOR_FAIL_ZONE, alpha=0.2, label="FAIL (>5%)")

    ax.bar(x - w, raw_cvs, w, color=COLOR_RAW, label="Raw", edgecolor="white", linewidth=0.5)
    ax.bar(x, clean_cvs, w, color=COLOR_CLEAN, label="Cleaned", edgecolor="white", linewidth=0.5)
    ax.bar(x + w, hv_cvs, w, color=COLOR_HIGH_VEL, label="High-Velocity Subset", edgecolor="white", linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(bone_names, rotation=55, ha="right", fontsize=7)
    ax.set_ylabel("Bone Length CV (%)")
    ax.set_title("Bone Integrity: Raw vs Cleaned vs High-Velocity Frames")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    _save(fig, output_path)


# =====================================================================
# Plot 2 — Gap Topology Heatmap
# =====================================================================

def plot_gap_topology(report: dict, output_path: Path) -> None:
    """2D heatmap: joints (Y) x time bins (X), colour = fraction missing."""
    block_b = report.get("block_b_gaps", {})
    topo_raw = block_b.get("topology_raw", {})
    topo_clean = block_b.get("topology_clean", {})
    bin_sec = block_b.get("bin_sec", 1.0)

    if not topo_raw:
        logger.warning("No topology data — skipping gap heatmap")
        return

    # Filter out finger joints for readability
    finger_kw = ("thumb", "index", "middle", "ring", "pinky")
    joints = [j for j in sorted(topo_raw.keys()) if not any(k in j.lower() for k in finger_kw)]
    if not joints:
        joints = sorted(topo_raw.keys())

    # Sort joints by body region
    region_order = ["trunk", "head", "upper_proximal", "upper_distal", "lower_proximal", "lower_distal", "other"]
    joints_sorted = sorted(joints, key=lambda j: (region_order.index(_classify_region_simple(j)) if _classify_region_simple(j) in region_order else 99, j))

    n_bins = block_b.get("n_bins", 1)

    fig, axes = plt.subplots(1, 2, figsize=(16, max(6, len(joints_sorted) * 0.25)), sharey=True,
                             constrained_layout=True)

    for ax, topo, title in zip(axes, [topo_raw, topo_clean], ["Raw (Pre-Cleaning)", "Clean (Post-Cleaning)"]):
        matrix = np.zeros((len(joints_sorted), n_bins))
        for i, j in enumerate(joints_sorted):
            vals = topo.get(j, [0.0] * n_bins)
            matrix[i, :len(vals)] = vals[:n_bins]

        im = ax.imshow(
            matrix, aspect="auto", cmap="YlOrRd", vmin=0, vmax=1,
            interpolation="nearest",
        )
        ax.set_title(title, fontsize=11)
        ax.set_xlabel(f"Time ({bin_sec}s bins)")

        # X tick labels (every 10 bins)
        xtick_step = max(1, n_bins // 10)
        ax.set_xticks(range(0, n_bins, xtick_step))
        ax.set_xticklabels([f"{i*bin_sec:.0f}" for i in range(0, n_bins, xtick_step)], fontsize=7)

    axes[0].set_yticks(range(len(joints_sorted)))
    axes[0].set_yticklabels(joints_sorted, fontsize=7)
    axes[0].set_ylabel("Joint")

    fig.colorbar(im, ax=axes, label="Fraction Missing", shrink=0.6, pad=0.02)
    fig.suptitle("Gap Topology: Spatiotemporal Distribution of Missing Data", fontsize=13)
    _save(fig, output_path)


# =====================================================================
# Plot 3 — Artifact Timeline
# =====================================================================

def plot_artifact_timeline(report: dict, fs: float, output_path: Path) -> None:
    """Scatter plot: time (X) x joint (Y), coloured by tier."""
    burst = report.get("block_d_artifacts", {}).get("burst_classification", {})
    events = burst.get("events", [])

    if not events or burst.get("status") == "not_provided":
        logger.warning("No burst events — skipping artifact timeline (burst_log not provided)")
        return

    # Collect unique joints and build y-index
    joints_in_events = sorted({e["joint"] for e in events})
    joint_idx = {j: i for i, j in enumerate(joints_in_events)}

    fig, ax = plt.subplots(figsize=PLOT_FIGSIZE_SINGLE)

    tier_cfg = {
        1: {"color": COLOR_TIER1, "marker": "x", "size": 30, "label": "Tier 1 — Artifact (removed)"},
        2: {"color": COLOR_TIER2, "marker": "^", "size": 30, "label": "Tier 2 — Burst (warning)"},
        3: {"color": COLOR_TIER3, "marker": "o", "size": 25, "label": "Tier 3 — Flow (Gaga preserved)"},
    }

    for tier_code, cfg in tier_cfg.items():
        tier_events = [e for e in events if e.get("tier") == tier_code]
        if not tier_events:
            continue
        xs = [e["start_frame"] / fs for e in tier_events]
        ys = [joint_idx.get(e["joint"], 0) for e in tier_events]
        ax.scatter(xs, ys, c=cfg["color"], marker=cfg["marker"], s=cfg["size"],
                   label=cfg["label"], alpha=0.7, edgecolors="none")

    ax.set_yticks(range(len(joints_in_events)))
    ax.set_yticklabels(joints_in_events, fontsize=7)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Joint")
    ax.set_title("Artifact vs Preserved Movement Timeline")
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    _save(fig, output_path)


# =====================================================================
# Plot 4 — PSD Comparison
# =====================================================================

def plot_psd_comparison(report: dict, output_path: Path) -> None:
    """Log-log PSD: raw (grey dashed) vs cleaned (blue solid) per representative joint."""
    psd_data = report.get("block_c_noise", {}).get("psd_comparison", {})
    valid_joints = [j for j in REPRESENTATIVE_JOINTS if psd_data.get(j, {}).get("status") == "OK"]

    if not valid_joints:
        logger.warning("No valid PSD data — skipping PSD plot")
        return

    n = len(valid_joints)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 5), squeeze=False)

    for idx, target in enumerate(valid_joints):
        ax = axes[0, idx]
        d = psd_data[target]

        f_raw = np.array(d.get("_freqs_raw", []))
        p_raw = np.array(d.get("_psd_raw", []))
        f_cln = np.array(d.get("_freqs_clean", []))  if d.get("_freqs_clean") else None
        p_cln = np.array(d.get("_psd_clean", []))     if d.get("_psd_clean") else None

        if len(f_raw) > 0:
            ax.semilogy(f_raw, p_raw, color="grey", linestyle="--", alpha=0.7, label="Raw")
        if f_cln is not None and len(f_cln) > 0:
            ax.semilogy(f_cln, p_cln, color=COLOR_CLEAN, linewidth=1.5, label="Cleaned")

        # Shade signal band
        ax.axvspan(0, 20, color=COLOR_GOLD_ZONE, alpha=0.15)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("PSD (mm²/Hz)" if idx == 0 else "")
        joint_used = d.get("joint_used", target)
        n_seg = d.get("n_segments_raw", "?")
        ax.set_title(f"{joint_used}\n({n_seg} segments)", fontsize=10)
        ax.legend(fontsize=7)
        ax.set_xlim(0, 60)

    fig.suptitle("Power Spectral Density: Raw vs Cleaned", fontsize=13, y=1.02)
    fig.tight_layout()
    _save(fig, output_path)


# =====================================================================
# Plot 5 — Forensic Dashboard (composite)
# =====================================================================

def plot_forensic_dashboard(report: dict, output_path: Path) -> None:
    """
    Composite 2×2 summary dashboard:
      (A) Data Recovery stacked bar
      (B) Per-Region mean residual RMS
      (C) Burst Classification pie
      (D) Bone CV lollipop with GOLD/WARN/FAIL zones
    """
    fig, axes = plt.subplots(2, 2, figsize=PLOT_FIGSIZE_DASHBOARD)

    # ── (A) Data Recovery ─────────────────────────────────────────────
    ax = axes[0, 0]
    inv = report.get("block_a_inventory", {})
    raw_nans = inv.get("raw", {}).get("total_nans", 0)
    cln_nans = inv.get("clean", {}).get("total_nans", 0)
    recovered = raw_nans - cln_nans
    total = inv.get("total_cells", 1)
    good_data = total - raw_nans

    labels = ["Valid Data", "Recovered", "Remaining NaN"]
    sizes = [good_data, max(recovered, 0), max(cln_nans, 0)]
    colors = [COLOR_CLEAN, "#81C784", COLOR_RAW]

    # Filter zero slices
    non_zero = [(l, s, c) for l, s, c in zip(labels, sizes, colors) if s > 0]
    if non_zero:
        labels_nz, sizes_nz, colors_nz = zip(*non_zero)
        ax.pie(sizes_nz, labels=labels_nz, colors=colors_nz, autopct="%1.1f%%",
               startangle=90, textprops={"fontsize": 8})
    ax.set_title("(A) Data Recovery", fontsize=11)

    # ── (B) Per-Region Residual RMS ───────────────────────────────────
    ax = axes[0, 1]
    region_rms = report.get("block_c_noise", {}).get("region_mean_residual_rms", {})
    if region_rms:
        regions = sorted(region_rms.keys())
        vals = [region_rms[r] for r in regions]
        y_pos = np.arange(len(regions))
        ax.barh(y_pos, vals, color=COLOR_CLEAN, edgecolor="white", height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(regions, fontsize=8)
        ax.set_xlabel("Mean Residual RMS (mm)")
    ax.set_title("(B) Noise Removed per Region", fontsize=11)

    # ── (C) Burst Classification Pie ──────────────────────────────────
    ax = axes[1, 0]
    burst = report.get("block_d_artifacts", {}).get("burst_classification", {})
    if burst.get("status") == "available":
        t1 = burst.get("tier1_artifact_frames", 0)
        t2 = burst.get("tier2_burst_frames", 0)
        t3 = burst.get("tier3_flow_frames", 0)
        total_frames = report.get("block_a_inventory", {}).get("total_frames", 1)
        normal = max(total_frames - t1 - t2 - t3, 0)

        slices = [
            ("Normal", normal, COLOR_CLEAN),
            ("Tier 1 Artifact", t1, COLOR_TIER1),
            ("Tier 2 Burst", t2, COLOR_TIER2),
            ("Tier 3 Flow (Gaga)", t3, COLOR_TIER3),
        ]
        slices = [(l, s, c) for l, s, c in slices if s > 0]
        if slices:
            labels_s, sizes_s, colors_s = zip(*slices)
            ax.pie(sizes_s, labels=labels_s, colors=colors_s, autopct="%1.2f%%",
                   startangle=90, textprops={"fontsize": 8})
    else:
        ax.text(0.5, 0.5, "Burst classification\nnot provided", transform=ax.transAxes,
                ha="center", va="center", fontsize=10, color="grey")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    ax.set_title("(C) Burst Classification", fontsize=11)

    # ── (D) Bone CV Lollipop ──────────────────────────────────────────
    ax = axes[1, 1]
    bone_clean = report.get("block_e_kinematic", {}).get("bone_cv_clean", {})
    if bone_clean:
        # Exclude fingers
        finger_kw = ("thumb", "index", "middle", "ring", "pinky")
        items = [(k, v) for k, v in bone_clean.items() if not any(f in k.lower() for f in finger_kw)]
        items = sorted(items, key=lambda x: x[1].get("cv_percent", 0), reverse=True)[:20]
        names = [i[0] for i in items]
        cvs = [i[1].get("cv_percent", 0) for i in items]

        y_pos = np.arange(len(names))
        colors_lollipop = []
        for cv in cvs:
            if cv <= BONE_CV_GOLD * 100:
                colors_lollipop.append(COLOR_GOLD_ZONE)
            elif cv <= BONE_CV_WARN * 100:
                colors_lollipop.append(COLOR_WARN_ZONE)
            else:
                colors_lollipop.append(COLOR_FAIL_ZONE)

        ax.hlines(y_pos, 0, cvs, color="grey", linewidth=0.8)
        ax.scatter(cvs, y_pos, c=colors_lollipop, s=50, edgecolors="grey", zorder=5)
        ax.axvline(BONE_CV_GOLD * 100, color="green", linestyle="--", linewidth=0.7, label="GOLD 2%")
        ax.axvline(BONE_CV_WARN * 100, color="orange", linestyle="--", linewidth=0.7, label="WARN 5%")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontsize=7)
        ax.set_xlabel("CV (%)")
        ax.legend(fontsize=7, loc="lower right")
    ax.set_title("(D) Bone Length CV (Cleaned)", fontsize=11)

    # ── Layout ────────────────────────────────────────────────────────
    run_id = report.get("run_id", "")
    verdict = report.get("executive_summary", {}).get("verdict", "")
    fig.suptitle(f"Forensic QA Dashboard — {run_id}\n{verdict}", fontsize=13, y=1.02)
    fig.tight_layout()
    _save(fig, output_path)


# =====================================================================
# Public entry point
# =====================================================================

def generate_all_plots(
    report: dict,
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    skeleton_schema: dict,
    fs: float,
    output_dir: Path,
    prefix: str = "forensic",
) -> List[Path]:
    """
    Generate all forensic visualisations and write PNGs.

    Returns list of created file paths.
    """
    output_dir = Path(output_dir)
    created: List[Path] = []

    # Plot 1 — Bone Integrity
    p = output_dir / f"{prefix}__forensic_bone_integrity.png"
    try:
        plot_bone_integrity(report, original_df, cleaned_df, skeleton_schema, fs, p)
        created.append(p)
    except Exception as exc:
        logger.warning("Bone integrity plot failed: %s", exc)

    # Plot 2 — Gap Topology
    p = output_dir / f"{prefix}__forensic_gap_topology.png"
    try:
        plot_gap_topology(report, p)
        created.append(p)
    except Exception as exc:
        logger.warning("Gap topology plot failed: %s", exc)

    # Plot 3 — Artifact Timeline
    p = output_dir / f"{prefix}__forensic_artifact_timeline.png"
    try:
        plot_artifact_timeline(report, fs, p)
        created.append(p)
    except Exception as exc:
        logger.warning("Artifact timeline plot failed: %s", exc)

    # Plot 4 — PSD Comparison
    p = output_dir / f"{prefix}__forensic_psd_comparison.png"
    try:
        plot_psd_comparison(report, p)
        created.append(p)
    except Exception as exc:
        logger.warning("PSD comparison plot failed: %s", exc)

    # Plot 5 — Dashboard (composite)
    p = output_dir / f"{prefix}__forensic_dashboard.png"
    try:
        plot_forensic_dashboard(report, p)
        created.append(p)
    except Exception as exc:
        logger.warning("Dashboard plot failed: %s", exc)

    logger.info("Forensic plots: %d/%d generated successfully", len(created), 5)
    return created
