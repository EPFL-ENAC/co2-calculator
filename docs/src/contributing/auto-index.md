# Auto-index frontmatter

`docs/gen_indexes.py` writes the section indexes (`architecture/`,
`backend/`, `frontend/`, `implementation-plans/`) before each build. Add
YAML frontmatter to a plan or a page to put it in the correct group.

## Schema

```yaml
---
status: delivered # delivered | in-progress | abandoned
issue: 310-b
last_updated: 2026-05-05
summary: One-line description.
---
```

All keys are optional. A file without `status` goes under
**Uncategorized**. A file without `title` uses its first `# H1` heading,
then its filename. An unknown `status` stops the build.

## Build or preview

From `docs/`, build the site the way CI does:

```bash
sh build.sh
```

For a live preview on <http://127.0.0.1:8001>, run `make serve-docs`.
The indexes are written once at start. Restart the preview to update
them.

## Where output lands

The script writes `_index.md` next to the section pages, in `src/`.
These files are gitignored. Open `site/<section>/_index.html` to see
the result.
