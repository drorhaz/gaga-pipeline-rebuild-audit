import pandas as pd
import numpy as np
import csv
import re
from pathlib import Path
from utils import normalize_joint_name
from scipy.spatial.transform import Rotation as R
from scipy.interpolate import CubicSpline
from scipy.stats import median_abs_deviation

def correct_motive_name(raw_name):
    """
    Maps Motive/OptiTrack abbreviations to standard schema names.
    """
    # 1. Handle "Asset:Bone" format
    if ":" in raw_name:
        parts = raw_name.split(":")
        asset = parts[0]
        bone = parts[-1]
        
        # FIX: If Bone Name == Asset Name (e.g. "763:763"), it is the Hips/Root
        if asset == bone:
            return "Hips"
        
        name = bone
    else:
        name = raw_name
        
    name = name.strip()

    # 2. Manual Mapping Dictionary
    mapping = {
        # Torso
        "Ab": "Spine",
        "Chest": "Spine1",
        "Hip": "Hips", 
        "Root": "Hips", # Just in case
        
        # Left Arm
        "LShoulder": "LeftShoulder",
        "LUArm": "LeftArm",
        "LFArm": "LeftForeArm",
        "LHand": "LeftHand",
        
        # Right Arm
        "RShoulder": "RightShoulder",
        "RUArm": "RightArm",
        "RFArm": "RightForeArm",
        "RHand": "RightHand",
        
        # Left Leg
        "LThigh": "LeftUpLeg",
        "LShin": "LeftLeg",
        "LFoot": "LeftFoot",
        "LToe": "LeftToeBase",
        
        # Right Leg
        "RThigh": "RightUpLeg",
        "RShin": "RightLeg",
        "RFoot": "RightFoot",
        "RToe": "RightToeBase",
        
        # Hands (Fingers)
        "LThumb1": "LeftHandThumb1", "LThumb2": "LeftHandThumb2", "LThumb3": "LeftHandThumb3",
        "LIndex1": "LeftHandIndex1", "LIndex2": "LeftHandIndex2", "LIndex3": "LeftHandIndex3",
        "LMiddle1": "LeftHandMiddle1", "LMiddle2": "LeftHandMiddle2", "LMiddle3": "LeftHandMiddle3",
        "LRing1": "LeftHandRing1", "LRing2": "LeftHandRing2", "LRing3": "LeftHandRing3",
        "LPinky1": "LeftHandPinky1", "LPinky2": "LeftHandPinky2", "LPinky3": "LeftHandPinky3",
        
        "RThumb1": "RightHandThumb1", "RThumb2": "RightHandThumb2", "RThumb3": "RightHandThumb3",
        "RIndex1": "RightHandIndex1", "RIndex2": "RightHandIndex2", "RIndex3": "RightHandIndex3",
        "RMiddle1": "RightHandMiddle1", "RMiddle2": "RightHandMiddle2", "RMiddle3": "RightHandMiddle3",
        "RRing1": "RightHandRing1", "RRing2": "RightHandRing2", "RRing3": "RightHandRing3",
        "RPinky1": "RightHandPinky1", "RPinky2": "RightHandPinky2", "RPinky3": "RightHandPinky3",
    }
    
    return mapping.get(name, name)

def extract_optitrack_calibration_metadata(rows):
    """
    Extract OptiTrack/Motive calibration metadata from CSV header rows.
    Looks for calibration quality metrics (Wand Error, Pointer RMS, etc.)
    
    Returns dict with calibration info or empty dict if not found.
    """
    calibration_data = {
        'pointer_tip_rms_error_mm': None,
        'wand_error_mm': None,
        'optitrack_version': 'unknown',
        'export_date': None
    }
    
    # OptiTrack CSVs typically have metadata in first ~10 rows
    # Format examples:
    # "Wand Calibration Error:,0.82 mm"
    # "Pointer Calibration RMS:,1.25 mm"
    # "Export Version:,1.23"
    # "Capture Date:,2025-01-15"
    
    for row in rows[:15]:  # Check first 15 rows for metadata
        if len(row) < 2:
            continue
        
        key = str(row[0]).strip().lower()
        value = str(row[1]).strip() if len(row) > 1 else ''
        
        # Wand calibration error
        if 'wand' in key and ('error' in key or 'calibration' in key):
            # Extract numeric value (e.g., "0.82 mm" -> 0.82)
            match = re.search(r'([\d.]+)', value)
            if match:
                calibration_data['wand_error_mm'] = float(match.group(1))
        
        # Pointer calibration RMS
        elif 'pointer' in key and ('rms' in key or 'error' in key or 'calibration' in key):
            match = re.search(r'([\d.]+)', value)
            if match:
                calibration_data['pointer_tip_rms_error_mm'] = float(match.group(1))
        
        # OptiTrack/Motive version
        elif any(term in key for term in ['export version', 'motive version', 'optitrack version']):
            calibration_data['optitrack_version'] = value.replace('mm', '').strip()
        
        # Capture/Export date
        elif any(term in key for term in ['capture date', 'export date', 'date']):
            calibration_data['export_date'] = value
    
    return calibration_data

def parse_optitrack_csv(csv_path, schema):
    path = Path(csv_path)
    
    # --- 1. Robustly Read Rows ---
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= 300: break

    # Extract calibration metadata from header (Enhancement 1)
    calibration_metadata = extract_optitrack_calibration_metadata(rows)

    # Find Header Row
    hdr_row_idx = None
    for i, row in enumerate(rows):
        row_lower = [str(x).strip().lower() for x in row]
        if "frame" in row_lower and any(t in row_lower for t in ["time", "time (seconds)"]):
            hdr_row_idx = i
            break
            
    if hdr_row_idx is None:
        raise ValueError("CRITICAL: Could not locate 'Frame' and 'Time' row.")

    # Find Name Row
    name_row = None
    name_row_idx = None
    for i in range(hdr_row_idx):
        if len(rows[i]) > 1 and str(rows[i][1]).strip().lower() == "name":
            name_row = rows[i]
            name_row_idx = i
            break
            
    # --- 2. Load Data ---
    df = pd.read_csv(path, header=None, skiprows=hdr_row_idx + 1, engine="python")
    
    # --- 3. Frame/Time ---
    header_tokens = [str(x).strip() for x in rows[hdr_row_idx]]
    header_lower = [x.lower() for x in header_tokens]
    
    col_frame = header_lower.index("frame") if "frame" in header_lower else 0
    col_time = -1
    for t in ["time (seconds)", "time"]:
        if t in header_lower: col_time = header_lower.index(t); break
    if col_time == -1: col_time = 1

    frame_idx = pd.to_numeric(df.iloc[:, col_frame], errors='coerce').fillna(0).astype(int).values
    time_s = pd.to_numeric(df.iloc[:, col_time], errors='coerce').fillna(0.0).astype(float).values
    T = len(time_s)

    # --- Ticket 002: S01 hard FAIL gate (conservative scope only) ---
    # USER DIRECTIVE (LD-6): duration < 30s OR frame count < 3600 → FAIL.
    # Label mismatches and column count deviations → WARN only (not FAIL).
    _gate_01_duration_sec = float(time_s[-1] - time_s[0]) if T > 1 else 0.0
    _gate_01_fail_reason = None
    if T < 3600:
        _gate_01_fail_reason = "frame_count_too_short"
    elif _gate_01_duration_sec < 30.0:
        _gate_01_fail_reason = "duration_too_short"

    if _gate_01_fail_reason is not None:
        raise ValueError(
            f"S01_GATE_FAIL:n_frames={T}:duration_sec={_gate_01_duration_sec:.3f}"
            f":reason={_gate_01_fail_reason}:threshold_frames=3600:threshold_duration_sec=30.0"
        )

    # --- 4. Scan Headers & Map Names ---
    found_cols = {} 
    
    i = 0
    while i < len(header_tokens) - 3:
        if header_tokens[i:i+4] == ["X", "Y", "Z", "W"]:
            raw_name = f"Unknown_{i}"
            if name_row and i < len(name_row):
                raw_name = str(name_row[i]).strip()
            
            # *** APPLY FIX HERE ***
            corrected_name = correct_motive_name(raw_name)
            norm_name = normalize_joint_name(corrected_name)
            
            if norm_name not in found_cols:
                found_cols[norm_name] = {'rot': None, 'pos': None}
            
            found_cols[norm_name]['rot'] = [i, i+1, i+2, i+3]
            i += 4
            
            if i < len(header_tokens) - 2 and header_tokens[i:i+3] == ["X", "Y", "Z"]:
                found_cols[norm_name]['pos'] = [i, i+1, i+2]
                i += 3
        else:
            i += 1

    # --- 5. Fill Arrays ---
    target_joints = list(schema['joint_names'])
    J = len(target_joints)
    
    pos_mm = np.full((T, J, 3), np.nan)
    q_global = np.full((T, J, 4), np.nan)
    
    joints_found = []
    joints_missing = []
    
    for idx, target_name in enumerate(target_joints):
        norm_target = normalize_joint_name(target_name)
        
        if norm_target in found_cols:
            joints_found.append(target_name)
            col = found_cols[norm_target]
            
            if col['rot']:
                indices = col['rot']
                q_global[:, idx, 0] = pd.to_numeric(df.iloc[:, indices[0]], errors='coerce').values
                q_global[:, idx, 1] = pd.to_numeric(df.iloc[:, indices[1]], errors='coerce').values
                q_global[:, idx, 2] = pd.to_numeric(df.iloc[:, indices[2]], errors='coerce').values
                q_global[:, idx, 3] = pd.to_numeric(df.iloc[:, indices[3]], errors='coerce').values
                
            if col['pos']:
                indices = col['pos']
                pos_mm[:, idx, 0] = pd.to_numeric(df.iloc[:, indices[0]], errors='coerce').values
                pos_mm[:, idx, 1] = pd.to_numeric(df.iloc[:, indices[1]], errors='coerce').values
                pos_mm[:, idx, 2] = pd.to_numeric(df.iloc[:, indices[2]], errors='coerce').values
        else:
            joints_missing.append(target_name)

# ... inside parse_optitrack_csv, after the loop ...

    # --- 6. Schema & Time Validation ---
    validate_time_vector(time_s)
    
    # Validate quaternion completeness only for joints that were actually found
    for joint_name in found_cols.keys():
        # Check if this joint has quaternion data in the parsed arrays
        joint_idx = None
        for i, target in enumerate(target_joints):
            if normalize_joint_name(target) == joint_name:
                joint_idx = i
                break
        
        if joint_idx is not None:
            # Check if we actually have quaternion data for this joint
            if not np.all(np.isnan(q_global[:, joint_idx])):
                # We have data, validate completeness
                validate_quaternion_completeness(
                    [f"{joint_name}__qx", f"{joint_name}__qy", 
                     f"{joint_name}__qz", f"{joint_name}__qw"],
                    joint_name
                )

    # --- 7. Report ---
    # MISSING LINES ADDED HERE:
    nan_pos_pct = np.mean(np.isnan(pos_mm)) * 100
    nan_rot_pct = np.mean(np.isnan(q_global)) * 100
    
    loader_report = {
        "file_path": str(csv_path),
        "gate_01_status": "PASS",
        "gate_01_n_frames": T,
        "gate_01_duration_sec": _gate_01_duration_sec,
        "total_frames": T,
        "duration_sec": time_s[-1] - time_s[0] if T > 0 else 0,
        "fps_estimated": 1.0 / np.median(np.diff(time_s)) if T > 1 else 0,
        "segments_expected": J,
        "segments_found_count": len(joints_found),
        "segments_missing_count": len(joints_missing),
        "segments_found_list": joints_found,
        "segments_missing_list": joints_missing,
        "calibration": calibration_metadata,  # Enhancement 1: Added calibration data
        "data_quality": {
            "nan_position_percent": f"{nan_pos_pct:.2f}%",
            "nan_rotation_percent": f"{nan_rot_pct:.2f}%"
        },
        "structure_info": {
            "header_row_index": hdr_row_idx,
            "name_row_index": name_row_idx,
            "total_columns": len(header_tokens)
        }
    }

    return frame_idx, time_s, pos_mm, q_global, loader_report


def compute_artifact_segment_stats(df, axis_suffixes=('__px', '__py', '__pz')):
    """
    Ticket 009: count and characterize contiguous NaN-runs across axis columns of a DataFrame.

    Used by NB02 to produce `{RUN_ID}__s02_interpolation_stats.json`. Aggregates run-length
    statistics of NaN segments across ALL columns matching `axis_suffixes`. Each run is
    counted as one segment; segments from different columns are accumulated together.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame containing position/quaternion axis columns (e.g. Hips__px).
    axis_suffixes : tuple of str
        Column suffixes to scan (default: position axes).

    Returns
    -------
    dict with keys:
        n_artifact_segments               : int
        max_artifact_segment_frames       : int (0 if no segments)
        mean_artifact_segment_frames      : float (0.0 if no segments)
        n_artifact_segments_above_5_frames : int (count with length > 5)
        n_artifact_segments_above_10_frames: int (count with length > 10)
        n_columns_scanned                 : int
        segment_lengths_summary           : dict (small histogram, optional consumer info)
    """
    import numpy as _np_t009
    import pandas as _pd_t009

    cols = [c for c in df.columns if any(c.endswith(s) for s in axis_suffixes)]
    if not cols:
        return {
            "n_artifact_segments": 0,
            "max_artifact_segment_frames": 0,
            "mean_artifact_segment_frames": 0.0,
            "n_artifact_segments_above_5_frames": 0,
            "n_artifact_segments_above_10_frames": 0,
            "n_columns_scanned": 0,
            "segment_lengths_summary": {},
        }

    all_lengths = []
    for col in cols:
        vals = df[col].values
        mask = _pd_t009.isna(vals)
        if not mask.any():
            continue
        # Run-length encoding of True runs in `mask`
        # diff trick: a run starts where mask is True AND previous is False
        # and ends where mask is True AND next is False
        padded = _np_t009.concatenate(([False], mask, [False]))
        diff = _np_t009.diff(padded.astype(_np_t009.int8))
        starts = _np_t009.where(diff == 1)[0]
        ends = _np_t009.where(diff == -1)[0]
        lengths = (ends - starts).tolist()
        all_lengths.extend(lengths)

    if not all_lengths:
        return {
            "n_artifact_segments": 0,
            "max_artifact_segment_frames": 0,
            "mean_artifact_segment_frames": 0.0,
            "n_artifact_segments_above_5_frames": 0,
            "n_artifact_segments_above_10_frames": 0,
            "n_columns_scanned": len(cols),
            "segment_lengths_summary": {},
        }

    n_above_5 = sum(1 for l in all_lengths if l > 5)
    n_above_10 = sum(1 for l in all_lengths if l > 10)
    # Compact histogram (capped to keep JSON small)
    from collections import Counter as _Counter_t009
    hist = dict(_Counter_t009(all_lengths))
    if len(hist) > 30:
        # Keep most common 30 length-buckets
        hist = dict(sorted(hist.items(), key=lambda kv: -kv[1])[:30])
    return {
        "n_artifact_segments": int(len(all_lengths)),
        "max_artifact_segment_frames": int(max(all_lengths)),
        "mean_artifact_segment_frames": float(round(sum(all_lengths) / len(all_lengths), 4)),
        "n_artifact_segments_above_5_frames": int(n_above_5),
        "n_artifact_segments_above_10_frames": int(n_above_10),
        "n_columns_scanned": int(len(cols)),
        "segment_lengths_summary": {str(k): int(v) for k, v in sorted(hist.items())},
    }


def detect_and_mask_artifacts(time_s, data, mad_multiplier=3.0, expand_frames=1):
    """
    Detect and mask non-physiological spikes using velocity-based MAD thresholding.
    
    Parameters:
    -----------
    time_s : np.ndarray
        Time vector in seconds
    data : np.ndarray
        1D position data
    mad_multiplier : float
        Multiplier for MAD threshold (default: 3.0)
    expand_frames : int
        Number of adjacent frames to mask around detected artifacts
        
    Returns:
    --------
    masked_data : np.ndarray
        Data with spikes replaced by NaN
    """
    if len(data) < 3 or len(time_s) != len(data):
        return data.copy()
    
    # Compute velocity on potentially irregular time grid
    dt = np.diff(time_s)
    # Avoid division by zero
    dt[dt <= 0] = np.median(dt[dt > 0]) if np.any(dt > 0) else 1.0/120.0
    
    # Velocity computation (m/s if data is in meters) - handle NaNs properly
    vel = np.diff(data) / dt
    abs_vel = np.abs(vel)
    
    # Remove NaNs from velocity before MAD computation
    valid_vel_mask = ~np.isnan(abs_vel)
    if not np.any(valid_vel_mask):
        return data.copy()  # All NaNs, nothing to process
    
    abs_vel_valid = abs_vel[valid_vel_mask]
    
    # Calculate MAD of absolute velocities (using only valid velocities)
    sigma = max(median_abs_deviation(abs_vel_valid, scale='normal'), 1e-6)
    threshold = mad_multiplier * sigma
    
    # Find velocity spikes (using original abs_vel to maintain length)
    spike_mask = abs_vel > threshold
    
    # Create masked copy
    masked_data = data.copy()
    
    # Mark spike points and their neighbors
    spike_indices = np.where(spike_mask)[0]
    for idx in spike_indices:
        # Mask the spike point and adjacent frames
        start_idx = max(0, idx - expand_frames)
        end_idx = min(len(masked_data), idx + expand_frames + 1)
        masked_data[start_idx:end_idx] = np.nan
    
    return masked_data


def ensure_hemispheric_continuity(q_prev, q_current):
    """
    Ensure quaternion continuity by checking hemisphere alignment.
    
    If dot(q_prev, q_current) < 0, flip q_current to same hemisphere.
    This prevents SLERP from taking the long arc (>180°).
    
    Parameters:
    -----------
    q_prev, q_current : np.ndarray
        Quaternions to check
        
    Returns:
    --------
    q_aligned : np.ndarray
        q_current aligned to same hemisphere as q_prev
    """
    if np.dot(q_prev, q_current) < 0:
        return -q_current
    return q_current


def quaternion_slerp_interpolation(time_points, quaternions, query_times):
    """
    Interpolate quaternions using SLERP with hemispheric continuity.
    
    Parameters:
    -----------
    time_points : np.ndarray
        Original time points
    quaternions : np.ndarray
        Quaternion data (N, 4)
    query_times : np.ndarray
        Times to interpolate at
        
    Returns:
    --------
    q_interp : np.ndarray
        Interpolated quaternions (M, 4)
    """
    if len(time_points) < 2:
        return quaternions.copy()
    
    # Ensure hemispheric continuity - make explicit copy
    q_continuous = quaternions.copy()
    for i in range(1, len(q_continuous)):
        if np.dot(q_continuous[i], q_continuous[i-1]) < 0:
            q_continuous[i] *= -1
    
    # Create rotation object
    rotations = R.from_quat(q_continuous)
    
    # Interpolate using scipy's built-in method
    from scipy.interpolate import interp1d
    # Create interpolator for each quaternion component
    q_interp = np.zeros((len(query_times), 4))
    for i in range(4):
        interp = interp1d(time_points, q_continuous[:, i], kind='linear')
        q_interp[:, i] = interp(query_times)
    
    # Re-normalize to unit quaternions
    norms = np.linalg.norm(q_interp, axis=1)
    norms[norms == 0] = 1.0
    q_interp = q_interp / norms[:, np.newaxis]
    
    return q_interp


def bounded_spline_interpolation(time_points, data, max_gap_s=0.1):
    """
    Fill gaps using bounded cubic spline interpolation.
    
    Only fills gaps <= max_gap_s. Gaps at boundaries remain NaN.
    
    Parameters:
    -----------
    time_points : np.ndarray
        Time vector
    data : np.ndarray
        Data with NaN gaps
    max_gap_s : float
        Maximum gap duration to fill (seconds)
        
    Returns:
    --------
    filled_data : np.ndarray
        Data with filled gaps
    """
    filled_data = data.copy()
    
    # Find NaN gaps
    nan_mask = np.isnan(data)
    
    # No gaps to fill
    if not np.any(nan_mask):
        return filled_data
    
    # Find gap start and end indices
    gap_starts = np.where(~nan_mask[:-1] & nan_mask[1:])[0] + 1
    gap_ends = np.where(nan_mask[:-1] & ~nan_mask[1:])[0] + 1
    
    # Handle case where gap starts at beginning or ends at end
    if nan_mask[0]:
        gap_starts = np.concatenate([[0], gap_starts])
    if nan_mask[-1]:
        gap_ends = np.concatenate([gap_ends, [len(data)]])
    
    # Ensure we have matching starts and ends
    if len(gap_starts) != len(gap_ends):
        # This shouldn't happen with proper gap detection
        return filled_data
    
    # Fill each gap
    for start, end in zip(gap_starts, gap_ends):
        gap_duration = time_points[end-1] - time_points[start] if end > start else 0
        
        # Skip if gap too large or at boundary
        if gap_duration > max_gap_s or start == 0 or end == len(data):
            continue
        
        # Get valid points for interpolation
        valid_mask = ~nan_mask
        valid_times = time_points[valid_mask]
        valid_data = data[valid_mask]
        
        # Need at least 4 points for cubic spline
        if len(valid_times) < 4:
            continue
        
        try:
            # Cubic spline interpolation
            spline = CubicSpline(valid_times, valid_data)
            gap_times = time_points[start:end]
            filled_data[start:end] = spline(gap_times)
        except:
            # Fallback to linear interpolation if spline fails
            filled_data[start:end] = np.interp(gap_times, valid_times, valid_data)
    
    return filled_data


def validate_time_vector(time_s):
    """
    Validate time vector monotonicity.
    
    Parameters:
    -----------
    time_s : np.ndarray
        Time vector in seconds
        
    Raises:
    -------
    ValueError
        If time is not strictly increasing
    """
    if len(time_s) < 2:
        return
    
    time_diffs = np.diff(time_s)
    
    # Check for non-positive time steps
    if np.any(time_diffs <= 0):
        # Find first violation
        violation_idx = np.where(time_diffs <= 0)[0][0]
        raise ValueError(
            f"Time vector is not monotonic at index {violation_idx}. "
            f"time[{violation_idx}] = {time_s[violation_idx]:.6f}, "
            f"time[{violation_idx+1}] = {time_s[violation_idx+1]:.6f}"
        )


def validate_quaternion_completeness(columns, joint_name):
    """
    Validate that all 4 quaternion components exist for a joint.
    
    Parameters:
    -----------
    columns : list
        Available column names
    joint_name : str
        Joint name to validate
        
    Raises:
    -------
    ValueError
        If quaternion components are incomplete
    """
    required_components = ['qx', 'qy', 'qz', 'qw']
    missing_components = []
    
    for comp in required_components:
        col_name = f"{joint_name}__{comp}"
        if col_name not in columns:
            missing_components.append(comp)
    
    if missing_components:
        raise ValueError(
            f"Incomplete quaternion data for joint '{joint_name}'. "
            f"Missing components: {missing_components}"
        )