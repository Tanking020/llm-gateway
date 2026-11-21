# syntax=docker/dockerfile:1.7
# LLM Gateway —— 生产镜像
#
# 阶段 1（builder）：装依赖，最终只把 /opt/venv 交出去（uv 与源码都留在 builder，不进最终层）
# 阶段 2（runtime）：只带 venv + alembic 配置，以非 root 用户运行
#
# 【注意】：CMD 用 `python -m app` 而不是裸 uvicorn —— 这样 settings.host/port 与
#   timeout_graceful_shutdown 都走 __main__.py（决策 39），不必在命令行重复参数

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.12.23
# 【注意】：COPY --from= 的镜像引用在解析期当阶段名处理，不展开 ARG（实测两种写法都报
#   invalid reference format）；且部分网络拉不到 ghcr.io 的 blob —— 所以 uv 走 pip 装。
# 【注意】：这个默认值【必须】与 uv.lock 里记录的 registry 一致 —— uv 把「包从哪个索引来」
#   也锁进了 lockfile，两者不一致时容器里的 `uv sync --locked` 直接 exit 1（#101 / 坑 K102）。
#   守卫：tests/test_docker_assets.py::test_dockerfile_default_index_matches_uv_lock
#   换源 = 换锁文件：`$env:UV_DEFAULT_INDEX="<index>"; uv lock`，两者一起改、一起提交
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple


# ============ 阶段 1：builder ============
FROM python:${PYTHON_VERSION}-slim AS builder

# 全局 ARG 只在 FROM 行可用，阶段内要用必须重新声明
ARG UV_VERSION
ARG PIP_INDEX_URL
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" "uv==${UV_VERSION}"

# 【注意】：pip 走 --index-url，uv 走 UV_DEFAULT_INDEX —— 两个都要设，否则 uv sync 会去撞默认源
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_DEFAULT_INDEX="${PIP_INDEX_URL}" \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build

# 先只拷依赖清单：依赖没变时这一层直接命中缓存，改代码不会重装依赖
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# 再拷源码并安装项目本身
COPY src ./src
# 【注意】：uv 默认 editable 装项目（写一个指向 /build/src 的 .pth），而 runtime 阶段没有 /build
#   → import app 直接 ModuleNotFoundError。必须 --no-editable 把包真正装进 site-packages
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


# ============ 阶段 2：runtime ============
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    # 【注意】：容器里必须 0.0.0.0 —— 默认的 127.0.0.1 只监听容器内部，宿主机连不上
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_URL="sqlite+aiosqlite:////app/data/app.db"

# 非 root：CIS Docker Benchmark 4.1；uid/gid 固定下来便于挂卷时对权限
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --create-home app \
 && mkdir -p /app/data \
 && chown -R app:app /app

WORKDIR /app

COPY --from=builder --chown=app:app /opt/venv /opt/venv

# 【注意】：alembic/ 与 alembic.ini 不在 wheel 里（实测装 wheel 后 `alembic upgrade head`
#   报 No 'script_location' key）—— migrate 服务要靠这两个文件，必须显式 COPY
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app alembic ./alembic

USER app
EXPOSE 8000

# 探 /health 而不是 /health/ready：liveness 只证明进程活着，
#   数据库没就绪不该让 Docker 反复重启容器（那是编排系统摘流量的事）
# 【注意】：urlopen 对 4xx/5xx 抛 HTTPError、连不上抛 URLError —— 都会让进程非 0 退出，
#   所以不需要再写 sys.exit(0 if ... else 1)。失败时 docker inspect 里的 traceback 是特性不是噪音
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

# exec 形式（JSON 数组）：PID 1 直接是 python，SIGTERM 能直达应用，
#   优雅停机窗口才会生效。shell 形式（CMD python -m app）会多一层 sh，信号可能被吞
CMD ["python", "-m", "app"]
