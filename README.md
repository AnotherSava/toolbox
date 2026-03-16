# toolbox

A collection of small tools for day-to-day life.

## Tools

| Command | Description |
|---------|-------------|
| `fb-strikethrough` | Edit a Facebook group post to replace its text with Unicode strikethrough |

## Setup

```bash
git clone <repo-url> && cd toolbox
python -m venv .venv
source .venv/bin/activate
pip install -e ".[browser,test]"
playwright install chromium
```

## Usage

```bash
fb-strikethrough <facebook-group-post-url>
```

On first run, a browser window opens for you to log into Facebook. Subsequent runs reuse the saved session.
