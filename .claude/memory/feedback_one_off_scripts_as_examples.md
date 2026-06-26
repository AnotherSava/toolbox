---
name: One-off scripts go in docs/examples, not src
description: When a script captures a one-off workflow that's unlikely to recur exactly, frame it as an example rather than a polished CLI subcommand.
type: feedback
---
When you produce a script for an ad-hoc task (e.g., migrating a specific Notion page structure, scraping one site once), default to placing it under the tool's `docs/examples/` directory with a docstring that says "EXAMPLE — copy and adapt", and DON'T register it as a CLI subcommand.

Reusable building blocks should be extracted into a real tool (e.g., `image_opt` for "optimize images before uploading anywhere"), not buried inside the example.

**Why:** During the May 2026 Notion image-optimization session, I built `plain_to_collection` and `extract_images` and registered them as `notion plain-to-collection` / `notion extract-images`. The user pushed back: "frame them more like examples — I'm not sure I'll need to do exactly the same activity in the future, more likely it will be just image optimization prior to adding to notion, rather than modifying in place." The recurring need was the generic primitive (image optimization), not the workflow that happened to use it.

**How to apply:**
- After finishing an ad-hoc task, ask: "is the recurring need the workflow I just automated, or a primitive inside it?"
- If the primitive is what's recurring, extract it into its own tool. Demote the workflow script to `tools/<tool>/docs/examples/<name>.py` with an `EXAMPLE:` docstring header.
- Don't auto-register every script as a subcommand. Subcommands are for genuinely reusable, parametrized tools.
- Examples are still expected to run (`python tools/.../examples/foo.py --help` should work). Use the installed package imports (`from notion_tools.client import ...`), not relative imports or `sys.path` hacks.
