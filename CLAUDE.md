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

Standalone AHK scripts belong in `tools/ahk/scripts/`. Tool-specific AHK helpers (e.g., a Windows-only OS integration helper for a Python tool) live under the tool that owns them, in a `scripts/` subdirectory — for example, `tools/overlay_grid/scripts/overlay.ahk`.

For AHK conventions, taskbar-hiding patterns, folder-watch snippets, and the Windows auto-start shortcut recipe, see the global learnings file at `~/.claude/learnings/autohotkey.md`.

## Notion API

The notion tool uses Notion's undocumented internal API (v3), not the official REST API. See `tools/notion/docs/learnings/notion-api-quirks.md` for known gotchas (search result caps, response format quirks, archive vs trash semantics).

## Browser Profiles

Tools that automate websites store browser profiles under `.browser_profiles/<site>/` at the project root (e.g., `.browser_profiles/facebook/`). Multiple tools targeting the same site share one login session. This directory is gitignored.
