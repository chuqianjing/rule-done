#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
远程同步管理模块

负责管理员配置上传到远程目标（GitHub / 阿里云 OSS），并管理远程同步配置的
默认值、字段校验、连接测试以及敏感字段的加密/解密。负责成员端从远程URL下载
管理员配置，并返回解析后的JSON对象。负责成员端基本信息上传至飞书多维表格
"""

from __future__ import annotations
from cryptography.fernet import Fernet, InvalidToken
from pathlib import Path
from urllib.parse import quote
from typing import Any, Dict, Tuple
import base64
import hashlib
import json
import oss2
import platform
import requests
import time


class SyncManager:
    """远程同步管理器。"""

    SECRET_PREFIX = "enc::"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    
    # ========================= 敏感字段加解密 =========================

    def _build_cipher(self) -> Fernet:
        """构造用于本地敏感字段加密的密钥。"""
        machine_seed = f"{platform.node()}|{Path.cwd()}|party0101-remote-sync"
        digest = hashlib.sha256(machine_seed.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)

    def _encrypt_text(self, value: str) -> str:
        if not value:
            return ""
        if value.startswith(self.SECRET_PREFIX):
            return value
        cipher = self._build_cipher()
        encrypted = cipher.encrypt(value.encode("utf-8")).decode("ascii")
        return f"{self.SECRET_PREFIX}{encrypted}"

    def _decrypt_text(self, value: str) -> str:
        if not value:
            return ""
        if not value.startswith(self.SECRET_PREFIX):
            return value
        cipher = self._build_cipher()
        token = value[len(self.SECRET_PREFIX):]
        try:
            return cipher.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as e:
            raise ValueError("远程同步密钥无法解密，请重新配置凭据。") from e
    
    
    
    # ********************************************************************************************************
    # config
    # ********************************************************************************************************


    # ========================= 配置默认值 =========================

    def get_default_config_sync_settings(self) -> Dict[str, Any]:
        """返回远程同步配置默认值。"""
        return {
            "enabled": False,
            "provider": "github",
            "github": {
                "repo": "",
                "branch": "main",
                "file_path": "admin_config.json",
                "token": "",
                "commit_message": "chore: sync admin config"
            },
            "oss": {
                "endpoint": "",
                "bucket": "",
                "object_key": "admin_config.json",
                "access_key_id": "",
                "access_key_secret": ""
            },
            "last_sync_time": "",
            "last_sync_status": "",
            "last_sync_message": "",
            "last_sync_target": ""
        }
    
    def merge_with_defaults(self, config: Dict[str, Any] | None) -> Dict[str, Any]:
        """将输入配置与默认值合并，保证字段完整。"""
        merged = self.get_default_config_sync_settings()
        if not isinstance(config, dict):
            return merged

        merged.update({k: v for k, v in config.items() if k in merged and k not in ("github", "oss")})

        if isinstance(config.get("github"), dict):
            merged["github"].update(config["github"])
        if isinstance(config.get("oss"), dict):
            merged["oss"].update(config["oss"])

        provider = str(merged.get("provider", "github")).lower()
        if provider in ("github", "oss"):
            merged["provider"] = provider
        else:
            merged["provider"] = "github"
        return merged
    
    def encrypt_sensitive_fields(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """加密配置中的敏感字段。"""
        merged = self.merge_with_defaults(config)
        merged["github"]["token"] = self._encrypt_text(str(merged["github"].get("token", "")))
        merged["oss"]["access_key_secret"] = self._encrypt_text(str(merged["oss"].get("access_key_secret", "")))
        return merged

    def decrypt_sensitive_fields(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解密配置中的敏感字段。"""
        merged = self.merge_with_defaults(config)
        merged["github"]["token"] = self._decrypt_text(str(merged["github"].get("token", "")))
        merged["oss"]["access_key_secret"] = self._decrypt_text(str(merged["oss"].get("access_key_secret", "")))
        return merged
    
    # ========================= 校验与测试 =========================

    def _validate_github(self, github_config: Dict[str, Any]) -> None:
        repo = str(github_config.get("repo", "")).strip()
        branch = str(github_config.get("branch", "")).strip()
        file_path = str(github_config.get("file_path", "")).strip()
        token = str(github_config.get("token", "")).strip()

        if not repo or "/" not in repo:
            raise ValueError("GitHub 仓库格式无效，应为 owner/repo。")
        if not branch:
            raise ValueError("GitHub 分支不能为空。")
        if not file_path:
            raise ValueError("GitHub 文件路径不能为空。")
        if not token:
            raise ValueError("GitHub Token 不能为空（公开仓与私有仓写入都需要可写权限 Token）。")

    def _validate_oss(self, oss_config: Dict[str, Any]) -> None:
        endpoint = str(oss_config.get("endpoint", "")).strip()
        bucket = str(oss_config.get("bucket", "")).strip()
        object_key = str(oss_config.get("object_key", "")).strip()
        access_key_id = str(oss_config.get("access_key_id", "")).strip()
        access_key_secret = str(oss_config.get("access_key_secret", "")).strip()

        if not endpoint:
            raise ValueError("OSS Endpoint 不能为空。")
        if not bucket:
            raise ValueError("OSS Bucket 不能为空。")
        if not object_key:
            raise ValueError("OSS Object Key 不能为空。")
        if not access_key_id:
            raise ValueError("OSS AccessKeyId 不能为空。")
        if not access_key_secret:
            raise ValueError("OSS AccessKeySecret 不能为空。")
    
    def validate_provider_config(self, provider: str, remote_config: Dict[str, Any]) -> None:
        """校验指定 provider 的配置。"""
        provider = str(provider or "").lower()
        if provider == "github":
            self._validate_github(remote_config.get("github", {}))
            return
        if provider == "oss":
            self._validate_oss(remote_config.get("oss", {}))
            return
        raise ValueError("不支持的远程同步类型，请选择 GitHub 或 OSS。")
    
    def test_connection(self, provider: str, remote_config: Dict[str, Any]) -> Tuple[bool, str]:
        """测试远程连接。"""
        config = self.decrypt_sensitive_fields(remote_config)
        self.validate_provider_config(provider, config)

        if provider == "github":
            github_cfg = config["github"]
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_cfg['token']}"
            }
            url = f"https://api.github.com/repos/{github_cfg['repo']}"
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return True, "GitHub 连接成功。"
            if response.status_code in (401, 403):
                return False, "GitHub 鉴权失败，请检查 Token 权限。"
            if response.status_code == 404:
                return False, "GitHub 仓库不存在，或当前 Token 无仓库访问权限。"
            return False, f"GitHub 连接失败（HTTP {response.status_code}）。"

        oss_cfg = config["oss"]
        try:
            auth = oss2.Auth(oss_cfg["access_key_id"], oss_cfg["access_key_secret"])
            bucket = oss2.Bucket(auth, oss_cfg["endpoint"], oss_cfg["bucket"])
            bucket.get_bucket_info()
            return True, "OSS 连接成功。"
        except Exception as e:
            return False, f"OSS 连接失败：{e}"
        
    # ========================= 上传实现 =========================

    def _upload_to_github(self, payload: Dict[str, Any], remote_config: Dict[str, Any]) -> Tuple[bool, str, str]:
        cfg = remote_config["github"]
        repo = cfg["repo"].strip()
        branch = cfg["branch"].strip()
        file_path = cfg["file_path"].strip().lstrip("/")
        token = cfg["token"].strip()
        commit_message = str(cfg.get("commit_message") or "chore: sync admin config").strip()

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}"
        }
        api_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

        sha = None
        get_resp = requests.get(api_url, headers=headers, params={"ref": branch}, timeout=self.timeout)
        if get_resp.status_code == 200:
            sha = (get_resp.json() or {}).get("sha")
        elif get_resp.status_code not in (404,):
            return False, f"读取 GitHub 目标文件失败（HTTP {get_resp.status_code}）。", ""

        content_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        encoded_content = base64.b64encode(content_bytes).decode("ascii")

        body = {
            "message": commit_message,
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        put_resp = requests.put(api_url, headers=headers, json=body, timeout=self.timeout)
        if put_resp.status_code in (200, 201):
            commit_sha = ((put_resp.json() or {}).get("commit") or {}).get("sha", "")
            message = f"已同步到 GitHub，commit={commit_sha[:8] if commit_sha else 'N/A'}"
            # target = f"github://{repo}/{branch}/{file_path}"
            target = "GitHub"
            return True, message, target
        if put_resp.status_code in (401, 403):
            return False, "GitHub 上传鉴权失败，请检查 Token 权限（repo/contents:write）。", "GitHub"
        return False, f"GitHub 上传失败（HTTP {put_resp.status_code}）：{put_resp.text}", "GitHub"

    def _upload_to_oss(self, payload: Dict[str, Any], remote_config: Dict[str, Any]) -> Tuple[bool, str, str]:
        cfg = remote_config["oss"]
        endpoint = cfg["endpoint"].strip()
        bucket_name = cfg["bucket"].strip()
        object_key = cfg["object_key"].strip().lstrip("/")
        access_key_id = cfg["access_key_id"].strip()
        access_key_secret = cfg["access_key_secret"].strip()

        try:
            auth = oss2.Auth(access_key_id, access_key_secret)
            bucket = oss2.Bucket(auth, endpoint, bucket_name)
            content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            result = bucket.put_object(
                object_key, content, 
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "x-oss-object-acl": "public-read"     # 使用该参数前，注意需要解除bucket的组织公共访问权限
                    }
            )
            # target = f"oss://{bucket_name}/{object_key}"
            target = "阿里云OSS"
            return True, f"已同步到 OSS，ETag={getattr(result, 'etag', '')}", target
        except Exception as e:
            return False, f"OSS 上传失败：{e}", "阿里云OSS"

    def upload_admin_config(self, provider: str, payload: Dict[str, Any], remote_config: Dict[str, Any]) -> Tuple[bool, str, str]:
        """上传管理员配置到远程目标。"""
        provider = str(provider or "").lower()
        config = self.decrypt_sensitive_fields(remote_config)
        self.validate_provider_config(provider, config)

        if provider == "github":
            return self._upload_to_github(payload, config)
        if provider == "oss":
            return self._upload_to_oss(payload, config)
        return False, "不支持的远程同步类型。", ""
    
    def download_admin_config(self, sync_url: str):
        """从远程URL下载管理员配置，并返回解析后的JSON对象

        异常处理：
            - 网络错误: 返回无法访问的错误信息
            - JSON解析错误: 返回格式错误的错误信息
        
        注意：
            1. 添加时间戳参数避免CDN缓存
            2. 尝试HEAD请求获取元信息
            3. 使用平台特定User-Agent发送GET请求
        """
        timestamp = int(time.time())
        sync_url = f"{sync_url}?t={timestamp}"  # 添加时间戳参数以避免缓存
        # 1. 获取远程配置的元信息
        try:
            head_response = requests.head(sync_url, timeout=5, allow_redirects=True)
            head_response.raise_for_status()
        except requests.RequestException:
            pass     # HEAD 请求失败，尝试 GET 请求
            
        # 2. 下载远程配置
        try:
            os_type = platform.system()
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PartyTool/1.0"
            if os_type == "Darwin":  # 这是 Mac 的系统代号
                ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PartyTool/1.0"
            elif os_type == "Linux":
                ua = "Mozilla/5.0 (X11; Linux x86_64) PartyTool/1.0"
            headers = {"User-Agent": ua}
            response = requests.get(sync_url, headers=headers, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            remote_config = response.json()
        except requests.RequestException as e:
            raise ConnectionError(f"无法访问配置 URL：{e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"远程配置文件不是有效的 JSON 格式：{e}")
        
        return remote_config


    
    # ********************************************************************************************************
    # info 
    # ********************************************************************************************************
    

    def get_default_info_sync_settings(self) -> Dict[str, Any]:
        """返回成员同步配置默认值。"""
        return {
            "enabled": True,
            "provider": "feishu",
            "feishu": {
                "app_id": "",
                "app_secret": "",
                "app_token": "",
                "table_id": "",
                "id_field": "身份证号",
                "field_mapping": {}
            },
            "last_sync_time": "",
            "last_sync_status": "",
            "last_sync_message": "",
            "last_sync_target": ""
        }

    def merge_info_sync_with_defaults(self, config: Dict[str, Any] | None) -> Dict[str, Any]:
        """将成员同步配置与默认值合并，保证字段完整。"""
        merged = self.get_default_info_sync_settings()
        if not isinstance(config, dict):
            return merged

        merged.update({
            k: v for k, v in config.items()
            if k in merged and k not in ("feishu",)
        })

        if isinstance(config.get("feishu"), dict):
            merged["feishu"].update(config["feishu"])

        for key in ("last_sync_time", "last_sync_status", "last_sync_message", "last_sync_target"):
            if key in config:
                merged[key] = config.get(key, merged[key])

        if not isinstance(merged["feishu"].get("field_mapping"), dict):
            merged["feishu"]["field_mapping"] = {}

        provider = str(merged.get("provider", "feishu")).lower()
        merged["provider"] = "feishu" if provider == "feishu" else "feishu"
        return merged

    def encrypt_info_sync_sensitive_fields(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """加密成员同步配置中的敏感字段。"""
        merged = self.merge_info_sync_with_defaults(config)
        merged["feishu"]["app_secret"] = self._encrypt_text(str(merged["feishu"].get("app_secret", "")))
        return merged

    def decrypt_info_sync_sensitive_fields(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解密成员同步配置中的敏感字段。"""
        merged = self.merge_info_sync_with_defaults(config)
        merged["feishu"]["app_secret"] = self._decrypt_text(str(merged["feishu"].get("app_secret", "")))
        return merged
    
    # ========================= 校验与测试 =========================

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

    def validate_info_sync_provider_config(self, provider: str, info_sync_config: Dict[str, Any]) -> None:
        """按 provider 校验成员同步配置。"""
        provider = str(provider or "").lower()
        if provider == "feishu":
            self._validate_feishu(info_sync_config.get("feishu", {}))
            return
        raise ValueError("不支持的成员同步类型，请选择 Feishu。")

    def _extract_feishu_error(self, response: requests.Response) -> str:
        try:
            body = response.json() or {}
            msg = str(body.get("msg") or body.get("message") or response.text).strip()
            code = body.get("code")
            if code is not None:
                return f"code={code}, msg={msg}"
            return msg
        except Exception:
            return response.text.strip() or f"HTTP {response.status_code}"

    def _get_feishu_tenant_access_token(self, feishu_config: Dict[str, Any]) -> str:
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": str(feishu_config.get("app_id", "")).strip(),
            "app_secret": str(feishu_config.get("app_secret", "")).strip(),
        }
        response = requests.post(token_url, json=payload, timeout=self.timeout)
        if response.status_code != 200:
            raise ValueError(f"飞书鉴权请求失败（HTTP {response.status_code}）：{self._extract_feishu_error(response)}")

        body = response.json() or {}
        if body.get("code") != 0:
            raise ValueError(f"飞书鉴权失败：code={body.get('code')}, msg={body.get('msg')}")

        tenant_access_token = str(body.get("tenant_access_token", "")).strip()
        if not tenant_access_token:
            raise ValueError("飞书鉴权失败：未获取到 tenant_access_token。")
        return tenant_access_token

    def _build_feishu_headers(self, tenant_access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {tenant_access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

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
            headers=self._build_feishu_headers(tenant_access_token),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise ValueError(f"飞书查询记录失败（HTTP {response.status_code}）：{self._extract_feishu_error(response)}")

        body = response.json() or {}
        if body.get("code") != 0:
            raise ValueError(f"飞书查询记录失败：code={body.get('code')}, msg={body.get('msg')}")

        items = ((body.get("data") or {}).get("items") or [])
        if not items:
            return ""
        return str(items[0].get("record_id", "")).strip()

    def _build_feishu_fields_payload(
        self,
        basic_data: Dict[str, Any],
        feishu_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        mapping = feishu_config.get("field_mapping", {})
        if not isinstance(mapping, dict):
            mapping = {}

        fields_payload: Dict[str, Any] = {}
        for local_key, value in basic_data.items():
            if value in (None, ""):
                continue
            target_key = str(mapping.get(local_key) or local_key).strip()
            if not target_key:
                continue
            fields_payload[target_key] = value
        return fields_payload
    
    def _values_conflict(self, existing_val, new_val) -> bool:
        if existing_val is None or existing_val == "" or existing_val == "无":
            return False
        if new_val is None or new_val == "" or new_val == "无":
            return False
        try:
            if existing_val == new_val:
                return False
            return str(existing_val) != str(new_val)
        except Exception:
            return str(existing_val) != str(new_val)

    def _is_missing_local_value(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == "" or value.strip() == "无"
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) == 0
        return False

    def _is_non_empty_remote_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != "" and value.strip() != "无"
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) > 0
        return True

    def _build_reverse_field_mapping(self, feishu_config: Dict[str, Any]) -> Dict[str, str]:
        mapping = feishu_config.get("field_mapping", {})
        if not isinstance(mapping, dict):
            return {}

        reverse_mapping: Dict[str, str] = {}
        for local_key, feishu_key in mapping.items():
            local_key_str = str(local_key).strip()
            feishu_key_str = str(feishu_key).strip()
            if not local_key_str or not feishu_key_str:
                continue
            if feishu_key_str not in reverse_mapping:
                reverse_mapping[feishu_key_str] = local_key_str
        return reverse_mapping

    def _backfill_local_missing_from_feishu(
        self,
        basic_data: Dict[str, Any],
        feishu_fields: Dict[str, Any],
        feishu_config: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], int]:
        merged_data = dict(basic_data or {})
        backfilled_count = 0
        reverse_mapping = self._build_reverse_field_mapping(feishu_config)

        for feishu_key, feishu_val in (feishu_fields or {}).items():
            if not self._is_non_empty_remote_value(feishu_val):
                continue
            feishu_key_str = str(feishu_key).strip()
            if not feishu_key_str:
                continue

            local_key = reverse_mapping.get(feishu_key_str, feishu_key_str)
            if self._is_missing_local_value(merged_data.get(local_key)):
                merged_data[local_key] = feishu_val
                backfilled_count += 1

        return merged_data, backfilled_count

    def _upsert_member_basic_data_to_feishu(
        self,
        basic_data: Dict[str, Any],
        info_sync_config: Dict[str, Any],
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """将成员基础信息同步到飞书多维表（按唯一标识 upsert）。"""
        config = self.decrypt_info_sync_sensitive_fields(info_sync_config)
        self.validate_info_sync_provider_config("feishu", config)
        feishu_cfg = config.get("feishu", {})
        id_field = str(feishu_cfg.get("id_field", "身份证号")).strip()

        member_id_value = str((basic_data or {}).get(id_field, "")).strip()
        if not member_id_value:
            return False, f"成员基本信息缺少唯一标识字段：{id_field}。", "飞书多维表", dict(basic_data or {})

        fields_payload = self._build_feishu_fields_payload(basic_data, feishu_cfg)
        if not fields_payload:
            return False, "没有可同步的成员字段。", "飞书多维表", dict(basic_data or {})

        app_token = str(feishu_cfg.get("app_token", "")).strip()
        table_id = str(feishu_cfg.get("table_id", "")).strip()
        base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"

        try:
            tenant_access_token = self._get_feishu_tenant_access_token(feishu_cfg)
            record_id = self._query_feishu_record_id_by_member_id(feishu_cfg, tenant_access_token, member_id_value)
            headers = self._build_feishu_headers(tenant_access_token)

            if record_id:
                update_url = f"{base_url}/{record_id}"
                
                # 先读取已有记录的字段并与待上传字段逐项比对：
                # 如果飞书中对应键已有非空值且与待上传值不一致，则禁止覆盖并返回失败
                get_existing_resp = requests.get(update_url, headers=headers, timeout=self.timeout)
                if get_existing_resp.status_code != 200:
                    return False, f"读取飞书现有记录失败（HTTP {get_existing_resp.status_code}）：{self._extract_feishu_error(get_existing_resp)}", "飞书多维表", dict(basic_data or {})
                existing_body = get_existing_resp.json() or {}
                existing_fields = ((existing_body.get("data") or {}).get('record') or {}).get("fields") or {}

                for key, new_val in fields_payload.items():
                    if key in existing_fields:
                        if self._values_conflict(existing_fields.get(key), new_val):
                            return False, f"字段 '{key}' 在飞书已有不同值（{existing_fields.get(key)}），禁止覆盖。", "飞书多维表", dict(basic_data or {})

                merged_basic_data, backfilled_count = self._backfill_local_missing_from_feishu(
                    basic_data,
                    existing_fields,
                    feishu_cfg,
                )

                update_resp = requests.put(update_url, headers=headers, json={"fields": fields_payload}, timeout=self.timeout)
                if update_resp.status_code != 200:
                    return False, f"飞书更新记录失败（HTTP {update_resp.status_code}）：{self._extract_feishu_error(update_resp)}", "飞书多维表", dict(basic_data or {})
                update_body = update_resp.json() or {}
                if update_body.get("code") != 0:
                    return False, f"飞书更新记录失败：code={update_body.get('code')}, msg={update_body.get('msg')}", "飞书多维表", dict(basic_data or {})

                success_message = "成员信息已同步并更新飞书记录。"
                if backfilled_count > 0:
                    success_message = f"{success_message} 已回填 {backfilled_count} 个字段到本地。"
                return True, success_message, "飞书多维表", merged_basic_data

            create_resp = requests.post(base_url, headers=headers, json={"fields": fields_payload}, timeout=self.timeout)
            if create_resp.status_code != 200:
                return False, f"飞书新建记录失败（HTTP {create_resp.status_code}）：{self._extract_feishu_error(create_resp)}", "飞书多维表", dict(basic_data or {})
            create_body = create_resp.json() or {}
            if create_body.get("code") != 0:
                return False, f"飞书新建记录失败：code={create_body.get('code')}, msg={create_body.get('msg')}", "飞书多维表", dict(basic_data or {})
            return True, "成员信息已同步并写入飞书记录。", "飞书多维表", dict(basic_data or {})
        except Exception as e:
            return False, f"飞书同步失败：{e}", "飞书多维表", dict(basic_data or {})

    def upload_member_basic_data(self, provider: str, basic_data: Dict[str, Any], info_sync_config: Dict[str, Any]) -> Tuple[bool, str, str, Dict[str, Any]]:
        """将成员基础信息上传到远程目标。"""
        active_provider = str(provider or "").lower()
        config = self.decrypt_info_sync_sensitive_fields(info_sync_config)
        self.validate_info_sync_provider_config(active_provider, config)

        if active_provider == "feishu":
            return self._upsert_member_basic_data_to_feishu(basic_data, config)
        return False, "不支持的成员同步类型。", "", dict(basic_data or {})

    def test_info_sync_connection(self, provider: str, info_sync_config: Dict[str, Any]) -> Tuple[bool, str]:
        """测试成员同步连接。"""
        active_provider = str(provider or "").lower()
        config = self.decrypt_info_sync_sensitive_fields(info_sync_config)
        self.validate_info_sync_provider_config(active_provider, config)

        if active_provider != "feishu":
            return False, "不支持的成员同步类型。"

        feishu_cfg = config["feishu"]
        try:
            token = self._get_feishu_tenant_access_token(feishu_cfg)
            app_token = str(feishu_cfg.get("app_token", "")).strip()
            table_id = str(feishu_cfg.get("table_id", "")).strip()
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=1"
            response = requests.get(url, headers=self._build_feishu_headers(token), timeout=self.timeout)
            if response.status_code != 200:
                return False, f"飞书连接失败（HTTP {response.status_code}）：{self._extract_feishu_error(response)}"
            body = response.json() or {}
            if body.get("code") != 0:
                return False, f"飞书连接失败：code={body.get('code')}, msg={body.get('msg')}"
            return True, "飞书连接成功。"
        except Exception as e:
            return False, f"飞书连接失败：{e}"





