"""Standalone image optimizer.

Takes one or more input files, or a directory of images, and writes optimized copies
(WebP or AVIF, resized to a max width, configurable quality) to an output directory.

Use this when you want to shrink images before uploading them somewhere — Notion,
GitHub, a blog, etc. — without any platform-specific glue.

Examples:
    image-opt photo.jpg                         # outputs ./photo.webp
    image-opt ./photos --out ./photos-small     # converts every image in a directory
    image-opt ./in --format avif --quality 50   # smallest files (no preview in Notion)
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

INPUT_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".bmp", ".tiff", ".webp", ".avif"}

FORMAT_INFO = {
    "webp": {"ext": ".webp", "save_kwargs": {"format": "WEBP", "method": 6}},
    "avif": {"ext": ".avif", "save_kwargs": {"format": "AVIF", "speed": 2, "subsampling": "4:2:0"}},
}


def convert_image(in_path: Path, out_path: Path, fmt: str, max_width: int, quality: int) -> int:
    """Resize and re-encode one image. Returns output byte count."""
    img = Image.open(in_path)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if img.width > max_width:
        new_h = round(img.height * max_width / img.width)
        img = img.resize((max_width, new_h), Image.LANCZOS)
    img.save(out_path, quality=quality, **FORMAT_INFO[fmt]["save_kwargs"])
    return out_path.stat().st_size


def collect_inputs(paths: list[Path]) -> list[Path]:
    """Expand directories to their image children. Files are passed through if recognized."""
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(c for c in p.iterdir() if c.is_file() and c.suffix.lower() in INPUT_EXTS))
        elif p.is_file():
            files.append(p)
        else:
            print(f"  skip: {p} not found", file=sys.stderr)
    return files


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Resize and re-encode images to WebP or AVIF.")
    parser.add_argument("inputs", nargs="+", type=Path, help="One or more image files or directories.")
    parser.add_argument("--out", type=Path, default=None, help="Output directory. Defaults to each input's parent directory.")
    parser.add_argument("--format", choices=list(FORMAT_INFO), default="webp", help="Output format (default: webp).")
    parser.add_argument("--max-width", type=int, default=1024, help="Resize images wider than this (pixels).")
    parser.add_argument("--quality", type=int, default=60, help="Quality 0-100; lower = smaller files.")
    args = parser.parse_args()

    files = collect_inputs(args.inputs)
    if not files:
        print("No input images found.", file=sys.stderr)
        return 1

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    fmt_ext = FORMAT_INFO[args.format]["ext"]
    total_in = 0
    total_out = 0
    for f in files:
        out_dir = args.out or f.parent
        out_path = out_dir / f"{f.stem}{fmt_ext}"
        in_size = f.stat().st_size
        out_size = convert_image(f, out_path, args.format, args.max_width, args.quality)
        print(f"  {in_size:>9,}B -> {out_size:>7,}B  {out_path.name}")
        total_in += in_size
        total_out += out_size

    print(f"\nTotal: {total_in:,}B -> {total_out:,}B ({100 * total_out / total_in:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
