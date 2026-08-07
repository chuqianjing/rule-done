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
    QGridLayout,
    QLineEdit,
    QMessageBox,
    QFileDialog,
    QScrollArea,
    QFrame,
)
import os
import sys
import subprocess
import webbrowser
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
from src.utils.sync_thread import ConfigSyncThread, ResourceSyncThread
from src.utils.update_check_thread import UpdateCheckThread
from src.utils.styles import ICONS
from src import __version__


class AdminSettingsPage(QWidget):
    """管理员态系统设置页面"""

    # 已弃用 config_changed = Signal()    # 配置变更信号，通知其他页面刷新，三处：锁定配置、解锁配置、导入配置
    mode_changed = Signal(str)   # 模式切换信号，参数为新模式
    before_mode_changed = Signal(str)  # 即将切换模式信号，参数为当前模式

    def __init__(self):
        super().__init__()

        self.data_manager = DataManager()
        self.permission_controller = PermissionController()
        self.update_check_thread: UpdateCheckThread | None = None

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

        # === 同步至远程 ===
        remote_group = QGroupBox(f"{ICONS['sync']} 发布支部数据至远程")
        remote_form = QVBoxLayout()
        remote_form.setSpacing(8)
        remote_form.setContentsMargins(12, 16, 12, 12)

        # 同步目标（共用），右侧跟随“保存设置”按钮（同一行）
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("同步目标："))
        self.remote_provider_combo = NoWheelComboBox()
        self.remote_provider_combo.addItem("GitHub", "github")
        self.remote_provider_combo.addItem("阿里云 OSS", "aliyun_oss")
        self.remote_provider_combo.currentIndexChanged.connect(self._on_remote_provider_changed)
        target_layout.addWidget(self.remote_provider_combo)
        target_layout.addStretch()
        save_remote_btn = QPushButton("保存同步设置项")
        save_remote_btn.setObjectName("secondary")
        save_remote_btn.clicked.connect(self.save_config_sync_settings)
        target_layout.addWidget(save_remote_btn)
        test_remote_btn = QPushButton("测试远程连接")
        test_remote_btn.setObjectName("secondary")
        test_remote_btn.clicked.connect(self.test_config_sync_connection)
        target_layout.addWidget(test_remote_btn)
        remote_form.addLayout(target_layout)

        # 连接配置（QGridLayout：4 列两对字段，label 右对齐，列间距作并列空隙）
        self.remote_provider_layout = QGridLayout()
        self.remote_provider_layout.setHorizontalSpacing(16)
        self.remote_provider_layout.setVerticalSpacing(8)
        self.remote_provider_layout.setColumnStretch(1, 1)
        self.remote_provider_layout.setColumnStretch(3, 1)

        def make_field(label_text, placeholder="", password=False):
            """创建 (label, edit) 字段对（label 右对齐）。"""
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            edit = QLineEdit()
            if placeholder:
                edit.setPlaceholderText(placeholder)
            if password:
                edit.setEchoMode(QLineEdit.EchoMode.Password)
            return label, edit

        # GitHub 连接配置：仓库+分支同一行，Token 单独一行
        github_repo_label, self.github_repo_edit = make_field("仓库：", "owner/repo")
        github_branch_label, self.github_branch_edit = make_field("分支：", "main")
        github_token_label, self.github_token_edit = make_field("Token：", "ghp_xxx", password=True)
        self.remote_provider_layout.addWidget(github_repo_label, 0, 0)
        self.remote_provider_layout.addWidget(self.github_repo_edit, 0, 1)
        self.remote_provider_layout.addWidget(github_branch_label, 0, 2)
        self.remote_provider_layout.addWidget(self.github_branch_edit, 0, 3)
        self.remote_provider_layout.addWidget(github_token_label, 1, 0)
        self.remote_provider_layout.addWidget(self.github_token_edit, 1, 1)

        self._github_rows = [
            github_repo_label, self.github_repo_edit,
            github_branch_label, self.github_branch_edit,
            github_token_label, self.github_token_edit,
        ]

        # OSS 连接配置：Endpoint+Bucket 同一行，AccessKey Id+Secret 同一行
        oss_endpoint_label, self.oss_endpoint_edit = make_field("Endpoint：", "oss-cn-hangzhou.aliyuncs.com")
        oss_bucket_label, self.oss_bucket_edit = make_field("Bucket：", "your-bucket")
        oss_access_key_id_label, self.oss_access_key_id_edit = make_field("AccessKey Id：", "LTAI...")
        oss_access_key_secret_label, self.oss_access_key_secret_edit = make_field("AccessKey Secret：", "AccessKeySecret", password=True)
        self.remote_provider_layout.addWidget(oss_endpoint_label, 2, 0)
        self.remote_provider_layout.addWidget(self.oss_endpoint_edit, 2, 1)
        self.remote_provider_layout.addWidget(oss_bucket_label, 2, 2)
        self.remote_provider_layout.addWidget(self.oss_bucket_edit, 2, 3)
        self.remote_provider_layout.addWidget(oss_access_key_id_label, 3, 0)
        self.remote_provider_layout.addWidget(self.oss_access_key_id_edit, 3, 1)
        self.remote_provider_layout.addWidget(oss_access_key_secret_label, 3, 2)
        self.remote_provider_layout.addWidget(self.oss_access_key_secret_edit, 3, 3)

        self._oss_rows = [
            oss_endpoint_label, self.oss_endpoint_edit,
            oss_bucket_label, self.oss_bucket_edit,
            oss_access_key_id_label, self.oss_access_key_id_edit,
            oss_access_key_secret_label, self.oss_access_key_secret_edit,
        ]

        remote_form.addLayout(self.remote_provider_layout)

        # === 分割标题：模板与字段资源 ===
        res_title_layout = QHBoxLayout()
        res_title_layout.setContentsMargins(0, 8, 0, 4)
        res_line1 = QFrame()
        res_line1.setFrameShape(QFrame.Shape.HLine)
        res_line1.setStyleSheet("QFrame { color: #d0d0d0; }")
        res_line2 = QFrame()
        res_line2.setFrameShape(QFrame.Shape.HLine)
        res_line2.setStyleSheet("QFrame { color: #d0d0d0; }")
        res_title = QLabel("字段与模板资源")
        res_title.setStyleSheet("color: #aaa; font-size: 12px;")
        res_title_layout.addWidget(res_line1, 1)
        res_title_layout.addWidget(res_title)
        res_title_layout.addWidget(res_line2, 1)
        remote_form.addLayout(res_title_layout)

        resource_prefix_layout = QHBoxLayout()
        resource_prefix_layout.addWidget(QLabel("资源文件路径："))
        self.resource_prefix_edit = QLineEdit()
        self.resource_prefix_edit.setPlaceholderText("resources")
        resource_prefix_layout.addWidget(self.resource_prefix_edit, 1)
        remote_form.addLayout(resource_prefix_layout)

        resource_btn_layout = QHBoxLayout()
        publish_res_btn = QPushButton("发布资源")
        publish_res_btn.clicked.connect(self.publish_resources)
        resource_btn_layout.addWidget(publish_res_btn)
        resource_btn_layout.addSpacing(24)
        resource_btn_layout.addWidget(QLabel("最近发布状态："))
        self.resource_push_status_label = QLabel("未发布")
        self.resource_push_status_label.setStyleSheet("color: #666;")
        resource_btn_layout.addWidget(self.resource_push_status_label)
        resource_btn_layout.addSpacing(16)
        resource_btn_layout.addWidget(QLabel("时间："))
        self.resource_push_time_label = QLabel("-")
        self.resource_push_time_label.setStyleSheet("color: #666;")
        resource_btn_layout.addWidget(self.resource_push_time_label)
        resource_btn_layout.addStretch()
        remote_form.addLayout(resource_btn_layout)

        # === 分割标题：管理员配置 ===
        cfg_title_layout = QHBoxLayout()
        cfg_title_layout.setContentsMargins(0, 8, 0, 4)
        cfg_line1 = QFrame()
        cfg_line1.setFrameShape(QFrame.Shape.HLine)
        cfg_line1.setStyleSheet("QFrame { color: #d0d0d0; }")
        cfg_line2 = QFrame()
        cfg_line2.setFrameShape(QFrame.Shape.HLine)
        cfg_line2.setStyleSheet("QFrame { color: #d0d0d0; }")
        cfg_title = QLabel("管理员配置")
        cfg_title.setStyleSheet("color: #aaa; font-size: 12px;")
        cfg_title_layout.addWidget(cfg_line1, 1)
        cfg_title_layout.addWidget(cfg_title)
        cfg_title_layout.addWidget(cfg_line2, 1)
        remote_form.addLayout(cfg_title_layout)

        # 配置文件路径 + 加密密钥（同一行，QGridLayout 右对齐）
        self.config_encrypt_layout = QGridLayout()
        self.config_encrypt_layout.setHorizontalSpacing(16)
        self.config_encrypt_layout.setColumnStretch(1, 1)
        self.config_encrypt_layout.setColumnStretch(3, 2)

        self.config_path_label = QLabel("配置文件路径：")
        self.config_path_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.config_path_edit = QLineEdit()
        self.config_path_edit.setPlaceholderText("admin_config.json")
        self.config_encrypt_layout.addWidget(self.config_path_label, 0, 0)
        self.config_encrypt_layout.addWidget(self.config_path_edit, 0, 1)

        encrypt_label = QLabel("加密密钥：")
        encrypt_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.remote_encrypt_key_edit = QLineEdit()
        self.remote_encrypt_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.remote_encrypt_key_edit.setPlaceholderText("必填：用于加密上传的配置文件")
        self.config_encrypt_layout.addWidget(encrypt_label, 0, 2)
        self.config_encrypt_layout.addWidget(self.remote_encrypt_key_edit, 0, 3)

        remote_form.addLayout(self.config_encrypt_layout)

        # 操作按钮 + 同步状态（同一行，状态信息在按钮右侧）
        remote_btn_layout = QHBoxLayout()
        sync_remote_btn = QPushButton("发布配置")
        sync_remote_btn.clicked.connect(self.sync_to_remote)
        remote_btn_layout.addWidget(sync_remote_btn)
        remote_btn_layout.addSpacing(24)
        remote_btn_layout.addWidget(QLabel("最近发布状态："))
        self.remote_status_label = QLabel("未同步")
        self.remote_status_label.setStyleSheet("color: #666;")
        remote_btn_layout.addWidget(self.remote_status_label)
        remote_btn_layout.addSpacing(16)
        remote_btn_layout.addWidget(QLabel("时间："))
        self.remote_time_label = QLabel("-")
        self.remote_time_label.setStyleSheet("color: #666;")
        remote_btn_layout.addWidget(self.remote_time_label)
        remote_btn_layout.addStretch()
        remote_form.addLayout(remote_btn_layout)

        remote_info = QLabel("提示：将资源文件和支部配置同步到远程后，成员端可从远程拉取最新资源和配置。")
        remote_info.setStyleSheet("color: #999; font-size: 12px;")
        remote_info.setWordWrap(True)
        remote_form.addWidget(remote_info)

        remote_group.setLayout(remote_form)
        scroll_layout.addWidget(remote_group)

        # === 模板和字段资源管理 ===
        tpl_group = QGroupBox(f"{ICONS['template']} 管理字段和模板资源")
        tpl_form = QVBoxLayout()
        tpl_form.setSpacing(10)
        tpl_form.setContentsMargins(15, 20, 15, 15)

        tpl_btn_layout = QHBoxLayout()
        open_tpl_btn = QPushButton(f"打开资源文件夹")
        open_tpl_btn.clicked.connect(self.open_resources_folder)
        tpl_btn_layout.addWidget(open_tpl_btn)
        tpl_btn_layout.addStretch()
        tpl_form.addLayout(tpl_btn_layout)

        tpl_info = QLabel(
            "提示：管理员须在resources文件夹中自行定制字段（schema下的fields_definition.json）和模板（templates下的templates_config.json和.docx 文件），并确保同步资源至远程以供成员使用。"
        )
        tpl_info.setStyleSheet("color: #999; font-size: 12px;")
        tpl_info.setWordWrap(True)
        tpl_form.addWidget(tpl_info)

        tpl_group.setLayout(tpl_form)
        scroll_layout.addWidget(tpl_group)

        # === 用户数据目录 ===
        runtime_group = QGroupBox(f"{ICONS['save']} 更改用户数据位置")
        runtime_form = QFormLayout()
        runtime_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        runtime_form.setSpacing(10)
        runtime_form.setContentsMargins(15, 20, 15, 15)

        runtime_path_layout = QHBoxLayout()
        self.user_data_root_edit = QLineEdit()
        self.user_data_root_edit.setPlaceholderText("默认：系统用户可写目录")
        self.user_data_root_edit.setReadOnly(True)
        runtime_path_layout.addWidget(self.user_data_root_edit, 1)

        runtime_browse_btn = QPushButton("浏览...")
        runtime_browse_btn.setObjectName("secondary")
        runtime_browse_btn.clicked.connect(self.browse_and_save_user_data_root)
        runtime_path_layout.addWidget(runtime_browse_btn)

        runtime_form.addRow(runtime_path_layout)

        runtime_info = QLabel("提示：该目录会存放资源文件（resources文件夹）和运行时数据（data文件夹），修改后会自动迁移这两项数据，建议重启应用后继续使用。")
        runtime_info.setStyleSheet("color: #999; font-size: 12px;")
        runtime_info.setWordWrap(True)
        runtime_form.addRow(runtime_info)

        runtime_group.setLayout(runtime_form)
        scroll_layout.addWidget(runtime_group)

        # === 配置锁定管理 ===
        lock_group = QGroupBox(f"{ICONS['lock']} 锁定管理员配置")
        lock_form = QVBoxLayout()
        lock_form.setSpacing(10)
        lock_form.setContentsMargins(15, 20, 15, 15)

        # 锁定/解锁按钮
        lock_btn_layout = QHBoxLayout()

        self.lock_btn = QPushButton(f"锁定")
        self.lock_btn.clicked.connect(self.lock_config)
        lock_btn_layout.addWidget(self.lock_btn)

        self.unlock_btn = QPushButton(f"解锁")
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

        lock_info = QLabel("提示：锁定后，管理员配置信息以只读方式呈现。如需修改，可解锁配置以继续编辑。")
        lock_info.setStyleSheet("color: #999; font-size: 12px;")
        lock_info.setWordWrap(True)
        lock_form.addWidget(lock_info)

        lock_group.setLayout(lock_form)
        scroll_layout.addWidget(lock_group)

        # === 配置导入导出 ===
        io_group = QGroupBox(f"{ICONS['exchange']} 本地配置的导入导出")
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

        io_info = QLabel("提示：导出的配置文件可上传至远程或直接下发以供成员同步。导入配置时会备份现有配置。")
        io_info.setStyleSheet("color: #999; font-size: 12px;")
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
        pwd_info.setStyleSheet("color: #999; font-size: 12px;")
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
        mode_info.setStyleSheet("color: #999; font-size: 12px;")
        mode_info.setWordWrap(True)
        mode_form.addWidget(mode_info)

        mode_group.setLayout(mode_form)
        scroll_layout.addWidget(mode_group)

        # === 关于 ===
        about_group = QGroupBox(f"{ICONS['info']} 关于")
        about_form = QFormLayout()
        about_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        about_form.setSpacing(10)
        about_form.setContentsMargins(15, 20, 15, 15)
        about_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        about_form.addRow("应用名：", QLabel("入档 (RuleDone)"))
        # 版本布局
        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel(f"v{__version__}"))
        self.check_update_btn = QPushButton("检查更新")
        self.check_update_btn.clicked.connect(self.check_for_updates)
        version_layout.addWidget(self.check_update_btn)
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

    # ====================== 模板管理 ======================

    def open_resources_folder(self):
        """在文件管理器中打开资源文件夹（含 schema/ 与 templates/，不存在则自动创建）。"""
        res_dir = self.data_manager.get_resources_dir()
        try:
            res_dir.mkdir(parents=True, exist_ok=True)
            if sys.platform == "darwin":
                subprocess.run(["open", str(res_dir)])
            elif sys.platform == "win32":
                os.startfile(str(res_dir))
            else:
                subprocess.run(["xdg-open", str(res_dir)])
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开文件夹：{e}")

    def load_settings(self):
        """加载当前设置"""
        is_locked = self.data_manager.get_admin_config("locked") or False
        self._update_lock_status(is_locked)
        self._update_password_status()
        self.user_data_root_edit.setText(self.data_manager.get_user_data_root())
        self._load_remote_sync_settings()
        self._load_resource_push_settings()

    def _load_remote_sync_settings(self):
        """加载远程同步配置到界面（remote 连接 + config_push 业务字段）。"""
        remote_cfg = self.data_manager.get_remote_settings(decrypt_sensitive=True)
        provider = str(remote_cfg.get("provider", "github")).lower()
        index = 1 if provider == "aliyun_oss" else 0
        self.remote_provider_combo.setCurrentIndex(index)

        github_cfg = remote_cfg.get("github", {})
        self.github_repo_edit.setText(str(github_cfg.get("repo", "")))
        self.github_branch_edit.setText(str(github_cfg.get("branch", "main")))
        self.github_token_edit.setText(str(github_cfg.get("token", "")))

        oss_cfg = remote_cfg.get("aliyun_oss", {})
        self.oss_endpoint_edit.setText(str(oss_cfg.get("endpoint", "")))
        self.oss_bucket_edit.setText(str(oss_cfg.get("bucket", "")))
        self.oss_access_key_id_edit.setText(str(oss_cfg.get("access_key_id", "")))
        self.oss_access_key_secret_edit.setText(str(oss_cfg.get("access_key_secret", "")))

        push_cfg = self.data_manager.get_config_push_settings(decrypt_sensitive=True)
        self.config_path_edit.setText(str(push_cfg.get("path", "admin_config.json")))
        self.remote_encrypt_key_edit.setText(str(push_cfg.get("encrypt_key", "")))

        sync_result = push_cfg.get("last_sync_result", {}) or {}
        status = str(sync_result.get("status", "") or "未同步")
        if status == "success":
            self.remote_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
            self.remote_status_label.setText("成功")
        elif status == "failed":
            self.remote_status_label.setStyleSheet("color: #ea4335; font-weight: bold;")
            self.remote_status_label.setText("失败")
        else:
            self.remote_status_label.setStyleSheet("color: #666;")
            self.remote_status_label.setText(status)
        last_sync_time = str(sync_result.get("time", "") or "-")
        if last_sync_time != "-":
            dt = datetime.fromisoformat(last_sync_time)
            last_sync_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        self.remote_time_label.setText(last_sync_time)
        self._on_remote_provider_changed()

    def _on_remote_provider_changed(self, *_):
        """根据 provider 显示对应字段。"""
        provider = self.remote_provider_combo.currentData()
        is_github = provider == "github"

        for widget in self._github_rows:
            widget.setVisible(is_github)
        for widget in self._oss_rows:
            widget.setVisible(not is_github)

    def _collect_remote_sync_config_from_ui(self):
        """从界面采集远程连接配置（remote 块，不含 path/encrypt_key）。"""
        return {
            "provider": self.remote_provider_combo.currentData(),
            "github": {
                "repo": self.github_repo_edit.text().strip(),
                "branch": self.github_branch_edit.text().strip() or "main",
                "token": self.github_token_edit.text().strip(),
                "commit_message": "chore: sync admin config"
            },
            "aliyun_oss": {
                "endpoint": self.oss_endpoint_edit.text().strip(),
                "bucket": self.oss_bucket_edit.text().strip(),
                "access_key_id": self.oss_access_key_id_edit.text().strip(),
                "access_key_secret": self.oss_access_key_secret_edit.text().strip(),
            }
        }

    def _collect_config_push_from_ui(self):
        """从界面采集管理员配置发布设置（path/encrypt_key）。"""
        return {
            "path": self.config_path_edit.text().strip() or "admin_config.json",
            "encrypt_key": self.remote_encrypt_key_edit.text().strip(),
        }

    def _save_all_sync_settings(self) -> None:
        """保存“同步数据至远程”整组设置（连接配置 + 资源路径 + 发布设置）。"""
        self.data_manager.save_remote_settings(self._collect_remote_sync_config_from_ui())
        self.data_manager.save_resource_push_settings(self.resource_prefix_edit.text().strip())
        self.data_manager.save_config_push_settings(self._collect_config_push_from_ui())

    def save_config_sync_settings(self):
        """保存“同步数据至远程”整组设置。"""
        try:
            self._save_all_sync_settings()
            QMessageBox.information(self, "提示", "同步设置已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存同步设置失败：{e}")

    def test_config_sync_connection(self):
        """测试远程同步连接（测试前先保存当前界面设置，确保所见即所测）。"""
        try:
            self._save_all_sync_settings()
            cfg = self._collect_remote_sync_config_from_ui()
            success, message = self.data_manager.test_config_sync_connection(cfg.get("provider", "github"))
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
            push_cfg = self._collect_config_push_from_ui()
            if not str(push_cfg.get("encrypt_key", "") or "").strip():
                QMessageBox.warning(
                    self,
                    "无法同步",
                    "为防止党务信息与平台凭据泄露到公网，发布到远程前必须设置加密密钥。\n\n"
                    "请在上方“传输至远程时的加密密钥”中填写加密密钥，并保存同步设置。"
                )
                return
            self.data_manager.save_remote_settings(cfg)
            self.data_manager.save_config_push_settings(push_cfg)
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

    # =========================== 模板与字段资源发布 ===========================

    def _load_resource_push_settings(self):
        """加载资源发布配置与最近结果到界面。"""
        push_settings = self.data_manager.get_resource_push_settings()
        self.resource_prefix_edit.setText(str(push_settings.get("prefix", "resources") or "resources"))

        result = self.data_manager.get_resource_push_result()
        status = str(result.get("status", "") or "未发布")
        if status == "success":
            self.resource_push_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
            self.resource_push_status_label.setText("成功")
        elif status == "failed":
            self.resource_push_status_label.setStyleSheet("color: #ea4335; font-weight: bold;")
            self.resource_push_status_label.setText("失败")
        else:
            self.resource_push_status_label.setStyleSheet("color: #666;")
            self.resource_push_status_label.setText(status)
        t = str(result.get("time", "") or "-")
        if t != "-":
            try:
                t = datetime.fromisoformat(t).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        self.resource_push_time_label.setText(t)

    def publish_resources(self):
        """将模板与字段资源打包发布到远程。"""
        reply = QMessageBox.question(
            self,
            "确认发布",
            "即将把当前字段定义与模板打包发布到远程，成员端将自动跟进。\n\n确定继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            # 先保存当前界面采集的连接配置与资源前缀（所见即所发；资源不加密，不要求加密密钥）
            self.data_manager.save_remote_settings(self._collect_remote_sync_config_from_ui())
            self.data_manager.save_resource_push_settings(self.resource_prefix_edit.text().strip())
            self.resource_thread = ResourceSyncThread(self.data_manager, mode="push")
            self.resource_thread.sync_completed.connect(self._on_resource_push_completed)
            self.resource_thread.sync_failed.connect(self._on_resource_push_failed)
            self.resource_thread.start()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发布失败：{e}")

    def _on_resource_push_completed(self, message: str):
        """资源发布成功回调。"""
        self._load_resource_push_settings()
        QMessageBox.information(self, "发布成功", message)

    def _on_resource_push_failed(self, error_message: str):
        """资源发布失败回调。"""
        self._load_resource_push_settings()
        QMessageBox.warning(self, "发布失败", error_message)

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

    def browse_and_save_user_data_root(self):
        """浏览选择用户数据目录并自动迁移。"""
        current_path = self.user_data_root_edit.text() or self.data_manager.get_user_data_root()
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择用户数据目录",
            current_path
        )
        if not dir_path:
            return

        try:
            changed, message = self.data_manager.update_user_data_root(dir_path)
            if changed:
                QMessageBox.information(self, "提示", f"{message}\n\n为确保页面全部切换到新目录，建议重启应用。")
            else:
                QMessageBox.information(self, "提示", message)
            self.load_settings()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"切换用户数据目录失败：{e}")

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
        if self.update_check_thread is not None and self.update_check_thread.isRunning():
            return

        self.check_update_btn.setEnabled(False)
        self.update_check_thread = UpdateCheckThread(
            current_version=f"v{__version__}",
            release_url="https://github.com/chuqianjing/rule-done/releases/latest",
            project_url="https://github.com/chuqianjing/rule-done",
        )
        self.update_check_thread.result_ready.connect(self._on_update_check_completed)
        self.update_check_thread.failed.connect(self._on_update_check_failed)
        self.update_check_thread.start()

    def _cleanup_update_check_thread(self):
        """安全释放更新线程，避免线程未结束即销毁导致进程退出。"""
        if self.update_check_thread is None:
            return

        if self.update_check_thread.isRunning():
            self.update_check_thread.wait(2000)

        self.update_check_thread.deleteLater()
        self.update_check_thread = None

    def _on_update_check_completed(self, result: dict):
        """更新检查完成回调"""
        self.check_update_btn.setEnabled(True)

        current_version = str(result.get("current_version", f"v{__version__}"))
        latest_version = str(result.get("latest_version", current_version))
        download_url = str(result.get("download_url", ""))
        project_url = str(result.get("project_url", "https://github.com/chuqianjing/rule-done"))

        if result.get("has_update"):
            reply = QMessageBox.question(
                self,
                "发现新版本",
                f"当前版本：{current_version}\n最新版本：{latest_version}\n\n是否前往下载？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                webbrowser.open(download_url)
        else:
            QMessageBox.information(
                self,
                "检查更新",
                "当前已是最新版本！\n\n"
                "如有新版本发布，请前往项目主页下载：\n"
                f"{project_url}",
            )
        self._cleanup_update_check_thread()

    def _on_update_check_failed(self, message: str):
        """更新检查失败回调"""
        self.check_update_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", message)
        self._cleanup_update_check_thread()
