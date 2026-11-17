import json

from hooks import ledger, signature
from hooks.dedupe import SeenEvents
from hooks.log import get_logger

log = get_logger(__name__)
seen = SeenEvents()


def handle(raw_body: bytes, headers: dict, forward=ledger.forward) -> int:
    """Process one provider webhook. Returns the HTTP status to answer with."""
    try:
        event = json.loads(raw_body)
    except ValueError:
        return 400
    if not signature.verify(raw_body, headers.get("X-Signature")):
        log.warning("rejected webhook with bad signature", extra={"fields": {"event_id": event.get("id")}})
        return 401
    if not seen.add_if_new(event["id"]):
        return 200
    try:
        forward(raw_body)
    except ledger.LedgerUnavailable:
        return 502
    return 200
