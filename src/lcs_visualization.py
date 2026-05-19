"""
Local Coordinate System (LCS) Visualization
===========================================
Per ISB recommendations - Visual verification of coordinate system stability

CRITICAL: Displaying X, Y, Z axis arrows on each joint is the only way to
visually verify that ISB orientation is stable and not "spinning" due to
sequence errors or gimbal lock.

Author: Gaga Motion Analysis Pipeline
Date: 2026-01-22
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.spatial.transform import Rotation as R

# ============================================================
# VISUALIZATION PARAMETERS
# ============================================================

LCS_ARROW_LENGTH = 50.0  # mm - length of coordinate axes
LCS_ARROW_WIDTH = 2.0    # Line width for axes
LCS_COLORS = {
    'X': 'red',      # X-axis: red
    'Y': 'green',    # Y-axis: green
    'Z': 'blue'      # Z-axis: blue
}


def quaternion_to_rotation_matrix(quat):
    """
    Convert quaternion to 3x3 rotation matrix.
    
    Parameters:
    -----------
    quat : array-like, shape (4,) or (N, 4)
        Quaternion in [x, y, z, w] format
        
    Returns:
    --------
    np.ndarray : Rotation matrix, shape (3, 3) or (N, 3, 3)
    """
    quat = np.asarray(quat)
    single = quat.ndim == 1
    
    if single:
        quat = quat.reshape(1, -1)
    
    # Use scipy for robust conversion
    rot = R.from_quat(quat)
    rot_mat = rot.as_matrix()
    
    return rot_mat[0] if single else rot_mat


def compute_lcs_axes(position, quaternion, axis_length=50.0):
    """
    Compute LCS axis endpoints from position and orientation.
    
    Parameters:
    -----------
    position : np.ndarray, shape (3,)
        Joint position [x, y, z]
    quaternion : np.ndarray, shape (4,)
        Joint orientation [qx, qy, qz, qw]
    axis_length : float
        Length of axes in mm
        
    Returns:
    --------
    dict : LCS axes with start and end points
        {'X': (start, end), 'Y': (start, end), 'Z': (start, end)}
    """
    # Get rotation matrix
    rot_mat = quaternion_to_rotation_matrix(quaternion)
    
    # Extract axis vectors
    x_axis = rot_mat[:, 0]  # First column
    y_axis = rot_mat[:, 1]  # Second column
    z_axis = rot_mat[:, 2]  # Third column
    
    # Compute endpoints
    axes = {
        'X': (position, position + x_axis * axis_length),
        'Y': (position, position + y_axis * axis_length),
        'Z': (position, position + z_axis * axis_length)
    }
    
    return axes


def plot_skeleton_with_lcs(positions, quaternions, joint_names, 
                           bone_hierarchy, frame_idx=0,
                           show_axes_for=None, axis_length=50.0,
                           figsize=(12, 10)):
    """
    Plot skeleton with LCS axes at each joint.
    
    Parameters:
    -----------
    positions : dict
        Joint positions {joint_name: (T, 3) array}
    quaternions : dict
        Joint quaternions {joint_name: (T, 4) array}
    joint_names : list
        List of joint names to display
    bone_hierarchy : list
        List of (parent, child) bone connections
    frame_idx : int
        Frame index to display
    show_axes_for : list, optional
        List of joints to show LCS for (None = all joints)
    axis_length : float
        Length of LCS axes in mm
    figsize : tuple
        Figure size
        
    Returns:
    --------
    fig, ax : Matplotlib figure and axis
    """
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection='3d')
    
    # Plot skeleton bones
    for parent, child in bone_hierarchy:
        if parent in positions and child in positions:
            parent_pos = positions[parent][frame_idx]
            child_pos = positions[child][frame_idx]
            
            if not (np.isnan(parent_pos).any() or np.isnan(child_pos).any()):
                ax.plot([parent_pos[0], child_pos[0]],
                       [parent_pos[1], child_pos[1]],
                       [parent_pos[2], child_pos[2]],
                       'k-', linewidth=1.5, alpha=0.6)
    
    # Plot joints
    for joint in joint_names:
        if joint in positions:
            pos = positions[joint][frame_idx]
            if not np.isnan(pos).any():
                ax.scatter(*pos, c='black', s=30, alpha=0.8)
    
    # Plot LCS axes
    joints_to_show = show_axes_for if show_axes_for is not None else joint_names
    
    for joint in joints_to_show:
        if joint in positions and joint in quaternions:
            pos = positions[joint][frame_idx]
            quat = quaternions[joint][frame_idx]
            
            if not (np.isnan(pos).any() or np.isnan(quat).any()):
                # Compute LCS axes
                axes = compute_lcs_axes(pos, quat, axis_length)
                
                # Plot X, Y, Z axes
                for axis_name, (start, end) in axes.items():
                    ax.plot([start[0], end[0]],
                           [start[1], end[1]],
                           [start[2], end[2]],
                           color=LCS_COLORS[axis_name],
                           linewidth=LCS_ARROW_WIDTH,
                           label=f'{axis_name}-axis' if joint == joints_to_show[0] else '')
                
                # Add joint label
                ax.text(pos[0], pos[1], pos[2], joint, fontsize=6, alpha=0.7)
    
    # Set axis labels and title
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_zlabel('Z (mm)')
    ax.set_title(f'Skeleton with Local Coordinate Systems (Frame {frame_idx})')
    
    # Equal aspect ratio
    ax.set_box_aspect([1,1,1])
    
    # Legend (only once)
    if len(joints_to_show) > 0:
        ax.legend()
    
    return fig, ax


def create_lcs_animation(positions, quaternions, joint_names,
                         bone_hierarchy, frames=None,
                         show_axes_for=None, axis_length=50.0,
                         output_path=None, fps=30):
    """
    Create animation of skeleton with LCS over time.
    
    Parameters:
    -----------
    positions : dict
        Joint positions {joint_name: (T, 3) array}
    quaternions : dict
        Joint quaternions {joint_name: (T, 4) array}
    joint_names : list
        List of joint names
    bone_hierarchy : list
        List of (parent, child) bone connections
    frames : list, optional
        List of frame indices to animate (None = all frames)
    show_axes_for : list, optional
        List of joints to show LCS for
    axis_length : float
        Length of LCS axes
    output_path : str, optional
        Path to save animation (MP4 or GIF)
    fps : int
        Frames per second for animation
        
    Returns:
    --------
    matplotlib.animation.FuncAnimation
    """
    from matplotlib.animation import FuncAnimation
    
    # Determine frames to animate
    if frames is None:
        total_frames = len(positions[joint_names[0]])
        frames = range(0, total_frames, max(1, total_frames // 300))  # Max 300 frames
    
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # Compute global bounds
    all_positions = []
    for joint in joint_names:
        if joint in positions:
            all_positions.append(positions[joint])
    all_positions = np.vstack(all_positions)
    
    x_min, y_min, z_min = np.nanmin(all_positions, axis=0)
    x_max, y_max, z_max = np.nanmax(all_positions, axis=0)
    
    # Set consistent axis limits
    ax.set_xlim([x_min - 100, x_max + 100])
    ax.set_ylim([y_min - 100, y_max + 100])
    ax.set_zlim([z_min - 100, z_max + 100])
    
    def update(frame_idx):
        ax.clear()
        
        # Plot skeleton bones
        for parent, child in bone_hierarchy:
            if parent in positions and child in positions:
                parent_pos = positions[parent][frame_idx]
                child_pos = positions[child][frame_idx]
                
                if not (np.isnan(parent_pos).any() or np.isnan(child_pos).any()):
                    ax.plot([parent_pos[0], child_pos[0]],
                           [parent_pos[1], child_pos[1]],
                           [parent_pos[2], child_pos[2]],
                           'k-', linewidth=1.5, alpha=0.6)
        
        # Plot LCS axes
        joints_to_show = show_axes_for if show_axes_for is not None else joint_names
        
        for joint in joints_to_show:
            if joint in positions and joint in quaternions:
                pos = positions[joint][frame_idx]
                quat = quaternions[joint][frame_idx]
                
                if not (np.isnan(pos).any() or np.isnan(quat).any()):
                    axes = compute_lcs_axes(pos, quat, axis_length)
                    
                    for axis_name, (start, end) in axes.items():
                        ax.plot([start[0], end[0]],
                               [start[1], end[1]],
                               [start[2], end[2]],
                               color=LCS_COLORS[axis_name],
                               linewidth=LCS_ARROW_WIDTH)
        
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_zlabel('Z (mm)')
        ax.set_title(f'Frame {frame_idx} / {frames[-1]}')
        ax.set_xlim([x_min - 100, x_max + 100])
        ax.set_ylim([y_min - 100, y_max + 100])
        ax.set_zlim([z_min - 100, z_max + 100])
    
    anim = FuncAnimation(fig, update, frames=frames, interval=1000/fps)
    
    if output_path:
        anim.save(output_path, fps=fps, writer='pillow' if output_path.endswith('.gif') else 'ffmpeg')
        print(f"Animation saved: {output_path}")
    
    return anim


def plot_lcs_stability_check(quaternions, joint_name, frame_range=None):
    """
    Plot LCS axis orientation over time to check for spinning/instability.
    
    Parameters:
    -----------
    quaternions : np.ndarray, shape (T, 4)
        Quaternion timeseries for one joint
    joint_name : str
        Joint name
    frame_range : tuple, optional
        (start, end) frame range to plot
        
    Returns:
    --------
    fig : Matplotlib figure
    """
    if frame_range:
        start, end = frame_range
        quaternions = quaternions[start:end]
    
    T = len(quaternions)
    
    # Convert quaternions to rotation matrices
    rot_mats = quaternion_to_rotation_matrix(quaternions)
    
    # Extract X, Y, Z axis vectors over time
    x_axes = rot_mats[:, :, 0]  # (T, 3)
    y_axes = rot_mats[:, :, 1]
    z_axes = rot_mats[:, :, 2]
    
    # Plot
    fig, axes = plt.subplots(3, 1, figsize=(12, 9))
    
    axes[0].plot(x_axes[:, 0], 'r-', label='X_x', alpha=0.7)
    axes[0].plot(x_axes[:, 1], 'g-', label='X_y', alpha=0.7)
    axes[0].plot(x_axes[:, 2], 'b-', label='X_z', alpha=0.7)
    axes[0].set_ylabel('X-axis components')
    axes[0].set_title(f'{joint_name} - LCS Stability Check')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    axes[1].plot(y_axes[:, 0], 'r-', label='Y_x', alpha=0.7)
    axes[1].plot(y_axes[:, 1], 'g-', label='Y_y', alpha=0.7)
    axes[1].plot(y_axes[:, 2], 'b-', label='Y_z', alpha=0.7)
    axes[1].set_ylabel('Y-axis components')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    axes[2].plot(z_axes[:, 0], 'r-', label='Z_x', alpha=0.7)
    axes[2].plot(z_axes[:, 1], 'g-', label='Z_y', alpha=0.7)
    axes[2].plot(z_axes[:, 2], 'b-', label='Z_z', alpha=0.7)
    axes[2].set_ylabel('Z-axis components')
    axes[2].set_xlabel('Frame')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    return fig
