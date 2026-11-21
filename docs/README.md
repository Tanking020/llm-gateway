# docs/ —— 项目文档

> **面向「想了解 / 接手 / 维护这个项目」的人。**
> 换一个项目也成立的知识（FastAPI 原理、索引为什么快）在 [../notes/](../notes/)。

## 文件

| 文件 | 回答什么 | 什么时候看 | 变化频率 |
|---|---|---|---|
| [DEVLOG.md](DEVLOG.md) | **什么时候做了什么、凭什么认为做对了、踩了什么坑** | 查历史、交接、复盘 | 每次收口追加 |
| [todos.md](todos.md) | **还没做完的事**（`#N` 编号的唯一事实来源） | 开工前、排优先级 | 每次收口 |
| [roadmap.md](roadmap.md) | **现在在哪、下一步做什么** | 想知道下一步 | 每阶段 |
| [decisions.md](decisions.md) | **为什么这么设计、放弃了什么、何时该重审** | **改数据结构 / 接口形状 / 部署形态之前** | 做决定时 |
| [architecture.md](architecture.md) | **长什么样**：七层栈 / 模块依赖 / ER+DDL / 端点总表 / 成功·错误·SSE 形状 / 配置 / 日志 / 状态机 | 弄清「这个请求经过哪几层」「这个字段从哪来」 | 随提问增补 |
| [api.md](api.md) | **端点契约**：请求 / 成功响应真实样本 / 错误码 / SSE 帧 | 对接前端、联调 | 加端点时 |
| [loadtest-record.md](loadtest-record.md) | **压测数据记录表单**：前置条件 / 数据 / 判定 / 结论 四节 + 陷阱自查 + 13f 样本 | 要压测、要对比历史结果 | 每次压测 |
| [production-readiness.md](production-readiness.md) | **距离上线还差什么**：七道门 + 档期 + 过门判据 | 排优先级、准备评审 | 每次评审 |
| [step13-closeout.md](step13-closeout.md) | **Step 13 收口报告**（2026-11-21 快照）：交付清单 / 七道门 / 数字总表 / 未做清单 / 评审可讲的三件事 | 回顾部署阶段、准备评审 | 一次性快照，不追加 |
| [ai-collaboration.md](ai-collaboration.md) | **AI 怎么协作**：步骤卡格式、讲解顺序、批改机制、边界、触发词 | 定协作方式时 | 学习者定新规则时 |
| [tool-approval.md](tool-approval.md) | **哪些操作用 AI 动手前要确认**：两层模型（工具批准 / 编辑接受）、危险与安全清单、当前设置与回滚 | 觉得「点得太频繁」或想收紧安全时 | 改审批设置时 |
| [dev-environment.md](dev-environment.md) | **本机命令与环境的硬规则**：PowerShell 5.1 四条硬规则、编码陷阱、本机缺哪些工具 | 写命令 / 排查编码问题时 | 换机器或装新工具时 |

## 边界：谁写什么、谁不写什么

| | DEVLOG | todos | decisions | architecture | notes/ |
|---|---|---|---|---|---|
| 回答 | 做了什么 | **还剩什么** | **为什么** | 长什么样 | **换个项目也对吗** |
| 不写什么 | 不写原理推导（→ `notes/`） | 不复述证据（→ DEVLOG） | 不写实测数据表（→ `notes/`） | 不写设计理由（→ decisions） | 不写「我们决定…」（→ decisions） |

⚠️ **单一真相**：一条事实只在一个文件里展开，其它地方**只引用编号**（`#38` / `决策 28` / `坑 K7` / `1.138`）。
判据：**改一处会不会漏另一处？** 会 → 说明写重复了。

## 改代码或改结构前，先查 [decisions.md](decisions.md)

里面已经定过的事，**别重新发明一遍**：

| 你可能想做的事 | 已有决策 | 结论 |
|---|---|---|
| 给 `Conversation.calls` 加 `cascade` | [决策 16](decisions.md) | ⛔ **不能加** —— 会连带删掉计费记录 |
| 把 `ConversationIn` 和 `ConversationPatch` 合并 | [决策 10](decisions.md) | ⛔ 那个「重复」是故意的 |
| 让 `PATCH` 接受空 body | [决策 12](decisions.md) | ⛔ 必填字段是免费的 bug 探测器 |
| 把引擎改成每请求新建 | [决策 14](decisions.md) | ⛔ 连接池就没意义了 |
| 给 `LlmCall` 写 `conversation_id: int` | [决策 16](decisions.md) | 必须 `int \| None` —— 📎 写 `int` 就是 500 |
| 在每条路由里各写一遍「对话不存在 → 404」 | [决策 8](decisions.md) | ⛔ 抽成 `require_conversation`，5 处共用 |
| 把记账的 `await db.commit()` 换回 `flush()`「少提交一次」 | [决策 28](decisions.md) | ⛔ 写锁横跨整条流 → 并发流串行化（📎 4 条并发 0.71s → 2.60s） |
| 把零内容收尾的状态改回 `aborted`「少一个值」 | [决策 27](decisions.md) | ⛔ 把「用户走了」和「上游坏了」混成一个值 |

## 编号规则（引用时用这几套，别自己发明）

| 前缀 | 含义 | 定义在哪 |
|---|---|---|
| `12a` / `10.6b-2` | **工作单元**（一次交付的原子单位） | [DEVLOG.md](DEVLOG.md) §一 |
| `1.138` / `0.22` | **流水**（按时间的一条记录，终身不重号） | [DEVLOG.md](DEVLOG.md) §二 |
| `#38` | **待办** | [todos.md](todos.md) |
| `决策 28` | **ADR** | [decisions.md](decisions.md) |
| `坑 K7` | **踩坑条目** | [DEVLOG.md](DEVLOG.md) §三 |
| `P0` / `P1` / `P2` / `P3` | **档期** | [production-readiness.md](production-readiness.md) |

> 要**写或改测试**、排查**并发与连接池**，看 [../tests/README.md](../tests/README.md)
> （21 个文件各测哪层 / 怎么读覆盖率 / **两个连接池谁占谁**）。
