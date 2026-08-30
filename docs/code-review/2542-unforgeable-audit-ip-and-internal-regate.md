# Code review — PR #2542, `fix(security): unforgeable audit ip, and re-gate /internal on a shared secret`

- **Branch**: `wip/2530-real-client-ip-regate` @ `18da34363`
- **Base**: `origin/dev`
- **Issue**: #2530 (Part 1)
- **Reviewed**: 2026-08-30
- **Verdict**: **SHIP WITH FIXES** — one must-fix (an unauthenticated 500 on the
  new gate) and three should-fixes (a test that does not test what it is named
  for, and two overclaims in the PR narrative).

Everything below was verified against source — uvicorn 0.52.4 in
`backend/.venv`, the `openshift-app-config` overlays, `helm/templates/routes.yaml`
— or by running the tests. Nothing here is taken from the PR description.

---

## 1. Is the exposure claim true?

**Yes. Every link in the chain holds, and the live in-cluster exposure is real.**

The PR asserts three things. Each was checked independently.

### 1.1 `FORWARDED_ALLOW_IPS` is already set, in all three overlays — CONFIRMED

| Overlay | File                                                    | Line | Value                        |
| ------- | ------------------------------------------------------- | ---- | ---------------------------- |
| dev     | `epfl/co2-calculator/overlays/dev/kustomization.yaml`   | 209  | `10.20.0.0/16,10.98.42.0/24` |
| stage   | `epfl/co2-calculator/overlays/stage/kustomization.yaml` | 280  | `10.20.0.0/16,10.98.42.0/24` |
| prod    | `epfl/co2-calculator/overlays/prod/kustomization.yaml`  | 263  | `10.20.0.0/16,10.98.42.0/24` |

The ops comment above each is verbatim what the PR quotes:

> `10.20.0.0/16` is the overlay subnet for pods (which includes the haproxies);
> `10.98.42.0/24` covers our AVI loadbalancers.

Also confirmed: `networkPolicies` is commented out in the prod overlay
(`prod/kustomization.yaml:319-320`), so nothing at the network layer narrows
this.

### 1.2 uvicorn's `proxy_headers` defaults to `True` — CONFIRMED

From `backend/.venv/.../uvicorn/config.py`:

- `:220` — `proxy_headers: bool = True`
- `:357` — `self.forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")`,
  reached only when the constructor arg is `None` (i.e. when `--forwarded-allow-ips`
  is not passed)
- `:527` — `if self.proxy_headers: self.loaded_app = ProxyHeadersMiddleware(self.loaded_app, trusted_hosts=self.forwarded_allow_ips)`

And `uvicorn/main.py:225-227` — the CLI flag is `--proxy-headers/--no-proxy-headers,
default=True`. So the Dockerfile's newly added `--proxy-headers` is genuinely a
no-op, exactly as the PR says. Keeping it as documentation is fine; the comment
above it correctly points at the real knob.

### 1.3 `10.20.0.0/16` lets any in-cluster workload spoof `request.client.host` — CONFIRMED

From `uvicorn/middleware/proxy_headers.py`:

```python
if client_host in self.trusted_hosts:      # attacker pod ∈ 10.20.0.0/16 → True
    ...
    host, port = self.trusted_hosts.get_trusted_client_address(x_forwarded_for)
    if host:
        scope["client"] = (host, port)
```

and, in `get_trusted_client_address`:

```python
for host_port in reversed(x_forwarded_for_hosts):
    host, port = _parse_host_port(host_port)
    if host not in self:
        return host, port
# All hosts are trusted meaning that the client was also a trusted proxy
return _parse_host_port(x_forwarded_for_hosts[0])
```

Walk it with the deployed CIDRs. An attacker pod at `10.20.9.9` connects
directly to a co2 pod on `:8000` with `X-Forwarded-For: 10.20.4.4` (a live pod
address from the `pods` table):

1. TCP peer `10.20.9.9` ∈ `10.20.0.0/16` → treated as a **trusted proxy**, so
   its `X-Forwarded-For` is honoured.
2. Reverse walk: `10.20.4.4` ∈ `10.20.0.0/16` → trusted → loop exhausts.
3. Fallback returns the **leftmost** element — `10.20.4.4`, which the attacker
   wrote.
4. `scope["client"]` becomes `("10.20.4.4", 0)`; `_caller_is_live_pod` is
   satisfied; the cache is cleared.

**This path is unconditional.** It needs no Route, no AVI, and no assumption
about the LB — only a pod in the cluster. The PR's headline claim is correct,
and this was live in dev, stage and prod.

The test `test_a_caller_inside_the_pod_subnet_can_still_choose_its_own_ip`
pins exactly this, through the real middleware with the real CIDRs. Good test.

### 1.4 One thing the PR gets right but understates, and one it misses

**Right, and worth keeping:** `/internal` is also reachable from outside the
cluster. `helm/templates/routes.yaml` gives the backend Route `path: '/api'`
with `haproxy.router.openshift.io/rewrite-target: /`, and an OpenShift Route
`path` is a _prefix_ match — so `POST /api/internal/cache/taxonomy/clear` is
rewritten to `/internal/cache/taxonomy/clear` and reaches the router. The
module docstring in `app/api/internal.py` says this; it checks out.

**Missed, and it strengthens the PR's own case:** whether that _public_ path is
also an auth bypass depends on the same AVI question the PR parks as open item
#1.

- If AVI **appends** the real client address, the chain arriving at the pod is
  `[forged_pod_ip, <real client>, 10.98.42.x]`. The reverse walk stops at
  `<real client>` (untrusted) → the forgery fails → 403.
- If AVI **does not append**, the chain is `[forged_pod_ip, 10.98.42.x]`. Both
  entries are trusted, the walk exhausts, the fallback returns the forged
  leftmost → **the pre-PR IP gate is bypassable from the EPFL network**, not
  just from inside the cluster.

So the AVI-doesn't-append branch is _strictly worse_ for `/internal` than it is
for audit IPs — where the PR correctly says the outcome is merely unchanged.
That asymmetry is an argument **for** the secret gate that the PR does not
make, and it is worth one sentence in the plan.

---

## 2. Is the new gate sound?

The mechanism is `HMAC-SHA256(JWT_HMAC_KEY, b"co2-calculator/internal-api/v1")`,
hex-encoded, compared with `hmac.compare_digest`. Reviewed against the four
angles asked for.

### 2.1 MUST FIX — a non-ASCII header value crashes the gate with a 500

`hmac.compare_digest` raises `TypeError` when either `str` argument contains a
non-ASCII character. Starlette decodes header values as **latin-1**, so any byte
≥ `0x80` in `X-Internal-Auth` produces a non-ASCII `str`.

Reproduced against the real code (throwaway test, since removed):

```
>       return hmac.compare_digest(presented, internal_auth_token())
E       TypeError: comparing strings with non-ASCII characters is not supported
app/core/internal_auth.py:49: TypeError
```

There is no handler for `TypeError` in `app/main.py` (only the three
`PermissionDeniedError` family handlers at `:493-495`), so this propagates as an
unhandled server error: **HTTP 500 instead of 403**, plus a logged traceback.

Impact:

- Reachable **unauthenticated**, from the EPFL network, at
  `POST /api/internal/cache/taxonomy/clear` (§1.4). Four bytes of `0xFF` is the
  whole exploit.
- Not an authentication bypass — access is still denied — but it is a crash
  path on the security boundary this PR exists to add, and a trivially
  repeatable 500 generator against a path with no rate limiting (which is
  precisely what #2530 Part 2 is about).
- It also pollutes error tracking and alerting with unauthenticated noise.

Fix is one token, in the guard clause that is already there:

```python
if not presented or not presented.isascii() or not get_settings().JWT_HMAC_KEY:
    return False
```

Comparing bytes instead — `hmac.compare_digest(presented.encode("latin-1"),
internal_auth_token().encode())` — also works for values that came off the
wire, but it is the weaker fix: `internal_auth_ok` is a public function, and
any caller passing a character above `U+00FF` (a test, or the next caller)
trades the `TypeError` for a `UnicodeEncodeError` on the same line. The
`isascii()` guard cannot raise at all and fails closed by construction.

Ship it with a regression test that feeds a non-ASCII header value and asserts
`False`, not an exception.

**This is the fix that sets the verdict.** See §3.1 for why the existing suite
structurally cannot catch it.

### 2.2 Key reuse — defensible, but name the rotation procedure

Domain separation holds. A JWS signing input is always
`b64url(header) + "." + b64url(payload)`, which can never equal the literal
`co2-calculator/internal-api/v1`, so no JWT the app issues is ever a valid
internal token and vice versa. HMAC-SHA256 is a PRF, so possession of the
derived token does not help recover `JWT_HMAC_KEY`. The `internal_auth.py`
docstring states both correctly.

The real cost is operational, and it is understated: **the token cannot be
rotated without rotating `JWT_HMAC_KEY`, which invalidates every session.** The
`/v1` suffix in the label _is_ the rotation mechanism — bump to `/v2`, redeploy
— but the docstring never says so, and a reader who finds a leaked token will
reasonably conclude that the only remedy is a mass logout.

Add one line to the module docstring: _"To rotate this token without touching
`JWT_HMAC_KEY`, bump the label to `.../v2` and redeploy; a rolling deploy has
the same 403 window described in `taxonomy_cache_broadcast`."_

### 2.3 Replay — accepted, and correctly scoped, but the plan should say so

The token is a **static bearer credential**: no nonce, no timestamp, no
expiry, sent over plaintext HTTP. Anyone who observes one intra-cluster request
replays it indefinitely.

This is acceptable here, and the PR's "known property, not a regression"
framing is right, because:

- The only protected operation is an idempotent cache clear. Worst case on
  replay is repeated cold-cache rebuilds — a performance nuisance the IP second
  factor still limits.
- The sender POSTs to whatever `pods.pod_ip` holds, so a forged `pods` row is a
  credential-exfiltration primitive — but writing that row already requires DB
  write access, which is a total compromise anyway.
- The IP second factor is retained, so a replay must _also_ originate from (or
  spoof) a live pod address.

No change requested. Do record in the plan that the gate is replay-tolerant by
design, so the next endpoint added under `/internal` does not inherit the
assumption silently. A non-idempotent `/internal` route would need more than
this.

### 2.4 Secret leakage through logs or errors — checked, clean

- No `sentry_sdk` anywhere in `backend/app/` — GlitchTip is fed from the
  frontend, via `client_ip` on `/v1/session`. So no server-side SDK captures
  request headers on error. (Had one existed, `X-Internal-Auth` is _not_ in
  Sentry's default scrubbing denylist and would have leaked.)
- OTEL captures exactly one request header:
  `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST: "x-forwarded-for"`.
  Not the auth header.
- `_clear_remote` logs `pod_id`, `pod_ip` and `exc` — the httpx exception string
  contains the URL, never request headers.
- The 403 body is a bare `"Forbidden"` with no oracle about which factor failed.

Good. Nothing to change.

### 2.5 Fails closed on every path — yes, except §2.1

`internal_auth_ok` returns `False` on a missing header and on an empty
`JWT_HMAC_KEY` (guarding against deriving a token from `""` that anyone could
compute — a good catch, and tested by
`test_internal_auth_fails_closed_without_a_signing_key`). `_authorize` raises
403 and both factors must pass. Ordering the cheap secret check before the DB
round trip is right.

The one exception is the `TypeError` in §2.1 — which denies access, so it is
not an _authorization_ failure, but it fails **loudly and wrongly** (500) rather
than closed and quietly (403).

---

## 3. Tests — verified by running them, and by reverting

### 3.1 The revert claim holds. The coverage claim is weaker than it looks.

Baseline, the four touched files: **67 passed in 2.12s** — matches the PR
exactly.

Reverting only the secret check inside `_authorize` (restoring the IP-only
gate) and re-running `tests/unit/core/test_internal_cache_endpoint.py`:

```
FAILED test_rejects_a_caller_whose_pod_ip_is_spoofed_via_proxy_headers
        Failed: DID NOT RAISE HTTPException
FAILED test_rejects_a_wrong_internal_token
2 failed, 6 passed
```

Both named tests fail on revert, and
`test_clears_local_cache_when_called_from_a_live_pod` still passes. **The PR's
claim is confirmed.** File restored afterwards; the worktree is clean.

**But — SHOULD FIX — `test_rejects_a_caller_whose_pod_ip_is_spoofed_via_proxy_headers`
does not test proxy-header spoofing.** It builds a
`SimpleNamespace(client=..., headers={})` and passes `auth=None`. It never
constructs an ASGI scope, never instantiates `ProxyHeadersMiddleware`, and never
sends an `X-Forwarded-For`. Functionally it is
`test_rejects_a_wrong_internal_token` with a different `auth` value — which is
why both fail with the identical assertion. The actual attack is characterized
in a _different file_ against a _different function_
(`test_audit_helpers.py::test_a_caller_inside_the_pod_subnet_can_still_choose_its_own_ip`),
and the two are joined only by a docstring cross-reference.

Two consequences:

1. Nothing proves the gate holds **on the endpoint** when the spoof is delivered
   the way the attack actually delivers it.
2. `headers` is a plain `dict`, which is case-sensitive and cannot hold a
   latin-1-decoded value. Starlette's `Headers` is neither. That is precisely
   why the §2.1 crash survived a suite that otherwise looks thorough — the fake
   cannot represent the input that breaks it. **The test design is the root
   cause of the missed bug, not bad luck.**

The fix is cheap and the pattern is already in the branch:
`test_audit_helpers.py::_ip_recorded_for` shows how to drive the real
`ProxyHeadersMiddleware`. Reuse it — build a scope with
`client=("10.20.9.9", …)` and `x-forwarded-for: 10.20.4.4`, run it through the
middleware with `DEPLOYED_FORWARDED_ALLOW_IPS`, and assert the endpoint 403s.
That single test would cover the real attack, the header casing, and the
non-ASCII input.

### 3.2 The rest of the suite is good

- `test_audit_helpers.py` running the helper behind uvicorn's **real**
  middleware with the **real deployed CIDRs** is the right instinct, and is the
  strongest evidence in the PR. Keep this pattern.
- `test_trusting_every_proxy_makes_the_audit_ip_forgeable` parametrised over
  `["*", "0.0.0.0/0"]` demonstrates the two spellings reach the same value,
  which is what justifies the widened boot guard. Well aimed.
- `test_sends_the_internal_token_the_endpoint_accepts` is the right test to have
  written: the sender swallows failures into a warning, so a mismatch between
  the two halves of the gate would be invisible. Asserting the receiver accepts
  what the sender emits is exactly the check that catches it.

---

## 4. The boot guard

**Placement is correct.** `assert_proxy_trust_settings()` is called in the
FastAPI lifespan (`app/main.py:156`), alongside `assert_security_settings` /
`assert_accred_settings` / `assert_poller_isolation` — not in a `Settings`
validator. The stated reason is right and matters: `FORWARDED_ALLOW_IPS` is
uvicorn's own env var, pydantic-settings reads `backend/.env` **without**
exporting into `os.environ`, and uvicorn only ever reads `os.environ`. A
`Settings` field would validate a value the server never sees. This also matches
the repo invariant that boot-time config checks live in the lifespan.

**It is effective.** A `RuntimeError` during lifespan startup makes uvicorn log
`"Application startup failed. Exiting."` and set `should_exit`
(`uvicorn/lifespan/on.py:59-60`), so a pod configured to trust every proxy never
serves a request. Fail-closed confirmed.

**Completeness — one honest gap, one harmless over-strictness.**

- _Gap (document, don't block):_ the guard reads `os.environ` only. uvicorn falls
  back to the env var **only when `--forwarded-allow-ips` is absent**
  (`config.py:355-358`). The Dockerfile CMD ends with `"$@"`, so an operator
  appending `--forwarded-allow-ips '*'` would set `always_trust` while the guard
  sees nothing and the pod boots happily. Complete for the path the deployment
  actually uses; blind to the CLI path. Worth a sentence in the docstring so the
  next reader does not over-trust it.
- _Over-strict, which is the safe direction:_ uvicorn sets `always_trust` only
  when the whole value is exactly `"*"` (`_TrustedHosts.__init__`:
  `trusted_hosts in ("*", ["*"])`). Inside a list — `"10.20.0.0/16,*"` — the
  `*` becomes an inert entry in `trusted_literals` and never matches a parsed IP
  address. The guard rejects it anyway. Refusing to boot on a config that is
  merely nonsense rather than dangerous is the right trade.
- Not caught: complementary halves such as `0.0.0.0/1,128.0.0.0/1`. Contrived;
  ignore.

The `*`-versus-`/0` reasoning in the docstring is accurate — I walked both
branches of `get_trusted_client_address` and they do reach the same
client-chosen leftmost element by different routes. Widening the guard was the
right call, and the parametrised test pins it.

---

## 5. The `set-forwarded-headers: replace` rejection

**The conclusion is correct. The claim that it is unconditional is not.**

Verified against `get_trusted_client_address`. Under `replace`, HAProxy
overwrites XFF with the single peer it sees — the AVI LB, `10.98.42.x`:

- With `10.98.42.0/24` trusted (as deployed): the entry is trusted, the reverse
  walk exhausts, and the fallback returns `x_forwarded_for_hosts[0]` — the LB.
- With it untrusted: the walk stops on the first iteration and returns it — the
  LB.

Either branch yields the load balancer's address. So the PR is right that
`replace` would turn every audit IP into a single useless constant, and right to
reverse the earlier maintainer decision. This is a genuinely good catch and the
reasoning is sound.

**Where it overreaches:** the PR states the rejection "does not depend on either
open question below." It does depend on open item #1.

- If AVI **appends**: `append` gives the real client, `replace` gives the LB.
  `replace` is clearly worse. Rejection is a slam dunk.
- If AVI **does not append**: `append` gives the _forged_ client-supplied value,
  `replace` gives the LB. That is forgeable-but-real versus unforgeable-but-
  useless — a judgment call about which failure mode you prefer in an audit
  trail, not a settled question. Reasonable people would argue for `replace`
  there.

The honest framing, which the plan should adopt: **`replace` is rejected because
the expected chain has AVI appending.** That makes open item #1 a _precondition
of this PR's value_, not an independent footnote — the same assumption carries
both the "forgery is fixed" claim and the `replace` rejection. Resolve it (read
one `http.request.header.x_forwarded_for` attribute off a prod SERVER span and
count the hops) before either claim is treated as settled.

The PR's "strictly no worse, and fixed under the expected chain" statement about
audit IPs is, separately, accurate — I walked both branches and pre-PR
`XFF.split(",")[0]` and post-PR `scope["client"]` return the same string when
AVI does not append.

---

## 6. Repo invariants

| Invariant                                     | Result                                                                                                                                           |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| No silent fallbacks                           | Mostly. See §7 — the rolling-deploy 403 window is swallowed into a `logger.warning` and the docstring understates it.                            |
| Functions ≤ 40 lines, ≤ 2 nesting levels      | Pass. Largest new function is `assert_proxy_trust_settings` at 35 lines including a 20-line docstring — ~10 statements, flat. `_authorize` is 5. |
| Imports at top of file                        | Pass. `ipaddress`/`os` in `main.py`, `hashlib`/`hmac` in `internal_auth.py`. No inline imports.                                                  |
| No `# type: ignore` / `@ts-expect-error`      | Pass — none in the diff.                                                                                                                         |
| No `assert` for runtime narrowing             | Pass. The `assert_*` functions raise `RuntimeError`; no `assert` statement in app code.                                                          |
| `route → service → repo`, commit in the route | N/A — no new SQL; `_caller_is_live_pod` reuses the existing read.                                                                                |
| Bug fix ships with a regression test          | Pass, with the §3.1 caveat.                                                                                                                      |
| Plan file present and conformant              | Pass. `2530-rate-limiting-router-and-per-user.md` has `status`/`issue`/`last_updated`/`summary`; `in-progress` is right with Part 2 outstanding. |

### Lint and type-check

- `make lint` — backend **ruff clean** (`All checks passed!`, 580 files
  formatted), prettier clean on docs.
- `backend/make type-check` — **`ty` clean**.
- Frontend `eslint` **could not run in this worktree** (`Cannot find package
'eslint-plugin-vue'` — no `node_modules`). The PR touches **zero** frontend
  files, so this is an environment gap, not a signal. Not reported as a pass.

---

## 7. Smaller findings

**7.1 (should fix — one sentence) The rolling-deploy staleness window is
understated.** `_clear_remote`'s new docstring says _"A rolling deploy logs 403s
here until every pod carries the #2530 auth header; the cache TTL covers that
window."_ The TTL is `TAXONOMY_CACHE_TTL_SECONDS = 3600.0`, and
`factor_taxonomy_cache.py`'s own module docstring says the TTL _"is no longer
what keeps this cache correct… so it can be sized for hit rate rather than
staleness."_ So "the cache TTL covers that window" means **up to one hour of
stale factor taxonomy**, behind a swallowed warning.

The direction that breaks is old pod → new pod: an old pod sends no header, the
new pod 403s, and the new pod keeps serving its stale tree. In practice the
window is narrow — new pods start with a cold cache, and factor writes come from
deliberate CSV ingestion — so this only bites if a rolling deploy overlaps an
ingestion. Bounded, self-healing, and acceptable. But in a repo whose first
invariant is _no silent fallbacks_, the docstring should name the number rather
than imply no impact. Suggested: _"…until every pod carries the header; a factor
write handled by an old pod can leave a new pod's taxonomy stale for up to
`TAXONOMY_CACHE_TTL_SECONDS` (1 h). Narrow in practice — new pods start cold and
factor writes are deliberate ingestions — but not zero."_

**7.2 (nit) `connectors.py` bypasses the centralised helper.**
`app/api/v1/connectors.py:103`, `:137` and `:191` each inline
`request.client.host if request.client else None` instead of calling
`extract_ip_address`. Not a security gap — they never read `X-Forwarded-For`, so
they were already correct — but it means the "one place resolves the audit IP"
property this PR establishes is not actually true, and the next such call site
is one copy-paste away from reintroducing the bug. Folding them into
`extract_ip_address` is a two-line change (mind the `None` vs `"unknown"`
difference).

**7.3 (nit) Header-name casing is untested.** The endpoint reads
`request.headers.get("X-Internal-Auth")`. Real Starlette `Headers` lookups are
case-insensitive, so this is fine in production — but the test fake is a plain
`dict`, so nothing pins it. The §3.1 fix (drive the real ASGI stack) covers this
for free.

---

## 8. What to do before merge

**Must fix**

1. §2.1 — non-ASCII `X-Internal-Auth` raises `TypeError` → unauthenticated 500.
   Add `not presented.isascii()` to the existing guard clause, plus a regression
   test.

**Should fix**

2. §3.1 — make `test_rejects_a_caller_whose_pod_ip_is_spoofed_via_proxy_headers`
   actually drive `ProxyHeadersMiddleware`, reusing the `_ip_recorded_for`
   pattern already in `test_audit_helpers.py`. It is the test that would have
   caught #1.
3. §5 — correct the "does not depend on either open question" claim in the PR
   body and the plan. The `replace` rejection is sound, but it rests on AVI
   appending, and so does the headline audit-IP claim. Make open item #1 a named
   precondition, not a footnote.
4. §7.1 — correct the "cache TTL covers that window" wording to name the 1 h
   number.

**Nice to have**

5. §2.2 — document `/v1 → /v2` as the token-rotation procedure, so nobody
   concludes rotation requires a mass logout.
6. §4 — note in the guard's docstring that it is blind to the
   `--forwarded-allow-ips` CLI path.
7. §1.4 — record that the AVI-doesn't-append branch makes the pre-PR `/internal`
   gate bypassable from the network, not just in-cluster. It strengthens the
   case for the secret gate.
8. §7.2 — route `connectors.py` through `extract_ip_address`.

**Not blocking, and correctly deferred:** narrowing `FORWARDED_ALLOW_IPS` off the
whole pod overlay subnet, and Part 2's rate limiting. Both are ops/plan items
and the PR is right that neither gates this merge.

---

## 9. Overall

This is careful, well-evidenced work. The central finding — that the proxy-trust
config was already deployed cluster-wide, making the `/internal` IP gate a live
exposure rather than a hypothetical one — is **true**, verified independently
against uvicorn's source and the three overlays. Choosing a derived shared
secret so the gate is closed on the first deploy, rather than one that waits on
an ops action, is the right call and the reasoning for it is honest about its
trade-off. The rejected-alternatives section is unusually good. The `replace`
rejection reverses an earlier decision **correctly**.

Two things keep it from a straight ship. The gate itself has an unauthenticated
crash path on a publicly reachable route — small, one line to fix, but it is on
the boundary the PR exists to build. And the test that carries the security
claim in its name does not exercise the attack it names, which is _why_ the
crash survived: the fake request object cannot represent the input that breaks
it. Fix those two together and this is a clear ship.
