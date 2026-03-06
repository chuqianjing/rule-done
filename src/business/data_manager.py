#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据管理模块
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import json
import requests

from src.data.config_manager import ConfigManager
from src.data.student_manager import StudentManager
from src.data.template_manager import TemplateManager
from src.data.field_manager import FieldManager
from src.utils.json_storage import JSONStorage
from src.utils.data_paths import get_admin_value


class DataManager:
    """数据管理类"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.student_manager = StudentManager()
        self.template_manager = TemplateManager()
        self.field_manager = FieldManager()
        self.json_storage = JSONStorage()
        self.timeout = 10

    # =========================== fields_definition.json ========================

    def get_fields(self, mode='admin'):
        """获取字段定义"""
        fields_definition = self.field_manager.load_fields_definition()
        admin_fields_groups = sorted(
                fields_definition.get("admin_fields", []),
                key=lambda x: x.get("group_order", 0),
                )
        if mode == 'admin':
            return admin_fields_groups, None
        elif mode == 'student':
            basic_fields = sorted(
                fields_definition.get("basic_info_fields", []),
                key=lambda x: x.get("display", {}).get("order", 0),
                )
            # 删去admin_fields_groups中的系统设置字段
            admin_fields_groups = [
                group_def for group_def in admin_fields_groups 
                if group_def.get("group", "") != "系统设置"
                ]
            return admin_fields_groups, basic_fields
    
    
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
    
    def import_admin_config(self, file_path, mode='student'):
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
        imported_config['locked'] = True if mode == 'student' else False
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
            remote_config['locked'] = local_config.get('locked', True)  # 学生端默认锁定
            remote_config['configured'] = True
            remote_config['synced_at'] = datetime.now().isoformat()
            remote_config['sync_source'] = sync_url
            # 管理员将本地导出的json上传至云端url，同步时remote_config中的exported_at和export_version字段应该删除
            remote_config.pop('exported_at', None)
            remote_config.pop('export_version', None)
            
            # 7. 保存配置
            is_success, message = self.save_admin_config(remote_config)
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
        required_keys = ['支部信息', '上级党委信息', '公共字段', '系统设置']
        return all(key in config for key in required_keys)
    
    # =========================== 本地处理admin_config.json ========================

    def get_admin_config(self, field_name=None):
        """获取管理员配置"""
        admin_config = self.config_manager.load_config()
        if field_name is None:
            return admin_config
        else:
            if field_name == "config_sync_url":
                return admin_config.get("system_settings", {}).get("config_sync_url", "")
            else:
                raise ValueError(f"未知的字段名称：{field_name}")

    def save_admin_config(self, config):
        """保存管理员配置"""
        try:
            self.config_manager.save_config(config)
        except Exception as e:
            return False, f"保存配置失败：{e}"
        return True, "配置保存成功"
    
    def lock_admin_config(self):
        self.config_manager.lock_config()

    def unlock_admin_config(self):
        self.config_manager.unlock_config()

    # =========================== student_data.json ========================
    
    def get_student_data(self):
        """获取学生数据"""
        return self.student_manager.load_data()
    
    def save_student_data(self, data):
        """保存学生数据"""
        return self.student_manager.save_data(data)
    
    # =========================== templates ========================

    def get_templates(self, template_id=None):
        return self.template_manager.load_templates(template_id)
    
    # =========================== 数据合并 ========================

    def merge_data_for_template(self, template_id):
        """合并数据用于模板生成（方案C：混合模式）"""
        merged_data = {}
        
        # 1. 加载管理员配置
        admin_config = self.get_admin_config()
        
        # 2. 加载学生数据
        student_data = self.get_student_data()
        
        # 3. 获取字段映射（优先使用 JSON 配置，否则使用自动映射）
        template_config = self.template_manager.get_template(template_id)
        field_mapping = template_config.get('field_mapping', {})
        
        # 如果 JSON 中没有映射配置，使用自动映射
        if not field_mapping:
            from src.business.template_engine import TemplateEngine
            template_engine = TemplateEngine()
            field_mapping = template_engine.auto_map_placeholders(template_id)
        
        # 4. 根据映射合并数据
        #    已配置映射的占位符优先按照映射规则取值
        for placeholder, mapping in field_mapping.items():
            key = placeholder.strip('{}')
            value = self._get_value_by_mapping(mapping, admin_config, student_data)
            merged_data[key] = value

        # 5. 获取管理员配置的模板字段
        admin_template_fields = admin_config.get("template_fields", {}).get(template_id, {})
        
        # 6. 注入模板数据中所有未映射的字段（应用方案C混合模式）
        tpl_data = student_data.get('template_data', {}).get(template_id, {})
        for k, v in tpl_data.items():
            if k not in merged_data and k != 'last_modified':
                # 检查管理员是否配置并锁定了该字段
                admin_field_config = admin_template_fields.get(k, {})
                if isinstance(admin_field_config, dict):
                    is_locked = admin_field_config.get("locked", False)
                    admin_value = admin_field_config.get("value", "")
                else:
                    # 兼容旧格式（直接存储值）
                    is_locked = False
                    admin_value = admin_field_config if admin_field_config else ""
                
                if is_locked and admin_value:
                    # 字段被锁定，使用管理员配置的值
                    merged_data[k] = admin_value
                else:
                    # 字段未锁定，优先使用学生数据
                    merged_data[k] = v if v else admin_value
        
        # 7. 补充管理员配置但学生未填写的字段
        for k, admin_field_config in admin_template_fields.items():
            if k not in merged_data:
                if isinstance(admin_field_config, dict):
                    merged_data[k] = admin_field_config.get("value", "")
                else:
                    merged_data[k] = admin_field_config if admin_field_config else ""
        
        return merged_data
    
    def _get_value_by_mapping(self, mapping, admin_config, student_data):
        """根据映射获取值"""
        source = mapping.get('source')
        
        if source == 'basic_info':
            field = mapping.get('field')
            return student_data.get('basic_info', {}).get(field, '')
        
        elif source == 'admin_config':
            # 使用 group + key 从管理员配置中获取值
            group = mapping.get('group', '')
            key = mapping.get('key', '')
            return get_admin_value(admin_config, group, key, '')
        
        elif source == 'template_data':
            template_id = mapping.get('template_id')
            field = mapping.get('field')
            return student_data.get('template_data', {}).get(template_id, {}).get(field, '')
        
        return ''
    
    def validate_data(self, data_type, data):
        """数据验证"""
        # TODO: 实现数据验证逻辑
        return {'valid': True, 'errors': []}

    # ========================= 模板字段配置方法 =========================
    
    def get_admin_template_fields(self, template_id: str = None) -> dict:
        """获取管理员配置的模板字段"""
        return self.config_manager.get_template_fields(template_id)
    
    def save_admin_template_fields(self, template_id: str, fields: dict):
        """保存管理员配置的模板字段"""
        self.config_manager.save_template_fields(template_id, fields)
    
    def get_field_config(self, template_id: str, field_name: str) -> dict:
        """获取单个字段的配置"""
        return self.config_manager.get_field_config(template_id, field_name)
    
    def is_field_locked(self, template_id: str, field_name: str) -> bool:
        """检查字段是否被管理员锁定"""
        return self.config_manager.is_field_locked(template_id, field_name)
    
    def get_merged_field_value(self, template_id: str, field_name: str) -> tuple:
        """
        获取合并后的字段值及其来源（方案C混合模式）
        
        Returns:
            (value, source, is_locked): 值、来源（'student'/'admin'/''）、是否锁定
        """
        admin_config = self.get_admin_config()
        student_data = self.get_student_data()
        
        # 管理员配置的字段
        admin_field_config = admin_config.get("template_fields", {}).get(template_id, {}).get(field_name, {})
        if isinstance(admin_field_config, dict):
            admin_value = admin_field_config.get("value", "")
            is_locked = admin_field_config.get("locked", False)
        else:
            admin_value = admin_field_config if admin_field_config else ""
            is_locked = False
        
        # 学生数据
        student_value = student_data.get("template_data", {}).get(template_id, {}).get(field_name, "")
        
        # 根据方案C确定最终值
        if is_locked and admin_value:
            return admin_value, "admin", True
        elif student_value:
            return student_value, "student", False
        elif admin_value:
            return admin_value, "admin", False
        else:
            return "", "", False
