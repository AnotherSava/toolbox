"""EXAMPLE: migrate a "plain page" of (text, image) pairs into an embedded sub-collection.

This is a snapshot of a one-off workflow used to convert hand-rolled lists (alternating
title + image blocks) into proper Notion databases. It mutates the page in place: creates
a new gallery sub-collection, adds a row per (text, image) pair, uploads WebP-optimized
images as the Picture property, then trashes the original blocks.

NOT a polished CLI tool — copy and adapt for similar one-off jobs. The recurring need for
this codebase is image *optimization* (`image-opt`), not Notion structural migrations.

Adapt-it-yourself notes:
- Cache filenames include the attachment UUID so duplicate titles don't collide on disk.
- Pairing is strict (text + image): handle headers, dividers, etc. yourself if needed.
- If something goes wrong mid-run, `getActivityLog` recovers the trashed blocks
  (see notion-api-quirks.md).

To run as-is from the project root:
    python tools/notion/docs/examples/plain_to_collection.py <page-url-or-id>
"""

import argparse
import sys
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from image_opt.main import convert_image
from notion_tools.client import NotionClient, create_client
from notion_tools.optimize_images import parse_page_id, upload_image

PICT_KEY = "pict"


@dataclass
class Item:
    """One pair of source blocks plus their derived files on disk."""
    text_block_id: str
    image_block_id: str
    title: str
    attachment_url: str
    filename: str
    local_path: Path = field(default=None)
    webp_path: Path = field(default=None)


def safe_name(text: str) -> str:
    """Filesystem-safe variant of a string (Windows-friendly)."""
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in text)[:60].strip()


def load_host_page(client: NotionClient, page_id: str) -> dict:
    """Fetch a single page record."""
    resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": page_id}, "version": -1}],
    }).json()
    page = resp.get("recordMap", {}).get("block", {}).get(page_id, {}).get("value", {}).get("value")
    if not page:
        raise SystemExit(f"Page {page_id} not found or no access.")
    return page


def pair_items(client: NotionClient, page: dict) -> list[Item]:
    """Walk the page's content array and produce (text, image) pairs."""
    children = page.get("content") or []
    block_records: dict = {}
    for i in range(0, len(children), 100):
        chunk = children[i:i + 100]
        r = client.post("syncRecordValues", {
            "requests": [{"pointer": {"table": "block", "id": bid}, "version": -1} for bid in chunk],
        }).json()
        block_records.update(r.get("recordMap", {}).get("block", {}))

    items: list[Item] = []
    i = 0
    while i < len(children) - 1:
        a = block_records[children[i]]["value"]["value"]
        b = block_records[children[i + 1]]["value"]["value"]
        if a.get("type") == "text" and b.get("type") == "image":
            title = "".join(p[0] if p else "" for p in a.get("properties", {}).get("title") or []).strip()
            src = (b.get("properties", {}).get("source") or [[None]])[0][0]
            if src:
                filename = src.split(":")[-1] if ":" in src else src
                items.append(Item(a["id"], b["id"], title, src, filename))
            i += 2
        else:
            print(f"  unexpected pattern at {i}: {a.get('type')} + {b.get('type')}")
            i += 1
    return items


def download_originals(client: NotionClient, items: list[Item], work_dir: Path, space_id: str) -> None:
    """Download each item's original image via Notion's image proxy."""
    for it in items:
        attach_uuid = it.attachment_url.split(":")[1] if it.attachment_url.startswith("attachment:") else "raw"
        stub = f"{safe_name(it.title)}__{attach_uuid[:8]}__{Path(it.filename).stem}"
        out = work_dir / f"{stub}{Path(it.filename).suffix or '.bin'}"
        if out.exists() and out.stat().st_size > 0:
            print(f"  cached: {out.name}")
            it.local_path = out
            continue
        encoded = urllib.parse.quote(it.attachment_url, safe="")
        url = f"https://www.notion.so/image/{encoded}?table=block&id={it.image_block_id}&spaceId={space_id}&width=2000&cache=v2"
        r = client.session.get(url)
        r.raise_for_status()
        out.write_bytes(r.content)
        print(f"  {len(r.content):>8,}B  {out.name}")
        it.local_path = out


def create_subcollection(client: NotionClient, host_page_id: str, items: list[Item], space_id: str) -> tuple[str, list[str]]:
    """Create the embedded collection_view block, collection, view, and one row per item.

    All operations are sent in a single saveTransactionsFanout call.
    Returns (collection_id, [row_id, ...]) in the same order as items.
    """
    cv_block_id = str(uuid.uuid4())
    collection_id = str(uuid.uuid4())
    view_id = str(uuid.uuid4())
    row_ids = [str(uuid.uuid4()) for _ in items]

    ops = [
        {"id": cv_block_id, "table": "block", "path": [], "command": "set", "args": {
            "id": cv_block_id, "type": "collection_view",
            "view_ids": [view_id], "collection_id": collection_id,
            "format": {
                "collection_pointer": {"id": collection_id, "table": "collection", "spaceId": space_id},
                "collection_pointers": [{"id": collection_id, "table": "collection", "spaceId": space_id}],
            },
            "parent_id": host_page_id, "parent_table": "block",
            "space_id": space_id, "alive": True,
        }},
        {"id": collection_id, "table": "collection", "path": [], "command": "set", "args": {
            "id": collection_id,
            "schema": {
                "title": {"name": "Name", "type": "title"},
                PICT_KEY: {"name": "Picture", "type": "file"},
            },
            "parent_id": cv_block_id, "parent_table": "block",
            "space_id": space_id, "alive": True, "migrated": True,
        }},
        {"id": view_id, "table": "collection_view", "path": [], "command": "set", "args": {
            "id": view_id, "type": "gallery",
            "format": {
                "card_layout": {"mode": "list"},
                "gallery_cover": {"type": "property", "property": PICT_KEY},
                "gallery_cover_size": "large",
                "gallery_cover_aspect": "contain",
                "table_wrap": True,
                "collection_pointer": {"id": collection_id, "table": "collection", "spaceId": space_id},
                "table_properties": [
                    {"property": "title", "visible": True, "width": 280},
                    {"property": PICT_KEY, "visible": True},
                ],
            },
            "parent_id": cv_block_id, "parent_table": "block",
            "space_id": space_id, "alive": True,
        }},
        {"id": host_page_id, "table": "block", "path": ["content"], "command": "listAfter", "args": {"id": cv_block_id}},
    ]
    for rid, it in zip(row_ids, items):
        ops.append({"id": rid, "table": "block", "path": [], "command": "set", "args": {
            "id": rid, "type": "page",
            "properties": {"title": [[it.title]]},
            "parent_id": collection_id, "parent_table": "collection",
            "space_id": space_id, "alive": True,
        }})

    r = client.post("saveTransactionsFanout", {
        "requestId": str(uuid.uuid4()),
        "transactions": [{
            "id": str(uuid.uuid4()),
            "spaceId": space_id,
            "debug": {"userAction": "plain_to_collection"},
            "operations": ops,
        }],
    })
    r.raise_for_status()
    return collection_id, row_ids


def attach_pictures(client: NotionClient, items: list[Item], row_ids: list[str], space_id: str) -> None:
    """Upload each item's WebP and set the Picture property on its row."""
    for rid, it in zip(row_ids, items):
        attach_url = upload_image(client, it.webp_path, rid, space_id, "image/webp")
        sr = client.post("saveTransactionsFanout", {
            "requestId": str(uuid.uuid4()),
            "transactions": [{
                "id": str(uuid.uuid4()),
                "spaceId": space_id,
                "debug": {"userAction": "set_picture"},
                "operations": [{
                    "id": rid, "table": "block",
                    "path": ["properties", PICT_KEY],
                    "command": "set",
                    "args": [[it.webp_path.name, [["a", attach_url]]]],
                }],
            }],
        })
        sr.raise_for_status()
        print(f"  {it.title}")


def trash_blocks(client: NotionClient, ids: list[str], chunk_size: int = 10) -> None:
    """Move blocks to trash in batches."""
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i:i + chunk_size]
        client.post("deleteBlocks", {"blockIds": chunk, "permanentlyDelete": False}).raise_for_status()
        print(f"  trashed {len(chunk)}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Migrate a plain (text, image) page into an embedded sub-collection.")
    parser.add_argument("page", help="Notion URL or page ID of the host page.")
    parser.add_argument("--work-dir", default="C:/tmp/notion_images", help="Local directory for downloads and converted files.")
    parser.add_argument("--max-width", type=int, default=1024, help="Resize images wider than this (pixels).")
    parser.add_argument("--quality", type=int, default=60, help="WebP quality 0-100; lower = smaller files.")
    args = parser.parse_args()
    host_page_id = parse_page_id(args.page)

    client = create_client()
    page = load_host_page(client, host_page_id)
    space_id = page["space_id"]
    page_title = (page.get("properties", {}).get("title") or [["page"]])[0][0]
    work_dir = Path(args.work_dir) / safe_name(page_title).replace(" ", "_")
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"Host page: {page_title!r} ({host_page_id})")
    print(f"Work dir:  {work_dir}\n")

    print("Step 1: pairing children...")
    items = pair_items(client, page)
    print(f"  paired {len(items)} items.")

    print("\nStep 2: downloading originals...")
    download_originals(client, items, work_dir, space_id)

    print(f"\nStep 3: converting to WebP ({args.max_width} wide, q={args.quality})...")
    for it in items:
        webp = it.local_path.with_suffix(".webp")
        out_size = convert_image(it.local_path, webp, "webp", args.max_width, args.quality)
        print(f"  {it.local_path.stat().st_size:>8,}B -> {out_size:>7,}B  {webp.name}")
        it.webp_path = webp

    print("\nStep 4: creating sub-collection + rows...")
    collection_id, row_ids = create_subcollection(client, host_page_id, items, space_id)

    print("\nStep 5: uploading WebPs and setting Picture...")
    attach_pictures(client, items, row_ids, space_id)

    print("\nStep 6: trashing old text/image blocks...")
    old_ids = [bid for it in items for bid in (it.text_block_id, it.image_block_id)]
    trash_blocks(client, old_ids)

    print(f"\nDone. New collection_id: {collection_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
