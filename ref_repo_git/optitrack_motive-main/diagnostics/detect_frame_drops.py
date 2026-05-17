#!/usr/bin/env python3
import time
import sys # Added for sys.stdout.flush()
import argparse # Added for command-line arguments
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optitrack_motive.streaming.NatNetClient import NatNetClient

last_frame_number = -1
dropped_frames_detected = False

# This is a callback function that gets connected to the NatNet client.
# It is called once per mocap frame.
def receive_new_frame(data_dict):
    global last_frame_number, dropped_frames_detected
    current_frame_number = data_dict.get('frame_number')

    if current_frame_number is None:
        print("Warning: Frame number not found in data_dict.")
        return

    # print(f"Received frame: {current_frame_number}") # Made less spammy by commenting this out

    if last_frame_number != -1 and current_frame_number > last_frame_number + 1:
        dropped_count = current_frame_number - last_frame_number - 1
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"ERROR: Dropped {dropped_count} frame(s) between {last_frame_number} and {current_frame_number}")
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        dropped_frames_detected = True
    
    last_frame_number = current_frame_number


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NatNet Client for monitoring frame drops with configurable status update interval.")
    parser.add_argument("--interval", "-i", type=int, default=1, help="Interval in seconds for printing status updates. Default is 10 seconds.")
    args = parser.parse_args()

    status_update_interval = args.interval

    streaming_client = NatNetClient()
    monitoring_active_start_time = 0 # Initialize

    # Configure the NatNet client (Update with your actual IPs)
    # client_ip = "10.40.49.143"  # Client IP
    # client_ip = "0.0.0.0"  # Client IP
    server_ip = "10.40.49.47"   # Motive server IP

    # streaming_client.set_client_address(client_ip)
    streaming_client.set_server_address(server_ip)
    streaming_client.set_use_multicast(True)  # Enable multicast

    print(f"Attempting to connect to NatNet server:")
    print(f"  Client IP: {streaming_client.get_client_address()}")
    print(f"  Server IP: {streaming_client.get_server_address()}")
    print(f"  Using Multicast: {streaming_client.use_multicast}")
    if streaming_client.use_multicast:
        print(f"  Multicast Address: {streaming_client.multicast_address}")

    streaming_client.new_frame_listener = receive_new_frame
    print("Starting NatNet client thread...") # New message
    is_running_initially = streaming_client.run('d') # Renamed variable

    if not is_running_initially:
        print("ERROR: Could not start NatNet client. Please check connection and IPs.")
    else:
        # Removed old status messages:
        # print("NatNet client started successfully. Monitoring for dropped frames...")
        # if not dropped_frames_detected and last_frame_number != -1 : # Check if no drops and not the first frame
        #      print("Status: OK - Frames are being received continuously.")
        monitoring_active_start_time = time.time()
        print(f"NatNet client running. Live status updates will follow below.")


    try:
        if is_running_initially:
            last_status_print_time = 0 # Time of the last status print
            while True: # Loop indefinitely if client started
                current_time = time.time()
                if monitoring_active_start_time > 0 and (current_time - last_status_print_time >= status_update_interval or last_status_print_time == 0) :
                    elapsed_seconds = current_time - monitoring_active_start_time
                    hours = int(elapsed_seconds // 3600)
                    minutes = int((elapsed_seconds % 3600) // 60)
                    seconds = int(elapsed_seconds % 60)
                    formatted_elapsed_time = f"{hours:02d}h:{minutes:02d}m:{seconds:02d}s"

                    frame_to_display = last_frame_number
                    status_str = "DROPS DETECTED!" if dropped_frames_detected else "OK"

                    status_line_content = ""
                    if frame_to_display == -1: # No frames received yet
                        status_line_content = f"Status: {status_str} (Waiting for first frame) | Elapsed: {formatted_elapsed_time}"
                    else:
                        status_line_content = f"Status: {status_str} | Last Frame: {frame_to_display} | Elapsed: {formatted_elapsed_time}"
                    
                    print(status_line_content) # Print as a new line
                    last_status_print_time = current_time
                
                time.sleep(1) # Regulate update frequency of the main loop
            
            # This part below might not be reached if client thread dies silently
            # and the loop above is just time.sleep(1)
            if monitoring_active_start_time > 0: 
                print("\nINFO: Main monitoring loop exited. This might be unexpected if not by KeyboardInterrupt.")
        else:
            # Client did not start, error message already printed
            pass

    except KeyboardInterrupt:
        print("Stopping NatNet client due to KeyboardInterrupt...") # Add newline for clean exit
    finally:
        print() # Ensure cursor moves to next line before final summary, cleaning up from \r 
        if is_running_initially: # Only attempt shutdown if client was started
            print("Shutting down NatNet client...")
            streaming_client.shutdown()
        else:
            print("NatNet client was not started, no shutdown needed.")
        print("NatNet client stopped.")
        if dropped_frames_detected:
            print("Summary: Dropped frames WERE detected during this session.")
        else:
            print("Summary: No dropped frames detected during this session.")

    print("Exiting script.") 
