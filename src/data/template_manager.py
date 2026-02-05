#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板管理

当前版本彻底舍弃了 templates_config.json，
仅通过扫描 resources/templates 目录中的 .docx 文件来管理模板。
"""

from pathlib import Path
import re


class TemplateManager:
    """模板管理器类（基于文件系统自动发现模板）"""

    def __init__(self):
        self.templates_dir = Path("resources/templates")
        self._auto_discovered_templates = None  # 缓存自动发现的模板
    
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
        获取所有模板

        说明：
        - 早期版本会“JSON 配置 + 自动发现”合并；
        - 现在已经完全舍弃 templates_config.json，
          因此这里直接返回自动发现的模板列表，
          行为上等价于“只有自动发现部分生效”。
        """
        return self.discover_templates_from_filesystem()
    
    def get_template(self, template_id):
        """获取模板信息（仅基于自动发现的模板）"""
        discovered = self.discover_templates_from_filesystem()
        for template in discovered:
            if template.get("id") == template_id:
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

