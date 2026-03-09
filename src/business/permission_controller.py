#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
权限控制模块
"""

import os
from pathlib import Path

from src.utils.json_storage import JSONStorage


class PermissionController:
    """权限控制类"""
    
    SETTINGS_PATH = Path("data/system_settings.json")
    
    def __init__(self):
        self.json_storage = JSONStorage()
        self.current_mode = self.detect_mode()
    
    def detect_mode(self):
        """检测当前运行模式
        
        根据 data/system_settings.json 文件判断：
        - 文件不存在：开发态 (developer)
        - 文件存在：根据 mode 字段判断 admin 或 student
        """
        if not self.SETTINGS_PATH.exists():
            return "developer"
        
        try:
            settings = self.json_storage.read_json(str(self.SETTINGS_PATH))
            mode = settings.get('mode', 'developer')
            if mode in ['admin', 'student']:
                return mode
            else:
                return "developer"
        except Exception:
            return "developer"
    
    def save_mode(self, mode):
        """保存模式到 system_settings.json 文件"""
        try:
            # 读取现有设置或创建新设置
            if self.SETTINGS_PATH.exists():
                settings = self.json_storage.read_json(str(self.SETTINGS_PATH))
            else:
                settings = {}
            
            settings['mode'] = mode
            self.json_storage.write_json(str(self.SETTINGS_PATH), settings)
            return True
        except Exception:
            return False
    
    def initialize_settings(self, mode='admin'):
        """初始化 system_settings.json 文件
        
        Args:
            mode: 初始模式，默认为 'admin'
        """
        if self.save_mode(mode):
            self.current_mode = mode
            return True
        return False
    
    def is_field_editable(self, field_key, field_source):
        """判断字段是否可编辑"""
        if self.current_mode == "developer":
            return True
        
        if self.current_mode == "admin":
            return True
        
        # 学生态
        if field_source == "admin_config":
            return False
        else:
            return True
    
    def can_edit_admin_config(self):
        """判断是否可以编辑管理员配置"""
        return self.current_mode in ["developer", "admin", "student"]
    
    def switch_to_admin_mode(self, password=None):
        """切换到管理员模式（需要验证）"""
        # TODO: 实现密码验证逻辑
        if self.can_edit_admin_config():
            if self.save_mode('admin'):
                self.current_mode = "admin"
                return True
        return False
    
    def switch_to_student_mode(self):
        """切换到学生模式"""
        if self.save_mode('student'):
            self.current_mode = "student"
            return True
        return False

