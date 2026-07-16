#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
模板管理模块

本模块负责文档模板的发现、加载和管理。通过解析 templates_config.json
配置文件（位于 resources/templates/ 目录下）来获取模板元数据，包括
阶段分组、排序和说明信息。

核心职责：
- 读取并解析 templates_config.json 配置文件
- 提供按阶段分组查询模板的能力
- 缓存发现的模板以优化性能
- 提供模板查询和文件路径解析接口
- 校验配置文件的完整性

配置文件格式（resources/templates/templates_config.json）：
    {
        "version": "1.0",
        "stages": [
            {"name": "申请阶段", "order": 1, "description": "..."},
            ...
        ],
        "templates": [
            {
                "file": "入党申请书（本人手写）.docx",
                "name": "入党申请书（本人手写）",
                "stage": "申请阶段",
                "order": 1,
                "description": "..."
            },
            ...
        ]
    }

template_id 由配置项中的 file 字段的文件名（不含扩展名）派生。

Author: 楚乾靖
Date: 2026-07
"""

from pathlib import Path
import json
from src.utils.file_path import get_abs_path


class TemplateManager:
    """模板管理器类。

    通过解析 resources/templates/templates_config.json 配置文件来管理模板。
    若配置文件不存在，则回退到文件系统扫描发现（向后兼容）。

    实例属性：
        templates_dir (Path): 模板目录路径，指向 resources/templates。
        config_path (Path): 配置文件路径，指向 resources/templates/templates_config.json。
        _config (dict | None): 缓存的完整配置字典。
        _discovered_templates (list[dict] | None): 缓存的模板列表。
        _stages (list[dict] | None): 缓存的阶段列表。

    模板字典结构：
        {
            "id": "入党申请书（本人手写）",  # 从 file 字段的 stem 派生
            "file": "入党申请书（本人手写）.docx",
            "name": "入党申请书（本人手写）",
            "enabled": True,
            "stage": "申请阶段",
            "stage_order": 1,
            "description": "..."
        }
    """

    def __init__(self):
        """初始化模板管理器。"""
        self.templates_dir = Path(get_abs_path("resources/templates"))
        self.config_path = self.templates_dir / "templates_config.json"
        self._config = None
        self._discovered_templates = None
        self._stages = None

    # ====================== 配置文件读取 ======================

    def _load_config(self) -> dict | None:
        """读取并缓存 templates_config.json。

        Returns:
            dict | None: 完整的配置字典，若文件不存在或解析失败返回 None。
        """
        if self._config is not None:
            return self._config

        if not self.config_path.exists():
            self._config = None
            return None

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            return self._config
        except (json.JSONDecodeError, IOError):
            self._config = None
            return None

    def _clear_cache(self):
        """清除所有缓存，强制下次重新读取。"""
        self._config = None
        self._discovered_templates = None
        self._stages = None

    # ====================== 模板发现 ======================

    def discover_templates_from_config(self) -> list[dict]:
        """从配置文件发现所有模板。

        解析 templates_config.json 中的 templates 数组，构建模板信息列表。
        id 由 file 字段的文件名（不含扩展名）派生。

        Returns:
            list[dict]: 按 order 排序的模板列表。
        """
        config = self._load_config()
        if config is None:
            return []

        raw_templates = config.get("templates", [])
        if not isinstance(raw_templates, list):
            return []

        templates = []
        for item in raw_templates:
            file_name = str(item.get("file", ""))
            if not file_name:
                continue

            template_id = Path(file_name).stem
            templates.append({
                "id": template_id,
                "file": file_name,
                "name": str(item.get("name", template_id)),
                "enabled": True,
                "stage": str(item.get("stage", "")),
                "stage_order": int(item.get("order", 999)),
                "description": str(item.get("description", "")),
            })

        # 按全局 order 排序
        templates.sort(key=lambda t: t.get("stage_order", 999))
        return templates

    def discover_templates_from_filesystem(self) -> list[dict]:
        """自动从文件系统发现所有模板文件（回退方案）。

        当配置文件不存在时，扫描 resources/templates 目录中的所有 .docx 文件。
        使用文件名（不含扩展名）作为模板 ID 和名称。

        Returns:
            list[dict]: 按文件名排序的模板列表。
        """
        if self._discovered_templates is not None:
            return self._discovered_templates

        # 优先使用配置
        config_templates = self.discover_templates_from_config()
        if config_templates:
            self._discovered_templates = config_templates
            return config_templates

        # 回退：文件系统扫描
        templates = []
        if not self.templates_dir.exists():
            self._discovered_templates = templates
            return templates

        for file_path in sorted(self.templates_dir.glob("*.docx")):
            filename = file_path.name
            template_id = file_path.stem
            templates.append({
                "id": template_id,
                "file": filename,
                "name": template_id,
                "enabled": True,
            })

        self._discovered_templates = templates
        return templates

    def load_templates(self, template_id=None) -> dict | list[dict]:
        """获取模板信息。

        返回指定 ID 的模板，或返回所有发现的模板。优先从配置文件加载，
        若配置文件不存在则回退到文件系统扫描。

        Args:
            template_id (str | None): 要查询的模板 ID。若为 None，返回所有模板。

        Returns:
            dict | list[dict]:
                - 若 template_id 为 None，返回所有模板的列表（按 order 排序）。
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
        """获取模板文件的完整路径。

        Args:
            template_id (str): 模板 ID。

        Returns:
            Path: 模板文件的绝对路径（Path 对象）。
        """
        template = self.load_templates(template_id)
        template_file = template.get('file', '')
        return self.templates_dir / template_file

    # ====================== 阶段分组 ======================

    def get_stages(self) -> list[dict]:
        """获取阶段列表。

        从配置文件中读取 stages 定义，按 order 排序后返回。
        若配置文件不存在，返回空列表。

        Returns:
            list[dict]: 阶段列表，每个阶段包含 name/order/description。
        """
        if self._stages is not None:
            return self._stages

        config = self._load_config()
        if config is None:
            self._stages = []
            return []

        raw_stages = config.get("stages", [])
        if not isinstance(raw_stages, list):
            self._stages = []
            return []

        self._stages = sorted(raw_stages, key=lambda s: s.get("order", 999))
        return self._stages

    def get_templates_grouped_by_stage(self) -> list[dict]:
        """按阶段分组返回模板列表。

        每组包含阶段信息（stage/order/stage_description）和该阶段下的模板列表。

        Returns:
            list[dict]: 按阶段顺序排列的分组列表。每组结构：
                {
                    "stage": "申请阶段",
                    "stage_order": 1,
                    "stage_description": "...",
                    "templates": [
                        {"id": "...", "name": "...", ...},
                        ...
                    ]
                }
        """
        stages = self.get_stages()
        all_templates = self.discover_templates_from_filesystem()

        # 构建阶段名到阶段信息的映射
        stage_map = {s["name"]: s for s in stages}

        # 收集每个阶段下的模板
        stage_template_map: dict[str, list[dict]] = {}
        for stage in stages:
            stage_template_map[stage["name"]] = []

        # 将没有归属阶段的模板归入"未分组"
        ungrouped = []

        for tpl in all_templates:
            stage_name = tpl.get("stage", "")
            if stage_name in stage_template_map:
                stage_template_map[stage_name].append(tpl)
            else:
                ungrouped.append(tpl)

        # 每个阶段内的模板按 stage_order 排序
        result = []
        for stage in stages:
            name = stage["name"]
            templates_in_stage = stage_template_map.get(name, [])
            templates_in_stage.sort(key=lambda t: t.get("stage_order", 999))
            result.append({
                "stage": name,
                "stage_order": stage.get("order", 999),
                "stage_description": stage.get("description", ""),
                "templates": templates_in_stage,
            })

        # 未分组的模板追加到最后
        if ungrouped:
            result.append({
                "stage": "未分组",
                "stage_order": 999,
                "stage_description": "",
                "templates": ungrouped,
            })

        return result

    # ====================== 配置校验 ======================

    def validate_config(self) -> list[str]:
        """校验配置文件的完整性。

        检查内容：
        - 配置文件是否存在且为合法的 JSON
        - stages 和 templates 是否为有效数组
        - 每个 template 的 file 字段对应的文件是否存在
        - 每个 template 的 stage 是否在 stages 中定义
        - order 是否唯一

        Returns:
            list[str]: 错误信息列表。若为空则表示配置无误。
        """
        errors: list[str] = []
        config = self._load_config()

        if config is None:
            if not self.config_path.exists():
                errors.append(f"配置文件不存在：{self.config_path}")
            else:
                errors.append(f"配置文件格式错误：{self.config_path}")
            return errors

        # 检查 stages
        stages = config.get("stages", [])
        if not isinstance(stages, list):
            errors.append("stages 必须是数组")
            stages = []
        if not stages:
            errors.append("stages 为空，至少需要一个阶段")

        stage_names = {s.get("name", "") for s in stages if isinstance(s, dict)}

        # 检查 templates
        raw_templates = config.get("templates", [])
        if not isinstance(raw_templates, list):
            errors.append("templates 必须是数组")
            raw_templates = []

        if not raw_templates:
            errors.append("templates 为空，至少需要一个模板")

        order_set: set[int] = set()
        for idx, item in enumerate(raw_templates):
            if not isinstance(item, dict):
                errors.append(f"templates[{idx}] 必须是对象")
                continue

            file_name = item.get("file", "")
            if not file_name:
                errors.append(f"templates[{idx}] 缺少 file 字段")
                continue

            # 检查文件是否存在
            file_path = self.templates_dir / file_name
            if not file_path.exists():
                errors.append(f"模板文件不存在：{file_name}")

            # 检查 stage 是否已定义
            stage_name = item.get("stage", "")
            if stage_name and stage_name not in stage_names:
                errors.append(f"模板 \"{file_name}\" 的 stage \"{stage_name}\" 未在 stages 中定义")

            # 检查 order 唯一性
            order = item.get("order")
            if order is not None:
                if order in order_set:
                    errors.append(f"模板 \"{file_name}\" 的 order={order} 重复")
                order_set.add(order)

        return errors
