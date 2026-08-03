# 开发文档（DEVELOPMENT.md）

> 面向开发者的项目文档：架构说明 + 关键问题与方案（一坑一篇）。
> 每个问题用统一格式：**TL;DR**（一句话结论）→ 问题 / 根因 / 解决 / 预防。

## 项目概览

C4D 用户数据管理插件（v2.1.0，兼容 C4D 2023-2026），单文件 `.pyp`。列表式 UI 批量管理用户数据，10 种数据类型、14 组预设、JSON 模板导入导出、多对象批量应用。

## 架构说明

```
UserDataManager.pyp
├── CommandData（插件入口）：self._dlg 保持引用 + RestoreLayout no-op
├── Dialog（GeDialog 异步对话框）
│   ├── CreateLayout(parent_dlg=None)：动态列表（ScrollGroup + 每行独立 Group）+ 预设按钮行
│   ├── _refresh_list()：LayoutFlushGroup → 添加控件 → LayoutChanged
│   ├── 预设按钮行：水平滚动（ScrollGroup + AddButton）
│   ├── build_bc()：构建用户数据描述（类型/默认值/范围/单位）
│   ├── get_c4d_value()：Python 值 → C4D 参数值（类型 + 单位转换）
│   └── 模板导入/导出（JSON）+ Undo/Redo 分组记录
└── 兼容层：_c(name, fallback) 常量安全获取
```

- **动态列表模式**：`ScrollGroupBegin` + 内容组（`cols=1, rows=0`）+ 每行独立 Group（`cols=4, rows=1`）+ 控件 ID 基准值偏移（`_ROW_BASE + i*_ROW_STRIDE`）
- **用户数据描述**：`build_bc()` 按 C4D 数据类型写入 `DESC_DEFAULT/MIN/MAX/STEP`，`get_c4d_value()` 统一转换（PERCENT /100、BOOL → int、COLOR → Vector）

## 关键问题与方案

### A. C4D 2026 SDK 迁移（2025 → 2026 破坏性变更）

#### A1. ListView 全套 API 被移除（破坏性最大）

**TL;DR**：`AddListView` 及 9 个配套方法在 C4D 2026 全部移除。用 **ScrollGroup + 动态控件模拟多列列表**：表头 StaticText + 可滚动内容组 + 每行独立 Group。

- **问题**：`AttributeError: 'UserDataDialog' object has no attribute 'AddListView'`
- **根因**：C4D 2026 移除 ListView 全套（AddListView/SetListViewMode/SetListViewColumn/GetListViewCount/RemoveListViewItem/SetListViewItem/GetSelectedListViewItem/SetSelectedListViewItem/FreezeListView/ThawListView）
- **解决**：ScrollGroupBegin + 内容组（cols=4, rows=0）+ 动态填充（LayoutFlushGroup → AddStaticText/AddButton → LayoutChanged）；点击 Name Button 用控件 ID 反推条目索引 `idx = (mid - _ROW_BASE) // _ROW_STRIDE`
- **预防**：动态列表统一用此模式；`LayoutFlushGroup` 只清子控件不删组；**不要对已存在组重复 GroupBegin**（布局参数首次创建后固定）

#### A2. ScrollGroupEnd 被移除

**TL;DR**：C4D 2026 没有 `ScrollGroupEnd`，用 `GroupEnd()` 收尾（ScrollGroupBegin 行为与 GroupBegin 一致）。

#### A3. GePopupMenu 被移除

**TL;DR**：`c4d.gui.GePopupMenu` 在 2026 移除。少量预设场景直接改用**第二排独立按钮**（更直观）；仍需弹窗用 `AddPopupButton` + `AddChild`。

#### A4. gui.Question 被移除

**TL;DR**：`gui.Question("...")` 在 2026 改名 `gui.QuestionDialog("...")`，接口完全兼容，直接替换。

#### A5. LoadDialog / SaveDialog 参数变更

**TL;DR**：`typeflags=` 参数在 2026 改名 `type=`，签名统一为 `type/flags/title/def_file/def_path/force_suffix`。

```python
# ✅ C4D 2026
fn = storage.LoadDialog(title="打开文件", flags=c4d.FILESELECT_LOAD,
                        type=c4d.FILESELECTTYPE_ANYTHING)
```

#### A6. CreateLayout 签名变更

**TL;DR**：C4D 2023 传 `CreateLayout(self, parent_dlg)`，2026 只调 `CreateLayout(self)`。用默认参数兼容：`def CreateLayout(self, parent_dlg=None):`。

#### A7. 常量不存在（_c() 兼容层）

**TL;DR**：低频常量在 2026 被移除（如 `CUSTOMGUI_COLORFIELD`）。用 `_c(name, fallback)` 包裹；**UI 相关常量（单位/自定义 GUI/边框）是高危区，数据类型常量是稳定区**。

```python
def _c(name, fallback):
    return getattr(c4d, name, fallback)
```

#### A8. AddStaticText / AddComboBox 参数变 positional-only

**TL;DR**：C4D 2026 将部分 GeDialog 方法末位的边缘参数改为仅位置参数。`AddStaticText(border=...)` → 第 6 个位置参数；`AddComboBox(cols=1)` → 第 3 个位置参数。**遇到 `'xxx' is an invalid keyword argument` 就改位置传参**。

- **不受影响**：`flags=`/`name=`/`initw=`/`inith=`/`title=`/`rows=`/`groupflags=`/`scrollflags=`

### B. 用户数据写入

#### B1. build_bc() 数据写入类型不匹配

**TL;DR**：`DESC_DEFAULT` 类型必须与 C4D 数据类型匹配：DTYPE_REAL→float、DTYPE_LONG→int、DTYPE_BOOL→`int(bool(...))`、DTYPE_VECTOR→Vector、PERCENT→float。混用导致默认值写入失败（显示 0 或无法修改）。

```python
if self.dtype in (UDT.FLOAT, UDT.PERCENT, UDT.ANGLE):
    bc[c4d.DESC_DEFAULT] = float(self.default_v)  # DTYPE_REAL → float
elif self.dtype == UDT.INTEGER:
    bc[c4d.DESC_DEFAULT] = int(self.default_v)    # DTYPE_LONG → int
```

#### B2. DESC_CUSTOMGUI=0 导致 FLOAT 空值

**TL;DR**：不存在的常量 `_c()` fallback 为 0，写入 `DESC_CUSTOMGUI=0` 会破坏参数渲染（FLOAT 显示为空）。**移除自定义 GUI 代码，让 C4D 用各类型默认控件**（DTYPE_COLOR 默认就是颜色选择器）。

#### B3. PERCENT 类型用 0-1 内部存储

**TL;DR**：`DTYPE_REAL + DESC_UNIT_PERCENT` 时 C4D 内部期望 0-1（1.0=100%）。UI 层保持 0-100，**写入时 `/100`**（DEFAULT/MIN/MAX/STEP 都要），否则显示 10000%。

#### B4. DESC_UNIT 非必填时不要写入 0

**TL;DR**：`BaseContainer` 中值为 0 ≠ 未设置。对无单位类型（FLOAT）写入 `DESC_UNIT=0` 会破坏渲染。**只有存在有效单位时才写入 DESC_UNIT**。

#### B5. AddUserData 后必须显式写入默认值

**TL;DR**：`AddUserData(bc)` 只创建描述定义，**不保证从 DESC_DEFAULT 初始化参数值**。必须 `obj[did] = entry.get_c4d_value()` 显式写入（统一转换：PERCENT /100、BOOL → int(bool(...))、COLOR → Vector）。

#### B6. GetUserDataContainer 迭代返回元组

**TL;DR**：C4D 2026 中 `for did in udc` 产生 `(key, value)` 元组而非整数 key。**做类型判断兼容**，删除容器元素**倒序遍历**避免索引偏移。

```python
dids = []
for item in udc:
    if isinstance(item, tuple):
        dids.append(item[0])    # C4D 2026: (key, value)
    else:
        dids.append(item)       # C4D 2025 及更早: key
for did in reversed(dids):
    obj.RemoveUserData(did)
```

### C. 对话框与 UI

#### C1. 对话框第二次打开崩溃

**TL;DR**：`RestoreLayout()` 直接 `return True`（no-op），`Execute()` 作为唯一入口（先安全关闭旧对话框再新建）。崩溃栈 `Py_HashPointer` = hash 已释放的 C4D 对象。

#### C2. 对话框显示空白（GC）

**TL;DR**：对话框对象用局部变量会被垃圾回收导致空白。**CommandData 用 `self._dlg` 实例变量保持引用**。

#### C3. ScrollGroup 内内容垂直居中

**TL;DR**：动态列表条目垂直居中不对齐。终版方案：**内容容器 `cols=1, rows=0` + 每行独立 Group（`cols=4, rows=1`）+ 所有控件统一 `inith=18` + `GroupBorderSpace(0,0,0,0)`**。

- 废弃方案 A：`cols=4, rows=0` 直接添加——Button/StaticText 高度计算方式不同，grid flow 无法保证每行顶部对齐

### D. 代码质量

#### D1. ListView 正向循环删除跳项

**TL;DR**：删除列表元素必须**倒序遍历**（正向删除时索引前移会跳项）。

#### D2. Undo 记录爆炸

**TL;DR**：批量操作先对**每个对象**统一 `AddUndo`，再循环写数据（避免 N×M 条 undo 记录）。

```python
doc.StartUndo()
for obj in objs:
    doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)  # 一个 Undo / 对象
for obj in objs:
    for entry in entries:
        obj.AddUserData(entry.build_bc())
doc.EndUndo()
```

#### D3. 异常堆栈被静默吞掉

**TL;DR**：`print()` 在 C4D 插件中用户看不见。收集异常，用 `gui.MessageDialog()` 弹窗展示（前 5 条）。

## 开发建议（C4D 跨版本插件）

1. **先查 SDK 文档再写代码**——2023→2026 破坏性变更尤其多
2. **动态控件用 LayoutFlushGroup + 内容组**，不重建组；不要重复 GroupBegin
3. **控件 ID 用基准值 + 偏移**（`_ROW_BASE + idx*stride`）
4. **常量全部 `_c()` 包裹**，避免运行时崩溃
5. **异步对话框必须保持引用**（self._dlg）
6. **外部输入必须校验**（JSON 模板类型检查）
7. **关键错误弹对话框**（MessageDialog），print 等同不存在
8. **DESC_DEFAULT 类型必须与 C4D 类型匹配**
9. **GeDialog 参数报 invalid keyword → 改位置传参**
10. **DESC_UNIT / DESC_CUSTOMGUI 只有有效值才写入**
11. **PERCENT 内部 0-1**（UI 0-100，写入 /100）
12. **AddUserData 后显式写参数值**
13. **跨版本迭代容器做类型判断**，删除倒序

## 开发环境

- Cinema 4D 2023 – 2026 + Python SDK（无构建工具，单文件 .pyp）
- 验证：放入 C4D plugins 目录重启；发布 = zip（.pyp + icon.png）
