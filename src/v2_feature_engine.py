"""
src/v2_feature_engine.py — v2 Methodology Feature Extraction Engine
====================================================================

Implements the four-feature pipeline specified in METHODOLOGY_SPEC_v2.md:
    F1  Active Time Fraction (ATF)
    F2  Total Movement (TM)
    F4  Effective Dimensionality (D_eff)
    F5  Joint Gini Coefficient

Architecture (§3.3):
    - Fresh code — no copy-paste from core_kinematics_engine.py or EDA_PCA.py.
    - The sole allowed legacy import is compute_noise_floor from src/pulsicity.py (F1).
    - No Plotly, ipywidgets, or HTML export logic in this module.
    - Longitudinal deltas and delta bootstrap live in v2_longitudinal.py (deferred).

Public API:
    apply_time_window        §3.2  session time windowing
    load_session             I/O   pure Parquet loader
    compute_quality_gates    §2    reliability gates → quality_df
    validate_reference       §3    reference-session hard gates
    compute_atf              §F1   Active Time Fraction (per-joint + groups)
    compute_total_movement   §F2   endpoint path length
    build_pca_engine         §F4   reference-anchored PCA engine
    compute_d_eff            §F4   participation ratio
    compute_joint_gini       §F5   Gini on PCA-attributed joint variance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from src.pulsicity import compute_noise_floor

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────────────────
# Constants (Appendix A.1 — normative)
# ───────────────────────────────────────────────────────────────────────────

ALL_19_JOINTS: List[str] = [
    "Hips", "Spine", "Spine1", "Neck", "Head",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot",
    "RightUpLeg", "RightLeg", "RightFoot",
]

JOINT_GROUPS: Dict[str, List[str]] = {
    "axial": ["Hips", "Spine", "Spine1", "Neck", "Head"],
    "peripheral": [
        "LeftForeArm", "LeftHand", "RightForeArm", "RightHand",
        "LeftFoot", "RightFoot",
    ],
    "transitional": [
        "LeftShoulder", "RightShoulder", "LeftArm", "RightArm",
        "LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg",
    ],
}

TM_ENDPOINTS: List[str] = ["LeftHand", "RightHand", "LeftFoot", "RightFoot"]


# ───────────────────────────────────────────────────────────────────────────
# Dataclasses
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class PCAEngine:
    """Frozen reference-anchored PCA basis (§F4 / §3 Key Pipeline Rules)."""
    scaler: StandardScaler
    pca: PCA
    feature_columns: List[str]
    reference_run_id: str
    scores_by_run: Dict[str, np.ndarray] = field(default_factory=dict)
    var_per_pc_by_run: Dict[str, np.ndarray] = field(default_factory=dict)
    clean_mask_by_run: Dict[str, np.ndarray] = field(default_factory=dict)
    n_clean_by_run: Dict[str, int] = field(default_factory=dict)


@dataclass
class ATFResult:
    atf_per_joint: Dict[str, float]
    atf_wb: float
    atf_axial: float
    atf_peripheral: float
    atf_transitional: float
    noise_floors: Dict[str, Dict[str, Any]]
    artifact_rates: Dict[str, float]
    n_clean_frames: Dict[str, int]


@dataclass
class TMResult:
    tm_total_mm: float
    tm_rate_mm_per_s: float
    tm_per_endpoint: Dict[str, float]
    clean_duration_tm_s: float
    step_counts: Dict[str, int]
    artifact_rates: Dict[str, float]


@dataclass
class DeffResult:
    d_eff: float
    d_eff_norm: float
    var_per_pc: np.ndarray
    proportions: np.ndarray
    n90: int
    session_native_d_eff: Optional[float] = None
    session_native_d_eff_norm: Optional[float] = None


@dataclass
class GiniResult:
    gini_anchored: float
    joint_proportions_anchored: Dict[str, float]
    gini_native: Optional[float] = None
    joint_proportions_native: Optional[Dict[str, float]] = None
    session_native_gini_skipped: bool = False


# ───────────────────────────────────────────────────────────────────────────
# §3.2 — Session time windowing
# ───────────────────────────────────────────────────────────────────────────

def apply_time_window(
    df: pd.DataFrame,
    time_col: str = "time_s",
    t_start_s: Optional[float] = None,
    t_end_s: Optional[float] = None,
) -> pd.DataFrame:
    """Crop DataFrame to [t_start_s, t_end_s] on *time_col*.

    Both bounds are inclusive.  If both are None, return the input unchanged.
    If only one is None, the interval is open-ended on that side.
    """
    if t_start_s is None and t_end_s is None:
        return df
    ts = df[time_col]
    mask = np.ones(len(df), dtype=bool)
    if t_start_s is not None:
        mask &= ts >= t_start_s
    if t_end_s is not None:
        mask &= ts <= t_end_s
    result = df.loc[mask].copy()
    if result.empty:
        logger.warning(
            f"apply_time_window: empty result for [{t_start_s}, {t_end_s}]; "
            f"time_s range was [{ts.min():.2f}, {ts.max():.2f}]"
        )
    return result


# ───────────────────────────────────────────────────────────────────────────
# I/O — Pure Parquet loader
# ───────────────────────────────────────────────────────────────────────────

def load_session(path: str | Path) -> pd.DataFrame:
    """Load a kinematics_master Parquet, returning the full DataFrame."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"load_session: {path} does not exist")
    df = pd.read_parquet(path)
    logger.info(f"load_session: {path.name} — {len(df)} rows, {len(df.columns)} cols")
    return df


# ───────────────────────────────────────────────────────────────────────────
# Reliability gates (§2 + Block 0)
# ───────────────────────────────────────────────────────────────────────────

def compute_quality_gates(
    sessions: Dict[str, pd.DataFrame],
    config: Dict[str, Any],
) -> pd.DataFrame:
    """Compute per-session reliability gates → quality_df (one row per run_id).

    Gate thresholds from config:
        artifact_critical_threshold  0.30  hard exclude
        artifact_warning_threshold   0.20  soft flag
        per_joint_artifact_exclude   0.30  joint exclusion
        per_endpoint_artifact_flag   0.20  TM endpoint flag
        min_clean_fraction_pca       0.70  PCA low-confidence
        min_session_duration_s       60.0  short-session flag
    """
    fs = float(config.get("fs", 120.0))
    art_crit = float(config.get("artifact_critical_threshold", 0.30))
    art_warn = float(config.get("artifact_warning_threshold", 0.20))
    pj_art = float(config.get("per_joint_artifact_exclude", 0.30))
    pe_art = float(config.get("per_endpoint_artifact_flag", 0.20))
    min_clean_pca = float(config.get("min_clean_fraction_pca", 0.70))
    min_dur = float(config.get("min_session_duration_s", 60.0))

    rows = []
    for run_id, df in sessions.items():
        n_frames = len(df)
        duration_s = n_frames / fs

        # Per-joint artifact rates
        joint_art_rates: Dict[str, float] = {}
        for j in ALL_19_JOINTS:
            art_col = f"{j}__is_artifact"
            if art_col in df.columns:
                rate = float(df[art_col].sum()) / n_frames if n_frames > 0 else 0.0
            else:
                rate = 0.0
            joint_art_rates[j] = rate

        # Global artifact fraction = max over joints
        global_artifact_frac = max(joint_art_rates.values()) if joint_art_rates else 0.0

        # All-joint clean mask (PCA requirement)
        all_clean_mask = np.ones(n_frames, dtype=bool)
        for j in ALL_19_JOINTS:
            art_col = f"{j}__is_artifact"
            if art_col in df.columns:
                all_clean_mask &= ~df[art_col].values.astype(bool)
        clean_fraction_pca = float(all_clean_mask.sum()) / n_frames if n_frames > 0 else 0.0
        clean_duration_s = float(all_clean_mask.sum()) / fs

        # Flags
        hard_exclude = global_artifact_frac > art_crit
        soft_warning = (not hard_exclude) and global_artifact_frac > art_warn
        pca_low_confidence = clean_fraction_pca < min_clean_pca
        short_session = duration_s < min_dur

        joints_excluded = [j for j, r in joint_art_rates.items() if r > pj_art]
        endpoints_flagged = [
            e for e in TM_ENDPOINTS
            if joint_art_rates.get(e, 0.0) > pe_art
        ]

        rows.append({
            "run_id": run_id,
            "n_frames": n_frames,
            "duration_s": duration_s,
            "global_artifact_frac": global_artifact_frac,
            "clean_fraction_pca": clean_fraction_pca,
            "clean_duration_s": clean_duration_s,
            "hard_exclude": hard_exclude,
            "soft_warning": soft_warning,
            "pca_low_confidence": pca_low_confidence,
            "short_session": short_session,
            "joints_excluded": joints_excluded,
            "endpoints_flagged": endpoints_flagged,
            "joint_artifact_rates": joint_art_rates,
        })

    return pd.DataFrame(rows)


def validate_reference(
    quality_df: pd.DataFrame,
    reference_run_id: str,
) -> Tuple[bool, str]:
    """Validate reference session meets hard gates (§3 Rule 4).

    Returns (is_valid, message).
    """
    ref_row = quality_df[quality_df["run_id"] == reference_run_id]
    if ref_row.empty:
        return False, f"Reference run_id '{reference_run_id}' not found in quality_df"

    ref = ref_row.iloc[0]
    issues = []

    if ref["hard_exclude"]:
        issues.append(
            f"artifact_frac={ref['global_artifact_frac']:.3f} > critical threshold"
        )
    if ref["pca_low_confidence"]:
        issues.append(
            f"clean_fraction_pca={ref['clean_fraction_pca']:.3f} < 0.70"
        )
    if ref["clean_duration_s"] < 60.0:
        issues.append(f"clean_duration={ref['clean_duration_s']:.1f}s < 60s")

    if issues:
        return False, "Reference session FAILED: " + "; ".join(issues)
    return True, "Reference session passed all validation gates."


# ───────────────────────────────────────────────────────────────────────────
# F1 — Active Time Fraction (ATF)
# ───────────────────────────────────────────────────────────────────────────

def compute_atf(
    df: pd.DataFrame,
    run_id: str,
    params_f1: Dict[str, Any],
    config: Dict[str, Any],
) -> ATFResult:
    """Compute F1 ATF for a single session per §F1.

    params_f1 keys used:
        noise_floor_guard_mms             1.0
        static_baseline_guard_mms        50.0
        static_window_sec                 2.0
        noise_floor_override_mms_by_joint {}
        artifact_warning_threshold        0.20
        artifact_critical_threshold       0.30
    """
    fs = float(config.get("fs", 120.0))
    overrides = params_f1.get("noise_floor_override_mms_by_joint", {})

    cfg_nf = {
        "fs_target": fs,
        "ref_search_sec": float(config.get("ref_search_sec", 8.0)),
        "ref_window_sec": float(params_f1.get("static_window_sec", 2.0)),
        "static_search_step_sec": float(config.get("static_search_step_sec", 0.1)),
        "reference_variance_threshold": float(
            config.get("reference_variance_threshold", 100.0)
        ),
    }

    atf_per_joint: Dict[str, float] = {}
    noise_floors: Dict[str, Dict[str, Any]] = {}
    artifact_rates: Dict[str, float] = {}
    n_clean_frames: Dict[str, int] = {}

    for joint in ALL_19_JOINTS:
        vel_col = f"{joint}__lin_vel_rel_mag"
        art_col = f"{joint}__is_artifact"

        if vel_col not in df.columns:
            logger.warning(f"compute_atf: {vel_col} missing — setting ATF=NaN for {joint}")
            atf_per_joint[joint] = np.nan
            continue

        vel = df[vel_col].values.astype(float)
        artifact = (
            df[art_col].values.astype(bool)
            if art_col in df.columns
            else np.zeros(len(vel), dtype=bool)
        )

        n_total = len(vel)
        n_art = int(artifact.sum())
        n_clean = n_total - n_art
        artifact_rates[joint] = n_art / n_total if n_total > 0 else 0.0
        n_clean_frames[joint] = n_clean

        # Noise floor — import from pulsicity.py or use override
        if joint in overrides and overrides[joint] is not None:
            V = float(overrides[joint])
            nf_info = {
                "V": V,
                "noise_floor_source": "override",
                "noise_floor_low_confidence": False,
            }
        else:
            nf_info = compute_noise_floor(
                df, joint, cfg_nf,
                static_baseline_guard_mms=float(
                    params_f1.get("static_baseline_guard_mms", 50.0)
                ),
                noise_floor_guard_mms=float(
                    params_f1.get("noise_floor_guard_mms", 1.0)
                ),
            )
            V = float(nf_info["V"])

        noise_floors[joint] = nf_info

        # ATF = proportion of clean frames where vel > V
        clean_mask = ~artifact
        if n_clean == 0:
            atf_per_joint[joint] = np.nan
        else:
            active = np.sum((vel > V) & clean_mask)
            atf_per_joint[joint] = float(active) / float(n_clean)

    # Whole-body = median over joints with valid ATF
    valid_atfs = [v for v in atf_per_joint.values() if not np.isnan(v)]
    atf_wb = float(np.median(valid_atfs)) if valid_atfs else np.nan

    # Group summaries
    def _group_median(group_joints: List[str]) -> float:
        vals = [atf_per_joint[j] for j in group_joints
                if j in atf_per_joint and not np.isnan(atf_per_joint[j])]
        return float(np.median(vals)) if vals else np.nan

    return ATFResult(
        atf_per_joint=atf_per_joint,
        atf_wb=atf_wb,
        atf_axial=_group_median(JOINT_GROUPS["axial"]),
        atf_peripheral=_group_median(JOINT_GROUPS["peripheral"]),
        atf_transitional=_group_median(JOINT_GROUPS["transitional"]),
        noise_floors=noise_floors,
        artifact_rates=artifact_rates,
        n_clean_frames=n_clean_frames,
    )


# ───────────────────────────────────────────────────────────────────────────
# F2 — Total Movement (TM)
# ───────────────────────────────────────────────────────────────────────────

def compute_total_movement(
    df: pd.DataFrame,
    run_id: str,
    params_f2: Dict[str, Any],
    config: Dict[str, Any],
) -> TMResult:
    """Compute F2 TM for a single session per §F2.

    Normative contiguous-run logic: never mask-then-diff.

    params_f2 keys:
        min_segment_frames   3
        normalize_by_duration True
    """
    fs = float(config.get("fs", 120.0))
    min_seg = int(params_f2.get("min_segment_frames", 3))

    tm_per_endpoint: Dict[str, float] = {}
    step_counts: Dict[str, int] = {}
    art_rates: Dict[str, float] = {}

    for ep in TM_ENDPOINTS:
        px_col = f"{ep}__lin_rel_px"
        py_col = f"{ep}__lin_rel_py"
        pz_col = f"{ep}__lin_rel_pz"
        art_col = f"{ep}__is_artifact"

        for col in (px_col, py_col, pz_col):
            if col not in df.columns:
                raise KeyError(f"compute_total_movement: column '{col}' missing")

        pos = df[[px_col, py_col, pz_col]].values.astype(float)
        artifact = (
            df[art_col].values.astype(bool)
            if art_col in df.columns
            else np.zeros(len(df), dtype=bool)
        )
        n_total = len(df)
        art_rates[ep] = float(artifact.sum()) / n_total if n_total > 0 else 0.0

        clean = ~artifact
        tm_e = 0.0
        n_steps = 0

        # Build contiguous clean runs
        run_labels = np.zeros(n_total, dtype=int)
        run_id_counter = 0
        in_run = False
        for i in range(n_total):
            if clean[i]:
                if not in_run:
                    run_id_counter += 1
                    in_run = True
                run_labels[i] = run_id_counter
            else:
                in_run = False

        for rid in range(1, run_id_counter + 1):
            run_indices = np.where(run_labels == rid)[0]
            if len(run_indices) < min_seg:
                continue
            run_pos = pos[run_indices]
            diffs = np.diff(run_pos, axis=0)
            steps = np.sqrt(np.sum(diffs ** 2, axis=1))
            tm_e += float(steps.sum())
            n_steps += len(steps)

        tm_per_endpoint[ep] = tm_e
        step_counts[ep] = n_steps

    tm_total = sum(tm_per_endpoint.values())
    total_steps = sum(step_counts.values())
    clean_duration_tm_s = total_steps / (4.0 * fs) if fs > 0 else 0.0
    tm_rate = tm_total / clean_duration_tm_s if clean_duration_tm_s > 0 else np.nan

    return TMResult(
        tm_total_mm=tm_total,
        tm_rate_mm_per_s=tm_rate,
        tm_per_endpoint=tm_per_endpoint,
        clean_duration_tm_s=clean_duration_tm_s,
        step_counts=step_counts,
        artifact_rates=art_rates,
    )


# ───────────────────────────────────────────────────────────────────────────
# Shared PCA Engine (§F4 — reference-anchored)
# ───────────────────────────────────────────────────────────────────────────

def _build_all_joint_clean_mask(df: pd.DataFrame) -> np.ndarray:
    """All-joint AND artifact mask: True where ALL 19 joints are clean."""
    mask = np.ones(len(df), dtype=bool)
    for j in ALL_19_JOINTS:
        art_col = f"{j}__is_artifact"
        if art_col in df.columns:
            mask &= ~df[art_col].values.astype(bool)
    return mask


def _get_dynamics_columns(branch: str = "dynamics") -> List[str]:
    """Return feature column names for the requested kinematic branch."""
    if branch == "dynamics":
        return [f"{j}__zeroed_rel_omega_mag" for j in ALL_19_JOINTS]
    raise ValueError(f"Unsupported kinematic branch: '{branch}'. MVP supports 'dynamics' only.")


def build_pca_engine(
    sessions: Dict[str, pd.DataFrame],
    reference_run_id: str,
    params_pca: Dict[str, Any],
) -> PCAEngine:
    """Build reference-anchored PCA engine per §F4.

    Steps:
        1. Select feature columns per kinematic_branch (default: dynamics → 19 omega_mag).
        2. Build all-joint-clean mask per session.
        3. Fit StandardScaler on reference clean frames.
        4. Scale all sessions with frozen scaler.
        5. Fit PCA(n_components=19) on reference scaled data.
        6. Transform all sessions; compute per-session var_per_pc.
    """
    branch = params_pca.get("kinematic_branch", "dynamics")
    feat_cols = _get_dynamics_columns(branch)
    n_components = len(feat_cols)
    epsilon = float(params_pca.get("epsilon_deff", 1e-12))

    if reference_run_id not in sessions:
        raise KeyError(f"build_pca_engine: reference '{reference_run_id}' not in sessions")

    # Reference session
    ref_df = sessions[reference_run_id]
    ref_clean = _build_all_joint_clean_mask(ref_df)
    for col in feat_cols:
        if col not in ref_df.columns:
            raise KeyError(f"build_pca_engine: column '{col}' missing from reference session")

    X_ref = ref_df.loc[ref_clean, feat_cols].values.astype(float)
    if X_ref.shape[0] < n_components:
        raise ValueError(
            f"build_pca_engine: reference has only {X_ref.shape[0]} clean frames "
            f"(need >= {n_components})"
        )

    # Step 1–2: Fit scaler on reference
    scaler = StandardScaler()
    scaler.fit(X_ref)

    # Step 3: Fit PCA on scaled reference
    X_ref_scaled = scaler.transform(X_ref)
    pca = PCA(n_components=n_components)
    pca.fit(X_ref_scaled)

    logger.info(
        f"build_pca_engine: reference='{reference_run_id}', "
        f"n_clean_ref={X_ref.shape[0]}, K={n_components}, "
        f"explained_variance_ratio[:3]={pca.explained_variance_ratio_[:3].round(4)}"
    )

    engine = PCAEngine(
        scaler=scaler,
        pca=pca,
        feature_columns=feat_cols,
        reference_run_id=reference_run_id,
    )

    # Step 4–5: Transform all sessions
    for run_id, df in sessions.items():
        clean_mask = _build_all_joint_clean_mask(df)
        for col in feat_cols:
            if col not in df.columns:
                logger.warning(
                    f"build_pca_engine: column '{col}' missing in session '{run_id}'"
                )
                break
        else:
            X_s = df.loc[clean_mask, feat_cols].values.astype(float)
            X_s_scaled = scaler.transform(X_s)
            Y_s = pca.transform(X_s_scaled)
            var_per_pc = np.var(Y_s, axis=0)

            engine.scores_by_run[run_id] = Y_s
            engine.var_per_pc_by_run[run_id] = var_per_pc
            engine.clean_mask_by_run[run_id] = clean_mask
            engine.n_clean_by_run[run_id] = int(clean_mask.sum())

    return engine


# ───────────────────────────────────────────────────────────────────────────
# F4 — Effective Dimensionality (Participation Ratio)
# ───────────────────────────────────────────────────────────────────────────

def compute_d_eff(
    pca_engine: PCAEngine,
    run_id: str,
    params_pca: Dict[str, Any],
    session_df: Optional[pd.DataFrame] = None,
) -> DeffResult:
    """Compute D_eff (participation ratio) from the shared PCAEngine per §F4.

    session_df is needed only if run_session_native_deff is True.
    """
    epsilon = float(params_pca.get("epsilon_deff", 1e-12))
    run_native = bool(params_pca.get("run_session_native_deff", True))

    if run_id not in pca_engine.var_per_pc_by_run:
        raise KeyError(f"compute_d_eff: run_id '{run_id}' not in PCA engine")

    var_per_pc = pca_engine.var_per_pc_by_run[run_id]
    K = len(var_per_pc)

    total_var = np.sum(var_per_pc) + epsilon
    p = var_per_pc / total_var
    d_eff = 1.0 / (np.sum(p ** 2) + epsilon)
    d_eff_norm = d_eff / K

    # n90: number of PCs needed to explain 90% of variance
    cum_var = np.cumsum(np.sort(var_per_pc)[::-1]) / (np.sum(var_per_pc) + epsilon)
    n90 = int(np.searchsorted(cum_var, 0.90) + 1)
    n90 = min(n90, K)

    # Session-native D_eff (sensitivity) — fresh PCA on this session alone.
    # Uses StandardScaler for D_eff (eigenvalue concentration is scale-invariant
    # for the participation ratio; scaling ensures numeric stability).
    session_native_d_eff = None
    session_native_d_eff_norm = None
    if run_native and session_df is not None:
        feat_cols = pca_engine.feature_columns
        clean_mask = _build_all_joint_clean_mask(session_df)
        X_s = session_df.loc[clean_mask, feat_cols].values.astype(float)
        if X_s.shape[0] >= len(feat_cols):
            ss = StandardScaler()
            X_ss = ss.fit_transform(X_s)
            pca_native = PCA(n_components=len(feat_cols))
            pca_native.fit(X_ss)
            ev_native = pca_native.explained_variance_
            total_native = np.sum(ev_native) + epsilon
            p_native = ev_native / total_native
            session_native_d_eff = 1.0 / (np.sum(p_native ** 2) + epsilon)
            session_native_d_eff_norm = session_native_d_eff / K

    return DeffResult(
        d_eff=float(d_eff),
        d_eff_norm=float(d_eff_norm),
        var_per_pc=var_per_pc,
        proportions=p,
        n90=n90,
        session_native_d_eff=(
            float(session_native_d_eff) if session_native_d_eff is not None else None
        ),
        session_native_d_eff_norm=(
            float(session_native_d_eff_norm) if session_native_d_eff_norm is not None else None
        ),
    )


# ───────────────────────────────────────────────────────────────────────────
# F5 — Joint Gini Coefficient
# ───────────────────────────────────────────────────────────────────────────

def _gini_coefficient(values: np.ndarray) -> float:
    """Standard sorted-form Gini on nonneg values: G = (2 Σ i·x_(i))/(n Σ x) - (n+1)/n."""
    x = np.sort(values)
    n = len(x)
    total = np.sum(x)
    if total <= 0 or n == 0:
        return 0.0
    indices = np.arange(1, n + 1)
    return float((2.0 * np.sum(indices * x)) / (n * total) - (n + 1.0) / n)


def compute_joint_gini(
    pca_engine: PCAEngine,
    run_id: str,
    params_pca: Dict[str, Any],
    session_df: Optional[pd.DataFrame] = None,
) -> GiniResult:
    """Compute Joint Gini coefficient per §F5.

    T1-anchored mode: uses PCAEngine loadings + per-session var_per_pc.
    Session-native mode: fresh PCA per session (sensitivity).
    """
    run_native = bool(params_pca.get("run_session_native_gini", True))

    if run_id not in pca_engine.var_per_pc_by_run:
        raise KeyError(f"compute_joint_gini: run_id '{run_id}' not in PCA engine")

    var_per_pc = pca_engine.var_per_pc_by_run[run_id]
    loadings = pca_engine.pca.components_  # shape (K, F)
    K = loadings.shape[0]

    # α_f = Σ_k λ_k · w_{k,f}² — variance attribution per feature
    alpha = np.zeros(K)
    for f_idx in range(K):
        alpha[f_idx] = np.sum(var_per_pc * loadings[:, f_idx] ** 2)

    # For dynamics branch (1 feature per joint), alpha maps 1-to-1 to joints
    joint_names = [
        col.replace("__zeroed_rel_omega_mag", "")
        for col in pca_engine.feature_columns
    ]

    total_alpha = np.sum(alpha)
    if total_alpha > 0:
        pi = alpha / total_alpha
    else:
        pi = np.ones(K) / K

    gini_anchored = _gini_coefficient(pi)
    joint_proportions_anchored = dict(zip(joint_names, pi.tolist()))

    # Session-native Gini (sensitivity)
    gini_native = None
    joint_proportions_native = None
    native_skipped = True

    if run_native and session_df is not None:
        feat_cols = pca_engine.feature_columns
        clean_mask = _build_all_joint_clean_mask(session_df)
        X_s = session_df.loc[clean_mask, feat_cols].values.astype(float)
        if X_s.shape[0] >= len(feat_cols):
            # Session-native Gini: do NOT standardize — use mean-centered
            # raw data so per-feature variance reflects genuine joint-level
            # differences. (StandardScaler forces all variances to 1, making
            # the attribution formula recover the identity and Gini = 0.)
            X_centered = X_s - X_s.mean(axis=0)
            pca_nat = PCA(n_components=len(feat_cols))
            pca_nat.fit(X_centered)
            ev_nat = pca_nat.explained_variance_
            load_nat = pca_nat.components_
            alpha_nat = np.zeros(len(feat_cols))
            for f_idx in range(len(feat_cols)):
                alpha_nat[f_idx] = np.sum(ev_nat * load_nat[:, f_idx] ** 2)
            total_nat = np.sum(alpha_nat)
            pi_nat = alpha_nat / total_nat if total_nat > 0 else np.ones(len(feat_cols)) / len(feat_cols)
            gini_native = _gini_coefficient(pi_nat)
            joint_proportions_native = dict(zip(joint_names, pi_nat.tolist()))
            native_skipped = False

    return GiniResult(
        gini_anchored=float(gini_anchored),
        joint_proportions_anchored=joint_proportions_anchored,
        gini_native=float(gini_native) if gini_native is not None else None,
        joint_proportions_native=joint_proportions_native,
        session_native_gini_skipped=native_skipped,
    )


# ───────────────────────────────────────────────────────────────────────────
# F5.1 — A/P Ratio (supplementary, from T1-anchored joint proportions)
# ───────────────────────────────────────────────────────────────────────────

def compute_ap_ratio(
    joint_proportions: Dict[str, float],
    epsilon: float = 1e-12,
) -> Dict[str, float]:
    """Compute Axial / Peripheral variance-share ratio per §F5.1."""
    pi_axial = sum(joint_proportions.get(j, 0.0) for j in JOINT_GROUPS["axial"])
    pi_periph = sum(joint_proportions.get(j, 0.0) for j in JOINT_GROUPS["peripheral"])
    return {
        "pi_axial": pi_axial,
        "pi_peripheral": pi_periph,
        "ap_ratio": pi_axial / (pi_periph + epsilon),
    }


# ───────────────────────────────────────────────────────────────────────────
# Export helpers
# ───────────────────────────────────────────────────────────────────────────

def assemble_feature_row(
    run_id: str,
    atf_result: ATFResult,
    tm_result: TMResult,
    deff_result: Optional[DeffResult],
    gini_result: Optional[GiniResult],
    ap_result: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Assemble one tidy row of feature_scalars for a session."""
    row: Dict[str, Any] = {"run_id": run_id}

    # F1
    row["atf_wb"] = atf_result.atf_wb
    row["atf_axial"] = atf_result.atf_axial
    row["atf_peripheral"] = atf_result.atf_peripheral
    row["atf_transitional"] = atf_result.atf_transitional
    for j in ALL_19_JOINTS:
        row[f"atf_{j}"] = atf_result.atf_per_joint.get(j, np.nan)

    # F2
    row["tm_total_mm"] = tm_result.tm_total_mm
    row["tm_rate_mm_per_s"] = tm_result.tm_rate_mm_per_s
    row["clean_duration_tm_s"] = tm_result.clean_duration_tm_s
    for ep in TM_ENDPOINTS:
        row[f"tm_{ep}_mm"] = tm_result.tm_per_endpoint.get(ep, np.nan)

    # F4
    if deff_result is not None:
        row["d_eff"] = deff_result.d_eff
        row["d_eff_norm"] = deff_result.d_eff_norm
        row["n90"] = deff_result.n90
        row["session_native_d_eff"] = deff_result.session_native_d_eff
        row["session_native_d_eff_norm"] = deff_result.session_native_d_eff_norm
    else:
        row["d_eff"] = np.nan
        row["d_eff_norm"] = np.nan
        row["n90"] = np.nan
        row["session_native_d_eff"] = np.nan
        row["session_native_d_eff_norm"] = np.nan

    # F5
    if gini_result is not None:
        row["gini_anchored"] = gini_result.gini_anchored
        row["gini_native"] = gini_result.gini_native
        row["session_native_gini_skipped"] = gini_result.session_native_gini_skipped
    else:
        row["gini_anchored"] = np.nan
        row["gini_native"] = np.nan
        row["session_native_gini_skipped"] = True

    # F5.1 A/P
    if ap_result is not None:
        row["ap_ratio"] = ap_result["ap_ratio"]
        row["pi_axial"] = ap_result["pi_axial"]
        row["pi_peripheral"] = ap_result["pi_peripheral"]

    return row
