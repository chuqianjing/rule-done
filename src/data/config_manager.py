#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置数据管理
"""

from pathlib import Path
from datetime import datetime

from src.utils.json_storage import JSONStorage


class ConfigManager:
    """配置管理器类"""
    
    def __init__(self):
        self.config_path = Path("config/admin_config.json")
        self.json_storage = JSONStorage()
    
    def load_config(self, check_sync: bool = False, allow_sync_when_locked: bool = False):
        """
        加载配置
        
        Args:
            check_sync: 是否检查并同步远程配置
            allow_sync_when_locked: 配置已锁定时是否仍允许同步（学生端常用）
        """
        if not self.config_path.exists():
            return self._get_default_config()
        
        try:
            config = self.json_storage.read_json(str(self.config_path))
            return config
        except Exception:
            return self._get_default_config()
    
    def save_config(self, config):
        """保存配置"""
        '''
        if self.is_locked():
            raise PermissionError("配置已锁定，无法修改")
        '''
        # 更新配置时间戳
        config['last_modified'] = datetime.now().isoformat()
        
        self.json_storage.write_json(str(self.config_path), config)
        return True

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
    
    def unlock_config(self, password=None):
        """解锁配置（需要验证）"""
        # TODO: 实现密码验证逻辑
        config = self.load_config()
        config['locked'] = False
        config['unlocked_at'] = datetime.now().isoformat()
        self.json_storage.write_json(str(self.config_path), config)
        return True
    
    def get_readonly_config(self):
        """获取只读配置（学生端使用）"""
        return self.load_config()
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            "version": "1.0",
            "configured": False,
            #"locked": False,
            "date_format": {
                # 全局日期显示格式，字段可根据自身需要选择使用
                "format": "YYYY年MM月DD日"
            },
            "branch_info": {
                "branch_name": "",
                "branch_code": "",
                "secretary": {
                    "name": "",
                    "position": "党支部书记"
                }
            },
            "party_committee": {
                "name": "",
                "secretary": {
                    "name": ""
                }
            },
            "common_fields": {
                "school_name": "",
                "college_name": ""
            },
            "system_settings": {
                "export_path": "./exports",
                "auto_save": True
            }
        }

