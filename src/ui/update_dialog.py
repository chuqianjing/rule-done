#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
应用更新进度对话框（模态）

承载「下载 → 校验 → 应用」的完整流程。用户点击确认后才开始下载；下载中可取消
（已下部分保留，下次可断点续传）。

对话框不直接决定程序何时退出，而是通过 ``exit_required`` 告知调用方：
为 True 时调用方应立即关闭主窗口，把接力棒交给安装器或外部替换脚本。
"""

from __future__ import annotations

import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.ui.choice_dialog import ChoiceDialog
from src.utils.app_update import (
    UpdateAction,
    UpdatePlan,
    build_update_plan,
    detect_install_form,
    get_app_dir,
    get_staging_dir,
    launch_windows_installer,
    prepare_and_launch_portable_replace,
    reveal_after_download,
)
from src.utils.update_download_thread import UpdateDownloadThread

# 进度标签刷新节流，避免 64KB 一块的事件把 UI 刷爆。
_UI_REFRESH_INTERVAL_SECONDS = 0.2

# 停不下来的下载线程挂在这里等 finished 信号：运行中的 QThread 一旦被销毁会直接崩溃进程。
_PENDING_THREADS: list[UpdateDownloadThread] = []


def format_size(num_bytes: float) -> str:
    """把字节数格式化为易读文本。"""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def format_duration(seconds: float) -> str:
    """把剩余秒数格式化为易读文本。"""
    if seconds <= 0 or seconds > 24 * 3600:
        return "--"
    total = int(seconds)
    if total < 60:
        return f"{total} 秒"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} 分 {secs} 秒"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} 小时 {minutes} 分"


class UpdateProgressDialog(QDialog):
    """模态更新进度对话框。

    用法::

        dialog = UpdateProgressDialog(current_version, latest_version, plan, parent=self)
        dialog.exec()
        if dialog.exit_required:
            self.close()   # 让安装器/外部脚本接管
    """

    def __init__(
        self,
        current_version: str,
        latest_version: str,
        plan: UpdatePlan,
        parent=None,
    ):
        super().__init__(parent)
        self.current_version = current_version
        self.latest_version = latest_version
        self.plan = plan

        #: 为 True 表示调用方需要立即关闭程序
        self.exit_required = False

        self.download_thread: UpdateDownloadThread | None = None
        self.downloaded_path: Path | None = None
        self._started_at = 0.0
        self._downloaded = 0
        self._total = 0
        self._last_refresh = 0.0
        self._finished = False

        self.setWindowTitle("正在更新")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._build_ui()

    # ====================== 界面 ======================

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        version_label = QLabel(f"当前版本 {self.current_version}　→　最新版本 {self.latest_version}")
        layout.addWidget(version_label)

        if self.plan.degraded_reason:
            # 未能走自动路径时先把原因说清楚，避免用户以为程序卡住了
            note = QLabel(self.plan.degraded_reason)
            note.setWordWrap(True)
            note.setStyleSheet("color: #b26a00;")
            layout.addWidget(note)

        self.stage_label = QLabel(self._initial_stage_text())
        self.stage_label.setWordWrap(True)
        layout.addWidget(self.stage_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        self.retry_btn = QPushButton("重试")
        self.retry_btn.setMinimumWidth(96)
        self.retry_btn.setVisible(False)
        self.retry_btn.clicked.connect(self._start_download)
        button_layout.addWidget(self.retry_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setMinimumWidth(96)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _initial_stage_text(self) -> str:
        if self.plan.auto_apply:
            return "正在下载更新包，下载完成后将自动完成安装并重新启动。"
        return "正在下载更新包…"

    # ====================== 生命周期 ======================

    def exec(self) -> int:
        """显示对话框，并在显示后立即开始下载。"""
        self._start_download()
        return super().exec()

    def closeEvent(self, event):
        """关闭窗口等同于取消（下载中需要先安全停止线程）。"""
        if not self._finished and not self._stop_download():
            event.ignore()
            return
        super().closeEvent(event)

    def reject(self) -> None:
        if not self._finished and not self._stop_download():
            return
        super().reject()

    # ====================== 下载 ======================

    def _start_download(self) -> None:
        asset = self.plan.asset or {}
        url = str(asset.get("url") or "")
        if not url:
            self._show_failure("更新包地址无效，无法下载。")
            return

        staging_dir = get_staging_dir(self.latest_version)
        dest_path = staging_dir / str(asset.get("name") or "RuleDone-update")

        self._finished = False
        self._started_at = time.monotonic()
        self._last_refresh = 0.0
        self._downloaded = 0
        self._total = int(asset.get("size") or 0)

        self.retry_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setText("取消")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.stage_label.setText(self._initial_stage_text())
        self.detail_label.setText("正在连接服务器…")

        self.download_thread = UpdateDownloadThread(
            url=url,
            dest_path=dest_path,
            expected_sha256=str(asset.get("sha256") or ""),
            expected_size=self._total,
        )
        self.download_thread.progress.connect(self._on_progress)
        self.download_thread.finished_ok.connect(self._on_download_finished)
        self.download_thread.failed.connect(self._on_download_failed)
        self.download_thread.cancelled.connect(self._on_download_cancelled)
        self.download_thread.start()

    def _stop_download(self) -> bool:
        """请求停止下载线程；返回 False 表示未能及时停止（调用方应放弃关闭）。"""
        if self.download_thread is None or not self.download_thread.isRunning():
            return True
        self.download_thread.cancel()
        if not self.download_thread.wait(3000):
            return False
        return True

    def _on_cancel_clicked(self) -> None:
        if self._finished:
            self.reject()
            return
        if self._stop_download():
            self.reject()

    # ====================== 进度回调 ======================

    def _on_progress(self, downloaded: int, total: int) -> None:
        self._downloaded = downloaded
        if total > 0:
            self._total = total

        now = time.monotonic()
        is_last = self._total > 0 and downloaded >= self._total
        if not is_last and (now - self._last_refresh) < _UI_REFRESH_INTERVAL_SECONDS:
            return
        self._last_refresh = now

        if self._total > 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(min(100, int(downloaded * 100 / self._total)))
        else:
            # 总大小未知时退化为「忙碌」进度条
            self.progress_bar.setRange(0, 0)

        self.detail_label.setText(self._build_detail_text(now))

    def _build_detail_text(self, now: float) -> str:
        parts = []
        if self._total > 0:
            parts.append(f"{format_size(self._downloaded)} / {format_size(self._total)}")
        else:
            parts.append(f"已下载 {format_size(self._downloaded)}")

        elapsed = now - self._started_at
        if elapsed > 0.5:
            speed = self._downloaded / elapsed
            parts.append(f"{format_size(speed)}/秒")
            if self._total > self._downloaded and speed > 0:
                parts.append(f"剩余约 {format_duration((self._total - self._downloaded) / speed)}")
        return "　·　".join(parts)

    # ====================== 结果处理 ======================

    def _on_download_finished(self, path: str) -> None:
        self.downloaded_path = Path(path)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.detail_label.setText(format_size(self.downloaded_path.stat().st_size)
                                  if self.downloaded_path.exists() else "")
        self.stage_label.setText("下载完成，正在准备更新…")
        self.cancel_btn.setEnabled(False)
        # 让上面的文案先绘制出来，再执行可能耗时的解压/启动步骤
        QCoreApplication.processEvents()

        try:
            self._apply()
        except Exception as exc:
            self._show_failure(f"准备更新失败：{exc}")

    def _apply(self) -> None:
        """按计划执行升级动作。"""
        path = self.downloaded_path
        if path is None:
            self._show_failure("更新包不存在。")
            return

        action = self.plan.action

        if action is UpdateAction.WIN_SILENT_INSTALL:
            launch_windows_installer(path)
            self._finished = True
            self.exit_required = True
            self.accept()
            return

        if action is UpdateAction.WIN_INPLACE_REPLACE:
            app_dir = get_app_dir()
            if app_dir is None:
                raise ValueError("无法确定程序所在目录。")
            prepare_and_launch_portable_replace(
                zip_path=path,
                app_dir=app_dir,
                staging_dir=get_staging_dir(self.latest_version),
            )
            self._finished = True
            self.exit_required = True
            self.accept()
            return

        # REVEAL_FILE：下载交给用户完成，不做自动替换
        reveal_after_download(path)
        self._finished = True
        ChoiceDialog(
            "更新包已下载",
            self._manual_instruction(path),
            [("好的", "accept")],
            parent=self,
        ).exec()
        self.accept()

    def _manual_instruction(self, path: Path) -> str:
        if path.suffix.lower() == ".dmg":
            return (
                "安装包已打开，请把「入档」拖入「应用程序」文件夹完成替换。\n\n"
                f"安装包位置：{path}"
            )
        if self.plan.degraded_reason:
            return (
                f"{self.plan.degraded_reason}\n\n"
                "新版已下载并定位到文件管理器，请手动解压替换原程序目录（用户数据不受影响）。\n\n"
                f"更新包位置：{path}"
            )
        return (
            "新版已下载并在文件管理器中定位。\n\n"
            "请解压后将「入档」替换到原位置。用户数据存放在独立目录，替换程序不会影响已有档案。\n\n"
            f"更新包位置：{path}"
        )

    def _on_download_failed(self, message: str) -> None:
        self._show_failure(message)

    def _on_download_cancelled(self) -> None:
        self._finished = True
        self.reject()

    def _show_failure(self, message: str) -> None:
        self._finished = True
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.stage_label.setText("更新失败")
        self.detail_label.setText(message)
        # 已下载部分会被保留（.partial），重试时可断点续传
        self.retry_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setText("关闭")

    # ====================== 收尾 ======================

    def cleanup(self) -> None:
        """释放下载线程。

        运行中的 QThread 被销毁会直接崩溃进程，所以分两种处理：
        能及时停下就直接回收；停不下来（socket 卡住）则挂到模块级列表，
        等 finished 信号到达后交给 Qt 回收。
        """
        thread = self.download_thread
        if thread is None:
            return
        self.download_thread = None

        if thread.isRunning():
            thread.cancel()
            thread.wait(3000)

        if thread.isRunning():
            _PENDING_THREADS.append(thread)
            thread.finished.connect(
                lambda: _PENDING_THREADS.remove(thread)
                if thread in _PENDING_THREADS
                else None
            )
            thread.finished.connect(thread.deleteLater)
        else:
            thread.deleteLater()


# ============================ 统一入口 ============================


@dataclass
class UpdateFlowResult:
    """一次更新交互的结果。"""

    exit_required: bool = False   # True 表示调用方应立即关闭程序
    dont_remind: bool = False     # 用户勾选了「不再提醒此版本」
    started: bool = False         # 用户确认并进入了下载流程


def describe_plan(plan: UpdatePlan) -> str:
    """把执行计划翻译成用户能看懂的一句话。"""
    if plan.auto_apply:
        return "更新包下载完成后会自动完成安装并重新启动程序。"
    name = str((plan.asset or {}).get("name") or "")
    if name.endswith(".dmg"):
        return "将下载安装包并自动打开，拖入「应用程序」文件夹即可完成替换。"
    return "将下载更新包，需手动替换程序文件（用户数据不受影响）。"


def run_update_flow(
    result: dict,
    parent=None,
    *,
    allow_dont_remind: bool = False,
) -> UpdateFlowResult:
    """统一的更新交互入口：确认 → 下载 → 应用。

    三处入口（启动弹窗、管理员设置页、成员设置页）共用本函数，避免升级逻辑
    被复制成三份。

    Args:
        result: ``UpdateCheckThread`` 的结果字典
        parent: 父窗口
        allow_dont_remind: 是否提供「不再提醒此版本」选项（启动弹窗才需要）
    """
    current = str(result.get("current_version") or "")
    latest = str(result.get("latest_version") or "")
    html_url = str(result.get("html_url") or result.get("download_url") or "")

    plan = build_update_plan(detect_install_form(), list(result.get("assets") or []))

    if plan.action is UpdateAction.NONE or plan.asset is None:
        # 拿不到可下载的资产：限流回退、资产未上传完，或开发运行。
        # 这类情况下旧行为（打开 release 页）反而是最可靠的。
        choice = ChoiceDialog(
            "发现新版本",
            f"当前版本：{current}\n最新版本：{latest}\n\n"
            "请前往项目主页下载最新版本。",
            [("前往下载", "accept"), ("稍后", "reject")],
            parent=parent,
        ).exec()
        if choice == "前往下载" and html_url:
            webbrowser.open(html_url)
        return UpdateFlowResult()

    confirm = ChoiceDialog(
        "发现新版本",
        f"当前版本：{current}\n最新版本：{latest}\n\n"
        f"{describe_plan(plan)}\n\n"
        "是否立即更新？",
        [("立即更新", "accept"), ("稍后", "reject")],
        parent=parent,
        checkbox_text="不再提醒此版本" if allow_dont_remind else "",
    )
    choice = confirm.exec()
    dont_remind = confirm.checkbox_checked

    if choice != "立即更新":
        return UpdateFlowResult(dont_remind=dont_remind)

    dialog = UpdateProgressDialog(current, latest, plan, parent=parent)
    try:
        dialog.exec()
        exit_required = dialog.exit_required
    finally:
        dialog.cleanup()

    return UpdateFlowResult(
        exit_required=exit_required, dont_remind=dont_remind, started=True
    )


__all__ = [
    "UpdateProgressDialog",
    "UpdateFlowResult",
    "run_update_flow",
    "describe_plan",
    "format_size",
    "format_duration",
]
