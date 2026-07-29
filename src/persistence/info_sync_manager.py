#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""成员信息同步管理器。"""

from __future__ import annotations
from typing import Any, Dict, Tuple
from urllib.parse import quote
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

    def _build_auth_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _build_fields_payload(
        self,
        basic_data: Dict[str, Any],
        force_backfill_fields: set[str] | None = None,
    ) -> Dict[str, Any]:
        fields_payload: Dict[str, Any] = {}
        for local_key, value in basic_data.items():
            if value in (None, "", "    年  月  日"):
                continue
            target_key = str(local_key).strip()
            if not target_key:
                continue
            if force_backfill_fields and target_key in force_backfill_fields:
                continue
            fields_payload[target_key] = str(value) if not isinstance(value, str) else value
        return fields_payload

    def _values_conflict(self, existing_val, new_val) -> bool:
        """
        existing_val: 飞书中已有的值
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
        判断远程飞书字段值是否为非空值
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
            headers=self._build_auth_headers(tenant_access_token),
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

    def _upsert_member_basic_data_to_feishu(
        self,
        basic_data: Dict[str, Any],
        info_sync_config: Dict[str, Any],
        force_update_fields: set[str] | None = None,
        force_backfill_fields: set[str] | None = None,
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """将成员基础信息同步到飞书多维表（按唯一标识 upsert）。"""

        feishu_cfg = info_sync_config.get("feishu", {})
        id_field = str(feishu_cfg.get("id_field", "身份证号")).strip()

        member_id_value = str((basic_data or {}).get(id_field, "")).strip()
        if not member_id_value:
            return False, f"成员基本信息缺少唯一标识字段：{id_field}。", "飞书多维表", dict(basic_data or {})

        fields_payload = self._build_fields_payload(basic_data, force_backfill_fields)
        if not fields_payload:
            return False, "没有可同步的成员字段。", "飞书多维表", dict(basic_data or {})

        app_token = str(feishu_cfg.get("app_token", "")).strip()
        table_id = str(feishu_cfg.get("table_id", "")).strip()
        base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"

        try:
            tenant_access_token = self._get_feishu_tenant_access_token(feishu_cfg)
            record_id = self._query_feishu_record_id_by_member_id(feishu_cfg, tenant_access_token, member_id_value)
            headers = self._build_auth_headers(tenant_access_token)

            if record_id:
                update_url = f"{base_url}/{record_id}"

                # 先读取已有记录的字段并与待上传字段逐项比对：
                # 如果飞书中对应键已有非空值且与待上传值不一致，则禁止覆盖并返回失败
                get_existing_resp = requests.get(update_url, headers=headers, timeout=self.timeout)
                if get_existing_resp.status_code != 200:
                    return False, f"读取飞书现有记录失败（HTTP {get_existing_resp.status_code}）：{self._extract_response_error(get_existing_resp)}", "飞书多维表", dict(basic_data or {})
                existing_body = get_existing_resp.json() or {}
                existing_fields = ((existing_body.get("data") or {}).get('record') or {}).get("fields") or {}

                force_fields = force_update_fields or set()
                for key, new_val in fields_payload.items():
                    if key in force_fields:
                        continue  # 强制更新字段跳过冲突检查（如填写进度）
                    if key in existing_fields:
                        if self._values_conflict(existing_fields.get(key), new_val):
                            return False, f"字段 '{key}' 在飞书已有不同值（{existing_fields.get(key)}），禁止覆盖。", "飞书多维表", dict(basic_data or {})

                    merged_basic_data, backfilled_count, backfilled_keys = self._backfill_local_missing_from_remote(
                    basic_data,
                    existing_fields,
                    force_backfill_fields=force_backfill_fields,
                )

                update_resp = requests.put(update_url, headers=headers, json={"fields": fields_payload}, timeout=self.timeout)
                if update_resp.status_code != 200:
                    return False, f"飞书更新记录失败（HTTP {update_resp.status_code}）：{self._extract_response_error(update_resp)}", "飞书多维表", dict(basic_data or {})
                update_body = update_resp.json() or {}
                if update_body.get("code") != 0:
                    return False, f"飞书更新记录失败：code={update_body.get('code')}, msg={update_body.get('msg')}" , "飞书多维表", dict(basic_data or {})

                success_message = "成员信息已同步并更新飞书记录。"
                if backfilled_count > 0:
                    success_message = f"{success_message} 已回填 {backfilled_count} 个字段到本地，回填的字段为：{', '.join(backfilled_keys)}。"
                return True, success_message, "飞书多维表", merged_basic_data

            create_resp = requests.post(base_url, headers=headers, json={"fields": fields_payload}, timeout=self.timeout)
            if create_resp.status_code != 200:
                return False, f"飞书新建记录失败（HTTP {create_resp.status_code}）：{self._extract_response_error(create_resp)}", "飞书多维表", dict(basic_data or {})
            create_body = create_resp.json() or {}
            if create_body.get("code") != 0:
                return False, f"飞书新建记录失败：code={create_body.get('code')}, msg={create_body.get('msg')}" , "飞书多维表", dict(basic_data or {})
            return True, "成员信息已同步并写入飞书记录。", "飞书多维表", dict(basic_data or {})
        except Exception as exc:
            return False, f"飞书同步失败：{exc}", "飞书多维表", dict(basic_data or {})

    def _test_feishu_connection(self, feishu_cfg: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            token = self._get_feishu_tenant_access_token(feishu_cfg)
            app_token = str(feishu_cfg.get("app_token", "")).strip()
            table_id = str(feishu_cfg.get("table_id", "")).strip()
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=1"
            response = requests.get(url, headers=self._build_auth_headers(token), timeout=self.timeout)
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

    def _convert_basic_data_to_tencent_values(
        self,
        basic_data: Dict[str, Any],
        force_backfill_fields: set[str] | None = None,
    ) -> Dict[str, Any]:
        """将 basic_data 转换为腾讯 Smartsheet 的 values 格式。"""
        values: Dict[str, Any] = {}
        for local_key, value in basic_data.items():
            if value in (None, "", "    年  月  日"):
                continue
            target_key = str(local_key).strip()
            if not target_key:
                continue
            if force_backfill_fields and target_key in force_backfill_fields:
                continue
            values[target_key] = self._build_tencent_value(value)
        return values

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
        return all_records

    def _find_tencent_record_id_by_member_id(
        self,
        tencent_cfg: Dict[str, Any],
        member_id_value: str,
    ) -> str:
        """在全量记录中按成员标识字段值查找记录 ID。"""
        id_field = str(tencent_cfg.get("id_field", "身份证号")).strip()
        records = self._query_tencent_all_records(tencent_cfg)
        for record in records:
            record_id = str(record.get("recordID", "")).strip()
            values = record.get("values") or {}
            field_value = self._extract_tencent_value(values.get(id_field))
            if field_value == member_id_value:
                return record_id
        return ""

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

    def _upsert_member_basic_data_to_tencent(
        self,
        basic_data: Dict[str, Any],
        info_sync_config: Dict[str, Any],
        force_update_fields: set[str] | None = None,
        force_backfill_fields: set[str] | None = None,
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """将成员基础信息同步到腾讯智能表格（按唯一标识 upsert）。

        腾讯 Smartsheet API 说明：
        - 所有操作均为 POST
        - 添加: {"addRecords": {"records": [{"values": {...}}]}}
        - 更新: {"updateRecords": {"records": [{"recordID": "...", "values": {...}}]}}
        - 查询: {"getRecords": {"offset": 0, "limit": 100}}
        """
        tencent_cfg = info_sync_config.get("tencent", {})
        self._resolve_tencent_file_id(tencent_cfg)

        id_field = str(tencent_cfg.get("id_field", "身份证号")).strip()

        member_id_value = str((basic_data or {}).get(id_field, "")).strip()
        if not member_id_value:
            return False, f"成员基本信息缺少唯一标识字段：{id_field}。", "腾讯智能表格", dict(basic_data or {})

        values_payload = self._convert_basic_data_to_tencent_values(basic_data, force_backfill_fields)
        if not values_payload:
            return False, "没有可同步的成员字段。", "腾讯智能表格", dict(basic_data or {})

        file_id = str(tencent_cfg.get("file_id", "")).strip()
        sheet_id = str(tencent_cfg.get("sheet_id", "")).strip()
        api_url = f"https://docs.qq.com/openapi/smartbook/v2/files/{file_id}/sheets/{sheet_id}"

        headers = self._build_tencent_headers(tencent_cfg)

        try:
            record_id = self._find_tencent_record_id_by_member_id(tencent_cfg, member_id_value)

            if record_id:
                # 读取现有记录做冲突检查和回填
                existing_record = self._fetch_tencent_record_by_id(tencent_cfg, record_id)
                existing_values = existing_record.get("values") or {}

                force_fields = force_update_fields or set()
                for key, new_val in values_payload.items():
                    if key in force_fields:
                        continue
                    if key in existing_values:
                        existing_text = self._extract_tencent_value(existing_values.get(key))
                        new_text = str(basic_data.get(key, ""))
                        if self._values_conflict(existing_text, new_text):
                            return False, f"字段 '{key}' 在腾讯文档已有不同值（{existing_text}），禁止覆盖。", "腾讯智能表格", dict(basic_data or {})

                # 回填：将腾讯格式的值展平为普通 dict，再复用公用方法
                existing_plain: Dict[str, Any] = {}
                for k, v in existing_values.items():
                    text = self._extract_tencent_value(v)
                    if text:
                        existing_plain[k] = text
                merged_basic_data, backfilled_count, backfilled_keys = self._backfill_local_missing_from_remote(
                    basic_data,
                    existing_plain,
                    force_backfill_fields=force_backfill_fields,
                )

                update_body = {"updateRecords": {"records": [{"recordID": record_id, "values": values_payload}]}}
                update_resp = requests.post(api_url, headers=headers, json=update_body, timeout=self.timeout)
                if update_resp.status_code != 200:
                    return False, f"腾讯文档更新记录失败（HTTP {update_resp.status_code}）：{self._extract_response_error(update_resp)}", "腾讯智能表格", dict(basic_data or {})
                resp_data = update_resp.json() or {}
                if resp_data.get("ret") != 0:
                    return False, f"腾讯文档更新记录失败：ret={resp_data.get('ret')}, msg={resp_data.get('msg')}", "腾讯智能表格", dict(basic_data or {})

                success_message = "成员信息已同步并更新腾讯文档记录。"
                if backfilled_count > 0:
                    success_message += f" 已回填 {backfilled_count} 个字段到本地，回填的字段为：{', '.join(backfilled_keys)}。"
                return True, success_message, "腾讯智能表格", merged_basic_data

            create_body = {"addRecords": {"records": [{"values": values_payload}]}}
            create_resp = requests.post(api_url, headers=headers, json=create_body, timeout=self.timeout)
            if create_resp.status_code != 200:
                return False, f"腾讯文档新建记录失败（HTTP {create_resp.status_code}）：{self._extract_response_error(create_resp)}", "腾讯智能表格", dict(basic_data or {})
            resp_data = create_resp.json() or {}
            if resp_data.get("ret") != 0:
                return False, f"腾讯文档新建记录失败：ret={resp_data.get('ret')}, msg={resp_data.get('msg')}", "腾讯智能表格", dict(basic_data or {})
            return True, "成员信息已同步并写入腾讯文档记录。", "腾讯智能表格", dict(basic_data or {})
        except Exception as exc:
            return False, f"腾讯文档同步失败：{exc}", "腾讯智能表格", dict(basic_data or {})

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

    # ======================= WPS 多维表格（暂不可用） =======================

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
            raise ValueError("WPS多维表格 Table ID（工作表ID）不能为空。")
        if not id_field:
            raise ValueError("WPS多维表格唯一标识字段不能为空。")

    def _get_wps_access_token(self, wps_config: Dict[str, Any]) -> str:
        token_url = "https://open.wps.cn/api/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": str(wps_config.get("app_id", "")).strip(),
            "client_secret": str(wps_config.get("app_secret", "")).strip(),
        }
        response = requests.post(token_url, data=payload, timeout=self.timeout)
        if response.status_code != 200:
            raise ValueError(f"WPS鉴权请求失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")

        body = response.json() or {}
        access_token = str(body.get("access_token") or body.get("data", {}).get("access_token", "")).strip()
        if not access_token:
            raise ValueError("WPS鉴权失败：未获取到 access_token。")
        return access_token

    def _query_wps_all_records(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
    ) -> list[Dict[str, Any]]:
        """查询WPS多维表格中所有记录（分页拉取）。"""
        app_token = str(wps_config.get("app_token", "")).strip()
        table_id = str(wps_config.get("table_id", "")).strip()
        headers = self._build_auth_headers(access_token)
        all_rows: list[Dict[str, Any]] = []
        offset = 0
        page_size = 200

        while True:
            list_url = (
                f"https://open.wps.cn/api/v1/sheets/{app_token}/rows"
                f"?sheet_id={table_id}&offset={offset}&limit={page_size}"
            )
            response = requests.get(list_url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                raise ValueError(f"WPS查询记录失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")
            body = response.json() or {}
            rows = body.get("rows") or body.get("data", {}).get("rows") or []
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < page_size:
                break
            offset += page_size

        return all_rows

    def _fetch_wps_record_by_id(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
        record_id: str,
    ) -> Dict[str, Any]:
        """按 row_id 查询WPS多维表格中的单条记录。"""
        app_token = str(wps_config.get("app_token", "")).strip()
        table_id = str(wps_config.get("table_id", "")).strip()
        headers = self._build_auth_headers(access_token)
        url = f"https://open.wps.cn/api/v1/sheets/{app_token}/rows/{record_id}?sheet_id={table_id}"
        response = requests.get(url, headers=headers, timeout=self.timeout)
        if response.status_code != 200:
            raise ValueError(f"读取WPS多维表格记录失败（HTTP {response.status_code}）：{self._extract_response_error(response)}")
        body = response.json() or {}
        existing_row = body.get("row") or body.get("data", {}).get("row") or {}
        return existing_row.get("fields") or existing_row.get("values") or {}

    def _query_wps_record_id_by_member_id(
        self,
        wps_config: Dict[str, Any],
        access_token: str,
        member_id_value: str,
    ) -> str:
        id_field = str(wps_config.get("id_field", "身份证号")).strip()
        rows = self._query_wps_all_records(wps_config, access_token)
        for row in rows:
            fields = row.get("fields") or row.get("values") or {}
            if str(fields.get(id_field, "")).strip() == member_id_value:
                return str(row.get("row_id") or row.get("id", "")).strip()
        return ""

    def _upsert_member_basic_data_to_wps(
        self,
        basic_data: Dict[str, Any],
        info_sync_config: Dict[str, Any],
        force_update_fields: set[str] | None = None,
        force_backfill_fields: set[str] | None = None,
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """将成员基础信息同步到WPS多维表格（按唯一标识 upsert）。"""

        wps_cfg = info_sync_config.get("wps", {})
        id_field = str(wps_cfg.get("id_field", "身份证号")).strip()

        member_id_value = str((basic_data or {}).get(id_field, "")).strip()
        if not member_id_value:
            return False, f"成员基本信息缺少唯一标识字段：{id_field}。", "WPS多维表格", dict(basic_data or {})

        fields_payload = self._build_fields_payload(basic_data, force_backfill_fields)
        if not fields_payload:
            return False, "没有可同步的成员字段。", "WPS多维表格", dict(basic_data or {})

        app_token = str(wps_cfg.get("app_token", "")).strip()
        table_id = str(wps_cfg.get("table_id", "")).strip()

        try:
            access_token = self._get_wps_access_token(wps_cfg)
            record_id = self._query_wps_record_id_by_member_id(wps_cfg, access_token, member_id_value)
            headers = self._build_auth_headers(access_token)

            if record_id:
                update_url = f"https://open.wps.cn/api/v1/sheets/{app_token}/rows/{record_id}"

                # 获取现有记录的字段进行冲突检查
                existing_fields = self._fetch_wps_record_by_id(wps_cfg, access_token, record_id)

                force_fields = force_update_fields or set()
                for key, new_val in fields_payload.items():
                    if key in force_fields:
                        continue
                    if key in existing_fields:
                        if self._values_conflict(existing_fields.get(key), new_val):
                            return False, f"字段 '{key}' 在WPS多维表格已有不同值（{existing_fields.get(key)}），禁止覆盖。", "WPS多维表格", dict(basic_data or {})

                merged_basic_data, backfilled_count, backfilled_keys = self._backfill_local_missing_from_remote(
                    basic_data,
                    existing_fields,
                    force_backfill_fields=force_backfill_fields,
                )

                update_payload = {"sheet_id": table_id, "fields": fields_payload}
                update_resp = requests.put(update_url, headers=headers, json=update_payload, timeout=self.timeout)
                if update_resp.status_code != 200:
                    return False, f"WPS更新记录失败（HTTP {update_resp.status_code}）：{self._extract_response_error(update_resp)}", "WPS多维表格", dict(basic_data or {})
                update_body = update_resp.json() or {}
                if update_body.get("code") not in (0, None):
                    return False, f"WPS更新记录失败：code={update_body.get('code')}, msg={update_body.get('msg')}", "WPS多维表格", dict(basic_data or {})

                success_message = "成员信息已同步并更新WPS多维表格记录。"
                if backfilled_count > 0:
                    success_message = f"{success_message} 已回填 {backfilled_count} 个字段到本地，回填的字段为：{', '.join(backfilled_keys)}。"
                return True, success_message, "WPS多维表格", merged_basic_data

            create_payload = {"sheet_id": table_id, "fields": fields_payload}
            create_resp = requests.post(
                f"https://open.wps.cn/api/v1/sheets/{app_token}/rows",
                headers=headers, json=create_payload, timeout=self.timeout,
            )
            if create_resp.status_code != 200:
                return False, f"WPS新建记录失败（HTTP {create_resp.status_code}）：{self._extract_response_error(create_resp)}", "WPS多维表格", dict(basic_data or {})
            create_body = create_resp.json() or {}
            if create_body.get("code") not in (0, None):
                return False, f"WPS新建记录失败：code={create_body.get('code')}, msg={create_body.get('msg')}", "WPS多维表格", dict(basic_data or {})
            return True, "成员信息已同步并写入WPS多维表格记录。", "WPS多维表格", dict(basic_data or {})
        except Exception as exc:
            return False, f"WPS同步失败：{exc}", "WPS多维表格", dict(basic_data or {})

    def _test_wps_connection(self, wps_cfg: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            token = self._get_wps_access_token(wps_cfg)
            app_token = str(wps_cfg.get("app_token", "")).strip()
            table_id = str(wps_cfg.get("table_id", "")).strip()
            url = f"https://open.wps.cn/api/v1/sheets/{app_token}/rows?sheet_id={table_id}&limit=1"
            response = requests.get(url, headers=self._build_auth_headers(token), timeout=self.timeout)
            if response.status_code != 200:
                return False, f"WPS连接失败（HTTP {response.status_code}）：{self._extract_response_error(response)}"
            return True, "WPS多维表格连接成功。"
        except Exception as exc:
            return False, f"WPS连接失败：{exc}"

    # ======================= 通用公开接口 =======================

    def upload_member_basic_data_with_config(
        self,
        basic_data: Dict[str, Any],
        provider: str,
        provider_cfg: Dict[str, Any],
        force_update_fields: set[str] | None = None,
        force_backfill_fields: set[str] | None = None,
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """根据 provider 自动路由到对应的同步实现。

        Args:
            basic_data: 成员基础信息字典
            provider: 平台标识（"feishu" / "tencent" / "wps"）
            provider_cfg: 该平台的连接配置字典
            force_update_fields: 强制更新字段集合
            force_backfill_fields: 强制回填字段集合

        Returns:
            (success, message, target, merged_data)
        """
        provider = str(provider).lower()
        if provider == "feishu":
            self._validate_feishu(provider_cfg)
            return self._upsert_member_basic_data_to_feishu(
                basic_data, {"feishu": provider_cfg},
                force_update_fields=force_update_fields,
                force_backfill_fields=force_backfill_fields,
            )
        elif provider == "tencent":
            self._validate_tencent(provider_cfg)
            return self._upsert_member_basic_data_to_tencent(
                basic_data, {"tencent": provider_cfg},
                force_update_fields=force_update_fields,
                force_backfill_fields=force_backfill_fields,
            )
        elif provider == "wps":
            self._validate_wps(provider_cfg)
            return self._upsert_member_basic_data_to_wps(
                basic_data, {"wps": provider_cfg},
                force_update_fields=force_update_fields,
                force_backfill_fields=force_backfill_fields,
            )
        else:
            raise ValueError(f"不支持的同步平台：{provider}。请选择 feishu、tencent 或 wps。")

    def test_connection_with_config(self, provider: str, provider_cfg: Dict[str, Any]) -> Tuple[bool, str]:
        """根据 provider 测试对应平台的连接。

        Args:
            provider: 平台标识（"feishu" / "tencent" / "wps"）
            provider_cfg: 该平台的连接配置字典

        Returns:
            (success, message)
        """
        provider = str(provider).lower()
        if provider == "feishu":
            self._validate_feishu(provider_cfg)
            return self._test_feishu_connection(provider_cfg)
        elif provider == "tencent":
            self._validate_tencent(provider_cfg)
            return self._test_tencent_connection(provider_cfg)
        elif provider == "wps":
            self._validate_wps(provider_cfg)
            return self._test_wps_connection(provider_cfg)
        else:
            raise ValueError(f"不支持的同步平台：{provider}。请选择 feishu、tencent 或 wps。")

