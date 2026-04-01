#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
配置数据管理模块

本模块负责管理员配置文件 (admin_config.json) 的持久化、加密/解密、
以及配置生命周期管理（加锁/解锁）。

核心职责：
- 配置文件的加载、保存、备份
- 基于密码的加密/解密与密码验证
- 配置锁定/解锁状态管理
- 内存级密码缓存管理

配置的基本结构：
- version：按 YYYY.MM 格式记录配置版本，作用于成员端模板页的占位符映射
- configured：配置是否完成的标志
- basic_data：基础数据
- template_data：模板数据

Author: 楚乾靖
Date: 2026-03
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from src.persistence.field_manager import FieldManager
from src.utils.crypto_storage import DecryptionError
from src.utils.json_storage import JSONStorage


class ConfigManager:
    """配置管理器类。

    负责管理员配置文件的完整生命周期，包括加载、保存、加密、解锁/加锁以及密码管理。
    提供统一接口供上层应用使用。

    类属性：
        _password_cache (str | None): 类级别密码缓存，在程序运行期间保持。

    实例属性：
        config_path (Path): 配置文件路径，指向 data/admin_config.json。
        json_storage (JSONStorage): JSON 存储工具，处理文件 I/O 和加密。
        field_manager (FieldManager): 字段定义管理器。
    """

    # 类级别的密码缓存，在程序运行期间保持
    _password_cache: Optional[str] = None

    def __init__(self):
        """初始化配置管理器
        """
        self.config_path = Path("data/admin_config.json")
        self.json_storage = JSONStorage()
        self.field_manager = FieldManager()

    # ========================= 密码管理 =========================

    @classmethod
    def set_password(cls, password: Optional[str]):
        cls._password_cache = password

    @classmethod
    def get_password(cls) -> Optional[str]:
        return cls._password_cache

    @classmethod
    def clear_password(cls):
        cls._password_cache = None

    def is_encrypted(self) -> bool:
        """检查配置文件是否加密"""
        return self.json_storage.is_encrypted(self.config_path)

    def has_password(self) -> bool:
        """检查是否存在密码（即配置文件是否加密）"""
        if not self.config_path.exists():
            return False
        return self.is_encrypted()

    def verify_password(self, password: str) -> bool:
        """验证密码是否正确"""
        if not self.config_path.exists():
            return False
        return self.json_storage.verify_password(self.config_path, password)

    def enable_encryption(self, password: str) -> bool:
        """启用加密保护（将明文配置转换为加密配置）"""

        # 如果配置文件不存在，先创建默认配置
        if not self.config_path.exists():
            config = self._get_default_config()
            self.json_storage.write_json(str(self.config_path), config)
        # 转换为加密格式
        success = self.json_storage.convert_to_encrypted(self.config_path, password)
        # 设置密码缓存
        if success:
            self.set_password(password)
        return success

    def disable_encryption(self, password: str) -> bool:
        """禁用加密保护（将加密配置转换为明文配置）"""
        if not self.is_encrypted():
            return True

        # 验证密码
        if not self.verify_password(password):
            raise DecryptionError("密码错误")
        # 转换为明文格式
        success = self.json_storage.convert_to_plaintext(self.config_path, password)
        # 清除密码缓存
        if success:
            self.clear_password()
        return success

    def change_password(self, old_password: str, new_password: str) -> bool:
        """修改密码"""
        if not self.is_encrypted():
            raise ValueError("配置文件未加密，无法修改密码")

        # 验证旧密码
        if not self.verify_password(old_password):
            raise DecryptionError("当前密码错误")

        # 读取数据
        config = self.json_storage.read_json_encrypted(str(self.config_path), old_password)

        # 使用新密码重新加密
        success = self.json_storage.write_json_encrypted(str(self.config_path), config, new_password)
        if success:
            self.set_password(new_password)
        return success

    # ========================= 加载&保存 =========================

    def load_config(self, password: Optional[str] = None) -> dict:
        """加载配置

        获取任何配置数据的入口方法，支持在加密时自动处理加密文件和密码验证。

        Args:
            password (str | None): 密码（如果文件已加密）。若为 None，
                会尝试使用缓存的密码。

        Returns:
            dict: admin_config数据字典。

        Raises:
            DecryptionError: 解密失败或密码缺失。
            ValueError: JSON 格式错误。
        """
        if not self.config_path.exists():
            return self._get_default_config()

        # 使用传入的密码或缓存的密码
        pwd = password or self.get_password()

        if self.is_encrypted():
            if pwd is None:
                raise DecryptionError("配置文件已加密，需要提供密码")
            return self.json_storage.read_json_encrypted(str(self.config_path), pwd)
        else:
            return self.json_storage.read_json(str(self.config_path))

    def _get_default_config(self) -> dict:
        """获取默认配置

        Returns:
            dict: 包含初始字段的默认配置对象。
        """
        # version 用来标记管理员配置的版本，按照年月格式
        version = datetime.now().strftime("%Y.%m")
        config = {
            "version": version,
            "configured": False,
            "basic_data": {},
            "template_data": {}
        }
        return config

    def save_config(self, config: dict, password: Optional[str] = None) -> bool:
        """保存配置

        支持多种场景：明文保存、加密保存、从明文转换为加密。
        自动更新 last_modified 时间戳。

        Args:
            config (dict): 配置数据。
            password (str | None): 密码（如果需要加密）。若为 None，
                会尝试使用缓存的密码。

        Returns:
            bool: 保存是否成功。
        """
        # 更新配置时间戳
        config['last_modified'] = datetime.now().isoformat()

        # 使用传入的密码或缓存的密码
        pwd = password or self.get_password()

        if pwd and self.is_encrypted():
            # 如果有密码且文件已加密，使用加密方式保存
            self.json_storage.write_json_encrypted(str(self.config_path), config, pwd)
        elif pwd and not self.config_path.exists():
            # 如果有密码但文件不存在，创建加密文件
            self.json_storage.write_json_encrypted(str(self.config_path), config, pwd)
        elif pwd:
            # 如果有密码但文件未加密，先保存明文再转换
            self.json_storage.write_json(str(self.config_path), config)
            self.json_storage.convert_to_encrypted(self.config_path, pwd)
        else:
            # 无密码，使用明文保存
            self.json_storage.write_json(str(self.config_path), config)

    # ========================= lock相关操作 =========================

    def is_locked(self) -> bool:
        """检查配置是否已锁定"""
        if not self.config_path.exists():
            return False
        config = self.load_config()
        return config.get('locked', False)

    def lock_config(self):
        """锁定配置"""
        config = self.load_config()
        config['locked'] = True
        config['locked_at'] = datetime.now().isoformat()
        self.save_config(config)

    def unlock_config(self):
        """解锁配置"""
        config = self.load_config()
        config['locked'] = False
        config['unlocked_at'] = datetime.now().isoformat()
        self.save_config(config)



