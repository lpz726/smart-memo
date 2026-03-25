#!/usr/bin/env python3
"""
Smart Memo MCP Server
支持 Claude、GPT 等主流大模型通过 MCP 协议操作智能备忘录
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# 确保能找到同级模块
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
import database as db
import ai_service as ai

# 初始化数据库
db.init_db()

mcp = FastMCP(
    name="smart-memo",
    instructions=(
        "智能备忘录 MCP 服务。支持添加、查询、搜索、删除备忘录，"
        "以及 AI 自动分类、行程规划等功能。"
        "类别: work(工作) life(生活) study(学习) health(健康) "
        "shopping(购物) ideas(想法) travel(出行) other(其他)"
    ),
)


# ── 备忘录工具 ─────────────────────────────────────────────────────────────

@mcp.tool()
def add_memo(content: str, use_ai: bool = True) -> dict:
    """
    添加一条新备忘录，AI 自动分类、提取时间、判断优先级。

    Args:
        content: 备忘录内容
        use_ai:  是否调用 AI（需配置 ANTHROPIC_API_KEY），默认 True
    Returns:
        新建备忘录对象
    """
    if use_ai:
        classification = ai.classify_with_ai(content)
    else:
        classification = ai.classify_local(content)

    time_info = ai.extract_time_local(content)
    scheduled_at = None
    if time_info:
        date = time_info["date"]
        slot = time_info.get("time_slot") or "00:00"
        scheduled_at = f"{date}T{slot}:00"

    # AI 返回的 scheduled_at 优先
    if classification.get("scheduled_at"):
        scheduled_at = classification["scheduled_at"]

    memo = db.add_memo(
        content=content,
        category=classification.get("category", "other"),
        confidence=classification.get("confidence", 0),
        tags=classification.get("tags", []),
        priority=classification.get("priority", "medium"),
        scheduled_at=scheduled_at,
    )

    # 如果有时间信息，同步写入行程表
    if scheduled_at:
        date_part = scheduled_at[:10]
        time_part = scheduled_at[11:16] if len(scheduled_at) > 10 else None
        db.add_schedule(
            memo_id=memo["id"],
            date=date_part,
            time_slot=time_part,
            title=content[:40],
            description=content,
            priority=memo["priority"],
        )

    return {"success": True, "memo": memo}


@mcp.tool()
def get_memos(category: str = "all", limit: int = 50, offset: int = 0) -> dict:
    """
    获取备忘录列表，支持按类别筛选。

    Args:
        category: 类别筛选（all / work / life / study / health / shopping / ideas / travel / other）
        limit:    最多返回条数（默认 50）
        offset:   分页偏移
    Returns:
        包含备忘录列表和统计信息的对象
    """
    memos = db.list_memos(category=category, limit=limit, offset=offset)
    stats = db.get_stats()
    return {"memos": memos, "stats": stats, "count": len(memos)}


@mcp.tool()
def search_memos(query: str, limit: int = 20) -> dict:
    """
    全文搜索备忘录。

    Args:
        query: 搜索关键词
        limit: 最多返回条数
    Returns:
        匹配的备忘录列表
    """
    results = db.search_memos(query=query, limit=limit)
    return {"results": results, "count": len(results), "query": query}


@mcp.tool()
def update_memo(
    memo_id: int,
    content: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    tags: list | None = None,
) -> dict:
    """
    更新备忘录字段。

    Args:
        memo_id:  备忘录 ID
        content:  新内容（可选）
        category: 新类别（可选）
        priority: 新优先级 urgent/high/medium/low（可选）
        tags:     新标签列表（可选）
    Returns:
        更新后的备忘录对象
    """
    fields = {}
    if content is not None:
        fields["content"] = content
    if category is not None:
        fields["category"] = category
    if priority is not None:
        fields["priority"] = priority
    if tags is not None:
        fields["tags"] = tags

    memo = db.update_memo(memo_id, **fields)
    if not memo:
        return {"success": False, "error": f"备忘录 #{memo_id} 不存在"}
    return {"success": True, "memo": memo}


@mcp.tool()
def delete_memo(memo_id: int) -> dict:
    """
    删除指定备忘录。

    Args:
        memo_id: 备忘录 ID
    Returns:
        操作结果
    """
    success = db.delete_memo(memo_id)
    if success:
        return {"success": True, "message": f"备忘录 #{memo_id} 已删除"}
    return {"success": False, "error": f"备忘录 #{memo_id} 不存在"}


# ── 行程工具 ───────────────────────────────────────────────────────────────

@mcp.tool()
def get_schedule(date: str | None = None) -> dict:
    """
    获取指定日期的行程安排。

    Args:
        date: 日期（ISO 格式 YYYY-MM-DD），默认今天
    Returns:
        行程列表
    """
    if not date:
        date = datetime.now().date().isoformat()
    schedules = db.get_schedules(date=date)
    return {"date": date, "schedules": schedules, "count": len(schedules)}


@mcp.tool()
def generate_schedule(date: str | None = None, use_ai: bool = True) -> dict:
    """
    利用 AI 根据当前备忘录自动规划指定日期的行程。

    Args:
        date:   目标日期（ISO 格式），默认今天
        use_ai: 是否调用 AI
    Returns:
        生成的行程列表
    """
    if not date:
        date = datetime.now().date().isoformat()

    # 获取所有备忘录
    memos = db.list_memos(limit=200)

    if use_ai:
        items = ai.generate_schedule_with_ai(memos, date)
    else:
        items = [
            m for m in memos
            if m.get("scheduled_at", "").startswith(date)
        ]

    saved = []
    for item in items:
        s = db.add_schedule(
            memo_id=item.get("memo_id"),
            date=date,
            time_slot=item.get("time_slot"),
            title=item.get("title", ""),
            description=item.get("description"),
            priority=item.get("priority", "medium"),
        )
        saved.append(s)

    return {"date": date, "schedules": saved, "count": len(saved)}


# ── AI 分类工具 ────────────────────────────────────────────────────────────

@mcp.tool()
def classify_text(text: str) -> dict:
    """
    对任意文本进行 AI 智能分类（不保存到数据库）。

    Args:
        text: 需要分类的文本
    Returns:
        分类结果（category, confidence, tags, priority）
    """
    result = ai.classify_with_ai(text)
    time_info = ai.extract_time_local(text)
    return {**result, "time_info": time_info}


@mcp.tool()
def get_stats() -> dict:
    """
    获取备忘录统计信息（总数、各类别数量、今日行程数）。
    """
    return db.get_stats()


# ── Resource：类别定义 ─────────────────────────────────────────────────────

@mcp.resource("memo://categories")
def get_categories() -> str:
    """返回所有支持的备忘录类别定义"""
    import json
    return json.dumps(ai.CATEGORY_RULES, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
