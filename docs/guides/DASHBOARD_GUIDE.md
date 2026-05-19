# Motion Analysis Dashboard - Quick Start Guide

## Overview
**Notebook**: `notebooks/09_motion_dashboard.ipynb`  
**Purpose**: Interactive dual-panel visualization synchronizing 3D stickman animation with kinematic features

---

## Features

### **Panel 1: Feature Selection (Left)**
- **Mode A - Velocity**: Multi-joint velocity tracking (kinematic chain)
- **Mode B - Volume**: Convex hull volume over time

### **Panel 2: 3D Stickman (Right)**
- Animated skeleton based on joint connections
- **Green Bubble**: Real-time convex hull (body envelope)
- Joint markers with 3D spatial tracking

### **Synchronization**
- Red vertical line tracks current frame across both panels
- Frame counter shows exact position in recording

---

## Quick Configuration

### **1. Select Mode**
```python
MODE = 'velocity'  # or 'volume'
```

### **2. Define Kinematic Chain** (for velocity mode)
```python
# Right arm chain
JOINTS_TO_PLOT = ['RightShoulder', 'RightElbow', 'RightWrist', 'RightHand']

# Left arm chain
JOINTS_TO_PLOT = ['LeftShoulder', 'LeftElbow', 'LeftWrist', 'LeftHand']

# Right leg chain
JOINTS_TO_PLOT = ['RightHip', 'RightKnee', 'RightAnkle', 'RightFoot']
```

### **3. Set Frame Range**
```python
START_FRAME = 0       # Start frame
END_FRAME = 1200      # End frame (None = all frames)
STEP = 2              # Frame increment (1=every frame, 2=every 2nd)
```

### **4. Customize Skeleton**
Edit `SKELETON_MAP` to add/remove bone connections:
```python
SKELETON_MAP = [
    ('Pelvis', 'LowerBack'),
    ('RightShoulder', 'RightElbow'),
    # ... add more connections
]
```

---

## Usage Examples

### **Example 1: Visualize Right Arm Velocity**
```python
MODE = 'velocity'
JOINTS_TO_PLOT = ['RightShoulder', 'RightElbow', 'RightWrist', 'RightHand']
START_FRAME = 0
END_FRAME = 1200
STEP = 2
```
**Result**: Multi-line velocity plot synchronized with 3D arm movement

---

### **Example 2: Body Volume Analysis**
```python
MODE = 'volume'
START_FRAME = 0
END_FRAME = 3000
STEP = 5  # Faster playback
```
**Result**: Single-line volume plot showing body expansion/contraction

---

### **Example 3: Focus on Specific Movement Phase**
```python
MODE = 'velocity'
JOINTS_TO_PLOT = ['RightHand', 'LeftHand']  # Both hands
START_FRAME = 500    # Start at 500th frame
END_FRAME = 800      # End at 800th frame
STEP = 1             # Every frame for detail
```
**Result**: Detailed bilateral hand velocity comparison

---

## Technical Specifications

### **Data Requirements**
- **Input**: Filtered parquet file from `step_04_filtering`
- **Format**: Position columns ending with `__px`, `__py`, `__pz`
- **Assumption**: Data is already filtered and gap-filled

### **Coordinate System**
- **X**: Right (+) / Left (-)
- **Y**: Up (+) / Down (-)
- **Z**: Forward (+) / Backward (-)
- **Units**: Millimeters (mm)

### **Convex Hull**
- **Algorithm**: `scipy.spatial.ConvexHull`
- **Minimum Points**: 4 (for 3D hull)
- **Volume Units**: mm³
- **Visualization**: Green semi-transparent faces with green edges

### **Velocity Computation**
- **Method**: Central difference (`np.gradient`)
- **Units**: mm/s
- **Formula**: `v_mag = sqrt(vx² + vy² + vz²)`

---

## Performance Tips

### **For Faster Loading**
1. Increase `STEP` value (e.g., `STEP = 5` for every 5th frame)
2. Reduce `END_FRAME` to smaller range
3. Lower `FPS` for smoother playback on slow machines

### **For Better Quality**
1. Use `STEP = 1` for every frame
2. Increase `FIGSIZE` and `DPI`
3. Save as high-resolution video

### **For Large Datasets**
```python
START_FRAME = 0
END_FRAME = 10000
STEP = 10  # Every 10th frame
FPS = 30   # Standard playback speed
```

---

## Output Options

### **1. Interactive Display** (Default)
- Runs animation directly in Jupyter notebook
- Uses `to_jshtml()` for browser rendering
- Best for exploration and analysis

### **2. Save as MP4 Video**
```python
# Uncomment in "Save Animation" cell
output_file = f"{RUN_ID}_dashboard_{MODE}.mp4"
anim.save(output_file, writer='ffmpeg', fps=FPS, dpi=DPI)
```
**Requirements**: ffmpeg installed on system

### **3. Save as GIF**
```python
output_gif = f"{RUN_ID}_dashboard_{MODE}.gif"
anim.save(output_gif, writer='pillow', fps=FPS//2)
```
**Note**: Lower FPS recommended for file size

### **4. Static Snapshot**
```python
snapshot_frame = len(df_subset) // 2  # Middle frame
update_frame(snapshot_frame)
plt.savefig(f"{RUN_ID}_dashboard_snapshot.png", dpi=150)
```

---

## Customization Options

### **Colors**
```python
# Change velocity line colors
colors = plt.cm.plasma(np.linspace(0, 1, len(velocity_data)))  # Use plasma colormap

# Change skeleton color
line, = ax_right.plot([], [], [], 'r-', linewidth=3)  # Red, thicker lines

# Change convex hull color
hull_collection = Poly3DCollection(hull_faces, 
                                  facecolors='cyan',      # Change color
                                  alpha=0.3,              # Change transparency
                                  edgecolors='blue')      # Change edges
```

### **Camera Angle** (3D view)
```python
# Set initial viewing angle
ax_right.view_init(elev=20, azim=45)  # Elevation and azimuth
```

### **Animation Speed**
```python
FPS = 60  # Fast playback
FPS = 15  # Slow-motion
FPS = 30  # Standard (default)
```

---

## Troubleshooting

### **Problem: Joints not found**
**Solution**: Check marker names match exactly (case-sensitive)
```python
# List available markers
print(marker_names)

# Adjust JOINTS_TO_PLOT accordingly
JOINTS_TO_PLOT = ['RightWrist', 'RightHand']  # Use exact names
```

### **Problem: Green bubble not showing**
**Solution**: Need at least 4 valid markers per frame
```python
# Check how many valid markers per frame
valid_count = df_subset.notna().sum(axis=1)
print(f"Valid markers per frame: min={valid_count.min()}, mean={valid_count.mean():.1f}")
```

### **Problem: Animation too slow**
**Solution**: Reduce frame count
```python
STEP = 10  # Use every 10th frame
END_FRAME = 1000  # Shorter sequence
```

### **Problem: Skeleton connections missing**
**Solution**: Verify SKELETON_MAP matches your marker set
```python
# Test if joints exist
for joint1, joint2 in SKELETON_MAP:
    exists = f"{joint1}__px" in df.columns and f"{joint2}__px" in df.columns
    print(f"{joint1} <-> {joint2}: {'✅' if exists else '❌'}")
```

---

## Advanced Features

### **Compare Multiple Chains**
```python
# Add second kinematic chain
JOINTS_TO_PLOT = [
    'RightShoulder', 'RightElbow', 'RightWrist',  # Right arm
    'LeftShoulder', 'LeftElbow', 'LeftWrist'       # Left arm
]
```

### **Export Frame-by-Frame Data**
```python
# Extract data for external analysis
if MODE == 'velocity':
    velocity_df = pd.DataFrame(velocity_data)
    velocity_df['time'] = time_axis
    velocity_df.to_csv(f"{RUN_ID}_velocity_data.csv", index=False)
elif MODE == 'volume':
    volume_df = pd.DataFrame({'time': time_axis, 'volume': volume_data})
    volume_df.to_csv(f"{RUN_ID}_volume_data.csv", index=False)
```

### **Highlight Specific Events**
```python
# Add event markers (e.g., peak velocity moments)
peak_frames = np.where(velocity_data['RightHand'] > threshold)[0]
for peak in peak_frames:
    ax_left.axvline(time_axis[peak], color='orange', alpha=0.3, linewidth=1)
```

---

## Research Applications

### **1. Movement Quality Assessment**
- Track velocity smoothness in kinematic chains
- Identify jerkiness or discontinuities
- Compare left vs right side symmetry

### **2. Body Shape Analysis**
- Volume changes indicate expansion/compression
- Correlate with breathing or movement phases
- Quantify spatial occupation over time

### **3. Coordination Studies**
- Multi-joint velocity synchronization
- Lead-lag relationships in kinematic chains
- Bilateral coordination patterns

### **4. Movement Segmentation**
- Visual identification of movement phases
- Velocity peaks indicate gesture endpoints
- Volume minima/maxima mark body configuration extremes

---

## Integration with Pipeline

This dashboard integrates with the complete Gaga mocap pipeline:

1. **00_setup.ipynb** → Load configuration
2. **01_Load_Inspect.ipynb** → Import raw data
3. **02_preprocess.ipynb** → Gap filling, artifacts
4. **03_resample.ipynb** → Temporal regularization
5. **04_filtering.ipynb** → Winter filtering + validation ✅
6. **05_reference_detection.ipynb** → Calibration pose
7. **06_rotvec_omega.ipynb** → Angular kinematics + validation ✅
8. **07_master_quality_report.ipynb** → QC metrics
9. **08_visualization_and_analysis.ipynb** → Statistical analysis
10. **09_motion_dashboard.ipynb** → Interactive visualization ⭐ **NEW**

---

## Citation

When using this dashboard in publications:

```bibtex
@software{gaga_motion_dashboard,
  title = {Motion Analysis Dashboard for Gaga Dance Biomechanics},
  author = {[Your Name]},
  year = {2026},
  note = {Dual-panel synchronized visualization with 3D stickman and convex hull}
}
```

---

## Contact & Support

For questions or feature requests, please open an issue on the GitHub repository.

**Repository**: Drorhaz/Gaga-mocap-Kinematics  
**Branch**: feature/research-validation-phase1  
**Notebook**: notebooks/09_motion_dashboard.ipynb

---

*Dashboard created: January 19, 2026*  
*Version: 1.0*
