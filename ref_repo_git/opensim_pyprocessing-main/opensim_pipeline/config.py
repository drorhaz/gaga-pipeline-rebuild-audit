"""Pipeline configuration: YAML loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

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


@dataclass
class PipelineConfig:
    """Typed representation of the pipeline YAML configuration."""

    # Subject
    subject_mass: float

    # Resolved paths
    c3d_folder: Path
    output_folder: Path
    generic_model: Path
    scaling_measurements_tsv: Path
    ik_marker_weights_tsv: Path
    external_loads_tsv: Path

    # Steps to run
    steps: dict[str, bool] = field(default_factory=lambda: {
        "c3d_export": True,
        "scaling": True,
        "inverse_kinematics": True,
        "inverse_dynamics": True,
        "center_of_mass": True,
    })

    # Trial identification
    static_pattern: str = "*static*"

    # Coordinate transform
    coordinate_transform: np.ndarray = field(
        default_factory=lambda: DEFAULT_TRANSFORM.copy()
    )

    # C3D export settings
    fill_gaps_max_missing_samples: int = 0

    # Inverse dynamics settings
    id_low_pass_cutoff: float = 6.0


def load_config(config_path: str | Path) -> PipelineConfig:
    """Load and validate a pipeline YAML configuration file.

    All relative paths in the config are resolved against the directory
    containing the config file.

    Parameters
    ----------
    config_path : str or Path
        Path to the YAML configuration file.

    Returns
    -------
    PipelineConfig
        Validated configuration object with resolved paths.
    """
    config_path = Path(config_path).resolve()
    base_dir = config_path.parent

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    def resolve(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else (base_dir / p).resolve()

    paths = raw.get("paths", {})
    steps = raw.get("steps", {})
    trials = raw.get("trials", {})
    c3d_settings = raw.get("c3d_export", {})
    id_settings = raw.get("inverse_dynamics", {})

    # Coordinate transform
    transform_raw = raw.get("coordinate_transform")
    if transform_raw is not None:
        transform = np.array(transform_raw, dtype=float)
    else:
        transform = DEFAULT_TRANSFORM.copy()

    return PipelineConfig(
        subject_mass=raw.get("subject", {}).get("mass", 79.0),
        c3d_folder=resolve(paths.get("c3d_folder", "data")),
        output_folder=resolve(paths.get("output_folder", "output")),
        generic_model=resolve(paths.get("generic_model", "model/RajagopalLaiUhlrich2023.osim")),
        scaling_measurements_tsv=resolve(paths.get("scaling_measurements_tsv", "config_tables/scaling_measurements.tsv")),
        ik_marker_weights_tsv=resolve(paths.get("ik_marker_weights_tsv", "config_tables/ik_marker_weights.tsv")),
        external_loads_tsv=resolve(paths.get("external_loads_tsv", "config_tables/external_loads.tsv")),
        steps={
            "c3d_export": steps.get("c3d_export", True),
            "scaling": steps.get("scaling", True),
            "inverse_kinematics": steps.get("inverse_kinematics", True),
            "inverse_dynamics": steps.get("inverse_dynamics", True),
            "center_of_mass": steps.get("center_of_mass", True),
        },
        static_pattern=trials.get("static_pattern", "*static*"),
        coordinate_transform=transform,
        fill_gaps_max_missing_samples=c3d_settings.get("fill_gaps_max_missing_samples", 0),
        id_low_pass_cutoff=id_settings.get("low_pass_cutoff_frequency", 6.0),
    )
