# toolbox

A collection of small tools for day-to-day life.

## Tech Stack

- Python 3.12+
- Playwright (browser automation)
- pytest (testing)

## Folder Structure

Each tool is a self-contained subpackage under `tools/`:

```
tools/<tool_name>/        # tool implementation
tests/<tool_name>/        # tests for the tool
```

## Adding a New Tool

1. Create `tools/<name>/` with `__init__.py` and implementation modules
2. Create `tests/<name>/` with `__init__.py` and test modules
3. Add a console script entry point in `pyproject.toml` under `[project.scripts]`

## Commands

- Run tests: `pytest`
- Install for development: `pip install -e ".[browser,test]"`

## Browser Profiles

Tools that automate websites store browser profiles under `.browser_profiles/<site>/` at the project root (e.g., `.browser_profiles/facebook/`). Multiple tools targeting the same site share one login session. This directory is gitignored.
