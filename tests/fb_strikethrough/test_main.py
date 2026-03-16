import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from tools.fb_strikethrough.main import build_parser, edit_post, FB_PROFILE_DIR
from tools.fb_strikethrough.strikethrough import to_strikethrough


class TestCLIArgParsing:
    def test_url_is_required(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([])
        assert exc_info.value.code == 2

    def test_url_is_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["https://www.facebook.com/groups/123/posts/456"])
        assert args.url == "https://www.facebook.com/groups/123/posts/456"


def _build_mock_playwright():
    """Build a mock Playwright stack where locator methods are sync (return MagicMock)
    and action methods (click, fill, goto, etc.) are async."""

    # Editor locator - sync attributes, async actions
    mock_editor = MagicMock()
    mock_editor.wait_for = AsyncMock()
    mock_editor.click = AsyncMock()
    mock_editor.inner_text = AsyncMock(return_value="hello world")
    mock_editor.fill = AsyncMock()

    # Save button locator
    mock_save_button = MagicMock()
    mock_save_button.click = AsyncMock()

    # More button locator
    mock_more_first = MagicMock()
    mock_more_first.click = AsyncMock()
    mock_more_locator = MagicMock()
    mock_more_locator.first = mock_more_first

    # Edit post menu item
    mock_edit_post = MagicMock()
    mock_edit_post.click = AsyncMock()

    # Page mock - locator methods are sync, navigation methods are async
    mock_page = MagicMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()

    mock_keyboard = MagicMock()
    mock_keyboard.press = AsyncMock()
    mock_page.keyboard = mock_keyboard

    mock_page.get_by_label = MagicMock(return_value=mock_more_locator)

    mock_page.get_by_text = MagicMock(return_value=mock_edit_post)

    def get_by_role_side_effect(role, **kwargs):
        if role == "button":
            return mock_save_button
        result = MagicMock()
        result.last = mock_editor
        return result

    mock_page.get_by_role = MagicMock(side_effect=get_by_role_side_effect)

    # Context mock
    mock_context = AsyncMock()
    mock_context.pages = [mock_page]

    # Playwright mock
    mock_pw = MagicMock()
    mock_pw.chromium = MagicMock()
    mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

    return mock_pw, mock_context, mock_page, mock_editor


def _make_factory(mock_pw):
    """Create a factory that returns an async context manager yielding mock_pw."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_pw)
    cm.__aexit__ = AsyncMock(return_value=None)

    def factory():
        return cm

    return factory


class TestEditPost:
    def test_launches_with_correct_profile_and_headed(self):
        mock_pw, mock_context, mock_page, mock_editor = _build_mock_playwright()
        factory = _make_factory(mock_pw)
        asyncio.run(edit_post("https://www.facebook.com/groups/123/posts/456", _playwright_factory=factory))

        mock_pw.chromium.launch_persistent_context.assert_called_once_with(
            user_data_dir=str(FB_PROFILE_DIR),
            headless=False,
        )

    def test_applies_strikethrough_to_text(self):
        mock_pw, mock_context, mock_page, mock_editor = _build_mock_playwright()
        factory = _make_factory(mock_pw)
        asyncio.run(edit_post("https://www.facebook.com/groups/123/posts/456", _playwright_factory=factory))

        mock_editor.fill.assert_called_once()
        filled_text = mock_editor.fill.call_args[0][0]
        assert filled_text == to_strikethrough("hello world")

    def test_navigates_to_post_url(self):
        mock_pw, mock_context, mock_page, mock_editor = _build_mock_playwright()
        factory = _make_factory(mock_pw)
        url = "https://www.facebook.com/groups/123/posts/456"
        asyncio.run(edit_post(url, _playwright_factory=factory))

        mock_page.goto.assert_called_once_with(url, wait_until="domcontentloaded")

    def test_closes_context_after_edit(self):
        mock_pw, mock_context, mock_page, mock_editor = _build_mock_playwright()
        factory = _make_factory(mock_pw)
        asyncio.run(edit_post("https://www.facebook.com/groups/123/posts/456", _playwright_factory=factory))

        mock_context.close.assert_called_once()
