#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""成员信息同步管理器。"""

from __future__ import annotations
from typing import Any, Dict, Tuple
from urllib.parse import quote
import hashlib
import hmac
import json
import time
import requests
from src.persistence.sync_base import SyncManagerBase
from src.persistence.admin_config_builtin_fields import ID_FIELD_DEFAULT
from src.persistence.review_table_fields import (
    COL_COMMENT,
    COL_STATUS,
    COL_TEMPLATE_ID,
    REVIEW_STATUS_PENDING,
    normalize_review_status,
    review_column_names,
)

# 最后一项为飞书确认的非空字段值，供应用层持久化只读状态；其他平台返回空字典。
BasicInfoSyncResult = Tuple[bool, str, str, Dict[str, Any], Dict[str, Any]]


class InfoSyncManager(SyncManagerBase):
    """成员信息同步管理器。"""

    # 判空规则中视为「空」的字符串字面量（比较前统一 strip）：
    #   ""           空串（含纯空白）
    #   "年  月  日"   未填日期占位符（控件原值为 "    年  月  日"）
    # 注意："无"、"不详" 等「特殊内容」是有意义的业务值，**不算空**：
    #   - 「学位」select 的合法选项之一就是 "无"（resources/schema/fields_definition.json）
    #   - 三态日期控件的 MODE_SPECIAL（"输入特殊内容"）由用户自由输入，默认仍是 "    年  月  日"；
    #     只要在特殊内容模式下填写了内容（包括历史值 "无"），就属于真实值
    #   - 该值会原样输出到 docx（template_engine 出生年月）与远程表格，必须参与同步
    _BLANK_STRING_VALUES = frozenset({"", "年  月  日"})

    # 平台展示名（同步提示文案用，避免各方法内重复定义）
    _PROVIDER_DISPLAY_NAMES: Dict[str, str] = {
        "飞书": "飞书多维表",
        "腾讯": "腾讯智能表格",
        "WPS": "WPS多维表格",
    }

    # ======================= 内部公用方法 =======================

    def _extract_response_error(self, response: requests.Response) -> str:
        """从响应中提取错误信息。"""
        try:
            body = response.json() or {}
            msg = str(body.get("msg") or body.get("message") or response.text).strip()
            code = body.get("code")
            if code is not None:
                return f"code={code}, msg={msg}"
            return msg
        except Exception:
            return response.text.strip() or f"HTTP {response.status_code}"

    def _build_bearer_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _build_shared_fields(
        self,
        basic_data: Dict[str, Any],
        force_backfill_fields: set[str] | None,
        wrap_value,
    ) -> Dict[str, Any]:
        """通用字段构建：过滤空值与强制回填字段后，对每个值调用 wrap_value 包装。

        空值判定统一复用 _is_missing_local_value（仅 None / 空白串 / 未填日期占位符 / 空集合）。
        "无"（不适用）是有效业务值，会正常上传；本地为 "无" 时不会静默覆盖远程已有数据，
        而是由 _values_conflict 判定冲突并拦截。
        """
        fields_payload: Dict[str, Any] = {}
        for local_key, value in basic_data.items():
            if self._is_missing_local_value(value):
                continue
            target_key = str(local_key).strip()
            if not target_key:
                continue
            if force_backfill_fields and target_key in force_backfill_fields:
                continue
            fields_payload[target_key] = wrap_value(value)
        return fields_payload

    def _build_platform_fields(
        self,
        provider: str,
        basic_data: Dict[str, Any],
        force_backfill_fields: set[str] | None = None,
    ) -> Dict[str, Any]:
        """按平台构建记录字段载荷（各平台值格式不同）。"""
        if provider == "飞书":
            return self._build_shared_fields(basic_data, force_backfill_fields, self._feishu_wrap_value)
        if provider == "腾讯":
            return self._build_shared_fields(basic_data, force_backfill_fields, self._build_tencent_value)
        if provider == "WPS":
            return self._build_shared_fields(basic_data, force_backfill_fields, self._wps_wrap_value)
        return {}

    def _feishu_wrap_value(self, value: Any) -> str:
        """飞书字段值：一律转为字符串。"""
        return value if isinstance(value, str) else str(value)

    def _wps_wrap_value(self, value: Any):
        """WPS 字段值：数值/布尔保留原类型，其余转为字符串。"""
        return value if isinstance(value, (int, float, bool)) else str(value)

    def _values_conflict(self, existing_val, new_val) -> bool:
        """判断远程已有值与待上传值是否存在冲突。

        existing_val: 远程平台中已有的值
        new_val: 待上传的值

        任一端为空（"" / 纯空白 / "    年  月  日"）即视为无冲突，允许写入。
        "无"（不适用）属于真实值，与远程不同值时**判定为冲突并拦截**，避免静默覆盖远程数据。
        两端都非空时，按 strip 后的字符串比较，避免首尾空格造成误报冲突。
        """
        if self._is_missing_local_value(existing_val):
            return False
        if self._is_missing_local_value(new_val):
            return False
        try:
            return str(existing_val).strip() != str(new_val).strip()
        except Exception:
            return str(existing_val) != str(new_val)

    def _is_missing_local_value(self, value: Any) -> bool:
        """判断字段值是否为空（同步流程中统一的判空规则）。

        空值：None、空串或纯空白字符串、"    年  月  日"（未填日期占位符）、空集合。
        注意：
        - 数字 0 与布尔 False 属于有效值，不算空。
        - "无"（不适用/无）属于有效业务值，**不算空**（见 _BLANK_STRING_VALUES 注释）。
        """
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() in self._BLANK_STRING_VALUES
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) == 0
        return False

    def _is_non_empty_remote_value(self, value: Any) -> bool:
        """判断远程平台字段值是否为非空值（与 _is_missing_local_value 严格互补）。"""
        return not self._is_missing_local_value(value)

    def _backfill_local_missing_from_remote(
        self,
        basic_data: Dict[str, Any],
        remote_fields: Dict[str, Any],
        force_backfill_fields: set[str] | None = None,
        allowed_keys: set[str] | None = None,
    ) -> Tuple[Dict[str, Any], int, set[str]]:
        merged_data = dict(basic_data or {})
        backfilled_count = 0
        backfilled_keys = set()
        force_fields = force_backfill_fields or set()

        for remote_key, remote_val in (remote_fields or {}).items():
            if not self._is_non_empty_remote_value(remote_val):
                continue
            remote_key_str = str(remote_key).strip()
            if not remote_key_str:
                continue

            # 只回填应用 schema 认识的字段（force_backfill_fields 始终允许），忽略远程表格中的独有列
            if allowed_keys is not None and remote_key_str not in allowed_keys and remote_key_str not in force_fields:
                continue

            if remote_key_str in force_fields:
                if str(merged_data.get(remote_key_str)) == str(remote_val):
                    continue
                merged_data[remote_key_str] = remote_val
                backfilled_count += 1
                backfilled_keys.add(remote_key_str)
            elif self._is_missing_local_value(merged_data.get(remote_key_str)):
                merged_data[remote_key_str] = remote_val
                backfilled_count += 1
                backfilled_keys.add(remote_key_str)

        return merged_data, backfilled_count, backfilled_keys

    def _match_record_id(
        self,
        records: list[Dict[str, Any]],
        id_field: str,
        member_id_value: str,
    ) -> str:
        """在记录列表中按成员标识字段值匹配记录 id。

        records: 元素为 {"id": record_id, "fields": {字段名: 值}} 的列表。
        """
        for row in records:
            fields = row.get("fields") or {}
            if str(fields.get(id_field, "")).strip() == member_id_value:
                return str(row.get("id", "")).strip()
        return ""

    # ======================= 飞书多维表格 =======================

    def _validate_feishu(self, feishu_config: Dict[str, Any]) -> None:
        app_id = str(feishu_config.get("app_id", "")).strip()
        app_secret = str(feishu_config.get("app_secret", "")).strip()
        app_token = str(feishu_config.get("app_token", "")).strip()
        table_id = str(feishu_config.get("table_id", "")).strip()
        id_field = str(feishu_config.get("id_field", "身份证号")).strip()

        if not app_id:
            raise ValueError("飞书 App ID 不能为空。")
        if not app_secret:
            raise ValueError("飞书 App Secret 不能为空。")
        if not app_token:
            raise ValueError("飞书 App Token 不能为空。")
        if not table_id:
            raise ValueError("飞书 Table ID 不能为空。")
        if not id_field:
            raise ValueError("飞书唯一标识字段不能为空。")

    def _get_feishu_tenant_access_token(self, feishu_config: Dict[str, Any]) -> str:
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": str(feishu_config.get("app_id", "")).strip(),
            "app_secret": str(feishu_config.get("app_secret", "")).strip(),
        }
        response = requests.post(token_url, json=payload, timeout=self.timeout)
        if response.status_code != 200:
            raise ValueError(f"飞书鉴权请求失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")

        body = response.json() or {}
        if body.get("code") != 0:
            raise ValueError(f"飞书鉴权失败：code={body.get('code')}, msg={body.get('msg')}")

        tenant_access_token = str(body.get("tenant_access_token", "")).strip()
        if not tenant_access_token:
            raise ValueError("飞书鉴权失败：未获取到 tenant_access_token。")
        return tenant_access_token

    def _query_feishu_record_id_by_member_id(
        self,
        feishu_config: Dict[str, Any],
        tenant_access_token: str,
        member_id_value: str,
    ) -> str:
        id_field = str(feishu_config.get("id_field", "身份证号")).strip()
        escaped_value = member_id_value.replace("\\", "\\\\").replace('"', '\\"')
        filter_expr = f'CurrentValue.[{id_field}] = "{escaped_value}"'
        encoded_filter = quote(filter_expr, safe="")

        app_token = str(feishu_config.get("app_token", "")).strip()
        table_id = str(feishu_config.get("table_id", "")).strip()
        list_url = (
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
            f"?page_size=1&filter={encoded_filter}"
        )

        response = requests.get(
            list_url,
            headers=self._build_bearer_headers(tenant_access_token),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise ValueError(f"飞书查询记录失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")

        body = response.json() or {}
        if body.get("code") != 0:
            raise ValueError(f"飞书查询记录失败：code={body.get('code')}, msg={body.get('msg')}")

        items = ((body.get("data") or {}).get("items") or [])
        if not items:
            return ""
        return str(items[0].get("record_id", "")).strip()

    def _fetch_feishu_record_fields(
        self,
        feishu_cfg: Dict[str, Any],
        access_token: str,
        record_id: str,
    ) -> Dict[str, Any]:
        """读取飞书单条记录的字段（供冲突检查与回填）。"""
        app_token = str(feishu_cfg.get("app_token", "")).strip()
        table_id = str(feishu_cfg.get("table_id", "")).strip()
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
        resp = requests.get(url, headers=self._build_bearer_headers(access_token), timeout=self.timeout)
        if resp.status_code != 200:
            raise ValueError(f"读取飞书现有记录失败（HTTP {resp.status_code}）：{self._extract_response_error(resp)}")
        body = resp.json() or {}
        if body.get("code") != 0:
            raise ValueError(f"读取飞书现有记录失败：code={body.get('code')}, msg={body.get('msg')}")
        return ((body.get("data") or {}).get("record") or {}).get("fields") or {}

    def _test_feishu_connection(self, feishu_cfg: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            token = self._get_feishu_tenant_access_token(feishu_cfg)
            app_token = str(feishu_cfg.get("app_token", "")).strip()
            table_id = str(feishu_cfg.get("table_id", "")).strip()
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=1"
            response = requests.get(url, headers=self._build_bearer_headers(token), timeout=self.timeout)
            if response.status_code != 200:
                return False, f"飞书连接失败（HTTP {response.status_code}）：{self._extract_response_error(response)}"
            body = response.json() or {}
            if body.get("code") != 0:
                return False, f"飞书连接失败：code={body.get('code')}, msg={body.get('msg')}"
            return True, "飞书连接成功。"
        except Exception as exc:
            return False, f"飞书连接失败：{exc}"

    # ======================= 腾讯智能表格 =======================
    # API 文档：https://docs.qq.com/open/document/app/openapi/v2/smartsheet/record/

    def _validate_tencent(self, tencent_config: Dict[str, Any]) -> None:
        client_id = str(tencent_config.get("client_id", "")).strip()
        access_token = str(tencent_config.get("access_token", "")).strip()
        open_id = str(tencent_config.get("open_id", "")).strip()
        file_id = str(tencent_config.get("file_id", "")).strip()
        sheet_id = str(tencent_config.get("sheet_id", "")).strip()
        id_field = str(tencent_config.get("id_field", "身份证号")).strip()

        if not client_id:
            raise ValueError("腾讯 Client ID（应用ID）不能为空。")
        if not access_token:
            raise ValueError("腾讯 Access Token 不能为空。")
        if not open_id:
            raise ValueError("腾讯 Open ID 不能为空。")
        if not file_id:
            raise ValueError("腾讯文档 File ID 不能为空。")
        if not sheet_id:
            raise ValueError("腾讯文档 Sheet ID 不能为空。")
        if not id_field:
            raise ValueError("腾讯文档唯一标识字段不能为空。")

    def _build_tencent_headers(self, tencent_cfg: Dict[str, Any]) -> Dict[str, str]:
        return {
            "Access-Token": str(tencent_cfg.get("access_token", "")).strip(),
            "Client-Id": str(tencent_cfg.get("client_id", "")).strip(),
            "Open-Id": str(tencent_cfg.get("open_id", "")).strip(),
            "Content-Type": "application/json; charset=utf-8",
        }

    def _resolve_tencent_file_id(self, tencent_cfg: Dict[str, Any]) -> str:
        """将用户输入的 encodedID 转换为腾讯文档 API 所需的 fileID。"""
        raw = str(tencent_cfg.get("file_id", "")).strip()
        if not raw:
            return raw
        if "$" in raw:
            return raw  # 已是 fileID，无需转换
        headers = self._build_tencent_headers(tencent_cfg)
        url = f"https://docs.qq.com/openapi/drive/v2/util/converter?type=2&value={raw}"
        response = requests.get(url, headers=headers, timeout=self.timeout)
        if response.status_code != 200:
            raise ValueError(f"腾讯文档 fileID 转换失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")
        resp_data = response.json() or {}
        if resp_data.get("ret") != 0:
            raise ValueError(f"腾讯文档 fileID 转换失败：ret={resp_data.get('ret')}, msg={resp_data.get('msg')}")
        file_id = ((resp_data.get("data") or {})).get("fileID", "")
        if not file_id:
            raise ValueError("腾讯文档 fileID 转换失败：未获取到 fileID。")
        # 将转换后的 fileID 写回配置缓存
        tencent_cfg["file_id"] = str(file_id).strip()
        return str(file_id).strip()

    def _build_tencent_value(self, value: Any) -> Any:
        """将 python 值转换为腾讯 Smartsheet API 的 Value 格式。"""
        if isinstance(value, (int, float)):
            return value  # 数字类型直接传值
        if isinstance(value, bool):
            return value  # 复选框
        # 文本类型包装为 TextValue 数组
        text = str(value)
        return [{"type": "text", "text": text}]

    def _extract_tencent_value(self, value: Any) -> str:
        """从腾讯 Smartsheet API 响应的 Value 格式中提取文本。"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            if not value:
                return ""
            item = value[0]
            if isinstance(item, dict):
                return str(item.get("text", ""))
            return str(item)
        return str(value)

    def _tencent_values_to_plain(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """将腾讯记录 values（text 对象等格式）展平为普通字段字典。"""
        plain: Dict[str, Any] = {}
        for k, v in (values or {}).items():
            text = self._extract_tencent_value(v)
            if text:
                plain[k] = text
        return plain

    def _query_tencent_all_records(
        self,
        tencent_cfg: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        """查询腾讯智能表格中所有记录。"""
        file_id = str(tencent_cfg.get("file_id", "")).strip()
        sheet_id = str(tencent_cfg.get("sheet_id", "")).strip()
        url = f"https://docs.qq.com/openapi/smartbook/v2/files/{file_id}/sheets/{sheet_id}"
        headers = self._build_tencent_headers(tencent_cfg)
        all_records: list[Dict[str, Any]] = []
        offset = 0
        while True:
            body = {"getRecords": {"offset": offset, "limit": 100}}
            response = requests.post(url, headers=headers, json=body, timeout=self.timeout)
            if response.status_code != 200:
                raise ValueError(f"腾讯文档查询记录失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")
            resp_data = response.json() or {}
            if resp_data.get("ret") != 0:
                raise ValueError(f"腾讯文档查询记录失败：ret={resp_data.get('ret')}, msg={resp_data.get('msg')}")
            records_data = (resp_data.get("data") or {}).get("getRecords") or {}
            records = records_data.get("records") or []
            all_records.extend(records)
            if not records_data.get("hasMore"):
                break
            offset += 100
        # 归一化为 (id, 展平字段) 结构，供共享匹配复用
        normalized: list[Dict[str, Any]] = []
        for record in all_records:
            record_id = str(record.get("recordID", "")).strip()
            normalized.append({
                "id": record_id,
                "fields": self._tencent_values_to_plain(record.get("values")),
            })
        return normalized

    def _find_tencent_record_id_by_member_id(
        self,
        tencent_cfg: Dict[str, Any],
        member_id_value: str,
    ) -> str:
        """在全量记录中按成员标识字段值查找记录 ID。"""
        id_field = str(tencent_cfg.get("id_field", "身份证号")).strip()
        records = self._query_tencent_all_records(tencent_cfg)
        return self._match_record_id(records, id_field, member_id_value)

    def _fetch_tencent_record_by_id(
        self,
        tencent_cfg: Dict[str, Any],
        record_id: str,
    ) -> Dict[str, Any]:
        """按 recordID 查询单条记录。"""
        file_id = str(tencent_cfg.get("file_id", "")).strip()
        sheet_id = str(tencent_cfg.get("sheet_id", "")).strip()
        url = f"https://docs.qq.com/openapi/smartbook/v2/files/{file_id}/sheets/{sheet_id}"
        headers = self._build_tencent_headers(tencent_cfg)
        body = {"getRecords": {"recordIDs": [record_id], "limit": 1}}
        response = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        if response.status_code != 200:
            raise ValueError(f"读取腾讯文档记录失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")
        resp_data = response.json() or {}
        if resp_data.get("ret") != 0:
            raise ValueError(f"读取腾讯文档记录失败：ret={resp_data.get('ret')}, msg={resp_data.get('msg')}")
        records = ((resp_data.get("data") or {}).get("getRecords") or {}).get("records") or []
        return records[0] if records else {}

    def _test_tencent_connection(self, tencent_cfg: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            file_id = self._resolve_tencent_file_id(tencent_cfg)
            sheet_id = str(tencent_cfg.get("sheet_id", "")).strip()
            url = f"https://docs.qq.com/openapi/smartbook/v2/files/{file_id}/sheets/{sheet_id}"
            headers = self._build_tencent_headers(tencent_cfg)
            body = {"getRecords": {"offset": 0, "limit": 1}}
            response = requests.post(url, headers=headers, json=body, timeout=self.timeout)
            if response.status_code != 200:
                return False, f"腾讯文档连接失败（HTTP {response.status_code}）：{self._extract_response_error(response)}"
            resp_data = response.json() or {}
            if resp_data.get("ret") != 0:
                return False, f"腾讯文档连接失败：ret={resp_data.get('ret')}, msg={resp_data.get('msg')}"
            return True, "腾讯文档连接成功。"
        except Exception as exc:
            return False, f"腾讯文档连接失败：{exc}"

    # ======================= WPS 多维表格 =======================
    # API 文档：https://open.wps.cn/documents/app-integration-dev/wps365/server/dbsheet/
    # 签名：KSO-1（X-Kso-Date / X-Kso-Authorization）
    # 鉴权：POST https://openapi.wps.cn/oauth2/token（client_credentials 租户 token，2 小时有效）

    _WPS_API_HOST = "https://openapi.wps.cn"
    _WPS_TOKEN_URL = "https://openapi.wps.cn/oauth2/token"

    def _validate_wps(self, wps_config: Dict[str, Any]) -> None:
        app_id = str(wps_config.get("app_id", "")).strip()
        app_secret = str(wps_config.get("app_secret", "")).strip()
        app_token = str(wps_config.get("app_token", "")).strip()
        table_id = str(wps_config.get("table_id", "")).strip()
        id_field = str(wps_config.get("id_field", "身份证号")).strip()

        if not app_id:
            raise ValueError("WPS App ID 不能为空。")
        if not app_secret:
            raise ValueError("WPS App Secret 不能为空。")
        if not app_token:
            raise ValueError("WPS多维表格 App Token（文档ID）不能为空。")
        if not table_id:
            raise ValueError("WPS多维表格 SheetID 不能为空，请填写目标数据表的 SheetID。")
        if not id_field:
            raise ValueError("WPS多维表格唯一标识字段不能为空。")

    def _get_wps_access_token(self, wps_config: Dict[str, Any]) -> str:
        """获取 WPS 租户 access_token（client_credentials，2 小时有效）。"""
        token_url = self._WPS_TOKEN_URL
        payload = {
            "grant_type": "client_credentials",
            "client_id": str(wps_config.get("app_id", "")).strip(),
            "client_secret": str(wps_config.get("app_secret", "")).strip(),
        }
        response = requests.post(token_url, data=payload, timeout=self.timeout)
        if response.status_code != 200:
            raise ValueError(f"WPS鉴权请求失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")

        body = response.json() or {}
        access_token = str(body.get("access_token", "")).strip()
        if not access_token:
            raise ValueError(f"WPS鉴权失败：未获取到 access_token（{body}）。")
        return access_token

    def _build_wps_headers(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
        method: str,
        uri: str,
        body_bytes: bytes = b"",
    ) -> Dict[str, str]:
        """构建 WPS KSO-1 签名请求头。

        X-Kso-Authorization = "KSO-1 {accessKey}:{signature}"
        signature = HMAC-SHA256(secretKey, "KSO-1" + Method + RequestURI + ContentType + KsoDate + sha256(RequestBody))
        """
        access_key = str(wps_config.get("app_id", "")).strip()
        secret_key = str(wps_config.get("app_secret", "")).strip()
        content_type = "application/json"
        kso_date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())

        sha256_hex = ""
        if body_bytes:
            sha256_hex = hashlib.sha256(body_bytes).hexdigest()

        data_to_sign = ("KSO-1" + method + uri + content_type + kso_date + sha256_hex).encode("utf-8")
        signature = hmac.new(secret_key.encode("utf-8"), data_to_sign, hashlib.sha256).hexdigest()
        authorization = f"KSO-1 {access_key}:{signature}"

        return {
            "Content-Type": content_type,
            "X-Kso-Date": kso_date,
            "X-Kso-Authorization": authorization,
            "Authorization": f"Bearer {access_token}",
        }

    def _wps_request(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
        method: str,
        uri: str,
        payload: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """发送 KSO-1 签名的请求并解析响应（code 非 0 抛异常，返回 data）。"""
        body_bytes = b""
        if payload is not None:
            body_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = self._build_wps_headers(wps_config, access_token, method, uri, body_bytes)
        url = self._WPS_API_HOST + uri
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=self.timeout)
        else:
            response = requests.post(url, headers=headers, data=body_bytes, timeout=self.timeout)
        if response.status_code != 200:
            raise ValueError(f"WPS接口请求失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")
        resp_body = response.json() or {}
        if resp_body.get("code") != 0:
            raise ValueError(f"WPS接口请求失败：code={resp_body.get('code')}, msg={resp_body.get('msg')}")
        return resp_body.get("data") or {}

    def _query_wps_schema(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
    ) -> list[Dict[str, Any]]:
        """获取 WPS 多维表格 Schema（数据表列表）。"""
        file_id = str(wps_config.get("app_token", "")).strip()
        uri = f"/v7/coop/dbsheet/{file_id}/schema"
        data = self._wps_request(wps_config, access_token, "GET", uri)
        return data.get("sheets") or []

    def _resolve_wps_sheet_id(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
    ) -> str:
        """解析数据表 id：WPSSheetID 必填，直接返回配置值。

        不自动选取第一个数据表，避免同步到错误的数据表造成业务错误。
        """
        table_id = str(wps_config.get("table_id", "")).strip()
        if not table_id:
            raise ValueError("WPS多维表格 SheetID 不能为空，请在管理员配置中填写目标数据表的 SheetID。")
        return table_id

    def _parse_wps_fields(self, fields: Any) -> Dict[str, Any]:
        """解析 WPS 返回的 fields（JSON 字符串或 dict）。"""
        if isinstance(fields, dict):
            return fields
        if isinstance(fields, str):
            try:
                parsed = json.loads(fields)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _query_wps_all_records(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
    ) -> list[Dict[str, Any]]:
        """查询 WPS 多维表格中所有记录（list_by_page 分页拉取）。"""
        file_id = str(wps_config.get("app_token", "")).strip()
        sheet_id = self._resolve_wps_sheet_id(wps_config, access_token)
        uri = f"/v7/coop/dbsheet/{file_id}/sheets/{sheet_id}/records/list_by_page"
        all_records: list[Dict[str, Any]] = []
        page_num = 1
        page_size = 200

        while True:
            payload = {
                "prefer_id": False,
                "text_value": "text",
                "page_num": page_num,
                "page_size": page_size,
            }
            data = self._wps_request(wps_config, access_token, "POST", uri, payload)
            records = data.get("records") or []
            for rec in records:
                all_records.append({
                    "id": str(rec.get("id", "")).strip(),
                    "fields": self._parse_wps_fields(rec.get("fields")),
                })
            if len(records) < page_size:
                break
            page_num += 1

        return all_records

    def _fetch_wps_record_by_id(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
        record_id: str,
    ) -> Dict[str, Any]:
        """按 record_id 查询 WPS 多维表格单条记录（返回字段字典）。"""
        file_id = str(wps_config.get("app_token", "")).strip()
        sheet_id = self._resolve_wps_sheet_id(wps_config, access_token)
        uri = f"/v7/coop/dbsheet/{file_id}/sheets/{sheet_id}/records/{record_id}?text_value=text"
        data = self._wps_request(wps_config, access_token, "GET", uri)
        record = data.get("record") or {}
        return self._parse_wps_fields(record.get("fields"))

    def _query_wps_record_id_by_member_id(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
        member_id_value: str,
    ) -> str:
        id_field = str(wps_config.get("id_field", "身份证号")).strip()
        rows = self._query_wps_all_records(wps_config, access_token)
        return self._match_record_id(rows, id_field, member_id_value)

    def _test_wps_connection(self, wps_cfg: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            token = self._get_wps_access_token(wps_cfg)
            sheets = self._query_wps_schema(wps_cfg, token)
            sheet_id = self._resolve_wps_sheet_id(wps_cfg, token)
            return True, f"WPS多维表格连接成功（文档共 {len(sheets)} 个数据表，当前使用数据表 id={sheet_id}）。"
        except Exception as exc:
            return False, f"WPS连接失败：{exc}"

    # ======================= 平台原语调度与共享同步流程 =======================

    def _validate_provider(self, provider: str, provider_cfg: Dict[str, Any]) -> None:
        """校验平台连接配置。"""
        if provider == "飞书":
            self._validate_feishu(provider_cfg)
        elif provider == "腾讯":
            self._validate_tencent(provider_cfg)
        elif provider == "WPS":
            self._validate_wps(provider_cfg)
        else:
            raise ValueError(f"不支持的同步平台：{provider}。请选择 飞书、腾讯 或 WPS。")

    def _get_provider_access_token(self, provider: str, provider_cfg: Dict[str, Any]) -> str:
        """获取平台访问凭证（腾讯无需 token，返回空串）。"""
        if provider == "飞书":
            return self._get_feishu_tenant_access_token(provider_cfg)
        if provider == "WPS":
            return self._get_wps_access_token(provider_cfg)
        return ""

    def _find_record_id(
        self,
        provider: str,
        provider_cfg: Dict[str, Any],
        member_id_value: str,
        access_token: str,
    ) -> str:
        """按成员唯一标识在平台中定位记录 id。"""
        if provider == "飞书":
            return self._query_feishu_record_id_by_member_id(provider_cfg, access_token, member_id_value)
        if provider == "腾讯":
            self._resolve_tencent_file_id(provider_cfg)
            return self._find_tencent_record_id_by_member_id(provider_cfg, member_id_value)
        if provider == "WPS":
            return self._query_wps_record_id_by_member_id(provider_cfg, access_token, member_id_value)
        return ""

    def _fetch_record_fields(
        self,
        provider: str,
        provider_cfg: Dict[str, Any],
        record_id: str,
        access_token: str,
    ) -> Dict[str, Any]:
        """读取平台中单条记录的字段（展平为普通 dict）。"""
        if provider == "飞书":
            return self._fetch_feishu_record_fields(provider_cfg, access_token, record_id)
        if provider == "腾讯":
            existing_record = self._fetch_tencent_record_by_id(provider_cfg, record_id)
            return self._tencent_values_to_plain(existing_record.get("values"))
        if provider == "WPS":
            return self._fetch_wps_record_by_id(provider_cfg, access_token, record_id)
        return {}

    def _assert_feishu_ok(self, response: requests.Response, action_desc: str) -> None:
        """校验飞书接口响应，失败抛出 ValueError。"""
        if response.status_code != 200:
            raise ValueError(f"{action_desc}（HTTP {response.status_code}）：{self._extract_response_error(response)}")
        body = response.json() or {}
        if body.get("code") != 0:
            raise ValueError(f"{action_desc}：code={body.get('code')}, msg={body.get('msg')}")

    def _assert_tencent_ok(self, response: requests.Response, action_desc: str) -> None:
        """校验腾讯接口响应，失败抛出 ValueError。"""
        if response.status_code != 200:
            raise ValueError(f"{action_desc}（HTTP {response.status_code}）：{self._extract_response_error(response)}")
        body = response.json() or {}
        if body.get("ret") != 0:
            raise ValueError(f"{action_desc}：ret={body.get('ret')}, msg={body.get('msg')}")

    def _create_record(
        self,
        provider: str,
        provider_cfg: Dict[str, Any],
        fields_payload: Dict[str, Any],
        access_token: str,
    ) -> None:
        """在平台中新建一条记录。"""
        if provider == "飞书":
            app_token = str(provider_cfg.get("app_token", "")).strip()
            table_id = str(provider_cfg.get("table_id", "")).strip()
            base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
            resp = requests.post(base_url, headers=self._build_bearer_headers(access_token),
                                 json={"fields": fields_payload}, timeout=self.timeout)
            self._assert_feishu_ok(resp, "飞书新建记录失败")
        elif provider == "腾讯":
            file_id = str(provider_cfg.get("file_id", "")).strip()
            sheet_id = str(provider_cfg.get("sheet_id", "")).strip()
            api_url = f"https://docs.qq.com/openapi/smartbook/v2/files/{file_id}/sheets/{sheet_id}"
            resp = requests.post(api_url, headers=self._build_tencent_headers(provider_cfg),
                                 json={"addRecords": {"records": [{"values": fields_payload}]}}, timeout=self.timeout)
            self._assert_tencent_ok(resp, "腾讯文档新建记录失败")
        elif provider == "WPS":
            file_id = str(provider_cfg.get("app_token", "")).strip()
            sheet_id = self._resolve_wps_sheet_id(provider_cfg, access_token)
            uri = f"/v7/coop/dbsheet/{file_id}/sheets/{sheet_id}/records/create"
            fields_value = json.dumps(fields_payload, ensure_ascii=False, separators=(",", ":"))
            self._wps_request(provider_cfg, access_token, "POST", uri,
                              {"prefer_id": False, "records": [{"fields_value": fields_value}]})

    def _update_record(
        self,
        provider: str,
        provider_cfg: Dict[str, Any],
        record_id: str,
        fields_payload: Dict[str, Any],
        access_token: str,
    ) -> None:
        """更新平台中一条已有记录。"""
        if provider == "飞书":
            app_token = str(provider_cfg.get("app_token", "")).strip()
            table_id = str(provider_cfg.get("table_id", "")).strip()
            base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
            resp = requests.put(f"{base_url}/{record_id}", headers=self._build_bearer_headers(access_token),
                                json={"fields": fields_payload}, timeout=self.timeout)
            self._assert_feishu_ok(resp, "飞书更新记录失败")
        elif provider == "腾讯":
            file_id = str(provider_cfg.get("file_id", "")).strip()
            sheet_id = str(provider_cfg.get("sheet_id", "")).strip()
            api_url = f"https://docs.qq.com/openapi/smartbook/v2/files/{file_id}/sheets/{sheet_id}"
            resp = requests.post(api_url, headers=self._build_tencent_headers(provider_cfg),
                                 json={"updateRecords": {"records": [{"recordID": record_id, "values": fields_payload}]}}, timeout=self.timeout)
            self._assert_tencent_ok(resp, "腾讯文档更新记录失败")
        elif provider == "WPS":
            file_id = str(provider_cfg.get("app_token", "")).strip()
            sheet_id = self._resolve_wps_sheet_id(provider_cfg, access_token)
            uri = f"/v7/coop/dbsheet/{file_id}/sheets/{sheet_id}/records/update"
            fields_value = json.dumps(fields_payload, ensure_ascii=False, separators=(",", ":"))
            self._wps_request(provider_cfg, access_token, "POST", uri,
                              {"records": [{"id": record_id, "fields_value": fields_value}]})

    def _sync_feishu_basic_data(
        self,
        basic_data: Dict[str, Any],
        provider_cfg: Dict[str, Any],
        record_id: str,
        access_token: str,
        fields_payload: Dict[str, Any],
        force_backfill_fields: set[str] | None,
        allowed_keys: set[str] | None,
        previous_remote_values: Dict[str, Any] | None,
    ) -> BasicInfoSyncResult:
        """飞书非空值优先；仅补填远程空值，写入后重新读取以确认只读字段。"""
        provider = "飞书"
        existing_fields = (
            self._fetch_record_fields(provider, provider_cfg, record_id, access_token)
            if record_id else {}
        )
        previous_values = previous_remote_values or {}
        if record_id:
            fields_payload = {
                key: value for key, value in fields_payload.items()
                if self._is_missing_local_value(existing_fields.get(key))
                # 管理员清空此前受管字段时，不把本地缓存的旧值重新上传。
                and key not in previous_values
            }
            if fields_payload:
                self._update_record(provider, provider_cfg, record_id, fields_payload, access_token)
        else:
            self._create_record(provider, provider_cfg, fields_payload, access_token)
            id_field = str(provider_cfg.get("id_field", "身份证号")).strip()
            record_id = self._find_record_id(
                provider, provider_cfg, str(basic_data[id_field]).strip(), access_token,
            )
            if not record_id:
                raise ValueError("信息已上传，但未能重新读取飞书记录，请重试同步。")

        if fields_payload:
            existing_fields = self._fetch_record_fields(provider, provider_cfg, record_id, access_token)

        known_keys = set(existing_fields) | set(basic_data) if allowed_keys is None else set(allowed_keys)
        known_keys.update(force_backfill_fields or set())
        known_keys.add(str(provider_cfg.get("id_field", "身份证号")).strip())
        remote_values = {
            key: value for key, value in existing_fields.items()
            if key in known_keys and self._is_non_empty_remote_value(value)
        }
        merged_data = dict(basic_data)
        # 同步管理员的清空操作，同时释放该字段的本地编辑权限。
        for key in (set(previous_values) | set(fields_payload)) & known_keys:
            if key not in remote_values:
                merged_data[key] = ""
        merged_data.update(remote_values)
        changed_keys = sorted(key for key, value in merged_data.items() if basic_data.get(key) != value)
        message = "成员信息已同步，飞书已有值的字段以飞书为准并设为只读。"
        if changed_keys:
            message += f" 已回填 {len(changed_keys)} 个字段到本地：{', '.join(changed_keys)}。"
        return True, message, self._PROVIDER_DISPLAY_NAMES[provider], merged_data, remote_values

    def _upsert_member_basic_data(
        self,
        provider: str,
        display_name: str,
        basic_data: Dict[str, Any],
        provider_cfg: Dict[str, Any],
        force_update_fields: set[str] | None = None,
        force_backfill_fields: set[str] | None = None,
        allowed_keys: set[str] | None = None,
        previous_remote_values: Dict[str, Any] | None = None,
    ) -> BasicInfoSyncResult:
        """按成员唯一标识 upsert 到指定平台（三平台共享的同步流程）。"""
        id_field = str(provider_cfg.get("id_field", "身份证号")).strip()

        member_id_value = str((basic_data or {}).get(id_field, "")).strip()
        if not member_id_value:
            return False, f"成员基本信息缺少唯一标识字段：{id_field}。", display_name, dict(basic_data or {}), {}

        fields_payload = self._build_platform_fields(provider, basic_data, force_backfill_fields)
        if not fields_payload:
            return False, "没有可同步的成员字段。", display_name, dict(basic_data or {}), {}

        try:
            access_token = self._get_provider_access_token(provider, provider_cfg)
            record_id = self._find_record_id(provider, provider_cfg, member_id_value, access_token)

            if provider == "飞书":
                return self._sync_feishu_basic_data(
                    basic_data, provider_cfg, record_id, access_token, fields_payload,
                    force_backfill_fields, allowed_keys, previous_remote_values,
                )

            if record_id:
                # 读取现有记录字段，做冲突检查与回填
                existing_fields = self._fetch_record_fields(provider, provider_cfg, record_id, access_token)

                force_fields = force_update_fields or set()
                for key in fields_payload:
                    if key in force_fields:
                        continue  # 强制更新字段跳过冲突检查（如填写进度）
                    if key in existing_fields:
                        if self._values_conflict(existing_fields.get(key), basic_data.get(key)):
                            return False, f"字段 '{key}' 在{display_name}已有不同值（{existing_fields.get(key)}），禁止覆盖。", display_name, dict(basic_data or {}), {}

                merged_basic_data, backfilled_count, backfilled_keys = self._backfill_local_missing_from_remote(
                    basic_data,
                    existing_fields,
                    force_backfill_fields=force_backfill_fields,
                    allowed_keys=allowed_keys,
                )

                self._update_record(provider, provider_cfg, record_id, fields_payload, access_token)

                success_message = f"成员信息已同步并更新{display_name}记录。"
                if backfilled_count > 0:
                    success_message = f"{success_message} 已回填 {backfilled_count} 个字段到本地，回填的字段为：{', '.join(backfilled_keys)}。"
                return True, success_message, display_name, merged_basic_data, {}

            self._create_record(provider, provider_cfg, fields_payload, access_token)
            return True, f"成员信息已同步并写入{display_name}记录。", display_name, dict(basic_data or {}), {}
        except Exception as exc:
            return False, f"{display_name}同步失败：{exc}", display_name, dict(basic_data or {}), {}

    # ======================= 通用公开接口 =======================

    def upload_member_basic_data_with_config(
        self,
        basic_data: Dict[str, Any],
        provider: str,
        provider_cfg: Dict[str, Any],
        force_update_fields: set[str] | None = None,
        force_backfill_fields: set[str] | None = None,
        allowed_keys: set[str] | None = None,
        previous_remote_values: Dict[str, Any] | None = None,
    ) -> BasicInfoSyncResult:
        """根据 provider 自动路由到对应的同步实现。

        Args:
            basic_data: 成员基础信息字典
            provider: 平台标识（"飞书" / "腾讯" / "WPS"）
            provider_cfg: 该平台的连接配置字典
            force_update_fields: 强制更新字段集合
            force_backfill_fields: 强制回填字段集合
            allowed_keys: 允许回填的字段键白名单（None 表示不限制）；仅回填这些字段，忽略远程独有列
            previous_remote_values: 上次飞书确认的受管字段，用于识别管理员清空操作

        Returns:
            (success, message, target, merged_data, remote_readonly_values)
        """
        self._validate_provider(provider, provider_cfg)
        display_name = self._PROVIDER_DISPLAY_NAMES.get(provider, provider)
        return self._upsert_member_basic_data(
            provider,
            display_name,
            basic_data,
            provider_cfg,
            force_update_fields=force_update_fields,
            force_backfill_fields=force_backfill_fields,
            allowed_keys=allowed_keys,
            previous_remote_values=previous_remote_values,
        )

    def test_connection_with_config(self, provider: str, provider_cfg: Dict[str, Any]) -> Tuple[bool, str]:
        """根据 provider 测试对应平台的连接。

        Args:
            provider: 平台标识（"飞书" / "腾讯" / "WPS"）
            provider_cfg: 该平台的连接配置字典

        Returns:
            (success, message)
        """
        self._validate_provider(provider, provider_cfg)
        if provider == "飞书":
            return self._test_feishu_connection(provider_cfg)
        elif provider == "腾讯":
            return self._test_tencent_connection(provider_cfg)
        elif provider == "WPS":
            return self._test_wps_connection(provider_cfg)
        else:
            raise ValueError(f"不支持的同步平台：{provider}。请选择 飞书、腾讯 或 WPS。")

    # ======================= 材料审核（成员 → 材料审核表） =======================
    # 契约（列名 / 状态取值）见 src/persistence/review_table_fields.py；
    # 管理员建表步骤见 docs/sync_guide.md（「4、新建材料审核表」）
    #
    # 设计要点：
    # - 一行 = 一个「成员 × 材料」，主键 = (唯一标识字段值, 材料标识)；
    # - 重复提交**更新同一行**，并把「审核状态」重置为待审核、「审核意见」置空（R3）；
    # - 材料审核表与基本信息表**共用同一套凭据**，仅表/Sheet 标识不同，
    #   因此全部复用既有平台原语（_create_record / _update_record / _get_provider_access_token ...）。

    def build_review_provider_config(
        self,
        provider: str,
        provider_cfg: Dict[str, Any],
    ) -> Dict[str, Any]:
        """把「基本信息表」的连接配置衍生为「材料审核表」的连接配置。

        两张表共用凭据（App ID/Secret、FileID 等），仅目标表/Sheet 不同：
        把表标识替换为 `review_table_id`（由「双端交互」分组的材料审核表 ID 字段提供）。

        Raises:
            ValueError: 未配置材料审核表 ID。
        """
        review_cfg = dict(provider_cfg or {})
        review_table_id = str(review_cfg.get("review_table_id", "") or "").strip()
        if not review_table_id:
            raise ValueError(
                "未配置材料审核表 ID，请先在「双端交互」分组填写当前平台对应的材料审核表 ID。"
            )
        if provider == "腾讯":
            review_cfg["sheet_id"] = review_table_id
        else:
            review_cfg["table_id"] = review_table_id
        return review_cfg

    # ----------------------- 平台原语：按成员列出多条记录 -----------------------

    def _filter_records_by_member_id(
        self,
        records: list[Dict[str, Any]],
        provider_cfg: Dict[str, Any],
        member_id_value: str,
    ) -> list[Dict[str, Any]]:
        """在已拉取的记录中按唯一标识字段筛出某成员的全部记录。"""
        id_field = str(provider_cfg.get("id_field", ID_FIELD_DEFAULT)).strip()
        target = str(member_id_value or "").strip()
        if not target:
            return []
        return [
            row for row in (records or [])
            if str((row.get("fields") or {}).get(id_field, "")).strip() == target
        ]

    def _query_feishu_records_by_member_id(
        self,
        feishu_config: Dict[str, Any],
        tenant_access_token: str,
        member_id_value: str,
    ) -> list[Dict[str, Any]]:
        """按唯一标识字段过滤，列出飞书多维表格中该成员的全部记录（分页拉全）。"""
        id_field = str(feishu_config.get("id_field", ID_FIELD_DEFAULT)).strip()
        escaped = str(member_id_value or "").replace("\\", "\\\\").replace('"', '\\"')
        encoded_filter = quote(f'CurrentValue.[{id_field}] = "{escaped}"', safe="")

        app_token = str(feishu_config.get("app_token", "")).strip()
        table_id = str(feishu_config.get("table_id", "")).strip()
        base_url = (
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
            f"?page_size=200&filter={encoded_filter}"
        )

        results: list[Dict[str, Any]] = []
        page_token = ""
        while True:
            url = base_url if not page_token else f"{base_url}&page_token={quote(page_token, safe='')}"
            response = requests.get(
                url, headers=self._build_bearer_headers(tenant_access_token), timeout=self.timeout,
            )
            self._assert_feishu_ok(response, "飞书查询记录失败")
            data = (response.json() or {}).get("data") or {}
            for item in data.get("items") or []:
                results.append({
                    "id": str(item.get("record_id", "")).strip(),
                    "fields": item.get("fields") or {},
                })
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token") or "").strip()
            if not page_token:
                break
        return results

    def _query_records_by_member_id(
        self,
        provider: str,
        provider_cfg: Dict[str, Any],
        member_id_value: str,
        access_token: str,
    ) -> list[Dict[str, Any]]:
        """列出某成员在目标表中的全部记录（元素为 {"id", "fields"}）。

        飞书：下推过滤条件到平台；腾讯 / WPS：拉取后本地过滤
        （两家当前未使用按字段过滤的查询接口，与既有成员信息同步一致）。
        """
        if provider == "飞书":
            return self._query_feishu_records_by_member_id(provider_cfg, access_token, member_id_value)
        if provider == "腾讯":
            self._resolve_tencent_file_id(provider_cfg)
            return self._filter_records_by_member_id(
                self._query_tencent_all_records(provider_cfg), provider_cfg, member_id_value,
            )
        if provider == "WPS":
            return self._filter_records_by_member_id(
                self._query_wps_all_records(provider_cfg, access_token), provider_cfg, member_id_value,
            )
        return []

    def _match_record_id_by_keys(
        self,
        records: list[Dict[str, Any]],
        keys: Dict[str, Any],
    ) -> str:
        """在记录列表中按**多个字段等值**匹配记录 id（全部字段相等才算命中）。"""
        normalized = {
            str(key).strip(): str(value).strip()
            for key, value in (keys or {}).items()
            if str(key).strip()
        }
        if not normalized:
            return ""
        for row in records or []:
            fields = row.get("fields") or {}
            if all(str(fields.get(key, "")).strip() == value for key, value in normalized.items()):
                return str(row.get("id", "")).strip()
        return ""

    def _find_record_id_by_keys(
        self,
        provider: str,
        provider_cfg: Dict[str, Any],
        member_id_value: str,
        keys: Dict[str, Any],
        access_token: str,
    ) -> str:
        """按多个字段定位审核行的记录 id（未命中返回空串）。"""
        records = self._query_records_by_member_id(
            provider, provider_cfg, member_id_value, access_token,
        )
        return self._match_record_id_by_keys(records, keys)

    # ----------------------- 公开接口：提交 / 拉取 / 测试 -----------------------

    def _build_review_fields_payload(
        self,
        provider: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """组装审核行的字段载荷。

        先按平台包装常规字段（跳过空值），再**强制写入**「审核状态＝待审核」
        与「审核意见＝空」：后者必须显式写入，否则重新提交时旧意见不会被清空（R3）。
        """
        fields = self._build_platform_fields(provider, payload)
        if provider == "飞书":
            wrap = self._feishu_wrap_value
        elif provider == "腾讯":
            wrap = self._build_tencent_value
        else:
            wrap = self._wps_wrap_value
        fields[COL_STATUS] = wrap(REVIEW_STATUS_PENDING)
        fields[COL_COMMENT] = wrap("")
        return fields

    def upload_review_submission(
        self,
        payload: Dict[str, Any],
        provider: str,
        provider_cfg: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """把一份材料的待填项提交到材料审核表（按 (唯一标识, 材料标识) upsert）。

        Args:
            payload: 该行的字段值。键为 review_table_fields 的列名常量、
                以及管理员配置的唯一标识字段名。应包含：唯一标识、姓名、
                材料、阶段、提交内容、提交时间、提交次数。
                「审核状态」「审核意见」由本方法强制写入，调用方无需提供。
            provider: 平台标识（"飞书" / "腾讯" / "WPS"）。
            provider_cfg: **基本信息表**的连接配置（内部自动衍生为材料审核表配置）。

        Returns:
            (success, message)

        Note:
            不做字段冲突检查：审核行归成员自己所有，重新提交就是覆盖自己的行。
        """
        display_name = self._PROVIDER_DISPLAY_NAMES.get(provider, provider)
        try:
            review_cfg = self.build_review_provider_config(provider, provider_cfg)
            self._validate_provider(provider, review_cfg)
        except ValueError as exc:
            return False, str(exc)

        id_field = str(review_cfg.get("id_field", ID_FIELD_DEFAULT)).strip()
        member_id_value = str((payload or {}).get(id_field, "") or "").strip()
        if not member_id_value:
            return False, f"提交内容缺少唯一标识字段：{id_field}。"
        template_key = str((payload or {}).get(COL_TEMPLATE_ID, "") or "").strip()
        if not template_key:
            return False, f"提交内容缺少「{COL_TEMPLATE_ID}」。"

        try:
            access_token = self._get_provider_access_token(provider, review_cfg)
            record_id = self._find_record_id_by_keys(
                provider,
                review_cfg,
                member_id_value,
                {id_field: member_id_value, COL_TEMPLATE_ID: template_key},
                access_token,
            )
            fields_payload = self._build_review_fields_payload(provider, payload)
            if record_id:
                self._update_record(provider, review_cfg, record_id, fields_payload, access_token)
                return True, f"该材料已重新提交并更新{display_name}记录。"
            self._create_record(provider, review_cfg, fields_payload, access_token)
            return True, f"该材料已提交审核并写入{display_name}记录。"
        except Exception as exc:
            return False, f"{display_name}提交失败：{exc}"

    def fetch_review_results(
        self,
        provider: str,
        provider_cfg: Dict[str, Any],
        member_id_value: str,
    ) -> Tuple[bool, str, Dict[str, Dict[str, Any]]]:
        """拉取某成员在材料审核表中的全部审核结果。

        Returns:
            (success, message, {材料标识: {"status", "comment"}})
            `status` 已经 normalize_review_status 归一化；无明确结论时为「待审核」。

        Note:
            同一材料若存在多条记录（理论上不应发生），优先保留已给出结论的一条。
        """
        display_name = self._PROVIDER_DISPLAY_NAMES.get(provider, provider)
        try:
            review_cfg = self.build_review_provider_config(provider, provider_cfg)
            self._validate_provider(provider, review_cfg)
        except ValueError as exc:
            return False, str(exc), {}

        target = str(member_id_value or "").strip()
        if not target:
            return False, "缺少成员唯一标识，无法拉取审核结果。", {}

        try:
            access_token = self._get_provider_access_token(provider, review_cfg)
            rows = self._query_records_by_member_id(provider, review_cfg, target, access_token)
            results: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                fields = row.get("fields") or {}
                template_key = str(fields.get(COL_TEMPLATE_ID, "") or "").strip()
                if not template_key:
                    continue
                previous = results.get(template_key)
                if previous is not None and previous.get("status") != REVIEW_STATUS_PENDING:
                    continue   # 已有明确结论，保留先出现的那条
                results[template_key] = {
                    "status": normalize_review_status(fields.get(COL_STATUS)),
                    "comment": str(fields.get(COL_COMMENT, "") or "").strip(),
                }
            return True, f"已从{display_name}拉取 {len(results)} 份材料的审核结果。", results
        except Exception as exc:
            return False, f"{display_name}拉取审核结果失败：{exc}", {}

    def _query_feishu_field_names(
        self,
        feishu_cfg: Dict[str, Any],
        access_token: str,
    ) -> list[str]:
        """读取飞书多维表格的列名（用于材料审核表列完整性校验）。"""
        app_token = str(feishu_cfg.get("app_token", "")).strip()
        table_id = str(feishu_cfg.get("table_id", "")).strip()
        base_url = (
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}"
            f"/fields?page_size=100"
        )
        names: list[str] = []
        page_token = ""
        while True:
            url = base_url if not page_token else f"{base_url}&page_token={quote(page_token, safe='')}"
            response = requests.get(
                url, headers=self._build_bearer_headers(access_token), timeout=self.timeout,
            )
            self._assert_feishu_ok(response, "读取飞书表格列失败")
            data = (response.json() or {}).get("data") or {}
            for item in data.get("items") or []:
                name = str(item.get("field_name", "") or "").strip()
                if name:
                    names.append(name)
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token") or "").strip()
            if not page_token:
                break
        return names

    @staticmethod
    def _missing_columns(available: list[str], expected) -> list[str]:
        """返回 expected 中不存在于 available 的列名（保持 expected 的顺序）。"""
        have = {str(name or "").strip() for name in (available or [])}
        return [str(col) for col in (expected or ()) if str(col).strip() not in have]

    def test_review_connection_with_config(
        self,
        provider: str,
        provider_cfg: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """测试材料审核表的可访问性（飞书额外校验列完整性）。

        Args:
            provider_cfg: **基本信息表**的连接配置（内部自动衍生为材料审核表配置）。

        Note:
            飞书多维表格提供字段列表接口，可校验全部必需列是否存在；
            腾讯智能表格 / WPS 多维表格当前未接入其字段结构接口，
            只验证可访问性 —— 列名是否正确会在首次提交时由平台报错暴露。
        """
        try:
            review_cfg = self.build_review_provider_config(provider, provider_cfg)
            self._validate_provider(provider, review_cfg)
        except ValueError as exc:
            return False, str(exc)

        try:
            access_token = self._get_provider_access_token(provider, review_cfg)
            expected = review_column_names(review_cfg.get("id_field", ID_FIELD_DEFAULT))

            if provider == "飞书":
                missing = self._missing_columns(
                    self._query_feishu_field_names(review_cfg, access_token), expected,
                )
                if missing:
                    return False, (
                        f"飞书材料审核表可访问，但缺少必需列：{'、'.join(missing)}。"
                        f"请参照 docs/sync_guide.md 创建这些列。"
                    )
                return True, f"飞书材料审核表连接成功，必需列齐全（共 {len(expected)} 列）。"

            if provider == "腾讯":
                file_id = self._resolve_tencent_file_id(review_cfg)
                sheet_id = str(review_cfg.get("sheet_id", "")).strip()
                url = f"https://docs.qq.com/openapi/smartbook/v2/files/{file_id}/sheets/{sheet_id}"
                resp = requests.post(
                    url,
                    headers=self._build_tencent_headers(review_cfg),
                    json={"getRecords": {"offset": 0, "limit": 1}},
                    timeout=self.timeout,
                )
                self._assert_tencent_ok(resp, "腾讯材料审核表访问失败")
                return True, (
                    "腾讯材料审核表连接成功。注意：腾讯智能表格暂无法校验列名，"
                    f"请核对是否已按 docs/sync_guide.md 创建 {len(expected)} 个必需列。"
                )

            if provider == "WPS":
                file_id = str(review_cfg.get("app_token", "")).strip()
                sheet_id = self._resolve_wps_sheet_id(review_cfg, access_token)
                uri = f"/v7/coop/dbsheet/{file_id}/sheets/{sheet_id}/records/list_by_page"
                self._wps_request(
                    review_cfg, access_token, "POST", uri,
                    {"prefer_id": False, "text_value": "text", "page_num": 1, "page_size": 1},
                )
                return True, (
                    "WPS材料审核表连接成功。注意：WPS多维表格暂无法校验列名，"
                    f"请核对是否已按 docs/sync_guide.md 创建 {len(expected)} 个必需列。"
                )

            return False, f"不支持的同步平台：{provider}。请选择 飞书、腾讯 或 WPS。"
        except Exception as exc:
            return False, f"材料审核表连接失败：{exc}"
