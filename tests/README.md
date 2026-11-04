# tests/ —— 自动化测试

> **这个目录只回答一个问题：「怎么证明改坏了会有人知道？」**
>
> 不写「为什么这么设计」（→ [decisions.md](../study_notes/project/decisions.md)）、
> 不写框架原理与推导（→ [stage1-fastapi.md](../study_notes/learning/stage1-fastapi.md)）、
> 不写「做到哪了」（→ [roadmap.md](../study_notes/project/roadmap.md)）。
>
> **本文件与别处的分工**（判据：同一份事实只许写一处，否则改一处必漏另一处）：

| 内容 | 唯一出处 |
|---|---|
| 每个用例的**答案与原理** | [self-check-questions.md](../study_notes/learning/self-check-questions.md) Step 12（第 1~17 题） |
| 踩坑的**完整过程与实测** | [learning-log.md](../study_notes/learning/learning-log.md) 流水 + 踩坑记录 + 重要结论 |
| 待办的**编号、现状、证据** | [roadmap.md](../study_notes/project/roadmap.md) |
| 线上一族症状的**档期与过门判据** | [production-readiness.md](../study_notes/project/production-readiness.md) 门 1 |
| **怎么跑、怎么读输出、连接池怎么算** | **本文件** |

---

## 1. 九个文件各测什么

71 个用例，按「测哪一层」分家 —— **一层一个文件**，改哪层就只跑那个文件：

| 文件 | 用例 | 测哪一层 | 上游怎么来 | 要真服务吗 |
|---|---|---|---|---|
| `test_smoke.py` | 2 | 地基：应用能起、lifespan 跑过、独立临时库生效 | 不涉及 | ❌ |
| `test_conversations.py` | 9 | 对话 CRUD 契约：全生命周期 / 游标分页 / 422 校验 / 404 语义 | 不涉及 | ❌ |
| `test_upstream.py` | 6 | **路由层接线**：假 LLM 注入生效、三类上游故障 → 502、pre-flight 能改状态码 | `FakeLlm` | ❌ |
| `test_errors.py` | 7 | **错误形状契约**：envelope 三键 / 三种 404 靠业务码分 / 422 的 `details` 只留三键 / 500 不泄漏 | `FakeLlm` | ❌ |
| `test_stream_frames.py` | 12 | **路由层**字段守卫：7 种怪 chunk + 帧序 + 终止条件（用假 chunk，不经 SSE 文本） | `FakeLlm` | ❌ |
| `test_stream_adapter.py` | 11 | **适配器协议层**：原始 SSE 字节 → `aiter_chunks()`，`data:{` 无空格 / 空 data / 非 dict / `[DONE]` 之后 | **直接喂 `httpx.Response`** | ❌ |
| `test_stream_accounting.py` | 10 | **账单四态**：completed / aborted / no_content / pending + 枚举值守卫 | `FakeLlm` | ❌ |
| `test_adapter_http.py` | 10 | **适配器真实 HTTP 路径**：L1 连不上 / L2 状态码不对（含 3xx）/ L3 结构不合规 / 错误正文截断 | 从**下面**换掉传输层：`httpx.MockTransport` | ❌ |
| `test_concurrency.py` | 4 | **并发与连接池**：串行化、首字节延迟、流跑到一半时 `pending` 已落库 | `FakeLlm`（慢速版） | ✅ **真 uvicorn** |

> ⚠️ **`fakes.py` 不是测试文件**，是共用的假对象：
> `FakeChatStream(LlmChatStream)` / `FakeLlm(LlmClient)` —— **继承真类**，
> 所以签名漂移会被 mypy 抓成 `[override]` 错误。
> `conftest.py` 是全局准备（环境变量 / 清表 / `client` 与 `db_path` fixture）。

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

---

## 6. 重要问答索引（答案不在这里，指过去）

完整题目与答案唯一出处：[self-check-questions.md](../study_notes/learning/self-check-questions.md) 的 **Step 12**（17 题）。
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
| 2026-11-03 | 🆕 **#75** 适配器 0% 覆盖 | 12f 第一次跑覆盖率 | 📎 `llm_client.py` **63%**，改坏 `_request` 仍 61 绿 |

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

