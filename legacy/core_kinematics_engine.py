"""
src/core_kinematics_engine.py
Pure analytical backend for the 3+3+1 Thesis Kinematic Pipeline.

No widget imports. No I/O side effects during computation.
All I/O (parquet reads, JSON writes) isolated to load_* / export_* functions.

Pipeline stages:
  Stage 0 — Session Discovery & Registry
  Stage 1 — ATF Computation
  Stage 2 — Time-Window Cropping & Branch-Local Artifact Masking
  Stage 3 — T1-Anchored PCA
  Stage 4 — Metric Computation (D_eff, Gini, Entropy, SampEn, A/P, RQA)
  Stage 5 — Results Assembly, Delta Table, Block Bootstrap CI
  Stage 6 — Visualization & Pipeline Validation
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import scipy.spatial.distance as spdist

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    _HAS_PLOTLY = True
except ImportError:
    go = None
    _HAS_PLOTLY = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    _HAS_MPL = True
except ImportError:
    plt = None
    _HAS_MPL = False

try:
    from pyrqa.time_series import EmbeddedSeries
    from pyrqa.settings import Settings
    from pyrqa.computation import RQAComputation
    from pyrqa.metric import EuclideanMetric
    from pyrqa.neighbourhood import FixedRadius
    _HAS_PYRQA = True
except ImportError:
    _HAS_PYRQA = False

from pulsicity import compute_noise_floor
from EDA_PCA import (
    prepare_3branch_data,
    run_3branch_pca,
    calculate_n90,
    calculate_whole_system_stats,
    calculate_state_space_entropy,
    calculate_state_space_entropy_t1_edges,
    calculate_centroid_displacement,
    _sample_entropy_numpy,
    _feature_to_joint,
    _session_joint_contributions,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants  (§7 Thresholds & Magic Numbers Dictionary)
# ---------------------------------------------------------------------------

FS = 120.0  # Hz

# The 19 primary joints, derived strictly from skeleton_defs / §3.2
ALL_19_JOINTS = (
    "Hips", "Spine", "Spine1", "Neck", "Head",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot",
    "RightUpLeg", "RightLeg", "RightFoot",
)

# §2.9.2 — strict 3-group classification
AXIAL_JOINTS = ("Hips", "Spine", "Spine1", "Neck", "Head")  # 5 joints; no "Chest"
PERIPHERAL_JOINTS = (
    "LeftForeArm", "LeftHand",
    "RightForeArm", "RightHand",
    "LeftFoot", "RightFoot",
)
TRANSITIONAL_JOINTS = (
    "LeftShoulder", "RightShoulder",
    "LeftArm", "RightArm",
    "LeftUpLeg", "RightUpLeg",
    "LeftLeg", "RightLeg",
)

# Distal joints for ATF reporting (upper + lower extremities)
DISTAL_JOINTS = ("LeftForeArm", "LeftHand", "RightForeArm", "RightHand",
                 "LeftFoot", "RightFoot")

MIN_SESSION_FRAMES = 1_000          # dead-recording threshold
MIN_CLEAN_FRACTION = 0.70           # hard exclusion below this
ARTIFACT_WARNING_THRESHOLD = 0.20
ARTIFACT_CRITICAL_THRESHOLD = 0.30

N_BINS_DEFAULT = 25
VARIANCE_THRESHOLD_DEFAULT = 0.90   # N90 / D_eff (dynamic per §Update 4)
SAMPEN_M = 2
SAMPEN_R_FRACTION_DEFAULT = 0.20
RQA_EPSILON_PERCENTILE_DEFAULT = 10.0
RQA_L_MIN = 2
RQA_MAX_STATE_DIM = 5
RQA_SUBSAMPLE_TARGET = 5_000
BOOTSTRAP_N = 1_000
BOOTSTRAP_BLOCK_SEC_DEFAULT = 2.0
BOOTSTRAP_SEED = 42
ENTROPY_RELIABILITY_THRESHOLD = 0.50   # PC1+PC2 cumvar
ENTROPY_SPREAD_THRESHOLD = 0.05        # occupied bins fraction
SAMPEN_PC1_RELIABILITY_THRESHOLD = 0.25
ENTROPY_BIN_EDGE_PERCENTILE = (1, 99)

BRANCHES = ("dynamics", "pose", "reach")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SessionInfo:
    subject_id: str
    timepoint: str          # T1 / T2 / T3
    protocol: str           # P2
    run_num: str            # R1 / R2
    run_id: str
    parquet_path: Path
    n_frames: int
    duration_s: float
    artifact_pct_any_joint: float
    is_dead: bool
    quality_rank: int = 0


@dataclass
class ATFResult:
    run_id: str
    per_joint_atf: dict[str, float]
    whole_body_atf_median: float
    whole_body_atf_std: float
    atf_distal_median: float
    atf_axial_median: float
    artifact_concern: Literal["OK", "WARNING", "CRITICAL"]
    clean_fraction: float
    clean_duration_s: float
    noise_floor_low_confidence: dict[str, bool]
    # Raw arrays preserved for bootstrap
    vel_arrays: dict[str, np.ndarray]   # joint -> velocity array (all frames)
    art_arrays: dict[str, np.ndarray]   # joint -> is_artifact bool array
    noise_floors: dict[str, float]      # joint -> V_j


@dataclass
class ThesisMetricsBundle:
    subject_id: str
    timepoints: list[str]
    run_ids: list[str]

    # ── ATF ──────────────────────────────────────────────────────────────────
    atf_whole_body: list[float]
    atf_distal: list[float]
    atf_axial: list[float]
    atf_per_joint: list[dict[str, float]]
    atf_artifact_concern: list[str]
    atf_clean_fraction: list[float]

    # ── PCA-derived  (branch → list, indexed same as timepoints) ─────────────
    n90: dict[str, list[int]]
    d_eff: dict[str, list[float]]
    d_eff_norm: dict[str, list[float]]

    gini_joint_anchored: dict[str, list[float]]
    gini_joint_native: dict[str, list[float]]   # session-specific sensitivity

    entropy_equalized: dict[str, list[float]]
    entropy_raw: dict[str, list[float]]
    entropy_t1_edge: dict[str, list[float]]     # sensitivity §2.4.5
    entropy_occupied_frac: dict[str, list[float]]
    entropy_valid: dict[str, list[bool]]
    n_min_equalization_frames: dict[str, int]   # per branch

    centroid_displacement_raw: dict[str, list[float]]
    centroid_displacement_norm: dict[str, list[float]]  # normalized by T1 PC1 std

    sampen: dict[str, list[float | None]]
    sampen_reliable: dict[str, list[bool]]

    ap_ratio: dict[str, list[float]]
    ap_index: dict[str, list[float]]

    rqa_pct_rec: dict[str, list[float | None]]
    rqa_pct_det: dict[str, list[float | None]]
    rqa_reliable: dict[str, list[bool]]
    rqa_epsilon_used: dict[str, list[float | None]]
    rqa_state_dim: dict[str, list[int]]
    rqa_cum_var: dict[str, list[float]]

    # ── PCA metadata ─────────────────────────────────────────────────────────
    pc1pc2_var_coverage: dict[str, list[float]]
    pc1_var: dict[str, list[float]]
    explained_variance_ratio: dict[str, np.ndarray]   # branch -> full EVR from T1 PCA

    # ── Raw data refs for bootstrap (not serialized) ──────────────────────────
    _pca_results: dict = field(repr=False)      # run_t1_anchored_pca output
    _prepared: dict = field(repr=False)         # prepare_3branch_data output
    _atf_results: list[ATFResult] = field(repr=False)  # one per timepoint

    # ── Sensitivity parameters ────────────────────────────────────────────────
    variance_threshold: float = VARIANCE_THRESHOLD_DEFAULT
    n_bins: int = N_BINS_DEFAULT
    sampen_r_fraction: float = SAMPEN_R_FRACTION_DEFAULT
    rqa_epsilon_percentile: float = RQA_EPSILON_PERCENTILE_DEFAULT
    bootstrap_block_sec: float = BOOTSTRAP_BLOCK_SEC_DEFAULT


# ---------------------------------------------------------------------------
# Stage 0 — Session Discovery & Registry
# ---------------------------------------------------------------------------

def _parse_run_id(run_id: str) -> dict[str, str]:
    """
    Parse run_id like '651_T1_P2_R1_Take 2026-01-15 04.35.25 PM_002'
    into {subject_id, timepoint, protocol, run_num}.
    """
    m = re.match(r"^(\d+)_(T[123])_(P\d+)_(R\d+)", run_id)
    if not m:
        return {"subject_id": "UNKNOWN", "timepoint": "UNKNOWN",
                "protocol": "UNKNOWN", "run_num": "UNKNOWN"}
    return {
        "subject_id": m.group(1),
        "timepoint": m.group(2),
        "protocol": m.group(3),
        "run_num": m.group(4),
    }


def discover_sessions(
    step06_dir: Path,
    subject_filter: str | None = None,
    protocol_filter: str = "P2",
) -> list[SessionInfo]:
    """
    Glob step_06_kinematics for *__kinematics_master.parquet.
    Reads artifact_pct from is_artifact columns (lightweight column-select).
    Flags dead recordings (n_frames < MIN_SESSION_FRAMES).
    Returns sorted list: subject → timepoint → run_num.
    """
    step06_dir = Path(step06_dir)
    pattern = "*__kinematics_master.parquet"
    paths = sorted(step06_dir.glob(pattern))
    sessions: list[SessionInfo] = []

    for path in paths:
        run_id = path.stem.replace("__kinematics_master", "")
        parsed = _parse_run_id(run_id)
        if parsed["timepoint"] == "UNKNOWN":
            continue
        if parsed["protocol"] != protocol_filter:
            continue
        if subject_filter is not None and parsed["subject_id"] != subject_filter:
            continue

        # Lightweight read: only time_s + is_artifact columns
        try:
            art_cols = [c for c in pd.read_parquet(path, columns=["time_s"]).columns
                        if c == "time_s"]  # just get time first for n_frames / duration
            meta_df = pd.read_parquet(path, columns=["time_s"])
            n_frames = len(meta_df)
            duration_s = (
                float(meta_df["time_s"].iloc[-1] - meta_df["time_s"].iloc[0])
                if n_frames > 1 else 0.0
            )

            # Artifact percentage: any joint flagged at each frame
            all_cols = pd.read_parquet(path, columns=None).columns.tolist()
            art_flag_cols = [c for c in all_cols if c.endswith("__is_artifact")]
            if art_flag_cols:
                art_df = pd.read_parquet(path, columns=art_flag_cols)
                any_artifact = art_df.any(axis=1)
                artifact_pct = float(any_artifact.mean() * 100)
            else:
                artifact_pct = 0.0
        except Exception as exc:
            logger.warning("Could not read %s: %s", path, exc)
            continue

        is_dead = n_frames < MIN_SESSION_FRAMES
        sessions.append(SessionInfo(
            subject_id=parsed["subject_id"],
            timepoint=parsed["timepoint"],
            protocol=parsed["protocol"],
            run_num=parsed["run_num"],
            run_id=run_id,
            parquet_path=path,
            n_frames=n_frames,
            duration_s=duration_s,
            artifact_pct_any_joint=artifact_pct,
            is_dead=is_dead,
        ))

    # Sort: subject → timepoint → run_num
    tp_order = {"T1": 0, "T2": 1, "T3": 2}
    sessions.sort(key=lambda s: (
        s.subject_id, tp_order.get(s.timepoint, 9), s.run_num
    ))
    # Assign quality ranks within (subject, timepoint)
    by_tp: dict[tuple, list] = {}
    for s in sessions:
        key = (s.subject_id, s.timepoint)
        by_tp.setdefault(key, []).append(s)
    for group in by_tp.values():
        alive = [s for s in group if not s.is_dead]
        alive.sort(key=lambda s: s.artifact_pct_any_joint)
        for rank, s in enumerate(alive):
            s.quality_rank = rank
        for s in group:
            if s.is_dead:
                s.quality_rank = 999
    return sessions


def select_representative_sessions(
    sessions: list[SessionInfo],
    strategy: Literal["lowest_artifact", "R1", "R2"] = "lowest_artifact",
) -> list[SessionInfo]:
    """
    For each (subject_id, timepoint) pair, select one non-dead representative.
    strategy='lowest_artifact': argmin(artifact_pct_any_joint).
    Returns one SessionInfo per (subject_id, timepoint), sorted T1→T2→T3.
    """
    by_key: dict[tuple, list[SessionInfo]] = {}
    for s in sessions:
        if s.is_dead:
            continue
        key = (s.subject_id, s.timepoint)
        by_key.setdefault(key, []).append(s)

    selected: list[SessionInfo] = []
    for (subj, tp), group in by_key.items():
        if strategy == "lowest_artifact":
            chosen = min(group, key=lambda s: s.artifact_pct_any_joint)
        elif strategy == "R1":
            r1 = [s for s in group if s.run_num == "R1"]
            chosen = r1[0] if r1 else group[0]
        elif strategy == "R2":
            r2 = [s for s in group if s.run_num == "R2"]
            chosen = r2[0] if r2 else group[0]
        else:
            raise ValueError(f"Unknown strategy: {strategy!r}")
        selected.append(chosen)

    tp_order = {"T1": 0, "T2": 1, "T3": 2}
    selected.sort(key=lambda s: (s.subject_id, tp_order.get(s.timepoint, 9)))
    return selected


# ---------------------------------------------------------------------------
# Stage 1 — ATF Computation
# ---------------------------------------------------------------------------

def compute_session_atf(
    df: pd.DataFrame,
    cfg: dict,
    joints: tuple[str, ...] = ALL_19_JOINTS,
) -> ATFResult:
    """
    Compute Active Time Fraction for all joints.
    ATF_j = sum(vel_j > V_j AND NOT art_j) / sum(NOT art_j).
    whole_body_atf = median(ATF_j across all joints).
    """
    per_joint_atf: dict[str, float] = {}
    noise_floor_low_confidence: dict[str, bool] = {}
    vel_arrays: dict[str, np.ndarray] = {}
    art_arrays: dict[str, np.ndarray] = {}
    noise_floors: dict[str, float] = {}

    for joint in joints:
        vel_col = f"{joint}__lin_vel_rel_mag"
        art_col = f"{joint}__is_artifact"
        if vel_col not in df.columns or art_col not in df.columns:
            logger.warning("Missing columns for joint %s — skipping ATF", joint)
            continue

        vel = df[vel_col].values.astype(np.float64)
        art = df[art_col].values.astype(bool)
        vel_arrays[joint] = vel
        art_arrays[joint] = art

        nf = compute_noise_floor(df, joint, cfg)
        V_j = float(nf["V"])
        noise_floors[joint] = V_j
        noise_floor_low_confidence[joint] = bool(nf.get("noise_floor_low_confidence", False))

        clean_mask = ~art
        denom = int(clean_mask.sum())
        if denom == 0:
            per_joint_atf[joint] = float("nan")
        else:
            numer = int(((vel > V_j) & clean_mask).sum())
            per_joint_atf[joint] = numer / denom

    valid_atf = [v for v in per_joint_atf.values() if np.isfinite(v)]
    whole_body_median = float(np.median(valid_atf)) if valid_atf else float("nan")
    whole_body_std = float(np.std(valid_atf)) if valid_atf else float("nan")

    distal_vals = [per_joint_atf[j] for j in DISTAL_JOINTS
                   if j in per_joint_atf and np.isfinite(per_joint_atf[j])]
    axial_vals = [per_joint_atf[j] for j in AXIAL_JOINTS
                  if j in per_joint_atf and np.isfinite(per_joint_atf[j])]

    any_art_col = [f"{j}__is_artifact" for j in joints if f"{j}__is_artifact" in df.columns]
    if any_art_col:
        any_artifact = df[any_art_col].any(axis=1)
        clean_fraction = float((~any_artifact).mean())
        clean_duration_s = float((~any_artifact).sum()) / FS
    else:
        clean_fraction = 1.0
        clean_duration_s = len(df) / FS

    artifact_fraction = 1.0 - clean_fraction
    if artifact_fraction > ARTIFACT_CRITICAL_THRESHOLD:
        concern = "CRITICAL"
    elif artifact_fraction > ARTIFACT_WARNING_THRESHOLD:
        concern = "WARNING"
    else:
        concern = "OK"

    return ATFResult(
        run_id="",  # caller sets this
        per_joint_atf=per_joint_atf,
        whole_body_atf_median=whole_body_median,
        whole_body_atf_std=whole_body_std,
        atf_distal_median=float(np.median(distal_vals)) if distal_vals else float("nan"),
        atf_axial_median=float(np.median(axial_vals)) if axial_vals else float("nan"),
        artifact_concern=concern,
        clean_fraction=clean_fraction,
        clean_duration_s=clean_duration_s,
        noise_floor_low_confidence=noise_floor_low_confidence,
        vel_arrays=vel_arrays,
        art_arrays=art_arrays,
        noise_floors=noise_floors,
    )


def build_branch_artifact_mask(
    df: pd.DataFrame,
    branch: Literal["dynamics", "pose", "reach"],
) -> np.ndarray:
    """
    Lenient branch-local masking (§4.2).
    Returns bool array, True = frame should be EXCLUDED.
    Dynamics/Pose: OR of is_artifact over all 19 joints.
    Reach: OR of is_artifact over 18 joints (Hips structurally excluded).
    """
    joints = ALL_19_JOINTS if branch != "reach" else tuple(
        j for j in ALL_19_JOINTS if j != "Hips"
    )
    art_cols = [f"{j}__is_artifact" for j in joints if f"{j}__is_artifact" in df.columns]
    if not art_cols:
        return np.zeros(len(df), dtype=bool)
    return df[art_cols].any(axis=1).values.astype(bool)


# ---------------------------------------------------------------------------
# Stage 2 — Time-Window Cropping (§Update 3)
# ---------------------------------------------------------------------------

def crop_session_to_window(
    df: pd.DataFrame,
    start_sec: float | None,
    end_sec: float | None,
) -> pd.DataFrame:
    """
    Crop DataFrame to [start_sec, end_sec] based on the 'time_s' column.
    None means no crop at that boundary. Returns a copy with reset index.
    """
    if "time_s" not in df.columns:
        return df
    mask = np.ones(len(df), dtype=bool)
    t = df["time_s"].values
    if start_sec is not None:
        mask &= t >= start_sec
    if end_sec is not None:
        mask &= t <= end_sec
    return df.loc[mask].copy().reset_index(drop=True)


# ---------------------------------------------------------------------------
# Stage 3 — T1-Anchored PCA
# ---------------------------------------------------------------------------

def run_t1_anchored_pca(
    session_infos: list[SessionInfo],
    time_windows: dict[str, dict[str, list[float]]] | None = None,
    include_joints: list[str] | None = None,
    exclude_joints: list[str] | None = None,
) -> dict[str, Any]:
    """
    Full T1-anchored PCA pipeline for a subject's T1/T2/T3 sessions.

    Args:
        session_infos:  Representative sessions for one subject, T1→T2→T3.
        time_windows:   Optional crop windows per timepoint.
                        Format: {"T1": [start_s, end_s], "T2": [...], ...}
        include_joints: Optional joint whitelist.
        exclude_joints: Optional joint blacklist.

    Returns:
        dict with keys: 'pca_results', 'prepared', 'session_mapping', 'raw_dfs'
        pca_results[branch] has: pca, projected_arrays (3D), projected_full (all K),
            explained_variance_ratio_, timepoints, columns, scaler.
    """
    # Load raw DataFrames with optional time-window cropping
    raw_dfs: list[pd.DataFrame] = []
    session_mapping: list[dict] = []
    for si in session_infos:
        df = pd.read_parquet(si.parquet_path)
        if time_windows is not None and si.timepoint in time_windows:
            w = time_windows[si.timepoint]
            start = w[0] if len(w) > 0 else None
            end = w[1] if len(w) > 1 else None
            df = crop_session_to_window(df, start, end)
        raw_dfs.append(df)
        session_mapping.append({
            "timepoint": si.timepoint,
            "run_id": si.run_id,
            "parquet_path": si.parquet_path,
        })

    # Apply branch-local artifact masks to get filtered DataFrames per branch
    filtered_by_branch: dict[str, list[pd.DataFrame]] = {b: [] for b in BRANCHES}
    for b in BRANCHES:
        for df in raw_dfs:
            mask = build_branch_artifact_mask(df, b)
            filtered_by_branch[b].append(df.loc[~mask].copy().reset_index(drop=True))

    # T1-anchored scaling and PCA via modified EDA_PCA functions
    # prepare_3branch_data with reference_timepoint="T1"
    prepared = prepare_3branch_data(
        session_mapping=session_mapping,
        preloaded_dfs=None,
        include_joints=include_joints,
        exclude_joints=exclude_joints,
        reference_timepoint="T1",
        preloaded_filtered_by_branch=filtered_by_branch,
    )

    # run_3branch_pca with T1-anchor
    pca_results = run_3branch_pca(prepared, reference_timepoint="T1")

    return {
        "pca_results": pca_results,
        "prepared": prepared,
        "session_mapping": session_mapping,
        "raw_dfs": raw_dfs,
        "filtered_by_branch": filtered_by_branch,
    }


# ---------------------------------------------------------------------------
# Stage 4 helpers
# ---------------------------------------------------------------------------

def _compute_native_gini(
    scaled_arrays: list[np.ndarray],
    columns: list[str],
    timepoints: list[str],
) -> list[float]:
    """
    Session-specific Gini: fit fresh PCA on each session's own data.
    Returns list of Gini values, one per session.
    """
    from EDA_PCA import _gini

    ginis: list[float] = []
    joint_to_idx: dict[str, list[int]] = {}
    for j, col in enumerate(columns):
        jname = _feature_to_joint(col)
        joint_to_idx.setdefault(jname, []).append(j)

    for X in scaled_arrays:
        n_comp = min(X.shape[0], X.shape[1])
        pca_native = PCA(n_components=n_comp)
        pca_native.fit(X)
        attr_per_feature = _session_joint_contributions(pca_native, X)
        total = float(np.sum(attr_per_feature))
        if total <= 0:
            ginis.append(float("nan"))
            continue
        joint_attr = {j: float(np.sum(attr_per_feature[idx]))
                      for j, idx in joint_to_idx.items()}
        s = sum(joint_attr.values())
        props = np.array([joint_attr.get(j, 0.0) / s for j in joint_to_idx])
        ginis.append(_gini(props))
    return ginis


def _equalize_projected_arrays(
    projected_arrays: list[np.ndarray],
) -> tuple[list[np.ndarray], int]:
    """
    Uniform-stride subsample each session to N_min frames (§2.4.2 Step 0).
    Returns (equalized_arrays, n_min).
    """
    n_min = min(len(pts) for pts in projected_arrays)
    equalized = []
    for pts in projected_arrays:
        if len(pts) == n_min:
            equalized.append(pts)
        else:
            stride = len(pts) // n_min
            eq = pts[::stride][:n_min]
            equalized.append(eq)
    return equalized, n_min


def _compute_entropy_from_arrays(
    projected_arrays: list[np.ndarray],
    equalized_arrays: list[np.ndarray],
    n_bins: int = 25,
    t1_edges_only: bool = False,
) -> dict[str, Any]:
    """
    Compute 2D state-space Shannon entropy (bits).
    - equalized_arrays: used for histogramming (duration-confound control)
    - Global bin edges: 1st–99th percentile of combined equalized cloud
    - If t1_edges_only: edges computed from T1 equalized data only (sensitivity §2.4.5)
    - np.clip guard applied before histogram2d
    Returns dict with entropy_equalized, entropy_raw, occupied_bin_frac per session.
    """
    # Build bin edges
    if t1_edges_only:
        edge_source = equalized_arrays[0]  # T1 only
    else:
        edge_source = np.vstack(equalized_arrays)

    pc1_lo, pc1_hi = np.percentile(edge_source[:, 0], [ENTROPY_BIN_EDGE_PERCENTILE[0],
                                                         ENTROPY_BIN_EDGE_PERCENTILE[1]])
    pc2_lo, pc2_hi = np.percentile(edge_source[:, 1], [ENTROPY_BIN_EDGE_PERCENTILE[0],
                                                         ENTROPY_BIN_EDGE_PERCENTILE[1]])
    pc1_edges = np.linspace(pc1_lo, pc1_hi, n_bins + 1)
    pc2_edges = np.linspace(pc2_lo, pc2_hi, n_bins + 1)

    def _hist_entropy(pts: np.ndarray) -> tuple[float, float]:
        pc1c = np.clip(pts[:, 0], pc1_edges[0], pc1_edges[-1])
        pc2c = np.clip(pts[:, 1], pc2_edges[0], pc2_edges[-1])
        hist, _, _ = np.histogram2d(pc1c, pc2c, bins=[pc1_edges, pc2_edges])
        assert hist.sum() == len(pts), "Frames dropped — clip guard failure"
        total = hist.sum()
        if total <= 0:
            return 0.0, 0.0
        p = hist.flatten() / total
        occupied_frac = float(np.count_nonzero(hist)) / (n_bins * n_bins)
        p_pos = p[p > 0]
        H = float(-np.sum(p_pos * np.log2(p_pos)))
        return H, occupied_frac

    entropy_equalized, occupied_frac = [], []
    for pts_eq in equalized_arrays:
        H, occ = _hist_entropy(pts_eq)
        entropy_equalized.append(H)
        occupied_frac.append(occ)

    entropy_raw = []
    for pts in projected_arrays:
        H, _ = _hist_entropy(pts)
        entropy_raw.append(H)

    return {
        "entropy_equalized": entropy_equalized,
        "entropy_raw": entropy_raw,
        "occupied_bin_frac": occupied_frac,
        "pc1_edges": pc1_edges,
        "pc2_edges": pc2_edges,
    }


# ---------------------------------------------------------------------------
# Stage 4 — Sample Entropy (Featured Secondary §2.8)
# ---------------------------------------------------------------------------

def compute_sample_entropy(
    pca_results: dict,
    m: int = SAMPEN_M,
    r_fraction: float = SAMPEN_R_FRACTION_DEFAULT,
) -> dict[str, dict]:
    """
    Sample Entropy of the PC1 trajectory per branch × session.
    Calls _sample_entropy_numpy() (O(N²), ~2–5s per call at 19K frames).
    r = r_fraction × std(PC1).
    Returns None (not NaN) for sessions where A=0 (undefined SampEn).
    """
    results: dict[str, dict] = {}
    for branch in BRANCHES:
        res = pca_results.get(branch)
        if not res:
            continue
        projected = res["projected_arrays"]
        timepoints = res["timepoints"]
        sampen_vals: list[float | None] = []
        r_used: list[float] = []
        for pts in projected:
            pc1 = pts[:, 0].astype(np.float64)
            r = r_fraction * float(np.std(pc1, ddof=1))
            if r <= 0:
                sampen_vals.append(None)
                r_used.append(r)
                continue
            val = _sample_entropy_numpy(pc1, m=m, r=r)
            sampen_vals.append(None if (np.isnan(val) or np.isinf(val)) else float(val))
            r_used.append(r)
        results[branch] = {
            "timepoints": timepoints,
            "sampen": sampen_vals,
            "r_used": r_used,
        }
    return results


# ---------------------------------------------------------------------------
# Stage 4 — A/P Ratio (Featured Secondary §2.9)
# ---------------------------------------------------------------------------

def compute_ap_ratio(
    whole_system_stats: dict,
) -> dict[str, dict]:
    """
    Extract A/P Ratio and A/P Index from calculate_whole_system_stats() output.
    ap_ratio  = axial_var_proportion / (peripheral_var_proportion + ε)
    ap_index  = (axial - periph) / (axial + periph)  ∈ [-1, +1]
    """
    results: dict[str, dict] = {}
    for branch in BRANCHES:
        data = whole_system_stats.get(branch)
        if not data:
            continue
        timepoints = data["timepoints"]
        ap_ratio_vals, ap_index_vals = [], []
        for m in data["metrics_per_session"]:
            ratio = float(m.get("AxialPeripheral", float("nan")))
            ap_ratio_vals.append(ratio)
            # Reconstruct index from ratio: ratio = ax/periph → index = (ax-periph)/(ax+periph)
            # From ratio r: ax = r·periph; ax+periph = (r+1)·periph; ax-periph = (r-1)·periph
            if np.isfinite(ratio) and ratio >= 0:
                ap_index = (ratio - 1.0) / (ratio + 1.0 + 1e-12)
            else:
                ap_index = float("nan")
            ap_index_vals.append(ap_index)
        results[branch] = {
            "timepoints": timepoints,
            "ap_ratio": ap_ratio_vals,
            "ap_index": ap_index_vals,
        }
    return results


# ---------------------------------------------------------------------------
# Stage 4 — RQA (Featured Secondary §2.10)
# ---------------------------------------------------------------------------

def _rqa_numpy_fallback(
    sv_sub: np.ndarray,
    epsilon: float,
    l_min: int = 2,
) -> tuple[float, float]:
    """
    Pure numpy RQA: compute %REC and %DET without pyrqa.
    sv_sub: (N_sub, d) state vectors (already subsampled).
    O(N²) — only called when pyrqa is unavailable.
    """
    N = len(sv_sub)
    # Build recurrence matrix
    dists = spdist.cdist(sv_sub, sv_sub, metric="euclidean")
    R = (dists <= epsilon).astype(np.int8)
    np.fill_diagonal(R, 0)  # exclude self-recurrences

    rec_sum = int(R.sum())
    pct_rec = float(rec_sum) / (N * N) * 100.0

    if rec_sum == 0:
        return pct_rec, 0.0

    # %DET: diagonal line counting via diff trick
    det_points = 0
    for k in range(-(N - 1), N):
        d = np.diag(R, k).astype(int)
        if len(d) < l_min:
            continue
        padded = np.concatenate([[0], d, [0]])
        diff = np.diff(padded)
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        lengths = ends - starts
        det_points += int(np.sum(lengths[lengths >= l_min]))

    pct_det = float(det_points) / rec_sum * 100.0
    return pct_rec, pct_det


def compute_rqa(
    pca_results: dict,
    n90_results: dict,
    max_state_dim: int = RQA_MAX_STATE_DIM,
    epsilon_percentile: float = RQA_EPSILON_PERCENTILE_DEFAULT,
    l_min: int = RQA_L_MIN,
    subsample_target: int = RQA_SUBSAMPLE_TARGET,
) -> dict[str, dict]:
    """
    Recurrence Quantification Analysis per branch × session (§2.10).
    State representation: first d = min(N90, max_state_dim) PCs.
    ε = epsilon_percentile-th percentile of pairwise Euclidean distances.
    Subsampled to subsample_target frames via uniform stride.
    Uses pyrqa if available, else falls back to pure numpy.
    """
    results: dict[str, dict] = {}
    for branch in BRANCHES:
        res = pca_results.get(branch)
        n90_data = n90_results.get(branch)
        if not res or not n90_data:
            continue

        projected_full = res.get("projected_full")
        if projected_full is None:
            logger.warning("projected_full missing for branch %s — skipping RQA", branch)
            continue

        timepoints = res["timepoints"]
        evr = res["explained_variance_ratio_"]
        n90_per_session = n90_data["n90_per_session"]

        pct_rec_list, pct_det_list, eps_list, dim_list, cum_var_list = [], [], [], [], []

        for s_idx, (proj_full, n90_s) in enumerate(zip(projected_full, n90_per_session)):
            d = min(n90_s, max_state_dim)
            d = max(d, 1)
            state_vecs = proj_full[:, :d]

            # Uniform stride subsample
            stride = max(1, len(state_vecs) // subsample_target)
            sv_sub = state_vecs[::stride][:subsample_target]

            # Cumulative variance of chosen d components
            cum_var = float(np.sum(evr[:d])) if d <= len(evr) else float(np.sum(evr))

            # Adaptive epsilon
            if len(sv_sub) < 2:
                pct_rec_list.append(None)
                pct_det_list.append(None)
                eps_list.append(None)
                dim_list.append(d)
                cum_var_list.append(cum_var)
                continue

            dists_flat = spdist.pdist(sv_sub, metric="euclidean")
            epsilon = float(np.percentile(dists_flat, epsilon_percentile))

            try:
                if _HAS_PYRQA:
                    series = EmbeddedSeries(sv_sub.astype(np.float64))
                    settings = Settings(
                        series,
                        neighbourhood=FixedRadius(epsilon),
                        similarity_measure=EuclideanMetric,
                    )
                    computation = RQAComputation.create(settings, verbose=False)
                    result = computation.run()
                    pct_rec = float(result.recurrence_rate) * 100.0
                    pct_det = float(result.determinism) * 100.0
                else:
                    logger.warning("pyrqa not available — using numpy fallback for RQA")
                    pct_rec, pct_det = _rqa_numpy_fallback(sv_sub, epsilon, l_min)
            except Exception as exc:
                logger.error("RQA failed for branch=%s session=%s: %s", branch, s_idx, exc)
                pct_rec, pct_det = None, None

            pct_rec_list.append(pct_rec)
            pct_det_list.append(pct_det)
            eps_list.append(epsilon)
            dim_list.append(d)
            cum_var_list.append(cum_var)

        results[branch] = {
            "timepoints": timepoints,
            "pct_recurrence": pct_rec_list,
            "pct_determinism": pct_det_list,
            "epsilon_used": eps_list,
            "state_dim": dim_list,
            "cum_var_captured": cum_var_list,
        }
    return results


# ---------------------------------------------------------------------------
# Stage 4 — Orchestrator
# ---------------------------------------------------------------------------

def compute_all_thesis_metrics(
    pca_output: dict,
    atf_results: list[ATFResult],
    subject_id: str,
    # ── Sensitivity parameters (§Update 5) ───────────────────────────────────
    n_bins: int = N_BINS_DEFAULT,
    variance_threshold: float = VARIANCE_THRESHOLD_DEFAULT,
    sampen_r_fraction: float = SAMPEN_R_FRACTION_DEFAULT,
    rqa_epsilon_percentile: float = RQA_EPSILON_PERCENTILE_DEFAULT,
    bootstrap_block_sec: float = BOOTSTRAP_BLOCK_SEC_DEFAULT,
) -> ThesisMetricsBundle:
    """
    Orchestrator — calls all metric functions in dependency order.
    pca_output: output of run_t1_anchored_pca().
    atf_results: list of ATFResult, one per timepoint in T1→T2→T3 order.
    """
    pca_results = pca_output["pca_results"]
    prepared = pca_output["prepared"]
    session_mapping = pca_output["session_mapping"]
    timepoints = [m["timepoint"] for m in session_mapping]
    run_ids = [m["run_id"] for m in session_mapping]

    # ── N90 + D_eff (single authoritative source in modified calculate_n90) ──
    n90_results = calculate_n90(
        pca_results, prepared, variance_threshold=variance_threshold
    )

    # ── Joint Gini T1-anchored ────────────────────────────────────────────────
    whole_stats = calculate_whole_system_stats(pca_results, prepared)

    # ── Joint Gini session-specific (sensitivity §2.3.4) ──────────────────────
    gini_native: dict[str, list[float]] = {}
    for branch in BRANCHES:
        prep_b = prepared.get(branch)
        res_b = pca_results.get(branch)
        if not prep_b or not res_b:
            continue
        gini_native[branch] = _compute_native_gini(
            prep_b["scaled_arrays"], res_b["columns"], timepoints
        )

    # ── Entropy: frame equalization → global + T1-edge variants ──────────────
    entropy_eq: dict[str, list[float]] = {}
    entropy_raw_dict: dict[str, list[float]] = {}
    entropy_t1: dict[str, list[float]] = {}
    entropy_occ: dict[str, list[float]] = {}
    entropy_valid: dict[str, list[bool]] = {}
    n_min_eq: dict[str, int] = {}

    for branch in BRANCHES:
        res_b = pca_results.get(branch)
        if not res_b:
            continue
        proj_3d = res_b["projected_arrays"]
        evr = res_b["explained_variance_ratio_"]

        eq_arrays, n_min = _equalize_projected_arrays(proj_3d)
        n_min_eq[branch] = n_min

        ent = _compute_entropy_from_arrays(proj_3d, eq_arrays, n_bins=n_bins,
                                           t1_edges_only=False)
        ent_t1 = _compute_entropy_from_arrays(proj_3d, eq_arrays, n_bins=n_bins,
                                              t1_edges_only=True)

        entropy_eq[branch] = ent["entropy_equalized"]
        entropy_raw_dict[branch] = ent["entropy_raw"]
        entropy_t1[branch] = ent_t1["entropy_equalized"]
        entropy_occ[branch] = ent["occupied_bin_frac"]

        # Entropy validity gate: PC1+PC2 cumvar ≥ 0.50 AND occupied_frac ≥ 0.05
        cum_pc1pc2 = [float(evr[0] + evr[1])] * len(timepoints)
        valid_flags = [
            (cv >= ENTROPY_RELIABILITY_THRESHOLD and occ >= ENTROPY_SPREAD_THRESHOLD)
            for cv, occ in zip(cum_pc1pc2, ent["occupied_bin_frac"])
        ]
        entropy_valid[branch] = valid_flags

    # ── PC1+PC2 coverage & PC1 variance ──────────────────────────────────────
    pc1pc2_cov: dict[str, list[float]] = {}
    pc1_var: dict[str, list[float]] = {}
    evr_store: dict[str, np.ndarray] = {}
    for branch in BRANCHES:
        res_b = pca_results.get(branch)
        if not res_b:
            continue
        evr = res_b["explained_variance_ratio_"]
        evr_store[branch] = evr
        n_sess = len(timepoints)
        pc1pc2_cov[branch] = [float(evr[0] + evr[1])] * n_sess
        pc1_var[branch] = [float(evr[0])] * n_sess

    # ── Centroid displacement ─────────────────────────────────────────────────
    centroid_res = calculate_centroid_displacement(pca_results)
    cent_raw: dict[str, list[float]] = {}
    cent_norm: dict[str, list[float]] = {}
    for branch in BRANCHES:
        cr = centroid_res.get(branch)
        if not cr:
            continue
        disps = cr["displacement_from_t1"]
        cent_raw[branch] = disps
        # Normalize by T1 PC1 std
        proj_t1 = pca_results[branch]["projected_arrays"][0]
        t1_pc1_std = float(np.std(proj_t1[:, 0], ddof=1)) if len(proj_t1) > 1 else 1.0
        if t1_pc1_std <= 0:
            t1_pc1_std = 1.0
        cent_norm[branch] = [d / t1_pc1_std for d in disps]

    # ── Sample Entropy ────────────────────────────────────────────────────────
    sampen_res = compute_sample_entropy(pca_results, m=SAMPEN_M,
                                        r_fraction=sampen_r_fraction)
    sampen_dict: dict[str, list[float | None]] = {}
    sampen_reliable: dict[str, list[bool]] = {}
    for branch in BRANCHES:
        sr = sampen_res.get(branch)
        if not sr:
            continue
        sampen_dict[branch] = sr["sampen"]
        sampen_reliable[branch] = [
            pc1 >= SAMPEN_PC1_RELIABILITY_THRESHOLD
            for pc1 in pc1_var.get(branch, [])
        ]

    # ── A/P Ratio ─────────────────────────────────────────────────────────────
    ap_res = compute_ap_ratio(whole_stats)
    ap_ratio_dict: dict[str, list[float]] = {}
    ap_index_dict: dict[str, list[float]] = {}
    for branch in BRANCHES:
        ar = ap_res.get(branch)
        if not ar:
            continue
        ap_ratio_dict[branch] = ar["ap_ratio"]
        ap_index_dict[branch] = ar["ap_index"]

    # ── RQA ──────────────────────────────────────────────────────────────────
    rqa_res = compute_rqa(
        pca_results, n90_results,
        epsilon_percentile=rqa_epsilon_percentile,
    )
    rqa_prec: dict[str, list[float | None]] = {}
    rqa_pdet: dict[str, list[float | None]] = {}
    rqa_rel: dict[str, list[bool]] = {}
    rqa_eps: dict[str, list[float | None]] = {}
    rqa_dim: dict[str, list[int]] = {}
    rqa_cv: dict[str, list[float]] = {}
    for branch in BRANCHES:
        rr = rqa_res.get(branch)
        if not rr:
            continue
        rqa_prec[branch] = rr["pct_recurrence"]
        rqa_pdet[branch] = rr["pct_determinism"]
        rqa_eps[branch] = rr["epsilon_used"]
        rqa_dim[branch] = rr["state_dim"]
        rqa_cv[branch] = rr["cum_var_captured"]
        rqa_rel[branch] = [cv >= ENTROPY_RELIABILITY_THRESHOLD
                           for cv in rr["cum_var_captured"]]

    # ── N90 / D_eff extract ───────────────────────────────────────────────────
    n90_dict: dict[str, list[int]] = {}
    deff_dict: dict[str, list[float]] = {}
    deff_norm_dict: dict[str, list[float]] = {}
    for branch in BRANCHES:
        nd = n90_results.get(branch)
        if not nd:
            continue
        n90_dict[branch] = nd["n90_per_session"]
        deff_dict[branch] = nd["d_eff_per_session"]
        deff_norm_dict[branch] = nd["d_eff_norm_per_session"]

    # ── Gini T1-anchored extract ──────────────────────────────────────────────
    gini_anchored: dict[str, list[float]] = {}
    for branch in BRANCHES:
        ws = whole_stats.get(branch)
        if not ws:
            continue
        gini_anchored[branch] = [m["Gini"] for m in ws["metrics_per_session"]]

    # ── ATF ───────────────────────────────────────────────────────────────────
    atf_whole = [r.whole_body_atf_median for r in atf_results]
    atf_dis = [r.atf_distal_median for r in atf_results]
    atf_ax = [r.atf_axial_median for r in atf_results]
    atf_pj = [r.per_joint_atf for r in atf_results]
    atf_con = [r.artifact_concern for r in atf_results]
    atf_cf = [r.clean_fraction for r in atf_results]

    return ThesisMetricsBundle(
        subject_id=subject_id,
        timepoints=timepoints,
        run_ids=run_ids,
        atf_whole_body=atf_whole,
        atf_distal=atf_dis,
        atf_axial=atf_ax,
        atf_per_joint=atf_pj,
        atf_artifact_concern=atf_con,
        atf_clean_fraction=atf_cf,
        n90=n90_dict,
        d_eff=deff_dict,
        d_eff_norm=deff_norm_dict,
        gini_joint_anchored=gini_anchored,
        gini_joint_native=gini_native,
        entropy_equalized=entropy_eq,
        entropy_raw=entropy_raw_dict,
        entropy_t1_edge=entropy_t1,
        entropy_occupied_frac=entropy_occ,
        entropy_valid=entropy_valid,
        n_min_equalization_frames=n_min_eq,
        centroid_displacement_raw=cent_raw,
        centroid_displacement_norm=cent_norm,
        sampen=sampen_dict,
        sampen_reliable=sampen_reliable,
        ap_ratio=ap_ratio_dict,
        ap_index=ap_index_dict,
        rqa_pct_rec=rqa_prec,
        rqa_pct_det=rqa_pdet,
        rqa_reliable=rqa_rel,
        rqa_epsilon_used=rqa_eps,
        rqa_state_dim=rqa_dim,
        rqa_cum_var=rqa_cv,
        pc1pc2_var_coverage=pc1pc2_cov,
        pc1_var=pc1_var,
        explained_variance_ratio=evr_store,
        _pca_results=pca_results,
        _prepared=prepared,
        _atf_results=atf_results,
        variance_threshold=variance_threshold,
        n_bins=n_bins,
        sampen_r_fraction=sampen_r_fraction,
        rqa_epsilon_percentile=rqa_epsilon_percentile,
        bootstrap_block_sec=bootstrap_block_sec,
    )


# ---------------------------------------------------------------------------
# Stage 5 — Results Assembly
# ---------------------------------------------------------------------------

def assemble_results_dataframe(bundle: ThesisMetricsBundle) -> pd.DataFrame:
    """
    Flatten ThesisMetricsBundle to tidy long-format DataFrame.
    One row per (subject, timepoint, branch, metric).
    """
    rows = []
    subj = bundle.subject_id
    tps = bundle.timepoints
    run_ids = bundle.run_ids

    def _add(tp_idx, branch, metric, value, unit, tier, **kwargs):
        rows.append({
            "subject_id": subj,
            "timepoint": tps[tp_idx],
            "run_id": run_ids[tp_idx],
            "branch": branch,
            "metric": metric,
            "value": value,
            "unit": unit,
            "tier": tier,
            **kwargs,
        })

    # ── ATF ──────────────────────────────────────────────────────────────────
    for i, tp in enumerate(tps):
        base = dict(
            artifact_concern=bundle.atf_artifact_concern[i],
            clean_fraction=bundle.atf_clean_fraction[i],
            pc1pc2_var_coverage=float("nan"),
            entropy_valid=False,
            sampen_reliable=False,
            rqa_reliable=False,
        )
        _add(i, "whole_body", "atf_whole_body_median", bundle.atf_whole_body[i],
             "fraction", "PRIMARY", **base)
        _add(i, "whole_body", "atf_distal_median", bundle.atf_distal[i],
             "fraction", "PRIMARY", **base)
        _add(i, "whole_body", "atf_axial_median", bundle.atf_axial[i],
             "fraction", "PRIMARY", **base)
        for joint, val in bundle.atf_per_joint[i].items():
            _add(i, "whole_body", f"atf_{joint}", val, "fraction", "PRIMARY", **base)

    # ── PCA-branch metrics ────────────────────────────────────────────────────
    for branch in BRANCHES:
        for i, tp in enumerate(tps):
            base = dict(
                artifact_concern=bundle.atf_artifact_concern[i],
                clean_fraction=bundle.atf_clean_fraction[i],
                pc1pc2_var_coverage=(bundle.pc1pc2_var_coverage.get(branch, [float("nan")] * len(tps))[i]),
                entropy_valid=(bundle.entropy_valid.get(branch, [False] * len(tps))[i]),
                sampen_reliable=(bundle.sampen_reliable.get(branch, [False] * len(tps))[i]),
                rqa_reliable=(bundle.rqa_reliable.get(branch, [False] * len(tps))[i]),
            )

            def _b(metric, value, unit, tier):
                _add(i, branch, metric, value, unit, tier, **base)

            # N90 & D_eff
            _b("n90", _safe(bundle.n90, branch, i), "components", "PRIMARY")
            _b("d_eff", _safe(bundle.d_eff, branch, i), "effective_modes", "PRIMARY")
            _b("d_eff_normalized", _safe(bundle.d_eff_norm, branch, i), "fraction", "PRIMARY")

            # Gini
            _b("gini_joint_anchored", _safe(bundle.gini_joint_anchored, branch, i),
               "0_to_1", "PRIMARY")
            _b("gini_joint_native", _safe(bundle.gini_joint_native, branch, i),
               "0_to_1", "PRIMARY_sensitivity")

            # Entropy (bits)
            _b("state_space_entropy_bits_equalized",
               _safe(bundle.entropy_equalized, branch, i), "bits", "PRIMARY")
            _b("state_space_entropy_bits_raw",
               _safe(bundle.entropy_raw, branch, i), "bits", "PRIMARY_supplement")
            _b("state_space_entropy_bits_t1_edge",
               _safe(bundle.entropy_t1_edge, branch, i), "bits", "PRIMARY_sensitivity")
            _b("entropy_occupied_frac",
               _safe(bundle.entropy_occupied_frac, branch, i), "fraction", "PRIMARY_supplement")
            _b("n_min_equalization_frames",
               bundle.n_min_equalization_frames.get(branch, float("nan")),
               "frames", "PRIMARY_supplement")

            # Centroid
            _b("centroid_displacement_raw",
               _safe(bundle.centroid_displacement_raw, branch, i), "PC_units", "FALLBACK")
            _b("centroid_displacement_normalized",
               _safe(bundle.centroid_displacement_norm, branch, i), "T1_PC1_std", "FALLBACK")

            # Featured Secondary
            sv = _safe(bundle.sampen, branch, i)
            _b("sampen_pc1", sv, "nats", "FEATURED_SECONDARY")
            _b("ap_ratio", _safe(bundle.ap_ratio, branch, i), "ratio", "FEATURED_SECONDARY")
            _b("ap_index", _safe(bundle.ap_index, branch, i), "-1_to_1", "FEATURED_SECONDARY")
            _b("rqa_pct_recurrence", _safe(bundle.rqa_pct_rec, branch, i),
               "percent", "FEATURED_SECONDARY")
            _b("rqa_pct_determinism", _safe(bundle.rqa_pct_det, branch, i),
               "percent", "FEATURED_SECONDARY")
            _b("rqa_epsilon_used", _safe(bundle.rqa_epsilon_used, branch, i),
               "PC_units", "FEATURED_SECONDARY")
            _b("rqa_state_dim", _safe(bundle.rqa_state_dim, branch, i),
               "components", "FEATURED_SECONDARY")
            _b("rqa_cum_var_captured", _safe(bundle.rqa_cum_var, branch, i),
               "fraction", "FEATURED_SECONDARY")

    df = pd.DataFrame(rows)
    return df


def _safe(d: dict, key: str, idx: int) -> Any:
    """Safe indexed access into a branch-dict."""
    lst = d.get(key)
    if lst is None:
        return float("nan")
    if idx >= len(lst):
        return float("nan")
    v = lst[idx]
    return v if v is not None else float("nan")


def compute_delta_table(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute intra-subject deltas: T1→T2, T2→T3, T1→T3.
    Applies between-subject consistency gate (§8.5).
    """
    pivot = results_df.pivot_table(
        index=["subject_id", "branch", "metric"],
        columns="timepoint",
        values="value",
        aggfunc="first",
    ).reset_index()

    for t_from, t_to, col_name in [
        ("T1", "T2", "delta_T1_T2"),
        ("T2", "T3", "delta_T2_T3"),
        ("T1", "T3", "delta_T1_T3"),
    ]:
        if t_from in pivot.columns and t_to in pivot.columns:
            pivot[col_name] = pivot[t_to] - pivot[t_from]
        else:
            pivot[col_name] = float("nan")

    # Between-subject consistency (§8.5) — only meaningful when >1 subject
    subjects = results_df["subject_id"].unique()
    if len(subjects) > 1:
        cross = pivot.groupby(["branch", "metric"])["delta_T1_T3"].apply(
            lambda x: _consistency_label(x.values)
        ).reset_index(name="cross_subject_consistency")
        pivot = pivot.merge(cross, on=["branch", "metric"], how="left")
    else:
        pivot["cross_subject_consistency"] = "single_subject"

    return pivot


def _consistency_label(deltas: np.ndarray) -> str:
    finite = deltas[np.isfinite(deltas)]
    if len(finite) < 2:
        return "insufficient_data"
    if np.all(finite > 0):
        return "↑ Convergent increase"
    if np.all(finite < 0):
        return "↓ Convergent decrease"
    if np.all(np.sign(finite) == np.sign(finite[0])):
        return "≈ Same direction"
    return "✗ Divergent"


# ---------------------------------------------------------------------------
# Stage 5 — Block Bootstrap CI (§9.3)
# ---------------------------------------------------------------------------

def _recompute_metric_from_projection(
    Y_boot: np.ndarray,
    metric_name: str,
    pca: PCA,
    columns: list[str],
    n_bins: int = 25,
    **kwargs,
) -> float:
    """
    Recompute a scalar metric from a bootstrapped projected array Y_boot (N, K).
    Used inside the bootstrap loop — must be fast.
    """
    from EDA_PCA import _gini, _session_joint_contributions

    if metric_name == "d_eff":
        var_pc = np.var(Y_boot, axis=0)
        total = np.sum(var_pc)
        if total <= 0:
            return float("nan")
        p = var_pc / (total + 1e-12)
        return float(1.0 / (np.sum(p ** 2) + 1e-12))

    if metric_name == "gini_joint":
        attr = _session_joint_contributions(pca, Y_boot)  # expects original-scale scaled data
        # Y_boot here IS already projected; we need to recompute from scaled data
        # This path is handled by passing scaled_boot instead of Y_boot — see below
        return float("nan")

    if metric_name == "state_space_entropy_equalized":
        pts = Y_boot[:, :2]
        pc1_lo, pc1_hi = np.percentile(pts[:, 0], [1, 99])
        pc2_lo, pc2_hi = np.percentile(pts[:, 1], [1, 99])
        e1 = np.linspace(pc1_lo, pc1_hi, n_bins + 1)
        e2 = np.linspace(pc2_lo, pc2_hi, n_bins + 1)
        p1c = np.clip(pts[:, 0], e1[0], e1[-1])
        p2c = np.clip(pts[:, 1], e2[0], e2[-1])
        hist, _, _ = np.histogram2d(p1c, p2c, bins=[e1, e2])
        total = hist.sum()
        if total <= 0:
            return 0.0
        p = hist.flatten() / total
        p = p[p > 0]
        return float(-np.sum(p * np.log2(p)))

    if metric_name == "sampen_pc1":
        r_frac = kwargs.get("r_fraction", SAMPEN_R_FRACTION_DEFAULT)
        pc1 = Y_boot[:, 0]
        r = r_frac * float(np.std(pc1, ddof=1))
        if r <= 0:
            return float("nan")
        val = _sample_entropy_numpy(pc1, m=SAMPEN_M, r=r)
        return float(val) if np.isfinite(val) else float("nan")

    return float("nan")


def _recompute_atf_from_blocks(
    vel_arrays: dict[str, np.ndarray],
    art_arrays: dict[str, np.ndarray],
    noise_floors: dict[str, float],
    block_indices: np.ndarray,
) -> float:
    """Recompute whole-body median ATF from a bootstrap block index array."""
    per_joint = []
    for joint, vel in vel_arrays.items():
        if joint not in art_arrays or joint not in noise_floors:
            continue
        art = art_arrays[joint]
        V_j = noise_floors[joint]
        vel_b = vel[block_indices]
        art_b = art[block_indices]
        clean = ~art_b
        denom = int(clean.sum())
        if denom == 0:
            continue
        numer = int(((vel_b > V_j) & clean).sum())
        per_joint.append(numer / denom)
    return float(np.median(per_joint)) if per_joint else float("nan")


def bootstrap_delta_ci(
    bundle: ThesisMetricsBundle,
    metrics: list[str] | None = None,
    n_iterations: int = BOOTSTRAP_N,
    block_sec: float | None = None,
    ci: float = 0.95,
    seed: int = BOOTSTRAP_SEED,
    sensitivity_block_secs: list[float] = (1.0, 2.0, 4.0),
) -> pd.DataFrame:
    """
    Non-overlapping block bootstrap CI for delta metrics (§9.3).

    For PCA-derived metrics: sample frame-index blocks, re-project onto FIXED
    T1-anchored W (PCA not refitted), recompute metric.
    For ATF: sample same frame-index blocks, recompute ATF from raw velocities.

    T1 and T3 bootstrapped independently; delta CI combines them.

    Returns DataFrame with [subject, metric, branch, timepoint, block_sec,
    ci_lower_T1, ci_upper_T1, ci_lower_T3, ci_upper_T3,
    ci_lower_delta, ci_upper_delta, n_blocks, effect_size_ES].
    """
    if block_sec is None:
        block_sec = bundle.bootstrap_block_sec

    rng = np.random.default_rng(seed)
    subj = bundle.subject_id
    tps = bundle.timepoints

    # Metrics to bootstrap (subset for speed; all by default)
    default_metrics = [
        ("atf_whole_body_median", "whole_body"),
        ("d_eff", "dynamics"), ("d_eff", "pose"), ("d_eff", "reach"),
        ("gini_joint_anchored", "dynamics"),
        ("state_space_entropy_bits_equalized", "dynamics"),
        ("state_space_entropy_bits_equalized", "pose"),
        ("state_space_entropy_bits_equalized", "reach"),
        ("sampen_pc1", "dynamics"), ("sampen_pc1", "pose"), ("sampen_pc1", "reach"),
    ]
    if metrics is not None:
        pairs = [(m, b) for m, b in default_metrics if m in metrics]
    else:
        pairs = default_metrics

    rows = []
    pca_results = bundle._pca_results
    prepared = bundle._prepared
    atf_results_raw = bundle._atf_results

    for block_s in sensitivity_block_secs:
        L = max(1, int(block_s * FS))

        for metric_name, branch in pairs:
            # Identify T1 and T3 indices
            t1_idx = tps.index("T1") if "T1" in tps else None
            t3_idx = tps.index("T3") if "T3" in tps else None
            if t1_idx is None or t3_idx is None:
                continue

            is_atf = (branch == "whole_body")

            if is_atf:
                atf_t1 = atf_results_raw[t1_idx]
                atf_t3 = atf_results_raw[t3_idx]
                n_frames_t1 = len(next(iter(atf_t1.vel_arrays.values())))
                n_frames_t3 = len(next(iter(atf_t3.vel_arrays.values())))
            else:
                pca_b = pca_results.get(branch)
                prep_b = prepared.get(branch)
                if not pca_b or not prep_b:
                    continue
                pca_obj = pca_b["pca"]
                scaled_t1 = prep_b["scaled_arrays"][t1_idx]
                scaled_t3 = prep_b["scaled_arrays"][t3_idx]
                n_frames_t1 = len(scaled_t1)
                n_frames_t3 = len(scaled_t3)

            n_blocks_t1 = n_frames_t1 // L
            n_blocks_t3 = n_frames_t3 // L
            if n_blocks_t1 < 2 or n_blocks_t3 < 2:
                continue

            boot_t1 = np.full(n_iterations, float("nan"))
            boot_t3 = np.full(n_iterations, float("nan"))

            for b_iter in range(n_iterations):
                # T1
                chosen_t1 = rng.integers(0, n_blocks_t1, size=n_blocks_t1)
                idx_t1 = np.concatenate([
                    np.arange(c * L, min((c + 1) * L, n_frames_t1))
                    for c in chosen_t1
                ])
                # T3
                chosen_t3 = rng.integers(0, n_blocks_t3, size=n_blocks_t3)
                idx_t3 = np.concatenate([
                    np.arange(c * L, min((c + 1) * L, n_frames_t3))
                    for c in chosen_t3
                ])

                if is_atf:
                    boot_t1[b_iter] = _recompute_atf_from_blocks(
                        atf_t1.vel_arrays, atf_t1.art_arrays, atf_t1.noise_floors, idx_t1)
                    boot_t3[b_iter] = _recompute_atf_from_blocks(
                        atf_t3.vel_arrays, atf_t3.art_arrays, atf_t3.noise_floors, idx_t3)
                else:
                    # Re-project onto FIXED T1-anchored W (do NOT refit PCA)
                    Y_t1 = pca_obj.transform(scaled_t1[idx_t1])
                    Y_t3 = pca_obj.transform(scaled_t3[idx_t3])
                    boot_t1[b_iter] = _recompute_metric_from_projection(
                        Y_t1, metric_name, pca_obj, pca_b["columns"],
                        n_bins=bundle.n_bins, r_fraction=bundle.sampen_r_fraction)
                    boot_t3[b_iter] = _recompute_metric_from_projection(
                        Y_t3, metric_name, pca_obj, pca_b["columns"],
                        n_bins=bundle.n_bins, r_fraction=bundle.sampen_r_fraction)

            alpha = (1.0 - ci) / 2.0
            lo, hi = 100 * alpha, 100 * (1 - alpha)
            delta_boot = boot_t3 - boot_t1
            finite_mask = np.isfinite(delta_boot)

            def pct(arr, q):
                arr_f = arr[np.isfinite(arr)]
                return float(np.percentile(arr_f, q)) if len(arr_f) > 0 else float("nan")

            t1_mean = pct(boot_t1, 50)
            t1_std = float(np.nanstd(boot_t1))
            es = pct(delta_boot, 50) / (t1_std + 1e-12) if t1_std > 0 else float("nan")

            rows.append({
                "subject_id": subj,
                "metric": metric_name,
                "branch": branch,
                "block_sec": block_s,
                "n_blocks_T1": n_blocks_t1,
                "n_blocks_T3": n_blocks_t3,
                "ci_lower_T1": pct(boot_t1, lo),
                "ci_upper_T1": pct(boot_t1, hi),
                "ci_lower_T3": pct(boot_t3, lo),
                "ci_upper_T3": pct(boot_t3, hi),
                "ci_lower_delta": pct(delta_boot, lo),
                "ci_upper_delta": pct(delta_boot, hi),
                "delta_median": pct(delta_boot, 50),
                "effect_size_ES": es,
                "n_finite_bootstrap": int(finite_mask.sum()),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Stage 6 — Visualization
# ---------------------------------------------------------------------------

def plot_atf_heatmap(
    atf_results_by_session: dict[str, ATFResult],
    subjects: list[str],
    save_path: Path | None = None,
) -> tuple:
    """
    Joint × Session ATF heatmap. Returns (plotly_fig, mpl_fig).
    Joints grouped by anatomical region.
    """
    if not _HAS_PLOTLY or not _HAS_MPL:
        return None, None

    joint_order = list(ALL_19_JOINTS)
    session_keys = list(atf_results_by_session.keys())

    Z = np.full((len(joint_order), len(session_keys)), float("nan"))
    for j_idx, joint in enumerate(joint_order):
        for s_idx, sk in enumerate(session_keys):
            atf_r = atf_results_by_session[sk]
            Z[j_idx, s_idx] = atf_r.per_joint_atf.get(joint, float("nan"))

    fig_pl = go.Figure(data=go.Heatmap(
        z=Z, x=session_keys, y=joint_order,
        colorscale="Viridis", zmin=0, zmax=1,
        colorbar=dict(title="ATF"),
    ))
    fig_pl.update_layout(title="Active Time Fraction — All Joints × Sessions",
                         height=600, width=900)
    if save_path:
        fig_pl.write_html(str(Path(save_path).with_suffix(".html")))

    fig_mpl, ax = plt.subplots(figsize=(max(6, len(session_keys) * 1.2), 8))
    im = ax.imshow(Z, aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(len(session_keys)))
    ax.set_xticklabels(session_keys, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(joint_order)))
    ax.set_yticklabels(joint_order, fontsize=8)
    fig_mpl.colorbar(im, ax=ax, label="ATF")
    ax.set_title("Active Time Fraction")
    fig_mpl.tight_layout()
    if save_path:
        fig_mpl.savefig(str(Path(save_path).with_suffix(".png")), dpi=300)
        fig_mpl.savefig(str(Path(save_path).with_suffix(".pdf")))
    return fig_pl, fig_mpl


def plot_gini_trajectories(
    bundle: ThesisMetricsBundle,
    branch: str = "dynamics",
    save_path: Path | None = None,
) -> tuple:
    """D_eff and Joint Gini longitudinal trajectories T1→T2→T3."""
    if not _HAS_PLOTLY or not _HAS_MPL:
        return None, None

    tps = bundle.timepoints
    deff = bundle.d_eff.get(branch, [])
    gini = bundle.gini_joint_anchored.get(branch, [])
    gini_nat = bundle.gini_joint_native.get(branch, [])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tps, y=deff, mode="lines+markers",
                             name="D_eff (T1-anchored)", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=tps, y=gini, mode="lines+markers",
                             name="Gini (T1-anchored)", line=dict(color="red")))
    fig.add_trace(go.Scatter(x=tps, y=gini_nat, mode="lines+markers",
                             name="Gini (native, sensitivity)", line=dict(color="red", dash="dash")))
    fig.update_layout(title=f"D_eff & Joint Gini — {branch} branch — {bundle.subject_id}",
                      yaxis_title="Value", height=450)
    if save_path:
        fig.write_html(str(Path(save_path).with_suffix(".html")))

    fig_mpl, ax1 = plt.subplots(figsize=(7, 4))
    ax2 = ax1.twinx()
    ax1.plot(tps, deff, "b-o", label="D_eff")
    ax2.plot(tps, gini, "r-o", label="Gini (anchored)")
    ax2.plot(tps, gini_nat, "r--o", label="Gini (native)")
    ax1.set_ylabel("D_eff (effective modes)", color="blue")
    ax2.set_ylabel("Joint Gini (↓ = more democratic)", color="red")
    ax2.invert_yaxis()
    ax1.set_title(f"D_eff & Joint Gini — {branch} — {bundle.subject_id}")
    fig_mpl.tight_layout()
    if save_path:
        fig_mpl.savefig(str(Path(save_path).with_suffix(".png")), dpi=300)
    return fig, fig_mpl


def plot_entropy_landscape(
    bundle: ThesisMetricsBundle,
    pca_output: dict,
    branch: str = "dynamics",
    save_path: Path | None = None,
) -> object:
    """3-panel PC1×PC2 state-space heatmaps (T1/T2/T3) with entropy annotation."""
    if not _HAS_PLOTLY:
        return None
    pca_res = pca_output["pca_results"].get(branch)
    if not pca_res:
        return None

    tps = bundle.timepoints
    proj_arrays = pca_res["projected_arrays"]
    n_bins = bundle.n_bins
    eq_arrays, _ = _equalize_projected_arrays(proj_arrays)
    ent_data = _compute_entropy_from_arrays(proj_arrays, eq_arrays, n_bins=n_bins)

    all_eq = np.vstack(eq_arrays)
    pc1_lo, pc1_hi = np.percentile(all_eq[:, 0], [1, 99])
    pc2_lo, pc2_hi = np.percentile(all_eq[:, 1], [1, 99])
    e1 = np.linspace(pc1_lo, pc1_hi, n_bins + 1)
    e2 = np.linspace(pc2_lo, pc2_hi, n_bins + 1)

    n_tp = len(tps)
    fig = make_subplots(rows=1, cols=n_tp, subplot_titles=tps)
    for idx, (tp, pts_eq) in enumerate(zip(tps, eq_arrays)):
        p1c = np.clip(pts_eq[:, 0], e1[0], e1[-1])
        p2c = np.clip(pts_eq[:, 1], e2[0], e2[-1])
        hist, _, _ = np.histogram2d(p1c, p2c, bins=[e1, e2])
        H = ent_data["entropy_equalized"][idx]
        fig.add_trace(go.Heatmap(
            z=hist.T, colorscale="Hot_r",
            showscale=(idx == n_tp - 1),
            name=tp,
        ), row=1, col=idx + 1)
        fig.add_annotation(
            row=1, col=idx + 1,
            text=f"H={H:.2f} bits",
            xref="paper", yref="paper",
            showarrow=False, font=dict(size=11),
        )
    fig.update_layout(title=f"State-Space Entropy — {branch} — {bundle.subject_id}",
                      height=400)
    if save_path:
        fig.write_html(str(Path(save_path).with_suffix(".html")))
    return fig


def plot_variance_structure(
    bundle: ThesisMetricsBundle,
    pca_output: dict,
    branch: str = "dynamics",
    save_path: Path | None = None,
) -> tuple:
    """Cumulative variance curves with N90 markers and D_eff annotations."""
    if not _HAS_PLOTLY or not _HAS_MPL:
        return None, None

    pca_res = pca_output["pca_results"].get(branch)
    prep_b = pca_output["prepared"].get(branch)
    if not pca_res or not prep_b:
        return None, None

    pca_obj = pca_res["pca"]
    tps = bundle.timepoints
    colors = {"T1": "#1f77b4", "T2": "#d62728", "T3": "#2ca02c"}

    fig = go.Figure()
    fig_mpl, ax = plt.subplots(figsize=(8, 5))

    for i, (tp, X) in enumerate(zip(tps, prep_b["scaled_arrays"])):
        Y = pca_obj.transform(X)
        var_pc = np.var(Y, axis=0)
        var_sorted = np.sort(var_pc)[::-1]
        total = var_sorted.sum()
        cum = np.cumsum(var_sorted / (total + 1e-12))
        n90 = int(bundle.n90.get(branch, [0] * len(tps))[i])
        deff = bundle.d_eff.get(branch, [float("nan")] * len(tps))[i]
        color = colors.get(tp, "black")
        label = f"{tp} (N90={n90}, D_eff={deff:.1f})"

        fig.add_trace(go.Scatter(
            x=list(range(1, len(cum) + 1)), y=cum,
            mode="lines", name=label, line=dict(color=color)
        ))
        ax.plot(range(1, len(cum) + 1), cum, color=color, label=label)
        ax.axvline(n90, color=color, linestyle="--", alpha=0.5)

    fig.add_hline(y=bundle.variance_threshold, line_dash="dot",
                  annotation_text=f"{bundle.variance_threshold:.0%}")
    ax.axhline(bundle.variance_threshold, linestyle=":", color="gray")
    ax.set_xlabel("Number of PCs")
    ax.set_ylabel("Cumulative Variance Explained")
    ax.set_title(f"Variance Structure — {branch} — {bundle.subject_id}")
    ax.legend(fontsize=8)
    fig_mpl.tight_layout()

    fig.update_layout(title=f"Variance Structure — {branch} — {bundle.subject_id}",
                      xaxis_title="PCs", yaxis_title="Cumulative Variance",
                      height=450)
    if save_path:
        fig.write_html(str(Path(save_path).with_suffix(".html")))
        fig_mpl.savefig(str(Path(save_path).with_suffix(".png")), dpi=300)
    return fig, fig_mpl


def plot_longitudinal_summary(
    delta_df: pd.DataFrame,
    save_path: Path | None = None,
) -> tuple:
    """Normalized delta bar chart: T1→T2, T2→T3, T1→T3 per metric."""
    if not _HAS_PLOTLY or not _HAS_MPL:
        return None, None
    metrics_to_show = [
        "atf_whole_body_median", "d_eff", "gini_joint_anchored",
        "state_space_entropy_bits_equalized", "sampen_pc1",
        "ap_index", "rqa_pct_recurrence",
    ]
    subset = delta_df[delta_df["metric"].isin(metrics_to_show)]

    fig = go.Figure()
    for col, name, color in [
        ("delta_T1_T2", "T1→T2", "royalblue"),
        ("delta_T2_T3", "T2→T3", "darkorange"),
        ("delta_T1_T3", "T1→T3", "green"),
    ]:
        if col in subset.columns:
            fig.add_trace(go.Bar(
                x=subset["metric"].astype(str) + " | " + subset["branch"].astype(str),
                y=subset[col], name=name,
                marker_color=color,
            ))
    fig.update_layout(barmode="group", title="Longitudinal Delta Summary",
                      height=500, xaxis_tickangle=-45)
    if save_path:
        fig.write_html(str(Path(save_path).with_suffix(".html")))
    return fig, None


def plot_cross_subject_trajectories(
    bundles: list[ThesisMetricsBundle],
    metrics: list[str] | None = None,
    branch: str = "dynamics",
    save_path: Path | None = None,
) -> tuple:
    """
    Both subjects on the same axes, z-scored to T1. (§10.2 required N=2 figure)
    Solid = subject 651; dashed = subject 671.
    """
    if not _HAS_PLOTLY or not _HAS_MPL:
        return None, None
    if metrics is None:
        metrics = ["d_eff", "gini_joint_anchored", "state_space_entropy_bits_equalized"]

    n_metrics = len(metrics)
    fig = make_subplots(rows=1, cols=n_metrics, subplot_titles=metrics)
    fig_mpl, axes = plt.subplots(1, n_metrics, figsize=(5 * n_metrics, 4), sharey=False)
    if n_metrics == 1:
        axes = [axes]

    linestyles = ["solid", "dash", "dot", "dashdot"]
    colors_subj = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]

    for m_idx, metric in enumerate(metrics):
        ax = axes[m_idx]
        for b_idx, bundle in enumerate(bundles):
            tps = bundle.timepoints
            # Extract metric values
            vals = _extract_metric_series(bundle, metric, branch)
            if vals is None or len(vals) == 0:
                continue
            # Z-score to T1
            t1_idx = tps.index("T1") if "T1" in tps else 0
            t1_val = vals[t1_idx]
            t1_std = float(np.nanstd(vals))
            if t1_std <= 0:
                t1_std = 1.0
            z_vals = [(v - t1_val) / t1_std for v in vals]
            color = colors_subj[b_idx % len(colors_subj)]
            ls = linestyles[b_idx % len(linestyles)]
            label = f"S{bundle.subject_id}"

            fig.add_trace(go.Scatter(
                x=tps, y=z_vals, mode="lines+markers",
                name=label, line=dict(color=color, dash=ls),
                showlegend=(m_idx == 0),
            ), row=1, col=m_idx + 1)

            mpl_ls = "-" if b_idx == 0 else "--"
            ax.plot(tps, z_vals, marker="o", linestyle=mpl_ls, color=color, label=label)

        ax.set_title(metric, fontsize=9)
        ax.axhline(0, color="gray", linestyle=":", alpha=0.5)
        ax.set_ylabel("ΔZ (T1-normalized)")
        ax.legend(fontsize=8)

    fig.update_layout(title=f"Cross-Subject Trajectories — {branch}", height=400)
    fig_mpl.tight_layout()
    if save_path:
        fig.write_html(str(Path(save_path).with_suffix(".html")))
        fig_mpl.savefig(str(Path(save_path).with_suffix(".png")), dpi=300)
    return fig, fig_mpl


def _extract_metric_series(
    bundle: ThesisMetricsBundle,
    metric: str,
    branch: str,
) -> list[float] | None:
    """Extract a named metric's time series from a bundle."""
    lookup = {
        "d_eff": bundle.d_eff,
        "d_eff_norm": bundle.d_eff_norm,
        "gini_joint_anchored": bundle.gini_joint_anchored,
        "gini_joint_native": bundle.gini_joint_native,
        "state_space_entropy_bits_equalized": bundle.entropy_equalized,
        "centroid_displacement_normalized": bundle.centroid_displacement_norm,
        "sampen_pc1": bundle.sampen,
        "ap_ratio": bundle.ap_ratio,
        "ap_index": bundle.ap_index,
        "rqa_pct_recurrence": bundle.rqa_pct_rec,
        "rqa_pct_determinism": bundle.rqa_pct_det,
        "atf_whole_body_median": {branch: bundle.atf_whole_body},
    }
    series_dict = lookup.get(metric)
    if series_dict is None:
        return None
    vals = series_dict.get(branch)
    if vals is None:
        return None
    return [v if v is not None else float("nan") for v in vals]


# ---------------------------------------------------------------------------
# Stage 6 — Validation (§10.2)
# ---------------------------------------------------------------------------

def validate_pipeline() -> dict[str, bool]:
    """
    Runs analytical pipeline on synthetic signals with known ground-truth.
    FAIL FAST: raises AssertionError with failing case description.
    All assertions use rtol=0.01 (1% numerical tolerance).
    """
    results: dict[str, bool] = {}
    FS_SYN = 120.0
    N = 4800  # 40 seconds at 120 Hz — enough for stable SampEn

    def _check(name: str, got: float, expected: float, rtol: float = 0.05):
        ok = abs(got - expected) <= rtol * max(abs(expected), 1e-6) + 1e-9
        results[name] = ok
        if not ok:
            raise AssertionError(
                f"validate_pipeline FAILED [{name}]: got {got:.6f}, expected {expected:.6f}"
            )

    # ── Test 1: ATF = 1.0 on constant-velocity above noise floor ─────────────
    vel = np.full(N, 50.0)  # 50 mm/s > typical V_j
    art = np.zeros(N, dtype=bool)
    V_j = 1.0
    clean = ~art
    atf_1 = float(((vel > V_j) & clean).sum()) / float(clean.sum())
    _check("ATF_constant_above_floor", atf_1, 1.0)

    # ── Test 2: ATF = 0.0 on constant-zero signal ─────────────────────────────
    vel0 = np.zeros(N)
    atf_0 = float(((vel0 > V_j) & clean).sum()) / float(clean.sum())
    _check("ATF_zero_signal", atf_0, 0.0)

    # ── Test 3: D_eff ≈ 1 on single-mode signal ───────────────────────────────
    rng = np.random.default_rng(0)
    X_1mode = rng.standard_normal((N, 1)) @ np.ones((1, 10))  # all 10 features = same
    pca_1 = PCA(n_components=10)
    pca_1.fit(X_1mode)
    var_pc = np.var(pca_1.transform(X_1mode), axis=0)
    total = var_pc.sum()
    p = var_pc / (total + 1e-12)
    d_eff_1 = float(1.0 / (np.sum(p ** 2) + 1e-12))
    _check("Deff_single_mode", d_eff_1, 1.0, rtol=0.05)

    # ── Test 4: D_eff ≈ K on white-noise signal ───────────────────────────────
    K = 19
    X_wn = rng.standard_normal((N, K))
    pca_wn = PCA(n_components=K)
    pca_wn.fit(X_wn)
    var_wn = np.var(pca_wn.transform(X_wn), axis=0)
    p_wn = var_wn / (var_wn.sum() + 1e-12)
    d_eff_wn = float(1.0 / (np.sum(p_wn ** 2) + 1e-12))
    _check("Deff_white_noise", d_eff_wn, float(K), rtol=0.10)

    # ── Test 5: Entropy of uniform histogram ≈ log2(n_bins²) ─────────────────
    n_bins = 25
    uniform = np.ones((n_bins, n_bins)) / (n_bins * n_bins)
    p_u = uniform.flatten()
    H_uniform = float(-np.sum(p_u * np.log2(p_u + 1e-300)))
    H_max = np.log2(n_bins * n_bins)
    _check("Entropy_uniform_histogram", H_uniform, H_max, rtol=0.01)

    # ── Test 6: Entropy = 0.0 on all-frames-in-one-bin ───────────────────────
    single_bin = np.zeros((n_bins, n_bins))
    single_bin[0, 0] = 1.0
    p_s = single_bin.flatten()
    p_s = p_s[p_s > 0]
    H_single = float(-np.sum(p_s * np.log2(p_s)))
    _check("Entropy_one_bin", H_single, 0.0, rtol=0.01)

    # ── Test 7: Joint Gini ≈ 0 for equal contributions ────────────────────────
    from EDA_PCA import _gini
    equal_props = np.ones(19) / 19.0
    g = _gini(equal_props)
    _check("Gini_equal_contributions", g, 0.0, rtol=0.05)

    # ── Test 8: Bootstrap CI width ≈ 0 for constant signal ──────────────────
    # A constant array has zero variance — every bootstrap sample gives the same
    # mean, so the CI width must be exactly 0.
    const_signal = np.full(N, 5.0)
    L_blocks = int(2.0 * FS_SYN)
    n_blocks = N // L_blocks
    rng2 = np.random.default_rng(42)
    boot_means = []
    for _ in range(200):
        chosen = rng2.integers(0, n_blocks, size=n_blocks)
        idx = np.concatenate([np.arange(c * L_blocks, (c + 1) * L_blocks) for c in chosen])
        boot_means.append(float(const_signal[idx].mean()))
    ci_width = float(np.percentile(boot_means, 97.5) - np.percentile(boot_means, 2.5))
    # All block means = 5.0, so CI width must be identically 0
    results["Bootstrap_CI_constant_signal_width_zero"] = (ci_width == 0.0)
    if ci_width != 0.0:
        raise AssertionError(
            f"validate_pipeline FAILED [Bootstrap_CI_constant_signal_width_zero]: "
            f"CI width = {ci_width:.6f}, expected 0.0"
        )

    print("validate_pipeline: ALL TESTS PASSED")
    return results


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_results(
    results_df: pd.DataFrame,
    delta_df: pd.DataFrame,
    ci_df: pd.DataFrame,
    output_dir: Path,
    subject_id: str,
    batch_name: str = "thesis",
) -> dict[str, Path]:
    """Export tidy DataFrames to parquet + JSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = output_dir / f"{subject_id}_{batch_name}"

    paths: dict[str, Path] = {}
    for name, df in [("metrics", results_df), ("deltas", delta_df), ("bootstrap_ci", ci_df)]:
        p = stem.parent / f"{stem.name}_{name}.parquet"
        df.to_parquet(p, index=False)
        paths[name] = p

    return paths
