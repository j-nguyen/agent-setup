import pytest

from payments import PaymentError, PaymentsClient
from tests.conftest import FakeResponse, FakeTransport


def test_create_charge(ok_charge):
    t = FakeTransport(ok_charge)
    charge = PaymentsClient(t, "sk_test").create_charge(1000, "usd", "cus_1", "tok_visa")
    assert charge["id"] == "ch_1"
    assert t.calls[0]["headers"]["Idempotency-Key"]


def test_declined_raises_payment_error():
    t = FakeTransport(FakeResponse(402, {"error": {"code": "card_declined", "message": "Declined"}}))
    with pytest.raises(PaymentError) as e:
        PaymentsClient(t, "sk_test").create_charge(1000, "usd", "cus_1", "tok_visa")
    assert e.value.code == "card_declined"
