"""
NSS ERP — a minimal, dependency-free PDF writer (one or more A4 pages, the standard Helvetica fonts, JPEG images).

Why not a library: nothing may be installed in the authoring sandbox and the Render build wheels for a new dependency are unverified
on Python 3.14/3.15, while a receipt needs only text, lines, rectangles and one logo. This module writes exactly that, correctly:
real xref offsets, Flate-compressed content, the PDF standard-14 fonts (no embedding needed) with WinAnsi encoding, a JPEG passed
through untouched (DCTDecode) and an opacity graphics state for a watermark.

Coordinates are in points with the origin at the TOP-LEFT of the page (y grows downwards), converted to PDF space internally.
Text is Windows-1252: a character outside it is written as "?" (the standard fonts have no Odia / Devanagari glyphs); the rupee sign
is not in that set either, so callers write "Rs.".
"""

import math
import zlib
from datetime import datetime, timezone

from api.services._pdf_metrics import HELVETICA, HELVETICA_BOLD

A4 = (595.28, 841.89)
FONTS = {"regular": ("F1", "Helvetica", HELVETICA), "bold": ("F2", "Helvetica-Bold", HELVETICA_BOLD)}


def encode(text: str) -> bytes:
    """Windows-1252 bytes of *text*; anything the font cannot show becomes '?'. Control characters become spaces."""
    out = bytearray()
    for ch in str(text):
        if ch in "\r\n\t":
            out += b" "
            continue
        try:
            b = ch.encode("cp1252")
        except UnicodeEncodeError:
            b = b"?"
        out += b if b[0] >= 32 else b" "
    return bytes(out)


def text_width(text: str, font: str, size: float) -> float:
    """Width of *text* in points: the font's advance widths (1/1000 em) of the encoded bytes."""
    widths = FONTS[font][2]
    return sum(widths[b - 32] if b >= 32 else 0 for b in encode(text)) * size / 1000.0


def wrap(text: str, font: str, size: float, max_width: float) -> list[str]:
    """Greedy word wrap; a single word longer than the line is split by characters."""
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = word if not current else f"{current} {word}"
            if text_width(candidate, font, size) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            while text_width(word, font, size) > max_width and len(word) > 1:
                cut = len(word)
                while cut > 1 and text_width(word[:cut], font, size) > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines or [""]


def _escape(data: bytes) -> bytes:
    return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _rgb(hex_colour: str) -> str:
    h = hex_colour.lstrip("#")
    return " ".join(_num(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


class Page:
    """Drawing operations for one page. Add them in painting order."""

    def __init__(self, width: float, height: float):
        self.width, self.height = width, height
        self.ops: list[str] = []
        self.images: dict[str, tuple] = {}
        self.uses_opacity = False

    def _y(self, y: float) -> float:
        return self.height - y

    def fill(self, colour: str) -> None:
        self.ops.append(f"{_rgb(colour)} rg")

    def stroke(self, colour: str, width: float = 0.5) -> None:
        self.ops.append(f"{_rgb(colour)} RG {_num(width)} w")

    def rect(self, x: float, y: float, w: float, h: float, *, fill: str | None = None, stroke: str | None = None, line: float = 0.5) -> None:
        """A rectangle whose TOP-LEFT corner is (x, y)."""
        if fill:
            self.fill(fill)
        if stroke:
            self.stroke(stroke, line)
        op = "B" if fill and stroke else ("f" if fill else "S")
        self.ops.append(f"{_num(x)} {_num(self._y(y + h))} {_num(w)} {_num(h)} re {op}")

    def line(self, x1: float, y1: float, x2: float, y2: float, colour: str = "#000000", width: float = 0.5) -> None:
        self.stroke(colour, width)
        self.ops.append(f"{_num(x1)} {_num(self._y(y1))} m {_num(x2)} {_num(self._y(y2))} l S")

    def text(self, x: float, y: float, text: str, *, font: str = "regular", size: float = 10, colour: str = "#000000",
             align: str = "left") -> None:
        """One line of text whose BASELINE is at y; align left / right / center around x."""
        w = text_width(text, font, size)
        if align == "right":
            x -= w
        elif align == "center":
            x -= w / 2
        self.ops.append(f"BT {_rgb(colour)} rg /{FONTS[font][0]} {_num(size)} Tf {_num(x)} {_num(self._y(y))} Td ({_escape(encode(text)).decode('latin-1')}) Tj ET")

    def rotated_text(self, cx: float, cy: float, text: str, *, font: str = "bold", size: float = 80, colour: str = "#CC0000",
                     degrees: float = 35, opacity: float = 0.15) -> None:
        """Text centred on (cx, cy), rotated counter-clockwise by *degrees*, drawn with *opacity* (a watermark)."""
        self.uses_opacity = True
        a = math.radians(degrees)
        c, s = math.cos(a), math.sin(a)
        w = text_width(text, font, size)
        # Td is applied after the rotation matrix, so the text origin is moved back by half its width and a third of its height.
        self.ops.append(
            f"q /GS1 gs BT {_rgb(colour)} rg /{FONTS[font][0]} {_num(size)} Tf {_num(c)} {_num(s)} {_num(-s)} {_num(c)} "
            f"{_num(cx - (w / 2) * c + (size / 3) * s)} {_num(self._y(cy) - (w / 2) * s - (size / 3) * c)} Tm "
            f"({_escape(encode(text)).decode('latin-1')}) Tj ET Q")

    def image(self, name: str, jpeg: bytes, width_px: int, height_px: int, x: float, y: float, w: float, h: float) -> None:
        """Place a JPEG (top-left at x, y; w x h points). The bytes are embedded as they are."""
        self.images[name] = (jpeg, width_px, height_px)
        self.ops.append(f"q {_num(w)} 0 0 {_num(h)} {_num(x)} {_num(self._y(y + h))} cm /{name} Do Q")


class Document:
    def __init__(self, title: str = "", author: str = "", subject: str = ""):
        self.title, self.author, self.subject = title, author, subject
        self.pages: list[Page] = []

    def add_page(self, size: tuple[float, float] = A4) -> Page:
        page = Page(*size)
        self.pages.append(page)
        return page

    def render(self) -> bytes:
        """The finished PDF file."""
        objects: list[bytes] = []                     # 1-based object numbers = index + 1

        def add(body: bytes) -> int:
            objects.append(body)
            return len(objects)

        catalog = add(b"")                            # placeholders, filled below once the numbers are known
        pages_obj = add(b"")
        font_nums = {key: add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} /Encoding /WinAnsiEncoding >>".encode())
                     for key, (_, base, _w) in FONTS.items()}
        gs = add(b"<< /Type /ExtGState /ca 0.15 /CA 0.15 >>")
        page_nums = []
        image_nums: dict[tuple, int] = {}
        for page in self.pages:
            content = zlib.compress("\n".join(page.ops).encode("latin-1"), 9)
            content_num = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(content) + content + b"\nendstream")
            xobjects = []
            for name, (jpeg, wpx, hpx) in page.images.items():
                key = (name, len(jpeg), hash(jpeg))
                if key not in image_nums:
                    image_nums[key] = add(
                        b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB /BitsPerComponent 8 "
                        b"/Filter /DCTDecode /Length %d >>\nstream\n" % (wpx, hpx, len(jpeg)) + jpeg + b"\nendstream")
                xobjects.append(f"/{name} {image_nums[key]} 0 R")
            fonts = " ".join(f"/{FONTS[k][0]} {n} 0 R" for k, n in font_nums.items())
            resources = f"<< /Font << {fonts} >> /ExtGState << /GS1 {gs} 0 R >>" + (f" /XObject << {' '.join(xobjects)} >>" if xobjects else "") + " >>"
            page_nums.append(add(
                f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {_num(page.width)} {_num(page.height)}] "
                f"/Resources {resources} /Contents {content_num} 0 R >>".encode()))
        now = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
        info = add(("<< /Title (%s) /Author (%s) /Subject (%s) /Creator (NSS ERP) /Producer (NSS ERP) /CreationDate (%s) >>" % (
            _escape(encode(self.title)).decode("latin-1"), _escape(encode(self.author)).decode("latin-1"),
            _escape(encode(self.subject)).decode("latin-1"), now)).encode("latin-1"))
        objects[catalog - 1] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode()
        objects[pages_obj - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{n} 0 R' for n in page_nums)}] /Count {len(page_nums)} >>".encode()

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)
