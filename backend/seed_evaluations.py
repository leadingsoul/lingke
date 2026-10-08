"""Seed script: 生成评价数据 + 客服满意度评分，覆盖近 30 天，支撑数据分析中心展示。

运行：cd repos/group22-backend && python seed_evaluations.py
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from random import Random

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.product_models import Product, Order, OrderDetail
from app.models.user_models import Consumer, CustomerServiceStaff
from app.models.chat_models import Conversation, SatisfactionFeedback
from app.models.evaluation_models import Evaluation

CONSUMER_ID = "4fa1c927ebbe4b31a06767a8cd2f3b52"  # consumer01
STAFF_ID = "0f0f4bd60853435d8ddefcf81dc962cc"      # cs01

rng = Random(42)  # 固定种子，可重复

# ── 商品 × 评价数据（覆盖不同时段和评分档位） ──
# (product_name, product_rating, service_rating, logistics_rating, content, sentiment, themes, days_ago)

EVALUATION_SEEDS = [
    # ── 洁柔抽纸（好评多，日用百货）──
    ("洁柔抽纸 3层100抽*24包", 5, 5, 5, "纸巾很厚实，不掉屑，比超市便宜多了！", "positive", ["纸质好", "性价比高"], 1),
    ("洁柔抽纸 3层100抽*24包", 4, 4, 4, "质量不错，发货也快，包装完好", "positive", ["质量好", "物流快"], 3),
    ("洁柔抽纸 3层100抽*24包", 5, 3, 5, "纸巾很好用，但是客服回复太慢了，问了好几遍才回", "neutral", ["纸质好", "客服慢"], 5),
    ("洁柔抽纸 3层100抽*24包", 3, 4, 2, "纸还行，但快递暴力运输，箱子都压扁了", "neutral", ["物流慢", "包装破损"], 8),

    # ── 新疆苹果（好评为主，但偶有坏果投诉）──
    ("新疆阿克苏冰糖心苹果 5斤装", 5, 4, 4, "苹果很甜很脆，汁水足！比水果店买的好吃", "positive", ["口感好", "新鲜"], 1),
    ("新疆阿克苏冰糖心苹果 5斤装", 5, 5, 5, "真冰糖心！切开真的能看到，果子也大个", "positive", ["品质好", "正宗"], 4),
    ("新疆阿克苏冰糖心苹果 5斤装", 2, 5, 3, "五个苹果坏了三个，申请退货客服倒是很快处理了", "negative", ["质量问题", "售后好"], 6),
    ("新疆阿克苏冰糖心苹果 5斤装", 4, 4, 4, "整体可以，有个别果子小了一点", "positive", ["大小不均"], 10),
    ("新疆阿克苏冰糖心苹果 5斤装", 1, 3, 2, "收到的苹果全是青的，又酸又涩，跟图片完全不一样，商家虚假宣传！", "negative", ["虚假宣传", "品质差", "色差大"], 12),

    # ── 苏泊尔电饭煲（价格高，期望高，有差评）──
    ("苏泊尔电饭煲 4L 智能预约", 5, 5, 4, "预约功能很方便，早上起来就有粥喝", "positive", ["功能好", "实用"], 2),
    ("苏泊尔电饭煲 4L 智能预约", 4, 4, 4, "煮饭口感好，操作也简单，长辈也能用", "positive", ["易用", "口感好"], 7),
    ("苏泊尔电饭煲 4L 智能预约", 2, 2, 3, "用了两个月内胆就掉涂层了，客服说不在保修范围内，297块钱的东西就这质量？", "negative", ["质量问题", "售后差", "性价比低"], 14),
    ("苏泊尔电饭煲 4L 智能预约", 3, 3, 4, "煮饭还行，但那个触控面板不太灵敏，要按好几下", "neutral", ["触控差", "体验一般"], 18),
    ("苏泊尔电饭煲 4L 智能预约", 1, 1, 3, "买来第三天就不加热了，退货还让我出运费，差评！", "negative", ["故障", "售后推诿", "物流"], 22),

    # ── 三只松鼠坚果（间歇性差评）──
    ("三只松鼠坚果大礼包 10袋装", 5, 5, 5, "每袋都好吃，特别喜欢夏威夷果！", "positive", ["口感好", "品种多"], 2),
    ("三只松鼠坚果大礼包 10袋装", 4, 4, 3, "味道不错就是快递盒有点破", "positive", ["包装问题", "物流"], 9),
    ("三只松鼠坚果大礼包 10袋装", 1, 4, 4, "包装袋都漏气了，坚果都软了，明显是库存货", "negative", ["包装漏气", "不新鲜"], 11),
    ("三只松鼠坚果大礼包 10袋装", 3, 3, 3, "一般般，没有上次买的好吃", "neutral", ["口感一般"], 16),
    ("三只松鼠坚果大礼包 10袋装", 5, 5, 5, "做活动买的很划算，包装也精致送人也体面", "positive", ["性价比高", "包装精致"], 20),

    # ── 美的落地扇（售后争议多）──
    ("美的落地扇 静音遥控款", 4, 4, 4, "风力大噪音小，夏天必备", "positive", ["静音", "风力大"], 3),
    ("美的落地扇 静音遥控款", 3, 4, 2, "风扇还行但是快递太慢了，足足等了五天", "neutral", ["物流慢"], 13),
    ("美的落地扇 静音遥控款", 2, 1, 3, "遥控器是坏的，问客服让我寄回去换，来来回回折腾一周还没解决", "negative", ["质量问题", "售后效率低", "客服态度"], 17),
    ("美的落地扇 静音遥控款", 4, 5, 4, "用了一个月，确实静音，比老式风扇好太多", "positive", ["静音", "品质好"], 24),

    # ── Python 编程书（好评多，但有一两个骂印刷的）──
    ("《Python编程：从入门到实践》第3版", 5, 4, 4, "讲得很清楚，适合零基础，跟着做了一遍收获很大", "positive", ["内容好", "适合入门"], 4),
    ("《Python编程：从入门到实践》第3版", 4, 3, 4, "内容不错，但是有几页印刷模糊看不清楚", "neutral", ["印刷问题"], 15),
    ("《Python编程：从入门到实践》第3版", 5, 5, 5, "非常棒的书！项目实战部分特别有用", "positive", ["实用", "内容好"], 21),

    # ── 李宁运动 T 恤（尺码争议 + 物流慢）──
    ("李宁运动T恤 速干透气", 5, 4, 4, "面料舒服，打球穿很透气", "positive", ["面料好", "透气"], 5),
    ("李宁运动T恤 速干透气", 3, 3, 3, "质量还行，但尺码偏小，建议买大一码", "neutral", ["尺码问题"], 8),
    ("李宁运动T恤 速干透气", 4, 5, 2, "衣服不错但发货太慢了，等了一个星期", "neutral", ["物流慢"], 19),
    ("李宁运动T恤 速干透气", 2, 2, 4, "洗了一次就缩水变形了，99块钱打水漂", "negative", ["质量问题", "缩水"], 25),
]

# ── 客服满意度评分 — 关联到 cs01 的会话 ──
STAFF_SATISFACTION_SEEDS = [
    (5, "客服态度非常好，耐心解答了我的所有问题", 1),
    (4, "回复挺快的，问题基本解决了", 2),
    (5, "很专业，一下子就找到了问题所在", 3),
    (3, "还行吧，等了大概十分钟才回复", 4),
    (5, "非常满意！客服小哥很有耐心", 5),
    (4, "解决问题效率高，好评", 6),
    (2, "态度敷衍，一直让我等等等，等了一个小时就回了句「在查」", 8),
    (5, "超级好！比淘宝客服专业多了", 9),
    (3, "回复是挺快但没解决问题，说了等于没说", 11),
    (5, "客服很有同理心，能站在消费者角度思考", 13),
    (4, "不错，虽然问题没完全解决但态度很好", 15),
    (1, "客服态度极差，直接说「这个不归我管」，投诉也没人理", 17),
    (5, "非常耐心，一步步教我操作", 19),
    (4, "整体满意，会继续使用", 21),
    (2, "转人工转了三次，每次都要我重复一遍问题，烦死了", 23),
    (5, "处理速度快，五分钟就解决了我的退货申请", 25),
    (3, "无功无过，标准流程回复", 27),
    (4, "服务态度好，但是解决速度再快一点就好了", 28),
]


async def main():
    s = Settings()
    engine = create_async_engine(s.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        now = datetime.now(timezone.utc)

        # ── 1. 查现有数据 ──
        products = (await db.execute(select(Product.id, Product.name))).all()
        product_map = {p[1]: p[0] for p in products}
        print(f"Found {len(product_map)} products")

        orders = (await db.execute(
            select(Order.id, Order.status, Order.created_at)
            .where(Order.consumer_id == CONSUMER_ID)
        )).all()
        # 筛选"已完成"订单用于评价
        completed_orders = [
            {"id": o[0], "created_at": o[2]}
            for o in orders if o[1] == "已完成"
        ]
        print(f"Found {len(completed_orders)} completed orders")

        # ── 2. 清理已有评价（避免重复：按内容去重）──
        existing_contents = set()
        existing_rows = (await db.execute(select(Evaluation.content))).scalars().all()
        for c in existing_rows:
            if c:
                existing_contents.add(c)

        # ── 3. 创建商品评价 ──
        eval_count = 0
        for prod_name, pr, sr, lr, content, sentiment, themes, days_ago in EVALUATION_SEEDS:
            if content in existing_contents:
                print(f"  SKIP (exists): {content[:40]}...")
                continue

            pid = product_map.get(prod_name)
            if not pid:
                print(f"  WARN: product not found: {prod_name}")
                continue

            # 按产品名称匹配已完成订单
            detail_rows = await db.execute(
                select(OrderDetail.order_id)
                .where(OrderDetail.product_name == prod_name)
                .limit(5)
            )
            matching_order_ids = [r[0] for r in detail_rows.all()]

            # Find a completed order
            order_id = None
            for o in completed_orders:
                if o["id"] in matching_order_ids:
                    order_id = o["id"]
                    break
            if not order_id and matching_order_ids:
                order_id = matching_order_ids[0]

            if not order_id:
                print(f"  WARN: no order for {prod_name}")
                continue

            created_at = now - timedelta(days=days_ago, hours=rng.randint(0, 12))
            db.add(Evaluation(
                id=uuid.uuid4().hex,
                order_id=order_id,
                consumer_id=CONSUMER_ID,
                product_rating=pr,
                service_rating=sr,
                logistics_rating=lr,
                content=content,
                sentiment=sentiment,
                sentiment_intensity=round(pr / 5.0 + rng.uniform(-0.1, 0.1), 2),
                themes=themes,
                risk_level="high" if sentiment == "negative" else "low",
                created_at=created_at,
            ))
            eval_count += 1

        await db.flush()
        print(f"Created {eval_count} evaluations")

        # ── 4. 创建客服满意度评分 ──
        # 获取 cs01 已关闭的会话
        staff_convs = (await db.execute(
            select(Conversation.id)
            .where(Conversation.staff_id == STAFF_ID)
        )).all()
        conv_ids = [c[0] for c in staff_convs]

        # 如果没有足够的已有关闭会话，用一些存在的会话ID
        if len(conv_ids) < 5:
            all_convs = (await db.execute(
                select(Conversation.id).limit(20)
            )).all()
            for c in all_convs:
                if c[0] not in conv_ids:
                    conv_ids.append(c[0])

        existing_sf = set()
        existing_sf_rows = (await db.execute(
            select(SatisfactionFeedback.conversation_id)
        )).all()
        for r in existing_sf_rows:
            existing_sf.add(r[0])

        sf_count = 0
        for rating, feedback, days_ago in STAFF_SATISFACTION_SEEDS:
            if len(conv_ids) == 0:
                break
            cid = conv_ids[sf_count % len(conv_ids)]
            if cid in existing_sf:
                continue

            created_at = now - timedelta(days=days_ago, hours=rng.randint(0, 12))
            db.add(SatisfactionFeedback(
                id=uuid.uuid4().hex,
                conversation_id=cid,
                consumer_id=CONSUMER_ID,
                rating=rating,
                feedback=feedback,
                created_at=created_at,
            ))
            sf_count += 1

        await db.flush()
        print(f"Created {sf_count} satisfaction feedbacks")

        # ── 5. 统计 ──
        # 重新查询确认总数
        total_evals = (await db.execute(
            select(text("count(1)")).select_from(Evaluation)
        )).scalar()
        total_sf = (await db.execute(
            select(text("count(1)")).select_from(SatisfactionFeedback)
        )).scalar()

        # 按日统计
        daily_stats = (await db.execute(
            text("""
                SELECT DATE(created_at) as d, COUNT(*) as cnt
                FROM evaluation
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY DATE(created_at)
                ORDER BY d
            """)
        )).all()

        await db.commit()

        print(f"\n=== Summary ===")
        print(f"Total evaluations:   {total_evals}")
        print(f"Total satisfaction:  {total_sf}")
        print(f"Daily distribution (last 30 days):")
        for row in daily_stats:
            print(f"  {row.d}: {row.cnt} evals")

    await engine.dispose()


asyncio.run(main())
