#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板引擎
"""

import os
from pathlib import Path

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
    
    def _generate_with_docxtpl(self, template_path, data, output_path):
        """使用 docxtpl 生成文档"""
        doc = DocxTemplate(str(template_path))
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

