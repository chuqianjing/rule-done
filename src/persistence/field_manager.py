#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
字段定义管理模块

本模块负责加载和管理系统的字段定义（fields_definition.json），
包括管理员字段、成员字段和模板字段的定义。

核心职责：
- 从 JSON 文件加载字段定义
- 提供字段定义的访问接口
- 支持字段定义的缓存与更新

字段定义结构：
- version：字段定义版本
- last_updated：字段定义的最后更新时间
- admin_fields：管理员端字段定义
- member_fields：成员端字段定义
- template_fields：模板通用字段定义

Author: 楚乾靖
Date: 2026-03
"""

from pathlib import Path
from typing import Any, Dict
from src.utils.json_storage import JSONStorage
from src.utils.file_path import get_abs_path


class FieldManager:
    """字段管理器类

    负责读取和提供系统字段定义，字段定义决定了应用支持的数据字段及其属性。
    """
    
    def __init__(self):
        """初始化字段管理器。

        设置字段定义文件路径并创建 JSON 存储工具实例。
        """
        # self.config_path = Path("resources/schema/fields_definition.json")
        self.config_path = Path(get_abs_path("resources/schema/fields_definition.json"))
        self.json_storage = JSONStorage()

    def load_fields_definition(self) -> Dict[str, Any]:
        """加载字段定义"""
        return self.json_storage.read_json(str(self.config_path))
        
    