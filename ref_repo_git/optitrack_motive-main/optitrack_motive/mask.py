"""Exact decoding helpers for Motive camera mask blobs stored in calibration JSON."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from PIL import Image, ImageDraw, ImageFilter


@dataclass(frozen=True)
class DecodedMaskBlob:
    serial: str
    width: int
    height: int
    grid: int
    packed_bytes: bytes
    version: int = 1
    terminator: int = 0xBEEF

    @property
    def native_width(self) -> int:
        return self.width * self.grid

    @property
    def native_height(self) -> int:
        return self.height * self.grid


def _parse_mask_entries(mask_data: Dict[str, object]) -> List[Dict[str, object]]:
    entries = mask_data.get("Mask", [])
    if isinstance(entries, dict):
        return [entries]
    if isinstance(entries, list):
        return entries
    return []


def iter_decoded_masks(mask_data: Dict[str, object]) -> Iterable[DecodedMaskBlob]:
    for entry in _parse_mask_entries(mask_data):
        attributes = entry.get("attributes", {})
        payload_hex = entry.get("text", "")
        if not isinstance(attributes, dict) or not isinstance(payload_hex, str):
            continue
        serial = str(attributes.get("Serial", "unknown"))
        yield decode_mask_blob(serial, bytes.fromhex(payload_hex))


def decode_mask_blob(serial: str, blob: bytes) -> DecodedMaskBlob:
    if len(blob) < 26:
        raise ValueError(f"{serial}: mask blob too short ({len(blob)} bytes)")

    width = int.from_bytes(blob[2:6], byteorder="little")
    height = int.from_bytes(blob[6:10], byteorder="little")
    grid = int.from_bytes(blob[10:14], byteorder="little")
    inner_len = int.from_bytes(blob[18:22], byteorder="little")
    if inner_len != len(blob) - 22:
        raise ValueError(f"{serial}: outer payload length {inner_len} != actual {len(blob) - 22}")

    pos = 22
    version = blob[pos]
    pos += 1

    inner_width = int.from_bytes(blob[pos:pos + 4], byteorder="little")
    pos += 4
    inner_height = int.from_bytes(blob[pos:pos + 4], byteorder="little")
    pos += 4
    inner_grid = int.from_bytes(blob[pos:pos + 4], byteorder="little")
    pos += 4
    total_bytes = int.from_bytes(blob[pos:pos + 4], byteorder="little")
    pos += 4

    if (inner_width, inner_height, inner_grid) != (width, height, grid):
        raise ValueError(
            f"{serial}: inner header {(inner_width, inner_height, inner_grid)} != outer {(width, height, grid)}"
        )

    packed = bytearray()
    while len(packed) < total_bytes:
        if pos >= len(blob):
            raise ValueError(f"{serial}: truncated RLE payload")
        token = blob[pos]
        pos += 1
        if token in (0x00, 0xFF):
            count = int.from_bytes(blob[pos:pos + 4], byteorder="little")
            pos += 4
            packed.extend([token] * count)
        else:
            packed.append(token)

    terminator = int.from_bytes(blob[pos:pos + 4], byteorder="little")
    pos += 4

    if pos != len(blob):
        raise ValueError(f"{serial}: trailing bytes remain after terminator ({len(blob) - pos})")
    if terminator != 0xBEEF:
        raise ValueError(f"{serial}: unexpected terminator {terminator:#x}")

    return DecodedMaskBlob(
        serial=serial,
        width=width,
        height=height,
        grid=grid,
        packed_bytes=bytes(packed),
        version=version,
        terminator=terminator,
    )


def encode_mask_blob(mask: DecodedMaskBlob) -> bytes:
    outer = bytearray(22)
    outer[0] = 0x02
    outer[1] = 0x01
    outer[2:6] = mask.width.to_bytes(4, byteorder="little")
    outer[6:10] = mask.height.to_bytes(4, byteorder="little")
    outer[10:14] = mask.grid.to_bytes(4, byteorder="little")
    outer[14:18] = mask.grid.to_bytes(4, byteorder="little")

    inner = bytearray([mask.version])
    inner += mask.width.to_bytes(4, byteorder="little")
    inner += mask.height.to_bytes(4, byteorder="little")
    inner += mask.grid.to_bytes(4, byteorder="little")
    inner += len(mask.packed_bytes).to_bytes(4, byteorder="little")

    pos = 0
    packed = mask.packed_bytes
    while pos < len(packed):
        token = packed[pos]
        if token in (0x00, 0xFF):
            run_end = pos + 1
            while run_end < len(packed) and packed[run_end] == token:
                run_end += 1
            inner.append(token)
            inner += (run_end - pos).to_bytes(4, byteorder="little")
            pos = run_end
            continue
        inner.append(token)
        pos += 1

    inner += mask.terminator.to_bytes(4, byteorder="little")
    outer[18:22] = len(inner).to_bytes(4, byteorder="little")
    return bytes(outer) + bytes(inner)


def packed_bytes_to_grid_image(packed_bytes: bytes, width: int, height: int) -> Image.Image:
    row_bytes = (width + 7) // 8
    if len(packed_bytes) != row_bytes * height:
        raise ValueError(f"Packed length {len(packed_bytes)} does not match {width}x{height}")

    image = Image.new("L", (width, height), 0)
    pixels = image.load()
    for y in range(height):
        row = packed_bytes[y * row_bytes:(y + 1) * row_bytes]
        for x in range(width):
            if row[x // 8] & (1 << (x % 8)):
                pixels[x, y] = 255
    return image


def native_image_from_mask(mask: DecodedMaskBlob) -> Image.Image:
    grid_image = packed_bytes_to_grid_image(mask.packed_bytes, mask.width, mask.height)
    return grid_image.resize((mask.native_width, mask.native_height), Image.Resampling.NEAREST)


def dilate_binary_image(image: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return image.copy()
    size = radius * 2 + 1
    return image.filter(ImageFilter.MaxFilter(size=size))


def mask_preview_image(native_mask: Image.Image, radius: int = 1) -> Image.Image:
    expanded = dilate_binary_image(native_mask, radius=radius).convert("RGB")
    src = expanded.load()
    preview = Image.new("RGB", expanded.size, (28, 28, 28))
    dst = preview.load()
    for y in range(expanded.height):
        for x in range(expanded.width):
            if src[x, y][0]:
                dst[x, y] = (220, 48, 48)
    return preview


def save_mask_sheet(entries: Sequence[Dict[str, object]], out_path: Path) -> None:
    if not entries:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)

    thumbs: List[Image.Image] = []
    for entry in entries:
        preview = Image.open(str(entry["preview_png"])).convert("RGB")
        serial = str(entry["serial"])
        labeled = Image.new("RGB", (preview.width, preview.height + 28), (18, 18, 18))
        labeled.paste(preview, (0, 28))
        label = Image.new("RGB", (preview.width, 28), (18, 18, 18))
        labeled.paste(label, (0, 0))
        draw = ImageDraw.Draw(labeled)
        draw.text((8, 6), serial, fill=(255, 255, 255))
        thumbs.append(labeled)

    cols = 3
    margin = 12
    thumb_w = max(image.width for image in thumbs)
    thumb_h = max(image.height for image in thumbs)
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new(
        "RGB",
        (cols * thumb_w + (cols + 1) * margin, rows * thumb_h + (rows + 1) * margin),
        (234, 234, 234),
    )
    for index, thumb in enumerate(thumbs):
        x = margin + (index % cols) * thumb_w
        y = margin + (index // cols) * thumb_h
        sheet.paste(thumb, (x, y))
    sheet.save(out_path)
