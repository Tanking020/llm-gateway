# project/ —— 项目业务台账

> **这里只关于「这一个项目」。**
> 想查「做到哪了」「为什么当时这么设计」→ 看这里。
> 想学「FastAPI 原理」「索引为什么快」→ 去 [../learning/](../learning/)。

## 文件

| 文件 | 内容 | 什么时候看 |
|---|---|---|
| [roadmap.md](roadmap.md) | 学习路线 / 阶段划分 / **进度** / **待办清单（#1~#40）** | 开工前、想知道「还剩几步」 |
| [decisions.md](decisions.md) | 业务与架构决策（ADR，18 条 + 待定清单） | 要改数据结构 / 接口形状 / 部署形态**之前** |

## ⚠️ 改代码或改结构前，先查 `decisions.md`

里面已经定过的事，**别重新发明一遍**：

| 你可能想做的事 | 已有决策 | 结论 |
|---|---|---|
| 给 `Conversation.calls` 加 `cascade` | [decisions #16](decisions.md#16-计费记录不能跟着对话一起删) | ⛔ **不能加** —— 会连带删掉计费记录 |
| 把 `ConversationIn` 和 `ConversationPatch` 合并 | [decisions #10](decisions.md#10-契约按用途分家in--patch--out) | ⛔ 那个"重复"是故意的 |
| 让 `PATCH` 接受空 body | [decisions #12](decisions.md#12-patch-而不是-put且空-body-直接拒绝) | ⛔ 必填字段是免费的 bug 探测器 |
| 把引擎改成每请求新建 | [decisions #14](decisions.md#14-引擎用模块级单例并在-lifespan-里释放) | ⛔ 连接池就没意义了 |

## 两个文件的边界

| | roadmap.md | decisions.md |
|---|---|---|
| 回答 | **做到哪了** | **为什么这么做** |
| 变化频率 | 每次收口都更新 | 只在做决定时追加 |
| 新增方式 | 加一行进度 | 按五段格式加一条 ADR |

⚠️ [learning/](../learning/) 里不写「我们决定」；这里不写实测数据表格（引用 learning/）。
详见 [工程规范与协作约定.md](../../工程规范与协作约定.md) §4.4d。
