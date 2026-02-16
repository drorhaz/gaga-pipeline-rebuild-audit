"""
EDA & PCA for Motor Repertoire Expansion (3-Branch: ω, q, XYZ).
All processing logic and data classes; notebook 10_EDA_PCA.ipynb calls this module.
Phase 0: Batch config parsing, file existence, structural alignment, Hips origin, temporal checks.
         Requires >= 2 timepoints; warns (does not fail) when one of T1/T2/T3 is missing.
Phase 1: Unified loader & longitudinal scaling (fit scaler on available sessions, transform each separately).
Phase 2: 3-branch PCA (fit on combined sessions, project into 3D PC space; full variance spectrum for N90).
Phase 3: Exploration metrics (N90 per branch/timepoint, 3D convex hull volume per branch/timepoint).
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from scipy.spatial import ConvexHull

import matplotlib.pyplot as plt

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    go = None
    make_subplots = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXPECTED_OMEGA_COLS = 19
EXPECTED_Q_COLS = 76   # 4 * 19
EXPECTED_XYZ_COLS = 57  # 3 * 19
HIP_TOL_MEAN = 1e-5   # Hips position columns should be ~0 (origin)
HIP_TOL_STD = 0.01  # Hips should not move; flag if std > this
GAP_MULTIPLIER = 2.0   # no gap > 2 * (1/fs)
SCALING_MEAN_TOL = 1e-5   # scaled features combined mean ≈ 0
SCALING_STD_TOL = 1e-5    # scaled features combined std ≈ 1


def load_batch_config(
    batch_config_path: str | Path | None = None,
    subject_id: str | None = None,
    project_root: str | Path = ".",
) -> dict[str, Any]:
    """
    Load JSON batch configuration. Prefer batch_config_path; if subject_id only,
    resolve to batch_configs/subject_{subject_id}_all.json.
    """
    root = Path(project_root)
    if batch_config_path is not None:
        path = Path(batch_config_path)
        if not path.is_absolute():
            path = root / path
    elif subject_id is not None:
        path = root / "batch_configs" / f"subject_{subject_id}_all.json"
    else:
        raise ValueError("Provide either batch_config_path or subject_id")
    if not path.exists():
        raise FileNotFoundError(f"Batch config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _timepoint_from_csv_path(csv_path: str) -> str:
    """Extract T1, T2, or T3 from path like 671/T1/... or 734/T3/..."""
    path = csv_path.replace("\\", "/")
    for tp in ("T1", "T2", "T3"):
        if f"/{tp}/" in path or path.startswith(f"{tp}/"):
            return tp
    return "UNKNOWN"


def get_session_mapping(
    batch_config: dict[str, Any],
    project_root: str | Path = ".",
) -> list[dict[str, Any]]:
    """
    Session list order follows batch_config["csv_files"] order.
    prepare_3branch_data() uses _get_representative_sessions_with_parquets() which
    re-orders to canonical [T1, T2, T3], so downstream index [0,1,2] always = [T1,T2,T3].
    """
    root = Path(project_root)
    data_dir = root / "data"
    deriv_dir = root / "derivatives" / "step_06_kinematics"
    out = []
    for csv_rel in batch_config.get("csv_files", []):
        parts = csv_rel.replace("\\", "/").split("/")
        csv_path = data_dir / Path(*parts)
        run_id = Path(parts[-1]).stem
        timepoint = _timepoint_from_csv_path(csv_rel)
        parquet_path = deriv_dir / f"{run_id}__kinematics_master.parquet"
        out.append({
            "timepoint": timepoint,
            "csv_rel": csv_rel,
            "run_id": run_id,
            "parquet_path": parquet_path,
            "csv_path": csv_path,
        })
    return out


def _omega_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.endswith("__zeroed_rel_omega_mag")]


def _q_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if re.match(r".+__zeroed_rel_q[wxyz]$", c)]


def _xyz_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if re.match(r".+__lin_rel_p[xyz]$", c)]


def _joints_from_omega_cols(cols: list[str]) -> set[str]:
    return {c.replace("__zeroed_rel_omega_mag", "") for c in cols}


def _joints_from_q_cols(cols: list[str]) -> set[str]:
    return {re.sub(r"__zeroed_rel_q[wxyz]$", "", c) for c in cols}


def _joints_from_xyz_cols(cols: list[str]) -> set[str]:
    return {re.sub(r"__lin_rel_p[xyz]$", "", c) for c in cols}


def _load_parquet_light(path: Path) -> pd.DataFrame:
    """Load parquet; use only columns we need for checks to keep memory low."""
    return pd.read_parquet(path)


def run_integrity_checks(
    batch_config: str | Path | dict | None = None,
    subject_id: str | None = None,
    project_root: str | Path = ".",
) -> dict[str, Any]:
    """
    Phase 0 integrity checks. Use batch_config (path or dict) or subject_id.
    Returns dict with:
      - table_rows: list of dicts for Numerical Verification Table
      - passed: bool (overall PASS/FAIL)
      - errors: list of blocking error messages
      - warnings: list of non-blocking warning messages
      - session_mapping: list of session dicts (timepoint, parquet_path, ...)
      - available_timepoints: list of str (e.g. ["T1", "T2"] or ["T1", "T2", "T3"])
    """
    errors: list[str] = []
    warnings: list[str] = []
    if isinstance(batch_config, dict):
        config = batch_config
    else:
        config = load_batch_config(
            batch_config_path=batch_config,
            subject_id=subject_id,
            project_root=project_root,
        )
    root = Path(project_root)
    mapping = get_session_mapping(config, root)

    # 1) Check which timepoints are present (at least 2 required, 3 ideal)
    by_tp: dict[str, list[dict]] = {}
    for m in mapping:
        tp = m["timepoint"]
        by_tp.setdefault(tp, []).append(m)
    available_timepoints = [tp for tp in ("T1", "T2", "T3") if tp in by_tp]
    missing_timepoints = [tp for tp in ("T1", "T2", "T3") if tp not in by_tp]
    if missing_timepoints:
        warnings.append(
            f"Missing timepoint(s): {', '.join(missing_timepoints)}. "
            f"Running with {len(available_timepoints)} session(s): {', '.join(available_timepoints)}."
        )
    if len(available_timepoints) < 2:
        errors.append(
            f"At least 2 timepoints required for comparison, found {len(available_timepoints)}: "
            f"{', '.join(available_timepoints) or 'none'}."
        )

    # Representative: one session per available timepoint (for table and checks)
    representative: list[dict] = []
    for tp in ("T1", "T2", "T3"):
        if tp in by_tp:
            representative.append(by_tp[tp][0])
    if not representative:
        return {
            "table_rows": [],
            "passed": False,
            "errors": errors,
            "warnings": warnings,
            "session_mapping": mapping,
            "available_timepoints": available_timepoints,
        }

    # 2) File existence
    for m in representative:
        if not m["parquet_path"].exists():
            errors.append(f"Parquet missing: {m['parquet_path']}")
    if errors:
        return {
            "table_rows": [],
            "passed": False,
            "errors": errors,
            "warnings": warnings,
            "session_mapping": mapping,
            "available_timepoints": available_timepoints,
        }

    # Load parquets for the available sessions
    dfs: list[pd.DataFrame] = []
    for m in representative:
        dfs.append(_load_parquet_light(m["parquet_path"]))

    # 3) Branch column counts and joint intersection
    omega_cols_per_session = [_omega_columns(df) for df in dfs]
    q_cols_per_session = [_q_columns(df) for df in dfs]
    xyz_cols_per_session = [_xyz_columns(df) for df in dfs]

    joints_omega = [_joints_from_omega_cols(c) for c in omega_cols_per_session]
    joints_q = [_joints_from_q_cols(c) for c in q_cols_per_session]
    joints_xyz = [_joints_from_xyz_cols(c) for c in xyz_cols_per_session]

    inter_omega = set.intersection(*joints_omega) if joints_omega else set()
    inter_q = set.intersection(*joints_q) if joints_q else set()
    inter_xyz = set.intersection(*joints_xyz) if joints_xyz else set()

    for i, (j1, j2, j3) in enumerate(zip(joints_omega, joints_q, joints_xyz)):
        only_t1 = (j1 - inter_omega) or (j2 - inter_q) or (j3 - inter_xyz)
        if only_t1:
            errors.append(f"Session {representative[i]['timepoint']}: joints not present in all sessions: {only_t1}")
    if len(omega_cols_per_session[0]) != EXPECTED_OMEGA_COLS:
        errors.append(f"Branch ω: expected {EXPECTED_OMEGA_COLS} columns, got {len(omega_cols_per_session[0])}")
    if len(q_cols_per_session[0]) != EXPECTED_Q_COLS:
        errors.append(f"Branch q: expected {EXPECTED_Q_COLS} columns, got {len(q_cols_per_session[0])}")
    if len(xyz_cols_per_session[0]) != EXPECTED_XYZ_COLS:
        errors.append(f"Branch XYZ: expected {EXPECTED_XYZ_COLS} columns, got {len(xyz_cols_per_session[0])}")

    # 4) Hips at origin (mean and std ≈ 0)
    hips_cols = ["Hips__lin_rel_px", "Hips__lin_rel_py", "Hips__lin_rel_pz"]
    for i, df in enumerate(dfs):
        for col in hips_cols:
            if col not in df.columns:
                errors.append(f"Session {representative[i]['timepoint']}: missing {col}")
                continue
            mu = float(df[col].mean())
            sigma = float(df[col].std())
            if abs(mu) > HIP_TOL_MEAN or sigma > HIP_TOL_STD:
                errors.append(
                    f"Session {representative[i]['timepoint']}: Hips {col} mean={mu:.6f} std={sigma:.6f} (expected ~0). "
                    "Branch C is not 'reach relative to body' (Hips are moving)."
                )

    # 5) Temporal: median fs, consistency, max gap
    time_col = "time_s"
    table_rows: list[dict[str, Any]] = []
    fs_list: list[float] = []
    for i, df in enumerate(dfs):
        if time_col not in df.columns:
            errors.append(f"Session {representative[i]['timepoint']}: missing '{time_col}'")
            table_rows.append({
                "Session ID": representative[i]["timepoint"],
                "Frames": len(df),
                "Median fs (Hz)": None,
                "Max Gap (ms)": None,
                "n_omega": len(omega_cols_per_session[i]),
                "n_q": len(q_cols_per_session[i]),
                "n_xyz": len(xyz_cols_per_session[i]),
            })
            continue
        t = df[time_col].values
        dt = np.diff(t)
        dt_ms = dt * 1000.0
        median_dt = np.median(dt)
        if median_dt <= 0:
            fs_hz = None
            max_gap_ms = float(np.max(dt_ms)) if len(dt_ms) else None
        else:
            fs_hz = 1.0 / median_dt
            max_gap_ms = float(np.max(dt_ms))
        fs_list.append(fs_hz)
        threshold_ms = (GAP_MULTIPLIER / fs_hz * 1000.0) if fs_hz else None
        if threshold_ms is not None and max_gap_ms is not None and max_gap_ms > threshold_ms:
            bad_idx = np.argmax(dt)
            errors.append(
                f"Session {representative[i]['timepoint']}: gap {max_gap_ms:.2f} ms at index {bad_idx} "
                f"(threshold {threshold_ms:.2f} ms = 2×1/fs)."
            )
        table_rows.append({
            "Session ID": representative[i]["timepoint"],
            "Frames": len(df),
            "Median fs (Hz)": round(fs_hz, 2) if fs_hz is not None else None,
            "Max Gap (ms)": round(max_gap_ms, 2) if max_gap_ms is not None else None,
            "n_omega": len(omega_cols_per_session[i]),
            "n_q": len(q_cols_per_session[i]),
            "n_xyz": len(xyz_cols_per_session[i]),
        })

    # Sampling consistency: fs equal across sessions
    if len(fs_list) >= 2 and all(f is not None for f in fs_list):
        if max(fs_list) - min(fs_list) > 0.01:
            errors.append(
                f"Median sampling rate differs across sessions: {fs_list}. "
                "Require consistent f_s across all sessions."
            )

    passed = len(errors) == 0
    return {
        "table_rows": table_rows,
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "session_mapping": mapping,
        "available_timepoints": available_timepoints,
    }


# ---------------------------------------------------------------------------
# Phase 1: Unified Loader & Longitudinal Scaling
# ---------------------------------------------------------------------------


def _get_representative_sessions_with_parquets(
    session_mapping: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter to sessions with existing parquet; pick one per timepoint (T1, T2, T3 order)."""
    existing = [m for m in session_mapping if Path(m["parquet_path"]).exists()]
    by_tp: dict[str, list[dict]] = {}
    for m in existing:
        by_tp.setdefault(m["timepoint"], []).append(m)
    representative = []
    for tp in ("T1", "T2", "T3"):
        if tp in by_tp:
            representative.append(by_tp[tp][0])
    return representative


def _filter_columns_by_joints(
    cols: list[str],
    include_joints: list[str] | None = None,
    exclude_joints: list[str] | None = None,
) -> list[str]:
    """Filter branch columns to keep only those belonging to allowed joints."""
    if include_joints is None and exclude_joints is None:
        return cols
    if include_joints is not None and exclude_joints is not None:
        raise ValueError("Set either include_joints or exclude_joints, not both.")
    filtered = []
    for c in cols:
        joint = c.split("__")[0]
        if include_joints is not None and joint not in include_joints:
            continue
        if exclude_joints is not None and joint in exclude_joints:
            continue
        filtered.append(c)
    return filtered


def prepare_3branch_data(
    session_mapping: list[dict[str, Any]],
    preloaded_dfs: list[pd.DataFrame] | None = None,
    include_joints: list[str] | None = None,
    exclude_joints: list[str] | None = None,
) -> dict[str, Any]:
    """
    Load parquets for representative sessions (one per T1/T2/T3 present), extract branch
    columns, fit one StandardScaler per branch on concatenated T1+T2+T3, transform each
    session separately. Zero-variance/NaN in scaled output are filled via ffill/bfill (not 0), so quaternions stay valid (norm≠0).

    Args:
        session_mapping: list of session dicts with parquet_path, timepoint, etc.
        preloaded_dfs: optional list of pre-loaded (e.g. trimmed) DataFrames, one per
            representative session in canonical T1/T2/T3 order. When provided, parquets
            are NOT re-loaded from disk — use this to inject time-windowed data.
        include_joints: optional list of joint names to INCLUDE (e.g. ["Spine", "Head"]).
            Only columns belonging to these joints enter PCA. None = all joints.
        exclude_joints: optional list of joint names to EXCLUDE (e.g. ["Hips", "LeftFoot"]).
            Columns belonging to these joints are removed. None = no exclusion.
            Set one or the other, not both.

    Returns:
        prepared: dict with keys "dynamics", "pose", "reach". Each branch has:
          - scaled_arrays: list of ndarray (one per session, in timepoint order)
          - columns: list of column names
          - scaler: fitted StandardScaler
          - n_frames_per_session: list of int
          - timepoints: list of str (e.g. ["T1", "T2", "T3"] or subset)
        Also "representative_sessions": list of session dicts used,
              "joint_filter": {"include": ..., "exclude": ..., "joints_used": [...]}.
    """
    representative = _get_representative_sessions_with_parquets(session_mapping)
    if not representative:
        raise ValueError(
            "No parquet files found for session_mapping. Ensure at least one session has "
            "derivatives/step_06_kinematics/{run_id}__kinematics_master.parquet."
        )

    if preloaded_dfs is not None:
        if len(preloaded_dfs) != len(representative):
            raise ValueError(
                f"preloaded_dfs has {len(preloaded_dfs)} entries but {len(representative)} "
                "representative sessions were found. They must match."
            )
        dfs = list(preloaded_dfs)
    else:
        dfs: list[pd.DataFrame] = []
        for m in representative:
            dfs.append(pd.read_parquet(m["parquet_path"]))

    # Column intersection across sessions so all have same feature set
    omega_sets = [set(_omega_columns(df)) for df in dfs]
    q_sets = [set(_q_columns(df)) for df in dfs]
    xyz_sets = [set(_xyz_columns(df)) for df in dfs]
    omega_cols = sorted(set.intersection(*omega_sets)) if omega_sets else []
    q_cols = sorted(set.intersection(*q_sets)) if q_sets else []
    xyz_cols = sorted(set.intersection(*xyz_sets)) if xyz_sets else []

    # Apply joint filter (include/exclude)
    omega_cols = _filter_columns_by_joints(omega_cols, include_joints, exclude_joints)
    q_cols = _filter_columns_by_joints(q_cols, include_joints, exclude_joints)
    xyz_cols = _filter_columns_by_joints(xyz_cols, include_joints, exclude_joints)

    if not omega_cols or not q_cols or not xyz_cols:
        raise ValueError(
            "Missing branch columns after joint filter: omega=%s, q=%s, xyz=%s."
            % (len(omega_cols), len(q_cols), len(xyz_cols))
        )

    timepoints = [m["timepoint"] for m in representative]

    def _scale_branch(cols: list[str], branch_name: str) -> dict[str, Any]:
        # Extract and concatenate
        blocks = [df[cols].values for df in dfs]
        combined = np.vstack(blocks)
        # Fit scaler on combined, transform each block separately
        scaler = StandardScaler()
        scaler.fit(combined)
        scaled_arrays = []
        n_frames_per_session = []
        for i, df in enumerate(dfs):
            X = df[cols].values
            n_frames_per_session.append(len(X))
            s = scaler.transform(X)
            # Handle NaN: ffill then bfill (avoids 0 for quaternions, which would give invalid norm=0)
            s = pd.DataFrame(s).ffill().bfill().to_numpy()
            # Any remaining NaN/inf (e.g. all-NaN column) fallback to 0 so pipeline does not break
            np.nan_to_num(s, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
            scaled_arrays.append(s)
        return {
            "scaled_arrays": scaled_arrays,
            "columns": cols,
            "scaler": scaler,
            "n_frames_per_session": n_frames_per_session,
            "timepoints": timepoints,
        }

    # Collect the unique set of joints that survived the filter
    all_filtered_cols = omega_cols + q_cols + xyz_cols
    joints_used = sorted({c.split("__")[0] for c in all_filtered_cols})

    prepared = {
        "dynamics": _scale_branch(omega_cols, "dynamics"),
        "pose": _scale_branch(q_cols, "pose"),
        "reach": _scale_branch(xyz_cols, "reach"),
        "representative_sessions": representative,
        "joint_filter": {
            "include": include_joints,
            "exclude": exclude_joints,
            "joints_used": joints_used,
        },
    }
    return prepared


def check_scaling_integrity(prepared: dict[str, Any]) -> dict[str, Any]:
    """
    Assert combined scaled features across all sessions: mean ≈ 0, std ≈ 1 or std ≈ 0 (constant), no NaN.
    Zero-variance columns (e.g. Hips position at origin in Reach branch) are valid: scaled = 0, std = 0.
    Returns dict: branch_name -> "PASS" | "FAIL".
    """
    results: dict[str, str] = {}
    for branch_key in ("dynamics", "pose", "reach"):
        data = prepared.get(branch_key)
        if not data:
            results[branch_key] = "FAIL"
            continue
        scaled_arrays = data["scaled_arrays"]
        combined = np.vstack(scaled_arrays)

        if np.any(np.isnan(combined)):
            results[branch_key] = "FAIL"
            continue

        mean_ok = np.all(np.abs(np.mean(combined, axis=0)) < SCALING_MEAN_TOL)
        stds = np.std(combined, axis=0)
        # Accept std ≈ 1 (normal scaled) or std ≈ 0 (constant column, e.g. Hips at origin)
        std_ok = np.all(
            (np.abs(stds - 1.0) < SCALING_STD_TOL) | (stds < SCALING_STD_TOL)
        )
        results[branch_key] = "PASS" if (mean_ok and std_ok) else "FAIL"

    return results


# ---------------------------------------------------------------------------
# Phase 2: 3-Branch PCA Engine
# ---------------------------------------------------------------------------


def run_3branch_pca(scaled_data_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Fit PCA on combined (T1+T2+T3) scaled data per branch; project each session
    into 3D (PC1, PC2, PC3). Full variance spectrum is retained for N90 in Phase 3.
    PCA objects are stored for loadings in Phase 4.

    Args:
        scaled_data_dict: output of prepare_3branch_data() with keys "dynamics", "pose", "reach".

    Returns:
        pca_results: for each branch:
          - pca: fitted sklearn PCA (fitted on all components for full variance spectrum)
          - projected_arrays: list of (n_frames, 3) arrays (PC1, PC2, PC3) per session
          - explained_variance_ratio_: full spectrum (for N90)
          - timepoints: list of session labels
          - n_features: number of input features
    """
    pca_results: dict[str, Any] = {}
    for branch_key in ("dynamics", "pose", "reach"):
        data = scaled_data_dict.get(branch_key)
        if not data:
            continue
        scaled_arrays = data["scaled_arrays"]
        columns = data["columns"]
        timepoints = data["timepoints"]
        combined = np.vstack(scaled_arrays)
        n_samples, n_features = combined.shape

        # Fit PCA on all components to get full variance spectrum (for N90)
        n_components_full = min(n_samples, n_features)
        pca = PCA(n_components=n_components_full)
        pca.fit(combined)

        # Project each session into 3D (first 3 components)
        projected_arrays = []
        for X in scaled_arrays:
            # X @ components_[:3].T = (n_frames, 3)
            proj_3d = X @ pca.components_[:3].T
            projected_arrays.append(proj_3d)

        pca_results[branch_key] = {
            "pca": pca,
            "projected_arrays": projected_arrays,
            "explained_variance_ratio_": pca.explained_variance_ratio_.copy(),
            "timepoints": timepoints,
            "n_features": n_features,
            "columns": columns,
        }
    return pca_results


# ---------------------------------------------------------------------------
# Phase 3: Exploration Metrics (N90 & 3D Convex Hull)
# ---------------------------------------------------------------------------


def calculate_n90(
    pca_results: dict[str, Any],
    prepared: dict[str, Any],
) -> dict[str, Any]:
    """
    For each branch and each timepoint, find the number of components required
    to reach 90% cumulative explained variance (N90). Cumulative variance is
    computed **per session**: we project that session's scaled data onto all
    PCs and use that session's variance along each PC. So even if the global
    PCA needs 40 components for 90% on combined data, T1 might need only 12;
    a jump to a higher N90 in T2 is evidence of increased entropy/complexity.

    Returns:
        n90_results: dict branch_key -> {
            "timepoints": ["T1", "T2", "T3"],
            "n90_per_session": [n90_t1, n90_t2, n90_t3],
        }
        So table: Branch | T1 N90 | T2 N90 | T3 N90.
    """
    n90_results: dict[str, Any] = {}
    for branch_key in ("dynamics", "pose", "reach"):
        res = pca_results.get(branch_key)
        prep = prepared.get(branch_key)
        if not res or not prep:
            continue
        pca = res["pca"]
        timepoints = res["timepoints"]
        scaled_arrays = prep["scaled_arrays"]
        n90_per_session = []
        for X in scaled_arrays:
            # Project this session onto all components; variance is per-session
            Y = X @ pca.components_.T  # (n_frames, n_components)
            var_per_pc = np.var(Y, axis=0)
            total_var = np.sum(var_per_pc)
            if total_var <= 0:
                n90_per_session.append(0)
                continue
            # Sort descending: session variance may reorder PCs relative to global fit
            var_per_pc = np.sort(var_per_pc)[::-1]
            # Cumulative explained variance for this session only
            explained_ratio = var_per_pc / total_var
            cum = np.cumsum(explained_ratio)
            # Smallest k (1-based count) such that cum[k-1] >= 0.9
            idx = np.searchsorted(cum, 0.9)
            n90 = int(idx) + 1
            n90_per_session.append(n90)
        n90_results[branch_key] = {
            "timepoints": timepoints,
            "n90_per_session": n90_per_session,
        }
    return n90_results


def plot_multi_session_variance_curves(
    pca_results: dict[str, Any],
    prepared_data: dict[str, Any],
    branch_key: str,
    save_path: str | Path | None = None,
    dpi: int = 300,
):
    """
    Plot cumulative explained variance vs number of PCs for T1, T2, T3 on one axis.
    Uses per-session variance when projecting onto the branch PCA; curves are averaged
    per timepoint. Horizontal line at 90%; marker at N90 (components to reach 90%) per curve.

    T1 (Blue), T2 (Red), T3 (Green). Legend: T1 (Baseline), T2 (Peak Effect), T3 (Afterglow).
    """
    res = pca_results.get(branch_key)
    prep = prepared_data.get(branch_key)
    if not res or not prep:
        raise ValueError(f"Missing pca_results or prepared_data for branch {branch_key!r}")
    pca = res["pca"]
    timepoints = res["timepoints"]
    scaled_arrays = prep["scaled_arrays"]
    n_components = pca.components_.shape[0]

    # Group session indices by timepoint (dynamic — works with 2 or 3 sessions)
    tp_to_indices: dict[str, list[int]] = {}
    for i, tp in enumerate(timepoints):
        tp_to_indices.setdefault(tp, []).append(i)

    colors = {"T1": "#1f77b4", "T2": "#d62728", "T3": "#2ca02c"}
    labels = {"T1": "T1 (Baseline)", "T2": "T2 (Peak Effect)", "T3": "T3 (Afterglow)"}

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    for tp, label in labels.items():
        indices = tp_to_indices.get(tp, [])
        if not indices:
            continue
        cums = []
        for idx in indices:
            X = scaled_arrays[idx]
            Y = X @ pca.components_.T
            var_per_pc = np.var(Y, axis=0)
            total_var = np.sum(var_per_pc)
            if total_var <= 0:
                continue
            # Sort descending so cumulative curve is monotonically steepest-first
            var_per_pc = np.sort(var_per_pc)[::-1]
            explained_ratio = var_per_pc / total_var
            cum = np.cumsum(explained_ratio)
            cums.append(cum)
        if not cums:
            continue
        cum_avg = np.mean(cums, axis=0)
        x_vals = np.arange(0, n_components + 1)
        y_vals = np.concatenate([[0.0], cum_avg])
        ax.plot(x_vals, y_vals, color=colors[tp], label=label, linewidth=2)
        idx_90 = np.searchsorted(cum_avg, 0.9)
        n90 = min(int(idx_90) + 1, n_components)
        ax.scatter([n90], [0.9], color=colors[tp], s=80, zorder=5, edgecolors="black", linewidths=1)

    ax.axhline(0.9, color="gray", linestyle="--", linewidth=1.5, alpha=0.8)
    ax.set_xlim(0, n_components)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("Number of Principal Components", fontsize=11)
    ax.set_ylabel("Cumulative Explained Variance", fontsize=11)
    ax.legend(loc="lower right", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_title(f"N90 Cumulative Variance — {branch_key.capitalize()} branch", fontsize=12)
    plt.tight_layout()

    if save_path is not None:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    return fig


def calculate_3d_hull_volume(pca_results: dict[str, Any]) -> dict[str, Any]:
    """
    For each branch and each timepoint, compute the volume of the 3D convex hull
    of the points (PC1, PC2, PC3). Requires at least 4 points; otherwise volume = 0.
    Uses qhull_options='QJ' (joggled input) to avoid precision errors on nearly flat
    or degenerate point sets (e.g. Reach/XYZ with little vertical movement in T1).

    Returns:
        volume_results: dict branch_key -> {
            "timepoints": ["T1", "T2", "T3"],
            "volumes": [v_t1, v_t2, v_t3],
        }
        So table: Branch | T1 Volume | T2 Volume | T3 Volume.
    """
    volume_results: dict[str, Any] = {}
    for branch_key in ("dynamics", "pose", "reach"):
        res = pca_results.get(branch_key)
        if not res:
            continue
        projected_arrays = res["projected_arrays"]
        timepoints = res["timepoints"]
        volumes = []
        for points in projected_arrays:
            if points.shape[0] < 4:
                volumes.append(0.0)
                continue
            try:
                hull = ConvexHull(points, qhull_options="QJ")
                volumes.append(float(hull.volume))
            except Exception:
                volumes.append(0.0)
        volume_results[branch_key] = {
            "timepoints": timepoints,
            "volumes": volumes,
        }
    return volume_results


# ---------------------------------------------------------------------------
# Phase 4: Anatomical Loadings (Top 5 Joint Contributors)
# ---------------------------------------------------------------------------

# Number of top joints to report per branch
TOP_N_JOINTS = 5


def _feature_to_joint(column_name: str) -> str:
    """Extract joint name from branch column (e.g. 'Hips__zeroed_rel_omega_mag' -> 'Hips')."""
    return column_name.split("__")[0]


def calculate_joint_loadings(pca_results: dict[str, Any]) -> dict[str, Any]:
    """
    For each branch, compute Anatomical Contribution Index: sum of squared loadings
    for PC1, PC2, PC3 per feature, aggregated by joint, normalized to 100%.
    Returns Top 5 joints per branch for the "Who" of the movement.

    Steps:
      - Take PCA.components_ for PC1, PC2, PC3.
      - Per feature: Loadings_Total = sqrt(PC1^2 + PC2^2 + PC3^2).
      - Aggregate by joint (sum over features belonging to that joint).
      - Normalize so total across joints = 1.0 (report as %).
      - Rank and return Top 5 joints with highest contribution.

    Returns:
        loadings_results: dict branch_key -> {
            "top5_joints": [joint1, joint2, ...],
            "top5_pct": [pct1, pct2, ...],  # 0-100
        }
    """
    loadings_results: dict[str, Any] = {}
    for branch_key in ("dynamics", "pose", "reach"):
        res = pca_results.get(branch_key)
        if not res:
            continue
        pca = res["pca"]
        columns = res["columns"]
        # (3, n_features) loadings for PC1, PC2, PC3
        loadings_3 = pca.components_[:3, :]
        n_features = loadings_3.shape[1]
        if n_features != len(columns):
            continue
        # Per-feature contribution: L2 norm of (PC1, PC2, PC3) loadings
        contribution_per_feature = np.sqrt(np.sum(loadings_3 ** 2, axis=0))
        # Aggregate by joint
        joint_score: dict[str, float] = {}
        for j, col in enumerate(columns):
            joint = _feature_to_joint(col)
            joint_score[joint] = joint_score.get(joint, 0.0) + contribution_per_feature[j]
        total = sum(joint_score.values())
        if total <= 0:
            loadings_results[branch_key] = {"top5_joints": [], "top5_pct": []}
            continue
        # Normalize to 1.0 (we'll report as %)
        for k in joint_score:
            joint_score[k] /= total
        # Top 5
        sorted_joints = sorted(
            joint_score.items(), key=lambda x: x[1], reverse=True
        )[:TOP_N_JOINTS]
        top5_joints = [j for j, _ in sorted_joints]
        top5_pct = [round(100.0 * pct, 2) for _, pct in sorted_joints]
        loadings_results[branch_key] = {
            "top5_joints": top5_joints,
            "top5_pct": top5_pct,
        }
    return loadings_results


def _session_joint_contributions(pca: PCA, session_data: np.ndarray) -> np.ndarray:
    """
    Variance contribution of each feature SPECIFIC to this session.
    Projects session onto global PC space, measures actual variance along each PC (local eigenvalues),
    attributes back to features via squared loadings. Returns (n_features,) contribution per feature.
    """
    projected_scores = pca.transform(session_data)  # (n_samples, n_components)
    local_variance = np.var(projected_scores, axis=0)  # (n_components,) — session's actual variance, not pca.explained_variance_
    squared_loadings = pca.components_ ** 2  # (n_components, n_features)
    joint_contributions = np.dot(local_variance, squared_loadings)  # (n_features,)
    return joint_contributions


def calculate_session_joint_loadings(
    pca_results: dict[str, Any],
    prepared_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Per-session (per-T) anatomical loadings: variance contribution of each joint
    SPECIFIC to that session. Uses the session's actual projected variance (local
    eigenvalues) weighted by squared PC loadings, not global explained_variance_,
    so T1 and T2 differ when their variance structure differs.

    Returns:
        session_loadings: dict branch_key -> {
            "timepoints": ["T1", "T2", "T3"],
            "joint_pct_per_session": [
                {"JointA": pct_t1, "JointB": ...},  # T1
                {"JointA": pct_t2, ...},             # T2
                {"JointA": pct_t3, ...},             # T3
            ],
        }
    """
    session_loadings: dict[str, Any] = {}
    for branch_key in ("dynamics", "pose", "reach"):
        res = pca_results.get(branch_key)
        prep = prepared_data.get(branch_key)
        if not res or not prep:
            continue
        pca = res["pca"]
        columns = res["columns"]
        scaled_arrays = prep["scaled_arrays"]
        timepoints = res["timepoints"]

        joint_to_idx: dict[str, list[int]] = {}
        for j, col in enumerate(columns):
            joint = _feature_to_joint(col)
            joint_to_idx.setdefault(joint, []).append(j)

        joint_pct_per_session: list[dict[str, float]] = []
        for X in scaled_arrays:
            attr_per_feature = _session_joint_contributions(pca, X)  # (n_features,)
            total = float(np.sum(attr_per_feature))
            if total <= 0:
                joint_pct_per_session.append({j: 0.0 for j in joint_to_idx})
                continue
            joint_attr = {joint: float(np.sum(attr_per_feature[idx])) for joint, idx in joint_to_idx.items()}
            s = sum(joint_attr.values())
            joint_pct = {j: 100.0 * (v / s) for j, v in joint_attr.items()}
            joint_pct_per_session.append(joint_pct)
        session_loadings[branch_key] = {
            "timepoints": timepoints,
            "joint_pct_per_session": joint_pct_per_session,
        }
    return session_loadings


def longitudinal_joint_shift_table(
    session_loadings: dict[str, Any],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """
    Build Longitudinal Joint Shift table with dynamic columns based on available timepoints.
    Columns: Branch | Joint | {tp} % ... | Change ({tp2}-{tp1}).
    Top N joints per branch ranked by absolute Change. If only one session, no Change.

    Returns:
        List of row dicts for DataFrame.
    """
    rows: list[dict[str, Any]] = []
    for branch_key in ("dynamics", "pose", "reach"):
        data = session_loadings.get(branch_key)
        if not data:
            continue
        timepoints = data["timepoints"]
        joint_pct = data["joint_pct_per_session"]
        if not joint_pct:
            continue
        all_joints = sorted(joint_pct[0].keys())

        if len(timepoints) < 2 or len(joint_pct) < 2:
            # Only one session: show top N by first session %
            t1_order = sorted(all_joints, key=lambda j: joint_pct[0].get(j, 0.0), reverse=True)[:top_n]
            for joint in t1_order:
                r: dict[str, Any] = {"Branch": branch_key, "Joint": joint}
                for i, tp in enumerate(timepoints):
                    r[f"{tp} %"] = round(joint_pct[i].get(joint, 0.0), 2) if i < len(joint_pct) else None
                rows.append(r)
            continue

        # >= 2 sessions: compute change between first two timepoints
        tp1, tp2 = timepoints[0], timepoints[1]
        t1_pct = joint_pct[0]
        t2_pct = joint_pct[1]
        changes = [(j, t2_pct.get(j, 0.0) - t1_pct.get(j, 0.0)) for j in all_joints]
        changes.sort(key=lambda x: abs(x[1]), reverse=True)
        top_joints = [j for j, _ in changes[:top_n]]
        for joint in top_joints:
            r = {"Branch": branch_key, "Joint": joint}
            for i, tp in enumerate(timepoints):
                r[f"{tp} %"] = round(joint_pct[i].get(joint, 0.0), 2) if i < len(joint_pct) else None
            r[f"Change ({tp2}-{tp1})"] = round(t2_pct.get(joint, 0.0) - t1_pct.get(joint, 0.0), 2)
            rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Phase 4 Upgrade: Whole-System Statistics (Gini, Shannon, Axial-Peripheral, Sparseness)
# ---------------------------------------------------------------------------

# Complete partition of the 19-joint skeleton into Axial (core) vs Peripheral (limb extremities).
# Proximal limb segments (Shoulder, UpLeg, Arm, Leg) are excluded from both — they are transitional.
AXIAL_JOINTS = ("Hips", "Spine", "Spine1", "Neck", "Head")
PERIPHERAL_JOINTS = (
    "LeftForeArm", "RightForeArm",   # distal arm
    "LeftHand", "RightHand",          # terminal arm
    "LeftFoot", "RightFoot",          # terminal leg
)
# Transitional (neither axial nor peripheral): LeftShoulder, RightShoulder, LeftArm, RightArm,
# LeftUpLeg, RightUpLeg, LeftLeg, RightLeg. These 8 joints are intentionally excluded from
# the ratio so it cleanly contrasts core vs distal extremities.


def calculate_gini(array: np.ndarray) -> float:
    """Calculates Gini coefficient using the robust Lorenz Curve method."""
    array = np.abs(np.array(array, dtype=np.float64)).flatten()
    if array.size == 0:
        return 0.0
    if np.amin(array) < 0:
        array = array - np.amin(array)
    array = array + 0.0000001  # Prevent div/0
    array = np.sort(array)  # Sort is required for Lorenz
    index = np.arange(1, array.shape[0] + 1)
    n = array.shape[0]
    return float((np.sum((2 * index - n - 1) * array)) / (n * np.sum(array)))


def _gini(proportions: np.ndarray) -> float:
    """Gini coefficient (0 = equality, 1 = one has all). Delegates to calculate_gini."""
    return calculate_gini(proportions)


def _shannon_entropy(proportions: np.ndarray) -> float:
    """Shannon entropy (natural log). proportions sum to 1. 0*log(0)=0."""
    p = np.asarray(proportions).flatten()
    p = p[p > 0]
    return float(-np.sum(p * np.log(p)))


def _axial_peripheral_ratio(joint_pct: dict[str, float]) -> float:
    """Central (Spine/Neck/Hips/Head) vs Distal (Hands/Feet). Ratio = axial_sum / peripheral_sum (%)."""
    axial = sum(joint_pct.get(j, 0.0) for j in AXIAL_JOINTS)
    peripheral = sum(joint_pct.get(j, 0.0) for j in PERIPHERAL_JOINTS)
    if peripheral <= 0:
        return float(axial) if axial > 0 else 0.0
    return axial / peripheral


def _sparseness(joint_pct: dict[str, float]) -> float:
    """Percentage of joints with <1% contribution (silent)."""
    if not joint_pct:
        return 0.0
    n_silent = sum(1 for v in joint_pct.values() if v < 1.0)
    return 100.0 * n_silent / len(joint_pct)


def get_index_definitions() -> dict[str, str]:
    """Return short names and full definitions for the four whole-system indices (for Legend)."""
    return {
        "Gini Coefficient (Inequality)": (
            "Calculated by reconstructing session variance from the full PCA weight matrix. "
            "A low Gini in T2 indicates that the 'movement budget' has shifted from being dominated "
            "by a few joints to a more democratic, whole-body integration."
        ),
        "Shannon Entropy (Diversity)": (
            "Measures the information density of the joint-variance distribution. "
            "Based on the probability of each joint contributing to the total movement. "
            "Higher entropy in T2 suggests the motor system is exploring a more diverse and less "
            "predictable set of joint combinations."
        ),
        "Axial-Peripheral Ratio (Core vs. Limbs)": (
            "A comparison of 'Central' (Spine/Neck/Hips) vs. 'Distal' (Hands/Feet) variance loadings. "
            "An increase in T2 suggests the subject has shifted toward 'embodied' movement, "
            "where the core of the body drives the behavioral complexity rather than just the extremities."
        ),
        "Sparseness (System Activation)": (
            "The percentage of the body that remains 'silent' (<1% contribution). "
            "Lower sparseness in T2 indicates that a larger portion of the subject's physical "
            "degrees of freedom have been 'awakened' by the intervention."
        ),
    }


def calculate_whole_system_stats(
    pca_results: dict[str, Any],
    prepared_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Whole-system indices per branch and per session using **all** PCs (consistent with
    _session_joint_contributions which also uses the full PCA). For each session:
      1. Project onto ALL PCs: Y = pca.transform(X)   -> (n_frames, n_components)
      2. Local variance per PC: var_pc = np.var(Y, 0)  -> (n_components,)
      3. Attribute to features: attr_j = Σ_k var_pc[k] · w_kj²
      4. Aggregate by joint, normalize, compute Gini / Shannon / Axial-Peripheral / Sparseness.

    Returns:
        stats: dict branch_key -> {
            "timepoints": ["T1", "T2", "T3"],
            "metrics_per_session": [
                {"Gini": v, "Shannon": v, "AxialPeripheral": v, "Sparseness": v},  # T1
                ...
            ],
        }
    """
    stats: dict[str, Any] = {}
    for branch_key in ("dynamics", "pose", "reach"):
        res = pca_results.get(branch_key)
        prep = prepared_data.get(branch_key)
        if not res or not prep:
            continue
        pca = res["pca"]
        columns = res["columns"]
        scaled_arrays = prep["scaled_arrays"]
        timepoints = res["timepoints"]
        joint_to_idx: dict[str, list[int]] = {}
        for j, col in enumerate(columns):
            joint = _feature_to_joint(col)
            joint_to_idx.setdefault(joint, []).append(j)

        metrics_per_session: list[dict[str, float]] = []
        for X in scaled_arrays:
            # Use all PCs (same as _session_joint_contributions)
            attr_per_feature = _session_joint_contributions(pca, X)  # (n_features,)
            total_attr = float(np.sum(attr_per_feature))
            if total_attr <= 0:
                joint_pct = {j: 100.0 / len(joint_to_idx) for j in joint_to_idx}
            else:
                joint_attr = {}
                for joint, idx in joint_to_idx.items():
                    joint_attr[joint] = float(np.sum(attr_per_feature[idx]))
                s = sum(joint_attr.values())
                joint_pct = {j: 100.0 * (v / s) for j, v in joint_attr.items()}
            p_prop = np.array([joint_pct.get(j, 0.0) / 100.0 for j in joint_to_idx])
            p_prop = p_prop / np.sum(p_prop) if np.sum(p_prop) > 0 else p_prop
            metrics_per_session.append({
                "Gini": _gini(p_prop),
                "Shannon": _shannon_entropy(p_prop),
                "AxialPeripheral": _axial_peripheral_ratio(joint_pct),
                "Sparseness": _sparseness(joint_pct),
            })
        stats[branch_key] = {
            "timepoints": timepoints,
            "metrics_per_session": metrics_per_session,
        }
    return stats


def longitudinal_strategy_table(stats_results: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Build Longitudinal Strategy Table with dynamic columns based on available timepoints.
    Columns: Branch | Metric | {tp1} | {tp2} | ... | % Change ({tp1} vs {tp2}).
    One row per (branch, metric). % Change = (tp2 - tp1) / |tp1| * 100 when tp1 != 0.
    """
    metric_keys = ["Gini", "Shannon", "AxialPeripheral", "Sparseness"]
    rows: list[dict[str, Any]] = []
    for branch_key in ("dynamics", "pose", "reach"):
        data = stats_results.get(branch_key)
        if not data:
            continue
        timepoints = data["timepoints"]
        metrics_per = data["metrics_per_session"]
        for mk in metric_keys:
            r: dict[str, Any] = {"Branch": branch_key, "Metric": mk}
            for i, tp in enumerate(timepoints):
                val = metrics_per[i].get(mk, 0.0) if i < len(metrics_per) else None
                r[tp] = round(val, 4) if val is not None else None
            # % Change between first two timepoints
            if len(timepoints) >= 2:
                v1 = metrics_per[0].get(mk, 0.0) if len(metrics_per) > 0 else None
                v2 = metrics_per[1].get(mk, 0.0) if len(metrics_per) > 1 else None
                if v1 is not None and v2 is not None and isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    pct_change = (v2 - v1) / (abs(v1) + 1e-12) * 100.0
                    r[f"% Change ({timepoints[0]} vs {timepoints[1]})"] = round(pct_change, 2)
                else:
                    r[f"% Change ({timepoints[0]} vs {timepoints[1]})"] = None
            rows.append(r)
    return rows


def plot_index_trends(
    stats_results: dict[str, Any],
    volume_results: dict[str, Any],
    n90_results: dict[str, Any],
    save_dir: str | Path | None = None,
    dpi: int = 300,
) -> list[tuple[str, Any]]:
    """
    Create five standalone line/point plots (one per index): Volume, Shannon Entropy,
    Gini Coefficient, Sparseness, Axial-Peripheral Ratio. Each figure: x = T1, T2, T3;
    three lines (Dynamics Blue, Pose Orange, Reach Green) with distinct markers.
    Clean white background, high resolution. If save_dir is set, save as Trend_*.png.

    Returns:
        List of (index_name, matplotlib Figure) for display or further saving.
    """
    # Derive available timepoints from data (works with 2 or 3 sessions)
    _all_tps: list[str] = []
    for bk in ("dynamics", "pose", "reach"):
        _d = stats_results.get(bk, {})
        if _d.get("timepoints"):
            _all_tps = list(_d["timepoints"])
            break
    # Fallback: try volume_results
    if not _all_tps:
        for bk in ("dynamics", "pose", "reach"):
            _d = volume_results.get(bk, {})
            if _d.get("timepoints"):
                _all_tps = list(_d["timepoints"])
                break
    timepoints = _all_tps or ["T1", "T2", "T3"]
    branch_order = ("dynamics", "pose", "reach")
    branch_colors = {"dynamics": "#1f77b4", "pose": "#ff7f0e", "reach": "#2ca02c"}
    branch_labels = {"dynamics": "Dynamics", "pose": "Pose", "reach": "Reach"}
    markers = ["o", "s", "D"]

    def _make_trend_figure(
        title: str,
        ylabel: str,
        series: dict[str, list[float]],
    ) -> Any:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")
        x = np.arange(len(timepoints))
        for i, branch_key in enumerate(branch_order):
            vals = series.get(branch_key)
            if not vals or len(vals) != len(timepoints):
                continue
            ax.plot(
                x,
                vals,
                color=branch_colors[branch_key],
                label=branch_labels[branch_key],
                marker=markers[i % len(markers)],
                markersize=10,
                linewidth=2,
            )
        ax.set_xticks(x)
        ax.set_xticklabels(timepoints)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=12)
        ax.legend(loc="best", fontsize=9)
        ax.set_facecolor("white")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        return fig

    # Volume: from volume_results
    vol_series: dict[str, list[float]] = {}
    for branch_key in branch_order:
        data = volume_results.get(branch_key, {})
        vol_series[branch_key] = list(data.get("volumes", []))

    # Strategy indices: from stats_results (Gini, Shannon, Sparseness, AxialPeripheral)
    stats_series: dict[str, dict[str, list[float]]] = {}
    for branch_key in branch_order:
        data = stats_results.get(branch_key, {})
        metrics_per = data.get("metrics_per_session", [])
        stats_series[branch_key] = {
            "Gini": [m.get("Gini", 0.0) for m in metrics_per],
            "Shannon": [m.get("Shannon", 0.0) for m in metrics_per],
            "Sparseness": [m.get("Sparseness", 0.0) for m in metrics_per],
            "AxialPeripheral": [m.get("AxialPeripheral", 0.0) for m in metrics_per],
        }

    out: list[tuple[str, Any]] = []
    figures = [
        ("Volume", "3D Convex Hull Volume", "Volume", vol_series, "Volume"),
        ("Entropy", "Shannon Entropy", "Entropy", {k: v["Shannon"] for k, v in stats_series.items()}, "Shannon Entropy"),
        ("Gini", "Gini Coefficient", "Gini", {k: v["Gini"] for k, v in stats_series.items()}, "Gini"),
        ("Sparseness", "Sparseness (% joints &lt;1% contribution)", "Sparseness (%)", {k: v["Sparseness"] for k, v in stats_series.items()}, "Sparseness"),
        ("AxialPeripheral", "Axial–Peripheral Ratio", "Ratio", {k: v["AxialPeripheral"] for k, v in stats_series.items()}, "Axial-Peripheral"),
    ]
    for save_name, title, ylabel, series, _ in figures:
        fig = _make_trend_figure(title, ylabel, series)
        out.append((save_name, fig))
        if save_dir is not None:
            path = Path(save_dir) / f"Trend_{save_name}.png"
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    return out


# ---------------------------------------------------------------------------
# Phase 5: 12-Plot Dashboard (4x3: 4 columns × 3 branches)
# ---------------------------------------------------------------------------

# Max points per session in 3D scatter (keep HTML responsive)
MAX_POINTS_3D = 1500

# Timepoint colors for 3D and bars
TP_COLORS = {"T1": "rgb(31, 119, 180)", "T2": "rgb(214, 39, 40)", "T3": "rgb(44, 160, 44)"}


def create_results_dashboard(
    pca_results: dict[str, Any],
    n90_results: dict[str, Any],
    volume_results: dict[str, Any],
    stats_results: dict[str, Any],
    session_loadings: dict[str, Any],
    output_path: str | Path | None = None,
) -> Any:
    """
    Build the 12-plot dashboard: 4 columns × 3 rows (Dynamics, Pose, Reach).
    Col 1: 3D PCA scatter (PC1, PC2, PC3) by T1/T2/T3.
    Col 2: Complexity (N90 & Volume) bar chart.
    Col 3: Strategy (Gini & Shannon) bar chart.
    Col 4: Anatomy (Top 5 joints for T2) bar chart.
    Saves to output_path if provided. Returns Plotly Figure.
    """
    if go is None or make_subplots is None:
        raise ImportError("Plotly is required for create_results_dashboard. Install with: pip install plotly")

    branch_order = ["dynamics", "pose", "reach"]
    row_titles = ["Dynamics (ω)", "Pose (q)", "Reach (XYZ)"]
    # Col 2: separate Y-axes for N90 (integers) vs Volume (large values) to avoid scale distortion
    specs = []
    for _ in range(3):
        specs.append([
            {"type": "scatter3d"},
            {"type": "xy", "secondary_y": True},
            {"type": "xy"},
            {"type": "xy"},
        ])
    # Determine which timepoint to feature in anatomy column
    _any_tps = list((pca_results.get("dynamics") or pca_results.get("pose") or pca_results.get("reach", {})).get("timepoints", []))
    _anat_label = "T2" if "T2" in _any_tps else (_any_tps[-1] if _any_tps else "?")
    _anat_title = f"Anatomy (Top 5 {_anat_label})"
    subplot_titles = [
        "Spatial (3D PCA)", "Complexity (N90 & Vol)", "Strategy (Gini & Entropy)", _anat_title,
        "Spatial (3D PCA)", "Complexity (N90 & Vol)", "Strategy (Gini & Entropy)", _anat_title,
        "Spatial (3D PCA)", "Complexity (N90 & Vol)", "Strategy (Gini & Entropy)", _anat_title,
    ]
    fig = make_subplots(
        rows=3,
        cols=4,
        specs=specs,
        subplot_titles=subplot_titles,
        vertical_spacing=0.15,
        horizontal_spacing=0.1,
    )

    for row_idx, branch_key in enumerate(branch_order):
        r = row_idx + 1
        # ---- Col 1: 3D scatter ----
        res = pca_results.get(branch_key)
        if res:
            projected_arrays = res["projected_arrays"]
            timepoints = res["timepoints"]
            for tp_idx, (proj, tp) in enumerate(zip(projected_arrays, timepoints)):
                n_pts = proj.shape[0]
                if n_pts > MAX_POINTS_3D:
                    ii = np.random.choice(n_pts, MAX_POINTS_3D, replace=False)
                    proj = proj[ii]
                color = TP_COLORS.get(tp, "rgb(128,128,128)")
                fig.add_trace(
                    go.Scatter3d(
                        x=proj[:, 0],
                        y=proj[:, 1],
                        z=proj[:, 2],
                        mode="markers",
                        marker=dict(size=1.2, opacity=0.4, color=color),
                        name=f"{tp}",
                        legendgroup=tp,
                    ),
                    row=r,
                    col=1,
                )

        # ---- Col 2: N90 (left Y) & Volume (right Y) in canonical T1,T2,T3 order ----
        n90_data = n90_results.get(branch_key, {})
        vol_data = volume_results.get(branch_key, {})
        tps_raw = vol_data.get("timepoints", n90_data.get("timepoints", []))
        n90_vals_raw = n90_data.get("n90_per_session", [])
        vol_vals_raw = vol_data.get("volumes", [])
        if tps_raw and len(tps_raw) == len(n90_vals_raw) == len(vol_vals_raw):
            canonical_order = ["T1", "T2", "T3"]
            idx = [tps_raw.index(t) for t in canonical_order if t in tps_raw]
            tps = [tps_raw[i] for i in idx]
            n90_vals = [n90_vals_raw[i] for i in idx]
            vol_vals = [vol_vals_raw[i] for i in idx]
            fig.add_trace(
                go.Bar(x=tps, y=n90_vals, name="N90", marker_color="steelblue", legendgroup="n90"),
                row=r, col=2, secondary_y=False,
            )
            fig.add_trace(
                go.Bar(x=tps, y=vol_vals, name="Volume", marker_color="coral", legendgroup="vol"),
                row=r, col=2, secondary_y=True,
            )

        # ---- Col 3: Gini & Shannon ----
        st = stats_results.get(branch_key, {})
        metrics_per = st.get("metrics_per_session", [])
        tps_st = st.get("timepoints", [])
        if tps_st and metrics_per:
            gini_vals = [m.get("Gini", 0) for m in metrics_per]
            shannon_vals = [m.get("Shannon", 0) for m in metrics_per]
            fig.add_trace(
                go.Bar(x=tps_st, y=gini_vals, name="Gini", marker_color="darkgreen", legendgroup="gini"),
                row=r, col=3,
            )
            fig.add_trace(
                go.Bar(x=tps_st, y=shannon_vals, name="Shannon", marker_color="darkorange", legendgroup="shannon"),
                row=r, col=3,
            )

        # ---- Col 4: Top 5 joints (prefer T2 if available, else last session) ----
        sl = session_loadings.get(branch_key, {})
        joint_pct_list = sl.get("joint_pct_per_session", [])
        sl_tps = sl.get("timepoints", [])
        _feat_idx = sl_tps.index("T2") if "T2" in sl_tps else (len(joint_pct_list) - 1 if joint_pct_list else 0)
        if joint_pct_list and _feat_idx < len(joint_pct_list):
            t2_pct = joint_pct_list[_feat_idx]
            sorted_joints = sorted(t2_pct.items(), key=lambda x: x[1], reverse=True)[:5]
            joints = [j for j, _ in sorted_joints]
            pcts = [round(v, 1) for _, v in sorted_joints]
            text_labels = [f"{p}%" for p in pcts]
            fig.add_trace(
                go.Bar(
                    x=joints,
                    y=pcts,
                    text=text_labels,
                    textposition="outside",
                    name="T2 %",
                    marker_color="crimson",
                    legendgroup="anatomy",
                ),
                row=r, col=4,
            )

    # Derive subject label from first session run_id (e.g. "671_T1_..." -> "671")
    _first_tp = list(pca_results.values())[0].get("timepoints", []) if pca_results else []
    _tp_label = " / ".join(_first_tp) if _first_tp else "T1/T2/T3"
    fig.update_layout(
        title_text=f"Behavioral Analysis Dashboard ({_tp_label}) — 4×3",
        height=900,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.12,
            xanchor="center",
            x=0.5,
            title_text="Timepoint",
        ),
    )
    # Axis labels and cube aspect for 3D scenes
    for scene_name in ["scene", "scene2", "scene3"]:
        if scene_name in fig.layout:
            fig.layout[scene_name].update(
                xaxis_title="PC1",
                yaxis_title="PC2",
                zaxis_title="PC3",
                aspectmode="cube",
            )

    return fig


# Phase 6: Sectional "Museum Grade" report — one figure per branch, hero + logic + anatomy
TP_COLORS_DEEP = {"T1": "rgb(0, 51, 102)", "T2": "rgb(204, 0, 0)", "T3": "rgb(76, 153, 76)"}  # Deep Blue, Vibrant Red, Soft Green


def create_branch_section_figure(
    branch_key: str,
    branch_title: str,
    branch_subtitle: str,
    pca_results: dict[str, Any],
    n90_results: dict[str, Any],
    volume_results: dict[str, Any],
    stats_results: dict[str, Any],
    session_loadings: dict[str, Any],
) -> Any:
    """
    One full-section figure for a single branch: Hero 3D (left 60%), Logic panel (right 40%:
    N90, Volume, Gini/Entropy bars), Anatomy footer (full width). Marker size=1.5, opacity=0.3.
    """
    if go is None or make_subplots is None:
        raise ImportError("Plotly is required. Install with: pip install plotly")

    # Determine which timepoint to feature in "Top joints" panel
    res_tp = pca_results.get(branch_key, {})
    _tps = res_tp.get("timepoints", [])
    # Prefer T2 if available, otherwise last available timepoint
    if "T2" in _tps:
        _anatomy_tp = "T2"
    elif _tps:
        _anatomy_tp = _tps[-1]
    else:
        _anatomy_tp = "?"

    specs = [
        [{"type": "scatter3d"}, {"type": "xy"}],
        [None, {"type": "xy"}],
        [None, {"type": "xy"}],
        [{"type": "xy", "colspan": 2}, None],
    ]
    fig = make_subplots(
        rows=4,
        cols=2,
        specs=specs,
        row_heights=[0.48, 0.17, 0.17, 0.18],
        column_widths=[0.6, 0.4],
        vertical_spacing=0.06,
        horizontal_spacing=0.05,
        subplot_titles=("3D PCA — Spatial footprint", "N90 (complexity)", "Volume (exploration)", "Gini & Entropy", f"Top joints ({_anatomy_tp} %)"),
    )

    res = pca_results.get(branch_key)
    if res:
        projected_arrays = res["projected_arrays"]
        timepoints = res["timepoints"]
        for proj, tp in zip(projected_arrays, timepoints):
            n_pts = proj.shape[0]
            if n_pts > MAX_POINTS_3D:
                ii = np.random.choice(n_pts, MAX_POINTS_3D, replace=False)
                proj = proj[ii]
            color = TP_COLORS_DEEP.get(tp, "rgb(128,128,128)")
            fig.add_trace(
                go.Scatter3d(
                    x=proj[:, 0], y=proj[:, 1], z=proj[:, 2],
                    mode="markers",
                    marker=dict(size=1.5, opacity=0.3, color=color),
                    name=tp, legendgroup=tp,
                ),
                row=1, col=1,
            )

    n90_data = n90_results.get(branch_key, {})
    vol_data = volume_results.get(branch_key, {})
    tps = n90_data.get("timepoints", vol_data.get("timepoints", []))
    if tps:
        n90_vals = n90_data.get("n90_per_session", [])
        fig.add_trace(
            go.Bar(x=tps, y=n90_vals, text=n90_vals, textposition="outside", texttemplate="%{y}",
                   marker_color="steelblue", showlegend=False),
            row=1, col=2,
        )
        vol_vals = vol_data.get("volumes", [])
        fig.add_trace(
            go.Bar(x=tps, y=vol_vals, text=[f"{v:.2f}" for v in vol_vals], textposition="outside",
                   marker_color="coral", showlegend=False),
            row=2, col=2,
        )
    st = stats_results.get(branch_key, {})
    metrics_per = st.get("metrics_per_session", [])
    tps_st = st.get("timepoints", [])
    if tps_st and metrics_per:
        gini_vals = [m.get("Gini", 0) for m in metrics_per]
        shannon_vals = [m.get("Shannon", 0) for m in metrics_per]
        fig.add_trace(
            go.Bar(x=tps_st, y=gini_vals, text=[f"{v:.3f}" for v in gini_vals], textposition="outside",
                   name="Gini", marker_color="darkgreen", legendgroup="gini"),
            row=3, col=2,
        )
        fig.add_trace(
            go.Bar(x=tps_st, y=shannon_vals, text=[f"{v:.3f}" for v in shannon_vals], textposition="outside",
                   name="Entropy", marker_color="darkorange", legendgroup="entropy"),
            row=3, col=2,
        )
    sl = session_loadings.get(branch_key, {})
    joint_pct_list = sl.get("joint_pct_per_session", [])
    sl_tps = sl.get("timepoints", [])
    # Find the index for the featured timepoint (_anatomy_tp)
    _anat_idx = sl_tps.index(_anatomy_tp) if _anatomy_tp in sl_tps else (len(joint_pct_list) - 1 if joint_pct_list else 0)
    if joint_pct_list and _anat_idx < len(joint_pct_list):
        featured_pct = joint_pct_list[_anat_idx]
        sorted_joints = sorted(featured_pct.items(), key=lambda x: x[1], reverse=True)[:10]
        joints = [j for j, _ in sorted_joints]
        pcts = [round(v, 1) for _, v in sorted_joints]
        fig.add_trace(
            go.Bar(x=joints, y=pcts, text=[f"{p}%" for p in pcts], textposition="outside",
                   marker_color="crimson", showlegend=False),
            row=4, col=1,
        )

    fig.update_layout(
        title_text=f"{branch_title}<br><sub>{branch_subtitle}</sub>",
        height=700,
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=1.02, xanchor="center", x=0.5),
    )
    for scene_name in ["scene"]:
        if scene_name in fig.layout:
            fig.layout[scene_name].update(
                xaxis_title="PC1", yaxis_title="PC2", zaxis_title="PC3",
                aspectmode="cube",
                camera=dict(eye=dict(x=1.4, y=1.4, z=1.0)),
            )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig


def create_phase6_branch_figures(
    pca_results: dict[str, Any],
    n90_results: dict[str, Any],
    volume_results: dict[str, Any],
    stats_results: dict[str, Any],
    session_loadings: dict[str, Any],
) -> list[tuple[str, str, Any]]:
    """Returns list of (branch_key, subtitle, figure) for Dynamics, Pose, Reach."""
    branches = [
        ("dynamics", "Dynamics (ω): How — rotational speed & rhythmic complexity", "Rotational dynamics across joints."),
        ("pose", "Pose (q): What — body shapes & postures", "Quaternion pose space exploration."),
        ("reach", "Reach (XYZ): Where the body moves in space", "Volumetric reach (Hips at origin)."),
    ]
    out = []
    for branch_key, title, subtitle in branches:
        fig = create_branch_section_figure(
            branch_key, title, subtitle,
            pca_results, n90_results, volume_results, stats_results, session_loadings,
        )
        out.append((branch_key, subtitle, fig))
    return out


# Metric definitions for the clean HTML report (integrated below charts)
N90_DEFINITION = (
    "N90: Number of principal components required to explain 90% of the variance in that session. "
    "Higher N90 indicates more complex, less repetitive movement."
)
GINI_DEFINITION = (
    "Gini Coefficient: Reconstructs session variance from the PCA weight matrix. "
    "A low Gini in T2 indicates a shift from few dominant joints to more democratic, whole-body integration."
)
ENTROPY_DEFINITION = (
    "Shannon Entropy: Information density of the joint-variance distribution. "
    "Higher entropy in T2 suggests the motor system is exploring more diverse, less predictable joint combinations."
)
VOLUME_DEFINITION = (
    "Volume: 3D convex hull of the (PC1, PC2, PC3) cloud per session. "
    "Larger volume in T2 indicates broader spatial exploration in the principal-component space."
)
SPARSENESS_DEFINITION = (
    "Sparseness (System Activation): The percentage of joints with &lt;1% contribution to variance. "
    "Lower sparseness in T2 indicates that more of the body's degrees of freedom have been activated by the intervention."
)
AXIAL_PERIPHERAL_DEFINITION = (
    "Axial–Peripheral Ratio: Central (Spine/Neck/Hips) vs distal (Hands/Feet) variance loadings. "
    "An increase in T2 suggests a shift toward core-driven, embodied movement."
)


def image_to_base64(path: str | Path) -> str:
    """Read image file and return base64-encoded string for portable HTML embedding."""
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


def save_index_trends_report_html(
    output_path: str | Path,
    image_dir: str | Path,
    subject_id: str = "671",
    available_timepoints: list[str] | None = None,
) -> None:
    """
    Generate an HTML report with five chapters (one per index): Volume, Shannon Entropy,
    Gini Coefficient, Sparseness, Axial–Peripheral Ratio. Each chapter contains the trend
    plot image and the generic explanation / PCA reconstruction logic below it.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img_dir = Path(image_dir)
    try:
        rel_img = img_dir.relative_to(out.parent)
        img_prefix = str(rel_img).replace("\\", "/")
    except ValueError:
        img_prefix = str(img_dir).replace("\\", "/")
    prefix = f"{img_prefix}/" if img_prefix != "." else ""

    definitions = get_index_definitions()
    chapters = [
        ("Volume", "Trend_Volume.png", VOLUME_DEFINITION),
        ("Shannon Entropy", "Trend_Entropy.png", definitions.get("Shannon Entropy (Diversity)", ENTROPY_DEFINITION)),
        ("Gini Coefficient", "Trend_Gini.png", definitions.get("Gini Coefficient (Inequality)", GINI_DEFINITION)),
        ("Sparseness", "Trend_Sparseness.png", definitions.get("Sparseness (System Activation)", SPARSENESS_DEFINITION)),
        ("Axial–Peripheral Ratio", "Trend_AxialPeripheral.png", definitions.get("Axial-Peripheral Ratio (Core vs. Limbs)", AXIAL_PERIPHERAL_DEFINITION)),
    ]

    chapter_html = []
    for title, img_name, definition in chapters:
        img_path = img_dir / img_name
        try:
            src = f"data:image/png;base64,{image_to_base64(img_path)}"
        except (FileNotFoundError, OSError):
            src = f"{prefix}{img_name}"
        chapter_html.append(f"""
    <section class="trend-chapter mb-5">
      <h2 class="chapter-title">{title}</h2>
      <img src="{src}" alt="{title} trend" class="trend-img img-fluid" />
      <div class="defn-box mt-2">
        <p class="small mb-0">{definition}</p>
      </div>
    </section>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subject {subject_id}: Index Trend Plots</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; padding: 2rem 0; }}
    .report-title {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 1.5rem; color: #1a1a1a; }}
    .chapter-title {{ font-size: 1.25rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.75rem; color: #333; }}
    .trend-img {{ max-width: 100%; height: auto; }}
    .defn-box {{ background: #f8f9fa; border-left: 4px solid #0d6efd; padding: 0.75rem 1rem; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="container" style="max-width: 900px;">
    <h1 class="report-title">Subject {subject_id}: Index Trend Plots</h1>
    <p class="text-muted">Longitudinal shifts in behavioral strategy ({" → ".join(available_timepoints or ["T1", "T2", "T3"])}). Dynamics (blue), Pose (orange), Reach (green).</p>
{"".join(chapter_html)}
  </div>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    out.write_text(html, encoding="utf-8")


def save_numerical_tables_html(
    tables: list[tuple[str, pd.DataFrame]],
    output_path: str | Path,
    subject_id: str = "671",
    available_timepoints: list[str] | None = None,
) -> tuple[int, int]:
    """
    Merge multiple (title, DataFrame) pairs into one Bootstrap-styled HTML report.
    Saves to output_path. Returns (number_of_tables, file_size_bytes).
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sections = []
    for title, df in tables:
        if df is None or not isinstance(df, pd.DataFrame):
            continue
        html_table = df.to_html(
            index=False,
            classes="table table-hover table-striped table-sm",
            border=0,
        )
        sections.append(
            f'<section class="mb-5">\n'
            f'  <h2 class="h5 text-primary border-bottom pb-2">{title}</h2>\n'
            f'  <div class="table-responsive">{html_table}</div>\n'
            f'</section>'
        )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subject {subject_id} — Numerical Results Archive</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; padding: 2rem 0; }}
    .report-title {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 1rem; color: #1a1a1a; }}
    .table {{ font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="container" style="max-width: 1200px;">
    <h1 class="report-title">Subject {subject_id} — Numerical Results Archive</h1>
    <p class="text-muted">Phase 0–5 statistical tables. Generated from 10_EDA_PCA.ipynb.</p>
    {"".join(sections)}
  </div>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    out.write_text(html, encoding="utf-8")
    n_tables = len(sections)
    size_bytes = out.stat().st_size
    return n_tables, size_bytes


def _tp_color_legend(available_timepoints: list[str] | None = None) -> str:
    """Return human-readable color legend string for available timepoints."""
    _colors = {"T1": "blue", "T2": "red", "T3": "green"}
    tps = available_timepoints or ["T1", "T2", "T3"]
    return ", ".join(f"{tp} ({_colors.get(tp, 'gray')})" for tp in tps)


def save_clean_dashboard_html(
    fig: Any,
    output_path: str | Path,
    subject_id: str = "671",
    available_timepoints: list[str] | None = None,
) -> None:
    """
    Wrap the dashboard figure in a Bootstrap HTML template with title, section headers,
    and integrated definitions. Saves to output_path (e.g. Subject_671_Clean_Analysis.html).
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subject {subject_id}: Behavioral Complexity &amp; Spatial Exploration Report</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; padding: 2rem 0; }}
    .report-title {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 1.5rem; color: #1a1a1a; }}
    .section-header {{ font-size: 1.1rem; font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem; color: #333; }}
    .defn-box {{ background: #f8f9fa; border-left: 4px solid #0d6efd; padding: 0.75rem 1rem; margin-top: 0.5rem; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="container-fluid">
    <h1 class="report-title">Subject {subject_id}: Behavioral Complexity &amp; Spatial Exploration Report</h1>

    <div class="row mb-3">
      <div class="col-md-4"><p class="section-header">Branch A: Dynamics (How)</p><p class="text-muted small">ω — rotational speed &amp; rhythmic complexity</p></div>
      <div class="col-md-4"><p class="section-header">Branch B: Pose (What)</p><p class="text-muted small">Quaternion pose space — body shapes &amp; postures</p></div>
      <div class="col-md-4"><p class="section-header">Branch C: Reach (Where)</p><p class="text-muted small">XYZ — volumetric reach (Hips at origin)</p></div>
    </div>

    <div class="mb-4">
      {fig_html}
    </div>

    <div class="row mt-4">
      <div class="col-md-3">
        <p class="section-header">Spatial (3D PCA)</p>
        <p class="defn-box small">PC1–PC3 cloud: {_tp_color_legend(available_timepoints)}. Expansion in later sessions suggests broader movement exploration.</p>
      </div>
      <div class="col-md-3">
        <p class="section-header">Complexity (N90 &amp; Volume)</p>
        <p class="defn-box small">{N90_DEFINITION} Volume: 3D convex hull of the PC cloud.</p>
      </div>
      <div class="col-md-3">
        <p class="section-header">Strategy (Gini &amp; Entropy)</p>
        <p class="defn-box small">{GINI_DEFINITION}</p>
        <p class="defn-box small">{ENTROPY_DEFINITION}</p>
      </div>
      <div class="col-md-3">
        <p class="section-header">Anatomy (Top 5 T2)</p>
        <p class="defn-box small">Joints contributing most to T2 variance — identifies which body parts &quot;woke up&quot; in the intervention window.</p>
      </div>
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    out.write_text(html, encoding="utf-8")


def save_interactive_deepdive_html(
    branch_figures: list[tuple[str, str, Any]],
    output_path: str | Path,
    subject_id: str = "671",
    available_timepoints: list[str] | None = None,
) -> None:
    """
    Phase 6: Museum-grade sectional HTML. Bootstrap container max-width 1200px,
    Key Findings / Systems Legend at top, then one full-viewport section per branch
    (h2 + 1-sentence explanation + embedded Plotly figure). Saves as Subject_671_Interactive_DeepDive.html.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    definitions = get_index_definitions()
    legend_html = "".join(
        f'<div class="mb-2"><strong>{k}</strong><br><span class="small text-muted">{v}</span></div>'
        for k, v in definitions.items()
    )
    # First figure includes Plotly.js; rest are div-only
    fig1_html = branch_figures[0][2].to_html(full_html=False, include_plotlyjs="cdn")
    fig2_html = branch_figures[1][2].to_html(full_html=False, include_plotlyjs=False) if len(branch_figures) > 1 else ""
    fig3_html = branch_figures[2][2].to_html(full_html=False, include_plotlyjs=False) if len(branch_figures) > 2 else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Subject {subject_id}: Interactive Deep Dive — Behavioral Complexity &amp; Spatial Exploration</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; padding: 1rem 0; }}
    .container-report {{ max-width: 1200px; margin: 0 auto; }}
    .report-title {{ font-size: 1.85rem; font-weight: 700; margin-bottom: 0.5rem; color: #1a1a1a; }}
    .key-findings {{ background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 8px; padding: 1.25rem; margin-bottom: 2rem; border-left: 4px solid #0d6efd; }}
    .key-findings h3 {{ font-size: 1.1rem; margin-bottom: 0.75rem; }}
    .branch-section {{ min-height: 85vh; }}
    .figure-wrapper {{ margin: 1rem 0; }}
  </style>
</head>
<body>
  <div class="container container-report">
    <h1 class="report-title">Subject {subject_id}: Behavioral Complexity &amp; Spatial Exploration Report</h1>
    <p class="text-muted mb-4">Interactive Deep Dive — 3 branches, vector-based plots (zoom for full resolution).</p>

    <div class="key-findings">
      <h3>Key Findings — Systems Metric Legend</h3>
      <div class="row">
        <div class="col-md-6">{legend_html}</div>
      </div>
    </div>

    <h2 class="h4 mt-4">Branch A: Dynamics (How)</h2>
    <p class="text-muted mb-2">Dynamics (ω): Rotational speed and rhythmic complexity across joints.</p>
    <div class="figure-wrapper mb-5">{fig1_html}</div>

    <h2 class="h4 mt-5 pt-4 border-top">Branch B: Pose (What)</h2>
    <p class="text-muted mb-2">Pose (q): Body shapes and postures in quaternion space.</p>
    <div class="figure-wrapper mb-5">{fig2_html}</div>

    <h2 class="h4 mt-5 pt-4 border-top">Branch C: Reach (Where)</h2>
    <p class="text-muted mb-2">Reach (XYZ): Where the body moves in space (Hips at origin).</p>
    <div class="figure-wrapper mb-5">{fig3_html}</div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    out.write_text(html, encoding="utf-8")

