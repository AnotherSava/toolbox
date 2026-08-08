# Flightradar24 CSV Export Quirks

Discovered while building the `flightradar` importer. The export is at `my.flightradar24.com/settings/export`; output filename is `flightdiary_YYYY_MM_DD_HH_MM.csv`.

- **The first line is blank.** The CSV starts with an empty line before the header row. `csv.DictReader` treats that empty line as the header and produces empty field names — every row becomes unindexable. Skip leading blank lines before handing the file to the reader.

- **Empty placeholders, not empty strings.** Missing aircraft data renders as `" ()"`, missing airline as `" (/)"`. Treat both as empty when extracting names; otherwise they leak into the output as literal "()" or "(/)" strings.

- **`(IATA/ICAO)` parenthetical suffixes follow free-text columns.** `From`, `To`, `Airline`, and `Aircraft` all carry a trailing `(...)` with codes. For display, strip with a regex like `r"\s*\([^()]*\)\s*$"`. For parsing the From/To codes, use a regex anchored at end-of-string capturing the IATA (3 chars) and optional ICAO (4 chars).

- **Seat type / Flight class / Flight reason are integer enum codes, not text labels.** FR24 stores these as numeric codes:
  - **Seat type:** `0`=unset, `1`=Window, `2`=Middle, `3`=Aisle
  - **Flight class:** `0`=unset, `1`=Economy, `2`=Premium Economy, `3`=Business, `4`=First, `5`=Private
  - **Flight reason:** `0`=unset, `1`=Leisure, `2`=Business, `3`=Crew, `4`=Other

  Mappings cross-verified against two third-party importers: `FlightLogger/server/routes/import.ts` and `Abrechen2/TravStats/frontend/src/lib/importers/fr24.ts`. They agree on class (1=Economy, 2=Premium Economy, 3=Business, 4=First) but TravStats labels reason as `1=Vacation, 2=Business`; FlightLogger labels it `1=Leisure, 2=Business`. The user's own data may not match either rigorously since FR24 users tag inconsistently — don't fight the data, just decode the codes and let the user re-tag.

- **Time columns include `:SS` even though FR24 only tracks HH:MM.** All time/duration values are stored as `HH:MM:00`. Strip trailing `:00` for display.

- **Five trailing internal-ID columns** at the end of each row: `Dep_id`, `Arr_id`, `Airline_id`, `Aircraft_id` (sometimes 5 columns total in this group). These don't surface in FR24's UI and have no documented use — safe to ignore on import.

- **Re-exports can contain duplicate rows.** Each "save" in FR24's web logbook can re-emit a flight without deduplication. Symptom: identical `(Date, Flight number, From, To, Dep time, Arr time)` rows appearing 2× in the export. Best handled by reporting duplicates to the user pre-import and letting them clean their FR24 logbook (vs. silently deduplicating on import).

- **City names from OurAirports may include parentheticals or slash suffixes.** Examples in real data: `"Paris (Roissy-en-France, Val-d'Oise)"`, `"Köln (Cologne)"`, `"Istanbul(Bakırköy)"` (no space before paren), `"Montpellier/Méditerranée"`. Normalize by: (a) splitting on first `/` and keeping the prefix, then (b) stripping any trailing `(...)`.

- **Country names need abbreviation for compact display.** Common verbose names in OurAirports: `"United Arab Emirates"` → `UAE`, `"United States"` → `USA`, `"United Kingdom"` → `UK`.

- **Closed airports may be absent from OurAirports.** Berlin Tegel (TXL/EDDT) was removed after its 2020 closure but appears in historical FR24 exports. Maintain a small fallback dict for known closures so trip-grouping doesn't silently break on unresolved airports.

- **Moscow has 5 IATA airports** (DME, SVO, VKO, ZIA, CKL). Hard-coded IATA whitelists for "home airport detection" miss at least one and break trip-grouping logic (we initially missed ZIA — Zhukovsky — and a Budapest trip got incorrectly merged with the Moscow → Vancouver migration two months later). Prefer city-name-based matching via resolved airport metadata: `airport.city in {"Moscow", "Vancouver"}`. This auto-handles any future new airports and any IATA codes the whitelist might miss.

## Date of research

2026-05-10
