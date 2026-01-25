#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
管理员配置页面
"""

from pathlib import Path
import json

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFormLayout,
    QLineEdit,
    QGroupBox,
    QMessageBox,
    QDateEdit,
    QComboBox,
    QTextEdit,
    QHBoxLayout,
    QFileDialog,
)
from PyQt6.QtCore import QDate

from src.data.config_manager import ConfigManager


class AdminConfigPage(QWidget):
    """管理员配置页面类"""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()

        # 字段定义和控件缓存
        self.admin_field_groups: list[dict] = []
        self.field_widgets: dict[str, QLineEdit | QComboBox | QDateEdit | QTextEdit] = {}
        # path -> widget 的映射，用于快速查找
        self.path_to_widget: dict[str, QLineEdit | QComboBox | QDateEdit | QTextEdit] = {}

        self.init_ui()
        self.load_field_definitions()
        self.build_admin_form()
        self.load_config()

    def init_ui(self):
        """初始化 UI"""
        self.main_layout = QVBoxLayout()

        # 标题
        title = QLabel("管理员配置")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.main_layout.addWidget(title)

        # 表单区域（动态生成）
        self.form_container = QWidget()
        self.form_layout = QVBoxLayout()
        self.form_container.setLayout(self.form_layout)
        self.main_layout.addWidget(self.form_container)

        # 按钮区域
        btn_layout = QVBoxLayout()
        
        # 第一行：保存和锁定按钮
        save_lock_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_config)
        save_lock_layout.addWidget(save_btn)

        lock_btn = QPushButton("保存并锁定（学生端只读）")
        lock_btn.clicked.connect(self.lock_config)
        save_lock_layout.addWidget(lock_btn)
        btn_layout.addLayout(save_lock_layout)
        
        # 第二行：导入和导出按钮
        import_export_layout = QHBoxLayout()
        export_btn = QPushButton("导出配置")
        export_btn.clicked.connect(self.export_config)
        import_export_layout.addWidget(export_btn)

        import_btn = QPushButton("导入配置")
        import_btn.clicked.connect(self.import_config)
        import_export_layout.addWidget(import_btn)
        btn_layout.addLayout(import_export_layout)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)

    def load_field_definitions(self):
        """从 fields_definition.json 加载管理员字段定义"""
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

        # 加载管理员字段分组
        self.admin_field_groups = sorted(
            config.get("admin_fields", []),
            key=lambda x: x.get("group_order", 0),
        )

    def build_admin_form(self):
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
                widget = self._create_widget_by_type(field_def)
                self.field_widgets[key] = widget
                if path:
                    self.path_to_widget[path] = widget

                group_form.addRow(f"{label_text}：", widget)

            group_box.setLayout(group_form)
            self.form_layout.addWidget(group_box)

    def _create_widget_by_type(self, field_def: dict):
        """根据字段定义创建对应的控件"""
        field_type = field_def.get("type", "text")
        display = field_def.get("display", {})

        if field_type == "select":
            widget = QComboBox()
            for option in field_def.get("options", []):
                widget.addItem(option)
        elif field_type == "date":
            widget = QDateEdit()
            widget.setCalendarPopup(True)
            fmt_cfg = field_def.get("format", "YYYY年MM月DD日")
            qt_format = "yyyy年MM月dd日"
            if fmt_cfg == "YYYY年MM月":
                qt_format = "yyyy年MM月"
            widget.setDisplayFormat(qt_format)
            widget.setDate(QDate.currentDate())
        elif field_type == "textarea":
            widget = QTextEdit()
        else:  # text
            widget = QLineEdit()
            placeholder = display.get("placeholder")
            if placeholder:
                widget.setPlaceholderText(placeholder)

        return widget

    def load_config(self):
        """加载配置并填充到表单"""
        config = self.config_manager.load_config()

        # 根据 path 从嵌套结构中读取值并填充到控件
        for path, widget in self.path_to_widget.items():
            value = self._get_value_by_path(config, path)
            self._set_widget_value(widget, value)

        # 处理锁定状态
        if config.get("locked", False):
            self._set_locked_state(True)

    def _get_value_by_path(self, data: dict, path: str) -> str:
        """根据路径从嵌套字典中获取值"""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, {})
            else:
                return ""
        return str(value) if isinstance(value, (str, int, float)) else ""

    def _set_widget_value(self, widget, value: str):
        """设置控件值"""
        if isinstance(widget, QLineEdit):
            widget.setText(value)
        elif isinstance(widget, QComboBox):
            index = widget.findText(value)
            if index >= 0:
                widget.setCurrentIndex(index)
        elif isinstance(widget, QDateEdit):
            if value:
                # 尝试解析日期字符串
                qt_format = "yyyy年MM月dd日"
                if "年" in value and "月" in value and "日" not in value:
                    qt_format = "yyyy年MM月"
                dt = QDate.fromString(value, qt_format)
                if dt.isValid():
                    widget.setDate(dt)
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(value)

    def _collect_config_from_form(self) -> dict:
        """从表单收集配置数据"""
        config = self.config_manager.load_config()

        # 确保基础结构存在
        for group_def in self.admin_field_groups:
            for field_def in group_def.get("fields", []):
                path = field_def.get("path", "")
                if not path:
                    continue

                # 确保路径中的所有嵌套字典存在
                keys = path.split(".")
                current = config
                for i, key in enumerate(keys[:-1]):
                    if key not in current:
                        current[key] = {}
                    current = current[key]

                # 从控件获取值并设置到配置中
                widget = self.path_to_widget.get(path)
                if widget:
                    value = self._get_widget_value(widget)
                    current[keys[-1]] = value

        config["configured"] = True
        return config

    def _get_widget_value(self, widget) -> str:
        """从控件获取值"""
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        elif isinstance(widget, QComboBox):
            return widget.currentText().strip()
        elif isinstance(widget, QDateEdit):
            # 根据显示格式转换为字符串
            qt_format = widget.displayFormat()
            return widget.date().toString(qt_format)
        elif isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        return ""

    def _set_locked_state(self, locked: bool):
        """根据锁定状态更新表单可编辑性"""
        for widget in self.field_widgets.values():
            if isinstance(widget, (QLineEdit, QComboBox, QDateEdit, QTextEdit)):
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

    def lock_config(self):
        """保存并锁定配置"""
        try:
            config = self._collect_config_from_form()
            # 先保存最新配置
            self.config_manager.save_config(config)
            # 再锁定
            self.config_manager.lock_config()
            self._set_locked_state(True)
            QMessageBox.information(
                self, "提示", "配置已保存并锁定，学生端将以只读方式使用这些信息。"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"锁定配置失败：{e}")

    def export_config(self):
        """导出配置为 JSON 文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出管理员配置",
            "admin_config.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            config = self.config_manager.load_config()
            
            # 创建导出配置（移除敏感信息和本地状态）
            export_config = config.copy()
            # 保留配置数据，但移除锁定状态等本地设置
            export_config.pop('locked', None)
            export_config.pop('locked_at', None)
            export_config.pop('unlocked_at', None)
            export_config.pop('synced_at', None)
            export_config.pop('sync_source', None)
            
            # 添加导出元信息
            from datetime import datetime
            export_config['exported_at'] = datetime.now().isoformat()
            export_config['export_version'] = export_config.get('version', '1.0')
            
            # 写入文件
            self.config_manager.json_storage.write_json(file_path, export_config)
            QMessageBox.information(self, "提示", f"配置已导出到：\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败：{e}")

    def import_config(self):
        """从 JSON 文件导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入管理员配置",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # 读取配置文件
            imported_config = self.config_manager.json_storage.read_json(file_path)
            
            # 验证配置格式
            if not self._validate_imported_config(imported_config):
                QMessageBox.warning(self, "警告", "配置文件格式不正确，缺少必需的字段。")
                return
            
            # 备份当前配置
            backup_path = None
            try:
                backup_path = self.config_manager.json_storage.backup_file(
                    str(self.config_manager.config_path)
                )
            except Exception:
                pass  # 备份失败不影响导入
            
            # 询问用户是否继续导入
            backup_msg = f"\n\n已备份当前配置到：{backup_path}" if backup_path else ""
            reply = QMessageBox.question(
                self,
                "确认导入",
                f"即将导入配置文件：{file_path}{backup_msg}\n\n是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # 保留本地设置（锁定状态等）
            current_config = self.config_manager.load_config()
            imported_config['locked'] = current_config.get('locked', False)
            imported_config['configured'] = True
            
            # 保存导入的配置
            self.config_manager.save_config(imported_config)
            
            # 重新加载到表单
            self.load_config()
            
            QMessageBox.information(self, "提示", "配置已导入成功！")
        except FileNotFoundError:
            QMessageBox.warning(self, "错误", "文件不存在。")
        except ValueError as e:
            QMessageBox.warning(self, "错误", f"配置文件格式错误：{e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def _validate_imported_config(self, config: dict) -> bool:
        """验证导入的配置格式"""
        # 检查必需的顶层字段
        required_keys = ['branch_info', 'party_committee', 'common_fields']
        return all(key in config for key in required_keys)
