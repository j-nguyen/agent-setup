"""Checkout: reserve stock, apply a coupon, charge the card and create the order."""
from dataclasses import dataclass
import uuid

from django.db import IntegrityError, transaction

from . import payments
from .emails import send_receipt
from .models import Coupon, CouponRedemption, Order, OrderItem, Product


class OutOfStock(Exception):
    pass


@dataclass
class CartItem:
    product_id: int
    qty: int


def checkout(customer, cart: list[CartItem], payment_token: str, coupon_code: str | None = None) -> Order:
    with transaction.atomic():
        # Lock each product row so two checkouts can't both take the last unit.
        lines = []
        for item in cart:
            product = Product.objects.select_for_update().get(pk=item.product_id)
            if product.stock < item.qty:
                raise OutOfStock(product.sku)
            lines.append((product, item.qty))

        total = sum(product.price_cents * qty for product, qty in lines)

        if coupon_code:
            coupon = Coupon.objects.get(code=coupon_code)
            try:
                CouponRedemption.objects.create(coupon=coupon, customer=customer)
                total = coupon.apply(total)
            except IntegrityError:
                pass  # already redeemed by this customer: charge full price

        charge = payments.charge(total, payment_token, idempotency_key=str(uuid.uuid4()))

        order = Order.objects.create(customer=customer, total_cents=total, charge_id=charge.id)
        send_receipt(order)

        for product, qty in lines:
            OrderItem.objects.create(order=order, product=product, qty=qty, price_cents=product.price_cents)
            product.stock -= qty  # safe: the row is locked by select_for_update above
            product.save(update_fields=["stock"])

    return order
