---
status: in-progress
issue: 3196
last_updated: 2026-11-25
summary: Clients outside the EPFL network get an info page, sorted by client IP, so the host can move to the public load balancer. The institution folder becomes an image, for the chart and for a Docker Compose file that needs no clone.
---

# 3196: info page for clients outside the EPFL network

## Problem

`co2-calculator.epfl.ch` points to the private load balancer. Off the EPFL
network the browser shows a connection error, and users think the site is
down. DSI agreed (INC0839057) to move the host to the public load balancer
and let us sort the clients ourselves, with no extra audit.

## Decision

Sort by source IP, with one hostname on the public load balancer. Split
DNS is rejected: browsers and operating systems cache DNS answers across a
VPN or Wi-Fi switch, and the page must show on the next reload.

The OpenShift router cannot do the sorting. Its `ip_allowlist` annotation
reads the TCP peer, which is the AVI load balancer for every request (dev
span: `x_forwarded_for = ["128.179.161.59", "10.98.42.215"]`). Each server
behind the router reads `X-Forwarded-For` instead. It takes the right-most
address that is not a trusted proxy, so a forged header does not pass.

| Path    | Check              | Outside the allowed CIDRs           |
| ------- | ------------------ | ----------------------------------- |
| `/`     | frontend nginx     | 403 with `offnet.html`              |
| `/docs` | docs nginx         | 302 to `/`, which shows the page    |
| `/api`  | backend middleware | 403, the backend is never reachable |

A probe path (`/healthz`, `/ready`, `/health`) answers only a request with
no `X-Forwarded-For` header. The kubelet calls the pod directly. The router
and the load balancer always add the header, so their clients get the same
answer as on any other path. The backend applies the same rule to
`/internal/`: the worker and the other backend pods call it directly
(taxonomy cache broadcast, #2845), from an address inside
`trustedProxies`. The route keeps its token and its live-pod check.

## Shape

- `offnet.html` is an asset of the institution folder, like the logo. It
  is one self-contained file: texts in EN and FR, a language switch, CSS,
  script, logo and icon. An outside client gets this file and no other, so
  the page cannot read `/injectEnv.js`, `/theme.css` or `/institution/`.
  Only a font on an other host can be an external file.
  `frontend/institution-default/offnet.html` is the neutral default, with
  no name, no contact and no VPN link.
- The entrypoint copies the page to `/tmp/institution/`. nginx serves it at
  `/offnet.html`, not through `/institution/`: the sandbox CSP of that
  location stops an inline script.
- nginx (frontend and docs): `geo $client_outside` with `proxy` and
  `proxy_recursive`, read from `/etc/nginx/client-allowlist/geo.conf`. The
  image ships a file that allows everyone, so the gate is off unless the
  chart mounts its own.
- Backend: `CLIENT_ALLOWED_CIDRS` setting. Empty means off. The client IP is
  `request.client.host`, already resolved by uvicorn from
  `FORWARDED_ALLOW_IPS`. The probe paths are `/healthz` and `/ready`.
- A trusted proxy as the client counts as outside, in nginx and in the
  backend. A wide allowed network (`10.0.0.0/8`) can hold the proxies, and
  a request can carry no client address: this rule closes both gaps.
- Chart: `clientAllowlist.allowedCidrs` and `clientAllowlist.trustedProxies`.
  One ConfigMap holds `geo.conf` for both nginx pods. The backend gets the
  CIDRs as an environment variable. Empty lists keep today's behavior. If the
  list is set without proxies or without `backend.env.FORWARDED_ALLOW_IPS`,
  the chart fails.

## Institution image

The page is one more file of the institution folder, and more files
follow later, for example the texts. So the folder now travels as an
image, to a cluster and to Docker Compose alike, with no git on the host.

- The institution repository builds an image that holds the folder. The
  image copies the folder into the volume at `/out`, then stops.
- Chart: `frontend.institutionAssets.image` renders an init container
  that runs the image into an `emptyDir`, mounted at `/institution`. The
  `volume` value stays for any other source. The chart fails with both
  or with none (`make -C helm check-institution-source`).
- `docker-compose.deploy.yml` runs the app from published images. The
  frontend mounts the institution image directly, read-only (Docker 28
  or later).
- Each institution has its own repository and its own image. The app
  chart names no institution: an overlay or a compose host gives the
  image of its institution.
- The EPFL repository keeps its ConfigMap chart for one more release, as
  a fallback. The EPFL nodes pull the app images from the internal
  registry, and nobody tried a pull from ghcr yet. After dev proves the
  image path, the chart can leave.
- Kubernetes 1.35 (the cluster of the maintainer's `oc` context) can
  also mount an image as a volume, through the
  `volume` value and with no init container. Not tried on OpenShift.

## Rollout

The institution image with `offnet.html` needs an app version with this
change: an older frontend stops on a file name that it does not know.
The dev overlay changes the app chart version and the institution chart
version in one change.

1. Local: `frontend/docker/test-nginx.sh` and `docs/test-nginx.sh` cover
   internal, external, forged chain, proxy-only, no header and probes. The
   backend unit test covers the middleware.
2. Ship the images and the chart to dev with the lists set, routes still
   private. Check on dev that campus and VPN still reach the app.
3. Keep the private Routes. Add a public copy of each Route in the dev
   overlay, and allow the public ingress controller in
   `ingressFromRoutes`. Each router admits its own copy, so the host works
   on both load balancers: no downtime and no order to respect.
4. From outside, check `/`, `/api`, `/docs` and `/api/healthz`, also with
   a forged `X-Forwarded-For`. Check the X-Forwarded-For chain of the
   public load balancer against `trustedProxies`.
5. Request the DNS change for dev.
6. Stage, then prod, with the same steps.

Allowed CIDRs for EPFL: `128.178.0.0/15`, `10.0.0.0/8`, `2001:620:618::/48`.
The EPFL page is `offnet.html` in the institution repository. The dev
overlay gets it through the institution image, or through version 1.1.0
of the institution chart if the nodes cannot pull the image.

## Open points

- Whether `10.0.0.0/8` is needed. The sample VPN client was `128.179.x`.
- The French texts other than the contact sentence are not approved.
- An open app shows API errors after a network change until a reload.
- `docker-compose.deploy.yml` is not tried with an OIDC login, and it
  keeps uploaded files inside the backend container, so an upgrade
  deletes them unless S3 is set. Issue #3250 owns the
  full Docker Compose deployment.
