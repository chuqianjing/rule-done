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
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QThread, pyqtSignal, Qt
import sys

from src.ui.styles import MAIN_STYLESHEET, NAV_SIDEBAR_STYLESHEET, ICONS

from src.business.permission_controller import PermissionController
from src.ui.basic_info_page import BasicInfoPage
from src.ui.admin_config_page import AdminConfigPage
from src.ui.template_list_page import TemplateListPage
from src.ui.template_page import TemplatePage
from src.ui.export_dialog import ExportDialog
from src.data.config_manager import ConfigManager
from src.business.data_manager import DataManager

class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()

        self.data_manager = DataManager()
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
        self.setMinimumSize(1100, 700)

        # 应用全局样式
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

        # 堆叠窗口（用于页面切换）
        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget, 1)  # 拉伸占满剩余空间

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 菜单栏（作为备用导航）
        self._create_menu_bar()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        self.stacked_widget.currentChanged.connect(self._sync_nav)
    
    def _sync_nav(self, index):
        page = self.stacked_widget.widget(index)
        if isinstance(page, BasicInfoPage):
            self.nav_list.setCurrentRow(0)
        elif isinstance(page, TemplateListPage):
            self.nav_list.setCurrentRow(1)
        else:
            self.nav_list.setCurrentRow(-1)  # 没有对应导航项时取消选择，不能用clearSelection()，这个操作并不会改变item

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
        title = QLabel(f"{ICONS['templates']} 党员材料系统")
        title.setObjectName("nav_title")
        layout.addWidget(title)

        # 导航列表
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("nav_list")
        
        # 定义导航项
        self.nav_items = {
            "home": QListWidgetItem(f"{ICONS['home']} 基本信息"),
            "templates": QListWidgetItem(f"{ICONS['template']} 模板列表"),
            "export": QListWidgetItem(f"{ICONS['export']} 批量导出"),
        }

        for item in self.nav_items.values():
            self.nav_list.addItem(item)

        self.nav_list.currentItemChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav_list)

        layout.addStretch()

        # 底部版本信息
        version_label = QLabel("v1.0.0")
        version_label.setStyleSheet("color: #999; padding: 15px; font-size: 12px;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        nav_widget.setLayout(layout)
        return nav_widget

    def _on_nav_changed(self, current, previous):
        """导航项变化处理"""
        if current is None:
            return
        if current == self.nav_items.get("home"):
            self.show_basic_info_page()
        elif current == self.nav_items.get("templates"):
            self.show_template_list_page()
        elif current == self.nav_items.get("export"):
            self.open_export_dialog_all()

    def _create_menu_bar(self):
        """创建菜单栏"""
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

    def load_appropriate_page(self):
        """根据当前模式加载对应页面"""
        if self.current_mode == "developer":
            self._handle_developer_startup()

        elif self.current_mode == "admin":
            self.show_admin_config_page()

        else:
            self.show_basic_info_page()
    
    def show_admin_config_page(self):
        """直接显示管理员配置页面（开发者模式下选择管理员体验时调用）"""
        admin_page = AdminConfigPage()
        self.stacked_widget.addWidget(admin_page)
        self.stacked_widget.setCurrentWidget(admin_page)

        # 管理员态下不需要学生导航菜单
        self.action_home.setEnabled(False)
        self.action_templates.setEnabled(False)
        self.action_export_all.setEnabled(False)
        
        # 隐藏侧边导航栏（管理员模式不需要）
        self.nav_widget.setVisible(False)
        
        self.status_bar.showMessage("当前为管理员配置模式，请先完成并锁定配置。")

    # 页面切换相关方法
    def show_basic_info_page(self):
        if self.basic_info_page is None:
            self.basic_info_page = BasicInfoPage()
            self.basic_info_page.go_to_template_list.connect(self.show_template_list_page)
            self.stacked_widget.addWidget(self.basic_info_page)
        self.stacked_widget.setCurrentWidget(self.basic_info_page)
        self.action_home.setEnabled(True)
        self.action_templates.setEnabled(True)
        self.action_export_all.setEnabled(True)
        self.status_bar.showMessage("请先在首页填写基本信息，然后在模板页面中填写并导出 Word。")

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

    # 开发者模式引导
    def _handle_developer_startup(self):
        """开发者模式下的启动引导：选择管理员 / 学生角色"""
        role_box = QMessageBox(self)
        role_box.setWindowTitle("选择角色")
        role_box.setText("当前为开发者模式，请选择要以哪种身份体验：")
        admin_btn = role_box.addButton("支部管理员", QMessageBox.ButtonRole.AcceptRole)
        student_btn = role_box.addButton("发展对象（学生）", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = role_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        role_box.exec()

        clicked = role_box.clickedButton()
        if clicked is admin_btn:
            self.show_admin_config_page()

        elif clicked is student_btn:
            # 以学生身份体验：先获取支部管理员配置
            if self._prepare_admin_config_for_student():
                self.show_basic_info_page()
            else:
                sys.exit(0)
        else:
            # 取消：直接关闭主窗口
            # self.close()
            sys.exit(0)   # 直接退出程序，避免点击“取消后”出现空白UI界面

    def _prepare_admin_config_for_student(self) -> bool:
        """
        为“学生体验”准备 admin_config.json：
        - 让用户选择：本地导入 / 通过 URL 同步
        - 成功写入配置后返回 True
        """
        choice_box = QMessageBox(self)
        choice_box.setWindowTitle("获取支部配置")
        choice_box.setText("请选择如何获取支部管理员配置：")
        import_btn = choice_box.addButton("从本地导入配置文件", QMessageBox.ButtonRole.AcceptRole)
        sync_btn = choice_box.addButton("通过 URL 同步配置", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = choice_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        choice_box.exec()

        clicked = choice_box.clickedButton()
        if clicked is import_btn:
            return self._developer_import_admin_config()
        if clicked is sync_btn:
            return self._developer_sync_admin_config()
        return False

    def _developer_import_admin_config(self) -> bool:
        """开发者模式：以学生身份从本地导入管理员配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择管理员配置 JSON 文件",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)",
        )
        if not file_path:
            return False
        
        success, message = self.data_manager.import_admin_config(file_path, mode='student')
        if success:
            QMessageBox.information(self, "导入成功", message)
        else:
            QMessageBox.critical(self, "导入失败", message)
        return success

    def _developer_sync_admin_config(self) -> bool:
        """开发者模式：以学生身份通过 URL 同步管理员配置"""
        url, ok = QInputDialog.getText(
            self,
            "配置 URL",
            "请输入管理员配置 JSON 的 URL：",
        )
        if not ok or not url.strip():
            return False

        sync_url = url.strip()
        try:
            success, message = self.data_manager.sync_admin_config(sync_url)
        except Exception as e:
            QMessageBox.critical(self, "同步失败", f"同步过程出错：{e}")
            return False

        if success:
            QMessageBox.information(self, "同步成功", f"支部配置已从远程 URL 同步到本地。\n\n{message}")
            return True

        # 不成功时给出提示，但仍然保留当前状态
        QMessageBox.warning(self, "同步失败", f"未能成功同步支部配置：\n{message}")
        return False

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

    # ========== 同步==========

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
            data_manager = DataManager()
            success, message = data_manager.sync_admin_config(self.sync_url)
            self.sync_completed.emit(success, message)
        except Exception as e:
            self.sync_completed.emit(False, f"同步过程出错：{e}")


