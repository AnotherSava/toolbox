"""Airport metadata lookup backed by the OurAirports public dataset.

Downloads two CSVs on first use and caches them under ``data/ourairports/``:
  * ``airports.csv`` — one row per airport with IATA, ICAO, name, municipality,
    iso_country
  * ``countries.csv`` — iso_country -> human-readable country name

After loading, a single ``Airport`` is keyed by both its IATA (3-letter) and
ICAO (4-letter) code where present, so callers can resolve either. City names
are normalized: anything after the first ``/`` is dropped (e.g.
``"Montpellier/Méditerranée" -> "Montpellier"``) and any trailing
parenthetical annotation is stripped (e.g.
``"Paris (Roissy-en-France, Val-d'Oise)" -> "Paris"``).
"""

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import requests

PAREN_RE = re.compile(r"\s*\(.*\)\s*$")

COUNTRY_ABBREV: dict[str, str] = {
    "United Arab Emirates": "UAE",
    "United States": "USA",
    "United States of America": "USA",
    "United Kingdom": "UK",
}


def _clean_city(value: str) -> str:
    """Drop ``/suffix`` and trailing ``(...)`` annotations from a city name."""
    return PAREN_RE.sub("", value.split("/")[0].strip()).strip()


def _clean_country(value: str) -> str:
    """Apply common abbreviations (UAE, USA, UK) to verbose country names."""
    return COUNTRY_ABBREV.get(value, value)

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
COUNTRIES_URL = "https://davidmegginson.github.io/ourairports-data/countries.csv"

EXTRA_AIRPORTS: list[dict[str, str]] = [
    {
        "iata": "TXL", "icao": "EDDT",
        "name": "Berlin Tegel Airport (closed 2020)",
        "city": "Berlin", "country": "Germany",
    },
]


@dataclass(frozen=True)
class Airport:
    """A single airport entry resolved from OurAirports."""
    iata: str
    icao: str
    name: str
    city: str
    country: str


def _download(url: str, dest: Path) -> None:
    """Download ``url`` to ``dest`` if the file is missing or empty."""
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  fetching {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)


def _load_countries(path: Path) -> dict[str, str]:
    """Map iso_country code -> country name."""
    out: dict[str, str] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["code"]] = row["name"]
    return out


def load_airports(cache_dir: Path) -> dict[str, Airport]:
    """Return a lookup keyed by both IATA and ICAO codes (uppercase).

    Airports without either code are skipped. Where an entry has both, both
    keys point at the same Airport instance.
    """
    airports_csv = cache_dir / "airports.csv"
    countries_csv = cache_dir / "countries.csv"
    _download(AIRPORTS_URL, airports_csv)
    _download(COUNTRIES_URL, countries_csv)
    countries = _load_countries(countries_csv)

    lookup: dict[str, Airport] = {}
    with open(airports_csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            iata = (row.get("iata_code") or "").strip().upper()
            icao = (row.get("ident") or "").strip().upper()
            if not iata and not icao:
                continue
            airport = Airport(
                iata=iata,
                icao=icao,
                name=row.get("name", "").strip(),
                city=_clean_city(row.get("municipality", "")),
                country=_clean_country(countries.get(row.get("iso_country", ""), row.get("iso_country", ""))),
            )
            if iata:
                lookup[iata] = airport
            if icao:
                lookup[icao] = airport

    for entry in EXTRA_AIRPORTS:
        airport = Airport(
            iata=entry["iata"], icao=entry["icao"], name=entry["name"],
            city=entry["city"], country=entry["country"],
        )
        if entry["iata"]:
            lookup.setdefault(entry["iata"], airport)
        if entry["icao"]:
            lookup.setdefault(entry["icao"], airport)
    return lookup


def resolve(lookup: dict[str, Airport], code: str) -> Airport | None:
    """Look up an airport by IATA or ICAO code (case-insensitive)."""
    if not code:
        return None
    return lookup.get(code.strip().upper())
