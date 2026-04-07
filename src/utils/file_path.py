import os
import sys

def get_abs_path(relative_path):
    """ 获取资源文件的绝对路径 """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录路径 (单文件模式)
        # 或者在单文件夹模式下，这也是程序运行的基础路径
        base_path = sys._MEIPASS
    else:
        # 普通 Python 环境下的绝对路径
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)