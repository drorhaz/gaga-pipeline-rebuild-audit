#!/usr/bin/env python3

"""Fetch the latest Motive .mcal calibration from a configured room source."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optitrack_motive.calib.remote import RemoteCalibrationError, fetch_latest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and parse the latest Motive .mcal calibration for a room."
    )
    parser.add_argument("--room", default="cork", help="Room preset name (default: cork)")
    parser.add_argument(
        "--save-snapshot",
        action="store_true",
        help="Write one normalized JSON snapshot with embedded raw .mcal bytes.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional root for saved snapshot artifacts. Defaults to the repo layout.",
    )
    parser.add_argument("--retries", type=int, default=3, help="Fetch/parse retry count")
    parser.add_argument("--timeout", type=float, default=30.0, help="SSH command timeout in seconds")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a compact machine-readable summary instead of human text.",
    )
    args = parser.parse_args()

    try:
        bundle = fetch_latest(
            room=args.room,
            save=args.save_snapshot,
            output_dir=args.output_dir,
            retries=args.retries,
            timeout=args.timeout,
        )
    except RemoteCalibrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    payload = bundle.payload
    source = payload.get("source", {})
    summary = {
        "room": payload.get("room"),
        "source_host": source.get("host"),
        "source_path": source.get("path"),
        "source_sha256": source.get("sha256"),
        "source_size_bytes": source.get("size_bytes"),
        "source_mtime_utc": source.get("mtime_utc"),
        "motive_running": source.get("motive_running"),
        "camera_count": len(payload.get("cameras", [])),
        "geometry_count": len(payload.get("camera_geometry_by_serial", {})),
        "raw_mcal_embedded": "raw_mcal" in payload,
        "snapshot_path": str(bundle.snapshot_path) if bundle.snapshot_path else None,
    }

    if args.json:
        print(json.dumps(summary, sort_keys=True))
        return 0

    print("Remote Calib Fetch")
    print("=" * 40)
    print(f"Room        : {summary['room']}")
    print(f"Source host : {summary['source_host']}")
    print(f"Source path : {summary['source_path']}")
    print(f"SHA256      : {summary['source_sha256']}")
    print(f"Size bytes  : {summary['source_size_bytes']}")
    print(f"MTime UTC   : {summary['source_mtime_utc']}")
    print(f"Motive run  : {summary['motive_running']}")
    print(f"Cameras     : {summary['camera_count']}")
    print(f"Geometries  : {summary['geometry_count']}")
    print(f"Raw .mcal   : {'embedded in JSON' if summary['raw_mcal_embedded'] else 'not saved'}")
    if bundle.snapshot_path:
        print(f"Snapshot    : {bundle.snapshot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
