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
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.constants import ALLOWED_ORIGINS, HEADER_REQUEST_ID


class AppError(Exception):
    """
    业务规则不允许：携带 【稳定错误码】 + 【给人看的说明】

    上游错误原本应该是 RequestError 类型，但是上游错误对客户端就是服务器返回错误；
    因此上游错误统一用业务错误 AppError 来管理。
    """

    def __init__(self, code: str, message: str, *, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        # 【注意】：只有极少数错误需要往响应里带额外的头（目前只有 429 的 Retry-After）
        self.headers = headers or {}


# 错误码 -> HTTP 状态码。没登记的码默认 400（"你的请求有问题"这一类）
_STATUS_BY_CODE: dict[str, int] = {
    "LAST_MESSAGE_NOT_USER": status.HTTP_400_BAD_REQUEST,
    # 以下三个都属于【上游的错】，必须与 500（我方的错）区分开
    # L1: 上游根本没回应（DNS / TCP / TLS 失败 / 超时）
    "UPSTREAM_UNREACHABLE": status.HTTP_502_BAD_GATEWAY,
    # L1 的「太慢」分支：连得上、也在吐数据，但超出我们的【总时长】预算
    # 【注意】：504 而不是 502 —— 网关超时的标准语义是「上游没在期限内答完」，
    #   与「上游坏了」(502) 分开，客户端/编排系统的处置也不同
    "UPSTREAM_TIMEOUT": status.HTTP_504_GATEWAY_TIMEOUT,
    # L2：按【客户端能不能靠自己修好】细分 —— 能修的透传 4xx，修不了的给 502 + 细分码
    #   能修：限流（等一等）/ 内容过长（缩短）-> 客户端知道该做什么
    "UPSTREAM_RATE_LIMITED": status.HTTP_429_TOO_MANY_REQUESTS,
    "UPSTREAM_PAYLOAD_TOO_LARGE": status.HTTP_413_CONTENT_TOO_LARGE,
    #   修不了：我们的密钥坏了 / 我们发的 body 上游不收 -> 502（客户端改请求也没用）
    "UPSTREAM_AUTH_FAILED": status.HTTP_502_BAD_GATEWAY,
    "UPSTREAM_REJECTED": status.HTTP_502_BAD_GATEWAY,
    #   L2 的兜底：5xx（上游故障，重试可能有用）与 3xx（接口搬家，重试没用）
    "UPSTREAM_BAD_STATUS": status.HTTP_502_BAD_GATEWAY,
    # L3: 上游回了 200，但 body 不是我们约定的结构（HTML / 空 / 字段改名 / null）
    "UPSTREAM_MALFORMED": status.HTTP_502_BAD_GATEWAY,
    # 503 = 我暂时不能服务（不是我的错误，依赖挂了）—— 负载均衡看到它会摘掉本实例
    "DB_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    # 我方容量：并发闸门顶穿 —— 既不是上游的错，也不是客户端的错
    # 【注意】：必须 503，不能 429 —— 429 的意思是"你请求太多了"，现在是"我们暂时满了"
    "SERVER_BUSY": status.HTTP_503_SERVICE_UNAVAILABLE,
    # 客户端的错，且它自己修得好（把要求生成的输出的 token 调小再发）：400 而不是 5xx
    # 【注意】：不登记也会落到 400 兜底 —— 但那是"漏登记"的兜底，不是"这个码治 400"
    "INVALID_MAX_TOKENS": status.HTTP_400_BAD_REQUEST,
    # 404 有两种来源、两种含义：客户端据此能区分"模型名打错"和"对话 id 不存在"
    "MODEL_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "CONVERSATION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
}

# 以模块名为 logger 名，日志里能一眼看出是哪一行代码打的
# 它不会自己输出，要等有人给 root logger 配 handler（uvicorn 默认已配好，输出到终端）
logger = logging.getLogger(__name__)


# 没走 AppError 的错误（框架自己抛的 HTTPException）靠状态码兜底出稳定码
#   【注意】：同一个状态码会共用这个码 —— 我们自己的代码一律抛 AppError，不要用 HTTPException
_CODE_BY_STATUS: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _request_id(request: Request) -> str:
    """优先用中间件分配的；只有中间件没跑到时才自己生成"""
    return getattr(request.state, "request_id", "") or uuid.uuid4().hex[:12]


def _error_response(
    request: Request,
    http_status: int,
    code: str,
    message: str,
    details: list[dict[str, object]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """所有错误响应的唯一出口：形状只在这里定义一次"""
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": _request_id(request),
    }
    if details is not None:
        error["details"] = details
    # 【注意】：合并而不是覆盖 —— X-Request-ID 那一份任何错误响应都必须有
    merged = {HEADER_REQUEST_ID: str(error["request_id"])}
    if headers:
        merged.update(headers)
    return JSONResponse(
        status_code=http_status,
        content={"error": error},
        headers=merged,
    )


def _cors_headers(request: Request) -> dict[str, str]:
    """给【绕过 CORSMiddleware 的响应】补 CORS 头（目前只有 500）

    【注意】：500 由最外层 ServerErrorMiddleware 产出，在 CORSMiddleware 之外 → 拿不到它的头。
        浏览器里前端只会看到「网络错误」，读不到 request_id —— 而 500 恰恰最需要它。
    """
    origin = request.headers.get("origin")
    # 只回显白名单里的源；不在名单里就不写头（绝不回落到 "*"）
    if origin is None or origin not in ALLOWED_ORIGINS:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        # 与 CORSMiddleware 保持一致：同一 URL 的响应随 Origin 变化，不能被缓存复用
        "Vary": "Origin",
    }


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
        return _error_response(
            request, http_status, exc.code, exc.message, headers=exc.headers or None
        )

    # 挂在 Starlette 的 HTTPException 上：FastAPI 那个是它的子类，
    #   而且"路径不存在"是 Starlette 自己抛的 —— 只挂 FastAPI 的会漏
    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """框架自己抛的 HTTPException（路径不存在 / 405）：detail 当 message，状态码兜底出码"""
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        code = _CODE_BY_STATUS.get(exc.status_code, f"HTTP_{exc.status_code}")
        return _error_response(request, exc.status_code, code, detail)

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """422：保留定位信息，但塞进统一形状的 details 里"""
        # 【注意】：只挑 loc/msg/type —— errors() 默认还带 input，那是用户提交的原值
        details: list[dict[str, object]] = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in exc.errors()
        ]
        return _error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "请求参数校验失败",
            details,
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """兜底：未预期异常 -> 500 + 统一的错误形状 + request_id（堆栈只写日志）"""
        request_id = _request_id(request)
        # logger.exception 会自动附带当前异常的完整 traceback（logger.error 不会）
        logger.exception("未处理异常 request_id=%s path=%s", request_id, request.url.path)
        # 回给客户端一句人话 + ID: 绝不回显 str(exc) 或堆栈
        return _error_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "服务内部错误",
            headers=_cors_headers(request),
        )
