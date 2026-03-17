import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from fb_strikethrough.main import build_parser, edit_post, FB_PROFILE_DIR


class TestCLIArgParsing:
    def test_url_is_optional_positional(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.url is None

    def test_url_is_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["https://www.facebook.com/groups/123/posts/456"])
        assert args.url == "https://www.facebook.com/groups/123/posts/456"


def _build_mock_playwright():
    """Build a mock Playwright stack matching the current edit_post flow."""

    # Editor locator
    mock_editor = MagicMock()
    mock_editor.wait_for = AsyncMock()
    mock_editor.click = AsyncMock()
    mock_editor.inner_text = AsyncMock(return_value="hello world")
    mock_editor.fill = AsyncMock()

    # Actions button (three-dot menu)
    mock_actions_button = MagicMock()
    mock_actions_button.click = AsyncMock()

    # Save button
    mock_save_button = MagicMock()
    mock_save_button.click = AsyncMock()

    # Edit post menu item
    mock_edit_post = MagicMock()
    mock_edit_post.click = AsyncMock()

    # Page mock
    mock_page = MagicMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.wait_for_url = AsyncMock()
    mock_page.evaluate = AsyncMock()
    # page.url returns a Facebook groups URL so login check is skipped
    type(mock_page).url = property(lambda self: "https://www.facebook.com/groups/123/posts/456")

    mock_keyboard = MagicMock()
    mock_keyboard.press = AsyncMock()
    mock_page.keyboard = mock_keyboard

    mock_page.get_by_text = MagicMock(return_value=mock_edit_post)

    def get_by_role_side_effect(role, **kwargs):
        name = kwargs.get("name", "")
        if role == "button" and name == "Actions for this post":
            return mock_actions_button
        if role == "button" and name == "Save":
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

    def test_navigates_to_post_url(self):
        mock_pw, mock_context, mock_page, mock_editor = _build_mock_playwright()
        factory = _make_factory(mock_pw)
        url = "https://www.facebook.com/groups/123/posts/456"
        asyncio.run(edit_post(url, _playwright_factory=factory))

        mock_page.goto.assert_called_once_with(url, wait_until="domcontentloaded")

    def test_clicks_actions_and_edit_post(self):
        mock_pw, mock_context, mock_page, mock_editor = _build_mock_playwright()
        factory = _make_factory(mock_pw)
        asyncio.run(edit_post("https://www.facebook.com/groups/123/posts/456", _playwright_factory=factory))

        # Verify "Actions for this post" button was clicked
        mock_page.get_by_role.assert_any_call("button", name="Actions for this post")
        # Verify "Edit post" was clicked
        mock_page.get_by_text.assert_called_with("Edit post", exact=True)

    def test_pastes_html_with_strikethrough(self):
        mock_pw, mock_context, mock_page, mock_editor = _build_mock_playwright()
        # Text contains "$" so it matches the marker in config
        mock_editor.inner_text = AsyncMock(return_value="selling $3k")
        factory = _make_factory(mock_pw)
        asyncio.run(edit_post("https://www.facebook.com/groups/123/posts/456", _playwright_factory=factory))

        # Verify clipboard HTML was set via page.evaluate
        mock_page.evaluate.assert_called_once()
        call_args = mock_page.evaluate.call_args
        js_code = call_args[0][0]
        html_arg = call_args[0][1]
        assert "ClipboardItem" in js_code
        assert html_arg == "<s>selling $3k</s>"

    def test_only_strikes_paragraphs_with_marker(self):
        mock_pw, mock_context, mock_page, mock_editor = _build_mock_playwright()
        mock_editor.inner_text = AsyncMock(return_value="selling $3k\n250+ reviews")
        factory = _make_factory(mock_pw)
        asyncio.run(edit_post("https://www.facebook.com/groups/123/posts/456", _playwright_factory=factory))

        html_arg = mock_page.evaluate.call_args[0][1]
        assert html_arg == "<s>selling $3k</s><br>250+ reviews"

    def test_closes_context_after_edit(self):
        mock_pw, mock_context, mock_page, mock_editor = _build_mock_playwright()
        factory = _make_factory(mock_pw)
        asyncio.run(edit_post("https://www.facebook.com/groups/123/posts/456", _playwright_factory=factory))

        mock_context.close.assert_called_once()
