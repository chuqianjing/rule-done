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
        # 动态占位符（未在 JSON 定义与映射中的字段）
        self.dynamic_field_names: set[str] = set()
        self.extra_field_widgets: dict[str, QLineEdit] = {}

        # 管理员配置缓存（用于日期格式等）
        self.admin_config = self.data_manager.get_admin_config()

        self.init_ui()
        self.load_field_definitions()
        self.build_template_form()
        self.build_dynamic_fields_from_template()
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

        # 其他（未预定义）字段
        self.extra_group = QGroupBox("其他字段（模板中存在但尚未在系统中预定义）")
        self.extra_form = QFormLayout()
        self.extra_group.setLayout(self.extra_form)
        self.main_layout.addWidget(self.extra_group)

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
        """从字段定义配置中加载模板特有字段定义和管理员字段定义"""
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

        # 加载模板特有字段定义
        self.template_field_defs = (
            config.get("template_specific_fields", {})
            .get(self.template_id, {})
            .get("fields", [])
        )

        # 加载管理员字段定义（用于只读显示）
        # 只显示"支部信息"和"公共字段"分组
        admin_groups = config.get("admin_fields", [])
        self.admin_field_defs_for_display = []
        for group in admin_groups:
            group_name = group.get("group", "")
            if group_name in ["支部信息", "公共字段"]:
                for field in group.get("fields", []):
                    self.admin_field_defs_for_display.append(field)

        # 加载学生基础信息字段定义（用于只读显示部分常用字段）
        basic_fields = config.get("basic_info_fields", [])
        # 只显示部分常用字段
        common_basic_keys = ["姓名", "性别", "出生年月"]
        self.basic_field_defs_for_display = [
            f for f in basic_fields if f.get("key") in common_basic_keys
        ]

    def build_dynamic_fields_from_template(self):
        """根据模板中实际占位符，补充展示未在 JSON 中声明的字段"""
        # 1. 获取模板中所有占位符变量名
        all_placeholders = self.template_engine.get_placeholders(self.template_id)

        # 2. 已知字段：字段定义 + 已配置映射
        template_config = self.template_manager.get_template(self.template_id)
        mapped_keys = {
            placeholder.strip("{}")
            for placeholder in template_config.get("field_mapping", {}).keys()
        }
        defined_keys = {f.get("key") for f in self.template_field_defs}

        known_keys = mapped_keys.union(defined_keys)

        # 3. 动态字段 = 模板中有、但系统未声明的占位符
        self.dynamic_field_names = {name for name in all_placeholders if name not in known_keys}

        # 4. 为这些字段创建简单的文本输入框
        #    统一归入“其他字段”分组中
        # 先清空旧的
        while self.extra_form.rowCount():
            self.extra_form.removeRow(0)
        self.extra_field_widgets.clear()

        for name in sorted(self.dynamic_field_names):
            widget = QLineEdit()
            self.extra_field_widgets[name] = widget
            self.extra_form.addRow(f"{name}：", widget)

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

        # 动态字段
        for key, widget in self.extra_field_widgets.items():
            value = str(template_data.get(key, ""))
            widget.setText(value)

    def _render_basic_info(self, admin_config: dict, student_data: dict):
        """根据字段定义动态显示只读基础信息"""
        while self.basic_form.rowCount():
            self.basic_form.removeRow(0)

        # 如果没有加载字段定义，使用空列表
        if not hasattr(self, 'admin_field_defs_for_display'):
            self.admin_field_defs_for_display = []
        if not hasattr(self, 'basic_field_defs_for_display'):
            self.basic_field_defs_for_display = []

        basic = student_data.get("basic_info", {})

        # 显示学生基础信息（部分常用字段）
        for field_def in self.basic_field_defs_for_display:
            key = field_def.get("key")
            display = field_def.get("display", {})
            label_text = display.get("label", key)
            value = str(basic.get(key, ""))

            label = QLabel(value)
            label.setStyleSheet("color: #555;")
            self.basic_form.addRow(f"{label_text}：", label)

        # 显示管理员配置（支部信息和公共字段）
        for field_def in self.admin_field_defs_for_display:
            path = field_def.get("path", "")
            display = field_def.get("display", {})
            label_text = display.get("label", field_def.get("key", ""))

            # 根据 path 从嵌套结构中获取值
            value = self._get_value_by_path(admin_config, path)

            label = QLabel(str(value))
            label.setStyleSheet("color: #555;")
            self.basic_form.addRow(f"{label_text}：", label)

    def _get_value_by_path(self, data: dict, path: str) -> str:
        """根据路径从嵌套字典中获取值"""
        if not path:
            return ""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, {})
            else:
                return ""
        return str(value) if isinstance(value, (str, int, float)) else ""

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

        # 动态字段
        for key, widget in self.extra_field_widgets.items():
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


