"""API key 运维 CLI（13d-5）：签发的 key 真的能过鉴权、撤销后真的 401、明文真的不进库"""

import sqlite3
from pathlib import Path

import conftest
import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.keys import main as keys_main

# 【注意】：这些用例**不**用 client fixture —— 它会把 TestClient 开在整条用例里，
#   而 CLI 用的是模块级 engine；两个事件循环抢同一个连接池会炸（见 keys.py 的 dispose 注释）


def _run(argv: list[str]) -> int:
    return keys_main(argv)


def _extract_key(out: str) -> str:
    """从 create 的输出里挑出 sk_ 开头的那个 token"""
    tokens = [tok for tok in out.split() if tok.startswith("sk_")]
    assert tokens, f"输出里没有明文 key：\n{out}"
    return tokens[0]


def _stored_hashes(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {row[0] for row in conn.execute("SELECT key_hash FROM api_keys")}
    finally:
        conn.close()


def test_created_key_actually_authenticates(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """签发的 key 必须真能用 —— 否则 CLI 只是"看起来成功" """
    conftest.reset_db()

    assert _run(["create", "--user", "carol", "--label", "laptop"]) == 0
    raw = _extract_key(capsys.readouterr().out)

    # 明文绝不进库
    assert raw not in _stored_hashes(db_path)

    with TestClient(app, headers={"X-API-Key": raw}) as c:
        assert c.get("/v1/conversations").status_code == 200
        # 归属生效：新用户看不到别人的东西
        assert c.get("/v1/conversations").json()["total"] == 0


def test_create_unknown_user_creates_it(capsys: pytest.CaptureFixture[str]) -> None:
    """13d-2 没有注册流程 —— 签发时必须顺手把人建出来，否则 key 挂不上属主"""
    conftest.reset_db()

    assert _run(["create", "--user", "dave"]) == 0
    out = capsys.readouterr().out
    assert "已创建用户 dave" in out


def test_create_twice_gives_two_working_keys(capsys: pytest.CaptureFixture[str]) -> None:
    """同一个人可以有多把 key（笔记本 / CI），互不影响"""
    conftest.reset_db()

    assert _run(["create", "--user", "carol", "--label", "laptop"]) == 0
    first = _extract_key(capsys.readouterr().out)
    assert _run(["create", "--user", "carol", "--label", "ci"]) == 0
    second = _extract_key(capsys.readouterr().out)
    assert first != second

    for raw in (first, second):
        with TestClient(app, headers={"X-API-Key": raw}) as c:
            assert c.get("/v1/conversations").status_code == 200


def test_list_never_prints_plaintext_or_full_hash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """list 会被贴进工单 —— 只能在里面看到 hash 前缀，看不到明文、也看不到完整 hash"""
    conftest.reset_db()
    assert _run(["create", "--user", "carol", "--label", "laptop"]) == 0
    raw = _extract_key(capsys.readouterr().out)

    assert _run(["list"]) == 0
    out = capsys.readouterr().out
    assert raw not in out
    assert "carol" in out and "laptop" in out and "active" in out
    full_hash = next(iter(h for h in _stored_hashes(Path(conftest._TEST_DB)) if len(h) == 64))
    assert full_hash not in out


def test_revoked_key_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """撤销后立刻 401 —— 这是"泄露了怎么办"的唯一答案"""
    conftest.reset_db()
    assert _run(["create", "--user", "erin"]) == 0
    raw = _extract_key(capsys.readouterr().out)

    with TestClient(app, headers={"X-API-Key": raw}) as c:
        assert c.get("/v1/conversations").status_code == 200

    assert _run(["revoke", "--id", "3"]) == 0  # reset_db 已占 id 1、2
    assert "已撤销" in capsys.readouterr().out

    with TestClient(app, headers={"X-API-Key": raw}) as c:
        assert c.get("/v1/conversations").status_code == 401


def test_revoke_is_idempotent_and_reports_unknown_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """幂等（脚本重跑不炸）；不存在的 id 要给出非 0 退出码，否则 CI 里静默成功"""
    conftest.reset_db()
    assert _run(["revoke", "--id", "1"]) == 0
    assert _run(["revoke", "--id", "1"]) == 0
    assert "已经是撤销状态" in capsys.readouterr().out

    assert _run(["revoke", "--id", "999"]) == 1
    assert "没有 id=999" in capsys.readouterr().err
