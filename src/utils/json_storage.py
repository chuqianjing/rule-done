#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
JSON 存储工具
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union
import json
import shutil
from src.utils.crypto_storage import CryptoStorage, DecryptionError


class JSONStorage:
    """JSON 存储类，支持加密和非加密两种模式"""

    def __init__(self):
        self.crypto = CryptoStorage()

    @staticmethod
    def read_json(file_path: Union[str, Path]) -> dict:
        """读取 JSON 文件（非加密）"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"文件格式错误: {e}")
        except Exception as e:
            raise IOError(f"读取文件失败: {e}")
                

    @staticmethod
    def write_json(file_path: Union[str, Path], data: Any) -> bool:
        """写入 JSON 文件（非加密）"""
        path = Path(file_path)

        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            raise IOError(f"写入文件失败: {e}")

    @staticmethod
    def backup_file(file_path: Union[str, Path]) -> Optional[str]:
        """备份文件"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件不存在，无法备份: {file_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_name(f'{path.stem}_backup_{timestamp}{path.suffix}')

        try:
            shutil.copy2(path, backup_path)
            return str(backup_path)
        except Exception as e:
            raise IOError(f"备份文件失败: {e}")

    # ==================== 加密相关方法 ====================

    def read_json_encrypted(self, file_path: Union[str, Path], password: str) -> dict:
        """
        读取加密的 JSON 文件

        Args:
            file_path: 文件路径
            password: 解密密码

        Returns:
            解密后的数据

        Raises:
            FileNotFoundError: 文件不存在
            DecryptionError: 解密失败（密码错误或数据损坏）
        """
        return self.crypto.read_encrypted_file(file_path, password)

    def write_json_encrypted(self, file_path: Union[str, Path], data: Any, password: str) -> bool:
        """
        写入加密的 JSON 文件

        Args:
            file_path: 文件路径
            data: 要加密存储的数据
            password: 加密密码

        Returns:
            是否成功
        """
        return self.crypto.write_encrypted_file(file_path, data, password)

    def is_encrypted(self, file_path: Union[str, Path]) -> bool:
        """
        检查文件是否为加密格式

        Args:
            file_path: 文件路径

        Returns:
            是否为加密文件
        """
        return CryptoStorage.is_encrypted_file(file_path)

    def verify_password(self, file_path: Union[str, Path], password: str) -> bool:
        """
        验证加密文件的密码是否正确

        Args:
            file_path: 文件路径
            password: 待验证的密码

        Returns:
            密码是否正确
        """
        password_hash = CryptoStorage.get_password_hash_from_file(file_path)
        if not password_hash:
            return False
        return self.crypto.verify_password(password, password_hash)

    def convert_to_encrypted(self, file_path: Union[str, Path], password: str) -> bool:
        """
        将明文 JSON 文件转换为加密格式

        Args:
            file_path: 文件路径
            password: 加密密码

        Returns:
            是否成功
        """
        path = Path(file_path)
        if not path.exists():
            return False

        if self.is_encrypted(file_path):
            return True

        data = self.read_json(file_path)

        return self.write_json_encrypted(file_path, data, password)

    def convert_to_plaintext(self, file_path: Union[str, Path], password: str) -> bool:
        """
        将加密 JSON 文件转换为明文格式

        Args:
            file_path: 文件路径
            password: 解密密码

        Returns:
            是否成功

        Raises:
            DecryptionError: 密码错误或数据损坏
        """
        path = Path(file_path)
        if not path.exists():
            return False

        if not self.is_encrypted(file_path):
            return True

        data = self.read_json_encrypted(file_path, password)

        return self.write_json(file_path, data)

    def read_json_auto(self, file_path: Union[str, Path], password: Optional[str] = None) -> dict:
        """
        自动检测并读取 JSON 文件（加密或非加密）

        Args:
            file_path: 文件路径
            password: 密码（如果文件是加密的）

        Returns:
            读取的数据

        Raises:
            FileNotFoundError: 文件不存在
            DecryptionError: 加密文件但未提供密码或密码错误
            ValueError: JSON 格式错误
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if self.is_encrypted(file_path):
            if password is None:
                raise DecryptionError("文件已加密，需要提供密码")
            return self.read_json_encrypted(file_path, password)
        else:
            return self.read_json(file_path)

    def write_json_auto(
        self,
        file_path: Union[str, Path],
        data: Any,
        password: Optional[str] = None
    ) -> bool:
        """
        自动写入 JSON 文件

        Args:
            file_path: 文件路径
            data: 要写入的数据
            password: 密码（如果需要加密）

        Returns:
            是否成功
        """
        if password:
            return self.write_json_encrypted(file_path, data, password)
        else:
            return self.write_json(file_path, data)

