"""
Load pipeline config from config/config_v1.yaml (single source of truth).
Exposes CONFIG with uppercase aliases for backward compatibility (FS_TARGET, SG_WINDOW_SEC, THRESH, etc.).

Subject anthropometrics (height, weight) are loaded from data/subjects_registry.json
and injected into CONFIG as subject_height_cm / subject_mass_kg.  The registry is keyed
by subject ID and is the primary source of truth for researcher-provided measurements.
Fallback chain: Registry (measured) > Step 05 mocap estimate > None.
"""
import json
import os
import re
import yaml

# --- Paths ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
CONFIG_YAML_PATH = os.path.join(PROJECT_ROOT, "config", "config_v1.yaml")
SUBJECTS_REGISTRY_PATH = os.path.join(PROJECT_ROOT, "data", "subjects_registry.json")

# Defaults used only when YAML is missing or key absent (minimal fallback)
_DEFAULT_PATHS = {
    "project_root": ".",
    "derivatives_dir": "derivatives",
    "qc_dir": "qc",
    "data_dir": "data",
}

# Uppercase alias mapping: YAML key (lowercase) -> CONFIG key (uppercase) for notebook/code compatibility
_UPPERCASE_ALIASES = {
    "fs_target": "FS_TARGET",
    "sg_window_sec": "SG_WINDOW_SEC",
    "sg_polyorder": "SG_POLYORDER",
    "ref_window_sec": "REF_WINDOW_SEC",
    "ref_search_sec": "REF_SEARCH_SEC",
    "ref_anchor": "REF_ANCHOR",
    "static_search_step_sec": "STATIC_SEARCH_STEP_SEC",
    "motion_thr_low": "MOTION_THR_LOW",
    "motion_thr_std": "MOTION_THR_STD",
    "time_reg_policy": "TIME_REG_POLICY",
    "pos_resample_method": "POS_RESAMPLE_METHOD",
    "quat_resample_method": "QUAT_RESAMPLE_METHOD",
    "joints_viz": "JOINTS_VIZ",
    "exclude_groups": "EXCLUDE_GROUPS",
    "required_joints": "REQUIRED_JOINTS",
    "crop_sec": "CROP_SEC",
    "write_full_csv": "WRITE_FULL_CSV",
    "write_full_parquet": "WRITE_FULL_PARQUET",
    "write_viz_csv": "WRITE_VIZ_CSV",
    "write_run_log_jsonl": "WRITE_RUN_LOG_JSONL",
    "write_global_events_jsonl": "WRITE_GLOBAL_EVENTS_JSONL",
    "registry_commit_mode": "REGISTRY_COMMIT_MODE",
    "deriv_method": "DERIV_METHOD",
    "sg_targets": "SG_TARGETS",
    "shortest_rotation": "SHORTEST_ROTATION",
    "rotation_rep": "ROTATION_REP",
    "omega_method": "OMEGA_METHOD",
    "omega_frame": "OMEGA_FRAME",
    "missing_policy_pos": "MISSING_POLICY_POS",
    "missing_policy_quat": "MISSING_POLICY_QUAT",
    "max_gap_pos_sec": "MAX_GAP_POS_SEC",
    "max_gap_quat_sec": "MAX_GAP_QUAT_SEC",
    "health_fallback_cap": "HEALTH_FALLBACK_CAP",
    "health_weights": "HEALTH_WEIGHTS",
    "subject_height_cm": "SUBJECT_HEIGHT_CM",
    "subject_mass_kg": "SUBJECT_MASS_KG",
    "subject_id": "SUBJECT_ID",
    "subject_height_source": "SUBJECT_HEIGHT_SOURCE",
    "subject_weight_source": "SUBJECT_WEIGHT_SOURCE",
}

# Defaults for uppercase aliases when YAML key is missing (so pipeline.py, reference.py, qc.py keep working)
_ALIAS_DEFAULTS = {
    "FS_TARGET": 120.0,
    "SG_WINDOW_SEC": 0.175,
    "SG_POLYORDER": 3,
    "REF_WINDOW_SEC": 1.0,
    "REF_SEARCH_SEC": 8.0,
    "REF_ANCHOR": "static_detection_pre_crop",
    "STATIC_SEARCH_STEP_SEC": 0.1,
    "MOTION_THR_LOW": 0.30,
    "MOTION_THR_STD": 0.15,
    "TIME_REG_POLICY": "resample_to_fs_target",
    "POS_RESAMPLE_METHOD": "cubic_spline",
    "QUAT_RESAMPLE_METHOD": "slerp",
    "JOINTS_VIZ": ["Hips", "Spine", "Spine1", "Neck", "Head", "LeftArm", "RightArm", "LeftUpLeg", "RightUpLeg"],
    "EXCLUDE_GROUPS": ["Fingers", "Toes"],
    "REQUIRED_JOINTS": ["Hips", "Spine", "Head"],
    "CROP_SEC": [10.0, 110.0],
    "WRITE_FULL_CSV": True,
    "WRITE_FULL_PARQUET": True,
    "WRITE_VIZ_CSV": True,
    "WRITE_RUN_LOG_JSONL": False,
    "WRITE_GLOBAL_EVENTS_JSONL": False,
    "REGISTRY_COMMIT_MODE": "batch_commit_only",
    "DERIV_METHOD": "savgol",
    "SG_TARGETS": "derivatives_only",
    "SHORTEST_ROTATION": True,
    "ROTATION_REP": "rotvec_relative_reference",
    "OMEGA_METHOD": "quat_log",
    "OMEGA_FRAME": "child_body",
    "MISSING_POLICY_POS": "interp_linear_or_spline",
    "MISSING_POLICY_QUAT": "interp_slerp",
    "MAX_GAP_POS_SEC": 1.0,
    "MAX_GAP_QUAT_SEC": 0.25,
    "HEALTH_FALLBACK_CAP": 59,
    "HEALTH_WEIGHTS": {"missing": 25.0, "ref": 25.0, "omega": 25.0, "bone": 25.0},
    "SUBJECT_HEIGHT_CM": None,
    "SUBJECT_MASS_KG": None,
    "SUBJECT_ID": None,
    "SUBJECT_HEIGHT_SOURCE": None,
    "SUBJECT_WEIGHT_SOURCE": None,
}

# THRESH: YAML uses lowercase keys; code (e.g. qc.py) expects CONFIG["THRESH"]["BONE_CV_ALERT"] etc.
_THRESH_KEY_MAP = {
    "fs_tol_frac": "FS_TOL_FRAC",
    "missing_warn_frac": "MISSING_WARN_FRAC",
    "missing_alert_frac": "MISSING_ALERT_FRAC",
    "eps_ref_rv_rad": "EPS_REF_RV_RAD",
    "ref_quality_std_rad_warn": "REF_QUALITY_STD_RAD_WARN",
    "ref_quality_std_rad_alert": "REF_QUALITY_STD_RAD_ALERT",
    "omega_p99_warn": "OMEGA_P99_WARN",
    "omega_p99_alert": "OMEGA_P99_ALERT",
    "bone_cv_warn": "BONE_CV_WARN",
    "bone_cv_alert": "BONE_CV_ALERT",
    "bone_p95_abs_dev_warn_m": "BONE_P95_ABS_DEV_WARN_M",
    "bone_max_jump_alert_m": "BONE_MAX_JUMP_ALERT_M",
}


def load_yaml_config():
    """Load config from config_v1.yaml. Returns dict (lowercase keys from YAML)."""
    if not os.path.exists(CONFIG_YAML_PATH):
        print(f"WARNING: Config file not found at {CONFIG_YAML_PATH}. Using default paths.")
        return _DEFAULT_PATHS.copy()

    with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            print(f"Error parsing YAML: {e}")
            return _DEFAULT_PATHS.copy()


def _apply_defaults(raw: dict) -> dict:
    """Apply in-code defaults for missing keys so short/legacy YAML still works."""
    defaults = {
        "fs_target": 120.0,
        "sg_window_sec": 0.175,
        "sg_polyorder": 3,
        "ref_window_sec": 1.0,
        "ref_search_sec": 8.0,
        "ref_anchor": "static_detection_pre_crop",
        "exclude_fingers": False,
        "min_run_seconds": 5.0,
    }
    for k, v in defaults.items():
        if k not in raw or raw[k] is None:
            raw[k] = v
    if "thresh" not in raw or not isinstance(raw["thresh"], dict):
        raw["thresh"] = {}
    return raw


def _build_thresh(raw_thresh: dict) -> dict:
    """Build CONFIG['THRESH'] with uppercase keys from YAML thresh (lowercase)."""
    default_thresh = {
        "FS_TOL_FRAC": 0.01,
        "MISSING_WARN_FRAC": 0.05,
        "MISSING_ALERT_FRAC": 0.10,
        "EPS_REF_RV_RAD": 0.02,
        "REF_QUALITY_STD_RAD_WARN": 0.03,
        "REF_QUALITY_STD_RAD_ALERT": 0.05,
        "OMEGA_P99_WARN": 30.0,
        "OMEGA_P99_ALERT": 60.0,
        "BONE_CV_WARN": 0.02,
        "BONE_CV_ALERT": 0.05,
        "BONE_P95_ABS_DEV_WARN_M": 0.01,
        "BONE_MAX_JUMP_ALERT_M": 0.03,
    }
    out = default_thresh.copy()
    if raw_thresh:
        for yaml_k, cfg_k in _THRESH_KEY_MAP.items():
            if yaml_k in raw_thresh and raw_thresh[yaml_k] is not None:
                out[cfg_k] = raw_thresh[yaml_k]
    return out


# --- Subjects Registry ---

def load_subjects_registry(path=None):
    """
    Load per-subject anthropometric registry from data/subjects_registry.json.

    Returns:
        dict keyed by subject ID (str), e.g. {"671": {"height_cm": 154.0, ...}}.
        Returns empty dict if file missing or unparseable.
    """
    path = path or SUBJECTS_REGISTRY_PATH
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Strip internal metadata key
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except (json.JSONDecodeError, OSError) as e:
        print(f"WARNING: Could not load subjects registry at {path}: {e}")
        return {}


def extract_subject_id(csv_path):
    """
    Extract subject ID from a CSV path like '671/T1/671_T1_P2_R1_...csv'.

    Tries two strategies:
      1. First path component (directory name) if it looks numeric.
      2. Leading digits in the filename (e.g. '671_T1_...' -> '671').

    Returns:
        Subject ID as str, or None if extraction fails.
    """
    if not csv_path:
        return None
    parts = csv_path.replace("\\", "/").split("/")
    # Strategy 1: first directory component
    if len(parts) >= 2 and parts[0].isdigit():
        return parts[0]
    # Strategy 2: leading digits in filename
    basename = parts[-1]
    m = re.match(r"^(\d+)", basename)
    if m:
        return m.group(1)
    return None


def get_subject_anthropometrics(csv_path, registry=None):
    """
    Look up anthropometric data for the subject associated with *csv_path*.

    Args:
        csv_path: Relative CSV path (e.g. '671/T1/671_T1_...csv').
        registry: Pre-loaded registry dict, or None to load from disk.

    Returns:
        dict with keys: subject_id, height_cm, weight_kg,
                        height_source, weight_source.
        Values are None when not found.
    """
    subject_id = extract_subject_id(csv_path)
    result = {
        "subject_id": subject_id,
        "height_cm": None,
        "weight_kg": None,
        "height_source": None,
        "weight_source": None,
    }
    if subject_id is None:
        return result

    if registry is None:
        registry = load_subjects_registry()

    entry = registry.get(subject_id, {})
    if entry.get("height_cm") is not None:
        result["height_cm"] = float(entry["height_cm"])
        result["height_source"] = entry.get("height_source", "registry")
    if entry.get("weight_kg") is not None:
        result["weight_kg"] = float(entry["weight_kg"])
        result["weight_source"] = entry.get("weight_source", "registry")

    return result


# --- Load YAML and build CONFIG ---
_raw = load_yaml_config()
_raw = _apply_defaults(_raw)

CONFIG = dict(_raw)

# --- Inject subject anthropometrics from registry (if current_csv is set) ---
_csv_path = CONFIG.get("current_csv")
if _csv_path:
    _anthro = get_subject_anthropometrics(_csv_path)
    # Only set from registry if not already set in YAML (YAML wins if explicitly set)
    if CONFIG.get("subject_id") is None:
        CONFIG["subject_id"] = _anthro["subject_id"]
    if CONFIG.get("subject_height_cm") is None and _anthro["height_cm"] is not None:
        CONFIG["subject_height_cm"] = _anthro["height_cm"]
        CONFIG["subject_height_source"] = _anthro["height_source"]
    if CONFIG.get("subject_mass_kg") is None and _anthro["weight_kg"] is not None:
        CONFIG["subject_mass_kg"] = _anthro["weight_kg"]
        CONFIG["subject_weight_source"] = _anthro["weight_source"]

# Uppercase aliases so existing code (notebooks, reference.py, pipeline.py, qc.py) keeps working
for yaml_key, cfg_key in _UPPERCASE_ALIASES.items():
    CONFIG[cfg_key] = CONFIG.get(yaml_key) if CONFIG.get(yaml_key) is not None else _ALIAS_DEFAULTS.get(cfg_key)

# THRESH with uppercase keys for qc.py and any code using CONFIG["THRESH"]["BONE_CV_ALERT"] etc.
CONFIG["THRESH"] = _build_thresh(CONFIG.get("thresh") or {})

# step_06: enforce_cleaning (surgical repair when Critical; false = audit only)
_step06 = CONFIG.get("step_06") if isinstance(CONFIG.get("step_06"), dict) else {}
CONFIG["ENFORCE_CLEANING"] = _step06.get("enforce_cleaning", False)
