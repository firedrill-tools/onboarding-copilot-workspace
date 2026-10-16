"""Bounded original JSON validation without replacing framework/vendor caches."""

from starlette.responses import JSONResponse
from .store import strict_json


class StrictJSONMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PATCH"}:
            await self.app(scope, receive, send)
            return
        messages = []
        chunks = []
        size = 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            if event["type"] != "http.request":
                continue
            part = event.get("body", b"")
            size += len(part)
            if size > 1048576:
                await JSONResponse(
                    {"detail": "Request JSON exceeds 1 MiB retained limit"},
                    status_code=413,
                )(scope, receive, send)
                return
            chunks.append(part)
            messages.append(event)
            if not event.get("more_body", False):
                break
        try:
            strict_json(b"".join(chunks).decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError):
            await JSONResponse(
                {"detail": "Request requires unambiguous finite JSON"}, status_code=400
            )(scope, receive, send)
            return

        async def replay():
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, replay, send)
