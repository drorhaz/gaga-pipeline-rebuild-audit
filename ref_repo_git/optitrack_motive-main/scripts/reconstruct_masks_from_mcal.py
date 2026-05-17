#!/usr/bin/env python3

"""Heuristically reconstruct Motive camera masks from an .mcal file.

This is not a byte-for-byte verified decoder for Motive's private MaskData
encoding. It reconstructs plausible mask silhouettes by:
1. Reading the known width/height/grid header from each <Mask> blob.
2. Interpreting the body as row-ordered sparse edge writes.
3. Rendering both the sparse edge map and a row-filled variant.

The output is useful for inspection and human comparison against Motive, but it
should be treated as a reconstruction candidate rather than a guaranteed exact
decode.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from binascii import unhexlify
from pathlib import Path
from typing import Dict, List

from PIL import Image


def _bits_to_image(data: bytes, width: int, height: int) -> Image.Image:
    row_bytes = width // 8
    img = Image.new("L", (width, height), 0)
    pixels = img.load()
    for y in range(height):
        row = data[y * row_bytes:(y + 1) * row_bytes]
        for x in range(width):
            if row[x // 8] & (1 << (x % 8)):
                pixels[x, y] = 255
    return img


def _choose_record_start(payload: bytes) -> int:
    # The non-empty masks we've inspected start one byte earlier when a leading
    # padding byte is present before the first 16-bit pattern.
    return 43 if len(payload) > 44 and payload[43] == 0 and payload[44] != 0 else 44


def _decode_sparse_edges(payload: bytes, width: int, height: int) -> bytes:
    row_bytes = width // 8
    raw = bytearray((width * height) // 8)
    start = _choose_record_start(payload)
    pos = start
    row = 0

    while pos + 6 <= len(payload) - 4 and row < height:
        pattern = int.from_bytes(payload[pos:pos + 2], byteorder="little")
        x_offset = int.from_bytes(payload[pos + 2:pos + 6], byteorder="little") >> 8
        pattern_bytes = pattern.to_bytes(2, byteorder="little")

        if 0 <= x_offset < row_bytes and x_offset + 2 <= row_bytes:
            idx = row * row_bytes + x_offset
            raw[idx:idx + 2] = bytes(a | b for a, b in zip(raw[idx:idx + 2], pattern_bytes))
            row += 1

        pos += 6

    return bytes(raw)


def _fill_rows(edge_img: Image.Image) -> Image.Image:
    filled = Image.new("L", edge_img.size, 0)
    src = edge_img.load()
    dst = filled.load()
    for y in range(edge_img.height):
        xs = [x for x in range(edge_img.width) if src[x, y]]
        if not xs:
            continue
        for x in range(min(xs), max(xs) + 1):
            dst[x, y] = 255
    return filled


def reconstruct_masks(mcal_path: Path, out_dir: Path) -> List[Dict[str, object]]:
    root = ET.fromstring(mcal_path.read_text(encoding="utf-16"))
    mask_data = root.find("MaskData")
    if mask_data is None:
        raise ValueError(f"No MaskData section found in {mcal_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: List[Dict[str, object]] = []

    for mask in mask_data:
        serial = mask.attrib.get("Serial", "unknown")
        payload_hex = (mask.text or "").strip()
        payload = unhexlify(payload_hex)

        width = int.from_bytes(payload[2:6], byteorder="little")
        height = int.from_bytes(payload[6:10], byteorder="little")
        grid = int.from_bytes(payload[10:14], byteorder="little")

        sparse_bytes = _decode_sparse_edges(payload, width, height)
        sparse_img = _bits_to_image(sparse_bytes, width, height)
        filled_img = _fill_rows(sparse_img)

        sparse_path = out_dir / f"{serial}_grid_sparse.png"
        filled_path = out_dir / f"{serial}_grid_filled.png"
        sparse_img.save(sparse_path)
        filled_img.save(filled_path)

        sensor_sparse = sparse_img.resize((width * grid, height * grid), Image.Resampling.NEAREST)
        sensor_filled = filled_img.resize((width * grid, height * grid), Image.Resampling.NEAREST)

        sensor_sparse_path = out_dir / f"{serial}_sensor_sparse.png"
        sensor_filled_path = out_dir / f"{serial}_sensor_filled.png"
        sensor_sparse.save(sensor_sparse_path)
        sensor_filled.save(sensor_filled_path)

        manifest.append(
            {
                "serial": serial,
                "grid_width": width,
                "grid_height": height,
                "grid": grid,
                "record_start": _choose_record_start(payload),
                "sparse_grid_png": str(sparse_path),
                "filled_grid_png": str(filled_path),
                "sparse_sensor_png": str(sensor_sparse_path),
                "filled_sensor_png": str(sensor_filled_path),
            }
        )

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Heuristically reconstruct camera masks from a Motive .mcal file")
    parser.add_argument("--mcal-path", required=True, help="Path to System Calibration.mcal or another .mcal export")
    parser.add_argument("--out-dir", required=True, help="Directory for reconstructed mask PNGs")
    args = parser.parse_args()

    manifest = reconstruct_masks(Path(args.mcal_path), Path(args.out_dir))
    print(f"Reconstructed {len(manifest)} mask candidates")
    print(f"Manifest: {Path(args.out_dir) / 'manifest.json'}")


if __name__ == "__main__":
    main()
