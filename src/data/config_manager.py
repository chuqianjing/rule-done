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
            "template_data": {}  # 管理员配置的模板字段
        }

        try:
            fields_definition = self.field_manager.load_fields_definition()
            admin_fields = fields_definition.get("admin_fields", [])

            # 按组和字段顺序构建默认配置，字段优先使用定义中的 default
            for group_def in sorted(admin_fields, key=lambda x: x.get("group_order", 9999)):
                group_name = group_def.get("group")
                if not group_name:
                    continue

                group_values = {}
                for field_def in sorted(group_def.get("fields", []), key=lambda x: x.get("display", {}).get("order", 9999)):
                    field_key = field_def.get("key")
                    if not field_key:
                        continue
                    group_values[field_key] = field_def.get("default", "")

                config["basic_data"][group_name] = group_values

        except Exception:
            pass

        # 兜底：字段定义读取失败时回退到内置默认结构
        return {
            "version": version,
            "configured": False,
            "basic_data": {
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
                "配置同步URL": "",
                "允许成员切换模式": ""
            },
            },
            "template_data": {}  # 管理员配置的模板字段
        }
    
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



