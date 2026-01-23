#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
管理员配置页面
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

from src.data.config_manager import ConfigManager


class AdminConfigPage(QWidget):
    """管理员配置页面类"""
    
    def __init__(self):
        super().__init__()
        
        self.config_manager = ConfigManager()
        
        self.init_ui()
        self.load_config()
    
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("管理员配置")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # TODO: 添加配置表单字段
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_config)
        layout.addWidget(save_btn)
        
        # 锁定按钮
        lock_btn = QPushButton("保存并锁定")
        lock_btn.clicked.connect(self.lock_config)
        layout.addWidget(lock_btn)
        
        self.setLayout(layout)
    
    def load_config(self):
        """加载配置"""
        # TODO: 实现配置加载逻辑
        pass
    
    def save_config(self):
        """保存配置"""
        # TODO: 实现配置保存逻辑
        pass
    
    def lock_config(self):
        """锁定配置"""
        # TODO: 实现配置锁定逻辑
        pass

