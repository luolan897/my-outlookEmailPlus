# DEVLOG

## v1.14.0 - CF 临时邮箱池化接入与删除链路修复

发布日期：2026-04-09

### 新增功能

- 新增 CF 临时邮箱接入邮箱池主链路：当 `/api/external/pool/claim-random` 指定 `provider=cloudflare_temp_mail` 且池中无可用账号时，系统可动态创建 CF 邮箱并直接进入 claimed 状态。
- 新增 CF pool 账号读信路由识别：`mailbox_resolver` 支持将 `provider=cloudflare_temp_mail` 的账号解析为 `kind=temp`，统一走 TempMailService 读取邮件与提取验证码。
- 新增临时邮箱 options 的 provider 维度：`/api/temp-emails/options` 支持 `provider_name` 参数，前端按当前 provider 请求域名与前缀规则，避免跨 provider 配置串扰。
- 新增账号管理保护：邮箱池管理的 CF 账号在后端接口与前端操作入口都增加编辑/删除守卫，降低误操作对池状态的破坏风险。

### 修复

- 修复 Graph 401 误判问题：新增 Graph 401 细分判定逻辑，仅在 token 真正过期时标记 `auth_expired`，权限不足场景允许继续 IMAP 回退。
- 修复 Issue #32 删除 500：删除账号前事务化清理 `account_claim_logs` 与 `account_project_usage` 关联记录，避免外键约束导致的删除失败。
- 修复全选语义偏差：全选状态计算改为基于分组作用域数据，并在搜索模式下增加显式拦截提示，减少“只选当前页”的误解。
- 修复批量导入 refresh_token 折行问题：导入链路新增续行合并逻辑，降低从外部复制长 token 时的解析失败概率。
- 修复 CF Worker 域名 options 口径：增强 `cf_worker_*` 优先读取和自动同步兜底，恢复域名下拉在部分配置场景下的可用性。

### 重要变更

- 版本号从 `1.13.0` 提升到 `1.14.0`，应用 UI、系统接口和对外 API 返回的版本信息继续由 `outlook_web.__version__` 统一驱动。
- 数据库 schema 版本提升为 `19`，`accounts` 表新增 `temp_mail_meta` 字段，用于存储 CF 邮箱池化链路所需的 provider 元数据。
- 邮箱池支持的 provider 白名单扩展到 `cloudflare_temp_mail`，并在 `complete` 阶段针对 `success/credential_invalid` 结果增加远程 CF 邮箱删除动作（失败非阻塞，仅记录日志）。

### 测试/验证

- 自动化测试：`python -m unittest discover -s tests -v`
  - 结果：`Ran 952 tests in 168.755s`
  - 状态：全部通过（`OK`, `skipped=8`）
- 构建验证：`docker build -t outlook-email-plus:v1.14.0 .`
  - 状态：成功
  - 镜像摘要：`sha256:c3a1e16a8779948a100890dae8f1373616e55436c4a24c935ac31a2fc792202b`
- 发布产物：
  - `dist/outlook-email-plus-v1.14.0-docker.tar`
  - `dist/outlookEmailPlus-v1.14.0-src.zip`

## v1.13.0 - 热更新双模式端到端验证与合并

发布日期：2026-04-09

### 新增功能

- 新增热更新双模式支持：Watchtower（推荐）和 Docker API 自更新（A2 helper 容器），可在设置页面一键切换更新方式。
- 新增 Watchtower 集成：连通性测试、手动触发更新、已是最新版本智能检测（基于 Watchtower 同步 POST `/v1/update` 接口的行为特征——收到 200 响应即表示当前已是最新版本）。
- 新增 Docker API 自更新（A2 方案）：通过 Docker API 创建短生命周期 updater 容器（`oep-updater-*`），执行 12 步更新流程（pull → digest 比对 → create → stop 旧 → start 新 → health check → rename → cleanup），支持失败自动回滚。
- 新增 GHCR 镜像支持：白名单新增 `ghcr.io/zeropointsix/` 前缀，支持 GitHub Container Registry 镜像的热更新。
- 新增版本比较 pre-release 后缀支持：`_version_gt()` 自动忽略 `-hotupdate-test` 等后缀，仅比较语义化版本号。
- 新增 `/api/system/deployment-info` 部署信息 API：返回镜像名、标签类型、本地构建检测、Docker API 可用性、Watchtower 连通性。
- 新增 healthz `boot_id` 和 `version` 字段：前端通过 boot_id 变化精确检测容器重启。
- 新增设置面板手动触发更新按钮 UI，支持 i18n 中英双语。

### 修复

- 修复 Watchtower 连通测试超时：Watchtower `POST /v1/update` 是同步接口，完整镜像检查需 25-30s，连通测试超时从 5s 增加到 35s。
- 修复 Watchtower 200 响应被误判为"更新成功"：实际为"已是最新版本"（收到 200 说明 Watchtower 完成检查且未触发更新）。
- 修复 GHCR 镜像不在白名单导致 Docker API 更新被拦截。
- 修复本地镜像检测 `_looks_like_local_image_ref()` 误判远程镜像为本地构建。
- 修复 `can_auto_update` 逻辑仅检查 Watchtower 不检查 Docker API 可用性。
- 修复 Docker API 自更新同步调用导致容器停止时 HTTP 响应中断（改为后台线程 + 立即返回 → 再改为 A2 helper 容器方案）。
- 修复 `ModuleNotFoundError: outlook_web.models.AuditLog` 导致更新接口 500。
- 修复前端 `waitForRestart()` 无法检测容器真正重启（新增 boot_id 变化检测 + seenDown 双重判定）。
- 修复 Docker API 更新同 digest 时前端超时卡死（新增 digest 预检查，相同版本立即返回 `already_latest`）。
- 修复 emoji 前缀文本（🔄/🚀）的 i18n 翻译匹配失败。
- 修复设置页 Tab 标签（基础/临时邮箱/API 安全/自动化）缺少英文翻译。

### 重要变更

- 版本号从 `1.12.0` 提升到 `1.13.0`，应用 UI、系统接口和对外 API 返回的版本信息继续由 `outlook_web.__version__` 统一驱动。
- 热更新功能经过 `hotupdate-test` 分支 24 个提交的端到端验证，使用 GHCR 远程镜像在 Docker 环境中完成了两种更新方式的实际测试。
- 删除测试专用 compose 文件（`docker-compose.hotupdate-test.yml`、`docker-compose.docker-api-test.yml`），仅保留主 `docker-compose.yml`。
- 英文 README 大幅更新：新增 docker-compose + Watchtower 部署方式、一键更新功能描述和环境变量说明。

### 测试/验证

- 自动化测试：`python -m unittest discover -s tests -v`
  - 结果：`Ran 893 tests in 171.220s`
  - 状态：全部通过（6 skipped）
- 端到端验证（`hotupdate-test` 分支）：
  - Watchtower 模式：连通性测试、已是最新检测、i18n 双语切换 ✅
  - Docker API 模式：digest 预检查、A2 helper 容器创建/运行/自动清理 ✅
  - 镜像白名单：本地构建拦截、GHCR 远程镜像放行 ✅
  - 正向端到端：远程镜像 tag 变更 → A2 updater 完成 stop/start/rename/backup 全链路 ✅

## v1.10.0 - OAuth 回归修复与认证后工作区重构

发布日期：2026-03-26

### 新增功能

- 新增认证后主应用 `workspace` 语义化布局与 `ui_layout_v2` 持久化能力，支持侧栏折叠、拖拽宽度、移动端响应式以及旧本地布局数据自动迁移。
- 新增 Outlook OAuth 回调页与回调路由注册，前端可直接处理 `code`、`state`、错误参数及来源校验结果，降低 OAuth 导入链路的人工兜底成本。
- 新增账号备注轻量编辑 `PATCH` 接口，标准列表与紧凑模式都可以单独更新备注，不再要求提交完整账号凭据。
- 新增外部邮箱池对接收口后的回归覆盖，围绕 `/api/external/pool/*`、账号类型建议与通知分发补齐了一批契约测试与流程测试。

### 修复

- 修复 Outlook OAuth 回调、CSRF 恢复、verify-token 绑定和重试后回跳流程中的多处回归问题，避免导入链路因旧前端参数或异常回调而中断。
- 修复通知分发、Telegram 推送参与判定、临时邮箱内联图片刷新以及刷新失败提示文案不一致的问题，恢复主流程的可观测性和前端反馈一致性。
- 修复认证后简洁模式回归，恢复账号摘要列、分组交互、紧凑布局样式、多语言文案以及备注弹窗流程。
- 修复多 Key 鉴权场景下旧版 `external_api_key` 优先级异常，避免陈旧多 Key 配置覆盖仍在使用的单 Key 鉴权。

### 重要变更

- 版本号从 `1.9.2` 提升到 `1.10.0`，应用 UI、系统接口和对外 API 返回的版本信息继续由 `outlook_web.__version__` 统一驱动。
- 内部匿名 `/api/pool/*` 路径相关测试与前端契约已彻底收口到受控外部接口 `/api/external/pool/*`，后续集成方应以外部池协议为准。
- 当前仓库仍不是 Tauri 工程，不包含 `Cargo.toml`、`package.json`、MSI 或 NSIS 构建链路；本次正式产物继续沿用 Docker 镜像 tar 与源码 zip。

### 测试/验证

- 自动化测试：`python -m unittest discover -s tests -v`
  - 结果：`Ran 644 tests in 125.575s`
  - 状态：全部通过
- 构建验证：`docker build -t outlook-email-plus:v1.10.0 .`
  - 状态：成功
  - 镜像摘要：`sha256:7563be074c157e3273c8fc7aa557bda2ce5e5944a3a0a285ad0125bc559ece73`
- 发布产物：
  - `dist/outlook-email-plus-v1.10.0-docker.tar`
  - `dist/outlookEmailPlus-v1.10.0-src.zip`

## v1.9.2 - 紧凑模式发布与刷新提示增强

发布日期：2026-03-24

### 新增功能

- 新增账号管理“简洁模式”视图：账号列表支持高密度展示、分组条、验证码/最新邮件摘要列，以及标准/简洁模式之间的选中状态同步，适合批量运营场景。
- 新增账号备注轻量编辑链路：标准列表与简洁模式都可直接打开备注弹窗，通过独立 `PATCH` 接口只更新 `remark` 字段，支持新增、修改和清空备注而不要求重新填写账号凭据。
- 新增临时邮箱富内容保真能力：临时邮箱详情页可解析 `cid:` 内联图片、data URL 与远程图片地址，验证码截图类邮件可直接在前端查看。
- 新增按账号类型生成的刷新失败建议：刷新错误弹窗会根据 Outlook OAuth、Gmail IMAP、通用 IMAP 等不同场景给出差异化排障提示。

### 修复

- 修复 Outlook 刷新链路回归，手动刷新、重试失败与全量刷新会明确限制在 Outlook OAuth 账号范围内，避免 IMAP 账号误走 Graph 刷新流程并污染日志。
- 修复 Outlook.com Basic Auth 失败时的错误反馈，对邮箱详情、验证码提取和 external API 场景统一返回明确的 OAuth 导入提示。
- 修复旧版浏览器内置 OAuth 取 Token 流程导致的初始化与交互问题，移除失效的 `/api/oauth/*` 路由及前端入口，避免继续暴露不可用流程。
- 修复备注编辑、多语言文案与账号面板展示的一致性问题，统一“备注”入口名称，补齐弹窗相关国际化文案，并避免 IMAP 账号显示误导性的 Token 过期状态。

### 重要变更

- 版本号从 `1.9.1` 提升到 `1.9.2`，应用 UI 侧边栏版本显示、系统/对外 API 返回的 `version` 字段继续由 `outlook_web.__version__` 统一驱动。
- 当前仓库不是 Tauri 工程，不包含 `Cargo.toml`、`package.json`、MSI 或 NSIS 构建链路；本次发布继续沿用仓库既有的 Docker 镜像 tar 与源码 zip 作为正式产物。
- `README.md`、`README.en.md` 与 `registration-mail-pool-api.en.md` 已按当前实现同步更新，对外说明统一到受控 external API 与当前部署口径。

### 测试/验证

- 自动化测试：`python -m unittest discover -s tests -v`
  - 结果：`Ran 617 tests in 158.232s`
  - 状态：全部通过
  - 备注：Playwright 相关 2 个浏览器用例因环境缺少 `playwright` / `werkzeug` 依赖而按预期跳过。
- 构建验证：`docker build -t outlook-email-plus:v1.9.2 .`
  - 状态：成功
  - 镜像摘要：`sha256:d7aa37eabd966be0789815742434bec45472197ff6bfc1861db1859d02051346`
- 发布产物：
  - `dist/outlook-email-plus-v1.9.2-docker.tar`（174,048,768 bytes）
  - `dist/outlookEmailPlus-v1.9.2-src.zip`（1,078,317 bytes）

## v1.8.0 - 邮箱池与受控对外池 API 首次交付

发布日期：2026-03-17

### 新增功能

- 新增内部邮箱池接口：`/api/pool/claim-random`、`/api/pool/claim-release`、`/api/pool/claim-complete`、`/api/pool/stats`，支持随机领取、人工释放、结果回写与池统计。
- 新增对外邮箱池接口：`/api/external/pool/*` 现已支持 API Key 鉴权访问，并接入既有公网模式守卫、访问审计与调用方日级使用统计。
- 新增邮箱池状态机与持久化结构：账号新增 `pool_status`、`claimed_by`、`lease_expires_at`、`claim_token`、成功/失败计数等字段，同时引入 `account_claim_logs` 记录 claim/release/complete/expire 全链路动作。
- 新增多 API Key 粒度权限：`external_api_keys` 现支持 `pool_access` 字段，可按调用方单独授予 external pool 访问能力。

### 修复

- 修正对外邮箱池接口的返回格式，使 `claim-random`、`claim-release`、`claim-complete` 与 `stats` 全部对齐现有 external API contract，避免对接方处理分支不一致。
- 修正设置接口对邮箱池总开关和公网模式细粒度禁用项的读写逻辑，确保 `pool_external_enabled` 与 `external_api_disable_pool_*` 系列配置可以稳定持久化并回显。
- 修正租约超时回收行为，过期 claim 会自动写入 claim log、转入 `cooldown`，降低因调用方异常退出导致账号长期悬挂的风险。

### 重要变更

- 版本号从 `1.7.0` 提升到 `1.8.0`，应用 UI 侧边栏版本显示、系统/对外 API 返回的 `version` 字段继续由 `outlook_web.__version__` 统一驱动。
- 数据库 schema 新增邮箱池相关字段、`account_claim_logs` 表，以及 `external_api_keys.pool_access` 权限列；现有库初始化/升级时会自动补齐。
- 当前仓库不是 Tauri 工程，不包含 `Cargo.toml`、`package.json`、MSI 或 NSIS 构建链路；本次发布继续沿用仓库既有的 Docker 镜像 tar 与源码 zip 作为正式产物。

### 测试/验证

- 单元测试：`python -m unittest discover -s tests -v`
  - 结果：`Ran 440 tests in 42.599s`
  - 状态：全部通过
- 构建验证：`docker build -t outlook-email-plus:v1.8.0 .`
  - 状态：失败
  - 原因：Docker daemon 未启动，`//./pipe/dockerDesktopLinuxEngine` 不存在，当前环境无法连接 Docker Desktop Linux Engine
- 发布产物：
  - 未生成。由于镜像构建失败，本次未导出 Docker tar、源码 zip，也未同步到 GitHub Release 页面。

## v1.7.0 - 第二次发布：README 交付口径补全

发布日期：2026-03-15

### 新增功能

- 无新增业务功能。本次版本以“对外交付说明与发布内容整理”为主。

### 修复

- 重写 `README.md`，按当前代码实际能力补齐对外说明：对外只读 API、公网模式守卫（IP 白名单/限流/高风险端点禁用）、异步 probe、调度器、反向代理安全配置等。

### 重要变更

- 版本号从 `1.6.1` 提升到 `1.7.0`，应用 UI 侧边栏版本显示、系统/对外 API 返回的 `version` 字段均由 `outlook_web.__version__` 统一驱动。
- 发布内容继续沿用仓库既有的 Docker 镜像 tar 与源码 zip 作为正式产物。

### 测试/验证

- 单元测试：`python -m unittest discover -s tests -v`
  - 结果：`Ran 378 tests in 47.899s`
  - 状态：全部通过
- 构建验证：`docker build -t outlook-email-plus:v1.7.0 .`
  - 状态：通过
- 发布产物：
  - `dist/outlook-email-plus-v1.7.0-docker.tar`（299,417,600 bytes）
  - `dist/outlookEmailPlus-v1.7.0-src.zip`（930,706 bytes）

## v1.6.1 - 发布质量闸门清理与发布内容精简

发布日期：2026-03-15

### 新增功能

- 无新增终端功能。
- 补回面向发布的 `docs/DEVLOG.md`，用于保留版本级发布记录，避免内部过程文档清理后缺少对外可读的版本说明。

### 修复

- 清理 `external_api_guard`、`external_api_keys`、`external_api`、`system` 控制器中的格式与类型问题，恢复发布质量闸门可通过状态。
- 将异步 probe 轮询逻辑拆分为更小的私有函数，分别处理过期探测、待处理探测加载、命中结果写回与异常落库，降低发布前质量检查中的复杂度风险。
- 保持外部 API 行为不变的前提下，修正多处测试代码排版与断言表达，确保测试套件在当前代码状态下稳定通过。

### 重要变更

- 大规模移除了仓库内的内部分析、设计、测试与过程文档，仅保留运行所需内容与少量公开文档，显著缩减发布包体积和源码分发噪音。
- 本次版本号从 `1.6.0` 提升到 `1.6.1`。应用 UI 侧边栏版本显示、系统/对外 API 返回的 `version` 字段均由 `outlook_web.__version__` 统一驱动，已同步到新版本。
- 当前仓库不是 Tauri 工程，不包含 `Cargo.toml`、`package.json`、MSI 或 NSIS 构建链路；本次发布沿用仓库既有的 Docker 镜像与源码压缩包作为正式产物。

### 测试/验证

- 待执行：`python -m unittest discover -s tests -v`
- 待执行：`docker build -t outlook-email-plus:v1.6.1 .`
- 待执行：导出 Docker 镜像 tar 与源码 zip，并同步到 GitHub Release 页面。
