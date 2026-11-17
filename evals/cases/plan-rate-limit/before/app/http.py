"""A minimal WSGI layer: requests, responses and a router."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import parse_qs

Handler = Callable[["Request"], "Response"]


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    remote_addr: str = ""
    params: dict[str, str] = field(default_factory=dict)
    # Set by middleware.
    api_key: object | None = None
    session: dict | None = None
    request_id: str | None = None

    def header(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name.lower(), default)

    def json(self) -> dict:
        return json.loads(self.body or b"{}")


@dataclass
class Response:
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> dict:
        return json.loads(self.body)


def json_response(data, status: int = 200, headers: dict[str, str] | None = None) -> Response:
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    return Response(status, json.dumps(data).encode(), h)


def error_response(status: int, code: str, message: str,
                   headers: dict[str, str] | None = None) -> Response:
    return json_response({"error": {"code": code, "message": message}}, status, headers)


STATUS_TEXT = {200: "OK", 201: "Created", 400: "Bad Request", 401: "Unauthorized",
               403: "Forbidden", 404: "Not Found", 429: "Too Many Requests",
               500: "Internal Server Error", 503: "Service Unavailable"}


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern, Handler]] = []

    def route(self, method: str, pattern: str):
        regex = re.compile("^" + re.sub(r"<(\w+)>", r"(?P<\1>[^/]+)", pattern) + "$")

        def decorator(fn: Handler) -> Handler:
            self._routes.append((method, regex, fn))
            return fn
        return decorator

    def dispatch(self, request: Request) -> Response:
        for method, regex, fn in self._routes:
            m = regex.match(request.path)
            if m and method == request.method:
                request.params = m.groupdict()
                return fn(request)
        return error_response(404, "not_found", "No such route")

    # WSGI entry point (gunicorn calls this).
    def __call__(self, environ, start_response):
        headers = {k[5:].replace("_", "-").lower(): v
                   for k, v in environ.items() if k.startswith("HTTP_")}
        length = int(environ.get("CONTENT_LENGTH") or 0)
        request = Request(
            method=environ["REQUEST_METHOD"],
            path=environ.get("PATH_INFO", "/"),
            headers=headers,
            query={k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()},
            body=environ["wsgi.input"].read(length) if length else b"",
            remote_addr=environ.get("REMOTE_ADDR", ""),
        )
        response = self.dispatch(request)
        start_response(f"{response.status} {STATUS_TEXT.get(response.status, '')}",
                       list(response.headers.items()))
        return [response.body]
