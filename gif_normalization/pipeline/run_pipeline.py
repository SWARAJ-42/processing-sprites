"""
run_pipeline.py
===============
End-to-end preprocessing pipeline for GIF game-character animations.

Usage
-----
    python run_pipeline.py <root_dir> [--workers N]

Arguments
---------
    root_dir   : directory that contains nested folders of .gif files.
                 Output is written to <root_dir>/dataset/.

    --workers  : number of parallel workers (default: cpu_count).

Pipeline steps (in order)
--------------------------
1. Transparency handling  – replace alpha with high-contrast bg colour
2. Frame normalisation    – adjust to nearest 8N+1 frame count
3. Resolution normalisation – pad + scale to multiples of 32 (min 512px)

Adding more preprocessing steps
--------------------------------
Import your new module and add a call inside ``_process_single_gif`` in the
"--- preprocessing steps ---" section.  The function signature convention is:

    new_step(frames, ...) -> (frames, ..., warnings: List[str])

Append its returned warnings to ``all_warnings`` and thread any new metadata
fields through to the returned dict.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so relative imports work when the
# script is run directly (python pipeline/run_pipeline.py ...)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from preprocess.transparency_handling import handle_transparency
from preprocess.frame_normalization import normalize_frame_count
from preprocess.resolution_normalization import normalize_resolution
from utils.io_utils import find_gifs, load_gif_frames, relative_posix, save_gif


# ---------------------------------------------------------------------------
# Resolution bucket helper  (Ostris / ai-toolkit compatibility)
# ---------------------------------------------------------------------------

_RESOLUTION_BUCKETS = [256, 512, 768, 1024, 1280, 1328, 1538]


def _resolution_bucket(width: int, height: int) -> int:
    """
    Return the nearest supported resolution bucket for a given (w, h).
    Bucket = nearest value in _RESOLUTION_BUCKETS to sqrt(w*h).
    """
    approx = math.sqrt(width * height)
    return min(_RESOLUTION_BUCKETS, key=lambda b: abs(b - approx))


# ---------------------------------------------------------------------------
# Output filename generation
# ---------------------------------------------------------------------------

def _make_output_name(index: int, src_path: Path, root: Path) -> str:
    """
    Generate a collision-free filename by combining the sequential index
    with the relative folder structure of the source GIF.

    Example: root/attack/special/a.gif, index=7  →  '7_attack_special_a.gif'
    """
    rel_parts = src_path.relative_to(root).with_suffix("").parts
    slug = "_".join(rel_parts)
    # Sanitise slug: replace spaces and special chars
    safe_slug = "".join(c if c.isalnum() or c == "_" else "_" for c in slug)
    return f"{index:04d}_{safe_slug}.gif"


# ---------------------------------------------------------------------------
# Single-GIF processing  (runs in a worker process)
# ---------------------------------------------------------------------------

def _process_single_gif(
    src_path: Path,
    dataset_dir: Path,
    root_dir: Path,
    index: int,
) -> Dict[str, Any]:
    """
    Load, preprocess, and save one GIF.  Returns a metadata dict.
    """
    all_warnings: List[str] = []
    bgcolor_hex = "#ffffff"  # default; updated by transparency step

    try:
        # -- Load ---------------------------------------------------------------
        frames, durations = load_gif_frames(src_path)

        if not frames:
            raise ValueError("GIF contains no frames.")

        # ======================================================
        # --- preprocessing steps (add new ones below here) ---
        # ======================================================

        # Step 1: Transparency
        frames, bgcolor_hex, w1 = handle_transparency(frames)
        all_warnings.extend(w1)

        # Step 2: Frame count
        frames, durations, w2 = normalize_frame_count(frames, durations)
        all_warnings.extend(w2)

        # Step 3: Resolution
        frames, width, height, w3 = normalize_resolution(frames, bgcolor_hex)
        all_warnings.extend(w3)

        # ======================================================
        # --- end preprocessing steps --------------------------
        # ======================================================

        # -- Save ---------------------------------------------------------------
        out_name = _make_output_name(index, src_path, root_dir)
        out_path = dataset_dir / out_name
        save_gif(frames, durations, out_path)

        # -- Metadata -----------------------------------------------------------
        rel_media   = "./" + relative_posix(out_path,  root_dir)
        rel_original = "./" + relative_posix(src_path, root_dir)
        resolution  = _resolution_bucket(width, height)

        return {
            "media_path":    rel_media,
            "original_path": rel_original,
            "width":         width,
            "height":        height,
            "num_frames":    len(frames),
            "resolution":    resolution,
            "bgcolor":       bgcolor_hex,
            "caption":       "",
            "warnings":      all_warnings,
        }

    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        rel_original = "./" + relative_posix(src_path, root_dir)
        return {
            "media_path":    None,
            "original_path": rel_original,
            "width":         None,
            "height":        None,
            "num_frames":    None,
            "resolution":    None,
            "bgcolor":       None,
            "caption":       "",
            "warnings":      [f"FATAL: {exc}", tb],
        }


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(root_dir: str | Path, workers: Optional[int] = None) -> Path:
    """
    Process all GIFs found under *root_dir* and write:
        <root_dir>/dataset/<name>.gif  for each processed GIF
        <root_dir>/dataset/metadata.json

    Returns the path to the dataset directory.
    """
    root_dir = Path(root_dir).resolve()
    if not root_dir.is_dir():
        raise NotADirectoryError(f"root_dir does not exist: {root_dir}")

    dataset_dir = root_dir / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    gif_paths = find_gifs(root_dir)

    # Exclude already-processed files sitting inside the dataset/ folder
    gif_paths = [p for p in gif_paths if not p.is_relative_to(dataset_dir)]

    if not gif_paths:
        print("No GIF files found under", root_dir)
        return dataset_dir

    print(f"Found {len(gif_paths)} GIF(s) under {root_dir}")

    results: List[Dict[str, Any]] = [None] * len(gif_paths)  # type: ignore[list-item]

    # Use process pool for CPU-bound work
    max_workers = workers or min(os.cpu_count() or 1, len(gif_paths))

    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(
                _process_single_gif,
                path,
                dataset_dir,
                root_dir,
                idx + 1,
            ): idx
            for idx, path in enumerate(gif_paths)
        }

        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                results[idx] = future.result()
            except Exception as exc:  # noqa: BLE001
                rel = "./" + relative_posix(gif_paths[idx], root_dir)
                results[idx] = {
                    "media_path": None,
                    "original_path": rel,
                    "width": None, "height": None,
                    "num_frames": None, "resolution": None,
                    "bgcolor": None, "caption": "",
                    "warnings": [f"Worker crashed: {exc}"],
                }

            src = gif_paths[idx].name
            status = "OK" if results[idx].get("media_path") else "FAILED"
            print(f"  [{idx+1}/{len(gif_paths)}] {src} → {status}")
            if results[idx]["warnings"]:
                for w in results[idx]["warnings"]:
                    print(f"      ⚠  {w}")

    # Write metadata
    meta_path = dataset_dir / "metadata.json"
    with meta_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    ok_count = sum(1 for r in results if r.get("media_path"))
    print(f"\nDone. {ok_count}/{len(gif_paths)} GIF(s) processed successfully.")
    print(f"Metadata → {meta_path}")

    return dataset_dir


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preprocess GIF animations for LTX 2.3 I2V training."
    )
    parser.add_argument("root_dir", help="Root directory containing nested GIF folders.")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel worker processes (default: cpu count).",
    )
    args = parser.parse_args()
    run_pipeline(args.root_dir, workers=args.workers)


if __name__ == "__main__":
    main()
