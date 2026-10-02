#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
管理员模板配置页面
"""

from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
    QHBoxLayout,
    QCheckBox,
    QPushButton
)
from src.ui.template_page import TemplatePage
from src.persistence.review_table_fields import REVIEW_ENABLED_FIELD, REVIEW_KEY
from src.utils.widget_binding import create_widget, set_widget_value, get_widget_value


class AdminTemplatePage(TemplatePage):
    """管理员模板配置页面"""

    mode = "admin"

    def __init__(self, template_id: str = "template_001", parent=None):
        self.lock_checkboxes: dict[str, QCheckBox] = {}
        self.review_checkbox: QCheckBox | None = None
        super().__init__(template_id=template_id, parent=parent)

    def tip_message(self) -> str:
        """管理员模式的提示信息"""
        return """本工具为模板字段的配置提供了如下三种方式，管理员可按需使用：
    - 锁定：勾选锁定框，管理员设定的该字段值在成员端会固定显示（不论该字段是否为空值），成员无法修改
    - 提示：管理员为该字段填写相应的值，但不勾选锁定框，该字段值在成员端会以提示的方式呈现，成员可根据需要修改其值
    - 无：管理员不配置该字段（既不填写值、也不勾选锁定框），该字段在成员端无任何配置信息，成员根据个人情况来填写"""

    def build_template_forms(self):
        """构建字段表单；审核开关位于头部固定区。"""
        self.lock_checkboxes.clear()
        super().build_template_forms()
        self._ensure_review_switch()

    def _ensure_review_switch(self):
        """在头部固定区创建审核开关；已创建则复用。"""
        if self.mode != "admin" or self.review_checkbox is not None:
            return
        checkbox = QCheckBox("开启材料审核机制")
        checkbox.setToolTip(
            "开启后，成员须先提交本材料的待填项、经审核通过，方可导出与锁定。\n"
            "需先在「基本信息」页的「双端交互」分组配置材料审核表 ID，并建好该表。"
        )
        checkbox.setStyleSheet("QCheckBox { color: #666; }")
        self.review_checkbox = checkbox
        self.header_extra_layout.addWidget(checkbox)
        self.header_extra.setVisible(True)

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
        for key, widget in self.field_widgets.items():
            data = self.placeholder_mapping.get(key, {}).get("data", {}) or {}
            value = data.get("value", "")
            is_locked = data.get("locked", False)

            set_widget_value(widget, value)

            if key in self.lock_checkboxes:
                self.lock_checkboxes[key].setChecked(is_locked)
        self._load_review_switch()
        self._set_locked_state(self.data_manager.get_admin_config("locked") or False)

    def _load_review_switch(self):
        """把管理员配置中的审核开关回填到复选框。"""
        checkbox = getattr(self, "review_checkbox", None)
        if checkbox is None:
            return
        config = self.data_manager.get_admin_config("template_data", self.template_id)
        review = config.get(REVIEW_KEY) if isinstance(config, dict) else None
        enabled = bool(isinstance(review, dict) and review.get(REVIEW_ENABLED_FIELD))
        checkbox.setChecked(enabled)

    def _set_locked_state(self, locked: bool):
        """根据锁定状态更新表单可编辑性"""
        for key, widget in self.field_widgets.items():
            widget.setEnabled(not locked)
            self.lock_checkboxes[key].setEnabled(not locked)
        checkbox = getattr(self, "review_checkbox", None)
        if checkbox is not None:
            checkbox.setEnabled(not locked)

    def save_data(self):
        """保存管理员模板配置数据"""
        try:
            # 先取出开关状态（字段控件会被下面的 build_template_forms() 销毁；
            # 审核开关在头部固定区虽不受影响，统一在重建前取值更稳妥）
            checkbox = getattr(self, "review_checkbox", None)
            review_enabled = checkbox.isChecked() if checkbox is not None else False

            template_data = {}
            for key, widget in self.field_widgets.items():
                value = get_widget_value(widget)
                lock_checkbox = self.lock_checkboxes.get(key)
                is_locked = lock_checkbox.isChecked() if lock_checkbox is not None else False
                template_data[key] = {
                    "value": value,
                    "locked": is_locked,
                }
            # 审核开关必须与字段数据**同一次写入**：
            # save_admin_config("template_page") 会整体替换该模板的配置条目
            if checkbox is not None:
                template_data[REVIEW_KEY] = {REVIEW_ENABLED_FIELD: review_enabled}

            self.data_manager.save_admin_config("template_page", template_data, self.template_id)
            self.load_mapping()
            self.build_template_forms()
            self.load_data()
            QMessageBox.information(self, "提示", "模板配置已保存。")
            self._warn_if_placeholder_problems()
            if review_enabled:
                self._warn_if_review_table_missing()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def _warn_if_placeholder_problems(self):
        """本模板 docx 的占位符写法有问题时给出提醒（不阻断保存）。

        剥码会改写项名，所以「码写在中间」「漏写项名」「多项同名」这类写法
        必须尽早暴露，否则要到导出时才炸或静默合并字段。
        """
        try:
            problems = self.template_engine.validate_placeholders(self.template_id)
        except Exception:
            return
        if not problems:
            return
        QMessageBox.warning(
            self,
            "提示",
            "本模板的占位符写法存在以下问题：\n\n"
            + "\n".join(f"· {item}" for item in problems)
            + "\n\n请修改 Word 模板中的占位符后重新打开本页。",
        )

    def _warn_if_review_table_missing(self):
        """已开启审核但未配置材料审核表时给出提醒（不阻断，允许多步配置）。"""
        try:
            if self.data_manager.has_review_table_config():
                return
        except Exception:
            return
        QMessageBox.warning(
            self,
            "提示",
            "已开启材料审核机制，但尚未配置「材料审核表 ID」。\n\n"
            "请在「基本信息」页的「双端交互」分组中填写当前平台的材料审核表 ID 并保存，"
            "否则成员无法提交审核。",
        )

    def export_document(self):
        """管理员模式不提供导出能力"""
        return
