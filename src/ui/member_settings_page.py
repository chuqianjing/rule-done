#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
成员设置页面
"""

import os
from datetime import datetime
from pathlib import Path
import webbrowser

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
    QDialog,
    QDialogButtonBox,
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
from src.utils.config_sync_thread import ConfigSyncThread
from src.utils.update_check_thread import UpdateCheckThread
from src.utils.file_path import get_runtime_exports_dir


class MemberSettingsPage(QWidget):
    """成员态系统设置页面"""

    mode_changed = Signal(str)         # 模式切换信号，通知主窗口重新加载
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
        self.config_version_label = QLabel(self.data_manager.get_admin_config('version'))
        config_info_layout.addWidget(self.config_version_label)
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

        # 最近同步结果
        sync_result_layout = QHBoxLayout()
        sync_result_layout.addWidget(QLabel("最近同步："))
        self.sync_result_status_label = QLabel("-")
        self.sync_result_status_label.setStyleSheet("color: #666;")
        sync_result_layout.addWidget(self.sync_result_status_label)
        sync_result_layout.addWidget(QLabel("时间："))
        self.sync_result_time_label = QLabel("-")
        self.sync_result_time_label.setStyleSheet("color: #666;")
        sync_result_layout.addWidget(self.sync_result_time_label)
        sync_result_layout.addStretch()
        config_form.addLayout(sync_result_layout)

        # 同步URL编辑
        url_layout = QFormLayout()
        url_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        url_layout.setSpacing(8)
        url_layout.setContentsMargins(0, 5, 0, 5)

        url_input_layout = QHBoxLayout()
        self.sync_url_edit = QLineEdit()
        self.sync_url_edit.setPlaceholderText("https://example.com/config.json")
        url_input_layout.addWidget(self.sync_url_edit, 1)

        save_url_btn = QPushButton("保存URL")
        save_url_btn.setObjectName("secondary")
        save_url_btn.clicked.connect(self._save_sync_url)
        url_input_layout.addWidget(save_url_btn)

        url_layout.addRow("同步URL：", url_input_layout)

        url_info = QLabel(
            "提示：修改同步URL后，点击「手动云端同步」将从新的URL获取配置。"
            "若管理员在管理端配置了新的URL，同步后将自动覆盖此处的URL。"
        )
        url_info.setStyleSheet("color: #666; font-size: 12px;")
        url_info.setWordWrap(True)
        url_layout.addRow("", url_info)

        config_form.addLayout(url_layout)

        # 更新解密密钥按钮
        decrypt_key_layout = QHBoxLayout()
        self.update_decrypt_key_btn = QPushButton("更新解密密钥")
        self.update_decrypt_key_btn.setObjectName("secondary")
        self.update_decrypt_key_btn.clicked.connect(self._show_update_decrypt_key_dialog)
        decrypt_key_layout.addWidget(self.update_decrypt_key_btn)
        self.decrypt_key_status_label = QLabel("未设置")
        self.decrypt_key_status_label.setStyleSheet("color: #ea4335;")
        decrypt_key_layout.addWidget(self.decrypt_key_status_label)
        decrypt_key_layout.addStretch()
        config_form.addLayout(decrypt_key_layout)

        tip_info = QLabel("提示：应用启动时会自动同步配置。如需强制获取云端配置，可点击手动同步或本地导入。若管理员设置了加密密钥，需在首次使用前输入。")
        tip_info.setStyleSheet("color: #666; font-size: 12px;")
        tip_info.setWordWrap(True)
        config_form.addWidget(tip_info)

        config_group.setLayout(config_form)
        scroll_layout.addWidget(config_group)

        '''
        # === 信息同步设置 ===
        feishu_group = QGroupBox(f"{ICONS['sync']} 信息同步设置")
        feishu_form = QVBoxLayout()
        feishu_form.setSpacing(10)
        feishu_form.setContentsMargins(15, 20, 15, 15)

        # 测试连接按钮
        feishu_btn_layout = QHBoxLayout()
        test_feishu_btn = QPushButton("测试飞书连接")
        test_feishu_btn.setObjectName("secondary")
        test_feishu_btn.clicked.connect(self.test_info_sync_connection)
        feishu_btn_layout.addWidget(test_feishu_btn)
        self.feishu_sync_status_label = QLabel("最近同步状态：未测试")
        self.feishu_sync_status_label.setStyleSheet("color: #666;")
        feishu_btn_layout.addWidget(self.feishu_sync_status_label)
        feishu_btn_layout.addStretch()
        feishu_form.addLayout(feishu_btn_layout)

        feishu_info = QLabel("提示：飞书同步凭据由支部管理员在管理端统一配置并下发，成员无需自行填写。如有疑问请联系支部管理员。")
        feishu_info.setStyleSheet("color: #666; font-size: 12px;")
        feishu_info.setWordWrap(True)
        feishu_form.addWidget(feishu_info)

        feishu_group.setLayout(feishu_form)
        scroll_layout.addWidget(feishu_group)
        '''

        # === 数据管理 ===
        data_group = QGroupBox(f"{ICONS['save']} 个人数据管理")
        data_form = QVBoxLayout()
        data_form.setSpacing(10)
        data_form.setContentsMargins(15, 20, 15, 15)

        data_btn_layout = QHBoxLayout()
        export_data_btn = QPushButton(f"导出数据")
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

        # === 用户数据目录 ===
        runtime_group = QGroupBox(f"{ICONS['save']} 用户数据目录")
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

        runtime_form.addRow("用户数据目录：", runtime_path_layout)

        runtime_info = QLabel("提示：用户数据目录 data 会存放在该目录下，修改后会自动迁移已有数据，建议重启应用后继续使用。导出目录 exports 默认也存放在该目录下。")
        runtime_info.setStyleSheet("color: #666; font-size: 12px;")
        runtime_info.setWordWrap(True)
        runtime_form.addRow("", runtime_info)

        runtime_group.setLayout(runtime_form)
        scroll_layout.addWidget(runtime_group)

        # === 导出设置 ===
        export_group = QGroupBox(f"{ICONS['export']} 材料文件导出")
        export_form = QFormLayout()
        export_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        export_form.setSpacing(10)
        export_form.setContentsMargins(15, 20, 15, 15)

        # 导出路径
        path_layout = QHBoxLayout()
        self.export_path_edit = QLineEdit()
        self.export_path_edit.setPlaceholderText(f"默认：{get_runtime_exports_dir()}")
        self.export_path_edit.setReadOnly(True)
        path_layout.addWidget(self.export_path_edit, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.setObjectName("secondary")
        browse_btn.clicked.connect(self.browse_and_save_export_path)
        path_layout.addWidget(browse_btn)

        export_form.addRow("导出路径：", path_layout)

        export_info = QLabel("提示：生成的材料文件将保存到此目录。建议首次使用时将默认路径变更为自定义路径，如个人党务工作相关目录。")
        export_info.setStyleSheet("color: #666; font-size: 12px;")
        export_info.setWordWrap(True)
        export_form.addRow("", export_info)

        export_group.setLayout(export_form)
        scroll_layout.addWidget(export_group)

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

        # === 模板管理 ===
        tpl_group = QGroupBox(f"{ICONS['template']} 模板管理")
        tpl_form = QVBoxLayout()
        tpl_form.setSpacing(10)
        tpl_form.setContentsMargins(15, 20, 15, 15)

        tpl_btn_layout = QHBoxLayout()
        open_tpl_btn = QPushButton(f"打开模板文件夹")
        open_tpl_btn.clicked.connect(self.open_templates_folder)
        tpl_btn_layout.addWidget(open_tpl_btn)
        tpl_btn_layout.addStretch()
        tpl_form.addLayout(tpl_btn_layout)

        tpl_info = QLabel(
            "操作说明：点击后可在文件管理器中查看所有 .docx 模板文件。\n"
            "如需新增或修改模板，请联系支部管理员。"
        )
        tpl_info.setStyleSheet("color: #666; font-size: 12px;")
        tpl_info.setWordWrap(True)
        tpl_form.addWidget(tpl_info)

        tpl_group.setLayout(tpl_form)
        scroll_layout.addWidget(tpl_group)

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
        version_layout.addWidget(QLabel("v1.0.0"))
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

        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)

        self.setLayout(main_layout)

        # 确保页面背景不透明，防止在 QStackedWidget 切换时"透出"
        self.setAutoFillBackground(True)

    # ====================== 模板管理 ======================

    def open_templates_folder(self):
        """在文件管理器中打开模板文件夹。"""
        tpl_dir = self.data_manager.template_manager.templates_dir
        if not tpl_dir.exists():
            QMessageBox.warning(self, "提示", f"模板文件夹不存在：{tpl_dir}")
            return
        try:
            os.startfile(str(tpl_dir))
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开文件夹：{e}")

    def load_settings(self):
        """加载当前设置"""
        config = self.data_manager.get_admin_config()

        # 检查是否允许成员切换模式
        allow_switch = config.get("basic_data", {}).get("交互设置", {}).get("成员可否切换模式", "禁止")
        self._update_switch_button_state(allow_switch == "允许")

        # 同步状态
        config_version = config.get("version", "1.0")
        self.config_version_label.setText(config_version)

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

        # 同步结果
        self._update_sync_result_display()

        # 同步URL
        current_url = config.get("basic_data", {}).get("交互设置", {}).get("配置同步URL", "")
        self.sync_url_edit.setText(str(current_url or ""))

        # 导出路径
        export_path = self.data_manager.get_system_settings("export_path") or str(get_runtime_exports_dir())
        self.export_path_edit.setText(export_path)

        # 用户数据目录
        self.user_data_root_edit.setText(self.data_manager.get_user_data_root())

        # 密码保护状态
        self._update_password_status()

        # 解密密钥状态
        self._update_decrypt_key_status()

    def _update_sync_result_display(self):
        """从 system_settings 读取最近同步结果并更新显示。"""
        result = self.data_manager.get_sync_result()
        status = str(result.get("status", "") or "")
        sync_time = str(result.get("time", "") or "")
        message = str(result.get("message", "") or "")

        if status == "success":
            self.sync_result_status_label.setText("成功")
            self.sync_result_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
            if sync_time:
                self.sync_result_time_label.setText(self._format_datetime(sync_time))
            else:
                self.sync_result_time_label.setText("-")
        elif status == "failed":
            self.sync_result_status_label.setText("失败")
            self.sync_result_status_label.setStyleSheet("color: #ea4335; font-weight: bold;")
            self.sync_result_time_label.setText(message if message else "-")
        else:
            self.sync_result_status_label.setText("-")
            self.sync_result_status_label.setStyleSheet("color: #666;")
            self.sync_result_time_label.setText("-")

    def _save_sync_url(self):
        """保存同步URL到 admin_config.json。"""
        new_url = self.sync_url_edit.text().strip()
        try:
            self.data_manager.update_sync_url(new_url)
            self.load_settings()
            QMessageBox.information(self, "提示", "同步URL已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存同步URL失败：{e}")

    def _update_decrypt_key_status(self):
        """更新解密密钥状态显示。"""
        has_key = self.data_manager.has_config_decrypt_key()
        if has_key:
            self.decrypt_key_status_label.setText("已设置")
            self.decrypt_key_status_label.setStyleSheet("color: #34a853;")
        else:
            self.decrypt_key_status_label.setText("未设置")
            self.decrypt_key_status_label.setStyleSheet("color: #ea4335;")

    def _show_update_decrypt_key_dialog(self):
        """显示更新解密密钥对话框。"""
        dialog = QDialog(self)
        dialog.setWindowTitle("配置解密密钥")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("请输入管理员下发的配置解密密钥："))
        key_edit = QLineEdit()
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_edit.setPlaceholderText("留空则清除密钥")
        layout.addWidget(key_edit)

        info_label = QLabel("提示：该密钥用于解密远程加密的配置。请通过线下渠道向管理员获取。")
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            key = key_edit.text().strip()
            try:
                self.data_manager.save_config_decrypt_key(key)
                self._update_decrypt_key_status()
                if key:
                    QMessageBox.information(self, "提示", "解密密钥已保存。")
                else:
                    QMessageBox.information(self, "提示", "解密密钥已清除。")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存解密密钥失败：{e}")

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
        current_path = self.export_path_edit.text() or str(get_runtime_exports_dir())
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

    def sync_config(self):
        """手动同步配置"""
        # 确认窗口
        reply = QMessageBox.question(
            self,
            "确认同步",
            "确定要获取云端配置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        sync_url = self.data_manager.get_admin_config("basic_data", "交互设置", "配置同步URL")

        if not sync_url:
            QMessageBox.warning(
                self,
                "无法同步",
                "未配置同步URL。\n\n请联系支部管理员获取同步URL或配置文件。"
            )
            return

        try:
            self.sync_thread = ConfigSyncThread(self.data_manager, sync_url=sync_url, force=True)
            self.sync_thread.sync_completed.connect(self._on_sync_completed)
            self.sync_thread.sync_failed.connect(self._on_sync_failed)
            self.sync_thread.start()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"同步过程出错：{e}")
    
    def _on_sync_completed(self, message: str):
        self.data_manager.save_sync_result("success", message)
        self.load_settings()
        QMessageBox.information(self, "同步成功", f"管理员配置已更新。{message}")

    def _on_sync_failed(self, message: str):
        self.data_manager.save_sync_result("failed", message)
        self.load_settings()
        QMessageBox.critical(self, "同步失败", f"管理员配置同步失败：{message}")

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

    def check_for_updates(self):
        """检查应用更新"""
        if self.update_check_thread is not None and self.update_check_thread.isRunning():
            return

        self.check_update_btn.setEnabled(False)
        self.update_check_thread = UpdateCheckThread(
            current_version="v1.0.0",
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

        current_version = str(result.get("current_version", "v1.0.0"))
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
