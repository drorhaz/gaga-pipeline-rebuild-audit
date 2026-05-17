"""Fetch and save Motive calibration files from a remote Windows host."""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union
import xml.etree.ElementTree as ET

from optitrack_motive.mcal import (
    McalValidationError,
    normalize_camera_geometries,
    parse_mcal_bytes,
)
from optitrack_motive.presets import load_room


DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3


class RemoteCalibrationError(RuntimeError):
    """Raised when remote calibration fetch fails."""


@dataclass(frozen=True)
class CalibrationBundle:
    payload: Dict[str, Any]
    raw_mcal: bytes
    snapshot_path: Optional[Path] = None
    raw_sidecar_path: Optional[Path] = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _snapshot_stamp(now: Optional[datetime] = None) -> str:
    current = now if now is not None else datetime.now().astimezone()
    if current.tzinfo is not None:
        current = current.astimezone()
    return current.strftime("%y%m%d_%H%M%S")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _embedded_raw_mcal(raw_mcal: bytes) -> Dict[str, Any]:
    return {
        "encoding": "base64",
        "sha256": _sha256(raw_mcal),
        "size_bytes": len(raw_mcal),
        "data": base64.b64encode(raw_mcal).decode("ascii"),
    }


def extract_raw_mcal_bytes(payload: Dict[str, Any]) -> bytes:
    """Extract and verify exact raw .mcal bytes embedded in a snapshot payload."""

    raw_block = payload.get("raw_mcal")
    if not isinstance(raw_block, dict):
        raise RemoteCalibrationError("Snapshot does not contain embedded raw_mcal data")
    if raw_block.get("encoding") != "base64":
        raise RemoteCalibrationError(f"Unsupported raw_mcal encoding: {raw_block.get('encoding')!r}")

    encoded = raw_block.get("data")
    if not isinstance(encoded, str) or not encoded:
        raise RemoteCalibrationError("Embedded raw_mcal block is missing base64 data")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise RemoteCalibrationError("Embedded raw_mcal data is not valid base64") from exc

    expected_size = raw_block.get("size_bytes")
    if expected_size is not None and int(expected_size) != len(raw):
        raise RemoteCalibrationError(
            f"Embedded raw_mcal size mismatch: expected={expected_size} actual={len(raw)}"
        )

    expected_sha = str(raw_block.get("sha256", "")).lower()
    actual_sha = _sha256(raw)
    if expected_sha and expected_sha != actual_sha:
        raise RemoteCalibrationError(
            f"Embedded raw_mcal SHA256 mismatch: expected={expected_sha} actual={actual_sha}"
        )

    source = payload.get("source")
    if isinstance(source, dict):
        source_sha = str(source.get("sha256") or source.get("raw_mcal_sha256") or "").lower()
        if source_sha and source_sha != actual_sha:
            raise RemoteCalibrationError(
                f"Embedded raw_mcal does not match source SHA256: source={source_sha} actual={actual_sha}"
            )
        source_size = source.get("size_bytes") or source.get("raw_mcal_size_bytes")
        if source_size is not None and int(source_size) != len(raw):
            raise RemoteCalibrationError(
                f"Embedded raw_mcal does not match source size: source={source_size} actual={len(raw)}"
            )

    return raw


def extract_raw_mcal_from_snapshot(snapshot_path: Union[str, Path]) -> bytes:
    """Load a snapshot JSON and return verified raw .mcal bytes."""

    payload = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    return extract_raw_mcal_bytes(payload)


def write_raw_mcal_from_snapshot(
    snapshot_path: Union[str, Path],
    output_path: Union[str, Path],
) -> Path:
    """Write verified raw .mcal bytes from a snapshot JSON to output_path."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(extract_raw_mcal_from_snapshot(snapshot_path))
    return output


def _hash_bytes_powershell_script(path: str) -> str:
    path_literal = "'" + path.replace("'", "''") + "'"
    return f"""
$ErrorActionPreference = 'Stop'
$path = {path_literal}
$item = Get-Item -LiteralPath $path
$bytes = [System.IO.File]::ReadAllBytes($path)
$sha = [System.Security.Cryptography.SHA256]::Create()
try {{
  $hashBytes = $sha.ComputeHash($bytes)
}} finally {{
  $sha.Dispose()
}}
$hash = -join ($hashBytes | ForEach-Object {{ $_.ToString('x2') }})
$motiveRunning = @((Get-Process -Name 'Motive' -ErrorAction SilentlyContinue)).Count -gt 0
[PSCustomObject]@{{
  path = $path
  sha256 = $hash
  size_bytes = $bytes.Length
  mtime_utc = $item.LastWriteTimeUtc.ToString('o')
  motive_running = $motiveRunning
  content_base64 = [Convert]::ToBase64String($bytes)
}} | ConvertTo-Json -Compress
""".strip()


def _extract_json_object(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RemoteCalibrationError(f"SSH command did not return JSON: {text[:500]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RemoteCalibrationError(f"SSH command returned invalid JSON: {text[:500]!r}") from exc


def fetch_remote_mcal_bytes(
    host: str,
    mcal_path: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Fetch raw .mcal bytes and metadata from a Windows host over SSH."""

    script = _hash_bytes_powershell_script(mcal_path)
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    command = f"powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand {encoded}"
    result = subprocess.run(
        ["ssh", host, command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or f"exit code {result.returncode}"
        raise RemoteCalibrationError(f"SSH fetch failed for {host}: {detail}")

    metadata = _extract_json_object(result.stdout)
    raw_b64 = metadata.pop("content_base64", None)
    if not isinstance(raw_b64, str) or not raw_b64:
        raise RemoteCalibrationError("SSH fetch response did not include content_base64")
    raw = base64.b64decode(raw_b64)

    local_sha = _sha256(raw)
    remote_sha = str(metadata.get("sha256", "")).lower()
    if remote_sha and remote_sha != local_sha:
        raise RemoteCalibrationError(
            f"SHA256 mismatch for remote .mcal: remote={remote_sha} local={local_sha}"
        )
    if int(metadata.get("size_bytes", len(raw))) != len(raw):
        raise RemoteCalibrationError(
            f"Size mismatch for remote .mcal: remote={metadata.get('size_bytes')} local={len(raw)}"
        )

    metadata["sha256"] = local_sha
    metadata["size_bytes"] = len(raw)
    metadata["host"] = host
    metadata["transport"] = "ssh"
    metadata["fetched_at_utc"] = _utc_now()
    metadata["raw_mcal"] = raw
    return metadata


def _file_metadata(path: Path) -> Dict[str, Any]:
    raw = path.read_bytes()
    stat = path.stat()
    return {
        "path": str(path),
        "sha256": _sha256(raw),
        "size_bytes": len(raw),
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": None,
        "transport": "file",
        "motive_running": None,
        "fetched_at_utc": _utc_now(),
        "raw_mcal": raw,
    }


def _legacy_name_by_serial(calib_root: Path, room_prefix: str) -> Dict[int, str]:
    names: Dict[int, str] = {}
    if not calib_root.exists():
        return names

    for path in sorted(calib_root.glob(f"{room_prefix}*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for camera in payload.get("cameras", []):
            if not isinstance(camera, dict):
                continue
            serial = camera.get("serial")
            name = camera.get("name")
            if isinstance(serial, int) and isinstance(name, str) and name:
                names.setdefault(serial, name)
    return names


def _legacy_cameras(parsed_cameras: List[Dict[str, Any]], previous_names: Dict[int, str]) -> List[Dict[str, Any]]:
    cameras: List[Dict[str, Any]] = []
    for camera in parsed_cameras:
        serial = camera.get("serial")
        name = previous_names.get(serial) if isinstance(serial, int) else None
        if not name:
            name = str(camera.get("name") or camera.get("serial_label") or "Camera")
        cameras.append(
            {
                "name": name,
                "serial": serial,
                "position": list(camera.get("position", [])),
                "orientation": list(camera.get("orientation", [])),
            }
        )
    return cameras


def _selected_camera_serials(cameras: List[Dict[str, Any]]) -> Optional[List[int]]:
    selected: List[int] = []
    for camera in cameras:
        role = str(camera.get("role", "")).lower()
        if role == "ignored":
            continue
        serial = camera.get("serial")
        if serial is None:
            continue
        selected.append(int(serial))
    return selected or None


def build_payload_from_mcal(
    raw_mcal: bytes,
    *,
    room: str,
    source: Dict[str, Any],
    previous_names: Optional[Dict[int, str]] = None,
    server_ip: Optional[str] = None,
    client_ip: Optional[str] = None,
    selected_serials: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    """Build a normalized, lossless calibration payload from raw .mcal bytes."""

    parsed = parse_mcal_bytes(raw_mcal, source.get("path") or "<remote mcal>")
    selected = [int(serial) for serial in selected_serials] if selected_serials is not None else None
    geometries = normalize_camera_geometries(parsed, selected_serials=selected)
    clean_source = {key: value for key, value in source.items() if key != "raw_mcal"}
    clean_source.setdefault("kind", "mcal")
    clean_source.setdefault("sha256", _sha256(raw_mcal))
    clean_source.setdefault("size_bytes", len(raw_mcal))

    return {
        "format_version": 2,
        "generated_at_utc": _utc_now(),
        "server_ip": server_ip,
        "client_ip": client_ip,
        "room": room,
        "cameras": _legacy_cameras(parsed["cameras"], previous_names or {}),
        "source_kind": "mcal",
        "source_path": clean_source.get("path"),
        "source": clean_source,
        "selected_camera_serials": selected,
        "camera_geometry_by_serial": geometries,
        "mcal": {
            "camera_count": parsed["camera_count"],
            "motive_build_info": parsed["motive_build_info"],
            "calibration_attributes": parsed["calibration_attributes"],
            "property_warehouse": parsed["property_warehouse"],
            "mask_data": parsed["mask_data"],
            "cameras": parsed["cameras"],
            "raw_mcal": parsed["raw_mcal"],
        },
    }


def save_snapshot(
    bundle: CalibrationBundle,
    *,
    room: str,
    output_dir: Optional[Path] = None,
) -> CalibrationBundle:
    """Write one self-contained JSON snapshot with exact raw .mcal bytes embedded."""

    base_dir = Path(output_dir).resolve() if output_dir is not None else _repo_root()
    if output_dir is None:
        json_root = base_dir / "optitrack_motive" / "calib"
    else:
        json_root = base_dir / "calib"

    json_root.mkdir(parents=True, exist_ok=True)

    stamp = _snapshot_stamp()
    sha = bundle.payload["source"]["sha256"]
    json_path = json_root / f"{room}_{stamp}.json"

    payload = json.loads(json.dumps(bundle.payload, sort_keys=True))
    payload["raw_mcal"] = _embedded_raw_mcal(bundle.raw_mcal)
    payload["source"]["raw_mcal_storage"] = "embedded_base64"
    payload["source"]["raw_mcal_sha256"] = sha
    payload["source"]["raw_mcal_size_bytes"] = len(bundle.raw_mcal)
    extract_raw_mcal_bytes(payload)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return CalibrationBundle(
        payload=payload,
        raw_mcal=bundle.raw_mcal,
        snapshot_path=json_path,
        raw_sidecar_path=None,
    )


def fetch_latest(
    *,
    room: str = "cork",
    save: bool = False,
    output_dir: Optional[Path] = None,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
) -> CalibrationBundle:
    """Fetch and parse the latest .mcal calibration for a room."""

    room_preset = load_room(room)
    calibration = room_preset.calibration
    transport = str(calibration.get("transport", "ssh"))
    mcal_path = str(calibration.get("mcal_path", ""))
    if not mcal_path:
        raise RemoteCalibrationError(f"Room '{room}' does not define calibration.mcal_path")

    last_error: Optional[BaseException] = None
    attempts = max(int(retries), 1)
    for attempt in range(1, attempts + 1):
        try:
            if transport == "ssh":
                host = str(calibration.get("host", ""))
                if not host:
                    raise RemoteCalibrationError(f"Room '{room}' does not define calibration.host")
                source = fetch_remote_mcal_bytes(host, mcal_path, timeout=timeout)
            elif transport == "file":
                source = _file_metadata(Path(mcal_path))
            else:
                raise RemoteCalibrationError(f"Unsupported calibration transport: {transport!r}")

            raw_mcal = source["raw_mcal"]
            calib_root = _repo_root() / "optitrack_motive" / "calib"
            previous_names = _legacy_name_by_serial(calib_root, f"{room}_")
            payload = build_payload_from_mcal(
                raw_mcal,
                room=room,
                source=source,
                previous_names=previous_names,
                server_ip=str(room_preset.connection.get("server_ip", "")) or None,
                client_ip=str(room_preset.connection.get("client_ip", "")) or None,
                selected_serials=_selected_camera_serials(room_preset.cameras),
            )
            bundle = CalibrationBundle(payload=payload, raw_mcal=raw_mcal)
            return save_snapshot(bundle, room=room, output_dir=output_dir) if save else bundle
        except (ET.ParseError, UnicodeDecodeError, McalValidationError, RemoteCalibrationError, OSError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.5 * attempt)
                continue
            break

    raise RemoteCalibrationError(f"Failed to fetch valid calibration for room '{room}': {last_error}") from last_error
