#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板引擎
"""

from docxtpl import DocxTemplate
from docx import Document
from src.data.template_manager import TemplateManager
from src.business.data_manager import DataManager
import os
import re


class TemplateEngine:
    """模板引擎类"""
    
    def __init__(self):
        self.template_manager = TemplateManager()
        self.data_manager = DataManager()
        self._admin_fields_cache, self._basic_fields_cache, _ = self.data_manager.get_fields(src='template')

    # ======================== 模板占位符解析与映射 =========================

    def get_placeholders(self, template_id: str) -> set[str]:
        """解析并返回模板中出现的所有占位符变量名（不含花括号）"""
        template_path = self.template_manager.get_template_file_path(template_id)

        if not template_path.exists():
            return set()

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
        basic_fields, admin_fields = self._basic_fields_cache, self._admin_fields_cache
        basic_keys = {f.get("key") for f in basic_fields}
        
        # 构建管理员字段映射表（key -> (group, key)）
        admin_key_to_group_key = {}
        for admin_field in admin_fields:
            key = admin_field.get("key", "")
            group = admin_field.get("group", "")
            if key:
                admin_key_to_group_key[key] = (group, key)
        
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
            if placeholder in admin_key_to_group_key:
                group, key = admin_key_to_group_key[placeholder]
                mapping[f"{{{{{placeholder}}}}}"] = {
                    "source": "admin_config",
                    "group": group,
                    "key": key,
                    "auto_mapped": True
                }
                continue
            
            # 3. 默认作为模板特有字段
            mapping[f"{{{{{placeholder}}}}}"] = {
                "source": "template_data",
                "template_id": template_id,
                "field": placeholder,
                "auto_mapped": True
            }
        
        return mapping
    
    # ======================== 合并有关数据 =========================

    def merge_data_for_template(self, template_id):
        """合并数据用于模板生成（方案C：混合模式）"""
        merged_data = {}
        
        # 1. 加载管理员配置
        admin_config = self.data_manager.get_admin_config()
        
        # 2. 加载成员数据
        member_info = self.data_manager.get_member_info()
        
        # 3. 获取字段映射（优先使用 JSON 配置，否则使用自动映射）
        template_config = self.template_manager.load_templates(template_id)
        field_mapping = template_config.get('field_mapping', {})
        
        # 如果 JSON 中没有映射配置，使用自动映射
        if not field_mapping:
            field_mapping = self.auto_map_placeholders(template_id)
        
        # 4. 根据映射合并数据
        #    已配置映射的占位符优先按照映射规则取值
        for placeholder, mapping in field_mapping.items():
            key = placeholder.strip('{}')
            value = self._get_value_by_mapping(mapping, admin_config, member_info)
            merged_data[key] = value

        # 5. 获取管理员配置的模板字段
        admin_template_data = admin_config.get("template_data", {}).get(template_id, {})
        
        # 6. 注入模板数据中所有未映射的字段（应用方案C混合模式）
        tpl_data = member_info.get('template_data', {}).get(template_id, {})
        for k, v in tpl_data.items():
            if k not in merged_data:
                # 检查管理员是否配置并锁定了该字段
                admin_field_config = admin_template_data.get(k, {})
                if isinstance(admin_field_config, dict):
                    is_locked = admin_field_config.get("locked", False)
                    admin_value = admin_field_config.get("value", "")
                else:
                    # 兼容旧格式（直接存储值）
                    is_locked = False
                    admin_value = admin_field_config if admin_field_config else ""
                
                if is_locked and admin_value:
                    # 字段被锁定，使用管理员配置的值
                    merged_data[k] = admin_value
                else:
                    # 字段未锁定，优先使用成员数据
                    merged_data[k] = v if v else admin_value
        
        # 7. 补充管理员配置但成员未填写的字段
        for k, admin_field_config in admin_template_data.items():
            if k not in merged_data:
                if isinstance(admin_field_config, dict):
                    merged_data[k] = admin_field_config.get("value", "")
                else:
                    merged_data[k] = admin_field_config if admin_field_config else ""
        
        return merged_data
    
    def _get_value_by_mapping(self, mapping, admin_config, member_info):
        """根据映射获取值"""
        source = mapping.get('source')
        
        if source == 'basic_info':
            field = mapping.get('field')
            return member_info.get('basic_data', {}).get(field, '')
        
        elif source == 'admin_config':
            # 使用 group + key 从管理员配置中获取值
            group = mapping.get('group', '')
            key = mapping.get('key', '')
            return admin_config.get("basic_data", {}).get(group, {}).get(key, '')
        
        elif source == 'template_data':
            template_id = mapping.get('template_id')
            field = mapping.get('field')
            return member_info.get('template_data', {}).get(template_id, {}).get(field, '')
        
        return ''
    
    # ======================== 生成模板 =========================
    
    def generate_document(self, template_id, output_path):
        """生成 Word 文档"""
        # 1. 获取模板文件路径
        template_path = self.template_manager.get_template_file_path(template_id)
        
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        # 2. 合并数据
        data = self.merge_data_for_template(template_id)
        
        # 3. 生成文档
        return self._generate_with_docxtpl(template_path, data, output_path)
    
    def _generate_with_docxtpl(self, template_path, data, output_path):
        """使用 docxtpl 生成文档"""
        doc = DocxTemplate(str(template_path))
        doc.render(data)

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        
        return output_path
    

