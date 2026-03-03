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
    QLineEdit,
    QGroupBox,
    QMessageBox,
    QHBoxLayout,
    QScrollArea,
    QFrame,
)

from src.data.config_manager import ConfigManager
from src.utils.field_utils import create_widget, set_widget_value, get_widget_value
from src.utils.data_paths import get_value_by_path, set_value_by_path


class AdminConfigPage(QWidget):
    """管理员配置页面类"""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()

        # 字段定义和控件缓存
        self.admin_field_groups: list[dict] = []
        self.field_widgets: dict[str, QWidget] = {}
        # path -> widget 的映射，用于快速查找
        self.path_to_widget: dict[str, QWidget] = {}

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
        title = QLabel("管理员配置")
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
        
        # 保存按钮
        btn_layout.addStretch()
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(save_btn)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)

    def load_fields(self):
        '''
        """从 fields_definition.json 加载管理员字段定义"""
        try:
            config = self.data_manager.get_fields_definition()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取字段定义失败：{e}")
            return
        self.admin_field_groups = config
        '''
        from src.utils.fields_loader import load_fields_definition
        try:
            config = load_fields_definition()
        except FileNotFoundError:
            QMessageBox.critical(self, "错误", "缺少字段定义文件：resources/fields_definition.json")
            return
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取字段定义失败：{e}")
            return

        # 加载管理员字段分组定义（用于分组显示）
        self.admin_field_groups = sorted(
            config.get("admin_fields", []),
            key=lambda x: x.get("group_order", 0),
        )
        

    def build_forms(self):
        """根据字段定义动态生成管理员配置表单"""
        # 清空旧表单
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.field_widgets.clear()
        self.path_to_widget.clear()

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
                path = field_def.get("path", "")
                display = field_def.get("display", {})
                label_text = display.get("label", key)
                field_type = field_def.get("type", "text")

                # 根据字段类型创建控件
                widget = create_widget(field_def)
                self.field_widgets[key] = widget
                if path:
                    self.path_to_widget[path] = widget

                group_form.addRow(f"{label_text}：", widget)

            group_box.setLayout(group_form)
            self.form_layout.addWidget(group_box)

        self.form_layout.addStretch()

    def load_config(self):
        """加载配置并填充到表单"""
        config = self.config_manager.load_config()

        # 根据 path 从嵌套结构中读取值并填充到控件
        for path, widget in self.path_to_widget.items():
            value = get_value_by_path(config, path, "")
            set_widget_value(widget, value)

        # 处理锁定状态
        if config.get("locked", False):
            self._set_locked_state(True)

    def _collect_config_from_form(self) -> dict:
        """从表单收集配置数据"""
        config = self.config_manager.load_config()

        # 确保基础结构存在
        for group_def in self.admin_field_groups:
            for field_def in group_def.get("fields", []):
                path = field_def.get("path", "")
                if not path:
                    continue

                # 从控件获取值并设置到配置中
                widget = self.path_to_widget.get(path)
                if widget:
                    value = get_widget_value(widget, field_def)
                    set_value_by_path(config, path, value)

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
            self.config_manager.save_config(config)
            QMessageBox.information(self, "提示", "配置已保存。")
        except PermissionError as e:
            QMessageBox.warning(self, "提示", str(e))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败：{e}")
