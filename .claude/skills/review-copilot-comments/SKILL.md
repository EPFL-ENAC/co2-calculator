---
name: review-copilot-comments
description: Fetch automated bot review comments (Copilot, github-actions, GitHub Advanced Security / CodeQL) for the current branch's PR, then produce a prioritized action checklist that filters out nitpicks and groups substantive feedback by file.
---

# Review automated bot PR comments

Run this when the user wants to triage automated review on the current branch's PR — Copilot summary reviews, `github-actions[bot]` checks, and `github-advanced-security[bot]` CodeQL findings.

## Step 1 — Fetch the comments

Run the bundled script via Bash:

```
bash "$(git rev-parse --show-toplevel)/.claude/skills/review-copilot-comments/retrieve-copilot-pr.sh"
```

The script writes raw feedback to `docs/code-review/<issue>-copilot-feedback-<desc>.md` and prints `OUTPUT_FILE=<path>` as its final stdout line. Capture that path.

These review artifacts live in `docs/code-review/` (not `docs/src/implementation-plans/`) because they have a different lifecycle: implementation plans are canonical and append-only (one per issue, governed by `.github/instructions/co2-calculator-rules.md.instructions.md`), while bot-feedback files are transient and get overwritten on every re-run (see "Re-runs" below).

If the script exits non-zero (no PR for branch, no issue ID in branch name), surface its error to the user and stop — don't try to recover.

## Step 2 — Read the file

Read the file at `OUTPUT_FILE`. It contains a `## Raw Feedback` section with summary reviews and inline comments from Copilot, `github-actions[bot]`, and `github-advanced-security[bot]`. The author login is annotated on each entry — use it to weigh comments (Copilot tends to mix nitpicks and real bugs; GHAS items are CodeQL security alerts and rarely nitpicks).

## Step 3 — Verify against the code

Do not trust the bot's claims — this includes GHAS, which can flag false positives on intentional patterns. For each non-nitpick comment, open the cited file at the referenced line(s) with the Read tool and confirm what the code actually does. Read enough surrounding context to judge — usually the whole function plus its callers. Where a comment depends on cross-file behavior (e.g. "this repo method commits, the endpoint also commits"), read both sides.

For each verified comment, assign one verdict:

- **valid** — the claim holds; the fix is needed
- **partial** — the symptom is real but the diagnosis or suggested fix is off; needs a different fix
- **wrong** — the claim doesn't hold against the current code (already handled, misread, or based on a stale assumption); drop it
- **already-fixed** — addressed in a later commit on this branch; drop it

Drop **wrong** and **already-fixed** items. Keep **valid** and **partial** for triage.

Filter out nitpicks before verification to save effort: trivial naming, whitespace, lint-level polish, doc-comment wording.

## Step 4 — Cluster and form recommendations

Cluster overlapping comments by **root cause**, not by file or by bot comment ID. One bullet per root cause, not one per comment. Common cluster patterns:

- Multiple comments on the same function describing different symptoms of one bug → one bullet, fix the function once.
- Repeated filename/style remarks across sibling files → one bullet covering the rename set.
- "Same issue as the X variant" comments → fold into the parent item.

For each cluster, write a **verdict + fix recommendation**, not a paraphrase of the comment. The bullet should answer:

1. What's the underlying defect (one sentence, in your words).
2. What's the concrete fix — function, approach, and any call-site updates.
3. Anything the bot got wrong about it (when verdict is partial), so the implementer doesn't blindly apply the suggested patch.

**Anti-patterns to avoid:**

- Restating the bot's comment verbatim or near-verbatim.
- Listing one bullet per bot comment when several share a root cause.
- Hedging ("consider doing X") when verification gave you a definite answer — say "do X" or "skip; reason."
- Including any item you didn't verify against the code.

## Step 5 — Append the checklist

Append (do not overwrite) a new section to the same file using the Edit tool, immediately after the `## Raw Feedback` block. Prioritize: critical correctness/security first, then performance, then maintainability. Format:

```markdown
---

## Action Items

### Critical: logic, security, correctness
- [ ] **<file path>** — <one-sentence defect>. Fix: <concrete change, function/lines/approach>. <Optional: note on what the bot got wrong.>

### Performance
- [ ] **<file path>** — <defect>. Fix: <change>.

### Maintainability / refactoring
- [ ] **<file path>** — <defect>. Fix: <change>.
```

Omit any section that has no items rather than leaving an empty header. If everything verified to wrong/nitpick, write a single line under `## Action Items`: `_No substantive items after verification — all comments were nitpicks, already addressed, or did not hold against the code._`

## Step 6 — Report

Tell the user the output path and a one-line summary of the triage (e.g., "3 critical, 1 perf, 0 refactor; 2 bot comments dropped as wrong/already-fixed"). Do not paste the checklist into chat — the file is the deliverable.

## Re-runs

The script overwrites the file each time. If the user re-runs after partially resolving items, prior `## Action Items` content will be lost — that's intentional, since fresh raw feedback should be re-triaged. If the user explicitly wants to preserve in-progress checkboxes, read the existing file *before* running the script, remember the checkbox states, and merge them into the new triage in step 4.
