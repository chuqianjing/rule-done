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
        self.config_path = Path("data/admin_config.json")
        self.json_storage = JSONStorage()
    
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
        return {
            "version": version,
            "configured": False,
            "支部信息": {
                "支部名称": "",
                "支部书记": ""
            },
            "上级党委信息": {
                "党委名称": "",
                "党委书记": ""
            },
            "公共字段": {
                "学校名称": "",
                "学院名称": ""
            },
            "系统设置": {
                "日期显示格式": "YYYY年MM月DD日",
                "配置同步地址": ""
            },
            "template_fields": {}  # 管理员配置的模板字段
        }
    
    def save_config(self, config):
        """保存配置"""
        # 更新配置时间戳
        config['last_modified'] = datetime.now().isoformat()
        self.json_storage.write_json(str(self.config_path), config)
        return True

    # ========================= 模板字段配置方法 =========================
    
    def get_template_fields(self, template_id: str = None) -> dict:
        """
        获取管理员配置的模板字段
        """
        config = self.load_config()
        template_fields = config.get("template_fields", {})
        
        if template_id is None:
            return template_fields
        return template_fields.get(template_id, {})
    
    def save_template_data(self, template_id: str, fields: dict):
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

