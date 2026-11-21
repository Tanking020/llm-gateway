# 接口契约（API Reference）

> **本文档是端点的唯一契约来源。** 每个端点写清：方法 / 路径 / 请求 / 成功响应 / 错误码。
> 契约的代码位置：[`src/app/schemas.py`](../src/app/schemas.py)（形状）与
> [`src/app/api/app.py`](../src/app/api/app.py)（路由）。
>
> 自动生成的交互式文档：服务启动后打开 `http://127.0.0.1:8000/docs`（仅 `APP_ENV=dev` 时开启）。
> 需鉴权的端点：先点右上角 **Authorize** 填一次 `X-API-Key`，之后 Try it out 才会带上（决策 56）。
> ⚠️ **走 compose 时入口是 nginx 的 80**（`http://127.0.0.1/docs`），宿主上的 8000 已不再发布（决策 46）。
> 形状的图形化版本（七层栈 / ER / 帧序 / 状态机）见 [architecture.md](architecture.md)。
> 端点表的变更记录见 [DEVLOG.md](DEVLOG.md)。

---

## 鉴权（13d-2 起，**每个业务端点都必须带**）

```text
X-API-Key: sk_<43 个字符>
```

| 项 | 规则 |
|---|---|
| 头名 | `X-API-Key`（常量在 `constants.HEADER_API_KEY`） |
| 库里存什么 | **只存 `sha256` 十六进制（64 位）**；明文只在签发时出现一次 |
| 怎么判定有效 | `sha256(明文)` 命中 `api_keys.key_hash` **且** `revoked_at IS NULL` |
| 失败返回 | **401** `{"error": {"code": "UNAUTHORIZED", …}}` + 响应头 `WWW-Authenticate: ApiKey` |
| 没带 / 无效 / 已撤销 | **同一句话同一个码** —— 不告诉你「这把曾经有效」 |
| 越权访问别人的对话 | **404 `CONVERSATION_NOT_FOUND`**（不是 403）—— 不确认资源存在性 |
| 为什么不用 Cookie | 自定义头会触发预检，跨站页面发不出 → **顺带免疫 CSRF**（[决策 40](decisions.md)） |
| **速率配额**（13d-4） | 按**用户**（不是按 key）计：默认 **60 次/分钟**、突发桶 **20**。超限 → **429 `RATE_LIMITED` + `Retry-After`**。⚠️ 进程内计数，`--workers N` 就是 N 倍 —— 生产上还有网关那层 |

**免鉴权端点**（否则负载均衡探测与前端取模型清单会挂）：`/health`、`/health/ready`、`/v1/models*`。

**怎么拿到一把 key（13d-5 起有 CLI，不用再手写 SQL）**：

```powershell
uv run python -m app.keys create --user alice --label laptop   # 明文只显示这一次
uv run python -m app.keys list                                 # 看 id / 用户 / 标签 / 状态 / hash 前缀
uv run python -m app.keys revoke --id 1                        # 撤销 = 打时间戳，立刻 401
```

| 规则 | 理由 |
|---|---|
| **明文只显示一次** | 库里只有 sha256，**任何人（含我们）都还原不出来**；丢了就 `revoke` 再建 |
| **`create` 找不到用户会自动建** | 13d-2 没有注册流程，key 必须挂到某个 `users` 行上 |
| **`revoke` 打时间戳不删行** | 删了就没有审计痕迹（"谁在什么时候被停的"） |
| **`revoke` 幂等、不存在的 id 退出码 1** | 脚本里重跑不该炸；但真错了必须能被 CI 看见 |

```powershell
curl.exe -s http://127.0.0.1:8000/v1/conversations -H "X-API-Key: sk_xxx"
```

---

## 端点总表

| 方法 | 路径 | 说明 | 主要状态码 | 鉴权 |
|---|---|---|---|---|
| GET | `/health` | **liveness**：只证明进程活着，**不检查外部依赖**（编排系统据此决定要不要重启） | 200 | **公开** |
| GET | `/health/ready` | **readiness**：探数据库（`SELECT 1`）；失败 → **503** `DB_UNAVAILABLE`，编排系统据此摘流量但不重启 | 200 / 503 | **公开** |
| GET | `/v1/models` | 硬编码的模型清单；支持 `?prefix=` / `?limit=`（1 ~ 100） | 200 / 422 | **公开** |
| GET | `/v1/models/latest` | 默认模型 | 200 | **公开** |
| GET | `/v1/models/{model_name}` | 单个模型；名称不在清单里 → 404 | 200 / 404 | **公开** |
| POST | `/v1/chat` | **非流式**：真调上游一次拿全正文与用量（决策 53）；最后一条消息必须是 `user`；可选 `conversation_id`（不存在**或不属于本人** → 404）；每次调用落一行账单；**同样受并发闸门约束**（顶穿 → 503 `SERVER_BUSY`） | 200 / **401** / 400 / 404 / 422 / 502 / **503** / **504** | key |
| GET | `/v1/upstream/models` | **真实调用**上游 `/models`，返回 `ModelListResponse`（**它花钱，所以必须鉴权**） | 200 / **401** / 502 / **504**（超出 `upstream_total_timeout`） | key |
| POST | `/v1/chat/stream` | **SSE 流式**：真调上游 `stream=true`，逐帧转发回答文字（思维链按产品要求丢弃）；可选 `conversation_id`（不存在**或不属于本人** → 404，**在流开始前拦**）；每次调用落一行账单 | 200 / **401** / 404 / 422 | key |
| POST | `/v1/conversations` | 新建对话（落库，**归属当前 key**）；`title` 长度 1~100 | 201 / **401** / 422 | key |
| GET | `/v1/conversations` | **游标分页**列出**自己的**对话（`?limit=1~100&after_id=N`），含账单统计；响应 `{items, total, limit, next_cursor, has_more}`，`total` 也只数自己的 | 200 / **401** / 422 | key |
| GET | `/v1/conversations/{conv_id}` | 单个对话；不存在**或不属于本人** → 404；`conv_id` 非整数 → 422 | 200 / **401** / 404 / 422 | key |
| DELETE | `/v1/conversations/{conv_id}` | 删除对话（204 无内容）；不存在**或不属于本人** → 404；⚠️ 计费记录 `SET NULL` 保留 | 204 / **401** / 404 / 422 | key |
| PATCH | `/v1/conversations/{conv_id}` | 修改标题（部分更新）；不存在**或不属于本人** → 404；空 body / null / 空串 → 422 | 200 / **401** / 404 / 422 | key |

**成功响应形状**（Step 4 起，`schemas.py` 定义，可在 `/docs` 展开）：

```jsonc
// POST /v1/chat —— 真上游；usage_tokens = 上游 total_tokens（缺字段记 0）
{"content": "你好！有什么可以帮你？", "model": "deepseek-flash", "usage_tokens": 38}

// GET /v1/upstream/models —— 上游 10 个键只暴露 3 个（白名单：owned_by / effort 等不外泄）
{"total": 2, "items": [
  {"id": "deepseek-flash", "name": "DeepSeek-V4.1-Flash", "context_window": 1048576},
  {"id": "deepseek-v4-pro", "name": "DeepSeek-V4-Pro", "context_window": 1048576}
]}

// GET /v1/conversations —— ConversationPageOut（含账单统计，join + group_by，1 条 SQL）
{"items": [{"id": 1, "title": "有账单", "created_at": "...", "updated_at": "...",
            "call_count": 2, "total_tokens": 175}],
 "total": 1, "limit": 20, "next_cursor": null, "has_more": false}
```

⚠️ **已知形状问题**（剩余待办 #39）：`/v1/models` 与 `/v1/upstream/models` 形状不一致。
~~`created_at` 带不带 `Z`~~（10.6d-4a 已统一为带 `Z`）、~~详情接口不返回 `call_count`~~（10.6d-4b 已统一为 6 字段）。
**分页方案：游标为主 + `total` 为辅**（[决策 #22](decisions.md)）——
⚠️ 不用 offset 分页，因为📎 实测它在翻页期间删数据会**漏掉一条**。

**错误响应形状**（Step 11d 起，**任何**错误都是同一种形状）：

```jsonc
// 鉴权失败（401）：没带 / 无效 / 已撤销 —— 三种情况同一句话同一个码
//   响应头额外带 WWW-Authenticate: ApiKey（RFC 9110 §15.5.2 要求）
{"error": {"code": "UNAUTHORIZED", "message": "缺少 X-API-Key 请求头", "request_id": "58d3b6cbcc94"}}

// 业务错误（400 / 404 …）：code 给机器判断（稳定不变），message 给人看（可改文案）
{"error": {"code": "LAST_MESSAGE_NOT_USER", "message": "最后一条消息必须是 user，当前是 assistant",
           "request_id": "1b085bd5c5b3"}}

// 越权访问别人的对话 → 404（与"真不存在"完全同形，不确认资源存在性）
{"error": {"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在：7", "request_id": "b12bb5a33d63"}}

// 超过速率配额（13d-4）：429 + Retry-After（整数秒，>= 1）
// 【注意】：与 UPSTREAM_RATE_LIMITED 都是 429，但责任方相反 —— 看 code 决定"等"还是"改"
{"error": {"code": "RATE_LIMITED", "message": "请求太频繁，请稍后重试", "request_id": "7f1c2a9d0e33"}}

// 框架错误：路由不存在 / 方法不允许 —— code 由状态码兜底
{"error": {"code": "NOT_FOUND", "message": "Not Found", "request_id": "a4175e01d830"}}
{"error": {"code": "METHOD_NOT_ALLOWED", "message": "Method Not Allowed", "request_id": "c5bb71007336"}}

// 参数校验失败（422）：多一个 details，只含 loc / msg / type（不回显用户提交的原值）
{"error": {"code": "VALIDATION_ERROR", "message": "请求参数校验失败", "request_id": "7284ed612708",
           "details": [{"loc": ["body", "messages"], "msg": "Field required", "type": "missing"}]}}

// 服务内部错误（500）：只回一句人话 + 请求 ID，堆栈只写服务端日志
{"error": {"code": "INTERNAL_ERROR", "message": "服务内部错误", "request_id": "ef9002e78ef3"}}
```

⭐ **客户端只需认 `code`**，不要匹配 `message`。业务码 → HTTP 状态码的映射集中在
`src/app/errors.py` 的 `_STATUS_BY_CODE`，所有错误响应经同一个出口 `_error_response()` 生成，
`X-Request-ID` 响应头**恒等于** body 里的 `request_id`。

**全部业务码（16 个，📎 从 `_STATUS_BY_CODE` 实读）** —— 「谁的责任」决定客户端该**等**、**改**还是**重试**：

| 状态码 | `code` | 什么时候出现 | 客户端该做什么 |
|---|---|---|---|
| 400 | `LAST_MESSAGE_NOT_USER` | 最后一条消息不是 `user` | 改请求 |
| 400 | `INVALID_MAX_TOKENS` | `max_tokens` 非正 / 超上限 | 改小 |
| 401 | `UNAUTHORIZED` | 没带 / 无效 / 已撤销的 `X-API-Key`（响应带 `WWW-Authenticate`） | 换 key |
| 404 | `MODEL_NOT_FOUND` | `/v1/models/{name}` 的名字不在清单里 | 改名字 |
| 404 | `CONVERSATION_NOT_FOUND` | 对话不存在**或不属于本人**（同形，不确认存在性） | 别重试 |
| 413 | `UPSTREAM_PAYLOAD_TOO_LARGE` | **上游**说请求体太大 | 缩短内容 |
| 429 | `RATE_LIMITED` | **我们**限这个客户端（按 `user.id`） | 等 `Retry-After` |
| 429 | `UPSTREAM_RATE_LIMITED` | **上游**限我们 | 等 `Retry-After` |
| 502 | `UPSTREAM_UNREACHABLE` | 上游根本没回应（DNS / TCP / TLS 失败） | 稍后重试 |
| 502 | `UPSTREAM_AUTH_FAILED` | **我们的**上游密钥坏了 | 重试无用，报障 |
| 502 | `UPSTREAM_REJECTED` | 上游拒收我们发的 body | 重试无用，报障 |
| 502 | `UPSTREAM_BAD_STATUS` | 上游回了意料外的 3xx / 5xx（兜底） | 5xx 可重试 |
| 502 | `UPSTREAM_MALFORMED` | 上游 200 但 body 不是约定结构（HTML / 空 / 字段改名） | 重试无用，报障 |
| 503 | `DB_UNAVAILABLE` | 数据库连不上（**不是** `no such table`，那是我们的 bug） | 等 |
| 503 | `SERVER_BUSY` | 我方并发闸门顶穿（不是「你请求太多」—— 那是 429） | 等 `Retry-After` |
| 504 | `UPSTREAM_TIMEOUT` | 超出 `upstream_total_timeout` 的总时长预算 | 缩短问题后重试 |
| 500 | `INTERNAL_ERROR` | **我们的** bug（没有对应业务码时兜底） | 报障，附 `request_id` |

📌 429 有**两个**码但责任方相反：`RATE_LIMITED` = 你太多，`UPSTREAM_RATE_LIMITED` = 上游限我们。

> ✅ **反代层（nginx）自己产生的错误现在也是同一个形状**（#89 / 决策 52）。
> 上面那张表是**应用**产生的；下表是**代理**产生的 —— 它们不经过应用，所以没有 `details`，
> 但信封、`X-Request-ID` 头、CORS 头与上表完全一致，客户端可以走同一套解析代码。
>
> | 层 | 状态码 | `code` | 什么时候出现 | 客户端该做什么 |
> |---|---|---|---|---|
> | 反代 | 413 | `PAYLOAD_TOO_LARGE` | 请求体超过 **1 MB**（`client_max_body_size`）。⚠️ 与上表的 `UPSTREAM_PAYLOAD_TOO_LARGE` 不同：那个是**上游**嫌大 | 缩短内容 |
> | 反代 | 502 | `BAD_GATEWAY` | 连应用被**拒绝**（app 进程没在听 8000） | 稍后重试，指数退避 |
> | 反代 | 504 | `GATEWAY_TIMEOUT` | 📎 实测两种情况都落这里：① 应用在 130 s 内没回完（`proxy_read_timeout`）；② 容器停掉后 TCP 握手**超时**（SYN 被丢弃，见待办 [#92](todos.md)） | 同上；② 说明实例已下线 |
>
> 📎 **两种 413 的区别（别混）**：`200 KB` 请求体（> 20000 字符）由**应用**回 **422 `VALIDATION_ERROR`**；
> `2 MB` 请求体由 **nginx** 回 **413 `PAYLOAD_TOO_LARGE`**。前者是业务字段超长、后者是协议层体积上限。


> ✅ 流式接口在 `/docs` 里已正确标成 `text/event-stream`（Step 11f：`SseResponse` 的类属性 `media_type` +
> `response_class=`；只加 `responses={200: …}` 不够，会把 `application/json` 一起留着）。

**SSE 流式响应**（Step 9b-3 起：真调上游 `stream=true`，含状态帧与用量记账）：

请求体与 `POST /v1/chat` 共用同一份契约（`ChatRequest`）。一帧 = `data: <内容>` + **一个空行**（`\n\n`）。实测响应：

```text
HTTP/1.1 200 OK
cache-control: no-cache
x-accel-buffering: no
content-type: text/event-stream; charset=utf-8
transfer-encoding: chunked

data: {"status": "thinking"}          ← 连上立刻发（实测 60ms），不等上游

data: {"delta": "1"}

data: {"delta": " "}

data: {"delta": "2"}

……

data: {"finish_reason": "stop"}       ← 为什么结束（"stop" 说完 / "length" 被截断）

data: {"usage": {"prompt_tokens": 44, "completion_tokens": 63, "total_tokens": 107,
                 "completion_tokens_details": {"reasoning_tokens": 57},
                 "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 44}}

data: [DONE]
```

**五类帧的分工**（我方对外只发这 5 类 + 1 类错误帧）：

| 帧 | 何时发 | 谁用 |
|---|---|---|
| `{"status": "thinking"}` | 请求开始，**在请求上游之前** | 前端显示"思考中"，避免空白期 |
| `{"delta": "..."}` | 上游每吐一个 token | 正文逐字显示 |
| `{"finish_reason": "..."}` | 上游最后一帧 | 区分正常结束 / 被截断（`length`） |
| `{"usage": {...}}` | 上游最后一帧 | 成本计量（含思维链 token） |
| **`{"error": {"code": "STREAM_NO_CONTENT", ...}}`** | 上游**一帧内容都没给**（200 + HTML / 空 body / 忽略 `stream`） | 区分「模型说了空」与「上游没给」——**`response.ok` 是 `true`，前端必须识别这一帧** |
| **`{"error": {"code": "STREAM_TIMEOUT", ...}}`** | 超出 `upstream_total_timeout`（上游「慢速滴答」被掐断） | 提示「上游太慢」；建议缩短问题后重试（不是简单重发） |
| **`{"error": {"code": "STREAM_FAILED", ...}}`** | 流**中途**出错（坏 JSON / 不可预期的结构） | 同上；**已收到的 `DELTA` 要保留**，但要提示「回答可能不完整」 |
| `[DONE]` | 我方在流末尾**统一发一次** | 前端据此关闭连接 |

⚠️ **流式接口的 `200` 也可能是失败**：响应头一旦发出就改不了状态码，
所以「上游挂了」在流式下只能表达成 **200 + `error` 帧**；而真正的 L1/L2（连不上 / 状态码不对）
已在 **pre-flight** 阶段拦成 **502**（`response.ok === false`）。

**上游 5 类 → 我方 5 类的映射**（正常路径；📎 实测问「从1数到3」：上游 64 帧 → 我方 9 帧）：

| 上游帧 | 数量 | 我方动作 | 我方帧 |
|---|---|---|---|
| `ROLE`（首帧，`delta.role=assistant`） | 1 | 丢弃（`content` 是 `null`） | — |
| `REASONING`（`reasoning_content` 有值） | **56** | 丢弃（产品只显示回答） | — |
| `CONTENT`（`content` 有值） | 5 | 重组为 `{"delta": text}` | `DELTA` |
| `FINISH`（`finish_reason` + `usage` **同帧**） | 1 | **拆成 2 帧** | `FINISH_REASON` + `USAGE` |
| `[DONE]` | 1 | 只用来跳过，**由我方重发** | `DONE` |
| —（我方自造） | — | 在请求上游之前发出 | `THINKING` |

> ⭐ 算一遍：64 − 57（丢弃 ROLE + 思维链）+ 1（THINKING）+ 1（FINISH 拆成 2 帧）= **9** ✅
> 帧的分类与顺序详见[阶段1 笔记](../notes/stage1-fastapi.md) §9.8d。

```powershell
# 请求体写进临时文件（含中文，避免 PowerShell 转义把 JSON 弄坏）
$body = '{"messages":[{"role":"user","content":"从1数到5，只输出数字，用空格隔开"}]}'
[IO.File]::WriteAllText("$env:TEMP\chat_stream.json", $body, (New-Object System.Text.UTF8Encoding($false)))

# 逐帧看内容（-N = 关掉 curl 自己的输出缓冲，否则看不到"逐字"）
# 【注意】：13d-2 起必须带 X-API-Key，否则 401
curl.exe -N -s -X POST http://127.0.0.1:8000/v1/chat/stream `
  -H "Content-Type: application/json" -H "X-API-Key: $env:API_KEY" --data-binary "@$env:TEMP\chat_stream.json"

# 只看响应头，丢弃 body
curl.exe -s -D - -o NUL -X POST http://127.0.0.1:8000/v1/chat/stream `
  -H "Content-Type: application/json" -H "X-API-Key: $env:API_KEY" --data-binary "@$env:TEMP\chat_stream.json"

Remove-Item "$env:TEMP\chat_stream.json"
```

> 🔴 **时序不能用 `curl -w` 的 `ttfb/total` 判**：`time_starttransfer` 量的是**响应头到达**，
> 而流式接口的头是路由立刻发出的（实测 8.9ms）。要证明"内容在流"，必须用**带时间戳的客户端**
> （httpx `iter_text()` + `perf_counter`）量首个数据帧时刻。详见[阶段1 笔记](../notes/stage1-fastapi.md) §9.3b ③。
>
> ⚠️ `TestClient` 里的 `transfer-encoding` 是 `None` —— 它能验证**帧格式**，证明不了"分批发送"。
> 时序必须用真 uvicorn + 真 HTTP 客户端。

**首帧延迟的前后对比**（📎 同一接口实测）：

| 版本 | 首个 body 帧 | 总耗时 | 占比 |
|---|---|---|---|
| 9b-2（无状态帧） | 845.8ms | 905.7ms | **93%** |
| **9b-3（加 `thinking` 帧）** | **60.0ms** | 906ms | **6.6%** |

**流式的已知限制**（已补齐的两条保留在此，作为「原样记录」）：

| 限制 | 表现 | 现状 |
|---|---|---|
| 上游报错时状态码改不了 | 客户端看到 `200` + 断连（头早已发出） | ✅ 已补（9b-4）：**pre-flight** 在开流前先探上游，L1/L2 → **502**；流内错误用 `error` 帧表达 |
| 客户端断开未处理 | 用户走了仍在烧 token | ✅ 已补（9b-4）：📎 实测 `aclose()` 让上游 **4ms 内停止生成**（40 帧只发出 3 帧）；账单落 `aborted` |
| 窗口外的在途流会被切断 | 发版时若 30s 内没跑完 | ✅ 已表达（13c-5，决策 39）：连接关闭、**无 `[DONE]`**，前端必须按「流断了」处理 |

**请求追踪**（Step 7a 起）：每个响应都带 `X-Request-ID` 头。

> ⭐ **经过 nginx（容器形态）时，ID 由边界决定**（#98 / [决策 57](decisions.md)）：
> 客户端传的 ID 若匹配 `^[A-Za-z0-9._:-]{1,64}$` 就**原样沿用**；否则（含空格 / 引号 / 换行 / 超长）
> **静默替换**成 nginx 生成的 32 位 hex。三种情况下 **`x-request-id` 响应头 == nginx access log 的 `rid=` == 应用日志的 `request_id`**，
> 包括 413/502/504 这类反代层自己产生的错误。
> ⚠️ 开发者直连 `python -m app`（8000，无 nginx）时没有这一层：不带 ID 会得到应用生成的 **12 位** hex —— 格式不同但语义相同。

```text
# 客户端可自带 ID，服务端会原样沿用（跨服务串联用）
curl.exe -i http://127.0.0.1:8000/health -H "X-Request-ID: my-trace-001"
#   -> x-request-id: my-trace-001

# 不带就自动生成；500 时响应头与响应体里的 request_id 完全相同
# 服务端每个请求都有一行【JSON】访问日志（13e-2，决策 48）：
#   {"ts": "2026-11-19T12:34:20.117+00:00", "level": "INFO", "logger": "app.api.app",
#    "msg": "request", "method": "GET", "path": "/v1/upstream/models", "status": 200,
#    "duration_ms": 157.7, "client": "203.0.113.7", "request_id": "c68615732f4e"}
#   异常路径上 status 是字符串 "ERR"（此时还没有响应对象）
# 【注意】：client 是「TCP 对端 + 可信代理写的 X-Forwarded-For」解析后的结果（决策 47），
#   不是邮件头里那串原文 —— 原文可被客户端伪造
```

**手工验证**（PowerShell 里 `curl` 是 `Invoke-WebRequest` 的别名，必须写 `curl.exe`）：

```powershell
# 【注意】：13d-2 起业务端点必须带 X-API-Key（否则 401）；/health 与 /v1/models* 免鉴权
$env:API_KEY = "sk_xxx"   # 用 `uv run python -m app.keys create --user alice` 签发（明文只显示一次）

curl.exe -s -i http://127.0.0.1:8000/health                                        # 200（免鉴权）
curl.exe -s -i http://127.0.0.1:8000/v1/models/deepseek-flash                       # 200（免鉴权）
curl.exe -s -i http://127.0.0.1:8000/v1/models/does-not-exist                       # 404
curl.exe -s -i http://127.0.0.1:8000/v1/conversations                               # 401（没带 key）
curl.exe -s -i http://127.0.0.1:8000/v1/conversations -H "X-API-Key: $env:API_KEY"  # 200

# 请求体含中文时写进临时文件，避免 PowerShell 转义把 JSON 弄坏
$body = '{"messages":[{"role":"user","content":"你好"}]}'
[IO.File]::WriteAllText("$env:TEMP\chat.json", $body, (New-Object System.Text.UTF8Encoding($false)))
curl.exe -s -i -X POST http://127.0.0.1:8000/v1/chat -H "Content-Type: application/json" -H "X-API-Key: $env:API_KEY" --data-binary "@$env:TEMP\chat.json"
```

---

