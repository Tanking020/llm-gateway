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

> 2026-11-16 实测。这一节的意义：**下次不要假设这些命令能用**。

| 工具 | 状态 | 怎么确认 | 卡住什么 |
|---|---|---|---|
| **Docker / Docker Desktop** | ❌ 未安装 | `docker --version` → 命令不存在；4 个常见安装路径全部 `Test-Path` = False | Step 13a（镜像 / compose / 非 root / SIGTERM）、13e（`X-Forwarded-For`）、13f（容器内压测） |
| **WSL / WSL2** | ❌ 未安装 | `wsl --status` → 「未安装用于 Linux 的 Windows 子系统」 | Docker Desktop 的前置条件 |
| 管理员权限 | ❌ 当前会话无 | `WindowsPrincipal.IsInRole(Administrator)` = False | 安装 Docker Desktop / `wsl --install` / 查 `Get-WindowsOptionalFeature` |
| 虚拟化 | ✅ 已开启 | `Win32_ComputerSystem.HypervisorPresent` = True | — |
| 磁盘 | ✅ 剩 169.8 GB | `Get-PSDrive C` | — |
| 系统版本 | Windows 11 **家庭版** | `Win32_OperatingSystem.Caption` | 家庭版**只能**用 WSL2 后端（Hyper-V 后端要 Pro/Enterprise） |

**要装 Docker 的话，顺序固定**（在管理员终端里）：

```powershell
wsl --install                 # 装 WSL2，完成后必须重启
# ── 重启后，管理员终端 ──
winget install --id Docker.DockerDesktop -e
# 启动 Docker Desktop → Settings 确认 Use WSL 2 based engine
docker run --rm hello-world   # 验证
```

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
