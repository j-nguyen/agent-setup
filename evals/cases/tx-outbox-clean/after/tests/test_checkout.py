import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from shop import checkout as co
from shop import payments
from shop.models import Base, LoyaltyAccount, Order, Product
from shop.outbox import OutboxEvent, relay_outbox


@pytest.fixture
def Session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    S = sessionmaker(engine, expire_on_commit=False)
    with S.begin() as s:
        s.add_all([Product(id=1, sku="mug", price_cents=1200, stock=5),
                   Product(id=2, sku="tee", price_cents=2500, stock=1)])
    return S


@pytest.fixture
def charges(monkeypatch):
    calls = []

    def fake_charge(amount, token, idempotency_key):
        calls.append(idempotency_key)
        if token == "tok_declined":
            raise payments.PaymentDeclined("no")
        return payments.Charge(f"ch_{len(calls)}", amount)

    monkeypatch.setattr(payments, "charge", fake_charge)
    return calls


def stock(S, pid):
    with S() as s:
        return s.get(Product, pid).stock


def test_checkout_reserves_charges_and_queues_event(Session, charges):
    oid = co.checkout(Session, 7, "c1", [co.CartItem(2, 1), co.CartItem(1, 2)], "tok_ok")
    with Session() as s:
        order = s.get(Order, oid)
        assert (order.status, order.total_cents) == ("paid", 4900)
        assert s.scalar(select(OutboxEvent)).topic == "orders.paid"
        assert s.scalar(select(LoyaltyAccount)).points == 49
    assert (stock(Session, 1), stock(Session, 2)) == (3, 0)
    assert charges == ["checkout-c1"]


def test_retrying_the_same_checkout_is_a_no_op(Session, charges):
    first = co.checkout(Session, 7, "c1", [co.CartItem(1, 1)], "tok_ok")
    assert co.checkout(Session, 7, "c1", [co.CartItem(1, 1)], "tok_ok") == first
    assert stock(Session, 1) == 4 and len(charges) == 1


def test_decline_releases_stock(Session, charges):
    with pytest.raises(payments.PaymentDeclined):
        co.checkout(Session, 7, "c2", [co.CartItem(2, 1)], "tok_declined")
    assert stock(Session, 2) == 1
    with Session() as s:
        assert s.scalar(select(Order)).status == "cancelled"


def test_retry_after_decline_is_refused(Session, charges):
    with pytest.raises(payments.PaymentDeclined):
        co.checkout(Session, 7, "c2", [co.CartItem(2, 1)], "tok_declined")
    with pytest.raises(co.CheckoutCancelled):
        co.checkout(Session, 7, "c2", [co.CartItem(2, 1)], "tok_declined")
    assert stock(Session, 2) == 1 and len(charges) == 1


def test_concurrent_duplicate_reuses_the_winning_order(Session, charges, monkeypatch):
    first = co.checkout(Session, 7, "c5", [co.CartItem(1, 1)], "tok_ok")
    real_find, calls = co._find, []

    def racy_find(session, checkout_id):  # the first lookup misses, as if the other insert hadn't committed yet
        calls.append(checkout_id)
        return None if len(calls) == 1 else real_find(session, checkout_id)

    monkeypatch.setattr(co, "_find", racy_find)
    assert co.checkout(Session, 7, "c5", [co.CartItem(1, 1)], "tok_ok") == first
    assert stock(Session, 1) == 4 and len(charges) == 1


@pytest.mark.parametrize("cart", [[], [co.CartItem(1, 0)], [co.CartItem(1, 3), co.CartItem(2, -1)]])
def test_rejects_empty_carts_and_non_positive_quantities(Session, charges, cart):
    with pytest.raises(ValueError):
        co.checkout(Session, 7, "c6", cart, "tok_ok")
    assert charges == [] and stock(Session, 2) == 1


def test_out_of_stock(Session, charges):
    with pytest.raises(co.OutOfStock):
        co.checkout(Session, 7, "c3", [co.CartItem(2, 2)], "tok_ok")
    assert charges == []


def test_relay_publishes_once(Session, charges):
    co.checkout(Session, 7, "c4", [co.CartItem(1, 1)], "tok_ok")
    published = []

    class Pub:
        def publish(self, topic, key, value):
            published.append((topic, key))

    assert relay_outbox(Session, Pub()) == 1
    assert relay_outbox(Session, Pub()) == 0
    assert published == [("orders.paid", "1")]
