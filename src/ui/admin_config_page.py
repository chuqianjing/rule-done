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
)

from src.data.config_manager import ConfigManager


class AdminConfigPage(QWidget):
    """管理员配置页面类"""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()

        # 表单控件缓存
        self.branch_name_edit: QLineEdit | None = None
        self.branch_code_edit: QLineEdit | None = None
        self.branch_secretary_edit: QLineEdit | None = None
        self.committee_name_edit: QLineEdit | None = None
        self.committee_secretary_edit: QLineEdit | None = None
        self.school_name_edit: QLineEdit | None = None
        self.college_name_edit: QLineEdit | None = None
        self.export_path_edit: QLineEdit | None = None

        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()

        # 标题
        title = QLabel("管理员配置")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # 支部信息
        branch_group = QGroupBox("支部信息")
        branch_form = QFormLayout()
        self.branch_name_edit = QLineEdit()
        self.branch_code_edit = QLineEdit()
        self.branch_secretary_edit = QLineEdit()
        branch_form.addRow("支部名称：", self.branch_name_edit)
        branch_form.addRow("支部代码：", self.branch_code_edit)
        branch_form.addRow("支部书记：", self.branch_secretary_edit)
        branch_group.setLayout(branch_form)
        layout.addWidget(branch_group)

        # 上级党委信息
        committee_group = QGroupBox("上级党委信息")
        committee_form = QFormLayout()
        self.committee_name_edit = QLineEdit()
        self.committee_secretary_edit = QLineEdit()
        committee_form.addRow("党委名称：", self.committee_name_edit)
        committee_form.addRow("党委书记：", self.committee_secretary_edit)
        committee_group.setLayout(committee_form)
        layout.addWidget(committee_group)

        # 公共字段
        common_group = QGroupBox("公共字段")
        common_form = QFormLayout()
        self.school_name_edit = QLineEdit()
        self.college_name_edit = QLineEdit()
        common_form.addRow("学校名称：", self.school_name_edit)
        common_form.addRow("学院名称：", self.college_name_edit)
        common_group.setLayout(common_form)
        layout.addWidget(common_group)

        # 系统设置
        system_group = QGroupBox("系统设置")
        system_form = QFormLayout()
        self.export_path_edit = QLineEdit("./exports")
        system_form.addRow("默认导出路径：", self.export_path_edit)
        system_group.setLayout(system_form)
        layout.addWidget(system_group)

        # 按钮区域
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_config)
        layout.addWidget(save_btn)

        lock_btn = QPushButton("保存并锁定（学生端只读）")
        lock_btn.clicked.connect(self.lock_config)
        layout.addWidget(lock_btn)

        self.setLayout(layout)

    def load_config(self):
        """加载配置并填充到表单"""
        config = self.config_manager.load_config()

        branch = config.get("branch_info", {})
        secretary = branch.get("secretary", {})
        committee = config.get("party_committee", {})
        committee_secretary = committee.get("secretary", {})
        common = config.get("common_fields", {})
        system_settings = config.get("system_settings", {})

        if self.branch_name_edit is not None:
            self.branch_name_edit.setText(branch.get("branch_name", ""))
        if self.branch_code_edit is not None:
            self.branch_code_edit.setText(branch.get("branch_code", ""))
        if self.branch_secretary_edit is not None:
            self.branch_secretary_edit.setText(secretary.get("name", ""))

        if self.committee_name_edit is not None:
            self.committee_name_edit.setText(committee.get("name", ""))
        if self.committee_secretary_edit is not None:
            self.committee_secretary_edit.setText(committee_secretary.get("name", ""))

        if self.school_name_edit is not None:
            self.school_name_edit.setText(common.get("school_name", ""))
        if self.college_name_edit is not None:
            self.college_name_edit.setText(common.get("college_name", ""))

        if self.export_path_edit is not None:
            self.export_path_edit.setText(system_settings.get("export_path", "./exports"))

        if config.get("locked", False):
            self._set_locked_state(True)

    def _collect_config_from_form(self) -> dict:
        """从表单收集配置数据"""
        config = self.config_manager.load_config()

        # 确保基础结构存在
        config.setdefault("branch_info", {})
        config.setdefault("party_committee", {})
        config.setdefault("common_fields", {})
        config.setdefault("system_settings", {})
        config.setdefault("branch_info", {}).setdefault("secretary", {})
        config.setdefault("party_committee", {}).setdefault("secretary", {})

        branch = config["branch_info"]
        secretary = branch["secretary"]
        committee = config["party_committee"]
        committee_secretary = committee["secretary"]
        common = config["common_fields"]
        system_settings = config["system_settings"]

        if self.branch_name_edit is not None:
            branch["branch_name"] = self.branch_name_edit.text().strip()
        if self.branch_code_edit is not None:
            branch["branch_code"] = self.branch_code_edit.text().strip()
        if self.branch_secretary_edit is not None:
            secretary["name"] = self.branch_secretary_edit.text().strip()

        if self.committee_name_edit is not None:
            committee["name"] = self.committee_name_edit.text().strip()
        if self.committee_secretary_edit is not None:
            committee_secretary["name"] = self.committee_secretary_edit.text().strip()

        if self.school_name_edit is not None:
            common["school_name"] = self.school_name_edit.text().strip()
        if self.college_name_edit is not None:
            common["college_name"] = self.college_name_edit.text().strip()

        if self.export_path_edit is not None:
            system_settings["export_path"] = self.export_path_edit.text().strip() or "./exports"

        config["configured"] = True
        return config

    def _set_locked_state(self, locked: bool):
        """根据锁定状态更新表单可编辑性"""
        for widget in [
            self.branch_name_edit,
            self.branch_code_edit,
            self.branch_secretary_edit,
            self.committee_name_edit,
            self.committee_secretary_edit,
            self.school_name_edit,
            self.college_name_edit,
            self.export_path_edit,
        ]:
            if widget is not None:
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
            QMessageBox.information(self, "提示", "配置已保存并锁定，学生端将以只读方式使用这些信息。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"锁定配置失败：{e}")

