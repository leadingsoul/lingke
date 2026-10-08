"""Seed script: add diverse products and orders for consumer01."""
import asyncio
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import Settings
from app.models.product_models import Product, Order, OrderDetail
from app.models.user_models import Consumer

CONSUMER_ID = "4fa1c927ebbe4b31a06767a8cd2f3b52"  # consumer01

NEW_PRODUCTS = [
    {"name": "新疆阿克苏冰糖心苹果 5斤装", "category": "生鲜水果", "price": 59.90},
    {"name": "苏泊尔电饭煲 4L 智能预约", "category": "厨房电器", "price": 299.00},
    {"name": "三只松鼠坚果大礼包 10袋装", "category": "零食特产", "price": 128.00},
    {"name": "美的落地扇 静音遥控款", "category": "生活电器", "price": 199.00},
    {"name": "《Python编程：从入门到实践》第3版", "category": "图书", "price": 79.00},
    {"name": "李宁运动T恤 速干透气", "category": "运动户外", "price": 99.00},
    {"name": "洁柔抽纸 3层100抽*24包", "category": "日用百货", "price": 49.90},
]

# (product_name, price, quantity, status, days_ago)
NEW_ORDERS = [
    # 待付款：3个
    ("苏泊尔电饭煲 4L 智能预约", 299.00, 1, "待付款", 1),
    ("李宁运动T恤 速干透气", 99.00, 2, "待付款", 2),
    ("新疆阿克苏冰糖心苹果 5斤装", 59.90, 1, "待付款", 0),
    # 待收货：3个
    ("三只松鼠坚果大礼包 10袋装", 128.00, 1, "待收货", 3),
    ("美的落地扇 静音遥控款", 199.00, 1, "待收货", 5),
    ("《Python编程：从入门到实践》第3版", 79.00, 1, "待收货", 4),
    # 已完成：4个
    ("洁柔抽纸 3层100抽*24包", 49.90, 2, "已完成", 10),
    ("新疆阿克苏冰糖心苹果 5斤装", 59.90, 1, "已完成", 15),
    ("三只松鼠坚果大礼包 10袋装", 128.00, 1, "已完成", 20),
    ("李宁运动T恤 速干透气", 99.00, 1, "已完成", 25),
    # 已关闭：1个（前端过滤，但保留数据完整性）
    ("美的落地扇 静音遥控款", 199.00, 1, "已关闭", 7),
]


async def main():
    s = Settings()
    engine = create_async_engine(s.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. Add new products
        existing = (await db.execute(select(Product.name))).scalars().all()
        existing_names = set(existing)
        product_map: dict[str, str] = {}  # name → id

        for p in NEW_PRODUCTS:
            if p["name"] in existing_names:
                # Find existing ID
                r = await db.execute(select(Product.id).where(Product.name == p["name"]))
                pid = r.scalar_one_or_none()
                if pid:
                    product_map[p["name"]] = pid
                    continue
            pid = uuid.uuid4().hex
            product_map[p["name"]] = pid
            db.add(Product(
                id=pid, name=p["name"], category=p["category"],
                price=p["price"], description=p["name"], status=1,
            ))

        # Also map existing products by name
        r = await db.execute(select(Product.id, Product.name))
        for pid, pname in r:
            if pname not in product_map:
                product_map[pname] = pid

        await db.flush()
        print(f"Products ready: {len(product_map)} total")

        # 2. Create orders
        now = datetime.utcnow()
        created = 0

        for prod_name, price, qty, status, days_ago in NEW_ORDERS:
            oid = uuid.uuid4().hex
            created_at = now - timedelta(days=days_ago)
            total = round(price * qty, 2)
            receiver = "张先生" if created % 2 == 0 else "李女士"

            db.add(Order(
                id=oid, consumer_id=CONSUMER_ID,
                total_amount=total, status=status,
                payment_method="微信支付" if status != "待付款" else None,
                receiver_name=receiver,
                receiver_phone="13800138000",
                receiver_address="重庆市沙坪坝区大学城中路",
                created_at=created_at, updated_at=created_at,
            ))
            pid = product_map[prod_name]
            db.add(OrderDetail(
                id=uuid.uuid4().hex, order_id=oid, product_id=pid,
                product_name=prod_name, quantity=qty, unit_price=price,
            ))
            created += 1

        await db.commit()
        print(f"Orders created: {created}")

    await engine.dispose()


asyncio.run(main())
