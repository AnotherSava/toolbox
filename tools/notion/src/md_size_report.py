"""Evernote markdown size calculator.

Reads markdown files exported from Evernote, calculates total size
(text + referenced resources), sorts by size descending, and outputs to CSV.
"""

import csv
import json
import re
from pathlib import Path

from .client import CONFIG_PATH

# Regex patterns for resource references in Evernote markdown exports
PATTERNS = [
    r"!\[.*?\]\(\.\./_resources/([^)]+)\)",  # ![alt](../_resources/file)
    r"(?<!!)\[.*?\]\(\.\./_resources/([^)]+)\)",  # [text](../_resources/file)
    r'<img[^>]+src=["\']\.\./_resources/([^"\']+)["\']',  # <img src="../_resources/file"
]


def _load_config() -> tuple[Path, Path, Path]:
    """Load md_size_report paths from config.json."""
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Config not found: {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    section = cfg.get("md_size_report")
    if not section:
        raise SystemExit(f"md_size_report section not found in {CONFIG_PATH}")
    missing = [k for k in ("notebook_dir", "resources_dir", "output_csv") if k not in section]
    if missing:
        raise SystemExit(f"Missing md_size_report keys in config: {', '.join(missing)}")
    return Path(section["notebook_dir"]), Path(section["resources_dir"]), Path(section["output_csv"])


def extract_resources(content: str) -> list[str]:
    """Extract all resource filenames from markdown content."""
    resources = []
    for pattern in PATTERNS:
        matches = re.findall(pattern, content)
        resources.extend(matches)
    return resources


def get_file_size(path: Path) -> int:
    """Get file size in bytes, returns 0 if file doesn't exist."""
    try:
        return path.stat().st_size
    except (FileNotFoundError, OSError):
        return 0


def process_markdown_file(md_path: Path, resources_dir: Path) -> tuple[str, int, int, int, int]:
    """Process a single markdown file.

    Returns: (filename, text_size, resources_size, total_size, resource_count)
    """
    try:
        content = md_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = md_path.read_text(encoding="latin-1")

    text_size = len(content.encode("utf-8"))
    resources = extract_resources(content)
    resources_size = sum(get_file_size(resources_dir / name) for name in resources)

    return (md_path.name, text_size, resources_size, text_size + resources_size, len(resources))


def main() -> int:
    notebook_dir, resources_dir, output_csv = _load_config()

    print(f"Scanning markdown files in: {notebook_dir}")
    md_files = list(notebook_dir.glob("*.md"))
    print(f"Found {len(md_files)} markdown files")

    results = []
    for i, md_path in enumerate(md_files, 1):
        if i % 100 == 0:
            print(f"Processing {i}/{len(md_files)}...")
        results.append(process_markdown_file(md_path, resources_dir))

    results.sort(key=lambda x: x[3], reverse=True)

    print(f"Writing results to: {output_csv}")
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "text_size_kb", "resources_size_kb", "total_size_kb", "resource_count"])
        for filename, text_size, resources_size, total_size, resource_count in results:
            writer.writerow([filename, round(text_size / 1024, 2), round(resources_size / 1024, 2), round(total_size / 1024, 2), resource_count])

    print(f"Done! Processed {len(results)} files.")

    print("\nTop 5 largest files:")
    for filename, text_size, resources_size, total_size, resource_count in results[:5]:
        print(f"  {filename}: {total_size / 1024 / 1024:.2f} MB ({resource_count} resources)")

    return 0
