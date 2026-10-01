#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
应用更新包下载线程

要点：
- 流式写入 ``<目标>.partial``，全部完成后才改名为正式文件，避免半截文件被误用；
- 已存在 ``.partial`` 时用 HTTP Range 断点续传（GitHub 资产支持），失败则重新下；
- 下载后校验 sha256 与文件头魔数，防止把错误页面当安装包执行。
"""

from __future__ import annotations

import os
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from src.utils.app_update import sha256_file

_USER_AGENT = "RuleDone-Updater"
_CHUNK_SIZE = 64 * 1024

# 文件头魔数，用于挡住「下到 HTML 错误页」这类低级问题。
_MAGIC_BY_SUFFIX = {
    ".zip": b"PK",
    ".exe": b"MZ",
    ".dmg": b"\x78\x01",  # UDZO(zlib) 压缩的 dmg；仅作弱校验，失败不阻断
}


class UpdateDownloadThread(QThread):
    """后台下载更新包，带进度、续传、取消与校验。"""

    progress = Signal(int, int)   # (已下载字节, 总字节；总字节未知时为 0)
    finished_ok = Signal(str)     # 本地文件绝对路径
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        url: str,
        dest_path: Path,
        expected_sha256: str = "",
        expected_size: int = 0,
        timeout: int = 30,
    ):
        super().__init__()
        self.url = url
        self.dest_path = Path(dest_path)
        self.expected_sha256 = str(expected_sha256 or "").strip().lower()
        self.expected_size = int(expected_size or 0)
        self.timeout = timeout
        self._cancel_requested = False

    # ====================== 外部控制 ======================

    def cancel(self) -> None:
        """请求取消；实际中断发生在下一个数据块边界。"""
        self._cancel_requested = True

    # ====================== 主流程 ======================

    def run(self):
        partial = self.dest_path.with_name(self.dest_path.name + ".partial")
        try:
            self.dest_path.parent.mkdir(parents=True, exist_ok=True)

            if not self._download_to(partial):
                return

            if not self._verify(partial):
                self._discard(partial)
                self.failed.emit("下载的文件校验未通过，已删除。请重试。")
                return

            # 校验通过才落到正式文件名，避免半截文件被后续流程使用。
            try:
                if self.dest_path.exists():
                    self.dest_path.unlink()
                os.replace(partial, self.dest_path)
            except OSError as exc:
                self._discard(partial)
                self.failed.emit(f"保存更新包失败：{exc}")
                return

            self.finished_ok.emit(str(self.dest_path))
        except Exception as exc:
            self._discard(partial)
            self.failed.emit(str(exc))

    # ====================== 内部实现 ======================

    def _download_to(self, partial: Path) -> bool:
        """下载到 .partial；返回 False 表示流程已结束（取消或失败）。"""
        resume_from = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": _USER_AGENT}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"

        try:
            response = requests.get(
                self.url, headers=headers, stream=True, timeout=self.timeout,
                allow_redirects=True,
            )
        except Exception as exc:
            self.failed.emit(f"下载失败：{exc}")
            return False

        if response.status_code not in (200, 206):
            self.failed.emit(f"下载失败：服务器返回 {response.status_code}。")
            return False

        # 服务器忽略 Range 而返回 200 时，必须从零重下（否则文件会拼接错乱）。
        if response.status_code == 200:
            resume_from = 0

        total = self._resolve_total(response, resume_from)

        mode = "ab" if resume_from > 0 else "wb"
        written = resume_from
        try:
            with open(partial, mode) as handle:
                for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                    if self._cancel_requested:
                        self.cancelled.emit()
                        return False
                    if not chunk:
                        continue
                    handle.write(chunk)
                    written += len(chunk)
                    self.progress.emit(written, total)
        except Exception as exc:
            self.failed.emit(f"下载中断：{exc}")
            return False

        self.progress.emit(written, total or written)
        return True

    @staticmethod
    def _resolve_total(response, resume_from: int) -> int:
        """推算完整文件总大小（续传时 Content-Length 只是剩余部分）。"""
        length = response.headers.get("Content-Length")
        try:
            remaining = int(length) if length else 0
        except (TypeError, ValueError):
            remaining = 0
        if remaining <= 0:
            return 0
        return remaining + resume_from

    def _verify(self, path: Path) -> bool:
        """sha256 + 大小 + 文件头魔数校验。"""
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size <= 0:
            return False

        if self.expected_size > 0 and size != self.expected_size:
            return False

        if self.expected_sha256:
            if sha256_file(path) != self.expected_sha256:
                return False

        # 用最终文件名取后缀（此时文件仍叫 xxx.partial）。
        magic = _MAGIC_BY_SUFFIX.get(self.dest_path.suffix.lower())
        if magic:
            try:
                with open(path, "rb") as handle:
                    head = handle.read(len(magic))
            except OSError:
                return False
            if head != magic:
                return False

        return True

    @staticmethod
    def _discard(path: Path) -> None:
        try:
            path.unlink()
        except OSError:
            pass
