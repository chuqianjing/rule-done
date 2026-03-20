#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
管理员配置页面
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QHBoxLayout,
    QScrollArea,
    QFrame,
)
from src.business.data_manager import DataManager
from src.utils.ui_utils import create_widget, set_widget_value, get_widget_value
from src.ui.styles import ICONS


class AdminHomePage(QWidget):
    """管理员配置页面类"""

    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()

        # 字段定义和控件缓存
        self.admin_fields_groups: list[dict] = []
        self.group_key_to_widget: dict[tuple[str, str], QWidget] = {}     # (group, key)->widget 的映射，用于将widget和字段相关联

        self.init_ui()
        self.load_fields()
        self.build_forms()
        self.load_data()

    def init_ui(self):
        """初始化 UI"""
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = QLabel(f"{ICONS['home']} 配置党支部基本信息")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.main_layout.addWidget(title)

        # 表单区域（滚动）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        self.form_container = QWidget()
        self.form_layout = QVBoxLayout()
        self.form_layout.setSpacing(15)
        self.form_layout.setContentsMargins(0, 0, 10, 0)
        self.form_container.setLayout(self.form_layout)

        scroll_area.setWidget(self.form_container)
        self.main_layout.addWidget(scroll_area, 1)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_data)
        btn_layout.addWidget(save_btn)
        self.main_layout.addLayout(btn_layout)

        self.setLayout(self.main_layout)

    # ======================== 保存配置 =========================

    def save_data(self):
        """保存配置"""
        try:
            basic_data = self._collect_basic_data_from_form()
            self.data_manager.save_admin_config("home_page", basic_data)
            QMessageBox.information(self, "提示", "配置已保存。")
        except PermissionError as e:
            QMessageBox.warning(self, "提示", str(e))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败：{e}")

    def _collect_basic_data_from_form(self) -> dict:
        """从表单收集配置数据"""
        data: dict[str, str] = {}
        for (group_name, key), widget in self.group_key_to_widget.items():
            if group_name not in data:
                data[group_name] = {}
            data[group_name][key] = get_widget_value(widget)
        return data
    
    # ======================== 渲染表单 =========================

    def load_fields(self):
        try:
            self.admin_fields_groups = self.data_manager.get_fields(src='admin')
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取字段定义失败：{e}")
            return

    def build_forms(self):
        """根据字段定义动态生成管理员配置表单"""
        # 清空旧表单
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.group_key_to_widget.clear()

        for group_def in self.admin_fields_groups:
            # 创建分组框
            group_name = group_def.get("group", "未分组")
            fields = sorted(group_def.get("fields", []), key=lambda x: x.get("display", {}).get("order", 0))

            group_box = QGroupBox(group_name)
            group_form = QFormLayout()

            for field_def in fields:
                key = field_def.get("key")
                widget = create_widget(field_def)
                group_form.addRow(f"{key}：", widget)

                self.group_key_to_widget[(group_name, key)] = widget

            group_box.setLayout(group_form)
            self.form_layout.addWidget(group_box)

        self.form_layout.addStretch()

    def load_data(self):
        """加载数据并填充到表单"""
        # 填充表单
        for (group, key), widget in self.group_key_to_widget.items():
            value = self.data_manager.get_admin_config("basic_data", group, key)
            set_widget_value(widget, value)
        
        # 设置控件状态
        self._set_locked_state(self.data_manager.get_admin_config("locked") == True)

    def _set_locked_state(self, locked: bool):
        """根据锁定状态更新表单可编辑性"""
        for widget in self.group_key_to_widget.values():
            widget.setEnabled(not locked)
    
