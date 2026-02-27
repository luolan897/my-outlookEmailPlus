# 项目概览

## 项目名称
Outlook 邮件管理工具 (Outlook Email Management Tool)

## 项目类型
Web 应用 - Flask 后端 + 传统前端

## 技术栈

### 后端框架
- **Flask 3.0+** - Web 框架
- **Flask-WTF 1.2+** - CSRF 保护
- **Werkzeug 3.0+** - WSGI 工具库

### 数据存储
- **SQLite** - 轻量级关系数据库
- 数据库路径: `data/outlook_accounts.db`
- Schema 版本: v2

### 核心依赖
- **requests[socks] 2.25+** - HTTP 客户端,支持 SOCKS 代理
- **APScheduler 3.10+** - 定时任务调度
- **croniter 1.3+** - Cron 表达式解析
- **bcrypt 4.0+** - 密码哈希
- **cryptography 41.0+** - 数据加密 (Fernet 对称加密)

### 外部 API
- **Microsoft Graph API** - 主要邮件访问方式
- **IMAP 协议** - 备用邮件访问方式 (新版/旧版服务器)
- **GPTMail API** - 临时邮箱服务

## 项目结构

```
outlookEmail/
├── web_outlook_app.py          # 应用入口
├── outlook_mail_reader.py      # 命令行邮件读取工具
├── outlook_web/                # 主应用模块
│   ├── app.py                  # Flask 应用工厂
│   ├── config.py               # 配置管理
│   ├── db.py                   # 数据库操作
│   ├── audit.py                # 审计日志
│   ├── errors.py               # 错误处理
│   ├── routes/                 # 路由层 (Blueprint)
│   ├── controllers/            # 控制器层
│   ├── services/               # 服务层
│   ├── repositories/           # 数据访问层
│   ├── security/               # 安全模块
│   └── middleware/             # 中间件
├── templates/                  # HTML 模板
│   ├── index.html              # 主页面
│   ├── login.html              # 登录页
│   └── partials/               # 页面片段
├── static/                     # 静态资源
│   ├── css/                    # 样式文件
│   └── js/                     # JavaScript 文件
│       ├── features/           # 功能模块
│       └── layout-*.js         # 布局系统
├── tests/                      # 测试
├── docs/                       # 文档
└── data/                       # 数据目录
```

## 核心功能模块

### 1. 邮箱账号管理
- 多邮箱账号管理
- 分组管理 (支持自定义颜色)
- 标签管理 (批量打标签/筛选)
- 批量导入/导出
- 分组级别代理配置

### 2. 邮件操作
- 查看邮件 (收件箱/垃圾邮件/已删除)
- 删除邮件 (单封/批量)
- 全屏查看模式
- 分页加载 (每页 20 封)
- 邮件缓存机制

### 3. Token 管理
- OAuth2 授权流程
- 自动刷新 Token
- 定时刷新 (按天数/Cron 表达式)
- 刷新历史记录
- 失败状态标识

### 4. 临时邮箱
- 集成 GPTMail API
- 一键生成临时邮箱

### 5. 批量操作增强
- 全选功能 (跨分组保持选中状态)
- 批量删除邮箱
- 批量移动分组
- 批量打标签

### 6. 验证码提取
- 自动提取验证码/链接
- Graph API → IMAP 回退策略
- 一键复制到剪贴板
- 加载状态与成功/失败反馈

### 7. 自动轮询
- 新邮件自动检测
- 桌面通知 (邮箱地址 + 邮件主题)
- 账号列表红点提��
- 连续错误自动停止
- 可配置轮询间隔/次数

### 8. 可调整布局系统
- 四栏式响应式布局
- 拖拽调整栏宽
- 布局状态持久化
- 支持折叠/展开
- 自适应窗口大小

### 9. 安全特性
- XSS 防护 (DOMPurify + iframe 沙箱)
- CSRF 防护 (Flask-WTF)
- 数据加密 (Fernet 对称加密)
- 登录限流 (5 次失败锁定 15 分钟)
- 审计日志
- 二次验证 (导出功能)

## 架构特点

### 分层架构
```
Routes (路由层)
  ↓
Services (服务层)
  ↓
Repositories (数据访问层)
  ↓
Database (SQLite)
```

### Blueprint 模块化
- `pages` - 页面路由
- `accounts` - 邮箱账号管理
- `groups` - 分组管理
- `tags` - 标签管理
- `emails` - 邮件操作
- `temp_emails` - 临时邮箱
- `oauth` - OAuth2 授权
- `settings` - 系统设置
- `scheduler` - 定时任务
- `system` - 系统操作
- `audit` - 审计日志

### 应用工厂模式
使用 `create_app()` 工厂函数创建 Flask 应用实例,便于测试和配置管理。

### 完整分层架构
- 已完成从单体架构到分层架构的迁移
- Routes → Controllers → Services → Repositories 清晰分层
- 中间件统一处理横切关注点

## 数据模型

### 核心表
- `accounts` - 邮箱账号
- `groups` - 分组
- `tags` - 标签
- `account_tags` - 账号标签关联
- `settings` - 系统设置
- `temp_emails` - 临时邮箱
- `refresh_logs` - Token 刷新日志
- `refresh_runs` - 刷新运行记录
- `distributed_locks` - 分布式锁

## 部署方式

### 开发环境
```bash
python web_outlook_app.py
```

### 生产环境
- Docker 部署 (提供 Dockerfile)
- WSGI 服务器 (Gunicorn/uWSGI)
- 环境变量配置

### 环境变量
- `PORT` - 端口号 (默认 5000)
- `HOST` - 监听地址 (默认 0.0.0.0)
- `FLASK_ENV` - 运行模式 (production/development)
- `SECRET_KEY` - Flask 密钥
- `DATABASE_PATH` - 数据库路径

## API 优先级策略

邮件操作采用三级回退机制:
1. **Graph API** (主要方式)
2. **IMAP 新版** (outlook.live.com)
3. **IMAP 旧版** (outlook.office365.com)

失败时自动回退到下一级,并提供详细错误信息。

## 当前状态

### 已完成
- ✅ 核心功能实现
- ✅ 安全特性完善
- ✅ 分组代理支持
- ✅ API 优先级回退
- ✅ 详细错误提示
- ✅ 全选功能 (跨分组状态保持)
- ✅ 验证码提取 (Graph → IMAP 回退)
- ✅ 自动轮询与通知
- ✅ 批量删除邮箱
- ✅ 架构迁移完成 (legacy.py 已移除)
- ✅ 可调整布局系统

### 进行中
- 🔄 前后端分离准备
- 🔄 单元测试覆盖率提升

### 待优化
- ⏳ 前后端完全分离
- ⏳ API 文档完善
- ⏳ 性能优化与监控
