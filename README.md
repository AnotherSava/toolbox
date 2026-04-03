# toolbox

A collection of small tools for day-to-day life.

## Setup

### Linux / macOS / WSL

```bash
git clone <repo-url> && cd toolbox
python -m venv .venv
source .venv/bin/activate
pip install -e ".[browser,test]"
playwright install chromium
```

### Windows (PowerShell)

```powershell
git clone <repo-url>; cd toolbox
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[browser,test]"
playwright install chromium
```

### Windows (cmd)

```cmd
git clone <repo-url> & cd toolbox
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e ".[browser,test]"
playwright install chromium
```

## Tools

### Facebook Strikethrough

Applies strikethrough formatting to a Facebook group post. Opens the post in a browser, enters the editor, and pastes the text back with native HTML strikethrough (`<s>` tags).

A marker string can be configured so that only paragraphs containing it get struck through (e.g., `"$"` to cross out lines with prices while keeping the rest intact). Without the marker, the entire post is struck through.

**CLI:**

```bash
fb-strikethrough <post-url>
fb-strikethrough              # prompts for URL
```

On first run a browser window opens for Facebook login. The session is saved and reused on subsequent runs.

**Config:**

`tools/fb_strikethrough/config/config.json`

```json
{
  "marker": "$"
}
```

### Notion Tools

Workspace management utilities for Notion using the internal API (token_v2 cookie auth), plus an Evernote markdown migration helper.

**CLI:**

```bash
notion clear-trash           # permanently delete all trashed pages
notion clear-teamspace       # interactively select and delete a teamspace
notion md-size-report        # analyze Evernote markdown exports by size
```

**Config:**

`tools/notion/config/config.json`

```json
{
  "notion_token_v2": "your_token_v2_from_browser_cookies",
  "md_size_report": {
    "notebook_dir": "/path/to/evernote/md/notebook",
    "resources_dir": "/path/to/evernote/md/_resources",
    "output_csv": "/path/to/output.csv"
  }
}
```

The `notion_token_v2` value can be obtained from browser cookies at notion.so. The `md_size_report` section is only needed for the `md-size-report` subcommand.

> **Warning:** `clear-trash` and `clear-teamspace` perform irreversible bulk deletions. They ask for confirmation before proceeding.

## Project Structure

```
tools/<tool_name>/
  config/    tool-specific configuration (gitignored)
  docs/      plans and documentation
  src/       source code (mapped as a Python package)
  tst/       tests
```

Each tool is self-contained. Adding a new tool means creating a directory under `tools/`, mapping its `src/` as a package in `pyproject.toml`, and adding a console script entry point.

## Running Tests

```bash
pytest
```
