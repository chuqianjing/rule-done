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
        # 预先计算各模板的配置快照状态（避免状态标签逐行重复判定）
        self._snapshot_states = (
            self.template_engine.data_manager.get_template_snapshot_states()
        )
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
        """在顶部添加管理员进度提醒（固定在滚动区域外，滚动时始终可见）。"""
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

        title_label = QLabel("💬 进度提醒")
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
        # 主布局顺序: title(0), scroll_area(1), tip(2), buttons(3)
        main_layout.insertWidget(1, container)
        self._reminder_label = container

    def refresh_reminder(self):
        """刷新进度提醒（同步完成后由 MainWindow 回调）。"""
        self._remove_reminder_banner()
        self._add_reminder_banner()

    def setup_extra_buttons(self, btn_layout: QHBoxLayout):
        """添加批量导出按钮"""
        export_btn = QPushButton("批量导出选中的材料")
        export_btn.clicked.connect(self.handle_export_selected)
        btn_layout.addWidget(export_btn)

    def get_template_status_label(self, template_id: str) -> str:
        """返回成员列表中的模板状态标签（工作期 / 待固化 / 已固化）。"""
        state = getattr(self, "_snapshot_states", {}).get(template_id, "")
        if state == "archived":
            return "已存档"
        if state == "locked":
            return "已锁定"
        if state == "graduated":
            return "待固化"
        if state == "working":
            return "工作期"
        return ""

    def get_template_status_color(self, status_label: str) -> str:
        """状态标签颜色：工作期蓝、待固化橙、已固化（已锁定/已存档）绿。"""
        if status_label == "工作期":
            return "#1a73e8"
        if status_label == "待固化":
            return "#e67e22"
        if status_label in ("已锁定", "已存档"):
            return "#34a853"
        return super().get_template_status_color(status_label)

    def handle_export_selected(self):
        """处理批量导出选中的材料"""
        ids = self._get_selected_template_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请至少选择一个材料用于导出。")
            return
        self.export_templates.emit(ids)
