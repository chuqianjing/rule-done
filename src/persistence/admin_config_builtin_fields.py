#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
管理员配置内置字段契约（admin_config.json → basic_data.双端交互）

命名说明：本模块描述 **admin_config.json 中「双端交互」分组** 的字段定义，
与「系统设置」（system_settings.json / SettingsManager）、
「管理员设置页」（admin_settings_page.py）以及用户 schema（fields_definition.json）
均无关，勿混。

该分组属于工具级技术契约而非党务内容字段，因此不通过用户 schema 定制：

- 代码按组名与键名读取其值（快照天数、汇总平台凭据、资源清单 URL 等），
  一旦可被改名/删除即会静默降级，故键名、类型、枚举、掩码、必填全部锁定在代码中；
- 用户 schema 中的同名分组会被 FieldManager 忽略，避免契约被覆盖；
- 该分组不进入模板占位符命名空间（不参与 get_fields('template') 平铺），
  防止凭据类字段被 .docx 模板引用；
- 但其**值**仍存放在 admin_config.basic_data.双端交互.*，随管理员配置加密发布给成员端。

字段元数据（供 UI 与数据层共用，避免各处再写魔法字符串集合）：
- secret：密钥类字段，UI 以密码框呈现、落盘前加密；
- info_sync_platform：所属「成员信息汇总平台」，UI 据此显隐；保存时仅保留当前平台凭据；
- info_sync_role：该字段在平台凭据映射中的角色名（组装 InfoSyncManager 配置用）；
- ui_role：特殊控件角色（info_sync_platform_selector = 汇总平台选择下拉框）；
- section_after：在该字段行之后插入带文字的分隔线（分组内的段落视觉划分）；
- required：恒为 False —— 平台凭据按当前 provider 条件生效，不参与全局必填校验。

Author: 楚乾靖
Date: 2026-09
"""

from copy import deepcopy
from typing import Any, Dict

# ============================ 分组标识 ============================

GROUP_NAME = "双端交互"
GROUP_ORDER = 4
GROUP_ROLE = "admin_config_builtin"                 # 分组角色标记：admin_config 的代码内置分组
FOOTER_ACTION_TEST_CONNECTION = "test_connection"   # 分组底部附加"测试连接"按钮

# ============================ 字段键（代码读取入口） ============================

KEY_MEMBER_MODE_SWITCH = "成员可否切换模式"
KEY_RESOURCE_MANIFEST_URL = "支部资源清单URL"
KEY_BRANCH_CONFIG_URL = "支部配置文件URL"
KEY_SNAPSHOT_DAYS = "配置快照有效天数"
KEY_INFO_SYNC_PLATFORM = "成员信息汇总平台"
KEY_ID_FIELD = "唯一标识字段"

ID_FIELD_DEFAULT = "身份证号"

# ============================ 平台枚举 ============================

INFO_SYNC_PLATFORMS = ("飞书", "腾讯", "WPS")
DEFAULT_INFO_SYNC_PLATFORM = "飞书"

# ============================ 快照有效期阈值 ============================

SNAPSHOT_DAYS_DEFAULT = 30
SNAPSHOT_DAYS_MIN = 1
SNAPSHOT_DAYS_MAX = 365

# ============================ 分组内段落分隔线文案 ============================

SECTION_ADMIN_DATA_SYNC = "管理员数据同步"
SECTION_MEMBER_INFO_SYNC = "成员信息同步"

# ============================ 字段定义 ============================

FIELDS: list[Dict[str, Any]] = [
    {
        "key": KEY_MEMBER_MODE_SWITCH, "type": "select", "required": False,
        "options": ["禁止", "允许"],
        "section_after": SECTION_ADMIN_DATA_SYNC,
        "display": {"order": 1, "placeholder": "若设为允许，则成员端可编辑配置信息，且仅作用于该成员端"},
    },
    {
        "key": KEY_RESOURCE_MANIFEST_URL, "type": "text", "required": False,
        "display": {"order": 2, "placeholder": "管理员发布资源时自动填入，无需专门填写"},
    },
    {
        "key": KEY_BRANCH_CONFIG_URL, "type": "text", "required": False,
        "display": {"order": 3, "placeholder": "请确保成员拥有此 URL 的同步凭据"},
    },
    {
        "key": KEY_SNAPSHOT_DAYS, "type": "number", "required": False,
        "section_after": SECTION_MEMBER_INFO_SYNC,
        "display": {
            "order": 4,
            "min": SNAPSHOT_DAYS_MIN,
            "max": SNAPSHOT_DAYS_MAX,
            "default": SNAPSHOT_DAYS_DEFAULT,
            "placeholder": "支部配置对成员端生效的天数，期满后成员材料将按其自身数据固化（默认30天）",
        },
    },
    {
        "key": KEY_INFO_SYNC_PLATFORM, "type": "select", "required": False,
        "options": list(INFO_SYNC_PLATFORMS),
        "ui_role": "info_sync_platform_selector",
        "display": {"order": 5, "placeholder": "请选择成员信息汇总平台"},
    },
    {
        "key": KEY_ID_FIELD, "type": "text", "required": False,
        "info_sync_role": "id_field",
        "display": {"order": 6, "placeholder": "建议设为：身份证号"},
    },
    # ---------- 飞书 ----------
    {
        "key": "飞书AppID", "type": "text", "required": False,
        "info_sync_platform": "飞书", "info_sync_role": "app_id",
        "display": {"order": 7, "placeholder": "从开发平台获取"},
    },
    {
        "key": "飞书AppSecret", "type": "text", "required": False, "secret": True,
        "info_sync_platform": "飞书", "info_sync_role": "app_secret",
        "display": {"order": 8, "placeholder": "从开发平台获取"},
    },
    {
        "key": "飞书AppToken", "type": "text", "required": False,
        "info_sync_platform": "飞书", "info_sync_role": "app_token",
        "display": {"order": 9, "placeholder": "从在线表格获取"},
    },
    {
        "key": "飞书TableID", "type": "text", "required": False,
        "info_sync_platform": "飞书", "info_sync_role": "table_id",
        "display": {"order": 10, "placeholder": "从在线表格获取"},
    },
    # ---------- 腾讯 ----------
    {
        "key": "腾讯ClientID", "type": "text", "required": False,
        "info_sync_platform": "腾讯", "info_sync_role": "client_id",
        "display": {"order": 11, "placeholder": "从开发平台获取"},
    },
    {
        "key": "腾讯AccessToken", "type": "text", "required": False, "secret": True,
        "info_sync_platform": "腾讯", "info_sync_role": "access_token",
        "display": {"order": 12, "placeholder": "从开发平台获取"},
    },
    {
        "key": "腾讯OpenID", "type": "text", "required": False, "secret": True,
        "info_sync_platform": "腾讯", "info_sync_role": "open_id",
        "display": {"order": 13, "placeholder": "从开发平台获取"},
    },
    {
        "key": "腾讯EncodedID", "type": "text", "required": False,
        "info_sync_platform": "腾讯", "info_sync_role": "file_id",
        "display": {"order": 14, "placeholder": "从在线表格获取"},
    },
    {
        "key": "腾讯SheetID", "type": "text", "required": False,
        "info_sync_platform": "腾讯", "info_sync_role": "sheet_id",
        "display": {"order": 15, "placeholder": "从在线表格获取"},
    },
    # ---------- WPS ----------
    {
        "key": "WPS应用ID", "type": "text", "required": False,
        "info_sync_platform": "WPS", "info_sync_role": "app_id",
        "display": {"order": 16, "placeholder": "从开发平台获取"},
    },
    {
        "key": "WPS应用密钥", "type": "text", "required": False, "secret": True,
        "info_sync_platform": "WPS", "info_sync_role": "app_secret",
        "display": {"order": 17, "placeholder": "从开发平台获取"},
    },
    {
        "key": "WPSFileID", "type": "text", "required": False,
        "info_sync_platform": "WPS", "info_sync_role": "app_token",
        "display": {"order": 18, "placeholder": "从在线表格获取"},
    },
    {
        "key": "WPSSheetID", "type": "text", "required": False,
        "info_sync_platform": "WPS", "info_sync_role": "table_id",
        "display": {"order": 19, "placeholder": "从在线表格获取"},
    },
]

# ============================ 派生集合（全部由 FIELDS 单一来源推导） ============================

SECRET_KEYS = frozenset(str(f["key"]) for f in FIELDS if f.get("secret"))

# {汇总平台: 该平台专属的凭据键}（用于保存时剪除非当前平台的凭据）
INFO_SYNC_CREDENTIAL_KEYS: Dict[str, tuple] = {
    platform: tuple(str(f["key"]) for f in FIELDS if f.get("info_sync_platform") == platform)
    for platform in INFO_SYNC_PLATFORMS
}

# {汇总平台: {InfoSyncManager 角色名: 字段键}}（用于组装平台凭据 dict，避免键名字面量散落）
INFO_SYNC_CREDENTIAL_ROLES: Dict[str, Dict[str, str]] = {
    platform: {
        **{
            str(f["info_sync_role"]): str(f["key"])
            for f in FIELDS if f.get("info_sync_platform") == platform
        },
        "id_field": KEY_ID_FIELD,
    }
    for platform in INFO_SYNC_PLATFORMS
}


def build_group_definition() -> Dict[str, Any]:
    """构建「双端交互」分组定义（每次返回全新副本，供调用方安全修改）。"""
    return {
        "group": GROUP_NAME,
        "group_order": GROUP_ORDER,
        "group_role": GROUP_ROLE,
        "footer_action": FOOTER_ACTION_TEST_CONNECTION,
        "fields": deepcopy(FIELDS),
    }


def normalize_info_sync_platform(value: Any) -> str:
    """归一化「成员信息汇总平台」取值：非法/空值统一回退默认平台。"""
    text = str(value or "").strip()
    return text if text in INFO_SYNC_PLATFORMS else DEFAULT_INFO_SYNC_PLATFORM
