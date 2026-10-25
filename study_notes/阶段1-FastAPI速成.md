# 阶段 1 · FastAPI 速成 · 学习笔记

> **用途**：用最短路径掌握**能交付 LLM 应用后端**的 FastAPI 核心能力（含 SSE 流式、依赖注入、数据库、测试、部署）。
> **写法约定**：术语后面跟一句 🧒「人话解释」，公式用 LaTeX，坑点用 ⚠️ 单独标出，重点用 ⭐。
> **目标读者**：已完成阶段 0（[阶段0-工程基础.md](./阶段0-工程基础.md)），会 pydantic 与 async 基础。
> **实践产出**：跟随本笔记从空目录亲手搭建一个可流式返回的聊天后端；仓库不附带预配置项目。
> **同系列**：ML 阶段笔记（房价预测，同一套写法）—— *该笔记不在本仓库*。

---

## 本笔记的代码**全部实测过**

| 依赖 | 实测版本 |
|------|---------|
| Python | 3.12.15 |
| fastapi | **0.143.0**（2026-10-14 本仓库实测；本笔记其余示例写于 0.142.2 时期） |
| starlette | **1.8.0**（2026-10-14 本仓库实测；原为 1.7.0） |
| uvicorn | 0.54.0（2026-10-14 实测一致） |
| pydantic | 2.13.5 |
| httpx | 0.28.1 |
| sqlalchemy | **2.1.3**（+ `greenlet` 3.5.6） |
| aiosqlite | 0.22.1 |
| pytest / pytest-asyncio | 9.1.1 / 1.4.0 |

> ⭐ **为什么强调这个**：网上大量 FastAPI 教程停留在 0.7x / pydantic v1 时代，
> 而 **Starlette 已经从 0.x 跨到 1.x**，写法有变（本笔记标注了每一处"旧写法已废弃"）。
> 下面每一段代码都在上述版本上**真实跑通**，并有断言支撑。

**2026-10-14 本仓库 `uv add fastapi "uvicorn[standard]"` 的实际结果**（步骤 1.1）：

```text
Resolved 31 packages | Installed 11 packages

直接依赖（我们声明的）：fastapi==0.143.0、uvicorn==0.54.0
间接依赖（它们自己带来的）：
  annotated-doc==0.0.5    click==8.5.0        httptools==0.9.0
  opentelemetry-api==1.45.1  pyyaml==6.0.3    starlette==1.8.0
  watchfiles==1.3.0       websockets==17.2
```

| 观察 | 说明 |
|---|---|
| `fastapi 0.142.2 → 0.143.0`、`starlette 1.7.0 → 1.8.0` | **文档写的是当时版本，装到的是新版本** —— 这正是"版本号必须实测"的原因 |
| `click` / `pyyaml` / `watchfiles` | uvicorn 的 `[standard]` extras 带来的（`watchfiles` 支撑 `--reload`） |
| `httptools` / `websockets` | 更快解析 / 支持 WebSocket 协议 |
| `annotated-doc` / `opentelemetry-api` | fastapi 新版引入的间接依赖（标注文档 / 可观测性接口） |
| `Resolved 31 packages` | 是**整张依赖图**的解析总数，不是新增 31 个 |

---

## 如何阅读这份笔记

**第一遍（建立全局）**
1. 先读 **「全局地图」** 和 **Step 1** —— 不搞清 HTTP/ASGI，后面全是黑盒魔法
2. 按 **Step 2 → Step 13** 顺序精读，每步都手敲一遍
3. **Step 9（SSE 流式）是重点** —— 这是"LLM 应用"和"普通后端"的分水岭

**第二遍（补深度）**
4. 读 **「难点拓展」** —— ASGI 协议细节、依赖注入解析算法、OpenAPI 生成原理、并发模型

**随时查阅**
5. 写代码时 → **附录 A 代码片段速查**（可直接抄）
6. 术语不懂 → **附录 C 术语速查**
7. 踩坑 → **附录 D 常见坑总表**
8. 准备面试 → **附录 E 面试高频问题速查**

**复习（已学完 Step 1 ~ 6）**
9. 先看 **「阶段 1 前半程回顾」**（在 Step 6 之后）—— 六步路线图 + 六个坑 → 六条判据 + 五条错误路径一览

---

## 目录

| 章节 | 内容 | 一句话定位 |
|------|------|-----------|
| Step 1 | HTTP 与 ASGI 地基 | 不搞懂这个，FastAPI 就是玄学 |
| Step 2 | 最小应用与自动文档 | 5 行代码换来一个交互式文档站 |
| Step 3 | 三段参数：路径 / 查询 / 请求体 | FastAPI 的核心"魔法"其实是类型注解 |
| Step 4 | pydantic 契约与 `response_model` | 输入校验 + 输出过滤 |
| Step 5 | 依赖注入 `Depends` | 阶段 0 手工注入的自动化版 |
| Step 6 | 错误处理与 `lifespan` | 统一错误体 + 启动/关闭逻辑 |
| Step 7 | 中间件与 CORS | 洋葱模型 / 前端跨域 |
| Step 8 | 异步的正确姿势 | `async def` 不是"更快"，是"不阻塞" |
| **Step 9** | **SSE 流式响应** ⭐⭐ | **LLM 应用的命门：首字延迟** |
| Step 10 | 数据库（SQLAlchemy 2.0 异步） | 会话历史存哪 |
| Step 11 | 配置 / 日志 / 安全 | API Key 绝不能进前端 |
| Step 12 | 测试 FastAPI | TestClient / ASGITransport / 依赖覆盖 |
| Step 13 | 部署 | uvicorn + Docker + 反向代理 |
| 回顾 | 聊天后端设计蓝图 | 把 13 步拼成一个可交付项目 |
| **前半程回顾** | **Step 1 ~ 6 走过的路线 + 六个坑 → 六条判据 + 五条错误路径** | **复习入口：先看这节** |
| **难点拓展** | 10 个关键问题的深入解释 | 含协议细节与算法 |
| 附录 A | 代码片段速查 | 可直接抄 |
| 附录 B | 数学背景 → 后端知识对照 | |
| 附录 C | 术语速查（人话版） | |
| 附录 D | 常见坑总表 | |
| 附录 E | 面试高频问题速查 | |

---

## 学习进度

**两列含义不同，别混**：`笔记状态` = 这份笔记该节内容是否已写好；`实操状态` = **本仓库是否真的动手做过**（对应 [学习过程记录.md](学习过程记录.md) 的流水编号）。

| Step | 主题 | 笔记状态 | 实操状态 |
|------|------|------|------|
| 1 | HTTP 与 ASGI 地基 | ✅ 已整理 | ✅ 已完成（1.2；新增 §1.4b / §1.4c 两组本仓库实测：并发三种命运、原始报文与状态码） |
| 2 | 最小应用与自动文档 | ✅ 已整理 | ✅ 已完成（1.1：`/health` + `/docs` + `/openapi.json` 实测 200） |
| 3 | 三段参数 | ✅ 已整理 | ✅ 已完成（1.3：4 条路由，15 组请求实测；提交 `19aa9cf` / `94fb0a2`） |
| 4 | pydantic 契约 | ✅ 已整理 | ✅ 已完成（输入契约 `ChatRequest`；输出契约：返回注解 + `response_model` 的取舍已实测；`ModelItem` / `ModelListResponse` 落地到 `/v1/upstream/models`，`/docs` 可展开。见 §4.5b） |
| 5 | `Depends` 依赖注入 | ✅ 已整理 | ✅ 已完成（流水 `1.4`~`1.4l`：`get_settings` / 覆盖机制 / `yield` 依赖 / 依赖缓存 / 嵌套 / 抽共用工厂 / 真实调上游；后又经 6.4 把 client 生命周期从请求级改为应用级） |
| 6 | 错误处理与 `lifespan` | ✅ 已整理 | ✅ 已完成（6.1~6.4：404 / 400 / 502 / 500+`request_id` / `AppError` 统一错误形状 / `lifespan` 共享 client；配套实测见 §6.1b~§6.1e、§6.3b、§6.4b） |
| 7 | 中间件与 CORS | ✅ 已整理 | ✅ 已完成（7a 请求 ID + 耗时中间件 / 7b CORS；含常量抽离与日志级别配置） |
| 8 | 异步正确姿势 | ✅ 已整理 | ✅ 已完成（`playground/blocking_demo.py`：1 慢 + 5 快并发，实测阻塞写法把快请求从 13ms 拖到 325ms，**差 25 倍**；另测线程池 40 上限是排队、GIL 下线程池对 CPU 密集无效 0.96x） |
| 9 | **SSE 流式** | ✅ 已整理 ⭐ | 🟡 进行中（**9a ✅** 假数据逐字 `GET /v1/chat/stream`，实测 TTFB 0.014s / total 1.85s、`chunked`、10 帧合法；**9b-1 ✅** 上游真实帧结构取证；**9b-2 ✅** 已改 `POST` + 真调上游 `stream=true`、只转发 `content`，实测 20 帧到达、首个内容帧 845.8ms；剩 9b-3~5：心跳 / `usage` / 流内错误 / 客户端断开） |
| 10 | 数据库 | ✅ 已整理 | ⬜ 未开始 |
| 11 | 配置/日志/安全 | ✅ 已整理 | 🟡 部分（配置已由阶段 0 的 `config.py` 解决；**日志已有基础**：`logging` + `request_id` + 堆栈只进 stderr（§6.3b），格式化 / 集中收集 / 密钥检查未做） |
| 12 | 测试 | ✅ 已整理 | ⬜ 未开始 |
| 13 | 部署 | ✅ 已整理（本机未装 Docker） | ⬜ 未开始 |

> ⚠️ **别把"笔记已整理"当成"学会了"** —— 这是本表的用途。笔记写得再全，只有"实操状态 ✅"才算真的做过。

---

## 全局地图

```mermaid
flowchart TB
    S1["1 HTTP / ASGI<br/>请求怎么进来的"] --> S2["2 最小应用<br/>路由 + 自动文档"]
    S2 --> S3["3 三段参数<br/>路径/查询/请求体"]
    S3 --> S4["4 pydantic 契约<br/>输入校验 + 输出过滤"]
    S4 --> S5["5 Depends<br/>依赖注入"]
    S5 --> S6["6 错误处理 + lifespan<br/>统一错误体"]
    S6 --> S7["7 中间件 / CORS<br/>洋葱模型"]
    S7 --> S8["8 异步正确姿势<br/>别阻塞事件循环"]
    S8 --> S9["9 SSE 流式 ⭐<br/>LLM 应用命门"]
    S5 --> S10["10 数据库<br/>会话历史"]
    S9 --> S11["11 配置/日志/安全"]
    S10 --> S11
    S11 --> S12["12 测试<br/>TestClient"]
    S12 --> S13["13 部署<br/>uvicorn + Docker"]
```

**心法**：

- **Step 1 是唯一"看起来不实用"但必须读的一步**：不搞清 HTTP 与 ASGI，后面全是"记住这个写法"
- Step 3 → 4 → 5 是一条线：**参数怎么进来（3）→ 怎么校验（4）→ 依赖怎么复用（5）**
- Step 6 → 7 → 8 是"服务能扛住"的三件事：**错误可控、横切逻辑集中、不阻塞**
- **Step 9 是你的岗位命门**：LLM 应用的体验 = 首字延迟（TTFT），不做流式等于产品不可用
- Step 12 → 13 是"能交付"：**测试锁行为，容器锁环境**

---

## 快速上手：5 分钟跑起来

```python
# main.py
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
```

```powershell
uv add fastapi uvicorn
uv run uvicorn main:app --reload
# 打开 http://127.0.0.1:8000/docs —— 你已经有交互式 API 文档了
```

> ⭐ 那行 `-> dict[str, bool]` 不是注释。**FastAPI 读的就是它**：类型注解 → JSON Schema → OpenAPI → `/docs` 页面。
> 这就是为什么阶段 0 要先把**类型注解**和 **pydantic** 学扎实 —— 在 FastAPI 里它们是功能，不是风格。

---

# Step 1 · HTTP 与 ASGI 地基

## 定位

> FastAPI 是一层**薄封装**。它把 HTTP 请求变成 Python 函数调用，再把返回值变成 HTTP 响应。
> 不理解这层，你就不明白"为什么函数签名能决定路由行为"。

## 1.1 一次请求发生了什么

```mermaid
sequenceDiagram
    participant C as 客户端 (浏览器/curl)
    participant D as DNS
    participant S as 服务器 (uvicorn)
    participant A as 你的代码
    C->>D: example.com 的 IP 是什么？
    D-->>C: 1.2.3.4
    C->>S: TCP 三次握手
    C->>S: TLS 握手（https）
    C->>S: POST /v1/chat/completions HTTP/1.1<br/>{...请求头...}<br/><br/>{...请求体...}
    S->>A: 解析成 (method, path, headers, body)
    A-->>S: 返回 (status, headers, body)
    S-->>C: HTTP/1.1 200 OK<br/>{...}
```

⭐ **关键认知**：**HTTP 是无连接的请求-响应模型**。
服务端**不记得**上一个请求是谁发的 —— "记住用户状态"这件事**必须你自己做**（Cookie / Token / 数据库）。

> 🧒 **类比**：HTTP 像"每次打电话都换一个陌生客服"，你必须在每通电话里自报家门（带 token）。
> 这就是为什么有 `Authorization` 头、有 session 表。

## 1.2 HTTP 报文结构

**请求**：

```http
POST /v1/chat/completions HTTP/1.1          ← 请求行：方法 + 路径
Host: api.example.com                        ← 请求头开始
Content-Type: application/json
Authorization: Bearer sk-xxx
Content-Length: 42
                                             ← 空行 = 头结束
{"messages":[{"role":"user","content":"hi"}]} ← 请求体
```

**响应**：

```http
HTTP/1.1 200 OK                              ← 状态行
Content-Type: application/json
                                             ← 空行
{"content":"你好"}                            ← 响应体
```

| 位置 | FastAPI 里对应什么 |
|------|------------------|
| 方法 + 路径 | `@app.post("/v1/chat/completions")` |
| 路径里的变量 | 路径参数（`/items/{item_id}`） |
| 查询串 `?limit=10` | 查询参数 |
| `Content-Type` | 决定请求体怎么解析 |
| 请求体 | pydantic 模型 |
| 响应状态码 | `status_code=` 或抛 `HTTPException` |

## 1.3 方法、状态码、幂等

| 方法 | 语义 | 幂等？ | 有请求体？ |
|------|------|-------|-----------|
| `GET` | 读取 | ✅ | 通常无 |
| `POST` | 创建 / 执行动作 | ❌ | 有 |
| `PUT` | 整体替换 | ✅ | 有 |
| `PATCH` | 局部更新 | ❌（通常） | 有 |
| `DELETE` | 删除 | ✅ | 通常无 |

> ⭐ **幂等 = 执行一次和执行 N 次，结果一样**。
> 为什么重要：网络会超时重试。**如果是 `POST /orders`，重试可能下两个单**！
> 所以支付类接口要配"幂等键"（idempotency key）。

**必须记住的状态码**：

| 码 | 含义 | 何时用 |
|----|------|-------|
| 200 | OK | 普通成功 |
| 201 | Created | POST 创建成功 |
| 204 | No Content | 成功但无返回体（如 DELETE） |
| 400 | Bad Request | 请求本身有问题 |
| 401 | Unauthorized | **没登录**（没带/带错凭证） |
| 403 | Forbidden | **登录了但没权限** |
| 404 | Not Found | 资源不存在 |
| **422** | **Unprocessable Entity** | ⭐ **参数校验失败（FastAPI 默认）** |
| 429 | Too Many Requests | 限流 |
| 500 | Internal Server Error | 服务端 bug |

> ⭐ **401 vs 403 的区别**（高频面试题）：
> 401 = "你是谁？"（未认证）；403 = "我知道你是谁，但你不能这么做"（未授权）。
>
> ⭐ **为什么 FastAPI 用 422 而不是 400**：400 是"请求格式就是错的"；422 是"格式对，但内容不合法"。
> pydantic 校验失败属于后者。细节见 **难点拓展 7**。

## 1.4 WSGI vs ASGI ⭐

**同步服务（WSGI）的工作方式**：

```text
一个请求 = 一个线程（或进程）
线程在等待 IO 时被操作系统挂起，什么也干不了
1 万个并发连接 → 需要 1 万个线程 → 内存爆炸
```

**异步服务（ASGI）的工作方式**：

```text
一个事件循环 + N 个协程
协程 await 时主动让出 → 循环去推进其他协程
1 万个并发连接 → 1 个（或几个）线程就够
```

| | WSGI | ASGI |
|---|------|------|
| 代表框架 | Flask、Django（传统） | **FastAPI / Starlette**、Django 3+ |
| 接口签名 | `def app(environ, start_response)` | `async def app(scope, receive, send)` |
| 并发模型 | 线程/进程 | 事件循环 |
| 支持 WebSocket | ❌ | ✅ |
| 支持 SSE 长连接 | 勉强（占线程） | ✅ 原生 |
| 适配的服务器 | gunicorn、uwsgi | **uvicorn**、hypercorn |

> ⭐ **对你的岗位意味着什么**：LLM 应用是"**长等待、多并发**"的典型场景。
> 一个 LLM 请求要 5~30 秒，WSGI 下 100 个用户就要 100 个线程全部挂在那里等；
> ASGI 下单线程就能扛住，**这就是选 FastAPI 的根本原因**（不是"因为它新"）。

### 1.4b 本仓库实测：三种写法的并发命运 ⭐⭐（2026-10-14）

> ⚠️ **说明**：下面的数字来自一个**临时演示应用**（写在系统临时目录、实验后已删除），
> **不是本项目 `src/app/api/app.py` 里的代码** —— 我们的应用目前**只有 `/health` 一条路由**。
> 造临时应用的原因：要量出"三种写法"的差别，就需要三条**只在等待方式上不同**的路由，`/health` 演示不了。
> 下表里的 `/async-sleep`、`/sync-def`、`/blocking-async` 都是那个临时应用的路由名，**本项目里不存在**。

> 上表是"讲道理"，这里给**量出来的数字**。用真实 uvicorn 起一个小应用，三条路由**内部都等 1 秒**，
> 唯一区别是写法；然后同时打 **8 个并发请求**。

| 路由写法 | 8 个并发的总耗时 | 结论 |
|---|---|---|
| `async def` + `await asyncio.sleep(1)` | **1.08 秒** | ✅ 理想：`await` 让出控制权，8 个请求重叠等待 |
| `def`（无 async）+ `time.sleep(1)` | **1.04 秒** | ⚠️ 不阻塞，但**代价是占线程** —— Starlette 把它丢进**线程池**（`anyio.to_thread`，默认上限约 40） |
| ⚠️ `async def` + `time.sleep(1)` | **8.03 秒** | ❌ **完全串行**：阻塞调用把事件循环的**唯一线程**按住了 1 秒 × 8 |

⭐ **最反直觉的结论：`async def` 里调用阻塞函数，比干脆写成 `def` 还糟。**

| 写法 | 谁在执行 | 阻塞谁 |
|---|---|---|
| `def` + 阻塞调用 | 线程池里的**一个线程** | 只占那一个线程 |
| `async def` + 阻塞调用 | **事件循环的唯一线程** | **整个服务**（所有请求一起等） |

**为什么**：`async def` 是对事件循环的**承诺**——"我在等待时会让出"。而 `time.sleep` / `requests.get` / 同步数据库驱动 / 大文件读 / 大计算**都不会让出**。许了做不到的承诺，被坑的是**所有其他请求**。

> ⚠️ **识别法**：看到 `async def` 里出现 `requests` / `time.sleep` / 同步 DB 驱动 / 大计算 → 立刻怀疑"这行会阻塞多久？"
> 这正是本项目选 `httpx`（异步）而非 `requests`、Step 10 要用 `aiosqlite` / `asyncpg` 的原因。

**WSGI 的线程账（1000 个并发、每个等 20 秒）**：

| | WSGI | ASGI |
|---|---|---|
| 一个请求占什么 | 一个线程/进程 | 一个协程（仅几个 Python 对象） |
| 1000 并发等待 | 需要 **1000 个线程**同时挂着，每线程栈约 1 MB → **≈ 1 GB 光栈**（典型值） | **1 个线程** + 1000 协程 → **几十 MB** |
| 额外开销 | 线程上下文切换与调度 | 协程切换是纯内存操作，几乎为零 |

**再叠加 SSE（Step 9）**：一个流式回答要占住连接 30 秒以上。WSGI 下一个 SSE 连接**占一个线程 30 秒**；ASGI 下这些协程在 `await` 时全部让出。

⭐ **一句话：同步模型里"等待"要占着一个工人；异步模型里"等待"是免费的。**

### 1.4c 本仓库实测：报文与状态码

**原始 HTTP 报文（用裸 socket 服务器抓 httpx 的真实字节）**：

```http
GET /health HTTP/1.1                      ← 请求行：方法 + 路径 + 版本
Host: 127.0.0.1:8138                      ← 以下 5 行都是 httpx 自动加的
Accept: */*
Accept-Encoding: gzip, deflate
Connection: keep-alive
User-Agent: python-httpx/0.28.1
                                          ← 空行 = 头结束
                                          ← 正文（GET 无）
```

```http
HTTP/1.1 200 OK                           ← 状态行
Content-Type: application/json
Content-Length: 15
                                          ← 空行
{"status":"ok"}                           ← 正文，正好 15 字节
```

| 观察 | 含义 |
|---|---|
| `Connection: keep-alive` + **同一条连接上成功发了两个请求** | HTTP/1.1 默认**复用连接** → 这就是客户端要维护**连接池**、要 `async with` 关闭的原因 |
| `Content-Length` **必须与正文长度精确一致** | 写错（如声明 20 只发 15）→ 客户端一直等剩下 5 字节，**两端都不报错**，界面永久转圈 |

**状态码实测**：

> ⚠️ **同样是那个临时演示应用**（已删除，见 §1.4b 开头的说明）。其中 `/items/{item_id}` 与
> `/no-such-path`、`POST /health` 是为了"造出 404 / 405 / 422"而特意写的，**本项目里不存在**。
> 本项目目前只有 `/health` 一条自定义路由（FastAPI 另白送 4 条：`/docs`、`/redoc`、`/openapi.json`、`/docs/oauth2-redirect`）。

```text
GET  /health        -> 200    正常（⭐ 本项目的真实路由）
GET  /items/42      -> 200    item_id: int，42 可转整数        ← 临时应用
GET  /items/abc     -> 422    内容不合法（格式没坏）           ← 临时应用
GET  /no-such-path  -> 404    路径未注册                       ← 临时应用
POST /health        -> 405    路径存在但方法不对                ← 临时应用
（无人监听的端口）   -> 无状态码，抛 ConnectError：连接都没建立
```

| 家族 | 口诀 | 实测例 |
|---|---|---|
| 2xx | 事办成了 | 200 |
| 3xx | 去那边找（⚠️ httpx 默认 `follow_redirects=False`，**不会自动跟**） | — |
| **4xx** | **你的问题（调用方）** | 401 / 404 / 405 / 422 |
| **5xx** | **我的问题（服务端）** | 500 |

> ⭐ **排查第一刀**：看到 4xx 就别翻服务端日志找 bug，先看**自己传了什么**。

**ASGI 接口长什么样**（看懂了就明白 FastAPI 在干什么）：

```python
async def app(scope, receive, send):
    # scope: 类似请求元信息（method/path/headers）
    # receive: 异步取请求体（可多次，用于流式上传）
    # send: 异步发响应（可多次，用于流式返回！）
    ...
```

> ⭐ 注意 `send` 可以被**调用多次** —— 这就是 SSE / WebSocket 能在 ASGI 上工作的原因。
> **WSGI 的 `start_response` 只能调一次**，所以同步框架做流式很别扭。

## 1.5 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 1 HTTP 与 ASGI）。

### 1.5b 自检批改（2026-10-14 学习者作答后订正）⭐

> 📋 **批改结论与三处订正已并入 [自检题清单.md](自检题清单.md)**（阶段 1 · Step 1 里标 🟡 的三题）。
> 📎 订正所用的实测数据仍在上面 §1.4b / §1.4c（并发三种命运、报文与状态码）—— 复习时值得回看。

---

# Step 2 · 最小应用与自动文档

## 2.1 三行起一个服务

```python
from fastapi import FastAPI

app = FastAPI(title="chat-backend", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
```

| 部分 | 作用 |
|------|------|
| `FastAPI(...)` | 应用实例（`title`/`version` 会出现在文档页里） |
| `@app.get("/health")` | **路径操作装饰器**：把函数注册到 `GET /health` |
| `async def health()` | 处理函数；可 `async` 也可同步（差别见 Step 8） |
| `-> dict[str, bool]` | **响应类型** → 决定文档与序列化 |

## 2.2 `uvicorn main:app` 这个参数怎么读

```powershell
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

| 部分 | 含义 |
|------|------|
| `main:app` | 模块 `main.py` 里的变量 `app`（**import 路径:属性名**） |
| `--reload` | 改代码自动重启（**仅开发用**，生产绝不能用） |
| `--host 0.0.0.0` | 允许外部访问（默认 `127.0.0.1` 只能本机访问） |
| `--port` | 端口 |
| `--workers N` | 多进程（生产用，见 Step 13） |

> ⚠️ `main:app` 是 **import 路径**，不是文件路径。
> 如果应用在 `src/app/main.py` 里，且项目根在 `sys.path` 上，就是 `app.main:app`。
> **写错了报 `ModuleNotFoundError` 或 `AttributeError: module has no attribute 'app'`。**

## 2.3 白送的三个端点 ⭐

FastAPI 自动生成：

| 端点 | 内容 |
|------|------|
| `/docs` | **Swagger UI**（可交互，能直接在页面发请求） |
| `/redoc` | ReDoc（另一种风格的文档） |
| `/openapi.json` | 机器可读的 OpenAPI 3 规范 |

**实测验证**：

```text
$ curl -s -o NUL -w "docs: %{http_code}\n" http://127.0.0.1:8123/docs
docs: 200

$ curl -s http://127.0.0.1:8123/openapi.json | ...
{"info": {"title": "verify", ...}, "paths": {"/chat": {...}, "/health": {...}}}
```

> ⭐ **这对 LLM 应用有额外价值**：你的后端要暴露给前端 / 别的 Agent 调用。
> 有 OpenAPI，对方可以直接生成客户端代码，**不用你写接口文档**（而且它永远和代码同步）。
>
> 🧒 **类比**：等于"你写完函数，文档自动生成且不会过期"。手写 API 文档最大的问题就是**它会过期**。

## 2.4 路由参数的顺序陷阱 ⚠️

```python
@app.get("/users/me")
async def me(): ...

@app.get("/users/{user_id}")
async def get_user(user_id: str): ...
```

**顺序必须这样**！如果把 `/{user_id}` 放前面，请求 `/users/me` 会**先匹配到** `/{user_id}`，
于是 `user_id="me"` —— 这是新手最常见的 404/类型错误来源。

> ⭐ **规则**：**具体路径写在参数化路径之前**。FastAPI 按注册顺序匹配。

## 2.5 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 2 最小应用与文档）。

---

# Step 3 · 三段参数：路径 / 查询 / 请求体

## 定位

> FastAPI 最"反直觉"又最省事的地方：**它从函数签名推断出参数从哪来**。
> 这一段讲清推断规则，之后你看任何 FastAPI 代码都能一眼看懂。

## 3.1 三类参数的位置

```text
POST /v1/items/42?verbose=true&limit=10
                 ↑              ↑        ↑
              路径参数        查询参数   查询参数
请求体：{"name": "apple"}   ← 请求体参数
```

```python
@app.post("/v1/items/{item_id}")
async def update_item(
    item_id: int,                                    # ← 路径参数（出现在路径里）
    verbose: bool = False,                           # ← 查询参数（标量 + 有默认值）
    limit: int = 10,                                 # ← 查询参数
    payload: ItemIn = ...,                           # ← 请求体（pydantic 模型）
) -> ItemOut: ...
```

## 3.2 FastAPI 的判定规则 ⭐

| 参数类型 | 位置 | 例子 |
|---------|------|------|
| 出现在路径 `{}` 里的名字 | **路径参数** | `item_id: int` |
| **pydantic 模型** / `dict` / `list[模型]` | **请求体** | `payload: ItemIn` |
| 其余**标量**（`int`/`str`/`bool`/`float`） | **查询参数** | `limit: int = 10` |

> 🧒 **一句话**：**"路径里有的算路径，复杂对象算 body，剩下的算查询串。"**
> 记住这条，你就能读懂任何 FastAPI 路由签名。

## 3.3 路径参数

```python
@app.get("/items/{item_id}")
async def get_item(item_id: int) -> dict[str, int]:
    return {"item_id": item_id}
```

**实测行为**：

| 请求 | 结果 | 说明 |
|------|------|------|
| `GET /items/5` | `200 {"item_id": 5}` | ⭐ `"5"` **自动转成** `5`（类型转换） |
| `GET /items/abc` | **`422`** | 转不成 int → 校验失败，**不是 500** |
| `GET /items/404` | 取决于你的代码 | 抛 `HTTPException` 才返回 404 |

> ⭐ **这就是"类型即校验"**：你只写了 `int`，就同时得到了
> **文档里的类型说明 + 运行时转换 + 转换失败的自动 422**。零额外代码。

**带校验的路径参数**：

```python
from typing import Annotated
from fastapi import Path

@app.get("/items/{item_id}")
async def get_item(item_id: Annotated[int, Path(ge=1, le=1000)]) -> dict[str, int]:
    return {"item_id": item_id}
```

## 3.4 查询参数

```python
@app.get("/items")
async def list_items(
    skip: int = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Annotated[str | None, Query(max_length=50)] = None,
) -> dict[str, object]:
    return {"skip": skip, "limit": limit, "q": q}
```

| 写法 | 含义 |
|------|------|
| `limit: int = 10` | 可选，默认 10 |
| `limit: int`（无默认值） | **必填**查询参数，缺了 → 422 |
| `q: str \| None = None` | 可选，可以是 None |
| `Annotated[int, Query(ge=1, le=100)]` | 带范围约束 |

**实测：约束真的会拦**：

```text
$ curl "http://127.0.0.1:8123/health?limit=0"
HTTP 422        ← Query(ge=1) 拦住了
```

> ⚠️ **`bool` 查询参数的坑**：`?flag=true` / `?flag=1` / `?flag=yes` 都能解析，
> 但 `?flag=false` **是 False**，而 `?flag=` （空值）**会报 422**。
> 前端传参时务必注意"空字符串 ≠ 布尔值"。

## 3.5 请求体

```python
from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[MessageIn] = Field(min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False


@app.post("/v1/chat")
async def chat(req: ChatRequest) -> dict[str, str]:
    return {"content": req.messages[-1].content}
```

> ⭐ **一个请求体参数 = 一个 pydantic 模型**。校验、默认值、文档全部来自阶段 0 学的那些能力。
> **阶段 0 的 pydantic 在这里直接变成"接口契约"** —— 这是两个阶段之间最自然的衔接点。

**多个请求体参数**（少见但要知道）：

```python
@app.post("/multi")
async def multi(a: ItemIn, b: UserIn) -> None:
    ...
    # 请求体变成 {"a": {...}, "b": {...}}   ← 自动加了字段名做 key
```

## 3.6 `Annotated` 为什么是现在的推荐写法 ⭐

**旧写法（过渡期）**：

```python
async def list_items(limit: int = Query(default=10, ge=1, le=100)): ...
```

**新写法（推荐）**：

```python
LimitParam = Annotated[int, Query(ge=1, le=100)]

async def list_items(limit: LimitParam = 10): ...
```

| 优势 | 说明 |
|------|------|
| **可复用** | `LimitParam` 定义一次，多处使用 |
| **默认值就是默认值** | 不用塞进 `Query(default=...)`，签名更干净 |
| **类型仍是真的 int** | 函数体内 `limit` 就是 `int`，mypy 开心，IDE 补全正常 |
| **静态检查友好** | 旧写法的默认值是 `QueryInfo` 对象，mypy 常要 ignore |

> ⭐ **FastAPI 官方从 0.95 起推荐 `Annotated`**。看到旧写法不用慌，但新代码一律用 `Annotated`。

### 3.6b 本仓库实测：1.3 的 4 条路由（2026-10-15）

> ✅ **代码在 [`src/app/api/app.py`](../src/app/api/app.py)**（本项目真实文件，非临时演示）。
> 验证方式：用 `httpx.ASGITransport` 直接打 `app`（不启服务、不占端口）。

**实装的 4 条路由**：

| 路由 | 演示哪种参数 | 要点 |
|---|---|---|
| `GET /v1/models` | **查询参数** | `prefix` 可选（前缀过滤）、`limit` 可选（默认 20） |
| `GET /v1/models/latest` | 无参数（固定路径） | ⚠️ **必须写在 `{model_name}` 之前**（见 2.4 的顺序陷阱） |
| `GET /v1/models/{model_name}` | **路径参数** | 路径里的 `{model_name}` 与参数名**必须一字不差** |
| `POST /v1/chat` | **请求体** | 参数类型是 `ChatRequest`（pydantic 模型）→ 判定为 JSON body |

**15 组请求实测结果**：

```text
GET  /health                         -> 200  {"status":"ok"}
GET  /v1/models                      -> 200  {"total":2,"items":["deepseek-flash","deepseek-v4-pro"]}
GET  /v1/models?limit=1              -> 200  {"total":2,"items":["deepseek-flash"]}
GET  /v1/models?prefix=deepseek-v4   -> 200  {"total":1,"items":["deepseek-v4-pro"]}   ← 前缀过滤生效
GET  /v1/models?prefix=flash         -> 200  {"total":0,"items":[]}
GET  /v1/models?limit=abc            -> 422  loc=['query','limit'] type=int_parsing     ← ⭐ 自动拦截
GET  /v1/models/latest               -> 200  {"model_name":"deepseek-flash"}            ← 固定路径优先
GET  /v1/models/deepseek-v4-pro      -> 200  {"model_name":"deepseek-v4-pro"}           ← 路径参数
POST /v1/chat {"messages":[{"role":"user","content":"你好"}]}
                                     -> 200  {"content":"[echo] 你好","model":"deepseek-flash"}
POST /v1/chat {"messages":[]}        -> 422  loc=['body','messages'] type=too_short     ← ⭐ min_length=1 生效
POST /v1/chat {"messages":[{"role":"tool",...}]}
                                     -> 422  loc=['body','messages',0,'role'] type=literal_error  ← ⭐ Literal 生效
```

⭐ **最后两组是"阶段 0 的 `schemas.py` 开始干活"的证据**：`Field(min_length=1)` 与 `Literal["system","user","assistant"]`
变成了**自动的请求校验**，我们**一行校验代码都没写**。

**⚠️ 三个"工具抓不到、只能实测发现"的坑**：

| 坑 | 现象 | 谁来发现 |
|---|---|---|
| `prefix: str \| None` **漏写 `= None`** | `/v1/models` 直接 **422 `Field required`** —— `str \| None` 只说"能装空"，不等于"可以不传" | ❌ ruff / ❌ mypy / ✅ **打请求** |
| `?limit=0` | 200，但 `items` 为空 | 同上 |
| `?limit=-1` | 200，返回 `["deepseek-flash"]` ⛔ **负索引切片**（`matched[:-1]` = "去掉最后一个"），**静默给出错误结果** | 同上 |

**修法**：给 `limit` 加约束（`Query(ge=1, le=100)`），让 `0` / `-1` / `101` 都被 422 拦下：

```python
limit: Annotated[int, Query(ge=1, le=100, description="最多返回几条")] = 20
```

**⚠️ 第四个坑：多余字段被静默忽略。**

```text
POST /v1/chat {"messages":[...], "extra":1}  ->  200  ✅（没报错！）
```

原因：pydantic `BaseModel` **默认 `extra="ignore"`** —— ⚠️ **与 `config.py` 里特意设的 `extra="forbid"` 相反**。

| 模型 | 设置 | 客户端多传字段 |
|---|---|---|
| `Settings`（配置） | `extra="forbid"`（故意选的） | 报错 |
| `ChatRequest`（数据契约） | **默认 `ignore`** | **静默忽略** |

⭐ **这意味着**：客户端把 `max_token`（少个 `s`）发过来，服务端会**默默用默认值**，两边都以为没问题 —— 又一处**静默失效**。
**要不要改成 `forbid` 是真实取舍**（严格能挡拼写错误，但客户端多传就 422），Step 4 正式讨论。

**⭐ 顺便：`mypy` 在本步抓到了一个会变成 500 的 bug**（详见 [学习过程记录](../study_notes/学习过程记录.md)）：

```text
src\app\api\app.py:65: error: "ChatRequest" has no attribute "message"; maybe "messages"?  [attr-defined]
```

`request.message`（少一个 `s`）**语法合法、`ruff` 也通过**，但运行时会抛 `AttributeError` → FastAPI 回 **500**。
**mypy 静态抓到它并直接给出正确拼写** —— 这正是"给数据模型写注解"的额外红利：**字段名拼写检查**。

### 3.6c ⚠️ 用 PowerShell 测中文接口的两个坑（2026-10-15 实测）⭐⭐

> 背景：用 `Invoke-RestMethod` 打 `/v1/chat` 传中文，结果回声是 `[echo] ??` —— **请求返回 200，但数据已经坏了**。

**两个独立的问题，必须分开判断**（判据：**看服务端实际收到的字节**，不能靠肉眼看终端）：

| # | 坑 | 现象 | 实测证据（服务端返回的原始字节） |
|---|---|---|---|
| 1 | **发**：`-Body "<含中文的字符串>"` | 中文被替换成 `?`，**请求侧真实损坏**，且返回 200 | 字节为 `3F-3F`（`??`） |
| 2 | **收**：PowerShell 显示响应时按 Latin-1 解码 | 看到 `ä½ å¥½` —— **只是显示乱码，数据是对的** | `-InFile` 时收到的是 `E4-BD-A0-E5-A5-BD`（`你好` 的正确 UTF-8） |

**三种发法实测对照**：

| 发法 | 服务端收到的中文 | PowerShell 显示 |
|---|---|---|
| `-Body '{"c":"你好"}'`（中文写在命令里） | ❌ `??`（损坏） | `??` |
| `-Body $utf8Bytes`（先转 UTF-8 字节数组） | ✅ 正确 | 乱码（显示问题） |
| `-InFile <UTF-8 文件>` | ✅ 正确 | 乱码（显示问题） |
| **Python `httpx`** | ✅ 正确 | ✅ **正确** |

**实践结论**：

```text
① 只想验证"接口逻辑对不对" → 用纯 ASCII 内容（hello / test），最省事
② 用 PowerShell 传中文 → 必须用 -InFile 或 UTF-8 字节数组（别把中文写在命令里）
③ 要"发和收都正确" → 改用 Python httpx（本项目已装）
④ 看到乱码先分清病因：是"发的时候坏了"（`??`）还是"只是显示坏了"（`ä½ å¥½`）
```

> ⭐ **这是本项目第 N 次编码坑**（前有 `.python-version` 的 BOM、`Get-Content` 按 GBK 读、中文经管道喂给 ruff）。
> **共同规律：Windows 上凡涉及"非 ASCII 文本进出命令行工具"，都要显式指定 UTF-8，并用字节级证据验证。**
>
> ⚠️ 附带一条能力边界：**注释 / docstring 里的英文单词拼错，没有任何工具能抓**
> （ruff / mypy 都不查拼写）。这与**属性名**拼错形成对比 —— 后者 mypy 的 `attr-defined` 能抓。

### 3.6d 当前已知待办（2026-10-15 工作区体检发现，归属到后续 Step 再修）⭐

> 这 3 条**不是"忘了改"，是刻意留到对应 Step 一起做** —— 避免零散打补丁、每处都有自己的归属。

| # | 现状（实测） | 问题 | 归属 |
|---|---|---|---|
| 1 | `GET /v1/models/this-model-does-not-exist` → **200** `{"model_name":"this-model-does-not-exist"}` | 不存在的模型**返回 200**，接口"假装查到了"。应 **404** | **Step 6**（`HTTPException`） |
| 2 | `POST /v1/chat {"messages":[{"role":"assistant",...}]}` → **200** 把"模型以前说的话"当答案回显 | **不检查最后一条是谁说的**（`system` / `assistant` 也会被回显） | **Step 4 / 6** |
| 3 | `/v1/models/latest` 返回 `KNOWN_MODELS[0]`（硬编码） | 与 `settings.llm_model` **无关联**：改配置时两处会不一致 | **Step 4**（接真实上游 `/models`） |
| 4 | ~~`deps.py` 的 `get_llm_client()` 与 `main.py` 的 `create_client()` 的三行构造参数刻意重复~~ | ✅ **已解决**（`f53c6dc`）：抽出 `src/app/llm_client.py` 的 `create_llm_client()` 两边共用 | **已完成** |
| 5 | client 的**生命周期**该跟着请求还是跟着应用（实测每请求新建比共享慢 **2.23 倍**：51.3ms vs 23.0ms / 200 次） | 当前"每请求新建"是**教学选择**（为了看清 `yield` 的 setup/teardown），不是性能最优；共享一个 `AsyncClient` 实测并发 20 请求全 200 安全 | **1.4d** 决定：请求级用 `yield` 依赖，应用级用 `lifespan`（Step 6） |
| 6 | `/v1/upstream/models` 上游出错时**返回 500**（`raise_for_status()` 抛 `httpx.HTTPStatusError`，不是 `HTTPException`） | 应转成 **502 Bad Gateway**（"上游错了"不是"我们错了"）；并区分 4xx（上游拒绝=我们的凭证问题）与 5xx（上游故障） | **Step 6**（错误处理） |

⭐ **为什么要显式记"待办"而不是记"已知缺陷"**：缺陷清单会越积越长、没人管；**待办有归属** ——
每条都写明"留给哪个 Step 修"，到那一步自然会被处理（这是"一次只解决一类问题"的具体做法）。

### 3.6e `POST /v1/chat` 逐行解剖（2026-10-15，配 4 组实测）⭐

> 提出问题："这 5 行到底是在干什么、怎么做的"。为了不靠背诵、靠事实回答，
> 做了 4 组实测。**探针均为内存里临时搭的 app（`TestClient`），不写任何文件，
> 不属于本项目；命令原样可复现**（见规范 §4.2b）。

#### ① `@app.post("/v1/chat")` 是"登记动作"，不是"运行时行为"

打印 `app.routes` 的实测结果：

| 类型 | 路径 | 方法 | name |
|---|---|---|---|
| `Route` | `/openapi.json`、`/docs`、`/docs/oauth2-redirect`、`/redoc` | `{'HEAD','GET'}` | 框架白送 |
| `APIRoute` | `/health` | `{'GET'}` | `health` |
| `APIRoute` | `/v1/models` | `{'GET'}` | `list_models` |
| `APIRoute` | `/v1/models/latest` | `{'GET'}` | `latest_model` |
| `APIRoute` | `/v1/models/{model_name}` | `{'GET'}` | `get_model` |
| `APIRoute` | `/v1/chat` | `{'POST'}` | `chat` |

⭐ **两个新事实**：
1. **框架白送的 4 条是 `Route`，自己写的是 `APIRoute`** —— 后者才是"带自动校验 + 自动文档"的那个类；
2. `name` 列**就是函数名**。所以函数名不是随便起的：改函数名，`/docs` 上的接口标题跟着变。

#### ② 返回类型注解 `-> ChatResponse` **等价于 `response_model`，并且会过滤字段**

实测（探针）：让一个模型在 `ChatResponse` 之上多带一个 `secret` 字段，返回 `"TOP-SECRET"`：

| 函数签名 | 实际返回的 JSON |
|---|---|
| `def a() -> ChatResponse:`（**有**注解） | `{'content':'hi','model':'m','usage_tokens':0}` |
| `def b():`（**无**注解） | `{'content':'hi','model':'m','usage_tokens':0,'secret':'TOP-SECRET'}` |

⭐ **`secret` 被剥掉了**。结论：**返回注解不是注释，是"返回值合同"** ——
它既是 `/docs` 里 200 响应的 schema（实测 `200 → $ref ChatResponse`），
也**真的会拦截未声明字段**。所以"随手不写返回类型"在 FastAPI 里是有风险的。

#### ③ `or` 按「真值」判断，不是按「是否为 None」（实测 5 种输入）

| 请求里的 `model` | `req.model` | 最终 model |
|---|---|---|
| 没写 | `None` | `deepseek-flash`（回落配置） |
| `null` | `None` | `deepseek-flash` |
| `""` | `""` | `deepseek-flash` ⚠️ **空字符串算"假"，也被兜掉** |
| `"deepseek-v4-pro"` | `"deepseek-v4-pro"` | `"deepseek-v4-pro"` |
| `"0"` | `"0"` | `"0"`（非空字符串算"真"） |

⭐ **规则**：`""` / `0` / `[]` / `{}` / `None` 都算假。`or` 适合"兜底默认值"，
但会连空字符串一起兜。若要求"只有明确没填才兜底"，须写
`request.model if request.model is not None else settings.llm_model`。

#### ④ 校验发生在你的函数体**之前**（实测）

探针在函数体里放了一条"被调用就留痕"的语句，然后发 1 个合法 + 3 个非法请求：

| 阶段 | 函数被执行次数 |
|---|---|
| 1 个合法请求后 | **1** |
| 再发 3 个非法请求后 | **仍然是 1** |

⭐ **3 个非法请求一次都没进函数体**，全被挡在门外返回 422（响应体只有 `['detail']` 一个键）。
那 3 个请求分别触发 `too_short` / `literal_error` / `list_type` —— **同一个 422 后面是三种不同规则**。
另：OpenAPI 里的 `422: HTTPValidationError` **不是手写的**，是 FastAPI 检测到"有请求体"后自动加的。

⭐ **教学结论**：把校验写进契约（`min_length=1`）之后，函数体里那句 `messages[-1]`
**不需要任何越界防御** —— 空列表根本到不了这一行。这是"契约时代替防御代码"的具体收益。

### 3.6f `Annotated` 与 `Query` 分别干嘛（2026-10-15 实测）⭐

> **完整实测与对照表见 [工具与依赖速查.md](工具与依赖速查.md) §7「`Annotated` 与 `Query` 的分工」**
> —— 这里只留"必须记住"的部分，避免同一事实抄两遍（规范 §12.1）。

**一句话分工**：`Annotated` 是**信封**（`typing` 标准库，只会"装"，不解释任何元数据）；
`Query` 是**信封里那张纸**（`fastapi`，是 FastAPI 认识的词汇，管约束 + 文档）。

**四条必须记住的实测结论**：

1. **`Query` 是 pydantic `FieldInfo` 的子类** → `ge=1` 经它转成 pydantic 元数据
   （`Query(ge=1).metadata` = `[Ge(ge=1)]`；`Query(ge=1).ge` 根本不存在）→ 真正执行约束的是 **pydantic 引擎**。
2. **为什么要 `Annotated`**：老写法 `limit: int = Query(20, ge=1)` 生成的 OpenAPI 与新的**完全一样**，
   但它把"默认值"位置**征用**了 —— 于是 `inspect.signature` 拿到的默认值是 `Query(20)` 而不是 `20`，
   **直接调用函数（单元测试就这么干）会 `TypeError`**。`Annotated` 把"元数据"和"默认值"两个位置**分开**。
3. **`Query()` 不负责"决定它是查询参数"**：`async def plain(n: int)` 什么都不加，OpenAPI 里也是 `in: query`。
   `Query()` 只加**约束和文档**。
4. **`required` 由"有没有默认值"决定，不由 `Query` 决定**：
   `x: Annotated[str | None, Query(...)]`（**没有** `= None`）→ `required: true` → 不带参数请求直接 **422**。
   ⚠️ **这正是本项目踩过的坑**：`str \| None` 只说"能装 None"，**不等于"可以不传"**。

**怎么读你自己的这行**：

```python
limit: Annotated[int, Query(ge=1, le=100, description="最多返回几条")] = 20,
#      └ Annotated 内 ────────────────────────────────┘  └ Annotated 外 ┘
#        类型 int  +  Query 指令（约束+文档）              默认值 → 决定"可选"
```

## 3.7 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 3 三段参数）。

---

# Step 4 · pydantic 契约与 `response_model`

## 定位

> 输入用 pydantic 校验；**输出也要用 pydantic 约定** —— 因为输出的风险是**泄露**。

## 4.1 输入契约

同 Step 3.5。核心是：**校验在进入业务逻辑之前完成**（阶段 0 的结论）。

## 4.2 校验失败时到底返回什么

**实测原始响应**（`POST /chat`，body 为 `{"messages":[]}`）：

```http
HTTP 422 Unprocessable Entity

{
  "detail": [
    {
      "type": "too_short",
      "loc": ["body", "messages"],
      "msg": "List should have at least 1 item after validation, not 0",
      "input": [],
      "ctx": {"field_type": "List", "min_length": 1, "actual_length": 0}
    }
  ]
}
```

**逐字段解读**：

| 字段 | 含义 | 用途 |
|------|------|------|
| `type` | 错误类型码 | 前端可据此做 i18n |
| **`loc`** | **错误位置路径** | ⭐ `["body","messages"]` = body 下的 messages 字段 |
| `msg` | 人类可读信息 | 直接展示给用户（英文！见下） |
| `input` | 实际收到的值 | ⚠️ **可能含敏感数据，注意别原样回显** |
| `ctx` | 约束上下文 | 调试用 |

> ⭐ **`loc` 是嵌套路径**：如果是 `messages[0].content` 不合法，`loc` 会是
> `["body", "messages", 0, "content"]` —— **精确到第几条消息的哪个字段**。
> 这是 pydantic 递归校验带来的直接好处。

> ⚠️ **两个注意点**：
> 1. `msg` 是**英文**的。面向中文用户的产品需要自定义错误响应（见 Step 6 的异常处理器）。
> 2. `input` 会把用户传的数据**原样回显**。如果请求体里含密码/token，你可能不希望它出现在响应里 —— 生产环境通常要**改写 422 响应体**。

## 4.3 `response_model`：输出也要管 ⭐

```python
class UserOut(BaseModel):
    id: int
    name: str
    email: str


class UserDb(BaseModel):          # 内部模型（含敏感字段）
    id: int
    name: str
    email: str
    password_hash: str
    internal_note: str


@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int) -> UserDb:
    return db.get_user(user_id)   # 返回的是 UserDb（含密码哈希！）
```

**实测：`response_model` 真的会过滤**：

```python
# 被测函数返回 ChatResponse(content=..., model=..., usage_tokens=...)
# 但 response_model 只声明了三个字段里的一部分时，多余字段被剔除

r = client.post("/chat", json={...})
assert set(r.json()) == {"content", "model", "usage_tokens"}   # ✅ 实测通过
```

| 作用 | 说明 |
|------|------|
| **字段过滤** | 只暴露 `response_model` 里声明的字段 → **防泄露** |
| **类型转换** | `datetime` → ISO 字符串；`Decimal` → 字符串 |
| **文档** | 响应 schema 出现在 `/docs` |
| **校验** | 返回值不符合模型会报错（说明你的代码有 bug，**早发现**） |

> ⭐ **这是 FastAPI 最被低估的安全特性**：
> 你可以在内部模型里随便加字段，**只要 `response_model` 没声明，它就不会出去**。
> 反过来说：**不加 `response_model` 就等于把内部模型的所有字段暴露给客户端**。
>
> 🧒 **类比**：`response_model` 是"出门前检查口袋"的白名单机制 —— 只放行清单上的东西。

**常见变体**：

| 写法 | 场景 |
|------|------|
| `response_model=UserOut` | 标准 |
| `response_model=list[UserOut]` | 列表（实测通过） |
| `response_model=UserOut \| None` | 可能返回 null |
| `response_model_exclude_none=True` | 省略值为 None 的字段 |
| `response_model_exclude_unset=True` | 只输出被显式赋值的字段 |
| `return {"..."} ` 直接写 dict | 也可以，但**没有过滤保护**（不推荐） |

## 4.4 状态码指定

```python
@app.post("/v1/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(...) -> Conversation:
    ...
```

**实测**：`POST` 返回 `201`（默认是 200）。

```python
@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int) -> Response:
    ...                                    # 204 不能有响应体
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

> ⚠️ **204 不允许有响应体**。如果你 `return {...}` 同时声明 204，某些客户端会报错。
> 用 `status` 常量（`status.HTTP_204_NO_CONTENT`）而不是魔法数字 `204`，可读性更好。

## 4.5 模型的复用策略（工程实践）

```text
UserCreate    ← 创建时用（含密码）
UserUpdate    ← 更新时用（字段都可选）
UserOut       ← 返回时用（不含密码）
UserInDb      ← 数据库内部用（含密码哈希）
```

| 做法 | 评价 |
|------|------|
| 一个 `User` 模型到处用 | ⚠️ **早晚泄露**：某个接口忘了过滤 |
| **按用途分模型 + 继承复用** | ⭐ 推荐 |

```python
class UserBase(BaseModel):
    name: str
    email: str


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    # 注意：这里没有 password
```

> ⭐ **判据**：**"这个数据会离开我的系统边界吗？"**
> 会 → 单独定义输出模型；不会 → 可以共用。

### 4.5b 本仓库落地：`response_model` 与返回注解的取舍（4a / 4b，2026-10-18 实测）⭐

#### ① 两种写法，什么时候用哪个

| 写法 | FastAPI 的行为 | 适用 |
|---|---|---|
| `async def f() -> Resp` | **自动**把它当 `response_model` | 返回的东西**就是**对外契约（本项目主用） |
| `@app.get(..., response_model=Resp)` + `-> Internal` | **`response_model` 赢**（文档与过滤都按它） | 内部模型**宽于**对外契约，要剥掉字段 |
| 两个都写、且相同 | 能跑，但**同一件事写两遍** | ❌ 不要 |

实测（同时存在且不同）：

```text
/c  response_model=Resp, -> InternalItem   OpenAPI: {"$ref": ".../Resp"}
返回 WideResp（多一个 debug 字段）+ response_model=Resp
  -> {"items": [{"id": "x"}]}              debug 被剥掉
```

#### ② ⚠️ 反直觉：`response_model` 不是"随便削一刀"

它要求返回对象**至少包含契约里的全部必填字段**：多了削掉，**少了 → 500**（实测）：

```text
返回 InternalItem（无 items 字段）+ response_model=Resp（要 items）
-> 500 ResponseValidationError: {'type': 'missing', 'loc': ('response', 'items')}
```

#### ③ 两层校验的分工

| 层 | 在哪 | 作用 | 失败时 |
|---|---|---|---|
| 业务层 | `ModelItem.model_validate(item)` | 把不可信的上游 dict 变成类型安全的模型 | 上游缺 `id` → **500**（我方假设崩了，不是客户端的错） |
| 响应层 | 返回注解 / `response_model` | **白名单**：没声明的字段不可能出去 | 必填字段缺失 → **500** |

⭐ `response_model` 是**最后一道网**，不是第一道。业务函数返回 `list[ModelItem]` 的好处：
失败点更早、mypy 看得懂、未来 CLI / 缓存也能复用。

#### ④ `list[ModelItem]` 而不是 `list[dict]`（实测对照）

```text
list[ModelItem] -> {"items": {"$ref": ".../ModelItem"}}         /docs 可展开字段
list[dict]      -> {"items": {"additionalProperties": true}}     /docs 只显示 [{}]
```

- **文档层**：`/docs` 能看到 `id` / `name` / `context_window` 的类型与说明
- **安全层**：响应模型 = 白名单；上游多塞的 `owned_by` / `effort` / `api_capabilities` 全部挡在门外

⚠️ **但 dict 也过不了这道网的反面不成立**：`list[dict]` + `response_model=ModelListResponse` **仍然会过滤**
（实测 `{"total":1,"items":[{"id":"x","name":"X"}]}`，`secret` 被剥）。区别在于**失败得更晚**，
且业务函数失去了类型信息。

#### ⑤ 本仓库实测（4b 完成态）

```text
GET /v1/upstream/models
200 {"total":2,"items":[
      {"id":"deepseek-flash","name":"DeepSeek-V4.1-Flash","context_window":1048576},
      {"id":"deepseek-v4-pro","name":"DeepSeek-V4-Pro","context_window":1048576}]}

OpenAPI 引用: {"$ref": "#/components/schemas/ModelListResponse"}
ModelItem 字段: ['id', 'name', 'context_window']
ModelListResponse 必填: ['total', 'items']
```

⚠️ **坑（本轮真实踩到）**：用 `TestClient(app)` **不加 `with`** 去调这条路由 → **500**，
堆栈是 `KeyError: 'llm_client'` —— 因为 `lifespan` 没执行，`app.state` 里没有共享 client。
这与 §6.4b 记的是同一个坑，**第二次踩到**。

## 4.6 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 4 pydantic 契约）。

---

# Step 5 · 依赖注入 `Depends`

## 定位

> 阶段 0 你手工做过依赖注入（把 `httpx.AsyncClient` 当参数传进 `fetch_model_ids`）。
> `Depends` 就是**把这件事自动化 + 声明式化**：FastAPI 帮你解析参数、创建对象、管理生命周期。

## 5.1 为什么需要它：先看重复代码

**没有 `Depends`**：

```python
@app.get("/conversations")
async def list_conversations(request: Request):
    token = request.headers.get("Authorization")           # ① 每个接口都要写
    if not token or not verify(token):
        raise HTTPException(401, "invalid token")
    async with SessionMaker() as db:                       # ② 每个接口都要写
        result = await db.execute(select(Conversation))
        return list(result.scalars().all())
```

**有 `Depends`**：

```python
@app.get("/conversations")
async def list_conversations(
    current_user: CurrentUserDep,     # ← 认证和数据库都"声明"出来就行
    db: DbDep,
):
    result = await db.execute(select(Conversation))
    return list(result.scalars().all())
```

> ⭐ **收益**：**接口函数只剩下它真正关心的事**。
> 认证、数据库、限流、分页参数……全部变成签名上的"声明"，实现被藏进可复用、可测试、可替换的依赖里。

## 5.2 函数依赖

```python
from typing import Annotated
from fastapi import Depends, Header, HTTPException


async def get_current_user(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ")
    if token != "valid-token":                     # 真实项目这里查库/JWT 验签
        raise HTTPException(status_code=401, detail="invalid token")
    return "user-001"


CurrentUserDep = Annotated[str, Depends(get_current_user)]


@app.get("/me")
async def me(user: CurrentUserDep) -> dict[str, str]:
    return {"user": user}
```

**三个关键点**：

| 点 | 说明 |
|----|------|
| 依赖的**参数**也能是别的依赖/参数 | `authorization: Annotated[str \| None, Header()]` 由 FastAPI 解析 |
| 依赖里 `raise HTTPException` | **在依赖阶段就短路**，路由函数根本不会被调用 |
| `Annotated[X, Depends(f)]` | ⭐ 让 `user` 的类型仍然是 `str`，mypy 和 IDE 都开心 |

## 5.3 类依赖：把一组参数打包

**实测通过的写法**（注意 `__init__` 里可以直接写 `Query`）：

```python
class PageDep:
    def __init__(self, limit: Annotated[int, Query(ge=1, le=100)] = 10) -> None:
        self.limit = limit


@app.get("/health")
async def health(page: Annotated[PageDep, Depends()]) -> dict[str, object]:
    return {"limit": page.limit}
```

**实测结果**：

```text
GET /health            → 200, limit = 10    （默认值生效）
GET /health?limit=3    → 200, limit = 3
GET /health?limit=0    → 422                 （Query(ge=1) 拦住）
```

> ⭐ `Depends()` **不带参数**表示"依赖这个类本身"，FastAPI 会去解析它的 `__init__` 签名。
> 这套写法适合"一组总是同时出现的参数"（分页、时间范围、排序），**一次声明，处处复用**。

## 5.4 `yield` 依赖：资源管理 ⭐

```python
async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionMaker() as session:
        try:
            yield session             # ① 交给路由使用
            await session.commit()    # ② 路由正常返回后提交
        except Exception:
            await session.rollback()  # ③ 出错回滚
            raise
```

**执行顺序**：

```mermaid
sequenceDiagram
    participant R as 路由函数
    participant D as get_db 依赖
    R->>D: 需要 db，进入依赖
    D->>D: 创建 session
    D->>R: yield session
    R->>R: 执行业务逻辑（可能抛异常）
    R->>D: 路由结束，回到 yield 之后
    D->>D: commit（或 rollback）
    D->>D: async with 退出，关闭 session
```

**实测**：`finally` 里的清理**确实执行**（本项目用一个记录列表验证过）。

| 关键点 | 说明 |
|--------|------|
| `yield` 前是 **setup** | 创建连接/会话 |
| `yield` 后是 **teardown** | 提交/回滚/关闭 |
| ⚠️ **异常时只有 `finally` / `async with` 的清理会执行** | `yield` 之后的**普通语句会被跳过** —— 详见 §5.4b（2026-10-15 实测，本行原表述"即使抛异常也会走 teardown"**过于笼统，已订正**） |
| ⚠️ 别在 `yield` 之后 `return` | 那里的返回值**不会被使用** |

> ⭐ **这是阶段 0 `async with create_client()` 的"框架版"**。
> 你自己写的时候要记得手动 `async with`；用 `Depends` 时，FastAPI 帮你记住生命周期。

### 5.4b ⚠️ 关键实测：异常时 `yield` 之后的**普通语句会被跳过**（2026-10-15）⭐⭐

**问题**：`yield` 之后的清理代码，在"路由抛异常"时到底执行吗？
（原 §5.4 只写了"即使抛异常也会走 teardown"，**没有区分"用什么写法"**，容易让人以为随便写都行。）

**两种写法的对照实测**：

| 写法 | 正常返回 | 路由抛异常 |
|---|---|---|
| ✅ 用 `async with` 包住 `yield` | `client.is_closed=True` | **`client.is_closed=True`** |
| ❌ `await client.aclose()` 写在 `yield` **之后** | `client.is_closed=True` | **`client.is_closed=False`** ⛔ |

```python
# ✅ 正确：清理由上下文管理器保证
async def client_ok() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(...) as client:
        yield client

# ❌ 反面：清理是 yield 之后的普通语句
async def client_bad() -> AsyncIterator[httpx.AsyncClient]:
    client = httpx.AsyncClient(...)
    yield client
    await client.aclose()      # ← 路由抛异常时，这行【被跳过】
```

**根因**：路由抛异常时，异常会被**"抛进"生成器的 `yield` 那一行** →
`yield` 之后的**普通语句全被跳过**，直接去找 `finally` / `async with.__aexit__` 的清理。

⭐ **后果**：**连接永远不会被关闭**。本机看不出（除非你主动检查 `is_closed`），
**上生产就是连接池耗尽、服务卡死**。

⭐ **规则（记死）**：**`yield` 之后只写"清理"，而且清理必须包在 `async with` 或 `try/finally` 里 —— 绝不写裸的普通语句。**

**另一条实测**（顺带验证）：无论路由抛的是 `HTTPException`（客户端错）还是裸 `RuntimeError`（500），
`async with` 的清理**都执行**。区分异常类型的是"要不要继续向上抛"，不是"要不要清理"。

### 5.4c 学习者亲测复现（2026-10-16）

`playground/depends_yield_demo.py` 把正反两种写法放进同一个 demo app 对照跑，实际输出：

```text
=== 正常返回 ===
  async with（正确）           状态码=200  client.is_closed=True
  yield 后 aclose（反面）       状态码=200  client.is_closed=True

=== 路由抛异常 ===
  async with（正确）           状态码=500  client.is_closed=True
  yield 后 aclose（反面）       状态码=500  client.is_closed=False   ← 泄漏

=== 项目里真正的依赖 LlmClientDep ===
  GET /real                状态码=200  {'ok': True}
```

⭐ **两行对照的读法**：
- 第 2 行 vs 第 4 行：**同样一种写法，只在"路由抛异常"时露馅** → 所以"跑一遍正常请求"是发现不了这个 bug 的；
- 第 4 行 vs 第 3 行：差异**只来自"清理用什么写法"**，与"路由干了什么"无关。

**演示文件里的三个关键技巧**（值得复用）：

| 技巧 | 作用 |
|---|---|
| `made: list[httpx.AsyncClient] = []` + 在依赖里 `made.append(client)` | **留下一个"可回查的痕迹"** —— 请求结束后才能回头问"它关了吗"。没有这个列表，`is_closed` 根本没机会看 |
| `TestClient(demo, raise_server_exceptions=False)` | 让路由异常变成 **500 响应**而不是抛给调用方；否则异常会直接中断脚本，你拿不到后面的检查结果 |
| 把**正反两种写法**放进**同一个文件**对照 | 单看一种写法"返回 200"无法判断对错；**两个并排跑、只让"异常"这一维变化**，差异才归因得清 |

> ⭐ 第 3 条是通用的实验设计法：**一次只变一个因素**，其余保持一致。
> 这里"路由是否抛异常"是唯一变量 —— 所以第 2 行与第 4 行的差别，**只能**归因于清理写法。

### 5.4d 三组补充实测（2026-10-16，回答自检题做的）⭐

> 📋 这三组实验回答的**题目与简要答案**在 [自检题清单.md](自检题清单.md)（阶段 1 · Step 5 第 6~8 题）。
> **本节保留的是完整实验数据**（清单里只放要点级答案）。

#### ① 依赖被"声明"就会执行 —— 哪怕路由函数体完全不用它

| 实验 | 结果 |
|---|---|
| 路由签名写了 `client: ClientDep`，函数体**一个字都没提** `client` | 状态码 200，**依赖被调用 1 次** |

⭐ **含义**：`Depends` 不是"用到才取"的惰性行为，而是**每次请求都执行**。
所以"给路由挂一个用不到的依赖"**是有成本的**（本例里等于每请求多造/关一个连接池）。
写 `Depends` 时应自问：**这个路由真的需要它吗？**

#### ② 同一次请求内，同一个依赖只执行一次（缓存的两个场景）

| 场景 | 依赖被调用次数 | 造出的 client 数 | 是不是同一个对象 |
|---|---|---|---|
| **同一路由两个参数**都要它（`a: ClientDep, b: ClientDep`） | **1** | **1** | ✅ `a is b` → `True` |
| **两个嵌套依赖**各自依赖它（`child_a` / `child_b`） | **1** | **1** | ✅ 同一个 |

⭐ 这就是 §5.5 讲的**依赖缓存**在起作用（默认 `use_cache=True`）：
不管多少层、多少个参数要用，**同一次请求里只算一次**。
这也回答了 §5.6b 那个问题 —— **嵌套依赖的任意一层被覆盖后，整棵树共用同一个替身**。

#### ③ ⚠️ 诚实的设计权衡：每请求新建 client 不是最优解（量化实测）

| 做法 | 200 次请求耗时 | 相对倍数 |
|---|---|---|
| **每请求新建**一个 `AsyncClient`（本项目当前做法） | **51.3 ms** | 1.00x |
| **全局共享**一个 `AsyncClient` | **23.0 ms** | **0.45x（快 2.23 倍）** |

**共享是否安全？** 实测：一个 `AsyncClient` 上 **20 个并发请求** → 20 个响应全部 200 ✅
（`httpx.AsyncClient` 就是设计成可共享并发的。）

⭐ **由此得到一个必须讲清的结论**：

| | 说明 |
|---|---|
| **`yield` 依赖这个机制必须学** | 因为有些资源的生命周期**天生**跟着请求走 —— 数据库会话（`AsyncSession`）**必须**每请求一个、请求结束就关；SSE 流式也一样 |
| **但 HTTP 客户端通常不该每请求新建** | 配置在启动时就固定了（`base_url`/`timeout`/`headers` 都来自 `settings`）；共享一个客户端才能**复用 keep-alive 连接**、省掉反复建池的开销 |
| **真实项目常见做法** | 在 **`lifespan`（应用启动/关闭钩子）**里创建一个全局 client，关闭时统一 `aclose()` —— 这正是 **Step 6** 的内容 |

⚠️ **所以本项目当前的"每请求新建 client"是一个【教学选择】，不是性能最优**：
它让我们能在一个简单场景里看清 `yield` 的 setup/teardown。
**已记为待办**：到 1.4d 决定 client 的生命周期最终怎么管（每请求 vs `lifespan` 全局）。
⚖️ 判据：**"生命周期跟着请求走"的资源用 `yield` 依赖；"生命周期跟着应用走"的资源用 `lifespan`。**

## 5.5 ⭐ 依赖缓存：同一次请求内只算一次

**实测结果**：

```python
def base_dep() -> str:
    calls["count"] += 1
    return "base"


def derived_dep(value: BaseDep, other: BaseDep) -> str:   # 请求了同一个依赖两次
    return value + "!"


# POST /v1/chat/completions 返回 call_count = 1     ← 实测：只执行了一次！
```

| 结论 | 说明 |
|------|------|
| 同一次请求内，**同一个依赖只执行一次** | 结果被缓存复用 |
| 缓存范围 | **单次请求**（不是全局） |
| 想强制不缓存 | `Depends(f, use_cache=False)` |

> ⭐ **为什么这个很重要**：`get_current_user` 可能要做 JWT 验签 + 查库。
> 如果 5 个依赖都用它，没有缓存就是**一次请求查 5 次库**。
> 有了缓存，无论谁要用，都只查 1 次 —— **这是 FastAPI 帮你做的性能优化**。

## 5.6 依赖覆盖：测试的杀手锏

```python
app.dependency_overrides[get_current_user] = lambda: "test-user"

try:
    response = client.get("/me")     # 现在不需要真实 token 了
finally:
    app.dependency_overrides.clear()  # ⚠️ 一定要清理，否则污染其他测试
```

| 用途 | 说明 |
|------|------|
| 绕过认证 | 测试业务逻辑时不想造 token |
| 换假数据库 | 换成内存库，测试快且隔离 |
| 模拟外部服务 | 假 LLM、假向量库 |

> ⚠️ **务必 `clear()`**（或用 fixture 自动清理），否则覆盖会**泄漏到后续测试**，造成"单独跑过、一起跑挂"。
>
> ⭐ 回到阶段 0 的结论：**依赖注入的全部价值就是"让调用方决定给真的还是给假的"**。
> `dependency_overrides` 把这句话变成了框架级能力。

## 5.6b 机制：覆盖到底怎么生效的（2026-10-15 读源码 + 实测）⭐

**问题来源**：学习者问"`app.dependency_overrides` 是哪来的？我好像没定义啊"。

### 它是 `FastAPI()` 送的，不是 Starlette 给的

出生证明在 `fastapi/applications.py` 第 986~1002 行（`FastAPI.__init__` 内）：

```python
self.dependency_overrides: Annotated[
    dict[Callable[..., Any], Callable[..., Any]],
    Doc("""... A dictionary with overrides for the dependencies.
             This is for testing, to replace expensive dependencies with testing versions."""),
] = {}
```

| 项 | 值（实测） |
|---|---|
| 何时产生 | 写 `app = FastAPI(title=...)` 的那一刻 |
| 类型 / 初值 | `dict[Callable, Callable]` / `{}` |
| 存在哪 | **实例属性**（`"dependency_overrides" in app.__dict__` → `True`） |
| Starlette 有吗 | **完全没有**（搜遍 `starlette/` 无此名）→ FastAPI 独有 |

**为什么"没定义也能用"**：Python 找 `app.xxx` 的顺序是
**实例 `__dict__` → 类 `__dict__` → 基类**。`FastAPI.__init__` 造对象时顺手挂了它，
所以你在第 ① 步就找到了 —— 它挂在**这个具体的 app 对象**上。

### 读取点在 `solve_dependencies()`（核心一行）

`fastapi/dependencies/utils.py` 第 619~638 行：

```python
for sub_dependant in dependant.dependencies:      # 遍历该路由的每个依赖
    original_call = sub_dependant.call
    call = getattr(provider, "dependency_overrides", {}).get(original_call, original_call)
    use_sub_dependant = get_dependant(path=..., call=call, ...)   # 用替身重新解析
```

⭐ **整件事的魔法就是 `.get(original_call, original_call)`**：**"查表；查不到就用它自己。"**

| 你做了什么 | 结果 |
|---|---|
| 字典为空 | `get` 返回原函数 → 一切照旧 |
| 登记了替身 | `get` 返回替身 → 替换生效 |

**由此解释三件事**：

1. **键必须是函数对象**：查表用的就是 `original_call` 本身，字符串路径查不到。
2. **替身签名必须对得上**：查完还要 `get_dependant(call=call)` **重新解析替身的签名**
   （`get_settings()` 零参数 → 替身也必须零参数）。
3. **嵌套依赖任意一层都能覆盖**：递归时把 `dependency_overrides_provider` 一路传下去。

另：第 623~626 行先判断"字典非空"才走这条分支 —— 空字典时不进这段逻辑（性能优化）。

### 为什么必须 `clear()`（实测）

同一个 `app` 上造两个 TestClient，只通过第一个做覆盖：

```text
经 c1 覆盖前 -> deepseek-flash
经 c1 请求   -> fake-model
经 c2 请求   -> fake-model   <- c2 什么都没做，也被改了
clear 之后 c2-> deepseek-flash
```

⭐ 它是**挂在 app 上的可变字典**，生命周期 = **app 的生命周期（整个进程）**，不是"一次请求"。
忘了 clear → 后续测试全被污染 → 症状是**"单独跑过、一起跑挂"**。

## 5.6c 三条补充实测（2026-10-15，收口时做的判定性实验）⭐

### ① 给依赖参数加默认值 `= None` —— 无效且有害

| 观察 | 结果 |
|---|---|
| 运行时 | 200，正常返回（**看起来没坏**） |
| **判定性实验** | 把 `get_settings` 覆盖成"会抛异常的函数" → **异常真的抛出了** → 证明**依赖照常被调用，`None` 被完全忽略** |
| mypy | `Incompatible default for parameter "config" (default has type "None", parameter has type "Settings") [assignment]` |

⭐ **结论：依赖参数不要加默认值。** 加了不但无效，还会**误导读者**以为"可以不传"。

> 判定性实验的价值：只看"返回 200"无法区分"默认值生效了"和"依赖照常执行"。
> 把一个**可观测的副作用**（这里是抛异常）放进依赖里，才能判定它到底有没有被调用。

### ② `dependency_overrides` 是【全局表】，做不到"按请求区分"

| 实验 | 结果 |
|---|---|
| 覆盖成 `fake-A` 后连发两次 | 两次都是 `fake-A`（**无法区分**） |
| 8 个**并发**请求（线程池） | distinct results = `["fake-A"]`（无竞态，但也无差异） |
| **正确姿势**：让替身自己读请求 | 不带 header → `deepseek-flash`；带 `x-use-fake: 1` → `fake-model` ✅ |

**正确姿势的代码形状**：

```python
def per_request_settings(request: Request) -> Settings:
    if request.headers.get("x-use-fake") == "1":
        return Settings(llm_model="fake-model")
    return get_settings()

app.dependency_overrides[get_settings] = per_request_settings
```

⭐ **`dependency_overrides` 的设计目标是"整场测试换成假的"**（上游源码注释原话：
*This is for testing*），**不是**"按请求动态切配置"。要按请求变，就把判断逻辑放进**依赖本身**。

### ③ 打补丁必须打在「用的地方」（`import` 的绑定语义）

内存实验（模拟 `config` 模块 + `app` 模块做 `from config import settings`）：

```text
初始                 -> REAL
改 config 模块里的    -> REAL                 <-- 没用！
改 app 模块里的       -> PATCHED_AT_USE_SITE   <-- 这才生效
```

⭐ 根因：`from app.config import settings` 是**在 app.py 这个模块里新建了一个名字绑定**。
`chat` 查的是**自己模块的全局名** → 要改的是 `app.api.app.settings`，**不是** `app.config.settings`。

**这正是"字符串路径"脆弱的含义**：你得知道**每一个使用点的准确路径**；
而 `depends_overrides` 的键是**函数对象**，与文件位置无关。

## 5.7 依赖可以嵌套（会形成一棵树）

```python
def get_settings() -> Settings: ...
def get_client(settings: SettingsDep) -> Client: ...
def get_service(client: ClientDep) -> Service: ...
def get_user(settings: SettingsDep, service: ServiceDep) -> User: ...
```

FastAPI 会：
1. 从最底层开始解析（**拓扑排序**）
2. 每个依赖**只解析一次**（缓存）
3. 任一环节抛 `HTTPException` → **整条链短路**

> ⭐ 细节（DAG、缓存、短路）见 **难点拓展 3**。

## 5.8 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 5 依赖注入）。

---

# Step 6 · 错误处理与 `lifespan`

## 定位

> 好的服务不是"不报错"，而是**报错时报得清楚、格式统一、不泄露内部细节**。

## 6.1 `HTTPException`：可预期的错误

```python
from fastapi import HTTPException, status

@app.get("/items/{item_id}")
async def get_item(item_id: int) -> dict[str, int]:
    if item_id == 404:
        raise HTTPException(status_code=404, detail="item not found")
    return {"item_id": item_id}
```

**实测响应**：

```http
HTTP 404
{"detail": "item not found"}
```

| 要点 | 说明 |
|------|------|
| 抛出后**立刻停止**，后续代码不执行 | 不用写 `return` |
| `detail` 必须是**可 JSON 序列化**的 | 可以是 `dict`（见下） |
| 默认响应体形状是 `{"detail": ...}` | 想改就得用异常处理器 |

**带结构化 detail**（前端更好处理）：

```python
raise HTTPException(
    status_code=400,
    detail={"code": "INVALID_MODEL", "message": "模型不支持", "model": model_name},
)
```

### 6.1b 本仓库实测：三组"看着对、结果错"的写法（2026-10-17）⭐

**① `HTTPException` 是谁翻译成响应的**（读源码 `fastapi/exception_handlers.py`）：

```python
# 第 11 行
async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    ...
    # 第 15 行
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
```

→ 你只负责 `raise`，框架负责翻译。所以 `raise` 之后不需要 `return`。

**② `Literal` 路径参数 vs 手写 `if not in`**（实测）：

```text
GET /lit/deepseek-flash -> 200 {"model_name":"deepseek-flash"}
GET /lit/nope            -> 422 {"detail":[{"type":"literal_error",
                              "msg":"Input should be 'deepseek-flash' or 'deepseek-v4-pro'",
                              "input":"nope", ...}]}
GET /lit/123             -> 422（同上）
```

| 问题 | 说明 |
|---|---|
| 状态码语义错 | 422 = "你的**格式**不对"；这里是"格式没问题，**资源不存在**" → 该 404 |
| **泄露允许清单** | 报错里把全部合法值列了出来。模型名无所谓，换成用户名/邀请码就是**枚举漏洞** |
| 第二份真相 | `KNOWN_MODELS` 变一次，`Literal` 也要改一次 |

⚠️ 顺带订正一个直觉：**URL 路径参数永远是字符串**（`/v1/models/123` 里的 `123` 也是 `str`），
所以"写 `str` 会漏掉数字类型的输入"这个担心不成立 —— 真正的漏检风险在"**谁负责判断在不在清单里**"。

**③ `return` 而不是 `raise`**（实测，两种返回注解都测了）：

```text
有返回注解 -> dict[str, str]：  500 Internal Server Error
                              （ResponseValidationError: dict_type ...
                                input: HTTPException(status_code=404, detail='x')）
没有返回注解：                 200 OK  {"status_code":404,"detail":"x","headers":null}
```

⭐ **最坏的是第二种：客户端拿到 200，以为成功了。** 这是"工具全绿但语义全错"的又一例
（同 1.4e 的 `Bearear`、1.4c 的缩进错一个家族）。

**④ 本项目落地**（`src/app/api/app.py` 的 `get_model`）：

```python
if model_name not in KNOWN_MODELS:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"模型不存在: {model_name}",
    )
```

实测：`/v1/models/deepseek-flash` → `200`；`/v1/models/this-model-does-not-exist` → `404 {"detail":"模型不存在: ..."}`。

### 6.1c 上游的错误怎么翻译成本服务的状态码（6.2a 实战，2026-10-17 实测）⭐⭐

> **本节是全阶段最重要的语义区分：上游的响应状态码 ≠ 我们回给客户端的状态码。**

#### ① 两层状态码，各自回答"谁的问题"

```text
客户端 ──请求──▶ 我们的服务 ──请求──▶ 上游（DeepSeek）
     ◀──响应──          ◀──响应──
   第 3 层            第 2 层
```

| 层 | 状态码 | 回答的问题 | 例 |
|---|---|---|---|
| 上游 `r.status_code` | 401 | "**你的服务器**对我有资格吗" | 我们的 API Key 错了 |
| 我方 `HTTPException.status_code` | 502 | "**你（客户端）**这次请求，我这里是什么结果" | 上游故障，不是我方也不是你的问题 |

**⚠️ 绝对不能把上游的码直接透传。** 实测（把 `r.status_code` 原样塞进 `HTTPException`）：

```text
透传上游 401 -> 401 {"detail":"upstream said no"}
```

客户端收到 401 的正常反应是**弹登录框 / 清本地 token / 重走认证** —— 而这些动作全都**无效**，
因为错的不是它，是我们服务器和上游之间的凭证。**错误的状态码会让客户端在错误的方向上努力。**

**所以采用"统一 502"**：上游 401 / 429 / 503 一律翻译成 **502 Bad Gateway**，上游的具体号码只放进 `detail`（人看的）与日志（机器查的）。

| 好处 | 说明 |
|---|---|
| 对外只有一种契约 | 客户端只需认"5xx = 等一会儿/找服务方"，不必对每个上游码写分支 |
| 不泄露上游供应商 | 客户端看不出我们是 DeepSeek 还是别家、以及上游的内部状态 |
| 语义准确 | 502 = 网关访问上游失败（RFC 9110），正好是"我们替客户端调第三方，第三方不行了" |

#### ② `httpx` 的异常分两支（实测继承链）

```text
httpx.HTTPError
├── HTTPStatusError      ← 上游【有回应】，但状态码 4xx/5xx（raise_for_status 抛）
└── RequestError         ← 上游【根本没有回应】
    └── TransportError
        ├── TimeoutException
        └── NetworkError
            └── ConnectError
```

| 分支 | 有 `.response` 吗 | 能读到什么 | detail 该写什么 |
|---|---|---|---|
| `HTTPStatusError` | ✅ `Response`（实测状态码 401、`.request` 也在） | `exc.response.status_code` | `上游返回状态码 401` |
| `RequestError` / `ConnectError` | ❌ **没有**（`hasattr` 实测 `False`） | 只能读 `str(exc)` | `无法连接上游模型服务` |

**推论**：两个分支的 `detail` 注定不同 → 不能合并成 `except httpx.HTTPError`
（合并就得写 `getattr(exc, "response", None)`，可读性更差）。

#### ③ `httpx.HTTPStatusError` vs `fastapi.HTTPException`（两个不同的东西）

| | `httpx.HTTPStatusError` | `fastapi.HTTPException` |
|---|---|---|
| 属于谁 | `httpx`（客户端库） | `fastapi`（Web 框架） |
| 谁抛 | `resp.raise_for_status()`，**上游**的行为触发 | **我们自己**写的 `raise` |
| 带什么 | `.request` / `.response` | `.status_code` / `.detail` / `.headers` |
| FastAPI 认识吗 | ❌ **不认识** → 漏出去就是 **500**（实测） | ✅ 认识，有专门处理器翻译成 JSON |
| 语义 | "我调上游失败了" | "我要给**我的**客户端回这个码" |

**FastAPI 只认识三个异常**（实测 `app.exception_handlers` 的键）：

```text
['HTTPException', 'RequestValidationError', 'WebSocketRequestValidationError']
```

⭐ **机制性结论：任何没被这几张表登记的异常，一律 500。** 所以"翻译"不是风格问题，是必经步骤。

#### ④ `as exc` 与 `from exc`

| 语法 | 作用 | 实测 |
|---|---|---|
| `except X as exc:` | 把捕获到的**实例**绑到名字上 | 块内可取；**块外 `NameError`**（Python 3 故意在块结束时删除，防止异常对象延长寿命）。名字随便起，`exc` 是习惯 |
| `raise Y from exc` | 设置 `Y.__cause__ = exc`（**显式**因果） | `__cause__: ConnectError`；traceback 措辞 `The above exception was the direct cause of the following exception:` |
| 不写 `from` | `__cause__` 为 `None`，但 `__context__` 仍被自动填（**隐式**因果） | traceback 措辞 `During handling of the above exception, another exception occurred:`（像"翻译代码自己崩了"） |

- 判据：**有意转换 → `from`；意外顺带炸出 → 不写**。
- 本项目启用了 `ruff` 的 **B904**（实测）：`except` 块里 `raise` 不写 `from` 会直接报错 —— 所以这是**质量门强制的**。
- 想主动切断因果：`raise ... from None`。

#### ⑤ 本仓库三组实测输出（`/v1/upstream/models`）

```text
A 真实上游            : 200 {"total":2,"items":["deepseek-flash","deepseek-v4-pro"]}
B 连不上(127.0.0.1:9) : 502 {"detail":"无法连接上游模型服务"}
C 上游回 404          : 502 {"detail":"上游返回状态码 404"}
D MockTransport 造 503: 502 {"detail":"上游返回状态码 503"}
```

- **B 验的是 `RequestError` 分支**，用 `$env:LLM_BASE_URL="http://127.0.0.1:9"` 临时覆盖（环境变量优先级高于 `.env`，实测）。
- **D 验的是 `HTTPStatusError` 分支**，用 `httpx.MockTransport` 在**不联网**的情况下造假上游 —— 提前用上了 Step 12（测试）的工具。
- ⚠️ C 暴露一个细节坑：`base_url="https://httpbin.org/status/503"` + 请求 `"/models"` 实测拼成
  `https://httpbin.org/status/503/models`（**base_url 的路径部分会被保留并拼上去**），于是一路 404。
  **`base_url` 应当只写到域名/版本前缀，别带路径。**

#### ⑥ 业务 bug 不能被抓进这两个分支

`payload["data"]` 拼成 `payload["datas"]` → `KeyError`，**两个 `except` 都匹配不上 → 500**（实测）。**这是对的**：

| 若被 502 吃掉 | 后果 |
|---|---|
| 监控 | 5xx 里分不出"依赖挂了"和"我写错了" → 告警永远不响 |
| 排查 | 你去查 DeepSeek 状态页，而不是看自己的 `payload["data"]` |
| 用户 | 以为"等一下重试就好"，实际重试一万次都错 |

⭐ **`except` 抓得越窄，"谁的错"记录得越准。** 用 `except Exception` 统一转 502 = 主动放弃这个能力。

### 6.1d 400 vs 422：两道关卡 + 怎么读 422（6.2b 实战，2026-10-17 实测）⭐

> 场景：`/v1/chat` 的最后一条消息不是 `user`（例如只有一条 `system`）时，应该回什么？

#### ① 两道关卡，各管一件事

| 关卡 | 谁在管 | 拦什么 | 状态码 |
|---|---|---|---|
| **契约层** | pydantic（`ChatRequest`） | **形状**：`role` 不在三个值里 / `messages` 空列表 / `temperature` 越界 | **422** |
| **业务层** | 路由函数里的 `if` | **语义**：形状全对，但这件事不合理 | **400** |

实测反例：`{"messages": [{"role": "system", "content": "你是助手"}]}` —— 字段全合法，
但**没有人类提问**，回显它等于把"人设"当答案（`[echo] 你是助手`）。→ 改后返回
`400 {"detail":"最后一条消息必须是 user，当前是 system"}`。

**为什么不用 pydantic 的 `model_validator` 干掉这条检查**：

| 理由 | 说明 |
|---|---|
| 职责混乱 | `schemas.py` 应只回答"数据长什么样"，不该回答"这个请求合不合理" |
| 复用会跟着跑 | 换一个接口复用 `ChatRequest` 时，业务规则不该被一起带走 |
| 状态码会错 | validator 失败统一变 **422**，而它本质是 400（语义问题） |

⭐ 判据：**形状归 pydantic，语义归路由。**

#### ② 422 有很多种 —— 必须读 `type` 和 `loc`

五种输入全返回 422，但含义完全不同（实测）：

| 输入 | `detail[0].type` | `detail[0].loc` |
|---|---|---|
| `{"messages": []}` | **`too_short`** | `["body","messages"]` |
| `{}` | `missing` | `["body","messages"]` |
| `{"messages": "hi"}` | `list_type` | `["body","messages"]` |
| `role: "usr"` | `literal_error` | `["body","messages",0,"role"]` |
| **请求体不是合法 JSON** | **`json_invalid`** | `["body", 1]` |

⭐ **判据：看 422 先看 `type` + `loc`，再看状态码。** 状态码只说"被拦下了"，`type`/`loc` 才说"在哪一关、因为什么"。

**真实踩坑（同一轮发生）**：用 PowerShell 内联写

```powershell
curl.exe ... --data "{\"messages\":[]}"     # ❌ 无效验证
```

服务器收到的字节是 `{\"messages\":[]}`（反斜杠被当字面量），于是返回 **422 `json_invalid`** ——
**状态码"对了"，但原因完全不对**，等于没验。正确做法是把 JSON 写进临时文件：

```powershell
[IO.File]::WriteAllText("$env:TEMP\chat_empty.json", '{"messages":[]}', (New-Object System.Text.UTF8Encoding($false)))
curl.exe -s -i -X POST http://127.0.0.1:8000/v1/chat -H "Content-Type: application/json" --data "@$env:TEMP\chat_empty.json"
# → 422 type=too_short loc=["body","messages"]  ✅ 这才是真的验到了契约层
```

#### ③ `detail` 回显什么安全

| 回显内容 | 风险 | 结论 |
|---|---|---|
| `last.role`（`Literal` 三值之一） | 有界枚举，无法注入 | ✅ 安全 |
| `last.content`（用户自由文本） | 超长撑爆响应/日志、换行造成日志注入 | ⚠️ 要截断/转义，或只回显长度或 ID |

### 6.1e 业务层 vs 接口层：本项目到底哪层是哪个文件（2026-10-18）

> 一句话判据：**接口层懂 HTTP，业务层懂业务。** 问"离了 HTTP 还活得下去吗"就够了。

#### ① 本项目现状

```text
接口层（懂 HTTP）
  src/app/api/app.py                       路由 / 状态码 / 响应序列化
  src/app/api/deps.py                      依赖装配（Depends 是框架机制）
  src/app/schemas.py                       对外契约（请求/响应形状）
  src/app/errors.py 的 register_exception_handlers + _STATUS_BY_CODE
业务层（懂业务规则）
  ⚠️ 目前没有 —— "最后一条必须是 user" 这条规则暂时住在 app.py 的 if 里
  将来：src/app/services/chat.py
基础设施层（懂外部世界）
  src/app/config.py / src/app/llm_client.py
  src/app/errors.py 的 AppError（纯业务异常，零 fastapi 依赖）
```

#### ② `errors.py` 是跨两层的，这是有意的妥协

| 内容 | 属于 | 判据 |
|---|---|---|
| `class AppError(Exception)` | **业务层** | 不知道 HTTP，只有 `code` / `message` |
| `_STATUS_BY_CODE` | **接口层** | 知道 400 / 409 |
| `register_exception_handlers` | **接口层** | import 了 `FastAPI` / `JSONResponse` |

拆的时机：出现 `services/` 目录或异常种类变多时，拆成
`src/app/errors.py`（只有 `AppError`）+ `src/app/api/exception_handlers.py`（映射 + 注册）。
⭐ 判据：**一个文件里同时有 `import fastapi` 和纯业务类，早晚要拆**；现在不拆是因为拆的收益 < 认知成本。

#### ③ 一眼判断文件属于哪层

| 看到什么 | 属于 |
|---|---|
| `from fastapi import ...` / `Request` / `JSONResponse` / `@app.get` / `status.HTTP_4xx` / `Depends` | 接口层 |
| `BaseModel` 定义的**输入/输出形状** | 契约（接口层边界） |
| `httpx` / `os.environ` / DB 驱动 | 基础设施层 |
| 纯 `if` + 抛 `AppError`，**不 import fastapi** | 业务层 |

**硬规则：业务层永远不 import `app.api.*` 或 `fastapi`。** 出现即说明控制流反了。
调用方向单向：`接口层 → 业务层 → 基础设施层`，禁止反向 import。

#### ④ 规则放错层会发生什么

| | 规则在接口层（现状） | 规则在业务层（将来） |
|---|---|---|
| 被 CLI 复用 | ❌ 抄一遍 | ✅ import |
| 测试 | 要造 HTTP 请求 | 直接传 `list[Message]` |
| 换框架 | 跟着重写 | 不动 |
| 规则变多 | `app.py` 膨胀 | `app.py` 保持薄 |

⭐ **分层跟着"变化的压力"走，不跟教条走**：只有 4 行、只有 1 个调用方时，抽出去只是搬家。

#### ⑤ 错误响应的形状应当只有一份

现在实际存在**三种**形状：

```text
400 业务异常   {"error": {"code": "...", "message": "..."}}
404 HTTPException {"detail": "..."}
422 校验失败   {"detail": [{...}]}     ← 还是数组
```

判据：**错误响应的形状应当让客户端只写一份解析代码。** 现在要写三份 → 是缺陷。
收口方式（留到 6.3c）：给 `HTTPException` 与 `RequestValidationError` 各注册一个处理器，统一成
`{"error": {"code", "message", ...}}`。**先做 6.3b（500 + 请求 ID）再动手**，否则会改两遍。


## 6.2 自定义异常 + 全局处理器

```python
class AppError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": exc.code},
    )


@app.get("/boom")
async def boom() -> None:
    raise AppError("duplicate")
```

**实测**：`GET /boom` → `409 {"error": "duplicate"}`

| 好处 | 说明 |
|------|------|
| **业务代码不用关心 HTTP** | 抛 `AppError("duplicate")` 即可，映射逻辑集中在一处 |
| **响应格式统一** | 前端只需要处理一种错误形状 |
| **不会漏掉** | 不用每个路由都记得 `try/except` |

> ⭐ **推荐分层**：
> | 异常 | 谁抛 | 映射成 |
> |------|------|-------|
> | `HTTPException` | 路由层（"这个请求有问题"） | 4xx（可直接指定） |
> | 自定义业务异常 | **服务层**（"业务规则不允许"） | 由处理器统一映射 |
> | 未捕获异常 | 任何地方 | **500**（+ 日志告警，⚠️ 绝不回显堆栈） |

## 6.3 ⚠️ 500 错误绝不回显堆栈

**危险做法**：

```python
@app.exception_handler(Exception)
async def all_errors(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc), "traceback": ...})
```

**为什么危险**：

| 风险 | 说明 |
|------|------|
| **泄露内部结构** | 堆栈里有文件路径、库版本、代码行号、变量名 |
| 泄露配置 | 报错信息里可能带连接串、Key 片段 |
| 给攻击者导航 | "哦，它用的是旧版 xxx，有已知漏洞" |

> ⭐ **正确做法**：
> **对用户**返回一个**请求 ID**；**对日志**记录完整堆栈（含请求 ID）。
> 排查时用 ID 关联 —— 用户看不到内部细节，你又能精确定位。

```python
return JSONResponse(status_code=500, content={"error": "internal_error", "request_id": rid})
```

## 6.3b 500 兜底 + 请求 ID：日志到底去哪儿（2026-10-18 实测）⭐⭐

#### ① 三张网，从近到远

```text
raise AppError          → _app_error_handler        （业务异常，400/409…，detail 可控）
raise 任意 Exception    → _unhandled_error_handler  （500 + request_id，堆栈只进日志）
处理器自己也炸          → uvicorn 原生 500（空 body，无 content-type）  ← 实测
```

⭐ 查找顺序是 `type(exc).__mro__` **从子到父**，所以 `HTTPException` 永远先命中它自己的内置处理器，
不会被 `Exception` 兜底吃掉（实测：`HTTPException(418)` → `418 {"detail":"我是茶壶"}`）。

#### ② 日志的实际落点（实测原文）

```text
INFO:     Uvicorn running on http://127.0.0.1:8015 (Press CTRL+C to quit)
未处理异常 request_id=2294deddc8e1 path=/__boom        ← 我们的 logger.exception（无格式）
Traceback (most recent call last):
  ...
KeyError: 'datas'
INFO:     127.0.0.1:54243 - "GET /__boom HTTP/1.1" 500 Internal Server Error   ← access log
ERROR:    Exception in ASGI application                 ← uvicorn 再打一遍
Traceback (most recent call last):
  ...
KeyError: 'datas'
```

六条实测事实：

| # | 事实 |
|---|---|
| 1 | 目的地 = **启动 uvicorn 那个终端的 stderr**；**不写文件**、关窗口即消失 |
| 2 | 我们的日志**没有时间戳/级别/模块名** —— root logger 无 handler、级别 WARNING，落到 `lastResort` |
| 3 | **两段 traceback 不是重复**：`starlette/middleware/errors.py:186` 生成响应后又 `raise exc`，uvicorn 接住再打一次 |
| 4 | **`logger.info(...)` 现在完全不出现**（级别不够）—— 静默丢弃 |
| 5 | `INFO: 127.0.0.1 - "GET ..."` 是 uvicorn **access log**，与应用日志是两条通道 |
| 6 | PowerShell 把 stderr 标成红字 `NativeCommandError`，那不是额外错误 |

#### ③ `request_id` 的真正价值

```text
用户：我报错了，ID 是 748f0334b804
你：  Select-String -Path "$env:TEMP\app.log" -Pattern "748f0334b804" -Context 0,30
```

**用户给一个不含内部信息的随机串，你定位到唯一那条日志。** 单机够用；
多机/微服务要补三样：日志集中收集（Loki/ELK）、`trace_id`（W3C `traceparent`，跨服务）、
结构化日志（JSON + 固定字段）。

#### ④ 兜底处理器的边界

| 原则 | 原因（实测） |
|---|---|
| 里面**只做**三件事：记日志、拼 JSON、返回 | 它自己抛异常时，客户端拿到**空 body、无 content-type** 的 500（没有更外层的网了） |
| 绝不回显 `str(exc)` / 堆栈 | 500 泄露内部结构（§6.3） |
| 日志必须带 `request_id` | 否则只有时间，无法与用户报的 ID 对上 |

## 6.4 `lifespan`：启动与关闭 ⭐

**⚠️ 旧写法已废弃**：

```python
@app.on_event("startup")      # ❌ 已废弃
async def startup(): ...

@app.on_event("shutdown")     # ❌ 已废弃
async def shutdown(): ...
```

**实测弃用警告原文**（FastAPI 0.142.2）：

```text
DeprecationWarning:
        on_event is deprecated, use lifespan event handlers instead.
        Read more about it in the
        [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
```

**新写法**：

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, object]]:
    # ---- 启动时：只执行一次 ----
    app.state.startup_done = True
    await init_db()                       # 建表 / 建连接池 / 预热模型

    yield {"store_version": 7}            # ① 这里的 dict 会并入 request.state

    # ---- 关闭时：只执行一次 ----
    await engine.dispose()                # 关连接池 / 释放资源


app = FastAPI(lifespan=lifespan)
```

**实测：`yield` 的 dict 真的能拿到**：

```python
@app.get("/health")
async def health(request: Request) -> dict[str, object]:
    return {
        "startup_done": getattr(request.app.state, "startup_done", False),
        "lifespan_state": getattr(request.state, "store_version", None),
    }

# 实测 GET /health →
# {"ok": true, "limit": 10, "startup_done": true, "lifespan_state": 7}
```

| 场景 | 该放哪 |
|------|-------|
| 建数据库表 / 连接池 | lifespan 启动段 |
| **加载模型 / 建向量库客户端** | lifespan 启动段 ⭐ |
| 关闭连接池、flush 日志 | lifespan 关闭段 |
| 每次请求都要做的 | 依赖（`Depends`），**不是 lifespan** |

> ⭐ **为什么不能在模块顶层加载模型**：
> ```python
> model = load_model()   # ❌ 模块导入时执行 → 测试 import 也会加载、--reload 会重复加载
> ```
> lifespan 让它**在服务真正启动时**加载一次，**测试时可以绕过**（甚至不触发）。
> 对 LLM 应用尤其关键 —— 加载 embedding 模型可能要好几十秒。

### 6.4b 本项目落地：把 HTTP client 改成应用级共享（2026-10-18 实测）⭐

#### ① 改了什么

| | 改前（`yield` 依赖） | 改后（`lifespan` + `app.state`） |
|---|---|---|
| 谁创建 | 每个请求进来时 | 进程启动时**一次** |
| 谁关闭 | 框架在请求结束时 | 进程关闭时**一次** |
| 连接池 | 每次新建 → 重新 TCP + TLS 握手 | **复用** |
| 实测 200 次请求 | 51.3 ms | 23.0 ms（**快 2.23 倍**） |

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with create_llm_client() as client:   # 退出时自动 aclose()
        app.state.llm_client = client           # 点号！挂到 app 上
        yield
```

```python
def get_llm_client(request: Request) -> httpx.AsyncClient:
    client: httpx.AsyncClient = request.app.state.llm_client
    return client
```

#### ② 实测：生命周期真的按预期走

```text
异常处理器: ['HTTPException', 'RequestValidationError', 'WebSocketRequestValidationError', 'AppError', 'Exception']
startup 后 is_closed: False
请求1: 200 {"total":2,...}
两次请求用的是同一个 client: True
运行中 is_closed: False
shutdown 后 is_closed: True          ← async with 自动 aclose
```

#### ③ 三个"工具抓不到、运行时必炸"的坑（本轮真实发生）

| 坑 | 症状 | 实测/原因 |
|---|---|---|
| **`app.state,llm_client = client`（逗号）** | 启动直接失败 | 实测 `TypeError: cannot unpack non-iterable AsyncClient object`。若右边可迭代更阴：`app.state, x = [1,2]` → **`app.state` 被换成 `1`**（整个 state 对象被覆盖），无任何报错 |
| **两个 `app = FastAPI(...)`** | 所有业务错误变 500 | 第二个覆盖模块级 `app`；`register_exception_handlers(app)` 注册在**旧的**上 → uvicorn 用新的 → 处理器全丢。判据：**一个模块只允许出现一次 `app = FastAPI(...)`** |
| **单测不用 `with TestClient(app)`** | `app.state` 里没有 `llm_client` → 500 | lifespan 只在上下文管理器里执行（2026-10-17 已实测）。**用过 `with` 之后再不用，会拿到已关闭的 client**（`is_closed=True`），更隐蔽 |

#### ④ `AsyncIterator[None]` 而不是 `dict`

`yield` 后面不写值 → 注解 `AsyncIterator[None]`；若 `yield {"k": v}`，注解写成 `AsyncIterator[dict[str, object]]`，
且那个 dict **并入每个请求的 `request.state`**（不是 `app.state`，2026-10-17 实测）。


## 6.5 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 6 错误处理与 lifespan）。

---

# 阶段 1 前半程回顾 · Step 1 ~ 6（2026-10-18）

> 与阶段 0 的「十步回顾」对称。**一句话主线**：
> 请求怎么进来 → 怎么读参数 → 怎么定契约 → 依赖怎么给 → 出错怎么办 → 资源活多久。
> 每一步都在往**同一个 `app.py`** 上加一个能力，不是并列的六个知识点。

```mermaid
flowchart LR
    S1["1 HTTP/ASGI<br/>请求怎么来的"] --> S2["2 最小应用<br/>路由怎么登记"]
    S2 --> S3["3 三段参数<br/>参数从哪读"]
    S3 --> S4["4 契约<br/>数据长什么样"]
    S4 --> S5["5 依赖<br/>东西从哪来"]
    S5 --> S6["6 错误与生命周期<br/>坏了怎么办 / 活多久"]
```

| Step | 一句话 | 一句话为什么 | 现在代码里对应什么 |
|---|---|---|---|
| 1 | HTTP 报文 / 无状态 / 幂等 / WSGI vs ASGI | **ASGI 的 `send` 能调多次**，这是流式响应的物理前提 | —— |
| 2 | 装饰器 = 往路由表登记一行；`/docs` 从注解生成 | 把"手写 HTTP 解析"变成"写普通函数" | `@app.get("/health")` |
| 3 | 路径 / 查询 / 请求体的判定规则 | 判定靠**类型注解与位置**，不靠参数名 | 4 条 `/v1/*` 路由 |
| 4 | 输入契约（422）+ **输出契约（白名单）** | 响应模型 = "我对客户端的承诺"，不是"我手里有什么" | `-> ChatResponse`、`ModelItem` / `ModelListResponse` |
| 5 | 依赖是**接缝**：有接缝才能替换 | 测试替换、生命周期、复用，三件事一次解决 | `config: SettingsDep`、`client: LlmClientDep` |
| 6 | 状态码描述**"谁的问题"**；`lifespan` 管进程级资源 | 502 / 400 / 404 / 500 各有归属，客户端才不会走错方向 | `errors.py`、`lifespan`、`register_exception_handlers(app)` |

**串起来的一句话**：

> **先弄清请求怎么来的（1、2），再弄清参数从哪读（3），再把数据形状钉死（4），
> 再把资源的来路管起来（5），最后把"坏了怎么办"和"活多久"定下来（6）。**

**与阶段 0 的衔接**：这一阶段没有引入新知识门类，只是把阶段 0 的东西**串成一条请求流水线** ——
路由读 pydantic 模型（0·Step 5）、服务靠 async 撑并发（0·Step 7）、接口靠 mypy 锁类型（0·Step 6）。

---

## 六个坑 → 六条判据（全部本仓库实测）

| 坑 | 判据 |
|---|---|
| 同一路径 `/v1/models/latest` 与 `/v1/models/{name}` 顺序颠倒 | **固定路径必须写在动态路径之前**，否则永远匹配不到 |
| `Literal[...]` 当路径参数（想省掉清单判断） | 不存在资源会回 **422 而非 404**，且报错里**列出全部合法值** |
| `return HTTPException(...)` 而不是 `raise` | 有返回注解 → 500；**没注解 → 200（谎报成功）**。异常对象只有 `raise` 才有意义 |
| 把上游的 `401` 原样透传 | 客户端会误以为"我要登录"。**状态码描述的是"谁的问题"，不是"上游回了什么"** |
| `except Exception` 统一转 502 | 自家 bug 被伪装成上游故障 → 监控不响、排查跑偏。**`except` 抓得越窄，"谁的错"记得越准** |
| 两个 `app = FastAPI(...)` | 处理器注册在旧对象上、uvicorn 用新对象 → 业务异常全变 500。**一个模块只允许一次** |

## 五条错误路径一览（本项目当前状态）

| 状态码 | 谁的问题 | 场景 | 响应形状 |
|---|---|---|---|
| **400** | 客户端（语义） | 最后一条消息不是 `user` | `{"error":{"code":...,"message":...}}` |
| **404** | 客户端（资源） | 模型名不在清单里 | `{"detail": "..."}` ⚠️ 待办 #6 |
| **422** | 客户端（形状） | 空列表 / `role` 拼错 / 温度越界 | `{"detail":[...]}` ⚠️ 待办 #6 |
| **500** | **我方** | 未预期异常（如上游缺 `id`） | `{"error":{"code":"INTERNAL_ERROR",...,"request_id":...}}` |
| **502** | **上游** | 上游 4xx/5xx 或连不上 | `{"detail": "..."}` ⚠️ 待办 #6 |

> ⚠️ **三种形状并存**是已知缺陷（待办 #6），计划在 Step 11 给 `HTTPException` 与
> `RequestValidationError` 各注册处理器后统一。

---

# Step 7 · 中间件与 CORS

## 定位

> 中间件管的是**"每个请求都要做的事"**：日志、耗时、请求 ID、鉴权预检、跨域头。
> 它的定位和 `Depends` 相似但层次不同：**中间件在路由之外，对所有请求生效**。

## 7.1 洋葱模型

```mermaid
flowchart TB
    C["请求进入"] --> M1["中间件 A 前半段"]
    M1 --> M2["中间件 B 前半段"]
    M2 --> R["路由处理函数"]
    R --> M2b["中间件 B 后半段"]
    M2b --> M1b["中间件 A 后半段"]
    M1b --> O["响应返回"]
```

> 🧒 **人话**：中间件像**洋葱的层**。请求从外往里穿，响应从里往外穿。
> ⚠️ **顺序（2026-10-19 实测订正）**：**最后注册的在最外层**。源码依据：`add_middleware` 用
> `user_middleware.insert(0, ...)` 插到列表头部（`starlette/applications.py:107`），而
> `build_middleware_stack` 用 `for cls in reversed(middleware): app = cls(app)`（同文件 81~82 行）包起来 ——
> 列表头部 = 最外层。实测：先注册 A、后注册 B → 进入顺序 **B → A → 路由**，退出顺序 **A → B**。
> （本条此前写反成"注册在前的先进入"，已订正。）

**中间件 vs 依赖**：

| | 中间件 | `Depends` |
|---|-------|-----------|
| 作用范围 | **所有**请求 | 声明了它的那个路由 |
| 能否拿到路由参数 | ❌ | ✅ |
| 能否改响应 | ✅ | 有限（通过 `Response`） |
| 典型用途 | 日志、请求 ID、CORS、限流 | 认证、数据库会话、分页 |

## 7.2 写一个请求 ID 中间件

```python
import uuid

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    response = await call_next(request)              # ① 交给内层（最终到路由）
    response.headers["X-Request-Id"] = request_id    # ② 拿到响应后加工
    return response
```

**实测**：响应头里确实出现了 `X-Request-Id`。

| # | 要点 |
|---|------|
| ① | `await call_next(request)` 是**必须的** —— 不调用它，请求永远到不了路由 |
| ① | 在这里可以做 `try/except` 统一兜底 |
| ② | 返回前可以改 header、加统一字段 |

> ⚠️ **`@app.middleware("http")` 的函数必须接收 `call_next`，且必须返回 `Response`**。
> 忘了 `await` 或忘了 return，症状是"请求卡住"或"500 无信息"，非常难查。

## 7.3 ⚠️ 中间件两个必踩的坑

**坑 1：执行顺序是"反的"**

```python
@app.middleware("http")
async def a(request, call_next):          # 先注册 → 【内层】
    print("A 进入"); r = await call_next(request); print("A 退出"); return r

@app.middleware("http")
async def b(request, call_next):          # 后注册 → 【外层】
    print("B 进入"); r = await call_next(request); print("B 退出"); return r
```

**实测输出（2026-10-19）**：

```text
B 进入        ← 后注册的先进入（最外层）
A 进入
>>> 路由
A 退出
B 退出
```

> ⭐ **记住**：中间件是**栈**，**后注册的在最外层**（像穿衣服，最后穿的外套在最外面）。
> 源码：`user_middleware.insert(0, ...)` + `for cls in reversed(middleware)`。
> ⚠️ 本条此前写反（"注册在前的先进入"），2026-10-19 实测订正。

### 7.3b `call_next(request)` 到底做了什么（2026-10-19 读源码 + 实测）

```python
response = await call_next(request)
```

| 片段 | 含义 |
|---|---|
| `call_next` | **框架给你的**函数（`BaseHTTPMiddleware` 内部闭包，`starlette/middleware/base.py:112`） |
| `call_next(request)` | "把请求继续往里传" → 内层中间件 → 最终到路由 |
| `await` | 因为内层可能 `async`、可能等 IO |
| `-> Response` | 返回内层产出的响应对象 |

**它内部做的四步**：

```python
task_group.start_soon(coro)                       # ① 后台启动内层 app（路由在跑）
message = await recv_stream.receive()             # ② 等第一条消息
assert message["type"] == "http.response.start"   # ③ 这条 = 状态码 + 响应头就绪
return _StreamingResponse(                        # ④ 用它拼响应
    status_code=message["status"],
    content=body_stream(),                        #    body 是【还没被读的流】
)
```

**两条实测后果**：

```text
outer 后半段 status=200 type=_StreamingResponse          ← 不是普通 Response
GET /stream -> 200 1.9ms request_id=...                  ← 真实耗时 ~150ms，只等到"头就绪"
```

| 能做 | 不能做 |
|---|---|
| ✅ 改 `response.headers`（头已就绪） | ❌ 读 `response.body` / `body_iterator` —— 读一次就把流抽干，SSE 失效 |

**里层报错时**：`call_next` **把异常原样抛出**（源码 `raise app_exc from app_exc.__cause__`），
不会返回 500 响应 —— 500 是**更外层** `ServerErrorMiddleware` 调你的 `Exception` 处理器生成的，
**不会再回到中间件**。所以 `finally` 里的 `response` 可能从未被赋值 → 必须先 `response: Response | None = None`，
否则 `UnboundLocalError` 会盖掉真正的异常（实测）。

### 7.2b 本仓库落地：request_id + 耗时中间件（7a，2026-10-19 实测）

#### ① 代码骨架

```python
logger = logging.getLogger(__name__)


@app.middleware("http")
async def add_request_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """给每个请求分配 request_id：优先沿用上游传来的，没有就新生成，并且记录耗时"""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id            # 异常处理器里也能读到
    response: Response | None = None                 # ⚠️ 必须先给 None
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "%s %s -> %s %.1fms request_id=%s",
            request.method, request.url.path,
            getattr(response, "status_code", "ERR"),   # 异常路径上没有 response
            duration_ms, request_id,
        )
    assert response is not None                      # 正常路径才走得到这里
    response.headers["X-Request-ID"] = request_id
    return response
```

`errors.py` 里配合两处：`request_id = getattr(request.state, "request_id", "") or uuid...`，
以及 500 响应加 `headers={"X-Request-ID": request_id}`（异常路径上中间件拿不到响应对象）。

#### ② ⭐ 验证中间件必须"四看"，只看响应会得到假通过

| 看什么 | 通过标准 |
|---|---|
| 响应头 | `x-request-id` 存在；**带 `-H "X-Request-ID: xxx"` 时应原样返回 `xxx`** |
| 响应体 | 500 时 `request_id` 与响应头**完全相同** |
| **服务端日志** | **每个请求**都有一行 `METHOD path -> status Xms request_id=...`（包括失败的） |
| **traceback 内容** | 是**原始异常**（`KeyError`），不是 `UnboundLocalError` 之类 |

本轮实测：前两条都过了，后两条才是真问题所在。

#### ③ 本轮两个"工具全绿但语义错"的 bug

| bug | 症状 | 根因 |
|---|---|---|
| `"X-Request_ID"`（下划线） | 客户端传 `X-Request-ID: my-trace-001`，响应却是新生成的 ID | HTTP 头名用**连字符**；两个名字不同 → 读不到 → 走 `or` 分支。与 `Bearear` 同一家族：**字符串字面量拼写，静态工具不查** |
| `finally` 里访问未赋值的 `response` | 500 的响应**看起来全对**，但**日志 0 条**，且 traceback 是 `UnboundLocalError` 盖掉了 `KeyError` | 里层抛异常 → `response = ...` 未执行 → `getattr(response, ...)` 先炸。**修法：`response: Response \| None = None`** |

#### ④ 实测日志（修好后）

```text
GET /health -> 200 0.8ms request_id=eac8d766b423
GET /v1/upstream/models -> 200 157.7ms request_id=c68615732f4e      ← 真实调上游，明显更慢
GET /__boom -> ERR 1.1ms request_id=9af3ecfbb812                    ← 失败请求也记录；ERR = 没有响应对象
未处理异常 request_id=9af3ecfbb812 path=/__boom
KeyError: 'datas'                                                   ← 原始异常没被掩盖
GET /v1/models/nope -> 404 1.0ms request_id=3fe2d034cd80            ← 4xx 也走中间件
```

⭐ 两个细节值得记：
- **`ERR` 而不是 `500`**：异常路径上 `response` 是 `None`，中间件**根本不知道**最终会变成 500 ——
  500 是更外层生成的。想要真实状态码，就得在中间件里 `except` 后自己记一个 500，代价是拿不到处理器改过的响应头。
- **`/v1/upstream/models` 157.7ms vs `/health` 0.8ms**：耗时日志立刻暴露"这个接口在等外部世界"，
  这就是访问日志最直接的用处。

#### ⑤ 头名抽成常量：`src/app/constants.py`（2026-10-19）

`X-Request-ID` 被 **3 处**使用（`app.py` 读请求头、`app.py` 写响应头、`errors.py` 给 500 补头）。
写死在多处 = 改一处漏一处，而且**拼错了没人报**。

```python
# src/app/constants.py
HEADER_REQUEST_ID = "X-Request-ID"
```

```python
# app.py / errors.py
from app.constants import HEADER_REQUEST_ID
```

**为什么放 `src/app/` 而不是 `src/app/api/`**：`errors.py` 在 `app/` 层也要用它。
放进 `api/` 就会让 `app/errors.py` **反向 import `app.api`** —— 违反"接口层 → 业务层"的单向依赖。

**实测：哪些差异有语义**

```text
发 X-Request-ID : 读 x-request-id / X-Request-ID 都拿得到   ← 大小写【不敏感】
发 x-request-id : 同上
发 X-Request_ID : 只有 X-Request_ID 拿得到                 ← 下划线是【另一个头】
```

⭐ **结论：大小写不重要，`-` 与 `_` 才重要。**

⚠️ **常量防不住什么**：它只防"多处不一致"，防不住"常量本身一开始就写错"。
第一次定义时仍要对着 RFC / 文档核验 —— 所以 `constants.py` 里那句话写了"必须是连字符不是下划线"。

#### ⑥ 两个常见的读法误区（2026-10-19 澄清）

**误区 1：「`logger.warning(...)` 是在"抛警告"，所以正常请求也会报警」**

不是。`logger.warning(...)` 只是**写一条日志记录**，级别是 WARNING；它的内容是**访问日志**
（`GET /health -> 200 0.8ms request_id=...`），不是"出问题了"。

那为什么用 `.warning` 而不用 `.info`？因为**默认 root 级别是 WARNING，`.info` 会被静默丢弃**
（§6.3b 实测）。这是**临时手段**，属于已知欠账（待办 #7）：Step 11 配好 `logging`（级别 + 格式）后
应降级成 `.info`。⭐ 判据：**日志级别描述"重要性"，不是"有没有出错"**；正常访问日志应当是 INFO。

**误区 2：「`finally` 意味着不管有没有异常都执行 → 所以每次都记一条？」**

"每次都记"是对的，但那**正是访问日志该做的事**；它不等于"每次都报警"。
更重要的是：**不写 `finally` 就会漏掉失败请求**。三种写法实测对比：

| 写法 | 正常请求 | 异常请求 |
|---|---|---|
| 写在 `try` 块**之后**（同一层） | ✅ 记录 | ❌ **跳过**（异常已抛出，后面的语句不执行） |
| 写在 `except` 里 | ❌ 跳过 | ✅ 记录 |
| 写在 **`finally`** 里 | ✅ 记录 | ✅ 记录 |

⭐ 所以 `finally` 的作用是"**两条路径都要覆盖**"，而不是"为了记录异常"。

**副作用（有意接受）**：500 请求会产生**两条**日志 —— 中间件的 `ERR` 行 + 兜底处理器的
`未处理异常 ...` + traceback。前者回答"哪个请求、多久"，后者回答"为什么崩"。

#### ⑦ "静默丢弃"是什么机制（2026-10-19 实测）

`log.info(...)` 不会报错、不会抛异常、**什么都不会发生** —— 这就是"静默"。它要过三道闸：

```text
log.info(msg)
  ├─ 闸 1：logger 的有效级别（logger.level，未设就向上找 root.level）  ← 默认 WARNING
  ├─ 闸 2：每个 handler 的级别（handler.setLevel）
  └─ 闸 3：handler 存在吗？没有 → 用 lastResort（只处理 WARNING 及以上，且【无格式】）
```

实测三层：

| 状态 | `isEnabledFor(INFO)` | `log.info` 的结果 |
|---|---|---|
| 默认（root: WARNING、无 handler） | `False` | 无输出 |
| 加了 handler（级别 DEBUG），root 仍 WARNING | 仍 `False` | 无输出 —— **闸 1 就拦下了，到不了 handler** |
| root 调到 INFO | `True` | 正常输出 |
| root INFO、handler 设成 ERROR | `True` | INFO 仍被 handler 丢弃，只有 ERROR 通过 |

⭐ 判据：**"没打印"分三种原因（级别不够 / 没有 handler / 写错了对象），排查顺序就是上面三道闸。**

#### ⑧ 为什么失败请求的访问日志也用 INFO（2026-10-19 澄清）

> 直觉会说："500 都出来了，怎么还用 INFO？"

因为**一条日志 = 一个事件**，级别描述的是**事件类别的重要性**，不是**本次结果的好坏**：

| 记录 | 记录的是什么事件 | 级别 |
|---|---|---|
| `GET /x -> 500 3.2ms request_id=...` | "**有一个请求被服务了**（结果是 500）" | INFO |
| `未处理异常 request_id=... + traceback` | "**代码崩了**" | ERROR |

**失败详情已经在 ERROR 那条里了**，访问日志那条再有情绪也没有新信息。

若把 4xx/5xx 的访问日志升到 WARNING，会有三个实际麻烦：

| 麻烦 | 说明 |
|---|---|
| 真 warning 被淹没 | 扫描器天天打 404，WARNING 里永远刷屏，真问题看不见 |
| 关不掉访问日志 | 想看"只留异常"就得把 WARNING 关掉，可上游超时那种**真 WARNING** 也一起没了 |
| 同一次 500 两处报警 | 访问日志 WARNING + 处理器 ERROR，告警规则要写两遍去重 |

⭐ 正确做法：**访问日志统一 INFO（带 status 字段），报警靠指标**（5xx 比例、P99 延迟），
而不是靠日志级别。若要区分，最合理的是让 **502（上游故障）** 在翻译处额外打一条 WARNING ——
因为它属于"没坏但要注意"，而是 5xx 里唯一**不是我们 bug** 的。

#### ⑨ `basicConfig(level=INFO)` 的副作用：第三方库也跟着开口（2026-10-19 实测）

`basicConfig` 调的是 **root** 级别，而 root 是所有 logger 的祖先 —— 所以**所有库**的 INFO 也会显示。
实测本仓库的日志里多出这类行：

```text
2026-10-19 16:46:50,976 INFO    httpx | HTTP Request: GET http://testserver/health "HTTP/1.1 200 OK"
```

| 影响 | 判断 |
|---|---|
| 每次调上游都多一行 httpx 日志 | 🟡 其实是**有用**的（能看到"发了什么请求"），但会变吵 |
| 生产环境日志量增加 | ⚠️ Step 11 用 `dictConfig` 给 `httpx` 单独设 `WARNING` 即可 |
| 会不会泄露密钥 | 实测**不会**：httpx 的 INFO 只打 `method url "status"`；httpcore 的 DEBUG trace 打的是 `Request` repr（method/url），**不含 headers** |

⭐ 判据：**改 root 级别 = 改全世界的嗓门**。要精细控制就得 `dictConfig` 按 logger 逐个设级别。

**坑 2：中间件会破坏流式响应** ⚠️⚠️

如果在中间件里**读取了整个响应体**（比如为了记日志）：

```python
@app.middleware("http")
async def log_body(request, call_next):
    response = await call_next(request)
    body = b"".join([chunk async for chunk in response.body_iterator])   # ❌ 灾难
    print(len(body))
    return Response(content=body, ...)
```

**后果**：**流式输出被缓冲成一次性返回，SSE 完全失效**（首字延迟退化成总耗时）。

> ⭐ **这是阶段 1 最值钱的一个坑**：
> 你会觉得"我就是加了个日志中间件，怎么流式就不流了？"
> **正确做法**：日志中间件**只记录状态码和耗时**，不碰响应体。
> 需要完整日志就写进**业务层**（在 SSE 生成器里逐条记）。

## 7.4 CORS：为什么前端会报错

**现象**：浏览器里 `fetch("http://localhost:8000/api")` 报

```text
Access to fetch at 'http://localhost:8000/api' from origin 'http://localhost:5173'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present.
```

**根因**：**浏览器的同源策略**。`localhost:5173`（前端）和 `localhost:8000`（后端）算**不同源**（端口不同）。

> ⚠️ **一个重要认知**：CORS 是**浏览器的限制**，不是服务器的。
> **用 `curl` 不会有任何 CORS 问题** —— 所以你用 curl 测通了，不代表浏览器能通。

**配置**：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],   # ⭐ 别用 ["*"] 配 allow_credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**实测：预检请求（Preflight）通过**：

```text
OPTIONS /chat
Origin: http://localhost:5173
Access-Control-Request-Method: POST
→ 200
  access-control-allow-origin: http://localhost:5173
```

**简单请求 vs 预检请求**：

| 类型 | 触发条件 | 浏览器行为 |
|------|---------|-----------|
| 简单请求 | `GET`/`POST` + 简单头 + `Content-Type` 是表单/文本 | 直接发出，检查响应头 |
| **预检请求** | `PUT`/`DELETE`、自定义头（如 `Authorization`）、`application/json` | **先发 `OPTIONS` 问服务器** |

> ⭐ **对 LLM 应用的实际影响**：你几乎必然带 `Authorization` 头和 `application/json`，
> 所以**每个请求前都会有一个 `OPTIONS` 预检**。预检失败的话，真正的请求根本不会发出。
>
> ⚠️ **两个高频错误**：
> 1. `allow_origins=["*"]` 同时 `allow_credentials=True` → **见下方 7.4b 的实测订正**
> 2. 线上忘了把生产域名加进 `allow_origins` → 本地好的，线上"跨域问题"

### 7.4b 本仓库落地 + 三条实测订正（7b，2026-10-19）

#### ① 落地配置

```python
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # 白名单，不用 "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],   # 只列实际用到的方法
    allow_headers=["*"],
)
```

#### ② 四条验证（`curl` 模拟浏览器）

| # | 请求 | 实测结果 | 说明 |
|---|---|---|---|
| ① | `GET /health` + `Origin: http://localhost:5173` | `200` + `ACAO: http://localhost:5173` + `ACAC: true` + `Vary: Origin` | 白名单命中 |
| ② | 同上，`Origin: http://evil.example.com` | **`200 {"status":"ok"}`**，但 **没有 ACAO** | ⭐ 服务器照发数据，**拦人的是浏览器** |
| ③ | `OPTIONS /v1/chat` + `Access-Control-Request-Method: POST` + `Request-Headers` | `200` `OK` + `allow-methods: GET, POST` + `allow-headers: content-type,authorization` + `max-age: 600` | 预检成功 |
| ④ | `OPTIONS /nope`（**不存在的路径**） | **`200 OK`** | 中间件在**路由之前**就答掉了 |

**额外一条**（我补测）：预检请求非法方法

```text
OPTIONS /v1/chat + Access-Control-Request-Method: DELETE
-> 400 "Disallowed CORS method"
```

⭐ 这条说明：**预检失败是 400，不是 403/405** —— 浏览器看到 400 就直接放弃发真正的请求。

#### ③ ⚠️ 订正：`allow_origins=["*"]` + `allow_credentials=True` 不会被浏览器拒绝

旧说法（本节上方那句）**实测不成立**（Starlette 1.8.0）：

```text
allow_origins=["*"] + credentials=True
  简单请求 ACAO: http://anything.com  | ACAC: true
  预检     ACAO: http://anything.com  | ACAC: true
```

源码依据（`cors.py:163`）：`allow_all_origins and allow_credentials` 为真时，它**回显具体 Origin**
而不是返回 `*` —— 因为规范不允许 `*` 配凭证，Starlette 选择"回显"来满足规范。

**真正的风险不是"被拒绝"，而是"悄悄全放开"**：

| 你以为 | 实际 |
|---|---|
| "我限制了凭证跨域" | **任何网站**都能带用户 Cookie 调你的接口 |
| | **报错你能发现，安全漏洞发现不了** |

⭐ 所以 `allow_origins` 必须写白名单 —— 理由不是"否则会报错"，而是"**否则会静默放开**"。

#### ④ 为什么 ACAO 要"回显"而不是写死

浏览器要求：**`Access-Control-Allow-Origin` 的值必须等于当前页面来源**（或 `*`）。
服务器不知道页面来源，只能 **照抄请求里的 `Origin`**：

```python
headers["Access-Control-Allow-Origin"] = origin   # allow_explicit_origin()
```

配套的 `Vary: Origin` 是给 CDN / 反向代理看的：**同一个 URL 的响应随 Origin 变，别缓存串了**。

#### ⑤ 一个容易被忽略的细节

请求**没带 `Origin`** 时（curl、服务端互调、同源请求），中间件**压根不加任何 CORS 头**
（源码 `if origin is not None:` 才 `headers.update(self.simple_headers)`）。

⭐ 推论：**CORS 头只在"浏览器跨域"这一种场景下存在**，所以它不能用来做"鉴权"或"来源校验" ——
任何人用 curl 加个假 Origin 都能拿到那张"回执"。

## 7.5 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 7 中间件与 CORS）。

---

# Step 8 · 异步的正确姿势

## 定位

> Step 7 的流式坑、Step 9 的 SSE，全都建立在"事件循环不被阻塞"之上。
> 这一段给出**判断该写 `def` 还是 `async def` 的完整决策规则**。

## 8.1 ⭐ `async def` 和 `def` 路由在 FastAPI 里的真实差别

**这是 FastAPI 最容易误解的一点**：

| 你写的 | FastAPI 怎么执行它 | 阻塞事件的后果 |
|--------|------------------|--------------|
| `def route()` | **丢进线程池**执行（`anyio.to_thread`） | 只占用一个线程，**不阻塞事件循环** |
| `async def route()` | **直接在事件循环里**执行 | ⚠️ **整个服务卡死** |

**实测**：`anyio` 默认线程池上限 = **40**（验证方式见 Step 8.4）；超限是**排队**，不是拒绝（§8.4b）。

> ⭐ **反直觉的结论**：
> **在 `async def` 路由里写同步阻塞代码，比写 `def` 路由更糟。**
> 因为 `def` 有线程池兜着（最多卡 40 个并发），`async def` 会把**整个服务**卡住。
> 📎 实测：1 个 300ms 慢请求 + 5 个快请求并发 → 快请求 `13ms` vs `325ms`，**差 25 倍**（§8.4b）。

## 8.2 决策规则（照这个走就不会错）

```mermaid
flowchart TB
    Q1{"用到的库是异步的吗？<br/>（httpx / asyncpg / aiofiles ...）"} -->|是| A["async def + await<br/>✅ 最佳"]
    Q1 -->|否| Q2{"是 CPU 密集吗？"}
    Q2 -->|是| B["def 路由<br/>或丢进进程池/任务队列"]
    Q2 -->|否| C["def 路由<br/>（FastAPI 自动丢线程池）"]
```

| 你的代码 | 推荐写法 |
|---------|---------|
| `await httpx.AsyncClient().get(...)` | `async def` ✅ |
| `requests.get(...)`（同步库） | **`def`**，或用 `run_in_threadpool` |
| `time.sleep(1)` | `await asyncio.sleep(1)`，或 `def` |
| `model.encode(...)`（CPU 密集） | `def`（会被丢线程池），⚠️ 但 GIL 下加速有限 |
| 大量 CPU 计算 | **单独进程 / 任务队列**，不要放在 API 进程里 |

## 8.3 阻塞库的三条出路

```python
# 出路 1：换成异步库（首选）
import httpx
async def f():
    async with httpx.AsyncClient() as c:
        return await c.get(url)

# 出路 2：必须用同步库时，丢到线程池
from starlette.concurrency import run_in_threadpool

async def f():
    return await run_in_threadpool(requests.get, url)

# 出路 3：CPU 密集 → 进程池（绕开 GIL）
from concurrent.futures import ProcessPoolExecutor

async def f():
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as pool:
        return await loop.run_in_executor(pool, heavy_compute, data)
```

| 出路 | 适用 | 代价 |
|------|------|------|
| 换异步库 | IO 密集 | 需要生态支持（`httpx`/`asyncpg`/`aiofiles`/`aiohttp`） |
| `run_in_threadpool` | IO 密集 + 只有同步库，**CPU 密集时无效**（📎 实测 0.96x，GIL） | 线程池上限 **40**，且受 GIL 影响（IO 时释放，仍有效） |
| 进程池 / 任务队列 | CPU 密集 | 序列化开销；任务队列（Celery/RQ/Arq）更工程化。📎 实测进程池 **1.28x**（受核数限制）；⚠️ Windows 上子进程会重新 import `__main__` |

> ⭐ **LLM 应用的典型组合**：
> | 组件 | 用法 |
> |------|------|
> | 调 LLM API | `httpx`（异步）✅ |
> | 调向量库 | 异步客户端（如 `AsyncQdrantClient`）或 `run_in_threadpool` |
> | 本地 embedding 模型 | ⚠️ **CPU 密集** → **独立推理服务**（首选）或任务队列；`run_in_threadpool` 只是"不卡事件循环"，📎 实测**不会变快** |
> | 文档解析（PDF） | ⚠️ CPU 密集 → 后台任务 + 任务队列 |

## 8.4 怎么"看到"阻塞的影响

**验证线程池上限**：

```python
import asyncio, anyio.to_thread

async def show():
    lim = anyio.to_thread.current_default_thread_limiter()
    print(lim.total_tokens)

asyncio.run(show())
# 实测输出：40
```

**验证阻塞的破坏力**（思路）：

```python
@app.get("/blocking")
async def blocking():
    time.sleep(1)          # ⚠️ 事件循环停摆 1 秒
    return {"ok": True}

# 用 10 个并发请求打它 → 总耗时 ≈ 10 秒（完全串行）
# 换成 await asyncio.sleep(1) → 总耗时 ≈ 1 秒
```

> ⭐ **这就是"并发"的实证**：同样的等待时间，写法不同，吞吐差 10 倍。

### 8.4b 本仓库实测：三种写法同台对比（2026-10-19，`playground/blocking_demo.py`）

一个 300ms 的慢接口 + **同时**发 5 个快请求，看**快请求各自被拖成多少**：

```text
阻塞的 async def  慢=318ms | 快请求各自=['325','325','325','325','326']   ← 全被拖慢 ≈25 倍
正确的 async def  慢=328ms | 快请求各自=['13','13','13','13','13']
同步 def          慢=312ms | 快请求各自=['13','13','13','14','14']
```

⭐ **三条结论**：

| # | 结论 |
|---|---|
| 1 | **慢接口本身耗时三者一样**（312~328ms）—— 只看总耗时会以为"没区别" |
| 2 | 差别全在**旁边的人**：快请求 13ms vs 325ms，差 **25 倍** |
| 3 | **`def` 比 `async def`+阻塞更安全** —— 前者有线程池兜底（40），后者拖垮整个进程 |

#### 线程池超限：**排队，不是拒绝**（实测）

```text
total_tokens = 40
45 个并发（每个 0.4s）→ 总耗时 0.87s | 状态全部 200
```

推算：40 个第一批 0.4s + 剩 5 个第二批 0.4s ≈ **0.8s** ✓

⚠️ **这是最危险的一类退化**：没有错误、没有告警，只有**延迟悄悄翻倍**。所以监控要看 **P99 / 排队时长**，不能只看错误率。

#### GIL：线程池对 CPU 密集**无效**（实测）

```text
4 个 CPU 任务：
  串行        0.41s
  线程池并发  0.43s   → 0.96x   ← 没有加速，甚至略慢
  进程池并发  0.33s   → 1.28x   ← 有加速（但受核数限制）
```

| 任务类型 | `run_in_threadpool` | 原因 |
|---|---|---|
| IO 密集（等网络/磁盘） | ✅ 有效 | 等待时**释放 GIL** |
| **CPU 密集**（encode / 解析 PDF） | ❌ **无效** | GIL 保证同一时刻只有一个线程跑字节码 |

⭐ 所以"本地 embedding 放 `run_in_threadpool`"只是**不让它卡事件循环**，**并不会变快** —— 它仍然串行。
真要并行：**独立推理服务**（推荐）或**任务队列**。

⚠️ **Windows 上用 `ProcessPoolExecutor` 的坑**（实测踩到）：子进程会**重新 import `__main__`**，
所以模块级代码（含 `print`）会再跑一遍 —— 我这次看到同一句话打了 **5 次**。
**必须**把入口放进 `if __name__ == "__main__":`。

## 8.5 一条容易犯的隐形错误

```python
@app.get("/items")
async def items():
    result = []
    for q in queries:                        # ⚠️ 看起来异步，其实是串行
        result.append(await fetch(q))        #    每个都等完才发下一个
    return result

@app.get("/items-fast")
async def items_fast():
    return await asyncio.gather(*(fetch(q) for q in queries))   # ✅ 真并发
```

> ⚠️ **`await` 在 `for` 循环里 = 串行**。
> 100 次 LLM 调用 × 2 秒 = 200 秒，而 `gather` 只要 ~2 秒（受并发上限约束）。
>
> ⭐ **但要小心**：`gather` 会**同时**发出所有请求，
> 对 LLM API 可能出现**限流（429）**。工程做法是加**并发上限**：
> ```python
> sem = asyncio.Semaphore(10)
> async def limited(q):
>     async with sem:
>         return await fetch(q)
> result = await asyncio.gather(*(limited(q) for q in queries))
> ```

## 8.6 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 8 异步的正确姿势）。

---

# Step 9 · SSE 流式响应 ⭐⭐

## 定位

> **这是"普通后端"和"LLM 应用后端"的分水岭。**
> 不做流式，你的产品在用户眼里就是"卡住不动"；做了流式，同样的模型、同样的耗时，**体验完全不同**。
>
> 🔁 **复习入口：[§9.9 一条流式请求的全生命周期](阶段1-FastAPI速成.md)（三张全景图）** —— 先看图，再查细节。

## 9.1 为什么 LLM 应用**必须**流式

**先看两个指标**：

| 指标 | 含义 | 典型值 |
|------|------|-------|
| **TTFT**（Time To First Token） | 从发请求到**第一个字**出现 | 0.3 ~ 2 s |
| **总耗时** | 到**最后一个字** | 5 ~ 60 s |

**非流式**：用户盯着 loading 转圈 **20 秒**，然后一次性看到全部文字。
**流式**：用户 **0.5 秒**后开始看到字在跳，**感知速度提升 40 倍**。

> ⭐ **关键洞察**：**用户感知的"快"取决于 TTFT，不取决于总耗时。**
> 总耗时你优化不了多少（模型就那么慢），但 TTFT 你完全可控 ——
> **不加流式，等于白白浪费了模型本身的流式能力。**

**对产品的实际影响**：

| 维度 | 非流式 | 流式 |
|------|-------|------|
| 用户心理 | "是不是卡了？要不要刷新？" | "它在思考，在写" |
| 首字可见 | 总耗时后 | TTFT 后 |
| 中断成本 | 必须等完才能取消 | 看到不对可以立刻停 |
| 长回答（几千字） | 灾难 | 自然 |

## 9.2 SSE 协议格式（很简单）

**响应头**：

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
```

**响应体**（每一帧是一个"事件"）：

```text
data: {"delta": "你"}

data: {"delta": "好"}

data: {"delta": "世界"}

data: [DONE]

```

**规则**：

| 规则 | 说明 |
|------|------|
| 每行以 `字段名: ` 开头 | 常用 `data:`、`event:`、`id:`、`retry:` |
| **空行 = 一帧结束** | ⭐ 所以每帧是 `data: xxx\n\n`（两个换行） |
| `data:` 可跨多行 | 多个 `data:` 行会拼起来 |
| `:` 开头是**注释** | ⭐ 可用来做**心跳保活** |
| 只有 `data:` 是必须的 | 其余可选 |

> 🧒 **人话**：SSE 就是"**服务器一直不关连接，往里面按格式吐字符串**"。
> 它比 WebSocket 简单得多 —— 单向、纯文本、就是 HTTP。
>
> ⭐ `data: [DONE]` 不是协议要求，是 **OpenAI 的约定**（表示"生成结束"）。你自己设计协议时可以换，但**跟主流对齐更省事**。

### 9.2b 这段代码里两个"看起来陌生"的写法（f-string 与 `\n\n`）

9a 里只有两行在造 SSE 帧，先把这两行的每个字符拆开：

```python
yield f"data: {payload}\n\n"      # 291 行
yield "data: [DONE]\n\n"          # 294 行
```

#### ① `f"..."`：`f` 前缀 = "大括号是插槽，不是文字"

| 写法 | `payload` 为 `{"delta": "你"}` 时产出 | 说明 |
|---|---|---|
| `f"data: {payload}\n\n"` | `'data: {"delta": "你"}\n\n'` | `{}` 被**替换成变量的值** |
| `"data: {payload}\n\n"`（没 f） | `'data: {payload}\n\n'` | 大括号**原样输出**，用户看到 `{payload}` 这个词 |
| `"data: " + payload + "\n\n"` | `'data: {"delta": "你"}\n\n'` | 拼字符串能做到同样效果，但啰嗦 |

📎 实测三种写法的 `repr`（`repr` 会把换行显示成 `\n`，见下一条）：

```text
payload 变量里其实是: '{"delta": "你"}'
  有 f: 'data: {"delta": "你"}\n\n'
  没 f: 'data: {payload}\n\n'          ← 大括号原样输出，没有插值
  没 f: 'data: {"delta": "你"}\n\n'    ← 拼字符串能达到同样效果
```

`{}` 里能放什么（实测）：

```python
f"  我叫{name}，今年{age}岁"      →   我叫小明，今年25岁
f"  下次生日我{age + 1}岁"         →   下次生日我26岁          ← 表达式
f"  名字长度{len(name)}"           →   名字长度2               ← 函数调用
```

⚠️ **两个易错点**（实测）：

| 写法 | 结果 | 为什么 |
|---|---|---|
| `f"名字={name}"` | `'名字=小明'` | ✅ 变量直接放 |
| `f"名字={'name'}"` | `'名字=name'` | ❌ 加了引号就成了**字符串字面量**，输出 `name` 这个词 |
| `f"data: {not_exist}"` | `NameError: name 'not_exist' is not defined` | 变量必须真实存在 |
| 想输出真的 `{}` | 双写 `{{}}` → `'data: {{}}\n\n'` | f-string 里单 `{}` 是插槽，`f"data: {}"` 直接 `SyntaxError` |

#### ② `\n`：反斜杠转义 = "换行符本身"

| 你看到的 | 实际存的东西 | 长度 |
|---|---|---|
| `"A\nB"`（源码 4 个符号） | `A` + **换行字符** + `B` | **3** 个字符 |
| `r"A\nB"`（raw 前缀） | `A` + `\` + `n` + `B` | 4 个字符 |

📎 实测：

```text
实际字符串内容: 'A\nB'
实际长度: 3 字符（A、换行、B）
实际字节: b'A\nB'
对比 r 前缀: 'A\\nB' 长度 4
```

⭐ **判据**：`\n` 是**一个字符**，只是源码里用两个符号写出来。`print()` 时它会真的换行。

#### ③ `\n\n` = 两个换行 = "这一帧结束"

这是 SSE 里最要命的一个字符（少一个就整条流失效）：

```text
frame = f"data: {payload}\n\n"
  repr: 'data: {"delta": "你"}\n\n'
  字节: b'data: {"delta": "\xe4\xbd\xa0"}\n\n'
  长度: 22
  结尾几个换行: 2
  用 splitlines 看: ['data: {"delta": "你"}', '']      ← 第二行是空字符串 = 空行
```

📎 **用一个极简 SSE 解析器验证"少一个换行会怎样"**（`split("\n\n")` 切帧）：

```text
--- 正确的两帧 + DONE（每帧 \n\n）---
raw: 'data: {"delta": "你"}\n\ndata: {"delta": "好"}\n\ndata: [DONE]\n\n'
  第 1 个事件: {'data': '{"delta": "你"}'}
  第 2 个事件: {'data': '{"delta": "好"}'}
  第 3 个事件: {'data': '[DONE]'}

--- 只用一个 \n（错误写法）---
raw: 'data: {"delta": "你"}\ndata: {"delta": "好"}\ndata: [DONE]\n'
  第 1 个事件: {'data': '[DONE]'}          ← ⚠️ 只剩 1 个事件
```

⚠️ **注意这个失败的形态**：只写一个 `\n` 时**不报错**，三行全部挤进一帧，客户端只触发 **1 次**
事件，且内容是最后那个 `[DONE]` —— 前端表现为"一个字都没收到"。这就是它被称为
"最经典 SSE bug" 的原因：**症状与原因完全不像**。

#### ④ 为什么 `[DONE]` 那行**没有** `f` 前缀

📎 实测：给它加上 `f`，输出**一模一样**

```text
B 行 repr:      'data: [DONE]\n\n'
B 加 f 前缀:    'data: [DONE]\n\n'     ← 完全一样，因为里面没有 {} 插槽
```

⭐ 判据：**`f` 前缀只在有 `{}` 时才起作用**。没有插槽就加 `f` 不是错，只是多余的噪声
（`ruff` 的 `F541` 规则会把它标出来）。

#### 一句话判据

> **`f` 前缀 = "让 `{}` 变成变量"；`\n` = 一个真实换行字符；`\n\n` = 帧结束符。
> 所以 291 行读作"字段名 data + 冒号空格 + 变量 payload 的值 + 两个换行"。**

### 9.2c ⭐「一帧」到底是什么？为什么假数据要手动 `sleep(0.2)`

学习者问的两个问题，恰好把这套东西最容易被混为一谈的两个维度暴露出来：

1. **一帧是什么？**
2. **既然已经切成帧了，为什么还要 `sleep` 0.2 秒？**

#### ① 「帧」= 一次事件的数据边界，**不是**时间单位

| 维度 | 由什么决定 | 属于哪一层 |
|---|---|---|
| **一帧的边界在哪** | `\n\n`（协议层分隔符） | SSE 协议 |
| **帧与帧之间隔多久** | **生产者的速度**（你的 `await`） | 你的业务代码 / 上游模型 |

⭐ 一句话：**帧是"一条消息"，不是"一个时刻"**。
把一份数据切成 3 帧还是 1 帧，跟"总共用多久"**没有任何关系**。

📎 实测三组（同一句 9 个汉字，端口 8097/8098）：

| 接口 | 帧数 | `ttfb` | `total` | 说明 |
|---|---|---|---|---|
| 每字一帧 + 每帧 `sleep(0.2)` | 10 | `0.026` | **`1.861`** | 时长 = 9 × 0.2 |
| **整句一帧** + 只 `sleep` 两次 | **2** | `0.001` | **`0.383`** | 帧少但总时长由 sleep 决定 |
| **200 帧**，完全不 sleep | **201** | `0.001` | **`0.002`** | 帧极多但 2 **毫秒**发完 |

⭐ 结论：**帧数多 ≠ 慢，帧数少 ≠ 快**。上面三行的"帧数"和"总时长"完全无关。

#### ② `sleep` 控制的是"帧到达的时刻"，📎 用带时间戳的客户端验证

同一个 `/v1/chat/stream` 式接口（每字一帧），两种写法对比：

```text
===== 无 sleep（/sleep0）=====
  响应头到达: 67.6ms
  第 1 帧 @    67.7ms  'data: {"delta": "你"}'
  第 2 帧 @    67.7ms  'data: {"delta": "好"}'
  第 3 帧 @    67.7ms  'data: {"delta": "，"}'
  ……（9 帧全部落在同一毫秒）
  第 10 帧 @    67.8ms  'data: [DONE]'
  总耗时: 67.9ms, 共 10 帧

===== 有 sleep(0.2)（/sleep02）=====
  响应头到达: 29.3ms
  第 1 帧 @    29.5ms  'data: {"delta": "你"}'
  第 2 帧 @   230.9ms  'data: {"delta": "好"}'      ← +201ms
  第 3 帧 @   448.3ms  'data: {"delta": "，"}'      ← +217ms
  第 4 帧 @   649.6ms  'data: {"delta": "我"}'
  第 5 帧 @   834.8ms  'data: {"delta": "是"}'
  ……
  第 10 帧 @  1845.7ms  'data: [DONE]'
  总耗时: 1846.6ms, 共 10 帧
```

⭐ **两版的"帧内容、帧数量"一模一样，只有"帧到达的时刻"不同** —— 而时刻完全由那个 `sleep` 决定。

#### ③ 那假数据为什么非要手动 sleep？

因为**假数据算得太快**：`json.dumps("你")` 是**微秒级**，9 个字符在 1 毫秒内全算完。
于是虽然帧还是 10 个、`chunked` 也照样分块，但**全部挤在同一毫秒到达** ——
人眼看不到"一个字一个字蹦"，也就**没法用肉眼/`curl` 验证"边算边发"这条管子通没通**。

| 场景 | 谁在提供"帧之间的延迟" | 需要手动 sleep 吗 |
|---|---|---|
| **假数据**（9a） | 没有人 —— 数据凭空产生 | ✅ **必须**，否则测不出流式 |
| **真实 LLM 上游**（9b） | **上游自己**：模型生成一个字就要几十毫秒 | ❌ **不需要**，`await` 上游 chunk 本身就是等待 |
| 从数据库/文件读 | 磁盘 IO（已经是 `await`） | ❌ 不需要 |

📎 **实测证据**（端口 8096，`event_source` 里**一行 sleep 都没有**，只是转发一个"每 0.15s 才产出一块"的假上游）：

```text
ttfb=0.032588 total=0.640263      ← 总时长 ≈ 4 × 0.15

  头到达 @  79.2ms
  第 1 帧 @ 233.8ms  'data: 你'
  第 2 帧 @ 387.3ms  'data: 好'
  第 3 帧 @ 543.7ms  'data: 世'
  第 4 帧 @ 699.9ms  'data: 界'
  第 5 帧 @ 700.6ms  'data: [DONE]'
```

⭐ **"节流"来自上游的等待，不是来自你写的 sleep**。9a 的 `sleep(0.2)` 是**替身演员**：
它扮演的正是"上游模型吐一个字要 200ms"这件事。9b 接真上游后，这个 `sleep` 会**被删掉**。

#### ④ 两条判据（别混）

> **`\n\n` 决定"帧在哪结束"（数据边界）；`await` 决定"下一帧什么时候到"（时间轴）。
> 假数据自己造不出延迟，所以要 `sleep` 替身；真上游自带延迟，所以 `sleep` 要删掉。**

### 9.2d ⭐ 分工：异步生成器 vs `StreamingResponse`（谁干了哪一半）

学习者问：**"流式输出不都是异步生成器干完了吗？`StreamingResponse` 干了啥？"**

答案：**生成器一行网络代码都没有，它只管"产出"，一根字节都发不出去。**

#### ① 硬证据：同一个 `event_source` 用在三个完全不同的地方

📎 实测（同一个生成器函数，三次都跑通）：

| 用法 | 怎么用 | 结果 |
|---|---|---|
| ① 交给 `StreamingResponse` | `StreamingResponse(event_source(), ...)` | 变成 **HTTP 流**：`'data: {...你}\n\ndata: {...好}\n\ndata: [DONE]\n\n'` |
| ② 自己 `async for` 收集 | `[f async for f in event_source()]` | 变成**普通 list**（3 个字符串） |
| ③ 直接 `print` | `async for f in event_source(): print(f)` | 变成**终端文字**（一行一行打出来） |

⭐ **同一个生成器，既可以是 HTTP 流、也可以是 list、也可以是终端输出** —— 所以它**完全不知道 HTTP 存在**。

| 职责 | 谁负责 | 具体做什么 |
|---|---|---|
| **产出什么内容** | 你的异步生成器 | 拼 `data: ...\n\n`，决定帧、决定 `[DONE]` |
| **发到网络上** | `StreamingResponse` | 写 socket：状态码、头、每个 chunk、结束信号 |
| **多久产一帧** | 你的 `await`（或上游） | 生产者速度 |

#### ② `StreamingResponse` 的完整工作清单（📎 抓 ASGI 消息实测）

用假 `send` 把它发出的每一条消息记下来：

```text
① 它自动发出的 http.response.start：
   status = 200
   headers =
     cache-control                  no-cache
     x-accel-buffering              no
     content-type                   text/event-stream; charset=utf-8     ← 自动补了 charset

② 它逐帧发出的 http.response.body：
   1) body=b'data: 0\n\n'       more_body=True
   2) body=b'data: 1\n\n'       more_body=True
   3) body=b''                  more_body=False      ← 流结束信号
```

⭐ 注意 **`more_body=False`** 是它**自己补的**，你的生成器从没产出过这个东西。
没有这一条，客户端会一直"等后续数据"。

所以 `StreamingResponse` 干了 5 件事：

| # | 干什么 | 不写它会怎样 |
|---|---|---|
| 1 | 发 `http.response.start`（状态码 + 头） | 客户端拿不到响应头 |
| 2 | 自动补 `content-type: text/event-stream; charset=utf-8` | 浏览器不认这是 SSE，`EventSource` 直接报错 |
| 3 | `async for chunk in body_iterator` **驱动生成器** | 生成器永不执行（📎 实测：造出对象等 0.5 秒，函数体一行都没跑） |
| 4 | 每帧 `send(..., more_body=True)`，`str` 自动 `.encode("utf-8")` | 你得自己编码、自己 `send` |
| 5 | 补最后一条 `more_body=False` | 客户端卡住等连接关闭 |
| 6 | （额外）监听 `http.disconnect`，客户端断开就取消任务 | 用户走了你还在烧 token |

#### ③ 把它拆掉会怎样？📎 手写裸 ASGI 实测

不用 `StreamingResponse`，直接当 ASGI app 写（端口 8095）：

```python
async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    # ① 自己发状态码 + 头
    await send({"type": "http.response.start", "status": 200, "headers": [
        (b"content-type", b"text/event-stream; charset=utf-8"),
        (b"cache-control", b"no-cache"),
    ]})
    # ② 自己驱动生成器（这就是 StreamingResponse 里那句 async for）
    async for frame in event_source():
        await send({"type": "http.response.body", "body": frame.encode(), "more_body": True})
    # ③ 自己发结束信号
    await send({"type": "http.response.body", "body": b"", "more_body": False})
```

📎 实测结果 —— **真的能流**：

```text
content-type: text/event-stream; charset=utf-8
cache-control: no-cache
transfer-encoding: chunked              ← uvicorn 看到 more_body=True 自动加的

ttfb=0.011686 total=0.415572            ← 确实逐帧

data: {"delta": "你"}

data: {"delta": "好"}

data: [DONE]
```

⭐ **结论**：`StreamingResponse` 不是魔法，它就是**上面这段样板的封装**。
你少写的每一行，都是它在替你写 —— 而且它还额外管了"客户端断开"这件你没写的事。

#### ③b ⭐ 学习者追问："我的 `app.py` 里没有 `async for` 也没有 `next()`，到底谁在推进？"

**对，你的文件里没有 —— 它在 starlette 的源码里。**

📎 **铁证**：在 `event_source` 第一行打印调用栈，起真 uvicorn（端口 8094）打一次请求，
服务端打出的真实栈（截尾部，前面还有 uvicorn → anyio 一长串）：

```text
  anyio/_core/_tasks.py:327  in _run_coro
      -> retval = await self._coro
  starlette/responses.py:279  in wrap
      -> await func()
  starlette/responses.py:253  in stream_response
      -> async for chunk in self.body_iterator:          ← ★ 就是这一句
  who_pulls.py:14  in event_source
      -> for fr in traceback.extract_stack():
```

| 栈帧 | 说明 |
|---|---|
| 最后一行 | **你的 `event_source`**（被唤醒的那一刻） |
| 倒数第二行 | **`starlette/responses.py:253`**：`async for chunk in self.body_iterator:` |
| `self.body_iterator` 是什么 | 就是 `event_source()` 返回的那个生成器对象 —— `StreamingResponse.__init__` 里 `self.body_iterator = content`（`responses.py:237`） |

⭐ **所以那个 `async for` 客观存在，只是写在别人的文件里**。你 `app.py` 里能看到的
`for ch in "你好，我是流式输出"` 遍历的是**字符串**，跟"推进生成器"没有关系。

**一句话**：`StreamingResponse(event_source(), ...)` 这一句 = "把生成器交出去"，
交出去之后由框架遍历；你只写"产出函数"，框架写"遍历循环"。

> 🧒 **人话**：`event_source` 是一根**水龙头**，拧它的是框架。
> 你只负责"拧开后有水流出来"，拧的动作在 `starlette/responses.py:253`。

#### ④ 一句话判据

> **生成器只管"产出"，`StreamingResponse` 管"上网"。
> 生成器不碰 socket，`StreamingResponse` 不碰内容 —— 一个好管子，一个负责往里灌水。**

## 9.2e ⭐ 四个单位：token / 帧 / 行 / 字节块（2026-10-23 实测，回答「流式输出哪里还有行」）

> **起因**：学习者问「上游是生成一个 token 就返回一个吗？`aiter_lines` 也是按 token 返回吗？流式输出哪里还有行这个概念？」
> 这三个问题其实是同一件事：**你没分清自己在看哪一层**。

### ① 一句话答案

> **「行」是 SSE 协议的分帧符，不是内容里的换行。**
> 模型真的输出了换行，但上游用 `json.dumps` 把它**转义**成 `\n` 两个字符，
> 所以**一帧永远只是一行文本** —— 内容再多行也压不破协议结构。

### ② 四个单位，数量互不相等

```text
① 模型层：token
      ↓ 上游把若干 token 打包成一条 JSON，包成 "data: {...}\n\n"
② 文本层：字节（UTF-8）
      ↓ TCP 分片 + gzip 压缩 + chunked 编码
③ 传输层：字节块（httpx 一次 recv 拿到的东西）
      ↓ httpx 解压 + UTF-8 增量解码 + 按 \n 切
④ 协议层：行（aiter_lines 给你的东西）
      ↓ 我们剥 data: 前缀、跳过空行、json.loads
⑤ 业务层：帧（aiter_chunks 给你的 dict）
```

📎 **同一次真实请求的实测计数**（2026-10-23，`deepseek-flash`，
prompt = "用三行回答，每行一个词：苹果、香蕉、橘子。不要编号，不要解释。"）：

| 单位 | 数量 | 用什么量的 |
|---|---|---|
| 原始字节块（**仍是 gzip 压缩态**） | **15** | `aiter_raw()` |
| 解压后字节块 | **13** | `aiter_bytes()` |
| 行 | **150** | `aiter_lines()` |
| 其中 `data: ...` 行 | **75** | 每行 = 一个 SSE 事件 |
| 其中空行 `''` | **75** | 每帧的分隔符 |
| 其中**真正给用户看的** content 帧 | **6** | 过滤 `delta.content` 是字符串 |

> ⭐ **13 个字节块 → 75 帧 → 6 个可见片段。三个数字都不相等。**
> 「一层等于另一层」的想法，从第一步就断了。

📎 **一个字节块里常常有好几个完整帧**（`aiter_bytes` 的原始观测）：

```text
块#1  @ 0.279s   316B  含完整帧(\n\n)=1
块#4  @ 1.032s  1207B  含完整帧(\n\n)=4     ← 一个字节块里 4 帧
块#8  @ 1.037s  1798B  含完整帧(\n\n)=6     ← 一个字节块里 6 帧
块#13 @ 1.085s   537B  含完整帧(\n\n)=2
```

### ③ 铁证：内容里有换行，但那一行里没有换行符

模型输出了三行（苹果 / 香蕉 / 橘子），逐帧还原原始行文本后检查：

```text
原始行里的片段 = 'content":"\\n","reasoni'      ← 反斜杠 + n，两个字符
json.loads 之后 content = '\n'  长度=1  是换行符=True
这一行里有真实换行符吗: False                     ← ★★★
```

| 层 | 换行长什么样 |
|---|---|
| 模型输出 | 真换行符 `\n`（1 个字符） |
| 上游 JSON 文本 | 转义成 `\` + `n`（**2 个字符**） |
| 我们 `json.loads` 之后 | 又变回真换行符 `\n`（1 个字符） |

⭐ **推论 1**：SSE 的「行」纯粹是**协议的结构**，与内容无关。内容再多行，也不会产生第二行文本。

⭐ **推论 2（危险的反面）**：**如果上游不转义**（坏实现），`data: {"content":"苹果<真换行>香蕉"}`
就会被 `aiter_lines` 切成两行 →

```text
data: {"content":"苹果          ← 第 1 行
香蕉"}                          ← 第 2 行：不以 data: 开头 → 被我们跳过 → 内容丢失
```

所以 `startswith("data:")` 不只是「过滤注释行」，**它同时是防止坏上游污染数据的守卫**。
这也解释了为什么判据是「**判定看字段名，不看格式细节**」。

### ④「一个 token 一帧」是真的吗？—— 部分真，但不能依赖

📎 **观测到的一 token 一帧**（`reasoning_content`，注意每帧只有一个 token）：

```text
'reasoning_content":"We"'
'reasoning_content":" need"'        ← 注意前导空格！
'reasoning_content":" answer"'
'reasoning_content":" in"'
'reasoning_content":" Chinese"'
...
'reasoning_content":"、"'
'reasoning_content":"橘子"'
'reasoning_content":"。"'
```

⭐ `" need"` **带一个前导空格** —— 这是 BPE tokenizer 的典型特征（空格粘在下一个词上）。
**这就是「token ≠ 字」的直观证据。**

📎 另一组实测：让模型「从 1 数到 3」，收到的帧是
`"1"` / `" "` / `"2"` / `" "` / `"3"` —— **空格单独成帧**，同一现象。

**但不能假设「一帧 = 一个 token」**，三个理由：

| # | 理由 | 后果 |
|---|---|---|
| ① | 实现自选粒度：推理引擎可以「攒 N 个 token 再刷」（vLLM 的 `--stream-interval` 之类），OpenAI 也会合批 | 一帧可能装好几个 token |
| ② | 一帧可以**没有内容**：`role` 帧、纯 `usage` 帧、`finish_reason` 帧的 `content` 都是 `null` | 帧数 ≠ token 数 |
| ③ | **到达一定是成批的** | 📎 实测 `1.945s` 那一瞬间到了 **10 行**（5 帧），`1.982s` 到了 **12 行**（6 帧） |

第三条最容易被误解：

```text
生成侧：可能真的是「一个 token 算完就写出去」
到达侧：操作系统缓冲 + gzip + chunked 会把它们攒成一批给你
```

⭐ 所以「用户看到逐字出现」靠的**不是**「网络一帧一帧送」，而是「上游**持续在产生**」。
哪怕 3 帧一起到达，前端一次渲染 3 个字，视觉上仍是「一个字一个字长出来」。

### ⑤ 那为什么不自己切字节，要用 `aiter_lines`？

因为「字节 → 行」有四个坑，httpx 已经替你填了：

| 坑 | 例子 |
|---|---|
| 多字节字符被切开 | 一个汉字 3 字节，可能第 1 字节在上一个字节块、第 2~3 个在下一个（📎 本次抓包里真出现了 `\xe8\x8b\xb9\xe6\x9e\x9c` 被分块） |
| 半行 | 一个字节块可能只有 `data: {"id":"fac` |
| gzip 压缩 | 上游 `content-encoding: gzip`，`aiter_raw` 给你的是**压缩字节**，不能当文本用 |
| `\r\n` | 有些服务端用 CRLF，切行时要一起去掉 |

`aiter_lines()` 的实际调用链（读源码可得）：

```text
aiter_lines()  →  aiter_text()  →  aiter_bytes()  →  aiter_raw()
   切行             UTF-8 解码       解压 gzip        原始网络字节
```

⭐ **判据**：`aiter_raw` 是「网络给了什么」，`aiter_lines` 是「文本读起来像什么」。
**在流式里这两个永远不相等。**

### ⑥ 这个结论解释了我们项目里的三个设计

| 设计 | 为什么必须这样 |
|---|---|
| `aiter_chunks` 里 `startswith("data:")` + `lstrip()` | 因为 line 是**文本单位**，`data:` 是**协议标记**，两者靠字符串处理连接 |
| 用 `content_frames` 计「内容帧」而不是「token」 | 一帧可能没内容、可能有多个字，**只有「有没有内容」是稳定的** |
| `text` 不是 `str` 时只 warning 不中止 | 上游可能改成多模态数组（`[{"type":"text","text":"hi"}]`），**一帧里装的是结构不是 token** |

### ⑦ 一句话判据（三条）

1. **token → 帧 → 行 → 字节块，是四个不同单位，数量互不相等。**（📎 本次：6 片段 / 75 帧 / 150 行 / 13 字节块）
2. **「行」是 SSE 协议的分帧符，不是内容里的换行**（内容换行被 JSON 转义成 `\n` 两个字符）。
3. **生成可能一 token 一帧，但到达一定成批。** 代码里任何地方都不能假设「一帧 = 一个 token」。
## 9.3 实现：`StreamingResponse` + 异步生成器

```python
import asyncio
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


@app.post("/v1/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    async def event_source() -> AsyncIterator[str]:
        for ch in "你好世界":
            payload = json.dumps({"delta": ch}, ensure_ascii=False)
            yield f"data: {payload}\n\n"        # ① 每帧以 \n\n 结束
            await asyncio.sleep(0)              # ② 让出控制权（真实场景是 await LLM）
        yield "data: [DONE]\n\n"                # ③ 结束标记

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",         # ④ 必须
        headers={
            "Cache-Control": "no-cache",        # ⑤ 禁止缓存
            "X-Accel-Buffering": "no",          # ⑥ 关掉 nginx 缓冲
        },
    )
```

**⭐ 实测输出**（用真实 uvicorn + curl `-N`，逐帧到达）：

```text
data: {"delta": "你"}

data: {"delta": "好"}

data: {"delta": "世"}

data: {"delta": "界"}

data: [DONE]
```

**逐点解释**：

| # | 要点 |
|---|------|
| ① | `\n\n` 是帧分隔符，**少一个换行客户端就不会触发事件**（最经典的 SSE bug） |
| ② | 真实场景这里是 `async for chunk in llm_client.stream(...)`。`await asyncio.sleep(0)` 只是让出控制权的演示 |
| ③ | 结束标记。前端收到它就关闭连接 |
| ④ | `media_type="text/event-stream"` → 浏览器才知道这是 SSE |
| ⑤ | 防止中间层缓存（代理/CDN 可能把流缓存成一次性响应） |
| ⑥ | ⭐ **nginx 默认会缓冲响应**，不关掉的话你前端的"流式"会变成"一次性" |

> ⭐ **`json.dumps(..., ensure_ascii=False)` 很重要**：
> 默认 `ensure_ascii=True` 会把中文转成 `\u4f60\u597d`（能用但浪费带宽、难调试）。
> 但注意：**如果帧里有换行符，会破坏 SSE 格式**！所以要么 `ensure_ascii=True`，
> 要么把内容里的 `\n` 转义掉 —— 用 JSON 序列化天然会把 `\n` 转成 `\\n`，所以安全。

### 9.3a 彻底搞懂「异步生成器」（2026-10-19 补，六组实测）

> 起因：学习者反馈"异步生成器还是没看懂"。根因是**跳过了普通生成器这一层**，直接从
> `async def` + `yield` 开始。正确顺序是：**普通函数 → 生成器 → 异步生成器 → 谁在拉它**。

#### 第 0 层：一张表说清四个概念

| 写法 | 调用后得到什么 | 函数体何时执行 | 能 `await` 吗 |
|---|---|---|---|
| `def f()` | 返回值 | 立刻执行完 | ❌ |
| `def f(): ... yield x` | **生成器对象** | **不执行**，等被 `next()` | ❌ |
| `async def f()` | **协程对象** | **不执行**，等被 `await` | ✅ |
| `async def f(): ... yield x` | **异步生成器对象** | **不执行**，等被 `__anext__()` | ✅ |

⭐ 一句话：**`async def` 决定"能不能 await"，`yield` 决定"能不能暂停交出一段"**。两个一叠加就是异步生成器。

#### 第 1 层：生成器 = 能暂停的函数（`yield` vs `return`）

📎 实测（普通函数 vs 只差一个 `yield` 的生成器）：

```text
=== 普通函数 ===
  准备调用 normal()
  [normal 函数体开始执行]     ← 调用时立刻执行
    正在处理 A / B / C
  [normal 函数体执行完毕]
  调用返回了: ['A', 'B', 'C'] （类型: list）

=== 生成器函数 ===
  准备调用 generator()
  调用返回了: <generator object generator at 0x...> （类型: generator）
  >>> 没有任何 [函数体…] 输出！函数体根本没跑
  现在开始一帧一帧地取（手动 next）:
  [generator 函数体开始执行]
    即将交出去 A
  next(g) -> A                ← 才跑了第一段就停住
    即将交出去 B
  next(g) -> B
    即将交出去 C
  next(g) -> C
  [generator 函数体执行完毕]
  第 4 次 next(g) -> StopIteration（生成器结束了）
```

| | `return x` | `yield x` |
|---|---|---|
| 函数结束了吗 | **结束**，帧销毁 | **没结束**，冻在原地 |
| 局部变量 | 随帧销毁 | **还在**（下次从这里继续） |
| 能再来一次吗 | 再调用一次即可 | `next()` 从 `yield` 下一行继续 |
| 调用几次 | 1 次 1 个结果 | 1 次调用 → N 个结果 |

📎 **"冻结"的硬证据**（`inspect.getgeneratorstate` + `gi_frame.f_locals`）：

```text
=== 刚创建 ===
  状态: GEN_CREATED
  局部变量快照: 还没有 frame        ← 连栈帧都没建

=== 第一次 next ===
    进入循环体, i=0
  拿到: 0
  状态: GEN_SUSPENDED              ← 停住了，不是死了
  局部变量: {'n': 3, 'i': 0}       ← 变量还在！

=== 第二次 next ===
    从 yield 恢复, 现在 i=0 → 即将 i+=1     ← 从 yield 的下一行继续
    进入循环体, i=1
  拿到: 1
  局部变量: {'n': 3, 'i': 1}

=== 第四次 next ===
  [循环结束，函数即将正常返回]
  StopIteration
  状态: GEN_CLOSED
  frame 还在吗: None               ← 彻底销毁
```

⭐ **状态机只有三态**：`GEN_CREATED`（造好没跑）→ `GEN_SUSPENDED`（冻在 yield）⇄ → `GEN_CLOSED`（走完/出错）。

⭐ **`for` 循环就是 `next()` 的语法糖**：`for x in g` ≈ 反复 `next(g)` 直到 `StopIteration` 被吞掉。

#### 第 2 层：为什么 9a 必须用「异步」生成器

📎 实测两条 `SyntaxError`：

```text
def bad():
    await asyncio.sleep(1)      → SyntaxError: 'await' outside async function (第 2 行)

def half():
    yield 1
    await asyncio.sleep(1)      → SyntaxError: 'await' outside async function (第 3 行)
```

推导链（**只有一条路走得通**）：

1. 9a 里必须 `await asyncio.sleep(0.2)`（否则瞬间发完，测不出流式；真实场景是 `await` 上游 chunk）
2. `await` 只能出现在 `async def` 里 → 外层必须 `async def`
3. 但同时要**每算出一段就交出去** → 必须 `yield`
4. `async def` + `yield` = **异步生成器**（唯一解）

📎 异步生成器对象与普通生成器的接口对照：

```text
类型: async_generator
有 __aiter__ / __anext__: True True     ← 异步世界用这一对
有 __iter__ / __next__ 吗: False False  ← 这两样都没有，所以不能 for，只能 async for
```

`async for` ≈ 反复 `await g.__anext__()`，直到 `StopAsyncIteration`。

#### 第 3 层：谁在拉？（"管子"的真相）

生成器**自己不会跑**，必须有人反复问它要下一帧。这个人就是 `StreamingResponse`。
📎 源码 `starlette/responses.py:253-258`：

```python
await send({"type": "http.response.start", ...})      # 先发状态码 + 头
async for chunk in self.body_iterator:                # ← 就是这里在"拉"
    if not isinstance(chunk, bytes | memoryview):
        chunk = chunk.encode(self.charset)            # str → utf-8 字节
    await send({"type": "http.response.body", "body": chunk, "more_body": True})
await send({"type": "http.response.body", "body": b"", "more_body": False})   # 收尾
```

⭐ **拉模式（pull）**：不是生成器"推"，是框架**一帧一帧地要**。

```text
客户端                Starlette                    你的 event_source()
  |                       |                                |
  |---- GET /v1/chat/stream --->                          |
  |                       |-- 造出生成器对象（此刻 0 行代码执行）->|
  |<-- 200 + 头（chunked）--|                                |
  |                       |-- await __anext__() ----------->|
  |                       |                                | 算第 1 帧 → yield
  |                       |<------------ "data: 你\n\n" ----|
  |<==== 立刻写 socket ==== |                                |
  |                       |-- await __anext__() ----------->| 从 yield 下一行继续
  |                       |                                | await sleep(0.2) ...
  |                       |<------------ "data: 好\n\n" ----|
  |<==== 立刻写 socket ==== |                                |
  |         ……            |            ……                  |
  |                       |<------------ StopAsyncIteration |
  |<---- more_body=False -|                                |
```

⭐ **这就是"边算边发"的全部机制**：每 `yield` 一次，`await send` 一次。算得慢 → 发得慢 → 用户看到字一个一个蹦。

#### 第 4 层：不写生成器会怎样（📎 用一个假 `send` 抓内部消息）

| 传给 `StreamingResponse` 的东西 | 实测 `http.response.body` 次数 | 内容 |
|---|---|---|
| `"你好ABC"`（str） | **6 次** | `b'\xe4\xbd\xa0'`、`b'\xe5\xa5\xbd'`、`b'A'`、`b'B'`、`b'C'`、`b''` |
| `["a", "b"]`（list） | 3 次 | `b'a'`、`b'b'`、`b''` |
| 异步生成器 | 3 次 | `b'data: 1\n\n'`、`b'data: 2\n\n'`、`b''` |

⚠️ **传 str 不报错，只是"按字符发"**（`starlette/responses.py:239` 会走
`iterate_in_threadpool`）—— 又一个"工具全绿但行为荒唐"的例子。而且 str 早就整串在内存里，
**根本没有"边算边发"**，只是把发送切碎了而已。

#### 第 5 层：生成器是一次性的（📎 别放模块级！）

```text
第一次遍历: [0, 1, 2]
同一个对象再遍历: []          ← 空的！
对比：每次重新调用 agen() → 每次都 [0, 1, 2]
```

⚠️ 实测"模块级复用"的后果：

```text
请求 1 拿到: [0, 1, 2]
请求 2 拿到: []              ← 用户看到空回答
```

⭐ 所以 `event_source()` **必须在请求处理函数体内被调用**（9a 就是这么写的）—— 每个请求
新建一个生成器对象。若写成模块级 `SHARED = event_source()`，第二个用户就没有输出了。

#### 第 6 层：`for` 循环**外**的 `yield` 也是"推进点"（📎 逐次唤醒实测）

学习者问：**"第二个 `yield` 没包在 `for` 里，岂不是只会暂停不会推进？"**

这是把"**循环**"当成了"**推进机制**"。真正的推进机制是**外部的 `__anext__` 调用**，
`for` 只是恰好调用它的语法糖。循环外的 `yield` 一样被推进，只是**只推进一次**。

📎 实测（每行都带日志，看它被唤醒了几次）：

```python
async def source():
    print("  [1] 进入函数体")
    for i in range(3):
        print(f"  [2] for 内部：准备 yield {i}")
        yield f"帧{i}"
        print(f"  [3] 被唤醒：从 'yield 帧{i}' 的下一行继续（for 下一轮）")
    print("  [4] for 循环结束，走到 yield 'DONE' 这一行")
    yield "DONE"
    print("  [5] 被唤醒：从 'yield DONE' 的下一行继续 → 函数体结束")
    print("  [6] 函数即将 return")
```

输出：

```text
=== 造出生成器对象后，什么都没发生 ===

--- 第 1 次 __anext__() ---
  [1] 进入函数体
  [2] for 内部：准备 yield 0
  >>> 拿到 '帧0'

--- 第 2 次 __anext__() ---
  [3] 被唤醒：从 'yield 帧0' 的下一行继续（for 下一轮）
  [2] for 内部：准备 yield 1
  >>> 拿到 '帧1'

--- 第 3 次 __anext__() ---
  [3] 被唤醒：从 'yield 帧1' 的下一行继续（for 下一轮）
  [2] for 内部：准备 yield 2
  >>> 拿到 '帧2'

--- 第 4 次 __anext__() ---
  [3] 被唤醒：从 'yield 帧2' 的下一行继续（for 下一轮）
  [4] for 循环结束，走到 yield 'DONE' 这一行      ← 循环外的 yield 也被推进到了
  >>> 拿到 'DONE'

--- 第 5 次 __anext__() ---
  [5] 被唤醒：从 'yield DONE' 的下一行继续 → 函数体结束
  [6] 函数即将 return
  -> StopAsyncIteration（再也要不出东西了）
```

⭐ **判据**：`yield` 被推进几次，**与它在不在循环里毫无关系**。
循环让语句**被重复执行**，于是里面的 `yield` 有机会被唤醒多次；循环**外**的 `yield`
只会被执行到**一次**，所以只产出**一帧**，之后函数走到末尾 → `StopAsyncIteration`。

| 位置 | 产出几帧 | 为什么 |
|---|---|---|
| `for` 内部 | 每循环一次 1 帧 | 循环让它被反复执行 |
| `for` 外部（只写一次） | **恰好 1 帧** | 只执行一次 |
| `while True` 内部 | 无限帧（要有 `break`） | 无限重复 |

> ⚠️ 注意：`StopAsyncIteration` 不是错误 —— 它是"正常结束"的信号，
> `StreamingResponse` 收到它就补上 `more_body=False` 收尾。

#### 一句话判据

> **`yield` = "交出并冻结"，`async for` = "反复唤醒它"；
> `StreamingResponse` 是那个不停唤醒它、每拿到一段就立刻写 socket 的消费者。
> 流式不是"生成器在推"，而是"框架在一帧一帧地拉"。**

### 9.3b 本仓库落地 + 三条硬证据（9a，2026-10-19 实测）

#### ① 落地代码要点

`src/app/api/app.py` 的 `GET /v1/chat/stream`（假数据版，真模型留到 9b）。

> ⚠️ **2026-10-20 更新**：9b-2 已把它改成 **`POST /v1/chat/stream`**（真调上游 `stream=true`），
> 假数据版本已删除，只保留在 git 历史（提交 `5086569`）中。本节 ②~⑥ 的实测数据**仍然成立**
> —— 它们测的是"SSE 管道"本身（格式 / 时序 / 代理缓冲），与上游无关。

#### ② 证据 1：响应头 —— 关键是 `transfer-encoding: chunked`

```text
content-type: text/event-stream; charset=utf-8
cache-control: no-cache
x-accel-buffering: no
transfer-encoding: chunked            ← 没有 Content-Length 才能"边发边传"
vary: Origin
x-request-id: 7f11cbbd8f36
```

⭐ **`chunked` 是流式的必要条件**：有 `Content-Length` 就意味着"服务器已经知道总长度"，
也就不需要边算边发了。`StreamingResponse` 因为长度未知，自动用 chunked。

#### ③ 证据 2：`curl -w` 量首字节 vs 总耗时（**最客观的判据**）

```powershell
curl.exe -s -o NUL -w "ttfb=%{time_starttransfer}s total=%{time_total}s`n" http://127.0.0.1:8000/v1/chat/stream
```

实测：

```text
ttfb=0.014s  total=1.850s
```

| 指标 | 含义 | 实测 |
|---|---|---|
| `time_starttransfer`（TTFB） | 从发出请求到**收到第一个字节** | **0.014s** |
| `time_total` | 直到**连接关闭** | **1.850s** |

⭐ **判据：TTFB ≪ total 就是真流式**。若两者接近 → 被缓冲了（查 `X-Accel-Buffering`、
中间件有没有读 `response.body`）。

> 🔴 **2026-10-20 订正（9b-2 实测）**：上面这条判据**只在"响应头之后立刻有第一帧"时成立**。
> `curl -w` 的 `time_starttransfer` 量的是**响应头到达**，不是"首个数据帧到达"。
>
> 📎 控制实验（端口 8002，路由立刻返回 `StreamingResponse`，但生成器先 `sleep(2)` 才 yield 第一帧）：
>
> ```text
> curl -w:   ttfb=0.0198s  total=2.0231s      ← 比值 1:102，按旧判据"完美流式"
> 逐帧时间戳: 响应头 61ms、第 1 帧 2067ms      ← 真实首帧占总耗时 97%
> ```
>
> 9a 当时结论对，是因为假数据第一帧紧跟着头就发了（`yield` 在 `sleep` 之前）；
> **9b 之后头由路由立刻发出、内容要等上游，两者彻底脱钩** —— 实测 `/v1/chat/stream`：
> `ttfb=0.0089s / total=0.9057s`，但**首个内容帧在 845.8ms**（占 93%）。
>
> ⭐ **新判据：用带时间戳的客户端量"首个数据帧时刻 / 总耗时"，`curl -w` 的 ttfb 不再可用。**

**对照组**（同一份响应，用非流式读法 `await client.get(...)`）：

```text
await c.get 返回耗时: 1.01s | 长度 84 字节   ← 一次性拿到全部
```

同一份数据，两种读法的"首字节时间"差 **70 倍**。

#### ③b 一个必须订正的直觉：`time.sleep` 不会让流"攒成一次性"

教学时我（AI）曾断言"异步生成器里写 `time.sleep` 会让流变成攒完再发" —— **实测是错的**，
这里按实测订正，因为它区分了两个常被混为一谈的问题。

**实测**（真 uvicorn，端口 8099，两个只差 sleep 写法的 SSE 路由）：

| 写法 | `ttfb` | `total` |
|---|---|---|
| `await asyncio.sleep(0.2)` ×5 | `0.006118` | `1.012899` |
| `time.sleep(0.2)` ×5 | `0.023076` | `1.025552` |

**两版都在流** —— 因为每帧 `yield` 之后，Starlette 仍然单独发一个 chunk（chunked 编码与
"事件循环有没有被占住"无关）。`ttfb` 大 3 倍多只是因为**第一帧之前**多了个 0.2s 的阻塞。

**真正的差别在"别人"身上**（先起一个请求占住循环，250ms 后再打探测请求）：

| 谁在占住 | 探测请求 `ttfb` | 探测请求 `total` |
|---|---|---|
| `/sync_sleep`（`time.sleep`） | **`0.753224`** | `1.775232` |
| `/async_sleep`（`await`） | **`0.003253`** | `1.003839` |

⭐ **判据两条，别混用**：
- **"能不能流"** → 看 **TTFB 与 total 的比值**
- **"有没有害别人"** → 看 **旁边那个请求的 TTFB**（从 3ms 涨到 753ms，230 倍）

所以 `time.sleep` 在 `async def` 里的罪名不是"破坏流式"，而是**阻塞事件循环、拖垮并发**
（与 §8 里"慢请求永远慢，能变的是它有没有连累别人"是同一条判据）。

#### ④ 证据 3：逐帧到达的时间戳（证明"边算边发"）

```text
[0.02s] data: chunk0
[0.23s] data: chunk1
[0.43s] data: chunk2
[0.63s] data: chunk3
[0.83s] data: chunk4
[1.04s] data: [DONE]
```

#### ⑤ 流开始后抛异常，客户端**实际**看到什么（实测）

生成器 `yield "data: first\n\n"` 之后立刻 `raise RuntimeError(...)`：

```text
status=200                                   ← 状态码已经发出去了，改不了
got=data: first                              ← 已经收到一帧
exc=RemoteProtocolError:
    peer closed connection without sending complete message body (incomplete chunked ...)
```

⭐ **三条推论**：

| # | 推论 |
|---|---|
| 1 | 客户端拿到的是 **200**，前端**看不出这是错误** |
| 2 | 它看到的是一个**协议层异常**（chunked 没传完），而不是你精心设计的 `{"error": ...}` |
| 3 | 所以 **§9.4 的"把错误编码进流里"不是最佳实践，是唯一做法** |

#### ⑥ `TestClient` 会"假装没流式"

用 `TestClient` 打这条路由，实测：

```text
transfer-encoding: None          ← 没有 chunked（内存里直接给了完整 body）
是否为合法 SSE 帧: True
帧数: 10   首帧 'data: {"delta": "你"}'   末帧 'data: [DONE]'
```

⭐ **`TestClient` 只能验证"帧格式对不对"，证明不了"是不是真的分批发"**。
要证明后者，必须用 **真实 uvicorn + `curl -w`**（或真实 HTTP 客户端）。

## 9.4 ⚠️⚠️ 一旦开始流式，你就失去了"改状态码"的权利

**这是 SSE 最反直觉、最容易出事的地方**：

```python
@app.post("/stream")
async def stream(req: ChatRequest) -> StreamingResponse:
    async def gen():
        async for chunk in llm.stream(req):
            yield f"data: {chunk}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
```

**问题**：如果 `llm.stream()` 在**第 3 帧之后**报错怎么办？

**答案**：**HTTP 状态码已经发出去了（200）**。
你**无法**再改成 500，客户端已经收到 200 了。

> ⚠️ **后果**：前端以为请求成功，实际上流中断了，而它**不知道这是错误**。

**正确做法：把错误编码进流里**

```python
async def event_source() -> AsyncIterator[str]:
    try:
        async for chunk in llm.stream(req):
            yield sse({"delta": chunk})
    except Exception as exc:
        # 用【事件】而不是状态码来报错
        yield sse({"error": {"type": "upstream_error", "message": str(exc)}})
    finally:
        yield "data: [DONE]\n\n"
```

| 结论 | 说明 |
|------|------|
| **校验必须发生在流开始之前** | 让 pydantic 和 `HTTPException` 在 200 之前把错误挡住 |
| **流内错误用事件表达** | 约定一个 `{"error": ...}` 事件 |
| **`finally` 里发结束标记** | 保证前端一定知道流结束了（否则它会一直等） |

> ⭐ **一个实用的设计**：**先发一帧"元信息"**，再做生成。
> ```text
> data: {"type":"meta","model":"qwen-7b","conversation_id":123}
> data: {"type":"delta","text":"你"}
> ...
> data: {"type":"done","usage":{"prompt_tokens":10,"completion_tokens":88}}
> ```
> 这样"用哪个模型、会话 ID 是多少"在**第一帧**就给了前端，而且**第一帧之前的所有准备工作都还能返回 4xx**。

## 9.5 ⚠️ 客户端断开：必须处理，否则你在白烧钱

用户等不及，关掉页面 / 点了"停止"。但**服务端还在调 LLM**，还在付钱。

```python
from starlette.requests import Request

async def event_source(request: Request) -> AsyncIterator[str]:
    async for chunk in llm.stream(prompt):
        if await request.is_disconnected():      # ① 主动检查
            break
        yield sse({"delta": chunk})
```

| 机制 | 说明 |
|------|------|
| `await request.is_disconnected()` | 轮询式检查（底层是 ASGI 消息） |
| **`asyncio.CancelledError`** | 客户端断开时，Starlette 会**取消**生成器任务 |
| `GeneratorExit` | 生成器被关闭时抛出 |

**推荐的完整写法（P3 形态）**：

```python
async def event_source(request: Request) -> AsyncIterator[str]:
    try:
        async for chunk in llm.stream(prompt):
            if await request.is_disconnected():
                break
            yield sse({"delta": chunk})
        yield "data: [DONE]\n\n"          # ① 正常路径
    except asyncio.CancelledError:
        # ⭐ 关键：把取消传播给上游 LLM 请求，让它也停下来（省钱）
        #   注意这里【不能】再 yield —— 生成器正在被取消，yield 会抛 RuntimeError
        raise
    except Exception:
        logger.exception("流式过程中失败")
        yield 'data: {"error": {"code": "STREAM_FAILED"}}\n\n'   # ② 异常编码进流
        yield "data: [DONE]\n\n"                                  # 异常路径也要收尾
    finally:
        await upstream.aclose()       # ⚠️ 只做清理，绝不 yield
```

### `[DONE]` 放在哪：三种写法 × 三条路径（📎 2026-10-22 实测，订正本节旧模板）

| 写法 | ① 正常读完 | ② 流内异常 | ③ 客户端断开（`break` + `aclose()`） |
|---|---|---|---|
| **P1** `finally:` 里 `yield "[DONE]"` ← ❌ 旧模板 | ✅ 有 `DONE` | ✅ 有 `DONE` | ❌ **`RuntimeError: async generator ignored GeneratorExit`** |
| **P2** `finally` 只清理，`[DONE]` 写在 `try/finally` **之后** | ✅ 有 `DONE` | ❌ **没有 `DONE`** | ✅ 不报错、也没有 `DONE` |
| **P3** 正常路径 + 异常路径各发一次（上面那段） | ✅ | ✅ | ✅ |

⭐ 根因：`aclose()` 往生成器里抛 `GeneratorExit`，而**收到 `GeneratorExit` 后再 `yield` 是 Python 硬禁止的**
（`except GeneratorExit: pass` 也救不了）。

⚠️ **P2 不是"错"，但不够**：它在"客户端断开"那格是安全的，代价是**流内异常时客户端连 `[DONE]` 都收不到**
（📎 本项目实测：上游 `data:` 行坏 JSON → 客户端只收到 `thinking` 一帧就没了）。
**P2 → P3 是 9b-4b 的任务，不是 bug 修复。**

> ⭐ **这是 LLM 应用最实际的成本优化之一**。
> 用户点了"停止"，你的上游请求**也应该停止** —— 否则每次"点了又停"都在白花钱。
> 用 `httpx` 的 `AsyncClient.stream()` 时，`CancelledError` 会**自动**关闭连接（因为 `async with` 的 `__aexit__` 会跑）。

## 9.6 SSE vs WebSocket vs 轮询

| | SSE | WebSocket | 轮询 | 长轮询 |
|---|-----|-----------|------|-------|
| 方向 | **单向**（服务器→客户端） | 双向 | 反复请求 | 请求挂起等数据 |
| 协议 | 就是 HTTP | 独立协议（需 Upgrade） | HTTP | HTTP |
| 实现复杂度 | **低** | 中/高 | 极低 | 低 |
| 自动重连 | ✅ 浏览器 `EventSource` 自带 | ❌ 要自己写 | — | — |
| 能否带自定义头 | ❌（`EventSource` 不支持）| ✅ | ✅ | ✅ |
| 适合 | ⭐ **LLM 流式输出** | 聊天室、协同编辑、游戏 | 低频状态查询 | 兼容老环境 |

> ⭐ **LLM 应用的结论**：**输出是单向的（服务器→用户），所以 SSE 是天然选择**。
> 用 WebSocket 属于"杀鸡用牛刀"（还要自己处理心跳、重连）。

## 9.7 ⚠️ 前端消费的两个坑

**坑 1：`EventSource` 不支持 POST、不支持自定义头**

```javascript
// ❌ 做不到：EventSource 只能 GET，不能带 Authorization 头
const es = new EventSource("/v1/chat/stream", { headers: {...} });   // 无效！

// ✅ 所以 LLM 聊天场景通常用 fetch + ReadableStream 手动解析
const resp = await fetch("/v1/chat/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
  body: JSON.stringify({ messages }),
});
const reader = resp.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  processChunk(decoder.decode(value, { stream: true }));   // 注意 { stream: true }
}
```

> ⭐ **所以实践是**：**后端按 SSE 格式输出，前端用 `fetch` 手动解析**。
> 好处：SSE 格式简单、中间层友好（就是纯文本），同时绕开 `EventSource` 的限制。

**坑 2：分帧不一定按"事件"切**

`reader.read()` 返回的 chunk **不保证**正好是一个完整的 SSE 帧（可能半帧，也可能两帧）。
**必须自己缓冲并按 `\n\n` 切分**，不能假设一次 read 一帧。

## 9.8 其它实现方式（了解）

| 方式 | 说明 |
|------|------|
| 手写 `StreamingResponse` ⭐ | 本笔记的写法，零依赖、可控 |
| `sse-starlette` 第三方库 | 提供 `EventSourceResponse`，自动处理心跳/断连（⚠️ 本笔记未实测该库） |
| 框架自带 | 部分框架（如 `litellm` 的网关）提供封装 |

> ⭐ **建议先手写一遍**：你会真正理解"帧格式、缓冲、断连"这三件事。
> 之后再上库，你才知道它帮你做了什么 —— 这和阶段 2"先原生 API 再用 LangChain"是同一条原则。

## 9.8b 上游真实 SSE 帧长什么样（9b-1 取证，2026-10-20 实测）

> 实测环境：DeepSeek 官方接口 `/chat/completions`，`model=deepseek-flash`，`stream=true`，
> 提问「从1数到5，只输出数字，用空格隔开」。共收到 **68 条非空行**（67 个 `data:` 帧 + 1 个 `[DONE]`）。

### ① 响应头和 9a 一模一样

```text
content-type         = text/event-stream; charset=utf-8
transfer-encoding    = chunked
content-length       = None
```

⭐ 说明"流式"这层协议**上游和我们用的是同一套**，差别只在**帧里装什么**。

### ② 67 个帧分成 5 类

| 类 | 数量 | 长什么样 | 含义 |
|---|---|---|---|
| **首帧** | 1 | `{"delta":{"role":"assistant","content":null,"reasoning_content":""}}` | 表明"我是 assistant 在回答"，还没内容 |
| **思维链帧** | **56** | `{"delta":{"content":null,"reasoning_content":"We"}}` | DeepSeek 的**推理过程**（`reasoning_content`） |
| **内容帧** | **9** | `{"delta":{"content":"1","reasoning_content":null}}` | 真正的回答文字（"1 2 3 4 5" 共 9 个 token） |
| **结束帧** | 1 | `{"delta":{"content":""},"finish_reason":"stop"}` + `"usage":{...}` | 说明"说完了" + **token 用量** |
| `[DONE]` | 1 | `data: [DONE]` | OpenAI 约定的收尾标记 |

⭐ **最大发现**：**56 / 67 的帧是思维链，不是回答**。所以"帧多"不等于"字数多"（呼应 §9.2c）。

### ③ 字段逐个解释

| 字段 | 实测值 | 含义 |
|---|---|---|
| `id` | `31381edc-…` | 这次生成的唯一编号。**67 帧全是同一个 id** —— 所以它能用来归组"同一次回答" |
| `object` | `chat.completion.chunk` | 固定字符串："聊天补全的一个**片段**"。`chunk` = 块 |
| `created` | `1792473349` | Unix 时间戳（秒） |
| `model` | `deepseek-flash` | 实际回答的模型（上游可能改写你传的名字） |
| `system_fingerprint` | `e72d3c…` | 上游内部版本指纹。用于排查"同样的请求为何结果变了" |
| `choices` | 数组 | 候选答案列表。我们没请求多个，所以只有 1 个（`index: 0`） |
| `choices[0].delta` | 对象 | **本帧新增的内容**（delta = 增量，不是全量） |
| `delta.role` | `"assistant"` | **只在首帧出现** |
| `delta.content` | `"1"` / `null` / `""` | 回答文字。`null` = 这帧没文字 |
| `delta.reasoning_content` | `"We"` / `null` | **思维链**（DeepSeek 特有能力，非所有模型都有） |
| `logprobs` | `null` | 词概率，我们没请求 |
| `finish_reason` | `null` / `"stop"` | **只有结束帧有值**。`stop` = 模型自己说完；另有 `length`（超长被截断）、`content_filter`（被过滤） |
| `usage` | 对象 | **只有结束帧出现**：`prompt_tokens=44 / completion_tokens=66 / total_tokens=110`，其中 `reasoning_tokens=56` |

### ④ 三个真实存在的坑

| 坑 | 实测证据 | 后果 / 正确写法 |
|---|---|---|
| **`content` 有三种取值：`null` / `""` / 字符串** | 首帧是 `null`；结束帧是 `""`；内容帧是 `"1"` | `delta["content"]` 直接取会 `KeyError`（有的帧没有该键）；写 `if delta.get("content"):` 用**真值判断**可一次覆盖三种 |
| **`content` 与 `reasoning_content` 互斥** | 56 帧只有 reasoning、9 帧只有 content，**没有一帧同时有** | 别用一个字段判断"有没有内容" |
| **`usage` 只在最后一帧** | 67 帧里只有第 67 帧带 `usage` | 想记 token 必须**留到结束帧**再读；只转发 `content` 会把它丢掉 |

### ⑤ 和 9a 的对照：9b-2 要做的"翻译"

| 上游给的 | 9a 现在发的 | 9b-2 必须决定 |
|---|---|---|
| `choices[0].delta.content = "1"` | `{"delta": "你"}` | ✅ 直接映射 |
| `choices[0].delta.reasoning_content = "We"` | **没有对应** | ❓ **转不转给前端**（56 帧！） |
| `finish_reason = "stop"` | **没有对应** | ❓ 转不转 |
| `usage = {prompt_tokens: 44, …}` | **没有对应** | ❓ 转不转（这是**计费**依据） |
| 其余（`id`/`object`/`created`/`model`/`system_fingerprint`/`logprobs`） | **不转发** | ✅ 白名单剔除（同 Step 4b「上游 10 键 → 3 字段」的道理） |

⭐ **核心认知**：9a 你是"造帧的人"，9b 你是"**翻译官**"。
上游帧是**协议规定**的（字段多、为多种用途服务），我们对外只需要**一小部分** ——
所以 `StreamingResponse` 里不是"把上游字节原样倒出去"，而是**一帧一帧解析 → 重新组装 → 再 yield**。

## 9.8c 上游响应的「三层结构」与字段类型（2026-10-20 实测）

> 起因：学习者问「上游返回的信息形状是什么，`chunk` 的类型是什么，`usage` 里都是什么」。
> 结论：**叫 "chunk" 的东西有三个层次，混起来就会写出错代码。**

### ① 三个层次的 "chunk"（名字一样，东西完全不同）

| 层 | 名字 | 类型 | 谁产生 | 在哪看到 |
|---|---|---|---|---|
| 第 1 层 | **HTTP chunk** | `bytes` | TCP 分块传输 | `transfer-encoding: chunked`；`resp.aiter_raw()` / `aiter_bytes()` |
| 第 2 层 | **SSE 行** | `str` | 上游按 SSE 格式写的文本 | `resp.aiter_lines()` 给你的每一条 |
| 第 3 层 | **补全片段对象** | `dict`（Go SDK 里叫 `ChatCompletionChunk`） | 我们自己 `json.loads(第 2 层)` | `chunk["choices"][0]["delta"]` |

📎 实测（本项目真实上游）三层各自长什么样：

```text
第 1 层（字节，gzip 解压后）: b'data: {"id":"31381edc-...}\n\n'
第 2 层（字符串）            : 'data: {"id":"31381edc-...}'        ← aiter_lines 已去掉行尾 \n
第 3 层（dict）              : {'id': '31381edc-...', 'object': 'chat.completion.chunk', ...}
```

#### ①b 一张图看清「包含关系」（📎 同一次响应的真实分层）

```text
┌─────────────────────────────────────────────────────────────┐
│ 一条 TCP 连接（我们 → api.deepseek.com）                      │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ HTTP 响应                                                     │
│  ├─ 状态行：HTTP/1.1 200 OK                                   │
│  ├─ 响应头：content-type: text/event-stream                   │
│  │          transfer-encoding: chunked   ← 长度未知，分块发     │
│  │          content-encoding: gzip       ← 体是压缩的          │
│  └─ 响应体 ↓                                                  │
└─────────────────────────────────────────────────────────────┘
        │  按 chunked 规则切，再 gunzip
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 【第 1 层】HTTP chunk = bytes（一整段连续字节）                 │
│  b'data: {"id":"3138...}\n\ndata: {"id":"3138...}\n\n...' │
│  ↑ 这一层 httpx 已经替我们处理完（解压 + 去分块长度）            │
└─────────────────────────────────────────────────────────────┘
        │  resp.aiter_lines()：按 \n 切开，去掉行尾 \n
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 【第 2 层】SSE 行 = str（一次给一行）                          │
│  'data: {"id":"3138...}'      ← 有内容的一行                   │
│  ''                           ← 空行 = 帧分隔符（要过滤掉）      │
│  'data: [DONE]'               ← 收尾行                        │
└─────────────────────────────────────────────────────────────┘
        │  line[6:] 去掉 "data: " 前缀 → json.loads()
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 【第 3 层】一帧 = dict（json.loads 的结果）                    │
│  {                                                           │
│    "id": "3138...",                    str                   │
│    "object": "chat.completion.chunk",  str                   │
│    "created": 1792473349,              int                   │
│    "model": "deepseek-flash",          str                   │
│    "system_fingerprint": "e72d...",    str                   │
│    "choices": [                        list ─┐               │
│      {                                       │               │
│        "index": 0,                     int   │               │
│        "delta": {                      dict ─┼─┐             │
│          "role": "assistant",  str（仅首帧）  │ │             │
│          "content": "1" 或 None,       str|None│             │
│          "reasoning_content": "" 或 "We"  str │              │
│        },                                    │ │             │
│        "logprobs": None,               None  │               │
│        "finish_reason": "stop" 或 None  str|None             │
│      }                                       │               │
│    ],                                        │               │
│    "usage": { ... }        dict，仅最后 1 帧（67 帧里出现 1 次）│
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

⭐ **读图要点**：`delta` 是**每帧新增的那一小段**；
`choices` 是**候选列表**（我们固定取 `[0]`）；`usage` 是**整次请求的汇总**，所以只出现一次。

⭐ **判据：`chunk` 这个词在每一层的类型都不同** —— 看代码时先确认"这里的 chunk 是哪一层"。
我们的代码里 `chunk = json.loads(raw)` 拿到的是**第 3 层**，所以 `chunk["choices"]` 是 dict 下标，不是字节切分。

### ② 第 3 层的完整形状 + 每个字段的**类型**（📎 逐字段实测）

```text
id                                    str        = '31381edc-87fb-49ca-93ed-640d1965ff13'
object                                str        = 'chat.completion.chunk'
created                               int        = 1792473349
model                                 str        = 'deepseek-flash'
system_fingerprint                    str        = 'e72d3c7f663d3e1383b00b3884cb4501'
choices                               list       长度 1，元素是 dict
choices[0].index                      int        = 0
choices[0].delta                      dict      继续下钻
choices[0].delta.role                 str        = 'assistant'
choices[0].delta.content              NoneType   = None            ← 这一帧没有文字
choices[0].delta.reasoning_content    str        = ''              ← 空串，不是 None！
choices[0].logprobs                   NoneType   = None
choices[0].finish_reason              NoneType   = None
```

⭐ 注意两个"反直觉"：

| 现象 | 后果 |
|---|---|
| `delta.content` 的类型**每帧都在变**（`None` / `str`） | 不能写 `if content != ""`（漏掉 `None`）；要用真值判断 `if not text` |
| `reasoning_content` 在首帧是 **`''` 而不是 `None`** | 同一个概念在同一帧里用了两种"没有"的表示 → 只能靠真值判断统一处理 |

### ③ 哪些字段"不是每帧都有"（📎 67 帧统计）

| 字段 | 出现帧数 | 说明 |
|---|---|---|
| `id` / `object` / `created` / `model` / `system_fingerprint` | **67 / 67** | 每帧都有（可用来归组"同一次回答"） |
| `choices` | **67 / 67** | 每帧都有 —— ⚠️ 但有 `[]` 空列表的情况（换上游时才出现） |
| **`usage`** | **1 / 67** | ⭐ **只在最后一帧** |
| `delta.content` | 67 / 67（值常为 `None`） | 键在，值不一定有 |
| `delta.reasoning_content` | 67 / 67 | 同上 |
| `delta.role` | **1 / 67** | 只在首帧 |
| `finish_reason` | **1 / 67**（其余 66 帧是 `None`） | 值分布：`None` × 66，`"stop"` × 1 |

⭐ **判据：`usage` / `finish_reason` / `role` 都是"单帧字段"** —— 处理它们必须放在"内容判断"之前，
否则会被 `if not text: continue` 吃掉（我们 9b-2 就这样丢过一次）。

### ④ `usage` 的 8 个字段（📎 逐字段实测）

```text
usage.prompt_tokens                                  int  = 44
usage.completion_tokens                              int  = 66
usage.total_tokens                                   int  = 110
usage.prompt_tokens_details                          dict
usage.prompt_tokens_details.cached_tokens            int  = 0
usage.completion_tokens_details                      dict
usage.completion_tokens_details.reasoning_tokens     int  = 56
usage.prompt_cache_hit_tokens                        int  = 0
usage.prompt_cache_miss_tokens                       int  = 44
```

| 字段 | 含义 | 用来干什么 |
|---|---|---|
| `prompt_tokens` | 这次**输入**消耗的 token（`messages` 全部内容） | 输入成本 |
| `completion_tokens` | **输出**消耗的 token | 输出成本 |
| `total_tokens` | 两者之和（实测 44 + 66 = 110 ✅） | 总成本 |
| `prompt_tokens_details.cached_tokens` | 输入里命中缓存的部分（OpenAI 风格字段） | 缓存效果（DeepSeek 恒为 0，用下面两个） |
| **`completion_tokens_details.reasoning_tokens`** | ⭐ **思维链**消耗的 token（56 / 66 = 85%！） | 判断"钱是不是花在思考上" |
| **`prompt_cache_hit_tokens`** | ⭐ 前缀缓存**命中**的输入 token | 缓存命中率 = hit / (hit + miss) |
| **`prompt_cache_miss_tokens`** | 前缀缓存**未命中**的输入 token | 同上 |

⭐ 两个关键发现：

1. **`reasoning_tokens` 会占大头**（实测 56 / 66 = 85%）→ 输出成本主要花在思维链上，不是回答本身
2. **`prompt_cache_hit_tokens` 是可观测指标** → 固定 system prompt 前缀后能到 85%（详见[学习过程记录](学习过程记录.md) 专题 6）

⚠️ `usage` 在**流式**下默认可能不返回（OpenAI 需要显式开 `stream_options.include_usage`）；
**DeepSeek 实测默认就带**，且是和 `finish_reason` **同一帧**。不同上游行为不同 → 必须两种位置都处理。

### ⑤ 为什么 `chunk` 的类型是 `dict[str, Any]` 是个**风险点**

```python
chunk = json.loads(raw)      # 类型：Any（mypy 眼里什么都放过）
```

| 后果 | 实测案例 |
|---|---|
| 键名写错 → 不报错，运行时 `KeyError` | `chunk["choice"]`（少个 s）→ `KeyError: 'choice'` |
| **值**的键名写错 → 连运行时不报错，只是静默走错分支 | `{'usgae': usage}` → 前端收不到 `usage`，日志一切正常 |

⭐ **改善方向（阶段 2/3 可做）**：用 pydantic 定义 `Chunk` 模型 + `model_validate`，
把 `Any` 变成有类型的对象 —— 键名写错会在解析处立刻报错，而不是流出到前端。
这就是 Step 4b 学过的「`list[dict]` vs `list[Model]`」在流式场景的再次应用。

### ⑥ 一句话记忆

> **三层 chunk：字节（HTTP）→ 字符串（SSE 行）→ dict（补全片段）。
> 单帧字段（`usage` / `finish_reason` / `role`）必须先处理；类型会变的字段（`content`）只能真值判断。**

## 9.8d 帧的五种类型与产生顺序（2026-10-21 实测）

> 起因：学习者问「帧应该有分类吧？不同帧的区别是什么？一次生成按什么顺序产生？」
> 结论：**上游只有 4 类帧 + 1 个结束标记；我方输出 5 类（多了自造的 THINKING）**。

### ① 一帧 = 一个 dict，按「里面装了什么」分类

分类判据只有 4 个问题，按此顺序问下去：

```text
拿到一帧 chunk
  ├─ choices 是空列表？           → ① 纯用量帧（PURE_USAGE，OpenAI 风格）
  └─ choices 有内容 → 看 delta / finish_reason
       ├─ delta.role 有值？        → ② 首帧（ROLE）  ← 只有 1 个
       ├─ finish_reason 有值？     → ④ 结束帧（FINISH）
       ├─ delta.content 有值？     → ③ 内容帧（CONTENT）
       └─ delta.reasoning_content 有值？ → ③' 思维链帧（REASONING）
（最后还有 1 个 data: [DONE]，它不是 JSON，是纯文本标记）
```

### ② 上游五类的对照表（📎 实测，问「从1数到3」共 64 帧）

| # | 类型 | `delta` 里装什么 | 数量 | 作用 | 我方是否转发 |
|---|---|---|---|---|---|
| ① | **ROLE 首帧** | `{"role":"assistant","content":null,"reasoning_content":""}` | **1** | 声明"接下来是 assistant 在回答" | ❌ 丢弃 |
| ② | **REASONING 思维链帧** | `{"content":null,"reasoning_content":"We"}` | **56** | 模型内部推理过程 | ❌ 丢弃（产品只显示回答） |
| ③ | **CONTENT 内容帧** | `{"content":"1","reasoning_content":null}` | **5** | 真正的回答文字 | ✅ 转发为 `{"delta": ...}` |
| ④ | **FINISH 结束帧** | `{"content":"","reasoning_content":null}` + **`finish_reason:"stop"`** + **`usage`** | **1** | 说明为何结束 + 本次用量 | ✅ 转发为 2 帧 |
| ⑤ | **`[DONE]`** | 不是 JSON，就是字符串 `[DONE]` | **1** | OpenAI 约定的收尾标记 | ✅ 由我方重发一次 |

⭐ 注意 ④ **一帧里装了两件事**（`finish_reason` + `usage`），所以转发时会被拆成 2 帧。

### ③ 📎 上游真实顺序（压缩连续重复）

```text
ROLE × 1
REASONING × 56
CONTENT × 5
FINISH(stop)+USAGE × 1
DONE × 1

首 3 帧: ['ROLE', 'REASONING', 'REASONING']
末 3 帧: ['CONTENT', 'FINISH(stop)+USAGE', 'DONE']
```

⭐ **顺序是固定的**：ROLE 打头 → 推理 → 内容 → 结束 → DONE。
⚠️ 但 **REASONING 与 CONTENT 不保证"先全推理再全内容"** —— 模型可能交替产出（本机这次是分段的）。

### ④ 📎 我方输出的 5 类（问「从1数到3」共 9 帧）

```text
第 1 帧 @  189.4ms  THINKING       {"status": "thinking"}          ← 我方新增，不等上游
第 2 帧 @  686.0ms  DELTA          {"delta": "1"}
第 3 帧 @  686.2ms  DELTA          {"delta": " "}
第 4 帧 @  686.7ms  DELTA          {"delta": "2"}
第 5 帧 @  686.8ms  DELTA          {"delta": " "}
第 6 帧 @  708.9ms  DELTA          {"delta": "3"}
第 7 帧 @  709.1ms  FINISH_REASON  {"finish_reason": "stop"}
第 8 帧 @  713.9ms  USAGE          {"usage": {...}}
第 9 帧 @  716.0ms  DONE           data: [DONE]

顺序: THINKING → DELTA×5 → FINISH_REASON → USAGE → DONE
```

### ⑤ 上游分类 → 我方分类的映射

| 上游帧 | 我方动作 | 我方帧 |
|---|---|---|
| ROLE | `if not text: continue` | （不发） |
| REASONING ×56 | `if not text: continue` | （不发） |
| CONTENT | 重组为 `{"delta": text}` | **DELTA** |
| FINISH 的 `finish_reason` | 单独发一次 | **FINISH_REASON** |
| FINISH 的 `usage` | 单独发一次 + 记日志 | **USAGE** |
| `[DONE]` | `break`/`seen_done` 跳过，**由我方统一发** | **DONE** |
| — | 我方自造，在请求上游之前 | **THINKING** |

⭐ **这解释了为什么 64 帧上游只变成 9 帧我方输出**：56 帧思维链 + 1 帧 ROLE 被丢弃，
1 帧 FINISH 被拆成 2 帧，再加 1 帧自造的 THINKING。

### ⑥ 为什么"顺序"必须搞清（写代码的直接后果）

| 顺序事实 | 代码后果 |
|---|---|
| ROLE 在最前，且 `content` 是 `null` | 首帧必被 `if not text` 跳过（正常） |
| `finish_reason` / `usage` **只在最后 1 帧** | 处理必须放在 `content` 判断**之前**，否则被 `continue` 吃掉 |
| FINISH 帧的 `content` 是**空字符串 `""`** | 用 `if not text` 会连 `finish_reason`/`usage` 一起丢 → 这就是 9b-2 的 bug |
| `[DONE]` 是最后一行、不是 JSON | 必须先判断 `raw.strip() == "[DONE]"` 再 `json.loads`，否则 `JSONDecodeError` |

### ⑦ 一句话记忆

> **五类帧：ROLE（首帧，丢）→ REASONING（思维链，丢）→ CONTENT（回答，转 DELTA）→ FINISH（拆成 FINISH_REASON + USAGE）→ DONE（我方重发）。
> 顺序固定，但「结束信息只在最后一帧」这一条决定了代码里的处理次序。**

## 9.8e 上游封层与 pre-flight（9b-4a，2026-10-21）

> 起因：学习者质疑「岂不是每个路由都要单独写完整的异常上抛？这会不会太复杂了，这是正常写法吗」
> —— 质疑成立，之前的步骤卡设计错了**两次**。完整复盘见
> [学习过程记录.md](学习过程记录.md) 专题 9；硬约束见[规范](../工程规范与协作约定.md) §14.7 / §14.8。

### ① 三个版本：错在哪一步

| 版本 | 做法 | 问题 |
|---|---|---|
| V1 | 每条路由自己 `try/except httpx.xxx` → `AppError` | **放错层**：N 份真相，抄漏/抄错（本项目已发生两次） |
| V2 | 全局 `@app.exception_handler(httpx.RequestError / HTTPStatusError)` | **用错机制**：靠 ASGI 中间件栈兜异常，**CLI / 定时任务里完全失效**；且不起 FastAPI 就没法单测 |
| **V3** | 把「发请求 + 判状态码 + 读错误正文 + 解析 + 翻译」封进 `LlmClient` 适配器 | — |

⭐ 判据：**先问「这段代码会被调用几次」—— 会被 ≥2 个调用点用到的错误处理，不属于任何一个调用点。**
次级判据（用来排除 V2）：**不启动 FastAPI 能测吗？定时任务里还有效吗？** —— V2 两个都是 ❌。

### ② 改动前后的代码形状（同一件事，两种写法）

```python
# ❌ 改前：路由直接持有 httpx，自己翻译三类失败（30~40 行，每条路由一份）
@app.get("/v1/upstream/models")
async def upstream_models(client: LlmClientDep) -> ModelListResponse:
    try:
        resp = await client.get("/models")
    except httpx.RequestError as exc:            # L1
        raise AppError("UPSTREAM_UNREACHABLE", "…") from exc
    if resp.status_code >= 400:                   # L2（3xx 会被放过）
        raise AppError("UPSTREAM_BAD_STATUS", "…")
    try:
        payload = resp.json(); raw = payload["data"]   # L3
    except (ValueError, KeyError, TypeError) as exc:
        raise AppError("UPSTREAM_MALFORMED", "…") from exc
    return ModelListResponse(total=len(raw), items=raw)

# ✅ 改后：路由只有两行，物理上看不见 httpx
@app.get("/v1/upstream/models")
async def upstream_models(client: LlmClientDep) -> ModelListResponse:
    models = await client.list_models()      # 失败必抛 AppError，成功必是 list[ModelItem]
    return ModelListResponse(total=len(models), items=models)
```

适配器的契约只有一句：**成功返回值，失败抛 `AppError`，绝不把 `httpx` 异常泄漏给调用方。**
因此路由层**不需要**写任何 `try/except` 来翻译 httpx 错误。

### ③ 职责边界：什么进适配器，什么留在业务层

| 进适配器（传输 + 协议 + 错误翻译） | 留在业务层（语义） |
|---|---|
| 发请求 / `build_request` / `send(stream=True)` | 哪个字段是回答正文 |
| 状态码判断（`is_success`）、读 error body、写日志 | 帧的类型（THINKING / DELTA / FINISH / USAGE） |
| 切行、剥 `data:` 前缀、消化 `[DONE]`、`json.loads` | 转发哪些字段（白名单） |
| L1/L2/L3 统一翻译成 `AppError` | 业务错误码的含义 |
| 关闭响应（`aclose`） | 什么时候关（放 `finally`） |

### ④ pre-flight：让流式接口还能返回 502

```python
# 顺序不能换：先校验上游，再返回 StreamingResponse
upstream = await client.open_chat_stream(body)   # 内部 send(stream=True) 拿到响应头就停
# ↑ L1 连不上 / L2 状态码不对 → 抛 AppError → 由 errors.py 的处理器回 502
return StreamingResponse(event_source(), media_type="text/event-stream")
```

📎 实测数字：

| 场景 | 改前（9b-2/9b-3） | 改后（9b-4a） |
|---|---|---|
| 上游正常，首个 body 帧 | **60.0ms** | 约 181~266ms（多了"等上游响应头"） |
| 上游返回 400 | `200` + 半截流 + 后端报错 | **502** + `{"error":{"code":"UPSTREAM_BAD_STATUS"}}` |

⭐ 代价换来正确性：TTFB 从 60ms 涨到约 181~266ms，仍远小于首个**内容**帧的 845.8ms。

### ⑤ 一个"三道门全绿但接口 500"的真坑

`_request(..., stream: bool = True)` 默认值写反 → `list_models()` 走流式分支 → `response.json()` 抛
`httpx.ResponseNotRead`（MRO：`ResponseNotRead → StreamError → RuntimeError`，**既不是 `RequestError`
也不在 `(ValueError, KeyError, TypeError)` 里**）→ 穿过所有 `except` → 500。

⚠️ **`MockTransport` 复现不出来**：它的 `httpx.Response(200, json=...)` body 已在内存，
`send(stream=True)` 与 `request()` 毫无区别。

⭐ 两条判据：① `stream` 这类开关**默认值取"安全的那一边"**（False = 读完 body）；
② **涉及"body 读没读"的改动必须打真网络**。

### ⑥ 用 lint 把约定变成机械检查

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "TID"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"httpx".msg = "上游调用必须走 LlmClient（src/app/llm_client.py），不要直接 import httpx"

[tool.ruff.lint.per-file-ignores]
"src/app/llm_client.py" = ["TID251"]
"playground/*.py" = ["TID251"]     # 学习脚本刻意直写 httpx
```

📎 实测：在 `app.py` 加回 `import httpx` → `TID251 httpx is banned`。

⭐ **规范里写"请勿…"是弱的，lint 里写"禁止…"是强的。**

### ⑦ 同一课的另一半：业务规则也只能有一份

`/v1/chat` 与 `/v1/chat/stream` 共用 `ChatRequest`，但"最后一条必须是 `user`"只写在一条路由里
→ 另一条**放行非法请求、还真打上游、白花一次调用**（📎 实测：一条 400、一条 200）。
修法：抽 `ensure_last_message_is_user(request)`，并且**放在 pre-flight 之前**。

### ⑧ 一句话记忆

> **上游调用必有适配器：一个类、一个文件、一句契约（成功返值 / 失败抛 `AppError` / 不泄漏 `httpx`）。
> 路由看不见 `httpx`，「翻不翻译」就不再是一个需要每轮重新决定的问题。
> 流式接口额外加 pre-flight —— 先验状态码，再开流。**

## 9.8f 流式静默失败与三层防线（9b-4b-1，2026-10-22）

> 完整实测与七种异常逐条对照见[学习过程记录.md](学习过程记录.md)专题 12。
> 这里是**复习入口**：记住三层的分工和那条判据就够了。

### ① 流式独有的失败形态：`200` + 空

| | 非流式 | 流式 |
|---|---|---|
| 表达失败 | 改状态码（502） | **头已发出，改不了** |
| "上游没给内容" | 502 + 错误体 | **200 + 空** ← 和"模型真说了空"一模一样 |
| 客户端能区分 | 能（`!response.ok`） | **不能**（`response.ok === true`） |

⭐ 所以必须多一条通道：**流内结构化 error 帧**。

```text
data: {"status": "thinking"}
data: {"error": {"code": "STREAM_NO_CONTENT", "message": "上游未返回任何内容"}}
data: [DONE]
```

### ② 三层，判据是「能不能在读到数据之前判断」

| 层 | 看什么 | 拦什么 | 客户端 |
|---|---|---|---|
| ① pre-flight | 状态码 `is_success` | L1 连不上 / L2 状态码不对 | **502**（`ok === false`） |
| ② 适配器 `aiter_chunks` | **行 / 帧本身** | `data:` 无空格、空 `data:` 行、解析结果非 dict | 丢弃 + WARNING（继续后续帧） |
| ③ 路由 `event_source` | **字段 / 最终结果** | `content` 非字符串、一帧内容都没有 | 丢弃 + WARNING / `STREAM_NO_CONTENT`（`ok === true`） |

⭐ **判据：这个问题在读到数据之前就能判断吗？** 能 → 前一层。
⚠️ **反向会坏**：适配器若要知道"整个流结束了没"才能判断，它就不再是协议层了。

### ③ 📎 七种异常各防在哪层（本项目实测）

| 上游给了什么 | 层 | 客户端看到 |
|---|---|---|
| `data:{"..."}` 无空格（合法 SSE） | ② 适配器 | ✅ 正常 `delta`（旧写法：**整条流静默丢弃**） |
| `data:` 空行（合法空事件） | ② 适配器 | ✅ 正常（旧写法：`JSONDecodeError` **打断整条流**） |
| `data: null` | ② 适配器 | ✅ null 丢掉，**后续帧照常**（旧写法：`AttributeError` 断连） |
| `data: [1,2,3]` | ② 适配器 | `STREAM_NO_CONTENT` |
| `content` 是数组 | ③ 路由 | `STREAM_NO_CONTENT`（旧写法：**把数组塞给前端**） |
| `200` + HTML / 空 body | ③ 路由 | `STREAM_NO_CONTENT`（旧写法：只收到 `thinking` + `[DONE]`） |
| 忽略 `stream`（字段是 `message`） | ③ 路由 | `STREAM_NO_CONTENT` |

### ④ 为什么用 `content_frames` 而不是 `raw_chunks`

`raw_chunks` 数"上游发了多少帧"，`content_frames` 数"我们真正转发了多少"。
📎 三种 `raw_chunks > 0` 但 `content_frames == 0`：忽略 `stream` / `content` 是数组 / 只有思维链帧。
⭐ **用户关心的是"拿到多少字"，不是"上游发了几帧"。**

### ⑤ 静默 vs 留痕的分界

| 情况 | 日志 | 为什么 |
|---|---|---|
| `content is None`（首帧 role / 结束帧 / 思维链帧） | ❌ 不记 | **正常帧**，记了刷屏 |
| `content` 是**非 None 的非字符串** | ✅ `warning` | 上游改结构了 |
| 解析结果不是 dict | ✅ `warning` | 同上 |
| 最终一帧内容都没有 | ✅ `error` | 请求**实质失败** |

### ⑥ 一句话记忆

> **状态码层只管「能不能开始流」；协议层只管「这一帧能不能用」；业务层才管「用户有没有拿到答案」。
> 200 + 空内容对用户就是失败 —— 必须主动说出来。**

## 9.9 一条流式请求的全生命周期（全景图，2026-10-23 补）

> 这一节是 **Step 9 的复习入口**：把前面 9.1 ~ 9.8f 散落的知识点，按「一条请求从进来到出去」的顺序串成一张路线图。
> 面试时被问「你这个流式接口怎么做的」，答案的骨架就是这一节的三张图 + 三条规律。
>
> **怎么用**：不要通读。先看三张图（9.9.1 ~ 9.9.3），能自己复述出「哪一步之后状态码就改不了了」，
> 再挑记不清的步骤去读 9.9.4 对应的那一段。

### 9.9.1 图一：时间轴 —— 谁在等谁

```text
时间 →

客户端               我们的 FastAPI 服务                      DeepSeek 上游
  │                        │                                      │
  │──① POST /v1/chat/stream│                                      │
  │───────────────────────>│                                      │
  │                        │ ② uvicorn 收到 TCP，组装 ASGI scope   │
  │                        │ ③ 中间件：分配 request_id             │
  │                        │ ④ 路由匹配 → 依赖注入 get_llm_client  │
  │                        │ ⑤ pydantic 校验请求体（422 就死在这）  │
  │                        │ ⑥ ensure_last_message_is_user（400）  │
  │                        │ ⑦ 拼 body = {model, messages, stream}│
  │                        │                                      │
  │                        │──⑧ send(stream=True) ───────────────>│
  │                        │                                      │ 模型开始生成
  │                        │  ⏸ 等响应头（实测 181~266ms）         │
  │                        │<─────⑨ 200 + 响应头 ─────────────────│
  │                        │ ⑩ is_success 检查通过                  │
  │                        │ ⑪ 返回 StreamingResponse              │
  │<──⑫ 200 + chunked ─────│   ★ 状态码从这里【焊死】              │
  │                        │                                      │
  │                        │<─────⑬ data: {...} 第 1 帧 ──────────│
  │<──⑭ data: {"delta":..} │ ⑮ aiter_lines → aiter_chunks         │
  │                        │    → 三层守卫 → 重组 → yield          │
  │                        │            ...（反复 ⑬~⑮）...         │
  │                        │<─────⑯ data: [DONE] ─────────────────│
  │                        │ ⑰ 零内容检查 → yield [DONE]           │
  │<──⑱ data: [DONE] ──────│ ⑲ finally: upstream.aclose()         │
  │                        │ ⑳ 连接归还池                          │
  │──㉑ 客户端读到 EOF，连接结束│                                     │
```

⭐ **全图只有一个分界点值得记死：第 ⑫ 步。**
`200 + transfer-encoding: chunked` 一旦发出去，**HTTP 状态码就再也改不了**（HTTP 协议层面，不是 FastAPI 的限制）。
Step 9 里所有的设计 —— pre-flight、错误编码进流、零内容保护 —— **全都是为了绕开这一个约束**。

### 9.9.2 图二：对象关系 —— 谁持有谁

```text
                            ┌─────────────────────────────┐
                            │  uvicorn（ASGI 服务器）      │
                            │  「怎么收 TCP、怎么发字节」   │
                            └──────────────┬──────────────┘
                                           │ 调用 app(scope, receive, send)
                            ┌──────────────▼──────────────┐
                            │  app: FastAPI               │
                            │  「路由表 + 异常表 + 中间件」 │
                            └──────────────┬──────────────┘
                                           │
              ┌────────────────────────────┼─────────────────────────┐
              │                            │                         │
   ┌──────────▼──────────┐      ┌──────────▼──────────┐   ┌──────────▼─────────┐
   │ add_request_id      │      │ chat_stream()       │   │ errors.py           │
   │ （中间件）           │      │ （路由函数）         │   │ 异常处理器          │
   │ 分配 request_id      │      │ 校验 + pre-flight   │   │ AppError → 502      │
   │ 记耗时日志           │      │ 返回流式响应         │   │ Exception → 500     │
   └─────────────────────┘      └──────────┬──────────┘   └────────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │ ① 用                │ ② 造                │ ③ 返回
        ┌───────────▼────────┐  ┌──────────▼──────────┐  ┌────────▼─────────────┐
        │ LlmClient           │  │ event_source()      │  │ StreamingResponse    │
        │ （适配器，持有        │  │ （异步生成器）        │  │ （Starlette 的壳）    │
        │  httpx.AsyncClient） │  │ 三层守卫 + 重组帧     │  │ 只负责把帧写上网      │
        └───────────┬────────┘  └──────────┬──────────┘  └──────────────────────┘
                    │                      │
                    │ open_chat_stream()   │ aiter_chunks()
                    ▼                      │
        ┌──────────────────────┐           │
        │ LlmChatStream        │◄──────────┘
        │ （持有 httpx.Response）│
        └──────────────────────┘

  ★ 依赖方向：event_source ──> LlmChatStream ──> httpx.Response
    event_source 永远看不见 httpx，只看得见「一个能吐 dict 的东西」
```

⭐ **这张图要能回答一个问题**：「如果要把 httpx 换成 aiohttp，改哪几个文件？」
答案：**只改 `llm_client.py` 一个文件**。因为依赖方向是单向的，路由层根本不知道 httpx 存在（`pyproject.toml` 的 `TID251` 规则会**拦住**任何其他文件 import httpx）。

### 9.9.3 图三：12 个失败点，谁接住

```text
    可能出错的位置                          谁接住                  客户端看到
  ─────────────────────────────────────────────────────────────────────────────
 ① 客户端发的 JSON 格式错          pydantic / FastAPI          422 + 字段定位
 ② 请求体字段类型/长度不对           pydantic / FastAPI          422 + 字段定位
 ③ 最后一条消息不是 user           ensure_last_message_is_user  400 + AppError
 ④ 上游 DNS/TCP/TLS 失败           LlmClient._request L1        502 UPSTREAM_UNREACHABLE
 ⑤ 上游超时                        LlmClient._request L1        502 UPSTREAM_UNREACHABLE
 ⑥ 上游返回 4xx/5xx                LlmClient._request L2        502 UPSTREAM_BAD_STATUS
 ──────────────── 以上都还能改状态码（响应头还没发） ──────────────────────────
 ⑦ 上游 200 但 body 是 HTML        零内容保护                    200 + 流内 STREAM_NO_CONTENT
 ⑧ 上游某帧是坏 JSON               → 中止                       200 + 流内 STREAM_FAILED
 ⑨ 上游某帧字段类型不对            → 跳过（三档）                200 + 正常内容（可能没有）
 ⑩ 我方代码抛未预期异常            except Exception              200 + 流内 STREAM_FAILED
 ──────────────── 以下连流内错误帧都发不出去 ────────────────────────────────
 ⑪ 客户端中途断开                  CancelledError 外抛           客户端自己断的，无需回应
 ⑫ 什么都没发生但没内容            content_frames == 0           200 + 流内 STREAM_NO_CONTENT
```

判据：**「客户端还能收到一个合法的 HTTP 错误响应吗？」**
- 能（①~⑥）→ 用**状态码 + JSON 错误体**
- 不能（⑦~⑫）→ 只能把错误**编码进流**，且必须保证流有正常收尾

### 9.9.4 逐步讲解

#### ①~③ 请求进门前

**② uvicorn 只做翻译。** 它把字节流翻译成 HTTP 语义（方法 / 路径 / 头 / body），再把响应语义翻译回字节流。它**不知道你有几条路由** —— 路由是 FastAPI 的事。

→ 所以日志里会有两条看起来重复的行：

| 日志 | 谁打的 | 含什么信息 |
|---|---|---|
| `INFO: 127.0.0.1:xxxx - "POST /v1/chat/stream HTTP/1.1" 200 OK` | **uvicorn** | 只有方法/路径/状态码 |
| `POST /v1/chat/stream -> 200 16.4ms request_id=...` | **我们的中间件** | 多了耗时和 `request_id` |

**③ 中间件的 `call_next` 等的是「响应头就绪」，不是「响应体发完」。**

📎 实测（假上游每 0.4s 吐一帧、共 3 帧）：

```text
  25.6ms  === 客户端发起 POST ===
  42.7ms  [日志] POST /v1/chat/stream -> 200 16.4ms request_id=1ea535d3aaee
1266.9ms  === 客户端拿到响应头 status=200 ===
1267.1ms  [帧] data: {"status": "thinking"} ... data: [DONE]
1267.1ms  === 客户端读完（连接结束） ===
```

⭐ **访问日志在 42.7ms 就打出来了，而整条流到 1267ms 才结束** —— `-> 200 16.4ms` 这个数字**不包含**流式传输时长。
（这是 TestClient 的表现，帧被缓冲到最后一起交付；真实 curl 下帧是逐条到达的，但**中间件日志提前这点一样成立**，因为它是 ASGI 层面的事实。）

> ⚠️ **可观测性陷阱**：流式接口的「耗时」指标不能只看中间件日志。要真实耗时得在 `event_source` 的 `finally` 里另记一条。

#### ④~⑦ 进屋后的三道检查

**④ 依赖注入靠类型注解，不靠参数顺序。**

```python
async def chat_stream(
    request: ChatRequest,          # pydantic 模型 → 从 body 来
    client: LlmClientDep,          # Annotated[..., Depends(...)] → 从 lifespan 单例来
    config: SettingsDep,           # Annotated[..., Depends(...)] → 从 .env 来
) -> StreamingResponse:
```

**⑤ pydantic 校验在 422 处就死** —— 一个字节都不会发给上游。所以 `ChatRequest` 的每个约束（`min_length`、`Literal`）都是在**替上游省钱**。

**⑥ 顺序：业务规则 → pre-flight。**

```python
ensure_last_message_is_user(request)      # 免费，先查
upstream = await client.open_chat_stream(body)   # 花钱，后查
```

⭐ 判据：**免费检查必须排在花钱检查前面**。反了就是「先付钱再验票」。

**⑦ 我们的契约 ≠ 上游的契约。** `ChatRequest` / `ChatResponse` 是**对外的**；`body` 那个 dict 是**对上上游的**。这一步是两份契约的翻译点，所以字段名、`None` 要不要放进去，都在这里决定。

#### ⑧~⑪ pre-flight（全篇最关键的 20 行）

| 动作 | 拿到什么 | 没拿到什么 |
|---|---|---|
| `build_request(...)` | 组装好的 `Request` 对象 | **不发网络** |
| `send(..., stream=True)` | 状态码 + 响应头 | **一行 body 都没读** |
| `http.request(...)`（非流式） | 状态码 + 响应头 + **整个 body 已进内存** | — |

**为什么这样就能回 502**：

```text
send(stream=True) 返回的那一刻：上游响应头到手，我们【还没】发自己的响应头
                                → 检查状态码还来得及 → 抛 AppError → 502 ✅

如果挪进 event_source() 里（生成器内部第一行）：
   return StreamingResponse(...) 已经执行
   → 200 + chunked 已发给客户端
   → 这时才发现上游 401 → 502 发不出去
   → 只能在流里写一个错误帧，前端拿到的是「200 但内容里带 error」
   → 且失败发生在【第一帧发出之前】，客户端会看到连接挂着不回包
```

⭐ **pre-flight 换来的不是「更早发现错误」，而是「保留了一个可以表达错误的通道（状态码）」**。这个区别在面试里很加分。

**L2 为什么用 `is_success` 而不是 `>= 400`**：`raise_for_status()` 对 1xx/3xx **也抛**。302 说明「接口地址搬家了」—— 这是**配置层面**的问题，不是「上游拒绝服务」，混在一起会把排查方向带偏。

**📎 `ResponseNotRead` 专讲（这一节最容易被忽略的坑）**

```python
try:
    text = response.text
except httpx.ResponseNotRead:
    text = (await response.aread()).decode("utf-8", errors="replace")
await response.aclose()
```

| 怎么发出去的 | `response.text` 可用？ | 原因 |
|---|---|---|
| `await http.request(...)` | ✅ | body 已读进内存 |
| `await http.send(..., stream=True)` | ❌ `ResponseNotRead` | body 还在网络上；`.text` 是**同步属性**，没法 await |

致命之处：**`ResponseNotRead` 不是 `RequestError` 的子类** → L1 的 `except httpx.RequestError` 抓不到它 → 直接穿透到 500 兜底 → 用户看到「服务内部错误」，而真实原因只是「想读上游 401 的错误正文，但读法不对」。

> 📎 这正是 9b-4a 那个「三道门全绿但真实环境 500」的 bug：`_request(..., stream: bool = True)` 默认值写反，`list_models()` 走了流式路径。
> **MockTransport 测不出来**，因为假响应的 body 本来就在内存里 —— 假上游天然「已读完」。

**判据一句话**：`.` `.text` 是**同步属性**、`.aread()` 是**异步方法**。同步 / 异步的边界，就是这类 bug 的产地。

#### ⑫ 状态码焊死

```python
return StreamingResponse(
    event_source(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",       # 别让中间层缓存（否则可能拿到别人的答案）
        "X-Accel-Buffering": "no",         # 给 nginx 看：别攒缓冲（否则流式失效）
    },
)
```

注意这一行**只创建对象，一个字节都还没发**。真正发送是框架执行 `await response(scope, receive, send)`。但对业务代码而言效果一样：**从这里之后，没有状态码可言了**。

#### ⑬~⑱ 逐帧流水线（两层解析）

```text
上游字节流（互联网上的 TCP 分片，边界随机）
   │
   │  httpx.Response.aiter_lines()     ← httpx 负责：解码 + 按 \n 切行 + 去行尾
   ▼
行（可能有空行 ''、可能不是 data: 开头）
   │
   │  LlmChatStream.aiter_chunks()     ← 我们负责 L1 协议层
   │     ① not line.startswith("data:") → 跳过
   │     ② raw = line[5:].lstrip(); if not raw → 跳过（空 data 行）
   │     ③ raw.strip() == "[DONE]" → 记 seen_done，跳过
   │     ④ seen_done 之后的帧全跳（上游多发的东西）
   │     ⑤ json.loads(raw) → 可能是 None / list / str / int
   │     ⑥ isinstance(parsed, dict) 检查 → 不是对象就 warning + 丢
   ▼
dict（★ 契约保证：到这里一定是 dict）
   │
   │  event_source() 的 async for       ← 我们负责 L2 字段层
   │     usage  = _as_dict(chunk.get("usage"))      ① 静默收窄
   │     choices = chunk.get("choices") or []
   │     ⑦ isinstance(choices, list)?   否则 warning + continue
   │     ⑧ 空列表？→ 纯用量帧，处理完 continue
   │     choice = choices[0]
   │     ⑨ isinstance(choice, dict)?    否则 warning + continue
   │     ⑩ choice["index"] != 0 → continue（多候选用）
   │     delta = _as_dict(choice.get("delta"))      ① 静默收窄
   │     finish_reason 是 str 且非空 → yield 帧；非 str 且非 None → warning
   │     text = delta.get("content")
   │     ⑪ isinstance(text, str)? 否则（非 None 时）warning + continue
   │     ⑫ 空字符串 → continue
   │     content_frames += 1
   ▼
我们自己的帧  data: {"delta": "..."}\n\n     ← ★ yield 一次 = 发一帧
```

⭐ **为什么 `isinstance(parsed, dict)` 必须在 `aiter_chunks` 里、不能移到路由里**：

`aiter_chunks` 标注了 `-> AsyncIterator[dict[str, Any]]`，这是**对调用方的承诺**。路由里再写一次 `isinstance(chunk, dict)`，mypy 会报：

```text
error: Statement is unreachable  [unreachable]
```

因为**刚承诺它是 dict，转头又怀疑它不是**。这不是 mypy 太严 —— 是**契约设计冲突**，正确做法是让承诺在**能兑现的地方**兑现（详见 §14.4 ⑤、笔记专题 12）。

### 9.9.5 三条最容易记错的规律

| # | 容易记错 | 正确理解 |
|---|---|---|
| 1 | 「中间件日志的 16ms 就是请求耗时」 | ❌ 那是**到响应头为止**的耗时（📎 9.9.4 ③ 实测：日志 42.7ms / 流结束 1267ms）。流式请求的真实耗时要另记 |
| 2 | 「`.text` 读响应正文，总能读」 | ❌ `stream=True` 时抛 `ResponseNotRead`，它**不是** `RequestError`，会漏到 500；要用 `await aread()` |
| 3 | 「错误都用一个 `except Exception` 抓」 | ❌ `CancelledError` / `GeneratorExit` 直接继承 `BaseException`，**故意**漏过去。改成 `except BaseException` 会把「客户端断开」误当成「我方故障」 |

### 9.9.6 一句话总结

> **一条流式请求有两个不可逆的时刻：⑧（钱花出去了）和 ⑫（状态码焊死了）。
> 所有的防御都安排在这两个时刻之前（pre-flight、业务校验），或者安排在这之后唯一的表达通道里（错误编码进流）。**

## 9.10 什么时候必须等完整 body，什么时候该流式（接收 × 返回，2026-10-23）

> **起因**：学习者问「什么时候必须等完整 body？什么时候需要用流式逐帧接收和返回 body？」
> 关键：这是**两个独立的问题**，不是一件事。

### ① 一句话判据

> **看「第一个有用的字节，什么时候能被用掉」。**
> 如果答案是「等最后一个字节到齐」，就等完整 body；否则就该流式。

### ② ⭐ 2×2 矩阵：接收 × 返回（本节最该记住的东西）

| | **返回非流式**（攒完一次发） | **返回流式**（边收边发） |
|---|---|---|
| **接收非流式**<br>（body 一次读完） | **普通 CRUD**<br>查数据库 → 返回 JSON<br>📎 我们的 `/v1/upstream/models` | **本地数据导出**<br>读数据库游标 → CSV/NDJSON 流式下载<br>（body 是**我方**产生的，不是收来的） |
| **接收流式**<br>（`send(stream=True)`） | **后端聚合**<br>上游流式收，攒完再一次性返回<br>（能边收边记账、能中途取消省钱） | **纯透传**<br>上游流式收，逐帧转发<br>📎 我们的 `/v1/chat/stream` |

⭐ **最常被忽略的是左下角**：它是「非流式接口」的最佳实现方式（见 ⑥）。

### ③ 什么时候**必须**等完整 body

判据：**处理过程需要「全局视角」** —— 少一个字节就做不出来。

| # | 场景 | 为什么 | 反例（可以流式的版本） |
|---|---|---|---|
| 1 | `response.json()` 解析 | JSON 语法是**整体**的：`{"a": [1, 2` 无法解析 | **NDJSON / SSE / JSON Lines**：每行**自足**，逐行可解析 |
| 2 | 校验 / 签名 / 哈希 | 校验和必须覆盖全部字节 | — |
| 3 | 排序 / 聚合 / 去重 / 取 top-k | 得见过所有元素才能排序 | 只「取前 10 个」→ 可流式提前停 |
| 4 | 需要先看全貌再决定 | 比如「总数是多少」 | — |

📎 本项目实例：`list_models()` 里 `response.json()` 整体解析，且 `total` 要由**全部**条目算出来 ——
**即使能逐条解析，也得等收完才能给 `total`。**

### ④ 什么时候**必须**流式

判据：**「有用」和「完整」不是同一时刻**。

| # | 场景 | 判据 | 例子 |
|---|---|---|---|
| 1 | 上游**持续产生**，用户能边看边用 | TTFB 是产品指标 | LLM 生成、日志 tail、实时行情 |
| 2 | body **上界未知或大于内存** | 不敢 `b"".join(...)` | 大文件下载、视频、全表导出 |
| 3 | 需要**透传**，中间层不能缓冲 | 缓存 = 延迟 = 功能失效 | SSE 代理（`X-Accel-Buffering: no`） |
| 4 | 能**中途取消来省钱** | 提前停 = 少算 token | 客户端断开 → `aclose()` 让上游停 |

📎 `/v1/chat/stream` 同时命中 1、3、4。

### ⑤ 三个容易搞反的边界

#### ① 「body 小」不等于「该一次读完」

📎 `/v1/chat/stream` 一次响应可能只有 100 字节（"1 2 3"），**但必须流式** ——
因为那 100 字节是 **1.2 秒内分批产生的**。

⭐ 判据不是「体积」，是「**到达是否分散在时间上**」。但反过来：500MB 文件若是**一次性生成**的，也必须流式（这时判据是体积）。

> **两个判据取「或」：`到达分散在时间上` OR `上界未知/过大` → 流式。**

#### ② 「我最后要整块数据」不等于「必须非流式接收」

反例就是 ② 的左下角：**接收流式 + 攒完再返回非流式**。三个好处：

| 好处 | 说明 |
|---|---|
| 可以**中途取消** | 用户点「停止」→ `aclose()` → 上游停止生成、**不再计费** |
| 可以**边收边记账** | 每帧的 `usage` 立刻落库，不用等最后 |
| 可以**防御坏帧** | 逐帧守卫（`_as_dict` 那套），而不是一次 `.json()` 全炸 |

⭐ 所以「非流式接口」的最佳实现往往是「**内部流式收 + 外部一次性返回**」。

#### ③ 能重试的简单性是真金白银

| | 非流式 | 流式 |
|---|---|---|
| 失败重试 | 重发一次就行（幂等读接口） | **已发出的帧收不回来** |
| 断点续传 | 不需要 | 需要 Range / `Last-Event-ID` 等协议支持 |

⭐ 判据：**如果这个请求可以「重来一次」，非流式的简单性值得珍惜**；
只有重来代价高（生成很久、花钱）时才值得承担流式的复杂度。

### ⑥ 协议的启示：想流式，就得让每一片「自足」

| 格式 | 能否流式解析 | 原因 |
|---|---|---|
| 一个大 JSON `{"choices": [...200 条...]}` | ❌ | 语法整体性 |
| **NDJSON / JSON Lines** | ✅ | 每行自足 |
| **SSE**（`data: {...}\n\n`） | ✅ | 每帧自足 + 空行分界 |
| CSV | ✅ | 行自足（但**表头**要单独处理） |
| Protobuf / gRPC 流 | ✅ | 有长度前缀分帧 |

⭐ 所以上游把「一次生成」**切成 N 个自足的 JSON 帧**，我们才有东西可以逐帧处理 ——
**这不是巧合，是协议设计**。

### ⑦ 本项目地图

| 接口 / 场景 | 接收 | 返回 | 为什么 |
|---|---|---|---|
| `GET /v1/upstream/models` | 非流式 | 非流式 | 要 `json()` + 算 `total` |
| `POST /v1/chat/stream` | **流式** | **流式** | 纯透传，TTFB 是命门 |
| `POST /v1/chat`（现在） | — | — | 还是 echo，不碰上游 |
| `POST /v1/chat`（**接真上游后建议**） | **流式** | 非流式 | 能中途取消省钱 + 逐帧记账 + 防坏帧 |
| **Function Calling / tool_calls**（阶段 2） | **必须等完整** | — | ⚠️ `arguments` 是**字符串片段流式拼装**（`{"loc` → `ation":"北` → `京"}`），**拼完才能 `json.loads`** |
| **RAG 检索**（阶段 3） | **必须等完整** | — | 要 Rerank / 排序 / 取 top-k → 需要全局视角 |
| **RAG 生成**（阶段 3） | 流式 | 流式 | 检索完就有上下文，生成阶段同 `/v1/chat/stream` |
| **Agent 多步**（阶段 4） | **混合** | 混合 | 每一步「思考 + 调工具」要完整（解析参数），**最终回答**可流式 |

### ⑧ 三句话判据

1. **接收和返回是两个决定**，可以任意组合 —— 别默认「流式收就必须流式发」。
2. **判据看两个「时刻」**：第一个有用字节 vs 最后一个字节。**两者分离，才值得流式。**
3. **想流式，先让数据「分片自足」** —— 整体 JSON 不行，NDJSON / SSE 行。
   协议设计决定了你能不能流。
## 9.11 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 9 SSE 流式）。
> **第 57~59 题专门考 §9.9 的三张图**（走完整路径 / 断开的三个问题 / 守卫放错位置）。

---

# Step 10 · 数据库（SQLAlchemy 2.1 异步，2.0 风格 API）

## 定位

> LLM 应用的三个刚需数据：**会话历史、文档元数据、调用记录（成本/可观测）**。
> 本 Step 用 SQLAlchemy 2.1 的 **2.0 风格 API** + SQLite 起步（⚠️ 生产换 PostgreSQL，写法几乎不变）。
>
> ⚠️ **「2.0 风格」≠「2.0.x 版本」**：`Mapped` / `mapped_column` / `DeclarativeBase` 这套写法叫「2.0 风格 API」，
> 而本项目实际锁的是 **2.1 系列**（`sqlalchemy[asyncio]>=2.1,<2.2`，本机解析到 2.1.6）。

| 小步 | 产出 | 状态 |
|---|---|---|
| ① §10.1 依赖取证 | `sqlalchemy[asyncio]` + `aiosqlite`；独立 venv 复现 greenlet 缺失 | ✅ 2026-10-23 |
| ② §10.2 模型定义 | `src/app/models.py`：`Base` + `Conversation` | ✅ 2026-10-23 |
| ③ §10.3 引擎与会话工厂 | `config.database_url` + `src/app/database.py` + `.gitignore` 忽略 `*.db` | ✅ 2026-10-24 |
| ④ §10.3b 连接池补讲 | 连接池原理 / `__aexit__` 关闭时机 / `yield` 位置 | ✅ 2026-10-24 |
| ⑤ §10.4 前半 · lifespan 集成 | 启动段建表、关闭段 `dispose()` | ✅ 2026-10-24 |
| ⑥ §10.4 后半 · `get_db` + `DbDep` | `deps.py`：一次请求一个会话 + 正常提交 / 异常回滚 | ✅ 2026-10-25 |
| ⑦ §10.5 CRUD | POST ✅ / GET 列表 ✅ / GET 详情 ✅；DELETE 待做 | 🟡 进行中 |
| ⑧ §10.6 N+1 + usage 落库 | `selectinload` 预加载；调用记录表保存上游 `usage` | ⬜ 待做 |
| ⑨ §10.8 自检 | 本节自检 7+ 题 | ⬜ 待做 |

## 10.1 ⚠️ 第一个坑：装 `sqlalchemy` 不够（这是 **2.1 起**的行为）

**版本边界先说清楚**（📎 2026-10-23 在两个独立环境分别实测）：

| 版本 | 裸装（不带 extra）后 `import sqlalchemy.ext.asyncio` | 结论 |
|---|---|---|
| `sqlalchemy==2.0.55` | **成功**（greenlet 被自动装上） | 旧版行为 |
| `sqlalchemy==2.1.6` | **失败**：`ModuleNotFoundError: No module named 'greenlet'` | 2.1 起需显式 extra |

⭐ 所以「必须写 `sqlalchemy[asyncio]`」这条**不能泛化到 2.0** —— 这是 2.1 起才有的安装行为变化。

**实测报错**（2.1.6 裸装后直接 import 异步模块）：

```text
sqlalchemy\ext\asyncio\__init__.py:28: in <module>
    concurrency._concurrency_shim._initialize()
...
ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed.
In order to ensure this dependency is available, use the 'sqlalchemy[asyncio]' install target:
'pip install sqlalchemy[asyncio]'
```

**正确命令**（带上界，防止 2.2 出破坏性升级）：

```powershell
uv add "sqlalchemy[asyncio]>=2.1,<2.2" aiosqlite
```

**实测结果**：本机解析到 `sqlalchemy==2.1.6` / `greenlet==3.5.6` / `aiosqlite==0.22.1`，异步导入成功。

| 认知 | 说明 |
|------|------|
| 2.1 的 `sqlalchemy` 本体**不装**异步所需的 `greenlet` | 它在 `[asyncio]` 这个**额外依赖（extras）**里 |
| 所以方括号写法 `sqlalchemy[asyncio]` | ⭐ 阶段 0 讲的"直接依赖 vs 间接依赖"在**声明层**的体现 |
| `aiosqlite` **不在** extra 里 | 它是数据库**驱动**，要单独写进 `uv add` |
| 换 PostgreSQL 还要 `asyncpg` | `uv add "sqlalchemy[asyncio]>=2.1,<2.2" asyncpg` |

> ⭐ **这个坑值得记熟练**：几乎每个用 SQLAlchemy 异步的人第一次都会踩。
> 而且报错信息**已经告诉你怎么修了** —— 学会读报错里的 `Hint` / `use the ... install target`。

## 10.2 模型定义（SQLAlchemy 2.0 风格）

```python
from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
```

| 关键点 | 说明 |
|--------|------|
| `DeclarativeBase` | 2.0 风格的基类（旧写法是 `declarative_base()` 函数，**已过时**）。继承它的类会自动把表登记进 `Base.metadata`，`create_all` 就靠这份清单建表 |
| `Mapped[int]` | ⭐ **类型注解就是列定义**，mypy 能检查，IDE 有补全。没有 `Optional` = 数据库里 `NOT NULL` |
| `mapped_column(...)` | 列级配置（主键、长度、默认值） |
| `default=lambda: ...` | 默认值（⚠️ 不是 `default=datetime.now(UTC)`，同 pydantic 的 `default_factory` 陷阱） |

> ⭐ **`Mapped[T]` 的好处**：SQLAlchemy 从注解**推断列类型**，同时又让 mypy 知道
> `conv.title` 是 `str` 而不是 `Any`。**这是"注解即功能"的又一次体现**。

### ⚠️ 两个实测出来的「已知限制」

这两条不影响代码跑，但会影响你对**约束从哪来**的判断。

#### ① `String(100)` 在 SQLite 里**不强制**

📎 2026-10-23 实测：往 `String(100)` 列塞 **200 个字符的标题** → **静默存进去了**，没有任何报错。

```text
String(100) 列里存进多长: 200 个字符
→ SQLite 是否拒绝了超长值: 没有，静默存下
```

⭐ **SQLite 忽略所有长度约束**（它把 `VARCHAR(100)` 当 `TEXT` 处理，这是 SQLite 的"动态类型"设计）。换 PostgreSQL 才会真的报错。

**判据**：**长度校验必须放在 pydantic 层**（`ConversationIn` 的 `max_length`），不能指望数据库帮你挡。
`String(100)` 仍要写 —— 它是给 PostgreSQL / 建表文档 / 建模意图看的，不是给 SQLite 用的。

#### ② `created_at` 的时区**读回来会丢**

📎 实测往返：

```text
flush 后（内存里）: datetime(2026, 10, 23, 14, 9, 42, tzinfo=UTC)
从库里读回:        datetime(2026, 10, 23, 14, 9, 42)          ← tzinfo 没了
tzinfo 还在吗:     False
```

而且**换写法救不回来**：📎 实测 `DateTime(timezone=True)` 在 SQLite 上**读回同样是 `tzinfo=None`** —— 因为 SQLite 根本没有时区类型，它只存一个字符串。

**对策（本项目的约定）**：

| 做法 | 说明 |
|---|---|
| 库里**一律存 UTC** | 用 `default=lambda: datetime.now(UTC)` 保证写入就是 UTC |
| 读回**当作 UTC 处理** | 需要算时间差时 `.replace(tzinfo=UTC)`；展示时再转本地时区 |
| 真需要严格时区 | 换 PostgreSQL（有 `timestamptz`），或自定义 `TypeDecorator` 在读回时补上 `tzinfo` |

⭐ 判据：**数据库的「约束」和「类型」都是方言相关的** —— 写代码时以为的保证，换个方言可能成立、也可能不成立。凡是"靠数据库帮我挡"的想法，都要先问一句「这个方言真的会挡吗」。

## 10.3 引擎与会话工厂

**项目实际写法**（`src/app/database.py`，运行库用**文件**）：

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url)   # ① URL 来自配置，默认 sqlite+aiosqlite:///./app.db
SessionMaker = async_sessionmaker(engine, expire_on_commit=False)   # ②③

__all__ = ["engine", "SessionMaker", "AsyncSession"]
```

| # | 要点 |
|---|------|
| ① | URL 格式 `方言+驱动://路径`。本项目 `sqlite+aiosqlite:///./app.db`（**文件**，跨重启保留）；换 PostgreSQL 写 `postgresql+asyncpg://...`，只改这一处 |
| ② | `async_sessionmaker` 是**模具**：`SessionMaker()` 才产出一个新的 `AsyncSession`。⚠️ 把 `SessionMaker` 当会话用会 `AttributeError` |
| ③ | ⭐ **`expire_on_commit=False` 很重要**，见下 |

### ⚠️ `create_async_engine` **不连数据库**

```text
create_async_engine(url)   →  创建引擎对象（含一个空连接池），不建立任何连接
第一次执行 SQL 时          →  才真的 open 连接
```

📎 2026-10-24 实测：`from app.database import engine` 之后 `Test-Path app.db` 仍然是 **`False`** —— 文件都还没生成。

⭐ **判据：看到「engine 建好了」不等于「连上了」。** 判断连没连只能看有没有真的发出 SQL（或看 `app.db` 是否出现）。

### ⭐ 为什么引擎是**模块级单例**，不放 `lifespan`

| 理由 | 说明 |
|---|---|
| **决定性的**：非请求上下文也要能用 | 放 `app.state` 就必须先有 `request` → CLI / 定时任务 / 迁移脚本全部拿不到。**和 Step 9「全局 exception_handler 在 CLI 里失效」是同一条规律** |
| 类型检查 | `app.state` 是 `Any`，属性名拼错 mypy 查不到（本项目**待办 #8** 就是这个坑）；模块级对象 mypy 知道它是 `AsyncEngine` |
| 职责更单一 | `lifespan` 只管「启动建表 / 关闭 dispose」，不用管「创建」 |
| 不会重复创建 | `with TestClient(app)` 进两次 → `app.state` 版会造两个 engine，前一个没 dispose |

⭐ **判据**：**「只要进程活着就该存在的东西」→ 模块级单例；「每个请求各要一份的东西」→ 依赖注入。**
engine 属前者（连接池跨请求复用），session 属后者（一次请求一个事务）。

> ⚠️ **模块级单例也有代价**：测试想换成 `:memory:` 时不好办。对策正是 10.4 的 `get_db` 做成依赖 —— 测试用 `app.dependency_overrides[get_db]` 替换。**单例解决「生命周期」，依赖注入解决「可替换」，两件事各解决一半。**

### `:memory:` + `StaticPool` 只用于**测试**

```python
from sqlalchemy.pool import StaticPool

mem_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,        # 让所有会话共用同一条连接 → 才能看到同一份内存数据
)
```

📎 本机 2.1.6 实测：`:memory:` 引擎**默认池已是 `StaticPool`**（`check_same_thread=True`）；**文件库**默认是 `AsyncAdaptedQueuePool`（`check_same_thread=False`）。显式写 `StaticPool` 只是把选择标清楚。

⚠️ **`:memory:` 数据库进程一结束就消失** —— 适合测试，不能当持久化存储。本项目运行时用**文件**，测试时可覆盖成内存库。

> ⚠️ 旧教程常见的 `connect_args={"check_same_thread": False}` 是给**同步** `sqlite3` + FastAPI 线程池用的。`sqlite+aiosqlite` 走 `AsyncAdaptedQueuePool`，实测默认已是 `check_same_thread=False`，不必手写。

**为什么 `expire_on_commit=False`**：

| 设置 | 行为 |
|------|------|
| 默认 `True` | commit 后对象的所有属性**过期**，再访问 `conv.title` 会**触发新的查询** |
| `False` | commit 后属性仍可直接读 |

> ⚠️ 异步下更危险：过期后访问属性需要**隐式 IO**，而在**同步序列化阶段**（如 `response_model` 处理时）
> 无法 await → 报错。📎 本机 SQLAlchemy 2.1.6 + `aiosqlite` 实测：**顶层异常是 `StatementError`，其 `orig` 才是 `MissingGreenlet`** —— 别按顶层异常名去猜。
> **`expire_on_commit=False` 是异步 SQLAlchemy 的标准配置。**

## 10.3b 连接池与 `async with` 的关闭时机（2026-10-24 补讲）

> **起因**：学习者问「连接池是什么，项目里怎么维护的？`async with create_llm_client() as client:` 这段到底怎么运行，我没看到关闭指令。」
> 这两件事其实是同一件事：**`async with` 的关闭动作不在那一行，而在对象的 `__aexit__` 里**。

### ① 连接池是什么

> **连接池 = 一组"已经建好的连接"，用完不扔，放回去给别人接着用。**

建一条 TCP 连接要握手。📎 Step 9 已量过真实公网代价：**TCP 19~45ms + TLS 43~70ms = 合计 60~115ms**。
不用池的话，**每个请求都要先付一次这个过路费**才开始传数据。

### ② 📎 实测：复用 vs 不复用

本机起了一个会记「accept 了几条连接」的 TCP 服务器，各发 20 次（已排除首次热身）：

```text
  20 次请求，复用同一个 client : 新连接  1 条  总耗时  35.1ms  平均  1.75ms/次
  20 次请求，每次新建 client   : 新连接 20 条  总耗时 220.2ms  平均 11.01ms/次
  新建方案慢 6.28 倍
```

⭐ **20 次请求只开了 1 条 TCP 连接**，客户端端口证明是同一根复用：

```text
[A] 一个 AsyncClient 连发 3 次：TCP 新连接数 = 1    客户端端口 = [51116]
[B] 每次新建 AsyncClient：      TCP 新连接数 = 3    客户端端口 = [51117, 51118, 51119]
```

⚠️ 6.28 倍还只是**本机回环网络**（握手几乎不花时间）。换成真实公网，差距更大。

### ③ 项目里有**两个**池

| # | 池 | 装什么连接 | 创建 | 释放 |
|---|---|---|---|---|
| 1 | **httpx 的池** | 到 DeepSeek 的 TCP | `llm_client.py` `create_llm_client()` 里的 `httpx.AsyncClient(...)` | `LlmClient.__aexit__` → `await self._http.aclose()` |
| 2 | **SQLAlchemy 的池** | 到 SQLite/PG 的连接 | `database.py` `create_async_engine(...)` | `lifespan` 的 `await engine.dispose()` |

**维护方式完全一样**：

```text
进程启动时创建一次  →  整个服务期反复复用  →  进程退出时释放一次
```

📎 **SQLAlchemy 池的内部状态实测**（默认 size=5 / max_overflow=10）：

```text
=== 还没执行过任何 SQL ===
  池类型: AsyncAdaptedQueuePool
  size = 5        checkedin = 0      checkedout = 0     _max_overflow = 10
  ⭐ checkedin=0 → 池是【懒】的，不执行 SQL 就一条连接都不建

=== 执行一次 SQL 之后 ===
  checkedout（借出中）= 1   checkedin（池内空闲）= 0

=== 归还之后 ===
  checkedout = 0   checkedin = 1     ← ★ 连接没销毁，放回池里等下次用

=== dispose 之后 ===
  checkedin = 0                      ← ★ 全部关掉
```

⭐ `checkedin = 0` 这条和「`create_async_engine` 不连库」是**同一件事的两面**。

### ④ ⭐ `async with` 到底怎么运行：关闭指令在哪

```python
async with create_llm_client() as client:
    app.state.llm_client = client
    yield
```

关闭动作**不在这一行**，而在 `LlmClient` 的两个"魔法方法"里：

```python
async def __aenter__(self) -> "LlmClient":      # 进入 with 时调用
    return self

async def __aexit__(self, *exc_info: object) -> None:   # 离开 with 时调用
    await self._http.aclose()                   # ★ 关闭指令就在这一行
```

⭐ **`async with` 是语法糖**，等价于：

```python
client = await X.__aenter__()
try:
    <块内代码>
finally:
    await X.__aexit__(...)      # 不管正常结束还是抛异常，一定执行
```

📎 **实测调用顺序**（给 `LlmClient` 套了个只加日志的 `Spy` 子类，行为不变）：

```text
=== 正常走完 async with ===
  ① __aenter__ 被调用（返回 self）
  ② 块内正在用：is_closed=False
  ③ __aexit__ 被调用  exc_type=None
     ④ __aexit__ 里的 await self._http.aclose() 执行完 → 池已关闭
  ⑤ with 块之后的代码

=== 块内抛异常 ===
  ① __aenter__ 被调用
  ② 块内抛 RuntimeError
  ③ __aexit__ 被调用  exc_type=RuntimeError      ← ★ 抛异常也照样关闭
     ④ 关闭完成
  ⑤ 外层捕获到：模拟业务异常

=== 手写 try/finally（等价写法）===
  事件顺序与第一种【完全一样】  ← 语法糖的证明
```

### ⑤ `yield` 在这里的角色

```text
uvicorn 启动
  ├─ 调用 lifespan(app)
  │     ├─ ① __aenter__  → 池建好（空池）
  │     ├─ ② app.state.llm_client = client
  │     ├─ ③ 遇到 yield  → 【挂起，控制权交回 uvicorn】
  │     │                    ⚠️ 此刻两个 async with 都还没退出
  │     │  ←←← 服务运行期（可能几小时），池一直在，反复复用 →→→
  │     └─ ④ uvicorn 关闭时，从 yield 之后继续
  │           ├─ 退出 async with → __aexit__ → aclose()
  │           └─ await engine.dispose()
  ▼
```

⭐ **判据**：**`yield` 的位置 = 「启动完成」和「开始关闭」的分界线。**
它在 `async with` 里面，就等于告诉 Python：「从我暂停到恢复之前，这个 with 块不算结束，所以 `__aexit__` 不要跑。」

📎 **放错位置不会报错，但清理会发生在启动阶段**（实测事件顺序）：

```text
写法 B（yield 在 async with 外面）
  1. 上游适配器: 打开
  2. 上游适配器: 关闭          ← ★ 启动阶段就关了
  3. yield 之前
  4. 【服务运行中】client.closed = True     ← 每个请求拿到坏客户端

写法 A（我们的）
  1. 上游适配器: 打开
  2. 【服务运行中】client.closed = False    ← 正常
  3. 上游适配器: 关闭
  4. yield 之后（关闭段）
```

### ⑥ 为什么 `create_llm_client()` 用 `return` 而不是 `yield`

| 写法 | 谁负责关 | 能不能交出去 |
|---|---|---|
| `yield` 造依赖 | 造它的那个函数（`finally` 里） | ❌ 出不了那个函数 |
| **`return` 一个实现 `__aenter__`/`__aexit__` 的对象** | **拿到它的人**（`async with`） | ✅ 可以传给别人 |

同一个工厂函数，项目里有两种用法：

```python
# 用法 1：CLI（src/app/main.py）—— 自己开自己关
async with create_llm_client() as client:
    ...

# 用法 2：HTTP 服务（lifespan）—— 开一次，挂到 app.state 给所有请求共用
async with create_llm_client() as client:
    app.state.llm_client = client
    yield                    # 关闭仍由这一层负责
```

⭐ 这正是「`return` 对象」比「`yield` 依赖」灵活的地方。

### ⑦ 不关闭的两种债务

| 池 | 场景 | 后果 |
|---|---|---|
| httpx | 流式响应不 `aclose` | 📎 Step 9 实测：第二个请求 **`PoolTimeout`** |
| httpx | 反复 `TestClient` / `--reload` | 连接累积 → `Too many open files` |
| 数据库 | PostgreSQL（`max_connections` 有上限） | 重启几次吃满 → 新连接被拒 → **全站 500** |
| 两个 | 单进程 SQLite / CLI 退出 | 操作系统回收，**看不出问题**（所以最危险） |

⭐ **判据**：**「不是你的资源了，就还回去。」** —— Step 9 的 `stream=True` 要 `aclose`、这里的 `engine.dispose()`，是同一条。

### ⑧ 三句话判据

1. **连接池 = 复用已建好的连接**，省掉每次 60~115ms 握手（📎 实测复用快 **6.28 倍**，20 次请求只开 1 条 TCP）。
2. **`async with` 的关闭指令在对象的 `__aexit__` 里**，不在 `with` 那一行；它保证**正常结束和抛异常都执行**（📎 两种路径实测都调到了）。
3. **`yield` 是「启动完成 / 开始关闭」的分界线**：在里面 → 暂停期间池不会被关；在外面 → 清理发生在启动阶段（📎 `client.closed = True`）。
## 10.4 会话生命周期：`yield` 依赖 + `lifespan`

同一个 `yield` 机制，两个**不同时间粒度**的用法：

```python
# ① 进程级：整个进程一次
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)   # 启动时建表
    async with create_llm_client() as client:
        app.state.llm_client = client
        yield                                            # ← 分界线
    await engine.dispose()                               # 关闭时释放连接池


# ② 请求级：每个请求一次
async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionMaker() as session:
        try:
            yield session                                # ← 分界线
            await session.commit()                       # 正常结束就提交
        except Exception:
            await session.rollback()                     # 出错就回滚
            raise


DbDep = Annotated[AsyncSession, Depends(get_db)]
app = FastAPI(lifespan=lifespan)
```

| | `lifespan` | `get_db` |
|---|---|---|
| `yield` 分界 | 「启动完成 / 开始关闭」 | 「路由开始 / 路由结束」 |
| 执行次数 | **整个进程 1 次** | **每个请求 1 次** |
| 谁在驱动 | uvicorn 的 LifespanManager | FastAPI 的 `AsyncExitStack` |
| 收尾代码 | `engine.dispose()` | `commit()` / `rollback()` |

⭐ **判据：看到 `yield` 就问「谁在它外面驱动」** —— 决定它跑几次、什么时候收尾。

| # | 说明 |
|---|------|
| ① | `conn.run_sync(...)` 用 **greenlet 在同一个线程内**适配同步风格的 SQLAlchemy API，并把其中的数据库 IO 接到异步驱动。⚠️ **它不是线程池**：回调里做阻塞 IO 或长 CPU 计算照样会卡住事件循环 |
| ② | 进程退出时释放连接池，否则连接泄漏 |
| ③ | ⭐ **"路由正常返回才提交"**：`commit()` 写在 `yield` **之后**，所以只有路由正常结束才走到它 |
| ④ | 回滚后**必须 `raise`** —— 详见下方「📎 实测订正」 |
| ⑤ | lifespan 里初始化数据库/连接池，**不是模块顶层**（Step 6.4） |

### 异常是怎么「送」进 `get_db` 的

路由抛异常时**不是** `get_db` 主动发现，而是框架把它**塞回**到 `yield` 那一行：

```python
async with SessionMaker() as session:
    try:
        yield session            ← 路由在跑；异常会在这里被"抛回来"
        await session.commit()   ← 只有正常路径走到这
    except Exception:            ← 异常路径从这里进
        await session.rollback()
        raise
```

📎 实测（`/ok` 正常 + `/boom` 抛异常，然后直接读库）：

```text
  /ok   -> 200 {"msg":"ok"}
  /boom -> 500
  库里行数 = 1
    id=1 title='提交我'          ← 正常路由的数据留下了，'回滚我' 没留下
```

⭐ **同一个函数、两条路径，结果是「只提交成功的那个」** —— 这是把事务边界收在一处的直接收益。

### 📎 实测订正：少了 `raise` 到底会怎样（原写法是**错的**）

本笔记原先写「不 `raise` → 客户端收到 200（非常隐蔽的 bug）」。**2026-10-25 实测推翻了这条**：

```text
❌ 少写 raise（FastAPI 0.143.0）：
   客户端 status=500
   body={"error":{"code":"INTERNAL_ERROR","message":"服务内部错误","request_id":"d2b074e21167"}}
   日志：fastapi.exceptions.FastAPIError: Response not awaited.
        There's a high chance that the application code is raising an exception
        and a dependency with yield has a block with ... except Exception,
        and is not raising the exception again.
   异常链：FastAPIError.__cause__ = None      ← ★ 原始 RuntimeError 彻底没了
```

| 版本 | 客户端 | 日志里能看到 |
|---|---|---|
| ✅ 有 `raise` | 500 + 统一形状 + `request_id` | **真实根因**：`RuntimeError: 故意失败：这是业务根因` |
| ❌ 少 `raise` | 500 + 统一形状 + `request_id`（**看起来一模一样**） | 只有 `FastAPIError: Response not awaited...`，**根因 / 类型 / 行号全丢** |

⭐ **结论不变（`raise` 必须有），但理由要改写**：

> 不是「客户端会收到 200」，而是「**日志里从此查不到真正出了什么事**」。
> 更阴险的是：**客户端看到的响应完全一样**，只有去翻日志的人才会发现不对劲。

> ⭐ **`try/except/raise` 这个模式值得记死**：
> **清理动作可以吞异常，但业务异常必须重新抛出**。

### 📎 同一个会话 `commit()` 两次会怎样

📎 实测：**不报错，第二次是无害的空提交**（SQLAlchemy 会自动开启一个新事务再提交）。

```text
  路由里 commit 一次后：status=200  body={"msg":"ok"}
  库里行数 = 1                                  ← 数据只有一份，没有重复插入

  === 同一个 session 连 commit 两次 ===
    第 1 次 commit 成功
    第 2 次 commit 成功（不报错，因为会自动开启新事务）
```

⚠️ 但**不要**因此在路由里也写 `commit()`：

| 做法 | 问题 |
|---|---|
| 依赖统一 `commit`（本项目） | 事务边界只有一处，改规则只改一处 |
| 路由里各自 `commit` | N 个接口 N 处要记得写；且**提交早了，后面的修改就不在同一事务里**（没法整体回滚） |

## 10.5 CRUD（本项目实际写法 + 实测）

### 契约先分家：`ConversationIn` / `ConversationOut`

```python
class ConversationIn(BaseModel):
    title: str = Field(min_length=1, max_length=100, description="对话标题")


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    created_at: datetime
```

⭐ **入参和出参永远不共用一个模型**：

| 契约 | 谁填 | 能不能有 `id` / `created_at` |
|---|---|---|
| `ConversationIn` | 用户 | ❌ 数据库生成，用户填了也不该采纳 |
| `ConversationOut` | 我们 | ✅ 必须（用户要知道新建的是几号） |

- **`max_length=100` 必须写**：📎 10.2 实测 SQLite **不强制** `String(100)`，长度校验只能靠 pydantic。
- **`from_attributes=True`**：📎 实测两种情况要分清 —— 经 FastAPI `response_model` 返回 ORM 对象时**不加也能工作**（FastAPI 先转 dict）；但**脱离 FastAPI** 用 `Model.model_validate(orm_obj)` 时**必须加**，否则 `ValidationError`。

### POST：`add` → `flush` → `return`

```python
@app.post("/v1/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(payload: ConversationIn, db: DbDep) -> Conversation:
    conv = Conversation(title=payload.title)   # ⚠️ payload.title，不是 payload
    db.add(conv)                                # 登记，一个 SQL 都没发
    await db.flush()                            # 发 INSERT，拿到自增 id
    return conv                                 # 提交由 get_db 在返回后做
```

📎 实测：

```text
  POST {"title":"第一次对话"} → 201 {"id":1,"title":"第一次对话","created_at":"2026-10-25T08:43:49.609945Z"}
  POST {"title":"第二次对话"} → 201 {"id":2,...}          ← id 由数据库分配，代码里没有 1/2
  POST {"title":""}          → 422 string_too_short
  POST {"title":"a"*101}     → 422 string_too_long
  直接读库： (1, '第一次对话', '2026-10-25 08:43:49.609945')
```

> ⚠️ **`await db.refresh(conv)` 不是必需的**（本项目没用它）：`id` 由 `flush` 拿到，`created_at` 由 Python 端 `default=lambda` 在 `flush` 时生成 —— 两者都已在内存对象里。
> **只在用「服务器端默认值」（`server_default`，如 `CURRENT_TIMESTAMP`）时才需要 `refresh`** 把库端算出来的值读回来。

### ⚠️ 坑 1：`Conversation(title=payload)` 会 500，而三道门拦不住

📎 真实异常（学习者踩到）：

```text
sqlalchemy.exc.ProgrammingError: (sqlite3.ProgrammingError)
Error binding parameter 1: type 'ConversationIn' is not supported
[SQL: INSERT INTO conversations (title, created_at) VALUES (?, ?)]
[parameters: (ConversationIn(title='第一次对话'), '2026-10-25 08:41:13.767766')]
```

⭐ **为什么 mypy 没报**：`Conversation.__init__` 的签名是 `(self, **kwargs)` —— **参数就是 `Any`**。

| mypy 管 | mypy **不管** |
|---|---|
| `conv.title` **读出来**是什么类型 | **构造时传进去**的是什么类型 |

> **判据**：ORM 模型的字段类型标注是给**读取**用的（补全、`conv.title.upper()` 检查），**不保护写入时的取值**。
> 这和 Step 9 的 `json.loads()` 返回 `Any` 是同一个规律：**`Any` 赋给任何类型都合法**。

### ⚠️ 坑 2：`created_at` 在「API 响应」和「数据库」里格式不同

📎 实测：

```text
POST 响应：  "2026-10-25T08:43:49.609945Z"        ← 带 Z（内存对象，tzinfo 还在）
直接读库：    2026-10-25 08:43:49.609945          ← 无时区（SQLite 不存时区）
```

**后果**：同一个字段，POST 返回带 UTC 标记，GET（重新查库）返回不带 → 前端解析不一致。

**现在不改**。触发修的条件：前端开始用 `created_at` 做时间计算时。修法两种（读回时 `.replace(tzinfo=UTC)` / 自定义 `TypeDecorator`），到那时再定。

### GET 列表：`execute` → `scalars` → `all`

```python
@app.get("/v1/conversations", response_model=list[ConversationOut])
async def list_conversations(db: DbDep) -> list[Conversation]:
    result = await db.execute(select(Conversation).order_by(Conversation.id))
    return list(result.scalars().all())
```

📎 实测：

```text
  空表       -> []                                                    [200]
  两条       -> [{"id":1,...},{"id":2,...}]                            [200]
```

#### ⭐ `.scalars()` 不是「转换」，是「每行只取第 1 列」

📎 实测四种组合，最后一行的结果最关键：

```text
select(Conversation)             → .all()          : [Row, Row]
同上                              → .scalars().all() : [Conversation, Conversation]

select(Conversation.id, .title)  → .all()          : [(1, 'A'), (2, 'B')]
同上                              → .scalars().all() : [1, 2]        ← ★ title 被丢掉了
```

⭐ **判据**：`.scalars()` 只是取每行的第一列。我们 `select(Conversation)` 的第一列本来就是完整 ORM 对象，所以看起来像"转换"。
⚠️ 换成 `select(id, title)` 再用 `.scalars()` → **title 静默丢失，不报错**。

#### ⭐ `list(...)` 是给 mypy 看的，不是让代码能跑

📎 实测：

```text
  type(result.scalars().all())  = <class 'list'>
  isinstance(..., list)         = True
  能 append 吗                   = 能
```

运行时它**就是** `list`。去掉 `list(...)` 后 mypy 报：

```text
error: Incompatible return value type (got "Sequence[Conversation]", expected "list[Conversation]")
```

⭐ **原因**：`.all()` 的**声明**返回类型是 `Sequence[...]`（只承诺可遍历 / 可索引 / 可 `len`，**不承诺可变**），运行时给的是 `list`。
`list(...)` 的作用是**把类型承诺升级**到返回注解要求的 `list`。

⚠️ 这和 10.5a 那个事故是**相反**的情形：

| 事故 | 声明类型 | 运行时实际 | 谁拦住了 |
|---|---|---|---|
| 10.5a `Conversation(title=payload)` | `title: str` | 传进去的是 `ConversationIn` | ⚠️ **没人拦**（`**kwargs` 是 `Any`），运行时 500 |
| 10.5b `scalars().all()` 不套 list | `Sequence` | 实际是 `list` | ✅ mypy 拦（类型不匹配），运行时没事 |

⭐ 判据：**「运行时对不对」和「类型对不对」是两个独立问题。**
这次是「类型保守、运行时更宽」（安全）；上次是「类型承诺了但没人检查」（危险）。

#### ⭐ `order_by` 不能省、空表返回 `[]`

```text
SQL 标准：不写 ORDER BY 时，返回顺序【未定义】
```

⚠️ 实践中"恰好是插入顺序"只是 SQLite 当前的实现细节 —— 换库 / 加索引 / 行数变大走不同执行计划都可能变。**只要客户端会看到顺序，就必须显式 `order_by`。**

⭐⭐ **空集合返回 `200 []`，不是 404**：

| 场景 | 返回 | 理由 |
|---|---|---|
| 集合为空 | `200 []` | "查询成功，结果是空的" —— **正常答案** |
| 单个资源不存在 | `404` | "你要的那个东西没有" —— **找不到** |

反例：列表为空返回 404 → 前端把"404"当"还没建过对话"，但 404 同时又是"接口不存在" → **语义撞车**。

#### ⭐ 新暴露的一个不一致：`created_at` 的两种格式

📎 实测（同一批数据，POST 后再 GET）：

```text
POST 响应: "2026-10-25T10:04:33.132282Z"     ← 带 Z
GET  响应: "2026-10-25T10:04:33.132282"      ← 没有 Z（同一行数据！）
```

**原因**：POST 返回的是**内存里刚建的对象**（`tzinfo` 还在）；GET 返回的是**从库里重新读出来的**（SQLite 不存时区 → `tzinfo` 丢了）。

⚠️ **这是已知债务，现在不修**。触发条件：前端开始用 `created_at` 做时间计算时。修法（读回时补 `tzinfo` / 自定义 `TypeDecorator`）到那时再定。

### GET 详情：`db.get()` + 判空 → 404

```python
@app.get("/v1/conversations/{conv_id}", response_model=ConversationOut)
async def get_conversation(conv_id: int, db: DbDep) -> Conversation:
    conv = await db.get(Conversation, conv_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话不存在：{conv_id}",
        )
    return conv
```

📎 实测五种 URL：

```text
① /v1/conversations/1    -> 200 {"id":1,"title":"现有对话",...}
② /v1/conversations/999  -> 404 {"detail":"对话不存在：999"}
③ /v1/conversations/abc  -> 422 int_parsing  loc=["path","conv_id"]
④ /v1/conversations      -> 200 [{...}]           （1 段 vs 2 段，不冲突）
⑤ /v1/conversations/-1   -> 404 {"detail":"对话不存在：-1"}
```

#### ⭐⭐ `/abc` 是 422，`/999` 是 404 —— 谁拒的完全不同

| URL | 状态码 | **谁拒的** | 为什么 |
|---|---|---|---|
| `/abc`、`/1.5` | **422** | **FastAPI 的路径参数校验** | `conv_id: int` 转不动 → **你的函数体一行都没跑** |
| `/999`、`/-1` | **404** | **你的 `if conv is None`** | 是合法整数，只是表里没这行 |

⭐ 判据：**「格式不对」是 422（客户端的锅）；「格式对但没这条」是 404（数据的状态）。**
⚠️ `-1` 返回 404 不是 422 —— 负数是**合法整数**。

#### ⭐ 不判空的真实后果（📎 实测，只有一种死法）

```text
  抛 fastapi.exceptions.ResponseValidationError
  {'type': 'model_attributes_type', 'loc': ('response',),
   'msg': 'Input should be a valid dictionary or object to extract fields from',
   'input': None}
  客户端看到：500 Internal Server Error
```

链路：

```
db.get() 找不到 → 返回 None（不抛异常）
    → return None
    → response_model 拿 None 去过 ConversationOut
    → pydantic: "这不是 dict 也不是对象"
    → ResponseValidationError → 500
```

⚠️ **不是 `AttributeError`** —— `response_model` 在**读属性之前**先检查"输入是不是对象"。

⭐ 判据：**把 404 的错误伪装成 500，是最容易误导排查的一种** —— 客户端以为服务器坏了。

#### ⚠️ 「固定词」和「路径参数」同层时会冲突

📎 实测：

```text
场景 A（固定词在前，正确）：  /items/latest -> {"which": "latest"}
场景 B（固定词在后，错误）：  /items/latest -> 422 int_parsing loc=["path","item_id"]
                             ⚠️ 永远走不到 /items/latest —— "latest" 被当成 item_id
```

⭐ 路由**按注册顺序**匹配，先注册的先命中。

但本项目这两个**不冲突**（📎 实测）：`/v1/conversations` 是 1 段、`/v1/conversations/{conv_id}` 是 2 段，URL 结构上撞不到。

⚠️ **加 `/v1/conversations/latest` 时就会撞**（都是 2 段）—— 那时必须写在 `{conv_id}` 之前。项目里已有先例：`/v1/models/latest` 就写在 `/v1/models/{model_name}` 前面。

⭐ 判据：**同层出现「固定词」和「路径参数」时，固定词必须在前；段数不同则无所谓。**

### 方法速查

| 方法 | 用途 |
|------|------|
| `db.add(obj)` | 加入会话（**不立即执行**） |
| `await db.flush()` | **执行 SQL**，拿到自增 ID，但**不提交** |
| `await db.refresh(obj)` | 重新从数据库读该对象（服务器端生成值时才需要） |
| `await db.execute(stmt)` | 执行查询 |
| `result.scalars().all()` | 取单个实体列的列表 |
| `await db.get(Model, pk)` | 按主键查（表达直接；若对象已在 identity map 中还可不发 SQL，**不应笼统认为它总比 `select` 快**） |
| `await db.delete(obj)` | 标记删除。⚠️ `AsyncSession.delete()` **是异步方法，必须 `await`**（顺手漏掉不会报错，但删除不生效） |

> ⭐ **`add` vs `flush` vs `commit`** 的区别（面试爱问）：
> | 动作 | 发 SQL？ | 能否回滚？ | 事务结束？ |
> |------|---------|-----------|-----------|
> | `add` | ❌ | — | ❌ |
> | `flush` | ✅ | ✅ | ❌ |
> | `commit` | ✅ | ❌（已落盘） | ✅ |
>
> **`flush` 的意义**：让数据库生成的值（自增 ID、默认值）变得可用，同时**保留回滚能力**。
> 这也是为什么 `get_db` 里统一 `commit`、而路由里只 `flush` —— **事务边界收在一个地方**。

**⚠️ 不用 `ORM 对象` 直接返回行不行？** 📎 实测可以（FastAPI 会先转 dict，再交给 `response_model`），
但要保证会话还活着（`expire_on_commit=False` 或还没 commit）。

## 10.6 ⚠️ N+1 查询问题

> ⚠️ 下面的 `conv.messages` 是**关系模型的教学伪代码** —— 当前 `Conversation` 还没有 `messages` 关系，复制过去跑不起来。这段只用来解释「查询次数」。

```python
convs = await db.execute(select(Conversation))
for conv in convs.scalars():
    print(conv.messages)      # ❌ 每条会话都发一次查询 → 1 + N 次
```

| 方案 | 写法 |
|------|------|
| **预加载**（推荐） | `select(Conversation).options(selectinload(Conversation.messages))` |
| 显式 join | `select(...).join(...)` |
| 批量查 + 内存拼装 | 查所有 message，按 `conversation_id` 分组 |

> ⭐ **判断信号**：**循环里访问"关系属性"**（`conv.messages`）几乎总是 N+1。
> 100 条会话 → 101 次查询，接口从 10ms 变成 1s。
>
> ⚠️ **异步下更严重**：`AsyncSession` 里直接访问未加载的关系会触发隐式 IO。
> 📎 本机 SQLAlchemy 2.1.6 + `aiosqlite` 实测：**顶层 `StatementError`，`.orig` 是 `MissingGreenlet`** ——
> 所以异步环境必须用 `selectinload` 预加载，或显式执行可等待的查询。
>
> 🔗 这和 ML 里的"**特征工程要向量化，不要 for 循环**"是同一种思维：
> **把 N 次操作合成 1 次批量操作**。

## 10.7 迁移（了解，阶段 1 不急）

**问题**：`create_all` 只会在**表不存在时**建表，**不会修改已有表结构**。
加一个字段后，老数据库不会自动更新。

| 阶段 | 做法 |
|------|------|
| 学习 / 原型 | `create_all` 够用 |
| 有了真实数据 | **Alembic**（生成迁移脚本：`alembic revision --autogenerate`） |

> ⭐ **判断标准**：**"这个库里的数据丢了我会心痛吗？"**
> 会 → 上 Alembic；不会（学习阶段）→ 先用 `create_all`。

## 10.8 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 10 数据库）。

---

# Step 11 · 工程化：配置 / 日志 / 安全

## 定位

> 前三步让服务"能跑"，这一步让它"**能上线**"。
> ⚠️ 其中 **11.4 的 API Key 问题是 LLM 应用最高频的安全事故**。

## 11.1 配置：复用阶段 0 的 `pydantic-settings`

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    env: str = "local"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./app.db"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    max_context_messages: int = 20          # ⭐ LLM 应用特有：上下文窗口控制
    request_timeout: float = 60.0           # ⭐ LLM 请求要长超时
```

**从阶段 0 直接复用**，只需注意两个 LLM 应用的特性：

| 配置项 | 为什么需要 |
|--------|-----------|
| `max_context_messages` | 上下文不能无限增长（**token = 钱**，且会超模型窗口） |
| `request_timeout` | LLM 请求动辄几十秒，**默认 30s 会误杀** |

**用依赖注入暴露给路由**（便于测试覆盖）：

```python
def get_settings() -> Settings:
    return settings

SettingsDep = Annotated[Settings, Depends(get_settings)]
```

> ⭐ **为什么包一层 `get_settings()`**：测试里 `dependency_overrides[get_settings]` 就能换配置，
> 而不用改环境变量、不用 reload 模块。

## 11.2 日志

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app")


@app.get("/x")
async def x() -> dict[str, bool]:
    logger.info("handling request", extra={"path": "/x"})
    return {"ok": True}
```

| 原则 | 说明 |
|------|------|
| **不要用 `print`** | 没有级别、没有时间戳、无法过滤、无法输出到文件 |
| **日志要能关联请求** | ⭐ 配合 Step 7 的请求 ID（`X-Request-Id`） |
| **不要记录密钥** | ⚠️ 日志会被收集、被搜索、被分享 |
| 记录**耗时和 token 数** | LLM 应用必须盯成本 |
| 结构化（JSON） | 便于日志平台检索 |

> ⭐ **LLM 应用该记什么**：`request_id`、`model`、`prompt_tokens`、`completion_tokens`、
> `latency_ms`、`ttft_ms`、`是否有缓存命中`。
> **这些都是优化产品和核算成本的原料。**

## 11.3 ⚠️ 500 错误与日志的配合

```python
@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    request_id = str(uuid.uuid4())
    logger.exception("unhandled error request_id=%s", request_id)   # ⭐ 堆栈进日志
    return JSONResponse(                              # ⭐ 只给用户一个 ID
        status_code=500,
        content={"error": "internal_error", "request_id": request_id},
    )
```

| 对象 | 看到什么 |
|------|---------|
| 用户 | `{"error":"internal_error","request_id":"..."}` |
| 你 | 日志里有完整堆栈 + 同样的 `request_id` |

> ⭐ **这就是"既安全又可排查"** —— 两者都要，且不冲突。

## 11.4 ⚠️⚠️ API Key 绝不能放在前端

**这是 LLM 应用最常见、后果最严重的事故。**

```javascript
// ❌❌❌ 绝对不要这样做
const resp = await fetch("https://api.openai.com/v1/chat/completions", {
  headers: { "Authorization": "Bearer sk-xxxxxxxx" },   // Key 在浏览器里！
  ...
});
```

**为什么必然泄露**：

| 途径 | 说明 |
|------|------|
| 打开 F12 → Network | **明文可见**，无需任何技术 |
| 打包产物 | 前端代码/环境变量最终都会进 JS 文件 |
| 反混淆 | 就算 `atob` 一下，也只是"延迟 3 秒" |
| **后果** | 别人拿你的 Key 刷 API，**账单是你的**，且可能被**封号** |

> ⭐ **唯一正确架构**：**Key 只存在服务端，前端只跟你的后端说话。**

```mermaid
flowchart LR
    FE["前端（浏览器）"] -->|"1. 调用你的接口<br/>带的是【你的用户 token】"| BE["你的后端"]
    BE -->|"2. 用服务端环境变量里的 Key<br/>调用 LLM"| LLM["LLM API"]
    LLM -->|"3. 流式返回"| BE
    BE -->|"4. 原样流式转发（SSE）"| FE
```

**这个架构顺带还解决了三件事**：

| 收益 | 说明 |
|------|------|
| **鉴权** | 你能知道是谁在用（限流、计费、封禁） |
| **限流** | 防止有人把你的后端当免费 API 刷 |
| **可观测** | token 用量、成本、延迟都掌握在你手里 |
| **可换模型** | 前端不用改，后端换个 `model` 参数就行 |

## 11.5 鉴权与限流（最小可用版）

```python
async def get_current_user(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ")
    # 真实项目：验签 JWT 或查库
    user = await lookup_token(token)
    if user is None:
        raise HTTPException(401, detail="invalid token")
    return user


@app.post("/v1/chat/stream")
async def chat_stream(req: ChatRequest, user: CurrentUserDep, db: DbDep): ...
```

**限流**（LLM 应用必备，因为每次调用都花钱）：

| 层次 | 手段 |
|------|------|
| 按用户 | 每分钟 N 次（滑动窗口 / 令牌桶） |
| 全局 | 并发上限（`asyncio.Semaphore`） |
| 成本 | 按 token 累计配额（超出拒绝） |

> ⭐ **为什么 LLM 应用的限流比普通 Web 更紧急**：
> 普通接口被刷只是 CPU 占用；**LLM 接口被刷是真金白银的账单**。
> 一个没限流的公开 LLM 接口，可能一夜之间烧掉几百美元。

## 11.6 部署前的安全检查清单

| 检查项 | 正确做法 |
|--------|---------|
| API Key 在哪 | **只在服务端环境变量**，❌ 不在前端/代码/镜像里 |
| `.env` 进 Git 了吗 | 必须在 `.gitignore` 里 |
| CORS 范围 | 生产**只列白名单域名**，❌ 不用 `["*"]` |
| 500 响应 | **不回显堆栈**，只给 request_id |
| `/docs` 要不要公开 | 生产环境可能该关掉（`FastAPI(docs_url=None)`） |
| 日志里有密钥吗 | 检查是否把 `Authorization` 头打进去了 |
| 限流 | 至少有一个粗粒度上限 |
| 依赖漏洞 | 定期升级 `uv lock --upgrade` |

## 11.7 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 11 工程化）。

---

# Step 12 · 测试 FastAPI

## 定位

> 阶段 0 的结论在这里继续生效：**静态检查看形状，测试看行为**。
> FastAPI 有很好的测试工具，能把"启动服务再 curl"变成**毫秒级的自动化断言**。

## 12.1 `TestClient`：不启服务器的"假客户端"

```python
from fastapi.testclient import TestClient

from main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
```

**原理**：`TestClient` 内部用 `httpx` + **ASGI 传输层**，请求**直接喂给你的 ASGI 应用**，
不走网络、不占端口、不用等启动。

> 🧒 **类比**：不是"真的打电话给客服"，而是"**拿着电话对着空气说完，客服的声音直接从墙里传回来**"。
> 快、稳定、可断言。

## 12.2 ⚠️ `with TestClient(app)` 和直接 `TestClient(app)` 的**致命区别**

**实测结果**（带 lifespan 的应用）：

```text
[no with] /s = {'ready': None, 'token': None}      ← lifespan 没跑！
[no with] log = []
[with]    /s = {'ready': True, 'token': 'abc'}      ← lifespan 跑了
[with]    log inside = ['startup']
[with]    log after  = ['startup', 'shutdown']      ← 退出上下文时跑 shutdown
```

| 写法 | lifespan | 后果 |
|------|----------|------|
| `TestClient(app)` | ❌ **不执行** | 数据库没建表、连接池没初始化 → **测试里一堆莫名错误** |
| `with TestClient(app) as c:` | ✅ 执行 | 正确 |

> ⭐ **这是 FastAPI 测试第一大坑**：
> "我明明在 lifespan 里建了表，为什么测试说表不存在？"
> **因为没用 `with`。**
>
> ⭐ 顺带：`with` 上下文退出时**会执行 shutdown**，所以它同时也验证了"关闭逻辑不报错"。

**写成 fixture 最省事**：

```python
@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
    # 退出 with 时自动跑 shutdown
```

## 12.3 ⚠️ `TestClient` 的依赖警告（2026 实测）

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated;
install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient
```

**实测验证**：

| 环境 | 结果 |
|------|------|
| 只有 `httpx` | 21 个测试通过，但**带弃用警告** |
| `uv add --dev httpx2` 后 | **警告消失**，21 个测试仍全通过 |

> ⭐ **结论**：`httpx2`（实测装上的是 `httpx2==2.13.1`，附带 `httpcore2`、`truststore`）
> 是 Starlette 1.x 时代推荐的测试客户端依赖。
> **这不是你的代码有问题**，是生态在换代 —— 但警告会污染输出，建议直接装上。

## 12.4 异步测试：`httpx.ASGITransport`

`TestClient` 是**同步**的（内部起一个 portal 桥接）。要在**纯异步**测试里测，用这个：

```python
import httpx
import pytest


async def test_health_async() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
```

**实测通过**。

| | `TestClient` | `httpx.ASGITransport` |
|---|-------------|----------------------|
| 测试函数 | 同步 `def` | 异步 `async def` |
| 能用 `await` | ❌ | ✅ |
| 适合 | 大多数接口测试 | 需要 `await`（如直接调异步依赖） |
| lifespan | 靠 `with` 触发 | ⚠️ **需要自己用 `LifespanManager` 或手动初始化** |

> ⚠️ **注意最后一行**：`ASGITransport` **不触发 lifespan**。
> 所以要么用 lifespan 之外的 fixture 初始化数据库，要么用 `asgi-lifespan` 之类的工具。
> **这也是为什么大多数项目首选 `TestClient`** —— 它能一并测 lifespan。

## 12.5 测 SSE 流式响应

```python
def test_sse_stream(client: TestClient) -> None:
    with client.stream(
        "POST",
        "/v1/chat/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())          # ①

    assert 'data: {"delta": "你"}' in body
    assert body.endswith("data: [DONE]\n\n")
```

**实测通过**。

| # | 要点 |
|---|------|
| ① | 必须用 `client.stream(...)` + `iter_text()`/`iter_lines()`，**不能用 `r.text`**（后者会等整个响应结束） |

> ⭐ **测 SSE 的关键**：断言三件事 —— **状态码、`content-type`、帧格式**。
> 特别是**帧结尾的两个换行**：少了它前端不会触发事件，而这种 bug 在浏览器里表现得很诡异（"什么都没发生"）。

## 12.6 依赖覆盖：绕过认证和数据库

```python
def test_me_with_override(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    try:
        assert client.get("/me").json() == {"user": "test-user"}
    finally:
        app.dependency_overrides.clear()      # ⚠️ 必须清理
```

**更稳的写法（fixture 自动清理）**：

```python
@pytest.fixture
def override_deps() -> Iterator[None]:
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    yield
    app.dependency_overrides.clear()          # 无论测试是否失败都会执行
```

> ⚠️ **不清理的后果**："单独跑通过，一起跑失败" —— 上一个测试的假用户泄漏到了下一个测试。
> **这是测试污染最典型的形式。**

## 12.7 该测哪些接口行为（LLM 后端清单）

| 类别 | 具体断言 |
|------|---------|
| **参数校验** | 空 messages → 422；temperature=5 → 422；`loc` 指向正确字段 |
| **认证** | 无 token → 401；错 token → 401；对 token → 200 |
| **业务** | 会话创建 → 201；查不存在的会话 → 404；`response_model` 不含敏感字段 |
| **流式** | 200 + `text/event-stream`；最后一帧是 `[DONE]`；**流内错误以事件形式出现** |
| **依赖覆盖** | 用假 LLM 替代真实调用（**测试绝不能真调 LLM**） |
| **数据库** | 事务回滚验证（抛异常后数据没落库） |

> ⭐ **"测试绝不能真调 LLM"** 这件事在阶段 1 就要立规矩：
> 慢、贵、不确定、可能限流。**用 `dependency_overrides` 注入一个假 LLM**：
> ```python
> async def fake_llm_stream(req: ChatRequest) -> AsyncIterator[str]:
>     for ch in "你好":
>         yield ch
>
> app.dependency_overrides[get_llm_client] = lambda: FakeLLM(fake_llm_stream)
> ```
> 这和阶段 0 用 `MockTransport` 假 HTTP 是**同一个思路**。

## 12.8 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 12 测试 FastAPI）。

---

# Step 13 · 部署

## 定位

> ⚠️ **本机未安装 Docker，本 Step 未实机构建**，以"理解配置项与坑"为验收标准。

## 13.1 uvicorn 的生产参数

```powershell
# 开发
uv run uvicorn app.main:app --reload

# 生产
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

| 参数 | 说明 |
|------|------|
| `--reload` | ⚠️ **生产绝不能用**（监听文件、额外开销、不稳定） |
| `--workers N` | 多**进程**（不是线程）：绕开 GIL，用满多核 |
| ⚠️ 不要同时用 `--reload` 和 `--workers` | 会报错或行为异常 |
| `--proxy-headers` | 在反向代理后面时，正确解析真实客户端 IP |

**`--workers` 怎么定**：一般 **= CPU 核心数**（IO 密集可到 2×）。
再往上收益递减（内存线性增长，每个 worker 独立进程）。

> ⚠️ **多 worker 的两个后果**（LLM 应用必须知道）：
> | 后果 | 说明 |
> |------|------|
> | **内存状态不共享** | 进程内缓存的会话/计数**各自一份** → 不能用内存做限流/会话存储 |
> | 需要**外部存储** | 会话、限流计数放 Redis / 数据库 |
>
> ⭐ SSE 本身**不受多 worker 影响**：一条长连接始终落在**同一个 worker** 上。
> 但"在内存里记录用户正在生成"这类设计会失效。

## 13.2 ⚠️ 反向代理会让你的流式失效

**nginx 默认开启响应缓冲**：

```nginx
location /v1/chat/stream {
    proxy_pass http://backend;
    proxy_buffering off;                # ⭐ 关键：关掉缓冲
    proxy_cache off;
    proxy_read_timeout 300s;            # ⭐ LLM 长响应必须调大
    proxy_set_header X-Accel-Buffering no;   # 辅助：告诉上游别缓冲
    chunked_transfer_encoding on;
}
```

| 配置 | 不配的后果 |
|------|-----------|
| `proxy_buffering off` | 流式变成"等全部生成完一次性返回" |
| `proxy_read_timeout 300s` | **60 秒后连接被掐断**（长回答直接失败） |
| `proxy_cache off` | 缓存住一个用户的回答，可能给到别人 |

> ⭐ **这是"本地好好的，上线就不流了"的头号原因**。
> 排查顺序：**nginx 缓冲 → 中间件（Step 7.3）→ gzip 压缩 → CDN**。

## 13.3 Dockerfile（沿用阶段 0 的模式）

```dockerfile
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# 依赖层在前（改代码不重装依赖）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 代码层在后
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

# ⚠️ 用 exec 形式（JSON 数组），进程才能收到 SIGTERM
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**LLM 应用特有的注意点**：

| 点 | 说明 |
|----|------|
| ⚠️ **绝不要 `COPY .env`** | Key 会进镜像层（历史里也删不掉） |
| 运行时注入配置 | `docker run -e LLM_API_KEY=...` 或用 secrets |
| 基础镜像要固定版本 | `python:3.12-slim`，不用 `latest` |
| `HEALTHCHECK` | 让编排系统知道服务是否活着 |

## 13.4 健康检查该检查什么

```python
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

| 层次 | 检查内容 | 用途 |
|------|---------|------|
| **liveness** | 进程还在响应吗 | 挂了就重启 |
| **readiness** | 依赖都就绪了吗（数据库/模型加载完） | 没就绪就别接流量 |
| 深度检查 | 上游 LLM 通不通 | 告警用，⚠️ **不宜放进 liveness**（上游抖动会导致你被反复重启） |

> ⚠️ **`/health` 里别做重活**：有人把它写成"查数据库 + 调上游"，
> 结果健康检查自己把服务拖垮，或者上游一抖动**全集群被重启**。

## 13.5 上线前的最后检查

```mermaid
flowchart LR
    A["1 环境变量注入<br/>（Key 不在镜像里）"] --> B["2 反向代理<br/>proxy_buffering off"]
    B --> C["3 超时配置<br/>read_timeout 300s"]
    C --> D["4 限流<br/>按用户 + 全局"]
    D --> E["5 日志<br/>token/耗时/request_id"]
    E --> F["6 健康检查<br/>liveness ≠ deep check"]
```

## 13.6 自检

> 本节自检题与简要答案已移入 [自检题清单.md](自检题清单.md)（阶段 1 · Step 13 部署）。

---

# 回顾 · 聊天后端设计蓝图 🎉

把 13 步拼起来，`projects/01-fastapi-chat/` 的目标结构：

```text
projects/01-fastapi-chat/
├── pyproject.toml
├── uv.lock
├── .env.example                  # 配置模板（LLM_API_KEY 等）
├── Dockerfile                    # Step 13
├── src/app/
│   ├── main.py                   # FastAPI 实例 + lifespan + 中间件注册
│   ├── config.py                 # Step 11.1（复用阶段 0）
│   ├── schemas.py                # Step 3/4：请求响应契约
│   ├── deps.py                   # Step 5：get_db / get_current_user / get_settings
│   ├── errors.py                 # Step 6：自定义异常 + 处理器
│   ├── db.py                     # Step 10：engine / SessionMaker / models
│   ├── llm.py                    # 阶段 2 填：LLM 客户端封装
│   └── routers/
│       ├── health.py             # §2
│       ├── chat.py               # §3/§9  ← 【核心】含 SSE 流式
│       └── conversations.py      # §10
└── tests/
    ├── conftest.py               # client fixture（with TestClient）
    ├── test_health.py
    ├── test_chat_contract.py     # 校验失败 / 401 / response_model 过滤
    └── test_chat_stream.py       # SSE 帧格式 + [DONE]
```

**接口设计（先定契约再写代码）**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/v1/chat` | 非流式对话（返回完整回答） |
| `POST` | `/v1/chat/stream` | **SSE 流式对话** ⭐ |
| `POST` | `/v1/conversations` | 建会话 |
| `GET` | `/v1/conversations` | 列会话 |
| `GET` | `/v1/conversations/{id}` | 查会话详情（含历史消息） |
| `DELETE` | `/v1/conversations/{id}` | 删会话 |

**SSE 帧协议（自己定的，写进文档）**：

```text
data: {"type":"meta","conversation_id":1,"model":"qwen-7b"}

data: {"type":"delta","text":"你"}

data: {"type":"delta","text":"好"}

data: {"type":"error","message":"upstream timeout"}

data: {"type":"done","usage":{"prompt_tokens":12,"completion_tokens":88}}

```

> ⭐ **为什么先发 `meta`**：会话 ID 和模型名要在**第一帧**就给前端；
> 而且**第一帧之前的所有准备工作都还能返回 4xx**（趁还没发 200，错误还能用状态码表达）。

**13 步串成一句话**：

> 用 **HTTP/ASGI（1）** 理解请求怎么进来；**路由（2）+ 三段参数（3）+ pydantic 契约（4）** 定义接口；
> 用 **`Depends`（5）** 把认证和数据库变成声明；用 **异常处理器（6）** 统一错误形状；
> **中间件（7）** 加横切逻辑但**别碰响应体**；**异步（8）** 守住事件循环；
> 用 **SSE（9）** 把 TTFT 压到秒级；用 **数据库（10）** 存历史；
> **配置/日志/安全（11）** 让 Key 留在服务端；**测试（12）** 锁住契约；
> **容器（13）** 连同环境一起交付。

---

# 难点拓展 · 深入理解关键问题

## 拓展 1 · ASGI 协议到底长什么样（实测）

**不依赖任何框架的裸 ASGI 应用**：

```python
async def raw_app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            msg = await receive()
            if msg["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif msg["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
        return

    assert scope["type"] == "http"
    msg = await receive()                       # 读请求体

    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"text/event-stream")]})
    for i in range(2):
        await send({"type": "http.response.body", "body": f"data: {i}\n\n".encode(),
                    "more_body": True})         # ⭐ 多次 send → 流式
    await send({"type": "http.response.body", "body": b"data: [DONE]\n\n",
                "more_body": False})            # 最后一帧
```

**实测输出**：

```text
[lifespan] startup 收到
scope 里的键 = ['client', 'extensions', 'headers', 'http_version', 'method',
                'path', 'query_string', 'raw_path', 'root_path', 'scheme',
                'server', 'state', 'type']
method = GET | path = /x
receive 第一帧 = {'type': 'http.request'} | body = b''
status = 200 | ct = text/event-stream
body = 'data: 0\n\ndata: 1\n\ndata: [DONE]\n\n'
[lifespan] shutdown 收到
```

**三个协议事实**：

| 事实 | 含义 |
|------|------|
| `scope` 是**一次连接的元信息字典** | 里面有 `method`/`path`/`headers`/**`state`** |
| `receive()` 可以调用**多次** | 用 `more_body` 表示"还有"（流式上传） |
| `send()` 可以调用**多次** | ⭐ `http.response.start` **只能一次**，然后可多次 `http.response.body` + `more_body: True` |

> ⭐ **由此解开了两个之前的疑惑**：
> 1. **`with TestClient(app)` 为什么会触发 lifespan？**
>    因为客户端发了一个 `type="lifespan"` 的 scope，服务器回 `lifespan.startup.complete`。
>    不用 `with` 就没有这个握手 → lifespan 不执行。（Step 12.2 实测验证）
> 2. **`scope` 里有 `state` 键** —— 这就是 lifespan `yield` 的 dict **并入 `request.state`** 的通道（Step 6.4）。

**这就是为什么 WSGI 做流式很别扭**：WSGI 的 `start_response()` 只能调用一次，且是"先声明全部响应头"。
ASGI 把"发送"变成了**可多次调用的协程**，天生支持流。

---

## 拓展 2 · 为什么 FastAPI 快

**"快"要分成两件事看**：

| 维度 | 说明 |
|------|------|
| **开发速度快** | 类型注解 → 自动校验 + 自动文档 + 自动补全，代码量少 |
| **运行速度快** | Starlette（轻量 ASGI）+ pydantic v2（Rust 校验） |

**具体来源**：

| 来源 | 解释 |
|------|------|
| **ASGI + 异步** | IO 等待时不占线程（Step 1.4）—— 这是**并发吞吐**的主要来源 |
| **Starlette 极薄** | 没有复杂中间件栈和 ORM 隐式查询；路由匹配是简单正则表 |
| **pydantic v2 用 Rust 校验** | 校验不再走 Python（阶段 0 拓展 7） |
| **schema 预编译** | 模型定义时就把校验逻辑编译好，请求时只执行 |
| **按需解析** | 只解析**函数签名里声明了**的字段，不解析整个 body 再挑 |

> ⚠️ **不要盲信 benchmark**：微基准（hello world）里框架差异很大，
> 但真实 LLM 应用里 **99% 的时间花在等模型**。
> **对你的项目而言，"FastAPI 快"的价值主要来自异步模型，而不是框架本身的开销。**

---

## 拓展 3 · 依赖注入的解析算法

FastAPI 处理一个请求时，怎么"把依赖填好"？

```mermaid
flowchart TB
    A["收集路由签名上的所有 Depends"] --> B["构建依赖图"]
    B --> C["拓扑排序：先解析没有依赖的"]
    C --> D["逐个解析，结果填入缓存 dict[key=依赖函数] "]
    D --> E{"任一依赖抛<br/>HTTPException？"}
    E -->|是| F["短路：路由不执行<br/>直接返回错误响应"]
    E -->|否| G["调用路由函数<br/>参数按签名注入"]
```

**三个关键机制**：

| 机制 | 为什么 |
|------|-------|
| **缓存 key 是"依赖可调用对象本身"** | 所以同一个函数被请求多次只执行一次（Step 5.5 实测 `call_count == 1`） |
| 缓存作用域是**单次请求** | 请求结束即销毁 → 不会跨请求串数据 |
| **短路** | 依赖里 `raise HTTPException` → 路由**根本不被调用** → 认证失败不会误执行业务 |

> ⚠️ **缓存 key 是函数对象**，这带来一个坑：
> **两个不同的函数做同一件事，会被当成两个依赖各执行一次**。
> 想复用就抽出**同一个**可调用对象（或把 `use_cache` 设为默认值 `True`）。

**为什么"先解析依赖，再解析参数"**：因为参数可能**依赖**依赖的结果。
这就是一个**有向无环图（DAG）的拓扑排序**问题 —— **和阶段 0 拓展 1 的依赖解析、拓展 3 的 Git 提交图，是同一类结构**。

---

## 拓展 4 · 类型注解是怎么变成 API 文档的

**完整链路**：

```mermaid
flowchart LR
    A["Python 类型注解<br/>+ Annotated 元数据"] --> B["pydantic core schema"]
    B --> C["JSON Schema"]
    C --> D["OpenAPI 3.1 文档"]
    D --> E["/openapi.json<br/>/docs (Swagger UI)"]
```

**实测证据**（`app.openapi()` 的真实输出）：

```json
// Query(ge=1, le=100) 变成了什么
{
  "name": "limit", "in": "query", "required": false,
  "schema": {"type": "integer", "maximum": 100, "minimum": 1, "default": 10, "title": "Limit"}
}

// 嵌套模型 + min_length 变成了什么
{
  "properties": {
    "messages": {"items": {"$ref": "#/components/schemas/Message"},
                 "type": "array", "minItems": 1, "title": "Messages"},
    "stream": {"type": "boolean", "title": "Stream", "default": false}
  },
  "type": "object",
  "required": ["messages"],
  "title": "ChatRequest"
}
```

| 你写的 | 生成的文档 |
|--------|-----------|
| `Annotated[int, Query(ge=1, le=100)]` | `{"type":"integer","minimum":1,"maximum":100}` |
| `Field(min_length=1)` on list | `"minItems": 1` |
| 无默认值 | 出现在 `required` 数组里 |
| 嵌套模型 | `$ref` 引用 + 独立的 component |
| ⭐ `Field(description=...)` | schema 里的 `description` 字段（**文档正文**） |
| ⭐ `model_config` 的 `examples` | 文档里的示例 |

**实测的 OpenAPI 版本**：`"openapi": "3.1.0"`（3.1 与 JSON Schema 完全对齐）。

> ⭐ **这解释了一个重要实践**：
> **写 pydantic 模型时顺手写 `description` 和 `examples`，等于免费写了 API 文档，而且永远不会过期。**
> 反过来说：**如果你的 `/docs` 页面空空如也，说明你的模型该补注释了。**

---

## 拓展 5 · SSE 协议的额外能力（和它的局限）

**完整字段**：

| 字段 | 作用 |
|------|------|
| `data:` | 数据（必须） |
| `event:` | 事件类型名（前端 `addEventListener("event", ...)` 监听） |
| `id:` | 事件 ID（⭐ 用于断线续传） |
| `retry:` | 建议客户端重连间隔（毫秒） |
| `:` 开头 | 注释（**常用于心跳保活**） |

**心跳为什么需要**：中间设备（代理/负载均衡）会把**长时间无数据的连接**判为僵死并掐掉。
定期发 `: keep-alive\n\n` 就能续命。

```python
# 心跳示例（业务空闲超过 N 秒就发注释帧）
yield ": ping\n\n"
```

**断线续传机制**：浏览器自动重连时会带上 `Last-Event-ID` 头（= 最后收到的 `id:`）。
服务端可以据此**从断点继续**：

```python
last_id = request.headers.get("Last-Event-ID")
```

> ⚠️ **局限（决定它不能替代 WebSocket 的地方）**：
> | 局限 | 说明 |
> |------|------|
> | **单向** | 只能服务器→客户端 |
> | 基于 HTTP/1.1 时**有连接数限制** | 浏览器对同一域名通常限 6 个并发连接 |
> | `EventSource` 不能带自定义头/不能 POST | ⭐ 所以 LLM 场景用 `fetch` 手动解析 |
> | 文本 only | 二进制要自己 base64 |
>
> ⭐ 但**对"LLM 流式输出"这个场景，以上局限一个都不重要** ——
> 因为是单向的、文本的、一条连接就够。**这就是选 SSE 的完整理由。**

---

## 拓展 6 · 连接池与背压

**连接池**：数据库/HTTP 连接建立很贵（TCP + TLS + 认证），所以**复用**。

```python
engine = create_async_engine(url, pool_size=5, max_overflow=10, pool_timeout=30)
```

| 参数 | 含义 |
|------|------|
| `pool_size` | 常驻连接数 |
| `max_overflow` | 临时可超出的数量（总上限 = 20） |
| `pool_timeout` | 等不到连接时，等多久后报错 |

> ⚠️ **池太小**：请求排队等待 → 延迟飙升。
> ⚠️ **池太大**：数据库连接数爆掉（**数据库有上限**，多了直接拒连）。
>
> ⭐ **一个必算的数**：
> ```text
> 总连接数 = pool_size + max_overflow (每 worker) × worker 数
> ```
> 4 个 worker × 20 = **80 个连接**。如果你的 PostgreSQL `max_connections=100`，
> 再加上别的服务，**很快就会打满**。**这是上线后最容易踩的容量坑。**

**背压（backpressure）**：当下游处理不过来时，让上游"慢下来"而不是无限堆积。

| 层面 | 手段 |
|------|------|
| 应用层 | `asyncio.Semaphore(n)` 限制并发数 |
| 连接池 | `pool_size` 本身就是背压 |
| 队列 | 任务队列（超出直接拒绝或排队） |
| 客户端 | 429 + `Retry-After` |

> ⭐ **LLM 应用的背压尤其重要**：上游 API 有**速率限制（RPM/TPM）**。
> 无限并发只会换来一堆 429 和重试风暴。**主动用 Semaphore 卡住并发**是标准做法。

---

## 拓展 7 · 为什么校验失败用 422 而不是 400

| 码 | 语义（RFC 9110） | 例子 |
|----|-----------------|------|
| **400** Bad Request | 服务器**无法理解**这个请求（语法/结构问题） | JSON 语法错误、请求行不合法 |
| **422** Unprocessable Content | 语法**正确**，但**语义上处理不了** | 字段类型不对、值越界、缺必填 |

**FastAPI 的选择**：pydantic 校验失败 → **422**。

```json
{"detail": [{"type": "too_short", "loc": ["body", "messages"], "msg": "...", "input": []}]}
```

| 理由 | 说明 |
|------|------|
| **JSON 解析成功** → 不能算 400 | 请求**被理解了**，只是内容不合法 |
| 前端需要**区分** | 400 = "你代码写错了"（不该给用户看）；422 = "用户填错了"（该给用户看） |
| 422 语义更精确 | 历史上来自 WebDAV，现在被广泛采用 |

> ⭐ **实践建议**：面向 C 端产品时，**通常会把 422 改写成 400 + 中文错误信息**，
> 因为很多前端框架/网关对 422 的处理不如 400 通用。**知道原理，才好做取舍。**

---

## 拓展 8 · 幂等性与重试

**问题场景**：用户点了"发送"，网络超时，前端自动重试 → **产生两条会话 / 两次计费**。

| 概念 | 说明 |
|------|------|
| 幂等 | 执行 1 次和执行 N 次，**结果相同** |
| 幂等键 | 客户端生成一个唯一 ID（`Idempotency-Key` 头），服务端记住"这个键处理过" |

```python
@app.post("/v1/conversations")
async def create_conversation(
    payload: ConversationIn,
    db: DbDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if idempotency_key:
        existing = await find_by_idempotency_key(db, idempotency_key)
        if existing:
            return existing              # ⭐ 直接返回上次的结果
    ...
```

> ⭐ **对 LLM 应用格外重要**：每次重试都**花真钱**。
> 一个"网络抖动导致的自动重试"可能让你为同一个问题付两次费。
> **前端生成本次请求的 UUID，后端用它去重。**

---

## 拓展 9 · LLM 应用的并发模型

**先算一笔账**：

```text
假设：
  单个请求平均耗时 T = 10 秒（含等模型）
  目标 QPS = 10（每秒 10 个新请求）

需要同时"在飞"的请求数 ≈ QPS × T = 10 × 10 = 100 个并发协程
```

**100 个并发协程对 asyncio 完全没压力**（内存开销约几百 KB 级别），
**但下面三个因素会立刻成为真正的瓶颈**：

| 瓶颈 | 限制 | 对策 |
|------|------|------|
| **上游 API 限流** | 如 60 RPM / 100K TPM | `asyncio.Semaphore` 主动卡并发 + 退避重试 |
| **数据库连接池** | 总连接数有限 | 调 `pool_size`、加 worker 要重算 |
| **成本** | 每次调用都花钱 | 按用户配额、缓存、用小模型分流 |

**推荐的分层限制**：

```python
llm_semaphore = asyncio.Semaphore(20)          # 进程内并发上限


async def guarded_stream(req: ChatRequest) -> AsyncIterator[str]:
    async with llm_semaphore:                   # 拿不到"令牌"就在这里等（形成背压）
        async for chunk in llm.stream(req):
            yield chunk
```

> ⚠️ **注意 Semaphore 是进程内的**：`--workers 4` 就是 4 份独立计数，实际并发 = 4 × 20 = 80。
> 要全局精确控制，必须用 **Redis 之类的共享计数器**。
>
> ⭐ **另一个重要设计**：**区分"快路径"和"慢路径"**。
> 简单问题走小模型（快、便宜），复杂问题走大模型 —— 这能把平均成本和延迟都压下来。

---

## 拓展 10 · 快问快答（实测数字）

| 问题 | 实测答案 |
|------|---------|
| 实测的 FastAPI / Starlette / uvicorn 版本？ | **0.142.2 / 1.7.0 / 0.54.0** |
| OpenAPI 版本？ | **3.1.0** |
| 校验失败的默认状态码？ | **422**，`detail` 是**列表**，`loc` 是嵌套路径 |
| `Query(ge=1, le=100)` 生成的 schema？ | `{"type":"integer","minimum":1,"maximum":100}` |
| 同一次请求里同一依赖被请求两次，执行几次？ | **1 次**（缓存） |
| `def` 路线的线程池上限？ | **40**（anyio 默认） |
| 不用 `with` 的 `TestClient` 会跑 lifespan 吗？ | **不会**（实测 `ready=None`） |
| 流式响应的 content-type？ | `text/event-stream` |
| 实测帧序列？ | `data: {...}\n\n` × N + `data: [DONE]\n\n` |
| `on_event` 现在的状态？ | **已废弃**，发 `DeprecationWarning`，改用 `lifespan` |
| `TestClient` 的弃用警告？ | 用 `httpx` 已弃用 → 装 **`httpx2`** 后警告消失 |
| `uv add sqlalchemy` 够吗？ | **不够**，异步必须 `sqlalchemy[asyncio]`（补 `greenlet`） |
| 异步测试用 TestClient 还是 ASGITransport？ | 前者能测 lifespan，后者能在 `async def` 里用 |

---

# 附录 A · 代码片段速查（可直接抄）

## 应用骨架

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()                    # 启动：建表 / 建池 / 预热模型
    yield
    await engine.dispose()             # 关闭：释放资源

app = FastAPI(title="chat-backend", version="0.1.0", lifespan=lifespan)
```

## 三段参数

```python
from typing import Annotated, Literal
from fastapi import Path, Query, Header
from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, description="消息正文")


class ChatRequest(BaseModel):
    messages: list[MessageIn] = Field(min_length=1, description="至少一条消息")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False


@app.post("/v1/items/{item_id}", status_code=201)
async def handler(
    item_id: Annotated[int, Path(ge=1)],                                  # 路径
    limit: Annotated[int, Query(ge=1, le=100)] = 10,                      # 查询
    q: Annotated[str | None, Query(max_length=50)] = None,                # 可选查询
    req: ChatRequest = ...,                                               # 请求体
    x_token: Annotated[str | None, Header(alias="X-Token")] = None,       # 请求头
) -> dict[str, object]: ...
```

## 依赖注入

```python
# 函数依赖
async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing bearer token")
    return "user-001"

CurrentUserDep = Annotated[str, Depends(get_current_user)]


# yield 依赖（资源管理）
async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionMaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

DbDep = Annotated[AsyncSession, Depends(get_db)]


# 类依赖（一组参数打包）
class PageDep:
    def __init__(self, limit: Annotated[int, Query(ge=1, le=100)] = 10) -> None:
        self.limit = limit

PageDepAnnotated = Annotated[PageDep, Depends()]
```

## 错误处理

```python
class AppError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": exc.code})


raise HTTPException(status_code=404, detail="not found")
```

## 中间件

```python
import uuid

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    response = await call_next(request)          # ⭐ 必须调用
    response.headers["X-Request-Id"] = rid
    return response                              # ⭐ 必须 return
```

## CORS

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],     # ⚠️ 生产写白名单，别用 ["*"] + credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## SSE 流式（核心片段）

```python
import json
from collections.abc import AsyncIterator
from fastapi import Request
from fastapi.responses import StreamingResponse


def sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/v1/chat/stream")
async def chat_stream(req: ChatRequest, request: Request) -> StreamingResponse:
    async def event_source() -> AsyncIterator[str]:
        try:
            yield sse({"type": "meta", "model": "qwen-7b"})
            async for chunk in llm.stream(req):            # 上游也是流
                if await request.is_disconnected():        # 客户端断开 → 停
                    break
                yield sse({"type": "delta", "text": chunk})
        except Exception as exc:
            yield sse({"type": "error", "message": str(exc)})   # ⚠️ 无法再改状态码
        finally:
            yield sse({"type": "done"})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

## 数据库

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))


engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=10)
SessionMaker = async_sessionmaker(engine, expire_on_commit=False)

# CRUD
db.add(obj); await db.flush(); await db.refresh(obj)
result = await db.execute(select(Conversation).order_by(Conversation.id))
rows = list(result.scalars().all())
obj = await db.get(Conversation, pk)
```

## 测试

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:          # ⭐ with 才会跑 lifespan
        yield c


def test_validation_error(client: TestClient) -> None:
    r = client.post("/v1/chat", json={"messages": []})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "messages"]


def test_sse(client: TestClient) -> None:
    with client.stream("POST", "/v1/chat/stream",
                       json={"messages": [{"role": "user", "content": "hi"}]}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    assert body.endswith("data: " + '{"type": "done"}' + "\n\n")


def test_override(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    try:
        ...
    finally:
        app.dependency_overrides.clear()      # ⚠️ 必须清理
```

## 启动

```powershell
uv run uvicorn app.main:app --reload                 # 开发
uv run uvicorn app.main:app --workers 4              # 生产
uv add fastapi uvicorn "sqlalchemy[asyncio]" aiosqlite httpx
uv add --dev pytest pytest-asyncio httpx2
```

---

# 附录 B · 数学背景 → 后端知识对照

| 数学武器 | 对应后端知识 | 学习成本 |
|---------|------------|---------|
| 映射 / 函数 | 路由：`(method, path) → handler` | ⭐ |
| 集合与约束 | pydantic 校验规则、JSON Schema | ⭐ |
| 图论（DAG）+ 拓扑排序 | **依赖注入解析顺序**、依赖图 | ⭐⭐ |
| 状态机 | 请求生命周期、连接/Session 状态 | ⭐⭐ |
| 排队论（直觉） | 并发上限、连接池、背压、限流 | ⭐⭐⭐ |
| 概率与尾延迟 | P95/P99 延迟比平均值重要得多 | ⭐⭐ |
| 流水线/并行 | TTFT vs 总耗时、`gather` vs 串行 | ⭐⭐ |
| 编码/序列化 | JSON、UTF-8、SSE 帧格式 | ⭐ |
| 语义与公理 | HTTP 方法语义、状态码语义、幂等性 | ⭐⭐ |
| **要新建的** | **工程直觉：分层、错误处理、安全边界** | ⭐⭐⭐⭐ |

> ⭐ **一个值得注意的转译**：数学里追求"**最优解**"；
> 工程里追求"**在约束下可交付**"（时间、成本、可维护性）。
> 比如"为什么用 422 而不是 400"，答案不是"哪个更对"，而是"**哪个对使用者更清楚**"。

---

# 附录 C · 术语速查（人话版）

| 术语 | 人话 |
|------|------|
| 路由 route | "什么样的请求交给哪个函数"的映射表 |
| 路径参数 | 写在 URL 路径里的变量（`/items/{id}`） |
| 查询参数 | URL 里 `?` 后面的键值对 |
| 请求体 body | 请求里携带的数据（通常是 JSON） |
| 状态码 | 三位数字，告诉客户端"发生了什么" |
| 401 / 403 | 没登录 / 登录了但没权限 |
| 422 | 格式对但内容不合法（FastAPI 校验失败） |
| 幂等 | 执行 1 次和 N 次结果一样 |
| ASGI | 异步服务器网关接口（支持流式/WebSocket） |
| WSGI | 同步版本（一个请求占一个线程） |
| uvicorn | ASGI 服务器（跑 FastAPI 的那个进程） |
| worker | 服务进程（多 worker = 多进程，用满多核） |
| `Depends` | 依赖注入：把"需要什么"写在签名上 |
| 依赖覆盖 | 测试里把真依赖换成假的 |
| 依赖缓存 | 同一次请求里同一依赖只算一次 |
| `lifespan` | 应用的启动/关闭钩子（加载模型、建连接池） |
| `request.state` | 一次请求内的临时存储（lifespan 的 state 会并入这里） |
| 中间件 | 夹在请求和路由之间的通用处理（日志、CORS） |
| 洋葱模型 | 中间件像洋葱：请求从外往里、响应从里往外 |
| CORS | 浏览器的跨域限制（服务器要显式允许） |
| 预检请求 | 浏览器先发 `OPTIONS` 问"我能发吗" |
| 事件循环 | 单线程里的任务调度员 |
| 阻塞事件循环 | 在 async 里干同步的活 → 服务卡死 |
| 线程池 | 存放同步阻塞任务的地方（anyio 默认 40） |
| 背压 | 下游处理不过来时，让上游慢下来 |
| 连接池 | 复用数据库/HTTP 连接，避免反复握手 |
| N+1 查询 | 循环里访问关系属性 → 1+N 次查询 |
| 迁移 migration | 数据库结构变更脚本（Alembic） |
| SSE | 服务器单向持续推送（LLM 流式输出的标准做法） |
| TTFT | 首字延迟，**用户感知的速度** |
| `StreamingResponse` | FastAPI 里做流式响应的类 |
| WebSocket | 双向长连接（SSE 用不上的场景才需要） |
| `TestClient` | 不启服务器的假客户端（内部走 ASGI） |
| `ASGITransport` | httpx 的传输层，用于异步测试 |
| 幂等键 | 客户端生成的请求唯一 ID，用于去重 |
| 结构化日志 | 机器可检索的日志（JSON），而非自由文本 |

---

# 附录 D · 常见坑总表

| 阶段 | 坑 | 后果 |
|------|----|------|
| 路由 | `/users/{id}` 写在 `/users/me` 前面 | `/users/me` 被当成 id |
| 参数 | 忘记给 `request` 加 `Request` 注解 | 被当成**查询参数**，报 422"缺少 request" |
| 参数 | `bool` 查询参数传空字符串 | 422（空串 ≠ 布尔） |
| 响应 | 不写 `response_model` | **内部字段（密码哈希等）泄露** |
| 响应 | 204 还返回响应体 | 部分客户端报错 |
| 依赖 | 同一次请求里两个函数做同一件事 | 各执行一次（缓存 key 是函数对象） |
| 依赖 | `dependency_overrides` 用完不 `clear()` | 测试间污染，"单跑过、一起跑挂" |
| 依赖 | `yield` 之后 `return` | 返回值无效（容易以为是 bug） |
| 数据库 | `yield` 依赖的 `except` 里忘了 `raise` | **吞掉异常，客户端收到 200 但数据没存** |
| 数据库 | 不设 `expire_on_commit=False` | commit 后访问属性触发隐式 IO → 报错 |
| 数据库 | 循环里访问关系属性 | **N+1 查询**，接口从 ms 变 s |
| 数据库 | `uv add sqlalchemy` 而非 `sqlalchemy[asyncio]` | ImportError（缺 greenlet） |
| 数据库 | `create_all` 当迁移用 | 加字段后老库不更新 |
| 生命周期 | 模块顶层加载模型 | 测试/热重载重复加载，启动巨慢 |
| 生命周期 | 用 `on_event` | 已废弃（DeprecationWarning） |
| 生命周期 | 模块里出现**两个** `app = FastAPI(...)` | 后一个覆盖前一个；`register_exception_handlers` 注册在旧对象上 → 业务异常全变 500 |
| 生命周期 | `app.state, client = x`（**逗号**） | 是解包赋值：`TypeError` 起不来；右边可迭代时更阴 —— 整个 `state` 被静默替换 |
| 错误处理 | `return HTTPException(...)` 而非 `raise` | 有返回注解 → 500；**没注解 → 200 + `{"status_code":404,...}`（谎报成功）** |
| 错误处理 | 把上游的 `401/503` 原样透传给客户端 | 客户端误以为"我要登录"，做出无效动作；应统一译成 **502** |
| 错误处理 | `except Exception` 统一转 502 | 自家 bug 被伪装成"上游故障"：监控分不清、排查跑偏 |
| 错误处理 | `except` 里 `raise` 不写 `from` | traceback 变成"处理过程中又出错"，像翻译代码崩了（ruff `B904` 会拦） |
| 错误处理 | 用 `Literal[...]` 当路径参数代替手写判断 | 不存在资源返回 **422** 而非 404，且报错里**列出全部合法值** |
| 错误处理 | 500 处理器里做业务逻辑 | 它自己一抛，客户端拿到**空 body 的 500**（没有更外层的网） |
| 日志 | 以为 `logger.info` 会输出 | 默认 root 级别 `WARNING` → **静默丢弃**；错误日志也只有 stderr，无格式、不落盘 |
| 中间件 | 中间件里读取整个响应体 | ⚠️ **SSE 流式失效**（被缓冲成一次返回） |
| 中间件 | 忘了 `await call_next(request)` | 请求卡住 |
| 中间件 | 注册顺序理解反了 | **后注册的在最外层**（2026-10-19 实测订正；原以为"先注册的在最外层"） |
| 中间件 | `finally` 里直接访问 `response` | 里层抛异常时它从未赋值 → `UnboundLocalError` 盖掉真异常；先 `response: Response \| None = None` |
| 中间件 | 在中间件里 `await call_next` 之后读 `response.body` | 读一次就把 `_StreamingResponse` 抽干 → **SSE 退化成一次性返回** |
| CORS | `allow_origins=["*"]` + `allow_credentials=True` | 浏览器**直接拒绝** |
| CORS | 线上忘加生产域名 | 本地正常、线上跨域失败 |
| CORS | 用 curl 测通就以为浏览器能通 | CORS 是浏览器限制，curl 不检查 |
| 异步 | `async def` 里调同步阻塞库 | **整个服务卡死** |
| 异步 | `for` 循环里逐个 `await` | 串行，100 次调用 = 100 倍耗时 |
| 异步 | 无上限 `gather` 打上游 | 429 限流 + 重试风暴 |
| SSE | 帧结尾只写一个 `\n` | 前端**不触发事件**（"什么都没发生"） |
| SSE | 流开始后想返回 500 | **做不到**，状态码已发出 |
| SSE | 不处理客户端断开 | 白烧上游 token（**真金白银**） |
| SSE | 不设 `X-Accel-Buffering: no` | 经 nginx 后流式变一次性 |
| SSE | nginx `proxy_read_timeout` 太短 | 长回答被中途掐断 |
| SSE | 用 `EventSource` 想带 Authorization | 做不到（`EventSource` 不支持） |
| 测试 | `TestClient(app)` 不用 `with` | **lifespan 不执行**，表不存在 |
| 测试 | 用 `r.text` 测流式 | 会等整个响应结束（失去意义） |
| 测试 | 测试里真调 LLM | 慢、贵、不确定 |
| 安全 | 前端直连 LLM API | ⚠️⚠️ **Key 必泄露，账单是你的** |
| 安全 | 500 回显堆栈 | 泄露路径/版本/内部结构 |
| 安全 | 日志里打 Authorization 头 | 密钥进日志系统 |
| 安全 | 镜像里 `COPY .env` | 密钥进镜像层（删不掉） |
| 安全 | 无限流 | 公开接口被人刷爆账单 |
| 部署 | `--reload` 上生产 | 不稳定 + 额外开销 |
| 部署 | 多 worker 却用内存存会话/限流 | 各 worker 各一份，行为不一致 |
| 部署 | 连接池总量 × worker 数 > 数据库上限 | 数据库拒连 |

---

# 附录 E · 面试高频问题速查

> 每题答案都在对应 Step 里；**能不看笔记口头讲清 30 题以上**，说明这套体系已经掌握。

## 一、HTTP 与架构

1. HTTP 是无状态的，那登录状态怎么维持？
2. 401 和 403 的区别？
3. 幂等性是什么？为什么支付接口必须有？
4. WSGI 和 ASGI 的区别？为什么 LLM 应用选 FastAPI？
5. ASGI 的 `send` 能调用多次，这件事解锁了什么能力？
6. 为什么校验失败用 422 而不是 400？

## 二、参数与契约

7. FastAPI 怎么判断一个参数来自路径、查询串还是请求体？
8. `GET /items/abc` 返回什么？为什么不是 500？
9. `Annotated[int, Query(ge=1)]` 比 `Query(default=1, ge=1)` 好在哪？
10. **不写 `response_model` 有什么安全风险？**
11. 422 响应体的 `loc` 字段有什么用？
12. 你会给"用户"设计几个 pydantic 模型？为什么？

## 三、依赖注入（高频）

13. `Depends` 相比"函数里自己 new"的收益有哪四条？
14. `yield` 依赖的 `yield` 之后什么时候执行？抛异常时呢？
15. 同一次请求里请求同一依赖两次，执行几次？为什么？
16. 依赖注入的解析顺序是什么问题？（提示：图论）
17. 依赖里 `raise HTTPException` 会发生什么？为什么这个设计重要？
18. `dependency_overrides` 用完后必须做什么？

## 四、异步与并发（高频）

19. `async def` 和 `def` 路由，FastAPI 分别怎么执行？哪个更怕阻塞？
20. 在 `async def` 里写 `time.sleep()` 会怎样？为什么比写 `def` 更糟？
21. anyio 默认线程池上限是多少？这带来什么限制？
22. 只有同步库可用时，三种处理方式分别适合什么场景？
23. `for` 循环里 `await` 有什么问题？改完要注意什么风险？
24. 连接池大小 × worker 数应该怎么和数据库上限对齐？
25. 什么是背压？LLM 应用为什么必须做？

## 五、SSE 与流式（你的岗位命门）

26. TTFT 和总耗时分别是什么？流式优化的是哪个？
27. SSE 一帧的格式是什么？为什么必须有两个换行？
28. **流开始后报错，能不能返回 500？正确做法是什么？**
29. 客户端断开必须处理吗？不处理的损失是什么？
30. 为什么 LLM 前端用 `fetch` 而不是 `EventSource`？
31. SSE vs WebSocket，怎么选？
32. 为什么第一帧建议发"元信息"？

## 六、数据库

33. `add` / `flush` / `commit` 的区别？事务边界应该收在哪？
34. `get_db` 的 `except` 里为什么必须 `raise`？
35. `expire_on_commit=False` 解决什么问题？
36. 什么代码模式等于 N+1？怎么修？
37. 什么时候必须上 Alembic？

## 七、测试与部署

38. `with TestClient(app)` 和 `TestClient(app)` 差什么？
39. 测 SSE 要断言哪三件事？
40. 测试里为什么绝不能真调 LLM？怎么替换？
41. 流式上线后"不流了"，按什么顺序排查？
42. `--workers` 带来哪两个"内存不共享"的后果？
43. 健康检查里为什么不该做深度依赖检查？

## 八、安全

44. **为什么"前端直连 LLM API"必然泄露 Key？**
45. "后端中转"架构额外带来的四个收益？
46. 500 错误要同时满足哪两个目标？怎么做到？
47. 为什么 LLM 应用的限流比普通接口更紧急？

