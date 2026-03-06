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
from src.utils.field_utils import create_widget, set_widget_value, get_widget_value
from src.utils.data_paths import get_admin_value, set_admin_value
from src.ui.styles import TIP_STYLE, ICONS


class AdminConfigPage(QWidget):
    """管理员配置页面类"""

    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()

        # 字段定义和控件缓存
        self.admin_field_groups: list[dict] = []
        self.field_widgets: dict[str, QWidget] = {}
        # (group, key) -> widget 的映射，用于快速查找
        self.group_key_to_widget: dict[tuple[str, str], QWidget] = {}

        self.init_ui()
        self.load_fields()
        self.build_forms()
        self.load_config()

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
        save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(save_btn)
        self.main_layout.addLayout(btn_layout)

        self.setLayout(self.main_layout)

    def load_fields(self):
        try:
            self.admin_field_groups, _ = self.data_manager.get_fields()
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
        self.field_widgets.clear()
        self.group_key_to_widget.clear()

        for group_def in self.admin_field_groups:
            group_name = group_def.get("group", "未分组")
            fields = sorted(
                group_def.get("fields", []),
                key=lambda x: x.get("display", {}).get("order", 0),
            )

            # 创建分组框
            group_box = QGroupBox(group_name)
            group_form = QFormLayout()

            for field_def in fields:
                key = field_def.get("key")
                display = field_def.get("display", {})
                # 直接使用 key 作为界面标签
                label_text = key

                # 根据字段类型创建控件
                widget = create_widget(field_def)
                self.field_widgets[key] = widget
                self.group_key_to_widget[(group_name, key)] = widget

                group_form.addRow(f"{label_text}：", widget)

            group_box.setLayout(group_form)
            self.form_layout.addWidget(group_box)

        self.form_layout.addStretch()

    def load_config(self):
        """加载配置并填充到表单"""
        config = self.data_manager.get_admin_config()

        # 根据 group + key 从配置中读取值并填充到控件
        for (group, key), widget in self.group_key_to_widget.items():
            value = get_admin_value(config, group, key, "")
            set_widget_value(widget, value)
            
        # 该代码实际上仅发挥作用于locked状态改变时
        # 管理员界面一直开着的时候，locked的改变除了false->true、也有true->false
        # 所以不论此时locked是true还是false，都要调用_set_locked_state()来更新界面状态
        self._set_locked_state(config.get("locked", False))
        
    def _collect_config_from_form(self) -> dict:
        """从表单收集配置数据"""
        config = self.data_manager.get_admin_config()

        # 遍历所有字段控件，按 group + key 存储值
        for group_def in self.admin_field_groups:
            group_name = group_def.get("group", "")
            for field_def in group_def.get("fields", []):
                key = field_def.get("key", "")
                if not key:
                    continue

                # 从控件获取值并设置到配置中
                widget = self.group_key_to_widget.get((group_name, key))
                if widget:
                    value = get_widget_value(widget, field_def)
                    set_admin_value(config, group_name, key, value)

        config["configured"] = True
        return config

    def _set_locked_state(self, locked: bool):
        """根据锁定状态更新表单可编辑性"""
        for widget in self.field_widgets.values():
            # QLineEdit/QComboBox/QDateEdit/QTextEdit 都提供 setReadOnly
            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(locked)

    def save_config(self):
        """保存配置"""
        try:
            config = self._collect_config_from_form()
            self.data_manager.save_admin_config(config)
            QMessageBox.information(self, "提示", "配置已保存。")
        except PermissionError as e:
            QMessageBox.warning(self, "提示", str(e))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败：{e}")
