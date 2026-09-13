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
from typing import Any, Dict, List
from src.utils.json_storage import JSONStorage
from src.utils.file_path import get_builtin_resources_dir, get_runtime_resources_dir
from src.persistence.admin_config_builtin_fields import (
    GROUP_NAME as BUILTIN_ADMIN_GROUP_NAME,
    build_group_definition,
)


class FieldManager:
    """字段管理器类

    负责读取和提供系统字段定义，字段定义决定了应用支持的数据字段及其属性。
    """
    
    def __init__(self):
        """初始化字段管理器。

        设置字段定义文件路径并创建 JSON 存储工具实例。
        优先使用运行时可写的生效目录（打包模式下首次启动自动从内置目录拷贝），
        缺失时回退到程序内置目录，保证程序可用。
        """
        runtime_path = get_runtime_resources_dir() / "schema" / "fields_definition.json"
        self.config_path = (
            runtime_path if runtime_path.exists()
            else get_builtin_resources_dir() / "schema" / "fields_definition.json"
        )
        self.json_storage = JSONStorage()

    def load_fields_definition(self) -> Dict[str, Any]:
        """加载字段定义（用户 schema 内容层）

        会剔除与内置「双端交互」分组同名的分组：该分组是代码契约，
        不允许通过 fields_definition.json 覆盖、改名或删除
        （契约定义见 src/persistence/admin_config_builtin_fields.py）。
        """
        definition = self.json_storage.read_json(str(self.config_path))
        if not isinstance(definition, dict):
            return {}
        admin_groups = definition.get("admin_fields")
        if isinstance(admin_groups, list):
            definition["admin_fields"] = [
                group_def for group_def in admin_groups
                if not (
                    isinstance(group_def, dict)
                    and str(group_def.get("group", "")).strip() == BUILTIN_ADMIN_GROUP_NAME
                )
            ]
        return definition

    def get_admin_field_groups(self) -> List[Dict[str, Any]]:
        """管理员字段组 = 用户 schema 内容分组 + 代码内置的「双端交互」分组。

        仅管理员端消费；成员端展示与模板占位符只使用用户 schema 内容分组，
        因此内置契约字段（含平台凭据）不会泄漏到成员端或模板命名空间。
        """
        definition = self.load_fields_definition()
        groups: List[Dict[str, Any]] = [
            group_def for group_def in (definition.get("admin_fields", []) or [])
            if isinstance(group_def, dict)
        ]
        groups.append(build_group_definition())
        return sorted(groups, key=lambda g: g.get("group_order", 0))
        
    