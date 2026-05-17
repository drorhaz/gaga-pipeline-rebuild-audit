import lunar_tools as lt
import time
import numpy as np
import argparse

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Receive OSC rigid body data')
    parser.add_argument('--ip', default='127.0.0.1', help='IP address to listen on (default: 127.0.0.1)')
    args = parser.parse_args()
    
    # Configuration
    rigid_body_name = "B"
    
    # Setup OSC receiver
    print("Setting up OSC receiver...")
    receiver = lt.OSCReceiver(args.ip)
    
    print(f"Listening for rigid body '{rigid_body_name}' OSC data...")
    print(f"Expected messages: /{rigid_body_name}_x, /{rigid_body_name}_y, /{rigid_body_name}_z, /{rigid_body_name}_roll, /{rigid_body_name}_pitch, /{rigid_body_name}_yaw")
    print("Press Ctrl+C to stop\n")
    
    frame_count = 0
    
    try:
        while True:
            time.sleep(0.1)  # 10Hz display rate
            frame_count += 1
            
            # Get all OSC values for rigid body
            x_values = receiver.get_all_values(f"/{rigid_body_name}_x")
            y_values = receiver.get_all_values(f"/{rigid_body_name}_y") 
            z_values = receiver.get_all_values(f"/{rigid_body_name}_z")
            roll_values = receiver.get_all_values(f"/{rigid_body_name}_roll")
            pitch_values = receiver.get_all_values(f"/{rigid_body_name}_pitch")
            yaw_values = receiver.get_all_values(f"/{rigid_body_name}_yaw")
            
            # Check if we have any data
            if x_values and y_values and z_values and roll_values and pitch_values and yaw_values:
                # Get latest values
                x = x_values[-1]
                y = y_values[-1]
                z = z_values[-1]
                roll = roll_values[-1]
                pitch = pitch_values[-1]
                yaw = yaw_values[-1]
                
                # Display the data
                position = np.array([x, y, z])
                orientation = np.array([roll, pitch, yaw])
                
                print(f"Frame {frame_count}:")
                print(f"  Position: [{x:.3f}, {y:.3f}, {z:.3f}]")
                print(f"  Orientation: [{roll:.3f}, {pitch:.3f}, {yaw:.3f}] (roll, pitch, yaw)")
                print(f"  Data count: {len(x_values)} samples")
                print("-" * 50)
            else:
                print(f"Frame {frame_count}: Waiting for OSC data...")
                
    except KeyboardInterrupt:
        print("\nStopping OSC receiver...")

if __name__ == "__main__":
    main() 