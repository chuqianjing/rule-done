#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
成员设置页面
"""

from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QFileDialog,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from src.ui.password_dialog import (
    PasswordSetupDialog,
    PasswordRemoveDialog,
    PasswordChangeDialog,
)
from src.application.data_manager import DataManager
from src.application.permission_controller import PermissionController
from src.utils.crypto_storage import DecryptionError
from src.utils.styles import ICONS


class MemberSettingsPage(QWidget):
    """成员态系统设置页面"""

    mode_changed = Signal(str)         # 模式切换信号，通知主窗口重新加载
    before_mode_changed = Signal(str)  # 即将切换模式信号，参数为当前模式

    def __init__(self):
        super().__init__()

        self.data_manager = DataManager()
        self.permission_controller = PermissionController()

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """初始化 UI"""
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("member_settings_page")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 页面标题
        title = QLabel(f"通用设置")
        title.setObjectName("title")
        main_layout.addWidget(title)

        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(0, 0, 10, 0)

        # === 支部配置管理 ===
        config_group = QGroupBox(f"{ICONS['sync']} 支部配置管理")
        config_form = QVBoxLayout()
        config_form.setSpacing(10)
        config_form.setContentsMargins(15, 20, 15, 15)

        # 操作按钮
        config_btn_layout = QHBoxLayout()
        sync_btn = QPushButton("手动云端同步")
        sync_btn.clicked.connect(self.sync_config)
        config_btn_layout.addWidget(sync_btn)

        import_btn = QPushButton("本地文件导入")
        import_btn.setObjectName("secondary")
        import_btn.clicked.connect(self.import_config)
        config_btn_layout.addWidget(import_btn)

        config_btn_layout.addStretch()
        config_form.addLayout(config_btn_layout)

        config_info_layout = QHBoxLayout()
        # 版本
        config_info_layout.addWidget(QLabel("配置版本："))
        config_info_layout.addWidget(QLabel(self.data_manager.get_admin_config().get("version", "1.0")))
        config_info_layout.addStretch()
        # 状态
        config_info_layout.addWidget(QLabel("配置状态："))
        self.sync_status_label = QLabel("使用默认配置")
        self.sync_status_label.setStyleSheet("color: #666;")
        config_info_layout.addWidget(self.sync_status_label)
        config_info_layout.addStretch()
        # 时间
        config_info_layout.addWidget(QLabel("上次配置："))
        self.sync_time_label = QLabel("-")
        self.sync_time_label.setStyleSheet("color: #666;")
        config_info_layout.addWidget(self.sync_time_label)
        config_info_layout.addStretch()
        config_form.addLayout(config_info_layout)

        tip_info = QLabel("提示：应用启动时会自动同步配置。如需强制获取云端配置，可点击手动同步或本地导入。")
        tip_info.setStyleSheet("color: #666; font-size: 12px;")
        tip_info.setWordWrap(True)
        config_form.addWidget(tip_info)

        config_group.setLayout(config_form)
        scroll_layout.addWidget(config_group)

        # === 导出设置 ===
        export_group = QGroupBox(f"{ICONS['export']} 材料文件导出")
        export_form = QFormLayout()
        export_form.setSpacing(10)
        export_form.setContentsMargins(15, 20, 15, 15)

        # 导出路径
        path_layout = QHBoxLayout()
        self.export_path_edit = QLineEdit()
        self.export_path_edit.setPlaceholderText("默认：./exports")
        path_layout.addWidget(self.export_path_edit, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.setObjectName("secondary")
        browse_btn.clicked.connect(self.browse_and_save_export_path)
        path_layout.addWidget(browse_btn)

        export_form.addRow("导出路径：", path_layout)

        export_info = QLabel("提示：生成的材料文件将保存到此目录。")
        export_info.setStyleSheet("color: #666; font-size: 12px;")
        export_info.setWordWrap(True)
        export_form.addRow("", export_info)

        export_group.setLayout(export_form)
        scroll_layout.addWidget(export_group)

        # === 数据管理 ===
        data_group = QGroupBox(f"{ICONS['save']} 个人数据管理")
        data_form = QVBoxLayout()
        data_form.setSpacing(10)
        data_form.setContentsMargins(15, 20, 15, 15)

        data_btn_layout = QHBoxLayout()
        export_data_btn = QPushButton(f"导出数据")
        export_data_btn.setObjectName("secondary")
        export_data_btn.clicked.connect(self.export_member_info)
        data_btn_layout.addWidget(export_data_btn)

        import_data_btn = QPushButton(f"导入数据")
        import_data_btn.setObjectName("secondary")
        import_data_btn.clicked.connect(self.import_member_info)
        data_btn_layout.addWidget(import_data_btn)

        data_btn_layout.addStretch()
        data_form.addLayout(data_btn_layout)

        data_info = QLabel("提示：导出个人数据可用于备份或在其他设备上继续填写。")
        data_info.setStyleSheet("color: #666; font-size: 12px;")
        data_info.setWordWrap(True)
        data_form.addWidget(data_info)

        data_group.setLayout(data_form)
        scroll_layout.addWidget(data_group)

        # === 模式管理 ===
        mode_group = QGroupBox(f"{ICONS['user']} 模式管理")
        mode_form = QVBoxLayout()
        mode_form.setSpacing(10)
        mode_form.setContentsMargins(15, 20, 15, 15)

        # 切换按钮
        mode_btn_layout = QHBoxLayout()
        self.switch_to_admin_btn = QPushButton("切换到管理员模式")
        self.switch_to_admin_btn.setObjectName("secondary")
        self.switch_to_admin_btn.clicked.connect(self.switch_to_admin_mode)
        mode_btn_layout.addWidget(self.switch_to_admin_btn)
        mode_btn_layout.addWidget(QLabel("当前模式："))
        self.mode_status_label = QLabel("成员模式")
        self.mode_status_label.setStyleSheet("color: #f9ab00; font-weight: bold;")
        mode_btn_layout.addWidget(self.mode_status_label)
        mode_btn_layout.addStretch()
        mode_form.addLayout(mode_btn_layout)

        mode_info = QLabel("提示：需要由管理员赋予切换操作的权限。")
        mode_info.setStyleSheet("color: #666; font-size: 12px;")
        mode_info.setWordWrap(True)
        mode_form.addWidget(mode_info)

        mode_group.setLayout(mode_form)
        scroll_layout.addWidget(mode_group)

        # === 密码保护 ===
        pwd_group = QGroupBox(f"{ICONS['key']} 数据加密保护")
        pwd_form = QVBoxLayout()
        pwd_form.setSpacing(10)
        pwd_form.setContentsMargins(15, 20, 15, 15)

        # 密码操作按钮
        pwd_btn_layout = QHBoxLayout()

        self.set_pwd_btn = QPushButton("设置密码")
        self.set_pwd_btn.clicked.connect(self.setup_password)
        pwd_btn_layout.addWidget(self.set_pwd_btn)

        self.change_pwd_btn = QPushButton("修改密码")
        self.change_pwd_btn.setObjectName("secondary")
        self.change_pwd_btn.clicked.connect(self.change_password)
        pwd_btn_layout.addWidget(self.change_pwd_btn)

        self.remove_pwd_btn = QPushButton(" 取消密码")
        self.remove_pwd_btn.setObjectName("secondary")
        self.remove_pwd_btn.clicked.connect(self.remove_password)
        pwd_btn_layout.addWidget(self.remove_pwd_btn)

        pwd_btn_layout.addWidget(QLabel("加密状态："))
        self.pwd_status_label = QLabel("未设置密码")
        self.pwd_status_label.setStyleSheet("color: #ea4335; font-weight: bold;")
        pwd_btn_layout.addWidget(self.pwd_status_label)

        pwd_btn_layout.addStretch()
        pwd_form.addLayout(pwd_btn_layout)

        pwd_info = QLabel(
            "提示：设置密码保护后，成员个人数据将被加密存储。即使直接打开数据文件也无法读取内容，请务必牢记密码！"
        )
        pwd_info.setStyleSheet("color: #666; font-size: 12px;")
        pwd_info.setWordWrap(True)
        pwd_form.addWidget(pwd_info)

        pwd_group.setLayout(pwd_form)
        scroll_layout.addWidget(pwd_group)

        # === 关于 ===
        about_group = QGroupBox(f"{ICONS['info']} 关于")
        about_form = QFormLayout()
        about_form.setSpacing(10)
        about_form.setContentsMargins(15, 20, 15, 15)

        about_form.addRow("应用版本：", QLabel("v1.0.0"))

        about_group.setLayout(about_form)
        scroll_layout.addWidget(about_group)

        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)

        self.setLayout(main_layout)

        # 确保页面背景不透明，防止在 QStackedWidget 切换时"透出"
        self.setAutoFillBackground(True)

    def load_settings(self):
        """加载当前设置"""
        config = self.data_manager.get_admin_config()

        # 检查是否允许成员切换模式
        allow_switch = config.get("basic_data", {}).get("交互设置", {}).get("成员可否切换模式", "禁止")
        self._update_switch_button_state(allow_switch == "允许")

        # 同步状态
        synced_at = config.get("synced_at")
        imported_at = config.get("imported_at")
        
        if synced_at:
            self.sync_status_label.setText("已同步")
            self.sync_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
            self.sync_time_label.setText(self._format_datetime(synced_at))
        elif imported_at:
            self.sync_status_label.setText("已导入")
            self.sync_status_label.setStyleSheet("color: #1a73e8; font-weight: bold;")
            self.sync_time_label.setText(self._format_datetime(imported_at))
        else:
            self.sync_status_label.setText("使用默认配置")
            self.sync_status_label.setStyleSheet("color: #666;")
            self.sync_time_label.setText("-")

        # 导出路径
        export_path = self.data_manager.get_system_settings("export_path") or "./exports"
        self.export_path_edit.setText(export_path)

        # 密码保护状态
        self._update_password_status()

    def _format_datetime(self, iso_string: str) -> str:
        """格式化 ISO 时间字符串"""
        try:
            dt = datetime.fromisoformat(iso_string)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return iso_string

    def _update_switch_button_state(self, allow: bool):
        """更新切换按钮状态"""
        self.switch_to_admin_btn.setEnabled(allow)
        if allow:
            self.switch_to_admin_btn.setStyleSheet("")  # 恢复默认样式
            self.switch_to_admin_btn.setToolTip("点击切换到管理员模式")
        else:
            self.switch_to_admin_btn.setStyleSheet("background-color: #ccc; color: #888;")
            self.switch_to_admin_btn.setToolTip("管理员已禁止成员切换模式")

    def browse_and_save_export_path(self):
        """浏览选择导出路径并保存"""
        current_path = self.export_path_edit.text() or "./exports"
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            current_path
        )
        if dir_path:
            self.export_path_edit.setText(dir_path)
            # 确保导出目录存在
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            # 保存导出路径
            self.data_manager.save_system_settings("export_path", dir_path)
            self.load_settings()

    def sync_config(self):
        """手动同步配置"""
        sync_url = self.data_manager.get_admin_config("basic_data", "交互设置", "配置同步URL")

        if not sync_url:
            QMessageBox.warning(
                self,
                "无法同步",
                "未配置同步URL。\n\n请联系支部管理员获取同步URL或配置文件。"
            )
            return

        try:
            message = self.data_manager.sync_admin_config(sync_url, force=True)
            self.load_settings()
            QMessageBox.information(self, "同步成功", f"管理员配置已更新。{message}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"同步过程出错：{e}")

    def import_config(self):
        """从文件导入管理员配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入管理员配置",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            message = self.data_manager.import_admin_config(file_path)
            self.load_settings()
            QMessageBox.information(self, "提示", f"已导入管理员配置。{message}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def export_member_info(self):
        """导出成员个人数据"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出个人数据",
            "member_info.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            self.data_manager.export_member_info(file_path)
            QMessageBox.information(self, "提示", f"个人数据已导出成功！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败：{e}")

    def import_member_info(self):
        """导入成员个人数据"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入个人数据",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return
        
        try:
            self.data_manager.import_member_info(file_path)
            self.load_settings()
            QMessageBox.information(self, "提示", "个人数据已导入成功！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def switch_to_admin_mode(self):
        """切换到管理员模式"""
        reply = QMessageBox.question(
            self,
            "确认切换",
            "切换到管理员模式后，应用将加载为管理员界面。\n\n确定要切换吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.before_mode_changed.emit("admin")  # 发出即将切换模式信号
            if self.permission_controller.switch_to_admin_mode():
                self.mode_changed.emit("admin")
                QMessageBox.information(self, "提示", "已切换到管理员模式。")
            else:
                QMessageBox.critical(self, "错误", "切换模式失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"切换模式失败：{e}")

    # =========================== 密码保护管理 ===========================

    def _update_password_status(self):
        """更新密码保护状态显示"""
        has_password = self.data_manager.has_password("member")
        if has_password:
            self.pwd_status_label.setText("已启用加密保护")
            self.pwd_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
            self.set_pwd_btn.setEnabled(False)
            self.change_pwd_btn.setEnabled(True)
            self.remove_pwd_btn.setEnabled(True)
        else:
            self.pwd_status_label.setText("未设置密码")
            self.pwd_status_label.setStyleSheet("color: #ea4335; font-weight: bold;")  # 红色加粗
            self.set_pwd_btn.setEnabled(True)
            self.change_pwd_btn.setEnabled(False)
            self.remove_pwd_btn.setEnabled(False)

    def setup_password(self):
        """设置密码保护"""
        dialog = PasswordSetupDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        password = dialog.get_password()
        if not password:
            return

        try:
            if self.data_manager.enable_encryption("member", password):
                self._update_password_status()
                QMessageBox.information(
                    self,
                    "设置成功",
                    "密码保护已启用！\n\n"
                    "您的个人数据现已加密存储。\n"
                    "下次启动应用时需要输入密码才能访问。\n\n"
                    "请务必牢记您的密码！"
                )
            else:
                QMessageBox.critical(self, "错误", "设置密码失败，请重试。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"设置密码失败：{e}")

    def change_password(self):
        """修改密码"""
        dialog = PasswordChangeDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        old_password, new_password = dialog.get_passwords()
        if not old_password or not new_password:
            return

        try:
            if self.data_manager.change_password("member", old_password, new_password):
                QMessageBox.information(
                    self,
                    "修改成功",
                    "密码已修改成功！\n\n下次启动应用时请使用新密码。"
                )
            else:
                QMessageBox.critical(self, "错误", "修改密码失败，请重试。")
        except DecryptionError:
            QMessageBox.critical(self, "错误", "当前密码错误，请重新输入。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"修改密码失败：{e}")

    def remove_password(self):
        """取消密码保护"""
        dialog = PasswordRemoveDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        password = dialog.get_password()
        if not password:
            return

        try:
            if self.data_manager.disable_encryption("member", password):
                self._update_password_status()
                QMessageBox.information(
                    self,
                    "已取消",
                    "密码保护已取消。\n\n您的个人数据现在以明文形式存储。"
                )
            else:
                QMessageBox.critical(self, "错误", "取消密码保护失败，请重试。")
        except DecryptionError:
            QMessageBox.critical(self, "错误", "密码错误，请重新输入。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"取消密码保护失败：{e}")
