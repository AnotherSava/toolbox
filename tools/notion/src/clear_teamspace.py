"""Deletes all pages from a selected teamspace."""

from .client import NotionClient, create_client, get_spaces


def get_teams(client: NotionClient, space_id: str) -> dict[str, str]:
    """Retrieve all teamspaces in a workspace.

    Returns:
        Mapping of team_id to team_name.
    """
    response = client.post("getTeams", {"spaceId": space_id}).json()
    teams = response.get("recordMap", {}).get("team", {})
    return {team_id: data["value"]["name"] for team_id, data in teams.items()}


def get_teamspace_pages(client: NotionClient, space_id: str, team_id: str) -> list[str]:
    """Retrieve up to 1000 page IDs in a teamspace."""
    query = {
        "type": "BlocksInSpace",
        "query": "",
        "filters": {
            "isDeletedOnly": False,
            "excludeTemplates": False,
            "isNavigableOnly": True,
            "requireEditPermissions": False,
            "ancestors": [],
            "createdBy": [],
            "editedBy": [],
            "lastEditedTime": {},
            "createdTime": {},
            "inTeams": [team_id],
            "includePublicPagesWithoutExplicitAccess": False,
            "navigableBlockContentOnly": True,
        },
        "sort": {"field": "lastEdited", "direction": "desc"},
        "limit": 1000,
        "spaceId": space_id,
        "source": "quick_find",
    }
    results = client.post("/api/v3/search", query).json()
    return [block["id"] for block in results["results"]]


def delete_blocks(client: NotionClient, block_ids: list[str], permanently: bool = False, chunk_size: int = 10) -> None:
    """Delete blocks in batches."""
    for i in range(0, len(block_ids), chunk_size):
        batch = block_ids[i : i + chunk_size]
        try:
            client.post("deleteBlocks", {"blockIds": batch, "permanentlyDelete": permanently})
            print(f"\tDeleted: {batch}")
        except Exception as e:
            print(f"\tFailed: {batch} ({e})")


def choose_option(options: dict[str, str], label: str) -> tuple[str, str]:
    """Prompt the user to pick from a numbered list."""
    items = list(options.items())
    for idx, (_, name) in enumerate(items, 1):
        print(f"  {idx}. {name}")
    choice = int(input(f"Select {label} (number): ")) - 1
    if choice < 0 or choice >= len(items):
        raise SystemExit("Invalid selection.")
    return items[choice]


def main() -> int:
    client = create_client()
    spaces = get_spaces(client)

    print("Workspaces:")
    space_id, space_name = choose_option(spaces, "workspace")
    print()

    teams = get_teams(client, space_id)
    if not teams:
        raise SystemExit("No teamspaces found.")

    print("Teamspaces:")
    team_id, team_name = choose_option(teams, "teamspace")
    print()

    if input(f'Permanently delete all pages in "{team_name}"? (yes/no) ') != "yes":
        return 1

    total_deleted = 0
    while True:
        page_ids = get_teamspace_pages(client, space_id, team_id)
        if not page_ids:
            break
        print(f"Batch: {len(page_ids)} page(s) found.")
        delete_blocks(client, page_ids, permanently=True)
        total_deleted += len(page_ids)
        print(f"Total deleted so far: {total_deleted}\n")

    print(f"Done. Deleted {total_deleted} page(s) total.")
    return 0
