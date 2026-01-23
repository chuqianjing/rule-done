#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据验证器
"""

import re
from datetime import datetime


class Validators:
    """数据验证器类"""
    
    @staticmethod
    def validate_field(field_def, value):
        """验证单个字段"""
        if field_def.get('required', False) and not value:
            return False, f"{field_def.get('display', {}).get('label', '字段')}不能为空"
        
        field_type = field_def.get('type')
        
        if field_type == 'text':
            return Validators.validate_text(value, field_def.get('validation', {}))
        elif field_type == 'date':
            return Validators.validate_date(value, field_def.get('format', ''))
        elif field_type == 'select':
            return Validators.validate_select(value, field_def.get('options', []))
        
        return True, None
    
    @staticmethod
    def validate_text(value, validation_config=None):
        """文本验证"""
        if validation_config is None:
            validation_config = {}
        
        if not value:
            return True, None  # 空值由 required 检查
        
        min_length = validation_config.get('min_length')
        max_length = validation_config.get('max_length')
        pattern = validation_config.get('pattern')
        
        if min_length and len(value) < min_length:
            return False, f"长度不能少于 {min_length} 个字符"
        
        if max_length and len(value) > max_length:
            return False, f"长度不能超过 {max_length} 个字符"
        
        if pattern:
            if not re.match(pattern, value):
                return False, "格式不正确"
        
        return True, None
    
    @staticmethod
    def validate_date(value, format_str="YYYY年MM月DD日", min_date=None, max_date=None):
        """日期验证"""
        if not value:
            return True, None
        
        # TODO: 实现日期格式验证
        return True, None
    
    @staticmethod
    def validate_select(value, options):
        """选择项验证"""
        if not value:
            return True, None
        
        if value not in options:
            return False, f"值必须在 {options} 中"
        
        return True, None
    
    @staticmethod
    def validate_id_card(value):
        """身份证号验证"""
        if not value:
            return True, None
        
        pattern = r'^[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]$'
        if not re.match(pattern, value):
            return False, "身份证号格式不正确"
        
        return True, None
    
    @staticmethod
    def validate_phone(value):
        """手机号验证"""
        if not value:
            return True, None
        
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, value):
            return False, "手机号格式不正确"
        
        return True, None
    
    @staticmethod
    def validate_logical_relations(data):
        """逻辑关系验证"""
        errors = []
        
        # 示例：转正时间不能早于入党时间
        basic_info = data.get('basic_info', {})
        template_data = data.get('template_data', {})
        
        # TODO: 实现具体的逻辑验证
        
        return errors

