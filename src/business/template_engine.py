#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板引擎
"""

import os
from pathlib import Path
import re

try:
    from docxtpl import DocxTemplate
    USE_DOCXTPL = True
except ImportError:
    from docx import Document
    USE_DOCXTPL = False

from src.data.template_manager import TemplateManager
from src.business.data_manager import DataManager


class TemplateEngine:
    """模板引擎类"""
    
    def __init__(self):
        self.template_manager = TemplateManager()
        self.data_manager = DataManager()
        self._common_fields_cache = None
        self._basic_fields_cache = None
        self._admin_fields_cache = None
    
    def generate_document(self, template_id, output_path):
        """生成 Word 文档"""
        # 1. 获取模板文件路径
        template_info = self.template_manager.get_template(template_id)
        template_file = template_info.get('file', '')
        template_path = Path("resources/templates") / template_file
        
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        # 2. 合并数据
        data = self.data_manager.merge_data_for_template(template_id)
        
        # 3. 生成文档
        if USE_DOCXTPL:
            return self._generate_with_docxtpl(template_path, data, output_path)
        else:
            return self._generate_with_docx(template_path, data, output_path)

    def get_placeholders(self, template_id: str) -> set[str]:
        """解析并返回模板中出现的所有占位符变量名（不含花括号）"""
        template_info = self.template_manager.get_template(template_id)
        template_file = template_info.get("file", "")
        template_path = Path("resources/templates") / template_file

        if not template_path.exists():
            return set()

        # 为了兼容，无论是否使用 docxtpl，这里都直接用 python-docx 解析结构
        if USE_DOCXTPL:
            from docx import Document as DocxDocument
            doc = DocxDocument(str(template_path))
        else:
            doc = Document(str(template_path))

        placeholders: set[str] = set()

        # 段落中的占位符
        for paragraph in doc.paragraphs:
            for match in re.findall(r"{{(.*?)}}", paragraph.text):
                placeholders.add(match.strip())

        # 表格中的占位符
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for match in re.findall(r"{{(.*?)}}", cell.text):
                        placeholders.add(match.strip())

        return placeholders
    
    def _load_common_template_fields(self) -> list[dict]:
        """加载通用模板字段定义"""
        if self._common_fields_cache is not None:
            return self._common_fields_cache
        
        from pathlib import Path
        import json
        
        fields_path = Path("resources/fields_definition.json")
        if not fields_path.exists():
            self._common_fields_cache = []
            return []
        
        try:
            with open(fields_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self._common_fields_cache = config.get("common_template_fields", [])
                return self._common_fields_cache
        except:
            self._common_fields_cache = []
            return []
    
    def _load_basic_info_fields(self) -> list[dict]:
        """加载基础信息字段定义"""
        if self._basic_fields_cache is not None:
            return self._basic_fields_cache
        
        from pathlib import Path
        import json
        
        fields_path = Path("resources/fields_definition.json")
        if not fields_path.exists():
            self._basic_fields_cache = []
            return []
        
        try:
            with open(fields_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self._basic_fields_cache = config.get("basic_info_fields", [])
                return self._basic_fields_cache
        except:
            self._basic_fields_cache = []
            return []
    
    def _load_admin_fields(self) -> list[dict]:
        """加载管理员字段定义"""
        if self._admin_fields_cache is not None:
            return self._admin_fields_cache
        
        from pathlib import Path
        import json
        
        fields_path = Path("resources/fields_definition.json")
        if not fields_path.exists():
            self._admin_fields_cache = []
            return []
        
        try:
            with open(fields_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                admin_groups = config.get("admin_fields", [])
                # 展平所有管理员字段
                fields = []
                for group in admin_groups:
                    fields.extend(group.get("fields", []))
                self._admin_fields_cache = fields
                return self._admin_fields_cache
        except:
            self._admin_fields_cache = []
            return []
    
    def get_field_definition_for_placeholder(self, placeholder: str) -> dict:
        """
        为占位符获取字段定义（优先从通用字段库匹配）
        返回字段定义，如果未找到则返回默认定义
        """
        # 1. 从通用字段库中查找
        common_fields = self._load_common_template_fields()
        for field_def in common_fields:
            if field_def.get("key") == placeholder:
                return field_def
        
        # 2. 从基础信息字段中查找
        basic_fields = self._load_basic_info_fields()
        for field_def in basic_fields:
            if field_def.get("key") == placeholder:
                return field_def
        
        # 3. 从管理员字段中查找（通过 key 或 path 的最后一部分）
        admin_fields = self._load_admin_fields()
        for field_def in admin_fields:
            admin_key = field_def.get("key", "")
            path = field_def.get("path", "")
            path_parts = path.split(".") if path else []
            last_part = path_parts[-1] if path_parts else ""
            
            if placeholder == admin_key or placeholder == last_part:
                # 返回一个适配的字段定义
                return {
                    "key": placeholder,
                    "type": field_def.get("type", "text"),
                    "required": field_def.get("required", False),
                    "display": field_def.get("display", {"label": placeholder})
                }
        
        # 4. 默认字段定义
        return {
            "key": placeholder,
            "type": "text",
            "required": False,
            "display": {
                "label": placeholder,
                "order": 999
            }
        }
    
    def auto_map_placeholders(self, template_id: str) -> dict:
        """
        自动映射占位符到数据源
        返回格式：{
            "{{姓名}}": {
                "source": "basic_info",
                "field": "姓名",
                "auto_mapped": True
            },
            ...
        }
        """
        placeholders = self.get_placeholders(template_id)
        mapping = {}
        
        # 加载已知字段定义
        basic_fields = self._load_basic_info_fields()
        admin_fields = self._load_admin_fields()
        common_fields = self._load_common_template_fields()
        
        basic_keys = {f.get("key") for f in basic_fields}
        common_keys = {f.get("key") for f in common_fields}
        
        # 构建管理员字段映射表（key -> path）
        admin_key_to_path = {}
        for admin_field in admin_fields:
            key = admin_field.get("key", "")
            path = admin_field.get("path", "")
            if key:
                admin_key_to_path[key] = path
            # 也支持通过 path 的最后一部分匹配
            if path:
                path_parts = path.split(".")
                last_part = path_parts[-1] if path_parts else ""
                if last_part and last_part not in admin_key_to_path:
                    admin_key_to_path[last_part] = path
        
        # 智能匹配
        for placeholder in placeholders:
            # 1. 尝试匹配基础信息字段
            if placeholder in basic_keys:
                mapping[f"{{{{{placeholder}}}}}"] = {
                    "source": "basic_info",
                    "field": placeholder,
                    "auto_mapped": True
                }
                continue
            
            # 2. 尝试匹配管理员配置字段
            if placeholder in admin_key_to_path:
                mapping[f"{{{{{placeholder}}}}}"] = {
                    "source": "admin_config",
                    "path": admin_key_to_path[placeholder],
                    "auto_mapped": True
                }
                continue
            
            # 3. 尝试匹配通用模板字段
            if placeholder in common_keys:
                mapping[f"{{{{{placeholder}}}}}"] = {
                    "source": "template_data",
                    "template_id": template_id,
                    "field": placeholder,
                    "auto_mapped": True
                }
                continue
            
            # 4. 默认作为模板特有字段
            mapping[f"{{{{{placeholder}}}}}"] = {
                "source": "template_data",
                "template_id": template_id,
                "field": placeholder,
                "auto_mapped": True
            }
        
        return mapping
    
    def _generate_with_docxtpl(self, template_path, data, output_path):
        """使用 docxtpl 生成文档"""
        doc = DocxTemplate(str(template_path))
        print(data)
        doc.render(data)
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        
        return output_path
    
    def _generate_with_docx(self, template_path, data, output_path):
        """使用纯 python-docx 生成文档（备选方案）"""
        import re
        
        doc = Document(str(template_path))
        
        # 替换段落中的占位符
        for paragraph in doc.paragraphs:
            for key, value in data.items():
                placeholder = f"{{{{{key}}}}}"
                if placeholder in paragraph.text:
                    paragraph.text = paragraph.text.replace(placeholder, str(value))
        
        # 替换表格中的占位符
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for key, value in data.items():
                        placeholder = f"{{{{{key}}}}}"
                        if placeholder in cell.text:
                            cell.text = cell.text.replace(placeholder, str(value))
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        
        return output_path

