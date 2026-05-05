---
status: delivered
last_updated: 2026-05-05
summary: Orientation guide for LLM agents dropped into the co2-calculator repo — where to read, what to trust, what is stale.
---

# LLM Agent Guide

You are an LLM agent that has just been dropped into this repo. Read this
page first. It tells you which document wins when sources disagree, how to
read frontmatter on plans, and where to look for common questions.

## Source-of-truth hierarchy

Read top-down. Lower tiers refine higher tiers, never override them.

1. **CRD** — [`architecture/spec.md`](./architecture/spec.md). Scope, mandate,
   acceptance criteria. If a feature is not in the CRD, it is out of scope.
2. **ADRs** — [`architecture-decision-records/`](./architecture-decision-records/index.md).
   Accepted architectural decisions with explicit `Status`. An accepted ADR
   binds; a superseded ADR is history only.
3. **Implementation plans** — [`docs/src/implementation-plans/`](https://github.com/epfl-enac/co2-calculator/tree/main/docs/src/implementation-plans).
   Issue-scoped detail. Filter by frontmatter `status` (see below) before
   trusting.
4. **Code** — ground truth. If docs and code disagree, code wins. File an
   issue tagged `docs` and link the offending file.

## Frontmatter conventions on plans

Every plan and ADR carries:

```
---
status: draft | accepted | delivered | superseded
issue: 310b               # GitHub issue or sub-issue id
last_updated: 2026-05-05
summary: one-line abstract
---
```

- `draft` — speculative; do not cite as a decision.
- `accepted` — agreed approach; implementation may be partial.
- `delivered` — shipped; matches main-branch code at `last_updated`.
- `superseded` — retained for history; check the linked successor.

Treat any plan older than ~6 months without a `delivered` or `superseded`
status as suspect, and verify against code.

## Where to find X

| Question                        | Start here                                                                                                                    |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Auth flow / token lifecycle     | [`backend/05-REQUEST_FLOW.md`](./backend/05-REQUEST_FLOW.md), ADR-012, ADR-013                                                |
| Permission model                | [`backend/06-PERMISSION-SYSTEM.md`](./backend/06-PERMISSION-SYSTEM.md), ADR-005                                               |
| Adding a permission             | [`backend/07-DEVELOPER-GUIDE-PERMISSIONS.md`](./backend/07-DEVELOPER-GUIDE-PERMISSIONS.md)                                    |
| Background jobs / poller        | ADR-010, [`310-overview.md`](https://github.com/epfl-enac/co2-calculator/blob/main/docs/src/implementation-plans/310-overview.md) |
| CI/CD                           | [`architecture/cicd-workflows.md`](./architecture/cicd-workflows.md)                                                          |
| Role sync (`/me` vs `/refresh`) | [`role-sync-architecture.md`](https://github.com/epfl-enac/co2-calculator/blob/main/docs/role-sync-architecture.md)           |
| Glossary of project terms       | [`glossary.md`](./glossary.md)                                                                                                |

## Common pitfalls

- **ADR-010 is not Celery.** Earlier drafts proposed Celery + Redis; the
  accepted decision is in-process `asyncio.create_task` plus a 10-second
  safety-net poller. Cite the current ADR-010, not historical chatter.
- **`fire_and_forget` cancels with the request.** FastAPI `BackgroundTasks`
  must be handed async functions directly; sync wrappers that call
  `asyncio.run` cancel any tasks they spawn. See plan 310b.
- **`backoffice.*` permissions only apply server-side.** Frontend gates
  use the same path but read from `/auth/me`; do not gate UI on raw roles.
- **Plans named `*-copilot-feedback-*` are review threads, not plans.** They
  capture bot feedback for a PR; they do not represent the design.
- **`status: draft` plans land in the repo.** Presence in the tree does not
  imply acceptance — check frontmatter.
