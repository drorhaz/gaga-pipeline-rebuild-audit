"""C3D file export to OpenSim TRC (markers) and MOT (forces) formats."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import opensim as osim
from scipy.interpolate import CubicSpline

from opensim_pipeline.io_utils import fix_mot_header
from opensim_pipeline.transforms import transform_data_table

logger = logging.getLogger(__name__)

# Default lab-to-OpenSim coordinate transformation matrix.
DEFAULT_TRANSFORM = np.array(
    [
        [0, 0, -1, 0],
        [-1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
    ],
    dtype=float,
)


def rename_grf_columns(table: osim.TimeSeriesTable) -> None:
    """Rename GRF columns from C3D default to OpenSim convention.

    Maps columns like ``f1_1``, ``p2_3``, ``m1_2`` to
    ``ground_force_1_vx``, ``ground_force_2_pz``, ``ground_torque_1_y``, etc.

    Parameters
    ----------
    table : osim.TimeSeriesTable
        Flattened forces table whose columns will be renamed in-place.
    """
    component_map = {"1": "x", "2": "y", "3": "z"}
    type_map = {
        "f": "ground_force_{}_v{}",
        "p": "ground_force_{}_p{}",
        "m": "ground_torque_{}_{}",
    }

    labels = list(table.getColumnLabels())
    new_labels = osim.StdVectorString()

    for label in labels:
        if (
            len(label) >= 4
            and label[0] in type_map
            and label[1].isdigit()
            and label[2] == "_"
            and label[3].isdigit()
        ):
            col_type = label[0]
            platform = label[1]
            component = label[3]
            new_label = type_map[col_type].format(
                platform, component_map[component]
            )
            new_labels.append(new_label)
        else:
            new_labels.append(label)

    table.setColumnLabels(new_labels)


def fill_marker_gaps(
    marker_table: osim.TimeSeriesTableVec3,
    max_missing_samples: int,
) -> None:
    """Fill gaps (NaN values) in the marker table using cubic spline interpolation.

    Iterates over each marker column, identifies contiguous NaN gaps up to
    *max_missing_samples* frames wide, and fills them in-place using a cubic
    spline fitted to the surrounding valid data.

    Parameters
    ----------
    marker_table : osim.TimeSeriesTableVec3
        OpenSim marker table to fill in-place.
    max_missing_samples : int
        Maximum gap length (in frames) to interpolate. Gaps longer than this
        are left as NaN.
    """
    n_rows = marker_table.getNumRows()
    n_cols = marker_table.getNumColumns()
    if n_rows < 4:
        return

    # Extract all marker data into a numpy array (n_rows x n_cols x 3)
    data = np.empty((n_rows, n_cols, 3))
    for i in range(n_rows):
        row = marker_table.getRowAtIndex(i)
        for j in range(n_cols):
            v = row[j]
            data[i, j, :] = [v[0], v[1], v[2]]

    frame_indices = np.arange(n_rows)

    for col_idx in range(n_cols):
        label = marker_table.getColumnLabel(col_idx)
        col_data = data[:, col_idx, :]  # (n_rows, 3)
        is_nan = np.isnan(col_data[:, 0])

        if not np.any(is_nan):
            continue

        # Find contiguous NaN gaps
        gaps_filled = 0
        in_gap = False
        gap_start = 0

        for i in range(n_rows + 1):
            if i < n_rows and is_nan[i]:
                if not in_gap:
                    gap_start = i
                    in_gap = True
            else:
                if in_gap:
                    gap_len = i - gap_start
                    if gap_len <= max_missing_samples:
                        # Need valid data on both sides for spline
                        valid = ~is_nan
                        if np.sum(valid) >= 4:
                            for axis in range(3):
                                cs = CubicSpline(
                                    frame_indices[valid],
                                    col_data[valid, axis],
                                )
                                col_data[gap_start:i, axis] = cs(
                                    frame_indices[gap_start:i]
                                )
                            is_nan[gap_start:i] = False
                            gaps_filled += gap_len
                    in_gap = False

        if gaps_filled > 0:
            # Write filled values back into the marker table
            for i in range(n_rows):
                row = marker_table.getRowAtIndex(i)
                row[col_idx] = osim.Vec3(
                    float(col_data[i, 0]),
                    float(col_data[i, 1]),
                    float(col_data[i, 2]),
                )
                marker_table.setRowAtIndex(i, row)
            logger.info(
                "    Filled %d gap frames for marker %s", gaps_filled, label
            )


def export_c3d_to_trc_and_mot(
    c3d_file_path: str | Path,
    output_dir: str | Path | None = None,
    lab_to_opensim_transform: np.ndarray | None = None,
    max_missing_samples: int = 0,
) -> dict[str, str]:
    """Export marker coordinates and forces from a C3D file.

    Produces a TRC file with marker coordinates (always) and a MOT file with
    force platform data (if forces are present in the C3D).

    Parameters
    ----------
    c3d_file_path : str or Path
        Path to the C3D file.
    output_dir : str or Path, optional
        Output directory. Defaults to the input file's directory.
    lab_to_opensim_transform : np.ndarray, optional
        4x4 homogeneous transformation matrix from lab coordinates to OpenSim
        coordinates. Defaults to ``DEFAULT_TRANSFORM``.
    max_missing_samples : int, optional
        Maximum gap length (in frames) to interpolate using cubic spline.
        Set to 0 to disable gap-filling. Defaults to 0.

    Returns
    -------
    dict[str, str]
        Keys ``'trc_file'`` and optionally ``'mot_file'`` with output paths.
    """
    if lab_to_opensim_transform is None:
        lab_to_opensim_transform = DEFAULT_TRANSFORM

    c3d_adapter = osim.C3DFileAdapter()
    c3d_adapter.setLocationForForceExpression(
        osim.C3DFileAdapter.ForceLocation_CenterOfPressure
    )
    trc_adapter = osim.TRCFileAdapter()
    mot_adapter = osim.STOFileAdapter()

    c3d_path = Path(c3d_file_path)
    tables = c3d_adapter.read(str(c3d_path))

    out_dir = Path(output_dir) if output_dir is not None else c3d_path.parent
    output_files: dict[str, str] = {}

    # Export markers to TRC
    marker_table = c3d_adapter.getMarkersTable(tables)
    if max_missing_samples > 0:
        fill_marker_gaps(marker_table, max_missing_samples)
    transform_data_table(marker_table, lab_to_opensim_transform)
    trc_file = str(out_dir / (c3d_path.stem + ".trc"))
    trc_adapter.write(marker_table, trc_file)
    output_files["trc_file"] = trc_file

    # Export forces to MOT (if present)
    try:
        forces_table_vec3 = c3d_adapter.getForcesTable(tables)
        transform_data_table(forces_table_vec3, lab_to_opensim_transform)
        forces_table = forces_table_vec3.flatten()
        if forces_table.getNumRows() > 0:
            rename_grf_columns(forces_table)
            mot_file = str(out_dir / (c3d_path.stem + ".mot"))
            mot_adapter.write(forces_table, mot_file)
            fix_mot_header(mot_file)
            output_files["mot_file"] = mot_file
    except Exception as e:
        logger.warning("No forces exported from %s: %s", c3d_path.name, e)

    return output_files
