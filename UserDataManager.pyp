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
from c4d import gui, storage, bitmaps
import json
import os
from typing import Optional

__version__ = "1.3.0"


# ─────────────────────────────────────────────────────────────────
# C4D 跨版本兼容
# ─────────────────────────────────────────────────────────────────
# 部分常量在 C4D 2026 Python SDK 中被移除，用 hasattr 安全回退

def _c(name, fallback):
    """安全获取 c4d 常量，不存在时用默认值"""
    return getattr(c4d, name, fallback)

# DESC_UNIT（整数值在各版本中稳定）
_DESC_UNIT_NONE       = _c('DESC_UNIT_NONE', 0)
_DESC_UNIT_METER      = _c('DESC_UNIT_METER', 1)
_DESC_UNIT_CENTIMETER = _c('DESC_UNIT_CENTIMETER', 2)
_DESC_UNIT_MILLIMETER = _c('DESC_UNIT_MILLIMETER', 3)
_DESC_UNIT_KILOMETER  = _c('DESC_UNIT_KILOMETER', 4)
_DESC_UNIT_DEGREE     = _c('DESC_UNIT_DEGREE', 5)
_DESC_UNIT_PERCENT    = _c('DESC_UNIT_PERCENT', 6)
_DESC_UNIT_SECOND     = _c('DESC_UNIT_SECOND', 7)
_DESC_UNIT_FRAME      = _c('DESC_UNIT_FRAME', 8)

# DESC_CYCLE（各版本稳定）
_DESC_CYCLE       = _c('DESC_CYCLE', 2000)
_DESC_CYCLE_COUNT = _c('DESC_CYCLE_COUNT', 20000)


# ─────────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────────

# ★ 重要：到 plugincafe.maxon.net 注册免费插件 ID 后替换此处
PLUGIN_ID   = 1060001
PLUGIN_NAME = "UserData Manager"
PLUGIN_HELP = "快速创建和管理用户数据，供 Xpresso 使用"

# 插件所在目录（用于加载图标）
PLUGIN_DIR = os.path.dirname(__file__)

# ── 控件 ID ───────────────────────────────────────────────────────
_gRoot   = 1000
_gTop    = 1001
_gBody   = 1002
_gList   = 1003
_gScroll = 1004   # scroll group for entry list
_gProp   = 1005
_gBot    = 1006
_gPreset = 1007

_btnAdd    = 2101
_btnDel    = 2102
_btnDup    = 2103
_btnUp     = 2104
_btnDown   = 2105
_btnApply  = 2106
_btnSave   = 2107
_btnLoad   = 2108
_btnClear  = 2110
_btnClearObjData = 2111  # 清空对象的用户数据
# 预设按钮基址（每个预设一个按钮）
_btnPresetBase = 2120

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
# 动态列表内容组（嵌套在 ScrollGroup 内部，用于 LayoutFlushGroup 刷新）
_gListContent = 2501

# 动态生成的列表行控件 ID 基址
# 每个条目行占用 4 个连续 ID
_ROW_BASE   = 5000
_ROW_STRIDE = 4
# 行内各控件的偏移
_R_IDX    = 0   # 序号（StaticText）
_R_SEL    = 1   # 选择按钮（Button）
_R_TYPE   = 2   # 类型（StaticText）
_R_VALUE  = 3   # 默认值（StaticText）


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
        ANGLE:   _DESC_UNIT_DEGREE,
        PERCENT: _DESC_UNIT_PERCENT,
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
        return cls._UNIT_MAP.get(t, _DESC_UNIT_NONE)

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
        "default_v", "unit", "group", "desc", "dd_items",
    )

    def __init__(self, name="Param", dtype=UDT.FLOAT,
                 min_v=0.0, max_v=100.0, step=1.0,
                 default_v=50.0, unit=_DESC_UNIT_NONE,
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

        if self.dtype in (UDT.FLOAT, UDT.PERCENT, UDT.ANGLE):
            # C4D 内部百分比以 0-1 存储，UI 层仍按 0-100 显示
            scale = 100.0 if self.dtype == UDT.PERCENT else 1.0
            bc[c4d.DESC_MIN]     = float(self.min_v) / scale
            bc[c4d.DESC_MAX]     = float(self.max_v) / scale
            bc[c4d.DESC_STEP]    = float(self.step) / scale
            bc[c4d.DESC_DEFAULT] = float(self.default_v) / scale

        elif self.dtype == UDT.INTEGER:
            bc[c4d.DESC_MIN]     = int(self.min_v)
            bc[c4d.DESC_MAX]     = int(self.max_v)
            bc[c4d.DESC_STEP]    = int(self.step)
            bc[c4d.DESC_DEFAULT] = int(self.default_v)

        elif self.dtype == UDT.VECTOR:
            bc[c4d.DESC_MIN]     = c4d.Vector(self.min_v, self.min_v, self.min_v)
            bc[c4d.DESC_MAX]     = c4d.Vector(self.max_v, self.max_v, self.max_v)
            bc[c4d.DESC_STEP]    = c4d.Vector(self.step, self.step, self.step)
            bc[c4d.DESC_DEFAULT] = c4d.Vector(self.default_v, self.default_v, self.default_v)

        elif self.dtype == UDT.BOOL:
            bc[c4d.DESC_DEFAULT] = int(bool(self.default_v))

        elif self.dtype == UDT.COLOR:
            bc[c4d.DESC_DEFAULT] = self._parse_color(self.default_v)

        elif self.dtype in (UDT.STRING, UDT.FILENAME):
            bc[c4d.DESC_DEFAULT] = str(self.default_v or "")

        elif self.dtype == UDT.DROPDOWN:
            bc[c4d.DESC_DEFAULT] = int(float(self.default_v or 0))
            self._build_dropdown(bc)

        # 单位：仅当存在有效单位时才写入，避免 DESC_UNIT=0 导致 FLOAT 等类型异常
        u = UDT.c4d_unit(self.dtype)
        if u != _DESC_UNIT_NONE:
            bc[c4d.DESC_UNIT] = u
        elif self.unit != _DESC_UNIT_NONE:
            bc[c4d.DESC_UNIT] = self.unit

        # 分组短名
        if self.group.strip():
            bc[c4d.DESC_SHORT_NAME] = self.group.strip()

        return bc

    def get_c4d_value(self):
        """返回可直接写入对象参数值的 Python 对象（处理百分比 0-100 → 0-1 等转换）"""
        if self.dtype == UDT.BOOL:
            return int(bool(self.default_v))
        elif self.dtype == UDT.COLOR:
            return self._parse_color(self.default_v)
        elif self.dtype == UDT.VECTOR:
            return c4d.Vector(self.default_v, self.default_v, self.default_v)
        elif self.dtype == UDT.INTEGER or self.dtype == UDT.DROPDOWN:
            return int(float(self.default_v or 0))
        elif self.dtype == UDT.PERCENT:
            return float(self.default_v) / 100.0
        elif self.dtype in (UDT.STRING, UDT.FILENAME):
            return str(self.default_v or "")
        else:  # FLOAT, ANGLE
            return float(self.default_v)

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
            bc.SetString(_DESC_CYCLE + i, item)
        bc[_DESC_CYCLE_COUNT] = len(items)

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
            unit=d.get("unit", _DESC_UNIT_NONE),
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
    {"name": "浮点数",   "btn": "浮点数",   "entries": [Entry("浮点数",   UDT.FLOAT,   0, 100,   1, 50)]},
    {"name": "速度",     "btn": "速度",     "entries": [Entry("速度",     UDT.FLOAT,   0, 100,   1, 50)]},
    {"name": "强度",     "btn": "强度",     "entries": [Entry("强度",     UDT.PERCENT, 0, 200,   1, 100)]},
    {"name": "透明度",   "btn": "透明度",   "entries": [Entry("透明度",   UDT.PERCENT, 0, 100,   1, 100)]},
    {"name": "缩放",     "btn": "缩放",     "entries": [Entry("缩放",     UDT.PERCENT, 0, 500,   1, 100)]},
    {"name": "颜色",     "btn": "颜色",     "entries": [Entry("颜色",     UDT.COLOR,   0, 1,   0.01, 1)]},
    {"name": "位置偏移", "btn": "位置偏移", "entries": [
        Entry("偏移.X", UDT.FLOAT, -1000, 1000, 1, 0),
        Entry("偏移.Y", UDT.FLOAT, -1000, 1000, 1, 0),
        Entry("偏移.Z", UDT.FLOAT, -1000, 1000, 1, 0),
    ]},
    {"name": "旋转",     "btn": "旋转",     "entries": [
        Entry("旋转.X", UDT.ANGLE, 0, 360, 1, 0),
        Entry("旋转.Y", UDT.ANGLE, 0, 360, 1, 0),
        Entry("旋转.Z", UDT.ANGLE, 0, 360, 1, 0),
    ]},
    {"name": "随机",     "btn": "随机",     "entries": [
        Entry("种子",   UDT.INTEGER, 0, 99999, 1, 0),
        Entry("随机化", UDT.BOOL,    0, 1, 1, True),
    ]},
    {"name": "计数",     "btn": "计数",     "entries": [Entry("计数", UDT.INTEGER, 1, 1000, 1, 10)]},
    {"name": "开关",     "btn": "开关",     "entries": [Entry("启用", UDT.BOOL, 0, 1, 1, True)]},
    {"name": "衰减",     "btn": "衰减",     "entries": [
        Entry("半径",  UDT.FLOAT,   0, 1000, 1, 100),
        Entry("衰减",  UDT.PERCENT, 0, 100,  1, 50),
    ]},
    {"name": "权重",     "btn": "权重",     "entries": [
        Entry("权重A", UDT.FLOAT, 0, 1, 0.01, 0.5),
        Entry("权重B", UDT.FLOAT, 0, 1, 0.01, 0.5),
    ]},
    {"name": "材质",     "btn": "材质",     "entries": [
        Entry("金属度",  UDT.PERCENT, 0, 100, 1, 0),
        Entry("粗糙度",  UDT.PERCENT, 0, 100, 1, 50),
        Entry("自发光",  UDT.COLOR,   0, 1, 0.01, 0),
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

    def CreateLayout(self, parent_dlg=None):
        # parent_dlg: C4D 2023 传入此参数，2026 不再传入；用默认值兼容两者
        self.SetTitle(f"{PLUGIN_NAME}  v{__version__}")
        self.GroupBegin(_gRoot, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                        cols=1, rows=4, title="")
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
        self.AddButton(_btnSave,   flags=c4d.BFH_LEFT, initw=50, inith=24, name="保存")
        self.AddButton(_btnLoad,   flags=c4d.BFH_LEFT, initw=50, inith=24, name="加载")
        self.AddButton(_btnClear,  flags=c4d.BFH_LEFT, initw=50, inith=24, name="清空")
        self.AddButton(_btnClearObjData, flags=c4d.BFH_LEFT, initw=90, inith=24, name="清空对象")
        self.AddButton(_btnApply,  flags=c4d.BFH_RIGHT, initw=120, inith=24, name="▸ 应用到对象")
        self.GroupEnd()

        # ─── 预设按钮行（水平滚动） ───
        self.GroupBegin(_gPreset, flags=c4d.BFH_SCALEFIT, cols=1, rows=1, title="")
        self.GroupBorderSpace(0, 0, 0, 4)
        self.ScrollGroupBegin(0, flags=c4d.BFH_SCALEFIT,
                              scrollflags=c4d.SCROLLGROUP_HORIZ)
        self.GroupBegin(0, flags=c4d.BFH_SCALEFIT,
                        cols=len(PRESETS), rows=1, title="")
        for i, p in enumerate(PRESETS):
            self.AddButton(_btnPresetBase + i, flags=c4d.BFH_LEFT,
                           initw=85, inith=24, name=p.get("btn", p["name"]))
        self.GroupEnd()
        self.GroupEnd()
        self.GroupEnd()

        # ─── 主体: 列表 + 属性 ───
        self.GroupBegin(_gBody, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                        cols=2, rows=1, title="")
        self.GroupBorderSpace(0, 0, 0, 4)

        # 左侧: 列表标题行 + 可滚动条目区域
        self.GroupBegin(_gList, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                        cols=1, rows=2, title="")
        self.GroupBorderNoTitle(c4d.BORDER_NONE)
        self.GroupBorderSpace(0, 0, 0, 2)

        # 列表表头
        self.GroupBegin(0, flags=c4d.BFH_SCALEFIT, cols=4, rows=1, title="")
        self.AddStaticText(0, c4d.BFH_LEFT,          30, 0, "#",     c4d.BORDER_THIN_IN)
        self.AddStaticText(0, c4d.BFH_SCALEFIT,     130, 0, "名称",  c4d.BORDER_THIN_IN)
        self.AddStaticText(0, c4d.BFH_SCALEFIT,     110, 0, "类型",  c4d.BORDER_THIN_IN)
        self.AddStaticText(0, c4d.BFH_SCALEFIT,     100, 0, "默认值", c4d.BORDER_THIN_IN)
        self.GroupEnd()

        # 可滚动的条目列表（由 _refresh_list 动态填充）
        self.ScrollGroupBegin(_gScroll, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                              scrollflags=c4d.SCROLLGROUP_VERT)
        self.GroupBegin(_gListContent, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, rows=0, title="")
        self.GroupEnd()  # _gListContent
        self.GroupEnd()  # ScrollGroupBegin
        self.GroupEnd()  # _gList

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
        self.AddComboBox(_cmbType, c4d.BFH_SCALEFIT, 1)
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
        self.AddComboBox(_cmbUnit, c4d.BFH_SCALEFIT, 1)
        _units = [
            (_DESC_UNIT_NONE,       "无"),
            (_DESC_UNIT_METER,      "米 (m)"),
            (_DESC_UNIT_CENTIMETER, "厘米 (cm)"),
            (_DESC_UNIT_MILLIMETER, "毫米 (mm)"),
            (_DESC_UNIT_KILOMETER,  "千米 (km)"),
            (_DESC_UNIT_DEGREE,     "度 (°)"),
            (_DESC_UNIT_PERCENT,    "百分比 (%)"),
            (_DESC_UNIT_SECOND,     "秒 (s)"),
            (_DESC_UNIT_FRAME,      "帧 (f)"),
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

        # ── 列表行按钮点击（选择条目） ──
        if _ROW_BASE <= mid < _ROW_BASE + 9999:
            idx = (mid - _ROW_BASE) // _ROW_STRIDE
            if 0 <= idx < len(self._entries):
                self._sel = idx
                self._update_props()
                self._update_status()
                self._refresh_list()
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
        elif mid == _btnClearObjData:
            self._clear_object_data()
        elif mid == _btnApply:
            self._apply_to_objects()
        elif mid == _btnSave:
            self._save_template()
        elif mid == _btnLoad:
            self._load_template()
        elif _btnPresetBase <= mid < _btnPresetBase + len(PRESETS):
            # 预设按钮点击——始终追加到末尾
            idx = mid - _btnPresetBase
            if 0 <= idx < len(PRESETS):
                preset = PRESETS[idx]
                for e in preset["entries"]:
                    self._entries.append(e.copy())
                self._sel = len(self._entries) - 1
                self._update_props()

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
        if not gui.QuestionDialog(f"确定删除「{name}」?"):
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
        if gui.QuestionDialog("确定要清空所有用户数据条目吗?"):
            self._entries.clear()
            self._sel = -1
            self._update_props()

    def _clear_object_data(self):
        """清空选中对象的所有用户数据"""
        doc = c4d.documents.GetActiveDocument()
        if not doc:
            return

        objs = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)
        if not objs:
            gui.MessageDialog("请在场景中选择一个或多个对象。")
            return

        if not gui.QuestionDialog(f"确定要清空 {len(objs)} 个选中对象的所有用户数据吗？"):
            return

        removed = 0
        doc.StartUndo()
        for obj in objs:
            if not obj:
                continue
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            # GetUserDataContainer 返回的容器在 C4D 2026 中迭代产生 (key, value) 元组
            udc = obj.GetUserDataContainer()
            if udc:
                dids = []
                for item in udc:
                    if isinstance(item, tuple):
                        dids.append(item[0])
                    else:
                        dids.append(item)
                for did in reversed(dids):
                    if obj.RemoveUserData(did):
                        removed += 1
        doc.EndUndo()
        c4d.EventAdd()

        gui.MessageDialog(f"已清空 {len(objs)} 个对象上的 {removed} 条用户数据。")

    # ── 列表刷新 ───────────────────────────────────────────────────
    # C4D 2026 移除了 AddListView / FreezeListView / ThawListView 等，
    # 使用 ScrollGroup + 按钮行模拟列表

    def _refresh_list(self):
        # 清除旧的列表行控件
        self.LayoutFlushGroup(_gListContent)

        # 每行用一个独立 Group 包裹，确保高度一致、从顶部排列
        for i, e in enumerate(self._entries):
            base = _ROW_BASE + i * _ROW_STRIDE
            is_sel = (i == self._sel)

            # 每行独立 Group：cols=4, rows=1 保证 4 个控件在同一行
            self.GroupBegin(0, flags=c4d.BFH_SCALEFIT, cols=4, rows=1, title="")
            self.GroupBorderSpace(0, 0, 0, 0)

            # 序号
            self.AddStaticText(base + _R_IDX, flags=c4d.BFH_LEFT,
                               initw=30, inith=18, name=str(i + 1))
            # 名称按钮（点击选择该行）
            name_text = f"▶ {e.name}" if is_sel else f"  {e.name}"
            self.AddButton(base + _R_SEL, flags=c4d.BFH_SCALEFIT,
                           initw=130, inith=18, name=name_text)
            # 类型
            self.AddStaticText(base + _R_TYPE, flags=c4d.BFH_SCALEFIT,
                               initw=110, inith=18, name=UDT.name(e.dtype))
            # 默认值
            self.AddStaticText(base + _R_VALUE, flags=c4d.BFH_SCALEFIT,
                               initw=100, inith=18, name=e.display_value())

            self.GroupEnd()

        self.LayoutChanged(_gScroll)

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
            self.SetInt32(_cmbUnit, _DESC_UNIT_NONE)

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
                        # AddUserData 不总能从 DESC_DEFAULT 正确初始化值，
                        # 显式写入一次以确保默认值生效
                        obj[did] = entry.get_c4d_value()
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
            replace = gui.QuestionDialog(
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
        # C4D 2026: typeflags 改为 type 参数
        fn = storage.LoadDialog(
            title="保存用户数据模板",
            flags=c4d.FILESELECT_SAVE,
            type=c4d.FILESELECTTYPE_ANYTHING,
            def_file="userdata_template.json")
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
        # C4D 2026: typeflags 改为 type 参数
        fn = storage.LoadDialog(
            title="加载用户数据模板",
            flags=c4d.FILESELECT_LOAD,
            type=c4d.FILESELECTTYPE_ANYTHING)
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
    # 使用第二排按钮（水平滚动）替代原来的 AddPopupButton 下拉菜单


# ─────────────────────────────────────────────────────────────────
# 插件注册
# ─────────────────────────────────────────────────────────────────

class UserDataCommandData(c4d.plugins.CommandData):
    """菜单命令"""

    def __init__(self):
        self._dlg: Optional[UserDataDialog] = None

    def Execute(self, doc):
        # 关闭旧的（若已被用户点 X 关闭则忽略错误）
        if self._dlg is not None:
            try:
                self._dlg.Close()
            except Exception:
                pass
            self._dlg = None
        # 创建新的
        self._dlg = UserDataDialog()
        return self._dlg.Open(
            dlgtype=c4d.DLG_TYPE_ASYNC,
            pluginid=PLUGIN_ID,
            defaultw=1200,
            defaulth=600,
            xpos=-1, ypos=-1,
            subid=0)

    def RestoreLayout(self, sec_ref):
        # 异步对话框：RestoreLayout 直接返回 True 避免二次打开崩溃
        return True

    def GetID(self):
        return PLUGIN_ID


def _load_icon():
    """加载插件图标，失败时返回 None"""
    # 按优先级尝试不同尺寸
    for name in ("icon.png", "icon_32.png", "icon_64.png"):
        path = os.path.join(PLUGIN_DIR, name)
        if os.path.isfile(path):
            bmp = bitmaps.BaseBitmap()
            if bmp.InitWith(path)[0] == c4d.IMAGERESULT_OK:
                return bmp
    return None


def main():
    """C4D 插件入口"""
    icon = _load_icon()
    if icon:
        print(f"[UserDataManager] 图标加载成功")
    else:
        print(f"[UserDataManager] 未找到图标文件，使用默认图标")
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
