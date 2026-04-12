#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
成员模板列表页面
"""

from PySide6.QtWidgets import QPushButton, QHBoxLayout, QMessageBox
from PySide6.QtCore import Signal
from src.ui.list_page import ListPage


class MemberListPage(ListPage):
    """
    成员模式的模板列表页面
    
    用于填写和导出模板
    """

    # 批量导出信号（传递一组模板 ID）
    export_templates = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

    def get_open_button_text(self) -> str:
        return "完善选中的材料"

    def setup_extra_buttons(self, btn_layout: QHBoxLayout):
        """添加批量导出按钮"""
        export_btn = QPushButton("批量导出选中的材料")
        export_btn.clicked.connect(self.handle_export_selected)
        btn_layout.addWidget(export_btn)

    def _has_filled_template_data(self, template_data: dict) -> bool:
        """判断模板是否存在可视为“已填写”的数据"""
        ignored_keys = {"version", "locked", "basic_entry", "template_entry", "archive_images"}

        template_entry = template_data.get("template_entry")
        if isinstance(template_entry, dict) and template_entry:
            return True

        for key, value in template_data.items():
            if key in ignored_keys:
                continue
            if isinstance(value, str) and value.strip():
                return True
            if isinstance(value, (dict, list)) and value:
                return True
            if isinstance(value, (int, float, bool)) and bool(value):
                return True
        return False

    def get_template_status_label(self, template_id: str) -> str:
        """返回成员列表中的模板状态标签"""
        data_manager = self.template_engine.data_manager
        template_data = data_manager.get_member_info("template_data", template_id)
        if not isinstance(template_data, dict):
            template_data = {}

        archive_images = data_manager.get_member_archive_images(template_id)
        if archive_images:
            return "已存档"

        if template_data.get("locked", False):
            return "已锁定"

        if self._has_filled_template_data(template_data):
            return "已填写"

        return ""

    def handle_export_selected(self):
        """处理批量导出选中的材料"""
        ids = self._get_selected_template_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请至少选择一个材料用于导出。")
            return
        self.export_templates.emit(ids)
