#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模板引擎
"""

from docxtpl import DocxTemplate
from docx import Document
from src.persistence.template_manager import TemplateManager
from src.application.data_manager import DataManager
import os
import re
from datetime import datetime
from pathlib import Path


class TemplateEngine:
    """模板引擎类"""
    
    def __init__(self):
        self.template_manager = TemplateManager()
        self.data_manager = DataManager()
        self._admin_fields_cache, self._member_fields_cache, self._template_fields_cache = self.data_manager.get_fields(src='template')
    
    # ======================== 获取模板元数据 =========================
    
    def get_templates(self, template_id=None):
        return self.template_manager.load_templates(template_id)

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
    
    def match_placehoder_def(self, placeholder: str, ) -> dict:
        for field_def in self._template_fields_cache:
            if field_def.get("is_default"):
                continue
            keywords = field_def.get("match_keywords", [])
            for keyword in keywords:
                if keyword in placeholder:
                    return {
                        "key": placeholder,
                        "type": field_def.get("type", "text"),
                        "required": field_def.get("required", False),
                        "format": field_def.get("format"),       # 这里应该先行考虑下“年月”时的处理方式
                        "display": field_def.get("display", {}),
                    }

        # 如果没有匹配，返回默认定义
        default_def = next((f for f in self._template_fields_cache if f.get("is_default")), None)
        if default_def:
            return {
                "key": placeholder,
                "type": default_def.get("type", "text"),
                "required": default_def.get("required", False),
                "display": default_def.get("display", {}),
            }

        return {
            "key": placeholder,
            "type": "text",
            "required": False,
            "display": {"order": 999},
        }
    
    # placeholder_mapping用于模板页的专有项字段构建、数据加载、文件生成
    def map_placeholders_to_data(self, template_id: str) -> dict:
        """
        自动映射占位符到数据源
        返回格式：{
            "{{姓名}}": {
                "source": "member_info",   # 数据文件
                "key": "姓名",             # 该placeholder对应的数据字段的键
            },
            ...
        }
        """
        placeholders = self.get_placeholders(template_id)
        mapping = {}

        member_template_data = self.data_manager.get_member_info("template_data", template_id) or {}
        admin_template_data = self.data_manager.get_admin_config("template_data", template_id) or {}
        
        # 加载成员和管理员定义字段的键
        member_fields, admin_fields = self._member_fields_cache, self._admin_fields_cache

        member_keys = {f.get("key") for f in member_fields}
        admin_keys = {}     # 构建管理员字段键（key -> (group, key)）
        for admin_field in admin_fields:
            key = admin_field.get("key", "")
            group = admin_field.get("group", "")
            if key:
                admin_keys[key] = (group, key)

        
        member_template_version = member_template_data.get("version")
        admin_template_version = self.data_manager.get_admin_config("version")
        subject_to_member_template = False     # True表示以member_template_data为准，False表示以目前的数据映射逻辑处理方式为准
        # 比较两个version的时间大小关系
        if member_template_version and admin_template_version:
            member_version_time = datetime.strptime(member_template_version, "%Y.%m")
            admin_version_time = datetime.strptime(admin_template_version, "%Y.%m")
            if member_version_time < admin_version_time:
                subject_to_member_template = True



        # 匹配
        for placeholder in placeholders:
            '''
            先成员再管理员的逻辑可实现：当成员和管理员的basic_data都有以当前placeholder为键的项，则优先显示成员的
            '''

            # 1、尝试与成员的基本字段来匹配
            if placeholder in member_keys:
                mapping[placeholder] = {
                    "source": "member_basic_data",
                    "key": placeholder,
                    "order": next((f.get("display", {}).get("order", 999) for f in member_fields if f.get("key") == placeholder), 999),
                }
                continue
            if placeholder == "出生年月":
                mapping[placeholder] = {
                    "source": "member_basic_data",
                    "key": "出生日期",
                    "order": next((f.get("display", {}).get("order", 999) for f in member_fields if f.get("key") == "出生日期"), 999),
                    "format": "YYYY年MM月",
                }
                continue
            # 2、尝试与管理员的基本字段来匹配
            if placeholder in admin_keys:
                group, key = admin_keys[placeholder]
                mapping[placeholder] = {
                    "source": "admin_basic_data",
                    "group": group,
                    "key": key,
                    # "order": next((f.get("display", {}).get("order", 999) for f in admin_fields if f.get("这里得用group-field啥的").get("key") == placeholder), 999),   placeholder属于管理员基本字段的比较少，就不用排序了
                }
                continue

            '''
            模板特有字段的数据源，仅发挥作用在member_template_page中（admin_template_page直接显示admin_config自己的）
            '''
            # 模板特有占位符
            if subject_to_member_template:
                mapping[placeholder] = {
                    "source": "member_template_data",
                }
                continue


            member_value = member_template_data.get(placeholder, "")

            admin_field_config = admin_template_data.get(placeholder, {})
            admin_value = admin_field_config.get("value", "")
            is_locked = admin_field_config.get("locked", False)

            if is_locked:
                mapping[placeholder] = {
                    "source": "admin_template_data",
                    "is_tip": False,
                }
            elif admin_value and not member_value:
                 mapping[placeholder] = {
                    "source": "admin_template_data",
                    "is_tip": True,
                }
            else:
                mapping[placeholder] = {
                    "source": "member_template_data",
                }

        return mapping
    
    # ======================== 合并有关数据 =========================

    def merge_data_for_template(self, template_id):
        """合并数据用于模板生成"""
        merged_data = {}

        admin_config = self.data_manager.get_admin_config()
        member_info = self.data_manager.get_member_info()
        
        placeholder_mapping = self.map_placeholders_to_data(template_id)

        for placeholder, mapping in placeholder_mapping.items():

            data_src = mapping.get('source')
            group = mapping.get('group', '')
            key = mapping.get('key', '')
            format = mapping.get('format', '')

            if data_src == "member_basic_data":
                value = member_info.get('basic_data', {}).get(key, '')
                if format == "YYYY年MM月" and value:
                    dt = datetime.strptime(value, "%Y年%m月%d日")
                    value = f"{dt.year}年{dt.month}月"
                if value == "1000年1月1日":   # 处理默认日期值
                    value = "无"
            elif data_src == 'admin_basic_data':
                value = admin_config.get("basic_data", {}).get(group, {}).get(key, '')
            elif data_src == 'admin_template_data':
                value = admin_config.get('template_data', {}).get(template_id, {}).get(placeholder, {}).get("value", '')
            elif data_src == 'member_template_data':
                value = member_info.get('template_data', {}).get(template_id, {}).get(placeholder, '')
            else:
                value = ''
            merged_data[placeholder] = value

        return merged_data
    
    # ======================== 生成模板 =========================
    
    def generate_document(self, template_id):
        """生成 Word 文档"""
        # 1. 获取模板文件路径
        template_path = self.template_manager.get_template_file_path(template_id)

        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")

        # 导出文件名和导出路径
        template_name = self.get_templates(template_id).get("name", "文档")
        name = self.data_manager.get_member_info("basic_data", "姓名") or "未命名"
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{template_name}_{name}_{date_str}.docx"

        export_path = self.data_manager.get_system_settings("export_path") or "./exports"
        export_dir = Path(export_path)
        export_dir.mkdir(parents=True, exist_ok=True)

        output_path = str(export_dir / filename)
        
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
    

