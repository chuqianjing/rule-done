#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
管理员模板配置页面
"""

from PyQt6.QtWidgets import (
    QWidget,
    QMessageBox,
    QHBoxLayout,
    QCheckBox,
)
from src.utils.widget_binding import create_widget, set_widget_value, get_widget_value
from src.ui.template_page import TemplatePage


class AdminTemplatePage(TemplatePage):
    """管理员模板配置页面"""

    mode = "admin"

    def __init__(self, template_id: str = "template_001", parent=None):
        self.lock_checkboxes: dict[str, QCheckBox] = {}
        super().__init__(template_id=template_id, parent=parent)

    def tip_message(self) -> str:
        """管理员模式的提示信息"""
        return """本工具为模板字段的配置提供了如下三种方式，管理员可按需使用：
    - 锁定：勾选锁定框，管理员设定的该字段值在成员端会固定显示（不论该字段是否为空值），成员无法修改
    - 提示：管理员为该字段填写相应的值，但不勾选锁定框，该字段值在成员端会以提示的方式呈现，成员可根据需要修改其值
    - 无：管理员不配置该字段（既不填写值、也不勾选锁定框），该字段在成员端无任何配置信息，成员根据个人情况来填写"""

    def _add_field_to_form(self, field_def: dict):
        """添加管理员字段到表单"""
        key = field_def.get("key")
        # 输入框
        widget = create_widget(field_def)
        self.field_widgets[key] = widget
        field_container = QWidget()
        field_layout = QHBoxLayout()
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(10)
        field_layout.addWidget(widget, 1)
        # 锁定复选框
        lock_checkbox = QCheckBox("锁定")
        lock_checkbox.setToolTip("勾选后成员将不能修改此字段")
        lock_checkbox.setStyleSheet("QCheckBox { color: #666; }")
        self.lock_checkboxes[key] = lock_checkbox
        field_layout.addWidget(lock_checkbox)

        field_container.setLayout(field_layout)
        self.template_form.addRow(f"{key}：", field_container)

    def load_data(self):
        """加载管理员模板配置数据"""
        template_data = self.data_manager.get_admin_config("template_data", self.template_id) or {}

        for key, widget in self.field_widgets.items():
            field_config = template_data.get(key, {})
            value = field_config.get("value", "")
            is_locked = field_config.get("locked", False)

            field_def = self.get_field_def(key)
            set_widget_value(widget, value, field_def)

            if key in self.lock_checkboxes:
                self.lock_checkboxes[key].setChecked(is_locked)
        self._set_locked_state(self.data_manager.get_admin_config("locked") or False)

    def _set_locked_state(self, locked: bool):
        """根据锁定状态更新表单可编辑性"""
        for key, widget in self.field_widgets.items():
            widget.setEnabled(not locked)
            self.lock_checkboxes[key].setEnabled(not locked)

    def save_data(self):
        """保存管理员模板配置数据"""
        try:
            template_data = {}
            for key, widget in self.field_widgets.items():
                value = get_widget_value(widget)
                is_locked = self.lock_checkboxes.get(key, QCheckBox()).isChecked()
                template_data[key] = {
                    "value": value,
                    "locked": is_locked,
                }
            
            self.data_manager.save_admin_config("template_page", template_data, self.template_id)
            QMessageBox.information(self, "提示", "模板配置已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def export_document(self):
        """管理员模式不提供导出能力"""
        return
