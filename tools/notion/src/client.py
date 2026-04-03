"""Shared Notion API client using token_v2 cookie authentication."""

import json
from pathlib import Path

import requests

TOOL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = TOOL_DIR / "config" / "config.json"


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
    """Create a NotionClient from config.json."""
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Config not found: {CONFIG_PATH}\nCreate it with: {{\"notion_token_v2\": \"your_token\"}}")
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    token = cfg.get("notion_token_v2")
    if not token:
        raise SystemExit(f"notion_token_v2 not set in {CONFIG_PATH}")
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
