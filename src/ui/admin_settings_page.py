#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统设置页面
管理员态和成员态有不同的设置界面
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QFileDialog,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import pyqtSignal
from src.application.data_manager import DataManager
from src.application.permission_controller import PermissionController
from src.ui.password_dialog import (
    PasswordSetupDialog,
    PasswordRemoveDialog,
    PasswordChangeDialog,
)
from src.utils.styles import TIP_STYLE, ICONS
from src.utils.crypto_storage import DecryptionError


class AdminSettingsPage(QWidget):
    """管理员态系统设置页面"""

    # 已弃用 config_changed = pyqtSignal()    # 配置变更信号，通知其他页面刷新，三处：锁定配置、解锁配置、导入配置
    mode_changed = pyqtSignal(str)   # 模式切换信号，参数为新模式
    before_mode_changed = pyqtSignal(str)  # 即将切换模式信号，参数为当前模式

    def __init__(self):
        super().__init__()

        self.data_manager = DataManager()
        self.permission_controller = PermissionController()

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """初始化 UI"""
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

        # === 配置锁定管理 ===
        lock_group = QGroupBox(f"{ICONS['lock']} 锁定管理")
        lock_form = QVBoxLayout()
        lock_form.setSpacing(10)
        lock_form.setContentsMargins(15, 20, 15, 15)

        # 锁定/解锁按钮
        lock_btn_layout = QHBoxLayout()

        self.lock_btn = QPushButton(f"锁定配置")
        self.lock_btn.clicked.connect(self.lock_config)
        lock_btn_layout.addWidget(self.lock_btn)

        self.unlock_btn = QPushButton(f"解锁配置")
        self.unlock_btn.setObjectName("secondary")
        self.unlock_btn.clicked.connect(self.unlock_config)
        lock_btn_layout.addWidget(self.unlock_btn)

        # 锁定状态显示
        lock_btn_layout.addWidget(QLabel("当前状态："))
        self.lock_status_label = QLabel("未锁定")
        self.lock_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
        lock_btn_layout.addWidget(self.lock_status_label)

        lock_btn_layout.addStretch()
        lock_form.addLayout(lock_btn_layout)

        lock_info = QLabel("提示：锁定后，配置信息以只读方式呈现。如需修改，可解锁配置以继续编辑。")
        lock_info.setStyleSheet("color: #666; font-size: 12px;")
        lock_info.setWordWrap(True)
        lock_form.addWidget(lock_info)

        lock_group.setLayout(lock_form)
        scroll_layout.addWidget(lock_group)

        # === 配置导入导出 ===
        io_group = QGroupBox(f"{ICONS['exchange']} 导入导出")
        io_form = QVBoxLayout()
        io_form.setSpacing(10)
        io_form.setContentsMargins(15, 20, 15, 15)

        io_btn_layout = QHBoxLayout()
        export_btn = QPushButton(f"导出配置")
        export_btn.clicked.connect(self.export_config)
        io_btn_layout.addWidget(export_btn)

        import_btn = QPushButton(f"导入配置")
        import_btn.setObjectName("secondary")
        import_btn.clicked.connect(self.import_config)
        io_btn_layout.addWidget(import_btn)

        io_btn_layout.addStretch()
        io_form.addLayout(io_btn_layout)

        io_info = QLabel("提示：导出的配置文件可上传至云端或直接下发以供成员同步。导入配置时会备份现有配置。")
        io_info.setStyleSheet("color: #666; font-size: 12px;")
        io_info.setWordWrap(True)
        io_form.addWidget(io_info)

        io_group.setLayout(io_form)
        scroll_layout.addWidget(io_group)

        # === 模式管理 ===
        mode_group = QGroupBox(f"{ICONS['user']} 模式管理")
        mode_form = QVBoxLayout()
        mode_form.setSpacing(10)
        mode_form.setContentsMargins(15, 20, 15, 15)

        # 切换按钮
        mode_btn_layout = QHBoxLayout()
        self.switch_to_member_btn = QPushButton(f"切换到成员模式")
        self.switch_to_member_btn.clicked.connect(self.switch_to_member_mode)
        mode_btn_layout.addWidget(self.switch_to_member_btn)
        mode_btn_layout.addWidget(QLabel("当前模式："))
        self.mode_status_label = QLabel("管理员模式")
        self.mode_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
        mode_btn_layout.addWidget(self.mode_status_label)
        mode_btn_layout.addStretch()
        mode_form.addLayout(mode_btn_layout)

        mode_info = QLabel("提示：如需切换回管理员模式，可在成员模式的通用设置中进行操作。")
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

        self.set_pwd_btn = QPushButton(f"设置密码")
        self.set_pwd_btn.clicked.connect(self.setup_password)
        pwd_btn_layout.addWidget(self.set_pwd_btn)

        self.change_pwd_btn = QPushButton(f"修改密码")
        self.change_pwd_btn.setObjectName("secondary")
        self.change_pwd_btn.clicked.connect(self.change_password)
        pwd_btn_layout.addWidget(self.change_pwd_btn)

        self.remove_pwd_btn = QPushButton(f"取消密码")
        self.remove_pwd_btn.setObjectName("secondary")
        self.remove_pwd_btn.clicked.connect(self.remove_password)
        pwd_btn_layout.addWidget(self.remove_pwd_btn)

        # 密码状态显示
        pwd_btn_layout.addWidget(QLabel("加密状态："))
        self.pwd_status_label = QLabel("未设置密码")
        self.pwd_status_label.setStyleSheet("color: #666;")
        pwd_btn_layout.addWidget(self.pwd_status_label)

        pwd_btn_layout.addStretch()
        pwd_form.addLayout(pwd_btn_layout)

        pwd_info = QLabel(
            "提示：设置密码保护后，管理员配置数据将被加密存储。即使直接打开数据文件也无法读取内容，请务必牢记密码！"
        )
        pwd_info.setStyleSheet("color: #666; font-size: 12px;")
        pwd_info.setWordWrap(True)
        pwd_form.addWidget(pwd_info)

        pwd_group.setLayout(pwd_form)
        scroll_layout.addWidget(pwd_group)

        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)

        self.setLayout(main_layout)

        # 确保页面背景不透明，防止在 QStackedWidget 切换时"透出"
        self.setAutoFillBackground(True)

    def load_settings(self):
        """加载当前设置"""
        is_locked = self.data_manager.get_admin_config("locked") or False
        self._update_lock_status(is_locked)
        self._update_password_status()

    def _update_lock_status(self, is_locked: bool):
        """更新锁定状态显示"""
        if is_locked:
            self.lock_status_label.setText("已锁定")
            self.lock_status_label.setStyleSheet("color: #ea4335; font-weight: bold;")
            self.lock_btn.setEnabled(False)
            self.unlock_btn.setEnabled(True)
        else:
            self.lock_status_label.setText("未锁定")
            self.lock_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
            self.lock_btn.setEnabled(True)
            self.unlock_btn.setEnabled(False)

    # =========================== 锁定管理 ===========================

    def lock_config(self):
        """锁定配置"""
        reply = QMessageBox.question(
            self,
            "确认锁定",
            "锁定后，下次启动应用将进入成员模式。\n\n确定要锁定当前配置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.data_manager.lock_admin_config()
            self._update_lock_status(True)
            QMessageBox.information(self, "提示", "配置已锁定，成员端将以只读方式使用这些信息。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"锁定配置失败：{e}")

    def unlock_config(self):
        """解锁配置"""
        reply = QMessageBox.question(
            self,
            "确认解锁",
            "解锁后，配置可以重新编辑。\n\n确定要解锁配置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.data_manager.unlock_admin_config()
            self._update_lock_status(False)
            QMessageBox.information(self, "提示", "配置已解锁，现在可以编辑。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"解锁配置失败：{e}")

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
            is_success, message = self.data_manager.export_admin_config(file_path)
            if is_success:
                QMessageBox.information(self, "提示", f"配置已导出到：\n{file_path}")
            else:
                QMessageBox.warning(self, "警告", message)
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
            is_success, message = self.data_manager.import_admin_config(file_path, mode='admin')
            if is_success:
                self.load_settings()
                QMessageBox.information(self, "提示", f"配置已导入成功！\n\n{message}")
            else:
                QMessageBox.warning(self, "警告", message)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def switch_to_member_mode(self):
        """切换到成员模式"""
        reply = QMessageBox.question(
            self,
            "确认切换",
            "切换到成员模式后，程序将重新加载为成员界面。\n\n确定要切换吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.before_mode_changed.emit("member")
            if self.permission_controller.switch_to_member_mode():
                self.mode_changed.emit("member")
                QMessageBox.information(self, "提示", "已切换到成员模式，程序将重新加载。")
            else:
                QMessageBox.critical(self, "错误", "切换模式失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"切换模式失败：{e}")

    # =========================== 密码保护管理 ===========================

    def _update_password_status(self):
        """更新密码保护状态显示"""
        has_password = self.data_manager.has_password("admin")
        if has_password:
            self.pwd_status_label.setText("已启用加密保护")
            self.pwd_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
            self.set_pwd_btn.setEnabled(False)
            self.change_pwd_btn.setEnabled(True)
            self.remove_pwd_btn.setEnabled(True)
        else:
            self.pwd_status_label.setText("未设置密码")
            self.pwd_status_label.setStyleSheet("color: #666;")
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
            if self.data_manager.enable_encryption("admin", password):
                self._update_password_status()
                QMessageBox.information(
                    self,
                    "设置成功",
                    "密码保护已启用！\n\n"
                    "您的管理员配置数据现已加密存储。\n"
                    "下次启动程序时需要输入密码才能访问。\n\n"
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
            if self.data_manager.change_password("admin", old_password, new_password):
                QMessageBox.information(
                    self,
                    "修改成功",
                    "密码已修改成功！\n\n下次启动程序时请使用新密码。"
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
            if self.data_manager.disable_encryption("admin", password):
                self._update_password_status()
                QMessageBox.information(
                    self,
                    "已取消",
                    "密码保护已取消。\n\n您的配置数据现在以明文形式存储。"
                )
            else:
                QMessageBox.critical(self, "错误", "取消密码保护失败，请重试。")
        except DecryptionError:
            QMessageBox.critical(self, "错误", "密码错误，请重新输入。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"取消密码保护失败：{e}")
