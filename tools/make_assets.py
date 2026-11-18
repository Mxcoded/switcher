"""Generate the Switcher icon and header mark from the Afriwave brand board.

The board (``assets/brand_board.png``) holds the horizontal lock-up, the
dark-green mark tile and the palette swatches. Only the mark is used:

* ``assets/switcher.ico`` - rounded dark-green tile with the gold ring and ivory
  wave, used by the exe, shortcut, installer and window icon. Sizes up to
  32 px are redrawn from the brand geometry so the ring stays legible; larger
  sizes are resampled from the original artwork.
* ``assets/logo_mark.png`` - the ring and wave with a transparent background,
  so it sits cleanly on the navy window header.

Run after changing the source artwork::

    .\\.venv\\Scripts\\python.exe tools\\make_assets.py

Pillow is a build-time tool only; the application never imports it.
"""

from __future__ import annotations

import argparse
import io
import logging
import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

LOGGER = logging.getLogger("make_assets")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "assets" / "brand_board.png"
DEFAULT_OUT = ROOT / "assets"

# The mark tile on the brand board, and the mark inside it.
TILE_BOX = (760, 0, 1200, 520)
MARK_BOX = (116, 156, 324, 364)  # 208 px square, a little padding around the art
TILE_MARK_CENTER = (220, 260)
ICON_CROP = 300  # square crop inside the tile; the mark fills about 65%
BACKGROUND = (20, 33, 29)
GOLD = (154, 118, 64, 255)
IVORY = (246, 242, 234, 255)
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
DRAWN_MAX = 32
ICON_SUPERSAMPLE = 1024
HEADER_SIZE = 48


def _load_board(path: Path) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"Brand board not found: {path}")
    return Image.open(path).convert("RGB")


def _icon_tile(board: Image.Image) -> Image.Image:
    """Return the rounded dark tile used for the larger icon sizes."""
    half = ICON_CROP // 2
    left = TILE_BOX[0] + TILE_MARK_CENTER[0] - half
    top = TILE_BOX[1] + TILE_MARK_CENTER[1] - half
    square = board.crop((left, top, left + ICON_CROP, top + ICON_CROP))
    base = square.resize(
        (ICON_SUPERSAMPLE, ICON_SUPERSAMPLE), Image.Resampling.LANCZOS
    ).convert("RGBA")

    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, ICON_SUPERSAMPLE - 1, ICON_SUPERSAMPLE - 1),
        radius=int(ICON_SUPERSAMPLE * 0.2),
        fill=255,
    )
    base.putalpha(mask)
    return base


def _transparent_mark(board: Image.Image, size: int = HEADER_SIZE) -> Image.Image:
    """Key the dark tile out, keeping the gold ring and ivory wave."""
    left = TILE_BOX[0] + MARK_BOX[0]
    top = TILE_BOX[1] + MARK_BOX[1]
    tile = board.crop((left, top, left + 208, top + 208)).convert("RGB")
    out = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    source = tile.load()
    target = out.load()
    low, high = 12.0, 70.0
    for y in range(tile.height):
        for x in range(tile.width):
            red, green, blue = source[x, y]
            distance = max(
                abs(red - BACKGROUND[0]),
                abs(green - BACKGROUND[1]),
                abs(blue - BACKGROUND[2]),
            )
            alpha = max(0.0, min(1.0, (distance - low) / (high - low)))
            target[x, y] = (red, green, blue, int(round(alpha * 255)))
    return out.resize((size, size), Image.Resampling.LANCZOS)


def _drawn_icon(size: int) -> Image.Image:
    """Draw the mark from primitives for the very small icon sizes.

    The original strokes are too fine to survive below about 40 px, so the
    small sizes use a slightly bolder ring and wave while keeping the layout.
    """
    scale = 16
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, canvas - 1, canvas - 1),
        radius=int(canvas * 0.2),
        fill=BACKGROUND,
    )

    centre = canvas / 2
    radius = canvas * 0.405
    draw.ellipse(
        (centre - radius, centre - radius, centre + radius, centre + radius),
        outline=GOLD,
        width=max(1, round(canvas * 0.030)),
    )

    amplitude = canvas * 0.105
    baseline = centre + canvas * 0.030
    span = canvas * 0.660
    start = centre - span / 2
    points = []
    for step in range(121):
        ratio = step / 120
        points.append(
            (
                start + span * ratio,
                baseline - amplitude * math.sin(ratio * 2 * math.pi),
            )
        )
    draw.line(
        points,
        fill=IVORY,
        width=max(1, round(canvas * 0.045)),
        joint="curve",
    )

    dot = max(1, round(canvas * 0.034))
    for point in (points[4], points[-5]):
        draw.ellipse(
            (point[0] - dot, point[1] - dot, point[0] + dot, point[1] + dot),
            fill=GOLD,
        )

    if size >= 24:
        top = centre - radius + canvas * 0.02
        bob = baseline - amplitude - canvas * 0.035
        draw.line(
            [(centre, top), (centre, bob)],
            fill=GOLD,
            width=max(1, round(canvas * 0.016)),
        )
        bob_dot = max(1, round(canvas * 0.032))
        draw.ellipse(
            (centre - bob_dot, bob - bob_dot, centre + bob_dot, bob + bob_dot),
            fill=GOLD,
        )

    return image.resize((size, size), Image.Resampling.LANCZOS)


def _icon_frames(tile: Image.Image) -> list[tuple[int, bytes]]:
    """Render every icon size, using the drawn mark where pixels get scarce."""
    frames: list[tuple[int, bytes]] = []
    for width, height in ICON_SIZES:
        if width <= DRAWN_MAX:
            frame = _drawn_icon(width)
        else:
            frame = tile.resize((width, height), Image.Resampling.LANCZOS)
            frame = frame.filter(
                ImageFilter.UnsharpMask(radius=0.8, percent=60, threshold=1)
            )
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG")
        frames.append((width, buffer.getvalue()))
    return frames


def _write_ico(path: Path, frames: list[tuple[int, bytes]]) -> None:
    """Write a PNG-compressed ICO (Windows Vista and later)."""
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = b""
    payload = b""
    offset = 6 + 16 * len(frames)
    for width, data in frames:
        dimension = 0 if width >= 256 else width
        entries += struct.pack(
            "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset
        )
        offset += len(data)
        payload += data
    path.write_bytes(header + entries + payload)


def build(source: Path, out_dir: Path) -> tuple[Path, Path]:
    """Write the icon and header mark, returning both paths."""
    board = _load_board(source)
    out_dir.mkdir(parents=True, exist_ok=True)

    icon_path = out_dir / "switcher.ico"
    _write_ico(icon_path, _icon_frames(_icon_tile(board)))

    mark_path = out_dir / "logo_mark.png"
    _transparent_mark(board).save(mark_path, format="PNG")

    LOGGER.info("Wrote %s and %s", icon_path, mark_path)
    return icon_path, mark_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    build(args.source, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
