"""Checkout in three short transactions, with the card charged in between.

1. reserve: lock the products (in id order), take the stock, create a pending order.
2. charge the card, outside any transaction, with an idempotency key tied to the checkout.
3. complete: mark the order paid, write the outbox event, award loyalty points.

Orders left pending (e.g. the process died after charging) are finished or
cancelled by the existing `reconcile_pending_orders` job using the same key.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from . import payments
from .models import LoyaltyAccount, Order, OrderLine, Product
from .outbox import OutboxEvent
from .tx import run_in_transaction

log = logging.getLogger(__name__)


class OutOfStock(Exception):
    pass


class CheckoutCancelled(Exception):
    """This checkout_id was declined earlier; the client must start a new checkout."""


@dataclass(frozen=True)
class CartItem:
    product_id: int
    qty: int


def checkout(Session, customer_id: int, checkout_id: str, cart: list[CartItem], payment_token: str) -> int:
    if not cart or any(item.qty <= 0 for item in cart):
        raise ValueError("cart must have at least one item, each with a positive qty")
    try:
        order_id, total, status = run_in_transaction(Session, lambda s: _reserve(s, customer_id, checkout_id, cart))
    except IntegrityError:
        # A concurrent attempt with the same checkout_id inserted its order first
        # (orders.checkout_id is unique), so carry on with that order.
        found = run_in_transaction(Session, lambda s: _find(s, checkout_id))
        if found is None:
            raise
        order_id, total, status = found
    if status == "paid":  # this checkout_id already went through
        return order_id
    if status == "cancelled":
        raise CheckoutCancelled(checkout_id)
    # Still pending (first attempt, or a retry racing one): charging again with the
    # same idempotency key returns the original charge, and _complete is a no-op twice.

    try:
        charge = payments.charge(total, payment_token, idempotency_key=f"checkout-{checkout_id}")
    except payments.PaymentDeclined:
        run_in_transaction(Session, lambda s: _cancel(s, order_id))
        raise

    run_in_transaction(Session, lambda s: _complete(s, order_id, charge.id))
    return order_id


def _find(session, checkout_id: str) -> tuple[int, int, str] | None:
    existing = session.scalar(select(Order).where(Order.checkout_id == checkout_id))
    if existing is None:
        return None
    return existing.id, existing.total_cents, existing.status


def _reserve(session, customer_id: int, checkout_id: str, cart: list[CartItem]) -> tuple[int, int, str]:
    found = _find(session, checkout_id)
    if found is not None:
        return found

    # Claim the checkout_id before locking any product: a concurrent attempt with the
    # same id blocks on the unique index here and then gets IntegrityError (handled in
    # checkout), rather than racing this one for stock and failing with OutOfStock.
    order = Order(customer_id=customer_id, checkout_id=checkout_id, status="pending", total_cents=0)
    session.add(order)
    session.flush()

    wanted: dict[int, int] = {}
    for item in cart:
        wanted[item.product_id] = wanted.get(item.product_id, 0) + item.qty
    # One query, locked in primary-key order, so concurrent checkouts can't deadlock.
    products = session.scalars(
        select(Product).where(Product.id.in_(wanted)).order_by(Product.id).with_for_update()
    ).all()
    if len(products) != len(wanted):
        raise LookupError("unknown product in cart")
    for p in products:
        if p.stock < wanted[p.id]:
            raise OutOfStock(p.sku)

    order.total_cents = sum(p.price_cents * wanted[p.id] for p in products)
    for p in products:
        p.stock -= wanted[p.id]  # safe: the row is locked FOR UPDATE in this transaction
        order.lines.append(OrderLine(product_id=p.id, qty=wanted[p.id], price_cents=p.price_cents))
    session.flush()
    return order.id, order.total_cents, order.status


def _cancel(session, order_id: int) -> None:
    order = session.get(Order, order_id, with_for_update=True)
    if order.status != "pending":
        return
    order.status = "cancelled"
    products = session.scalars(
        select(Product).where(Product.id.in_([l.product_id for l in order.lines]))
        .order_by(Product.id).with_for_update()
    ).all()
    by_id = {p.id: p for p in products}
    for line in order.lines:
        by_id[line.product_id].stock += line.qty


def _complete(session, order_id: int, charge_id: str) -> None:
    order = session.get(Order, order_id, with_for_update=True)
    if order.status != "pending":
        return
    order.status = "paid"
    order.charge_id = charge_id
    session.add(OutboxEvent(topic="orders.paid", key=str(order.id),
                            payload={"order_id": order.id, "customer_id": order.customer_id,
                                     "total_cents": order.total_cents}))

    # Write the order and event now, outside the try below: begin_nested() flushes
    # pending changes first, and a failure there must fail the checkout.
    session.flush()

    # Loyalty points are best effort: a failure here must not undo the payment
    # bookkeeping above, so it gets its own savepoint.
    try:
        with session.begin_nested():
            account = session.scalar(
                select(LoyaltyAccount).where(LoyaltyAccount.customer_id == order.customer_id).with_for_update()
            )
            if account is None:
                account = LoyaltyAccount(customer_id=order.customer_id, points=0)
                session.add(account)
            account.points += order.total_cents // 100
            session.flush()
    except SQLAlchemyError:
        # E.g. another checkout created this customer's account at the same moment
        # (unique customer_id). Only the savepoint is rolled back.
        log.warning("skipped loyalty points for order %s", order.id, exc_info=True)
