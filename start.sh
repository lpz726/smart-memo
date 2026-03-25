#!/bin/bash
# ── Smart Memo 一键启动脚本 ────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"
PYTHON="$VENV/bin/python"

echo "🧠 Smart Memo 启动中..."

# 检查虚拟环境
if [ ! -f "$PYTHON" ]; then
  echo "⚠️  未找到虚拟环境，正在创建..."
  python3.12 -m venv "$VENV"
  "$VENV/bin/pip" install -q mcp anthropic python-dotenv
fi

# 加载 .env（如存在）
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# 清理旧进程
kill $(lsof -ti:8765) 2>/dev/null || true

echo "🚀 启动 HTTP API 服务 (端口 8765)..."
"$PYTHON" "$SCRIPT_DIR/server/api_server.py" &
API_PID=$!

sleep 1

# 检测是否成功启动
if kill -0 $API_PID 2>/dev/null; then
  echo "✅ API 服务已启动 (PID: $API_PID)"
else
  echo "❌ API 服务启动失败，请检查错误信息"
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📌 前端界面: 用浏览器打开"
echo "     $(cd "$SCRIPT_DIR/frontend" && pwd)/index.html"
echo ""
echo "  🔌 MCP 服务器: Claude Code 启动时自动激活"
echo "     命令: $PYTHON $SCRIPT_DIR/server/mcp_server.py"
echo ""
echo "  🔑 配置 Claude API Key（可选，启用 AI 分类）:"
echo "     export ANTHROPIC_API_KEY=sk-ant-..."
echo "     或写入 $SCRIPT_DIR/.env"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "按 Ctrl+C 停止服务"

# 等待
wait $API_PID
