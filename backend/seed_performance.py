"""Seed script: create satisfaction feedback + today's service records for performance page."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.user_models import CustomerServiceStaff, Consumer
from app.models.product_models import Order
from app.models.chat_models import Conversation, Message, ServiceRecord, SatisfactionFeedback

# Target: TestCS1 (cs01) — has 4 conversations already
STAFF_ID = "0f0f4bd60853435d8ddefcf81dc962cc"
CONSUMER_ID = "4fa1c927ebbe4b31a06767a8cd2f3b52"  # consumer01


async def main():
    s = Settings()
    engine = create_async_engine(s.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Find conversations handled by this staff (or create new ones)
        convs = (await db.execute(
            select(Conversation.id, Conversation.status)
            .where(Conversation.staff_id == STAFF_ID)
        )).all()

        conv_ids = [c[0] for c in convs]
        print(f"Found {len(conv_ids)} conversations for TestCS1")

        # 如果数据库为空，先创建 4 个基础对话记录供后续分发满意度
        if not conv_ids:
            print("  No existing conversations — creating seed conversations...")
            # 找一个存在的订单 ID
            order_result = await db.execute(
                select(Order.id).limit(1)
            )
            base_order_id = order_result.scalar_one_or_none()

            for _ in range(4):
                cid = uuid.uuid4().hex
                conv = Conversation(
                    id=cid,
                    consumer_id=CONSUMER_ID,
                    staff_id=STAFF_ID,
                    order_id=base_order_id,  # 可能为 None（允许）
                    status="已关闭",
                    priority="普通",
                    message_count=2,
                    created_at=now - timedelta(days=14),
                )
                db.add(conv)
                conv_ids.append(cid)
                # 添加消费者消息和客服回复
                db.add(Message(
                    id=uuid.uuid4().hex,
                    conversation_id=cid,
                    sender_type="consumer",
                    sender_id=CONSUMER_ID,
                    msg_type="text",
                    content="请问我的订单什么时候发货？",
                    created_at=now - timedelta(days=14),
                ))
                db.add(Message(
                    id=uuid.uuid4().hex,
                    conversation_id=cid,
                    sender_type="staff",
                    sender_id=STAFF_ID,
                    msg_type="text",
                    content="您好，已为您查询，预计明天发出。",
                    created_at=now - timedelta(days=14, seconds=-120),
                ))
            await db.flush()
            print(f"  Created {len(conv_ids)} seed conversations")

        # 2. Create satisfaction feedback for these conversations
        existing_sf_conv = set()
        existing_sfs = (await db.execute(
            select(SatisfactionFeedback.conversation_id)
        )).all()
        for row in existing_sfs:
            existing_sf_conv.add(row[0])

        ratings = [5, 4, 5, 3, 4, 5, 5, 3, 4, 5]
        feedbacks = [
            "客服态度很好，问题解决得很快",
            "回复挺快的，但问题没完全解决",
            "非常满意，客服很专业",
            "还行吧，等了一段时间才回复",
            "解决问题很及时，态度也不错",
            "客服很耐心，解答详细",
            "完美！5星好评",
            "一般般，回复有点慢",
            "不错，基本满意",
            "挺好的，会推荐给朋友",
        ]

        sf_count = 0
        for i, (rating, feedback) in enumerate(zip(ratings, feedbacks)):
            # Distribute across conversations
            cid = conv_ids[i % len(conv_ids)]
            sf_id = uuid.uuid4().hex
            db.add(SatisfactionFeedback(
                id=sf_id,
                conversation_id=cid,
                rating=rating,
                feedback=feedback,
                consumer_id=CONSUMER_ID,
                created_at=now - timedelta(days=i + 1),
            ))
            sf_count += 1
            print(f"  Satisfaction #{i+1}: conv={cid[:12]} rating={rating}")

        print(f"Created {sf_count} satisfaction feedbacks (skipped {len(existing_sf_conv)} existing)")

        # 3. Create today's service records so "今日概览" isn't 0
        today_actions = ["回复"] * 8 + ["审核"] * 3 + ["关闭"] * 1  # 12 today
        for i, action in enumerate(today_actions):
            db.add(ServiceRecord(
                id=uuid.uuid4().hex,
                staff_id=STAFF_ID,
                action=action,
                target_type="conversation",
                target_id=conv_ids[i % len(conv_ids)],
                detail=f"种子数据-{action}",
                created_at=today_start + timedelta(hours=8 + i),
            ))

        # 4. Also create some older ServiceRecords if total < 100 (for richer "累计" display)
        existing_total = (await db.execute(
            select(text("count(1)")).select_from(ServiceRecord).where(
                ServiceRecord.staff_id == STAFF_ID
            )
        )).scalar() or 0
        print(f"Existing ServiceRecords: {existing_total}")

        # 5. Create fresh conversations with fast response times to bring avg down
        #    (existing conversations have hours-long gaps, making the metric look bad)
        # 先找一个合法订单 ID
        order_result = await db.execute(
            select(Order.id).limit(1)
        )
        base_order_id = order_result.scalar_one_or_none()

        new_conv_count = 3
        for i in range(new_conv_count):
            cid = uuid.uuid4().hex
            base_ts = now - timedelta(days=1, hours=i)

            db.add(Conversation(
                id=cid,
                consumer_id=CONSUMER_ID,
                staff_id=STAFF_ID,
                order_id=base_order_id,  # 动态查找的合法订单 ID，避免外键约束错误
                status="已关闭",
                priority="普通",
                message_count=4,
                created_at=base_ts,
            ))

            # Consumer's first message
            db.add(Message(
                id=uuid.uuid4().hex,
                conversation_id=cid,
                sender_type="consumer",
                sender_id=CONSUMER_ID,
                msg_type="text",
                content=["快递还没到急用", "我的退货怎么还没退款", "能帮我查一下订单状态吗"][i],
                created_at=base_ts,
            ))
            # Staff's first reply — fast (30-90 seconds)
            response_delay = timedelta(seconds=30 + i * 30)
            db.add(Message(
                id=uuid.uuid4().hex,
                conversation_id=cid,
                sender_type="staff",
                sender_id=STAFF_ID,
                msg_type="text",
                content=["我帮您查一下物流", "退款已提交财务处理", "好的请发订单号给我"][i],
                created_at=base_ts + response_delay,
            ))
            # Add a second round of conversation
            db.add(Message(
                id=uuid.uuid4().hex,
                conversation_id=cid,
                sender_type="consumer",
                sender_id=CONSUMER_ID,
                msg_type="text",
                content=["谢谢", "大概多久到账", "订单号发给你了"][i],
                created_at=base_ts + response_delay + timedelta(seconds=10),
            ))
            db.add(Message(
                id=uuid.uuid4().hex,
                conversation_id=cid,
                sender_type="staff",
                sender_id=STAFF_ID,
                msg_type="text",
                content=["不客气！", "1-3个工作日", "查到了，预计明天到"][i],
                created_at=base_ts + response_delay + timedelta(seconds=50),
            ))

            # Add service record for this conversation
            db.add(ServiceRecord(
                id=uuid.uuid4().hex,
                staff_id=STAFF_ID,
                action="回复",
                target_type="conversation",
                target_id=cid,
                detail="快速响应-种子数据",
                created_at=base_ts + response_delay,
            ))

            # Add satisfaction feedback
            db.add(SatisfactionFeedback(
                id=uuid.uuid4().hex,
                conversation_id=cid,
                rating=4 if i == 0 else 5,
                feedback=["回复很快", "满意", "服务很好"][i],
                consumer_id=CONSUMER_ID,
                created_at=base_ts + timedelta(hours=1),
            ))
            print(f"  New conversation {cid[:12]}: response_time={response_delay.total_seconds():.0f}s")

        await db.commit()
        print("\nDone! Refresh the performance page.")

    await engine.dispose()


asyncio.run(main())