"""
本项目的配置

设计原则：所有【可调参数】集中在这一个文件里
其他代码只 'from app.config import settings', 不直接读 os.environ
这样本项目有哪些配置项一目了然而不是靠全局搜索
"""

# Literal 是 Python 标准库 typing 里的类型，用来表达“只能是这几个值之一”
from typing import Literal, Self

# BaseSettings: pydantic 普通模型（BaseModel）的子类
# 额外具备 "从环境变量 / .env 文件自动读取并填充字段" 的能力
# SettingsConfigDict：专门描述"去哪里读、怎么读"的配置字典类型
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # model_config 是本模型的行为配置（pydantic 约定用这个固定名字）
    model_config = SettingsConfigDict(
        # 去工作目录下的 .env 文件里读配置。文件不存在也不报错，会退回用默认值
        env_file=".env",
        # 用 UTF-8 解码 .env —— Windows 上不写这句可能按 GBK 读，中文会乱码
        env_file_encoding="utf-8",
        # .env 里出现"本模型没定义的键"时【直接报错】，而不是默默忽略
        # 选 forbid 的原因：拼错键名（如 PORTT）会被立刻发现，
        # 而不是"以为配上了、实际没配上" —— 静默失效是最难查的一类 bug
        extra="forbid",
        # 校验失败时，不把读到的原始值打出来！否则可能导致密钥泄露
        hide_input_in_errors=True,
    )

    # ===== 以下是本项目的全部可配置项 =====
    # 写法：字段名: 类型 = 默认值
    # 环境变量名 = 字段名转大写（匹配时大小写不敏感）
    # 例如字段 app_name ← 环境变量 APP_NAME。这个映射是自动的，不用手写

    # 应用名：字符串类型
    app_name: str = "llm-app-engineering"

    # 运行环境 Literal["dev", "prod"] = 只允许这两个值，
    # 写成别的（如 APP_ENV=test）会直接校验失败 —— 这就是"枚举式约束"
    # dev: 本机 prod: 线上服务器
    # 可部署：同一份产物，切环境不改代码，app_env 决定这是生产行为还是开发行为
    app_env: Literal["dev", "prod"] = "dev"

    # 调试开关，布尔类型。环境变量里写 true / false / 1 / 0 都能自动转成 bool
    debug: bool = False

    # 服务监听地址，字符串
    host: str = "127.0.0.1"

    # 服务监听端口，整数类型。
    # 环境变量里写 "8000"（字符串），pydantic 会自动转成 int 8000
    port: int = 8000

    # 数据库连接串。格式是「方言+驱动://路径」，sqlite+aiosqlite 表示"用 aiosqlite 驱动访问 SQLite"
    # 默认落到【当前工作目录】的 app.db（已加进 .gitignore）；可用 .env 里的 DATABASE_URL 覆盖
    database_url: str = "sqlite+aiosqlite:///./app.db"

    # ===== 上游 LLM 供应商（OpenAI 兼容协议）=====
    # 字段名故意不用 openai_*：我们走的是"OpenAI 兼容"协议，具体供应商可替换
    # （现在接 DeepSeek，将来换别家或本地推理，只改 .env，代码不动）

    # 上游 LLM 的 API Key
    # 【注意】：真实密钥只放 .env（不进 Git），这个字段只是用来读取它
    llm_api_key: str | None = None

    # 上游基础地址
    # 末尾不要带斜杠（相对路径 /models 会接到它后面）
    llm_base_url: str = "https://api.deepseek.com"

    # 默认模型名：客户端没在请求里指定 model 时用它兜底
    llm_model: str = "deepseek-flash"

    # 单次上游【读取间隔】的超时时间（秒）：httpx 默认只有 5 秒，LLM 生成动辄十几秒
    # 【注意】：它【不是】请求总时长 —— 上游每 0.9s 滴一帧就能无限期挂着（实测见 #55）
    request_timeout: float = 30.0

    # 单次上游调用的【总时长】预算（秒）：从开始消费到结束，超过就掐断
    # 【注意】：这是「慢速滴答」的唯一防线（request_timeout 管不到总时长）
    # 数值依据：max_tokens_ceiling=4096，慢模型约 30 tok/s → 上限 ≈ 137s，留余量取 120s；
    #   压测（13f）后再按实测 p99 校准
    upstream_total_timeout: float = Field(default=120.0, gt=0.0, le=600.0)

    # 优雅停机窗口（秒）：收到停止信号后，最多再等这么久让在途请求跑完
    # 【注意】：必须【小于】编排系统的宽限期（k8s terminationGracePeriodSeconds 默认 30s、
    #   docker stop 默认 10s 后 SIGKILL），否则 SIGKILL 先到、优雅窗口形同虚设
    # 【注意】：本配置只在 `python -m app` 下生效；直接 `uvicorn app.api.app:app` 时
    #   要用命令行参数 --timeout-graceful-shutdown（见架构 §9.5）
    # 【注意】：类型是 int 不是 float —— uvicorn 的 Config 注解写的是 `int | None`，
    #   传 float 过不了 mypy（实测报 arg-type）
    graceful_shutdown_timeout: int = Field(default=30, gt=0, le=300)

    # ===== 容量与成本护栏（不是调优参数，是防止一个用户拖垮所有人）=====

    # 同一时刻最多允许多少个上游调用在飞
    # 【注意】：这是【进程级】上限。用 --workers 4 启动时真实上限 = 这个数 × 4
    #   （每个 worker 是独立进程，各有一把自己的锁）
    # le=100 只是防手抖写成 10000，不是"最优值"
    max_concurrent_upstream_calls: int = Field(default=4, ge=1, le=100)

    # 抢不到槽位时最多等多久（秒）；等不到就回 503 + Retry-After
    # 设得太大 -> 被挡的请求一直占着 socket 和内存
    upstream_queue_timeout: float = Field(default=1.0, gt=0.0, le=30.0)

    # 服务端允许的 max_tokens 上限
    #   客户端要得比这个多 -> 拒绝（400），不是悄悄改成这个数
    #   客户端没指定     -> 发这个数当默认值（否则"不传"就等于"不限制"）
    # 【注意】：不要改成"夹紧到上限" —— 静默改客户端的参数会让回答被莫名截断
    # 上界不是"防手抖"（那是副产品），而是【成本预算】：
    #   📎 deepseek-flash 输出 $1.20/1M tokens -> 32768 输出 ≈ $0.039/请求
    #   模型支持到 384K=393216（≈ $0.47/请求），我们故意远低于它
    # 【注意】：一旦允许 >= 40960，"4096 多打一个 0" 就再也拦不住了 —— 两者不可兼得
    max_tokens_ceiling: int = Field(default=4096, ge=1, le=32768)

    @model_validator(mode="after")
    def _forbid_debug_in_prod(self) -> Self:
        # 【注意】：debug=True 会让 @app.exception_handler(Exception) 不执行，
        #   traceback 直接进响应体。所以写错配置要启动即崩，不能静默改成 False
        if self.app_env == "prod" and self.debug:
            raise ValueError("APP_ENV=prod 时不允许 DEBUG=true：traceback 会返回给客户端")
        return self


def startup_config_summary(config: Settings) -> dict[str, object]:
    """启动第一屏要打印的【生效配置摘要】—— 白名单制，不是「打印整个 settings」

    【注意】：这里是白名单，新增敏感字段时【不要】加进来；新增运行期旋钮时必须加进来
        （配错了值合法也看不出来，只有打出来才能发现）。tests/test_startup_config.py 钉住这份清单。
    """
    dialect, _, rest = config.database_url.partition("://")
    db_name = rest.rsplit("/", 1)[-1] if rest else ""
    return {
        "app_env": config.app_env,
        "debug": config.debug,
        # 【注意】：只打方言 + 库名 —— 连接串里可能有 用户名:密码@主机
        "database": f"{dialect}://…/{db_name}",
        "max_concurrent_upstream_calls": config.max_concurrent_upstream_calls,
        "upstream_queue_timeout": config.upstream_queue_timeout,
        "max_tokens_ceiling": config.max_tokens_ceiling,
        "request_timeout": config.request_timeout,
        "upstream_total_timeout": config.upstream_total_timeout,
        "graceful_shutdown_timeout": config.graceful_shutdown_timeout,
    }


# 模块级单例：整个应用共用这一个 settings 对象。
# 其它文件通过 `from app.config import settings` 拿到它
settings = Settings()
