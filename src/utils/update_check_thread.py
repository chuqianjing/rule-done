#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
应用更新检查线程
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from packaging import version
import requests


class UpdateCheckThread(QThread):
    """后台检查应用更新。"""

    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, current_version: str, release_url: str, project_url: str, timeout: int = 10):
        super().__init__()
        self.current_version = current_version
        self.release_url = release_url
        self.project_url = project_url
        self.timeout = timeout

    def run(self):
        """执行更新检查。"""
        try:
            response = requests.get(self.release_url, timeout=self.timeout, allow_redirects=True)
            if response.status_code != 200:
                self.failed.emit("无法获取最新版本信息。")
                return

            final_url = response.url
            if "tag/" not in final_url:
                self.failed.emit("无法解析最新版本信息。")
                return

            latest_version = final_url.split("tag/")[-1]
            self.result_ready.emit(
                {
                    "current_version": self.current_version,
                    "latest_version": latest_version,
                    "download_url": final_url,
                    "project_url": self.project_url,
                    "has_update": version.parse(latest_version) > version.parse(self.current_version),
                }
            )
        except Exception as e:
            self.failed.emit(str(e))