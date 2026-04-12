#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
模板列表页面基类
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QAbstractItemView,
)
from PySide6.QtCore import Signal, Qt
from src.application.template_engine import TemplateEngine
from src.utils.styles import ICONS


class ListPage(QWidget):
    """
    模板列表页面基类
    
    子类需要实现：
        - get_page_title(): 返回页面标题
        - get_open_button_text(): 返回打开按钮文字
        - setup_extra_buttons(btn_layout): 添加额外按钮（可选）
    """

    # 打开某个模板的信号
    open_template = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.template_engine = TemplateEngine()

        self.init_ui()
        self.load_templates()

    def get_open_button_text(self) -> str:
        """返回打开按钮文字，子类应重写此方法"""
        return "打开选中模板"

    def setup_extra_buttons(self, btn_layout: QHBoxLayout):
        """添加额外按钮，子类可重写此方法"""
        pass

    def get_template_status_label(self, template_id: str) -> str:
        """返回模板状态标签，子类可重写此方法"""
        return ""

    def _display_width(self, text: str) -> int:
        """估算字符串显示宽度（中文按2，其他按1）"""
        width = 0
        for ch in text:
            width += 2 if ord(ch) > 127 else 1
        return width

    def _format_item_text(self, base_text: str, status_label: str, target_width: int) -> str:
        """格式化列表项文本，状态标签对齐显示"""
        if not status_label:
            return base_text
        padding = max(2, target_width - self._display_width(base_text) + 2)
        return f"{base_text}{' ' * padding}[{status_label}]"

    def init_ui(self):
        """初始化 UI"""
        # 显式启用样式背景绘制，避免在 QStackedWidget 切页时出现残影/透出
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("list_page_root")

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 页面标题
        title = QLabel("材料模板")
        title.setObjectName("title")
        layout.addWidget(title)

        # 模板列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.setup_extra_buttons(btn_layout)   # 子类可添加额外按钮
        open_btn = QPushButton(self.get_open_button_text()+f" {ICONS['next']}")
        open_btn.clicked.connect(self.handle_open_selected)
        btn_layout.addWidget(open_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 确保页面背景不透明
        self.setAutoFillBackground(True)

        self.list_widget.itemDoubleClicked.connect(self.handle_item_double_clicked)

    def load_templates(self):
        """从模板管理器加载模板列表"""
        self.list_widget.clear()
        templates = self.template_engine.get_templates()
        rows = []
        max_base_width = 0

        for tpl in templates:
            tpl_id = str(tpl.get("id", ""))
            tpl_name = str(tpl.get("name", ""))
            base_text = f"{tpl_id}、{tpl_name}"
            status_label = self.get_template_status_label(tpl_id)
            rows.append((tpl_id, base_text, status_label))
            max_base_width = max(max_base_width, self._display_width(base_text))

        for tpl_id, base_text, status_label in rows:
            item = QListWidgetItem(self._format_item_text(base_text, status_label, max_base_width))
            item.setData(32, tpl_id)  # 32 = Qt.UserRole
            self.list_widget.addItem(item)

    def _get_selected_template_ids(self) -> list:
        """获取当前选中的模板ID列表"""
        ids = []
        for item in self.list_widget.selectedItems():
            tpl_id = item.data(32)
            if tpl_id:
                ids.append(tpl_id)
        return ids

    def handle_open_selected(self):
        """处理打开选中模板"""
        ids = self._get_selected_template_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请先选择一个模板。")
            return
        # 只打开第一个选中的模板
        self.open_template.emit(ids[0])

    def handle_item_double_clicked(self, item: QListWidgetItem):
        """处理双击打开模板"""
        tpl_id = item.data(32)
        if tpl_id:
            self.open_template.emit(tpl_id)



