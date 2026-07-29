#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""同步领域加解密助手。"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken
from src.utils.file_path import load_bootstrap_settings, save_bootstrap_settings


class SyncCryptoHelper:
    """同步业务专用的加解密助手。"""

    SECRET_PREFIX = "enc::"

    def _get_install_id(self) -> str:
        settings = load_bootstrap_settings()
        install_id = settings.get("install_id")
        if not install_id:
            install_id = str(uuid.uuid4())
            settings["install_id"] = install_id
            save_bootstrap_settings(settings)
        return install_id

    def _build_cipher(self, use_install_id: bool = True) -> Fernet:
        """构造用于本地敏感字段加密的密钥。"""
        if use_install_id:
            install_id = self._get_install_id()
            machine_seed = f"{install_id}|party0101-remote-sync"
        else:
            machine_seed = "party0101-remote-sync"
        digest = hashlib.sha256(machine_seed.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)

    def encrypt_text(self, value: str, use_install_id: bool = True) -> str:
        if not value:
            return ""
        if value.startswith(self.SECRET_PREFIX):
            return value
        cipher = self._build_cipher(use_install_id=use_install_id)
        encrypted = cipher.encrypt(value.encode("utf-8")).decode("ascii")
        return f"{self.SECRET_PREFIX}{encrypted}"

    def decrypt_text(self, value: str, use_install_id: bool = True) -> str:
        if not value:
            return ""
        if not value.startswith(self.SECRET_PREFIX):
            return value
        cipher = self._build_cipher(use_install_id=use_install_id)
        token = value[len(self.SECRET_PREFIX):]
        try:
            return cipher.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("远程同步密钥无法解密，请重新配置凭据。") from exc

    def encrypt_payload(self, payload: Dict[str, Any], password: str) -> bytes:
        """用密码加密整个 payload（PBKDF2 + Fernet）。"""
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes

        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        cipher = Fernet(key)
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        encrypted = cipher.encrypt(data)
        return salt + encrypted

    def decrypt_payload(self, encrypted_data: bytes, password: str) -> Dict[str, Any]:
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes

        salt = encrypted_data[:16]
        encrypted = encrypted_data[16:]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        cipher = Fernet(key)
        decrypted = cipher.decrypt(encrypted)
        return json.loads(decrypted.decode("utf-8"))
