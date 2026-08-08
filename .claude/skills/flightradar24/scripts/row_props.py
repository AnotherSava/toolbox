"""Readers for Notion v3 row property values.

Every script that reads rows back out of the collection needs the same handful
of accessors, and three private copies had already drifted into two different
names for the same function. They live here so a change to the v3 value shape —
which is undocumented and has moved before — lands in one place.

Value shapes (see `tools/notion/docs/learnings/notion-api-quirks.md`):
  text   ``[[<string>]]``, optionally ``[[<string>, [["b"]]]]`` when annotated
  date   ``[["‣", [["d", {"type": "date", "start_date": "YYYY-MM-DD"}]]]]``
"""


def plain(props: dict, key: str) -> str:
    """Read the plain string out of a property value, or "" when absent."""
    value = props.get(key)
    return value[0][0] if value else ""


def is_bold(props: dict, key: str) -> bool:
    """True when the property's first text run carries the bold annotation."""
    value = props.get(key)
    return bool(value and len(value[0]) > 1 and value[0][1] and value[0][1][0][0] == "b")


def iso_date(props: dict) -> str:
    """Read the ISO date out of the hidden ``date_sort`` property, or ""."""
    value = props.get("date_sort")
    try:
        return value[0][1][0][1]["start_date"]
    except (IndexError, KeyError, TypeError):
        return ""


def row_key(props: dict) -> tuple:
    """Dedup key identifying a flight row, read off a live row.

    Must stay in step with ``sync.flight_key``, which builds the same tuple from
    a parsed ``Flight``; the sync diff matches one against the other.
    """
    return (iso_date(props), plain(props, "flight_no"), plain(props, "from_code"),
            plain(props, "to_code"), plain(props, "dep"))


def label(props: dict) -> str:
    """Human-readable row label for reports."""
    return f"{iso_date(props)} {plain(props, 'title') or '?'} ({plain(props, 'flight_no') or 'no flight no'})"
