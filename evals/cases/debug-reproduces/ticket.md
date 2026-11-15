ENG-101: Promo discount only partly applied on multi-item orders

**Reported by:** Support (Maria) · **Priority:** High · **Labels:** bug, billing

A customer used the 10% PROMO10 code on an order with three different items
($10.00, $20.00 and $30.00, qty 1 each). The invoice total came out as **$59.00**.
It should be **$54.00** (10% off $60). Single-item orders look right.

Comment from Dev (Sam): discount logic is in `invoice_total`, added last sprint.
