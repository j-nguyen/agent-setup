Checkout for the shop (Django 5, PostgreSQL).

1. Reserve stock atomically: two checkouts must never sell the same last unit. Flash sales mean hundreds of concurrent checkouts on the same few products, each with several items.
2. A coupon can be redeemed once per customer. If this customer already used it, the checkout still succeeds at full price.
3. Charge the card once per checkout. If the order can't be created, the customer must not end up charged with no order.
4. Email the receipt only for orders that were actually created.
5. Checkout must stay fast under load. Product rows are hot, so don't hold their locks longer than needed.
