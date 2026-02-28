# Anatomical Region Mapping for Engineering Reports

## Overview

Phase 2+ enhancement: Human-readable anatomical region aggregation for the engineering audit report.

Instead of showing individual joints like `LeftForeArm` and `RightForeArm`, the report now aggregates them into clinically meaningful regions like **"Elbows"**.

---

## Anatomical Region Definitions

| Region | Technical Joints Included | Aggregation Method |
|--------|---------------------------|-------------------|
| **Neck** | `Neck` | Direct (single joint) |
| **Shoulders** | `LeftShoulder`, `RightShoulder` | Max (most active side) |
| **Elbows** | `LeftForeArm`, `RightForeArm` | Max (most active side) |
| **Wrists** | `LeftHand`, `RightHand` | Max (most active side) |
| **Spine** | `Spine`, `Spine1` | Max (most active segment) |
| **Hips** | `Hips`, `LeftUpLeg`, `RightUpLeg` | Max (includes pelvis + hip joints) |
| **Knees** | `LeftLeg`, `RightLeg` | Max (most active side) |
| **Ankles** | `LeftFoot`, `RightFoot` | Max (most active side) |

---

## Why This Mapping?

### Clinical Relevance
Clinicians and researchers think in terms of **body regions**, not individual joint names:
- "How much did the patient move their elbows?" ✅
- "What's the path length of LeftForeArm vs RightForeArm?" ❌ (too technical)

### Bilateral Aggregation
For paired limbs, we report the **maximum** value to capture the most active side:
- `Elbows = max(LeftForeArm, RightForeArm)`
- This highlights asymmetry and identifies the dominant limb

### Example
```
Raw data:
  LeftForeArm:  45.2m
  RightForeArm: 48.7m

Anatomical report:
  Elbows: 48.7m  (Right-dominant)
```

---

## Technical Joint → Anatomical Region Mapping

### Why "LeftForeArm" = "Elbows"?

In motion capture, joint names represent **segments** (bones), not anatomical landmarks:

| MoCap Joint Name | Anatomical Meaning | Clinical Term |
|------------------|-------------------|---------------|
| `LeftArm` | Humerus (upper arm bone) | Upper Arm |
| `LeftForeArm` | Radius + Ulna (forearm bones) | Elbow-to-Wrist segment |
| `LeftHand` | Carpals + Metacarpals | Wrist |
| `LeftUpLeg` | Femur (thigh bone) | Thigh |
| `LeftLeg` | Tibia + Fibula (shin bones) | Knee-to-Ankle segment |
| `LeftFoot` | Tarsals (ankle bones) | Ankle |

**Key Insight:** The `ForeArm` segment moves when you bend/extend your **elbow**, so it's the best proxy for "elbow movement."

---

## Implementation

### Location: `src/utils_nb07.py`

```python
ANATOMICAL_REGIONS = {
    "Neck": ["Neck"],
    "Shoulders": ["LeftShoulder", "RightShoulder"],
    "Elbows": ["LeftForeArm", "RightForeArm"],
    "Wrists": ["LeftHand", "RightHand"],
    "Spine": ["Spine", "Spine1"],
    "Hips": ["Hips", "LeftUpLeg", "RightUpLeg"],
    "Knees": ["LeftLeg", "RightLeg"],
    "Ankles": ["LeftFoot", "RightFoot"],
}

def aggregate_by_anatomical_region(per_segment_data, aggregation_func="max"):
    """Aggregate per-segment metrics by anatomical region."""
    # ... (see implementation)
```

### New Columns in Engineering DataFrame

**Added 8 new columns:**
1. `Path_Neck_m`
2. `Path_Shoulders_m`
3. `Path_Elbows_m`
4. `Path_Wrists_m`
5. `Path_Spine_m`
6. `Path_Hips_m`
7. `Path_Knees_m`
8. `Path_Ankles_m`

### New Section in Notebook 08

**Section 11.5: Anatomical Region View**
- Displays path lengths by body region
- Summary statistics (mean, min, max)
- Ranking of most active regions

---

## Example Output

```
================================================================================
ANATOMICAL REGION PATH LENGTHS (meters)
================================================================================

Run_ID                                           Neck  Shoulders  Elbows  Wrists  Spine  Hips  Knees  Ankles
734_T3_P2_R1_Take 2025-12-30 04.12.54 PM_002   12.45     45.23   48.71   52.34  18.92  15.67  42.18   38.45

================================================================================
REGION SUMMARY (across all runs)
================================================================================
           Neck  Shoulders  Elbows  Wrists   Spine    Hips   Knees  Ankles
mean     12.45      45.23   48.71   52.34   18.92   15.67   42.18   38.45
min      12.45      45.23   48.71   52.34   18.92   15.67   42.18   38.45
max      12.45      45.23   48.71   52.34   18.92   15.67   42.18   38.45

================================================================================
MOST ACTIVE REGIONS (ranked by average path length)
================================================================================
  1. Wrists      : 52.34m
  2. Elbows      : 48.71m
  3. Shoulders   : 45.23m
  4. Knees       : 42.18m
  5. Ankles      : 38.45m
  6. Spine       : 18.92m
  7. Hips        : 15.67m
  8. Neck        : 12.45m
```

---

## Bilateral Symmetry Labels

Also updated to use human-friendly labels:

| Internal Key | User-Friendly Label |
|--------------|---------------------|
| `upper_arm` | Upper Arms |
| `forearm` | Elbows/Forearms |
| `hand` | Wrists/Hands |
| `thigh` | Hips/Thighs |
| `shin` | Knees/Shins |
| `foot` | Ankles/Feet |

**Example:**
```
Most_Asymmetric_Pair: "Elbows/Forearms"  (instead of "forearm")
```

---

## Benefits

### For Clinicians
- ✅ Speaks their language ("elbows" not "forearms")
- ✅ Quick assessment of regional movement
- ✅ Easy comparison between body regions

### For Researchers
- ✅ Both views available (raw + aggregated)
- ✅ Maintains full traceability
- ✅ Excel export includes all columns

### For Interpretation
- ✅ Identifies movement patterns (e.g., upper body vs lower body)
- ✅ Flags asymmetry at the region level
- ✅ Simplifies reporting for non-technical audiences

---

## Files Modified

1. `src/utils_nb07.py`
   - Added `ANATOMICAL_REGIONS` constant
   - Added `BILATERAL_PAIR_LABELS` constant
   - Added `aggregate_by_anatomical_region()` function
   - Updated `extract_phase2_metrics()` to compute region aggregation
   - Added 8 new columns to `build_engineering_profile_row()`

2. `notebooks/08_engineering_physical_audit.ipynb`
   - Added Section 11.5 (Anatomical Region View)
   - Displays region-level summary table
   - Shows ranking of most active regions

---

## Testing

```bash
# 1. Re-run notebook 06 (if needed, to ensure Phase 2 data exists)
# 2. Run notebook 08
# 3. Check Section 11.5 for anatomical region breakdown
# 4. Verify Excel export includes new Path_*_m columns
```

---

## Future Enhancements

Potential additions:
- Anatomical heatmaps (color-coded by activity)
- Region-specific outlier analysis
- Time-series plots per region
- Clinical interpretation guidelines (normative values)

---

## Reference

- **Joint naming:** `docs/JOINT_NAMING_CONVENTION.md`
- **Phase 2 overview:** `docs/PHASE_2_IMPLEMENTATION_SUMMARY.md`
- **Full implementation:** `src/utils_nb07.py` lines 1-50
