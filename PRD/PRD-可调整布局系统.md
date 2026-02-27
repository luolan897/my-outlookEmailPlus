# PRD - 可调整布局系统

## 文档信息

- **文档编号**: PRD-00001
- **创建日期**: 2026-02-26
- **版本**: v1.1
- **状态**: 已审查
- **负责人**: 开发团队
- **审查日期**: 2026-02-26
- **审查结果**: 通过（已根据审查意见修订）

## 一、需求背景

### 1.1 当前问题

Outlook 邮件管理工具当前采用固定宽度的四栏布局：
- 分组面板（200px）
- 账号面板（260px）
- 邮件列表面板（380px）
- 邮件详情面板（自适应）

存在以下问题：
1. **缺乏灵活性**：用户无法根据使用习惯调整面板宽度
2. **空间利用率低**：不同屏幕尺寸下，固定宽度导致空间浪费或拥挤
3. **无法聚焦**：无法临时折叠不需要的面板，专注于当前任务
4. **用户体验落后**：现代编辑器（VS Code、EnsoAI）普遍支持可调整布局

### 1.2 需求来源

参考 EnsoAI 编辑器的 UI 设计理念，提升用户体验，使布局更加灵活和现代化。

### 1.3 目标用户

- **主要用户**：桌面浏览器用户（Chrome、Edge、Firefox、Safari）
- **使用场景**：
  - 需要同时查看多个邮箱账号的用户
  - 需要在不同工作模式间切换的用户（浏览模式 vs 专注阅读模式）
  - 使用不同屏幕尺寸的用户（笔记本 vs 外接显示器）

## 二、产品目标

### 2.1 核心目标

1. **提升灵活性**：用户可以自由调整每个面板的宽度
2. **支持折叠**：用户可以临时折叠不需要的面板
3. **状态持久化**：记住用户的布局偏好，刷新后自动恢复
4. **平滑体验**：所有交互都有流畅的动画过渡

### 2.2 成功指标

- 用户可以在 3 秒内完成面板宽度调整
- 用户可以在 1 秒内完成面板折叠/展开
- 布局状态在页面刷新后 100% 恢复
- 拖动调整时帧率保持在 60fps

## 三、功能需求

### 3.1 可拖动调整宽度

#### 3.1.1 功能描述

用户可以通过拖动面板边缘的分隔条来调整面板宽度。

#### 3.1.2 交互细节

**拖动区域**：
- 每个面板右侧边缘有 4px 宽的拖动区域（resizer）
- 鼠标悬停时显示视觉反馈：
  - 光标变为 `col-resize`（双向箭头）
  - 显示 2px 的高亮边框指示器
  - 背景色变为半透明黑色（rgba(26, 26, 26, 0.1)）

**拖动行为**：
- 鼠标按下（mousedown）时开始拖动
- 鼠标移动（mousemove）时实时更新面板宽度
- 鼠标释放（mouseup）时结束拖动，保存宽度到 localStorage

**宽度限制**：
- **最小宽度限制**：
  - 分组面板：150px（确保分组名称和图标可见）
  - 账号面板：180px（确保邮箱地址可读）
  - 邮件列表面板：280px（确保邮件预览可读）
  - 邮件详情面板：400px（确保邮件内容可读）
- **最大宽度限制**：
  - 分组面板：400px
  - 账号面板：500px
  - 邮件列表面板：600px
  - 邮件详情面板：无限制（自动填充）
- **窗口尺寸自适应**：
  - 当浏览器窗口宽度 < 1200px 时，自动折叠分组面板
  - 当浏览器窗口宽度 < 900px 时，自动折叠账号面板
  - 当浏览器窗口宽度 < 700px 时，自动折叠邮件列表面板
  - 确保邮件详情面板始终保持至少 400px 可见宽度

**视觉反馈**：
- 拖动时整个页面光标变为 `col-resize`
- 拖动时添加 `user-select: none` 防止选中文本
- 使用 CSS transitions 实现平滑过渡（200ms ease）

#### 3.1.3 技术实现

- 使用 CSS Grid 布局
- 使用 CSS 变量存储面板宽度：
  - `--group-panel-width`
  - `--account-panel-width`
  - `--email-list-panel-width`
- 使用原生 JavaScript 实现拖动逻辑
- 使用 requestAnimationFrame 优化性能

### 3.2 面板折叠/展开

#### 3.2.1 功能描述

用户可以点击折叠按钮来隐藏/显示面板，专注于当前任务。

#### 3.2.2 交互细节

**折叠按钮位置**：
- 分组面板：右上角
- 账号面板：右上角
- 邮件列表面板：右上角

**按钮样式**：
- 图标：左箭头（←）表示折叠，右箭头（→）表示展开
- 尺寸：24x24px
- 悬停效果：背景色变为 #f5f5f5

**折叠动画**：
- 使用 CSS transition 实现平滑动画（200ms ease）
- 折叠时宽度变为 0，同时 opacity 从 1 到 0
- 展开时恢复到折叠前的宽度，opacity 从 0 到 1

**折叠状态指示**：
- 折叠后在主容器边缘显示一个细条（48px 宽）
- 细条上显示面板名称（竖排文字）
- 点击细条可以快速展开面板

#### 3.2.3 折叠规则

- 分组面板、账号面板、邮件列表面板可以独立折叠
- 邮件详情面板不可折叠（始终可见）
- 至少保持一个侧边栏面板展开（不能全部折叠）
- **折叠时的拖动行为**：
  - 当面板处于折叠状态时，该面板的 resizer（拖动区域）自动隐藏
  - 用户必须先点击折叠指示条展开面板后，才能拖动调整宽度
  - 展开时恢复到折叠前的宽度（从 localStorage 读取）

### 3.3 恢复默认布局

#### 3.3.1 功能描述

用户可以一键恢复到默认布局，清除所有自定义调整。

#### 3.3.2 交互细节

**触发位置**：
- 在顶部导航栏的右侧添加"恢复默认布局"按钮
- 图标：重置图标（↻）
- 文字：仅在悬停时显示 tooltip

**确认机制**：
- 点击后弹出确认对话框：
  - 标题："恢复默认布局"
  - 内容："确定要恢复到默认布局吗？当前的面板宽度和折叠状态将被重置。"
  - 按钮："取消" / "确定"

**默认布局参数**：
- 分组面板：200px，展开
- 账号面板：260px，展开
- 邮件列表面板：380px，展开
- 邮件详情面板：自适应

**重置动画**：
- 使用 CSS transition 平滑过渡到默认宽度（300ms ease）

### 3.4 状态持久化

#### 3.4.1 功能描述

自动保存用户的布局偏好，页面刷新后恢复。

#### 3.4.2 保存内容

**面板宽度**：
- 分组面板宽度
- 账号面板宽度
- 邮件列表面板宽度

**折叠状态**：
- 分组面板是否折叠
- 账号面板是否折叠
- 邮件列表面板是否折叠

#### 3.4.3 存储方式

- 使用 localStorage 存储
- **存储键名**：`outlook_layout_state_${userId}`（支持多用户隔离）
  - 如果用户未登录，使用 `outlook_layout_state_guest`
  - 如果系统有用户 ID，使用 `outlook_layout_state_${userId}`
- 数据格式：
```json
{
  "version": "1.1",
  "userId": "user123",
  "timestamp": 1709020800000,
  "panels": {
    "groups": {
      "width": "200px",
      "collapsed": false
    },
    "accounts": {
      "width": "260px",
      "collapsed": false
    },
    "emails": {
      "width": "380px",
      "collapsed": false
    }
  }
}
```

#### 3.4.4 保存时机

- 拖动调整宽度后，延迟 500ms 保存（防抖）
- 折叠/展开面板后，立即保存
- 恢复默认布局后，清除保存的状态
- **页面卸载时强制保存**：
  - 监听 `beforeunload` 事件
  - 如果有未保存的防抖任务，立即执行保存
  - 确保用户的最后一次调整不会丢失

#### 3.4.5 加载时机

- 页面加载完成后，从 localStorage 读取状态
- 如果存在保存的状态，应用到 CSS 变量
- 如果不存在，使用默认布局

## 四、非功能需求

### 4.1 性能要求

- **拖动流畅度**：拖动时帧率保持在 60fps
- **动画性能**：使用 CSS transform 和 opacity，避免触发 reflow
- **内存占用**：localStorage 数据不超过 1KB

### 4.2 兼容性要求

- **浏览器支持**：
  - Chrome 90+
  - Edge 90+
  - Firefox 88+
  - Safari 14+
- **CSS 特性**：
  - CSS Grid
  - CSS 变量
  - CSS transitions
- **JavaScript 特性**：
  - ES6+
  - localStorage API
  - requestAnimationFrame

### 4.3 可访问性要求

- **折叠按钮**：
  - 支持键盘操作（Tab 聚焦 + Enter 触发）
  - 有合适的 aria-label（如"折叠分组面板"）
- **拖动区域（Resizer）**：
  - 支持键盘操作：
    - Tab 键聚焦到 resizer
    - 左箭头键（←）：减小面板宽度（每次 10px）
    - 右箭头键（→）：增大面板宽度（每次 10px）
    - Shift + 左/右箭头：快速调整（每次 50px）
  - 添加 ARIA 属性：
    - `role="separator"`
    - `aria-orientation="vertical"`
    - `aria-label="调整[面板名称]宽度"`
    - `aria-valuenow`：当前宽度值
    - `aria-valuemin`：最小宽度
    - `aria-valuemax`：最大宽度
  - 聚焦时有明显的视觉反馈（outline 或高亮边框）
- **所有交互元素**：
  - 有明确的视觉反馈
  - 支持屏幕阅读器

### 4.4 安全性要求

- localStorage 数据仅存储布局状态，不包含敏感信息
- 防止 XSS 攻击：不直接将用户输入插入 DOM

## 五、UI 设计规范

### 5.1 布局结构

```
┌─────────────────────────────────────────────────────────┐
│  顶部导航栏（固定高度 56px）                              │
├──────┬──────┬──────┬────────────────────────────────────┤
│ 分组 │ 账号 │ 邮件 │ 邮件详情                            │
│ 面板 │ 面板 │ 列表 │ 面板                                │
│      │      │ 面板 │ （自适应）                          │
│ [▼]  │ [▼]  │ [▼]  │                                    │
│ ├─┤  │ ├─┤  │ ├─┤  │                                │
└──────┴──────┴──────┴────────────────────────────────────┘
  200px  260px  380px   flex: 1

[▼] = 折叠按钮
├─┤ = 拖动分隔条
```

### 5.2 颜色规范

- **拖动区域背景（hover）**: rgba(26, 26, 26, 0.1)
- **拖动指示器**: #1a1a1a
- **折叠按钮背景（hover）**: #f5f5f5
- **折叠按钮图标**: #666

### 5.3 尺寸规范

- **拖动区域宽度**: 4px
- **拖动指示器宽度**: 2px
- **折叠按钮尺寸**: 24x24px
- **折叠后细条宽度**: 48px

### 5.4 动画规范

- **拖动过渡**: 无（实时响应）
- **折叠/展开**: 200ms ease
- **恢复默认布局**: 300ms ease

## 六、技术实现方案

### 6.1 技术栈

- **前端框架**: 无（原生 JavaScript）
- **CSS 预处理器**: 无（原生 CSS）
- **布局系统**: CSS Gr- **状态管理**: localStorage

### 6.2 核心模块

#### 6.2.1 布局管理器（LayoutManager）

**职责**：
- 管理面板宽度和折叠状态
- 处理拖动事件
- 处理折叠/展开事件
- 保存/加载布局状态

**主要方法**：
```javascript
class LayoutManager {
  constructor()
  init()
  startResize(e)
  resize(e)
  stopResize()
  togglePanel(panelName)
  resetLayout()
  saveState()
  loadState()
  updatePanelWidth(panel, width)
}
```

#### 6.2.2 状态持久化（StateManager）

**职责**：
- 读写 localStorage
- 数据格式验证
- 版本兼容性处理

**主要方法**：
```javascript
class StateManager {
  save(state)
  load()
  clear()
  validate(state)
}
```

### 6.3 文件结构

```
static/
├── css/
│   ├── main.css              # 现有样式（需修改）
│   └── layout.css            # 新增：布局系统样式
├── js/
│   ├── main.js               # 现有脚本（需修改）
│   ├── layout-manager.js     # 新增：布局管理器
│   └── state-manager.js      # 新增：状态管理器
templates/
└── index.html                # 主页面（需修改）
```

### 6.4 关键代码片段

#### CSS 变量定义

```css
:root {
  /* 面板初始宽度 */
  --group-panel-width: 200px;
  --account-panel-width: 260px;
  --email-list-panel-width: 380px;

  /* 最小/最大宽度限制 */
  --group-panel-min-width: 150px;
  --group-panel-max-width: 400px;
  --account-panel-min-width: 180px;
  --account-panel-max-width: 500px;
  --email-list-panel-min-width: 280px;
  --email-list-panel-max-width: 600px;
  --email-detail-panel-min-width: 400px;

  /* 折叠状态宽度 */
  --panel-collapsed-width: 0px;
  --panel-collapsed-indicator-width: 48px;

  /* 拖动区域 */
  --resizer-width: 4px;

  /* 动画时长 */
  --panel-transition-duration: 200ms;
}
```

#### Grid 布局

```css
.main-container {
  display: grid;
  grid-template-columns:
    minmax(var(--group-panel-min-width), var(--group-panel-width))
    minmax(var(--account-panel-min-width), var(--account-panel-width))
    minmax(var(--email-list-panel-min-width), var(--email-list-panel-width))
    minmax(var(--email-detail-panel-min-width), 1fr);
  height: calc(100vh - 56px);
  transition: grid-template-columns var(--panel-transition-duration) ease;
}

/* 窗口尺寸自适应 */
@media (max-width: 1200px) {
  .main-container {
    grid-template-columns:
      0px
      minmax(var(--account-panel-min-width), var(--account-panel-width))
      minmax(var(--email-list-panel-min-width), var(--email-list-panel-width))
      minmax(var(--email-detail-panel-min-width), 1fr);
  }
  .group-panel {
    display: none;
  }
}

@media (max-width: 900px) {
  .main-container {
    grid-template-columns:
      0px
      0px
      minmax(var(--email-list-panel-min-width), var(--email-list-panel-width))
      minmax(var(--email-detail-panel-min-width), 1fr);
  }
  .group-panel,
  .account-panel {
    display: none;
  }
}

@media (max-width: 700px) {
  .main-container {
    grid-template-columns: 1fr;
  }
  .group-panel,
  .account-panel,
  .email-list-panel {
    display: none;
  }
}
```

#### 拖动区域样式

```css
.resizer {
  position: absolute;
  top: 0;
  right: 0;
  width: var(--resizer-width);
  height: 100%;
  cursor: col-resize;
  z-index: 10;
  transition: background-color 0.2s;
  /* 可访问性：支持键盘聚焦 */
  outline: none;
}

.resizer:hover,
.resizer:focus {
  background-color: rgba(26, 26, 26, 0.1);
}

.resizer:focus {
  outline: 2px solid #1a1a1a;
  outline-offset: -2px;
}

.resizer::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 2px;
  background-color: transparent;
  transform: translateX(-50%);
  transition: background-color 0.2s;
}

.resizer:hover::after,
.resizer:focus::after {
  background-color: #1a1a1a;
}

/* 折叠状态下隐藏 resizer */
.resizable-panel.collapsed .resizer {
  display: none;
}
```

#### Resizer HTML 结构（支持可访问性）

```html
<div class="resizer"
     role="separator"
     aria-orientation="vertical"
     aria-label="调整分组面板宽度"
     aria-valuenow="200"
     aria-valuemin="150"
     aria-valuemax="400"
     tabindex="0"
     data-resizer="groups">
</div>
```

#### JavaScript 核心逻辑（含所有改进）

```javascript
class LayoutManager {
  constructor() {
    this.isResizing = false;
    this.currentPanel = null;
    this.startX = 0;
    this.startWidth = 0;
    this.pendingSave = null;
    this.init();
  }

  init() {
    // 鼠标拖动
    document.querySelectorAll('.resizer').forEach(resizer => {
      resizer.addEventListener('mousedown', this.startResize.bind(this));
      // 键盘支持
      resizer.addEventListener('keydown', this.handleKeyboard.bind(this));
    });

    document.addEventListener('mousemove', this.resize.bind(this));
    document.addEventListener('mouseup', this.stopResize.bind(this));

    // 窗口尺寸变化监听
    window.addEventListener('resize', this.handleWindowResize.bind(this));

    // 页面卸载时强制保存
    window.addEventListener('beforeunload', this.saveStateNow.bind(this));
  }

  startResize(e) {
    this.isResizing = true;
    const resizerType = e.target.dataset.resizer;
    this.currentPanel = document.querySelector(`[data-panel="${resizerType}"]`);
    this.startX = e.clientX;
    this.startWidth = this.currentPanel.offsetWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }

  resize(e) {
    if (!this.isResizing) return;

    const delta = e.clientX - this.startX;
    let newWidth = this.startWidth + delta;

    // 应用最小/最大宽度限制
    const panelType = this.currentPanel.dataset.panel;
    const minWidth = this.getMinWidth(panelType);
    const maxWidth = this.getMaxWidth(panelType);
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

    // 确保邮件详情面板至少 400px
    const containerWidth = document.querySelector('.main-container').offsetWidth;
    const otherPanelsWidth = this.calculateOtherPanelsWidth(panelType);
    const maxAllowedWidth = containerWidth - otherPanelsWidth - 400;
    newWidth = Math.min(newWidth, maxAllowedWidth);

    this.updatePanelWidth(this.currentPanel, newWidth);
  }

  stopResize() {
    if (this.isResizing) {
      this.isResizing = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      this.saveStateDebounced();
    }
  }

  handleKeyboard(e) {
    const resizer = e.target;
    const panelType = resizer.dataset.resizer;
    const panel = document.querySelector(`[data-panel="${panelType}"]`);
    const currentWidth = panel.offsetWidth;

    let delta = 0;
    if (e.key === 'ArrowLeft') {
      delta = e.shiftKey ? -50 : -10;
    } else if (e.key === 'ArrowRight') {
      delta = e.shiftKey ? 50 : 10;
    } else {
      return;
    }

    e.preventDefault();

    let newWidth = currentWidth + delta;
    const minWidth = this.getMinWidth(panelType);
    const maxWidth = this.getMaxWidth(panelType);
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

    this.updatePanelWidth(panel, newWidth);
    this.updateAriaValue(resizer, newWidth);
    this.saveStateDebounced();
  }

  handleWindowResize() {
    const windowWidth = window.innerWidth;

    // 自动折叠逻辑
    if (windowWidth < 1200) {
      this.collapsePanel('groups', true);
    }
    if (windowWidth < 900) {
      this.collapsePanel('accounts', true);
    }
    if (windowWidth < 700) {
      this.collapsePanel('emails', true);
    }
  }

  updatePanelWidth(panel, width) {
    const panelType = panel.dataset.panel;
    const varName = `--${panelType}-panel-width`;
    document.documentElement.style.setProperty(varName, `${width}px`);
  }

  updateAriaValue(resizer, value) {
    resizer.setAttribute('aria-valuenow', Math.round(value));
  }

  getMinWidth(panelType) {
    const minWidths = {
      'groups': 150,
      'accounts': 180,
      'emails': 280
    };
    return minWidths[panelType] || 150;
  }

  getMaxWidth(panelType) {
    const maxWidths = {
      'groups': 400,
      'accounts': 500,
      'emails': 600
    };
    return maxWidths[panelType] || 600;
  }

  calculateOtherPanelsWidth(excludePanel) {
    const panels = ['groups', 'accounts', 'emails'];
    let total = 0;
    panels.forEach(panel => {
      if (panel !== excludePanel) {
        const el = document.querySelector(`[data-panel="${panel}"]`);
        if (el && !el.classList.contains('collapsed')) {
          total += el.offsetWidth;
        }
      }
    });
    return total;
  }

  saveStateDebounced() {
    if (this.pendingSave) {
      clearTimeout(this.pendingSave);
    }
    this.pendingSave = setTimeout(() => {
      this.saveStateNow();
    }, 500);
  }

  saveStateNow() {
    if (this.pendingSave) {
      clearTimeout(this.pendingSave);
      this.pendingSave = null;
    }

    const userId = this.getCurrentUserId() || 'guest';
    const state = {
      version: '1.1',
      userId: userId,
      timestamp: Date.now(),
      panels: {
        groups: {
          width: getComputedStyle(document.documentElement)
            .getPropertyValue('--groups-panel-width'),
          collapsed: document.querySelector('[data-panel="groups"]')
            .classList.contains('collapsed')
        },
        accounts: {
          width: getComputedStyle(document.documentElement)
            .getPropertyValue('--accounts-panel-width'),
          collapsed: document.querySelector('[data-panel="accounts"]')
            .classList.contains('collapsed')
        },
        emails: {
          width: getComputedStyle(document.documentElement)
            .getPropertyValue('--emails-panel-width'),
          collapsed: document.querySelector('[data-panel="emails"]')
            .classList.contains('collapsed')
        }
      }
    };

    localStorage.setItem(`outlook_layout_state_${userId}`, JSON.stringify(state));
  }

  getCurrentUserId() {
    // 从页面或全局变量获取用户 ID
    return window.currentUserId || null;
  }

  collapsePanel(panelType, auto = false) {
    const panel = document.querySelector(`[data-panel="${panelType}"]`);
    if (!panel) return;

    panel.classList.add('collapsed');
    if (!auto) {
      this.saveStateNow();
    }
  }
}
```

## 七、实施计划

### 7.1 开发阶段

#### 阶段一：基础布局改造（2-3 天）

**任务**：
- [ ] 修改 HTML 结构，添加 resizer 元素
- [ ] 修改 CSS，实现 Grid 布局
- [ ] 添加 CSS 变量系统
- [ ] 确保现有功能不受影响

**验收标准**：
- 页面布局正常显示
- 现有功能（邮件列表、详情查看）正常工作

#### 阶段二：拖动调整功能（2-3 天）

**任务**：
- [ ] 实现 LayoutManager 类
- [ ] 实现拖动事件处理
- [ ] 添加视觉反馈（hover 效果）
- [ ] 优化拖动性能（requestAnimationFrame）

**验收标准**：
- 可以拖动调整每个面板宽度
- 拖动流畅，帧率 60fps
- 有明确的视觉反馈

#### 阶段三：折叠功能（1-2 天）

**任务**：
- [ ] 添加折叠按钮
- [ ] 实现折叠/展开逻辑
- [ ] 添加折叠动画
- [ ] 实现折叠后的细条指示器

**验收标准**：
- 可以折叠/展开每个面板
- 动画平滑自然
- 折叠后有明确的视觉指示

#### 阶段四：状态持久化（1 天）

**任务**：
- [ ] 实现 StateManager 类
- [ ] 实现保存/加载逻辑
- [ ] 添加防抖优化
- [ ] 处理异常情况（localStorage 不可用）

**验收标准**：
- 刷新页面后布局状态恢复
- localStorage 数据格式正确
- 异常情况有降级处理

#### 阶段五：恢复默认布局（1 天）

**任务**：
- [ ] 添加重置按钮
- [ ] 实现确认对话框
- [ ] 实现重置逻辑
- [ ] 添加重置动画

**验收标准**：
- 可以一键恢复默认布局
- 有确认机制防止误操作
- 重置动画平滑

#### 阶段六：测试与优化（2-3 天）

**任务**：
- [ ] 浏览器兼容性测试
- [ ] 性能测试（帧率、内存）
- [ ] 边界情况测试
- [ ] 用户体验优化

**验收标准**：
- 所有主流浏览器正常工作
- 性能指标达标
- 无明显 bug

### 7.2 总体时间估算

- **开发时间**: 9-12 天
- **测试时间**: 2-3 天
- **总计**: 11-15 天

### 7.3 风险评估

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| CSS Grid 兼容性问题 | 高 | 低 | 提前测试目标浏览器，准备降级方案 |
| 拖动性能不佳 | 中 | 中 | 使用 requestAnimationFrame 优化 |
| 现有功能受影响 | 高 | 中 | 充分测试，保持向后兼容 |
| localStorage 不可用 | 低 | 低 | 降级到默认布局，不影响核心功能 |

## 八、验收标准

### 8.1 功能验收

- [ ] 可以拖动调整分组面板宽度
- [ ] 可以拖动调整账号面板宽度
- [ ] 可以拖动调整邮件列表面板宽度
- [ ] 可以折叠/展开分组面板
- [ ] 可以折叠/展开账号面板
- [ ] 可以折叠/展开邮件列表面板
- [ ] 可以一键恢复默认布局
- [ ] 刷新页面后布局状态恢复
- [ ] 拖动时有视觉反馈
- [ ] 折叠/展开有平滑动画

### 8.2 性能验收

- [ ] 拖动时帧率 ≥ 60fps
- [ ] 折叠/展开动画流畅
- [ ] localStorage 数据 ≤ 1KB
- [ ] 页面加载时间增加 ≤ 50ms

### 8.3 兼容性验收

- [ ] Chrome 90+ 正常工作
- [ ] Edge 90+ 正常工作
- [ ] Firefox 88+ 正常工作
- [ ] Safari 14+ 正常工作

### 8.4 用户体验验收

- [ ] 拖动操作直观易懂
- [ ] 折叠按钮位置合理
- [ ] 视觉反馈清晰明确
- [ ] 无明显的交互延迟

## 九、后续优化方向

### 9.1 短期优化（1-2 个月内）

1. **键盘快捷键支持**
   - `Ctrl/Cmd + B` 切换左侧面板
   - `Ctrl/Cmd + \` 切换邮件列表

2. **预设布局模板**
   - 紧凑模式（适合小屏幕）
   - 标准模式（默认）
   - 宽松模式（适合大屏幕）

3. **拖动排序**
   - 支持拖动调整面板顺序

### 9.2 中期优化（3-6 个月内）

1. **移动端适配**
   - 抽屉式侧边栏
   - 触摸手势支持

2. **多套布局方案**
   - 用户可以保存多套布局配置
   - 快速切换不同工作场景

3. **布局分享**
   - 导出布局配置
   - 导入他人的布局配置

## 十、附录

### 10.1 参考资料

- EnsoAI 项目：`E:\hushaokang\Data-code\outlookEmail\exeample\EnsoAI`
- shadcn/ui Sidebar 组件文档
- CSS Grid 布局指南
- localStorage API 文档

### 10.2 术语表

| 术语 | 说明 |
|------|------|
| 面板 | 指分组面板、账号面板、邮件列表面板、邮件详情面板 |
| Resizer | 拖动分隔条，用于调整面板宽度 |
| 折叠 | 隐藏面板内容，宽度变为 0 或显示细条 |
| 展开 | 显示面板内容，恢复到折叠前的宽度 |
| 布局状态 | 包括面板宽度和折叠状态 |
| 默认布局 | 初始的面板宽度和折叠状态 |

### 10.3 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|----------|--------|
| v1.0 | 2026-02-26 | 初始版本 | 开发团队 |
| v1.1 | 2026-02-26 | 根据审查报告修订：<br>1. 添加最小/最大宽度限制<br>2. 添加窗口尺寸自适应策略<br>3. 支持多用户布局隔离<br>4. 添加页面卸载时强制保存<br>5. 明确折叠时的拖动行为<br>6. 增强键盘可访问性支持 | 开发团队 |

### 10.4 审查报告摘要

**审查日期**: 2026-02-26
**审查结果**: 通过（已修订）
**文档质量**: 优秀 (A)

#### 已解决的问题

🔴 **严重问题**：
1. ✅ **缺乏面板拖动的临界值约束** - 已添加明确的最小/最大宽度限制
2. ✅ **浏览器窗口尺寸变化的响应策略不明确** - 已添加媒体查询和自动折叠逻辑

🟡 **中等问题**：
3. ✅ **状态持久化缺乏用户隔离** - 存储键名改为 `outlook_layout_state_${userId}`
4. ✅ **状态保存可能丢失** - 添加 `beforeunload` 事件监听，强制保存
5. ✅ **折叠状态与拖动的逻辑冲突** - 明确折叠时隐藏 resizer

🟢 **低优先级问题**：
6. ✅ **无障碍键盘控制不足** - 添加完整的键盘支持（方向键调整宽度）

#### 改进内容

1. **宽度限制系统**：
   - 分组面板：150px - 400px
   - 账号面板：180px - 500px
   - 邮件列表：280px - 600px
   - 邮件详情：最小 400px

2. **响应式断点**：
   - < 1200px：自动折叠分组面板
   - < 900px：自动折叠账号面板
   - < 700px：自动折叠邮件列表

3. **可访问性增强**：
   - Resizer 支持 Tab 聚焦
   - 支持方向键调整宽度（← / →）
   - 支持 Shift + 方向键快速调整
   - 完整的 ARIA 属性支持

4. **状态管理优化**：
   - 多用户隔离存储
   - 页面卸载时强制保存
   - 防抖机制优化

---

**文档结束**
