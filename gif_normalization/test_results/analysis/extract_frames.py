import os
import argparse
from PIL import Image


def gif_to_spritesheet(gif_path, output_path=None):
    # Validate input
    if not os.path.exists(gif_path):
        raise FileNotFoundError(f"File not found: {gif_path}")

    # Default output path
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(gif_path))[0]
        output_path = f"{base_name}_spritesheet.png"

    frames = []

    # Load frames
    with Image.open(gif_path) as img:
        try:
            while True:
                frame = img.convert("RGBA")
                frames.append(frame.copy())
                img.seek(img.tell() + 1)
        except EOFError:
            pass

    if len(frames) == 0:
        raise ValueError("No frames found in GIF")

    # Get max dimensions (handles inconsistent frame sizes)
    max_width = max(f.width for f in frames)
    max_height = max(f.height for f in frames)

    # Create sprite sheet (1 row)
    sheet_width = max_width * len(frames)
    sheet_height = max_height

    spritesheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))

    # Paste frames side-by-side
    for i, frame in enumerate(frames):
        # Center frame if smaller than max size
        x_offset = i * max_width + (max_width - frame.width) // 2
        y_offset = (max_height - frame.height) // 2

        spritesheet.paste(frame, (x_offset, y_offset), frame)

    # Save output
    spritesheet.save(output_path)

    print(f"✅ Spritesheet saved to '{output_path}'")
    print(f"Frames: {len(frames)}, Frame size: {max_width}x{max_height}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert GIF to 1-row spritesheet")
    parser.add_argument("--input", required=True, help="Path to input GIF")
    parser.add_argument("--output", help="Output PNG path (optional)")

    args = parser.parse_args()

    gif_to_spritesheet(args.input, args.output)