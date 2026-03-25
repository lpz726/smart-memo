#!/usr/bin/env python3
"""
Smart Memo HTTP API 服务
供前端页面调用；MCP 服务器单独运行供 LLM 使用
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import database as db
import ai_service as ai

db.init_db()

PORT = int(os.getenv("API_PORT", "8765"))


class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默日志

    def _send(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        def q(key, default=None):
            vals = qs.get(key, [])
            return vals[0] if vals else default

        if path == "/api/memos":
            category = q("category", "all")
            limit = int(q("limit", 100))
            offset = int(q("offset", 0))
            memos = db.list_memos(category=category, limit=limit, offset=offset)
            stats = db.get_stats()
            self._send({"memos": memos, "stats": stats})

        elif path == "/api/memos/search":
            query = q("q", "")
            results = db.search_memos(query, limit=50) if query else []
            self._send({"results": results, "count": len(results)})

        elif path == "/api/stats":
            self._send(db.get_stats())

        elif path == "/api/schedule":
            date = q("date") or datetime.now().date().isoformat()
            schedules = db.get_schedules(date)
            self._send({"date": date, "schedules": schedules})

        elif path == "/api/categories":
            self._send(ai.CATEGORY_RULES)

        elif path == "/health":
            self._send({"status": "ok", "time": datetime.now().isoformat()})

        else:
            self._send({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._body()

        if path == "/api/memos":
            content = body.get("content", "").strip()
            if not content:
                self._send({"error": "content required"}, 400)
                return
            use_ai = body.get("use_ai", True)
            classification = ai.classify_with_ai(content) if use_ai else ai.classify_local(content)
            time_info = ai.extract_time_local(content)
            scheduled_at = None
            if time_info:
                slot = time_info.get("time_slot") or "00:00"
                scheduled_at = f"{time_info['date']}T{slot}:00"
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
            self._send({"success": True, "memo": memo}, 201)

        elif path == "/api/schedule/generate":
            date = body.get("date") or datetime.now().date().isoformat()
            memos = db.list_memos(limit=200)
            use_ai = body.get("use_ai", True)
            items = ai.generate_schedule_with_ai(memos, date) if use_ai else []
            saved = []
            for item in items:
                s = db.add_schedule(
                    memo_id=item.get("memo_id"),
                    date=date,
                    time_slot=item.get("time_slot"),
                    title=item.get("title", "")[:40],
                    description=item.get("description"),
                    priority=item.get("priority", "medium"),
                )
                saved.append(s)
            self._send({"date": date, "schedules": saved})

        elif path == "/api/classify":
            text = body.get("text", "")
            result = ai.classify_with_ai(text)
            time_info = ai.extract_time_local(text)
            self._send({**result, "time_info": time_info})

        else:
            self._send({"error": "Not found"}, 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        body = self._body()

        # PUT /api/memos/:id
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "memos":
            memo_id = int(parts[2])
            memo = db.update_memo(memo_id, **{
                k: v for k, v in body.items()
                if k in ("content", "category", "priority", "tags")
            })
            if memo:
                self._send({"success": True, "memo": memo})
            else:
                self._send({"error": "not found"}, 404)
        else:
            self._send({"error": "Not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")

        # DELETE /api/memos/:id
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "memos":
            memo_id = int(parts[2])
            success = db.delete_memo(memo_id)
            self._send({"success": success})
        else:
            self._send({"error": "Not found"}, 404)


def run():
    server = HTTPServer(("0.0.0.0", PORT), APIHandler)
    print(f"Smart Memo API 运行在 http://localhost:{PORT}")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    run()
