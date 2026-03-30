#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置数据管理
"""

from pathlib import Path
from typing import Any, Dict
from src.utils.json_storage import JSONStorage


class FieldManager:
    """字段管理器类"""
    
    def __init__(self):
        self.config_path = Path("resources/schema/fields_definition.json")
        self.json_storage = JSONStorage()

    def load_fields_definition(self) -> Dict[str, Any]:
        return self.json_storage.read_json(str(self.config_path))
        
    