from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    price_cents: Mapped[int]
    stock: Mapped[int]


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int]
    checkout_id: Mapped[str] = mapped_column(String(64), unique=True)  # client-generated, one per checkout attempt
    status: Mapped[str] = mapped_column(String(16))  # pending | paid | cancelled
    total_cents: Mapped[int]
    charge_id: Mapped[str | None] = mapped_column(String(64))
    lines: Mapped[list["OrderLine"]] = relationship(back_populates="order")


class OrderLine(Base):
    __tablename__ = "order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int]
    price_cents: Mapped[int]
    order: Mapped[Order] = relationship(back_populates="lines")


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(unique=True)
    points: Mapped[int] = mapped_column(default=0)
