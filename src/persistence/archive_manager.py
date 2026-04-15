#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
档案图片持久化管理模块

负责成员档案图片的本地存储，包括：
1. 图片格式校验
2. 目录管理与文件复制
3. 同名冲突处理（覆盖/自动重命名）
"""

from datetime import datetime
from pathlib import Path
import mimetypes
import shutil
from src.utils.file_path import get_runtime_data_dir


class ArchiveManager:
    """档案图片文件管理器"""

    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    def __init__(self):
        self.base_dir = get_runtime_data_dir() / "archive_images"

    def _sanitize_template_id(self, template_id: str) -> str:
        """将模板ID转换为安全目录名"""
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in template_id)
        return safe or "default"

    def _template_dir(self, template_id: str) -> Path:
        """获取模板对应的图片目录"""
        return self.base_dir / self._sanitize_template_id(template_id)

    def _validate_image(self, source_path: Path):
        """校验图片文件是否存在且扩展名合法"""
        if not source_path.exists():
            raise FileNotFoundError(f"图片文件不存在: {source_path}")
        if not source_path.is_file():
            raise ValueError(f"无效的图片文件: {source_path}")

        ext = source_path.suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError("仅支持 JPG/JPEG/PNG/BMP/WEBP 图片格式")

    def _build_unique_path(self, target_path: Path) -> Path:
        """为目标文件构建不冲突的文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = target_path.stem
        suffix = target_path.suffix
        return target_path.with_name(f"{stem}_{timestamp}{suffix}")

    def save_image(
        self,
        source_file_path: str,
        template_id: str,
        overwrite: bool = False,
        auto_rename: bool = False,
    ) -> dict:
        """保存图片到本地目录

        Args:
            source_file_path (str): 源图片路径
            template_id (str): 模板ID
            overwrite (bool): 是否覆盖同名文件
            auto_rename (bool): 同名时是否自动重命名

        Returns:
            dict: 包含保存后的图片元数据

        Raises:
            FileExistsError: 目标文件存在且未允许覆盖/重命名
            ValueError: 入参或文件格式不合法
            IOError: 文件复制失败
        """
        if overwrite and auto_rename:
            raise ValueError("overwrite 和 auto_rename 不能同时为 True")

        source_path = Path(source_file_path)
        self._validate_image(source_path)

        target_dir = self._template_dir(template_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / source_path.name
        if target_path.exists():
            if overwrite:
                pass
            elif auto_rename:
                target_path = self._build_unique_path(target_path)
            else:
                raise FileExistsError(f"目标文件已存在: {target_path}")

        try:
            shutil.copy2(source_path, target_path)
        except Exception as e:
            raise IOError(f"图片保存失败: {e}")

        mime_type = mimetypes.guess_type(str(target_path))[0] or "application/octet-stream"
        return {
            "file_name": target_path.name,
            "relative_path": str(target_path.as_posix()),
            "uploaded_at": datetime.now().isoformat(),
            "size_bytes": target_path.stat().st_size,
            "mime_type": mime_type,
        }

    def delete_image(self, relative_path: str) -> bool:
        """删除已保存的档案图片

        Args:
            relative_path (str): 图片相对路径（记录在 member_info.json）。

        Returns:
            bool: 文件存在且删除成功返回 True；文件不存在返回 False。

        Raises:
            ValueError: 目标路径不在档案目录下，或目标不是文件。
            IOError: 删除文件失败。
        """
        target = Path(relative_path)
        target_resolved = target.resolve()
        base_resolved = self.base_dir.resolve()

        try:
            target_resolved.relative_to(base_resolved)
        except ValueError:
            raise ValueError(f"仅允许删除 {self.base_dir.as_posix()} 目录下的文件")

        if not target_resolved.exists():
            return False
        if not target_resolved.is_file():
            raise ValueError(f"无效的图片文件: {target_resolved}")

        try:
            target_resolved.unlink()
            return True
        except Exception as e:
            raise IOError(f"删除图片失败: {e}")
