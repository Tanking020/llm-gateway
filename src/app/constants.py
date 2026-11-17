"""
跨模块共用的常量：只放"多个文件都要用，且必须保持一致"的字面量

为什么单独一个文件：
    同一个字符串写在多处的最大风险是改一处漏一处
    而且像 HTTP 头名这种"数据"拼错了，ruff / mypy 都不会报
"""

# 请求 ID 的 HTTP 头名
# 用它的三处：app.py 读请求头、app.py 回写响应头、errors.py 给 500 补响应头
HEADER_REQUEST_ID = "X-Request-ID"

# 允许跨域的前端来源（浏览器里的"源" = 协议 + 域名 + 端口，三者全同才算同源）
# 【注意】：必须写完整 origin，末尾不带斜杠；故意不写 "*" —— allow_credentials=True 时
#   写 "*" 等于对任何网站开放凭证访问
# 【注意】：放这里而不是 api/app.py —— errors.py 也要用它（500 由最外层
#   ServerErrorMiddleware 产出，不经过 CORSMiddleware，只能由处理器自己补头）
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# 鉴权凭据的 HTTP 头名
# 【注意】：必须是【自定义请求头】，不能用 Cookie —— 跨站页面发不出带自定义头的请求
#   （会先触发预检，非白名单源被拦），所以这一条同时把 CSRF 面消掉了
HEADER_API_KEY = "X-API-Key"
