"""容器产物（Dockerfile / .dockerignore / docker-compose.yml）的静态检查

为什么不跑 docker build：那要真引擎（且不在每次 pytest 里）。但这里要防的三类错
**不需要引擎也能查**：
  ① 密钥泄漏 —— `.env` 被排除掉之后又被人"手动加回来"
  ② 构建失败 —— Dockerfile `COPY` 的东西被 .dockerignore 排掉了（写代码时看不出来）
  ③ 部署顺序 —— compose 里迁移与应用的依赖被改回"人工 exec"（那种错没有任何其它用例会红）
"""

import re
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_DOCKERFILE = _ROOT / "Dockerfile"
_DOCKERIGNORE = _ROOT / ".dockerignore"
_NGINX_CONF = _ROOT / "deploy" / "nginx.conf"
_COMPOSE = _ROOT / "docker-compose.yml"

# 镜像里【必须】有的路径：缺任何一个，构建或运行就会坏
_REQUIRED_IN_CONTEXT = [
    "pyproject.toml",
    "uv.lock",
    "src",
    "alembic",
    "alembic.ini",
]

# 镜像里【绝不能】有的路径：进去就等于把密钥打进可被 pull 的层里
# 【注意】：必须包含**嵌套**路径 —— 📎 实测 `src/app/__pycache__/*.pyc` 真的进过镜像
#   （23 个 .pyc，还混着 cpython-314），而当时的守卫报绿。只查根层等于没查
_FORBIDDEN_IN_CONTEXT = [
    ".env",
    ".env.production",
    ".venv",
    ".git",
    "src/app/__pycache__",
    "src/app/__pycache__/x.cpython-312.pyc",
    "alembic/versions/__pycache__/y.pyc",
    "data/app.db",
    "logs/app.log",
    # 【注意】：deploy/ 只给宿主上的 compose 用，进镜像上下文毫无意义（且拖慢传输）
    "deploy/nginx.conf",
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


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """把一个 .dockerignore 模式转成「匹配整条相对路径」的正则

    【注意】：语义来自**实测**，不是文档推测。📎 同一棵树（顶层 / 一层嵌套 / 三层嵌套
    各一个 `__pycache__`），只换模式，BuildKit 的结果是：

        模式                顶层   一层   三层
        `__pycache__`       排掉   留下   留下      ← 裸名字只匹配根层！
        `__pycache__/`      排掉   留下   留下
        `*.pyc`             留下   留下   留下      ← 不含 `/` 连嵌套都碰不到
        `*.py[cod]`         留下   留下   留下
        `**/__pycache__`    排掉   排掉   排掉      ← 正确写法
        `**/*.pyc`          排掉   排掉   排掉

    换句话说：`**/` 是「任意层（含零层）」，`*` 不跨 `/`，`?` 单字符，`[abc]` 字符集
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern.startswith("**/", i):
                out.append("(?:.*/)?")  # 零到多层目录
                i += 3
            elif pattern.startswith("**", i):
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                out.append(re.escape(ch))
                i += 1
            else:
                inner = pattern[i + 1 : end]
                out.append("[" + ("^" + inner[1:] if inner.startswith("!") else inner) + "]")
                i = end + 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("".join(out))


def _ancestors(path: str) -> list[str]:
    """`a/b/c` → `['a', 'a/b', 'a/b/c']`（命中目录等于排掉其下全部）"""
    parts = path.split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def _matches(patterns: list[tuple[str, bool]], path: str) -> bool:
    """按 .dockerignore 顺序判断 path 会不会被排掉

    【注意】：Docker 的规则是「后匹配的覆盖先匹配的」，`!` 表示取反（重新包含）
    """
    excluded = False
    for pattern, negated in patterns:
        regex = _glob_to_regex(pattern.rstrip("/"))
        if any(regex.fullmatch(ancestor) for ancestor in _ancestors(path)):
            excluded = not negated
    return excluded


def _is_excluded(path: str) -> bool:
    return _matches(_patterns(), path)


def test_dockerfile_and_dockerignore_exist() -> None:
    assert _DOCKERFILE.is_file(), "缺 Dockerfile"
    assert _DOCKERIGNORE.is_file(), "缺 .dockerignore"


def test_matcher_follows_measured_buildkit_semantics() -> None:
    """回归：匹配器必须和真 Docker 一致 —— 这组期望值全部来自真 `docker build` 实测

    📎 见 `_glob_to_regex` 的实测矩阵。这条测试保护的是「守卫本身」：
        匹配器一旦退回「不含 `/` 就匹配任意层」的经典 builder 语义，这里会红
    """
    cases = [
        ("__pycache__", "__pycache__/a.pyc", True),
        ("__pycache__", "src/app/__pycache__/x.cpython-312.pyc", False),
        ("__pycache__/", "src/app/__pycache__/x.cpython-312.pyc", False),
        ("*.pyc", "__pycache__/a.pyc", False),
        ("*.py[cod]", "__pycache__/a.pyc", False),
        ("**/__pycache__", "__pycache__/a.pyc", True),
        ("**/__pycache__", "src/app/__pycache__/x.cpython-312.pyc", True),
        ("**/*.pyc", "src/app/__pycache__/x.cpython-312.pyc", True),
        (".venv/", ".venv/lib/junk.py", True),
    ]
    for pattern, path, expected in cases:
        actual = _matches([(pattern, False)], path)
        assert actual is expected, (
            f"模式 {pattern!r} 对 {path!r}：实测 {expected}，实现给了 {actual}"
        )


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


def _compose() -> dict[str, Any]:
    """解析 docker-compose.yml —— YAML 锚点会被展开成真实值

    【注意】：用真 YAML 解析而不是正则 —— 缩进/换行一变正则守卫就会给出虚假安全感（坑 K96）
    """
    raw: object = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), "docker-compose.yml 顶层不是字典"
    return raw


def test_compose_migrates_before_app_starts() -> None:
    """回归：迁移必须先成功、app 才启动，且两者看同一个库（#84 / 决策 45）"""
    services = _compose()["services"]
    app, migrate = services["app"], services["migrate"]

    # 【注意】：迁移没跑完就起 app = 空库首请求 no such table，而探针只 SELECT 1 发现不了（K93）
    depends = app.get("depends_on", {}).get("migrate", {})
    assert depends.get("condition") == "service_completed_successfully", (
        "app 必须等 migrate 成功退出 —— 否则空库上线第一个请求就是 no such table"
    )
    assert migrate["command"] == ["python", "-m", "alembic", "upgrade", "head"], (
        "migrate 的 command 必须走 alembic upgrade head"
    )
    # 【注意】：卷或连接串不一致 → 迁移改的是另一个库，app 用的那个仍然空（比不迁移更难查）
    assert migrate["volumes"] == app["volumes"], "migrate 与 app 必须挂同一个数据卷"
    assert migrate["environment"]["DATABASE_URL"] == app["environment"]["DATABASE_URL"], (
        "migrate 与 app 的 DATABASE_URL 必须一致"
    )
    assert "env_file" not in migrate, "migrate 不该挂 env_file —— 迁移用不上 LLM_API_KEY"
    assert migrate["restart"] in ("no", False), "一次性任务的 restart 必须关（失败要停下等人看）"


def test_compose_defines_database_url_once() -> None:
    """回归：连接串只写一份（锚点共享）；app 不许自己跑迁移"""
    text = _COMPOSE.read_text(encoding="utf-8")
    url = "sqlite+aiosqlite:////app/data/app.db"
    # 【注意】：两份副本迟早漂移；结构断言看不出"是不是抄的"，所以这里查字面量出现次数
    assert text.count(url) == 1, f"连接串字面量出现 {text.count(url)} 次，必须只在锚点写一次"
    app = _compose()["services"]["app"]
    assert app["environment"]["DATABASE_URL"] == url
    # 【注意】：把迁移塞进 app 启动命令 → 每次重启都跑、多副本并发迁移（决策 45 否掉的方案 B）
    assert "alembic" not in str(app.get("command", "")), "app 不许自己跑迁移"


def _nginx_code() -> str:
    """读 nginx 配置并【去掉注释】—— 否则注释里提到 proxy_buffering 也会被当成配置

    【注意】：单行内 `#` 之后整段都是注释，nginx 本身就是这么解析的
    """
    text = _NGINX_CONF.read_text(encoding="utf-8")
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def test_app_is_not_published_to_host() -> None:
    """回归：入口只允许 nginx —— app 一旦 publish 端口，就绕过了反代（决策 46）"""
    services = _compose()["services"]
    app, proxy = services["app"], services["proxy"]
    # 【注意】：发布端口 = 任何能连本机的人都能绕过 nginx 直连应用
    assert "ports" not in app, "app 不能再发布宿主端口 —— 入口只允许 nginx"
    assert app.get("expose") == ["8000"]
    published = [str(p) for p in proxy["ports"]]
    assert published == ["80:80"], f"只有 proxy 该发布端口，实际 {published}"


def test_proxy_waits_for_healthy_app_and_exits_gracefully() -> None:
    """回归：反代等 app 健康才起 + 收到 SIGQUIT 才优雅退出（决策 46 ③④）"""
    proxy = _compose()["services"]["proxy"]
    assert proxy["depends_on"]["app"]["condition"] == "service_healthy", (
        "反代必须在 app 健康后才起，否则启动期全是 502"
    )
    # 【注意】：nginx 对 SIGTERM 是 fast shutdown（掐断在途连接），SIGQUIT 才等它做完
    assert proxy["stop_signal"] == "SIGQUIT", (
        "nginx 默认 SIGTERM 是 fast shutdown，会掐断在途 SSE（决策 46）"
    )
    mounts = proxy["volumes"]
    assert any(str(m).endswith(":ro") and "nginx.conf" in str(m) for m in mounts), (
        "nginx 配置必须以只读方式挂进 conf.d"
    )


def test_nginx_conf_streams_and_reresolves() -> None:
    """回归：流式与上游重解析的四个前提（决策 46 ①②）"""
    code = _nginx_code()
    # 【注意】：默认 on 会把 SSE 攒成一块 —— 📎 实测 5 帧 × 0.4s 全在 2.07s 到齐
    assert "proxy_buffering off;" in code, "不关缓冲，SSE 会被 nginx 攒成一块"
    assert "proxy_cache off;" in code
    # 【注意】：nginx 只在上线时解析一次上游 IP；app 换 IP 后不重解析就一直 502
    assert re.search(r"resolver\s+127\.0\.0\.11\s+valid=", code), (
        "缺 resolver，上游 IP 变更后永久 502"
    )
    assert re.search(r"server\s+app:8000\s+resolve;", code), "上游必须带 resolve"
    assert re.search(r"zone\s+\S+\s+\d+k?;", code), "resolve 需要共享内存 zone"


def test_nginx_read_timeout_exceeds_app_budget() -> None:
    """回归：代理读超时必须大于应用侧总预算，否则长流被代理先掐（决策 46 ③ 的代价）"""
    from app.config import settings  # 局部 import：本文件其它用例不需要 app 包

    match = re.search(r"proxy_read_timeout\s+(\d+)s;", _nginx_code())
    assert match, "缺 proxy_read_timeout"
    timeout = int(match.group(1))
    # 【注意】：这两个数是「同一份事实的两处副本」—— 改 UPSTREAM_TOTAL_TIMEOUT 必须同步改 nginx
    assert timeout > settings.upstream_total_timeout, (
        f"nginx {timeout}s 必须 > upstream_total_timeout {settings.upstream_total_timeout}s"
    )
