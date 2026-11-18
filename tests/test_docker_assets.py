"""容器产物（Dockerfile / .dockerignore）的静态检查

为什么不跑 docker build：那要真引擎（且不在每次 pytest 里）。但这里要防的两类错
**不需要引擎也能查**：
  ① 密钥泄漏 —— `.env` 被排除掉之后又被人"手动加回来"
  ② 构建失败 —— Dockerfile `COPY` 的东西被 .dockerignore 排掉了（写代码时看不出来）
"""

import fnmatch
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DOCKERFILE = _ROOT / "Dockerfile"
_DOCKERIGNORE = _ROOT / ".dockerignore"

# 镜像里【必须】有的路径：缺任何一个，构建或运行就会坏
_REQUIRED_IN_CONTEXT = [
    "pyproject.toml",
    "uv.lock",
    "src",
    "alembic",
    "alembic.ini",
]

# 镜像里【绝不能】有的路径：进去就等于把密钥打进可被 pull 的层里
_FORBIDDEN_IN_CONTEXT = [
    ".env",
    ".venv",
    ".git",
    "src/app/__pycache__",
]


def _patterns() -> list[tuple[str, bool]]:
    """解析 .dockerignore 成 [(pattern, 是否取反)]，按文件顺序

    【注意】：Docker 的规则是「后匹配的覆盖先匹配的」，`!` 表示取反（重新包含）
    """
    result: list[tuple[str, bool]] = []
    for raw in _DOCKERIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        result.append((line[1:].strip() if negated else line, negated))
    return result


def _is_excluded(path: str) -> bool:
    """按 .dockerignore 判断某个仓库相对路径会不会被排掉

    【注意】：这是 Docker 语义的**近似实现**，但覆盖了本项目用到的两类规则：
      ① 含 `/` 的模式 —— 对完整相对路径做匹配（如 `src/app/__pycache__`）
      ② 不含 `/` 的模式 —— 匹配【任意一层】路径片段（如 `__pycache__` 要能命中
         `src/app/__pycache__`）。📎 这正是我第一版写错的地方：只做整串
         `fnmatch` 会认为 `__pycache__` 排不掉 `src/app/__pycache__`
    """
    excluded = False
    for pattern, negated in _patterns():
        normalized = pattern.rstrip("/")
        if "/" in normalized:
            hit = fnmatch.fnmatch(path, normalized) or path.startswith(normalized + "/")
        else:
            hit = any(fnmatch.fnmatch(part, normalized) for part in path.split("/"))
        if hit:
            excluded = not negated
    return excluded


def test_dockerfile_and_dockerignore_exist() -> None:
    assert _DOCKERFILE.is_file(), "缺 Dockerfile"
    assert _DOCKERIGNORE.is_file(), "缺 .dockerignore"


def test_secrets_and_bulk_are_excluded() -> None:
    """回归：`.env` / `.venv` / `.git` 必须在排除清单里"""
    leaked = [p for p in _FORBIDDEN_IN_CONTEXT if not _is_excluded(p)]
    assert leaked == [], f"这些路径会进构建上下文（密钥/体积风险）：{sorted(leaked)}"


def test_required_build_inputs_are_not_excluded() -> None:
    """回归：把 uv.lock / alembic 排掉会让构建或 migrate 服务直接失败

    📎 实测过的失败形状：镜像里缺 alembic/ 时，`alembic upgrade head` 报
        `No 'script_location' key found in configuration.`
    """
    missing = [p for p in _REQUIRED_IN_CONTEXT if _is_excluded(p)]
    assert missing == [], f"这些构建必需路径被 .dockerignore 排掉了：{sorted(missing)}"


def test_every_copy_source_survives_dockerignore() -> None:
    """回归：Dockerfile 里 `COPY <src>` 的源必须真在构建上下文里

    这是「写的时候看不出来、build 时才炸」的那类错 —— 用静态检查提前拦下
    """
    text = _DOCKERFILE.read_text(encoding="utf-8")
    sources: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("COPY "):
            continue
        parts = stripped.split()[1:]
        # 跳过 --from=... / --chown=... 这类选项，取源与目标
        operands = [p for p in parts if not p.startswith("--")]
        if len(operands) < 2:
            continue
        # 跨阶段复制（--from=builder）的源来自上一阶段，不在构建上下文里
        if any(p.startswith("--from=") for p in parts):
            continue
        sources.extend(operands[:-1])

    assert sources, "Dockerfile 里没解析到任何 COPY（解析规则可能已过时）"
    dropped = [s for s in sources if _is_excluded(s)]
    assert dropped == [], f"这些 COPY 源被 .dockerignore 排掉了，构建会失败：{sorted(dropped)}"


def test_final_stage_runs_as_non_root_and_uses_exec_form() -> None:
    """回归：非 root + exec 形式 CMD —— 后者决定 SIGTERM 能不能直达应用（决策 39）"""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"^USER\s+(?!root)\S+", text, re.MULTILINE), "最终镜像没有切到非 root 用户"
    # exec 形式 = JSON 数组；shell 形式多一层 sh，信号可能被吞
    assert re.search(r'^CMD\s+\[\s*"python"', text, re.MULTILINE), (
        "CMD 必须是 exec 形式（JSON 数组），否则 SIGTERM 可能到不了应用"
    )
