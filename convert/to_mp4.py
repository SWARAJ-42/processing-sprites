import subprocess
from pathlib import Path
import shutil
import argparse


def convert_gif_to_mp4(gif_path: Path, output_path: Path):
    output_file = output_path / (gif_path.stem + ".mp4")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(gif_path),

        # Preserve sharp pixels (VERY important)
        "-vf", "scale=iw:ih:flags=neighbor",

        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "12",
        "-pix_fmt", "yuv420p",

        str(output_file)
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"{gif_path} → {output_file}")


def process_dataset(input_root, output_root):
    input_root = Path(input_root)
    output_root = Path(output_root)

    for path in input_root.rglob("*"):
        relative_path = path.relative_to(input_root)
        target_path = output_root / relative_path

        if path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        # Skip GIF copy
        if path.suffix.lower() == ".gif":
            # Convert instead
            target_path.parent.mkdir(parents=True, exist_ok=True)
            convert_gif_to_mp4(path, target_path.parent)
        else:
            # Copy everything else
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target_path)


def main():
    parser = argparse.ArgumentParser(
        description="Convert GIF dataset to MP4 while copying structure."
    )
    parser.add_argument("input_dir", help="Original dataset folder")
    parser.add_argument("output_dir", help="New dataset folder")

    args = parser.parse_args()

    process_dataset(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()