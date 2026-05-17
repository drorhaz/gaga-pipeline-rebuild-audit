"""OpenSim model scaling using a static trial."""

from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path

import opensim as osim

from opensim_pipeline.io_utils import parse_ik_marker_weights_tsv


def parse_scaling_measurements_tsv(
    tsv_path: str | Path,
) -> OrderedDict[str, dict]:
    """Parse scaling measurements from a TSV file.

    Supports multiple marker pairs per measurement: rows with blank ``bodies``
    and ``axes`` columns inherit values from the previous row.

    Parameters
    ----------
    tsv_path : str or Path
        TSV file with columns: measurement, marker1, marker2, bodies, axes.

    Returns
    -------
    OrderedDict[str, dict]
        Measurement name -> ``{'marker_pairs': [...], 'bodies': [...], 'axes': str}``.
    """
    measurements: OrderedDict[str, dict] = OrderedDict()
    current_bodies: list[str] | None = None
    current_axes: str | None = None

    with open(tsv_path, "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            name = row["measurement"]
            marker1 = row["marker1"]
            marker2 = row["marker2"]
            bodies = (row.get("bodies") or "").strip()
            axes = (row.get("axes") or "").strip()

            if bodies:
                current_bodies = [b.strip() for b in bodies.split(",")]
            if axes:
                current_axes = axes

            if name not in measurements:
                measurements[name] = {
                    "marker_pairs": [],
                    "bodies": current_bodies or [],
                    "axes": current_axes or "X Y Z",
                }

            measurements[name]["marker_pairs"].append((marker1, marker2))

    return measurements


def run_scaling(
    static_trc_file: str | Path,
    model_file: str | Path,
    output_model_file: str | Path,
    measurements_tsv: str | Path,
    ik_weights_tsv: str | Path,
    subject_mass: float = 79.0,
    time_range: tuple[float, float] | None = None,
) -> str:
    """Scale an OpenSim model using a static trial.

    Parameters
    ----------
    static_trc_file : str or Path
        Static trial TRC file.
    model_file : str or Path
        Generic (unscaled) .osim model file.
    output_model_file : str or Path
        Path where the scaled model will be saved.
    measurements_tsv : str or Path
        Scaling measurements TSV file.
    ik_weights_tsv : str or Path
        IK marker weights TSV file.
    subject_mass : float
        Subject mass in kg.
    time_range : tuple[float, float], optional
        (start, end) time in seconds. Defaults to the full TRC duration.

    Returns
    -------
    str
        Path to the scaled model file.
    """
    static_trc_file = Path(static_trc_file).resolve()
    output_model_file = Path(output_model_file).resolve()
    model_file = Path(model_file).resolve()

    measurements = parse_scaling_measurements_tsv(measurements_tsv)
    ik_weights = parse_ik_marker_weights_tsv(ik_weights_tsv)

    if time_range is None:
        marker_table = osim.TimeSeriesTableVec3(str(static_trc_file))
        times = marker_table.getIndependentColumn()
        time_range = (times[0], times[-1])

    # ScaleTool
    scale_tool = osim.ScaleTool()
    scale_tool.setName(output_model_file.stem)
    scale_tool.setSubjectMass(subject_mass)

    # GenericModelMaker
    scale_tool.getGenericModelMaker().setModelFileName(str(model_file))

    # ModelScaler
    model_scaler = scale_tool.getModelScaler()
    model_scaler.setApply(True)
    scaling_order = osim.ArrayStr()
    scaling_order.append("measurements")
    model_scaler.setScalingOrder(scaling_order)
    model_scaler.setMarkerFileName(str(static_trc_file))
    time_range_arr = osim.ArrayDouble()
    time_range_arr.append(time_range[0])
    time_range_arr.append(time_range[1])
    model_scaler.setTimeRange(time_range_arr)
    model_scaler.setOutputModelFileName(str(output_model_file))

    measurement_set = model_scaler.getMeasurementSet()
    measurement_set.clearAndDestroy()

    for meas_name, meas_data in measurements.items():
        measurement = osim.Measurement()
        measurement.setName(meas_name)
        measurement.setApply(True)

        marker_pair_set = measurement.getMarkerPairSet()
        for m1, m2 in meas_data["marker_pairs"]:
            marker_pair = osim.MarkerPair()
            marker_pair.setMarkerName(0, m1)
            marker_pair.setMarkerName(1, m2)
            marker_pair_set.cloneAndAppend(marker_pair)

        body_scale_set = measurement.getBodyScaleSet()
        for body in meas_data["bodies"]:
            body_scale = osim.BodyScale()
            body_scale.setName(body)
            axes = osim.ArrayStr()
            for axis in meas_data["axes"].split():
                axes.append(axis)
            body_scale.setAxisNames(axes)
            body_scale_set.cloneAndAppend(body_scale)

        measurement_set.cloneAndAppend(measurement)

    # MarkerPlacer
    marker_placer = scale_tool.getMarkerPlacer()
    marker_placer.setApply(True)
    marker_placer.setMarkerFileName(str(static_trc_file))
    marker_placer.setTimeRange(time_range_arr)
    marker_placer.setOutputModelFileName(str(output_model_file))

    ik_task_set = marker_placer.getIKTaskSet()
    ik_task_set.clearAndDestroy()
    for m in ik_weights:
        task = osim.IKMarkerTask()
        task.setName(m["marker"])
        task.setApply(m["apply"])
        task.setWeight(m["weight"])
        ik_task_set.cloneAndAppend(task)

    scale_tool.run()

    return str(output_model_file)
