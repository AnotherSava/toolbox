"""Append newly-logged flights to an existing Notion flights collection.

Re-running the initial import would build a *second* table and throw away the
view tweaks made in Notion's UI (renamed views, column widths, group state), so
syncing appends in place instead:

  * Trip numbers, stay/layover flags and the bold markers depend on neighbouring
    flights, so they are recomputed over the **whole** history and only then
    filtered down to the rows Notion is missing.
  * Existing rows are matched on ``(date, flight number, from, to, dep time)``;
    anything already there is left untouched.
  * The Trip select options and every view's group list are extended to cover
    the new trips — Notion renders a grouped view only for values it knows
    about, so a new ``T69`` without a matching option/group entry would drop its
    rows into the catch-all bucket.
"""

import uuid

from notion_tools.client import NotionClient

from flights import Flight
from notion_db import TRIP_COLORS, _collection_groups, _send_transaction, insert_rows
from row_props import row_key


def find_collection(client: NotionClient, host_page_id: str) -> tuple[str, str, list[str]]:
    """Locate the first ``collection_view`` block on ``host_page_id``.

    Returns ``(collection_id, space_id, view_ids)``.
    """
    resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": host_page_id}, "version": -1}],
    }).json()
    page = resp.get("recordMap", {}).get("block", {}).get(host_page_id, {}).get("value", {}).get("value")
    if not page:
        raise SystemExit(f"Page {host_page_id} not found or no access.")
    space_id = page["space_id"]
    content = page.get("content", [])
    if not content:
        raise SystemExit(f"Page {host_page_id} has no child blocks.")
    children = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": c}, "version": -1} for c in content],
    }).json().get("recordMap", {}).get("block", {})
    for block_id in content:
        block = children.get(block_id, {}).get("value", {}).get("value", {})
        if block.get("type") == "collection_view" and block.get("collection_id"):
            return block["collection_id"], space_id, block.get("view_ids", [])
    raise SystemExit(f"No collection_view block found on page {host_page_id}.")


def fetch_existing_keys(client: NotionClient, collection_id: str, view_id: str, space_id: str) -> set[tuple]:
    """Return the dedup key of every live row already in the collection."""
    resp = client.post("queryCollection", {
        "collectionId": collection_id,
        "collectionViewId": view_id,
        "loader": {
            "type": "reducer",
            "reducers": {"results": {"type": "results", "limit": 10000}},
            "searchQuery": "",
            "userTimeZone": "UTC",
        },
        "query": {},
        "source": {"type": "collection", "id": collection_id, "spaceId": space_id},
    })
    resp.raise_for_status()
    blocks = resp.json().get("recordMap", {}).get("block", {})
    keys = set()
    for entry in blocks.values():
        row = entry.get("value", {})
        row = row.get("value", row)
        if row.get("parent_id") != collection_id or not row.get("alive"):
            continue
        keys.add(row_key(row.get("properties", {})))
    return keys


def flight_key(flight: Flight) -> tuple:
    """Build the same dedup key from a parsed Flight."""
    return (flight.date, flight.flight_number, flight.origin_code, flight.destination_code, flight.dep_time)


def extend_trip_options(client: NotionClient, collection_id: str, space_id: str, trip_count: int) -> int:
    """Add select options for any trip up to ``trip_count`` that has none yet.

    Existing options keep their ``id`` so the cells already pointing at them stay
    bound (removing and re-adding an option orphans every value that used it).
    Returns the number of options added.
    """
    resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "collection", "id": collection_id}, "version": -1}],
    }).json()
    collection = resp["recordMap"]["collection"][collection_id]["value"]["value"]
    options = list(collection["schema"]["trip"].get("options", []))
    known = {opt["value"] for opt in options}
    added = [
        {"id": str(uuid.uuid4()), "value": f"T{i}", "color": TRIP_COLORS[(i - 1) % len(TRIP_COLORS)]}
        for i in range(1, trip_count + 1)
        if f"T{i}" not in known
    ]
    if not added:
        return 0
    _send_transaction(client, space_id, "extend_trip_options", [{
        "id": collection_id, "table": "collection", "path": ["schema", "trip", "options"],
        "command": "set", "args": options + added,
    }])
    return len(added)


def extend_groups(client: NotionClient, view_ids: list[str], space_id: str, trip_count: int) -> int:
    """Append group entries for new trips to every view, keeping existing ones.

    Rebuilding the array wholesale would reset any group a user collapsed or
    hid, so entries already present are preserved verbatim and only the missing
    trips are inserted — ahead of the trailing catch-all bucket for unset values.
    """
    if not view_ids:
        return 0
    resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "collection_view", "id": v}, "version": -1} for v in view_ids],
    }).json().get("recordMap", {}).get("collection_view", {})
    wanted = _collection_groups(trip_count)
    updated = 0
    for view_id in view_ids:
        view = resp.get(view_id, {}).get("value", {}).get("value", {})
        existing = list(view.get("format", {}).get("collection_groups", []))
        present = {g.get("value", {}).get("value") for g in existing}
        missing = [g for g in wanted if g["value"].get("value") and g["value"]["value"] not in present]
        if not missing:
            continue
        # Keep the unset catch-all last; new trip groups go just before it.
        head = [g for g in existing if g.get("value", {}).get("value")]
        tail = [g for g in existing if not g.get("value", {}).get("value")]
        _send_transaction(client, space_id, "extend_collection_groups", [{
            "id": view_id, "table": "collection_view", "path": ["format", "collection_groups"],
            "command": "set", "args": head + missing + tail,
        }])
        updated += 1
    return updated


def sync_flights(
    client: NotionClient,
    collection_id: str,
    space_id: str,
    view_ids: list[str],
    flights: list[Flight],
    batch_size: int = 50,
    dry_run: bool = False,
) -> list[Flight]:
    """Insert every flight missing from the collection; returns the ones added."""
    if not view_ids:
        raise SystemExit("Collection has no views to query.")
    existing = fetch_existing_keys(client, collection_id, view_ids[0], space_id)
    print(f"  {len(existing)} rows already in Notion.")
    missing = [f for f in sorted(flights, key=lambda f: (f.date, f.dep_time)) if flight_key(f) not in existing]
    if not missing:
        print("  Nothing to add — Notion is up to date.")
        return []
    trip_count = max(f.trip for f in flights)
    print(f"  {len(missing)} flight(s) to add, up to trip T{trip_count}:")
    for f in missing:
        print(f"    + {f.date}  {f.origin_code or '?'} -> {f.destination_code or '?':4}  T{f.trip}  {f.flight_number}")
    if dry_run:
        print("  (dry run — nothing written)")
        return missing
    added = extend_trip_options(client, collection_id, space_id, trip_count)
    print(f"  trip options added: {added}")
    touched = extend_groups(client, view_ids, space_id, trip_count)
    print(f"  views regrouped: {touched}")
    insert_rows(client, collection_id, space_id, missing, batch_size=batch_size)
    return missing
