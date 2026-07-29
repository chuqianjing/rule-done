#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""管理员配置同步管理器。"""

from __future__ import annotations

import base64
import json
import platform
import time
from typing import Any, Dict, Tuple

import oss2
import requests

from src.persistence.sync_base import SyncManagerBase
from src.persistence.sync_crypto_helper import SyncCryptoHelper


class ConfigSyncManager(SyncManagerBase):
    """管理员配置同步管理器。"""

    def __init__(self, timeout: int = 10, crypto_helper: SyncCryptoHelper | None = None):
        super().__init__(timeout=timeout)
        self.crypto = crypto_helper or SyncCryptoHelper()

    def encrypt_sensitive_fields(self, config: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(config)
        result["encrypt_key"] = self.crypto.encrypt_text(str(result.get("encrypt_key", "")))
        result["github"]["token"] = self.crypto.encrypt_text(str(result["github"].get("token", "")))
        result["oss"]["access_key_secret"] = self.crypto.encrypt_text(str(result["oss"].get("access_key_secret", "")))
        return result

    def decrypt_sensitive_fields(self, config: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(config)
        result["encrypt_key"] = self.crypto.decrypt_text(str(result.get("encrypt_key", "")))
        result["github"]["token"] = self.crypto.decrypt_text(str(result["github"].get("token", "")))
        result["oss"]["access_key_secret"] = self.crypto.decrypt_text(str(result["oss"].get("access_key_secret", "")))
        return result

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
        provider = str(provider or "").lower()
        if provider == "github":
            self._validate_github(remote_config.get("github", {}))
            return
        if provider == "oss":
            self._validate_oss(remote_config.get("oss", {}))
            return
        raise ValueError("不支持的远程同步类型，请选择 GitHub 或 OSS。")

    def test_connection(self, provider: str, config: Dict[str, Any]) -> Tuple[bool, str]:
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
        except Exception as exc:
            return False, f"OSS 连接失败：{exc}"

    def _upload_to_github(self, payload: Dict[str, Any], remote_config: Dict[str, Any], encrypt_key: str = "") -> Tuple[bool, str, str]:
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
            return False, f"读取 GitHub 目标文件失败（HTTP {get_resp.status_code}）。", "GitHub"

        content_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        if encrypt_key:
            content_bytes = self.crypto.encrypt_payload(payload, encrypt_key)
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
            return True, message, "GitHub"
        if put_resp.status_code in (401, 403):
            return False, "GitHub 上传鉴权失败，请检查 Token 权限（repo/contents:write）。", "GitHub"
        return False, f"GitHub 上传失败（HTTP {put_resp.status_code}）：{put_resp.text}", "GitHub"

    def _upload_to_oss(self, payload: Dict[str, Any], remote_config: Dict[str, Any], encrypt_key: str = "") -> Tuple[bool, str, str]:
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
            if encrypt_key:
                content = self.crypto.encrypt_payload(payload, encrypt_key)
            result = bucket.put_object(
                object_key,
                content,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "x-oss-object-acl": "public-read",
                }
            )
            return True, f"已同步到 OSS，ETag={getattr(result, 'etag', '')}", "阿里云OSS"
        except Exception as exc:
            return False, f"OSS 上传失败：{exc}", "阿里云OSS"

    def upload_admin_config(self, provider: str, payload: Dict[str, Any], config: Dict[str, Any], encrypt_key: str = "") -> Tuple[bool, str, str]:
        """上传管理员配置到远程目标。

        Args:
            provider: 远程目标类型 (github/oss)
            payload: 待上传的配置字典
            remote_config: 远程同步配置（含凭据）
            encrypt_key: 若非空，上传前用此密钥加密整个 payload
        """
        provider = str(provider or "").lower()
        self.validate_provider_config(provider, config)

        if provider == "github":
            return self._upload_to_github(payload, config, encrypt_key=encrypt_key)
        if provider == "oss":
            return self._upload_to_oss(payload, config, encrypt_key=encrypt_key)
        return False, "不支持的远程同步类型。", ""

    def download_admin_config(self, sync_url: str, decrypt_key: str = ""):
        """从远程URL下载管理员配置，并返回解析后的JSON对象

        支持两种模式：
        - 无 decrypt_key：以 JSON 格式直接解析（兼容未加密的旧配置）
        - 有 decrypt_key：先尝试 JSON 解析，失败则尝试用密钥解密

        Args:
            sync_url: 配置文件的网络URL地址
            decrypt_key: 解密密钥（若远程文件已加密）

        Returns:
            dict: 解析后的配置字典

        Raises:
            ConnectionError: 网络请求失败
            ValueError: JSON解析失败或解密失败
        """
        timestamp = int(time.time())
        sync_url = f"{sync_url}?t={timestamp}"  # 添加时间戳参数以避免缓存
        # 1. 获取远程配置的元信息
        try:
            head_response = requests.head(sync_url, timeout=5, allow_redirects=True)
            head_response.raise_for_status()
        except requests.RequestException:
            pass

        # 2. 下载远程配置
        try:
            os_type = platform.system()
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PartyTool/1.0"
            if os_type == "Darwin":
                ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PartyTool/1.0"
            elif os_type == "Linux":
                ua = "Mozilla/5.0 (X11; Linux x86_64) PartyTool/1.0"
            headers = {"User-Agent": ua}
            response = requests.get(sync_url, headers=headers, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            content = response.content

            # 先尝试当作普通 JSON 解析（向后兼容）
            try:
                remote_config = json.loads(content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                if not decrypt_key:
                    raise ValueError("远程配置文件已加密，需要解密密钥。请联系管理员获取。")
                try:
                    remote_config = self.crypto.decrypt_payload(content, decrypt_key)
                except Exception as exc:
                    raise ValueError(f"远程配置解密失败：{exc} 请确认解密密钥是否正确。")
        except requests.RequestException as exc:
            raise ConnectionError(f"无法访问配置 URL：{exc}")

        return remote_config
