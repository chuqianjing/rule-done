#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
管理员设置页面
"""

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
from datetime import datetime
from src.utils.widget_binding import NoWheelComboBox
from PySide6.QtCore import Qt, Signal
from src.application.data_manager import DataManager
from src.application.permission_controller import PermissionController
from src.utils.crypto_storage import DecryptionError
from src.ui.password_dialog import (
    PasswordSetupDialog,
    PasswordRemoveDialog,
    PasswordChangeDialog,
)
from src.utils.config_sync_thread import ConfigSyncThread
from src.utils.styles import ICONS


class AdminSettingsPage(QWidget):
    """管理员态系统设置页面"""

    # 已弃用 config_changed = Signal()    # 配置变更信号，通知其他页面刷新，三处：锁定配置、解锁配置、导入配置
    mode_changed = Signal(str)   # 模式切换信号，参数为新模式
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
        self.setObjectName("admin_settings_page")

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

        # === 云端发布 ===
        remote_group = QGroupBox(f"{ICONS['sync']} 云端发布")
        remote_form = QVBoxLayout()
        remote_form.setSpacing(10)
        remote_form.setContentsMargins(15, 20, 15, 15)

        self.remote_provider_layout = QFormLayout()
        self.remote_provider_layout.setSpacing(10)
        self.remote_provider_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.remote_provider_combo = NoWheelComboBox()
        self.remote_provider_combo.addItem("GitHub", "github")
        self.remote_provider_combo.addItem("阿里云 OSS", "oss")
        self.remote_provider_combo.currentIndexChanged.connect(self._on_remote_provider_changed)
        self.remote_provider_layout.addRow("同步目标：", self.remote_provider_combo)

        self._github_rows = []
        self._oss_rows = []

        
        # GitHub 配置
        self.github_repo_label = QLabel("GitHub 仓库：")
        self.github_repo_edit = QLineEdit()
        self.github_repo_edit.setPlaceholderText("owner/repo")
        self.remote_provider_layout.addRow(self.github_repo_label, self.github_repo_edit)
        self._github_rows.append((self.github_repo_label, self.github_repo_edit))

        self.github_branch_label = QLabel("GitHub 分支：")
        self.github_branch_edit = QLineEdit()
        self.github_branch_edit.setPlaceholderText("main")
        self.remote_provider_layout.addRow(self.github_branch_label, self.github_branch_edit)
        self._github_rows.append((self.github_branch_label, self.github_branch_edit))

        self.github_path_label = QLabel("GitHub 文件路径：")
        self.github_path_edit = QLineEdit()
        self.github_path_edit.setPlaceholderText("admin_config.json")
        self.remote_provider_layout.addRow(self.github_path_label, self.github_path_edit)
        self._github_rows.append((self.github_path_label, self.github_path_edit))

        self.github_token_label = QLabel("GitHub Token：")
        self.github_token_edit = QLineEdit()
        self.github_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_token_edit.setPlaceholderText("ghp_xxx")
        self.remote_provider_layout.addRow(self.github_token_label, self.github_token_edit)
        self._github_rows.append((self.github_token_label, self.github_token_edit))

        # OSS 配置
        self.oss_endpoint_label = QLabel("OSS Endpoint：")
        self.oss_endpoint_edit = QLineEdit()
        self.oss_endpoint_edit.setPlaceholderText("oss-cn-hangzhou.aliyuncs.com")
        self.remote_provider_layout.addRow(self.oss_endpoint_label, self.oss_endpoint_edit)
        self._oss_rows.append((self.oss_endpoint_label, self.oss_endpoint_edit))

        self.oss_bucket_label = QLabel("OSS Bucket：")
        self.oss_bucket_edit = QLineEdit()
        self.oss_bucket_edit.setPlaceholderText("your-bucket")
        self.remote_provider_layout.addRow(self.oss_bucket_label, self.oss_bucket_edit)
        self._oss_rows.append((self.oss_bucket_label, self.oss_bucket_edit))

        self.oss_object_key_label = QLabel("OSS Object Key：")
        self.oss_object_key_edit = QLineEdit()
        self.oss_object_key_edit.setPlaceholderText("admin_config.json")
        self.remote_provider_layout.addRow(self.oss_object_key_label, self.oss_object_key_edit)
        self._oss_rows.append((self.oss_object_key_label, self.oss_object_key_edit))

        self.oss_access_key_id_label = QLabel("OSS AccessKeyId：")
        self.oss_access_key_id_edit = QLineEdit()
        self.oss_access_key_id_edit.setPlaceholderText("LTAI...")
        self.remote_provider_layout.addRow(self.oss_access_key_id_label, self.oss_access_key_id_edit)
        self._oss_rows.append((self.oss_access_key_id_label, self.oss_access_key_id_edit))

        self.oss_access_key_secret_label = QLabel("OSS AccessKeySecret：")
        self.oss_access_key_secret_edit = QLineEdit()
        self.oss_access_key_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.oss_access_key_secret_edit.setPlaceholderText("AccessKeySecret")
        self.remote_provider_layout.addRow(self.oss_access_key_secret_label, self.oss_access_key_secret_edit)
        self._oss_rows.append((self.oss_access_key_secret_label, self.oss_access_key_secret_edit))
        
        # =============
        remote_form.addLayout(self.remote_provider_layout)
        remote_btn_layout = QHBoxLayout()

        sync_remote_btn = QPushButton("立即同步到远程")
        sync_remote_btn.clicked.connect(self.sync_to_remote)
        remote_btn_layout.addWidget(sync_remote_btn)

        save_remote_btn = QPushButton("保存同步配置")
        save_remote_btn.setObjectName("secondary")
        save_remote_btn.clicked.connect(self.save_remote_sync_config)
        remote_btn_layout.addWidget(save_remote_btn)

        test_remote_btn = QPushButton("测试连接")
        test_remote_btn.setObjectName("secondary")
        test_remote_btn.clicked.connect(self.test_remote_sync_connection)
        remote_btn_layout.addWidget(test_remote_btn)

        remote_btn_layout.addStretch()
        remote_form.addLayout(remote_btn_layout)

        remote_status_layout = QHBoxLayout()
        remote_status_layout.addWidget(QLabel("状态："))
        self.remote_status_label = QLabel("未同步")
        self.remote_status_label.setStyleSheet("color: #666;")
        remote_status_layout.addWidget(self.remote_status_label)

        remote_status_layout.addWidget(QLabel("时间："))
        self.remote_time_label = QLabel("-")
        self.remote_time_label.setStyleSheet("color: #666;")
        remote_status_layout.addWidget(self.remote_time_label)
        
        remote_status_layout.addWidget(QLabel("目标："))
        self.remote_target_label = QLabel("-")
        self.remote_target_label.setStyleSheet("color: #666;")
        remote_status_layout.addWidget(self.remote_target_label)
        remote_status_layout.addStretch()
        remote_form.addLayout(remote_status_layout)

        remote_info = QLabel("提示：该功能会把data/admin_config.json推送到远程静态资源位置。同步前请确保已在主页配置该资源的URL。")
        remote_info.setStyleSheet("color: #666; font-size: 12px;")
        remote_info.setWordWrap(True)
        remote_form.addWidget(remote_info)

        remote_group.setLayout(remote_form)
        scroll_layout.addWidget(remote_group)

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
        self.pwd_status_label.setStyleSheet("color: #ea4335; font-weight: bold;")
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

        # === 关于 ===
        about_group = QGroupBox(f"{ICONS['info']} 关于")
        about_form = QFormLayout()
        about_form.setSpacing(10)
        about_form.setContentsMargins(15, 20, 15, 15)
        about_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        about_form.addRow("应用名：", QLabel("入档 (RuleDone)"))
        # 版本布局
        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel("v1.0.0"))
        check_update_btn = QPushButton("检查更新")
        check_update_btn.clicked.connect(self.check_for_updates)
        version_layout.addWidget(check_update_btn)
        version_layout.addStretch()
        about_form.addRow("版本号：", version_layout)
        about_form.addRow("开发者：", QLabel("楚乾靖 (Chu Qianjing)"))
         # 项目主页
        link_label = QLabel('<a href="https://github.com/chuqianjing/rule-done" style="color: #1a73e8; text-decoration: underline;">https://github.com/chuqianjing/rule-done</a>')
        link_label.setOpenExternalLinks(True)
        about_form.addRow("项目主页：", link_label)
        # 法律与致谢
        law_info = QLabel(
            "项目遵循 GNU General Public License v3.0 许可证开源\n"
            "欢迎访问项目主页获取更多信息、提交反馈或参与贡献！\n\n"
            "Copyright (c) 2026 楚乾靖(Chu Qianjing)"
        )
        law_info.setStyleSheet("color: #666; font-size: 12px;")
        law_info.setWordWrap(True)
        about_form.addRow("", law_info)

        about_group.setLayout(about_form)
        scroll_layout.addWidget(about_group)

        # ==============================

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
        self._load_remote_sync_settings()

    def _load_remote_sync_settings(self):
        """加载远程同步配置到界面。"""
        remote_cfg = self.data_manager.get_remote_sync_config(decrypt_sensitive=True)
        provider = str(remote_cfg.get("provider", "github")).lower()
        index = 1 if provider == "oss" else 0
        self.remote_provider_combo.setCurrentIndex(index)

        github_cfg = remote_cfg.get("github", {})
        self.github_repo_edit.setText(str(github_cfg.get("repo", "")))
        self.github_branch_edit.setText(str(github_cfg.get("branch", "main")))
        self.github_path_edit.setText(str(github_cfg.get("file_path", "admin_config.json")))
        self.github_token_edit.setText(str(github_cfg.get("token", "")))

        oss_cfg = remote_cfg.get("oss", {})
        self.oss_endpoint_edit.setText(str(oss_cfg.get("endpoint", "")))
        self.oss_bucket_edit.setText(str(oss_cfg.get("bucket", "")))
        self.oss_object_key_edit.setText(str(oss_cfg.get("object_key", "admin_config.json")))
        self.oss_access_key_id_edit.setText(str(oss_cfg.get("access_key_id", "")))
        self.oss_access_key_secret_edit.setText(str(oss_cfg.get("access_key_secret", "")))

        status = str(remote_cfg.get("last_sync_status", "") or "未同步")
        if status == "success":
            self.remote_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
            self.remote_status_label.setText("成功")
        elif status == "failed":
            self.remote_status_label.setStyleSheet("color: #ea4335; font-weight: bold;")
            self.remote_status_label.setText("失败")
        else:
            self.remote_status_label.setStyleSheet("color: #666;")
            self.remote_status_label.setText(status)
        last_sync_time = str(remote_cfg.get("last_sync_time", "") or "-")
        if last_sync_time != "-":
            dt = datetime.fromisoformat(last_sync_time)
            last_sync_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        self.remote_time_label.setText(last_sync_time)
        self.remote_target_label.setText(str(remote_cfg.get("last_sync_target", "") or "-"))
        self._on_remote_provider_changed()

    def _on_remote_provider_changed(self, *_):
        """根据 provider 显示对应字段。"""
        provider = self.remote_provider_combo.currentData()
        is_github = provider == "github"

        for label_widget, field_widget in self._github_rows:
            label_widget.setVisible(is_github)
            field_widget.setVisible(is_github)

        for label_widget, field_widget in self._oss_rows:
            label_widget.setVisible(not is_github)
            field_widget.setVisible(not is_github)

    def _collect_remote_sync_config_from_ui(self):
        """从界面采集远程同步配置。"""
        return {
            "enabled": True,
            "provider": self.remote_provider_combo.currentData(),
            "github": {
                "repo": self.github_repo_edit.text().strip(),
                "branch": self.github_branch_edit.text().strip() or "main",
                "file_path": self.github_path_edit.text().strip() or "admin_config.json",
                "token": self.github_token_edit.text().strip(),
                "commit_message": "chore: sync admin config"
            },
            "oss": {
                "endpoint": self.oss_endpoint_edit.text().strip(),
                "bucket": self.oss_bucket_edit.text().strip(),
                "object_key": self.oss_object_key_edit.text().strip() or "admin_config.json",
                "access_key_id": self.oss_access_key_id_edit.text().strip(),
                "access_key_secret": self.oss_access_key_secret_edit.text().strip(),
            }
        }

    def save_remote_sync_config(self):
        """保存远程同步配置。"""
        try:
            cfg = self._collect_remote_sync_config_from_ui()
            self.data_manager.save_remote_sync_config(cfg)
            QMessageBox.information(self, "提示", "远程同步配置已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存远程同步配置失败：{e}")

    def test_remote_sync_connection(self):
        """测试远程同步连接。"""
        try:
            cfg = self._collect_remote_sync_config_from_ui()
            self.data_manager.save_remote_sync_config(cfg)
            success, message = self.data_manager.test_remote_sync_connection(cfg.get("provider", "github"))
            if success:
                QMessageBox.information(self, "连接测试", message)
            else:
                QMessageBox.warning(self, "连接测试", message)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"连接测试失败：{e}")

    def sync_to_remote(self):
        """立即同步 admin_config 到远程。"""
        reply = QMessageBox.question(
            self,
            "确认同步",
            "即将把当前管理员配置发布到远程，确定继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            cfg = self._collect_remote_sync_config_from_ui()
            self.data_manager.save_remote_sync_config(cfg)
            provider = str(cfg.get("provider", "github"))
            self.sync_thread = ConfigSyncThread(self.data_manager, mode="push", provider=provider)
            self.sync_thread.sync_completed.connect(self._on_push_sync_completed)
            self.sync_thread.sync_failed.connect(self._on_push_sync_failed)
            self.sync_thread.start()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"同步失败：{e}")

    def _on_push_sync_completed(self, message: str):
        """远程上传成功回调。"""
        self._load_remote_sync_settings()
        QMessageBox.information(self, "同步成功", f'已成功同步至 {message}')

    def _on_push_sync_failed(self, error_message: str):
        """远程上传失败回调。"""
        self._load_remote_sync_settings()
        QMessageBox.warning(self, "同步失败", error_message)

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
            "锁定后，配置将处于只读状态。\n\n确定要锁定当前配置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.data_manager.lock_admin_config()
            self._update_lock_status(True)
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
            self.data_manager.export_admin_config(file_path)
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
            message = self.data_manager.import_admin_config(file_path)
            self.load_settings()
            QMessageBox.information(self, "提示", f"配置已导入成功！{message}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def switch_to_member_mode(self):
        """切换到成员模式"""
        reply = QMessageBox.question(
            self,
            "确认切换",
            "切换到成员模式后，应用将加载为成员界面。\n\n确定要切换吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.before_mode_changed.emit("member")
            if self.permission_controller.switch_to_member_mode():
                self.mode_changed.emit("member")
                QMessageBox.information(self, "提示", "已切换到成员模式")
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
            self.pwd_status_label.setStyleSheet("color: #ea4335; font-weight: bold;")
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
                    "密码保护已取消。\n\n您的管理员配置数据现在以明文形式存储。"
                )
            else:
                QMessageBox.critical(self, "错误", "取消密码保护失败，请重试。")
        except DecryptionError:
            QMessageBox.critical(self, "错误", "密码错误，请重新输入。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"取消密码保护失败：{e}")

    def check_for_updates(self):
        """检查应用更新"""
        QMessageBox.information(
            self,
            "检查更新",
            "当前已是最新版本！\n\n"
            "如有新版本发布，请前往项目主页下载：\n"
            "https://github.com/chuqianjing/rule-done"
        )
        
