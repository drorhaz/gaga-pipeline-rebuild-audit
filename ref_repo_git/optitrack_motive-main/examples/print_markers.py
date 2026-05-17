#!/usr/bin/env python3
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optitrack_motive.motive_receiver import MotiveReceiver


def format_vec(values):
    if values is None:
        return "None"
    return "(" + ", ".join(f"{float(value):.4f}" for value in values[:3]) + ")"


def print_marker_frame(motive, frame):
    print(f"\nFrame {frame['frame_id']} timestamp={frame['timestamp']:.6f}")

    marker_sets = motive.get_marker_sets(frame)
    print(f"Marker sets ({len(marker_sets)}):")
    if marker_sets:
        for name, positions in marker_sets.items():
            print(f"  {name} ({len(positions)} markers)")
            for idx, position in enumerate(positions):
                print(f"    {name}[{idx:02d}] pos={format_vec(position)}")
    else:
        print("  (none)")

    labeled_markers = motive.get_labeled_markers(frame)
    print(f"Labeled markers ({len(labeled_markers)}):")
    if labeled_markers:
        for marker in labeled_markers:
            model_name = marker['model_name'] or "unknown"
            print(
                f"  #{marker['index']:02d} id={marker['id_num']} "
                f"model={marker['model_id']}({model_name}) marker={marker['marker_id']} "
                f"pos={format_vec(marker['position'])} size={marker['size']:.4f} "
                f"residual={marker['residual']:.4f} "
                f"flags=occluded:{int(marker['occluded'])},"
                f"point_cloud:{int(marker['point_cloud_solved'])},"
                f"model:{int(marker['model_solved'])}"
            )
    else:
        print("  (none)")

    unlabeled_markers = motive.get_unlabeled_markers(frame)
    print(f"Unlabeled markers ({len(unlabeled_markers)}):")
    if unlabeled_markers:
        for idx, position in enumerate(unlabeled_markers):
            print(f"  #{idx:02d} pos={format_vec(position)}")
    else:
        print("  (none)")


def main():
    parser = argparse.ArgumentParser(
        description="Print marker-set, labeled-marker, and unlabeled-marker positions from Motive."
    )
    parser.add_argument(
        "-s", "--server", default="10.40.49.47",
        help="IP address of the NatNet server"
    )
    parser.add_argument(
        "--timeout", type=float, default=5.0,
        help="Seconds to wait for the first frame before failing"
    )
    parser.add_argument(
        "--interval", type=float, default=1.0,
        help="Seconds between printed frames when --max-frames is greater than 1"
    )
    parser.add_argument(
        "--max-frames", type=int, default=1,
        help="Number of frames to print. Use 0 to run until Ctrl+C."
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose NatNet SDK packet logging"
    )
    args = parser.parse_args()

    print(f"Connecting to OptiTrack server at {args.server}...")
    motive = MotiveReceiver(server_ip=args.server, verbose=args.verbose)
    printed = 0
    last_frame_id = None

    try:
        first_frame = motive.wait_for_frame(timeout=args.timeout)
        if first_frame is None:
            print("ERROR: No data received. Check Motive streaming and network connectivity.")
            return 1

        print("Connection established. Press Ctrl+C to exit.")
        while True:
            frame = motive.get_last()
            if frame is None or frame.get("frame_id") == last_frame_id:
                time.sleep(0.01)
                continue

            print_marker_frame(motive, frame)
            last_frame_id = frame.get("frame_id")
            printed += 1
            if args.max_frames and printed >= args.max_frames:
                break
            time.sleep(args.interval)

        return 0
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0
    finally:
        motive.stop()


if __name__ == "__main__":
    raise SystemExit(main())
