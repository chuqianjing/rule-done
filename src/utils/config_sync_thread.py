#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
管理员配置同步线程
"""

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QThread, Signal
from src.application.data_manager import DataManager

class ConfigSyncThread(QThread):
    """配置同步后台线程"""
    sync_completed = Signal(str)
    sync_failed = Signal(str)
    
    def __init__(self, data_manager: DataManager, sync_url: str):
        super().__init__()
        self.data_manager = data_manager
        self.sync_url = sync_url
    
    def run(self):
        """执行同步检查"""
        try:
            message = self.data_manager.sync_admin_config(self.sync_url)
            self.sync_completed.emit(message)
        except Exception as e:
            self.sync_failed.emit(f"{str(e)}")
            