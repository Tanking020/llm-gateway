"""
业务异常与统一错误响应: 错误码在这里定义，HTTP 状态码在这里映射

用于解决错误响应形状不统一的问题（detail 是自由文本，没法机器判断）

为什么要单独一个文件：
    抛异常的地方（服务层 / 路由）只需要说清"出了什么业务错误"
    不需要知道该回 400 还是 409 —— 这个映射集中一处，改规则只改这里
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务规则不允许：携带 【稳定错误码】 + 【给人看的说明】"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# 错误码 -> HTTP 状态码。没登记的码默认 400（"你的请求有问题"这一类）
_STATUS_BY_CODE: dict[str, int] = {
    "LAST_MESSAGE_NOT_USER": status.HTTP_400_BAD_REQUEST,
}


def register_exception_handlers(app: FastAPI) -> None:
    """把 AppError 的翻译器挂到 app 上（在 app 创建后调用一次）"""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        http_status = _STATUS_BY_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
        return JSONResponse(
            status_code=http_status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
