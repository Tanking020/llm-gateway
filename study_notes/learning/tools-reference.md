# 工具与依赖速查

> **这份文件是干什么的**：把本项目用到的**工具**（uv / ruff / mypy）和**第三方库**（pydantic / pydantic-settings / httpx）
> 集中记在一处 —— **它解决什么问题、怎么装、最常用的 API 与命令、在我们项目里落在哪个文件、哪里容易踩坑**。
>
> **与其它笔记的分工**（避免重复）：
>
> | 想知道 | 去哪看 |
> |---|---|
> | **为什么**要这样设计、原理推演 | [stage0-engineering-basics.md](stage0-engineering-basics.md) / [stage1-fastapi.md](stage1-fastapi.md) |
> | 我**做过什么**、踩过什么坑 | [learning-log.md](learning-log.md) |
> | 我现在在哪、下一步做什么 | [project/roadmap.md](../project/roadmap.md) |
> | **自检题与简要答案**（复习用） | [self-check-questions.md](self-check-questions.md) |
> | **这个包怎么用**（速查） | **本文件** |
>
> ⚠️ **更新规则（硬约束，已写入 [工程规范与协作约定.md](../../工程规范与协作约定.md) §12.2）**：
> **每给项目加一个新依赖或新工具，同一轮内必须**：① 在本文件新增一节；② 更新下面 §0 总览表。
> **只装不记 = 这一步没完成。**
>
> 下面所有版本号与行为都是**在本机实测**得到的（记录日期 2026-10-13），不是照抄文档。

---

## 0. 总览

| 类别 | 名字 | 一句话定位 | 怎么进来的 | 步骤 | 本节 |
|---|---|---|---|---|---|
| 工具 | **uv** | 管 Python 版本、虚拟环境、依赖、锁文件、运行命令 | 独立安装，非项目依赖 | 0.2 ~ 0.4 | [§1](#1-uv工程工具) |
| 库 | **pydantic** | 用类型注解声明"数据长什么样"，并在门口完成校验与转换 | `uv add pydantic` | 0.11 | [§2](#2-pydantic数据校验) |
| 库 | **pydantic-settings** | pydantic 的子类，额外会从环境变量 / `.env` 读配置 | `uv add pydantic-settings` | 0.15 | [§3](#3-pydantic-settings配置) |
| 工具 | **mypy** | 不运行代码，按类型注解静态查错 | `uv add --dev mypy` | 0.20 | [§4](#4-mypy类型检查) |
| 工具 | **ruff** | 一个工具干两件事：排版（format）+ 查可疑写法（check） | `uv add --dev ruff` | 0.21 | [§5](#5-ruff排版--lint) |
| 库 | **httpx** | 同步 + **异步**都支持的 HTTP 客户端 | `uv add httpx` | 0.27 | [§6](#6-httpxhttp-客户端) |
| 库 | **fastapi** | 把带类型注解的函数变成 HTTP 接口；自动校验 + 自动生成 API 文档 | `uv add fastapi` | 1.1 | [§7](#7-fastapihttp-框架) |
| 工具 | **uvicorn** | ASGI 服务器：监听端口、解析 HTTP、把请求交给 `app` 对象 | `uv add "uvicorn[standard]"` | 1.1 | [§8](#8-uvicornasgi-服务器) |
| 标准库 | **logging** | 分级日志事件流（替代 `print`）；默认落 stderr，**不写文件** | Python 自带，无需安装 | 6.3b | [§9](#9-loggingpython-标准库不是项目依赖) |
| 库 | **SQLAlchemy** | 用 Python 类映射数据库表，并组织查询与事务 | `uv add "sqlalchemy[asyncio]>=2.1,<2.2"` | 阶段 1 · Step 10 | [§10](#10-sqlalchemy-21-异步-orm-与-aiosqlite) |
| 库 | **aiosqlite** | 让 SQLite 操作可以 `await`（SQLAlchemy 的异步 SQLite 驱动） | `uv add aiosqlite` | 阶段 1 · Step 10 | [§10](#10-sqlalchemy-21-异步-orm-与-aiosqlite) |
| 概念 | **健康探针** | 编排平台定期打一个 HTTP 路径来判断「进程活着 / 能接流量」；**配置在 YAML 里，不在代码里** | 无需安装（k8s / Docker 能力） | 阶段 1 · 10.6d-3（端点）/ Step 13（配置） | [§11](#11-健康探针k8s--docker-配置层不是代码层) |
| 标准库 | **time**（时钟） | `time` / `monotonic` / `perf_counter` 三个时钟**不能互换**：一个会被改表，两个不会 | Python 自带，无需安装 | 阶段 1 · Step 7（请求计时） | [§12](#12-时钟time--monotonic--perf_counter) |

**本机版本基线（实测）**：`uv 0.12.23` / `pydantic 2.13.5` / `pydantic-settings 2.15.0` / `mypy 2.4.0` / `ruff 0.16.10` / `httpx 0.28.1` / `fastapi 0.143.0` / `uvicorn 0.54.0` / `starlette 1.8.0` / `sqlalchemy 2.1.6` / `greenlet 3.5.6` / `aiosqlite 0.22.1`

**还没装（用到再补节，不提前写空节）**：`httpx2`（Starlette 已开始推荐，见 §6 的换代警告；**暂不装**）、`pytest`（阶段 1 后半）。

---

## 1. uv（工程工具）

**解决什么问题**：把过去要手工拼的五件事合成一个工具 —— ① 装/切 Python 版本 ② 建虚拟环境 ③ 解析依赖并选版本 ④ 记锁文件 ⑤ 在项目环境里跑命令。
（对比：老办法要用 `pyenv` + `venv` + `pip` + `pip-tools` + 手记 README。）

**两条心智模型**（比记命令更重要）：

1. **`uv run` 是"进入项目环境执行"**。直接用系统 `python xxx.py` 可能用的是**另一个解释器**，`import app` 会失败。
2. **`pyproject.toml` 只声明"允许的版本集合"，`uv.lock` 才决定"实际用哪个"**。改约束不会自动升版本，`uv lock --upgrade` 才会。

### 常用命令

| 命令 | 干什么 | 会改哪些文件 |
|---|---|---|
| `uv --version` | 看 uv 自己的版本 | — |
| `uv python pin 3.12` | 固定本项目 Python 版本 | `.python-version` |
| `uv sync` | 按锁文件建出 / 修好 `.venv` | `.venv/` |
| `uv add httpx` | 加**运行**依赖（会顺带解析 + 装 + 更新锁文件） | `pyproject.toml`、`uv.lock`、`.venv/` |
| `uv add --dev mypy` | 加**开发**依赖（放在 `[dependency-groups] dev`，不进运行环境） | 同上 |
| `uv remove httpx` | 删依赖 | 同上 |
| `uv run <命令>` | 在项目环境里执行（如 `uv run python -m app.main`） | — |
| `uv tree` | 看依赖树（谁是谁的依赖） | — |
| `uv lock` | 按当前约束重算锁文件 | `uv.lock` |
| `uv lock --upgrade` | **升级**依赖版本 ⚠️ 破坏性升级可能从这一天进来 | `uv.lock` |
| `uv version` | 读/改**本项目自己**的版本号（不是 Python 版本） | `pyproject.toml` |

### 易错点

- **`uv add` 输出里的数字要会读**：`Resolved 20 packages` 是**整个依赖图**的包数，不是新增 20 个；`+` 才是新装的；`~ llm-app-engineering` 是本地项目包被重建，**不代表项目版本升级**。
- **直接依赖 vs 间接依赖**：你只声明 `httpx`，它自带 `httpcore` / `anyio` / `certifi` / `h11` / `idna` 一起装上 —— `dependencies` 里**声明意图，不声明结果**。
- **别用 `pip install`**：那样装进环境却**没写进 `pyproject.toml`**，别人 `uv sync` 复现不出来。

---

## 2. pydantic（数据校验）

**解决什么问题**：外部来的数据（HTTP 请求体、LLM 返回、文件内容）**都不可信**。pydantic 让你用**类型注解**描述"数据长什么样"，
然后在数据进入业务逻辑**之前**完成三件事：**解析**（`"123"` → `123`）、**校验**（不合法就报错）、**序列化**（对象 → JSON）。

### 常用语法

| 写法 | 作用 |
|---|---|
| `class Message(BaseModel):` | 声明一个数据模型（`BaseModel` 是"会校验的类"） |
| `role: Literal["system", "user", "assistant"]` | 值只能是列出的几个之一（拼错**立刻**报错，而非静默走错分支） |
| `content: str` | 类型注解；**没有默认值 = 必填** |
| `model: str \| None = None` | 有默认值 = 可选；本项目用它表达"客户端不指定，由服务端配置兜底" |
| `messages: list[Message] = Field(min_length=1)` | 嵌套模型（逐元素递归校验）+ 列表长度约束 |
| `Field(default=0.7, ge=0.0, le=2.0)` | 单项约束：`ge/gt` 数值下界，`le/lt` 上界，`min_length/max_length` 长度，`pattern` 正则，`description`（**会进 OpenAPI 文档**） |
| `int \| None = Field(default=None, gt=0)` | "整数或空"；`gt=0` 表示"填了就必须大于 0" |
| `@field_validator("content")` + `@classmethod` | 内置约束表达不了的规则（如跨字段比较）；⚠️ **不要用它做 strip** —— 见下方「`StringConstraints`」实测，长度约束在它**之前**执行 |
| `Model.model_validate(原始数据)` | dict / JSON → 模型对象（校验入口） |
| `obj.model_dump()` | 模型 → **dict** |
| `obj.model_dump_json()` | 模型 → **JSON 字符串** |

### `StringConstraints`：给「字符串类型本身」加约束（2026-10-25 实测，10.5f）

**解决什么问题**：`Field(min_length=1)` **只数字符个数，不看内容** —— `"   "` 长度是 3，能通过校验，
然后库里存进 3 个空格，前端显示一个空白标题。需要的是「**先去掉首尾空白，再判长度**」。

**本项目实际写法**（`src/app/schemas.py`，一处定义两个契约共用）：

```python
from typing import Annotated
from pydantic import Field, StringConstraints

ConversationTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]

class ConversationIn(BaseModel):
    title: Annotated[ConversationTitle, Field(description="对话标题")]

class ConversationPatch(BaseModel):
    title: Annotated[ConversationTitle, Field(description="新的对话标题")]
```

**常用参数**

| 参数 | 作用 |
|---|---|
| `strip_whitespace=True` | **先**去掉首尾空白（含 `\t` `\n` 和全角空格 `\u3000`），**再**做长度校验 |
| `min_length` / `max_length` | 长度上下界（作用于 strip **之后**的字符串） |
| `to_lower=True` | 转小写（本项目未用） |
| `pattern=r"..."` | 正则约束（本项目未用） |

**📎 实测：修前 vs 修后（`POST` / `PATCH` 同一个类型）**

```text
                修前（Field(min_length=1)）        修后（strip_whitespace=True）
"   "          -> 200  ⚠️ 存进 3 个空格             422 string_too_short
"\t\n"         -> 200  ⚠️                          422 string_too_short
"\u3000\u3000" -> 200  ⚠️（全角空格）                422 string_too_short
"  首尾有空格  " -> 200  存 "  首尾有空格  "（带空格）   201  存 "首尾有空格"（strip 了）
```

**📎 实测：为什么不能用 `field_validator` 代替**

| 输入 | `Field(min_length=1)` + `field_validator` 里 strip | `StringConstraints(strip_whitespace=True)` |
|---|---|---|
| `"   "` | 422 **`value_error`** | 422 **`string_too_short`** |
| `" " + 100个a + " "`（102 字符） | **422 `string_too_long`** ⚠️ **误拒** | **200** ✅ strip 后正好 100 |
| `"  新标题  "` | OK `"新标题"` | OK `"新标题"` |

⭐⭐ **根因**：**`Field(min_length/max_length)` 在 `field_validator` 之前执行** ——
所以先按**原始长度（含空格）**判超长，validator 根本没机会 strip。

⭐⭐ **判据**：
- **「先清洗再判长度」→ 必须 `StringConstraints`**
- `field_validator` 只做**长度之外**的自定义校验，且报错类型会变成 `value_error`（客户端要额外分支）

**易错点**

- ⚠️ `Annotated` 里**顺序无关**，但 `StringConstraints` 内部的 strip 和长度校验**顺序固定**（strip 在前）
- ⚠️ 只写 `StringConstraints(min_length=1)` **不带** `strip_whitespace` 等于没修 —— `"   "` 照样通过
- ⭐ `Annotated[ConversationTitle, Field(description="…")]` **可以叠加** —— OpenAPI 里 `description` / `minLength` / `maxLength` 三样都在（📎 实测）

### 实测：校验成功与失败长什么样

```python
ChatRequest(messages=[Message(role="user", content="hi")])
# 输出：messages=[Message(role='user', content='hi')] model=None temperature=0.7 max_tokens=None
#        ↑ model 默认 None = "客户端没指定"，由服务端用 config.llm_model 兜底

ChatRequest(messages=[Message(role="user", content="hi")]).model_dump()
# 输出：{'messages': [{'role': 'user', 'content': 'hi'}], 'model': None,
#        'temperature': 0.7, 'max_tokens': None}

ChatRequest.model_validate({"messages": []})            # 空列表
# 报错：loc=('messages',)        type=too_short

ChatRequest.model_validate({"messages": [{"role": "tool", "content": "x"}]})   # role 不在允许值里
# 报错：loc=('messages', 0, 'role')   type=literal_error
```

⭐ **`loc` 会精确指到出错的位置**（`messages[0].role`），`type` 是机器可读的错误种类。这就是"当场验货"的价值：报错离**真正的源头**很近。
捕获方式：`except ValidationError as exc:` 然后 `exc.errors()`。

### 🌟 `field_validator`：`mode="before"` 还是 `"after"`

| | `mode="before"` | `mode="after"`（默认） |
|---|---|---|
| 收到的值 | **原始值**（可能是 `str` / `int` / `None`） | **已校验转换好的**值 |
| 返回值还会被校验吗 | ✅ 会（写错类型会抛 `ValidationError`） | ❌ **不会**（直接进模型，只在序列化时 warning） |
| 适合干什么 | 把字符串 / 数字**转换成**目标类型 | 对**已校验好**的值做修正（补时区、裁剪、判空） |

📎 实测（同一个「给 naive datetime 补 UTC」的需求）：

| 输入 | `before` | `after` |
|---|---|---|
| naive `datetime`（ORM 对象） | ✅ 补 Z | ✅ 补 Z |
| **字符串** `"2026-10-28T05:51:54.604445"` | ❌ **输出无 Z** | ✅ 补 Z |
| `None` | ✅ 跳过 | ✅ 跳过 |

**before 在字符串输入时为什么静默失效**：

```text
before 收到: str       '2026-10-28T05:51:54.604445'    ← isinstance(v, datetime) 为 False
after  收到: datetime  datetime(2026, 10, 28, 5, 51, 54, 604445)
```

📎 `after` 的坑（返回值不重校验）—— 让 validator 故意返回 `"我就是个字符串"`：

```text
before: ValidationError 被拦下
after : 建对象【成功】，t = '我就是个字符串'，只在序列化时给 warning
```

⭐⭐ 判据：**「转换类型」用 before，「修正已校验的值」用 after。**

⚠️ **`@classmethod` 跟 mode 无关**：pydantic 对两种 mode **都要求**必须是类方法/静态方法。

```text
before 不加 @classmethod -> PydanticUserError: cannot be applied to instance methods
after  不加 @classmethod -> PydanticUserError: cannot be applied to instance methods（一模一样）
```

⚠️ **父类上的 validator 会被子类继承**（跟着字段走）→ 在基类写一次，所有子类生效。

### 易错点

- **`default=datetime.now()` 是错的**：默认参数在**函数定义时**求值一次 → 所有对象共享同一个时间戳。要用 `default_factory=lambda: ...`（每次创建时才求值）。
- **字段名不是 Python 保留字，而是"接口 JSON 的键名"**：改字段名 = 改 API 契约，客户端也会跟着不兼容。
- **`extra="forbid"` 还是 `"ignore"`**：本项目选 `forbid`，因为拼错键名时会**直接报错**，而不是被静默丢掉（静默失效最难查）。

---

## 3. pydantic-settings（配置）

**解决什么问题**：配置既要**类型安全**（端口是 `int` 不是字符串），又要能**从环境变量 / `.env` 读**，且**换环境不改代码**。

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",              # 去工作目录下的 .env 读
        env_file_encoding="utf-8",    # Windows 上不写可能按 GBK 读 → 中文乱码
        extra="forbid",               # .env 里有没定义的键就报错
    )
    port: int = 8000                  # 环境变量 PORT=9001 会自动覆写它

settings = Settings()                 # 模块级单例，全项目共用这一个
```

| 要点 | 说明 |
|---|---|
| 环境变量名 | **= 字段名转大写**（`app_env` ← `APP_ENV`），匹配时大小写不敏感 |
| 类型转换 | `.env` 里写的是文本，`"8000"` 会自动转成 `int 8000`；`true/1` 转 `bool` |
| 优先级 | 真实环境变量 **高于** `.env` |
| 引用方式 | 其它文件只写 `from app.config import settings`，**不直接读 `os.environ`** |

**易错点（真实踩过）**：

- **`env_file=".env"` 是相对「当前工作目录」解析的**，不是相对 `config.py` 所在目录。在子目录里启动 → 读不到 → **静默退回默认值，不报错**。所以要在**项目根**启动。
- `.env` 键名拼错时，`extra="ignore"` 会**默默丢掉**；改 `forbid` 才能暴露。

---

## 4. mypy（类型检查）

**解决什么问题**：在**不运行代码**的前提下，按类型注解查错 —— 把错误从"上线后崩"提到"写代码时"。
它和运行时检查的分工：mypy 管**静态可知**的错误（类型不匹配、可能为 `None`），测试管**动态行为**（值对不对、分支走没走对）。

### 常用命令

| 命令 | 干什么 |
|---|---|
| `uv run mypy .` | ⭐ **本项目质量门的标准写法**（全项目 `.py`，含 `playground/`）—— **2026-10-14 起统一** |
| `uv run mypy` | 按 `pyproject.toml` 里 `files` 检查。**2026-10-14 起 `files = ["."]`，与 `mypy .` 等价**（此前是 `["src"]`，只查 4 个文件，容易误判成"全绿"） |
| `uv run mypy --strict` | 打开一整组严格开关（本项目已在配置里开 `strict = true`） |
| `uv run mypy --show-error-codes` | 显示错误码（`--strict` 已含此项） |
| `uv run mypy --install-types` | 给缺类型注解的第三方库装 stub 包 |

**它必须在配置里认识你的项目结构**：本项目配置为 `python_version = "3.12"`、`strict = true`、`warn_unreachable = true`、`files = ["."]`。

### 实测的错误码（本项目真实出现的）

| 错误码 | 含义 | 触发场景 |
|---|---|---|
| `union-attr` | 对"可能是 `None`"的值取属性 | `cur.next.val` 而 `next: Node \| None` |
| `no-untyped-def` | 函数没写类型注解（strict 下报） | 新写的函数漏注解 |
| `assignment` | 赋值类型不匹配 | 把 `str` 赋给 `int` 变量 |
| `return-value` | 返回值类型与声明不符 | 声明 `-> int` 却 `return None` |
| `no-any-return` | 把 `Any` 当具体类型返回 | `.json()` 返回值直接 `return` |
| ⭐ `attr-defined` | **对象上不存在这个属性** | `request.message`（实际字段叫 `messages`）—— 实测报错原文：`"ChatRequest" has no attribute "message"; maybe "messages"?  [attr-defined]` |

⭐ **`attr-defined` 是"拦住 500 的那道闸门"**（2026-10-15 实战）：`request.message` 少打一个 `s`，**语法合法、ruff 通过**，但运行时抛
`AttributeError` → FastAPI 回 **500 Internal Server Error**（客户端只看得到这五个字，真正原因只在服务端日志里）。
**mypy 在写代码时就抓到它，并直接给出了正确拼写建议** —— 这就是"注解让工具有的可查"的兑现。

> ⚠️ **为什么 pydantic 模型能被 mypy 检查属性**：pydantic 2.x 自带 `py.typed` 标记并提供了 mypy 插件，
> 所以 `BaseModel` 子类**声明过的字段名对 mypy 可见** —— 拼错字段名/属性名会被静态查出。
> 这也意味着：**给数据模型写好类型注解 = 顺手获得"字段名拼写检查"**。

### 易错点

- **没注解 = mypy 无能为力**。它能抓到 `None` 解引用，**前提是你写了 `self.next: Optional[Node] = None`**。
- `# type: ignore` **必须带错误码**（如 `# type: ignore[union-attr]`），否则会连带屏蔽那一行**未来所有**的类型错误。
- `Success: no issues found in N source files` 里的**文件数**是范围信号：数不对，先怀疑你查的路径。
- ⚠️⚠️ **"这次没报错" ≠ "工具发现问题不了它"** —— 2026-10-15 我犯过这个推理错误：在**已修好**的代码上跑 mypy 得到 `Success`，
  就断言"mypy 抓不到这个 typo"。**要判断某工具能不能抓某类问题，必须故意构造那个问题再跑**（判定性实验），
  不能拿一次"通过"反推"能力缺失"。这和 E501 那次（用管道喂中文导致错误结论）是同一类错误：**结论必须来自能证伪的实验**。

---

## 5. ruff（排版 + lint）

**解决什么问题**：一个工具干两件事 —— `format`（排版，机械统一风格）+ `check`（lint，找可疑写法与真 bug）。
用 Rust 写的，比老一代工具快一两个数量级，所以可以放心放进每次收口。

### 常用命令

| 命令 | 干什么 | 会改文件吗 |
|---|---|---|
| `uv run ruff format .` | 按统一风格排版 | ✅ **会直接改** |
| `uv run ruff format --check .` | 只检查"是否会改"，**不改文件**（质量门用这个） | ❌ |
| `uv run ruff format --diff .` | 把将会改的内容当 diff 打出来 | ❌ |
| `uv run ruff check .` | lint（质量门用这个） | ❌ |
| `uv run ruff check . --fix` | 自动修可修的项 | ✅ **会直接改** |
| `uv run ruff check . --diff` | 打印将会修的 diff | ❌ |
| `uv run ruff check . --statistics` | 按规则统计各类问题数量 | ❌ |
| `uv run ruff check . --select I` | 只跑指定规则族（排查单个问题时很有用） | ❌ |

> ⚠️ **两个 `--fix` 的教训**：`--fix` 改完文件**必须** `git diff` 看一眼，并**重跑三条质量门** —— 修复类工具（check）和校验类工具（format）可能互相影响。

### 为什么质量门必须用 `--check` 而不是直接 `format`（2026-10-15 实测）

**会改文件的那个，永远给不出判定。** 实测两个命令的退出码：

| 命令 | 退出码 | 说明 |
|---|---|---|
| `ruff format .`（文件不合规时） | **0** | 它先把文件改好了，然后报告"我成功了" |
| `ruff format --check .`（文件不合规时） | **1** | 只读，明确告诉你"不合规" |

于是 `ruff format . && echo OK` 在**任何情况下**都会打印 OK —— 这就是**假绿灯**：
它把"问题被自动修掉了"和"本来就没问题"混成同一个结果。

⭐ **判定性实验**：造一个格式错乱的文件，跑完 `format` 再用 `format --check`，
前者退出码 0 但文件已变、后者把问题如实报成 1。**凡是"会自我修复"的检查，
都不能当验收标准**；它只能当**修复工具**用。

**正确分工**：日常改代码时用 `format .`（让它替你把活干了）；**收口 / CI 判定时用 `--check`**（要一个可信的红绿灯）。
`mypy` 和 `ruff check` 本身不改文件，所以它们天然可以当判定。

### 本项目启用的规则族（`select = ["E","F","I","UP","B"]`）

| 字母 | 来自 | 管什么 |
|---|---|---|
| `E` | pycodestyle | 缩进、空白等格式类问题 |
| `F` | Pyflakes | **真 bug**：未使用的 import/变量、未定义的名称 |
| `I` | isort | import 的排序与分组 |
| `UP` | pyupgrade | 把旧写法升级成新写法（如用 `X \| None` 代替 `Optional[X]`） |
| `B` | flake8-bugbear | 容易写出 bug 的写法（如可变默认参数） |

**`I001` 到底在管什么（实测确认）**：ruff 按**来源**把 import 分段 —— **标准库 → 第三方 → 第一方**，段与段之间**必须空一行**，段内才按字母序。

| 实测探针 | 结果 |
|---|---|
| `import os` + `import sys`（同为标准库） | ✅ 通过 |
| `import os` + `import httpx`（标准库 + 第三方） | ❌ `I001` |
| `import httpx` + `import pydantic`（同为第三方） | ✅ 通过 |

注意 `I001` 的原文是 `Import block is un-sorted **or** un-formatted` —— **两个独立条件，满足任一即报**。

### 易错点

- **`ruff format` 会格式化 markdown 里的 ` ```python ` 代码块**，会毁掉刻意对齐的教学示例 → 本项目用 `extend-exclude = ["*.md"]` 排除。
- **`ruff check` 默认不 lint markdown**，所以只需拦 `format`。
- **`ruff format` 会顺带补文件末尾换行**（POSIX 要求文本文件最后一行也以换行结尾）。
- **`ruff check` 默认不管行内注释前留几个空格**（实测 `x = 1 # c` 通过检查），但 `ruff format` 会统一成两个空格 —— 两个工具"管辖区"不同。
- ⚠️ **`E501` 按「显示宽度」算，一个汉字占 2 列**（2026-10-14 实测，**推翻了我此前的错误结论**）：`line-length = 100` 时，**中文注释大约只能写 40 个汉字**。判定性实验：106 个字符的行（含 90 汉字）报 **196**；45 汉字报 **106**；46 汉字报 **108** —— 与宽度算法完全吻合。
  > ⚠️ **踩坑背景**：我上次把中文**经 PowerShell 管道**喂给 ruff 的 stdin 做实验，编码被破坏（回显里汉字变成 `??`），于是得出"按字符数算"的错误结论。**教训：把中文喂给命令行工具时走文件，别走管道；并检查工具回显的内容是不是你写进去的。**
- ⚠️ **BOM 会让 `ruff format` 直接崩溃**（2026-10-14 实测，ruff 0.16.10）：判定性实验三种写法 —— PowerShell `Set-Content -Encoding UTF8` 写出的文件**前 3 字节是 `EF BB BF`（BOM）**，`ruff format --check` → **panic，退出码 101**（`Annotation range ... is beyond the end of buffer`）；同一份内容改用 `.NET` 无 BOM 写入 → **正常**；项目里 VS Code 保存的文件（首字节 `22 22 22`）→ **正常**。⚠️ **`ruff check` 不受影响**（所以容易漏发现）。
  - **实践规则**：**用脚本生成 `.py` 临时文件时，一律用 `[IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))`（无 BOM）**；项目文件交给 VS Code 保存即可。
  - 判据：文件首 3 字节是否为 `EF BB BF`。

---

## 6. httpx（HTTP 客户端）

**解决什么问题**：发 HTTP 请求；而且**同时支持同步与异步** —— 这是它取代 `requests` 的关键（`requests` 只有同步，在 `async def` 里用会**阻塞事件循环**）。

### 两种客户端

| 用途 | 写法 | 说明 |
|---|---|---|
| 异步（项目主线） | `async with httpx.AsyncClient(timeout=10.0) as client:` + `await client.get(...)` | 进 `async def` 里用；忘写 `await` 只会拿到协程对象 |
| 同步（脚本/工具） | `with httpx.Client() as client:` + `client.get(...)` | 拿了 `AsyncClient` 就别配同步写法，反之亦然 |

⭐ `with` / `async with` 的价值：**退出时自动关闭连接，即使中途抛异常**。

### 常用 API

| 写法 | 作用 |
|---|---|
| `client.get(url)` / `.post(url, json=...)` | 发请求；`params=` 查询参数，`headers=` 请求头，`json=` JSON 请求体 |
| `response.status_code` | 状态码（`int`）；2xx 表示成功 |
| `response.url` | **最终实际**请求的地址（URL 对象，打印时转文本） |
| `response.headers` | 响应头（大小写不敏感地取值：`response.headers.get("content-type")`） |
| `response.text` | 响应正文，**原始字符串**（未解析） |
| `response.json()` | 把正文**解析成 dict / list**（解析失败会抛异常） |
| `response.raise_for_status()` | 4xx/5xx 就抛 `httpx.HTTPStatusError`；正常时什么也不做 |

### 实测默认行为（要知道，否则会误判）

| 项 | 默认值 | 影响 |
|---|---|---|
| `timeout` | `5.0` 秒 | 大模型接口要显式调大（本项目练习用 `10.0`） |
| `follow_redirects` | `False` | 遇到 3xx **不会**自动跳转 |
| `base_url` | `URL('')` | 不设就每次写完整 URL |

**`raise_for_status()` 的真实差别**：

```python
response = await client.get("https://httpbin.org/status/404")
print(response.status_code)        # 输出 404 —— 不报错，照常返回
response.raise_for_status()        # 这一行才抛 httpx.HTTPStatusError
```

> ⭐ 所以**不调用它，就没人替你检查错误**：404 的响应体会被当成正常数据继续处理下去。

### 异常分两支 + 与 `HTTPException` 的分工（2026-10-17 实测，6.2a）

```text
httpx.HTTPError
├── HTTPStatusError      ← 上游【有回应】但 4xx/5xx；有 .response / .request
└── RequestError         ← 上游【没有回应】；没有 .response（hasattr 实测 False）
    └── TransportError
        ├── TimeoutException
        └── NetworkError
            └── ConnectError
```

| | `httpx.HTTPStatusError` | `fastapi.HTTPException` |
|---|---|---|
| 属于谁 | httpx（客户端库） | fastapi（Web 框架） |
| 谁触发 | `raise_for_status()`，**上游**的行为 | **我们自己**写的 `raise` |
| FastAPI 认识吗 | ❌ 漏出去 = **500** | ✅ 有处理器翻译成 JSON |
| 语义 | "我调上游失败了" | "我要给**我的**客户端回这个码" |

⭐ **两层状态码不能混**：上游的 `401` 意思是"**我们服务器**的 key 不对"；若原样透传给客户端，客户端会以为
"**我要登录**"（实测透传后客户端收到 401）→ 在完全错误的方向上努力。**统一翻译成 502**，
上游具体号码只放 `detail` 与日志。

**两个语法**（实测）：

| 写法 | 作用 | 细节 |
|---|---|---|
| `except X as exc:` | 绑定异常**实例** | 只在块内有效，块外 `NameError`（Python 3 故意删名） |
| `raise Y from exc` | 设置 `Y.__cause__`（显式因果） | 无 `from` 时 `__cause__=None` 但 `__context__` 仍自动填；traceback 措辞从 "During handling…" 变成 "The above exception was the direct cause…"；本项目 `ruff` 的 **B904** 会强制要求 |

**`base_url` 的路径会被拼上**（实测）：`base_url="https://httpbin.org/status/503"` + 请求 `"/models"`
→ `https://httpbin.org/status/503/models`。所以 `base_url` 只写到域名 / 版本前缀。

### 易错点

- **URL 必须加引号**：`client.get(https://...` 是语法错误。
- **`.text` 截断会"看起来像坏了"**：实测 httpbin 返回 **304 字符** JSON，`.text[:80]` 正好切在 `"gz`（`gzip, deflate` 的开头）中间。它是**字符串**，不是解析后的数据；要取字段值必须 `.json()`。
- **`response.text` 里的换行**：响应体里的 `\n` 在终端会显示成真正的换行，所以输出会变成多行。
- **`httpx.MockTransport`**（阶段 1 写测试时用）：可以替换传输层，**不联网**也能测 HTTP 逻辑。

### ⚠️ 换代警告：`httpx2` 与 `StarletteDeprecationWarning`（2026-10-15 实测）

**症状**：只要 `import fastapi.testclient`（用 `TestClient`），就会打印：

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
```

**⚠️ 它不是报错** —— 程序继续跑、退出码仍是 0。**它和"脚本没输出"没有因果关系**（后者见下面 §7 的"零输出"陷阱）。

**触发条件是"三层 fallback"**（`starlette/testclient.py` 第 29~45 行源码）：

| 情况 | 结果 |
|---|---|
| 装了 `httpx2` | ✅ 静默使用，**无警告** |
| 只装了 `httpx` | ⚠️ **能用但警告** ← 本项目当前状态（`httpx 0.28.1`，`httpx2` 未安装） |
| 两个都没有 | ❌ 真 `RuntimeError` |

**为什么这条警告你看得见**（实测继承链）：

```text
StarletteDeprecationWarning -> UserWarning -> Warning -> Exception
```

它的源码注释写得很直白：*"Unlike the built-in `DeprecationWarning`, this inherits from `UserWarning`
to ensure it is visible by default"* —— **Python 默认隐藏内置 `DeprecationWarning`，starlette 故意继承
`UserWarning` 就是为了让你看见。**

**`httpx2` 是什么**（PyPI 查证，2026-10-15）：标题为 *"HTTPX2 — A next-generation HTTP client for Python"*，
作者是 **Tom Christie**（`httpx` 的作者本人），仓库 `github.com/pydantic/httpx2`（现挂 pydantic 组织下）。

⭐ **结论：这不是"你装错了包"，是上游正在换代。** 本项目暂时忽略它（按需引入依赖是既定原则）；
等真的要用 `TestClient` 写正式测试时，再讨论要不要 `uv add --dev httpx2`。

### 练习脚本

- [playground/httpx_demo.py](../../playground/httpx_demo.py) —— 第一个真实 HTTP 请求（步骤 0.27b）

---

## 7. FastAPI（HTTP 框架）

**解决什么问题**：把"一个带类型注解的普通 Python 函数"变成"一个 HTTP 接口"。没有它，你得自己解析报文、判断方法/路径、手动校验 JSON、手写文档 —— 这些它全包了。

**装法**：`uv add fastapi`（运行依赖）。**实测版本 0.143.0**。

### 最小骨架（本项目 `src/app/api/app.py`）

```python
from fastapi import FastAPI

app = FastAPI(title="llm-app-engineering", version="0.1.0")   # 应用对象 = uvicorn 要托管的那个东西


@app.get("/health")                                    # 装饰器的作用：往路由表里登记一行
async def health() -> dict[str, str]:
    return {"status": "ok"}                            # 返回 dict → 自动序列化成 JSON
```

### 实测：默认白送的 4 条路由

启动后**不用写一行代码**就拥有（实测 `app.routes` 列表，不启服务也能看）：

| 路径 | 用途 |
|---|---|
| `/docs` | ⭐ **交互式 API 文档站**，能直接点 "Try it out" 发真实请求 |
| `/redoc` | 另一套风格的文档（只读，不能试发） |
| `/openapi.json` | 上面两个文档站的**数据源**：机器可读的接口描述 |
| `/docs/oauth2-redirect` | `/docs` 页面做 OAuth2 登录时的回调页 |

⭐ 之所以"白送"，是因为 FastAPI **从你的类型注解和函数签名里读出了接口形状** —— 这就是"注解即文档"。

### 常用语法（最小集；路径/查询/请求体的细节在阶段 1 的 Step 3~4）

| 写法 | 作用 |
|---|---|
| `@app.get("/x")` / `@app.post("/x")` | 按 HTTP 方法注册路由 |
| `async def f(item_id: int)` | 参数注解 → **自动校验 + 自动转换类型** + 进文档 |
| `-> dict[str, str]` / `-> SomeModel` | 返回值注解 → 决定响应格式与响应文档，**并会过滤未声明字段**（见下） |
| `app.include_router(router)` | 把拆到别的文件里的路由挂上来（本项目 1.3 起用） |

### 实测：返回值注解不是注释，是"合同"（2026-10-15）

`-> ChatResponse` 等价于 `response_model=ChatResponse`，而 `response_model` **会剥掉你没声明的字段**。
探针实测（内存里临时搭的 app，`TestClient`；不写文件、不属于本项目）：

| 函数签名 | 实际返回的 JSON |
|---|---|
| `def a() -> ChatResponse:`（**有**注解） | `{'content':'hi','model':'m','usage_tokens':0}` |
| `def b():`（**无**注解） | `{'content':'hi','model':'m','usage_tokens':0,'secret':'TOP-SECRET'}` |

⭐ 结论：**返回注解 = 返回值合同**，既写进 `/docs` 的 200 schema（实测 `200 → $ref ChatResponse`），
也真的拦字段。**"随手不写返回类型"是有风险的。**

### 实测：想看装饰器到底登记了什么，打印 `app.routes`

```python
for r in app.routes:
    print(type(r).__name__, r.path, getattr(r, "methods", None), r.name)
```

实测输出（本项目）：白送的 4 条类型是 **`Route`**（Starlette 原生），自己写的 5 条是 **`APIRoute`**
—— 后者才是"带自动校验 + 自动文档"的那个类。`name` 列**就是函数名**（所以改函数名会让
`/docs` 的标题跟着变）。

### `Annotated` 与 `Query` 的分工（2026-10-15 实测）⭐

**一句话**：`Annotated` 是**信封**（怎么装），`Query` 是**信封里那张纸**（装什么）。

| | `Annotated` | `Query` |
|---|---|---|
| 从哪来 | `typing` —— **标准库**（实测 `Annotated.__module__ == "typing"`） | `fastapi`（`fastapi.param_functions.Query`） |
| 是什么 | 纯"打包袋"：`Annotated[类型, 元数据1, 元数据2, ...]` | pydantic `FieldInfo` 的子类 |
| 懂 HTTP 吗 | ❌ 完全不懂，**不解释**任何元数据 | ✅ 它就是"FastAPI 认识的词汇" |
| 干什么 | 把额外信息**挂**在类型上，**不改变类型** | 声明约束（`ge`/`le`/`min_length`）+ 文档（`description`） |

**实测：`Query` 的继承链**（`type(Query(...)).__mro__`）

```text
fastapi.params.Query → fastapi.params.Param → pydantic.fields.FieldInfo → object
```

**实测：`ge=1` 存在哪里**（极易想当然搞错）：

```python
q = Query(ge=1, le=3, description="d")
q.ge        # MISSING！Query 对象上根本没有这个属性
q.metadata  # [Ge(ge=1), Le(le=3)]  ← 被转成 pydantic 元数据对象
```

⭐ 约束最终由 **pydantic 的校验引擎**执行，`Query` 只是"声明书"。

**实测：`Annotated` 的运行时语义**

```python
a = Annotated[int, "any-metadata"]
a.__origin__      # int
a.__metadata__    # ("any-metadata",)
isinstance(1, a)  # TypeError: Subscripted generics cannot be used with class and instance checks
```

⭐ `Annotated[int, "随便什么"]` **不报错也不解释** —— 只有"认识它"的工具才去读（FastAPI 会读 `Query`，忽略字符串）。

### 为什么必须有 `Annotated`（它替掉了什么）

老写法（FastAPI 源码里称为 `alternative-old-query-as-the-default-value`）：

```python
async def f(limit: int = Query(20, ge=1, le=100)): ...   # ❌ 不要这样写
```

**实测：两种写法生成的 OpenAPI 完全一样**（都是 `minimum: 1, maximum: 100, description: "how many", default: 20`），
行为也一样（`limit=0` / `limit=101` 均 422）。差别在**代码本身**：

| 对比项 | 老写法 `= Query(20, ...)` | 新写法 `Annotated[...] = 20` |
|---|---|---|
| 生成的 OpenAPI | 一样 | 一样 |
| `inspect.signature(...).default` | `Query(20)` ← **不是 20** | `20` |
| **直接调用函数**（单元测试就这么干） | **`TypeError: unsupported operand type(s) for *: "Query" and "int"`** | ✅ 正常返回 |
| 类型检查器看到的 | **一个谎**（`int` 的默认值是个 `Query` 对象） | 真的 `int` |

⭐ **根因**：老写法把**"默认值"这个位置征用**了 —— 那本该放真正的默认值。
所以它只在 FastAPI 驱动时正常；**自己直接 `f()` 调用就崩**。

### ⭐ 更本质的理由：签名里的「位置」不够用（2026-10-15 实测）

一个参数在签名里**只有两个位置**，而且 Python 自己两个都要用：

```python
def f(limit: int = 5):
#           ↑      ↑
#        类型位   默认值位（这才是【真正的默认值】）
```

FastAPI 想加的信息（"至少 1"、"最多 100"、"文档写这句话"）**没地方放** →
于是老办法去**征用默认值位**（`limit: int = Query(20, ge=1)`）。
`Annotated` 的解法是**给类型位扩容**：

| 实测 | 结果 | 含义 |
|---|---|---|
| `Annotated[int, "a", "b"].__origin__` | `int` | **真类型还在** |
| `Annotated[int, "a", "b"].__metadata__` | `("a", "b")` | **其他东西全在这**（可以有很多个） |
| 运行时值受影响吗 | ❌ 不受（`h(7)` 里 value=7、type=int） | 值还是普通 int |
| 元数据存在哪 | **函数上**（`h.__annotations__`） | **不在值上** |

⭐ **回答"挂个东西进去干嘛"**：那个东西**不是给 Python 用的**，是给**会去读注解的工具**用的；
它在运行时**对值没有任何影响**。

### 为什么必须「打包」：一个位置要同时服务多个工具

实测：造一个**只有"我的工具"认识**的 `MyTag`，塞进同一个 `Annotated` ——

```python
limit: Annotated[int, Query(ge=1, description="for swagger"), MyTag("for-my-tool")] = 5
```

| 工具 | 读到 | 忽略 |
|---|---|---|
| 我的工具 | `MyTag("for-my-tool")` ✅ | `Query` |
| FastAPI | `Query(ge=1)` → OpenAPI 里 `minimum: 1` ✅ | `MyTag` |

行为验证：`GET /x?limit=0` → **422**（`Query(ge=1)` 真在管事）；`GET /x?limit=3` → `{"limit": 3}`。

⭐ **一个注解位、两个工具、零冲突** —— 这就是 PEP 593 设计 `Annotated` 的**全部目的**，
也是 FastAPI 从老写法迁移到它的原因：它是**标准**，所以"多方共用同一个位置"合法且稳定。

### ⚠️ 容易误会：Python **不检查**类型位

实测（故意把**普通字符串**放进类型位）：

```python
ns = {"settings": "a plain STRING"}
exec("def g(cfg: settings): ...", ns)
ns["g"].__annotations__["cfg"]   # -> "a plain STRING"，没有任何报错
```

Python 对注解**只做两件事：求值、存起来**，**从不检查**它是不是类型。

由此解释两件事：

1. 为什么 `Annotated[settings, ...]`（实例放进类型位）**运行时"碰巧能跑通"** —— Python 不管；
2. 为什么**只有 mypy 拦得住**（`valid-as-a-type`）—— 所以三条质量门一个都不能少。

### `required` 由谁决定（实测 5 种）

| 签名 | required | 不带 `x` 请求 |
|---|---|---|
| `x: Annotated[str \| None, Query(description="d")]` | **True** | **422** |
| `x: Annotated[str \| None, Query(description="d")] = None` | False | 200 |
| `x: Annotated[str \| None, Query(...)]`（无签名默认） | **True** | **422** |
| `x: Annotated[str \| None, Query(...)] = None` | False | 200 |
| `x: Annotated[str, Query(min_length=2)]`（无默认） | **True** | **422** |

⚠️ **本项目踩过的坑**：`prefix: Annotated[str \| None, Query(...)]` 少写 `= None` → 必填 → 422。
**`str \| None` 只说"能装 None"，不等于"可以不传"。**

**另两条实测**：

1. **`Query()` 不负责"决定它是查询参数"** —— `async def plain(n: int)` 什么都不加，OpenAPI 里也是 `in: query`。`Query()` 的作用是**加约束和文档**。
2. **`Annotated` 里 FastAPI 不认识的元数据被静默忽略** —— `Annotated[int, "just-a-note"]` 仍是正常 int 查询参数，不报错。

### `Query` 的参数速查：29 个，分四组（2026-10-15 实测签名）

**一句话**：`Query` 是一张**配置单** —— 你用关键字参数在上面勾选"这个查询参数要被怎么对待"，
FastAPI 读它去**约束**和**写文档**。它**不负责取值**（取值是框架干的），
**也不负责决定"这是查询参数"**（`async def plain(n: int)` 什么都不加也是查询参数）。

实测 `inspect.signature(fastapi.Query)`：**共 29 个参数，全部「仅关键字」**（必须写 `名字=`）。

| 分组 | 参数 | 作用 |
|---|---|---|
| **默认值** | `default` | 默认值（**通常不用**，直接写 `= 20` 更清楚） |
| | `default_factory` | 默认值由函数生成（可变默认值场景） |
| **改名** | `alias` | **URL 里的名字**与函数参数名不同时用（见下实测） |
| | `validation_alias` / `serialization_alias` | 更细的别名控制（本项目用不上） |
| **文档** | `title` / `description` | 参数标题与说明，进 `/docs` |
| | `examples` / `openapi_examples` | 文档里的示例值 |
| | `deprecated=True` | 标记弃用（`/docs` 里划掉，但**仍能用**） |
| | `include_in_schema=False` | **不进 `/docs`**，但**仍然能用**（⚠️ 不是安全机制） |
| **数字** | `gt` / `ge` / `lt` / `le` | 大于 / 大于等于 / 小于 / 小于等于 |
| | `multiple_of` | 必须是几的倍数 |
| | `max_digits` / `decimal_places` | 小数总位数 / 小数位数 |
| **字符串** | `min_length` / `max_length` | 长度上下限（**按字符数**，不是显示宽度） |
| | `pattern` | **正则**匹配（如 `^[a-z]+$` = 全是小写字母） |
| **少用/已弃用** | `strict` / `allow_inf_nan` / `regex` / `discriminator` | 特殊场景；`regex` 已被 `pattern` 取代 |

**实测：约束真的在拦**

| 路由写法 | 请求 | 结果 |
|---|---|---|
| `Query(min_length=2, max_length=5, pattern="^[a-z]+$")` | `?q=abc` | 200 |
| 同上 | `?q=a` | **422**（太短） |
| 同上 | `?q=ABC` | **422**（`pattern` 拦住大写） |
| `Query(gt=0, lt=10, multiple_of=2)` | `?n=6` | 200 |
| 同上 | `?n=7` | **422**（不是 2 的倍数） |

**实测：三个容易想不到的**

1. **`alias="userId"`** → OpenAPI 里参数名是 `userId`；`?userId=x` ✅ 有效，`?user_id=x` ⛔ **函数里的名字不认**。
   用途：**线上驼峰 / 代码里下划线**，前后端各用各自习惯的命名。
2. **`deprecated=True`** → OpenAPI 里出现 `"deprecated": true`，`/docs` 划掉但**还能调** ——
   这是"通知调用方迁移、但先不砸掉他们"的标准做法。
3. **`include_in_schema=False`** → 实测 `/d` 的 OpenAPI 里**没有** `secret`，但 `?secret=2` 时服务端**收到了**。
   ⚠️ **它只是"不在文档里显示"，不是权限控制** —— 真要保密必须做鉴权。

### ⚠️ 别把「对象」直接传进接口（2026-10-15 实测）⭐⭐

**问题**：既然 `settings` 已经能 import，为什么不能写成参数 `config: Settings = settings`？
实测**两种"直接传"都会出事**：

| 写法 | 实测结果 | 结论 |
|---|---|---|
| `config: Settings = settings` | `Settings` 是 pydantic 模型 → FastAPI 按三段判定规则当成**请求体**：`requestBody present? True`。**客户端能发 JSON body 顶掉配置**（实测返回 `ATTACKER-CHOSEN`） | ⛔ **配置注入**，绝不能用 |
| `Annotated[settings, Depends(f)]`（实例放类型槽） | **运行时碰巧能跑通**（200），但 mypy 报 2 个错：`valid-type`（变量不能当类型）+ 连锁的 `attr-defined` | ⛔ 只有 mypy 拦得住 → **不许写** |

⭐ **正确的只有一种**：`config: Annotated[Settings, Depends(get_settings)]` ——
类型槽放**类**，值由**依赖**提供。

**`Settings`（类）vs `settings`（实例）怎么选**：

| 位置 | 用哪个 | 为什么 |
|---|---|---|
| 注解槽（`-> Settings`、`Annotated[Settings, ...]`） | **`Settings`** | 类型槽必须放**类型**，放实例 mypy 报 `valid-type` |
| 函数体（`return settings`、`settings.llm_model`） | **`settings`** | 要的是**值** |

**顺带记住两条**：

- `settings is settings` → `True`（模块级单例）；`settings is Settings()` → `False`（每次都是新对象，会重读 `.env`）。
- "把对象传进函数"**不等于**依赖注入。判定标准：**能否在不改这个函数的前提下把对象换掉？**
  直接 import 只能靠 monkeypatch（键是**字符串路径**，搬文件就失效）；`Depends` 用 `dependency_overrides`（键是**函数对象**，重构不受影响）。
  更关键：`yield` 依赖（HTTP 客户端的创建/关闭）**没有 DI 做不到**。

### `TestClient`：FastAPI 自带的「假客户端」（2026-10-15 首次使用）

**从哪来**：`from fastapi.testclient import TestClient`。
⚠️ 看 `fastapi/testclient.py` 的**全部内容**只有一行：`from starlette.testclient import TestClient as TestClient`
—— 它只是 Starlette 的转发。

**它是什么**（实测继承链）：

```text
starlette.testclient.TestClient -> httpx.Client -> httpx._client.BaseClient -> object
```

⭐ **`TestClient` 是 `httpx.Client` 的子类**（`isinstance(..., httpx.Client)` 实测 `True`）
—— 所以它的用法和 httpx 一模一样，也是上面那条 `httpx2` 警告的根源。

**它省掉了什么**：

| | 起 uvicorn + 发请求 | `TestClient` |
|---|---|---|
| 端口 | 要（8000） | **不要** |
| 真实网络 | 要 | **不要**（请求在本进程内按 ASGI 直接交给 app） |
| 速度 | 慢 | **快**（函数调用级） |
| 适合 | 手工验证、演示 | **反复跑、写测试** |

**常用写法**：

```python
client = TestClient(app)                          # 包一层
resp = client.post("/v1/chat", json={...})        # 用法同 httpx
resp.status_code                                  # 属性，不加括号
resp.json()                                       # 方法，要加括号
TestClient(app, raise_server_exceptions=False)    # 让路由异常变成 500，而不是抛给调用方
```

⭐ `raise_server_exceptions=False` 的用处：**测"异常时清理有没有做"**这类场景 ——
默认行为下异常会直接抛到你脸上，你就拿不到响应对象了。

⚠️ **`TestClient(app)` 不用 `with` 时 lifespan 不执行**（2026-10-18 实测）：`app.state` 里不会有
`lifespan` 挂上去的资源 → 路由里 `request.app.state.xxx` 直接 `AttributeError` → 500。
要用 `with TestClient(app) as c:` 才会跑 startup / shutdown。
副作用：先 `with` 退出后再创建的新 client 会拿到**已关闭**的旧对象（`is_closed=True`），更隐蔽。

### `status`：状态码常量模块（2026-10-17 首次，2026-10-21 补全实测细节）

**一句话**：`status` **既不是类，也不是枚举** —— 它是一个**普通 Python 模块**，里面装着一堆
`整数常量`。

#### ① 它到底是什么（实测）

```text
type(status)        = <class 'module'>
status.__name__     = starlette.status
status.__file__     = .venv/Lib/site-packages/starlette/status.py
status is starlette.status → True
```

**从哪来**：`fastapi/__init__.py:5` 就只有一句

```python
from starlette import status as status
```

所以三种导入拿到的是**同一个对象**：

| 写法 | 拿到的 `__name__` | 同一个对象？ |
|---|---|---|
| `from fastapi import status` | `starlette.status` | ✅ |
| `import starlette.status` | `starlette.status` | ✅ |
| `from starlette import status` | `starlette.status` | ✅ |

⚠️ **没有 `fastapi/status.py` 这个文件**（实测 `Test-Path` → `False`），
所以 `from fastapi.status import HTTP_502_BAD_GATEWAY` → `ModuleNotFoundError`。

#### ② 里面装了什么（实测清点）

```text
大写常量共 82 个 = 67 个 HTTP 码（100 ~ 511）+ 15 个 WebSocket 关闭码（WS_1000 ~ WS_1015）
所有常量类型：全部是 <class 'int'>（纯 int，不是 IntEnum）
```

| 前缀 | 数量 | 取值范围 | 用途 |
|---|---|---|---|
| `HTTP_` | **67** | 100 ~ 511 | HTTP 状态码 → 给 `status_code=` 用 |
| **`WS_`** | **15** | 1000 ~ 1015 | ⚠️ **WebSocket 关闭码**，与 HTTP 无关（`WS_1001_GOING_AWAY` 等） |

📎 项目实际用到的 6 处（`errors.py`）：`HTTP_400_BAD_REQUEST` /
`HTTP_500_INTERNAL_SERVER_ERROR` / `HTTP_502_BAD_GATEWAY` ×3 / 默认兜底 400。

#### ③ 类型是**纯 `int`**，这带来两个后果

```text
type(status.HTTP_502_BAD_GATEWAY)  = <class 'int'>
status.HTTP_502_BAD_GATEWAY == 502 → True
status.HTTP_502_BAD_GATEWAY + 1    → 503        ← 能直接参与运算
print(status.HTTP_502_BAD_GATEWAY) → 502        ← ⚠️ 打印【只有数字】，看不出是哪条
```

| 后果 | 说明 |
|---|---|
| ✅ 好处 | 能直接塞进任何要 `int` 的地方（`JSONResponse(status_code=...)`、`dict[str, int]` 码表、`assert code == 502`） |
| ⚠️ 代价 1 | **日志/调试时只看到 `502`**，看不到 `BAD_GATEWAY`。想知道是哪条只能回头查代码 |
| ⚠️ 代价 2 | **`mypy` 只看到 `int`**，所以「码表里写了 `HTTP_404_NOT_FOUND` 但语义该用 502」这种错它抓不到 |

#### ④ 和标准库 `http.HTTPStatus` 的差别（实测对比）

| | `starlette.status.HTTP_502_BAD_GATEWAY` | `http.HTTPStatus.BAD_GATEWAY` |
|---|---|---|
| 类型 | **`int`** | **`IntEnum`**（`<enum 'HTTPStatus'>`） |
| `repr()` | `502` | `<HTTPStatus.BAD_GATEWAY: 502>` |
| 自带措辞 | ❌ 没有 | ✅ `.phrase` → `'Bad Gateway'` |
| 自带判断 | ❌ 没有 | ✅ `.is_success` → `False` |
| 相等比较 | `== 502` ✅ | `== 502` ✅（IntEnum） |
| `f"{x}"` | `502` | `502`（Python 3.11+ 的 IntEnum `__str__` 返回数字） |

⭐ 为什么 FastAPI 生态用前者：**值就是 int，零转换成本**。
需要 `.phrase` 那种能力时再 `import http`（两者可以互换使用，因为都等于 502）。

#### ⑤ 名字本身有三代，别用已废弃的（📎 实测 DeprecationWarning）

| 码 | 现行名 | 已废弃的旧名（用了会告警） |
|---|---|---|
| 413 | `HTTP_413_CONTENT_TOO_LARGE` | `HTTP_413_REQUEST_ENTITY_TOO_LARGE` |
| 414 | `HTTP_414_URI_TOO_LONG` | `HTTP_414_REQUEST_URI_TOO_LONG` |
| 416 | `HTTP_416_RANGE_NOT_SATISFIABLE` | `HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE` |
| 422 | `HTTP_422_UNPROCESSABLE_CONTENT` | `HTTP_422_UNPROCESSABLE_ENTITY` |

📎 实测访问旧名会打 `StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated.
Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.` —— 但**值仍然返回 422**，所以不会崩，
只是告警。⚠️ 本项目**没有**用旧名（实测 0 处），保持这个习惯。

#### ⑥ 三个实测坑

| # | 坑 | 实测结果 |
|---|---|---|
| 1 | 以为有 `status.HTTPStatus` | ❌ `hasattr(status, "HTTPStatus")` → `False`；写 `status.HTTPStatus.NOT_FOUND` → **`AttributeError`**（`starlette/status.py:207` 的 `__getattr__` 直接抛） |
| 2 | 把 `WS_` 码当 HTTP 码用 | ❌ `WS_1001_GOING_AWAY` 的值是 **1001**，传给 `status_code=` 会生成非法 HTTP 状态码 |
| 3 | `from fastapi.status import ...` | ❌ `ModuleNotFoundError`（没有这个子模块） |

**为什么用常量而不是直接写 `404`**：① 名字自解释 ② 常量名拼错 → `AttributeError` 当场炸；
数字写错（`440`）**什么都不会发生** ③ 不用背编号 ④ 团队写法统一。
⚠️ 但注意：**它防不住"选错码"**（`404` 和 `502` 都合法，选错只有语义层面的错）。

### `HTTPException`：可预期的错误（2026-10-17 实测，Step 6）

```python
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,   # 必填
    detail=f"模型不存在: {model_name}",       # 发给客户端的内容
    # headers=...,                           # 可选，如 401 的 WWW-Authenticate
)
```

| 事实 | 实测结果 |
|---|---|
| 继承链 | `fastapi.exceptions.HTTPException` → `starlette.exceptions.HTTPException` → **`builtins.Exception`** |
| 所以 | 它是**普通异常**（`isinstance(e, Exception)` 为 `True`，`except Exception` 抓得到）—— 对照阶段 0 的 `SystemExit`，那个不是 `Exception` |
| 构造签名 | `(status_code, detail=None, headers=None)` |
| 属性 | `e.status_code` / `e.detail`；`str(e)` → `'404: 模型不存在: x'`（写日志时就是这个样子） |
| 谁会翻译它 | **不是你**。`fastapi/exception_handlers.py:11` 的 `http_exception_handler`，第 15 行 `JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})` |
| 只能表示 4xx 吗 | ❌ 不是。502 / 503 同样用它抛（Step 6.2 会用 `502` 表示上游故障） |

**⚠️ 两个实测反例（都是"看着对、结果错"的写法）**：

| 写法 | 实测结果 | 根因 |
|---|---|---|
| 把路径参数写成 `Literal["deepseek-flash", "deepseek-v4-pro"]` 代替 `if not in` | `/lit/nope` → **422**，body 里还**列出全部合法值**：`msg: "Input should be 'deepseek-flash' or 'deepseek-v4-pro'"` | ① 状态码语义错（422 = 你格式不对，实际是资源不存在）② **报错信息泄露完整允许清单** ③ 清单要跟着代码改，形成第二份真相 |
| `return HTTPException(...)` | 有返回注解 `-> dict[str, str]` → **500**（`ResponseValidationError: dict_type ... input: HTTPException(...)`）；**没写返回注解** → **200 + `{"status_code":404,"detail":"x","headers":null}`** | 异常对象**只有被 `raise` 才会走异常通道**；当返回值时它只是一个普通对象，会被当数据序列化 —— 最坏情况是**谎报 200**（正是"工具全绿但语义全错"的又一例） |

**`detail` 的边界**：它是**给客户端看的**，会原样进 JSON。所以：不放堆栈 / 路径 / SQL / 密钥片段；不要把上游返回的原始错误体整段转出去（可能带 key）；回显用户输入时注意它会被原样反射。

### `curl.exe`：命令行看原始响应（2026-10-17 实测，Step 6）

**是什么**：Windows 10/11 **自带**的 HTTP 客户端（实测 `C:\Windows\system32\curl.exe`，`curl 8.21.0`），只做一件事 —— 发请求、把**原始报文**打出来。

| 参数 | 作用 |
|---|---|
| `-i` | **include headers**：连响应头一起打，第一行就是**状态行** `HTTP/1.1 404 Not Found`。不带它只有 body，而 body 看不出状态码 |
| `-s` | silent：关掉下载进度条（就是那串 `% Total % Received % Xferd`，它走 stderr） |
| `-X POST` | 指定方法；**不写默认 GET** |
| `-H "Content-Type: application/json"` | 加请求头 |
| `-d '{"k":"v"}'` | 带请求体（自动变成 POST） |

⚠️ **在 PowerShell 5.1 里必须写 `curl.exe`**：`Get-Command curl` 实测 `CommandType: Alias` ——
`curl` 是 `Invoke-WebRequest` 的**内置别名**，别名优先于同名 exe，而 `Invoke-WebRequest` **没有 `-i` 参数**。

实测输出（本项目 6.1）：

```text
HTTP/1.1 404 Not Found          ← 状态行
date: Sat, 17 Oct 2026 12:43:24 GMT
server: uvicorn
content-length: 55
content-type: application/json
                                 ← 空行 = 头/体分界（RFC 规定）
{"detail":"模型不存在: this-model-does-not-exist"}
```

### `curl.exe` 完整参数速查（2026-10-19 补，含流式测量）

#### ① 看输出：四个选项，作用完全不同（实测）

| 选项 | 输出 | 实测现象 |
|---|---|---|
| `-i` | 响应头 + body，混在一起 | `HTTP/1.1 200 OK` + 空行 + `{"status":"ok"}` |
| `-I` | **发 HEAD 请求**（换方法！） | 本项目 `/health` 返回 **405**（`allow: GET`）——`-I` 不是"只看头" |
| `-D -` | 头输出到 stdout，body 可另存 | 配 `-o NUL` 最干净：`curl -s -D - -o NUL <url>` |
| `-v` | 完整调试（含**发出去的请求头**），走 **stderr** | 能看到 `> GET /health HTTP/1.1` / `> Host:` / `> User-Agent:` |

#### ② body 去哪

| 选项 | 作用 |
|---|---|
| `-o 文件名` | 写进文件 |
| `-o NUL` | 丢弃（Windows 黑洞；Linux 是 `/dev/null`） |

#### ③ 发请求

| 选项 | 作用 | 备注 |
|---|---|---|
| `-X POST` | 指定方法 | 不写默认 GET |
| `-H "K: V"` | 加请求头（可多次） | CORS 验证用它：`-H "Origin: http://localhost:5173"` |
| `-d` / `--data` | 请求体（自动变 POST） | ⚠️ PowerShell 内联 JSON 会被转义搞坏，见下方易错点 |
| `--data-binary "@文件"` | 从文件读，**原样发送** | 中文 / 含换行时必用 |
| `-N` / `--no-buffer` | 关掉 curl 自己的输出缓冲 | ⭐ **看流式必须加** |
| `-L` | 跟随重定向 | 默认**不跟** |

#### ④ `-w`：把结果变成数字（判"是否流式"的关键）

| 变量 | 含义 | 本项目流式接口实测 |
|---|---|---|
| `%{http_code}` | 状态码 | `200` |
| `%{time_namelookup}` | DNS 解析完成（累计，秒） | `0.000052` |
| `%{time_connect}` | TCP 握手完成 | `0.000567` |
| `%{time_appconnect}` | TLS 握手完成 | `0.000000`（http） |
| `%{time_starttransfer}` | **收到第一个字节**（TTFB） | `0.022239` |
| `%{time_total}` | **连接关闭** | `1.838900` |
| `%{size_download}` | 下载字节数 | `230` |
| `%{content_type}` | 响应 Content-Type | `text/event-stream; charset=utf-8` |

PowerShell 写法（换行用**反引号 n**）：

```powershell
curl.exe -s -o NUL -w "ttfb=%{time_starttransfer} total=%{time_total}`n" http://127.0.0.1:8000/v1/chat/stream
```

⭐ **判据**：`starttransfer ≪ total` = 真流式。同项目对照：`/health` 是 `0.013/0.013`（1:1），
`/v1/chat/stream` 是 `0.022/1.839`（**1:83**）。

#### ⑤ 其他常用

| 选项 | 作用 |
|---|---|
| `-s` | silent，关进度条 |
| `-k` | 忽略 TLS 证书错误（仅自签名测试） |
| `--max-time 10` | 总超时；⚠️ 测流式要设大，否则长回答被掐断 |
| `-b "k=v"` / `-u user:pass` | Cookie / Basic 认证 |

⚠️ **`-I`（HEAD）会导致 405**：FastAPI 的 `@app.get(...)` 只注册 GET。
有些监控探活用 HEAD 打 `/health` 会失败 —— 见路线图待办 #9。

### 易错点

- ⚠️ **校验发生在你的函数体之前**（实测：1 个合法请求 → 函数执行 1 次；再发 3 个非法请求 → **仍只执行 1 次**）。所以"校验失败"时你函数里的 `print` 不会响 —— 别以为代码没跑到就是没生效。反面收益：契约里写了 `min_length=1`，函数体里 `messages[-1]` 就**不需要越界防御**。
- ⚠️ **一个路径可以只有 1 个请求体参数**：函数签名里的变量名（如 `request`）**随便起**，起决定作用的是**类型**。判定规则见笔记 Step 3：名字在路径 `{}` 里 → 路径参数；类型是 pydantic 模型 → 请求体；其他 → 查询参数。
- ⚠️ **`422` 与 `HTTPValidationError` 是自动加的**，不是你写的 —— 只要路由有请求体就会出现。
- ⚠️ ⭐ **`422` 有很多种，必须读 `detail[0].type` 和 `loc`**（2026-10-17 实测）：`too_short`（空列表）/ `missing`（缺字段）/ `list_type` / `literal_error`（枚举拼错）/ **`json_invalid`（请求体根本不是合法 JSON，解析阶段就拒了）**。状态码只说"被拦下了"，`type`+`loc` 才说"在哪一关、因为什么"。
- ⚠️ **PowerShell 里不要内联拼 JSON 发给 `curl.exe`**（2026-10-17 实测）：`--data "{\"messages\":[]}"` 会让服务器收到 `{\"messages\":[]}`（反斜杠被当字面量）→ 422 `json_invalid`，**看起来"验过了"其实没验到**。改用 `[IO.File]::WriteAllText("$env:TEMP\body.json", '...', UTF8无BOM)` + `--data "@$env:TEMP\body.json"`。
- ⚠️ **形状归 pydantic（422），语义归路由（400）**：如"最后一条消息必须是 `user`"属于业务规则，写进 `model_validator` 会把 400 变成 422，且让 `schemas.py` 变成业务规则仓库。
- ⚠️ **`x or default` 按"真值"判断，不是按"是否 None"**（实测）：`""`/`0`/`[]`/`{}`/`None` 全算假，所以空字符串也会被兜掉。要"只在明确没填时兜底"须写 `x if x is not None else default`。
- ⚠️ **FastAPI 自己不监听端口**。它只提供"应用"，必须由 ASGI 服务器（uvicorn）来跑 —— 两个包、两个角色，见 §8。
- ⚠️ `uvicorn app.api.app:app` 里 **`app` 出现两次、含义不同**：前面是包名/模块名，冒号后是**变量名**。路径上少任何一个 `__init__.py` 都会报 `Could not import module`。
- ⚠️ 本项目的 `src/app/main.py` 是**阶段 0 的 CLI**，不在这条 import 链上 —— **别往它里面加 HTTP 逻辑**（混在一起会让"这文件干嘛的"变模糊）。
- ⚠️ **被装饰器登记的函数本身没被改变**（实测 `type(app.api.app.chat)` 仍是普通 `function`）→ 所以**可以直接 `await chat(ChatRequest(...))` 做单元测试，不用起服务**。
- ℹ️ **import 图会随代码增长**（2026-10-15 订正）：1.1 时 `app.api.app` 只 import 了 `fastapi`，`config` / `schemas` 都没加载；1.3 加了路由后实测 **`app.config` 与 `app.schemas` 都已进入 import 图**。所以"改 `config.py` 没生效"这类判断**必须重新实测，不能沿用旧结论**。

---

## 8. uvicorn（ASGI 服务器）

**解决什么问题**：**监听端口**、把 TCP 字节按 HTTP 协议解析、再按 **ASGI 协议**调用你的 `app` 对象，最后把响应写回去。FastAPI 提供"应用"，它提供"服务器"。

**装法**：`uv add "uvicorn[standard]"`。**实测版本 0.54.0**。

`[standard]` 是 **extras**（额外依赖包），带来：`watchfiles`（支撑 `--reload`）、`httptools`（更快的 HTTP 解析）、`websockets`（WebSocket 支持）、`click`、`pyyaml` 等。

### 常用命令

| 命令 | 干什么 |
|---|---|
| `uv run uvicorn app.api.app:app --reload` | **开发模式**：改文件自动重启 |
| `uv run uvicorn app.api.app:app --port 8001` | 换端口（默认 8000） |
| `uv run uvicorn app.api.app:app --host 0.0.0.0` | 允许外部访问（默认只绑本机 `127.0.0.1`） |
| `uv run uvicorn app.api.app:app --workers 4` | 生产：多进程（⚠️ 与 `--reload` 互斥） |
| `uv run uvicorn app.api.app:app --log-level warning` | 降噪 |

**`模块路径:变量名` 的读法**：`app.api.app` = 包 `app` → 子包 `api` → 模块 `app.py`；冒号后的 `app` = 那个模块里的**变量名**。

### 实测行为（不知道这些会误判）

| 现象 | 实测结果 |
|---|---|
| 启动后有几个进程 | **2 个**（`--reload` 时）：`reloader`（盯文件变化的"监工"）+ `server`（真正监听端口的"干活的"） |
| `--reload` 盯哪些目录 | **整个工作目录**（日志原话：`Will watch for changes in these directories: [...]`）—— 连改 `README.md` 也会触发重启 |
| 按 Ctrl+C 之后 | 优雅关闭共 5 行：`Shutting down` → `Waiting for application shutdown` → `Application shutdown complete` → `Finished server process [...]` → `Stopping reloader process [...]` |
| 常驻还是退出 | **常驻**（占住终端，不会自己结束）—— 这是它与 `python -m app.main` 最直观的区别 |

⭐ **watch ≠ import**：`--reload` 盯的是**整个目录**，但每次真正执行的只有 **import 链上的模块**。实测：启动后只加载了 `app` / `app.api` / `app.api.app` 三个自有模块，`config.py` / `schemas.py` / `main.py` **均未加载**（另外还加载了 374 个模块 / 85 个顶层包，来自标准库与第三方）。

### 实测：路径写错时的两种报错原文

| 情况 | 报错原文 | 含义 |
|---|---|---|
| 模块路径不存在 | `ERROR: Error loading ASGI app. Could not import module "app.api.nope".` | import 链断了 —— 路径拼错 / 少 `__init__.py` / **当前工作目录不在项目根** |
| 变量名不存在 | `ERROR: Error loading ASGI app. Attribute "nope" not found in module "app.api.app".` | 模块执行成功了，但里面没有那个名字 |

两种情况**退出码都是 3**（非 0 = 失败，脚本/CI 靠它判断）。

### 易错点

- ⚠️ **`--reload` 只用于开发**：多一个进程盯文件，且生产环境行为不可预测。
- ⚠️ 报错信息走 **stderr**。在 PowerShell 里会被标成红字 `NativeCommandError` —— 那是 PowerShell 在说"这个子进程往 stderr 写了东西"，**不是额外的错误**，看 `ERROR:` 后面那句才是原因。
- ⚠️ 端口被占用会报 `error while attempting to bind on address ... only one usage of each socket address`，换一个 `--port` 即可。

---

## 9. logging（Python 标准库，不是项目依赖）

> ⭐ **本节只做速查卡**。原理（四道闸 / Logger 树与 `propagate` / 级别语义 / Handler 与轮转 /
> `dictConfig` 参数 / 14 条注意事项 / 踩坑表）全部在独立专题 **[logging.md](logging.md)**。

**解决什么问题**：把"运行时发生了什么"写成**带级别的事件流**。代替 `print` 的理由：能分级、
能带模块名与时间、能被外部系统收集、级别不够时整条丢弃（零成本）。

**怎么进来的**：标准库，**不用 `uv add`**。

### 三行速查

| 想干什么 | 写法 |
|---|---|
| 取 logger | `logger = logging.getLogger(__name__)`（名字 = 模块路径） |
| 打日志 | `logger.info("%s -> %s", path, status)` ⚠️ **不用 f-string**（级别不够时白拼） |
| 打异常 | `logger.exception("...")` ⚠️ **只能在 `except` 块里**（它读 `sys.exc_info()`） |

### 不配任何东西时（默认行为）

| 调用 | 会不会出现 | 说明 |
|---|---|---|
| `logger.debug(...)` / `.info(...)` | ❌ 静默丢弃 | root 级别是 WARNING，且**没有 handler** |
| `.warning(...)` / `.error(...)` / `.exception(...)` | ✅ 出现在 **stderr** | 走 `logging.lastResort` 兜底，**无任何格式**（没有时间戳/级别/模块名） |

⭐ 这就是本项目早期"终端里只有 `未处理异常 request_id=…` 这一句、没有时间和级别"的原因。
→ 正式配置见 [logging.md](logging.md) §7~§8，本项目落地在 `src/app/logging_setup.py`。

### 独有备忘

| 项 | 结论 |
|---|---|
| `logger.exception(...)` | ⚠️ **只能用在 `except` 块里**（它读 `sys.exc_info()`），块外调用不会附带 traceback |
| 兜底处理器里别写可能抛异常的代码 | 📎 实测：500 处理器自身抛异常 → 客户端拿到**空 body、无 content-type** 的 500（uvicorn 原始错误页） |
| 日志里别打完整对象 | `logger.info(payload)` 可能把密钥写进日志（规范 §10.5） |

📎 **「一次 500 两段 traceback」「多出一行 access log」「PowerShell 红字」** 三个容易误判的现象 →
[logging.md](logging.md) §11 踩坑表。
📎 **12-Factor 第 11 条（只写 stdout）** → [logging.md](logging.md) §5.2；
**`request_id` vs `trace_id`** → [logging.md](logging.md) §9.0。

---

## 10. SQLAlchemy 2.1 异步 ORM 与 aiosqlite

**一句话定位**：SQLAlchemy 把 Python 类映射成数据库表，并负责组织查询与事务；`aiosqlite` 是 SQLite 的异步驱动。二者是**两个独立依赖**。

### 安装

| 命令 | 作用 |
|---|---|
| `uv add "sqlalchemy[asyncio]>=2.1,<2.2" aiosqlite` | 安装 SQLAlchemy 2.1 的异步 extra（含 `greenlet`）和 SQLite 异步驱动；更新 `pyproject.toml`、`uv.lock`、`.venv` |
| `uv tree` | 检查依赖树，确认 `sqlalchemy`、`greenlet`、`aiosqlite` 均已安装 |
| `uv run python -c "import sqlalchemy, sqlalchemy.ext.asyncio, aiosqlite; print(sqlalchemy.__version__)"` | 实际导入异步模块并打印 SQLAlchemy 版本；本机输出 `2.1.6` |

### 常用 API

| 写法 | 作用 |
|---|---|
| `class Base(DeclarativeBase): ...` | 建立 ORM 模型共用的基类；模型的表结构会汇集在 `Base.metadata` |
| `Mapped[int]` / `mapped_column(...)` | 用类型标注和列配置声明表字段 |
| `create_async_engine(url)` | 创建异步数据库引擎；`sqlite+aiosqlite:///...` 使用 SQLite 异步驱动 |
| `async_sessionmaker(engine, expire_on_commit=False)` | 制作可反复创建 `AsyncSession` 的工厂，并避免提交后 ORM 对象属性过期 |
| `await connection.run_sync(Base.metadata.create_all)` | 在异步连接上下文用 greenlet 调用同步风格 SQLAlchemy API，并把数据库 IO 接到异步驱动；**不是线程池**，不要在回调里做阻塞 IO 或长时间 CPU 计算 |
| `await engine.dispose()` | 在异步上下文中关闭连接池资源 |

### 实测行为与易错点

| 现象 | 结论 |
|---|---|
| 裸装 `sqlalchemy>=2.1,<2.2` 后导入 `sqlalchemy.ext.asyncio` | 📎 2026-10-23 隔离环境实测：`ModuleNotFoundError: No module named 'greenlet'`，随后抛出 SQLAlchemy 提示安装 `[asyncio]` extra 的 `ImportError` |
| 安装 `sqlalchemy[asyncio]>=2.1,<2.2` 与 `aiosqlite` | 📎 本项目解析到 SQLAlchemy 2.1.6、greenlet 3.5.6、aiosqlite 0.22.1；异步导入成功，三道质量门全绿 |
| SQLAlchemy 2.0 与 2.1 的 greenlet 安装行为 | 不要混为一谈：本机裸装 2.0.55 可导入 async 模块；2.1 起 greenlet 不再默认安装，需声明 `[asyncio]` extra |
| `aiosqlite` 属于哪个依赖项 | 它是 SQLite 驱动，需独立安装；不是 SQLAlchemy 的 `[asyncio]` extra |
| `run_sync` 会不会开线程 | 不会把回调放进线程池；它在 greenlet 上下文运行，SQLAlchemy 数据库 IO 由异步驱动处理。它不是通用线程卸载工具；不要在其中做阻塞网络或长时间计算 |
| 内存 SQLite 是否持久 | `:memory:` 数据库在进程结束后消失；`StaticPool` 可让测试连接共用同一内存库，但不提供跨重启持久化。需要保留数据时使用 SQLite 文件或 PostgreSQL |

> SQLAlchemy 2.1 仍可使用 `Mapped` / `mapped_column` 等 **2.0 风格 API**。“2.0 风格”描述 API 形态，不代表依赖版本必须是 2.0.x。

---

### 关系与索引：`ForeignKey` / `relationship` / `index=True`（2026-10-26 实测，10.6a）

**一句话**：`ForeignKey` 是**数据库层**的约束（产生列），`relationship` 是 **Python 层**的导航（不产生列），`index=True` 是**额外的排序目录**。

| 写法 | 作用 | 生效层 |
|---|---|---|
| `mapped_column(ForeignKey("conversations.id"))` | 声明外键；字符串格式是 **`"表名.列名"`**（`__tablename__` 的值，**不是类名**） | 数据库（建表语句） |
| `ForeignKey(..., ondelete="CASCADE")` | 父行被删时数据库自动删子行 | 数据库（**仅原生 SQL 删时生效**） |
| `mapped_column(..., index=True)` | 额外建一条索引，名字自动是 `ix_<表>_<列>` | 数据库（多一条 `CREATE INDEX`） |
| `relationship(back_populates="xxx")` | 双向导航；字符串是**对方类里那个属性的名字** | Python（无列） |
| `relationship(cascade="all, delete-orphan")` | 删父对象时**真删**子对象 | Python（**仅 ORM 删时生效**） |
| `Mapped[list["LlmCall"]]` | 一对多（集合）；**必须加引号**（前向引用） | Python 类型注解 |
| `Mapped[int \| None]` | 列可为空；⚠️ 同时会改变 ORM 删父行时的默认行为（置 `NULL`） | 数据库 `NOT NULL` + Python 类型 |

**📎 实测：删一个有 2 条子记录的父行（五种写法）**

| 写法 | 子行剩几行 | 子行 FK |
|---|---|---|
| 不写 `cascade`（`session.delete`） | **2** | 变成 `NULL`（孤儿） |
| **`cascade="all, delete-orphan"`**（`session.delete`） | **0** ✅ | 行没了 |
| `passive_deletes=True` 单用（`session.delete`） | 2 | 变成 `NULL` ⚠️ |
| 默认 relationship + **原生 `DELETE`** | 0 | 行没了（`ondelete` 生效） |
| `passive_deletes=True` + 原生 `DELETE` | 0 | 行没了 |

⭐⭐ **判据：走 ORM 用 `cascade=`，走原生 SQL 用 `ondelete=`，两层各管一段。**

**📎 实测：`index=True` 的收益（5 万行同一查询）**

| | 单次耗时 | 查询计划 |
|---|---|---|
| 无索引 | 2985.9 µs | `SCAN`（逐行检查） |
| 有索引 | **119.6 µs（25 倍）** | `SEARCH ... USING INDEX`（按目录找） |

**📎 实测：规模增长方式**

| 行数 | 无索引 | 有索引 |
|---|---|---|
| 40 000 | 7.085 ms | 0.165 ms |
| 80 000 | **17.352 ms（≈2.4x，线性）** | **0.216 ms（≈1.3x，对数）** |

**📎 实测：索引的代价**

| 代价 | 数据 |
|---|---|
| 插入变慢 | 156.6 → **216.0 ms**（+38%，5 万行） |
| 占空间 | 3056 → **3612 KB**（+18%） |
| 可能不被使用 | `WHERE conv_id > 0` 命中大半表时数据库**主动放弃**索引 |

**📎 实测：`COVERING INDEX`（覆盖索引）**

| 查询 | 计划 | 是否回表 |
|---|---|---|
| `SELECT id FROM t WHERE conv_id=?` | `USING COVERING INDEX` | 否 |
| `SELECT pad FROM t WHERE conv_id=?` | `USING INDEX` | **是**（每行回原表取 `pad`） |

⭐ 判据：**`SELECT *` 一定要回表**；只选索引里有的列才能全靠索引。

- ⚠️ **SQLite 默认不强制外键**（`PRAGMA foreign_keys=0`），必须挂 `engine.sync_engine` 的 `"connect"` 事件执行 `PRAGMA foreign_keys=ON`。📎 实测：挂事件后池内 3 条连接全为 `1`，孤儿 `conversation_id=999` 被 `IntegrityError: FOREIGN KEY constraint failed` 拒
- ⚠️ **`PRAGMA` 是「每条连接」的开关且不持久化** —— 启动时执行一次只能打开当时那一条连接
- ⭐ 事件里拿到的连接是 `AsyncAdapt_aiosqlite_connection`（同步风格适配层），不是原生 `aiosqlite.Connection`，所以参数注解只能写 `Any`
**易错点**

- ⚠️ `ForeignKey` 里写**表名**，不是类名。📎 写错 → `NoReferencedTableError: could not find table 'c_typo'`（建表时立刻报）
- ⚠️ `Mapped[list["X"]]` 的引号**不能省** —— 📎 省略 → `NameError: name 'X' is not defined`（Python 从上往下执行）
- ⚠️ `back_populates` 写错 → 📎 `InvalidRequestError: Mapper ... has no property 'xxx'`（配置 mapper 时立刻报，报错里点名了错误属性）
- ⚠️ **三个静默坑**：`ondelete` 不写 / `index` 不写 / `cascade` 不写 —— 都**不报错**，问题在运行时（删数据、大数据量）才暴露，**三道门一个都拦不住**
- ⚠️ SQLite **默认不强制外键**（`PRAGMA foreign_keys=0`），需要 `event.listens_for(engine, "connect")` 里执行 `PRAGMA foreign_keys=ON`
- ⚠️ `create_all` **只建缺失的表，不改已有表** —— 给已有表加列必须删库重建或写迁移

### `Result` 的五个取值方法 + 「一次性游标」陷阱（2026-10-28 实测）

`await session.execute(stmt)` 返回的**不是值**，而是一个**结果集容器**（`ChunkedIteratorResult`）。
📎 实测：即使 `SELECT count(...)` 只回 1 行 1 列，它也不是 `int`。

| 方法 | 返回 | 恰好 1 行 1 列时 | 多行时 | 0 行时 |
|---|---|---|---|---|
| `.all()` | `list[Row]` | `[(3,)]` | 全部 | `[]` |
| `.first()` | `Row \| None` | `(3,)` | 只取第一行 | `None` |
| `.one()` | `Row` | `(3,)` | ⚠️ `MultipleResultsFound` | `NoResultFound` |
| `.scalar()` | 第一行第一列的值 | `3` | ⚠️ **静默取第一行** | `None` |
| **`.scalar_one()`** | 第一行第一列的值 | `3` | ⚠️ `MultipleResultsFound` | `NoResultFound` |
| `.scalar_one_or_none()` | 值或 `None` | `3` | ⚠️ `MultipleResultsFound` | `None` |
| `.scalars()` | **还是 `Result`**（只留第一列）→ 还要 `.all()`/`.one()` | — | — | — |

⭐ **选法**：

| 场景 | 用哪个 |
|---|---|
| `COUNT` / `SUM` / `MAX`（SQL 保证恰好 1 行） | **`.scalar_one()`** |
| 按主键/唯一键查一个值，可能没有 | `.scalar_one_or_none()` |
| 业务上允许多行、只要第一条 | `.first()` |
| 要全部 | `.all()` / `.scalars().all()` |

⭐⭐ **为什么 `COUNT` 要用 `scalar_one()` 而不是 `scalar()`**：它把「我假设恰好一行」**写进了代码**。
若将来有人把查询改成带 `GROUP BY`（会返回多行），`scalar_one()` **立刻抛异常**；
而 `scalar()` 会**静默返回第一组的数** —— `total` 变成一个错误的数字且不报错。

#### ⚠️⚠️ 坑：`Result` 是**一次性游标**，用过就废

📎 实测：

```text
第 1 次 .all()        -> [(3,)]
第 2 次 .all()        -> []          ← 空的，不报错
先 .all() 再 .first()  -> [(3,)] 然后 None   ← None，不报错
```

⭐⭐ **`Result` 内部是数据库游标，读到末尾就没了。** 对同一个 `Result` 调两次取值方法，
第二次拿到**空值/None** 且**不报错** —— 典型的静默失效。

⭐ 判据：**`Result` 只能消费一次；需要多次读取就先 `rows = result.all()` 存下来。**

#### ⚠️⚠️ 坑：SQLite 下 `datetime` 的时区**必然丢失**，`timezone=True` 也没用

📎 三段链路：

| 阶段 | 值 | `tzinfo` |
|---|---|---|
| 写入前（Python） | `datetime(..., tzinfo=UTC)` | `UTC` → aware |
| bind 格式化后 | `'2026-10-28 05:51:54.604445'` | **没了** |
| 读回（Python） | `datetime(2026,10,28,5,51,54,604445)` | `None` → naive |

📎 丢失点在 `sqlite.DATETIME()._storage_format`：

```text
%(year)04d-%(month)02d-%(day)02d %(hour)02d:%(minute)02d:%(second)02d.%(microsecond)06d
```

占位符只有 `year/month/day/hour/minute/second/microsecond` —— **一个时区占位符都没有**。

📎 `DateTime(timezone=True)` 在 SQLite 与 PostgreSQL 下的 DDL 对比：

```sql
-- SQLite 方言
plain    DATETIME,
with_tz  DATETIME,                  -- timezone=True 消失
-- PostgreSQL 方言
plain    TIMESTAMP WITHOUT TIME ZONE,
with_tz  TIMESTAMP WITH TIME ZONE,  -- 生效
```

⭐⭐ **SQLite 没有「带时区的时间类型」**，类型声明只是亲和性标签，值存 TEXT。
`timezone=True` 在 SQLite 下**既不改 DDL、也不改 bind 格式、也不改读回结果**。

📎 危险推论：`+08:00` 的 13:51 与 UTC 的 13:51 落盘是**同一个字符串**，读回来无法区分。

⭐ 判据：
- **SQLite 阶段**：在**出口**（pydantic schema）统一补 `tzinfo=UTC`，别指望列类型
- **换 PostgreSQL 时**：这一列才该加 `timezone=True`

## 11. 健康探针（k8s / Docker）—— 配置层，不是代码层

> ⚠️ **最容易混的一点**：健康检查涉及**两个不同的层**，它们分别住在**不同的文件**里。

| | 端点（endpoint） | 探针（probe） |
|---|---|---|
| 是什么 | 一个 **HTTP 路径** | 一条**配置**：「定期去请求某个路径」 |
| 写在哪 | **应用代码**（`@app.get("/health")`） | **YAML**（k8s `livenessProbe` / compose `healthcheck`） |
| 谁执行 | 你的应用 | **编排平台**（kubelet / Docker 引擎） |
| 应用知道探针存在吗 | ❌ **完全不知道**，只是「碰巧有人来 GET」 | — |

⭐⭐ **探针不是代码，是配置。** 两者唯一的耦合是**一个路径字符串**：

```yaml
# k8s deployment.yaml
livenessProbe:
  httpGet: { path: /health, port: 8000 }        # ← 必须与应用路由一致
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /health/ready, port: 8000 }  # ← 同上
  periodSeconds: 5
  failureThreshold: 2
```

```yaml
# docker-compose.yml（等价物）
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
  interval: 10s
  retries: 3
```

### 三种探针

| 探针 | 回答什么问题 | 失败时平台做什么 |
|---|---|---|
| **liveness** | 进程还活着吗？ | **重启容器** |
| **readiness** | 能接流量吗？ | **从负载均衡摘掉**，不重启 |
| **startup** | 启动完成了吗？ | 在它成功前，**暂停其它两种探针** |

⭐ **startup 探针解决「启动慢」问题**：启动要 60 秒的应用，liveness 的 `initialDelaySeconds` 只有 10 秒 → 启动中就被判定失败 → 无限重启。加一个 `startupProbe: failureThreshold: 12, periodSeconds: 5` 就对了。

### HTTP 探针的判定规则

⭐ **状态码 200~399 算成功**，其它（含 404、500、503）都算失败。

⚠️ 所以 **路径拼错 = 404 = 探针永远失败**，而日志里只会看到「Pod 在重启」，很难定位。

📎 实测（本项目）：

```text
GET /health          -> 200     ✅
GET /health/ready    -> 200     ✅
GET /healthz         -> 404     ← 拼错（k8s 社区常见写法，本项目没有）
GET /health/live     -> 404     ← 同上
```

### 三类探针该检查什么（最容易做错的地方）

| 检查内容 | 放哪个探针 | 为什么 |
|---|---|---|
| 进程/事件循环在转 | **liveness** | 死了才该重启 |
| **数据库**连通性 | **readiness** | 数据库挂不是重启应用能修的 |
| 下游第三方 API 可用 | ❌ **都不放** | 别人的问题不该让你被摘流量/重启 |
| 磁盘/内存快满 | liveness ⚠️ 慎用 | 重启缓解不了，应该告警 |

⭐⭐ **把「别人的依赖」放进 liveness 是最经典的事故**：数据库抖动 30 秒 → 全部实例 liveness 失败 → 全部重启 → 重启后还要连库 → 还是失败 → **雪崩**。

### 本项目的对应关系

| 端点 | 类型 | 检查 | 失败响应 |
|---|---|---|---|
| `/health` | liveness | 不检查外部依赖 | 恒为 200 |
| `/health/ready` | readiness | `SELECT 1` 探库 | **503** `DB_UNAVAILABLE` |

⚠️ **FastAPI / Starlette 一个健康端点都不自带**（只自带 `/docs`、`/redoc`、`/openapi.json`、`/docs/oauth2-redirect`）。
对比：Spring Boot 有 `Actuator` 的 `/actuator/health`、ASP.NET Core 有 `HealthChecks`。

### 常见坑

| 坑 | 后果 |
|---|---|
| 探针路径与应用路由不一致（拼错 / 改名忘同步） | 404 → **无限重启**或**永远被摘流量**，且**不报错** |
| 把探库放进 liveness | 数据库抖动 → 全实例雪崩重启 |
| `initialDelaySeconds` 小于真实启动耗时 | 启动中就被判失败 → 重启循环（该用 `startupProbe`） |
| readiness 探第三方 API | 上游抖动 → 你被摘流量 |
| 探针间隔过短（如 1s）+ 探库查询很重 | 健康检查自己变成负载来源 |

⭐ 判据：**探针是「两处文件里的一致事实」** —— 改一边必须回头改另一边；建议把路径提成环境变量（如 `HEALTH_PATH`）让 YAML 引用同一个值。

---


## 12. 时钟：`time` / `monotonic` / `perf_counter`

**解决什么问题**：写超时、算耗时、盖时间戳都需要「时间」，但**这三个时钟不能互换** —— 选错会在特定场景下静默出错。

### 📎 本机实测（Python 3.12.15 / Windows 11）

```text
time          monotonic=False  adjustable=True   GetSystemTimeAsFileTime()
monotonic     monotonic=True   adjustable=False  GetTickCount64()
perf_counter  monotonic=True   adjustable=False  QueryPerformanceCounter()
```

| 字段 | 含义 |
|---|---|
| `monotonic=False` | **可以倒退**（时钟被调整时） |
| `adjustable=True` | **会被 NTP / 手动改时间改掉** |

⭐⭐ 只有 `time.time()` 是 `adjustable=True`，另两个不会被调整。

### ⭐⭐ 判据：先问「你要回答哪个问题」

| 你要回答的问题 | 用哪个 | 代表场景 |
|---|---|---|
| 「到 30 秒了吗 / 花了多久」 | `monotonic()` / `perf_counter()` | **超时**、重试等待、耗时统计、限速令牌 |
| 「现在是什么时刻 / 什么时候过期」 | `time.time()` 或数据库 `now()` | **时间戳落库**、JWT `exp`、限流窗口、缓存 TTL |

⭐ 一句话：**「多久」用单调钟，「何时」用墙钟。**

### 🔴 两个方向相反的失效模式（都要知道）

| | 墙钟 `time.time()` | 单调钟 `time.monotonic()` |
|---|---|---|
| 系统时钟被 NTP 校正 | 🔴 **跳变** → 超时提前误触发 / 永不触发 | ✅ 完全不受影响 |
| 机器休眠 / 挂起 | ✅ 休眠时间照算 → 醒来可能已「超时」 | ⚠️ 依平台而定，**可能不计休眠** → 超时被推迟 |

📎 实测（模拟 NTP 向前校正 60 秒，做 30 秒超时）：

```text
真实过去   1s，剩余预算   30.0s  → 继续等
真实过去   2s，剩余预算   30.0s  → 继续等
真实过去   3s，剩余预算  -30.0s  → 触发超时  [时钟跳到 +60s]
```

只过去 3 秒，30 秒超时就**误触发**了。换成单调钟，同样场景剩余预算 `27.0s`，正常继续等。

⚠️ **反向校正（时钟后退）更常见也更隐蔽**：30 秒超时变成 90 秒，表现为「服务偶发卡很久」。

### ⭐⭐ 所以「为了避免休眠导致超时不触发，改用系统时钟」是错的

这是**用一个更高频、更严重的故障（时钟跳变）去换一个更低频的故障（休眠不计时）**。

- 休眠时没人等你的请求，超时晚一点触发**通常无害**（甚至是期望行为：不该因为机器睡了就立刻杀掉请求）
- 时钟跳变在任何**长期运行的服务器**上都会发生（NTP 守护进程定期对齐），一次就误杀一片请求

⭐ 如果确实需要「包含休眠的经过时间」：Linux 用 `time.clock_gettime(time.CLOCK_BOOTTIME)`；
不要退回 `time.time()`。

### 📎 本项目实际用到的两个（都正确）

| 位置 | 使用 | 判断 |
|---|---|---|
| `app.py` 请求耗时日志 | `time.perf_counter()` | ✅ 单调，测耗时正确 |
| `httpx` 的 `request_timeout` | 库内部 `anyio.fail_after()` → `loop.time()` → `time.monotonic()` | ✅ 库替我们选对了 |
| `models.py` 的 `created_at` | `datetime.now(UTC)`（墙钟） | ✅ 落库时间戳**必须**墙钟 |

📎 实测 `loop.time()` 与 `time.monotonic()` **完全相等**（diff 0），与 `perf_counter()` 差 163 秒（不同起点）：

```text
loop.time()         = 1153308.546000
time.monotonic()    = 1153308.546000   diff=0.000000000   ← 同一个时钟
time.perf_counter() = 1153471.840602   diff=163.294602200 ← 不同起点
```

### ⚠️ 未实测的部分（诚实标注）

「Windows 的 `GetTickCount64()` / Linux 的 `CLOCK_MONOTONIC` 在休眠期间到底走不走」——
**我无法在这台机器上真休眠来实测**。上面的判断来自平台机制文档，属**未实测推断**。
⭐ 如果将来真要在笔记本上跑长任务，正确做法不是换时钟，而是**在请求层加总时长上限**（见下）。

### 🔴 顺带发现：`read timeout` 不是「总时长」

📎 实测（假上游每 0.4 秒发一帧，客户端 `read timeout = 1.0` 秒）：

```text
收完 12 块，总耗时 4.95 秒
read timeout 是 1 秒，但请求跑了 4.95 秒 —— 没有超时
```

📎 对照组（单帧后停 2.5 秒 > 1 秒间隔）：

```text
[1.03s] ReadTimeout ✅ 间隔超限被抓到
```

⭐⭐ **`read timeout` 管的是「两次读取之间的最长间隔」，不是「整个请求的总时长」。**
只要上游每 0.9 秒滴一帧，请求可以**无限期**挂着 —— httpx 只有 `connect / read / write / pool`
四个**间隔型**超时，**没有总时长上限**（待办 #55）。

---

## 13. 本文件更新日志

| 日期 | 变更 |
|---|---|
| 2026-10-13 | 初版：uv / pydantic / pydantic-settings / mypy / ruff / httpx 六节 + 总览表；所有版本号与默认值均为本机实测 |
| 2026-10-14 | 新增 §7 FastAPI、§8 uvicorn（步骤 1.1）；§0 总览表与版本基线同步；§5 ruff 补上 **E501 按显示宽度计算（汉字 = 2 列）** 的订正 |
| 2026-10-15 | §7 新增「`Annotated` 与 `Query` 的分工」「为什么必须有 `Annotated`」「更本质的理由：签名里的位置不够用」「为什么必须打包：一个位置服务多个工具」「Python 不检查类型位」「别把对象直接传进接口」「`Query` 的参数速查（29 个分四组）」「`TestClient`：自带的假客户端」；§6 新增「换代警告：`httpx2` 与 `StarletteDeprecationWarning`」；§0「还没装」补 `httpx2` |
| 2026-10-17 | §7 新增三节（步骤 6.1）：「`status`：状态码常量模块」（`status is starlette.status`、`HTTP_404_NOT_FOUND` 是 `int`、**没有** `HTTPStatus`）、「`HTTPException`：可预期的错误」（继承链 / 签名 / `http_exception_handler` 翻译点 / **两个实测反例**：`Literal` 路径参数 → 422 且泄露允许清单；`return HTTPException` → 有注解 500、无注解 **200**）、「`curl.exe`：命令行看原始响应」（Windows 自带、**必须写 `.exe`** 否则被 `Invoke-WebRequest` 别名吃掉、`-i`/`-s` 参数与输出结构） |
| 2026-10-17 | §6 新增「异常分两支 + 与 `HTTPException` 的分工」（步骤 6.2a）：`HTTPStatusError` vs `RequestError` 继承链与 `.response` 有无、**上游状态码 ≠ 我方状态码**（透传 401 的实测反例）、`as exc` 作用域、`raise ... from` 的 `__cause__` / `__context__` 实测与 B904、`base_url` 路径会被拼上的坑 |
| 2026-10-18 | 新增 **§9 logging**（原「更新日志」顺延为 §10）：默认落点实测（root 无 handler / level WARNING / lastResort 无格式）、`logger.info` 静默丢弃、12-Factor 与"不写文件"、**双 traceback 的机制**（Starlette `errors.py:186` 再抛）、access log vs 应用日志、`request_id` vs `trace_id`、兜底处理器自炸的实测结果 |
| 2026-10-18 | §7 `TestClient` 小节补一条实测：**不用 `with` 时 lifespan 不执行**（`app.state` 里没有资源 → 500），以及"先 with 再新建 client 会拿到已关闭对象"这个更隐蔽的副作用 |
| 2026-10-19 | §7 新增 `curl.exe` **完整参数速查**：`-i` / `-I`（换方法！实测 405）/ `-D -` / `-v` 的区别、body 去向、发请求参数、**`-w` 的 8 个时间变量**（用 TTFB/total 比值判流式，本项目 1:83）、`-N` 看流式的必要性 |
| 2026-10-21 | §7 重写 `status` 小节：它是**模块**不是枚举（`fastapi/__init__.py:5` 直接 `from starlette import status`）；清点出 **82 个大写常量 = 67 个 HTTP 码 + 15 个 WebSocket 关闭码**；常量是**纯 `int`**（打印只有数字、mypy 只看到 int）；与 `http.HTTPStatus`（IntEnum，带 `.phrase` / `.is_success`）逐项对比；列出 4 组「现行名 vs 已废弃旧名」（422 旧名实测会打 DeprecationWarning） |
| 2026-10-23 | 新增 §10 SQLAlchemy 2.1 与 aiosqlite（原「更新日志」顺延为 §11）；记录版本约束、`[asyncio]` extra 与 greenlet 的 2.0/2.1 差异、常用 API、`run_sync` 不是线程池、内存 SQLite 不跨重启持久；同步 §0 总览与版本基线 |
| 2026-10-26 | §10 新增「关系与索引：`ForeignKey` / `relationship` / `index=True`」（10.6a 实测）：两层分工（`ondelete` vs `cascade`）/ 五种删父子写法对比 / 📎 索引 25 倍收益 + 规模曲线证明 O(log n) / 索引三个代价（插入 +38%、空间 +18%、可能不被使用）/ `COVERING INDEX` / 三个静默坑 |
| 2026-10-25 | §2 新增「`StringConstraints`：给字符串类型本身加约束」（10.5f 实测）：`strip_whitespace=True` 先清洗再判长度 / 📎 修前 `"   "` `"\t\n"` 全角空格都返回 200 并入库空白标题、修后全 422 / 📎 `Field(min_length)` 在 `field_validator` **之前**执行，所以不能用 validator 做 strip / 📎 顺带修掉「空格+100字符+空格」被误判 `string_too_long` 的旧行为。同时订正 §2「常用语法」里「`field_validator` 可顺带清洗」那条（半错） |
| 2026-10-28 | §10 新增「`Result` 的五个取值方法 + 「一次性游标」陷阱」（10.6d-2 实测）：`execute()` 返回的是结果集容器不是值；`.all()` / `.first()` / `.one()` / `.scalar()` / `.scalar_one()` 在「1 行 / 多行 / 0 行」三种情况下的行为对照表；⭐⭐ `COUNT` 用 `.scalar_one()` 而不是 `.scalar()` —— 把「假设恰好一行」写进代码，改查询时立刻炸而不是静默返回错的数；⚠️⚠️ `Result` 是一次性游标，第 2 次 `.all()` 返回 `[]`、`.first()` 返回 `None`，**都不报错** |
| 2026-10-28 | 新增 **§11 健康探针（k8s / Docker）**（原更新日志顺延为 §12）：区分「端点（代码里的路由）」与「探针（YAML 里的配置）」两个层；三种探针（liveness 重启 / readiness 摘流量 / startup 等启动完）；⭐ HTTP 探针判定规则 **200~399 算成功**，拼错路径 → 404 → 无限重启；⭐⭐ **把数据库放进 liveness = 雪崩**（重启治不好数据库）；⚠️ FastAPI 一个健康端点都不自带（只自带 4 个文档路由）；📎 实测本项目 `/health` 200 / `/health/ready` 200 / `/healthz` 404 / `/health/live` 404 |
| 2026-10-28 | §2 新增「`field_validator` 的 `mode="before"` vs `"after"`」（10.6d-4a 实测）：📎 「补 UTC」场景下 before 遇到**字符串**输入时 `isinstance` 失败 → **静默不补**；after 唯一缺点 **返回值不重校验**（📎 返回字符串竟建对象成功）；⭐⭐ 判据「转换类型用 before，修正已校验的值用 after」；⚠️ `@classmethod` 与 mode **无关**，两种都要求 |
| 2026-10-28 | §10 新增「SQLite 下 `datetime` 的时区必然丢失」（10.6d-4a 实测）：📎 丢失点在 `sqlite.DATETIME()._storage_format` —— **格式串里没有时区占位符**；📎 `DateTime(timezone=True)` 在 SQLite 下展开，DDL 与 plain完全相同，PostgreSQL 才变 `TIMESTAMP WITH TIME ZONE`；⭐ 判据「SQLite 阶段在出口补 UTC，换 PG 时列才加 `timezone=True`」 |
| 2026-10-28 | 新增 **§12 时钟**（原更新日志顺延为 §13）：📎 本机 `get_clock_info` 实测只有 `time.time()` 是 `adjustable=True`；📎 模拟 NTP 前跳 60s → 墙钟方案在真实过去 3 秒时误触发 30 秒超时，单调钟正常；⭐⭐ 判据「**「多久」用单调钟，「何时」用墙钟**」；⭐⭐ 订正「为避免休眠不计时改用系统时钟」这个反向做法（用高频故障换低频故障）；📎 实测 `loop.time()` == `time.monotonic()`；🔴 顺带实测 **`read timeout` 是「每次读取的间隔」不是「总时长」**（read=1s 而请求跑满 4.95s 不超时）→ 新增待办 #55 |
