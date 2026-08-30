# Code review — PR #2533 `fix/2530-unforgeable-audit-ip`

**Reviewed:** `8f9c8d594` against `origin/dev` (`6bb8d284a`) · 2026-08-30
**Issue:** #2530 (Part 1) · **Superseded in part by:** #2542 `wip/2530-real-client-ip-regate`

## Verdict: SHIP WITH FIXES

The nine-line code change is right, and it is _more_ right than the PR claims.
Deleting the `X-Forwarded-For` branch closes a real forgery hole with no new
abstraction, all three callers are unaffected, and the test swap is a clean
straight trade. Nothing in the code needs to change.

What must change before merge is everything written _around_ it:

1. **R1** — the docstring shipped in this diff asserts something now known to
   be false, about the security property the function exists to provide.
2. **R2** — `make lint` is **red** on this branch head. The PR body says it is
   green.
3. **R3** — the plan file repeats the same false premise in four places, and
   the plan outlives the PR.

Plus a merge-order decision the maintainer should make explicitly — see the
last section.

---

## R1 (required) — the docstring in the diff is false

`request_context.py:22-24`, added by commit `8f9c8d594` (whose subject is
"correct the ip-resolution docstring"):

> `scope["client"]` is unforgeable under either deployment regime. Today it is
> the raw TCP peer — **and since FORWARDED_ALLOW_IPS is unset here, that is the
> router pod, not the end user.** If FORWARDED_ALLOW_IPS is ever configured,
> uvicorn resolves it from the _right_ of the proxy chain instead.

Both halves of that are wrong, and this can be shown from the vendored uvicorn
source without access to the ops repo:

| Claim                                                                                       | Reality                                                                                                                                                                                                |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "the deployment runs uvicorn without `--proxy-headers`" (PR body), so headers are untrusted | `uvicorn/config.py:220` — `proxy_headers: bool = True`. There is no flag to set; it is on by default.                                                                                                  |
| `FORWARDED_ALLOW_IPS` is "unset here" so the peer is the router pod                         | `uvicorn/config.py:355-358` reads it **from the environment**, not from a CLI flag or `backend/.env`. Per #2542 it is set in all three `openshift-app-config` overlays (`10.20.0.0/16,10.98.42.0/24`). |

So `request.client.host` has already been the **resolved end-user address** in
dev, stage and prod. The function was not trading precision for
unforgeability; it was throwing away a good value and reading a forgeable one.
That makes this PR strictly better than it claims — and the code comment as
written will send the next reader down a wrong path on a security question.

The irony is that the commit before this one had it right: the text it replaced
said "resolved against FORWARDED_ALLOW_IPS by walking the chain from the right,
so it cannot be forged." That is the correct description. The "correction"
introduced the error.

It also now **contradicts a comment in the same repo**. `auth.py:601-604`, on
`GET /v1/session` — which this very docstring cites as documenting "the same
reasoning" — says:

```
# scope["client"], not the X-Forwarded-For header: uvicorn resolves
# it against FORWARDED_ALLOW_IPS by walking the chain from the
# right, so a client-supplied header cannot forge it.
```

Two comments, same mechanism, opposite conclusions. Restore the earlier
wording.

---

## R2 (required) — `make lint` fails on this branch

```
make -C docs lint FILES="."
[warn] src/implementation-plans/2530-rate-limiting-router-and-per-user.md
[warn] Code style issues found in the above file.
make[1]: *** [lint] Error 1
```

Reproduced from a clean tree at `8f9c8d594`. Prettier wants table-column
alignment on the two tables and `_only because_` instead of `*only because*` —
12 lines, no content change. The offending rows were added by the last commit,
which is itself titled as a fix for a prettier violation. `make type-check`
passes.

The PR body's Checks block says "`make lint` — backend clean". Backend ruff is
indeed clean; the docs half is not, and the root target is what CI runs. Run
`make format` and amend.

---

## R3 (required) — the plan doc carries the same false premise

`docs/src/implementation-plans/2530-rate-limiting-router-and-per-user.md`, the
artefact the next person will grep long after the PR body is forgotten:

| Line  | Says                                                                                                        | Status per #2542                                                                                                                                                                                   |
| ----- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 41    | heading: "Known consequence — recorded IP is now the router pod"                                            | false — it is the end-user address                                                                                                                                                                 |
| 43-45 | "`FORWARDED_ALLOW_IPS` is set nowhere in this repo … the peer uvicorn sees is **the OpenShift router pod**" | false — set in all three overlays; and the repo is the wrong place to look                                                                                                                         |
| 55-58 | restoring real IPs needs `set-forwarded-headers: replace` **plus** `FORWARDED_ALLOW_IPS`                    | false, and actively harmful — #2542 shows with source proof that `replace` makes every audit IP the AVI load balancer's address, by both branches of `get_trusted_client_address`                  |
| 63    | the `/internal` gate "holds _only because_ uvicorn currently trusts no proxy headers"                       | false — it does not hold **at all** today. `10.20.0.0/16` is the whole pod overlay subnet, so any workload in the cluster is a trusted proxy and can set `scope["client"]` to a live pod's address |
| 181   | "record the router pod IP until then"                                                                       | false, same premise                                                                                                                                                                                |

Line 63 is the one that matters beyond documentation hygiene: as written, the
PR tells a reader that `POST /api/internal/*` is safe today and would only
become exposed by a future ops change. It is exposed **now**. Whoever reads
this plan without also reading #2542 will not know to prioritise it.

The "coarse-but-true IP beats plausible-but-forged" framing in the PR body is
sound reasoning that simply does not apply — there is no coarseness and no
granularity loss to accept. Drop that section rather than rewriting it.

---

## Callers (question 1) — all three correct, no behaviour change

| Call site                     | Use                                    |
| ----------------------------- | -------------------------------------- |
| `auth.py:190`                 | `"ip_address"` in the login audit dict |
| `data_sync.py:889`, `:988`    | same, sync audit dicts                 |
| `carbon_report_module.py:234` | same, report audit dict                |

All three consume the return value identically: a `str` into
`AuditLog.ip_address`, which is a plain `str` Field (`models/audit.py:92`) with
no length or format constraint. The signature, return type and `"unknown"`
sentinel are unchanged, so nothing downstream can break — only the recorded
value changes, and per R1 it changes for the better.

Keeping the `"unknown"` sentinel is the right call and the PR's justification
holds: raising inside audit-context construction would convert a missing peer
into a failed user request, which is the opposite of what an audit trail is
for. It logs a warning, so it is not a silent fallback.

## `connectors.py` / `internal.py` (question 2) — correctly left alone

Both read `request.client.host` directly and were already unforgeable, so
neither needed the fix.

- `connectors.py:103,137,191` — audit-adjacent, but they fall back to `None`
  rather than `"unknown"`, so routing them through the helper would be a
  behaviour change dressed as a refactor. Leaving them is right.
- `internal.py:62-63` — a `403` gate, not an audit field. Different semantics,
  correctly out of scope for a helper change.

The **scoping** decision is right; the **characterisation** of `internal.py` is
not — see R3, line 63. This PR's body and plan both describe the `/internal`
exposure as a future risk gated behind an ops change. #2542 establishes it is
live. That belongs in the PR body, not only in the superseding branch, because
if #2533 merges alone the record left in `dev` says the door is shut.

## Tests (question 3) — yes, coverage preserved plus the new guarantee

The old `test_extract_ip_address_from_forwarded_for` asserted three things: XFF
is read, the comma-list is split, the first element is taken and stripped. All
three describe behaviour this PR **deletes**, so there is nothing to preserve —
retaining any of it would pin the bug.

What the old test's _scenario_ covered (XFF present, no peer) is still covered:
`test_extract_ip_address_returns_unknown_when_no_client` was extended with a
forged header, so the no-peer path is now pinned as "must not fall back to the
header" rather than just "returns unknown". That is a strict gain. The
replacement `test_extract_ip_address_ignores_forged_forwarded_for` adds the
case that never existed — forged header _and_ a real peer, peer wins.

Both fail on `dev` as claimed (on `dev` the helper returns `"1.2.3.4"` in each,
against expected `"9.8.7.6"` and `"unknown"`).

`27 passed` in `tests/unit/utils/test_audit_helpers.py`.

**One variant left unpinned:** `test_extract_ip_address_returns_unknown_when_client_host_empty`
(peer present, `host` falsy) still uses `headers = {}`. Add the forged header
there too — it is the last path that could regress into reading the header, and
it is a one-line change.

---

## Merge order — needs an explicit decision

`request_context.py` is changed **identically** in #2542
(`wip/2530-real-client-ip-regate`), which also carries the `/internal` re-gate,
the widened boot guard and the `set-forwarded-headers` rejection. The
maintainer's decision 6 on this PR was: _"Both halves ship together or neither
ships."_ Merging #2533 alone ships one half, and ships a `dev` whose comments
and plan say the other half is not yet needed.

Two coherent options:

- **Close #2533 in favour of #2542.** Cleanest. R1/R3 are already fixed there
  (#2542's body corrects both findings), and the two halves land together as
  asked. The audit-IP fix loses nothing by riding along.
- **Merge #2533 first**, with R1–R3 fixed, then rebase #2542 onto it. Only
  worth it if landing the audit-IP fix a day earlier matters; note that on its
  own it changes nothing operationally, since per R1 the value it now records
  was already the correct one.

Either way, do not merge this PR with the docstring and plan as they stand.

---

## Checks run

```
uv run pytest tests/unit/utils/test_audit_helpers.py -q
→ 27 passed

make lint        → ❌ prettier, docs/src/implementation-plans/2530-*.md (R2)
make type-check  → ✅ ty (backend) + vue-tsc (frontend)
```

Frontend checks needed `npm ci` + `npx quasar prepare` in this worktree; the
diff is backend + docs only.
