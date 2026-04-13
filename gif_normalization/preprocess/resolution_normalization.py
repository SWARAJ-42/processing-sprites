"""
resolution_normalization.py
============================
Pad and scale GIF frames so that:
  • width  % 32 == 0
  • height % 32 == 0
  • min(width, height) >= 512

Rules
-----
* NO cropping – only padding then scaling.
* Padding is symmetric and uses the detected background colour.
* Scaling uses Lanczos (best quality).
* Aspect ratio is preserved throughout.

Public API
----------
    normalize_resolution(frames, bgcolor_hex) -> (frames, new_w, new_h, warnings)
"""

from __future__ import annotations

import math
from typing import List, Tuple

from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ceil32(n: int) -> int:
    """Round up *n* to the nearest multiple of 32."""
    return math.ceil(n / 32) * 32


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert '#rrggbb' or 'rrggbb' to (R, G, B)."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _detect_bg_from_borders(frame: Image.Image) -> Tuple[int, int, int]:
    """
    Heuristic: sample the outermost pixel ring of the first frame and return
    the most common (R, G, B).  Used when the caller supplies no bgcolor.
    """
    import collections

    arr = frame.convert("RGBA")
    w, h = arr.size
    pixels = []

    for x in range(w):
        pixels.append(arr.getpixel((x, 0))[:3])
        pixels.append(arr.getpixel((x, h - 1))[:3])
    for y in range(1, h - 1):
        pixels.append(arr.getpixel((0, y))[:3])
        pixels.append(arr.getpixel((w - 1, y))[:3])

    counter = collections.Counter(pixels)
    return counter.most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Step 1 – Padding to multiples of 32
# ---------------------------------------------------------------------------

def _pad_to_32(
    frames: List[Image.Image],
    bg: Tuple[int, int, int],
) -> Tuple[List[Image.Image], int, int]:
    """
    Symmetrically pad every frame to (ceil32(w), ceil32(h)).
    Returns padded frames and the new (width, height).
    """
    w, h = frames[0].size
    new_w = _ceil32(w)
    new_h = _ceil32(h)

    if new_w == w and new_h == h:
        return frames, w, h

    pad_left   = (new_w - w) // 2
    pad_right  = new_w - w - pad_left
    pad_top    = (new_h - h) // 2
    pad_bottom = new_h - h - pad_top

    out: List[Image.Image] = []
    bg_rgba = (*bg, 255)

    for frame in frames:
        canvas = Image.new("RGBA", (new_w, new_h), bg_rgba)
        canvas.paste(frame.convert("RGBA"), (pad_left, pad_top))
        out.append(canvas)

    return out, new_w, new_h

def _pad_to_square(
    frames: List[Image.Image],
    bg: Tuple[int, int, int],
) -> Tuple[List[Image.Image], int, int]:
    """
    Symmetrically pad frames so width == height (square canvas).
    
    IMPORTANT:
    - Uses background colour for padding
    - Does NOT distort content
    """
    w, h = frames[0].size
    size = max(w, h)

    if w == h:
        return frames, w, h

    pad_left = (size - w) // 2
    pad_top  = (size - h) // 2

    out: List[Image.Image] = []
    bg_rgba = (*bg, 255)

    for frame in frames:
        canvas = Image.new("RGBA", (size, size), bg_rgba)
        canvas.paste(frame.convert("RGBA"), (pad_left, pad_top))
        out.append(canvas)

    return out, size, size

def _resize_to_768(
    frames: List[Image.Image],
    w: int,
    h: int,
) -> Tuple[List[Image.Image], int, int]:
    """
    Resize frames to 768x768 using NEAREST to preserve pixel art.
    
    NOTE:
    - No interpolation → no pixel tearing
    - Square input ensures uniform scaling
    """
    if w == 768 and h == 768:
        return frames, w, h

    out = [f.resize((768, 768), Image.NEAREST) for f in frames]
    return out, 768, 768

# ---------------------------------------------------------------------------
# Step 2 – Scale so min-side >= 512
# ---------------------------------------------------------------------------

def _scale_to_min512(
    frames: List[Image.Image],
    w: int,
    h: int,
) -> Tuple[List[Image.Image], int, int, bool]:
    """
    If min(w, h) < 512, upscale uniformly (NEAREST for pixel-perfect scaling) so that
    min-side == 512 and both dimensions remain multiples of 32.

    NOTE:
    - Changed from Lanczos → NEAREST to prevent pixel tearing/blurring.
    - This preserves sharp pixel-art blocks exactly.

    If already large enough, return unchanged.

    Returns (frames, new_w, new_h, was_scaled).
    """
    min_side = min(w, h)

    if min_side >= 512:
        return frames, w, h, False

    scale = 512.0 / min_side
    raw_w = round(w * scale)
    raw_h = round(h * scale)

    # Snap to multiples of 32 without going below 512
    new_w = _ceil32(raw_w)
    new_h = _ceil32(raw_h)

    # --- IMPORTANT CHANGE HERE ---
    out = [f.resize((new_w, new_h), Image.NEAREST) for f in frames]

    return out, new_w, new_h, True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_resolution(
    frames: List[Image.Image],
    bgcolor_hex: str = "#ffffff",
) -> Tuple[List[Image.Image], int, int, List[str]]:
    """
    Pad then scale frames to satisfy LTX 2.3 resolution constraints.

    Parameters
    ----------
    frames      : list of PIL.Image (RGBA expected)
    bgcolor_hex : '#rrggbb' background colour used for padding
                  (use the value returned by handle_transparency)

    Returns
    -------
    out_frames : processed RGBA frames
    width      : final frame width  (multiple of 32, ≥512 on short side)
    height     : final frame height
    warnings   : list of warning strings
    """
    warnings: List[str] = []

    if not frames:
        warnings.append("resolution_normalization: received empty frame list.")
        return frames, 0, 0, warnings

    orig_w, orig_h = frames[0].size

    # --- Determine background colour -----------------------------------------
    try:
        bg = _hex_to_rgb(bgcolor_hex)
    except (ValueError, IndexError):
        bg = _detect_bg_from_borders(frames[0])
        warnings.append(
            "resolution_normalization: could not parse bgcolor_hex "
            f"'{bgcolor_hex}'; detected border colour #{bg[0]:02x}{bg[1]:02x}{bg[2]:02x} instead."
        )

    # --- Step 1: pad to multiples of 32 --------------------------------------
    frames, w, h = _pad_to_square(frames, bg)
    if (w, h) != (orig_w, orig_h):
        warnings.append(
            f"resolution_normalization: padded {orig_w}×{orig_h} → {w}×{h} "
            f"(square, symmetric, colour #{bg[0]:02x}{bg[1]:02x}{bg[2]:02x})."
        )

    # --- Step 2: resize to 768x768 --------------------------------------
    frames, w, h = _resize_to_768(frames, w, h)
    warnings.append(
        "resolution_normalization: resized to 768×768 using NEAREST (pixel-perfect)."
    )

    # Sanity checks
    if w % 32 != 0 or h % 32 != 0:
        warnings.append(
            f"resolution_normalization: WARNING – final size {w}×{h} is not "
            "divisible by 32. This should not happen; please report a bug."
        )

    return frames, w, h, warnings
