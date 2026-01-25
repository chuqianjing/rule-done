#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板管理
"""

from pathlib import Path
import re

from src.utils.json_storage import JSONStorage


class TemplateManager:
    """模板管理器类"""
    
    def __init__(self):
        self.templates_config_path = Path("resources/templates_config.json")
        self.templates_dir = Path("resources/templates")
        self.json_storage = JSONStorage()
        self._templates_config = None
        self._auto_discovered_templates = None  # 缓存自动发现的模板
    
    def load_templates_config(self):
        """加载模板配置"""
        if self._templates_config is None:
            if self.templates_config_path.exists():
                self._templates_config = self.json_storage.read_json(str(self.templates_config_path))
            else:
                self._templates_config = {"version": "1.0", "templates": []}
        return self._templates_config
    
    def discover_templates_from_filesystem(self) -> list[dict]:
        """
        自动从文件系统发现所有模板文件
        返回格式：[
            {
                "id": "template_001",
                "file": "template_001_入党申请书.docx",
                "name": "入党申请书",  # 从文件名提取或使用默认
                "auto_discovered": True  # 标记为自动发现
            },
            ...
        ]
        """
        if self._auto_discovered_templates is not None:
            return self._auto_discovered_templates
        
        templates = []
        if not self.templates_dir.exists():
            self._auto_discovered_templates = templates
            return templates
        
        # 扫描所有 .docx 文件
        for file_path in self.templates_dir.glob("*.docx"):
            filename = file_path.name
            
            # 尝试从文件名提取 ID 和名称
            # 格式：template_{ID}_{名称}.docx
            match = re.match(r"template_(\w+)_(.+)\.docx", filename)
            if match:
                template_id = f"template_{match.group(1)}"
                name = match.group(2)
            else:
                # 如果格式不匹配，使用文件名（不含扩展名）作为 ID
                template_id = file_path.stem
                name = file_path.stem
            
            templates.append({
                "id": template_id,
                "file": filename,
                "name": name,
                "auto_discovered": True,
                "enabled": True
            })
        
        self._auto_discovered_templates = templates
        return templates
    
    def get_all_templates(self) -> list[dict]:
        """
        获取所有模板（合并 JSON 配置和自动发现的模板）
        优先级：JSON 配置 > 自动发现的模板
        """
        # 加载 JSON 配置
        json_config = self.load_templates_config()
        json_templates = {t["id"]: t for t in json_config.get("templates", [])}
        
        # 自动发现模板
        discovered_templates = self.discover_templates_from_filesystem()
        
        # 合并：JSON 配置优先，自动发现的作为补充
        all_templates = []
        discovered_ids = set()
        
        # 先添加 JSON 配置的模板
        for template in json_config.get("templates", []):
            template_id = template.get("id")
            if template.get("enabled", True):
                all_templates.append(template)
                discovered_ids.add(template_id)
        
        # 再添加自动发现但不在 JSON 中的模板
        for template in discovered_templates:
            template_id = template.get("id")
            if template_id not in discovered_ids:
                all_templates.append(template)
        
        return all_templates
    
    def get_template(self, template_id):
        """获取模板信息（支持自动发现的模板）"""
        # 先尝试从 JSON 配置获取
        config = self.load_templates_config()
        templates = config.get('templates', [])
        
        for template in templates:
            if template.get('id') == template_id:
                return template
        
        # 如果 JSON 中没有，尝试从自动发现的模板获取
        discovered = self.discover_templates_from_filesystem()
        for template in discovered:
            if template.get('id') == template_id:
                return template
        
        raise ValueError(f"模板 {template_id} 不存在")
    
    def get_template_file_path(self, template_id):
        """获取模板文件路径"""
        template = self.get_template(template_id)
        template_file = template.get('file', '')
        return self.templates_dir / template_file
    
    def get_template_fields(self, template_id):
        """获取模板字段列表（已废弃，保留以兼容旧代码）"""
        # 不再从配置中读取，改为从模板文件自动解析
        return []
    
    def get_field_mapping(self, template_id):
        """获取字段映射关系（已废弃，保留以兼容旧代码）"""
        # 不再从配置中读取，改为自动映射
        return {}
    
    def list_available_templates(self):
        """列出所有可用模板（包括自动发现的）"""
        return self.get_all_templates()

