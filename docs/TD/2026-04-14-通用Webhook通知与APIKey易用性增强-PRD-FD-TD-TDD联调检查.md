# PRD/FD/TD/TDD 联调检查：通用 Webhook 通知与 API Key 易用性增强（V1）

> 检查日期：2026-04-14  
> 对照文档：
> - PRD: `docs/PRD/2026-04-14-通用Webhook通知与APIKey易用性增强PRD.md`（v1.5，路径待补）
> - FD: `docs/FD/2026-04-14-通用Webhook通知与APIKey易用性增强FD.md`（v1.5）
> - TD: `docs/TD/2026-04-14-通用Webhook通知与APIKey易用性增强TD.md`（v1.5）
> - TDD: `docs/TDD/2026-04-14-通用Webhook通知与APIKey易用性增强TDD.md`（v1.4）

---

## 1. 核心口径一致性检查

| 检查项 | PRD | FD | TD | TDD | 结论 |
|---|---|---|---|---|---|
| 范围：Webhook + API Key随机/复制 | ✅ | ✅ | ✅ | ✅ | 一致 |
| Webhook 位置：自动化 Tab 通知区 | ✅ | ✅ | ✅ | ✅ | 一致 |
| 配置粒度：全局单 URL | ✅ | ✅ | ✅ | ✅ | 一致 |
| 协议：`POST text/plain; charset=utf-8` | ✅ | ✅ | ✅ | ✅ | 一致 |
| URL 支持 `http/https` | ✅ | ✅ | ✅ | ✅ | 一致 |
| Token 可选（空则不发头） | ✅ | ✅ | ✅ | ✅ | 一致 |
| 测试口径：先保存再测试 | ✅ | ✅ | ✅ | ✅ | 一致 |
| 超时 10s + 失败重试 1 次 | ✅ | ✅ | ✅ | ✅ | 一致 |
| API Key 随机：64 位 URL-safe | ✅ | ✅ | ✅ | ✅ | 一致 |
| 随机/复制不自动保存 | ✅ | ✅ | ✅ | ✅ | 一致 |
| 不引入新库/新架构层 | ✅(目标) | ✅(设计) | ✅(技术决策) | ✅(测试原则) | 一致 |

---

## 2. 本轮联调发现与修正

### 2.1 Webhook Token 口径歧义（已修）

- 现象：PRD 初版文字“固定 Header”易被理解为无条件发送。
- 修正：PRD v1.1 明确为“可选 Header”，仅 token 非空时发送。

### 2.2 Webhook 测试配置来源需前置明确（已修）

- 现象：PRD 初版未显式强调 `webhook-test` 读取已保存配置。
- 修正：PRD v1.1 与 FD/TD/TDD 对齐，明确“先保存，再测试”。

---

## 3. 联调结论

1. 四份文档（PRD/FD/TD/TDD）已完成核心约束收敛。
2. 需求口径与测试口径一致，可直接进入 TODO 任务拆分与实现阶段。
3. 当前无阻塞性矛盾项。

---

## 4. 下一步建议

1. 按 TODO 推进实现：`docs/TODO/2026-04-14-通用Webhook通知与APIKey易用性增强TODO.md`。
2. 实施中严格保持：
   - `webhook-test` 仅使用已保存配置；
   - API Key 随机值前端原生算法生成，不引入新依赖。

### 4.1 TODO 联调回填（2026-04-14）

- 已完成：TODO Phase 0（文档与口径冻结）
- 说明：
  - PRD/FD/TD/TDD/TODO 引用链已闭环；
  - 会话硬约束已在 TODO 顶部与 Phase 0 勾选项中固化。

### 4.2 自动化验证回填（2026-04-15）

- 结论：Webhook/API Key 相关定向测试 + 分批全量回归均通过。
- 关键结果：
  - 定向：`test_settings_webhook` / `test_webhook_push` / `test_notification_dispatch` / `test_settings_webhook_frontend_contract` / `test_v190_frontend_contract` 全绿；
  - 分批回归：
    - `test_[a-f]*` → Ran 346, OK
    - `test_[g-l]*` → Ran 89, OK
    - `test_[m-r]*` → Ran 231, OK (skipped=7)
    - `test_[s-z]*` → Ran 492, OK
- 汇总：自动化回归共 **1158 tests 通过，skipped=7**。

### 4.3 会话场景回填（2026-04-15）

- 用户当前无现成 webhook 地址，已将联调口径统一为：
  1. 成功链路优先 `https://webhook.site/`；
  2. 失败链路使用 Beeceptor/Pipedream 返回 `5xx`；
  3. 配置入口固定为 `设置 -> 自动化 Tab -> Webhook 通知`；
  4. 若需本地服务配合联调，仅使用后台独立进程（`Start-Process`/独立进程），不使用前台阻塞命令。

### 4.4 实测进展回填（2026-04-15）

- 用户提供 webhook.site URL：`https://webhook.site/00766721-eaaf-4a3b-9821-60575812158c`
- 服务已按后台独立进程启动并通过健康检查（PID `37460`，`/healthz`=200）
- 日志显示 webhook-test 从“未配置 400”进入“保存后 200”链路，符合“先保存再测试”约束
- webhook.site 请求明细已核对：`POST` + `text/plain; charset=utf-8` + 业务文本 body；token 为空时未带 `X-Webhook-Token` 符合设计

### 4.5 第二轮全量回归与 Docker 前置检查（2026-04-15）

- 第二轮分批全量回归结果：
  - `test_[a-f]*` → Ran 346, OK
  - `test_[g-l]*` → Ran 89, OK
  - `test_[m-r]*` → Ran 231, OK (skipped=7)
  - `test_[s-z]*` → Ran 492, OK
- 汇总：**1158 tests 通过，skipped=7**（与第一轮一致，无新增回归失败）。
- Docker 前置检查结果：本机当前未连接 Docker Engine（`//./pipe/dockerDesktopLinuxEngine` 不存在），`docker version` 与 `docker build` 均失败；需启动 Docker Desktop/Engine 后再执行镜像构建验证。

### 4.6 Docker 构建与容器验证回填（2026-04-15）

- Docker 环境已恢复可用（Client/Server `28.3.2`）；
- 镜像构建成功：`outlook-email-plus:local-regression-20260415`；
- 容器运行成功：`oep-regression-20260415`，端口映射 `18080->5000`；
- 健康检查通过：`GET /healthz` 返回 `200`，容器状态 `healthy`。
- 端口异常处理：首次 `5055` 端口绑定失败后已清理失败容器并切换至 `18080` 成功。

### 4.7 main 分支启动与全量回归回填（2026-04-15）

- 分支状态：`Buggithubissue` 已本地 fast-forward 合并到 `main`（未 push）。
- 服务状态：
  - 按会话要求先停止旧进程（PID `37460`）；
  - 在 `main` 后台独立进程重新启动（PID `41184`）；
  - `GET /healthz` 返回 `200`。
- 分批全量回归（main）：
  - `test_[a-f]*` → Ran 346, OK
  - `test_[g-l]*` → Ran 89, OK
  - `test_[m-r]*` → Ran 231, OK (skipped=7)
  - `test_[s-z]*` → Ran 492, OK
- 汇总：**1158 tests 通过，skipped=7**，与前序回归一致。

---

**文档结束**
