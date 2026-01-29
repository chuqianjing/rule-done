#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主窗口
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QMessageBox,
    QMenuBar,
    QMenu,
    #QAction,
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QThread, pyqtSignal

from src.business.permission_controller import PermissionController
from src.ui.basic_info_page import BasicInfoPage
from src.ui.admin_config_page import AdminConfigPage
from src.ui.template_list_page import TemplateListPage
from src.ui.template_page import TemplatePage
from src.ui.export_dialog import ExportDialog
from src.data.config_manager import ConfigManager


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()

        self.permission_controller = PermissionController()
        self.current_mode = self.permission_controller.detect_mode()

        # 页面缓存
        self.basic_info_page: BasicInfoPage | None = None
        self.template_list_page: TemplateListPage | None = None
        self.template_pages: dict[str, TemplatePage] = {}

        self.init_ui()
        self.check_config_sync_on_startup()
        self.load_appropriate_page()

    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("党员发展材料生成系统")
        self.setMinimumSize(960, 640)

        # 创建堆叠窗口（用于页面切换）
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # 菜单栏
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        nav_menu = QMenu("导航", self)
        menubar.addMenu(nav_menu)

        self.action_home = QAction("基本信息", self)
        self.action_home.triggered.connect(self.show_basic_info_page)
        nav_menu.addAction(self.action_home)

        self.action_templates = QAction("模板列表", self)
        self.action_templates.triggered.connect(self.show_template_list_page)
        nav_menu.addAction(self.action_templates)

        self.action_export_all = QAction("批量导出", self)
        self.action_export_all.triggered.connect(self.open_export_dialog_all)
        nav_menu.addAction(self.action_export_all)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def load_appropriate_page(self):
        """根据当前模式加载对应页面"""
        if self.current_mode in ["developer", "admin"]:
            # 开发者态或管理员态：显示管理员配置页面
            admin_page = AdminConfigPage()
            self.stacked_widget.addWidget(admin_page)
            self.stacked_widget.setCurrentWidget(admin_page)

            # 管理员态下不需要学生导航菜单
            self.action_home.setEnabled(False)
            self.action_templates.setEnabled(False)
            self.action_export_all.setEnabled(False)
            self.status_bar.showMessage("当前为管理员配置模式，请先完成并锁定配置。")
        else:
            # 学生态：显示基本信息页面，并启用导航
            self.show_basic_info_page()
            self.action_home.setEnabled(True)
            self.action_templates.setEnabled(True)
            self.action_export_all.setEnabled(True)
            self.status_bar.showMessage("请先在首页填写基本信息，然后在模板页面中填写并导出 Word。")

    # 页面切换相关方法
    def show_basic_info_page(self):
        if self.basic_info_page is None:
            self.basic_info_page = BasicInfoPage()
            self.basic_info_page.go_to_template_list.connect(self.show_template_list_page)
            self.stacked_widget.addWidget(self.basic_info_page)
        self.stacked_widget.setCurrentWidget(self.basic_info_page)

    def show_template_list_page(self):
        if self.template_list_page is None:
            self.template_list_page = TemplateListPage()
            self.template_list_page.open_template.connect(self.open_template_page)
            self.template_list_page.export_templates.connect(self.open_export_dialog_for_ids)
            self.stacked_widget.addWidget(self.template_list_page)
        else:
            # 每次打开时刷新模板列表，方便后续扩展
            self.template_list_page.load_templates()
        self.stacked_widget.setCurrentWidget(self.template_list_page)

    def open_template_page(self, template_id: str):
        # 缓存每个模板对应的页面
        if template_id not in self.template_pages:
            page = TemplatePage(template_id)
            self.template_pages[template_id] = page
            self.stacked_widget.addWidget(page)
        self.stacked_widget.setCurrentWidget(self.template_pages[template_id])

    # 导出相关
    def open_export_dialog_all(self):
        """打开导出对话框，包含所有模板"""
        dlg = ExportDialog(parent=self)
        dlg.exec()

    def open_export_dialog_for_ids(self, template_ids: list[str]):
        """按指定模板列表打开导出对话框"""
        dlg = ExportDialog(template_ids=template_ids, parent=self)
        dlg.exec()

    def check_config_sync_on_startup(self):
        """程序启动时检查配置同步（学生态/管理员态均支持）"""
        config_manager = ConfigManager()
        config = config_manager.load_config()

        sync_url = config.get("system_settings", {}).get("config_sync_url")
        if sync_url and str(sync_url).strip():
            # 在后台线程中检查同步，避免阻塞 UI
            self.sync_thread = ConfigSyncThread(config_manager, str(sync_url).strip())
            self.sync_thread.sync_completed.connect(self.on_sync_completed)
            self.sync_thread.start()
    
    def on_sync_completed(self, success: bool, message: str):
        """配置同步完成回调"""
        if success:
            QMessageBox.information(
                self,
                "配置已更新",
                f"支部配置已自动同步更新。\n\n{message}"
            )
            # 如果当前在管理员配置页面，刷新显示
            current_widget = self.stacked_widget.currentWidget()
            if isinstance(current_widget, AdminConfigPage):
                current_widget.load_config()
            # 如果当前在学生首页，刷新展示（尤其是支部信息、日期格式）
            if isinstance(current_widget, BasicInfoPage):
                try:
                    current_widget.admin_config = ConfigManager().load_config()
                    # 日期格式可能变化，需要重建表单以应用新的 displayFormat
                    current_widget.build_student_form()
                    current_widget.load_data()
                except Exception:
                    pass
        # 同步失败时不显示错误（避免干扰用户），仅在控制台输出
        elif "无需更新" not in message:
            # 只在非"无需更新"的情况下记录日志
            print(f"配置同步检查：{message}")


class ConfigSyncThread(QThread):
    """配置同步后台线程"""
    sync_completed = pyqtSignal(bool, str)
    
    def __init__(self, config_manager, sync_url):
        super().__init__()
        self.config_manager = config_manager
        self.sync_url = sync_url
    
    def run(self):
        """执行同步检查"""
        try:
            from src.utils.config_sync import ConfigSync
            sync_manager = ConfigSync(self.config_manager)
            success, message = sync_manager.check_and_sync(self.sync_url)
            self.sync_completed.emit(success, message)
        except Exception as e:
            self.sync_completed.emit(False, f"同步过程出错：{e}")


