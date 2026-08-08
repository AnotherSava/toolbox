"""Prove a sync only appended — existing rows and view formatting must be untouched.

Two independent checks, because they catch opposite failures:

* **Snapshot diff** — take ``--snapshot`` before the sync and ``--against`` it after.
  Every row that existed before must still be there with identical properties, and
  each view's column layout and colour rules must be unchanged, with group entries
  only ever *added*. This is what proves the sync appended and did nothing else.

* **CSV reconciliation** — always runs. Every live row must equal the value recomputed
  from the full CSV. This catches the *opposite* failure: a row that should have
  changed but didn't. An append-only sync never revisits existing rows, yet trip
  numbers renumber when a flight is back-filled mid-history, and a newly added flight
  can flip the previous flight's layover/stay flag (and therefore its bold marker).

Usage::

    python .../reconcile.py <page-url> --snapshot before.json     # before syncing
    python .../reconcile.py <page-url> --against  before.json     # after syncing

Exits non-zero if either check fails, so it can gate a sync.
"""

import argparse
import json
import sys
from pathlib import Path

from notion_tools.client import NotionClient, create_client
from notion_tools.page_ids import parse_page_id

from airports import load_airports
from flights import assign_origin_changes, assign_stays, assign_trips, parse_flights
from notion_db import SCHEMA, _row_properties
from row_props import label, row_key
from sync import find_collection, flight_key

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "tools" / "flightradar" / "data"
SCHEMA_KEYS = [key for key, _name, _type in SCHEMA]


def _canonical(props: dict) -> str:
    """Stable string form of the schema-owned part of a row's properties."""
    return json.dumps({k: props[k] for k in SCHEMA_KEYS if k in props}, sort_keys=True, ensure_ascii=False)


def fetch_rows(client: NotionClient, collection_id: str, space_id: str, view_id: str) -> dict[str, dict]:
    """Return ``{row_id: properties}`` for every live row in the collection."""
    resp = client.post("queryCollection", {
        "collectionId": collection_id,
        "collectionViewId": view_id,
        "loader": {"type": "reducer", "reducers": {"results": {"type": "results", "limit": 10000}},
                   "searchQuery": "", "userTimeZone": "UTC"},
        "query": {},
        "source": {"type": "collection", "id": collection_id, "spaceId": space_id},
    })
    resp.raise_for_status()
    rows = {}
    for entry in resp.json().get("recordMap", {}).get("block", {}).values():
        row = entry.get("value", {})
        row = row.get("value", row)
        if row.get("parent_id") == collection_id and row.get("alive"):
            rows[row["id"]] = row.get("properties", {})
    return rows


def fetch_views(client: NotionClient, view_ids: list[str]) -> dict[str, dict]:
    """Fingerprint each view's layout: columns, colour rules and group entries."""
    records = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "collection_view", "id": v}, "version": -1} for v in view_ids],
    }).json().get("recordMap", {}).get("collection_view", {})
    views = {}
    for view_id in view_ids:
        view = records.get(view_id, {}).get("value", {}).get("value", {})
        fmt = view.get("format", {})
        views[view_id] = {
            "name": view.get("name", "?"),
            "columns": json.dumps(fmt.get("table_properties", []), sort_keys=True),
            "color_rules": json.dumps(fmt.get("conditional_color_rules", []), sort_keys=True),
            "query": json.dumps(view.get("query2", {}), sort_keys=True),
            "groups": [
                {"value": g.get("value", {}).get("value"), "hidden": g.get("hidden", False)}
                for g in fmt.get("collection_groups", [])
            ],
        }
    return views


def capture(client: NotionClient, collection_id: str, space_id: str, view_ids: list[str]) -> dict:
    """Snapshot the whole table: per-row fingerprints plus per-view layout."""
    rows = fetch_rows(client, collection_id, space_id, view_ids[0])
    return {
        "rows": {rid: _canonical(props) for rid, props in rows.items()},
        "labels": {rid: label(props) for rid, props in rows.items()},
        "views": fetch_views(client, view_ids),
    }


def compare(before: dict, after: dict) -> list[str]:
    """Report every way ``after`` is not ``before`` plus appended rows/groups."""
    problems: list[str] = []
    old_rows, new_rows = before["rows"], after["rows"]

    removed = sorted(set(old_rows) - set(new_rows))
    for rid in removed:
        problems.append(f"ROW REMOVED: {before['labels'].get(rid, rid)}")

    modified = sorted(rid for rid in set(old_rows) & set(new_rows) if old_rows[rid] != new_rows[rid])
    for rid in modified:
        problems.append(f"ROW MODIFIED: {after['labels'].get(rid, rid)}")

    added = sorted(set(new_rows) - set(old_rows))
    print(f"  rows before={len(old_rows)} after={len(new_rows)} added={len(added)} "
          f"modified={len(modified)} removed={len(removed)}")
    for rid in added:
        print(f"    + {after['labels'].get(rid, rid)}")

    for view_id, new_view in after["views"].items():
        old_view = before["views"].get(view_id)
        name = new_view["name"]
        if old_view is None:
            problems.append(f"VIEW ADDED: {name}")
            continue
        for field, description in (("columns", "column layout"), ("color_rules", "conditional colour rules"),
                                   ("query", "sort/group query")):
            if old_view[field] != new_view[field]:
                problems.append(f"VIEW CHANGED ({name}): {description} differs")
        old_groups, new_groups = old_view["groups"], new_view["groups"]
        # Existing group entries must survive verbatim and in order; only additions are allowed.
        kept = [g for g in new_groups if any(g["value"] == o["value"] for o in old_groups)]
        if kept != old_groups:
            problems.append(f"VIEW CHANGED ({name}): existing group entries reordered, hidden or dropped")
        gained = [g["value"] for g in new_groups if all(g["value"] != o["value"] for o in old_groups)]
        print(f"  view {name:16} groups {len(old_groups)} -> {len(new_groups)}"
              + (f", added {gained}" if gained else ""))
    for view_id in set(before["views"]) - set(after["views"]):
        problems.append(f"VIEW REMOVED: {before['views'][view_id]['name']}")
    return problems


def reconcile_csv(client: NotionClient, collection_id: str, space_id: str, view_id: str, csv_path: Path) -> list[str]:
    """Check every live row still equals what the full CSV says it should be."""
    airports = load_airports(DATA_DIR / "ourairports")
    flights = parse_flights(csv_path, airports)
    assign_trips(flights)
    assign_stays(flights)
    assign_origin_changes(flights)
    expected = {flight_key(f): _canonical(_row_properties(f)) for f in flights}

    live = fetch_rows(client, collection_id, space_id, view_id)
    problems: list[str] = []
    seen: dict[tuple, str] = {}
    for rid, props in live.items():
        key = row_key(props)
        if key in seen:
            problems.append(f"DUPLICATE ROW: {label(props)}")
            continue
        seen[key] = rid
        if key not in expected:
            problems.append(f"ROW NOT IN CSV: {label(props)}")
        elif expected[key] != _canonical(props):
            problems.append(f"ROW DRIFTED FROM CSV: {label(props)}")
    for key in expected:
        if key not in seen:
            problems.append(f"CSV FLIGHT MISSING FROM NOTION: {key[0]} {key[2]}->{key[3]} {key[1]}")
    print(f"  csv flights={len(expected)} notion rows={len(live)} matched={len(seen) - len(problems) if problems else len(seen)}")
    return problems


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Verify a sync only appended rows.")
    parser.add_argument("page", help="Notion URL or page ID of the host page.")
    parser.add_argument("--snapshot", help="Write the current state to this file (run before syncing).")
    parser.add_argument("--against", help="Compare the current state to this snapshot (run after syncing).")
    parser.add_argument("--csv", default=str(DATA_DIR / "flights.csv"), help="CSV to reconcile against.")
    parser.add_argument("--skip-csv", action="store_true", help="Skip the CSV reconciliation check.")
    args = parser.parse_args()

    client = create_client()
    collection_id, space_id, view_ids = find_collection(client, parse_page_id(args.page))
    if not view_ids:
        raise SystemExit("Collection has no views to query.")

    if args.snapshot:
        state = capture(client, collection_id, space_id, view_ids)
        Path(args.snapshot).write_text(json.dumps(state), encoding="utf-8")
        print(f"Snapshot: {len(state['rows'])} rows, {len(state['views'])} views -> {args.snapshot}")
        if not args.against and args.skip_csv:
            return 0

    problems: list[str] = []
    if args.against:
        before = json.loads(Path(args.against).read_text(encoding="utf-8"))
        print("\nAppend-only check (vs snapshot):")
        problems += compare(before, capture(client, collection_id, space_id, view_ids))

    if not args.skip_csv:
        print("\nCSV reconciliation:")
        problems += reconcile_csv(client, collection_id, space_id, view_ids[0], Path(args.csv))

    if problems:
        print(f"\nFAILED — {len(problems)} problem(s):")
        for p in problems:
            print(f"  ! {p}")
        return 1
    print("\nOK — existing rows and view layout unchanged; every row matches the CSV.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
