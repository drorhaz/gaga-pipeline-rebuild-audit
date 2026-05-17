"""OpenSim inverse dynamics."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import opensim as osim

logger = logging.getLogger(__name__)


def parse_external_loads_tsv(tsv_path: str | Path) -> list[dict[str, str]]:
    """Parse external loads configuration from a TSV file.

    Parameters
    ----------
    tsv_path : str or Path
        TSV file with columns: name, body, force_identifier,
        point_identifier, torque_identifier.

    Returns
    -------
    list[dict[str, str]]
        Each dict describes one external force.
    """
    loads = []
    with open(tsv_path, "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            loads.append(
                {
                    "name": row["name"],
                    "body": row["body"],
                    "force_identifier": row["force_identifier"],
                    "point_identifier": row["point_identifier"],
                    "torque_identifier": row["torque_identifier"],
                }
            )
    return loads


def run_id(
    ik_mot_file: str | Path,
    model_file: str | Path,
    grf_mot_file: str | Path,
    external_loads_tsv: str | Path,
    output_dir: str | Path | None = None,
    time_range: tuple[float, float] | None = None,
    low_pass_cutoff: float = 6.0,
) -> str:
    """Run inverse dynamics.

    Parameters
    ----------
    ik_mot_file : str or Path
        IK results .mot file (joint angles).
    model_file : str or Path
        Scaled .osim model file.
    grf_mot_file : str or Path
        Ground reaction forces .mot file.
    external_loads_tsv : str or Path
        TSV file defining external loads mapping.
    output_dir : str or Path, optional
        Output directory. Defaults to the IK file's directory.
    time_range : tuple[float, float], optional
        (start, end) time in seconds. Defaults to the full motion duration.
    low_pass_cutoff : float
        Low-pass filter cutoff frequency in Hz for kinematics.

    Returns
    -------
    str
        Path to the output .sto file with joint moments.
    """
    ik_mot_file = Path(ik_mot_file).resolve()
    model_file = Path(model_file).resolve()
    grf_mot_file = Path(grf_mot_file).resolve()

    if output_dir is None:
        output_dir = ik_mot_file.parent
    else:
        output_dir = Path(output_dir).resolve()

    external_loads_config = parse_external_loads_tsv(external_loads_tsv)

    if time_range is None:
        storage = osim.Storage(str(ik_mot_file))
        time_range = (storage.getFirstTime(), storage.getLastTime())

    output_file = output_dir / (
        ik_mot_file.stem.replace("_ik", "") + "_id.sto"
    )

    # External loads
    external_loads = osim.ExternalLoads()
    external_loads.setDataFileName(str(grf_mot_file))

    for load_config in external_loads_config:
        ext_force = osim.ExternalForce()
        ext_force.setName(load_config["name"])
        ext_force.setAppliedToBodyName(load_config["body"])
        ext_force.setForceExpressedInBodyName("ground")
        ext_force.setPointExpressedInBodyName("ground")
        ext_force.setForceIdentifier(load_config["force_identifier"])
        ext_force.setPointIdentifier(load_config["point_identifier"])
        ext_force.setTorqueIdentifier(load_config["torque_identifier"])
        external_loads.cloneAndAppend(ext_force)

    external_loads_file = output_dir / (
        ik_mot_file.stem.replace("_ik", "") + "_external_loads.xml"
    )
    external_loads.printToXML(str(external_loads_file))

    # Inverse dynamics tool
    id_tool = osim.InverseDynamicsTool()
    id_tool.setModelFileName(str(model_file))
    id_tool.setCoordinatesFileName(str(ik_mot_file))
    id_tool.setStartTime(time_range[0])
    id_tool.setEndTime(time_range[1])
    id_tool.setResultsDir(str(output_dir))
    id_tool.setOutputGenForceFileName(output_file.name)
    id_tool.setLowpassCutoffFrequency(low_pass_cutoff)
    id_tool.setExternalLoadsFileName(str(external_loads_file))

    # CRITICAL: exclude muscle forces to get correct joint moments
    id_tool.setExcludedForces(osim.ArrayStr("Muscles", 1))

    logger.debug(
        "ID tool setup saved to %s",
        output_dir / "id_tool_setup_debug.xml",
    )
    id_tool.printToXML(str(output_dir / "id_tool_setup_debug.xml"))

    id_tool.run()

    return str(output_file)
