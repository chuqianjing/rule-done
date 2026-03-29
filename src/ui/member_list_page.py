#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
成员模板列表页面
"""

from PyQt6.QtWidgets import QPushButton, QHBoxLayout, QMessageBox
from PyQt6.QtCore import pyqtSignal
from src.ui.list_page import ListPage


class MemberListPage(ListPage):
    """
    成员模式的模板列表页面
    
    用于填写和导出模板
    """

    # 批量导出信号（传递一组模板 ID）
    export_templates = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

    def get_open_button_text(self) -> str:
        return "完善选中的材料"

    def setup_extra_buttons(self, btn_layout: QHBoxLayout):
        """添加批量导出按钮"""
        export_btn = QPushButton("批量导出选中的材料")
        export_btn.clicked.connect(self.handle_export_selected)
        btn_layout.addWidget(export_btn)

    def handle_export_selected(self):
        """处理批量导出选中的材料"""
        ids = self._get_selected_template_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请至少选择一个材料用于导出。")
            return
        self.export_templates.emit(ids)
