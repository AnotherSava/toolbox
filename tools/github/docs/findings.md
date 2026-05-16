# github tool — findings

Context captured from the conversation that produced `repos-status.sh`.
None of this is load-bearing for the script — it explains *why* the
defaults look the way they do.

## Repository discovery rules

The script walks `PROJECTS_ROOT` (default `/d/projects`) at `find -maxdepth 4`.
The user's deepest repo root is at depth 2 (`games/<repo>/`, `3d/<repo>/`),
so depth 4 (i.e. `<repo>/.git/`) is generous.

Hard exclusions:
- `_archive/` — user's archived projects, not active.
- `node_modules/` — defensive; rarely contains `.git` but cheap to filter.

## Ownership filter

Origin URL must match `github.com[:/]AnotherSava/`. This automatically
filters out third-party clones that happen to live under the projects root:

| Path | Origin |
|---|---|
| `games/achievement-watchdog` | `50t0r25/achievement-watchdog` |
| `games/gbe_fork` | `Detanup01/gbe_fork` |
| `games/gse_fork` | `alex47exe/gse_fork` |
| `games/ingame_overlay` | `Nemirtingas/ingame_overlay` |

Forks owned by AnotherSava are still counted as the user's repos even when
they have an `upstream` remote pointing at the original author. Known
forks at time of writing: `claude-mermaid-fix` (`upstream`: `veelenga`),
`InverseCSG` (`upstream`: `yijiangh`).

## Explicit exclusions

The `EXCLUDED` array filters out repos owned by the user that they don't
want in the report. Rationale was not given in the conversation that
introduced them — they were removed by user request:

- `notion`
- `claude-mermaid-fix`

Edit the array in `scripts/repos-status.sh` to add or remove entries.

## "Last pushed" semantics

The pushed-date column is the committer date of `HEAD` of the local
tracking ref `@{upstream}`. **No `git fetch` is run.** If the local
clone has been idle and the remote has advanced, the displayed date
will lag reality. Run `git fetch --all` across repos beforehand if you
need an authoritative snapshot.

`unpushed` counts commits in `@{upstream}..HEAD` and shares the same
caveat.

Branches with no upstream show empty fields and sort to the bottom.
