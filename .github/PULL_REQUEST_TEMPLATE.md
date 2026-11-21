## 这个 PR 做了什么

<!-- 一段话说清改动与动机。关联编号写 `#N` / `决策 N` / `坑 K<n>`，不要复述内容。 -->

**改动**：
**动机**：

## 类型

- [ ] 功能（新增能力）
- [ ] 修复（行为错了）
- [ ] 重构（行为不变）
- [ ] 文档 / 配置 / 部署

## 自检（缺一项就别点 Ready for review）

- [ ] **五道门全绿**：`uv run ruff format --check . ; uv run ruff check . ; uv run mypy . ; uv run pyright ; uv run pytest -q`
- [ ] **行为有牙**：新行为至少一条用例；关键路径做了变异（改坏一行 → 用例红 → 还原）并在描述里写结果
- [ ] **契约同步**：端点 / 错误码 / 必填头有变 → `docs/api.md` + `docs/architecture.md`
- [ ] **文档同步**：取舍变化 → `docs/decisions.md` 加 ADR（背景 / 方案对比 / 决定 / **代价** / 重审条件）
- [ ] **台账同步**：`docs/DEVLOG.md` §二 追加一行（日期 / 做了什么 / 证据 / 关联编号），关闭的待办在 `docs/todos.md` 标 `✅`
- [ ] **计数同步**：用例数 / 文件数变化后，README / `tests/README.md` / `production-readiness.md` 已同步（`test_docs_contract.py` 会先红）
- [ ] **部署改动**：改了 `Dockerfile` / `docker-compose.yml` / `deploy/` → 本地 `docker compose build` 且 `up -d` 后 `/health` 200
- [ ] **没有密钥**：diff 里没有 `.env`、真实 key、完整连接串

## 影响与回滚

- **影响面**：（端点 / 表结构 / 部署形态 / 只影响内部实现 —— 不涉及就写「无」）
- **回滚方式**：（revert 这一个提交够不够？是否需要数据迁移回退？）
- **怎么验证修好了**：（贴一条可执行的命令 + 期望输出）

## 备注

（评审时需要先知道的事：未覆盖的情形、后续待办编号等）
