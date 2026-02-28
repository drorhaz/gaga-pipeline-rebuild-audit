"""
Forensic QA Report — Configuration Constants
=============================================
Centralised thresholds, representative joints, and plot styling
used by forensic_report.py and forensic_plots.py.

Author: Gaga Motion Analysis Pipeline v3.1
"""

# ---------------------------------------------------------------------------
# Acceleration spike threshold
# 50 m/s² ≈ 50 000 mm/s²  (maximum plausible human segment acceleration,
# per Hatze 2002 — conservative for dance / athletic movement).
# ---------------------------------------------------------------------------
ACCEL_SPIKE_THRESHOLD_MM_S2 = 50_000.0

# ---------------------------------------------------------------------------
# Representative joints for PSD and Jerk analysis
# ---------------------------------------------------------------------------
REPRESENTATIVE_JOINTS = ["Hips", "RightHand", "Head"]

FALLBACK_JOINTS = {
    "Hips":      ["Spine"],
    "RightHand": ["LeftHand", "RightForeArm", "LeftForeArm"],
    "Head":      ["Neck"],
}

# ---------------------------------------------------------------------------
# PSD parameters
# ---------------------------------------------------------------------------
PSD_MIN_SEGMENT_FRAMES = 256        # Minimum contiguous valid run for Welch
PSD_NPERSEG = 256                   # Welch window length (frames)
PSD_SIGNAL_BAND_HZ = (0.5, 20.0)   # Movement band (exclude DC)
PSD_NOISE_FLOOR_HZ = (20.0, 55.0)  # Noise estimation band

# ---------------------------------------------------------------------------
# Gap heatmap
# ---------------------------------------------------------------------------
GAP_HEATMAP_BIN_SEC = 1.0

# ---------------------------------------------------------------------------
# Bone integrity status thresholds (mirror qc.py convention)
# ---------------------------------------------------------------------------
BONE_CV_GOLD = 0.02    # ≤ 2 %
BONE_CV_WARN = 0.05    # ≤ 5 %
# > 5 % → FAIL

# ---------------------------------------------------------------------------
# Minimum data guard — refuse to generate a report on < 2 s of data
# ---------------------------------------------------------------------------
MIN_FRAMES_FACTOR = 2   # multiplied by fs

# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
PLOT_DPI = 150
PLOT_STYLE = "seaborn-v0_8-whitegrid"
PLOT_FIGSIZE_DASHBOARD = (16, 12)
PLOT_FIGSIZE_SINGLE = (12, 6)

# Colour palette (consistent across all forensic plots)
COLOR_RAW = "#E07B39"       # warm orange
COLOR_CLEAN = "#3B7DD8"     # blue
COLOR_HIGH_VEL = "#D63B3B"  # red
COLOR_GOLD_ZONE = "#C8E6C9" # light green fill
COLOR_WARN_ZONE = "#FFF9C4" # light yellow fill
COLOR_FAIL_ZONE = "#FFCDD2" # light red fill

# Artifact timeline markers
COLOR_TIER1 = "#D32F2F"     # red
COLOR_TIER2 = "#FFA000"     # amber
COLOR_TIER3 = "#388E3C"     # green
