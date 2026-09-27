#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
材料审核契约（材料审核表列名 / 审核状态 / 保留键）

本模块是「材料审核」功能的**唯一契约来源**，供以下各处共用，避免魔法字符串散落：

- 同步层 `InfoSyncManager`：组装审核记录字段、解析回读的审核状态；
- 业务层 `DataManager`：读写 `admin_config` / `member_info` 中的 `_review` 保留键；
- UI 层：材料执行状态的呈现与「导出 / 锁定」按钮闸门；
- `docs/sync_guide.md`：管理员需在在线表格中创建的列名。

## 核心约定

1. **材料审核表所有列均使用文本类型**。
   三家平台对「单选 / 日期 / 数字」列的写入语义不一致（选项自动创建、时区与格式解析、
   类型不匹配直接报错），文本列最稳；且与基本信息表同步「一律转字符串」的既有做法一致。
2. **「审核状态」列由管理员手工填写**，成员端只识别「已通过」「需修改」，
   其余任意值（含空）一律按「待审核」处理，见 `normalize_review_status`。
3. **材料审核表记录主键 = (唯一标识字段值, 材料标识)**，一行 = 一个「成员 × 材料」。
   「唯一标识字段」的列名由管理员配置的 `KEY_ID_FIELD` 动态决定，故不作为常量。

Author: 楚乾靖
Date: 2026-09
"""

from typing import Any, Dict, Set

from src.persistence.admin_config_builtin_fields import ID_FIELD_DEFAULT

# ============================ 保留键（admin_config / member_info） ============================

REVIEW_KEY = "_review"
"""模板条目内的审核子状态保留键。前导下划线确保与 docx 占位符名不冲突。"""

REVIEW_ENABLED_FIELD = "enabled"
"""`admin_config.template_data[tid]._review.enabled`：该模板是否开启审核机制。"""

RESERVED_TEMPLATE_KEYS: frozenset = frozenset({
    REVIEW_KEY,
    "basic_entry",
    "template_entry",
    "locked",
    "work_start",
    "version",
    "archive_images",
    "progress_reminder",
})
"""模板条目中的保留键（非占位符）。任何「遍历模板条目」的逻辑都应排除它们。"""


def is_reserved_template_key(key: Any) -> bool:
    """判断键是否为保留键（非占位符）。按下划线前缀兜底，防止未来新增保留键漏登记。"""
    text = str(key or "").strip()
    return text in RESERVED_TEMPLATE_KEYS or text.startswith("_")


# ============================ 材料审核表列名 ============================

COL_NAME = "姓名"
COL_TEMPLATE_ID = "材料标识"
COL_STAGE = "阶段"
COL_CONTENT = "提交内容"
COL_STATUS = "审核状态"
COL_COMMENT = "审核意见"
COL_SUBMITTED_AT = "提交时间"
COL_SUBMIT_COUNT = "提交次数"

REQUIRED_COLUMNS: tuple = (
    COL_NAME,
    COL_TEMPLATE_ID,
    COL_STAGE,
    COL_CONTENT,
    COL_STATUS,
    COL_COMMENT,
    COL_SUBMITTED_AT,
    COL_SUBMIT_COUNT,
)
"""除「唯一标识」列外的必需列（用于材料审核表可访问性与结构校验）。"""


def review_column_names(id_field: Any = "") -> tuple:
    """返回材料审核表的完整列名（首列为唯一标识列，列名由管理员配置决定）。"""
    return (str(id_field or "").strip() or ID_FIELD_DEFAULT,) + REQUIRED_COLUMNS


# ============================ 审核状态 ============================

REVIEW_STATUS_PENDING = "待审核"
REVIEW_STATUS_APPROVED = "已通过"
REVIEW_STATUS_REJECTED = "需修改"

REVIEW_STATUS_VALUES: tuple = (
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_REJECTED,
)
"""材料审核表「审核状态」列的合法取值（由管理员手工填写）。"""

REVIEW_STATE_NONE = ""
"""本地 `_review.status` 的「未提交」取值（含被撤回、被作废）。"""

LOCAL_REVIEW_STATES: tuple = (
    REVIEW_STATE_NONE,
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_REJECTED,
    REVIEW_STATUS_APPROVED,
)

# 管理员可能手写的近义表述，统一归一化到三个标准值
_STATUS_ALIASES: Dict[str, str] = {
    "已通过": REVIEW_STATUS_APPROVED,
    "通过": REVIEW_STATUS_APPROVED,
    "同意": REVIEW_STATUS_APPROVED,
    "合格": REVIEW_STATUS_APPROVED,
    "需修改": REVIEW_STATUS_REJECTED,
    "不通过": REVIEW_STATUS_REJECTED,
    "退回": REVIEW_STATUS_REJECTED,
    "打回": REVIEW_STATUS_REJECTED,
    "不合格": REVIEW_STATUS_REJECTED,
}


def normalize_review_status(raw: Any) -> str:
    """把材料审核表回读的状态文本归一化为标准值。

    无法识别（含空值、随意文本）时一律返回 `REVIEW_STATUS_PENDING`，
    即「未给出明确结论」按待审核处理，不会误放行。
    """
    text = str(raw or "").strip()
    return _STATUS_ALIASES.get(text, REVIEW_STATUS_PENDING)


# ============================ 面向 UI 的执行状态 ============================

EXEC_STATE_UNFILLED = "未填写"
EXEC_STATE_FILLING = "填写中"
EXEC_STATE_PENDING = REVIEW_STATUS_PENDING
EXEC_STATE_REJECTED = REVIEW_STATUS_REJECTED
EXEC_STATE_APPROVED = REVIEW_STATUS_APPROVED
EXEC_STATE_LOCKED = "已锁定"

EXEC_STATES: tuple = (
    EXEC_STATE_UNFILLED,
    EXEC_STATE_FILLING,
    EXEC_STATE_PENDING,
    EXEC_STATE_REJECTED,
    EXEC_STATE_APPROVED,
    EXEC_STATE_LOCKED,
)


# ============================ 内容归一化与默认结构 ============================

_BLANK_TEXT_VALUES: frozenset = frozenset({"", "年  月  日"})
"""归一化后视为「空」的文本。

`年  月  日` 是三态日期控件未填写时的占位形态（控件原值为 "    年  月  日"，
strip 后即为此串）。与 `InfoSyncManager._BLANK_STRING_VALUES` 同一判定理由。
注意「无」是有效业务值，**不算空**。
"""


def normalize_review_text(value: Any) -> str:
    """把待填项的值归一化为可比较的文本。

    规则：None/非字符串转字符串 → 统一换行为 `\\n` → 去掉各行的行尾空白 →
    整体 strip → 空白占位视为空串。用于「内容是否变化」的比对，
    以消除平台回读时的换行差异与控件占位差异造成的误判。
    """
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n")).strip()
    return "" if text in _BLANK_TEXT_VALUES else text


def build_review_state() -> Dict[str, Any]:
    """返回一个全新的、默认的审核子状态结构（每次调用均返回独立副本）。"""
    return {
        "status": REVIEW_STATE_NONE,
        "comment": "",
        "submit_count": 0,
        "submitted_at": "",
        "fingerprint": {},
    }


def copy_review_state(review: Dict[str, Any]) -> Dict[str, Any]:
    """浅拷贝审核子状态，并把 `fingerprint` 也复制一层，避免共享可变对象。"""
    result = dict(review or {})
    fingerprint = result.get("fingerprint")
    result["fingerprint"] = dict(fingerprint) if isinstance(fingerprint, dict) else {}
    return result


def is_review_content_changed(
    fingerprint: Any,
    current: Any,
    keys: Set[str] | None = None,
) -> bool:
    """比对提交指纹与当前内容是否不同。

    Args:
        fingerprint: 提交时存档的 `{占位符: 值}`。
        current: 当前的表单数据（可含锁定项，会比较前剔除保留键）。
        keys: 比较范围；为 None 时以指纹自身的键为准。
            调用方若传入**当前待填项集合**，则"提交后新增的待填项"也能被识别为变化。

    Returns:
        bool: True 表示内容已变化（应作废审核结果）。

    Notes:
        指纹为空（从未提交）时恒返回 False——"没有可作废的审核"。
    """
    if not isinstance(fingerprint, dict) or not fingerprint:
        return False
    current_data = current if isinstance(current, dict) else {}
    compare_keys = set(keys) if keys else set(fingerprint)
    for key in compare_keys:
        if is_reserved_template_key(key):
            continue
        if normalize_review_text(current_data.get(key)) != normalize_review_text(fingerprint.get(key)):
            return True
    return False


# ============================ 提交内容文本 ============================

EMPTY_FIELD_PLACEHOLDER = "（未填写）"
"""待填项为空时在提交内容中的占位提示，便于管理员发现漏填。"""


def build_review_content_text(pending_fields: Any) -> str:
    """把待填项拼接为提交内容文本。

    格式（每个项一个块，块间以空行分隔）：

        【占位符名】
        值

    - **保持传入顺序**：调用方需按文档阅读顺序（`doc_order`）传入；
    - 值为空时输出 ``EMPTY_FIELD_PLACEHOLDER``，而不是留白；
    - 不包含管理员锁定项与管理员原始提示值（由调用方保证）。
    """
    if not isinstance(pending_fields, dict) or not pending_fields:
        return ""
    blocks = []
    for key, value in pending_fields.items():
        text = str(value or "").strip()
        blocks.append(f"【{key}】\n{text or EMPTY_FIELD_PLACEHOLDER}")
    return "\n\n".join(blocks)
