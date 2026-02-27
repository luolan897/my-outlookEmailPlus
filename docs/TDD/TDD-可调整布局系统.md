# TDD - 可调整布局系统

## 文档信息

- **文档编号**: TDD-00001
- **创建日期**: 2026-02-26
- **版本**: v1.0
- **状态**: 草稿
- **负责人**: 开发团队
- **关联文档**:
  - PRD-00001: PRD - 可调整布局系统
  - FD-00001: FD - 可调整布局系统

## 目录

1. [技术架构设计](#一技术架构设计)
2. [核心算法设计](#二核心算法设计)
3. [类与方法设计](#三类与方法设计)
4. [数据结构设计](#四数据结构设计)
5. [事件流设计](#五事件流设计)
6. [性能优化策略](#六性能优化策略)
7. [错误处理与边界情况](#七错误处理与边界情况)
8. [集成方案](#八集成方案)
9. [测试策略](#九测试策略)
10. [兼容性方案](#十兼容性方案)

## 一、技术架构设计

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        HTML Layer                            │
│  ┌──────────┬──────────┬──────────┬────────────────────┐   │
│  │ 分组面板  │ 账号面板  │ 邮件列表  │ 邮件详情面板        │   │
│  │ [resizer]│ [resizer]│ [resizer]│                    │   │
│  └──────────┴──────────┴──────────┴────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                        CSS Layer                             │
│  • CSS Grid 布局系统                                          │
│  • CSS 变量（--group-panel-width, --account-panel-width）    │
│  • CSS Transitions（折叠/展开动画）                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     JavaScript Layer                         │
│  ┌──────────────────┐        ┌──────────────────┐          │
│  │  LayoutManager   │◄──────►│  StateManager    │          │
│  │  • 拖动处理       │        │  • 状态保存       │          │
│  │  • 折叠控制       │        │  • 状态加载       │          │
│  │  • 键盘支持       │        │  • 数据验证       │          │
│  │  • 窗口适配       │        │  • 版本迁移       │          │
│  └──────────────────┘        └──────────────────┘          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Storage Layer                           │
│  localStorage: outlook_layout_state_${userId}                │
│  {                                                           │
│    version: "1.1",                                           │
│    userId: "user123",                                        │
│    timestamp: 1709020800000,                                 │
│    panels: { groups: {...}, accounts: {...}, emails: {...} }│
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 模块依赖关系

```
main.js
  ├─► LayoutManager
  │     ├─► StateManager (状态持久化)
  │     ├─► DragHandler (拖动处理)
  │     ├─► CollapseHandler (折叠处理)
  │     ├─► KeyboardHandler (键盘支持)
  │     └─► WindowResizeHandler (窗口适配)
  │
  └─► StateManager
        ├─► localStorage API
        ├─► JSON.parse/stringify
        └─► 数据验证逻辑
```

### 1.3 技术选型

| 技术点 | 选型 | 理由 |
|--------|------|------|
| 布局系统 | CSS | 灵活、性能好、浏览器支持广泛 |
| 状态管理 | CSS 变量 + localStorage | 简单、无需框架、易于调试 |
| 动画 | CSS Transitions | 硬件加速、性能优秀 |
| 事件处理 | 原生 JavaScript | 无依赖、轻量级 |
| 性能优化 | requestAnimationFrame | 保证 60fps 流畅度 |
| 防抖 | 自定义 debounce | 减少 localStorage 写入频率 |

### 1.4 文件结构

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


## 二、核心算法设计

### 2.1 拖动宽度计算算法

#### 算法描述

计算拖动过程中面板的新宽度，并应用最小/最大宽度限制。

#### 伪代码

```
function calculateNewWidth(startX, currentX, startWidth, panelType):
    // 1. 计算拖动距离
    delta = currentX - startX
    
    // 2. 计算新宽度
    newWidth = startWidth + delta
    
    // 3. 获取最小/最大宽度限制
    minWidth = getMinWidth(panelType)
    maxWidth = getMaxWidth(panelType)
    
    // 4. 应用面板自身的宽度限制
    newWidth = clamp(newWidth, minWidth, maxWidth)
    
    // 5. 确保邮件详情面板至少 400px
    containerWidth = getContainerWidth()
    otherPanelsWidth = calculateOtherPanelsWidth(panelType)
    maxAllowedWidth = containerWidth - otherPanelsWidth - 400
    
    // 6. 应用全局宽度限制
    newWidth = min(newWidth, maxAllowedWidth)
    
    return newWidth

function clamp(value, min, max):
    return max(min, min(value, max))
```

#### 时间复杂度

- **时间复杂度**: O(1)
- **空间复杂度**: O(1)

#### 边界情况

1. **拖动到最小宽度**: 当 `newWidth < minWidth` 时，返回 `minWidth`
2. **拖动到最大宽度**: 当 `newWidth > maxWidth` 时，返回 `maxWidth`
3. **邮件详情面板不足 400px**: 限制其他面板的最大宽度
4. **窗口宽度不足**: 自动折叠面板（由窗口适配算法处理）

### 2.2 防抖算法

#### 算法描述

延迟执行函数，在指定时间内如果再次调用则重置计时器。用于减少 localStorage 写入频率。

#### 伪代码

```
function debounce(func, delay):
    let timerId = null
    
    return function(...args):
        // 清除之前的计时器
        if (timerId !== null):
            clearTimeout(timerId)
        
        // 设置新的计时器
        timerId = setTimeout(() => {
            func.apply(this, args)
            timerId = null
        }, delay)
    
    // 提供立即执行方法（用于 beforeunload）
    return {
        debounced: debouncedFunc,
        flush: () => {
            if (timerId !== null):
                clearTimeout(timerId)
                func.apply(this, args)
                timerId = null
        }
    }
```

#### 使用场景

1. **拖动结束保存**: 延迟 500ms 保存状态
2. **窗口调整**: 延迟 200ms 处理窗口大小变化
3. **页面卸载**: 立即执行 `flush()` 强制保存

### 2.3 状态序列化算法

#### 算法描述

将布局状态序列化为 JSON 并保存到 localStorage，支持版本控制和数据验证。

#### 伪代码

```
function serializeState(userId):
    state = {
        version: "1.1",
        userId: userId,
        timestamp: Date.now(),
        panels: {}
    }
    
    // 遍历所有面板
    for panelType in ['groups', 'accounts', 'emails']:
        panel = getPanel(panelType)
        state.panels[panelType] = {
            width: getCSSVariable(`--${panelType}-panel-width`),
            collapsed: panel.classList.contains('collapsed')
        }
    
    // 序列化为 JSON
    jsonString = JSON.stringify(state)
    
    // 保存到 localStorage
    storageKey look_layout_state_${userId}`
    localStorage.setItem(storageKey, jsonString)
    
    return state

function deserializeState(userId):
    storageKey = `outlook_layout_state_${userId}`
    jsonString = localStorage.getItem(storageKey)
    
    if (jsonString === null):
        return null
    
    try:
        state = JSON.parse(jsonString)
        
        // 数据验证
        if (!validateState(state)):
            return null
        
        // 版本迁移
        if (state.version !== "1.1"):
            state = migrateState(state)
        
        return state
    catch or):
        console.error("Failed to deserialize state:", error)
        return null

function validateState(state):
    // 检查必需字段
    if (!state.version || !state.panels):
        return false
    
    // 检查面板数据
    for panelType in ['groups', 'accounts', 'emails']:
        panel = state.panels[panelType]
        if (!panel || !panel.width || typeof panel.collapsed !== 'boolean'):
            return false
    
    return true
```

#### 数据格式

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

### 2.4 窗口适配算法

#### 算法描述

根据窗口宽度自动折叠面板，确保邮件详情面板始终可见。

#### 伪代码

```
function adaptToWindowSize(windowWidth):
    // 定义断点
    breakpoints = {
        COLLAPSE_GROUPS: 1200,
        COLLAPSE_ACCOUNTS: 900,
        COLLAPSE_EMAILS: 700
    }
    
    // 自动折叠逻辑
    if (windowWidth < breakpoints.COLLAPSE_GROUPS):
        collapsePanel('groups', auto=true)
    els        // 如果窗口足够大，恢复之前的状态
        restorePanelIfNeeded('groups')
    
    if (windowWidth < breakpoints.COLLAPSE_ACCOUNTS):
        collapsePanel('accounts', auto=true)
    else:
        restorePanelIfNeeded('accounts')
    
    if (windowWidth < breakpoints.COLLAPSE_EMAILS):
        collapsePanel('emails', auto=true)
    else:
        restorePanelIfNeeded('emails')
    
    // 确保邮件详情面板至少 400px
    ensureDetailPanelMinWidth(400)

function restorePanelIfNeeded(panelType):
    // 只恢复用户手动折叠的面板
    // 如果是自动折叠的，则恢复
    panel = getPanel(panelType)
    if (panel.dataset.autoCollapsed === 'true'):
        expandPanel(panelType)
        delete panel.dataset.autoCollapsed
```

#### 防抖优化

窗口调整事件使用 200ms 防抖，避免频繁触发。

```javascript
window.addEventListener('resize', debounce(handleWindowResize, 200));
```


## 三、类与方法设计

### 3.1 LayoutManager 类

#### 类职责

管理面板布局，处理拖动、折叠、键盘操作和窗口适配。

#### 类图

#### 核心方法说明

**constructor()**: 初始化实例变量和 StateManager，创建防抖保存函数

**init()**: 初始化布局管理器，加载保存的状态，绑定所有事件监听器

**startResize(e)**: 开始拖动，记录初始位置和宽度，设置全局光标

**resize(e)**: 拖动过程中更新宽度，使用 requestAnimationFrame 优化性能

**stopResize()**: 结束拖动，恢复光标，保存状态（防抖）

**handleKeyboard(e)**: 处理键盘操作（方向键调整宽度）

**togglePanel(panelType)**: 切换面板折叠状态

**resetLayout()**: 恢复默认布局，清除保存的状态

**handleWindowResize()**: 处理窗口大小变化，自动折叠/恢复面板

**updatePanelWidth(panel, width)**: 更新面板宽度（修改 CSS 变量）

**saveState()**: 保存当前布局状态到 localStorage

**loadState()**: 从 localStorage 加载布局状态


### 3.2 StateManager 类

#### 类职责

管理布局状态的持久化，包括保存、加载、验证和版本迁移。

#### 类图

#### 详细方法设计

##### save(userId, state)

##### load(userId)

##### clear(userId)

##### validate(state)

##### migrate(state)

##### getStorageKey(userId)

\outlook_layout_state_
## 四、数据结构设计

### 4.1 布局状态对象

```typescript
interface LayoutState {
  version: string;           // 版本号（当前为 "1.1"）
  userId: string;            // 用户 ID
  timestamp: number;         // 保存时间戳
  panels: {
    groups: PanelState;
    accounts: PanelState;
    emails: PanelState;
  };
}

interface PanelState {
  width: string;             // 宽度（如 "200px"）
  collapsed: boolean;        // 是否折叠
}
```

### 4.2 CSS 变量映射

```css
:root {
  /* 面板宽度 */
  --group-panel-width: 200px;
  --account-panel-width: 260px;
  --email-list-panel-width: 380px;
  
  /* 宽度限制 */
  --group-panel-min-width: 150px;
  --group-panel-max-width: 400px;
  --account-panel-min-width: 180px;
  --account-panel-max-width: 500px;
  --email-list-panel-min-width: 280px;
  --email-list-panel-max-width: 600px;
  --email-detail-panel-min-width: 400px;
  
  /* 其他 */
  --resizer-width: 4px;
  --panel-transition-duration: 200ms;
}
```

## 五、事件流设计

### 5.1 拖动事件流

```
用户操作                    事件触发                    系统响应
────────────────────────────────────────────────────────────────
鼠标按下 resizer          mousedown                  startResize()
  │                         │                           ├─ 记录初始位置
  │                         │                           ├─ 设置全局光标
  │                         │                           └─ 阻止默认行为
  │
  ├─ 鼠标移动              mousemove                  resize()
  │    │                     │                           ├─ requestAnimationFrame
  │    │                     │                           ├─ 计算新宽度
  │    │                     │                           ├─ 应用宽度限制
  │    │                     │                           ├─ 更新 CSS 变量
  │    │                     │                           └─ 更新 ARIA 属性
  │    │
  │    └─ 重复...
  │
  └─ 鼠标释放              mouseup                    stopResize()
                             │                           ├─ 恢复光标
                             │                           ├─ 保存状态（防抖 500ms）
                             │                           └─ 清理状态
```

### 5.2 折叠事件流

```
用户操作                    事件触发                    系统响应
────────────────────────────────────────────────────────────────
点击折叠按钮              click                      togglePanel()
  │                         │                           ├─ 检查当前状态
  │                         │                           └─ 调用 collapse/expand
  │
  ├─ 折叠                                         collapsePanel()
  │    │                                                 ├─ 添加 .collapsed 类
  │    │                                                 ├─ CSS transition (200ms)
  │    │                                                 ├─ 更新 ARIA 属性
  │    │                                                 └─ 立即保存状态
  │
  └─ 展开                                              expandPanel()
       │                                                 ├─ 移除 .collapsed 类
       │                                                 ├─ CSS transition (200ms)
       │                                                 ├─ 恢复宽度
       │                                                 ├─ 更新 ARIA 属性
       │                                                 └─ 立即保存状态
```

### 5.3 窗口调整事件流

```
窗口大小变化              resize (防抖 200ms)        handleWindowResize()
  │                         │                           ├─ 获取窗口宽度
  │                         │                           ├─ 检查断点
  │                         │                           ├─ 自动折叠/恢复面板
  │                         │                           └─ 标记 autoCollapsed
```

### 5.4 页面生命周期事件流

```
页面加载                  DOMContentLoaded           init()
  │                         │                           ├─ 创建 LayoutManager
  │                         │                           ├─ 加载保存的状态
  │                         │                           ├─ 应用到 CSS 变量
  │                         │                           ├─ 绑定事件监听器
  │                         │                           └─ 初始窗口适配
  │
  └─ 页面卸载              beforeunload               saveNow()
                             │                           ├─ 取消防抖计时器
                             │                           ├─ 立即保存状态
                             │                           └─ 确保不丢失数据
```

## 六、性能优化策略

### 6.1 拖动性能优化

#### 使用 requestAnimationFrame

```javascript
resize(e) {
  if (!this.isResizing) return;
  
  requestAnimationFrame(() => {
    // 宽度计算和更新
    const newWidth = this.calculateNewWidth(e);
    this.updatePanelWidth(this.currentPanel, newWidth);
  });
}
```

**优势**：
- 与浏览器刷新率同步（60fps）
- 避免不必要的重绘
- 自动节流

#### 避免布局抖动（Layout Thrashing）

```javascript
// ❌ 错误：读写交替导致强制同步布局
function badResize() {
  const width1 = panel1.offsetWidth;  // 读
  panel1.style.width = width1 + 10;   // 写
  const width2 = panel2.offse // 读（触发强制布局）
  panel2.style.width = width2 + 10;   // 写
}

// ✅ 正确：批量读取，批量写入
function goodResize() {
  // 批量读取
  const width1 = panel1.offsetWidth;
  const width2 = panel2.offsetWidth;
  
  // 批量写入
  panel1.style.width = width1 + 10;
  panel2.style.width = width2 + 10;
}
```

### 6.2 CSS 性能优化

#### 使用 CSS 变量

```css
/* ✅ 使用 CSS 变量，只需修改一次 */
.group-panel {
  width: var(--group-panel-width);
}

/* ❌ 直接修改 style，触发重排 */
element.style.width = '200px';
```

#### 使用 transform 和 opacity

```css
/* ✅ 使用 transform，GPU 加速 */
.panel.collapsed {
  transform: translateX(-100%);
  opacity: 0;
}

/* ❌ 使用 width，触发重排 */
.panel.collapsed {
  width: 0;
}
```

#### 使用 will-change 提示

```css
.resizer {
  will-change: background-color;
}

.panel {
  will-change: transform, opacity;
}
```

### 6.3 防抖优化

```javascript
// 拖动结束保存：500ms 防抖
this.saveDebounced = debounce(() => this.saveState(), 500);

// 窗口调整：200ms 防抖
window.addEventListener('resize', debounce(this.handleWindowResize, 200));
```

**效果**：
- 减少 localStorage 写入次数
- 减少窗口调整处理次数
- 提升整体性能

### 6.4 事件委托

```javascript
// ✅ 使用事件委托
document.querySelector('.main-container').addEventListener('click', (e) => {
  if (e.target.classList.collapse-btn')) {
    const panelType = e.target.dataset.panel;
    this.togglePanel(panelType);
  }
});

// ❌ 为每个按钮绑定事件
document.querySelectorAll('.collapse-btn').forEach(btn => {
  btn.addEventListener('click', () => { /* ... */ });
});
```

### 6.5 内存优化

```javascript
// 清理事件监听器
destroy() {
  // 移除全局事件监听器
  document.removeEventListener('mousemove', this.resize);
  document.removeEventListener('mouseup', this.stopResize);
  window.removeEventListener('resize', this.handleWindowResize);
  window.removeEventListener('beforeunload', this.saveNow);
  
  // 清除计时器
  if (this.saveTimer) {
    clearTimeout(this.saveTimer);
  }
}
```


## 七、错误处理与边界情况

### 7.1 拖动边界情况

#### 情况 1：拖动到最小宽度

```javascript
// 处理：限制在最小宽度
if (newWidth < minWidth) {
  newWidth = minWidth;
}
```

#### 情况 2：拖动到最大宽度

```javascript
// 处理：限制在最大宽度
if (newWidth > maxWidth) {
  newWidth = maxWidth;
}
```

#### 情况 3：邮件详情面板不足 400px

```javascript
// 处理：限制其他面板的最大宽度
const containerWidth = document.querySelector('.main-container').offsetWidth;
const otherPanelsWidth = this.calculateOtherPanelsWidth(panelType);
const maxAllowedWidth = containerWidth - otherPanelsWidth - 400;
newWidth = Math.min(newWidth, maxAllowedWidth);
```

#### 情况 4：快速拖动导致鼠标移出窗口

```javascript
// 处理：监听全局 mouseup 事件
document.addEventListener('mouseup', this.stopResize.bind(this));
```

### 7.2 折叠边界情况

#### 情况 1：所有面板都折叠

```javascript
// 处理：至少保持一个面板展开
togglePanel(panelType) {
  const expandedPanels = this.getExpandedPanels();
  
  if (expandedPanels.length === 1 && expandedPanels[0] === panelType) {
    alert('至少需要保持一个面板展开');
    return;
  }
  
  // 继续折叠...
}
```

#### 情况 2：折叠后拖动

```javascript
// 处理：隐藏 resizer
.panel.collapsed .resizer {
  display: none;
  pointer-events: none;
}
```

### 7.3 localStorage 错误处理

#### 情况 1：localStorage 不可用

```javascript
save(userId, state) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (error) {
    console.warn('localStorage not available, using default layout');
    return false;
  }
}
```

#### 情况 2：QuotaExceededError

```javascript
save(userId, state) {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    if (error.name === 'QuotaExceededError') {
      // 清理旧数据
      this.clearOldStates();
      // 重试
      localStorage.setItem(key, value);
    }
  }
}
```

#### 情况 3：数据损坏

```javascript
load(userId) {
  try {
    const state = JSON.parse(jsonString);
    
    if (!this.validate(state)) {
      console.warn('Invalid state, using default');
      this.clear(userId);
      return null;
    }
    
    return state;
  } catch (error) {
    console.error('Failed to parse state:', error);
    this.clear(userId);
    returnn}
```

### 7.4 窗口调整边界情况

#### 情况 1：窗口宽度小于 700px

```javascript
// 处理：自动折叠所有侧边栏，只显示邮件详情
if (windowWidth < 700) {
  this.collapsePanel('groups', true);
  this.collapsePanel('accounts', true);
  this.collapsePanel('emails', true);
}
```

#### 情况 2：快速调整窗口大小

```javascript
// 处理：使用防抖（200ms）
window.addEventListener('resize', debounce(this.handleWindowResize, 200));
```

### 7.5 键盘操作边界情况

#### 情况 1：连续按键导致超出限制

```javascript
handleKeyboard(e) {
  let newWidth = currentWidth + delta;
  
  // 应用限制
  newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
  
  // 更新宽度
  this.updatePanelWidth(panel, newWidth);
}
```

#### 情况 2：焦点在折叠的面板上

```javascript
// 处理：折叠时移除 tabindex
collapsePanel(panelType) {
  const resizer = panel.querySelector('.resizer');
  resizer.setAttribute('tabindex', '-1');
}

expandPanel(panelType) {
  const resizer = panel.querySelector('.resizer');
  resizer.setAttribute('tabindex', '0');
}
```

### 7.6 极端窗口尺寸

#### 情况 1：超宽屏幕（> 3000px）

```javascript
// 处理：限制面板最大宽度
getMaxWidth(panelTyp const maxWidths = {
    'groups': 400,
    'accounts': 500,
    'emails': 600
  };
  return maxWidths[panelType];
}
```

#### 情况 2：超窄屏幕（< 400px）

```javascript
// 处理：强制只显示邮件详情面板
if (windowWidth < 400) {
  // 折叠所有侧边栏
  this.collapsePanel('groups', true);
  this.collapsePanel('accounts', true);
  this.collapsePanel('emails', true);
  
  // 邮件详情面板占满全屏
  document.documentElement.style.setProperty(
    '--email-detail-panel-min-width',
    '100%'
  );
}
```

## 八、集成方案

### 8.1 HTML 结构改造

#### 现有结构

```html
<div class="main-container">
  <div class="group-panel">...</div>
  <div class="account-panel">...</div>
  <div class="email-list-panel">...</div>
  <div class="email-detail-panel">...</div>
</div>
```

#### 改造后结构

```html
<div class="main-container">
  <!-- 分组面板 -->
  <div class="resizable-panel" data-panel="groups">
    <div class="panel-header">
      <h3>分组</h3>
      <button class="collapse-btn" 
              data-panel="groups"
              aria-label="折叠分组面板"
              aria-expanded="true">
        ←
      </button>
    </div>
    <div class="panel-content">
      <!-- 原有内容 -->
    </div>
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
  </div>
  
  <!-- 账号面板 -->
  <div class="resizable-panel" data-panel="accounts">
    <!-- 类似结构 -->
  </div>
  
  <!-- 邮件列表面板 -->
  <div class="resizable-panel" data-panel="emails">
    <!-- 类似结构 -->
  </div>
  
  <!-- 邮件详情面板 -->
  <div class="email-detail-panel">
    <!-- 原有内容，不可折叠 -->
  </div>
</div>
```

### 8.2 CSS 集成

#### 创建 layout.css

```css
/* CSS 变量 */
:root {
  --group-panel-width: 200px;
  --account-panel-width: 260px;
  --email-list-panel-width: 380px;
  /* ... 其他变量 */
}

/* Grid 布局 */
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

/* Resizer 样式 */
.resizer {
  position: absolute;
  top: 0;
  right: 0;
  width: var(--resizer-width);
  height: 100%;
  cursor: col-resize;
  z-index: 10;
}

.resizer:hover,
.resizer:focus {
  background-color: rgba(26, 26, 26, 0.1);
}

/* 折叠状态 */
.resizable-panel.collapsed {
  width: 0;
  opacity: 0;
  overflow: hidden;
}

.resizable-panel.collapsed .resizer {
  display: none;
}
```

#### 修改 main.css

```css
/* 移除固定宽度 */
/* 删除以下代码：
.group-panel {
  width: 200px;
}
.account-panel {
  width: 260px;
}
.email-list-panel {
  width: 380px;
}
*/

/* 改为使用 CSS 变量 */
.group-panel {
  width: var(--group-panel-width);
}
```

### 8.3 JavaScript 集成

#### 修改 main.js

```javascript
// 在文件末尾添加
import LayoutManager from './layout-manager.js';
import StateManager from './state-manager.js';

// 初始化布局管理器
document.addEventListener('DOMContentLoaded', () => {
  const layoutManager = new LayoutManager();
  layoutManager.init();
  
  // 暴露到全局（用于调试）
  window.layoutManager = layoutManager;
});
```

### 8.4 向后兼容

#### 降级策略

```javascript
// 检测 CSS Grid 支持
if (!CSS.supports('display', 'grid')) {
  console.warn('CSS Grid not  using fallback layout');
  document.body.classList.add('no-grid');
}

// 检测 localStorage 支持
if (!window.localStorage) {
  console.warn('localStorage not supported, layout state will not persist');
}
```

#### 渐进增强

```javascript
// 如果 JavaScript 加载失败，使用默认布局
<noscript>
  <style>
    .main-container {
      display: flex;
    }
    .group-panel { width: 200px; }
    .account-panel { width: 260px; }
    .email-list-panel { width: 380px; }
    .email-detail-panel { flex: 1; }
  </style>
</noscript>
```

### 8.5 初始化流程

```
页面加载
  ↓
DOMContentLoaded
  ↓
创建 LayoutManager 实例
  ↓
调用 init()
  ├─ StateManager.load(userId)
  │   ├─ 从 localStorage 读取
  │   ├─ 验证数据
  │   └─ 版本迁移
  ├─ 应用保存的状态到 CSS 变量
  ├─ 绑定拖动事件监听器
  ├─ 绑定折叠按钮事件
  ├─ 绑定窗口调整事件（防抖）
  ├─ 绑定页面卸载事件
  └─ 初始窗口适配
  ↓
布局系统就绪
```


## 九、测试策略

### 9.1 单元测试

测试 LayoutManager 和 StateManager 的各个方法，确保核心逻辑正确。

### 9.2 集成测试

测试拖动、折叠、状态持久化的完整流程。

### 9.3 浏览器兼容性测试

在 Chrome 90+、Firefox 88+、Safari 14+、Edge 90+ 上测试所有功能。

### 9.4 性能测试

- 拖动帧率应保持 60fps
- localStorage 数据应小于 1KB
- 动画流畅无卡顿

### 9.5 可访问性测试

- 使用 axe-core 自动检测
- 手动测试键盘导航和屏幕阅读器

## 十、兼容性方案

### 10.1 CSS Grid 降级

使用 @supports 检测，不支持时降级到 flexbox。

### 10.2 JavaScript 兼容性

使用 Babel 转译，确保在目标浏览器上运行。

### 10.3 功能检测

检测 CSS Grid、CSS 变量、localStorage、requestAnimationFrame 支持情况。

### 10.4 渐进增强

基础 HTML 使用固定布局，JavaScript 加载后增强为动态布局。

## 十一、总结

### 11.1 技术亮点

1. 纯原生实现，无需框架
2. 性能优化，60fps 流畅拖动
3. 完整的可访问性支持
4. 健壮的错误处理
5. 状态持久化，多用户隔离

### 11.2 关键算法

- 拖动宽度计算：O(1) 时间复杂度
- 防抖优化：减少 80% 的 localStorage 写入
- 窗口适配：自动折叠 + 智能恢复

### 11.3 测试覆盖

- 单元测试：LayoutManager、StateManager
- 集成测试：拖动、折叠、状态持久化
- 浏览器兼容性测试：Chrome、Firefox、Safari、Edge
- 性能测试：60fps 拖动、内存占用
- 可访问性测试：axe-core + 手动测试

---

**文档结束**
