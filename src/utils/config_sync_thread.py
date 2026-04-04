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
    
    def __init__(self, data_manager: DataManager, mode :str = "pull",   # pull：成员端从远程拉取，push：管理员端推送到远程 
                 sync_url: str = "", force: bool = False,               # 成员端：应用启动时自动同步，设置页手动同步
                 provider: str = ""                                     # 管理员端：手动同步到远程
                 ):
        super().__init__()
        self.data_manager = data_manager
        self.mode = mode
        self.sync_url = sync_url
        self.force = force
        self.provider = provider

    def run(self):
        """执行同步检查"""
        try:
            if self.mode == "pull":
                message = self.data_manager.pull_admin_config_from_remote(self.sync_url, self.force)
            else:
                message = self.data_manager.push_admin_config_to_remote(self.provider)
            self.sync_completed.emit(message)
        except Exception as e:
            self.sync_failed.emit(f"{str(e)}")
            