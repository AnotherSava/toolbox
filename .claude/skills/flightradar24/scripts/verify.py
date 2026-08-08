"""Print the state of the Notion flights database, for post-sync verification.

Reports the row count, the Trip select options, each view's group count and
conditional-color rules, and the tail of the table with the derived values that
are easy to get wrong — trip, parity, and which location cells came out bold.

    python .claude/skills/flightradar24/scripts/verify.py <notion-page-url> [--tail N]
"""

import argparse
import sys

from notion_tools.client import create_client
from notion_tools.page_ids import parse_page_id

from row_props import is_bold, iso_date, plain
from sync import find_collection


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Verify the Notion flights database after a sync.")
    parser.add_argument("page", help="Notion URL or page ID of the host page.")
    parser.add_argument("--tail", type=int, default=8, help="How many trailing rows to show (default: 8).")
    args = parser.parse_args()

    client = create_client()
    collection_id, space_id, view_ids = find_collection(client, parse_page_id(args.page))

    collection = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "collection", "id": collection_id}, "version": -1}],
    }).json()["recordMap"]["collection"][collection_id]["value"]["value"]
    options = collection["schema"]["trip"].get("options", [])
    print(f"trip options: {len(options)}  last: {[(o['value'], o['color']) for o in options[-3:]]}")

    views = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "collection_view", "id": v}, "version": -1} for v in view_ids],
    }).json().get("recordMap", {}).get("collection_view", {})
    for view_id in view_ids:
        view = views.get(view_id, {}).get("value", {}).get("value", {})
        fmt = view.get("format", {})
        groups = fmt.get("collection_groups", [])
        print(f"view {view.get('name', '?'):16} groups={len(groups):4} "
              f"last={[g['value'].get('value') for g in groups[-3:]]} "
              f"color_rules={len(fmt.get('conditional_color_rules', []))}")

    resp = client.post("queryCollection", {
        "collectionId": collection_id,
        "collectionViewId": view_ids[0],
        "loader": {"type": "reducer", "reducers": {"results": {"type": "results", "limit": 10000}},
                   "searchQuery": "", "userTimeZone": "UTC"},
        "query": {},
        "source": {"type": "collection", "id": collection_id, "spaceId": space_id},
    })
    resp.raise_for_status()
    rows = []
    for entry in resp.json().get("recordMap", {}).get("block", {}).values():
        row = entry.get("value", {})
        row = row.get("value", row)
        if row.get("parent_id") == collection_id and row.get("alive"):
            rows.append(row.get("properties", {}))
    print(f"\ntotal rows: {len(rows)}")

    for props in sorted(rows, key=lambda p: (iso_date(p), plain(p, "dep")))[-args.tail:]:
        from_bold = " *BOLD" if is_bold(props, "from_loc") else ""
        to_bold = " *BOLD" if is_bold(props, "to_loc") else ""
        print(f"  {iso_date(props)}  {plain(props, 'title'):12} {plain(props, 'trip'):5} {plain(props, 'parity')}  "
              f"{plain(props, 'flight_no'):8} {plain(props, 'airline'):18}")
        print(f"      from={plain(props, 'from_loc')}{from_bold}   to={plain(props, 'to_loc')}{to_bold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
