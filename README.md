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
- **14 组内置预设** — 浮点数、速度、强度、颜色、旋转、衰减等常用参数一键追加
- **预设按钮行** — 预设以第二排按钮展示，支持水平滚动，点击即追加
- **自定义 GUI 选择** — 每条数据可单独设置浮点滑块、颜色选择器、循环下拉等控件
- **模板导入/导出** — JSON 格式，方便团队共享配置
- **多对象批量应用** — 选中多个对象，一键添加全部用户数据
- **完整 Undo 支持** — 误操作可撤销
- **键盘快捷键** — Delete 键删除条目

## 兼容性

| 版本 | 支持 |
|------|------|
| C4D 2023 | ✅ |
| C4D 2024 | ✅ |
| C4D 2025 | ✅ |
| C4D 2026 | ✅（v1.2.3+） |

## 安装方法

1. 下载 `c4d-userdata-manager_v1.2.3.zip`（或最新版本）
2. 解压后得到 `UserDataManager.pyp` + `icon.png`
3. 放到 C4D 的 **plugins** 文件夹：
   - **Windows**: `C:\Program Files\Maxon Cinema 4D 202X\plugins\`
   - **macOS**: `/Applications/Maxon Cinema 4D 202X/plugins/`
4. 重启 C4D
5. 菜单栏 → **扩展 (Extensions) → UserData Manager**

> **重要**：请到 [plugincafe.maxon.net](https://plugincafe.maxon.net) 注册一个免费插件 ID，替换源码中的 `PLUGIN_ID = 1060001`，避免与其他插件冲突。

## 使用流程

```
① 打开插件 → ② 添加条目或点预设 → ③ 编辑属性（可设置自定义GUI）→ ④ 选中场景对象 → ⑤ 点"应用到对象"
                                                                               ↓
                                                                   Xpresso 里拖入对象即可看到用户数据端口
```

## 工作流示例

1. 打开插件面板
2. 点击第二排预设按钮「旋转」
3. 在场景中选中一个 Null 对象
4. 点击「▸ 应用到对象」
5. 打开 Xpresso 编辑器，把 Null 拖进来
6. Null 的用户数据端口现在有 Rotate.X / Rotate.Y / Rotate.Z，可以直接连接到其他节点

## 界面说明

```
第一排: ＋ － ⧉ ↑ ↓ | 保存 加载 清空 | ▸ 应用到对象
第二排: [浮点数] [速度] [强度] [透明度] [缩放] [颜色] ... ← 水平滚动

左侧列表:   # | 名称 | 类型 | 默认值
右侧属性:   名称 / 类型 / 分组 / 范围 / 默认值 / 单位 / 自定义GUI / 说明
```

## 技术细节

- **单文件 `.pyp`**，零外部依赖
- 纯 Python，基于 C4D Python API
- 支持 Undo/Redo
- JSON 模板格式，可版本控制
- 跨版本兼容层（`_c()` 函数安全获取已移除的常量）

## License

MIT
