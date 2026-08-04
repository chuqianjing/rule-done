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


class InfoSyncManager(SyncManagerBase):
    """成员信息同步管理器。"""

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
        """通用字段构建：过滤空值与强制回填字段后，对每个值调用 wrap_value 包装。"""
        fields_payload: Dict[str, Any] = {}
        for local_key, value in basic_data.items():
            if value in (None, "", "    年  月  日"):
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
        """
        existing_val: 远程平台中已有的值
        new_val: 待上传的值
        """
        if existing_val is None or existing_val == "" or existing_val == "无" or existing_val == "    年  月  日":
            return False
        if new_val is None or new_val == "" or new_val == "无" or new_val == "    年  月  日":
            return False
        try:
            if existing_val == new_val:
                return False
            return str(existing_val) != str(new_val)
        except Exception:
            return str(existing_val) != str(new_val)

    def _is_missing_local_value(self, value: Any) -> bool:
        """
        判断本地字段值是否为空
        """
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == "" or value.strip() == "无" or value == "    年  月  日"
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) == 0
        return False

    def _is_non_empty_remote_value(self, value: Any) -> bool:
        """
        判断远程平台字段值是否为非空值
        """
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != "" and value.strip() != "无" and value != "    年  月  日"
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) > 0
        return True

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

    def _upsert_member_basic_data(
        self,
        provider: str,
        display_name: str,
        basic_data: Dict[str, Any],
        provider_cfg: Dict[str, Any],
        force_update_fields: set[str] | None = None,
        force_backfill_fields: set[str] | None = None,
        allowed_keys: set[str] | None = None,
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """按成员唯一标识 upsert 到指定平台（三平台共享的同步流程）。"""
        id_field = str(provider_cfg.get("id_field", "身份证号")).strip()

        member_id_value = str((basic_data or {}).get(id_field, "")).strip()
        if not member_id_value:
            return False, f"成员基本信息缺少唯一标识字段：{id_field}。", display_name, dict(basic_data or {})

        fields_payload = self._build_platform_fields(provider, basic_data, force_backfill_fields)
        if not fields_payload:
            return False, "没有可同步的成员字段。", display_name, dict(basic_data or {})

        try:
            access_token = self._get_provider_access_token(provider, provider_cfg)
            record_id = self._find_record_id(provider, provider_cfg, member_id_value, access_token)

            if record_id:
                # 读取现有记录字段，做冲突检查与回填
                existing_fields = self._fetch_record_fields(provider, provider_cfg, record_id, access_token)

                force_fields = force_update_fields or set()
                for key in fields_payload:
                    if key in force_fields:
                        continue  # 强制更新字段跳过冲突检查（如填写进度）
                    if key in existing_fields:
                        if self._values_conflict(existing_fields.get(key), basic_data.get(key)):
                            return False, f"字段 '{key}' 在{display_name}已有不同值（{existing_fields.get(key)}），禁止覆盖。", display_name, dict(basic_data or {})

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
                return True, success_message, display_name, merged_basic_data

            self._create_record(provider, provider_cfg, fields_payload, access_token)
            return True, f"成员信息已同步并写入{display_name}记录。", display_name, dict(basic_data or {})
        except Exception as exc:
            return False, f"{display_name}同步失败：{exc}", display_name, dict(basic_data or {})

    # ======================= 通用公开接口 =======================

    def upload_member_basic_data_with_config(
        self,
        basic_data: Dict[str, Any],
        provider: str,
        provider_cfg: Dict[str, Any],
        force_update_fields: set[str] | None = None,
        force_backfill_fields: set[str] | None = None,
        allowed_keys: set[str] | None = None,
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """根据 provider 自动路由到对应的同步实现。

        Args:
            basic_data: 成员基础信息字典
            provider: 平台标识（"飞书" / "腾讯" / "WPS"）
            provider_cfg: 该平台的连接配置字典
            force_update_fields: 强制更新字段集合
            force_backfill_fields: 强制回填字段集合
            allowed_keys: 允许回填的字段键白名单（None 表示不限制）；仅回填这些字段，忽略远程独有列

        Returns:
            (success, message, target, merged_data)
        """
        self._validate_provider(provider, provider_cfg)
        display_names = {
            "飞书": "飞书多维表",
            "腾讯": "腾讯智能表格",
            "WPS": "WPS多维表格",
        }
        display_name = display_names.get(provider, provider)
        return self._upsert_member_basic_data(
            provider,
            display_name,
            basic_data,
            provider_cfg,
            force_update_fields=force_update_fields,
            force_backfill_fields=force_backfill_fields,
            allowed_keys=allowed_keys,
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

