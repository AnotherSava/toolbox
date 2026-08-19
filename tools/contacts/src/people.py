"""Pure helpers over People API payloads.

Kept free of network access so the label arithmetic — the part that decides
whether a contact counts as unlabeled — is testable on plain dictionaries.
"""

from typing import Any

USER_GROUP = "USER_CONTACT_GROUP"


def user_group_names(groups: list[dict[str, Any]]) -> dict[str, str]:
    """Map resource name to label name, for user-created labels only.

    The People API tags every group as ``USER_CONTACT_GROUP`` or
    ``SYSTEM_CONTACT_GROUP``, which is what separates a real label from the
    ``myContacts`` / ``starred`` bookkeeping groups every contact carries. The web
    UI's CSV export offers no such flag — there you have to guess from a ``*``
    name prefix, which is a display convention rather than a guarantee.
    """
    return {g["resourceName"]: g.get("formattedName") or g.get("name", "") for g in groups if g.get("groupType") == USER_GROUP}


def membership_resource_names(person: dict[str, Any]) -> list[str]:
    """Return the contact-group resource names a person belongs to.

    Ignores ``domainMembership`` entries, which Workspace directory contacts carry
    instead of a contact group.
    """
    names = []
    for membership in person.get("memberships", []):
        group = membership.get("contactGroupMembership")
        if not group:
            continue
        resource = group.get("contactGroupResourceName")
        if not resource and group.get("contactGroupId"):
            resource = f"contactGroups/{group['contactGroupId']}"
        if resource:
            names.append(resource)
    return names


def user_labels(person: dict[str, Any], groups: dict[str, str]) -> list[str]:
    """Return the user-created label names a person carries, sorted."""
    return sorted(groups[name] for name in membership_resource_names(person) if name in groups)


def display_name(person: dict[str, Any]) -> str:
    """Best available human-readable name, falling back through org, email, phone."""
    names = person.get("names") or []
    if names and names[0].get("displayName"):
        return names[0]["displayName"]
    organizations = person.get("organizations") or []
    if organizations and organizations[0].get("name"):
        return organizations[0]["name"]
    emails = person.get("emailAddresses") or []
    if emails and emails[0].get("value"):
        return emails[0]["value"]
    phones = person.get("phoneNumbers") or []
    if phones and phones[0].get("value"):
        return phones[0]["value"]
    return "(no name)"


def primary_email(person: dict[str, Any]) -> str:
    """First email address, or an empty string."""
    emails = person.get("emailAddresses") or []
    return emails[0].get("value", "") if emails else ""


def primary_phone(person: dict[str, Any]) -> str:
    """First phone number, or an empty string."""
    phones = person.get("phoneNumbers") or []
    return phones[0].get("value", "") if phones else ""


def unlabeled(connections: list[dict[str, Any]], groups: dict[str, str]) -> list[dict[str, Any]]:
    """Return the contacts carrying no user-created label."""
    return [person for person in connections if not user_labels(person, groups)]


def label_distribution(connections: list[dict[str, Any]], groups: dict[str, str]) -> dict[str, int]:
    """Count contacts per user-created label, including labels with no members."""
    counts = {name: 0 for name in groups.values()}
    for person in connections:
        for label in user_labels(person, groups):
            counts[label] += 1
    return counts
