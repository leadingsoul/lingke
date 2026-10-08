"""管理员端路由 — 概览 / 知识库 / 客服 / 统计 / 爬虫 / 对策库 / 沉淀 / 进化 / 日志"""

from fastapi import APIRouter, Depends, File, Query, UploadFile
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.core.database import get_db
from app.schemas.admin_schemas import (
    AdminDashboardResponse,
    KnowledgeCreateRequest,
    KnowledgeUpdateRequest,
    KnowledgeItem,
    StaffCreateRequest,
    StaffUpdateRequest,
    StaffItem,
    StaffPerformanceItem,
    StatsQueryRequest,
    ExportRequest,
    AIInsightRequest,
    CrawlTaskCreateRequest,
    CrawlTaskItem,
    CrawledReviewItem,
    SummaryItem,
    SummaryDetail,
    OperationLogItem,
)
from app.services.admin_service import AdminService

router = APIRouter()

DB = (AsyncSession, Depends(get_db))


# ═══════════════ 系统概览 ═══════════════

@router.get("/dashboard", response_model=dict, summary="管理员仪表盘概览")
async def get_dashboard(
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.get_dashboard(db=db)
    return {"code": 200, "message": "查询成功", "data": result}


# ═══════════════ 知识库 ═══════════════

@router.get("/knowledge", response_model=dict, summary="查询知识库列表")
async def get_knowledge_items(
    type: str = Query(None, description="知识类型过滤"),
    tag: str = Query(None, description="标签过滤"),
    keyword: str = Query(None, description="标题/内容搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    items, total = await service.get_knowledge_items(
        type=type, tag=tag, keyword=keyword, page=page, page_size=page_size, db=db,
    )
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.post("/knowledge", response_model=dict, summary="创建知识条目")
async def create_knowledge(
    request: KnowledgeCreateRequest,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.create_knowledge(
        admin_id=current_user["id"], title=request.title, type=request.type,
        tags=request.tags, content=request.content, status=request.status, db=db,
    )
    return {"code": 200, "message": "创建成功", "data": result}


@router.put("/knowledge/{knowledge_id}", response_model=dict, summary="更新知识条目")
async def update_knowledge(
    knowledge_id: str,
    request: KnowledgeUpdateRequest,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.update_knowledge(
        knowledge_id=knowledge_id, title=request.title, type=request.type,
        tags=request.tags, content=request.content, status=request.status, db=db,
    )
    return {"code": 200, "message": "更新成功", "data": result}


@router.delete("/knowledge/{knowledge_id}", response_model=dict, summary="删除知识条目")
async def delete_knowledge(
    knowledge_id: str,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    await service.delete_knowledge(knowledge_id=knowledge_id, db=db)
    return {"code": 200, "message": "删除成功", "data": None}


@router.post("/knowledge/import", response_model=dict, summary="批量导入知识条目")
async def import_knowledge(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.import_knowledge(admin_id=current_user["id"], file=file, db=db)
    return {"code": 200, "message": result.get("message", "导入成功"), "data": result}


# ═══════════════ 客服管理 ═══════════════

@router.get("/staff", response_model=dict, summary="查询客服列表")
async def get_staff(
    status: str = Query(None, description="状态过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    items, total = await service.get_staff(status=status, page=page, page_size=page_size, db=db)
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.post("/staff", response_model=dict, summary="创建客服账号")
async def create_staff(
    request: StaffCreateRequest,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.create_staff(
        admin_id=current_user["id"], username=request.username, password=request.password,
        name=request.name, role=request.role, phone=request.phone, email=request.email,
        max_concurrent=request.max_concurrent, db=db,
    )
    return {"code": 200, "message": "创建成功", "data": result}


@router.put("/staff/{staff_id}", response_model=dict, summary="更新客服信息")
async def update_staff(
    staff_id: str,
    request: StaffUpdateRequest,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.update_staff(
        staff_id=staff_id, name=request.name, role=request.role,
        status=request.status, email=request.email, max_concurrent=request.max_concurrent, db=db,
    )
    return {"code": 200, "message": "更新成功", "data": result}


@router.get("/staff/{staff_id}/performance", response_model=dict, summary="查询客服绩效详情")
async def get_staff_performance(
    staff_id: str,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.get_staff_performance(staff_id=staff_id, db=db)
    return {"code": 200, "message": "查询成功", "data": result}


@router.delete("/staff/{staff_id}", response_model=dict, summary="禁用/启用客服账号（ADM014）")
async def disable_staff(
    staff_id: str,
    action: str = Query("disable", description="disable/enable"),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    await service.disable_staff(staff_id=staff_id, action=action, db=db)
    msg = "客服账号已禁用" if action != "enable" else "客服账号已启用"
    return {"code": 200, "message": msg, "data": None}


# ═══════════════ 统计 ═══════════════

@router.get("/stats/charts", response_model=dict, summary="获取图表统计数据")
async def get_charts(
    start_date: str = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    type: str = Query("day", description="聚合粒度 day/week/month"),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.get_charts(start_date=start_date, end_date=end_date, group_by=type, db=db)
    return {"code": 200, "message": "查询成功", "data": result}


@router.post("/stats/export", summary="导出统计数据")
async def export_statistics(
    request: ExportRequest,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    return await service.export_statistics(
        export_type=request.type, format=request.format,
        start_date=request.start_date, end_date=request.end_date, db=db,
    )


@router.get("/stats/ai-insight", response_model=dict, summary="AI 评价洞察分析")
async def get_ai_insight(
    start_date: str = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.get_ai_insight(start_date=start_date, end_date=end_date, db=db)
    return {"code": 200, "message": "分析完成", "data": result}


# ═══════════════ 爬虫 ═══════════════

@router.get("/crawler/tasks", response_model=dict, summary="查询爬虫任务列表")
async def get_crawl_tasks(
    status: str = Query(None, description="任务状态过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    items, total = await service.get_crawl_tasks(status=status, page=page, page_size=page_size, db=db)
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.post("/crawler/tasks", response_model=dict, summary="创建爬虫任务")
async def create_crawl_task(
    request: CrawlTaskCreateRequest,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.create_crawl_task(
        admin_id=current_user["id"], name=request.name, platform=request.platform,
        keywords=request.keywords, frequency=request.frequency, db=db,
    )
    return {"code": 200, "message": "创建成功", "data": result}


@router.put("/crawler/tasks/{task_id}/start", response_model=dict, summary="启动爬虫任务")
async def start_crawl_task(
    task_id: str,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.start_crawl_task(task_id=task_id, db=db)
    return {"code": 200, "message": "任务已启动", "data": result}


@router.put("/crawler/tasks/{task_id}/pause", response_model=dict, summary="暂停爬虫任务")
async def pause_crawl_task(
    task_id: str,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.pause_crawl_task(task_id=task_id, db=db)
    return {"code": 200, "message": "任务已暂停", "data": result}


@router.put("/crawler/tasks/{task_id}/stop", response_model=dict, summary="停止爬虫任务")
async def stop_crawl_task(
    task_id: str,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.stop_crawl_task(task_id=task_id, db=db)
    return {"code": 200, "message": "任务已停止", "data": result}


@router.delete("/crawler/tasks/{task_id}", response_model=dict, summary="删除爬虫任务")
async def delete_crawl_task(
    task_id: str,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    await service.delete_crawl_task(task_id=task_id, db=db)
    return {"code": 200, "message": "删除成功", "data": None}


@router.get("/crawler/tasks/{task_id}/reviews", response_model=dict, summary="查询爬取评论")
async def get_crawled_reviews(
    task_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    items, total = await service.get_crawled_reviews(task_id=task_id, page=page, page_size=page_size, db=db)
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.get("/crawler/logs", response_model=dict, summary="查询爬虫日志")
async def get_crawl_logs(
    task_id: str = Query(None, description="任务ID过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    items, total = await service.get_crawl_logs(task_id=task_id, page=page, page_size=page_size, db=db)
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


# ═══════════════ 沉淀文档 ═══════════════

@router.get("/summaries", response_model=dict, summary="查询沉淀文档列表")
async def get_summaries(
    review_status: str = Query(None, description="审核状态过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    items, total = await service.get_summaries(
        review_status=review_status, page=page, page_size=page_size, db=db,
    )
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.get("/summaries/{summary_id}", response_model=dict, summary="查询沉淀文档详情")
async def get_summary_detail(
    summary_id: str,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.get_summary_detail(summary_id=summary_id, db=db)
    return {"code": 200, "message": "查询成功", "data": result}


@router.post("/summaries/{summary_id}/review", response_model=dict, summary="审核沉淀文档")
async def review_summary(
    summary_id: str,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.review_summary(summary_id=summary_id, admin_id=current_user["id"], db=db)
    return {"code": 200, "message": "审核完成", "data": result}


@router.post("/summaries/{summary_id}/sync-knowledge", response_model=dict, summary="同步沉淀文档至知识库（LLM提取FAQ+去重）")
async def sync_summary_to_knowledge(
    summary_id: str,
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    result = await service.sync_summary_to_knowledge(summary_id=summary_id, db=db)
    msg_parts = [f"新增{result['imported']}条"]
    if result.get("merged", 0) > 0:
        msg_parts.append(f"合并{result['merged']}条")
    if result.get("skipped", 0) > 0:
        msg_parts.append(f"跳过{result['skipped']}条")
    message_text = f"已同步至知识库（{'，'.join(msg_parts)}）"
    return {"code": 200, "message": message_text, "data": result}


# ═══════════════ 进化引擎 ═══════════════

@router.post("/evolution/trigger", response_model=dict, summary="手动触发进化引擎")
async def trigger_evolution(
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    await service.trigger_evolution(db=db)
    return {"code": 200, "message": "进化引擎已触发", "data": None}


# ═══════════════ 操作日志 ═══════════════

@router.get("/logs", response_model=dict, summary="查询操作日志")
async def get_operation_logs(
    action: str = Query(None, description="操作类型过滤"),
    target_type: str = Query(None, description="目标类型过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    service: AdminService = Depends(),
):
    items, total = await service.get_operation_logs(
        action=action, target_type=target_type, page=page, page_size=page_size, db=db,
    )
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}
