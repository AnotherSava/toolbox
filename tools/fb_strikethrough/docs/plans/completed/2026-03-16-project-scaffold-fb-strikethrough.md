# Project Scaffold + Facebook Strikethrough Tool

## Overview

Set up the toolbox project structure (README, CLAUDE.md, pyproject.toml, folder layout) to support a growing collection of small day-to-day utilities, then implement the first tool: a Playwright-based CLI that edits an existing Facebook group post to replace its text with a Unicode strikethrough version.

## Context

- Files involved:
  - Create: `README.md` — project overview and tool catalog
  - Create: `CLAUDE.md` — development conventions
  - Create: `pyproject.toml` — Python project config with console script entry points
  - Create: `.gitignore` — standard Python + browser profile ignores
  - Create: `tools/__init__.py`
  - Create: `tools/fb_strikethrough/__init__.py`
  - Create: `tools/fb_strikethrough/main.py` — CLI entry point + Playwright automation
  - Create: `tools/fb_strikethrough/strikethrough.py` — pure text-to-strikethrough conversion
  - Create: `tests/__init__.py`
  - Create: `tests/fb_strikethrough/__init__.py`
  - Create: `tests/fb_strikethrough/test_strikethrough.py` — unit tests for conversion
  - Create: `tests/fb_strikethrough/test_main.py` — CLI arg parsing tests
- Related patterns: none (greenfield project)
- Dependencies: `playwright` (browser automation), `pytest` (testing)

## Development Approach

- Testing approach: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Design Notes

**Target: Facebook group posts.** This tool edits posts within Facebook groups, not personal timeline posts. The post URL will be a group permalink like `https://www.facebook.com/groups/{GROUP_ID}/posts/{POST_ID}`.

**Facebook API is not viable.** Facebook removed write access to personal posts via the Graph API in 2018. Page post editing only works for posts created by your own app. The Graph API has no support for editing group posts. Playwright browser automation is the only path.

**mbasic.facebook.com is not viable.** Facebook redirects modern browsers from mbasic to the full site, and blocks older User-Agent strings entirely with a "download a modern browser" message. The basic HTML version cannot be used.

**Unicode strikethrough approach.** Facebook doesn't support markdown. Strikethrough is achieved by inserting Unicode combining character `U+0336` (COMBINING LONG STROKE OVERLAY) after each visible character. For example, `hello` becomes `h̶e̶l̶l̶o̶`. This is the standard used by every strikethrough generator (YayText, Piliapp, etc.) and the most visually consistent approach across devices. The conversion function must handle:
- Regular text characters (insert U+0336 after each)
- Existing U+0336 characters (skip to avoid double-striking)
- Newlines and whitespace (preserve as-is, don't strike spaces)
- Emoji and multi-codepoint sequences (best-effort — strike the base character)

**Shared browser profiles.** Browser profiles are stored under `.browser_profiles/<site>/` at the project root (e.g., `.browser_profiles/facebook/`). This way multiple tools that interact with the same site share one login session. The entire `.browser_profiles/` directory is gitignored. On first run, the user logs into Facebook manually. Subsequent runs reuse the session. This avoids storing credentials and works with 2FA.

**Headed mode only.** The browser window is always visible. This makes debugging easier and reduces the chance of Facebook flagging the session as suspicious.

**Auto-save after edit.** After replacing the text, the tool automatically clicks Save. No review step — the user can always edit the post again if needed.

**Playwright semantic locators for Facebook DOM.** Facebook's CSS classes are obfuscated garbage strings that change frequently (sometimes hourly). `data-testid` attributes were removed from production. The tool must use Playwright's semantic locators instead:
- `page.get_by_role()` — targets ARIA roles like `button`, `dialog`, `textbox`
- `page.get_by_text()` — matches visible text content
- `page.get_by_label()` — targets `aria-label` attributes

These are more stable than CSS selectors. All locators are defined as named constants in one place for easy updating when Facebook changes its UI. Reference: [jayremnt/facebook-scripts-dom-manipulation](https://github.com/jayremnt/facebook-scripts-dom-manipulation) for DOM interaction patterns.

**Folder structure.** Each tool lives in `tools/<tool_name>/` with a corresponding `tests/<tool_name>/` directory. The `pyproject.toml` registers console scripts so each tool gets its own CLI command. This keeps tools isolated while sharing the same virtualenv and project infrastructure.

```
toolbox/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .gitignore
├── .browser_profiles/
│   └── facebook/          # shared by all Facebook tools
├── docs/plans/
├── tools/
│   ├── __init__.py
│   └── fb_strikethrough/
│       ├── __init__.py
│       ├── main.py
│       └── strikethrough.py
└── tests/
    ├── __init__.py
    └── fb_strikethrough/
        ├── __init__.py
        ├── test_strikethrough.py
        └── test_main.py
```

## Implementation Steps

### Task 1: Project scaffold

**Files:**
- Create: `README.md`
- Create: `CLAUDE.md`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `tools/__init__.py`
- Create: `tests/__init__.py`

- [x] Create `pyproject.toml` with project metadata (name: `toolbox`, requires-python >= 3.12), dependencies (`playwright`), optional test dependencies (`pytest`), and a console script entry point: `fb-strikethrough = "tools.fb_strikethrough.main:main"`
- [x] Create `.gitignore` with standard Python ignores (`.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `dist/`, `*.egg-info/`) plus `.browser_profiles/`
- [x] Create `tools/__init__.py` (empty)
- [x] Create `tests/__init__.py` (empty)
- [x] Create `README.md` with project title ("toolbox"), one-line description ("A collection of small tools for day-to-day life"), a tools table with the first entry (fb-strikethrough), and basic setup instructions (clone, create venv, `pip install -e ".[test]"`, `playwright install chromium`)
- [x] Create `CLAUDE.md` with: project description, tech stack (Python 3.12+, Playwright, pytest), folder structure explanation, how to add a new tool (create `tools/<name>/`, `tests/<name>/`, add console script to pyproject.toml), commands to run tests (`pytest`), browser profiles convention (`.browser_profiles/<site>/` shared across tools), and the convention that each tool is a self-contained subpackage under `tools/`
- [x] Install the project in the venv: `pip install -e ".[test]"` and `playwright install chromium`
- [x] Run `pytest` (should pass with no tests collected)

### Task 2: Strikethrough conversion module

**Files:**
- Create: `tools/fb_strikethrough/__init__.py`
- Create: `tools/fb_strikethrough/strikethrough.py`
- Create: `tests/fb_strikethrough/__init__.py`
- Create: `tests/fb_strikethrough/test_strikethrough.py`

- [x] Create `tools/fb_strikethrough/__init__.py` (empty)
- [x] Create `tools/fb_strikethrough/strikethrough.py` with a `to_strikethrough(text: str) -> str` function that inserts `\u0336` after each visible character. Rules: skip whitespace (spaces, newlines, tabs), skip characters that are already followed by `\u0336`, handle empty string input
- [x] Create `tests/fb_strikethrough/__init__.py` (empty)
- [x] Create `tests/fb_strikethrough/test_strikethrough.py` with tests:
  - Basic conversion: `"hello"` → `"h\u0336e\u0336l\u0336l\u0336o\u0336"`
  - Preserves whitespace: `"hello world"` → struck "hello" + space + struck "world"
  - Preserves newlines: `"line1\nline2"` → struck lines with newline preserved
  - Empty string: `""` → `""`
  - Already struck text: idempotent (applying twice gives same result as once)
  - Unicode characters (e.g., accented letters)
- [x] Run `pytest` — must pass before next task

### Task 3: Playwright automation and CLI

**Files:**
- Create: `tools/fb_strikethrough/main.py`
- Create: `tests/fb_strikethrough/test_main.py`

- [x] Create `tools/fb_strikethrough/main.py` with:
  - `BROWSER_PROFILES_DIR` constant pointing to `.browser_profiles/` relative to project root
  - `FB_PROFILE_DIR` = `BROWSER_PROFILES_DIR / "facebook"`
  - `edit_post(url: str)` async function that:
    1. Launches Playwright Chromium with persistent context from `FB_PROFILE_DIR` (headed)
    2. Navigates to the group post URL
    3. Waits for page to settle
    4. Locates the specific post and clicks its three-dot menu using `page.get_by_role()` / `page.get_by_label()`
    5. Clicks "Edit post" in the dropdown using `page.get_by_text("Edit post")`
    6. Waits for the editor to appear (contenteditable / `[role="textbox"]`)
    7. Selects all text, reads it
    8. Converts via `to_strikethrough()`
    9. Clears and types the converted text into the editor
    10. Clicks the Save button using `page.get_by_role("button", name=...)` or `page.get_by_text("Save")`
    11. Waits for save to complete
    12. Closes browser
  - `main()` function: argument parser with required `url` positional arg, calls `asyncio.run(edit_post(url))`
  - `if __name__ == "__main__": main()` block
- [x] Create `tests/fb_strikethrough/test_main.py` with:
  - Test CLI arg parsing (url is required, missing url exits with error)
  - Test that `edit_post` calls Playwright with correct profile dir and headed mode (mock playwright)
  - Test that the strikethrough conversion is applied to extracted text (mock playwright page interactions)
- [x] Run `pytest` — must pass before next task

### Task 4: Verify acceptance criteria

- [x] Manual test: run `fb-strikethrough <real-group-post-url>` — first run should open browser for Facebook login, second run should reuse session and edit the post (skipped: no display/browser in CI environment)
- [x] Run full test suite: `pytest`
- [x] Verify no lint issues

### Task 5: Update documentation

- [x] Update README.md if anything changed during implementation
- [x] Update CLAUDE.md if internal patterns changed
- [x] Move this plan to `docs/plans/completed/`
