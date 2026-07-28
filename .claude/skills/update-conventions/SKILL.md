---
name: update-conventions
description: >-
  Refresh the board-game Conventions Notion database — roll finished editions forward to their next year,
  clear the Estimate flag once organizers announce firm dates, recompute the date-conflict highlights,
  and sync ticket status from Gmail. TRIGGER when: the user wants to update, refresh, or re-check the
  conventions table (its dates, tickets, or conflicts), e.g. "update the conventions", "refresh convention
  dates", "re-check my convention tickets". DO NOT TRIGGER for other Notion databases, or for the one-time
  RTM→Notion migration.
---

# Update the Conventions table

Periodic maintenance of one Notion database: a calendar of board-game conventions the user might attend.
Each row is the **next** upcoming edition of a recurring annual convention. Over time editions finish,
organizers announce future dates, and the user buys tickets — this skill re-syncs the table with reality.

## Context
- Today: !`date +%F`

## Database coordinates

Run everything against the user's connected Notion workspace via the **Notion MCP plugin** (`mcp__plugin_Notion_notion__*`).
For the operations the MCP layer can't do (recolor/remove select options, set date format, trash a row) use the
toolbox **`notion_tools` v3 client** — see `references/v3-operations.md`.

| What | ID |
|---|---|
| Database (page) | `664b5b1159274639bbacb903b790d567` |
| Data source (collection) | `collection://4a9aa87c-c7e3-4e36-baf3-a9a9fbcfece4` |
| Space | `0b9a0494-0efd-81e7-8eab-00038a20f15d` |
| Default table view | `24803935-6640-47cc-a4e6-29da6167f4a2` |
| Calendar view (keys on `Start`) | `3aba0494-0efd-8149-badd-000c9381352f` |

If an ID ever fails, re-locate the database with `notion-search "Conventions"` (it lives under the "Remeber the Milk" page).

## Schema

| Property | Type | Meaning / rules |
|---|---|---|
| `Task` | title | Convention name **only** — no date, no location (those have their own columns). |
| `Location` | text | `City, ST` (or `City, Country`). |
| `Start`, `End` | date (`ll` fmt) | The next edition's date range. `ll` renders as the long month ("September 5, 2025") — see date-format note below. |
| `Dates` | select | Only value is `Estimate` (yellow) = projected from the usual weekend. **Blank = confirmed** — organizer-announced dates get no pill (blank is the default). |
| `Plans` | select | `Considering` (yellow) · `Planned` (blue) · `Ticket` (green). Empty = undecided. The skill only ever sets `Ticket` (from email evidence); it never overwrites a `Plans` value already set by the user by hand. |
| `Priority` | select | `P1`/`P2`/`P3` (user-owned; don't touch). |
| `Link` | url | Official site / durable registration page. |
| `Notes` | text | Terse: estimate basis ("Memorial Day weekend"), or hiatus/defunct explanation. |
| `Conflict` | select | Color-coded date-collision window (see step 4). The user applies Notion conditional row-coloring on this property. |
| `Early bird deadline` | date | Early-bird ticket-price deadline for the upcoming edition — **only for cons without a `Ticket`**. Blank = none published / not applicable. On `Planned`/`Considering` rows this date carries a Notion "1 week before" reminder. |

## The "next edition" rule (load-bearing — used in steps 2–3)

For each convention find the **soonest edition whose `End` is on/after today**:
- If the current edition is still upcoming or in progress (ends today or later) → keep it.
- If it **already ended before today** → move to next year's edition.
- Leave `Dates` **blank** when the organizer has officially posted the dates (blank = confirmed, the default).
  Set `Dates = Estimate` only for a projection, with a one-phrase basis in `Notes` (e.g. "Presidents' Day weekend", "2nd weekend of July (low confidence)").
- Truly dead/hiatused cons: blank `Start`/`End`, explain in `Notes`, leave `Dates` empty.

## Procedure

### 1. Pull current state
`notion-query-data-sources` (SQL mode) over the collection:
`SELECT url, "Task", "Location", "date:Start:start" AS start, "date:End:start" AS "end", "Dates", "Plans", "Link", "Notes", "Conflict" FROM "collection://4a9aa87c-c7e3-4e36-baf3-a9a9fbcfece4" ORDER BY "date:Start:start"`

### 2. Decide what needs a refresh
A row needs re-research if **any** holds:
- `End` < **Today** (its edition has passed — roll forward).
- `Dates = Estimate` (check whether official dates were announced since last run → if so, clear `Dates` to blank).
- The user flagged a specific convention.
Rows whose edition is still comfortably in the future and already `Confirmed` can be skipped.

### 3. Research next-edition dates
For each flagged row, web-search the organizer's official site / BoardGameGeek / tabletop.events for the next
edition per the rule above. Update `Start`, `End`, `Dates`, and (if better) `Link`, `Location`, `Notes` via
`notion-update-page` (`update_properties`, keys `date:Start:start`, `date:End:start`, `Dates`, …).
When **many** rows need it, fan the research out with a verification pass — see `references/next-edition-research.md`
(also covers the cutoff prompt and how to recover if a research agent hangs).

### 4. Recompute `Conflict`
Overlaps change whenever a date moves. From the updated `Start`/`End` ranges, compute clusters where ranges
intersect (`startA ≤ endB and startB ≤ endA`). Give each collision window one `Conflict` value (label it by the
overlap window, e.g. `Sep 4-9`); every convention in that window gets that value; non-overlapping rows are blank.
Assign colors so **date-adjacent windows contrast** (they sit next to each other in the sorted table). Adding,
recoloring, or removing `Conflict` options requires the v3 client — see `references/v3-operations.md`.

### 5. Sync tickets from Gmail
Search the user's Gmail for ticket/badge confirmations and set `Plans = Ticket`. **Match each confirmation to the
edition YEAR the row now represents** — a ticket for a past edition does not count. Full query set and platform
list in `references/ticket-sync.md`.

### 6. Early-bird deadlines & reminders
For rows **without** a `Ticket`, WebFetch the official registration page / ticketing host (tabletop.events,
ticketspice, eventbrite, showclix) for the early-bird price deadline of the upcoming edition — never reuse a past
edition's. Write it to `Early bird deadline`; leave blank if registration isn't open or there's no early-bird tier.
On `Planned`/`Considering` rows that have a deadline, attach a Notion **"1 week before"** reminder to that date
(MCP can't set reminders — use the reminder snippet in `references/v3-operations.md`).

### 7. Report
Summarize the changes (rolled editions, cleared Estimate flags, new/removed conflicts, new tickets, early-bird deadlines).
**Confirm before destructive edits** — trashing a defunct convention's row, or blanking dates on a con that
merely hasn't announced yet.

## Date-format note
Notion honors custom `date_format` tokens (set via the collection schema, not MCP). `Start`, `End`, and
`Early bird deadline` use **`MMM d`** ("Jul 25" — abbreviated month, no year); `MM/DD/YYYY`, `YYYY/MM/DD`, and
`relative` also work. Set the token with the date-format snippet in `references/v3-operations.md`.

## Out of scope
- Do NOT re-run or reference the RTM→Notion migration, initial column creation, or title/location cleanup — those were one-time.
- Do NOT set `Priority`, `Considering`, or `Planned` — those are the user's to manage.
- Do NOT commit or push changes to the repo unless explicitly asked.
