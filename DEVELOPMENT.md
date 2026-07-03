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

**解决方案：** 用 `ScrollGroup` + 逐行动态按钮模拟多列列表：

```python
# 在 CreateLayout 中创建骨架
self.ScrollGroupBegin(_gScroll, flags=..., scrollflags=c4d.SCROLLGROUP_VERT)
self.GroupBegin(_gListContent, flags=..., cols=1, rows=1, title="")
self.GroupEnd()  # _gListContent（由 _refresh_list 动态填充）
self.GroupEnd()  # ScrollGroup
```

```python
# 在 _refresh_list 中动态填充
def _refresh_list(self):
    self.LayoutFlushGroup(_gListContent)
    self.GroupBegin(_gListContent, ..., cols=1, rows=len(self._entries) or 1)
    for i, entry in enumerate(self._entries):
        base = _ROW_BASE + i * _ROW_STRIDE
        self.GroupBegin(base + 1000, ..., cols=4, rows=1)
        self.AddStaticText(base,     ..., name=str(i+1))      # 序号
        self.AddButton(base + 1,     ..., name=entry.name)    # 名称（可点击选中）
        self.AddStaticText(base + 2, ..., name=UDT.name(...)) # 类型
        self.AddStaticText(base + 3, ..., name=...)            # 默认值
        self.GroupEnd()
    self.GroupEnd()  # _gListContent
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
- 刷新时机：`LayoutFlushGroup` → 重建 → `LayoutChanged(父group)`
- 必须嵌套一个中间 Group（`_gListContent`），不要直接 Flush ScrollGroup
- 行控件 ID 用基准值 + 偏移量计算，确保不冲突

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

**解决方案：** 改用 `AddPopupButton`，它创建一个始终带下拉箭头的按钮，通过 `AddChild` 添加选项。

```python
# ❌ C4D 2025
menu = gui.GePopupMenu()
for i, p in enumerate(PRESETS):
    menu.AddString(i, p["name"])
result = menu.Open(self, x=0, y=0)

# ✅ C4D 2026
self.AddPopupButton(_btnPreset, flags=c4d.BFH_LEFT, initw=70)
self.SetPopup(_btnPreset, "预设 ▼")
for i, p in enumerate(PRESETS):
    self.AddChild(_btnPreset, i, p["name"])

# 在 Command 中获取选择
def Command(self, mid, bc):
    if mid == _btnPreset:
        idx = self.GetInt32(_btnPreset)
```

**注意：** `AddPopupButton` 不接受 `cols` 参数（`'cols' is an invalid keyword argument`）。

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

### 8. 对话框第二次打开崩溃

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

### 9. 对话框显示空白

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

### 10. ListView 正向循环删除跳项

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

### 11. Undo 记录爆炸

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

### 12. 异常堆栈被静默吞掉

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

## 开发建议

1. **先查 SDK 文档再写代码。** C4D 每次大版本都可能移除/重命名 API，2023→2026 之间的破坏性变更尤其多。
2. **动态控件用 LayoutFlushGroup + 内容组。** 不要重建 Group/ScrollGroup 本身，只刷新内部内容。
3. **控件 ID 用基准值 + 偏移。** 动态生成的控件需要一个 ID 范围，`_ROW_BASE + index * stride + offset` 是最常见的模式。
4. **常量全部用 `_c()` 包裹。** 不确定是否存在的常量一律用 `getattr` 回退，避免运行时崩溃。
5. **异步对话框必须保持引用。** 用实例变量存对话框对象，防止被 Python GC 回收。
6. **外部输入必须校验。** JSON 模板加载时需要做类型检查，任何用户提供的文件都不可信。
7. **关键错误要弹对话框。** `print()` 在 C4D 插件中等同于不存在，用户看不见。
