#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
成员数据管理模块

本模块负责成员信息文件 (member_info.json) 的持久化、加密/解密、
数据验证以及生命周期管理（模板锁定）。

核心职责：
- 成员数据文件的加载、保存、备份
- 基于密码的加密/解密与密码验证
- 成员数据字段验证及逻辑关系验证
- 模板数据的锁定管理
- 内存级密码缓存管理

成员数据基本结构：
- created_at：成员数据创建时间戳
- basic_data：基础信息部分（姓名、性别等）
- template_data：模板数据部分（各模板对应数据）

Author: 楚乾靖
Date: 2026-03
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from src.persistence.field_manager import FieldManager
from src.utils.crypto_storage import DecryptionError
from src.utils.json_storage import JSONStorage
from src.utils.validators import Validators
from src.utils.file_path import get_runtime_data_dir


class InfoManager:
    """成员数据管理器类

    负责成员信息文件的完整生命周期，包括加载、保存、加密、解密以及数据验证。
    提供统一接口供上层应用（DataManager）使用。

    类属性：
        _password_cache (str | None): 类级别密码缓存，在程序运行期间保持。

    实例属性：
        data_path (Path): 数据文件路径，指向 data/member_info.json。
        json_storage (JSONStorage): JSON 存储工具，处理文件 I/O 和加密。
        validators (Validators): 数据验证器，负责字段与逻辑校验。
        field_manager (FieldManager): 字段定义管理器。
    """

    # 类级别的密码缓存，在程序运行期间保持
    _password_cache: Optional[str] = None

    def __init__(self):
        """初始化成员数据管理器。

        创建各类工具实例、设置数据文件路径。
        """
        self.data_path = get_runtime_data_dir() / "member_info.json"
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
        """启用加密保护（将明文数据转换为加密数据）"""
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
        """禁用加密保护（将加密数据转换为明文数据）"""
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
        """修改密码"""
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
        """加载成员数据

        若文件不存在，返回默认数据结构。若文件已加密，需提供密码或使用缓存密码。

        Args:
            password (str | None): 密码（如果文件已加密）。若为 None，
                会尝试使用缓存的密码。

        Returns:
            dict: 成员数据字典。

        Raises:
            DecryptionError: 解密失败或密码缺失。
            ValueError: JSON 格式错误。
        """
        if not self.data_path.exists():
            return self._get_default_info()
        
        pwd = password or self.get_password()

        if self.is_encrypted():
            if pwd is None:
                raise DecryptionError("数据文件已加密，需要提供密码")
            return self.json_storage.read_json_encrypted(str(self.data_path), pwd)
        else:
            return self.json_storage.read_json(str(self.data_path))

    def _get_default_info(self) -> dict:
        """获取默认数据结构

        Returns:
            dict: 包含初始字段的默认成员数据对象。

        说明：
            - created_at：按 ISO 格式记录成员数据创建时间。
            - basic_data：基础信息容器，初始为空。
            - template_data：模板数据容器，初始为空。
        """
        return {
            "created_at": datetime.now().isoformat(),
            "basic_data": {},
            "template_data": {}
        }

    def save_data(self, data: dict, password: Optional[str] = None) -> bool:
        """保存成员数据

        保存前执行数据验证（字段验证 + 逻辑关系验证）。
        更新 last_modified 时间戳。
        支持多种场景：明文保存、加密保存、从明文转换为加密。

        Args:
            data (dict): 成员数据。
            password (str | None): 密码（如果需要加密）。若为 None，
                会尝试使用缓存的密码。

        Returns:
            bool: 保存是否成功。

        Raises:
            ValueError: 数据验证失败，包含详细的字段错误或逻辑错误信息。
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

    def validate_data(self, data: dict) -> dict:
        """执行成员数据验证

        分为两个层次的验证：
        1. 字段验证：根据字段定义验证每个字段的有效性。
        2. 逻辑验证：验证字段之间的逻辑关系（如入党时间与转正时间）。

        Args:
            data (dict): 待验证的成员数据。

        Returns:
            dict: 验证结果，包含以下结构：
                {
                    "basic_data": {
                        "valid": bool,
                        "errors": [{ "field": str, "message": str }, ...]
                    },
                    "logical": {
                        "valid": bool,
                        "errors": [{ "field": str, "message": str }, ...]
                    }
                }
        """
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
        """锁定成员的模板数据快照

        用于在导出模板文档确认数据无误无需修改后，持续留存该模板数据。

        Args:
            template_id (str): 模板的ID。
            basic_entry (dict): 模板渲染时使用的基本项。
            template_entry (dict): 模板渲染时使用的专有项。

        Returns:
            bool: 锁定是否成功。

        Note:
            - 锁定后会在 member_info.json 的 template_data 中创建对应模板ID的条目
            - 设置 locked=True 标识。
        """
        member_info = self.load_data()
        if "template_data" not in member_info:
            member_info["template_data"] = {}
        member_info["template_data"][template_id] = {}

        member_info["template_data"][template_id]["basic_entry"] = basic_entry
        member_info["template_data"][template_id]["template_entry"] = template_entry
        member_info["template_data"][template_id]["locked"] = True
        self.save_data(member_info)
