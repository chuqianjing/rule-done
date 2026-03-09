#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统设置页面
管理员态和学生态有不同的设置界面
"""

from PyQt6.QtWidgets import (
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
from PyQt6.QtCore import pyqtSignal
from datetime import datetime
from pathlib import Path
from src.business.data_manager import DataManager
from src.business.permission_controller import PermissionController
from src.ui.styles import TIP_STYLE, ICONS


class StudentSettingsPage(QWidget):
    """学生态系统设置页面"""

    # 配置变更信号
    config_changed = pyqtSignal()  # 参数为数据源
    # 请求同步信号
    sync_requested = pyqtSignal()
    # 学生数据变更信号
    student_data_changed = pyqtSignal()
    # 模式切换信号，通知主窗口重新加载
    mode_changed = pyqtSignal(str)

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
        title = QLabel(f"{ICONS['settings']} 当前模式：党支部发展成员")
        title.setObjectName("title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        main_layout.addWidget(title)

        # 提示信息
        tip_label = QLabel(f"{ICONS['info']} 在此管理支部配置同步和导出设置")
        tip_label.setStyleSheet(TIP_STYLE)
        tip_label.setWordWrap(True)
        main_layout.addWidget(tip_label)

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
        config_group = QGroupBox(f"{ICONS['pin']} 支部配置管理")
        config_form = QVBoxLayout()
        config_form.setSpacing(10)
        config_form.setContentsMargins(15, 20, 15, 15)

        # 同步状态显示
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("配置状态："))
        self.sync_status_label = QLabel("使用默认配置")
        self.sync_status_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.sync_status_label)
        status_layout.addStretch()
        config_form.addLayout(status_layout)

        # 同步时间
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("上次配置："))
        self.sync_time_label = QLabel("-")
        self.sync_time_label.setStyleSheet("color: #666;")
        time_layout.addWidget(self.sync_time_label)
        time_layout.addStretch()
        config_form.addLayout(time_layout)

        # 操作按钮
        config_btn_layout = QHBoxLayout()
        sync_btn = QPushButton(f"{ICONS['sync']} 手动云端同步")
        sync_btn.clicked.connect(self.sync_config)
        config_btn_layout.addWidget(sync_btn)

        import_btn = QPushButton(f"{ICONS['import']} 本地文件导入")
        import_btn.setObjectName("secondary")
        import_btn.clicked.connect(self.import_config)
        config_btn_layout.addWidget(import_btn)

        config_btn_layout.addStretch()
        config_form.addLayout(config_btn_layout)

        config_info = QLabel("提示：支部配置由管理员设置，应用启动时会自动同步。如需立即获取最新配置，可点击手动同步或本地导入。")
        config_info.setStyleSheet("color: #666; font-size: 12px;")
        config_info.setWordWrap(True)
        config_form.addWidget(config_info)

        config_group.setLayout(config_form)
        scroll_layout.addWidget(config_group)

        # === 导出设置 ===
        export_group = QGroupBox(f"{ICONS['export']} Word 文件导出")
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

        export_info = QLabel("提示：生成的 Word 文档材料将保存到此目录。")
        export_info.setStyleSheet("color: #666; font-size: 12px;")
        export_info.setWordWrap(True)
        export_form.addRow("", export_info)

        export_group.setLayout(export_form)
        scroll_layout.addWidget(export_group)

        # === 数据管理 ===
        data_group = QGroupBox(f"{ICONS['templates']} 个人数据管理")
        data_form = QVBoxLayout()
        data_form.setSpacing(10)
        data_form.setContentsMargins(15, 20, 15, 15)

        data_btn_layout = QHBoxLayout()
        export_data_btn = QPushButton(f"{ICONS['export']} 导出数据")
        export_data_btn.setObjectName("secondary")
        export_data_btn.clicked.connect(self.export_student_data)
        data_btn_layout.addWidget(export_data_btn)

        import_data_btn = QPushButton(f"{ICONS['import']} 导入数据")
        import_data_btn.setObjectName("secondary")
        import_data_btn.clicked.connect(self.import_student_data)
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
        mode_group = QGroupBox(f"{ICONS['lock']} 模式管理")
        mode_form = QVBoxLayout()
        mode_form.setSpacing(10)
        mode_form.setContentsMargins(15, 20, 15, 15)

        # 当前模式状态显示
        mode_status_layout = QHBoxLayout()
        mode_status_layout.addWidget(QLabel("当前模式："))
        self.mode_status_label = QLabel("成员模式")
        self.mode_status_label.setStyleSheet("color: #f9ab00; font-weight: bold;")
        mode_status_layout.addWidget(self.mode_status_label)
        mode_status_layout.addStretch()
        mode_form.addLayout(mode_status_layout)

        # 切换按钮
        mode_btn_layout = QHBoxLayout()
        self.switch_to_admin_btn = QPushButton(f"{ICONS['unlock']} 切换到管理员模式")
        self.switch_to_admin_btn.setObjectName("secondary")
        self.switch_to_admin_btn.clicked.connect(self.switch_to_admin_mode)
        mode_btn_layout.addWidget(self.switch_to_admin_btn)
        mode_btn_layout.addStretch()
        mode_form.addLayout(mode_btn_layout)

        mode_info = QLabel("提示：切换到管理员模式需要相应权限，程序将重新加载为管理员界面。")
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

        about_form.addRow("应用版本：", QLabel("v1.0.0"))
        about_form.addRow("配置版本：", QLabel(self.data_manager.get_admin_config().get("version", "1.0")))

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
        allow_switch = config.get("系统设置", {}).get("允许成员切换模式", "禁止")
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
        student_data = self.data_manager.get_student_data()
        export_path = student_data.get("settings", {}).get("export_path", "./exports")
        self.export_path_edit.setText(export_path)

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

    def save_settings(self):
        """保存设置"""
        pass

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
        
            # 导出路径保存到学生数据中
            student_data = self.data_manager.get_student_data()
            if "settings" not in student_data:
                student_data["settings"] = {}
            
            export_path = self.export_path_edit.text().strip() or "./exports"
            student_data["settings"]["export_path"] = export_path
            
            # 确保导出目录存在
            Path(export_path).mkdir(parents=True, exist_ok=True)
            
            self.data_manager.save_student_data(student_data)

    def sync_config(self):
        """手动同步配置"""
        config = self.data_manager.get_admin_config()
        sync_url = config.get("system_settings", {}).get("config_sync_url", "")

        if not sync_url:
            QMessageBox.warning(
                self,
                "无法同步",
                "未配置同步 URL。\n\n请联系支部管理员获取配置文件或同步 URL。"
            )
            return

        try:
            success, message = self.data_manager.sync_admin_config(sync_url, force=True)
            if success:
                self.load_settings()
                QMessageBox.information(self, "同步成功", f"支部配置已更新。\n\n{message}")
                self.config_changed.emit()
            else:
                if "无需更新" in message or "最新" in message:
                    QMessageBox.information(self, "提示", "本地配置已是最新版本。")
                else:
                    QMessageBox.warning(self, "同步失败", f"无法同步配置：\n{message}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"同步过程出错：{e}")

    def import_config(self):
        """从文件导入支部配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入支部配置",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        is_success, message = self.data_manager.import_admin_config(file_path, mode='student')
        if is_success:
            self.load_settings()
            QMessageBox.information(self, "提示", f"支部配置已导入并锁定。\n\n{message}")
            self.config_changed.emit()
        else:
            QMessageBox.warning(self, "错误", f"导入失败：{message}")

    def export_student_data(self):
        """导出学生个人数据"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出个人数据",
            "student_data.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        is_success, message = self.data_manager.export_student_data(file_path)
        if is_success:
            QMessageBox.information(self, "提示", f"个人数据已导出成功！\n\n{message}")
        else:
            QMessageBox.critical(self, "错误", f"导出失败：{message}")

    def import_student_data(self):
        """导入学生个人数据"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入个人数据",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return
        
        is_success, message = self.data_manager.import_student_data(file_path)
        if is_success:
            self.load_settings()
            QMessageBox.information(self, "提示", "个人数据已导入成功！")
            self.student_data_changed.emit("student")
        else:
            QMessageBox.warning(self, "错误", f"导入失败：{message}")

    def switch_to_admin_mode(self):
        """切换到管理员模式"""
        reply = QMessageBox.question(
            self,
            "确认切换",
            "切换到管理员模式后，程序将重新加载为管理员界面。\n\n确定要切换吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            # TODO: 可在此添加密码验证逻辑
            if self.permission_controller.switch_to_admin_mode():
                #self.mode_status_label.setText("管理员模式")
                #self.mode_status_label.setStyleSheet("color: #34a853; font-weight: bold;")
                self.mode_changed.emit("admin")
                QMessageBox.information(self, "提示", "已切换到管理员模式，程序将重新加载。")
            else:
                QMessageBox.critical(self, "错误", "切换模式失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"切换模式失败：{e}")
