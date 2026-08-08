"""CLI entry point: import an FR24 CSV export into Notion, or sync new flights into it.

Run directly — these modules are skill-local, not an installed package::

    python .claude/skills/flightradar24/scripts/main.py sync <notion-page-url>

Sibling modules import by bare name because Python puts this script's own
directory first on ``sys.path``. Only ``notion_tools`` comes from the installed
toolbox package.
"""

import argparse
import sys
from pathlib import Path

from notion_tools.client import create_client
from notion_tools.page_ids import parse_page_id

from airports import load_airports
from flights import assign_origin_changes, assign_stays, assign_trips, parse_flights
from notion_db import create_collection, insert_rows
from sync import find_collection, sync_flights

# scripts -> flightradar24 -> skills -> .claude -> repo root. The data cache is
# gitignored and stayed behind in the tools tree when the code moved here.
REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "tools" / "flightradar" / "data"
DEFAULT_CSV = DATA_DIR / "flights.csv"
AIRPORTS_CACHE = DATA_DIR / "ourairports"


def _load_host(client, host_page_id: str) -> dict:
    """Fetch the host page record (used to recover its space_id)."""
    resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": host_page_id}, "version": -1}],
    }).json()
    page = resp.get("recordMap", {}).get("block", {}).get(host_page_id, {}).get("value", {}).get("value")
    if not page:
        raise SystemExit(f"Page {host_page_id} not found or no access.")
    return page


def _load_flights(csv_path: Path):
    """Parse the CSV and derive trips, stays and origin changes over the full history."""
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    print("Step 1: loading airport metadata (OurAirports)...")
    airports = load_airports(AIRPORTS_CACHE)
    print(f"  {len(airports)} code -> airport entries cached.")

    print(f"\nStep 2: parsing flights from {csv_path}...")
    flights = parse_flights(csv_path, airports)
    assign_trips(flights)
    assign_stays(flights)
    assign_origin_changes(flights)
    n_trips = max((f.trip for f in flights), default=0)
    unresolved = [f for f in flights if f.origin is None or f.destination is None]
    print(f"  {len(flights)} flights in {n_trips} trips; {len(unresolved)} have unresolved airports.")
    for f in unresolved[:10]:
        print(f"    ? {f.date}  {f.origin_code or '-':4}({f.origin_raw[:30]:30})  {f.destination_code or '-':4}({f.destination_raw[:30]:30})")
    return flights, n_trips


def _create(args) -> int:
    """Build a brand-new collection on the host page and fill it."""
    flights, n_trips = _load_flights(Path(args.csv))
    host_page_id = parse_page_id(args.page)
    client = create_client()
    space_id = _load_host(client, host_page_id)["space_id"]
    print(f"\nStep 3: creating collection on host page {host_page_id} (space {space_id})...")
    cv_block_id, collection_id = create_collection(client, host_page_id, space_id, n_trips)
    print(f"  collection_view block: {cv_block_id}")
    print(f"  collection id:         {collection_id}")

    print(f"\nStep 4: inserting {len(flights)} rows (batch={args.batch_size})...")
    insert_rows(client, collection_id, space_id, flights, batch_size=args.batch_size)
    print("\nDone.")
    return 0


def _sync(args) -> int:
    """Append flights the existing collection on the host page is missing."""
    flights, _ = _load_flights(Path(args.csv))
    host_page_id = parse_page_id(args.page)
    client = create_client()
    collection_id, space_id, view_ids = find_collection(client, host_page_id)
    print(f"\nStep 3: syncing into collection {collection_id} ({len(view_ids)} views)...")
    added = sync_flights(
        client, collection_id, space_id, view_ids, flights,
        batch_size=args.batch_size, dry_run=args.dry_run,
    )
    print(f"\nDone — {len(added)} flight(s) {'would be ' if args.dry_run else ''}added.")
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Import or sync a Flightradar24 CSV export with a Notion database.")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text, handler in (
        ("create", "Create a new flights database on the page and import every row.", _create),
        ("sync", "Append flights missing from the page's existing database.", _sync),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("page", help="Notion URL or page ID of the host page.")
        p.add_argument("--csv", default=str(DEFAULT_CSV), help=f"Path to the FR24 CSV export (default: {DEFAULT_CSV}).")
        p.add_argument("--batch-size", type=int, default=50, help="Rows per Notion transaction (default: 50).")
        p.set_defaults(func=handler)

    sub.choices["sync"].add_argument("--dry-run", action="store_true", help="Report what would be added without writing.")
    sub.choices["create"].set_defaults(dry_run=False)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
