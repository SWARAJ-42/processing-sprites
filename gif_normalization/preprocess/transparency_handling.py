"""
transparency_handling.py
========================
Replace transparent (alpha) pixels in GIF frames with a solid background colour
that has high contrast against all visible colours in the animation.

Strategy
--------
1. Collect all opaque pixel colours from every frame.
2. Build a small set of candidate background colours (a grid of saturated /
   neutral hues plus pure white / black).
3. Score each candidate by its **minimum perceptual distance** (CIE-76 ΔE in
   L*a*b* space) from all visible colours.
4. Pick the candidate with the highest minimum distance (max-min approach).
5. Replace every transparent pixel across all frames with that colour.
6. Return frames as RGBA (alpha channel kept but fully opaque).

Public API
----------
    handle_transparency(frames) -> (frames, bgcolor_hex, warnings)
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Colour math helpers
# ---------------------------------------------------------------------------

def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb_to_xyz(r: int, g: int, b: int) -> Tuple[float, float, float]:
    rl, gl, bl = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    x = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041
    return x, y, z


def _xyz_to_lab(x: float, y: float, z: float) -> Tuple[float, float, float]:
    # D65 reference white
    x /= 0.95047
    z /= 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    return L, a, b


def _rgb_to_lab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    return _xyz_to_lab(*_rgb_to_xyz(r, g, b))


def _delta_e(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


# ---------------------------------------------------------------------------
# Candidate background colours
# ---------------------------------------------------------------------------

_CANDIDATE_COLORS: List[Tuple[int, int, int]] = [
    (255, 255, 255),  # white
    (0, 0, 0),        # black
    (128, 128, 128),  # mid-grey
    (255, 0, 0),      # red
    (0, 255, 0),      # green
    (0, 0, 255),      # blue
    (255, 255, 0),    # yellow
    (0, 255, 255),    # cyan
    (255, 0, 255),    # magenta
    (255, 128, 0),    # orange
    (0, 128, 255),    # sky-blue
    (128, 0, 255),    # violet
    (0, 64, 0),       # dark-green
    (64, 0, 0),       # dark-red
    (0, 0, 64),       # dark-blue
    (192, 192, 192),  # light-grey
]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _collect_visible_colors(frames: List[Image.Image], max_samples: int = 2000) -> List[Tuple[int, int, int]]:
    """
    Sample opaque pixel colours across all frames.
    Returns a de-duplicated list of (R, G, B) tuples.
    """
    color_set: set = set()

    for frame in frames:
        arr = np.asarray(frame.convert("RGBA"))  # H × W × 4
        mask = arr[:, :, 3] > 128               # opaque pixels
        rgb = arr[mask, :3]

        # Quantise to multiples of 4 to reduce set size
        rgb_q = (rgb // 4) * 4
        for row in rgb_q:
            color_set.add(tuple(int(x) for x in row))
            if len(color_set) >= max_samples:
                break
        if len(color_set) >= max_samples:
            break

    return list(color_set)


def _choose_background(visible: List[Tuple[int, int, int]]) -> Tuple[int, int, int]:
    """
    Pick the candidate colour with the highest minimum ΔE to all visible colours.
    Falls back to white if there are no visible colours.
    """
    if not visible:
        return (255, 255, 255)

    visible_lab = [_rgb_to_lab(*c) for c in visible]

    best_color = _CANDIDATE_COLORS[0]
    best_score = -1.0

    for candidate in _CANDIDATE_COLORS:
        cand_lab = _rgb_to_lab(*candidate)
        min_de = min(_delta_e(cand_lab, vl) for vl in visible_lab)
        if min_de > best_score:
            best_score = min_de
            best_color = candidate

    return best_color


def _replace_transparency(
    frames: List[Image.Image],
    bg: Tuple[int, int, int],
) -> List[Image.Image]:
    """
    Composite every frame over a solid *bg* colour, return RGBA frames.
    """
    out: List[Image.Image] = []
    bg_image = None  # lazily created per-size

    for frame in frames:
        rgba = frame.convert("RGBA")

        if bg_image is None or bg_image.size != rgba.size:
            bg_image = Image.new("RGBA", rgba.size, (*bg, 255))

        composited = Image.alpha_composite(bg_image, rgba)
        out.append(composited)

    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def handle_transparency(
    frames: List[Image.Image],
) -> Tuple[List[Image.Image], str, List[str]]:
    """
    Replace transparent areas with a high-contrast background colour.

    Parameters
    ----------
    frames : list of PIL.Image (RGBA expected)

    Returns
    -------
    out_frames   : composited RGBA frames (fully opaque)
    bgcolor_hex  : '#RRGGBB' string of the chosen background colour
    warnings     : list of warning strings (may be empty)
    """
    warnings: List[str] = []

    # Check whether any frame actually has transparent pixels
    has_alpha = False
    for f in frames:
        arr = np.asarray(f.convert("RGBA"))
        if (arr[:, :, 3] < 255).any():
            has_alpha = True
            break

    if not has_alpha:
        # No transparency – return as-is with a fallback white bgcolor
        return frames, "#ffffff", warnings

    visible = _collect_visible_colors(frames)
    bg_rgb = _choose_background(visible)
    bgcolor_hex = "#{:02x}{:02x}{:02x}".format(*bg_rgb)

    out_frames = _replace_transparency(frames, bg_rgb)

    warnings.append(
        f"transparency_handling: replaced alpha with background colour {bgcolor_hex}."
    )
    return out_frames, bgcolor_hex, warnings
