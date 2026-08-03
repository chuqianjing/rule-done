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

    # ========================== 下载 =========================

    @staticmethod
    def _append_cache_buster(url: str) -> str:
        """追加时间戳参数以避免缓存（兼容 URL 已含查询串的情况）。"""
        timestamp = int(time.time())
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}t={timestamp}"

    @staticmethod
    def _build_download_headers(sync_url: str, access_token: str = "") -> Dict[str, str]:
        """构造下载请求头，支持私有仓库访问令牌。"""
        os_type = platform.system()
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PartyTool/1.0"
        if os_type == "Darwin":
            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PartyTool/1.0"
        elif os_type == "Linux":
            ua = "Mozilla/5.0 (X11; Linux x86_64) PartyTool/1.0"
        headers: Dict[str, str] = {"User-Agent": ua}
        token = str(access_token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            # 对 GitHub contents API 端点，使用 raw 媒体类型直接取文件内容
            if "api.github.com/repos/" in sync_url and "/contents/" in sync_url:
                headers["Accept"] = "application/vnd.github.raw+json"
        return headers

    @staticmethod
    def _is_oss_url(sync_url: str) -> bool:
        """判断 URL 是否指向阿里云 OSS 对象。"""
        from urllib.parse import urlsplit

        hostname = (urlsplit(sync_url).netloc or "").lower()
        return "aliyuncs.com" in hostname or hostname.startswith("oss-")

    @staticmethod
    def _parse_oss_url(sync_url: str) -> Tuple[str, str, str]:
        """从 OSS 对象 URL 解析 (bucket, endpoint, object_key)。

        支持两种形态：
        - virtual-hosted style：https://{bucket}.{endpoint}/{object_key}（阿里云标准形态）
        - path-style：https://{endpoint}/{bucket}/{object_key}
        """
        from urllib.parse import urlsplit

        parsed = urlsplit(sync_url)
        hostname = (parsed.netloc or "").split(":")[0]
        path = parsed.path.lstrip("/")

        # host 本身就是 endpoint（path-style，bucket 在路径首段）
        if hostname.startswith("oss-"):
            parts = path.split("/")
            return parts[0], hostname, "/".join(parts[1:])

        # virtual-hosted style：host 形如 bucket.endpoint，endpoint 含 "oss-"
        if "oss-" in hostname:
            bucket_name = hostname.split(".")[0]
            endpoint = hostname[len(bucket_name) + 1:]
            return bucket_name, endpoint, path

        # 不含 "oss-"：视为 path-style（自定义 endpoint）
        parts = path.split("/")
        return parts[0], hostname, "/".join(parts[1:])

    def _download_from_oss(self, sync_url: str, access_key_id: str, access_key_secret: str) -> bytes:
        """使用只读子账号凭据，签名下载 OSS 私有对象。"""
        try:
            bucket_name, endpoint, object_key = self._parse_oss_url(sync_url)
            if not bucket_name or not object_key:
                raise ValueError("无法从 URL 解析出 OSS Bucket 与 Object Key，请检查同步URL。")
            if not endpoint.startswith(("http://", "https://")):
                endpoint = f"https://{endpoint}"
            auth = oss2.Auth(access_key_id, access_key_secret)
            bucket = oss2.Bucket(auth, endpoint, bucket_name, connect_timeout=self.timeout)
            result = bucket.get_object(object_key)
            return result.read()
        except ValueError as exc:
            raise ConnectionError(str(exc))
        except Exception as exc:
            raise ConnectionError(f"OSS 私有对象访问失败：{exc}")

    def _download_via_http(self, sync_url: str, access_token: str, decrypt_key: str):
        """匿名 / 携带 Bearer 令牌的 HTTP 下载。"""
        sync_url = self._append_cache_buster(sync_url)
        headers = self._build_download_headers(sync_url, access_token)

        # 1. 获取远程配置的元信息
        try:
            head_response = requests.head(sync_url, timeout=5, allow_redirects=True, headers=headers)
            head_response.raise_for_status()
        except requests.RequestException:
            pass

        # 2. 下载远程配置
        try:
            response = requests.get(sync_url, headers=headers, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            content = response.content
        except requests.RequestException as exc:
            raise ConnectionError(f"无法访问配置 URL：{exc}")

        return self._parse_downloaded_content(content, decrypt_key)

    def _parse_downloaded_content(self, content: bytes, decrypt_key: str):
        """解析下载内容：先按 JSON，失败则尝试用密钥解密（向后兼容）。"""
        try:
            return json.loads(content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            if not decrypt_key:
                raise ValueError("远程配置文件已加密，需要解密密钥。请联系管理员获取。")
            try:
                return self.crypto.decrypt_payload(content, decrypt_key)
            except Exception as exc:
                raise ValueError(f"远程配置解密失败：{exc} 请确认解密密钥是否正确。")

    def download_admin_config(self, sync_url: str, decrypt_key: str = "", access_token: str = "",
                              oss_credentials: Dict[str, Any] | None = None):
        """从远程URL下载管理员配置，并返回解析后的JSON对象

        支持两种模式：
        - 无 decrypt_key：以 JSON 格式直接解析（兼容未加密的旧配置）
        - 有 decrypt_key：先尝试 JSON 解析，失败则尝试用密钥解密

        下载方式按 URL 实际情况自动选择：
        - OSS 对象 URL：配置了 OSS 只读子账号凭据时签名下载私有对象；
          未配置时退回匿名 GET（公开对象可用，私有对象会提示配置凭据）。
        - GitHub 私有仓库 URL：携带 Bearer 令牌（只读 PAT）访问；无令牌时按匿名 URL 处理。
        - 其他 URL：匿名 GET。

        Args:
            sync_url: 配置文件的网络URL地址
            decrypt_key: 解密密钥（若远程文件已加密）
            access_token: 远程访问令牌（若配置存放在 GitHub 私有仓库，如只读 PAT）
            oss_credentials: OSS 只读子账号凭据（若配置存放在 OSS 私有对象）

        Returns:
            dict: 解析后的配置字典

        Raises:
            ConnectionError: 网络请求失败
            ValueError: JSON解析失败或解密失败
        """
        oss_credentials = oss_credentials or {}
        oss_access_key_id = str(oss_credentials.get("access_key_id", "") or "").strip()
        oss_access_key_secret = str(oss_credentials.get("access_key_secret", "") or "").strip()

        if self._is_oss_url(sync_url):
            # OSS 对象 URL：优先使用只读子账号凭据签名下载
            if oss_access_key_id and oss_access_key_secret:
                content = self._download_from_oss(sync_url, oss_access_key_id, oss_access_key_secret)
                return self._parse_downloaded_content(content, decrypt_key)
            # 未配置凭据：尝试匿名 GET（公开对象可访问；私有对象 403 时给出提示）
            try:
                return self._download_via_http(sync_url, access_token="", decrypt_key=decrypt_key)
            except ConnectionError as exc:
                raise ConnectionError(
                    f"{exc}\n提示：该 URL 指向 OSS 对象，若为私有对象，请先在设置页配置 OSS 只读子账号凭据。"
                )

        # GitHub 私有仓库 / 其他 URL：匿名 GET（GitHub 私有仓库时携带 Bearer 令牌）
        return self._download_via_http(sync_url, access_token=access_token, decrypt_key=decrypt_key)
