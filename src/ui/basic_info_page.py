#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基本信息页面
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

from src.business.data_manager import DataManager
from src.business.permission_controller import PermissionController


class BasicInfoPage(QWidget):
    """基本信息页面类"""
    
    def __init__(self):
        super().__init__()
        
        self.data_manager = DataManager()
        self.permission_controller = PermissionController()
        
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("基本信息填写")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # TODO: 添加表单字段
        # 这里将根据 fields_definition.json 动态生成表单
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_data)
        layout.addWidget(save_btn)
        
        self.setLayout(layout)
    
    def load_data(self):
        """加载数据"""
        # TODO: 实现数据加载逻辑
        pass
    
    def save_data(self):
        """保存数据"""
        # TODO: 实现数据保存逻辑
        self.status_message("数据已保存")

