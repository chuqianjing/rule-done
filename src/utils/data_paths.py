#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
嵌套字典路径工具
统一处理用点号路径（如 "a.b.c"）从 dict 中读写值的逻辑
"""

from typing import Any


def get_admin_value(config: dict, group: str, key: str, default: Any = "") -> Any:
    """
    根据 group 和 key 从管理员配置中获取值

    Args:
        config: 管理员配置字典
        group: 分组名称（如 "支部信息"）
        key: 字段名称（如 "支部名称"）
        default: 当路径不存在时返回的默认值
    """
    if not group or not key:
        return default
    
    group_data = config.get(group)
    if isinstance(group_data, dict):
        return group_data.get(key, default)
    return default


def set_admin_value(config: dict, group: str, key: str, value: Any) -> None:
    """
    根据 group 和 key 在管理员配置中设置值

    Args:
        config: 管理员配置字典
        group: 分组名称（如 "支部信息"）
        key: 字段名称（如 "支部名称"）
        value: 要设置的值
    """
    if not group or not key:
        return
    
    if group not in config or not isinstance(config[group], dict):
        config[group] = {}
    
    config[group][key] = value


