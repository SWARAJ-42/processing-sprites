"""
frame_normalization.py
======================
Normalize the frame count of a GIF to the nearest value of the form **8N + 1**
(e.g. 9, 17, 25, 33 …) required by LTX 2.3.

Design principle: ZERO interpolation / blending.
------------------------------------------------
Blending between frames introduces "ghost" pixels that never existed in the
original animation. These smudged artefacts can confuse diffusion models and
degrade generation quality.

This module only ever uses exact copies of source frames.

Strategy
--------
Upsampling  (source < target)
    Bresenham-style distribution: express T = q×N + r, then assign
    (q+1) repetitions to the first r frames and q repetitions to the rest.
    This spreads duplicates as evenly as possible across the timeline.
    Per-frame display duration is reduced proportionally so the total
    animation wall-clock time is preserved.

Downsampling  (source > target)
    Uniform index selection: pick T evenly-spaced indices from [0, N-1].
    Always selects real source frames — never synthesises new ones.

Pass-through  (source == target)
    Returned unchanged.

Public API
----------
    normalize_frame_count(frames, durations) -> (frames, durations, warnings)
    save_normalized_output(frames, durations, gif_path)
        -> Saves both <gif_path> and <stem>.mp4 side-by-side.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Nearest 8N+1 target
# ---------------------------------------------------------------------------

def _nearest_8n1(n: int) -> int:
    """
    Return the nearest integer of the form 8k+1 (k >= 1, minimum 9) to *n*.
    Ties broken toward the larger value.
    """
    if n <= 0:
        return 9

    k = max(1, (n - 1) // 8)
    candidates = []
    for dk in range(-1, 3):          # small neighbourhood is always sufficient
        val = 8 * (k + dk) + 1
        if val >= 9:
            candidates.append(val)

    return min(candidates, key=lambda v: abs(v - n))


# ---------------------------------------------------------------------------
# Upsampling — Bresenham duplication
# ---------------------------------------------------------------------------

def _upsample_bresenham(
    frames: List[Image.Image],
    durations: List[int],
    target: int,
) -> Tuple[List[Image.Image], List[int]]:
    """
    Expand *frames* to exactly *target* frames using only exact copies.

    Algorithm
    ---------
    target = q * N + r   (N = len(frames))

    Each of the first *r* source frames is repeated (q + 1) times.
    Each of the remaining (N - r) source frames is repeated q times.
    Total = r*(q+1) + (N-r)*q = N*q + r = target  (proven)

    Duration
    --------
    A frame repeated k times gets duration = original_duration / k per copy,
    preserving total animation wall-clock time.
    Minimum enforced at 10 ms (GIF spec lower-bound).
    """
    n = len(frames)
    q, r = divmod(target, n)          # target = q*n + r

    out_frames: List[Image.Image] = []
    out_dur: List[int] = []

    for i, (frame, dur) in enumerate(zip(frames, durations)):
        reps = (q + 1) if i < r else q
        per_copy_dur = max(10, round(dur / reps))
        for _ in range(reps):
            out_frames.append(frame.copy())
            out_dur.append(per_copy_dur)

    return out_frames, out_dur


# ---------------------------------------------------------------------------
# Downsampling — uniform index selection
# ---------------------------------------------------------------------------

def _downsample_uniform(
    frames: List[Image.Image],
    durations: List[int],
    target: int,
) -> Tuple[List[Image.Image], List[int]]:
    """
    Select *target* evenly-spaced frames from *frames*.

    Uses round() to distribute selection points uniformly across [0, N-1].
    Total duration is redistributed evenly across the selected frames.
    """
    n = len(frames)
    if target == 1:
        indices = [0]
    else:
        indices = [
            round(i * (n - 1) / (target - 1))
            for i in range(target)
        ]

    out_frames = [frames[i].copy() for i in indices]

    total_dur = sum(durations)
    per_frame = max(10, round(total_dur / target))
    out_dur = [per_frame] * target

    return out_frames, out_dur


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_frame_count(
    frames: List[Image.Image],
    durations: List[int],
) -> Tuple[List[Image.Image], List[int], List[str]]:
    """
    Adjust *frames* / *durations* so that len(frames) == 8k+1.

    No interpolation or blending is ever performed — only exact source
    frame copies are used.

    Parameters
    ----------
    frames    : list of PIL.Image (RGBA expected)
    durations : per-frame display duration in milliseconds

    Returns
    -------
    out_frames    : normalized frame list (all frames are copies of originals)
    out_durations : matching duration list
    warnings      : list of informational strings (may be empty)
    """
    warnings: List[str] = []
    n = len(frames)

    if n == 0:
        warnings.append("frame_normalization: received 0 frames -- nothing to normalize.")
        return frames, durations, warnings

    target = _nearest_8n1(n)

    if n == target:
        return frames, durations, warnings

    if n < target:
        # --- Upsample via Bresenham duplication ---
        q, r = divmod(target, n)
        out_frames, out_dur = _upsample_bresenham(frames, durations, target)
        warnings.append(
            f"frame_normalization: upsampled {n} -> {target} frames "
            f"(Bresenham duplication: {r} frames x{q+1} reps, "
            f"{n-r} frames x{q} reps -- no interpolation)."
        )
    else:
        # --- Downsample via uniform selection ---
        out_frames, out_dur = _downsample_uniform(frames, durations, target)
        warnings.append(
            f"frame_normalization: downsampled {n} -> {target} frames "
            f"(uniform index selection -- no interpolation)."
        )

    return out_frames, out_dur, warnings


# ---------------------------------------------------------------------------
# Dual save: GIF (backward compat) + MP4 (frame-exact)
# ---------------------------------------------------------------------------

def save_normalized_output(
    frames: List[Image.Image],
    durations: List[int],
    gif_path: str | os.PathLike,
) -> Tuple[str, str]:
    """
    Save the normalized frames as **both** a GIF and an MP4.

    Why two formats?
    ----------------
    GIF encoders (including Pillow) may collapse consecutive identical frames
    during palette/LZW optimisation, silently discarding the duplicates that
    Bresenham upsampling intentionally introduced.  MP4 (via imageio + ffmpeg)
    writes every frame to its own timestamp, so the exact frame count is
    always preserved — which is the guarantee LTX 2.3 requires.

    The MP4 file is written alongside the GIF with the same stem and only
    the extension changed:
        /path/to/animation.gif  ->  /path/to/animation.mp4

    Parameters
    ----------
    frames    : normalized frame list (PIL.Image, RGBA or RGB)
    durations : per-frame duration in milliseconds (must match len(frames))
    gif_path  : destination path for the GIF file

    Returns
    -------
    (gif_path_str, mp4_path_str)
        Absolute paths to the two files that were written.

    Raises
    ------
    ImportError  if imageio or its ffmpeg plugin are unavailable.
    ValueError   if frames and durations lengths do not match.
    """
    if len(frames) != len(durations):
        raise ValueError(
            f"save_normalized_output: frames ({len(frames)}) and "
            f"durations ({len(durations)}) must have the same length."
        )

    gif_path = Path(gif_path).resolve()
    mp4_path = gif_path.with_suffix(".mp4")

    # ------------------------------------------------------------------
    # 1. GIF — saved for backward compatibility.
    #    disable_minimal_update=True stops Pillow stripping "identical"
    #    delta frames; optimize=False keeps every palette entry intact.
    # ------------------------------------------------------------------
    gif_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert all frames to RGBA palette-safe P mode for GIF
    gif_frames = []
    for frame in frames:
        gif_frames.append(frame.convert("RGBA"))

    gif_frames[0].save(
        gif_path,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=durations,          # list of per-frame ms values
        loop=0,
        optimize=False,              # do NOT strip duplicate palette entries
        disposal=2,                  # full-frame replace — no delta blending
    )

    # ------------------------------------------------------------------
    # 2. MP4 — every frame written to its own timestamp; duplicates are
    #    truly preserved because ffmpeg does not perform frame dedup.
    #
    #    fps is derived from the *median* per-frame duration so that the
    #    container's constant frame-rate assumption matches the animation.
    #    A small epsilon guard avoids division by zero.
    # ------------------------------------------------------------------
    try:
        import imageio
    except ImportError as exc:
        raise ImportError(
            "imageio is required for MP4 output. "
            "Install it with:  pip install imageio[ffmpeg]"
        ) from exc

    median_dur_ms = float(np.median(durations)) if durations else 100.0
    fps = 1000.0 / max(median_dur_ms, 1.0)

    # imageio expects uint8 RGB numpy arrays
    np_frames = []
    for frame in frames:
        rgb = frame.convert("RGB")
        np_frames.append(np.asarray(rgb, dtype=np.uint8))

    writer_kwargs = {
        "fps": fps,
        "codec": "libx264",
        "pixelformat": "yuv420p",    # broadest player compatibility
        "macro_block_size": None,    # let imageio handle odd dimensions
        "ffmpeg_params": [
            "-crf", "0",             # lossless — preserves exact pixel values
            "-preset", "veryslow",   # best compression at lossless quality
        ],
    }

    with imageio.get_writer(str(mp4_path), **writer_kwargs) as writer:
        for np_frame in np_frames:
            writer.append_data(np_frame)

    return str(gif_path), str(mp4_path)