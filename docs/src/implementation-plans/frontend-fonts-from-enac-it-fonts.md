---
status: delivered
last_updated: 2026-10-28
title: "Load the brand font from enac-it-fonts.epfl.ch"
summary: "Load Suisse Int'l from the ENAC font server shared by ENAC apps instead of from the app's own build output."
---

**Goal:** the brand font comes from `enac-it-fonts.epfl.ch`, the font
server ENAC apps share. It serves `*.epfl.ch` origins.

## Direct, not through our nginx

The browser loads the fonts from the font server directly. A reverse proxy
in the frontend nginx would have to forge an `Origin` header to get past
the server's 403. It would also re-serve the files with no embed gate.
On top of that it needs resolver and egress configuration, plus a Vite dev
proxy. Every ingress host is `*.epfl.ch`, and nothing sets a CSP or a
`Referrer-Policy`, so Safari's Referer-only font request passes too.

## Shipped

- `frontend/src/css/00-fonts/_fonts.scss`: `@font-face` points at
  `SuisseIntl-*-WebS.woff2` (400/500/700). The family alias `SuisseIntl`
  is unchanged.
- `frontend/index.html`: the preloads point at the same URLs and keep
  `crossorigin`.
- `frontend/scripts/inject-co2.mjs`: external fonts are not in
  `dist/spa`. Their served sizes come from a table, and an unlisted
  external font fails the build. The first-load badge goes from 367.6 KB
  to 380.1 KB.
- `frontend/tests/integration/fonts-from-font-server.spec.ts`: every woff2
  request on `/` targets the font server. The font server itself is
  aborted, which keeps CI hermetic.

## Caveats

- Local dev off the EPFL network or VPN, CI and any non-`epfl.ch` host
  get 403 and render the fallback font.
