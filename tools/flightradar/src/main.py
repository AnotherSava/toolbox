"""CLI entry point: import an FR24 CSV export into a new Notion database."""

import argparse
import sys
from pathlib import Path

from notion_tools.client import create_client
from notion_tools.optimize_images import parse_page_id

from flightradar.airports import load_airports
from flightradar.flights import assign_origin_changes, assign_stays, assign_trips, parse_flights
from flightradar.notion_db import create_collection, insert_rows

TOOL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV = TOOL_DIR / "data" / "flights.csv"
AIRPORTS_CACHE = TOOL_DIR / "data" / "ourairports"


def _load_host(client, host_page_id: str) -> dict:
    """Fetch the host page record (used to recover its space_id)."""
    resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": host_page_id}, "version": -1}],
    }).json()
    page = resp.get("recordMap", {}).get("block", {}).get(host_page_id, {}).get("value", {}).get("value")
    if not page:
        raise SystemExit(f"Page {host_page_id} not found or no access.")
    return page


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Import a Flightradar24 CSV export into a Notion database.")
    parser.add_argument("page", help="Notion URL or page ID of the host page where the database will be created.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help=f"Path to the FR24 CSV export (default: {DEFAULT_CSV}).")
    parser.add_argument("--batch-size", type=int, default=50, help="Rows per Notion transaction (default: 50).")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    host_page_id = parse_page_id(args.page)

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

    client = create_client()
    page = _load_host(client, host_page_id)
    space_id = page["space_id"]
    print(f"\nStep 3: creating collection on host page {host_page_id} (space {space_id})...")
    cv_block_id, collection_id = create_collection(client, host_page_id, space_id, n_trips)
    print(f"  collection_view block: {cv_block_id}")
    print(f"  collection id:         {collection_id}")

    print(f"\nStep 4: inserting {len(flights)} rows (batch={args.batch_size})...")
    insert_rows(client, collection_id, space_id, flights, batch_size=args.batch_size)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
