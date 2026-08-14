#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""成员端同步凭据编辑对话框。

集中管理三类凭据：
- 配置解密密钥：解密远程加密的配置内容
- 远程访问令牌：访问 GitHub 私有仓库（只读 PAT）
- OSS 只读子账号：访问阿里云 OSS 私有对象

凭据按"存放平台"（GitHub / 阿里云 OSS）切换显隐，避免同时呈现；
打开时预填当前已保存值，仅需修改需要变更的项，留空表示清除。
"""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)
from PySide6.QtCore import Qt


class SyncCredentialsDialog(QDialog):
    """成员端同步凭据编辑对话框。"""

    def __init__(self, data_manager, parent=None, title="同步凭据设置",
                 skip_button_text: str | None = None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self._build_ui(skip_button_text)
        self._load_current_values()

    def _build_ui(self, skip_button_text: str | None) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._form = QFormLayout()
        self._form.setSpacing(8)
        self._form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 配置解密密钥（两种平台均需要）
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("留空则清除")
        self._form.addRow("解密密钥：", self.key_edit)

        # 存放平台选择（先建控件，最后填充选项并连接信号）
        self.provider_combo = QComboBox()
        self._form.addRow("同步平台：", self.provider_combo)

        # GitHub 私有仓库令牌
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("GitHub 只读令牌；留空则清除")
        self._form.addRow("Access token：", self.token_edit)

        # OSS 只读子账号
        self.oss_id_edit = QLineEdit()
        self.oss_id_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.oss_id_edit.setPlaceholderText("OSS 只读子账号 AccessKeyId；留空则清除")
        self._form.addRow("AccessKey Id：", self.oss_id_edit)

        self.oss_secret_edit = QLineEdit()
        self.oss_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.oss_secret_edit.setPlaceholderText("OSS 只读子账号 AccessKeySecret；留空则清除")
        self._form.addRow("AccessKey Secret：", self.oss_secret_edit)

        self.provider_combo.addItem("阿里云 OSS", "aliyun_oss")
        self.provider_combo.addItem("GitHub", "github")
        self.provider_combo.currentIndexChanged.connect(self._update_platform_visibility)

        layout.addLayout(self._form)

        info_label = QLabel(
            "请通过安全渠道向管理员获取同步凭据，请勿随意转发。"
        )
        info_label.setStyleSheet("color: #999;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 按钮
        self._button_box = QDialogButtonBox()
        if skip_button_text:
            self._button_box.addButton(skip_button_text, QDialogButtonBox.ButtonRole.RejectRole)
            self._button_box.addButton("确认", QDialogButtonBox.ButtonRole.AcceptRole)
        else:
            self._button_box.setStandardButtons(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

    def _load_current_values(self) -> None:
        """预填当前已保存的凭据值，并根据已配置情况选择平台。"""
        self.key_edit.setText(self.data_manager.get_config_decrypt_key())
        self.token_edit.setText(self.data_manager.get_config_access_token())
        oss_creds = self.data_manager.get_config_oss_credentials()
        self.oss_id_edit.setText(str(oss_creds.get("access_key_id", "")))
        self.oss_secret_edit.setText(str(oss_creds.get("access_key_secret", "")))

        has_oss = bool(oss_creds.get("access_key_id") and oss_creds.get("access_key_secret"))
        has_token = bool(self.data_manager.has_config_access_token())
        if has_token and not has_oss:
            self.provider_combo.setCurrentIndex(1)  # 仅配置了 GitHub 时保持 GitHub
        else:
            self.provider_combo.setCurrentIndex(0)  # 默认 / 仅 OSS / 两者皆备 → OSS
        self._update_platform_visibility()

    def _update_platform_visibility(self, *_) -> None:
        """根据存放平台显隐对应凭据输入项（同时显隐其行标签）。"""
        is_oss = self.provider_combo.currentData() == "aliyun_oss"
        self.token_edit.setVisible(not is_oss)
        self._form.labelForField(self.token_edit).setVisible(not is_oss)
        self.oss_id_edit.setVisible(is_oss)
        self._form.labelForField(self.oss_id_edit).setVisible(is_oss)
        self.oss_secret_edit.setVisible(is_oss)
        self._form.labelForField(self.oss_secret_edit).setVisible(is_oss)

    def save(self) -> list[str]:
        """保存凭据（解密密钥 + 当前存放平台对应的项），返回提示消息列表。

        仅处理当前选中平台的凭据，另一平台已有值保持不变，避免误清除。
        """
        key = self.key_edit.text().strip()
        is_oss = self.provider_combo.currentData() == "aliyun_oss"
        token = self.token_edit.text().strip()
        oss_id = self.oss_id_edit.text().strip()
        oss_secret = self.oss_secret_edit.text().strip()

        self.data_manager.save_config_decrypt_key(key)
        if is_oss:
            self.data_manager.save_config_oss_credentials(oss_id, oss_secret)
        else:
            self.data_manager.save_config_access_token(token)

        messages = ["配置解密密钥已保存。" if key else "配置解密密钥已清除。"]
        if is_oss:
            messages.append("OSS 子账号凭据已保存。" if (oss_id or oss_secret) else "OSS 子账号凭据已清除。")
        else:
            messages.append("远程访问令牌已保存。" if token else "远程访问令牌已清除。")
        return messages
