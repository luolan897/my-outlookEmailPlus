# BUG-00007 Telegram 推送实测问题

关联功能: TODO-00007 / FD-00007

## BUG-TG-001: 轮询间隔 min/max 限制过严

**现象**: 前端 HTML `<input>` 的 `min=60 max=3600` 和后端校验 `< 60 → 400` 限制了用户设置更灵活的轮询间隔。

**影响**: 用户无法设置 < 60 秒（快速调试）或 > 3600 秒（低频推送）的间隔。

**建议修复**:
- 前端：`min=10 max=86400`
- 后端：同步放宽范围 `10 ≤ interval ≤ 86400`
- 默认值保持 600 秒

**状态**: 待修复

---

## BUG-TG-002: 推送启用账号视觉区分度不够（已修复 ✅）

**现象**: 账号卡片上的 🔔 按钮仅通过 `.tg-push-active` 颜色高亮，在深色/浅色主题下不够明显。

**修复方案**: 在账号标签区域添加 `🔔 推送` 标签（Telegram 蓝 #0088cc 背景），与现有标签一致风格。
- 点击标签 → 关闭推送（标签消失）
- 🔔 按钮 → 开启推送（标签出现）
- 样式: `.tg-push-tag` 类，hover 半透明反馈

**状态**: ✅ 已修复

---

## BUG-TG-003: Graph API 调用缺少 proxy_url（已修复 ✅）

**现象**: `_fetch_new_emails_graph` 未传递 proxy_url，导致在需要代理的网络环境中 Graph API 请求超时。

**根因**:
1. `get_access_token` 函数名错误 → 应为 `get_access_token_graph`
2. `get_access_token_graph` 需要 `client_id` 参数，但 `get_telegram_push_accounts()` 的 SELECT 未包含该列
3. Graph API 请求 (`requests.get`) 和 Token 请求均未传递 `proxy_url`

**修复内容** (commit `4adb255`):
- 修正导入: `get_access_token` → `get_access_token_graph`
- SELECT 增加 `client_id` 列
- LEFT JOIN `groups` 表获取 `proxy_url`
- 传递 `proxy_url` 到 `get_access_token_graph()` 和 `requests.get(proxies=...)`

**状态**: ✅ 已修复

---

## BUG-TG-004: 未配置代理时 Outlook 账号推送全部失败

**现象**: 在需要代理才能访问外网的环境中，Outlook 分组的 `proxy_url` 为空，导致所有 Graph API 调用报 SSL/超时错误。

**日志**:
```
SSLError: HTTPSConnectionPool(host='login.microsoftonline.com', port=443): Max retries exceeded
ConnectTimeoutError: Connection to login.microsoftonline.com timed out. (connect timeout=30)
```

**影响**: 所有 Outlook 账号的 Telegram 推送功能失效；IMAP 账号 (QQ) 同样超时。

**根因**: 用户环境配置问题 — 分组未设置代理 URL。代码已正确支持代理传递。

**建议修复**: 用户需在「分组管理」中为对应分组填写代理地址。

**状态**: 非代码问题 / 配置相关

---

## BUG-TG-005: 禁用后重新启用推送会推送所有历史邮件（已修复 ✅）

**现象**: 用户关闭推送后再次开启，推送 Job 会将关闭期间所有邮件一次性推送到 Telegram。

**根因**: `toggle_telegram_push()` 在重新启用时未重置 `telegram_last_checked_at` 游标，旧游标指向很久之前的时间点，导致拉取大量历史邮件。

**原代码逻辑**:
```python
if enabled:
    if row["telegram_last_checked_at"] is None:
        # 仅首次启用重置游标
        db.execute("UPDATE ... SET telegram_last_checked_at = ?", (now,))
    else:
        # 重新启用：保留旧游标 ← BUG
        db.execute("UPDATE ... SET telegram_push_enabled = 1")
```

**修复内容**:
- 检测 `telegram_push_enabled` 当前值：
  - 从 0 → 1（状态切换）: 总是重置游标到当前 UTC 时间
  - 已经 1 → 1（幂等重复）: 不做任何修改，保持游标不变
- 新增测试 T-12b 验证重新启用行为

**状态**: ✅ 已修复
