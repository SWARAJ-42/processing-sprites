import random
from pathlib import Path
import re

from generate_captions import process_gif


def test_random_samples(dataset_path, n=3):
    dataset_path = Path(dataset_path)
    metadata_path = dataset_path / "metadata.json"

    gifs = list(dataset_path.rglob("*.gif"))
    samples = random.sample(gifs, min(n, len(gifs)))

    for gif in samples:
        print("\n==============================")
        print(f"GIF: {gif.name}")

        prompt = process_gif(gif, "Pksnjfs", metadata_path, gif.name)

        print("PROMPT:")
        print(prompt)


def test_single_gif(gif_path, dataset_path):
    gif_path = Path(gif_path)
    dataset_path = Path(dataset_path)
    metadata_path = dataset_path / "metadata.json"

    if not gif_path.exists():
        print(f"❌ File not found: {gif_path}")
        return

    print("\n==============================")
    print(f"TESTING SINGLE GIF: {gif_path.name}")

    # Pass gif_path.name as the fourth argument
    clean_name = re.sub(r'\d+', '', gif_path.stem).strip('_')
    print(clean_name)
    prompt = process_gif(gif_path, "Pksnjfs", metadata_path, clean_name)

    print("PROMPT:")
    print(prompt)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Random test: python test_prompt_quality.py <dataset_path>")
        print("  Single GIF : python test_prompt_quality.py <dataset_path> <gif_path>")
        exit(1)

    dataset_path = sys.argv[1]

    # ✅ If GIF path provided → test only that
    if len(sys.argv) >= 3:
        gif_path = sys.argv[2]
        test_single_gif(gif_path, dataset_path)
    else:
        test_random_samples(dataset_path, n=3)