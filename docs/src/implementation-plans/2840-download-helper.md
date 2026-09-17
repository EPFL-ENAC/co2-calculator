---
status: delivered
issue: 2840
last_updated: 2026-09-17
title: "Downloads go through fetch + Blob so they are observable and fail loudly"
summary: "Six places built a hidden <a download> navigation by hand: the request never showed in DevTools and a 401/404 died in the browser's download shelf without reaching the app or Sentry. One downloadBlob helper plus a fetchFile API module replace them; the ?d=true Safari workaround goes because object URLs honor a.download everywhere. Follow-up from #2835."
---

# Downloads go through fetch + Blob so they are observable and fail loudly

## Problem

An anchor with a `download` attribute is a download navigation: the browser
hands it to its download manager outside the page's fetch pipeline. DevTools
Network does not list it, the page never sees the response, and a 401 or 404
becomes a failed entry in the download shelf that nobody reports. Six call
sites did this by hand (`useUploadCard`, `useModuleConfig`,
`useSubmoduleConfig`, `PipelineOperationsConsolePage`,
`ReductionObjectivesSection`, the template download in `ModuleTable`), four of
them carrying a `?d=true` query so the backend sends `Content-Disposition`
because Safari ignores `a.download` on a plain navigation; the others had that
Safari bug live. Four more sites already fetched a Blob and inlined the same
six anchor lines.

## Decisions

1. **One `downloadBlob(blob, filename)`** in `utils/csvDownload.ts`. Object
   URLs honor `a.download` in every browser, so no server header is needed.
2. **`api/files.ts` with `fetchFile(path)`** through the ky client: auth and
   refresh hooks apply, and a non-2xx response throws. Callers do
   `downloadBlob(await fetchFile(path), basename)`.
3. **Templates fetch too.** `constant/templateAssets.ts` exposes
   `fetchTemplate(fileName)` with a `response.ok` check instead of a URL.
4. **`?d=true` is gone from the frontend.** The backend flag and its
   regression tests stay: nothing in the app calls it, but it is a public
   URL feature and removing it is a separate decision.
5. Handlers become `async`; a rejected download surfaces as an unhandled
   rejection, which the Sentry boot captures. No `no-floating-promises`
   rule is configured, so no call-site changes were needed.

## Verification

`make lint` and `make type-check` pass. The integration test for the
"download last CSV" button now asserts the API request (path, no `?d=true`)
and the suggested file name instead of the anchor URL, which a `blob:` URL
could not satisfy.

## Not done

- `chartDownload.ts` keeps its own anchor: it downloads a `data:` URL from
  the chart canvas, no network involved.
- Removing the backend `?d=true` flag. Decide separately.
