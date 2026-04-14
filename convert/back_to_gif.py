import os
import subprocess

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

INPUT_DIR = "./dataset_candidate"   # folder with mp4 files
OUTPUT_DIR = "./dataset_gifs"   # where gifs will be saved
FPS = 12                    # adjust if needed (lower = smaller file)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ------------------------------------------------------------------
# CORE FUNCTION
# ------------------------------------------------------------------

def convert_mp4_to_gif(mp4_path, gif_path):
    """
    Convert MP4 → GIF using palette generation for best quality.

    IMPORTANT:
    - Uses NEAREST scaling → preserves pixel art sharpness
    - Disables dithering → prevents noise/tearing
    """

    palette_path = gif_path + ".png"

    # Step 1: Generate palette
    cmd_palette = [
        "ffmpeg",
        "-y",
        "-i", mp4_path,
        "-vf", f"fps={FPS},scale=iw:ih:flags=neighbor,palettegen",
        palette_path
    ]

    # Step 2: Use palette to create GIF
    cmd_gif = [
        "ffmpeg",
        "-y",
        "-i", mp4_path,
        "-i", palette_path,
        "-lavfi", f"fps={FPS},scale=iw:ih:flags=neighbor[x];[x][1:v]paletteuse=dither=none",
        gif_path
    ]

    subprocess.run(cmd_palette, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(cmd_gif, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # cleanup
    if os.path.exists(palette_path):
        os.remove(palette_path)


# ------------------------------------------------------------------
# BATCH PROCESS
# ------------------------------------------------------------------

def process_folder():
    for file in os.listdir(INPUT_DIR):
        if file.lower().endswith(".mp4"):
            mp4_path = os.path.join(INPUT_DIR, file)
            gif_name = os.path.splitext(file)[0] + ".gif"
            gif_path = os.path.join(OUTPUT_DIR, gif_name)

            print(f"Converting: {file}")
            convert_mp4_to_gif(mp4_path, gif_path)

    print("\nDone.")


if __name__ == "__main__":
    process_folder()