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


class Severity:
    """校验结果级别。

    - ``BLOCK``：自相矛盾或不可能合法（如转正早于预备、日期晚于今天），应当阻断保存；
    - ``WARN``：与一般要求不一致，但真实数据中确实可能存在（如积极分子培养期
      不足 6 个月），只提示、不阻断。**拦不拦由调用方决定，校验器本身不抛异常。**
    """
    BLOCK = "block"
    WARN = "warn"


# ── 时间轴结构（代码契约）──────────────────────────────────────────
# 主干：链式节点依次要求前置项已填、且时间不早于前置项。
# 顺序与完整性由此自动派生，无需手工罗列依赖组合。
CHAIN_FIELDS = (
    "出生日期",
    "申请入党时间",
    "确定积极分子时间",
    "确定发展对象时间",
    "成为预备党员时间",
    "转为正式党员时间",
)

# 旁支节点：只要求「填了就说明前置项也该填」，不参与主干链
SIDE_FIELDS = ("入团时间",)
SIDE_PREREQUISITES = {"入团时间": ("出生日期",)}

# 缺省日期格式（schema 的 format 缺失或非法时兜底）
_DEFAULT_FIELD_FORMATS = {
    **{key: "YYYY年M月D日" for key in CHAIN_FIELDS},
    "入团时间": "YYYY年M月",
}

# 「未来日期」这类节点级规则在规则表中的名字（只能配 severity，没有间隔）
FUTURE_DATE_RULE_ID = "未来日期"

# 最小间隔配置非法时的哨兵：表示「不要覆盖默认值」
_UNSET = object()


# ── 成员时间节点规则表（阈值与级别可在 schema 的 member_time_rules 段按 id 覆盖）──
# min_interval 为 None 表示只校验先后顺序。id 同时用于配置覆盖与问题溯源。
DEFAULT_TIME_RULES = (
    {
        "id": "申请入党年龄",
        "earlier": "出生日期",
        "later": "申请入党时间",
        "min_interval": relativedelta(years=18),
        "severity": Severity.BLOCK,
        "message": "申请入党时间必须在出生日期满18周岁之后",
    },
    {
        "id": "积极分子培养期",
        "earlier": "申请入党时间",
        "later": "确定积极分子时间",
        "min_interval": relativedelta(months=6),
        "severity": Severity.WARN,
        "message": "确定积极分子时间一般应在申请入党满6个月之后，请确认是否符合实际",
    },
    {
        "id": "发展对象培养期",
        "earlier": "确定积极分子时间",
        "later": "确定发展对象时间",
        "min_interval": relativedelta(years=1),
        "severity": Severity.WARN,
        "message": "确定发展对象时间必须在确定为积极分子满1年之后",
    },
    {
        "id": "发展对象到预备党员",
        "earlier": "确定发展对象时间",
        "later": "成为预备党员时间",
        "min_interval": None,
        "severity": Severity.BLOCK,
        "message": "成为预备党员时间必须在确定发展对象时间之后",
    },
    {
        "id": "预备期",
        "earlier": "成为预备党员时间",
        "later": "转为正式党员时间",
        "min_interval": relativedelta(years=1),
        "severity": Severity.BLOCK,
        "message": "转为正式党员时间必须在成为预备党员满1年之后",
    },
    {
        "id": "入团晚于出生",
        "earlier": "出生日期",
        "later": "入团时间",
        "min_interval": None,
        "severity": Severity.BLOCK,
        "message": "入团时间必须晚于出生日期",
    },
    {
        "id": "入团早于申请",
        "earlier": "入团时间",
        "later": "申请入党时间",
        "min_interval": None,
        "severity": Severity.WARN,
        "message": "申请入党时间一般应晚于入团时间，请确认是否符合实际",
    },
)


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
        """日期验证

        "    年  月  日"（未填）与任意「特殊内容」（如"无""不详"）都视为合法：
        特殊内容是用户在日期控件中自由填写的文本，无法参与日期先后比较，直接放行。
        """
        if Validators._is_blank_date(value):
            return True, None

        fmt = Validators._format_to_strptime(format)

        if value == "    年  月  日":
            return True, None

        try:
            parsed = datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            # 无法解析为日期：按「特殊内容」处理，放行而不是报错
            return True, None

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
    
    # 视为「日期未填」的值（已 strip）：""、"无"（历史占位值）、未填占位符。
    # 其余无法解析的文本（"不详"等特殊内容）是**有效业务值**，只是不参与日期比较，
    # 由 _parse_date_field 捕获解析异常后返回 None。
    _DATE_EMPTY = {"", "无", "年  月  日"}

    @staticmethod
    def _is_blank_date(value) -> bool:
        """判断日期字段是否「未填」。

        特殊内容（"不详"等）不是未填，只是无法参与日期比较。
        """
        if value is None:
            return True
        if not isinstance(value, str):
            return False
        return value.strip() in Validators._DATE_EMPTY

    @staticmethod
    def _format_to_strptime(format_text: str) -> str:
        """把 schema 中的 format 文本（如 "YYYY年M月D日"）转成 strptime 格式串。

        无法识别时退回 "%Y-%m-%d"，与历史行为一致。
        """
        if format_text in ("YYYY年M月D日", "YYYY年MM月DD日"):
            return "%Y年%m月%d日"
        if format_text in ("YYYY年M月", "YYYY年MM月"):
            return "%Y年%m月"
        if format_text == "YYYY/MM/DD":
            return "%Y/%m/%d"
        return "%Y-%m-%d"

    @staticmethod
    def _parse_date_field(value, fmt: str):
        """安全解析日期字段，返回 datetime 或 None（空值、特殊内容或格式错误时）。"""
        if Validators._is_blank_date(value):
            return None
        try:
            return datetime.strptime(value.strip(), fmt)
        except (ValueError, TypeError):
            return None

    # ── 规则解析 ────────────────────────────────────────────────

    @staticmethod
    def _normalize_severity(value):
        """规范化级别文本，无法识别时返回 None（表示不要覆盖）。"""
        text = str(value or "").strip().lower()
        if text in ("block", "error", "hard", "阻断", "错误"):
            return Severity.BLOCK
        if text in ("warn", "warning", "soft", "提示", "警告"):
            return Severity.WARN
        return None

    @staticmethod
    def _normalize_interval(value):
        """解析最小间隔配置。

        ``{"years": 1}`` → ``relativedelta``；``None`` / ``{}`` → ``None``（只校验先后）；
        非法值 → ``_UNSET``（表示不要覆盖默认值）。
        """
        if value is None or value == {}:
            return None
        if not isinstance(value, dict):
            return _UNSET
        kwargs = {}
        for unit in ("years", "months", "weeks", "days"):
            raw = value.get(unit)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                continue
            if raw >= 0:
                kwargs[unit] = int(raw)
        if not kwargs:
            return _UNSET
        try:
            return relativedelta(**kwargs)
        except (TypeError, ValueError):
            return _UNSET

    @staticmethod
    def _resolve_time_rules(rules_config):
        """合并内置默认规则与 schema 覆盖项。

        Args:
            rules_config: schema 中 ``member_time_rules`` 段内容，可为 None。

        Returns:
            tuple: (``{rule_id: rule}``, 未来日期规则级别)。

        未知规则名、非法字段一律忽略，保证配置笔误不会让校验静默失效。
        """
        rules = {rule["id"]: dict(rule) for rule in DEFAULT_TIME_RULES}
        future_severity = Severity.BLOCK

        if not isinstance(rules_config, dict):
            return rules, future_severity

        overrides = rules_config.get("rules")
        if not isinstance(overrides, list):
            return rules, future_severity

        for item in overrides:
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("id", "")).strip()
            severity = Validators._normalize_severity(item.get("severity"))

            # 节点级规则只有级别可调，没有先后/间隔概念
            if rule_id == FUTURE_DATE_RULE_ID:
                if severity:
                    future_severity = severity
                continue

            rule = rules.get(rule_id)
            if rule is None:
                continue
            if severity:
                rule["severity"] = severity
            if "min_interval" in item:
                interval = Validators._normalize_interval(item.get("min_interval"))
                if interval is not _UNSET:
                    rule["min_interval"] = interval

        return rules, future_severity

    # ── 逻辑关系验证 ────────────────────────────────────────────

    @staticmethod
    def validate_logical_relations(data, rules_config=None, field_formats=None):
        """校验时间节点之间的逻辑关系（纯计算，不抛异常）。

        Args:
            data: 成员数据，读取其 ``basic_data``。
            rules_config: schema 中 ``member_time_rules`` 段的覆盖配置（可为 None）。
            field_formats: 字段 key → 日期格式文本（来自 schema 的 ``format``）。

        Returns:
            list[dict]: 问题列表，每条包含
                ``field`` / ``message`` / ``severity`` / ``code`` / ``rule_id``。

        ``code`` 含义：
            - ``future``：日期晚于今天（几乎一定是笔误）；
            - ``missing-prerequisite``：填了后项却缺前置项（数据不完整，
              草稿保存时可忽略）；
            - ``order``：先后顺序颠倒；
            - ``interval``：间隔不足。

        ``severity`` 为 ``Severity.BLOCK``（应当阻断）或 ``Severity.WARN``
        （与一般要求不一致但可能真实存在，提示后放行）。**是否阻断由调用方决定**。
        """
        basic_data = (data or {}).get("basic_data") or {}
        if not isinstance(basic_data, dict):
            basic_data = {}

        formats = dict(_DEFAULT_FIELD_FORMATS)
        if isinstance(field_formats, dict):
            for key, value in field_formats.items():
                if isinstance(value, str) and value.strip():
                    formats[key] = value.strip()

        parsed = {}
        for key in CHAIN_FIELDS + SIDE_FIELDS:
            fmt = Validators._format_to_strptime(formats.get(key, ""))
            parsed[key] = Validators._parse_date_field(basic_data.get(key, ""), fmt)

        rules, future_severity = Validators._resolve_time_rules(rules_config)
        issues = []

        def add(field, message, severity, code, rule_id=""):
            issues.append({
                "field": field,
                "message": message,
                "severity": severity,
                "code": code,
                "rule_id": rule_id,
            })

        # 1) 未来日期
        now = datetime.now()
        for key in CHAIN_FIELDS + SIDE_FIELDS:
            value = parsed.get(key)
            if value is not None and value > now:
                add(key, f"{key}不能晚于今天", future_severity, "future", FUTURE_DATE_RULE_ID)

        # 2) 完整性：填了某节点，则其所有前置节点都应已填
        for index, key in enumerate(CHAIN_FIELDS):
            if Validators._is_blank_date(basic_data.get(key)):
                continue
            for predecessor in CHAIN_FIELDS[:index]:
                if Validators._is_blank_date(basic_data.get(predecessor)):
                    add(predecessor, f"{key}不为空时，{predecessor}不能为空",
                        Severity.BLOCK, "missing-prerequisite", "missing-prerequisite")

        for key, prerequisites in SIDE_PREREQUISITES.items():
            if Validators._is_blank_date(basic_data.get(key)):
                continue
            for predecessor in prerequisites:
                if Validators._is_blank_date(basic_data.get(predecessor)):
                    add(predecessor, f"{key}不为空时，{predecessor}不能为空",
                        Severity.BLOCK, "missing-prerequisite", "missing-prerequisite")

        # 3) 先后顺序与最小间隔
        for rule in rules.values():
            earlier_key = rule.get("earlier")
            later_key = rule.get("later")
            earlier_value = parsed.get(earlier_key)
            later_value = parsed.get(later_key)
            if earlier_value is None or later_value is None:
                continue

            severity = rule.get("severity", Severity.BLOCK)
            rule_id = rule.get("id", "")

            if later_value < earlier_value:
                add(later_key, f"{later_key}不能早于{earlier_key}", severity, "order", rule_id)
                continue

            interval = rule.get("min_interval")
            if interval is not None and earlier_value + interval > later_value:
                add(later_key,
                    rule.get("message", f"{later_key}与{earlier_key}间隔不足"),
                    severity, "interval", rule_id)

        return issues

    @staticmethod
    def split_issues(issues):
        """按级别拆分问题列表，返回 (阻断项, 提示项)。"""
        blocks = [item for item in (issues or []) if item.get("severity") != Severity.WARN]
        warns = [item for item in (issues or []) if item.get("severity") == Severity.WARN]
        return blocks, warns

    @staticmethod
    def format_issues(issues) -> str:
        """把问题列表格式化为多行文本（UI 展示用）。"""
        lines = []
        for item in issues or []:
            field = str(item.get("field", "") or "").strip()
            message = str(item.get("message", "") or "").strip()
            lines.append(f" · {field}：{message}" if field else f" · {message}")
        return "\n".join(lines)


