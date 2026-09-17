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

1. **One `downloadBlob(blob, filename)`** in `utils/download.ts` (renamed
   from `csvDownload.ts`: it now serves JSON and PDF exports too). Object
   URLs honor `a.download` in every browser, so no server header is needed.
   The object URL is revoked 40 s later, not synchronously: Firefox can
   abort a large download when the URL dies before its download manager
   reads the blob (FileSaver does the same).
2. **`downloadFrom(load, filename)`** wraps the load: on failure it toasts
   `common_download_failed` and rethrows, so the user sees something and
   Sentry gets the error. The one place download errors become visible.
3. **`api/files.ts` with `fetchFile(path)` and `downloadFile(path)`**
   through the ky client: auth and refresh hooks apply, a non-2xx throws,
   and the file keeps its base name. `composables/downloadLastCsv.ts` is
   the single upload-card download, replacing three identical copies.
4. **Templates fetch too.** `constant/templateAssets.ts` exposes
   `fetchTemplate(fileName)` with a `response.ok` check. Raw `fetch` on
   purpose: a same-origin static asset with no auth, and the ky client's
   `prefixUrl` would rewrite the hashed `/assets/` path.
5. **`?d=true` is gone from the frontend.** The backend flag and its
   regression tests stay: nothing in the app calls it, but it is a public
   URL feature and removing it is a separate decision.
6. Handlers become `async`; a rejected download surfaces as an unhandled
   rejection, which the Sentry boot captures, after the toast. No `no-floating-promises`
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
