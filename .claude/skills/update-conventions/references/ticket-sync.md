# Syncing ticket status from Gmail

Use the Gmail MCP tools (`mcp__claude_ai_Gmail__search_threads`, `get_thread`). These are interactively
authenticated — run them in the main loop, not inside a workflow subagent. `search_threads` returns subject +
snippet, which is usually enough to confirm a purchase without opening the thread.

## The critical rule: match the edition, not just the convention
A confirmation only counts if it's for the **edition the row now represents**. Board-game cons are annual; a
ticket for a past edition does not carry to next year's row. Check the year / edition number in the subject or
confirmation code (e.g. `BTTSCNFLL2026` = BottosCon **Fall 2026**; "TraXX 6" = the 2026 edition). Exception: a
ticket explicitly **rolled over** to next year counts for the new edition (the user sometimes emails an organizer
to roll a missed ticket forward).

Set `Plans = Ticket` for a paid badge/pass, only from real ticket evidence. Never overwrite a `Plans` value the
user set by hand; you may upgrade a `Considering`/`Planned` con to `Ticket` once its purchase is confirmed.

## Where tickets come from (search these)
| Platform / sender | Cons seen | What a purchase looks like |
|---|---|---|
| `con.<name>@tabletop.events` | Dragonflight, Messen ACE, BGG cons, many US cons | Receipt with a badge line: "3-Day Full Access", "full pass", "Early bird full pass". Ignore $0 game-signup receipts — the badge/pass line is the ticket. |
| `noreply@order.eventbrite.com` | TraXX and smaller cons | "Order Confirmation for <con N>" |
| `<con>@ticketspice.com` | BottosCon | "Registration Confirmation … Regular Pass $x" |
| `tickets@sched.com` | Terminal City | "Accept your … tickets — Ticket purchase completed" |
| `noreply@www.gencon.com` | Gen Con | "You Have a Badge for Gen Con …" — confirm it's a paid badge (some are comped) before `Ticket` |
| Stripe receipts (`receipts@…stripe.com`) | some organizers (e.g. Plaid Dog Events) | dollar receipt; correlate date/amount to a con |

## Suggested searches (broad → specific)
- `from:tabletop.events`
- `from:eventbrite (order OR ticket OR confirmation)`
- `(gencon OR "gen con" OR pax OR essen OR badge OR convention OR tabletop OR boardgame) (badge OR ticket OR registration OR "order confirmation" OR receipt) after:<~last 12 months>`
- Then targeted per-con searches for any table row not yet resolved.

Report matches as a table (convention · evidence · Plans value) and note which found tickets were for *past*
editions (so the user sees they weren't missed), before writing the `Plans` updates.
