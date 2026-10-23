# llm-app-engineering

> 一个从零搭建的 LLM 应用后端。工程规范先行，逐步演进为**带量化评估的中文 RAG 知识库问答服务**。

**当前状态**：阶段 0 · 工程基础（依赖管理 / 版本控制 / 项目结构 / 数据契约 / 静态检查）已完成；
阶段 1 · FastAPI 服务开发中 —— **Step 1 ~ 9b-4b-2 已完成**（HTTP/ASGI 地基 → 三段参数 → 依赖注入 →
错误处理与 `lifespan` → 中间件与 CORS → 异步正确姿势 → SSE 流式响应 → 上游防御）。
已具备：404 / 400 / 502 / 500+请求 ID 的统一错误处理、请求追踪中间件、
**一个把「上游调用 + 错误翻译」封在一起的适配器**（路由层不出现 `httpx`，且由 lint 强制）、
以及一个**真调上游 DeepSeek 的 SSE 流式接口**（状态帧 + 正文逐字 + `finish_reason` + token 用量，
实测首帧 60ms / 总 906ms；上游失败时客户端拿 **502** 而不是 `200` + 断连）。
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
| POST | `/v1/chat/stream` | **SSE 流式**：真调上游 `stream=true`，逐帧转发回答文字（思维链按产品要求丢弃）；`text/event-stream` + chunked | 200 / 422 |

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
> 帧的分类与顺序详见[阶段1 笔记](study_notes/阶段1-FastAPI速成.md) §9.8d。

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
> （httpx `iter_text()` + `perf_counter`）量首个数据帧时刻。详见[阶段1 笔记](study_notes/阶段1-FastAPI速成.md) §9.3b ③。
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
│   ├── config.py             # 全部可调参数集中在这里，类型安全且带校验
│   ├── schemas.py            # 对外数据契约：请求 / 响应的形状定义
│   ├── constants.py          # 必须跨模块一致的常量（HTTP 头名等，只写一处）
│   ├── errors.py             # 业务异常 AppError + 错误码→HTTP 状态码映射 + 异常处理器注册
│   ├── llm_client.py         # 上游适配器：唯一 import httpx、唯一翻译上游故障的地方（LlmClient / LlmChatStream）
│   ├── main.py               # 命令行入口：离线演示 + `ping` 上游连通性检查（与 HTTP 共用同一个适配器）
│   └── api/
│       ├── __init__.py
│       ├── deps.py           # 依赖注入：get_settings / get_llm_client（从 app.state 取共享适配器）
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
uv run ruff check . --fix     # 2. lint（规则集 E/F/I/UP/B/TID）
uv run mypy .                 # 3. 类型检查（strict + warn_unreachable，全项目含 playground/）
```

`uv run pytest -q` 是第 4 条，等 `tests/` 落地后加入（当前 `pytest` 尚未进依赖）。

当前状态：

| 检查 | 结果 |
|---|---|
| `ruff check .` | All checks passed! |
| `ruff format --check .` | 16 files already formatted |
| `mypy .` | Success: no issues found in 16 source files |

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
| **上游一律视为不可信输入**（2026-10-21 新增，规范 §十四） | 和用户输入同级：`json.loads` 的结果是 `Any`，键名/类型/结构都可能与假设不同。失败分三层——**L1 没回应 / L2 状态码不对 / L3 200 但结构不对**，只有 L2 被 `raise_for_status()` 自动覆盖，L1/L3 必须自己翻译成 502。流式下 L3 发生在头已发出之后，只能把错误编码进流 | 需要写 `try/except (ValueError, KeyError, TypeError)` 与流内错误帧；📎 实测现有代码有 **6 种 L3 场景落到 500**、**4 种导致流「200 + 断连」**、**1 种静默丢整条流**（见[路线图](study_notes/学习档案与路线图.md)待办 #14~#18） |
| **流式失败三层防线**（2026-10-22 新增，笔记专题 12） | 判据一是**「这个问题在读到数据之前就能判断吗」**：① **pre-flight**（看状态码）→ L1/L2 → **502**；② **适配器**（看「行 / 帧」：`startswith("data:")`、空行跳过、非 dict 丢弃）→ 丢弃 + WARNING；③ **路由**（看「字段 / 最终结果」：`isinstance(text, str)`、`content_frames == 0`）→ 零内容发 **`STREAM_NO_CONTENT`** 帧。📎 实测 7 种上游异常因此全部有 `[DONE]` 收尾（此前 3 种静默、2 种断连） | 前端必须知道 **200 也可能是失败**（`response.ok === true`），要在 SSE 循环里识别 `frame.error`；让适配器自己发错误帧是错的 —— 它就得知道「整个流」的状态，那它就不再是协议层。判据二是**「这一帧的内容未知吗」**：未知 → **中止**（`STREAM_FAILED`）；只是没有可用文字 → **跳过**（`warning` + `continue`）—— 一个坏帧不该毁掉整个回答 |
| **单一真相：同一份事实只写一处**（2026-10-21 新增，规范 §4.6 总纲） | 判据不是"看起来重复"，而是**「改一处会不会漏另一处」**。五类事实各有各的家：字面量 → `constants.py`；错误码/状态码映射 → `errors.py`；上游错误翻译 → `LlmClient` 适配器（§14.7）；业务规则/语义校验 → 独立纯函数（§14.8）；可复用功能（SSE 切行、重试、分页） → 独立模块。📎 本项目五起同源事故（`Bearear` / `X-Request_ID` / `UPSTREAM_MALFORMEAD` / 12 行死代码 / role 校验漏一条路由）**没有一起是"不小心"** —— 只要同一份事实存在 N 份（N≥2），第 N+1 次改动就会漏 | 三个提问顺序：① 会被 ≥2 处用到吗（否 → 就地写）② 两处不一致会出错吗（否 → 可不抽）③ 抽完要传 ≥4 个参数吗（是 → **抽错了**）。⚠️ **反向代价同样真实**：抽太碎会让读代码要跳三个文件 —— 读的成本与改的成本必须一起算（§14.3） |
| **上游调用一律封进适配器**（`LlmClient`，2026-10-21 新增，规范 §14.7） | 把「发请求 + 判状态码 + 读错误正文 + 解析 JSON + 翻译成 `AppError`」收进一个类，契约一句话：**成功返回值、失败抛 `AppError`、绝不泄漏 `httpx` 异常**。路由因此**不 import `httpx`、不写 `try/except`**，新加路由不可能漏翻译。用 `ruff` 的 `TID251` 把这条约定变成**机械检查**（只有 `llm_client.py` 与 `playground/` 可 import `httpx`）。⚠️ 曾试过"每条路由各写一遍"（抄漏一次：`UPSTREAM_MALFORMEAD` 拼错 → L3 全变 400）和"全局 `@app.exception_handler(httpx.xxx)`"（路由确实零行，但它靠 ASGI 中间件栈，**CLI / 定时任务里完全失效**，且不用起 FastAPI 就没法单测） | 适配器要自己管 `aclose()`（`send(stream=True)` 没有 `async with` 帮你关）；`stream` 默认值必须取安全的 `False`，否则 `response.json()` 抛 `ResponseNotRead` → 500，而 **MockTransport 复现不出来**；流式接口还得额外做 **pre-flight**（先校验状态码再返回 `StreamingResponse`），代价是 TTFB 从 60ms 升到约 181~266ms |
| **同一业务规则只有一份实现**（2026-10-21 新增，规范 §14.8） | 与上一条同型：`/v1/chat` 与 `/v1/chat/stream` 共用同一个 `ChatRequest`，"最后一条必须是 `user`"就必须抽成 `ensure_last_message_is_user()` 两条路由都调。📎 曾经只写在一条路由里 → 另一条**放行非法请求并真的打上游、白花一次调用** | 抽之前先问"会被调用几次"：只有 1 个调用点时抽出去属于提前抽象（比重复更糟）。分层归属：**形状归 pydantic，语义归纯函数/服务层，HTTP 归路由** |
| **分层：接口层 / 业务层 / 基础设施层** | 判据只有一条：**这段代码离了 HTTP 还活得下去吗**。接口层懂 `Request` / 状态码 / 响应；业务层只认普通 Python 值；基础设施层管 httpx / 配置 / DB。硬规则：**业务层永远不 import `fastapi`**，调用方向单向。上两条（适配器 / 业务规则）就是这条判据的具体落地：`LlmClient` 属基础设施层，`ensure_last_message_is_user` 属"离了 HTTP 也活得下去"的纯函数 | 现阶段还要为"分层而分层"会过度设计 —— 一个 4 行规则、只有一个调用方时抽到 `services/` 只是搬家；出现第二个调用方（CLI / 另一个接口）才是拆分信号 |
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
- **同一段错误翻译写了 N 遍，一定会抄错一次**：本项目真实发生过两种——`upstream_models` 里那 12 行 `except httpx.xxx` 是**永不触发的死代码**（翻译早在上游函数里做完了）；手抄时把 `UPSTREAM_MALFORMED` 写成 `UPSTREAM_MALFORMEAD`，而码表兜底是 `.get(code, 400)` → **所有 L3 场景静默返回 400**，三道质量门全绿。解决办法不是"更仔细"，而是**把翻译封进适配器**（规范 §14.7）＋ 用 `TID251` 禁止其它文件 `import httpx`
- **`stream` 默认值写成 `True`，三道门全绿但接口 500**：`send(stream=True)` 只拿响应头，接着 `response.json()` 抛 `httpx.ResponseNotRead`；它的 MRO 是 `ResponseNotRead → StreamError → RuntimeError`，**既不是 `RequestError` 也不在 `(ValueError, KeyError, TypeError)` 里**，于是穿过所有 `except` 落到 500。⚠️ **`MockTransport` 复现不出来** —— 它的 `httpx.Response(200, json=...)` body 已在内存，`stream=True` 与 `request()` 毫无区别。判据：**涉及"body 读没读"的改动必须打真网络**
- **`@app.exception_handler(httpx.xxx)` 不是"封层"的替代品**：它靠 ASGI 中间件栈兜异常，**只在有请求时存在** —— CLI / 定时任务里调同一个上游完全不生效，而且"不起 FastAPI 就没法单测"。它是"路由零 try/except"的充分条件，却不是"任何调用点都翻译"的充分条件
- **同一条业务规则写在两条路由里，一定会漏一条**：`/v1/chat` 拒 assistant 收尾（400），`/v1/chat/stream` 却放行、还真打上游、白花一次调用。抽 `ensure_last_message_is_user()` 后两条一致，且**必须放在 pre-flight 之前**，否则"先花钱再拒绝"（规范 §14.8）
- **类型标注不是运行时保证**：`chunk: dict[str, Any] = json.loads(raw)` 零校验 —— `json.loads` 返回 `Any`，赋给 `dict` 完全合法。📎 这个谎一直没被发现，直到我在下游又写了 `isinstance(chunk, dict)`，mypy 立刻报 `Statement is unreachable`：**它抓的是「你对自己的类型都不信」**。修法是让适配器兑现 `AsyncIterator[dict]` 的承诺（内部丢弃非 dict），而不是让每个调用方去怀疑
- **「字段值宽松」不等于「出问题」**：`null` / `''` / 缺键往往正是协议规定的**正常中间状态**（`finish_reason` 在每一帧都有，中间帧就是 `null`）。📎 我把判空写成 `is not None`，结果**空字符串也报警**、还打出 `type=str`（自相矛盾），一个正常请求会刷几十条 warning —— 等于把告警调成没人看。三档判据见规范 §14.4 ⑥
- **SSE 的 `data:` 后面空格是可选的**：规范里 `data:{...}` 合法。📎 旧写法 `startswith("data: ")` 遇到它会把**整条流静默丢弃** —— 客户端只收到 `thinking` + `[DONE]`，服务端零日志。而 `data:` 空行是合法的空数据事件，不跳过会让 `json.loads("")` 抛 `JSONDecodeError` **打断整条流**
- **同一份事实出现第二份，就是定时炸弹**：五起事故（`Bearear` / `X-Request_ID` / `UPSTREAM_MALFORMEAD` / 12 行永不触发的 `except` / role 校验漏一条路由）**没有一起是"不小心"**。判据不是"看起来重复"，而是**"改一处会不会漏另一处"** —— 但只要 N ≥ 2，第 N+1 次改动就会漏，所以对策是消灭第二份，而不是"更仔细"（规范 §4.6）
- **流式接口的访问日志耗时 ≠ 请求耗时**：📎 假上游每 0.4s 吐一帧、共 3 帧，中间件在 **42.7ms** 就打出 `-> 200 16.4ms`，而整条流到 **1266.9ms** 才结束。根因在 ASGI：中间件等的 `call_next` 返回于**响应头就绪**那一刻（第一条 `http.response.start`），之后逐帧发送发生在框架内部、中间件全程不参与。⭐ 推论：真实耗时要另记；且**绝不能读 `response.body`**（读一次就把流抽干，SSE 失效）

| 文档 | 内容 |
|---|---|
| [学习档案与路线图.md](study_notes/学习档案与路线图.md) | 目标、能力缺口分析、阶段规划 |
| [阶段0-工程基础.md](study_notes/阶段0-工程基础.md) | uv / Git / 项目结构 / pydantic / 类型注解 / 异步 / 测试 / lint / Docker |
| [阶段1-FastAPI速成.md](study_notes/阶段1-FastAPI速成.md) | HTTP/ASGI → 三段参数 → 依赖注入 → 错误处理与 `lifespan` → 中间件 → SSE 流式 → 数据库 → 测试 → 部署（Step 1~6 后有「前半程回顾」章节；**Step 9 的 §9.9「一条流式请求的全生命周期」是三张全景图的复习入口**，§9.2b~9.2d / §9.3a 是流式的分层讲解） |
| [学习过程记录.md](study_notes/学习过程记录.md) | 步骤流水、踩坑记录、关键结论 |
| [工具与依赖速查.md](study_notes/工具与依赖速查.md) | 第三方包与工程工具速查：定位、安装、常用 API 与命令、易错点 |
| [工程规范与协作约定.md](工程规范与协作约定.md) | 本项目的工程规范：命名、分层、质量门、安全约定 |
| [.github/copilot-instructions.md](.github/copilot-instructions.md) | AI 协作指令：任何新会话自动加载的讲解风格、工作纪律与命令规范 |

---

## 说明

本项目为个人学习与能力展示用途，处于持续开发中。仓库中的笔记与代码均经过实测，
具体版本号与环境细节以 `pyproject.toml` / `uv.lock` 为准。
