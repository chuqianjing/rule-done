#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
入档·党员发展档案材料填写与生成工具
主程序入口
"""

from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
import qdarktheme
from src.ui.main_window import MainWindow

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 确保必要的目录存在
project_root.joinpath('data').mkdir(exist_ok=True)
project_root.joinpath('exports').mkdir(exist_ok=True)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("入档·党员发展档案材料填写与生成工具")
    app.setOrganizationName("Party Development System")
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("my_unique_app_id")

    # 应用现代主题（亮色模式）
    qdarktheme.setup_theme("light")

    # 创建主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()




