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
                "config_sync_url": "",
                "auto_save": True
            },
            "template_fields": {}  # 管理员配置的模板字段
        }

    # ========================= 模板字段配置方法 =========================
    
    def get_template_fields(self, template_id: str = None) -> dict:
        """
        获取管理员配置的模板字段
        
        Args:
            template_id: 模板 ID，若为 None 则返回所有模板的配置
        
        Returns:
            模板字段配置字典
        """
        config = self.load_config()
        template_fields = config.get("template_fields", {})
        
        if template_id is None:
            return template_fields
        return template_fields.get(template_id, {})
    
    def save_template_fields(self, template_id: str, fields: dict):
        """
        保存管理员配置的模板字段
        
        Args:
            template_id: 模板 ID
            fields: 字段配置字典，格式为 {"字段名": {"value": "值", "locked": True/False}}
        """
        config = self.load_config()
        if "template_fields" not in config:
            config["template_fields"] = {}
        
        config["template_fields"][template_id] = fields
        self.save_config(config)
    
    def get_field_config(self, template_id: str, field_name: str) -> dict:
        """
        获取单个字段的配置
        
        Args:
            template_id: 模板 ID
            field_name: 字段名
        
        Returns:
            字段配置，包含 value 和 locked，若不存在返回 {"value": "", "locked": False}
        """
        template_fields = self.get_template_fields(template_id)
        field_config = template_fields.get(field_name, {})
        
        # 兼容旧数据格式（直接存储值而非对象）
        if isinstance(field_config, str):
            return {"value": field_config, "locked": False}
        
        return {
            "value": field_config.get("value", ""),
            "locked": field_config.get("locked", False)
        }
    
    def is_field_locked(self, template_id: str, field_name: str) -> bool:
        """检查字段是否被管理员锁定"""
        field_config = self.get_field_config(template_id, field_name)
        return field_config.get("locked", False)

