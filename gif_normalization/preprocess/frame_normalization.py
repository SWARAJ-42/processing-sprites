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
"""

from __future__ import annotations

from typing import List, Tuple

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