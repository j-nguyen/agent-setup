import pytest

from payments import PaymentError, PaymentsClient, TransientError
from payments.retry import backoff_delays
from tests.conftest import FakeResponse, FakeTransport


def client(t, **kw):
    return PaymentsClient(t, "sk_test", sleep=lambda s: None, **kw)


def test_backoff_is_capped_and_jittered():
    delays = list(backoff_delays(6))
    assert len(delays) == 6
    assert all(0 < d <= 8.0 for d in delays)
    assert delays[0] <= 0.5


def test_retries_timeout_then_succeeds(ok_charge):
    t = FakeTransport(TimeoutError("read timed out"), ok_charge)
    assert client(t).create_charge(1000, "usd", "cus_1", "tok_visa")["id"] == "ch_1"
    assert len(t.calls) == 2


def test_retries_5xx_and_429(ok_charge):
    t = FakeTransport(FakeResponse(503), FakeResponse(429, headers={"Retry-After": "2"}), ok_charge)
    assert client(t).create_charge(1000, "usd", "cus_1", "tok_visa")["id"] == "ch_1"
    assert len(t.calls) == 3


def test_gives_up_after_max_attempts():
    t = FakeTransport(FakeResponse(500), FakeResponse(502), FakeResponse(503))
    with pytest.raises(TransientError):
        client(t).create_charge(1000, "usd", "cus_1", "tok_visa")
    assert len(t.calls) == 3


def test_does_not_retry_declines():
    t = FakeTransport(FakeResponse(402, {"error": {"code": "card_declined"}}))
    with pytest.raises(PaymentError):
        client(t).create_charge(1000, "usd", "cus_1", "tok_visa")
    assert len(t.calls) == 1
