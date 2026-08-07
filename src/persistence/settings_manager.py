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
from src.utils.file_path import get_runtime_data_dir


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
        self.config_path = get_runtime_data_dir() / "system_settings.json"
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

    # ======================= 信息同步（成员端 -> 远程） =======================

    @staticmethod
    def get_default_info_sync_settings() -> Dict[str, Any]:
        return {
            "last_sync_result": {
                "time": "",
                "status": "",
                "message": "",
                "target": "",
            }
        }

    @staticmethod
    def merge_info_sync_settings(config: Dict[str, Any] | None) -> Dict[str, Any]:
        merged = SettingsManager.get_default_info_sync_settings()
        if not isinstance(config, dict):
            return merged

        merged.update({k: v for k, v in config.items() if k in merged})
        return merged

    # ======================= 配置同步（管理员端 -> 远程） =======================

    @staticmethod
    def get_default_config_sync_settings() -> Dict[str, Any]:
        return {
            "provider": "github",
            "encrypt_key": "",
            "github": {
                "repo": "",
                "branch": "main",
                "file_path": "admin_config.json",
                "token": "",
                "commit_message": "chore: sync admin config",
            },
            "aliyun_oss": {
                "endpoint": "",
                "bucket": "",
                "object_key": "admin_config.json",
                "access_key_id": "",
                "access_key_secret": "",
            },
            "last_sync_result": {
                "time": "",
                "status": "",
                "message": "",
                "target": "",
            },
        }

    @staticmethod
    def merge_config_sync_settings(config: Dict[str, Any] | None) -> Dict[str, Any]:
        merged = SettingsManager.get_default_config_sync_settings()
        if not isinstance(config, dict):
            return merged

        merged.update({k: v for k, v in config.items() if k in merged and k not in ("github", "aliyun_oss")})

        if isinstance(config.get("github"), dict):
            merged["github"].update(config["github"])
        if isinstance(config.get("aliyun_oss"), dict):
            merged["aliyun_oss"].update(config["aliyun_oss"])

        provider = str(merged.get("provider", "github")).lower()
        merged["provider"] = provider if provider in ("github", "aliyun_oss") else "github"
        return merged

    # ======================= 资源分发（管理员端 -> 远程） =======================

    @staticmethod
    def get_default_resource_push_settings() -> Dict[str, Any]:
        return {
            "prefix": "resources",
            "last_sync_result": {
                "time": "",
                "status": "",
                "message": "",
                "target": "",
            },
        }

    @staticmethod
    def merge_resource_push_settings(config: Dict[str, Any] | None) -> Dict[str, Any]:
        merged = SettingsManager.get_default_resource_push_settings()
        if not isinstance(config, dict):
            return merged
        merged.update({k: v for k, v in config.items() if k in merged})
        return merged

    # ======================= 资源分发（成员端 <- 远程） =======================

    @staticmethod
    def get_default_resource_pull_settings() -> Dict[str, Any]:
        return {
            "auto_download": True,
            "last_sync_result": {
                "time": "",
                "status": "",
                "message": "",
            },
        }

    @staticmethod
    def merge_resource_pull_settings(config: Dict[str, Any] | None) -> Dict[str, Any]:
        merged = SettingsManager.get_default_resource_pull_settings()
        if not isinstance(config, dict):
            return merged
        merged.update({k: v for k, v in config.items() if k in merged})
        return merged

    # ======================= 更新检查忽略版本 =======================

    def get_ignored_update_version(self) -> str | None:
        """获取用户选择忽略的更新版本号。

        Returns:
            str | None: 被忽略的版本号字符串（如 "v1.0.12"），没有则返回 None。
        """
        settings = self.load_settings()
        update_check = settings.get("update_check", {})
        if not isinstance(update_check, dict):
            return None
        ignored = update_check.get("ignored_version")
        return str(ignored) if ignored else None

    def set_ignored_update_version(self, version: str) -> None:
        """设置用户选择忽略的版本号。

        Args:
            version (str): 要忽略的版本号（如 "v1.0.13"）。
        """
        settings = self.load_settings()
        if "update_check" not in settings or not isinstance(settings["update_check"], dict):
            settings["update_check"] = {}
        settings["update_check"]["ignored_version"] = version
        self.save_settings(settings)

    # ======================= 公告忽略 =======================

    def get_dismissed_announcement_id(self) -> str | None:
        """获取用户已忽略的公告 ID。

        Returns:
            str | None: 被忽略的公告 ID，没有则返回 None。
        """
        settings = self.load_settings()
        announcement = settings.get("announcement", {})
        if not isinstance(announcement, dict):
            return None
        dismissed = announcement.get("dismissed_id")
        return str(dismissed) if dismissed else None

    def set_dismissed_announcement_id(self, announcement_id: str) -> None:
        """保存用户已忽略的公告 ID。

        Args:
            announcement_id (str): 要忽略的公告 ID。
        """
        settings = self.load_settings()
        if "announcement" not in settings or not isinstance(settings["announcement"], dict):
            settings["announcement"] = {}
        settings["announcement"]["dismissed_id"] = announcement_id
        self.save_settings(settings)
    