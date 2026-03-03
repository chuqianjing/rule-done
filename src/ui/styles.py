#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全局样式定义
统一管理应用程序的视觉风格
"""

# 主样式表
MAIN_STYLESHEET = """
/* ========== 全局字体 ========== */
QWidget {
    font-family: "Microsoft YaHei", "SimHei", sans-serif;
    font-size: 14px;
}

/* ========== 标题样式 ========== */
QLabel#title {
    font-size: 20px;
    font-weight: bold;
    color: #333;
    padding: 10px 0;
}

QLabel#subtitle {
    font-size: 16px;
    font-weight: bold;
    color: #555;
    padding: 5px 0;
}

/* ========== 分组框 ========== */
QGroupBox {
    font-weight: bold;
    border: 1px solid #ddd;
    border-radius: 6px;
    margin-top: 12px;
    padding: 15px 10px 10px 10px;
    background-color: #fafafa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 8px;
    color: #1a73e8;
    background-color: #fafafa;
}

/* ========== 主按钮样式 ========== */
QPushButton {
    background-color: #1a73e8;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    min-width: 80px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #1557b0;
}

QPushButton:pressed {
    background-color: #104080;
}

QPushButton:disabled {
    background-color: #ccc;
    color: #888;
}

/* 次要按钮 */
QPushButton#secondary {
    background-color: #f1f3f4;
    color: #333;
    border: 1px solid #ddd;
}

QPushButton#secondary:hover {
    background-color: #e8eaed;
    border-color: #ccc;
}

QPushButton#secondary:pressed {
    background-color: #d2d4d6;
}

/* 成功按钮 */
QPushButton#success {
    background-color: #34a853;
}

QPushButton#success:hover {
    background-color: #2d8f46;
}

/* 警告按钮 */
QPushButton#warning {
    background-color: #fbbc04;
    color: #333;
}

QPushButton#warning:hover {
    background-color: #e5a800;
}

/* 危险按钮 */
QPushButton#danger {
    background-color: #ea4335;
}

QPushButton#danger:hover {
    background-color: #d33426;
}

/* ========== 输入框 ========== */
QLineEdit, QComboBox, QDateEdit, QTextEdit, QSpinBox {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 6px 8px;
    background-color: white;
    selection-background-color: #1a73e8;
}

QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus, QSpinBox:focus {
    border-color: #1a73e8;
    outline: none;
}

QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QTextEdit:hover, QSpinBox:hover {
    border-color: #aaa;
}

/* 只读字段 */
QLineEdit:read-only {
    background-color: #f5f5f5;
    color: #666;
}

/* 下拉框箭头 */
QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

/* ========== 状态栏 ========== */
QStatusBar {
    background-color: #f8f9fa;
    border-top: 1px solid #e0e0e0;
    padding: 4px;
    color: #666;
}

/* ========== 列表组件 ========== */
QListWidget {
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: white;
    outline: none;
}

QListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #eee;
}

QListWidget::item:last-child {
    border-bottom: none;
}

QListWidget::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}

QListWidget::item:hover:!selected {
    background-color: #f5f5f5;
}

/* ========== 滚动区域 ========== */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background-color: #f5f5f5;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #ccc;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #aaa;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* ========== 菜单栏 ========== */
QMenuBar {
    background-color: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
    padding: 2px;
}

QMenuBar::item {
    padding: 6px 12px;
    background-color: transparent;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #e8eaed;
}

QMenu {
    background-color: white;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}

/* ========== 进度条 ========== */
QProgressBar {
    border: 1px solid #ddd;
    border-radius: 4px;
    text-align: center;
    height: 20px;
    background-color: #f5f5f5;
}

QProgressBar::chunk {
    background-color: #1a73e8;
    border-radius: 3px;
}

/* ========== 表格 ========== */
QTableWidget {
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: white;
    gridline-color: #eee;
}

QTableWidget::item {
    padding: 8px;
}

QTableWidget::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}

QHeaderView::section {
    background-color: #f8f9fa;
    border: none;
    border-bottom: 1px solid #ddd;
    padding: 8px;
    font-weight: bold;
}

/* ========== 复选框 ========== */
QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #ddd;
    border-radius: 3px;
    background-color: white;
}

QCheckBox::indicator:checked {
    background-color: #1a73e8;
    border-color: #1a73e8;
}

QCheckBox::indicator:hover {
    border-color: #1a73e8;
}

/* ========== 对话框 ========== */
QDialog {
    background-color: white;
}

/* ========== 提示框样式 ========== */
QToolTip {
    background-color: #333;
    color: white;
    border: none;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}

/* ========== 分隔线 ========== */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    background-color: #e0e0e0;
}
"""

# 侧边导航栏样式
NAV_SIDEBAR_STYLESHEET = """
QWidget#nav_sidebar {
    background-color: #f8f9fa;
    border-right: 1px solid #e0e0e0;
}

QLabel#nav_title {
    font-size: 16px;
    font-weight: bold;
    color: #1a73e8;
    padding: 20px 15px 10px 15px;
}

QListWidget#nav_list {
    border: none;
    background-color: transparent;
    outline: none;
}

QListWidget#nav_list::item {
    padding: 12px 15px;
    border-radius: 4px;
    margin: 2px 8px;
    border: none;
}

QListWidget#nav_list::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
    font-weight: bold;
}

QListWidget#nav_list::item:hover:!selected {
    background-color: #eee;
}
"""

# 提示信息样式
TIP_STYLE = """
    background-color: #e8f4fd;
    color: #1a73e8;
    padding: 10px 15px;
    border-radius: 4px;
    font-size: 13px;
    border-left: 4px solid #1a73e8;
"""

# 警告提示样式
WARNING_TIP_STYLE = """
    background-color: #fff8e1;
    color: #f57c00;
    padding: 10px 15px;
    border-radius: 4px;
    font-size: 13px;
    border-left: 4px solid #f57c00;
"""

# 成功提示样式
SUCCESS_TIP_STYLE = """
    background-color: #e8f5e9;
    color: #2e7d32;
    padding: 10px 15px;
    border-radius: 4px;
    font-size: 13px;
    border-left: 4px solid #2e7d32;
"""

# 错误提示样式
ERROR_TIP_STYLE = """
    background-color: #ffebee;
    color: #c62828;
    padding: 10px 15px;
    border-radius: 4px;
    font-size: 13px;
    border-left: 4px solid #c62828;
"""

# 保存状态样式
SAVE_STATUS_SAVED = "color: #34a853; font-size: 12px;"
SAVE_STATUS_UNSAVED = "color: #ea4335; font-size: 12px;"
SAVE_STATUS_NEUTRAL = "color: #999; font-size: 12px;"

# 颜色常量
COLORS = {
    "primary": "#1a73e8",
    "primary_dark": "#1557b0",
    "primary_light": "#e8f0fe",
    "success": "#34a853",
    "success_dark": "#2d8f46",
    "success_light": "#e8f5e9",
    "warning": "#fbbc04",
    "warning_dark": "#e5a800",
    "warning_light": "#fff8e1",
    "error": "#ea4335",
    "error_dark": "#d33426",
    "error_light": "#ffebee",
    "text": "#333333",
    "text_secondary": "#666666",
    "text_muted": "#999999",
    "border": "#dddddd",
    "border_light": "#eeeeee",
    "background": "#ffffff",
    "background_secondary": "#f8f9fa",
    "background_hover": "#f5f5f5",
}

# 图标（使用 Emoji）
ICONS = {
    "home": "🏠",
    "template": "📄",
    "templates": "📋",
    "export": "📤",
    "import": "📥",
    "save": "💾",
    "edit": "✏️",
    "delete": "🗑️",
    "add": "➕",
    "settings": "⚙️",
    "info": "ℹ️",
    "warning": "⚠️",
    "success": "✓",
    "error": "✗",
    "next": "→",
    "prev": "←",
    "up": "↑",
    "down": "↓",
    "pin": "📌",
    "party": "🎉",
    "user": "👤",
    "folder": "📁",
    "file": "📄",
    "calendar": "📅",
    "clock": "🕐",
    "search": "🔍",
    "refresh": "🔄",
    "lock": "🔒",
    "unlock": "🔓",
    "sync": "🔄",
}
