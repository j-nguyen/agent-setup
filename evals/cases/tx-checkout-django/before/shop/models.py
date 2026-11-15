from django.db import models


class Product(models.Model):
    sku = models.CharField(max_length=40, unique=True)
    price_cents = models.PositiveIntegerField()
    stock = models.PositiveIntegerField(default=0)


class Coupon(models.Model):
    code = models.CharField(max_length=40, unique=True)
    percent_off = models.PositiveSmallIntegerField()

    def apply(self, total_cents: int) -> int:
        return total_cents * (100 - self.percent_off) // 100


class CouponRedemption(models.Model):
    """A customer can redeem each coupon once."""
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT)
    customer = models.ForeignKey("auth.User", on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["coupon", "customer"], name="one_redemption_per_customer")]


class Order(models.Model):
    customer = models.ForeignKey("auth.User", on_delete=models.PROTECT)
    total_cents = models.PositiveIntegerField()
    charge_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField()
    price_cents = models.PositiveIntegerField()
