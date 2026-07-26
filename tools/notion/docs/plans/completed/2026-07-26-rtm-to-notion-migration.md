# Remember The Milk → Notion migration

## Overview

Migrate a 14-year Remember The Milk task history into a single Notion collection that starts as a triage pile and settles into a searchable archive. The schema design, the data analysis, and the importer are done; what remains is running it against the real Notion workspace, verifying the result, and the one manual step (sub-items) that no API exposes.

The importer is written but **has never touched a live Notion workspace** — it was verified only against an offline stub. Treat the first run as the risky step and do it against a scratch page.

## Context

- Files involved:
  - Exists: `tools/notion/docs/examples/rtm_transform.py` — export → flat records. Pure data, no Notion. Tested.
  - Exists: `tools/notion/docs/examples/rtm_to_collection.py` — the v3 importer. Untested against live Notion.
  - Exists: `tools/notion/docs/examples/rtm_to_collection_selftest.py` — offline replay of the op stream.
  - Exists: `tools/notion/docs/examples/README.md` — updated with both entries and the run sequence.
  - Read: `tools/notion/docs/learnings/notion-api-quirks.md` — three of its findings are load-bearing here.
  - Update at the end: `tools/notion/docs/learnings/notion-api-quirks.md` with whatever the first live run teaches.
- Input: the RTM JSON export (`rememberthemilk_export_20260531T08_47_11.464Z.json`). Not in the repo and **should not be committed** — its `lists[].token` fields are credential-shaped.
- Related patterns: `tools/flightradar/src/notion_db.py` is the closest sibling (collection + schema + batched rows + view format). `tools/notion/docs/examples/plain_to_collection.py` for the block-creation pattern.
- Dependencies: `notion_tools` (installed package, `token_v2` from `tools/notion/config/config.json`), `requests`. No new dependencies.

## Development Approach

- Testing approach: the offline self-test already exists and passes; keep it passing after any edit to either script.
- Run against a scratch Notion page first. Verify, then trash and re-run against the real host page, or keep it if it looks right.
- The importer is resumable (`rtm_import_state.json`, keyed by RTM ID) — on failure, fix and re-run rather than starting over.
- **CRITICAL: do not dedupe rows on task name.** Four recurring series have several occurrence rows sharing a name; they are real history.

---

## Design notes

### What the export actually contains

Measured, not assumed. All counts from the 2026-05-31 export.

| | |
|---|---|
| tasks | 1,156 — 292 open, 864 completed |
| date range | created 2012-02-13 → 2026-05-10; completed through 2026-03-22 |
| lists | 7, but **1,155 of 1,156 tasks are in Inbox** |
| smart lists | 4 (one is the empty-filter "All Tasks") |
| tags | 45 declared, 43 used, 2 dead (`canada`, `snowboard`) |
| subtasks | 167 under 46 parents; depth 2 in two cases; largest parent has 19 children |
| notes | 395 across 288 series; avg 191 chars, longest 5,033 |
| recurrence | 13 rows across 4 series, all `document-expiry` |
| dates | 237 rows have one; 53 of the open ones; 26 of those already past |
| URLs | 252 rows (81 open) |
| unused | estimate (absent from the export entirely), location (1), attachment (1), postponed (4), contacts/sharing (single user) |

**There is no project structure to migrate.** The lists are dead. Anything that assumes RTM lists map to Notion projects is wrong for this data.

**Tags are the whole taxonomy and they do three unrelated jobs.** This is the single most important finding:

- *Review cadence* — `reminder-daily/weekly/monthly/quarterly` plus one-offs `reminder-world` and `reminder-never`. 468 records. Exactly one task carries two of them, which is what confirms it's single-valued and belongs in a select rather than a tag list. (That task is `galaxy lamp $119-129`, Daily + Weekly; the transform keeps Daily and warns.)
- *Readiness* — `new_and_ready`, 52 records. A boolean. The `important new` smart list filters on it.
- *Topic* — 36 distinct, 35 after merging `internet.actual` (3 rows) into `internet` (55).

**169 of the 292 open tasks have neither a date nor a cadence tag.** Nothing in the RTM setup would ever surface them again. The `Untriaged` view exists specifically for this pile and it is the first thing to work down.

**The date field means three different things.** A deadline, a document's expiry (`Visa US` → 2035, `NEXUS` → 2031), and a convention's start date (31 open rows with real event dates through 2027). That's why the property is called `Date` and not `Due` — an "Overdue" view built on a `Due` label would be wrong about a third of its rows. Topic-scoped views supply the meaning instead.

**Recurrence is a non-problem.** The export carries `repeat_every: true` and nothing else — no rule, no interval, no unit. RTM materialised each occurrence as its own row. Import the 13 rows as 13 rows and set the next date by hand four times a year.

### Schema decisions

**One database, not two.** Earlier drafts split completed history into a separate archive; that was solving for a deletable landing zone. Since nothing is being deleted, the split only costs: cross-database moves drop properties that don't name-match, whereas a status filter costs nothing. It also avoids tearing apart the seven containers that are open with completed children (`Amazon Prime`: 8 open / 9 done, `Aliexpress`: 3 / 7).

**Rows leave the working surface three ways**, and only one removes them from the database: *extracted* into a purpose-built database, *archived* in place (`Triage = Archived`, where all 864 completed rows start), or *still to decide*. `Triage` also has an `Extract later` value, because you will spot things worth extracting before the destination for them exists.

**Cadence is a recommendation, not a rule — do not compute a review date from it.** The tempting move is `Next review = Last seen + 30 days` for Monthly. Don't. It converts 71 open tasks into dated obligations, most of which get blown past, and within two months there's a large red overdue count that means nothing except that it was a busy month. Worse, it devalues the one place a date *is* a rule: `document-expiry`, where an external authority sets the date. Cadence groups and sorts; it never filters by a threshold. The `Browse by cadence` view sorts oldest-untouched first so neglect surfaces on its own.

**Notes go in page bodies, not a property.** Three reasons, in increasing order of importance: they're prose; page content survives a Move-to between databases whereas unmatched properties are dropped; and Notion's workspace search indexes page body text but **excludes select and multi-select values** from results. Search for a word in a note and you'll find it. Search for `conventions` and you will *not* find rows tagged that way — tag retrieval has to come from a saved view.

**Property names are a contract with databases that don't exist yet.** The plan is to extract useful items into purpose-built databases over time. Notion's Move-to preserves a property only where the destination has one of the same name and compatible type; anything unmatched is dropped silently, with no warning. So these names are frozen: `Task`, `Link` (not `URL`), `Date`, `Topic`, `Priority`, `Created`, `Completed`, `RTM ID`. Every future destination reuses them exactly, and pre-creates its select/multi-select options or values arrive empty. The scaffolding properties — `Triage`, `Ready`, `Cadence`, `Start`, `RTM series`, `Modified` — are not part of that contract.

**Keep `RTM ID` everywhere, forever.** It makes the import retryable and it's the only stable join back to the export JSON. `RTM series` is how the 395 notes find their tasks, and how the four recurring families stay recognisable.

### Why the internal v3 API rather than the public one

Both were built; v3 won on two counts.

**Throughput.** Rows batch 50 to a `saveTransactionsFanout` call and note blocks batch 150 — 56 transactions for the whole import. The public API is one HTTP call per page, rate-limited to ~3/s: ~1,325 calls, about 8 minutes.

**Views.** The public API cannot create views at all. v3 can, so all ten working views ship with the import instead of being clicked together afterwards.

The public-API version still exists as a fallback if v3 auth becomes a problem; it needs an internal integration token and a manual `status`-property fix-up.

### Notion facts verified against documentation

- Sub-items are enabled from the database menu → *More settings* → *Sub-items*, creating paired relation properties. **Not exposed by either API** — this is the one unavoidable manual step. Sub-items exist only within a single database, and deleting a parent deletes its children.
- Sub-item filtering: table/list/timeline views offer *parents only* / *parents and sub-items* / *sub-items only*; board, calendar and gallery views offer only *parents only* for filtering, though they do have a "flattened list" display option that shows children as separate cards.
- Notion's row cap is 250,000 per database and 500 properties; performance guidance is about visible columns and filters that run on formulas/rollups rather than native properties. At 1,156 rows none of this bites.
- Deleting moves to Trash for 30 days, then a further 30 during which support can recover. **Restoring a database *version* from version history restores pages and properties but not the contents of database pages** — it would silently drop all 395 notes. If an undo is ever needed, restore from Trash, not version history.
- Repeating database templates support daily/weekly/monthly/yearly plus a custom pattern option, but fire on schedule regardless of whether the previous instance was completed — wrong for renewals, where the clock should start when you actually renewed.
- The public API cannot create a `status`-type property (hence `select`).

Three items from `notion-api-quirks.md` drive the implementation directly: child blocks need **both** a `parent_id` and a `listAfter` into the parent's `content` array or they exist but don't render; grouped views need both `query2.group_by` and `format.collection_groups` including the catch-all unset bucket; and the way to learn an unknown v3 field shape is to set the feature up in the UI, then `syncRecordValues` the record to see what Notion persisted.

### What the self-test proves, and what it does not

`rtm_to_collection_selftest.py` stubs `notion_tools.client` and replays every operation. It currently passes and asserts: 1,156 rows created, 1,713 note blocks, 10 views, every note block both parented and `listAfter`-ed, every property key present in the schema, every select value declared as an option, every multi-select part declared, well-formed date payloads, no duplicate rows after a simulated crash-and-resume, and 167 well-formed relation values in phase 3.

It **cannot** prove Notion accepts these field names. Specific things to watch on the first live run, roughly in order of risk:

1. **View filter operators.** `enum_is`, `enum_contains`, `is_empty`, `is_not_empty` are used. If a view comes out unfiltered or errors, that's the cause. Each view is sent in its own transaction so one failure can't take the other nine down — check the console for `! view <name> failed`.
2. **The `url` schema type.** If v3 rejects it, fall back to `text`; the value shape `[[str]]` is identical either way.
3. **`multi_select` as a comma-joined string.** Verified that no topic contains a comma, so the encoding is safe — but confirm the pills render as 35 separate options and not one long one.
4. **Datetime payloads.** Only 20 rows have a time component; check one of them renders with a time.
5. **`collection_groups`** on the cadence view — if grouping doesn't appear, this is the field to inspect.

---

## Implementation Steps

### Task 1: Dry run and sanity check

- [ ] `python tools/notion/docs/examples/rtm_to_collection.py <export.json> --dry-run`
- [ ] Confirm the counts match this document: 1,156 records / 292 open / 864 archived / 167 with parent / 237 with date / 252 with link / 468 with cadence / 395 notes / 35 topics
- [ ] Confirm exactly one warning, about `galaxy lamp $119-129` carrying two cadence tags
- [ ] `python tools/notion/docs/examples/rtm_to_collection_selftest.py <export.json>` — must print `ALL CHECKS PASSED`

### Task 2: First live run against a scratch page

- [ ] Create a throwaway Notion page; copy its URL
- [ ] `python tools/notion/docs/examples/rtm_to_collection.py <export.json> <scratch-page-url>`
- [ ] Watch for `! view <name> failed` lines; note which operators were rejected
- [ ] If it dies partway, fix and re-run — `rtm_import_state.json` resumes; delete that file only when starting genuinely fresh

### Task 3: Verify the result in the UI

- [ ] Row count is 1,156
- [ ] `Archive` view shows 864; `Remaining` shows 292
- [ ] Open a row with notes (e.g. any row in the 288 noted series) — headings and paragraphs present and in order
- [ ] `Topic` renders as 35 separate pills, not one joined string
- [ ] A dated row with a time component renders with the time (20 such rows)
- [ ] `Browse by cadence` is actually grouped, with the unset bucket present
- [ ] `Documents & renewals` sorts ascending by date and shows 12 open rows
- [ ] All ten views exist and each is filtered as described
- [ ] Fix anything broken in the scripts, re-run the self-test, re-run the import

### Task 4: Sub-items

- [ ] In Notion: database `...` → *More settings* → *Sub-items* → Turn on
- [ ] `python tools/notion/docs/examples/rtm_to_collection.py <export.json> --parents`
- [ ] Confirm it reports 167 of 167 linked
- [ ] Spot-check `Amazon Prime` (16 children), `games` (19), `Aliexpress` (9)
- [ ] Set the main table's sub-item display to "nested in toggle" so large containers collapse
- [ ] Optional: `syncRecordValues` the collection and record the real sub-item schema shape in `notion-api-quirks.md` — that would let a future run skip the manual toggle

### Task 5: Post-import fix-ups

- [ ] Convert `Status` from a select to a real Status property if the grouped To-do/Done behaviour is wanted (use the quirks-file technique to learn the shape, or just do it in the UI)
- [ ] Switch the `Conventions` view to a calendar layout on `Date` — it was left as a table because the calendar `query2.calendar_by` / `format.calendar_properties` shape is unverified. One click in the UI, or script it and record the shape.
- [ ] Decide the fate of `internet` (29 open) and `order` (19 open). Both are barely narrower than "things I might do" and make weak extraction batches; they may want splitting before they suggest a destination.
- [ ] Move the collection to its permanent host page, inside a plain wrapper page so future extracted databases can be siblings

### Task 6: Begin extraction

Not code — the point of the whole exercise. Order matters; the first one is the highest value in the export.

- [ ] **Documents & renewals first.** 12 open rows: NEXUS, both passports, driver's licence, BC Service Card, four credit cards, Visa US. Real expiry dates, real consequences, and RTM never gave them a good home. Build the destination database with the contract property names (`Task`, `Date`, `Link`, `Topic`, `RTM ID`), pre-create its options, move one row, verify every property arrived, then move the rest.
- [ ] Conventions (31 open, dated through 2027) — wants its own database with a calendar
- [ ] Buy (21 open + the `Amazon Prime` / `Aliexpress` containers, 25 children between them)
- [ ] Reading & watching (`book`, `boardgames`, `education`, `entertainment`, plus the `books` / `movies` / `games` containers)
- [ ] Work the `Untriaged` view down — 169 rows, the silent backlog

**Bulk-move gotchas.** Notion lazy-loads long tables, so "select all" grabs only the rendered rows — work inside the filtered views, each of which loads fully. Any destination receiving a container needs sub-items enabled *first*, or its children become top-level rows; move parent and children in one selection.

### Task 7: Documentation

- [ ] Add whatever the live run taught to `tools/notion/docs/learnings/notion-api-quirks.md` — especially the working filter-operator shapes, the calendar-view format, and the sub-item schema shape if it got inspected
- [ ] Update `tools/notion/docs/examples/README.md` if either script's interface changed
- [ ] Re-run the self-test; it must still pass
- [ ] Move this plan to `tools/notion/docs/plans/completed/`

---

## Acceptance criteria

- 1,156 rows in one Notion collection, no duplicates (check `RTM ID` is unique)
- 864 rows with `Triage = Archived` and a `Completed` date; 292 with `Status = To do`
- 395 notes present as page content across 288 rows
- 167 sub-item links, 46 parents, containers intact
- 10 views, each filtered and sorted as described
- The export JSON is untouched and uncommitted

## Rollback

Trash the collection_view block. Rows go with it; Trash holds for 30 days. Delete `rtm_import_state.json` and re-run from scratch. The export JSON is the real backup and nothing in Notion can damage it — the cost of a bad run is a few minutes, which is why the scratch-page step is cheap insurance rather than ceremony.

## Open questions for the user

- Where should the collection permanently live — which host page, which teamspace?
- Is `Start` worth keeping? Only 5 open rows use it, and the `important new` smart list was the only thing that consumed it.
- Should the two dead cadence values (`reminder-world`, `reminder-never`, one task each) be resolved into a real cadence or dropped?
