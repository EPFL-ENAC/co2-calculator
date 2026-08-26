"""Headers a real browser attaches, for tests that drive the app as one.

`RequestOriginMiddleware` (#89) rejects any cookie-authenticated write that
cannot show it came from our own origin. A bare `TestClient` sends no
`Sec-Fetch-Site`, `Origin` or `Referer`, so it looks exactly like the forged
cross-origin request the middleware exists to stop.

Tests exercising the *application* should therefore present themselves the way
the SPA does. Tests exercising the *middleware* deliberately omit these — see
`tests/unit/core/test_request_origin.py`.
"""

SAME_ORIGIN_HEADERS = {"Sec-Fetch-Site": "same-origin"}
