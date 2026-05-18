# Documentation Standards

Write technical docs a reader understands in one ~10-minute sitting. This extends the summary in [Global Conventions → Documentation Standards](07-global-conventions.md#documentation-standards), and applies to every README, how-to, runbook, ADR, troubleshooting note, and proposal.

## The 10-Minute Rule

- Title under 60 characters, capitalized, no trailing punctuation. Blank line, then a context paragraph stating what the doc covers and why it matters.
- Active voice; imperative mood for instructions ("Run the command", not "The command is run").
- Sentences under 20 words. Wrap prose at ~72 characters.
- No filler — drop "simply", "basically", "clearly". Keep terminology and capitalization consistent.
- Commands and snippets in code blocks, never inline prose. Put examples after the concept they illustrate.
- Numbered lists for ordered steps, bullets otherwise. A header every 2–3 paragraphs; a visual break (table, list, code) every ~20 lines.
- For long docs, add a TL;DR or per-section summary. End every doc with a clear takeaway or next action.
- The doc must make sense read in isolation, and must not duplicate content that lives in another `.md` — cross-link instead.
- Update documentation in the same PR as the code it describes.

## Length targets

| Document type        | Target length |
| -------------------- | ------------- |
| README / how-to      | 30–60 lines   |
| ADR / design doc     | 40–80 lines   |
| Troubleshooting note | 25–50 lines   |
| Technical proposal   | 60–120 lines  |
| Whole document       | ≤ ~800 words  |

A multi-procedure operational runbook may exceed these. When it must, say so and offer to split it, rather than silently overrunning.

## MkDocs conventions (this repo)

These follow from how the docs site and the Prettier hook actually behave:

- **Use blockquote callouts, not `!!!` admonitions.** The repo Prettier hook strips the 4-space indentation MkDocs admonitions require and silently breaks their rendering. Write callouts as a blockquote with a bold lead-in:
  ```markdown
  > **⚠️ Warning.** One sentence, one line, bold lead-in.
  ```
- **Add every new page to `mkdocs.yml` `nav:`.** A page reachable only by cross-link is orphaned — it never appears in the sidebar. Place it near its topical neighbours.
- **No agent-only tooling in human-facing docs.** Use plain `git` / `gh`; never `rtk` or other local wrappers the reader will not have installed.
- **Critical operational docs:** keep commands in the runbook and policy in the policy doc — cross-link, do not restate. Density may favour inline prose over strict 72-character wrapping when the doc is operational and correctness-critical.

## Before you commit

Run both, from `docs/`:

```bash
npx prettier --check <file>.md
uv run mkdocs build --strict
```

`--strict` promotes warnings to errors. A doc is not done until both pass.

## Final check

Confirm the doc explains **what and why**, not only how; reads in ~10 minutes; ends with a clear action; stands alone; and duplicates nothing in another `.md`.
