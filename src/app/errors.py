"""
业务异常与统一错误响应: 错误码在这里定义，HTTP 状态码在这里映射

用于解决错误响应形状不统一的问题（detail 是自由文本，没法机器判断）

为什么要单独一个文件：
    抛异常的地方（服务层 / 路由）只需要说清"出了什么业务错误"
    不需要知道该回 400 还是 409 —— 这个映射集中一处，改规则只改这里

待办：目前只考虑单机部署，若后续要多机部署要做日志收集系统
"""

# logging: 标准库【日志】模块。用它而不是 print —— 能带级别、时间、模块名，且可配置输出到文件
import logging

# uuid: 生成随机 ID，无需中心分配，适合做请求 ID
import uuid

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.constants import HEADER_REQUEST_ID


class AppError(Exception):
    """
    业务规则不允许：携带 【稳定错误码】 + 【给人看的说明】

    上游错误原本应该是 RequestError 类型，但是上游错误对客户端就是服务器返回错误；
    因此上游错误统一用业务错误 AppError 来管理。
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# 错误码 -> HTTP 状态码。没登记的码默认 400（"你的请求有问题"这一类）
_STATUS_BY_CODE: dict[str, int] = {
    "LAST_MESSAGE_NOT_USER": status.HTTP_400_BAD_REQUEST,
    # 以下三个都属于【上游的错】，必须与 500（我方的错）区分开
    # L1: 上游根本没回应（DNS / TCP / TLS 失败 / 超时）
    "UPSTREAM_UNREACHABLE": status.HTTP_502_BAD_GATEWAY,
    # L2: 上游有回应，但状态码是 4xx / 5xx
    "UPSTREAM_BAD_STATUS": status.HTTP_502_BAD_GATEWAY,
    # L3: 上游回了 200，但 body 不是我们约定的结构（HTML / 空 / 字段改名 / null）
    "UPSTREAM_MALFORMED": status.HTTP_502_BAD_GATEWAY,
}

# 以模块名为 logger 名，日志里能一眼看出是哪一行代码打的
# 它不会自己输出，要等有人给 root logger 配 handler（uvicorn 默认已配好，输出到终端）
logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """把各类异常的【翻译器】挂到 app 上（在 app 创建后调用一次）"""

    # 装饰器括号里：异常类 -> 登记到【异常表】（之前用路径字符串的登记到【路由表】）
    # 装饰器规则 = "把下面的函数，登记到某张表里的某一行"。
    #   括号里的参数 = 这张表的【主键】
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """把业务异常 AppError 翻译成统一形状的错误响应（HTTP 状态码由 _STATUS_BY_CODE 决定）"""
        # 用业务码去查表；查不到就用默认 400 —— 兜底防的是"漏登记"，不是"猜对"
        http_status = _STATUS_BY_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
        # JSONResponse：把 content 序列化成 JSON，并自动设好 Content-Type: application/json
        return JSONResponse(
            status_code=http_status,  # 回给客户端的 HTTP 状态码（由业务码映射而来）
            # 外层 error 是命名空间：将来加 request_id 等字段时，一眼能分清哪些属于错误信息
            #   code 给机器判断（稳定不变），message 给人看（可改文案）
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    # 注册"兜底"翻译器：任何没被更具体处理器接住的异常都落到这里
    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """兜底：未预期异常 -> 500 + 统一的错误形状 + request_id（堆栈只写日志）"""
        # 优先用中间件分配的 request_id（这样响应头、日志、响应体里的 ID 是同一个）
        #   只有中间件没跑到时才自己生成（兜底）
        request_id = getattr(request.state, "request_id", "") or uuid.uuid4().hex[:12]
        # logger.exception 会自动附带当前异常的完整 traceback（logger.error 不会）
        logger.exception("未处理异常 request_id=%s path=%s", request_id, request.url.path)
        # 回给客户端一句人话 + ID: 绝不回显 str(exc) 或堆栈
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # 500 = 我方服务器出错
            content={
                "error": {
                    "code": "INTERNAL_ERROR",  # 稳定业务码：客户端只需认这一个
                    "message": "服务内部错误",  # 给人看，不泄露任何内部细节
                    "request_id": request_id,  # 用户报错时提供它，我方据此搜日志
                }
            },
            # 正常响应由中间件补头，异常响应由处理器补头（因为两者创建 Response 的地方不同）
            # 这句正是对异常响应手动加头
            headers={HEADER_REQUEST_ID: request_id},
        )
