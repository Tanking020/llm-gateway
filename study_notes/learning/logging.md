# 日志（logging）—— 原理、架构与写法

> **定位**：这是「日志」的**知识章节**（换任何 Python 项目都成立的原理与判据）。
> - 本项目的**落地代码**：[`src/app/logging_setup.py`](../../src/app/logging_setup.py)、[`src/app/__main__.py`](../../src/app/__main__.py)
> - 本项目**怎么改过来的**（实测对照）：[stage1-fastapi.md](stage1-fastapi.md) **§11c**
> - **为什么这么定**（方案取舍）：[project/decisions.md](../project/decisions.md) 第 24 条
>
> **最后更新**：2026-10-31

---

## 目录

| # | 内容 |
|---|---|
| 1 | [一次 `logger.info()` 走过的四道闸](#1-一次-loggerinfo-走过的四道闸) |
| 2 | [五个角色：Logger / Handler / Formatter / Filter / Level](#2-五个角色logger--handler--formatter--filter--level) |
| 3 | [Logger 是一棵树：级别继承 与 propagate 冒泡](#3-logger-是一棵树级别继承-与-propagate-冒泡) |
| 4 | [级别怎么选（语义，不是数值）](#4-级别怎么选语义不是数值) |
| 5 | [Handler：日志输出到哪](#5-handler日志输出到哪) |
| 6 | [Formatter：消息长什么样](#6-formatter消息长什么样) |
| 7 | [三种配置方式与四个关键参数](#7-三种配置方式与四个关键参数) |
| 8 | [本项目怎么接的（三层）](#8-本项目怎么接的三层) |
| 9 | [写日志的注意事项（14 条）](#9-写日志的注意事项14-条) |
| 10 | [LLM 应用该记什么](#10-llm-应用该记什么) |
| 11 | [踩坑表](#11-踩坑表) |

---

## 1. 一次 `logger.info()` 走过的四道闸

```text
logger.info("GET %s -> %s", path, status)
    │
    ├─ 闸 1：这个 logger 的有效级别允许 INFO 吗？            ← getEffectiveLevel()
    │        不允许 → 直接 return，后面的全不发生（连 %s 都不展开）
    │
    ├─ 闸 2：沿父链向上找 handler（遇到 propagate=False 就停）
    │
    ├─ 闸 3：每个 handler 自己还有级别（handler.setLevel）
    │
    └─ 闸 4：Formatter 渲染成字符串 → Handler.emit() 写到目标流
```

⭐⭐ **判据：日志"没出来"时，按这个顺序查** —— 是级别闸拦了？是没找到 handler？是 handler 级别拦了？还是写到了你看不到的地方（stderr / 文件）？

---

## 2. 五个角色：Logger / Handler / Formatter / Filter / Level

| 角色 | 一句话 | 你平时碰到的 |
|---|---|---|
| **Logger** | 你调用的入口，**有名字**，按名字组成一棵树 | `logging.getLogger(__name__)` |
| **Level** | 一个整数（DEBUG=10 / INFO=20 / WARNING=30 / ERROR=40 / CRITICAL=50） | `logger.setLevel(...)`、`level=` 参数 |
| **Handler** | **决定去哪儿**（stdout / 文件 / 网络）+ 怎么 flush | `StreamHandler` / `FileHandler` |
| **Formatter** | **决定长什么样**（时间、级别、模块名…） | `"%(asctime)s %(levelname)s %(name)s \| %(message)s"` |
| **Filter** | 更细的过滤（按字段、按请求） | 项目里还没用，按需加 |

⭐ 记忆法：**Logger 问"要不要"，Handler 问"去哪儿"，Formatter 问"长什么样"。**
三者是**独立**的三层 —— 换格式不影响去哪儿，换目标不影响要不要。

---

## 3. Logger 是一棵树：级别继承 与 propagate 冒泡

### 3.1 树

名字里的 `.` 就是层级。**📎 本项目进程里真实的树**（`import app.api.app` 之后 dump `logging.root.manager.loggerDict`）：

```text
root  ("")  level=INFO   handlers=[console]        ← 全进程唯一挂 handler 的地方
├── app                          [PlaceHolder]     ← 只是名字占位，没有 Logger 对象
│   ├── app.api                  [PlaceHolder]
│   │   └── app.api.app          [Logger] NOTSET  handlers=[]  propagate=True
│   ├── app.errors               [Logger] NOTSET  handlers=[]  propagate=True
│   └── app.llm_client           [Logger] NOTSET  handlers=[]  propagate=True
├── uvicorn                      [Logger] INFO    handlers=[]  propagate=True
│   ├── uvicorn.error            [Logger] INFO    handlers=[]  propagate=True
│   └── uvicorn.access           [Logger] WARNING handlers=[]  propagate=False  ← 到此为止
├── sqlalchemy                   [Logger] WARNING  ← 这个 level 是 SQLAlchemy 自己设的
│   ├── sqlalchemy.engine                   [PlaceHolder]
│   │   └── sqlalchemy.engine.Engine        [Logger] NOTSET → 有效级别 WARNING
│   └── sqlalchemy.pool                     [PlaceHolder]
│       └── sqlalchemy.pool.impl.AsyncAdaptedQueuePool  [Logger] NOTSET → 有效级别 WARNING
└── httpx                        [Logger] NOTSET → 有效级别 INFO（跟着 root）
```

⚠️ **这张图不是"框架自带的固定结构"，而是"此刻谁调用过 `getLogger`"的快照** —— 见 §3.4。

### 3.4 谁才会出现在这棵树上（`getLogger` 是「获取或创建」）

| 事实 | 说明 |
|---|---|
| logger **不会**自动存在 | 只有别人 `logging.getLogger("app.errors")` 调过，那个 logger 才被建出来 |
| 名字里的点只决定**父子关系** | 建 `app.api.app` 时，缺失的祖先 `app` 和 `app.api` 会以 **`PlaceHolder`** 占位：只有名字，**没有 level、没有 handler** |
| `PlaceHolder` 会不会变成真 logger | 只有当有人 `getLogger("app.api")` 或者有人在它上面设 level/handler 时 |
| 三方库也遵守这套 | 📎 `sqlalchemy.engine` / `sqlalchemy.pool` 是 **PlaceHolder**；真正的 logger 是 `sqlalchemy.engine.Engine`、`sqlalchemy.pool.impl.AsyncAdaptedQueuePool` |
| 库会自己设级别 | 📎 SQLAlchemy 源码 `log.py`：`rootlogger = getLogger("sqlalchemy"); if rootlogger.level == NOTSET: rootlogger.setLevel(WARNING)` —— 注释原话是"这样在没显式开启日志时不会打日志" |

⭐⭐ **踩坑：用 `getLogger(name)` 去"探测"logger 存不存在，等于**创建**它。**

📎 实测：

```text
探测前 'app.core' 在 loggerDict 里吗: False
logging.getLogger("app.core.probe")     ← 只为检查一下
探测后 'app.core' 在 loggerDict 里吗: True   （类型是 PlaceHolder）
```

正确查法：`logging.root.manager.loggerDict`（只读字典，不会创建任何东西），
`isinstance(obj, logging.PlaceHolder)` 判占位。

### 3.5 为什么 `sqlalchemy` 的 SQL 日志我们看不到（却没配过任何东西）

📎 `sqlalchemy` 自己 `level=WARNING`；`sqlalchemy.engine.Engine` 是 `NOTSET` → **有效级别继承最近的祖先 = WARNING**。
我们 root 是 INFO，但 INFO < WARNING，所以那些 DEBUG 级 SQL 永远出不来。
⭐ 由此得到一条实用技巧：**想临时看 SQL，只要 `logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)`**，
不需要改 `echo=True`，也不需要动我们的 `configure_logging()`。


### 3.2 两条**完全相反**的规则（最容易搞混的地方）

| | 级别（level） | Handler |
|---|---|---|
| 子 logger 没设时怎么办 | **继承**最近祖先的级别（📎 `child.level = NOTSET` 但 `getEffectiveLevel() = INFO`） | **不会**继承到自己的 `handlers` 列表里 |
| 那为什么日志还是出来了 | — | 因为 **`propagate=True`（默认）会让同一条记录继续交给祖先的 handler** |
| 查找终点 | — | 遇到某个祖先 `propagate=False` 就**停**，不再往 root 递 |

📎 实测「自己加 handler + propagate 默认 True」→ **同一条日志打出两行**：

```text
CHILD |probe.child|双输出测试      ← 自己的 handler
PARENT|probe.child|双输出测试      ← 冒泡到父 logger 的 handler
```

⭐⭐ **判据：双重输出的唯一原因是「同一行日志被两个 handler 各写了一次」** —— 要么去掉自己加的 handler，要么设 `propagate=False`。

### 3.3 用 uvicorn 的真实配置验证这套规则

📎 uvicorn 的 `LOGGING_CONFIG["loggers"]` 原样：

| logger | handlers | level | propagate |
|---|---|---|---|
| `uvicorn` | `["default"]` | INFO | **False** |
| `uvicorn.error` | *（没写）* | INFO | *（默认 True）* |
| `uvicorn.access` | `["access"]` | INFO | **False** |

读法：`uvicorn.error` **自己没有 handler**，靠 `propagate=True` 把记录交给祖先 `uvicorn` 的 `default` handler；
`uvicorn` 又 `propagate=False`，所以它**不会**再递给 root。

⚠️ 这就是为什么「uvicorn 的日志格式」和「我们的日志格式」能各自独立 —— 直到我们把 `uvicorn.*` 的
`handlers` 清空、`propagate` 改成 `True`，它才肯用 root 那个 handler（见 §8）。

---

## 4. 级别怎么选（语义，不是数值）

| 级别 | 语义 | 本项目用在哪 |
|---|---|---|
| `DEBUG` | 开发期细节（每帧数据、SQL、请求头） | 默认不开；`DEBUG=true` 时可考虑 |
| `INFO` | **正常业务流程里值得记一笔的事** | 每个请求一行（方法/路径/状态/耗时/`request_id`） |
| `WARNING` | **异常但已处理**，需要人看一眼但不一定要立刻动手 | 上游返回结构不合约定、字段被丢弃 |
| `ERROR` | **本次请求失败了**，需要人处理 | 就绪检查探库失败、流式中途出错 |
| `CRITICAL` | 进程级别不可用 | 项目未用 |

⚠️ **两条常见误用**：

| 误用 | 后果 |
|---|---|
| 正常流程打 `ERROR`（比如"用户输入不合法"） | 告警噪音 → 真故障被埋掉；错误率指标失真 |
| 该 `WARNING` 的打了 `INFO` | 线上看不出"有问题但在跑" |

📎 惰性格式化实测：`logger.debug("值=%s", Boom())`（`Boom.__str__` 会 `raise`）→ **没有抛异常**，
说明级别不够时参数**根本没被展开**。所以：

| 写法 | 级别不够时 |
|---|---|
| `logger.info("x=%s", x)` ✅ | 不拼字符串，零开销 |
| `logger.info(f"x={x}")` ❌ | **先拼好**再判断要不要输出 —— 白白付代价（拼 JSON、`repr` 大对象时很贵） |

### 4.1 📎 同一份 `Boom` 的对照实验（级别设为 WARNING，INFO 被关）

| 写法 | 结果 |
|---|---|
| `logger.info("x=%s", Boom())` | ✅ **没有异常** —— `__str__` 从未被调用 |
| `logger.info(f"x={Boom()}")` | 🔴 **抛 `RuntimeError`** —— f-string 在调用**之前**就求值，异常直接进业务代码 |

### 4.1b 📎 求值时机：字节码 + 打点时间线

**字节码（`dis.dis`，关键差别是有没有 `FORMAT_VALUE` 在 `CALL` 之前）**

```text
log.info("x=%s", x)          log.info(f"x={x}")
  LOAD_CONST 'x=%s'            LOAD_CONST 'x='
  LOAD_FAST  x                 LOAD_FAST  x
  CALL 2                       FORMAT_VALUE 0   ← 调 __format__ 变字符
                               BUILD_STRING 2   ← 拼成新字符串
                               CALL 1           ← 参数已是成品 str
```

**时间线（给 构造 / `__format__` / `__str__` / Handler / Formatter 打点）**

| 顺序 | `log.info("x=%s", Boom())` | `log.info(f"x={Boom()}")` |
|---|---|---|
| ① | `Boom()` 构造 | `Boom()` 构造 |
| ② | — | **`__format__` 被调用**，生成 `'x=<Boom>'` |
| ③ | `Logger.info` → 级别闸 → `Handler.emit` | 同左 |
| ④ | `Formatter.format`：`msg='x=%s'`、`args=(<Boom object>,)` | `Formatter.format`：`msg='x=<Boom>'`、`args=()` |
| ⑤ | **`__str__` 被调用**（`getMessage()` 里，最后） | 无（已是字符串） |

**级别关掉时**：`%s` 停在 ①（级别闸直接 return）；f-string 走完 ①②，**代价已经在闸外付掉了**。

⭐⭐ 一句话：**两边的闸位置一样（都在 `logger.info` 内部），但 f-string 的代价在闸的外面。**

**三个容易忽略的细节**

| 细节 | `%s` | f-string |
|---|---|---|
| 用哪个魔法方法 | `__str__`（`%r` 用 `__repr__`） | **`__format__`**（`!r` 用 `__repr__`） |
| 多个 handler 时格式化几次 | 📎 **每个 handler 一次**：1 / 2 / 3 个 → `__str__` 调 1 / 2 / 3 次 | 📎 **恒 1 次** |
| `record.args` | 保留原对象，可事后脱敏 / 供 JSON formatter 用 | `()`，参数身份丢了 |

⚠️ 所以 `%s` **不是"永远更快"**：级别关掉时快得多；级别开着 + 多 handler 时反而更贵（格式化 N 次）。
它稳定的优势只有两条：**级别关掉时零代价**、**参数原样保留**。

### 4.2 📎 代价量级（1 MB 字符串，INFO 关掉，各 200 次）

| 写法 | 耗时 |
|---|---|
| `logger.info("len=%s", len(big))` | **0.03 ms** |
| `logger.info(f"payload={big}")` | **66.31 ms**（**2352 倍**） |

⭐ 一行日志都没输出，却付了 66 ms 和 200 MB 临时内存。LLM 应用里最常见的踩法：
把整个上游响应体 / `messages` 列表拼进日志。

### 4.3 `%s` 只保证「不 `str()`」，不保证「不算参数」

```python
logger.debug("body=%s", await request.body())          # ❌ await 在传参时就执行了
logger.debug("rows=%s", [r.dict() for r in rows])      # ❌ 列表推导也先跑完
```

这类要加**第二道闸**：

```python
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("body=%s", await request.body())
```

### 4.4 级别**开着**时，两者还有这些差别

| | `%s` | f-string |
|---|---|---|
| 格式化时机 | 交给 `Formatter`，emit 那一步才 `msg % args` | 调用前做完 |
| 格式写错（`"%d"` 传 `str`） | `handleError` 兜住，打一行 `--- Logging error ---`，**不崩程序** | — |
| 参数的"原样" | 留在 `record.args`，JSON formatter / Sentry 能拿到结构化参数 | 只剩成品字符串 |
| 事后脱敏 | 可在 filter 里改 `record.args` | 改不了 |

⭐ 想机械拦截：ruff 的 `select` 里加 `"G"`（flake8-logging-format），`logger.info(f"…")` 会报 `G004`。

⚠️ 一个真实的坑：`logger.info(f"{request.json()}")` 这类写法在**打日志之前**就已经把 body 序列化了一遍。

---

## 5. Handler：日志输出到哪

| Handler | 输出 | 什么时候用 |
|---|---|---|
| `StreamHandler(stream=sys.stdout)` | 标准输出 | ⭐ **容器 / K8s 的标准做法**：进程只管写 stdout，平台负责收集 |
| `StreamHandler(stream=sys.stderr)` | 标准错误 | 📎 uvicorn 的 `default` handler 就是 **stderr**；`access` handler 是 **stdout** |
| `FileHandler(filename)` | 文件 | 单机脚本；⚠️ 多 worker 抢同一个文件会互踩 |
| `RotatingFileHandler` | 文件 + **按大小轮转** | 单机 + 不想磁盘被写满 |
| `TimedRotatingFileHandler` | 文件 + **按时间轮转** | 同上，按天更自然 |

### 5.1 轮转的参数含义（按大小）

| 参数 | 含义 | 典型值 |
|---|---|---|
| `maxBytes` | 单个文件多大就切 | `10 * 1024 * 1024`（10 MB） |
| `backupCount` | 保留几个历史文件（**超过就删最旧的**） | `5` → 最多占 60 MB |
| `delay` | 打开文件是否推迟到第一次写 | `True`（避免启动就建空文件） |

⭐ 没有 `backupCount` 的轮转等于没轮转（只是换了个文件继续涨）。
⚠️ **本项目现在不写文件**：只写 stdout，轮转交给平台（Docker 的 `log-opts`、K8s 的 log rotation）。
理由：写本地文件在多副本部署里既收集不到、又抢文件。

### 5.2 ⭐ 12-Factor 第 11 条：应用只写 stdout/stderr

应用只把事件流写到 **stdout/stderr**，由外部系统（journald / Docker / 云日志）负责
收集、轮转、存储。**应用自己写日志文件是反模式** —— 多副本时既收集不到，多进程还会抢同一个文件。

---

## 6. Formatter：消息长什么样

### 6.1 本项目用的格式

```text
%(asctime)s %(levelname)-7s %(name)s | %(message)s
```

| 占位符 | 输出 | 说明 |
|---|---|---|
| `%(asctime)s` | `2026-10-31 21:00:28,637` | 默认格式；要改就配 `datefmt="%Y-%m-%dT%H:%M:%S%z"` |
| `%(levelname)s` | `INFO` | |
| `%(levelname)-7s` | `INFO   ` | `-7` = **左对齐**补到 7 宽（`-` 是左对齐，正数是右对齐），让后面的列对齐 |
| `%(name)s` | `app.api.app` | logger 名（我们用 `__name__`，所以等于模块路径） |
| `%(message)s` | 你传的那句话（`%s` 已填好） | |

### 6.2 其他常用字段（需要再加）

| 字段 | 是什么 | 什么时候值得加 |
|---|---|---|
| `%(process)d` / `%(processName)s` | 进程号 | 多 worker 时区分是谁打的 |
| `%(threadName)s` | 线程名 | 有线程池时 |
| `%(pathname)s` / `%(lineno)d` / `%(funcName)s` | 文件名 / 行号 / 函数名 | 排查时很省事；但**取路径有开销**，高频日志别开 |
| `%(msecs)d` | 毫秒 | 要更细的时间 |
| `%(levelno)s` | 级别数字 | 给机器解析用 |

### 6.3 生产要 JSON

平台（Loki / ELK / CloudWatch）要的是**结构化**：`{"ts":…,"level":"INFO","logger":"app.api.app","msg":…,"request_id":…}`。
做法二选一：自定义 Formatter（内部 `json.dumps`）或 `python-json-logger`。
⚠️ 本项目**还没做**（待办 #51 的另一半），因为现在没有日志平台。

---

## 7. 三种配置方式与四个关键参数

| 方式 | 适合 | 特点 |
|---|---|---|
| `logging.basicConfig(...)` | 临时脚本、单文件 | **只在 root 没有 handler 时才生效** —— 被抢先配过就**静默失效** |
| `logging.config.dictConfig(dict)` | ⭐ 生产 | 声明式、可整体替换；支持 `force` / `disable_existing_loggers` |
| `logging.config.fileConfig(ini)` | 老项目 / 外部要求 | 要单独一个 `.ini`，不好版本管理 |

### 7.1 四个关键参数

| 参数 | 默认 | 含义 | 本项目取 |
|---|---|---|---|
| `force` | `False` | `True` = **先拆掉 root 上已有的 handler 再装**（真正的"覆盖"） | `True` |
| `disable_existing_loggers` | `True` | 把**没出现在 `loggers` 段里**的已有 logger **禁用**（`logger.disabled = True`） | `False` |
| `incremental` | `False` | `True` = 只增量更新，**不会清掉已有 handler** | 不用 |
| `version` | 必填 | 目前只有 `1` | `1` |

⭐⭐ **`disable_existing_loggers` 是最危险的默认值**：它禁的是「**配置里没提到的**那些」，不是"全部"。

📎 用与项目同结构的配置实测（保留默认 `True`）：

| logger | 在 `loggers` 段里被命名 | 结果 |
|---|---|---|
| `app.errors` | ❌ | **`disabled=True`** → 500 的 traceback 一条都不打 |
| `uvicorn.error` | ✅ | `disabled=False`（被重新配置） |
| `httpx` | ❌ | `disabled=True` |

⭐ 判据：**`app.errors` 这类"在 import 期就创建好"的 logger，最容易被这个默认值静默阉掉。**

### 7.2 配置里那两个特殊写法

| 写法 | 含义 |
|---|---|
| `"stream": "ext://sys.stdout"` | 配置是**纯数据**，写不了对象。`ext://` 前缀让 dictConfig 去 import `sys.stdout` |
| `"()": "uvicorn.logging.DefaultFormatter"` | **工厂**：dictConfig 去 import 这个可调用对象并**调用它**来构造（uvicorn 用它做彩色输出） |

⚠️ `dictConfig` 的参数类型是 `dict[str, Any]`。字面量不标注会被 mypy 推断成 `dict[str, object]` 而**报错** →
所以本项目写 `config: dict[str, Any] = {...}`。

### 7.3 幂等性：为什么要 `force=True`

📎 实测 `basicConfig` 连调两次：第二次的 `format` **完全不生效**，输出仍是第一次的 `A|hello`。

| 场景 | 不加 `force` 的结果 |
|---|---|
| 库 / 框架先配过 root | 你的配置**被忽略**（静默） |
| 自己的模块被 import 两次（reload / 测试） | 第二次配置**被忽略**（静默） |

⭐ 判据：**凡是"配置全局状态"的入口都要问「别人先配过了怎么办」** —— 不写 `force` 就等于把结果交给 import 顺序。

---

## 8. 本项目怎么接的（三层）

```text
┌ src/app/logging_setup.py ─────────────────────────────┐
│ configure_logging(): dictConfig(force=True,           │
│   disable_existing_loggers=False,                     │
│   loggers={uvicorn.*: handlers=[] propagate=True,     │
│            uvicorn.access: level=WARNING propagate=False},
│   root={console})                                     │
└───────────────────────────────────────────────────────┘
        ▲ 被谁调用？
        │
   ┌────┴──────────────────────┬──────────────────────────────┐
   │ ① app.py 模块级           │ ② __main__.py 的 main()      │
   │    覆盖：uvicorn CLI、测试 │    覆盖：reload 的【父进程】  │
   └───────────────────────────┴──────────────────────────────┘
```

| 调用点 | 覆盖哪些启动方式 | 不加会怎样 |
|---|---|---|
| `app.py` 模块级 | `python -m app`、`uvicorn app.api.app:app`、`TestClient(app)` | CLI 路径会用 uvicorn 自己的格式 |
| `__main__.py` + `log_config=None` | `reload=True` 时的 **reloader 父进程**（它**永远不 import 应用**） | 📎 父进程那 3 行退回 `INFO:     ` |

⭐ 关键认知：**"配置日志"这件事必须发生在**「所有会用日志的代码之前」—— 而不同启动方式下"之前"不是同一个位置。
这就是为什么一个项目里会出现**两个**调用点，这不是重复，是覆盖面。

---

## 9. 写日志的注意事项（14 条）

> 前 8 条是「写错就出问题」，后 6 条是「上线后才会疼」。

| # | 注意事项 | 不这么做会怎样 |
|---|---|---|
| 1 | **不要用 `print`** | 没有级别、没有时间戳、没法关、没法收集 |
| 2 | **用 `%s` 惰性格式化，不要 f-string** | 📎 级别不够时 f-string 已经付过代价了 |
| 3 | **绝不记录密钥 / 完整配置对象** | 📎 `print(pydantic对象)` 的 `repr` 会吐出全部字段；日志会被收集、搜索、转发 |
| 4 | **每行日志都能关联到请求**（`request_id`） | 用户报障时你只能靠猜 |
| 5 | **异常用 `logger.exception`，不要 `logger.error(str(exc))`** | `exception` 自动带 traceback；`str(exc)` 只剩一句话 |
| 6 | `logger.exception` **只能在 `except` 块里** | 它靠 `sys.exc_info()`；在块外调用会打 `NoneType: None` |
| 7 | **`except` 之后至少打一条** | 静默吞异常 = 最难查的 bug |
| 8 | **不要把日志当数据库** | 要统计/聚合的写库或打指标，日志是用来"看"的 |
| 9 | 级别语义要一致（见 §4） | 告警噪音 → 真故障被埋 |
| 10 | 高频日志挂 `DEBUG` | 线上日志量爆炸 |
| 11 | 日志量要有上限（轮转 / 平台侧限制） | 📎 磁盘写满 → 服务挂；这也是个 DoS 面 |
| 12 | 结构化优先：`extra={...}` 而不是把字段拼进字符串 | 拼进字符串后机器无法可靠解析 |
| 13 | 多进程 / 多 worker：**每个进程各自配** | 配置不会跨进程共享；写同一个文件会互踩 |
| 14 | 时间要能对齐（UTC / 带时区） | `asctime` 是**本地时间**；容器里常是 UTC，和本机差 8 小时 |

### 9.0 `request_id` vs `trace_id`（什么时候够用）

| | 覆盖范围 | 什么时候够用 |
|---|---|---|
| `request_id` | **一次请求、一台机器** | 单机开发 / 单服务 ✅ 本项目现在 |
| `trace_id`（W3C `traceparent`） | **一次调用链、跨多个服务** | 微服务 / 网关 + 服务 + 上游 ⬜ 上生产再补 |

多机部署要补三样：① **集中收集**（Loki / ELK / 云日志）② `trace_id` 打通服务边界
③ **结构化日志**（JSON + 固定字段 `request_id` / `path` / `status`）。

### 9.1 `extra={...}` 怎么用

```python
logger.info("上游返回", extra={"model": model, "tokens": 128})
```

⚠️ `extra` 的键**不能和 LogRecord 的已有属性重名**（`message` / `args` / `levelname` …），
否则 `KeyError: "Attempt to overwrite 'message' in LogRecord"`。
而且**默认 Formatter 不会输出 `extra` 里的字段** —— 要用 `%(model)s` 这种占位符，或改用 JSON formatter。

---

## 10. LLM 应用该记什么

| 原则 | 说明 |
|---|---|
| 日志要能关联请求 | ⭐ 配合 Step 7 的请求 ID（`X-Request-Id`） |
| 记录**耗时和 token 数** | LLM 应用必须盯成本 |
| 结构化（JSON） | 便于日志平台检索 |

> ⭐ **LLM 应用该记的字段**：`request_id`、`model`、`prompt_tokens`、`completion_tokens`、
> `latency_ms`、`ttft_ms`、`是否有缓存命中`。
> **这些都是优化产品和核算成本的原料。**
>
> ⚠️ 但**不要**把用户消息原文打进日志（隐私 / 合规），存库归存库，日志归日志。

---

## 11. 踩坑表

| 📎/⚠️ | 症状 | 原因 | 解法 |
|---|---|---|---|
| 📎 | 一屏日志**两种格式** | uvicorn 只配了 `uvicorn.*` 三个 logger，**它的 `LOGGING_CONFIG` 里没有 root** | 用 `dictConfig(force=True)` 接管，把 `uvicorn.*` 归拢到同一 handler |
| 📎 | `basicConfig` 的 `format` 不生效 | 第二次调用时 root 已有 handler → **静默跳过** | 换 `dictConfig(force=True)` |
| 📎 | `uvicorn.error` / `app.errors` 的日志突然全没了 | `disable_existing_loggers` 用了默认 `True` | 显式写 `False` |
| 📎 | 同一条日志打两行 | 自己加了 handler，`propagate` 又是默认 `True` | 二选一：删掉自己的 handler，或 `propagate=False` |
| 📎 | reload 时头几行格式不一样 | `uvicorn.run()` 没传 `log_config=None`，uvicorn 又装了一遍自己的配置 | 传 `None` |
| 📎 | 服务日志里找不到 `GET /x` 的客户端 IP | 关掉了 `uvicorn.access`（本项目待办 #56） | 在中间件那行加 `request.client.host` |
| 📎 | `logger.info` 写了但没输出 | 三道闸都可能是元凶（见 §1）；最常见是**级别**或**没有 handler** | 按 §1 的顺序查，别乱改代码 |
| 📎 | 用 `getLogger(name)` 探测 logger 存不存在，结果"探一个多一个" | `getLogger` 是**获取或创建**，不是查询 | 查 `logging.root.manager.loggerDict`；判 `PlaceHolder` |
| 📎 | 一次 500 打出**两段** traceback（以为重复了） | 不是 bug：`starlette/middleware/errors.py` 在用你的异常处理器生成响应后**又 `raise exc`** 抛回服务器 → uvicorn 打 `ERROR: Exception in ASGI application` | **你那段带 `request_id`，uvicorn 那段不带** —— 排查认准带 ID 的那段 |
| 📎 | 每行前面多出 `INFO: 127.0.0.1 - "GET ..."` | 那是 uvicorn 的 **access log**，与应用日志是两条独立通道 | 用 `dictConfig` 关掉 `uvicorn.access`（本项目做法，代价见待办 #56） |
| 📎 | PowerShell 把日志显示成红字 `NativeCommandError` | 只是"子进程往 stderr 写了东西"，不是额外错误 | 忽略，或用 `2>&1` 合并 |
| ⚠️ | 生产日志时间差 8 小时 | `asctime` 用本地时间，容器是 UTC | 统一 UTC，或配 `datefmt` 带 `%z` |

---

## 相关自检题

见 [self-check-questions.md](self-check-questions.md) **阶段 1 · Step 11**（第 9~13 题）。
