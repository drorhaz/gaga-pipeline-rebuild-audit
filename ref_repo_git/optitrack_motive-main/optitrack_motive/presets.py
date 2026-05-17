from __future__ import annotations

import atexit
import json
from contextlib import ExitStack
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Dict, List, Optional

CONNECTION_FIELDS = {
    "server_ip",
    "client_ip",
    "use_multicast",
}


@dataclass(frozen=True)
class RoomPreset:
    name: str
    connection: Dict[str, object]
    calibration: Dict[str, object]
    camera_stream: Dict[str, object]
    pose_defaults: Dict[str, object]
    cameras: List[Dict[str, object]]


_RESOURCE_STACK = ExitStack()
atexit.register(_RESOURCE_STACK.close)
_PACKAGED_PRESETS_ROOT: Optional[Path] = None


def _get_packaged_presets_root() -> Optional[Path]:
    """Locate the bundled presets directory within the optitrack_motive package."""
    global _PACKAGED_PRESETS_ROOT

    if _PACKAGED_PRESETS_ROOT is not None:
        return _PACKAGED_PRESETS_ROOT

    presets_resource = resources.files(__package__) / "preset_assets"
    if not presets_resource.is_dir():
        return None

    try:
        _PACKAGED_PRESETS_ROOT = Path(
            _RESOURCE_STACK.enter_context(resources.as_file(presets_resource))
        )
    except FileNotFoundError:
        return None

    return _PACKAGED_PRESETS_ROOT


def get_presets_root() -> Path:
    """Return the root directory containing packaged presets."""
    packaged_root = _get_packaged_presets_root()
    if packaged_root is not None:
        return packaged_root

    raise FileNotFoundError(
        "No presets directory found; packaged preset_assets is missing from the installation."
    )


def list_rooms(presets_root: Optional[Path] = None) -> List[str]:
    """List available room preset directories."""
    root = presets_root or get_presets_root()
    if not root.exists():
        return []
    return sorted(
        entry.name
        for entry in root.iterdir()
        if entry.is_dir() and (entry / "room.json").exists()
    )


def load_room(
    room_name: str,
    connection_overrides: Optional[Dict[str, object]] = None,
    presets_root: Optional[Path] = None,
) -> RoomPreset:
    """Load a room preset definition and apply optional overrides."""
    root = presets_root or get_presets_root()
    room_dir = root / room_name
    room_file = room_dir / "room.json"
    if not room_file.exists():
        raise FileNotFoundError(f"Room preset '{room_name}' not found at {room_file}")

    with room_file.open("r", encoding="utf-8") as fh:
        raw_room = json.load(fh)

    room_label = raw_room.get("room", room_name)
    defaults = raw_room.get("default", {})
    connection = raw_room.get("connection", {})
    calibration = raw_room.get("calibration", {})
    camera_stream = raw_room.get("camera_stream", {})
    pose_defaults = raw_room.get("pose_defaults", {})
    cameras = raw_room.get("cameras", [])
    if not isinstance(defaults, dict):
        defaults = {}
    if not isinstance(connection, dict):
        connection = {}
    if not isinstance(calibration, dict):
        calibration = {}
    if not isinstance(camera_stream, dict):
        camera_stream = {}
    if not isinstance(pose_defaults, dict):
        pose_defaults = {}
    if not isinstance(cameras, list):
        cameras = []

    merged_connection = {k: v for k, v in defaults.items() if k in CONNECTION_FIELDS}
    merged_connection.update({k: v for k, v in connection.items() if k in CONNECTION_FIELDS})
    if connection_overrides:
        merged_connection.update(connection_overrides)

    merged_connection.setdefault("server_ip", "localhost")
    merged_connection.setdefault("client_ip", "auto")
    merged_connection.setdefault("use_multicast", True)

    return RoomPreset(
        name=room_label,
        connection=merged_connection,
        calibration=dict(calibration),
        camera_stream=dict(camera_stream),
        pose_defaults=dict(pose_defaults),
        cameras=[dict(camera) for camera in cameras if isinstance(camera, dict)],
    )
