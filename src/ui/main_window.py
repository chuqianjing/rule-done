#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
主窗口
"""

from pathlib import Path
import sys
import webbrowser
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QMessageBox,
    QFileDialog,
    QInputDialog,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QIcon
from src.ui.admin_home_page import AdminHomePage
from src.ui.admin_list_page import AdminListPage
from src.ui.admin_settings_page import AdminSettingsPage
from src.ui.admin_template_page import AdminTemplatePage
from src.ui.export_dialog import ExportDialog
from src.ui.member_home_page import MemberHomePage
from src.ui.member_list_page import MemberListPage
from src.ui.member_settings_page import MemberSettingsPage
from src.ui.member_template_page import MemberTemplatePage
from src.ui.password_dialog import PasswordInputDialog
from src.application.data_manager import DataManager
from src.application.permission_controller import PermissionController
from src.utils.config_sync_thread import ConfigSyncThread
from src.utils.update_check_thread import UpdateCheckThread
from src.utils.styles import MAIN_STYLESHEET, NAV_SIDEBAR_STYLESHEET, ICONS


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()

        self.data_manager = DataManager()
        self.permission_controller = PermissionController()
        self.current_mode = self.permission_controller.detect_mode()

        # 成员模式页面缓存
        self.member_home_page: MemberHomePage | None = None
        self.member_list_page: MemberListPage | None = None
        self.member_template_pages: dict[str, MemberTemplatePage] = {}
        self.member_settings_page: MemberSettingsPage | None = None

        # 管理员模式页面缓存
        self.admin_home_page: AdminHomePage | None = None
        self.admin_list_page: AdminListPage | None = None
        self.admin_template_pages: dict[str, AdminTemplatePage] = {}
        self.admin_settings_page: AdminSettingsPage | None = None
        self.update_check_thread: UpdateCheckThread | None = None

        # 检查是否需要密码验证
        if not self._check_password_on_startup():
            sys.exit(0)
        
        self.init_ui()
        if self.current_mode == "member":
            self.check_config_sync_on_startup()
        self.load_appropriate_page()
        # 延后到窗口初始化完成后再检查更新，避免构造期并发弹窗/线程竞态
        QTimer.singleShot(0, self.check_updates_on_startup)

    def _check_password_on_startup(self) -> bool:
        """
        程序启动时检查是否需要密码验证

        Returns:
            是否验证成功（或无需验证）
        """
        # 根据当前模式检查相应的数据文件是否加密
        if self.current_mode == "admin":
            # 管理员模式检查 admin_config.json
            if not self.data_manager.has_password("admin"):
                return True  # 未加密，无需验证

            # 弹出密码输入对话框
            max_attempts = 3
            for attempt in range(max_attempts):
                dialog = PasswordInputDialog(mode="admin")
                if dialog.exec() != dialog.DialogCode.Accepted:
                    return False  # 用户取消

                password = dialog.get_password()
                if self.data_manager.verify_password("admin", password):
                    # 密码正确，缓存密码
                    self.data_manager.set_password("admin", password)
                    return True

                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    QMessageBox.warning(
                        None,
                        "密码错误",
                        f"密码不正确，请重试。\n\n剩余尝试次数：{remaining}"
                    )
                else:
                    QMessageBox.critical(
                        None,
                        "验证失败",
                        "密码验证失败次数过多，将退出应用。"
                    )
            return False

        elif self.current_mode == "member":
            # 成员模式检查 member_info.json
            if not self.data_manager.has_password("member"):
                return True  # 未加密，无需验证

            # 弹出密码输入对话框
            max_attempts = 3
            for attempt in range(max_attempts):
                dialog = PasswordInputDialog(mode="member")
                if dialog.exec() != dialog.DialogCode.Accepted:
                    return False  # 用户取消

                password = dialog.get_password()
                if self.data_manager.verify_password("member", password):
                    # 密码正确，缓存密码
                    self.data_manager.set_password("member", password)
                    return True

                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    QMessageBox.warning(
                        None,
                        "密码错误",
                        f"密码不正确，请重试。\n\n剩余尝试次数：{remaining}"
                    )
                else:
                    QMessageBox.critical(
                        None,
                        "验证失败",
                        "密码验证失败次数过多，将退出应用   。"
                    )
            return False

        # 用户模式或其他模式，无需验证
        return True

    def init_ui(self):
        """初始化 UI"""
        icon_path = Path(__file__).resolve().parents[2] / "resources" / "icons" / "logo.ico"
        self.setWindowIcon(QIcon(str(icon_path)))
        
        self.setWindowTitle("入档 • 党员发展档案管理工具")
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(MAIN_STYLESHEET)

        # 创建主容器
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 侧边导航栏
        self.nav_widget = self._create_nav_sidebar()
        main_layout.addWidget(self.nav_widget)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedWidth(1)
        separator.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(separator)

        # 内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 堆叠窗口（用于页面切换），self.stacked_widget用以控制页面切换
        self.stacked_widget = QStackedWidget()

        content_layout.addWidget(self.stacked_widget)
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget, 1)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 页面切换时同步导航栏选择
        self.stacked_widget.currentChanged.connect(self._sync_nav)
    
    # ==================== 侧边栏导航相关 ====================  

    def _sync_nav(self, index):
        page = self.stacked_widget.widget(index)
        # 阻止信号，避免循环触发
        self.nav_list.blockSignals(True)
        if isinstance(page, MemberHomePage) or isinstance(page, AdminHomePage):
            self.nav_list.setCurrentRow(0)
        elif isinstance(page, AdminListPage) or isinstance(page, MemberListPage):
            self.nav_list.setCurrentRow(1)
        elif isinstance(page, AdminSettingsPage) or isinstance(page, MemberSettingsPage):
            self.nav_list.setCurrentRow(2)
        else:
            self.nav_list.setCurrentRow(-1)  # 当前页面没有对应导航项时取消选择，不能用clearSelection()，这个操作并不会改变item
        # 恢复信号
        self.nav_list.blockSignals(False)

    def _create_nav_sidebar(self) -> QWidget:
        """创建侧边导航栏"""
        nav_widget = QWidget()
        nav_widget.setObjectName("nav_sidebar")
        nav_widget.setFixedWidth(200)
        nav_widget.setStyleSheet(NAV_SIDEBAR_STYLESHEET)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题区域
        title = QLabel(f"{ICONS['templates']} 工具导航栏")
        title.setObjectName("nav_title")
        layout.addWidget(title)

        # 导航列表
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("nav_list")
        self.nav_items = {
            "home": QListWidgetItem(f"{ICONS['home']} 基本信息"),
            "templates": QListWidgetItem(f"{ICONS['folder']} 材料模板"),
            "settings": QListWidgetItem(f"{ICONS['settings']} 通用设置"),
        }
        for item in self.nav_items.values():
            self.nav_list.addItem(item)
        
        # 导航项变化时触发页面切换
        self.nav_list.currentItemChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav_list)

        layout.addStretch()
        # 侧边栏图片展示区
        layout.addWidget(self._create_nav_showcase())
        layout.addStretch()

        # 底部版本信息
        version_label = QLabel("v1.0.0")
        version_label.setStyleSheet("color: #999; padding: 15px; font-size: 12px;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        layout.addSpacing(-25)
        copyright_label = QLabel("Copyright (c) 2026 楚乾靖")
        copyright_label.setStyleSheet("color: #999; padding: 15px; font-size: 12px;")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)

        nav_widget.setLayout(layout)

        return nav_widget

    def _create_nav_showcase(self) -> QWidget:
        """创建侧边栏图片展示区。"""
        showcase_widget = QWidget()

        showcase_layout = QVBoxLayout()
        showcase_layout.setContentsMargins(14, 8, 14, 8)
        showcase_layout.setSpacing(8)

        image_label = QLabel()
        image_label.setObjectName("nav_image_label")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        quote_pixmap = self._load_nav_showcase_pixmap(200, 500)
        if quote_pixmap is not None:
            image_label.setPixmap(quote_pixmap)
            #image_label.setFixedHeight(500)
            showcase_layout.addWidget(image_label)

        showcase_widget.setLayout(showcase_layout)
        return showcase_widget

    def _load_nav_showcase_pixmap(self, width: int, height: int) -> QPixmap | None:
        """加载资源图片"""
        resource_path = Path(__file__).resolve().parents[2] / "resources" / "images" / "sidebar_showcase.png"
        custom_pixmap = QPixmap(str(resource_path))
        if not custom_pixmap.isNull():
            return custom_pixmap.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return None

    def _on_nav_changed(self, current, previous):
        """导航项变化处理"""
        if current is None:
            return
        if current == self.nav_items.get("home"):
            if self.current_mode == "admin":
                self.show_admin_home_page()
            else:
                self.show_member_home_page()
        elif current == self.nav_items.get("templates"):
            if self.current_mode == "admin":
                self.show_admin_list_page()
            else:
                self.show_member_list_page()
        elif current == self.nav_items.get("settings"):
            if self.current_mode == "admin":
                self.show_admin_settings_page()
            else:
                self.show_member_settings_page()
    
    # ==================== 页面切换 ====================

    def load_appropriate_page(self):
        """根据当前模式加载对应页面"""
        if self.current_mode == "user":
            self._handle_user_startup()
        elif self.current_mode == "admin":
            self.show_admin_home_page()
        else:
            self.show_member_home_page()
    
    # ==================== 用户模式引导 ====================

    def _handle_user_startup(self):
        """初始模式下的启动引导：选择管理员 / 成员角色"""
        role_box = QMessageBox(self)
        role_box.setWindowTitle("选择身份")
        role_box.setText("当前为初始模式，请先选择身份：" + " " * 30)
        admin_btn = role_box.addButton("党支部管理员", QMessageBox.ButtonRole.AcceptRole)
        member_btn = role_box.addButton("发展成员", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = role_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        role_box.exec()

        clicked = role_box.clickedButton()
        if clicked is admin_btn:
            # 初始化 system_settings.json，设置为管理员模式
            self.permission_controller.initialize_settings('admin')
            self.current_mode = "admin"
            self.show_admin_home_page()

        elif clicked is member_btn:
            # 初始化 system_settings.json，设置为成员模式
            self.permission_controller.initialize_settings('member')
            self.current_mode = "member"
            if self._prepare_admin_config_for_member():     # 先获取支部管理员配置
                self.show_member_home_page()
            else:
                sys.exit(0)
        else:
            sys.exit(0)   # 直接退出程序，不要用self.close()、避免点击“取消后”出现空白UI界面

    def _prepare_admin_config_for_member(self) -> bool:
        """
        为“成员体验”准备 admin_config.json：
        - 让用户选择：本地导入 / 通过 URL 同步
        - 成功写入配置后返回 True
        """
        choice_box = QMessageBox(self)
        choice_box.setWindowTitle("获取管理员配置")
        choice_box.setText("请选择如何获取管理员配置：" + " " * 50)
        sync_btn = choice_box.addButton("从URL云端同步", QMessageBox.ButtonRole.AcceptRole)
        import_btn = choice_box.addButton("从本地文件导入", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = choice_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        choice_box.exec()

        clicked = choice_box.clickedButton()
        if clicked is import_btn:
            return self._user_import_admin_config()
        if clicked is sync_btn:
            return self._user_pull_admin_config_from_remote()
        return False

    def _user_import_admin_config(self) -> bool:
        """用户模式：以成员身份从本地导入管理员配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择管理员配置的JSON文件",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)",
        )
        if not file_path:
            return False
        try:
            message = self.data_manager.import_admin_config(file_path)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入过程中出错：{e}")
            return False
        QMessageBox.information(self, "导入成功", f"管理员配置已成功导入。{message}")
        return True

    def _user_pull_admin_config_from_remote(self) -> bool:
        """用户模式：以成员身份通过 URL 同步管理员配置"""
        url, ok = QInputDialog.getText(
            self,
            "配置URL",
            "请输入管理员配置JSON的URL：",
        )
        if not ok or not url.strip():
            return False

        sync_url = url.strip()
        try:
            message = self.data_manager.pull_admin_config_from_remote(sync_url)
        except Exception as e:
            QMessageBox.critical(self, "同步失败", f"同步过程出错：{e}")
            return False
        if message == "无需更新":
            return True
        QMessageBox.information(self, "同步成功", f"管理员配置已从远程URL同步到本地。{message}")
        return True
    
    # ==================== 主页和列表页 ====================
    # 如果页面存在（即通过成员属性进行了缓存），再次显示时调用load_data相关函数刷新数据，确保页面数据是最新的

    def show_admin_home_page(self):
        """显示管理员配置页面（支持导航到模板配置）"""
        if self.admin_home_page is None:
            self.admin_home_page = AdminHomePage()
            self.admin_home_page.go_to_template_list.connect(self.show_admin_list_page)
            self.stacked_widget.addWidget(self.admin_home_page)
        else:
            self.admin_home_page.load_data()
        self.stacked_widget.setCurrentWidget(self.admin_home_page)
        self.status_bar.showMessage("管理员模式：可配置支部基础信息和模板通用字段")

    def show_member_home_page(self):
        if self.member_home_page is None:
            self.member_home_page = MemberHomePage()
            self.member_home_page.go_to_template_list.connect(self.show_member_list_page)
            self.stacked_widget.addWidget(self.member_home_page)
        else:
            self.member_home_page.load_data()
        self.stacked_widget.setCurrentWidget(self.member_home_page)
        self.status_bar.showMessage("成员模式：请先在首页填写基本信息，然后在模板页面中完善并导出材料文件")

    def show_member_list_page(self):
        if self.member_list_page is None:
            self.member_list_page = MemberListPage()
            self.member_list_page.open_template.connect(self.open_member_template_page)
            self.member_list_page.export_templates.connect(self.open_export_dialog_for_ids)
            self.stacked_widget.addWidget(self.member_list_page)
        else:
            self.member_list_page.load_templates()
        self.stacked_widget.setCurrentWidget(self.member_list_page)

    def show_admin_list_page(self):
        """显示管理员模式的模板列表页面"""
        if self.admin_list_page is None:
            self.admin_list_page = AdminListPage()
            self.admin_list_page.open_template.connect(self.open_admin_template_page)
            self.stacked_widget.addWidget(self.admin_list_page)
        else:
            self.admin_list_page.load_templates()
        self.stacked_widget.setCurrentWidget(self.admin_list_page)
    
    def show_admin_settings_page(self):
        """管理员模式的系统设置页面"""
        if self.admin_settings_page is None:
            self.admin_settings_page = AdminSettingsPage()
            self.admin_settings_page.before_mode_changed.connect(self._before_mode_changed)
            self.admin_settings_page.mode_changed.connect(self._on_mode_changed)
            self.stacked_widget.addWidget(self.admin_settings_page)
        else:
            self.admin_settings_page.load_settings()
        self.stacked_widget.setCurrentWidget(self.admin_settings_page)

    def show_member_settings_page(self):
        """成员模式的设置页面"""
        if self.member_settings_page is None:
            self.member_settings_page = MemberSettingsPage()
            self.member_settings_page.before_mode_changed.connect(self._before_mode_changed)
            self.member_settings_page.mode_changed.connect(self._on_mode_changed)
            self.stacked_widget.addWidget(self.member_settings_page)
        else:
            self.member_settings_page.load_settings()
        self.stacked_widget.setCurrentWidget(self.member_settings_page)
    
    def _before_mode_changed(self, new_mode: str):
        """即将切换模式时的回调，执行必要的清理工作，以及密码校验工作"""
        # 这里可以根据 current_mode 来判断是从哪个模式切换过来，进行针对性的清理
        self.current_mode = new_mode
        self.permission_controller.current_mode = new_mode
        if new_mode == "admin":
            if not self._check_password_on_startup():
                self.current_mode = "member"  # 切换回成员模式
                self.permission_controller.current_mode = "member"
                QMessageBox.critical(self, "验证失败", "密码验证失败，无法切换模式。")
                sys.exit(0)
            # 从管理员模式切换到成员模式，清理管理员页面缓存
            self.member_home_page = None
            self.member_list_page = None
            self.member_template_pages = {}
            self.member_settings_page = None
        elif new_mode == "member":
            if not self._check_password_on_startup():
                self.current_mode = "admin"  # 切换回管理员模式
                self.permission_controller.current_mode = "admin"
                QMessageBox.critical(self, "验证失败", "密码验证失败，无法切换模式。")
                sys.exit(0)
            # 从成员模式切换到管理员模式，清理成员页面缓存
            self.admin_home_page = None
            self.admin_list_page = None
            self.admin_template_pages = {}
            self.admin_settings_page = None

    def _on_mode_changed(self, new_mode: str):
        """模式切换时的回调，重新加载主界面"""
        self.current_mode = new_mode
        self.permission_controller.current_mode = new_mode
        
        # 根据新模式加载对应页面
        if new_mode == "admin":
            self.show_admin_home_page()
        else:
            self.show_member_home_page()

    # ==================== 模板页面相关 ====================

    def open_member_template_page(self, template_id: str):
        # 缓存每个模板对应的页面
        if template_id not in self.member_template_pages:
            page = MemberTemplatePage(template_id)
            page.back_to_list_page.connect(self.show_member_list_page)
            page.lock_document_signal.connect(self._load_member_template_page_after_lock)
            self.member_template_pages[template_id] = page
            self.stacked_widget.addWidget(page)
        else:
            self.member_template_pages[template_id].load_mapping()
            self.member_template_pages[template_id].build_template_forms()
            self.member_template_pages[template_id].load_data()
        self.stacked_widget.setCurrentWidget(self.member_template_pages[template_id])
    
    def _load_member_template_page_after_lock(self):
        """成员模板页锁定后重新加载页面以更新界面状态"""
        current_page = self.stacked_widget.currentWidget()
        if isinstance(current_page, MemberTemplatePage):
            template_id = current_page.template_id
            # 重新创建页面实例并替换原有页面，以确保界面状态完全更新（如表单框样式）
            new_page = MemberTemplatePage(template_id)
            new_page.back_to_list_page.connect(self.show_member_list_page)
            new_page.lock_document_signal.connect(self._load_member_template_page_after_lock)
            self.member_template_pages[template_id] = new_page
            self.stacked_widget.addWidget(new_page)
            self.stacked_widget.setCurrentWidget(new_page)
    
    def open_admin_template_page(self, template_id: str):
        """打开管理员模式的模板页面"""
        if template_id not in self.admin_template_pages:
            page = AdminTemplatePage(template_id)
            page.back_to_list_page.connect(self.show_admin_list_page)
            self.admin_template_pages[template_id] = page
            self.stacked_widget.addWidget(page)
        else:
            self.admin_template_pages[template_id].load_data()
        self.stacked_widget.setCurrentWidget(self.admin_template_pages[template_id])

    def open_export_dialog_for_ids(self, template_ids: list[str]):
        """按指定模板列表打开导出对话框"""
        dlg = ExportDialog(template_ids=template_ids, parent=self)
        dlg.exec()

    # ========== 同步==========

    def check_config_sync_on_startup(self):
        """（成员态下）程序启动时检查配置同步"""
        sync_url = self.data_manager.get_admin_config("basic_data", "交互设置", "配置同步URL")
        if sync_url and str(sync_url).strip():
            # 在后台线程中检查同步，避免阻塞 UI
            try:
                self.sync_thread = ConfigSyncThread(self.data_manager, mode="pull", sync_url=str(sync_url).strip())
                self.sync_thread.sync_completed.connect(self.on_sync_completed)
                self.sync_thread.sync_failed.connect(self.on_sync_failed)
                self.sync_thread.start()
            except Exception as e:
                QMessageBox.warning(self, "同步失败", f"启动时同步云端配置失败：{e}")
    
    def on_sync_completed(self, message: str):
        """配置同步完成回调"""
        if message != "无需更新":
            QMessageBox.information(
                self,
                "配置已更新",
                f"管理员配置已自动同步更新。\n\n{message}"
            )
            # 尝试刷新当前页面数据，忽略可能的属性错误
            current_widget = self.stacked_widget.currentWidget()
            if hasattr(current_widget, 'load_data'):
                current_widget.load_data()
    
    def on_sync_failed(self, error_message: str):
        """配置同步失败回调"""
        QMessageBox.warning(self, "同步失败", f"启动时同步云端配置失败：{error_message}")

    def check_updates_on_startup(self):
        """检查应用更新"""
        if self.update_check_thread is not None and self.update_check_thread.isRunning():
            return

        self.update_check_thread = UpdateCheckThread(
            current_version="v1.0.0",
            release_url="https://github.com/chuqianjing/rule-done/releases/latest",
            project_url="https://github.com/chuqianjing/rule-done",
        )
        self.update_check_thread.result_ready.connect(self._on_startup_update_check_completed)
        self.update_check_thread.failed.connect(self._on_startup_update_check_failed)
        self.update_check_thread.start()

    def _cleanup_update_check_thread(self):
        """安全释放更新线程，避免线程未结束即销毁导致进程退出。"""
        if self.update_check_thread is None:
            return

        if self.update_check_thread.isRunning():
            self.update_check_thread.wait(2000)

        self.update_check_thread.deleteLater()
        self.update_check_thread = None

    def _on_startup_update_check_completed(self, result: dict):
        """启动时更新检查完成回调"""
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
                f"{project_url}"
            )
        self._cleanup_update_check_thread()

    def _on_startup_update_check_failed(self, message: str):
        """启动时更新检查失败回调"""
        print(f"检查更新失败: {message}")
        self._cleanup_update_check_thread()



