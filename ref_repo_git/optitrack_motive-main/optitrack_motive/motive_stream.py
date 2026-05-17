"""Helpers for retrieving OptiTrack data via the NatNet client."""

from __future__ import annotations

import socket
import struct
import re
import threading
import time
from typing import Any, Dict, List, Tuple

from .streaming.NatNetClient import NatNetClient

_NATNET_COMMAND_PORT = 1510
_NATNET_DATA_PORT = 1511

_VIDEO_MODE_NAMES = {
    0: "Segment",
    1: "Grayscale",
    2: "Object",
    4: "Precision",
    6: "MJPEG",
    9: "ColorH264",
    11: "Duplex",
}

_MODE_NAMES = {
    0: "Live",
    1: "Edit",
}


def resolve_client_ip(server_ip: str, requested: str = "auto") -> str:
    """Determine the appropriate client IP for NatNet streaming."""
    if requested and requested.lower() not in {"", "auto"}:
        return requested

    if server_ip.startswith("127.") or server_ip.lower() == "localhost":
        return "127.0.0.1"

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((server_ip, _NATNET_DATA_PORT))
            return sock.getsockname()[0]
    except OSError:
        # Fall back to binding all interfaces if detection fails.
        return "0.0.0.0"


def _parse_camera_descriptions(data_descs: Any) -> List[Dict[str, Any]]:
    """Extract camera metadata from a NatNet model definition."""
    cameras: List[Dict[str, Any]] = []
    for camera_desc in getattr(data_descs, "camera_list", []):
        name = getattr(camera_desc, "name", getattr(camera_desc, "camera_name", "Camera"))
        if isinstance(name, bytes):
            name = name.decode("utf-8", errors="ignore")
        name_str = str(name)
        serial = None
        match = re.search(r"#\s*(\d+)", name_str)
        if match:
            serial = int(match.group(1))

        raw_position = list(getattr(camera_desc, "position", [0.0, 0.0, 0.0]))
        if len(raw_position) < 3:
            raw_position = (raw_position + [0.0, 0.0, 0.0])[:3]

        raw_orientation = list(getattr(camera_desc, "orientation", [0.0, 0.0, 0.0, 1.0]))
        if len(raw_orientation) < 4:
            raw_orientation = (raw_orientation + [0.0, 0.0, 0.0, 1.0])[:4]

        position = tuple(float(x) for x in raw_position[:3])
        orientation = tuple(float(x) for x in raw_orientation[:4])

        cameras.append({
            "name": name_str,
            "serial": serial,
            "position": position,
            "orientation": orientation,
        })

    return cameras


def fetch_camera_descriptions(
    server_ip: str,
    client_ip: str = "auto",
    timeout: float = 8.0,
    verbose: bool = False,
    use_multicast: bool = True,
) -> Tuple[List[Dict[str, Any]], str]:
    """Retrieve camera descriptions from Motive via NatNet."""
    resolved_client_ip = resolve_client_ip(server_ip, client_ip)

    client = NatNetClient()
    client.set_server_address(server_ip)
    client.set_client_address(resolved_client_ip)
    client.set_use_multicast(use_multicast)

    if hasattr(client, "set_print_level"):
        client.set_print_level(1 if verbose else 0)
    if hasattr(client, "set_suppress_output"):
        client.set_suppress_output(not verbose)

    data_descs_holder: Dict[str, Any] = {}
    data_descs_event = threading.Event()

    def on_data_descs(data_descs: Any) -> None:
        data_descs_holder["data"] = data_descs
        data_descs_event.set()

    client.data_description_listener = on_data_descs

    if not client.run('c'):
        client.data_description_listener = None
        raise RuntimeError("Failed to start NatNet client")

    try:
        client.send_request(
            client.command_socket,
            client.NAT_REQUEST_MODELDEF,
            "",
            (client.server_ip_address, client.command_port),
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            if data_descs_event.wait(timeout=0.1):
                data_descs = data_descs_holder.get("data")
                cameras = _parse_camera_descriptions(data_descs)
                return cameras, resolved_client_ip

        raise TimeoutError("Timed out waiting for camera descriptions from Motive")
    finally:
        client.data_description_listener = None
        client.shutdown()


def _nat_connect_packet() -> bytes:
    handshake = [0] * 270
    handshake[0:4] = [80, 105, 110, 103]  # "Ping"
    handshake[264:269] = [0, 4, 2, 0, 0]
    payload = bytes(handshake) + b"\0"
    return (
        NatNetClient.NAT_CONNECT.to_bytes(2, byteorder="little", signed=True)
        + len(handshake).to_bytes(2, byteorder="little", signed=True)
        + payload
    )


def _nat_request_packet(command: str) -> bytes:
    payload = command.encode("utf-8") + b"\0"
    return (
        NatNetClient.NAT_REQUEST.to_bytes(2, byteorder="little", signed=True)
        + len(command).to_bytes(2, byteorder="little", signed=True)
        + payload
    )


def _recv_nat_packet(sock: socket.socket) -> Tuple[int, bytes]:
    data, _ = sock.recvfrom(65535)
    message_id = int.from_bytes(data[0:2], byteorder="little", signed=True)
    packet_size = int.from_bytes(data[2:4], byteorder="little", signed=True)
    payload = bytes(data[4:4 + packet_size])
    return message_id, payload


def _open_natnet_command_socket(server_ip: str, client_ip: str, timeout: float) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.bind((client_ip, 0))
    sock.sendto(_nat_connect_packet(), (server_ip, _NATNET_COMMAND_PORT))

    message_id, _ = _recv_nat_packet(sock)
    if message_id != NatNetClient.NAT_SERVERINFO:
        sock.close()
        raise RuntimeError(f"Unexpected NatNet connect response: {message_id}")

    return sock


def _request_motive_payload(sock: socket.socket, server_ip: str, command: str) -> bytes:
    sock.sendto(_nat_request_packet(command), (server_ip, _NATNET_COMMAND_PORT))
    message_id, payload = _recv_nat_packet(sock)

    if message_id == NatNetClient.NAT_UNRECOGNIZED_REQUEST:
        raise RuntimeError(f"Motive did not recognize NatNet command: {command}")

    if message_id not in {NatNetClient.NAT_RESPONSE, NatNetClient.NAT_MESSAGESTRING}:
        raise RuntimeError(f"Unexpected NatNet response {message_id} for command: {command}")

    return payload


def _payload_ascii_text(payload: bytes) -> str | None:
    stripped = payload.rstrip(b"\0")
    if not stripped:
        return ""

    if all(32 <= byte <= 126 for byte in stripped):
        return stripped.decode("ascii")

    return None


def _request_motive_text(sock: socket.socket, server_ip: str, command: str) -> str:
    payload = _request_motive_payload(sock, server_ip, command)

    text = _payload_ascii_text(payload)
    if text is not None and text != "":
        return text

    if len(payload) == 4:
        return str(int.from_bytes(payload, byteorder="little", signed=True))

    if text == "":
        return text

    return ""


def _request_motive_int(sock: socket.socket, server_ip: str, command: str) -> int:
    return int(_request_motive_text(sock, server_ip, command))


def _request_motive_float(sock: socket.socket, server_ip: str, command: str) -> float:
    payload = _request_motive_payload(sock, server_ip, command)

    if len(payload) == 4:
        return float(struct.unpack("<f", payload)[0])

    text = _payload_ascii_text(payload)
    if text is not None and text != "":
        return float(text)

    raise ValueError(f"Expected float response, got payload {payload!r}")


def _parse_bool_text(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"Expected boolean text, got {value!r}")


def fetch_camera_statuses(
    server_ip: str,
    client_ip: str = "auto",
    timeout: float = 8.0,
    use_multicast: bool = True,
) -> Dict[str, Any]:
    """Query live Motive camera status and video mode via NatNet remote properties."""
    cameras_raw, resolved_client_ip = fetch_camera_descriptions(
        server_ip,
        client_ip,
        timeout=timeout,
        verbose=False,
        use_multicast=use_multicast,
    )

    cameras_by_name: Dict[str, Dict[str, Any]] = {}

    with _open_natnet_command_socket(server_ip, resolved_client_ip, timeout) as sock:
        for camera in cameras_raw:
            name = str(camera["name"])
            video_mode_text = _request_motive_text(sock, server_ip, f"GetProperty,{name},Video Mode")
            enabled_text = _request_motive_text(sock, server_ip, f"GetProperty,{name},Enabled")
            reconstruction_text = _request_motive_text(sock, server_ip, f"GetProperty,{name},Reconstruction")

            video_mode = int(video_mode_text)

            camera_status = dict(camera)
            camera_status["enabled"] = _parse_bool_text(enabled_text)
            camera_status["reconstruction_enabled"] = _parse_bool_text(reconstruction_text)
            camera_status["video_mode"] = video_mode
            camera_status["video_mode_name"] = _VIDEO_MODE_NAMES.get(video_mode, f"Unknown({video_mode})")
            camera_status["duplex"] = video_mode == 11
            cameras_by_name[name] = camera_status

    return {
        "server_ip": server_ip,
        "client_ip": resolved_client_ip,
        "camera_count": len(cameras_by_name),
        "cameras": cameras_by_name,
    }


def fetch_recording_status(
    server_ip: str,
    client_ip: str = "auto",
    timeout: float = 8.0,
    sample_seconds: float = 1.0,
) -> Dict[str, Any]:
    """Infer whether Motive is actively recording by sampling live take length."""
    resolved_client_ip = resolve_client_ip(server_ip, client_ip)

    with _open_natnet_command_socket(server_ip, resolved_client_ip, timeout) as sock:
        current_mode = _request_motive_int(sock, server_ip, "CurrentMode")
        frame_rate = _request_motive_float(sock, server_ip, "FrameRate")
        take_length_start = _request_motive_int(sock, server_ip, "CurrentTakeLength")
        time.sleep(max(sample_seconds, 0.0))
        take_length_end = _request_motive_int(sock, server_ip, "CurrentTakeLength")

    delta_frames = take_length_end - take_length_start
    recording = current_mode == 0 and delta_frames > 0

    return {
        "server_ip": server_ip,
        "client_ip": resolved_client_ip,
        "current_mode": current_mode,
        "current_mode_name": _MODE_NAMES.get(current_mode, f"Unknown({current_mode})"),
        "frame_rate": frame_rate,
        "sample_seconds": max(sample_seconds, 0.0),
        "current_take_length_start": take_length_start,
        "current_take_length_end": take_length_end,
        "delta_frames": delta_frames,
        "recording": recording,
    }
