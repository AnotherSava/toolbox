# toolbox

A collection of small tools for day-to-day life.

## Tech Stack

- Python 3.12+
- Playwright (browser automation)
- requests (HTTP client)
- Pillow (image generation)
- pytest (testing)

## Folder Structure

Each tool is self-contained under `tools/`:

```
tools/<tool_name>/
├── __init__.py
├── src/              # source modules
│   ├── __init__.py
│   └── main.py
├── tst/              # tests
│   ├── __init__.py
│   └── test_main.py
├── config/           # tool-specific config (gitignored)
│   └── config.json
└── docs/             # tool-specific docs and plans
    ├── examples/     # one-off scripts using this tool — adapt, don't run as-is
    └── plans/
        ├── completed/
        └── draft/
```

## Docs and Plans

Plans and documentation live inside each tool at `tools/<tool_name>/docs/`. This is where `/plan-ralphex` and other skills should create plan files. There is no top-level `docs/` directory — each tool owns its own docs.

## Adding a New Tool

1. Create `tools/<name>/` with `src/`, `tst/`, and optionally `config/` subdirectories
2. Add `__init__.py` in each subdirectory (including the tool root)
3. In `pyproject.toml`:
   - Add the package name to `[tool.setuptools] packages`
   - Add the src mapping under `[tool.setuptools.package-dir]`: `<pkg_name> = "tools/<name>/src"`
   - Add a console script under `[project.scripts]`

## Subcommand or example?

When writing a script that uses one of these tools:
- **Polished, parametrized CLI for repeated use** → register under `src/` + `pyproject.toml` as a subcommand.
- **One-off workflow capturing a specific job** → place under `tools/<tool>/docs/examples/<name>.py` with an `EXAMPLE:` docstring header. Don't register as a subcommand. Use installed-package imports (`from notion_tools.client import ...`), not relative imports or `sys.path` hacks.

Extract reusable primitives into their own tool (e.g., `image_opt`) so each example is mostly glue. See `tools/notion/docs/examples/README.md` for live examples.

## Commands

- Run tests: `pytest`
- Install for development: `pip install -e ".[browser,test]"`

## AutoHotkey Tool

The `ahk` tool is a collection of AutoHotkey v2 scripts, not a Python package. It uses a simplified layout:

```
tools/ahk/
├── scripts/          # .ahk source files
└── docs/
```

No `src/`, `tst/`, or `config/` subdirectories. Not registered in `pyproject.toml`. Scripts run via the AutoHotkey v2 runtime (`AutoHotkey.exe`).

Standalone AHK scripts belong in `tools/ahk/scripts/`. Tool-specific AHK helpers (e.g., a Windows-only OS integration helper for a Python tool) live under the tool that owns them, in a `scripts/` subdirectory.

For AHK conventions, taskbar-hiding patterns, folder-watch snippets, and the Windows auto-start shortcut recipe, see the global learnings file at `~/.claude/learnings/autohotkey.md`.

## Flightradar24 Skill

The Flightradar24 → Notion importer is a **skill**, not a tool under `tools/`:

```
.claude/skills/flightradar24/
├── SKILL.md
├── scripts/          # main.py, sync.py, flights.py, notion_db.py, airports.py,
│                     # row_props.py, csv_hash.py, verify.py,
│                     # reconcile.py (append-only + CSV drift check)
└── references/

tools/flightradar/
└── data/             # gitignored CSV + OurAirports cache — the only thing left here
```

Keeping the logbook current is a procedure, not a single command: it fetches a fresh export from a
logged-in browser session, proves the export is purely additive, appends, then verifies. That sequence
belongs in a SKILL.md, so the code moved next to it and the `flightradar` console script and package
entry were removed from `pyproject.toml`.

Consequences worth remembering before "fixing" this layout back:

- The scripts are **not** an installed package. Sibling modules import by bare name (`from flights
  import ...`), which works because Python puts the script's own directory first on `sys.path`. Only
  `notion_tools` comes from the installed toolbox package.
- Run them by path from the repo root: `python .claude/skills/flightradar24/scripts/main.py sync <url>`.
- `main.py` resolves the data cache via `Path(__file__).resolve().parents[4]`, so moving the scripts
  to a different depth breaks the CSV and airports paths.

## Notion API

The notion tool uses Notion's undocumented internal API (v3), not the official REST API. For when to reach for v3 versus the Notion MCP integration, and the copy-paste recipes, see the global `notion` skill; `tools/notion/docs/learnings/notion-api-quirks.md` is the raw finding log behind it (search result caps, response format quirks, archive vs trash semantics).

## Secrets

The Notion `token_v2` cookie lives in **Doppler** (project `toolbox`, config `dev`, key `NOTION_TOKEN_V2`), not on disk. Anything that reaches Notion runs under `doppler run -- <command>`; `create_client()` reads the environment variable and has **no config-file fallback**, so a bare invocation fails with instructions instead of silently using a stale local token. A committed `doppler.yaml` pins project and config, so a fresh machine only needs `doppler login && doppler setup`.

Per-tool `config/config.json` files still exist for **non-secret** local settings (e.g. `fb_strikethrough`'s). The notion tool has none — the Doppler-held token is its only input. Never put a credential back in one.

## Browser Automation

Two patterns, chosen by **who owns the login session** — not by convenience:

- **Playwright with a stored profile** — the tool drives its own browser and keeps the session under `.browser_profiles/<site>/` at the project root (e.g. `.browser_profiles/facebook/`). Tools targeting the same site share one login. Gitignored. Use this whenever the workflow must run unattended, because the tool has to be able to authenticate on its own.
- **Claude in Chrome, driving the user's signed-in browser** — no stored profile at all: the session already exists in the user's Chrome and the extension acts inside it. Use this for interactive, skill-driven work where the login already exists and reproducing it headlessly would be the hard part. The `flightradar24` skill works this way to pull the FR24 export, which is why there is no `.browser_profiles/flightradar/`.

If a workflow needs to run without the user present, it needs its own profile under `.browser_profiles/`.
