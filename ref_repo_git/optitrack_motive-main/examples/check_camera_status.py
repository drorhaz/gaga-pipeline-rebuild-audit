#!/usr/bin/env python3

"""Query live Motive camera status and duplex mode, returning a JSON dictionary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optitrack_motive.motive_stream import fetch_camera_statuses


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch live camera status and video mode from Motive via NatNet remote properties"
    )
    parser.add_argument("--server-ip", default="10.40.49.47", help="Motive server IP address")
    parser.add_argument("--client-ip", default="auto", help="Local client IP (default: auto detect)")
    parser.add_argument("--timeout", type=float, default=8.0, help="Seconds to wait for responses")
    parser.add_argument("--no-multicast", action="store_true", help="Use unicast for camera discovery")
    args = parser.parse_args()

    status = fetch_camera_statuses(
        server_ip=args.server_ip,
        client_ip=args.client_ip,
        timeout=args.timeout,
        use_multicast=not args.no_multicast,
    )
    print(json.dumps(status, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
