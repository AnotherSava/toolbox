# toolbox

A collection of small tools for day-to-day life.

## Tech Stack

- Python 3.12+
- Playwright (browser automation)
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

## Browser Profiles

Tools that automate websites store browser profiles under `.browser_profiles/<site>/` at the project root (e.g., `.browser_profiles/facebook/`). Multiple tools targeting the same site share one login session. This directory is gitignored.
