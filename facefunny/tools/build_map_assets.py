"""Rebuild the Mirage map assets from a radar image (developer tool).

Reads  assets/source/mirage_radar_source.webp  and writes:
  assets/mirage_texture.png  - the re-textured map in the app's dark style
  assets/mirage_mask.txt     - walkability grid used by the simulation

Needs Pillow and numpy (see requirements-dev.txt); the app itself does not.
Usage:  python tools/build_map_assets.py [source_image]
"""

from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
DEFAULT_SOURCE = os.path.join(ASSETS, "source", "mirage_radar_source.webp")

# Square crop (in source pixels) that removes the A-P / 1-17 grid labels.
# It is expressed relative to a 250 px source and scaled for other sizes.
CROP_250 = (14, 14, 236, 236)
FLOOR_THRESHOLD = 40   # max RGB channel; the background is near-black
TEXTURE_SIZE = 1024
GRID_SIZE = 160


def _to_bool(img: Image.Image, threshold: int = 128) -> np.ndarray:
    return np.asarray(img, dtype=np.uint8) >= threshold


def _morph(mask: np.ndarray, size: int, grow: bool) -> np.ndarray:
    img = Image.fromarray(mask.astype(np.uint8) * 255)
    filt = ImageFilter.MaxFilter(size) if grow else ImageFilter.MinFilter(size)
    return _to_bool(img.filter(filt))


def build(source: str) -> None:
    src = Image.open(source).convert("RGB")
    scale = src.width / 250.0
    crop = tuple(int(round(v * scale)) for v in CROP_250)
    src = src.crop(crop)

    # 1. Floor mask at source resolution, cleaned from specks and grid lines.
    rgb = np.asarray(src, dtype=np.int16)
    floor = rgb.max(axis=2) > FLOOR_THRESHOLD
    floor = _morph(_morph(floor, 3, grow=False), 3, grow=True)   # open
    floor = _morph(_morph(floor, 3, grow=True), 3, grow=False)   # close tiny holes

    # 2. Smooth upscale of the mask.
    m = Image.fromarray(floor.astype(np.uint8) * 255).resize((TEXTURE_SIZE, TEXTURE_SIZE), Image.LANCZOS)
    m = m.filter(ImageFilter.GaussianBlur(3))
    mask_hi = _to_bool(m)

    # 3. New texture: dark navy palette driven by the original luminance,
    #    with a hint of the original hue and the fine detail (crates, steps).
    hi = src.resize((TEXTURE_SIZE, TEXTURE_SIZE), Image.LANCZOS)
    orig = np.asarray(hi, dtype=np.float32)
    lum = np.asarray(hi.convert("L"), dtype=np.float32)
    blur = np.asarray(hi.convert("L").filter(ImageFilter.GaussianBlur(10)), dtype=np.float32)
    detail = np.clip(lum - blur, -40, 60)

    t = np.clip((lum - 45.0) / 75.0, 0.0, 1.0)[..., None]
    dark = np.array([20, 26, 38], dtype=np.float32)
    light = np.array([50, 62, 86], dtype=np.float32)
    color = dark + (light - dark) * t
    color = color * 0.82 + orig * 0.18 * 0.75             # keep a little of the original hue
    color += detail[..., None] * np.array([0.55, 0.65, 0.85], dtype=np.float32)

    # Fine tactical grid baked into the floor.
    yy, xx = np.mgrid[0:TEXTURE_SIZE, 0:TEXTURE_SIZE]
    fine = ((xx % 32) == 0) | ((yy % 32) == 0)
    color[fine] += 6

    inner_edge = mask_hi & ~_morph(mask_hi, 5, grow=False)
    color[inner_edge] = color[inner_edge] * 0.3 + np.array([84, 104, 146]) * 0.7

    alpha = np.where(mask_hi, 255, 0).astype(np.float32)

    # Outer glow.
    glow_mask = Image.fromarray(mask_hi.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(9))
    glow = np.asarray(glow_mask.filter(ImageFilter.GaussianBlur(7)), dtype=np.float32) / 255.0
    outside = ~mask_hi
    glow_rgb = np.array([90, 140, 255], dtype=np.float32)
    color[outside] = glow_rgb
    alpha[outside] = glow[outside] * 70

    out = np.dstack([np.clip(color, 0, 255), np.clip(alpha, 0, 255)]).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(os.path.join(ASSETS, "mirage_texture.png"), optimize=True)

    # 4. Walkability grid for the simulation.
    g = Image.fromarray(mask_hi.astype(np.uint8) * 255).resize((GRID_SIZE, GRID_SIZE), Image.BOX)
    grid = np.asarray(g) >= 100  # generous: keeps narrow doorways passable
    with open(os.path.join(ASSETS, "mirage_mask.txt"), "w", encoding="ascii") as fh:
        fh.write(f"{GRID_SIZE} {GRID_SIZE}\n")
        for row in grid:
            fh.write("".join("1" if v else "0" for v in row) + "\n")
    print(f"Wrote texture and {GRID_SIZE}x{GRID_SIZE} mask ({grid.mean() * 100:.1f}% walkable)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE)
