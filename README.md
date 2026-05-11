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
notion optimize-images <url> # download, convert (WebP/AVIF), re-upload, and consolidate images
                             # in an embedded sub-collection into its Picture property
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

### Image Optimizer

A standalone CLI for shrinking images before uploading them anywhere — Notion, GitHub, a blog, etc. Resizes to a max width and re-encodes as WebP (default) or AVIF.

**CLI:**

```bash
image-opt photo.jpg                          # outputs ./photo.webp
image-opt ./photos --out ./photos-small      # converts every image in a directory
image-opt ./in --format avif --quality 50    # smaller files (note: Notion does not preview AVIF)
image-opt ./in --max-width 1024 --quality 60 # defaults
```

Accepts files or directories; recognizes JPG, PNG, HEIC/HEIF, BMP, TIFF, WebP, AVIF as inputs. Output filename mirrors the input stem (`photo.heic` → `photo.webp`). No config file; all options are CLI flags.

### Flightradar Importer

Imports your personal Flightradar24 logbook into a Notion database. Reads a FR24 CSV export, enriches each flight with airport/city/country metadata from [OurAirports](https://ourairports.com/), groups flights into trips (one trip = chronologically-contiguous flights starting and ending at a home city), and creates a Notion database with two pre-configured views (Full and Compact), trip-based row banding via Notion's conditional-color rules, and chronological sort.

**CLI:**

```bash
flightradar <notion-page-url>                 # imports tools/flightradar/data/flights.csv
flightradar <notion-page-url> --csv path.csv  # specify a CSV explicitly
```

Workflow:

1. Export your logbook at `my.flightradar24.com/settings/export` and save the CSV
2. Place it at `tools/flightradar/data/flights.csv` (default path; gitignored)
3. Run `flightradar <parent-page-url>` — creates a "Flights" database under that page

The importer uses the same Notion credentials as the Notion Tools (token_v2 cookie auth in `tools/notion/config/config.json`).

**Config:** None of its own. Reuses `tools/notion/config/config.json` for Notion auth.

See `tools/flightradar/docs/learnings/fr24-csv-quirks.md` for the FR24 CSV format details and `tools/flightradar/API_RESEARCH.md` for why CSV is the only sanctioned interface.

### AutoHotkey Scripts

A collection of [AutoHotkey v2](https://www.autohotkey.com/) scripts for Windows automation. Unlike the other tools, these are standalone `.ahk` files — no Python packaging, no CLI entry point. Just run them with the AutoHotkey runtime.

**Scripts** (in `tools/ahk/scripts/`):

- `base.ahk` — F1 hides a window from the taskbar; F2 restores it. Edit `targetTitle` in the script to match your window.
- `hide.ahk` — Auto-hides specified windows from the taskbar when they open. Edit the `windows` array to add/remove targets. See the top comment for how to auto-run on startup.

**Usage:**

```powershell
# Run a script manually
"C:\Program Files\AutoHotkey\v2\AutoHotkey.exe" tools\ahk\scripts\hide.ahk
```

Or double-click the `.ahk` file in Explorer if AutoHotkey v2 is installed as the default handler.

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
