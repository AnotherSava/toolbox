# v3 operations (things the MCP plugin can't do)

The Notion MCP plugin can query, update page properties, and add/drop columns — but it **cannot recolor or remove
existing select options, set a date format, or trash a database row**. Use the toolbox `notion_tools` v3 client
(internal `token_v2` API, config in `tools/notion/config/config.json`, gitignored). Run from the toolbox repo root
so `notion_tools` is importable. Always use a heredoc, never `python -c`.

Constants:
- collection id: `4a9aa87c-c7e3-4e36-baf3-a9a9fbcfece4`
- space id: `0b9a0494-0efd-81e7-8eab-00038a20f15d`

## Manage select options (add / recolor / remove) — e.g. the `Conflict` windows

Read the current options, build the full desired list (preserve `id` for options you keep, generate a `uuid` for
new ones), and `set` the whole `options` array. Cells keep their value as long as the option's `id`+`value` survive.
Notion colors: `default, gray, brown, orange, yellow, green, blue, purple, pink, red`.

```bash
python <<'EOF'
import uuid
from notion_tools.client import create_client
c = create_client()
COLL, SPACE = "4a9aa87c-c7e3-4e36-baf3-a9a9fbcfece4", "0b9a0494-0efd-81e7-8eab-00038a20f15d"
PROP = "Conflict"

# desired final state: {value: color}, in the order you want them listed
desired = {
    "Aug 1-2": "brown", "Aug 21-23": "blue", "Sep 4-9": "red", "Nov 12-15": "green",
    "Jan 14-17": "orange", "Feb 12-14": "purple", "May 28-31": "yellow", "Jun 25-27": "gray", "Jul 8-11": "pink",
}

r = c.post("syncRecordValues", {"requests":[{"pointer":{"table":"collection","id":COLL},"version":-1}]}).json()
schema = r["recordMap"]["collection"][COLL]["value"]["value"]["schema"]
pid = next(k for k,v in schema.items() if v.get("name")==PROP)
by_value = {o["value"]: o for o in schema[pid].get("options", [])}   # preserve ids of kept options

new_opts = []
for value, color in desired.items():
    o = by_value.get(value, {"id": str(uuid.uuid4()), "value": value})
    new_opts.append({**o, "value": value, "color": color})
# any value NOT in `desired` is dropped (removes that option)

c.post("saveTransactionsFanout", {"requestId": str(uuid.uuid4()),
    "transactions":[{"id":str(uuid.uuid4()),"spaceId":SPACE,"debug":{"userAction":"set_options"},
        "operations":[{"id":COLL,"table":"collection","path":["schema",pid,"options"],
                       "command":"set","args":new_opts}]}]}).raise_for_status()
print("options now:", [(o["value"],o["color"]) for o in new_opts])
EOF
```

**Removing an in-use option does NOT clear the cells** that reference it by value — first null those cells via
`notion-update-page` (`{"<Prop>": null}`), then drop the option with the snippet above.

## Set a date format

Notion honors custom `date_format` tokens. The table uses **`MMM d`** ("Jul 25" — abbreviated month, no year);
`MM/DD/YYYY`, `YYYY/MM/DD`, and `relative` also work.

```bash
python <<'EOF'
import uuid
from notion_tools.client import create_client
c = create_client()
COLL, SPACE = "4a9aa87c-c7e3-4e36-baf3-a9a9fbcfece4", "0b9a0494-0efd-81e7-8eab-00038a20f15d"
r = c.post("syncRecordValues", {"requests":[{"pointer":{"table":"collection","id":COLL},"version":-1}]}).json()
schema = r["recordMap"]["collection"][COLL]["value"]["value"]["schema"]
ops = [{"id":COLL,"table":"collection","path":["schema",k,"date_format"],"command":"set","args":"ll"}
       for k,v in schema.items() if v.get("type")=="date"]   # change "ll" to "MMM d" etc.
c.post("saveTransactionsFanout", {"requestId":str(uuid.uuid4()),
    "transactions":[{"id":str(uuid.uuid4()),"spaceId":SPACE,"debug":{"userAction":"date_fmt"},"operations":ops}]}).raise_for_status()
EOF
```

## Set a Notion reminder on a date

MCP can't attach reminders. Set the date property value to the mention form with a `reminder` object. Get the
date prop id from the schema (find by name). Reminder shape for an all-day date: `{"unit":"day"|"week","value":N,"time":"HH:MM"}`.

```bash
python <<'EOF'
import uuid
from notion_tools.client import create_client
c = create_client()
SPACE = "0b9a0494-0efd-81e7-8eab-00038a20f15d"
PAGE = "<page-id-with-dashes>"
PROP = "<date-prop-id>"   # e.g. "Early bird deadline" = eBvy
# date 2027-05-15 with a "1 week before" reminder at 09:00
val = [["‣", [["d", {"type":"date","start_date":"2027-05-15",
                               "reminder":{"unit":"week","value":1,"time":"09:00"}}]]]]
c.post("saveTransactionsFanout", {"requestId":str(uuid.uuid4()),
    "transactions":[{"id":str(uuid.uuid4()),"spaceId":SPACE,"debug":{"userAction":"set_reminder"},
        "operations":[{"id":PAGE,"table":"block","path":["properties",PROP],"command":"set","args":val}]}]}).raise_for_status()
EOF
```

## Trash a row (recoverable — goes to Notion Trash for 30 days)

Set the page block's `alive` to false. **Confirm with the user first** — this removes the row.

```bash
python <<'EOF'
import uuid
from notion_tools.client import create_client
c = create_client()
SPACE = "0b9a0494-0efd-81e7-8eab-00038a20f15d"
PAGE = "<page-id-with-dashes>"
c.post("saveTransactionsFanout", {"requestId":str(uuid.uuid4()),
    "transactions":[{"id":str(uuid.uuid4()),"spaceId":SPACE,"debug":{"userAction":"trash_row"},
        "operations":[{"id":PAGE,"table":"block","path":[],"command":"update","args":{"alive":False}}]}]}).raise_for_status()
EOF
```

## MCP operations (for reference)
- Read rows: `notion-query-data-sources` (SQL).
- Edit a row: `notion-update-page` `update_properties`. Dates use expanded keys `date:Start:start` / `date:End:start`; clear a value with `null`.
- Add a column / add-only new options: `notion-update-data-source` `ADD COLUMN "X" SELECT('a':red, ...)`. (Recoloring or dropping options via `ALTER COLUMN ... SET` is rejected — use the v3 snippet instead.)
- Repoint a view / change sort: `notion-update-view` (`CALENDAR BY "Start"`, `SORT BY "Start" ASC`).
