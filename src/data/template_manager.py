#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板管理
"""

from pathlib import Path

from src.utils.json_storage import JSONStorage


class TemplateManager:
    """模板管理器类"""
    
    def __init__(self):
        self.templates_config_path = Path("resources/templates_config.json")
        self.templates_dir = Path("resources/templates")
        self.json_storage = JSONStorage()
        self._templates_config = None
    
    def load_templates_config(self):
        """加载模板配置"""
        if self._templates_config is None:
            if self.templates_config_path.exists():
                self._templates_config = self.json_storage.read_json(str(self.templates_config_path))
            else:
                self._templates_config = {"version": "1.0", "templates": []}
        return self._templates_config
    
    def get_template(self, template_id):
        """获取模板信息"""
        config = self.load_templates_config()
        templates = config.get('templates', [])
        
        for template in templates:
            if template.get('id') == template_id:
                return template
        
        raise ValueError(f"模板 {template_id} 不存在")
    
    def get_template_file_path(self, template_id):
        """获取模板文件路径"""
        template = self.get_template(template_id)
        template_file = template.get('file', '')
        return self.templates_dir / template_file
    
    def get_template_fields(self, template_id):
        """获取模板字段列表"""
        template = self.get_template(template_id)
        return template.get('fields', [])
    
    def get_field_mapping(self, template_id):
        """获取字段映射关系"""
        template = self.get_template(template_id)
        return template.get('field_mapping', {})
    
    def list_available_templates(self):
        """列出所有可用模板"""
        config = self.load_templates_config()
        templates = config.get('templates', [])
        
        # 只返回启用的模板
        return [t for t in templates if t.get('enabled', True)]

