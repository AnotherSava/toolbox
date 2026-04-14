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

### Overlay Grid

Generates a coordinate grid image (PNG) for use as a click-through screen overlay or as a regular desktop wallpaper. Useful as a layout reference when positioning desktop widgets or UI mockups.

**CLI:**

```bash
overlay-grid                                        # uses output_path from config
overlay-grid out.png                                # override output path
overlay-grid --width 1920 --height 1080 out.png
overlay-grid --variant dark --background ff00ff     # dark lines, magenta chroma-key background
```

**Config:**

`tools/overlay_grid/config/config.json`

Dimensions, step sizes (minor/major/super grid intervals), colors, font, default output path, and named color variants. Unlike the other tools, this config is committed with sensible 4K defaults and can be edited in place. Relative `output_path` values resolve against the tool directory, so `overlay-grid` always writes under `tools/overlay_grid/output/` by default — regardless of where you run it from.

**Windows screen overlay** (`tools/overlay_grid/scripts/overlay.ahk`):

An AutoHotkey v2 helper that shows the grid as a click-through overlay on top of the desktop — wallpaper state is never touched, so Windows Spotlight / Slideshow / Picture modes keep running underneath.

- `Ctrl+Shift+9` — cycle overlay: hidden → dark variant → light variant → hidden

Two color variants cover different wallpaper brightness:

- **dark** — dark lines, designed to be visible on light/bright wallpapers
- **light** — light lines, designed to be visible on dark wallpapers

On each first encounter of a variant, the script enumerates monitors and runs `overlay-grid --variant <name> --background ff00ff` for each resolution, producing `output/overlay_grid_<variant>_<W>x<H>.png`. It displays one always-on-top click-through window per monitor with the magenta background chroma-keyed out so only the grid lines and labels show. Subsequent cycles are instant.

Color palettes live in `config/config.json` under `variants.<name>.colors` — edit them to taste. An empty variant (`"colors": {}`) inherits from the top-level `colors` section.

Run the script with the AutoHotkey v2 runtime, or add a startup shortcut (see `~/.claude/learnings/autohotkey.md`).

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
