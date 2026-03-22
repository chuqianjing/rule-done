#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板填写页面基类
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QFormLayout,
    QPushButton,
    QHBoxLayout,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import pyqtSignal
from src.business.data_manager import DataManager
from src.business.template_engine import TemplateEngine
from src.utils.ui_utils import get_widget_value


class TemplatePage(QWidget):
    """模板填写页面基类"""

    back_to_list_page = pyqtSignal()
    mode: str = ""

    def __init__(self, template_id: str = "template_001", parent=None):
        super().__init__(parent)

        self.template_id = template_id

        self.data_manager = DataManager()
        self.template_engine = TemplateEngine()

        self.field_widgets: dict[str, QWidget] = {}
        self.placeholder_defs: dict[str, dict] = {}        # 模板占位符对应的字段定义

        self.placeholder_mapping: dict[str, dict] = {}     # 模板占位符映射关系
        self.referenced_member_basic_keys: set[str] = set()
        self.referenced_admin_keys: set[str] = set()

        self.init_ui()
        self.load_fields()
        self.build_template_forms()
        self.load_data()

    def init_ui(self):
        """初始化 UI 布局"""
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        template_info = self.template_engine.get_templates(self.template_id)
        title_text = template_info.get("name")

        title = QLabel(f"{self.get_title_prefix()}：{title_text}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.main_layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(0, 0, 10, 0)

        if self.mode == "member":
            self.basic_group = QGroupBox("基本项")
            self.basic_form = QFormLayout()
            self.basic_form.setSpacing(10)
            self.basic_form.setContentsMargins(15, 20, 15, 15)
            self.basic_group.setLayout(self.basic_form)
            scroll_layout.addWidget(self.basic_group)
        else:
            self.basic_group = None
            self.basic_form = None

        self.template_group = QGroupBox(self.get_template_group_title())
        self.template_form = QFormLayout()
        self.template_form.setSpacing(10)
        self.template_form.setContentsMargins(15, 20, 15, 15)
        self.template_group.setLayout(self.template_form)
        scroll_layout.addWidget(self.template_group)

        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)

        self.main_layout.addWidget(scroll_area, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        back_btn = QPushButton("← 返回")
        back_btn.clicked.connect(self.back_to_list_page.emit)
        btn_layout.addWidget(back_btn)

        btn_layout.addStretch()

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_data)
        btn_layout.addWidget(save_btn)

        if self.mode == "member":
            export_btn = QPushButton("导出 Word")
            export_btn.clicked.connect(self.export_document)
            btn_layout.addWidget(export_btn)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)
        self.setAutoFillBackground(True)

    def get_title_prefix(self) -> str:
        raise NotImplementedError

    def get_template_group_title(self) -> str:
        raise NotImplementedError

    def load_fields(self):
        """从字段定义配置中加载通用模板字段定义和管理员字段定义"""
        self.admin_fields, self.member_fields, self.template_fields = self.data_manager.get_fields(src="template")

        # self.placeholders = self.template_engine.get_placeholders(self.template_id)

    def build_template_forms(self):
        """构建模板想字段表单（基于模板文件中的占位符和通用字段库）"""
        while self.template_form.rowCount():
            self.template_form.removeRow(0)
        self.field_widgets.clear()
        self.placeholder_defs.clear()

        self.placeholders = self.template_engine.get_placeholders(self.template_id)

        # 以下全都是在找mapping，确定template specific
        self.placeholder_mapping = self.template_engine.auto_map_placeholders(self.template_id)

        self.referenced_member_basic_keys = {
            m.get("field", "")
            for m in self.placeholder_mapping.values()
            if m.get("source") == "basic_info" and m.get("field")
        }
        self.referenced_admin_keys = {
            m.get("key", "")
            for m in self.placeholder_mapping.values()
            if m.get("source") == "admin_config" and m.get("key")
        }

        known_fields = set()
        for field_def in self.member_fields:
            known_fields.add(field_def.get("key"))
        for field_def in self.admin_fields:
            known_fields.add(field_def.get("key"))

        mapped_non_template_fields = {
            placeholder.strip("{}")
            for placeholder, mapping in self.placeholder_mapping.items()
            if mapping.get("source") != "template_data"
        }

        self.template_specific_placeholders = sorted(
            placeholder
            for placeholder in self.placeholders
            if placeholder not in known_fields and placeholder not in mapped_non_template_fields
        )
        # 到这里

        # 这里才是build form
        for placeholder in self.template_specific_placeholders:
            field_def = self.template_engine.match_placehoder_def(placeholder)
            self.placeholder_defs[placeholder] = field_def
            self._add_field_to_form(field_def)

    def _add_field_to_form(self, field_def: dict):
        raise NotImplementedError

    def get_field_def(self, key: str) -> dict | None:
        return self.placeholder_defs.get(key)

    def _collect_template_data_from_form(self) -> dict:
        """从表单采集模板特有数据"""
        data: dict[str, str] = {}
        for key, widget in self.field_widgets.items():
            data[key] = get_widget_value(widget)
        return data

    def load_data(self):
        raise NotImplementedError

    def save_data(self):
        raise NotImplementedError

    def export_document(self):
        raise NotImplementedError
