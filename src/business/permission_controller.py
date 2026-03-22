#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
权限控制模块
"""

from src.business.data_manager import DataManager


class PermissionController:
    """权限控制类"""
    def __init__(self):
        self.data_manager = DataManager()
        self.current_mode = self.detect_mode()
    
    def detect_mode(self):
        """检测当前运行模式"""
        return self.data_manager.get_system_settings("mode") or "developer"
    
    def save_mode(self, mode):
        """保存模式到 system_settings.json 文件"""
        try:
            self.data_manager.save_system_settings("mode", mode)
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
    
    def can_edit_admin_config(self):
        """判断是否可以编辑管理员配置"""
        return self.current_mode in ["developer", "admin", "member"]
    
    def switch_to_admin_mode(self, password=None):
        """切换到管理员模式（需要验证）"""
        # TODO: 实现密码验证逻辑
        if self.can_edit_admin_config():
            if self.save_mode('admin'):
                self.current_mode = "admin"
                return True
        return False
    
    def switch_to_member_mode(self):
        """切换到成员模式"""
        if self.save_mode('member'):
            self.current_mode = "member"
            return True
        return False

