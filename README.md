# 🧠 Smart Memo — 智能备忘录

> 自动分类 · AI 驱动 · MCP 协议 · 行程规划

一个支持 **MCP 协议**的智能备忘录系统，可让 Claude、GPT 等大模型直接操作你的本地备忘数据。

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 🤖 AI 自动分类 | 接入 Claude API，8 大类别智能识别（工作/生活/学习/健康/购物/想法/出行/其他） |
| 🕐 时间提取 | 自动识别"明天上午9点"等中文时间表达，生成行程 |
| 🔌 MCP 协议 | 标准 MCP 服务器，Claude Code 直接调用工具操作备忘 |
| 🎤 语音输入 | 浏览器语音识别，支持语音添加备忘 |
| 📅 行程规划 | AI 自动将备忘转化为每日行程时间线 |
| 🔊 行程播报 | 文字转语音朗读当日行程 |
| 💾 SQLite 持久化 | 本地数据库存储，无需云端 |
| 📡 REST API | 前端通过 HTTP API 与后端通信 |

---

## 项目结构

```
smart-memo/
├── server/
│   ├── mcp_server.py    # MCP 服务器（供 Claude Code 使用）
│   ├── api_server.py    # HTTP REST API（供前端使用）
│   ├── database.py      # SQLite 数据库操作
│   ├── ai_service.py    # Claude API + 本地规则分类
│   └── requirements.txt
├── frontend/
│   ├── index.html       # 主页面
│   ├── css/style.css    # 样式
│   └── js/
│       ├── app.js       # 应用主逻辑
│       ├── api.js       # API 客户端
│       └── voice.js     # 语音模块
├── data/                # SQLite 数据库（自动创建）
├── venv/                # Python 虚拟环境
├── .env.example         # 环境变量示例
├── start.sh             # 一键启动脚本
└── README.md
```

---

## 快速开始

### 1. 启动服务

```bash
cd ~/claude/smart-memo
chmod +x start.sh
./start.sh
```

### 2. 打开前端

用浏览器打开 `frontend/index.html`（需要本地 HTTP 服务，或直接双击）

### 3. 配置 Claude API（可选）

```bash
cp .env.example .env
# 编辑 .env，填写 ANTHROPIC_API_KEY
```

无 API Key 时自动使用本地关键词规则分类，仍可正常使用。

---

## MCP 工具列表

Claude Code 中可直接调用以下工具：

```
add_memo(content, use_ai)          添加备忘录
get_memos(category, limit)         获取备忘列表
search_memos(query, limit)         搜索备忘
update_memo(id, ...)               更新备忘
delete_memo(id)                    删除备忘
get_schedule(date)                 获取行程
generate_schedule(date, use_ai)    AI 生成行程
classify_text(text)                文本分类（不保存）
get_stats()                        统计信息
```

---

## Claude Code 集成

MCP 服务器已自动注册到 `~/.claude/settings.json`，重启 Claude Code 即可生效。

在对话中可以直接说：
- 「帮我记一下明天下午3点开会」
- 「查看我今天的所有工作备忘」
- 「搜索关于项目的备忘录」
- 「生成今天的行程安排」

---

## 技术栈

- **后端**: Python 3.12 · MCP SDK · SQLite · 标准库 HTTP 服务
- **AI**: Anthropic Claude API（可选）
- **前端**: 原生 HTML5/CSS3/ES Modules
- **协议**: MCP (Model Context Protocol)
