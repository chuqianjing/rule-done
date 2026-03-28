#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统设置数据管理
"""

from pathlib import Path
from typing import Any, Dict
from src.utils.json_storage import JSONStorage


class SettingsManager:
    """系统设置管理器类"""
    
    def __init__(self):
        self.config_path = Path("data/system_settings.json")
        self.json_storage = JSONStorage()

    def load_settings(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        return self.json_storage.read_json(str(self.config_path))
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """保存系统设置，失败时抛出异常"""
        self.json_storage.write_json(str(self.config_path), settings)
        return True
        
    