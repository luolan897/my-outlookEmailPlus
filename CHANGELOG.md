# Changelog

All notable changes to OutlookMail Plus are documented in this file.

## [v1.14.0] - 2026-04-09

### 新功能 / New Features

- **CF 临时邮箱接入邮箱池（Phase 0-6）**：`/api/external/pool/claim-random` 在 `provider=cloudflare_temp_mail` 且池空时支持动态创建并直接进入 `claimed` 状态，统一纳入池化生命周期
- **CF 读信链路打通**：`mailbox_resolver` 新增 `provider=cloudflare_temp_mail` 识别与 `kind=temp` 描述返回，外部读信/验证码提取链路可透明处理 CF pool 账号
- **临时邮箱 Options 按 Provider 返回**：`/api/temp-emails/options` 支持 `provider_name` 参数，前端会按当前 provider 请求域名与规则，减少跨 provider 配置串扰
- **账号管理保护增强**：池化管理的 CF 账号在 UI 和后端都增加删除/编辑保护，避免手工误操作破坏池状态

### 修复 / Bug Fixes

- **Graph 401 回退策略修复**：区分 token 过期与权限不足（如 `ErrorAccessDenied`），权限不足场景允许继续 IMAP 回退，避免误判为必须重新授权
- **Issue #32 后端 500 修复**：删除账号前事务化清理 `account_claim_logs` 与 `account_project_usage`，修复关联历史导致的删除失败
- **全选交互修复**：账号全选改为基于分组数据源计算，并补充搜索模式下的显式拦截提示，减少“只选中当前页”误解
- **批量导入换行问题修复**：修复复制凭据时 refresh_token 折行导致的导入失败，新增续行合并逻辑
- **CF 配置兼容修复**：增强 CF Worker domains/options 读取与自动同步兜底，修复部分场景下域名下拉不生效

### 测试 / Verification

- 新增与补强测试覆盖：
  - `tests/test_pool_cf_integration_tdd_skeleton.py`
  - `tests/test_pool_cf_real_e2e.py`
  - `tests/test_graph_401_imap_fallback_regression.py`
  - `tests/test_account_delete_with_pool_history.py`
  - `tests/test_temp_emails_api_regression.py`
  - `tests/test_cf_pool_missing_coverage.py`

---

## [v1.13.0] - 2026-04-09

### 新功能 / New Features

- **热更新双模式支持**：新增 Watchtower 和 Docker API（A2 helper 容器）两种一键更新方式，支持在设置页面切换
- **Watchtower 集成**：连通性测试、手动触发更新、已是最新版本智能检测（基于 Watchtower 同步行为）
- **Docker API 自更新**：digest 预检查避免无效更新、辅助容器（oep-updater）执行 12 步更新流程、失败自动回滚
- **GHCR 镜像支持**：白名单新增 `ghcr.io/zeropointsix/` 前缀，支持 GitHub Container Registry 镜像
- **版本检测增强**：`_version_gt()` 支持 pre-release 后缀（如 `-hotupdate-test`），自动忽略后缀仅比较语义版本号
- **部署信息 API**：`/api/system/deployment-info` 返回镜像名、标签、本地构建检测、Docker API 可用性
- **healthz 增强**：新增 `boot_id`（进程指纹）和 `version` 字段，支持前端精确检测容器重启

### 修复 / Bug Fixes

- 修复 Graph API 401 被统一视为授权失效的问题，现可区分 token 过期与权限不足，避免错误跳过 IMAP 回退
- 修复 Watchtower 连通测试 5s 超时（Watchtower 同步检查需 25-30s），增加到 35s
- 修复 Watchtower 200 响应被误判为"更新成功"（实际为"已是最新"）
- 修复 GHCR 镜像不在白名单导致 Docker API 更新被拦截
- 修复本地镜像检测 `_looks_like_local_image_ref()` 误判远程镜像
- 修复 `docker_api_available` 仅检查 Watchtower 不检查 Docker API
- 修复 Docker API 自更新同步调用导致容器停止时响应中断（改为后台线程 + 立即返回）
- 修复 `ModuleNotFoundError: outlook_web.models.AuditLog` 导致更新接口 500
- 修复前端 `waitForRestart()` 无法检测容器真正重启（新增 boot_id 变化检测）

### i18n

- 新增 emoji 前缀 i18n 变体：`🔄 一键更新配置`、`🚀 触发容器更新`
- 新增设置页 Tab 翻译：基础 / 临时邮箱 / API 安全 / 自动化
- 新增连通性/更新状态翻译：连通正常 / 检查完毕 / 测试中 / 更新失败
- `testWatchtower()` 结果文本经过 `translateAppTextLocal()` 翻译
- `manualTriggerUpdate()` 使用 `pickApiMessage()` 实现双语消息

### 安全

- 镜像白名单校验 + RepoDigests 检测双重防护，禁止本地构建镜像触发更新
- Docker API 自更新默认关闭，需显式设置 `DOCKER_SELF_UPDATE_ALLOW=true`
- 更新操作记录审计日志

---

## [v1.11.0] - 2026-04-03

### 新功能 / New Features

- **邮箱池项目隔离（PR#27）**：在 `claim-random` 时支持传入 `project_key`，同一 `caller_id + project_key` 下已使用的账号不会被重复领取（DB 迁移 v17）
- **CF Worker 临时邮箱多域支持**：可在设置页配置多个 CF Worker 域名；新增"同步域名"按钮，支持前端一键刷新域名列表
- **CF Worker Admin Key 加密存储**：`cf_worker_admin_key` 现在以 `enc:` 前缀加密写入数据库，不再以明文存储（DB 迁移 v18）
- **账号列表前端分页**：每页展示 50 条账号，大量账号时滚动加载更流畅
- **统一轮询引擎**：将标准模式与简洁模式的双轮询系统合并为单一 `poll-engine`（4 阶段重构），消除轮询竞争与状态积压

### 修复 / Bug Fixes

- **BUG-06**：生成或删除临时邮箱后，列表中已选中的邮箱状态得到正确保留，不再因刷新而丢失选中高亮
- **BUG-07**：临时邮箱面板在刷新邮件列表后，域名下拉选择不再被意外重置回默认值
- **Issue #24**：修复邮件展开/激活状态在列表重渲染后丢失、i18n 语言切换后账号列表不刷新、视口高度链路断裂、缺失翻译词条等问题
- **轮询 BUG**：修复页面初始加载时触发的批量邮件拉取、分组切换重复启动轮询、跨视图切换时轮询状态积压等问题
- **Graph API 401 静默回退**：修复 token 轮换时 Graph API 401 被静默吞掉导致的 token 丢失问题

### i18n

- 临时邮箱面板域名提示文字（`domain_hint_xxx`）新增中英双语翻译
- CF Worker 域名同步按钮 (`sync_cf_domains`)、提示文字 (`cf_domain_hint`) 新增双语支持
- 补充设置页与轮询指示器等处的缺失翻译词条

### CI / 代码质量修复

- 修复 `pool.py` 中存在的重复函数定义（`release`、`complete`、`expire_stale_claims`、`recover_cooldown`、`get_stats`）
- 修复 `pool.py` `get_stats()` 后的死代码（`return` 之后的不可达 `claim` 函数体）
- 修复 `RESULT_TO_POOL_STATUS` 中 `"success"` 映射：由旧的 `"cooldown"` 改为正确的 `"used"`
- 修复 `get_stats()` 的 `pool_counts` 字典，补充缺失的 `"used": 0` 键
- 修复 `pool.py` `claim_atomic()` 中 black 格式化问题（`cutoff`、`lease_expires_at_str` 多行表达式）
- 在 `external_api.py` 中添加 `# noqa: E203`、`# noqa: C901` 压制 flake8 误报
- 对齐 `test_pool.py` 和 `test_pool_flow_suite.py` 中的测试断言，统一期望 `success` 完成后状态为 `"used"`
- 全量 `black --line-length 127` 与 `isort --profile black` 格式化

---

## [v1.10.0] - 2026-03-26

- OAuth 回归修复与认证后工作区重构

## [v1.9.2] - 2026-03-24

- 小版本修复

## [v1.9.0] - 2026-03-20

- 双语界面、统一通知分发与演示站点保护

## [v1.7.0] - 2026-03-15

- 第二次发布：README 交付口径补全

## [v1.6.1] - 2026-03-15

- 发布质量闸门清理与发布内容精简
