"""Seed script: 初始化用户数据（消费者、客服、管理员）
其他种子脚本依赖这些用户的存在。

运行顺序：seed_users.py → seed_orders.py → seed_evaluations.py → seed_performance.py
"""
import asyncio
import uuid

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import Settings
from app.core.security import hash_password
from app.models.user_models import Consumer, CustomerServiceStaff, Admin

# ── 固定 ID（其他种子脚本引用了这些 ID） ──
CONSUMER_ID = "4fa1c927ebbe4b31a06767a8cd2f3b52"   # consumer01
STAFF_ID = "0f0f4bd60853435d8ddefcf81dc962cc"       # cs01
ADMIN_ID = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"       # admin


async def main():
    s = Settings()
    engine = create_async_engine(s.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # ── 1. 创建消费者 │ 用户名: consumer01 / 密码: 123456 ──
        existing_consumer = await db.get(Consumer, CONSUMER_ID)
        if existing_consumer:
            print(f"  [SKIP] Consumer {CONSUMER_ID[:12]} already exists")
        else:
            db.add(Consumer(
                id=CONSUMER_ID,
                openid="consumer01",
                nickname="消费者一号",
                phone=None,
                password=hash_password("123456"),
                role="consumer",
                status=1,
            ))
            print(f"  [OK]   Consumer created: consumer01 / 123456")

        # ── 2. 创建客服 │ 用户名: cs01 / 密码: 123456 ──
        existing_staff = await db.get(CustomerServiceStaff, STAFF_ID)
        if existing_staff:
            print(f"  [SKIP] Staff {STAFF_ID[:12]} already exists")
        else:
            db.add(CustomerServiceStaff(
                id=STAFF_ID,
                username="cs01",
                password=hash_password("123456"),
                name="客服小张",
                role="普通客服",
                status="在线",
                max_concurrent=5,
            ))
            print(f"  [OK]   Staff created: cs01 / 123456")

        # ── 3. 创建管理员 │ 用户名: admin / 密码: 123456 ──
        # 先检查是否已有 username='admin' 的管理员（无论 ID）
        existing_admin_by_username = (await db.execute(
            select(Admin).where(Admin.username == "admin")
        )).scalar_one_or_none()
        existing_admin = await db.get(Admin, ADMIN_ID)

        if existing_admin:
            print(f"  [SKIP] Admin {ADMIN_ID[:12]} already exists")
        elif existing_admin_by_username:
            # 有同名的老记录，将其 ID 更新为期待的 ADMIN_ID
            old_id = existing_admin_by_username.id
            existing_admin_by_username.id = ADMIN_ID
            # 删除旧的 ID 映射记录（若新 ID 不同）
            if old_id != ADMIN_ID:
                await db.delete(existing_admin_by_username)
                await db.flush()
                db.add(Admin(
                    id=ADMIN_ID,
                    username="admin",
                    password=hash_password("123456"),
                    name="系统管理员",
                    role="超级管理员",
                    status=1,
                ))
            print(f"  [OK]   Admin updated: admin / 123456 (id={ADMIN_ID[:12]})")
        else:
            db.add(Admin(
                id=ADMIN_ID,
                username="admin",
                password=hash_password("123456"),
                name="系统管理员",
                role="超级管理员",
                status=1,
            ))
            print(f"  [OK]   Admin created: admin / 123456")

        await db.commit()
        print("\n✅ 用户初始化完成！")

        # ── 验证 ──
        consumer_count = (await db.execute(select(Consumer))).scalars().all()
        staff_count = (await db.execute(select(CustomerServiceStaff))).scalars().all()
        admin_count = (await db.execute(select(Admin))).scalars().all()
        print(f"    当前数据库：消费者 {len(consumer_count)} 人, 客服 {len(staff_count)} 人, 管理员 {len(admin_count)} 人")

    await engine.dispose()


asyncio.run(main())