# Notion examples

Snapshots of one-off workflows. Not polished CLIs — copy and adapt for similar jobs.

If you need pure image optimization (no Notion glue), use `image-opt` instead.

| File | What it did | When to use |
|---|---|---|
| `plain_to_collection.py` | Turn a hand-rolled list (alternating text + image blocks) into a proper Notion gallery sub-collection. Mutates the page in place. | If you have similar legacy pages and want to convert them to databases. |
| `extract_images.py` | Pull every image off a Notion page and save WebP-optimized copies named `image_NN.webp` in page order. Read-only. | When you want the images for an external workflow without touching the source page. |

Both scripts depend on `notion_tools` (the installed package) and `image_opt`. Run from the project root:

```
python tools/notion/docs/examples/extract_images.py <page-url-or-id>
```

For Notion API gotchas relevant to these scripts (image proxy, attachment URLs, upload flow, recovering trashed blocks via `getActivityLog`), see `../learnings/notion-api-quirks.md`.
