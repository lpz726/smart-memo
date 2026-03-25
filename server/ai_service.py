"""AI 分类与行程提取服务，支持 Claude 及通用 OpenAI 兼容接口"""
import os
import json
import re
from datetime import datetime, timedelta

# ── 本地关键词规则（无 API 时的回退） ─────────────────────────────────────

CATEGORY_RULES = {
    "work": {
        "name": "工作",
        "icon": "briefcase",
        "keywords": ["会议", "报告", "项目", "客户", "deadline", "DDL", "提交", "汇报",
                     "上班", "同事", "老板", "需求", "开发", "测试", "发布", "review",
                     "邮件", "合同", "谈判", "拜访"],
    },
    "life": {
        "name": "生活",
        "icon": "home",
        "keywords": ["吃饭", "睡觉", "购物", "超市", "家里", "家务", "做饭", "洗衣",
                     "打扫", "整理", "水电", "缴费", "快递", "外卖", "约会", "聚餐"],
    },
    "study": {
        "name": "学习",
        "icon": "book",
        "keywords": ["学习", "课程", "考试", "复习", "作业", "论文", "读书", "笔记",
                     "培训", "证书", "技能", "编程", "英语", "单词", "背诵"],
    },
    "health": {
        "name": "健康",
        "icon": "heart",
        "keywords": ["医院", "体检", "药", "锻炼", "运动", "健身", "跑步", "瑜伽",
                     "看病", "复诊", "预约", "营养", "睡眠", "休息", "减肥"],
    },
    "shopping": {
        "name": "购物",
        "icon": "shopping-cart",
        "keywords": ["买", "购买", "下单", "网购", "淘宝", "京东", "优惠", "折扣",
                     "促销", "清单", "采购", "囤货", "补货", "礼物"],
    },
    "ideas": {
        "name": "想法",
        "icon": "lightbulb",
        "keywords": ["想法", "灵感", "创意", "点子", "计划", "目标", "梦想", "构思",
                     "方案", "建议", "改进", "优化", "创新", "思考"],
    },
    "travel": {
        "name": "出行",
        "icon": "plane",
        "keywords": ["出行", "旅行", "旅游", "机票", "火车", "高铁", "订酒店", "景点",
                     "行程", "签证", "护照", "出发", "抵达", "转机"],
    },
    "other": {
        "name": "其他",
        "icon": "tag",
        "keywords": [],
    },
}

TIME_PATTERNS = [
    (r"(\d{1,2})[：:点](\d{0,2})\s*(上午|下午|晚上|早上)?", "specific"),
    (r"(上午|下午|晚上|早上|中午|傍晚)", "period"),
    (r"明天", "relative_day", 1),
    (r"后天", "relative_day", 2),
    (r"下周(一|二|三|四|五|六|日|天)", "next_week"),
    (r"(\d{1,2})月(\d{1,2})[日号]", "date"),
]

PRIORITY_KEYWORDS = {
    "urgent": ["紧急", "立刻", "马上", "ASAP", "urgent", "重要", "关键", "必须", "今天"],
    "high":   ["尽快", "优先", "重点", "高优先级"],
    "low":    ["有空", "闲时", "以后", "之后", "慢慢"],
}


def classify_local(text: str) -> dict:
    """基于关键词的本地分类（回退方案）"""
    scores: dict[str, int] = {}
    for cat, rule in CATEGORY_RULES.items():
        score = sum(1 for kw in rule["keywords"] if kw in text)
        if score:
            scores[cat] = score
    if not scores:
        return {"category": "other", "confidence": 0, "tags": [], "priority": "medium"}

    best = max(scores, key=lambda k: scores[k])
    confidence = min(100, scores[best] * 20)
    priority = _detect_priority(text)
    return {"category": best, "confidence": confidence, "tags": [], "priority": priority}


def extract_time_local(text: str) -> dict | None:
    """从文本提取时间信息（本地规则）"""
    today = datetime.now().date()
    for pat_info in TIME_PATTERNS:
        pattern = pat_info[0]
        kind = pat_info[1]
        m = re.search(pattern, text)
        if not m:
            continue
        if kind == "relative_day":
            delta = pat_info[2]
            target = today + timedelta(days=delta)
            return {"date": target.isoformat(), "time_slot": None}
        if kind == "date":
            month, day = int(m.group(1)), int(m.group(2))
            year = today.year
            target = datetime(year, month, day).date()
            if target < today:
                target = target.replace(year=year + 1)
            return {"date": target.isoformat(), "time_slot": None}
        if kind == "period":
            period_map = {"早上": "08:00", "上午": "10:00", "中午": "12:00",
                          "下午": "14:00", "傍晚": "17:00", "晚上": "19:00"}
            return {"date": today.isoformat(), "time_slot": period_map.get(m.group(1))}
        if kind == "specific":
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            period = m.group(3) or ""
            if period in ("下午", "晚上") and hour < 12:
                hour += 12
            return {"date": today.isoformat(), "time_slot": f"{hour:02d}:{minute:02d}"}
    return None


def _detect_priority(text: str) -> str:
    for level, keywords in PRIORITY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return "high" if level == "urgent" else level
    return "medium"


# ── Claude / OpenAI 兼容 AI 分类 ──────────────────────────────────────────

def classify_with_ai(text: str) -> dict:
    """
    尝试调用 Claude API 进行智能分类，失败时回退到本地规则。
    环境变量:
      ANTHROPIC_API_KEY  - Claude API key
      AI_MODEL           - 模型名称（默认 claude-haiku-4-5-20251001）
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return classify_local(text)

    try:
        import anthropic

        model = os.getenv("AI_MODEL", "claude-haiku-4-5-20251001")
        categories = list(CATEGORY_RULES.keys())
        prompt = f"""分析下面这条备忘录，返回 JSON：
{{
  "category": "{'" | "'.join(categories)}",
  "confidence": 0-100,
  "tags": ["标签1", "标签2"],
  "priority": "urgent|high|medium|low",
  "scheduled_at": "ISO8601 或 null",
  "summary": "一句话摘要"
}}
只返回 JSON，不要其他内容。

备忘录：{text}"""

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # 提取 JSON
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            # 验证 category
            if result.get("category") not in categories:
                result["category"] = "other"
            result.setdefault("confidence", 80)
            result.setdefault("tags", [])
            result.setdefault("priority", "medium")
            result.setdefault("scheduled_at", None)
            return result
    except Exception:
        pass

    return classify_local(text)


def generate_schedule_with_ai(memos: list[dict], date: str) -> list[dict]:
    """
    使用 Claude 将备忘录转换为行程建议。
    无 API 时返回简单映射。
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not memos:
        # 本地生成：有时间信息的备忘直接放入行程
        schedules = []
        for m in memos:
            if m.get("scheduled_at") and m["scheduled_at"].startswith(date):
                schedules.append({
                    "memo_id": m["id"],
                    "date": date,
                    "time_slot": m["scheduled_at"][11:16] if len(m["scheduled_at"]) > 10 else None,
                    "title": m["content"][:30],
                    "description": m["content"],
                    "priority": m.get("priority", "medium"),
                })
        return schedules

    try:
        import anthropic

        model = os.getenv("AI_MODEL", "claude-haiku-4-5-20251001")
        memo_text = "\n".join(f"- [{m['id']}] {m['content']}" for m in memos)
        prompt = f"""根据以下备忘录为 {date} 生成合理的行程安排，返回 JSON 数组：
[
  {{
    "memo_id": 备忘录ID或null,
    "time_slot": "HH:MM 或 null",
    "title": "行程标题",
    "description": "详情",
    "priority": "high|medium|low"
  }}
]
只返回 JSON 数组。

备忘录：
{memo_text}"""

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        arr_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if arr_match:
            items = json.loads(arr_match.group())
            for item in items:
                item["date"] = date
                item.setdefault("priority", "medium")
            return items
    except Exception:
        pass

    return []
