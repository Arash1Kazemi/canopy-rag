"""Write an image-only PDF with the standard library only (zlib), so making a "scanned" page needs no Pillow.

Each page holds one picture and nothing else: no font and no text objects. A PDF reader therefore finds no text
layer, exactly as with a scanner. scripts/make_real_files.py uses it to turn D19 into an image-only PDF, and the tests
use it to build a PDF that mixes text pages and scanned pages.

A PDF file is a header, numbered objects, a cross-reference table (the byte offset of each object) and a trailer.
Each page needs three objects: the page itself, its content stream ("draw image Im1 over the whole page"), and the
image, whose pixel rows are compressed with zlib (the PDF filter FlateDecode). Unlike a PNG, the rows have no
filter byte in front. The output has no dates in it, so the same pixels always give the same bytes.
"""
import zlib
from dataclasses import dataclass

COLOUR_SPACE = {1: "/DeviceGray", 3: "/DeviceRGB"}   # channels -> PDF colour space
HEADER = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"           # the second line tells tools the file is binary


@dataclass(frozen=True)
class PageImage:
    """One page as a picture. `pixels` are rows of 8-bit samples, top row first, `stride` bytes apart
    (0 means width x channels). The page size is in points (1/72 inch); 0 means one point per pixel."""
    width: int
    height: int
    pixels: bytes
    channels: int = 1
    stride: int = 0
    width_pt: float = 0
    height_pt: float = 0


def _number(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _image_object(page):
    if page.channels not in COLOUR_SPACE:
        raise ValueError(f"an image page here has 1 (grey) or 3 (RGB) channels, not {page.channels}")
    row = page.width * page.channels
    stride = page.stride or row
    data = bytes(page.pixels)
    if page.width <= 0 or page.height <= 0 or len(data) < stride * (page.height - 1) + row:
        raise ValueError("the pixel buffer is smaller than width x height")
    rows = b"".join(data[y * stride:y * stride + row] for y in range(page.height))
    packed = zlib.compress(rows, 9)
    head = (f"<< /Type /XObject /Subtype /Image /Width {page.width} /Height {page.height} "
            f"/ColorSpace {COLOUR_SPACE[page.channels]} /BitsPerComponent 8 /Filter /FlateDecode /Length {len(packed)} >>")
    return head.encode() + b"\nstream\n" + packed + b"\nendstream"


def encode_image_pdf(pages):
    """The bytes of a PDF with one image per page and no text layer."""
    pages = list(pages)
    if not pages:
        raise ValueError("a PDF needs at least one page")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None]   # objects 1 and 2; 2 is filled in below
    kids = []
    for page in pages:
        page_no = len(objects) + 1
        content_no, image_no = page_no + 1, page_no + 2
        w = _number(page.width_pt or page.width)
        h = _number(page.height_pt or page.height)
        draw = f"q {w} 0 0 {h} 0 0 cm /Im1 Do Q".encode()
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] "
                       f"/Resources << /XObject << /Im1 {image_no} 0 R >> >> /Contents {content_no} 0 R >>".encode())
        objects.append(f"<< /Length {len(draw)} >>".encode() + b"\nstream\n" + draw + b"\nendstream")
        objects.append(_image_object(page))
        kids.append(f"{page_no} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()

    out, offsets = bytearray(HEADER), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
