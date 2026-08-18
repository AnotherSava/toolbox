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
        parsed = urllib.parse.urlparse(candidate)
        # A side-peek URL (…/Parent-<id>?p=<row-id>&pm=s) addresses the peeked row
        # in ?p=, while the path still names the parent — take ?p= when present, or
        # the paste silently resolves to the wrong page. ?v= is a view, not a page.
        peeked = urllib.parse.parse_qs(parsed.query).get("p")
        candidate = peeked[0] if peeked else parsed.path.rsplit("/", 1)[-1].rsplit("-", 1)[-1]
    candidate = candidate.replace("-", "")
    if len(candidate) != 32:
        raise SystemExit(f"Could not parse page id from: {value}")
    return f"{candidate[0:8]}-{candidate[8:12]}-{candidate[12:16]}-{candidate[16:20]}-{candidate[20:32]}"
