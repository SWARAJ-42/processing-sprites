import os
import json
import random
import tempfile
from PIL import Image, ImageSequence
from pathlib import Path

from generate_prompt_azure import generate_prompt_bytes

MAX_SIZE = 1024

# -----------------------------
# GIF → SPRITE SHEET
# -----------------------------
def gif_to_sprite_sheet(gif_path, save=False):
    gif_path = Path(gif_path)
    gif = Image.open(gif_path)

    frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(gif)]
    num_frames = len(frames)

    w, h = frames[0].size

    # ✅ Force single row
    cols = num_frames
    rows = 1

    sheet_width = cols * w
    sheet_height = h

    # Optional: scale down if exceeding MAX_SIZE
    if sheet_width > MAX_SIZE:
        scale = MAX_SIZE / sheet_width
        w = int(w * scale)
        h = int(h * scale)
        frames = [f.resize((w, h), Image.NEAREST) for f in frames]
        sheet_width = cols * w
        sheet_height = h

    sheet = Image.new("RGBA", (sheet_width, sheet_height))

    for i, frame in enumerate(frames):
        x = i * w
        sheet.paste(frame, (x, 0))

    # Save in current working directory
    if save:
        output_name = gif_path.stem + "_spritesheet.png"
        output_path = Path(".") / output_name
        sheet.save(output_path)
        print(f"Saved spritesheet: {output_path.resolve()}")

    return sheet, num_frames, rows, cols


# -----------------------------
# PROCESS SINGLE GIF
# -----------------------------
def process_gif(gif_path, token, metadata_path, gif_name):

    sheet, num_frames, rows, cols = gif_to_sprite_sheet(gif_path)

    prompt = generate_prompt_bytes(
        sheet=sheet,
        token=token,
        rows=rows,
        cols=cols,
        num_frames=num_frames,
        gif_name=gif_name,
        metadata_path=metadata_path,
        gif_path=gif_path
    )

    return prompt

# -----------------------------
# UPDATE METADATA
# -----------------------------
def update_metadata(metadata_path, gif_name, caption):
    with open(metadata_path, "r") as f:
        data = json.load(f)

    for item in data:
        if gif_name in item["media_path"]:
            item["caption"] = caption

    with open(metadata_path, "w") as f:
        json.dump(data, f, indent=2)

# -----------------------------
# MAIN PIPELINE
# -----------------------------
def run(dataset_path, token="PBmcK7uc"):

    dataset_path = Path(dataset_path)
    metadata_path = dataset_path / "metadata.json"

    gifs = list(dataset_path.rglob("*.gif"))

    for gif in gifs:
        print(f"Processing: {gif}")

        # gif.name extracts the filename (e.g., "animation.gif")
        prompt = process_gif(gif, token, metadata_path, gif.name)

        # save txt
        txt_path = gif.with_suffix(".txt")
        with open(txt_path, "w") as f:
            f.write(prompt)

        # update metadata
        update_metadata(metadata_path, gif.name, prompt)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python generate_dataset_captions.py <dataset_path>")
        exit(1)

    run(sys.argv[1])