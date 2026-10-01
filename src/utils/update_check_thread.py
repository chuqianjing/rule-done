#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
应用更新检查线程

优先走 GitHub Releases API：除版本号外还能拿到 assets 清单（文件名、大小、
sha256 摘要），供下载与校验环节使用。

API 未认证限流为 60 次/小时/IP，同一出口 IP（如单位内网 NAT）可能撞上，
故失败时回退到 /releases/latest 重定向解析（只拿得到版本号，拿不到 assets）。
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from packaging import version
import requests

GITHUB_REPO = "chuqianjing/rule-done"
GITHUB_PROJECT_URL = f"https://github.com/{GITHUB_REPO}"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_PAGE_LATEST = f"{GITHUB_PROJECT_URL}/releases/latest"

# GitHub API 强制要求带 User-Agent，缺失会直接 403。
_USER_AGENT = "RuleDone-Updater"
_API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": _USER_AGENT,
}


def _parse_version(text: str) -> version.Version | None:
    """宽松解析版本号；不可解析时返回 None（调用方按「无更新」处理）。"""
    try:
        return version.Version(str(text).strip())
    except Exception:
        return None


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class UpdateCheckThread(QThread):
    """后台检查应用更新，并可选地获取远程公告。"""

    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        current_version: str,
        release_url: str = GITHUB_PAGE_LATEST,
        project_url: str = GITHUB_PROJECT_URL,
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
            release = self._fetch_release_info()
            if release is None:
                self.failed.emit("无法获取最新版本信息，请检查网络后重试。")
                return

            latest_version, html_url, assets, release_notes = release
            current = _parse_version(self.current_version)
            latest = _parse_version(latest_version)
            # 解析失败按「无更新」处理：宁可漏报，也不要给出错误的升级引导。
            has_update = bool(
                current is not None and latest is not None and latest > current
            )

            self.result_ready.emit(
                {
                    "current_version": self.current_version,
                    "latest_version": latest_version,
                    "download_url": html_url or self.release_url,
                    "html_url": html_url,
                    "project_url": self.project_url,
                    "assets": assets,
                    "release_notes": release_notes,
                    "has_update": has_update,
                    "announcement": self._fetch_announcement(),
                }
            )
        except Exception as e:
            self.failed.emit(str(e))

    # ====================== 远端信息获取 ======================

    def _fetch_release_info(self) -> tuple[str, str, list[dict], str] | None:
        """返回 (版本号, release 页面 URL, assets, 发布说明)；失败返回 None。"""
        info = self._fetch_release_info_from_api()
        if info is not None:
            return info
        return self._fetch_release_info_from_redirect()

    def _fetch_release_info_from_api(self) -> tuple[str, str, list[dict], str] | None:
        """走 GitHub API 获取结构化发布信息。"""
        try:
            response = requests.get(
                GITHUB_API_LATEST, headers=_API_HEADERS, timeout=self.timeout
            )
            if response.status_code != 200:
                return None
            data = response.json()
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

        tag = str(data.get("tag_name") or "").strip()
        if not tag:
            return None

        assets: list[dict] = []
        for item in data.get("assets") or []:
            if not isinstance(item, dict):
                continue
            digest = str(item.get("digest") or "").strip()
            assets.append(
                {
                    "name": str(item.get("name") or ""),
                    "url": str(item.get("browser_download_url") or ""),
                    "size": _safe_int(item.get("size")),
                    # GitHub 目前对部分旧资产不回填 digest，缺失时留空由下载后自算。
                    "sha256": digest.split(":", 1)[1].lower()
                    if digest.startswith("sha256:")
                    else "",
                }
            )

        return (
            tag,
            str(data.get("html_url") or "").strip(),
            assets,
            str(data.get("body") or ""),
        )

    def _fetch_release_info_from_redirect(self) -> tuple[str, str, list[dict], str] | None:
        """回退方案：跟随 /releases/latest 重定向，从最终 URL 解析 tag。"""
        try:
            response = requests.get(
                self.release_url,
                headers={"User-Agent": _USER_AGENT},
                timeout=self.timeout,
                allow_redirects=True,
            )
            if response.status_code != 200:
                return None
            final_url = response.url
            if "tag/" not in final_url:
                return None
            tag = final_url.split("tag/")[-1].strip()
            if not tag:
                return None
            return tag, final_url, [], ""
        except Exception:
            return None

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