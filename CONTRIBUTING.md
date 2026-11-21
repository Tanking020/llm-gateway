# 贡献指南（Contributing）

> 本文件是**改这个仓库必须满足的条件**。它由项目的工程规范提炼而来：
> 只保留「不做会出问题」的硬约束，详细解释与事故复盘在
> [docs/dev-environment.md](docs/dev-environment.md)。
>
> 本仓库不含过程笔记（能力路线、自检题、机制长文）—— 它们与具体项目解耦，
> 不参与这个仓库的交付，也不列入「改了什么要更新什么」的清单。

---

## 1. 环境准备

```bash
uv sync                 # 按 uv.lock 还原依赖（含 Python 3.12）
cp .env.example .env    # Windows: Copy-Item .env.example .env
```

- **不要**用系统 Python / 全局 pip：所有命令加 `uv run` 前缀。
- `.env` 里放真实密钥；`.env.example` 里只放键名与示例值。**`.env` 永不提交**。
- 启动服务用 `uv run python -m app`（`settings.host/port/debug` 才会生效）。

## 2. 质量门（提交前必须全绿，CI 会再跑一遍）

```bash
uv run ruff format .     # 1. 格式化
uv run ruff check .       # 2. lint（E/F/I/UP/B/TID）
uv run mypy .             # 3. 类型检查（strict）
uv run pyright            # 4. 类型检查（与编辑器 Pylance 对齐，只拦 error）
uv run pytest -q          # 5. 回归测试（不碰真上游、不碰开发库）
```

| 门槛 | 标准 |
|---|---|
| `ruff format --check .` | 0 diff |
| `ruff check .` | 0 error（`--fix` 后仍报的必须手改） |
| `mypy .` | `--strict` 0 error；**不允许静默加** `# type: ignore`（要加必须写原因） |
| `pyright` | 0 error。**规则是「并集」**：`mypy` 与 `pyright` 都过才算过。若 pyright 报的写法 mypy 允许 → **改代码**，不加 `# pyright: ignore` |
| `pytest` | 全绿；**新增行为必须带用例** |

⚠️ **为什么两道类型检查都要跑**（[决策 55](docs/decisions.md)）：两者对**同一个写法**的推断会分叉。
📎 实测 `getattr(obj, "名字", None)`：`mypy` 把它当 `Any` 从此什么错都放行，`pyright` 当 `object` 于是 `int(object)` 报错。
**只跑 `mypy` 会出现「质量门全绿、编辑器一片红」** —— 那不是配置问题，是它真的看不见那个错。

**三条容易踩的规则**：

1. **范围一律用 `.`**，不要缩成 `src/` —— 否则 `scripts/` 与 `tests/` 成了质量盲区。
2. **`.md` 必须排除在 ruff 之外**（`pyproject.toml` 的 `extend-exclude = ["*.md"]`）。
   否则 `ruff format .` 会改写文档里的 Python 示例：刻意对齐的注释被压掉、故意报错的例子被"修好"。
3. **报「全绿」之前先确认命令范围**。带路径的 `mypy src` 与不带参数的结果可能不同。

## 3. 提交规范

| 项 | 规则 |
|---|---|
| 标题 | Conventional Commits：`feat: …` / `fix: …` / `test: …` / `docs: …` / `ci: …` / `refactor: …` |
| 正文 | 中文，写**为什么改**，不写「改了什么」（diff 已经说了） |
| 中文多行 | **必须** `git commit -F <文件>`。PowerShell 下 `-m` 遇到多行 / 引号 / 中文会被解析碎裂 |
| 提交信息文件 | 写 `$env:TEMP\msg.txt`，**绝不放进仓库**（会被 `git add -A` 一起提交） |
| 粒度 | 一个工作单元一提交；能独立跑通的最小单元 |
| 提交前 | `git status` + `git diff --staged` 各看一次 |
| 提交后 | `git --no-pager show --stat HEAD` 核对：**信息说的改动必须真的在里面** |
| 分支 | `feat/xxx` / `fix/xxx` / `chore/xxx` / `docs/xxx` |

> 当前是**单人开发**，日常直接提交 `main`。开 PR 时 CI 会跑同一套质量门。

## 4. 代码约定

### 4.1 分层方向（禁止反向 import）

```text
api/  →  services/  →  db/ , core/
schemas.py  ←被 api/ 使用（只放契约，不写逻辑）
config.py   ←任何层可读（只读，不写状态）
```

**上游调用只能出现在适配器**（`llm_client.py`）：路由里**不许** `import httpx`、不许写 `try/except` 翻译上游错误。
这条由 lint 规则 `TID251` 机械保证 —— 违反了 CI 会红。

### 4.2 命名

| 对象 | 规范 | 示例 |
|---|---|---|
| 模块 / 包 | `snake_case` | `chat_service.py` |
| 类 | `PascalCase` | `ChatRequest` |
| 函数 / 变量 / 常量 | `snake_case` / `UPPER_SNAKE_CASE` | `stream_chat()` / `MAX_TOKENS` |
| 内部实现 | 单下划线前缀 | `_build_prompt()` |
| 对外契约 | `XxxRequest` / `XxxResponse` | `ChatRequest` |
| 测试文件 / 函数 | `test_<模块>.py` / `test_<行为>_<条件>_<预期>` | `test_stream_chat_when_client_disconnects_stops_generation` |
| 路由路径 | 名词复数 + 版本前缀 | `/v1/conversations` |

**标识符必须英文**（`src/` / `tests/` / `scripts/` 一律）—— 中文只出现在**注释、docstring、字符串字面量**里。
理由：生态惯例、公开仓库的可读性，以及**中文标识符在编码被破坏时会直接语法错**（注释坏了还能跑）。

### 4.3 注释

- **注释写「为什么必须这样」与「不这样会怎样」，不写「这行在做什么」。**
  代码能表达的不写；边界条件、反直觉的坑、被否决的替代写法要写。
- 单个逻辑单元的连续注释 **≤ 4 行**；docstring 的"为什么"段 **≤ 3 行**。
- **代码里不用 emoji**，需要提醒写 `【注意】：`。

### 4.4 文档里的标记

| 标记 | 含义 |
|---|---|
| ⭐ | 高频 / 容易错 |
| 🟡 | 曾经答错或理解偏过 |
| 📎 | 有配套实测数据 |

**emoji 只用于 `.md`**；`.py` 里一律用 `【注意】：`。

## 4.5 数据库变更流程（改了模型就必须生成迁移）

改动 `src/app/models.py` 后，**必须**生成迁移文件并提交，否则「模型」与「库」会悄悄分叉：

```bash
# 1. 对【空库】生成迁移：autogenerate 算的是「metadata vs 现有库」的差集，
#    若对着已有表的开发库跑，差集会为空 —— 生成的迁移是空的且不会报错
$env:DATABASE_URL = "sqlite+aiosqlite:///$env:TEMP\autogen.db"   # PowerShell
uv run alembic revision --autogenerate -m "add owner_id to conversations"

# 2. 人工 review 生成的文件：列类型、外键 ondelete、索引、downgrade 顺序
# 3. 验证
uv run alembic upgrade head
uv run alembic check          # 期望 No new upgrade operations detected
uv run alembic downgrade base && uv run alembic upgrade head
```

| 规则 | 理由 |
|---|---|
| 迁移文件**必须提交** | 它是部署产物的一部分；CI 与生产都靠它建表 |
| **不要手改** autogenerate 的产物到「看不出来源」 | 要改就在文件顶部写一句为什么，review 时才看得懂 |
| `alembic/versions` **排除在 ruff 之外** | 它是生成物；被改写后下次 regenerate 会产出格式上的假 diff，掩盖真正的 schema 变更 |
| `alembic.ini` **只写英文** | `fileConfig` 用 locale 编码读它，中文在 GBK 环境下会 `UnicodeDecodeError`（坑 K89） |
| 上面第 3 步**已自动化** | `tests/test_migrations.py` 每次 `pytest` 都会跑 `upgrade head` + `alembic check` + DDL 对比 → 忘生成迁移 / 迁移写漏，CI 直接红。手工那三条命令现在只用于**定位**（[决策 33](docs/decisions.md)） |

## 5. 测试约定

| 判据 | 做法 |
|---|---|
| **不碰真上游** | `dependency_overrides` 注入 `tests/fakes.py`；假对象**继承真类**，签名漂移会被 mypy 抓到 |
| **不碰开发库** | `conftest.py` 在 `import app` **之前**设 `DATABASE_URL` 指向 `%TEMP%`；每个测试清表 |
| **走 HTTP，不 import 路由函数** | 测试只认 URL 字符串；中间件 / 异常处理器 / 依赖注入全都真实经过 |
| **断言要有牙** | 每批用例抽 3 ~ 5 处做**变异测试**：故意改坏一行源码 → 看它红不红 → 还原 |
| **常量值要单独钉** | `StrEnum` 防成员名、不防值 —— 拼错的值必须有一条断言钉住 |

更细的说明（10 个文件各测哪层、两个连接池谁占谁、怎么读 pytest 输出）见 [tests/README.md](tests/README.md)。

## 6. 文档约定：改了什么，就要更新什么

> 判据：**换个项目，这条还对吗？** 对 → 不写进本仓库（属跨项目笔记）；不对 → `docs/`。

| 你做了 | 必须更新 |
|---|---|
| 完成一个工作单元 | [docs/DEVLOG.md](docs/DEVLOG.md) §二追加一行（日期 / 做了什么 / 证据 / 关联编号） |
| 修了一个待办 | [docs/todos.md](docs/todos.md) 对应行改成 `✅ 已解决（单元号，日期）` |
| 发现新缺陷 | 先在 [docs/todos.md](docs/todos.md) 登记编号，**编号永不重用** |
| 做了一个取舍 | [docs/decisions.md](docs/decisions.md) 加一条 ADR（五段：背景 → 方案对比 → 决定 → **代价** → 重审条件） |
| 改了接口形状 / 中间件 / 状态机 | [docs/architecture.md](docs/architecture.md) + [docs/api.md](docs/api.md) |
| ↳ 其中**「接口形状」包括**：端点增删、**新增必填请求头 / 请求体字段**、**新增错误码或状态码**、响应字段增删 | 同上（📎 2026-11-17 教训：13d-2 加了 `X-API-Key` + 401，`architecture.md` 改了，`api.md` 漏了 → 文档里的 curl 示例全部会 401） |
| 改了**部署形态**（compose / nginx / 端口 / 网络 / 卷） | [docs/architecture.md](docs/architecture.md) §13.5 时序图 + `docker-compose.yml` 里的 `【注意】` + [docs/dev-environment.md](docs/dev-environment.md) §8.0d + `tests/test_docker_assets.py` 的守卫 |
| 改了**日志字段或格式** | [docs/architecture.md](docs/architecture.md) §10.3 字段表 + `tests/test_log_json.py`；⚠️ 别在 `api.md` 里抄一份字段清单（单一真相） |
| 改了**端点 / 错误码 / 加删测试** | `tests/test_docs_contract.py` 会**直接变红**点名哪一处没同步（决策 49）：`api.md` 的错误码表与端点表、`README` / `tests/README` / `production-readiness` 里的用例数。⚠️ 单独跑该文件时两条计数用例会 skip（子集运行），`-rs` 可看原因 |
| 踩了一个可复现的坑 | [docs/DEVLOG.md](docs/DEVLOG.md) §三 加一行（`K<n>`），**写出复现方式** |
| 学到一条跨项目结论或原理 | **不属于本仓库** —— 写进跨项目笔记，不要写进 `docs/` |
| 改了阶段进度 | [docs/roadmap.md](docs/roadmap.md) |
| **改版本号 / 发版** | 只改 [pyproject.toml](pyproject.toml) 一处 —— 运行时从打包元数据读（`app/api/app.py` 的 `_app_version()`），`uv lock` 会同步 `uv.lock`；同时补 [CHANGELOG.md](CHANGELOG.md)。⚠️ **不要在代码里写死版本号**，`test_openapi_version_comes_from_the_packaging_metadata` 会红 |

**单一真相**：一条事实只在一个文件里展开，其它地方只引用编号（`#38` / `决策 28` / `坑 K7` / `1.138`）。
判据：**改一处会不会漏另一处？** 会 → 说明写重复了。

**已经收敛成单一真相的几处**（改的时候别在别处再抄一份）：

| 事实 | 唯一来源 | 谁在读 |
|---|---|---|
| 版本号 | [pyproject.toml](pyproject.toml) | `importlib.metadata`（`/openapi.json` 的 version） |
| 错误码 → HTTP 状态码 | `src/app/errors.py` 的 `_STATUS_BY_CODE` | 异常处理器；`api.md` 与 `test_docs_contract.py` 跟它比 |
| 模型白名单 | `src/app/api/app.py` 的 `KNOWN_MODELS` | `/v1/models*` 与两条 chat 的校验（#48） |
| 镜像索引 | `Dockerfile` 的 `ARG PIP_INDEX_URL` | `uv sync --locked`（必须等于 `uv.lock` 的 registry，决策 60） |
| 用例数 | pytest 实际收集 | `test_docs_contract.py` 拿它比对 README / tests-README / production-readiness |

## 7. 安全

- `.env` 不提交；密钥不进代码、日志、commit、响应体。
- 500 响应只回一句人话 + `request_id`，堆栈只进服务端日志。
- 打印 / 探针脚本**只打印白名单字段**，绝不 `print(pydantic 对象)`（`repr` 会吐出全部字段，含密钥）。
- 危险命令先确认再执行：`git reset --hard`、`git clean -fd`、删除 `.venv`、`docker system prune`。

## 8. Pull Request

- 标题与提交信息同规范；正文写「为什么」+「怎么验证的」。
- 提交前自查：五道质量门全绿、`git status` 无多余文件、文档已按 §6 更新。
- CI（`.github/workflows/ci.yml`）会在 push 与 PR 上跑：`uv sync --locked` → `ruff format --check` → `ruff check` → `mypy` → `pytest`。
  **`--locked` 是刻意的**：它断言 `uv.lock` 与 `pyproject.toml` 同步 —— 改了依赖却忘了 `uv lock`，CI 立刻红。

## 9. 许可证

本项目以 [MIT](LICENSE) 分发。提交贡献即表示你同意以同一许可证（MIT）授权该贡献
（inbound = outbound：进来和出去用同一套条款，否则使用时会出现「有一部分代码不能用」的版权空洞）。
