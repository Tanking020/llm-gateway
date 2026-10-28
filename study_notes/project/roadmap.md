# AI 工程师学习档案与路线图

> **用途**：本文档是长期学习的唯一上下文来源（single source of truth）。
> 每次开启新对话时，请先让 AI 阅读本文档，再继续讨论。
>
> **最后更新**：2026-10-18（阶段 1 · Step 6 完成）

---

## 一、个人档案

| 项目 | 内容 |
|---|---|
| 身份 | 哈尔滨工业大学（深圳）数学专业 研一 |
| 起步时间 | 2026 年 10 月（研一上学期） |
| 专业优势 | 线性代数 / 概率统计 / 最优化 —— 对 Attention 数学、评估体系、微调理论有天然优势 |
| 已掌握 | Python 基础语法与常用库；基础算法能力；机器学习全流程 |
| 已有项目 | 房价预测（sklearn + 特征工程 + 交叉验证 + RMSE 评估，已跑通完整流程） |
| 目标岗位 | 大模型应用工程师 / AI 工程师（**应用向**，非大模型训练算法向） |
| 目标时间线 | 研一下学期或研二暑期拿到大厂 AI 应用方向实习 |
| 每周可投入 | 10 ~ 15 小时（需与课业、论文并行） |

---

## 二、能力断层分析

现有基础（房价预测）属于**传统监督学习**范式，与大模型应用栈存在以下断层：

| 维度 | 目前具备 | 目标岗位需要 |
|---|---|---|
| 模型理解 | sklearn 调参、传统 ML 算法 | Transformer / Attention / Embedding 的**概念性**理解（不需要从零训练） |
| 数据类型 | 结构化表格 | 非结构化文本、文档切分、向量化、检索 |
| 工程能力 | 单脚本 / Notebook | FastAPI、异步、数据库、Docker、API 成本与密钥管理 |
| 评估方式 | RMSE / MAE | 检索命中率、忠实度、幻觉率（RAGAS 等） |
| 系统形态 | 离线批处理 | 在线服务、流式输出、可观测性 |

> **关键判断**：目标是「应用向」，因此 Transformer 只需**理解层面**；若后续转向「大模型算法工程师」，则必须补 PyTorch / 从零实现 Transformer / 分布式训练 / SFT-DPO-RLHF，届时再重新评估（见第七节）。

**Python 语法短板追踪**（2026-10-19 新增；每轮"卡住"都记在这里，补完标 ✅）：

| 缺口 | 表现 | 补齐位置 | 状态 |
|---|---|---|---|
| **生成器 / 迭代协议**（`yield` / `__anext__` / 谁在推进） | 连续三轮问"到底谁在推进 yield"、"循环外的 yield 会不会推进"、"我代码里没有 `async for`" | [阶段1](../learning/stage1-fastapi.md) **§9.3a 六层**（冻结证据 / 状态机 / 谁在拉）+ **§9.2d ③b**（调用栈指向 `starlette/responses.py:253`） | 🟡 已讲解，待自检题 12~16、21~24 自测确认 |
| **字面量语义**（f-string / 转义 `\n`） | 问"`f"data: {payload}\n\n"` 和 `"data: [DONE]\n\n"` 是啥" | [阶段1](../learning/stage1-fastapi.md) **§9.2b**（`f` 前缀 / `{}` 插槽 / `\n` 是一个字符 / 双写 `{{}}`） | ✅ 已补齐 |
| **"帧" vs "时间"两个维度** | 问"既然有帧了为啥还要手动 sleep" | [阶段1](../learning/stage1-fastapi.md) **§9.2c**（帧是数据边界 / 帧数与时长无关 / sleep 是上游延迟的替身） | ✅ 已补齐 |
| **生成器 vs 框架的分工** | 问"`StreamingResponse` 干了啥，不是生成器都干完了" | [阶段1](../learning/stage1-fastapi.md) **§9.2d**（同一生成器三种用法 / SR 六项职责 / 手写 ASGI 对比） | ✅ 已补齐 |

> 规律：**这几项都属于"Python 语言层"而非"框架层"** —— 框架文档不会讲，但读框架源码时必须先有。
> 后续进入 RAG/Agent 若再出现同类卡壳（如装饰器、上下文管理器、`Protocol`），继续往这张表加行。

---

## 三、学习路线（总周期约 4 ~ 5 个月）

> 核心原则：**先原生 API，后框架**；每个阶段必须有**可验证产出**，不接受"看完教程就算学会"。

### 阶段 0：工程基础（1 ~ 2 周）

- **内容**：Git（branch / PR 规范）、conda 或 uv 环境管理、类型注解、`pydantic`、`async/await`、Docker 基础
- **产出**：从空目录搭建一个规范的 Python 项目（含 `pyproject.toml`、`.gitignore`、虚拟环境；Dockerfile 作为后续练习）
- **验收**：能用 Git 提交 PR、能用 Docker 跑起一个 Python 服务
- **笔记**：[learning/stage0-engineering-basics.md](../learning/stage0-engineering-basics.md)
- **状态**：✅ **已完成**（2026-10-07 ~ 10-14，步骤 `0.1 ~ 0.30`）
  - 实际产出：`uv` + `src` 布局 + Git/GitHub + pydantic 配置与数据契约 + 异步原理实验 + httpx 真实请求 + CLI 入口（`ping` 已实测调通上游 API）+ 三条质量门（ruff / mypy strict）
  - ⚠️ **验收中的两项未做，已顺延**：`Dockerfile`（留到有服务之后）、`git branch / PR` 实际演练（目前直接提交 `main`）

### 阶段 1：FastAPI + 数据库（2 ~ 3 周）

- **内容**：路由、依赖注入、`pydantic` 请求/响应模型、中间件、异常处理、**SSE 流式响应**、SQLite/PostgreSQL CRUD、SQLAlchemy
- **产出**：一个可运行的「聊天接口后端」（业务逻辑先用 echo 占位）
- **验收**：能用 curl / Swagger 调通接口，能流式返回内容
- **笔记**：[learning/stage1-fastapi.md](../learning/stage1-fastapi.md)（13 步 + 10 个难点拓展 + 5 个附录）
- **状态**：🟡 **进行中**（2026-10-14 起，Step 1~9 已完成）
  - **Step 1 ~ 6 已完成**，其中 **Step 4 于 10-18 补齐**（4a / 4b）：`ModelItem` + `ModelListResponse` 落地，`/docs` 可展开响应结构
  - Step 6：404 / 400 / 502 / 500+`request_id` / `AppError` 统一错误形状 / `lifespan` 共享 client
  - Step 7 中间件与 CORS ✅ / Step 8 异步正确姿势 ✅ / **Step 9 SSE 流式 ✅（含 9b-4a~9b-4b-3 + 复盘 + 三次补讲，2026-10-23 收口）**
  - 子进度与提交号见第六节；**Step 10 数据库进行中**：10.1 依赖取证 ✅ / 10.2 `Conversation` 模型 ✅ / 10.6b-2 `conversation_id` + pre-flight ✅ / 10.6b-3 usage 记账 ✅ / **10.6b-4 两阶段记账（`status` 三态）✅** / **10.6c N+1 + 列表账单统计 ✅**；下一步 **10.6d Step 10 收尾专项**
  - ✅ **笔记章节顺序已于 2026-10-28 整理**：`§10.6c`（N+1）原来排在 `§10.6b-2` 之前，现已移到 `§10.6b-5` 之后，编号与物理顺序一致

### 阶段 2：LLM 原生 API（2 周）

- **内容**：OpenAI 兼容 API、messages 结构、streaming、`temperature`、token 与费用计算、**Function Calling / Tool Calling**、结构化输出（JSON Schema 约束）、Prompt 工程（few-shot / CoT / system prompt）
- **产出**：命令行 + HTTP 双入口的 LLM 对话程序，支持流式与工具调用
- **验收**：能自己算出一次调用的 token 与成本；能写出一个被模型正确调用的工具函数
- **注意**：**此阶段禁止使用 LangChain**，必须手写一遍
- **状态**：⬜ 未开始

### 阶段 3：RAG（3 ~ 4 周）★ 重点

按重要性排序，不要只做「向量库 demo」：

1. 文本切分策略（固定长 / 递归 / 语义 / 父子块）—— **拉开差距的关键**
2. Embedding 模型选型（bge / m3e / text-embedding-3 系列）+ 向量库（Chroma → pgvector / Milvus）
3. **混合检索**：BM25 / 关键词 + 向量，RRF 融合
4. **重排序 Rerank**（bge-reranker / Cohere）
5. 查询改写、多路召回、HyDE
6. 上下文压缩与拼装、引用溯源（citation）、防幻觉
7. **评估体系**：RAGAS（faithfulness / answer relevancy / context precision），做参数消融实验 ★ 数学背景的差异化优势
8. 工程化：PDF/表格解析、增量索引、缓存、流式输出

- **产出**：带量化评估的中文 RAG 知识库问答系统
- **验收**：能给出「chunk 大小 vs 召回率」实验曲线；能说明加 Rerank 前后指标提升多少
- **注意**：手写一遍之后，再用 LangChain / LlamaIndex 重构，体会框架解决了什么
- **状态**：⬜ 未开始

### 阶段 4：Agent + 部署（3 ~ 4 周）

- **内容**：Function Calling 深入、ReAct、LangGraph、MCP、记忆管理；vLLM / Ollama 本地推理、Langfuse 可观测性
- **产出**：一个真实场景的多步 Agent，用 FastAPI 部署
- **验收**：Agent 能自主规划并调用多个工具完成任务；有调用链路追踪
- **状态**：⬜ 未开始

---

## 四、并行长期任务（贯穿全程，不要等）

| 任务 | 内容 | 频率 | 状态 |
|---|---|---|---|
| 算法刷题 | LeetCode Hot 100 → 进阶，笔试面试硬门槛 | 每天 1 ~ 2 题 | ⬜ 未开始 |
| 大模型八股 | Transformer 结构、Attention 计算、KV Cache、量化（INT8/INT4）、LoRA、RAG vs 微调取舍 | 每周 2 ~ 3 次 | ⬜ 未开始 |

---

## 五、项目清单（做 3 个能讲深的，不要堆 demo）

> 每个项目都必须包含：GitHub 仓库 + README + 架构图 + 可访问 demo + 「遇到什么问题 / 怎么解决 / 指标提升多少」的记录。

| # | 项目 | 关键点 | 状态 |
|---|---|---|---|
| 1 | 中文 RAG 知识库问答 | PDF 解析 + 混合检索 + Rerank + 量化评估报告 | ⬜ 未开始 |
| 2 | 真实场景 Agent | Tool calling + 多步规划 + FastAPI 部署 | ⬜ 未开始 |
| 3 | LoRA 微调小模型 | Qwen 7B 级 + 部署，理解微调成本与适用边界 | ⬜ 未开始 |

---

## 六、进度追踪

| 阶段 / 任务 | 计划周期 | 开始日期 | 完成日期 | 状态 |
|---|---|---|---|---|
| 阶段 0 工程基础 | 1 ~ 2 周 | 2026-10-07 | 2026-10-14 | ✅ 已完成（`tests/` 与 `Dockerfile` 按计划顺延，见下方"后补"） |
| 阶段 1 FastAPI + DB | 2 ~ 3 周 | 2026-10-14 | - | 🟡 进行中 |
| 阶段 2 LLM 原生 API | 2 周 | - | - | ⬜ 未开始 |
| 阶段 3 RAG | 3 ~ 4 周 | - | - | ⬜ 未开始 |
| 阶段 4 Agent + 部署 | 3 ~ 4 周 | - | - | ⬜ 未开始 |
| 项目 1 RAG 问答 | - | - | - | ⬜ 未开始 |
| 项目 2 Agent | - | - | - | ⬜ 未开始 |
| 项目 3 LoRA 微调 | - | - | - | ⬜ 未开始 |

> 状态图例：⬜ 未开始 / 🟡 进行中 / ✅ 已完成 / ⛔ 阻塞

**阶段 0 子进度（2026-10-07 ~ 10-14，明细见 [learning/learning-log.md](../learning/learning-log.md) 第一节）**：

| 区间 | 内容 | 状态 |
|---|---|---|
| 0.1 ~ 0.10 | 项目骨架：uv / Git / `src` 布局 / `.gitignore` / `.gitattributes` | ✅ |
| 0.11 ~ 0.19 | 依赖与配置：pydantic、pydantic-settings、`.env` / `.env.example`、`extra=forbid` | ✅ |
| 0.20 ~ 0.21b | 质量门：mypy（strict）、ruff（E/F/I/UP/B）+ 首次全面体检 | ✅ |
| 0.22 ~ 0.22b | 异步原理实验（协程 / `gather` 串行对比） | ✅ |
| 0.23 ~ 0.25b | GitHub 远程仓库 + README + 首次推送 | ✅ |
| 0.26 ~ 0.27b | 数据契约 `schemas.py` + httpx + 首个 HTTP 请求练习 | ✅ |
| 0.28a ~ 0.28b | `main.py` 可执行入口 + `ping` 首次真实调用上游 API（DeepSeek） | ✅ |
| 0.29 | 工具与依赖速查笔记 + 维护规则 | ✅ |
| 0.30 | 阶段 0 全面体检 + 复盘（6 类文档问题全部修复） | ✅ |
| 后补 | `tests/`（pytest，有接口后再做）、`Dockerfile`（有服务后再做） | ⬜ 顺延 |

**阶段 1 子进度（2026-10-14 起）**：

> ⚠️ **编号规则在 Step 6 处变过一次，别按一种规则去读全部**：
> - `1.1` ~ `1.4l`：**按发生顺序**编的流水号，**不等于 Step 号**。映射：`1.1`→Step 2、`1.2`→Step 1、`1.3`→Step 3、**`1.4`~`1.4l`→Step 5（依赖注入）**；`1.5`~`1.7` 是支线（改名 / 会话恢复 / copilot-instructions），不属于任何 Step
> - `6.1` 起：改用**笔记小节号**（`6.1` = Step 6 的第 1 小步），与 [learning/stage1-fastapi.md](../learning/stage1-fastapi.md) 的章节一一对应

| 编号 | 内容 | 状态 |
|---|---|---|
| 1.1 | 装 `fastapi` + `uvicorn[standard]`，起第一个服务（`/health` + `/docs`）**← 对应笔记 Step 2** | ✅ 提交 `931698c` |
| 1.1b | 补更新工具与依赖速查（§7 FastAPI / §8 uvicorn） | ✅ 提交 `3944d13` |
| 1.1c | 讲解服务运行机制（框架 vs 服务器 / ASGI / `/docs` 生成 / `--reload`） | ✅ |
| 1.2 | 系统讲解 HTTP 与 ASGI 地基（Step 1，配两组本仓库实测）**← 对应笔记 Step 1** | ✅ |
| 1.3 | 三段参数：路径 / 查询 / 请求体（Step 3）**← 对应笔记 Step 3** | ✅ 提交 `19aa9cf` / `94fb0a2` |
| 1.4a | 依赖注入第 1 步：`deps.py`（`get_settings` + `SettingsDep`），`/v1/chat` 改用 `config: SettingsDep` | ✅ 提交 `14bc45c` |
| 1.4b | 用 `TestClient` + `dependency_overrides` 实测「配置可替换」 | ✅ 提交 `bcff4f2` |
| 1.4c | `yield` 依赖：把 HTTP 客户端的生命周期交给框架（**Step 5 完成**） | ✅ 提交 `82db843`（实测复现反面写法 `is_closed=False`） |
| 1.4d-1 | 抽共用模块：新增 `src/app/llm_client.py`（`create_llm_client()`），`deps.py` 与 `main.py` 改用它，删掉重复的三行构造 | ✅ 提交 `f53c6dc` |
| 1.4d-2 | 把 client 真的接进 `/v1/chat`，发一次真实上游请求（验证 `Bearer` 拼写） | ✅ 提交 `af6cdbf`（实测 200 + 真实模型列表） |
| 1.5 ~ 1.7 | 支线（不属于任何 Step）：项目改名 / 找回改名后消失的会话 / 固化 copilot-instructions | ✅ 见 [learning/learning-log.md](../learning/learning-log.md) |
| 4a | `schemas.py` 新增 `ModelItem`（3 字段白名单）+ `ModelListResponse`（**Step 4 输出契约**） | ✅ 实测上游 10 键 → 3 字段 |
| 4b | `/v1/upstream/models` 改用 `ModelListResponse` 返回注解，`fetch_upstream_models` 返回 `list[ModelItem]`（**Step 4 收口**） | ✅ 实测 200 结构化 / 502 回归 / OpenAPI 指向 `ModelListResponse` |
| 6.1 | 未知模型返回 404（`HTTPException` + `status`，修待办 #1） | ✅ 提交 `600264b`；实测 200 / 404 |
| 6.2a | 上游错误统一翻译成 **502**（`HTTPStatusError` / `RequestError` 两分支 + `raise ... from exc`） | ✅ 提交 `3785509`；实测 200 / 502×2 |
| 6.2b | `/v1/chat` 最后一条必须是 `user`，否则 400（修待办 #2） | ✅ 提交 `e935d56`；实测 400 / 200 / 422(`too_short`) |
| 6.3a | `AppError` + `register_exception_handlers`：业务码与 HTTP 状态码解耦，统一错误形状 | ✅ 提交 `1c06665`（注释补齐 `1660faf`） |
| 6.3b | 500 兜底 + `request_id`（用户看 ID，日志看堆栈） | ✅ 提交 `abfc52c`；实测 500+request_id / 400 回归 |
| 6.4 | `lifespan`：client 改为应用级共享（待办 #5 定案） | ✅ 提交 `2a479df`；实测共享 + 关闭 |
| 7a | 请求 ID + 耗时中间件（`@app.middleware("http")`）；500 复用同一 ID 并补响应头 | ✅ 实测：沿用客户端 ID / 500 头体一致 / 日志覆盖 200·404·500 |
| 7a-补 | 新建 `src/app/constants.py`（`HEADER_REQUEST_ID`），三处硬编码收敛到一处 | ✅ 实测 `X-Request-ID` 与 `X-Request_ID` 是两个不同的头（大小写则不敏感） |
| 7b | CORS（预检、`allow_credentials` 的禁忌） | ✅ 实测：白名单返 ACAO / 非白名单仍 200 无 ACAO / 预检打不存在路径 200 / 非法方法 400 |
| 8 ~ 13 | SSE 流式 → 数据库 → 工程化 → 测试 → 部署 | 🟡 Step 8 / 9 已完成；Step 10 进行中（10.1 ✅）；Step 11~13 未开始 |
| 8 | Step 8 异步正确姿势（`blocking_demo.py`） | ✅ 实测 25 倍 / 排队 / GIL |
| 9a | SSE 假数据流式：`/v1/chat/stream` + `StreamingResponse` | ✅ 实测 TTFB 0.014s / total 1.85s / chunked |
| 9a-补 | 机制补讲四轮（学习者反馈"没看懂"）：§9.2b f-string 与 `\n\n`、§9.2c 帧 vs 时间、§9.2d 生成器与 `StreamingResponse` 分工（含调用栈铁证）、§9.3a 六层生成器讲解 | ✅ 提交 `ee8b4e2` / `696d7ae` / `98ec498` / 收尾提交；详见流水 1.24~1.29 |
| 9b ~ | 接真实上游 `stream=true`（断开局 / 中途报错 / 计费） | ✅ **全部完成**（9b-1 取证 / 9b-2 真模型流式 / 9b-3 心跳帧 + `usage` 记账 / 9b-4a 封层 + pre-flight） |
| 9b-4b-1 | 流协议加固（`data:` 无空格 / 空 data 行 / 非 dict chunk / `content` 非字符串 / 零内容保护） | ✅ 2026-10-22 完成；📎 7 种异常全部有 `[DONE]` 收尾，真上游 9 帧不变 |
| 9b-4b-2 | 流内异常编码（P2 → P3：异常路径也发 `[DONE]`）+ `choices` / `choices[0]` 守卫 | ✅ 2026-10-22 完成；📎 7 种输入全部 `DONE=True`（改前 4 种没有） |
| 9b-4b-2d | `_as_dict` 收窄 `usage` / `delta` / `finish_reason`（补齐「每次解引用都有守卫」） | ✅ 2026-10-22 完成；📎 12 用例全 `DONE=True`，`usage` 是字符串时内容不再被丢弃 |
| 9b-4b-2e | `finish_reason` 非字符串时留痕（宽松字段三档里的 ② 档） | ✅ 2026-10-22 完成；📎 6 种取值行为正确，13 用例全 `DONE=True`，真上游零 WARNING |
| 9b-4b-3 | 客户端断开：**无需写代码**，靠 `except Exception` 豁免 + `finally` 清理 | ✅ 2026-10-22 取证确认（📎 上游真的会停） |
| 9b-复盘 | Step 9 全景复盘第 1 步：笔记 §9.9 三张全景图（时间轴 21 步 / 对象关系 / 12 个失败点）+ 三条易错规律 | ✅ 2026-10-23 完成；📎 实测中间件日志 42.7ms vs 流结束 1266.9ms |
| 9b-补讲 | 后续三次深挖（学习者提问驱动）：**§9.2e 四个单位**（token / 帧 / 行 / 字节块）、**§9.10 接收流式 vs 返回流式**（2×2 矩阵）、`stream` 参数落点清点 | ✅ 2026-10-23 完成；📎 §9.2e：15 字节块 / 75 帧 / 6 片段；§9.10：靠 `stream` 默认值的只有 `list_models()` 一行 |
| 10.1 | 依赖取证与版本边界：确认 `sqlalchemy[asyncio]` / `aiosqlite` 已装；在独立 venv 复现裸装 2.1 的 `ImportError`，再补 extra 修复、补驱动 | ✅ 2026-10-23 完成；📎 裸装 2.1.6 → `ModuleNotFoundError: No module named 'greenlet'`；补 `[asyncio]` 后立即可用；`import aiosqlite` 仍报缺失（证明驱动不在 extra 里） |
| 10.2 | `Conversation` 模型（`Base` / `Mapped` / `mapped_column` / `default=lambda`） | ✅ 2026-10-23 完成；📎 建表+插入+读回成功；实测 `String(100)` 塞 200 字符不报错、`created_at` 读回 `tzinfo=None` |
| 10.3a | 引擎与会话工厂：`config.database_url` + `database.py`（`engine` / `SessionMaker`）+ `.gitignore` 忽略 `*.db` | ✅ 2026-10-24 完成；📎 `Test-Path app.db` = False（engine 不连库）；`git check-ignore` 确认规则生效 |
| 10.3b | `lifespan` 集成：启动段建表 + 关闭段 `dispose()`；连接池与 `async with` 补讲 | ✅ 2026-10-24 完成；📎 从零启动生成 `app.db` 并读出 `conversations` 表结构；重启幂等；📎 复用连接快 **6.28 倍**（20 次请求 1 条 TCP vs 20 条） |
| 10.4b | `get_db` + `DbDep`：一次请求一个会话，正常提交 / 异常回滚后 `raise` | ✅ 2026-10-25 完成；📎 `/ok` 入库 1 行、`/boom` 回滚 0 行、500 证明 raise 生效；📎 订正旧结论「不 raise → 200」（实际是日志根因全丢） |
| 10.5a | 两个契约（`ConversationIn` / `ConversationOut`）+ `POST /v1/conversations` | ✅ 2026-10-25 完成；📎 201×2（id=1/2）、422×2（too_short / too_long）、读库 2 行；⚠️ 首跑 500（`title=payload`），三道门没拦住（`**kwargs`） |
| 10.5b | `GET /v1/conversations` 列表：`select()` + `order_by()` + `.scalars().all()` | ✅ 2026-10-25 完成；📎 空表 `[]`[200] / 两条升序[200]；📎 印证 `created_at` POST 带 Z、GET 不带 |
| 10.5c | `GET /v1/conversations/{conv_id}` 详情：`await db.get()` + 判空 → 404 | ✅ 2026-10-25 完成；📎 五条 URL 全对（200/404/422/200/404）；📎 不判空 → `ResponseValidationError` → 500 |
| 10.5d | `DELETE /v1/conversations/{conv_id}`：`await db.delete()` + 204 无内容 | ✅ 2026-10-25 完成；📎 生命周期五步全对（200/204/404/404/200），读库确认空表；📎 204 语义补测（改 200 → 客户端收 null，且"没做事"无法区分） |
| 10.5e | `PATCH /v1/conversations/{conv_id}`：`ConversationPatch` + 部分更新 | ✅ 2026-10-25 完成（⚠️ 起因：学习者发现上一轮我误称「CRUD 四接口完成」，Update 未做）；📎 九种情况全对；必填字段作为 bug 探测器的判据入笔记 |
| 10.5f | **抽出公共规则 `ConversationTitle`**：`StringConstraints(strip_whitespace=True)` 堵住「纯空格标题」 | ✅ 2026-10-25 完成（测试中发现缺口）；📎 修前 `"   "` / `"\t\n"` / 全角空格全部返回 200 并入库空白标题；📎 修后全部 422；📎 顺带修掉「空格+100字符+空格」被误判超长的旧行为；POST/PATCH 共用一处定义 |
| 10.6a | `LlmCall` 表 + `Conversation.calls` 一对多（外键 / `cascade` / `conversation_id` 索引） | ✅ 2026-10-26 完成；📎 建表语句含 `ON DELETE CASCADE` + `ix_llm_calls_conversation_id`；📎 索引实测 25 倍（5 万行）+ 规模曲线证明 O(log n)；📎 五种删父子写法对比；⚠️ 批改订正一处理解错误（`ondelete=` 不能解决 ORM 置 NULL） |
| 10.6b-1 | 打开 SQLite 外键强制（`engine.sync_engine` 的 `connect` 事件 + `PRAGMA foreign_keys=ON`） | ✅ 2026-10-26 完成；📎 池内 3 条连接全为 1；孤儿 `conversation_id=999` 被 `IntegrityError` 拒；📎 **订正 10.6a 的旧结论**：10 组矩阵证明 `ondelete` 依赖 `PRAGMA`，且「有 relationship 无 cascade」会抵消级联 |
| 10.6b-2 | `ChatRequest` 加 `conversation_id` + pre-flight（不存在 → 404，流开始前拦） | ✅ 2026-10-27 完成；📎 六项验证 200 / 404 / 404 / 422 / 200 / 400×2；⭐ 顺带把「对话不存在」的 5 处重复抽成 `require_conversation`，并统一两条 chat 的校验顺序 |
| 10.6b-3 | 生成器里写 `LlmCall`（第一版：`except BaseException` 回滚守卫） | ✅ 2026-10-27 完成，⚠️ **但方案在 1.63 被推翻**：守卫守的是「编造的帧序」，且业务上让断开的调用完全不留账（学习者指出「断了也花了 token」） |
| 10.6b-4 | **两阶段记账**：流开始前落 `pending` 行 → 拿到 usage 改 `completed` → 断开/异常只做同步赋值 `aborted` | ✅ 2026-10-27；📎 真 app 中间件栈下 5 种「断开时补写」全失败，只有「提前写」可行；📎 四格验收 + 真实 DeepSeek 端到端；新增 `LlmCall.status`（`pending`/`completed`/`aborted`） |
| 10.6b-4a | 流开始前 `add` + `flush` 一行 `pending`（`yield thinking` 必须挪到其后） | ✅ 学习者手写；📎 两次真实调用都是 `completed` 且 token 非 0 |
| 10.6b-4b | 两个 `except` 去掉 `rollback`，改成同步赋值 `aborted` | ✅ 学习者手写；📎 端到端：断开 `aborted 0/0/0`、正常 `completed 33/49/82`；⚠️ 首次验收拿到 404 `对话不存在：1`（库被删过）导致测试空转 |
| 10.6c | N+1 原理 + `selectinload` 实测 | ✅ 2026-10-28；📎 三种写法实测（N=5：6/2/1 条），规模曲线 N=100 时 **101 条 57.7ms vs 2 条 4.9ms**；📎 async 下惰性加载是 `MissingGreenlet` 报错不是变慢；落地成 `GET /v1/conversations` 加 `call_count` + `total_tokens`（`outerjoin` + `coalesce`） |
| 10.6d | Step 10 收尾专项（分页 #25 / `/health` #26 / `updated_at` #31 / 形状统一 #39） | ⬜ 待做 |

> ✅ **Step 9 于 2026-10-23 正式收口**：代码（9a → 9b-4b-3）、文档（§9.1~§9.11）、自检题 1~61、待办 #1~#23 全部关闭。
> **下一个动作 = Step 10 数据库**。开工前注意两条与本步相关的遗留：待办 **#8**（`/v1/chat` 仍是 echo）与 **#11**（`/docs` 把流式接口标成 `application/json`）。

**阶段 1 已知待办（体检发现，归属到对应 Step 时再修）**：

| # | 待办 | 现状 | 建议处理时机 |
|---|---|---|---|
| 1 | ~~`GET /v1/models/{model_name}` 对**不存在的模型返回 200**（应 404）~~ | ✅ **已解决**（6.1，2026-10-17）：改用 `raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, ...)`；实测 `this-model-does-not-exist` → `404 {"detail":"模型不存在: ..."}` | **已完成** |
| 2 | ~~`/v1/chat` **不检查最后一条消息的角色**~~ | ✅ **已解决**（6.2b，2026-10-17）：最后一条不是 `user` → `400 {"detail":"最后一条消息必须是 user，当前是 system"}`；实测 `user` 仍 200、空列表仍 422(`too_short`) | **已完成** |
| 3 | `KNOWN_MODELS` 与 `/v1/models/latest` 仍是硬编码 | `/v1/models/latest` 返回 `KNOWN_MODELS[0]`，与 `settings.llm_model` 无关联；改配置时两处会不一致。现在已有 `/v1/upstream/models` 作为对照，可改用真实数据 | **Step 7 之后**（或做缓存/降级策略时） |
| 4 | ~~`deps.py` 的 `get_llm_client()` 与 `main.py` 的 `create_client()` 构造参数刻意重复~~ | ✅ **已解决**（提交 `f53c6dc`）：抽出 `src/app/llm_client.py` 的 `create_llm_client()`，两边共用；实测构造参数已收敛到 1 处 | **已完成** |
| 5 | ~~client 生命周期按"请求级"还是"应用级"管~~ | ✅ **已定案**（6.4，2026-10-18）：改为 **应用级**（`lifespan` 创建 + `app.state.llm_client` 共享）；实测 startup 后 `is_closed=False`、两次请求同一对象、shutdown 后 `is_closed=True`。性能依据：每请求新建比共享慢 **2.23 倍** | **已完成** |
| 6 | **三种错误响应形状并存**：400 `{"error":{code,message}}` / 404 `{"detail":"…"}` / 422 `{"detail":[…]}` | 客户端要写三份解析代码。判据：错误形状应让客户端只写一份 | **Step 11（工程化）**：给 `HTTPException` 与 `RequestValidationError` 各注册处理器统一形状 |
| 7 | **日志只有基础**：无格式化（无时间/级别/模块名）、`logger.info` 被静默丢弃、无文件/集中收集 | 现在只有 ERROR 级能出现在终端；排查时缺上下文 | **Step 11**：`logging.dictConfig` + 统一格式 +（生产）日志收集 |
| 8 | `/v1/chat` 仍是 `echo` 占位（Step 9 只让**流式**路由接了真上游）；`app.state.llm_client` 是 `Any`（mypy 校验不到属性拼错） | 📎 Step 9 收口后实测：`POST /v1/chat` → `{"content":"[echo] 你好",...}`，未触碰上游。⚠️ 接真上游时**不要照抄流式写法**：建议「**接收流式 + 返回非流式**」（能中途取消省钱 / 逐帧记账 / 防坏帧），判据见笔记 §9.10 ⑦ | **Step 10 之后或阶段 2**；类型问题**随时可做** |
| 9 | **`HEAD` 请求返回 405**（`allow: GET`） | 实测 `curl -I http://127.0.0.1:8000/health` → `405 Method Not Allowed`。因为 `@app.get(...)` 只注册 GET。有些监控/探活工具用 HEAD 探测会失败 | **随时可做**：`@app.api_route("/health", methods=["GET", "HEAD"])` 或加一个 `@app.head("/health")` |
| 10 | **流内错误尚未编码**（9b 才做） | 现在 `/v1/chat/stream` 是假数据，不会中途出错；接真实上游后必须用帧报错 + `finally` 发 `[DONE]`，否则前端只看到"连接被掐断" | **9b** |
| 11 | `/docs` 把流式接口标成 `application/json` + 空 schema | 实测 `app.openapi()` 里 `/v1/chat/stream` 的 `200.content` 是 `application/json: {schema: {}}`，实际返回的是 `text/event-stream`。因为返回注解是 `Response` 子类时 FastAPI 把 `response_model` 置空（`fastapi/routing.py:1116`） | **随时可做**：给装饰器加 `responses={200: {"content": {"text/event-stream": {}}}}` |
| 12 | ~~`choices[0]` 缺 `index != 0` 防御~~ | ✅ **已解决**（9b-3 收口，2026-10-21）：`app.py:368~369` 加 `if choice.get("index", 0) != 0: continue`。原记录： 📎 实测 DeepSeek 只支持 `n=1`（`n=2/3` → 400），所以现在安全；但若换上游支持多候选，逐帧取 `choices[0]` 会把两路文字**搅成乱码**（模拟实测：`'答另案一A段'`）。修法 1 行：`if choice.get("index", 0) != 0: continue` | **已完成** |
| 13 | ~~`prompt_cache_hit_tokens` / `miss_tokens` 未进日志~~ | ✅ **已解决**（9b-3 收口，2026-10-21）：`流式用量` 日志已加 `cache_hit=%s cache_miss=%s`，实测输出 `cache_hit=0 cache_miss=44`。原记录： 已有 `usage` 转发但日志只打了 `prompt/completion/total/reasoning`，**缺前缀缓存命中率**这个可观测指标。📎 实测固定前缀可到 hit 1408 / miss 245（85%）。修法：在 `流式用量` 那条 `logger.info` 里加两个字段 | **已完成** |
| 14 | ~~**L3 上游结构异常全落到 500**（应 502）：HTML 错误页 / 空 body / 字段改名 / `{"error":...}` / `data: null` / 元素缺 `id` / 元素非对象~~ | ✅ **已解决**（9b-4a 收口，2026-10-21）：`LlmClient.list_models` 里 `except (ValueError, KeyError, TypeError)` → `AppError(UPSTREAM_MALFORMED)` → 502。📎 原实测：MockTransport 6 种全 500。原修法记录：`resp.json()` + 取字段包进 `try/except (ValueError, KeyError, TypeError)` | **9b-4a 已完成** |
| 15 | 🟡 **流式下 4 种上游异常导致「200 + 断连」**：`message` 而非 `delta`（上游忽略 `stream:true`）/ `delta: null` / `data:` 行坏 JSON / 其它。**其中 `delta` 两项已被学习者修掉**（`app.py:376` 改成 `choice.get("delta") or {}`，📎 实测 `message`/`delta:null`/缺 `delta` 三种都不再崩，退化为「只发 finish_reason」） | 📎 修前分别抛 `KeyError` / `AttributeError` / `JSONDecodeError`；修后前两种已安全。⚠️ 但「上游忽略 stream」时**回答文字会被静默丢弃**（现有代码不报警）——仍需处理  | **9b-4**：坏 JSON 与「忽略 stream」仍需处理；错误编码进流 + `finally` 发 `[DONE]`（规范 §14.4 ③） |
| 16 | ~~**`data:xxx`（无空格，SSE 合法）→ 整条流被静默丢弃**~~：✅ **9b-4b-1 已修**（`startswith("data:")` + `lstrip()`，📎 三种写法都收到 chunk）。原记录：`startswith("data: ")` 判定失败，**0 输出、不报错** | 📎 实测：客户端只收到 `thinking` 与 `[DONE]`，中间全空，日志无任何异常 —— 最危险的「静默错误」 | **9b-4**：改 `line.startswith("data:")` + `line[len("data:"):].lstrip()`（规范 §14.6 #6） |
| 17 | ~~**`content` 是数组时会把 list 塞进 `{"delta": [...]}`**~~：✅ **9b-4b-1 已修**（`isinstance(text, str)` + WARNING）。原记录：（多模态风格的 `[{"type":"text","text":"..."}]`） | 📎 实测 `if not text` 判定**通过**（list 为真值）→ 前端拿到数组而非字符串 | **9b-4**：`if not isinstance(text, str): continue`（或显式取 text 字段） |
| 18 | **`llm_api_key` 为 `None` 时拼出 `Authorization: Bearer None`**；**`request_timeout` 是单一值**（同时作用于 connect 与 read） | 📎 实测前者生成 `'Bearer None'`（看起来像真凭证 → 上游 401 → 误判「密钥错了」）；`main.py` 有检查，`lifespan` 里**没有**。后者属推断：流式首 token >30s 会被误判超时 | **阶段 2**：lifespan 里加 `if not settings.llm_api_key: raise`；超时改 `httpx.Timeout(connect=5, read=60, write=10, pool=5)` |
| 19 | ~~**上游调用尚未封层**：`app.py` 直接持有 `httpx` 并自己翻译 L1/L2/L3~~ | ✅ **已解决**（9b-4a 收口，2026-10-21）：抽出 `LlmClient` / `LlmChatStream`，路由层零 `try/except`、零 `import httpx`（`TID251` 机械保证）；`chat_stream` 加 pre-flight（📎 上游 400 → 客户端拿 **502**）。📎 迁移前已用 13 种上游场景对照两套实现，状态码逐条一致 | **9b-4a 已完成** |
| 20 | ~~**流式 L3 无法在 pre-flight 发现**~~：✅ **9b-4b-1 已修**（零内容保护发 `STREAM_NO_CONTENT`）。原记录：上游 `200` + 非 SSE body（如 HTML 页面）时，客户端只收到 `thinking` + `[DONE]`，中间全空 | 📎 端到端实测（9b-4a 收口复验仍如此）：`POST /v1/chat/stream` 上游返回 `200 <html>` → 我方 `200` + `thinking` + `[DONE]`，**零内容、零报错** | **9b-4b**：`aiter_chunks` 统计帧数，`0 帧` 时补一帧 `event: error`；顺带处理 `data:` 无空格（#16）与 `content` 非字符串（#17） |
| 21 | **`_STATUS_BY_CODE.get(code, 400)` 兜底是 400**：未登记的业务码会被伪装成「客户端的错」 | 📎 与 `UPSTREAM_MALFORMEAD` 那次事故同源 —— 拼写错 + 兜底 400 = 静默返回 400，三道门全绿。建议兜底改 **500** 并 `logger.error` 记一条「未登记的业务错误码」 | **待定**（一行改动，但要先确认没有依赖 400 的调用方） |
| 22 | ~~**流内异常仍是 P2 形态**~~：`data:` 行坏 JSON 时客户端**连 `[DONE]` 都收不到** | ✅ **9b-4b-2 已修**：`[DONE]` 挪进 `try` + `except Exception` 分支各发一次（📎 实测 7 种输入全 `DONE=True`） | — |
| 23 | ~~**`usage` / `delta` / `finish_reason` 拿到非预期类型时会中止整条流**~~（📎 实测 `usage` 是字符串 → `STREAM_FAILED`，内容明明能送达） | ✅ **9b-4b-2d 已修**（`_as_dict()` + `isinstance(finish_reason, str)`）；📎 12 用例全 `DONE=True` | — |
| 24 | 🔴 **CORS `allow_methods` 缺 `PATCH` / `DELETE`**：浏览器预检 `OPTIONS` 直接 400，前端完全无法调用这两个接口 | 📎 2026-10-25 实测：`OPTIONS /v1/conversations/1` + `Access-Control-Request-Method: PATCH` → **400**，`allow-methods: GET, POST`。⚠️ `curl` 测不出来（CORS 只在浏览器生效），实际请求本身还是 200/204 且带 `ACAO` 头。根因：10.5d / 10.5e 加路由时没同步 CORS 列表 | ✅ **已修**（2026-10-25）：`allow_methods=["GET","POST","PATCH","DELETE"]`；📎 复测四种方法预检全 200，`PUT` 仍正确拒绝 |
| 25 | 🟠 **`GET /v1/conversations` 无分页**：一次返回全表 | 代码里 `select(Conversation).order_by(...)` 直接 `.all()`，无 `limit` / `offset` / 游标。数据量上千后响应体过大、内存峰值高；且与 `/v1/models`（有 `?limit=`）风格不一致 | **10.6d**（Step 10 收尾）：加 `?limit=&offset=` + `total`，或改游标分页 |
| 26 | 🟠 **`/health` 不检查数据库连通性**：库挂了仍返回 ok | `async def health()` 只 `return {"status": "ok"}` —— 只证明进程活着。Docker / 负载均衡据此不会摘掉不健康实例 | **10.6d** 或 **Step 13 部署**：加 `SELECT 1` 探活，失败返回 503 |
| 27 | 🟡 **`.env.example` 缺 `DATABASE_URL`**：别人 clone 后不知道有这个配置项 | 📎 2026-10-25 核对：模板里有 `APP_NAME` / `APP_ENV` / `DEBUG` / `HOST` / `PORT` / `LLM_*` / `REQUEST_TIMEOUT`，**唯独没有 `DATABASE_URL`**（10.3a 新增了 `config.database_url` 但没同步模板） | **随时可做**（1 行）：补 `DATABASE_URL` 及注释 |
| 28 | 🟡 **`settings.debug` 定义了但没传给 `FastAPI(debug=...)`** | 📎 核对：`app = FastAPI(title=..., description=..., version=..., lifespan=lifespan)` —— **没有 `debug` 参数**。`settings.debug` 只在 `main.py:77` 的 CLI 演示里打印一次 | **Step 11**：与日志 / 配置一起收拾；顺带决定生产环境是否关闭 `/docs` |
| 29 | 🟡 **`settings.host` / `settings.port` 完全未被使用**：配置漂移 | 📎 核对：这两个字段在 `.env.example` 里写得清清楚楚，但代码里**零引用** —— 实际监听地址由 `uvicorn app.api.app:app --reload` 命令行决定 | **Step 13 部署**：改成 `uvicorn.run(app, host=settings.host, port=settings.port)`，或删掉这两个字段 |
| 30 | 🟡 **`created_at` 时区不统一**：POST 返回带 `Z`，GET 返回不带 | 📎 实测：POST → `...318091Z`；GET → `...318091`（无 Z）。根因：POST 返回**内存对象**（`tzinfo=UTC`），GET 从库读回（SQLite 不存时区）。`DateTime(timezone=True)` **同样丢失** | **触发条件**：前端开始用 `created_at` 做时间计算时。修法：出参统一 `astimezone(UTC)` 或在 schema 层加 `field_serializer` |
| 31 | ✅ **`Conversation` 无 `updated_at`** | 已解决（2026-10-28，10.6d-1）：`updated_at` 加 `default` + `onupdate` 双 lambda。📎 实测：首次插入 `created_at == updated_at`；PATCH 后 `created_at` 不变、`updated_at` 变晚；**值没变（dirty check）就不发 UPDATE、`updated_at` 也不动**。⚠️ `onupdate` 是 **SQLAlchemy 在 Python 侧**算好塞进 SQL 的，**不是数据库触发器**（`sqlite_master` 里 0 个 trigger）—— 绕过 ORM 直接写 SQL 时不会更新。⚠️ 另：SQLite 读回的 `datetime` **不带 tzinfo**，引出待办 #45 | — |
| 32 | 🟡 **PATCH 无并发控制**：两个客户端同时改，后写覆盖前写（lost update） | PATCH 直接 `conv.title = payload.title`，无版本号 / `If-Match` 校验。将来加字段后，A 与 B 各改不同字段会互相覆盖 | **阶段 2 之后**（当前只有一个可改字段，风险低） |
| 33 | ~~**无索引**：除主键外没有任何索引~~ | 📎 核对 `models.py`：`Index` / `unique` 出现次数均为 **0**。将来按 `created_at` 排序或按 `conversation_id` 查 `llm_calls` 会全表扫 | ✅ **已完成**（10.6a，2026-10-26）：`llm_calls.conversation_id` 已加 `index=True`，📎 实测 25 倍 |
| 34 | 🟡 **无软删除**：`DELETE` 是真删，误删无法恢复 | `await db.delete(conv)` 直接从表里删行。⚠️ 注意：这**不影响账单**（10.6b 已改 `ondelete="SET NULL"`，计费记录保留）。📎 若要做软删除，实测代价：所有列表查询必须加 `deleted_at IS NULL`（漏一处返回已删数据）/ 外键失效（能给已软删的对话挂新计费）/ 表无限增长 / 与「被遗忘权」冲突 | **产品出现「回收站 / 撤销删除」需求时**（属产品决策，见 decisions #16 的「两个正交决策」） |
| 35 | 🟠 **对话只有标题，没有消息内容** —— 没有 `messages` 表 | 现在 `conversations` 只有 `id` / `title` / `created_at`。`/v1/chat/stream` 完全不落库 → **这个后端还不能真正「管理对话」** | **10.6 之后 / 阶段 2**：建 `messages` 表（`conversation_id` / `role` / `content`），流式接口写用户消息 + 助手回答 |
| 36 | 🟡 **无认证 / 鉴权**：任何人知道 URL 就能删任何对话 | 所有 `/v1/conversations` 接口零鉴权；也没有「对话归属哪个用户」的字段 | **阶段 3 部署前必须做**：至少加 API key 头校验；正式版需用户表 + `owner_id` |
| 37 | 🟡 **无速率限制**：会被刷爆（真金白银） | `/v1/chat` 与 `/v1/chat/stream` 每次调用都花钱，但没有限流。一个循环就能烧完余额 | **阶段 3 部署前**：加 IP / key 维度限流（`slowapi` 或网关层） |
| 38 | 🟢 **无请求体大小限制**：超大 body 会占满内存 | FastAPI 默认不限制 body 大小。`title` 有 `max_length=100`，但 `messages` 列表与单条 `content` 只有长度下限 | **阶段 3 部署前**：网关（nginx `client_max_body_size`）或中间件层限制 |
| 39 | 🟡 **`/v1/models` 与 `/v1/upstream/models` 形状不一致** | 前者返回 `{"total": int, "items": list[str]}`，后者返回 `ModelListResponse`（`items` 是 `ModelItem` 对象）。同一概念两种形状 | **10.6d**（与分页一起）：统一成 `ModelListResponse` |
| 45 | 🟠 **同一字段两种时间格式：`...Z` vs 无 `Z`** | 📎 实测同一个 `created_at`：`POST` 返回 `"2026-10-28T05:51:54.604445Z"`（**带 Z**），`GET` / `PATCH` 返回 `"2026-10-28T05:51:54.604445"`（**无 Z**）。根因：新建时值来自 Python 侧 `lambda`（aware），读回时来自 SQLite（**naive，tzinfo 丢了**）。⚠️ 前端 `new Date("2026-10-28T05:51:54.604445")` 会按**本地时间**解析 → 时区差 8 小时。修法：`ConversationOut` 用 `AwareDatetime` 类型 + `field_serializer`，或统一在 schema 层补 `tzinfo=UTC` | **10.6d 最后统一形状时**（与 #39 一起，只需一次测试） |
| 40 | 🟡 **没有 `tests/` 目录**：全部验证靠手工 curl + 临时脚本 | 📎 核对：项目根下 `tests/` **不存在**。每次改动靠手跑 curl 或临时探针脚本（用完即删），无法回归 | **Step 12**（测试 FastAPI）：建 `tests/` + `TestClient` + 关键路径用例 |
| 41 | 🟠 **写 `LlmCall` 出参 schema 时 `conversation_id` 必须 `int \| None`**，且要带 `status` | 📎 实测同一条 `conversation_id=None` 的记录：schema 写 `int` → **500 Internal Server Error**（客户端完全不知道是 NULL 导致）；写 `int \| None` → **200 `null`**。⚠️ 另：`call.conversation` 在 NULL 时是 `None`，取 `.title` 会 `AttributeError` → 也必须判空。⭐ 10.6b-4 之后还要暴露 `status`（`pending`/`completed`/`aborted`）。详见笔记 §10.6b-2 / §10.6b-4 | **10.6b-3 之后做查询接口时**（或现在就先定好 schema 形状） |
| 42 | 🟠 **账单还扛不住进程崩溃（`flush` 不是持久化）** | 📎 强杀 uvicorn 实测：流进行中 `pending` 行已 `flush` 过，进程一死 `llm_calls = []` —— **一行都没有**。要真扛崩溃，得在流开始前**用独立会话 `commit` 一次**（`async with SessionMaker() as acct: acct.add(...); await acct.commit()`），代价是每请求多一次独立事务提交。⚠️ 另：断开时 token 只能记 `0`（usage 帧永远到不了），**金额算不出来** —— 要不要按已转发内容估算 `completion_tokens`？详见笔记 §10.6b-4 | **要做「账单统计 / 成本看板」时**（10.6d 或阶段 2 末） |
| 43 | 🟠 **`aborted` 行 token 全 `0`，攻击成本在账面上隐形** | 📎 实测 `prompt_tokens` **只由输入决定**（同样 `'hi'` 三次都是 `31`，长文本 `52`）→ 断开时它其实**可预知**，记 `0` 是不必要的。建议：`aborted` 行至少记 `prompt_tokens`（发请求前算），`completion_tokens` 按已转发字符数估算。⚠️ 估算值只能用于**对账**，不能用于计费（真实金额以上游账单为准）。详见 [decisions #21](decisions.md#21-防刷靠限流不靠记账准确度) | **10.6d 做账单相关接口时** |
| 44 | 🔴 **完全没有限流 / 配额 / 并发上限** | 📎 实测：客户端断开后 `aclose()` 能让上游 **4ms 内停止生成**（40 帧只发出 3 帧，6 秒只花 455ms），所以单次攻击损失有上界；⚠️ 但**高频请求 + 高并发**完全敞开。⭐⭐ **记账再准也拦不住，防护必须独立**。优先级：① 并发上限（`asyncio.Semaphore`，不需要 token 数）② 每用户速率 ③ 日配额。⚠️ 单进程 `Semaphore` 在 `--workers 4` 下就是 4 倍，真正上线要放 Redis / 网关层。详见 [decisions #21](decisions.md#21-防刷靠限流不靠记账准确度) | **阶段 3 部署前必须做**（与 #36 #37 一起） |


**待办 → 步骤 对照（2026-10-25 审计后新增）**：

| 步骤 | 这一步要解决的待办 | 关联编号 |
|---|---|---|
| **10.6a** | `LlmCall` 表 + `Conversation.calls` 一对多（外键 + `cascade` + `conversation_id` 索引） | #33（索引） |
| **10.6b-1** | 打开 SQLite 外键强制（`connect` 事件 + `PRAGMA foreign_keys=ON`） | — |
| **10.6b-2** | `ChatRequest` 加 `conversation_id` + pre-flight 校验（`require_conversation` 一处实现） | #41（`LlmCall` 出参 schema 要提前定形状） |
| **10.6b-3** | 生成器里写 `LlmCall` + 第一版回滚守卫（⚠️ 方案已被 10.6b-4 推翻） | — |
| **10.6b-4** | **两阶段记账**：`status` 三态（`pending` / `completed` / `aborted`） | #41（`LlmCall` 出参 schema 也要带 `status`） |
| **10.6c** | N+1 原理 + `selectinload` 实测 + 列表加账单统计 | #43（账单统计的第一步） |
| **10.6d** | **Step 10 收尾专项**（分页 / `updated_at` / `/health` 探活 / 形状统一） | **#25 #26 #31 #39** |
| **10.8** | Step 10 自检（59 题） | — |
| **11** | 工程化：`dictConfig` / 统一错误形状 / `settings.debug` / 生产关 `/docs` | **#6 #7 #28** |
| **12** | 测试 FastAPI：建 `tests/` + `TestClient` | **#40** |
| **13** | 部署：`settings.host/port` 接线 / body 大小 / 限流 / 鉴权 | **#29 #36 #37 #38** |
| **阶段 2** | 消息落库 / 软删除 / 并发控制 / KNOWN_MODELS 改真实数据 | **#3 #32 #34 #35** |
| **随时** | `DATABASE_URL` 补进 `.env.example` | **#27** |

---

## 七、路线分岔提醒

- **LLM 应用 / AI 工程师**（当前选择）：FastAPI + RAG + Agent + 工程化，PyTorch 只需理解层面，门槛相对友好。
- **大模型算法工程师**：必须 PyTorch、从零实现 Transformer、DeepSpeed/Megatron 分布式训练、SFT/DPO/RLHF、推理优化；通常要求顶会论文或大厂实习，竞争激烈。

**决策点**：阶段 3（RAG）完成后重新评估，届时对行业的判断会更准确。

---

## 八、学习资料结构

```text
llm-app-engineering\                       # 项目根
├── 工程规范与协作约定.md        # 协作规范（开新对话第一个读）
├── README.md                    # 面向使用者的说明（含架构决策与路线图）
├── study_notes\                 # 学习笔记集中存放（2026-10-27 分两个文件夹）
│   ├── project\                 # 【项目业务】这个项目自己的台账
│   │   ├── roadmap.md           # 本文档：进度 / 路线 / 待办清单
│   │   └── decisions.md         # 业务与架构决策（为什么项目长成这样）
│   └── learning\                # 【纯学习笔记】换个项目照样有用的知识
│       ├── stage0-engineering-basics.md   # 阶段 0：工程基础
│       ├── stage1-fastapi.md              # 阶段 1：FastAPI 速成
│       ├── tools-reference.md             # 第三方包与工程工具速查
│       ├── self-check-questions.md        # 全部自检题 + 简要答案
│       └── learning-log.md                # 过程与收获：流水 / 踩坑 / 结论
├── pyproject.toml / uv.lock / .python-version / .gitignore / .gitattributes
├── .env.example（提交） / .env（不提交）
├── src\app\                     # 应用代码
│   ├── config.py                # 配置（pydantic-settings）
│   ├── schemas.py               # 对外数据契约（pydantic）
│   ├── constants.py             # 必须跨模块一致的常量（如 HTTP 头名）
│   ├── errors.py                # 业务异常 AppError + 错误码→状态码映射 + 异常处理器注册
│   ├── llm_client.py            # 上游 HTTP 客户端的唯一构造点
│   ├── main.py                  # 阶段 0 的 CLI（演示 + ping 连通性检查）
│   └── api\
│       ├── app.py               # 阶段 1 的 FastAPI 应用对象 + lifespan + 路由
│       └── deps.py              # 依赖注入声明（get_settings / get_llm_client）
└── playground\                  # 实验区：一次性验证代码，随时可删
```

> 环境由学习者自行从零搭建与记录；本仓库不预设本机工具版本、路径或用户级配置。

### 笔记索引

| 笔记 | 规模 | 覆盖内容 |
|---|---|---|
| [learning/stage0-engineering-basics.md](../learning/stage0-engineering-basics.md) | 2457 行 | uv / Git / pydantic / 类型注解 / 异步 / 测试 / lint / Docker + 11 个难点拓展 |
| [learning/stage1-fastapi.md](../learning/stage1-fastapi.md) | 4375 行 | HTTP/ASGI → SSE 流式 → 数据库 → 测试 → 部署，共 13 步 + 10 个难点拓展；**Step 6 后有「前半程回顾」**（复习入口） |
| [learning/learning-log.md](../learning/learning-log.md) | 884 行 | 步骤流水 / 踩坑 / 重要结论 / 重点专题（每步自动追加） |
| [learning/tools-reference.md](../learning/tools-reference.md) | 914 行 | 每个依赖与工具的定位、安装、常用语法与命令、实测默认值、易错点（§9 起含标准库 logging） |
| [learning/self-check-questions.md](../learning/self-check-questions.md) | 415 行 | **全部自检题 + 简要答案**，按阶段/步骤排列；⭐ 标高频、🟡 标答错过、📎 标有配套实测 |
| [工程规范与协作约定.md](../../工程规范与协作约定.md) | 1486 行 | 协作节奏、步骤卡模板、质量门、目录与命名、安全约定 |

> ⭐ 两篇阶段笔记的代码**全部在真实环境实测过**（本仓库实测版本：fastapi **0.143.0** / starlette **1.8.0** /
> uvicorn **0.54.0** / pydantic 2.13.5 / httpx 0.28.1），并标注了 2026 年的废弃写法（`on_event`、`TestClient` 的 httpx 依赖等）。
>
> 📋 **复习入口**：阶段笔记里的"自检"小节只保留标题 + 指向 [learning/self-check-questions.md](../learning/self-check-questions.md) 的指针；
> **题目与答案只存在一处**（避免两处不一致，规则见规范 §12.1）。深度原理与实测数据仍在各阶段笔记正文里。


---

## 九、与 AI 协作约定

1. **每次新对话开始时**，先让 AI 阅读本文档，再继续讨论，避免重复交代背景。
2. 说「**更新进度**」时 → 修改第六节的日期与状态。
3. 说「**记笔记**」时 → 在 [learning/tools-reference.md](../learning/tools-reference.md) 里新增/更新对应工具或依赖的小节（维护规则见规范 §12.2），并在本文档登记。
4. 说「**做项目 X**」时 → 先从空目录开始，按阶段产出推进。
5. 技术原则：
   - 先原生 API，后框架
   - 每个阶段必须有可验证产出，不接受"看完教程就算学会"
   - 涉及取舍时优先问「为什么」，而不是直接给代码
6. 用户为数学背景，讲解可适当深入到公式与数学原理层面。

---

## 十、一句话总结

**应该学，顺序为**：FastAPI / Python 工程 → 原生 LLM API → RAG（重点在检索质量与量化评估）→ Agent → 部署；同时并行刷题与大模型八股。
