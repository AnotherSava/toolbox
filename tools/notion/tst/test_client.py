import os
from unittest.mock import patch

from notion_tools.client import NotionClient, create_client, get_spaces, unwrap_record


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


def test_create_client_reads_env():
    with patch.dict(os.environ, {"NOTION_TOKEN_V2": "test_token"}):
        client = create_client()
        assert client.session.cookies.get("token_v2") == "test_token"


def test_unwrap_record_handles_permission_envelope():
    entry = {"value": {"role": "editor", "value": {"name": "My Space"}}}
    assert unwrap_record(entry) == {"name": "My Space"}


def test_unwrap_record_handles_flat_record():
    assert unwrap_record({"value": {"name": "My Space"}}) == {"name": "My Space"}


def test_get_spaces_reads_through_the_envelope(requests_mock):
    # Notion wraps space records as {"value": {"role", "value"}}; reading one
    # level too few used to raise KeyError: 'name', which broke `notion clear-trash`
    # at its first call.
    requests_mock.post(
        "https://www.notion.so/api/v3/loadUserContent",
        json={"recordMap": {"space": {"sid-1": {"value": {"role": "editor", "value": {"name": "My Space"}}}}}},
    )
    assert get_spaces(NotionClient("fake_token")) == {"sid-1": "My Space"}


def test_create_client_missing_token_points_at_doppler():
    # clear=True so this still exercises the missing-token path when pytest
    # itself is run under `doppler run --`, which would otherwise supply it.
    with patch.dict(os.environ, {}, clear=True):
        try:
            create_client()
            assert False, "Expected SystemExit"
        except SystemExit as e:
            assert "NOTION_TOKEN_V2" in str(e)
            assert "doppler run" in str(e)
