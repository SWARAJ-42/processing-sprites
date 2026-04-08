"""
io_utils.py — GIF I/O helpers shared across the pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageSequence


# ---------------------------------------------------------------------------
# GIF loading / saving
# ---------------------------------------------------------------------------

def load_gif_frames(path: str | Path) -> Tuple[List[Image.Image], List[int]]:
    """
    Load every frame of a GIF, converting each to RGBA.

    Returns
    -------
    frames : list of PIL.Image (RGBA)
    durations : list of int  — per-frame display time in milliseconds
                              (defaults to 100 ms if not specified)
    """
    frames: List[Image.Image] = []
    durations: List[int] = []

    with Image.open(path) as gif:
        for frame in ImageSequence.Iterator(gif):
            frames.append(frame.convert("RGBA"))
            durations.append(frame.info.get("duration", 100))

    return frames, durations


def save_gif(
    frames: List[Image.Image],
    durations: List[int],
    out_path: str | Path,
    loop: int = 0,
) -> None:
    """
    Save a list of RGBA PIL frames as an animated GIF.

    Parameters
    ----------
    frames    : list of PIL.Image (RGBA or RGB)
    durations : per-frame duration in ms (must match len(frames))
    out_path  : destination file path
    loop      : 0 = loop forever, else loop count
    """
    if not frames:
        raise ValueError("No frames to save.")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to RGBA uniformly before saving
    rgba_frames = [f.convert("RGBA") for f in frames]

    # PIL GIF save requires palette-mode images for proper transparency
    palette_frames = []
    for f in rgba_frames:
        pf = f.convert("P", palette=Image.ADAPTIVE, colors=255)
        palette_frames.append(pf)

    palette_frames[0].save(
        out_path,
        format="GIF",
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=loop,
        disposal=2,
    )


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_gifs(root_dir: str | Path) -> List[Path]:
    """
    Recursively find all .gif files under root_dir.
    Returns absolute Path objects sorted for determinism.
    """
    root = Path(root_dir).resolve()
    return sorted(root.rglob("*.gif"))


def relative_posix(path: str | Path, base: str | Path) -> str:
    """
    Return a POSIX-style relative path string (forward slashes, no leading /).
    Suitable for cross-platform metadata storage.
    """
    return Path(path).relative_to(base).as_posix()
