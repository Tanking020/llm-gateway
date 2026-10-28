# 自检题清单（按阶段汇总）

> **这份文件是干什么的**：把**所有阶段的自检题**集中在一处，按阶段/步骤排列，每题配**一句话答案**。
> 用途：复习、面试前过一遍、确认自己是真的懂而不是"看着眼熟"。
>
> **与其它笔记的分工**（避免重复，规则见规范 §12.1）：
>
> | 想知道 | 去哪看 |
> |---|---|
> | **题目与简要答案**（复习用） | **本文件** |
> | 某题的**深度原理与实测过程** | [stage0-engineering-basics.md](stage0-engineering-basics.md) / [stage1-fastapi.md](stage1-fastapi.md) |
> | 我做过什么、踩过什么坑 | [learning-log.md](learning-log.md) |
>
> ⚠️ **怎么用**：**先自己答，再对照**。只读答案 = 没学会。
> 答案只写要点，**展开要能自己讲出来**才算过。
>
> **标记含义**：
> - ⭐ = **面试高频 / 易答错 / 有坑**
> - 🟡 = 我实际答错过（原文与订正见对应笔记）
> - 📎 = 有配套的实测实验（笔记里有完整数据）

---

## 阶段 0 · 工程基础（Step 1 ~ 10）

### Step 1 · 为什么需要工程规范

1. "能跑"和"可复现"差哪三样东西？
   > 依赖版本锁定（lock）、运行环境声明（Python 版本 / 系统依赖）、运行方式记录。
2. 为什么"不固定随机种子"会让所有实验结论失效？
   > 无法复现同一个实验 → 没有可比较的基线 → 结论不可信。
3. 遇到 `train_v2_final_fix.py` 这种文件，正确做法是什么？
   > 别用"复制文件"当版本管理；用 Git 提交与分支代替。

### Step 2 · 虚拟环境与依赖管理（uv）

1. `pyproject.toml` 和 `uv.lock` 分别"声明"什么？谁该进 Git？
   > pyproject 声明**意图**（要哪些包、版本范围）；lock 锁定**结果**（每个包的确切版本 + 哈希）。**两个都进 Git**。
2. 为什么 `uv run` 比"先 activate 再 python"更不容易出环境问题？
   > `uv run` 先确保环境与 lock 一致再执行；手动 activate 依赖当时的 shell 状态，容易环境漂移。
3. 虚拟环境隔离了哪些东西？**没有**隔离哪些东西？
   > 隔离**第三方包**；不隔离 Python 解释器本身（那个由 `.python-version` 管），也不隔离系统库/系统工具。
4. 全局装了个包、代码里 import 成功、但没写进 `pyproject.toml` —— 为什么这是最危险的 bug 之一？
   > 本机能跑、换机器/CI 就 `ModuleNotFoundError`；"碰巧能跑"掩盖了真问题。
5. ⭐⭐ `uv sync` 做的 **editable 安装**（`uv pip install -e .`）本质是什么？它怕"代码变化"还是"路径变化"？
   > 本质是**只写指针、不复制代码**：在 `.venv` 里写 `_editable_impl_<包名>.pth`（一行绝对路径）+ `<包名>.dist-info\direct_url.json`（`{"url":"file:///...","dir_info":{"editable":true}}`）+ `pyvenv.cfg` 的 `prompt`。
   > ⭐ 结论：**改代码完全不用重装**（这正是 editable 的价值），**改文件夹路径/项目名必须删 `.venv` 重建**（指针全悬空 → `import app` 立刻炸）。
6. 由上题推出：既然 `.venv` 里存着绝对路径，为什么还说它"可以随时删掉"？
   > 因为它**不含任何"只有它才知道"的信息** —— 全部内容都能由 `pyproject.toml`（意图）+ `uv.lock`（确切版本）+ 本机 Python（`.python-version`）重新算出。
   > 这正是"`uv.lock` 进 Git、`.venv` 不进 Git"的实质：**进 Git 的是配方，不进 Git 的是成品**。

### Step 3 · Git 版本控制

1. Git 存"快照"还是"差异"？带来什么好处？
   > 概念上是**快照**（每个 commit 是整棵树的快照），底层用 delta 压缩；好处是分支切换/回滚不依赖逐条差异重放。
2. 暂存区存在的意义是什么？`git add -p` 解决什么问题？
   > 让你挑选"这次提交什么"，把一堆改动拆成主题清晰的提交；`-p` 按块挑选，避免无关改动混进同一提交。
3. 已经 `push` 的 `.env`，第一步该做什么？为什么不是先删文件？
   > ⭐ **先吊销/轮换密钥**。密钥已进本地与远端历史，**删文件不删历史**，删了照样是泄露。
4. 为什么 `uv.lock` 要提交，而 `.venv/` 不要？
   > lock 是可复现的"配方"（小、必须）；`.venv/` 是可再生的"成品"（大、平台相关）。

### Step 4 · 项目结构

1. src 布局比扁平布局多解决了什么问题？
   > 强制"安装后才能 import"，**逼你真测打包配置**；同时消除"脚本所在目录碰巧在 `sys.path`"带来的假成功。
2. 为什么要专门留一个 `playground/` 目录？
   > 给一次性验证代码一个**合法去处**，不污染 `src/`；可随时删。
3. 硬编码 `api_key` 和 `base_url` 分别有什么风险？
   > key 会进 Git 历史（泄露）；`base_url` 硬编码 → 换环境（本地/测试/生产）必须改代码。

### Step 5 · pydantic：把"契约"写下来

1. pydantic 的"解析"和"校验"分别指什么？
   > 解析 = 把输入（dict / JSON / 环境变量字符串）转成 Python 对象与正确类型；校验 = 检查是否满足约束（范围/长度/枚举）。
2. `field_validator` 里 `return stripped` 有什么额外好处？
   > 让"清洗后的值"成为**后续所有代码看到的值**，下游不必各自再 strip 一遍。
3. 为什么 `default=[]` 会导致诡异的串数据 bug？怎么修？
   > ⭐ 列表**只创建一次**，所有实例共享同一个对象 → 一个实例改了会影响别人。修：`Field(default_factory=list)`。
4. "校验该放在哪一层"，你的理由是什么？（面试常问的架构题）
   > 放在**系统边界**（入口）：HTTP 请求体、环境变量、上游 API 响应。一次校验，内部代码就可以信任数据。
5. `extra="ignore"` 在本仓库里具体避免了什么问题？
   > `.env` 里有模型没定义的键时被静默丢弃、不报错。
   > ⚠️ 本项目反而选 `forbid` —— 因为要**暴露拼错**（静默失效最难查）。

### Step 6 · 类型注解与 mypy

1. mypy 能查出"列表可能为空"吗？为什么？那这个保证该由谁提供？
   > 不能（它不做"取值可能不存在"的控制流推断）。这个保证该由**运行时的边界校验**（pydantic / 显式判断长度）提供。
2. `Any` 和 `object` 的区别是什么？为什么本仓库用 `dict[str, object]`？
   > `Any` = 放弃检查（任何操作都放行）；`object` = 最宽泛的**确定类型**，用前必须收窄。`dict[str, object]` 表示"值是任意类型，但我必须显式处理"。
3. `warn_unused_ignores` 帮你避免什么问题？
   > 防止 `type: ignore` 过期后一直留着，把后来出现的真错一起吞掉。
4. 为什么"跨越系统边界的数据"要当成敌意输入？
   > 你无法控制对方的格式/内容；可能恶意、也可能版本不一致 —— 必须假设"可能是任何东西"。

### Step 7 · 异步 async/await

1. `async def f()` 定义后直接调用 `f()`，代码会执行吗？会返回什么？
   > **不执行**；返回一个 `coroutine` 对象（并给 `RuntimeWarning: never awaited`）。
2. `await` 的本质作用是什么？
   > ⭐ **让出控制权给事件循环**（"我在等，别人先跑"），不是"阻塞等待"。
3. 并发和并行的区别？`asyncio` 提供的是哪个？
   > 并发 = 交替推进（看起来同时）；并行 = 真同时（多核）。`asyncio` 提供**并发**（单线程）。
4. 在 `async def` 路由里写 `time.sleep(5)` 会发生什么？为什么比写 `def` 路由更糟？
   > 堵死事件循环，所有请求一起卡。写 `def` 时 FastAPI 会丢进**线程池**，反而不会互相堵 → 所以 `async def` + 阻塞**更糟**。
5. `fetch_model_ids` 为什么要把 `client` 当参数传进来？
   > 依赖注入：调用方决定用真的还是假的 → 可替换、可测试。
6. 如果 `messages[-1]` 是 `system` 角色，当前 `echo()` 的行为对吗？怎么改？
   > 不对 —— 会把"人设"当答案回显。应要求最后一条是 `user`，否则报 4xx。
   > 📎 这也是项目**待办 #2**（笔记 §3.6d）。

### Step 8 · 测试

1. 为什么 `ruff` 和 `mypy --strict` 都没抓出那个缩进 bug？这说明了什么？
   > ⭐ 因为那段代码**语法合法**（只是永不执行）。说明工具只能查"能静态判定的错"；**可达性/逻辑问题必须靠"跑一次并读输出"**。
2. `warn_unreachable` 为什么不在 `--strict` 里？
   > 推测：它依赖控制流分析、**误报率较高**（如平台相关的 `sys.platform` 分支），放进 strict 会让严格模式难用。
3. `MockTransport` 能测真网络测不了的哪两类场景？
   > ① 超时/连接错误 ② 各种状态码与畸形响应（500 带 HTML、非法 JSON）—— 真网络很难稳定复现。
4. 覆盖率 100% 能不能保证没 bug？举一个反例。
   > 不能。反例：断言写错（`assert x == x`）、只测正常路径、只测实现细节。
5. 怎么判断一个测试"该不该存在"？
   > 判据：**重构实现（不改行为）后它会不会无故变红** —— 会，说明它测的是实现细节（脆弱测试）。

### Step 9 · lint / format / 类型检查

1. `ruff format` 和 `ruff check` 分别管什么？为什么 CI 里要用 `--check`？
   > format 管**纯排版**；check 管**可疑写法与真 bug**。CI 用 `--check` 是因为 `format` 会改文件且**永远退出码 0**（假绿灯，给不出判定）。
2. 规则集 `B` 解决了什么问题？举一个它抓得到的经典 bug。
   > flake8-bugbear：容易写出 bug 的写法。经典例子：**可变默认参数**（`def f(x=[])`）。
3. 为什么推荐 "format → check → mypy → pytest" 这个顺序？
   > 先修机械问题（避免格式噪音掩盖真问题）→ 再查代码期错误（类型）→ 最后查运行期错误（测试）。**从便宜到贵**。
4. 为什么这些工具都抓不到 Step 8 那个 bug？
   > 同第 1 题：语法合法 → 静态工具无从下手。

### Step 10 · Docker

1. Docker 解决了 venv 解决不了的哪三件事？
   > ① 系统级依赖（libc / 编译工具）② 交付物一致性（镜像 = 代码 + 依赖 + 运行时）③ 环境完全可复现（不依赖本机状态）。
2. 为什么"在容器里手改配置文件"不算方案？
   > 容器重建/重启就丢，且改动不在任何声明里 → **不可复现、不可审计**。
3. Dockerfile 里为什么要"先拷 `pyproject.toml`/`uv.lock`，再拷 `src`"？
   > 利用**层缓存**：依赖没变时跳过重装，只重跑"拷代码"那层 → 构建快很多。
4. `CMD` 为什么推荐 JSON 数组形式？
   > exec 形式**不经 shell**：SIGTERM 能正确传给主进程（优雅退出），参数也不会被 shell 展开。
5. `.dockerignore` 里如果漏了 `.venv/`，会有什么具体后果？
   > 本机 venv（几百 MB、平台相关）被打进镜像 → **镜像体积暴增**，还可能污染容器内解释器。

---

## 阶段 1 · FastAPI（Step 1 ~ 13）

### Step 1 · HTTP 与 ASGI 地基

1. HTTP 为什么被称为"无状态"？那登录状态靠什么维持？
   > 🟡 每个请求独立、服务器不记上一个请求。登录状态只能靠 ① **每次带凭证** ② **服务端把状态存进共享持久层**（DB / Redis）。
   > ⭐ **我答错过**：说"靠 uvicorn 维持"。**错** —— uvicorn 连 `Authorization` 头都不解析（那是应用的事）；进程内存重启就归零、`--workers` 多进程互不可见。
2. 401 和 403 的区别？
   > 401 = 没认证 / 凭证无效；403 = 认证了但**没权限**。
3. 幂等性为什么对支付接口是刚需？
   > 🟡 因为"**响应丢失导致客户端不确定**"：超时后客户端分不清 A. 没收到（该重试）B. 成功了但响应丢了（重试 = 重复下单）。解法是**幂等键**。
   > ⭐ **我答错过**：把"流式中断"当成支付幂等的理由 —— 那是 LLM 重试白花钱的场景。
4. WSGI 和 ASGI 的并发模型区别？为什么 LLM 应用必须选 ASGI？
   > 🟡 WSGI：**一个请求占一个线程/进程**；ASGI：**一个事件循环 + N 个协程**。
   > 两条理由都要说：① 等待不占工人（扛高并发）② `send()` 可多次调用 → 能做流式。
   > ⭐ 别只说"ASGI 更快" —— 单请求跑同样代码**速度一样**；我答时漏了"并发模型"这层。
5. ASGI 的 `send` 能被调用多次，这件事解锁了什么能力？
   > SSE 流式、WebSocket、大文件分块下载。
   > 📎 实测：app 往回了**两条**消息（`http.response.start` + `http.response.body`）。

### Step 2 · 最小应用与自动文档

1. `uvicorn main:app` 里的 `main:app` 分别指什么？
   > `main` = 模块（文件名）；`app` = 模块里的**变量名**。
2. `/docs` 和 `/openapi.json` 的关系是什么？
   > `/docs` 是 HTML + JS 的界面（Swagger UI），它去读 `/openapi.json`（机器可读的接口描述）渲染出来。
3. 为什么 `/users/me` 必须写在 `/users/{user_id}` 前面？
   > 路由**按注册顺序匹配**，先注册的先命中；否则 `"me"` 会被当成 `user_id` 吃掉。
4. 为什么说"自动生成的文档不会过期"这件事对协作特别重要？
   > 文档由**代码注解生成** → 改代码就改文档，从根上消除了"人忘了更新文档"这个失效模式。

### Step 3 · 三段参数：路径 / 查询 / 请求体

1. 说出 FastAPI 判定"参数从哪来"的规则。
   > ⭐ 名字在路径 `{}` 里 → **路径参数**；类型是 **pydantic 模型** → **请求体**；其他 → **查询参数**。
2. `GET /items/abc` 返回什么？为什么不是 500？
   > 422（校验失败）。因为这是**调用方提供了不合法的值** = 4xx；不是服务端崩溃。
3. `limit: int = 10` 和 `limit: int` 有什么区别？
   > 前者可选（不传用 10）；后者**必填**（不传 422）。
4. `Annotated[int, Query(ge=1)]` 比 `Query(default=10, ge=1)` 好在哪三个地方？
   > ⭐ ① 元数据位与默认值位**分开**（函数能直接调用，不会 `TypeError: 'Query' * 'int'`）② mypy 看到的是真 `int` 而不是 `Query` 对象 ③ 是 **PEP 593 标准**，多方工具可共用同一个注解位。
   > 📎 实测：老写法直接调用会崩，新写法正常；两者生成的 OpenAPI 一样。

### Step 4 · pydantic 契约与 `response_model`

1. `loc` 字段为什么能精确到"第几条消息的哪个字段"？
   > 校验是**递归**的：嵌套模型逐层带上路径（实测 `["body","messages",0,"role"]`）。
2. 422 响应体的 `input` 字段有什么风险？
   > ⭐ 它**回显你提交的原始值** —— 含密码/密钥就会进日志（与 pydantic 报错回显同一类风险）。
3. **不写 `response_model` 有什么安全风险？**（面试题）
   > ⭐ 返回对象上的**多余字段会被原样输出**（实测：多一个 `secret` 字段就泄漏了）。
4. 204 状态码为什么不能有响应体？
   > HTTP 规范定义 204 = No Content；带 body 会让部分客户端/代理行为异常。
5. 你会给"用户"设计几个 pydantic 模型？分别为什么？
   > 至少三个：`UserCreate`（含密码，入参）/ `UserPublic`（响应，**不含**密码）/ `UserInDB`（含哈希）。
   > 理由：**不同场景暴露不同字段**，避免敏感字段外泄 + 入参约束被误用到出参。
6. `response_model=` 和返回注解 `-> Resp` 同时写、且内容不同时，**文档**和**过滤**分别按哪个？
   > 都按 **`response_model`**（📎 实测：OpenAPI 里指向 `Resp`；返回 `WideResp` 时多出的 `debug` 被剥掉）。两者相同时只写返回注解即可 —— 写了是**同一件事写两遍**。
7. 返回的对象**缺少** `response_model` 里的必填字段会怎样？为什么不是 500 以外的码？
   > 📎 **500**（`ResponseValidationError: {'type':'missing','loc':('response','items')}`）。因为错在"我要发出去的响应不符合我自己声明的形状" = **我方 bug**，客户端无从修改；422 是"请求不合法"，语义不同。
8. `list[dict]` 和 `list[ModelItem]` 作响应类型差在哪？
   > 📎 三层差异：① `/docs` 里 `list[dict]` 显示成 `{"additionalProperties": true}`（= `[{}]`，展开不出字段）② 业务函数失去类型信息（mypy 帮不上）③ **过滤会晚一步**（`response_model` 仍能过滤，实测 `secret` 被剥），但失败点更靠后、更难定位。
9. 上游某条记录缺 `id` 时，接口返回什么？为什么不是 422/502？
   > 📎 **500**。不是 422（客户端改不了上游数据），也不是 502（上游正常回了 200，是我们的解析假设崩了）→ 落 `Exception` 兜底 + `request_id`，堆栈进日志。**取舍**：想"跳过坏记录保可用"就 `try/except ValidationError` 逐条跳过 + 打日志，但必须接受静默丢数据。
10. 同一个 `total` 字段，为什么由我们算而不是直接取上游条数？
    > `total` 是**业务语义**（本次查询命中总数），`len(上游响应)` 是运输细节。现在无过滤所以相等（巧合）；加 `?prefix=` 或分页后就不等。分页时 `total` ≠ `len(items)`。

### Step 5 · 依赖注入 `Depends`

1. `Depends` 相比"函数里自己 new"，收益有哪四条？
   > ① 可替换（测试注入假对象）② 可复用（声明一次处处用）③ 依赖关系显式（签名即文档）④ 生命周期由框架管（`yield` 的 setup/teardown）。
2. `yield` 依赖里 `yield` 之后的代码什么时候执行？抛异常时呢？
   > ⭐ 路由执行**结束之后**。异常时**只有包在 `async with` / `try-finally` 里的清理会执行**；裸语句会被**跳过**。
   > 📎 实测：`await client.aclose()` 写在 `yield` 后 → 异常时 `is_closed=False`（**连接泄漏**）。
3. 同一次请求里请求同一个依赖两次，会执行几次？这个设计的理由？
   > **一次**（依赖缓存，`use_cache=True`）。理由：避免一次请求重复查库/验签。
   > 📎 实测：同一路由两个参数、或两个嵌套依赖 —— 都是调用 1 次、同一个对象。
4. `dependency_overrides` 用完后必须做什么？不做会怎样？
   > ⭐ `clear()`。它是**挂在 app 上的全局字典**（寿命 = 进程），不清理会污染后续测试 → 症状是"**单独跑过、一起跑挂**"。
5. `Annotated[X, Depends(f)]` 比 `x: X = Depends(f)` 好在哪？
   > 元数据位与默认值位分离：类型对 mypy 仍是 `X`、函数可直接调用、不会被误当请求体。
6. ⭐ 📎 **补充实测（本会话新增）**：路由**声明了依赖但函数体完全不用它**，依赖会执行吗？
   > **会**（实测调用 1 次）。所以"挂一个用不到的依赖"是有成本的 —— 写前先自问"这个路由真的需要吗"。
7. ⭐ 📎 **补充**：`dependency_overrides` 能让**不同的并发请求**拿到不同配置吗？
   > **不能** —— 它是全局表，只能"整场测试换成假的"。要按请求区分，得让**替身自己读 `Request`**。
8. ⭐ **补充**：给依赖参数加 `= None` 会怎样？
   > **依赖照常执行，`None` 被完全忽略**（用"覆盖成会抛异常的依赖"判定）；mypy 另外报 `assignment` 错。
9. ⭐ **补充（1.4d-1）**：把 `create_llm_client()` 抽出来后，加一个"重试 3 次"的配置要改几个文件？重构前是几个？
   > **1 个**（只改 `llm_client.py`）；重构前要改 **2 个**（`deps.py` + `main.py`）。
   > ⭐ 抽共用模块的真实收益 = **改动点从 N 个变成 1 个**，不是"代码变短"。
10. ⭐ **补充（1.4d-1）**：为什么 `create_llm_client()` 只 `return`、不写成 `yield`？
   > 因为两个使用者的**关闭责任不同**：`main.py`（CLI）自己 `async with` 关；`deps.py`（服务）由框架关。
   > 工厂只回答"**怎么造**"，不回答"**谁关**" —— 一个函数只做一件事。
11. ⭐ **补充（1.4d-1）**：重构的验收标准是什么？为什么三条质量门全绿还不够？
   > 标准是**行为不变**。`ruff`/`mypy` 只能证明"代码合法、类型自洽"，
   > **证明不了"你没把 `timeout=30` 改成 `timeout=3`"** → 必须跑一次并把输出与重构前逐字对比。
12. ⭐ **补充（1.4d-1）**：`create_llm_client()` 为什么放 `src/app/` 而不是 `src/app/api/`？
   > 因为 `main.py`（组合层）也要用它；若放 `api/` 就变成 **`main.py` → `api/` 的反向依赖**，违反规范 §8.1 的分层方向。
13. ⭐ **补充（1.4d-2）**：`/v1/models` 和 `/v1/upstream/models` 返回内容看起来一样，本质区别是什么？
   > `/v1/models` 返回**硬编码**的 `KNOWN_MODELS`（改配置不会变）；`/v1/upstream/models` **真的去问了上游**。
   > ⭐ 只有后者能反映"**上游此刻真的可用**"—— 前者在断网、密钥失效时照样 200。
14. ⭐ **补充（1.4d-2）**：上游返回 401 时，`/v1/upstream/models` 会返回什么？为什么**不是** 401？
   > 会返回 **500**。因为 `raise_for_status()` 抛的是 `httpx.HTTPStatusError`，不是 `HTTPException`，
   > FastAPI 当**未捕获异常**处理。正确做法：转 **502 Bad Gateway**（上游的问题），并区分 4xx/5xx（待办 #6，Step 6）。
15. ⭐ **补充（1.4d-2）**：`fetch_upstream_models(client)` 测试时怎么不联网？
   > 它接收 `client` 参数 → 传一个用 **`httpx.MockTransport`** 造的假 client 即可，
   > 或对路由测试时用 `app.dependency_overrides[get_llm_client] = 假 client`。
   > ⭐ 这正是"把 client 做成参数"的可测试性收益。

### Step 6 · 错误处理与 `lifespan`

1. `HTTPException` 和自定义异常分别适合哪一层？
   > `HTTPException` 适合**路由层**（直接对应状态码）；自定义领域异常适合 **service 层**（业务语义），再由异常处理器翻译成 HTTP 状态码。
2. 为什么 500 不能回显堆栈？正确的排查方式是什么？
   > ⭐ 会泄露路径/依赖/内部结构（给攻击者地图）。正确：**服务端记日志**（含 traceback + 请求 id），返回给客户端一个 id 让它来报。
3. `lifespan` 的 `yield` 里返回的 dict 有什么用？
   > 它会**并入每个请求的 `request.state`**（📎 2026-10-17 实测：`request.state.store_version` 拿得到，`request.app.state.store_version` 拿不到），请求里用 `request.state.xxx` 取。适合放"启动时算一次、每次请求都要读"的东西（全局 client、连接池句柄）。⚠️ 本答案原写成"`request.app.state` 取到"，是错的，已订正。
4. 为什么"在模块顶层加载模型"是反模式？
   > **导入时就执行** → 测试/CLI 一 `import` 就付出代价（慢、可能要网络），且无法在测试里替换。
5. `on_event` 现在还能用吗？该换成什么？
   > 已废弃，换成 **`lifespan`**。
6. `status.HTTP_404_NOT_FOUND` 和 `404` 有什么区别？为什么用前者？
   > 前者只是后者的**常量别名**（实测 `type` 是 `int`，来源 `starlette.status`）。收益是**可读**与**拼错立刻炸**（`AttributeError`）；直接写 `404` 则写错数字什么都不发生。⚠️ 本版本**没有** `status.HTTPStatus`，照抄老教程会报错。
7. 把路径参数写成 `Literal["a","b"]` 代替手写判断，会有什么问题？
   > 📎 实测返回 **422**（`literal_error`）而不是 404，且**把允许的全部取值写进报错**；语义上"格式没问题、资源不存在"应该是 404。另：清单成为第二份真相，随数据源变化要改两处。
8. `return HTTPException(...)` 和 `raise HTTPException(...)` 结果差在哪？
   > 📎 实测：`raise` → 走异常通道 → 404；`return` → 当普通值序列化 → 有返回注解时 **500**（`ResponseValidationError`），**没注解时 200 + `{"status_code":404,...}`**（谎报成功）。判据：**异常对象只有 `raise` 才有意义**。
9. 上游返回 401 时，我们的客户端应该收到 4xx 还是 502？为什么？
   > **502**。上游 401 的语义是"**你的服务器**对我没通过认证"，与调用者无关。透传会让客户端以为"我要登录"（📎 实测透传后客户端收到 401）→ 弹登录框 / 清 token，全是无效动作。502 = 网关访问上游失败，语义准确，且对外只暴露一种契约。
10. `httpx.ConnectError` 属于哪一支？能拿 `.response` 吗？
    > 属于 **`RequestError`**（→ `TransportError` → `NetworkError`）；**没有** `.response`（`hasattr` 实测 `False`）。所以这类分支的 `detail` 只能写"连不上"，不能读上游状态码。
11. 我们自己的业务 bug（如 `payload["datas"]` 拼错）会进哪个 `except` 分支？应该进吗？
    > 📎 都不进 → **500**。**应该**：500 = "我方出错"，正是事实。若被 502 吃掉，监控分不出"依赖挂"和"我写错"，排查会跑去查上游。判据：**`except` 抓得越窄，"谁的错"记得越准**；`except Exception` 统一转 502 = 放弃这个能力。
12. `messages` 只有一条 `assistant` 消息时，`/v1/chat` 返回什么？合理吗？
    > 返回 **400**（`最后一条消息必须是 user，当前是 assistant`）。对"问答"语义是合理的保守选择；若将来要做"续写 / assistant 预填"，就要显式放开这条规则。
13. 把规则改成"往前找最近一条 `user`"有什么取舍？
    > 优点：容忍尾部的 `assistant`（多轮里客户端常把整段历史发回来）。缺点：**意图变模糊**（是"继续生成"还是"重发"？），且整段历史没有 `user` 时仍要 400。工程判断：先用"必须 user"（明确、可测），有真实产品需求再放开。
14. `detail` 里回显 `last.role` 有风险吗？换成 `last.content` 呢？
    > `role` 是 `Literal` 三值之一 → 有界枚举，**安全**。`content` 是用户自由文本 → 超长撑爆响应/日志、换行可造成**日志注入** → 要截断/转义，或只回显长度或 ID。
15. 抛一个没在 `_STATUS_BY_CODE` 里登记的 `code` 会怎样？这个兜底合理吗？
    > 落到默认 **400**（`.get(key, 默认值)`）。合理，但它是"**防崩溃**"不是"正确"—— 它会**掩盖漏登记**。推荐组合：保留 400 兜底 + 把 `code` 限定成 `Literal`/`Enum`，让 **mypy 当场抓错**。
16. `register_exception_handlers(app)` 忘了调用，客户端看到什么？为什么？
    > **500**。`_lookup_exception_handler` 沿 `type(exc).__mro__` 查表，查不到返回 `None` → 框架默认 500（实测用"实例当键"复现了同一机制）。⚠️ 它**不报错不警告**，属静默失效 → 用 `assert AppError in app.exception_handlers` 或一条必触发 `AppError` 的测试兜住。
17. 现在 400 是 `{"error":{...}}`、404 是 `{"detail":"..."}`、422 是 `{"detail":[...]}` —— 算设计缺陷吗？
    > 算**一致性问题**。判据：**错误响应的形状应当让客户端只写一份解析代码**，现在要写三份。但"现在该不该改"要看：有没有真实客户端、有没有文档契约、迁移成本。收口方式：给 `HTTPException` 与 `RequestValidationError` 各注册处理器统一形状。
18. `HTTPException` 会被注册在 `Exception` 上的兜底处理器吃掉吗？
    > **不会**。① `app.exception_handlers` 里本来就有 `HTTPException` 的内置处理器 ② 查找沿 `type(exc).__mro__` **从子到父**，`HTTPException` 排在 `Exception` 前 → 先命中。📎 实测 `HTTPException(418)` → `418 {"detail":"我是茶壶"}`。⚠️ 前提：别删内置处理器。
19. 用户只给一个 `request_id`，你怎么找日志？多机部署还要补什么？
    > 单机：在日志里搜这个 ID（`Select-String ... -Pattern <id>`）。多机补三样：① **集中收集**（Loki/ELK/云日志）② **`trace_id`**（W3C `traceparent`）打通跨服务 ③ **结构化日志**（JSON + 固定字段）。判据：`request_id` 解决"一台机器内"，`trace_id` 解决"跨服务"。
20. 如果 500 兜底处理器**自己**抛异常，会发生什么？
    > 📎 实测：客户端拿到 **500 + 空 body + 无 content-type**（uvicorn 的原始错误页）—— 因为它是最后一道网，没有更外层接住。所以它里面**只做**三件事：记日志、拼 JSON、返回；且其中不能有会抛异常的代码。
21. `lifespan` 与 `yield` 依赖的本质区别是什么？（说"谁调用、谁清理"，不要只说应用级/请求级）
    > `yield` 依赖：**框架在每次请求**进入时调用、请求结束时把控制权交回生成器继续执行清理 —— 创建/清理都绑在**请求**上。`lifespan`：**uvicorn 在进程启动时**进入、关闭时继续执行 —— 创建/清理绑在**进程**上，全应用共享。判据：**看"谁的生命周期决定它该活多久"**。
22. `app.state.llm_client` 在测试里怎么替换？比 `dependency_overrides` 麻烦在哪？
    > 需要 `with TestClient(app) as tc:` 触发 lifespan 后 `tc.app.state.llm_client = fake`（或直接 `app.state.llm_client = fake`）。麻烦在哪：① lifespan 必须真的跑过，否则 state 里没这个属性（不用 `with` 会拿到旧/已关闭对象）② 它是**全局可变状态**，用例之间会互相污染，必须手工还原 ③ 不如 `dependency_overrides` 那样能对 `get_llm_client` 这个"接缝"做精确替换。⭐ 所以：**共享资源放 lifespan，但"取用"仍走依赖** —— 两者配合才有可测性。
23. 一个 client 被 100 个并发请求同时使用，会不会出问题？
    > 不会。`httpx.AsyncClient` 内部维护**连接池**，并发请求各自取连接、用完归还；2026-10-16 实测并发 20 请求全 200。要注意的是**连接池上限**（`limits=httpx.Limits(max_connections=...)`），并发很高时排队而非报错。

### Step 7 · 中间件与 CORS

1. 中间件的"洋葱模型"里，注册顺序和执行顺序是什么关系？
   > **后注册的在最外层、最先接触请求**；响应时反过来（📎 2026-10-19 实测：先注册 A、后注册 B → 进入 **B→A→路由**，退出 **A→B**）。源码：`user_middleware.insert(0, ...)` 插列表头部 + `for cls in reversed(middleware): app = cls(app)`。
2. 为什么"记日志的中间件"会让 SSE 流式失效？
   > 中间件通常要**读完整响应体**才能记日志 → 它会把流式响应**全部缓冲**起来再发，等于没有流式。📎 补充：`await call_next(request)` 返回的是 `_StreamingResponse`，**body 还没被读**；读 `response.body` 才会抽干。实测 3 块 × 50ms 的流式接口，中间件记到的耗时只有 **1.9ms**（真实 ~150ms）。
2b. `await call_next(request)` 到底做了什么？里层抛异常时它返回什么？
   > 后台跑内层 app，等第一条 `http.response.start`（状态码 + 头就绪）后返回 `_StreamingResponse(content=body_stream())`。里层抛异常时它**原样上抛**，不返回响应 → 500 由更外层的 `Exception` 处理器生成（不会再回到中间件），所以 `finally` 里的 `response` 可能从未赋值。
3. `app.state` 与 `request.state` 的区别？各自适合放什么？
   > `app.state` 挂在整个**进程**上（所有请求共享）：共享 client / 连接池 / 配置。`request.state` 存在这次请求的 `scope["state"]` 里（只活一次请求）：`request_id` / 当前用户 / 租户。📎 中间件里 `request.state.x = ...` 之后，**异常处理器里读得到**（同一个 scope），这是 500 能复用同一个 ID 的原因。
4. 为什么 500 响应头里的 `X-Request-ID` 必须由**处理器**加，而不是中间件加？
   > 因为 `Exception` 处理器挂在 `ServerErrorMiddleware` 上，位置在**中间件外面**：里层抛异常时 `call_next` 把异常上抛，中间件拿不到响应对象；500 是处理器**新建**的响应，不会再回到中间件。⭐ 判据：**正常响应由中间件补头，异常响应由处理器补头**。
5. 验证一个中间件，只看响应够吗？应该看哪几处？
   > 📎 不够，必须"**四看**"：① 响应头 ② 响应体 ③ **服务端日志（每个请求都有，含失败的）** ④ **traceback 里是原始异常**。本轮实测：前两条全过，但日志 0 条、traceback 是 `UnboundLocalError` —— 只看响应就是**假通过**。
6. HTTP 头名里，哪些字符差异**有语义**、哪些**没有**？
   > 📎 实测：**大小写不敏感**（Starlette 把 `X-Request-ID` 与 `x-request-id` 视作同一个头）；**`-` 与 `_` 是两个不同的头**（`X-Request-ID` ≠ `X-Request_ID`）。
7. 为什么要把 `X-Request-ID` 抽成常量？它防不住什么？
   > 防的是"**多处写同一个字面量，改一处漏一处**"以及"某处拼错、三个工具都查不出来"。**防不住"常量本身一开始就写错"** —— 所以第一次定义时仍要对着 RFC/文档核验。
8. 常量该放哪一层？判据是什么？
   > 判据两条：① **「谁 import 谁」** —— 被下层模块（如 `app/errors.py`）使用就必须放上层（`src/app/`），否则下层反向 import 上层、破坏分层 ② **「改一处会不会漏另一处」** —— 只有会漏的才需要抽（只在一个函数里用的路径字符串不必抽）。
9. 中间件里访问日志为什么要写在 `finally` 里？写在别处会怎样？
   > 📎 三种写法实测：写在 `try` 之后 → 异常时**跳过**；写在 `except` 里 → 正常时跳过；写在 **`finally`** → 两条路径都覆盖。访问日志恰恰**最需要失败请求那一条**。
10. 为什么用 `logger.warning` 而不是 `logger.info`？这是长期方案吗？
   > 因为默认 root 级别 = `WARNING`，`.info` 会被静默丢弃。这是**临时手段**（待办 #7）：Step 11 配好日志级别与格式后应降级为 `.info`。⭐ 判据：**日志级别描述"重要性"，不是"有没有出错"**；正常访问日志属于 INFO。另：`logger.warning` 只是写一条日志记录，**不是抛警告**。
11. `log.info(...)` 被"静默丢弃"是什么意思？它要过哪三道闸？
   > 📎 "静默" = **不报错、不输出、调用照常返回**。三道闸：① logger 的**有效级别**（未设则向上找 root，默认 WARNING）② 每个 handler 的级别 ③ 有没有 handler（没有则用 `lastResort`，只处理 WARNING+ 且无格式）。实测：即使装了 DEBUG 级 handler，只要 root 还是 WARNING，`isEnabledFor(INFO)` 仍为 `False` —— **闸 1 就拦下了**。
12. 500 请求的**访问日志**为什么也用 INFO，而不是 WARNING？失败信息在哪？
   > 一条日志 = 一个事件。访问日志记的是"**有一个请求被服务了**（结果 500）"，属 INFO；"**代码崩了**"由处理器的 `logger.exception` 以 **ERROR** 记录（含堆栈）。若把 4xx/5xx 升成 WARNING：① 扫描器打的 404 会刷屏淹没真 warning ② 想关访问日志就得连真 WARNING 一起关 ③ 同一次 500 两处报警要去重。⭐ **报警靠指标（5xx 比例、P99），不靠日志级别**；唯一值得额外 WARNING 的是 **502（上游故障）**。
3. CORS 是浏览器的限制还是服务器的？为什么 `curl` 测不出来？
   > ⭐ 是**浏览器**的安全策略（同源策略）。`curl` 不受同源策略约束 → 永远不报 CORS 错。
4. 什么样的请求会触发预检？为什么 LLM 应用几乎必然触发？
   > 非简单请求（自定义头如 `Authorization`、`Content-Type: application/json`、非 GET/POST）。聊天接口必带 Authorization 或 JSON → **必然预检**。
5. `allow_origins=["*"]` + `allow_credentials=True` 会怎样？
   > ⚠️ **旧答案已订正**（2026-10-19 实测）：**不会被浏览器拒绝**。Starlette 会**回显具体 Origin**（`cors.py:163`）来满足规范。所以风险是**静默全放开** —— 任何网站都能带用户 Cookie 调你的接口。⭐ 判据：**报错你能发现，安全漏洞发现不了**。
6. 非白名单来源时，服务器状态码是多少？谁在拦？
   > 📎 **200**，数据照发（`{"status":"ok"}`），只是**没有 `Access-Control-Allow-Origin` 头**。拦人的是**浏览器**：它检查这个头的值是否等于当前页面来源。
7. `Access-Control-Allow-Origin` 为什么是"回显请求里的 Origin"，而不是写死？
   > 浏览器要求这个值**必须等于**当前页面来源（或 `*`）；服务器不知道页面来源，只能照抄。配套的 `Vary: Origin` 告诉 CDN "这个响应随 Origin 变，别串缓存"。
8. 预检失败时状态码是什么？预检能打到不存在的路径上吗？
   > 📎 失败是 **400**（`Disallowed CORS method` / `Disallowed CORS headers`），不是 403/405。能 —— 实测 `OPTIONS /nope` 返回 **200 OK**，因为 `CORSMiddleware` 在**路由之前**就答掉了（`cors.py:86~91`）。

### Step 8 · 异步的正确姿势

1. `def` 路由和 `async def` 路由，FastAPI 分别怎么执行？哪个更怕阻塞代码？
   > `def` 被丢进**线程池**（默认上限约 40），阻塞只占一个线程；`async def` 直接在事件循环里跑，阻塞会**堵死整个循环** → **`async def` 更怕阻塞**。
2. anyio 默认线程池上限是多少？这带来什么限制？
   > 约 **40**。限制：同时超过 40 个阻塞型 `def` 请求会排队。
3. 只有同步库可用时，三种处理方式分别适合什么场景？
   > ① 直接写成 `def` 路由（简单，交给线程池）② `await anyio.to_thread.run_sync(...)` ③ 进程池 / 消息队列（CPU 密集）。
4. `for` 循环里 `await` 有什么问题？怎么改？改完要注意什么风险？
   > 串行等待（n 次等待叠加）。改 `asyncio.gather` **并发**。风险：并发太高会打爆上游/本地连接数 → 需要限制并发（信号量）。
5. `async def` 路由里调 `requests.get()` 会怎样？为什么比写成 `def` 更糟？
   > 两种都阻塞，但**影响面差 40 倍**：`async def` 卡住**整个事件循环**（所有请求排队）；`def` 只占线程池里的 **1 个线程**。📎 实测（1 慢 + 5 快并发）：阻塞写法把快请求从 **13ms 拖到 325ms（25 倍）**，而 `def` 写法的快请求仍是 13ms。⭐ 判据：**`async def` 是对框架的承诺**——承诺"这里不阻塞"，做不到代价比一开始写 `def` 大得多。
6. `anyio` 线程池超限时会**拒绝**还是**排队**？为什么这更危险？
   > 📎 **排队**。实测 45 个并发（每个 0.4s）= **0.87s**（40 个第一批 + 5 个第二批），全部 200。危险在于**没有错误、没有告警，只有延迟悄悄翻倍** → 监控要看 P99/排队时长，不能只看错误率。
7. `model.encode()`（CPU 密集 2 秒）该怎么部署？为什么 `run_in_threadpool` 只是"缓解"？
   > 📎 实测 GIL：4 个 CPU 任务**线程池并发 0.43s vs 串行 0.41s = 0.96x**（没有加速）；**进程池 0.33s = 1.28x**（受核数限制）。因为 CPU 密集不释放 GIL，线程只能轮流跑。⭐ 部署首选 **独立推理服务**或**任务队列**；`run_in_threadpool` 只保证"不卡事件循环"。⚠️ Windows 上 `ProcessPoolExecutor` 子进程会**重新 import `__main__`**，必须用 `if __name__ == "__main__":` 保护。

### Step 9 · SSE 流式响应

1. TTFT 和总耗时分别是什么？流式优化的是哪个？为什么这等于"免费提速"？
   > TTFT = 首字节时间；总耗时 = 全部完成。流式优化 **TTFT**（观感"立刻开始"），**总耗时不变** —— 所以是"免费"的体验提升。
2. SSE 一帧的格式是什么？为什么必须有两个换行？
   > `data: <内容>` + **空行**。空行是"这一帧结束"的分隔符。
3. **流已经开始后报错，能不能返回 500？正确做法是什么？**
   > ⭐ **不能**（状态码和头已经发出去了）。正确做法：发一个**数据帧**说明出错（如 `event: error`），然后正常结束流。
4. 客户端断开时，为什么必须处理？不处理的实际损失是什么？
   > 不处理就继续白烧 **token 和上游调用**（用户已经走了）→ 损失 = 钱 + 上游配额。
5. `X-Accel-Buffering: no` 是给谁看的？
   > 给 **nginx 等反向代理**看 —— 让它不要缓冲响应（否则流式被代理攒住）。
6. 为什么 LLM 聊天用 `fetch` 而不是 `EventSource`？
   > `EventSource` 只支持 GET（不能带 JSON body）、不能自定义头（不能带 `Authorization`）。`fetch` + `ReadableStream` 可以 POST + 自定义头。
7. `curl -w` 的 `time_starttransfer` 与 `time_total` 分别量什么？为什么这两个数的比值能证明流式？
   > 📎 `time_starttransfer` = 从发出请求到**收到响应第一个字节（含响应头）**；`time_total` = 到**连接关闭**。9a 实测 `ttfb=0.014s / total=1.850s`。
   > 🔴 **2026-10-20 订正**：这个比值**只有在"响应头之后立刻来第一帧"时才能证明流式**。`time_starttransfer` 包含响应头，所以**头一发出去它就返回了**。📎 控制实验（端口 8002）：路由立刻返回 `StreamingResponse`、生成器 `sleep(2)` 后才 yield 第一帧 → `curl -w` 报 `ttfb=0.0198s / total=2.0231s`（比值 1:102，"看着完美"），但逐帧时间戳显示**第一帧在 2067ms**。⭐ **正确做法：用带时间戳的客户端（httpx `iter_text()` + `perf_counter`）量"首个数据帧时刻 / 总耗时"。**
8. 响应头里哪个字段是"能流式"的必要条件？
   > `transfer-encoding: chunked`。有 `Content-Length` 就意味着长度已知、不需要边算边发；`StreamingResponse` 因长度未知自动用 chunked（📎 实测存在）。
9. 用 `TestClient` 能证明"真的在分批发"吗？
   > 📎 **不能**。实测 `transfer-encoding: None`（内存里直接给了完整 body）。它只能验证**帧格式**（10 帧、首帧 `data: {"delta": "你"}`、末帧 `data: [DONE]`）；证明"分批"必须用**真实 uvicorn + `curl -w`**。
10. 流开始后生成器抛异常，客户端实际看到什么？
    > 📎 实测：`status=200`（已发出）→ 收到已发出的帧 → 然后 `RemoteProtocolError: peer closed connection without sending complete message body (incomplete chunked ...)`。⭐ 前端**看不出这是业务错误**，只看到协议层断连 —— 所以"把错误编码进流里"是**唯一做法**，不是最佳实践。
11. 异步生成器里把 `await asyncio.sleep(0.2)` 换成 `time.sleep(0.2)`，流会不会变成"攒完再一次性发"？怎么证明？
    > 📎 **不会**。实测单请求两版都在流：`time.sleep` 版 `ttfb=0.023s / total=1.026s`，`asyncio.sleep` 版 `0.006/1.013` —— 每帧 yield 后照样单独成 chunk。**真正的差别在并发**：先让 `/sync_sleep` 占住事件循环，再打另一个请求，`ttfb` 从 **`0.003s` → `0.753s`**；换成异步版占住则探测请求 `ttfb` 仍 `0.003s`。⭐ 判据：**"能不能流"看 TTFB/total；"有没有害别人"看旁边那个请求的 TTFB**。
12. `yield` 和 `return` 的本质区别是什么？函数执行到 `yield` 之后，局部变量还活着吗？
    > `return` **结束**函数、销毁帧；`yield` **冻结**函数。📎 实测 `inspect.getgeneratorstate`：`GEN_CREATED → GEN_SUSPENDED（冻在 yield）⇄ → GEN_CLOSED`；暂停期间 `gi_frame.f_locals` 仍有 `{'n': 3, 'i': 1}`，走完后 `gi_frame is None`。⭐ 所以生成器"调一次得 N 个结果"，且**只能走一次**（同一对象二次遍历得 `[]`）。
13. 为什么 9a 里 `event_source` 必须是 `async def` + `yield`？（三种写法各错在哪）
    > 📎 实测两条 `SyntaxError`：`await` 写在 `def` 里 → `'await' outside async function`。推导：① 要给 `await asyncio.sleep` 让出控制权 → 外层必须 `async def` ② 要每算一段就交出去 → 必须 `yield` ③ 所以只能是异步生成器。只写 `async def` 无 `yield` → 得到**协程对象**（没有 `__aiter__`）；只写 `def`+`yield` → 里面不能 `await`。
14. 如果直接 `StreamingResponse("你好ABC")` 传一个字符串，会怎样？
    > 📎 **不报错，只是"按字符发"**：用假 `send` 抓到 **6 次** `http.response.body`（每个字符一个 chunk + 收尾的空 chunk）。因为 `starlette/responses.py:239` 对非 `AsyncIterable` 走 `iterate_in_threadpool`。⚠️ 而且 str 早就整串在内存里 —— **发送切碎了，但不是"边算边发"**。
15. 谁在"驱动"生成器产出下一帧？这句话为什么重要？
    > `StreamingResponse.stream_response` 里的 `async for chunk in self.body_iterator:`（`starlette/responses.py:253`），每拿到一帧立刻 `await send(..., "more_body": True)`，最后补 `more_body=False`。⭐ 重要性：流式是**拉模式**（框架一帧一帧地要），不是生成器主动推 —— 所以"每 `yield` 一次 = 一次 `send` = 一个 chunk"，算得慢就发得慢。
16. `event_source()` 能不能写成模块级 `SHARED = event_source()` 然后每个请求都用它？
    > ❌ 不能。📎 实测同一个生成器对象二次遍历得到 `[]`；模拟模块级共享 → **请求 1 拿到 `[0,1,2]`，请求 2 拿到 `[]`**（用户看到空回答）。必须在**请求处理函数体内**调用，每个请求新建一个。
17. `f"data: {payload}\n\n"` 里的 `f` 前缀做了什么？去掉会怎样？
    > `f` 让 `{}` 变成**插槽**（运行期替换成变量的值）。📎 实测：有 `f` → `'data: {"delta": "你"}\n\n'`；**去掉 `f` → `'data: {payload}\n\n'`（大括号原样输出）**。等价写法是 `"data: " + payload + "\n\n"`。⚠️ 想输出真的大括号要双写 `{{}}`；`f"data: {}"` 直接 `SyntaxError`；`f"名字={'name'}"` 输出的是字面量 `name` 而不是变量的值。
18. `"data: [DONE]\n\n"` 为什么**没有** `f` 前缀？`\n\n` 里两个换行分别有什么用？
    > 因为里面**没有 `{}` 插槽**，加 `f` 输出完全一样（📎 实测 repr 相同），只是多余噪声（`ruff` 的 `F541` 会提示）。`\n` 是**一个真实的换行字符**（`"A\nB"` 长度是 **3**，`r"A\nB"` 长度是 4）；`\n\n` 中的第二个换行构成**空行 = 帧结束符**。📎 用 `split("\n\n")` 解析验证：两帧各带 `\n\n` → **3 个事件**；全部只写一个 `\n` → **只剩 1 个事件**（内容还是 `[DONE]`），前端表现为"一个字都没收到"，且**不报错**。
19. 「一帧」是时间单位还是数据单位？帧数和总耗时是什么关系？
    > 帧是**数据边界**（由 `\n\n` 切出），不是时间单位。📎 实测三组同一句话：每字一帧 + `sleep(0.2)` → 10 帧 / **1.861s**；**整句只 1 帧** + 两次 sleep → 2 帧 / **0.383s**；**200 帧完全不 sleep** → 201 帧 / **0.002s**。⭐ **帧数多 ≠ 慢**，`\n\n` 管"帧在哪结束"，`await` 管"下一帧何时到"。
20. 假数据为什么要手动 `sleep(0.2)`？接真实上游后还要不要？
    > 因为 `json.dumps("你")` 是微秒级的，9 个字 1ms 内全算完 → 帧还是 10 个，但全挤在同一毫秒到达，**肉眼/curl 验证不了"边算边发"**（📎 无 sleep 版带时间戳测得 9 帧全落在 `67.7ms`）。`sleep` 是**替身演员**，扮演"上游模型吐一个字要 200ms"。📎 实测只转发一个"每 0.15s 才产出一块"的假上游、`event_source` 里**一行 sleep 都没有**：帧到达为 `233.8 / 387.3 / 543.7 / 699.9ms`，总耗时 `0.640s`。⭐ **真实上游自带延迟 → 9b 要把这个 sleep 删掉**。
21. 流式输出不是异步生成器就干完了吗？`StreamingResponse` 到底干了什么？
    > **生成器一行网络代码都没有。** 📎 实测同一个 `event_source` 三种用法全跑通：交给 `StreamingResponse` → HTTP 流；`[f async for f in ...]` → 普通 list；`async for ... print` → 终端文字。`StreamingResponse` 的活：① 发 `http.response.start`（状态码+头）② 自动补 `charset=utf-8` ③ `async for` **驱动生成器**（📎 不驱动时造出对象等 0.5s 函数体一行没跑）④ 每帧 `send(more_body=True)` 并自动 `.encode()` ⑤ 最后补 `more_body=False` ⑥ 监听 `http.disconnect` 取消任务。⭐ 判据：**生成器管产出，`StreamingResponse` 管上网。**
22. 不用 `StreamingResponse`，手写 ASGI 能不能流？要自己写哪几段？
    > 能。📎 实测（端口 8095）三段样板：① `send({"type":"http.response.start","status":200,"headers":[...]})` ② `async for frame in event_source(): await send({"type":"http.response.body","body":frame.encode(),"more_body":True})` ③ 最后补 `more_body=False`。结果 `content-type: text/event-stream; charset=utf-8` + `transfer-encoding: chunked`，`ttfb=0.012 / total=0.416` 照样逐帧。⭐ `StreamingResponse` = 这段样板的封装，还多管了"客户端断开"。
23. `event_source` 里第二个 `yield "data: [DONE]\n\n"` 没在 `for` 循环里，它会不会"只暂停、不推进"？
    > 会推进。推进机制是**外部的 `__anext__` 调用**，`for` 只是它的语法糖。📎 逐次唤醒实测：第 4 次 `__anext__` 时日志打出 `[4] for 循环结束，走到 yield 'DONE' 这一行` → 拿到 `'DONE'`；**第 5 次**唤醒时打出 `[5] 被唤醒：从 'yield DONE' 的下一行继续 → 函数体结束` → `StopAsyncIteration`。⭐ 判据：**`yield` 被推进几次与它在不在循环里无关**；循环内每轮 1 帧，循环外（只写一次）**恰好 1 帧**。`StopAsyncIteration` 是正常结束信号，不是错误。
24. 我的 `app.py` 里既没有 `async for` 也没有 `next()`，那到底是谁在推进 `event_source` 的 `yield`？在哪个文件哪一行？
    > 在 **`starlette/responses.py:253`**：`async for chunk in self.body_iterator:`。`self.body_iterator` 就是 `event_source()` 返回的对象（`responses.py:237` 的 `self.body_iterator = content`）。📎 打印调用栈实测（端口 8094）：`starlette/responses.py:279 in wrap -> await func()` → `responses.py:253 in stream_response -> async for chunk in self.body_iterator:` → `who_pulls.py:14 in event_source`。⭐ 判据：**`StreamingResponse(event_source(), ...)` 这一句就是把生成器"交出去"，之后由框架遍历**。⚠️ 别把 `app.py` 里的 `for ch in "你好…"` 当成推进机制 —— 它遍历的是**字符串**。
25. 「协程」「普通生成器」「异步生成器」三者怎么区分？各配什么工具推进？
    > **只看两件事：有没有 `yield`、有没有 `async`。** 📎 实测接口差异：`generator` 只有 `__next__`（配 `next()` / `for`）；`coroutine` 只有 `__await__`（配 `await`）；`async_generator` 只有 `__anext__`（配 `async for`）。拿错工具直接报错：`next(异步生成器)` → `'async_generator' object is not an iterator`；`async for 协程` → `'async for' requires an object with __aiter__ method, got coroutine`。⚠️ **协程不能 `async for`**；"普通函数的 `yield`"这个说法不存在（有 `yield` 就是生成器）。
26. 上游 OpenAI 兼容接口的流式帧里，回答文字藏在哪个路径？一帧能装多少内容？
    > `choices[0].delta.content`（delta = **增量**，不是全量）。📎 实测 DeepSeek「从1数到5」：67 个帧里 **56 帧是 `reasoning_content`（思维链）**、只有 **9 帧是 `content`**（"1 2 3 4 5" + 空格）。⭐ 所以**帧数 ≠ 字数**，且 `content` 与 `reasoning_content` **互斥**（没有一帧同时有值）。
27. 上游的结束帧有什么特殊？只转发 `content` 会丢掉什么？
    > 结束帧（倒数第 2 条）`delta.content` 是**空字符串 `""`**，同时带 **`finish_reason: "stop"`** 和 **`usage`**（实测 `prompt_tokens=44 / completion_tokens=66 / total_tokens=110`，其中 `reasoning_tokens=56`）。⚠️ 只按"content 非空就转发"会**同时丢掉** `finish_reason` 和 `usage`（后者是**计费依据**）。另注：首帧的 `content` 是 `null` 而不是 `""` —— 判断要用 `if delta.get("content"):` 真值判断，一次覆盖 `null` / `""` / 字符串三种。
28. 假数据流式接口原来是 `GET`，接真模型为什么必须改成 `POST`？"GET 带 body 会报错"这个理由对吗？
    > ❌ **不对**。📎 实测：`@app.get` 的路由声明 pydantic 请求体后，`GET + body` 返回 **200** 并正确解析，OpenAPI 里 `GET` 也生成了 `requestBody`。真正的理由是**语义**：① GET 是**安全方法**（可缓存 / 可预取 / 可自动重试），而聊天请求**花钱、占上游配额、结果不可重复** ② messages 是**数组结构**，塞 URL 要编码且有长度风险 —— 📎 实测 `httpx` 超长 query 直接抛 `InvalidURL: URL component 'query' too long` ③ URL 会进 access log / 浏览器历史 / Referer，聊天内容不该出现在那里 ④ 与 OpenAI `/chat/completions` 的 POST 对齐。⭐ 判据：**"能跑" ≠ "该这么做"，方法选择由语义决定**。
29. 上游流式帧里 `choices` 为什么是列表？我们的代码为什么能安全地固定取 `choices[0]`？
    > 列表是因为 OpenAI 协议有 `n`（一次要几个候选），每个元素带 `index`。📎 实测 DeepSeek：**不传 `n` / `n=1` → 200 且 `choices` 长度恒为 1**；**`n=2` / `n=3` → 400**，原文 `Invalid n value (currently only n = 1 is supported)`。⭐ 所以 `[0]` 安全的理由是**"我们不发 n + 上游只支持 1"两件事合起来保证了长度 1**，不是"我们决定只要第一个"。
30. `choices[0]` 和"index 为 0 的候选"是一回事吗？如果上游真支持 `n>1` 会怎样？
    > **不是一回事**。`choices[0]` = "**本帧**数组的第一个元素"。📎 模拟 `n=2` 的交织帧（`index` 0/1 交替、每帧只含一个候选）→ 现在的代码逐帧取 `[0]` 会把两路文字**搅成 `'答另案一A段'`**，不是"丢弃一个"。按 `index` 聚合才得到 `0:'答案A'` / `1:'另一段'`。⭐ 防御写法 1 行：`if choice.get("index", 0) != 0: continue`。判据：**列表取 `[0]` 前先问"这个 0 代表什么"**。
31. 「语义缓存」这个想法在业界存在吗？自己想到 ACL 隔离算不算创新？
    > **存在且成熟**，叫 **semantic cache**。📎 官方页面原文：GPTCache 仓库标题 `A Library for Creating Semantic Cache for LLM Queries`；RedisVL `SemanticCache` 文档"What You'll Learn" 里直接写着 `Configure TTL policies` 与 `Implement access controls with tags and filters for multi-user scenarios`。⭐ 所以 ACL 进键、TTL 失效都是**库里的现成参数，不是创新**。真正的分水岭是**能不能用数据证明该缓存（命中率 / 误命中率 / 省多少钱）并设计出不越权的失效机制**。详见[学习过程记录](learning-log.md)专题 7。
32. `async with client.stream(...)` 退出代码块时的「关闭连接」，到底关的是什么？TCP 会断吗？
    > 取决于**流有没有读完**。📎 三种情形实测（读 `client._transport._pool.connections`）：① **读完**整个 body → 连接**归还连接池**、TCP **不断**（3 次请求池内恒为 `1`、`is_idle=True is_closed=False`）② **中途 break** → 连接**被销毁**（池内 `0`）③ 退出 `AsyncClient` 的 `async with` → 池清空。⚠️ 这说的是**「我们的服务器 → 上游」**，与「浏览器 → 我们的服务」是两条独立连接。⭐ 判据：**「关闭」≠「断 TCP」**，读完只是归还。
33. 我们的代码在 `[DONE]` 处 `break`，会带来什么后果？
    > 🔴 **每次流式请求都销毁 TCP 连接 → 共享 client 完全失效**。📎 实测：`break` 版池内恒为 `0`；改成 `continue` 读到 EOF → 池内恒为 `1` 且 `is_idle=True`。⚠️ 根因：**没读完的 body 不能复用连接**（残留字节会污染下一个请求），`resp.aread()` 补救会抛 `httpx.StreamConsumed`。⭐ 修法：`break` 改 `continue` + `seen_done` 标志。
34. 叫「chunk」的东西有几种？类型分别是什么？
    > **三层，类型完全不同**：① **HTTP chunk** = `bytes`（`transfer-encoding: chunked`，见 `aiter_raw`/`aiter_bytes`）② **SSE 行** = `str`（`aiter_lines()` 给的）③ **补全片段对象** = `dict`（我们 `json.loads` 得到的，Go SDK 里叫 `ChatCompletionChunk`）。⭐ 判据：**看代码先确认「这里的 chunk 是哪一层」**；我们代码里的 `chunk` 是第 3 层，所以用 `["choices"]` 下标。
35. `usage` 里哪些字段最值得监控？哪些字段「不是每帧都有」？
    > 监控：`completion_tokens_details.reasoning_tokens`（📎 实测 56/66 = 85%，钱主要花在思维链）、`prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`（算前缀缓存命中率）。单帧字段：`usage`（📎 67 帧里只出现 **1** 次）、`finish_reason`（`None` × 66、`"stop"` × 1）、`delta.role`（1 次）。⭐ 判据：**单帧字段必须先处理，再判断 content**。
36. 「连接池里 0 条连接」和「1 条 idle 连接」分别意味着什么？代价差多少？
    > **连接池 = 客户端手里维护的一批已经握好手的 TCP 连接**，用完不销毁，留着下次直接用。
    > 📎 `池内=1 is_idle=True is_closed=False` → 有 1 条连接空着待用；`池内=0` → 一条可用的都没有，
    > 下次请求必须重做 **DNS + TCP 三次握手 + TLS 握手**。
    > 📎 实测握手成本：`curl -w` 新连接 `connect=19~45ms`、`tls=43~70ms`；**复用连接时两者都是 `0.000000s`**。
    > 📎 httpx 端到端：每次新建 client **174.5ms/次** vs 共用 client **103.7ms/次**，差 **70.8ms/次（1.68 倍）**。
    > ⭐ 判据：**「池内 0」不是错误，只是每次都要重新付 50~115ms 的握手钱** —— 所以 `break` 销毁连接是纯浪费。
37. 上游流式帧可以分成哪几类？一次生成按什么顺序产生它们？（📎 问「从1数到3」实测 64 帧）
    > **五类**：① **ROLE 首帧**（`delta.role=assistant`，1 帧）② **REASONING 思维链帧**（`reasoning_content` 有值，**56 帧**）③ **CONTENT 内容帧**（`content` 有值，5 帧）④ **FINISH 结束帧**（`finish_reason` + `usage` **挤在同一帧**，1 帧）⑤ **`[DONE]`**（纯文本、不是 JSON，1 帧）。
    > 📎 实测顺序：`ROLE ×1 → REASONING ×56 → CONTENT ×5 → FINISH(stop)+USAGE ×1 → DONE ×1`。首 3 帧 `['ROLE','REASONING','REASONING']`，末 3 帧 `['CONTENT','FINISH(stop)+USAGE','DONE']`。
    > ⚠️ REASONING 与 CONTENT **不保证先全推理再全内容**（可能交替）。⭐ 判据：**结束信息只在最后 1 帧，且那帧的 `content` 是 `""`** —— 所以处理 `finish_reason`/`usage` 必须放在 `content` 判断之前。
38. 上游 64 帧为什么只变成我方的 9 帧？少了什么、多了什么？
    > 📎 实测我方输出：`THINKING → DELTA×5 → FINISH_REASON → USAGE → DONE`（9 帧）。
    > **少了**：ROLE 1 帧 + REASONING 56 帧（共 57 帧被 `if not text: continue` 丢弃）。
    > **多了**：THINKING（我方在请求上游**之前**自造）；FINISH 那 1 帧被**拆成 2 帧**（`finish_reason` 和 `usage` 各发一次）；`[DONE]` 由我方重发（上游那个只用来 `seen_done` 跳过）。
    > ⭐ 计算：64 − 57（丢弃）+ 1（THINKING）+ 1（FINISH 拆成 2）+ 0（DONE 重发不算新增）= 9 ✅
39. 上游失败可以分几层？每层各应该给客户端什么状态码？
    > **三层**：① **L1 没回应**（DNS / TCP / TLS 失败、超时）→ `httpx.RequestError` → **502** ② **L2 有回应但状态码不对**（401/403/404/429/5xx）→ `httpx.HTTPStatusError` → **502**（`429` 可考虑 `503` + `Retry-After`）③ **L3 200 但内容不合规**（HTML 错误页 / 空 body / 字段改名 / `null` / 忽略 `stream`）→ `JSONDecodeError` / `KeyError` / `TypeError` / `ValidationError` → **502**。
    > ⭐ 判据：**500 的含义是「我方有 bug」，L3 是「上游不守规矩」**，混在一起等于监控失效（值班告警与排查方向完全不同）。⚠️ 流式下 L3 发生在**响应头已发出之后**，状态码改不了 → 只能把错误编码进流。
40. 为什么流式接口的「静默错误」比崩溃更危险？举两个实测例子。
    > 因为**不抛异常、不写日志、客户端以为正常结束** → 上线一个月才有人报；崩溃当天就能发现。
    > 📎 实测两个：① **`data:xxx` 无空格**（SSE 规范允许）→ `startswith("data: ")` 判定失败 → 整条流被静默丢弃，**0 输出、无报错** ② **`content` 是数组**（多模态风格）→ `if not text` 通过（list 为真）→ 把 list 塞进 `{"delta": [...]}` 发给前端。
    > ⭐ 判据：**防御要覆盖「结构会变」，不能只覆盖「网络会断」** —— 网络断了你能立刻知道，结构变了你什么都不知道。
41. 防御性编程什么时候属于「过度设计」？判据是什么？
    > 判据一句话：**防「会变的契约」和「会坏的网络」，不防「不可能的世界」。**
    > ✅ 该防：上游结构变化（键名/类型/`null`）、状态变化（4xx/5xx/429/超时）、非 2xx 时读 error body、流式错误编码进流、缺字段降级。
    > ❌ 过度：防上游 10 层恶意嵌套（不是威胁模型）、为每家上游写适配器（现在只有 1 家）、每帧加 crc（TCP 已有校验和）、自动降级到第二家上游（阶段 4 再说）。
    > ⚠️ 过度防御的具体代价：代码量翻倍、**真实错误被 `except` 吞掉**、调试变难 —— 掩盖 bug 比暴露 bug 更糟。
42. 「把上游错误翻译成 502」这段代码应该写在哪？三个候选方案各自的问题是什么？
    > **判据：先问「这段代码会被调用几次」—— 会被 ≥2 个调用点用到的错误处理，不属于任何一个调用点。**
    > ① **每条路由各写一遍** → 新路由要抄 30~40 行；抄漏 → 静默落 500；抄错 → 错误码飞掉（📎 本项目真发生过：`UPSTREAM_MALFORMED` 被抄成 `UPSTREAM_MALFORMEAD`，`.get(code, 400)` 静默回退，**所有 L3 场景实际返回 400**，而三道质量门全绿）。
    > ② **全局 `@app.exception_handler(httpx.RequestError / HTTPStatusError)`** → 路由零行，但它**靠 ASGI 中间件栈兜异常**，在 CLI / 定时任务 / 后台 worker 里调同一个上游时**完全失效**；而且"同一件事有 2 处真相"。
    > ③ ✅ **抽出 `LlmClient` 适配器** → 路由零行、非请求上下文照样翻译、**不用起 FastAPI 就能用 `MockTransport` 单测**。
    > ⭐ 两个次级判据用来排除 ②：**不启动 FastAPI 能测吗？定时任务里还有效吗？** —— ② 两个都是 ❌。
43. 适配器（`LlmClient`）的契约用一句话怎么说？为什么"路由零 `try/except`"不等于"一个字都不写"？
    > 契约：**成功返回值，失败抛 `AppError`，绝不把 `httpx` 异常泄漏给调用方。**
    > 「零 `try/except`」指的是**不翻译 `httpx` 异常**。例外是**流已经开始之后**出的错：那时 `200` 响应头早已发出，改不了状态码 → 必须由路由接住并编码成 `event: error` 帧（📎 实测：流中抛异常时客户端看到 `RemoteProtocolError: incomplete chunked`，不是你的错误信息）。
44. `raise_for_status()` 与 `if resp.status_code >= 400` 有什么区别？哪个更对？
    > 📎 实测 `raise_for_status()` 对 **100 / 301 / 302 / 304 / 400 / 404 / 500 全部抛**，只对 200 / 204 不抛 —— 它判定的是 **`is_success`（200~299）**，不是 `>= 400`。
    > ⚠️ 所以 `>= 400` 会**放过 3xx** 继续去解析空 body → 误报成「结构不合规」。⭐ 判据：**判成功用 `resp.is_success`**；302 说明接口地址搬家了，那是状态码问题，不是结构问题。
45. 流式接口在响应头已经发出的情况下，怎样才能仍然返回正确的 502？代价是什么？
    > **pre-flight（起飞前检查）**：在 `return StreamingResponse(...)` **之前**，先 `client.send(client.build_request(...), stream=True)` —— 它**拿到响应头就停，body 一行没读**；此时 `raise_for_status()` 失败，我们的响应头还没发出去，所以仍有资格回 502。
    > 📎 实测：上游返回 400 时客户端拿到 **502 `UPSTREAM_BAD_STATUS`**，而上游正常时客户端拿到完整帧流（9b-2 时这里是 `200` + 断连）。
    > ⚠️ 两个必须记住的点：① **`send(stream=True)` 没有 `async with` 帮你关**，必须自己 `aclose()` 且放 `finally`；② 代价是 TTFB 从 **60.0ms → 约 181~266ms**（要等上游响应头），仍远小于首个内容帧的 845.8ms。
    > ⭐ 边界：pre-flight 只能看**状态码**，看不到 body 内容 —— 上游 `200` + HTML 它照样放行（📎 实测客户端只收到 `thinking` + `[DONE]`）。
46. `_request(..., stream: bool = True)` 这个默认值会造成什么后果？为什么三道质量门和 `MockTransport` 都抓不到？
    > 后果：`list_models()` 不传 `stream` → 走 `send(stream=True)` → 接着 `response.json()` 抛 `httpx.ResponseNotRead`；它的 MRO 是 **`ResponseNotRead → StreamError → RuntimeError`**，**既不是 L1 的 `RequestError`，也不在 L3 的 `(ValueError, KeyError, TypeError)` 里** → 穿过适配器所有 `except` → **500**。📎 真网络实测 `GET /v1/upstream/models -> 500`。
    > 抓不到的原因：`ruff`/`mypy` 只看代码形状；**`MockTransport` 里 `httpx.Response(200, json=...)` 的 body 已在内存**，`send(stream=True)` 与 `request()` 毫无区别 —— 模拟环境根本表达不出"这条连接是流式的"。
    > ⭐ 判据：① 这类开关**默认值必须取"安全的那一边"**（False = 读完 body），需要流的方法自己显式传 True；② **涉及"body 读没读"的改动必须打真网络**。
47. 同一条业务规则（最后一条消息必须是 `user`）只写在一条路由里，会付出什么代价？应该怎么放？
    > 📎 实测同一个请求体：`/v1/chat` → **400**；`/v1/chat/stream` → **200**，还真的把 assistant 那段话发给上游、拿回一整段回答 —— **白花一次上游调用**，客户端完全不知道自己做错了。
    > ⭐ 修法：抽成纯函数 `ensure_last_message_is_user(request)`，两条路由都调；**必须放在 pre-flight 之前**，否则等于"先花钱再拒绝"。
    > 判据（与 §14.7 同型）：**先问「这段代码会被调用几次」，会被 ≥2 个入口用到的规则/翻译，不属于任何一个入口。**
    > 分层归属：**形状归 pydantic，语义归纯函数/服务层，HTTP 归路由**；只有 1 个调用点时抽出去属于提前抽象，比重复更糟。
48. 「同一份事实只写一处」这条原则的判据是什么？为什么不能只用「有没有重复代码」来判断？    > 判据：**改一处会不会漏另一处**（不是"看起来重复"）。
    > 因为**重复代码有时是对的** —— 两段长得像但会往不同方向演化（两个接口各自的提示文案、两个模型各自的分支）；
    > 而"必须同步"才是真问题。反过来，**同一份事实存在 N 份（N≥2）时，第 N+1 次改动一定会漏**，
    > 📎 本项目五起事故全部同源：`Bearear`（字面量）/ `X-Request_ID`（头名）/ `UPSTREAM_MALFORMEAD`（错误码抄第二遍）/
    > `upstream_models` 那 12 行永不触发的 `except`（翻译写两层）/ `chat_stream` 缺 role 校验（规则只写一条路由）。
    > ⭐ 三个提问顺序：① 会被 ≥2 处用到吗（否 → 就地写）② 两处不一致会出错吗（否 → 可不抽）③ 抽完要传 ≥4 个参数吗（是 = **抽错了**）。
49. 用户（学习者）提出的要求本身可能是错的。AI 应该怎么处理？「每次都反驳」和「每次都照做」为什么都不对？
    > **三档**：A 直接执行（要求成立 / 风格偏好）｜B 执行 + 标注风险（有次要代价）｜**C 先质疑，等确认**（事实错误 / 影响正确性安全 / 与规范冲突 / 难以撤销）。
    > 分档判据：**这个决定的错误能不能低成本撤销？** 能 → A/B，不能 → C。
    > 「每次都照做」的害处：错误设计被固化进代码，而学习者会以为"这是讨论过的结论"（📎 本项目真发生过：AI 的步骤卡让每条路由写 `try/except`，设计错了两次）。
    > 「每次都反驳」的害处：把偏好当错误来论证，浪费学习者时间，且会让真正的质疑失去分量。
    > C 档四步：**先说结论 → 给证据（实测/文档原文/源码，不许拿"一般来说"当证据）→ 说清后果 → 给替代方案**（只否定不给出路 = 没帮上忙）。
    > ⚠️ **双向**：学习者也要评估 AI 的输出（📎 AI 曾谎报"已收口"却一个 edit 都没执行）。
50. `chunk: dict[str, Any] = json.loads(raw)` 这行在运行时做了什么校验？mypy 为什么抓不到？什么情况下它才会暴露？
    > **运行时零校验。** 这是 annotated assignment：Python 只把名字 `chunk` 绑到 `json.loads(raw)` 的值上，`dict[str, Any]` 只记进 `__annotations__`（元数据），**没有任何代码验证它**。📎 实测 `json.loads` 可返回 `None` / `[]` / `'x'` / `1`，全部违反标注，Python 一声不响。
    > **mypy 抓不到**：`json.loads` 的返回类型是 `Any`，而 `Any` 赋给任何类型都合法（既是所有类型的子类型、也是父类型），所以 mypy 相信你的标注。
    > **唯一暴露方式**：你在下游**又 `isinstance` 它** → `mypy: Statement is unreachable`（📎 本项目实测 `app.py:313`）。因为 mypy 认为「你说是 dict，那 `if not isinstance(..., dict)` 永远为假」。
    > ⭐ 所以 `warn_unreachable`（不在 `strict` 预设里，项目显式开了）真正抓的是**「你对自己的类型都不信」**。判据：**标了类型就信任它；不信任就在产生它的地方收窄，不要留给调用方怀疑。**
51. 「上游一帧内容都没给」为什么必须发一帧 `STREAM_NO_CONTENT`，而不能靠状态码表达？判断条件为什么用 `content_frames == 0` 而不是 `raw_chunks == 0`？
    > **状态码表达不了**：上游返回的是 `200`（HTML 错误页 / 空 body / 忽略 `stream` 全都是 200），pre-flight 拦不住；而响应头一旦发出就改不了状态码。客户端 `response.ok === true`，**「模型真的说了空」和「上游啥也没给」长得一模一样**。所以只能在流里发一帧结构化 error：`data: {"error": {"code": "STREAM_NO_CONTENT", ...}}`。
    > **为什么数 `content_frames`**：`raw_chunks` 数的是"上游发了多少帧"，用户关心的是"我拿到多少字"。📎 三种 `raw_chunks > 0` 但 `content_frames == 0` 的真实场景：① 上游忽略 `stream`（字段是 `message` 不是 `delta`）② `content` 是数组 ③ 只回了思维链帧。用 `raw_chunks == 0` 会全部漏掉。
    > ⭐ 判据：**计数要数「我们真正交付出去的东西」，不是「上游给了多少」。**
52. 流式失败可以分几层？每层的判据是什么？为什么「让适配器自己发 `STREAM_NO_CONTENT`」是错的？
    > **三层**，判据是**「这个问题在读到数据之前就能判断吗」**：<br>① **pre-flight**（看状态码 `is_success`）→ L1/L2 → **502**（头还没发，能改）<br>② **适配器**（看「行 / 帧」：`startswith("data:")`、空行跳过、非 dict 丢弃）→ 协议变形 → 丢弃 + WARNING<br>③ **路由**（看「字段 / 最终结果」：`isinstance(text, str)`、`content_frames == 0`）→ 类型不对丢弃、零内容发 `STREAM_NO_CONTENT`。
    > **为什么适配器不能发**：它需要知道「**整个流**结束了没有、一共转发了多少」—— 那是路由的状态。**一旦适配器开始关心全局，它就不再是适配器**（规范 §14.7 的职责边界）。
    > 📎 实测补充：**同样是"丢弃"，结果不同** —— `data: null` 后面还有好帧 → 用户拿到 `hi`；`data: [1,2,3]` 后面没了 → 用户拿到错误帧。这正是"适配器只负责丢、路由才负责判断最终结果"的原因。

53. `except Exception` 为什么**不**写 `except asyncio.CancelledError: raise` 也是对的？如果加了，会多一层什么保障？
    > 📎 实测 MRO：`CancelledError` 和 `GeneratorExit` **都直接继承 `BaseException`，不是 `Exception` 的子类**（`issubclass(..., Exception) == False`）。所以「客户端断开」和「生成器被关闭」**根本不会进 `except Exception` 分支**，会原样往外抛，`finally` 照常执行。
    > 加了不多一分保障（它们本来就不进这个分支），反而**多一层噪音**：读代码的人要判断"这里显式放过，是不是因为别的地方会漏"。
    > ⭐ 判据：**用 `except Exception` 就已经自动豁免了所有「取消/退出」类信号** —— 这是 Python 的设计（让取消永远能穿透）。
54. 客户端拿到 `THINKING + DELTA + ERROR(STREAM_FAILED) + DONE` 这一串，应该怎么向用户展示？为什么不能当成"正常回答 + 空结尾"？
    > 必须**保留已收到的 `DELTA` 文字**，同时**明确提示"回答中断，可能不完整"**（可附 request_id 供报错）。
    > 不能当成正常结尾，因为：① 它**没走到 `finish_reason`**，模型并没有"说完"；② 用户看到半句话会以为模型答完了，**可能据此做错误决策**；③ 📎 如果只靠连接断开判断，很多前端库表现为**静默结束**，用户完全无感。
    > ⭐ 判据：**`[DONE]` 只表示"流结束了"，不表示"成功"** —— 成不成功要看有没有 `error` 帧、有没有 `finish_reason`。
55. 9b-4b-2 **没有**任何一行代码专门处理「客户端断开」，为什么说这件事已经解决了？两处代码各负责哪一半？
    > **第一半（检测 + 传播）**：客户端断开时，Starlette 的 `StreamingResponse` 会取消任务 → 生成器收到 `CancelledError`（📎 真 uvicorn 实测 `EVENTS = ['gen-start', 'CancelledError', 'finally', 'upstream.aclose']`）。而 `except Exception` **抓不到它**（它不是 `Exception` 子类），所以它原样往外抛，不会被误当成"流内异常"而发出无意义的错误帧。
    > **第二半（清理 + 真的停下上游）**：`finally: await upstream.aclose()` 照常执行，`aclose()` 会让**上游服务端也停止生成**（📎 实测：本地假上游上限 30 帧，我们读 3 帧后 `aclose()` → 上游只产出 3 帧、收到 `upstream-CancelledError`、1.5s 后不再增长）。
    > ⭐ 所以「客户端断开」是靠 **`except Exception` 的豁免 + `finally` 的清理** 两半合起来解决的，不需要专门写分支。**反过来说：如果把 `except Exception` 改成 `except BaseException`，或者把 `aclose()` 挪出 `finally`，这件事立刻就坏了。**
56. 上游某个字段「类型不对」时，什么时候该静默收窄、什么时候该记 `warning`、什么时候该发错误帧？
    > **三档，判据是「它坏了影响什么」**：<br>① **不影响回答**（只是少了记账/元信息）→ **静默收窄**（`_as_dict` / `or {}`），不记日志。例：`usage` 是字符串。<br>② **丢了会失去可观测性**（少了一条事后排查要用的信息）→ **收窄 + `warning`**。例：`finish_reason` 是对象、`content` 是非 None 的非字符串。<br>③ **整体没交付** → **`error` + 错误帧**。例：`content_frames == 0` → `STREAM_NO_CONTENT`；解析失败 → `STREAM_FAILED`。
    > ⭐⭐ **最容易搞错的是 ① 和 ② 的分界**，判据一句话：**「这条日志出现时，会有人去查吗？」会 → ②；不会 → ①。**
    > 📎 本项目写错过一次：`finish_reason` 判空写成 `is not None`，于是**空字符串也报警**，还打出 `type=str`（自相矛盾）。但 `finish_reason` 在**每一帧**都有，中间帧就是 `null` / `''` —— 正常请求会刷几十条 warning，等于把告警调成没人看。正确条件：`is not None and not isinstance(x, str)`。
    > ⭐ 推论：**「字段值宽松」不等于「出问题」**。`null` / `''` / 缺键往往正是协议规定的**正常中间状态**。把正常状态当异常报警，是日志系统最常见的自杀方式。
57. 不看代码，把 `POST /v1/chat/stream` 从客户端发起到连接结束的路径**按顺序背一遍**（至少说出：谁分配 `request_id`、在哪一步花掉上游的钱、哪一步之后状态码改不了、`[DONE]` 从哪里发出去）。
    > 📎 完整 21 步图见笔记 §9.9.1。要点顺序：<br>① 客户端 POST → ② uvicorn 组 ASGI scope → ③ **中间件分配 `request_id`** → ④ 路由匹配 + 依赖注入 → ⑤ pydantic 校验（不过就 422）→ ⑥ 业务规则 `ensure_last_message_is_user`（不过就 400）→ ⑦ 拼上游 body → ⑧ **`send(stream=True)` ← 钱从这里花出去** → ⑨ 上游响应头到 → ⑩ `is_success` 检查 → ⑪ 返回 `StreamingResponse` → ⑫ **200 + chunked 发出 ← 状态码从此焊死** → ⑬~⑯ 逐帧 `aiter_lines → aiter_chunks → 守卫 → 重组 → yield` → ⑰ 零内容检查 + `yield [DONE]` → ⑱ 客户端收到 `[DONE]` → ⑲ `finally: await upstream.aclose()` → ⑳ 连接归还池 → ㉑ 客户端读到 EOF。
    > ⭐ 两个**不可逆时刻**：**⑧（钱花了）** 和 **⑫（状态码焊死了）**。所有防御都安排在这两点之前（pre-flight / 业务校验），或之后唯一的表达通道里（错误编码进流）。
58. 客户端收到第 2 帧后主动断开。服务端会：进 `except Exception` 吗？会执行 `finally` 吗？会发 `[DONE]` 吗？
    > **三个答案：不会 / 会 / 不会。**<br>① **不进 `except Exception`** —— 断开触发的是 `CancelledError`，它直接继承 `BaseException`，被 `except Exception` 自动豁免（📎 MRO 实测 `issubclass(CancelledError, Exception) == False`）。<br>② **会执行 `finally`** —— 因为它是 `try/finally` 的一部分，取消信号不跳过它（📎 `EVENTS = ['gen-start', 'CancelledError', 'finally', 'upstream.aclose']`）。<br>③ **不会发 `[DONE]`** —— 它写在 `try` 正文和 `except` 里，两个分支都被跳过了；而且**即使想发也发不出去**（客户端已经走了），更糟的是如果在 `finally` 里 `yield` 会直接 `RuntimeError: async generator ignored GeneratorExit`。
    > ⭐ 这条顺带解释了为什么 `[DONE]` 要**写两次**（正常路径 + 异常路径），却不能靠 `finally` 兜一次。
59. 如果把 `LlmChatStream.aiter_chunks` 里的 `isinstance(parsed, dict)` 删掉、把同样的检查移到 `event_source` 的 `async for` 循环体第一行，会发生什么？为什么这代表**设计错误**而不是「mypy 太严」？
    > **具体后果**：`aiter_chunks` 的返回注解是 `AsyncIterator[dict[str, Any]]`，这是一份**契约承诺**。路由里再 `isinstance` 一次，mypy 报 `error: Statement is unreachable [unreachable]`（📎 本项目 2026-10-22 真踩过）—— 因为「刚承诺它是 dict，转头又怀疑它不是」自相矛盾。
    > **为什么是设计错误**：校验的位置决定了**契约的可信度**。放在生产者（适配器）里 → 契约成立，消费者可以信任类型；放在消费者里 → 契约形同虚设，而且**每个消费者都要各写一遍**（`/v1/chat/stream`、将来第二条 SSE 路由、CLI 全部要重写）。
    > ⭐ 判据：**校验要放在「能兑现承诺的那一层」** —— 谁把 `Any` 收窄成具体类型，谁就对下游负责。绕开它的唯一"办法"是把注解降级成 `AsyncIterator[Any]`，那是**用类型系统的失明换编译通过**，更糟。

60. 说出流式里 **token / 帧 / 行 / 字节块** 四个单位的定义，并解释：模型明明输出了一句话带换行，为什么「行」这个概念还能成立？
    > 📎 一次真实请求实测：**15 个 gzip 原始字节块 → 13 个解压字节块 → 150 行（75 个 `data:` + 75 个空行）→ 75 帧 → 6 个可见片段**。单个字节块里最多含 6 个完整帧。
    > <br>① **token**：模型层的生成单位（`" need"` 带前导空格 → token ≠ 字）<br>② **帧**：协议层的一个 SSE 事件 = `data: {...}` + 空行<br>③ **行**：文本层按 `\n` 切出来的结果<br>④ **字节块**：传输层一次 recv 拿到的东西（可能含多帧、可能是半行、可能是 gzip 压缩态）。
    > <br>⭐ **「行」为什么成立**：模型输出的真换行符被 `json.dumps` **转义**成 `\` + `n` 两个字符。实测还原那一行原文：`'content":"\\n"'` → `json.loads` 后是 1 个字符的真换行；而 **「这一行里有真实换行符吗: False」**。所以内容再多行，也压不破协议结构。
    > <br>⚠️ **反面**：上游若**不转义**，`data: {"content":"苹果<真换行>香蕉"}` 会被切成两行，第二行不以 `data:` 开头 → 被我们跳过 → **内容静默丢失**。所以 `startswith("data:")` 既是过滤也是守卫。
    > <br>⭐ 另一条：**生成可能一 token 一帧，但到达一定成批**（📎 `1.982s` 一瞬间到达 12 行）。「逐字出现」靠的是上游**持续产生**，不是逐帧送达。

61. 「什么时候必须等完整 body，什么时候该流式」——判据是什么？为什么「接收流式」和「返回流式」是两个独立决定？
    > ⭐ **一句话判据**：看「**第一个有用的字节**什么时候能被用掉」。答案是「等最后一个字节到齐」→ 等完整；否则 → 流式。
    > <br>**必须等完整（需要「全局视角」）**：① `json()` 解析（JSON 语法整体性）② 校验/哈希/签名 ③ 排序/聚合/去重/取 top-k ④ 要先看全貌再决定（如 `total`）。
    > <br>**必须流式（「有用」≠「完整」时刻）**：① 上游持续产生且用户能边看边用（TTFB 是产品指标）② body 上界未知或大于内存 ③ 透传而中间层不能缓冲 ④ 能中途取消省钱。
    > <br>⭐ **两个独立决定**：接收侧决定「能不能在 body 到齐前开始处理」，返回侧决定「能不能在拿全前往下游发」。四种组合都存在：<br>· 都非流式 = 普通 CRUD（📎 `/v1/upstream/models`）<br>· 都流式 = 纯透传（📎 `/v1/chat/stream`）<br>· 接收流式 + 返回非流式 = **后端聚合**（非流式接口的最佳实现：能中途取消省钱、逐帧记账、防坏帧）<br>· 接收非流式 + 返回流式 = 本地数据导出（body 是我方产生的）
    > <br>⚠️ **两个易错点**：① **「body 小」不等于「该一次读完」** —— 📎 100 字节的响应也可能要 1.2 秒分批到达；判据是「到达是否分散在时间上」OR「上界未知/过大」。② **「我最后要整块数据」不等于「必须非流式接收」**。
    > <br>⭐ **协议启示**：想流式，就得让每一片**自足**（NDJSON / SSE / 长度前缀）。一个大 JSON 语法上整体，无法逐片解析 —— 这是 LLM API 用 SSE 而非一个大 JSON 的根本原因。
    > <br>📌 **将来会遇到**：`tool_calls` 的 `arguments` 是**字符串片段流式拼装**的，必须拼完才能 `json.loads` —— 属于「必须等完整」那一类（阶段 2）。

### Step 10 · 数据库（SQLAlchemy 2.1，2.0 风格异步 ORM）

1. 为什么 `uv add sqlalchemy` 不够，必须 `sqlalchemy[asyncio]`？
   > 📎 版本边界要分清（2026-10-23 两个独立环境实测）：**2.1.6 裸装**后 `import sqlalchemy.ext.asyncio` → `ModuleNotFoundError: No module named 'greenlet'`；**2.0.55 裸装**则会自动装上 greenlet，异步导入直接成功。所以「必须显式装 extra」是 **2.1 起**的行为，**不能泛化到 2.0**。
   > 另外：`aiosqlite` / `asyncpg` 是**数据库驱动**，要作为独立依赖安装，不在 SQLAlchemy 的 extra 里。
2. `expire_on_commit=False` 解决什么问题？异步下不设会怎样？
   > 默认 commit 后对象**过期**，再访问属性会触发隐式刷新；异步下同步序列化阶段无法 `await` 这次 IO。
   > 📎 本机 2.1.6 + `aiosqlite` 实测：**顶层异常是 `StatementError`，其 `.orig` 才是 `MissingGreenlet`** —— 别按顶层异常名去猜。
3. `add` / `flush` / `commit` 的区别？事务边界应该收在哪里？
   > `add` = 放进 session（待处理）；`flush` = **把待处理改动发成 SQL，仍可回滚**（能拿到自增 id；若当前没有事务，session 会按配置自动开始事务）；`commit` = 提交并结束事务。边界应收在**依赖的 teardown**里（一次请求一个事务）。
4. `get_db` 里的 `except` 为什么必须 `raise`？不 raise 的症状是什么？
   > 📎 2026-10-25 实测订正（FastAPI 0.143.0）：不 `raise` **不是**「客户端收到 200」。实际客户端仍拿到 **500 + 统一错误形状 + `request_id`**，日志里则是 `fastapi.exceptions.FastAPIError: Response not awaited. There's a high chance that the application code is raising an exception and a dependency with yield has a block with ... except Exception, and is not raising the exception again.`，且 **`FastAPIError.__cause__ = None`**。
   > ⭐ 真实代价：**原始异常（类型 / 消息 / 出错行号）彻底丢失**，而客户端看到的响应与正常路径**一模一样** —— 只有翻日志的人才会发现不对劲。
   > 判据：**清理动作可以吞异常，业务异常必须重新抛出**。
5. 什么样的代码模式几乎等于 N+1？怎么修？
   > 循环里为每条父记录单独查询关系 → 1 次查列表 + N 次查关联。异步 ORM 直接访问未加载关系会触发隐式 IO；📎 本机 2.1.6 + `aiosqlite` 实测顶层是 `StatementError`、`.orig` 是 `MissingGreenlet`。修：`selectinload` **预加载**，或显式执行可等待的批量查询。

6. 为什么 `engine` 放**模块级单例**，而不是在 `lifespan` 里创建后挂到 `app.state`？
   > **决定性理由**：挂 `app.state` 就必须先有一个 `request` 才能取到 → CLI / 定时任务 / 迁移脚本 / 不起 app 的单测全部拿不到。⭐ 这和 Step 9「全局 `exception_handler` 在 CLI 里失效」是**同一条规律**：挂在 app 上的东西只在 HTTP 生命周期内存在。
   > 另外三条：① `app.state` 是 `Any`，属性名拼错 mypy 查不到（本项目待办 #8）② `lifespan` 职责更单一（只管启动建表 / 关闭 dispose）③ `with TestClient(app)` 进两次会造两个 engine，前一个没 dispose。
   > ⭐ 判据：**「只要进程活着就该存在」→ 模块级单例；「每个请求各要一份」→ 依赖注入。**
   > ⚠️ 模块级单例的代价：测试换 `:memory:` 不好办 → 对策是 `get_db` 做成依赖，用 `dependency_overrides` 替换。

7. `engine = create_async_engine("sqlite+aiosqlite:///./app.db")` 执行完，数据库文件就存在了吗？怎么验证？
   > **不存在。** 📎 实测：导入 `app.database` 之后 `Test-Path app.db` 仍是 `False`。`create_async_engine` 只创建引擎对象（含一个**空**连接池），真正 `open` 连接发生在**第一次执行 SQL** 时。
   > ⭐ 判据：**「对象建好了」≠「东西发生了」** —— 判断后者的唯一办法是看副作用（文件出现 / 真发了 SQL / 日志里有语句）。
   > 📎 附带实测：`:memory:` 引擎默认池已是 `StaticPool`（`check_same_thread=True`）；文件库默认 `AsyncAdaptedQueuePool`（`check_same_thread=False`）—— 所以旧教程那句 `connect_args={"check_same_thread": False}` 对 `sqlite+aiosqlite` 是多余的。

8. `async with create_llm_client() as client:` 里我**看不到任何关闭代码**，那连接是谁关的、什么时候关的？
   > **关闭指令在对象的 `__aexit__` 里**，不在 `with` 那一行。`LlmClient.__aexit__` 的实现就是 `await self._http.aclose()`。
   > `async with X as y` 是语法糖，等价于：`y = await X.__aenter__()` / `try: <块> finally: await X.__aexit__(...)` —— 所以**正常结束和抛异常都会关**（📎 实测两种路径都调到了 `__aexit__`，异常时 `exc_type=RuntimeError`）。
   > ⭐ 判据：**`async with` 的关闭动作由「对象实现了 `__aenter__`/`__aexit__`」保证，不由写代码的人记得保证。**
   > ⚠️ 推论：`yield` 必须在 `async with` **里面** —— 它在里面 = 「暂停期间 with 块没结束，别关」；放外面**不报错**但清理发生在**启动阶段**（📎 实测 `client.closed = True`，整个服务期每个请求拿到已关闭客户端）。

9. 为什么 20 次请求「复用同一个 `AsyncClient`」比「每次新建」快很多？项目里两个连接池分别在哪创建、在哪关闭？
   > 因为**新建 client 就要重新 TCP 握手（+ TLS）**。📎 实测 20 次请求：复用同一个 client → **新连接 1 条**、1.75ms/次；每次新建 → **新连接 20 条**、11.01ms/次，**慢 6.28 倍**（本机回环；真实公网 TCP 19~45ms + TLS 43~70ms，差距更大）。端口证据：复用方案 3 次请求只有 1 个客户端端口。
   > **两个池**：① httpx 池（到上游的 TCP）—— `create_llm_client()` 里建，`LlmClient.__aexit__` 里 `aclose()`；② SQLAlchemy 池（到数据库）—— `database.py` 的 `create_async_engine()` 里建，`lifespan` 里 `engine.dispose()`。
   > 维护方式相同：**进程启动创建一次 → 整个服务期复用 → 进程退出释放一次**。
   > 📎 池状态实测（默认 size=5 / max_overflow=10）：执行 SQL 前 `checkedin=0`（**懒创建**）→ 执行时 `checkedout=1` → 归还后 `checkedin=1` → `dispose()` 后 `checkedin=0`。
   > ⭐ 判据：**「不是你的资源了，就还回去」** —— 和 Step 9 里 `stream=True` 必须 `aclose()` 是同一条。

10. `Conversation(title=payload)` 与 `Conversation(title=payload.title)` 差在哪？为什么 **mypy 抓不到**这个错误？
   > 前者把**整个 pydantic 对象**塞进 `title` 列，后者只取其中的字符串。📎 实测前者报 `sqlalchemy.exc.ProgrammingError: (sqlite3.ProgrammingError) Error binding parameter 1: type 'ConversationIn' is not supported`，客户端收到 **500**。
   > ⭐ **mypy 抓不到的原因**：SQLAlchemy 模型构造函数签名是 `(self, **kwargs)` —— 参数就是 `Any`。所以 **mypy 保护「读出来的类型」（`conv.title` 是 `str`），不保护「写进去的取值」**。这和 Step 9 的 `json.loads()` 返回 `Any` 是同一规律：**`Any` 赋给任何类型都合法**。
   > ⭐ 判据：**ORM 字段类型标注是给读取用的，不是给构造时的入参做校验的。** 想校验入参就靠 pydantic 契约（`ConversationIn`）。

11. `await db.refresh(conv)` 什么情况下才需要？为什么本项目的 POST 里没有它？
   > `refresh` 的作用是「把数据库里那一行的当前值重新读进对象」。只在**值由数据库服务器算出来**时才需要，比如 `server_default=text("CURRENT_TIMESTAMP")`、触发器、或别的连接刚改过的数据。
   > 本项目的 `id` 是**数据库自增**，但 `flush` 时就会把它带回来；`created_at` 是 **Python 端 `default=lambda`**，在 flush 之前就赋值了 —— 两者都已在内存对象里，**不需要 refresh**。
   > ⭐ 判据：**「这个值是谁算的？」** Python 算的（`default=`）→ flush 后就有；数据库算的（`server_default=`）→ 必须 `refresh`（或 `RETURNING`）。

12. `.scalars()` 到底做了什么？为什么 `select(Conversation)` 用它正好，而 `select(Conversation.id, Conversation.title)` 用它就会丢数据？
   > `.scalars()` = **每行只取第 1 列**，不是「把 tuple 转成对象」。📎 实测：`select(Conversation)` → `.all()` 是 `[Row, Row]`，`.scalars().all()` 是 `[Conversation, Conversation]`（因为第一列本来就是完整 ORM 对象）；但 `select(id, title)` → `.all()` 是 `[(1,'A'),(2,'B')]`，`.scalars().all()` 只剩 `[1, 2]` —— **title 被静默丢掉，不报错**。
   > ⭐ 判据：**想拿完整对象就用 `select(Model)` + `scalars()`；选多列就用 `.all()` 或按名取。**

13. `return list(result.scalars().all())` 里的 `list(...)` 去掉，运行时会不会出错？那谁会发现？为什么这次和 `Conversation(title=payload)` 那次的结论相反？
   > 📎 实测：**运行时不出错**。`type(result.scalars().all())` 就是 `<class 'list'>`，`append` / 切片全都能用。去掉后 **mypy 报** `Incompatible return value type (got Sequence[Conversation], expected list[Conversation])`。
   > 原因：`.all()` 的**声明返回类型**是 `Sequence[...]`（只承诺可遍历/索引/`len`，不承诺可变），运行时给的是 `list`。`list(...)` 是**把类型承诺升级**到返回注解要求的 `list`。
   > ⭐ 两次相反：10.5a 是 **运行时错、没人拦**（`**kwargs` 是 `Any`，mypy 查不到）；10.5b 是 **运行时对、mypy 拦**（类型保守）。
   > ⭐ 判据：**「运行时对不对」和「类型对不对」是两个独立问题。**

14. `GET /v1/conversations` 在表为空时该返回什么？为什么不能返回 404？
   > **`200 []`**（📎 实测）。⭐ 理由：「集合为空」是**正常答案**（查询成功了，结果就是空的）；404 意味着「你要的那个东西没有」。如果列表为空返回 404，前端会把「还没建过对话」和「这个接口不存在」混在一起 —— **语义撞车**。
   > 对照：`GET /v1/conversations/{id}` 查单个不存在 → **404**（那才是「找不到」）。

15. `GET /v1/conversations/abc` 和 `GET /v1/conversations/999` 分别返回什么？**谁拒的**？为什么 `-1` 返回 404 而不是 422？
   > `abc` → **422** `int_parsing`（`loc=["path","conv_id"]`）；`999` → **404**。⭐ **谁拒的完全不同**：422 是 **FastAPI 的路径参数校验**拒的（`conv_id: int` 转不动）→ **你的函数体一行都没跑**；404 是**你的 `if conv is None`** 拒的。
   > `-1` → **404**，因为负数是**合法整数**（能解析成 int），只是表里没有这一行。
   > ⭐ 判据：**「格式不对」是 422（客户端的锅）；「格式对但没这条」是 404（数据的状态）。**

16. `db.get()` 查不到时返回什么？如果把 `if conv is None: raise HTTPException(404)` 删掉会怎样？
   > 返回 **`None`，不抛异常**。删掉判空后 `None` 会流到 `response_model`，📎 实测抛 **`fastapi.exceptions.ResponseValidationError`**：`{'type': 'model_attributes_type', 'loc': ('response',), 'msg': 'Input should be a valid dictionary or object to extract fields from', 'input': None}`，客户端拿到 **500**。
   > ⚠️ **不是 `AttributeError`** —— `response_model` 在读属性**之前**先检查"输入是不是对象"。
   > ⭐ 判据：**把 404 的错误伪装成 500，是最容易误导排查的一种** —— 客户端会以为服务器坏了。所以看到返回类型是 `X | None`，下一步就必须判空。

17. 加一个 `GET /v1/conversations/latest` 时，应该写在 `{conv_id}` 之前还是之后？为什么现在这两个路由（列表 + 详情）不需要考虑顺序？
   > **固定词 `latest` 必须写在 `{conv_id}` 之前**。📎 实测写反了：`/items/latest` → **422 int_parsing**（`"latest"` 被当成 `item_id`），那个固定路由**永远走不到**。⭐ 路由按**注册顺序**匹配，先注册的先命中。
   > 现在这两个不冲突：`/v1/conversations` 是 **1 段**、`/v1/conversations/{conv_id}` 是 **2 段**，URL 结构上撞不到（📎 实测两者都正常）。`latest` 也是 2 段，所以会撞。
   > ⭐ 判据：**同层出现「固定词」和「路径参数」时固定词在前；段数不同则无所谓。** 项目里已有先例：`/v1/models/latest` 写在 `/v1/models/{model_name}` 前面。

18. `DELETE` 成功为什么返回 204 而不是 200？如果写成 `status_code=200` + `-> None`，客户端收到什么？**为什么这比报错更难发现**？
   > 📎 实测：`status_code=200` + `-> None` → 客户端收到 `b'null'`（4 字节）。**不是报错**，`mypy` / `ruff` 都不说话。
   > ⭐ 更关键：📎 再把一个「什么都不做」的接口也设成 200 → 它同样返回 `b'null'` —— **客户端完全无法区分「真删了」和「什么也没发生」**。
   > 204 的价值不是省 4 字节，而是**语义上不允许有 body**：FastAPI 在**注册路由时**就检查，违反直接 `AssertionError: Status code 204 must not have a response body`（服务根本起不来）。
   > ⭐ 判据：**「能跑」和「语义正确」是两件事。语义错误不会让任何测试失败 —— 只有读懂 204 语义的人才会发现。**

19. `DELETE /v1/conversations/1` 连发两次，第二次返回 404。这算不算违反 DELETE 的幂等性？
   > **不算**。「幂等」指**连续调用 N 次后最终状态一样**（这条数据都没了），**不要求**每次都返回同一个状态码。📎 实测 204 → 404（第二次）。
   > 两种都合法：第二次返 **404**（客户端能知道"本来就不存在"）或 **204**（重试逻辑简单，但掩盖了"你删的东西不存在"）。
   > ⭐ 本项目选 404，理由是**和"查详情"保持一致**（查不到就 404）—— **一致性比"哪种更优雅"更重要**。

20. `except Exception: raise` 什么额外事都不做，和不写 `try/except` 有什么区别？📎 实测两者的 traceback 帧数和帧序列**完全一样**，说明什么？
    > 📎 实测 F（不写 try）帧数=3 `['<module>:18', 'F:11', 'boom:8']`；G（`except: raise`）帧数=3 `['<module>:18', 'G:14', 'boom:8']`。
    > ⭐ 说明 `except: raise` 是**纯噪音** —— 「放行」最干净的方式是压根不写 `except`。

21. `raise e` 和裸 `raise` 有什么区别？为什么 `raise e` **永远不该用**？
    > 📎 实测：裸 `raise` 顶层 3 帧 `['<module>:43', 'A:20', 'boom:16']`；`raise e` **4 帧**，多出 `B:25`（就是 `raise e` 那一行本身）。
    > 原因：`raise e` 是「**在当前帧重新抛出这个对象**」，Python 会在 `e.__traceback__` 前面**追加当前帧**；裸 `raise` 是「**继续传播手上这个异常**」，不追加。
    > ⚠️ 后果不是报错，而是**日志里多一行毫无意义的行号**，让人以为那里出的问题。

22. `get_db` 里为什么用 `except` + 裸 `raise`，而不是 `finally: await session.rollback()`？
    > 📎 实测三种收尾：`except`+裸 `raise` → 正常 `COMMIT, CLOSE` / 抛错 `ROLLBACK, CLOSE`；**`finally: rollback` → 正常 `COMMIT, ROLLBACK, CLOSE`**（提交完又被回滚掉！）/ 抛错 `ROLLBACK, CLOSE`。
    > ⭐ 原因：**`finally` 两条路都会跑**，而 `rollback` 只该在出错那条路上跑。想区分两条路只能靠 `except`。

23. `PATCH /v1/conversations/{id}` 传 `{}` 会被 422 拒掉。**为什么不允许空 body**？如果放行，会造成什么后果？
    > 如果放行（当 no-op 返回 200）：⚠️ **静默成功** —— 客户端以为改了，其实没改。
    > ⭐⭐ **最要命的理由**：前端把 `title` 拼成 `titel` 时，`title: str`（必填）会报 422 `missing` 立刻暴露；改成 `title: str \| None = None` + 允许空更新就变成 **200 但一个字没改**。
    > ⭐ 判据：**「必填字段」是免费的 bug 探测器**，改成"可选 + 默认 None"等于把它关掉。

24. `422` 里的 `type` 是 `missing` 和 `string_type`，两者区别是什么？
    > `missing` = 字段**根本没出现在请求体里**（`{}`）；`string_type` = 字段**出现了但类型不对**（`{"title": null}`，null 不是 str）。
    > ⭐ 判据：**`missing` 修「漏传」，`string_type` 修「传错了」** —— 先看 `type` 再看 `msg`。

25. `PATCH` 和 `PUT` 的区别？为什么本项目的 `PATCH` 现在和 `PUT` 行为一样？多字段时该怎么写？
    > `PATCH` = 部分更新（没传的字段保持原样）；`PUT` = 整体替换（没传的字段被重置成默认值/null）。
    > ⭐ 本项目只有 `title` 一个可改字段，所以两者行为一样 —— **「部分」这个概念需要至少两个字段才体现得出来**。
    > 多字段时必须用 `payload.model_dump(exclude_unset=True)`：📎 实测 `model_dump()` 在 `{}` 下输出 `{'title': None}`（会把没传的也 setattr 进去，静默清空）；`exclude_none=True` 则**分不清「没传」和「传了 null」**。

26. 一个 PATCH 请求由哪三块组成？**标题和 id 分别在哪一块里**？
    > ① 请求行（`PATCH /v1/conversations/1 HTTP/1.1`）② 头部（`Content-Type` 等）③ body（空行之后）。
    > ⭐ **id 在 URL（请求行）里，标题在 body 里** —— 两套独立的参数通道。

27. 「body 为空」有哪两种？怎么从 422 的响应里区分它们？
    > **A 完全没有 body**（0 字节）→ `loc: ["body"]`、`input: null`；**B body 是 `{}`**（4 字节）→ `loc: ["body","title"]`、`input: {}`。
    > ⭐ `loc` 的层数就是答案：一层 = body 缺失，两层 = 字段缺失。📎 两者都是 `type: missing`，只能靠 `loc` 和 `input` 区分。

28. `{"title": ""}`、`{"title": null}`、`{}` 三者的错误属于**两个不同层次**，分别是什么？
    > `{}`（和完全没 body）是「**没说要改什么**」—— 信息缺失；`""` / `null` 是「**说了，但要改成非法的东西**」—— 内容非法。
    > ⭐ `""` 是长度 0 的**文本**（是 str）；`null` 是**空无一物**（不是 str）→ 前者 `string_too_short`，后者 `string_type`。

29. `ForeignKey` 和 `relationship` 各管什么？为什么说它们是「两个层面」？
    > `ForeignKey` 在**数据库层**（建表语句里生成 `FOREIGN KEY` 约束，**产生列**）；`relationship` 在 **Python 层**（提供 `conv.calls` 导航，**不产生任何列**）。
    > ⭐ 删父行时：`ondelete=` 只对**原生 SQL 删**生效，`cascade=` 才对 **ORM 删**生效。

30. 删一个有 2 条 `llm_calls` 的对话，`relationship` 写不写 `cascade` 差在哪？
    > 📎 实测：**不写** → `llm_calls` 还剩 2 行，`conversation_id` 变成 `NULL`（孤儿留在库里）；**`cascade="all, delete-orphan"`** → 剩 0 行（真删）。
    > ⚠️ 即使写了 `ondelete="CASCADE"`，`session.delete()` 仍然只置 `NULL` —— 因为那是数据库层的规则，ORM 不走它。
    > ⭐ 而「子记录该不该跟着父记录消失」是**业务问题**：财务/审计场景**不该**跟着删。

31. 为什么 `Mapped[list["LlmCall"]]` 里的 `LlmCall` 要加引号？不加会怎样？
    > 📎 实测不加：`NameError: name 'LlmCall' is not defined`。
    > ⭐ 原因：**Python 从上往下执行** —— 执行到 `Conversation` 类体时 `LlmCall` 还不存在。引号把它变成**字符串**（不做名字查找），等所有类定义完再解析。
    > ⭐ 判据：**引号 = 「先记下这个名字，等会儿再找」；不加引号 = 「现在就找」。**

32. `index=True` 不写为什么会全表扫？有索引后为什么是 O(log n) 而不是 O(1)？
    > 表里的行按**插入顺序**堆放，`conv_id` 的值没规律 → 数据库不知道目标在第几页 → 只能逐行看（`SCAN`）。索引是**按该列排好序的额外一份表**（B-Tree），能逐层缩小范围（`SEARCH ... USING INDEX`）。
    > 📎 实测（5 万行）：无索引 2985.9 µs vs 有索引 119.6 µs = **25 倍**。
    > ⭐ 不是 O(1) 因为**索引本身也要一层层找**：📎 规模实测 4 万→8 万，无索引 7.085→17.352 ms（**线性**），有索引 0.165→0.216 ms（**几乎不变**）。每页约 200 项 → 树高只随数据量**对数**增长（40 万行 2 层，800 万行 3 层）。

33. 索引有哪三个代价？什么情况下「不该建索引」？
    > 📎 实测代价：**插入慢 38%**（156.6 → 216.0 ms / 5 万行）、**占空间多 18%**（3056 → 3612 KB）、**可能不被使用**（`WHERE conv_id > 0` 命中大半表时数据库会放弃索引直接全表扫）。
    > ⭐ 不该建：表很小 / **选择性很低的列**（如布尔）/ 频繁写入的列 / 已有复合索引的前缀列。

34. 索引里到底存了什么？「新插入一行的索引值是多少」需要计算吗？
    > 索引项 = **`(被索引列的值, 该行的 rowid)`**，只有这两样。📎 `PRAGMA index_xinfo` 实测：`seqno=0 name='conversation_id' key=1`（排序键）+ `seqno=1 name=None key=0`（隐含 rowid）。
    > ⭐ **不需要计算** —— 你往 `conversation_id` 填 7，索引的键就是 7。新行在索引里的**位置**由「拿这个值在已排序的索引里二分找位置」决定，与 `rowid` 顺序无关。

35. 索引里的顺序是按 `rowid` 排的吗？外键索引里会不会出现重复的键？
    > **不是**。📎 手工模拟实测：依次插 `(rowid=1,conv=3)`、`(rowid=2,conv=1)`、`(rowid=3,conv=3)` → 索引变成 `[(1,2), (3,1), (3,3)]` —— `rowid` 更大的反而排前面。
    > ✅ **会出现重复键**：`conv_id` 是 `1,1,1, 3,3, 4,4`（一个对话有多条调用），重复值连续堆放，所以「查某对话的所有调用」一次就能取到全部。

36. 删掉一行，索引会怎样？为什么主键不用额外建索引？
    > 📎 实测：删一行 = 表里删一行 + **每个索引里删一项**（字节码多一步 `IdxDelete`）；其余项顺序不变，B-Tree 仍有序。有 5 个索引就要动 6 棵树。
    > ⭐ **主键不用额外索引**：📎 实测 `conversations.id` 没有任何索引条目，但按 id 查仍是 `SEARCH ... USING INTEGER PRIMARY KEY` —— 因为**表本身就是按 rowid 排的 B-Tree**。而 `conversation_id` 在表里乱序，才需要再建一棵。

37. SQLite 的外键默认是强制还是不强制的？为什么打开它必须挂在 `connect` 事件上，而不能在启动时执行一次 `PRAGMA`？
    > **默认不强制**（`PRAGMA foreign_keys = 0`）—— 📎 实测能插进 `conversation_id=999` 的孤儿记录。
    > ⭐ 必须挂事件因为 **`PRAGMA` 是「每条连接」的开关，且不持久化**（断开重连恢复默认）。连接池里每条新建连接都要单独打开；只执行一次的话，池里其它连接仍是不强制的。📎 实测挂事件后取 3 条连接全是 `foreign_keys = 1`。
    > ⭐ 用 `engine.sync_engine` 而不是 `engine` —— `event.listens_for` 认不出异步引擎；用 `"connect"`（每条新连接建立时）而不是 `"checkout"`（每次取出，会重复触发）。

38. 「对话不存在 → 404」这段校验原本在 5 处各写一遍（两条 chat + GET/PATCH/DELETE）。为什么必须抽成一个函数？判据是什么？
    > 📎 实测：`detail=f"对话不存在：…"` 这一行出现在 **273 / 337 / 357 / 382 / 429** 五个位置 —— 改文案或改状态码要改 5 处，漏一处就出现「同一种错有两个说法」。
    > ⭐ 判据：**改这条规则时，你需要打开几个文件/几处代码？** 大于 1 就有重复。本项目已有先例 `ensure_last_message_is_user`（6.2b 时就是为此抽的）。
    > ⭐ 抽出来后 5 处各剩 1 行：两条 chat 是 `await require_conversation(...)`，三条 CRUD 是 `conv = await require_conversation(...)` / `return await require_conversation(...)`。

39. 两条接口的**成功**响应形状完全不同（`ChatResponse` 的 JSON vs `StreamingResponse` 的流）。这能不能作为「不抽公共校验函数」的理由？
    > **不能。** 判据错在看了**成功路径**。
    > ⭐ 应该看**失败路径**：校验失败时两条接口回的都是 `application/json` 的 404，形状完全一致 —— 所以校验逻辑 100% 可以共用，只有成功路径的组装必须各写各的。
    > ⭐ 判据：**抽不抽公共代码看「失败路径」而不是「成功路径」** —— 失败路径通常比成功路径一致得多。

40. 一个请求要过四层检查：pydantic 形状校验 / 业务语义（最后一条必须是 user）/ 查库（对话是否存在）/ 调用上游 API。四层应该按什么顺序排？顺序反了会怎样？
    > **按「代价从低到高」排**：pydantic（纯内存）→ 语义（纯内存）→ 查库（一次数据库往返）→ 上游 API（真金白银 + 秒级延迟）。
    > 📎 实测反例：改之前 `/v1/chat` 先查库(270 行)后语义(276 行)，`/v1/chat/stream` 先语义(421)后查库(426) —— 对「`conversation_id=999` + 最后一条是 assistant」这个请求，两条接口分别回 **404 / 400**（同一种坏请求两个答案）。统一成「先语义后查库」后两条都回 **400**。
    > ⭐ 附带收益：非法消息**零 IO** 就被拒，数据库白省一次往返。

41. 为什么「客户端断开时用 `except BaseException: await db.rollback()` 把账单撤掉」这个方案被否决了？错在哪两个层次？
    > **层次 1：验证的场景是编的。** 六组矩阵用的是「usage 帧先到、内容帧后到」的假帧序，但真实上游的 `usage` **永远在最后一帧**。📎 实测真实帧序下中途断开：`llm_calls` 是空的 —— `record_usage` 从未被调用，**根本没有「半截账单」可撤**。
    > **层次 2：业务方向搞反了。** 上游按**已产出**计费，断开不是退款。`rollback` 一做，这次调用在库里**一行都没有** —— 比「留一行 token=0」更差，月底对账连差额来自哪里都查不出。
    > ⭐ 判据：**「验证通过」只证明「在我构造的场景下成立」。** 先问「这个场景在真实数据里出现吗」。

42. 为什么「断开时补写一行账单」做不到，而「流开始前先写一行 `pending`」可以？
    > 关键在**代码跑在哪个上下文**：
    > | 时机 | 上下文 | 能不能 `await` |
    > |---|---|---|
    > | 流开始前（第一个 `yield` 之前） | 正常请求上下文 | ✅ |
    > | 断开时（`except BaseException` 里） | **已被取消的 cancel scope** | ❌ 任何 `await` 都被二次取消 |
    > 📎 实测断开时：`await db.commit()` 抛 `CancelledError` 并炸出 `ResourceClosedError: This transaction is closed`；`asyncio.shield(commit())` 一样失败。
    > ⭐ 而 **`get_db` 的 `commit()` 跑在中间件退出栈里（`AsyncExitStackMiddleware`），不在被取消的 task 里** —— 所以我们只「登记 + `flush`」，提交交给它。
    > ⚠️ 补充：这个方案在一个**只有 `get_db`、没有中间件**的精简 app 里能成，在真 app（多了 `BaseHTTPMiddleware`）里失败。**复刻环境漏一个中间件，结论就反了。**

43. 流式落库时 `except Exception` 和 `except BaseException` 分别覆盖什么？两个分支的顺序能反吗？
    > | 分支 | 覆盖 | 该做什么 |
    > |---|---|---|
    > | `except Exception` | 上游给坏帧 / `flush` 失败等普通异常 | `call.status = "aborted"`（同步赋值） |
    > | `except BaseException` | 客户端断开（`CancelledError`）、生成器关闭（`GeneratorExit`） | 同上，**且绝对不能 `await`** |
    > ⚠️ **顺序不能反**：`BaseException` 写在前面会把所有普通异常也吃掉，`except Exception` 分支永远不执行。
    > ⭐ 两个分支都只做**同步赋值**、不 `rollback` 不 `commit` —— 落盘统一交给 `get_db`。

44. `LlmCall.status` 的三个值分别是什么含义？「进程崩溃」时 `pending` 行会留下吗？
    > | 值 | 含义 | 谁写 |
    > |---|---|---|
    > | `pending` | 流还没结束（正在进行的请求） | 流开始前 |
    > | `completed` | 拿到完整 usage | `record_usage` |
    > | `aborted` | 明确知道被中断（客户端断开 / 上游异常） | 两个 `except` 分支 |
    > ⚠️ **进程崩溃时 `pending` 一行都留不下** —— 📎 强杀 uvicorn 实测 `llm_calls = []`。因为 `flush()` 只发 SQL、**事务没提交**，进程一死就被回滚。
    > ⭐ 判据：**`flush` ≠ 持久化，只有 `commit` 才写进库。** 想扛崩溃必须在流开始前用独立会话 `commit` 一次。
    > ⭐ 这个列的业务意义：**能算出「中断损耗率」**（有多少调用没拿到 usage），否则账面永远对不上上游账单。

45. 「需要一定会留下的数据（账单 / 审计 / 日志），不要跟请求事务同生共死」—— 这句话在代码上怎么落地？
    > 三个做法，按代价从低到高：
    > | 做法 | 说明 |
    > |---|---|
    > | **两阶段** | 先写 `pending` 行（正常上下文 `flush`），结束时改状态 |
    > | **独立会话** | `async with SessionMaker() as acct:` 自己 `commit`，不共用请求事务 |
    > | **异步通道** | 写消息队列，由独立 worker 落账（阶段 3 规模才需要） |
    > ⭐ 判据：**「这次请求回滚了，这条记录该不该消失？」** 该消失 → 用请求事务；不该消失 → 用上面三个。

46. `usage` 在 DeepSeek 和 OpenAI 的流式响应里出现的位置有什么不同？只处理一处会怎样？
    > | 上游 | 位置 |
    > |---|---|
    > | DeepSeek | 和 `finish_reason` 挤在**同一帧** |
    > | OpenAI（`stream_options.include_usage`） | **单独一帧**，且 `choices` 是空列表 |
    > ⭐ 只处理一处 → **有一半上游记不上账**（而且不报错，静默漏账）。
    > ⭐ 另外要防重复：上游可能在多帧重复给 `usage`，不设开关会**一次调用记成两行 = 重复收费**。
    > 📎 用假上游造两种帧序，两种都落 1 行（`conv=1 / prompt=33 / completion=46 / total=79`）。

47. 流式验收时第一次输出是 `{"detail":"对话不存在：1"}`，查库 0 行。这说明守卫失效了吗？
    > **不能这么推。** 那条 404 来自 pre-flight，请求**根本没进到 `event_source`** —— 自然一行都不会写。
    > 📎 本例的真实原因：中间删过库，`conversation_id=1` 已不存在。
    > ⭐⭐ 判据：**测试失败时先确认「请求真的走到了我想测的那条路径」。** 一个前置校验的 404 / 422 就能让整段测试空转。
    > ⭐ 做法：验证脚本**自带建数据**（先 `POST /v1/conversations` 拿返回的 id），不要依赖写死的 id。

48. 同样一句 `await`，在「`task.cancel()` 之后」和「anyio `CancelScope` 取消之后」表现一样吗？
    > **不一样。** 📎 实测：纯 asyncio 里捕获 `CancelledError` 后，`await asyncio.sleep(0)` / `sleep(0.01)` **都能成功**；anyio cancel scope 取消后，**两个都被再次取消**。
    > ⭐ 机制：asyncio 的 `cancel()` 是**一次性投递消息**，捕获后这次投递就结束；anyio 的 `CancelScope.cancel()` 是把 **scope 状态永久改成「已取消」**，scope 内每个 `await` 挂起点都先查这个开关 → 立刻再抛。
    > ⭐⭐ **你 catch 到的不是「一次异常」，而是「正身处一个已取消的区域」。**

49. 为什么 `call.status = "aborted"` 能成功，而 `await db.commit()` 一定失败？
    > **因为取消只在「`await` 挂起点」生效，同步代码不会被打断。**
    > | 操作 | 会挂起吗 | 会查取消开关吗 |
    > |---|---|---|
    > | `call.status = "aborted"` | ❌ 纯内存写属性 | ❌ 根本不看 |
    > | `await db.commit()` | ✅ 等 IO | ✅ 一看就抛 |
    > ⭐ 属性改完 SQLAlchemy 把它标成 dirty，**落盘交给 `get_db`** —— 它的 `commit()` 跑在中间件退出栈里（另一个 scope），请求 task 被取消它也照样收尾。

50. `asyncio.shield()` 和 anyio 的 `CancelScope(shield=True)` 都能「防取消」吗？
    > **只有后者能。** 📎 在已取消的 scope 里实测：裸 `await` ❌、`await asyncio.shield(coro)` ❌ **同样被取消**、`with anyio.CancelScope(shield=True): await coro` ✅ **成功**。
    > ⭐ `asyncio.shield` 保护的是**里面的协程不被砍**，但 `await shield(...)` **本身仍是一个挂起点** —— 在这个挂起点上照样查开关 → 立刻抛。等于「里面还在跑，你已经不等了」。
    > ⭐ anyio 的 shield scope 是**临时代替掉取消状态**，让里面的 `await` 看到「未取消」。
    > ⚠️ 本项目没用它：只能救回一次 `await`，复杂度不值得。**能靠结构解决的，别靠技巧。**

51. N+1 是什么？N=5 时三种写法各发几条 SQL？N=100 时呢？
    > 「查 1 次主表 + 循环里每行再查 1 次子表」= **1 + N 次**。
    > | N | A 循环 `await` | B `selectinload` | C `join+group` |
    > |---|---|---|---|
    > | 5 | **6 条** 5.3ms | 2 条 4.1ms | 1 条 1.4ms |
    > | 100 | **101 条** 57.7ms | 2 条 4.9ms | 1 条 1.0ms |
    > ⭐ **A 是 O(N)，B 是 O(1)**。⚠️ N=5 时只差 2 倍，看不出问题 —— **小数据测不出来，上线才炸**。

52. 同步 SQLAlchemy 里 N+1 表现是「变慢」，async 里也是这样吗？
    > **不是。** 📎 async 里直接访问 `conv.calls` → `StatementError: (sqlalchemy.exc.MissingGreenlet) greenlet_spawn has not been called`。
    > ⭐ 因为惰性加载要发 SQL，但触发点是「属性访问」这个同步上下文，async 不允许在这里偷偷 `await`。
    > ⭐ 所以 async 项目的 N+1 更多是**「显式循环里的 N 次 `await`」**，不是「忘记预加载」。

53. 只想要「每个对话有几次调用」，该用 `selectinload` 还是 `join + group_by`？为什么？
    > **用 `join + group_by`。** 它只回 1 个数字；`selectinload` 会把**所有子行**取回内存再数。
    > | 需求 | 用哪个 |
    > |---|---|
    > | 只要数量 / 总和 | `join + group_by`（1 条 SQL，只回 1 个数） |
    > | 要子行完整内容 | `selectinload`（1 + 1 条，用 `IN (...)` 批量取） |
    > | 子行特别多 | `selectinload` 要小心，内存会塞下全部子行 |

54. 给列表接口加统计时，为什么必须 `outerjoin` 而不是 `join`？为什么必须 `coalesce`？
    > **`outerjoin`**：用 `join` 会让**没有账单的对话整行消失**（📎 实测新对话直接不见）。
    > **`coalesce(sum, 0)`**：`SUM` 遇到空集返回 `NULL` 不是 `0` → 响应里是 `null`，前端 `total + 1` 变 `NaN`。
    > ⭐ 判据：**「从 A 出发查 A +（可选的 B）」→ 永远用 `outerjoin`。** `join` 回答「同时有 A 和 B 的」，`outerjoin` 回答「所有 A，有 B 就带上」。

55. 能不能直接给 `ConversationOut` 加 `call_count` 字段就好，何必新建一个 `ConversationStatsOut`？
    > **不能，会 500。** `ConversationOut` 是 `from_attributes=True`，从 ORM 对象读字段；`POST /v1/conversations` 创建后返回的 ORM 对象**没有 `call_count` 属性** → pydantic 校验失败 → **500**。
    > ⭐ 所以必须单独定义 `ConversationStatsOut`（继承 `ConversationOut` 加两个字段）：列表用它，CRUD 三接口继续用 `ConversationOut`。
    > ⭐ 这是 [决策 #10](../project/decisions.md#10-契约按用途分家in--patch--out)「契约按用途分家」的又一处落地。

56. `onupdate=lambda: datetime.now(UTC)` 是数据库触发器吗？绕过 ORM 直接写 SQL 会怎样？
    > **不是触发器。** 📎 实测 `sqlite_master` 里 **0 个 trigger**，DDL 里也没有 `ON UPDATE`；实际 SQL 是 `UPDATE convs SET title=?, updated_at=? WHERE id=?` —— **时间由 Python 填好再传进去**。
    > ⭐ 所以**绕过 ORM 手写 `UPDATE` 时 `updated_at` 不会变**。

57. PATCH 一个新标题和 PATCH 同一个标题（内容没变），`updated_at` 一样吗？
    > **不一样。** 📎 实测：改成新值 → `updated_at` 变晚 ✅；改成**同一个值** → **`updated_at` 不变**。
    > ⭐ 因为 SQLAlchemy 有 **dirty check**：新旧值一样就不生成 `UPDATE` 语句，`onupdate` 自然不会触发。

58. 列表接口用 `select(具体列)` 手动组装，但忘了把 `updated_at` 加进 `select()`，会报什么？
    > 📎 实测 **`AttributeError: updated_at`**（`Row._fields` 里没有它）→ 不是客户端错误 → 被兜底处理器转成 **500 INTERNAL_ERROR**。
    > ⭐ 对比：`POST` / `PATCH` / GET 详情返回的是**完整 ORM 对象**，属性都在，所以只有列表接口会炸。
    > ⭐⭐ 判据：**手动组装时，「`select()` 选了哪些列」和「用了哪些属性」必须一一对应。**

59. 为什么同一个 `created_at`，`POST` 返回 `...Z` 而 `GET` 返回没有 `Z`？
    > 值的来源不同：
    > | 场景 | 来源 | tzinfo | 序列化 |
    > |---|---|---|---|
    > | `POST` 刚创建 | Python 侧 lambda 现算 | ✅ aware | `...Z` |
    > | `GET` / `PATCH` | 从 SQLite 读回 | ❌ naive | 无 `Z` |
    > ⭐ SQLite 把 `DATETIME` 存成字符串，读回来就丢了时区。
    > ⚠️ 前端 `new Date("2026-10-28T05:51:54.604445")` 会按**本地时间**解析 → 时区差 8 小时。修法见待办 #45（`AwareDatetime` + `field_serializer`）。

60. `offset` 分页和游标分页在「翻页期间别人删了一条数据」时表现有什么区别？为什么？
    > 📎 实测（10 条数据，每页 5 条，翻页时删掉刚看完的最后一条）：
    > | 方式 | 翻页路径 | 结果 |
    > |---|---|---|
    > | offset | `[1,2,3,4,5,7,8,9,10]` | ⚠️ **漏掉 id=6** |
    > | 游标 | `[1,2,3,4,5,6,7,8,9,10]` | ✅ 完整 |
    > ⭐ 根因：**`offset` 数的是「位置」，位置会随数据增删漂移；游标数的是「值」（`id > 5`），值不会变。**
    > ⭐ 副作用：offset 在**插入**数据时可能**重复**返回同一条（反向漂移）。
    > ⚠️ 这个场景**不需要多用户** —— 同一个人的两个标签页就够了。

61. `limit + 1` 这个技巧是干什么的？比什么更便宜？
    > 多取一条，用来判断「还有没有下一页」：
    > ```python
    > rows = (await db.execute(stmt.limit(limit + 1))).all()
    > has_more = len(rows) > limit
    > rows = rows[:limit]
    > ```
    > ⭐ 比「再跑一次 `SELECT COUNT(*)` 判断」便宜 —— **一次查询同时拿到数据和「有没有下一页」**。
    > ⚠️ 但精确的 `total` 还是要单独 `COUNT(*)`（`has_more` 只是布尔，给不出数字）。

62. `(await db.execute(select(func.count(X.id)))).scalar_one()` 里，为什么不能省掉 `.scalar_one()`？
    > 因为 **`execute()` 返回的不是值，是「结果集容器」**。📎 实测它的类型是 `ChunkedIteratorResult`，`isinstance(result, int)` 为 **False**。
    > | 方法 | 返回 | 多行时 |
    > |---|---|---|
    > | `.all()` | `list[Row]`（嵌套） | 全部 |
    > | `.one()` | `Row` | ⚠️ `MultipleResultsFound` |
    > | `.scalar()` | 第一行第一列的值 | ⚠️ **静默取第一行** |
    > | **`.scalar_one()`** | 第一行第一列的值 | ⚠️ `MultipleResultsFound` |
    > ⭐ `COUNT` 恰好 1 行 1 列，用 `scalar_one()` 把「我假设恰好一行」**写进代码** —— 改查询时立刻炸，而不是静默返回错的数。

63. 对同一个 `Result` 连续调两次 `.all()` 会怎样？
    > 📎 实测：第 1 次 `[(3,)]`，第 2 次 **`[]`** —— **不报错**。`.all()` 之后 `.first()` 返回 **`None`**，也不报错。
    > ⭐ 因为 **`Result` 内部是数据库游标，读到末尾就没了**（一次性消费）。
    > ⭐ 判据：**需要多次读取就先 `rows = result.all()` 存下来。**

64. 写 `stmt.where(...)` 但忘了赋值回去，会发生什么？
    > **条件静默失效，返回全表**（不报错）。
    > ⭐ 因为 SQLAlchemy 的 `select()` 是**不可变描述对象** —— 每个方法都返回**新对象**，不修改原对象。
    > ✅ 正确写法：`stmt = stmt.where(...)`。
    > ⭐ 同类坑：`stmt.limit(...)` / `stmt.order_by(...)` 也必须赋值回去（或直接链式调在 `execute` 里）。

65. 为什么不能把「探数据库」放进 `/health`（liveness）？会引发什么后果？
    > **liveness 失败 = 编排系统重启容器，而重启治不好数据库。**
    > ```text
    > 数据库抖动 → 全部实例 /health 失败 → 全部重启
    >            → 重启后启动要连库，还是失败 → 雪崩
    > ```
    > ⭐ 正确做法：拆两个端点 —— `/health` 只证明进程活着（不检查外部依赖）、
    > `/health/ready` 探库，失败回 **503**（摘流量，不重启）。
    > ⭐ 判据：**liveness 只回答「我的事件循环还在转吗」；任何「别人的问题」都归 readiness。**
    > ⚠️ 反过来：readiness 也只探**自己的关键依赖**（数据库），不探第三方 API。

66. `/health/ready` 探库为什么用 `SELECT 1` 而不是 `SELECT count(*) FROM conversations`？
    > 健康检查会被每秒调用很多次，**不能自己成为瓶颈**。
    > | 方式 | 成本 | 证明什么 |
    > |---|---|---|
    > | `SELECT 1` | 最便宜，不碰表 | 连接可用、能执行语句、能返回结果 |
    > | `count(*) FROM 大表` | 要扫表 | 同上 + 表存在 |
    > ⭐ 另外 SQLAlchemy 2.0 起裸字符串不能执行，必须用 `text("SELECT 1")` 包一下。

67. `curl` 返回 `[000]` 是什么意思？和 503 怎么区分？
    > 📎 实测：`[000]` + **退出码 7** = **连接被拒，服务根本没在跑**。
    > ```text
    > curl.exe -s -o NUL -w "[%{http_code}]" http://127.0.0.1:9999/health
    > [000]      exit code = 7
    > ```
    > 而 503 是**有服务在监听**、只是它自己说「我暂时不能服务」。
    > ⭐⭐ 判据：**看到 `[000]` 先检查服务是否在监听，别急着怀疑代码。**

68. `DATABASE_URL` 指向不存在的目录时，服务会怎样？这说明什么架构问题？
    > 📎 实测：**启动直接失败** —— `lifespan` 里 `engine.begin()` / `create_all` 抛
    > `OperationalError: unable to open database file` → `Application startup failed. Exiting.`
    > | 看法 | 说明 |
    > |---|---|
    > | ✅ 好 | fail-fast，不会带着坏依赖对外服务 |
    > | 🔴 坏 | docker-compose / K8s 里 DB 未就绪时应用 **crash loop**；`/health/ready` 根本没机会回 503（进程已死）|
    > ⭐⭐ 根因：**`create_all` 在启动路径上**（待办 #50）。把 DDL 移到 Alembic 独立部署步骤后，
    > 启动就不需要 DB，`/health/ready` 才能真正承担「报告 503」的职责。

69. SQLite 读回来的 `datetime` 为什么没有 `tzinfo`？它是在**哪一步**丢的？
    > 📎 三段链路：
    > | 阶段 | 值 | `tzinfo` |
    > |---|---|---|
    > | 写入前（Python） | `datetime(..., tzinfo=UTC)` | `UTC` → aware |
    > | bind 格式化后 | `'2026-10-28 05:51:54.604445'` | **没了** |
    > | 读回（Python） | `datetime(2026,10,28,5,51,54,604445)` | `None` → naive |
    > 📎 根因是 `sqlite.DATETIME()._storage_format`：
    > `%(year)04d-%(month)02d-%(day)02d %(hour)02d:%(minute)02d:%(second)02d.%(microsecond)06d`
    > —— **一个时区占位符都没有**。
    > ⭐ 不是「数据库不肯存」，是 **SQLAlchemy 生成字符串时就没写**。
    > ⚠️ 危险推论：`+08:00` 的 13:51 和 UTC 的 13:51 存进去是**同一个字符串**，读回来无法区分。

70. 给列加 `DateTime(timezone=True)` 能修好 SQLite 的时区丢失吗？
    > ❌ **不能，完全无效**。📎 同一份 `Table` 定义：
    > ```sql
    > -- SQLite
    > plain DATETIME,  with_tz DATETIME            -- timezone=True 消失了
    > -- PostgreSQL
    > plain TIMESTAMP WITHOUT TIME ZONE,
    > with_tz TIMESTAMP WITH TIME ZONE             -- 生效
    > ```
    > ⭐ SQLite **没有「带时区的时间类型」**，它的类型声明只是亲和性标签，值实际存 TEXT。
    > `timezone=True` 在 SQLite 下既不改 DDL、也不改 bind 格式、也不改读回结果。
    > ⭐ 判据：**换到 PostgreSQL 时才需要它**；SQLite 阶段加了只是心理安慰。

71. `field_validator` 的 `mode="before"` 和 `"after"` 怎么选？
    > 📎 实测对照：
    > | 输入 | `before` | `after` |
    > |---|---|---|
    > | naive `datetime`（ORM 对象） | ✅ | ✅ |
    > | **字符串** `"2026-10-28T05:51:54"` | ❌ **静默失效** | ✅ |
    > | `None` | ✅ 跳过 | ✅ 跳过 |
    > **before 为什么在字符串时失效**：它拿到的是**原始值**（`str`），
    > `isinstance(v, datetime)` 为 False → 修复被跳过；`after` 拿到的已是 `datetime`。
    > ⚠️ `after` 唯一缺点：**返回值不重新校验** —— 📎 返回 `"我就是个字符串"` 竟然建对象成功，
    > 只在序列化时给 warning；`before` 会抛 `ValidationError`。
    > ⭐ 判据：
    > | 想干的事 | 用哪个 |
    > |---|---|
    > | 把字符串/数字**转换成**目标类型 | `before` |
    > | 对**已校验好**的值做修正（补时区、裁剪、判空） | `after` |
    > | 想让自己写错的返回值被发现 | `before` |
    > ⚠️ 另外：`@classmethod` 跟 mode **无关**，pydantic 对两种 mode **都要求**（📎 不加都抛 `PydanticUserError: cannot be applied to instance methods`）。

72. 接口返回了 `201 Created`，能保证数据已经写进数据库了吗？
    > ❌ **不能**。`get_db` 的 `commit()` 跑在**路由函数返回之后**（依赖的 `yield` 之后）。
    > 📎 实测（patch `AsyncSession.commit` 抛 `RuntimeError("模拟磁盘满")`）：
    > ```text
    > POST /v1/conversations -> 201
    > body -> {"id":2,"title":"提交会失败","created_at":...}
    > 库里共 1 行：id=1（id=2 从未存在）
    > ```
    > 🔴 客户端拿到完整的「成功」响应，数据却没落盘；服务端只在日志留一条未处理异常。
    > ⚠️ 因为**响应已经发出**，`register_exception_handlers` 也救不了（改不了状态码）。
    > ⭐ 触发条件都是产品环境常见的：磁盘满 / 连接池耗尽 / 唯一约束冲突 / 连接被掐断。
    > 修法方向（待办 #54）：`commit()` 提到路由函数内、`return` 之前。

73. `time.time()` / `time.monotonic()` / `time.perf_counter()` 有什么区别？做超时该用哪个？
    > 📎 本机 `get_clock_info` 实测：
    > ```text
    > time          monotonic=False  adjustable=True   GetSystemTimeAsFileTime()
    > monotonic     monotonic=True   adjustable=False  GetTickCount64()
    > perf_counter  monotonic=True   adjustable=False  QueryPerformanceCounter()
    > ```
    > ⭐⭐ 判据：**「多久」用单调钟（`monotonic` / `perf_counter`），「何时」用墙钟（`time.time()` / 数据库 `now()`）。**
    > 📎 实测模拟 NTP 前跳 60 秒（做 30 秒超时）：
    > ```text
    > 真实过去 2s，剩余 30.0s → 继续等
    > 真实过去 3s，剩余 -30.0s → 触发超时  [时钟跳到 +60s]
    > ```
    > 只过去 3 秒，墙钟方案就**误触发**；单调钟剩余 `27.0s` 正常继续等。

74. 「为了避免机器休眠导致超时不触发，把超时改成系统时钟」这个做法对吗？
    > ❌ **反了，这是用一个更严重的故障去换一个更轻的故障。**
    > | | 墙钟 | 单调钟 |
    > |---|---|---|
    > | 时钟被 NTP 校正 | 🔴 **跳变** → 超时误触发 / 永不触发 | ✅ 不受影响 |
    > | 机器休眠 | ✅ 照算 | ⚠️ 可能不计（依平台） |
    > - 休眠时没人等你的请求，超时晚一点触发**通常无害**
    > - 时钟跳变在任何**长期运行的服务器**上都会发生，一次就误杀一片请求
    > ⭐ 真需要「含休眠的经过时间」：Linux 用 `time.clock_gettime(time.CLOCK_BOOTTIME)`，不要退回 `time.time()`。
    > ⚠️ 诚实标注：「休眠期间单调钟到底走不走」我**没有真休眠实测过**，属未实测推断。

75. `httpx` 的 `read timeout = 30` 是指「请求最多跑 30 秒」吗？
    > ❌ **不是。它是「两次读取之间的最长间隔」。**
    > 📎 实测（假上游每 0.4s 发一帧，客户端 `httpx.Timeout(1.0)`）：
    > ```text
    > 收完 12 块，总耗时 4.95 秒 —— 没有超时
    > 对照组：单帧后停 2.5s → [1.03s] ReadTimeout
    > ```
    > ⚠️ httpx 只有 `connect / read / write / pool` 四个**间隔型**超时，**没有总时长上限**。
    > ⭐ 后果：上游每 0.9 秒滴一帧就能让请求**无限期挂着** —— 占连接、占并发名额、账单还在涨。
    > 对一个 LLM 应用尤其危险：**慢速滴答比直接失败更费钱**（待办 #55）。

### Step 11 · 工程化：配置 / 日志 / 安全

1. 为什么"前端直连 LLM API"必然泄露 Key？F12 能看到吗？
   > 前端代码和请求都跑在浏览器里，Key 必然随请求出现在**网络面板（F12）**里，任何人都能看到。
2. "后端中转"架构额外带来的四个收益是什么？
   > ① Key 不出服务端 ② 可加限流/配额 ③ 可记日志与计费 ④ 可做缓存与统一重试。
3. 为什么 LLM 应用的限流比普通接口更紧急？
   > 每次调用**都花钱**且有速率上限；被刷 = 直接烧钱，还会拖垮上游配额导致正常用户不可用。
4. 500 错误要同时满足哪两个目标？怎么做到？
   > ① **不泄露**内部细节 ② 又能**被定位**。做法：返回客户端一个请求 id，服务端日志里带同一个 id。
5. `get_settings()` 为什么要包一层而不是直接 import `settings`？
   > 造出**可替换的接缝**：测试能 `dependency_overrides` 换掉它，不改业务代码。

### Step 12 · 测试 FastAPI

1. `TestClient` 为什么不启服务器就能测接口？
   > 它按 **ASGI 协议在本进程内直接调用 app 对象**，不经过网络（继承自 `httpx.Client`，用自定义 transport 转发）。
2. `with TestClient(app)` 和 `TestClient(app)` 差什么？症状是什么？
   > `with` 会**执行 lifespan**（启动/关闭钩子）。不用 `with` 时 lifespan 不跑 → 全局 client/连接池没建、`app.state` 里没东西 → 依赖取不到。
3. `ASGITransport` 的好处和**代价**分别是什么？
   > 好处：能用 `httpx.AsyncClient` 的异步接口（可 `await`）、不启服务器。代价：**不跑 lifespan**（除非加 `LifespanManager`）、不经过真实网络栈。
4. 测 SSE 要断言哪三件事？
   > ① **分多帧到达**（不是一次性）② 帧格式正确（`data:` + 双换行）③ 结束标记 / 错误帧行为正确。
5. 测试里为什么绝不能真调 LLM？怎么替换？
   > 慢、要钱、结果**不确定**（无法断言）。替换：`app.dependency_overrides[get_llm_client] = 假 client`（`MockTransport` 或假生成器）。

### Step 13 · 部署

1. `--reload` 为什么不能进生产？
   > 它盯文件、改动就**杀掉重启** → 多 worker 下会丢请求，且监控整个目录有额外开销。生产应"发布新版本再切"。
2. `--workers` 设多少？它带来哪两个"内存不共享"的后果？
   > 常按 CPU 核数（`2*CPU+1`）或按内存/负载调。后果：① 进程内缓存/变量**各算各的**（不能当共享状态）② 后台定时任务**每个 worker 都会跑一遍**（要加锁或独立进程）。
3. 流式上线后"不流了"，按什么顺序排查？
   > ① nginx 等**代理缓冲**（`X-Accel-Buffering` / `proxy_buffering off`）② **中间件**是否缓冲了响应体 ③ 应用代码是否真在**分帧** `yield`。
4. `proxy_read_timeout` 不调大会怎样？
   > 上游长时间不返回（LLM 生成慢）时，代理认为超时 → 客户端看到 **504**；表现为"生成超过 N 秒必断"。
5. 为什么健康检查里不该做深度依赖检查？
   > 健康检查频率高；深检会给自己和依赖加额外负载，且依赖抖动会让"能服务"的实例被**误杀**。

---

## 附：与本文件的维护约定

- **新增自检题**时：题目与简要答案写进本文件对应阶段/步骤，**不要在阶段笔记里复制一份**；
  阶段笔记里保留一个指向本文件的小节标题即可（便于跳转与锚点不变）。
- **深度原理、实测过程、完整实验数据**仍留在阶段笔记里（本文件只放"要点级"答案）。
- 标记 `📎` 的题，笔记里有配套实测数据，复习时值得回看。

---

## 更新日志

| 日期 | 变更 |
|---|---|
| 2026-10-16 | 初版：从 [stage0-engineering-basics.md](stage0-engineering-basics.md)（10 节）与 [stage1-fastapi.md](stage1-fastapi.md)（13 节）汇总全部自检题并配简要答案；阶段1 Step 1 的批改订正（🟡 三处）并入答案；阶段1 Step 5 补入本会话新增的 3 道（依赖执行时机 / 覆盖表全局性 / 参数默认值） |
| 2026-10-17 | 阶段 1 · Step 5 补 7 题（第 9~15 题）：1.4d-1 抽取共用工厂 4 题（改动点数量 / 为何不 yield / 重构验收标准 / 模块放哪层）+ 1.4d-2 真实调上游 3 题（硬编码 vs 真实、上游 401 为何变 500、怎么不联网测试） |
| 2026-10-17 | 阶段 0 · Step 2 补 2 题（第 5~6 题）：editable 安装的本质（只写指针不复制代码，怕路径变化不怕代码变化）/ 既然 `.venv` 里存着绝对路径为何还能随便删（配方 vs 成品）。来源：改名时踩到 `.venv` 指针悬空的实测 |
| 2026-10-17 | **订正**阶段 1 · Step 6 第 3 题答案：`lifespan` 的 `yield` dict 进的是 `request.state`，**不是** `app.state`（`TestClient` 实测）；同批实测：不用 `with TestClient(...)` 时 lifespan **完全不执行** |
| 2026-10-17 | 阶段 1 · Step 6 补 3 题（第 6~8 题）：`status` 常量 vs 裸数字 / `Literal` 路径参数为何不合适（📎 422 + 泄露清单）/ `return` vs `raise` `HTTPException`（📎 500 与"200 谎报"两例） |
| 2026-10-17 | 阶段 1 · Step 6 再补 3 题（第 9~11 题，6.2a）：上游 401 为何译成 502（📎 透传反例）/ `ConnectError` 属哪一支、有无 `.response` / 业务 bug 为何必须留在 500 |
| 2026-10-17 | 阶段 1 · Step 6 再补 3 题（第 12~14 题，6.2b）：assistant 收尾返回 400 是否合理 / 改成"往前找 user"的取舍 / `detail` 回显 `role` 与 `content` 的风险差异 |
| 2026-10-18 | 阶段 1 · Step 6 补 3 题（第 15~17 题，6.3a）：未登记 `code` 的兜底是否合理 / 忘注册处理器为何是静默 500 / 三种错误形状并存算不算缺陷 |
| 2026-10-18 | 阶段 1 · Step 6 补 3 题（第 18~20 题，6.3b）：`HTTPException` 是否会被 `Exception` 兜底吃掉 / `request_id` 怎么用、多机补什么 / 兜底处理器自炸的结果 |
| 2026-10-18 | 阶段 1 · Step 6 补 3 题（第 21~23 题，6.4）：`lifespan` 与 `yield` 依赖的本质区别 / `app.state` 在测试里怎么换、为何比覆盖表麻烦 / 共享 client 的并发安全性 |
| 2026-10-18 | 阶段 1 · **Step 4** 补 5 题（第 6~10 题，4a/4b）：`response_model` 与返回注解冲突时哪个生效 / 缺必填字段为何是 500 / `list[dict]` vs `list[ModelItem]` / 上游缺 `id` 为何落到 500 / `total` 为何由我们算 |
| 2026-10-19 | 阶段 1 · Step 7 订正第 1 题答案（中间件顺序：**后注册的在最外层**，附源码与实测），第 2 题补 `_StreamingResponse` 实测，新增 2b（`call_next` 做了什么、里层抛异常时如何） |
| 2026-10-19 | 阶段 1 · Step 7 补第 3~5 题（`app.state` vs `request.state` / 500 头由谁加 / 验证中间件的"四看"）与第 6~8 题（头名哪些差异有语义 / 常量防什么不防什么 / 常量放哪层的判据） |
| 2026-10-19 | 阶段 1 · Step 7 补第 9~10 题：`finally` 里写访问日志的理由（三种写法实测对比）/ `logger.warning` 为何是临时手段、级别描述的是重要性而非错误 |
| 2026-10-19 | 阶段 1 · Step 7 **订正第 5 题**（`["*"]` + credentials **不会**被浏览器拒绝，而是静默回显任意 Origin），补第 6~8 题（非白名单仍 200 但无 ACAO / ACAO 为何是回显 / 预检失败是 400 且能打不存在路径） |
| 2026-10-19 | 阶段 1 · **Step 8** 补第 5~7 题：`async def` 里调同步库为何比 `def` 更糟（📎 25 倍）/ 线程池超限是排队不是拒绝（📎 45 并发 0.87s）/ CPU 密集为何线程池无效（📎 GIL 0.96x vs 进程池 1.28x） |
| 2026-10-19 | 阶段 1 · **Step 9** 补第 7~10 题（9a）：`curl -w` 两个时间指标如何证明流式（📎 0.014s vs 1.85s）/ `transfer-encoding: chunked` 为何是必要条件 / `TestClient` 证明不了分批 / 流中抛异常客户端的真实报错 |
| 2026-10-19 | 阶段 1 · **Step 9** 补第 11 题：`time.sleep` 与 `asyncio.sleep` 在异步生成器里的真实差别（📎 单请求都能流 0.023/1.026，并发探测 `ttfb` 0.003→0.753） |
| 2026-10-19 | 阶段 1 · **Step 9** 补第 12~16 题（生成器基础）：`yield` vs `return` + 冻结证据 / 为什么必须 `async def`+`yield` / 传 `str` 会按字符发 6 次 / 谁在拉（`async for chunk in body_iterator`）/ 生成器不能模块级复用（二次遍历得 `[]`） |
| 2026-10-19 | 阶段 1 · **Step 9** 补第 17~18 题（Python 字面量基础）：`f` 前缀去掉后大括号原样输出 / `\n` 是**一个字符**、`\n\n` 的第二换行构成空行 → 只写一个 `\n` 时三行挤成 1 个事件且**不报错** |
| 2026-10-19 | 阶段 1 · **Step 9** 补第 19~20 题（帧 vs 时间）：帧是数据单位不是时间单位（📎 10 帧 1.861s / 2 帧 0.383s / 201 帧 0.002s）/ 假数据必须 `sleep` 而真实上游不需要（📎 无 sleep 时 9 帧全落 67.7ms；假上游转发法 233.8→699.9ms） |
| 2026-10-19 | 阶段 1 · **Step 9** 补第 21~23 题（分工与推进机制）：`StreamingResponse` 干了什么（📎 同一生成器三种用法）/ 手写 ASGI 三段样板（📎 8095 实测仍逐帧）/ 循环外 `yield` 会不会推进（📎 第 4 次拿到 DONE、第 5 次 StopAsyncIteration） |
| 2026-10-19 | 阶段 1 · **Step 9** 补第 24 题：代码里没有 `async for` 时谁在推进（📎 调用栈实测指向 `starlette/responses.py:253`） |
| 2026-10-20 | 阶段 1 · **Step 9** 补第 28~31 题：GET vs POST 的语义判据（📎 FastAPI 允许 GET 带 body）/ `choices` 为何取 `[0]`（📎 DeepSeek 只支持 n=1）/ `choices[0]` ≠ index 0（📎 模拟 n=2 交织成乱码）/ 语义缓存是否创新（📎 GPTCache 与 RedisVL 原文） |
| 2026-10-20 | 阶段 1 · **Step 9** 补第 32~35 题：`async with` 关的到底是什么（📎 读连接池属性）/ `break` 会销毁连接（📎 break 池内 0 vs continue 池内 1）/ 三层 chunk 的类型 / `usage` 里该监控什么（📎 reasoning 占 85%） |
| 2026-10-21 | 阶段 1 · **Step 9** 补第 37~38 题：五类帧的分类与产生顺序（📎 64 帧实测）/ 64 帧→9 帧的映射（丢弃 57、自造 1、拆分 1） |
| 2026-10-21 | 跨阶段 · 补第 39~41 题（上游三层失败模型 / 静默错误为何更危险 / 防御性编程边界）：配套规范 §十四 |
| 2026-10-21 | 跨阶段 · 补第 42~44 题（**封层**）：错误翻译该写在哪（三方案对比）、适配器契约与"流开始后"的例外、`raise_for_status` vs `>= 400`。配套规范 §14.7、笔记专题 9 |
| 2026-10-21 | 跨阶段 · 补第 45~47 题（**9b-4a 落地**）：pre-flight 的机制与代价、`stream` 默认值事故为何工具抓不到、同一业务规则重复写在两条路由的代价。配套规范 §14.7/§14.8、笔记专题 9 ⑧~⑩ |
| 2026-10-21 | 跨阶段 · 补第 48~49 题（**协作与单一真相**）：单一真相原则的判据（为何不能只看"有没有重复代码"）、AI 如何评估学习者要求的可靠性（三档 + C 档四步 + 双向）。配套规范 §4.6/§2.3、笔记专题 10/11 |
| 2026-10-22 | 阶段 1 · **Step 9** 补第 50~52 题（**流式静默失败三层防线**）：类型标注不是运行时保证（📎 `mypy: Statement is unreachable`）、`STREAM_NO_CONTENT` 为何不能靠状态码表达、`content_frames` vs `raw_chunks`、三层判据与职责边界。配套笔记专题 12、规范 §14.5 |
| 2026-10-22 | 阶段 1 · **Step 9** 补第 53~55 题（**9b-4b-2 落地**）：`except Exception` 为何已豁免 `CancelledError`、拿到 `STREAM_FAILED` 该怎么展示、客户端断开为何无需专门代码（两处各负责一半）。配套笔记专题 12 ⑦ |
| 2026-10-23 | 阶段 1 · **Step 9** 补第 57~59 题（**全生命周期路径**）：21 步完整路径与两个不可逆时刻 / 客户端断开的三问（不进 except、进 finally、不发 DONE）/ 守卫放错位置为何是设计错误（📎 `Statement is unreachable`）。配套笔记 §9.9 三张全景图 |
| 2026-10-23 | 阶段 1 · **Step 9** 补第 60 题（**四个单位**）：token / 帧 / 行 / 字节块的定义与实测计数（📎 15 字节块 / 75 帧 / 6 片段）；「行」是协议分帧符而非内容换行（📎 JSON 转义成 `\n` 两字符）；不转义时内容会静默丢失。配套笔记 §9.2e |
| 2026-10-23 | 阶段 1 · **Step 9** 补第 61 题（**接收流式 vs 返回流式**）：一句话判据（第一个有用字节的时刻）、必须等完整的 4 类、必须流式的 4 类、2×2 组合矩阵、两个易错点（体积 vs 时间 / 整块数据 ≠ 非流式接收）、协议自足性。配套笔记 §9.10 |
| 2026-10-24 | 阶段 1 · **Step 10** 补第 6~7 题（**引擎生命周期**）：engine 为何模块级单例（决定性：非请求上下文可用）/ `create_async_engine` 不连库（📎 `Test-Path app.db` = False）。配套笔记 §10.3 |
| 2026-10-24 | 阶段 1 · **Step 10** 补第 8~9 题（**连接池与 `async with`**）：关闭指令在 `__aexit__` 而非 `with` 行（📎 异常路径也执行）/ `yield` 必须 inside（📎 放外面 → 启动阶段就关）/ 复用 vs 新建 6.28 倍（📎 20 次请求 1 条连接 vs 20 条）。配套笔记 §10.3b |
| 2026-10-25 | 阶段 1 · **Step 10 订正**：原 Q4「不 raise → 客户端收到 200」**是错的**。📎 实测 FastAPI 0.143.0 有专门守卫：客户端仍是 500 + 统一形状，但日志被 `FastAPIError: Response not awaited...` 顶替且 `__cause__ = None` → **根因全丢**。配套笔记 §10.4 已重写 |
| 2026-10-25 | 阶段 1 · **Step 10** 补第 10~11 题（**POST 落地**）：`title=payload` vs `payload.title` 与 mypy 的盲区（📎 `**kwargs` 是 `Any`）/ `refresh` 何时才有必要（📎 Python `default` vs `server_default`）。配套笔记 §10.5 |
| 2026-10-25 | 阶段 1 · **Step 10** 补第 12~14 题（**GET 列表**）：`.scalars()` 是取第一列不是转换（📎 选多列时静默丢数据）/ `list(...)` 是给 mypy 看的（📎 运行时本来就是 list；「运行时对」≠「类型对」）/ 空表返回 `200 []` 不是 404。配套笔记 §10.5 |
| 2026-10-25 | 阶段 1 · **Step 10** 补第 15~17 题（**GET 详情 / 404**）：`abc` 422 vs `999` 404 谁拒的（📎 422 时函数体没跑）/ 不判空 → `ResponseValidationError` → 500（📎 不是 AttributeError）/ 固定词与路径参数的路由顺序（📎 写反 → 422，固定路由永远走不到）。配套笔记 §10.5 |
| 2026-10-25 | 阶段 1 · **Step 10** 补第 18~19 题（**DELETE / 204**）：204 的语义（📎 改 200 后客户端收到 `null`，且"什么都没做"也能伪装成功）/ 204 带 body 在**注册路由时**就 AssertionError / DELETE 幂等性（第二次 404 合法）。配套笔记 §10.5 |
| 2026-10-25 | 阶段 1 · **Step 10** 补第 20~22 题（**裸 `raise` 的时机**）：`except: raise` 是纯噪音（📎 帧数与不写 try 完全相同）/ `raise e` 多一帧（📎 3 → 4）/ `finally: rollback` 在**正常路径也会跑**（📎 `COMMIT, ROLLBACK, CLOSE`）。配套笔记 §10.4 末尾「裸 `raise` 什么时候用」 |
| 2026-10-25 | 阶段 1 · **Step 10** 补第 23~25 题（**PATCH / 部分更新**）：空 body 为何必须拒（必填字段是免费的 bug 探测器）/ `missing` vs `string_type` / `PATCH` vs `PUT` + `exclude_unset`。配套笔记 §10.5 |
| 2026-10-25 | 阶段 1 · **Step 10** 补第 26~28 题（**请求长啥样 / body 为空的两种含义**）：请求三块结构与 id 在哪 / `loc` 层数区分两种「空 body」/ 「信息缺失」vs「内容非法」两个层次。配套笔记 §10.5 |
| 2026-10-26 | 阶段 1 · **Step 10** 补第 29~33 题（**外键 / 关系 / 索引**）：`ForeignKey` vs `relationship` 两个层面 / `cascade` 五种写法实测 / 前向引用为什么要引号 / 索引为什么是 O(log n)（📎 25 倍 + 规模曲线）/ 索引三个代价。配套笔记 §10.6a §10.6b |
| 2026-10-26 | 阶段 1 · **Step 10** 补第 34~36 题（**索引内部结构**）：索引项 = `(列值, rowid)` 不需要算 / 顺序按列值不按 rowid、键可重复 / 删行要动所有索引、主键为何不用额外索引。配套笔记 §10.6b-补 |
| 2026-10-26 | 阶段 1 · **Step 10** 补第 37 题（**PRAGMA foreign_keys**）：SQLite 默认不强制外键 / 为什么必须挂 `connect` 事件 / `sync_engine` 与事件名的选择。配套笔记 §10.6b-1 |
| 2026-10-28 | 阶段 1 · **Step 10** 补第 69~72 题（**时间字段 / validator mode / 提交时机**）：UTC 在哪一步丢（📎 `_storage_format` 无时区占位符）/ `DateTime(timezone=True)` 在 SQLite 下 DDL 不变（📎 对比 PostgreSQL）/ before vs after 判据（📎 字符串输入下 before 静默失效、after 返回值不重校验）/ 「返回 201」≠「已提交」（📎 commit 抛异常后客户端仍收到完整响应体）。配套笔记 §10.6d-4a、待办 #30 #54 |
| 2026-10-28 | 阶段 1 · **Step 10** 补第 73~75 题（**时钟选择 / 超时语义**）：三个时钟的 `adjustable` 差异（📎 `get_clock_info` 实测）/ 「改系统时钟避免休眠不计时」为何是反向做法（📎 模拟 NTP 前跳 60s 时墙钟 3 秒误触发）/ `read timeout` 是间隔不是总时长（📎 read=1s 而请求跑满 4.95s 不超时）。配套 [tools-reference §12](tools-reference.md)、待办 #55 |
| 2026-10-23 | 阶段 1 · **Step 9** 补第 56 题（**宽松字段三档**）：静默收窄 / warning / error 的判据（📎 `finish_reason=''` 误报警那次的教训）。配套规范 §14.4 ⑥、笔记专题 12 ⑤ |
