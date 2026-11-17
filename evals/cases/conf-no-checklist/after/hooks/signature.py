import hashlib
import hmac

from hooks.config import WEBHOOK_SECRET


def verify(raw_body: bytes, signature_header: str | None) -> bool:
    if not signature_header:
        return False
    expected = hmac.new(WEBHOOK_SECRET, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
