# OpenSim PyProcessing

Automated biomechanical analysis pipeline using the OpenSim Python API. Converts C3D motion capture data to OpenSim-compatible format (.trc and .mot) and allows the batch processing of the OpenSim pipeline: model scaling, inverse kinematics, inverse dynamics, and center-of-mass computation (so far).

## Pipeline Overview

```
C3D files
    |  export_c3d_to_trc_and_mot()
    v
TRC (markers) + MOT (ground reaction forces)
    |  run_scaling()
    v
Scaled musculoskeletal model (.osim)
    |  run_ik()
    v
Joint angles (*_ik.mot)
    |                   |
    |  run_id()         |  compute_com()
    v                   v
Joint moments       Center of mass
(*_id.sto)          (*_com.sto)
```

## Prerequisites

- **Python 3.10+**
- **OpenSim 4.5+** with Python bindings ([installation guide](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53085346/Scripting+in+Python#Setting-up-your-Python-scripting-environment))
- Python dependencies:
  ```
  pip install -r requirements.txt
  ```

> **Note:** The `opensim` Python package is not available via pip. Install it through conda or from the OpenSim distribution. See the link above.

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/opensim_pyprocessing.git
   cd opensim_pyprocessing
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run with the included example data:
   ```bash
   python run_pipeline.py --config example/example_config.yaml
   ```

4. For your own data, copy and edit the config:
   ```bash
   cp config.yaml my_config.yaml
   # Edit my_config.yaml with your paths and parameters
   python run_pipeline.py --config my_config.yaml
   ```

## Configuration

The pipeline is driven by a YAML configuration file. All paths are resolved relative to the config file's directory.

```yaml
subject:
  mass: 79.0  # kg

paths:
  c3d_folder: "data"              # Directory with C3D files
  output_folder: "output"         # Pipeline output directory
  generic_model: "model/RajagopalLaiUhlrich2023.osim"
  scaling_measurements_tsv: "config_tables/scaling_measurements.tsv"
  ik_marker_weights_tsv: "config_tables/ik_marker_weights.tsv"
  external_loads_tsv: "config_tables/external_loads.tsv"

steps:
  c3d_export: true
  scaling: true
  inverse_kinematics: true
  inverse_dynamics: true
  center_of_mass: true

trials:
  static_pattern: "*static*"      # Glob pattern for static trial(s)

# 4x4 lab-to-OpenSim coordinate transform (row-major)
coordinate_transform:
  - [ 0,  0, -1, 0]
  - [-1,  0,  0, 0]
  - [ 0,  1,  0, 0]
  - [ 0,  0,  0, 1]

inverse_dynamics:
  low_pass_cutoff_frequency: 6.0  # Hz
```

### Key Configuration Fields

| Field | Description |
|-------|-------------|
| `subject.mass` | Subject body mass in kg, used for model scaling |
| `steps.*` | Toggle each pipeline step on/off |
| `trials.static_pattern` | Glob pattern to find the static calibration trial used for scaling|
| `coordinate_transform` | 4x4 matrix mapping your lab coordinate system to OpenSim (Y-up) |
| `inverse_dynamics.low_pass_cutoff_frequency` | Butterworth filter cutoff for kinematics smoothing in the inverse dynamics step |

### Coordinate Transform

The `coordinate_transform` matrix converts marker and force data from your lab's coordinate system to OpenSim's convention (Y-up). The default matrix assumes a specific lab setup.

## Project Structure

```
opensim_pyprocessing/
├── run_pipeline.py              # Entry point
├── config.yaml                  # Default configuration template
├── requirements.txt
│
├── opensim_pipeline/            # Core package
│   ├── pipeline.py              # Pipeline orchestrator
│   ├── config.py                # YAML config loader
│   ├── c3d_export.py            # C3D → TRC/MOT conversion
│   ├── scaling.py               # Model scaling
│   ├── inverse_kinematics.py    # Inverse kinematics
│   ├── inverse_dynamics.py      # Inverse dynamics
│   ├── center_of_mass.py        # COM computation
│   ├── transforms.py            # Coordinate transformations
│   └── io_utils.py              # File I/O utilities
│
├── model/                       # Musculoskeletal model + geometry
├── config_tables/               # TSV configuration files
│   ├── scaling_measurements.tsv
│   ├── ik_marker_weights.tsv
│   └── external_loads.tsv
│
├── example/                     # Example dataset
│   ├── data/                    # 3 sample C3D files
│   └── example_config.yaml
│
└── 
```

## Command-Line Interface Options

```
python run_pipeline.py --config <path>    # Specify config file (default: config.yaml)
python run_pipeline.py --verbose          # Enable debug-level logging
```

## License

MIT
