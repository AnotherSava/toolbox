import pytest

from notion_tools.page_ids import parse_page_id

DASHED = "11112222-3333-4444-5555-666677778888"
BARE = "11112222333344445555666677778888"
OTHER = "99990000-aaaa-bbbb-cccc-ddddeeeeffff"


def test_parse_bare_hex():
    assert parse_page_id(BARE) == DASHED


def test_parse_already_dashed():
    assert parse_page_id(DASHED) == DASHED


def test_parse_url_with_title_slug():
    assert parse_page_id(f"https://www.notion.so/My-Page-{BARE}") == DASHED


def test_parse_url_with_view_query_ignores_view_id():
    # ?v= names a view, not a page — the path id still wins.
    assert parse_page_id(f"https://www.notion.so/My-Page-{BARE}?v={OTHER.replace('-', '')}") == DASHED


def test_parse_side_peek_url_prefers_the_peeked_row():
    # …?p=<row-id>&pm=s addresses the peeked row; the path names its parent.
    url = f"https://www.notion.so/Parent-Page-{BARE}?p={OTHER.replace('-', '')}&pm=s"
    assert parse_page_id(url) == OTHER


def test_parse_rejects_garbage():
    with pytest.raises(SystemExit):
        parse_page_id("not-a-page")
