# llm-app-engineering

> 一个从零搭建的 LLM 应用后端。工程规范先行，逐步演进为**带量化评估的中文 RAG 知识库问答服务**。

**当前状态**：阶段 0 · 工程基础（依赖管理 / 版本控制 / 项目结构 / 数据契约 / 静态检查）已完成；
阶段 1 · FastAPI 服务开发中 —— **Step 1 ~ 9a 已完成**（HTTP/ASGI 地基 → 三段参数 → 依赖注入 →
错误处理与 `lifespan` → 中间件与 CORS → 异步正确姿势 → **SSE 流式响应**）。
已具备：404 / 400 / 502 / 500+请求 ID 的统一错误处理、请求追踪中间件、应用级共享 HTTP 客户端、
以及一个假数据版的逐帧 SSE 接口（实测 TTFB 0.014s / total 1.85s，真模型接上游属下一步 9b）。
详见[路线图](#路线图)。

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
| 数据库 | SQLAlchemy 2.0 async + SQLite → PostgreSQL | 阶段 1 引入 |
| 测试 | pytest + pytest-asyncio | 阶段 1 引入 |
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

# 4. 启动 HTTP 服务（开发模式：改代码自动重启）
uv run uvicorn app.api.app:app --reload
# 然后打开 http://127.0.0.1:8000/docs —— 自动生成的交互式 API 文档
```

> 所有命令都用 `uv run` 前缀。原因是 `uv run` 会自动指向项目自己的 `.venv`，
> 并在依赖发生变化时**先自动同步**，避免"装了依赖却仍然导入失败"这类问题。

**另一个入口**：阶段 0 的 CLI 仍可用，用于验证配置与上游 LLM 的连通性（不属于服务）：

```bash
uv run python -m app.main        # 离线演示：打印配置与占位响应
uv run python -m app.main ping   # 真实调用上游 /models，列出可用模型
```

---

## 接口一览（截至阶段 1 · Step 9，含 Step 4 的响应契约与 Step 9 的 SSE）

| 方法 | 路径 | 说明 | 主要状态码 |
|---|---|---|---|
| GET | `/health` | 健康检查（部署探活用） | 200 |
| GET | `/v1/models` | 硬编码的模型清单；支持 `?prefix=` / `?limit=`（1 ~ 100） | 200 / 422 |
| GET | `/v1/models/latest` | 默认模型 | 200 |
| GET | `/v1/models/{model_name}` | 单个模型；名称不在清单里 → 404 | 200 / 404 |
| POST | `/v1/chat` | 聊天（业务逻辑仍为 `echo` 占位）；最后一条消息必须是 `user` | 200 / 400 / 422 |
| GET | `/v1/upstream/models` | **真实调用**上游 `/models`，返回 `ModelListResponse` | 200 / 502 |
| GET | `/v1/chat/stream` | **SSE 流式**（假数据逐字输出，真模型待接）；`text/event-stream` + chunked | 200 |

**成功响应形状**（Step 4 起，`schemas.py` 定义，可在 `/docs` 展开）：

```jsonc
// POST /v1/chat
{"content": "[echo] 你好", "model": "deepseek-flash", "usage_tokens": 0}

// GET /v1/upstream/models —— 上游 10 个键只暴露 3 个（白名单：owned_by / effort 等不外泄）
{"total": 2, "items": [
  {"id": "deepseek-flash", "name": "DeepSeek-V4.1-Flash", "context_window": 1048576},
  {"id": "deepseek-v4-pro", "name": "DeepSeek-V4-Pro", "context_window": 1048576}
]}
```

**错误响应形状**（Step 6 起）：

```jsonc
// 业务错误（400 / 409 …）：错误码给机器判断，message 给人看
{"error": {"code": "LAST_MESSAGE_NOT_USER", "message": "最后一条消息必须是 user，当前是 system"}}

// 服务内部错误（500）：只回一句人话 + 请求 ID，堆栈只写服务端日志
{"error": {"code": "INTERNAL_ERROR", "message": "服务内部错误", "request_id": "748f0334b804"}}
```

> ⚠️ 框架层的 404（路由不存在）与 422（请求形状不合法）目前仍是 FastAPI 默认的 `{"detail": ...}`，
> 三种形状并存属于**已知待办**（见[路线图](study_notes/学习档案与路线图.md) 待办 #6），计划在 Step 11 统一。
>
> 流式接口的 `/docs` 目前把 `200` 标成 `application/json`（返回注解是 `Response` 子类时 FastAPI 会置空
> `response_model`），实际响应是 `text/event-stream` —— 见待办 #11。

**SSE 流式响应**（Step 9a 起，假数据版；真模型接上游属 9b）：

一帧 = `data: <内容>` + **一个空行**（`\n\n`）。实测响应：

```text
HTTP/1.1 200 OK
cache-control: no-cache
x-accel-buffering: no
content-type: text/event-stream; charset=utf-8
transfer-encoding: chunked

data: {"delta": "你"}

data: {"delta": "好"}

……

data: [DONE]
```

```powershell
# ⭐ 判"是否真流式"只看这两个数的比值（本例 ttfb 0.014s / total 1.850s = 1:130）
curl.exe -s -o NUL -w "ttfb=%{time_starttransfer}s total=%{time_total}s`n" http://127.0.0.1:8000/v1/chat/stream

# 逐帧看内容（-N = 关掉 curl 自己的输出缓冲，否则看不到"逐字")
curl.exe -N -s http://127.0.0.1:8000/v1/chat/stream

# 只看响应头，丢弃 body
curl.exe -s -D - -o NUL http://127.0.0.1:8000/v1/chat/stream
```

> ⚠️ `TestClient` 里的 `transfer-encoding` 是 `None` —— 它能验证**帧格式**，证明不了"分批发送"。
> 时序必须用真 uvicorn + 真 HTTP 客户端。

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
│   ├── config.py             # 全部可调参数集中在这里，类型安全且带校验
│   ├── schemas.py            # 对外数据契约：请求 / 响应的形状定义
│   ├── constants.py          # 必须跨模块一致的常量（HTTP 头名等，只写一处）
│   ├── errors.py             # 业务异常 AppError + 错误码→HTTP 状态码映射 + 异常处理器注册
│   ├── llm_client.py         # 上游 HTTP 客户端的唯一构造点（create_llm_client）
│   ├── main.py               # 命令行入口：离线演示 + `ping` 上游连通性检查
│   └── api/
│       ├── __init__.py
│       ├── deps.py           # 依赖注入：get_settings / get_llm_client（从 app.state 取共享 client）
│       └── app.py            # FastAPI 应用对象 + lifespan + 路由（uvicorn app.api.app:app）
│
├── playground/               # 实验区：一次性验证代码，随时可删，不参与交付
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

提交前跑这三条，全部通过：

```bash
uv run ruff format .          # 1. 格式化
uv run ruff check . --fix     # 2. lint（规则集 E/F/I/UP/B）
uv run mypy .                 # 3. 类型检查（strict + warn_unreachable，全项目含 playground/）
```

`uv run pytest -q` 是第 4 条，等 `tests/` 落地后加入（当前 `pytest` 尚未进依赖）。

当前状态：

| 检查 | 结果 |
|---|---|
| `ruff check .` | All checks passed! |
| `ruff format --check .` | 14 files already formatted |
| `mypy .` | Success: no issues found in 14 source files |

> 三条命令的**范围一律用 `.`**（全项目，含 `playground/`）。`mypy` 的默认范围由
> `[tool.mypy] files = ["."]` 保证，所以带不带参数结果一致。

mypy 采用 `strict = true`（要求函数写类型注解、禁止隐式 `Any` 等），并额外开启 `warn_unreachable`
—— 后者**不在 `strict` 预设内**，需要显式打开，用于发现"永远执行不到"的死代码。

---

## 关键技术决策

| 决策 | 理由 | 代价 / 取舍 |
|---|---|---|
| **uv + `uv.lock`** 而非 `requirements.txt` | `requirements.txt` 无法表达"意图"（只能写死版本），且不锁定间接依赖；`uv.lock` 记录求解结果 + 哈希，换机器能装出**逐位一致**的环境 | 多一个需要提交的文件；团队需统一使用 uv |
| **`src` 布局 + 可安装包** | 见上文「为什么用 src 布局」 | 多一层目录；需显式声明 `packages = ["src/app"]` |
| **pydantic 管理配置**（而非 `os.environ` 散落各处） | ① 类型自动转换与校验 ② 报错**点名到字段**（`port` + `input_value='abc'`），而非 `invalid literal for int()` ③ 读一个类就知道有哪些可调参数 | 引入一层抽象；需要理解环境变量与 `.env` 的**优先级**（真实环境变量 > `.env` > 默认值） |
| **配置严格模式 `extra="forbid"`** | 键名拼错（如把 `PORT` 写成 `PORTT`）会**立即报错**，而不是被静默忽略 —— 后者是"以为配好了、其实没配上"的隐蔽 bug | 若将来多个工具共用同一个 `.env`，别人的键会导致启动失败（届时应按工具拆分配置文件） |
| **`.venv` 与 `.env` 永不提交** | 二者都可由仓库内文件重建（`.venv` ← `uv.lock`）或属于本机私有（`.env` 含密钥）。尤其密钥：Git 历史**只增不减**，一旦提交只能吊销重发 | 新人需多跑一条 `cp .env.example .env` |
| **异步优先（`async`/`await`）** | LLM 应用的时间几乎全花在"等"（等模型返回 1~30 秒、等数据库、等外部 API）。同步写法在等待时占住执行权，并发请求会退化成串行 | 需避免在异步路径里调用阻塞库；CPU 密集任务更适合进程池 |
| **mypy strict + ruff 双工具** | 二者分工不同：**ruff 管"形状"**（格式、导入顺序、可疑写法），**mypy 管"含义"**（类型是否自相矛盾）。后者需要理解代码语义，是 ruff 做不到的 | 严格模式初期会报较多错，需要写全类型注解 |
| **上层供应商中立**（`llm_api_key` / `llm_base_url` / `llm_model`） | 走"OpenAI 兼容协议"，但配置项**不以供应商命名** —— 换厂商只改 `.env` 三行，代码零改动（实测：把 `base_url` 指向另一家兼容服务，`/models` 检查命令原样可用） | 需要在代码与供应商 JSON 之间做一层转换；专有能力（如某家私有参数）不能直接用 |
| **分层：接口层 / 业务层 / 基础设施层** | 判据只有一条：**这段代码离了 HTTP 还活得下去吗**。接口层懂 `Request` / 状态码 / 响应；业务层只认普通 Python 值；基础设施层管 httpx / 配置 / DB。硬规则：**业务层永远不 import `fastapi`**，调用方向单向 | 现阶段还要为"分层而分层"会过度设计 —— 一个 4 行规则、只有一个调用方时抽到 `services/` 只是搬家；出现第二个调用方（CLI / 另一个接口）才是拆分信号 |
| **业务错误码与 HTTP 状态码解耦** | `AppError` 只带 `code` + `message`，**不带 `status_code`**；映射集中在 `_STATUS_BY_CODE` 一处。同一个 400 可对应多个业务码，客户端按 `code` 分支，不再靠匹配文案 | 多一层映射表；未登记的码会落到默认 400（属于"防崩溃"而非"正确"，需靠 `Literal`/测试兜住） |
| **HTTP 客户端应用级共享（`lifespan`）** | 每请求新建客户端要重新做 TCP + TLS 握手：实测 200 次请求 **51.3 ms → 23.0 ms（快 2.23 倍）**。用 `lifespan` 在启动时建一次、关闭时释放；创建/销毁归 lifespan，**取用仍走依赖**（保留 `dependency_overrides` 可测接缝） | 单测必须 `with TestClient(app)` 才会触发 lifespan；`app.state` 是全局可变状态，用例间要手工还原 |
| **错误日志与响应分离** | 500 只回 `request_id` + 一句人话，**堆栈只进服务端日志** —— 既不泄露内部结构，又能靠 ID 精确定位 | 目前日志只有 stderr、无格式化、`logger.info` 会被丢弃；生产需补日志配置与集中收集（已知待办 #7） |
| **响应契约：返回注解优先，`response_model` 用于收窄** | 两者相同时只写返回注解（FastAPI 自动采用）；只有"内部模型宽于对外契约"时才显式写 `response_model=`。响应模型是**白名单**：没声明的字段不可能输出 | 返回对象缺必填字段会 `ResponseValidationError` → 500（错在我方）；响应类型写 `list[dict]` 会让 `/docs` 失去结构，且过滤晚一步 |
| **中间件做"每个请求都要做的事"** | 请求 ID、耗时、CORS 这类逻辑写在中间件里一处生效；用 `request.state` 把 ID 传给路由与异常处理器，500 也能返回同一个 ID | 中间件拿不到路由参数；**绝不能读 `response.body`**（会把流式响应抽干）；异常路径上拿不到响应对象，500 的响应头要由处理器补 |
| **流式 = 异步生成器 + `StreamingResponse`** | 二者分工是硬的：生成器只**产出**字符串（不碰 socket），`StreamingResponse` 负责 `http.response.start`、逐帧 `send(more_body=True)`、最后补 `more_body=False`、并监听 `http.disconnect`。驱动生成器的那句 `async for` 在 `starlette/responses.py:253`，不在本项目代码里（📎 打印调用栈实测） | 一旦开始流式就**不能再改状态码**（头已发出）；中途出错只能"把错误编码进流里"；`TestClient` 无法验证分批，时序必须用真服务 |

---

## 路线图

| 阶段 | 内容 | 产出 | 状态 |
|---|---|---|---|
| **0 · 工程基础** | 依赖管理、版本控制、项目结构、数据契约、静态检查 | 规范的项目骨架 | ✅ 已完成 |
| **1 · FastAPI + 数据库** | 路由、依赖注入、中间件、异常处理、**SSE 流式响应**、SQLAlchemy 异步 CRUD | 可运行的聊天接口后端（业务逻辑先 echo 占位） | 🚧 进行中 |
| **2 · LLM 原生 API** | OpenAI 兼容接口、流式消费、token 与成本核算、Function Calling、结构化输出 | 手写的 LLM 调用层（不依赖 LangChain） | ⬜ |
| **3 · RAG** | 文本切分策略、Embedding 选型、**混合检索（BM25 + 向量 + RRF）**、Rerank、引用溯源、**RAGAS 量化评估与参数消融** | 带评估报告的中文知识库问答系统 | ⬜ |
| **4 · Agent + 部署** | 多步规划、工具调用、LangGraph、可观测性、容器化部署 | 真实场景的多步 Agent 服务 | ⬜ |

---

## 开发笔记

`study_notes/` 记录了设计理由与实证过程，其中**踩坑记录都带最小复现和定位方法**，例如：

- PowerShell 读取 UTF-8 中文文件的乱码：用 GBK 解码所致 —— 结合字节级检查定位，而非贸然重写文件
- `.gitattributes` 放在子目录导致规则**静默失效**：用 `git check-attr` 验证，而非假设
- TOML 表头写错导致的"键归属错误"：报错信息只说类型不对，根因却是少了表头
- `extra="ignore"` 静默吞掉拼错的配置键：改为 `forbid` 后错误暴露在启动时
- **密钥被自己的报错打印出来**：配置校验失败时 pydantic 默认回显原始值 —— 处理方式（全历史取证、吊销重发、`hide_input_in_errors`）与整改规则见规范 §10.1
- **一个曾被记错的结论被自己推翻**：行宽规则原先记成"按字符数"，后用**判定性实验**证伪并纠正为"按显示宽度（汉字占 2 列）"—— 错误来源是实验时把中文经管道喂进工具导致编码损坏，见[工具与依赖速查](study_notes/工具与依赖速查.md) §5
- **状态码"对了"不等于验证通过**：PowerShell 内联拼 JSON 导致服务器收到伪 JSON，422 是拿到了，但 `type=json_invalid`（解析关被拦）而非 `too_short`（契约关被拦）—— 判据改成"先看 `type`+`loc`，再看状态码"
- **`app.state, client = x`（逗号）与 `app.state.client = x`（点号）是两种语义**：前者是解包赋值，对 `AsyncClient` 直接 `TypeError`；若右边可迭代更阴 —— 整个 `state` 对象会被静默替换
- **同名重绑定会让"注册"失效**：模块里出现两个 `app = FastAPI(...)` 时，异常处理器注册在旧对象上，uvicorn 却用新对象 → 所有业务异常静默回落成 500
- **`response_model` 不是"随便削一刀"**：返回对象*多了*字段会被削掉，*缺了*必填字段则是 500 `ResponseValidationError` —— 因为错在"我方响应不符合自己声明的契约"
- **"一帧"是数据边界，不是时间单位**：实测同一句话可切 10 帧（1.861s）/ 2 帧（0.383s）/ 201 帧（0.002s）—— 帧数与总耗时无关。`\n\n` 管"帧在哪结束"，`await` 管"下一帧何时到"；假数据的 `sleep(0.2)` 只是"上游延迟"的替身演员
- **SSE 少写一个换行不报错，但整条流失效**：三帧各带 `\n\n` 解析出 3 个事件；全部只写一个 `\n` 只解析出 **1 个**事件（内容是最后的 `[DONE]`），前端表现为"一个字都没收到"—— 症状与原因完全不像的 bug
- **"我的代码里找不到 `async for`"是正常的**：驱动 `event_source` 的那句在 `starlette/responses.py:253`（`async for chunk in self.body_iterator`）。打印调用栈可直接看到 `responses.py:279 in wrap → responses.py:253 in stream_response → event_source`。生成器只产出、不碰网络；`StreamingResponse` 只上网、不碰内容

| 文档 | 内容 |
|---|---|
| [学习档案与路线图.md](study_notes/学习档案与路线图.md) | 目标、能力缺口分析、阶段规划 |
| [阶段0-工程基础.md](study_notes/阶段0-工程基础.md) | uv / Git / 项目结构 / pydantic / 类型注解 / 异步 / 测试 / lint / Docker |
| [阶段1-FastAPI速成.md](study_notes/阶段1-FastAPI速成.md) | HTTP/ASGI → 三段参数 → 依赖注入 → 错误处理与 `lifespan` → 中间件 → SSE 流式 → 数据库 → 测试 → 部署（Step 1~6 后有「前半程回顾」章节；Step 9 的 §9.2b~9.2d / §9.3a 是流式的分层讲解，复习入口） |
| [学习过程记录.md](study_notes/学习过程记录.md) | 步骤流水、踩坑记录、关键结论 |
| [工具与依赖速查.md](study_notes/工具与依赖速查.md) | 第三方包与工程工具速查：定位、安装、常用 API 与命令、易错点 |
| [工程规范与协作约定.md](工程规范与协作约定.md) | 本项目的工程规范：命名、分层、质量门、安全约定 |
| [.github/copilot-instructions.md](.github/copilot-instructions.md) | AI 协作指令：任何新会话自动加载的讲解风格、工作纪律与命令规范 |

---

## 说明

本项目为个人学习与能力展示用途，处于持续开发中。仓库中的笔记与代码均经过实测，
具体版本号与环境细节以 `pyproject.toml` / `uv.lock` 为准。
