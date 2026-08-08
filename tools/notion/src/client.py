"""Shared Notion API client using token_v2 cookie authentication.

The token comes from the ``NOTION_TOKEN_V2`` environment variable, supplied by
Doppler (project ``toolbox``, config ``dev``) — so anything touching Notion runs
under ``doppler run -- …``. There is deliberately no on-disk fallback: a second
copy in a config file is exactly the per-machine drift Doppler prevents, and it
would put a live credential back in plaintext.
"""

import os

import requests

TOKEN_ENV = "NOTION_TOKEN_V2"


class NotionClient:
    """Simple Notion API client using token_v2 cookie authentication."""

    def __init__(self, token_v2: str):
        self.session = requests.Session()
        self.session.cookies.set("token_v2", token_v2)
        self.session.headers["Content-Type"] = "application/json"

    def post(self, endpoint: str, data: dict) -> requests.Response:
        """Send a POST request to the Notion API."""
        if not endpoint.startswith("/"):
            endpoint = f"/api/v3/{endpoint}"
        return self.session.post(f"https://www.notion.so{endpoint}", json=data)


def create_client() -> NotionClient:
    """Create a NotionClient from the ``NOTION_TOKEN_V2`` environment variable."""
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise SystemExit(
            f"{TOKEN_ENV} is not set — Notion credentials live in Doppler.\n"
            f"Run the command through Doppler:  doppler run -- <command>\n"
            f"First time on this machine:       doppler login && doppler setup"
        )
    return NotionClient(token)


def get_spaces(client: NotionClient) -> dict[str, str]:
    """Retrieve all workspaces accessible to the user.

    Returns:
        Mapping of space_id to space_name.
    """
    response = client.post("loadUserContent", {}).json()
    if "recordMap" not in response:
        raise SystemExit(f"Auth error: {response}")
    spaces = response["recordMap"]["space"]
    return {space_id: data["value"]["name"] for space_id, data in spaces.items()}
