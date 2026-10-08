"""NotificationService — 消息通知管理"""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_models import Notification


class NotificationService:
    """通知服务"""

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        recipient_id: str,
        recipient_type: str,
        type: str,
        title: str,
        content: str | None = None,
        link: str | None = None,
    ) -> dict:
        """创建通知"""
        notification = Notification(
            id=uuid.uuid4().hex,
            recipient_id=recipient_id,
            recipient_type=recipient_type,
            type=type,
            title=title,
            content=content,
            link=link,
            is_read=0,
        )
        db.add(notification)
        await db.flush()

        return {
            "id": notification.id,
            "recipient_id": notification.recipient_id,
            "recipient_type": notification.recipient_type,
            "type": notification.type,
            "title": notification.title,
            "content": notification.content,
            "link": notification.link,
            "is_read": notification.is_read,
            "created_at": str(notification.created_at) if notification.created_at else "",
        }

    @staticmethod
    async def get_notifications(
        db: AsyncSession,
        recipient_id: str,
        recipient_type: str,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ) -> dict:
        """获取通知列表"""
        base_query = select(Notification).where(
            Notification.recipient_id == recipient_id,
            Notification.recipient_type == recipient_type,
        )
        count_query = select(func.count(Notification.id)).where(
            Notification.recipient_id == recipient_id,
            Notification.recipient_type == recipient_type,
        )

        if unread_only:
            base_query = base_query.where(Notification.is_read == 0)
            count_query = count_query.where(Notification.is_read == 0)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await db.execute(
            base_query.order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        notifications = result.scalars().all()

        items = []
        for n in notifications:
            items.append({
                "id": n.id,
                "recipient_id": n.recipient_id,
                "recipient_type": n.recipient_type,
                "type": n.type,
                "title": n.title,
                "content": n.content,
                "link": n.link,
                "is_read": n.is_read,
                "created_at": str(n.created_at) if n.created_at else "",
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def mark_read(db: AsyncSession, notification_id: str) -> None:
        """标记单条通知为已读"""
        result = await db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="通知不存在",
            )

        notification.is_read = 1
        await db.flush()

    @staticmethod
    async def mark_all_read(
        db: AsyncSession,
        recipient_id: str,
        recipient_type: str,
    ) -> None:
        """标记所有通知为已读"""
        await db.execute(
            update(Notification)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.recipient_type == recipient_type,
                Notification.is_read == 0,
            )
            .values(is_read=1)
        )
        await db.flush()

    @staticmethod
    async def get_unread_count(
        db: AsyncSession,
        recipient_id: str,
        recipient_type: str,
    ) -> int:
        """获取未读通知数"""
        result = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.recipient_id == recipient_id,
                Notification.recipient_type == recipient_type,
                Notification.is_read == 0,
            )
        )
        return result.scalar() or 0
