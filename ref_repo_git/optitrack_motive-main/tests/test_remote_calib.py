from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from optitrack_motive.calib import _parse_calib_timestamp
from optitrack_motive.calib.remote import (
    CalibrationBundle,
    RemoteCalibrationError,
    build_payload_from_mcal,
    extract_raw_mcal_bytes,
    extract_raw_mcal_from_snapshot,
    fetch_latest,
    fetch_remote_mcal_bytes,
    save_snapshot,
    write_raw_mcal_from_snapshot,
    _snapshot_stamp,
)


SAMPLE_MCAL = """<?xml version="1.0" encoding="UTF-16LE"?>
<calibrationProfile version="1">
    <MotiveBuildInfo AppVersion="3.4.0.2"/>
    <Calibration>
        <Cameras Count="1">
            <Camera Serial="M123456">
                <Properties CameraID="6" Enabled="1" EnabledForRecording="1" FrameRate="30" VideoType="2"/>
                <Attributes Revision="50" ImagerPixelWidth="2048" ImagerPixelHeight="1088"/>
                <IntrinsicStandardCameraModel LensCenterX="1000.0" LensCenterY="500.0" HorizontalFocalLength="1200.0" VerticalFocalLength="1201.0" k1="0.01" k2="-0.02" k3="0.001" TangentialX="0.003" TangentialY="-0.004"/>
                <Extrinsic X="1.5" Y="2.5" Z="3.5" OrientMatrix0="1.0" OrientMatrix1="0.0" OrientMatrix2="0.0" OrientMatrix3="0.0" OrientMatrix4="1.0" OrientMatrix5="0.0" OrientMatrix6="0.0" OrientMatrix7="0.0" OrientMatrix8="1.0"/>
            </Camera>
        </Cameras>
        <CalibrationAttributes/>
    </Calibration>
    <property_warehouse/>
    <MaskData/>
</calibrationProfile>
"""


def _sample_bytes() -> bytes:
    return SAMPLE_MCAL.encode("utf-16")


def _sample_with_aux_camera_bytes() -> bytes:
    aux_camera = """
            <Camera Serial="C11679">
                <Properties CameraID="99" Enabled="1"/>
                <Attributes Revision="50" ImagerPixelWidth="1920" ImagerPixelHeight="1200"/>
                <Extrinsic X="4.0" Y="5.0" Z="6.0" OrientMatrix0="1.0" OrientMatrix1="0.0" OrientMatrix2="0.0" OrientMatrix3="0.0" OrientMatrix4="1.0" OrientMatrix5="0.0" OrientMatrix6="0.0" OrientMatrix7="0.0" OrientMatrix8="1.0"/>
            </Camera>
"""
    text = SAMPLE_MCAL.replace('<Cameras Count="1">', '<Cameras Count="2">')
    text = text.replace("        </Cameras>", f"{aux_camera}        </Cameras>")
    return text.encode("utf-16")


def _source(raw: bytes) -> dict:
    return {
        "transport": "ssh",
        "host": "Admin@kyushu",
        "path": r"C:\ProgramData\OptiTrack\Motive\System Calibration.mcal",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "mtime_utc": "2026-04-28T12:00:00Z",
        "motive_running": True,
        "fetched_at_utc": "2026-04-28T12:00:05Z",
        "raw_mcal": raw,
    }


class RemoteCalibTests(unittest.TestCase):
    def test_calib_timestamp_parser_accepts_legacy_minutes_and_snapshot_seconds(self) -> None:
        legacy = _parse_calib_timestamp("cork_260428_0818.json", "cork")
        current = _parse_calib_timestamp("cork_260428_081800.json", "cork")

        self.assertIsNotNone(legacy)
        self.assertIsNotNone(current)
        self.assertEqual(legacy.replace(second=0), current)

    def test_fetch_remote_mcal_bytes_decodes_and_verifies_ssh_payload(self) -> None:
        raw = _sample_bytes()
        response = {
            "path": r"C:\ProgramData\OptiTrack\Motive\System Calibration.mcal",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
            "mtime_utc": "2026-04-28T12:00:00Z",
            "motive_running": True,
            "content_base64": base64.b64encode(raw).decode("ascii"),
        }

        with patch(
            "optitrack_motive.calib.remote.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(response), stderr=""),
        ) as run:
            fetched = fetch_remote_mcal_bytes("Admin@kyushu", response["path"], timeout=5.0)

        self.assertEqual(fetched["raw_mcal"], raw)
        self.assertEqual(fetched["sha256"], response["sha256"])
        self.assertEqual(fetched["size_bytes"], len(raw))
        self.assertEqual(fetched["host"], "Admin@kyushu")
        self.assertEqual(fetched["transport"], "ssh")
        self.assertEqual(run.call_args.args[0][0], "ssh")

    def test_build_payload_from_mcal_preserves_raw_tree_and_adds_geometry(self) -> None:
        raw = _sample_bytes()

        payload = build_payload_from_mcal(raw, room="cork", source=_source(raw))

        self.assertEqual(payload["format_version"], 2)
        self.assertEqual(payload["room"], "cork")
        self.assertEqual(payload["source"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertIn("raw_mcal", payload["mcal"])
        self.assertEqual(payload["cameras"][0]["serial"], 123456)
        geometry = payload["camera_geometry_by_serial"][123456]
        self.assertEqual(geometry["fx"], 1200.0)
        self.assertEqual(geometry["p2"], -0.004)

    def test_build_payload_strictly_normalizes_only_selected_cameras(self) -> None:
        raw = _sample_with_aux_camera_bytes()

        payload = build_payload_from_mcal(
            raw,
            room="cork",
            source=_source(raw),
            selected_serials=[123456],
        )

        self.assertEqual(payload["mcal"]["camera_count"], 2)
        self.assertEqual(payload["selected_camera_serials"], [123456])
        self.assertEqual(sorted(payload["camera_geometry_by_serial"]), [123456])
        self.assertEqual(len(payload["mcal"]["cameras"]), 2)

    def test_fetch_latest_retries_when_first_remote_read_is_malformed(self) -> None:
        raw = _sample_bytes()

        with patch(
            "optitrack_motive.calib.remote.fetch_remote_mcal_bytes",
            side_effect=[
                {**_source(b"<not xml>"), "raw_mcal": b"<not xml>"},
                _source(raw),
            ],
        ), patch("optitrack_motive.calib.remote._selected_camera_serials", return_value=None):
            bundle = fetch_latest(room="cork", retries=2, timeout=1.0)

        self.assertEqual(bundle.payload["source"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(bundle.payload["mcal"]["camera_count"], 1)

    def test_snapshot_stamp_uses_local_wall_clock_time(self) -> None:
        self.assertEqual(_snapshot_stamp(datetime(2026, 4, 28, 15, 32, 5)), "260428_153205")

    def test_save_snapshot_writes_one_json_with_extractable_raw_mcal(self) -> None:
        raw = _sample_bytes()
        payload = build_payload_from_mcal(raw, room="cork", source=_source(raw))
        bundle = CalibrationBundle(payload=payload, raw_mcal=raw)

        with tempfile.TemporaryDirectory() as tmpdir:
            saved = save_snapshot(bundle, room="cork", output_dir=Path(tmpdir))
            saved_payload = json.loads(saved.snapshot_path.read_text(encoding="utf-8"))
            extracted = extract_raw_mcal_from_snapshot(saved.snapshot_path)
            export_path = write_raw_mcal_from_snapshot(saved.snapshot_path, Path(tmpdir) / "exported.mcal")
            exported = export_path.read_bytes()
            sidecar_dir_exists = (Path(tmpdir) / "calib_sources").exists()

        expected_sha = hashlib.sha256(raw).hexdigest()
        self.assertIsNone(saved.raw_sidecar_path)
        self.assertFalse(sidecar_dir_exists)
        self.assertEqual(extracted, raw)
        self.assertEqual(exported, raw)
        self.assertEqual(hashlib.sha256(extracted).hexdigest(), expected_sha)
        self.assertEqual(saved_payload["raw_mcal"]["encoding"], "base64")
        self.assertEqual(saved_payload["raw_mcal"]["sha256"], expected_sha)
        self.assertEqual(saved_payload["raw_mcal"]["size_bytes"], len(raw))
        self.assertEqual(extract_raw_mcal_bytes(saved_payload), raw)
        self.assertEqual(saved_payload["source"]["raw_mcal_sha256"], expected_sha)
        self.assertEqual(saved_payload["source"]["raw_mcal_size_bytes"], len(raw))
        self.assertEqual(saved_payload["source"]["raw_mcal_storage"], "embedded_base64")

    def test_extract_raw_mcal_rejects_tampered_snapshot_hash(self) -> None:
        raw = _sample_bytes()
        payload = build_payload_from_mcal(raw, room="cork", source=_source(raw))
        with tempfile.TemporaryDirectory() as tmpdir:
            saved = save_snapshot(
                CalibrationBundle(payload=payload, raw_mcal=raw),
                room="cork",
                output_dir=Path(tmpdir),
            )
            tampered = json.loads(json.dumps(saved.payload))
        tampered["raw_mcal"]["sha256"] = "0" * 64

        with self.assertRaises(RemoteCalibrationError):
            extract_raw_mcal_bytes(tampered)


if __name__ == "__main__":
    unittest.main()
