"""Access calibration data stored in this package."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import datetime as _dt

from .remote import (  # noqa: F401
    CalibrationBundle,
    extract_raw_mcal_bytes,
    extract_raw_mcal_from_snapshot,
    fetch_latest,
    write_raw_mcal_from_snapshot,
)


def _calib_root() -> Path:
    return resources.files(__package__)  # type: ignore[return-value]


def _latest_filename(room: Optional[str]) -> str:
    if room:
        return f"{room}_latest.json"
    return "calib_latest.json"


def _parse_calib_timestamp(name: str, room: Optional[str]) -> Optional[_dt.datetime]:
    """Parse YYMMDD_HHMM or YYMMDD_HHMMSS timestamp from a calibration filename."""
    prefix = f"{room}_" if room else "calib_"
    if not name.startswith(prefix) or not name.endswith(".json"):
        return None
    token = name[len(prefix):-5]
    if len(token) == len("260428_081800"):
        formats = ("%y%m%d_%H%M%S",)
    elif len(token) == len("260428_0818"):
        formats = ("%y%m%d_%H%M",)
    else:
        formats = ()
    for fmt in formats:
        try:
            return _dt.datetime.strptime(token, fmt)
        except ValueError:
            continue
    return None


def list_calibs(room: Optional[str] = None) -> List[Path]:
    """Return sorted calibration files (newest last)."""
    root = _calib_root()
    if not root.exists():
        return []

    prefix = f"{room}_" if room else "calib_"
    calibs = [
        p for p in root.iterdir()
        if p.is_file() and p.name.startswith(prefix) and p.name.endswith(".json")
        and "latest" not in p.name
    ]
    return sorted(calibs, key=lambda p: p.name)


def list_calib_names(room: Optional[str] = None) -> List[str]:
    """Return sorted calibration filenames (newest last)."""
    return [path.name for path in list_calibs(room)]


def latest_json_path(room: Optional[str] = None) -> Optional[Path]:
    """Return the latest calibration JSON path if it exists."""
    calibs = list_calibs(room)
    if calibs:
        return calibs[-1]

    # Backward compatibility with previous layout.
    root = _calib_root()
    legacy_dir = root / "latest"
    legacy_name = f"{room}_calib.json" if room else "calib.json"
    legacy_path = legacy_dir / legacy_name
    if legacy_path.exists():
        return legacy_path

    legacy_latest = root / _latest_filename(room)
    return legacy_latest if legacy_latest.exists() else None


def load_latest(room: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load the latest calibration JSON if available."""
    path = latest_json_path(room)
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_snapshots(room: Optional[str] = None) -> List[Path]:
    """Backward compatible alias for list_calibs()."""
    return list_calibs(room)


def list_snapshot_names(room: Optional[str] = None) -> List[str]:
    """Backward compatible alias for list_calib_names()."""
    return list_calib_names(room)


def find_calib_at_or_before(
    target: Union[str, _dt.datetime],
    room: Optional[str] = None,
) -> Optional[Path]:
    """Return the calibration file at or before the given date/time.

    The target can be a datetime or a string in YYYY-MM-DD, YYYY-MM-DDTHH:MM,
    YYMMDD_HHMM, or YYMMDD_HHMMSS format. The match uses local time for parsing
    strings.
    """
    if isinstance(target, _dt.datetime):
        target_dt = target
    else:
        text = target.strip()
        formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M"]
        if len(text) == len("260428_081800"):
            formats.append("%y%m%d_%H%M%S")
        elif len(text) == len("260428_0818"):
            formats.append("%y%m%d_%H%M")
        for fmt in formats:
            try:
                target_dt = _dt.datetime.strptime(text, fmt)
                break
            except ValueError:
                target_dt = None
        if target_dt is None:
            raise ValueError(
                "Unsupported date format. Use YYYY-MM-DD, YYYY-MM-DDTHH:MM, YYMMDD_HHMM, "
                "or YYMMDD_HHMMSS."
            )

    candidates: List[Tuple[_dt.datetime, Path]] = []
    for path in list_calibs(room):
        ts = _parse_calib_timestamp(path.name, room)
        if ts is None:
            continue
        if ts <= target_dt:
            candidates.append((ts, path))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]
