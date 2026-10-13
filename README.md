# LLM Service

> 一个从零搭建的 LLM 应用后端。工程规范先行，逐步演进为**带量化评估的中文 RAG 知识库问答服务**。

**当前状态**：阶段 0 · 工程基础（依赖管理 / 版本控制 / 项目结构 / 数据契约 / 静态检查）已完成，
阶段 1 · FastAPI 服务开发中。详见[路线图](#路线图)。

---

## 这是什么

面向 LLM 应用的**异步后端服务**。与常见的"跑通一个 demo"不同，本项目的重点在**工程地基**：

- 每次结论都有**可复现的环境**支撑（依赖锁定 + 隔离环境 + 精确的 Python 版本）
- 每行代码都过**静态检查**（类型 strict 模式 + 格式化 + lint）
- 每个"为什么这样设计"都写在[开发笔记](study_notes/)里，包括**踩过的坑和定位过程**

业务逻辑目前用 `echo` 占位，随阶段推进替换为真实的 LLM 调用与检索逻辑。

---

## 技术栈

| 层 | 选型 | 当前版本 |
|---|---|---|
| 语言 | Python（由 uv 托管的独立解释器，不依赖系统 Python） | 3.12.15 |
| 环境与依赖 | **uv**（`pyproject.toml` 声明 + `uv.lock` 锁定） | uv 0.12.23 |
| 数据契约与配置 | pydantic / pydantic-settings | 2.13.5 / 2.15.0 |
| 静态检查 | mypy（strict）/ ruff | 2.4.0 / 0.16.10 |
| Web 框架 | FastAPI + uvicorn | 阶段 1 引入 |
| 数据库 | SQLAlchemy 2.0 async + SQLite → PostgreSQL | 阶段 1 引入 |
| 测试 | pytest + pytest-asyncio | 阶段 1 引入 |
| 交付 | Docker（多阶段构建 + 非 root 运行） | 阶段 1 引入 |

依赖分工：**运行必需的**写在 `[project] dependencies`，**仅开发需要的**（mypy / ruff / pytest）写在
`[dependency-groups] dev` —— 生产镜像可以用 `uv sync --frozen --no-dev` 一句排除掉。

---

## 快速开始

前置：安装 [uv](https://docs.astral.sh/uv/)（唯一需要手动准备的工具）。

```bash
git clone https://github.com/Tanking020/llm-app-engineering.git
cd llm-app-engineering

# 1. 按 uv.lock 还原出逐位一致的依赖环境（同时自动装 Python 3.12）
uv sync

# 2. 生成本地配置文件
cp .env.example .env

# 3. 验证环境（可选）
uv run python -c "from app.config import settings; print(settings)"
```

> 所有命令都用 `uv run` 前缀。原因是 `uv run` 会自动指向项目自己的 `.venv`，
> 并在依赖发生变化时**先自动同步**，避免"装了依赖却仍然导入失败"这类问题。

---

## 项目结构

```text
.
├── pyproject.toml            # 唯一事实来源：元数据、依赖、构建配置、所有工具配置
├── uv.lock                   # 精确依赖清单（含哈希）—— 提交，保证可复现
├── .python-version           # 本项目使用的 Python 版本（精确指定，而非范围）
├── .gitignore / .gitattributes
├── .env.example              # 配置模板（提交）；真实取值放 .env（不提交）
│
├── src/app/                  # 应用代码
│   ├── __init__.py
│   └── config.py             # 全部可调参数集中在这里，类型安全且带校验
│
├── playground/               # 实验区：一次性验证代码，随时可删，不参与交付
│
└── study_notes/              # 开发笔记：设计理由、踩坑记录、阶段规划
```

### 为什么用 `src` 布局

`src/app/` 而不是根目录直接放 `app/`，是为了**强制暴露打包配置的问题**：

- 扁平布局下 `import app` 能成功，只是因为"当前工作目录恰好被加进了模块搜索路径"，属于**碰巧**
- `src` 布局下必须先真正"安装"项目才能导入 —— 配置写错会立刻报 `ModuleNotFoundError`，
  而不是等到使用者 `pip install` 之后才暴露

代价是多了一层目录和一个 `[build-system]` 配置，换来的是**打包正确性有保障**。

---

## 质量门

提交前跑这四条，全部通过：

```bash
uv run ruff format .          # 1. 格式化
uv run ruff check . --fix     # 2. lint（规则集 E/F/I/UP/B）
uv run mypy                   # 3. 类型检查（strict + warn_unreachable）
uv run pytest -q              # 4. 测试（阶段 1 起）
```

当前状态：

| 检查 | 结果 |
|---|---|
| `ruff check src` | All checks passed! |
| `ruff format --check src` | already formatted |
| `mypy` | Success: no issues found |

mypy 采用 `strict = true`（要求函数写类型注解、禁止隐式 `Any` 等），并额外开启 `warn_unreachable`
—— 后者**不在 `strict` 预设内**，需要显式打开，用于发现"永远执行不到"的死代码。

---

## 关键技术决策

| 决策 | 理由 | 代价 / 取舍 |
|---|---|---|
| **uv + `uv.lock`** 而非 `requirements.txt` | `requirements.txt` 无法表达"意图"（只能写死版本），且不锁定间接依赖；`uv.lock` 记录求解结果 + 哈希，换机器能装出**逐位一致**的环境 | 多一个需要提交的文件；团队需统一使用 uv |
| **`src` 布局 + 可安装包** | 见上文「为什么用 src 布局」 | 多一层目录；需显式声明 `packages = ["src/app"]` |
| **pydantic 管理配置**（而非 `os.environ` 散落各处） | ① 类型自动转换与校验 ② 报错**点名到字段**（`port` + `input_value='abc'`），而非 `invalid literal for int()` ③ 读一个类就知道有哪些可调参数 | 引入一层抽象；需要理解环境变量与 `.env` 的**优先级**（真实环境变量 > `.env` > 默认值） |
| **配置严格模式 `extra="forbid"`** | 键名拼错（如把 `PORT` 写成 `PORTT`）会**立即报错**，而不是被静默忽略 —— 后者是"以为配好了、其实没配上"的隐蔽 bug | 若将来多个工具共用同一个 `.env`，别人的键会导致启动失败（届时应按工具拆分配置文件） |
| **`.venv` 与 `.env` 永不提交** | 二者都可由仓库内文件重建（`.venv` ← `uv.lock`）或属于本机私有（`.env` 含密钥）。尤其密钥：Git 历史**只增不减**，一旦提交只能吊销重发 | 新人需多跑一条 `cp .env.example .env` |
| **异步优先（`async`/`await`）** | LLM 应用的时间几乎全花在"等"（等模型返回 1~30 秒、等数据库、等外部 API）。同步写法在等待时占住执行权，并发请求会退化成串行 | 需避免在异步路径里调用阻塞库；CPU 密集任务更适合进程池 |
| **mypy strict + ruff 双工具** | 二者分工不同：**ruff 管"形状"**（格式、导入顺序、可疑写法），**mypy 管"含义"**（类型是否自相矛盾）。后者需要理解代码语义，是 ruff 做不到的 | 严格模式初期会报较多错，需要写全类型注解 |

---

## 路线图

| 阶段 | 内容 | 产出 | 状态 |
|---|---|---|---|
| **0 · 工程基础** | 依赖管理、版本控制、项目结构、数据契约、静态检查 | 规范的项目骨架 | ✅ 已完成 |
| **1 · FastAPI + 数据库** | 路由、依赖注入、中间件、异常处理、**SSE 流式响应**、SQLAlchemy 异步 CRUD | 可运行的聊天接口后端（业务逻辑先 echo 占位） | 🚧 进行中 |
| **2 · LLM 原生 API** | OpenAI 兼容接口、流式消费、token 与成本核算、Function Calling、结构化输出 | 手写的 LLM 调用层（不依赖 LangChain） | ⬜ |
| **3 · RAG** | 文本切分策略、Embedding 选型、**混合检索（BM25 + 向量 + RRF）**、Rerank、引用溯源、**RAGAS 量化评估与参数消融** | 带评估报告的中文知识库问答系统 | ⬜ |
| **4 · Agent + 部署** | 多步规划、工具调用、LangGraph、可观测性、容器化部署 | 真实场景的多步 Agent 服务 | ⬜ |

---

## 开发笔记

`study_notes/` 记录了设计理由与实证过程，其中**踩坑记录都带最小复现和定位方法**，例如：

- PowerShell 读取 UTF-8 中文文件的乱码：用 GBK 解码所致 —— 结合字节级检查定位，而非贸然重写文件
- `.gitattributes` 放在子目录导致规则**静默失效**：用 `git check-attr` 验证，而非假设
- TOML 表头写错导致的"键归属错误"：报错信息只说类型不对，根因却是少了表头
- `extra="ignore"` 静默吞掉拼错的配置键：改为 `forbid` 后错误暴露在启动时

| 文档 | 内容 |
|---|---|
| [能力档案与路线图.md](study_notes/能力档案与路线图.md) | 目标、能力缺口分析、阶段规划 |
| [阶段0-工程基础.md](study_notes/阶段0-工程基础.md) | uv / Git / 项目结构 / pydantic / 类型注解 / 异步 / 测试 / lint / Docker |
| [阶段1-FastAPI速成.md](study_notes/阶段1-FastAPI速成.md) | HTTP/ASGI → 三段参数 → 依赖注入 → 中间件 → SSE 流式 → 数据库 → 测试 → 部署 |
| [学习过程记录.md](study_notes/学习过程记录.md) | 步骤流水、踩坑记录、关键结论 |
| [工具与依赖速查.md](study_notes/工具与依赖速查.md) | 第三方包与工程工具速查：定位、安装、常用 API 与命令、易错点 |
| [工程规范与协作约定.md](工程规范与协作约定.md) | 本项目的工程规范：命名、分层、质量门、安全约定 |

---

## 说明

本项目为个人学习与能力展示用途，处于持续开发中。仓库中的笔记与代码均经过实测，
具体版本号与环境细节以 `pyproject.toml` / `uv.lock` 为准。
