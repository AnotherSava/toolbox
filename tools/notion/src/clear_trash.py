"""Permanently deletes all pages in the trash across all workspaces."""

from .client import NotionClient, create_client, get_spaces


def get_trashed_blocks(client: NotionClient, space_id: str) -> list[str]:
    """Retrieve all block IDs in the trash for a specific workspace."""
    query = {
        "type": "BlocksInSpace",
        "query": "",
        "filters": {
            "isDeletedOnly": True,
            "excludeTemplates": False,
            "isNavigableOnly": True,
            "requireEditPermissions": False,
            "ancestors": [],
            "createdBy": [],
            "editedBy": [],
            "lastEditedTime": {},
            "createdTime": {},
            "inTeams": [],
            "includePublicPagesWithoutExplicitAccess": False,
            "navigableBlockContentOnly": True,
        },
        "sort": {"field": "lastEdited", "direction": "desc"},
        "limit": 1000,
        "spaceId": space_id,
        "source": "trash",
    }
    results = client.post("/api/v3/search", query).json()
    return [block["id"] for block in results["results"]]


def delete_blocks_permanently(client: NotionClient, block_ids: list[str], chunk_size: int = 10) -> None:
    """Permanently delete blocks in batches."""
    if not block_ids:
        print("\tNo pages found.")
        return

    for i in range(0, len(block_ids), chunk_size):
        batch = block_ids[i : i + chunk_size]
        try:
            client.post("deleteBlocks", {"blockIds": batch, "permanentlyDelete": True})
            print(f"\tDeleted: {batch}")
        except Exception as e:
            print(f"\tFailed: {batch} ({e})")


def main() -> int:
    client = create_client()
    spaces = get_spaces(client)

    if input("Confirm? (yes/no) ") != "yes":
        return 1

    for space_id, space_name in spaces.items():
        print(space_name)
        block_ids = get_trashed_blocks(client, space_id)
        delete_blocks_permanently(client, block_ids)
        print()

    print("Done.")
    return 0
