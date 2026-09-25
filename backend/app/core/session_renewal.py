"""Deliver a renewed session cookie on whatever response goes out (#2943).

FastAPI merges a dependency's ``Response`` headers only when the route
returns plain data. Routes that return a ``Response`` themselves (304 on
taxonomies, file downloads, SSE streams, redirects) would drop the renewed
cookie while its audit row still says "Session renewed". The dependency
therefore parks the ``Set-Cookie`` value on the request state and this
middleware appends it at ``http.response.start``, for every response shape.

Raw ASGI, like ``RequestOriginMiddleware``, so it never buffers a stream.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

RENEWED_COOKIE_STATE_KEY = "renewed_session_cookie"


class SessionRenewalMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Same dict ``request.state`` writes into, so the dependency's value is
        # visible here when the response starts.
        state = scope.setdefault("state", {})

        async def send_with_cookie(message: Message) -> None:
            cookie = state.get(RENEWED_COOKIE_STATE_KEY)
            if message["type"] == "http.response.start" and cookie:
                message["headers"] = [
                    *message.get("headers", []),
                    (b"set-cookie", cookie.encode("latin-1")),
                ]
            await send(message)

        await self.app(scope, receive, send_with_cookie)
