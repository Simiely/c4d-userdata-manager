# 开发笔记

记录开发过程中遇到的关键问题和解决思路。

---

## 1. C4D Python SDK 常量缺失

**现象：** C4D 2026 报 `AttributeError: module 'c4d' has no attribute 'CUSTOMGUI_COLORFIELD'`

**根因：** C4D Python SDK 在每个版本中并非包含全部 C++ API 常量。`DESC_UNIT_NONE`、`CUSTOMGUI_COLORFIELD` 等一些低频使用的常量在 2026 版本中被移除。

**解决：** 在模块顶部加入兼容层，用 `getattr` 动态获取，不存在时回退到已知的整数值。

```python
def _c(name, fallback):
    return getattr(c4d, name, fallback)

_DESC_UNIT_NONE = _c('DESC_UNIT_NONE', 0)      # 0
_DESC_UNIT_METER = _c('DESC_UNIT_METER', 1)     # 1
# ... 共 12 个常量
```

**教训：** 不要假设 `c4d.XXX` 常量在所有版本中都存在。引用任何 `c4d.` 常量时都应该评估其被移除的可能性。低频常量（UI 相关、单位、自定义 GUI）是高危区。

---

## 2. 对话框第二次打开崩溃

**现象：** 第一次打开正常，关闭后再次打开 → C4D 崩溃。

**崩溃栈：** `Py_HashPointer` + `PyIter_Send` —— Python 尝试 hash 已释放的 C4D 对象。

**根因：** `RestoreLayout()` 未正确处理。C4D 可能在用户关闭对话框后调用 `RestoreLayout` 恢复布局，如果该函数尝试 `Open()` 一个已经销毁的旧对话框，导致崩溃。

**解决：**
1. `RestoreLayout` 直接返回 `True`（不做任何操作）
2. `Execute` 作为唯一入口，每次执行时先尝试关闭旧的对话框（`try/except` 安全包裹），再创建新的

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

**教训：** C4D 异步对话框有两个入口（`Execute` 和 `RestoreLayout`），后者容易被忽略。对异步对话框，`RestoreLayout` 做 no-op 是最安全的策略。

---

## 3. GeDialog API 参数不存在

**现象：** `TypeError: 'dialogid' is an invalid keyword argument for this function`

**根因：** C4D Python 的 `GeDialog.Open()` 不接受 `dialogid` 参数（这个参数是 C++ API 的，Python 绑定中不存在）。同理，`GeDialog.IsOpen()` 方法也可能不存在。

**解决：** 不使用任何"不确定存在"的方法或参数。用 `try/except` 包裹可能失败的方法调用。用状态跟踪替代 API 查询。

```python
# ❌ 不存在的 API
self._dlg.Open(..., dialogid=0)
self._dlg.IsOpen()

# ✅ 安全的做法
try:
    self._dlg.Close()
except Exception:
    pass
self._dlg = UserDataDialog()
self._dlg.Open(...)
```

**教训：** C4D Python SDK 和 C++ SDK 的 API 并不完全一致。参考他人代码时要注意区分是 C++ 还是 Python。

---

## 4. 对话框显示空白

**现象：** 面板打开后完全空白，没有任何控件。

**根因：** 异步对话框的 Python 对象被垃圾回收了。`Execute()` 中用局部变量 `dlg = Dialog()`，函数返回后 `dlg` 被回收，C4D 窗口失去 Python 回调连接，显示空白。

**解决：** 用 `self._dlg` 保存对话框引用。

```python
class UserDataCommandData(c4d.plugins.CommandData):
    def __init__(self):
        self._dlg = None  # 保持引用，防止 GC

    def Execute(self, doc):
        self._dlg = UserDataDialog()
        ...
```

**教训：** C4D Python 的对象生命周期管理需要手动介入。任何跨函数/跨消息需要存活的 C4D 对象，都必须保存在实例变量或全局变量中。

---

## 5. Undo 记录爆炸

**现象：** 批量添加用户数据时，每一条 x 每一个对象都调用一次 `AddUndo`，undo 记录数量是 N×M。

**解决：** 先对所有要修改的对象统一标记一次 Undo，再循环添加数据。

```python
doc.StartUndo()
# 先标记所有对象（一个 undo 记录 / 对象）
for obj in objs:
    doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
# 再批量添加数据
for obj in objs:
    for entry in entries:
        obj.AddUserData(entry.build_bc())
doc.EndUndo()
```

**教训：** 在一个 `StartUndo` / `EndUndo` 块中，`AddUndo` 记录的是状态快照。多个 `AddUndo` 不会合并为一条 undo 记录，而是会产生多次撤销步骤。只在必要时对真正变化的对象做标记。

---

## 6. 异常堆栈被静默吞掉

**现象：** 插件报错但用户看不到任何提示。错误通过 `print()` 输出到 C4D 控制台，但控制台默认隐藏。

**解决：** 将所有运行时异常收集到列表中，通过 `gui.MessageDialog()` 显示给用户，最多显示前 5 条详情。

```python
errors = []
try:
    ...
except Exception as ex:
    errors.append(f"{obj.GetName()}: {entry.name} → {ex}")

if errors:
    detail = "\n".join(errors[:5])
    gui.MessageDialog(f"失败: {len(errors)} 个\n\n{detail}")
else:
    gui.MessageDialog("✅ 全部成功")
```

**教训：** `print()` 在 C4D 插件中基本等于"用户看不见"。关键错误必须通过对话框、状态栏或日志文件告知用户。

---

## 7. JSON 模板加载无校验

**现象：** 加载一个结构损坏的模板 JSON 文件会导致 `Entry.from_dict` 产生异常状态，后续操作可能崩溃。

**解决：** 在 `from_dict` 之前对数据结构做逐级校验：

```python
raw = data.get("entries")
if not isinstance(raw, list):
    return  # ❌ 格式错误
for i, item in enumerate(raw):
    if not isinstance(item, dict):
        return  # ❌ 条目格式错误
    if "name" not in item or "type" not in item:
        return  # ❌ 缺少必要字段
    if not isinstance(item["type"], int) or item["type"] not in UDT._ALL_TYPES:
        return  # ❌ 类型值非法
entries = [Entry.from_dict(e) for e in raw]
```

**教训：** 外部输入（文件、网络、用户输入）在任何时候都不可信。解序列化之前必须做类型检查和边界校验。

---

## 8. Color 类型的默认值输入限制

**现象：** 插件 UI 中 Color 类型的默认值只能输入一个浮点数（灰度值），无法设置 RGB 颜色。

**原因：** `AddEditNumberArrows` 是单值输入控件。要实现 RGB 输入需要三个独立的数值输入框或一个文本输入框加上颜色解析。

**当前策略：** 插件 UI 中只设置灰度默认值，具体颜色在应用到对象后通过 C4D 原生拾色器调整。这是有意为之的取舍——C4D 的拾色器比任何文本输入都好用。

**教训：** 不是所有功能缺陷都值得在插件 UI 中解决。如果 C4D 原生工具做得更好，就让插件做"足够好"的事情，把精细调整留给原生工具。

---

## 9. `Open()` 参数列表

C4D Python 中 `GeDialog.Open()` 的有效参数（C4D 2023~2026 验证通过）：

```python
dlg.Open(
    dlgtype,          # DLG_TYPE_ASYNC / DLG_TYPE_MODAL / ...
    pluginid=0,       # 插件 ID，用于窗口管理
    defaultw=0,       # 默认宽度
    defaulth=0,       # 默认高度
    xpos=-1, ypos=-1, # 位置，-1 为自动
    subid=0           # 子窗口 ID
)
```

> 注意：`dialogid` 参数在 Python API 中不存在。

---

## 10. 后续开发备忘

### 可能的改进方向

- 支持在列表中**直接编辑**条目名称（当前需要点选后在属性面板修改）
- 支持 Drag & Drop 调整条目顺序
- 添加"应用到场景全部对象"选项
- 预设系统的用户自定义（保存/管理自建预设）
- 多语言界面支持

### 已知无风险的 c4d 常量

以下常量在 C4D R13~2026 中始终存在，可以直接使用：

| 类别 | 常量 |
|---|---|
| 数据类型 | `DTYPE_REAL` `DTYPE_LONG` `DTYPE_BOOL` `DTYPE_COLOR` `DTYPE_VECTOR` `DTYPE_STRING` `DTYPE_FILENAME` |
| 描述 ID | `DESC_NAME` `DESC_SHORT_NAME` `DESC_MIN` `DESC_MAX` `DESC_STEP` `DESC_DEFAULT` `DESC_UNIT` `DESC_CUSTOMGUI` |
| 布局 | `BFH_LEFT` `BFH_RIGHT` `BFH_SCALEFIT` `BFV_SCALEFIT` |
| 消息 | `BFM_INPUT` `BFM_INPUT_CHANNEL` `BFM_INPUT_KEYBOARD` `BFM_INPUT_VALUE` |
| 键盘 | `KEY_DELETE` `KEY_BACKSPACE` |
| 其他 | `UNDOTYPE_CHANGE` `DLG_TYPE_ASYNC` `LV_REPORT` `EventAdd` `Vector` `BaseContainer` |

---

## 11. C4D 2026 — `CreateLayout` 签名变更

**现象：** C4D 2026 报 `TypeError: CreateLayout() missing 1 required positional argument: 'parent_dlg'`

**根因：** C4D 2026 的 `GeDialog.CreateLayout()` 不再传入 `parent_dlg` 参数。旧版签名是 `CreateLayout(self, parent_dlg)`，新版是 `CreateLayout(self)`。

**解决：** 用带默认值的方式兼容两个版本：

```python
def CreateLayout(self, parent_dlg=None):
    ...
```

**教训：** C4D 跨版本开发时，所有 `GeDialog` 的重写方法都要注意参数签名变化。`CreateLayout`、`InitValues`、`Command` 等都可能在不同版本中增减参数。

---

## 12. C4D 2026 — `FreezeListView` / `ThawListView` 被移除

**现象：** `AttributeError: 'UserDataDialog' object has no attribute 'FreezeListView'`

**根因：** C4D 2026 Python SDK 移除了 `FreezeListView()` 和 `ThawListView()` 方法。这两个方法原是 ListView 批量操作时的性能优化（冻结重绘），新版 SDK 内部已优化，不再需要手动冻结。

**解决：** 直接删除这俩调用即可。同时反向修复了原代码中 `RemoveListViewItem` 正向循环删除会跳项的 bug：

```python
# ❌ 旧代码（正向删除会跳项）
for i in range(self.GetListViewCount(_lstMain)):
    self.RemoveListViewItem(_lstMain, i)

# ✅ 新代码（倒序删除，安全）
cnt = self.GetListViewCount(_lstMain)
for i in range(cnt - 1, -1, -1):
    self.RemoveListViewItem(_lstMain, i)
```

**教训：** 
- C4D 2026 移除了一些低频的 UI 辅助方法，批量操作 ListView 时不再需要手动冻结/解冻
- 删除最后一个元素开始逆向遍历是通用安全的做法
- 升级 SDK 版本时不仅要关注新增功能，还要检查被移除的 API
