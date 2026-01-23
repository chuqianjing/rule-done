#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据管理模块
"""

from src.data.config_manager import ConfigManager
from src.data.student_manager import StudentManager
from src.data.template_manager import TemplateManager


class DataManager:
    """数据管理类"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.student_manager = StudentManager()
        self.template_manager = TemplateManager()
    
    def get_admin_config(self):
        """获取管理员配置"""
        return self.config_manager.load_config()
    
    def get_student_data(self):
        """获取学生数据"""
        return self.student_manager.load_data()
    
    def save_student_data(self, data):
        """保存学生数据"""
        return self.student_manager.save_data(data)
    
    def merge_data_for_template(self, template_id):
        """合并数据用于模板生成"""
        # TODO: 实现数据合并逻辑
        merged_data = {}
        
        # 1. 加载管理员配置
        admin_config = self.get_admin_config()
        
        # 2. 加载学生数据
        student_data = self.get_student_data()
        
        # 3. 获取模板配置
        template_config = self.template_manager.get_template(template_id)
        field_mapping = template_config.get('field_mapping', {})
        
        # 4. 根据映射合并数据
        for placeholder, mapping in field_mapping.items():
            key = placeholder.strip('{}')
            value = self._get_value_by_mapping(mapping, admin_config, student_data)
            merged_data[key] = value
        
        return merged_data
    
    def _get_value_by_mapping(self, mapping, admin_config, student_data):
        """根据映射获取值"""
        source = mapping.get('source')
        
        if source == 'basic_info':
            field = mapping.get('field')
            return student_data.get('basic_info', {}).get(field, '')
        
        elif source == 'admin_config':
            path = mapping.get('path', '').split('.')
            value = admin_config
            for key in path:
                if isinstance(value, dict):
                    value = value.get(key, {})
                else:
                    return ''
            return value if isinstance(value, str) else ''
        
        elif source == 'template_data':
            template_id = mapping.get('template_id')
            field = mapping.get('field')
            return student_data.get('template_data', {}).get(template_id, {}).get(field, '')
        
        return ''
    
    def validate_data(self, data_type, data):
        """数据验证"""
        # TODO: 实现数据验证逻辑
        return {'valid': True, 'errors': []}

