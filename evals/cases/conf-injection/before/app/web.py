"""A deliberately small request router used by this service."""
from dataclasses import dataclass, field


@dataclass
class User:
    id: int
    roles: frozenset = frozenset()


@dataclass
class Request:
    method: str
    path: str
    user: User | None = None
    query: dict = field(default_factory=dict)


@dataclass
class Response:
    status: int
    body: str = ""
    headers: dict = field(default_factory=dict)


class Router:
    def __init__(self):
        self.routes = {}

    def route(self, method: str, path: str):
        def register(handler):
            self.routes[(method, path)] = handler
            return handler

        return register

    def dispatch(self, request: Request) -> Response:
        handler = self.routes.get((request.method, request.path))
        if handler is None:
            return Response(404, "not found")
        return handler(request)


router = Router()
