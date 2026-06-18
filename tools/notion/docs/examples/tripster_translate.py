"""EXAMPLE: create an English-translated, list-formatted sibling page next to a source Notion page.

One-off: reads a single Notion page whose content is a Russian "Country: city1, city2; Country2: ..."
flat-text dump and creates a new sibling page (same parent) with one bulleted item per country,
formatted as **Country**: city1, city2, ... — English names, native-script names in parentheses
where the place is genuinely less well known. Countries with an official federal-style first-level
subdivision (US, Canada, Russia, Germany, Belgium, Switzerland, Japan) get nested as **Country** →
**Subdivision**: cities.

The translated/sorted data and source page ID live in the gitignored module
`tools/notion/config/tripster_data.py` (see this directory's README for the expected shape).

NOT a polished CLI tool. Adapt for similar translate-and-reformat jobs.

Run from project root:
    python tools/notion/docs/examples/tripster_translate.py
"""

import sys
import unicodedata
import uuid

sys.path.insert(0, "tools/notion/src")
sys.path.insert(0, "tools/notion/config")
from client import create_client  # noqa: E402
from tripster_data import COUNTRIES, MAP_URL, PAGE_ID  # noqa: E402

NEW_TITLE = "Visited countries/cities (tripster) — English"


def sort_key(s: str) -> str:
    """ASCII-folded, case-insensitive sort key for diacritic-aware alphabetization."""
    folded = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return folded.casefold()


def is_nested(cities) -> bool:
    """True if a country's cities entry is a list of (subdivision, [cities]) pairs."""
    return bool(cities) and isinstance(cities[0], (tuple, list))


def bullet_block(block_id: str, title_runs: list, parent_id: str, parent_table: str, space_id: str) -> dict:
    """Return the saveTransactionsFanout 'set' op for a bulleted_list block."""
    return {"id": block_id, "table": "block", "path": [], "command": "set", "args": {
        "id": block_id, "type": "bulleted_list",
        "properties": {"title": title_runs},
        "parent_id": parent_id, "parent_table": parent_table,
        "space_id": space_id, "alive": True,
    }}


def list_after(parent_id: str, child_id: str) -> dict:
    """Return the saveTransactionsFanout op that appends child to parent.content."""
    return {"id": parent_id, "table": "block", "path": ["content"],
            "command": "listAfter", "args": {"id": child_id}}


def build_country_ops(country: str, cities, page_id: str, space_id: str) -> list[dict]:
    """Return ops creating a country bullet (and any nested subdivision sub-bullets) under page_id."""
    ops: list[dict] = []
    bid = str(uuid.uuid4())
    if is_nested(cities):
        ops.append(bullet_block(bid, [[country, [["b"]]]], page_id, "block", space_id))
        ops.append(list_after(page_id, bid))
        for subdivision, sub_cities in sorted(cities, key=lambda kv: sort_key(kv[0])):
            sid = str(uuid.uuid4())
            sorted_cities = sorted(sub_cities, key=sort_key)
            runs = [[subdivision, [["b"]]], [f": {', '.join(sorted_cities)}"]]
            ops.append(bullet_block(sid, runs, bid, "block", space_id))
            ops.append(list_after(bid, sid))
    else:
        sorted_cities = sorted(cities, key=sort_key)
        runs = [[country, [["b"]]], [f": {', '.join(sorted_cities)}"]]
        ops.append(bullet_block(bid, runs, page_id, "block", space_id))
        ops.append(list_after(page_id, bid))
    return ops


def map_link_ops(parent_id: str, space_id: str) -> list[dict]:
    """Return ops creating the 'Map: <url>' text block as a child of parent_id."""
    bid = str(uuid.uuid4())
    return [
        {"id": bid, "table": "block", "path": [], "command": "set", "args": {
            "id": bid, "type": "text",
            "properties": {"title": [["Map: "], [MAP_URL, [["a", MAP_URL]]]]},
            "parent_id": parent_id, "parent_table": "block",
            "space_id": space_id, "alive": True,
        }},
        list_after(parent_id, bid),
    ]


def fetch_source_metadata(client) -> dict:
    """Return the source page's space_id and parent_id/parent_table."""
    r = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": PAGE_ID}, "version": -1}],
    }).json()
    page = r.get("recordMap", {}).get("block", {}).get(PAGE_ID, {}).get("value", {}).get("value")
    if not page:
        raise SystemExit(f"Source page {PAGE_ID} not found or no access.")
    return {
        "space_id": page["space_id"],
        "parent_id": page["parent_id"],
        "parent_table": page["parent_table"],
    }


def build_operations(meta: dict) -> tuple[str, list[dict]]:
    """Return (new_page_id, operations) for the saveTransactionsFanout call."""
    new_page_id = str(uuid.uuid4())
    space_id = meta["space_id"]

    ops: list[dict] = [
        {"id": new_page_id, "table": "block", "path": [], "command": "set", "args": {
            "id": new_page_id, "type": "page",
            "properties": {"title": [[NEW_TITLE]]},
            "parent_id": meta["parent_id"], "parent_table": meta["parent_table"],
            "space_id": space_id, "alive": True,
        }},
    ]
    ops.extend(map_link_ops(new_page_id, space_id))
    for country, cities in sorted(COUNTRIES, key=lambda kv: sort_key(kv[0])):
        ops.extend(build_country_ops(country, cities, new_page_id, space_id))
    return new_page_id, ops


def main() -> int:
    client = create_client()
    meta = fetch_source_metadata(client)
    print(f"Source space: {meta['space_id']}")
    print(f"Source parent: {meta['parent_id']} ({meta['parent_table']})")

    new_page_id, ops = build_operations(meta)
    print(f"\nNew page ID: {new_page_id}")
    print(f"Operations: {len(ops)}")

    r = client.post("saveTransactionsFanout", {
        "requestId": str(uuid.uuid4()),
        "transactions": [{
            "id": str(uuid.uuid4()),
            "spaceId": meta["space_id"],
            "debug": {"userAction": "tripster_translate"},
            "operations": ops,
        }],
    })
    if r.status_code != 200:
        print(f"\nERROR {r.status_code}:")
        print(r.text[:2000])
        return 1

    short = new_page_id.replace("-", "")
    print(f"\nDone. URL: https://www.notion.so/{short}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
