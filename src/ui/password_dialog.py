#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
密码相关对话框

包含：
- PasswordInputDialog: 密码输入对话框（启动时验证）
- PasswordSetupDialog: 密码设置对话框（首次设置密码）
- PasswordRemoveDialog: 取消密码对话框（验证后取消密码保护）
- PasswordChangeDialog: 修改密码对话框（验证旧密码后设置新密码）
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class PasswordInputDialog(QDialog):
    """
    密码输入对话框

    用于程序启动时验证用户密码
    """

    def __init__(self, mode: str = "member", parent=None):
        """
        初始化密码输入对话框

        Args:
            mode: 当前模式 (admin/member)
            parent: 父窗口
        """
        super().__init__(parent)
        self.mode = mode
        self.password = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("密码验证")
        self.setFixedSize(400, 200)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # 标题
        title_label = QLabel("请输入密码")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 提示
        mode_text = "管理员" if self.mode == "admin" else "成员"
        hint_label = QLabel(f"当前{mode_text}数据已加密保护，请输入密码以解锁")
        hint_label.setStyleSheet("color: #666; font-size: 12px;")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #e0e0e0;")
        layout.addWidget(line)

        # 密码输入
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("请输入密码...")
        self.password_input.setMinimumHeight(36)
        self.password_input.returnPressed.connect(self.on_confirm)
        layout.addWidget(self.password_input)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.cancel_btn = QPushButton("退出程序")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("确认")
        self.confirm_btn.setMinimumHeight(36)
        self.confirm_btn.clicked.connect(self.on_confirm)
        self.confirm_btn.setDefault(True)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 聚焦到密码输入框
        self.password_input.setFocus()

    def on_confirm(self):
        """确认按钮点击处理"""
        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "提示", "请输入密码")
            self.password_input.setFocus()
            return
        self.password = password
        self.accept()

    def get_password(self) -> str:
        """获取输入的密码"""
        return self.password


class PasswordSetupDialog(QDialog):
    """
    密码设置对话框

    用于首次设置密码保护
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.password = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("设置密码保护")
        self.setFixedSize(450, 320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(30, 25, 30, 25)

        # 标题
        title_label = QLabel("设置数据加密密码")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 提示
        hint_label = QLabel(
            "设置密码后，您的数据将被加密存储。\n"
            "即使直接打开数据文件也无法读取内容。\n"
            "请务必牢记密码，密码丢失将无法恢复数据！"
        )
        hint_label.setStyleSheet("color: #e65100; font-size: 12px; background-color: #fff3e0; padding: 10px; border-radius: 4px;")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #e0e0e0;")
        layout.addWidget(line)

        # 密码输入
        pwd_label = QLabel("输入密码：")
        layout.addWidget(pwd_label)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("请输入密码（至少6位）...")
        self.password_input.setMinimumHeight(36)
        layout.addWidget(self.password_input)

        # 确认密码
        confirm_label = QLabel("确认密码：")
        layout.addWidget(confirm_label)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("请再次输入密码...")
        self.confirm_input.setMinimumHeight(36)
        self.confirm_input.returnPressed.connect(self.on_confirm)
        layout.addWidget(self.confirm_input)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("确认设置")
        self.confirm_btn.setMinimumHeight(36)
        self.confirm_btn.clicked.connect(self.on_confirm)
        self.confirm_btn.setDefault(True)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 聚焦到密码输入框
        self.password_input.setFocus()

    def on_confirm(self):
        """确认按钮点击处理"""
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        if not password:
            QMessageBox.warning(self, "提示", "请输入密码")
            self.password_input.setFocus()
            return

        if len(password) < 6:
            QMessageBox.warning(self, "提示", "密码长度至少为6位")
            self.password_input.setFocus()
            self.password_input.selectAll()
            return

        if password != confirm:
            QMessageBox.warning(self, "提示", "两次输入的密码不一致")
            self.confirm_input.setFocus()
            self.confirm_input.selectAll()
            return

        self.password = password
        self.accept()

    def get_password(self) -> str:
        """获取设置的密码"""
        return self.password


class PasswordRemoveDialog(QDialog):
    """
    取消密码保护对话框

    需要验证当前密码后才能取消密码保护
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.password = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("取消密码保护")
        self.setFixedSize(400, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 25, 30, 25)

        # 标题
        title_label = QLabel("取消密码保护")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 提示
        hint_label = QLabel(
            "取消密码保护后，数据将以明文形式存储。\n"
            "请输入当前密码以确认操作。"
        )
        hint_label.setStyleSheet("color: #666; font-size: 12px;")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #e0e0e0;")
        layout.addWidget(line)

        # 密码输入
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("请输入当前密码...")
        self.password_input.setMinimumHeight(36)
        self.password_input.returnPressed.connect(self.on_confirm)
        layout.addWidget(self.password_input)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("确认取消密码")
        self.confirm_btn.setMinimumHeight(36)
        self.confirm_btn.setStyleSheet("background-color: #f44336;")
        self.confirm_btn.clicked.connect(self.on_confirm)
        self.confirm_btn.setDefault(True)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 聚焦到密码输入框
        self.password_input.setFocus()

    def on_confirm(self):
        """确认按钮点击处理"""
        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "提示", "请输入当前密码")
            self.password_input.setFocus()
            return
        self.password = password
        self.accept()

    def get_password(self) -> str:
        """获取输入的密码"""
        return self.password


class PasswordChangeDialog(QDialog):
    """
    修改密码对话框
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.old_password = None
        self.new_password = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("修改密码")
        self.setFixedSize(450, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(30, 25, 30, 25)

        # 标题
        title_label = QLabel("修改数据加密密码")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #e0e0e0;")
        layout.addWidget(line)

        # 当前密码
        old_label = QLabel("当前密码：")
        layout.addWidget(old_label)

        self.old_password_input = QLineEdit()
        self.old_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.old_password_input.setPlaceholderText("请输入当前密码...")
        self.old_password_input.setMinimumHeight(36)
        layout.addWidget(self.old_password_input)

        # 新密码
        new_label = QLabel("新密码：")
        layout.addWidget(new_label)

        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input.setPlaceholderText("请输入新密码（至少6位）...")
        self.new_password_input.setMinimumHeight(36)
        layout.addWidget(self.new_password_input)

        # 确认新密码
        confirm_label = QLabel("确认新密码：")
        layout.addWidget(confirm_label)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("请再次输入新密码...")
        self.confirm_input.setMinimumHeight(36)
        self.confirm_input.returnPressed.connect(self.on_confirm)
        layout.addWidget(self.confirm_input)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("确认修改")
        self.confirm_btn.setMinimumHeight(36)
        self.confirm_btn.clicked.connect(self.on_confirm)
        self.confirm_btn.setDefault(True)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 聚焦到当前密码输入框
        self.old_password_input.setFocus()

    def on_confirm(self):
        """确认按钮点击处理"""
        old_pwd = self.old_password_input.text()
        new_pwd = self.new_password_input.text()
        confirm = self.confirm_input.text()

        if not old_pwd:
            QMessageBox.warning(self, "提示", "请输入当前密码")
            self.old_password_input.setFocus()
            return

        if not new_pwd:
            QMessageBox.warning(self, "提示", "请输入新密码")
            self.new_password_input.setFocus()
            return

        if len(new_pwd) < 6:
            QMessageBox.warning(self, "提示", "新密码长度至少为6位")
            self.new_password_input.setFocus()
            self.new_password_input.selectAll()
            return

        if new_pwd != confirm:
            QMessageBox.warning(self, "提示", "两次输入的新密码不一致")
            self.confirm_input.setFocus()
            self.confirm_input.selectAll()
            return

        if old_pwd == new_pwd:
            QMessageBox.warning(self, "提示", "新密码不能与当前密码相同")
            self.new_password_input.setFocus()
            self.new_password_input.selectAll()
            return

        self.old_password = old_pwd
        self.new_password = new_pwd
        self.accept()

    def get_passwords(self) -> tuple:
        """获取旧密码和新密码"""
        return self.old_password, self.new_password
