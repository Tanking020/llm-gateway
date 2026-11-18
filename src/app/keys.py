"""API key 运维 CLI：签发 / 列示 / 撤销

用法：
    uv run python -m app.keys create --user alice [--label laptop]
    uv run python -m app.keys list [--user alice]
    uv run python -m app.keys revoke --id 3

【注意】：明文只显示这一次 —— 库里只有 sha256，任何人（含我们）都还原不出来。
    丢了就 revoke 掉再建一把，不要试图"找回"。
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_api_key, hash_api_key
from app.database import SessionMaker, engine
from app.models import ApiKey, User

# 列表里只显示 hash 的前缀：够人肉区分两把 key，又不至于把整行贴进工单
_HASH_PREFIX = 12


async def _get_or_create_user(db: AsyncSession, name: str) -> tuple[User, bool]:
    """按名字取用户，不存在就建。返回 (用户, 是否新建)"""
    stmt = select(User).where(User.name == name)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is not None:
        return user, False
    user = User(name=name)
    db.add(user)
    # flush 只发 INSERT 拿到自增 id，不提交 —— 提交由调用方按自己的时机做
    await db.flush()
    return user, True


async def _create(user_name: str, label: str) -> int:
    raw = generate_api_key()
    async with SessionMaker() as db:
        user, created = await _get_or_create_user(db, user_name)
        if created:
            print(f"已创建用户 {user.name}（id={user.id}）")
        row = ApiKey(user_id=user.id, key_hash=hash_api_key(raw), label=label)
        db.add(row)
        # 【注意】：先提交再打印 —— 打印失败只是"你看不到"，而"你看到了但没存住"
        #   会让你拿着一把永远 401 的 key 去排查
        await db.commit()
        print(f"已创建 key id={row.id}（{user.name} / {label}）")
        print()
        print(raw)
        print()
        print("⚠️  明文只显示这一次。丢掉就 revoke 再建，库里没有可还原的副本。")
    return 0


async def _list(user_name: str | None) -> int:
    async with SessionMaker() as db:
        stmt = select(ApiKey, User.name).join(User, ApiKey.user_id == User.id).order_by(ApiKey.id)
        if user_name is not None:
            stmt = stmt.where(User.name == user_name)
        rows = (await db.execute(stmt)).all()

    if not rows:
        print("（没有匹配的 key）")
        return 0

    print(f"{'ID':<5}{'USER':<12}{'LABEL':<12}{'CREATED (UTC)':<18}{'STATUS':<9}HASH")
    for row, name in rows:
        status = "revoked" if row.revoked_at is not None else "active"
        created = str(row.created_at)[:16]
        print(
            f"{row.id:<5}{name:<12}{row.label:<12}{created:<18}{status:<9}"
            f"{row.key_hash[:_HASH_PREFIX]}…"
        )
    return 0


async def _revoke(key_id: int) -> int:
    async with SessionMaker() as db:
        row = await db.get(ApiKey, key_id)
        if row is None:
            print(f"没有 id={key_id} 的 key", file=sys.stderr)
            return 1
        if row.revoked_at is not None:
            # 幂等：重复撤销不报错（脚本里重跑不该炸）
            print(f"key id={key_id} 已经是撤销状态，无需再撤")
            return 0
        # 【注意】：撤销 = 打时间戳，不删行 —— 删了就没有审计痕迹了
        row.revoked_at = datetime.now(UTC)
        await db.commit()
        print(f"已撤销 key id={key_id}")
    return 0


async def _dispatch(args: argparse.Namespace) -> int:
    try:
        if args.cmd == "create":
            return await _create(args.user, args.label)
        if args.cmd == "list":
            return await _list(args.user)
        return await _revoke(args.id)
    finally:
        # 【注意】：CLI 是一次性进程，用完就把连接池放掉 ——
        #   否则同一次 pytest 里连续两次 asyncio.run 会各自新建事件循环，
        #   而池里留着上一个循环的连接（aiosqlite 会报 attached to a different loop）
        await engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.keys", description="API key 运维")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="签发一把新 key（明文只显示一次）")
    p_create.add_argument("--user", required=True, help="用户名；不存在会自动创建")
    p_create.add_argument("--label", default="", help="人看的标签，如 laptop / ci")

    p_list = sub.add_parser("list", help="列出 key（不显示明文）")
    p_list.add_argument("--user", default=None, help="只看某个用户的")

    p_revoke = sub.add_parser("revoke", help="撤销一把 key（打时间戳，不删行）")
    p_revoke.add_argument("--id", type=int, required=True, help="key 的 id，见 list")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return asyncio.run(_dispatch(args))


if __name__ == "__main__":
    sys.exit(main())
