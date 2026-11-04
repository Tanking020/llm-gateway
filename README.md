# llm-app-engineering

> 一个从零搭建的 LLM 应用后端。工程规范先行，逐步演进为**带量化评估的中文 RAG 知识库问答服务**。
>
> ⭐⭐ **项目定位：最终要作为产品上线**（2026-10-28 确认）。讲解价值是**附带的**，不是决策依据。
> 每个技术选择都先过这一关：**「如果这个接口明天就要给 1000 个真实用户用，这样做够不够？」**
> 判据与「可以让步 vs 绝不能让步」的清单见[工程规范 §7.0c](工程规范与协作约定.md)。

**当前状态**：阶段 0 · 工程基础已完成；
阶段 1 · FastAPI 服务开发中 —— **Step 1 ~ 12 已完成；71 个用例全绿（含真 uvicorn 并发与穿过适配器的真实 HTTP 路径），服务代码分支覆盖 90%**
（HTTP/ASGI 地基 → 三段参数 → 依赖注入 → 错误处理与 `lifespan` → 中间件与 CORS → 异步正确姿势 → SSE 流式响应 → 上游防御 → 数据库与账单 → 工程化 → 自动化测试）。
已具备：请求追踪中间件、**一个把「上游调用 + 错误翻译」封在一起的适配器**（路由层不出现 `httpx`，且由 lint 强制）、
一个**真调上游 DeepSeek 的 SSE 流式接口**（状态帧 + 正文逐字 + `finish_reason` + token 用量，
实测首帧 60ms / 总 906ms；上游失败时客户端拿 **502** 而不是 `200` + 断连）、
**可对账的账单体系**（`llm_calls` 表，`status` **四态**：`completed` / `aborted` / `no_content` / `pending`，值域用 `StrEnum` 收敛，📎 并发 6 条流时连接池峰值仅 2）、
**全项目统一的错误响应**（任何错误都是 `{"error":{code,message,request_id}}`，422 多一个 `details`）、
**单一出口的日志配置**（`dictConfig`，三条启动路径同一格式）、
**prod 环境的多重保护**（`DEBUG=true` 启动即崩、`/docs` `/redoc` `/openapi.json` 一并关闭）、
**说真话的 `/docs`**（流式接口标 `text/event-stream`），
以及**自动化回归测试**：`tests/` + `TestClient` + 假上游 + `MockTransport`，`uv run pytest` 一条命令跑完 **71 个用例**（含**真 uvicorn 并发测试**与**穿过适配器的真实 HTTP 路径**；**24 次变异测试**证明断言真的有牙）。⭐ 这套测试已经逼出并修掉了两个真缺陷：坏帧吞掉 token 用量、并发流被完全串行化。
详见[路线图](#路线图)。

> ⚠️ **离「能上线」还差什么**：无鉴权 / 无限流 / 无 CI / 无 `Dockerfile` / 无指标，
> 且 `/v1/chat`（非流式）仍是 `echo` 占位实现。完整清单见[路线图待办](study_notes/project/roadmap.md)（#1~#76，**37 已关闭 / 39 未关闭**）。

---

## 这是什么

面向 LLM 应用的**异步后端服务**。与常见的"跑通一个 demo"不同，本项目的重点在**工程地基**：

- 每次结论都有**可复现的环境**支撑（依赖锁定 + 隔离环境 + 精确的 Python 版本）
- 每行代码都过**静态检查**（类型 strict 模式 + 格式化 + lint）
- 每个"为什么这样设计"都写在[开发笔记](study_notes/)里，包括**踩过的坑和定位过程**

业务逻辑目前用 `echo` 占位，随阶段推进替换为真实的 LLM 调用与检索逻辑。

---

## 技术栈

| 层 | 选型 | 当前版本 |
|---|---|---|
| 语言 | Python（由 uv 托管的独立解释器，不依赖系统 Python） | 3.12.15 |
| 环境与依赖 | **uv**（`pyproject.toml` 声明 + `uv.lock` 锁定） | uv 0.12.23 |
| 数据契约与配置 | pydantic / pydantic-settings | 2.13.5 / 2.15.0 |
| 静态检查 | mypy（strict）/ ruff | 2.4.0 / 0.16.10 |
| Web 框架 | FastAPI + uvicorn（ASGI） | 0.143.0 / 0.54.0 |
| 数据库 | SQLAlchemy 2.1 async（2.0 风格 ORM）+ aiosqlite；SQLite → PostgreSQL | 2.1.6 / 0.22.1；Step 10 已完成（依赖 / 模型 / 引擎 / 请求级会话 / 对话 CRUD 四操作五接口 / 账单表 / 游标分页） |
| 测试 | pytest + pytest-asyncio + httpx2（Starlette 1.x 的测试客户端依赖）+ pytest-cov（分支覆盖） | 9.2.0 / 1.4.1 / 2.16.0 / 7.1.0；Step 12 已落地 **71 个用例**，服务代码分支覆盖 **90%** |
| 交付 | Docker（多阶段构建 + 非 root 运行） | 阶段 1 引入 |

依赖分工：**运行必需的**写在 `[project] dependencies`，**仅开发需要的**（mypy / ruff / pytest）写在
`[dependency-groups] dev` —— 生产镜像可以用 `uv sync --frozen --no-dev` 一句排除掉。

---

## 快速开始

前置：安装 [uv](https://docs.astral.sh/uv/)（唯一需要手动准备的工具）。

```bash
git clone https://github.com/Tanking020/llm-app-engineering.git
cd llm-app-engineering

# 1. 按 uv.lock 还原出逐位一致的依赖环境（同时自动装 Python 3.12）
uv sync

# 2. 生成本地配置文件
cp .env.example .env
# Windows PowerShell 用：Copy-Item .env.example .env

# 3. 验证环境（可选）
uv run python -c "from app.config import settings; d = settings.model_dump(); d['llm_api_key'] = '已配置' if d['llm_api_key'] else '未配置'; print(d)"

# 4. 启动 HTTP 服务（推荐走项目自己的入口）
uv run python -m app
# 然后打开 http://127.0.0.1:8000/docs —— 自动生成的交互式 API 文档
```

> ⭐ **为什么用 `uv run python -m app` 而不是 `uvicorn app.api.app:app --reload`**：
> 前者的监听地址 / 端口 / 是否 reload 全部读 `.env` 里的 `HOST` / `PORT` / `DEBUG`；
> 后者会绕过这些配置（`.env` 写 `PORT=9001` 毫无作用，属于**静默失效**）。
>
> 📎 `DEBUG=true` 时日志里会出现 `Started reloader process [...] using WatchFiles`；`DEBUG=false` 则没有。

> 所有命令都用 `uv run` 前缀。原因是 `uv run` 会自动指向项目自己的 `.venv`，
> 并在依赖发生变化时**先自动同步**，避免"装了依赖却仍然导入失败"这类问题。

**另一个入口**：阶段 0 的 CLI 仍可用，用于验证配置与上游 LLM 的连通性（不属于服务）：

```bash
uv run python -m app.main        # 离线演示：打印配置与占位响应
uv run python -m app.main ping   # 真实调用上游 /models，列出可用模型
```

---

## 接口一览（截至阶段 1 · Step 12）

| 方法 | 路径 | 说明 | 主要状态码 |
|---|---|---|---|
| GET | `/health` | **liveness**：只证明进程活着，**不检查外部依赖**（编排系统据此决定要不要重启） | 200 |
| GET | `/health/ready` | **readiness**：探数据库（`SELECT 1`）；失败 → **503** `DB_UNAVAILABLE`，编排系统据此摘流量但不重启 | 200 / 503 |
| GET | `/v1/models` | 硬编码的模型清单；支持 `?prefix=` / `?limit=`（1 ~ 100） | 200 / 422 |
| GET | `/v1/models/latest` | 默认模型 | 200 |
| GET | `/v1/models/{model_name}` | 单个模型；名称不在清单里 → 404 | 200 / 404 |
| POST | `/v1/chat` | 聊天；⚠️ **业务逻辑仍为 `echo` 占位**（待办 #46）；最后一条消息必须是 `user`；可选 `conversation_id`（不存在 → 404） | 200 / 400 / 404 / 422 |
| GET | `/v1/upstream/models` | **真实调用**上游 `/models`，返回 `ModelListResponse` | 200 / 502 |
| POST | `/v1/chat/stream` | **SSE 流式**：真调上游 `stream=true`，逐帧转发回答文字（思维链按产品要求丢弃）；可选 `conversation_id`（不存在 → 404，**在流开始前拦**）；每次调用落一行账单 | 200 / 404 / 422 |
| POST | `/v1/conversations` | 新建对话（落库）；`title` 长度 1~100 | 201 / 422 |
| GET | `/v1/conversations` | **游标分页**列出对话（`?limit=1~100&after_id=N`），含账单统计；响应 `{items, total, limit, next_cursor, has_more}` | 200 / 422 |
| GET | `/v1/conversations/{conv_id}` | 单个对话；不存在 → 404；`conv_id` 非整数 → 422 | 200 / 404 / 422 |
| DELETE | `/v1/conversations/{conv_id}` | 删除对话（204 无内容）；不存在 → 404；⚠️ 计费记录 `SET NULL` 保留 | 204 / 404 / 422 |
| PATCH | `/v1/conversations/{conv_id}` | 修改标题（部分更新）；不存在 → 404；空 body / null / 空串 → 422 | 200 / 404 / 422 |

**成功响应形状**（Step 4 起，`schemas.py` 定义，可在 `/docs` 展开）：

```jsonc
// POST /v1/chat（⚠️ echo 占位）
{"content": "[echo] 你好", "model": "deepseek-flash", "usage_tokens": 0}

// GET /v1/upstream/models —— 上游 10 个键只暴露 3 个（白名单：owned_by / effort 等不外泄）
{"total": 2, "items": [
  {"id": "deepseek-flash", "name": "DeepSeek-V4.1-Flash", "context_window": 1048576},
  {"id": "deepseek-v4-pro", "name": "DeepSeek-V4-Pro", "context_window": 1048576}
]}

// GET /v1/conversations —— 含账单统计（join + group_by，1 条 SQL）
[{"id": 1, "title": "有账单", "created_at": "...", "updated_at": "...",
  "call_count": 2, "total_tokens": 175}]
```

⚠️ **已知形状问题**（剩余待办 #39）：`/v1/models` 与 `/v1/upstream/models` 形状不一致。
~~`created_at` 带不带 `Z`~~（10.6d-4a 已统一为带 `Z`）、~~详情接口不返回 `call_count`~~（10.6d-4b 已统一为 6 字段）。
**分页方案：游标为主 + `total` 为辅**（[决策 #22](study_notes/project/decisions.md)）——
⚠️ 不用 offset 分页，因为📎 实测它在翻页期间删数据会**漏掉一条**。

**错误响应形状**（Step 11d 起，**任何**错误都是同一种形状）：

```jsonc
// 业务错误（400 / 404 …）：code 给机器判断（稳定不变），message 给人看（可改文案）
{"error": {"code": "LAST_MESSAGE_NOT_USER", "message": "最后一条消息必须是 user，当前是 assistant",
           "request_id": "1b085bd5c5b3"}}

// 框架错误：路由不存在 / 方法不允许 —— code 由状态码兜底
{"error": {"code": "NOT_FOUND", "message": "Not Found", "request_id": "a4175e01d830"}}
{"error": {"code": "METHOD_NOT_ALLOWED", "message": "Method Not Allowed", "request_id": "c5bb71007336"}}

// 参数校验失败（422）：多一个 details，只含 loc / msg / type（不回显用户提交的原值）
{"error": {"code": "VALIDATION_ERROR", "message": "请求参数校验失败", "request_id": "7284ed612708",
           "details": [{"loc": ["body", "messages"], "msg": "Field required", "type": "missing"}]}}

// 服务内部错误（500）：只回一句人话 + 请求 ID，堆栈只写服务端日志
{"error": {"code": "INTERNAL_ERROR", "message": "服务内部错误", "request_id": "ef9002e78ef3"}}
```

⭐ **客户端只需认 `code`**，不要匹配 `message`。业务码 → HTTP 状态码的映射集中在
`src/app/errors.py` 的 `_STATUS_BY_CODE`，所有错误响应经同一个出口 `_error_response()` 生成，
`X-Request-ID` 响应头**恒等于** body 里的 `request_id`。

> ✅ 流式接口在 `/docs` 里已正确标成 `text/event-stream`（Step 11f：`SseResponse` 的类属性 `media_type` +
> `response_class=`；只加 `responses={200: …}` 不够，会把 `application/json` 一起留着）。

**SSE 流式响应**（Step 9b-3 起：真调上游 `stream=true`，含状态帧与用量记账）：

请求体与 `POST /v1/chat` 共用同一份契约（`ChatRequest`）。一帧 = `data: <内容>` + **一个空行**（`\n\n`）。实测响应：

```text
HTTP/1.1 200 OK
cache-control: no-cache
x-accel-buffering: no
content-type: text/event-stream; charset=utf-8
transfer-encoding: chunked

data: {"status": "thinking"}          ← 连上立刻发（实测 60ms），不等上游

data: {"delta": "1"}

data: {"delta": " "}

data: {"delta": "2"}

……

data: {"finish_reason": "stop"}       ← 为什么结束（"stop" 说完 / "length" 被截断）

data: {"usage": {"prompt_tokens": 44, "completion_tokens": 63, "total_tokens": 107,
                 "completion_tokens_details": {"reasoning_tokens": 57},
                 "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 44}}

data: [DONE]
```

**五类帧的分工**（我方对外只发这 5 类 + 1 类错误帧）：

| 帧 | 何时发 | 谁用 |
|---|---|---|
| `{"status": "thinking"}` | 请求开始，**在请求上游之前** | 前端显示"思考中"，避免空白期 |
| `{"delta": "..."}` | 上游每吐一个 token | 正文逐字显示 |
| `{"finish_reason": "..."}` | 上游最后一帧 | 区分正常结束 / 被截断（`length`） |
| `{"usage": {...}}` | 上游最后一帧 | 成本计量（含思维链 token） |
| **`{"error": {"code": "STREAM_NO_CONTENT", ...}}`** | 上游**一帧内容都没给**（200 + HTML / 空 body / 忽略 `stream`） | 区分「模型说了空」与「上游没给」——**`response.ok` 是 `true`，前端必须识别这一帧** |
| **`{"error": {"code": "STREAM_FAILED", ...}}`** | 流**中途**出错（坏 JSON / 不可预期的结构） | 同上；**已收到的 `DELTA` 要保留**，但要提示「回答可能不完整」 |
| `[DONE]` | 我方在流末尾**统一发一次** | 前端据此关闭连接 |

⚠️ **流式接口的 `200` 也可能是失败**：响应头一旦发出就改不了状态码，
所以「上游挂了」在流式下只能表达成 **200 + `error` 帧**；而真正的 L1/L2（连不上 / 状态码不对）
已在 **pre-flight** 阶段拦成 **502**（`response.ok === false`）。

**上游 5 类 → 我方 5 类的映射**（正常路径；📎 实测问「从1数到3」：上游 64 帧 → 我方 9 帧）：

| 上游帧 | 数量 | 我方动作 | 我方帧 |
|---|---|---|---|
| `ROLE`（首帧，`delta.role=assistant`） | 1 | 丢弃（`content` 是 `null`） | — |
| `REASONING`（`reasoning_content` 有值） | **56** | 丢弃（产品只显示回答） | — |
| `CONTENT`（`content` 有值） | 5 | 重组为 `{"delta": text}` | `DELTA` |
| `FINISH`（`finish_reason` + `usage` **同帧**） | 1 | **拆成 2 帧** | `FINISH_REASON` + `USAGE` |
| `[DONE]` | 1 | 只用来跳过，**由我方重发** | `DONE` |
| —（我方自造） | — | 在请求上游之前发出 | `THINKING` |

> ⭐ 算一遍：64 − 57（丢弃 ROLE + 思维链）+ 1（THINKING）+ 1（FINISH 拆成 2 帧）= **9** ✅
> 帧的分类与顺序详见[阶段1 笔记](study_notes/learning/stage1-fastapi.md) §9.8d。

```powershell
# 请求体写进临时文件（含中文，避免 PowerShell 转义把 JSON 弄坏）
$body = '{"messages":[{"role":"user","content":"从1数到5，只输出数字，用空格隔开"}]}'
[IO.File]::WriteAllText("$env:TEMP\chat_stream.json", $body, (New-Object System.Text.UTF8Encoding($false)))

# 逐帧看内容（-N = 关掉 curl 自己的输出缓冲，否则看不到"逐字"）
curl.exe -N -s -X POST http://127.0.0.1:8000/v1/chat/stream `
  -H "Content-Type: application/json" --data-binary "@$env:TEMP\chat_stream.json"

# 只看响应头，丢弃 body
curl.exe -s -D - -o NUL -X POST http://127.0.0.1:8000/v1/chat/stream `
  -H "Content-Type: application/json" --data-binary "@$env:TEMP\chat_stream.json"

Remove-Item "$env:TEMP\chat_stream.json"
```

> 🔴 **时序不能用 `curl -w` 的 `ttfb/total` 判**：`time_starttransfer` 量的是**响应头到达**，
> 而流式接口的头是路由立刻发出的（实测 8.9ms）。要证明"内容在流"，必须用**带时间戳的客户端**
> （httpx `iter_text()` + `perf_counter`）量首个数据帧时刻。详见[阶段1 笔记](study_notes/learning/stage1-fastapi.md) §9.3b ③。
>
> ⚠️ `TestClient` 里的 `transfer-encoding` 是 `None` —— 它能验证**帧格式**，证明不了"分批发送"。
> 时序必须用真 uvicorn + 真 HTTP 客户端。

**首帧延迟的前后对比**（📎 同一接口实测）：

| 版本 | 首个 body 帧 | 总耗时 | 占比 |
|---|---|---|---|
| 9b-2（无状态帧） | 845.8ms | 905.7ms | **93%** |
| **9b-3（加 `thinking` 帧）** | **60.0ms** | 906ms | **6.6%** |

**流式的已知限制**（下一步要补）：

| 限制 | 表现 | 归属 |
|---|---|---|
| 上游报错时状态码改不了 | 客户端看到 `200` + 断连（头早已发出） | 9b-4：在开始流**之前**判断上游状态 |
| 客户端断开未处理 | 用户走了仍在烧 token | 9b-4 |

**请求追踪**（Step 7a 起）：每个响应都带 `X-Request-ID` 头。

```text
# 客户端可自带 ID，服务端会原样沿用（跨服务串联用）
curl.exe -i http://127.0.0.1:8000/health -H "X-Request-ID: my-trace-001"
#   -> x-request-id: my-trace-001

# 不带就自动生成；500 时响应头与响应体里的 request_id 完全相同
# 服务端每个请求都有一行访问日志：
#   GET /v1/upstream/models -> 200 157.7ms request_id=c68615732f4e
#   GET /__boom -> ERR 1.1ms request_id=9af3ecfbb812      （ERR = 异常路径上还没有响应对象）
```

**手工验证**（PowerShell 里 `curl` 是 `Invoke-WebRequest` 的别名，必须写 `curl.exe`）：

```powershell
curl.exe -s -i http://127.0.0.1:8000/v1/models/deepseek-flash          # 200
curl.exe -s -i http://127.0.0.1:8000/v1/models/does-not-exist          # 404

# 请求体含中文时写进临时文件，避免 PowerShell 转义把 JSON 弄坏
$body = '{"messages":[{"role":"user","content":"你好"}]}'
[IO.File]::WriteAllText("$env:TEMP\chat.json", $body, (New-Object System.Text.UTF8Encoding($false)))
curl.exe -s -i -X POST http://127.0.0.1:8000/v1/chat -H "Content-Type: application/json" --data-binary "@$env:TEMP\chat.json"
```

---

## 项目结构

```text
.
├── pyproject.toml            # 唯一事实来源：元数据、依赖、构建配置、所有工具配置
├── uv.lock                   # 精确依赖清单（含哈希）—— 提交，保证可复现
├── .python-version           # 本项目使用的 Python 版本（精确指定，而非范围）
├── .gitignore / .gitattributes
├── .env.example              # 配置模板（提交）；真实取值放 .env（不提交）
├── .github/
│   └── copilot-instructions.md   # AI 协作指令：新会话自动加载的语言风格与工作纪律
│
├── src/app/                  # 应用代码
│   ├── __init__.py
│   ├── config.py             # 全部可调参数集中在这里，类型安全且带校验（含 prod 禁 DEBUG 的跨字段校验）
│   ├── logging_setup.py      # 日志配置唯一一处：dictConfig(force=True)，全进程一套格式
│   ├── schemas.py            # 对外数据契约：请求 / 响应的形状定义
│   ├── constants.py          # 必须跨模块一致的常量（HTTP 头名等，只写一处）
│   ├── errors.py             # 业务异常 AppError + 码↔状态码两张映射 + 4 个异常处理器（单一出口 _error_response）
│   ├── llm_client.py         # 上游适配器：唯一 import httpx、唯一翻译上游故障的地方（LlmClient / LlmChatStream）
│   ├── database.py           # 数据库引擎与会话工厂：engine（连接池）+ SessionMaker（造会话的模具）
│   ├── models.py             # ORM 模型：Base 基类 + Conversation 表（Mapped / mapped_column）
│   ├── main.py               # 命令行入口：离线演示 + `ping` 上游连通性检查（与 HTTP 共用同一个适配器）
│   ├── __main__.py           # HTTP 启动入口：`uv run python -m app`（让 settings.host/port/debug 生效）
│   └── api/
│       ├── __init__.py
│       ├── deps.py           # 依赖注入：get_settings / get_llm_client / get_db（一次请求一个会话）
│       └── app.py            # FastAPI 应用对象 + lifespan + 路由（uvicorn app.api.app:app）
│
├── playground/               # 实验区：一次性验证代码，随时可删，不参与交付
│
├── tests/                    # 自动化测试（Step 12 起）
│   ├── conftest.py           # 全局准备：import app 之前设 DATABASE_URL → 独立临时库；client fixture + 每测试清表
│   ├── fakes.py              # 假上游：FakeLlm / FakeChatStream（继承真类，签名漂移会被 mypy 抓到）
│   ├── test_smoke.py         # 冒烟：tests/ 能跑 + lifespan 真的执行 + 临时库生效
│   ├── test_conversations.py # 对话接口 HTTP 契约：CRUD 全生命周期 / 游标分页 / 422 / 404
│   └── test_upstream.py      # 上游接线 + 三类故障 → 502 + 流式 pre-flight 失败仍能改状态码
│
└── study_notes/              # 开发笔记：设计理由、踩坑记录、阶段规划
```

### 为什么用 `src` 布局

`src/app/` 而不是根目录直接放 `app/`，是为了**强制暴露打包配置的问题**：

- 扁平布局下 `import app` 能成功，只是因为"当前工作目录恰好被加进了模块搜索路径"，属于**碰巧**
- `src` 布局下必须先真正"安装"项目才能导入 —— 配置写错会立刻报 `ModuleNotFoundError`，
  而不是等到使用者 `pip install` 之后才暴露

代价是多了一层目录和一个 `[build-system]` 配置，换来的是**打包正确性有保障**。

---

## 质量门

提交前跑这四条，全部通过：

```bash
uv run ruff format .          # 1. 格式化
uv run ruff check . --fix     # 2. lint（规则集 E/F/I/UP/B/TID）
uv run mypy .                 # 3. 类型检查（strict + warn_unreachable，全项目含 tests/ 与 playground/）
uv run pytest -q              # 4. 回归测试（71 个用例，不碰真上游、不碰开发库；约 10s，含真 uvicorn）
```

当前状态：

| 检查 | 结果 |
|---|---|
| `ruff check .` | All checks passed! |
| `ruff format --check .` | 31 files already formatted |
| `mypy .` | Success: no issues found in 31 source files |
| `pytest -q` | 71 passed |
| `pytest --cov` | ✅ 服务代码**分支**覆盖 **90%**（`branch = true`；`llm_client.py` 已 **100%**，最大缺口是 `app.py` 84%）。⚠️ **不设 `--cov-fail-under`**：数字会抖，且覆盖率只用来找缺口，守行为靠断言 |

> 三条静态检查命令的**范围一律用 `.`**（全项目，含 `playground/` 与 `tests/`）。`mypy` 的默认范围由
> `[tool.mypy] files = ["."]` 保证，所以带不带参数结果一致。

### 测试怎么写的（三条判据）

| 判据 | 做法 |
|---|---|
| **不碰真上游** | `app.dependency_overrides[get_llm_client]` 注入 `tests/fakes.py` 的假对象；假对象**继承真类**，所以签名漂移会被 mypy 抓到 |
| **不碰开发库** | `conftest.py` 在 `import app` **之前**设 `DATABASE_URL` 指向 `%TEMP%`；每个测试再清一次表（`reversed(Base.metadata.sorted_tables)`） |
| **必须走 HTTP，不 import 路由函数** | 测试文件一行都不 import 源码 —— 关联靠 **URL 字符串 + 运行时查表**。这样中间件 / 异常处理器 / 依赖注入全都真实经过 |

⭐ 最容易被忽略的一条：**「全绿」不等于「断言有牙」。** 所以每批用例写完要抽 3~5 处做**变异测试** ——
故意把源码改坏一行、看它红不红、再 `git checkout` 还原。累计 **24 次、21 次抓到**，3 次抓不到的都记了原因：

| 抓不到的变异 | 为什么抓不到 | 记录 |
|---|---|---|
| 去掉 `errors.py` 的 `X-Request-ID` 头 | 中间件也写这个头，**行为没变** | 等价变异，测试放行是对的 |
| `PENDING = "pengding"` | 当时**没有任何用例断言过这个值** → 之后补了「枚举值守卫」用例 | 现已被抓住 |
| `record_usage` 里 `commit` 改回 `flush` | **最终状态一样**，只有锁持有窗口变长 | 待办 #74（测试只断言得到「最终状态」） |

⚠️ 另一条同样重要：**「并发」是网络层的行为**。`TestClient` 走 ASGI 直连，客户端一帧不读也不产生背压 ——
📎 同一份代码在 `TestClient` 下连接池峰值 **0**、在真 uvicorn 下 **= 并发数**。所以并发缺陷只能在真服务上测。

mypy 采用 `strict = true`（要求函数写类型注解、禁止隐式 `Any` 等），并额外开启 `warn_unreachable`
—— 后者**不在 `strict` 预设内**，需要显式打开，用于发现"永远执行不到"的死代码。

---

## 关键技术决策

> 完整 28 条（含「放弃了什么」「何时该重审」）在 [decisions.md](study_notes/project/decisions.md)。这里只留**评审时值得主动讲**的 8 条。

| 决策 | 一句话理由 | 代价 / 取舍 |
|---|---|---|
| **`uv` + `uv.lock`** | 声明「意图」（`>=x,<y`）+ 锁定「结果」（哈希），换机器能装出逐位一致的环境 | 多一个提交文件；团队需统一用 uv |
| **上游一律视为不可信输入** | 失败分 **L1 没回应 / L2 状态码不对 / L3 200 但结构不对**；只有 L2 被 `raise_for_status()` 覆盖，L1/L3 必须自己翻译 | 要写 `try/except (ValueError, KeyError, TypeError)` + 流内错误帧 |
| **上游调用封进适配器**（`LlmClient`） | 契约一句话：成功返回值、失败抛 `AppError`、**绝不泄漏 `httpx` 异常**。用 ruff `TID251` 把它变成**机械检查** | 适配器自己管 `aclose()`；`stream` 默认必须 `False`（📎 否则 `ResponseNotRead` → 500，且 MockTransport 复现不出） |
| **流式失败三层防线** | 判据「这个问题在读到数据之前能判断吗」：pre-flight → 适配器（逐帧）→ 路由（零内容）。📎 7 种上游异常因此全部有 `[DONE]` 收尾 | 前端必须知道 **200 也可能是失败**（要在 SSE 循环里认 `frame.error`） |
| **分层判据只有一条** | **「这段代码离了 HTTP 还活得下去吗」**：接口层懂 `Request`/状态码，业务层只认普通值，基础设施层管 httpx/DB。硬规则：业务层永不 import `fastapi` | 现阶段为分层而分层是过度设计；出现第二个调用方才拆 |
| **错误码与 HTTP 状态码解耦 + 单一出口** | `AppError` 只带 `code`+`message`；所有错误响应经 `errors.py` 的 `_error_response()` 生成 | 📎 三种 404 靠业务码区分；代价是「码要在调用点与 `_STATUS_BY_CODE` 两处维护」（待办 #58） |
| **计费不跟对话一起删 + 两阶段记账** | `ondelete="SET NULL"`（📎 `CASCADE` 会丢 900 token 的账）；流开始前落 `pending`，断开只做同步赋值 `aborted` | 被删对话的账单 `conversation_id=NULL`，**无法区分「从没属于过」与「父行被删」** |
| **分页用游标不用 offset** | 📎 offset 在「翻页期间删数据」时会**漏掉一条**（用户永远看不到）；游标用「值」`id > N` 不受影响 | 不支持「跳到第 N 页」；`total` 会轻微过时 |

⚠️ **可读性/工程惯例类**的小决策（`src` 布局、`extra="forbid"`、`.venv`/`.env` 不提交、mypy+ruff 分工、异步优先、供应商中立）已并入上文对应章节，不再重复列表。

---

## 路线图


| 阶段 | 内容 | 产出 | 状态 |
|---|---|---|---|
| **0 · 工程基础** | 依赖管理、版本控制、项目结构、数据契约、静态检查 | 规范的项目骨架 | ✅ 已完成 |
| **1 · FastAPI + 数据库** | 路由、依赖注入、中间件、异常处理、**SSE 流式响应**、SQLAlchemy 异步 CRUD | 可运行的聊天接口后端（业务逻辑先 echo 占位） | 🚧 进行中 |
| **2 · LLM 原生 API** | OpenAI 兼容接口、流式消费、token 与成本核算、Function Calling、结构化输出 | 手写的 LLM 调用层（不依赖 LangChain） | ⬜ |
| **3 · RAG** | 文本切分策略、Embedding 选型、**混合检索（BM25 + 向量 + RRF）**、Rerank、引用溯源、**RAGAS 量化评估与参数消融** | 带评估报告的中文知识库问答系统 | ⬜ |
| **4 · Agent + 部署** | 多步规划、工具调用、LangGraph、可观测性、容器化部署 | 真实场景的多步 Agent 服务 | ⬜ |

**离「敢对外上线」还差什么**：见 [production-readiness.md](study_notes/project/production-readiness.md)
（七道门自检 + `P0/P1/P2` 档期 + 过门判据）。当前定级 **L2.5 / L5**（内部工具级偏上），
主要缺口是**测试 / 鉴权 / 容量上限 / 观测 / 部署产物**五块。

---

## 开发笔记

`study_notes/` 里 **200+ 条踩坑与结论**，每条都带最小复现与定位方法（📎 = 有实测数字）。
这里只留 10 条**最能体现工程素养**的；完整清单见
[learning-log.md](study_notes/learning/learning-log.md)（踩坑表 + 结论表）。

| 教训 | 一句话 |
|---|---|
| **同一份事实出现第二份就是定时炸弹** | 五起事故（`Bearear` / `X-Request_ID` / `UPSTREAM_MALFORMEAD` / 12 行永不触发的 `except` / role 校验漏一条路由）**没有一起是"不小心"**。判据不是"看起来重复"，而是**「改一处会不会漏另一处」** —— 只要 N ≥ 2，第 N+1 次改动就会漏 |
| **类型标注不是运行时保证** | 📎 `chunk: dict[str, Any] = json.loads(raw)` 零校验（`json.loads` 返回 `Any`）。这个谎一直没被发现，直到下游又写 `isinstance(chunk, dict)`，mypy 立刻报 `Statement is unreachable` —— **它抓的是「你对自己的类型都不信」** |
| **`stream` 默认值写成 `True`：三道门全绿但接口 500** | 📎 `send(stream=True)` 只拿响应头，`response.json()` 抛 `ResponseNotRead`，其 MRO 既不是 `RequestError` 也不在 `(ValueError, KeyError, TypeError)` 里 → 穿过所有 `except` 落 500。⚠️ **`MockTransport` 复现不出来** —— 判据：**涉及「body 读没读」的改动必须打真网络** |
| **「一帧」是数据边界，不是时间单位** | 📎 同一句话可切 10 帧（1.861s）/ 2 帧（0.383s）/ 201 帧（0.002s）—— 帧数与总耗时无关。`\n\n` 管"帧在哪结束"，`await` 管"下一帧何时到"。📎 一次真实请求：15 字节块 → 13 解压块 → 150 行 → 75 帧 → 6 个可见片段 |
| **「行」是 SSE 的分帧符，不是内容里的换行** | 📎 模型输出的换行被 `json.dumps` 转义成 `\` + `n` 两个字符，所以一帧永远只是一行（实测「这一行里有真实换行符吗: False」）。⚠️ 上游若不转义，一帧被切多行、第二行会被 `startswith("data:")` 跳过 → **内容静默丢失** |
| **流式接口的访问日志耗时 ≠ 请求耗时** | 📎 假上游每 0.4s 一帧共 3 帧，中间件在 **42.7ms** 就打出 `-> 200 16.4ms`，整条流到 **1266.9ms** 才结束 —— `call_next` 返回于**响应头就绪**那一刻。⭐ 推论：真实耗时要另记，且**绝不能读 `response.body`**（读一次就把流抽干） |
| **「字段值宽松」不等于「出问题」** | 📎 判空写成 `is not None` → 空字符串也报警、还打出 `type=str`（自相矛盾），一个正常请求刷几十条 warning，等于把告警调成没人看。判据：`null`/`''`/缺键往往是协议规定的**正常中间状态** |
| **一个曾被记错的结论被自己推翻** | 行宽规则原先记成"按字符数"，后用**判定性实验**证伪并纠正为"按显示宽度（汉字占 2 列）"—— 错误来源是把中文经管道喂进工具导致编码损坏 |
| **「测试全绿」证明不了「断言有牙」** | 判据：**测行为不测实现** —— 实现换了但用户可见契约没变，测试不该红。📎 最初的 5 次变异里就有 1 次是这种**等价变异**（去掉 `errors.py` 那份 `X-Request-ID` 头，中间件还在写）→ 测试放行是对的。⚠️ 更有杀伤力的是反面：**值域写错也全绿**（`PENDING = "pengding"`）—— 因为没有任何用例断言过那个值。📎 累计 24 次变异的完整记录（含 3 次抓不到的原因）在[质量门](#质量门) |
| **`flush` 与 `commit` 差的是「事务结束不结束」** | 📎 记账只把 `await db.flush()` 改成 `await db.commit()`（**一个词**），四个数字同时变了：并发 4 条流总耗时 **2.60s → 0.71s**、连接池峰值 **6 → 2**、并发 6 条流里 **3 条 200 + 0 帧 → 0 条**、进程被强杀后账单 **0 行 → 1 行 `pending`**。⭐ 三个「毫不相干」的待办（并发串行化 / 连接被流独占 / 崩了不留账）**是同一个根因的三种症状** ——判据：**写事务不该活得比一次写入更久**。⚠️ 而且这类回归**测试抓不到**：改回去 61 个用例全绿，因为「最终状态」一样、只有「持有多久」变了（待办 #74） |
| **`with` 不承诺「关闭」** | 📎 `with sqlite3.connect(...)` 退出后连接**仍可用**（`__exit__` 只 commit/rollback，没有 `close()`）；而 `with TestClient(app)` 会触发 lifespan —— 因为 `TestClient.__enter__` 里显式调了 `start_task_soon(self.lifespan)`。⭐ 判据：**判断一个 `with` 做了什么，只看 `__enter__`/`__exit__` 的源码** |

> ⭐ 另有几条**流程类**教训（不是技术点，但更值钱）：密钥被自己的报错打印出来（规范 §10.1）；
> 报错要**读完每个词**（`or` 前后常是两个独立条件）；**「工具全绿」证明不了「代码会执行」**。

---

## 文档地图

> 一份事实只放一处。想知道「某类信息去哪找」看这张表。

| 文件 | 只回答一个问题 | 变化频率 |
|---|---|---|
| [study_notes/project/roadmap.md](study_notes/project/roadmap.md) | **做到哪了 / 还剩几步**（一张 80 行进度表 + 待办 #1~#76 唯一台账，37 已关闭 / 39 未关闭） | 每步收口 |
| [study_notes/project/decisions.md](study_notes/project/decisions.md) | **为什么这么设计 / 放弃了什么 / 何时该重审**（ADR 28 条） | 做决定时 |
| [study_notes/project/production-readiness.md](study_notes/project/production-readiness.md) | **距离敢上线还差什么 / 怎么才算过门**（七道门 + `P0/P1/P2`） | 每次收口重推门的颜色 |
| [study_notes/project/architecture-map.md](study_notes/project/architecture-map.md) | **各种关系与形状长什么样**（七层栈 / 模块依赖 / **§2.4 依赖解析与资源生命周期** / **§2.5 `app.py` 调用链** / ER+DDL / 端点总表 / 成功·错误·SSE 的完整形状 / **§8.6 流式完整时序** / 配置 / 日志 / 测试 / 状态机 / **§13 运行形态** / **§14 决策↔代码↔测试**） | 想弄清一个形状时 |
| [study_notes/learning/stage1-fastapi.md](study_notes/learning/stage1-fastapi.md) | **FastAPI 与 SQLAlchemy 的机制**（原理 + 实测） | 学到新东西时 |
| [study_notes/learning/logging.md](study_notes/learning/logging.md) | **日志原理与写法**（专题，换项目照样成立） | 同上 |
| [study_notes/learning/learning-log.md](study_notes/learning/learning-log.md) | **那天为什么改成这样**（流水 / 踩坑 / 结论 / 12 个专题） | 每步收口 |
| [study_notes/learning/self-check-questions.md](study_notes/learning/self-check-questions.md) | **我到底懂没懂**（全部自检题 + 答案，唯一出处） | 每步补题 |
| [tests/README.md](tests/README.md) | **怎么测**（9 个文件各测哪层 / 怎么跑 / 怎么读 pytest 与覆盖率输出 / **两个连接池谁占谁** / 并发要问的 5 个问题） | 改测试或排查并发时 |
| [study_notes/learning/tools-reference.md](study_notes/learning/tools-reference.md) | **这个工具/包怎么用**（速查卡片） | 用错一次就补一条 |
| [工程规范与协作约定.md](工程规范与协作约定.md) | **我们怎么协作**（步骤卡格式 / 质量门 / 安全约定 / 硬约束） | 约定变化时 |
| [.github/copilot-instructions.md](.github/copilot-instructions.md) | **AI 进来先读什么**（新会话自动加载的协作指令） | 少改 |

⚠️ **禁止跨类搬运**：笔记里不写「我们决定」；`decisions.md` 不写实测数据表格；
`production-readiness.md` 不写缺陷细节（引用 roadmap 的编号与 📎 证据）。
判据见 [工程规范 §4.4d](工程规范与协作约定.md)。

---

## 说明

本项目为个人学习与能力展示用途，处于持续开发中。仓库中的笔记与代码均经过实测，
具体版本号与环境细节以 `pyproject.toml` / `uv.lock` 为准。
