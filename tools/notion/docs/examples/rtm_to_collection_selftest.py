"""Offline self-test for rtm_to_collection.py.

Stubs notion_tools.client with a fake that records and validates every v3
operation the importer emits, then asserts the resulting recordMap is what the
design calls for. It cannot prove Notion accepts these field names — only that
the op stream is internally consistent and complete.
"""
import sys
import types
from pathlib import Path

EXPORT = sys.argv[1]

# ---- stub notion_tools.client -------------------------------------------- #
STORE = {"collection": {}, "block": {}, "collection_view": {}, "content": {}}
CALLS = {"saveTransactionsFanout": 0, "syncRecordValues": 0}
SUBITEMS_ON = "--subitems" in sys.argv


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class FakeClient:
    def post(self, endpoint, data):
        CALLS[endpoint] = CALLS.get(endpoint, 0) + 1
        if endpoint == "syncRecordValues":
            req = data["requests"][0]["pointer"]
            if req["table"] == "block" and req["id"] not in STORE["block"]:
                # the host page
                return FakeResponse({"recordMap": {"block": {req["id"]: {"value": {"value": {
                    "id": req["id"], "space_id": "space-1",
                    "properties": {"title": [["Host page"]]}}}}}}})
            table, rid = req["table"], req["id"]
            value = dict(STORE[table].get(rid, {}))
            if table == "collection" and SUBITEMS_ON:
                value.setdefault("schema", {})["par"] = {
                    "name": "Parent item", "type": "relation",
                    "collection_id": rid}
            return FakeResponse({"recordMap": {table: {rid: {"value": {"value": value}}}}})

        assert endpoint == "saveTransactionsFanout"
        for tx in data["transactions"]:
            assert tx["spaceId"], "missing spaceId"
            for op in tx["operations"]:
                _apply(op)
        return FakeResponse({})


def _apply(op):
    table, oid = op["table"], op["id"]
    if op["command"] == "set" and op["path"] == []:
        args = op["args"]
        assert args.get("space_id"), f"{oid}: no space_id"
        assert args.get("alive") is True, f"{oid}: not alive"
        STORE[table][oid] = args
        if table == "block" and args.get("type") == "page":
            _check_row(args)
    elif op["command"] == "set" and op["path"][:1] == ["properties"]:
        key = op["path"][1]
        STORE[table][oid].setdefault("properties", {})[key] = op["args"]
    elif op["command"] == "listAfter":
        STORE["content"].setdefault(oid, []).append(op["args"]["id"])
    else:
        raise AssertionError(f"unhandled op {op['command']} {op['path']}")


def _check_row(args):
    """Validate a row's property map against the collection schema."""
    coll = STORE["collection"].get(args["parent_id"])
    assert coll, "row created before its collection"
    schema = coll["schema"]
    for key, value in args["properties"].items():
        assert key in schema, f"unknown schema key {key}"
        ptype = schema[key]["type"]
        if ptype == "select":
            allowed = {o["value"] for o in schema[key]["options"]}
            assert value[0][0] in allowed, f"{key}: undeclared option {value[0][0]!r}"
        elif ptype == "multi_select":
            allowed = {o["value"] for o in schema[key]["options"]}
            for part in value[0][0].split(","):
                assert part in allowed, f"topic: undeclared option {part!r}"
        elif ptype == "date":
            assert value[0][0] == "‣" and value[0][1][0][0] == "d", f"{key}: bad date shape"
            payload = value[0][1][0][1]
            assert payload["type"] in ("date", "datetime")
            assert len(payload["start_date"]) == 10
        elif ptype in ("text", "url", "title", "checkbox"):
            assert isinstance(value[0][0], str)


fake = types.ModuleType("notion_tools")
client_mod = types.ModuleType("notion_tools.client")
client_mod.NotionClient = FakeClient
client_mod.create_client = lambda: FakeClient()
fake.client = client_mod
sys.modules["notion_tools"] = fake
sys.modules["notion_tools.client"] = client_mod

# ---- run ------------------------------------------------------------------ #
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rtm_to_collection as imp                                    # noqa: E402
from rtm_transform import load_records                             # noqa: E402

state_file = Path("rtm_import_state.json")
state_file.unlink(missing_ok=True)
imp._state_path = state_file

records, warnings = load_records(EXPORT)
client = FakeClient()
cv, coll = imp.create_collection(client, "host-page-id", "space-1", records, "RTM")
state = imp.load_state()
state.update({"cv_block_id": cv, "collection_id": coll, "space_id": "space-1"})

imp.insert_rows(client, coll, "space-1", records[:300], state)     # partial run
state = imp.load_state()                                           # "crash", resume
imp.insert_rows(client, coll, "space-1", records, state)

rows = [b for b in STORE["block"].values() if b.get("type") == "page"]
blocks = [b for b in STORE["block"].values() if b.get("type") in ("text", "sub_sub_header")]
expected_blocks = sum(len(imp._note_blocks(r)) for r in records)

print()
print(f"transactions            {CALLS['saveTransactionsFanout']}")
print(f"rows created            {len(rows)}   (expected {len(records)})")
print(f"note blocks created     {len(blocks)}   (expected {expected_blocks})")
print(f"views created           {len(STORE['collection_view'])}   (expected {len(imp.VIEWS)})")
assert len(rows) == len(records), "row count mismatch"
assert len(blocks) == expected_blocks, "note block count mismatch"
assert len(STORE["collection_view"]) == len(imp.VIEWS)

# every note block must be both parented and listAfter-ed into its row
listed = {b for kids in STORE["content"].values() for b in kids}
for bid, blk in STORE["block"].items():
    if blk.get("type") in ("text", "sub_sub_header"):
        assert bid in listed, f"block {bid} never listAfter-ed"
        assert STORE["block"][blk["parent_id"]]["type"] == "page", "note not parented to a row"
print("every note block is parented AND listed")

# the collection_view block must be listed into the host page
assert cv in STORE["content"].get("host-page-id", []), "collection_view not listed onto host page"
print("collection_view listed onto host page")

# no duplicate rows after the resume
ids = [r["properties"]["rtm_id"][0][0] for r in rows]
assert len(ids) == len(set(ids)), "duplicate rows after resume"
print("no duplicates after resume")

# phase 3
try:
    imp.link_parents(client, coll, "space-1", records, state)
    raise AssertionError("should have refused without sub-items")
except SystemExit as exc:
    print(f"guard without sub-items: {str(exc).splitlines()[0]}")

globals()["SUBITEMS_ON"] = True
imp.link_parents(client, coll, "space-1", records, state)
expected_links = sum(1 for r in records if r["parent_id"])
linked = [b for b in STORE["block"].values()
          if b.get("type") == "page" and "par" in (b.get("properties") or {})]
print(f"parent links written    {len(linked)}   (expected {expected_links})")
assert len(linked) == expected_links
for b in linked:
    val = b["properties"]["par"]
    assert val[0][0] == "‣" and val[0][1][0][0] == "p", "bad relation shape"
print("relation values well-formed")

view_names = [v["name"] for v in STORE["collection_view"].values()]
print(f"views: {', '.join(view_names)}")

# Clean up the scratch state file on success; on failure it's left for inspection.
state_file.unlink(missing_ok=True)
print("\nALL CHECKS PASSED")
