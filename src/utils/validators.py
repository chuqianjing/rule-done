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
            return False, f"{field_def.get('key', '字段')}不能为空"
        
        field_type = field_def.get('type')
        
        if field_type == 'text':
            return Validators.validate_text(value, field_def.get('validation', {}))
        elif field_type == 'date':
            return Validators.validate_date(value, field_def.get('format', ''))
        elif field_type == 'select':
            return Validators.validate_select(value, field_def.get('options', []))
        
        return True, None
    
    @staticmethod
    def validate_text(value, validation=None):
        """文本验证"""
        if validation is None:
            validation = {}
        if not value:
            return True, None  # 空值由 required 检查
        
        min_length = validation.get('min_length')
        max_length = validation.get('max_length')
        pattern = validation.get('pattern')
        
        if min_length and len(value) < min_length:
            return False, f"长度不能少于 {min_length} 个字符"
        if max_length and len(value) > max_length:
            return False, f"长度不能多于 {max_length} 个字符"
        if pattern:
            if not re.match(pattern, value):
                return False, "格式不正确"
        
        return True, None
    
    @staticmethod
    def validate_date(value, format="YYYY年MM月DD日", min_date=None, max_date=None):
        """日期验证"""
        if not value:
            return True, None

        # 将逻辑格式转换为 strptime 格式
        fmt = "%Y-%m-%d"
        if format == "YYYY年MM月DD日":
            fmt = "%Y年%m月%d日"
        elif format == "YYYY年MM月":
            fmt = "%Y年%m月"

        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            return False, f"日期格式应为：{format}"

        if min_date:
            try:
                min_dt = datetime.strptime(min_date, fmt)
                if parsed < min_dt:
                    return False, "日期不能早于允许的最小日期"
            except ValueError:
                pass

        if max_date:
            try:
                max_dt = datetime.strptime(max_date, fmt)
                if parsed > max_dt:
                    return False, "日期不能晚于允许的最大日期"
            except ValueError:
                pass

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
        template_data = data.get('template_data', {})

        join_date_str = None
        confirm_date_str = None

        t1 = template_data.get("template_001", {})
        t2 = template_data.get("template_002", {})

        if isinstance(t1, dict):
            join_date_str = t1.get("入党时间")
        if isinstance(t2, dict):
            confirm_date_str = t2.get("转正时间")

        if join_date_str and confirm_date_str:
            try:
                # 默认按完整日期处理
                d1 = datetime.strptime(join_date_str, "%Y年%m月%d日")
                d2 = datetime.strptime(confirm_date_str, "%Y年%m月%d日")
                if d2 < d1:
                    errors.append({
                        "field": "转正时间",
                        "message": "转正时间不能早于入党时间"
                    })
            except ValueError:
                # 格式异常时略过关系校验，由单字段验证负责
                pass
        
        return errors

