# project/ —— 项目业务台账

> **这里只关于「这一个项目」。**
> 想查「做到哪了」「为什么当时这么设计」→ 看这里。
> 想学「FastAPI 原理」「索引为什么快」→ 去 [../learning/](../learning/)。

## 文件

| 文件 | 内容 | 什么时候看 |
|---|---|---|
| [roadmap.md](roadmap.md) | 学习路线 / 阶段划分 / **进度（一张表 79 行，按时间顺序）** / **待办清单（#1~#74）** | 开工前、想知道「还剩几步」 |
| [decisions.md](decisions.md) | 业务与架构决策（ADR，28 条 + 待定清单） | 要改数据结构 / 接口形状 / 部署形态**之前** |
| [production-readiness.md](production-readiness.md) | **生产级自检**：七道门（测试 / 安全 / 容量 / 成本 / 可观测 / 可交付 / 数据治理）+ 档期 `P0/P1/P2` + 过门判据 | 排优先级、判断「能不能上线了」、准备面试 |
| [architecture-map.md](architecture-map.md) | **各种关系与形状的图**：请求穿过的七层 / 模块依赖 / lifespan / ER+DDL / 端点总表 / 成功·错误·SSE 的完整形状 / **§8.6 流式完整时序（含账单状态机与每个时刻的故障）** / 配置 / 日志 / 测试 / 状态机 | 想弄清「这个请求经过哪几层」「出错时前端拿到什么」「这个字段从哪来」 |

> 📌 要**写/改测试**或排查**并发与连接池**，去看 [tests/README.md](../../tests/README.md)（8 个文件各测哪层 / 怎么读覆盖率 / **两个连接池谁占谁**）。那里不重复本目录的任何内容。

## ⚠️ 改代码或改结构前，先查 `decisions.md`

里面已经定过的事，**别重新发明一遍**：

| 你可能想做的事 | 已有决策 | 结论 |
|---|---|---|
| 给 `Conversation.calls` 加 `cascade` | [decisions #16](decisions.md#16-计费记录不能跟着对话一起删) | ⛔ **不能加** —— 会连带删掉计费记录 |
| 把 `ConversationIn` 和 `ConversationPatch` 合并 | [decisions #10](decisions.md#10-契约按用途分家in--patch--out) | ⛔ 那个"重复"是故意的 |
| 让 `PATCH` 接受空 body | [decisions #12](decisions.md#12-patch-而不是-put且空-body-直接拒绝) | ⛔ 必填字段是免费的 bug 探测器 |
| 把引擎改成每请求新建 | [decisions #14](decisions.md#14-引擎用模块级单例并在-lifespan-里释放) | ⛔ 连接池就没意义了 |
| 给 `LlmCall` 写 `conversation_id: int` | [decisions #16](decisions.md#16-计费记录不能跟着对话一起删) | 必须 `int \| None` —— 📎 写 `int` 就是 500 |
| 在每条路由里各写一遍「对话不存在 → 404」 | [decisions #8](decisions.md#8-业务规则抽成函数由多条路由共用) | ⛔ 抽成 `require_conversation`，5 处共用 |
| 把记账的 `await db.commit()` 换回 `flush()`「少提交一次」 | [decisions #28](decisions.md#28-两阶段记账的两次写入都用-commit不用-flush) | ⛔ 写锁会横跨整条流 → 并发流串行化（📎 4 条并发 0.71s → 2.60s） |
| 把零内容收尾的状态改成 `aborted`「少一个值」 | [decisions #27](decisions.md#27-账单-status-只表达金额准不准四态值域用-strenum) | ⛔ 把「用户走了」和「上游坏了」混成一个值 |

## 四个文件的边界

| | roadmap.md | decisions.md | production-readiness.md | architecture-map.md |
|---|---|---|---|---|
| 回答 | **做到哪了** | **为什么这么做** | **距离上线还差什么** | **长什么样** |
| 变化频率 | 每次收口都更新 | 只在做决定时追加 | 每次收口重推一遍门的颜色 | 想弄清一个形状时 |
| 新增方式 | 加一行进度 / 加一条待办编号 | 按五段格式加一条 ADR | 先在 roadmap 登记编号，再挂到门下 | 加一节「图 + 真实样本」 |
| **不写什么** | 不写原理与实测（→ learning/） | 不写实测数据表格（引用 learning/） | **不写缺陷细节与实测数字**（引用 roadmap 的编号与 📎 证据） | 不写「为什么这么设计」（→ decisions）、不写推导过程（→ learning） |

⚠️ [learning/](../learning/) 里不写「我们决定」；这里不写实测数据表格（引用 learning/）。
详见 [工程规范与协作约定.md](../../工程规范与协作约定.md) §4.4d。

## 待办编号的唯一事实来源

**缺陷的编号、现状证据、📎 实测数字全部只在 [roadmap.md](roadmap.md) 的待办表里。**
`production-readiness.md` 与 `decisions.md` 只**引用编号**，不复述内容 ——
否则「一个问题两处描述」，改一处必漏另一处（规范 §4.6）。
