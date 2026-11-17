# 接口契约（API Reference）

> **本文档是端点的唯一契约来源。** 每个端点写清：方法 / 路径 / 请求 / 成功响应 / 错误码。
> 契约的代码位置：[`src/app/schemas.py`](../src/app/schemas.py)（形状）与
> [`src/app/api/app.py`](../src/app/api/app.py)（路由）。
>
> 自动生成的交互式文档：服务启动后打开 `http://127.0.0.1:8000/docs`（仅 `APP_ENV=dev` 时开启）。
> 形状的图形化版本（七层栈 / ER / 帧序 / 状态机）见 [architecture.md](architecture.md)。
> 端点表的变更记录见 [DEVLOG.md](DEVLOG.md)。

---

## 端点总表

| 方法 | 路径 | 说明 | 主要状态码 |
|---|---|---|---|
| GET | `/health` | **liveness**：只证明进程活着，**不检查外部依赖**（编排系统据此决定要不要重启） | 200 |
| GET | `/health/ready` | **readiness**：探数据库（`SELECT 1`）；失败 → **503** `DB_UNAVAILABLE`，编排系统据此摘流量但不重启 | 200 / 503 |
| GET | `/v1/models` | 硬编码的模型清单；支持 `?prefix=` / `?limit=`（1 ~ 100） | 200 / 422 |
| GET | `/v1/models/latest` | 默认模型 | 200 |
| GET | `/v1/models/{model_name}` | 单个模型；名称不在清单里 → 404 | 200 / 404 |
| POST | `/v1/chat` | 聊天；⚠️ **业务逻辑仍为 `echo` 占位**（待办 #46）；最后一条消息必须是 `user`；可选 `conversation_id`（不存在 → 404） | 200 / 400 / 404 / 422 |
| GET | `/v1/upstream/models` | **真实调用**上游 `/models`，返回 `ModelListResponse` | 200 / 502 / **504**（超出 `upstream_total_timeout`） |
| POST | `/v1/chat/stream` | **SSE 流式**：真调上游 `stream=true`，逐帧转发回答文字（思维链按产品要求丢弃）；可选 `conversation_id`（不存在 → 404，**在流开始前拦**）；每次调用落一行账单 | 200 / 404 / 422 |
| POST | `/v1/conversations` | 新建对话（落库）；`title` 长度 1~100 | 201 / 422 |
| GET | `/v1/conversations` | **游标分页**列出对话（`?limit=1~100&after_id=N`），含账单统计；响应 `{items, total, limit, next_cursor, has_more}` | 200 / 422 |
| GET | `/v1/conversations/{conv_id}` | 单个对话；不存在 → 404；`conv_id` 非整数 → 422 | 200 / 404 / 422 |
| DELETE | `/v1/conversations/{conv_id}` | 删除对话（204 无内容）；不存在 → 404；⚠️ 计费记录 `SET NULL` 保留 | 204 / 404 / 422 |
| PATCH | `/v1/conversations/{conv_id}` | 修改标题（部分更新）；不存在 → 404；空 body / null / 空串 → 422 | 200 / 404 / 422 |

**成功响应形状**（Step 4 起，`schemas.py` 定义，可在 `/docs` 展开）：

```jsonc
// POST /v1/chat（⚠️ echo 占位）
{"content": "[echo] 你好", "model": "deepseek-flash", "usage_tokens": 0}

// GET /v1/upstream/models —— 上游 10 个键只暴露 3 个（白名单：owned_by / effort 等不外泄）
{"total": 2, "items": [
  {"id": "deepseek-flash", "name": "DeepSeek-V4.1-Flash", "context_window": 1048576},
  {"id": "deepseek-v4-pro", "name": "DeepSeek-V4-Pro", "context_window": 1048576}
]}

// GET /v1/conversations —— 含账单统计（join + group_by，1 条 SQL）
[{"id": 1, "title": "有账单", "created_at": "...", "updated_at": "...",
  "call_count": 2, "total_tokens": 175}]
```

⚠️ **已知形状问题**（剩余待办 #39）：`/v1/models` 与 `/v1/upstream/models` 形状不一致。
~~`created_at` 带不带 `Z`~~（10.6d-4a 已统一为带 `Z`）、~~详情接口不返回 `call_count`~~（10.6d-4b 已统一为 6 字段）。
**分页方案：游标为主 + `total` 为辅**（[决策 #22](decisions.md)）——
⚠️ 不用 offset 分页，因为📎 实测它在翻页期间删数据会**漏掉一条**。

**错误响应形状**（Step 11d 起，**任何**错误都是同一种形状）：

```jsonc
// 业务错误（400 / 404 …）：code 给机器判断（稳定不变），message 给人看（可改文案）
{"error": {"code": "LAST_MESSAGE_NOT_USER", "message": "最后一条消息必须是 user，当前是 assistant",
           "request_id": "1b085bd5c5b3"}}

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
curl.exe -N -s -X POST http://127.0.0.1:8000/v1/chat/stream `
  -H "Content-Type: application/json" --data-binary "@$env:TEMP\chat_stream.json"

# 只看响应头，丢弃 body
curl.exe -s -D - -o NUL -X POST http://127.0.0.1:8000/v1/chat/stream `
  -H "Content-Type: application/json" --data-binary "@$env:TEMP\chat_stream.json"

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

**流式的已知限制**（下一步要补）：

| 限制 | 表现 | 归属 |
|---|---|---|
| 上游报错时状态码改不了 | 客户端看到 `200` + 断连（头早已发出） | 9b-4：在开始流**之前**判断上游状态 |
| 客户端断开未处理 | 用户走了仍在烧 token | 9b-4 |

**请求追踪**（Step 7a 起）：每个响应都带 `X-Request-ID` 头。

```text
# 客户端可自带 ID，服务端会原样沿用（跨服务串联用）
curl.exe -i http://127.0.0.1:8000/health -H "X-Request-ID: my-trace-001"
#   -> x-request-id: my-trace-001

# 不带就自动生成；500 时响应头与响应体里的 request_id 完全相同
# 服务端每个请求都有一行访问日志：
#   GET /v1/upstream/models -> 200 157.7ms request_id=c68615732f4e
#   GET /__boom -> ERR 1.1ms request_id=9af3ecfbb812      （ERR = 异常路径上还没有响应对象）
```

**手工验证**（PowerShell 里 `curl` 是 `Invoke-WebRequest` 的别名，必须写 `curl.exe`）：

```powershell
curl.exe -s -i http://127.0.0.1:8000/v1/models/deepseek-flash          # 200
curl.exe -s -i http://127.0.0.1:8000/v1/models/does-not-exist          # 404

# 请求体含中文时写进临时文件，避免 PowerShell 转义把 JSON 弄坏
$body = '{"messages":[{"role":"user","content":"你好"}]}'
[IO.File]::WriteAllText("$env:TEMP\chat.json", $body, (New-Object System.Text.UTF8Encoding($false)))
curl.exe -s -i -X POST http://127.0.0.1:8000/v1/chat -H "Content-Type: application/json" --data-binary "@$env:TEMP\chat.json"
```

---

