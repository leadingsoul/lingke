"""KnowledgeService — 智能知识库管理"""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_models import KnowledgeItem


class KnowledgeService:
    """知识库服务"""

    @staticmethod
    async def list_items(
        db: AsyncSession,
        type: str | None = None,
        tag: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """知识条目列表"""
        base_query = select(KnowledgeItem)
        count_query = select(func.count(KnowledgeItem.id))

        if type:
            base_query = base_query.where(KnowledgeItem.type == type)
            count_query = count_query.where(KnowledgeItem.type == type)

        if tag:
            # JSON 字段中包含指定标签
            base_query = base_query.where(
                func.json_contains(KnowledgeItem.tags, f'"{tag}"')
            )
            count_query = count_query.where(
                func.json_contains(KnowledgeItem.tags, f'"{tag}"')
            )

        if keyword:
            like_filter = or_(
                KnowledgeItem.title.ilike(f"%{keyword}%"),
                KnowledgeItem.content.ilike(f"%{keyword}%"),
            )
            base_query = base_query.where(like_filter)
            count_query = count_query.where(like_filter)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await db.execute(
            base_query.order_by(KnowledgeItem.updated_at.desc().nullslast(), KnowledgeItem.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = result.scalars().all()

        return {
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "type": item.type,
                    "tags": item.tags,
                    "content": item.content,
                    "status": item.status,
                    "source": item.source,
                    "created_by": item.created_by,
                    "created_at": str(item.created_at) if item.created_at else "",
                    "updated_at": str(item.updated_at) if item.updated_at else None,
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def create_item(
        db: AsyncSession,
        data: dict,
        admin_id: str,
    ) -> dict:
        """创建知识条目"""
        item = KnowledgeItem(
            id=uuid.uuid4().hex,
            title=data.get("title", ""),
            type=data.get("type", "FAQ"),
            tags=data.get("tags"),
            content=data.get("content", ""),
            status=data.get("status", "启用"),
            source="人工创建",
            created_by=admin_id,
        )
        db.add(item)
        await db.flush()

        return {
            "id": item.id,
            "title": item.title,
            "type": item.type,
            "tags": item.tags,
            "content": item.content,
            "status": item.status,
            "source": item.source,
            "created_by": item.created_by,
            "created_at": str(item.created_at) if item.created_at else "",
            "updated_at": str(item.updated_at) if item.updated_at else None,
        }

    @staticmethod
    async def update_item(
        db: AsyncSession,
        item_id: str,
        data: dict,
    ) -> dict:
        """更新知识条目"""
        result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="知识条目不存在",
            )

        if "title" in data and data["title"] is not None:
            item.title = data["title"]
        if "type" in data and data["type"] is not None:
            item.type = data["type"]
        if "tags" in data and data["tags"] is not None:
            item.tags = data["tags"]
        if "content" in data and data["content"] is not None:
            item.content = data["content"]
        if "status" in data and data["status"] is not None:
            item.status = data["status"]

        await db.flush()

        return {
            "id": item.id,
            "title": item.title,
            "type": item.type,
            "tags": item.tags,
            "content": item.content,
            "status": item.status,
            "source": item.source,
            "created_by": item.created_by,
            "created_at": str(item.created_at) if item.created_at else "",
            "updated_at": str(item.updated_at) if item.updated_at else None,
        }

    @staticmethod
    async def delete_item(
        db: AsyncSession,
        item_id: str,
    ) -> None:
        """软删除知识条目（设为停用）"""
        result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="知识条目不存在",
            )

        item.status = "停用"
        await db.flush()

    @staticmethod
    async def batch_import(
        db: AsyncSession,
        file_data: list[dict],
        file_type: str,
    ) -> dict:
        """批量导入知识条目（mock）"""
        import logging
        logger = logging.getLogger(__name__)

        success_count = 0
        fail_count = 0
        # Mock: 假设 file_data 已经是解析后的列表
        for row in file_data[:100]:  # 最多 100 条
            try:
                item = KnowledgeItem(
                    id=uuid.uuid4().hex,
                    title=row.get("title", "Untitled"),
                    type=row.get("type", "FAQ"),
                    tags=row.get("tags"),
                    content=row.get("content", ""),
                    status="启用",
                    source="批量导入",
                )
                db.add(item)
                success_count += 1
            except Exception:
                fail_count += 1

        await db.flush()
        logger.info(f"[BatchImport] Imported {success_count}/{success_count + fail_count} items from {file_type}")

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "total": success_count + fail_count,
        }

    @staticmethod
    async def search_semantic(
        db: AsyncSession,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """语义搜索（mock: 使用 MySQL LIKE 搜索）"""
        keywords = [kw for kw in query.split() if len(kw) >= 2]
        if not keywords:
            return []

        conditions = []
        for kw in keywords[:3]:
            conditions.append(KnowledgeItem.title.ilike(f"%{kw}%"))
            conditions.append(KnowledgeItem.content.ilike(f"%{kw}%"))

        result = await db.execute(
            select(KnowledgeItem)
            .where(
                KnowledgeItem.status == "启用",
                or_(*conditions),
            )
            .limit(top_k)
        )
        items = result.scalars().all()

        return [
            {
                "id": item.id,
                "title": item.title,
                "type": item.type,
                "content": item.content[:300],
                "score": 0.8,  # mock score
            }
            for item in items
        ]
