# AGENTS.md · 项目规则

> 写给 AI / 未来维护者的项目上下文。只记录代码里看不出的信息。

## 技术栈

- C4D Python SDK，**跨版本 2023 – 2026**（2025→2026 有大量破坏性 API 变更）
- 单文件 `.pyp`，零外部依赖；插件 ID 用 `PLUGIN_ID` 常量（注册前勿与他人冲突）
- 核心机制：动态列表（ScrollGroup + 动态控件模拟 ListView）+ 用户数据描述构建（build_bc）

## 关键坑（改代码前必读）

1. **C4D 2026 迁移**：`AddListView` 全家、`GePopupMenu`、`gui.Question`、`ScrollGroupEnd` 已移除；`AddStaticText(border=)` / `AddComboBox(cols=)` 等 kwargs 变 **positional-only**（报 `'xxx' is an invalid keyword argument` 就改位置传参）
2. **常量用 `_c()` 包裹**：`_c(name, fallback)` 安全获取可能被移除的常量；但 **`DESC_CUSTOMGUI` / `DESC_UNIT` 只在有有效值时才写入**（fallback 为 0 写入会破坏参数渲染）
3. **PERCENT 内部 0-1 存储**：UI 层用 0-100，写入 C4D 必须 `/100`（`DESC_DEFAULT/MIN/MAX/STEP` 都要转换）
4. **`AddUserData()` 不初始化默认值**：必须 `obj[did] = value` 显式写入（类型要匹配：DTYPE_LONG→int、DTYPE_REAL→float、BOOL→int(bool(...))、PERCENT→/100）
5. **`GetUserDataContainer()` 迭代返回元组**（C4D 2026）：`for item in udc` 需 `isinstance(item, tuple)` 判断取 key；删除容器元素**倒序遍历**
6. **对话框生命周期**：`self._dlg` 保持引用防 GC 空白；`RestoreLayout()` 直接 `return True` 防二次打开崩溃
7. **动态列表刷新**：`LayoutFlushGroup` 只清子控件，不重建组；**不要对已存在组重复 GroupBegin**（布局参数不更新）；列表行用「每行独立 Group（cols=4,rows=1）+ 统一 inith」保证对齐

## 约定

- 动态控件 ID 用「基准值 + 索引偏移」模式（`_ROW_BASE + i * stride + offset`）
- 关键错误用 `gui.MessageDialog()` 弹窗（`print()` 在 C4D 插件中用户看不见）
- 批量操作：先统一 AddUndo（一个 Undo/对象），再循环写数据（避免 Undo 爆炸）
- 外部输入（JSON 模板）必须类型校验

## 常用命令

- 无构建 / 无测试命令；验证 = 放入 C4D plugins 目录重启
- 发布 = 打包 zip（.pyp + icon），见知识库 模板/插件Release打包模板
- 详细开发记录见 DEVELOPMENT.md；版本历史见 CHANGELOG.md
