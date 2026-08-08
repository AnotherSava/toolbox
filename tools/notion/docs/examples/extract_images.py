"""EXAMPLE: extract all images from a Notion page to disk — no mutations.

A snapshot of the workflow used to pull every image off a Notion page (in page order)
and save WebP-optimized copies named image_01.webp, image_02.webp, ... — useful when
you want the images for an external workflow (e.g., building a database manually) and
don't want to mutate the source page.

NOT a polished CLI tool — copy and adapt for similar one-off jobs. For pure image
optimization (without the Notion glue), use `image-opt` instead.

To run as-is from the project root:
    python tools/notion/docs/examples/extract_images.py <page-url-or-id>
"""

import argparse
import sys
import urllib.parse
from pathlib import Path

from image_opt.main import convert_image
from notion_tools.client import NotionClient, create_client
from notion_tools.page_ids import parse_page_id


def safe_name(text: str) -> str:
    """Filesystem-safe variant of a string (Windows-friendly)."""
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in text)[:60].strip()


def collect_image_blocks(client: NotionClient, page_id: str) -> tuple[list[tuple[str, str]], str, str]:
    """Return [(image_block_id, attachment_url), ...] in page order, plus space_id and page title."""
    page_resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": page_id}, "version": -1}],
    }).json()
    page = page_resp["recordMap"]["block"][page_id]["value"]["value"]
    children = page.get("content") or []
    space_id = page["space_id"]
    title = (page.get("properties", {}).get("title") or [["page"]])[0][0]

    block_records: dict = {}
    for i in range(0, len(children), 100):
        chunk = children[i:i + 100]
        r = client.post("syncRecordValues", {
            "requests": [{"pointer": {"table": "block", "id": bid}, "version": -1} for bid in chunk],
        }).json()
        block_records.update(r.get("recordMap", {}).get("block", {}))

    images: list[tuple[str, str]] = []
    for cid in children:
        b = block_records[cid]["value"]["value"]
        if b.get("type") == "image":
            src = (b.get("properties", {}).get("source") or [[None]])[0][0]
            if src:
                images.append((cid, src))
    return images, space_id, title


def download_via_proxy(client: NotionClient, block_id: str, attachment_url: str, space_id: str, out_path: Path) -> int:
    """Download an attachment via Notion's image proxy. Returns bytes written."""
    encoded = urllib.parse.quote(attachment_url, safe="")
    url = f"https://www.notion.so/image/{encoded}?table=block&id={block_id}&spaceId={space_id}&width=2000&cache=v2"
    r = client.session.get(url)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    return len(r.content)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Extract all images from a Notion page (read-only).")
    parser.add_argument("page", help="Notion URL or page ID.")
    parser.add_argument("--work-dir", default="C:/tmp/notion_images", help="Output directory; a subfolder is created per page.")
    parser.add_argument("--max-width", type=int, default=1024, help="WebP max width (pixels).")
    parser.add_argument("--quality", type=int, default=60, help="WebP quality 0-100.")
    parser.add_argument("--keep-originals", action="store_true", help="Keep the downloaded JPG/HEIC files alongside WebP.")
    args = parser.parse_args()
    page_id = parse_page_id(args.page)

    client = create_client()
    images, space_id, title = collect_image_blocks(client, page_id)
    work_dir = Path(args.work_dir) / safe_name(title).replace(" ", "_")
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"Page:     {title!r}")
    print(f"Output:   {work_dir}")
    print(f"Images:   {len(images)}\n")

    total_orig = 0
    total_webp = 0
    originals: list[Path] = []
    for index, (block_id, attachment_url) in enumerate(images, 1):
        filename = attachment_url.split(":")[-1] if ":" in attachment_url else attachment_url
        suffix = Path(filename).suffix or ".jpg"
        orig_path = work_dir / f"image_{index:02}{suffix}"
        webp_path = work_dir / f"image_{index:02}.webp"
        orig_size = download_via_proxy(client, block_id, attachment_url, space_id, orig_path)
        webp_size = convert_image(orig_path, webp_path, "webp", args.max_width, args.quality)
        print(f"  [{index:02}] {orig_size:>9,}B -> {webp_size:>7,}B  {webp_path.name}")
        total_orig += orig_size
        total_webp += webp_size
        originals.append(orig_path)

    if not args.keep_originals:
        for p in originals:
            p.unlink()
        print(f"\nRemoved {len(originals)} originals (use --keep-originals to retain).")
    if total_orig:
        print(f"\nTotal: {total_orig:,}B -> {total_webp:,}B WebP ({100 * total_webp / total_orig:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
