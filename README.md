# toolbox

A collection of small tools for day-to-day life.

## Setup

### Linux / macOS / WSL

```bash
git clone <repo-url> && cd toolbox
python -m venv .venv
source .venv/bin/activate
pip install -e ".[browser,contacts,test]"
playwright install chromium
```

### Windows (PowerShell)

```powershell
git clone <repo-url>; cd toolbox
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[browser,contacts,test]"
playwright install chromium
```

### Windows (cmd)

```cmd
git clone <repo-url> & cd toolbox
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e ".[browser,contacts,test]"
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

Every subcommand that talks to Notion needs the credential, so run it through Doppler:

```bash
doppler run -- notion clear-trash           # permanently delete all trashed pages
doppler run -- notion optimize-images <url> # download, convert (WebP/AVIF), re-upload, and consolidate
                                            # images in an embedded sub-collection into its Picture property
```

**Credentials:** the `token_v2` cookie lives in Doppler (project `toolbox`, config `dev`, key `NOTION_TOKEN_V2`) — never on disk. `create_client()` reads it from the environment and has no config-file fallback, so a bare invocation fails with instructions rather than quietly using a stale local copy. `doppler.yaml` is committed, so a new machine needs only:

```bash
doppler login && doppler setup
```

To set or rotate the token, grab `token_v2` from your browser cookies and run this **in a normal terminal** (not through Claude, which would record the value):

```bash
doppler secrets set NOTION_TOKEN_V2="{{token-v2-from-browser-cookies}}" -p toolbox -c dev --silent
```

**Config:** none. The Doppler-held token is the only input.

> **Warning:** `clear-trash` performs an irreversible bulk deletion. It asks for confirmation before proceeding.

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

This one ships as the **`flightradar24` skill** rather than a registered CLI, because keeping the logbook current is a procedure rather than a single command — it also has to fetch a fresh export from a logged-in browser session and verify the export is purely additive before touching Notion. The scripts live in `.claude/skills/flightradar24/scripts/`; only the gitignored data cache stays under `tools/flightradar/data/`.

**Usage:** run `/flightradar24`, or just ask to update the FlightRadar24 Notion page.

**Scripts** (run from the repo root):

```bash
S=.claude/skills/flightradar24/scripts
doppler run -- python $S/main.py sync <page-url> --dry-run       # what would be added
doppler run -- python $S/main.py sync <page-url>                 # append missing flights
doppler run -- python $S/main.py create <page-url>               # first-time import
doppler run -- python $S/reconcile.py <page-url> --snapshot s.json  # before syncing
doppler run -- python $S/reconcile.py <page-url> --against  s.json  # after syncing
doppler run -- python $S/verify.py <page-url>                    # readable state dump
python $S/csv_hash.py                                            # local only — fingerprint the CSV
```

`sync` appends in place, which preserves view tweaks made in Notion's UI; `create` builds the database from scratch and is first-import only. Both default to `tools/flightradar/data/flights.csv` and accept `--csv`.

`reconcile.py` is the safety net, and exits non-zero on any problem. Snapshotted before a sync and compared after, it proves every pre-existing row survived untouched and that both views' column layout, colour rules and group entries only gained entries. It independently reconciles every live row against the value recomputed from the full CSV — which catches the opposite failure, a row that *should* have changed but didn't, since trips renumber when a flight is back-filled mid-history and a new flight can flip the previous one's layover flag.

**Config:** None of its own. Uses the same Doppler-held `NOTION_TOKEN_V2` as the Notion Tools, so every command above runs under `doppler run --`.

`csv_hash.py` fingerprints `tools/flightradar/data/flights.csv` (row count, djb2 hash, character count) so it can be proved identical to a live FR24 export — both before appending and, crucially, again afterwards. That local CSV is what the sync diff and `reconcile.py` both trust, so nothing else guarantees it stayed faithful.

See `.claude/skills/flightradar24/references/` for the CSV format quirks, the browser-session export recipe, and the Notion database's formatting rules.

### Google Contacts

Reads a Google account's contacts through the official [People API](https://developers.google.com/people). It tags each contact group as user-created or system-managed, so "which contacts have no label?" is an exact query rather than a guess at which names are system ones. It also reaches the auto-collected "Other contacts" bucket, which the Contacts web UI has no way to export.

**CLI:**

```bash
doppler run -- contacts labels      # contact count per label
doppler run -- contacts unlabeled   # contacts carrying no label
doppler run -- contacts show        # every contact with its labels
doppler run -- contacts other       # auto-collected "Other contacts"
doppler run -- contacts authorize   # one-time OAuth consent
```

Every report accepts `--json`. Read-only by design: the tool requests only `contacts.readonly` and `contacts.other.readonly`, so it cannot modify or delete a contact.

**Credentials:** two Doppler keys (project `toolbox`, config `dev`) — `GOOGLE_OAUTH_CLIENT_JSON` (the Desktop OAuth client downloaded from the Google Cloud Console) and `GOOGLE_CONTACTS_REFRESH_TOKEN` (minted by `contacts authorize`, which pipes it into Doppler over stdin rather than printing it). Creating the OAuth client is a one-time Console step — see `tools/contacts/docs/setup.md`.

**Config:** none. The Doppler-held credentials are the only input.

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
