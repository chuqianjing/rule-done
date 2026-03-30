#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
成员模板填写页面
"""

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QMessageBox,
    QHBoxLayout,
    QFormLayout,
)
from PySide6.QtCore import QTimer, Signal
from src.utils.widget_binding import create_widget, set_widget_value
from src.ui.template_page import TemplatePage
from datetime import datetime
from src.utils.styles import ICONS


class MemberTemplatePage(TemplatePage):
    """成员模板填写页面"""

    mode = "member"
    lock_document_signal = Signal()

    def __init__(self, template_id: str = "template_001", parent=None):
        self._is_initialized = False      # 用于showEvent()，在widget完全初始化后才执行检查逻辑
        super().__init__(template_id=template_id, parent=parent)
        self._is_initialized = True
    
    def tip_message(self) -> str:
        """成员模式的提示信息"""
        return """成员可根据字段旁的提示完善相关信息：
    - 已锁定：管理员已为该字段设置固定值，成员无需修改
    - 待确认：管理员已为该字段填写相应值以用于提示，成员可根据自身情况完善信息或保持原值
    - 无提示：管理员未配置该字段，成员需根据自身情况来填写"""


    def _show_basic_info_error(self):
        QMessageBox.critical(self, "错误", "请先完善基本信息")
        
    def check_basic_info(self):
        """专门负责检查数据的逻辑（仅成员模式）"""
        if self.basic_form is None:
            return
        for row in range(self.basic_form.rowCount()):
            item = self.basic_form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if item and item.widget() and not item.widget().text():
                QTimer.singleShot(100, lambda: self._show_basic_info_error())
                break

    def showEvent(self, event):
        """每次页面显示时都会运行"""
        super().showEvent(event)
        if self._is_initialized and self.mode == "member":
            self.check_basic_info()

    def _add_field_to_form(self, field_def: dict):
        """添加成员字段到表单"""
        key = field_def.get("key")
        widget = create_widget(field_def)
        self.field_widgets[key] = widget

        data_src = self.placeholder_mapping.get(key, {}).get("source")
        is_tip = self.placeholder_mapping.get(key, {}).get("is_tip", False)

        if data_src == "admin_template_data" and not is_tip:
            field_container = QWidget()
            field_layout = QHBoxLayout()
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(10)
            # 锁定提示
            lock_label = QLabel(f"{ICONS['lock']} 已锁定")
            lock_label.setStyleSheet("color: #888; font-size: 12px;")
            lock_label.setToolTip("此字段由管理员统一配置，不可修改")
            field_layout.addWidget(lock_label)
             # 表单
            field_layout.addWidget(widget, 1)

            field_container.setLayout(field_layout)
            self.template_form.addRow(f"{key}：", field_container)

            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(True)
            elif hasattr(widget, "setEnabled"):
                widget.setEnabled(False)
        elif is_tip:
            field_container = QWidget()
            field_layout = QHBoxLayout()
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(10)
            # 填写提示
            lock_label = QLabel(f"{ICONS['pen']} 待确认")
            lock_label.setStyleSheet("color: #888; font-size: 12px;")
            lock_label.setToolTip("此字段管理员已统一配置，但可修改")
            field_layout.addWidget(lock_label)
            # 表单
            field_layout.addWidget(widget, 1)

            field_container.setLayout(field_layout)
            self.template_form.addRow(f"{key}：", field_container)
        elif data_src == "member_template_data":
            self.template_form.addRow(f"{key}：", widget)

    def _render_basic_data(self):
        """根据字段定义动态显示只读基础信息"""
        while self.basic_form.rowCount():
            self.basic_form.removeRow(0)

        member_template_data = self.data_manager.get_member_info("template_data", self.template_id) or {}
        member_template_locked = member_template_data.get("locked", False)
        if member_template_locked:
            member_template_basic_entry = member_template_data.get("basic_entry", {})
            for key, value in member_template_basic_entry.items():
                label = QLabel(str(value))
                label.setObjectName(key)
                label.setStyleSheet("color: #555;")
                self.basic_form.addRow(f"{key}：", label)
            return
        
        member_basic_data = self.data_manager.get_member_info("basic_data") or {}
        admin_basic_data = self.data_manager.get_admin_config("basic_data") or {}

        display_priority = {"member_basic_data": 1}
        sorted_placeholder_mapping = dict(sorted(
            self.placeholder_mapping.items(),
            key=lambda item: (display_priority.get(item[1].get("source"), 999),
                              item[1].get("order", 999))))
        for placeholder, mapping in sorted_placeholder_mapping.items():
            if mapping.get("source") not in ["member_basic_data", "admin_basic_data"]:
                continue
            key = mapping.get("key", "")
            group = mapping.get("group", "")
            format = mapping.get("format", "")
            if mapping.get("source") == "member_basic_data":
                value = member_basic_data.get(key)
                if format == "YYYY年MM月" and value:
                    try:
                        dt = datetime.strptime(value, "%Y年%m月%d日")
                        value = f"{dt.year}年{dt.month}月"
                    except ValueError:
                        pass  # 日期格式不匹配时保持原值
            elif mapping.get("source") == "admin_basic_data":
                value = admin_basic_data.get(group, {}).get(key)
            label = QLabel(str(value))
            label.setObjectName(placeholder)
            label.setStyleSheet("color: #555;")
            self.basic_form.addRow(f"{placeholder}：", label)

    def load_data(self):
        """加载成员模板填写数据"""
        self._render_basic_data()

        member_template_data = self.data_manager.get_member_info("template_data", self.template_id) or {}
        admin_template_data = self.data_manager.get_admin_config("template_data", self.template_id) or {}

        for key, widget in self.field_widgets.items():
            data_src = self.placeholder_mapping.get(key, {}).get("source")
            if data_src == "member_template_data":
                value = member_template_data.get(key, "")
            elif data_src == "admin_template_data":
                value = admin_template_data.get(key, {}).get("value", "")

            field_def = self.get_field_def(key)
            set_widget_value(widget, value, field_def)

    def save_data(self):
        """保存成员模板填写数据"""
        try:
            template_data = self._collect_template_data_from_form()
            self.data_manager.save_member_info("template_page", template_data, self.template_id)
            QMessageBox.information(self, "提示", "材料数据已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def export_document(self):
        """导出 Word 文档"""
        try:
            self.save_data()
            output_path = self.template_engine.generate_document(self.template_id)
            QMessageBox.information(self, "提示", f"文档已导出：\n{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败：{e}")

    def lock_document(self):
        """锁定材料，禁止修改"""
        try:
            # 先弹出确认框，确认后再执行锁定操作
            reply = QMessageBox.question(self, "确认锁定", "锁定后将无法修改材料，是否继续？", QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
            basic_entry = self._collect_basic_data_from_form()
            template_entry = self._collect_template_data_from_form()
            self.data_manager.lock_member_template(self.template_id, basic_entry, template_entry)
            QMessageBox.information(self, "提示", "材料已锁定，无法修改。")
            self.lock_document_signal.emit()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"锁定失败：{e}")

    def _collect_basic_data_from_form(self) -> dict:
        """从表单采集基本信息数据"""
        data: dict[str, str] = {}
        for i in range(self.basic_form.rowCount()):
            # itemAt(row, role) 获取指定行和角色的项
            # QFormLayout.FieldRole 指的是右侧的输入框/显示控件列
            item = self.basic_form.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if item:
                widget = item.widget()
                if isinstance(widget, QLabel):
                    data[widget.objectName()] = widget.text()
        return data


