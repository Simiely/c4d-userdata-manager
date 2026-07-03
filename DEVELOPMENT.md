# 开发笔记

记录 C4D 跨版本插件开发中遇到的关键问题和解决思路，方便后续规避同类问题。

---

## C4D 版本迁移清单

从 C4D 2025 迁移到 2026 时，Python API 发生了大量破坏性变更。以下清单按严重程度排列：

### 1. ListView 全套 API 被移除（破坏性最大）

**现象：** `AttributeError: 'UserDataDialog' object has no attribute 'AddListView'`

**根因：** C4D 2026 移除了以下 ListView 相关方法：

| 被移除的方法 | 用途 |
|---|---|
| `AddListView(id, flags, cols)` | 创建列表控件 |
| `SetListViewMode(id, mode)` | 设置显示模式 |
| `SetListViewColumn(id, col, name, width)` | 设置列标题/宽度 |
| `GetListViewCount(id)` | 获取行数 |
| `RemoveListViewItem(id, row)` | 删除某行 |
| `SetListViewItem(id, row, text, column)` | 设置单元格文本 |
| `GetSelectedListViewItem(id)` | 获取选中行索引 |
| `SetSelectedListViewItem(id, row)` | 设置选中行 |
| `FreezeListView(id)` / `ThawListView(id)` | 冻结/解冻刷新 |

**解决方案：** 用 `ScrollGroup` + 动态控件模拟多列列表：

```python
# 在 CreateLayout 中创建骨架
self.GroupBegin(_gList, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                cols=1, rows=2, title="")
# 表头行
self.GroupBegin(0, flags=c4d.BFH_SCALEFIT, cols=4, rows=1, title="")
self.AddStaticText(0, c4d.BFH_LEFT, 30,  0, "#",     c4d.BORDER_THIN_IN)
self.AddStaticText(0, c4d.BFH_SCALEFIT, 130, 0, "名称", c4d.BORDER_THIN_IN)
self.AddStaticText(0, c4d.BFH_SCALEFIT, 110, 0, "类型", c4d.BORDER_THIN_IN)
self.AddStaticText(0, c4d.BFH_SCALEFIT, 100, 0, "默认值",c4d.BORDER_THIN_IN)
self.GroupEnd()
# 可滚动内容区 — cols=4, rows=0 使条目在 4 列网格中自然流动
self.ScrollGroupBegin(_gScroll, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                      scrollflags=c4d.SCROLLGROUP_VERT)
self.GroupBegin(_gListContent, flags=c4d.BFH_SCALEFIT, cols=4, rows=0, title="")
self.GroupEnd()
self.GroupEnd()
self.GroupEnd()

# 在 _refresh_list 中动态填充
def _refresh_list(self):
    self.LayoutFlushGroup(_gListContent)
    for i, e in enumerate(self._entries):
        base = _ROW_BASE + i * _ROW_STRIDE
        # 直接在 cols=4 的 _gListContent 中按行添加 4 个控件
        self.AddStaticText(...)  # 序号
        self.AddButton(...)      # 名称（可点击选中）
        self.AddStaticText(...)  # 类型
        self.AddStaticText(...)  # 默认值
    self.LayoutChanged(_gScroll)
```

点击 Name Button 时通过控件 ID 反推条目索引：

```python
def Command(self, mid, bc):
    if _ROW_BASE <= mid < _ROW_BASE + 9999:
        idx = (mid - _ROW_BASE) // _ROW_STRIDE
        self._sel = idx
```

**关键要点：**
- `LayoutFlushGroup` 只清空子控件，不删除组本身
- **不要**在 `_refresh_list` 中对已存在的组再次调用 `GroupBegin(id, ...)`，因为布局参数（cols/rows/flags）在首次创建时固定，重复调用不会更新
- 刷新时机：`LayoutFlushGroup` → 直接添加控件 → `LayoutChanged(父group)`
- 内容容器的 `cols` 应根据实际列数设置（如 4 列），`rows=0` 表示动态行数

---

### 2. ScrollGroupEnd 被移除

**现象：** `AttributeError: 'GeDialog' object has no attribute 'ScrollGroupEnd'`

**解决方案：** 用 `GroupEnd()` 替代。C4D 2026 中 `ScrollGroupBegin` 的行为与 `GroupBegin` 一致，使用 `GroupEnd()` 收尾。

```python
# ❌ C4D 2025
self.ScrollGroupBegin(id, ...)
self.ScrollGroupEnd(id)

# ✅ C4D 2026
self.ScrollGroupBegin(id, ...)
self.GroupEnd()
```

---

### 3. GePopupMenu 被移除

**现象：** `AttributeError: module 'c4d.gui' has no attribute 'GePopupMenu'`

**解决方案：** 若只需要少数预设，建议直接改用**第二排独立按钮**（不需要弹窗交互），比 `AddPopupButton` 更直观：

```python
# ✅ 推荐：预设按钮行（水平滚动）
self.ScrollGroupBegin(0, flags=c4d.BFH_SCALEFIT,
                      scrollflags=c4d.SCROLLGROUP_HORIZ)
self.GroupBegin(0, flags=c4d.BFH_SCALEFIT, cols=len(PRESETS), rows=1, title="")
for i, p in enumerate(PRESETS):
    self.AddButton(_btnPresetBase + i, flags=c4d.BFH_LEFT,
                   initw=65, inith=24, name=p["btn"])
self.GroupEnd()
self.GroupEnd()

# Command 中通过 ID 范围判断
elif _btnPresetBase <= mid < _btnPresetBase + len(PRESETS):
    idx = mid - _btnPresetBase
    preset = PRESETS[idx]
```

如果仍需要弹窗，改用 `AddPopupButton`：

```python
# 替代方案：AddPopupButton
self.AddPopupButton(_btnPreset, flags=c4d.BFH_LEFT, initw=70)
self.SetString(_btnPreset, "预设 ▼")
for i, p in enumerate(PRESETS):
    self.AddChild(_btnPreset, i, p["name"])

# Command 中获取选中
if mid == _btnPreset:
    idx = self.GetInt32(_btnPreset)
```

---

### 4. gui.Question 被移除

**现象：** `AttributeError: module 'c4d.gui' has no attribute 'Question'`

**解决方案：** 改用 `gui.QuestionDialog`，接口完全兼容：

```python
# ❌ C4D 2025
if gui.Question("确定删除?"):
    ...

# ✅ C4D 2026
if gui.QuestionDialog("确定删除?"):
    ...
```

---

### 5. storage.LoadDialog / SaveDialog 参数变更

**现象：** `TypeError: 'typeflags' is an invalid keyword argument for this function`

**根因：** C4D 2026 将分散的关键字参数统一为标准的 `type`、`flags`、`title`、`def_file`、`def_path`、`force_suffix`。

```python
# ❌ C4D 2025
fn = storage.LoadDialog(title="打开文件", flags=c4d.FILESELECT_LOAD,
                        typeflags=c4d.FILESELECTTYPE_ANYTHING)

# ✅ C4D 2026
fn = storage.LoadDialog(
    title="打开文件",
    flags=c4d.FILESELECT_LOAD,
    type=c4d.FILESELECTTYPE_ANYTHING,  # 注意：参数名从 typeflags → type
    def_file="template.json")           # 可选

# SaveDialog 同理
fn = storage.SaveDialog(title="保存文件", flags=c4d.FILESELECT_SAVE,
                        type=c4d.FILESELECTTYPE_ANYTHING,
                        def_file="template.json")
```

---

### 6. CreateLayout 签名变更

**现象：** `TypeError: CreateLayout() missing 1 required positional argument: 'parent_dlg'`

**根因：** C4D 2023 调用 `CreateLayout(self, parent_dlg)`，C4D 2026 调用 `CreateLayout(self)`。

**解决方案：** 用默认参数兼容两个版本：

```python
def CreateLayout(self, parent_dlg=None):
    # parent_dlg: C4D 2023 传入此参数，2026 不传
    ...
```

---

### 7. 常量不存在

**现象：** `AttributeError: module 'c4d' has no attribute 'CUSTOMGUI_COLORFIELD'`

**根因：** 低频使用的常量在 2026 中被移除。

**解决方案：** 在模块顶部加兼容层：

```python
def _c(name, fallback):
    return getattr(c4d, name, fallback)

_DESC_UNIT_NONE = _c('DESC_UNIT_NONE', 0)
_DESC_UNIT_METER = _c('DESC_UNIT_METER', 1)
# ... 低频常量都用 _c() 包裹
```

**风险判断：** UI 相关的常量（单位、自定义 GUI、边框样式）是高危区；数据类型常量（`DTYPE_REAL`、`DESC_NAME` 等）是稳定区。

---

### 8. AddStaticText / AddComboBox 参数变为仅位置参数

**现象：**
```
TypeError: 'border' is an invalid keyword argument for this function
TypeError: 'cols' is an invalid keyword argument for this function
```

**根因：** C4D 2026 Python SDK 将部分 GeDialog 方法的某些参数改为 **positional-only**（仅位置参数），不再接受关键字传参。

**已确认受影响的方法和参数：**

| 方法 | 受影响参数 | 原本写法 | 修正写法 |
|------|-----------|---------|---------|
| `AddStaticText` | `border` | `AddStaticText(id, ..., border=c4d.BORDER_THIN_IN)` | `AddStaticText(id, ..., c4d.BORDER_THIN_IN)`（第6个位置参数） |
| `AddComboBox` | `cols` | `AddComboBox(id, flags=..., cols=1)` | `AddComboBox(id, c4d.BFH_SCALEFIT, 1)`（第3个位置参数） |

**后续排查方法：** 其他参数如 `flags=`, `name=`, `initw=`, `inith=`, `title=`, `rows=`, `groupflags=`, `scrollflags=` 等**未受影响**。只有方法签名末位的、不太常用的参数可能被改成 positional-only。如果在 C4D 2026 遇到新的 `'xxx' is an invalid keyword argument` 错误，把该参数改为位置传参即可。

---

### 9. build_bc() 数据写入类型不匹配

**现象：** 应用用户数据到对象后，默认值显示为 0 或无法修改。

**根因：** `build_bc()` 中设置 `DESC_DEFAULT`/`DESC_MIN`/`DESC_MAX`/`DESC_STEP` 时，数据类型与 C4D 期望的不一致：

```python
# ❌ 错误 — 对 DTYPE_LONG 也用了 float
if self.dtype in (UDT.FLOAT, UDT.INTEGER, UDT.PERCENT, UDT.ANGLE):
    bc[c4d.DESC_DEFAULT] = float(self.default_v)

# ✅ 正确 — 按 C4D 数据类型分开处理
if self.dtype in (UDT.FLOAT, UDT.PERCENT, UDT.ANGLE):
    bc[c4d.DESC_DEFAULT] = float(self.default_v)  # DTYPE_REAL → float
elif self.dtype == UDT.INTEGER:
    bc[c4d.DESC_DEFAULT] = int(self.default_v)    # DTYPE_LONG → int
```

**类型对照表：**

| Python 类型 | C4D 数据类型 | DESC_DEFAULT 类型 |
|------------|-------------|------------------|
| FLOAT / PERCENT / ANGLE | `DTYPE_REAL` | `float` |
| INTEGER | `DTYPE_LONG` | `int` |
| BOOL | `DTYPE_BOOL` | `int(bool(...))` |
| COLOR / VECTOR | `DTYPE_VECTOR` | `c4d.Vector(...)` |
| STRING / FILENAME | `DTYPE_STRING` | `str` |
| DROPDOWN | `DTYPE_LONG` | `int(...)` |

**BOOL 特别注意：** `bool(50.0)` 在 Python 中是 `True`，但 C4D 的 `BaseContainer` 需要整数 0 或 1。应使用 `int(bool(self.default_v))`。

---

### 10. 对话框第二次打开崩溃

**现象：** 第一次打开正常，关闭后再次打开 → C4D 崩溃。

**崩溃栈：** `Py_HashPointer` + `PyIter_Send` — Python 尝试 hash 已释放的 C4D 对象。

**根因：** `RestoreLayout()` 未正确处理。C4D 可能在用户关闭对话框后调用 `RestoreLayout` 恢复布局。

**解决方案：**
1. `RestoreLayout` 直接返回 `True`（no-op）
2. `Execute` 作为唯一入口，每次执行时先安全关闭旧对话框，再创建新的

```python
def Execute(self, doc):
    if self._dlg is not None:
        try:
            self._dlg.Close()
        except Exception:
            pass
        self._dlg = None
    self._dlg = UserDataDialog()
    return self._dlg.Open(...)

def RestoreLayout(self, sec_ref):
    return True  # no-op，让 C4D 通过 Execute 重建
```

---

### 11. 对话框显示空白

**现象：** 异步对话框打开后完全空白，没有任何控件。

**根因：** 对话框的 Python 对象被垃圾回收了。`Execute()` 中用局部变量保存对话框时，函数返回后对象被回收，C4D 窗口失去 Python 回调连接。

**解决方案：** 用实例变量保持引用：

```python
class UserDataCommandData(c4d.plugins.CommandData):
    def __init__(self):
        self._dlg = None  # 保持引用，防止 GC

    def Execute(self, doc):
        self._dlg = UserDataDialog()
        ...
```

---

### 12. ListView 正向循环删除跳项

**现象（代码审查发现）：** 原 ListView 的清除循环存在 bug。

```python
# ❌ 正向删除 — 删除 index 0 后，原 index 1 变成 index 0，下一次 i=1 跳过原 index 1
for i in range(self.GetListViewCount(_lstMain)):
    self.RemoveListViewItem(_lstMain, i)

# ✅ 倒序删除 — 从末尾开始删，索引不受影响
cnt = self.GetListViewCount(_lstMain)
for i in range(cnt - 1, -1, -1):
    self.RemoveListViewItem(_lstMain, i)
```

---

### 13. Undo 记录爆炸

**现象：** 批量添加用户数据时，每一条 x 每一个对象都调用一次 `AddUndo`，undo 记录数量是 N×M。

**解决方案：** 先对所有要修改的对象统一标记 Undo，再循环添加数据：

```python
doc.StartUndo()
for obj in objs:
    doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)  # 一个 Undo 记录 / 对象
for obj in objs:
    for entry in entries:
        obj.AddUserData(entry.build_bc())
doc.EndUndo()
```

---

### 14. 异常堆栈被静默吞掉

**现象：** 插件报错但用户看不到任何提示（`print()` 输出到默认隐藏的控制台）。

**解决方案：** 收集异常，用 `gui.MessageDialog()` 显示：

```python
errors = []
try:
    ...
except Exception as ex:
    errors.append(f"{obj.GetName()}: {entry.name} → {ex}")

if errors:
    detail = "\n".join(errors[:5])
    gui.MessageDialog(f"失败: {len(errors)} 个\n\n{detail}")
```

---

### 15. ScrollGroup 内内容垂直居中

**现象：** ScrollGroup 中动态添加的列表条目垂直居中显示，不在顶部排列。经过多轮迭代，最终采用每行独立 Group 方案解决。

**历史演进（了解背景）：**

**方案 A（已废弃）：** `cols=4, rows=0` 直接添加控件
- 问题：Button 和 StaticText 默认高度不一致，且 `cols=4` 的 flow 布局在 C4D 中无法保证每行从顶部对齐
- 根因：不同控件类型（Button / StaticText）在 grid flow 中的高度计算方式不同

**方案 B（终版方案 ✅）：** `cols=1, rows=0` + 每行独立 Group

**核心思路：** 内容容器设为单列 (`cols=1, rows=0`)，每行的 4 个控件用一个独立的 Group (`cols=4, rows=1`) 包裹。这样 C4D 的布局引擎会将每行作为一个整体单元，各行独立计算高度，不会互相影响。

```python
# CreateLayout — 内容容器设为单列
self.GroupBegin(_gListContent, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                cols=1, rows=0, title="")
self.GroupEnd()

# _refresh_list — 每行用独立 Group 包裹
def _refresh_list(self):
    self.LayoutFlushGroup(_gListContent)
    for i, e in enumerate(self._entries):
        # 每行独立 Group：cols=4, rows=1 保证 4 个控件在同一行
        self.GroupBegin(0, flags=c4d.BFH_SCALEFIT, cols=4, rows=1, title="")
        self.GroupBorderSpace(0, 0, 0, 0)

        self.AddStaticText(..., inith=18, ...)   # 序号
        self.AddButton(..., inith=18, ...)        # 名称（可点击选中）
        self.AddStaticText(..., inith=18, ...)    # 类型
        self.AddStaticText(..., inith=18, ...)    # 默认值

        self.GroupEnd()
    self.LayoutChanged(_gScroll)
```

**关键要点：**
- `_gListContent` 用 `cols=1, rows=0`（单列动态行）
- 每行的 4 个控件用 `GroupBegin(0, cols=4, rows=1)` 包裹
- 所有控件统一设置 `inith=18` 确保行高一致
- `GroupBorderSpace(0, 0, 0, 0)` 消除行内边距

---

## 快速参考：C4D 2026 可用的 GeDialog 方法

从 C4D 2025 迁移时，以下方法被确认**仍然可用**（完整列表）：

```
AddButton, AddStaticText, AddEditText, AddComboBox, AddChild,
AddEditNumberArrows, AddEditNumber, AddSlider, AddCheckbox,
AddRadioButton, AddRadioGroup, AddSeparatorH, AddSeparatorV,
AddUserArea, AddCustomGui, AddPopupButton, AddColorField,
AddMultiLineEditText, AddSubDialog, AddDlgGroup,
GroupBegin, GroupEnd, GroupBorder, GroupBorderNoTitle,
GroupBorderSpace, GroupSpace, GroupBeginInMenuLine,
ScrollGroupBegin, TabGroupBegin,
SetString, SetReal, SetInt32, SetBool, SetFloat, SetLong,
SetFilename, SetTime, SetVector, SetColorField,
GetString, GetReal, GetInt32, GetBool, GetFloat, GetLong,
GetFilename, GetTime, GetVector, GetColorField, GetColorRGB,
Enable, HideElement, IsVisible, IsActive, IsEnabled, IsOpen,
LayoutChanged, LayoutChangedNoRedraw, LayoutFlushGroup, LayoutFlushDisableRedraw,
FreeChildren, RemoveElement,
SetTitle, Open, Close, GetId,
MenuAddString, MenuAddCommand, MenuAddSeparator, MenuFinished,
MenuFlushAll, MenuInitString, MenuSubBegin, MenuSubEnd,
```

### 已知受影响的参数（keyword → positional-only）

| 方法 | 参数 | 建议写法 |
|------|------|---------|
| `AddStaticText` | `border` | 第 6 个位置参数 |
| `AddComboBox` | `cols` | 第 3 个位置参数 |

## 开发建议

1. **先查 SDK 文档再写代码。** C4D 每次大版本都可能移除/重命名 API，2023→2026 之间的破坏性变更尤其多。
2. **动态控件用 LayoutFlushGroup + 内容组。** 不要重建 Group/ScrollGroup 本身，只刷新内部内容。**也不要在 `_refresh_list` 中对已存在组重复 GroupBegin**——布局参数不会更新。
3. **控件 ID 用基准值 + 偏移。** 动态生成的控件需要一个 ID 范围，`_ROW_BASE + index * stride + offset` 是最常见的模式。
4. **常量全部用 `_c()` 包裹。** 不确定是否存在的常量一律用 `getattr` 回退，避免运行时崩溃。
5. **异步对话框必须保持引用。** 用实例变量存对话框对象，防止被 Python GC 回收。
6. **外部输入必须校验。** JSON 模板加载时需要做类型检查，任何用户提供的文件都不可信。
7. **关键错误要弹对话框。** `print()` 在 C4D 插件中等同于不存在，用户看不见。
8. **build_bc() 的 DESC_DEFAULT 类型必须与 C4D 数据类型匹配。** DTYPE_LONG → int, DTYPE_REAL → float, DTYPE_BOOL → int(bool(...))，混用会导致默认值写入失败。
9. **GeDialog 参数如果报 `'xxx' is an invalid keyword argument`，改为位置传参。** C4D 2026 中将部分边缘参数改为了 positional-only。
