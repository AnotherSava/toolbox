"""EXAMPLE: overwrite a Notion page with the English/sorted content from tripster_translate.

Trashes the page's content blocks, sets a new English title, and appends the same bulleted list
`tripster_translate.py` produces. Preserves the page URL and any inbound links.

The target page ID and country data live in the gitignored `tools/notion/config/tripster_data.py`.

Run from project root:
    python tools/notion/docs/examples/tripster_replace.py
"""

import sys
import uuid

sys.path.insert(0, "tools/notion/src")
sys.path.insert(0, "tools/notion/docs/examples")
sys.path.insert(0, "tools/notion/config")
from client import create_client  # noqa: E402
from tripster_data import COUNTRIES, PAGE_ID  # noqa: E402
from tripster_translate import build_country_ops, map_link_ops, sort_key  # noqa: E402

NEW_TITLE = "Visited countries/cities (tripster)"


def fetch_page(client, page_id: str) -> dict:
    r = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": page_id}, "version": -1}],
    }).json()
    page = r.get("recordMap", {}).get("block", {}).get(page_id, {}).get("value", {}).get("value")
    if not page:
        raise SystemExit(f"Page {page_id} not found.")
    return page


def main() -> int:
    client = create_client()
    page = fetch_page(client, PAGE_ID)
    space_id = page["space_id"]
    old_children = page.get("content") or []
    print(f"Page space: {space_id}")
    print(f"Old child blocks: {len(old_children)}")

    if old_children:
        r = client.post("deleteBlocks", {"blockIds": old_children, "permanentlyDelete": False})
        r.raise_for_status()
        print(f"  trashed {len(old_children)} child blocks")

    ops: list[dict] = [
        {"id": PAGE_ID, "table": "block", "path": ["properties", "title"],
         "command": "set", "args": [[NEW_TITLE]]},
    ]
    ops.extend(map_link_ops(PAGE_ID, space_id))
    for country, cities in sorted(COUNTRIES, key=lambda kv: sort_key(kv[0])):
        ops.extend(build_country_ops(country, cities, PAGE_ID, space_id))

    r = client.post("saveTransactionsFanout", {
        "requestId": str(uuid.uuid4()),
        "transactions": [{
            "id": str(uuid.uuid4()),
            "spaceId": space_id,
            "debug": {"userAction": "tripster_replace"},
            "operations": ops,
        }],
    })
    if r.status_code != 200:
        print(f"ERROR {r.status_code}: {r.text[:500]}")
        return 1
    print(f"  applied {len(ops)} operations to page")

    short = PAGE_ID.replace("-", "")
    print(f"\nDone. Page now lives at: https://www.notion.so/{short}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
