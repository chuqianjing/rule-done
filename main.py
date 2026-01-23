#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
党员发展材料生成系统
主程序入口
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 确保必要的目录存在
project_root.joinpath('config').mkdir(exist_ok=True)
project_root.joinpath('data').mkdir(exist_ok=True)
project_root.joinpath('exports').mkdir(exist_ok=True)
project_root.joinpath('backups').mkdir(exist_ok=True)

from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("党员发展材料生成系统")
    app.setOrganizationName("Party Development System")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

