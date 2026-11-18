"""测「启动配置摘要」这一层：该打什么、绝不能打什么（#77）"""

import pytest
import uvicorn

from app import __main__ as main_module
from app.config import Settings, settings, startup_config_summary

_WHITELIST = {
    "app_env",
    "debug",
    "database",
    "max_concurrent_upstream_calls",
    "upstream_queue_timeout",
    "max_tokens_ceiling",
    "request_timeout",
    "upstream_total_timeout",
    "graceful_shutdown_timeout",
    "rate_limit_per_minute",
    "rate_limit_burst",
}

# 每个「故意不打」的字段都必须写理由：写不出理由的，就该进摘要（#85）
# 【注意】：新增敏感字段时加进这里 —— 它会出现在 diff 里，评审看得见
_NOT_PRINTED = {
    "llm_api_key": "敏感：绝不打印",
    "database_url": "只打脱敏派生项 database（方言 + 库名）",
    "app_name": "静态标识，排障无用",
    "host": "由启动命令（uvicorn 参数）决定，配置项在容器里可能不生效",
    "port": "同上",
    "llm_base_url": "外部依赖地址（含主机），不打",
    "llm_model": "默认模型名；每请求可被客户端覆盖，启动值不代表实际用量",
}


def test_summary_is_exactly_the_whitelist() -> None:
    assert set(startup_config_summary(Settings())) == _WHITELIST


def test_every_setting_is_printed_or_has_a_reason() -> None:
    """回归 #85：新增 Settings 字段却忘了放进摘要时，必须红 —— 而不是静默漏掉"""
    printed = set(startup_config_summary(Settings()))
    missing = set(Settings.model_fields) - printed - set(_NOT_PRINTED)
    assert missing == set(), f"这些配置项既没打印、也没说明理由：{sorted(missing)}"


@pytest.mark.parametrize(
    ("dsn", "must_contain", "must_not_contain"),
    [
        ("sqlite+aiosqlite:///./app.db", "sqlite+aiosqlite://…/app.db", "./app.db"),
        (
            "postgresql+asyncpg://user:pw@db.local:5432/prod",
            "postgresql+asyncpg://…/prod",
            "user:pw",
        ),
    ],
)
def test_database_shows_dialect_and_name_only(
    dsn: str, must_contain: str, must_not_contain: str
) -> None:
    summary = startup_config_summary(Settings(database_url=dsn))
    assert summary["database"] == must_contain
    assert must_not_contain not in str(summary)


def test_secrets_never_reach_the_summary() -> None:
    """回归：#77 —— 密钥与完整连接串（含账号密码 / 主机）绝不能进启动日志"""
    summary = startup_config_summary(
        Settings(
            llm_api_key="sk-secret-123", database_url="postgresql+asyncpg://u:p@db.local:5432/prod"
        )
    )
    text = str(summary)
    assert "sk-secret-123" not in text
    assert "u:p" not in text
    assert "db.local" not in text


def test_main_passes_graceful_shutdown_timeout_to_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归 13c-5：优雅窗口必须真的传给 uvicorn —— 否则默认 None = 无限等，发版会挂住"""
    captured: dict[str, object] = {}

    # 替换 uvicorn.run：只记录参数，不真的起服务
    def fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    # 【注意】：patch uvicorn.run（模块属性）而不是 main_module.uvicorn —— 后者 mypy strict 会报
    #   "does not explicitly export attribute"，且两者指向同一个模块对象，效果相同
    monkeypatch.setattr(uvicorn, "run", fake_run)
    main_module.main()

    assert captured["timeout_graceful_shutdown"] == settings.graceful_shutdown_timeout
