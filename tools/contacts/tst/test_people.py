"""Tests for the label arithmetic over People API payloads."""

from contacts_tools.people import (
    display_name,
    label_distribution,
    membership_resource_names,
    primary_email,
    unlabeled,
    user_group_names,
    user_labels,
)


GROUPS = [
    {"resourceName": "contactGroups/myContacts", "name": "myContacts", "formattedName": "My Contacts", "groupType": "SYSTEM_CONTACT_GROUP"},
    {"resourceName": "contactGroups/starred", "name": "starred", "formattedName": "Starred", "groupType": "SYSTEM_CONTACT_GROUP"},
    {"resourceName": "contactGroups/1a2b", "name": "friends", "formattedName": "friends", "groupType": "USER_CONTACT_GROUP"},
    {"resourceName": "contactGroups/3c4d", "name": "archive", "formattedName": "archive", "groupType": "USER_CONTACT_GROUP"},
    {"resourceName": "contactGroups/5e6f", "name": "empty", "formattedName": "empty", "groupType": "USER_CONTACT_GROUP"},
]


def person(name: str, group_ids: list[str], email: str = "") -> dict:
    """Build a connections.list entry with the given contact group memberships."""
    entry: dict = {
        "resourceName": f"people/{name}",
        "names": [{"displayName": name}],
        "memberships": [{"contactGroupMembership": {"contactGroupResourceName": f"contactGroups/{gid}"}} for gid in group_ids],
    }
    if email:
        entry["emailAddresses"] = [{"value": email}]
    return entry


def test_user_group_names_excludes_system_groups():
    groups = user_group_names(GROUPS)
    assert groups == {"contactGroups/1a2b": "friends", "contactGroups/3c4d": "archive", "contactGroups/5e6f": "empty"}


def test_system_only_membership_counts_as_unlabeled():
    groups = user_group_names(GROUPS)
    connections = [person("Only System", ["myContacts", "starred"]), person("Labelled", ["myContacts", "1a2b"])]
    assert [display_name(p) for p in unlabeled(connections, groups)] == ["Only System"]


def test_contact_with_no_memberships_at_all_is_unlabeled():
    groups = user_group_names(GROUPS)
    assert len(unlabeled([{"names": [{"displayName": "Bare"}]}], groups)) == 1


def test_label_distribution_counts_each_label_and_keeps_empty_ones():
    groups = user_group_names(GROUPS)
    connections = [
        person("A", ["myContacts", "1a2b"]),
        person("B", ["myContacts", "1a2b", "3c4d"]),
        person("C", ["myContacts"]),
    ]
    assert label_distribution(connections, groups) == {"friends": 2, "archive": 1, "empty": 0}


def test_user_labels_are_sorted_and_named():
    groups = user_group_names(GROUPS)
    assert user_labels(person("A", ["3c4d", "1a2b", "starred"]), groups) == ["archive", "friends"]


def test_membership_falls_back_to_contact_group_id():
    entry = {"memberships": [{"contactGroupMembership": {"contactGroupId": "1a2b"}}]}
    assert membership_resource_names(entry) == ["contactGroups/1a2b"]


def test_domain_membership_is_ignored():
    entry = {"memberships": [{"domainMembership": {"inViewerDomain": True}}]}
    assert membership_resource_names(entry) == []


def test_unknown_group_does_not_count_as_a_label():
    """A membership in a group missing from contactGroups.list must not mask an unlabeled contact."""
    groups = user_group_names(GROUPS)
    assert len(unlabeled([person("Ghost", ["deadbeef"])], groups)) == 1


def test_display_name_falls_back_through_org_then_email():
    assert display_name({"organizations": [{"name": "Acme"}]}) == "Acme"
    assert display_name({"emailAddresses": [{"value": "a@b.c"}]}) == "a@b.c"
    assert display_name({}) == "(no name)"


def test_primary_email_handles_missing_field():
    assert primary_email({}) == ""
    assert primary_email(person("A", [], email="a@b.c")) == "a@b.c"
