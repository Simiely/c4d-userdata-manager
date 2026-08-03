# 更新日志（CHANGELOG）

## v2.1.0（当前版本）

- 回退至经过充分测试的版本（`9fe87b4`）
- 修复 C4D 2026 兼容问题：
  - `GetUserDataContainer` 元组迭代（`(key, value)` 而非整数 key）
  - ListView 移除后的替代方案（ScrollGroup + 动态控件）
  - `GePopupMenu` / `gui.Question` 移除替代
  - `AddStaticText` / `AddComboBox` 参数 positional-only
  - 常量 `_c()` fallback 兼容层
- 完整 Undo/Redo 支持
- JSON 模板导入/导出

## v1.x

- 早期版本：User Data 批量创建 / 管理基础功能（10 种数据类型、14 组预设、多对象批量应用）
