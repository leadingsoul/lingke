"""CrawlerService — 爬虫任务管理（ALL mock）"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_models import CrawlTask, CrawledReview


class CrawlerService:
    """爬虫任务服务（全部为 mock 实现）"""

    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """任务列表"""
        base_query = select(CrawlTask)
        count_query = select(func.count(CrawlTask.id))

        if status:
            base_query = base_query.where(CrawlTask.status == status)
            count_query = count_query.where(CrawlTask.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await db.execute(
            base_query.order_by(CrawlTask.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        tasks = result.scalars().all()

        items = []
        for t in tasks:
            items.append({
                "id": t.id,
                "name": t.name,
                "platform": t.platform,
                "status": t.status,
                "progress": t.progress,
                "total_collected": t.total_collected,
                "last_run_at": str(t.last_run_at) if t.last_run_at else None,
                "created_at": str(t.created_at) if t.created_at else "",
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def create_task(
        db: AsyncSession,
        data: dict,
        admin_id: str,
    ) -> dict:
        """创建爬虫任务"""
        task = CrawlTask(
            id=uuid.uuid4().hex,
            name=data.get("name", ""),
            platform=data.get("platform", ""),
            keywords=data.get("keywords", []),
            frequency=data.get("frequency", "单次"),
            status="待启动",
            progress=0,
            total_collected=0,
            created_by=admin_id,
        )
        db.add(task)
        await db.flush()

        return {
            "id": task.id,
            "name": task.name,
            "platform": task.platform,
            "status": task.status,
            "progress": task.progress,
            "total_collected": task.total_collected,
            "last_run_at": str(task.last_run_at) if task.last_run_at else None,
            "created_at": str(task.created_at) if task.created_at else "",
        }

    @staticmethod
    async def start_task(
        db: AsyncSession,
        task_id: str,
    ) -> dict:
        """启动任务（mock）"""
        result = await db.execute(
            select(CrawlTask).where(CrawlTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在",
            )

        task.status = "运行中"
        task.progress = 10  # mock 初始进度

        # Mock 生成几条爬取结果
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[Crawler] Mock start task {task.name} on {task.platform}")

        for i, kw in enumerate(task.keywords[:3]):
            review = CrawledReview(
                id=uuid.uuid4().hex,
                task_id=task.id,
                platform=task.platform,
                reviewer_nickname=f"用户_{i+1}",
                content=f"关于「{kw}」的{['好评','中评','差评'][i % 3]}：商品{'质量不错' if i%3==0 else '物流有点慢' if i%3==1 else '不太满意'}。",
                rating=[5, 3, 1][i % 3],
                review_time=datetime.now(timezone.utc),
                sentiment=["positive", "neutral", "negative"][i % 3],
                themes=[[kw]],
                is_processed=0,
            )
            db.add(review)

        task.progress = 100
        task.total_collected = (task.total_collected or 0) + len(task.keywords[:3])
        task.status = "已完成" if task.frequency == "单次" else "运行中"
        task.last_run_at = datetime.now(timezone.utc)

        await db.flush()

        return {
            "id": task.id,
            "name": task.name,
            "platform": task.platform,
            "status": task.status,
            "progress": task.progress,
            "total_collected": task.total_collected,
            "last_run_at": str(task.last_run_at) if task.last_run_at else None,
            "created_at": str(task.created_at) if task.created_at else "",
        }

    @staticmethod
    async def pause_task(
        db: AsyncSession,
        task_id: str,
    ) -> dict:
        """暂停任务"""
        result = await db.execute(
            select(CrawlTask).where(CrawlTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在",
            )

        task.status = "已暂停"
        await db.flush()

        return {
            "id": task.id,
            "name": task.name,
            "platform": task.platform,
            "status": task.status,
            "progress": task.progress,
            "total_collected": task.total_collected,
            "last_run_at": str(task.last_run_at) if task.last_run_at else None,
            "created_at": str(task.created_at) if task.created_at else "",
        }

    @staticmethod
    async def stop_task(
        db: AsyncSession,
        task_id: str,
    ) -> dict:
        """停止任务"""
        result = await db.execute(
            select(CrawlTask).where(CrawlTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在",
            )

        task.status = "已完成"
        task.progress = 100
        await db.flush()

        return {
            "id": task.id,
            "name": task.name,
            "platform": task.platform,
            "status": task.status,
            "progress": task.progress,
            "total_collected": task.total_collected,
            "last_run_at": str(task.last_run_at) if task.last_run_at else None,
            "created_at": str(task.created_at) if task.created_at else "",
        }

    @staticmethod
    async def delete_task(
        db: AsyncSession,
        task_id: str,
    ) -> None:
        """删除任务及其爬取结果"""
        result = await db.execute(
            select(CrawlTask).where(CrawlTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在",
            )

        # 删除关联的爬取结果
        review_result = await db.execute(
            select(CrawledReview).where(CrawledReview.task_id == task_id)
        )
        reviews = review_result.scalars().all()
        for review in reviews:
            await db.delete(review)

        await db.delete(task)
        await db.flush()

    @staticmethod
    async def get_logs(
        db: AsyncSession,
        task_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取爬取日志/结果"""
        # 验证任务存在
        task_result = await db.execute(
            select(CrawlTask).where(CrawlTask.id == task_id)
        )
        if task_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在",
            )

        count_result = await db.execute(
            select(func.count(CrawledReview.id)).where(
                CrawledReview.task_id == task_id
            )
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await db.execute(
            select(CrawledReview)
            .where(CrawledReview.task_id == task_id)
            .order_by(CrawledReview.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        reviews = result.scalars().all()

        items = []
        for r in reviews:
            items.append({
                "id": r.id,
                "platform": r.platform,
                "reviewer_nickname": r.reviewer_nickname,
                "content": r.content,
                "rating": r.rating,
                "sentiment": r.sentiment,
                "is_processed": r.is_processed,
                "created_at": str(r.created_at) if r.created_at else "",
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
