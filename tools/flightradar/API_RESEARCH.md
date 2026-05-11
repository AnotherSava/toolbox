---
name: MyFlightradar24 API research
description: Findings on whether my.flightradar24.com offers an API for reading flight history and adding flights
---

# MyFlightradar24 — API research

## TL;DR

**No public API for the personal logbook.** The only sanctioned way to read or add entries to your `my.flightradar24.com` history is **CSV import/export**.

The official Flightradar24 API at `fr24api.flightradar24.com` exposes live/historical flight data, airline/airport metadata, and flight summaries — none of it is tied to a user's personal logbook.

## Supported interface: CSV

- **Export:** https://my.flightradar24.com/settings/export
- **Import:** Settings → Import (same CSV format)
- **Mandatory fields:** `Date` (YYYY-MM-DD), `Origin`, `Destination`
- **Airport codes:** ICAO or IATA both accepted, in any combination
- Other columns (flight number, aircraft reg, seat, class, notes, etc.) are optional — easiest path is to download a sample export first and match the column layout exactly.

## Programmatic options

1. **CSV round-trip (recommended)**
   - Build a CSV from your data source, upload via the web UI.
   - Officially supported, stable format, used by third-party tools (e.g. AirTrail) for interop.
   - Downside: requires a manual upload step in the browser; no scheduling.

2. **Reverse-engineered session calls (unsupported)**
   - The `my.flightradar24.com` web UI calls internal HTTP endpoints behind the login cookie.
   - Not documented, no stability guarantees, likely violates ToS.
   - Signal that no sanctioned API exists: third-party logbook tools all interoperate via CSV, not API.

3. **Browser automation against the web UI (unsupported but practical)**
   - Drive the import page with Playwright/Selenium using a stored session.
   - Same ToS caveat, but lower breakage surface than reverse-engineering JSON endpoints — the import form changes less often than internal APIs.

## Sources

- [Can I upload flights via CSV? — FR24 Support](https://support.fr24.com/support/solutions/articles/3000115530--can-i-upload-flights-via-csv-)
- [MyFlightradar24 FAQ](https://my.flightradar24.com/about/faq)
- [Flightradar24 API overview](https://fr24api.flightradar24.com/)
- [AirTrail import docs (third-party logbook using FR24 CSV)](https://airtrail.johan.ohly.dk/docs/features/import)
- [CSV import tool not working — FR24 forum thread](https://forum.flightradar24.com/forum/radar-forums/flightradar24-web-page-and-apps/221410-csv-import-tool-not-working-on-my-flightradar24)

## Date of research

2026-05-09
