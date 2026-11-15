import pytest


class FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status, self._body, self.headers = status, body or {}, headers or {}

    def json(self):
        return self._body


class FakeTransport:
    """Returns (or raises) the queued outcomes in order and records every call."""

    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture
def ok_charge():
    return FakeResponse(200, {"id": "ch_1", "status": "succeeded"})
