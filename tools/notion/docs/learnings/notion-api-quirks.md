# Notion Internal API Quirks

Notion internal API (token_v2 cookie auth, /api/v3/ endpoints) has several quirks discovered during development:

- **Search API has a hard 1000-result limit.** Pagination tokens cycle and return duplicates rather than advancing. Workaround: delete results in batches (fetch 1000, delete, re-fetch until empty).

- **`getTeams` response format.** Teamspaces are nested under `recordMap.team`, not returned as a flat list.

- **Archived vs. trashed pages are fundamentally different.** Trash is global and searchable via `isDeletedOnly` filter. Archives are per-parent page with no global "all archived" view — there's no API to list all archived pages across a workspace.

- **`getSignedFileUrls` URLs return 403 from `file.notion.so` even with `token_v2`.** The file.notion.so domain enforces extra browser-session checks beyond the cookie, so direct GETs fail with the 6 KB "Access denied" HTML page (Server: AmazonS3). Workaround: download via the image proxy at `https://www.notion.so/image/<URL-encoded attachment URL>?table=block&id=<host_block_id>&spaceId=<space_id>&width=2000&cache=v2`. The proxy honors the cookie and even auto-converts HEIC to JPEG.

- **File upload uses `getUploadFileUrl`.** Pass `{bucket: "secure", name, contentType, record: {table, id, spaceId}}`. The response gives back `signedPutUrl` (a real AWS-signed S3 URL — no cookie needed, just `Content-Type` header) plus the new `attachment:<uuid>:<filename>` reference to use in property values.

- **File-property values use the `[[filename, [["a", attachment_url]]]]` shape.** Set them via `saveTransactionsFanout` with `command: "set"` on `path: ["properties", "<prop_key>"]`.

- **Notion does not preview AVIF images in card / gallery views.** WebP is the next-best format for compression and renders fine. AVIF still works as a stored attachment but the thumbnail just doesn't render. Use WebP (q=60, max-width 1024) as the default for image-property workflows. Compression ratio drops sharply on already-small inputs (~14% of original for typical phone photos, ~38% if the source is already <150 KB).

- **`getActivityLog` recovers blocks that were just trashed** via `deleteBlocks`. Pass `{spaceId, navigableBlockId, limit: 500}` and the response's `recordMap.block` includes children (text, image, ...) of the navigable block with `alive: false` and their original `properties` intact — including image `source` attachment URLs. Useful when a script trashed blocks and needs to recover them. `loadPageChunk` and `BlocksInSpace` search both filter out `alive: false` non-navigable blocks, so this is the only path.

- **When caching downloaded files, key by attachment UUID, not by title.** Two rows with the same title (e.g., three "Waterproof bag" entries) will produce the same `safe_name(title)` and overwrite each other's downloads if the cache filename only uses the title. The attachment URL `attachment:<uuid>:<filename>` carries a unique UUID — include the first 8 chars in the cached filename to avoid collisions: `f"{safe_name(title)}__{attach_uuid[:8]}__{stem}{ext}"`.

- **Programmatically-created blocks don't get `created_time` auto-filled.** When you create a block via `saveTransactionsFanout` with `command: "set"` and a fresh UUID, Notion fills in CRDT data and `version` but leaves `created_time` absent. If you need stable ordering on rows you created, set `created_time` explicitly in the args, or sort by row UUID.

- **`format.block_color` on collection row blocks does not render in table view.** The value persists when set via `saveTransactionsFanout`, but Notion's table renderer ignores it (verified by setting six distinct vivid colors on visible rows — none rendered). Per-row coloring in inline databases must be done via `format.conditional_color_rules` on the *view*, not on the row block. `block_color` still works on standalone page blocks.

- **Conditional row colors via `format.conditional_color_rules` on a view.** Per-view rule shape:
  ```json
  [{
      "id": "<uuid>",
      "background": {"type": "match_property_value"},
      "conditional_filter": {"filter": {"operator": "is_not_empty"}, "property": "<schema_key>"},
      "properties_to_color": {"type": "all"}
  }]
  ```
  With `match_property_value`, the row background inherits the referenced select-property option's color — e.g. a row whose `Parity` property holds the option whose `color: "blue"` gets a blue row tint. Use a binary helper property (A/B, with one "default" and one colored option) to band rows by an arbitrary grouping with a single rule.

- **Column alignment cannot be set via v3 API.** None of `alignment`, `text_align`, `text_alignment`, `align`, or a nested `format.alignment` are honored — at either the schema level or the `format.table_properties[i]` level. All values persist; none render. Alignment is currently a Notion UI-only feature; users must right-click the column header to align.

- **`date_format` respects the fixed enum AND custom moment-style format strings.** Enum values: missing/empty (renders as "Full date", e.g. "July 4, 2025"), `relative`, `MM/DD/YYYY`, `DD/MM/YYYY`, `YYYY/MM/DD`. **Custom moment-style strings also render** — verified `MMM d` → "Jul 25" (abbreviated month + day, no year). The exception is the *shortcut* tokens `ll`/`LL`: they're accepted but silently fall back to Full date (this is what earlier testing hit, giving the wrong impression that no abbreviated form was possible). So abbreviated-month rendering IS achievable natively with a real format string like `MMM d` — the hidden-text-column workaround is unnecessary. Set the token via `saveTransactionsFanout` `command:"set"` on `path:["schema","<key>","date_format"]`; not settable through the official/MCP API.

- **Select options can't be recolored or removed via the official/MCP API — use v3.** The MCP `update_data_source` `ALTER COLUMN … SET SELECT(…)` rejects a color change (`Cannot update color of select with name: X`) and won't drop an option. Instead `saveTransactionsFanout` `command:"set"` on `path:["schema","<key>","options"]` with the full desired options array. **Preserve each kept option's `id`** (match by `value`) so existing cell values stay bound; give any new option a fresh `uuid` `id`.

- **Removing a select option does NOT clear the cells that used it.** Page values store the option by its string `value`, so a dropped option leaves an orphaned value on every row that had it. Null those cells first (set the property to null), *then* remove the option from the schema.

- **Date reminders live inside the date property value.** The value is the mention form `[["‣",[["d",{"type":"date","start_date":"YYYY-MM-DD"}]]]]`; add a `reminder` object inside the inner `d` object to attach a Notion reminder — `{"unit":"day"|"week","value":N,"time":"HH:MM"}` (e.g. `{"unit":"week","value":1,"time":"09:00"}` = "1 week before, 9am" on an all-day date). Set via `saveTransactionsFanout` `command:"set"` on `path:["properties","<key>"]`; not exposed by the MCP/official API.

- **`queryCollection` needs a real *view* id, not the `collection_view` block id.** The two are easy to confuse: the block that embeds the table has its own uuid and a `view_ids` array, and only the entries in that array are valid for `collectionViewId`. Passing the block id returns a bare `400 {"name":"ValidationError","debugMessage":"Invalid input."}` with nothing naming the offending field, so it reads like a malformed `loader`/`query` rather than a wrong id. Resolve views first (`syncRecordValues` on the block → `view_ids`), then query with `view_ids[0]`. Rows come back in `recordMap.block`, mixed with other records — filter by `parent_id == <collection_id>` and `alive`.

- **Grouped views need both `query2.group_by` and `format.collection_groups`.** `group_by` holds the property key; `collection_groups` is an array of `{property, value: {type, value}, hidden}` — one entry per distinct group value, plus a catch-all `{property, value: {type}, hidden: False}` for the unset bucket. Group display order follows the option order in the property's schema (for `select`-type group keys).

- **Trashed blocks (`alive=false`) remain fetchable via `syncRecordValues`.** Useful reverse-engineering technique when an API field name is unknown: set up the feature via Notion's UI, then `syncRecordValues` the block to see what field shape Notion persisted. The block stays inspectable even after being trashed. This is how the `conditional_color_rules` schema was discovered.

- **Nested blocks need both a parent-ID chain AND a `listAfter` at every level.** Children with `parent_id=<parent_block_id>` won't render unless they're also `listAfter`-ed into the parent block's own `content`. Pattern for one country → many states:
  1. Create the country block (`parent_id=page_id`), then `listAfter` it into `page.content`
  2. For each state: create with `parent_id=country_block_id`, then `listAfter` it into the country block's `content`

  Skip either listAfter and the block exists in the recordMap but isn't visible in the rendered tree.

- **Rich-text title runs annotate inline.** A `title` property is a list of runs where each run is `[text]` or `[text, annotations]`. Annotations is a list of `[type, ...args]`: `[["b"]]` bold, `[["i"]]` italic, `[["a", url]]` link, `[["c"]]` inline code. Example title with a bold lead-in plus a link: `[["List", [["b"]]], [": "], ["map", [["a", "https://..."]]]]`. Same shape as the file-property `[[filename, [["a", attachment_url]]]]` pattern, just for inline text formatting. Update a single block's title with `saveTransactionsFanout` `command:"set"` on `path:["properties","title"]`.

- **The `url` schema type is accepted by v3.** A collection schema property with `"type": "url"` persists and renders as a clickable link column; the value shape is the same `[[<string>]]` as a text property. (Verified on the RTM import — 252 `Link` values.)

- **A `multi_select` value is a single comma-joined string of option *names*, and renders as separate pills.** Store `[["a,b,c"]]`, not one entry per option. Notion splits on commas and matches each part against the schema's declared options, so **no option name may contain a comma** and every part must be pre-declared as an option or it renders empty. Verified: a 3-topic value rendered as 3 distinct pills.

- **Trashing an inline `collection_view` needs a `listRemove` from the parent's `content`, not just `alive: false`.** Setting the block's `alive: false` moves it to Trash, but Notion keeps rendering it as a ghost table because the block id is still in the host page's `content` array. Also send `{command: "listRemove", path: ["content"], args: {id: <cv_block_id>}}` on the host page. A rollback that only flips `alive` leaves a phantom table on the page until the pointer is removed.

- **Sub-items are a paired self-relation; writing one side auto-syncs the other.** Enabling *Sub-items* in the UI (still the one manual, API-unexposed step) adds **two** relation properties on the same collection — `Parent item` and `Sub-item` — each pointing at the other through its `property` field (the parent side carries `limit: 1`). Writing only the child's `Parent item` relation via `saveTransactionsFanout` auto-populates the parent's `Sub-item` back-reference — verified: after 167 child→parent writes, a parent's `Sub-item` held all 16 of its children with no explicit parent-side write. Discover the opaque 4-char schema keys (e.g. `?YWO`, `bhVo`) by `syncRecordValues` on the collection and filtering `type == "relation"`.

- **A view's sub-item filter mode interacts with its filters.** *"Parents and sub-items"* filters children on their own property values; *"Parents only"* shows children nested under any matching parent regardless of the child's own values. So the mode to pick depends on where the filtered attribute lives: when it lives **only on the parent** (a container tagged `order` whose child items carry no tag), "Parents and sub-items" filters the children out and the parent renders as an empty expandable row — use **"Parents only"** there. When the filter is on a **per-row** value like status (children have their own real statuses), use **"Parents and sub-items"** so each child is judged individually. Rule of thumb: *attribute-on-parent → parents only; per-row value → parents and sub-items.*

When modifying or extending the notion tool's API calls, don't assume standard REST pagination behavior. Always test with real data.

## Related reading

- **[`jamalex/notion-py`](https://github.com/jamalex/notion-py)** — the most complete public Python client for Notion's internal v3 API. Uses `token_v2` cookie auth (same surface as this tool). Wraps blocks, collections, views, and transactions in Python classes; auto-generates row attributes from collection schemas. Its own `CLAUDE.md` is a good architectural reference. **Limitation:** the library is built around older endpoints (`submitTransaction` instead of `saveTransactionsFanout`, `query.group_by` instead of `query2.group_by`) and does NOT cover the post-2022 view-format fields documented above (`conditional_color_rules`, `collection_groups`, `block_color`, schema-level `date_format`, etc.). Use it for the well-trodden parts of v3; fall back to raw HTTP + this quirks file for the bleeding-edge view config.
- **[`Notion MCP server`](https://mcp.notion.com/mcp)** — Notion's official API path (OAuth + REST). Separate surface, separate constraints. None of the quirks here apply there; many of the things this tool does (multi-view DB construction, conditional row colors, bulk teamspace deletion) aren't exposed via the MCP server.
