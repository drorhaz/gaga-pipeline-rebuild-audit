from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from optitrack_motive.mcal import (
    McalValidationError,
    normalize_camera_geometries,
    parse_mcal,
    parse_mcal_bytes,
    parse_mcal_text,
)


SAMPLE_MCAL = """<?xml version="1.0" encoding="UTF-16LE"?>
<calibrationProfile version="1">
    <MotiveBuildInfo AppVersion="3.4.0.2" BuildStamp="build" BuildDate="March 16, 2026"/>
    <Calibration>
        <Cameras Count="1">
            <Camera Serial="M123456">
                <Properties CameraID="6" ImagerIndex="00" Exposure="250"/>
                <Attributes Revision="50" ImagerPixelWidth="2048" ImagerPixelHeight="1088"/>
                <Intrinsic LensCenterX="1000.0" LensCenterY="500.0" HorizontalFocalLength="1200.0" VerticalFocalLength="1201.0" k1="0.1" k2="-0.2" k3="0.0" TangentialX="0.0" TangentialY="0.0"/>
                <IntrinsicStandardCameraModel LensCenterX="1000.0" LensCenterY="500.0" HorizontalFocalLength="1200.0" VerticalFocalLength="1201.0" k1="0.01" k2="-0.02" k3="0.001" TangentialX="0.0" TangentialY="0.0"/>
                <Extrinsic X="1.5" Y="2.5" Z="3.5" OrientMatrix0="1.0" OrientMatrix1="0.0" OrientMatrix2="0.0" OrientMatrix3="0.0" OrientMatrix4="1.0" OrientMatrix5="0.0" OrientMatrix6="0.0" OrientMatrix7="0.0" OrientMatrix8="1.0"/>
                <CameraSoftwareFilters FilterLevel="2"/>
                <CameraHardwareFilters GrayscaleFloor="48"/>
                <Calibration PartitionID="1"/>
                <ColorCamera CameraResolution="0"/>
            </Camera>
        </Cameras>
        <CalibrationAttributes>
            <TriangulationMeanResidual Error="0.001"/>
        </CalibrationAttributes>
    </Calibration>
    <property_warehouse>
        <properties>
            <property name="PCResidual" value="0.003013"/>
        </properties>
    </property_warehouse>
    <MaskData/>
</calibrationProfile>
"""


class ParseMcalTests(unittest.TestCase):
    def test_parse_mcal_path_bytes_and_text_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.mcal"
            path.write_text(SAMPLE_MCAL, encoding="utf-16")

            from_path = parse_mcal(path)
            from_bytes = parse_mcal_bytes(path.read_bytes(), str(path))
            from_text = parse_mcal_text(path.read_text(encoding="utf-16"), str(path))

        self.assertEqual(from_path, from_bytes)
        self.assertEqual(from_path, from_text)

    def test_parse_mcal_preserves_rich_camera_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.mcal"
            path.write_text(SAMPLE_MCAL, encoding="utf-16")

            parsed = parse_mcal(path)

        self.assertEqual(parsed["camera_count"], 1)
        self.assertEqual(parsed["motive_build_info"]["AppVersion"], "3.4.0.2")
        self.assertIn("raw_mcal", parsed)

        camera = parsed["cameras"][0]
        self.assertEqual(camera["name"], "M123456")
        self.assertEqual(camera["serial"], 123456)
        self.assertEqual(camera["serial_label"], "M123456")
        self.assertEqual(camera["position"], [1.5, 2.5, 3.5])
        self.assertEqual(camera["orientation_matrix"], [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])
        self.assertEqual(len(camera["orientation"]), 4)
        self.assertEqual(camera["properties"]["ImagerIndex"], "00")
        self.assertEqual(camera["color_camera"]["CameraResolution"], "0")

    def test_normalize_camera_geometries_extracts_strict_numeric_intrinsics(self) -> None:
        parsed = parse_mcal_text(SAMPLE_MCAL)

        geometries = normalize_camera_geometries(parsed)

        geometry = geometries[123456]
        self.assertEqual(geometry["serial"], 123456)
        self.assertEqual(geometry["name"], "M123456")
        self.assertEqual(geometry["model"], "PrimeX 22")
        self.assertEqual(geometry["image_width"], 2048)
        self.assertEqual(geometry["image_height"], 1088)
        self.assertEqual(geometry["fx"], 1200.0)
        self.assertEqual(geometry["fy"], 1201.0)
        self.assertEqual(geometry["cx"], 1000.0)
        self.assertEqual(geometry["cy"], 500.0)
        self.assertEqual(geometry["k1"], 0.01)
        self.assertEqual(geometry["k2"], -0.02)
        self.assertEqual(geometry["k3"], 0.001)
        self.assertEqual(geometry["p1"], 0.0)
        self.assertEqual(geometry["p2"], 0.0)
        self.assertEqual(geometry["intrinsics_source"], "IntrinsicStandardCameraModel")

    def test_normalize_camera_geometries_fails_when_required_intrinsics_are_missing(self) -> None:
        broken = SAMPLE_MCAL.replace(' LensCenterX="1000.0"', "", 2)
        parsed = parse_mcal_text(broken)

        with self.assertRaises(McalValidationError):
            normalize_camera_geometries(parsed)

    def test_normalize_camera_geometries_fails_when_selected_serial_is_missing(self) -> None:
        parsed = parse_mcal_text(SAMPLE_MCAL)

        with self.assertRaises(McalValidationError):
            normalize_camera_geometries(parsed, selected_serials=[123456, 999999])


if __name__ == "__main__":
    unittest.main()
