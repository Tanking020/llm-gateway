"""测「启动配置摘要」这一层：该打什么、绝不能打什么（#77）"""

import pytest

from app.config import Settings, startup_config_summary

_WHITELIST = {
    "app_env",
    "debug",
    "database",
    "max_concurrent_upstream_calls",
    "upstream_queue_timeout",
    "max_tokens_ceiling",
    "request_timeout",
}


def test_summary_is_exactly_the_whitelist() -> None:
    assert set(startup_config_summary(Settings())) == _WHITELIST


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
