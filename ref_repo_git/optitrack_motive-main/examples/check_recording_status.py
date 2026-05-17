#!/usr/bin/env python3

"""Query Motive recording status, returning a JSON dictionary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optitrack_motive.motive_stream import fetch_recording_status


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Infer whether Motive is actively recording via NatNet remote commands"
    )
    parser.add_argument("--server-ip", default="10.40.49.47", help="Motive server IP address")
    parser.add_argument("--client-ip", default="auto", help="Local client IP (default: auto detect)")
    parser.add_argument("--timeout", type=float, default=8.0, help="Seconds to wait for responses")
    parser.add_argument(
        "--sample-seconds",
        type=float,
        default=1.0,
        help="How long to wait between take-length samples",
    )
    args = parser.parse_args()

    status = fetch_recording_status(
        server_ip=args.server_ip,
        client_ip=args.client_ip,
        timeout=args.timeout,
        sample_seconds=args.sample_seconds,
    )
    print(json.dumps(status, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
