# 本机环境与操作纪律（Dev Environment）

> 这个文件回答：**在这台机器上干活，有哪些「不做就会出错」的具体操作。**
> 每条都来自真实事故；来龙去脉在 [ai-collaboration.md](ai-collaboration.md) §10（保留现场）。
> 这里只留**可执行的纪律**。
>
> 环境换了（macOS / Linux / PowerShell 7）请回来改这张表，别默认老经验成立。

## 1. 环境基线（2026-10-08 实测）

| 项 | 值 | 怎么查 |
|---|---|---|
| 操作系统 | Windows | — |
| Shell | **Windows PowerShell 5.1**（5.1.26100.9444，Desktop 版） | `$PSVersionTable.PSVersion` |
| Python | **3.12.15**（uv 托管，不依赖系统 Python） | `uv run python -V` |
| 系统 Python | 3.14.6 —— **不直接使用**，所有命令走 `uv run` | `python -V` |
| 包管理器 | **uv 0.12.23** | `uv --version` |
| Git | 2.55.0.windows.3 | `git --version` |
| uv 镜像 | `%APPDATA%\uv\uv.toml` → 清华 PyPI 镜像（`default = true`） | `Get-Content $env:APPDATA\uv\uv.toml` |
| 编码 | 用户级 `PYTHONUTF8=1`（Python 侧默认 UTF-8） | `[Environment]::GetEnvironmentVariable("PYTHONUTF8","User")` |
| 项目根 | `<user>\Desktop\llm-app-engineering` | `Get-Location` 必须在这里 |

## 2. PowerShell 5.1 的四条硬规则

| # | 规则 | 不这么做的后果 |
|---|---|---|
| 1 | **不支持** `&&`、`\|\|`、三元运算符 | 语法错误；用 `;` 串联，用 `if ($?) { … }` 判断上一步 |
| 2 | 读中文 / UTF-8 文件**必须** `-Encoding UTF8` | 按系统 ANSI（GBK/936）解码 → 乱码（`# 鎻忚堪…`） |
| 3 | 写文件用 `[IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding($false)))` | `Set-Content -Encoding utf8` 会写 **BOM**，`.python-version` 带 BOM 后 uv 直接忽略该文件 |
| 4 | 多行 / 含引号 / 含中文的提交信息 → 写 `$env:TEMP\msg.txt` 再 `git commit -F` | `-m` 被 PowerShell 解析碎裂 → `error: pathspec '…' did not match any file(s)` |

**多行文本用单引号 here-string**（`@'` … `'@`）：

```powershell
$msg = @'
feat: 增加 SSE 流式聊天接口

为什么：首字节 845ms 太慢，用户看不到任何反馈。
'@
[IO.File]::WriteAllText("$env:TEMP\msg.txt", $msg, (New-Object Text.UTF8Encoding($false)))
git commit -F "$env:TEMP\msg.txt"
```

> ❌ 双引号 here-string（`@"` … `"@`）里，反引号会转义（`` `f `` → 换页符、`` `n `` → 真换行），
> `$env:xxx` 会被**展开成值**。字符量大的提交信息必然踩。

**BOM 陷阱的实测证据**（2026-10-08）：`Set-Content -Encoding utf8` 写出的 `.python-version` 首字节是 `EF BB BF`，
uv 报 `warning: Ignoring unsupported Python request ﻿3.12 in version file`，然后**悄悄用了别的解释器**。
`uv python pin 3.12` 生成的文件字节是 `51,46,49,50,10`（`3.12\n`，无 BOM）。
判定方法：`Format-Hex .python-version | Select-Object -First 1`。

## 3. 常用命令（PowerShell 版）

| 想做的事 | 命令 |
|---|---|
| 找文本 | `Select-String -Path "src\**\*.py" -Pattern "…" -Encoding UTF8`（**没有 `grep`**） |
| 看文件差异 | `git --no-pager diff` / `git --no-pager diff --staged`（**禁用分页器**） |
| 提交前自查 | `git status` + `git diff --staged --stat` |
| 提交后核对 | `git --no-pager show --stat HEAD` —— **信息说的改动必须真的在里面** |
| 确认忽略生效 | `git check-ignore -v .env .venv/Scripts/python.exe` |
| 检查 lock 同步 | `uv lock --check` |
| 逐帧看 SSE | `curl.exe -N -s -X POST …`（`-N` 关掉 curl 自己的缓冲，否则看不到"逐字"） |
| **建表 / 升级本地库** | `uv run alembic upgrade head` —— ⚠️ **2026-11-16 起应用启动不再建表**（13b-2b-2），新 clone 或删过 `app.db` 之后必须先跑这一条，否则接口报 `no such table`（#50 / #84） |
| **验优雅停机窗口** | `uv run python scripts/probe_graceful_shutdown.py` —— 起真子进程 + 投真信号，打印 `PASS/FAIL` 并给出退出码（升级 uvicorn / 改停机逻辑 / 发版前跑一次；决策 39） |
| **签发 API key** | `uv run python -m app.keys create --user alice --label laptop` —— **明文只显示这一次**（库里只有 sha256） |
| **列示 / 撤销 API key** | `uv run python -m app.keys list` / `uv run python -m app.keys revoke --id <N>` —— 撤销 = 打时间戳，立刻 401 |

> ⚠️ PowerShell 里 `curl` 是 `Invoke-WebRequest` 的**别名**，必须写 `curl.exe`。
> 请求体含中文时写进 `$env:TEMP\chat.json`，用 `--data-binary "@$env:TEMP\chat.json"`，避免转义把 JSON 弄坏。

## 4. 临时文件与打印纪律

| 规则 | 原因 |
|---|---|
| 临时文件一律写 `$env:TEMP`，**绝不放进仓库** | 提交信息文件曾被 `git add -A` 一起提交（2026-10-10 真实发生） |
| 探针脚本**只打印白名单字段** | `print(pydantic 对象)` 会吐出全部字段，包含 `llm_api_key`（2026-10-13 真实泄露到终端） |
| 跑探针先确认 `DATABASE_URL` 指向 `%TEMP%` | 曾用默认 `./app.db` 跑探针，收尾时把开发库删了（2026-11-02） |

## 5. 运行中的服务

- 起服务用 `uv run python -m app`（`settings.host/port/debug` 才生效）。
- 关进程用 **PID**：`Stop-Process -Id <PID>`；**不要**按名字批量杀（`taskkill /IM` / `Stop-Process -Name`）。
- 改 `.env` 后要**重启**（`config` 在导入时读一次）。`DEBUG=true` 的 reloader 不会重读 `.env`。

## 6. 危险命令（先确认再执行）

`git reset --hard` · `git clean -fd` · 删除 `.venv` · `docker system prune` · 任何 `Remove-Item` 指向 `app.db`。

## 8. 本机**没有**的工具（会卡住哪些工作）

> 2026-11-16 建立，**2026-11-18 更新**（WSL 已装好）。这一节的意义：**下次不要假设这些命令能用**。

| 工具 | 状态 | 怎么确认 | 卡住什么 |
|---|---|---|---|
| **WSL / WSL2** | ✅ **3.0.5.0**（2026-11-18） | `wsl --version`；`Test-Path "$env:WINDIR\System32\vmcompute.exe"` = True | — |
| **Docker / Docker Desktop** | ✅ **4.99.0 / engine 29.9.3**（2026-11-18，WSL2 后端，数据盘在 `D:\Docker\wsl`） | `docker --version`；`docker info --format '{{.OSType}}'` = linux | 已解除。⚠️ 新装的 bin 目录要**重启 VS Code** 才进 PATH |
| 管理员权限 | ❌ 助手会话里没有 | `WindowsPrincipal.IsInRole(Administrator)` = False | 只能由学习者本人在**管理员终端**操作 |
| 虚拟化 | ✅ 已开启（VBS Running） | `Win32_ComputerSystem.HypervisorPresent` = True | — |
| 磁盘 | ✅ C 剩 174 GB / D 剩 455 GB（**同一块 NVMe**） | `Get-CimInstance Win32_LogicalDisk` | 装 Docker 时把**镜像存储位置**指到 D（已做：`D:\Docker\wsl`） |
| 系统版本 | Windows 11 **家庭版** 26200 | `Win32_OperatingSystem.Caption` | 家庭版**只能**用 WSL2 后端 |

### 8.0 WSL 安装时踩到的坑（2026-11-18 真实经历）

| 症状 | 根因 | 解法 |
|---|---|---|
| `wsl --install` 提示「请求的操作需要提升」，但**同时显示在下载 3.0.5** | 一条命令里有两半：**下载 MSIX 包**（不需要提权，成功了）与**启用可选功能**（要提权，被拒）。所以「看起来在装」其实只成功了一半 | 用**管理员终端**；或用「Windows 功能」窗口勾选 |
| `wsl --status` 说「WSL2 无法启动，因为未启用虚拟化」，但**「虚拟机平台」已经显示已勾选** | 🔴 **功能标记 Enabled，但 FOD 载荷还没装完**：`vmcompute.exe` 不在 `System32`（在 `WinSxS` 里躺着），`CBS\RebootPending` = True | ①**先跑 Windows Update**（📎 这次就是它补齐的：系统版本从 `.9711` 变成 `.9974`）；②`dism /online /enable-feature /featurename:VirtualMachinePlatform /all`；③**从开始菜单「重启」**（`shutdown /s` 走快速启动，**不会**完成 CBS 安装） |
| `wsl.exe` 输出在 PowerShell 里是乱码 | `wsl.exe` 输出是 **UTF-16LE** | `Start-Process ... -RedirectStandardOutput x.txt` 再 `[Text.Encoding]::Unicode.GetString(...)` |

**装 Docker 的顺序**（在**管理员**终端里）：

```powershell
winget install --id Docker.DockerDesktop -e --accept-source-agreements
# 启动 Docker Desktop → 接受协议 → 跳过登录
# 设置 → Resources → Advanced → Disk image location 改到 D:\Docker\wsl（趁还是空的，迁移成本为 0）
docker info --format '{{.OSType}}'   # 必须是 linux
```

### 8.0b Docker 装好之后还有一步：给 Docker Hub 配镜像加速器（2026-11-18 实测）

`docker.io` / `auth.docker.io` 在国内是 **000（8s 超时）**，不配加速器连 `hello-world` 都拉不下来。
📎 实测各源（`curl -o NUL -w "%{http_code}|%{time_total}" https://<host>/v2/`）：

| 目标 | 结果 | 结论 |
|---|---|---|
| `registry-1.docker.io` | **000**（8s 超时） | ❌ 不可用 |
| `ghcr.io` | 401 / 0.99s，但 **blob 下载卡死 >12 分钟** | ❌ 只有 API 通 |
| `docker.m.daocloud.io` | 401 / **0.15s** | ✅ 采用 |
| `docker.1ms.run` | 401 / **0.17s** | ✅ 采用（备用） |
| `pypi.tuna.tsinghua.edu.cn` | 200 / 2.2s | ✅（构建期 pip / uv 用） |

**配法**：写 `%USERPROFILE%\.docker\daemon.json`（Docker Desktop 的 Docker Engine 配置），然后 `docker desktop restart`：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run"
  ]
}
```

📎 验证：`docker info --format '{{json .RegistryConfig.Mirrors}}'` 应回显两条。

⚠️ `registry-mirrors` **只对 Docker Hub（docker.io）生效**，不管 `ghcr.io` —— 所以 `Dockerfile` 里不依赖任何 ghcr 镜像（决策 44）。
⚠️ 数据盘落点**不能**看 `docker info` 的 `DockerRootDir`（WSL2 后端永远是 `/var/lib/docker`，那是**虚拟机内部**路径）。权威来源是注册表：

```powershell
Get-ChildItem "HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss" | ForEach-Object {
  $p = Get-ItemProperty $_.PSPath; "$($p.DistributionName) -> $($p.BasePath)"
}
# 期望：docker-desktop -> \?\D:\Docker\wsl\DockerDesktopWSL\main
```

### 8.0c 构建镜像（只有两条命令要记）

```powershell
# 首次 / 换基础镜像后（会用清华 PyPI 源装 uv，避免撞 pypi.org 超时）
docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t llm-app:dev .

# 跑起来看看
docker run --rm llm-app:dev whoami                       # 必须 app，不是 root
docker run --rm llm-app:dev python -m alembic upgrade head
```

⚠️ `--build-arg PIP_INDEX_URL` **不能省**：省掉就是 `Dockerfile` 里 `ARG` 的默认值 `https://pypi.org/simple`，本机会慢到以为卡死（📎 `pypi.org/simple/uv/` 实测 10s 超时）。CI / 海外构建反而不该传它。
📎 参考实测：全量构建约 **14~20s**（依赖层命中缓存时 5.5s），镜像 **283 MB**，构建上下文 **26 文件 / 471 KB**。

### 8.0d 用 compose 起整套（13a-2a 起）

```powershell
docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
docker compose up -d
docker compose ps                                   # 等到 healthy
docker compose exec app whoami                      # app
docker compose exec app python -m alembic upgrade head
docker compose stop                                 # 停机计时（宽限期 40s / 窗口 30s）
docker compose down                                 # 保留卷；加 -v 才删数据
```

⚠️ **不要跑 `docker compose config` 就整份贴出来** —— 它会把 `env_file` 注入的 `LLM_API_KEY` **明文解析出来**（📎 2026-11-19 实际踩到）。要核对就用 `docker compose config | Select-String "stop_grace_period|HOST|DATABASE_URL"`。
⚠️ 数据在**命名卷** `llm-app_app_data` 里（WSL 的 ext4），宿主资源管理器打不开：`docker compose exec app ls -ln /app/data`。
📎 本机 SQLite 写入实测（200 次 commit）：命名卷 **1.975s** vs bind mount（v9fs）**7.465s**。

### 8.1 与这条相关的排期决定

Step 13 的执行顺序因此调整为 **13b → 13c → 13d → 13a → 13e → 13f**（见 [roadmap.md](roadmap.md) §二）。
理由不是"绕过"，是**先做不需要容器的三件事**，而且 13b 要改启动路径 —— 先定启动路径再封装镜像，compose 只需写一次。

## 7. 相关

| 想深入 | 去 |
|---|---|
| 这些纪律背后的 5 起事故 | [ai-collaboration.md](ai-collaboration.md) §10.1 ~ §10.8 |
| 工具开关（VS Code 工具数超限、审批流卡死） | [ai-collaboration.md](ai-collaboration.md) §10.6 ~ §10.6d |
| 仓库改名 / 换目录的完整流程 | [ai-collaboration.md](ai-collaboration.md) §10.7 |
| 跨项目也成立的 Windows 编码知识 | [../notes/stage0-engineering-basics.md](../notes/stage0-engineering-basics.md) 拓展 8 |
