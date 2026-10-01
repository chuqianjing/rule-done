#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
入档·党员发展档案管理工具
主程序入口
"""

from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
import qdarktheme
from src.ui.choice_dialog import ChoiceDialog
from src.ui.main_window import MainWindow
from src.utils.app_update import (
    PendingUpdateIssue,
    cleanup_previous_update_artifacts,
    retry_pending_portable_replace,
    safe_rmtree,
)
from src.utils.file_path import ensure_runtime_directories, get_abs_path, get_user_data_root
from src.utils.single_instance import SingleInstanceGuard

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 确保运行时目录存在（默认在用户可写目录）
ensure_runtime_directories()


def main():
    """主函数"""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.chuqianjing.ruledone")
    
    app = QApplication(sys.argv)
    app.setApplicationName("入档 • 党员发展档案管理工具")
    app.setOrganizationName("Party Development System")
    app.setWindowIcon(QIcon(get_abs_path("resources/icons/logo.ico")))

    # 单实例约束：同一用户数据目录只允许一个实例。
    # 多实例会并发读写 system_settings.json 等配置（读-改-写 + 覆盖写，无锁），
    # 造成配置互相覆盖、甚至读到半截内容而解析失败。
    guard = SingleInstanceGuard(get_user_data_root() / "app.lock")
    if not guard.try_acquire():
        # 已有实例在运行：正常情况下已请求其窗口置前，静默退出即可；
        # 若未能通知到（对方未响应），则给出提示，避免用户双击后「毫无反应」
        if not guard.existing_instance_notified:
            QMessageBox.information(
                None,
                "程序已在运行",
                "入档已在运行中，请使用已打开的窗口。\n"
                "若未看到窗口，请在任务管理器中结束残留的「入档」进程后重试。",
            )
        sys.exit(0)

    # 清理上一次自动更新留下的备份目录与暂存文件（只由首实例做）
    pending_update = cleanup_previous_update_artifacts()

    # 应用现代主题（亮色模式）
    qdarktheme.setup_theme("light")

    # 创建主窗口
    window = MainWindow()
    guard.activation_requested.connect(window.bring_to_front)
    # 窗口构造期间（如启动密码框）到达的置前请求不能丢
    if guard.take_pending_activation():
        window.bring_to_front()
    window.show()

    # 上次自动更新没完成：如实告知并提供继续完成的选项
    if pending_update is not None and _resolve_pending_update(window, pending_update):
        guard.release()
        sys.exit(0)

    exit_code = app.exec()
    guard.release()
    sys.exit(exit_code)


def _resolve_pending_update(window: MainWindow, issue: PendingUpdateIssue) -> bool:
    """处理上一次未完成的绿色版原地替换。

    返回 True 表示调用方应立即退出（替换脚本已启动，等本进程退出后接管目录）。
    """
    reason = issue.reason or "上次的替换脚本没能完成目录切换（可能被系统短暂占用）。"
    choice = ChoiceDialog(
        "上次更新未完成",
        "上次自动更新没有完成，程序仍是更新前的版本。\n\n"
        f"原因：{reason}\n\n"
        f"新版已解压到：\n{issue.new_dir}\n\n"
        "是否现在继续完成更新？选择「立即完成更新」后程序会关闭，"
        "并在几秒后以新版本重新打开。",
        [("立即完成更新", "accept"), ("放弃本次更新", "reject")],
        parent=window,
    ).exec()

    if choice != "立即完成更新":
        # 放弃就清掉暂存的新版本，避免每次启动都来问一遍
        safe_rmtree(issue.new_dir)
        return False

    if retry_pending_portable_replace(issue):
        return True

    QMessageBox.warning(
        window,
        "无法继续更新",
        "暂存的新版本已不可用，请在「设置」页重新检查更新。\n\n"
        f"更新日志：{issue.log_path}",
    )
    return False


if __name__ == '__main__':
    main()




