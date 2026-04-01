#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
系统设置数据管理模块

本模块负责系统全局设置的持久化管理，包括加载、保存系统配置文件。

核心职责：
- 系统设置文件的加载和保存
- 设置数据的持久化存储
- 异常处理和错误提示

Author: 楚乾靖
Date: 2026-03
"""

from pathlib import Path
from typing import Any, Dict
from src.utils.json_storage import JSONStorage


class SettingsManager:
    """系统设置管理器类

    负责系统全局设置的管理和持久化，提供统一接口供上层应用使用。
    通过 JSONStorage 工具类处理 JSON 文件的读写操作。

    实例属性：
        config_path (Path): 系统设置文件路径，指向 data/system_settings.json。
        json_storage (JSONStorage): JSON 存储工具，处理文件 I/O。
    """
    
    def __init__(self):
        """初始化设置管理器。

        创建 JSONStorage 实例并设置设置文件路径。
        """
        self.config_path = Path("data/system_settings.json")
        self.json_storage = JSONStorage()

    def load_settings(self) -> Dict[str, Any]:
        """加载系统设置

        从设置文件中读取并返回系统设置。如果文件不存在，返回空字典。

        Returns:
            Dict[str, Any]: 系统设置字典。如果文件不存在则返回空字典 {}。

        Raises:
            json.JSONDecodeError: 如果设置文件格式不是有效的 JSON。
            IOError: 如果读取文件时发生 I/O 错误。
        """
        if not self.config_path.exists():
            return {}
        return self.json_storage.read_json(str(self.config_path))
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """保存系统设置

        将系统设置保存到设置文件。如果目录不存在则自动创建。

        Args:
            settings (Dict[str, Any]): 要保存的系统设置字典。

        Returns:
            bool: 保存成功返回 True。

        Raises:
            IOError: 如果写入文件时发生 I/O 错误。
            Exception: 其他 JSON 序列化或文件操作错误。
        """
        self.json_storage.write_json(str(self.config_path), settings)
        
    