#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
数据验证器
"""

from datetime import datetime
from dateutil.relativedelta import relativedelta
import re


class Validators:
    """数据验证器类"""
    
    @staticmethod
    def validate_field(field_def, value):
        """验证单个字段"""
        if field_def.get('required', False) and not value:
            return False, f"{field_def.get('key', '字段')}不能为空"
        
        field_type = field_def.get('type')

        if field_def.get('required', False) and field_type == "date" and value == "    年  月  日":
            return False, f"{field_def.get('key', '字段')}不能为空"
        
        if field_type == 'text':
            ok, msg = Validators.validate_text(value, field_def.get('validation', {}))
            if not ok:
                return ok, msg
            # 身份证号补充校验码验证
            if field_def.get('key') == '身份证号' and value:
                return Validators._check_id_card_checksum(value)
            return ok, msg
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
        if not value or value == "无":
            return True, None

        fmt = "%Y-%m-%d"  
        if format == "YYYY年M月D日":
            fmt = "%Y年%m月%d日"
        elif format == "YYYY年M月":
            fmt = "%Y年%m月"
        elif format == "YYYY年MM月DD日":
            fmt = "%Y年%m月%d日"
        elif format == "YYYY年MM月":
            fmt = "%Y年%m月"
        
        if value =="    年  月  日" or value == "无":
            return True, None

        parsed = datetime.strptime(value, fmt)

        if min_date:
            min_dt = datetime.strptime(min_date, fmt)
            if parsed < min_dt:
                return False, "日期不能早于允许的最小日期"
        if max_date:
            max_dt = datetime.strptime(max_date, fmt)
            if parsed > max_dt:
                return False, "日期不能晚于允许的最大日期"

        return True, None
    
    @staticmethod
    def _check_id_card_checksum(value):
        """校验身份证第18位校验码"""
        if len(value) != 18:
            return False, "身份证号格式不正确"

        weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']

        total = 0
        for i in range(17):
            if not value[i].isdigit():
                return False, "身份证号格式不正确"
            total += int(value[i]) * weights[i]

        expected = check_codes[total % 11]
        if value[17].upper() != expected:
            return False, "身份证号校验码不正确"

        return True, None

    @staticmethod
    def validate_select(value, options):
        """选择项验证"""
        if not value:
            return True, None
        
        if value not in options:
            return False, f"值必须在 {options} 中"
        
        return True, None
    
    _DATE_EMPTY = {"", "无", "    年  月  日"}

    @staticmethod
    def _parse_date_field(value: str, fmt: str):
        """安全解析日期字段，返回 datetime 或 None（空值或格式错误时）。"""
        if value in Validators._DATE_EMPTY:
            return None
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def validate_logical_relations(data):
        """逻辑关系验证"""
        errors = []

        basic_data = data.get("basic_data", {})
        template_data = data.get("template_data", {})     # 目前未用到此信息，但之后可以根据key来检索需要验证的字段数据、并加以验证

        # ── 1. 读取所有日期字段 ──
        birthday = Validators._parse_date_field(basic_data.get("出生日期"), "%Y年%m月%d日")
        league = Validators._parse_date_field(basic_data.get("入团时间"), "%Y年%m月")
        join = Validators._parse_date_field(basic_data.get("申请入党时间"), "%Y年%m月%d日")
        activist = Validators._parse_date_field(basic_data.get("确定积极分子时间"), "%Y年%m月%d日")
        develop = Validators._parse_date_field(basic_data.get("确定发展对象时间"), "%Y年%m月%d日")
        probation = Validators._parse_date_field(basic_data.get("成为预备党员时间"), "%Y年%m月%d日")
        formal = Validators._parse_date_field(basic_data.get("转为正式党员时间"), "%Y年%m月%d日")

        add_err = lambda f, m: errors.append({"field": f, "message": m})

        # ── 2. 前置依赖检查：后一个时间填入时，前一个时间必须已填 ──
        # 定义依赖链：(当前字段名, 当前值, 前置字段名, 前置值, 错误消息模板)
        deps = [
            # 入团 → 出生日期
            ("入团时间", league, "出生日期", birthday, "入团时间不为空时，出生日期不能为空"),
            # 申请入党 → 出生日期
            ("申请入党时间", join, "出生日期", birthday, "申请入党时间不为空时，出生日期不能为空"),
            # 积极分子 → 申请入党、出生日期
            ("确定积极分子时间", activist, "申请入党时间", join, "确定积极分子时间不为空时，申请入党时间不能为空"),
            ("确定积极分子时间", activist, "出生日期", birthday, "确定积极分子时间不为空时，出生日期不能为空"),
            # 发展对象 → 申请入党、积极分子、出生日期
            ("确定发展对象时间", develop, "申请入党时间", join, "确定发展对象时间不为空时，申请入党时间不能为空"),
            ("确定发展对象时间", develop, "确定积极分子时间", activist, "确定发展对象时间不为空时，确定积极分子时间不能为空"),
            ("确定发展对象时间", develop, "出生日期", birthday, "确定发展对象时间不为空时，出生日期不能为空"),
            # 预备党员 → 申请入党、积极分子、发展对象、出生日期
            ("成为预备党员时间", probation, "申请入党时间", join, "成为预备党员时间不为空时，申请入党时间不能为空"),
            ("成为预备党员时间", probation, "确定积极分子时间", activist, "成为预备党员时间不为空时，确定积极分子时间不能为空"),
            ("成为预备党员时间", probation, "确定发展对象时间", develop, "成为预备党员时间不为空时，确定发展对象时间不能为空"),
            ("成为预备党员时间", probation, "出生日期", birthday, "成为预备党员时间不为空时，出生日期不能为空"),
            # 正式党员 → 申请入党、积极分子、发展对象、预备党员、出生日期
            ("转为正式党员时间", formal, "申请入党时间", join, "转为正式党员时间不为空时，申请入党时间不能为空"),
            ("转为正式党员时间", formal, "确定积极分子时间", activist, "转为正式党员时间不为空时，确定积极分子时间不能为空"),
            ("转为正式党员时间", formal, "确定发展对象时间", develop, "转为正式党员时间不为空时，确定发展对象时间不能为空"),
            ("转为正式党员时间", formal, "成为预备党员时间", probation, "转为正式党员时间不为空时，成为预备党员时间不能为空"),
            ("转为正式党员时间", formal, "出生日期", birthday, "转为正式党员时间不为空时，出生日期不能为空"),
        ]

        for field_name, field_val, dep_name, dep_val, msg in deps:
            if field_val is not None and dep_val is None:
                add_err(dep_name, msg)

        # ── 3. 时间间隔校验 ──
        # 定义校验规则：(左值, 右值, 最小间隔/None表示只需先后, 左标签, 右标签, 错误消息)
        intervals = [
            (join, birthday, relativedelta(years=18),
             "申请入党时间", "出生日期", "申请入党时间必须在出生日期满18周岁之后"),
            (activist, join, relativedelta(months=6),
             "确定积极分子时间", "申请入党时间", "确定积极分子时间必须在申请入党时间满6个月之后"),
            (develop, activist, relativedelta(years=1),
             "确定发展对象时间", "确定积极分子时间", "确定发展对象时间必须在确定积极分子时间满1年之后"),
            (probation, develop, None,
             "成为预备党员时间", "确定发展对象时间", "成为预备党员时间必须在确定发展对象时间之后"),
            (formal, probation, relativedelta(years=1),
             "转为正式党员时间", "成为预备党员时间", "转为正式党员时间必须在确定预备党员时间满1年之后"),
        ]

        for later, earlier, min_delta, later_label, earlier_label, msg in intervals:
            if later is None or earlier is None:
                continue
            if later < earlier:
                add_err(later_label, f"{later_label}不能早于{earlier_label}")
            elif min_delta is not None and later - earlier < min_delta:
                add_err(later_label, msg)

        return errors

