# Researching next-edition dates

## Small number of rows (typical maintenance run)
Just web-search each flagged convention inline: fetch the organizer's official site, cross-check against
BoardGameGeek / tabletop.events. Apply the "next edition" rule from SKILL.md. Update the row with
`notion-update-page`. This is usually all a periodic refresh needs — only the editions that finished since the
last run roll forward.

## Many rows (e.g. a yearly full re-verify)
Fan out with the Workflow tool: a `pipeline` over the conventions, each item going through a **research** agent
then an independent **verify** agent that re-searches from scratch before the date is trusted. Use
`agentType: 'general-purpose'` (they need `WebSearch`/`WebFetch`) and force structured output with a schema.

Embed this rule verbatim in both prompts (substitute today's date):

> Find the soonest edition of THIS specific convention whose END date is on/after {TODAY}. If the {year} edition
> already ENDED before {TODAY}, use the next year's edition. Match the city/region in the name so similarly-named
> cons aren't confused. Return official (organizer-confirmed) vs estimated, ISO `YYYY-MM-DD` start/end (null if
> genuinely unannounced), a source URL, and confidence.

Have each agent return `{found, start, end, edition_year, official, confidence, source_url, notes}`; the verifier
returns `{agree, final_start, final_end, official, confidence, sources, notes}`. Prefer the verifier's dates.
Leave dates blank (and note it) for cons that are unannounced or defunct rather than guessing.

## If a research agent hangs
Observed: an agent can fetch the answer but freeze before emitting its structured result, stalling the whole
pipeline. Recovery, in order:
1. `TaskStop` the workflow.
2. **Resume**: re-invoke `Workflow` with `{scriptPath, resumeFromRunId}` **and re-pass the same `args`** — completed
   agents replay from cache, only the hung one re-runs. Omitting `args` on resume crashes the script (`args` is undefined).
3. If it hangs again, **harvest** completed results instead of re-running: read the run's `journal.jsonl`
   (`type=="result"` entries carry each agent's returned object) under
   `~/.claude/projects/<project>/subagents/workflows/<runId>/`, map agents→conventions by scanning each
   `agent-*.jsonl` transcript for its `Convention: "<name>"` prompt line, and pull the missing one's answer
   straight from its transcript.
