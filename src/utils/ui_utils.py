#!/usr/bin/env python
# -*- coding: utf-8 -*-
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


from PyQt6.QtWidgets import (
    QLineEdit,
    QComboBox,
    QDateEdit,
    QTextEdit,
    QWidget,
)
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QWheelEvent
from typing import Any, Dict, Optional

WidgetType = QLineEdit | QComboBox | QDateEdit | QTextEdit

def _resolve_date_qt_format(field_def: Dict[str, Any]) -> str:
    """
    根据字段定义和管理员配置解析日期的 Qt 显示格式
    """
    fmt = field_def.get("format", "YYYY年MM月DD日")
    if fmt == "YYYY年MM月DD日":
        return "yyyy年M月d日"
    if fmt == "YYYY年MM月":
        return "yyyy年M月"
    return "yyyy-MM-dd"


# 定义自定义的ComboBox类，禁用滚轮切换
class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event: QWheelEvent) -> None:
        # 重写滚轮事件，直接忽略（不调用父类的wheelEvent）
        # 这样鼠标滚轮在控件上滑动时就不会切换选项了
        event.ignore()

class NoWheelDateEdit(QDateEdit):
    def wheelEvent(self, event: QWheelEvent) -> None:
        # 忽略滚轮事件，不传递给父类处理
        event.ignore()
        

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
    display = field_def.get("display", {}) or {}

    if field_type == "select":
        widget = NoWheelComboBox()
        for option in field_def.get("options", []) or []:
            widget.addItem(str(option))
        return widget

    if field_type == "date":
        widget = NoWheelDateEdit()
        widget.setCalendarPopup(True)
        qt_format = _resolve_date_qt_format(field_def)
        widget.setDisplayFormat(qt_format)
        widget.setDate(QDate.currentDate())
        return widget

    if field_type == "textarea":
        widget = QTextEdit()
        placeholder = display.get("placeholder")
        if placeholder:
            widget.setPlaceholderText(str(placeholder))
        return widget

    # 默认 text
    widget = QLineEdit()
    placeholder = display.get("placeholder")
    if placeholder:
        widget.setPlaceholderText(str(placeholder))
    return widget


def set_widget_value(widget: QWidget, value: Any, field_def: Optional[Dict[str, Any]] = None) -> None:
    """
    把值写入控件
    """
    if isinstance(widget, QLineEdit):
        widget.setText("" if value is None else str(value))
    elif isinstance(widget, QComboBox):
        text = "" if value is None else str(value)
        index = widget.findText(text)
        if index >= 0:
            widget.setCurrentIndex(index)
    elif isinstance(widget, QDateEdit):
        text = "" if value is None else str(value)
        if not text:
            return
        # 推断日期格式并解析
        fmt = None
        if field_def:
            fmt = field_def.get("format")
        # 根据格式选择 Qt 解析格式
        if fmt == "YYYY年MM月DD日":
            qt_format = "yyyy年M月d日"
        elif fmt == "YYYY年MM月":
            qt_format = "yyyy年M月"
        else:
            # 尝试多种格式
            for fmt in ["yyyy年M月d日", "yyyy年M月", "yyyy-MM-dd"]:
                dt = QDate.fromString(text, fmt)
                if dt.isValid():
                    widget.setDate(dt)
                    return
            return
        dt = QDate.fromString(text, qt_format)
        if dt.isValid():
            widget.setDate(dt)
    elif isinstance(widget, QTextEdit):
        widget.setPlainText("" if value is None else str(value))


def get_widget_value(widget: QWidget) -> str:
    """
    从控件中读取值，统一转为字符串（供 JSON 存储）
    """
    if isinstance(widget, QLineEdit):
        return widget.text().strip()
    if isinstance(widget, QComboBox):
        return widget.currentText().strip()
    if isinstance(widget, QTextEdit):
        return widget.toPlainText().strip()
    if isinstance(widget, QDateEdit):
        qt_format = widget.displayFormat()   # 按当前显示格式输出
        return widget.date().toString(qt_format)
    return ""

