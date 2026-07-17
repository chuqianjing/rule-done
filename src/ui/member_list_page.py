#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
成员模板列表页面
"""

from PySide6.QtWidgets import (
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QLabel,
    QWidget,
    QVBoxLayout,
)
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
        self._reminder_label = None
        super().__init__(parent)

    def get_open_button_text(self) -> str:
        return "完善选中的材料"

    def load_templates(self):
        """加载模板列表后，顶部插入管理员提醒横幅（若有）。"""
        super().load_templates()
        # 先移除旧横幅（它在主布局中，super().load_templates() 清理不到）
        self._remove_reminder_banner()
        self._add_reminder_banner()

    def _remove_reminder_banner(self):
        """移除已有的提醒横幅。"""
        if self._reminder_label is not None:
            self._reminder_label.deleteLater()
            self._reminder_label = None

    def _add_reminder_banner(self):
        """在顶部添加管理员预期进度提醒（固定在滚动区域外，滚动时始终可见）。"""
        data_manager = self.template_engine.data_manager
        reminder = data_manager.get_progress_reminder()
        if not reminder:
            return

        container = QWidget()
        container.setObjectName("reminder_banner")
        container.setStyleSheet("""
            QWidget#reminder_banner {
                background-color: #f5f3ff;
                border: 1px solid #d4cdf4;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        title_label = QLabel("💬 预期进度")
        title_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #6b4ce6; background: transparent;"
        )
        layout.addWidget(title_label)

        text_label = QLabel(reminder)
        text_label.setWordWrap(True)
        text_label.setStyleSheet(
            "font-size: 13px; color: #3d2a8a; background: transparent; padding-left: 22px;"
        )
        layout.addWidget(text_label)

        container.setLayout(layout)

        # 插入到主布局中（滚动区域之前），使提醒在滚动时始终可见
        main_layout = self.layout()
        # 主布局顺序: title(0), tip(1), scroll_area(2), buttons(3)
        main_layout.insertWidget(2, container)
        self._reminder_label = container

    def refresh_reminder(self):
        """刷新预期进度提醒（同步完成后由 MainWindow 回调）。"""
        self._remove_reminder_banner()
        self._add_reminder_banner()

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
