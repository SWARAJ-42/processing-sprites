import subprocess
from pathlib import Path
import argparse


def get_frame_count(video_path: Path) -> int:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-count_frames",
        "-show_entries", "stream=nb_read_frames",
        "-of", "default=nokey=1:noprint_wrappers=1",
        str(video_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    try:
        return int(result.stdout.strip())
    except ValueError:
        return -1  # fallback if ffprobe fails


def scan_videos(root_dir: str):
    root = Path(root_dir)

    for video_path in root.rglob("*.mp4"):
        num_frames = get_frame_count(video_path)
        print(f"{video_path} → {num_frames} frames")


def main():
    parser = argparse.ArgumentParser(
        description="Print frame count for all MP4 videos in a directory"
    )
    parser.add_argument("input_dir", help="Directory containing MP4 videos")

    args = parser.parse_args()

    scan_videos(args.input_dir)


if __name__ == "__main__":
    main()