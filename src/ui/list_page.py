#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板列表页面基类
"""

from PyQt6.QtWidgets import (
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
from PyQt6.QtCore import pyqtSignal
from src.application.template_engine import TemplateEngine


class ListPage(QWidget):
    """
    模板列表页面基类
    
    子类需要实现：
        - get_page_title(): 返回页面标题
        - get_open_button_text(): 返回打开按钮文字
        - setup_extra_buttons(btn_layout): 添加额外按钮（可选）
    """

    # 打开某个模板的信号
    open_template = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.template_engine = TemplateEngine()

        self.init_ui()
        self.load_templates()

    def get_page_title(self) -> str:
        """返回页面标题，子类应重写此方法"""
        return "模板列表"

    def get_open_button_text(self) -> str:
        """返回打开按钮文字，子类应重写此方法"""
        return "打开选中模板"

    def setup_extra_buttons(self, btn_layout: QHBoxLayout):
        """添加额外按钮，子类可重写此方法"""
        pass

    def init_ui(self):
        layout = QVBoxLayout()

        # 页面标题
        title = QLabel(self.get_page_title())
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # 模板列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)

        # 按钮区域
        btn_layout = QHBoxLayout()
        
        open_btn = QPushButton(self.get_open_button_text())
        open_btn.clicked.connect(self.handle_open_selected)
        btn_layout.addWidget(open_btn)

        # 子类可添加额外按钮
        self.setup_extra_buttons(btn_layout)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 确保页面背景不透明
        self.setAutoFillBackground(True)

        self.list_widget.itemDoubleClicked.connect(self.handle_item_double_clicked)

    def load_templates(self):
        """从模板管理器加载模板列表"""
        self.list_widget.clear()
        templates = self.template_engine.get_templates()
        for tpl in templates:
            item = QListWidgetItem(
                f"{tpl.get('id', '')}_{tpl.get('name', '')}"
            )
            item.setData(32, tpl.get("id"))  # 32 = Qt.UserRole
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



