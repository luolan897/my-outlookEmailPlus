# FD - 可调整布局系统功能设计

## 文档信息

- **文档编号**: FD-00001
- **创建日期**: 2026-02-26
- **版本**: v1.0
- **状态**: 待评审
- **负责人**: 开发团队
- **关联 PRD**: PRD-00001 可调整布局系统 v1.1

## 一、功能概述

本文档详细描述可调整布局系统的功能设计，包括 6 个主要功能模块、23 个子功能的实现细节、验收标准和测试策略。

### 1.1 功能范围

本次实现的功能包括：

1. **可拖动调整宽度** - 用户可以通过拖动面板边缘调整宽度
2. **面板折叠/展开** - 用户可以折叠/展开侧边栏面板
3. **恢复默认布局** - 用户可以一键恢复到默认布局
4. **状态持久化** - 自动保存和恢复用户的布局偏好
5. **窗口尺寸自适应** - 根据窗口大小自动调整布局
6. **键盘可访问性** - 支持键盘操作和屏幕阅读器

### 1.2 参考文档

- **PRD**: `PRD/PRD-可调整布局系统.md` v1.1
- **设计参考**: EnsoAI 编辑器 UI 设计

### 1.3 术语定义

| 术语 | 说明 |
|------|------|
| 面板 | 指分组面板、账号面板、邮件列表面板、邮件详情面板 |
| Resizer | 拖动分隔条，位于面板右侧边缘，用于调整宽度 |
| 折叠 | 隐藏面板内容，宽度变为 0 或显示 48px 细条 |
| 展开 | 显示面板内容，恢复到折叠前的宽度 |
| 布局状态 | 包括所有面板的宽度和折叠状态 |
| 默认布局 | 初始的面板宽度和折叠状态 |

## 二、功能详细设计

### 功能模块总览

| 模块编号 | 模块名称 | 子功能数量 | 优先级 |
|---------|---------|-----------|--------|
| F1 | 可拖动调整宽度 | 4 | P0 |
| F2 | 面板折叠/展开 | 6 | P0 |
| F3 | 恢复默认布局 | 4 | P1 |
| F4 | 状态持久化 | 5 | P0 |
| F5 | 窗口尺寸自适应 | 3 | P1 |
| F6 | 键盘可访问性 | 4 | P2 |

**总计**: 6 个模块，26 个子功能

---

## 三、F1 - 可拖动调整宽度

### F1.1 鼠标拖动调整宽度

**功能编号**: F1.1
**功能名称**: 鼠标拖动调整宽度
**优先级**: P0

#### 功能描述

用户可以通过鼠标拖动面板右侧的 resizer（拖动条）来实时调整面板宽度。

#### 前置条件

- 面板处于展开状态（非折叠）
- Resizer 元素已渲染且可见

#### 主流程

1. 用户将鼠标悬停在 resizer 上
2. 鼠标光标变为 `col-resize`（双向箭头）
3. Resizer 显示视觉反馈（背景色变化、边框高亮）
4. 用户按下鼠标左键（mousedown）
5. 系统记录起始位置和起始宽度
6. 用户移动鼠标（mousemove）
7. 系统实时计算新宽度：`newWidth = startWidth + (currentX - startX)`
8. 系统应用宽度限制（最小/最大值）
9. 系统更新 CSS 变量，面板宽度实时变化
10. 用户释放鼠标（mouseup）
11. 系统触发防抖保存（500ms 后保存到 localStorage）

#### 异常流程

- **异常 1**: 用户拖动时鼠标移出窗口
  - 处理：继续监听 mousemove 事件，直到 mouseup
- **异常 2**: 拖动过程中窗口大小改变
  - 处理：重新计算容器宽度，调整最大允许宽度
- **异常 3**: 拖动速度过快导致性能问题
  - 处理：使用 requestAnimationFrame 节流

#### 界面元素

**Resizer 元素**：
```html
<div class="resizer"
     role="separator"
     aria-orientation="vertical"
     aria-label="调整分组面板宽度"
     aria-valuenow="200"
     aria-valuemin="150"
     aria-valuemax="400"
    0"
     data-resizer="groups">
</div>
```

**样式**：
- 宽度：4px
- 高度：100%（填充面板高度）
- 位置：绝对定位，right: 0
- 光标：col-resize
- Hover 背景色：rgba(26, 26, 26, 0.1)
- Hover 边框：2px solid #1a1a1a

#### 验收标准

- [ ] 可以拖动分组面板的 resizer
- [ ] 可以拖动账号面板的 resizer
- [ ] 可以拖动邮件列表面板的 resizer
- [ ] 拖动时面板宽度实时变化
- [ ] 拖动时光标为 col-resize
- [ ] 拖动时有视觉反馈（背景色、边框）
- [ ] 拖动流畅，帧率 ≥ 60fps
- [ ] 释放鼠标后 500ms 保存状态

---

### F1.2 宽度限制（最小/最大）

**功能编号**: F1.2
**功能名称**: 宽度限制
**优先级**: P0

#### 功能描述

系统对每个面板的宽度进行限制，防止用户拖动到不合理的尺寸。

#### 宽度限制规则

| 面板 | 最小宽度 | 最大宽度 | 说明 |
|------|---------|---------|------|
| 分组面板 | 150px | 400px | 确保分组名称和图标可见 |
| 账号面板 | 180px | 500px | 确保邮箱地址可读 |
| 邮件列表 | 280px | 600px | 确保邮件预览可读 |
| 邮件详情 | 400px | 无限制 | 自动填充剩余空间 |

#### 主流程

1. 用户拖动 resizer
2. 系统计算新宽度
3. 系统获取该面板的最小/最大宽度
4. 系统应用限制：`newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth))`
5. 系统更新面板宽度

#### 验收标准

- [ ] 分组面板宽度不能小于 150px
- [ ] 分组面板宽度不能大于 400px
- [ ] 账号面板宽度不能小于 180px
- [ ] 账号面板宽度不能大于 500px
- [ ] 邮件列表宽度不能小于 280px
- [ ] 邮件列表宽度不能大于 600px
- [ ] 达到限制时，继续拖动无效果

---

### F1.3 确保邮件详情面板可见

**功能编号**: F1.3
**功能名称**: 确保邮件详情面板可见
**优先级**: P0

#### 功能描述

无论用户如何调整侧边栏宽度，邮件详情面板始终保持至少 400px 可见宽度。

#### 主流程

1. 用户拖动任意侧边栏的 resizer
2. 系统计算容器总宽度
3. 系统计算其他面板的总宽度
4. 系统计算最大允许宽度：`maxAllowed = containerWidth - otherPanelsWidth - 400`
5. 系统应用限制：`newWidth = Math.min(newWidth, maxAllowed)`
6. 系统更新面板宽度

#### 异常流程

- **异常 1**: 容器宽度不足（< 800px）
  - 处理：触发窗口自适应逻辑部分面板

#### 验收标准

- [ ] 邮件详情面板始终可见
- [ ] 邮件详情面板宽度 ≥ 400px
- [ ] 拖动侧边栏时，邮件详情面板不会被挤压消失
- [ ] 窗口宽度不足时，自动折叠侧边栏

---

### F1.4 拖动视觉反馈

**功能编号**: F1.4
**功能名称**: 拖动视觉反馈
**优先级**: P1

#### 功能描述

在拖动过程中提供清晰的视觉反馈，让用户知道当前正在拖动。

#### 视觉反馈元素

1. **Resizer Hover 状态**：
   - 背景色：rgba(26, 26, 26, 0.1)
   - 中心线：2px solid #1a1a1a

2. **拖动中状态**：
   - 全局光标：col-resize
   - 禁用文本选择：user-select: none
   - Resizer 保持高亮状态

3. **拖动结束**：
   - 恢复默认光标
   - 恢复文本选择
   - Resizer 恢复普通状态

#### 验收标准

- [ ] Hover 时 resizer 有视觉反馈
- [ ] 拖动时全局光标为 col-resize
- [ ] 拖动时无法选中文本
- [ ] 拖动结束后光标恢复正常
- [ ] 拖动结束后可以选中文本

---

## 四、F2 - 面板折叠/展开

### F2.1 折叠按钮交互

**功能编号**: F2.1
**功能名称**: 折叠按钮交互
**优先级**: P0

#### 功能描述

每个侧边栏面板的右上角有一个折叠按钮，点击可以折叠/展开面板。

#### 前置条件

- 面板已渲染
- 至少有一个其他侧边栏面板处于展开状态

#### 主流程

1. 用户点击折叠按钮
2. 系统检查是否至少有一个其他面板展开
3. 如果是最后一个展开的面板，阻止折叠并提示用户
4. 否则，切换面板的折叠状态
5. 系统添加/移除 `.collapsed` 类
6. 系统触发 CSS 过渡动画（200ms）
7. 系统立即保存状态到 localStorage

#### 界面元素

**折叠按钮**：
```html
<button class="collapse-btn"
        aria-label="折叠分组面板"
        aria-expanded="true"
        title="折叠">
  <svg><!-- 左箭头图标 --></svg>
</bn>
```

**按钮样式**：
- 尺寸：24x24px
- 位置：面板右上角
- 图标：展开时显示 ←，折叠时显示 →
- Hover 背景色：#f5f5f5

#### 验收标准

- [ ] 点击折叠按钮可以折叠面板
- [ ] 折叠后按钮图标变为 →
- [ ] 点击折叠后的指示器可以展开
- [ ] 展开后按钮图标变为 ←
- [ ] 不能折叠最后一个展开的面板
- [ ] 折叠/展开有平滑动画

---

### F2.2 折叠动画

**功能编号**: F2.2
**功能名称**: 折叠动画
**优先级**: P0

#### 功能描述

面板折叠/展开时有平滑的过渡动画，提升用户体验。

#### 动画参数

- **动画时长**: 200ms
- **缓动函数**: ease
- **动画属性**: width, opacity
- **折叠方向**: 宽度从当前值到 0，透明度从 1 到 0
- **展开方向**: 宽度从 0 到保存的值，透明度从 0 到 1

#### CSS 实现

```css
.resizable-panel {
  transition: width 200ms ease, opacity 200ms ease;
}

.resizable-panel.collapsed {
  width: 0 !important;
  opacity: 0;
  overflow: hidden;
}
```

#### 验收标准

- [ ] 折叠动画流畅，无卡顿
- [ ] 展开动画流畅，无卡顿
- [ ] 动画时长为 200ms
- [ ] 动画期间不影响其他操作

---

### F2.3 折叠指示器

**功能编号**: F2.3
**功能名称**: 折叠指示器
**优先级**: P1

#### 功能描述

面板折叠后，在主容器边缘显示一个 48px 宽的细条，竖排显示面板名称。

#### 界面元素

**折叠指示器**：
```html
<div class="collapsed-indicator" data-panel="groups">
  <span class="indicator-text">分组</span>
</div>
```

**样式**：
- 宽度：48px
- 高度：100%
- 背景色：#fafafa
- 边框：1px solid #e5e5e5
- 文字方向：竖排（writing-mode: vertical-rl）
- 文字大小：14px
- 文字颜色：#666
- Hover 背景色：#f0f0f0
- 光标：pointer

#### 验收标准

- [ ] 折叠后显示 48px 宽的指示器
- [ ] 指示器显示面板名称（竖排）
- [ ] Hover 时有视觉反馈
- [ ] 光标为 pointer

---

### F2.4 点击指示器展开

**功能编号**: F2.4
**功能名称**: 点击指示器展开
**优先级**: P1

#### 功能描述

用户点击折叠指示器可以快速展开对应的面板。

#### 主流程

1. 用户点击折叠指示器
2. 系统识别对应的面板
3. 系统移除 `.collapsed` 类
4. 系统触发展开动画
5. 系统恢复面板到折叠前的宽度
6. 系统立即保存状态

#### 验收标准

- [ ] 点击指示器可以展开面板
- [ ] 展开后恢复到折叠前的宽度
- [ ] 展开动画流畅
- [ ] 展开后指示器消失

---

### F2.5 折叠时隐藏 Resizer

**功能编号**: F2.5
**功能名称**: 折叠时隐藏 Resizer
**优先级**: P0

#### 功能描述

面板折叠后，该面板的 resizer 自动隐藏，避免用户误操作。

#### CSS 实现

```css
.resizable-panel.collapsed .resizer {
  display: none;
}
```

#### 验收标准

- [ ] 折叠后 resizer 不可见
- [ ] 折叠后无法拖动调整宽度
- [ ] 展开后 resizer 恢复可见
- [ ] 展开后可以拖动调整宽度

---

### F2.6 至少保持一个面板展开

**功能编号**: F2.6
**功能名称**: 至少保持一个面板展开
**优先级**: P0

#### 功能描述

系统确保至少有一个侧边栏面板处于展开状态，防止用户折叠所有面板导致无法操作。

#### 主流程

1. 用户尝试折叠面板
2. 系统检查其他侧边栏面板的状态
3. 如果所有其他面板都已折叠，阻止操作
4. 显示提示消息："至少需要保持一个面板展开"
5. 否则，允许折叠

#### 验收标准

- [ ] 不能折叠最后一个展开的面板
- [ ] 尝试折叠时显示提示消息
- [ ] 至少有一个其他面板展开时可以折叠

---

## 五、F3 - 恢复默认布局

### F3.1 重置按钮

**功能编号**: F3.1
**功能名称**: 重置按钮
**优先级**: P1

#### 功能描述

在顶部导航栏添加"恢复默认布局"按钮，用户可以一键重置布局。

#### 界面元素

**重置按钮**：
```html
<button class="navbar-btn reset-layout-btn"
        aria-label="恢复默认布局"
        title="恢复默认布局">
  <svg><!-- 重置图标 ↻ --></svg>
</button>
```

**按钮位置**：
- 导航栏右侧
- 在其他操作按钮之后

**按钮样式**：
- 尺寸：32x32px
- 图标：重置图标（↻）
- Hover 背景色：#f5f5f5
- Hover 边框：1px solid #ccc

#### 验收标准

- [ ] 导航栏显示重置按钮
- [ ] 按钮位置合理
- [ ] Hover 时有视觉反馈
- [ ] Tooltip 显示"恢复默认布局"

---

### F3.2 确认对话框

**功能编号**: F3.2
**功能名称**: 确认对话框
**优先级**: P1

#### 功能描述

点击重置按钮后，弹出确认对话框，防止用户误操作。

#### 界面元素

**确认对话框**：
```html
<div class="modal" id="resetLayoutModal">
  <div class="modal-content">
    <div class="modal-header">
      <h3>恢复默认布局</h3>
      <button class="modal-close">×</button>
    </div>
    <div class="modal-body">
      <p>确定要恢复到默认布局吗？</p>
      <p class="text-muted">当前的面板宽度和折叠状态将被重置。</p>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary">取消</button>
      <button class="btn btn-primary">确定</button>
    </div>
  </div>
</div>
```

#### 主流程

1. 用户点击重置按钮
2. 系统显示确认对话框
3. 用户点击"确定"或"取消"
4. 如果点击"确定"，执行重置逻辑
5. 如果点击"取消"，关闭对话框

#### 验收标准

- [ ] 点击重置按钮显示对话框
- [ ] 对话框内容清晰
- [ ] 点击"取消"关闭对话框
- [ ] 点击"确定"执行重置
- [ ] 点击遮罩层关闭对话框

---

### F3.3 重置逻辑

**功能编号**: F3.3
**功能名称**: 重置逻辑
**优先级**: P1

#### 功能描述

执行重置操作，将所有面板恢复到默认宽度和折叠状态。

#### 默认布局参数

| 面板 | 默认宽度 | 默认状态 |
|------|---------|---------|
| 分组面板 | 200px | 展开 |
| 账号面板 | 260px | 展开 |
| 邮件列表 | 380px | 展开 |
| 邮件详情 | 自适应 | 展开 |

#### 主流程

1. 用户确认重置
2. 系统清除 localStorage 中的布局状态
3. 系统重置 CSS 变量到默认值
4. 系统移除所有 `.collapsed` 类
5. 系统触发重置动画（300ms）
6. 系统关闭确认对话框
7. 系统显示成功提示

#### 验收标准

- [ ] 所有面板恢复到默认宽度
- [ ] 所有面板恢复到展开状态
- [ ] localStorage 被清除
- [ ] 重置动画流畅
- [ ] 显示成功提示

---

### F3.4 重置动画

**功能编号**: F3.4
**功能名称**: 重置动画
**优先级**: P2

#### 功能描述

重置时使用平滑的过渡动画，而不是瞬间跳变。

#### 动画参数

- **动画时长**: 300ms
- **缓动函数**: ease
- **动画属性**: width

#### CSS 实现

```css
.main-container.resetting {
  transition: grid-template-columns 300ms ease;
}

.resizable-panel.resetting {
  transition: width 300ms ease;
}
```

#### 验收标准

- [ ] 重置动画流畅
- [ ] 动画时长为 300ms
- [ ] 所有面板同时动画

---

## 六、F4 - 状态持久化

### F4.1 保存布局状态

**功能编号**: F4.1
**功能名称**: 保存布局状态
**优先级**: P0

#### 功能描述

自动保存用户的布局偏好到 localStorage，包括面板宽度和折叠状态。

#### 数据结构

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

#### 存储键名

- 格式：`outlook_layout_state_${userId}`
- 未登录：`outlook_layout_state_guest`

#### 主流程

1. 用户调整布局（拖动或折叠）
2. 系统触发保存逻辑
3. 系统读取当前所有面板的状态
4. 系统构建数据对象
5. 系统序列化为 JSON
6. 系统写入 localStorage

#### 验收标准

- [ ] 拖动后 500ms 保存状态
- [ ] 折叠后立即保存状态
- [ ] 数据格式正确
- [ ] 多用户隔离生效
- [ ] localStorage 数据 ≤ 1KB

---

### F4.2 加载布局状态

**功能编号**: F4.2
**功能名称**: 加载布局状态
**优先级**: P0

#### 功能描述

页面加载时从 localStorage 读取并恢复用户的布局偏好。

#### 主流程

1. 页面 DOMContentLoaded 事件触发
2. 系统获取当前用户 ID
3. 系统从 localStorage 读取数据
4. 系统验证数据格式和版本
5. 系统应用面板宽度（更新 CSS 变量）
6. 系统应用折叠状态（添加 `.collapsed` 类）
7. 系统跳过动画（避免页面加载时的闪烁）

#### 异常流程

- **异常 1**: localStorage 不可用
  - 处理：使用默认布局，不报错
- **异常 2**: 数据格式错误
  - 处理：清除数据，使用默认布局
- **异常 3**: 版本不兼容
  - 处理：迁移数据或使用默认布局

#### 验收标准

- [ ] 刷新页面后布局状态恢复
- [ ] 恢复时无动画闪烁
- [ ] localStorage 不可用时使用默认布局
- [ ] 数据错误时使用默认布局

---

### F4.3 多用户隔离

**功能编号**: F4.3
**功能名称**: 多用户隔离
**优先级**: P1

#### 功能描述

不同用户的布局偏好独立存储，互不影响。

#### 实现方式

- 存储键名包含用户 ID：`outlook_layout_state_${userId}`
- 从全局变量或页面元素获取用户 ID
- 未登录用户使用 `guest` 作为 ID

#### 主流程

1. 系统获取当前用户 ID
2. 系统构建存储键名
3. 系统使用该键名读写 localStorage

#### 验收标准

- [ ] 不同用户的布局独立
- [ ] 切换用户后布局正确
- [ ] 未登录用户使用 guest 键名

---

### F4.4 防抖保存

**功能编号**: F4.4
**功能名称**: 防抖保存
**优先级**: P1

#### 功能描述

拖动调整宽度时，延迟 500ms 保存，避免频繁写入 localStorage。

#### 实现逻辑

```javascript
let pendingSave = null;

function saveStateDebounced() {
  if (pendingSave) {
    clearTimeout(pendingSave);
  }
  pendingSave = setTimeout(() => {
    saveStateNow();
    pendingSave = null;
  }, 500);
}
```

#### 验收标准

- [ ] 拖动时不立即保存
- [ ] 停止拖动后 500ms 保存
- [ ] 连续拖动只保存一次
- [ ] 折叠操作立即保存（不防抖）

---

### F4.5 页面卸载时强制保存

**功能编号**: F4.5
**功能名称**: 页面卸载时强制保存
**优先级**: P1

#### 功能描述

用户关闭页面或刷新时，强制执行防抖任务，确保最后一次调整被保存。

#### 实现逻辑

```javascript
window.addEventListener('beforeunload', () => {
  if (pendingSave) {
    clearTimeout(pendingSave);
    saveStateNow();
  }
});
```

#### 验收标准

- [ ] 拖动后立即关闭页面，状态被保存
- [ ] 拖动后立即刷新页面，状态被保存
- [ ] 不影响页面卸载速度

---


## 七、F5 - 窗口尺寸自适应

### F5.1 监听窗口大小变化

**功能编号**: F5.1
**功能名称**: 监听窗口大小变化
**优先级**: P1

#### 功能描述

系统监听浏览器窗口的 resize 事件，根据窗口宽度自动调整布局。

#### 实现逻辑

```javascript
let resizeTimer = null;

window.addEventListener("resize", () => {
  if (resizeTimer) {
    clearTimeout(resizeTimer);
  }
  resizeTimer = setTimeout(() => {
    handleWindowResize();
    resizeTimer = null;
  }, 200);
});
```

#### 验收标准

- [ ] 窗口大小改变时触发处理
- [ ] 使用防抖避免频繁触发
- [ ] 防抖延迟为 200ms

---

### F5.2 自动折叠面板

**功能编号**: F5.2
**功能名称**: 自动折叠面板
**优先级**: P1

#### 功能描述

当窗口宽度小于特定断点时，自动折叠侧边栏面板，确保邮件详情面板可见。

#### 断点规则

| 窗口宽度 | 自动折叠的面板 |
|---------|---------------|
| < 1200px | 分组面板 |
| < 900px | 分组面板 + 账号面板 |
| < 700px | 分组面板 + 账号面板 + 邮件列表 |

#### 主流程

1. 窗口大小改变
2. 系统获取当前窗口宽度
3. 系统根据断点判断需要折叠的面板
4. 系统自动折叠面板（不保存状态）
5. 系统添加 .auto-collapsed 类（区分用户手动折叠）

#### 特殊处理

- 自动折叠不保存到 localStorage
- 窗口变大时不自动展开（尊重用户选择）
- 用户手动展开后，窗口缩小时再次自动折叠

#### 验收标准

- [ ] 窗口 < 1200px 时自动折叠分组面板
- [ ] 窗口 < 900px 时自动折叠账号面板
- [ ] 窗口 < 700px 时自动折叠邮件列表
- [ ] 自动折叠不保存状态
- [ ] 窗口变大时不自动展开

---

### F5.3 媒体查询降级

**功能编号**: F5.3
**功能名称**: 媒体查询降级
**优先级**: P2

#### 功能描述

使用 CSS 媒体查询作为降级方案，即使 JavaScript 失效也能保证基本的响应式布局。

#### CSS 实现

```css
@media (max-width: 1200px) {
  .group-panel {
    display: none;
  }
}

@media (max-width: 900px) {
  .account-panel {
    display: none;
  }
}

@media (max-width: 700px) {
  .email-list-panel {
    display: none;
  }
}
```

#### 验收标准

- [ ] JavaScript 禁用时布局仍然响应式
- [ ] 媒体查询断点与 JavaScript 一致
- [ ] 小屏幕下邮件详情面板可见

---


## 八、F6 - 键盘可访问性

### F6.1 Resizer 键盘支持

**功能编号**: F6.1
**功能名称**: Resizer 键盘支持
**优先级**: P2

#### 功能描述

Resizer 支持键盘操作，用户可以使用方向键调整面板宽度。

#### 键盘操作

| 按键 | 操作 | 调整幅度 |
|------|------|---------|
| ← | 减小宽度 | 10px |
| → | 增大宽度 | 10px |
| Shift + ← | 快速减小 | 50px |
| Shift + → | 快速增大 | 50px |
| Tab | 聚焦到下一个 resizer | - |
| Shift + Tab | 聚焦到上一个 resizer | - |

#### 主流程

1. 用户按 Tab 键聚焦到 resizer
2. Resizer 显示聚焦样式（outline）
3. 用户按方向键
4. 系统计算新宽度
5. 系统应用宽度限制
6. 系统更新面板宽度
7. 系统更新 aria-valuenow 属性
8. 系统触发防抖保存

#### 验收标准

- [ ] Tab 键可以聚焦到 resizer
- [ ] 聚焦时有明显的视觉反馈
- [ ] 左箭头键减小宽度
- [ ] 右箭头键增大宽度
- [ ] Shift + 箭头键快速调整
- [ ] 键盘调整也应用宽度限制
- [ ] 键盘调整后保存状态

---

### F6.2 折叠按钮键盘支持

**功能编号**: F6.2
**功能名称**: 折叠按钮键盘支持
**优先级**: P2

#### 功能描述

折叠按钮支持键盘操作，用户可以使用 Enter 或 Space 键触发折叠/展开。

#### 键盘操作

| 按键 | 操作 |
|------|------|
| Tab | 聚焦到按钮 |
| Enter | 触发折叠/展开 |
| Space | 触发折叠/展开 |

#### 验收标准

- [ ] Tab 键可以聚焦到折叠按钮
- [ ] 聚焦时有视觉反馈
- [ ] Enter 键触发折叠/展开
- [ ] Space 键触发折叠/展开

---

### F6.3 ARIA 属性支持

**功能编号**: F6.3
**功能名称**: ARIA 属性支持
**优先级**: P2

#### 功能描述

为所有交互元素添加完整的 ARIA 属性，支持屏幕阅读器。

#### ARIA 属性清单

**Resizer**：
- `role="separator"`
- `aria-orientation="vertical"`
- `aria-label="调整[面板名称]宽度"`
- `aria-valuenow`: 当前宽度值
- `aria-valuemin`: 最小宽度
- `aria-valuemax`: 最大宽度
- `tabindex="0"`

**折叠按钮**：
- `aria-label="折叠[面板名称]"` 或 `"展开[面板名称]"`
- `aria-expanded="true"` 或 `"false"`
- `title`: 提示文本

**折叠指示器**：
- `role="button"`
- `aria-label="展开[面板名称]"`
- `tabindex="0"`

#### 验收标准

- [ ] 所有 resizer 有完整的 ARIA 属性
- [ ] 所有折叠按钮有完整的 ARIA 属性
- [ ] 所有折叠指示器有完整的 ARIA 属性
- [ ] aria-valuenow 实时更新
- [ ] aria-expanded 实时更新

---

### F6.4 焦点管理

**功能编号**: F6.4
**功能名称**: 焦点管理
**优先级**: P2

#### 功能描述

合理管理键盘焦点，确保用户使用键盘操作时体验流畅。

#### 焦点规则

1. **折叠面板后**：
   - 焦点移到折叠指示器
   
2. **展开面板后**：
   - 焦点移到折叠按钮

3. **Tab 顺序**：
   - 导航栏按钮 → 分组面板折叠按钮 → 分组面板 resizer → 账号面板折叠按钮 → ...

4. **模态框打开**：
   - 焦点移到模态框的第一个可聚焦元素

5. **模态框关闭**：
   - 焦点返回到触发按钮

#### 验收标准

- [ ] 折叠后焦点移到指示器
- [ ] 展开后焦点移到折叠按钮
- [ ] Tab 顺序合理
- [ ] 模态框焦点管理正确

---


## 九、实现细节

### 9.1 文件修改清单

#### 需要修改的文件

| 文件路径 | 修改内容 | 优先级 |
|---------|---------|--------|
| `templates/index.html` | 修改主容器结构，添加 resizer 和折叠按钮 | P0 |
| `static/css/main.css` | 添加 Grid 布局、CSS 变量、resizer 样式 | P0 |
| `static/js/main.js` | 初始化 LayoutManager | P0 |

#### 需要新增的文件

| 文件路径 | 文件内容 | 优先级 |
|---------|---------|--------|
| `static/js/layout-manager.js` | LayoutManager 类实现 | P0 |
| `static/js/state-manager.js` | StateManager 类实现 | P0 |

### 9.2 HTML 结构变更

#### 当前结构

```html
<div class="main-container">
  <aside class="group-panel">...</aside>
  <aside class="account-panel">...</aside>
  <aside class="email-list-panel">...</aside>
  <main class="email-detail-panel">...</main>
</div>
```

#### 目标结构

```html
<div class="main-container">
  <!-- 分组面板 -->
  <aside class="resizable-panel group-panel" data-panel="groups">
    <div class="panel-header">
      <span class="panel-title">分组</span>
      <button class="collapse-btn" aria-label="折叠分组面板" aria-expanded="true">
        <svg><!-- 左箭头 --></svg>
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
  </aside>

  <!-- 折叠指示器（折叠时显示） -->
  <div class="collapsed-indicator" data-panel="groups" style="display: none;">
    <span class="indicator-text">分组</span>
  </div>

  <!-- 账号面板、邮件列表面板（结构同上） -->
  <!-- ... -->

  <!-- 邮件详情面板（不可折叠，无 resizer） -->
  <main class="email-detail-panel">...</main>
</div>
```

### 9.3 CSS 变量系统

```css
:root {
  /* 面板初始宽度 */
  --groups-panel-width: 200px;
  --accounts-panel-width: 260px;
  --emails-panel-width: 380px;

  /* 最小/最大宽度 */
  --groups-panel-min-width: 150px;
  --groups-panel-max-width: 400px;
  --accounts-panel-min-width: 180px;
  --accounts-panel-max-width: 500px;
  --emails-panel-min-width: 280px;
  --emails-panel-max-width: 600px;
  --email-detail-panel-min-width: 400px;

  /* 折叠状态 */
  --panel-collapsed-width: 0px;
  --collapator-width: 48px;

  /* Resizer */
  --resizer-width: 4px;

  /* 动画 */
  --panel-transition-duration: 200ms;
  --reset-transition-duration: 300ms;
}
```

### 9.4 JavaScript 模块设计

#### LayoutManager 类

```javascript
class LayoutManager {
  constructor() {
    this.isResizing = false;
    this.currentPanel = null;
    this.startX = 0;
    this.startWidth = 0;
    this.pendingSave = null;
    this.stateManager = new StateManager();
  }

  // 初始化
  init() { }

  // 拖动相关
  startResize(e) { }
  resize(e) { }
  stopResize() { }

  // 键盘相关
  handleKeyboard(e) { }

  // 折叠相关
  togglePanel(panelName) { }
  collapsePanel(panelName, auto = false) { }
  expandPanel(panelName) { }

  // 重置相关
  resetLayout() { }

  // 窗口自适应
  handleWindowResize() { }

  // 状态管理
  saveStateDebounced() { }
  saveStateNow() { }
  loadState() { }

  // 工具方法
  updatePanelWidth(panel, width) { }
  getMinWidth(panelType) { }
  getMaxWidth(panelType) { }
  calculateOtherPanelsWidth(excludePanel) { }
  updateAriaValue(resizer, value) { }
  getCurrentUserId() { }
}
```

#### StateManager 类

```javascript
class StateManager {
  constructor() {
    this.storageKeyPrefix = 'outlook_layout_state_';
  }

  // 保存状态
  save(userId, state) { }

  // 加载状态
  load(userId) { }

  // 清除状态
  clear(userId) { }

  // 验证数据
  validate(state) { }

  // 版本迁移
  migrate(state) { }

  // 获取存储键名
  getStorageKey(userId) { }
}
```

---

## 十、验收标准总览

### 10.1 功能验收标准

#### P0 - 必须通过（核心功能）

**拖动调整宽度**：
- [ ] F1.1 - 可以拖动调整分组面板宽度
- [ ] F1.1 - 可以拖动调整账号面板宽度
- [ ] F1.1 - 可以拖动调整邮件列表宽度
- [ ] F1.2 - 宽度限制生效（最小/最大）
- [ ] F1.3 - 邮件详情面板始终可见且 ≥ 400px

**面板折叠/展开**：
- [ ] F2.1 - 可以折叠/展开分组面板
- [ ] F2.1 - 可以折叠/展开账号面板
- [ ] F2.1 - 可以折叠/展开邮件列表
- [ ] F2.2 - 折叠/展开动画流畅（200ms）
- [ ] F2.5 - 折叠后 resizer 隐藏
- [ ] F2.6 - 不能折叠最后一个面板

**状态持久化**：
- [ ] F4.1 - 拖动后 500ms 保存状态
- [ ] F4.1 - 折叠后立即保存状态
- [ ] F4.2 - 刷新页面后状态恢复

#### P1 - 重要功能

**视觉反馈**：
- [ ] F1.4 - 拖动时有视觉反馈
- [ ] F2.3 - 折叠后显示 48px 指示器
- [ ] F2.4 - 点击指示器可以展开

**恢复默认布局**：
- [ ] F3.1 - 导航栏显示重置按钮
- [ ] F3.2 - 点击重置显示确认对话框
- [ ] F3.3 - 确认后恢复默认布局

**状态管理**：
- [ ] F4.3 - 多用户布局隔离
- [ ] F4.5 - 页面卸载时强制保存

**窗口自适应**：
- [ ] F5.1 - 监听窗口大小变化
- [ ] F5.2 - 窗口 < 1200px 自动折叠分组
- [ ] F5.2 - 窗口 < 900px 自动折叠账号
- [ ] F5.2 - 窗口 < 700px 自动折叠邮件列表

#### P2 - 优化功能

**动画优化**：
- [ ] F3.4 - 重置动画流畅（300ms）
- [ ] F5.3 - 媒体查询降级生效

**键盘可访问性**：
- [ ] F6.1 - Resizer 支持键盘操作
- [ ] F6.2 - 折叠按钮支持键盘操作
- [ ] F6.3 - ARIA 属性完整
- [ ] F6.4 - 焦点管理合理

### 10.2 非功能验收标准

#### 性能

- [ ] 拖动时帧率 ≥ 60fps
- [ ] 折叠/展开动画流畅无卡顿
- [ ] localStorage 数据 ≤ 1KB
- [ ] 页面加载时间增加 ≤ 50ms

#### 兼容性

- [ ] Chrome 90+ 正常工作
- [ ] Edge 90+ 正常工作
- [ ] Firefox 88+ 正常工作
- [ ] Safari 14+ 正常工作

#### 可访问性

- [ ] 所有交互元素可键盘访问
- [ ] 所有交互元素有 ARIA 属性
- [ ] 屏幕阅读器可正常使用

### 10.3 回归验证清单

#### 现有功能不受影响

- [ ] 邮件列表正常显示
- [ ] 邮件详情正常显示
- [ ] 点击邮件可以查看详情
- [ ] 账号切换正常
- [ ] 分组切换正常
- [ ] 邮件刷新正常
- [ ] 邮件删除正常
- [ ] Token 刷新正常
- [ ] 搜索功能正常
- [ ] 原有的响应式布局正常

---

## 十一、测试策略

### 11.1 单元测试

**测试文件**: `tests/test_layout_manager.js`

**测试用例**：
1. LayoutManager 初始化
2. 宽度计算逻辑
3. 宽度限制逻辑
4. 状态序列化/反序列化
5. 用户 ID 获取逻辑

### 11.2 集成测试

**测试场景**：
1. 拖动调整宽度 → 保存 → 刷新 → 恢复
2. 折叠面板 → 保存 → 刷新 → 恢复
3. 重置布局 → localStorage 清除
4. 窗口缩小 → 自动折叠 → 窗口放大
5. 多用户切换 → 布局独立

### 11.3 用户验收测试

**测试场景**：
1. 新用户首次访问 → 默认布局
2. 调整布局 → 刷新 → 布局恢复
3. 折叠所有面板 → 阻止最后一个
4. 拖动到极限 → 宽度限制生效
5. 小屏幕访问 → 自动折叠

### 11.4 兼容性测试

**测试矩阵**：

| 浏览器 | 版本 | 操作系统 | 测试结果 |
|--------|------|---------|---------|
| Chrome | 90+ | Windows | |
| Chrome | 90+ | macOS | |
| Edge | 90+ | Windows | |
| Firefox | 88+ | Windows | |
| Firefox | 88+ | macOS | |
| Safari | 14+ | macOS | |

---

## 十二、风险和依赖

### 12.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| CSS Grid 兼容性 | 高 | 低 | 提前测试目标浏览器 |
| 拖动性能问题 | 中 | 中 | 使用 requestAnimationFrame |
| localStorage 配额满 | 低 | 低 | 降级到默认布局 |
| 现有功能受影响 | 高 | 中 | 充分回归测试 |

### 12.2 依赖关系

- **无后端依赖**：纯前端功能，不需要后端支持
- **无第三方库依赖**：使用原生 JavaScript 实现
- **CSS 特性依赖**：CSS Grid、CSS 变量、CSS transitions

### 12.3 缓解措施

1. **充分测试**：在所有目标浏览器上测试
2. **渐进增强**：使用媒体查询作为降级方案
3. **错误处理**：localStorage 不可用时使用默认布局
4. **性能优化**：使用防抖、节流、requestAnimationFrame

---

## 十三、附录

### 13.1 参考文档

- **PRD**: `PRD/PRD-可调整布局系统.md` v1.1
- **EnsoAI**: `exeoAI/src/renderer/components/layout/`
- **CSS Grid**: https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Grid_Layout
- **ARIA**: https://www.w3.org/WAI/ARIA/apg/

### 13.2 功能清单汇总

| 模块 | 子功能数 | P0 | P1 | P2 |
|------|---------|----|----|-----|
| F1 - 可拖动调整宽度 | 4 | 3 | 1 | 0 |
| F2 - 面板折叠/展开 | 6 | 4 | 2 | 0 |
| F3 - 恢复默认布局 | 4 | 0 | 3 | 1 |
| F4 - 状态持久化 | 5 | 2 | 3 | 0 |
| F5 - 窗口尺寸自适应 | 3 | 0 | 2 | 1 |
| F6 - 键盘可访问性 | 4 | 0 | 0 | 4 |
| **总计** | **26** | **9** | **11** | **6** |

### 13.3 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|----------|--------|
| v1.0 | 2026-02-26 | 初始版本，包含 6 个功能模块、26 个子功能 | 开发团队 |

---

**文档结束**
