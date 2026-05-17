"""Helpers for reading Motive .mcal calibration exports."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Union


PathLike = Union[str, Path]

PRIMEX_22 = "PrimeX 22"
PRIMEX_13W = "PrimeX 13W"
PRIME_COLOR_FS = "Prime Color-FS"

PRIMEX_22_SERIALS = {
    103517,
    103518,
    103519,
    103520,
    103521,
    103522,
    109641,
    109642,
}
PRIMEX_13W_SERIALS = {108490, 108496}
PRIME_COLOR_FS_SERIALS = {11679, 11680, 11681}


class McalValidationError(ValueError):
    """Raised when strict normalized calibration data cannot be built."""


def _float_attr(attrs: Dict[str, str], key: str, default: float = 0.0) -> float:
    value = attrs.get(key)
    if value is None:
        return default
    return float(value)


def _required_float(attrs: Dict[str, Any], key: str, label: str) -> float:
    value = attrs.get(key)
    if value in (None, ""):
        raise McalValidationError(f"{label} missing required field {key!r}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise McalValidationError(f"{label} has invalid float field {key!r}: {value!r}") from exc


def _required_int(attrs: Dict[str, Any], key: str, label: str) -> int:
    value = attrs.get(key)
    if value in (None, ""):
        raise McalValidationError(f"{label} missing required field {key!r}")
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise McalValidationError(f"{label} has invalid integer field {key!r}: {value!r}") from exc


def _optional_int(attrs: Dict[str, Any], key: str) -> Optional[int]:
    value = attrs.get(key)
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_bool(attrs: Dict[str, Any], key: str) -> Optional[bool]:
    value = attrs.get(key)
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    return None


def _matrix_to_quaternion(values: Iterable[float]) -> List[float]:
    """Convert a row-major 3x3 rotation matrix into a quaternion."""
    m = list(values)
    if len(m) != 9:
        raise ValueError("Rotation matrix must contain exactly 9 values.")

    m00, m01, m02 = m[0], m[1], m[2]
    m10, m11, m12 = m[3], m[4], m[5]
    m20, m21, m22 = m[6], m[7], m[8]

    trace = m00 + m11 + m22
    if trace > 0.0:
        s = (trace + 1.0) ** 0.5 * 2.0
        w = 0.25 * s
        x = (m21 - m12) / s
        y = (m02 - m20) / s
        z = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = (1.0 + m00 - m11 - m22) ** 0.5 * 2.0
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = (1.0 + m11 - m00 - m22) ** 0.5 * 2.0
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = (1.0 + m22 - m00 - m11) ** 0.5 * 2.0
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s

    return [float(x), float(y), float(z), float(w)]


def infer_camera_model(serial: Optional[int], name: str = "", token_prefix: Optional[str] = None) -> Optional[str]:
    """Infer the camera model from known Cork serials and Motive camera labels."""

    prefix = (token_prefix or "").upper() or None
    name_lower = str(name or "").lower()
    if (
        "prime color-fs" in name_lower
        or prefix == "C"
        or (serial is not None and int(serial) in PRIME_COLOR_FS_SERIALS)
    ):
        return PRIME_COLOR_FS
    if "primex 13w" in name_lower or (serial is not None and int(serial) in PRIMEX_13W_SERIALS):
        return PRIMEX_13W
    if "primex 22" in name_lower or (serial is not None and int(serial) in PRIMEX_22_SERIALS):
        return PRIMEX_22
    if prefix == "M":
        return PRIMEX_22
    return None


def _element_to_tree(element: ET.Element) -> Dict[str, Any]:
    """Convert XML into a JSON-friendly tree while preserving all attributes."""
    node: Dict[str, Any] = {}
    if element.attrib:
        node["attributes"] = dict(element.attrib)

    text = (element.text or "").strip()
    children = [child for child in list(element) if isinstance(child.tag, str)]
    if text:
        node["text"] = text

    if not children:
        return node

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for child in children:
        grouped[child.tag].append(_element_to_tree(child))

    for tag, items in grouped.items():
        node[tag] = items[0] if len(items) == 1 else items
    return node


def _parse_camera(camera: ET.Element) -> Dict[str, Any]:
    serial_label = camera.attrib.get("Serial", "")
    serial_match = re.search(r"(\d+)$", serial_label)
    serial_number = int(serial_match.group(1)) if serial_match else None

    sections = {child.tag: child for child in camera if isinstance(child.tag, str)}
    properties = dict(sections["Properties"].attrib) if "Properties" in sections else {}
    attributes = dict(sections["Attributes"].attrib) if "Attributes" in sections else {}
    intrinsic = dict(sections["Intrinsic"].attrib) if "Intrinsic" in sections else {}
    intrinsic_standard = (
        dict(sections["IntrinsicStandardCameraModel"].attrib)
        if "IntrinsicStandardCameraModel" in sections
        else {}
    )
    extrinsic = dict(sections["Extrinsic"].attrib) if "Extrinsic" in sections else {}
    software_filters = (
        dict(sections["CameraSoftwareFilters"].attrib)
        if "CameraSoftwareFilters" in sections
        else {}
    )
    hardware_filters = (
        dict(sections["CameraHardwareFilters"].attrib)
        if "CameraHardwareFilters" in sections
        else {}
    )
    calibration = dict(sections["Calibration"].attrib) if "Calibration" in sections else {}
    color_camera = dict(sections["ColorCamera"].attrib) if "ColorCamera" in sections else {}

    position = [
        _float_attr(extrinsic, "X"),
        _float_attr(extrinsic, "Y"),
        _float_attr(extrinsic, "Z"),
    ]
    orientation_matrix = [
        _float_attr(extrinsic, f"OrientMatrix{i}")
        for i in range(9)
        if f"OrientMatrix{i}" in extrinsic
    ]
    orientation = _matrix_to_quaternion(orientation_matrix) if len(orientation_matrix) == 9 else []

    return {
        "tag": camera.tag,
        "name": serial_label or f"Camera {properties.get('CameraID', '')}".strip(),
        "serial": serial_number,
        "serial_label": serial_label,
        "position": position,
        "orientation": orientation,
        "orientation_matrix": orientation_matrix,
        "properties": properties,
        "attributes": attributes,
        "intrinsic": intrinsic,
        "intrinsic_standard_camera_model": intrinsic_standard,
        "extrinsic": extrinsic,
        "camera_software_filters": software_filters,
        "camera_hardware_filters": hardware_filters,
        "calibration": calibration,
        "color_camera": color_camera or None,
    }


def _parse_mcal_root(root: ET.Element, source_label: str) -> Dict[str, Any]:
    calibration = root.find("Calibration")
    if calibration is None:
        raise ValueError(f"No Calibration node found in {source_label}")

    cameras_elem = calibration.find("Cameras")
    cameras = []
    if cameras_elem is not None:
        cameras = [
            _parse_camera(camera)
            for camera in cameras_elem
            if isinstance(camera.tag, str) and camera.tag == "Camera"
        ]

    calibration_attributes_elem = calibration.find("CalibrationAttributes")
    property_warehouse_elem = root.find("property_warehouse")
    mask_data_elem = root.find("MaskData")
    motive_build_info_elem = root.find("MotiveBuildInfo")

    return {
        "motive_build_info": dict(motive_build_info_elem.attrib) if motive_build_info_elem is not None else {},
        "camera_count": len(cameras),
        "cameras": cameras,
        "calibration_attributes": (
            _element_to_tree(calibration_attributes_elem) if calibration_attributes_elem is not None else {}
        ),
        "property_warehouse": (
            _element_to_tree(property_warehouse_elem) if property_warehouse_elem is not None else {}
        ),
        "mask_data": _element_to_tree(mask_data_elem) if mask_data_elem is not None else {},
        "raw_mcal": {
            "tag": root.tag,
            "attributes": dict(root.attrib),
            "children": _element_to_tree(root),
        },
    }


def parse_mcal_text(text: str, source_label: str = "<mcal text>") -> Dict[str, Any]:
    """Parse Motive .mcal XML text into a rich JSON-friendly dict."""

    return _parse_mcal_root(ET.fromstring(text), source_label)


def parse_mcal_bytes(data: bytes, source_label: str = "<mcal bytes>") -> Dict[str, Any]:
    """Parse raw Motive .mcal bytes into a rich JSON-friendly dict."""

    return _parse_mcal_root(ET.fromstring(data), source_label)


def parse_mcal(path: PathLike) -> Dict[str, Any]:
    """Parse a Motive .mcal file into a rich JSON-friendly dict."""

    path = Path(path)
    return parse_mcal_bytes(path.read_bytes(), str(path))


def normalize_camera_geometry(camera: Dict[str, Any]) -> Dict[str, Any]:
    """Build a strict numeric geometry block for one parsed .mcal camera."""

    serial = camera.get("serial")
    label = f"camera {serial}" if serial is not None else f"camera {camera.get('name', '<unknown>')}"
    if serial is None:
        raise McalValidationError(f"{label} missing required serial")
    try:
        serial_int = int(serial)
    except (TypeError, ValueError) as exc:
        raise McalValidationError(f"{label} has invalid serial: {serial!r}") from exc

    name = str(camera.get("name") or camera.get("serial_label") or f"Camera {serial_int}")
    serial_label = str(camera.get("serial_label") or name)
    prefix_match = re.match(r"([A-Za-z])", serial_label)
    token_prefix = prefix_match.group(1) if prefix_match else None

    position = [float(value) for value in camera.get("position", [])]
    orientation = [float(value) for value in camera.get("orientation", [])]
    orientation_matrix = [float(value) for value in camera.get("orientation_matrix", [])]
    if len(position) != 3:
        raise McalValidationError(f"{label} position must contain 3 values")
    if len(orientation) != 4:
        raise McalValidationError(f"{label} orientation must contain 4 values")
    if len(orientation_matrix) != 9:
        raise McalValidationError(f"{label} orientation_matrix must contain 9 values")

    attributes = camera.get("attributes") or {}
    properties = camera.get("properties") or {}
    intrinsics = camera.get("intrinsic_standard_camera_model") or {}
    if not isinstance(attributes, dict):
        raise McalValidationError(f"{label} attributes must be a mapping")
    if not isinstance(properties, dict):
        raise McalValidationError(f"{label} properties must be a mapping")
    if not isinstance(intrinsics, dict):
        raise McalValidationError(f"{label} IntrinsicStandardCameraModel must be a mapping")

    model = infer_camera_model(serial_int, name=name, token_prefix=token_prefix)
    return {
        "serial": serial_int,
        "name": name,
        "serial_label": serial_label,
        "model": model,
        "camera_id": _optional_int(properties, "CameraID"),
        "enabled": _optional_bool(properties, "Enabled"),
        "enabled_for_recording": _optional_bool(properties, "EnabledForRecording"),
        "frame_rate": _optional_int(properties, "FrameRate"),
        "video_type": _optional_int(properties, "VideoType"),
        "image_width": _required_int(attributes, "ImagerPixelWidth", label),
        "image_height": _required_int(attributes, "ImagerPixelHeight", label),
        "fx": _required_float(intrinsics, "HorizontalFocalLength", label),
        "fy": _required_float(intrinsics, "VerticalFocalLength", label),
        "cx": _required_float(intrinsics, "LensCenterX", label),
        "cy": _required_float(intrinsics, "LensCenterY", label),
        "k1": _required_float(intrinsics, "k1", label),
        "k2": _required_float(intrinsics, "k2", label),
        "k3": _required_float(intrinsics, "k3", label),
        "p1": _required_float(intrinsics, "TangentialX", label),
        "p2": _required_float(intrinsics, "TangentialY", label),
        "position": position,
        "orientation": orientation,
        "orientation_matrix": orientation_matrix,
        "intrinsics_source": "IntrinsicStandardCameraModel",
    }


def normalize_camera_geometries(
    parsed: Dict[str, Any],
    *,
    selected_serials: Optional[Iterable[int]] = None,
) -> Dict[int, Dict[str, Any]]:
    """Return strict numeric camera geometry keyed by serial number."""

    selected: Optional[Set[int]] = None
    if selected_serials is not None:
        selected = {int(serial) for serial in selected_serials}
    geometries: Dict[int, Dict[str, Any]] = {}
    for camera in parsed.get("cameras", []):
        if not isinstance(camera, dict):
            raise McalValidationError(f"Expected camera mapping, got {type(camera).__name__}")
        serial = camera.get("serial")
        if selected is not None and serial is not None and int(serial) not in selected:
            continue
        geometry = normalize_camera_geometry(camera)
        geometries[int(geometry["serial"])] = geometry
    if selected is not None:
        missing = selected.difference(geometries)
        if missing:
            missing_text = ", ".join(str(serial) for serial in sorted(missing))
            raise McalValidationError(f"Selected camera serials missing from .mcal: {missing_text}")
    return geometries
