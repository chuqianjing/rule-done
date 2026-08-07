#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""模板与字段资源同步管理器。

负责把 schema（字段定义）与 templates（模板配置 + .docx）打包发布到远程
（复用 config_sync 的 GitHub/OSS 通道），以及成员端按清单（manifest）版本
先行判断、按需拉取与应用。

设计要点：
- manifest 先行：成员端只下载 KB 级清单做版本比较，版本相同即零下载。
- 资源包（zip）内容寻址：version 由内容哈希派生，内容不变则版本不变。
- 不加密（资源不含机密），但做 SHA-256 完整性校验；应用前备份、失败回滚。
- 应用策略：覆盖 + 新增，不删除成员端本地额外文件。
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlsplit, urlunsplit

from src.utils.file_path import get_runtime_resources_dir, get_runtime_resources_sync_dir
from src.persistence.field_manager import FieldManager
from src.persistence.template_manager import TemplateManager
from src.persistence.config_sync_manager import ConfigSyncManager
from src.utils.json_storage import JSONStorage


class ResourceSyncManager:
    """模板与字段资源同步管理器。"""

    MANIFEST_FILENAME = "resources_manifest.json"
    PACK_FILENAME = "resources_pack.zip"

    def __init__(self, field_manager : FieldManager, template_manager : TemplateManager, config_sync_manager : ConfigSyncManager, json_storage : JSONStorage):
        self.field_manager = field_manager
        self.template_manager = template_manager
        self.config_sync_manager = config_sync_manager
        self.json_storage = json_storage

    # ====================== 本地资源 ======================

    def _resources_dir(self) -> Path:
        return get_runtime_resources_dir()

    def _sync_dir(self) -> Path:
        return get_runtime_resources_sync_dir()

    def get_local_version(self) -> str:
        """本机已应用资源的版本（来自 manifest_local.json）。"""
        manifest_path = self._sync_dir() / "manifest_local.json"
        if not manifest_path.exists():
            return ""
        try:
            data = self.json_storage.read_json(str(manifest_path))
            return str(data.get("version", "") or "")
        except Exception:
            return ""

    # ====================== 打包与清单 ======================

    def _add_file_to_zip(self, zf: zipfile.ZipFile, src: Path, arcname: str, entries: list) -> None:
        data = src.read_bytes()
        entries.append({"path": arcname, "sha256": hashlib.sha256(data).hexdigest()})
        zf.writestr(arcname, data)

    def build_resources_pack(self) -> bytes:
        """把 schema + templates 打包为 zip（内存字节），包内含 MANIFEST.txt。"""
        buf = io.BytesIO()
        entries: list[dict] = []
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            schema_path = Path(self.field_manager.config_path)
            if schema_path.exists():
                self._add_file_to_zip(zf, schema_path, "schema/fields_definition.json", entries)
            templates_dir = Path(self.template_manager.templates_dir)
            config_path = templates_dir / "templates_config.json"
            if config_path.exists():
                self._add_file_to_zip(zf, config_path, "templates/templates_config.json", entries)
            if templates_dir.exists():
                for docx in sorted(templates_dir.glob("*.docx")):
                    self._add_file_to_zip(zf, docx, f"templates/{docx.name}", entries)
            zf.writestr("MANIFEST.txt", json.dumps({"files": entries}, ensure_ascii=False, indent=2))
        return buf.getvalue()

    def build_manifest(self, pack_bytes: bytes) -> Dict[str, Any]:
        """根据资源包内容生成远程清单（版本由内容哈希派生，内容不变则版本不变）。"""
        schema_version = ""
        try:
            schema = self.field_manager.load_fields_definition()
            schema_version = str(schema.get("version", "") or "")
        except Exception:
            schema_version = ""
        pack_sha = hashlib.sha256(pack_bytes).hexdigest()
        version = f"{schema_version}-r{pack_sha[:8]}"
        return {
            "version": version,
            "released_at": datetime.now().isoformat(),
            "pack": {
                "file": self.PACK_FILENAME,
                "size": len(pack_bytes),
                "sha256": pack_sha,
            },
            "schema_version": schema_version,
        }

    # ====================== 管理员端发布 ======================

    def preflight(self) -> list[str]:
        """发布前本地预检，返回错误列表（空表示通过）。"""
        errors: list[str] = []
        errors.extend(self.template_manager.validate_config())
        schema_path = Path(self.field_manager.config_path)
        if not schema_path.exists():
            errors.append(f"字段定义文件不存在：{schema_path}")
        else:
            try:
                self.field_manager.load_fields_definition()
            except Exception as exc:
                errors.append(f"字段定义文件无法解析：{exc}")
        return errors

    def publish_resources(self, provider: str, config: Dict[str, Any],
                          prefix: str = "resources",
                          commit_message: str = "chore: sync resources") -> Tuple[bool, str, str]:
        """发布资源包 + 清单到远程。

        先传包、再传清单：清单是"指针"，最后更新以避免指向不存在的资源包。
        """
        errors = self.preflight()
        if errors:
            raise ValueError("资源发布预检未通过：\n" + "\n".join(f" - {e}" for e in errors))

        pack_bytes = self.build_resources_pack()
        manifest = self.build_manifest(pack_bytes)
        prefix = str(prefix or "resources").strip().strip("/")

        manifest_obj = f"{prefix}/{self.MANIFEST_FILENAME}"
        pack_obj = f"{prefix}/{self.PACK_FILENAME}"

        ok, msg, target = self.config_sync_manager.upload_raw_file(
            provider, pack_obj, pack_bytes, config,
            content_type="application/zip", commit_message=commit_message,
        )
        if not ok:
            return False, f"资源包上传失败：{msg}", target

        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        ok2, msg2, target2 = self.config_sync_manager.upload_raw_file(
            provider, manifest_obj, manifest_bytes, config,
            content_type="application/json; charset=utf-8", commit_message=commit_message,
        )
        if not ok2:
            return False, f"资源清单上传失败：{msg2}", target2

        return True, f"资源已发布（版本 {manifest['version']}，{len(pack_bytes)} 字节）", f"{target} / {target2}"

    # ====================== 成员端拉取 ======================

    def derive_pack_url(self, manifest_url: str) -> str:
        """由清单 URL 推导同目录下的资源包 URL。"""
        parts = urlsplit(manifest_url)
        path = parts.path.rstrip("/")
        if path.endswith("/" + self.MANIFEST_FILENAME):
            new_path = path[: -len(self.MANIFEST_FILENAME)] + self.PACK_FILENAME
        else:
            slash = path.rfind("/")
            new_path = (path[:slash] if slash >= 0 else "") + "/" + self.PACK_FILENAME
        return urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))

    def check_resources_update(self, manifest_url: str, force: bool = False, download: bool = True,
                               access_token: str = "",
                               oss_credentials: Dict[str, Any] | None = None) -> Tuple[bool, str]:
        """检查资源清单，按需拉取并应用。

        Args:
            manifest_url: 远程资源清单 URL
            force: 忽略版本比较，强制拉取
            download: 是否允许实际下载（False 时仅提示存在新版本）
            access_token: GitHub 只读 PAT（私有仓库）
            oss_credentials: OSS 只读子账号凭据

        Returns:
            (applied, message): applied 表示本次实际应用了新版本。
        """
        manifest = self.config_sync_manager.download_admin_config(
            manifest_url, access_token=access_token, oss_credentials=oss_credentials,
        )
        remote_version = str(manifest.get("version", "") or "")
        if not remote_version:
            raise ValueError("远程资源清单格式不正确，缺少 version 字段。")

        local_version = self.get_local_version()
        if not force and local_version == remote_version:
            return False, "无需更新"

        if not download:
            return False, f"检测到新版本 {remote_version}（未自动下载，可在设置页手动更新）"

        pack_url = self.derive_pack_url(manifest_url)
        pack_meta = manifest.get("pack", {}) or {}
        pack_bytes = self.config_sync_manager.download_raw_bytes(
            pack_url, access_token=access_token, oss_credentials=oss_credentials,
        )

        expected_size = pack_meta.get("size")
        if expected_size is not None:
            try:
                if len(pack_bytes) != int(expected_size):
                    raise ValueError(
                        f"资源包大小与清单不符（期望 {expected_size}，实际 {len(pack_bytes)}），已中止应用。"
                    )
            except (TypeError, ValueError):
                pass
        expected_sha = str(pack_meta.get("sha256", "") or "")
        if expected_sha and hashlib.sha256(pack_bytes).hexdigest() != expected_sha:
            raise ValueError("资源包校验失败（SHA-256 不匹配），已中止应用。")

        ok, message = self.apply_resources_pack(pack_bytes, remote_version)
        return ok, message

    # ====================== 应用与回滚 ======================

    def apply_resources_pack(self, pack_bytes: bytes, version: str = "") -> Tuple[bool, str]:
        """校验并应用资源包到生效目录：备份 -> 覆盖应用 -> 写版本记录 -> 刷新缓存。

        任一环节失败时自动从备份回滚，保证旧资源不被破坏。
        """
        sync_dir = self._sync_dir()
        resources_dir = self._resources_dir()
        sync_dir.mkdir(parents=True, exist_ok=True)
        staging = sync_dir / f"staging_{int(time.time())}"
        stamp = version or str(int(time.time()))
        backup = sync_dir / "backup" / stamp

        try:
            # 1. 解压到 staging（防路径穿越）
            staging.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(pack_bytes)) as zf:
                for member in zf.infolist():
                    name = member.filename.replace("\\", "/")
                    if name.startswith("/") or ".." in Path(name).parts:
                        raise ValueError(f"资源包包含非法路径：{name}")
                zf.extractall(staging)

            # 2. 校验包内 MANIFEST.txt 与逐文件哈希
            inner_manifest_path = staging / "MANIFEST.txt"
            if not inner_manifest_path.exists():
                raise ValueError("资源包缺少 MANIFEST.txt，已中止应用。")
            inner = json.loads(inner_manifest_path.read_text(encoding="utf-8"))
            staged_root = staging.resolve()
            for entry in inner.get("files", []):
                rel = str(entry.get("path", "")).replace("\\", "/")
                fp = (staging / rel).resolve()
                if not fp.is_relative_to(staged_root):
                    raise ValueError(f"资源包包含非法路径：{rel}")
                if not fp.exists():
                    raise ValueError(f"资源包缺少文件：{rel}")
                if hashlib.sha256(fp.read_bytes()).hexdigest() != entry.get("sha256"):
                    raise ValueError(f"资源包文件校验失败：{rel}")

            # 3. 备份当前生效资源（仅 schema/ 与 templates/）
            backup.mkdir(parents=True, exist_ok=True)
            for sub in ("schema", "templates"):
                src_sub = resources_dir / sub
                if src_sub.exists():
                    shutil.copytree(src_sub, backup / sub, dirs_exist_ok=True)

            # 4. 覆盖式应用（覆盖 + 新增，不删除成员端本地多余文件）
            for entry in inner.get("files", []):
                rel = str(entry.get("path", "")).replace("\\", "/")
                target = resources_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staging / rel, target)

            # 5. 写本机已应用版本
            manifest_local = {"version": version, "applied_at": datetime.now().isoformat()}
            self.json_storage.write_json(str(sync_dir / "manifest_local.json"), manifest_local)

            # 6. 刷新模板缓存
            self.template_manager.refresh()
            return True, f"模板与字段资源已更新至 {version or '最新版'}"
        except Exception:
            # 失败回滚
            try:
                self._restore_from_backup(backup, resources_dir)
            except Exception:
                pass
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _restore_from_backup(self, backup: Path, resources_dir: Path) -> None:
        for sub in ("schema", "templates"):
            src_sub = backup / sub
            if src_sub.exists():
                shutil.copytree(src_sub, resources_dir / sub, dirs_exist_ok=True)
        try:
            self.template_manager.refresh()
        except Exception:
            pass
