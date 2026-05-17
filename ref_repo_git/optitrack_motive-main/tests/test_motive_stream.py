from __future__ import annotations

import unittest
from unittest.mock import patch

from optitrack_motive.motive_stream import fetch_camera_statuses, fetch_recording_status


class FetchCameraStatusesTests(unittest.TestCase):
    def test_fetch_camera_statuses_returns_dict_keyed_by_camera_name(self) -> None:
        cameras = [
            {
                "name": "PrimeX 22 #103517",
                "serial": 103517,
                "position": (1.0, 2.0, 3.0),
                "orientation": (0.0, 0.0, 0.0, 1.0),
            }
        ]
        property_values = {
            ("PrimeX 22 #103517", "Video Mode"): "11",
            ("PrimeX 22 #103517", "Enabled"): "true",
            ("PrimeX 22 #103517", "Reconstruction"): "false",
        }

        fake_socket = object()

        with patch(
            "optitrack_motive.motive_stream.fetch_camera_descriptions",
            return_value=(cameras, "10.0.0.5"),
        ), patch(
            "optitrack_motive.motive_stream._open_natnet_command_socket"
        ) as open_socket, patch(
            "optitrack_motive.motive_stream._request_motive_text"
        ) as request_text:
            open_socket.return_value.__enter__.return_value = fake_socket
            open_socket.return_value.__exit__.return_value = False

            def side_effect(sock: object, server_ip: str, command: str) -> str:
                self.assertIs(sock, fake_socket)
                self.assertEqual(server_ip, "10.0.0.1")
                _, name, prop = command.split(",", 2)
                return property_values[(name, prop)]

            request_text.side_effect = side_effect

            status = fetch_camera_statuses("10.0.0.1")

        self.assertEqual(status["server_ip"], "10.0.0.1")
        self.assertEqual(status["client_ip"], "10.0.0.5")
        self.assertEqual(status["camera_count"], 1)

        camera = status["cameras"]["PrimeX 22 #103517"]
        self.assertEqual(camera["serial"], 103517)
        self.assertEqual(camera["video_mode"], 11)
        self.assertEqual(camera["video_mode_name"], "Duplex")
        self.assertTrue(camera["enabled"])
        self.assertFalse(camera["reconstruction_enabled"])
        self.assertTrue(camera["duplex"])


class FetchRecordingStatusTests(unittest.TestCase):
    def test_fetch_recording_status_infers_recording_when_take_length_advances(self) -> None:
        fake_socket = object()

        with patch(
            "optitrack_motive.motive_stream.resolve_client_ip",
            return_value="10.0.0.5",
        ), patch(
            "optitrack_motive.motive_stream._open_natnet_command_socket"
        ) as open_socket, patch(
            "optitrack_motive.motive_stream._request_motive_int"
        ) as request_int, patch(
            "optitrack_motive.motive_stream._request_motive_float",
            return_value=30.0,
        ):
            open_socket.return_value.__enter__.return_value = fake_socket
            open_socket.return_value.__exit__.return_value = False
            request_int.side_effect = [0, 100, 130]

            status = fetch_recording_status("10.0.0.1", sample_seconds=0.0)

        self.assertEqual(status["server_ip"], "10.0.0.1")
        self.assertEqual(status["client_ip"], "10.0.0.5")
        self.assertEqual(status["current_mode"], 0)
        self.assertEqual(status["current_mode_name"], "Live")
        self.assertEqual(status["frame_rate"], 30.0)
        self.assertEqual(status["current_take_length_start"], 100)
        self.assertEqual(status["current_take_length_end"], 130)
        self.assertEqual(status["delta_frames"], 30)
        self.assertTrue(status["recording"])


if __name__ == "__main__":
    unittest.main()
