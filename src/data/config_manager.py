#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置数据管理
"""

from pathlib import Path
from datetime import datetime
from src.utils.json_storage import JSONStorage
from src.data.field_manager import FieldManager


class ConfigManager:
    """配置管理器类"""
    
    def __init__(self):
        self.config_path = Path("data/admin_config.json")
        self.json_storage = JSONStorage()
        self.field_manager = FieldManager()
    
    # ========================= 加载&保存 =========================
    
    def load_config(self):
        """
        加载配置
        """
        if not self.config_path.exists():
            return self._get_default_config()
        try:
            config = self.json_storage.read_json(str(self.config_path))
            return config
        except Exception:
            return self._get_default_config()
    
    def _get_default_config(self):
        """获取默认配置"""
        # version用来标记管理员配置的版本，按照年月格式
        version = datetime.now().strftime("%Y.%m")
        config = {
            "version": version,
            "configured": False,
            "basic_data": {},
            "template_data": {}
        }
        return config
    
    def save_config(self, config):
        """保存配置"""
        # 更新配置时间戳
        config['last_modified'] = datetime.now().isoformat()
        self.json_storage.write_json(str(self.config_path), config)
        return True
    
    # ========================= lock相关操作 =========================

    def is_locked(self):
        """检查配置是否已锁定"""
        if not self.config_path.exists():
            return False
        try:
            config = self.json_storage.read_json(str(self.config_path))
            return config.get('locked', False)
        except Exception:
            return False
    
    def lock_config(self):
        """锁定配置"""
        config = self.load_config()
        config['locked'] = True
        config['locked_at'] = datetime.now().isoformat()
        self.json_storage.write_json(str(self.config_path), config)
        return True
    
    def unlock_config(self):
        """解锁配置"""
        config = self.load_config()
        config['locked'] = False
        config['unlocked_at'] = datetime.now().isoformat()
        self.json_storage.write_json(str(self.config_path), config)
        return True



