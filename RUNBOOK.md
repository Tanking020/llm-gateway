# RUNBOOK · 运行与展示速查

> **按「我要做什么」查。** 每条命令都能直接抄。
> **只有两平台不同时才分两列** —— 只有一列 = Windows / Linux 都能直接跑。
> Windows 侧是 **PowerShell 5.1**（不支持 `&&`、`||`，用 `;` 串联）。
> 原理与取舍不在这里 —— 见 [§14](#14-去哪儿看什么)。

## 索引

| 我要做什么 | 去哪 |
|---|---|
| 第一次把项目跑起来 | [§1](#1-第一次跑起来一次性) |
| 日常起服务 / 改配置 | [§2](#2-日常起服务) |
| curl 调接口（鉴权 / 流式 / 会话 / 账单） | [§3](#3-调接口curl-配方) |
| 提交前跑质量门 / 只跑某条测试 | [§4](#4-质量门与测试) |
| 改了 `models.py` → 生成迁移 | [§5](#5-改数据库迁移) |
| 用容器起整套（生产形态） | [§6](#6-容器生产形态) |
| 看日志 / 看指标 / 验告警规则 | [§7](#7-看日志与指标) |
| 压测定容量 | [§8](#8-压测) |
| 签 / 列 / 撤 API key | [§9](#9-api-key-运维) |
| 验优雅停机 | [§10](#10-优雅停机验收) |
| **上线前逐条核对** | [§11](#11-上线前检查清单) |
| **给别人演示（5 分钟）** | [§12](#12-演示动线5-分钟) |
| 出问题了，先跑什么 | [§13](#13-排查症状--先跑什么) |
| 某概念 / 决策 / 待办在哪 | [§14](#14-去哪儿看什么) |

---

## §1 第一次跑起来（一次性）

| 步 | PowerShell | bash |
|---|---|---|
| 还原依赖 | `uv sync` | `uv sync` |
| 建配置 | `Copy-Item .env.example .env` | `cp .env.example .env` |
| 填密钥 | 编辑 `.env`，把 `LLM_API_KEY` 那行改成真值 | 同左 |
| 验上游连通 | `uv run python -m app.main ping` | 同左 |

成功标志：`可用模型 N 个：...`。

⚠️ `ping` 不带密钥只会打印「未配置 LLM_API_KEY」并以 **1** 退出 —— 故意的（避免拿 `Bearer None` 去请求，报成误导性的 401）。
✅ **17 个旋钮全部在 `.env.example` 里有注释**（默认值 + 取值范围 + 反向约束）。`.env` 里只留你真正要改的那几行即可，其余删掉也照样生效。

---

## §2 日常起服务

```bash
uv run python -m app                 # 监听地址/端口/reload 全部读 .env
```

打开 <http://127.0.0.1:8000/docs>（仅 `APP_ENV=dev` 时开）。

| 想改什么 | 改 `.env` 哪个键 |
|---|---|
| 端口被占 | `PORT`（`HOST` 一般不动） |
| 开自动重载 | `DEBUG=true` |
| 关交互式文档（生产） | `APP_ENV=prod` |
| 换模型 | `LLM_MODEL` |
| 上游地址（换假上游也用它） | `LLM_BASE_URL` |

⚠️ **不要用** `uvicorn app.api.app:app --reload` —— 它**静默绕过** `HOST` / `PORT` / `DEBUG`（`.env` 写 `PORT=9001` 也不会生效）。
⚠️ `APP_ENV=prod` 且 `DEBUG=true` 会**拒绝启动**（有意为之）。

---

## §3 调接口（curl 配方）

⚠️ PowerShell 里写 **`curl.exe`**（裸 `curl` 是 `Invoke-WebRequest` 别名，参数不兼容）。
**除 `/health`、`/health/ready`、`/metrics`、`/v1/models*` 外，全部要 `X-API-Key`。**

⚠️ **`/docs` 里点 "Try it out" 会一律 401** —— 本项目把 key 从 `request.headers` 里读（不是 `Header(...)` 参数），
所以 OpenAPI 里**没有** `X-API-Key` 字段，`/docs` 也就没有地方填它（见待办 **#94**）。
**要带 key 试调，用下面这张表，不要用 `/docs`。** `/docs` 只用来看契约与响应模型。
⚠️ 另外 `/docs` **看不到逐帧流式**（它等响应读完才显示），也不会经过 nginx（直连 8000）——
反代层的 413/502/504 与 SSE 缓冲行为只能在 §6 的 80 端口上验。

先设一个环境变量（§9 签出来的明文）：

| PowerShell | bash |
|---|---|
| `$env:KEY = "sk_xxx"` | `export KEY=sk_xxx` |

| 要做的事 | 命令（两平台只差 `curl.exe` / `curl`） |
|---|---|
| 活着 | `curl -s http://127.0.0.1:8000/health` |
| 就绪（DB 通不通） | `curl -s http://127.0.0.1:8000/health/ready` |
| **非流式**对话 | `curl -s http://127.0.0.1:8000/v1/chat -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"你好"}]}'` |
| **流式**（SSE） | `curl -N -s http://127.0.0.1:8000/v1/chat/stream -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"列出三种排序算法"}]}'` |
| 建会话 | `curl -s -X POST http://127.0.0.1:8000/v1/conversations -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"title":"第一次对话"}'` |
| 列表（含账单统计） | `curl -s "http://127.0.0.1:8000/v1/conversations?limit=20" -H "X-API-Key: $KEY"` |
| 删会话 | `curl -s -X DELETE http://127.0.0.1:8000/v1/conversations/1 -H "X-API-Key: $KEY"` |
| 看错误形状（故意 400） | `curl -s -i http://127.0.0.1:8000/v1/chat -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"messages":[{"role":"assistant","content":"x"}]}'` |
| 只想要状态码 | `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health`（PowerShell 用 `-o NUL`） |
| 指定 `request_id` 追链路 | 任意请求加 `-H "X-Request-ID: abc123"`；响应头与 body 的 `request_id` 恒等于它 |

**读流式输出的顺序**：`{"status":"thinking"}` → 多个 `{"delta":"字"}` → `{"finish_reason":"stop"}` → `{"usage":{...}}` → **`[DONE]` 才是结束**（`finish_reason` 之后还可能有帧；`200` 不代表成功）。

---

## §4 质量门与测试

**五道门，提交前全绿**：

```bash
uv run ruff format .          # 1 格式化（加 --check 只检查不改）
uv run ruff check .           # 2 lint
uv run mypy .                 # 3 类型检查（strict）
uv run pyright                # 4 类型检查（与编辑器一致，只拦 error）
uv run pytest -q              # 5 回归（不碰真上游、不碰开发库）
```

| 我要什么 | 命令 |
|---|---|
| 只跑一个文件 | `uv run pytest tests/test_adapter_http.py -q` |
| 只跑名字匹配的几条 | `uv run pytest -q -k "usage or plain_dict"` |
| 看覆盖率（终端） | `uv run pytest --cov --cov-report=term-missing` |
| 看覆盖率（浏览器、黄行） | `uv run coverage html` → 打开 `htmlcov/index.html` |
| 只列用例不执行 | `uv run pytest --collect-only -q` |

⚠️ 报「全绿」前**确认范围**：一律用 `.`，别缩成 `src/`（否则 `tests/`、`scripts/` 成盲区）。
⚠️ **`mypy` 绿 ≠ 编辑器绿** —— 那种情况跑 `uv run pyright`，见 [§13](#13-排查症状--先跑什么)。

---

## §5 改数据库（迁移）

```bash
# 1 对着【空库】生成迁移（对着有数据的库跑会算出空差集，且不报错）
```

| PowerShell | bash |
|---|---|
| `$env:DATABASE_URL = "sqlite+aiosqlite:///$env:TEMP\autogen.db"` | `export DATABASE_URL="sqlite+aiosqlite:///$TMPDIR/autogen.db"` |

```bash
uv run alembic revision --autogenerate -m "add xxx to yyy"

# 2 人工 review 生成的文件：列类型 / 外键 ondelete / 索引 / downgrade 顺序

# 3 验证四连
uv run alembic upgrade head
uv run alembic check                                  # 期望：No new upgrade operations detected
uv run alembic downgrade base; uv run alembic upgrade head
```

| 症状 / 目的 | 命令 |
|---|---|
| 本地库缺表（`no such table`） | `uv run alembic upgrade head` |
| 模型与库是否一致 | `uv run alembic check` |
| 当前版本号 | `uv run alembic current` |
| 回退一步 | `uv run alembic downgrade -1` |

⚠️ 迁移文件**必须提交**。⚠️ 启动时**不建表**（DDL 归迁移独占，[决策 32](docs/decisions.md)）。
⚠️ `downgrade` 只能撤结构，**撤不回被删的数据**。

---

## §6 容器（生产形态）

```bash
docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
docker compose up -d            # ① migrate 跑完 → ② app healthy → ③ proxy 起
docker compose ps               # app / proxy 都 healthy；migrate 是 exited 0
curl -s http://127.0.0.1/health # 入口是 nginx 的 80，不是 8000
```

| 要做的事 | 命令 |
|---|---|
| 看**没起来**的容器（停在 `created`） | `docker compose ps -a` |
| 改完代码重起 | `docker compose up -d --build` |
| 改完 `deploy/nginx.conf` 生效 | `docker compose up -d --force-recreate proxy` |
| 验 nginx 语法（必须在 compose 网络内） | `docker compose exec proxy nginx -t` |
| 容器内看数据文件 | `docker compose exec app ls -ln /app/data` |
| 确认非 root | `docker compose exec app whoami` → `app` |
| 停（保留数据） | `docker compose stop` |
| 起回来 | `docker compose start` |
| 删容器与网络（**保留卷**） | `docker compose down` |
| 连数据一起删（⚠️ 不可恢复） | `docker compose down -v` |
| 隔离试跑，不碰真卷 | `docker compose -p probe up -d` … `docker compose -p probe down -v` |

⚠️ **宿主 8000 不发布**，只有 80（[决策 46](docs/decisions.md)）。
⚠️ `up` 不带 `--build` 会用**本地旧镜像**。
⚠️ 迁移失败时 `docker compose ps` 看不到 app；`up` 以非 0 退出并打印 `condition "service_completed_successfully" ... not met`。
⚠️ 数据在命名卷 `llm-app_app_data`（WSL 的 ext4），宿主资源管理器打不开。
⚠️ **不要** `docker compose config` 整份贴出来 —— 它会明文解析出 `LLM_API_KEY`。

---

## §7 看日志与指标

**日志（一行一 JSON）**：

| PowerShell | bash |
|---|---|
| `docker compose logs --no-log-prefix -f app \| ForEach-Object { $_ \| ConvertFrom-Json } \| Format-Table ts, level, msg, status, duration_ms, client, request_id -AutoSize` | `docker compose logs --no-log-prefix -f app \| jq -c '{ts,level,msg,status,duration_ms,client,request_id}'` |

| 我要什么 | PowerShell | bash |
|---|---|---|
| 按 `request_id` 追链路 | `docker compose logs app \| Select-String "abc123"` | `docker compose logs app \| grep abc123` |
| 只看 ERROR | `docker compose logs app \| Select-String '"level": *"ERROR"'` | `docker compose logs app \| grep '"level": *"ERROR"'` |
| 本地跑（非容器） | 直接在启动终端看 | 同左 |

**指标** —— `/metrics` **不对宿主开放**（nginx `return 404`），只有容器网络内能抓：

| PowerShell | bash |
|---|---|
| `docker run --rm --network llm-app_app_net --entrypoint python llm-app:dev -c "import urllib.request;print(urllib.request.urlopen('http://app:8000/metrics').read().decode())"` | 同左（命令本身无平台差异） |

验告警规则语法（不需要起 Prometheus）：

| PowerShell | bash |
|---|---|
| `docker run --rm -v "${PWD}\deploy:/rules:ro" --entrypoint promtool prom/prometheus:v3.6.0 check rules /rules/alerts.yml` | `docker run --rm -v "$PWD/deploy:/rules:ro" --entrypoint promtool prom/prometheus:v3.6.0 check rules /rules/alerts.yml` |

⚠️ 轮转由 Docker 做（`10m × 3`，每服务最多 30 MB）；**不要**在 Python 里加文件 handler（[决策 48](docs/decisions.md)）。

---

## §8 压测

```bash
# ① 假上游（终端 A）
```

| PowerShell | bash |
|---|---|
| `$env:FAKE_PORT = "18099"; uv run python scripts/fake_upstream.py` | `FAKE_PORT=18099 uv run python scripts/fake_upstream.py` |

```bash
# ② 独立库 + 放大限流 + 指向假上游 + 建表 + 起服务（终端 B）
```

| PowerShell | bash |
|---|---|
| `$env:DATABASE_URL = "sqlite+aiosqlite:///$env:TEMP\lt.db"; $env:LLM_BASE_URL = "http://127.0.0.1:18099"; $env:LLM_API_KEY = "sk-fake"; $env:RATE_LIMIT_PER_MINUTE = "100000"; $env:RATE_LIMIT_BURST = "1000"` | `export DATABASE_URL="sqlite+aiosqlite:///$TMPDIR/lt.db" LLM_BASE_URL=http://127.0.0.1:18099 LLM_API_KEY=sk-fake RATE_LIMIT_PER_MINUTE=100000 RATE_LIMIT_BURST=1000` |

```bash
uv run alembic upgrade head
uv run python -m app          # ③ 也是一个终端

# ④ 签 key 并压（终端 C）
uv run python -m app.keys create --user lt --label bench     # 抄下返回的明文
uv run python scripts/loadtest_chat_stream.py --key sk_xxx --concurrency 1,4,8,16,32
```

| 参数 / 环境变量 | 含义 |
|---|---|
| `--concurrency 1,4,8,16,32` | 并发档位 |
| `--rounds 3` | 每档轮数（**≥3 才谈得上 p95**） |
| `--gate 4` | 预期闸门值；与实际不符 → **FAIL exit 1**（让判据能失败） |
| `FAKE_FRAMES` / `FAKE_FRAME_DELAY` | 帧数 / 帧间隔 → 决定单请求服务时长 = **决定吞吐上限** |

⚠️ **`RATE_LIMIT_*` 不放大 = 测限流器**（📎 25 个请求就撞 429）。
⚠️ 探针只打 app **直连**端口（`/metrics` 在 nginx 那边是 404）。
📋 结果填 [docs/loadtest-record.md](docs/loadtest-record.md)（前置条件 / 数据 / 判定 / 结论，四节缺一不可比）。

---

## §9 API key 运维

```bash
uv run python -m app.keys create --user me --label laptop   # 明文只显示这一次
uv run python -m app.keys list                             # 只显示 hash 前缀
uv run python -m app.keys list --user me
uv run python -m app.keys revoke --id 3                    # 打时间戳，不删行
```

⚠️ 库里**只存 sha256**，明文丢了只能重签。
⚠️ 顺序是 **commit → print**：宁可留一行查得到 hash 的记录，也不要给出一把库里不存在的 key。

---

## §10 优雅停机验收

```bash
uv run python scripts/probe_graceful_shutdown.py            # 默认 --hold 1.0
uv run python scripts/probe_graceful_shutdown.py --hold 5   # 把窗口顶穿
```

期望 `PASS` + 退出码 0。`FAIL` = 「窗口内该跑完的没跑完」或「超窗口没被切断」。

---

## §11 上线前检查清单

> 逐条过，任一条不过就**不要发版**。⚠️ 最后一段是**回滚的手工方案**（自动化还没做，见 [门 6](docs/production-readiness.md)）。

### 11a 发版前（本地）

| # | 检查 | 命令 | 通过判据 |
|---|---|---|---|
| 1 | 五道门全绿 | `uv run ruff format --check . ; uv run ruff check . ; uv run mypy . ; uv run pyright ; uv run pytest -q` | 0 error / `pyright` 0 errors / 全 passed |
| 2 | 模型与迁移一致 | `uv run alembic check` | `No new upgrade operations detected` |
| 3 | 生产配置正确 | 检查 `.env` | `APP_ENV=prod`、`DEBUG=false`、`LLM_API_KEY` 已填 |
| 4 | 镜像能构建 | `docker compose build --build-arg PIP_INDEX_URL=...` | exit 0，镜像大小 ~283 MB |
| 5 | 工作区干净 | `git status --short` | 无多余文件；`git log --oneline -1` 记下这次的提交号 |

### 11b 发版（一条命令 + 三步确认）

```bash
docker compose up -d --build
docker compose ps                 # app / proxy healthy，migrate exited 0
curl -s http://127.0.0.1/health   # {"status":"ok"}
curl -s http://127.0.0.1/health/ready
```

### 11c 发版后（对外契约逐条验）

| # | 验什么 | 命令 | 通过判据 |
|---|---|---|---|
| 1 | 无 key → 401 且是**我们的**信封 | `curl -s -i -X POST http://127.0.0.1/v1/conversations -H "Content-Type: application/json" -d '{"title":"x"}'` | `401` + `{"error":{"code":"UNAUTHORIZED",...,"request_id":...}}` |
| 2 | 带 key → 201 | 同上加 `-H "X-API-Key: $KEY"` | `201` |
| 3 | **SSE 真流式**（不是攒着一次到） | `curl -N -s http://127.0.0.1/v1/chat/stream -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"数到十"}]}'` | 逐帧到达（不是最后一次性出现） |
| 4 | 反代层错误也是 JSON | 传 >1 MB body | `413` + `application/json`（不是 nginx HTML） |
| 5 | `/metrics` 对宿主封死 | `curl -s -o NUL -w "%{http_code}" http://127.0.0.1/metrics`（bash 用 `/dev/null`） | `404` |
| 6 | 日志能追链路 | 拿响应里的 `request_id`，按 [§7](#7-看日志与指标) 搜 | 命中的那一行里 `client` 是真实来源 IP |
| 7 | 实例下线快速失败 | `docker compose stop app` 后请求一次 | **3 秒内** `504` JSON（不是等 60 秒） |
| 8 | 起回来 | `docker compose start app` | healthy，请求恢复 200 |

### 11d 回滚（当前只有手工方案 ⚠️）

```bash
docker compose down                        # 停掉，保留卷
# 用上一版镜像 tag 重新起（前提：发版时打了 tag 并保留）
docker compose up -d
# 若这次发版带了迁移：先确认能否 downgrade
uv run alembic downgrade -1                # ⚠️ 只撤结构，撤不回被删的数据
```

⚠️ **这条是缺口**：现在没有 registry、没有镜像 tag 策略、没有灰度 —— 见 [门 6](docs/production-readiness.md) 与 [step13-closeout.md](docs/step13-closeout.md) §四。

---

## §12 演示动线（5 分钟）

| 分 | 做什么 | 命令 / 位置 |
|---|---|---|
| 0:00 | 起整套 + 证明活着 | `docker compose up -d` → `curl -s http://127.0.0.1/health` |
| 0:30 | **鉴权与越权** | 无 key → 401；带 key 建会话 → 201；访问别人的 id → **404**（不是 403，不泄露存在性） |
| 1:30 | **流式逐帧** | [§3](#3-调接口curl-配方) 的 `-N` 那一行；指一下 **`[DONE]` 才是结束信号** |
| 2:30 | **日志追链路** | [§7](#7-看日志与指标)；拿响应里的 `request_id` 搜一条 |
| 3:00 | **指标与硬阻断** | 宿主 `/metrics` → **404**；容器网络内 → 200 且 5 个指标齐全 |
| 3:30 | **容量有数字** | [§8](#8-压测) 跑 `--concurrency 1,4,8,16`（假上游，零成本）；对照 [loadtest-record.md](docs/loadtest-record.md) |
| 4:30 | **发版不断流** | [§10](#10-优雅停机验收) 探针 `PASS` |
| 5:00 | **摊开未做清单** | [step13-closeout.md](docs/step13-closeout.md) §四 —— 「我知道还差什么」 |

---

## §13 排查（症状 → 先跑什么）

| 症状 | 先跑这个 | 大概率原因 |
|---|---|---|
| 编辑器一片红，但 `mypy` 绿 | `uv run pyright` | 类型推断分叉（`getattr` / 反射）；按 [docs/dev-environment.md](docs/dev-environment.md) §8.0f 五步走 |
| `401 UNAUTHORIZED` | `curl -i` 看 body 与请求头 | 忘了 `X-API-Key` / key 已撤 / 键名拼错 |
| `404` 而不是 `403` | —— | **这是设计**：越权与不存在同一个观测结果（[决策 12](docs/decisions.md)） |
| `429 RATE_LIMITED` | 看响应 `Retry-After` | 每用户 60 次/分 + 突发 20；压测必须放大 |
| `503` + `Retry-After` | 看 `MAX_CONCURRENT_UPSTREAM_CALLS` | 上游闸门满，排队超时（默认 1.0s） |
| `502` | `docker compose ps -a`；`docker compose logs proxy` | app 没起 / nginx 缓存了旧 IP（需 `resolver`） |
| 很慢或 `504` | nginx 日志里的 `rt=`；`proxy_connect_timeout` / `UPSTREAM_TOTAL_TIMEOUT` | 实例下线（SYN 被丢弃，只能等超时）；上游慢 |
| `no such table` | `uv run alembic upgrade head` | 迁移没跑（启动不建表） |
| 端口被占 | `.env` 的 `PORT` | 上一个进程没退 |
| 测试偶发红 / 互相污染 | 重跑一次；看库名是否带 pid | 固定全局名（库路径 / 端口）被两个实例共享 |
| 文档类用例红（用例数 / 链接） | 读断言里点名的文件名 | 代码改了但文档计数 / 链接没同步 |
| 容器里 `import` 失败 / 行为像旧代码 | `docker compose up -d --build` | 用了旧镜像 |

**两条固定纪律**：
1. **先取证再改代码** —— 报错读完每个词（`or` 前后常是两个独立条件）。
2. **一个根因常引发多条报错** —— 先看第一条的列号，别逐条修。

---

## §14 去哪儿看什么

| 想知道 | 去哪 |
|---|---|
| 为什么这么设计、放弃了什么、何时重审 | [docs/decisions.md](docs/decisions.md)（55 条 ADR） |
| 系统长什么样（中间件栈 / ER / 帧序 / 状态机 / 两层接缝） | [docs/architecture.md](docs/architecture.md) |
| 端点契约与真实响应样本 | [docs/api.md](docs/api.md) |
| 什么时候做了什么、踩了什么坑、证据 | [docs/DEVLOG.md](docs/DEVLOG.md) |
| 还剩什么没做（`#N` 编号唯一来源） | [docs/todos.md](docs/todos.md) |
| 距离上线差什么（七道门） | [docs/production-readiness.md](docs/production-readiness.md) |
| Step 13 交付了什么（快照） | [docs/step13-closeout.md](docs/step13-closeout.md) |
| 压测怎么记数据 / 历史数字 | [docs/loadtest-record.md](docs/loadtest-record.md) |
| 测试怎么跑、两个连接池谁占谁 | [tests/README.md](tests/README.md) |
| 提交规范 / 「改了什么就要更新什么」 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 本机命令与环境陷阱（PowerShell / Docker / 编码） | [docs/dev-environment.md](docs/dev-environment.md) |
| 哪些操作要先确认 | [docs/tool-approval.md](docs/tool-approval.md) |
| 原理与实测（换个项目也成立） | [notes/](notes/) |
