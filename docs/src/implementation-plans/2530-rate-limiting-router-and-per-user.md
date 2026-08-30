---
status: in-progress
issue: 2530
last_updated: 2026-08-30
summary: Two-layer rate limiting — OpenShift router annotations for the hard cap, an in-app per-user limiter on expensive endpoints as a per-pod safety valve. Part 1 (unforgeable audit IP) shipped; this covers Part 2.
---

# 2530 — Rate limiting: router annotations + per-user in-app limiter

## Status

**Part 1 — delivered.** `extract_ip_address` no longer reads `X-Forwarded-For`;
it returns `request.client.host`, which a client cannot forge. See
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

### Known consequence — recorded IP is now the router pod

`FORWARDED_ALLOW_IPS` is set nowhere in this repo, and the deployment runs
uvicorn without `--proxy-headers` (`backend/Dockerfile:76`). So the peer
uvicorn sees is **the OpenShift router pod**, not the end user. Audit rows will
carry the router's address until the follow-up below lands.

This is the intended trade: a coarse-but-true IP beats a plausible-but-forged
one. Misleading evidence in an audit log is worse than uninformative evidence.

### Follow-up to restore real client IPs — read this before doing it

To get end-user addresses back, both halves are needed:

1. `haproxy.router.openshift.io/set-forwarded-headers: replace` on the Route,
   so the router **overwrites** XFF instead of appending — the header then
   carries only what the router observed.
2. `FORWARDED_ALLOW_IPS` set to the router's address/CIDR, so uvicorn's
   `ProxyHeadersMiddleware` resolves `scope["client"]` from that trusted
   header.

**Blocking prerequisite:** `backend/app/api/internal.py`'s `_caller_is_live_pod`
gate is an IP allowlist that holds *only because* uvicorn currently trusts no
proxy headers — this is stated explicitly in
`docs/src/implementation-plans/archive/2278-cache-per-request-user-lookup.md`.
The OpenShift Route's `path: '/api'` is a prefix match
(`helm/templates/routes.yaml`), so `POST /api/internal/...` is reachable from
outside. Enabling proxy-header trust without re-verifying that gate opens it.
Do step 2 only after `internal.py` is re-gated on a shared secret, or after
proving pod-to-pod calls still resolve to their raw peer address.

## Part 2 — Layer 1: OpenShift router (do this first)

Zero app code, and it sheds floods **before** they occupy a pod worker or a DB
connection. The Route is already annotated with
`haproxy.router.openshift.io/timeout: 10m`, so this is adding siblings to an
existing block, not a new pattern.

Annotations to add:

| Annotation | Purpose |
| --- | --- |
| `haproxy.router.openshift.io/rate-limit-connections: "true"` | Enables the stick-table; the others are inert without it. |
| `haproxy.router.openshift.io/rate-limit-connections.concurrent-tcp` | Concurrent TCP connections per source IP. |
| `haproxy.router.openshift.io/rate-limit-connections.rate-http` | HTTP requests per source IP per window. **Verify the window length** against the [OpenShift Route annotation reference](https://docs.openshift.com/container-platform/latest/networking/routes/route-configuration.html) before sizing — it is not per-second, and the numbers below are wrong by that factor if you assume it is. |

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

| Endpoint | Why it is expensive |
| --- | --- |
| `POST /v1/sync/dispatch` | Upload storms saturate the DB — 3.7 CPU cores at 20 parallel ingests. |
| `POST /v1/files/temp-upload` | Same; #2528's failures scale with this concurrency. |
| plan create, `PATCH /v1/project-plans/{id}` | Each can enqueue a prefill job — 42 s median at 40 parallel on dev. |
| login / OAuth callback | Unauthenticated surface; IP-keyed. |

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

1. Do you want the `set-forwarded-headers: replace` + `FORWARDED_ALLOW_IPS`
   follow-up at all, given it requires re-gating `internal.py` first? Audit rows
   record the router pod IP until then.
2. Is `slowapi` an acceptable new dependency, or should Layer 2 wait entirely
   and let the router annotations stand alone?
