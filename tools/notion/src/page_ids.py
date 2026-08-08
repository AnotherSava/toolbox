"""Notion page-identifier helpers.

Its own module rather than a corner of a feature module, because every tool that
accepts a page URL on the command line needs this and nothing else from its
neighbours — importing it should not drag in an image pipeline.
"""

import urllib.parse


def parse_page_id(value: str) -> str:
    """Accept a Notion URL or raw 32-hex / dashed UUID, return dashed UUID."""
    candidate = value.strip()
    if "://" in candidate:
        path = urllib.parse.urlparse(candidate).path
        candidate = path.rsplit("/", 1)[-1].rsplit("-", 1)[-1]
    candidate = candidate.replace("-", "")
    if len(candidate) != 32:
        raise SystemExit(f"Could not parse page id from: {value}")
    return f"{candidate[0:8]}-{candidate[8:12]}-{candidate[12:16]}-{candidate[16:20]}-{candidate[20:32]}"
