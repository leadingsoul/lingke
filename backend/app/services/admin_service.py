"""AdminService — 管理员端聚合服务"""

import io
import json
import uuid
from datetime import datetime, timezone, timedelta

from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select, func, text, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill

from app.models.user_models import Admin, CustomerServiceStaff, Consumer
from app.models.knowledge_models import (
    KnowledgeItem, CrawlTask, CrawledReview,
)
from app.models.chat_models import Conversation, Message, SatisfactionFeedback, ServiceRecord, SessionSummary
from app.models.aftersale_models import AfterSaleOrder
from app.models.evaluation_models import Evaluation
from app.models.product_models import Order, OrderDetail

class AdminService:
    """管理员端聚合服务"""

    def __init__(self, db=None):
        self.db = db

    # ═══════════════ 仪表盘 ═══════════════

    async def get_dashboard(self, db: AsyncSession = None) -> dict:
        db = db or self.db

        total_users = await db.execute(select(func.count(Consumer.id)))
        total_consultations = await db.execute(select(func.count(Conversation.id)))
        total_tickets = await db.execute(select(func.count(AfterSaleOrder.id)))
        total_evaluations = await db.execute(select(func.count(Evaluation.id)))
        pending_tickets = await db.execute(
            select(func.count(AfterSaleOrder.id)).where(AfterSaleOrder.aso_status == "待审核")
        )
        negative_evals = await db.execute(
            select(func.count(Evaluation.id)).where(Evaluation.sentiment == "negative")
        )
        online_staff = await db.execute(
            select(func.count(CustomerServiceStaff.id)).where(
                CustomerServiceStaff.status == "在线"
            )
        )

        total_evals_val = total_evaluations.scalar() or 0
        negative_val = negative_evals.scalar() or 0
        negative_rate = round(negative_val / total_evals_val * 100, 1) if total_evals_val > 0 else 0.0

        # --- 趋势图：最近 7 天按日聚合 ---
        today = datetime.now(timezone.utc).date()
        week_ago = today - timedelta(days=6)

        # consultation_trend
        cons_rows = await db.execute(
            text("""
                SELECT DATE(created_at) as d, COUNT(*) as cnt
                FROM conversation
                WHERE DATE(created_at) BETWEEN :start AND :end
                GROUP BY DATE(created_at)
                ORDER BY d
            """),
            {"start": week_ago.isoformat(), "end": today.isoformat()}
        )
        cons_map = {str(row.d): row.cnt for row in cons_rows}
        consultation_trend = [
            {"date": (week_ago + timedelta(days=i)).isoformat(),
             "count": cons_map.get((week_ago + timedelta(days=i)).isoformat(), 0)}
            for i in range(7)
        ]

        # ticket_trend
        ticket_rows = await db.execute(
            text("""
                SELECT DATE(created_at) as d, COUNT(*) as cnt
                FROM after_sale_order
                WHERE DATE(created_at) BETWEEN :start AND :end
                GROUP BY DATE(created_at)
                ORDER BY d
            """),
            {"start": week_ago.isoformat(), "end": today.isoformat()}
        )
        ticket_map = {str(row.d): row.cnt for row in ticket_rows}
        ticket_trend = [
            {"date": (week_ago + timedelta(days=i)).isoformat(),
             "count": ticket_map.get((week_ago + timedelta(days=i)).isoformat(), 0)}
            for i in range(7)
        ]

        # sentiment_trend
        sent_rows = await db.execute(
            text("""
                SELECT DATE(created_at) as d, sentiment, COUNT(*) as cnt
                FROM evaluation
                WHERE DATE(created_at) BETWEEN :start AND :end
                GROUP BY DATE(created_at), sentiment
                ORDER BY d
            """),
            {"start": week_ago.isoformat(), "end": today.isoformat()}
        )
        sent_map: dict = {}
        for row in sent_rows:
            d = str(row.d)
            if d not in sent_map:
                sent_map[d] = {"positive": 0, "neutral": 0, "negative": 0}
            sent_map[d][row.sentiment or "neutral"] = row.cnt
        sentiment_trend = [
            {
                "date": (week_ago + timedelta(days=i)).isoformat(),
                **sent_map.get((week_ago + timedelta(days=i)).isoformat(), {"positive": 0, "neutral": 0, "negative": 0}),
            }
            for i in range(7)
        ]

        return {
            "total_users": total_users.scalar() or 0,
            "total_consultations": total_consultations.scalar() or 0,
            "total_tickets": total_tickets.scalar() or 0,
            "total_evaluations": total_evals_val,
            "pending_tickets": pending_tickets.scalar() or 0,
            "negative_sentiment_rate": negative_rate,
            "online_agents": online_staff.scalar() or 0,
            "consultation_trend": consultation_trend,
            "ticket_trend": ticket_trend,
            "sentiment_trend": sentiment_trend,
        }

    # ═══════════════ 知识库 ═══════════════

    async def get_knowledge_items(
        self, type: str = None, tag: str = None, keyword: str = None,
        status: str = None, page: int = 1, page_size: int = 10,
        db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(KnowledgeItem)
        count_query = select(func.count(KnowledgeItem.id))

        if type:
            base_query = base_query.where(KnowledgeItem.type == type)
            count_query = count_query.where(KnowledgeItem.type == type)

        if status:
            base_query = base_query.where(KnowledgeItem.status == status)
            count_query = count_query.where(KnowledgeItem.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(KnowledgeItem.created_at.desc()).offset(offset).limit(page_size)
        )
        items = []
        for k in result.scalars().all():
            items.append({
                "id": k.id,
                "title": k.title,
                "type": k.type,
                "tags": k.tags,
                "content": k.content,
                "status": k.status,
                "source": k.source,
                "created_by": k.created_by,
                "created_at": str(k.created_at) if k.created_at else "",
                "updated_at": str(k.updated_at) if k.updated_at else "",
            })
        return items, total

    async def create_knowledge(
        self, admin_id: str, title: str, type: str, tags: list,
        content: str, status: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        item = KnowledgeItem(
            title=title, type=type, tags=tags, content=content,
            status=status, created_by=admin_id,
        )
        db.add(item)
        await db.flush()
        return {"id": item.id, "title": item.title}

    async def update_knowledge(
        self, knowledge_id: str, title: str = None, type: str = None,
        tags: list = None, content: str = None, status: str = None,
        db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.id == knowledge_id)
        )
        k = result.scalar_one_or_none()
        if k:
            if title is not None:
                k.title = title
            if type is not None:
                k.type = type
            if tags is not None:
                k.tags = tags
            if content is not None:
                k.content = content
            if status is not None:
                k.status = status
            await db.flush()
            return {"id": k.id, "title": k.title}
        return {"id": knowledge_id, "title": ""}

    async def delete_knowledge(self, knowledge_id: str, db: AsyncSession = None):
        db = db or self.db
        result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.id == knowledge_id)
        )
        k = result.scalar_one_or_none()
        if k:
            await db.delete(k)
            await db.flush()

    async def import_knowledge(
        self, admin_id: str, file, db: AsyncSession = None,
    ) -> dict:
        """Multi-format import: supports xlsx/xls/docx/pdf/pptx/html/txt/json/csv.
        For structured Excel files: reads columns (title/type/content/tags).
        For unstructured files: extracts text then uses LLM to parse into knowledge items.
        """
        db = db or self.db
        content = await file.read()
        filename = getattr(file, "filename", "") or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        VALID_TYPES = {"商品知识", "FAQ", "售后政策"}

        # ── Route by format ──
        if ext in ("xlsx", "xls"):
            return await self._import_excel(content, admin_id, VALID_TYPES, db)

        # Unstructured → extract text → LLM parse
        text = await self._extract_text(content, ext)
        if not text or not text.strip():
            return {"imported": 0, "message": "未能从文件中提取到文本内容"}

        return await self._import_via_llm(text, admin_id, VALID_TYPES, filename, db)

    async def _import_excel(self, content: bytes, admin_id: str, valid_types: set, db: AsyncSession) -> dict:
        """Import from structured Excel: expect columns title / type / content / tags."""
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        pending_items = []  # collect first, then dedup
        errors = []

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):  # skip header
            if len(pending_items) >= 100:
                break
            if not row or len(row) < 3:
                continue
            title = str(row[0]).strip() if row[0] else ""
            item_type = str(row[1]).strip() if len(row) > 1 and row[1] else "FAQ"
            item_content = str(row[2]).strip() if len(row) > 2 and row[2] else ""
            tags_raw = str(row[3]).strip() if len(row) > 3 and row[3] else ""

            if not title or not item_content:
                errors.append(f"第{row_idx}行缺少标题或内容")
                continue
            if item_type not in valid_types:
                item_type = "FAQ"

            tags = [t.strip() for t in tags_raw.replace("，", ",").split(",") if t.strip()]
            pending_items.append({
                "title": title, "type": item_type, "content": item_content, "tags": tags,
            })

        wb.close()
        result = await self._import_dedup_and_insert(pending_items, admin_id, "Excel导入", db)
        if errors:
            result["message"] += f"（跳过 {len(errors)} 行格式错误）"
        return result

    async def _extract_text(self, content: bytes, ext: str) -> str:
        """Extract raw text from document bytes."""
        try:
            if ext == "docx":
                from docx import Document
                doc = Document(io.BytesIO(content))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return "\n\n".join(paragraphs)

            elif ext == "pdf":
                import pdfplumber
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    pages = [p.extract_text() or "" for p in pdf.pages]
                return "\n\n".join(pages)

            elif ext in ("pptx", "ppt"):
                from pptx import Presentation
                prs = Presentation(io.BytesIO(content))
                slides = []
                for i, slide in enumerate(prs.slides, 1):
                    texts = [shape.text for shape in slide.shapes if hasattr(shape, "text") and shape.text.strip()]
                    if texts:
                        slides.append(f"--- 第{i}页 ---\n" + "\n".join(texts))
                return "\n\n".join(slides)

            elif ext in ("html", "htm"):
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, "lxml")
                # Remove script/style tags
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                return soup.get_text(separator="\n", strip=True)

            elif ext in ("txt", "json", "csv", "md"):
                return content.decode("utf-8", errors="ignore")

            else:
                # Fallback: try UTF-8 text
                return content.decode("utf-8", errors="ignore")
        except Exception as exc:
            # If structured parse fails, try plain text
            try:
                return content.decode("utf-8", errors="ignore")
            except Exception:
                raise ValueError(f"无法解析文件格式 (.{ext}): {exc}")

    async def _import_via_llm(
        self, text: str, admin_id: str, valid_types: set, filename: str, db: AsyncSession,
    ) -> dict:
        """Use LLM to parse unstructured text into structured knowledge items."""
        # Truncate for LLM — keep it practical
        if len(text) > 12000:
            text = text[:12000] + "\n\n[内容已截断...]"

        prompt = f"""你是一个知识库管理助手。请从以下文档内容中提取知识条目，返回 JSON 数组。

文件来源：{filename}

每个条目的格式：
{{"title": "知识标题（简洁概括）", "type": "商品知识|FAQ|售后政策", "content": "知识内容（Markdown 格式，保留要点和结构）", "tags": ["标签1", "标签2"]}}

规则：
1. type 只能是：商品知识、FAQ、售后政策 之一。优先判断：操作步骤/常见问题→FAQ，商品参数/对比/规格→商品知识，政策/条款/流程→售后政策
2. 将内容拆分成独立的知识条目（最多 10 条），每个条目信息完整、可独立阅读
3. title 应简洁概括该条目的核心主题
4. content 用 Markdown 格式保留层次结构（标题、列表、加粗等）
5. tags 提取 2-5 个关键词作为标签
6. 如果文档只有一个主题，返回一个条目的数组即可

只返回 JSON 数组，不要任何其他文字、解释或 Markdown 代码块标记。

文档内容：
{text}"""

        try:
            from ai_engine.llm_gateway import LLMGateway
            gateway = LLMGateway.from_env()
            raw = gateway.chat_sync(prompt, temperature=0.3, max_tokens=4000)
        except Exception:
            # LLM unavailable → single item with raw text as content
            return await self._fallback_import(text, admin_id, filename, db)

        # Parse LLM response
        try:
            items = json.loads(raw.strip())
            if not isinstance(items, list):
                items = [items]
        except json.JSONDecodeError:
            # Try to extract JSON array from markdown-wrapped response
            import re
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                try:
                    items = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return await self._fallback_import(text, admin_id, filename, db)
            else:
                return await self._fallback_import(text, admin_id, filename, db)

        pending_items = []
        for item_data in items[:100]:
            title = (item_data.get("title") or "").strip()
            item_type = (item_data.get("type") or "FAQ").strip()
            item_content = (item_data.get("content") or "").strip()
            tags = item_data.get("tags") or []

            if not title or not item_content:
                continue
            if item_type not in valid_types:
                item_type = "FAQ"
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
            tags = tags[:10]

            pending_items.append({
                "title": title, "type": item_type, "content": item_content, "tags": tags,
            })

        result = await self._import_dedup_and_insert(pending_items, admin_id, f"智能导入({filename})", db)
        return result

    async def _import_dedup_and_insert(
        self, pending_items: list[dict], admin_id: str, source_label: str, db: AsyncSession,
    ) -> dict:
        """Dedup imported items against all existing knowledge (LLM semantic + rule fallback), then insert/merge."""
        if not pending_items:
            return {"imported": 0, "merged": 0, "skipped": 0, "message": "无有效条目可导入"}

        # Fetch all existing knowledge for dedup comparison
        existing_result = await db.execute(
            select(KnowledgeItem.id, KnowledgeItem.title, KnowledgeItem.type, KnowledgeItem.content)
            .limit(500)
        )
        existing_rows = existing_result.all()
        existing_items = [
            {"id": row[0], "title": row[1], "type": row[2], "content": row[3] or ""}
            for row in existing_rows
        ]

        # Build FAQItem-compatible list for EvolutionEngine.dedup_faqs()
        class _FakeFaq:
            def __init__(self, title, item_type, content, tags):
                self.title = title
                self.type = item_type
                self.content = content
                self.tags = tags

        faqs = [_FakeFaq(
            title=item["title"],
            item_type=item.get("type", "FAQ"),
            content=item["content"],
            tags=item.get("tags", []),
        ) for item in pending_items]

        # LLM 语义去重（三层：LLM → 关键词Jaccard → 精确标题）
        try:
            from app.services.evolution_service import EvolutionService
            engine = EvolutionService._get_evolution_engine()
            decisions = engine.dedup_faqs(faqs, existing_items)
        except Exception:
            from ai_engine.evolution_engine import EvolutionEngine
            decisions = EvolutionEngine._rule_dedup_faqs(faqs, existing_items)

        id_to_item = {item["id"]: item for item in existing_items}
        imported = 0
        merged = 0
        skipped = 0
        now_str = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

        for decision in decisions:
            idx = decision.get("index", -1)
            if idx < 0 or idx >= len(pending_items):
                continue
            item = pending_items[idx]

            if decision["judgement"] == "duplicate" and decision.get("match_id"):
                match_id = decision["match_id"]
                if match_id in id_to_item:
                    existing = id_to_item[match_id]
                    merge_note = decision.get("merge_note", "").strip()
                    if merge_note:
                        append_text = f"\n\n---\n📝 [{now_str} 导入补充] {merge_note}"
                        new_content = (existing["content"] or "") + append_text

                        target = (await db.execute(
                            select(KnowledgeItem).where(KnowledgeItem.id == match_id)
                        )).scalar_one_or_none()
                        if target:
                            target.content = new_content
                            target.hit_count = (target.hit_count or 0) + 1
                    merged += 1
                    continue
                # match_id not found → fall through as new

            # Exact title guard
            exact_titles = {e["title"] for e in existing_items}
            if item["title"] in exact_titles:
                skipped += 1
                continue

            db.add(KnowledgeItem(
                title=item["title"],
                type=item.get("type", "FAQ"),
                content=item["content"],
                tags=item.get("tags", []),
                source=source_label,
                created_by=admin_id,
            ))
            # Track in-memory for batch dedup (prevent inserting same item twice this batch)
            mem_id = f"_new_{imported}"
            existing_items.append({"id": mem_id, "title": item["title"], "type": item.get("type", "FAQ"), "content": item["content"]})
            id_to_item[mem_id] = existing_items[-1]
            imported += 1

        await db.flush()

        parts = [f"成功导入 {imported} 条"]
        if merged > 0:
            parts.append(f"合并 {merged} 条至已有知识")
        if skipped > 0:
            parts.append(f"跳过 {skipped} 条（标题重复）")
        return {"imported": imported, "merged": merged, "skipped": skipped, "message": "，".join(parts)}

    async def _fallback_import(self, text: str, admin_id: str, filename: str, db: AsyncSession) -> dict:
        """Fallback: import the entire document as a single knowledge item, with dedup check."""
        title = filename.rsplit(".", 1)[0] if filename else "导入文档"
        # Truncate content to a reasonable size
        content = text[:8000] + ("\n\n[内容已截断]" if len(text) > 8000 else "")

        result = await self._import_dedup_and_insert(
            [{"title": title, "type": "FAQ", "content": content, "tags": ["导入"]}],
            admin_id, f"文档导入({filename})", db,
        )
        if result["imported"] == 0 and result["merged"] == 0:
            result["message"] = f"LLM 解析未成功，且标题「{title}」与已有知识重复，未执行导入"
        elif result["merged"] > 0:
            result["message"] = f"LLM 解析未成功，但发现与已有知识重合，已合并 1 条（标题：{title}）"
        else:
            result["message"] = f"LLM 解析未成功，已将全文作为 1 条知识导入（标题：{title}）"
        return result

    # ═══════════════ 客服管理 ═══════════════

    async def get_staff(
        self, status: str = None, page: int = 1, page_size: int = 10,
        db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(CustomerServiceStaff)
        count_query = select(func.count(CustomerServiceStaff.id))

        if status:
            base_query = base_query.where(CustomerServiceStaff.status == status)
            count_query = count_query.where(CustomerServiceStaff.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(CustomerServiceStaff.created_at.desc()).offset(offset).limit(page_size)
        )
        items = []
        for s in result.scalars().all():
            items.append({
                "id": s.id,
                "username": s.username,
                "name": s.name,
                "role": s.role,
                "status": s.status,
                "phone": s.phone,
                "email": s.email,
                "max_concurrent": s.max_concurrent,
                "today_handled": 0,
                "satisfaction_rate": 0.0,
                "created_at": str(s.created_at) if s.created_at else "",
            })
        return items, total

    async def create_staff(
        self, admin_id: str, username: str, password: str, name: str,
        role: str, phone: str = None, email: str = None,
        max_concurrent: int = 5, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        from app.core.security import hash_password
        staff = CustomerServiceStaff(
            username=username,
            password=hash_password(password),
            name=name,
            role=role or "普通客服",
            phone=phone,
            email=email,
            max_concurrent=max_concurrent or 5,
        )
        db.add(staff)
        await db.flush()
        return {"id": staff.id, "username": staff.username, "name": staff.name}

    async def update_staff(
        self, staff_id: str, name: str = None, role: str = None,
        status: str = None, email: str = None,
        max_concurrent: int = None, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        result = await db.execute(
            select(CustomerServiceStaff).where(CustomerServiceStaff.id == staff_id)
        )
        s = result.scalar_one_or_none()
        if s:
            if name is not None:
                s.name = name
            if role is not None:
                s.role = role
            if status is not None:
                s.status = status
            if email is not None:
                s.email = email
            if max_concurrent is not None:
                s.max_concurrent = max_concurrent
            await db.flush()
            return {"id": s.id, "name": s.name}
        return {"id": staff_id, "name": ""}

    async def get_staff_performance(
        self, staff_id: str, db: AsyncSession = None,
    ) -> dict:
        """A4：客服绩效 — 总处理量/平均满意度/平均响应时间/7日趋势"""
        db = db or self.db

        # 验证客服存在
        s = await db.get(CustomerServiceStaff, staff_id)
        if s is None:
            return {}

        today = datetime.now(timezone.utc).date()
        week_ago = today - timedelta(days=6)

        # 1. 总处理量 = 该客服关闭的会话数
        total_row = await db.execute(
            text("""
                SELECT COUNT(*) FROM conversation
                WHERE staff_id = :sid AND status = '已关闭'
            """),
            {"sid": staff_id},
        )
        total_handled = total_row.scalar() or 0

        # 2. 平均满意度 = 该客服关闭会话的评价平均分 * 20（5星→100%）
        sat_row = await db.execute(
            text("""
                SELECT COALESCE(AVG(sf.rating) * 20, 0)
                FROM satisfaction_feedback sf
                JOIN conversation c ON sf.conversation_id = c.id
                WHERE c.staff_id = :sid AND c.status = '已关闭'
            """),
            {"sid": staff_id},
        )
        avg_satisfaction = round(float(sat_row.scalar() or 0), 1)

        # 3. 平均响应时间 = 每个已关闭会话的 (首条客服/AI 消息 - 首条用户消息) 的平均秒数
        rt_row = await db.execute(
            text("""
                SELECT COALESCE(AVG(TIMESTAMPDIFF(SECOND, u.first_user_time, u.first_staff_time)), 0)
                FROM (
                    SELECT
                        c.id,
                        (SELECT MIN(m.created_at) FROM message m
                         WHERE m.conversation_id = c.id AND m.sender_type = 'consumer') as first_user_time,
                        (SELECT MIN(m.created_at) FROM message m
                         WHERE m.conversation_id = c.id AND m.sender_type IN ('staff', 'ai')) as first_staff_time
                    FROM conversation c
                    WHERE c.staff_id = :sid AND c.status = '已关闭'
                ) u
                WHERE u.first_staff_time IS NOT NULL
            """),
            {"sid": staff_id},
        )
        avg_response_time = round(float(rt_row.scalar() or 0), 1)

        # 4. 7 日趋势：每日关闭会话数 + 平均满意度
        trend_rows = await db.execute(
            text("""
                SELECT
                    DATE(c.closed_at) as d,
                    COUNT(c.id) as handled,
                    COALESCE(AVG(sf.rating) * 20, 0) as satisfaction
                FROM conversation c
                LEFT JOIN satisfaction_feedback sf ON sf.conversation_id = c.id
                WHERE c.staff_id = :sid AND c.status = '已关闭'
                  AND DATE(c.closed_at) BETWEEN :start AND :end
                GROUP BY DATE(c.closed_at)
                ORDER BY d
            """),
            {"sid": staff_id, "start": week_ago.isoformat(), "end": today.isoformat()},
        )

        trend_map = {}
        for row in trend_rows:
            trend_map[str(row[0])] = {"handled": row[1], "satisfaction": round(float(row[2]), 1)}

        # 填充 7 天空白日期
        daily_stats = []
        for i in range(7):
            day = (week_ago + timedelta(days=i)).isoformat()
            entry = trend_map.get(day, {"handled": 0, "satisfaction": 0})
            daily_stats.append({"date": day, "handled": entry["handled"], "satisfaction": entry["satisfaction"]})

        return {
            "staff_id": s.id,
            "staff_name": s.name,
            "total_handled": total_handled,
            "avg_satisfaction": avg_satisfaction,
            "avg_response_time": avg_response_time,
            "daily_stats": daily_stats,
        }

    async def disable_staff(
        self, staff_id: str, action: str = "disable", db: AsyncSession = None,
    ):
        """ADM014：禁用或重新启用客服账号"""
        db = db or self.db
        result = await db.execute(
            select(CustomerServiceStaff).where(CustomerServiceStaff.id == staff_id)
        )
        s = result.scalar_one_or_none()
        if s is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="客服不存在")
        s.status = "禁用" if action != "enable" else "在线"
        await db.flush()

    # ═══════════════ 统计 ═══════════════

    async def get_charts(
        self, start_date: str = None, end_date: str = None,
        group_by: str = "day", db: AsyncSession = None,
    ) -> dict:
        """统计数据：满意度 / 工单分布 / 客服绩效 / 热点问题 / 商品评分"""
        db = db or self.db

        # 日期过滤
        date_filter = ""
        date_params: dict = {}
        if start_date and end_date:
            date_filter = "WHERE e.created_at BETWEEN :start AND :end"
            date_params = {"start": start_date, "end": end_date + " 23:59:59"}
        elif start_date:
            date_filter = "WHERE e.created_at >= :start"
            date_params = {"start": start_date}
        elif end_date:
            date_filter = "WHERE e.created_at <= :end"
            date_params = {"end": end_date + " 23:59:59"}

        # 1. 满意度分布（SatisfactionFeedback rating 1-5）
        sf_rows = await db.execute(
            text("SELECT rating, COUNT(*) as cnt FROM satisfaction_feedback GROUP BY rating ORDER BY rating")
        )
        satisfaction_stats = [{"rating": int(r[0]), "count": r[1]} for r in sf_rows.all()]

        # 2. 工单类型分布
        ticket_rows = await db.execute(
            select(AfterSaleOrder.aso_type, func.count(AfterSaleOrder.id)).group_by(AfterSaleOrder.aso_type)
        )
        ticket_distribution = [{"type": r[0], "count": r[1]} for r in ticket_rows.all()]

        # 3. 客服绩效：AVG(rating) + 处理量
        perf_rows = await db.execute(
            text("""
                SELECT s.name, COALESCE(AVG(sf.rating), 0) as avg_rating, COUNT(sf.id) as cnt
                FROM customer_service_staff s
                LEFT JOIN conversation c ON c.staff_id = s.id
                LEFT JOIN satisfaction_feedback sf ON sf.conversation_id = c.id
                GROUP BY s.id, s.name
                ORDER BY cnt DESC
            """)
        )
        agent_performance = [
            {"name": r[0], "handled": r[2], "satisfaction": round(float(r[1]), 1)}
            for r in perf_rows.all()
        ]

        # 4. 热点主题：从 Evaluation.themes JSON 展开聚合
        eval_rows = await db.execute(
            select(Evaluation.themes).where(Evaluation.themes != None)
        )
        theme_counts: dict = {}
        for (themes,) in eval_rows.all():
            if isinstance(themes, list):
                for t in themes:
                    if t:
                        theme_counts[t] = theme_counts.get(t, 0) + 1
        hot_topics = sorted(
            [{"topic": k, "count": v} for k, v in theme_counts.items()],
            key=lambda x: x["count"], reverse=True,
        )[:15]

        # 5. 商品评分排行：Evaluation JOIN OrderDetail（跳过 order 表，直接用 order_id）
        prod_sql = """
            SELECT od.product_name,
                   ROUND(AVG(e.product_rating), 1) as avg_rating,
                   COUNT(e.id) as cnt
            FROM evaluation e
            JOIN order_detail od ON od.order_id = e.order_id
        """
        if date_filter:
            prod_sql += " " + date_filter
        prod_sql += " GROUP BY od.product_name ORDER BY cnt DESC, avg_rating DESC LIMIT 15"
        product_rows = await db.execute(text(prod_sql), date_params)
        product_ratings = [
            {"product_name": r[0], "avg_rating": float(r[1]), "count": r[2]}
            for r in product_rows.all()
        ]

        # 6. 情感趋势（最近 30 天）
        today = datetime.now(timezone.utc).date()
        thirty_days_ago = today - timedelta(days=29)
        sent_rows = await db.execute(
            text("""
                SELECT DATE(created_at) as d, sentiment, COUNT(*) as cnt
                FROM evaluation
                WHERE DATE(created_at) BETWEEN :start AND :end
                GROUP BY DATE(created_at), sentiment
                ORDER BY d
            """),
            {"start": thirty_days_ago.isoformat(), "end": today.isoformat()},
        )
        sent_map: dict = {}
        for row in sent_rows:
            d = str(row[0])
            if d not in sent_map:
                sent_map[d] = {"positive": 0, "neutral": 0, "negative": 0}
            sent_map[d][row[1] or "neutral"] = row[2]
        sentiment_trend = [
            {
                "date": (thirty_days_ago + timedelta(days=i)).isoformat(),
                **sent_map.get((thirty_days_ago + timedelta(days=i)).isoformat(), {"positive": 0, "neutral": 0, "negative": 0}),
            }
            for i in range(30)
        ]

        return {
            "satisfaction_stats": satisfaction_stats,
            "ticket_distribution": ticket_distribution,
            "agent_performance": agent_performance,
            "hot_topics": hot_topics,
            "product_ratings": product_ratings,
            "sentiment_trend": sentiment_trend,
        }

    async def export_statistics(
        self, export_type: str, format: str = "xlsx",
        start_date: str = None, end_date: str = None,
        db: AsyncSession = None,
    ) -> StreamingResponse:
        """导出统计数据为 Excel 文件"""
        db = db or self.db

        # 按类型查数据
        if export_type == "satisfaction":
            rows = await db.execute(
                text("""
                    SELECT css.name as staff_name, sf.rating, sf.feedback, sf.created_at
                    FROM satisfaction_feedback sf
                    LEFT JOIN conversation c ON c.id = sf.conversation_id
                    LEFT JOIN customer_service_staff css ON css.id = c.staff_id
                    ORDER BY sf.created_at DESC
                """)
            )
            data = [(r[0] or "未分配", int(r[1]), r[2] or "", str(r[3]) if r[3] else "") for r in rows.all()]
            headers = ["客服姓名", "评分", "反馈内容", "创建时间"]
            filename = "satisfaction_export"
        elif export_type == "ticket":
            rows = await db.execute(
                select(AfterSaleOrder.aso_type, AfterSaleOrder.aso_reason, AfterSaleOrder.aso_status, AfterSaleOrder.created_at)
                .order_by(AfterSaleOrder.created_at.desc())
            )
            data = [(r[0], r[1], r[2], str(r[3]) if r[3] else "") for r in rows.all()]
            headers = ["工单类型", "原因", "状态", "创建时间"]
            filename = "ticket_export"
        elif export_type == "performance":
            rows = await db.execute(
                text("""
                    SELECT s.name, COALESCE(AVG(sf.rating), 0), COUNT(sf.id),
                           COUNT(DISTINCT c.id) as conv_count
                    FROM customer_service_staff s
                    LEFT JOIN conversation c ON c.staff_id = s.id
                    LEFT JOIN satisfaction_feedback sf ON sf.conversation_id = c.id
                    GROUP BY s.id, s.name
                    ORDER BY conv_count DESC
                """)
            )
            data = [(r[0], round(float(r[1]), 1), r[2], r[3]) for r in rows.all()]
            headers = ["客服姓名", "均分", "评价数", "会话数"]
            filename = "performance_export"
        elif export_type == "product_eval":
            rows = await db.execute(
                text("""
                    SELECT od.product_name,
                           ROUND(AVG(e.product_rating), 1) as avg_p,
                           ROUND(AVG(e.service_rating), 1) as avg_s,
                           ROUND(AVG(e.logistics_rating), 1) as avg_l,
                           COUNT(e.id) as cnt
                    FROM evaluation e
                    JOIN order_detail od ON od.order_id = e.order_id
                    GROUP BY od.product_name
                    ORDER BY cnt DESC
                """)
            )
            data = [(r[0], float(r[1]), float(r[2]), float(r[3]), r[4]) for r in rows.all()]
            headers = ["商品名称", "商品均分", "服务均分", "物流均分", "评价数"]
            filename = "product_eval_export"
        else:
            # hot_topics
            eval_rows = await db.execute(select(Evaluation.themes).where(Evaluation.themes != None))
            theme_counts: dict = {}
            for (themes,) in eval_rows.all():
                if isinstance(themes, list):
                    for t in themes:
                        if t:
                            theme_counts[t] = theme_counts.get(t, 0) + 1
            data = [(k, v) for k, v in sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)]
            headers = ["主题", "出现次数"]
            filename = "hot_topics_export"

        # 生成 Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = export_type

        header_font = Font(bold=True, size=12)
        header_fill = PatternFill(start_color="1677FF", end_color="1677FF", fill_type="solid")
        header_font_white = Font(bold=True, size=12, color="FFFFFF")

        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = header_font_white
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for row_idx, row_data in enumerate(data, 2):
            for col_idx, val in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=val)

        # 列宽自适应
        for col_idx in range(1, len(headers) + 1):
            max_width = len(str(headers[col_idx - 1]))
            for row_idx in range(2, len(data) + 2):
                cell_val = ws.cell(row=row_idx, column=col_idx).value
                if cell_val:
                    max_width = max(max_width, len(str(cell_val)))
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_width + 4, 60)

        # 输出到 buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}_{datetime.now().strftime('%Y%m%d')}.xlsx"},
        )

    async def get_ai_insight(
        self, start_date: str = None, end_date: str = None,
        db: AsyncSession = None,
    ) -> dict:
        """AI 评价洞察：LLM 分析评价数据，生成 Markdown 报告"""
        db = db or self.db

        date_label = "全部历史"
        where_sql = "1=1"
        date_params: dict = {}
        if start_date and end_date:
            date_label = f"{start_date} ~ {end_date}"
            where_sql = "e.created_at BETWEEN :dstart AND :dend"
            date_params = {"dstart": start_date, "dend": end_date + " 23:59:59"}
        elif start_date:
            date_label = f"{start_date} 至今"
            where_sql = "e.created_at >= :dstart"
            date_params = {"dstart": start_date}
        elif end_date:
            date_label = f"截止 {end_date}"
            where_sql = "e.created_at <= :dend"
            date_params = {"dend": end_date + " 23:59:59"}

        # 收集差评/中评内容
        neg_sql = f"""
            SELECT e.content, e.product_rating, e.service_rating, e.logistics_rating, e.sentiment
            FROM evaluation e
            WHERE {where_sql} AND e.sentiment IN ('negative', 'neutral')
            ORDER BY e.product_rating ASC
            LIMIT 30
        """
        neg_rows = await db.execute(text(neg_sql), date_params)
        negative_evals = [
            {"content": r[0], "product": r[1], "service": r[2], "logistics": r[3], "sentiment": r[4]}
            for r in neg_rows.all()
        ]

        # 商品评分排行
        prod_sql = f"""
            SELECT od.product_name,
                   ROUND(AVG(e.product_rating), 1) as avg_rating,
                   COUNT(e.id) as cnt
            FROM evaluation e
            JOIN order_detail od ON od.order_id = e.order_id
            WHERE {where_sql}
            GROUP BY od.product_name
            ORDER BY avg_rating DESC
            LIMIT 15
        """
        prod_rows = await db.execute(text(prod_sql), date_params)
        product_rankings = [{"name": r[0], "avg_rating": float(r[1]), "count": r[2]} for r in prod_rows.all()]

        # 整体统计
        stats_sql = f"""
            SELECT COUNT(*) as total,
                   ROUND(AVG(e.product_rating), 1) as avg_p,
                   ROUND(AVG(e.service_rating), 1) as avg_s,
                   ROUND(AVG(e.logistics_rating), 1) as avg_l
            FROM evaluation e
            WHERE {where_sql}
        """
        stats_rows = await db.execute(text(stats_sql), date_params)
        stats = stats_rows.first()
        overall_stats = {
            "total": stats[0] if stats else 0,
            "avg_product": float(stats[1]) if stats and stats[1] else 0,
            "avg_service": float(stats[2]) if stats and stats[2] else 0,
            "avg_logistics": float(stats[3]) if stats and stats[3] else 0,
        }

        # 客服评分统计
        sf_rows = await db.execute(
            text("""
                SELECT ROUND(AVG(rating), 1), COUNT(*),
                       SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END)
                FROM satisfaction_feedback
            """)
        )
        sf_stats = sf_rows.first()
        staff_data = {
            "avg_rating": float(sf_stats[0]) if sf_stats and sf_stats[0] else 0,
            "total": sf_stats[1] if sf_stats else 0,
            "good": sf_stats[2] if sf_stats else 0,
            "bad": sf_stats[3] if sf_stats else 0,
        }

        if not negative_evals and not product_rankings:
            return {"markdown": f"## 📊 AI 评价洞察报告（{date_label}）\n\n暂无评价数据，无法生成分析报告。", "generated_at": datetime.now(timezone.utc).isoformat()}

        # 组装 LLM Prompt
        neg_summary = "\n".join(
            f"- [商品:{e['product']}/服务:{e['service']}/物流:{e['logistics']}] {e['content'][:150]}"
            for e in negative_evals[:15]
        )
        prod_summary = "\n".join(
            f"- {p['name']}：均分 {p['avg_rating']}（{p['count']} 条评价）"
            for p in product_rankings[:8]
        )

        prompt = f"""你是电商数据分析师。请根据以下数据生成一份评价洞察报告。

【时间范围】{date_label}

【整体统计】
总评价数：{overall_stats['total']}
商品均分：{overall_stats['avg_product']}  / 服务均分：{overall_stats['avg_service']}  / 物流均分：{overall_stats['avg_logistics']}
客服均分：{staff_data['avg_rating']}（{staff_data['total']} 条评分，{staff_data['good']} 好评 / {staff_data['bad']} 差评）

【差评/中评内容】
{neg_summary if neg_summary else '（无差评/中评）'}

【商品评分排行】
{prod_summary if prod_summary else '（暂无）'}

【报告要求】
生成一份 Markdown 格式报告，包含三个章节：

### 一、核心问题摘要
从差评中概括 3-5 个核心问题，每条问题附改进建议。若无差评则说明"暂无显著问题"。

### 二、趋势分析
基于评分数据指出：哪个维度（商品/服务/物流）表现最差、哪些商品评分偏低、客服满意度情况。如果样本量较少（<20 条）请在末尾注明。

### 三、商品口碑对比
列出评分较高和偏低的商品，简要分析原因。

要求：语言专业简洁、结论有数据支撑、改进建议具体可落地。直接输出 Markdown，不要 JSON 包裹。"""

        try:
            from ai_engine.llm_gateway import LLMGateway
            gateway = LLMGateway.from_env()
            markdown = gateway.chat_sync(prompt, temperature=0.5, max_tokens=1500)
        except Exception:
            markdown = f"""## 📊 AI 评价洞察报告（{date_label}）

> ⚠️ AI 分析服务暂时不可用，以下为数据摘要。

### 整体数据
- 总评价数：{overall_stats['total']}
- 商品均分：{overall_stats['avg_product']}
- 服务均分：{overall_stats['avg_service']}
- 物流均分：{overall_stats['avg_logistics']}
- 客服均分：{staff_data['avg_rating']}

### 商品评分排行
{prod_summary or '暂无数据'}
"""

        return {
            "markdown": markdown,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ═══════════════ 爬虫 ═══════════════

    async def get_crawl_tasks(
        self, status: str = None, page: int = 1, page_size: int = 10,
        db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(CrawlTask)
        count_query = select(func.count(CrawlTask.id))

        if status:
            base_query = base_query.where(CrawlTask.status == status)
            count_query = count_query.where(CrawlTask.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(CrawlTask.created_at.desc()).offset(offset).limit(page_size)
        )
        items = []
        for t in result.scalars().all():
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
        return items, total

    async def create_crawl_task(
        self, admin_id: str, name: str, platform: str,
        keywords: list, frequency: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        task = CrawlTask(
            name=name, platform=platform, keywords=keywords,
            frequency=frequency, created_by=admin_id,
        )
        db.add(task)
        await db.flush()
        return {"id": task.id, "name": task.name}

    async def _update_task_status(
        self, task_id: str, status: str, db: AsyncSession,
    ) -> dict:
        result = await db.execute(select(CrawlTask).where(CrawlTask.id == task_id))
        t = result.scalar_one_or_none()
        if t:
            t.status = status
            await db.flush()
            return {"id": t.id, "status": t.status}
        return {"id": task_id, "status": ""}

    async def start_crawl_task(self, task_id: str, db: AsyncSession = None) -> dict:
        return await self._update_task_status(task_id, "运行中", db or self.db)

    async def pause_crawl_task(self, task_id: str, db: AsyncSession = None) -> dict:
        return await self._update_task_status(task_id, "已暂停", db or self.db)

    async def stop_crawl_task(self, task_id: str, db: AsyncSession = None) -> dict:
        return await self._update_task_status(task_id, "已完成", db or self.db)

    async def delete_crawl_task(self, task_id: str, db: AsyncSession = None):
        db = db or self.db
        result = await db.execute(select(CrawlTask).where(CrawlTask.id == task_id))
        t = result.scalar_one_or_none()
        if t:
            await db.delete(t)
            await db.flush()

    async def get_crawled_reviews(
        self, task_id: str, page: int = 1, page_size: int = 10,
        db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(CrawledReview).where(CrawledReview.task_id == task_id)
        count_query = select(func.count(CrawledReview.id)).where(CrawledReview.task_id == task_id)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(CrawledReview.created_at.desc()).offset(offset).limit(page_size)
        )
        items = []
        for r in result.scalars().all():
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
        return items, total

    async def get_crawl_logs(
        self, task_id: str = None, page: int = 1, page_size: int = 20,
        db: AsyncSession = None,
    ):
        db = db or self.db
        # Crawl logs could be stored in a separate table, but we simplify
        # by returning crawl tasks as "logs"
        return [], 0

    # ═══════════════ 沉淀文档 ═══════════════

    async def get_summaries(
        self, review_status: str = None, page: int = 1, page_size: int = 10, db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(SessionSummary)
        count_query = select(func.count(SessionSummary.id))

        if review_status:
            base_query = base_query.where(SessionSummary.review_status == review_status)
            count_query = count_query.where(SessionSummary.review_status == review_status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(SessionSummary.created_at.desc()).offset(offset).limit(page_size)
        )
        items = []
        for s in result.scalars().all():
            items.append({
                "id": s.id,
                "conversation_id": s.conversation_id,
                "tags": s.tags,
                "review_status": s.review_status,
                "synced_to_knowledge": s.synced_to_knowledge,
                "reviewer_id": s.reviewer_id,
                "created_at": str(s.created_at) if s.created_at else "",
            })
        return items, total

    async def get_summary_detail(
        self, summary_id: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        result = await db.execute(
            select(SessionSummary).where(SessionSummary.id == summary_id)
        )
        s = result.scalar_one_or_none()
        if s is None:
            return {}
        return {
            "id": s.id,
            "conversation_id": s.conversation_id,
            "content": s.content,
            "tags": s.tags,
            "review_status": s.review_status,
            "synced_to_knowledge": s.synced_to_knowledge,
            "reviewer_id": s.reviewer_id,
            "reviewed_at": str(s.reviewed_at) if s.reviewed_at else None,
            "created_at": str(s.created_at) if s.created_at else "",
        }

    async def review_summary(
        self, summary_id: str, admin_id: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        result = await db.execute(
            select(SessionSummary).where(SessionSummary.id == summary_id)
        )
        s = result.scalar_one_or_none()
        if s:
            s.review_status = "已审核"
            s.reviewer_id = admin_id
            s.reviewed_at = datetime.now(timezone.utc)
            await db.flush()
            return {"id": s.id, "review_status": s.review_status}
        return {"id": summary_id, "review_status": ""}

    async def sync_summary_to_knowledge(
        self, summary_id: str, db: AsyncSession = None,
    ) -> dict:
        """从沉淀文档提取 FAQ 并写入知识库（LLM 语义去重 + 合并）"""
        db = db or self.db
        result = await db.execute(
            select(SessionSummary).where(SessionSummary.id == summary_id)
        )
        s = result.scalar_one_or_none()
        if s is None:
            return {"imported": 0, "merged": 0, "skipped": 0}

        # 使用 EvolutionEngine 从沉淀文档中 LLM 提取 FAQ
        from app.services.evolution_service import EvolutionService
        engine = EvolutionService._get_evolution_engine()

        ai_summary = type('AI_Summary', (), {
            'content': s.content,
            'tags': s.tags or [],
            'conversation_id': s.conversation_id,
        })()
        faqs = engine.extract_faqs_from_summary(ai_summary)

        # 获取现有知识点（id + title + content）
        existing_result = await db.execute(
            select(KnowledgeItem.id, KnowledgeItem.title, KnowledgeItem.type, KnowledgeItem.content)
            .where(KnowledgeItem.source == "进化同步")
            .limit(500)
        )
        existing_rows = existing_result.all()
        existing_items = [
            {"id": row[0], "title": row[1], "type": row[2], "content": row[3] or ""}
            for row in existing_rows
        ]

        # LLM 语义去重（三层：精确标题 → LLM → 关键词兜底）
        decisions = engine.dedup_faqs(faqs, existing_items)

        # 构建 existing_items 的 id→item 映射，方便合并
        id_to_item = {item["id"]: item for item in existing_items}

        imported = 0
        merged = 0
        skipped = 0
        now_str = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

        for decision in decisions:
            idx = decision.get("index", -1)
            if idx < 0 or idx >= len(faqs):
                continue
            faq = faqs[idx]

            if decision["judgement"] == "duplicate" and decision.get("match_id"):
                match_id = decision["match_id"]
                if match_id in id_to_item:
                    # 合并：在已有条目内容末尾追加补充信息
                    existing = id_to_item[match_id]
                    merge_note = decision.get("merge_note", "").strip()
                    if merge_note:
                        append_text = f"\n\n---\n📝 [{now_str} 同步补充] {merge_note}"
                        new_content = (existing["content"] or "") + append_text

                        target = (await db.execute(
                            select(KnowledgeItem).where(KnowledgeItem.id == match_id)
                        )).scalar_one_or_none()
                        if target:
                            target.content = new_content
                            # 递增 hit_count 表示该条目被再次印证/充实
                            target.hit_count = (target.hit_count or 0) + 1
                    merged += 1
                    continue
                else:
                    # match_id 不在 existing_items 中 → 降级为新条目
                    pass

            if decision["judgement"] == "new" or decision.get("match_id") not in id_to_item:
                # 精确标题二次兜底（同一批次或跨批次）
                exact_titles = {item["title"] for item in existing_items}
                if faq.title in exact_titles:
                    skipped += 1
                    continue

                item = KnowledgeItem(
                    id=uuid.uuid4().hex,
                    title=faq.title,
                    type="FAQ",
                    tags=faq.tags,
                    content=faq.content,
                    status="启用",
                    source="进化同步",
                    source_id=s.id,
                )
                db.add(item)
                existing_items.append({"id": item.id, "title": item.title, "type": "FAQ", "content": item.content})
                id_to_item[item.id] = {"id": item.id, "title": item.title, "content": item.content}
                imported += 1

        # 标记沉淀文档已同步 + 自动视为已审核
        s.synced_to_knowledge = True
        if s.review_status == "待审核":
            s.review_status = "已审核"

        await db.flush()
        return {"imported": imported, "merged": merged, "skipped": skipped}

    # ═══════════════ 进化引擎 ═══════════════

    async def trigger_evolution(self, db: AsyncSession = None):
        from app.services.evolution_service import EvolutionService
        await EvolutionService.trigger_evolution_analysis(db=db)


    async def get_operation_logs(
        self, action: str = None, target_type: str = None,
        page: int = 1, page_size: int = 20, db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = (
            select(ServiceRecord, CustomerServiceStaff.name.label("cs_name"))
            .outerjoin(CustomerServiceStaff, ServiceRecord.staff_id == CustomerServiceStaff.id)
        )
        count_query = select(func.count(ServiceRecord.id))

        if action:
            base_query = base_query.where(ServiceRecord.action == action)
            count_query = count_query.where(ServiceRecord.action == action)
        if target_type:
            base_query = base_query.where(ServiceRecord.target_type == target_type)
            count_query = count_query.where(ServiceRecord.target_type == target_type)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(ServiceRecord.created_at.desc()).offset(offset).limit(page_size)
        )

        # 中英文映射
        TARGET_TYPE_CN = {
            "conversation": "会话",
            "ticket": "工单",
            "knowledge": "知识库",
            "policy": "策略",
            "staff": "客服",
            "ai_config": "AI配置",
            "countermeasure": "对策",
            "summary": "沉淀文档",
        }
        ACTION_CN = {
            "reply": "回复",
            "回复": "回复",
            "关闭": "关闭",
            "审核": "审核",
            "删除": "删除",
        }

        items = []
        for r, staff_name in result.all():
            detail = r.detail or "-"
            items.append({
                "id": r.id,
                "staff_id": r.staff_id,
                "staff_name": staff_name or "未知",
                "action": r.action,
                "action_cn": ACTION_CN.get(r.action, r.action),
                "target_type": r.target_type,
                "target_type_cn": TARGET_TYPE_CN.get(r.target_type, r.target_type),
                "target_id": r.target_id,
                "detail": detail if len(detail) <= 200 else detail[:200] + "...",
                "created_at": str(r.created_at) if r.created_at else "",
            })
        return items, total
