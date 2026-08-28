---
status: delivered
issue: 2342
last_updated: 2026-08-25
summary: Move the portable half of guardrails.md into the shared it4r-agent-kit repo, vendored here as a plain file (not a submodule), leaving guardrails.md as the co2-specific delta.
---

# 2342 — Extract portable engineering rules into `it4r-agent-kit`

## Problem

`docs/src/contributing/guardrails.md` (147 lines) mixed two kinds of rule:

- **Portable** (~110 lines) — backend is the source of truth,
  `route → service → repo` with the commit in the route, no silent fallbacks,
  the frontend never checks roles, no backward-compat paths, function/component
  size limits, no type suppressions, no defensive programming.
- **co2-specific** (~37 lines) — the 310-series pipeline plans, `make ci`,
  `make db-revision`, `fix/pipeline-debug`, the 80 ms / 400 ms budget with its
  4× dev-DB factor, "while the lead is away".

Other IT4R projects had no access to the portable half except by copying it —
and two rulebooks drift, which is the failure `guardrails.md` itself warns
about.

## What shipped

1. **[`EPFL-ENAC/it4r-agent-kit`](https://github.com/EPFL-ENAC/it4r-agent-kit)**
   (public, MIT) now holds the portable rules in `AGENTS.md`, plus two skills
   that were project-agnostic all along: `plan-conventions` (extracted from
   this repo's `llm-agent-guide.md` and the "before you code" section) and
   `review-copilot-comments` (moved from `.claude/skills/`). It is both a
   Claude Code plugin marketplace and a submodule-able skill.
2. **Vendored here** as a plain file, `docs/src/contributing/it4r-rules.md`,
   imported by `CLAUDE.md` ahead of `guardrails.md`. The rules stay always-on,
   exactly as before — no per-developer install step. `make sync-agent-rules`
   re-pulls it and stamps the upstream commit in the header, so staleness is
   visible in the diff.
3. **`guardrails.md` shrank to 103 lines**: a "Two layers" header pointing at
   the kit, then only what is specific to this repo. Same path, same section
   headings, so `.github/instructions/co2-calculator-rules.md.instructions.md`
   (a symlink) and the `§ Workflow` deep links from ADR-014 keep resolving.
   Copilot reads instructions files but not Claude's `@import`, so a second
   symlink — `it4r-agent-kit-rules.md.instructions.md` → the kit's `AGENTS.md` —
   gives it the shared rules too. Without it, keeping the first symlink pointing
   at a file that lost 44 lines would have silently halved what Copilot sees.
4. **Dropped the duplicate `review-copilot-comments` skill** — it now lives in
   the kit, and the task skills are delivered by the plugin. Added a provenance
   header to `.claude/skills/owasp-security/SKILL.md`.

## Decisions

- **Vendored file, not plugin-only, and not a submodule.** The plugin is
  per-developer opt-in; a contributor who skipped it would have silently lost
  every architecture invariant, so the rules have to be committed here. A
  submodule would have done that too, but the maintainers don't want submodules
  in this repo — a vendored file gives the same properties (in-repo, always-on,
  readable by Copilot, no install step) with `git diff` as the drift signal.
- **Rules are vendored; skills are not.** Rules must apply whether or not you
  opted in, so they live in the repo. The task skills (`plan-conventions`,
  `review-copilot-comments`) are invoked deliberately, so the plugin is the
  right delivery and a second in-repo copy is just drift.
- **The kit is public.** Every line of it already lived in this public repo, so
  publishing leaked nothing, and a public repo cannot carry a private submodule.
- **`owasp-security` stayed put.** It is a vendored copy of
  [`agamm/claude-code-owasp`](https://github.com/agamm/claude-code-owasp) (MIT),
  not our work — the kit links upstream instead of re-vendoring it.

## Follow-ups

- `review-copilot-comments` is now plugin-only in this repo. Anyone who wants it
  runs `claude plugin marketplace add EPFL-ENAC/it4r-agent-kit` then
  `claude plugin install it4r-agent-kit`; the `/review-copilot-comments` steps in
  the 310-series plans assume it is installed.
- `owasp-security` has diverged from upstream in both directions (see the
  provenance header). Reconciling it is a merge, not a pull — worth doing, not
  done here.
