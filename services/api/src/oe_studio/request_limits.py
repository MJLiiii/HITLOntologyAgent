"""Bound bytes before multipart parsing, including requests without a truthful length."""
from uuid import uuid4
from starlette.responses import JSONResponse


class RequestBodyLimit:
    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def reject(status, code, message):
            response = JSONResponse(status_code=status, content={"code": code, "message": message,
                                    "details": None, "correlation_id": str(uuid4())})
            await response(scope, receive, send)

        lengths = [value for key, value in scope.get("headers", []) if key.lower() == b"content-length"]
        if lengths and (len(lengths) != 1 or not lengths[0].isdigit()):
            return await reject(400, "invalid_length", "Invalid Content-Length header")
        if lengths and int(lengths[0]) > self.limit:
            return await reject(413, "too_large", "Request exceeds the local size limit")
        if scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                return await reject(413, "too_large", "Request exceeds the local size limit")
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app(scope, bounded_receive, send)
