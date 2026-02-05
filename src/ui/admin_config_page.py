#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
管理员配置页面
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
        try:
            config = load_fields_definition()
        except FileNotFoundError:
            QMessageBox.critical(self, "错误", "缺少字段定义文件：resources/fields_definition.json")
            return
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
                widget = create_widget(field_def)
                self.field_widgets[key] = widget
                if path:
                    self.path_to_widget[path] = widget

                group_form.addRow(f"{label_text}：", widget)

            group_box.setLayout(group_form)
            self.form_layout.addWidget(group_box)

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
            export_config.pop('imported_at', None)
            export_config.pop('import_source', None)
            
            # 添加导出元信息
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
            imported_config['imported_at'] = datetime.now().isoformat()
            imported_config['import_source'] = file_path
            imported_config.pop('exported_at', None)
            imported_config.pop('export_version', None)
            
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
