"""Test doubles shared by the order and relay tests."""
from shop.broker import Broker


class RecordingTransport:
    def __init__(self, fail_times: int = 0):
        self.sent: list[tuple[str, str]] = []
        self.fail_times = fail_times

    def send(self, topic: str, body: str) -> None:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError("broker unavailable")
        self.sent.append((topic, body))


def make_broker(fail_times: int = 0) -> tuple[Broker, RecordingTransport]:
    transport = RecordingTransport(fail_times)
    return Broker(transport), transport
