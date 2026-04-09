from pathlib import Path
import shutil
import argparse
from PIL import Image, ImageSequence


def extract_first_frame(gif_path: Path, output_path: Path):
    output_file = output_path / (gif_path.stem + ".png")

    try:
        gif = Image.open(gif_path)

        # ✅ Get first frame
        frame = next(ImageSequence.Iterator(gif)).convert("RGBA")

        # Save as PNG (lossless)
        frame.save(output_file)

        print(f"🖼️ {gif_path} → {output_file}")

    except Exception as e:
        print(f"❌ Failed: {gif_path} | {e}")


def process_dataset(input_root, output_root):
    input_root = Path(input_root)
    output_root = Path(output_root)

    for path in input_root.rglob("*"):
        relative_path = path.relative_to(input_root)
        target_path = output_root / relative_path

        if path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        if path.suffix.lower() == ".gif":
            # ✅ Replace GIF with first frame PNG
            target_path.parent.mkdir(parents=True, exist_ok=True)
            extract_first_frame(path, target_path.parent)
        else:
            # ✅ Copy everything else
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target_path)


def main():
    parser = argparse.ArgumentParser(
        description="Extract first frame from GIFs and copy dataset structure."
    )
    parser.add_argument("input_dir", help="Original dataset folder")
    parser.add_argument("output_dir", help="New dataset folder")

    args = parser.parse_args()

    process_dataset(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()