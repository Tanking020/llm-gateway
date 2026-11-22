# RUNBOOK · 运行与展示速查

> **按「我要做什么」查。** 每条命令都能直接抄。
>
> 📎 **2026-11-21 逐条实跑校验过一遍**（Windows PowerShell 5.1 / uv 0.12.23 / Python 3.12.15 /
> Docker 29.9.3）。标 **📎** 的是这次实测的数字；标 **⛔** 的是**当前跑不通**的命令（附原因与替代）。
> 唯一未通过项：**§10 优雅停机探针**（探针漏带 `X-API-Key`，见那节）。
> **只有两平台不同时才分两列** —— 只有一列 = Windows / Linux 都能直接跑。
> Windows 侧是 **PowerShell 5.1**（不支持 `&&`、`||`，用 `;` 串联）。
> 原理与取舍不在这里 —— 见 [§14](#14-去哪儿看什么)。

## 索引

| 我要做什么 | 去哪 |
|---|---|
| 第一次把项目跑起来（含**建表 + 签 key + 三个库**） | [§1](#1-第一次跑起来一次性) |
| **本地还是容器**起服务 / 日常起服务 / 改配置 | [§2](#2-日常起服务) |
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
| **建表**（新库才有） | `uv run alembic upgrade head` | 同左 |
| 验上游连通 | `uv run python -m app.main ping` | 同左 |
| **签一把 API key** | `uv run python -m app.keys create --user me --label laptop` | 同左 |

成功标志：`可用模型 N 个：...` + `sk_` 开头的明文（**只显示这一次**）。

📎 **本次实测**：`uv sync` → `Resolved 54 / Checked 52`；`upgrade head` 对空库跑 **3 条**迁移，
对最新库**什么都不做**（幂等）；`ping` → `可用模型 2 个：deepseek-flash, deepseek-v4-pro`；
`keys create` 的明文恒为 **46** 字符（`sk_` + 43）；`alembic current` → `7c1f0a2d9b44 (head)`。

⚠️ **`ping` 只验上游、不碰数据库**（`main.py` 不 import 数据库）—— 所以它成功**不代表**你的 key 能用于 HTTP 接口。
⚠️ **「试没配密钥」不能靠 `$env:LLM_API_KEY=""`**：PS 5.1 里赋空串等于**删掉这个变量**（📎 `os.environ` 读到 `None`），
`.env` 的密钥照旧生效。要验这条，得在**没有 `.env` 的目录**里跑
（`Push-Location $env:TEMP; uv run --project <仓库> python -m app.main ping` → 打印「未配置 LLM_API_KEY」+ 退出码 **1**）。

### §1.1 三个库：它们在哪儿、什么时候用哪个 ⚠️

**这是最容易撞 401 的地方** —— key 签在 A 库，服务连的是 B 库，就会「key 明明对却说无效」。

| 库 | 位置 | 谁在用 | 怎么确认自己在用哪个 |
|---|---|---|---|
| **开发库** | 仓库根 `./app.db` | `uv run python -m app`（`.env` 没写 `DATABASE_URL` 时的默认值） | `Select-String -Path .env -Pattern DATABASE_URL` —— **没这一行**就是它 |
| **测试库** | `%TEMP%\llm-app-test-<进程号>.db` | `pytest`（`conftest.py` 在 import app **之前**改环境变量，一进程一个） | 跑测试时自动建；手工看不到很正常 |
| **容器库** | 命名卷 `llm-app_app_data` 里的 `/app/data/app.db` | `docker compose` 起的 app / migrate | `docker compose exec app ls -ln /app/data` |

三者**完全不互通**（key、用户、会话、账单都各算各的）：

```powershell
# 确认「我这个终端签的 key 会进哪个库」
uv run python -m app.keys list          # 列出来的就是当前 DATABASE_URL 指向的那个库

# 容器里那把 key（要在容器里签，或者把库指过去）
docker compose exec app python -m app.keys list
```

⚠️ `uv run python -m app.keys create` 和 `docker compose exec app python -m app.keys create` **是两个不同的库**，不要混。

📎 三者实测：开发库 `./app.db` 有 `alembic_version=7c1f0a2d9b44`；测试库由 pytest 建在 `%TEMP%`；
容器库在卷 `llm-app_app_data` 里（`docker compose up` 之后才有，`ls -ln /app/data` 看到属主是 **10001**）。
容器库是**独立的一份**：宿主签的 key 在容器里查不到，反之亦然。

---

⚠️ `ping` 不带密钥只会打印「未配置 LLM_API_KEY」并以 **1** 退出 —— 故意的（避免拿 `Bearer None` 去请求，报成误导性的 401）。
✅ **17 个旋钮全部在 `.env.example` 里有注释**（默认值 + 取值范围 + 反向约束）。`.env` 里只留你真正要改的那几行即可，其余删掉也照样生效。

---

## §2 日常起服务

### §2.0 先选外壳：本地进程还是容器？（8 行表）

> **同一份程序、两套外壳**：容器里的 `CMD` 就是 `python -m app`（📎 [Dockerfile](Dockerfile) 最后一行）。
> 判据：**「这一轮改没改代码？」改了就本地；「这一轮要不要证明能交付？」要就容器。**

| 问题 | 本地 `uv run python -m app` | 容器 `docker compose up -d`（[§6](#6-容器生产形态)） |
|---|---|---|
| 入口 | `127.0.0.1:8000` **直连 app** | 宿主 **80** → nginx → `app:8000`（8000 不发布） |
| 建表 | 你手动 `alembic upgrade head` | `migrate` 容器自动跑，失败就不起 app |
| 数据库 | `./app.db` | 命名卷里的 `/app/data/app.db` —— **另一份，key 不通用** |
| 代码生效 | 重启进程（`DEBUG=true` 可 reload） | 必须 `--build`，否则**跑旧镜像** |
| 身份 | 你自己（可以 root） | 非 root `uid 10001` |
| 反代层（413/502/504、SSE 缓冲、`$rid`） | ❌ 没有 | ✅ 有 |
| 该用在哪 | 改代码 / 跑测试 / 调响应形状 | 发版验收（[§11](#11-上线前检查清单)）/ 演示（[§12](#12-演示动线5-分钟)） |

⚠️ 第三种写法 `uv run uvicorn app.api.app:app` **不要用**：它绕过 `.env` 的 `HOST` / `PORT` / `DEBUG`
（📎 实测 `$env:PORT="9001"` 时它仍去绑 8000，报 `10048`）。

```bash
uv run python -m app                 # 监听地址/端口/reload 全部读 .env
```

打开 <http://127.0.0.1:8000/docs>（仅 `APP_ENV=dev` 时开；📎 实测 200，`/openapi.json` 里
`securitySchemes={"APIKeyHeader":…}`、**8 个受保护操作**都带 `security`）。

📎 启动第一屏是**一行 JSON**：`生效配置：{...}`（白名单 + 脱敏），紧接着 `Uvicorn running on http://127.0.0.1:8000`。
⚠️ 8000 被占时只报最后一行 `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`
（前面几行仍然是「startup complete」，别被误导）。

| 想改什么 | 改 `.env` 哪个键 |
|---|---|
| 端口被占 | `PORT`（`HOST` 一般不动） |
| 开自动重载 | `DEBUG=true` |
| 关交互式文档（生产） | `APP_ENV=prod` |
| 换模型 | `LLM_MODEL` |
| 上游地址（换假上游也用它） | `LLM_BASE_URL` |

⚠️ **不要用** `uvicorn app.api.app:app --reload` —— 它**静默绕过** `HOST` / `PORT` / `DEBUG`（`.env` 写 `PORT=9001` 也不会生效）。
📎 实测（`$env:PORT="9001"; uv run uvicorn app.api.app:app`）：它仍然去绑 **8000**，报 `10048`，退出码 3。
⚠️ `APP_ENV=prod` 且 `DEBUG=true` 会**拒绝启动**（有意为之）。
📎 实测：`ValidationError: APP_ENV=prod 时不允许 DEBUG=true：traceback 会返回给客户端`，退出码 **1**（连端口都没碰）。
⚠️ **怎么把它停干净**：前台跑就 `Ctrl+C`。若用 `Start-Process` / `uv run ... &` 放到后台，**`uv` 只是包装器**——
杀掉它并不会杀掉真正在听端口的 python 进程。查真凶：`Get-NetTCPConnection -State Listen -LocalPort 8000 | Select-Object -ExpandProperty OwningProcess`，再 `Stop-Process -Id <那个 PID>`。

---

## §3 调接口（curl 配方）

⚠️ **PowerShell 里必须写 `curl.exe`** —— 裸 `curl` 是 `Invoke-WebRequest` 的别名，参数不兼容，会报
「无法绑定参数 "Headers"」。下面的命令**已经写成 `curl.exe`，直接抄**；bash / Linux 上把 `.exe` 去掉即可。
⚠️ `-o /dev/null` 在 PowerShell 里要写成 `-o NUL`（表里已按平台标好）。
**除 `/health`、`/health/ready`、`/metrics`、`/v1/models*` 外，全部要 `X-API-Key`。**

⚠️ **`/docs` 里点 "Try it out" 现在可以带 key 了**：点右上角 **Authorize** 填一次即可（2026-11-21 修复，决策 56）。
⚠️ 但 `/docs` **看不到逐帧流式**（它等响应读完才显示），也不会经过 nginx（直连 8000）——
反代层的 413/502/504 与 SSE 缓冲行为只能在 §6 的 80 端口上验。

先设一个变量（§9 签出来的明文）：

| PowerShell | bash |
|---|---|
| `$KEY = "sk_xxx"` | `export KEY=sk_xxx` |

⚠️ 上面是**普通变量 `$KEY`**，不是环境变量 `$env:KEY` —— 两者在 PowerShell 里不是同一个东西。
下面所有命令统一用 `$KEY`；若你习惯 `$env:KEY`，那就把出现的每一处都改成 `$env:KEY`（混用 = 头里是空串 = 401）。

### ⚠️ PowerShell 5.1：JSON body 一律走临时文件（📎 实测）

| 写法 | 实际发出去的 body | 结果 |
|---|---|---|
| `-d '{"title":"x"}'` | `{title:x}`（双引号被剥） | **422** `{"loc":["body",1],"type":"json_invalid"}` |
| `-d '{\"title\":\"x\"}'` | `{"title":"x"}` | 200/201 —— 但**值里含空格时又会坏**（`{"title":"runbook verify"}` 实测同样 422） |
| 变量中转 `$b='{"title":"x"}'; -d $b` | `{title:x}`（同样被剥） | 422 |
| **写文件 + `--data-binary "@文件"`** | 原样字节（UTF-8 无 BOM） | ✅ 唯一不会坏、还能带中文的写法 |

固定三行（PowerShell）：

```powershell
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText("$env:TEMP\body.json", '{"title":"第一次对话"}', $utf8)
curl.exe -s -X POST http://127.0.0.1:8000/v1/conversations -H "X-API-Key: $KEY" -H "Content-Type: application/json" --data-binary "@$env:TEMP\body.json"
```

| 要做的事 | 命令（PowerShell 抄这列；bash 把 `curl.exe` 换成 `curl`） |
|---|---|
| 活着 | `curl.exe -s http://127.0.0.1:8000/health` → 📎 `{"status":"ok"}` |
| 就绪（DB 通不通） | `curl.exe -s http://127.0.0.1:8000/health/ready` → 📎 `{"status":"ready"}` |
| **非流式**对话 | body `{"messages":[{"role":"user","content":"你好"}]}` 写文件 → `curl.exe -s -X POST http://127.0.0.1:8000/v1/chat -H "X-API-Key: $KEY" -H "Content-Type: application/json" --data-binary "@$env:TEMP\body.json"` → 📎 200 + `{"content","model","usage_tokens"}` |
| **流式**（SSE） | 同上换 `/v1/chat/stream`，**加 `-N`**；想量首帧时间再加 `-w`（格式串里的换行在 PowerShell 里写「反引号 + n」）→ 📎 `ttfb=0.16s / total=0.66s`（首帧远早于总时长才算真流式） |
| 建会话 | body `{"title":"第一次对话"}` → POST `/v1/conversations` → 📎 **201**，`id` 从 1 起，`created_at` 带 `Z` |
| 列表（含账单统计） | `curl.exe -s "http://127.0.0.1:8000/v1/conversations?limit=20" -H "X-API-Key: $KEY"` → 📎 `{items,total,limit,next_cursor,has_more}` |
| 删会话 | `curl.exe -s -i -X DELETE http://127.0.0.1:8000/v1/conversations/1 -H "X-API-Key: $KEY"` → 📎 **204**；再删一次 → **404** `CONVERSATION_NOT_FOUND` |
| 看错误形状（故意 400） | body `{"messages":[{"role":"assistant","content":"x"}]}` → 📎 **400** `LAST_MESSAGE_NOT_USER` |
| 只想要状态码 | `curl.exe -s -o NUL -w "%{http_code}\n" http://127.0.0.1:8000/health`（bash 用 `-o /dev/null`） |
| 指定 `request_id` 追链路 | 任意请求加 `-H "X-Request-ID: abc123"`；📎 响应头与 body 的 `request_id` 恒等于它 |
| 真调上游模型清单（**花钱**） | `curl.exe -s -i http://127.0.0.1:8000/v1/upstream/models -H "X-API-Key: $KEY"` → 📎 200 + 2 个模型 |

**状态码怎么读**（📎 实测出来的顺序，别搞反）：

1. **JSON 解码在鉴权之前** → 坏 body + **无 key** = **422**（不是 401）
2. **schema 校验在鉴权之后** → 好 JSON + 类型错 / 超长 + 无 key = **401**
3. 所以「没带 key 却拿到 422」= body 坏了，不是鉴权坏了；反过来 401 也可能是「body 没问题，只是没身份」

⚠️ **尾斜杠会 307**：`DELETE /v1/conversations/`（id 为空）→ **307** 跳到 `/v1/conversations`；
curl 默认不跟随，加 `-L` 才看到 **405**（📎 两者都实测过）。

**读流式输出的顺序**：`{"status":"thinking"}` → 多个 `{"delta":"字"}` → `{"finish_reason":"stop"}` → `{"usage":{...}}` → **`[DONE]` 才是结束**（`finish_reason` 之后还可能有帧；`200` 不代表成功）。

---

## §4 质量门与测试

**五道门，提交前全绿**（命令与参数只在 [`scripts/check.py`](scripts/check.py) 定义，决策 63）：

```bash
uv run python scripts/check.py           # 五道门全跑：format / lint / mypy / pyright / test
uv run python scripts/check.py --list    # 看每道门实际跑的命令（= CI 跑的那些）
uv run python scripts/check.py test      # 只跑一道（CI 里每道门是一个独立 step）
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

📎 **2026-11-22 实测（`uv run python scripts/check.py` 全绿）**：

```text
质量门 5 道 | <仓库根>
    ok     0.1s  format  格式化检查（只读）
    ok     0.1s  lint    lint（E/F/I/UP/B/TID）
    ok     0.5s  mypy    类型检查（strict）
    ok     8.4s  pyright 类型检查（对齐编辑器）
    ok    16.0s  test    回归测试
```

逐道的原始输出：`ruff format --check` → **46 files already formatted**；
`ruff check` → **All checks passed!**；`mypy` → **Success: no issues found in 49 source files**；
`pyright` → **0 errors, 0 warnings, 0 informations**；`pytest -q` → **228 passed**。

📎 子集命令实测：`tests/test_adapter_http.py` → **28 passed**；
`-k "usage or plain_dict"` → **8 passed, 200 deselected**；`--cov` → **TOTAL 93%**；
`coverage html` → `htmlcov\index.html`；`--collect-only -q` 末行 `228 tests collected`。

---

## §5 改数据库（迁移）

**顺序不能换：先让「一次性库」到 head，再 autogenerate。**
📎 实测：对着一个**没跑过迁移的空库**直接 `revision --autogenerate` → `FAILED: Target database is not up to date.`（退出码非 0）；
对着**已是最新**的库则得到一个空迁移（`upgrade()` 里是 `pass`）。

| PowerShell | bash |
|---|---|
| `$env:DATABASE_URL = "sqlite+aiosqlite:///$env:TEMP\autogen.db"` | `export DATABASE_URL="sqlite+aiosqlite:///$TMPDIR/autogen.db"` |

```bash
# 1 一次性库先到 head（这一步不能省）
uv run alembic upgrade head

# 2 算的是「模型 vs 当前 head 结构」的差异
uv run alembic revision --autogenerate -m "add xxx to yyy"

# 3 人工 review 生成的文件：列类型 / 外键 ondelete / 索引 / downgrade 顺序
#    ⚠️ 若决定「删掉它」，别先 upgrade（否则库版本号会指向不存在的 revision，见下）

# 4 验证四连
uv run alembic upgrade head
uv run alembic check                                  # 期望：No new upgrade operations detected
uv run alembic downgrade base; uv run alembic upgrade head
```

⚠️ **别把 `DATABASE_URL` 指向开发库**：`--autogenerate` 本身只读结构，但**第 4 步那四条会真的执行 DDL**。

| 症状 / 目的 | 命令 |
|---|---|
| 本地库缺表（`no such table`） | `uv run alembic upgrade head` |
| 模型与库是否一致 | `uv run alembic check` |
| 当前版本号 | `uv run alembic current` |
| 回退一步 | `uv run alembic downgrade -1` |

⚠️ 迁移文件**必须提交**。⚠️ 启动时**不建表**（DDL 归迁移独占，[决策 32](docs/decisions.md)）。
⚠️ `downgrade` 只能撤结构，**撤不回被删的数据**。

📎 **2026-11-21 实测**（对着 `%TEMP%\autogen.db` 一次性库）：`upgrade head` 建 3 张表 →
`check` 输出 `No new upgrade operations detected.` → `current` 输出 `7c1f0a2d9b44 (head)` →
`revision --autogenerate` 生成一个**空迁移**（`upgrade` 里是 `pass`）→ `downgrade -1` / `downgrade base` / `upgrade head` 全部 exit 0。

⛔ **顺序陷阱（实测踩到）**：自动生成的空迁移**先被 `upgrade head` 应用了，然后才删掉文件** →
库里的版本号指向一个不存在的 revision，之后所有 alembic 命令都报
`ERROR [alembic.util.messaging] Can't locate revision identified by 'b3842e928d9d'`。
✅ 正确顺序：**先 review 文件 → 决定「留下提交」还是「删掉」→ 删掉的话别先 upgrade**；
万一已经踩了，对着一次性库直接删库重建即可（别对着开发库踩这一下）。

---

## §6 容器（生产形态）

```bash
docker compose build            # 索引与 uv.lock 绑定，见 dev-environment §8.0c
docker compose up -d            # ① migrate 跑完 → ② app healthy → ③ proxy 起
docker compose ps               # app / proxy 都 healthy；migrate 是 exited 0
curl.exe -s http://127.0.0.1/health # 入口是 nginx 的 80，不是 8000
```

> ⚠️ **入口只绑 127.0.0.1（决策 58）**：`http://127.0.0.1/...` 可用，`http://<局域网IP>/` 不可用 —— 这是有意的。
> 容器默认 `APP_ENV=prod`（没有 /docs）；演示文档：`$env:APP_ENV_CONTAINER="dev"; docker compose up -d`。
> 公网演示/上线前必须补 TLS，见待办 #100。

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

📎 **2026-11-21 实测**：镜像 **284 MB**（不是 283）；`up -d` 顺序 migrate `Exited (0)` → app `healthy` → proxy `healthy`；
`whoami` → `app`；`/app/data` 里 `app.db` 属主 `10001 10001`；`nginx -t` → `syntax is ok / test is successful`；
`compose stop` 后 `start` 回来数据还在（健康检查 200）；`down`（无 `-v`）**保留**卷 `llm-app_app_data`。

⚠️ **`docker compose build` 不要接 PowerShell 管道**：📎 实测 `docker compose build … | Select-Object -Last 40`
虽然镜像构建成功（末尾 `Image llm-app:dev Built`），`$LASTEXITCODE` 却是 **1**（buildkit 走 stderr，被 PS 当成错误）。
要么不接管道，要么把输出重定向到文件再 `Get-Content -Tail` —— §11a 第 4 条判「exit 0」时才不会被坑。

⚠️ **验「宿主 8000 不发布」前，先确认本机没有开发服务在跑**：📎 我第一次验时 8000 上跑着 §2 的开发服务，
`curl 127.0.0.1:8000/health` 回了 200，差点误判「端口泄露」。判据以 `docker compose ps` 的 PORTS 列为准：
app 那行是 **`8000/tcp`**（不是 `0.0.0.0:8000->8000`），proxy 是 `0.0.0.0:80->80/tcp`。

⛔ **`-p probe` 隔离试跑必须先停主栈**：📎 实测主栈在跑时 `docker compose -p probe up -d` 直接失败 ——
`invalid pool request: Pool overlaps with other one on this address space`（子网 `172.30.0.0/24` 与 80 端口都是写死的，
换项目名不会换端口/子网）。

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

📎 **实测（2026-11-21）**：
- 日志逐行 `ConvertFrom-Json` 全部成功；`Format-Table` 列太宽会被截断，想看清加 `| Out-String -Width 200`
- `promtool check rules` → `SUCCESS: 3 rules found`
- 容器网络内抓 `/metrics` → 200，含 `http_requests_total{method,path,status}` / `db_pool_checked_out` 等

✅ **「对不上号」已修一处、留一处**（都实测过）：
1. ~~**nginx 的 `rid=` 不是应用的 `request_id`**~~ → **已修（#98 / 决策 57）**：`deploy/nginx.conf` 加 `map $http_x_request_id $rid`（白名单 `^[A-Za-z0-9._:-]{1,64}$`），
   日志 / 三个错误页 / 透传统一用 `$rid`。📎 实测：带 `X-Request-ID: trace-abc123` → 响应头、nginx `rid=`、应用日志 `request_id` **三处同值**；
   带非法 ID（含空格/引号）→ 三处一起变成同一个 32 位 hex，且 nginx 日志里搜不到那串原文。
2. **从宿主 curl 时，应用日志的 `client` 是 Docker 网桥地址**（📎 `172.30.0.128`），不是 `127.0.0.1`；
   容器内 healthcheck 才是 `127.0.0.1`。只有**从另一台机器**访问，才能看到真实外部 IP。

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

📎 **2026-11-21 实测**（假上游 `FAKE_PORT=18099`、`--concurrency 1,4,8,16 --rounds 3 --gate 4`）：

```text
c=1   codes={'200': 3}                 ttfb p50= 25ms p95= 63ms total p95= 427ms pool_peak=1
c=4   codes={'200': 12}                ttfb p50= 76ms p95= 98ms total p95= 427ms pool_peak=4
c=8   codes={'200': 24}                ttfb p50=348ms p95=484ms total p95= 803ms pool_peak=4
c=16  codes={'200': 36, '503': 12}     ttfb p50=463ms p95=868ms total p95=1247ms pool_peak=4
PASS: 低并发全成功、高并发出现 503（闸门生效）   exit 0
```

⚠️ **两个坑（实测）**：
1. 压测服务若改了 `PORT`，探针**必须加 `--base http://127.0.0.1:<port>`** —— 它默认打 8000，
   而 8000 上很可能是你的**开发服务**（真上游、真花钱、限流也没放大）。
2. 起压测服务前先确认 8000/你选的端口**没被占**，否则只会看到 `10048`，探针全线连不上。

---

## §9 API key 运维

```text
uv run python -m app.keys create --user me --label laptop   # 明文只显示这一次
uv run python -m app.keys list                             # 只显示 hash 前缀
uv run python -m app.keys list --user me
uv run python -m app.keys revoke --id 3                    # 打时间戳，不删行
```

⚠️ 库里**只存 sha256**，明文丢了只能重签。
⚠️ 顺序是 **commit → print**：宁可留一行查得到 hash 的记录，也不要给出一把库里不存在的 key。
⚠️ **签给哪个库由 `DATABASE_URL` 决定**：`.env` 里没写就用 `./app.db`；容器用的是命名卷里的库 ——
**两者不是同一个库**，在宿主签的 key 到容器里查不到（反之亦然）。签完先 `list` 确认，再用 §3 验一次。

📎 **实测（2026-11-21）**：`create` → 明文 46 字符；`list` 只显示 hash 前 12 位；
`list --user verify` 只列该用户；`revoke --id 3` → `已撤销 key id=3`，**紧接着请求立刻 401**
（`API key 无效或已撤销`）；**再 revoke 同一 id → `已经是撤销状态，无需再撤`，退出码 0**（幂等）；
`revoke --id 999` → `没有 id=999 的 key`，**退出码 1**。

---

## §10 优雅停机验收

> ✅ **2026-11-21 修复（#97）并实测通过**：探针现在会自己签一把临时 key 再开流。

```bash
uv run python scripts/probe_graceful_shutdown.py            # 默认 --hold 1.0
uv run python scripts/probe_graceful_shutdown.py --hold 5   # 把窗口顶穿
```

期望 `PASS` + 退出码 **0**。`FAIL` = 「窗口内该跑完的没跑完」或「超窗口没被切断」。

📎 修后实跑输出（原样）：

```text
[父进程] 1.08s 已投递信号
[父进程] 响应码=200 帧数=16 末帧='{"delta": "滴"}'
[父进程] 客户端结局=客户端异常 RemoteProtocolError（流被切断时属正常）
[父进程] 总耗时=3.24s 信号后=2.16s 子进程退出码=3
==> 结论：PASS 窗口生效（在途流按窗口被掐断）
```

📎 **变异验证**（证明「变绿」确实是这一行带来的）：把 `headers={"X-API-Key": key}` 删掉跑副本 →
`POST /v1/chat/stream` **401** → 「没收到任何帧」→ **FAIL exit 1**。

📎 探针跑完会**自己清掉**它在 `%TEMP%` 建的 `probe_graceful_*` 目录（#99）；失败时子进程日志会先打进那一屏再删。

> 背景（别再踩）：探针写于 13c-6，13d-4 给业务路由加鉴权后它没跟上，裸发请求 → 401 → 连带报
> 「没收到帧 / 没机会发信号 / 子进程没退出」。这类**不在 CI 里的独立脚本**最容易这样静默腐坏（坑 K100）。

---

## §11 上线前检查清单

> 逐条过，任一条不过就**不要发版**。⚠️ 最后一段是**回滚的手工方案**（自动化还没做，见 [门 6](docs/production-readiness.md)）。

### 11a 发版前（本地）

| # | 检查 | 命令 | 通过判据 |
|---|---|---|---|
| 1 | 五道门全绿 | `uv run python scripts/check.py` | 每道门都 `ok`（脚本逐道打印耗时；任一道红就停并回显命令） |
| 2 | 模型与迁移一致 | `uv run alembic check` | `No new upgrade operations detected` |
| 3 | 生产配置正确 | 检查 `.env` | `APP_ENV=prod`、`DEBUG=false`、`LLM_API_KEY` 已填（⚠️ **本地演示用 `dev` 即可**，切 `prod` 会关掉 `/docs`） |
| 4 | 镜像能构建 | `docker compose build` | exit 0，镜像 **284 MB**（⚠️ 别接 PowerShell 管道，否则退出码会假报 1，见 §6）。**不许加 `--build-arg PIP_INDEX_URL`** —— 索引必须与 `uv.lock` 一致（#101） |
| 5 | 工作区干净 | `git status --short` | 无多余文件；`git log --oneline -1` 记下这次的提交号 |
| 6 | 优雅停机探针 PASS | `uv run python scripts/probe_graceful_shutdown.py` | `PASS` + 退出码 0（⚠️ 它**不在 CI 里**，只能靠这条清单保证「有人跑」，见坑 K100） |

### 11b 发版（一条命令 + 三步确认）

```bash
docker compose up -d --build
docker compose ps                 # app / proxy healthy，migrate exited 0
curl.exe -s http://127.0.0.1/health   # {"status":"ok"}
curl.exe -s http://127.0.0.1/health/ready
```

📎 实测顺序：`migrate Exited (0)` → `app (healthy)` → `proxy (healthy)`；80 端口回 `{"status":"ok"}`。

### 11c 发版后（对外契约逐条验）

| # | 验什么 | 命令 | 通过判据 |
|---|---|---|---|
| 1 | 无 key → 401 且是**我们的**信封 | `curl.exe -s -i -X POST http://127.0.0.1/v1/conversations -H "Content-Type: application/json" -d '{"title":"x"}'` | `401` + `{"error":{"code":"UNAUTHORIZED",...,"request_id":...}}` |
| 2 | 带 key → 201 | 同上加 `-H "X-API-Key: $KEY"` | `201` |
| 3 | **SSE 真流式**（不是攒着一次到） | `curl.exe -N -s http://127.0.0.1/v1/chat/stream -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"数到十"}]}'` | 逐帧到达（不是最后一次性出现） |
| 4 | 反代层错误也是 JSON | 传 >1 MB body | `413` + `application/json`（不是 nginx HTML） |
| 5 | `/metrics` 对宿主封死 | `curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1/metrics`（bash 用 `/dev/null`） | `404` |
| 6 | 日志能追链路 | 拿响应里的 `request_id`，按 [§7](#7-看日志与指标) 搜 | app 与 nginx **两处都能搜到**（#98 起 nginx `rid=` 与它同源）；`client` 是可信链解析后的来源（⚠️ 从宿主测会是 Docker 网桥 IP，见 §7） |
| 7 | 实例下线快速失败 | `docker compose stop app` 后请求一次 | **3 秒内** `504` JSON（不是等 60 秒） |
| 8 | 起回来 | `docker compose start app` | healthy，请求恢复 200（⚠️ **刚起回来第一次可能 502**：nginx 还握着重启前的上游连接，📎 实测 `upst=502 rt=0.000`，等 ~3s 再判） |

📎 **11c 逐条实测（2026-11-21，全过）**：无 key → `401` + `www-authenticate: ApiKey` + 我们的信封；
带 key → `201`；SSE 经 nginx 逐帧（`ttfb=0.249s / total=0.705s`，末帧 `[DONE]`）；
`/metrics` → **404**；1.2 MB body → **413** + `PAYLOAD_TOO_LARGE`（JSON，不是 nginx HTML）；
`stop app` → **3.01s** 回 `504 GATEWAY_TIMEOUT`（JSON）；`start app` → healthy + `200`。

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

**开场前 30 秒准备**（否则 0:30 那条演不了越权）：
`uv run python -m app.keys create --user demo --label laptop` 和
`uv run python -m app.keys create --user bob --label other` 各签一把，分别存进 `$KEY` / `$KEY2`。

| 分 | 做什么 | 命令 / 位置 |
|---|---|---|
| 0:00 | 起整套 + 证明活着 | `docker compose up -d` → `curl.exe -s http://127.0.0.1/health` |
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
| `422` + `"type":"json_invalid"` + `"loc":["body",N]` | 看 body 是不是用 `-d '{...}'` 发的 | **PowerShell 5.1 剥了双引号**，curl 发出去的不是 JSON → 改用临时文件（§3） |
| `307 Temporary Redirect` | 看 URL 末尾是不是多了 `/` | Starlette 的尾斜杠重定向；curl 默认不跟随 → 去掉斜杠，或加 `-L`（会得到 405） |
| `alembic current` 报 `Can't locate revision` | 看 `alembic/versions/` 里还剩哪些文件 | 库的版本号指向一个**已删除**的迁移文件（§5 顺序陷阱） |
| `revision --autogenerate` 报 `Target database is not up to date` | `uv run alembic upgrade head` | 指向的库没跑过迁移（§5 第 1 步不能省） |
| `docker compose -p probe up -d` 报 `Pool overlaps` | `docker compose ps` | 主栈还在跑：子网 `172.30.0.0/24` 与 80 端口写死，先 `docker compose down` |
| `docker compose build` 回 exit 1 但日志末尾是 `Built` | 看有没有接 PowerShell 管道 | buildkit 走 stderr，被 PS 当错误；重跑别接管道 |
| 编辑器一片红，但 `mypy` 绿 | `uv run pyright` | 类型推断分叉（`getattr` / 反射）；按 [docs/dev-environment.md](docs/dev-environment.md) §8.0f 五步走 |
| `401 UNAUTHORIZED` | `curl.exe -i` 看 body 里的 `message` | **先看是哪一句**：`缺少 X-API-Key 请求头` = 头没送到；`API key 无效或已撤销` = 头到了但**库里没有这把 key**（最常见：key 签在另一个库 / 另一个容器里） |
| `Invoke-WebRequest : 无法绑定参数 "Headers"` | 改用 `curl.exe` | 裸 `curl` 是 PowerShell 的别名，不是真 curl |
| 签了 key 但仍 `无效或已撤销` | `uv run python -m app.keys list` | 库不对：`.env` 没写 `DATABASE_URL` 时用 `./app.db`；容器用的是命名卷里的库 —— 两者不是同一个 |
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
| 为什么这么设计、放弃了什么、何时重审 | [docs/decisions.md](docs/decisions.md)（57 条 ADR） |
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
