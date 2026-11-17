"""API key 的生成、哈希与查人：签发（CLI）与请求鉴权共用同一份规则

【注意】：只存 sha256 —— key 是 secrets.token_urlsafe(32) 的高熵随机串，
    慢哈希（bcrypt / argon2）是为「人选的低熵口令」设计的，套在这里等于每个请求白送几十毫秒 CPU
"""

import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, User

KEY_PREFIX = "sk_"  # 前缀让日志 / 密钥扫描器能一眼认出来
KEY_BYTES = 32  # token_urlsafe(32) → 43 个字符（约 256 bit 熵）


def generate_api_key() -> str:
    """生成一把新 key 的【明文】—— 它只在签发那一刻出现一次，之后库里只有 hash"""
    return KEY_PREFIX + secrets.token_urlsafe(KEY_BYTES)


def hash_api_key(raw: str) -> str:
    """明文 -> 库里存的 64 位十六进制

    【注意】：不加盐 —— 盐是用来对抗彩虹表的（针对低熵值），对 43 字符随机串没有意义；
        而且加盐后没法用 key_hash 的唯一索引直接查，只能全表扫
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def find_user_by_key(db: AsyncSession, raw: str) -> User | None:
    """按明文找到【未撤销】key 的属主；找不到返回 None（撤销 = revoked_at 非空）"""
    stmt = (
        select(User)
        .join(ApiKey, ApiKey.user_id == User.id)
        .where(ApiKey.key_hash == hash_api_key(raw), ApiKey.revoked_at.is_(None))
    )
    return (await db.execute(stmt)).scalar_one_or_none()
