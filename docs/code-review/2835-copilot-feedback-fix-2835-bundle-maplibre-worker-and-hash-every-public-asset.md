# Bot Review TODOs: PR #2838

Source Branch: `fix/2835-bundle-maplibre-worker`
---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### Summary Feedback (enac-ai-reviewer)

This PR bundles the maplibre worker with Vite, moves public/ assets into src/assets so they get content-hashed URLs, and reworks the nginx cache rules so only hashed names get `immutable` while everything else revalidates. The approach is sound and well-documented; the main things to verify are the nginx regex ordering/quoting, the favicon query-string cache busting, and that the moved assets are all actually referenced.
---

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### File: `frontend/nginx.conf` (Line 150) — enac-ai-reviewer[bot]

The hashed-asset regex now includes `ico`, and the `location = /favicon.ico` block above sets `expires 1d` / `max-age=86400`. But `index.html` links the favicon as `favicon.ico?v=<%= appVersion %>` — a query string. nginx `location = /favicon.ico` matches the path without the query, so the versioned request still hits this location and gets the 1-day cache, not the hashed/immutable rule. That's presumably intended (the query busts it per release), but worth confirming the `?v=` request actually reaches this location and isn't caught by the hashed regex (it won't be, since the path has no hash). Just double-check the intended behavior holds for the versioned URL.
---

### File: `frontend/nginx.conf` (Line 166) — enac-ai-reviewer[bot]

The unhashed rule now covers `csv` and all image/font types with `no-cache, must-revalidate`. But the `location = /favicon.ico` block above sets `expires 1d` with `public, max-age=86400` — that's a longer cache than the unhashed rule's `no-cache`. Since `location =` (exact match) takes precedence over regex locations, the favicon gets 1 day of caching while every other unhashed asset revalidates. That's intentional per the comment, but it means a replaced favicon under the same URL (without the `?v=` bust) can be stale for up to a day — acceptable, just confirming it's deliberate.
---

---

## Action Items

_No substantive items after verification. Copilot hit its quota on all seven review requests. The two `enac-ai-reviewer` comments ask to confirm intent, and both hold: nginx matches `location = /favicon.ico` on the path without the query, so `favicon.ico?v=<sha>` reaches it (verified in the base image, answers `public, max-age=86400`), and the one-day cache on the bare path versus `no-cache` for other unhashed assets is deliberate (see decision 6 in the implementation plan). The `expires 1d` the reviewer cites was already removed in the last commit; the `add_header` carries the max-age._
