#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
加密存储工具模块

使用 Argon2id 进行密码哈希
使用 AES-256-GCM 进行数据加密
使用 PBKDF2-SHA256 进行密钥派生
"""

import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Union, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

class CryptoStorageError(Exception):
    """加密存储相关异常基类"""
    pass


class DecryptionError(CryptoStorageError):
    """解密失败异常（密码错误或数据损坏）"""
    pass


class PasswordVerificationError(CryptoStorageError):
    """密码验证失败异常"""
    pass


class CryptoStorage:
    """
    加密存储工具类

    功能：
    1. 密码哈希：使用 Argon2id（如果可用）或 PBKDF2-SHA256
    2. 数据加密：使用 AES-256-GCM
    3. 密钥派生：使用 PBKDF2-SHA256

    文件格式（加密后）：
    {
        "encrypted": true,
        "version": "1.0",
        "password_hash": "<Argon2/PBKDF2哈希>",
        "salt": "<Base64编码的盐值>",
        "nonce": "<Base64编码的随机数>",
        "data": "<Base64编码的加密数据>"
    }
    """

    # 加密参数
    SALT_LENGTH = 32        # 盐值长度（字节）
    NONCE_LENGTH = 12       # GCM nonce 长度（字节）
    KEY_LENGTH = 32         # AES-256 密钥长度（字节）
    KDF_ITERATIONS = 600000 # PBKDF2 迭代次数
    VERSION = "1.0"

    def __init__(self):
        """初始化加密存储工具"""
        # 使用 Argon2id 进行密码哈希
        self.password_hasher = PasswordHasher(
            time_cost=3,        # 迭代次数
            memory_cost=65536,  # 内存使用量（KB）
            parallelism=4,      # 并行度
            hash_len=32,        # 哈希长度
            salt_len=16,        # 盐长度
        )

    # ==================== 密码哈希相关 ====================

    def hash_password(self, password: str) -> str:
        """
        对密码进行哈希处理

        Args:
            password: 明文密码

        Returns:
            密码哈希值
        """
        return self.password_hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        验证密码是否正确

        Args:
            password: 明文密码
            password_hash: 存储的密码哈希

        Returns:
            密码是否正确
        """
        try:
            self.password_hasher.verify(password_hash, password)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False

    # ==================== 密钥派生 ====================

    def derive_key(self, password: str, salt: bytes) -> bytes:
        """
        从密码派生加密密钥

        Args:
            password: 用户密码
            salt: 随机盐值

        Returns:
            32字节的AES密钥
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=salt,
            iterations=self.KDF_ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))

    # ==================== 加密/解密 ====================

    def encrypt_data(self, data: Any, password: str) -> dict:
        """
        加密数据

        Args:
            data: 要加密的数据（任意可JSON序列化的对象）
            password: 用户密码

        Returns:
            包含加密数据和元信息的字典
        """
        # 将数据序列化为 JSON 字符串
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        plaintext = json_str.encode('utf-8')

        # 生成随机盐值和 nonce
        salt = os.urandom(self.SALT_LENGTH)
        nonce = os.urandom(self.NONCE_LENGTH)

        # 从密码派生密钥
        key = self.derive_key(password, salt)

        # 使用 AES-256-GCM 加密
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        # 计算密码哈希（用于后续验证）
        password_hash = self.hash_password(password)

        return {
            "encrypted": True,
            "version": self.VERSION,
            "password_hash": password_hash,
            "salt": base64.b64encode(salt).decode('ascii'),
            "nonce": base64.b64encode(nonce).decode('ascii'),
            "data": base64.b64encode(ciphertext).decode('ascii')
        }

    def decrypt_data(self, encrypted_obj: dict, password: str) -> Any:
        """
        解密数据

        Args:
            encrypted_obj: 包含加密数据的字典
            password: 用户密码

        Returns:
            解密后的原始数据对象

        Raises:
            DecryptionError: 解密失败（密码错误或数据损坏）
        """
        try:
            # 验证是否为加密数据
            if not encrypted_obj.get("encrypted"):
                raise DecryptionError("数据未加密")

            # 提取加密参数
            salt = base64.b64decode(encrypted_obj["salt"])
            nonce = base64.b64decode(encrypted_obj["nonce"])
            ciphertext = base64.b64decode(encrypted_obj["data"])

            # 从密码派生密钥
            key = self.derive_key(password, salt)

            # 使用 AES-256-GCM 解密
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)

            # 将解密后的字节转换回 JSON 对象
            json_str = plaintext.decode('utf-8')
            return json.loads(json_str)

        except json.JSONDecodeError as e:
            raise DecryptionError(f"解密后数据格式错误：{e}")
        except Exception as e:
            # 捕获所有加密相关异常并转换为 DecryptionError
            error_msg = str(e)
            if "tag" in error_msg.lower() or "authentication" in error_msg.lower():
                raise DecryptionError("密码错误或数据已损坏")
            raise DecryptionError(f"解密失败：{error_msg}")

    # ==================== 文件读写 ====================

    def read_encrypted_file(self, file_path: Union[str, Path], password: str) -> Any:
        """
        读取并解密文件

        Args:
            file_path: 文件路径
            password: 用户密码

        Returns:
            解密后的数据对象

        Raises:
            FileNotFoundError: 文件不存在
            DecryptionError: 解密失败
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(path, 'rb') as f:
            content = f.read()

        try:
            encrypted_obj = json.loads(content.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise DecryptionError("文件格式错误或已损坏")

        return self.decrypt_data(encrypted_obj, password)

    def write_encrypted_file(self, file_path: Union[str, Path], data: Any, password: str) -> bool:
        """
        加密并写入文件

        Args:
            file_path: 文件路径
            data: 要加密的数据
            password: 用户密码

        Returns:
            是否成功
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        encrypted_obj = self.encrypt_data(data, password)
        json_str = json.dumps(encrypted_obj, ensure_ascii=False, indent=2)

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(json_str)
        except Exception as e:
            raise IOError(f"写入文件失败: {e}")
        return True

    # ==================== 辅助方法 ====================

    @staticmethod
    def is_encrypted_file(file_path: Union[str, Path]) -> bool:
        """
        检查文件是否为加密格式

        Args:
            file_path: 文件路径

        Returns:
            是否为加密文件
        """
        path = Path(file_path)
        if not path.exists():
            return False

        try:
            with open(path, 'rb') as f:
                content = f.read()
            data = json.loads(content.decode('utf-8'))
            return data.get("encrypted", False) is True
        except Exception:
            raise IOError("无法读取文件或文件格式错误")

    @staticmethod
    def get_password_hash_from_file(file_path: Union[str, Path]) -> Optional[str]:
        """
        从加密文件中获取密码哈希（用于验证密码）

        Args:
            file_path: 文件路径

        Returns:
            密码哈希，如果文件不存在或未加密则返回 None
        """
        path = Path(file_path)
        if not path.exists():
            return None

        try:
            with open(path, 'rb') as f:
                content = f.read()
            data = json.loads(content.decode('utf-8'))
            if data.get("encrypted"):
                return data.get("password_hash")
        except Exception:
            return None

        return None
