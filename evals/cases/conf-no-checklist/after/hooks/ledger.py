import time
import urllib.error
import urllib.request

from hooks.config import LEDGER_URL
from hooks.log import get_logger

log = get_logger(__name__)

MAX_DELIVERY_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 1.0


class LedgerUnavailable(Exception):
    pass


def _http_send(url: str, body: bytes) -> int:
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status


def forward(event_body: bytes, send=_http_send, sleep=time.sleep) -> int:
    """POST one event to the ledger, retrying until it is accepted."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
        try:
            status = send(LEDGER_URL, event_body)
            if status < 300:
                return status
            raise urllib.error.HTTPError(LEDGER_URL, status, "ledger rejected event", None, None)
        except Exception as exc:  # network errors and non-2xx responses alike
            last_error = exc
            log.warning("ledger delivery failed", extra={"fields": {"attempt": attempt, "error": str(exc)}})
            if attempt < MAX_DELIVERY_ATTEMPTS:
                sleep(RETRY_DELAY_SECONDS)
    raise LedgerUnavailable(str(last_error))
