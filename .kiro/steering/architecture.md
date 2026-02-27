# 架构设计

## 整体架构

### 架构模式
采用经典的三层架构模式:

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│    (Routes / Templates / Static)        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│          Business Layer                 │
│            (Services)                   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Data Access Layer               │
│          (Repositories)                 │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│          Database Layer                 │
│            (SQLite)                     │
└─────────────────────────────────────────┘
```

## 目录结构详解

### outlook_web/ 主模块

#### 核心文件
- `app.py` - Flask 应用工厂,负责应用初始化和 Blueprint 注册
- `config.py` - 配置管理,环境变量读取
- `db.py` - 数据库连接管理,Schema 初始化和升级
- `audit.py` - 审计日志记录
- `errors.py` - 错误处理和 trace_id 生成

#### routes/ 路由层
Blueprint 模块化路由,每个文件对应一个功能模块 (共 11 个):

- `pages.py` - 页面路由 (首页/登录页)
- `accounts.py` - 邮箱账号 CRUD
- `groups.py` - 分组 CRUD
- `tags.py` - 标签 CRUD
- `emails.py` - 邮件查看/删除
- `temp_emails.py` - 临时邮箱管理
- `oauth.py` - OAuth2 授权流程
- `settings.py` - 系统设置
- `scheduler.py` - 定时任务管理
- `system.py` - 系统操作 (导出/密码修改)
- `audit.py` - 审计日志查询

#### controllers/ 控制器层
请求处理和参数验证,每个文件对应一个路由模块 (共 11 个):

- `pages.py` - 页面控制器
- `accounts.py` - 账号管理控制器
- `groups.py` - 分组管理控制器
- `tags.py` - 标签控制器
- `emails.py` - 邮件操作控制器
- `temp_emails.py` - 临时邮箱控制器
- `oauth.py` - OAuth 控制器
- `settings.py` - 系统设置控制器
- `scheduler.py` - 调度器控制器
- `system.py` - 系统控制器
- `audit.py` - 审计控制器

#### services/ 服务层
业务逻辑实现,封装外部 API 调用 (共 9 个):

- `graph.py` - Microsoft Graph API 封装
  - 获取邮件列表
  - 获取邮件详情
  - 刷新 Token
  - 删除邮件
- `imap.py` - IMAP 协议封装
  - 新版服务器 (outlook.live.com)
  - 旧版服务器 (outlook.office365.com)
  - 邮件列表/详情获取
- `refresh.py` - Token 刷新服务
  - 单账号刷新
  - 批量刷新
  - 定时刷新调度
- `email_delete.py` - 邮件删除服务
  - 多 API 回退策略
- `scheduler.py` - 定时任务调度器
  - APScheduler 封装
  - 任务管理
- `gptmail.py` - GPTMail API 封装
- `http.py` - HTTP 客户端封装 (支持代理)
- `verification_extractor.py` - 验证码提取服务
  - 验证码/链接自动提取
  - Graph API → IMAP 回退策略
  - 正则表达式匹配

#### repositories/ 数据访问层
数据库 CRUD 操作封装 (共 8 个):

- `accounts.py` - 邮箱账号数据访问
  - 增删改查
  - 批量操作
  - 状态更新
- `groups.py` - 分组数据访问
- `tags.py` - 标签数据访问
- `settings.py` - 系统设置数据访问
- `temp_emails.py` - 临时邮箱数据访问
- `refresh_logs.py` - 刷新日志数据访问
- `refresh_runs.py` - 刷新运行记录数据访问
- `distributed_locks.py` - 分布式锁实现

#### middleware/ 中间件
横切关注点处理 (共 2 个):

- `trace.py` - trace_id 中间件
  - 请求追踪 ID 生成
  - 日志关联
- `error_handler.py` - 错误处理中间件
  - 统一错误响应
  - 异常捕获

#### security/ 安全模块
安全相关功能封装 (共 3 个):

- `auth.py` - 认证授权
  - 登录验证
  - 密码哈希
  - 会话管理
  - 登录限流
- `crypto.py` - 加密解密
  - Fernet 对称加密
  - Token 加密存储
  - 密钥派生
- `csrf.py` - CSRF 防护
  - Token 生成和验证
  - 装饰器封装

## 数据流

### 典型请求流程

```
1. 用户请求
   ↓
2. Route (Blueprint)
   - 参数验证
   - CSRF 验证
   - 认证检查
   ↓
3. Service
   - 业务逻辑
   - 外部 API 调用
   - 数据处理
   ↓
4. Repository
   - 数据库操作
   - 数据转换
   ↓
5. Database
   - SQL 执行
   ↓
6. 响应返回
   - JSON / HTML
   - 错误处理
```

### 示例: 获取邮件列表

```python
# 1. Route (routes/emails.py)
@bp.route("/api/emails")
def get_emails():
    account_id = request.args.get("account_id")
    folder = request.args.get("folder", "inbox")

    # 2. Service (services/graph.py or imap.py)
    emails = email_service.get_emails(account_id, folder)

    return jsonify(emails)

# 3. Service 内部
def get_emails(account_id, folder):
    # 从 Repository 获取账号信息
    account = account_repo.get_by_id(account_id)

    # 尝试 Graph API
    try:
        return graph_api.get_emails(account, folder)
    except:
        # 回退到 IMAP
        return imap_api.get_emails(account, folder)
```

## 设计模式

### 1. 工厂模式
`create_app()` 应用工厂函数,便于测试和多实例创建。

### 2. 仓储模式
Repository 层封装数据访问,业务逻辑与数据库解耦。

### 3. 策略模式
邮件访问采用多策略回退 (Graph API → IMAP 新 → IMAP 旧)。

### 4. 装饰器模式
- `@login_required` - 登录验证
- `@csrf_exempt` - CSRF 豁免
- `@rate_limit` - 速率限制

### 5. 单例模式
数据库连接绑定到 Flask `g` 对象,请求内单例。

## 安全架构

### 多层防护

```
┌─────────────────────────────────────────┐
│         Input Validation                │  参数验证
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         CSRF Protection                 │  CSRF Token
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│      Authentication & Rate Limit        │  登录验证/限流
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Business Logic                  │  业务逻辑
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Data Encryption                 │  数据加密
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Audit Logging                   │  审计日志
└─────────────────────────────────────────┘
```

### XSS 防护
1. **前端**: DOMPurify 净化 HTML
2. **iframe 沙箱**: 禁止脚本执行
3. **输出转义**: Jinja2 自动转义

### CSRF 防护
1. **Token 验证**: 所有状态变更操作
2. **SameSite Cookie**: Lax 模式
3. **Referer 检查**: 可选

### 数据加密
1. **Refresh Token**: Fernet 对称加密
2. **密码**: bcrypt 哈希
3. **密钥派生**: 基于 SECRET_KEY

## 并发处理

### 数据库并发
- SQLite WAL 模式
- 连接池管理 (Flask g 对象)
- 分布式锁 (distributed_locks 表)

### 定时任务
- APScheduler 后台调度
- 单实例运行 (避免重复执行)
- 任务状态持久化

## 缓存策略

### 邮件列表缓存
- 前端内存缓存
- 切换邮箱/文件夹即时展示
- 刷新页面清空缓存

### Token 缓存
- 数据库持久化
- 90 天有效期
- 自动刷新机制

## 错误处理

### 统一错误响应
```json
{
  "error": "错误信息",
  "trace_id": "唯一追踪 ID",
  "details": "详细错误信息"
}
```

### 错误级别
1. **HTTP 异常**: 4xx/5xx 状态码
2. **业务异常**: 自定义错误类
3. **系统异常**: 未捕获异常

### 错误追踪
- 每个请求生成唯一 trace_id
- 记录到审计日志
- 便于问题排查

## 扩展性设计

### 水平扩展
- 无状态设计 (会话存储在 Cookie)
- 数据库可迁移到 PostgreSQL/MySQL
- 支持负载均衡

### 垂直扩展
- 模块化设计,易于拆分微服务
- Blueprint 可独立部署
- 服务层可抽取为独立服务

## 前端架构

### 静态资源结构
```
static/
├── css/
│   ├── main.css           # 主样式
│   └── layout.css         # 布局系统样式
└── js/
    ├── main.js            # 主入口
    ├── layout-manager.js  # 布局管理器
    ├── layout-bootstrap.js # 布局初始化
    ├── state-manager.js   # 状态管理
    └── features/          # 功能模块
        ├── accounts.js    # 账号管理
        ├── emails.js      # 邮件操作
        ├── groups.js      # 分组管理
        └── temp_emails.js # 临时邮箱
```

### 模板结构
```
templates/
├── index.html             # 主页面
├── login.html             # 登录页
└── partials/              # 页面片段
    ├── modals.html        # 模态框
    └── scripts.html       # 脚本引用
```

### 布局系统
- 四栏式可调整布局 (分组/账号/邮件列表/邮件详情)
- 拖拽调整栏宽,实时保存
- 支持折叠/展开
- 响应式设计,自适应窗口大小

## 架构演进

### 已完成的迁移
1. ✅ 创建新的分层结构
2. ✅ Blueprint 模块化路由
3. ✅ 业务逻辑迁移到 Services
4. ✅ 数据访问迁移到 Repositories
5. ✅ 移除 legacy.py
6. ✅ 中间件统一处理

### 下一步计划
- ⏳ 前后端完全分离 (RESTful API)
- ⏳ 前端框架引入 (Vue.js/React)
- ⏳ API 文档完善 (OpenAPI/Swagger)
