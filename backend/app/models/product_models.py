"""商品与订单域模型：Product / Order / OrderDetail"""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, DECIMAL, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def gen_uuid() -> str:
    return uuid.uuid4().hex


class Product(Base):
    __tablename__ = "product"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称")
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="商品分类")
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[float | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(default=1, comment="1 上架 / 0 下架")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())


class Order(Base):
    __tablename__ = "`order`"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    consumer_id: Mapped[str] = mapped_column(String(32), ForeignKey("consumer.id"), nullable=False)
    total_amount: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="待付款", comment="待付款/待发货/待收货/已完成/已关闭")
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    receiver_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    receiver_phone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receiver_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logistics_company: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logistics_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    details: Mapped[list["OrderDetail"]] = relationship("OrderDetail", back_populates="order", lazy="selectin")


class OrderDetail(Base):
    __tablename__ = "order_detail"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("`order`.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(32), ForeignKey("product.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="details")
