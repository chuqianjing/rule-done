#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置数据管理
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
from src.utils.json_storage import JSONStorage
from src.data.field_manager import FieldManager
from src.utils.crypto_storage import DecryptionError


class ConfigManager:
    """配置管理器类"""

    # 类级别的密码缓存，在程序运行期间保持
    _password_cache: Optional[str] = None

    def __init__(self):
        self.config_path = Path("data/admin_config.json")
        self.json_storage = JSONStorage()
        self.field_manager = FieldManager()

    # ========================= 密码管理 =========================

    @classmethod
    def set_password(cls, password: Optional[str]):
        """设置密码缓存"""
        cls._password_cache = password

    @classmethod
    def get_password(cls) -> Optional[str]:
        """获取密码缓存"""
        return cls._password_cache

    @classmethod
    def clear_password(cls):
        """清除密码缓存"""
        cls._password_cache = None

    def is_encrypted(self) -> bool:
        """检查配置文件是否已加密"""
        return self.json_storage.is_encrypted(self.config_path)

    def has_password(self) -> bool:
        """检查是否设置了密码（文件是否加密）"""
        if not self.config_path.exists():
            return False
        return self.is_encrypted()

    def verify_password(self, password: str) -> bool:
        """验证密码是否正确"""
        if not self.config_path.exists():
            return False
        return self.json_storage.verify_password(self.config_path, password)

    def enable_encryption(self, password: str) -> bool:
        """
        启用加密保护（将明文配置转换为加密配置）

        Args:
            password: 用户设置的密码

        Returns:
            是否成功
        """
        if not self.config_path.exists():
            # 如果配置文件不存在，先创建默认配置
            config = self._get_default_config()
            self.json_storage.write_json(str(self.config_path), config)

        # 转换为加密格式
        success = self.json_storage.convert_to_encrypted(self.config_path, password)
        if success:
            self.set_password(password)
        return success

    def disable_encryption(self, password: str) -> bool:
        """
        禁用加密保护（将加密配置转换为明文配置）

        Args:
            password: 当前密码（用于验证和解密）

        Returns:
            是否成功

        Raises:
            DecryptionError: 密码错误
        """
        if not self.is_encrypted():
            return True

        # 验证密码
        if not self.verify_password(password):
            raise DecryptionError("密码错误")

        # 转换为明文格式
        success = self.json_storage.convert_to_plaintext(self.config_path, password)
        if success:
            self.clear_password()
        return success

    def change_password(self, old_password: str, new_password: str) -> bool:
        """
        修改密码

        Args:
            old_password: 当前密码
            new_password: 新密码

        Returns:
            是否成功

        Raises:
            DecryptionError: 当前密码错误
        """
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
        """
        加载配置

        Args:
            password: 密码（如果文件已加密）。如果为 None，会尝试使用缓存的密码。

        Returns:
            配置数据
        """
        if not self.config_path.exists():
            return self._get_default_config()

        try:
            # 使用传入的密码或缓存的密码
            pwd = password or self.get_password()

            if self.is_encrypted():
                if pwd is None:
                    raise DecryptionError("配置文件已加密，需要提供密码")
                config = self.json_storage.read_json_encrypted(str(self.config_path), pwd)
            else:
                config = self.json_storage.read_json(str(self.config_path))

            return config
        except DecryptionError:
            raise
        except Exception:
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """获取默认配置"""
        # version用来标记管理员配置的版本，按照年月格式
        version = datetime.now().strftime("%Y.%m")
        config = {
            "version": version,
            "configured": False,
            "basic_data": {},
            "template_data": {}
        }
        return config

    def save_config(self, config: dict, password: Optional[str] = None) -> bool:
        """
        保存配置

        Args:
            config: 配置数据
            password: 密码（如果需要加密）。如果为 None，会尝试使用缓存的密码。

        Returns:
            是否成功
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

        return True

    # ========================= lock相关操作 =========================

    def is_locked(self) -> bool:
        """检查配置是否已锁定"""
        if not self.config_path.exists():
            return False
        try:
            config = self.load_config()
            return config.get('locked', False)
        except Exception:
            return False

    def lock_config(self):
        """锁定配置"""
        config = self.load_config()
        config['locked'] = True
        config['locked_at'] = datetime.now().isoformat()
        self.save_config(config)
        return True

    def unlock_config(self):
        """解锁配置"""
        config = self.load_config()
        config['locked'] = False
        config['unlocked_at'] = datetime.now().isoformat()
        self.save_config(config)
        return True



