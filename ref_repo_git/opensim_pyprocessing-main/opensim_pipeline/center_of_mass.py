"""Whole-body center of mass computation from IK results."""

from __future__ import annotations

from pathlib import Path

import opensim as osim

from opensim_pipeline.io_utils import fix_mot_header


def compute_com(
    model_file: str | Path,
    ik_mot_file: str | Path,
    output_dir: str | Path | None = None,
) -> str:
    """Compute whole-body center of mass trajectory from IK results.

    Parameters
    ----------
    model_file : str or Path
        Scaled .osim model file.
    ik_mot_file : str or Path
        IK results .mot file (joint angles).
    output_dir : str or Path, optional
        Output directory. Defaults to the IK file's directory.

    Returns
    -------
    str
        Path to the output .sto file with COM coordinates (com_x, com_y, com_z).
    """
    model_file = Path(model_file).resolve()
    ik_mot_file = Path(ik_mot_file).resolve()

    if output_dir is None:
        output_dir = ik_mot_file.parent
    else:
        output_dir = Path(output_dir).resolve()

    model = osim.Model(str(model_file))
    state = model.initSystem()

    storage = osim.Storage(str(ik_mot_file))
    if storage.isInDegrees():
        model.getSimbodyEngine().convertDegreesToRadians(storage)

    coord_set = model.getCoordinateSet()

    times: list[float] = []
    com_x: list[float] = []
    com_y: list[float] = []
    com_z: list[float] = []

    for i in range(storage.getSize()):
        state_vector = storage.getStateVector(i)
        time = state_vector.getTime()

        for j in range(coord_set.getSize()):
            coord = coord_set.get(j)
            col_indices = storage.getColumnIndicesForIdentifier(
                coord.getName()
            )
            if col_indices.getSize() > 0:
                value = state_vector.getData().get(col_indices.get(0) - 1)
                coord.setValue(state, value, False)

        model.realizePosition(state)
        com = model.calcMassCenterPosition(state)
        times.append(time)
        com_x.append(com[0])
        com_y.append(com[1])
        com_z.append(com[2])

    # Write output
    output_file = output_dir / (
        ik_mot_file.stem.replace("_ik", "") + "_com.sto"
    )
    com_table = osim.TimeSeriesTable()
    com_table.setColumnLabels(
        osim.StdVectorString(["com_x", "com_y", "com_z"])
    )
    for i in range(len(times)):
        row = osim.RowVector([com_x[i], com_y[i], com_z[i]])
        com_table.appendRow(times[i], row)

    sto_adapter = osim.STOFileAdapter()
    sto_adapter.write(com_table, str(output_file))
    fix_mot_header(output_file)

    return str(output_file)
