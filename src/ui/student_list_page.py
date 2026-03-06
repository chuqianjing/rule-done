#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生模板列表页面
"""

from PyQt6.QtWidgets import QPushButton, QHBoxLayout, QMessageBox
from PyQt6.QtCore import pyqtSignal
from src.ui.template_list_page import TemplateListPage


class StudentListPage(TemplateListPage):
    """
    学生模式的模板列表页面
    
    用于填写和导出模板
    """

    # 批量导出信号（传递一组模板 ID）
    export_templates = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

    def get_page_title(self) -> str:
        return "模板列表"

    def get_open_button_text(self) -> str:
        return "填写选中模板"

    def setup_extra_buttons(self, btn_layout: QHBoxLayout):
        """添加批量导出按钮"""
        export_btn = QPushButton("批量导出选中模板")
        export_btn.clicked.connect(self.handle_export_selected)
        btn_layout.addWidget(export_btn)

    def handle_export_selected(self):
        """处理批量导出选中的模板"""
        ids = self._get_selected_template_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请至少选择一个模板用于导出。")
            return
        self.export_templates.emit(ids)
