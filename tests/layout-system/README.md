# 布局系统测试运行指南

## 测试概述

本目录包含可调整布局系统的完整测试套件，包括单元测试、集成测试、性能测试和可访问性测试。

## 目录结构

```
tests/layout-system/
├── jest.config.js          # Jest 配置文件
├── setup.js                # 测试环境设置
├── test-utils.js           # 测试辅助工具
├── README.md               # 本文件
├── unit/                   # 单元测试
│   ├── layout-manager.test.js
│   └── state-manager.test.js
├── integration/            # 集成测试
│   ├── drag-resize.test.js
│   ├── panel-collapse.test.js
│   ├── reset-layout.test.js
│   ├── state-error-handling.test.js
│   ├── state-load.test.js
│   ├── state-multi-user.test.js
│   ├── state-save.test.js
│   ├── window-adapt.test.js
│   └── keyboard-resizer.test.js
├── performance/            # 性能测试
│   └── (待添加)
└── accessibility/          # 可访问性测试
    └── (待添加)
```

## 前置要求

### 安装依赖

```bash
# 安装 Jest 和相关依赖
npm install --save-dev jest @jest/globals jest-environment-jsdom

# 或使用 yarn
yarn add --dev jest @jest/globals jest-environment-jsdom
```

### 配置 package.json

在项目根目录的 `package.json` 中添加测试脚本：

```json
{
  "scripts": {
    "test": "jest --config tests/layout-system/jest.config.js",
    "test:watch": "jest --config tests/layout-system/jest.config.js --watch",
    "test:coverage": "jest --config tests/layout-system/jest.config.js --coverage",
    "test:unit": "jest --config tests/layout-system/jest.config.js tests/layout-system/unit",
    "test:integration": "jest --config tests/layout-system/jest.config.js tests/layout-system/integration"
  }
}
```

## 运行测试

### 运行所有测试

```bash
npm test
```

### 运行单元测试

```bash
npm run test:unit
```

### 运行集成测试

```bash
npm run test:integration
```

### 运行测试并生成覆盖率报告

```bash
npm run test:coverage
```

覆盖率报告将生成在 `tests/layout-system/coverage/` 目录。

### 监听模式（开发时使用）

```bash
npm run test:watch
```

## 测试用例说明

### 单元测试

#### StateManager 测试 (`unit/state-manager.test.js`)

测试状态持久化功能：

- ✅ TC-F4-001-P: 保存有效状态
- ✅ TC-F4-003-P: 加载有效状态
- ✅ TC-F4-004-P: 多用户布局隔离
- ✅ TC-F4-006-N: localStorage 不可用
- ✅ TC-F4-007-N: localStorage 数据损坏
- ✅ 版本迁移（v1.0 → v1.1）
- ✅ 数据验证

**运行单个测试文件：**

```bash
npx jest tests/layout-system/unit/state-manager.test.js
```

#### LayoutManager 测试 (`unit/layout-manager.test.js`)

测试布局管理核心功能：

- ✅ TC-F1-001-P: 计算拖动后的宽度
- ✅ TC-F1-002-B: 限制在最小宽度
- ✅ TC-F1-003-B: 限制在最大宽度
- ✅ TC-F2-001-P: 折叠面板
- ✅ TC-F2-002-P: 展开面板
- ✅ 更新 CSS 变量
- ✅ 切换面板状态

**运行单个测试文件：**

```bash
npx jest tests/layout-system/unit/layout-manager.test.js
```

### 集成测试

#### 拖动调整宽度测试 (`integration/drag-resize.test.js`)

测试完整的拖动流程：

- ✅ TC-F1-001-P: 完整的拖动流程
- ✅ TC-F1- 确保邮件详情面板至少 400px
- ✅ TC-F1-005-N: 快速拖动导致鼠标移出窗口
- ✅ TC-F1-006-PF: 拖动帧率测试（≥ 55fps）

**运行单个测试文件：**

```bash
npx jest tests/layout-system/integration/drag-resize.test.js
```

#### 面板折叠测试 (`integration/panel-collapse.test.js`)

测试完整的折叠/展开流程：

- ✅ TC-F2-001-P: 点击折叠按钮折叠面板
- ✅ TC-F2-002-P: 点击折叠指示条展开面板
- ✅ TC-F2-003-N: 尝试折叠所有面板
- ✅ TC-F2-004-P: 折叠后 resizer 不可见
- ✅ TC-F2-005-N: 折叠状态下尝试拖动
- ✅ 折叠动画性能测试（200ms ± 50ms）

**运行单个测试文件：**

```bash
npx jest tests/layout-system/integration/panel-collapse.test.js
```

## 测试覆盖率目标

根据 TD 文档的要求：

- **代码覆盖率**: > 80%
  - 分支覆盖率: > 80%
  - 函数覆盖率: > 80%
  - 行覆盖率: > 80%
  - 语句覆盖率: > 80%

- **功能覆盖率**: 100%
  - F1 - 拖动调整宽度: 100%
  - F2 - 面板折叠展开: 100%
  - F3 - 恢复默认布局: 100%
  - F4 - 状态持久化: 100%
  - F5 - 窗口尺寸适配: 100%
  - F6 - 键盘可访问性: 100%

## 测试数据

测试使用的数据定义在 `test-utils.js` 中：

- **用户 ID**: `test-user`, `user-a`, `user-b`, `guest`
- **面板宽度**:
  - 分组面板: 150px (最小) ~ 400px (最大)
  - 账号面板: 180px (最小) ~ 500px (最大)
  - 邮件列表: 280px (最小) ~ 600px (最大)
- **窗口尺寸**: 1200px, 900px, 700px (断点)

## 调试测试

### 运行单个测试用例

```bash
npx jest -t "TC-F1-001-P"
```

### 查看详细输出

```bash
npx jest --verbose
```

### 调试模式

```bash
node --inspect-brk node_modules/.bin/jest --runInBand
```

然后在 Chrome 中打开 `chrome://inspect` 进行调试。

## 持续集成

### GitHub Actions 配置示例

```yaml
name: 布局系统测试

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2

      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '16'

      - name: Install dependencies
        run: npm install

      - name: Run tests
        run: npm test

      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          files: ./tests/layout-system/coverage/lcov.info
```

## 常见问题

### Q: 测试失败：localStorage is not defined

**A**: 确保 `setup.js` 文件正确配置了 localStorage mock。

### Q: 测试失败：requestAnimationFrame is not defined

**A**: 确保 `setup.js` 文件正确配置了 requestAnimationFrame mock。

### Q: 覆盖率不足 80%

**A**: 检查是否有未测试的代码分支，添加更多的边界测试用例。

### Q: 测试运行很慢

**A**: 使用 `--maxWorkers=4` 参数限制并发数，或使用 `--runInBand` 串行运行。

## 下一步计划

- [ ] 添加性能测试（帧率、内存占用）
- [ ] 添加可访问性测试（axe-core）
- [ ] 添加 E2E 测试（Playwright）
- [ ] 添加视觉回归测试
- [ ] 集成到 CI/CD 流程

## 参考文档

- [TD - 可调整布局系统](../../docs/TD/TD-可调整布局系统.md)
- [TDD - 可调整布局系统](.././TDD-可调整布局系统.md)
- [Jest 文档](https://jestjs.io/docs/getting-started)
- [Testing Library](https://testing-library.com/)

## 联系方式

如有问题，请联系测试团队或在 GitHub Issues 中提出。
