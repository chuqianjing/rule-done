#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
模板管理模块

本模块负责文档模板的自动发现、加载和管理。当前版本采用文件系统扫描机制，
通过扫描 resources/templates 目录中的 .docx 文件来动态管理模板。

核心职责：
- 自动从文件系统发现所有模板文件
- 解析模板文件名并提取模板 ID 和名称
- 缓存发现的模板以优化性能
- 提供模板查询和文件路径解析接口

文件命名规范：
- 推荐格式：template_{ID}_{名称}.docx（例如：template_001_入党申请书.docx）
- 其他格式：{任意名称}.docx（ID 和名称将使用文件名作为备选）

模板目录：resources/templates/
缓存策略：发现的模板列表在内存中缓存，避免重复扫描文件系统。

Author: 楚乾靖
Date: 2026-03
"""

from pathlib import Path
import re
from src.utils.file_path import get_abs_path


class TemplateManager:
    """模板管理器类。

    负责管理文档模板的生命周期，采用文件系统自动发现机制。从 resources/templates/
    目录扫描所有 .docx 文件，支持模板查询、获取和缓存管理。

    实例属性：
        templates_dir (Path): 模板目录路径，指向 resources/templates。
        _discovered_templates (list[dict] | None): 缓存的发现模板列表，
            首次调用发现方法时会初始化，后续查询使用缓存提高性能。

    缓存的模板结构：
        [
            {
                "id": "1",                          # 模板 ID（从文件名提取或使用文件名）
                "file": "template_001_入党申请书.docx",  # 模板文件名
                "name": "入党申请书",               # 模板显示名称
                "enabled": True                     # 模板是否启用
            },
            ...
        ]
    """

    def __init__(self):
        """初始化模板管理器。

        创建模板目录路径引用并初始化缓存为 None。
        """
        # self.templates_dir = Path("resources/templates")
        self.templates_dir = Path(get_abs_path("resources/templates"))
        self._discovered_templates = None  # 缓存发现的模板
    
    def discover_templates_from_filesystem(self) -> list[dict]:
        """自动从文件系统发现所有模板文件

        扫描 resources/templates 目录中的所有 .docx 文件，解析文件名并
        构建模板信息字典。首次调用时从文件系统扫描，后续调用返回缓存结果。

        文件名解析规则：
        - 若匹配 template_{ID}_{名称}.docx 模式，提取 ID 和名称
        - 否则使用文件名（不含扩展名）作为 ID 和名称

        Returns:
            list[dict]: 发现的模板列表。每个模板是一个字典，包含：
                - id (str): 模板 ID（数字字符串或文件名）
                - file (str): 模板文件名
                - name (str): 模板显示名称
                - enabled (bool): 始终为 True
        """
        if self._discovered_templates is not None:
            return self._discovered_templates
        
        templates = []
        if not self.templates_dir.exists():
            self._discovered_templates = templates
            return templates
        
        # 扫描所有 .docx 文件
        for file_path in self.templates_dir.glob("*.docx"):
            filename = file_path.name
            
            # 尝试从文件名提取 ID 和名称
            # 格式：template_{ID}_{名称}.docx
            match = re.match(r"template_(\d+)_(.+)\.docx", filename)
            if match:
                #template_id = f"template_{match.group(1)}"
                template_id = str(int(match.group(1)))
                name = match.group(2)
            else:
                # 如果格式不匹配，使用文件名（不含扩展名）作为 ID
                template_id = file_path.stem
                name = file_path.stem
            
            templates.append({
                "id": template_id,
                "file": filename,
                "name": name,
                "enabled": True
            })
        
        self._discovered_templates = templates
        return templates
    
    def load_templates(self, template_id=None) -> dict | list[dict]:
        """获取模板信息

        返回指定 ID 的模板，或返回所有发现的模板。使用 discover_templates_from_filesystem()
        获取模板列表，如果指定了 template_id 则查询单个模板。

        Args:
            template_id (str | None): 要查询的模板 ID。若为 None，返回所有模板。

        Returns:
            dict | list[dict]: 
                - 若 template_id 为 None，返回所有模板的列表。
                - 若 template_id 不为 None，返回匹配的模板字典。
        """
        discovered = self.discover_templates_from_filesystem()
        if template_id is None:
            return discovered
        for template in discovered:
            if template.get("id") == template_id:
                return template
        
        raise ValueError(f"模板 {template_id} 不存在")
    
    def get_template_file_path(self, template_id: str) -> Path:
        """获取模板文件的完整路径

        根据模板 ID 查询模板并返回其在文件系统中的完整路径。该路径可直接用于
        文件操作（如打开、读取等）。

        Args:
            template_id (str): 模板 ID。

        Returns:
            Path: 模板文件的绝对路径（Path 对象）。
        """
        template = self.load_templates(template_id)
        template_file = template.get('file', '')
        return self.templates_dir / template_file
    
    