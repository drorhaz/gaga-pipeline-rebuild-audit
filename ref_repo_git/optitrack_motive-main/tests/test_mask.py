from __future__ import annotations

import json
import unittest
from pathlib import Path

from optitrack_motive.mask import (
    DecodedMaskBlob,
    decode_mask_blob,
    encode_mask_blob,
    iter_decoded_masks,
    native_image_from_mask,
    packed_bytes_to_grid_image,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_JSON = REPO_ROOT / "optitrack_motive" / "calib" / "cork_260316_1328.json"


class MaskCodecTests(unittest.TestCase):
    def test_synthetic_mask_roundtrips_and_unpacks(self) -> None:
        original = DecodedMaskBlob(
            serial="SYNTH",
            width=8,
            height=2,
            grid=4,
            packed_bytes=bytes([0b00011000, 0b11110000]),
        )

        blob = encode_mask_blob(original)
        decoded = decode_mask_blob("SYNTH", blob)
        grid_image = packed_bytes_to_grid_image(decoded.packed_bytes, decoded.width, decoded.height)
        native_image = native_image_from_mask(decoded)

        self.assertEqual(decoded, original)
        self.assertEqual(grid_image.size, (8, 2))
        self.assertEqual(native_image.size, (32, 8))
        self.assertEqual(grid_image.getpixel((3, 0)), 255)
        self.assertEqual(grid_image.getpixel((4, 0)), 255)
        self.assertEqual(grid_image.getpixel((0, 0)), 0)
        self.assertEqual(grid_image.getpixel((4, 1)), 255)
        self.assertEqual(grid_image.getpixel((7, 1)), 255)

    def test_real_calibration_masks_roundtrip_exactly(self) -> None:
        data = json.loads(CALIBRATION_JSON.read_text())
        source_by_serial = {
            entry["attributes"]["Serial"]: entry["text"]
            for entry in data["mask_data"]["Mask"]
        }

        decoded_masks = list(iter_decoded_masks(data["mask_data"]))
        self.assertEqual(len(decoded_masks), 13)

        for mask in decoded_masks:
            rebuilt = encode_mask_blob(mask).hex()
            self.assertEqual(rebuilt, source_by_serial[mask.serial].lower())


if __name__ == "__main__":
    unittest.main()
