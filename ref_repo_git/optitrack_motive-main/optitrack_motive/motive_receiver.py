#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import numpy as np
import math
import time
import threading
import sys
import signal
# # from icecream import ic

# #from util import euler_from_quaternion
# sys.path.append("/home/lugo/git/NatNetSDK_4.1.0")

from optitrack_motive.streaming.NatNetClient import NatNetClient


def decode_marker_id(id_num):
    model_id = int(id_num) >> 16
    marker_id = int(id_num) & 0x0000ffff
    return model_id, marker_id


def decode_marker_params(param):
    param = int(param)
    return {
        "occluded": bool(param & 0x01),
        "point_cloud_solved": bool(param & 0x02),
        "model_solved": bool(param & 0x04),
    }


def _decode_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _position_tuple(position):
    if position is None:
        return None
    return tuple(float(value) for value in position[:3])


def compute_sq_distances(a, b):
    # Calculate differences using broadcasting
    diff = a[:, np.newaxis, :] - b[np.newaxis, :, :]
    # Calculate squared Euclidean distances
    dist_squared = np.sum(diff ** 2, axis=2)
    ## Take square root to get Euclidean distances
    # distances = np.sqrt(dist_squared)
    
    # Create dictionary to store dist_squared with index pairs
    distance_dict = {
        (i_a, i_b): dist_squared[i_a, i_b] 
        for i_a in range(dist_squared.shape[0]) 
        for i_b in range(dist_squared.shape[1])
    }
    distance_dict = dict(sorted(distance_dict.items(), key=lambda item: item[1]))
    return distance_dict


class MotiveReceiver:
    def __init__(
        self, 
        server_ip, 
        client_ip="0.0.0.0",  # Default to all interfaces to receive multicast
        max_buffer_size=100000, 
        start_process=True, 
        do_record_streaming=False, 
        do_mock_streaming=False, 
        fn_mock='streaming_mock.pkl',
        verbose=False,
    ):
        self.server_ip = server_ip
        self.client_ip = client_ip
        self.max_buffer_size = max_buffer_size
        self.marker_data = []
        self.lock = threading.Lock()
        self.running = True
        self.sleep_time = 0.000001
        self.list_raw_packets = []
        self.list_dict_packets = []
        
        
        self.v_last_time = 0
        self.v_sampling_time = 0.01
        self.last_frame_id = 0
        self.list_labels = []
        self.dict_label_idx = {}
        self.set_labels = set()
        self.list_unlabeled = []
        self.list_timestamps = []
        
        self.max_nr_markers = 999
        self.positions = np.zeros([self.max_buffer_size, self.max_nr_markers, 3])*np.nan
        self.velocities = np.zeros([self.max_buffer_size, self.max_nr_markers, 3])
        self.pos_idx = 0
        self.last_timestamp = None
                        
        self.do_record_streaming = do_record_streaming
        self.do_mock_streaming = do_mock_streaming
        self.fn_mock = fn_mock
        self.verbose = verbose
        # self.rigid_body_positions = {label:[] for label in self.rigid_body_labels}
        if start_process:
            self.start_process()

    def get_last_by_model(self, simbly, model_name=""):
        latest = self.get_last()
        if latest is None or simbly not in latest:
            return None
        if model_name and isinstance(latest[simbly], dict) and model_name in latest[simbly]:
            return latest[simbly][model_name]
        return latest[simbly]

    def get_last_timestamp(self):
        latest = self.get_last()
        if latest is not None:
            return latest['timestamp']
        else:
            return 0
                

    def start_process(self):
        self.thread = threading.Thread(target=self.get_data)
        self.thread.start()

    def get_data(self):
        try:
            optionsDict = {}
            optionsDict["clientAddress"] = self.client_ip
            optionsDict["serverAddress"] = self.server_ip
            optionsDict["use_multicast"] = True

            self.streaming_client = NatNetClient()
            self.streaming_client.set_print_level(1 if self.verbose else 0)
            self.streaming_client.set_suppress_output(not self.verbose)
            if self.do_record_streaming:
                self.streaming_client.set_record_streaming(fn_mock=self.fn_mock)
            if self.do_mock_streaming:
                self.streaming_client.set_mock_streaming(fn_mock=self.fn_mock)
            self.streaming_client.set_client_address(optionsDict["clientAddress"])
            self.streaming_client.set_server_address(optionsDict["serverAddress"])
            self.streaming_client.set_use_multicast(optionsDict["use_multicast"])
            self.streaming_client.new_frame_with_data_listener = self.process_packet
                
            is_running = self.streaming_client.run('d')
            if not is_running:
                print("ERROR: Could not start streaming client.")
                return
        except Exception as e:
            print(f"ERROR: Exception in streaming client: {e}")
            return
            

    def save_packet(self, packet_content):
        self.list_raw_packets.append(packet_content)
        
    def normalizer_data(self, dict_data):
        marker_sets = dict_data.get("marker_sets_labeled_data", [])
        marker_sets_for_rigid_bodies = [
            marker_set for marker_set in marker_sets
            if _decode_text(marker_set.get("model_name")).lower() != "all"
        ] or marker_sets
        dict_data["rigid_bodies_full"] = {}
        
        sorted_rigid_bodies = sorted(
            dict_data.get("rigid_bodies", []),
            key=lambda x: x["id_num"],
        )
        
        for idx, rigid_body in enumerate(sorted_rigid_bodies):
            out = rigid_body.copy()
            
            if idx < len(marker_sets_for_rigid_bodies):
                marker_set = marker_sets_for_rigid_bodies[idx]
                out["markers"] = marker_set.get("marker_pos_list", [])
                
                if len(dict_data["labeled_markers"]) > idx:
                    out["labeled_markers"] = dict_data["labeled_markers"][idx]
                    
                model_name = _decode_text(marker_set.get("model_name"))
                dict_data["rigid_bodies_full"][model_name] = out
            else:
                model_name = f"RigidBody_{rigid_body['id_num']}"
                dict_data["rigid_bodies_full"][model_name] = out
                
        return dict_data
    
    def process_packet(self, data_dict):
        mocap_data = data_dict["mocap_data"]
        asset_data = getattr(mocap_data, "asset_data", None)
        dict_data = {
            "frame_id": data_dict["frame_number"],
            "timestamp": mocap_data.suffix_data.timestamp,
            "marker_sets_unlabeled_data": mocap_data.marker_set_data.unlabeled_markers.__dict__,
            "unlabeled_markers": mocap_data.legacy_other_markers.__dict__,
            "marker_sets_labeled_data": [
                marker_set.__dict__ for marker_set in mocap_data.marker_set_data.marker_data_list
            ],
            "labeled_markers": [
                marker.__dict__ for marker in mocap_data.labeled_marker_data.labeled_marker_list
            ],
            "rigid_bodies": [
                rigid_body.__dict__ for rigid_body in mocap_data.rigid_body_data.rigid_body_list
            ],
            "asset_data": asset_data.__dict__ if asset_data is not None else None,
            "skeletons_list": [
                skeleton.__dict__ for skeleton in mocap_data.skeleton_data.skeleton_list
            ],
        }

        #if len(dict_data["skeletons_list"]) > 0:
        for ii,_ in enumerate(dict_data["skeletons_list"]):
            if "rigid_body_list" in _.keys():
                for i,__ in enumerate(_["rigid_body_list"]):
                    dict_data["skeletons_list"][ii]["rigid_body_list"][i] = __.__dict__
        #print(dict_data["skeletons_list"])
        dict_data = self.normalizer_data(dict_data)
        with self.lock:
            self.list_dict_packets.append(dict_data)
        

    def stop(self):
        if self.verbose:
            print("stopping process!")
        self.running = False
        if hasattr(self, 'streaming_client') and self.streaming_client:
            self.streaming_client.shutdown()
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join()

    def get_last(self, label=None):
        with self.lock:
            latest = self.list_dict_packets[-1] if self.list_dict_packets else None
        if latest is None:
            return None
        if label is None:
            return latest
        return latest.get(label)

    def wait_for_frame(self, timeout=5.0, poll_interval=0.01):
        deadline = time.time() + timeout
        while time.time() < deadline:
            latest = self.get_last()
            if latest is not None:
                return latest
            time.sleep(poll_interval)
        return None

    def get_rigid_body_names(self, frame=None):
        frame = frame if frame is not None else self.get_last()
        if frame is None:
            return []
        return sorted(frame.get("rigid_bodies_full", {}).keys())

    def get_rigid_body(self, name=None, frame=None):
        frame = frame if frame is not None else self.get_last()
        if frame is None:
            return None
        rigid_bodies = frame.get("rigid_bodies_full", {})
        if name is None:
            if len(rigid_bodies) == 1:
                return next(iter(rigid_bodies.values()))
            return None
        return rigid_bodies.get(name)

    def get_marker_sets(self, frame=None):
        frame = frame if frame is not None else self.get_last()
        if frame is None:
            return {}

        marker_sets = {}
        for idx, marker_set in enumerate(frame.get("marker_sets_labeled_data", [])):
            name = _decode_text(marker_set.get("model_name")) or f"marker_set_{idx}"
            key = name if name not in marker_sets else f"{name}_{idx}"
            marker_sets[key] = [
                _position_tuple(pos) for pos in marker_set.get("marker_pos_list", [])
            ]
        return marker_sets

    def get_unlabeled_markers(self, frame=None):
        frame = frame if frame is not None else self.get_last()
        if frame is None:
            return []

        source = frame.get("unlabeled_markers") or frame.get("marker_sets_unlabeled_data") or {}
        return [
            _position_tuple(pos) for pos in source.get("marker_pos_list", [])
        ]

    def get_labeled_markers(self, frame=None):
        frame = frame if frame is not None else self.get_last()
        if frame is None:
            return []

        model_names_by_id = {
            int(body.get("id_num")): name
            for name, body in frame.get("rigid_bodies_full", {}).items()
            if body.get("id_num") is not None
        }
        out = []
        for idx, marker in enumerate(frame.get("labeled_markers", [])):
            id_num = int(marker.get("id_num", 0))
            model_id, marker_id = decode_marker_id(id_num)
            marker_info = {
                "index": idx,
                "id_num": id_num,
                "model_id": model_id,
                "model_name": model_names_by_id.get(model_id),
                "marker_id": marker_id,
                "position": _position_tuple(marker.get("pos")),
                "size": float(marker.get("size", 0.0)),
                "param": int(marker.get("param", 0)),
                "residual": float(marker.get("residual", 0.0)),
            }
            marker_info.update(decode_marker_params(marker_info["param"]))
            out.append(marker_info)
        return out


if __name__ == "__main__":
    # Create a MotiveReceiver instance with the server IP
    motive = MotiveReceiver(server_ip="10.40.49.47")
    
    # Signal handler for graceful shutdown
    def signal_handler(signum, frame):
        print("\nStopping receiver...")
        motive.stop()
        print("Shutdown complete.")
        sys.exit(0)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    # Wait a moment for connection to establish
    import time
    time.sleep(1)
    
    # Keep the script running to receive and display data
    try:
        print("Receiving data from OptiTrack. Press Ctrl+C to stop.")
        print("Waiting for data...")
        
        while True:
            latest_data = motive.get_last()
            if latest_data:
                # Print all frames with all rigid bodies
                print(f"\nFrame ID: {latest_data['frame_id']}")
                print(f"Timestamp: {latest_data['timestamp']}")
                if 'rigid_bodies_full' in latest_data and latest_data['rigid_bodies_full']:
                    print("\nRigid Bodies:")
                    for name, body in latest_data['rigid_bodies_full'].items():
                        pos = body.get('pos')
                        print(f"  {name}: Position {pos}")
                else:
                    print("No rigid bodies detected")
            else:
                print(".", end="", flush=True)

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nStopping receiver...")
        motive.stop()
        print("Shutdown complete.")
        
