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
    
    def __init__(self):
        self.current_mode = self.detect_mode()
        self.json_storage = JSONStorage()
    
    def detect_mode(self):
        """检测当前运行模式"""
        config_path = Path("config/admin_config.json")
        
        if not config_path.exists():
            return "developer"  # 开发者态
        
        try:
            config = self.json_storage.read_json(str(config_path))
            if config.get('locked', False):
                return "student"  # 学生态（文件存在且locked字段显示已锁定）
            else:
                return "admin"  # 管理员态（文件存在且locked字段显示未锁定）
        except Exception:
            return "developer"  # 出错时返回开发者态
    
    def is_field_editable(self, field_key, field_source):
        """判断字段是否可编辑"""
        if self.current_mode == "developer":
            return True  # 开发者态全部可编辑
        
        if self.current_mode == "admin":
            return True  # 管理员态全部可编辑
        
        # 学生态
        if field_source == "admin_config":
            return False  # 管理员配置不可编辑
        else:
            return True  # 学生数据可编辑
    
    def can_edit_admin_config(self):
        """判断是否可以编辑管理员配置"""
        return self.current_mode in ["developer", "admin"]
    
    def switch_to_admin_mode(self, password=None):
        """切换到管理员模式（需要验证）"""
        # TODO: 实现密码验证逻辑
        if self.can_edit_admin_config():
            self.current_mode = "admin"
            return True
        return False
    
    def switch_to_student_mode(self):
        """切换到学生模式"""
        self.current_mode = "student"

