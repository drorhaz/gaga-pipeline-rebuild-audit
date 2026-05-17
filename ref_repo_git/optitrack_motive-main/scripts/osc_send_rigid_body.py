import lunar_tools as lt
import time
import sys
import os
import argparse
import random

# Add the parent directory to the path to import optitrack_motive
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optitrack_motive.motive_receiver import MotiveReceiver
from optitrack_motive.rigid_body import RigidBody

# Add a helper to linearly scale values based on configuration
def scale_value(val, in_min, in_max, out_min, out_max):
    # Linearly scale val from [in_min, in_max] to [out_min, out_max]
    scaled = (val - in_min) / (in_max - in_min) * (out_max - out_min) + out_min
    # Clamp to output range
    return max(min(scaled, out_max), out_min)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Send OptiTrack rigid body data via OSC')
    parser.add_argument('--ip', required=True, help='OSC receiver IP address')
    parser.add_argument('--port', type=int, default=8003, help='OSC receiver port (default: 8003)')
    parser.add_argument('--rigid-body', default='B', help='Rigid body name (default: B)')
    parser.add_argument('--rate', type=float, default=100.0, help='Sampling rate in Hz (default: 100)')
    parser.add_argument('--test-mode', action='store_true', help='Send random values within output range instead of real data')
    args = parser.parse_args()
    test_mode = args.test_mode
    
    # Configuration
    rigid_body_name = args.rigid_body
    sleep_time = 1.0 / args.rate  # Convert Hz to sleep time in seconds
    
    # Setup OptiTrack connection
    print("Connecting to OptiTrack...")
    motive = MotiveReceiver(server_ip="10.40.49.47")
    
    print("Waiting for data connection...")
    time.sleep(1)
    
    # Test basic connection
    print("Testing basic connection...")
    for i in range(50):
        latest_data = motive.get_last()
        if latest_data:
            print(f"✓ Connection established! Frame ID: {latest_data['frame_id']}")
            break
        time.sleep(0.1)
    else:
        print("✗ No data received. Check OptiTrack connection.")
        motive.stop()
        exit(1)
    
    # Create rigid body
    rigid_body = RigidBody(motive, rigid_body_name)
    
    # Setup OSC senders - one for each signal
    print(f"Setting up OSC senders to {args.ip}...")
    signals = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
    # Add scaling configuration: define in/out min and max for each channel
    scale_config = {
        'x':    {'in_min': -3.5,   'in_max': 3.5,   'out_min': 0.0, 'out_max': 1.0},
        'y':    {'in_min': 0.0,   'in_max': 2.1,   'out_min': 0.0, 'out_max': 1.0},
        'z':    {'in_min': -3.5,   'in_max': 3.5,   'out_min': 0.0, 'out_max': 1.0},
        'roll': {'in_min': -180.0,'in_max': 180.0,'out_min': 0.0, 'out_max': 1.0},
        'pitch':{'in_min': -180.0,'in_max': 180.0,'out_min': 0.0, 'out_max': 1.0},
        'yaw':  {'in_min': -180.0,'in_max': 180.0,'out_min': 0.0, 'out_max': 1.0},
    }
    senders = {}
    
    for i, signal in enumerate(signals):
        port = args.port + i
        senders[signal] = lt.OSCSender(args.ip, port)
        print(f"  {rigid_body_name}_{signal} -> {args.ip}:{port}")

    print(f"Starting OSC streaming for rigid body '{rigid_body_name}' at {args.rate}Hz...")
    frame_count = 0
    
    try:
        while True:
            time.sleep(sleep_time)  # Use sleep_time for consistent update rate
            frame_count += 1
            
            if test_mode:
                # Test mode: send random values within output range
                test_vals = {}
                for signal in signals:
                    cfg = scale_config[signal]
                    val = random.uniform(cfg['out_min'], cfg['out_max'])
                    test_vals[signal] = val
                    senders[signal].send_message(f"/{rigid_body_name}_{signal}", val)
                if frame_count % 100 == 0:
                    print(f"Test mode frame {frame_count}: {test_vals}")
                continue

            # Update rigid body data
            rigid_body.update()
            
            # Get position and orientation data
            position = rigid_body.positions.get_last()
            euler_angles = rigid_body.euler_angles.get_last()
            
            # Only send if we have valid data (not zeros)
            if not position.any() == 0:
                # Send position data using separate senders with scaling
                senders['x'].send_message(f"/{rigid_body_name}_x", scale_value(position[0], **scale_config['x']))
                senders['y'].send_message(f"/{rigid_body_name}_y", scale_value(position[1], **scale_config['y']))
                senders['z'].send_message(f"/{rigid_body_name}_z", scale_value(position[2], **scale_config['z']))
                
                # Send orientation data (euler angles) using separate senders with scaling
                senders['roll'].send_message(f"/{rigid_body_name}_roll", scale_value(euler_angles[0], **scale_config['roll']))
                senders['pitch'].send_message(f"/{rigid_body_name}_pitch", scale_value(euler_angles[1], **scale_config['pitch']))
                senders['yaw'].send_message(f"/{rigid_body_name}_yaw", scale_value(euler_angles[2], **scale_config['yaw']))
                
                # Print status occasionally
                if frame_count % 100 == 0:
                    # Compute scaled values for logging
                    scaled_position = [
                        scale_value(position[0], **scale_config['x']),
                        scale_value(position[1], **scale_config['y']),
                        scale_value(position[2], **scale_config['z']),
                    ]
                    scaled_euler = [
                        scale_value(euler_angles[0], **scale_config['roll']),
                        scale_value(euler_angles[1], **scale_config['pitch']),
                        scale_value(euler_angles[2], **scale_config['yaw']),
                    ]
                    print(f"Streaming frame {frame_count}: raw_pos={position}, raw_euler={euler_angles}, scaled_pos={scaled_position}, scaled_euler={scaled_euler}")
                    
    except KeyboardInterrupt:
        print("\nStopping OSC streaming...")
        motive.stop()

if __name__ == "__main__":
    main() 