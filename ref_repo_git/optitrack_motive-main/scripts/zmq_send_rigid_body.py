import lunar_tools as lt
import zmq
import time
import sys
import os
import argparse
import random

# Add the parent directory to the path to import optitrack_motive
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optitrack_motive.motive_receiver import MotiveReceiver
from optitrack_motive.rigid_body import RigidBody

# Helper to scale values
def scale_value(val, in_min, in_max, out_min, out_max):
    scaled = (val - in_min) / (in_max - in_min) * (out_max - out_min) + out_min
    return max(min(scaled, out_max), out_min)

def main():
    parser = argparse.ArgumentParser(description='Send OptiTrack rigid body data via ZMQ')
    parser.add_argument('--ip', help='ZMQ endpoint IP address (default: local IP)')
    parser.add_argument('--port', type=int, required=True, help='ZMQ endpoint port')
    parser.add_argument('--rigid-bodies', nargs='+', default=['A','B','C','D'], help='Rigid body names (default: A B C D)')
    parser.add_argument('--rate', type=float, default=100.0, help='Sampling rate in Hz (default: 100)')
    parser.add_argument('--test-mode', action='store_true', help='Send random values within output range instead of real data')
    parser.add_argument('--server-ip', default='10.40.49.47', help='OptiTrack server IP (default: 10.40.49.47)')
    parser.add_argument('--scale', action='store_true', help='Scale the data to 0-1 range (default: False)')
    args = parser.parse_args()
    test_mode = args.test_mode
    scale_data = args.scale

    # Determine ZMQ endpoint IP, fallback to local
    ip_address = args.ip or lt.get_local_ip()

    rigid_body_names = args.rigid_bodies
    sleep_time = 1.0 / args.rate

    print("Connecting to OptiTrack...")
    motive = MotiveReceiver(server_ip=args.server_ip)
    time.sleep(1)

    print("Testing basic connection...")
    for i in range(50):
        latest = motive.get_last()
        if latest:
            print(f"✓ Connection established! Frame ID: {latest['frame_id']}")
            break
        time.sleep(0.1)
    else:
        print("✗ No data received. Check OptiTrack connection.")
        motive.stop()
        sys.exit(1)

    rigid_bodies = {name: RigidBody(motive, name) for name in rigid_body_names}

    # Setup ZMQ server endpoint
    print(f"Setting up ZMQ server at {ip_address}:{args.port}...")
    server = lt.ZMQPairEndpoint(is_server=True, ip=ip_address, port=args.port)

    # Scaling configuration
    scale_config = {
        'x':    {'in_min': -3.5,   'in_max': 3.5,   'out_min': 0.0, 'out_max': 1.0},
        'y':    {'in_min': 0.0,    'in_max': 2.1,   'out_min': 0.0, 'out_max': 1.0},
        'z':    {'in_min': -3.5,   'in_max': 3.5,   'out_min': 0.0, 'out_max': 1.0},
        'roll': {'in_min': -180.0, 'in_max': 180.0,'out_min': 0.0, 'out_max': 1.0},
        'pitch':{'in_min': -180.0, 'in_max': 180.0,'out_min': 0.0, 'out_max': 1.0},
        'yaw':  {'in_min': -180.0, 'in_max': 180.0,'out_min': 0.0, 'out_max': 1.0},
    }
    signals = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']

    print(f"Starting ZMQ streaming for rigid bodies {', '.join(rigid_body_names)} at {args.rate}Hz...")
    frame_count = 0

    try:
        while True:
            time.sleep(sleep_time)
            frame_count += 1

            if test_mode:
                for name in rigid_body_names:
                    test_vals = {}
                    for signal in signals:
                        cfg = scale_config[signal]
                        test_vals[signal] = random.uniform(cfg['out_min'], cfg['out_max'])
                    try:
                        server.send_json({'frame': frame_count, 'name': name, **test_vals})
                    except zmq.error.Again:
                        pass
                    if frame_count % 100 == 0:
                        print(f"Test mode frame {frame_count} [{name}]: {test_vals}")
                continue

            for name, rigid_body in rigid_bodies.items():
                rigid_body.update()
                position = rigid_body.positions.get_last()
                euler_angles = rigid_body.euler_angles.get_last()

                # Only send if we have valid data (not zeros)
                if not position.any() == 0:
                    data = {}
                    for i, signal in enumerate(signals):
                        cfg = scale_config[signal]
                        raw = position[i] if i < 3 else euler_angles[i - 3]
                        if scale_data:
                            data[signal] = scale_value(raw, **cfg)
                        else:
                            data[signal] = raw
                    try:
                        server.send_json({'frame': frame_count, 'name': name, **data})
                    except zmq.error.Again:
                        pass
                    if frame_count % 100 == 0:
                        print(f"Streaming frame {frame_count} [{name}]: scaled {data}")
    except KeyboardInterrupt:
        print("\nStopping ZMQ streaming...")
        motive.stop()

if __name__ == "__main__":
    main() 