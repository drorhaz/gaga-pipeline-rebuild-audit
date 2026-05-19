"""
Interactive Synchronized Visualization for Master Audit Section 5
================================================================
ISB Compliance Verification + Time-Synced Stick Figure with LCS + Kinematics

Purpose: Provide "Visual Proof" for supervisors with:
1. ISB Euler sequence verification
2. Interactive 3D skeleton with LCS axes (X/Y/Z arrows)
3. Time-synchronized kinematic plots (position/velocity)
4. Shared slider that updates all visualizations simultaneously

Author: Gaga Motion Analysis Pipeline
Date: 2026-01-22
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.spatial.transform import Rotation as R
import json

# ============================================================
# ISB COMPLIANCE CHECKING
# ============================================================

def verify_isb_compliance(euler_validation_json_path):
    """
    Verify that Euler sequences match ISB standards.
    
    Parameters:
    -----------
    euler_validation_json_path : str
        Path to {run_id}__euler_validation.json from nb06
        
    Returns:
    --------
    dict : Compliance report with per-joint verification
    """
    try:
        with open(euler_validation_json_path) as f:
            validation_data = json.load(f)
        
        compliance_results = []
        violations = []
        
        for joint, data in validation_data.items():
            sequence = data.get('sequence', 'UNKNOWN')
            is_valid = data.get('is_valid', True)
            violation_count = data.get('violation_count', 0)
            rom_limits = data.get('rom_limits', 'N/A')
            angle_range = data.get('primary_angle_range', [0, 0])
            
            # Determine compliance status
            if not is_valid and violation_count > 0:
                status = "⚠️ ROM_VIOLATION"
                violations.append(joint)
            else:
                status = "✅ COMPLIANT"
            
            compliance_results.append({
                'Joint': joint,
                'ISB_Sequence': sequence,
                'ROM_Limits': str(rom_limits),
                'Actual_Range': f"[{angle_range[0]:.1f}, {angle_range[1]:.1f}]°",
                'Violations': violation_count,
                'Status': status
            })
        
        df_compliance = pd.DataFrame(compliance_results)
        
        summary = {
            'total_joints': len(df_compliance),
            'compliant_joints': (df_compliance['Status'] == '✅ COMPLIANT').sum(),
            'violation_joints': (df_compliance['Status'] == '⚠️ ROM_VIOLATION').sum(),
            'overall_status': 'PASS' if len(violations) == 0 else 'REVIEW',
            'violated_joints': violations
        }
        
        return df_compliance, summary
        
    except FileNotFoundError:
        return None, {'error': 'Euler validation JSON not found - run notebook 06 first'}


# ============================================================
# INTERACTIVE SYNCHRONIZED VISUALIZATION
# ============================================================

def quaternion_to_rotation_matrix(quat):
    """Convert quaternion [qx, qy, qz, qw] to 3x3 rotation matrix."""
    rot = R.from_quat(quat)
    return rot.as_matrix()


def create_lcs_arrows(position, quaternion, axis_length=100.0):
    """
    Create X, Y, Z axis arrows at a joint position.
    
    Returns:
    --------
    dict : {'X': (start, end), 'Y': (start, end), 'Z': (start, end)}
    """
    rot_mat = quaternion_to_rotation_matrix(quaternion)
    
    x_axis = rot_mat[:, 0]
    y_axis = rot_mat[:, 1]
    z_axis = rot_mat[:, 2]
    
    return {
        'X': (position, position + x_axis * axis_length),
        'Y': (position, position + y_axis * axis_length),
        'Z': (position, position + z_axis * axis_length)
    }


def create_interactive_synchronized_viz(df, joint_names, bone_hierarchy,
                                        show_lcs_for=None, 
                                        axis_length=100.0,
                                        sample_frames=300):
    """
    Create interactive synchronized visualization with:
    - 3D skeleton with LCS axes
    - Position plot for selected joint
    - Velocity plot for selected joint
    - Shared slider that updates all plots
    
    Parameters:
    -----------
    df : pd.DataFrame
        Kinematics DataFrame with position, quaternion, velocity data
    joint_names : list
        List of joint names
    bone_hierarchy : list
        List of (parent, child) bone connections
    show_lcs_for : list, optional
        Joints to show LCS axes for (default: ['LeftShoulder', 'RightShoulder', 'Hips'])
    axis_length : float
        Length of LCS axes in mm
    sample_frames : int
        Number of frames to include (downsample for performance)
        
    Returns:
    --------
    plotly.graph_objects.Figure : Interactive figure with slider
    """
    # Default joints to show LCS for
    if show_lcs_for is None:
        show_lcs_for = ['LeftShoulder', 'RightShoulder', 'Hips', 'Spine1']
    
    # Downsample frames for performance
    total_frames = len(df)
    frame_indices = np.linspace(0, total_frames-1, min(sample_frames, total_frames), dtype=int)
    
    # Extract time vector
    time = df['Time'].values[frame_indices]
    
    # Extract positions and quaternions
    positions = {}
    quaternions = {}
    velocities = {}
    
    for joint in joint_names:
        # Positions
        px_col = f'{joint}__px'
        py_col = f'{joint}__py'
        pz_col = f'{joint}__pz'
        
        if px_col in df.columns:
            positions[joint] = df[[px_col, py_col, pz_col]].values[frame_indices]
        
        # Quaternions
        qx_col = f'{joint}__qx'
        qy_col = f'{joint}__qy'
        qz_col = f'{joint}__qz'
        qw_col = f'{joint}__qw'
        
        if qx_col in df.columns:
            quaternions[joint] = df[[qx_col, qy_col, qz_col, qw_col]].values[frame_indices]
        
        # Velocities
        vx_col = f'{joint}__vx'
        vy_col = f'{joint}__vy'
        vz_col = f'{joint}__vz'
        
        if vx_col in df.columns:
            velocities[joint] = df[[vx_col, vy_col, vz_col]].values[frame_indices]
    
    # Create subplots: 1 row, 3 columns (3D skeleton | Position | Velocity)
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=('3D Skeleton with LCS', 'Position (mm)', 'Velocity (mm/s)'),
        specs=[[{'type': 'scatter3d'}, {'type': 'scatter'}, {'type': 'scatter'}]],
        column_widths=[0.5, 0.25, 0.25]
    )
    
    # Reference joint for kinematic plots (use Hips as default)
    ref_joint = 'Hips' if 'Hips' in positions else joint_names[0]
    
    # ============================================================
    # CREATE FRAMES FOR ANIMATION
    # ============================================================
    frames = []
    
    for i, frame_idx in enumerate(frame_indices):
        frame_data = []
        
        # --- 3D Skeleton Traces (for this frame) ---
        # Bones
        bone_x, bone_y, bone_z = [], [], []
        for parent, child in bone_hierarchy:
            if parent in positions and child in positions:
                p_pos = positions[parent][i]
                c_pos = positions[child][i]
                
                if not (np.isnan(p_pos).any() or np.isnan(c_pos).any()):
                    bone_x.extend([p_pos[0], c_pos[0], None])
                    bone_y.extend([p_pos[1], c_pos[1], None])
                    bone_z.extend([p_pos[2], c_pos[2], None])
        
        frame_data.append(go.Scatter3d(
            x=bone_x, y=bone_y, z=bone_z,
            mode='lines',
            line=dict(color='black', width=3),
            name='Skeleton',
            showlegend=(i == 0)
        ))
        
        # Joints
        joint_x = [positions[j][i][0] for j in joint_names if j in positions and not np.isnan(positions[j][i]).any()]
        joint_y = [positions[j][i][1] for j in joint_names if j in positions and not np.isnan(positions[j][i]).any()]
        joint_z = [positions[j][i][2] for j in joint_names if j in positions and not np.isnan(positions[j][i]).any()]
        
        frame_data.append(go.Scatter3d(
            x=joint_x, y=joint_y, z=joint_z,
            mode='markers',
            marker=dict(size=4, color='black'),
            name='Joints',
            showlegend=(i == 0)
        ))
        
        # LCS Axes
        lcs_colors = {'X': 'red', 'Y': 'green', 'Z': 'blue'}
        
        for joint in show_lcs_for:
            if joint in positions and joint in quaternions:
                pos = positions[joint][i]
                quat = quaternions[joint][i]
                
                if not (np.isnan(pos).any() or np.isnan(quat).any()):
                    axes = create_lcs_arrows(pos, quat, axis_length)
                    
                    for axis_name, (start, end) in axes.items():
                        frame_data.append(go.Scatter3d(
                            x=[start[0], end[0]],
                            y=[start[1], end[1]],
                            z=[start[2], end[2]],
                            mode='lines',
                            line=dict(color=lcs_colors[axis_name], width=4),
                            name=f'{axis_name}-axis' if (i == 0 and joint == show_lcs_for[0]) else '',
                            showlegend=(i == 0 and joint == show_lcs_for[0])
                        ))
        
        # --- Position Plot (X, Y, Z) ---
        if ref_joint in positions:
            frame_data.append(go.Scatter(
                x=time[:i+1],
                y=positions[ref_joint][:i+1, 0],
                mode='lines',
                line=dict(color='red', width=2),
                name='X' if i == 0 else '',
                showlegend=(i == 0)
            ))
            frame_data.append(go.Scatter(
                x=time[:i+1],
                y=positions[ref_joint][:i+1, 1],
                mode='lines',
                line=dict(color='green', width=2),
                name='Y' if i == 0 else '',
                showlegend=(i == 0)
            ))
            frame_data.append(go.Scatter(
                x=time[:i+1],
                y=positions[ref_joint][:i+1, 2],
                mode='lines',
                line=dict(color='blue', width=2),
                name='Z' if i == 0 else '',
                showlegend=(i == 0)
            ))
            
            # Current time marker
            frame_data.append(go.Scatter(
                x=[time[i], time[i]],
                y=[positions[ref_joint][:, 0].min(), positions[ref_joint][:, 0].max()],
                mode='lines',
                line=dict(color='black', width=2, dash='dash'),
                name='Current Time' if i == 0 else '',
                showlegend=(i == 0)
            ))
        
        # --- Velocity Plot (Magnitude) ---
        if ref_joint in velocities:
            vel_mag = np.linalg.norm(velocities[ref_joint][:i+1], axis=1)
            
            frame_data.append(go.Scatter(
                x=time[:i+1],
                y=vel_mag,
                mode='lines',
                line=dict(color='purple', width=2),
                name='Speed' if i == 0 else '',
                showlegend=(i == 0)
            ))
            
            # Current time marker
            frame_data.append(go.Scatter(
                x=[time[i], time[i]],
                y=[0, vel_mag.max()],
                mode='lines',
                line=dict(color='black', width=2, dash='dash'),
                name='',
                showlegend=False
            ))
        
        frames.append(go.Frame(data=frame_data, name=str(i)))
    
    # ============================================================
    # ADD INITIAL FRAME DATA
    # ============================================================
    fig.add_traces(frames[0].data)
    
    # ============================================================
    # LAYOUT CONFIGURATION
    # ============================================================
    fig.update_layout(
        height=600,
        title=dict(
            text=f"<b>Interactive Synchronized Visualization</b><br><sub>Reference Joint: {ref_joint} | LCS shown for: {', '.join(show_lcs_for)}</sub>",
            x=0.5,
            xanchor='center'
        ),
        showlegend=True,
        
        # Slider configuration
        sliders=[{
            'active': 0,
            'yanchor': 'top',
            'y': -0.1,
            'xanchor': 'left',
            'currentvalue': {
                'prefix': 'Frame: ',
                'visible': True,
                'xanchor': 'right'
            },
            'steps': [
                {
                    'args': [[f.name], {'frame': {'duration': 0, 'redraw': True}, 'mode': 'immediate'}],
                    'label': str(i),
                    'method': 'animate'
                }
                for i, f in enumerate(frames)
            ]
        }],
        
        # Play/Pause buttons
        updatemenus=[{
            'type': 'buttons',
            'showactive': False,
            'y': -0.15,
            'x': 0.1,
            'xanchor': 'left',
            'yanchor': 'top',
            'buttons': [
                {
                    'label': '▶ Play',
                    'method': 'animate',
                    'args': [None, {
                        'frame': {'duration': 50, 'redraw': True},
                        'fromcurrent': True,
                        'transition': {'duration': 0}
                    }]
                },
                {
                    'label': '⏸ Pause',
                    'method': 'animate',
                    'args': [[None], {
                        'frame': {'duration': 0, 'redraw': False},
                        'mode': 'immediate',
                        'transition': {'duration': 0}
                    }]
                }
            ]
        }]
    )
    
    # Update 3D scene
    fig.update_scenes(
        aspectmode='data',
        xaxis_title='X (mm)',
        yaxis_title='Y (mm)',
        zaxis_title='Z (mm)',
        camera=dict(
            eye=dict(x=1.5, y=1.5, z=1.5)
        )
    )
    
    # Update 2D plots
    fig.update_xaxes(title_text='Time (s)', row=1, col=2)
    fig.update_xaxes(title_text='Time (s)', row=1, col=3)
    fig.update_yaxes(title_text='Position (mm)', row=1, col=2)
    fig.update_yaxes(title_text='Velocity (mm/s)', row=1, col=3)
    
    # Add frames to figure
    fig.frames = frames
    
    return fig


def create_static_lcs_snapshot(df, joint_names, bone_hierarchy, frame_idx,
                               show_lcs_for=None, axis_length=100.0):
    """
    Create a static snapshot of skeleton with LCS at a specific frame.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Kinematics DataFrame
    joint_names : list
        List of joint names
    bone_hierarchy : list
        List of (parent, child) connections
    frame_idx : int
        Frame index to display
    show_lcs_for : list, optional
        Joints to show LCS for
    axis_length : float
        Length of LCS axes
        
    Returns:
    --------
    plotly.graph_objects.Figure
    """
    if show_lcs_for is None:
        show_lcs_for = ['LeftShoulder', 'RightShoulder', 'Hips']
    
    fig = go.Figure()
    
    # Extract data for this frame
    positions = {}
    quaternions = {}
    
    for joint in joint_names:
        px_col = f'{joint}__px'
        if px_col in df.columns:
            positions[joint] = df.loc[frame_idx, [px_col, f'{joint}__py', f'{joint}__pz']].values
        
        qx_col = f'{joint}__qx'
        if qx_col in df.columns:
            quaternions[joint] = df.loc[frame_idx, [qx_col, f'{joint}__qy', f'{joint}__qz', f'{joint}__qw']].values
    
    # Plot bones
    bone_x, bone_y, bone_z = [], [], []
    for parent, child in bone_hierarchy:
        if parent in positions and child in positions:
            p_pos = positions[parent]
            c_pos = positions[child]
            
            if not (np.isnan(p_pos).any() or np.isnan(c_pos).any()):
                bone_x.extend([p_pos[0], c_pos[0], None])
                bone_y.extend([p_pos[1], c_pos[1], None])
                bone_z.extend([p_pos[2], c_pos[2], None])
    
    fig.add_trace(go.Scatter3d(
        x=bone_x, y=bone_y, z=bone_z,
        mode='lines',
        line=dict(color='black', width=4),
        name='Skeleton'
    ))
    
    # Plot joints
    joint_x = [positions[j][0] for j in joint_names if j in positions and not np.isnan(positions[j]).any()]
    joint_y = [positions[j][1] for j in joint_names if j in positions and not np.isnan(positions[j]).any()]
    joint_z = [positions[j][2] for j in joint_names if j in positions and not np.isnan(positions[j]).any()]
    
    fig.add_trace(go.Scatter3d(
        x=joint_x, y=joint_y, z=joint_z,
        mode='markers',
        marker=dict(size=6, color='black'),
        name='Joints'
    ))
    
    # Plot LCS axes
    lcs_colors = {'X': 'red', 'Y': 'green', 'Z': 'blue'}
    
    for joint in show_lcs_for:
        if joint in positions and joint in quaternions:
            pos = positions[joint]
            quat = quaternions[joint]
            
            if not (np.isnan(pos).any() or np.isnan(quat).any()):
                axes = create_lcs_arrows(pos, quat, axis_length)
                
                for axis_name, (start, end) in axes.items():
                    fig.add_trace(go.Scatter3d(
                        x=[start[0], end[0]],
                        y=[start[1], end[1]],
                        z=[start[2], end[2]],
                        mode='lines+text',
                        line=dict(color=lcs_colors[axis_name], width=6),
                        text=['', axis_name],
                        textposition='top center',
                        textfont=dict(size=14, color=lcs_colors[axis_name]),
                        name=f'{joint} {axis_name}-axis'
                    ))
    
    fig.update_layout(
        title=f'<b>Skeleton with LCS Axes (Frame {frame_idx})</b><br><sub>ISB-Compliant Coordinate Systems</sub>',
        scene=dict(
            aspectmode='data',
            xaxis_title='X (mm)',
            yaxis_title='Y (mm)',
            zaxis_title='Z (mm)',
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
        ),
        height=700,
        showlegend=True
    )
    
    return fig
