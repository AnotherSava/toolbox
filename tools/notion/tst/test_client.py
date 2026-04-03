import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from notion_tools.client import NotionClient, create_client


def test_client_sets_cookie():
    client = NotionClient("fake_token")
    assert client.session.cookies.get("token_v2") == "fake_token"


def test_client_sets_content_type():
    client = NotionClient("fake_token")
    assert client.session.headers["Content-Type"] == "application/json"


def test_client_post_builds_url(requests_mock):
    client = NotionClient("fake_token")
    requests_mock.post("https://www.notion.so/api/v3/loadUserContent", json={"ok": True})
    resp = client.post("loadUserContent", {})
    assert resp.json() == {"ok": True}


def test_client_post_absolute_endpoint(requests_mock):
    client = NotionClient("fake_token")
    requests_mock.post("https://www.notion.so/api/v3/search", json={"results": []})
    resp = client.post("/api/v3/search", {})
    assert resp.json() == {"results": []}


def test_create_client_missing_config():
    with patch("notion_tools.client.CONFIG_PATH", Path("/nonexistent/config.json")):
        try:
            create_client()
            assert False, "Expected SystemExit"
        except SystemExit as e:
            assert "Config not found" in str(e)


def test_create_client_missing_token():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        config_path = Path(f.name)
    try:
        with patch("notion_tools.client.CONFIG_PATH", config_path):
            try:
                create_client()
                assert False, "Expected SystemExit"
            except SystemExit as e:
                assert "notion_token_v2 not set" in str(e)
    finally:
        config_path.unlink(missing_ok=True)


def test_create_client_success():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"notion_token_v2": "test_token"}, f)
        config_path = Path(f.name)
    try:
        with patch("notion_tools.client.CONFIG_PATH", config_path):
            client = create_client()
            assert client.session.cookies.get("token_v2") == "test_token"
    finally:
        config_path.unlink(missing_ok=True)
