#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量导出对话框
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QCheckBox,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
)
from src.business.template_engine import TemplateEngine
from src.business.data_manager import DataManager


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
            cb = QCheckBox(f"{tpl.get('name', '')}（{tpl_id}）")
            cb.setChecked(True)
            self.checkbox_map[tpl_id] = cb
            layout.addWidget(cb)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        export_btn = QPushButton("开始导出")
        export_btn.clicked.connect(self.handle_export)
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def handle_export(self):
        selected_ids = [tid for tid, cb in self.checkbox_map.items() if cb.isChecked()]
        if not selected_ids:
            QMessageBox.information(self, "提示", "请至少选择一个模板。")
            return

        # 从成员数据中读取导出路径，若未设置则使用默认路径

        success_count = 0
        fail_count = 0

        for tpl_id in selected_ids:
            try:
                self.template_engine.generate_document(tpl_id)
                success_count += 1
            except Exception as e:
                fail_count += 1
                # 累积错误信息到日志或弹窗中，这里简化为提示
                print(f"导出模板 {tpl_id} 失败: {e}")

        QMessageBox.information(
            self,
            "导出完成",
            f"成功导出 {success_count} 个文档，失败 {fail_count} 个。",
        )
        self.accept()


