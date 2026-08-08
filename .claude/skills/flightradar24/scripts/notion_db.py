"""Create a Notion database (collection) for flights and import rows.

Uses the Notion internal v3 API via ``notion_tools.client``. The collection is
embedded as a ``collection_view`` block on a host page; one ``page`` block per
flight is created with ``parent_table='collection'``.

Property values for v3 are decoration arrays:
  * text/number: ``[[<string>]]`` (numbers stored as their string form)
  * date:        ``[["‣", [["d", {"type": "date", "start_date": "YYYY-MM-DD"}]]]]``

Empty values are simply omitted from the row's ``properties`` map rather than
being set to an empty array.

Two date-related columns exist by design: ``date_sort`` is the real date
property, kept hidden, and used for chronological view sorts. ``date`` is the
visible text column pre-formatted as ``"Jul 4, 2025"`` because Notion's
date renderer does not natively support abbreviated month names.
"""

import uuid
from datetime import datetime
from typing import Iterable

from notion_tools.client import NotionClient

from flights import Flight, HOME_CITIES

SCHEMA: list[tuple[str, str, str]] = [
    ("title", "Route", "title"),
    ("date_sort", "Date (sort)", "date"),
    ("date", "Date", "text"),
    ("trip", "Trip", "select"),
    ("parity", "Parity", "select"),
    ("from_loc", "From", "text"),
    ("from_code", "From IATA", "text"),
    ("from_name", "From airport", "text"),
    ("from_city", "From city", "text"),
    ("from_country", "From country", "text"),
    ("to_loc", "To", "text"),
    ("to_code", "To IATA", "text"),
    ("to_name", "To airport", "text"),
    ("to_city", "To city", "text"),
    ("to_country", "To country", "text"),
    ("dep", "Departure", "text"),
    ("arr", "Arrival", "text"),
    ("dur", "Duration", "text"),
    ("flight_no", "Flight number", "text"),
    ("airline", "Airline", "text"),
    ("aircraft", "Aircraft", "text"),
    ("reg", "Registration", "text"),
    ("class", "Class", "text"),
    ("reason", "Reason", "text"),
    ("note", "Note", "text"),
]

# The Trip property still drives grouping and the conditional-color rule, but
# the column itself is redundant once trip identity is shown in group headers
# and via the row background, so it stays hidden in every view.
ALWAYS_HIDDEN: set[str] = {"date_sort", "parity", "trip"}

# Full view: hide the new combined From/To columns (city/country/code stay split).
FULL_HIDDEN: set[str] = ALWAYS_HIDDEN | {"from_loc", "to_loc"}

# Compact view: hide the split From/To columns; just show the combined ones.
COMPACT_HIDDEN: set[str] = ALWAYS_HIDDEN | {
    "from_code", "from_name", "from_city", "from_country",
    "to_code", "to_name", "to_city", "to_country",
    "aircraft", "reg", "class", "reason", "note",
}

# Per-column widths in the Compact view (in pixels). Keys not listed fall back
# to the default of 140. Picked to match content — short codes get narrow
# columns, free-text columns get wider ones.
COMPACT_WIDTHS: dict[str, int] = {
    "title": 140,
    "date": 110,
    "trip": 60,
    "flight_no": 110,
    "from_loc": 200,
    "to_loc": 200,
    "dep": 90,
    "arr": 90,
    "dur": 90,
    "airline": 200,
}


# Notion's select-pill colors used by `_build_schema` to alternate trip
# options. Two soft colors keep adjacent trip groups visually distinct without
# turning the table into a kaleidoscope.
TRIP_COLORS = ("blue", "default")


def _build_schema(trip_count: int) -> dict[str, dict]:
    """Build the Notion collection schema, filling in select options for trips.

    ``trip_count`` is the number of distinct trips; we generate one option per
    trip with names ``T1``..``T<trip_count>`` and alternating colors. Parity
    gets two options (``A``/``B``) used as an anchor for one conditional-color
    rule that bands rows by trip.
    """
    schema = {key: {"name": name, "type": ptype} for key, name, ptype in SCHEMA}
    schema["trip"]["options"] = [
        {"id": str(uuid.uuid4()), "value": f"T{i}", "color": TRIP_COLORS[(i - 1) % len(TRIP_COLORS)]}
        for i in range(1, trip_count + 1)
    ]
    schema["parity"]["options"] = [
        {"id": str(uuid.uuid4()), "value": "A", "color": "default"},
        {"id": str(uuid.uuid4()), "value": "B", "color": "blue"},
    ]
    return schema


def _format_date(iso: str) -> str:
    """Convert ``YYYY-MM-DD`` to ``"Jul 4, 2025"`` (no leading zero on day)."""
    if not iso:
        return ""
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def _text(value: str) -> list:
    """Notion v3 text property value."""
    return [[value]]


def _bold(value: str) -> list:
    """Notion v3 text property value, bolded."""
    return [[value, [["b"]]]]


def _date(value: str) -> list | None:
    """Notion v3 date property value for ``YYYY-MM-DD``."""
    if not value:
        return None
    return [["‣", [["d", {"type": "date", "start_date": value}]]]]


def _format_loc(airport) -> str:
    """Combine city + country as ``"Vancouver, Canada"`` (skip empties)."""
    if airport is None:
        return ""
    parts = [p for p in (airport.city, airport.country) if p]
    return ", ".join(parts)


def _trim_seconds(value: str) -> str:
    """``"05:15:00" -> "05:15"``; leaves shorter strings unchanged."""
    return value.rsplit(":", 1)[0] if value.count(":") == 2 else value


def _row_properties(flight: Flight) -> dict[str, list]:
    """Serialize a Flight into a Notion v3 properties dict (omitting empties)."""
    o, d = flight.origin, flight.destination
    title_str = ""
    if flight.origin_code or flight.destination_code:
        title_str = f"{flight.origin_code or '?'} → {flight.destination_code or '?'}"
    formatted_date = _format_date(flight.date)
    from_loc = _format_loc(o)
    to_loc = _format_loc(d)
    # Bold the destination when it's a real stay (not a quick layover, not a
    # home city). Bold the origin when it differs from the previous flight's
    # arrival — signals overland travel between flights, e.g. Tivat -> Dubrovnik.
    bold_to = (
        flight.destination_is_stay
        and flight.destination is not None
        and flight.destination.city not in HOME_CITIES
    )
    bold_from = (
        flight.origin_is_new
        and flight.origin is not None
        and flight.origin.city not in HOME_CITIES
    )
    from_loc_value = (_bold if bold_from else _text)(from_loc) if from_loc else None
    to_loc_value = (_bold if bold_to else _text)(to_loc) if to_loc else None
    raw: dict[str, list | None] = {
        "title": _text(title_str) if title_str else None,
        "date_sort": _date(flight.date),
        "date": _text(formatted_date) if formatted_date else None,
        "trip": _text(f"T{flight.trip}") if flight.trip else None,
        "parity": _text("B" if flight.trip and flight.trip % 2 == 0 else "A") if flight.trip else None,
        "flight_no": _text(flight.flight_number) if flight.flight_number else None,
        "from_loc": from_loc_value,
        "from_code": _text(flight.origin_code) if flight.origin_code else None,
        "from_name": _text(o.name) if o and o.name else None,
        "from_city": _text(o.city) if o and o.city else None,
        "from_country": _text(o.country) if o and o.country else None,
        "to_loc": to_loc_value,
        "to_code": _text(flight.destination_code) if flight.destination_code else None,
        "to_name": _text(d.name) if d and d.name else None,
        "to_city": _text(d.city) if d and d.city else None,
        "to_country": _text(d.country) if d and d.country else None,
        "dep": _text(flight.dep_time) if flight.dep_time else None,
        "arr": _text(flight.arr_time) if flight.arr_time else None,
        "dur": _text(_trim_seconds(flight.duration)) if flight.duration else None,
        "airline": _text(flight.airline) if flight.airline else None,
        "aircraft": _text(flight.aircraft) if flight.aircraft else None,
        "reg": _text(flight.registration) if flight.registration else None,
        "class": _text(flight.flight_class) if flight.flight_class else None,
        "reason": _text(flight.flight_reason) if flight.flight_reason else None,
        "note": _text(flight.note) if flight.note else None,
    }
    return {k: v for k, v in raw.items() if v is not None}


def _send_transaction(client: NotionClient, space_id: str, label: str, ops: list[dict]) -> None:
    """Send one ``saveTransactionsFanout`` call with ``ops`` and raise on errors."""
    r = client.post("saveTransactionsFanout", {
        "requestId": str(uuid.uuid4()),
        "transactions": [{
            "id": str(uuid.uuid4()),
            "spaceId": space_id,
            "debug": {"userAction": label},
            "operations": ops,
        }],
    })
    r.raise_for_status()


def _table_view_format(
    collection_id: str,
    space_id: str,
    hidden: set[str] = frozenset(),
    widths: dict[str, int] | None = None,
) -> dict:
    """Build the format dict for a table view.

    Hides any schema key in ``hidden``; uses per-key widths from ``widths``
    where provided, falling back to 200 for the title column and 140 elsewhere.
    """
    widths = widths or {}
    title_width = widths.get("title", 200)
    table_properties = [{"property": "title", "visible": "title" not in hidden, "width": title_width}]
    for key, _name, _ptype in SCHEMA:
        if key == "title":
            continue
        table_properties.append({
            "property": key,
            "visible": key not in hidden,
            "width": widths.get(key, 140),
        })
    return {
        "table_wrap": True,
        "collection_pointer": {"id": collection_id, "table": "collection", "spaceId": space_id},
        "table_properties": table_properties,
    }


def _conditional_color_rules() -> list[dict]:
    """Build the conditional-color rule that bands rows by Parity.

    ``match_property_value`` means each row inherits the background of its
    Parity select option — option ``A`` is ``default`` (no tint), option ``B``
    is ``blue`` — so even-numbered trips render blue.
    """
    return [{
        "id": str(uuid.uuid4()),
        "background": {"type": "match_property_value"},
        "conditional_filter": {
            "filter": {"operator": "is_not_empty"},
            "property": "parity",
        },
        "properties_to_color": {"type": "all"},
    }]


def _collection_groups(trip_count: int) -> list[dict]:
    """Build per-group descriptors for grouped views: one entry per Tn option.

    Notion needs an entry for every group it might render so that order and
    visibility are stable. We mark all trip groups visible.
    """
    groups = [
        {
            "property": "trip",
            "value": {"type": "select", "value": f"T{i}"},
            "hidden": False,
        }
        for i in range(1, trip_count + 1)
    ]
    # Catch-all for rows with no trip value; keeps Notion happy.
    groups.append({
        "property": "trip",
        "value": {"type": "select"},
        "hidden": False,
    })
    return groups


def _view_op(
    view_id: str,
    cv_block_id: str,
    collection_id: str,
    space_id: str,
    name: str,
    hidden: set[str],
    trip_count: int,
    widths: dict[str, int] | None = None,
) -> dict:
    """Build a single ``set`` op for a table view grouped by Trip, sorted date desc."""
    fmt = _table_view_format(collection_id, space_id, hidden, widths)
    fmt["collection_groups"] = _collection_groups(trip_count)
    fmt["conditional_color_rules"] = _conditional_color_rules()
    return {"id": view_id, "table": "collection_view", "path": [], "command": "set", "args": {
        "id": view_id, "type": "table", "name": name,
        "format": fmt,
        "query2": {
            "group_by": "trip",
            "sort": [
                {"property": "date_sort", "direction": "descending"},
                {"property": "dep", "direction": "descending"},
            ],
        },
        "parent_id": cv_block_id, "parent_table": "block",
        "space_id": space_id, "alive": True,
    }}


def create_collection(
    client: NotionClient,
    host_page_id: str,
    space_id: str,
    trip_count: int,
) -> tuple[str, str]:
    """Create the embedded collection_view + collection + Full and Compact views.

    ``trip_count`` is needed to enumerate Trip select options and group entries.
    Returns ``(collection_view_block_id, collection_id)``.
    """
    cv_block_id = str(uuid.uuid4())
    collection_id = str(uuid.uuid4())
    full_view_id = str(uuid.uuid4())
    compact_view_id = str(uuid.uuid4())
    ops = [
        {"id": cv_block_id, "table": "block", "path": [], "command": "set", "args": {
            "id": cv_block_id, "type": "collection_view",
            "view_ids": [full_view_id, compact_view_id], "collection_id": collection_id,
            "format": {
                "collection_pointer": {"id": collection_id, "table": "collection", "spaceId": space_id},
                "collection_pointers": [{"id": collection_id, "table": "collection", "spaceId": space_id}],
            },
            "parent_id": host_page_id, "parent_table": "block",
            "space_id": space_id, "alive": True,
        }},
        {"id": collection_id, "table": "collection", "path": [], "command": "set", "args": {
            "id": collection_id,
            "name": [["Flights"]],
            "schema": _build_schema(trip_count),
            "parent_id": cv_block_id, "parent_table": "block",
            "space_id": space_id, "alive": True, "migrated": True,
        }},
        _view_op(full_view_id, cv_block_id, collection_id, space_id, "Full", FULL_HIDDEN, trip_count),
        _view_op(compact_view_id, cv_block_id, collection_id, space_id, "Compact", COMPACT_HIDDEN, trip_count, COMPACT_WIDTHS),
        {"id": host_page_id, "table": "block", "path": ["content"], "command": "listAfter", "args": {"id": cv_block_id}},
    ]
    _send_transaction(client, space_id, "create_flights_collection", ops)
    return cv_block_id, collection_id


def insert_rows(
    client: NotionClient,
    collection_id: str,
    space_id: str,
    flights: Iterable[Flight],
    batch_size: int = 50,
) -> list[str]:
    """Insert one page row per flight in ``batch_size``-sized transactions.

    Returns the list of row IDs in input order.
    """
    flights = list(flights)
    row_ids = [str(uuid.uuid4()) for _ in flights]
    for start in range(0, len(flights), batch_size):
        chunk = flights[start:start + batch_size]
        chunk_ids = row_ids[start:start + batch_size]
        ops: list[dict] = []
        for rid, flight in zip(chunk_ids, chunk):
            ops.append({"id": rid, "table": "block", "path": [], "command": "set", "args": {
                "id": rid, "type": "page",
                "properties": _row_properties(flight),
                "parent_id": collection_id, "parent_table": "collection",
                "space_id": space_id, "alive": True,
            }})
        _send_transaction(client, space_id, "insert_flights_batch", ops)
        print(f"  inserted {start + len(chunk)}/{len(flights)}")
    return row_ids
