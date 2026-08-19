"""Read-only reports over Google Contacts: label distribution, unlabeled, other."""

import argparse
import json
from typing import Any

from .client import ContactsClient, create_client
from .people import (
    display_name,
    label_distribution,
    primary_email,
    primary_phone,
    unlabeled,
    user_group_names,
    user_labels,
)


def _rows_to_table(rows: list[tuple[str, ...]], headers: tuple[str, ...]) -> str:
    """Render rows as a plain aligned table."""
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)] if rows else [len(h) for h in headers]
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip()]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(str(cell).ljust(w) for cell, w in zip(row, widths)).rstrip())
    return "\n".join(lines)


def _parse_args(description: str) -> argparse.Namespace:
    """Parse the arguments every report subcommand accepts."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    return parser.parse_args()


def _fetch(client: ContactsClient) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    """Return (connections, user label names by resource name, raw groups)."""
    groups = client.list_contact_groups()
    return client.list_connections(), user_group_names(groups), groups


_PERSON_HEADERS = ("name", "email", "phone")


def _person_row(person: dict[str, Any]) -> tuple[str, str, str]:
    """Table row for a person, matching _PERSON_HEADERS."""
    return display_name(person), primary_email(person), primary_phone(person)


def _person_fields(person: dict[str, Any]) -> dict[str, str]:
    """JSON object for a person, mirroring _person_row."""
    return dict(zip(_PERSON_HEADERS, _person_row(person)))


def labels_main() -> int:
    """Print how many contacts carry each user-created label."""
    args = _parse_args("Show the contact count for each label.")

    client = create_client()
    connections, groups, raw_groups = _fetch(client)
    counts = label_distribution(connections, groups)
    unlabeled_count = len(unlabeled(connections, groups))

    if args.json:
        print(json.dumps({"total": len(connections), "unlabeled": unlabeled_count, "labels": counts}, indent=2, ensure_ascii=False))
        return 0

    rows = [(label, str(count)) for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))]
    print(_rows_to_table(rows, ("label", "contacts")))
    print(f"\n{len(connections)} contacts, {len(counts)} labels, {unlabeled_count} with no label")

    # The API reports its own memberCount per group; a mismatch means the label
    # arithmetic here and Google's disagree, which is worth knowing about loudly.
    reported = {g.get("formattedName") or g.get("name", ""): g.get("memberCount", 0) for g in raw_groups if g["resourceName"] in groups}
    drift = [(name, counts[name], reported.get(name, 0)) for name in counts if counts[name] != reported.get(name, 0)]
    if drift:
        print("\nwarning: counts disagree with the API's memberCount:")
        for name, computed, api in drift:
            print(f"  {name}: computed {computed}, API {api}")
    return 0


def unlabeled_main() -> int:
    """Print the contacts that carry no user-created label."""
    args = _parse_args("List contacts with no label assigned.")

    client = create_client()
    connections, groups, _ = _fetch(client)
    people = unlabeled(connections, groups)

    if args.json:
        payload = [{**_person_fields(p), "resourceName": p.get("resourceName", "")} for p in people]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if not people:
        print(f"All {len(connections)} contacts have at least one label.")
        return 0
    print(_rows_to_table([_person_row(p) for p in people], _PERSON_HEADERS))
    print(f"\n{len(people)} of {len(connections)} contacts have no label")
    return 0


def other_main() -> int:
    """Print the auto-collected "Other contacts", which carry no labels by design."""
    args = _parse_args('List "Other contacts" — addresses Google auto-collected from mail. Not exportable from the web UI.')

    people = create_client().list_other_contacts()

    if args.json:
        print(json.dumps([_person_fields(p) for p in people], indent=2, ensure_ascii=False))
        return 0

    print(_rows_to_table([_person_row(p) for p in people], _PERSON_HEADERS))
    print(f"\n{len(people)} other contacts")
    return 0


def show_main() -> int:
    """Print every contact with the labels it carries."""
    args = _parse_args("List all contacts and their labels.")

    client = create_client()
    connections, groups, _ = _fetch(client)

    if args.json:
        payload = [
            {"name": display_name(p), "email": primary_email(p), "labels": user_labels(p, groups)}
            for p in connections
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    rows = [(display_name(p), primary_email(p), ", ".join(user_labels(p, groups)) or "—") for p in connections]
    print(_rows_to_table(rows, ("name", "email", "labels")))
    print(f"\n{len(connections)} contacts")
    return 0
