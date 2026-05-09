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

When modifying or extending the notion tool's API calls, don't assume standard REST pagination behavior. Always test with real data.
