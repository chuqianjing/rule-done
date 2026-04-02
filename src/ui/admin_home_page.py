#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
管理员主页
"""

from PySide6.QtWidgets import (
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
from PySide6.QtCore import Qt, Signal
from src.application.data_manager import DataManager
from src.utils.styles import ICONS, TIP_STYLE
from src.utils.widget_binding import create_widget, set_widget_value, get_widget_value


class AdminHomePage(QWidget):
    """管理员配置页面类"""

    go_to_template_list = Signal()  # 跳转到模板列表页面的信号
    
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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("admin_home_page")

        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = QLabel("基本信息")
        title.setObjectName("title")
        self.main_layout.addWidget(title)

        # 提示信息
        tip_label = QLabel(f"{ICONS['info']} 充分利用相关配置，促进重要信息的交流共享和基层党建的创新发展")
        tip_label.setStyleSheet(TIP_STYLE)
        tip_label.setWordWrap(True)
        self.main_layout.addWidget(tip_label)

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
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_data)
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        goto_tpl_btn = QPushButton(f"选择模板 {ICONS['next']}")
        goto_tpl_btn.clicked.connect(self.go_to_template_list.emit)
        btn_layout.addWidget(goto_tpl_btn)
        self.main_layout.addLayout(btn_layout)

        self.setLayout(self.main_layout)

        # 确保页面背景不透明，防止在 QStackedWidget 切换时"透出"
        self.setAutoFillBackground(True)

    # ======================== 保存配置 =========================

    def save_data(self):
        """保存配置"""
        try:
            basic_data = self._collect_basic_data_from_form()
            self.data_manager.save_admin_config("home_page", basic_data)
            self.load_data()  # 刷新数据，确保界面与保存的数据一致。目前该保存操作是操作即结果（与成员模板页的不一样），故不刷新亦可
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
        """加载字段定义"""
        try:
            self.admin_fields_groups = self.data_manager.get_fields(src='admin')
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载表单字段失败：{e}")

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
            group_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

            for field_def in fields:
                key = field_def.get("key")
                required = field_def.get("required", False)
                if required:
                    label_text = f'<html>{key}<span style="color:red;"> *</span>：</html>'
                else:
                    label_text = f"{key}："
                widget = create_widget(field_def)
                group_form.addRow(label_text, widget)

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
    
