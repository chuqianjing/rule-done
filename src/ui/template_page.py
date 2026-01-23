#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板填写页面（示例：入党申请书）
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QMessageBox,
    QHBoxLayout,
    QDateEdit,
)
from PyQt6.QtCore import QDate

from src.business.data_manager import DataManager
from src.business.template_engine import TemplateEngine
from src.data.template_manager import TemplateManager


class TemplatePage(QWidget):
    """
    单个模板填写页面

    当前主要面向 template_001（入党申请书），后续可以复用到其他模板。
    """

    def __init__(self, template_id: str = "template_001", parent=None):
        super().__init__(parent)

        self.template_id = template_id
        self.data_manager = DataManager()
        self.template_engine = TemplateEngine()
        self.template_manager = TemplateManager()

        self.template_field_defs: list[dict] = []
        self.field_widgets: dict[str, QLineEdit | QTextEdit | QDateEdit] = {}

        # 管理员配置缓存（用于日期格式等）
        self.admin_config = self.data_manager.get_admin_config()

        self.init_ui()
        self.load_field_definitions()
        self.build_template_form()
        self.load_data()

    def init_ui(self):
        """初始化 UI 布局"""
        self.main_layout = QVBoxLayout()

        template_info = self.template_manager.get_template(self.template_id)
        title_text = template_info.get("name", "模板填写")

        title = QLabel(f"模板填写：{title_text}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.main_layout.addWidget(title)

        # 基础信息引用（只读）
        self.basic_group = QGroupBox("基础信息（只读，来自首页和管理员配置）")
        self.basic_form = QFormLayout()
        self.basic_group.setLayout(self.basic_form)
        self.main_layout.addWidget(self.basic_group)

        # 模板特有字段
        self.template_group = QGroupBox("本模板特有字段")
        self.template_form = QFormLayout()
        self.template_group.setLayout(self.template_form)
        self.main_layout.addWidget(self.template_group)

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_data)
        btn_layout.addWidget(save_btn)

        export_btn = QPushButton("导出 Word")
        export_btn.clicked.connect(self.export_document)
        btn_layout.addWidget(export_btn)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)

    def load_field_definitions(self):
        """从字段定义配置中加载模板特有字段定义"""
        from pathlib import Path
        import json

        fields_path = Path("resources/fields_definition.json")
        if not fields_path.exists():
            QMessageBox.critical(self, "错误", "缺少字段定义文件：resources/fields_definition.json")
            return

        try:
            with open(fields_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取字段定义失败：{e}")
            return

        self.template_field_defs = (
            config.get("template_specific_fields", {})
            .get(self.template_id, {})
            .get("fields", [])
        )

    def build_template_form(self):
        """构建模板特有字段表单"""
        # 清空旧表单
        while self.template_form.rowCount():
            self.template_form.removeRow(0)
        self.field_widgets.clear()

        for field_def in self.template_field_defs:
            key = field_def.get("key")
            label_text = field_def.get("display", {}).get("label", key)
            field_type = field_def.get("type")

            if field_type == "textarea":
                widget = QTextEdit()
            elif field_type == "date":
                widget = QDateEdit()
                widget.setCalendarPopup(True)
                fmt_cfg = (
                    self.admin_config.get("date_format", {}).get("format")
                    or field_def.get("format", "YYYY年MM月DD日")
                )
                qt_format = "yyyy年MM月dd日"
                if fmt_cfg == "YYYY年MM月":
                    qt_format = "yyyy年MM月"
                widget.setDisplayFormat(qt_format)
                widget.setDate(QDate.currentDate())
            else:
                widget = QLineEdit()

            self.field_widgets[key] = widget
            self.template_form.addRow(f"{label_text}：", widget)

    def load_data(self):
        """加载基础信息和模板数据"""
        # 基础信息引用
        admin_config = self.data_manager.get_admin_config()
        student_data = self.data_manager.get_student_data()

        # 渲染基础信息（部分常用字段）
        self._render_basic_info(admin_config, student_data)

        # 模板特有字段
        template_data = student_data.get("template_data", {}).get(self.template_id, {})
        for key, widget in self.field_widgets.items():
            value = str(template_data.get(key, ""))
            if isinstance(widget, QTextEdit):
                widget.setPlainText(value)
            elif isinstance(widget, QDateEdit):
                if value:
                    fmt_cfg = (
                        self.admin_config.get("date_format", {}).get("format")
                        or next((f.get("format") for f in self.template_field_defs if f.get("key") == key), "YYYY年MM月DD日")
                    )
                    if fmt_cfg == "YYYY年MM月DD日":
                        qt_format = "yyyy年MM月dd日"
                    elif fmt_cfg == "YYYY年MM月":
                        qt_format = "yyyy年MM月"
                    else:
                        qt_format = "yyyy-MM-dd"
                    dt = QDate.fromString(value, qt_format)
                    if dt.isValid():
                        widget.setDate(dt)
            elif isinstance(widget, QLineEdit):
                widget.setText(value)

    def _render_basic_info(self, admin_config: dict, student_data: dict):
        """显示只读基础信息"""
        while self.basic_form.rowCount():
            self.basic_form.removeRow(0)

        branch = admin_config.get("branch_info", {})
        common = admin_config.get("common_fields", {})
        basic = student_data.get("basic_info", {})

        items = [
            ("姓名", basic.get("姓名", "")),
            ("性别", basic.get("性别", "")),
            ("出生年月", basic.get("出生年月", "")),
            ("支部名称", branch.get("branch_name", "")),
            ("学校名称", common.get("school_name", "")),
            ("学院名称", common.get("college_name", "")),
        ]

        for label_text, value in items:
            label = QLabel(str(value))
            label.setStyleSheet("color: #555;")
            self.basic_form.addRow(f"{label_text}：", label)

    def _collect_template_data_from_form(self) -> dict:
        """从表单采集模板特有数据"""
        data: dict[str, str] = {}
        for key, widget in self.field_widgets.items():
            if isinstance(widget, QTextEdit):
                data[key] = widget.toPlainText().strip()
            elif isinstance(widget, QDateEdit):
                fmt_cfg = (
                    self.admin_config.get("date_format", {}).get("format")
                    or next((f.get("format") for f in self.template_field_defs if f.get("key") == key), "YYYY年MM月DD日")
                )
                if fmt_cfg == "YYYY年MM月DD日":
                    qt_format = "yyyy年MM月dd日"
                elif fmt_cfg == "YYYY年MM月":
                    qt_format = "yyyy年MM月"
                else:
                    qt_format = "yyyy-MM-dd"
                data[key] = widget.date().toString(qt_format)
            elif isinstance(widget, QLineEdit):
                data[key] = widget.text().strip()
        return data

    def save_data(self):
        """保存模板特有数据"""
        try:
            student_data = self.data_manager.get_student_data()
            if "template_data" not in student_data:
                student_data["template_data"] = {}
            if self.template_id not in student_data["template_data"]:
                student_data["template_data"][self.template_id] = {}

            student_data["template_data"][self.template_id].update(
                self._collect_template_data_from_form()
            )

            self.data_manager.save_student_data(student_data)
            QMessageBox.information(self, "提示", "模板数据已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def export_document(self):
        """导出 Word 文档"""
        from pathlib import Path
        import datetime

        try:
            # 先保存数据，确保使用的是最新内容
            self.save_data()

            admin_config = self.data_manager.get_admin_config()
            student_data = self.data_manager.get_student_data()
            basic = student_data.get("basic_info", {})

            name = basic.get("姓名", "未命名")
            template_info = self.template_manager.get_template(self.template_id)
            template_name = template_info.get("name", "文档")

            date_str = datetime.datetime.now().strftime("%Y%m%d")
            export_dir = Path(admin_config.get("system_settings", {}).get("export_path", "./exports"))
            export_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{template_name}_{name}_{date_str}.docx"
            output_path = str(export_dir / filename)

            self.template_engine.generate_document(self.template_id, output_path)
            QMessageBox.information(self, "提示", f"文档已导出：\n{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败：{e}")


