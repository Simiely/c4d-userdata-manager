"""UserData Manager for Cinema 4D
================================================================

轻量级用户数据 (User Data) 管理插件，方便快速创建/管理用户数据，
供 Xpresso / Python / 表达式 直接调用。

兼容版本: C4D 2023 ~ 2026
使用时通过 扩展(Extensions) → UserData Manager 打开

使用方法:
  1. 在插件中添加需要的用户数据条目
  2. 在场景中选择一个或多个对象
  3. 点击"应用到对象"将用户数据添加到对象上
  4. 在 Xpresso 编辑器中拖入对象即可看到用户数据端口

Author  : Your Name
License : MIT
"""

import c4d
from c4d import gui, storage
import json
from typing import Optional

__version__ = "1.1.0"


# ─────────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────────

# ★ 重要：到 plugincafe.maxon.net 注册免费插件 ID 后替换此处
PLUGIN_ID   = 1060001
PLUGIN_NAME = "UserData Manager"
PLUGIN_HELP = "快速创建和管理用户数据，供 Xpresso 使用"

# ── 控件 ID ───────────────────────────────────────────────────────
_gRoot   = 1000
_gTop    = 1001
_gBody   = 1002
_gList   = 1003
_gProp   = 1004
_gBot    = 1005

_lstMain = 2000

_btnAdd    = 2101
_btnDel    = 2102
_btnDup    = 2103
_btnUp     = 2104
_btnDown   = 2105
_btnApply  = 2106
_btnSave   = 2107
_btnLoad   = 2108
_btnPreset = 2109
_btnClear  = 2110

_edtName    = 2201
_cmbType    = 2202
_edtMin     = 2203
_edtMax     = 2204
_edtStep    = 2205
_edtDefault = 2206
_cmbUnit    = 2207
_edtGroup   = 2208
_edtDesc    = 2209
_edtDDItems = 2210

_txtInfo = 2400


# ─────────────────────────────────────────────────────────────────
# 数据类型
# ─────────────────────────────────────────────────────────────────

class UDT:
    """用户数据类型枚举"""
    FLOAT    = 0
    INTEGER  = 1
    BOOL     = 2
    COLOR    = 3
    VECTOR   = 4
    ANGLE    = 5
    PERCENT  = 6
    STRING   = 7
    DROPDOWN = 8
    FILENAME = 9

    LABELS = {
        FLOAT:    "Float 浮点数",
        INTEGER:  "Integer 整数",
        BOOL:     "Boolean 布尔",
        COLOR:    "Color 颜色",
        VECTOR:   "Vector 向量",
        ANGLE:    "Angle 角度 (°)",
        PERCENT:  "Percentage 百分比",
        STRING:   "String 字符串",
        DROPDOWN: "Dropdown 下拉列表",
        FILENAME: "Filename 文件路径",
    }

    # 类型 → C4D 内部类型（静态，只构建一次）
    _DTYPE_MAP = {
        FLOAT:    c4d.DTYPE_REAL,
        INTEGER:  c4d.DTYPE_LONG,
        BOOL:     c4d.DTYPE_BOOL,
        COLOR:    c4d.DTYPE_COLOR,
        VECTOR:   c4d.DTYPE_VECTOR,
        ANGLE:    c4d.DTYPE_REAL,
        PERCENT:  c4d.DTYPE_REAL,
        STRING:   c4d.DTYPE_STRING,
        DROPDOWN: c4d.DTYPE_LONG,
        FILENAME: c4d.DTYPE_FILENAME,
    }
    _UNIT_MAP = {
        ANGLE:   c4d.DESC_UNIT_DEGREE,
        PERCENT: c4d.DESC_UNIT_PERCENT,
    }
    _GUI_MAP = {
        COLOR:    c4d.CUSTOMGUI_COLORFIELD,
        DROPDOWN: c4d.CUSTOMGUI_CYCLECUSTOM,
    }
    _RANGE_TYPES = {FLOAT, INTEGER, PERCENT, ANGLE, VECTOR}
    _NUMERIC_TYPES = {FLOAT, INTEGER, PERCENT, ANGLE, VECTOR, COLOR}
    _ALL_TYPES = [FLOAT, INTEGER, BOOL, COLOR, VECTOR,
                  ANGLE, PERCENT, STRING, DROPDOWN, FILENAME]

    @classmethod
    def list(cls):
        return cls._ALL_TYPES

    @classmethod
    def name(cls, t):
        return cls.LABELS.get(t, "未知")

    @classmethod
    def c4d_dtype(cls, t):
        return cls._DTYPE_MAP.get(t, c4d.DTYPE_REAL)

    @classmethod
    def c4d_unit(cls, t):
        return cls._UNIT_MAP.get(t, c4d.DESC_UNIT_NONE)

    @classmethod
    def c4d_gui(cls, t):
        return cls._GUI_MAP.get(t, c4d.CUSTOMGUI_REALSLIDER)

    @classmethod
    def has_range(cls, t):
        return t in cls._RANGE_TYPES

    @classmethod
    def is_numeric(cls, t):
        return t in cls._NUMERIC_TYPES


# ─────────────────────────────────────────────────────────────────
# 数据条目
# ─────────────────────────────────────────────────────────────────

class Entry:
    """一条用户数据条目"""
    __slots__ = (
        "name", "dtype", "min_v", "max_v", "step",
        "default_v", "unit", "group", "desc", "dd_items"
    )

    def __init__(self, name="Param", dtype=UDT.FLOAT,
                 min_v=0.0, max_v=100.0, step=1.0,
                 default_v=50.0, unit=c4d.DESC_UNIT_NONE,
                 group="", desc="", dd_items="Item 1\nItem 2\nItem 3"):
        self.name = name
        self.dtype = dtype
        self.min_v = min_v
        self.max_v = max_v
        self.step = step
        self.default_v = default_v
        self.unit = unit
        self.group = group
        self.desc = desc
        self.dd_items = dd_items

    def build_bc(self) -> c4d.BaseContainer:
        """构建 C4D 用户数据定义 BaseContainer"""
        bc = c4d.GetCustomDataTypeDefault(UDT.c4d_dtype(self.dtype))
        bc[c4d.DESC_NAME] = self.name

        if self.dtype in (UDT.FLOAT, UDT.INTEGER, UDT.PERCENT, UDT.ANGLE):
            bc[c4d.DESC_MIN]     = float(self.min_v)
            bc[c4d.DESC_MAX]     = float(self.max_v)
            bc[c4d.DESC_STEP]    = float(self.step)
            bc[c4d.DESC_DEFAULT] = float(self.default_v)

        elif self.dtype == UDT.VECTOR:
            bc[c4d.DESC_MIN]     = c4d.Vector(self.min_v, self.min_v, self.min_v)
            bc[c4d.DESC_MAX]     = c4d.Vector(self.max_v, self.max_v, self.max_v)
            bc[c4d.DESC_STEP]    = c4d.Vector(self.step, self.step, self.step)
            bc[c4d.DESC_DEFAULT] = c4d.Vector(self.default_v, self.default_v, self.default_v)

        elif self.dtype == UDT.BOOL:
            bc[c4d.DESC_DEFAULT] = bool(self.default_v)

        elif self.dtype == UDT.COLOR:
            bc[c4d.DESC_DEFAULT] = self._parse_color(self.default_v)

        elif self.dtype in (UDT.STRING, UDT.FILENAME):
            bc[c4d.DESC_DEFAULT] = str(self.default_v or "")

        elif self.dtype == UDT.DROPDOWN:
            bc[c4d.DESC_DEFAULT] = int(float(self.default_v or 0))
            self._build_dropdown(bc)

        # 单位
        u = UDT.c4d_unit(self.dtype)
        bc[c4d.DESC_UNIT] = u if u != c4d.DESC_UNIT_NONE else self.unit

        # 分组短名
        if self.group.strip():
            bc[c4d.DESC_SHORT_NAME] = self.group.strip()

        # 自定义 GUI
        g = UDT.c4d_gui(self.dtype)
        if g:
            bc[c4d.DESC_CUSTOMGUI] = g

        return bc

    def _parse_color(self, val) -> c4d.Vector:
        if isinstance(val, (int, float)):
            return c4d.Vector(float(val), float(val), float(val))
        try:
            parts = str(val).replace("(", "").replace(")", "").split(",")
            parts = [float(p.strip()) for p in parts if p.strip()]
            if len(parts) >= 3:
                return c4d.Vector(parts[0], parts[1], parts[2])
            if len(parts) == 1:
                return c4d.Vector(parts[0], parts[0], parts[0])
        except (ValueError, TypeError):
            pass
        return c4d.Vector(1, 1, 1)

    def _build_dropdown(self, bc):
        items = [s.strip() for s in self.dd_items.split("\n") if s.strip()]
        for i, item in enumerate(items):
            bc.SetString(c4d.DESC_CYCLE + i, item)
        bc[c4d.DESC_CYCLE_COUNT] = len(items)

    # ── 序列化 ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.dtype,
            "min": self.min_v,
            "max": self.max_v,
            "step": self.step,
            "default": self.default_v,
            "unit": self.unit,
            "group": self.group,
            "desc": self.desc,
            "dd_items": self.dd_items,
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            name=d.get("name", "Param"),
            dtype=d.get("type", UDT.FLOAT),
            min_v=d.get("min", 0.0),
            max_v=d.get("max", 100.0),
            step=d.get("step", 1.0),
            default_v=d.get("default", 50.0),
            unit=d.get("unit", c4d.DESC_UNIT_NONE),
            group=d.get("group", ""),
            desc=d.get("desc", ""),
            dd_items=d.get("dd_items", "Item 1\nItem 2\nItem 3"),
        )

    def copy(self):
        return Entry(self.name, self.dtype, self.min_v, self.max_v,
                     self.step, self.default_v, self.unit,
                     self.group, self.desc, self.dd_items)

    def display_value(self) -> str:
        if self.dtype == UDT.COLOR:
            try:
                v = self._parse_color(self.default_v)
                return f"{v.x:.2f}, {v.y:.2f}, {v.z:.2f}"
            except Exception:
                return str(self.default_v)
        elif self.dtype == UDT.BOOL:
            return "是" if self.default_v else "否"
        elif self.dtype == UDT.PERCENT:
            return f"{self.default_v}%"
        elif self.dtype == UDT.ANGLE:
            return f"{self.default_v}°"
        elif self.dtype == UDT.DROPDOWN:
            items = [s.strip() for s in self.dd_items.split("\n") if s.strip()]
            idx = int(float(self.default_v or 0))
            if 0 <= idx < len(items):
                return items[idx]
            return str(self.default_v)
        return str(self.default_v)


# ─────────────────────────────────────────────────────────────────
# 预设
# ─────────────────────────────────────────────────────────────────

PRESETS = [
    {"name": "Speed 速度",    "entries": [Entry("Speed",    UDT.FLOAT,   0, 100,   1, 50)]},
    {"name": "Strength 强度", "entries": [Entry("Strength", UDT.PERCENT, 0, 200,   1, 100)]},
    {"name": "Opacity 透明度", "entries": [Entry("Opacity",  UDT.PERCENT, 0, 100,   1, 100)]},
    {"name": "Scale 缩放",    "entries": [Entry("Scale",    UDT.PERCENT, 0, 500,   1, 100)]},
    {"name": "Color 颜色",    "entries": [Entry("Color",    UDT.COLOR,   0, 1,   0.01, 1)]},
    {"name": "Position 位置偏移", "entries": [
        Entry("Offset.X", UDT.FLOAT, -1000, 1000, 1, 0),
        Entry("Offset.Y", UDT.FLOAT, -1000, 1000, 1, 0),
        Entry("Offset.Z", UDT.FLOAT, -1000, 1000, 1, 0),
    ]},
    {"name": "Rotation 旋转", "entries": [
        Entry("Rotate.X", UDT.ANGLE, 0, 360, 1, 0),
        Entry("Rotate.Y", UDT.ANGLE, 0, 360, 1, 0),
        Entry("Rotate.Z", UDT.ANGLE, 0, 360, 1, 0),
    ]},
    {"name": "Random Seed",  "entries": [
        Entry("Seed",      UDT.INTEGER, 0, 99999, 1, 0),
        Entry("Randomize", UDT.BOOL,    0, 1, 1, True),
    ]},
    {"name": "Count 计数",   "entries": [Entry("Count", UDT.INTEGER, 1, 1000, 1, 10)]},
    {"name": "Enable 开关",  "entries": [Entry("Enabled", UDT.BOOL, 0, 1, 1, True)]},
    {"name": "Falloff 衰减", "entries": [
        Entry("Radius",  UDT.FLOAT,   0, 1000, 1, 100),
        Entry("Falloff", UDT.PERCENT, 0, 100,  1, 50),
    ]},
    {"name": "Weights 权重", "entries": [
        Entry("Weight A", UDT.FLOAT, 0, 1, 0.01, 0.5),
        Entry("Weight B", UDT.FLOAT, 0, 1, 0.01, 0.5),
    ]},
    {"name": "Material 材质", "entries": [
        Entry("Metallic",  UDT.PERCENT, 0, 100, 1, 0),
        Entry("Roughness", UDT.PERCENT, 0, 100, 1, 50),
        Entry("Emission",  UDT.COLOR,   0, 1, 0.01, 0),
    ]},
]


# ─────────────────────────────────────────────────────────────────
# 对话框
# ─────────────────────────────────────────────────────────────────

class UserDataDialog(gui.GeDialog):
    """主对话框"""

    def __init__(self):
        super().__init__()
        self._entries: list[Entry] = []
        self._sel: int = -1

    # ── 布局 ───────────────────────────────────────────────────────

    def CreateLayout(self, parent_dlg):
        self.SetTitle(f"{PLUGIN_NAME}  v{__version__}")
        self.GroupBegin(_gRoot, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                        cols=1, rows=3, title="")
        self.GroupBorderSpace(6, 6, 6, 6)

        # ─── 工具栏 ───
        self.GroupBegin(_gTop, flags=c4d.BFH_SCALEFIT, cols=11, rows=1, title="")
        self.GroupBorderSpace(0, 0, 0, 4)
        self.AddButton(_btnAdd,    flags=c4d.BFH_LEFT, initw=32, inith=24, name="＋")
        self.AddButton(_btnDel,    flags=c4d.BFH_LEFT, initw=32, inith=24, name="－")
        self.AddButton(_btnDup,    flags=c4d.BFH_LEFT, initw=32, inith=24, name="⧉")
        self.AddButton(_btnUp,     flags=c4d.BFH_LEFT, initw=32, inith=24, name="↑")
        self.AddButton(_btnDown,   flags=c4d.BFH_LEFT, initw=32, inith=24, name="↓")
        self.AddSeparatorH(initw=8)
        self.AddButton(_btnPreset, flags=c4d.BFH_LEFT, initw=70, inith=24, name="预设")
        self.AddButton(_btnSave,   flags=c4d.BFH_LEFT, initw=50, inith=24, name="保存")
        self.AddButton(_btnLoad,   flags=c4d.BFH_LEFT, initw=50, inith=24, name="加载")
        self.AddButton(_btnClear,  flags=c4d.BFH_LEFT, initw=50, inith=24, name="清空")
        self.AddButton(_btnApply,  flags=c4d.BFH_RIGHT, initw=120, inith=24, name="▸ 应用到对象")
        self.GroupEnd()

        # ─── 主体: 列表 + 属性 ───
        self.GroupBegin(_gBody, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                        cols=2, rows=1, title="")
        self.GroupBorderSpace(0, 0, 0, 4)

        # 左侧列表
        self.GroupBegin(_gList, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                        cols=1, rows=1, title="")
        self.GroupBorderNoTitle(c4d.BORDER_NONE)
        self.AddListView(_lstMain, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=4)
        self.SetListViewColumn(_lstMain, 0, "#",   30)
        self.SetListViewColumn(_lstMain, 1, "名称", 130)
        self.SetListViewColumn(_lstMain, 2, "类型", 110)
        self.SetListViewColumn(_lstMain, 3, "默认值", 100)
        self.GroupEnd()

        # 右侧属性面板
        self.GroupBegin(_gProp, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                        cols=2, rows=13, title="属性",
                        groupflags=c4d.BORDER_GROUP_TOP | c4d.BORDER_WITH_TITLE)
        self.GroupBorderSpace(4, 2, 4, 4)

        # 名称
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="名称:")
        self.AddEditText(_edtName, flags=c4d.BFH_SCALEFIT, initw=140, inith=0)

        # 类型
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="类型:")
        self.AddComboBox(_cmbType, flags=c4d.BFH_SCALEFIT, cols=1)
        for dt in UDT.list():
            self.AddChild(_cmbType, dt, UDT.name(dt))

        # 分组
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="分组:")
        self.AddEditText(_edtGroup, flags=c4d.BFH_SCALEFIT, initw=140, inith=0)

        # 最小值
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="最小值:")
        self.AddEditNumberArrows(_edtMin, flags=c4d.BFH_SCALEFIT)

        # 最大值
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="最大值:")
        self.AddEditNumberArrows(_edtMax, flags=c4d.BFH_SCALEFIT)

        # 步幅
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="步幅:")
        self.AddEditNumberArrows(_edtStep, flags=c4d.BFH_SCALEFIT)

        # 默认值
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="默认值:")
        self.AddEditNumberArrows(_edtDefault, flags=c4d.BFH_SCALEFIT)

        # 单位
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="单位:")
        self.AddComboBox(_cmbUnit, flags=c4d.BFH_SCALEFIT, cols=1)
        _units = [
            (c4d.DESC_UNIT_NONE,       "无"),
            (c4d.DESC_UNIT_METER,      "米 (m)"),
            (c4d.DESC_UNIT_CENTIMETER, "厘米 (cm)"),
            (c4d.DESC_UNIT_MILLIMETER, "毫米 (mm)"),
            (c4d.DESC_UNIT_KILOMETER,  "千米 (km)"),
            (c4d.DESC_UNIT_DEGREE,     "度 (°)"),
            (c4d.DESC_UNIT_PERCENT,    "百分比 (%)"),
            (c4d.DESC_UNIT_SECOND,     "秒 (s)"),
            (c4d.DESC_UNIT_FRAME,      "帧 (f)"),
        ]
        for uid, ulabel in _units:
            self.AddChild(_cmbUnit, uid, ulabel)

        # 说明
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="说明:")
        self.AddEditText(_edtDesc, flags=c4d.BFH_SCALEFIT, initw=140, inith=0)

        # 下拉选项
        self.AddStaticText(0, flags=c4d.BFH_LEFT, name="下拉选项\n(每行一项):")
        self.AddEditText(_edtDDItems, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                         initw=140, inith=50)

        self.GroupEnd()  # _gProp
        self.GroupEnd()  # _gBody

        # ─── 底部状态 ───
        self.GroupBegin(_gBot, flags=c4d.BFH_SCALEFIT, cols=1, rows=1, title="")
        self.GroupBorderSpace(0, 4, 0, 0)
        self.AddStaticText(_txtInfo, flags=c4d.BFH_SCALEFIT, name="就绪")
        self.GroupEnd()

        self.GroupEnd()  # _gRoot
        return True

    # ── 初始化 ─────────────────────────────────────────────────────

    def InitValues(self):
        self._refresh_list()
        self._update_props()
        self._update_status()
        return True

    # ── 消息处理 ───────────────────────────────────────────────────

    def Command(self, mid, bc):
        # ── 键盘快捷键 ──
        if mid == c4d.BFM_INPUT:
            chn = bc[c4d.BFM_INPUT_CHANNEL]
            if chn == c4d.BFM_INPUT_KEYBOARD:
                key = bc[c4d.BFM_INPUT_VALUE]
                # Delete / Backspace 删除选中条目
                if key in (c4d.KEY_DELETE, c4d.KEY_BACKSPACE) and \
                   self._get_entry():
                    self._del()
                    self._refresh_list()
                    self._update_status()
                    return True
            return True

        # 列表选择变化
        if mid == _lstMain:
            sel = self.GetSelectedListViewItem(_lstMain)
            self._sel = sel if sel >= 0 else -1
            self._update_props()
            self._update_status()
            return True

        # 操作按钮
        if mid == _btnAdd:
            self._add()
        elif mid == _btnDel:
            self._del()
        elif mid == _btnDup:
            self._dup()
        elif mid == _btnUp:
            self._move(-1)
        elif mid == _btnDown:
            self._move(1)
        elif mid == _btnClear:
            self._clear_all()
        elif mid == _btnApply:
            self._apply_to_objects()
        elif mid == _btnSave:
            self._save_template()
        elif mid == _btnLoad:
            self._load_template()
        elif mid == _btnPreset:
            self._show_presets()

        # 属性编辑
        elif mid in (_edtName, _edtGroup, _edtDesc, _edtDDItems,
                     _edtMin, _edtMax, _edtStep, _edtDefault,
                     _cmbType, _cmbUnit):
            self._update_entry_from_ui()
            # 切换类型时立即刷新属性面板
            if mid == _cmbType:
                self._update_props()

        self._refresh_list()
        self._update_status()
        return True

    # ── 增删改 ─────────────────────────────────────────────────────

    def _add(self):
        self._entries.append(Entry())
        self._sel = len(self._entries) - 1
        self._update_props()

    def _del(self):
        if not (0 <= self._sel < len(self._entries)):
            return
        name = self._entries[self._sel].name
        if not gui.Question(f"确定删除「{name}」?"):
            return
        del self._entries[self._sel]
        self._sel = min(self._sel, len(self._entries) - 1)
        self._update_props()

    def _dup(self):
        if not (0 <= self._sel < len(self._entries)):
            return
        e = self._entries[self._sel].copy()
        e.name += "_copy"
        self._entries.insert(self._sel + 1, e)
        self._sel += 1
        self._update_props()

    def _move(self, direction: int):
        n = len(self._entries)
        if n < 2 or not (0 <= self._sel < n):
            return
        ni = self._sel + direction
        if ni < 0 or ni >= n:
            return
        self._entries[self._sel], self._entries[ni] = \
            self._entries[ni], self._entries[self._sel]
        self._sel = ni
        # 不用调 _update_props：数据没变只是位置变了

    def _clear_all(self):
        if not self._entries:
            return
        if gui.Question("确定要清空所有用户数据条目吗?"):
            self._entries.clear()
            self._sel = -1
            self._update_props()

    # ── 列表刷新 ───────────────────────────────────────────────────

    def _refresh_list(self):
        self.FreezeListView(_lstMain)
        self.SetListViewMode(_lstMain, c4d.LV_REPORT)
        # 清空
        for i in range(self.GetListViewCount(_lstMain)):
            self.RemoveListViewItem(_lstMain, i)
        # 填充
        for i, e in enumerate(self._entries):
            self.SetListViewItem(_lstMain, i, str(i + 1), column=0)
            self.SetListViewItem(_lstMain, i, e.name, column=1)
            self.SetListViewItem(_lstMain, i, UDT.name(e.dtype), column=2)
            self.SetListViewItem(_lstMain, i, e.display_value(), column=3)
        # 恢复选中
        if 0 <= self._sel < len(self._entries):
            self.SetSelectedListViewItem(_lstMain, self._sel)
        self.ThawListView(_lstMain)

    # ── 属性面板 ───────────────────────────────────────────────────

    def _get_entry(self) -> Optional[Entry]:
        if 0 <= self._sel < len(self._entries):
            return self._entries[self._sel]
        return None

    def _update_props(self):
        """属性面板 ← 当前选中条目"""
        e = self._get_entry()
        enabled = e is not None

        self.SetString(_edtName, e.name if e else "")
        if e:
            self.SetInt32(_cmbType, e.dtype)
        self.SetString(_edtGroup, e.group if e else "")
        self.SetString(_edtDesc, e.desc if e else "")
        self.SetString(_edtDDItems, e.dd_items if e else "")

        if e:
            self.SetReal(_edtMin, e.min_v)
            self.SetReal(_edtMax, e.max_v)
            self.SetReal(_edtStep, e.step)
            self.SetReal(_edtDefault, e.default_v)
            self.SetInt32(_cmbUnit, e.unit)
        else:
            self.SetReal(_edtMin, 0.0)
            self.SetReal(_edtMax, 100.0)
            self.SetReal(_edtStep, 1.0)
            self.SetReal(_edtDefault, 0.0)
            self.SetInt32(_cmbUnit, c4d.DESC_UNIT_NONE)

        # 启用/禁用
        for cid in (_edtName, _edtGroup, _edtDesc, _edtDDItems,
                    _edtMin, _edtMax, _edtStep, _edtDefault,
                    _cmbType, _cmbUnit):
            self.Enable(cid, enabled)

        if e:
            hr = UDT.has_range(e.dtype)
            self.Enable(_edtMin, hr)
            self.Enable(_edtMax, hr)
            self.Enable(_edtStep, e.dtype in (UDT.FLOAT, UDT.PERCENT,
                                               UDT.ANGLE, UDT.VECTOR))
            # 下拉选项
            is_dd = e.dtype == UDT.DROPDOWN
            self.Enable(_edtDDItems, is_dd)
            # 非数值类型禁用范围
            if not UDT.is_numeric(e.dtype) and e.dtype != UDT.DROPDOWN:
                self.Enable(_edtMin, False)
                self.Enable(_edtMax, False)
                self.Enable(_edtStep, False)

    def _update_entry_from_ui(self):
        """当前条目 ← 属性面板"""
        e = self._get_entry()
        if not e:
            return
        e.name    = self.GetString(_edtName)
        e.dtype   = self.GetInt32(_cmbType)
        e.group   = self.GetString(_edtGroup)
        e.desc    = self.GetString(_edtDesc)
        e.dd_items = self.GetString(_edtDDItems)
        e.min_v   = self.GetReal(_edtMin)
        e.max_v   = self.GetReal(_edtMax)
        e.step    = self.GetReal(_edtStep)
        e.default_v = self.GetReal(_edtDefault)
        e.unit    = self.GetInt32(_cmbUnit)

    # ── 状态 ───────────────────────────────────────────────────────

    def _update_status(self):
        cnt = len(self._entries)
        sel_info = f" | 选中: #{self._sel + 1}" if 0 <= self._sel < cnt else ""
        self.SetString(_txtInfo, f"条目数: {cnt}{sel_info}")

    # ── 应用到对象 ─────────────────────────────────────────────────

    def _apply_to_objects(self):
        if not self._entries:
            gui.MessageDialog("请先添加用户数据条目。")
            return

        doc = c4d.documents.GetActiveDocument()
        if not doc:
            return

        objs = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)
        if not objs:
            gui.MessageDialog("请在场景中选择一个或多个对象。")
            return

        added = 0
        errors = []
        total = len(objs) * len(self._entries)

        doc.StartUndo()
        # 先标记所有对象，undo 时一步恢复
        for obj in objs:
            if obj:
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)

        for obj in objs:
            if not obj:
                continue
            for entry in self._entries:
                try:
                    bc = entry.build_bc()
                    did = obj.AddUserData(bc)
                    if did is not None:
                        added += 1
                    else:
                        msg = f"{obj.GetName()}: {entry.name} → AddUserData 返回空"
                        errors.append(msg)
                except Exception as ex:
                    msg = f"{obj.GetName()}: {entry.name} → {ex}"
                    errors.append(msg)

        doc.EndUndo()
        c4d.EventAdd()

        summary = (
            f"对象数: {len(objs)}  条目数: {len(self._entries)}\n"
            f"成功: {added}/{total}"
        )
        if errors:
            # 最多显示前 5 条错误
            detail = "\n".join(errors[:5])
            if len(errors) > 5:
                detail += f"\n...及其他 {len(errors)-5} 条错误"
            gui.MessageDialog(
                f"{summary}\n"
                f"失败: {len(errors)} 个\n\n"
                f"错误详情:\n{detail}"
            )
        else:
            gui.MessageDialog(f"✅ 全部成功\n{summary}")

    # ── 替换/追加公共逻辑 ──────────────────────────────────────────

    def _replace_or_append(self, new_entries: list[Entry],
                           source_label: str) -> None:
        if not new_entries:
            return
        if self._entries:
            replace = gui.Question(
                f"{source_label} ({len(new_entries)} 个条目)\n"
                f"当前共 {len(self._entries)} 个条目。\n\n"
                "「是」= 替换全部  「否」= 追加到末尾"
            )
            if replace:
                self._entries = new_entries
            else:
                self._entries.extend(new_entries)
        else:
            self._entries = new_entries
        self._sel = 0 if self._entries else -1
        self._refresh_list()
        self._update_props()
        self._update_status()

    # ── 模板 ───────────────────────────────────────────────────────

    def _save_template(self):
        if not self._entries:
            gui.MessageDialog("没有条目可保存。")
            return
        fn = storage.LoadDialog(title="保存用户数据模板",
                                flags=c4d.FILESELECT_SAVE,
                                def_file="userdata_template.json",
                                typeflags=c4d.FILESELECTTYPE_ANYTHING)
        if not fn:
            return
        if not fn.endswith(".json"):
            fn += ".json"
        data = {
            "version": __version__,
            "count": len(self._entries),
            "entries": [e.to_dict() for e in self._entries],
        }
        try:
            with open(fn, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            gui.MessageDialog(f"已保存:\n{fn}")
        except Exception as ex:
            gui.MessageDialog(f"保存失败: {ex}")

    def _load_template(self):
        fn = storage.LoadDialog(title="加载用户数据模板",
                                flags=c4d.FILESELECT_LOAD,
                                typeflags=c4d.FILESELECTTYPE_ANYTHING)
        if not fn:
            return
        try:
            with open(fn, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as ex:
            gui.MessageDialog(f"加载失败: {ex}\n文件格式不是有效的 JSON。")
            return

        # ── 校验数据结构 ──
        raw = data.get("entries")
        if not isinstance(raw, list):
            gui.MessageDialog("模板格式错误：缺少 entries 列表。")
            return
        if not raw:
            gui.MessageDialog("模板中没有条目。")
            return
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                gui.MessageDialog(f"模板格式错误：第 {i+1} 项不是合法条目。")
                return
            if "name" not in item or "type" not in item:
                gui.MessageDialog(
                    f"模板格式错误：第 {i+1} 项缺少 name 或 type 字段。")
                return
            if not isinstance(item.get("type"), int) or \
               item["type"] not in UDT._ALL_TYPES:
                gui.MessageDialog(
                    f"模板格式错误：第 {i+1} 项 type 值无效 ({item.get('type')})。")
                return

        entries = [Entry.from_dict(e) for e in raw]
        self._replace_or_append(entries, f"模板文件")
        gui.MessageDialog(f"已加载 {len(entries)} 个条目。")

    # ── 预设 ───────────────────────────────────────────────────────

    def _show_presets(self):
        menu = gui.GePopupMenu()
        for i, p in enumerate(PRESETS):
            menu.AddString(i, p["name"])
        result = menu.Open(self, x=0, y=0)
        if result < 0 or result >= len(PRESETS):
            return
        preset = PRESETS[result]
        entries = [e.copy() for e in preset["entries"]]
        self._replace_or_append(entries, f"预设「{preset['name']}」")


# ─────────────────────────────────────────────────────────────────
# 插件注册
# ─────────────────────────────────────────────────────────────────

class UserDataCommandData(c4d.plugins.CommandData):
    """菜单命令"""

    def __init__(self):
        self._dlg: Optional[UserDataDialog] = None

    def Execute(self, doc):
        if self._dlg is None:
            self._dlg = UserDataDialog()
        return self._dlg.Open(
            dlgtype=c4d.DLG_TYPE_ASYNC,
            pluginid=PLUGIN_ID,
            defaultw=640,
            defaulth=520,
            xpos=-1, ypos=-1,
            subid=0)

    def RestoreLayout(self, sec_ref):
        if self._dlg is None:
            self._dlg = UserDataDialog()
        return self._dlg.Restore(pluginid=PLUGIN_ID, subid=0, sec_ref=sec_ref)

    def GetID(self):
        return PLUGIN_ID


def main():
    """C4D 插件入口"""
    icon = None  # 可用 c4d.bitmaps.BaseBitmap 加载图标
    return c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str=PLUGIN_NAME,
        info=0,
        icon=icon,
        help=PLUGIN_HELP,
        dat=UserDataCommandData(),
    )


if __name__ == "__main__":
    main()
