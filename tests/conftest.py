from __future__ import annotations

from contextlib import contextmanager
from functools import partial
import json
import sys
import warnings
from pathlib import Path
from urllib.parse import urlsplit

import anyio
import anyio.to_thread
import httpx


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def _run_sync_inline(func, *args, **kwargs):
    kwargs.pop("abandon_on_cancel", None)
    kwargs.pop("cancellable", None)
    kwargs.pop("limiter", None)
    return func(*args, **kwargs)


class ASGISyncTestClient:
    __test__ = False

    def __init__(
        self,
        app,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        cookies=None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
        **_,
    ):
        self.app = app
        self.base_url = base_url
        self.raise_server_exceptions = raise_server_exceptions
        self.root_path = root_path
        self.cookies = httpx.Cookies(cookies)
        self.headers = headers or {}
        self.follow_redirects = follow_redirects

    async def _async_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        follow_redirects = kwargs.pop("follow_redirects", self.follow_redirects)
        json_payload = kwargs.pop("json", None)
        content = kwargs.pop("content", None)
        params = kwargs.pop("params", None)
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        if kwargs:
            unsupported = ", ".join(sorted(kwargs))
            raise TypeError(f"Unsupported test client request argument(s): {unsupported}")

        request = httpx.Request(method, httpx.URL(self.base_url).join(url), headers=headers, params=params)
        if json_payload is not None:
            content = json.dumps(json_payload).encode("utf-8")
            request.headers.setdefault("content-type", "application/json")
        body = content if isinstance(content, bytes) else str(content or "").encode("utf-8")
        if body:
            request.headers["content-length"] = str(len(body))
        self.cookies.set_cookie_header(request)

        parsed = urlsplit(str(request.url))
        response_started: dict[str, object] = {}
        response_body = bytearray()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": parsed.scheme,
            "path": parsed.path or "/",
            "raw_path": (parsed.path or "/").encode("ascii"),
            "query_string": parsed.query.encode("ascii"),
            "headers": [(key.lower(), value) for key, value in request.headers.raw],
            "client": ("testclient", 50000),
            "server": (parsed.hostname or "testserver", parsed.port or (443 if parsed.scheme == "https" else 80)),
            "root_path": self.root_path,
        }
        request_sent = False

        async def receive() -> dict:
            nonlocal request_sent
            if request_sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict) -> None:
            if message["type"] == "http.response.start":
                response_started["status"] = message["status"]
                response_started["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response_body.extend(message.get("body", b""))

        try:
            await self.app(scope, receive, send)
        except Exception:
            if self.raise_server_exceptions:
                raise
            response_started.setdefault("status", 500)
            response_started.setdefault("headers", [])

        response = httpx.Response(
            int(response_started.get("status") or 500),
            headers=httpx.Headers(response_started.get("headers") or []),
            content=bytes(response_body),
            request=request,
        )
        self.cookies.update(response.cookies)
        if follow_redirects and response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            if location:
                next_method = "GET" if response.status_code == 303 else method
                return await self._async_request(next_method, location)
        return response

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        return anyio.run(partial(self._async_request, method, url, **kwargs))

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    @contextmanager
    def stream(self, method: str, url: str, **kwargs):
        yield self.request(method, url, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *_) -> None:
        return None


def pytest_configure() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import fastapi.testclient

    fastapi.testclient.TestClient = ASGISyncTestClient
    anyio.to_thread.run_sync = _run_sync_inline
