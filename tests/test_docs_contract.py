"""文档 ↔ 代码的机械守卫（#90，2026-11-20 / 决策 49）

为什么需要它：端点表 / 错误码表 / 用例数这三类事实**同时存在于代码与文档**，
靠人比对必然腐烂（📎 2026-11-20 体检发现 13 处落后，其中 `api.md` 漏了 12 个业务码）。
判据：**「改一处会不会漏另一处」** —— 会漏的，就必须让它变红。
"""

import os
import re
import subprocess
from pathlib import Path

import pytest
from conftest import COLLECTED_COUNTS

from app.api.app import app
from app.errors import _STATUS_BY_CODE

_ROOT = Path(__file__).resolve().parents[1]
_API_MD = _ROOT / "docs" / "api.md"
_README = _ROOT / "README.md"
_TESTS_README = _ROOT / "tests" / "README.md"
_PRODUCTION_READINESS = _ROOT / "docs" / "production-readiness.md"

# 文档路由不写进端点表（它们随 APP_ENV 关闭，不是业务契约）
# 【注意】：/metrics 同理 —— 它是运维端点，`include_in_schema=False`，
#   且 nginx 硬阻断；写进对外契约反而会误导客户端（决策 50）
_DOC_ROUTES = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc", "/metrics"}


def test_api_md_documents_every_error_code() -> None:
    """回归：`_STATUS_BY_CODE` 里每个码都要在 api.md 写明状态码（漏一个，客户端就少一条分支）"""
    rows = re.findall(
        r"^\| (\d{3}) \| `([A-Z_]+)` \|", _API_MD.read_text(encoding="utf-8"), re.MULTILINE
    )
    documented = {code: int(status) for status, code in rows}
    # 【注意】：500 是兜底（没有业务码），文档里用 INTERNAL_ERROR 这个名字指代它
    expected = {**_STATUS_BY_CODE, "INTERNAL_ERROR": 500}

    assert set(documented) == set(expected), (
        f"文档多 {sorted(set(documented) - set(expected))}，"
        f"缺 {sorted(set(expected) - set(documented))}"
    )
    mismatched = {c: (documented[c], expected[c]) for c in expected if documented[c] != expected[c]}
    assert not mismatched, f"状态码不一致（文档, 代码）：{mismatched}"


def test_api_md_endpoint_table_matches_routes() -> None:
    """回归：端点表 == 实际路由（新增路由忘了写文档 = 客户端不知道有这个接口）"""
    documented = set(
        re.findall(
            r"^\| (GET|POST|PATCH|DELETE) \| `([^`]+)` \|",
            _API_MD.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    actual: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path is None or path in _DOC_ROUTES:
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            actual.add((method, path))

    assert documented == actual, (
        f"文档有、代码没有：{sorted(documented - actual)}；"
        f"代码有、文档没有：{sorted(actual - documented)}"
    )


# (文件, 正则, 预期命中次数) —— 锚定 + 次数双保险：既防「数字写错」，也防「正则悄悄失效」
# 【注意】：不能写宽正则 `\*\*(\d+) 个用例\*\*` —— 📎 会误判 tests/README 历史行的「累计 61 个用例」
_COUNT_CLAIMS: list[tuple[Path, str, int]] = [
    (_README, r"tests-(\d+)%20passed", 1),
    (_README, r"\n> (\d+) tests · ", 1),
    (_README, r"uv run pytest -q\s+# (\d+) 个用例", 1),
    (_README, r"\| `pytest -q` \| \*\*(\d+) passed\*\* \|", 1),
    (_README, r"# (\d+) 个用例，按「测哪一层」分为 \d+ 个文件", 1),
    (_TESTS_README, r"^\*\*(\d+) 个用例\*\*，按「测哪一层」", 1),
    (_PRODUCTION_READINESS, r"\*\*(\d+) 个用例\*\*", 2),
    (_PRODUCTION_READINESS, r"一条命令 (\d+) 个用例", 1),
    (_PRODUCTION_READINESS, r"→ \*\*(\d+) passed / \d+ s\*\*", 1),
]


def _per_file_counts() -> dict[str, int]:
    """取本次收集的逐文件用例数；只跑了子集就 skip

    【注意】：拿子集的数去比全量文档是**假红** —— 所以先确认「磁盘上的测试文件都被收集到了」
    """
    per_file = COLLECTED_COUNTS.get("per_file")
    assert isinstance(per_file, dict), (
        "收集钩子没跑：conftest.py 里的 pytest_collection_finish 被删了？"
    )
    on_disk = {p.name for p in (_ROOT / "tests").glob("test_*.py")}
    if set(per_file) != on_disk:
        pytest.skip("只收集到部分测试文件（子集运行）—— 用例数断言只在全量跑时有意义")
    return {str(name): int(count) for name, count in per_file.items()}


def test_docs_declared_test_counts_match_collection() -> None:
    """回归：文档里每个「N 个用例」都必须等于实际收集数（📎 曾烂到 153 vs 172）"""
    per_file = _per_file_counts()
    total = sum(per_file.values())
    problems = []
    for path, pattern, expected_hits in _COUNT_CLAIMS:
        found = [
            int(v) for v in re.findall(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
        ]
        if len(found) != expected_hits:
            problems.append(
                f"{path.name}：{pattern!r} 命中 {len(found)} 次，预期 {expected_hits} 次"
                "（正则或文档结构变了）"
            )
        problems.extend(
            f"{path.name}：宣称 {v} 个用例，实际收集 {total}" for v in found if v != total
        )
    assert not problems, "\n".join(problems)


def test_tests_readme_per_file_counts_match_collection() -> None:
    """回归：§1 的逐文件用例表 == 实际收集（一张会腐烂的表比没有表更糟）"""
    per_file = _per_file_counts()
    documented = {
        m.group(1): int(m.group(2))
        for m in re.finditer(
            r"^\| `(test_[a-z_]+\.py)` \| (\d+) \|",
            _TESTS_README.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    }
    assert set(documented) == set(per_file), (
        f"文档多 {sorted(set(documented) - set(per_file))}，"
        f"缺 {sorted(set(per_file) - set(documented))}"
    )
    mismatched = {n: (documented[n], per_file[n]) for n in per_file if documented[n] != per_file[n]}
    assert not mismatched, f"逐文件用例数不一致（文档, 实际）：{mismatched}"


# ============ 相对链接必须指向【已提交】的文件（2026-11-22）============
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_EXTERNAL = ("http://", "https://", "mailto:")


def _tracked_files() -> set[str] | None:
    """仓库里【已提交】的文件（posix 相对路径）；不在 git 工作区时返回 None"""
    try:
        done = subprocess.run(["git", "ls-files", "-z"], cwd=_ROOT, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return {p for p in done.stdout.decode("utf-8").split("\0") if p}


def test_relative_links_point_to_tracked_files() -> None:
    """回归：相对链接的目标必须是【已提交】的文件

    【注意】：只判断「磁盘上存不存在」不够 —— 本地有、仓库没有的文件（例如被 .gitignore
        排除的 .github/copilot-instructions.md）在 GitHub 上是 404，而本机永远检查不出来。
        📎 2026-11-22 实测：974 条链接报 0 broken，线上实际 14 处 404。
    """
    tracked = _tracked_files()
    if tracked is None:
        pytest.skip("不在 git 工作区（例如源码 tarball）：无法判断哪些文件已提交")

    # 目录也可能被链接（如 ../.github/ISSUE_TEMPLATE），只要它下面有已提交文件就算通
    dirs_with_files = {p.rsplit("/", 1)[0] for p in tracked if "/" in p}
    broken: list[str] = []
    for doc in sorted(p for p in tracked if p.endswith(".md")):
        text = (_ROOT / doc).read_text(encoding="utf-8")
        for match in _LINK.finditer(text):
            target = match.group(1)
            if target.startswith(_EXTERNAL) or target.startswith("#"):
                continue
            path = target.split("#")[0]
            if not path:
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(doc), path))
            if resolved.replace("\\", "/") in tracked | dirs_with_files:
                continue
            broken.append(f"{doc} -> {target}")

    assert not broken, f"这些相对链接指向未提交的文件（线上会 404）：{broken}"
