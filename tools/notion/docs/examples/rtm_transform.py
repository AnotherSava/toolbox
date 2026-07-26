"""Transform a Remember The Milk JSON export into flat, import-ready records.

Pure data munging — no Notion. Import ``load_records`` from the importer, or run
standalone to eyeball the counts:

    python tools/notion/docs/examples/rtm_transform.py <export.json>

Tag splitting is the substantive decision here. RTM's single tag namespace is
doing three unrelated jobs in this export, so it gets split three ways:

* ``reminder-*``  -> ``cadence``  (single-valued: a review-frequency hint)
* ``new_and_ready`` -> ``ready``  (a boolean)
* everything else -> ``topic``    (real topics, multi-valued)
"""

import collections
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Vancouver")

CADENCE = {
    "reminder-daily": "Daily", "reminder-weekly": "Weekly",
    "reminder-monthly": "Monthly", "reminder-quarterly": "Quarterly",
    "reminder-world": "World", "reminder-never": "Never",
}
# When a task carries more than one cadence tag, keep the most frequent one.
CADENCE_RANK = ["Daily", "Weekly", "Monthly", "Quarterly", "World", "Never"]
READY_TAG = "new_and_ready"
TAG_MERGE = {"internet.actual": "internet"}
TAG_DROP = {"canada", "snowboard"}          # declared in the export, never used
PRIORITY = {"P1": "P1", "P2": "P2", "P3": "P3", "PN": None}


def _dt(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).astimezone(TZ) if ms else None


def _date(ms):
    d = _dt(ms)
    return d.strftime("%Y-%m-%d") if d else None


def _time(ms):
    d = _dt(ms)
    return d.strftime("%H:%M") if d else None


def load_records(path: str) -> tuple[list[dict], list[str]]:
    """Parse the export. Returns ``(records, warnings)``."""
    raw = json.load(open(path, encoding="utf-8"))
    tasks = raw["tasks"]
    warnings: list[str] = []

    notes_by_series = collections.defaultdict(list)
    for n in raw["notes"]:
        notes_by_series[n["series_id"]].append(n)
    for v in notes_by_series.values():
        v.sort(key=lambda n: n["date_created"])

    # A note belongs to a *series*, not a task. Four series have several
    # occurrence rows; hang their notes on the newest one.
    newest = {}
    for t in tasks:
        s = t["series_id"]
        if s not in newest or t["date_created"] > newest[s]["date_created"]:
            newest[s] = t

    records = []
    for t in tasks:
        tags = list(t.get("tags") or [])
        cad = [CADENCE[g] for g in tags if g in CADENCE]
        if len(cad) > 1:
            warnings.append(
                f"multiple cadence tags on {t['id']} {t['name']!r}: {cad}"
                f" -> kept {min(cad, key=CADENCE_RANK.index)}")

        topics = []
        for g in tags:
            if g in CADENCE or g == READY_TAG or g in TAG_DROP:
                continue
            g = TAG_MERGE.get(g, g)
            if g not in topics:
                topics.append(g)
        for g in topics:
            if "," in g:
                warnings.append(f"topic {g!r} contains a comma; v3 multi_select cannot store it")

        notes = []
        if newest.get(t["series_id"], {}).get("id") == t["id"]:
            notes = [{"title": n.get("title") or "", "date": _date(n["date_created"]),
                      "content": n["content"]} for n in notes_by_series.get(t["series_id"], [])]

        done = bool(t.get("date_completed"))
        records.append({
            "rtm_id": t["id"],
            "rtm_series": t["series_id"],
            "parent_id": t.get("parent_id"),
            "task": t["name"],
            "link": t.get("url") or None,
            "date": _date(t.get("date_due")),
            "date_time": _time(t["date_due"]) if t.get("date_due") and t.get("date_due_has_time") else None,
            "start": _date(t.get("date_start")),
            "start_time": _time(t["date_start"]) if t.get("date_start") and t.get("date_start_has_time") else None,
            "topic": topics,
            "priority": PRIORITY.get(t["priority"]),
            "cadence": min(cad, key=CADENCE_RANK.index) if cad else None,
            "ready": READY_TAG in tags,
            "status": "Done" if done else "To do",
            "triage": "Archived" if done else None,
            "created": _date(t["date_created"]),
            "completed": _date(t.get("date_completed")),
            "modified": _date(t["date_modified"]),
            "notes": notes,
        })

    ids = {r["rtm_id"] for r in records}
    orphans = [r["rtm_id"] for r in records if r["parent_id"] and r["parent_id"] not in ids]
    if orphans:
        warnings.append(f"{len(orphans)} rows reference a missing parent: {orphans[:5]}")
    placed = sum(len(r["notes"]) for r in records)
    if placed != len(raw["notes"]):
        warnings.append(f"note count mismatch: placed {placed} of {len(raw['notes'])}")
    return records, warnings


def summarize(records: list[dict], warnings: list[str]) -> None:
    """Print a one-screen summary of what the transform produced."""
    topics = collections.Counter(g for r in records for g in r["topic"])
    print(f"records          {len(records)}")
    print(f"  open           {sum(1 for r in records if r['status'] == 'To do')}")
    print(f"  archived       {sum(1 for r in records if r['triage'] == 'Archived')}")
    print(f"  with parent    {sum(1 for r in records if r['parent_id'])}")
    print(f"  with date      {sum(1 for r in records if r['date'])}")
    print(f"  with link      {sum(1 for r in records if r['link'])}")
    print(f"  with cadence   {sum(1 for r in records if r['cadence'])}")
    print(f"notes            {sum(len(r['notes']) for r in records)}")
    print(f"topics           {len(topics)}")
    for w in warnings:
        print("  !", w)


if __name__ == "__main__":
    summarize(*load_records(sys.argv[1]))
