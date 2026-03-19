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
    QMessageBox,
)
from PyQt6.QtCore import QTimer, pyqtSignal
from src.business.data_manager import DataManager
from src.business.template_engine import TemplateEngine
from src.utils.field_utils import get_widget_value
from src.utils.data_paths import get_admin_value


class TemplatePage(QWidget):
    """模板填写页面基类"""

    back_to_tpl = pyqtSignal()
    mode: str = ""

    def __init__(self, template_id: str = "template_001", parent=None):
        super().__init__(parent)

        self._is_initialized = False

        self.template_id = template_id
        self.data_manager = DataManager()
        self.template_engine = TemplateEngine()

        self.field_widgets: dict[str, QWidget] = {}
        self.template_field_defs: dict[str, dict] = {}

        # 管理员配置缓存（用于日期格式等）
        self.admin_config = self.data_manager.get_admin_config()

        self.init_ui()
        self.load_field_definitions()
        self.build_template_form()
        self.load_data()

        self._is_initialized = True

    def init_ui(self):
        """初始化 UI 布局"""
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        template_info = self.data_manager.get_templates(self.template_id)
        title_text = template_info.get("name", "模板填写")

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

        if self.should_show_basic_group():
            self.basic_group = QGroupBox("基础信息（只读，来自首页和管理员配置）")
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
        back_btn.clicked.connect(self.back_to_tpl.emit)
        btn_layout.addWidget(back_btn)

        btn_layout.addStretch()

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_data)
        btn_layout.addWidget(save_btn)

        if self.should_show_export_button():
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

    def should_show_basic_group(self) -> bool:
        return False

    def should_show_export_button(self) -> bool:
        return False

    def load_field_definitions(self):
        """从字段定义配置中加载通用模板字段定义和管理员字段定义"""
        self.admin_fields, self.member_fields, self.template_fields = self.data_manager.get_fields(src="template")

    def build_template_form(self):
        """构建模板字段表单（基于模板文件中的占位符和通用字段库）"""
        while self.template_form.rowCount():
            self.template_form.removeRow(0)
        self.field_widgets.clear()
        self.template_field_defs.clear()

        self.placeholders = self.template_engine.get_placeholders(self.template_id)

        known_fields = set()
        for field_def in self.member_fields:
            known_fields.add(field_def.get("key"))
        for field_def in self.admin_fields:
            known_fields.add(field_def.get("key"))

        self.template_specific_placeholders = sorted(self.placeholders - known_fields)

        for placeholder in self.template_specific_placeholders:
            field_def = self._match_field_definition(placeholder)
            self.template_field_defs[placeholder] = field_def
            self._add_field_to_form(field_def)

    def _match_field_definition(self, placeholder: str) -> dict:
        """根据占位符名称模糊匹配字段定义"""
        # 遍历所有模板字段定义，进行关键词匹配
        for field_def in self.template_fields:
            if field_def.get("is_default"):
                continue
            keywords = field_def.get("match_keywords", [])
            for keyword in keywords:
                if keyword in placeholder:
                    return {
                        "key": placeholder,
                        "type": field_def.get("type", "text"),
                        "required": field_def.get("required", False),
                        "format": field_def.get("format"),
                        "display": field_def.get("display", {}),
                    }

        # 如果没有匹配，返回默认定义
        default_def = next((f for f in self.template_fields if f.get("is_default")), None)
        if default_def:
            return {
                "key": placeholder,
                "type": default_def.get("type", "text"),
                "required": default_def.get("required", False),
                "display": default_def.get("display", {}),
            }

        # 最后的 fallback
        return {
            "key": placeholder,
            "type": "text",
            "required": False,
            "display": {"order": 999},
        }

    def _add_field_to_form(self, field_def: dict):
        raise NotImplementedError

    def get_field_def(self, key: str) -> dict | None:
        return self.template_field_defs.get(key)

    def _render_basic_info(self, admin_config: dict, member_info: dict):
        """根据字段定义动态显示只读基础信息"""
        if self.basic_form is None:
            return

        while self.basic_form.rowCount():
            self.basic_form.removeRow(0)

        basic = member_info.get("basic_info", {})

        for field_def in self.member_fields:
            key = field_def.get("key")
            label_text = key
            value = str(basic.get(key, ""))

            label = QLabel(value)
            label.setStyleSheet("color: #555;")
            if key in self.placeholders:
                self.basic_form.addRow(f"{label_text}：", label)

        for field_def in self.admin_fields:
            key = field_def.get("key")
            group = field_def.get("group", "")
            label_text = key
            value = get_admin_value(admin_config, group, key, "")

            label = QLabel(str(value))
            label.setStyleSheet("color: #555;")
            if key in self.placeholders:
                self.basic_form.addRow(f"{label_text}：", label)

    def check_basic_info(self):
        """专门负责检查数据的逻辑（仅成员模式）"""
        if self.basic_form is None:
            return
        for row in range(self.basic_form.rowCount()):
            item = self.basic_form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if item and item.widget() and not item.widget().text():
                QTimer.singleShot(100, lambda: self._show_basic_info_error())
                break

    def _show_basic_info_error(self):
        QMessageBox.critical(self, "错误", "请先完善基本信息")

    def showEvent(self, event):
        """每次页面显示时都会运行"""
        super().showEvent(event)
        if self._is_initialized and self.mode == "member":
            self.check_basic_info()

    def _collect_template_data_from_form(self) -> dict:
        """从表单采集模板特有数据"""
        data: dict[str, str] = {}
        for key, widget in self.field_widgets.items():
            field_def = self.get_field_def(key)
            data[key] = get_widget_value(widget, field_def, self.admin_config)
        return data

    def load_data(self):
        raise NotImplementedError

    def save_data(self):
        raise NotImplementedError

    def export_document(self):
        raise NotImplementedError
