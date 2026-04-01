#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
权限控制模块

本模块用于管理应用的运行模式与权限状态，提供模式检测、初始化、
模式持久化以及模式切换能力。

核心职责：
- 读取并维护当前运行模式（user/admin/member）
- 将模式写入 system_settings.json
- 提供管理员模式与成员模式的切换入口

Author: 楚乾靖 (Chu Qianjing)
Date: 2026-03
"""

from src.application.data_manager import DataManager


class PermissionController:
    """权限控制类。

    负责运行模式的读取、保存与切换，作为 UI 层与数据持久化层之间的
    权限控制协调器。

    Attributes:
        data_manager (DataManager): 数据管理器，用于读写系统设置。
        current_mode (str): 当前运行模式。
    """

    def __init__(self):
        """初始化权限控制器。

        创建数据管理器实例，并在启动时读取当前模式。
        """
        self.data_manager = DataManager()
        self.current_mode = self.detect_mode()
    
    def detect_mode(self):
        """检测当前运行模式。

        从系统设置中读取 `mode`，若不存在则回退到 `user`。

        Returns:
            str: 当前模式，可能值为 `user`、`admin`、`member`。
        """
        return self.data_manager.get_system_settings("mode") or "user"
    
    def save_mode(self, mode):
        """保存模式到 system_settings.json 文件。

        Args:
            mode (str): 目标模式。

        Returns:
            bool: 保存是否成功。当前实现固定返回 True。
        """
        self.data_manager.save_system_settings("mode", mode)
        return True
    
    def initialize_settings(self, mode='admin'):
        """初始化系统模式设置。
        
        Args:
            mode (str): 初始模式，默认为 `admin`。

        Returns:
            bool: 初始化是否成功。
        """
        if self.save_mode(mode):
            self.current_mode = mode
    
    def switch_to_admin_mode(self):
        """切换到管理员模式"""
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

