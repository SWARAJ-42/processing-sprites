import argparse
from pathlib import Path
from collections import Counter


# Proper replacements AFTER decoding
REPLACEMENTS = {
    "\u2018": "'",   # ‘
    "\u2019": "'",   # ’
    "\u201C": '"',   # “
    "\u201D": '"',   # ”
    "\u2013": "-",   # –
    "\u2014": "-",   # —
    "\u00A0": " ",   # non-breaking space
}


def detect_bad_bytes(raw: bytes):
    counter = Counter()
    for b in raw:
        if 128 <= b <= 159:  # Windows problematic range
            counter[hex(b)] += 1
    return counter


def read_file_correctly(file_path: Path):
    raw = file_path.read_bytes()

    try:
        text = raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        text = raw.decode("cp1252")  # 🔥 THIS IS THE REAL FIX
        encoding = "cp1252"

    return text, raw, encoding


def clean_text(text: str):
    counter = Counter()
    cleaned = text

    # Replace known characters
    for bad, good in REPLACEMENTS.items():
        count = cleaned.count(bad)
        if count > 0:
            counter[f"{repr(bad)} → {repr(good)}"] += count
            cleaned = cleaned.replace(bad, good)

    # Remove control characters
    cleaned = "".join(ch if ord(ch) >= 32 else " " for ch in cleaned)

    # Detect leftover non-ASCII
    unknown_counter = Counter()
    for ch in cleaned:
        if ord(ch) > 127:
            unknown_counter[repr(ch)] += 1

    return cleaned, counter, unknown_counter


def process_file(file_path: Path, log_file):
    text, raw, encoding = read_file_correctly(file_path)
    bad_bytes = detect_bad_bytes(raw)

    cleaned_text, known, unknown = clean_text(text)

    if text != cleaned_text or bad_bytes:
        file_path.write_text(cleaned_text, encoding="utf-8")

        print(f"🧹 Cleaned: {file_path}")

        log_file.write(f"\nFILE: {file_path}\n")
        log_file.write(f"  Original encoding: {encoding}\n")

        if bad_bytes:
            log_file.write("  Raw problematic bytes:\n")
            for k, v in bad_bytes.items():
                log_file.write(f"    {k}: {v} times\n")

        if known:
            log_file.write("  Replacements:\n")
            for k, v in known.items():
                log_file.write(f"    {k}: {v} times\n")

        if unknown:
            log_file.write("  Remaining non-ASCII:\n")
            for k, v in unknown.items():
                log_file.write(f"    {k}: {v} times\n")

    else:
        print(f"✅ OK: {file_path}")


def process_folder(root_dir):
    root = Path(root_dir)
    txt_files = list(root.rglob("*.txt"))

    if not txt_files:
        print("No .txt files found.")
        return

    log_path = root / "cleaning_log.txt"

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write("=== TEXT CLEANING LOG ===\n")

        print(f"🔍 Found {len(txt_files)} text files\n")

        for file_path in txt_files:
            process_file(file_path, log_file)

    print(f"\n📄 Log saved at: {log_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="Fix Windows-encoded text files to UTF-8 safely."
    )
    parser.add_argument("root_dir", help="Root directory")

    args = parser.parse_args()

    process_folder(args.root_dir)


if __name__ == "__main__":
    main()