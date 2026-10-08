"""
本项目的配置

设计原则：所有【可调参数】集中在这一个文件里
其他代码只 'from app.config import settings', 不直接读 os.environ
这样本项目有哪些配置项一目了然而不是靠全局搜索
"""
# Literal 是 Python 标准库 typing 里的类型，用来表达“只能是这几个值之一”
from typing import Literal

# BaseSettings: pydantic 普通模型（BaseModel）的子类
# 额外具备 "从环境变量 / .env 文件自动读取并填充字段" 的能力
# SettingsConfigDict：专门描述"去哪里读、怎么读"的配置字典类型
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # model_config 是本模型的行为配置（pydantic 约定用这个固定名字）
    model_config = SettingsConfigDict(
        # 去工作目录下的 .env 文件里读配置。文件不存在也不报错，会退回用默认值
        env_file='.env',
        # 用 UTF-8 解码 .env —— Windows 上不写这句可能按 GBK 读，中文会乱码
        env_file_encoding="utf-8",
        # .env 里出现"本模型没定义的键"时忽略它，而不是报错
        # extra="ignore",

        # 修改：.env 里出现"本模型没定义的键"时【直接报错】，而不是默默忽略
        # 选 forbid 的原因：拼错键名（如 PORTT）会被立刻发现，
        # 而不是"以为配上了、实际没配上" —— 静默失效是最难查的 bug
        extra="forbid",
    )

    # ===== 以下是本项目的全部可配置项 =====
    # 写法：字段名: 类型 = 默认值
    # 环境变量名 = 字段名转大写（匹配时大小写不敏感）
    # 例如字段 app_name ← 环境变量 APP_NAME。这个映射是自动的，不用手写

    # 应用名：字符串类型
    app_name: str = "llm-service"

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

    # 上游 LLM 的 API Key。`str | None` = "字符串 或 空"，
    # 默认 None 表示"允许不填"
    # ⚠️ 真实密钥只放 .env（不进 Git），这个字段只是用来读取它
    openai_api_key: str | None = None

# 模块级单例：整个应用共用这一个 settings 对象。
# 其它文件通过 `from app.config import settings` 拿到它
settings = Settings()