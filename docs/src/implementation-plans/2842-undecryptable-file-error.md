---
status: delivered
issue: 2842
last_updated: 2026-09-17
title: "Undecryptable stored file answers an explicit 500"
summary: "GET /api/v1/files/{path} logged 'Error retrieving file: ' with nothing after the colon and returned a blank 500 when the object could not be decrypted: cryptography's InvalidToken has an empty str(), the handler logged only str(e), and the exception never reached the span. The handler now catches InvalidToken by name, logs with traceback and path, records the exception on the span, and answers a detail that names the cause. Cleanup of the objects themselves is an ops task."
---

# Undecryptable stored file answers an explicit 500

## Problem

Seen on dev on 2026-09-17, downloading `processed/141/equipment_factors.csv`
through the new fetch-based download (#2841). S3 returned the object (200,
29,752 bytes, `text/csv`); two milliseconds later the handler logged
`Error retrieving file: ` and answered 500. The trace showed a 500 span with
no exception event.

Root cause, traced through `enacit4r-files`: the store decrypts with Fernet
whenever `FILES_ENCRYPTION_KEY` is set. The object is a valid Fernet token
(starts with `gAAAAA`) written on 2026-09-09 with the key of that day; the
dev backend secret was recreated since, so `Fernet.decrypt` raises
`InvalidToken`. Three things hid that:

- `str(InvalidToken())` is the empty string.
- The handler logged `f"Error retrieving file: {e}"`, no type, no traceback.
- The handler converted the exception into `HTTPException(500)` before the
  OpenTelemetry instrumentation could record it, so the span had no event.

A second latent bug sat in the same block: the 404 for an empty body was
raised inside the `try` and re-caught by the blanket `except`, so an empty
object answered 500 too.

## Decisions

1. **`InvalidToken` gets its own branch**: `logger.exception` with the path
   and the two setting names, `record_exception` on the current span, and a
   500 whose detail says "Stored file cannot be decrypted with the
   configured key". Still a 500: it is a server configuration problem, not
   a client one.
2. **The blanket branch logs with `logger.exception`** and records the
   exception on the span, so the next unknown failure carries its type.
3. **The 404 moves out of the `try`.**
4. Not touched: `enacit4r-files` maps every S3 exception to `(False, False)`
   inside `S3Service.get_file`, so any S3-side failure surfaces as a 404
   here. That is a silent fallback in the dependency, to be raised upstream.

## Tests

`tests/unit/v1/test_files_download_disposition.py`: the store raising
`InvalidToken` answers 500 with the explicit detail and a log record with
the path, the setting names and `exc_info`; an empty body answers 404.

## Ops follow-up, not in this PR

Objects encrypted with the previous dev key are unreadable. Either
re-encrypt them with a one-off script if the old key and salt still exist,
or delete them and clear `processed_file_path` on the jobs that point at
them so the download arrow disappears. Stage and prod need the same check
if their secret was recreated.
