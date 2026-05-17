import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optitrack_motive.streaming.NatNetClient import NatNetClient

# This is a callback function that gets connected to the NatNet client.
# It is called once per mocap frame.
def receive_new_frame(data_dict):
    print(f"--- New Frame Received (Frame #: {data_dict.get('frame_number', 'N/A')}) ---")
    for key, value in data_dict.items():
        if key == "mocap_data":
            print(f"  {key}:")
            if hasattr(value, '__dict__'):
                # If it's an object with a __dict__, print its attributes
                for sub_key, sub_value in value.__dict__.items():
                    # Avoid printing very long lists of marker data directly in the main loop
                    if isinstance(sub_value, list) and len(sub_value) > 10 and sub_key in ["rigid_bodies", "labeled_markers", "unlabeled_markers", "skeletons", "assets"]:
                        print(f"    {sub_key}: List with {len(sub_value)} items (first item: {sub_value[0] if sub_value else 'empty'})")
                    else:
                        print(f"    {sub_key}: {sub_value}")
            else:
                # Otherwise, just print the value
                print(f"    {value}")
        else:
            print(f"  {key}: {value}")
    print("--- End of Frame Data ---")
    # You can access other data from the data_dict here, for example:
    # print("Rigid Body Count:", data_dict["rigid_body_count"])
    # print("Timestamp:", data_dict["timestamp"])

if __name__ == "__main__":
    # Create an instance of the NatNetClient.
    # You can provide client_ip, server_ip and multicast_address as arguments.
    # By default, it will connect to a server on localhost.
    streaming_client = NatNetClient()

    # Configure the NatNet client.
    streaming_client.set_server_address("10.40.49.47")

    print(f"Attempting to connect:")
    print(f"  Client IP: {streaming_client.get_client_address()}")
    print(f"  Server IP: {streaming_client.get_server_address()}")
    print(f"  Using Multicast: {streaming_client.use_multicast}")
    if streaming_client.use_multicast:
        print(f"  Multicast Address: {streaming_client.multicast_address}")

    # Connect the callback function to the client.
    # This function will be called every time a new frame is received.
    streaming_client.new_frame_listener = receive_new_frame

    # Start an asynchronous infinite loop.
    # This will run in a separate thread and call the receive_new_frame callback.
    is_running = streaming_client.run('d')
    print(f"streaming_client.run() returned: {is_running}")

    if not is_running:
        print("ERROR: Could not start NatNet client.")
        # Potentially add some error handling or exit the script
    else:
        print("NatNet client started successfully. Receiving data...")

    try:
        while True:
            # Keep the main thread alive, or do other work here.
            time.sleep(1)
    except KeyboardInterrupt:
        # Stop the client on KeyboardInterrupt (Ctrl+C).
        print("Stopping NatNet client...")
        streaming_client.shutdown()
        print("NatNet client stopped.")

    print("Exiting script.") 
