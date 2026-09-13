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
from src.ui.main_window import MainWindow
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

    # 应用现代主题（亮色模式）
    qdarktheme.setup_theme("light")

    # 创建主窗口
    window = MainWindow()
    guard.activation_requested.connect(window.bring_to_front)
    # 窗口构造期间（如启动密码框）到达的置前请求不能丢
    if guard.take_pending_activation():
        window.bring_to_front()
    window.show()

    exit_code = app.exec()
    guard.release()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()




