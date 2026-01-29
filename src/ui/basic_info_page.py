#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基本信息页面
"""

from pathlib import Path
import json

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QHBoxLayout,
    QMessageBox,
    QDateEdit,
    QFileDialog,
)
from PyQt6.QtCore import QDate, pyqtSignal

from src.business.data_manager import DataManager
from src.business.permission_controller import PermissionController
from src.data.config_manager import ConfigManager


class BasicInfoPage(QWidget):
    """基本信息页面类"""

    # 进入模板列表/填写的信号，由 MainWindow 连接
    go_to_template_list = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.data_manager = DataManager()
        self.permission_controller = PermissionController()
        self.config_manager = ConfigManager()

        # 缓存字段定义与控件
        self.basic_field_defs: list[dict] = []
        self.field_widgets: dict[str, QLineEdit | QComboBox | QDateEdit] = {}

        # 管理员配置缓存（用于日期格式等）
        self.admin_config = self.data_manager.get_admin_config()

        self.init_ui()
        self.load_field_definitions()
        self.build_student_form()
        self.load_data()

    def init_ui(self):
        """初始化 UI"""
        self.main_layout = QVBoxLayout()

        # 标题
        title = QLabel("基本信息填写")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.main_layout.addWidget(title)

        # 管理员配置字段（只读）
        self.admin_group = QGroupBox("本支部公共信息（管理员配置，只读）")
        self.admin_form = QFormLayout()
        self.admin_group.setLayout(self.admin_form)
        self.main_layout.addWidget(self.admin_group)

        # 学生填写字段（可编辑）
        self.student_group = QGroupBox("个人基本信息（请如实填写）")
        self.student_form = QFormLayout()
        self.student_group.setLayout(self.student_form)
        self.main_layout.addWidget(self.student_group)

        # 按钮区域
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_data)
        btn_layout.addWidget(save_btn)

        import_config_btn = QPushButton("导入支部配置")
        import_config_btn.clicked.connect(self.import_admin_config)
        btn_layout.addWidget(import_config_btn)

        goto_tpl_btn = QPushButton("进入模板填写")
        goto_tpl_btn.clicked.connect(self.go_to_template_list.emit)
        btn_layout.addWidget(goto_tpl_btn)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)

    def load_field_definitions(self):
        """加载字段定义（来自 resources/fields_definition.json）"""
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

        # 加载学生基础信息字段定义
        self.basic_field_defs = sorted(
            config.get("basic_info_fields", []),
            key=lambda x: x.get("display", {}).get("order", 0),
        )

        # 加载管理员字段定义（用于只读显示）
        admin_groups = sorted(
            config.get("admin_fields", []),
            key=lambda x: x.get("group_order", 0),
        )
        # 展平所有管理员字段，排除"系统设置"分组（不显示给学生）
        self.admin_field_defs = []
        for group in admin_groups:
            if group.get("group", "") != "系统设置":
                for field in group.get("fields", []):
                    self.admin_field_defs.append(field)

    def build_student_form(self):
        """根据字段定义动态生成学生填写表单"""
        # 清空旧表单
        while self.student_form.rowCount():
            self.student_form.removeRow(0)
        self.field_widgets.clear()

        for field_def in self.basic_field_defs:
            key = field_def.get("key")
            display = field_def.get("display", {})
            label_text = display.get("label", key)
            field_type = field_def.get("type")

            if field_type == "select":
                widget = QComboBox()
                for option in field_def.get("options", []):
                    widget.addItem(option)
            elif field_type == "date":
                widget = QDateEdit()
                widget.setCalendarPopup(True)
                # 解析管理员配置的日期格式，转为 Qt 格式
                fmt_cfg = (
                    self.admin_config.get("date_format", {}).get("format")
                    or field_def.get("format", "YYYY年MM月DD日")
                )
                qt_format = "yyyy-MM-dd"
                if fmt_cfg == "YYYY年MM月DD日":
                    qt_format = "yyyy年MM月dd日"
                elif fmt_cfg == "YYYY年MM月":
                    qt_format = "yyyy年MM月"
                widget.setDisplayFormat(qt_format)
                widget.setDate(QDate.currentDate())
            else:
                widget = QLineEdit()
                placeholder = display.get("placeholder")
                if placeholder:
                    widget.setPlaceholderText(placeholder)

            self.field_widgets[key] = widget
            self.student_form.addRow(f"{label_text}：", widget)

    def load_data(self):
        """加载管理员配置和学生数据"""
        # 管理员配置（只读显示）
        admin_config = self.data_manager.get_admin_config()
        self._render_admin_config(admin_config)

        # 学生数据
        student_data = self.data_manager.get_student_data()
        basic_info = student_data.get("basic_info", {})

        for key, widget in self.field_widgets.items():
            value = str(basic_info.get(key, ""))
            if isinstance(widget, QComboBox):
                index = widget.findText(value)
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif isinstance(widget, QDateEdit):
                # 尝试根据显示格式解析字符串到 QDate
                if value:
                    fmt_cfg = (
                        self.admin_config.get("date_format", {}).get("format")
                        or next((f.get("format") for f in self.basic_field_defs if f.get("key") == key), "YYYY年MM月DD日")
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

    def _render_admin_config(self, config: dict):
        """根据字段定义动态渲染管理员配置为只读信息"""
        # 清空旧行
        while self.admin_form.rowCount():
            self.admin_form.removeRow(0)

        # 如果没有加载字段定义，使用空列表
        if not hasattr(self, 'admin_field_defs'):
            self.admin_field_defs = []

        # 按 order 排序字段
        sorted_fields = sorted(
            self.admin_field_defs,
            key=lambda x: x.get("display", {}).get("order", 0),
        )

        # 根据字段定义动态渲染
        for field_def in sorted_fields:
            path = field_def.get("path", "")
            display = field_def.get("display", {})
            label_text = display.get("label", field_def.get("key", ""))

            # 根据 path 从嵌套结构中获取值
            value = self._get_value_by_path(config, path)

            label = QLabel(str(value))
            label.setStyleSheet("color: #555;")
            self.admin_form.addRow(f"{label_text}：", label)

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

    def _collect_basic_info_from_form(self) -> dict:
        """从表单采集学生基础信息"""
        basic_info: dict[str, str] = {}
        for key, widget in self.field_widgets.items():
            if isinstance(widget, QComboBox):
                basic_info[key] = widget.currentText().strip()
            elif isinstance(widget, QDateEdit):
                # 使用当前显示格式导出为字符串
                fmt_cfg = (
                    self.admin_config.get("date_format", {}).get("format")
                    or next((f.get("format") for f in self.basic_field_defs if f.get("key") == key), "YYYY年MM月DD日")
                )
                if fmt_cfg == "YYYY年MM月DD日":
                    qt_format = "yyyy年MM月dd日"
                elif fmt_cfg == "YYYY年MM月":
                    qt_format = "yyyy年MM月"
                else:
                    qt_format = "yyyy-MM-dd"
                basic_info[key] = widget.date().toString(qt_format)
            elif isinstance(widget, QLineEdit):
                basic_info[key] = widget.text().strip()
        return basic_info

    def save_data(self):
        """保存数据"""
        try:
            student_data = self.data_manager.get_student_data()
            student_data["basic_info"] = self._collect_basic_info_from_form()
            self.data_manager.save_student_data(student_data)
            QMessageBox.information(self, "提示", "基本信息已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def import_admin_config(self):
        """学生端导入支部管理员配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入支部配置",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # 读取配置文件
            imported_config = self.config_manager.json_storage.read_json(file_path)
            
            # 验证配置格式
            required_keys = ['branch_info', 'party_committee', 'common_fields']
            if not all(key in imported_config for key in required_keys):
                QMessageBox.warning(self, "警告", "配置文件格式不正确，缺少必需的字段。")
                return
            
            # 备份当前配置
            try:
                backup_path = self.config_manager.json_storage.backup_file(
                    str(self.config_manager.config_path)
                )
            except Exception:
                pass  # 备份失败不影响导入
            
            # 学生端导入时自动锁定配置
            imported_config['locked'] = True
            imported_config['configured'] = True
            from datetime import datetime
            imported_config['imported_at'] = datetime.now().isoformat()
            
            # 保存配置
            # 学生端通常处于 locked=true，需要强制写入
            if hasattr(self.config_manager, "save_config_force"):
                self.config_manager.save_config_force(imported_config)
            else:
                self.config_manager.save_config(imported_config)
            
            # 更新缓存并刷新显示
            self.admin_config = self.config_manager.load_config()
            self.load_data()
            
            QMessageBox.information(
                self, 
                "提示", 
                "支部配置已导入并锁定。\n\n配置信息已自动更新显示。"
            )
        except FileNotFoundError:
            QMessageBox.warning(self, "错误", "文件不存在。")
        except ValueError as e:
            QMessageBox.warning(self, "错误", f"配置文件格式错误：{e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

