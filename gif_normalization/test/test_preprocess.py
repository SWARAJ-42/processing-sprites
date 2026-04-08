"""
test_preprocess.py
==================
Manual-inspection test for the three preprocessing algorithms.

Usage
-----
    python test/test_preprocess.py <gif_path> <operation>

Operations
----------
    frame_normalization
    resolution_normalization
    transparency_handling

Output
------
    ./test_results/<operation>_<timestamp>.gif

The script applies ONLY the requested operation so you can study each step
in isolation with a real GIF.

Examples
--------
    python test/test_preprocess.py sample.gif transparency_handling
    python test/test_preprocess.py sample.gif frame_normalization
    python test/test_preprocess.py sample.gif resolution_normalization
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is importable regardless of cwd
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from utils.io_utils import load_gif_frames, save_gif
from preprocess.transparency_handling import handle_transparency
from preprocess.frame_normalization import normalize_frame_count
from preprocess.resolution_normalization import normalize_resolution


# ---------------------------------------------------------------------------
# Operation registry
# ---------------------------------------------------------------------------

OPERATIONS = {
    "transparency_handling",
    "frame_normalization",
    "resolution_normalization",
}


def apply_transparency_handling(frames, durations):
    out_frames, bgcolor_hex, warnings = handle_transparency(frames)
    return out_frames, durations, {"bgcolor": bgcolor_hex, "warnings": warnings}


def apply_frame_normalization(frames, durations):
    out_frames, out_durations, warnings = normalize_frame_count(frames, durations)
    return out_frames, out_durations, {
        "original_frame_count": len(frames),
        "new_frame_count": len(out_frames),
        "warnings": warnings,
    }


def apply_resolution_normalization(frames, durations):
    # Use transparency step first to get a valid bgcolor
    frames, bgcolor_hex, _ = handle_transparency(frames)
    out_frames, width, height, warnings = normalize_resolution(frames, bgcolor_hex)
    return out_frames, durations, {
        "width": width,
        "height": height,
        "bgcolor_used": bgcolor_hex,
        "warnings": warnings,
    }


_DISPATCH = {
    "transparency_handling":    apply_transparency_handling,
    "frame_normalization":      apply_frame_normalization,
    "resolution_normalization": apply_resolution_normalization,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test a single preprocessing operation on a GIF."
    )
    parser.add_argument("gif_path", help="Path to the input GIF file.")
    parser.add_argument(
        "operation",
        choices=sorted(OPERATIONS),
        help="Preprocessing operation to apply.",
    )
    args = parser.parse_args()

    gif_path = Path(args.gif_path).resolve()
    if not gif_path.is_file():
        print(f"ERROR: File not found: {gif_path}", file=sys.stderr)
        sys.exit(1)

    # Output path
    timestamp = int(time.time())
    out_dir = _PROJECT_ROOT / "test_results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{args.operation}_{timestamp}.gif"

    # Load
    print(f"Loading  : {gif_path}")
    frames, durations = load_gif_frames(gif_path)
    print(f"Input    : {len(frames)} frames, size {frames[0].size}")

    # Apply
    fn = _DISPATCH[args.operation]
    out_frames, out_durations, info = fn(frames, durations)

    # Report
    print(f"Operation: {args.operation}")
    for k, v in info.items():
        if k == "warnings":
            for w in v:
                print(f"  ⚠  {w}")
        else:
            print(f"  {k}: {v}")
    print(f"Output   : {len(out_frames)} frames, size {out_frames[0].size}")

    # Save
    save_gif(out_frames, out_durations, out_path)
    print(f"Saved to : {out_path}")


if __name__ == "__main__":
    main()
