#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通用 UI 组件
"""

from datetime import datetime

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
    QFileDialog,
)

from src.data.config_manager import ConfigManager
from src.utils.field_utils import create_widget, set_widget_value, get_widget_value
from src.utils.data_paths import get_value_by_path, set_value_by_path
from src.utils.fields_loader import load_fields_definition
from src.business.data_manager import DataManager


# 渲染器类，提供一些通用方法，供不同页面调用
class FormManager:
    """通用表单 UI 组件类"""

    def __init__(self, layout, mode='admin'):
        self.data_manager = DataManager()
        self.config_manager = ConfigManager()

        self.layout = layout
        self.mode = mode
        self.field_widgets = {}
        self.path_to_widget = {}

    def load_fields(self):
        """从 fields_definition.json 加载管理员字段定义"""
        i, j = self.data_manager.get_fields(mode=self.mode)
        if self.mode == 'admin':
            self.admin_field_groups = i
        elif self.mode == 'student':
            self.basic_fields, self.admin_fields = i, j
        else:
            raise ValueError(f"未知的模式：{self.mode}")
    
    def build_forms(self, field_groups):
        self._clear()
    






    def _clear(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.field_widgets.clear()
        self.path_to_widget.clear()
        





