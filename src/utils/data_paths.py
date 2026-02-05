#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
嵌套字典路径工具
统一处理用点号路径（如 "a.b.c"）从 dict 中读写值的逻辑
"""

from typing import Any


def get_value_by_path(data: dict, path: str, default: Any = "") -> Any:
    """
    根据路径从嵌套字典中获取值

    Args:
        data: 源字典
        path: 形如 "a.b.c" 的路径
        default: 当路径不存在或类型不匹配时返回的默认值
    """
    if not path:
        return default

    keys = path.split(".")
    value: Any = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key, default)
        else:
            return default
    return value


def set_value_by_path(data: dict, path: str, value: Any) -> None:
    """
    根据路径在嵌套字典中设置值，如有必要自动创建中间字典

    Args:
        data: 目标字典
        path: 形如 "a.b.c" 的路径
        value: 要设置的值
    """
    if not path:
        return

    keys = path.split(".")
    current: Any = data
    for key in keys[:-1]:
        if not isinstance(current, dict):
            # 如果路径中间不是 dict，直接中止
            return
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]

    if isinstance(current, dict):
        current[keys[-1]] = value


