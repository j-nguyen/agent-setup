"""Operator commands: python3 -m shop.admin replay --db shop.db --since 0"""
import argparse
import socket

from shop.broker import Broker
from shop.db import connect
from shop.event_relay import replay_events


class _TcpTransport:
    def __init__(self, host: str, port: int):
        self._addr = (host, port)

    def send(self, topic: str, body: str) -> None:
        with socket.create_connection(self._addr, timeout=5) as s:
            s.sendall(f"{topic} {body}\n".encode())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="shop.admin")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("replay", help="re-publish outbox events")
    rp.add_argument("--db", required=True)
    rp.add_argument("--since", type=int, default=0)
    rp.add_argument("--broker", default="localhost:7000")
    args = ap.parse_args(argv)
    host, port = args.broker.rsplit(":", 1)
    n = replay_events(connect(args.db), Broker(_TcpTransport(host, int(port))), args.since)
    print(f"replayed {n} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
