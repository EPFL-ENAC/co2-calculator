---
name: review-copilot-comments
description: Fetch Copilot/github-actions review comments for the current branch's PR, then produce a prioritized action checklist that filters out nitpicks and groups substantive feedback by file.
---

# Review Copilot PR comments

Run this when the user wants to triage Copilot's automated review on the current branch's PR.

## Step 1 — Fetch the comments

Run the bundled script via Bash:

```
bash "$(git rev-parse --show-toplevel)/.claude/skills/review-copilot-comments/retrieve-copilot-pr.sh"
```

The script writes raw feedback to `docs/implementation-plans/<issue>-copilot-feedback-<desc>.md` and prints `OUTPUT_FILE=<path>` as its final stdout line. Capture that path.

If the script exits non-zero (no PR for branch, no issue ID in branch name), surface its error to the user and stop — don't try to recover.

## Step 2 — Read the file

Read the file at `OUTPUT_FILE`. It contains a `## Raw Feedback` section with summary reviews and inline comments from Copilot/github-actions.

## Step 3 — Triage

Apply this rubric to the raw feedback:

- **Filter out nitpicks**: trivial naming suggestions that don't affect clarity, whitespace, basic linting-level remarks, doc-comment polish.
- **Keep substantive items**: logic errors, security issues, performance bottlenecks, concurrency or correctness bugs, architectural inconsistencies, missing error handling at real boundaries.
- **Group by file**: each item references the file it applies to.
- **Prioritize**: critical correctness/security first, then performance, then maintainability.

## Step 4 — Append the checklist

Append (do not overwrite) a new section to the same file using the Edit tool, immediately after the `## Raw Feedback` block. Format:

```markdown
---

## Action Items

### Critical: logic, security, correctness
- [ ] **<file path>**: <what's wrong and why it matters>

### Performance
- [ ] **<file path>**: <suggested improvement>

### Maintainability / refactoring
- [ ] **<file path>**: <structural suggestion worth doing>
```

Omit any section that has no items rather than leaving an empty header. If everything is a nitpick, write a single line under `## Action Items`: `_No substantive items — all comments were nitpicks or already addressed._`

## Step 5 — Report

Tell the user the output path and a one-line summary of the triage (e.g., "3 critical, 1 perf, 0 refactor"). Do not paste the checklist into chat — the file is the deliverable.

## Re-runs

The script overwrites the file each time. If the user re-runs after partially resolving items, prior `## Action Items` content will be lost — that's intentional, since fresh raw feedback should be re-triaged. If the user explicitly wants to preserve in-progress checkboxes, read the existing file *before* running the script, remember the checkbox states, and merge them into the new triage in step 4.
