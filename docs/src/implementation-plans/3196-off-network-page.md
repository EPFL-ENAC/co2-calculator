---
status: in-progress
issue: 3196
last_updated: 2026-11-11
summary:
  "A page tells off-network users that the calculator works only on the
  EPFL network or VPN. Step 1 is a frontend mock at /off-network for design
  review. The network detection comes later."
---

# 3196: Explain that the site is reachable only on the EPFL network or VPN

## Problem

The calculator is reachable only from the EPFL network or the EPFL VPN.
Off the network, the browser shows a timeout or a generic error. Users
think that the site is down and do not come back.

## Step 1: frontend mock (this PR)

The route `/off-network` shows `pages/ErrorOffNetwork.vue`. The page does
no network check. It shows the screen for design review only.

The page uses the login page background and a card shaped like the login
card: the EPFL logo and the "CO₂ Calculator" title on top. The user then
sees that they reached the correct site. The card then holds:

- one dark sentence that says the calculator works only on the EPFL
  network, and one grey sentence that tells off-campus users to connect
  to the EPFL VPN,
- a full-width Retry button that goes back to the app landing route,
- a full-width outlined button that opens the EPFL VPN help page in a
  new tab,
- the text for external users that the business owner approved on the
  issue, with the `co2calculator@epfl.ch` address.

The strings are in `i18n/off_network.ts`, in English and French.

## Open questions

- Nobody approved the VPN documentation URL yet.
- How does an off-network browser get this page? If the router blocks the
  host by IP, the app never loads. The page then must be a static page
  that the frontend container or the router serves. The technical owner
  on the issue decides this.
