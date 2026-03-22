#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据管理模块
"""

from datetime import datetime
from typing import Optional, Tuple
import json
import requests

from src.data.config_manager import ConfigManager
from src.data.info_manager import InfoManager
from src.data.template_manager import TemplateManager
from src.data.field_manager import FieldManager
from src.data.settings_manager import SettingsManager
from src.utils.json_storage import JSONStorage


class DataManager:
    """数据管理类"""
    
    def __init__(self):
        self.field_manager = FieldManager()
        self.config_manager = ConfigManager()
        self.info_manager = InfoManager()
        self.template_manager = TemplateManager()
        self.settings_manager = SettingsManager()
        self.json_storage = JSONStorage()
        self.timeout = 10

    # =========================== fields_definition.json ========================
    def get_fields(self, src):
        """获取字段定义"""
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
            # 删去admin_fields_groups中的系统设置字段
            admin_fields_groups = [
                group_def for group_def in admin_fields_groups
                if group_def.get("group", "") != "系统设置"
                ]
            return admin_fields_groups, member_fields
        elif src == 'template':
            # template页面不需要分组呈现admin相关字段，所以直接把admin_fields_groups中的字段平铺成一个列表返回
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

    def export_admin_config(self, file_path):
        """导出配置为 JSON 文件"""
        try:
            config = self.get_admin_config()

            # 创建导出配置（移除敏感信息和本地状态）
            export_config = config.copy()
            # 保留配置数据，但移除锁定状态等本地设置
            export_config.pop('locked', None)
            export_config.pop('locked_at', None)
            export_config.pop('unlocked_at', None)
            export_config.pop('synced_at', None)
            export_config.pop('sync_source', None)
            export_config.pop('imported_at', None)
            export_config.pop('import_source', None)

            # 添加导出元信息
            export_config['exported_at'] = datetime.now().isoformat()
            export_config['export_version'] = export_config.get('version', '1.0')

            # 写入文件
            self.json_storage.write_json(file_path, export_config)
            return True, f"配置已导出到：\n{file_path}"
        except Exception as e:
            return False, f"导出失败：{e}"
    
    def import_admin_config(self, file_path, mode='member'):
        """从本地 JSON 文件导入管理员配置"""

        # 读文件
        try:
            imported_config = self.json_storage.read_json(file_path)
            if not isinstance(imported_config, dict):
                raise ValueError("配置文件格式不正确（根应为 JSON 对象）。")
        except Exception as e:
            return False, f"配置加载失败：{e}"
        
        # 验证格式
        if not self._validate_config(imported_config):
            return False, "配置文件缺少必需的字段（支部信息、上级党委信息、公共字段、系统设置）。"
        
        # 判断是否需要备份
        # 如果存在当前配置文件且启用备份，则先备份当前配置
        backup_path = None
        if self.config_manager.config_path.exists():
            try:
                backup_path = self.json_storage.backup_file(str(self.config_manager.config_path))
            except Exception as e:
                return False, f"备份当前配置失败：{e}"

        # 设置值
        imported_config['locked'] = True if mode == 'member' else False
        imported_config['configured'] = True
        imported_config['imported_at'] = datetime.now().isoformat()
        imported_config['import_source'] = file_path
        imported_config.pop('exported_at', None)
        imported_config.pop('export_version', None)

        # 存配置
        is_success, message = self.save_admin_config(imported_config)
        if backup_path:
            message += f"（已备份当前配置到: {backup_path}）"
        return is_success, message
    
    def sync_admin_config(self, sync_url: str, force: bool = False) -> Tuple[bool, str]:
        """
        检查并同步配置
        
        Args:
            sync_url: 配置文件的网络 URL
            force: 是否强制同步（忽略时间戳比较）
        
        Returns:
            (success: bool, message: str)
            success=True 表示同步成功，False 表示无更新或失败
        """
        try:
            # 1. 获取远程配置的元信息
            try:
                head_response = requests.head(sync_url, timeout=5, allow_redirects=True)
                head_response.raise_for_status()
            except requests.RequestException:
                # HEAD 请求失败，尝试 GET 请求
                pass
            
            # 2. 下载远程配置
            try:
                response = requests.get(sync_url, timeout=self.timeout, allow_redirects=True)
                response.raise_for_status()
                remote_config = response.json()
            except requests.RequestException as e:
                return False, f"无法访问配置 URL：{e}"
            except json.JSONDecodeError:
                return False, "远程配置文件格式错误（不是有效的 JSON）"
            
            # 3. 验证配置格式
            if not self._validate_config(remote_config):
                return False, "远程配置文件格式不正确，缺少必需的字段"
            
            # 4. 比较时间戳（如果不强制同步）
            if not force:
                local_config = self.config_manager.load_config()
                local_modified = local_config.get('last_modified')
                remote_modified = remote_config.get('last_modified')
                
                if local_modified and remote_modified:
                    if not self._is_remote_newer(remote_modified, local_modified):
                        return False, "本地配置已是最新版本，无需更新"
            
            # 5. 备份当前配置
            backup_path = None
            if self.config_manager.config_path.exists():
                try:
                    backup_path = self.json_storage.backup_file(str(self.config_manager.config_path))
                except Exception as e:
                    return False, f"备份当前配置失败：{e}"
            
            # 6. 合并配置（保留本地设置）
            local_config = self.config_manager.load_config()
            remote_config['locked'] = local_config.get('locked', True)  # 成员端默认锁定
            remote_config['configured'] = True
            remote_config['synced_at'] = datetime.now().isoformat()
            remote_config['sync_source'] = sync_url
            # 管理员将本地导出的json上传至云端url，同步时remote_config中的exported_at和export_version字段应该删除
            remote_config.pop('exported_at', None)
            remote_config.pop('export_version', None)
            
            # 7. 保存配置
            is_success, message = self.save_admin_config("remote", remote_config)
            if backup_path:
                message += f"同步成功（已备份当前配置到: {backup_path}）"
            return is_success, message
        except Exception as e:
            return False, f"同步过程出错：{e}"
        
    def _is_remote_newer(self, remote_time: str, local_time: str) -> bool:
        """比较远程和本地配置的时间戳"""

        # 如果远程或本地时间戳为空，则认为需要更新
        if not remote_time or not local_time:
            return True
        
        try:
            from dateutil import parser
            remote_dt = parser.parse(remote_time)
            local_dt = parser.parse(local_time)
            return remote_dt > local_dt
        except Exception:
            # 解析失败时默认认为需要更新
            return True
    
    def _validate_config(self, config: dict) -> bool:
        """验证配置格式"""
        required_keys = ['version', 'configured', 'basic_data', 'template_data']
        return all(key in config for key in required_keys)
    
    # =========================== 本地处理admin_config.json ========================

    def get_admin_config(self, *keys):
        """获取管理员配置"""
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
        """保存管理员配置"""
        admin_config = self.get_admin_config()

        if src == "home_page":
            admin_config["basic_data"] = data
            admin_config["configured"] = True     # 只要保存了home_page的数据，就认为配置完成了？？？？？？？？？应该是这样吗
        elif src == "template_page":
            if "template_data" not in admin_config:
                admin_config["template_data"] = {}
            if template_id not in admin_config["template_data"]:
                admin_config["template_data"][template_id] = {}
            admin_config["template_data"][template_id] = data
        elif src == "remote":
            # 远程同步时直接覆盖整个配置（前提是已经验证过格式了）
            admin_config = data

        return self.config_manager.save_config(admin_config), "配置已保存。"

    def lock_admin_config(self):
        self.config_manager.lock_config()

    def unlock_admin_config(self):
        self.config_manager.unlock_config()

    # =========================== member_info.json ========================
    
    def get_member_info(self, *keys):
        """获取成员数据"""
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
        """保存成员数据"""
        member_info = self.get_member_info()

        if src == "home_page":
            member_info["basic_data"] = data     # ？？？？？？？？？？？？？此处需要用类似于template_data的update吗
        elif src == "template_page":
            if "template_data" not in member_info:   # 这里一般来说是肯定有template_data键的
                member_info["template_data"] = {}
            if template_id not in member_info["template_data"]:
                member_info["template_data"][template_id] = {}
            member_info["template_data"][template_id].update(data)

        return self.info_manager.save_data(member_info)
    
    def export_member_info(self, file_path):
        """导出成员数据为 JSON 文件"""
        try:
            member_info = self.get_member_info()

            # 添加导出元信息
            export_data = member_info.copy()
            export_data['exported_at'] = datetime.now().isoformat()
            self.json_storage.write_json(file_path, export_data)
            return True, f"成员数据已导出到：\n{file_path}"
        except Exception as e:
            return False, f"导出失败：{e}"
    
    def import_member_info(self, file_path):
        """从 JSON 文件导入成员数据"""
        try:
            imported_data = self.json_storage.read_json(file_path)

            if not isinstance(imported_data, dict):
                raise ValueError("成员数据文件格式不正确（根应为 JSON 对象）。")
            
            imported_data.pop('exported_at', None)  # 移除导出元信息
            imported_data['imported_at'] = datetime.now().isoformat()
            imported_data['import_source'] = file_path

            self.save_member_info(imported_data)

            return True, f"成员数据已从以下文件导入：\n{file_path}"
        except Exception as e:
            return False, f"导入失败：{e}"
    
    # =========================== system_settings.json ========================
    
    def get_system_settings(self, *keys):
        """获取系统设置"""
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
    
    def save_system_settings(self, settings):
        """保存系统设置"""
        return self.settings_manager.save_settings(settings)
