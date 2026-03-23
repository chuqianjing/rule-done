#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据验证器
"""

import re
from datetime import datetime


class Validators:
    """数据验证器类"""
    '''
    "validation_status": {
    "basic_data": {
      "valid": true,
      "errors": []
    },
    "logical": {
      "valid": false,
      "errors": [
        {
          "field": "确定积极分子时间",
          "message": "确定积极分子时间必须在申请入党时间满6个月之后"
        }
      ]
    }
  },
    '''
    
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
    def validate_logical_relations(data):
        """逻辑关系验证"""
        errors = []

        basic_data = data.get("basic_data", {})
        template_data = data.get("template_data", {})     # 目前为用到此信息，但之后可以根据key来检索需要验证的字段数据、并加以验证

        birthday_str = basic_data.get("出生日期")
        join_date_str = basic_data.get("申请入党时间")
        activist_date_str = basic_data.get("确定积极分子时间")
        develop_date_str = basic_data.get("确定发展对象时间")
        probation_date_str = basic_data.get("确定预备党员时间")
        formal_date_str = basic_data.get("转为正式党员时间")

        if birthday_str and join_date_str:
            d1 = datetime.strptime(birthday_str, "%Y年%m月%d日")
            d2 = datetime.strptime(join_date_str, "%Y年%m月%d日")
            # 如果不满18周岁
            if (d2 - d1).days < 18 * 365:
                errors.append({
                    "field": "申请入党时间",
                    "message": "申请入党时间必须在出生日期满18周岁之后"
                })
        if join_date_str and activist_date_str:
            d1 = datetime.strptime(join_date_str, "%Y年%m月%d日")
            d2 = datetime.strptime(activist_date_str, "%Y年%m月%d日")
            # 如果积极分子时间不满6个月
            if (d2 - d1).days < 180:
                errors.append({
                    "field": "确定积极分子时间",
                    "message": "确定积极分子时间必须在申请入党时间满6个月之后"
                })
        if activist_date_str and develop_date_str:
            d1 = datetime.strptime(activist_date_str, "%Y年%m月%d日")
            d2 = datetime.strptime(develop_date_str, "%Y年%m月%d日")
            # 如果发展对象时间不满1年
            if (d2 - d1).days < 365:
                errors.append({
                    "field": "确定发展对象时间",
                    "message": "确定发展对象时间必须在确定积极分子时间满1年之后"
                })
        if develop_date_str and probation_date_str:
            d1 = datetime.strptime(develop_date_str, "%Y年%m月%d日")
            d2 = datetime.strptime(probation_date_str, "%Y年%m月%d日")
            # 如果时间先后不正确
            if d2 < d1:
                errors.append({
                    "field": "确定预备党员时间",
                    "message": "确定预备党员时间必须在确定发展对象时间之后"
                })
        if probation_date_str and formal_date_str:
            d1 = datetime.strptime(probation_date_str, "%Y年%m月%d日")
            d2 = datetime.strptime(formal_date_str, "%Y年%m月%d日")
            # 如果不满1年转正
            if (d2 - d1).days < 365:
                errors.append({
                    "field": "转为正式党员时间",
                    "message": "转为正式党员时间必须在确定预备党员时间满1年之后"
                })
        
        return errors

