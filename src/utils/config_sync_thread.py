#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
管理员配置同步线程
"""

from PyQt6.QtCore import QThread, pyqtSignal


class ConfigSyncThread(QThread):
    """配置同步后台线程"""
    sync_completed = pyqtSignal(bool, str)
    
    def __init__(self, data_manager, sync_url):
        super().__init__()
        self.data_manager = data_manager
        self.sync_url = sync_url
    
    def run(self):
        """执行同步检查"""
        try:
            success, message = self.data_manager.sync_admin_config(self.sync_url)
            self.sync_completed.emit(success, message)
        except Exception as e:
            self.sync_completed.emit(False, f"同步过程出错：{e}")

            