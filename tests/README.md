# tests/ —— 自动化测试

> **这个目录只回答一个问题：「怎么证明改坏了会有人知道？」**

>

> 不写「为什么这么设计」（→ [decisions.md](../docs/decisions.md)）、

> 不写框架原理与推导（→ [stage1-fastapi.md](../notes/stage1-fastapi.md)）、

> 不写「做到哪了」（→ [roadmap.md](../docs/roadmap.md)）。

>

> **本文件与别处的分工**（判据：同一份事实只许写一处，否则改一处必漏另一处）：

| 内容 | 唯一出处 |
|---|---|
| 每个用例的**答案与原理** | [self-check-questions.md](../notes/self-check-questions.md) Step 12（第 1~17 题） |
| 踩坑的**完整过程与实测** | [DEVLOG.md](../docs/DEVLOG.md) 流水 + 踩坑记录 + 重要结论 |
| 待办的**编号、现状、证据** | [roadmap.md](../docs/roadmap.md) |
| 线上一族症状的**档期与过门判据** | [production-readiness.md](../docs/production-readiness.md) 门 1 |
| **怎么跑、怎么读输出、连接池怎么算** | **本文件** |

---

## 1. 十七个文件各测什么

**154 个用例**，按「测哪一层」分家 —— **一层一个文件**，改哪层就只跑那个文件：

| 文件 | 用例 | 测哪一层 | 上游怎么来 | 要真服务吗 |
|---|---|---|---|---|
| `test_smoke.py` | 6 | 地基：应用能起、lifespan 跑过、独立临时库生效、**健康检查两态**（`/health/ready` 200 / DB 挂时 503）、**测试库一进程一个**（#87）、**清表真的清干净**（每张表都写脏数据再断言 0） | 不涉及 | ❌ |
| `test_keys_cli.py` | 6 | **API key 运维 CLI**（13d-5）：签发的 key 真能过鉴权 / 明文绝不进库 / 自动建用户 / 同人两把 key 都可用 / `list` 不暴露明文与完整 hash / 撤销后立刻 401 / 撤销幂等且不存在的 id 退出码 1 | 不涉及 | ❌ |
| `test_rate_limit.py` | 9 | **每用户限流**（13d-4）：5 条桶数学（突发耗尽 / 随时间补充 / **封顶** / **按 key 隔离** / `Retry-After` 取整） + 4 条过 HTTP（第 3 个请求 429 + `Retry-After` / **配额按用户隔离** / 假时钟快进恢复 / 401 不消耗任何人的配额） | 不涉及 | ❌ |
| `test_docker_assets.py` | 5 | **容器产物静态检查**（13a-1）：`.env`/`.venv`/`.git`/`__pycache__` 必须被排掉 / `uv.lock`·`alembic`·`src` 不许被排掉 / **Dockerfile 每个 `COPY` 源都要活过 `.dockerignore`** / 非 root + exec 形式 CMD | 不涉及（**只读文件，不用 Docker**） | ❌ |
| `test_auth.py` | 14 | **鉴权与归属**（13d-2）：6 个端点的 401 / 公开路由免鉴权 / 错 key / **已撤销 key** / 越权读改写删全 **404** / 列表与 `total` 不泄露 / 聊天挂别人对话 id / **库里只有 sha256** | 不涉及（`FakeLlm` 只用于 chat 两条） | ❌ |
| `test_conversations.py` | 12 | 对话 CRUD 契约：全生命周期 / 游标分页 / 422 校验 / 404 语义 / **提交失败必须 5xx（不能先回 201）** | 不涉及 | ❌ |
| `test_upstream.py` | 7 | **路由层接线**：假 LLM 注入生效、三类上游故障 → 502、**上游 429 → 429 + `Retry-After`**、pre-flight 能改状态码 | `FakeLlm` | ❌ |
| `test_errors.py` | 11 | **错误形状契约**：envelope 三键 / 三种 404 靠业务码分 / 422 的 `details` 只留三键 / 500 不泄漏 / **500 的 CORS 头与 404 一致且不外泄给外来源** / **DB 连不上 → 503（SQL 错仍 500）** | `FakeLlm` | ❌ |
| `test_stream_frames.py` | 12 | **路由层**字段守卫：7 种怪 chunk + 帧序 + 终止条件（用假 chunk，不经 SSE 文本） | `FakeLlm` | ❌ |
| `test_stream_adapter.py` | 11 | **适配器协议层**：原始 SSE 字节 → `aiter_chunks()`，`data:{` 无空格 / 空 data / 非 dict / `[DONE]` 之后 | **直接喂 `httpx.Response`** | ❌ |
| `test_stream_accounting.py` | 10 | **账单四态**：completed / aborted / no_content / pending + 枚举值守卫 | `FakeLlm` | ❌ |
| `test_adapter_http.py` | 21 | **适配器真实 HTTP 路径**：L1 连不上 / L2 状态码不对（含 3xx、429）/ L3 结构不合规 / 错误正文截断 | 从**下面**换掉传输层：`httpx.MockTransport` | ❌ |
| `test_concurrency.py` | 4 | **并发与连接池**：串行化、首字节延迟、流跑到一半时 `pending` 已落库 | `FakeLlm`（慢速版） | ✅ **真 uvicorn** |
| `test_limits.py` | 13 | **护栏上限**：并发闸门 503 / 槽位归还（正常+异常）/ `max_tokens` 三分支 / 输入三条上限 / **上游总时长超预算 → `STREAM_TIMEOUT`** / `UPSTREAM_TIMEOUT` → 504 | `FakeLlm` | ❌ |
| `test_migrations.py` | 2 | **迁移层**：`alembic check` 无漂移 + 迁移建出的**结构**（列/外键/索引/唯一约束，用 `PRAGMA` 读）与 `create_all` 一致 | 不涉及（**起子进程跑 alembic CLI**） | ❌ |
| `test_startup_config.py` | 6 | **启动摘要层 + 启动接线**：白名单恰好这几项 / **每个 `Settings` 字段要么打出来、要么写明为何不打** / 连接串只留方言 + 库名 / 密钥与主机绝不出现 / **优雅窗口真的传给 uvicorn** | 不涉及 | ❌ |
| `test_source_rules.py` | 4 | **源码约定（静态检查）**：用 `ast` 断言每个写路由函数体里有 `await db.commit()`（#86）+ **每个非公开路由都声明了 `CurrentUserDep`**（13d-2）；两条白名单都不许留过期项 | 不涉及（**只读源码，不跑应用**） | ❌ |

> ⚠️ **`fakes.py` 不是测试文件**，是共用的假对象：

> `FakeChatStream(LlmChatStream)` / `FakeLlm(LlmClient)` —— **继承真类**，

> 所以签名漂移会被 mypy 抓成 `[override]` 错误。

> `conftest.py` 是全局准备（环境变量 / **跑真实迁移建表** / 清表 + **写两个测试用户与两把 key** / `client`、`other_client`、`anon_client`、`db_path` fixture）。

> ⭐ **三条 fixture 的分工**（13d-2 起所有业务端点都要 `X-API-Key`）：

> `client` = alice 的 key，绝大多数用例用它；`other_client` = bob 的 key，只用来测**越权**；

> `anon_client` = 不带凭据，只用来测 **401**。要自己裸造 `TestClient(app)` 的用例（如 `test_errors.py` 里要 `raise_server_exceptions=False`）

> 必须显式传 `headers=AUTH_HEADERS` —— 📎 不传就是成片 401，而不是"能调但没数据"。

> `test_migrations.py` 是**唯一**起子进程的用例（`sys.executable -m alembic`）：`env.py` 的连接串取自
> `settings` 单例，进程内改不动 → 代价是多约 2 秒（[决策 33](../docs/decisions.md)）。

📎 **「跑真实迁移建表」的一次性成本（2026-11-16 本机实测）**：

| 动作 | 耗时 | 说明 |
|---|---|---|
| `upgrade head` 对着**空库**（真建表） | **166 ms** | 这就是 `conftest` 每次 pytest 多付的那点钱 |
| `upgrade head` 对着**已是最新**的库 | **7 ms** | 幂等：只读 `alembic_version` 比一下，什么都不做 |
| `create_all` 建同样 3 个对象 | **18 ms** | 快 9 倍，但它**不读迁移文件** → 迁移写错测不出来 |

⚠️ 关键：这个成本按 **pytest 会话**（一次 `uv run pytest`）付，**不是按用例**付 ——
115 个用例共用同一个库，每个用例前只 `DELETE` 清表。**也不要**在应用启动时跑迁移（多副本会 DDL 竞态）。

---

## 2. 怎么跑

| 想做什么 | 命令 |
|---|---|
| 全量（提交前必跑） | `uv run pytest -q` |
| 只跑一层 | `uv run pytest tests/test_stream_frames.py -q` |
| 只跑一个用例 | `uv run pytest "tests/test_concurrency.py::test_two_concurrent_streams_do_not_serialize" -q` |
| 看通过/失败的**详细原因** | `uv run pytest -q -rxX`（`x` = 把 XFAIL 的原因也打出来） |
| 覆盖率（终端） | `uv run pytest --cov --cov-report=term-missing` |
| 覆盖率（浏览器，能看**黄行**） | `uv run coverage html` → 打开 `htmlcov/index.html`（⚠️ 文件名带哈希前缀，**只能从 index 点进去**，手输 `app.py.html` 找不到） |
| 找**没被任何测试覆盖**的代码 | 上面任一方式，然后按「## 6 怎么读输出」读 |

⚠️ `htmlcov/` 与 `.coverage` 已在 `.gitignore` 里（2026-10-08 建项目时就加了）。

⚠️ **不要用 `uv run coverage annotate`** —— 它会生成 12 个 `src/app/**/*.py,cover`，而 `.gitignore` **没有**这条规则，

    一不小心 `git add .` 就把报告副本提交了。📎 实测踩过一次。

---

## 3. 怎么读 pytest 输出

### 3.1 一行进度条就是全部用例，**位置 = 文件里的定义顺序**

```text

.FFF.                                        [100%]

```

| 字符 | 含义 |
|---|---|
| `.` | 通过 |
| `F` | 失败 |
| `x` | XFAIL（预期失败，**不算红**） |
| `X` | XPASS（本以为会失败却过了 → 配合 `strict=True` 会变红） |
| `s` | skip |

⭐ **读法**：看到 `FFF` 先数有几个 `.`。**全红先怀疑「接线」（fixture 没注入 / 拼错 URL / 假对象没生效）；

部分红才怀疑「逻辑」。** 📎 12d-1 那轮 11 个用例全红，根因是学习者把请求体写成 `REQ = {"message": ...}`（少个 s）。

### 3.2 失败块：`>` 是失败那一行，`E` 是实际 vs 期望

```text

>   assert _rows(db_path) == [("completed", 31, 7, 38)]

E   AssertionError: assert [('pending', 0, 0, 0)] == [('completed', 31, 7, 38)]

E     At index 0 diff: ('pending', 0, 0, 0) != ('completed', 31, 7, 38)

```

⭐ `assert 左 == 右` 里**左边是实际值**（从库里查出来的），右边是你写的期望值。

### 3.3 `Captured log call` 里的行号就是**哪个守卫先触发**

```text

WARNING app.api.app:app.py:640 上游 choices 不是列表，已丢弃: type=dict

ERROR   app.api.app:app.py:744 流式零内容：上游 chunk=1 内容帧=0

```

⚠️ **但它只说了「内容丢了」，没说「钱也丢了」** —— 这就是待办 #70 靠「账」而不是靠日志才被发现的原因。

### 3.4 覆盖率表里的两种「缺」

```text

Name                  Stmts   Miss Branch BrPart  Cover   Missing

src\app\api\app.py      229     32     52      6    84%   653->666, 737

```

| 写法 | 含义 |
|---|---|
| `737` | 这一行**一次都没执行** |
| `122-135` | 连续一段都没执行 |
| **`653->666`** | **分支只走了一半** —— 从 653 跳到 666，中间那条分支从没走过。这就是 HTML 报告里的 🟡 黄行 |

### 3.5 ⚠️ 覆盖率数字**会抖**，别拿它当精确指标

📎 **同一个命令连跑 4 次**（中间什么都没改）：

```text

第 1 次 | TOTAL  484  66  74  8  85%   app.py 缺 221-226

第 2 次 | TOTAL  484  67  74  8  84%   app.py 缺 220-226

第 3 次 | TOTAL  484  67  74  8  84%   app.py 缺 220-226

第 4 次 | TOTAL  484  67  74  8  84%   app.py 缺 220-226

```

只差一行（`220` 那个 `try:`），`Cover` 就在 **84% / 85%** 之间横跳。推测与 SQLAlchemy 的 greenlet 切栈导致tracing 少收事件有关（同源问题见 §5 坑 #3）。

⭐⭐ **判据：覆盖率是「找缺口的探照灯」，不是「达标分数线」。**

- ✅ 用它找「哪块没被验证过」

- ❌ **不要设 `--cov-fail-under`** —— 数字会抖，CI 会莫名其妙红

- ✅ 想守住某个行为，写**断言**，不写覆盖率阈值

---

## 4. ⭐ 连接池：本项目有【两个】池，不是一个

### 4.1 两个池的实测参数

| 池 | 谁创建的 | 类 | 上限 | 超限后 |
|---|---|---|---|---|
| **数据库池** | `database.py` 的 `create_async_engine` | `AsyncAdaptedQueuePool` | `size=5` + `max_overflow=10` = **15 条** | 第 16 个等 `pool_timeout=30s`，超时抛错 → 500 |
| **上游 HTTP 池** | `llm_client.py` 的 `httpx.AsyncClient` | `AsyncHTTPTransport`（httpx 默认 `Limits`） | `max_connections=100`（keepalive 20） | 排队等空闲连接 |

📎 实测（`engine.pool.status()`）：

```text

Pool size: 5  Connections in pool: 0  Current Overflow: -5  Current Checked out connections: 0

```

⭐⭐ **推论：DB 池（15）远小于 HTTP 池（100）→ 瓶颈永远是数据库池。**

待办 #59 里那个「第 16 个并发」的 **16** 就是从 `5 + 10 + 1` 来的。

### 4.2 哪些操作占哪个池、持有多久（⭐ 这一张是核心）

| 操作 | 占哪个池 | 从什么时候开始 | 到什么时候还 | 盘踞时长 |
|---|---|---|---|---|
| `get_db` 依赖（任何走库的路由） | **DB** 1 条 | 第一条 SQL | `commit` / `rollback` | 请求级 |
| **SSE 流（改造前）** | **DB** 1 条 | 开流前的 `flush()` | `get_db` 收尾 | 🔴 **整条流 10~60s**（#73） |
| **SSE 流（现在）** | **DB** 1 条 | 每次 `commit()` | 立刻 | ✅ 毫秒级 |
| `client.open_chat_stream()` | **HTTP** 1 条 | 响应头就绪 | `aclose()`（`finally` 里） | ⚠️ **整条流**（**无法避免** —— 要边读边转） |
| `client.list_models()` | **HTTP** 1 条 | 发请求 | 响应读完 + `aclose()` | 毫秒级 |
| `_read_error_body()` | **HTTP** 同一条 | 上游返回非 2xx | 它自己 `aclose()` | 毫秒级 |
| `_truncate_all()`（conftest 清表） | **不占池** | —— | —— | ⚠️ 见 4.3 ③ |
| `db_path` 直接查库（如 12e 的 `latest()`） | **不占池** | —— | —— | ⚠️ 同上 |
| `TestClient` 发请求 | **不占任何池** | —— | —— | ASGI 直连，无 TCP |

### 4.3 四个反直觉的点

**① SSE 流同时占两个池。** 上游 HTTP 连接从「响应头就绪」到「流读完」一直被攥着（这是流式协议的本质，

**不可能避免**）；而数据库连接**可以**避免 —— 只要不把写事务活得跟流一样长。

**② 「绕过池」≠「绕过锁」。** `_truncate_all()` 用裸 `sqlite3.connect()`，确实不占 SQLAlchemy 的池，

但它照样要抢 **SQLite 的写锁**。所以「我在测试里用 sqlite3 直连，不会影响池」这句话是**错的**。

**③ `engine` 是模块级单例 → 所有测试共享同一个池。**

所以**一个用例泄漏一条连接，后面所有用例一起变慢/超时**，而且报错指向的是**后面那个文件**，不是泄漏源。

📎 这也是为什么「逐个单跑全绿、一起跑就红」这种症状要**先怀疑连接泄漏**。

**④ `TestClient` 两头都是内存流 → 没有 TCP 背压 → 池占用测不出来。**

📎 实测：6 条并发流，`TestClient` 下 `checkedout` 峰值 **0**；真 uvicorn 下 **= 6**。

所以 `test_concurrency.py` 必须真起 `uvicorn`（`port=0` 随机端口）。

### 4.4 考虑并发时要问的 5 个问题（按顺序问）

| # | 问题 | 为什么先问这个 |
|---|---|---|
| 1 | **这次请求一共占几条连接？DB 几条、HTTP 几条？** | 两个池分开算。漏掉任意一个，「能扛多少」就是错的 |
| 2 | **每条连接持有多久？** 毫秒级 还是 整条流？ | **时长 × 并发数 = 占用积分**。占 60s 的第 16 个请求就超时，占 5ms 的不会 |
| 3 | **池上限是多少？第 N+1 个等多久、超时后报什么？** | 15 条 / 30s 超时 → 用户看到的是 500。**这个数必须能背出来** |
| 4 | **断开 / 异常 / 取消三条路上，连接有没有被还？** | 只在正常路径还 = 一遇异常就慢性泄漏 |
| 5 | **换成 PostgreSQL 后这两个数字会变成多少？** | SQLite 单写者会让「并发」退化成「排队」，PG 不会 —— 症状变、根因不变 |

⭐ 判据一句话：**「谁被持有得太久」比「谁报了什么错」更能定位并发问题的根因。**

### 4.5 我们的实测曲线（#73 修复前 vs 后）

假上游每条流 0.6s，真 uvicorn 同时在飞：

| 并发数 | 修复前 总耗时 | 修复后 总耗时 | 修复前 首字节 | 修复后 首字节 |
|---|---|---|---|---|
| 1 | 0.66s | 0.67s | 0.03s | 0.05s |
| 2 | **1.32s**（串行） | **0.67s** | 0.01 / **0.67s** | 0.03 / 0.04s |
| 4 | **2.60s**（串行） | **0.71s** | 0.02 / 0.67 / 1.33 / **1.98s** | 全都 < 0.07s |

| 更极端的一组 | 修复前 | 修复后 |
|---|---|---|
| 6 条并发、单流 2.0s | 6.53s，**3 条拿到 200 + 0 帧** | **2.17s，6 条全 7 帧** |
| 连接池 `checkedout` 峰值 | **6** | **2** |
| 强杀进程（`os._exit(9)`）后的账单 | **0 行** | **`(1,'pending',0)`** |

📎 那 3 条失败请求的服务端日志：`sqlite3.OperationalError: database is locked`（发生在 `INSERT INTO llm_calls`）。

⚠️ **客户端拿到的是 HTTP 200 + 空响应体，不是 5xx** —— 因为响应头在生成器开跑之前就发出去了。

---

### 4.6 三种 `transport`：`TestClient` 到底是不是「真发请求」

**先看对象链**（这是「传输层」这三个字在代码里的落点）：

```
httpx.AsyncClient
  └─ _transport = AsyncHTTPTransport      ← 默认；决定「字节怎么进出」
       └─ _pool = AsyncConnectionPool     ← 连接池就在这一层
            └─ 一条 keep-alive TCP 连接 → socket
```

**「换 transport」= 只换「字节怎么进出」，上面的 `AsyncClient` / `post()` / `stream()` API 一个字都不用改。**

📎 三种 transport 实测（2026-11-04，本项目 venv 内跑）：

| transport | 谁在用 | 有没有 `_pool` | `vars()` 里有什么 | 走真网络吗 |
|---|---|---|---|---|
| `AsyncHTTPTransport` | 我们代码里的 `httpx.AsyncClient()` | ✅ `AsyncConnectionPool`（`_max_connections=100` / `_max_keepalive_connections=20`） | `['_pool']` | ✅ |
| `_TestClientTransport` | `fastapi.testclient.TestClient` 内部 | ❌ | `['app', 'app_state', 'client', 'portal_factory', 'raise_server_exceptions', 'root_path']` | ❌ |
| `MockTransport` | `tests/test_adapter_http.py` | ❌ | `['handler']` | ❌ |

⭐⭐ **判据：`TestClient` 就是「换了个 transport」** —— 它把手写的 `httpx.Request` 直接扔进 ASGI `app`，
**中间没有 socket、没有 TCP、没有操作系统缓冲区**。所以：

- 📎 实测 `TestClient(app).get("http://example.com/ping")` 返回的是**我们自己 app 的** `{"pong": "1"}` ——
  **host 谁都不看**，因为这个请求根本没离开进程。
- 📎 实测 6 条并发流：`TestClient` 下数据库池 `checkedout` 峰值 **0**，真 `uvicorn` 下 **= 6**
  （见 §4.3 ④）。**不是池「没被占」，是根本没有池这一层。**

#### 4.6b `MockTransport` 和 `FakeLlm` 的分工（别混）

| | `MockTransport` | `FakeLlm`（`dependency_overrides`） |
|---|---|---|
| 换掉的是什么 | **transport** —— 我们发出去的请求不再进 socket | **适配器本身** —— `LlmClient` 整个被替换 |
| 被测代码还剩哪些 | `LlmClient` **全是真的**：拼 URL、拼 body、读状态码、翻译错误、解析 SSE | 只剩路由和记账，适配器一行都不执行 |
| 能测出什么 | 上游返回 429 / 401 / 3xx / 非 JSON 时**我们怎么翻译** | 路由接线、错误码 → HTTP 状态码、账单四态 |
| 什么时候用 | 要覆盖 [llm_client.py](../src/app/llm_client.py) 的翻译逻辑时（#75 / #60） | 要测「不依赖真实 LLM」的路由行为时（绝大多数用例） |

🔴 **两个说法要纠正**（这曾是笔记里的错）：

1. `MockTransport` **拦的是「我们发出去的请求」**，不是「服务器收到的请求」——
   方向上它是**客户端这一侧**的假出口，服务器不存在。
2. `FakeLlm` 替的是**适配器**，不是「业务逻辑层」。它替换的位置是 `app.dependency_overrides[get_llm]`，
   也就是**依赖注入的接缝**，跟「业务逻辑」这个抽象层没关系。

📌 一句话：**`MockTransport` 假在「网线」，`FakeLlm` 假在「翻译官本人」。**

---

### 4.7 现在多了一道闸门：`max_concurrent_upstream_calls`（2026-11-04）

§4.1~§4.6 讲的是**连接池** —— 它们是"被动兜底"：满了就让请求排队，超时给 500。
我们现在在自己这层加一道**主动闸门**，让它**先于**池顶住，并且给一个客户端能读懂的码。

| 层 | 数字 | 顶穿时客户端看到 | 位置 |
|---|---|---|---|
| 上游配额 | 未知 | **429** + `Retry-After` | 外部 |
| **我们的闸门** | `MAX_CONCURRENT_UPSTREAM_CALLS`（默认 **4**） | **503** + `Retry-After` | 待 12g-2 落地 |
| 上游 HTTP 池 | **100** | 排队（几乎不会满） | [llm_client.py](../src/app/llm_client.py) |
| 数据库池 | **15**（5+10），`pool_timeout=30s` | **卡 30 秒 → 500** | [database.py](../src/app/database.py) |

⭐⭐ **判据：闸门设得比它下游的池还宽 = 把「明确的 503」换成「30 秒后的 500」。**
所以 `MAX_CONCURRENT_UPSTREAM_CALLS` 必须 **≤ 15 再减去非 chat 路由的余量**。
📎 数字关系：`4（闸门） ≤ 15（DB 池） « 100（HTTP 池）`。
完整推导见 [architecture.md §13.3](../docs/architecture.md)。

📎 三种"超限怎么办"的实测（`Semaphore(1)`、单流 1.5s、同时发 2 个）：

| 策略 | 被挡的那个 |
|---|---|
| 纯排队 `async with sem` | 200，但**头 3.05s** 才到（客户端像卡死） |
| 有限等待 `wait_for(acquire, 0.5s)` | **503，头 0.50s** |
| 快速失败 `sem.locked()` | **503，头 0.02s** |

⚠️ **测并发时必须把闸门调大**，否则 `test_concurrency.py` 里 N=4 的用例会被自己的闸门挡住 ——
这正是"测试配置和生产配置不是一回事"的经典陷阱。

📌 还有一个只有测过才知道的点：**用 `yield` 依赖做闸门，槽位会持有到整条流结束**
（📎 日志顺序 `入场 入场 → 流结束 → 离场`）。同一个 `yield` 机制在 `get_db` 那里是**缺陷**（#59），
在这里正好是**要的语义** —— 因为"并发上游生成数"本来就该按整条流算。

---

## 5. 测试专属的坑（都是我们真踩过的）

| # | 坑 | 📎 证据 | 判据 / 正确做法 |
|---|---|---|---|
| 1 | **`TestClient` 测不出并发问题** | 同一份代码：`checkedout` 峰值 `TestClient` **0** / 真 uvicorn **6** | **「并发」是网络层的行为** —— 想看并发就必须有真连接与背压 |
| 2 | **`StrEnum` 的值拼错，四道门全绿** | `PENDING = "pengding"` → `ruff`/`format`/`mypy`/`pytest 61 passed`；`LlmCallStatus.PENDING == "pending"` 是 `False` | **「类型对」≠「值对」**：`mypy` 只管成员名，值的字面量必须**单独一条断言**钉住 |
| 3 | **覆盖率会把「真跑到了」报成「未覆盖」，而且**数字会在 1 行内抖** | `465`(`await db.delete`)/`485`(`conv.title=`) 报未覆盖，但探针实测 DELETE 后库里 `1 → 0` 行；同一命令连跑 4 次 `TOTAL Miss` 在 **66/67** 之间跳 | **覆盖率数字必须和行为断言交叉验证**，且**不要设 `--cov-fail-under`**（见 §3.5） |
| 4 | **`xfail(strict=True)` 在修好后会主动变红** | 修 #73 后 2 个 `[XPASS(strict)]` → `2 failed` | 这是**已知缺陷的正式登记方式**：缺陷在时不挡开发，修好了逼你删标记 |
| 5 | **`coverage annotate` 生成物不在 `.gitignore`** | 生成 12 个 `src/app/**/*.py,cover`，`git status` 全是 `??` | **引入任何生成物之前先确认 `.gitignore` 挡得住** |
| 6 | **`omit` 掉无关文件，覆盖率才有意义** | 不 omit 阶段 0 的 `main.py` / 入口 `__main__.py`：**84% → 78%** | 分母里不该有「跟服务无关」或「要真起进程才能测」的文件，否则缺口被稀释 |
| 7 | **`dependency_overrides` 把整层适配器绕过了** | `llm_client.py` 只覆盖 **63%**，真实 HTTP 路径 0%；把 `_request` 的 `except` 改坏 → **61 个全绿**（当时的用例数） | **假对象越彻底，被测的真代码越少** —— 要另建一层「穿过适配器」的测试。✅ 2026-11-04 已补 `test_adapter_http.py`（10 个用例 + `MockTransport`），`llm_client.py` 现已 **100%** |
| 8 | **`with sqlite3.connect(...)` 不关连接** | 退出 `with` 后连接**仍可用**（`__exit__` 只 commit/rollback） | 「`with` 不承诺关闭」——**判断一个 `with` 做了什么，只看 `__enter__`/`__exit__` 源码** |
| 9 | **不写 `with TestClient(app)` → 表不存在** | `/health`·`/v1/models`·`/health/ready` 全 200，`POST /v1/conversations` 炸 `no such table` | **「某个接口 200」完全不能证明 lifespan 跑过** —— 只有用到 lifespan 那份资源的接口才验得出来 |
| 10 | **`lambda f=fake: f` 当依赖覆盖会炸** | FastAPI 把参数当查询参数 → `TypeError: AppError.__init__() missing 1 required positional argument` | 覆盖值必须是**不接收参数**的可调用对象 |
| 11 | **断言工具退出码写死 `== 1`，守卫会永远绿** | 📎 Windows 上 `alembic check` 检测到漂移时 `sys.exit(-1)` → `subprocess` 拿到 **`4294967295`**（Python 里是 `-1`），断言 `== 1` 就永远不成立 | 断言**只写「成功是 0」**（`returncode == 0`），失败一律按 `<成功条件之外>` 处理，并检查输出里的关键字（坑 K92） |
| 12 | ~~**测试库是固定文件名，两个 pytest 同时跑会互相踩**~~ | 📎 2026-11-17 复核覆盖率时连跑两次：第二次出现 `ERROR tests/test_limits.py::… - sqlite3.OperationalError`，覆盖率 **93% → 64%**、`app.py` **89% → 29%**；另一次 `55 passed, 76 errors` | ✅ **已修（#87 / 坑 K94）**：库名带 `os.getpid()` → 一进程一个库。📎 修后：**两个 pytest 并行**跑都 `132 passed`；**连跑三次**全绿。⭐ 记住成本：**偶发失败会被误读成「代码有 bug」**，它比稳定失败贵得多 |

---

## 6. 重要问答索引（答案不在这里，指过去）

完整题目与答案唯一出处：[self-check-questions.md](../notes/self-check-questions.md) 的 **Step 12**（17 题）+ **Step 13b-2a**（4 题，迁移守卫）。

这里只给**主题**，方便你要查的时候知道去哪一条：

| 题 | 主题 | 一句话钩子 |
|---|---|---|
| 1 | `TestClient` 为什么不启服务器 | 按 ASGI 协议在进程内直接调 app；那个「httpx」其实是 `httpx2` |
| 2 | `with TestClient` 与不 with 差什么 | 📎 症状：三个接口 200，只有用表的接口炸 `no such table` |
| 3 | `ASGITransport` 的好处与代价 | 代价是**不跑 lifespan**、不过网络栈 |
| 4 | 测 SSE 要断言哪三件事 | 分多帧 / 帧格式 / 收尾标记 |
| 5 | 为什么测试绝不能真调 LLM | 慢、要钱、**结果不确定** |
| 6 | `raise_server_exceptions` 默认 `True` | 测 **500 的响应体** 必须关掉它 |
| 7 | `DATABASE_URL` 为什么必须在 `import app` 之前设 | `settings` / `engine` 都是**模块级单例** |
| 8 | `with TestClient` 在**机制层**做了什么 | ASGI 有两条通道：`http` / **`lifespan`** |
| 9 | 同样是 `with`，为什么行为差这么远 | 看 `__enter__`/`__exit__` 源码，别看 `with` 这个词 |
| 10 | 假对象没覆盖的方法会不会真的花钱 | **不会**，`AttributeError: no attribute '_http'`（但不是绝对保证） |
| 11 | 为什么 `client` fixture 不设 `raise_server_exceptions=False` | 那会让**所有**真 bug 退化成「500 响应」 |
| 12 | 对调 header 断言与读 body 会怎样 | **不会红** —— 变的是**报错指向的方向** |
| 13 | 流式循环的终止条件 | **只有上游 EOF**；`[DONE]` 只 `continue`，`finish_reason` 完全不影响 |
| 14 | `usage` 与坏结构同帧 → 记账丢了 | 📎 `('pending', 0, 0, 0)` → 待办 #70 |
| 15 | 为什么「只提前记账」而不是「整块上移」 | 整块上移会改掉已实测的帧序 |
| 16 | `StrEnum` 为什么四道门都拦不住 | 见本文件「坑 #2」 |
| 17 | `flush` → `commit` 一个词改三件事 | 见下表「#73」一行 |

---

## 7. 按顺序收掉的待办（这一节是「什么时候该写测试」的证据）

| 时间 | 待办 | 是被什么逼出来的 | 证据 |
|---|---|---|---|
| 2026-11-01 | **#40** 没有 `tests/` | Step 12 开工 | 12a~12e 累计 **61 个用例** |
| 2026-11-02 | **#70** 坏结构帧吞掉 `usage` | 学习者追问「字段错会不会让 usage 被跳过」 | 📎 3 组实测全 `pending 0/0/0`；补丁后 5 绿 |
| 2026-11-02 | **#68** 零内容收尾停在 `pending` | 写 12d 探针时顺手发现 | 新增第 4 态 `no_content` |
| 2026-11-03 | **#73** 并发流被完全串行化 | 12e 用**真 uvicorn**测并发 | 📎 N=4 总耗时 **2.60s → 0.71s** |
| 2026-11-03 | **#59** 连接被整条流独占 | 与 #73 **同一处改动** | 📎 池峰值 **6 → 2** |
| 2026-11-03 | **#42** 崩了不留账 | 同上 | 📎 强杀后 **0 行 → 1 行 `pending`** |
| 2026-11-03 | **#7 #10 #15 #40** 台账对齐 | 12f 数待办时发现早就解决了却没标 | 「还剩几条」原来被高估 |
| 2026-11-03 | **#45** 补登记 | 它在 3 处文档被引用，但待办表里**没有这一行** | 合并进 #30 时漏删引用 |
| 2026-11-03 | 🆕 **#75** 适配器真实 HTTP 路径 0% 覆盖（发现） | 12f 第一次跑覆盖率 | 📎 `llm_client.py` **63%**，改坏 `_request` 仍 61 绿 |
| 2026-11-04 | ✅ **#75 关闭** | 12f-3 用 `MockTransport` 从传输层下面喂数据 | 📎 `llm_client.py` **63% → 100%** |
| 2026-11-04 | ✅ **#60 关闭** 上游 4xx/429 一律 502 | 补 `llm_client` 覆盖率时看清了 `_STATUS_BY_CODE` 里**只有 3 个上游码** | 📎 11 个上游状态码逐个实测；`82 passed`、分支覆盖 **91%** |
| 2026-11-04 | ✅ **#38 关闭** 输入侧无上限（单请求输入可达 1M tokens ≈ $0.30） | 学习者读 `le=32768` 那段注释时追问「客户端能不能把值调大」 | 📎 单请求最坏 $0.05；6 个边界实测；**只有「合计」那条真管成本** |
| 2026-11-04 | ✅ **#44 的 P0 部分关闭** 并发上限 + 成本上限 | 12g 前实测：把 `finally: release()` 整块删掉，**82 个用例一个都不红** | 📎 补 11 条后 9 个变异 9 抓；`deps.py` 89%→94%、`schemas.py` 94%→97% |
| 2026-11-16 | 🆕 **迁移与模型分叉，93 个用例一个都不红**（13b-2a，无编号） | 13b-1 把 DDL 交给 Alembic **之后**才发现：所有用例都跑在 `lifespan` 的 `create_all` 建好的库上，**没有一条用例读过迁移文件** | 📎 3 个变异（删索引 / 删 `ondelete` / 模型加列不生成迁移）→ 补守卫前全绿，补后 **6 条全红** |

⭐⭐ **最值钱的一条**：**测试最大的产出不是用例数，而是「用测试逼出真缺陷」。**

#70 / #68 / #73 三个都不是「写测试时顺手发现的」，是**测试逼着我们必须先无歧义地描述行为**，

描述的过程中才照出原来的实现不对。

---

## 8. 维护约定

| 什么时候改本文件 | 什么时候**不要**改本文件 |
|---|---|
| 新增/删除测试文件、用例数变了 | 某个用例的**原理**变了 → 改 `self-check-questions.md` |
| 连接池参数或「谁占哪个池」变了（换 PG / 加流式接口 / 改池大小） | 某次**踩坑的过程** → 改 `learning-log.md` |
| 发现新的「测试专属」坑（测试框架/工具层面） | 待办状态变了 → 改 `roadmap.md` |
| 覆盖率基线数字变了（供对照） | 「为什么选这个方案」→ 改 `decisions.md` |

⭐ 判据：**「这条知识只对『怎么写测试』有用吗？」**

是 → 写这里；不是（对写业务代码同样有用）→ 写 `study_notes/learning/`。
