"""
跨模块共用的常量：只放"多个文件都要用，且必须保持一致"的字面量

为什么单独一个文件：
    同一个字符串写在多处的最大风险是改一处漏一处
    而且像 HTTP 头名这种"数据"拼错了，ruff / mypy 都不会报
"""

# 请求 ID 的 HTTP 头名
# 用它的三处：app.py 读请求头、app.py 回写响应头、errors.py 给 500 补响应头
HEADER_REQUEST_ID = "X-Request-ID"
