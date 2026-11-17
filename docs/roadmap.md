# 路线图（Roadmap）

> 这个文件只回答三件事：**现在在哪、下一步做什么、每个阶段怎么算完成。**
>
> | 你想查 | 去哪 |
> |---|---|
> | 逐条历史（做了什么 / 证据 / 坑） | [DEVLOG.md](DEVLOG.md) |
> | 未完成的编号清单（#1 ~ #82） | [todos.md](todos.md) |
> | 离上线还差什么（七道门 / 档期） | [production-readiness.md](production-readiness.md) |
> | 学习规划与阶段判据（个人向） | [../notes/career-plan.md](../notes/career-plan.md) |

**最后更新**：2026-11-14

---

## 一、当前状态

| 阶段 | 计划周期 | 实际 | 状态 |
|---|---|---|---|
| 阶段 0 · 工程基础 | 1 ~ 2 周 | 2026-10-07 ~ 10-14 | ✅ 已完成（`Dockerfile` 顺延到 Step 13） |
| **阶段 1 · FastAPI + 数据库** | 2 ~ 3 周 | 2026-10-14 ~ | 🟡 **进行中**：Step 1 ~ 12 ✅；**Step 13 部署未开始** |
| 阶段 2 · LLM 原生 API | 2 周 | — | ⬜ 未开始 |
| 阶段 3 · RAG | 3 ~ 4 周 | — | ⬜ 未开始 |
| 阶段 4 · Agent + 部署 | 3 ~ 4 周 | — | ⬜ 未开始 |

图例：⬜ 未开始 / 🟡 进行中 / ✅ 已完成 / ⛔ 阻塞

**阶段 1 已完成的部分**：HTTP/ASGI 地基 → 三段参数 → 依赖注入 → 错误处理与 `lifespan` →
中间件与 CORS → 异步 → SSE 流式 → 上游适配器封层 → 数据库与账单 → 工程化（配置/日志/安全）→
自动化测试（95 个用例、分支覆盖 92%）→ CI。

**Step 14（架构盘点）已并入文档**：不需要单独「做完」，它的产物就是
[architecture.md](architecture.md)，随提问继续增补。

---

## 二、下一步：Step 13「部署」拆成 6 个子阶段

> **档期**：全部 `P1`（第一次发版之前）。**形态**：docker-compose + nginx（单机完整栈，本地复现生产形态）。
> **鉴权方案**：API key → 内部用户（中间件解析出 `owner_id`，为将来换成真正的用户表留好形状）。
> 每个子阶段的完成判据必须是**一条命令 + 一组可见输出**，不是「代码写完了」。
>
> ⚠️ **执行顺序（2026-11-16 调整）**：原为 `13a→13b→…`，现改为 **`13b→13c→13d→13a→13e→13f`**。
> 两个理由：① 本机**没有 Docker / 无 WSL / 非管理员**，13a 只能"写出来"不能"证明它对"
> （见 [dev-environment.md](dev-environment.md) §8）；② 13b 要改启动路径（`create_all` 退出 `lifespan`），
> **先定启动路径再封装镜像**，compose 只需写一次。

| 执行序 | 子阶段 | 做什么 | 关联待办 | 完成判据 | 硬依赖 |
|---|---|---|---|---|---|
| **①** | **13b 启动路径与迁移** ✅ **2026-11-16 完成** | Alembic 接管 DDL；`lifespan` 移除 `create_all`；启动打印生效配置白名单 | [#50](todos.md) [#77](todos.md) | ① DB 未就绪时服务**能起来**（`/health/ready` 503，而非进程退出）；② `alembic upgrade head` 建出的表与模型一致（✅ 13b-2a 已由 `tests/test_migrations.py` 钉住）；③ 启动第一屏打印 6 项配置，**不含** `api_key` | — |
| **②** | **13c 请求生命周期** ✅ **2026-11-17 完成（c-1 ~ c-5）** | 拆解：**c-1** ✅ 500 补 CORS（[#57](todos.md) 关闭）· **c-2** ✅ DB 不可用 → 503（[#83](todos.md) 关闭）· **c-3** ✅ 上游总时长上限（[#55](todos.md) 关闭）· **c-4** ✅ `commit` 时机（[#54](todos.md) 关闭）· **c-5** ✅ 优雅停机（决策 39） | [#55](todos.md) [#57](todos.md) [#54](todos.md) [#83](todos.md) | ① ✅ 慢速滴答上游被掐断（📎 0.61s）；② ✅ 500 带 `Access-Control-Allow-Origin` 且 `request_id` 可读；③ ✅ 模拟 commit 失败**不再**返 201（📎 三个写接口全 500）；④ ✅ 发版时在途 SSE 跑完或明确超时（📎 真信号探针）；⑤ ✅ DB 不可用时业务端点 **503** | 13b |
| **③** | **13d 访问控制** 🟡 **2026-11-17 开始（d-1 ✅）** | 拆解：**d-1** ✅ 身份表 `users` + `api_keys`（只存 sha256，决策 40）· **d-2** 鉴权依赖 + `conversations.owner_id NOT NULL`（同步落地）· **d-3** 归属过滤（越权 **404**）· **d-4** 限流（按 key，墙钟）· **d-5** `python -m app keys` 运维命令 | [#36](todos.md) [#37](todos.md) | ① 换 key 看不到也删不掉别人的对话；② 跨用户访问 **404**；③ 超阈值 **429 + `Retry-After`** | 13b + 13c |
| **④** | **13a 容器化底座** | `Dockerfile`（多阶段 · 非 root · exec 形式 CMD）+ `.dockerignore` + `docker-compose.yml`（app + nginx + **一次性 migrate 服务**） | [#49](todos.md) [#84](todos.md) | `docker compose up` → 经 nginx 访问 `/health` 200；镜像内无 `.venv`/`.git`/`tests`；进程非 root；`stop` 时收到 SIGTERM；**空库时迁移先跑完**，`POST /v1/conversations` 返回 201 | 13b（启动路径定稿）· **需先装 Docker** |
| **⑤** | **13e 可观测** | 访问日志带客户端 IP（`X-Forwarded-For` 只信任自己那层）· 日志 JSON + 按天轮转 · 指标最小集 | [#56](todos.md) [#51](todos.md) [#66](todos.md) | ① 每行日志可被 `ConvertFrom-Json` 解析；② 日志有客户端 IP；③ `/metrics` 能读请求数 / 5xx 比例 / p99 / 池占用 | **13a**（XFF 需真实 nginx） |
| **⑥** | **13f 压测定容量** | k6 / locust 打真实并发；把「闸门 4 / 池 15」换成实测数字 | [#76](todos.md) | 一张表：并发 N 时的 p95 首字节 / 错误率 / DB 池 `checkedout` / 上游 429 次数 | **13e**（要读指标） |

### 13b 内部再拆 3 小步（一次一个可验证单元）

| 小步 | 内容 | 判据 |
|---|---|---|
| **13b-1** ✅ | `uv add alembic` + `alembic init -t async` + 配 `env.py` + autogenerate 出初始迁移 | ✅ **2026-11-16 完成**：项目内实测 **3 对象、差异 0**；四步验证（upgrade / check / downgrade / upgrade）全通；四道门全绿 |
| **13b-2** ✅ **2026-11-16 完成（2a + 2b-1 + 2b-2）** | 拆成 2a / 2b，**先加守卫再拆**：<br>**13b-2a** ✅ 2026-11-16：建 `tests/test_migrations.py`（`alembic check` 无漂移 + 迁移 DDL 与 `create_all` 逐字一致）<br>**13b-2b-1** ✅ 2026-11-16：`conftest.py` 改跑真实迁移（`migrated` session fixture + 表存在断言），测试不再依赖 `create_all`<br>**13b-2b-2** ✅ 2026-11-16：`lifespan` 移除 `create_all`；`/health/ready` 两态写成用例（200 / 503） | ① ✅ DB 不可用 → 服务**起得来** + 503（📎 真进程实测：进程 ALIVE / `/health` 200 / `/health/ready` 503）；② ✅ **97 个**用例全绿；③ ✅ 迁移写错时 CI 会红（3 个变异 6 条全红） |
| **13b-3** ✅ 2026-11-16 | 启动打印生效配置白名单（[#77](todos.md) 关闭） | ✅ 启动第一屏 7 项（6 旋钮 + 脱敏库标识）；📎 不含 `api_key` / 完整 `database_url` / 主机 |

### 为什么是这个顺序

| 顺序 | 理由 |
|---|---|
| 启动路径最先 | 它改的是**进程怎么活**：DDL 移出启动路径既是「迁移工具接管」，也是「DB 未就绪不再 crash loop」。容器化必须建在定稿的启动路径上 |
| 生命周期先于访问控制 | 13c 改所有请求的公共路径，13d 改所有端点 —— 先公共后端点，回归里只变一个变量 |
| 鉴权先于限流 | 没有「这个请求属于谁」，限流只能按 IP，而 IP 在反向代理后面不可靠 |
| 容器化先于可观测 | `X-Forwarded-For` 只信任自己那层代理 —— 没有 nginx 就没法验证这条 |
| 指标先于压测 | [#76](todos.md) 要读 p95 / 池占用，没有 13e 只能人工计时，数字不可信 |

### 不在 Step 13 范围内的 P1

| 待办 | 为什么移出 |
|---|---|
| [#63](todos.md) 拆出 `services/` 层 | 不改变「能不能上线」，只影响「改起来累不累」；独立成 Step 14，或推到加检索功能前 |
| [#61](todos.md) `total` 的 `COUNT(*)` | 同上；加 `owner_id` 后变成带条件计数，与 13d 一起重估即可 |

## 三、阶段定义与验收判据

> 每个阶段的**内容 / 产出 / 验收标准 / 状态**在
> [../notes/career-plan.md](../notes/career-plan.md) §三「学习路线」。
> 这里不复制 —— 那份文件是「我要学什么」，本文件是「这个项目做到哪」。

---

## 四、路线分岔（保留提醒）

- **LLM 应用 / AI 工程师**（当前选择）：FastAPI + RAG + Agent + 工程化，PyTorch 只需理解层面。
- **大模型算法工程师**：必须 PyTorch、从零实现 Transformer、分布式训练、SFT/DPO/RLHF、推理优化。

**重新评估的时点**：阶段 3（RAG）完成后。详见 [../notes/career-plan.md](../notes/career-plan.md) §六。
