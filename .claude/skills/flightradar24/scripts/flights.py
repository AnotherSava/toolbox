"""Parse a Flightradar24 CSV export into enriched Flight records.

The FR24 personal logbook CSV typically has columns like::

    Date,Flight number,From,To,Dep time,Arr time,Duration,Airline,
    Aircraft,Registration,Seat number,Seat type,Flight class,
    Flight reason,Note,Dep_id,Arr_id,Airline_id,Aircraft_id

The ``From`` / ``To`` cells are usually formatted as ``"Airport Name (IATA/ICAO)"``
so we extract the codes via regex and resolve them through the OurAirports
lookup; a cell that doesn't match keeps its raw string rather than being lost.

Seat number, seat type and the trailing ``*_id`` columns are read past on
purpose — see "Deliberately not stored" in ``references/notion-db.md``.
"""

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from airports import Airport, resolve

CODE_RE = re.compile(r"\(([A-Z0-9]{3,4})(?:/([A-Z0-9]{4}))?\)\s*$")
TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")
EMPTY_PLACEHOLDERS = {"", "()", "(/)"}

# A "trip" begins on departure from a home city and ends on arrival at one.
# Using cities (resolved via OurAirports) instead of a hard-coded IATA list
# catches every Moscow/Vancouver airport now and in the future — Moscow alone
# has DME, SVO, VKO, ZIA, CKL. The one-way Moscow -> Vancouver migration falls
# out of this rule naturally.
HOME_CITIES = {"Moscow", "Vancouver"}

FLIGHT_CLASS = {"1": "Economy", "2": "Premium Economy", "3": "Business", "4": "First", "5": "Private"}
FLIGHT_REASON = {"1": "Leisure", "2": "Business", "3": "Crew", "4": "Other"}


@dataclass
class Flight:
    """One row from the FR24 export, enriched with airport metadata."""
    date: str
    flight_number: str
    origin_raw: str
    destination_raw: str
    origin_code: str
    destination_code: str
    origin: Airport | None
    destination: Airport | None
    dep_time: str
    arr_time: str
    duration: str
    airline: str
    aircraft: str
    registration: str
    flight_class: str
    flight_reason: str
    note: str
    trip: int = 0
    destination_is_stay: bool = True
    # True when this flight's origin city differs from the previous flight's
    # destination city — i.e., the user travelled overland between flights.
    origin_is_new: bool = False


def _extract_code(cell: str) -> tuple[str, str]:
    """Return (preferred_code, raw) for a ``From``/``To`` cell.

    Prefers IATA when present, falls back to ICAO. If the cell is just a bare
    code (no parentheses), returns it as-is.
    """
    cell = (cell or "").strip()
    if not cell:
        return "", ""
    match = CODE_RE.search(cell)
    if match:
        iata, icao = match.group(1), match.group(2)
        return (iata or icao or "").upper(), cell
    bare = cell.upper()
    if re.fullmatch(r"[A-Z0-9]{3,4}", bare):
        return bare, cell
    return "", cell


def _get(row: dict[str, str], *names: str) -> str:
    """Return the first non-empty value from ``row`` for any of ``names``.

    FR24 stores missing aircraft/airline metadata as placeholder strings like
    ``" ()"`` or ``" (/)"``; treat any of those as empty.
    """
    for n in names:
        if n in row and row[n]:
            value = row[n].strip()
            if value not in EMPTY_PLACEHOLDERS:
                return value
    return ""


def _strip_codes(value: str) -> str:
    """Drop a trailing ``(IATA/ICAO)`` parenthetical from an airline/aircraft name."""
    return TRAILING_PAREN_RE.sub("", value).strip()


def assign_trips(flights: list[Flight]) -> None:
    """Assign 1-indexed trip numbers in chronological order, mutating in place.

    A new trip starts on the first flight after returning home (or on the very
    first flight if it departs from anywhere). It closes when the destination's
    city is in HOME_CITIES. Mid-trip layovers stay inside the same trip.
    """
    chrono = sorted(flights, key=lambda f: (f.date, f.dep_time))
    trip_id = 0
    in_trip = False
    for f in chrono:
        if not in_trip:
            trip_id += 1
            in_trip = True
        f.trip = trip_id
        if f.destination and f.destination.city in HOME_CITIES:
            in_trip = False


def _parse_dt(date: str, time: str) -> datetime | None:
    """Parse ``YYYY-MM-DD`` + ``HH:MM[:SS]`` into a datetime, or None on bad input."""
    if not date or not time:
        return None
    parts = time.split(":")
    if len(parts) < 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) >= 3 else 0
        return datetime.strptime(date, "%Y-%m-%d").replace(hour=h, minute=m, second=s)
    except ValueError:
        return None


def assign_stays(flights: list[Flight], layover_threshold_hours: float = 12) -> None:
    """Mark each flight's destination as a real stay vs. a quick layover.

    A stop is a layover when the next flight departs from the same city within
    ``layover_threshold_hours`` of arrival. Otherwise the user actually spent
    time there. The last flight in the chronological sequence keeps the default
    ``True`` — arriving home is always a real stay.
    """
    chrono = sorted(flights, key=lambda f: (f.date, f.dep_time))
    for i in range(len(chrono) - 1):
        cur, nxt = chrono[i], chrono[i + 1]
        if not (cur.destination and nxt.origin):
            continue
        if not cur.destination.city or cur.destination.city != nxt.origin.city:
            continue
        cur_dep = _parse_dt(cur.date, cur.dep_time)
        cur_arr = _parse_dt(cur.date, cur.arr_time)
        nxt_dep = _parse_dt(nxt.date, nxt.dep_time)
        if not (cur_dep and cur_arr and nxt_dep):
            continue
        if cur_arr < cur_dep:  # flight crossed midnight
            cur_arr += timedelta(days=1)
        gap_hours = (nxt_dep - cur_arr).total_seconds() / 3600
        if 0 <= gap_hours <= layover_threshold_hours:
            cur.destination_is_stay = False


def assign_origin_changes(flights: list[Flight]) -> None:
    """Mark each flight whose origin city differs from the previous arrival.

    Signals overland travel between flights (e.g. Tivat -> Dubrovnik by bus).
    The first flight in the chronological sequence has no predecessor and is
    left unmarked.
    """
    chrono = sorted(flights, key=lambda f: (f.date, f.dep_time))
    prev_dest_city: str | None = None
    for f in chrono:
        if prev_dest_city and f.origin and f.origin.city and f.origin.city != prev_dest_city:
            f.origin_is_new = True
        prev_dest_city = f.destination.city if f.destination else prev_dest_city


def _decode_enum(value: str, mapping: dict[str, str]) -> str:
    """Decode an FR24 integer enum to its label.

    ``"0"`` means unset and becomes ``""``. Unknown integers and free-form
    strings pass through unchanged so we don't drop data we don't recognize.
    """
    if not value or value == "0":
        return ""
    return mapping.get(value, value)


def parse_flights(csv_path: Path, airports: dict[str, Airport]) -> list[Flight]:
    """Read ``csv_path`` and produce one Flight per row, enriched with airports.

    FR24 exports begin with a blank line before the header, so we skip leading
    empty lines before handing the file to DictReader.
    """
    flights: list[Flight] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                return flights
            if line.strip():
                f.seek(pos)
                break
        reader = csv.DictReader(f)
        for row in reader:
            origin_code, origin_raw = _extract_code(_get(row, "From"))
            dest_code, dest_raw = _extract_code(_get(row, "To"))
            flights.append(Flight(
                date=_get(row, "Date"),
                flight_number=_get(row, "Flight number"),
                origin_raw=origin_raw,
                destination_raw=dest_raw,
                origin_code=origin_code,
                destination_code=dest_code,
                origin=resolve(airports, origin_code),
                destination=resolve(airports, dest_code),
                dep_time=_get(row, "Dep time"),
                arr_time=_get(row, "Arr time"),
                duration=_get(row, "Duration"),
                airline=_strip_codes(_get(row, "Airline")),
                aircraft=_strip_codes(_get(row, "Aircraft")),
                registration=_get(row, "Registration"),
                flight_class=_decode_enum(_get(row, "Flight class"), FLIGHT_CLASS),
                flight_reason=_decode_enum(_get(row, "Flight reason"), FLIGHT_REASON),
                note=_get(row, "Note"),
            ))
    return flights
