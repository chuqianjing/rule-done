#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
成员数据管理
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
from src.utils.json_storage import JSONStorage
from src.utils.validators import Validators
from src.data.field_manager import FieldManager
from src.utils.crypto_storage import DecryptionError


class InfoManager:
    """成员数据管理器类"""

    # 类级别的密码缓存，在程序运行期间保持
    _password_cache: Optional[str] = None

    def __init__(self):
        self.data_path = Path("data/member_info.json")
        self.json_storage = JSONStorage()
        self.validators = Validators()
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
        """检查数据文件是否已加密"""
        return self.json_storage.is_encrypted(self.data_path)

    def has_password(self) -> bool:
        """检查是否设置了密码（文件是否加密）"""
        if not self.data_path.exists():
            return False
        return self.is_encrypted()

    def verify_password(self, password: str) -> bool:
        """验证密码是否正确"""
        if not self.data_path.exists():
            return False
        return self.json_storage.verify_password(self.data_path, password)

    def enable_encryption(self, password: str) -> bool:
        """
        启用加密保护（将明文数据转换为加密数据）

        Args:
            password: 用户设置的密码

        Returns:
            是否成功
        """
        if not self.data_path.exists():
            # 如果数据文件不存在，先创建默认数据
            data = self._get_default_info()
            self.json_storage.write_json(str(self.data_path), data)

        # 转换为加密格式
        success = self.json_storage.convert_to_encrypted(self.data_path, password)
        if success:
            self.set_password(password)
        return success

    def disable_encryption(self, password: str) -> bool:
        """
        禁用加密保护（将加密数据转换为明文数据）

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
        success = self.json_storage.convert_to_plaintext(self.data_path, password)
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
            raise ValueError("数据文件未加密，无法修改密码")

        # 验证旧密码
        if not self.verify_password(old_password):
            raise DecryptionError("当前密码错误")

        # 读取数据
        data = self.json_storage.read_json_encrypted(str(self.data_path), old_password)

        # 使用新密码重新加密
        success = self.json_storage.write_json_encrypted(str(self.data_path), data, new_password)
        if success:
            self.set_password(new_password)
        return success

    # ========================= 加载&保存 =========================

    def load_data(self, password: Optional[str] = None) -> dict:
        """
        加载成员数据

        Args:
            password: 密码（如果文件已加密）。如果为 None，会尝试使用缓存的密码。

        Returns:
            成员数据
        """
        if not self.data_path.exists():
            return self._get_default_info()

        try:
            # 使用传入的密码或缓存的密码
            pwd = password or self.get_password()

            if self.is_encrypted():
                if pwd is None:
                    raise DecryptionError("数据文件已加密，需要提供密码")
                return self.json_storage.read_json_encrypted(str(self.data_path), pwd)
            else:
                return self.json_storage.read_json(str(self.data_path))
        except DecryptionError:
            raise
        except Exception:
            return self._get_default_info()

    def _get_default_info(self) -> dict:
        """获取默认数据结构"""
        return {
            "version": "1.0",     # 需要version吗
            "created_at": datetime.now().isoformat(),
            "basic_data": {},
            "template_data": {},
            "export_history": []
        }

    def save_data(self, data: dict, password: Optional[str] = None) -> bool:
        """
        保存成员数据

        Args:
            data: 成员数据
            password: 密码（如果需要加密）。如果为 None，会尝试使用缓存的密码。

        Returns:
            是否成功
        """
        # 执行数据验证
        validation_result = self.validate_data(data)
        if not validation_result['basic_data']['valid'] or not validation_result['logical']['valid']:
            message = "数据验证失败:\n"
            if not validation_result['basic_data']['valid']:
                message += "信息字段错误:\n"
                for error in validation_result['basic_data']['errors']:
                    message += f" - {error['field']}: {error['message']}\n"
            if not validation_result['logical']['valid']:
                message += "逻辑关系错误:\n"
                for error in validation_result['logical']['errors']:
                    message += f" - {error['field']}: {error['message']}\n"
            raise ValueError(message)

        # 更新修改时间
        data['last_modified'] = datetime.now().isoformat()

        # 使用传入的密码或缓存的密码
        pwd = password or self.get_password()

        if pwd and self.is_encrypted():
            # 如果有密码且文件已加密，使用加密方式保存
            self.json_storage.write_json_encrypted(str(self.data_path), data, pwd)
        elif pwd and not self.data_path.exists():
            # 如果有密码但文件不存在，创建加密文件
            self.json_storage.write_json_encrypted(str(self.data_path), data, pwd)
        elif pwd:
            # 如果有密码但文件未加密，先保存明文再转换
            self.json_storage.write_json(str(self.data_path), data)
            self.json_storage.convert_to_encrypted(self.data_path, pwd)
        else:
            # 无密码，使用明文保存
            self.json_storage.write_json(str(self.data_path), data)

        return True

    def validate_data(self, data: dict) -> dict:
        """执行数据验证（结合字段定义和逻辑关系）"""

        result = {
            "basic_data": {"valid": True, "errors": []},
            # "template_data": {},   目前不需要template_data的验证
            "logical": {"valid": True, "errors": []},
        }

        # 字段定义
        fields_def = self.field_manager.load_fields_definition()
        member_fields = fields_def.get("member_fields", [])

        # 数据
        basic_data = data.get("basic_data", {})

        # 基本信息字段验证
        basic_errors = []
        for field_def in member_fields:
            key = field_def.get("key")
            value = basic_data.get(key, "")
            ok, msg = self.validators.validate_field(field_def, value)
            if not ok and msg:
                basic_errors.append({"field": key, "message": msg})

        result["basic_data"]["valid"] = len(basic_errors) == 0
        result["basic_data"]["errors"] = basic_errors

        # 逻辑关系验证（如入党时间 vs 转正时间）
        logical_errors = self.validators.validate_logical_relations(data)
        result["logical"]["valid"] = len(logical_errors) == 0
        result["logical"]["errors"] = logical_errors

        return result

    def lock_template_data(self, template_id: str, basic_entry: dict, template_entry: dict) -> bool:
        """锁定成员的模板数据，使其无法再修改（如导出后）"""
        member_info = self.load_data()
        if "template_data" not in member_info:
            member_info["template_data"] = {}
        member_info["template_data"][template_id] = {}

        member_info["template_data"][template_id]["basic_entry"] = basic_entry
        member_info["template_data"][template_id]["template_entry"] = template_entry
        member_info["template_data"][template_id]["locked"] = True
        return self.save_data(member_info)
