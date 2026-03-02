#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板列表页面
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

from src.data.template_manager import TemplateManager


class TemplateListPage(QWidget):
    """
    模板列表页面
    
    Args:
        mode: 'student'（学生模式）或 'admin'（管理员模式）
        parent: 父窗口
    """

    # 打开某个模板填写页的信号
    open_template = pyqtSignal(str)
    # 批量导出信号（传递一组模板 ID）
    export_templates = pyqtSignal(list)

    def __init__(self, mode: str = "student", parent=None):
        super().__init__(parent)

        self.mode = mode  # 'student' 或 'admin'
        self.template_manager = TemplateManager()

        self.init_ui()
        self.load_templates()

    def init_ui(self):
        layout = QVBoxLayout()

        # 根据模式显示不同标题
        if self.mode == "admin":
            title = QLabel("模板字段配置")
        else:
            title = QLabel("模板列表")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        
        # 根据模式显示不同按钮文字
        if self.mode == "admin":
            open_btn = QPushButton("配置选中模板")
        else:
            open_btn = QPushButton("填写选中模板")
        open_btn.clicked.connect(self.handle_open_selected)
        btn_layout.addWidget(open_btn)

        # 批量导出按钮仅在学生模式下显示
        if self.mode == "student":
            export_btn = QPushButton("批量导出选中模板")
            export_btn.clicked.connect(self.handle_export_selected)
            btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.list_widget.itemDoubleClicked.connect(self.handle_item_double_clicked)

    def load_templates(self):
        """从模板管理器加载模板列表"""
        self.list_widget.clear()
        templates = self.template_manager.list_available_templates()
        for tpl in templates:
            item = QListWidgetItem(
                f"{tpl.get('id', '')}_{tpl.get('name', '')}"
            )
            item.setData(32, tpl.get("id"))  # 32 = Qt.UserRole
            self.list_widget.addItem(item)

    def _get_selected_template_ids(self) -> list:
        ids = []
        for item in self.list_widget.selectedItems():
            tpl_id = item.data(32)
            if tpl_id:
                ids.append(tpl_id)
        return ids

    def handle_open_selected(self):
        ids = self._get_selected_template_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请先选择一个模板。")
            return
        # 只打开第一个选中的模板
        self.open_template.emit(ids[0])

    def handle_export_selected(self):
        ids = self._get_selected_template_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请至少选择一个模板用于导出。")
            return
        self.export_templates.emit(ids)

    def handle_item_double_clicked(self, item: QListWidgetItem):
        tpl_id = item.data(32)
        if tpl_id:
            self.open_template.emit(tpl_id)


