# learning/ —— 纯学习笔记

> **这里的知识，换一个项目照样有用。**
> 想学「FastAPI 怎么做流式」「索引为什么是 O(log n)」「日志该怎么配」→ 看这里。
> 想查「我们这个项目做到哪了、为什么这么设计、离上线还差什么」→ 去 [../project/](../project/)。

## 文件

| 文件 | 内容 | 什么时候看 |
|---|---|---|
| [stage0-engineering-basics.md](stage0-engineering-basics.md) | 阶段 0：uv / Git / pydantic / 异步 / mypy / ruff / Docker | 想起工程基础原理时 |
| [stage1-fastapi.md](stage1-fastapi.md) | 阶段 1：路由 / 依赖注入 / 中间件 / SSE / 数据库 / 工程化（**最大的一个文件**） | 查 FastAPI 与 SQLAlchemy 的机制、看实测数据 |
| [logging.md](logging.md) | **日志专题**：四道闸 / Logger 树与 `propagate` / 级别语义 / Handler 与轮转 / Formatter 字段 / `dictConfig` 参数 / 14 条注意事项 / 踩坑表 | 写日志、查"为什么没输出"、配生产日志 |
| [tools-reference.md](tools-reference.md) | 第三方包与工程工具速查（uv / pydantic / mypy / ruff / httpx / FastAPI / SQLAlchemy / logging…） | 忘了某个 API 怎么用 |
| [self-check-questions.md](self-check-questions.md) | 全部自检题 + 简要答案（**按 Step 内 1..N 编号**） | 复习、检验理解 |
| [learning-log.md](learning-log.md) | 学习流水 / 踩坑 / 结论表 / 12 个重点专题 | 查「那天为什么改成这样」 |

## 两类文件的写法差别

| | `stage*.md` / `logging.md` / `tools-reference.md` | `learning-log.md` |
|---|---|---|
| 组织方式 | **按知识点**（可随时跳读） | **按时间**（流水、踩坑、结论） |
| 什么时候读 | 想学某个东西 | 想查某天发生了什么 |
| 会不会重写 | 会（发现讲错了就订正） | ⚠️ **只追加，不改旧行**（改了就失去"当时怎么想的"的意义） |

## 判据：一条内容该写这里还是写 `project/`？

> **问自己：「换个项目，这条还对吗？」**
> **对 → 写这里。**（「`PRAGMA` 是每条连接一份」是事实，任何项目都成立）
> **不对 → 写 [../project/](../project/)。**（「我们决定给 `conversation_id` 建索引」只对本项目成立）

| 只写这里 | 只写 project/ |
|---|---|
| 原理、机制、协议 | 我们的方案选型 |
| 实测数据、N 组对照 | 进度、待办 |
| 踩坑记录（可复现的） | 生产就绪度、档期 |
| 代码怎么写 | 为什么这么设计 |

⚠️ **禁止跨类搬运**：这里不写「我们决定…」；`project/decisions.md` 不写实测表格（引用这里）。
详见 [工程规范与协作约定.md](../../工程规范与协作约定.md) §4.4d。
