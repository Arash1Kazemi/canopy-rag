"""Write a PNG image with the standard library only (zlib), so rendering a scanned page needs no Pillow.

A PNG file is a signature followed by chunks: IHDR (size and colour type), IDAT (the pixel rows, each row starting
with a filter byte 0, compressed with zlib), and IEND. Each chunk ends with a CRC-32 of its type and data.
"""
import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
COLOUR_TYPE = {1: 0, 3: 2, 4: 6}   # channels -> PNG colour type: grey, RGB, RGBA


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(width, height, pixels, channels=3, stride=None):
    """`pixels` are rows of 8-bit samples (RGB order for 3 channels), `stride` bytes apart."""
    if channels not in COLOUR_TYPE:
        raise ValueError(f"a PNG here has 1, 3 or 4 channels, not {channels}")
    row = width * channels
    stride = stride or row
    data = bytes(pixels)
    if len(data) < stride * (height - 1) + row:
        raise ValueError("the pixel buffer is smaller than width x height")
    raw = b"".join(b"\x00" + data[y * stride:y * stride + row] for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, COLOUR_TYPE[channels], 0, 0, 0)
    return SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 6)) + _chunk(b"IEND", b"")
