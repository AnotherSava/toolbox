---
name: flightradar24
description: >-
  Sync new flights from the user's Flightradar24 logbook into the FlightRadar24 Notion database —
  pulls a fresh CSV export from a logged-in Chrome session, verifies it is purely additive, and appends
  the missing rows with their trip, row-banding and bold-location formatting recomputed.
  TRIGGER when: the user wants to update, refresh or re-sync the FlightRadar24 Notion page or their
  flight log, e.g. "update the flightradar page", "add my new flights to Notion", "sync my flight log".
  DO NOT TRIGGER for other Notion databases (the board-game conventions table has its own skill), or
  for live flight-tracking questions unrelated to the personal logbook.
allowed-tools: Bash, Read, Edit, Skill, ToolSearch, mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__tabs_close_mcp
---

# Sync Flightradar24 → Notion

Appends newly-logged flights to the existing `Flights` database on the **FlightRadar24** Notion page.

The database is not a plain dump of the CSV: trip numbers, alternating row bands and bold location
names are all **derived from the surrounding flights**, so they cannot be computed from the new rows
alone. Every step below re-parses the full history and only then filters down to what Notion is missing.

## Context
- Today: !`date +%F`
- Local CSV fingerprint: !`python .claude/skills/flightradar24/scripts/csv_hash.py 2>/dev/null || echo MISSING`
- Newest logged flight: !`tail -1 tools/flightradar/data/flights.csv 2>/dev/null | cut -c1-10 || echo MISSING`
- Notion credentials: !`doppler secrets --only-names 2>/dev/null | grep -q NOTION_TOKEN_V2 && echo PRESENT || echo MISSING`

**Page — the single source for this value; every `<page-url>` below means this one:**

```
https://app.notion.com/p/FlightRadar24-35ca04940efd80eebaabe6a556433b63
```

Use it unless the user names a different page. The scripts take it as a required argument and resolve
the collection, views and space from it at runtime, so this is the only Notion identifier that needs
recording anywhere. If it ever changes, change it here and nowhere else.

## Preconditions

If **Notion credentials** is `MISSING`, stop: the token lives in Doppler (project `toolbox`, config
`dev`, key `NOTION_TOKEN_V2`). On a machine that has never been set up, that is `doppler login` followed
by `doppler setup` — `doppler login` needs a real terminal, so ask the user to run it themselves rather
than trying it here. If **Local CSV fingerprint** is `MISSING`, the history mirror is gone — this becomes
a first-time import, so ask the user rather than proceeding.

**Every command that reaches Notion must run under `doppler run --`.** There is no on-disk credential
fallback by design; a bare invocation exits telling you to use Doppler.

On Windows, also prefix Python commands with `PYTHONIOENCODING=utf-8` — route titles contain `→`, which
crashes on the console's default cp1251 codec.

## 1. Load the browser tools

Invoke the `claude-in-chrome` skill, then load the tools in **one** ToolSearch call:

```
select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__tabs_close_mcp
```

## 2. Pull a fresh export

Call `tabs_context_mcp{createIfEmpty:true}`, create a **new** tab, and navigate it to
`https://my.flightradar24.com/settings/export`. Give it a moment — the tab title resolves to
`Export | myFlightradar24` once it has loaded.

Then fetch the export **same-origin** with `javascript_tool` and stash it on `window`:

```js
const r = await fetch('/public-scripts/export');
const t = await r.text();
window.__fr24 = t;
const lines = t.split(/\r?\n/).filter(l => l.trim());
const rows = lines.slice(1);
const dates = rows.map(l => l.slice(0,10)).filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d)).sort();
JSON.stringify({status: r.status, dataRows: rows.length, minDate: dates[0], maxDate: dates[dates.length-1]})
```

`status` must be 200 and `dataRows` must exceed the row count already in Notion. A redirect to a login
page means the session expired — ask the user to sign in to Flightradar24 in Chrome, then retry.

Read `references/fr24-export.md` **before improvising here**. It documents why `credentials: 'include'`
is rejected outright, why screenshots time out on this page, why clicking `DOWNLOAD CSV` doesn't produce
a file, and the ~1000-character output cap that shapes step 4.

## 3. Prove the export is purely additive

**Local CSV fingerprint** from Context already gives you `rows=N hash=H chars=C` for the local mirror.
Hash the same prefix of the fresh export and require agreement before appending.

```js
const rows = window.__fr24.split(/\r?\n/).filter(l => l.trim()).slice(1);
const h = s => { let x = 5381; for (let i=0;i<s.length;i++) x = ((x*33) ^ s.charCodeAt(i)) >>> 0; return x; };
window.__new = rows.slice(N);
JSON.stringify({hash: h(rows.slice(0,N).join('\n')), chars: rows.slice(0,N).join('\n').length,
                newCount: window.__new.length, newDates: window.__new.map(l => l.slice(0,10))})
```

**Both hash and chars must match.** If they do, the new rows are strictly appended and step 4 can copy
them verbatim. If they don't, **stop and report it** — the user's history changed, so appending would
duplicate or diverge. Getting that wrong silently corrupts the table, so never "fix it up" and continue.

## 4. Retrieve the new rows

`javascript_tool` truncates its output at roughly 1000 characters, so pull **at most 3 rows per call**:

```js
window.__new.slice(0,3).join('\n')
```

then `window.__new.slice(3,6)`, and so on. Check each returned line ends in the trailing numeric ID
columns — a line cut mid-field means the slice was too big.

## 5. Append to the local CSV

Write the rows verbatim to `tools/flightradar/data/flights.csv` (LF endings, UTF-8, no BOM, trailing
newline). This file is gitignored — it is the local mirror of the logbook, and the sync's diff depends
on it staying faithful.

```bash
PYTHONIOENCODING=utf-8 python <<'PYEOF'
from pathlib import Path
NEW = '''<rows, one per line>
'''
with open(Path("tools/flightradar/data/flights.csv"), "a", encoding="utf-8", newline="") as f:
    f.write(NEW)
PYEOF
```

Then **prove the mirror is now identical to the live logbook** — not just that the prefix matched before:

```bash
python .claude/skills/flightradar24/scripts/csv_hash.py
```

Its `rows`/`hash`/`chars` must equal the **full** export's, hashed in the page over every data row:

```js
const rows = window.__fr24.split(/\r?\n/).filter(l => l.trim()).slice(1);
const h = s => { let x = 5381; for (let i=0;i<s.length;i++) x = ((x*33) ^ s.charCodeAt(i)) >>> 0; return x; };
JSON.stringify({rows: rows.length, hash: h(rows.join('\n')), chars: rows.join('\n').length})
```

Do not skip this. Step 3 only proved the *old* rows matched; this is what proves the *append itself* was
faithful, and it is the check that catches a truncated paste, a row pasted twice, a mangled encoding, or
rows appended in the wrong order. Without it, a bad append survives until the next sync, by which point
it has already been pushed to Notion. If the numbers disagree, fix the CSV before going near Notion.

## 6. Dry run, then confirm

```bash
PYTHONIOENCODING=utf-8 doppler run -- python .claude/skills/flightradar24/scripts/main.py sync <page-url> --dry-run
```

This reparses the whole history, queries the live table, and lists exactly what it would add. Check the
"rows already in Notion" figure matches the count before your append — if the diff is larger than the
rows you just added, the dedup key missed something; investigate rather than writing.

**Show the user the list and get their go-ahead before step 7.** It writes to their data.

## 7. Snapshot the table before writing

**Required — do not skip.** This is the only thing that can prove afterwards that the sync appended and
nothing else:

```bash
PYTHONIOENCODING=utf-8 doppler run -- python .claude/skills/flightradar24/scripts/reconcile.py <page-url> \
  --snapshot tools/flightradar/data/presync-snapshot.json --skip-csv
```

It records a fingerprint of every existing row plus each view's column layout, colour rules, sort/group
query and group entries. The file lands in the gitignored data directory.

## 8. Sync

```bash
PYTHONIOENCODING=utf-8 doppler run -- python .claude/skills/flightradar24/scripts/main.py sync <page-url>
```

This extends the `trip` select options and every view's group list, then inserts the rows. See
`references/notion-db.md` for what those two steps are protecting — in short, a new trip with no
matching option and group entry lands in the catch-all bucket instead of its own group, and rewriting
the options array without preserving existing IDs orphans every cell already using them.

## 9. Verify — nothing but appends

```bash
PYTHONIOENCODING=utf-8 doppler run -- python .claude/skills/flightradar24/scripts/reconcile.py <page-url> \
  --against tools/flightradar/data/presync-snapshot.json
```

**This must print `OK` and exit 0.** It runs two checks that fail in opposite directions:

- **Append-only check** — every pre-existing row still present with identical properties, no row
  removed or modified, and in *both* views the column layout, colour rules and sort/group query
  unchanged, with group entries only ever added (never reordered, hidden or dropped). Any `ROW
  MODIFIED`, `ROW REMOVED` or `VIEW CHANGED` line is a failure: report it and stop rather than
  patching over it.
- **CSV reconciliation** — every live row still equals the value recomputed from the full CSV, with no
  duplicates and nothing missing. This catches the reverse failure, where a row *should* have changed
  and didn't: trips renumber when a flight is back-filled mid-history, and a new flight can flip the
  previous flight's layover/stay flag and therefore its bold marker. Sync only ever appends, so it
  cannot fix those on its own — if `ROW DRIFTED FROM CSV` appears, the table needs rows updated, which
  is a decision for the user.

Then run the view-level eyeball check:

```bash
PYTHONIOENCODING=utf-8 doppler run -- python .claude/skills/flightradar24/scripts/verify.py <page-url>
```

Confirm the highest `Tn` option matches the newest trip, both views carry one group per trip plus the
catch-all and one `color_rules` entry, and on the new rows `parity` keeps alternating per trip.

Sanity-check the bold flags against the rule rather than assuming — a destination reached and left again
within 12 hours is a layover and correctly stays unbolded, which reliably looks like a bug at a glance.
Home cities never bold. `references/notion-db.md` has the full rule set.

Finally re-run step 6's dry run: it must report **nothing to add**, proving the sync is idempotent and
the dedup key round-trips. Then delete the snapshot file.

## 10. Clean up and report

Close the Chrome tab you created. Report the added flights as a table (date, route, trip, flight
number), and call out any bold decision that looks surprising — especially an unbolded destination that
was a short layover — so the user can see it was deliberate.

## Out of scope

- Do **NOT** run `main.py create` against a page that already has a database — it builds a *second*
  table and discards the user's renamed views and hand-set column widths. `create` is first-import only.
- Do **NOT** edit or delete existing rows. Sync is append-only; a changed history is a stop-and-ask.
- Do **NOT** propose adding columns for the CSV fields the table omits (seat type, seat number, FR24's
  internal IDs). That was considered and declined — see the "Deliberately not stored" section of
  `references/notion-db.md`.
- Do **NOT** attach the CSV export to the page. The host page holds the database and nothing else.
- Do **NOT** deduplicate the user's FR24 logbook. Re-exports can legitimately contain duplicate rows;
  report them and let the user clean up their logbook. See `references/fr24-csv-quirks.md`.
- Do **NOT** commit. The code lives here, but the CSV is gitignored and committing is the user's call.
