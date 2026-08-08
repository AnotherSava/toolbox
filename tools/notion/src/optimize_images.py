"""Download images from a Notion sub-collection, convert (WebP or AVIF), re-upload, and consolidate into a file property.

Per row, the tool:
  1. Finds the image source — file property (preferred) or first image block in the row body.
  2. Downloads the original via Notion's image proxy.
  3. Resizes to max width and re-encodes (WebP by default; AVIF available via --format).
  4. Uploads via getUploadFileUrl + S3 PUT.
  5. Sets the row's file property to the new attachment.
  6. Deletes the body image block if the source was there.

Input: the page ID of a row that contains a single embedded collection_view (Notion's
"linked database" / inline sub-database pattern). The tool auto-detects the collection,
view, space, and picture property.
"""

import argparse
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from image_opt.main import FORMAT_INFO as _IMAGE_OPT_FORMATS, convert_image

from .client import NotionClient, create_client
from .page_ids import parse_page_id


@dataclass
class CollectionContext:
    """Resolved IDs needed to query and mutate the sub-collection."""
    collection_id: str
    view_id: str
    space_id: str
    picture_prop_key: str


@dataclass
class ImageSource:
    """Where an image lives for a given row."""
    row_id: str
    row_title: str
    in_picture: bool
    body_block_id: Optional[str]
    attachment_url: str
    filename: str


def resolve_collection_context(client: NotionClient, host_page_id: str) -> CollectionContext:
    """Find the embedded collection_view inside host_page_id and resolve all IDs."""
    resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": host_page_id}, "version": -1}]
    }).json()
    page = resp.get("recordMap", {}).get("block", {}).get(host_page_id, {}).get("value", {}).get("value", {})
    if not page:
        raise SystemExit(f"Page {host_page_id} not found or no access.")
    children = page.get("content") or []
    cv_block_id = None
    cv_block = None
    for cid in children:
        cresp = client.post("syncRecordValues", {
            "requests": [{"pointer": {"table": "block", "id": cid}, "version": -1}]
        }).json()
        b = cresp.get("recordMap", {}).get("block", {}).get(cid, {}).get("value", {}).get("value", {})
        if b.get("type") in ("collection_view", "collection_view_page"):
            cv_block_id = cid
            cv_block = b
            break
    if not cv_block:
        raise SystemExit(f"No collection_view block found inside page {host_page_id}.")

    collection_id = cv_block.get("collection_id") or cv_block.get("format", {}).get("collection_pointer", {}).get("id")
    view_ids = cv_block.get("view_ids") or []
    space_id = cv_block.get("space_id")
    if not (collection_id and view_ids and space_id):
        raise SystemExit("Missing collection/view/space metadata on collection_view block.")

    coll_resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "collection", "id": collection_id}, "version": -1}]
    }).json()
    coll = coll_resp.get("recordMap", {}).get("collection", {}).get(collection_id, {}).get("value", {}).get("value", {})
    schema = coll.get("schema") or {}
    picture_prop_key = next((key for key, prop in schema.items() if prop.get("type") == "file"), None)
    if not picture_prop_key:
        raise SystemExit("No file-type column found in collection schema.")
    return CollectionContext(collection_id, view_ids[0], space_id, picture_prop_key)


def _parse_picture_property(prop: list) -> Optional[tuple[str, str]]:
    """Extract (filename, attachment_url) from a Picture property value."""
    if not prop:
        return None
    for item in prop:
        if isinstance(item, list) and len(item) >= 2 and isinstance(item[1], list):
            for marker in item[1]:
                if marker and marker[0] == "a":
                    return item[0], marker[1]
    return None


def _parse_image_block(block: dict) -> Optional[tuple[str, str]]:
    """Extract (filename, attachment_url) from an image block's source property."""
    src = block.get("properties", {}).get("source", [])
    if not src or not src[0]:
        return None
    url = src[0][0]
    filename = url.split(":")[-1] if ":" in url else url
    return filename, url


def collect_image_sources(client: NotionClient, ctx: CollectionContext) -> list[ImageSource]:
    """Walk the collection and return one ImageSource per row that has an image."""
    qresult = client.post("queryCollection", {
        "collection": {"id": ctx.collection_id},
        "collectionView": {"id": ctx.view_id},
        "loader": {"type": "reducer", "reducers": {"collection_group_results": {"type": "results", "limit": 500}}, "searchQuery": "", "userTimeZone": "UTC"},
    }).json()
    block_ids = qresult["result"]["reducerResults"]["collection_group_results"]["blockIds"]
    rows = qresult["recordMap"]["block"]

    body_ids: list[str] = []
    row_meta: list[tuple[str, str, list[str], list]] = []
    for rid in block_ids:
        row = rows[rid]["value"]["value"]
        title = (row.get("properties", {}).get("title") or [["(untitled)"]])[0][0]
        content = row.get("content", []) or []
        pic = row.get("properties", {}).get(ctx.picture_prop_key)
        body_ids.extend(content)
        row_meta.append((rid, title, content, pic))

    body_blocks: dict = {}
    for i in range(0, len(body_ids), 100):
        chunk = body_ids[i:i + 100]
        resp = client.post("syncRecordValues", {
            "requests": [{"pointer": {"table": "block", "id": bid}, "version": -1} for bid in chunk],
        }).json()
        body_blocks.update(resp.get("recordMap", {}).get("block", {}))

    sources: list[ImageSource] = []
    for rid, title, content, pic in row_meta:
        parsed = _parse_picture_property(pic) if pic else None
        if parsed:
            filename, url = parsed
            sources.append(ImageSource(rid, title, True, None, url, filename))
            continue
        for bid in content:
            blk = body_blocks.get(bid, {}).get("value", {}).get("value", {})
            if blk.get("type") == "image":
                parsed_block = _parse_image_block(blk)
                if parsed_block:
                    filename, url = parsed_block
                    sources.append(ImageSource(rid, title, False, bid, url, filename))
                break
    return sources


def safe_filename(title: str, original: str, suffix: str) -> str:
    """Build a filename safe for Windows that includes the row title for traceability."""
    keep = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:60].strip()
    stem = Path(original).stem
    return f"{keep}__{stem}{suffix}"


def download_via_proxy(client: NotionClient, src: ImageSource, ctx: CollectionContext, out_path: Path) -> int:
    """Download an attachment via Notion's image proxy. Returns bytes written."""
    permission_block_id = src.body_block_id or src.row_id
    encoded = urllib.parse.quote(src.attachment_url, safe="")
    url = f"https://www.notion.so/image/{encoded}?table=block&id={permission_block_id}&spaceId={ctx.space_id}&width=2000&cache=v2"
    r = client.session.get(url)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    return len(r.content)


FORMAT_INFO = {fmt: {**info, "mime": f"image/{fmt}"} for fmt, info in _IMAGE_OPT_FORMATS.items()}


def upload_image(client: NotionClient, file_path: Path, row_id: str, space_id: str, mime: str) -> str:
    """Upload an image file to Notion's storage and return the attachment URL."""
    resp = client.post("getUploadFileUrl", {
        "bucket": "secure",
        "name": file_path.name,
        "contentType": mime,
        "record": {"table": "block", "id": row_id, "spaceId": space_id},
    }).json()
    body = file_path.read_bytes()
    r = requests.put(resp["signedPutUrl"], data=body, headers={"Content-Type": mime})
    r.raise_for_status()
    return resp["url"]


def set_picture_property(client: NotionClient, row_id: str, ctx: CollectionContext, filename: str, attachment_url: str) -> None:
    """Replace the Picture property value on a row."""
    op = {
        "id": row_id,
        "table": "block",
        "path": ["properties", ctx.picture_prop_key],
        "command": "set",
        "args": [[filename, [["a", attachment_url]]]],
    }
    r = client.post("saveTransactionsFanout", {
        "requestId": str(uuid.uuid4()),
        "transactions": [{
            "id": str(uuid.uuid4()),
            "spaceId": ctx.space_id,
            "debug": {"userAction": "optimize_images.set_picture"},
            "operations": [op],
        }],
    })
    r.raise_for_status()


def trash_block(client: NotionClient, block_id: str) -> None:
    """Move a block to trash."""
    r = client.post("deleteBlocks", {"blockIds": [block_id], "permanentlyDelete": False})
    r.raise_for_status()


def build_parser() -> argparse.ArgumentParser:
    """CLI argument parser."""
    p = argparse.ArgumentParser(description="Optimize images in a Notion sub-collection: convert (WebP/AVIF) and consolidate into the Picture property.")
    p.add_argument("page", help="Notion URL or page ID of the row containing the embedded sub-collection.")
    p.add_argument("--work-dir", default="C:/tmp/notion_images", help="Local directory for downloads and converted files.")
    p.add_argument("--format", choices=list(FORMAT_INFO), default="webp", help="Output format. WebP is the safe default — Notion does not preview AVIF in card views.")
    p.add_argument("--max-width", type=int, default=1024, help="Resize images wider than this (pixels).")
    p.add_argument("--quality", type=int, default=60, help="Quality 0-100; lower = smaller files.")
    p.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    return p


def main() -> int:
    """CLI entry point."""
    args = build_parser().parse_args()
    page_id = parse_page_id(args.page)
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    client = create_client()
    ctx = resolve_collection_context(client, page_id)
    print(f"Collection: {ctx.collection_id}")
    print(f"View:       {ctx.view_id}")
    print(f"Space:      {ctx.space_id}")
    print(f"File prop:  {ctx.picture_prop_key}")
    print()

    sources = collect_image_sources(client, ctx)
    in_pic = sum(1 for s in sources if s.in_picture)
    print(f"Found {len(sources)} rows with images ({in_pic} in property, {len(sources) - in_pic} in body).")

    if not args.yes and input("Proceed? (yes/no) ") != "yes":
        return 1

    fmt = FORMAT_INFO[args.format]
    summary: list[tuple[str, int, int, str]] = []
    for i, s in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] {s.row_title[:60]}")
        suffix = Path(s.filename).suffix or ".bin"
        orig_path = work_dir / safe_filename(s.row_title, s.filename, suffix)
        out_path = work_dir / safe_filename(s.row_title, s.filename, fmt["ext"])
        try:
            orig_size = download_via_proxy(client, s, ctx, orig_path)
            out_size = convert_image(orig_path, out_path, args.format, args.max_width, args.quality)
            attachment_url = upload_image(client, out_path, s.row_id, ctx.space_id, fmt["mime"])
            set_picture_property(client, s.row_id, ctx, out_path.name, attachment_url)
            if s.body_block_id:
                trash_block(client, s.body_block_id)
            marker = " (moved from body)" if s.body_block_id else ""
            print(f"   {orig_size:>9,}B -> {out_size:>7,}B {args.format.upper()} ({100*out_size/orig_size:.1f}%){marker}")
            summary.append((s.row_title, orig_size, out_size, "ok"))
        except Exception as e:
            print(f"   FAILED: {e}")
            summary.append((s.row_title, 0, 0, f"failed: {e}"))

    total_orig = sum(s[1] for s in summary)
    total_out = sum(s[2] for s in summary)
    ok_count = sum(1 for s in summary if s[3] == "ok")
    print()
    print(f"Done: {ok_count}/{len(summary)} ok")
    if total_orig:
        print(f"Total: {total_orig:,}B -> {total_out:,}B ({100*total_out/total_orig:.1f}%)")
    failed = [s for s in summary if s[3] != "ok"]
    if failed:
        print(f"Failed:")
        for s in failed:
            print(f"  - {s[0]}: {s[3]}")
    return 0 if not failed else 1
