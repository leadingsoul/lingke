"""initial tables — 20 张业务表全量创建

Revision ID: 001
Revises: None
Create Date: 2026-06-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 用户层 3 表 ──
    op.create_table(
        "consumer",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("openid", sa.String(100), unique=True, nullable=False),
        sa.Column("nickname", sa.String(50), nullable=True),
        sa.Column("avatar", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(255), nullable=True),
        sa.Column("platform_account", sa.String(100), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="consumer"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "customer_service_staff",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="普通客服"),
        sa.Column("phone", sa.String(255), nullable=True),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("avatar", sa.String(255), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="离线"),
        sa.Column("max_concurrent", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "admin",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="admin"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ── 商品域 2 表 ──
    op.create_table(
        "product",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("image_url", sa.String(255), nullable=True),
        sa.Column("price", sa.DECIMAL(10, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "`order`",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("consumer_id", sa.String(32), sa.ForeignKey("consumer.id"), nullable=False),
        sa.Column("total_amount", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="待付款"),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("receiver_name", sa.String(50), nullable=True),
        sa.Column("receiver_phone", sa.String(255), nullable=True),
        sa.Column("receiver_address", sa.String(500), nullable=True),
        sa.Column("logistics_company", sa.String(100), nullable=True),
        sa.Column("logistics_no", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "order_detail",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("order_id", sa.String(32), sa.ForeignKey("`order`.id"), nullable=False),
        sa.Column("product_id", sa.String(32), sa.ForeignKey("product.id"), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("product_image", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.DECIMAL(10, 2), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ── 售后域 1 表 ──
    op.create_table(
        "after_sale_order",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("order_id", sa.String(32), sa.ForeignKey("`order`.id"), nullable=False),
        sa.Column("consumer_id", sa.String(32), sa.ForeignKey("consumer.id"), nullable=False),
        sa.Column("aso_type", sa.String(20), nullable=False),
        sa.Column("aso_reason", sa.String(20), nullable=False),
        sa.Column("aso_status", sa.String(20), server_default="待审核"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence_urls", sa.JSON(), nullable=True),
        sa.Column("handler_id", sa.String(32), sa.ForeignKey("customer_service_staff.id"), nullable=True),
        sa.Column("review_opinion", sa.Text(), nullable=True),
        sa.Column("urgency", sa.String(10), server_default="普通"),
        sa.Column("responsibility", sa.String(10), server_default="待定"),
        sa.Column("custom_tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ── 咨询域 5 表 ──
    op.create_table(
        "conversation",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("consumer_id", sa.String(32), sa.ForeignKey("consumer.id"), nullable=False),
        sa.Column("staff_id", sa.String(32), sa.ForeignKey("customer_service_staff.id"), nullable=True),
        sa.Column("order_id", sa.String(32), sa.ForeignKey("`order`.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="AI进行中"),
        sa.Column("intent_level", sa.String(2), nullable=True),
        sa.Column("priority", sa.String(10), server_default="普通"),
        sa.Column("message_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "message",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("conversation_id", sa.String(32), sa.ForeignKey("conversation.id"), nullable=False),
        sa.Column("sender_type", sa.String(10), nullable=False),
        sa.Column("sender_id", sa.String(32), nullable=True),
        sa.Column("msg_type", sa.String(20), server_default="text"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("image_urls", sa.JSON(), nullable=True),
        sa.Column("ai_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "session_summary",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("conversation_id", sa.String(32), sa.ForeignKey("conversation.id"), nullable=False),
        sa.Column("content", MEDIUMTEXT(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("review_status", sa.String(10), server_default="待审核"),
        sa.Column("sync_status", sa.String(10), server_default="未同步"),
        sa.Column("reviewer_id", sa.String(32), sa.ForeignKey("admin.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "satisfaction_feedback",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("conversation_id", sa.String(32), sa.ForeignKey("conversation.id"), nullable=False),
        sa.Column("consumer_id", sa.String(32), sa.ForeignKey("consumer.id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "service_record",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("staff_id", sa.String(32), sa.ForeignKey("customer_service_staff.id"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ── 评价域 2 表 ──
    op.create_table(
        "evaluation",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("order_id", sa.String(32), sa.ForeignKey("`order`.id"), nullable=False),
        sa.Column("consumer_id", sa.String(32), sa.ForeignKey("consumer.id"), nullable=False),
        sa.Column("product_rating", sa.Integer(), nullable=False),
        sa.Column("service_rating", sa.Integer(), nullable=False),
        sa.Column("logistics_rating", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("image_urls", sa.JSON(), nullable=True),
        sa.Column("is_anonymous", sa.Integer(), server_default="0"),
        sa.Column("sentiment", sa.String(10), nullable=True),
        sa.Column("sentiment_intensity", sa.DECIMAL(3, 2), nullable=True),
        sa.Column("themes", sa.JSON(), nullable=True),
        sa.Column("risk_level", sa.String(10), server_default="low"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "evaluation_reply",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("evaluation_id", sa.String(32), sa.ForeignKey("evaluation.id"), nullable=False),
        sa.Column("reply_type", sa.String(10), nullable=False),
        sa.Column("replier_id", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("image_urls", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ── 知识运营域 5 表 ──
    op.create_table(
        "knowledge_item",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("content", MEDIUMTEXT(), nullable=False),
        sa.Column("status", sa.String(10), server_default="启用"),
        sa.Column("source", sa.String(20), server_default="人工创建"),
        sa.Column("source_id", sa.String(32), nullable=True),
        sa.Column("created_by", sa.String(32), sa.ForeignKey("admin.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "after_sale_policy",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Integer(), server_default="1"),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("created_by", sa.String(32), sa.ForeignKey("admin.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "crawl_task",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="待启动"),
        sa.Column("progress", sa.Integer(), server_default="0"),
        sa.Column("total_collected", sa.Integer(), server_default="0"),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(32), sa.ForeignKey("admin.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "crawled_review",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("task_id", sa.String(32), sa.ForeignKey("crawl_task.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("reviewer_nickname", sa.String(100), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("review_time", sa.DateTime(), nullable=True),
        sa.Column("sentiment", sa.String(10), nullable=True),
        sa.Column("themes", sa.JSON(), nullable=True),
        sa.Column("is_processed", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "countermeasure",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("theme", sa.String(50), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(32), nullable=True),
        sa.Column("trigger_condition", sa.Text(), nullable=False),
        sa.Column("reply_template", sa.Text(), nullable=False),
        sa.Column("action_plan", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), server_default="草稿"),
        sa.Column("call_count", sa.Integer(), server_default="0"),
        sa.Column("resolve_rate", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("created_by", sa.String(32), nullable=True),
        sa.Column("reviewer_id", sa.String(32), sa.ForeignKey("admin.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ── 消息通知域 1 表 ──
    op.create_table(
        "notification",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("recipient_id", sa.String(32), nullable=False),
        sa.Column("recipient_type", sa.String(10), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("is_read", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ── 索引 ──
    op.create_index("ix_consumer_phone", "consumer", ["phone"])
    op.create_index("ix_staff_status", "customer_service_staff", ["status"])
    op.create_index("ix_order_consumer", "`order`", ["consumer_id"])
    op.create_index("ix_order_status", "`order`", ["status"])
    op.create_index("ix_order_detail_order", "order_detail", ["order_id"])
    op.create_index("ix_aso_order", "after_sale_order", ["order_id"])
    op.create_index("ix_aso_consumer", "after_sale_order", ["consumer_id"])
    op.create_index("ix_aso_status", "after_sale_order", ["aso_status"])
    op.create_index("ix_conv_consumer", "conversation", ["consumer_id"])
    op.create_index("ix_conv_staff", "conversation", ["staff_id"])
    op.create_index("ix_conv_status", "conversation", ["status"])
    op.create_index("ix_msg_conversation", "message", ["conversation_id"])
    op.create_index("ix_msg_created", "message", ["created_at"])
    op.create_index("ix_eval_order", "evaluation", ["order_id"])
    op.create_index("ix_eval_consumer", "evaluation", ["consumer_id"])
    op.create_index("ix_eval_sentiment", "evaluation", ["sentiment"])
    op.create_index("ix_eval_reply_evaluation", "evaluation_reply", ["evaluation_id"])
    op.create_index("ix_knowledge_type", "knowledge_item", ["type"])
    op.create_index("ix_knowledge_status", "knowledge_item", ["status"])
    op.create_index("ix_countermeasure_theme", "countermeasure", ["theme"])
    op.create_index("ix_countermeasure_status", "countermeasure", ["status"])
    op.create_index("ix_crawl_task_status", "crawl_task", ["status"])
    op.create_index("ix_notif_recipient", "notification", ["recipient_id", "is_read"])
    op.create_index("ix_notif_recipient_id", "notification", ["recipient_id"])

    # ── 种子数据：默认管理员 ──
    op.execute("""
        INSERT INTO admin (id, username, password, name, role, status)
        VALUES ('a00000000000000000000000000001', 'admin', '$2b$12$LJ3m4ys3GZfnYMz8kVsKaOTSxGHLv2VGxB.OmT4hVfMqNOqLqEdeC', '系统管理员', '超级管理员', 1)
    """)
    # 密码: admin123


def downgrade() -> None:
    op.drop_table("notification")
    op.drop_table("countermeasure")
    op.drop_table("crawled_review")
    op.drop_table("crawl_task")
    op.drop_table("after_sale_policy")
    op.drop_table("knowledge_item")
    op.drop_table("evaluation_reply")
    op.drop_table("evaluation")
    op.drop_table("service_record")
    op.drop_table("satisfaction_feedback")
    op.drop_table("session_summary")
    op.drop_table("message")
    op.drop_table("conversation")
    op.drop_table("after_sale_order")
    op.drop_table("order_detail")
    op.drop_table("`order`")
    op.drop_table("product")
    op.drop_table("admin")
    op.drop_table("customer_service_staff")
    op.drop_table("consumer")
