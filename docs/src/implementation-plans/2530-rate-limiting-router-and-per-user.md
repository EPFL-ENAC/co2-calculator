---
status: in-progress
issue: 2530
last_updated: 2026-08-30
summary: Two-layer rate limiting — OpenShift router annotations for the hard cap, an in-app per-user limiter on expensive endpoints as a per-pod safety valve. Part 1 (unforgeable audit IP) shipped; this covers Part 2.
---

# 2530 — Rate limiting: router annotations + per-user in-app limiter

## Status

**Part 1 — delivered.** `extract_ip_address` no longer reads `X-Forwarded-For`;
it returns `request.client.host`, which a client cannot forge. The follow-up
shipped with it: `/internal` is re-gated on a shared secret, because proxy
headers turned out to be trusted already and the IP allowlist was already
spoofable from inside the cluster. See
[Part 1, shipped](#part-1-shipped-unforgeable-audit-ip) below.

**Part 2 — planned, not implemented.** This file is the design; no limiter code
exists yet.

## Why

The #2295 load tests drove **360 req/s from a single client** with nothing
pushing back. A real user generates **~0.35 req/s**. There is no rate limiting
of any kind in `backend/app` — no slowapi, no limiter, no per-IP throttle. The
connection pool is the resource that breaks first, and #2528's failures scale
with the same concurrency.

## Part 1, shipped: unforgeable audit IP

`backend/app/utils/request_context.py:extract_ip_address` read
`X-Forwarded-For` first and returned `split(",")[0]`. The OpenShift HAProxy
router **appends** to XFF (`set-forwarded-headers` defaults to `append`), so a
client sending its own header owned the first element and the helper returned
the attacker's chosen string. It feeds the audit trail in
`app/api/v1/auth.py`, `data_sync.py` and `carbon_report_module.py`, so audit
IPs were spoofable.

The helper now reads `scope["client"]` only, mirroring the reasoning already
documented on `GET /v1/session`. Regression test:
`backend/tests/unit/utils/test_audit_helpers.py::test_extract_ip_address_ignores_forged_forwarded_for`.

### Correction — proxy headers were already trusted, and the internal endpoint was already exposed

An earlier revision of this plan said `FORWARDED_ALLOW_IPS` was "set nowhere"
and that audit rows would therefore carry the router pod's address. Both were
wrong. It is set nowhere **in this repo**; it is set in
[`openshift-app-config`](https://github.com/EPFL-ENAC/openshift-app-config), in
**all three** overlays:

```yaml
FORWARDED_ALLOW_IPS: "10.20.0.0/16,10.98.42.0/24"
```

and uvicorn's `proxy_headers` defaults to `True` (`uvicorn/config.py:220`), so
`--proxy-headers` was never the switch. `scope["client"]` has been the resolved
end-user address in dev, stage and prod all along.

Two consequences, both now handled:

- **Audit IPs are already real user addresses** once `extract_ip_address` stops
  reading XFF. Nothing further is needed for that half.
- **`10.20.0.0/16` is the cluster's whole pod overlay subnet** — the ops
  comment says so verbatim ("the overlay subnet for pods (which includes the
  haproxies)"). Every workload in the cluster is therefore a _trusted proxy_:
  uvicorn walks the chain from the right, skips the caller's own trusted
  address, and honours whatever it put to the left. So any in-cluster pod could
  set `scope["client"]` to a live co2 pod's IP and satisfy
  `internal.py`'s `_caller_is_live_pod` allowlist. On prod, where
  `networkPolicies` is commented out, it does not even need the Route — it can
  reach a backend pod on 8000 directly, from a trusted source address.

  This was **live exposure, not a future risk** introduced by turning proxy
  headers on. `internal.py` now authenticates on a shared secret first (see
  below); the IP check stays as a second factor.

External clients then cannot forge — **on one unverified assumption**: that the
AVI load balancer (`10.98.42.0/24`) appends the real client address before
HAProxy appends AVI's own. Under that chain the walk from the right stops at
the first untrusted hop, the user. It is the only reading under which the AVI
CIDR belongs in the allowlist at all, and the "we don't need
`128.178.211.0/24`" note in the prod overlay implies ops models these hops as
appearing in XFF. Measure it rather than infer it — see "Still worth doing".

### Delivered — `internal.py` re-gated on a shared secret

`backend/app/core/internal_auth.py`: an `X-Internal-Auth` header carrying
`HMAC-SHA256(JWT_HMAC_KEY, "co2-calculator/internal-api/v1")`, compared with
`hmac.compare_digest`. Derived rather than provisioned so the gate is real the
moment the image ships — a gate waiting on an Infisical secret ships open, or
ships closed and silently breaks the broadcast. Sent by
`taxonomy_cache_broadcast._clear_remote`, required by every `/internal` route.

`backend/app/main.py:assert_proxy_trust_settings` additionally refuses to boot
on a `FORWARDED_ALLOW_IPS` that trusts every proxy. It rejects **both**
spellings, because uvicorn arrives at the same forgeable value by two paths
(`uvicorn/middleware/proxy_headers.py`):

- `*` sets `always_trust`, and `get_trusted_client_address` returns the
  _first_, client-chosen element without walking the chain at all.
- a `/0` network (`0.0.0.0/0`, `::/0`) trusts every address instead, so the
  reverse walk finds no untrusted hop and falls through to the same leftmost
  element. A guard that only grepped for `*` would wave this one through.

### Known property, not a regression

The internal token travels over plain HTTP to whatever address `pods.pod_ip`
holds. That is the trust model the broadcast already had before #2530 — the
`pods` table is written only by the pods' own heartbeat — so nothing here got
weaker. A poisoned `pods` row would misdirect the broadcast either way; the
secret is what stops the _receiver_ accepting a caller that never was a pod.

### Still worth doing, for ops

- **Verify the XFF chain against a real span** — the one measurement that
  confirms Part 1's headline claim. `append` resolves to the real user only if
  the AVI LB appends the client address before HAProxy appends AVI's. If AVI
  SNATs without appending, the chain is `[forged, 10.98.42.7]`, the walk stops
  at the forged entry, and audit IPs stay forgeable from outside. Prod already
  captures `http.request.header.x_forwarded_for` on SERVER-kind spans for
  exactly this purpose — read one and count the hops.

  Be precise about what the change buys in each case, because "strict
  improvement" would be an overclaim. If AVI appends, the forgery is **fixed**.
  If it does not, the walk returns the forged entry and the old
  `XFF.split(",")[0]` returned the same string — **the outcome is identical,
  neither better nor worse**. So: strictly no worse, and fixed under the
  expected chain.

- **Narrow `FORWARDED_ALLOW_IPS`** from the pod overlay subnet to the router
  pods' addresses. Not blocking any more — the secret gate is what stops the
  in-cluster spoof — but a whole-cluster trust list is far wider than the
  purpose needs, and it is what let a header stand in for identity.
- **`set-forwarded-headers: replace` is _not_ recommended**, despite being the
  obvious-looking fix. With `replace`, HAProxy overwrites XFF with the peer
  _it_ sees — the AVI LB, `10.98.42.x`. Every audit IP in the system then
  becomes the load balancer's address, by either branch of
  `get_trusted_client_address` and regardless of the two open items above:
  with the AVI CIDR trusted, the single entry is trusted, the walk exhausts,
  and the "all hosts are trusted" fallback returns it; with it untrusted, the
  walk stops on it and returns it. Unforgeable and useless — it regresses the
  thing Part 1 fixes. `append` (the default) is what makes the chain resolvable
  at all.

## Part 2 — Layer 1: OpenShift router (do this first)

Zero app code, and it sheds floods **before** they occupy a pod worker or a DB
connection. The Route is already annotated with
`haproxy.router.openshift.io/timeout: 10m`, so this is adding siblings to an
existing block, not a new pattern.

Annotations to add:

| Annotation                                                          | Purpose                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `haproxy.router.openshift.io/rate-limit-connections: "true"`        | Enables the stick-table; the others are inert without it.                                                                                                                                                                                                                                                                          |
| `haproxy.router.openshift.io/rate-limit-connections.concurrent-tcp` | Concurrent TCP connections per source IP.                                                                                                                                                                                                                                                                                          |
| `haproxy.router.openshift.io/rate-limit-connections.rate-http`      | HTTP requests per source IP per window. **Verify the window length** against the [OpenShift Route annotation reference](https://docs.openshift.com/container-platform/latest/networking/routes/route-configuration.html) before sizing — it is not per-second, and the numbers below are wrong by that factor if you assume it is. |

HAProxy sees the true source IP at the socket, so this layer is not affected by
the XFF problem above.

**These live in the `openshift-app-config` repo, not this one** —
<https://github.com/EPFL-ENAC/openshift-app-config>, under the Route in
`overlays/{env}/`. Land it there, in the dev overlay first.

Sizing caveat: EPFL campus traffic egresses through **shared NAT**, so a whole
building can present as one source IP. Set `concurrent-tcp` and `rate-http`
generously — this layer is a flood cap, not a fairness mechanism. Fairness is
Layer 2's job. Watch router 503s in the dev overlay for a week before touching
stage.

## Part 2 — Layer 2: in-app, keyed on the authenticated user

### Key: `institutional_id`, not the IP

The JWT carries an unforgeable `institutional_id` on every authenticated
request. Key on that. **Not the IP** — shared campus NAT means an IP-keyed
limit tight enough to matter would throttle a whole building. Reserve IP-keying
for the unauthenticated surface (login / OAuth callback), where no user
identity exists yet, and keep those numbers loose for the same NAT reason.

### Scope: expensive writes only, never reads

| Endpoint                                    | Why it is expensive                                                   |
| ------------------------------------------- | --------------------------------------------------------------------- |
| `POST /v1/sync/dispatch`                    | Upload storms saturate the DB — 3.7 CPU cores at 20 parallel ingests. |
| `POST /v1/files/temp-upload`                | Same; #2528's failures scale with this concurrency.                   |
| plan create, `PATCH /v1/project-plans/{id}` | Each can enqueue a prefill job — 42 s median at 40 parallel on dev.   |
| login / OAuth callback                      | Unauthenticated surface; IP-keyed.                                    |

Reads stay unlimited. Layer 1 is the backstop for read floods.

### Starting numbers

Both are ~an order of magnitude above real usage (~0.35 req/s per user):

- **~20 req/s burst, 5 sustained** per user, across the scoped endpoints.
- **~5 uploads/minute** per user on the two upload paths.

Tune from measurement, not from these numbers — they are a starting point, not
a target.

### The constraint: no shared store

There is **no Redis/Valkey in the stack**, so any in-app limiter is **per-pod
state**. With N replicas a user gets N× the configured limit, and a load
balancer spreading their requests will hand them exactly that.

**Do not add Redis just for this.** A new stateful dependency to enforce a
safety valve costs more than the valve is worth. Two acceptable resolutions:

1. **Divide by replica count** — configure `limit / replicas`. Simple, but
   wrong whenever the deployment scales, and it under-limits a user whose
   requests happen to land on one pod.
2. **Let the router hold the hard cap** (preferred) — Layer 1 is the real
   ceiling; Layer 2 is a per-pod safety valve that stops one authenticated user
   monopolising the pod they landed on. Under this reading, N× is acceptable:
   the app limit does not need to be globally exact, because it is not the
   thing standing between the service and a flood.

Take resolution 2. It needs no config coupling to replica count and it keeps
the two layers doing different jobs.

### Implementation sketch

Ship Layer 1 first and measure before writing any of this.

- Prefer `slowapi` (a thin wrapper over `limits`, in-memory backend) over a
  hand-rolled limiter — but it is a **new dependency**, so per the guardrails it
  waits for the maintainer's go-ahead. Add via `uv add`, never by editing
  `pyproject.toml`.
- Apply per-route, not globally — a global limiter would catch reads.
- The key function resolves `institutional_id` from the already-decoded JWT.
  If it is absent on a route that requires auth, **raise** — do not fall back to
  the IP. A silent key downgrade would let anyone opt out of their own limit by
  dropping a claim, which is the same class of bug as Part 1.
- Over-limit returns **429** with a `Retry-After` header. The frontend surfaces
  it as a distinct "too many requests, retry in Ns" state, not a generic error
  toast, and never as a silent no-op.

### Tests it ships with

- Key function returns the JWT `institutional_id`, and **raises** rather than
  falling back when the claim is missing.
- N+1 requests inside the window return 429 with `Retry-After`.
- The limiter is not attached to any read route (assert a read endpoint stays
  unlimited under the same burst).

## Open questions for the maintainer

1. ~~Do you want the `set-forwarded-headers: replace` + `FORWARDED_ALLOW_IPS`
   follow-up at all?~~ Answered by the ops repo: `FORWARDED_ALLOW_IPS` was
   already set everywhere, so the only outstanding half was the re-gate, which
   shipped. `replace` should **not** be added — see above.
2. Is `slowapi` an acceptable new dependency, or should Layer 2 wait entirely
   and let the router annotations stand alone?
3. `internal_auth` derives its token from `JWT_HMAC_KEY` instead of taking a
   dedicated `INTERNAL_HMAC_KEY` from Infisical, which trades the codebase's
   "one key per signing domain" convention for a gate that needs no ops action
   to be real. Say the word and it becomes its own secret — the only cost is
   that the endpoint 403s (fail-closed, TTL covers it) until that secret lands.
4. Should ops narrow `FORWARDED_ALLOW_IPS` to the router pods?
5. Can someone read one prod SERVER span's
   `http.request.header.x_forwarded_for` and paste the array here? It settles
   whether the AVI LB appends the client address, which is the one assumption
   Part 1's "audit IPs are now the real user" claim rests on. Not blocking —
   the change is a strict improvement either way — but it decides whether
   anything further is needed.
