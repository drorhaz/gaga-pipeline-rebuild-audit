#!/usr/bin/env python3

"""Export exact Motive camera mask images from a calibration JSON snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optitrack_motive.mask import (
    encode_mask_blob,
    iter_decoded_masks,
    native_image_from_mask,
    packed_bytes_to_grid_image,
    save_mask_sheet,
    mask_preview_image,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export exact Motive camera masks from calibration JSON")
    parser.add_argument("--json-path", required=True, help="Calibration JSON produced from Motive .mcal import")
    parser.add_argument("--out-dir", required=True, help="Directory for PNG outputs and manifest.json")
    parser.add_argument(
        "--preview-radius",
        type=int,
        default=2,
        help="Dilate exact mask pixels in the preview images to make sparse masks easier to see",
    )
    args = parser.parse_args()

    json_path = Path(args.json_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(json_path.read_text())
    entries = []

    for mask in iter_decoded_masks(data.get("mask_data", {})):
        grid_image = packed_bytes_to_grid_image(mask.packed_bytes, mask.width, mask.height)
        native_image = native_image_from_mask(mask)
        preview_image = mask_preview_image(native_image, radius=args.preview_radius)

        grid_path = out_dir / f"{mask.serial}_grid_exact.png"
        native_path = out_dir / f"{mask.serial}_sensor_exact.png"
        preview_path = out_dir / f"{mask.serial}_sensor_preview.png"
        grid_image.save(grid_path)
        native_image.save(native_path)
        preview_image.save(preview_path)

        rebuilt = encode_mask_blob(mask)
        nonzero_grid = sum(1 for value in grid_image.getdata() if value)
        entries.append(
            {
                "serial": mask.serial,
                "width": mask.width,
                "height": mask.height,
                "grid": mask.grid,
                "native_width": mask.native_width,
                "native_height": mask.native_height,
                "nonzero_grid_pixels": nonzero_grid,
                "bbox_grid": grid_image.getbbox(),
                "grid_exact_png": str(grid_path.resolve()),
                "sensor_exact_png": str(native_path.resolve()),
                "preview_png": str(preview_path.resolve()),
                "roundtrip_matches_source": rebuilt == bytes.fromhex(next(
                    entry["text"]
                    for entry in data["mask_data"]["Mask"]
                    if entry["attributes"]["Serial"] == mask.serial
                )),
            }
        )

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(entries, indent=2))

    sheet_path = out_dir / "preview_sheet.png"
    save_mask_sheet(entries, sheet_path)

    print(f"Exported {len(entries)} masks")
    print(f"Manifest: {manifest_path.resolve()}")
    print(f"Preview sheet: {sheet_path.resolve()}")


if __name__ == "__main__":
    main()
