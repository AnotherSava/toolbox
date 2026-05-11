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

- **`date_format` only respects a fixed enum.** Valid values: missing/empty (renders as "Full date", e.g. "July 4, 2025"), `relative`, `MM/DD/YYYY`, `DD/MM/YYYY`, `YYYY/MM/DD`. Anything else (`ll`, `MMM D, YYYY`, …) is accepted by the API but silently falls back to Full date. For abbreviated-month rendering ("Jul 4, 2025"), store as a text column with the format pre-applied and keep a hidden real-date column for chronological sort.

- **Grouped views need both `query2.group_by` and `format.collection_groups`.** `group_by` holds the property key; `collection_groups` is an array of `{property, value: {type, value}, hidden}` — one entry per distinct group value, plus a catch-all `{property, value: {type}, hidden: False}` for the unset bucket. Group display order follows the option order in the property's schema (for `select`-type group keys).

- **Trashed blocks (`alive=false`) remain fetchable via `syncRecordValues`.** Useful reverse-engineering technique when an API field name is unknown: set up the feature via Notion's UI, then `syncRecordValues` the block to see what field shape Notion persisted. The block stays inspectable even after being trashed. This is how the `conditional_color_rules` schema was discovered.

When modifying or extending the notion tool's API calls, don't assume standard REST pagination behavior. Always test with real data.

## Related reading

- **[`jamalex/notion-py`](https://github.com/jamalex/notion-py)** — the most complete public Python client for Notion's internal v3 API. Uses `token_v2` cookie auth (same surface as this tool). Wraps blocks, collections, views, and transactions in Python classes; auto-generates row attributes from collection schemas. Its own `CLAUDE.md` is a good architectural reference. **Limitation:** the library is built around older endpoints (`submitTransaction` instead of `saveTransactionsFanout`, `query.group_by` instead of `query2.group_by`) and does NOT cover the post-2022 view-format fields documented above (`conditional_color_rules`, `collection_groups`, `block_color`, schema-level `date_format`, etc.). Use it for the well-trodden parts of v3; fall back to raw HTTP + this quirks file for the bleeding-edge view config.
- **[`Notion MCP server`](https://mcp.notion.com/mcp)** — Notion's official API path (OAuth + REST). Separate surface, separate constraints. None of the quirks here apply there; many of the things this tool does (multi-view DB construction, conditional row colors, bulk teamspace deletion) aren't exposed via the MCP server.
