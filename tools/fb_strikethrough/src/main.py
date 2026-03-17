import argparse
import asyncio
import html as html_module
import json
import sys
from pathlib import Path

from .strikethrough import strip_strikethrough

# Browser profile directories
TOOL_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = TOOL_DIR.parent.parent
BROWSER_PROFILES_DIR = PROJECT_ROOT / ".browser_profiles"
FB_PROFILE_DIR = BROWSER_PROFILES_DIR / "facebook"
CONFIG_PATH = TOOL_DIR / "config" / "config.json"

_PASTE = "Meta+v" if sys.platform == "darwin" else "Control+v"


async def edit_post(url: str, *, _playwright_factory=None) -> None:
    """Open a Facebook group post and apply native strikethrough formatting."""
    if _playwright_factory is None:
        from playwright.async_api import async_playwright

        _playwright_factory = async_playwright

    async with _playwright_factory() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(FB_PROFILE_DIR),
            headless=False,
            permissions=["clipboard-read", "clipboard-write"],
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()

            # Navigate to the post
            await page.goto(url, wait_until="domcontentloaded")

            # If redirected away from target (login, 2FA, etc.), wait for user
            if "/groups/" not in page.url:
                print("Login required. Please log in to Facebook in the browser window.")
                print("Waiting for you to reach the post...")
                await page.wait_for_url(
                    lambda u: "/groups/" in u,
                    timeout=300_000,  # 5 minutes to log in
                )

            # Wait for the post modal to render
            await page.wait_for_timeout(3000)

            # Click the three-dot menu on the post
            actions_button = page.get_by_role("button", name="Actions for this post")
            await actions_button.click(timeout=10_000)

            # Click "Edit post" in the dropdown
            await page.get_by_text("Edit post", exact=True).click()

            # Wait for the editor textbox to appear
            editor = page.get_by_role("textbox").last
            await editor.wait_for(state="visible", timeout=10_000)
            await editor.click()

            # Read text and strip any existing Unicode strikethrough (U+0336)
            original_text = await editor.inner_text()
            clean_text = strip_strikethrough(original_text)

            # Load marker from config — if set, only strike paragraphs containing it
            marker = None
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH) as f:
                    cfg = json.load(f)
                marker = cfg.get("marker")

            # Build HTML
            lines = clean_text.split("\n")
            html_parts = []
            for line in lines:
                if marker is None or marker in line:
                    html_parts.append("<s>" + html_module.escape(line) + "</s>")
                else:
                    html_parts.append(html_module.escape(line))
            html = "<br>".join(html_parts)

            # Select all existing text, then write HTML to clipboard and paste
            _select_all = "Meta+a" if sys.platform == "darwin" else "Control+a"
            await page.keyboard.press(_select_all)

            await page.evaluate("""async (html) => {
                const blob = new Blob([html], {type: 'text/html'});
                const item = new ClipboardItem({'text/html': blob});
                await navigator.clipboard.write([item]);
            }""", html)
            await page.keyboard.press(_PASTE)

            # Click Save
            await page.wait_for_timeout(1000)
            save_button = page.get_by_role("button", name="Save")
            await save_button.click()

            # Wait briefly for save to complete
            await page.wait_for_timeout(2000)
        finally:
            await context.close()


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Apply strikethrough formatting to a Facebook group post."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="URL of the Facebook group post to edit",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    url = args.url or input("Post URL: ").strip()
    if not url:
        parser.error("URL is required")
    asyncio.run(edit_post(url))


if __name__ == "__main__":
    main()
