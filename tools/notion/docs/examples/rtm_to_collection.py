"""EXAMPLE: import a Remember The Milk JSON export into a Notion collection.

Uses the internal v3 API via ``notion_tools.client`` — one embedded
``collection_view`` block on a host page, one ``page`` row per RTM task, note
bodies as child blocks, and the working views created up front.

Why v3 rather than the public API: rows go in 50 to a ``saveTransactionsFanout``
call instead of one HTTP request each (1,156 rows in ~25 calls, not ~1,200 at
3/s), and the public API cannot create views at all.

    python tools/notion/docs/examples/rtm_to_collection.py <export.json> <host-page-url>
    #   then, in Notion: database ... -> More settings -> Sub-items -> Turn on
    python tools/notion/docs/examples/rtm_to_collection.py <export.json> --parents

Progress lands in ``rtm_import_state.json`` next to the export, keyed by RTM ID,
so an interrupted run resumes instead of duplicating rows.

v3 property value shapes used here (see notion-api-quirks.md):
  text / url / select : ``[[<string>]]``
  multi_select        : ``[["a,b,c"]]``   (so option names must not contain commas)
  checkbox            : ``[["Yes"]]`` / omitted
  date                : ``[["‣", [["d", {"type": "date", "start_date": "YYYY-MM-DD"}]]]]``
  relation            : ``[["‣", [["p", "<row-uuid>"]]]]``
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

from notion_tools.client import NotionClient, create_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rtm_transform import load_records, summarize          # noqa: E402

STATE_NAME = "rtm_import_state.json"
ROW_BATCH = 50          # rows per transaction
BLOCK_BATCH = 150       # note-block ops per transaction
CHUNK = 1900            # characters per rich-text run
TIME_ZONE = "America/Vancouver"

# (schema key, display name, v3 type)
SCHEMA: list[tuple[str, str, str]] = [
    ("title", "Task", "title"),
    ("status", "Status", "select"),
    ("priority", "Priority", "select"),
    ("topic", "Topic", "multi_select"),
    ("date", "Date", "date"),
    ("cadence", "Cadence", "select"),
    ("link", "Link", "url"),
    ("triage", "Triage", "select"),
    ("ready", "Ready", "checkbox"),
    ("start", "Start", "date"),
    ("created", "Created", "date"),
    ("completed", "Completed", "date"),
    ("modified", "Modified", "date"),
    ("rtm_id", "RTM ID", "text"),
    ("rtm_series", "RTM series", "text"),
]

SELECT_OPTIONS: dict[str, list[tuple[str, str]]] = {
    "status": [("To do", "default"), ("Done", "green")],
    "priority": [("P1", "red"), ("P2", "orange"), ("P3", "yellow")],
    "cadence": [("Daily", "default"), ("Weekly", "default"), ("Monthly", "default"),
                ("Quarterly", "default"), ("World", "gray"), ("Never", "gray")],
    "triage": [("Archived", "gray"), ("Extract later", "blue")],
}

# Columns hidden in every view; the rest are shown unless a view says otherwise.
ALWAYS_HIDDEN = {"rtm_id", "rtm_series", "modified", "start", "created"}
WIDTHS = {"title": 380, "topic": 180, "link": 220, "date": 120,
          "status": 100, "priority": 80, "cadence": 100, "triage": 110}


# --------------------------------------------------------------------------- #
# value builders
# --------------------------------------------------------------------------- #

def _text(value: str) -> list:
    return [[value]]


def _date_value(day: str, time: str | None = None) -> list:
    """v3 date property value; includes a time component only when given one."""
    if time:
        payload = {"type": "datetime", "start_date": day,
                   "start_time": time, "time_zone": TIME_ZONE}
    else:
        payload = {"type": "date", "start_date": day}
    return [["‣", [["d", payload]]]]


def _relation(page_ids: list[str]) -> list:
    """v3 relation property value: page mentions separated by commas."""
    out: list = []
    for i, pid in enumerate(page_ids):
        if i:
            out.append([","])
        out.append(["‣", [["p", pid]]])
    return out


def _row_properties(rec: dict) -> dict[str, list]:
    """Serialize one record into a v3 properties map, omitting empties."""
    raw: dict[str, list | None] = {
        "title": _text(rec["task"][:CHUNK]) if rec["task"] else _text("(untitled)"),
        "status": _text(rec["status"]),
        "priority": _text(rec["priority"]) if rec["priority"] else None,
        "topic": _text(",".join(rec["topic"])) if rec["topic"] else None,
        "date": _date_value(rec["date"], rec["date_time"]) if rec["date"] else None,
        "cadence": _text(rec["cadence"]) if rec["cadence"] else None,
        "link": _text(rec["link"]) if rec["link"] else None,
        "triage": _text(rec["triage"]) if rec["triage"] else None,
        "ready": _text("Yes") if rec["ready"] else None,
        "start": _date_value(rec["start"], rec["start_time"]) if rec["start"] else None,
        "created": _date_value(rec["created"]) if rec["created"] else None,
        "completed": _date_value(rec["completed"]) if rec["completed"] else None,
        "modified": _date_value(rec["modified"]) if rec["modified"] else None,
        "rtm_id": _text(rec["rtm_id"]),
        "rtm_series": _text(rec["rtm_series"]),
    }
    return {k: v for k, v in raw.items() if v is not None}


def _note_blocks(rec: dict) -> list[tuple[str, list]]:
    """Flatten a record's notes into ``(block_type, title_property)`` pairs."""
    out: list[tuple[str, list]] = []
    for note in rec["notes"]:
        out.append(("sub_sub_header", _text((note["title"] or note["date"])[:CHUNK])))
        if note["title"]:
            out.append(("text", [[note["date"], [["i"]]]]))
        for para in note["content"].split("\n"):
            para = para.rstrip()
            if not para:
                continue
            for i in range(0, len(para), CHUNK):
                out.append(("text", _text(para[i:i + CHUNK])))
    return out


# --------------------------------------------------------------------------- #
# schema, views
# --------------------------------------------------------------------------- #

def _build_schema(records: list[dict]) -> dict[str, dict]:
    topics = sorted({t for r in records for t in r["topic"]})
    schema = {key: {"name": name, "type": ptype} for key, name, ptype in SCHEMA}
    for key, options in SELECT_OPTIONS.items():
        schema[key]["options"] = [
            {"id": str(uuid.uuid4()), "value": value, "color": color}
            for value, color in options]
    schema["topic"]["options"] = [
        {"id": str(uuid.uuid4()), "value": t, "color": "default"} for t in topics]
    return schema


def _table_properties(hidden: set[str]) -> list[dict]:
    props = []
    for key, _name, _ptype in SCHEMA:
        props.append({"property": key, "visible": key not in hidden,
                      "width": WIDTHS.get(key, 140)})
    return props


def _f(prop: str, operator: str, value=None, value_type: str = "exact") -> dict:
    """One v3 filter clause."""
    clause: dict = {"operator": operator}
    if value is not None:
        clause["value"] = {"type": value_type, "value": value}
    return {"property": prop, "filter": clause}


# name, extra hidden columns, filter clauses, sorts, group_by
VIEWS: list[tuple[str, set, list, list, str | None]] = [
    ("Remaining", {"completed", "triage"},
     [_f("status", "enum_is", "To do"), _f("triage", "is_empty")],
     [("priority", "ascending"), ("date", "ascending")], None),

    ("Untriaged", {"completed", "triage", "cadence", "date"},
     [_f("triage", "is_empty"), _f("date", "is_empty"), _f("cadence", "is_empty")],
     [("created", "descending")], None),

    ("Browse by cadence", {"completed", "triage"},
     [_f("cadence", "is_not_empty"), _f("triage", "is_empty")],
     [("modified", "ascending")], "cadence"),

    ("Documents & renewals", {"completed", "triage", "cadence"},
     [_f("topic", "enum_contains", "document-expiry"), _f("status", "enum_is", "To do")],
     [("date", "ascending")], None),

    ("Conventions", {"completed", "triage", "cadence"},
     [_f("topic", "enum_contains", "conventions"), _f("status", "enum_is", "To do")],
     [("date", "ascending")], None),

    ("Buy", {"completed", "triage"},
     [_f("topic", "enum_contains", "order"), _f("status", "enum_is", "To do")],
     [("priority", "ascending")], None),

    ("Important", {"completed", "triage"},
     [_f("priority", "is_not_empty"), _f("triage", "is_empty")],
     [("priority", "ascending"), ("date", "ascending")], None),

    ("People", {"completed", "triage"},
     [_f("topic", "enum_contains", "people")],
     [("modified", "descending")], None),

    ("Archive", {"cadence", "ready", "triage", "link"},
     [_f("triage", "enum_is", "Archived")],
     [("completed", "descending")], None),

    ("Everything", set(), [], [("created", "descending")], None),
]


def _collection_groups(key: str, records: list[dict]) -> list[dict]:
    """One entry per distinct value, plus the catch-all for the unset bucket."""
    order = [v for v, _c in SELECT_OPTIONS[key]]
    groups = [{"property": key, "value": {"type": "select", "value": v}, "hidden": False}
              for v in order]
    groups.append({"property": key, "value": {"type": "select"}, "hidden": False})
    return groups


def _view_args(view_id: str, cv_block_id: str, collection_id: str, space_id: str,
               name: str, hidden: set, filters: list, sorts: list,
               group_by: str | None, records: list[dict]) -> dict:
    fmt: dict = {
        "table_wrap": True,
        "collection_pointer": {"id": collection_id, "table": "collection", "spaceId": space_id},
        "table_properties": _table_properties(ALWAYS_HIDDEN | hidden),
    }
    query2: dict = {"sort": [{"property": p, "direction": d} for p, d in sorts]}
    if filters:
        query2["filter"] = {"operator": "and", "filters": filters}
    if group_by:
        query2["group_by"] = group_by
        fmt["collection_groups"] = _collection_groups(group_by, records)
    return {"id": view_id, "type": "table", "name": name, "format": fmt, "query2": query2,
            "parent_id": cv_block_id, "parent_table": "block",
            "space_id": space_id, "alive": True}


# --------------------------------------------------------------------------- #
# transactions
# --------------------------------------------------------------------------- #

def _send(client: NotionClient, space_id: str, label: str, ops: list[dict]) -> None:
    r = client.post("saveTransactionsFanout", {
        "requestId": str(uuid.uuid4()),
        "transactions": [{"id": str(uuid.uuid4()), "spaceId": space_id,
                          "debug": {"userAction": label}, "operations": ops}],
    })
    r.raise_for_status()


def load_host_page(client: NotionClient, page_id: str) -> dict:
    resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "block", "id": page_id}, "version": -1}]}).json()
    page = resp.get("recordMap", {}).get("block", {}).get(page_id, {}).get("value", {}).get("value")
    if not page:
        raise SystemExit(f"Page {page_id} not found or no access.")
    return page


def create_collection(client: NotionClient, host_page_id: str, space_id: str,
                      records: list[dict], title: str) -> tuple[str, str]:
    """Create the collection_view block, the collection, and every view."""
    cv_block_id = str(uuid.uuid4())
    collection_id = str(uuid.uuid4())
    view_ids = [str(uuid.uuid4()) for _ in VIEWS]

    ops = [
        {"id": cv_block_id, "table": "block", "path": [], "command": "set", "args": {
            "id": cv_block_id, "type": "collection_view",
            "view_ids": view_ids, "collection_id": collection_id,
            "format": {
                "collection_pointer": {"id": collection_id, "table": "collection", "spaceId": space_id},
                "collection_pointers": [{"id": collection_id, "table": "collection", "spaceId": space_id}],
            },
            "parent_id": host_page_id, "parent_table": "block",
            "space_id": space_id, "alive": True}},
        {"id": collection_id, "table": "collection", "path": [], "command": "set", "args": {
            "id": collection_id, "name": [[title]], "schema": _build_schema(records),
            "parent_id": cv_block_id, "parent_table": "block",
            "space_id": space_id, "alive": True, "migrated": True}},
        {"id": host_page_id, "table": "block", "path": ["content"],
         "command": "listAfter", "args": {"id": cv_block_id}},
    ]
    _send(client, space_id, "rtm_create_collection", ops)
    print(f"  collection {collection_id}")

    # One transaction per view, so a rejected view cannot take the others down.
    for view_id, (name, hidden, filters, sorts, group_by) in zip(view_ids, VIEWS):
        args = _view_args(view_id, cv_block_id, collection_id, space_id,
                          name, hidden, filters, sorts, group_by, records)
        try:
            _send(client, space_id, f"rtm_view_{name}",
                  [{"id": view_id, "table": "collection_view", "path": [],
                    "command": "set", "args": args}])
            print(f"  view: {name}")
        except Exception as exc:                                  # noqa: BLE001
            print(f"  ! view {name} failed: {exc}")
    return cv_block_id, collection_id


def insert_rows(client: NotionClient, collection_id: str, space_id: str,
                records: list[dict], state: dict) -> None:
    """Create one row per record, then its note blocks."""
    todo = [r for r in records if r["rtm_id"] not in state["rows"]]
    print(f"rows: {len(todo)} to create ({len(state['rows'])} already done)")
    for start in range(0, len(todo), ROW_BATCH):
        chunk = todo[start:start + ROW_BATCH]
        ops, made = [], {}
        for rec in chunk:
            rid = str(uuid.uuid4())
            made[rec["rtm_id"]] = rid
            ops.append({"id": rid, "table": "block", "path": [], "command": "set", "args": {
                "id": rid, "type": "page", "properties": _row_properties(rec),
                "parent_id": collection_id, "parent_table": "collection",
                "space_id": space_id, "alive": True}})
        _send(client, space_id, "rtm_insert_rows", ops)
        state["rows"].update(made)
        save_state(state)
        print(f"  {start + len(chunk)}/{len(todo)}")

    # Note bodies. Per notion-api-quirks.md, a child block needs BOTH a
    # parent_id and a listAfter into the parent's own content array.
    pending = [r for r in records if r["notes"] and r["rtm_id"] not in state["noted"]]
    total = sum(len(_note_blocks(r)) for r in pending)
    print(f"notes: {total} blocks across {len(pending)} rows")
    ops, touched, done = [], [], 0
    for rec in pending:
        row_id = state["rows"][rec["rtm_id"]]
        for block_type, title_prop in _note_blocks(rec):
            bid = str(uuid.uuid4())
            ops.append({"id": bid, "table": "block", "path": [], "command": "set", "args": {
                "id": bid, "type": block_type, "properties": {"title": title_prop},
                "parent_id": row_id, "parent_table": "block",
                "space_id": space_id, "alive": True}})
            ops.append({"id": row_id, "table": "block", "path": ["content"],
                        "command": "listAfter", "args": {"id": bid}})
        touched.append(rec["rtm_id"])
        if len(ops) >= BLOCK_BATCH:
            _send(client, space_id, "rtm_insert_notes", ops)
            done += len(ops) // 2
            state["noted"].extend(touched)
            save_state(state)
            print(f"  {done}/{total}")
            ops, touched = [], []
    if ops:
        _send(client, space_id, "rtm_insert_notes", ops)
        state["noted"].extend(touched)
        save_state(state)
        print(f"  {total}/{total}")


def link_parents(client: NotionClient, collection_id: str, space_id: str,
                 records: list[dict], state: dict) -> None:
    """Phase 3: write the sub-item relation, once it exists on the collection."""
    resp = client.post("syncRecordValues", {
        "requests": [{"pointer": {"table": "collection", "id": collection_id}, "version": -1}]}).json()
    schema = (resp.get("recordMap", {}).get("collection", {})
              .get(collection_id, {}).get("value", {}).get("value", {}).get("schema", {}))
    key = None
    for k, prop in schema.items():
        if prop.get("type") == "relation" and prop.get("collection_id") == collection_id:
            key = k
            if "parent" in prop.get("name", "").lower():
                break
    if not key:
        raise SystemExit(
            "No self-relation on this collection yet.\n"
            "  In Notion: database ... -> More settings -> Sub-items -> Turn on\n"
            "  then re-run with --parents")
    print(f"linking via schema key {key!r} ({schema[key].get('name')})")

    kids = [r for r in records if r["parent_id"] and r["rtm_id"] not in state["linked"]]
    for start in range(0, len(kids), ROW_BATCH):
        chunk, ops, ids = kids[start:start + ROW_BATCH], [], []
        for rec in chunk:
            child = state["rows"].get(rec["rtm_id"])
            parent = state["rows"].get(rec["parent_id"])
            if not child or not parent:
                print(f"  ! {rec['rtm_id']}: row missing, skipped")
                continue
            ops.append({"id": child, "table": "block", "path": ["properties", key],
                        "command": "set", "args": _relation([parent])})
            ids.append(rec["rtm_id"])
        if ops:
            _send(client, space_id, "rtm_link_parents", ops)
            state["linked"].extend(ids)
            save_state(state)
            print(f"  {start + len(chunk)}/{len(kids)}")


# --------------------------------------------------------------------------- #

_state_path = Path(STATE_NAME)


def load_state() -> dict:
    if _state_path.exists():
        return json.load(open(_state_path, encoding="utf-8"))
    return {"collection_id": None, "cv_block_id": None, "space_id": None,
            "rows": {}, "noted": [], "linked": []}


def save_state(state: dict) -> None:
    json.dump(state, open(_state_path, "w", encoding="utf-8"), indent=1)


def parse_page_id(value: str) -> str:
    """Accept a Notion URL or a bare id; return the dashed 36-char form."""
    tail = value.rstrip("/").split("/")[-1].split("?")[0]
    raw = tail.split("-")[-1] if "-" in tail and len(tail.split("-")[-1]) == 32 else tail
    raw = raw.replace("-", "")
    if len(raw) != 32:
        raise SystemExit(f"Cannot read a page id out of {value!r}")
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Import a Remember The Milk export into Notion.")
    ap.add_argument("export", help="RTM JSON export")
    ap.add_argument("page", nargs="?", help="host page URL or id (omit with --parents)")
    ap.add_argument("--title", default="RTM", help="collection name")
    ap.add_argument("--parents", action="store_true",
                    help="phase 3: link sub-items after enabling them in the UI")
    ap.add_argument("--dry-run", action="store_true", help="transform and report, touch nothing")
    args = ap.parse_args()

    records, warnings = load_records(args.export)
    summarize(records, warnings)
    if args.dry_run:
        return 0

    global _state_path
    _state_path = Path(args.export).resolve().parent / STATE_NAME
    state = load_state()
    client = create_client()

    if args.parents:
        if not state.get("collection_id"):
            raise SystemExit("No collection yet — run the first phase before --parents.")
        link_parents(client, state["collection_id"], state["space_id"], records, state)
        print(f"\nlinked {len(state['linked'])} of {sum(1 for r in records if r['parent_id'])}")
        return 0

    if not state["collection_id"]:
        if not args.page:
            raise SystemExit("Give a host page URL or id.")
        host = parse_page_id(args.page)
        page = load_host_page(client, host)
        state["space_id"] = page["space_id"]
        print(f"\nhost page {(page.get('properties', {}).get('title') or [['(untitled)']])[0][0]!r}")
        cv, coll = create_collection(client, host, state["space_id"], records, args.title)
        state["cv_block_id"], state["collection_id"] = cv, coll
        save_state(state)
    else:
        print(f"\nresuming into collection {state['collection_id']}")

    insert_rows(client, state["collection_id"], state["space_id"], records, state)
    print("\nNext, in Notion: database ... -> More settings -> Sub-items -> Turn on")
    print(f"then: python {Path(__file__).name} {args.export} --parents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
