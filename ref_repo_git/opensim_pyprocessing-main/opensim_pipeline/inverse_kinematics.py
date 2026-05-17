"""OpenSim inverse kinematics."""

from __future__ import annotations

from pathlib import Path

import opensim as osim

from opensim_pipeline.io_utils import parse_ik_marker_weights_tsv


def run_ik(
    trc_file: str | Path,
    model_file: str | Path,
    ik_weights_tsv: str | Path,
    output_dir: str | Path | None = None,
    time_range: tuple[float, float] | None = None,
) -> str:
    """Run inverse kinematics on a TRC marker file.

    Parameters
    ----------
    trc_file : str or Path
        TRC file with marker data.
    model_file : str or Path
        Scaled .osim model file.
    ik_weights_tsv : str or Path
        IK marker weights TSV file.
    output_dir : str or Path, optional
        Output directory. Defaults to the TRC file's directory.
    time_range : tuple[float, float], optional
        (start, end) time in seconds. Defaults to the full TRC duration.

    Returns
    -------
    str
        Path to the output IK .mot file.
    """
    trc_file = Path(trc_file).resolve()
    model_file = Path(model_file).resolve()

    if output_dir is None:
        output_dir = trc_file.parent
    else:
        output_dir = Path(output_dir).resolve()

    ik_weights = parse_ik_marker_weights_tsv(ik_weights_tsv)

    if time_range is None:
        marker_table = osim.TimeSeriesTableVec3(str(trc_file))
        times = marker_table.getIndependentColumn()
        time_range = (times[0], times[-1])

    output_motion_file = output_dir / (trc_file.stem + "_ik.mot")

    model = osim.Model(str(model_file))

    ik_tool = osim.InverseKinematicsTool()
    ik_tool.setModel(model)
    ik_tool.setMarkerDataFileName(str(trc_file))
    ik_tool.setStartTime(time_range[0])
    ik_tool.setEndTime(time_range[1])
    ik_tool.setOutputMotionFileName(str(output_motion_file))

    task_set = ik_tool.getIKTaskSet()
    task_set.clearAndDestroy()
    for m in ik_weights:
        task = osim.IKMarkerTask()
        task.setName(m["marker"])
        task.setApply(m["apply"])
        task.setWeight(m["weight"])
        task_set.cloneAndAppend(task)

    ik_tool.run()

    return str(output_motion_file)
