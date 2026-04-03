# Notion Internal API Quirks

Notion internal API (token_v2 cookie auth, /api/v3/ endpoints) has several quirks discovered during development:

- **Search API has a hard 1000-result limit.** Pagination tokens cycle and return duplicates rather than advancing. Workaround: delete results in batches (fetch 1000, delete, re-fetch until empty).

- **`getTeams` response format.** Teamspaces are nested under `recordMap.team`, not returned as a flat list.

- **Archived vs. trashed pages are fundamentally different.** Trash is global and searchable via `isDeletedOnly` filter. Archives are per-parent page with no global "all archived" view — there's no API to list all archived pages across a workspace.

When modifying or extending the notion tool's API calls, don't assume standard REST pagination behavior. Always test with real data.
