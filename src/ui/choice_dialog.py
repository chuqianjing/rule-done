#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""自定义选择对话框。

QMessageBox 在 macOS 上会使用系统原生弹窗（NSAlert），按钮顺序与文字宽度
由系统接管，导致与 Windows 上的显示不一致（顺序被打乱、按钮文字被截断）。
本对话框改用普通 QDialog + QPushButton 手动布局，保证：
- 按钮顺序与传入顺序完全一致，跨平台显示一致
- 按钮宽度随文字自适应，文字完整显示
"""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class ChoiceDialog(QDialog):
    """按钮顺序固定、文字完整显示的通用选择对话框。

    Args:
        title: 对话框标题
        message: 提示文字（自动换行）
        choices: 按钮列表，每个元素为 (按钮文字, 角色)。
                 角色仅用于语义标记，不影响排序（顺序即传入顺序）。
                 推荐：确认/主操作用 "accept"，取消类用 "reject"。
        parent: 父窗口

    exec() 返回被点击按钮的文字；若直接关闭（Esc / 关闭按钮）则返回 None。
    """

    def __init__(self, title: str, message: str,
                 choices: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self._result_text: str | None = None
        self.setWindowTitle(title)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        # 按钮行：使用普通 QPushButton 手动布局，顺序与传入一致，避免平台重排
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch(1)  # 按钮整体右对齐，与 Windows 习惯一致
        for text, _role in choices:
            btn = QPushButton(text)
            btn.setMinimumWidth(96)
            btn.clicked.connect(lambda _checked=False, t=text: self._on_clicked(t))
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

    def _on_clicked(self, text: str) -> None:
        """记录点击的按钮文字并关闭对话框。"""
        self._result_text = text
        self.accept()

    def exec(self) -> str | None:
        """显示对话框并返回点击按钮的文字；关闭/Esc 返回 None。"""
        self._result_text = None
        super().exec()
        return self._result_text
