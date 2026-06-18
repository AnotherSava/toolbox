# Notion examples

Snapshots of one-off workflows. Not polished CLIs — copy and adapt for similar jobs.

If you need pure image optimization (no Notion glue), use `image-opt` instead.

| File | What it did | When to use |
|---|---|---|
| `plain_to_collection.py` | Turn a hand-rolled list (alternating text + image blocks) into a proper Notion gallery sub-collection. Mutates the page in place. | If you have similar legacy pages and want to convert them to databases. |
| `extract_images.py` | Pull every image off a Notion page and save WebP-optimized copies named `image_NN.webp` in page order. Read-only. | When you want the images for an external workflow without touching the source page. |
| `tripster_translate.py` | Translate a Russian "Country: city1, city2; …" flat-text Notion page into an English bulleted list (alphabetized; optional nesting by state/province for federal-subdivision countries). Creates a new sibling page. | When migrating a hand-written travel/list page to a normalized form. |
| `tripster_replace.py` | Same content `tripster_translate.py` builds, but applied in-place to the target page (preserves URL and inbound links) — trashes the page's old content blocks first. | After you've vetted the translated draft and want to promote it onto the canonical page. |

The tripster scripts read their personal data (page ID, map URL, country/city lists) from a gitignored `tools/notion/config/tripster_data.py`. Expected shape:

```python
PAGE_ID = "<32-char-or-dashed-uuid>"
MAP_URL = "https://..."
COUNTRIES = [
    ("Country", ["City A", "City B"]),                          # flat
    ("Country", [("State", ["City A"]), ("State 2", [...])]),  # nested by subdivision
]
```

Both scripts depend on `notion_tools` (the installed package) and `image_opt`. Run from the project root:

```
python tools/notion/docs/examples/extract_images.py <page-url-or-id>
```

For Notion API gotchas relevant to these scripts (image proxy, attachment URLs, upload flow, recovering trashed blocks via `getActivityLog`), see `../learnings/notion-api-quirks.md`.
