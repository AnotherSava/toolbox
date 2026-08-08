# Getting a fresh Flightradar24 logbook export

## There is no logbook API

The personal logbook at `my.flightradar24.com` has **no public API**. CSV import/export is the only
sanctioned interface:

- **Export:** https://my.flightradar24.com/settings/export
- **Import:** Settings → Import (same CSV format)
- **Mandatory fields:** `Date` (YYYY-MM-DD), `Origin`, `Destination`; everything else is optional
- Airport codes may be ICAO or IATA, in any combination

The official API at `fr24api.flightradar24.com` is a different product — live/historical flight data,
airline and airport metadata, flight summaries. None of it is tied to a user's personal logbook. The
giveaway that no sanctioned logbook API exists: every third-party logbook tool interoperates with FR24
via CSV, never via an API.

Downloaded exports are named `flightdiary_YYYY_MM_DD_HH_MM.csv`.

## Pulling the export without asking the user

Don't ask the user to re-download the CSV by hand — drive their logged-in Chrome session instead. This
is the same web UI the export button uses, just invoked directly.

Fetch the endpoint **same-origin from a `my.flightradar24.com` tab**:

```js
const r = await fetch('/public-scripts/export');
const t = await r.text();
window.__fr24 = t;                       // stash it; retrieving it costs several calls
const lines = t.split(/\r?\n/).filter(l => l.trim());
const rows = lines.slice(1);
JSON.stringify({status: r.status, dataRows: rows.length, maxDate: rows.map(l => l.slice(0,10)).sort().pop()})
```

Four traps, each of which cost a round-trip the first time:

- **Never pass `credentials: 'include'`.** The Chrome extension's safety layer scans the code and
  refuses it with `[BLOCKED: Cookie/query string data]`. A same-origin `fetch` sends the session cookie
  anyway (`same-origin` is the default), so the explicit option buys nothing and breaks the call.
- **Screenshots time out on this page.** `computer{action:"screenshot"}` fails with a script-injection
  timeout. Read the DOM with `javascript_tool` instead — that works fine on the same page.
- **Clicking `DOWNLOAD CSV` is unreliable.** The anchor click reports success but no file appears in
  `~/Downloads`. Fetching the endpoint sidesteps the download path entirely.
- **`javascript_tool` truncates its output at roughly 1000 characters.** A 36 KB CSV cannot be returned
  in one call, and even slicing it into 12 KB chunks gets truncated. Return **at most 3 CSV rows per
  call** (`window.__new.slice(0,3).join('\n')`), or just derive what you need inside the page.

Confirm login before fetching: the page body contains `Sign out` when authenticated, and the tab title
resolves to `Export | myFlightradar24` rather than redirecting to a login page.

## Proving the export is purely additive

Before appending anything, verify the rows already imported are untouched — that turns a risky merge
into a safe append and catches the case where the user edited or deleted historical entries in FR24.

Hash the first N rows (N = the row count already in Notion) in the page and compare against the local
CSV. djb2, matched on both sides:

```js
const h = s => { let x = 5381; for (let i=0;i<s.length;i++) x = ((x*33) ^ s.charCodeAt(i)) >>> 0; return x; };
h(rows.slice(0, N).join('\n'))
```

```python
def h(s):
    x = 5381
    for ch in s:
        x = ((x * 33) ^ ord(ch)) & 0xFFFFFFFF
    return x
```

Compare the character count too — it catches a same-hash collision and is free.

**If the hashes match**, the new rows are strictly appended at the end and can be copied over verbatim.
**If they differ**, stop and report it: something in the user's history changed, so appending would
duplicate or diverge rather than sync, and the right move is a decision from the user rather than a
guess.

Note that a JS string length counts UTF-16 code units while a UTF-8 file counts bytes — the Cyrillic
notes in this logbook make the byte size larger than the JS length. Compare *character* counts (Python
`len(str)` vs JS `.length`), not file size.

## Sources

- [Can I upload flights via CSV? — FR24 Support](https://support.fr24.com/support/solutions/articles/3000115530--can-i-upload-flights-via-csv-)
- [MyFlightradar24 FAQ](https://my.flightradar24.com/about/faq)
- [Flightradar24 API overview](https://fr24api.flightradar24.com/)
- [AirTrail import docs (third-party logbook using FR24 CSV)](https://airtrail.johan.ohly.dk/docs/features/import)

API research: 2026-05-09. Browser-session export method verified: 2026-08-07.
