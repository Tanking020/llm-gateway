# 架构与形状地图（Architecture & Shapes）

> **这个文件只干一件事：把「长什么样」画出来。**
> 谁调用谁、请求穿过哪些层、响应体有哪些字段、错误码长什么样、SSE 有哪几种帧、配置从哪来、日志树是什么形状。
>
> **不写**：为什么这么设计（→ [decisions.md](decisions.md)）、做到哪了（→ [roadmap.md](roadmap.md)）、
> 原理推导与实测过程（→ [stage1-fastapi.md](../notes/stage1-fastapi.md)）。
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
| [1. 请求穿过的七层](#1-全景一次请求穿过的七层) | 这个请求经过了哪些中间件？异常在哪一层被接住？**请求头分哪四类、两样「ID」怎么不混（§1.5）？** |
| [2. 代码分层与依赖](#2-代码分层与模块依赖) | 改一个文件会影响谁？**一个请求按什么顺序拿到资源（§2.4）？`app.py` 里谁调谁（§2.5）？** |
| [3. 启动与关闭](#3-启动与关闭lifespan-的两条通道) | 表什么时候建？client 什么时候造？ |
| [4. 数据模型](#4-数据模型er--ddl) | 有几张表？外键怎么连？删对话账单会怎样？ |
| [5. 端点总表](#5-端点总表) | 有哪些接口？各自收什么、回什么、什么状态码？ |
| [6. 成功响应形状](#6-成功响应形状逐端点真实样本) | 每个成功响应到底有哪些键？ |
| [7. 错误形状](#7-错误形状统一-envelope) | 出错时前端拿到什么？怎么区分两种 404？**每个码是谁产生的（§7.7）？** |
| [8. SSE 帧形状](#8-sse-帧形状) | 流里有几种帧？顺序是什么？**每个时刻出错会怎样？**（§8.6 完整时序） |
| [9. 配置形状](#9-配置形状三层来源) | 这个配置项从哪读来的？谁优先？**改它会动到谁（§9.5）？** |
| [10. 日志形状](#10-日志形状) | 一条日志经过哪几道闸？ |
| [11. 测试形状](#11-测试形状) | 测试怎么连到代码？fixture 依赖谁？ |
| [12. 状态机](#12-状态机) | 账单的四态怎么流转？对话的一生？ |
| [13. 运行形态](#13-运行形态一个进程两个外部依赖) | 这个服务在外面长什么样？几个进程、几个池、几个外部依赖？ |
| [14. 决策 ↔ 代码 ↔ 测试](#14-决策--代码--钉住它的测试一张对账表) | 这条决策落在哪一行？改这行会让哪条决策失效？ |
| [15. 附录：速查](#15-附录速查) | 常量在哪？每个文件一句话？ |

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
| ③ BaseHTTPMiddleware（含 `add_request_id`） | **我们**：`@app.middleware("http")` | [app.py](../src/app/api/app.py) |
| ④ CORSMiddleware | **我们**：`app.add_middleware(CORSMiddleware, ...)` | [app.py](../src/app/api/app.py) |
| ⑤ ExceptionMiddleware | **FastAPI 自动**（handler 表由 `register_exception_handlers(app)` 填） | [errors.py](../src/app/errors.py) |
| ⑥ AsyncExitStackMiddleware | FastAPI 自动 | — |
| ⑦ APIRouter → 路由函数 | **我们**：`@app.get/@app.post/...` | [app.py](../src/app/api/app.py) |

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

### 1.5 请求头全景：四类 + 两类「ID」（谁写、谁能伪造）

> ⭐ **判据：能撤销、存库、伪造不了的才是凭据；只能对日志、谁都能编的是追踪号。**
> 两者都叫 "ID"，但 `X-API-Key` 回答「**你是谁**」，`X-Request-ID` 回答「**这是哪一次请求**」。

| 类 | 头 | 方向 | 谁写 | 客户端伪造会怎样 | 代码位置 |
|---|---|---|---|---|---|
| ① **凭据** | `X-API-Key` | 客户端 → 我们 | `python -m app.keys create`（明文只出现一次） | 查不到 sha256 → **401** | `deps.require_user` / `auth.find_user_by_key` |
| ② **追踪** | `X-Request-ID` | 客户端 ↹ 我们 | 客户端可选；nginx `$rid`（[决策 57](decisions.md)）；应用兜底 12 位 hex | 只影响日志串联，**不影响鉴权** | `constants.HEADER_REQUEST_ID` / 中间件 / `nginx.conf` 的 `map` |
| ③ **代理链路** | `X-Real-IP`、`X-Forwarded-For`、`X-Forwarded-Proto` | nginx → 应用 | **只有 nginx** | 被 uvicorn 丢弃（只信 `FORWARDED_ALLOW_IPS`，[决策 47](decisions.md)） | `nginx.conf` / `docker-compose.yml` |
| ④ **上游与协议** | `Authorization: Bearer <LLM_API_KEY>`、`Content-Type`、`Origin` | 应用 → DeepSeek；客户端 → 我们 | 应用自己拼 / 客户端 | `Authorization` 进来**根本不被读取**（我们只认 `X-API-Key`） | `llm_client.py` / `constants.ALLOWED_ORIGINS` |

**一次请求里它们各自出现在哪**（📎 与 §1 的七层、§10 的日志字段一一对应）：

```text
客户端 ──X-API-Key + (可选)X-Request-ID──▶ nginx ──+X-Real-IP / X-Forwarded-For / X-Forwarded-Proto
                                              │      +X-Request-ID: $rid        ← 边界定稿（决策 57）
                                              ▼
                                             app ──Authorization: Bearer <LLM_API_KEY>──▶ DeepSeek
                                              │
客户端 ◀── X-Request-ID（同值回显）/ WWW-Authenticate（仅 401）/ Retry-After（429·503）/ ACAO（CORS）
```

⚠️ **回程三样头各有唯一来源，别混**：
- `WWW-Authenticate: ApiKey` —— 只在 **401**，由 `deps._unauthorized()` 给（RFC 9110 §15.5.2）
- `Retry-After` —— 只在 **429 / 503**，由 `AppError(headers=...)` 给
- `X-Request-ID` —— **每个响应都有**（含 nginx 自己产生的 413/502/504），且响应头 / nginx `rid=` / 应用日志 `request_id` 三处同值

⚠️ **两个反直觉点**：
1. **`Authorization` 不是我们的鉴权头**。有人写 `Authorization: Bearer sk_...` 一样 401 —— 那个头只用于「我们 → 上游」那一段。
2. **`X-Request-ID` 永远不能当凭据**。它是可猜、可伪造、不存库的；能靠它进来的系统等于没有鉴权。

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
| `api/deps.py` | `auth`, `config`, `constants`, `database`, `errors`, `llm_client`, `models`, `ratelimit` |
| `auth.py` | `models` |
| `keys.py` | `auth`, `database`, `models` |
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

### 2.4 依赖注入：一次请求拿到哪些资源、什么时候还

📎 2026-11-04 实测（把 `get_settings` / `get_db` 换成会打日志的版本，用 `TestClient` 打真路由）：

```text
POST /v1/chat
  dep settings enter ─→ dep db enter ─→ 〔路由跑完、响应对象就绪〕─→ dep db exit

POST /v1/chat/stream
  dep settings enter ─→ dep db enter ─→ client.open_chat_stream 返回
      ─→ gen start ─→ …n 帧… ─→ gen end ─→ upstream aclose ─→ dep db exit
                                                              ▲
                                          依赖的收尾排在【整条流之后】
```

⭐ 三条顺序规则：

| 规则 | 依据 |
|---|---|
| **解析顺序 = 函数签名里的参数顺序** | `chat(request, config, db)` → config 先于 db；`chat_stream(request, client, config, db)` 同理。📎 实测 `dep settings enter` 在 `dep db enter` 之前 |
| **真正"有收尾"的只有 `yield` 依赖** | `return` 依赖没有后半段；本项目只有 `get_db` 是 `yield` |
| **收尾发生在"响应彻底结束"之后** | 流式路由的"返回"是 `return SseResponse(...)`，此时生成器还没跑 → 收尾要等生成器结束（对应 §8.6 的 ⑪） |

### 2.4.1 五种资源，五种生命周期

| 依赖 | 提供者 | 何时创建 | 何时释放 | 测试能不能换 |
|---|---|---|---|---|
| `SettingsDep` | `get_settings()` 直接 `return settings` | **import 那一刻**（模块级单例） | 进程退出 | ✅ `dependency_overrides[get_settings]` |
| `LlmClientDep` | `get_llm_client(request)` 读 `app.state.llm_client` | **lifespan 启动段** | lifespan 关闭段 `aclose()` | ✅ `dependency_overrides[get_llm_client]` |
| `DbDep` | `get_db()` **yield** 一个会话 | 依赖被解析时（`SessionMaker()`） | 生成器收尾时（`commit` / `rollback` 之后） | ✅ 也能换，但换了就测不到真事务 |
| `CurrentUserDep` | `require_user(request, db, config)` 读 `X-API-Key` → 查库 → **扣令牌** | 依赖被解析时（每个需鉴权的路由） | 无状态（令牌扣了就扣了，不退） | ✅ 换 `app.state.rate_limiter` 为假时钟版 |
| `UpstreamSlotDep` | `get_upstream_slot()` **yield** 一个名额 | 参数最靠前 → **最先解析** | **最后收尾**（依赖按反序退场）→ 覆盖到 `db.commit` 之后 | ✅ 测试里直接替换 `app.state.upstream_semaphore` |

> 📌 会话对象 ≠ 连接：会话在解析时就造好，**连接**要到第一条 SQL 才向池里借，
> `commit()` / `rollback()` 一结束就把连接还回池 —— 所以"会话活得比连接久"。

⭐ 判据：**「依赖」不等于「每请求新建」。** 上表只有 `DbDep` 是请求级；
`settings` 与 `llm_client` 都是进程级，`Depends` 只负责**把已有对象递进来**，
顺带提供"可被替换的接缝"（这正是测试能绕过真库与真上游的原因，见 §11.2）。

⚠️ 上面这些资源各自**占用多久**不写在这里 —— 连接池那一半的唯一出处是
[tests/README.md](../tests/README.md) §4.2，闸门见 §4.7。
📌 闸门这一行有个反直觉点：**槽位持有到「整条流结束」**，比 `DbDep` 还长一截 ——
而这一点是**要的**（"同时在生成的上游调用数"本来就该按整条流算）；同一个 `yield` 机制在 `get_db` 那里却是缺陷（#59）。

### 2.5 `app.py` 内部调用链（857 行怎么读）

`app.py` 是**组合层**：全部路由 + 装配 + SSE 生成器都在同一个文件里，没有 `services/` 层（待办 #63）。
所以"改一处会影响谁"只能靠文件内部的调用关系看。

#### 2.5.1 路由 → 共用函数（箭头 = 调用）

```text
GET   /health ─────────────────→ health
GET   /health/ready ───────────→ health_ready ──────────→ AppError(DB_UNAVAILABLE)
GET   /v1/models ──────────────→ list_models（读常量 KNOWN_MODELS）
GET   /v1/models/latest ───────→ latest_model
GET   /v1/models/{model_name} ─→ get_model ─────────────→ AppError(MODEL_NOT_FOUND)
POST  /v1/chat ────────────────→ chat ──┬───────────────→ ensure_last_message_is_user
                                        └─(传了 id 才走)→ require_conversation
GET   /v1/upstream/models ─────→ upstream_models ───────→ client.list_models()
POST  /v1/conversations ───────→ create_conversation ───→ _fetch_conversation_stats
GET   /v1/conversations/{id} ──→ get_conversation ──────→ _fetch_conversation_stats
PATCH /v1/conversations/{id} ──→ update_conversation ─┬─→ require_conversation
                                                      └─→ _fetch_conversation_stats
DELETE /v1/conversations/{id} ─→ delete_conversation ──→ require_conversation
GET   /v1/conversations ───────→ list_conversations ──┬─→ _conversation_stats_stmt
                                                      └─→ _row_to_stats
POST  /v1/chat/stream ─────────→ chat_stream ────────┬─→ ensure_last_message_is_user
                                                     ├─→ require_conversation
                                                     ├─→ client.open_chat_stream()  ← pre-flight
                                                     └─→ event_source()  ← 生成器，逐帧 yield
                                                           ├─ _as_dict / _as_int
                                                           ├─ record_usage()
                                                           └─ upstream.aiter_chunks() / aclose()
```

#### 2.5.2 共用函数的扇入：改一次 = 动几个端点

| 函数 | 行 | 被几处调用 | 谁在调 | 改了要回归什么 |
|---|---|---|---|---|
| `ensure_last_message_is_user` | 263 | 2 | `chat` / `chat_stream` | 两个 chat 端点的 400 语义 |
| `_conversation_not_found` | 286 | 2 | `_fetch_conversation_stats` / `require_conversation` | **5 个对话读写端点的 404 文案** |
| `_conversation_stats_stmt` | 298 | 2 | `_fetch_conversation_stats` / `list_conversations` | 详情 / PATCH / POST / 列表 **四处统计口径** |
| `_row_to_stats` | 320 | 2 | 同上 | 同上（**加字段只改这一处**） |
| `_fetch_conversation_stats` | 337 | 3 | `create_conversation` / `get_conversation` / `update_conversation` | 这三个端点的响应形状 |
| `require_conversation` | 346 | 4 | `chat` / `chat_stream` / `update_conversation` / `delete_conversation` | 存在性校验，**含两条流的 pre-flight** |
| `_as_dict` | 363 | 1（2 次） | `event_source` 里的 `usage` / `delta` | 上游字段类型守卫 |
| `_as_int` | 377 | 1（3 次） | `record_usage` 的三个 token 字段 | 账单金额 |

⭐ 判据：**「改 `_conversation_stats_stmt` 要回归 4 个端点，改 `require_conversation` 要回归 4 条路由」**
—— 这是 `app.py` 里仅有的"扇出"结构，`services/` 层就是为了拆它（#63）。

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
   │     ① 上游并发闸门：app.state.upstream_semaphore                 │
   │        （2026-11-16 13b-2b-2 起，启动【不再碰数据库】——           │
   │         DDL 全归 `alembic upgrade head`，见 decisions 32 / #50）  │
   │     ② async with create_llm_client() as client:                 │
   │           app.state.llm_client = client                          │
   │           yield  ←──────── 服务运行期间停在这里 ──────────────┐   │
   │                                                              │   │
   ├─ 处理 N 个 http 请求（每个都可能用到 ①② 的产物）                │   │
   │                                                              │   │
   ├─ lifespan.shutdown ←─────────────────────────────────────────┘   │
   │     ③ 退出 async with → client.aclose()                          │
   │     ④ await engine.dispose()  释放连接池                          │
   │        （uvicorn 收到 SIGTERM 后先停 accept、等在途请求最多                │
   │          graceful_shutdown_timeout 秒，再取消并走到这里 —— 决策 39）      │
   └──────────────────────────────────────────────────────────────────┘
```

### 3.3 少了 `lifespan` 会怎样（📎 按接口分类）

| 端点 | 需要 lifespan 的什么 | 不开通道时 |
|---|---|---|
| `/health`、`/v1/models` | 什么都不要 | 200 |
| `/health/ready` | 只要一条**能用的连接**（引擎懒建立，与 lifespan 无关） | **200** |
| `POST /v1/conversations` 等用表的 | **表结构**（📎 2026-11-16 起来自 `alembic upgrade head`，**不再来自 lifespan**） | 200 需要迁移已跑；没跑 → ❌ `no such table`（📎 实测，见 #84） |
| `/v1/upstream/models`、`/v1/chat/stream` | **`app.state.llm_client`** | ❌ `AttributeError: 'State' object has no attribute 'llm_client'` |

> ⭐ 一句话：**lifespan 的产物只有「`app.state` 上的两个共享对象」，不是「表结构」、也不是「连接」。**
> 📎 2026-11-16（13b-2b-2）起，`create_all` 已移出启动路径：DB 不可用时进程**照常起来**，
> `/health` 200、`/health/ready` 503，由编排系统摘流量而不是 crash loop。

---

## 4. 数据模型：ER + DDL

### 4.1 ER 图

```text
┌───────────────────────────────┐              ┌──────────────────────────────────┐
│ conversations                 │              │ llm_calls                        │
├───────────────────────────────┤              ├──────────────────────────────────┤
│ id            INTEGER  PK     │ 1          * │ id                 INTEGER  PK   │
│ owner_id      INTEGER  NN FK  │◄─────────────│ conversation_id    INTEGER  NULL │
│ title         VARCHAR(100) NN │  ondelete=   │ model              VARCHAR(100)  │
│ created_at    DATETIME   NN   │   SET NULL   │ prompt_tokens      INTEGER  NN   │
│ updated_at    DATETIME   NN   │              │ completion_tokens  INTEGER  NN   │
└───────────────────────────────┘              │ total_tokens       INTEGER  NN   │
        │                                      │ status             VARCHAR(20)   │
        │ owner_id → users.id                  │ created_at         DATETIME  NN  │
        │ （NO ACTION：删人有对话会被拒）        └──────────────────────────────────┘
        │                                               ▲
        │                                               │ index=True
        │                                 ix_llm_calls_conversation_id
        │
        │  1                    *
        └──────────────►┌──────────────────────────────────────────┐
                        │ users                                    │
                        ├──────────────────────────────────────────┤
                        │ id          INTEGER     PK               │
                        │ name        VARCHAR(50) NN  UNIQUE       │
                        │ created_at  DATETIME    NN               │
                        └──────────────────────────────────────────┘
                                        ▲ 1
                                        │ ondelete=CASCADE（凭据是附属品）
                                        │ *
                        ┌──────────────────────────────────────────┐
                        │ api_keys                                 │
                        ├──────────────────────────────────────────┤
                        │ id          INTEGER     PK               │
                        │ user_id     INTEGER     NN (index)       │
                        │ key_hash    VARCHAR(64) NN  UNIQUE       │
                        │ label       VARCHAR(50) NN               │
                        │ created_at  DATETIME    NN               │
                        │ revoked_at  DATETIME    NULL             │
                        └──────────────────────────────────────────┘

   relationship: Conversation.calls / LlmCall.conversation
                 User.api_keys    / ApiKey.user
                 Conversation.owner（单向，User 那边不需要）
```

### 4.2 📎 真实 DDL（SQLite 建出来的）

```sql
-- ⚠️ 这张表是 batch 模式（建新表 → 拷数据 → 改名）重建出来的，
--    所以 sqlite_master 里的语句带双引号表名、owner_id 在末尾、外键带 CONSTRAINT 名。
--    语义与 models.py 一致（守卫按【结构】比对，不按文本，见 tests/test_migrations.py）
CREATE TABLE "conversations" (
    id          INTEGER      NOT NULL,
    title       VARCHAR(100) NOT NULL,
    created_at  DATETIME     NOT NULL,
    updated_at  DATETIME     NOT NULL,
    owner_id    INTEGER      NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_conversations_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_conversations_owner_id ON conversations (owner_id);

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

CREATE TABLE users (
    id          INTEGER     NOT NULL,
    name        VARCHAR(50) NOT NULL,
    created_at  DATETIME    NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (name)
);

CREATE TABLE api_keys (
    id          INTEGER     NOT NULL,
    user_id     INTEGER     NOT NULL,
    key_hash    VARCHAR(64) NOT NULL,
    label       VARCHAR(50) NOT NULL,
    created_at  DATETIME    NOT NULL,
    revoked_at  DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (key_hash)
);

CREATE INDEX ix_api_keys_user_id ON api_keys (user_id);
```

### 4.3 五个「不这么写就会错」的点

| 设定 | 不这样会怎样 |
|---|---|
| `ondelete="SET NULL"`（**不是 CASCADE**） | 📎 写 CASCADE 时删 1 个对话会连带删掉 900 token 的账 |
| `conversation_id` 可空（`int \| None`） | 📎 写成 `int` 就是 500（单次调用可以不属于任何对话） |
| `relationship` 上**故意不写** `cascade="all, delete-orphan"` | 写了 ORM 会先把外键置 NULL 再删，等于绕过数据库层的 `SET NULL` |
| `api_keys` 存 **sha256**（`key_hash`，UNIQUE）、**CASCADE 只给它** | 存明文 = 库/备份泄露即可直接调用；给 `conversations` 写 CASCADE = 删人连账单一起消失（资产不能随人蒸发） |
| `owner_id` **NOT NULL + 索引，且不写 CASCADE** | 可空 → 过滤条件到处变成 `or owner_id is null`，永远清不掉；漏索引 → 列表每页全表扫；写 CASCADE → 删人连对话带账单蒸发 |

> 📌 副作用要知道：被删对话的账单 `conversation_id = NULL`，**无法区分「从没属于过」和「父行被删」**。

---

## 5. 端点总表

📎 由 `app.routes` 实读。共 **17 条**：13 条业务 + 4 条文档。

| 方法 | 路径 | 请求体 / 参数 | 响应模型 | 成功码 | 主要错误 | 鉴权 |
|---|---|---|---|---|---|---|
| GET | `/health` | — | `{"status": "ok"}` | 200 | — | **公开** |
| GET | `/health/ready` | — | `{"status": "ready"}` | 200 | 503 `DB_UNAVAILABLE` | **公开** |
| GET | `/v1/models` | `?prefix=&limit=`(1..100, 默认 20) | `{"total", "items": [str]}` | 200 | 422 | **公开** |
| GET | `/v1/models/latest` | — | `{"model_name"}` | 200 | — | **公开** |
| GET | `/v1/models/{model_name}` | 路径参数 | `{"model_name"}` | 200 | 404 `MODEL_NOT_FOUND` | **公开** |
| POST | `/v1/chat` | `ChatRequest` | `ChatResponse` | 200 | 401 / 400 / 404 / 422 | key |
| GET | `/v1/upstream/models` | — | `ModelListResponse` | 200 | 401 / 502 `UPSTREAM_*` | key |
| POST | `/v1/conversations` | `ConversationIn` | `ConversationStatsOut` | **201** | 401 / 422 | key |
| GET | `/v1/conversations/{conv_id}` | 路径参数 | `ConversationStatsOut` | 200 | 401 / 404 / 422 | key |
| PATCH | `/v1/conversations/{conv_id}` | `ConversationPatch` | `ConversationStatsOut` | 200 | 401 / 404 / 422 | key |
| DELETE | `/v1/conversations/{conv_id}` | 路径参数 | **无 body** | **204** | 401 / 404 / 422 | key |
| GET | `/v1/conversations` | `?limit=`(1..100, 默认 20) `&after_id=`(≥0) | `ConversationPageOut` | 200 | 401 / 422 | key |
| POST | `/v1/chat/stream` | `ChatRequest` | **SSE**（`text/event-stream`） | 200 | 401 / **502（pre-flight）** / 400 / 404 / 422 | key |
| GET | `/docs` `/redoc` `/openapi.json` `/docs/oauth2-redirect` | — | — | 200 | **prod 下全 404** | **公开** |

> **鉴权**：请求头 `X-API-Key: sk_…`（13d-2）。库里只存 `sha256`，明文只在签发时给一次。
> 401 形状 `{"error": {"code": "UNAUTHORIZED", …}}` + 响应头 `WWW-Authenticate: ApiKey`。
> **越权与不存在共用 404**（403 会泄露"这个 id 存在"）。守卫：`tests/test_source_rules.py` 断言"除白名单外每个路由都必须声明 `CurrentUserDep`"。
> **限流**（13d-4）：`require_user` 里顺带扣一次令牌（按 `user.id`，默认 60 次/分 + 突发 20）→ 超限 **429 `RATE_LIMITED` + `Retry-After`**。⚠️ **挂在鉴权里是刻意的**：没有身份就没法按人计配额，而且这样「新增路由忘挂限流」这件事不存在。

### 5.1 两个容易混的点

| 点 | 说明 |
|---|---|
| `/v1/models` vs `/v1/upstream/models` | 前者读**硬编码常量** `KNOWN_MODELS = ["deepseek-flash", "deepseek-v4-pro"]`；后者**真调上游**。形状也不同（`items: [str]` vs `items: [ModelItem]`）—— 待办 #39 |
| `/v1/chat` vs `/v1/chat/stream` | **两条都真调上游**（决策 53）—— 前者一次拿全（非流式），后者 SSE 逐帧；两者共用 `ChatRequest`、同一条 pre-flight 顺序、同一个并发闸门 |

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

### 6.3 非流式对话（真调上游，决策 53）

```json
POST /v1/chat  → 200  {"content": "你好！有什么可以帮你？", "model": "deepseek-flash", "usage_tokens": 38}
```

`ChatRequest` 的字段（📎 从 `model_fields` 导出）：

| 字段 | 类型 | 必填 |
|---|---|---|
| `messages` | `list[Message]` | ✅ |
| `model` | `str \| None` | 可选（None → 回落 `settings.llm_model`） |
| `temperature` | `float` | 可选（默认 0.7） |
| `max_tokens` | `int \| None` | 可选（None → **用 `max_tokens_ceiling` 兜底**；⚠️ `/v1/chat/stream` 是「不放进 body」，两处差异是**有意的**：省略等于让客户端绕过成本上限） |
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

| `code` | HTTP | 客户端该做什么 |
|---|---|---|
| `LAST_MESSAGE_NOT_USER` | 400 | 改请求 |
| `MODEL_NOT_FOUND` / `CONVERSATION_NOT_FOUND` | 404 | 改请求 |
| `UPSTREAM_UNREACHABLE` | 502 | 稍后重试（可能有用） |
| **`UPSTREAM_RATE_LIMITED`** | **429** + `Retry-After` | **按秒数退避重试** |
| **`UPSTREAM_PAYLOAD_TOO_LARGE`** | **413** | **缩短消息后重试** |
| **`UPSTREAM_AUTH_FAILED`** | 502 | 报错给运维（我们的密钥坏了） |
| **`UPSTREAM_REJECTED`** | 502 | 报错给运维（我们发的 body 上游不收） |
| `UPSTREAM_BAD_STATUS` | 502 | 稍后重试（5xx）/ 不要重试（3xx 接口搬家） |
| `UPSTREAM_MALFORMED` | 502 | 报错给运维（上游改了结构） |
| `DB_UNAVAILABLE` | 503 | 稍后重试 |
| （未登记的码） | **400**（兜底防"漏登记"，不是"猜对"） | —— |

#### 7.4b 上游状态码 → 我们的业务码（📎 2026-11-04 实测）

| 上游返回 | 我们的 code | 我们的 HTTP | 为什么 |
|---|---|---|---|
| 429 | `UPSTREAM_RATE_LIMITED` | **429** + 透传 `Retry-After` | 客户端**等一等**就能好 |
| 413 | `UPSTREAM_PAYLOAD_TOO_LARGE` | **413** | 客户端**缩短**就能好 |
| 400 / 422（body 含 `context_length_exceeded` 或 `maximum context length`） | `UPSTREAM_PAYLOAD_TOO_LARGE` | **413** | 上游用 400 表达，但语义是「你太大了」 |
| 400 / 404 / 其它 4xx | `UPSTREAM_REJECTED` | 502 | body 是**我们**造的，客户端改请求没用 |
| 401 / 403 | `UPSTREAM_AUTH_FAILED` | 502 | **我们的密钥**坏了，客户端无从修复 |
| 5xx | `UPSTREAM_BAD_STATUS` | 502 | 上游故障，重试可能有用 |
| 3xx | `UPSTREAM_BAD_STATUS` | 502 | 接口搬家了，重试没用 |

⭐⭐ 判据：**「客户端能不能靠自己修好？」能 → 透传那个 4xx；不能 → 502 + 细分 code。**
📌 认不出的 400（没有超长标记）**退回 `UPSTREAM_REJECTED`（502）** —— 不会比「一律 502」更糟。

📌 **为什么「我们自己的错」给 502 而不是 500**（学习者 2026-11-04 提出）：
语义上 500 也讲得通（确实是我们拼错了 body），选 502 只为**保住 500 的独占含义** ——
现在 500 只有一种来源：我们自己代码抛了未处理异常（[errors.py](../src/app/errors.py) 的兜底 handler）。
混进去之后，「我们的 bug」和「依赖方不给面子」在告警上就分不开了，而 #66（无指标）还没做。
另：Step 13 会在前面挂反向代理，`nginx` 自己用 **502/504** 表示上游异常，沿用同一个桶只需一条阈值。
改起来是一行（`_STATUS_BY_CODE` 的一个字典项），已列进决策 29 的重审条件。

📌 **401 与 403 被合并成同一个业务码**（`UPSTREAM_AUTH_FAILED`）：
两者语义不同（401 = 凭据不对 / 403 = 凭据不够，📎 RFC 9110 §15.5.2 / §15.5.4），
但对我们来说**都只有运维能修**，拆开也不会有人据此做不同动作。要区分就看日志里上游的 body。

### 7.5 `details` 是被**过滤过**的（这条最容易被忽略）

📎 pydantic 原始 `exc.errors()[0]` 有 **6 个字段**：

```json
{"type":"too_short", "loc":["messages"], "msg":"…",
 "input": [],                                   ← 🔴 用户提交的原值，必须丢
 "ctx":{"field_type":"List","min_length":1,"actual_length":0},
 "url":"https://errors.pydantic.dev/2.13/v/too_short"}
```

我们只留 `loc` / `msg` / `type`。📎 且原始 `loc` 是 `["messages"]`，我们的是 `["body","messages"]`。

### 7.5b 🔑 「DB 不可用」的判定点只有一个：`get_db` 里探连接那一步

```text
get_db
  ├─ await session.connection()   ← 【连不上】在这里抛 OperationalError → 503 DB_UNAVAILABLE
  └─ yield session
        └─ 路由执行 SQL            ← 【SQL/表结构错】(no such table) 在这里抛 → 500 INTERNAL_ERROR
```

📎 两类故障**抛出的异常类型完全相同**（都是 `sqlalchemy.exc.OperationalError`），所以只能按**抛出阶段**分辨。
统一在异常处理器里映射 503 会把「迁移没跑」（#84）伪装成「依赖挂了」。[决策 36](decisions.md)。

| 现象 | 判定点 | 结果 | 证据 |
|---|---|---|---|
| 库目录/实例不存在 | `connection()` | **503** + `Retry-After: 1` | 📎 真 uvicorn 实测 |
| 连得上但没跑迁移 | `execute()` | **500** | 📎 `test_sql_level_failure_stays_500` |
| 连得上但很慢（锁等待） | `execute()` | **500**（→ 13c-3 的总时长上限处理） | 未实测 |

### 7.6 500 的 CORS 头：只能由处理器自己补（✅ 2026-11-17 已修，#57）

📎 **根因（读源码 + 打印构建出来的栈，2026-11-17）**：`@app.exception_handler(Exception)` 被 FastAPI **挂到最外层的 `ServerErrorMiddleware` 上**，而它**永远在 `CORSMiddleware` 之外**；且它发完响应后还会 `raise exc`（给服务器日志）。所以「把 CORS 挪到更外层」这条路**不存在**。

```text
ServerErrorMiddleware          ← 这里跑 500 处理器（📎 打印到 handler=<function h500>）
  └ ExceptionTelemetryMiddleware
      └ CORSMiddleware         ← 500 的响应在它【里面】就已经发出去了
          └ ExceptionMiddleware  ← 只登记 HTTPException / WebSocketException / 422
              └ 路由
```

**修法**：`errors._cors_headers(request)` 按**同一份** `constants.ALLOWED_ORIGINS` 补 3 个头（`Access-Control-Allow-Origin` 回显源 / `-Allow-Credentials` / `Vary: Origin`），只用在 500 上（404/422 已经过 `CORSMiddleware`，再补会出现重复头）。

| 响应 | `Access-Control-Allow-Origin` | |
|---|---|---|
| 404 / 422 / 2xx（经 `CORSMiddleware`） | ✅ 回显源 + `vary: Origin` | |
| **500** | ✅ **与 404 完全一致** | 📎 `test_500_carries_the_same_cors_headers_as_other_errors` 断言两者头的 **集合相等** |
| 500 + 白名单外的源 | ❌ 无头（**绝不回落 `*`**） | 📎 `test_500_does_not_echo_a_foreign_origin` |

⚠️ 代价：CORS 策略现在有**两个出口**（中间件配置 + 处理器补头），共享的是白名单常量而非逻辑本身 → [决策 35](decisions.md)。

### 7.7 错误码有**两个出口**：HTTP envelope 和流内帧

📎 实测 `app.exception_handlers` 共 **5 个键**（其中 1 个是框架默认，本项目用不到）：

| 异常类 | 处理器 | HTTP | 出口 |
|---|---|---|---|
| `AppError` | `_app_error_handler` | `_STATUS_BY_CODE` 查表，**未登记 → 400** | envelope |
| `StarletteHTTPException` | `_http_exception_handler` | 原状态码（404 / 405） | envelope，码由 `_CODE_BY_STATUS` 兜底 |
| `RequestValidationError` | `_validation_error_handler` | 422 | envelope + `details` |
| `WebSocketRequestValidationError` | 框架默认 | — | 本项目没有 WS 路由 |
| `Exception` | `_unhandled_error_handler` | 500 | envelope（**无 CORS 头**，见 §7.6） |

#### 7.7.1 每个码的产生点（改码名只该改这一处）

| `code` | 谁产生 | 位置 | 出口 |
|---|---|---|---|
| `LAST_MESSAGE_NOT_USER` | `ensure_last_message_is_user` | [app.py](../src/app/api/app.py) | 400 envelope |
| `MODEL_NOT_FOUND` | `get_model` | [app.py](../src/app/api/app.py) | 404 envelope |
| `CONVERSATION_NOT_FOUND` | `_conversation_not_found`（**5 个端点共用这一处**） | [app.py](../src/app/api/app.py) | 404 envelope |
| `DB_UNAVAILABLE` | `health_ready` | [app.py](../src/app/api/app.py) | 503 envelope |
| `UPSTREAM_UNREACHABLE`（L1） | `LlmClient._request` | [llm_client.py](../src/app/llm_client.py) | 502 envelope |
| `UPSTREAM_BAD_STATUS`（L2） | `LlmClient._request` | [llm_client.py](../src/app/llm_client.py) | 502 envelope |
| `UPSTREAM_MALFORMED`（L3） | `LlmClient.list_models` | [llm_client.py](../src/app/llm_client.py) | 502 envelope |
| `STREAM_NO_CONTENT` | 零内容保护段 | [app.py](../src/app/api/app.py) | ⚠️ **200 的流里的一帧**，不是状态码 |
| `STREAM_FAILED` | `except Exception` 分支 | [app.py](../src/app/api/app.py) | ⚠️ 同上 |
| `NOT_FOUND` / `METHOD_NOT_ALLOWED` | 路由未命中 / 方法不对（框架抛） | `errors.py` 的 `_CODE_BY_STATUS` | envelope |
| `VALIDATION_ERROR` | pydantic 校验失败 | `errors.py` | 422 envelope |
| `INTERNAL_ERROR` | 任何未捕获异常 | `errors.py` | 500 envelope |

⭐⭐ 判据：**`_STATUS_BY_CODE` 里查不到的码，就不是 HTTP 错误码。**
`STREAM_*` 不在表里 —— 它们只存在于一条**已经是 200** 的流里；
谁想给它们"配一个状态码"，说明他还没读 §8.5。

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

### 8.2 八种帧（📎 全部来自源码里的 `yield`）

| # | 帧体 | 什么时候发 | 前端怎么用 |
|---|---|---|---|
| 1 | `{"status": "thinking"}` | **首帧**，一进生成器就发 | 立刻显示"思考中" |
| 2 | `{"delta": "<文字>"}` | 每个有内容的上游帧 | 追加到回答 |
| 3 | `{"finish_reason": "stop"\|"length"}` | 上游末帧（**只在是字符串时**） | 判断"说完了 / 被截断" |
| 4 | `{"usage": {…}}` | 上游给 usage 时（可能在纯用量帧，也可能和 finish 挤一帧） | 显示 token 用量 |
| 5 | `{"error": {"code": "STREAM_NO_CONTENT", …}}` | 上游 200 但**一帧内容都没有** | 明确告知"这次空" |
| 6 | `{"error": {"code": "STREAM_FAILED", …}}` | 流**已开始后**出异常 | 提示中断 |
| 6b | `{"error": {"code": "STREAM_TIMEOUT", …}}` | 超出 `upstream_total_timeout`（📎 2026-11-17 / 决策 37） | 提示「上游太慢」，建议缩短问题重试 |
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

### 8.4b 坏帧怎么处置：**四类，两种处置**（📎 2026-11-02 实测）

| # | 上游给了什么 | 处置 | 客户端看到 | 服务端日志 |
|---|---|---|---|---|
| 1 | **结构错**：`content` 是数组 / `choices` 不是 list / `choices[0]` 不是 dict / `delta` 不是 dict / `index != 0` | **跳过该帧，继续** | 少那一段（如「大家好」→「大好」） | `WARNING` |
| 2 | **字段类型错（非内容类）**：`finish_reason` 不是字符串 | **只丢这个字段** | 内容**完整**，只是没有「说完/截断」信息 | `WARNING` |
| 3 | **JSON 语法错**（`data: {坏}`） | **中止整条流** | 已拿到的内容 + `STREAM_FAILED` + `[DONE]` | `ERROR` |
| 4 | **运行时异常**（连接断 / flush 失败等） | **中止整条流** | 已拿到的内容 + `STREAM_FAILED` + `[DONE]` | `ERROR` |

📎 四组实测（假上游 / 直接喂字节）：

| 实验 | 帧序列 |
|---|---|
| `content: ["家"]` 夹在中间 | `thinking` → `delta 大` → `delta 好` → `[DONE]`（**「家」没了**） |
| `finish_reason: {"x": 1}` 夹在中间 | `thinking` → `delta 大` → `delta 家` → `delta 好` → `[DONE]`（**内容完整**） |
| 中间一帧是坏 JSON | 适配器**抛出** `JSONDecodeError`；抛出**之前**已吐出 1 个 chunk（`大`） |
| 流开始后抛异常 | `thinking` → `delta 大` → `error STREAM_FAILED` → `[DONE]` |

⭐ 判据：**「结构错」跳过（这一帧用不了，但流的解释框架还在）；「语法错 / 运行时异常」中止（连这是什么都不知道了）。**

### 8.5 pre-flight：状态码还没发出去的最后机会

```text
await client.open_chat_stream(body)     ← 只等响应头
   ├─ 抛 AppError（连不上 / 状态码不对） → 502（此时响应头还没发，改得了）
   └─ 成功 → return StreamingResponse(...)   ← 从这一刻起状态码定死为 200
```

🔴 如果把这一行挪进生成器：上游失败会变成 **200 + 流里一个 error 帧** —— 日志 200、用户看到空回答。
📎 测试 `test_stream_preflight_failure_changes_status_code` 专门钉这一条。

---

### 8.6 完整时序：一次流式请求的每个时刻（含账单状态机）

> 前面 8.1~8.5 讲的是「帧长什么样」。这一节讲**时间**：一条流从进门到收尾，每个时刻发生了什么、
> 那一刻出错会怎样、账单那一行停在哪个状态。

#### 8.6.1 三条生命线 × 十二个时刻

```text
时间
 ↓      客户端            uvicorn + 七层中间件          chat_stream（路由 + 生成器）        上游 LLM
        ┌──────┐          ┌──────────────────┐          ┌──────────────────────────┐       ┌────────┐
        │      │          │  add_request_id  │          │                          │       │        │
        │      │          │  CORS            │          │                          │       │        │
        └──┬───┘          └────────┬─────────┘          └────────────┬─────────────┘       └───┬────┘
  ①       │  POST /v1/chat/stream  │                                 │                         │
          ├───────────────────────▶│                                 │                         │
  ②       │                       ├────────────────────────────────▶│ pydantic 校验 形状          │
          │                       │                                 │ 最后一条必须是 user         │
  ③       │                       │                                 ├─── require_conversation ──▶ 数据库 SELECT
  ④       │                       │                                 ├────────────────────────▶│ open_chat_stream
          │                       │                                 │◀────────────────────────┤ 只等响应头
  ════════╪═══════════════════════╪═════════════════════════════════╪══ 200 + chunked ════════╪══ 状态码锁死
  ⑤       │◀══════════════════════════════════════════════════════════│ return SseResponse       │
  ⑥       │                       │                                 ├─── db.commit() ────────▶ 数据库 INSERT + 提交
          │                       │                                 │   ✅ 写锁在这里就释放      │
  ⑦       │◀──── data: thinking ──┼─────────────────────────────────┤ yield                    │
  ⑧       │◀──── data: delta ─────┼─────────────────────────────────┤ async for chunk ────────▶│ 逐帧
          │                       │                                 │ 每帧：usage → finish → content
  ⑨       │◀──── error 帧 ────────┼─────────────────────────────────┤ 仅零内容时               │
  ⑩       │◀──── data: [DONE] ────┼─────────────────────────────────┤ yield                    │
  ⑪       │                       │◀────────────────────────────────┤ 生成器结束                │
          │                       │  get_db commit ────────────────▶ 数据库 最终状态 UPDATE    │
          │                       │                                 │   （aborted / no_content）│
  ⑫       │◀════ 连接关闭（或客户端早已断开 → GeneratorExit）═════════│                          │
```

⭐ **⑤ 是整条流最重要的分界线**：

| ⑤ 之前（①~④） | ⑤ 之后（⑥~⑫） |
|---|---|
| 状态码**还能改** | 状态码**锁死 200** |
| 出错 → `errors.py` 的统一 envelope（4xx / 502） | 出错 → **只能**发流内 `error` 帧，或干脆发不出去 |
| 账单**没有行** | 账单**已经有行**（或本行被回滚） |

#### 8.6.2 每个时刻能出什么问题

| 时刻 | 出什么事 | 客户端看到 | `llm_calls.status` | 能改状态码吗 | 待办 |
|---|---|---|---|---|---|
| ② | 形状非法（缺 `messages`、`temperature` 越界） | **422** + `details` | **没有行**（生成器没跑） | ✅ | — |
| ② | 最后一条不是 `user` | **400** `LAST_MESSAGE_NOT_USER` | **没有行** | ✅ | — |
| ③ | `conversation_id` 不存在 | **404** `CONVERSATION_NOT_FOUND` | **没有行** | ✅ | — |
| ④ | 上游连不上 / 超时 | **502** `UPSTREAM_UNREACHABLE` | **没有行** | ✅ | #60 |
| ④ | 上游回 4xx / 5xx | **502** `UPSTREAM_BAD_STATUS` | **没有行** | ✅ | #60 |
| ⑤ 之后 · ⑥ | `INSERT` 失败（`database is locked`） | **200 + 空 body**（0 帧） | **没有行**（事务回滚） | ❌ | #73 已修 |
| ⑥~⑧ | 客户端提前断开（📎 读到 0 / 1 / 3 段就退出，三种都实测过） | 连接断，后续帧收不到 | **`aborted`**（同步赋值） | ❌ | — |
| ⑧ | 坏 JSON（协议不可信） | 已拿到的内容 + `STREAM_FAILED` + `[DONE]` | 未拿到 usage → **`aborted`** | ❌ | — |
| ⑧ | 结构坏帧（`content` 是数组等） | **少了那一段字**，流里无任何提示 | 拿过 usage → `completed`；否则看 ⑨ | ❌ | **#69** |
| ⑧ | 坏帧与 `usage` 同帧 | — | 现在会先记账 → **`completed`** | ❌ | #70 已修 |
| ⑧ | `finish_reason` 不是字符串 | 内容完整，缺「说完/截断」 | 不受影响 | ❌ | — |
| ⑨ | 上游 200 但一帧内容都没有，且没 usage | `STREAM_NO_CONTENT` + `[DONE]` | **`no_content`** | ❌ | #68 已修 |
| ⑨ | 零内容但**拿到了** usage | `STREAM_NO_CONTENT` + `[DONE]` | **`completed`**（钱准了） | ❌ | 决策 27 |
| ⑩~⑪ | `get_db` 的 commit 失败 | **已经收完完整响应**，无从告知 | **丢失**（只在日志里） | ❌ | — |
| 任意 | 进程被强杀 | 连接断 | **`pending`**（⑥ 已 commit，📎 实测 exit code 9 后仍有一行） | ❌ | #42 已修 |

⭐ **⑥ 为什么必须是 `commit` 而不是 `flush`**（2026-11-03 修 #73）：`flush` 只把 SQL 发出去、**不结束事务** → 写锁会一直持有到 ⑪。SQLite 只允许一个写者，于是并发流被完全串行化。改成 `commit` 之后写锁在 ⑥ 就释放（📎 实测并发 6 条流的连接池峰值从 6 降到 2）。

📎 断开那三行是实测的：即使客户端**一段 body 都没读**就断开，账单也会落成 `aborted`（因为 Starlette 一旦开始发响应就会启动生成器，`aclose()` 时 `GeneratorExit` 会走进 `except BaseException`）。

⭐ 一个反直觉的点：**⑪ 的 commit 失败是最难发现的** —— 客户端拿到的是完整回答，账面却没有这一行。
所以「客户端说成功了」**不能**当作「账面记上了」的证据。

#### 8.6.3 账单状态机（时刻编号与上图对应）

```text
              ② 422 / 400      ③ 404      ④ 502     ⑥ flush 炸（#73）
                     └────────────┴───────────┴──────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │  没有账单行            │  生成器根本没跑 / 事务回滚
                        └───────────────────────┘
                                    │ ⑥ db.add + flush（INSERT）
                                    ▼
                        ┌───────────────────────┐
                        │       pending         │  ← 唯一一个「中间态」
                        └───┬───────┬───────┬───┘
                            │       │       │
        ⑧ 拿到 usage ───────┘       │       └─────── ⑨ 零内容 且 没拿到 usage
        （record_usage 置位）        │                 （if not recorded）
                            │       │                          │
                            ▼       │                          ▼
                ┌──────────────┐    │            ┌──────────────┐
                │  completed   │    │            │  no_content  │
                └──────────────┘    │            └──────────────┘
                                    │ ⑦~⑧ 客户端断开 / 流内异常 / 坏 JSON
                                    ▼
                        ┌──────────────┐
                        │   aborted    │
                        └──────────────┘
```

⭐⭐ **一张图说清优先级：`recorded` 是一个「锁存器」。**

```python
recorded = False                    # ⑥ 之后
# ⑧ 拿到 usage：
recorded = True; call.status = "completed"
# 之后无论发生什么，两个出口都写成 if not recorded: ...  → 都不会再改它
```

所以**一旦拿到 usage，状态就定格在 `completed`** —— 哪怕随后客户端断开、上游断流、JSON 坏掉。
理由：**usage 是上游对「这次调用确实发生并计费」的确认**。钱已经准了，后面的事改不了这个事实。

#### 8.6.4 出口 × 状态 全矩阵（穷举，不会再有意外）

| 出口 | 谁写的 | 值 | `recorded` 已为 `True` 时 |
|---|---|---|---|
| 正常读完 | `record_usage()` | `completed` | （本来就是） |
| 零内容 | 零内容保护段 | `no_content` | **不写**，保持 `completed` |
| `except Exception` | 异常分支 | `aborted` | **不写**，保持 `completed` |
| `except BaseException` | 取消分支（同步赋值） | `aborted` | **不写**，保持 `completed` |
| 没走到以上任何一处 | —— | `pending` | —— |

> ⚠️ 两条命门：① `aborted` / `no_content` **必须是同步赋值**，此时处在已被取消的 cancel scope 里，任何 `await` 都会被二次取消；
> ② 落盘交给**不会被取消**的 `get_db`，生成器只负责「登记」。

#### 8.6.5 三个「两个问题叠加」的组合（这才是真实故障的样子）

| 组合 | 现场 | 为什么难查 |
|---|---|---|
| ⑧ 坏帧 + ⑨ 零内容 | 上游全帧都结构坏 → 内容帧 0 → `no_content` | 看起来像「上游没给内容」，其实是「我们全扔了」 |
| ⑥ 写锁 + ⑧ 并发（**#73**） | 并发 4 条流 → 后 3 条 TTFB 1.33s / 1.98s；并发 6 条 + 单流 2s → **3 条拿到 200 + 0 帧** | 每条单独跑都正常；`TestClient` 也全绿（无背压） |
| ⑧ 跳过 + 无提示（**#69**） | 客户端看到「大好」，以为是模型说错 | 「模型答得不对」和「我们丢了它的话」在客户端一模一样 |

📎 相关实测见 [stage1-fastapi.md](../notes/stage1-fastapi.md) §12.5c（帧序）、§12.5d（坏帧处置）、
§12.5f（账单四态）、§12.7b（并发串行化）。

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
| `request_timeout` | float | `30.0` | httpx 默认只有 5 秒，LLM 不够；⚠️ 只是**读取间隔**，不是总时长 |
| `graceful_shutdown_timeout` | **int** | `30`（`gt=0, le=300`） | **优雅停机窗口**：收到 SIGINT/SIGTERM 后最多再等多久（决策 39）；⚠️ 必须小于编排宽限期；⚠️ 只在 `python -m app` 生效 |
| `upstream_total_timeout` | float | `120.0`（`gt=0, le=600`） | **单次上游调用的总时长预算** —— 慢速滴答的唯一防线（决策 37）；超时非流式 504 / 流式 `STREAM_TIMEOUT` 帧 |
| `max_concurrent_upstream_calls` | int | `4` | `ge=1, le=100`。**进程级**闸门，`--workers N` 就是 N 倍 |
| `upstream_queue_timeout` | float | `1.0` | `gt=0, le=30`。抢不到槽位最多等这么久，超时 503 + `Retry-After` |
| `max_tokens_ceiling` | int | `4096` | `ge=1, le=32768`。客户端要更多 → **400 拒绝**；没指定 → 用它当默认值。📎 上界是**成本预算**（$0.039/请求），不是模型上限（393216） |

### 9.4 启动即崩的保护

```text
APP_ENV=prod + DEBUG=true
   └─ @model_validator(mode="after") 抛 ValueError
        └─ settings = Settings() 在模块体里 → import 就崩 → 进程 exit_code=1
```

📎 为什么必须崩、不能静默改 False：`debug=True` 会让 `@app.exception_handler(Exception)` 不执行，**traceback 直接进响应体**。

**「值合法但配错了」不归这一节管 —— 归启动摘要**（2026-11-16，[#77](../docs/todos.md) / [决策 34](../docs/decisions.md)）：

```text
lifespan 启动段[1]
   └─ logger.info("生效配置：%s", startup_config_summary(settings))
        └─ 白名单 7 项：app_env / debug / database / max_concurrent_upstream_calls
                        / upstream_queue_timeout / max_tokens_ceiling / request_timeout / upstream_total_timeout
                        / graceful_shutdown_timeout
        └─ 📎 database 只打「方言://…/库名」—— 不出现 用户名:密码@主机
```

📎 真进程第一屏样本（`MAX_CONCURRENT_UPSTREAM_CALLS=7`；13e-2 起是 JSON，下面是展开后的可读形式）：

```json
{"ts": "2026-11-19T12:34:20.077+00:00", "level": "INFO", "logger": "app.api.app",
 "msg": "生效配置：{'app_env': 'dev', 'debug': False, 'database': 'sqlite+aiosqlite://…/x.db',
        'max_concurrent_upstream_calls': 7, 'upstream_queue_timeout': 1.0,
        'max_tokens_ceiling': 4096, 'request_timeout': 30.0,
        'upstream_total_timeout': 120.0, 'graceful_shutdown_timeout': 30}"}
```

⚠️ 白名单的「漏项」目前没有机械兜底（见 [#85](../docs/todos.md)）：`Settings` 新增字段而忘了加进摘要，测试不会红。

### 9.5 配置项 → 读取点（改一个字段，谁的行为会变）

📎 从源码里 `settings.<字段>` / `config.<字段>` 实读（2026-11-04）：

| 字段 | 谁读 | 怎么读 | 生效时机 |
|---|---|---|---|
| `app_env` | [api/app.py](../src/app/api/app.py)（`_DOCS_ENABLED`） | 模块级直读 | **import 时**（决定 `/docs` 开不开） |
| `debug` | [api/app.py](../src/app/api/app.py)（`FastAPI(debug=…)`）、[__main__.py](../src/app/__main__.py)（`reload=`） | 直读 | import 时 / 启动时 |
| `host` / `port` / `graceful_shutdown_timeout` | [__main__.py](../src/app/__main__.py) | 直读 | **只走 `python -m app` 才生效**（`uvicorn app.api.app:app` 会绕过） |
| `database_url` | [database.py](../src/app/database.py) | 直读（建 engine） | import 时；**一个进程只能绑一个库** |
| `llm_base_url` / `request_timeout` / `upstream_total_timeout` / `llm_api_key` | [llm_client.py](../src/app/llm_client.py)（`create_llm_client`） | 直读 | lifespan 启动段造 client |
| `llm_model` | `chat` / `chat_stream` | ⭐ **经 `SettingsDep` 注入**（`config.llm_model`） | 每请求，且**可被 `dependency_overrides` 换掉** |
| `app_name` | 只有 [main.py](../src/app/main.py) 打印 | 直读 | ⚠️ 服务自己的 `FastAPI(title=…)` 是**硬编码**，不读这个字段 |
| `max_concurrent_upstream_calls` / `upstream_queue_timeout` | 🟡 [api/deps.py](../src/app/api/deps.py)（`get_upstream_slot`，**12g-2 才落地**） | 直读 | 每请求 |
| `max_tokens_ceiling` | 🟡 `chat` / `chat_stream` 路由层（**12g-3 才落地**） | 待定（倾向于经 `SettingsDep`，这样测试能换） | 每请求 |

⭐ 判据：**只有 `llm_model` 走依赖注入**，所以测试能换的也只有它；
其余全是模块级单例直读 → **改环境变量必须重启**（import 之后改 `os.environ` 无效，见 §9.1）。

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
④ root 的 handler（`StreamHandler(stream=sys.stdout)`）→ Formatter（`JsonFormatter`）拼成一行 JSON → 输出
```

> ⚠️ **是 stdout，不是 stderr**（📎 `logging_setup.py` 里 `"stream": "ext://sys.stdout"`）：
> 容器里 stdout 才是「应用事件流」的规范出口（12-Factor 第 11 条），由 Docker 收集并轮转。

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

### 10.3 输出格式：一行一个 JSON 对象（决策 48）

```json
{"ts": "2026-11-19T12:34:20.117+00:00", "level": "INFO", "logger": "app.api.app", "msg": "request", "method": "GET", "path": "/health", "status": 200, "duration_ms": 0.3, "client": "203.0.113.7", "request_id": "f4f5d692bbc6"}
```

| 字段 | 来源 | 为什么必须有 |
|---|---|---|
| `ts` | `datetime.fromtimestamp(record.created, UTC)` | 带 **UTC 偏移**，跨时区排查不用换算 |
| `level` / `logger` / `msg` | `LogRecord` | 最小可读三件套；`msg` 仍是人拼的字符串 |
| `client=` | `request.client.host`，**已被 uvicorn 按信任链改写**（决策 47） | 区分「一个客户端刷 1 万次」和「一万个客户端各一次」（#56） |
| `request_id=` | 请求头 `X-Request-ID` 或新生成 | 用户贴一个 id 就能定位整条链路 |
| `duration_ms` | `perf_counter` 差值 | 只有一个数字，但它是 p99 的原料（13f） |
| `exc` | `formatter.formatException(record.exc_info)` | **换行被 `json.dumps` 转义** → traceback 仍是一行，不会被采集器切碎 |

⚠️ `client` 是**外部输入**：`X-Forwarded-For` 里可能带换行 → 直接格式化能凭空造出一行假日志（CWE-117）。
所以它先过 `_client_label()`（去控制字符 + 截断 64 字符），📎 见 `tests/test_access_log.py`。

⚠️ **轮转不在 Python 里**：容器日志走 stdout，由 Docker 的 `logging` 选项截断（📎 实测默认 4000 行全留，`64k × 2` 只剩 504 行）。`compose` 里三个服务都是 `json-file` + `max-size: 10m` + `max-file: 3`。

| 设定 | 值 | 为什么 |
|---|---|---|
| `dictConfig(force=True)` | — | 幂等：重复调用不会叠 handler |
| `disable_existing_loggers` | **`False`** | 默认 `True` 会禁掉未在 `loggers` 里命名的已有 logger（📎 `app.errors` 会被禁 → 500 traceback 全哑） |
| `uvicorn.access` | `disabled` | 访问日志我们自己打（要带 `request_id` 和耗时） |

---

## 10b. 指标形状（13e-3 / 决策 50）

`GET /metrics`（Prometheus 文本格式，`include_in_schema=False`）：

```text
http_requests_total{method="GET",path="/v1/conversations",status="401"} 1.0
http_request_duration_seconds_bucket{path="/v1/conversations",le="0.01"} 0.0
app_errors_total{code="UNAUTHORIZED",status="401"} 1.0
llm_tokens_total{direction="prompt"} 46.0
db_pool_checked_out 0.0
```

| 指标 | 类型 | 标签 | 谁写它 |
|---|---|---|---|
| `http_requests_total` | Counter | `method` / **`path`（路由模板）** / `status` | `add_request_id` 中间件 |
| `http_request_duration_seconds` | Histogram | `path` | 同上，**只非流式** |
| `app_errors_total` | Counter | `code` / `status` | `_error_response()`（所有 HTTP 错误的单一出口） |
| `llm_tokens_total` | Counter | `direction`（prompt / completion） | `record_usage()` |
| `db_pool_checked_out` | Gauge | — | `/metrics` 路由**在生成输出前**采样 |

**三条硬规则**（每条都有实测依据）：
1. **`path` 用路由模板**，不是真实 URL —— 否则 `/v1/conversations/1`、`/2`… 各建一条时间序列
2. **探针与抓取端点不计量**（`/health`、`/health/ready`、`/metrics`）—— 📎 实测 3 次 `/health` 就压过 1 次真实请求，会把 5xx 比例的分母撑大
3. **流式不记总时长** —— 它由 `upstream_total_timeout`（120s）决定，混进来会让 p99 永久趴在 120s

⚠️ **谁能看**：`deploy/nginx.conf` 里 `location = /metrics { return 404; }` —— 宿主访问 404（📎 实测），
只有容器网络内的抓取方能连 `app:8000/metrics`（📎 实测 200）。**不用 `allow`/`deny` 的原因**：
📎 外部请求的源 IP 在不同堆栈里分别是 `172.18.0.1` 与 `172.30.0.128`，写哪个白名单都会错。

⚠️ **告警规则**在 `deploy/alerts.yml`（5xx > 1% / 429 > 10·min⁻¹ / 非流式 p99 > 8s），
📎 用 `promtool check rules` 验过（`SUCCESS: 3 rules found`；故意拼错函数 → `FAILED`）。
**但没有接收端** —— 没有 Alertmanager，规则不会自己发出来。

⚠️ **进程内计数**：多 worker / 多副本时每个进程各一份，抓到的只是「被路由到的那一个进程」的账。

---

## 11. 测试形状

### 11.1 目录形状：一层一个文件

```text
tests/
├── conftest.py   ① 环境地基（必须在 import app 之前就位）
│     ├─ 删旧测试库（.db / -wal / -shm）
│     ├─ os.environ["DATABASE_URL"] = %TEMP%/llm-app-test-<pid>.db   ← 一进程一个库（#87 / 坑 K94）
│     ├─ import app  ← 到这一行 settings 才定型
│     ├─ _truncate_all()   清表（子 → 父）
│     └─ client fixture    with TestClient(app) → 触发 lifespan → 清表 → yield
│
├── fakes.py      ② 假对象（不是测试文件）
│     ├─ FakeChatStream(LlmChatStream)   aiter_chunks / aclose / closed 标志
│     └─ FakeLlm(LlmClient)              list_models / open_chat_stream / last_body
│
└── test_*.py     ③ 按【测哪一层】分家
      ├─ 地基自检 ──────────── smoke（含「一进程一库」的真子进程用例）
      ├─ HTTP 契约 ─────────── conversations / errors
      ├─ 身份与配额 ────────── auth / rate_limit / keys_cli
      ├─ 路由层接线与守卫 ──── upstream / stream_frames / stream_accounting
      ├─ 适配器协议层 ──────── stream_adapter / adapter_http ← 允许 import httpx（构造/喂数据，不调上游）
      ├─ 并发与连接池 ──────── concurrency ← 真起 uvicorn + 真 TCP
      ├─ 访问日志与日志格式 ── access_log（真 uvicorn 验可信链）/ log_json（子进程验一行一 JSON）
      ├─ 迁移层 ────────────── migrations ← 起子进程跑 alembic CLI
      ├─ 源码约定 ──────────── source_rules ← 只读源码不跑应用（AST + 文本规则）
      ├─ 容器产物静态检查 ──── docker_assets ← 只读 Dockerfile / .dockerignore / compose / nginx.conf
      ├─ 启动接线 ──────────── startup_config（白名单 + 优雅窗口真的传给了 uvicorn）
      └─ 护栏上限 ──────────── limits（闸门 503 / 槽位归还 / max_tokens / 输入长度）
```

📌 **每个文件测什么 / 各有多少用例 / 要不要真服务** —— 唯一出处是
[tests/README.md](../tests/README.md) §1。本文件不抄一份（抄了就会有两处数字，改一处必漏另一处）。

### 11.2 依赖注入图（fixture 与 override）

```text
                    conftest.migrated  (session 作用域 · autouse)
                            │
                            ▼
                   alembic upgrade head   ← 建表（13b-2b-1 起；lifespan 不再建表）
                            │
                            ▼
                    conftest.client  (function 作用域)
                            │
                            ▼
                  with TestClient(app)      ← 触发 lifespan：造 llm_client / 并发闸门
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

### 11.4 两个必须记住的测试坑（一句话版，细节在 tests/README）

| 坑 | 一句话 | 细节 |
|---|---|---|
| `raise_server_exceptions` 默认 `True` | 要在断言里拿到 **500 的响应体**，必须 `TestClient(app, raise_server_exceptions=False)`；**但别改共享 fixture**，否则所有真 bug 都退化成"500 响应" | [tests/README.md](../tests/README.md) §5、`test_errors.py::test_500_hides_internals` |
| `TestClient` 没有 **TCP 背压** | 并发 / 池占用问题在 `TestClient` 下**复现不出来**（`checkedout` 峰值 0 vs 真 uvicorn 6） | [tests/README.md](../tests/README.md) §5 #1 |

---

## 12. 状态机

### 12.1 账单（`llm_calls.status`）四态

```text
                     开流前（yield 之前）
                            │
                            ▼
                     ┌─────────────┐
                     │   pending   │   db.add + commit（⚠️ 已持久化，写锁当场释放）
                     └──┬──────┬───┘
          拿到 usage ───┘      └──── 客户端断开 / 上游异常
                │                          │
                │                          ▼
                ▼                   ┌──────────────┐
        ┌──────────────┐            │   aborted    │
        │  completed   │            └──────────────┘
        └──────────────┘
        上游 200 但一帧内容都没有（且没拿到 usage）
                      │
                      ▼
              ┌──────────────┐
              │  no_content  │   金额不确定：上游可能已扣费
              └──────────────┘

        落盘时机：pending 在 ⑥ 就 commit；completed 由 record_usage 里的 commit 写入；
        aborted / no_content 只改内存属性，由 get_db 收尾那次 commit 写入
```

> ⚠️ `completed` 与 `no_content` 互斥：**拿到 usage 就一定是 `completed`**，
> 只有「零内容 **且** 没拿到 usage」才是 `no_content`（`if not recorded` 守卫）。
> 四个值定义在 `models.py` 的 `LlmCallStatus(StrEnum)`，值字面量由测试钉住。

| 状态 | 含义 | 谁写它 |
|---|---|---|
| `pending` | 流已经开始，还没结束 | 生成器一开始 |
| `completed` | 拿到完整 `usage`（金额可信） | `record_usage()`（**在三个结构守卫之前调用**，见 §8.4b / 待办 #70） |
| `aborted` | 客户端断开 / 上游报错 | `except` / `except BaseException` 分支（**同步赋值**，不能 `await`） |
| `no_content` | 上游 200 但一帧内容都没有，且没拿到 usage | 零内容保护段（`if not recorded`） |

> ⚠️ `aborted` 必须是**同步赋值**：被取消后继续 `await` 会抛 `RuntimeError`。
> ⭐ 想知道**每个状态是在哪一刻被写进去的**，看 [§8.6 完整时序](#86-完整时序一次流式请求的每个时刻含账单状态机)。
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

**谁负责提交**（2026-11-17，[决策 38](decisions.md)）：

| 写路径 | 提交位置 | 为什么 |
|---|---|---|
| `POST` / `PATCH` / `DELETE` 对话 | **路由内**，`return` 之前 | 状态码一旦发出就改不了：提交失败必须让客户端看到 **5xx**（📎 `test_conversations.py` 3 条回归钉住） |
| 流式账单（`pending → completed/aborted/no_content`） | 前段在路由内 commit；**末段靠 `get_db` 收尾 commit** | 收尾写在响应开始之后，且取消路径禁止 await（📎 删掉兜底 → 3 条账单用例红；失败时只降级为 `pending`） |

⚠️ 兜底 commit 有个副作用：**将来某个写路由忘了 commit 会被它悄悄救回来**（📎 探针实测：201 且行真的存了，漏写看不出来）→ 待办 [#86](../docs/todos.md)（AST 静态检查）。

---

## 13. 运行形态：一个进程、两个外部依赖

### 13.1 现在的形状

```text
┌────────────────────────────────────┐
│ 浏览器（前端，不在本仓库）          │  origin 必须是 5173 才带 CORS 头
└──────────────┬─────────────────────┘
               │ HTTP
               ▼
┌──────────────────────────────────────────────────────────────┐
│ uvicorn  ←【单进程】，没有 --workers                          │
│   └─ app.api.app:app                                         │
│        ├─ SQLite 文件 ./app.db                               │
│        │    （相对【当前工作目录】，不是相对代码目录）          │
│        └─ httpx.AsyncClient × 1（进程共享，lifespan 造/关）    │
│             └─ https://api.deepseek.com                      │
└──────────────────────────────────────────────────────────────┘
```

⭐ 这个「进程共享的一个 client」在测试里有两个可替换的接缝 —— 见 [§13.7](#137-上游客户端的两层接缝工厂层-vs-取用层2026-11-20决策-4--53)。

📎 2026-11-04 实测（`app.routes` / `engine.pool` / `httpx` 内部对象 / `PRAGMA`）：

| 事实 | 值 | 位置 |
|---|---|---|
| 进程数 | **1**（`uvicorn.run(...)` 没传 `workers`；`reload` 只在 `debug=True` 时开） | [__main__.py](../src/app/__main__.py) |
| 监听 | `settings.host:settings.port`（默认 `127.0.0.1:8000`） | 同上 |
| 路由条数 | dev **17** / prod **13**（4 条文档路由被 `docs_url=None` 关掉） | [app.py](../src/app/api/app.py) |
| 数据库池 | `AsyncAdaptedQueuePool`：`size=5` + `max_overflow=10` = **15**，等连接 `pool_timeout=30s` | [database.py](../src/app/database.py) |
| 上游 HTTP 池 | `max_connections=100`（httpx 默认 `Limits`） | [llm_client.py](../src/app/llm_client.py) |
| SQLite 忙等 | `busy_timeout = 5000ms` | SQLite/`sqlite3` 默认 |
| 部署产物 | **CI 已有**（`.github/workflows/ci.yml`，push/PR 跑五道门）；**镜像 + compose 栈已就绪**（13a-1 / 13a-2a / 13a-2b / 13a-2c，📎 真 `docker build` + 空库部署 + 经 nginx 验过）；**没有**灰度与回滚 | 待办 #49（灰度） |

⭐ 一句话：**第一道顶不住的是我们自己设的闸门（`max_concurrent_upstream_calls`，默认 4）**；
闸门之后才是「15 条数据库连接」和「SQLite 只能有一个写者」；上游 HTTP 池（100）永远排最后。
"多副本"仍然不存在 → 所有进程内计数都是单进程的账。逐层推导见 [§13.3](#133-五层上限谁在限谁2026-11-04)。

### 13.2 上线前这张图会变的三处

| 会变什么 | 为什么 | 待办 |
|---|---|---|
| ~~前面多一层反向代理~~ ✅ **已做（13a-2c，决策 46）** | CORS / 限流 / body 上限 / 给 500 补头 在那一层做更省事。现在：`浏览器 → nginx:80 → app:8000`，app 只 `expose` | #38 #57 #89（413 形状） |
| SQLite → PostgreSQL | 单写者会把并发退化成排队 | 决策 13 |
| 进程 → 多副本 | 单进程里的任何计数（`Semaphore` / 内存限流）都会变成 N 倍 | #44 |

> ⚠️ 这三处**改的是图，不是代码风格** ——
> 任何「现在单机能跑 / 能扛 N 个」的结论，换形态之后都要重测。

---

### 13.3 五层上限：谁在限谁（2026-11-04）

> 要回答 **「第 1001 个并发请求会发生什么？」**，不能只看一个数字，
> 而要看**哪一层先顶不住**。所以把所有层排成一队，从外到内看。

#### 13.3a 📎 五层，五个数字

| 层 | 数字 | 谁定的 | 我们能不能改 | 位置 |
|---|---|---|---|---|
| **L0 上游配额** | 未知（DeepSeek 账号的 RPM / TPM / 余额） | 供应商 | ❌ 只能被动挨 429 | 外部 |
| **L1 我们的闸门** | **4** 条流 / 进程 | 我们自己 | ✅ 改 `.env` | `settings.max_concurrent_upstream_calls` |
| **L2 上游 HTTP 连接池** | **100**（keepalive 20） | httpx 默认 | ✅ 但没必要 | `create_llm_client()` |
| **L3 数据库连接池** | **15**（`size=5` + `max_overflow=10`），等连接 `pool_timeout=30s` | SQLAlchemy 默认 | ✅ | [database.py](../src/app/database.py)（**没写参数 = 用默认值**） |
| **L4 SQLite 写者** | **1**（全库同时只能有一个写事务），忙等 `busy_timeout=5000ms` | SQLite 的锁模型 | ❌ 换 PG 才行（决策 13） | `app.db` |

#### 13.3b ⭐⭐ 判据：不看"上限是多少"，看"顶住时客户端看到什么"

| 层被顶穿 | 我们回什么 | 客户端能自救吗 | 评价 |
|---|---|---|---|
| L0 上游配额 | **429 + `Retry-After`**（#60 翻译出来的） | ✅ 等一等 | 🟢 好 |
| L1 我们的闸门 | **503 + `Retry-After`**（12g-2 要做的） | ✅ 稍后重试 | 🟢 好 |
| L2 HTTP 池满 | 排队等（100 条几乎不会满） | ❌ 什么都看不见 | ⚪ 无感 |
| L3 DB 池满 | **卡 30 秒，然后 500** | ❌ | 🔴 最差 |
| L4 写锁冲突 | 500（或 200 + 0 帧，见 #73） | ❌ | 🔴 最差 |

⭐⭐ 一句话判据：**好的限流在最外层拒绝、给一个能读懂的码；坏的限流在内层排队，等出一个 500。**

#### 13.3c 由此得到一条硬规则

> **闸门（L1）必须小于它下游的池（L3）。**

反例：假如把 `MAX_CONCURRENT_UPSTREAM_CALLS` 调成 **20**（> 15）：

1. 第 16 条流顺利拿到上游额度，但**借不到**数据库连接；
2. `await` 卡在 `pool_timeout=30s` 上；
3. 30 秒后抛 `sqlalchemy.exc.TimeoutError` → **500**；
4. 而客户端在这 30 秒里**一个字节都没收到**，早就自己超时走了。

也就是说：**把闸门设得太宽，等于把「明确的 503」换成「30 秒后的 500」** ——
这不是"更宽松"，是**更差**。

📎 能直接背下来的数字关系：

```text
4（闸门）  ≤  15（DB 池）  «  100（HTTP 池）
```

#### 13.3d 为什么闸门默认是 4，不是 15

三个约束同时压着：

1. ~~上游配额：4 条流同时生成已经够把常见 RPM 打满~~ 🔴 **2026-11-04 订正（查到真实数字了）**：📎 `deepseek-flash` 的**并发上限是 2500**，4 对它来说微不足道。**所以「闸门设成 4」的理由不是上游配额**，而是下面两条 + 成本预算；
2. **成本 = 并发 × 时长 × 输出上限**：`4 × 4096 tokens` 就是"一次洪峰最多烧多少"的上界；
3. **要给非 chat 路由留余量**：对话 CRUD / 分页**不经过**这道闸门，它们还要用那 15 条连接。

⚠️ **4 是"保守的起点"，不是"压测出来的最优值"。** 门 3 最后一项（压测）做完之前，
任何"4 够不够"的说法都是猜。

#### 13.3e 多副本会怎么变

| 形态 | L1 闸门真实上限 | L3 DB 池 | 备注 |
|---|---|---|---|
| 现在：1 进程 | **4** | 15 | 每进程 4 ≤ 15，安全 |
| `--workers 4` | **16**（4 × 4） | 每进程各 15 | 单进程仍安全；但**上游配额按账号算**，16 条同时生成很可能直接打爆 → 429 |
| 多机 | 16 × 机器数 | 每机独立 | 进程内计数 = 假上限，必须放 Redis / 网关层才作数（#44 的重审条件） |

#### 13.3f 📎 实测（2026-11-20，13f / 决策 51）

环境：**假上游**（12 帧 × 20ms ≈ 0.4s/请求）→ `scripts/loadtest_chat_stream.py`，单进程，
限流放大到 60k/min（否则测到的是限流器），每档 3 轮：

| 并发 | 状态码分布 | 首帧 p50 | 首帧 p95 | 总时长 p95 | 墙钟 | **吞吐**（成功÷墙钟） | 池峰值 |
|---|---|---|---|---|---|---|---|
| 1 | 200 × 3 | **19 ms** | 27 ms | 410 ms | 0.41 s | 2.4 req/s（没喂饱） | 1 |
| 4 | 200 × 12 | **47 ms** | 72 ms | 436 ms | 0.44 s | **9.1 req/s** | **4** |
| 8 | 200 × 24 | **398 ms** | 504 ms | 871 ms | 0.87 s | **9.2 req/s** | **4** |
| 16 | 200 × 36 + **503 × 12** | 463 ms | 884 ms | 1258 ms | 1.26 s | **9.5 req/s**（只算成功） | **4** |
| 32 | 200 × 44 + **503 × 52** | 761 ms | **1485 ms** | 1788 ms | 1.79 s | 8.2 req/s | **4** |

⭐⭐ **三个结论（都是数字，不再是推导）**：

1. **c=8 仍然全 200** —— 闸门 4 不等于「第 5 个用户被拒」，因为 `upstream_queue_timeout=1.0s`
   允许排队：吞吐上限 ≈ `slots × (1 + queue_timeout / service_time)` = 4 × (1 + 1.0/0.4) ≈ **14**
2. **首帧延迟随排队线性上升**（47ms → 398ms → 761ms）—— **排队不是免费的**，它把延迟从「上游时间」
   变成「排队时间 + 上游时间」
3. **池峰值始终 4**（上限 15）→ 先顶住的是**我们自己的闸门**，不是数据库池
4. ⭐ **吞吐从 c=4 起就钉死在 ≈9.1 ~ 9.5 req/s，而延迟 4 倍增长** —— 用实测墙钟反算
   （`成功数 ÷ 墙钟`），与理论上限 `slots / service = 4 / 0.41 = 9.76` 对得上。
   **这就是「饱和」的直接证据：过了饱和点，加并发只加延迟、不加吞吐。**
   📎 c=1 只有 2.4 req/s 是**未饱和**（1 个并发喂不满 4 个槽位），不能算容量

⚠️ 这三个数**只对「假上游 0.4s/请求」这一条件成立**：换成真上游（几十秒的流）时，
吞吐上限会掉到个位数，而 p95 首帧会变成「排队 + 上游首帧」。

---

### 13.4 一次请求最多花多少钱（2026-11-04，📎 单价来自 DeepSeek 官方定价页）
`deepseek-flash` 峰时价：**输入（cache miss）$0.30 / 1M tokens、输出 $1.20 / 1M tokens**（非峰时减半）。
模型侧：context **1M**、最大输出 **384K（393216）**、并发上限 **2500**。

| 护栏 | 上界 | 折成钱（峰时） | 位置 |
|---|---|---|---|
| 输入 · 单条正文 | 20 000 字符 | —— | `schemas.MAX_CONTENT_CHARS` |
| 输入 · 条数 | 100 条 | —— | `schemas.MAX_MESSAGES` |
| **输入 · 合计** | **60 000 字符** ≈ 4 万 tokens | **≈ $0.012** | `schemas.MAX_TOTAL_CHARS` |
| **输出** | `MAX_TOKENS_CEILING`（默认 4096，可配上界 32768） | 4096 → **$0.005**；32768 → **$0.039** | `config.max_tokens_ceiling` |
| 同时在飞 | `MAX_CONCURRENT_UPSTREAM_CALLS`（默认 4） | 一次洪峰 ≈ 4 × 单请求 | `app.state.upstream_semaphore` |

⭐⭐ **单请求最坏 ≈ $0.05**（输入 0.012 + 输出 0.039）。

📌 判据：**输入是输出的 61 倍**（1M vs 4096 tokens）——
所以护栏要**先压输入、再压输出**。只压 `max_tokens` 等于把 98% 的风险留在门外。

⚠️ **这个数是「单请求上界」，不是「总损失上界」**：没有限流（#37）时一个循环仍能连续烧。
真正防刷的是 #37，不是这里的任何一个数字。

🔴 另一条容易配错的约束：**`MAX_TOKENS_CEILING` 必须 ≤ 模型的真实输出上限**。
配大了 → 客户端请求通过我们的检查、却被上游以 400 拒绝、且 body 里没有超长 marker
→ 落到 `UPSTREAM_REJECTED` → **502**（语义上"我们的配置错了"，但看起来像上游故障）。

### 13.5 容器栈的三条时序（13a 收口，2026-11-19）

> 判据：**能凭这三张图回答「谁先起、谁先停、出事时用户看到什么」**。
> 三张图的每一步都有 📎 实测（13a-2b / 13a-2c，Docker 29.9.3，隔离项目 + 全新空卷）。

#### ① `docker compose up` —— 启动顺序

```text
docker compose up -d
        │
        ├─ ① migrate（一次性，restart: "no"）
        │       command: python -m alembic upgrade head
        │       env: 只有 DATABASE_URL（不挂 .env → 没有 LLM_API_KEY）
        │       卷:  app_data:/app/data（与 app 同一个）
        │       exit 0 ──────────────┐
        │       exit ≠ 0 ──▶ ✗ up 退出码 1，app 停在 created，不会启动
        │                            │
        ├─ ② app ◀───────────────────┘（condition: service_completed_successfully）
        │       env_file: .env + environment（HOST=0.0.0.0 / PORT=8000 / DATABASE_URL）
        │       expose: 8000（不对宿主发布）
        │       healthcheck（镜像自带）→ 探 127.0.0.1:8000/health
        │       healthy ─────────────┐
        │                            │
        └─ ③ proxy ◀────────────────┘（condition: service_healthy）
                nginx:1.29-alpine，唯一发布 80
                /nginx-health → 200 "ok"（只证 nginx 活着，不牵 app）
```

#### ② 一次请求走的路

```text
浏览器 ──HTTP:80──▶ proxy(nginx)
                      │  resolver 127.0.0.11 valid=10s + server app:8000 resolve
                      │  proxy_buffering off   ← 不关它，SSE 会被攒成一块
                      │  proxy_read_timeout 130s > upstream_total_timeout 120s
                      ▼
                    app(uvicorn, 单进程, uid 10001)
                      ├─ X-API-Key → sha256 → users/api_keys（401 的唯一来源）
                      ├─ 令牌桶（按 user.id，60/分 + 突发 20 → 429 + Retry-After）
                      ├─ SQLite（命名卷 /app/data/app.db）
                      └─ httpx → api.deepseek.com（闸门 4 个槽位；总预算 120s）
```

⚠️ 代理这一跳**自己也会产生错误**（413 / 502 / 504）。它们**默认**是 nginx 的 HTML 页，
不受我们的 envelope 管 —— 现已由 `error_page` + `@json_*` 内部 location 改成**同一个信封**
（[#89](../docs/todos.md) 已解决、决策 52，详见 [§13.6](#136-反代层错误也是契约89--决策-52)）。
body 超限在两层都还会拦，但形状现在一致：nginx 的 `1m` 上限 → **413 JSON**，app 自己的 422 不变。

#### ③ `docker compose stop` —— 停机顺序（依赖者先停）

```text
docker compose stop
        │
        ├─ ① proxy  收 SIGQUIT（compose 的 stop_signal）
        │       不再接新连接，把「手上还有的请求」做完 → 在途 SSE 继续流
        │       📎 stop 在 1.2s 发起，客户端仍跑到 4.8s 收到 data: [DONE]
        │
        ├─ ② app    收 SIGTERM → uvicorn 的 timeout_graceful_shutdown=30s（决策 39）
        │       宽限期内跑完 → exit 0；超窗口 → 明确切断（无 [DONE]）
        │       compose 的 stop_grace_period: 40s = 30s 窗口 + 10s 收尾余量
        │
        └─ ③ migrate（已退出的容器，无事可做）

📎 三个容器 ExitCode 全 0。⚠️ 换默认 SIGTERM 给 nginx 就是 fast shutdown = 掐断连接。
```

⚠️ **启动 / 停机两条链上的每个等待都有超时**：migrate 失败不会卡住（直接非 0 退出）、
app 等 `service_healthy` 最多等到健康检查判失败、nginx 的 `proxy_read_timeout 130s`
必须大于应用侧 120s —— **任何一处配反，症状都是「用户端莫名断开」而不是报错**。

---

### 13.6 反代层错误也是契约（#89 / 决策 52）

⭐ **一句话**：`502`/`504` 发生时 app **根本没执行** —— 所以「错误信封由 app 统一定义」必须扩展成
「错误信封由**这条链**统一定义」。nginx 是唯一能替 app 说话的地方。

| 谁产生 | 状态码 | `code` | 📎 怎么触发的（2026-11-20 实测） | 信封 |
|---|---|---|---|---|
| app | 422 | `VALIDATION_ERROR` | body 200 KB（> 20000 字符），< 1 MB | JSON |
| **nginx** | 413 | `PAYLOAD_TOO_LARGE` | body 2 MB > `client_max_body_size 1m` | **JSON**（修前是 HTML） |
| **nginx** | 502 | `BAD_GATEWAY` | 端口没在听（进程崩了）→ 连接被**拒绝** | JSON |
| **nginx** | 504 | `GATEWAY_TIMEOUT` | ① 应用 130 s 没回完 ② **容器停掉 → SYN 被丢弃 → 握手超时** | JSON |

⚠️ **两个 413 不是孪生兄弟**：`PAYLOAD_TOO_LARGE` 是**我们**嫌大（协议层体积），
`UPSTREAM_PAYLOAD_TOO_LARGE` 是**上游**嫌大（我们把它的判断透传给你）。客户端必须按 `code` 分支，不能按状态码。

⚠️ **两条 request_id 空间**：nginx 的是 32 位 hex（`$request_id`），app 的是 12 位 ——
nginx 错误在 app 日志里查不到，只能 `grep rid=<id>` 查 nginx 访问日志（格式 `app_json_ext`）。

🔴 **已知缺口（#92）**：`proxy_connect_timeout` 还是默认 **60 s** —— 应用下线时用户要等 60 秒才拿到 504。

---
### 13.7 上游客户端的两层接缝：工厂层 vs 取用层（2026-11-20，决策 4 + 53）

⭐⭐ **一句话**：**「怎么造」和「怎么取」是两个独立的接缝** —— 用例里的 mock 换**取用层**，
全局哨兵换**工厂层**。两者能共存，正是因为它们在不同时刻被调用、且清理机制不同。

| 层 | 谁 | 什么时候被调用 | 测试里由谁替换 | 被 `dependency_overrides.clear()` 清掉吗 |
|---|---|---|---|---|
| **工厂层** | `create_llm_client()`（`app.llm_client`），由 `lifespan` 调用 | **启动时一次** | `tests/conftest.py` 的 `_forbid_real_upstream`（session 级哨兵） | ❌ **清不掉**（它是模块属性，不是依赖覆盖） |
| **取用层** | `get_llm_client(request)`（`app.api.deps`）→ 读 `request.app.state.llm_client` | **每个请求一次** | 用例里的 `app.dependency_overrides[get_llm_client] = lambda: FakeLlm(...)` | ✅ 立刻清掉 |

```text
应用启动（每个 TestClient 都跑一次 lifespan）
  └─ create_llm_client()                       ← 【工厂层】哨兵改这里
        │   ⚠️ 换成的是「造出来的东西【碰网络】才报错」的工厂，
        │      不是「一调用就报错」—— 后者会让 lifespan 直接炸，所有用例一起红
        ↓
     app.state.llm_client = LlmClient(transport = 会炸的 transport)

每个请求
  └─ Depends(get_llm_client)                   ← 【取用层】mock 改这里
        ├─ 有 override → 直接返回 FakeLlm（完全不走 app.state）
        └─ 无 override → 走原始实现 → 取 app.state.llm_client（= 哨兵造的那个）
                          ↓
                    路由调用 client.complete() / open_chat_stream() / list_models()
                          ↓
                    真正发 HTTP 的那一刻 → RealUpstreamForbidden
```

#### 13.7a 三个时点：造 → 取 → 发（最容易混淆的地方）

| 时点 | 发生什么 | 📎 实测 |
|---|---|---|
| ① **造**（lifespan） | 成功，得到一个 `LlmClient` —— **不报错** | `forbidden_llm()` 返回 `LlmClient` |
| ② **取**（`Depends`） | 成功，拿到对象 —— **不报错** | `app.state.llm_client` 类型是 `LlmClient` |
| ③ **发**（适配器里） | **报错** `RealUpstreamForbidden` | `POST /v1/chat` / `GET /v1/upstream/models` 都抛 |

🔴 **由此得到一条重要推论**：**pre-flight 就失败的请求不会触发哨兵** —— 400 / 401 / 404 / 422 / 500
全都发生在「打上游之前」。📎 实测：无 override + `{"messages": []}` → **422**，哨兵一声没响。
这正是 9 个 `/v1/chat` 用例（`test_auth` / `test_errors` / `test_limits`）**没有 override 也照样绿**的原因。

#### 13.7b 为什么 mock 必须在取用层、哨兵必须在工厂层

| 问题 | 答案 |
|---|---|
| 为什么 mock 不换工厂？ | 工厂**只在启动跑一次**。要让「A 用例用假上游、B 用例用另一个假上游」，只能在**每次取用**时换 —— 取用层是每请求一次的接缝，粒度正好 |
| 为什么哨兵不也放取用层？ | 用例里的 `app.dependency_overrides.clear()` 会把它一起清掉 → 保护瞬间失效。工厂是**模块属性**，`clear()` 碰不到 |
| 为什么哨兵不在 lifespan 里直接 raise？ | lifespan 每个用例都跑 → 所有用 `TestClient` 的用例一起炸，连已经 override 的也炸。**粒度太粗** |
| 为什么哨兵要换整个 transport 而不重写方法？ | 所有方法都走 `self._http` → 将来适配器**新增的方法自动被保护**，不用回来补 |

★ **两条判据**：
1. **mock = 换「怎么取」（每请求、可清）；哨兵 = 换「怎么造」（每启动、清不掉）。**
2. **守卫要响在「真正发生危险动作」的那一刻**（发 HTTP），不要在「准备动作」（造 / 取）时响 —— 
   否则误伤整批用例，最后一定会有人把它关掉。

---
## 14. 决策 ↔ 代码 ↔ 钉住它的测试（一张对账表）

> 用途有两个：读到一条决策想知道**它落在哪个符号**；改一个符号想知道**哪条决策会因此失效**。
> ⚠️ **本表只写符号名、不写行号** —— 📎 2026-11-16 实测：旧表里的行号整体漂了 2~30 行（一次 4 行的删除就够），
> 行号是**必然过期**的信息；要行号就 `Select-String -Pattern "def chat_stream"`。
> 决策正文（为什么、放弃了什么）在 [decisions.md](decisions.md)，这里只放**落点**。

| # | 决策一句话 | 代码落点 | 钉住它的测试 |
|---|---|---|---|
| 1 | 项目与笔记同仓库 | 仓库根 | — |
| 2 | `app` + `src/` 布局 | [pyproject.toml](../pyproject.toml) `packages = ["src/app"]` | — |
| 3 | Docker 延后 | 未落地（#49） | — |
| 4 | client 应用级共享 | [app.py](../src/app/api/app.py) `lifespan`、[deps.py](../src/app/api/deps.py) `get_llm_client`（两层接缝见 [§13.7](#137-上游客户端的两层接缝工厂层-vs-取用层2026-11-20决策-4--53)） | `test_upstream.py`（间接：override 的正是取用层）、[conftest.py](../tests/conftest.py) `_forbid_real_upstream`（工厂层哨兵） | |
| 5 | 三种错误形状暂不统一 | 已被 #25 取代 → [errors.py](../src/app/errors.py) | `test_errors.py`（7） |
| 6 | 上游错误三层翻译 | [llm_client.py](../src/app/llm_client.py) `_request`（L1/L2）、`list_models`（L3） | ✅ `test_adapter_http.py`（10，穿过 `MockTransport`） |
| 7 | 流式用 SSE | [app.py](../src/app/api/app.py) `SseResponse`、`chat_stream` | `test_stream_frames.py`、`test_stream_consumes_fake_chunks` |
| 8 | 业务规则抽成共用函数 | [app.py](../src/app/api/app.py) `ensure_last_message_is_user`（两条 chat 路由共用） | `test_error_envelope[business_400]`、`test_stream_preflight_failure_changes_status_code` |
| 9 | 请求级会话由 `get_db` 统一提交 | [deps.py](../src/app/api/deps.py) | `test_create_then_get`（间接） |
| 10 | 契约按用途分家（In / Patch / Out） | [schemas.py](../src/app/schemas.py) `ConversationIn` / `ConversationPatch` / `ConversationStatsOut` | `test_conversations.py`（9） |
| 11 | 标题规则抽成 `ConversationTitle` | [schemas.py](../src/app/schemas.py) | `test_invalid_title_returns_422`（3 组）、`test_title_is_stripped` |
| 12 | PATCH 拒绝空 body | [schemas.py](../src/app/schemas.py)（`title` 必填） | ⚠️ **无**（3 组 422 打的是 POST） |
| 13 | SQLite 起步、可切 PG | [config.py](../src/app/config.py)、[database.py](../src/app/database.py) | — |
| 14 | 引擎模块级单例 | [database.py](../src/app/database.py) `engine`、关闭段 [app.py](../src/app/api/app.py) `engine.dispose()` | `test_smoke.py`（间接：`/health/ready` 用到引擎） |
| 15~19 | 命名 / 完成度表述 / 注释边界 / 标记符号 /「一次对话」无状态 | 文档与约定；"无状态"体现在**没有 messages 表**（#35） | — |
| 16 | 计费记录不跟着对话删 | [models.py](../src/app/models.py) `ondelete="SET NULL"` + 关系上**不写** `cascade` | ✅ `test_migrations.py`（DDL 对比钉住 `ON DELETE SET NULL`；📎 从迁移里删掉它 → 两条全红） |
| 20 | 两阶段记账 | [app.py](../src/app/api/app.py) `add` + `commit` → `record_usage` | `test_stream_accounting.py`（10） |
| 21 | 防刷靠限流不靠记账 | 未落地（#37 #44） | — |
| 22 | 游标分页为主 | [app.py](../src/app/api/app.py) `list_conversations` | `test_pagination_walks_two_pages` |
| 23 | `prod` + `debug` 启动即崩 | [config.py](../src/app/config.py) `_forbid_debug_in_prod` | ⚠️ **无**（手动实测过 `exit_code=1`） |
| 24 | `dictConfig` 接管日志 | [logging_setup.py](../src/app/logging_setup.py) | ⚠️ **无** |
| 25 | 统一错误形状、自有代码只抛 `AppError` | [errors.py](../src/app/errors.py) `_error_response` / `AppError` | `test_errors.py`（7，含 3 种 404 靠码分开） |
| 26 | 坏帧三档处置 | [llm_client.py](../src/app/llm_client.py)（语义层）+ `event_source` 的守卫 | `test_stream_adapter.py`（11）、`test_stream_frames.py`（12） |
| 27 | 账单四态 + `StrEnum` | [models.py](../src/app/models.py) | `test_status_enum_values_are_pinned` |
| 28 | 两次写入都用 `commit` | [app.py](../src/app/api/app.py) `record_usage` | `test_concurrency.py`（4，串行化回归） |
| 32 | 测试跑真实迁移，不跑 `create_all` | ✅ [tests/conftest.py](../tests/conftest.py) `migrated`（session 级）+ `lifespan` 已不建表（13b-2b-2） | ✅ `test_smoke.py`（2 条 ready 用例）+ `test_migrations.py` |
| 33 | 迁移守卫用子进程跑 alembic CLI | [tests/test_migrations.py](../tests/test_migrations.py) `_run_alembic` | 它自己就是守卫（📎 3 个变异 6 条全红） |
| 40 | 身份与凭据存两张表，密钥只存 sha256 | [models.py](../src/app/models.py) `User` / `ApiKey`、[auth.py](../src/app/auth.py) `hash_api_key` / `find_user_by_key` | ✅ `test_auth.py::test_key_is_stored_as_sha256_not_plaintext` |
| 41 | 鉴权做成**依赖**（`CurrentUserDep`）而不是中间件；越权一律 **404** | [deps.py](../src/app/api/deps.py) `require_user` / `CurrentUserDep`、[app.py](../src/app/api/app.py) `require_conversation` / `_fetch_conversation_stats` / `list_conversations` | ✅ `test_auth.py`（13 条）+ `test_source_rules.py::test_every_non_public_route_requires_a_user`（📎 变异：删掉某路由的 `CurrentUserDep` → 点名 `DELETE /v1/conversations/{conv_id}`） |
| 42 | 限流：进程内令牌桶，按 user 计不按 key 计 | [ratelimit.py](../src/app/ratelimit.py) `RateLimiter`、[deps.py](../src/app/api/deps.py) `require_user` | ✅ `test_rate_limit.py`（9 条；📎 变异「桶不按 user 分」→ `assert 429 == 200`） |
| 43 | 镜像多阶段 + 非 root + exec 形式 `python -m app` | [Dockerfile](../Dockerfile)、[.dockerignore](../.dockerignore) | ✅ `tests/test_docker_assets.py`（5 条；📎 7 个变异全红）+ 📎 真 `docker build` / `docker run`（13a-1c） |
| 45 | 部署时迁移由一次性 `migrate` 服务执行，app 等它成功再起 | [docker-compose.yml](../docker-compose.yml) `migrate` / `app.depends_on` | ✅ `test_docker_assets.py::test_compose_migrates_before_app_starts` + `::test_compose_defines_database_url_once`（📎 6 个变异全红：删 `depends_on` / 换卷 / 加 `env_file` / 抄第二份连接串 / app 自己跑迁移 / `restart: always`） |
| 46 | 入口只有 nginx，app 不发布宿主端口 | [docker-compose.yml](../docker-compose.yml) `proxy`、[deploy/nginx.conf](../deploy/nginx.conf) | ✅ `test_docker_assets.py` 4 条：`test_app_is_not_published_to_host` / `test_proxy_waits_for_healthy_app_and_exits_gracefully` / `test_nginx_conf_streams_and_reresolves` / `test_nginx_read_timeout_exceeds_app_budget`（📎 11 个变异全红：`buffering on` / 删 `resolver` / 去 `resolve` / 读超时 60s / 删 `proxy_cache` / app 加回 `ports` / `SIGTERM` / `service_started` / 端口改 8080 / `.dockerignore` 删 `deploy/` / `UPSTREAM_TOTAL_TIMEOUT=200`） |
| 47 | 客户端 IP：只信代理那一跳 | [docker-compose.yml](../docker-compose.yml) `FORWARDED_ALLOW_IPS` / `networks.app_net`、[app.py](../src/app/api/app.py) `_client_label` | ✅ `test_access_log.py`（3 条，含**真 uvicorn** 的伪造头用例）+ `test_docker_assets.py::test_forwarded_allow_ips_matches_proxy_static_ip`（📎 7 个变异全红） |
| 48 | 日志一行一 JSON；轮转归 Docker | [logging_setup.py](../src/app/logging_setup.py) `JsonFormatter`、[docker-compose.yml](../docker-compose.yml) `logging` | ✅ `test_log_json.py`（2 条：子进程逐行 `json.loads` / traceback 不换行）+ `test_docker_assets.py::test_every_service_rotates_its_logs`（📎 6 个变异全红） |
| 49 | 文档里边数字用测试钉住 | [tests/test_docs_contract.py](../tests/test_docs_contract.py)、[tests/conftest.py](../tests/conftest.py) `pytest_collection_finish` | ✅ 4 条（📎 8 个变异全红；子集运行 2 passed + 2 skipped） |
| 50 | 指标最小集 + `/metrics` 只给容器网络内抓 | [metrics.py](../src/app/metrics.py)、[app.py](../src/app/api/app.py) `/metrics` 路由、[deploy/nginx.conf](../deploy/nginx.conf)、[deploy/alerts.yml](../deploy/alerts.yml) | ✅ `test_metrics.py`（6 条，📎 4 个变异全红）+ `promtool check rules`（📎 SUCCESS / 故意拼错 → FAILED） |
| 51 | 压测不打真上游；容量探针自带 PASS/FAIL | [scripts/fake_upstream.py](../scripts/fake_upstream.py)、[scripts/loadtest_chat_stream.py](../scripts/loadtest_chat_stream.py) | ⚠️ 无自动化用例（要真端口/真 key，与 `probe_graceful_shutdown.py` 同性质）—— 📎 但判据可失败：`--gate 2` → **FAIL exit 1**；指向假上游本身 → **FAIL**（全 404） |
| 52 | 反代层 413/502/504 也回应用信封 | [deploy/nginx.conf](../deploy/nginx.conf) `error_page` + `@json_*`、`map $http_origin`、`log_format app_json_ext` | `test_docker_assets.py`（5 条，📎 6 变异全红） |
| 53 | 非流式 `/v1/chat` 接真上游 | [llm_client.py](../src/app/llm_client.py) `complete()` / `LlmCompletion`、[app.py](../src/app/api/app.py) `chat`、[conftest.py](../tests/conftest.py) `_forbid_real_upstream` | `test_upstream.py`（4）、`test_adapter_http.py`（6）、`test_limits.py` `test_gate_applies_to_non_stream_chat`、`test_source_rules.py`（`_READ_ONLY_ROUTES` 已空） |
| 54 | `LlmCompletion.usage` 保持 `dict`，不换 `MappingProxyType` | [llm_client.py](../src/app/llm_client.py) `LlmCompletion` docstring | `test_adapter_http.py::test_complete_usage_stays_a_plain_dict`（📎 变异「换成 proxy」→ 该条红、既有 `==` 条仍绿） |
| 55 | 质量门 4 道 → 5 道：加 `pyright` 与编辑器对齐 | [pyrightconfig.json](../pyrightconfig.json)、[.github/workflows/ci.yml](../.github/workflows/ci.yml)、[pyproject.toml](../pyproject.toml) dev 组 | CI 独立一步 `Type check (editor parity)`。📎 **变异 A**（`_pool_checked_out` 改回 `getattr`）→ mypy 仍绿 / pyright **2 errors**；📎 **变异 B**（`constants.py` 加 `int = "x"`）→ 两边都红 |
| 56 | `/docs` 的凭据改成 OpenAPI 声明（`APIKeyHeader` + `Security`） | [deps.py](../src/app/api/deps.py) `api_key_header` / `require_user` | `test_auth.py`：`test_openapi_declares_api_key_security` + `test_public_routes_are_not_marked_secure`。📎 变异「退回修复前（行为不变）」→ 只有前一条红、15 条行为用例全绿 |

⭐ **这张表最有用的是最后一列的空格。** 空着的那几条（#12 #23 #24）意味着：
**改坏了不会有任何测试变红** —— 目前只靠注释和人工实测守着。

> 📌 用例总数与每个文件的用例数**不写在这张表里** —— 唯一出处是 [tests/README.md](../tests/README.md) §1。

---

## 15. 附录：速查

### 15.1 常量

| 常量 | 值 | 位置 |
|---|---|---|
| `HEADER_REQUEST_ID` | `X-Request-ID` | [constants.py](../src/app/constants.py) |
| `HEADER_API_KEY` | `X-API-Key` | [constants.py](../src/app/constants.py) |
| `KNOWN_MODELS` | `["deepseek-flash", "deepseek-v4-pro"]` | [app.py](../src/app/api/app.py) |
| `ALLOWED_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173"]` | [constants.py](../src/app/constants.py)（13c-1 从 `api/app.py` 搬来，供 500 处理器复用） |
| `MAX_ERROR_BODY_CHARS` | `500` | [llm_client.py](../src/app/llm_client.py) |

### 15.2 文件职责一句话

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
| `api/deps.py` | 依赖的集中地（可替换的接缝）：含 `get_db` / `get_llm_client` / `get_upstream_slot` / **`require_user`** | 不含路由 |
| `auth.py` | API key 的生成 / 哈希 / 查人（请求鉴权与签发 CLI 共用） | 不认识 HTTP 头（只吃明文字符串） |
| `ratelimit.py` | 令牌桶（按 key 分桶、时钟可注入） | 不认识 HTTP；不自己决定状态码 |
| `Dockerfile`（仓库根） | 多阶段镜像：builder 只交出 `/opt/venv`；runtime 非 root + exec 形式 CMD | 不写业务配置（用环境变量注入） |
| `docker-compose.yml`（仓库根） | 单机栈：**`proxy`（nginx，唯一发布 80）** → `app`（`expose: 8000`，健康后才起反代）→ 一次性 `migrate`；**命名卷** `app_data:/app/data`；连接串用 `x-database-url` 锚点共享 | 不写密钥（`app` 的 `env_file: .env` 从宿主读；`migrate` **只拿 `DATABASE_URL`**）；不重复写 app 的 `healthcheck`（继承镜像） |
| `deploy/nginx.conf`（仓库根下 `deploy\`） | 反代唯一配置：`proxy_buffering off`（不关流式就废）、`resolver 127.0.0.11 valid=10s` + `server app:8000 resolve`（否则 app 换 IP 后永久 502）、`client_max_body_size 1m`、`/nginx-health` | 不放业务逻辑；不改 app 的响应形状（⚠️ 例外：413 是 nginx 自己的 HTML 页 → #89） |
| `.dockerignore` | 构建上下文里「白名单之外的一切」（📎 26 文件 / 471 KB） | 不排除 `uv.lock` / `alembic` / `src`（会构建失败） |
| `keys.py` | API key 运维 CLI（`python -m app.keys create/list/revoke`） | 不含业务路由；不打印明文到日志 |
| `api/app.py` | FastAPI 对象 + lifespan + 全部路由 | 不写上游协议细节 |
| `main.py` | 命令行 demo / ping | 不是 HTTP 入口 |
| `__main__.py` | `python -m app` 的 HTTP 入口 | 不直接建 app |

---

## 更新日志

| 日期 | 变更 |
|---|---|
| 2026-11-21 | **新增 §1.5「请求头全景」**：四类头（凭据 `X-API-Key` / 追踪 `X-Request-ID` / 代理链路 `X-Real-IP`·XFF·Proto / 上游与协议 `Authorization`·`Content-Type`·`Origin`）× 谁写 × 伪造后果 × 代码位置；标注两个反直觉点（`Authorization` 不是我们的鉴权头、`X-Request-ID` 永远不能当凭据）。配套 [决策 57](decisions.md)（ID 的单一真相在 nginx 边界）与 RUNBOOK §7/§11c |
| 2026-11-04 | **专门做一次「关系图」盘点**（只补图，不动代码）。新增 §2.4 依赖注入解析图（📎 实测解析顺序 `settings → db`、流式的依赖收尾排在**整条流之后**）、§2.5 `app.py` 内部调用链 + 扇入表（改一个 helper 要回归几个端点）、§7.7 错误码的**两个出口** + 每个码的产生点（`STREAM_*` 不在 `_STATUS_BY_CODE` 里）、§9.5 配置项 → 读取点、§13 运行形态（单进程 / 17·13 条路由 / 15 条 DB 连接 / 100 条上游连接 / `busy_timeout` 5s）、§14 决策 ↔ 代码 ↔ 测试对账表（空着的那几格 = 改坏没人红）。⚠️ 同时订正三处过期事实：§11 的用例数（24 → 指向 tests/README，不再抄）、§12.1 的 `flush`（已改 `commit`）、索引里「账单三态」（是四态） |
| 2026-11-03 | **新增 §8.6「完整时序」**：三条生命线 × 十二个时刻的时序图 + 每个时刻出错会怎样（15 行矩阵）+ 账单状态机（时刻编号对应）+ 出口 × 状态全矩阵 + 三个「问题叠加」组合。⭐ 核心：**⑤（响应头发出）是「还能改状态码」与「只能往流里塞错误」的分界线**；⭐⭐ 另一个核心：**`recorded` 是锁存器** —— 一旦拿到 usage，状态就定格 `completed`，后面发生什么都改不了。📎 断开那一行按实测订正（读到 0 / 1 / 3 段就退出，三种都落 `aborted`） |
| 2026-11-02 | 建立。13 节：七层栈 / 模块依赖 / lifespan / ER+DDL / 端点总表 / 成功形状 / 错误形状 / SSE 帧 / 配置 / 日志 / 测试 / 状态机 / 速查 |
