#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
远程同步管理模块

负责管理员配置上传到远程目标（GitHub / 阿里云 OSS），并管理远程同步配置的
默认值、字段校验、连接测试以及敏感字段的加密/解密。负责成员端从远程URL下载
管理员配置，并返回解析后的JSON对象。
"""

from __future__ import annotations
from cryptography.fernet import Fernet, InvalidToken
from pathlib import Path
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

    # ========================= 配置默认值 =========================

    def get_default_config(self) -> Dict[str, Any]:
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
        merged = self.get_default_config()
        if not isinstance(config, dict):
            return merged

        merged.update({k: v for k, v in config.items() if k in merged and k not in ("github", "oss")})

        if isinstance(config.get("github"), dict):
            merged["github"].update(config["github"])
        if isinstance(config.get("oss"), dict):
            merged["oss"].update(config["oss"])

        provider = str(merged.get("provider", "github")).lower()
        merged["provider"] = "oss" if provider == "oss" else "github"
        return merged

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





