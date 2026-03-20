#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
成员模板填写页面
"""

from pathlib import Path
import datetime

from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QMessageBox,
    QHBoxLayout,
)

from src.utils.ui_utils import create_widget, set_widget_value
from src.ui.template_page import TemplatePage


class MemberTemplatePage(TemplatePage):
    """成员模板填写页面"""

    mode = "member"

    def get_title_prefix(self) -> str:
        return "模板填写"

    def get_template_group_title(self) -> str:
        return "本模板特有字段"

    def should_show_basic_group(self) -> bool:
        return True

    def should_show_export_button(self) -> bool:
        return True

    def _add_field_to_form(self, field_def: dict):
        """添加成员字段到表单"""
        key = field_def.get("key")
        label_text = key
        widget = create_widget(field_def)

        self.field_widgets[key] = widget

        field_config = self.data_manager.get_admin_config().get("template_data", {}).get(self.template_id, {}).get(key, {})

        is_locked = field_config.get("locked", False)
        admin_value = field_config.get("value", "")

        if is_locked and admin_value:
            field_container = QWidget()
            field_layout = QHBoxLayout()
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(10)

            field_layout.addWidget(widget, 1)

            lock_label = QLabel("🔒 管理员已配置")
            lock_label.setStyleSheet("color: #888; font-size: 12px;")
            lock_label.setToolTip("此字段由管理员统一配置，不可修改")
            field_layout.addWidget(lock_label)

            field_container.setLayout(field_layout)
            self.template_form.addRow(f"{label_text}：", field_container)

            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(True)
            elif hasattr(widget, "setEnabled"):
                widget.setEnabled(False)
        else:
            self.template_form.addRow(f"{label_text}：", widget)

    def load_data(self):
        """加载成员模板填写数据"""
        admin_config = self.data_manager.get_admin_config()
        member_info = self.data_manager.get_member_info()

        self._render_basic_info(admin_config, member_info)

        template_data = member_info.get("template_data", {}).get(self.template_id, {})
        admin_template_data = admin_config.get("template_data", {}).get(self.template_id, {})

        for key, widget in self.field_widgets.items():
            member_value = template_data.get(key, "")

            admin_field_config = admin_template_data.get(key, {})
            admin_value = admin_field_config.get("value", "")
            is_locked = admin_field_config.get("locked", False)

            if is_locked and admin_value:
                value = admin_value
            else:
                value = member_value if member_value else admin_value

            field_def = self.get_field_def(key)
            set_widget_value(widget, value, field_def)

    def save_data(self):
        """保存成员模板填写数据"""
        try:
            template_data = self._collect_template_data_from_form()
            self.data_manager.save_member_info("template_page", template_data, self.template_id)
            QMessageBox.information(self, "提示", "模板数据已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def export_document(self):
        """导出 Word 文档"""
        try:
            self.save_data()

            member_info = self.data_manager.get_member_info()
            basic = member_info.get("basic_data", {})

            name = basic.get("姓名", "未命名")
            template_info = self.data_manager.get_templates(self.template_id)
            template_name = template_info.get("name", "文档")

            date_str = datetime.datetime.now().strftime("%Y%m%d")
            export_path = member_info.get("settings", {}).get("export_path", "./exports")
            export_dir = Path(export_path)
            export_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{template_name}_{name}_{date_str}.docx"
            output_path = str(export_dir / filename)

            self.template_engine.generate_document(self.template_id, output_path)
            QMessageBox.information(self, "提示", f"文档已导出：\n{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败：{e}")
