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
    """后台检查应用更新，并可选地获取远程公告。"""

    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        current_version: str,
        release_url: str,
        project_url: str,
        announcement_url: str | None = None,
        timeout: int = 10,
    ):
        super().__init__()
        self.current_version = current_version
        self.release_url = release_url
        self.project_url = project_url
        self.announcement_url = announcement_url
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
                    "announcement": self._fetch_announcement(),
                }
            )
        except Exception as e:
            self.failed.emit(str(e))

    def _fetch_announcement(self) -> dict | None:
        """获取远程公告（失败时静默返回 None，不影响更新检查主流程）。"""
        if not self.announcement_url:
            return None
        try:
            response = requests.get(self.announcement_url, timeout=self.timeout)
            if response.status_code != 200:
                return None
            data = response.json()
            if isinstance(data, dict) and data.get("enabled", True):
                return data
        except Exception:
            pass
        return None