# 架构与形状地图（Architecture & Shapes）

> **这个文件只干一件事：把「长什么样」画出来。**
> 谁调用谁、请求穿过哪些层、响应体有哪些字段、错误码长什么样、SSE 有哪几种帧、配置从哪来、日志树是什么形状。
>
> **不写**：为什么这么设计（→ [decisions.md](decisions.md)）、做到哪了（→ [roadmap.md](roadmap.md)）、
> 原理推导与实测过程（→ [../learning/stage1-fastapi.md](../learning/stage1-fastapi.md)）。
> 这里只放**结论的图形化**，每张图都能在代码里对上。

---

## 0. 怎么读这份文件

| 约定 | 含义 |
|---|---|
| 📎 | 该图有实测支撑（探针跑出来的，不是画的想象） |
| 🔴 | 已知缺陷 / 容易误解的地方，编号指向 roadmap 的待办 |
| 箭头方向 | 代码里的**调用方向**（`A → B` 读作「A 调用 B」），不是数据流 |

### 图的顺序为什么是这样

**从「一个请求怎么走」开始（横向），再到「代码怎么分层」（纵向），然后「时间」（启动/关闭），
再到「数据存成什么」（存储），再「对外长什么样」（契约），最后是横切关注点（配置 / 日志 / 测试 / 状态机）。**

理由：**排查 bug 时的思考顺序就是这个顺序** —— 先问"请求走到哪一层了"，再问"是哪一层写错了"，
再问"数据对不对"，最后才问"对外表现是什么"。

| 图 | 回答的问题 |
|---|---|
| [1. 请求穿过的七层](#1-全景一次请求穿过的七层) | 这个请求经过了哪些中间件？异常在哪一层被接住？ |
| [2. 代码分层与依赖](#2-代码分层与模块依赖) | 改一个文件会影响谁？能不能反向依赖？ |
| [3. 启动与关闭](#3-启动与关闭lifespan-的两条通道) | 表什么时候建？client 什么时候造？ |
| [4. 数据模型](#4-数据模型er--ddl) | 有几张表？外键怎么连？删对话账单会怎样？ |
| [5. 端点总表](#5-端点总表) | 有哪些接口？各自收什么、回什么、什么状态码？ |
| [6. 成功响应形状](#6-成功响应形状逐端点真实样本) | 每个成功响应到底有哪些键？ |
| [7. 错误形状](#7-错误形状统一-envelope) | 出错时前端拿到什么？怎么区分两种 404？ |
| [8. SSE 帧形状](#8-sse-帧形状) | 流里有几种帧？顺序是什么？ |
| [9. 配置形状](#9-配置形状三层来源) | 这个配置项从哪读来的？谁优先？ |
| [10. 日志形状](#10-日志形状) | 一条日志经过哪几道闸？ |
| [11. 测试形状](#11-测试形状) | 测试怎么连到代码？fixture 依赖谁？ |
| [12. 状态机](#12-状态机) | 账单的三态怎么流转？对话的一生？ |

---

## 1. 全景：一次请求穿过的七层

📎 由 `app.build_middleware_stack()` 逐层取 `type(node).__name__` 得到（**真实嵌套链，不是示意图**）：

```text
 inbound                                                                    outbound
   │                                                                            ▲
   ▼                                                                            │
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ① ServerErrorMiddleware          ← 最外层兜底。只接 Exception/500                     │
│    │                               它的响应【不经过】下面的 CORS，🔴 所以 500 没有 CORS 头 │
│    ▼                                                                                  │
│ ② ExceptionTelemetryMiddleware   ← 观测用，不改行为                                     │
│    ▼                                                                                  │
│ ③ BaseHTTPMiddleware             ← 我们的 add_request_id                              │
│    │   dispatch=add_request_id     分配/沿用 request_id、记耗时、写响应头               │
│    │                               🔴 它抛的异常【穿不出去】到 ⑤，会变成 500             │
│    ▼                                                                                  │
│ ④ CORSMiddleware                 ← 补 Access-Control-*、直接答复预检 OPTIONS           │
│    ▼                                                                                  │
│ ⑤ ExceptionMiddleware            ← ★ 查表 dispatch 只在这里发生                        │
│    │   handlers = app.exception_handlers                                              │
│    ▼                                                                                  │
│ ⑥ AsyncExitStackMiddleware       ← 管理 lifespan 的退出栈                              │
│    ▼                                                                                  │
│ ⑦ APIRouter → 路由函数            ← 你的业务代码                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 谁注册了哪一层

📎 实测 `app.user_middleware` 只有 **2 项**（其余由 FastAPI 自己加）：

```text
Middleware(BaseHTTPMiddleware, dispatch=<function add_request_id ...>)     ← @app.middleware("http")
Middleware(CORSMiddleware, allow_origins=[...5173...], allow_credentials=True,
                          allow_methods=['GET','POST','PATCH','DELETE'], allow_headers=['*'])
```

| 层 | 谁加的 | 代码位置 |
|---|---|---|
| ① ServerErrorMiddleware | **FastAPI 自动** | — |
| ② ExceptionTelemetryMiddleware | FastAPI 自动 | — |
| ③ BaseHTTPMiddleware（含 `add_request_id`） | **我们**：`@app.middleware("http")` | [app.py](../../src/app/api/app.py) |
| ④ CORSMiddleware | **我们**：`app.add_middleware(CORSMiddleware, ...)` | [app.py](../../src/app/api/app.py) |
| ⑤ ExceptionMiddleware | **FastAPI 自动**（handler 表由 `register_exception_handlers(app)` 填） | [errors.py](../../src/app/errors.py) |
| ⑥ AsyncExitStackMiddleware | FastAPI 自动 | — |
| ⑦ APIRouter → 路由函数 | **我们**：`@app.get/@app.post/...` | [app.py](../../src/app/api/app.py) |

### 1.2 「注册顺序」与「层的顺序」是反的

```python
app.add_middleware(CORSMiddleware, ...)      # 先注册 → insert(0) → user_middleware[0] 最终被挤到后面
@app.middleware("http")                       # 后注册 → insert(0) → user_middleware[0] = BaseHTTPMiddleware
```

构建时用 `for ... in reversed(middleware): app = cls(app)` —— **后注册的在外层**。

📎 实测 `user_middleware = [BaseHTTPMiddleware, CORSMiddleware]`，构建后却是
**Base(③) 在 CORS(④) 外面** —— 因为 `reversed` 后再逐个包。

### 1.3 异常走哪条路

📎 源码「分家」（`fastapi/applications.py`）：`Exception` / `500` 这两个键交给 **①**，
其余交给 **⑤**。

```text
raise AppError          → ⑤ ExceptionMiddleware 查表 → _app_error_handler → 4xx/502/503
raise HTTPException     → ⑤ ExceptionMiddleware 查表 → _http_exception_handler
校验失败                → ⑤ ExceptionMiddleware 查表 → _validation_error_handler → 422
raise RuntimeError      → 一路冒到 ① ServerErrorMiddleware → _unhandled_error_handler → 500
③ 里抛 AppError         → 🔴 穿不出 ③，落 ① → 500（不是 4xx）
路径不存在 / 方法不对    → ⑤（Starlette 在 router 外面抛的 HTTPException）
```

### 1.4 一张图记住「哪些响应有 CORS 头」

| 响应由谁产生 | 有 `Access-Control-Allow-Origin` 吗 |
|---|---|
| 路由 / ⑤ 里的处理器（200 / 400 / 404 / 422 / 502） | ✅ 有（经过 ④） |
| ① ServerErrorMiddleware（**500**） | 🔴 **没有** —— 见待办 #57 |

---

## 2. 代码分层与模块依赖

### 2.1 依赖方向（📎 从源码里 `from app.x import` 提取）

```text
                       ┌─────────────────┐
                       │   api/app.py    │  ← 组合层：唯一知道"有哪些路由"的地方
                       │  （路由 + 组装） │
                       └───┬───┬───┬───┬─┘
             ┌─────────────┘   │   │   └──────────────┐
             ▼                 ▼   ▼                  ▼
     ┌───────────────┐  ┌──────────────┐      ┌──────────────┐
     │  api/deps.py  │  │  errors.py   │      │   models.py  │
     │  依赖的集中地   │  │ AppError+处理器│      │  ORM 表定义   │
     └──┬────┬───┬───┘  └──────┬───────┘      └──────────────┘
        │    │   │             │
        ▼    ▼   ▼             ▼
 ┌──────────┐ ┌──────────┐ ┌──────────────┐
 │ config.py │ │database.py│ │ constants.py │
 │ 唯一配置   │ │engine+工厂│ │ 头名等常量    │
 └──────────┘ └────┬─────┘ └──────────────┘
                   │
                   ▼
              ┌──────────┐        ┌──────────────┐
              │  schemas │◄───────│ llm_client.py│  唯一 import httpx 的地方
              │  契约     │        │  上游适配器    │  唯一翻译上游故障的地方
              └──────────┘        └──────┬───────┘
                                         │
                                    （errors / config）
```

📎 实测的完整边（左 → 右 = 「左 import 右」）：

| 文件 | import 了 |
|---|---|
| `__main__.py` | `config`, `logging_setup` |
| `api/app.py` | `api/deps`, `config`, `constants`, `database`, `errors`, `llm_client`, `logging_setup`, `models`, `schemas` |
| `api/deps.py` | `config`, `database`, `llm_client` |
| `database.py` | `config` |
| `errors.py` | `constants` |
| `llm_client.py` | `config`, `errors`, `schemas` |
| `main.py` | `config`, `llm_client`, `schemas` |
| `config.py` / `constants.py` / `schemas.py` / `models.py` / `logging_setup.py` | **无内部依赖**（叶子） |

### 2.2 三条硬规则（违反就会让图变成环）

| 规则 | 为什么 |
|---|---|
| **`config.py` / `constants.py` / `schemas.py` 是叶子，不许 import 别人** | 一旦反向依赖，所有东西都要 import 它们，环立刻出现 |
| **只有 `llm_client.py` 能 import `httpx`** | 否则"上游故障翻译"会散落到各个路由 —— 用 ruff `TID251` **机械强制** |
| **`schemas.py` 只描述形状，不碰 IO** | 它被 `llm_client` 和 `api/app` 同时依赖，碰了 IO 就成了公共耦合点 |

### 2.3 两个入口（📎 不同的进程，不是同一个东西）

```text
python -m app                      →  __main__.py
                                      ├─ configure_logging()     先配日志
                                      └─ uvicorn.run("app.api.app:app", log_config=None)
                                                │
uvicorn app.api.app:app            →  ─────────┘
                                      api/app.py
                                      ├─ configure_logging()     模块级（兜底）
                                      ├─ app = FastAPI(lifespan=lifespan, debug=..., docs_url=...)
                                      ├─ add_middleware(CORS)
                                      ├─ register_exception_handlers(app)
                                      └─ @app.middleware("http") add_request_id

python -m app.main                 →  main.py（命令行 demo / ping 上游，跑完即退出）
```

---

## 3. 启动与关闭：`lifespan` 的两条通道

### 3.1 ASGI 应用有两条入口通道（本项目用到两条）

| 通道 `scope["type"]` | 谁往里发消息 | 干什么 | 频率 |
|---|---|---|---|
| **`http`** | 每个 HTTP 请求 | 交给路由，送回响应 | **每请求一次** |
| **`lifespan`** | 启动器（uvicorn / `TestClient` 的 `with`） | `lifespan.startup` / `lifespan.shutdown` | **进程一生一次** |

> 📌 还有 `websocket`，本项目没用。

### 3.2 时序

```text
uvicorn 启动
   │
   ├─ lifespan.startup ──────────────────────────────────────────────┐
   │     ① engine.begin() → create_all()   建表（已存在的表不改）      │
   │     ② async with create_llm_client() as client:                 │
   │           app.state.llm_client = client                          │
   │           yield  ←──────── 服务运行期间停在这里 ──────────────┐   │
   │                                                              │   │
   ├─ 处理 N 个 http 请求（每个都可能用到 ①② 的产物）                │   │
   │                                                              │   │
   ├─ lifespan.shutdown ←─────────────────────────────────────────┘   │
   │     ③ 退出 async with → client.aclose()                          │
   │     ④ await engine.dispose()  释放连接池                          │
   └──────────────────────────────────────────────────────────────────┘
```

### 3.3 少了 `lifespan` 会怎样（📎 按接口分类）

| 端点 | 需要 lifespan 的什么 | 不开通道时 |
|---|---|---|
| `/health`、`/v1/models` | 什么都不要 | 200 |
| `/health/ready` | 只要一条**能用的连接**（引擎懒建立，与 lifespan 无关） | **200** |
| `POST /v1/conversations` 等用表的 | **表结构** | ❌ `no such table` |
| `/v1/upstream/models`、`/v1/chat/stream` | **`app.state.llm_client`** | ❌ `AttributeError: 'State' object has no attribute 'llm_client'` |

> ⭐ 一句话：**lifespan 的产物是「表结构」和「`app.state` 上的共享对象」，不是「连接」。**

---

## 4. 数据模型：ER + DDL

### 4.1 ER 图

```text
┌───────────────────────────────┐              ┌──────────────────────────────────┐
│ conversations                 │              │ llm_calls                        │
├───────────────────────────────┤              ├──────────────────────────────────┤
│ id            INTEGER  PK     │ 1          * │ id                 INTEGER  PK   │
│ title         VARCHAR(100) NN │◄─────────────│ conversation_id    INTEGER  NULL │
│ created_at    DATETIME   NN   │  ondelete=   │ model              VARCHAR(100)  │
│ updated_at    DATETIME   NN   │   SET NULL   │ prompt_tokens      INTEGER  NN   │
└───────────────────────────────┘              │ completion_tokens  INTEGER  NN   │
                                               │ total_tokens       INTEGER  NN   │
   relationship: Conversation.calls            │ status             VARCHAR(20)   │
                 LlmCall.conversation          │ created_at         DATETIME  NN  │
                                               └──────────────────────────────────┘
                                                        ▲
                                                        │ index=True
                                          ix_llm_calls_conversation_id
```

### 4.2 📎 真实 DDL（SQLite 建出来的）

```sql
CREATE TABLE conversations (
    id          INTEGER      NOT NULL,
    title       VARCHAR(100) NOT NULL,
    created_at  DATETIME     NOT NULL,
    updated_at  DATETIME     NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE llm_calls (
    id                INTEGER      NOT NULL,
    conversation_id   INTEGER,                    -- 可空
    model             VARCHAR(100) NOT NULL,
    prompt_tokens     INTEGER      NOT NULL,
    completion_tokens INTEGER      NOT NULL,
    total_tokens      INTEGER      NOT NULL,
    status            VARCHAR(20)  NOT NULL,
    created_at        DATETIME     NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE SET NULL
);

CREATE INDEX ix_llm_calls_conversation_id ON llm_calls (conversation_id);
```

### 4.3 三个「不这么写就会错」的点

| 设定 | 不这样会怎样 |
|---|---|
| `ondelete="SET NULL"`（**不是 CASCADE**） | 📎 写 CASCADE 时删 1 个对话会连带删掉 900 token 的账 |
| `conversation_id` 可空（`int \| None`） | 📎 写成 `int` 就是 500（单次调用可以不属于任何对话） |
| `relationship` 上**故意不写** `cascade="all, delete-orphan"` | 写了 ORM 会先把外键置 NULL 再删，等于绕过数据库层的 `SET NULL` |

> 📌 副作用要知道：被删对话的账单 `conversation_id = NULL`，**无法区分「从没属于过」和「父行被删」**。

---

## 5. 端点总表

📎 由 `app.routes` 实读。共 **17 条**：13 条业务 + 4 条文档。

| 方法 | 路径 | 请求体 / 参数 | 响应模型 | 成功码 | 主要错误 |
|---|---|---|---|---|---|
| GET | `/health` | — | `{"status": "ok"}` | 200 | — |
| GET | `/health/ready` | — | `{"status": "ready"}` | 200 | 503 `DB_UNAVAILABLE` |
| GET | `/v1/models` | `?prefix=&limit=`(1..100, 默认 20) | `{"total", "items": [str]}` | 200 | 422 |
| GET | `/v1/models/latest` | — | `{"model_name"}` | 200 | — |
| GET | `/v1/models/{model_name}` | 路径参数 | `{"model_name"}` | 200 | 404 `MODEL_NOT_FOUND` |
| POST | `/v1/chat` | `ChatRequest` | `ChatResponse` | 200 | 400 / 404 / 422 |
| GET | `/v1/upstream/models` | — | `ModelListResponse` | 200 | 502 `UPSTREAM_*` |
| POST | `/v1/conversations` | `ConversationIn` | `ConversationStatsOut` | **201** | 422 |
| GET | `/v1/conversations/{conv_id}` | 路径参数 | `ConversationStatsOut` | 200 | 404 `CONVERSATION_NOT_FOUND` / 422 |
| PATCH | `/v1/conversations/{conv_id}` | `ConversationPatch` | `ConversationStatsOut` | 200 | 404 / 422 |
| DELETE | `/v1/conversations/{conv_id}` | 路径参数 | **无 body** | **204** | 404 / 422 |
| GET | `/v1/conversations` | `?limit=`(1..100, 默认 20) `&after_id=`(≥0) | `ConversationPageOut` | 200 | 422 |
| POST | `/v1/chat/stream` | `ChatRequest` | **SSE**（`text/event-stream`） | 200 | **502（pre-flight）** / 400 / 404 / 422 |
| GET | `/docs` `/redoc` `/openapi.json` `/docs/oauth2-redirect` | — | — | 200 | **prod 下全 404** |

### 5.1 两个容易混的点

| 点 | 说明 |
|---|---|
| `/v1/models` vs `/v1/upstream/models` | 前者读**硬编码常量** `KNOWN_MODELS = ["deepseek-flash", "deepseek-v4-pro"]`；后者**真调上游**。形状也不同（`items: [str]` vs `items: [ModelItem]`）—— 待办 #39 |
| `/v1/chat` vs `/v1/chat/stream` | 前者是 **`echo` 占位**（`{"content": "[echo] hi"}`），后者才真调上游 |

---

## 6. 成功响应形状（逐端点真实样本）

📎 全部是实跑输出（dev 环境，SQLite）。

### 6.1 健康检查

```json
GET /health          → 200  {"status": "ok"}
GET /health/ready    → 200  {"status": "ready"}
```

> 📌 形状**故意不同**：`ok` = 进程活着（不查依赖）；`ready` = 能接流量（查过库）。

### 6.2 模型清单（两种形状）

```json
GET /v1/models            → 200  {"total": 2, "items": ["deepseek-flash", "deepseek-v4-pro"]}
GET /v1/models?prefix=d   → 200  {"total": 2, "items": ["deepseek-flash"]}
GET /v1/models/latest     → 200  {"model_name": "deepseek-flash"}
GET /v1/models/deepseek-flash → 200  {"model_name": "deepseek-flash"}
```

```json
GET /v1/upstream/models   → 200
{
  "total": 2,
  "items": [
    {"id": "deepseek-flash",  "name": null, "context_window": null},
    {"id": "deepseek-v4-pro", "name": null, "context_window": null}
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `total` | int | **我们算的**条数（过滤后），不是上游返回的条数 |
| `items[].id` | str 必填 | 调 `/v1/chat` 时传它 |
| `items[].name` | str \| null | 供应商展示名，**可能没有** |
| `items[].context_window` | int \| null | 上下文窗口 |

### 6.3 非流式对话（当前是 echo 占位）

```json
POST /v1/chat  → 200  {"content": "[echo] hi", "model": "deepseek-flash", "usage_tokens": 0}
```

`ChatRequest` 的字段（📎 从 `model_fields` 导出）：

| 字段 | 类型 | 必填 |
|---|---|---|
| `messages` | `list[Message]` | ✅ |
| `model` | `str \| None` | 可选（None → 回落 `settings.llm_model`） |
| `temperature` | `float` | 可选（默认 0.7） |
| `max_tokens` | `int \| None` | 可选（None → **不放进上游请求体**） |
| `conversation_id` | `int \| None` | 可选（传了就先校验存在） |

`Message` = `{role: "system"|"user"|"assistant", content: str}`

### 6.4 对话对象（**四种接口同一种形状**）

```json
POST /v1/conversations → 201
GET  /v1/conversations/1 → 200
PATCH /v1/conversations/1 → 200
{
  "id": 1,
  "title": "示例",
  "created_at": "2026-11-02T06:58:26.093557Z",
  "updated_at": "2026-11-02T06:58:26.130310Z",
  "call_count": 0,
  "total_tokens": 0
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int | 数据库生成 |
| `title` | str | 已 `strip_whitespace`、`1 ≤ len ≤ 100` |
| `created_at` / `updated_at` | datetime | **UTC，带 `Z`**；`updated_at` 只在 PATCH 后变 |
| `call_count` | int | 这个对话发生过几次 LLM 调用（`0` 而不是 `null`） |
| `total_tokens` | int | 累计 token（`0` 而不是 `null`） |

> ⭐ **为什么 POST / GET / PATCH 必须同形**：前端把 POST 的返回值直接塞进列表缓存，少两个字段那条数据就会缺字段。

```json
DELETE /v1/conversations/1 → 204  （body 为空，长度 0）
```

### 6.5 分页

```json
GET /v1/conversations?limit=2 → 200
{
  "items": [ {…ConversationStatsOut…}, {…} ],
  "total": 2,
  "limit": 2,
  "next_cursor": null,
  "has_more": false
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `items` | `list[ConversationStatsOut]` | 本页数据 |
| `total` | int ≥ 0 | **命中总数**，不是本页条数 |
| `limit` | int ≥ 1 | 客户端传的上限（回显） |
| `next_cursor` | int \| null | **下一页传 `after_id` 用这个值**；`null` = 没有下一页 |
| `has_more` | bool | 还有没有下一页 |

> 📌 游标是 **`id` 本身**（`id > after_id`），不是 offset。📎 offset 在翻页期间删数据会漏一条。

---

## 7. 错误形状（统一 envelope）

### 7.1 骨架

```text
HTTP/1.1 <4xx|5xx>
x-request-id: <12 位 hex>          ← 恒等于 body 里的 request_id
content-type: application/json

{"error": {"code": "<稳定码>", "message": "<人话>", "request_id": "<同一个 id>"}}
                                                              └─ 422 才有 details
```

| 键 | 谁该用 | 会不会变 |
|---|---|---|
| `code` | **机器判断**（客户端只认它） | 🚫 **稳定，不改** |
| `message` | 人看 / 日志 | ✅ 可改文案 |
| `request_id` | 报障时给用户，用来查日志 | 每请求不同 |
| `details` | 只有 422 | 结构固定 |

### 7.2 📎 七种真实响应（字节数也在）

```jsonc
// 405 —— 方法没注册（message 是英文，框架给的）
{"error":{"code":"METHOD_NOT_ALLOWED","message":"Method Not Allowed","request_id":"dbbcd4e7aa33"}}

// 400 —— 业务规则
{"error":{"code":"LAST_MESSAGE_NOT_USER","message":"最后一条消息必须是 user，当前是 assistant","request_id":"262618e9519a"}}

// 404 —— 模型不存在（业务码）
{"error":{"code":"MODEL_NOT_FOUND","message":"模型不存在：nope","request_id":"12a1f5891c2c"}}

// 404 —— 路由不存在（框架兜底码）
{"error":{"code":"NOT_FOUND","message":"Not Found","request_id":"d092e2eb3b38"}}

// 404 —— 对话不存在（业务码）
{"error":{"code":"CONVERSATION_NOT_FOUND","message":"对话不存在：999","request_id":"36fe5cd963bd"}}

// 422 —— 校验失败（多一个 details）
{"error":{"code":"VALIDATION_ERROR","message":"请求参数校验失败","request_id":"db5073bf0627",
  "details":[{"loc":["body","messages"],"msg":"List should have at least 1 item after validation, not 0","type":"too_short"}]}}

// 500 —— 兜底（不含任何堆栈）
{"error":{"code":"INTERNAL_ERROR","message":"服务内部错误","request_id":"f475146e313e"}}
```

### 7.3 三种 404 必须能分开

| 请求 | `code` | 谁产生的 |
|---|---|---|
| `GET /v1/nope` | `NOT_FOUND` | **Starlette**（路由未命中） |
| `GET /v1/models/nope` | `MODEL_NOT_FOUND` | **业务代码**（`AppError`） |
| `GET /v1/conversations/999` | `CONVERSATION_NOT_FOUND` | **业务代码**（`AppError`） |

### 7.4 业务码 → 状态码（唯一映射表）

| `code` | HTTP |
|---|---|
| `LAST_MESSAGE_NOT_USER` | 400 |
| `MODEL_NOT_FOUND` / `CONVERSATION_NOT_FOUND` | 404 |
| `UPSTREAM_UNREACHABLE` / `UPSTREAM_BAD_STATUS` / `UPSTREAM_MALFORMED` | 502 |
| `DB_UNAVAILABLE` | 503 |
| （未登记的码） | **400**（兜底防"漏登记"，不是"猜对"） |

### 7.5 `details` 是被**过滤过**的（这条最容易被忽略）

📎 pydantic 原始 `exc.errors()[0]` 有 **6 个字段**：

```json
{"type":"too_short", "loc":["messages"], "msg":"…",
 "input": [],                                   ← 🔴 用户提交的原值，必须丢
 "ctx":{"field_type":"List","min_length":1,"actual_length":0},
 "url":"https://errors.pydantic.dev/2.13/v/too_short"}
```

我们只留 `loc` / `msg` / `type`。📎 且原始 `loc` 是 `["messages"]`，我们的是 `["body","messages"]`。

### 7.6 🔴 500 是唯一没有 CORS 头的响应

| 响应 | `Access-Control-Allow-Origin` |
|---|---|
| 404（或其他经 ⑤ 的） | ✅ `http://localhost:5173`，另有 `vary: Origin` |
| **500** | ❌ **一个 CORS 头都没有** |

原因：500 由 **① ServerErrorMiddleware** 产出，**不经过 ④ CORSMiddleware**。
后果：浏览器里前端拿 500 是**网络错误**，读不到 body、读不到 `request_id`。→ 待办 **#57**。

---

## 8. SSE 帧形状

### 8.1 响应头

```text
HTTP/1.1 200 OK
content-type: text/event-stream; charset=utf-8
cache-control: no-cache
x-accel-buffering: no                 ← 让 nginx 不要缓冲
transfer-encoding: chunked
```

### 8.2 七种帧（📎 全部来自源码里的 `yield`）

| # | 帧体 | 什么时候发 | 前端怎么用 |
|---|---|---|---|
| 1 | `{"status": "thinking"}` | **首帧**，一进生成器就发 | 立刻显示"思考中" |
| 2 | `{"delta": "<文字>"}` | 每个有内容的上游帧 | 追加到回答 |
| 3 | `{"finish_reason": "stop"\|"length"}` | 上游末帧（**只在是字符串时**） | 判断"说完了 / 被截断" |
| 4 | `{"usage": {…}}` | 上游给 usage 时（可能在纯用量帧，也可能和 finish 挤一帧） | 显示 token 用量 |
| 5 | `{"error": {"code": "STREAM_NO_CONTENT", …}}` | 上游 200 但**一帧内容都没有** | 明确告知"这次空" |
| 6 | `{"error": {"code": "STREAM_FAILED", …}}` | 流**已开始后**出异常 | 提示中断 |
| 7 | `[DONE]` | **正常 / 异常两条路都发** | 结束标记 |

### 8.3 正常路径的帧序列

```text
data: {"status": "thinking"}
data: {"delta": "你"}
data: {"delta": "好"}
data: {"finish_reason": "stop"}
data: {"usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}
data: [DONE]
```

⭐ 每帧 = `data: ` + JSON + **两个换行**。少了那两个换行，前端不会触发事件。

### 8.4 三条退出路径都发 `[DONE]`

```text
正常结束       → … → data: [DONE]
零内容         → data: {"error":{"code":"STREAM_NO_CONTENT",…}} → data: [DONE]
流内异常       → data: {"error":{"code":"STREAM_FAILED",…}}     → data: [DONE]
客户端断开     → （发不出去，但 finally 里做清理 + 账单标 aborted）
```

> ⚠️ **为什么 `[DONE]` 不能在 `finally` 里发一次**：客户端断开时 Starlette 会往生成器抛 `GeneratorExit`（继承 `BaseException`），
> 在 `finally` 里 `yield` 会触发 `RuntimeError: async generator ignored GeneratorExit`。所以两条路各写一次。

### 8.5 pre-flight：状态码还没发出去的最后机会

```text
await client.open_chat_stream(body)     ← 只等响应头
   ├─ 抛 AppError（连不上 / 状态码不对） → 502（此时响应头还没发，改得了）
   └─ 成功 → return StreamingResponse(...)   ← 从这一刻起状态码定死为 200
```

🔴 如果把这一行挪进生成器：上游失败会变成 **200 + 流里一个 error 帧** —— 日志 200、用户看到空回答。
📎 测试 `test_stream_preflight_failure_changes_status_code` 专门钉这一条。

---

## 9. 配置形状（三层来源）

### 9.1 优先级

```text
   shell / IDE / Docker 的环境变量        ← 优先级最高
            │
            ▼
   os.environ（进程内字典）  ◄── conftest.py 在 import app 之前往这里写
            │
            │            .env 文件（磁盘，只有 pydantic-settings 读它）
            │                    │
            └────────┬───────────┘
                     ▼
              Settings()  ← 模块级单例，import 那一刻定型
                     │
                     ▼
             settings.<字段>  ← 全项目只从这里读，不直接读 os.environ
```

| 事实 | 说明 |
|---|---|
| **进程环境变量 > `.env` > 字段默认值** | 📎 `.env` 写 `prod`、进程写 `dev` → 结果是 `dev` |
| 读 `.env` **不会**进 `os.environ` | 📎 `Settings()` 读到了，但 `"APP_NAME" in os.environ` 仍是 `False` |
| `settings` 是**模块级单例** | import 之后再改 `os.environ` 无效 |
| `engine` 也是模块级 | **一个进程只能绑一个库 URL** → 测试隔离只能在同库内做 |

### 9.2 🔴 一个不对称的静默失效

| 未知键放在哪 | 结果 |
|---|---|
| `.env` 里写 `UNKNOWN_KEY=1` | ❌ `ValidationError: Extra inputs are not permitted [type=extra_forbidden]` |
| 进程环境变量里 `UNKNOWN_KEY=1` | ✅ **静默忽略** |

> 后果：`.env` 里拼错键名会被抓，**shell 里拼错不会**（`$env:DATABASE_URLL` 会静默用默认值）。

### 9.3 全部配置项

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `app_name` | str | `llm-app-engineering` | 应用名 |
| `app_env` | `Literal["dev","prod"]` | `dev` | 写别的**直接校验失败** |
| `debug` | bool | `False` | 接进 `FastAPI(debug=…)` |
| `host` | str | `127.0.0.1` | 监听地址 |
| `port` | int | `8000` | 监听端口 |
| `database_url` | str | `sqlite+aiosqlite:///./app.db` | 相对**当前工作目录** |
| `llm_api_key` | `str \| None` | `None` | 缺了不报错，但会拼出假 token → 401（所以 `ping` 先查它） |
| `llm_base_url` | str | `https://api.deepseek.com` | 末尾不带斜杠 |
| `llm_model` | str | `deepseek-flash` | 客户端没指定时兜底 |
| `request_timeout` | float | `30.0` | httpx 默认只有 5 秒，LLM 不够 |

### 9.4 启动即崩的保护

```text
APP_ENV=prod + DEBUG=true
   └─ @model_validator(mode="after") 抛 ValueError
        └─ settings = Settings() 在模块体里 → import 就崩 → 进程 exit_code=1
```

📎 为什么必须崩、不能静默改 False：`debug=True` 会让 `@app.exception_handler(Exception)` 不执行，**traceback 直接进响应体**。

---

## 10. 日志形状

### 10.1 一条日志经过四道闸

```text
logger.info("…")            logger.error("…")
      │
      ▼
① 级别闸    logger.getEffectiveLevel()  ── 不够高 → 直接丢弃（参数都不展开）
      │
      ▼
② logger 自己的 handler（本项目：没有）→ 交给 propagate
      │
      ▼
③ 沿 logger 树向上到 root  ← 名字是点分层级：app < app.api < app.api.app
      │
      ▼
④ root 的 handler（StreamHandler → stderr）→ Formatter 拼格式 → 输出
```

### 10.2 树形（📎 实测 `loggerDict`）

```text
root  (WARNING, 有我们的 handler)
 ├── app                       ← 只占名字（PlaceHolder）
 │    └── app.api.app          ← 模块级 logger，实际打日志的就是它
 ├── app.errors                ← 500 的 traceback 从这里出
 ├── app.llm_client
 ├── app.logging_setup
 ├── uvicorn                   ← uvicorn 的三个 logger 由它自己配（log_config=None 后由我们接管）
 ├── uvicorn.error
 └── uvicorn.access            ← 本项目**主动关掉**（访问日志由中间件自己打，带 request_id）
```

### 10.3 输出格式

```text
2026-11-02 00:19:56,291 INFO    app.api.app | POST /v1/chat/stream -> 200 11.6ms request_id=07e575948a97
└──────── 时间 ────────┘ └级别┘ └── logger 名 ──┘ └──────────── message ────────────────────────┘
```

| 设定 | 值 | 为什么 |
|---|---|---|
| `dictConfig(force=True)` | — | 幂等：重复调用不会叠 handler |
| `disable_existing_loggers` | **`False`** | 默认 `True` 会禁掉未在 `loggers` 里命名的已有 logger（📎 `app.errors` 会被禁 → 500 traceback 全哑） |
| `uvicorn.access` | `disabled` | 访问日志我们自己打（要带 `request_id` 和耗时） |

---

## 11. 测试形状

### 11.1 四层结构

```text
tests/
├── conftest.py            ① 环境地基（import app 之前就位）
│     ├─ 删旧测试库（.db / -wal / -shm）
│     ├─ os.environ["DATABASE_URL"] = %TEMP%/llm-app-test.db
│     ├─ import app  ← 到这一行 settings 才定型
│     ├─ _truncate_all()   清表（子 → 父）
│     └─ client fixture    with TestClient(app) → 触发 lifespan → 清表 → yield
│
├── fakes.py               ② 假上游（不碰网络）
│     ├─ FakeChatStream(LlmChatStream)   aiter_chunks / aclose / closed 标志
│     └─ FakeLlm(LlmClient)              list_models / open_chat_stream / last_body
│
├── test_smoke.py          ③ 地基自检（2）      证明 tests/ 能跑 + lifespan 跑过 + 临时库生效
├── test_conversations.py  ④ HTTP 契约（9）     CRUD 全生命周期 / 分页 / 422 / 404
├── test_upstream.py       ⑤ 上游接线（6）      假 LLM 200 / 三种 502 / pre-flight / 帧被消费
└── test_errors.py         ⑥ 错误形状（7）      envelope / 三种 404 / 422 details / 500 不泄漏
```

📎 当前 **24 passed**。

### 11.2 依赖注入图（fixture 与 override）

```text
                    conftest.client  (function 作用域)
                            │
                            ▼
                  with TestClient(app)      ← 触发 lifespan：建表 + 造 client
                            │
                            ▼
                     _truncate_all()        ← 清表（必须在 with 之后，否则 no such table）
                            │
                            ▼
                        yield c  ──────────┬───────────────────────────────┐
                                           │                               │
                    普通测试直接用 client    │   需要假上游的测试还要：          │
                                           │   app.dependency_overrides[   │
                                           │       get_llm_client] = lambda: fake
                                           │                               │
                                           └──────► 请求穿过七层 ◄──────────┘
                                                        │
                                            get_llm_client 被换成 fake
                                                        │
                                    路由拿到 fake → 不碰 network / 不花钱
```

### 11.3 测试 ↔ 代码靠什么连上（**不是 import**）

📎 `tests/test_conversations.py` **一行都没 import 源码**（只有 `typing.cast` / `pytest` / `TestClient`）。

| # | 线 | 什么时候绑上 |
|---|---|---|
| ① | fixture → 应用对象 | **import 时**（`conftest.py` 里唯一的 `from app.api.app import app`） |
| ② | 测试 → 路由 | **每条请求时**，拿 **URL 字符串**查路由表 |
| ③ | 断言 → 契约 | 运行时读 JSON 键名（无类型检查） |

📎 写错的后果：`/v1/conversation`（少 s）→ 404 `NOT_FOUND`；`PUT /v1/conversations` → 405 `METHOD_NOT_ALLOWED`。

### 11.4 两个必须记住的测试坑

| 坑 | 事实 |
|---|---|
| `raise_server_exceptions` 默认 `True` | 测"500 的响应体"必须 `TestClient(app, raise_server_exceptions=False)`；**但别改共享 fixture**，否则所有真 bug 都退化成"500 响应" |
| `TestClient` 下**没有 TCP 背压** | 📎 客户端一帧不读时 `get_db` 也已收尾（`checkedout=0`）→ **#59 在这里复现不出来**，12e 必须起真 uvicorn |

---

## 12. 状态机

### 12.1 账单（`llm_calls.status`）三态

```text
                     开流前（yield 之前）
                            │
                            ▼
                     ┌─────────────┐
                     │   pending   │   db.add + flush（还没持久化）
                     └──┬───────┬──┘
        拿到 usage 且完成   │       │  客户端断开 / 上游异常
                        ▼       ▼
             ┌──────────────┐  ┌──────────────┐
             │  completed   │  │   aborted    │
             └──────────────┘  └──────────────┘
                   │                  │
                   └────── 由 get_db 在请求结束时统一 commit ──────┘
```

| 状态 | 含义 | 谁写它 |
|---|---|---|
| `pending` | 流已经开始，还没结束 | 生成器一开始 |
| `completed` | 拿到完整 `usage` | `record_usage()` |
| `aborted` | 客户端断开 / 上游报错 | `except` 分支（**同步赋值**，不能 `await`） |

> ⚠️ `aborted` 必须是**同步赋值**：被取消后继续 `await` 会抛 `RuntimeError`。
> 📎 上游**已经产出的 token 照样收费**，所以这行不能删。

### 12.2 对话的一生

```text
POST /v1/conversations
      │  201 + ConversationStatsOut
      ▼
  ┌────────┐  PATCH（改 title）   ┌────────┐
  │  存在   │ ──────────────────► │  存在   │   updated_at 变，created_at 不变
  └───┬────┘                      └───┬────┘
      │ DELETE                        │ DELETE
      ▼                               ▼
  ┌────────┐                     ┌────────┐
  │ 不存在  │  再 GET / DELETE → 404 CONVERSATION_NOT_FOUND
  └────────┘
      │
      └─ 它名下的 llm_calls：conversation_id 被置 NULL，**行保留**（账不能丢）
```

---

## 13. 附录：速查

### 13.1 常量

| 常量 | 值 | 位置 |
|---|---|---|
| `HEADER_REQUEST_ID` | `X-Request-ID` | [constants.py](../../src/app/constants.py) |
| `KNOWN_MODELS` | `["deepseek-flash", "deepseek-v4-pro"]` | [app.py](../../src/app/api/app.py) |
| `ALLOWED_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173"]` | [app.py](../../src/app/api/app.py) |
| `MAX_ERROR_BODY_CHARS` | `500` | [llm_client.py](../../src/app/llm_client.py) |

### 13.2 文件职责一句话

| 文件 | 一句话 | 不许做什么 |
|---|---|---|
| `config.py` | 全部可调参数 + 跨字段校验 | 不 import 任何内部模块 |
| `constants.py` | 必须跨模块一致的常量 | 同上 |
| `schemas.py` | 对外契约（请求 / 响应形状） | 不碰 IO |
| `models.py` | ORM 表定义 | 不含业务逻辑 |
| `database.py` | engine（池）+ SessionMaker（模具） | 不知道 HTTP 存在 |
| `errors.py` | `AppError` + 码↔状态码 + 4 个处理器 + 单一出口 | 不认识具体业务 |
| `llm_client.py` | 唯一 import `httpx`、唯一翻译上游故障 | 不 import `fastapi` |
| `logging_setup.py` | 日志配置唯一一处 | — |
| `api/deps.py` | 依赖的集中地（可替换的接缝） | 不含路由 |
| `api/app.py` | FastAPI 对象 + lifespan + 全部路由 | 不写上游协议细节 |
| `main.py` | 命令行 demo / ping | 不是 HTTP 入口 |
| `__main__.py` | `python -m app` 的 HTTP 入口 | 不直接建 app |

---

## 更新日志

| 日期 | 变更 |
|---|---|
| 2026-11-02 | 建立。13 节：七层栈 / 模块依赖 / lifespan / ER+DDL / 端点总表 / 成功形状 / 错误形状 / SSE 帧 / 配置 / 日志 / 测试 / 状态机 / 速查 |
