"""Thin client for the message broker.

In production this wraps the broker SDK; publishing is a network call that can
time out or fail. Tests use an in-memory subclass.
"""
import json


class PublishError(Exception):
    pass


class Broker:
    def __init__(self, transport):
        self._transport = transport

    def publish(self, topic: str, payload: dict) -> None:
        try:
            self._transport.send(topic, json.dumps(payload, sort_keys=True))
        except OSError as e:
            raise PublishError(str(e)) from e
