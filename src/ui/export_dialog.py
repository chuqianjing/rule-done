#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
批量导出对话框
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QCheckBox,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from pathlib import Path
from src.application.data_manager import DataManager
from src.application.template_engine import TemplateEngine
from src.utils.file_path import get_runtime_exports_dir


class ExportDialog(QDialog):
    """批量导出多个模板的对话框"""

    def __init__(self, template_ids: list[str] | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("批量导出 Word 文档")
        self.template_engine = TemplateEngine()
        self.data_manager = DataManager()

        self.template_ids = template_ids or [
            tpl.get("id") for tpl in self.template_engine.get_templates()
        ]
        self.checkbox_map: dict[str, QCheckBox] = {}

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("请选择要导出的模板："))

        for tpl_id in self.template_ids:
            tpl = self.template_engine.get_templates(tpl_id)
            cb = QCheckBox(f"{tpl.get('name', tpl_id)}")
            cb.setChecked(True)
            self.checkbox_map[tpl_id] = cb
            layout.addWidget(cb)

        btn_layout = QHBoxLayout()

        export_btn = QPushButton("开始导出")
        export_btn.clicked.connect(self.handle_export)
        btn_layout.addWidget(export_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def handle_export(self):
        selected_ids = [tid for tid, cb in self.checkbox_map.items() if cb.isChecked()]
        if not selected_ids:
            QMessageBox.information(self, "提示", "请至少选择一个模板。")
            return

        success_count = 0
        failed_templates = []

        for tpl_id in selected_ids:
            try:
                self.template_engine.generate_document(tpl_id)
                success_count += 1
            except Exception as e:
                failed_templates.append(f"{tpl_id}: {e}")

        if failed_templates:
            self._show_export_result(
                QMessageBox.Icon.Warning,
                "导出完成",
                f"成功导出 {success_count} 个文档，失败 {len(failed_templates)} 个。\n\n失败详情：\n"
                + "\n".join(failed_templates),
            )
        else:
            self._show_export_result(
                QMessageBox.Icon.Information,
                "导出完成",
                f"成功导出 {success_count} 个文档。",
            )
        self.accept()

    def _show_export_result(self, icon, title, message):
        """显示导出结果提示，并提供“打开导出文件夹”按钮"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setIcon(icon)
        export_path = self.data_manager.get_system_settings("export_path") or str(
            get_runtime_exports_dir()
        )
        message += f"\n\n导出文件夹：\n{export_path}"
        msg_box.setText(message)

        open_folder_btn = msg_box.addButton(
            "打开所在文件夹", QMessageBox.ButtonRole.ActionRole
        )
        open_folder_btn.clicked.connect(self._open_export_folder)
        msg_box.addButton("确定", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

    def _open_export_folder(self):
        """在文件管理器中打开导出文件夹"""
        export_path = self.data_manager.get_system_settings("export_path") or str(
            get_runtime_exports_dir()
        )
        folder_path = Path(export_path)
        if not folder_path.exists():
            QMessageBox.warning(self, "提示", f"导出文件夹不存在：\n{folder_path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path)))


