# AGENTS.md

## Calibration Workflow

Preferred calibration source is the live Motive `.mcal` file on the Windows
Motive PC. Do not use the Motive API or YAML/default intrinsic fallbacks for
this path.

### Get Current Calibration

Fetch and validate the latest Cork calibration without saving anything:

```bash
python scripts/fetch_calib.py --room cork
```

For Cork, the room template fetches this file over SSH:

```text
Admin@kyushu:C:\ProgramData\OptiTrack\Motive\System Calibration.mcal
```

The command reads the file directly, parses it locally, reports SHA256/size,
and builds strict `camera_geometry_by_serial` entries from
`IntrinsicStandardCameraModel`.

### Save Calibration

Save a complete calibration snapshot as one self-contained JSON file:

```bash
python scripts/fetch_calib.py --room cork --save-snapshot
```

Default output:

```text
optitrack_motive/calib/cork_YYMMDD_HHMMSS.json
```

This is intentionally one file. It contains:

- legacy top-level `cameras` for old callers;
- strict `camera_geometry_by_serial` for selected pose cameras;
- full parsed `.mcal` tree under `mcal`;
- source metadata under `source`, including host, path, SHA256, mtime, and size;
- exact raw `.mcal` bytes embedded under `raw_mcal` as base64.

Do not expect a separate `.mcal` sidecar in the new snapshot format.

### Use Calibration

Existing compatible callers can still use:

```python
from optitrack_motive import calib

snapshot = calib.load_latest(room="cork")
cameras = snapshot["cameras"]
```

New consumers should prefer the strict geometry block:

```python
geometry_by_serial = snapshot["camera_geometry_by_serial"]
```

Every geometry entry is derived from `.mcal` fields only. If required pose,
image size, or intrinsic fields are missing, the fetch path should fail rather
than falling back to defaults.

### Extract Raw `.mcal` From JSON

The raw `.mcal` can be recovered exactly from the saved JSON:

```python
from optitrack_motive.calib import extract_raw_mcal_from_snapshot

raw_mcal = extract_raw_mcal_from_snapshot("optitrack_motive/calib/cork_YYMMDD_HHMMSS.json")
```

To write it back to disk as a `.mcal` file:

```python
from optitrack_motive.calib import write_raw_mcal_from_snapshot

write_raw_mcal_from_snapshot(
    "optitrack_motive/calib/cork_YYMMDD_HHMMSS.json",
    ".agents/extracted_cork.mcal",
)
```

Extraction verifies SHA256 and byte size before returning or writing bytes. If
the embedded data or metadata was tampered with, extraction raises
`RemoteCalibrationError`.

### Remote Acceptance Test Pattern

When testing the network path from Tenerife, keep the local checkout as source
of truth. Copy the current local tree or patch set into a throwaway directory
under Tenerife's repo `.agents/` area, then run:

```bash
python scripts/fetch_calib.py --room cork
python scripts/fetch_calib.py --room cork --save-snapshot --output-dir .agents/calib_fetch_test
```

Verify:

- SHA256 is reported;
- raw `.mcal` camera count is currently 13 for Cork;
- selected pose geometry count is currently 10;
- all geometry entries use `IntrinsicStandardCameraModel`;
- snapshot mode writes one JSON and no sidecar;
- `extract_raw_mcal_from_snapshot(...)` returns bytes whose SHA256 matches
  `source.sha256`.

Copy any Tenerife-generated artifacts back to local `.agents/` before reporting
paths to the user.
