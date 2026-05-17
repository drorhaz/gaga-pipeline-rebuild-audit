# OptiTrack Motive

A modern Python client library for OptiTrack's NatNet streaming protocol, enabling real-time motion capture data retrieval from OptiTrack systems.

## Features

- 🚀 **Real-time streaming** - Receive motion capture data in real-time from OptiTrack systems
- 🎯 **Rigid body tracking** - Easy-to-use rigid body position and orientation tracking
- 📊 **Multiple data formats** - Support for labeled/unlabeled markers, skeletons, and assets
- 🔌 **Multiple protocols** - Built-in OSC and ZeroMQ integration examples
- 🛠️ **Diagnostic tools** - Frame drop detection and tracking diagnostics
- 📈 **Visualization** - Optional pygame-based real-time position visualization

## Installation

```bash
pip install git+https://github.com/Immersive-AI-Systems/optitrack_motive.git
```

### Required SSH Setup for Calibration Fetch

Run this once on every computer that needs to fetch live Motive calibration
from the Windows Motive PC:

```bash
bash scripts/setup_windows_ssh_key.sh Admin kyushu
```

This is required before automatic calibration fetches can work. The `cork`
room calibration source lives on `Admin@kyushu` at
`C:\ProgramData\OptiTrack\Motive\System Calibration.mcal`, and
`python scripts/fetch_calib.py --room cork` reads that file over SSH.

The setup script behaves like a project-specific `ssh-copy-id`: it creates a
fresh OptiTrack Motive SSH key under `~/.ssh`, installs the public key on the
Windows host, and updates a managed `~/.ssh/config` block so normal
`ssh Admin@kyushu` and calibration-fetch commands use that key. Without
`SSH_PASSWORD`, it lets OpenSSH prompt for the Windows password; using
`SSH_PASSWORD=...` for non-interactive setup requires `expect`.

### Dependencies
- Python 3.10+
- numpy
- Optional: pygame (for visualization), python-osc, zmq

## Quick Start

```python
from optitrack_motive.streaming.NatNetClient import NatNetClient

def receive_frame(data_dict):
    print(f"Frame {data_dict['frame_number']}: {len(data_dict['mocap_data'].rigid_body_data.rigid_body_list)} rigid bodies")

# Connect to OptiTrack server
client = NatNetClient()
client.set_server_address("10.40.49.47")  # Your OptiTrack server IP
client.new_frame_listener = receive_frame
client.run()
```

## Examples

### Basic Streaming

#### `hello_streaming_client.py`
Basic example showing how to connect and receive all motion capture data:
```bash
python examples/hello_streaming_client.py
```


### Native NatNet SampleClient
The tracked `examples/SampleClient` binary is refreshed from OptiTrack's official NatNet SDK 4.4.0 Ubuntu package and embeds `RUNPATH=$ORIGIN/../NatNet_SDK_4.4/lib`. On Tenerife, keep the SDK extracted at `~/git/optitrack_motive/NatNet_SDK_4.4` and run:
```bash
cd ~/git/optitrack_motive && ./examples/SampleClient 10.40.49.47
```

Official SDK source used for the refresh: `NatNet_SDK_4.4_ubuntu.tar`; the Windows ZIP has the same SampleClient/Python sources after CRLF normalization, plus extra Windows-only samples.

### Rigid Body Tracking

#### `print_rigid_body.py`
Track a specific rigid body in the terminal, or let the script auto-select the first visible rigid body:
```bash
# Auto-select the first visible rigid body
python examples/print_rigid_body.py -s 10.40.49.47

# Track rigid body "left"
python examples/print_rigid_body.py -n left -s 10.40.49.47 --max-frames 20

# Optional pygame visualization
python examples/print_rigid_body.py -n left -s 10.40.49.47 --pygame
```

#### `print_markers.py`
Print marker-set, labeled-marker, and unlabeled-marker positions:
```bash
# Print one frame of all marker positions
python examples/print_markers.py -s 10.40.49.47

# Print five marker frames
python examples/print_markers.py -s 10.40.49.47 --max-frames 5
```

### Protocol Integration

#### OSC (Open Sound Control)
Receive and send rigid body data via OSC:
```bash
# Receive OSC messages
python examples/osc_receive_rigid_body.py

# Send rigid body data as OSC messages
python scripts/osc_send_rigid_body.py
```

#### ZeroMQ
High-performance message queuing:
```bash
# Receive via ZeroMQ
python examples/zmq_receive_rigid_body.py

# Send via ZeroMQ
python scripts/zmq_send_rigid_body.py
```

## High-Level API

### MotiveReceiver
The main class for receiving motion capture data:

```python
from optitrack_motive.motive_receiver import MotiveReceiver

# Create receiver
motive = MotiveReceiver(server_ip="10.40.49.47")

# Get latest data
latest_frame = motive.get_last()
timestamp = motive.get_last_timestamp()

# Access rigid bodies by model name
rigid_body_data = motive.get_last_by_model("rigid_bodies_full", "MyRigidBody")

# Access marker data from the latest frame
rigid_body_names = motive.get_rigid_body_names()
marker_sets = motive.get_marker_sets()
labeled_markers = motive.get_labeled_markers()
unlabeled_markers = motive.get_unlabeled_markers()
```

### RigidBody
Simplified interface for tracking individual rigid bodies:

```python
from optitrack_motive.rigid_body import RigidBody
from optitrack_motive.motive_receiver import MotiveReceiver

motive = MotiveReceiver(server_ip="10.40.49.47")
rb = RigidBody(motive, "left")  # Track rigid body named "left"

# Get position and orientation
position = rb.get_position()  # [x, y, z]
rotation = rb.get_rotation()  # [qx, qy, qz, qw]
```

## Diagnostic Tools

### Frame Drop Detection
Monitor streaming performance and detect dropped frames:
```bash
python diagnostics/detect_frame_drops.py
```

### Rigid Body Tracker
Advanced rigid body tracking with detailed output:
```bash
python diagnostics/rigid_body_tracker.py
```

## Project Structure

```
optitrack_motive/
├── optitrack_motive/          # Main package
│   ├── streaming/             # Core NatNet streaming implementation
│   ├── motive_receiver.py     # High-level data receiver
│   └── rigid_body.py          # Rigid body tracking utilities
├── examples/                  # Usage examples
├── scripts/                   # Utility scripts for sending data
├── diagnostics/               # Diagnostic and debugging tools
└── logs/                      # Log files directory
```

## Configuration

### Server Connection
Configure your OptiTrack server connection:

```python
# Default localhost connection
client = NatNetClient()

# Custom server
client = NatNetClient()
client.set_server_address("192.168.1.100")
client.set_client_address("192.168.1.50")
client.set_use_multicast(True)
```

### Data Access
Access different types of motion capture data:

```python
def process_frame(data_dict):
    mocap_data = data_dict["mocap_data"]
    
    # Rigid bodies
    rigid_bodies = mocap_data.rigid_body_data.rigid_body_list
    
    # Labeled markers
    labeled_markers = mocap_data.labeled_marker_data.labeled_marker_list
    
    # Unlabeled markers  
    unlabeled_markers = mocap_data.legacy_other_markers
    
    # Skeletons
    skeletons = mocap_data.skeleton_data.skeleton_list
```

## Calibration
Fetch the latest Motive `.mcal` calibration directly from the configured room host:

```bash
python scripts/fetch_calib.py --room cork
```

Save a complete archival snapshot as one self-contained JSON file. The JSON
contains normalized calibration data, the full parsed `.mcal` tree, and the
exact raw `.mcal` bytes embedded as checksum-verified base64:

```bash
python scripts/fetch_calib.py --room cork --save-snapshot
```

The `cork` room preset fetches
`C:\ProgramData\OptiTrack\Motive\System Calibration.mcal` from `Admin@kyushu`
over SSH. The parser preserves the full `.mcal` tree and also writes strict
numeric `camera_geometry_by_serial` entries for the selected pose cameras,
derived from Motive's `IntrinsicStandardCameraModel`; production `.mcal`
calibration does not fall back to YAML/default intrinsics. Auxiliary cameras
remain in the parsed `.mcal` tree even when they are not selected for pose
geometry.

If calibration fetch fails with an SSH authentication error on a new machine,
run the required SSH setup command from the installation section first.

Default saved snapshots use:

`optitrack_motive/calib/<room>_YYMMDD_HHMMSS.json`

For old recordings, keep the historical calibration JSON files and copy the
matching snapshot manually into the recording's `calib/` subfolder. Do not use
the removed legacy save scripts for this.

Load the packaged latest calibration:

```python
from optitrack_motive import calib

latest = calib.load_latest(room="cork")
geometry_by_serial = latest["camera_geometry_by_serial"]
```

Extract the embedded raw `.mcal` from a saved one-file snapshot:

```python
from optitrack_motive.calib import extract_raw_mcal_from_snapshot

raw_mcal = extract_raw_mcal_from_snapshot("optitrack_motive/calib/cork_YYMMDD_HHMMSS.json")
```

The top-level `cameras` list keeps the old compact schema (`name`, `serial`,
`position`, `orientation`) for compatibility. New consumers should prefer
`camera_geometry_by_serial`.

## Recording and Playback

Record streaming data for later analysis:
```python
motive = MotiveReceiver(
    server_ip="10.40.49.47",
    do_record_streaming=True,
    fn_mock="my_recording.pkl"
)
```

Playback recorded data:
```python
motive = MotiveReceiver(
    server_ip="10.40.49.47", 
    do_mock_streaming=True,
    fn_mock="my_recording.pkl"
)
```

## License

Apache License 2.0 - see LICENSE file for details.

## Contributing

Contributions welcome! Please feel free to submit issues and pull requests.
