import argparse
from pathlib import Path
from collections import Counter


# Problematic → safe replacements
REPLACEMENTS = {
    "\u2018": "'",   # ‘
    "\u2019": "'",   # ’
    "\u201C": '"',   # “
    "\u201D": '"',   # ”
    "\u2013": "-",   # –
    "\u2014": "-",   # —
    "\u00A0": " ",   # non-breaking space
}


def read_file_safely(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="latin-1")


def clean_text_with_log(text: str):
    counter = Counter()
    cleaned = text

    # Count + replace known problematic chars
    for bad, good in REPLACEMENTS.items():
        count = cleaned.count(bad)
        if count > 0:
            counter[f"{repr(bad)} → {repr(good)}"] += count
            cleaned = cleaned.replace(bad, good)

    # Detect unknown problematic chars
    unknown_counter = Counter()
    for ch in cleaned:
        if ord(ch) > 127:  # non-ASCII
            unknown_counter[repr(ch)] += 1

    # Replace unknowns safely
    cleaned = cleaned.encode("utf-8", errors="replace").decode("utf-8")

    return cleaned, counter, unknown_counter


def process_file(file_path: Path, log_file):
    original_text = read_file_safely(file_path)
    cleaned_text, known, unknown = clean_text_with_log(original_text)

    if original_text != cleaned_text:
        file_path.write_text(cleaned_text, encoding="utf-8")

        print(f"Cleaned: {file_path}")

        log_file.write(f"\nFILE: {file_path}\n")

        if known:
            log_file.write("  Known replacements:\n")
            for k, v in known.items():
                log_file.write(f"    {k}: {v} times\n")

        if unknown:
            log_file.write("  Unknown non-ASCII characters:\n")
            for k, v in unknown.items():
                log_file.write(f"    {k}: {v} times\n")

    else:
        print(f"OK: {file_path}")


def process_folder(root_dir):
    root = Path(root_dir)
    txt_files = list(root.rglob("*.txt"))

    if not txt_files:
        print("No .txt files found.")
        return

    log_path = root / "cleaning_log.txt"

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write("=== TEXT CLEANING LOG ===\n")

        print(f"Found {len(txt_files)} text files\n")

        for file_path in txt_files:
            process_file(file_path, log_file)

    print(f"\nLog saved at: {log_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="Clean .txt files + log detected problematic characters."
    )
    parser.add_argument("root_dir", help="Root directory")

    args = parser.parse_args()

    process_folder(args.root_dir)


if __name__ == "__main__":
    main()