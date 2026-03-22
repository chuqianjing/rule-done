#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JSON 存储工具
"""

import json
from pathlib import Path
from datetime import datetime


class JSONStorage:
    """JSON 存储类"""
    
    @staticmethod
    def read_json(file_path):
        """读取 JSON 文件"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {e}")
    
    @staticmethod
    def write_json(file_path, data):
        """写入 JSON 文件"""
        path = Path(file_path)
        
        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            raise IOError(f"写入文件失败: {e}")
    
    @staticmethod
    def backup_file(file_path):
        """备份文件"""
        path = Path(file_path)
        
        if not path.exists():
            return None
        
        # 得在文件名中加上备份的时间
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_name(f'{path.stem}_backup_{timestamp}{path.suffix}')
        
        try:
            import shutil
            shutil.copy2(path, backup_path)
            return str(backup_path)
        except Exception as e:
            raise IOError(f"备份文件失败: {e}")

