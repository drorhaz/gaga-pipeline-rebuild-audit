import numpy as np
import pandas as pd

def build_master_tables(
    run_id,
    time_s,
    frame_idx,
    joint_names,
    joints_export_mask,
    joints_viz_mask,
    qc_frame_valid,
    pos_world_m,
    pos_rootrel_m,
    rotvec,
    rv_mag,
    omega,
    omega_mag,
    vpos_world,
    vpos_rootrel,
    # Ticket 004: session label columns (UD-006 Option A). All str/None; session-constant.
    subject_id=None,
    timepoint=None,
    piece=None,
    rep=None,
):
    base = {
        "run_id": run_id,
        "frame_idx": frame_idx,
        "time_s": time_s,
        "qc_frame_valid": qc_frame_valid.astype(int),
    }
    # Ticket 004: inject session label columns when provided
    if subject_id is not None:
        base["subject_id"] = subject_id
    if timepoint is not None:
        base["timepoint"] = timepoint
    if piece is not None:
        base["piece"] = piece
    if rep is not None:
        base["rep"] = rep

    df_full = pd.DataFrame(base)

    def add_joint_cols(df, j, name):
        df[f"{name}__pos_world_x"] = pos_world_m[:, j, 0]
        df[f"{name}__pos_world_y"] = pos_world_m[:, j, 1]
        df[f"{name}__pos_world_z"] = pos_world_m[:, j, 2]

        df[f"{name}__pos_rootrel_x"] = pos_rootrel_m[:, j, 0]
        df[f"{name}__pos_rootrel_y"] = pos_rootrel_m[:, j, 1]
        df[f"{name}__pos_rootrel_z"] = pos_rootrel_m[:, j, 2]

        df[f"{name}__rv_x"] = rotvec[:, j, 0]
        df[f"{name}__rv_y"] = rotvec[:, j, 1]
        df[f"{name}__rv_z"] = rotvec[:, j, 2]
        df[f"{name}__rv_mag"] = rv_mag[:, j]

        df[f"{name}__omega_x"] = omega[:, j, 0]
        df[f"{name}__omega_y"] = omega[:, j, 1]
        df[f"{name}__omega_z"] = omega[:, j, 2]
        df[f"{name}__omega_mag"] = omega_mag[:, j]

        df[f"{name}__vpos_world_x"] = vpos_world[:, j, 0]
        df[f"{name}__vpos_world_y"] = vpos_world[:, j, 1]
        df[f"{name}__vpos_world_z"] = vpos_world[:, j, 2]
        df[f"{name}__vpos_world_mag"] = np.linalg.norm(vpos_world[:, j, :], axis=1)

        df[f"{name}__vpos_rootrel_x"] = vpos_rootrel[:, j, 0]
        df[f"{name}__vpos_rootrel_y"] = vpos_rootrel[:, j, 1]
        df[f"{name}__vpos_rootrel_z"] = vpos_rootrel[:, j, 2]
        df[f"{name}__vpos_rootrel_mag"] = np.linalg.norm(vpos_rootrel[:, j, :], axis=1)

    for j, name in enumerate(joint_names):
        if joints_export_mask[j]:
            add_joint_cols(df_full, j, name)

    df_viz = pd.DataFrame(base)
    for j, name in enumerate(joint_names):
        if joints_viz_mask[j]:
            add_joint_cols(df_viz, j, name)

    return df_full, df_viz