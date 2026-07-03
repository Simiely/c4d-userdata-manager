# C4D UserData Manager

> 轻量级 Cinema 4D 插件，用于快速创建和管理用户数据 (User Data)，供 Xpresso / Python / 表达式直接调用。

## 为什么需要它

C4D 自带的用户数据创建体验不佳：

- 每次添加都要弹对话框，无法批量操作
- 改参数要重新打开窗口
- 没有预设和模板复用机制
- 只能逐个对象添加

本插件用一个面板解决以上全部痛点。

## 功能特性

- **批量编辑** — 列表式 UI，一次性管理多条用户数据
- **10 种数据类型** — Float / Integer / Boolean / Color / Vector / Angle / Percentage / String / Dropdown / Filename
- **13 组内置预设** — 速度、强度、颜色、旋转、衰减等常用参数一键添加
- **模板导入/导出** — JSON 格式，方便团队共享配置
- **多对象批量应用** — 选中多个对象，一键添加全部用户数据
- **完整 Undo 支持** — 误操作可撤销
- **键盘快捷键** — Delete 键删除条目

## 兼容性

Cinema 4D 2023 / 2024 / 2025 / 2026（v1.2.1 修复了 C4D 2026 API 变更问题）

## 安装方法

1. 下载 `UserDataManager.pyp` 文件
2. 放到 C4D 的 **plugins** 文件夹：
   - **Windows**: `C:\Program Files\Maxon Cinema 4D 202X\plugins\`
   - **macOS**: `/Applications/Maxon Cinema 4D 202X/plugins/`
3. 重启 C4D
4. 菜单栏 → **扩展 (Extensions) → UserData Manager**

> **重要**：请到 [plugincafe.maxon.net](https://plugincafe.maxon.net) 注册一个免费插件 ID，替换源码第 33 行的 `PLUGIN_ID = 1060001`，避免与其他插件冲突。

## 使用流程

```
① 打开插件 → ② 添加条目或选预设 → ③ 编辑属性 → ④ 选中场景对象 → ⑤ 点"应用到对象"
                                                                    ↓
                                                        Xpresso 里拖入对象即可看到用户数据端口
```

## 工作流示例

1. 打开插件面板
2. 点击「预设」→ 选择「Rotation 旋转」
3. 在场景中选中一个 Null 对象
4. 点击「应用到对象」
5. 打开 Xpresso 编辑器，把 Null 拖进来
6. Null 的用户数据端口现在有 Rotate.X / Rotate.Y / Rotate.Z，可以直接连接到其他节点

## 截图

```
┌─ UserData Manager  v1.1 ───────────────────────────────┐
│ ＋ － ⧉ ↑ ↓ │ 预设 保存 加载 清空 │  ▸ 应用到对象   │
├──────────┬──────────────────────────────────────────────┤
│ # │名称│类型│默认值 │ 属性                           │
│ 1 │Speed│Float│50    │ 名称: [Speed              ]    │
│ 2 │Color│Color│1,1,1│ 类型: [Float 浮点数    ▼]    │
│ 3 │...  │     │      │ 分组: [                    ]    │
│         │              │ 最小值: [0]  最大值: [100]    │
│         │              │ 步幅: [1]   默认值: [50]      │
│         │              │ 单位: [无              ▼]    │
│         │              │ 说明: [                    ]    │
├──────────┴──────────────────────────────────────────────┤
│ 条目数: 3 | 选中: #1                                    │
└─────────────────────────────────────────────────────────┘
```

## 技术细节

- **单文件 `.pyp`**，零外部依赖
- 纯 Python，基于 C4D Python API
- 支持 Undo/Redo
- JSON 模板格式，可版本控制

## License

MIT
