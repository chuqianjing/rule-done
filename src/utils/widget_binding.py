#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
字段控件工具

根据字段定义（来自 fields_definition.json）统一创建和读写控件：
- create_widget: 字段定义 -> 对应的 Qt 控件
- set_widget_value: 往控件里写值
- get_widget_value: 从控件里读值

主要服务于：
- AdminHomePage
- MemberHomePage
- TemplatePage
"""


from html import escape
import re

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QTextEdit,
    QSpinBox,
    QWidget,
    QSizePolicy,
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QWheelEvent
from typing import Any, Dict, Optional, Union

WidgetType = Union[QLineEdit, QComboBox, QDateEdit, QTextEdit, QSpinBox, "DateWidget"]


# ========= 富文本处理 ==========

_URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)

def _split_trailing_url_punctuation(url: str) -> tuple[str, str]:
    trailing = ""
    while url and url[-1] in ")],.;:!?】〕》〉」』、。！？":
        trailing = url[-1] + trailing
        url = url[:-1]
    return url, trailing


def build_rich_text(text: Any) -> str:
    """把普通文本转换成可安全渲染的富文本，并将 URL 变成可点击链接。"""
    raw_text = "" if text is None else str(text)
    if not raw_text:
        return ""

    parts: list[str] = []
    last_index = 0

    for match in _URL_PATTERN.finditer(raw_text):
        start, end = match.span()
        parts.append(escape(raw_text[last_index:start]).replace("\n", "<br>"))

        url, trailing = _split_trailing_url_punctuation(match.group(0))
        if url:
            escaped_url = escape(url, quote=True)
            parts.append(
                f'<a href="{escaped_url}" style="color: #1a73e8; text-decoration: underline;">{escape(url)}</a>'
            )
            parts.append(escape(trailing))
        else:
            parts.append(escape(match.group(0)).replace("\n", "<br>"))

        last_index = end

    parts.append(escape(raw_text[last_index:]).replace("\n", "<br>"))
    return "".join(parts)

def configure_rich_label(label: QLabel, text: Any) -> QLabel:
    """让只读展示标签支持链接点击与文本选择。"""
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    label.setOpenExternalLinks(True)
    label.setWordWrap(True)
    label.setText(build_rich_text(text))
    return label

def configure_selectable_label(label: QLabel) -> QLabel:
    """让只读展示标签支持鼠标选择和复制。"""
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setCursor(Qt.CursorShape.IBeamCursor)
    return label


# ========== 自定义控件 ==========

# 选择控件
class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()

# 日期编辑控件（作为 DateWidget 的一个子控件）
class NoWheelDateEdit(QDateEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDate(QDate.currentDate())

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()

# 数字控件
class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class DateWidget(QWidget):
    """三态日期控件，支持三种状态：具体日期、"    年  月  日"（未填）、"输入特殊内容"（自由输入）。

    内部组合：
    - NoWheelComboBox：模式选择（"    年  月  日" / "选择具体日期..." / "输入特殊内容"）
    - QLineEdit：特殊内容输入（仅在"输入特殊内容"模式下可见，内容由用户自行填写）
    - NoWheelDateEdit：实际日期选择（仅在选择日期模式下可见）
    """

    MODE_EMPTY = "    年  月  日"
    MODE_DATE = "选择具体日期..."
    MODE_SPECIAL = "输入特殊内容"

    def __init__(self, field_def: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._field_def = field_def

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 模式选择下拉框（宽度按最长选项自适应后固定，不再随模式变化，也不占用多余空间）
        self._combo = NoWheelComboBox()
        self._combo.addItems([self.MODE_EMPTY, self.MODE_DATE, self.MODE_SPECIAL])
        self._combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        # Fixed（而非默认 Expanding）：宽度按最长选项一次自适应后固定不变，
        # 既不随当前模式变化，也不会在输入控件隐藏时反过来占满整行
        self._combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 特殊内容输入框（仅在特殊内容模式下可见，无法提前穷举的特殊字符都在这里自由填写）
        self._special_edit = QLineEdit()
        self._special_edit.setPlaceholderText("请输入特殊内容，如：无、不详")

        # 日期编辑控件（仅在选择日期模式下可见）
        self._date_edit = NoWheelDateEdit()
        self._date_edit.setCalendarPopup(True)
        if self._field_def:
            qt_format = self._resolve_date_qt_format(self._field_def)
            self._date_edit.setDisplayFormat(qt_format)

        # 两个「值输入」控件统一占满下拉框之外的剩余宽度，避免切换模式时宽度跳变
        for value_widget in (self._special_edit, self._date_edit):
            value_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout.addWidget(self._combo, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._special_edit, 1)
        layout.addWidget(self._date_edit, 1)

        # 初始状态：显示未填模式
        self._combo.setCurrentText(self.MODE_EMPTY)
        self._special_edit.setVisible(False)
        self._date_edit.setVisible(False)

        # 连接信号
        self._combo.currentTextChanged.connect(self._on_mode_changed)
        self._date_edit.dateChanged.connect(self._on_date_changed)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    # ===== 外部方法 =====

    def set_value(self, value: Any) -> None:
        """设置控件值。接受 "    年  月  日"、任意特殊内容文本或格式化的日期字符串。

        能解析成日期的文本进入日期模式；其余非空文本一律作为「特殊内容」原样保留，
        避免历史值（如"无"）或用户自定义的特殊字符被静默丢弃。
        """
        text = "" if value is None else str(value)
        if not text or text.strip() == "" or text == self.MODE_EMPTY:
            self._combo.setCurrentText(self.MODE_EMPTY)
            self._special_edit.setVisible(False)
            self._date_edit.setVisible(False)
        elif text != self.MODE_SPECIAL and self._parse_date_string(text):
            self._combo.setCurrentText(self.MODE_DATE)
            self._special_edit.setVisible(False)
            self._date_edit.setVisible(True)
        else:
            self._special_edit.setText(text)
            self._combo.setCurrentText(self.MODE_SPECIAL)
            self._special_edit.setVisible(True)
            self._date_edit.setVisible(False)

    def get_value(self) -> str:
        """获取控件值，返回 "    年  月  日" / 特殊内容文本 / 格式化的日期字符串。

        「特殊内容」模式下输入框内为空时返回空串（语义上等同未填）。
        """
        mode = self._combo.currentText()
        if mode == self.MODE_EMPTY:
            return self.MODE_EMPTY
        if mode == self.MODE_SPECIAL:
            return self._special_edit.text().strip()
        # MODE_DATE
        qt_format = self._date_edit.displayFormat()
        return self._date_edit.date().toString(qt_format)

    def setReadOnly(self, read_only: bool) -> None:
        """设置只读状态。"""
        self._combo.setEnabled(not read_only)
        self._special_edit.setEnabled(not read_only)
        self._date_edit.setEnabled(not read_only)

    # ===== 内部方法 =====

    def _resolve_date_qt_format(self, field_def: Dict[str, Any]) -> str:
        """
        根据字段定义和管理员配置解析日期的 Qt 显示格式
        """
        fmt = field_def.get("format", "YYYY年MM月DD日")
        if fmt == "YYYY年M月D日":
            return "yyyy年M月d日"
        if fmt == "YYYY年M月":
            return "yyyy年M月"
        if fmt == "YYYY年MM月DD日":
            return "yyyy年MM月dd日"
        if fmt == "YYYY年MM月":
            return "yyyy年MM月"
        return "yyyy-MM-dd"

    def _parse_date_string(self, text: str) -> bool:
        """尝试用多种格式解析日期字符串，成功则设置到 _date_edit 并返回 True。"""
        qt_format = None
        if self._field_def:
            qt_format = self._resolve_date_qt_format(self._field_def)

        if qt_format:
            dt = QDate.fromString(text, qt_format)
            if dt.isValid():
                self._date_edit.setDate(dt)
                return True
        else:
            # 此时再尝试多种常见格式，不必严格依赖字段定义
            for fmt in ["yyyy年M月d日", "yyyy年M月", "yyyy年MM月dd日", "yyyy年MM月", "yyyy-MM-dd"]:
                dt = QDate.fromString(text, fmt)
                if dt.isValid():
                    self._date_edit.setDate(dt)
                    return True
        return False

    def _on_mode_changed(self, text: str) -> None:
        """模式切换时显示对应的子控件。"""
        self._special_edit.setVisible(text == self.MODE_SPECIAL)
        self._date_edit.setVisible(text == self.MODE_DATE)

    def _on_date_changed(self, date: QDate) -> None:
        """用户通过日历选择了日期，确保模式为"选择日期..."。"""
        if self._combo.currentText() != self.MODE_DATE:
            self._combo.setCurrentText(self.MODE_DATE)


# ========== widget 的三个核心方法：创建、写入值、读取值 ==========

def create_widget(field_def: Dict[str, Any]) -> WidgetType:
    """
    根据字段定义创建对应的控件
    支持类型：
    - text: QLineEdit
    - select: QComboBox
    - date: QDateEdit
    - textarea: QTextEdit
    """
    field_type = field_def.get("type", "text")
    placeholder = field_def.get("display", {}).get("placeholder", "")
    height = field_def.get("display", {}).get("rows", 3) * 25  # 粗略估算行高，调整 QTextEdit 的高度

    widget: WidgetType = None

    if field_type == "select":
        widget = NoWheelComboBox()
        for option in field_def.get("options", []) or []:
            widget.addItem(str(option))
        widget.setCurrentIndex(-1)
    elif field_type == "date":
        widget = DateWidget(field_def)
    elif field_type == "textarea":
        widget = QTextEdit()
        widget.setFixedHeight(height)
    elif field_type == "number":
        widget = NoWheelSpinBox()
        number_display = field_def.get("display", {}) or {}
        # min 语义：用户可填的最小值（人数/数量/票数类默认 0）
        number_min = int(number_display.get("min", 0))
        number_max = int(number_display.get("max", 999))
        number_default = number_display.get("default")
        if number_default is not None:
            # 配了默认值：没有「未填」态，空值/非法值都回退到该默认值，初始即显示默认值
            widget.setRange(number_min, number_max)
            widget.setProperty("defaultValue", int(number_default))
            widget.setValue(int(number_default))
        else:
            # 未配默认值：在可填下界下方多留一位作为「未填」哨兵，由 specialValueText 显示提示。
            # 读取时哨兵值转为空串，避免 0/-1 被当作真实数据存储、导出与同步。
            widget.setRange(number_min - 1, number_max)
            widget.setSpecialValueText(
                str(number_display.get("special_value_text", "根据实际情况填写"))
            )
            widget.setValue(widget.minimum())
    else:
        widget = QLineEdit()
    
    if placeholder and hasattr(widget, "setPlaceholderText"):
        widget.setPlaceholderText(str(placeholder))
    
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    return widget


def _spin_fallback_value(widget: QSpinBox) -> int:
    """数值控件的「空值 / 非法值」落点：配了默认值用默认值，否则回到「未填」哨兵（最小值）。"""
    number_default = widget.property("defaultValue")
    return int(number_default) if number_default is not None else widget.minimum()


def set_widget_value(widget: QWidget, value: Any) -> None:
    """
    把值写入控件
    """
    if isinstance(widget, DateWidget):
        widget.set_value(value)
    elif isinstance(widget, QLineEdit):
        widget.setText("" if value is None else str(value))
    elif isinstance(widget, QComboBox):
        text = "" if value is None else str(value)
        index = widget.findText(text)
        # 空值或已移除的选项应清空选择，避免同步清空后仍显示并再次保存旧值。
        widget.setCurrentIndex(index)
    elif isinstance(widget, QTextEdit):
        widget.setPlainText("" if value is None else str(value))
    elif isinstance(widget, QSpinBox):
        text = "" if value is None else str(value).strip()
        if not text:
            widget.setValue(_spin_fallback_value(widget))
            return
        try:
            num = int(float(text))
        except (ValueError, TypeError):
            # 非数字内容（历史遗留文本、平台回读异常值等）：按未填/默认值处理，不抛异常
            widget.setValue(_spin_fallback_value(widget))
            return
        widget.setValue(num)


def get_widget_value(widget: QWidget) -> str:
    """
    从控件中读取值，统一转为字符串（供 JSON 存储）
    """
    if isinstance(widget, DateWidget):
        return widget.get_value()
    if isinstance(widget, QLineEdit):
        return widget.text().strip()
    if isinstance(widget, QComboBox):
        return widget.currentText().strip()
    if isinstance(widget, QTextEdit):
        return widget.toPlainText().strip()
    if isinstance(widget, QSpinBox):
        # 设置了 specialValueText 时，最小值即为「未填」哨兵，读作空串（不落库、不导出、不参与同步）
        if widget.specialValueText() and widget.value() == widget.minimum():
            return "   "
        return str(widget.value())
    return ""
