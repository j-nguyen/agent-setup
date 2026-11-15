from django.core.mail import send_mail


def send_receipt(order) -> None:
    send_mail(
        subject=f"Your order #{order.pk}",
        message=f"Thanks! We charged {order.total_cents / 100:.2f}.",
        from_email="orders@shop.example",
        recipient_list=[order.customer.email],
    )
