import argparse
import asyncio
import sys
from pathlib import Path

from tools.fb_strikethrough.strikethrough import to_strikethrough

# Browser profile directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BROWSER_PROFILES_DIR = PROJECT_ROOT / ".browser_profiles"
FB_PROFILE_DIR = BROWSER_PROFILES_DIR / "facebook"

_SELECT_ALL = "Meta+a" if sys.platform == "darwin" else "Control+a"


async def edit_post(url: str, *, _playwright_factory=None) -> None:
    """Open a Facebook group post and replace its text with strikethrough version."""
    if _playwright_factory is None:
        from playwright.async_api import async_playwright

        _playwright_factory = async_playwright

    async with _playwright_factory() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(FB_PROFILE_DIR),
            headless=False,
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()

            # Navigate to the post
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")

            # Click the three-dot menu on the post
            more_button = page.get_by_label("More").first
            await more_button.click()

            # Click "Edit post" in the dropdown
            await page.get_by_text("Edit post", exact=True).click()

            # Wait for the editor textbox to appear
            editor = page.get_by_role("textbox").last
            await editor.wait_for(state="visible")

            # Read the current text
            await editor.click()
            original_text = await editor.inner_text()

            # Convert to strikethrough
            struck_text = to_strikethrough(original_text)

            # Clear and type the converted text
            await page.keyboard.press(_SELECT_ALL)
            await page.keyboard.press("Backspace")
            await editor.fill(struck_text)

            # Click Save
            save_button = page.get_by_role("button", name="Save")
            await save_button.click()

            # Wait for save to complete
            await page.wait_for_load_state("networkidle")
        finally:
            await context.close()


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Replace a Facebook group post's text with strikethrough Unicode."
    )
    parser.add_argument(
        "url",
        help="URL of the Facebook group post to edit",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(edit_post(args.url))


if __name__ == "__main__":
    main()
