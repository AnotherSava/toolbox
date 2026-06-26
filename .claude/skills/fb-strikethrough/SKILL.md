---
name: fb-strikethrough
description: >-
  Apply native strikethrough to a Facebook group post via the fb-strikethrough CLI.
  TRIGGER when: the user pastes a facebook.com/groups/.../posts/... URL and wants it
  struck through / crossed out, or types /fb-strikethrough with a post URL.
  DO NOT TRIGGER for non-Facebook URLs, or for member-activity URLs
  (/groups/{group}/user/{member}/) — those are not editable posts.
allowed-tools: Bash(fb-strikethrough:*), AskUserQuestion
---

# fb-strikethrough

Run the `fb-strikethrough` CLI to apply native strikethrough formatting to a Facebook
group post. The CLI opens a headed Chrome session (shared `.browser_profiles/facebook/`
login), edits the post, and **auto-saves** — there is no review step in the tool itself,
so the URL guard below is the only safety check.

## Marker behavior

The tool reads `tools/fb_strikethrough/config/config.json`. If a `marker` is set (currently
`$`), it strikes **only the paragraphs containing that marker**; other lines are left
intact. If `marker` is `null`, it strikes every line. Mention this in the result so the
user knows what to expect.

## Process

1. **Get the URL.** Take it from the skill arguments or the user's latest message.

2. **Validate the URL shape** before running anything:
   - **Valid** — a single-post permalink: `/groups/{group}/posts/{post}` or
     `/groups/{group}/permalink/{post}`. Proceed to step 3.
   - **Member-activity URL** — `/groups/{group}/user/{member}/` (one member's posts, not a
     single post). STOP. The tool would edit whichever post renders first and save it. Ask
     the user (AskUserQuestion) to paste the direct post permalink instead. Do NOT run the
     CLI on this URL.
   - **Anything else** (not a `facebook.com/groups/...` URL, or no post id). STOP and tell
     the user what a valid post permalink looks like. Do NOT run the CLI.

3. **Run the tool** with the validated URL:
   ```
   fb-strikethrough "<url>"
   ```
   It can take up to ~5 minutes on first run (manual Facebook login in the opened window);
   normally it completes in seconds reusing the saved session.

4. **Report the result.** No error means the edit-and-save flow completed. Tell the user:
   - which marker rule applied (from the config above), and
   - to glance at the open browser window to confirm the post looks right; if it's wrong,
     they can re-run or edit the post again manually (the edit is reversible).

## Out of scope

- Do NOT edit the CLI, config, or `marker` value — only run the tool. If the user wants
  different marker behavior, point them to `tools/fb_strikethrough/config/config.json`.
- Do NOT run the CLI on member-activity URLs or non-post URLs.
- Do NOT attempt to undo a previous strikethrough — re-running on the same post is safe
  (the tool strips existing strikethrough before re-applying), but undoing is a manual edit.
