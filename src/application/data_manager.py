#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
数据管理模块

主要功能：
1. fields_definition: 表单字段定义的加载与管理
2. admin_config.json: 管理员配置的本地操作和导入、导出、同步
3. member_info.json: 成员数据的本地操作和导入、导出
4. 针对admin_config.json和member_info.json的密码和加密的处理
5. system_settings.json: 系统设置的管理

Author: 楚乾靖 (Chu Qianjing)
Date: 2026-03
"""

from datetime import datetime
from pathlib import Path
import shutil
from dateutil import parser
from typing import Dict, Any, Tuple
from src.persistence.archive_manager import ArchiveManager
from src.persistence.field_manager import FieldManager
from src.persistence.config_manager import ConfigManager
from src.persistence.info_manager import InfoManager
from src.persistence.template_manager import TemplateManager
from src.persistence.settings_manager import SettingsManager
from src.persistence.sync_manager import SyncManager
from src.utils.json_storage import JSONStorage
from src.utils.file_path import (
    USER_DATA_ROOT_KEY,
    ensure_runtime_directories,
    get_runtime_exports_dir,
    get_user_data_root,
    set_user_data_root,
)


class DataManager:
    """数据管理类
    
    负责应用程序的所有数据操作，包括字段定义、配置管理、成员数据、系统设置和安全认证。
    提供统一的接口来访问和修改各类数据。
    
    属性：
        field_manager (FieldManager): 字段定义管理器
        config_manager (ConfigManager): 配置文件管理器
        info_manager (InfoManager): 成员数据管理器
        template_manager (TemplateManager): 模板管理器
        settings_manager (SettingsManager): 系统设置管理器
        json_storage (JSONStorage): JSON存储工具
        timeout (int): 网络请求超时时间（秒）
    """
    
    _runtime_bootstrapped = False

    def __init__(self):
        """初始化数据管理器
        
        实例化所有子管理器和工具类。
        """
        self.json_storage = JSONStorage()
        self._ensure_runtime_bootstrap()
        self.field_manager = FieldManager()
        self._init_runtime_managers()
        self.template_manager = TemplateManager()
        self.sync_manager = SyncManager()

    def _init_runtime_managers(self):
        """初始化与运行时目录相关的 manager。"""
        self.config_manager = ConfigManager()
        self.info_manager = InfoManager()
        self.image_manager = ArchiveManager()
        self.settings_manager = SettingsManager()

    def _copytree_merge(self, src: Path, dst: Path):
        """合并拷贝目录（不覆盖已存在文件）。"""
        if not src.exists() or not src.is_dir():
            return
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            target = dst / item.name
            if item.is_dir():
                self._copytree_merge(item, target)
            else:
                if not target.exists():
                    shutil.copy2(item, target)

    def _ensure_runtime_bootstrap(self):
        """确保运行时目录可用，并在首次启动时迁移旧目录数据。"""
        if DataManager._runtime_bootstrapped:
            return

        current_root, target_data_dir, target_exports_dir = ensure_runtime_directories()

        legacy_base = Path.cwd()
        legacy_data_dir = legacy_base / "data"
        legacy_exports_dir = legacy_base / "exports"

        # 仅当目标不是当前工作目录时进行迁移，避免开发模式重复拷贝自身。
        if current_root.resolve() != legacy_base.resolve():
            self._copytree_merge(legacy_data_dir, target_data_dir)
            self._copytree_merge(legacy_exports_dir, target_exports_dir)

        settings_path = target_data_dir / "system_settings.json"
        if settings_path.exists():
            try:
                settings = self.json_storage.read_json(settings_path)
            except Exception:
                settings = {}
        else:
            settings = {}

        configured_export = str(settings.get("export_path", "")).strip()
        should_reset_export = not configured_export or configured_export in {"./exports", "exports"}
        if configured_export and not should_reset_export:
            try:
                should_reset_export = Path(configured_export).expanduser().resolve() == legacy_exports_dir.resolve()
            except Exception:
                should_reset_export = False
        if should_reset_export:
            settings["export_path"] = str(target_exports_dir)

        settings[USER_DATA_ROOT_KEY] = str(current_root)
        self.json_storage.write_json(settings_path, settings)

        DataManager._runtime_bootstrapped = True

    def get_user_data_root(self) -> str:
        """获取当前用户数据根目录。"""
        return str(get_user_data_root())

    def update_user_data_root(self, new_root: str) -> Tuple[bool, str]:
        """更新用户数据根目录并迁移运行时数据。"""
        new_root_path = Path(new_root).expanduser().resolve()
        old_root_path = get_user_data_root().expanduser().resolve()
        if new_root_path == old_root_path:
            return False, "已是当前目录，无需修改。"

        old_data_dir = old_root_path / "data"
        # old_exports_dir = old_root_path / "exports"

        _, new_data_dir, new_exports_dir = ensure_runtime_directories(new_root_path)

        self._copytree_merge(old_data_dir, new_data_dir)
        # self._copytree_merge(old_exports_dir, new_exports_dir)

        # 先读取旧设置，再切换根目录，避免路径切换后丢失旧配置。
        old_settings = self.get_system_settings()

        set_user_data_root(str(new_root_path))
        DataManager._runtime_bootstrapped = False
        self._ensure_runtime_bootstrap()
        self._init_runtime_managers()

        settings = old_settings if isinstance(old_settings, dict) else {}
        settings[USER_DATA_ROOT_KEY] = str(new_root_path)
        # settings["export_path"] = str(get_runtime_exports_dir(new_root_path))
        self.settings_manager.save_settings(settings)

        return True, f"用户数据目录已切换到：{new_root_path}"

    # =========================== fields_definition.json ========================

    def get_fields(self, src):
        """获取字段定义
        
        根据请求源返回相应的字段定义。不同的界面使用不同的字段集和组织方式。
        
        Args:
            src (str): 请求源，支持的值：
                - 'admin': 返回管理员字段组（分组呈现）
                - 'member': 返回管理员字段组和成员字段（已过滤交互设置）
                - 'template': 返回所有字段（admin平铺、member、template）
        
        Returns:
            对于'admin':
                list: 按group_order排序的字段组列表
            对于'member':
                tuple: (admin_fields_groups, member_fields) 的二元组
            对于'template':
                tuple: (admin_fields, member_fields, template_fields) 的三元组
        """
        fields_definition = self.field_manager.load_fields_definition()
        admin_fields_groups = sorted(
                fields_definition.get("admin_fields", []),
                key=lambda x: x.get("group_order", 0),
                )
        member_fields = sorted(
                fields_definition.get("member_fields", []),
                key=lambda x: x.get("display", {}).get("order", 0),
                )
        template_fields = fields_definition.get("template_fields", [])
        
        if src == 'admin':
            return admin_fields_groups
        elif src == 'member':
            # 删去admin_fields_groups中的交互设置字段
            admin_fields_groups = [
                group_def for group_def in admin_fields_groups
                if group_def.get("group", "") != "交互设置"
                ]
            return admin_fields_groups, member_fields
        elif src == 'template':
            # template页面不需要分组呈现admin相关字段，所以直接把admin_fields_groups中的字段平铺成一个列表返回，每个字段都带上原来的group信息
            admin_fields = []
            for group in admin_fields_groups:
                group_name = group.get("group", "")
                for field in group.get("fields", []):
                    field_with_group = dict(field)
                    field_with_group["group"] = group_name
                    admin_fields.append(field_with_group)
            return admin_fields, member_fields, template_fields
    
    # =========================== admin_config.json ========================
    # =========================== 从别处进行admin_config.json的相互传输 ========================
    def _build_export_admin_config_payload(self) -> Dict[str, Any]:
        """构建管理员配置导出/上传 payload
        
        导出的配置移除的敏感字段：
            - locked, locked_at, unlocked_at: 本地锁定状态
            - synced_at, sync_source: 同步状态信息
            - imported_at, import_source: 导入状态信息
        
        添加的导出元信息：
            - version: 当前配置版本（如2026.04.01）
            - exported_at: ISO格式的导出时间戳
        """
        config = self.get_admin_config()

        export_config = config.copy()
        export_config.pop('locked', None)
        export_config.pop('locked_at', None)
        export_config.pop('unlocked_at', None)
        export_config.pop('synced_at', None)
        export_config.pop('sync_source', None)
        export_config.pop('imported_at', None)
        export_config.pop('import_source', None)

        export_config['version'] = datetime.now().strftime("%Y.%m.%d")
        export_config['exported_at'] = datetime.now().isoformat()
        return export_config
    
    # =========================== 从本地进行admin_config.json的导入导出 ========================

    def export_admin_config(self, file_path=None):
        """导出管理员配置为本地JSON文件
        
        将当前的管理员配置导出为JSON文件，并移除敏感的本地状态信息。
        导出的配置可用于备份或传输给其他端点。
        
        Args:
            file_path (str): 目标导出文件路径
        Returns:
            None
        """
        export_config = self._build_export_admin_config_payload()
        self.json_storage.write_json(file_path, export_config)

    def import_admin_config(self, file_path):
        """从本地JSON文件导入管理员配置
        
        读取导出的配置文件并将其导入为当前的活动配置。支持备份当前配置。
        导入后会添加导入源信息用于审计追踪。
        
        Args:
            file_path (str): 源配置文件路径
        
        Returns:
            str: 包含备份路径（可选）的成功消息
        
        导入的配置移除的敏感字段：
            - exported_at: ISO格式的导出时间戳
        
        添加/确定的导入元信息：
            - imported_at: ISO格式的导入时间戳
            - import_source: 导入源文件路径
        """
        # 读文件
        imported_config = self.json_storage.read_json(file_path)
        if not isinstance(imported_config, dict):
            raise ValueError("配置文件格式不正确（应为 JSON 对象）。")
        
        # 验证格式
        if not self._validate_config(imported_config):
            raise ValueError("配置文件缺少必需的字段。")
        
        # 判断是否需要备份
        # 如果存在当前配置文件且启用备份，则先备份当前配置
        backup_path = None
        if self.config_manager.config_path.exists():
            backup_path = self.json_storage.backup_file(str(self.config_manager.config_path))

        # 设置值
        imported_config['configured'] = True
        imported_config['imported_at'] = datetime.now().isoformat()
        imported_config['import_source'] = file_path
        imported_config.pop('exported_at', None)

        # 存配置
        self.save_admin_config(imported_config)
        if backup_path:
            return f"原有配置已备份到 {backup_path}。"
        else:
            return ""
        
    # =========================== 从远程URL进行admin_config.json的相互传输 ========================

    def get_config_sync_settings(self, decrypt_sensitive: bool = True) -> Dict[str, Any]:
        """获取远程同步配置。"""
        config_sync = self.get_system_settings("config_sync")
        config = self.sync_manager.merge_with_defaults(config_sync)

        if decrypt_sensitive:
            return self.sync_manager.decrypt_sensitive_fields(config)
        return config

    def save_config_sync_settings(self, config: Dict[str, Any]) -> bool:
        """保存远程同步配置（敏感字段加密存储）。"""
        merged = self.sync_manager.merge_with_defaults(config)
        encrypted = self.sync_manager.encrypt_sensitive_fields(merged)
        self.save_system_settings("config_sync", encrypted)
        return True

    def test_config_sync_connection(self, provider: str = "") -> Tuple[bool, str]:
        """测试远程同步连接。"""
        config = self.get_config_sync_settings(decrypt_sensitive=False)
        active_provider = str(provider or config.get("provider", "github")).lower()
        return self.sync_manager.test_connection(active_provider, config)

    def push_admin_config_to_remote(self, provider: str = "") -> str:
        """将管理员配置发布到远程（GitHub/OSS）。"""
        remote_cfg_raw = self.get_config_sync_settings(decrypt_sensitive=False)
        active_provider = str(provider or remote_cfg_raw.get("provider", "github")).lower()
        payload = self._build_export_admin_config_payload()

        success, message, target = self.sync_manager.upload_admin_config(
            active_provider,
            payload,
            remote_cfg_raw,
        )

        current_remote_cfg = self.get_config_sync_settings(decrypt_sensitive=True)
        now = datetime.now().isoformat()
        current_remote_cfg["provider"] = active_provider
        current_remote_cfg["last_sync_time"] = now
        current_remote_cfg["last_sync_status"] = "success" if success else "failed"
        current_remote_cfg["last_sync_message"] = message
        current_remote_cfg["last_sync_target"] = target
        self.save_config_sync_settings(current_remote_cfg)

        if not success:
            raise ValueError(f"同步失败：{message}")
        return message

    def pull_admin_config_from_remote(self, sync_url: str, force: bool = False) -> Tuple[bool, str]:
        """检查并从远程URL同步管理员配置
        
        从指定的网络URL下载远程配置，与本地配置进行时间戳比较后决定是否更新。
        同步过程包括格式验证、时间戳比较、本地备份和配置保存。
        
        Args:
            sync_url (str): 配置文件的网络URL地址
            force (bool): 是否强制同步
                - False（默认）: 仅当远程配置更新时才同步
                - True: 忽略时间戳比较，强制同步
        
        Returns:
            str: 同步情况说明
                - "当前配置已备份到：{backup_path}"（如果成功且有备份）
                - ""（如果成功但无需备份）
                - "无需更新"（如果远程配置不比本地更新且未强制同步）
        
        同步流程：
            1. 获取远程配置
            2. 验证远程配置的格式
            3. 比较local_modified和remote_modified时间戳
            4. 备份当前配置
            5. 合并配置并保存
        
        异常处理：
            - 格式验证失败: 返回字段缺失的错误信息
            - 备份失败: 阻止同步，返回备份失败错误
            - 未知异常: 返回通用同步过程错误信息
        
        元信息变更：
            - 移除：导出字段（exported_at）
            - 添加：synced_at时间戳和sync_source URL用于审计
        """
        remote_config = self.sync_manager.download_admin_config(sync_url)

        if not self._validate_config(remote_config):
            raise ValueError("远程配置文件的内容格式不正确，缺少必需的字段")
            
        if not force:
            local_config = self.config_manager.load_config()
            local_modified = local_config.get('last_modified')
            remote_modified = remote_config.get('last_modified')
                
            if local_modified and remote_modified:
                if not self._is_remote_newer(remote_modified, local_modified):
                    return "无需更新"
            
        backup_path = None
        if self.config_manager.config_path.exists():
            backup_path = self.json_storage.backup_file(str(self.config_manager.config_path))
            
        local_config = self.config_manager.load_config()
        remote_config['synced_at'] = datetime.now().isoformat()
        remote_config['sync_source'] = sync_url
        remote_config.pop('exported_at', None)

        self.save_admin_config("remote", remote_config)
        if backup_path:
            return f"原有配置已备份到：{backup_path}"
        else:
            return ""

    def _is_remote_newer(self, remote_time: str, local_time: str) -> bool:
        """比较远程和本地配置的时间戳
        
        解析ISO格式的时间戳字符串并进行比较。
        若时间戳为空或解析失败，则默认认为需要更新。
        
        Args:
            remote_time (str): 远程配置的时间戳（ISO格式）
            local_time (str): 本地配置的时间戳（ISO格式）
        
        Returns:
            bool: 远程时间是否比本地更新
                - True: 远程更新或时间戳缺失或解析失败
                - False: 本地更新或相同
        """
        if not remote_time or not local_time:
            return True
        
        try:
            remote_dt = parser.parse(remote_time)
            local_dt = parser.parse(local_time)
            return remote_dt > local_dt
        except Exception:
            return True
    
    def _validate_config(self, config: dict) -> bool:
        """验证配置文件的格式
        
        检查配置字典是否包含所有必需的顶级字段。
        
        Args:
            config (dict): 待验证的配置字典
        
        Returns:
            bool: 配置格式是否有效
        
        必需字段：
            - version: 配置版本号
            - configured: 配置是否完成标志
            - basic_data: 基本数据
            - template_data: 模板数据
            - exported_at: 导出时间戳
        """
        # 远程config可以没有last_modified字段，表示管理员需要成员同步空的配置
        required_keys = ['version', 'configured', 'basic_data', 'template_data', 'exported_at']
        return all(key in config for key in required_keys)
    
    # =========================== 本地处理admin_config.json ========================

    def get_admin_config(self, *keys):
        """获取管理员配置
        
        加载并返回配置数据。支持多级嵌套键访问。
        
        Args:
            *keys: 可变数量的字符串键，用于逐级访问嵌套字典
                - 无键: 返回完整配置字典
                - 单个键: 返回该键的值
                - 多个键: 逐级访问嵌套键（如get_admin_config('basic_data', 'name')）
        
        Returns:
            dict或其他类型: 
                - 无参数返回: 完整的admin_config字典
                - 有参数返回: 指定键的值，或空字符串（若键不存在或路径中断）
        """
        admin_config = self.config_manager.load_config()
        if not keys:
            return admin_config
        current_val = admin_config
        for key in keys:
            if isinstance(current_val, dict):
                current_val = current_val.get(key)
                if current_val is None:
                    return ""
            else:
                return ""
        return current_val
    
    def save_admin_config(self, src, data, template_id=None):
        """保存或更新管理员配置
        
        根据源标识更新配置的不同部分。支持主页数据、模板数据和整体配置替换。
        
        Args:
            src (str): 数据源标识，决定如何处理数据：
                - 'home_page': 更新basic_data
                - 'template_page': 更新指定template_id的模板数据
                - 'remote': 直接替换整个配置（用于远程同步）
            data (dict): 待保存的数据
            template_id (str, 可选): 模板ID，仅在src='template_page'时使用
        
        Returns:
            tuple: (success: bool, message: str)
                - success: 保存是否成功
                - message: 始终为"配置已保存。"
        """
        admin_config = self.get_admin_config()

        if src not in ["home_page", "template_page", "remote"]:
            raise ValueError("无效的数据源标识。必须是 'home_page'、'template_page' 或 'remote'。")

        if src == "home_page":
            admin_config["basic_data"] = data
        elif src == "template_page":
            if "template_data" not in admin_config:
                admin_config["template_data"] = {}
            if template_id not in admin_config["template_data"]:
                admin_config["template_data"][template_id] = {}
            admin_config["template_data"][template_id] = data
        else:
            # 远程同步时直接覆盖整个配置（前提是已经验证过格式了）
            admin_config = data
        admin_config["configured"] = True

        self.config_manager.save_config(admin_config)

    def lock_admin_config(self):
        """锁定管理员配置"""
        self.config_manager.lock_config()

    def unlock_admin_config(self):
        """解锁管理员配置"""
        self.config_manager.unlock_config()

    # =========================== member_info.json ========================

    # =========================== 从别处进行member_info.json的相互传输 (成员端基本信息同步至飞书多维表格) ========================

    def get_info_sync_settings(self, decrypt_sensitive: bool = True) -> Dict[str, Any]:
        """获取成员飞书同步配置。"""
        info_sync = self.get_system_settings("info_sync")
        config = self.sync_manager.merge_info_sync_with_defaults(info_sync)

        if decrypt_sensitive:
            return self.sync_manager.decrypt_info_sync_sensitive_fields(config)
        return config

    def save_info_sync_settings(self, config: Dict[str, Any]) -> bool:
        """保存成员飞书同步配置（敏感字段加密存储）。"""
        merged = self.sync_manager.merge_info_sync_with_defaults(config)
        encrypted = self.sync_manager.encrypt_info_sync_sensitive_fields(merged)
        self.save_system_settings("info_sync", encrypted)
        return True

    def get_info_sync_provider_settings(self, provider: str = "", decrypt_sensitive: bool = True) -> Dict[str, Any]:
        """获取成员同步 provider 的配置块。"""
        info_cfg = self.get_info_sync_settings(decrypt_sensitive=decrypt_sensitive)
        active_provider = str(provider or info_cfg.get("provider", "feishu")).lower()
        provider_cfg = info_cfg.get(active_provider, {})
        if not isinstance(provider_cfg, dict):
            provider_cfg = {}
        return provider_cfg

    def save_info_sync_provider_settings(self, provider: str, provider_config: Dict[str, Any]) -> bool:
        """保存成员同步 provider 的配置块。"""
        info_cfg = self.get_info_sync_settings(decrypt_sensitive=True)
        active_provider = str(provider or info_cfg.get("provider", "feishu")).lower()
        info_cfg["provider"] = active_provider
        info_cfg[active_provider] = provider_config or {}
        self.save_info_sync_settings(info_cfg)
        return True

    def test_info_sync_connection(self, provider: str = "") -> Tuple[bool, str]:
        """测试成员同步连接。"""
        info_cfg = self.get_info_sync_settings(decrypt_sensitive=False)
        active_provider = str(provider or info_cfg.get("provider", "feishu")).lower()
        return self.sync_manager.test_info_sync_connection(active_provider, info_cfg)

    def push_member_basic_data_to_remote(self, provider: str = "") -> Tuple[bool, str]:
        """将成员基础信息发布到远程目标。"""
        member_info = self.get_member_info()
        basic_data = (member_info or {}).get("basic_data", {})
        if not isinstance(basic_data, dict) or not basic_data:
            raise ValueError("成员基本信息为空，请先填写并保存后再同步。")

        info_cfg_raw = self.get_info_sync_settings(decrypt_sensitive=False)
        active_provider = str(provider or info_cfg_raw.get("provider", "feishu")).lower()
        success, message, target, merged_basic_data = self.sync_manager.upload_member_basic_data(
            active_provider,
            basic_data,
            info_cfg_raw,
        )

        if success and "已回填" in message and isinstance(merged_basic_data, dict):
            self.save_member_info("home_page", merged_basic_data)

        current_cfg = self.get_info_sync_settings(decrypt_sensitive=True)
        provider_cfg = current_cfg.get(active_provider, {})
        if not isinstance(provider_cfg, dict):
            provider_cfg = {}

        now = datetime.now().isoformat()
        current_cfg["provider"] = active_provider
        current_cfg["last_sync_time"] = now
        current_cfg["last_sync_status"] = "success" if success else "failed"
        current_cfg["last_sync_message"] = message
        current_cfg["last_sync_target"] = target
        current_cfg[active_provider] = provider_cfg
        self.save_info_sync_settings(current_cfg)

        if not success:
            raise ValueError(message)
        return True, message

    # =========================== 从本地进行member_info.json的操作 ========================
    
    def get_member_info(self, *keys):
        """获取成员数据
        
        加载并返回成员数据。支持多级嵌套键访问，用法同get_admin_config。
        
        Args:
            *keys: 可变数量的字符串键，用于逐级访问嵌套字典
                - 无键: 返回完整成员数据字典
                - 有键: 逐级访问嵌套键
        
        Returns:
            dict或其他类型: 完整的member_info或指定键的值
        """
        member_info = self.info_manager.load_data()
        if not keys:
            return member_info
        current_val = member_info
        for key in keys:
            if isinstance(current_val, dict):
                current_val = current_val.get(key)
                if current_val is None:
                    return ""
            else:
                return ""
        return current_val

    def save_member_info(self, src, data, template_id=None):
        """保存或更新成员数据
        
        根据源标识更新成员数据的不同部分。保存模板数据时自动更新版本戳。
        
        Args:
            src (str): 数据源标识
                - 'home_page': 更新basic_data部分
                - 'template_page': 更新指定template_id的数据
            data (dict): 待保存的数据
            template_id (str, 可选): 模板ID，仅在src='template_page'时使用
        
        Returns:
            bool: 保存是否成功
        
        行为说明：
            - 存储template_data[template_id]时，自动设置version为当前年月，用于成员端判断显示的数据版本
        """
        member_info = self.get_member_info()

        if src == "home_page":
            member_info["basic_data"] = data
        elif src == "template_page":
            if "template_data" not in member_info:   # 这里一般来说是肯定有template_data键的
                member_info["template_data"] = {}
            if template_id not in member_info["template_data"]:
                member_info["template_data"][template_id] = {}
            data["version"] = datetime.now().strftime("%Y.%m.%d")   # 每次保存模板数据时都更新version为当前时间，如此则成员的模板页的专有项就可以通过version来判断显示哪里的数据了
            member_info["template_data"][template_id] = data

        self.info_manager.save_data(member_info)
    
    def lock_member_template(self, template_id, basic_entry, template_entry):
        """锁定成员的特定模板数据
        
        防止修改已生成的模板材料，通常用于当前模板数据的永久保存。
        
        Args:
            template_id (str): 模板的ID
            basic_entry (str): 当前模板的基本项
            template_entry (str): 当前模板的专有项
        """
        self.info_manager.lock_template_data(template_id, basic_entry, template_entry)

    def save_member_archive_image(
        self,
        source_file_path: str,
        template_id: str,
        overwrite: bool = False,
        auto_rename: bool = False,
    ) -> dict:
        """保存成员档案图片并写入元数据

        Args:
            source_file_path (str): 源图片路径。
            template_id (str): 模板ID。
            overwrite (bool): 目标存在时是否覆盖。
            auto_rename (bool): 目标存在时是否自动重命名。

        Returns:
            dict: 保存后的图片元数据。

        Raises:
            FileNotFoundError: 源文件不存在。
            FileExistsError: 目标已存在且未允许覆盖/重命名。
            ValueError: 参数或文件格式不合法。
            IOError: 文件保存失败。
        """
        image_meta = self.image_manager.save_image(
            source_file_path=source_file_path,
            template_id=template_id,
            overwrite=overwrite,
            auto_rename=auto_rename,
        )

        member_info = self.info_manager.load_data()
        if "template_data" not in member_info:
            member_info["template_data"] = {}

        if template_id not in member_info["template_data"]:
            member_info["template_data"][template_id] = {}

        template_data = member_info["template_data"][template_id]
        archive_images = template_data.get("archive_images", [])

        # 覆盖同一路径时更新已有记录，避免重复条目
        replaced = False
        for idx, item in enumerate(archive_images):
            if item.get("relative_path") == image_meta["relative_path"]:
                archive_images[idx] = image_meta
                replaced = True
                break

        if not replaced:
            archive_images.append(image_meta)

        template_data["archive_images"] = archive_images
        self.info_manager.save_data(member_info)

        return image_meta

    def get_member_archive_images(self, template_id: str) -> list[dict]:
        """获取成员模板下已保存的档案图片列表

        Args:
            template_id (str): 模板ID。

        Returns:
            list[dict]: 图片元数据列表。
        """
        member_info = self.info_manager.load_data()
        template_data = member_info.get("template_data", {}).get(template_id, {})
        archive_images = template_data.get("archive_images", [])
        if not isinstance(archive_images, list):
            return []
        return archive_images

    def remove_member_archive_image(
        self,
        template_id: str,
        relative_path: str,
        delete_file: bool = True,
    ) -> bool:
        """删除成员模板下的档案图片记录（并可选删除本地文件）

        Args:
            template_id (str): 模板ID。
            relative_path (str): 图片相对路径。
            delete_file (bool): 是否同时删除本地文件。

        Returns:
            bool: 删除是否成功。

        Raises:
            ValueError: 未找到对应图片记录。
            IOError: 文件删除失败。
        """
        member_info = self.info_manager.load_data()
        template_data_all = member_info.get("template_data", {})
        template_data = template_data_all.get(template_id, {})
        archive_images = template_data.get("archive_images", [])

        if not isinstance(archive_images, list):
            archive_images = []

        target_index = None
        for idx, item in enumerate(archive_images):
            if item.get("relative_path") == relative_path:
                target_index = idx
                break

        if target_index is None:
            raise ValueError("未找到指定的档案图片记录")

        if delete_file:
            self.image_manager.delete_image(relative_path)

        archive_images.pop(target_index)
        template_data["archive_images"] = archive_images

        if "template_data" not in member_info:
            member_info["template_data"] = {}
        if template_id not in member_info["template_data"]:
            member_info["template_data"][template_id] = {}

        member_info["template_data"][template_id].update(template_data)
        self.info_manager.save_data(member_info)
        return True
    
    def export_member_info(self, file_path):
        """导出成员数据到本地JSON文件
        
        将当前的成员数据导出为JSON文件，包含导出时间戳用于审计。
        
        Args:
            file_path (str): 目标导出文件路径
        
        Returns:
            tuple: (success: bool, message: str)
                - success: 始终为True
                - message: 包含导出文件路径的成功消息
        
        添加的导出元信息：
            - exported_at: ISO格式的导出时间戳
        """
        member_info = self.get_member_info()
        export_data = member_info.copy()
        export_data['exported_at'] = datetime.now().isoformat()
        self.json_storage.write_json(file_path, export_data)
    
    def import_member_info(self, file_path):
        """从JSON文件导入成员数据
        
        读取导出的成员数据文件并将其导入为当前活动的成员数据。
        会移除导出时间戳，添加导入源信息用于审计。
        
        Args:
            file_path (str): 源数据文件路径
        
        Returns:
            tuple: (success: bool, message: str)
                - success: 导入是否成功
                - message: 包含源文件路径的成功消息或错误描述

        导入的数据移除的字段：
            - exported_at: ISO格式的导出时间戳
        
        添加的导入元信息：
            - imported_at: ISO格式的导入时间戳
            - import_source: 导入源文件路径
        """
        imported_data = self.json_storage.read_json(file_path)

        if not isinstance(imported_data, dict):
            raise ValueError("成员数据文件格式不正确（应为 JSON 对象）。")

        if not self._validate_info(imported_data):
            raise ValueError("成员数据文件缺少必需的字段。")
        
        imported_data.pop('exported_at', None)
        imported_data['imported_at'] = datetime.now().isoformat()
        imported_data['import_source'] = file_path

        self.save_member_info(imported_data)
    
    def _validate_info(self, info: dict) -> bool:
        """验证成员数据的格式
        
        检查成员数据字典是否包含所有必需的顶级字段。
        
        Args:
            info (dict): 待验证的成员数据字典
        
        Returns:
            bool: 成员数据格式是否有效
        
        必需字段：
            - created_at: 数据创建时间戳
            - basic_data: 基本数据
            - template_data: 模板数据
            - exported_at: 导出时间戳
        """
        required_keys = ['created_at', 'basic_data', 'template_data', 'exported_at']
        return all(key in info for key in required_keys)
    
    # =========================== about password for admin and member ========================

    def has_password(self, src) -> bool:
        """检查是否设置了密码
        
        Args:
            src (str): 源标识，支持'admin'或'member'
        
        Returns:
            bool: 是否已设置密码
        """
        if src == "admin":
            return self.config_manager.has_password()
        elif src == "member":
            return self.info_manager.has_password()
        return False
    
    def verify_password(self, src, password) -> bool:
        """验证历史密码
        
        检查提供的密码是否与存储的密码匹配。
        
        Args:
            src (str): 源标识，支持'admin'或'member'
            password (str): 待验证的密码
        
        Returns:
            bool: 密码是否正确
        """
        if src == "admin":
            return self.config_manager.verify_password(password)
        elif src == "member":
            return self.info_manager.verify_password(password)
        return False
    
    def set_password(self, src, password) -> bool:
        """设置新密码
        
        为指定的端点（admin或member）设置或更新密码。
        
        Args:
            src (str): 源标识，支持'admin'或'member'
            password (str): 新密码
        
        Returns:
            bool: 设置是否成功
        """
        if src == "admin":
            return self.config_manager.set_password(password)
        elif src == "member":
            return self.info_manager.set_password(password)
        return False
    
    def enable_encryption(self, src, password) -> bool:
        """启用密码加密保护
        
        为指定端点启用基于密码的加密保护。
        
        Args:
            src (str): 源标识，支持'admin'或'member'
            password (str): 用于加密的密码
        
        Returns:
            bool: 启用是否成功
        """
        if src == "admin":
            return self.config_manager.enable_encryption(password)
        elif src == "member":
            return self.info_manager.enable_encryption(password)
        return False
    
    def change_password(self, src, old_password, new_password) -> bool:
        """修改现有密码
        
        使用旧密码验证后，用新密码替换。
        
        Args:
            src (str): 源标识，支持'admin'或'member'
            old_password (str): 当前密码
            new_password (str): 新密码
        
        Returns:
            bool: 修改是否成功
        """
        if src == "admin":
            return self.config_manager.change_password(old_password, new_password)
        elif src == "member":
            return self.info_manager.change_password(old_password, new_password)
        return False
    
    def disable_encryption(self, src, password) -> bool:
        """禁用密码保护
        
        关闭指定端点的加密保护。需要提供正确的密码进行验证。
        
        Args:
            src (str): 源标识，支持'admin'或'member'
            password (str): 验证用的密码
        
        Returns:
            bool: 禁用是否成功
        """
        if src == "admin":
            return self.config_manager.disable_encryption(password)
        elif src == "member":
            return self.info_manager.disable_encryption(password)
        return False
    
    # =========================== system_settings.json ========================
    
    def get_system_settings(self, *keys):
        """获取系统设置
        
        加载并返回系统级设置。支持多级嵌套键访问，用法同get_admin_config。
        
        Args:
            *keys: 可变数量的字符串键，用于逐级访问嵌套字典
        
        Returns:
            dict或其他类型: 完整的系统设置或指定键的值
        """
        settings = self.settings_manager.load_settings()
        if not keys:
            return settings
        current_val = settings
        for key in keys:
            if isinstance(current_val, dict):
                current_val = current_val.get(key)
                if current_val is None:
                    return ""
            else:
                return ""
        return current_val
    
    def save_system_settings(self, key, value):
        """保存或修改系统设置
        
        更新系统级设置中的单个键值对。
        
        Args:
            key (str): 设置的键名
            value: 设置的值
        
        Returns:
            bool: 保存是否成功
        """
        if key == USER_DATA_ROOT_KEY:
            self.update_user_data_root(str(value))
            return True

        settings = self.get_system_settings()
        settings[key] = value
        self.settings_manager.save_settings(settings)
        return True
    




    