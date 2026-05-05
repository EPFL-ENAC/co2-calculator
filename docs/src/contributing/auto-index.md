# Auto-index frontmatter

Section indexes (`architecture/`, `backend/`, `frontend/`, `implementation-plans/`)
are generated at build time by `docs/gen_indexes.py` (run via the
`mkdocs-gen-files` plugin). Add YAML frontmatter to any plan or page so it
appears in the right group with rich metadata.

## Schema

```yaml
---
status: delivered  # delivered | in-progress | abandoned
issue: 310-b
last_updated: 2026-05-05
summary: One-line description.
---
```

All keys are optional. Files missing `status` land under **Uncategorized**;
files missing `title` fall back to the first `# H1` heading, then the
filename stem.

## Trigger a rebuild

Local preview:

```bash
cd docs
uv run mkdocs serve
```

The `gen-files` plugin re-runs on every reload. CI builds invoke
`uv run mkdocs build --strict` — `--strict` promotes warnings to errors,
so missing frontmatter must still produce a valid page (the script
guarantees this by emitting an "Uncategorized" group).

## Where output lands

Each `INDEX.md` is virtual (written via `mkdocs_gen_files.open()`), so
it never appears on disk. Run `mkdocs build` and open
`site/<section>/INDEX.html` to inspect output.
