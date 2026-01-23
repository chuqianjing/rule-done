#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主窗口
"""

from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QStatusBar, QMessageBox
from PyQt6.QtCore import Qt

from src.business.permission_controller import PermissionController
from src.ui.basic_info_page import BasicInfoPage
from src.ui.admin_config_page import AdminConfigPage
from src.ui.template_page import TemplatePage


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        
        self.permission_controller = PermissionController()
        self.current_mode = self.permission_controller.detect_mode()
        
        self.init_ui()
        self.load_appropriate_page()
    
    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("党员发展材料生成系统")
        self.setMinimumSize(800, 600)
        
        # 创建堆叠窗口（用于页面切换）
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def load_appropriate_page(self):
        """根据当前模式加载对应页面"""
        if self.current_mode in ['developer', 'admin']:
            # 开发者态或管理员态：显示管理员配置页面
            admin_page = AdminConfigPage()
            self.stacked_widget.addWidget(admin_page)
            self.stacked_widget.setCurrentWidget(admin_page)
        else:
            # 学生态：显示基本信息页面
            basic_info_page = BasicInfoPage()
            self.stacked_widget.addWidget(basic_info_page)
            self.stacked_widget.setCurrentWidget(basic_info_page)

            # 在菜单或后续可以增加入口，这里简单在启动后提示用户可通过菜单进入模板填写
            self.status_bar.showMessage("请先在首页填写基本信息，然后在模板页面中填写并导出 Word。")

