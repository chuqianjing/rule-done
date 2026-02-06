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
)
from PyQt6.QtCore import QTimer

from src.business.data_manager import DataManager
from src.business.template_engine import TemplateEngine
from src.data.template_manager import TemplateManager
from src.utils.field_utils import create_widget, set_widget_value, get_widget_value
from src.utils.data_paths import get_value_by_path


class TemplatePage(QWidget):
    """
    单个模板填写页面

    当前主要面向 template_001（入党申请书），后续可以复用到其他模板。
    """

    def __init__(self, template_id: str = "template_001", parent=None):
        super().__init__(parent)

        self._is_initialized = False

        self.template_id = template_id
        self.data_manager = DataManager()
        self.template_engine = TemplateEngine()
        self.template_manager = TemplateManager()

        self.common_template_fields: list[dict] = []
        self.field_widgets: dict[str, QWidget] = {}

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
        """从字段定义配置中加载通用模板字段定义和管理员字段定义"""
        from src.utils.fields_loader import load_fields_definition

        try:
            config = load_fields_definition()
        except FileNotFoundError:
            QMessageBox.critical(self, "错误", "缺少字段定义文件：resources/fields_definition.json")
            return
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取字段定义失败：{e}")
            return

        # 加载通用模板字段定义（不再使用模板特定字段）
        self.common_template_fields = config.get("common_template_fields", [])

        # 加载管理员字段定义（用于只读显示）
        admin_groups = config.get("admin_fields", [])
        self.admin_field_defs_for_display = []
        for group in admin_groups:
            for field in group.get("fields", []):
                self.admin_field_defs_for_display.append(field)

        # 加载学生基础信息字段定义（用于只读显示部分常用字段）
        basic_fields = config.get("basic_info_fields", [])
        self.basic_field_defs_for_display = basic_fields

    def build_template_form(self):
        """构建模板字段表单（基于模板文件中的占位符和通用字段库）"""
        # 清空旧表单
        while self.template_form.rowCount():
            self.template_form.removeRow(0)
        self.field_widgets.clear()

        # 从模板文件中获取所有占位符
        self.placeholders = self.template_engine.get_placeholders(self.template_id)
        
        # 获取已知字段（基础信息、管理员配置），这些字段会在基础信息区域显示
        known_fields = set()
        # 基础信息字段
        for field_def in self.basic_field_defs_for_display:
            known_fields.add(field_def.get("key"))
        # 管理员字段（通过 path 的最后一部分）
        for field_def in self.admin_field_defs_for_display:
            known_fields.add(field_def.get("key"))
            '''
            path = field_def.get("path", "")
            if path:
                path_parts = path.split(".")
                last_part = path_parts[-1] if path_parts else ""
                if last_part:
                    known_fields.add(last_part)
            '''

        # 为每个占位符创建表单字段（排除已知字段，它们会在基础信息区域显示）
        self.template_specific_placeholders = sorted(self.placeholders - known_fields)

        # 按顺序构建表单（优先使用通用字段库中的定义）
        field_defs_map = {f.get("key"): f for f in self.common_template_fields}

        for placeholder in self.template_specific_placeholders:
            field_def = field_defs_map.get(placeholder)
            if field_def is None:
                # 未在通用字段库中定义的字段（使用默认定义）
                field_def = {
                    "key": placeholder,
                    "type": "text",
                    "required": False,
                    "display": {"label": placeholder, "order": 999},
                }
            self._add_field_to_form(field_def)
    
    def _add_field_to_form(self, field_def: dict):
        """添加字段到表单"""
        key = field_def.get("key")
        label_text = field_def.get("display", {}).get("label", key)
        widget = create_widget(field_def, self.admin_config)

        self.field_widgets[key] = widget
        self.template_form.addRow(f"{label_text}：", widget)

    def load_data(self):
        """加载基础信息和模板数据"""
        # 基础信息引用
        admin_config = self.data_manager.get_admin_config()
        student_data = self.data_manager.get_student_data()

        # 渲染基础信息（部分常用字段）
        self._render_basic_info(admin_config, student_data)

        # 模板字段
        template_data = student_data.get("template_data", {}).get(self.template_id, {})
        for key, widget in self.field_widgets.items():
            value = template_data.get(key, "")
            # 查找字段定义（如果存在），便于日期等格式的处理
            field_def = next((f for f in self.common_template_fields if f.get("key") == key), None)
            set_widget_value(widget, value, field_def, self.admin_config)

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

        # 显示学生基础信息
        for field_def in self.basic_field_defs_for_display:
            key = field_def.get("key")
            display = field_def.get("display", {})
            label_text = display.get("label", key)
            value = str(basic.get(key, ""))

            label = QLabel(value)
            label.setStyleSheet("color: #555;")
            if key in self.placeholders:
                self.basic_form.addRow(f"{label_text}：", label)

        # 显示管理员配置
        for field_def in self.admin_field_defs_for_display:
            key = field_def.get("key")
            path = field_def.get("path", "")
            display = field_def.get("display", {})
            label_text = display.get("label", field_def.get("key", ""))

            # 根据 path 从嵌套结构中获取值
            value = get_value_by_path(admin_config, path, "")

            label = QLabel(str(value))
            label.setStyleSheet("color: #555;")
            if key in self.placeholders:
                self.basic_form.addRow(f"{label_text}：", label)
    
    def showEvent(self, event):
        """每次页面显示时都会运行"""
        super().showEvent(event) # 必须调用父类实现
        if self._is_initialized:
            self.check_basic_info()

    def check_basic_info(self):
        """专门负责检查数据的逻辑"""
        for row in range(self.basic_form.rowCount()):
            item = self.basic_form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if item and not item.widget().text():
                QTimer.singleShot(100, lambda: QMessageBox.critical(self, "错误", "请先完善基本信息"))
                break

    def _collect_template_data_from_form(self) -> dict:
        """从表单采集模板特有数据"""
        data: dict[str, str] = {}
        for key, widget in self.field_widgets.items():
            field_def = next((f for f in self.common_template_fields if f.get("key") == key), None)
            data[key] = get_widget_value(widget, field_def, self.admin_config)

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


