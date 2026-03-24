#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
成员数据管理
"""

from pathlib import Path
from datetime import datetime
from src.utils.json_storage import JSONStorage
from src.utils.validators import Validators
from src.data.field_manager import FieldManager


class InfoManager:
    """成员数据管理器类"""
    
    def __init__(self):
        self.data_path = Path("data/member_info.json")
        self.json_storage = JSONStorage()
        self.validators = Validators()
        self.field_manager = FieldManager()
    
    def load_data(self):
        """加载成员数据"""
        if not self.data_path.exists():
            return self._get_default_info()
        try:
            return self.json_storage.read_json(str(self.data_path))
        except Exception:
            return self._get_default_info()
        
    def _get_default_info(self):
        """获取默认数据结构"""
        return {
            "version": "1.0",     # 需要version吗
            "created_at": datetime.now().isoformat(),
            "basic_data": {},
            "template_data": {},
            #  "validation_status": {},     弃用，其应该作为验证失败时的信息在UI呈现给用户，而不是保存在数据文件中
            "export_history": []
        }
    
    def save_data(self, data):
        """保存成员数据"""
        # 执行数据验证
        validation_result = self.validate_data(data)
        if not validation_result['basic_data']['valid'] or not validation_result['logical']['valid']:
            message = "数据验证失败:\n"
            if not validation_result['basic_data']['valid']:
                message += "信息字段错误:\n"
                for error in validation_result['basic_data']['errors']:
                    message += f" - {error['field']}: {error['message']}\n"
            if not validation_result['logical']['valid']:
                message += "逻辑关系错误:\n"
                for error in validation_result['logical']['errors']:
                    message += f" - {error['field']}: {error['message']}\n"
            raise ValueError(message)
        
        # 更新修改时间
        data['last_modified'] = datetime.now().isoformat()
        self.json_storage.write_json(str(self.data_path), data)
        return True
    
    def validate_data(self, data):
        """执行数据验证（结合字段定义和逻辑关系）"""

        result = {
            "basic_data": {"valid": True, "errors": []},
            # "template_data": {},   目前不需要template_data的验证
            "logical": {"valid": True, "errors": []},
        }

        # 字段定义
        fields_def = self.field_manager.load_fields_definition()
        member_fields = fields_def.get("member_fields", [])

        # 数据
        basic_data = data.get("basic_data", {})

        # 基本信息字段验证
        basic_errors = []
        for field_def in member_fields:
            key = field_def.get("key")
            value = basic_data.get(key, "")
            ok, msg = self.validators.validate_field(field_def, value)
            if not ok and msg:
                basic_errors.append({"field": key, "message": msg})

        result["basic_data"]["valid"] = len(basic_errors) == 0
        result["basic_data"]["errors"] = basic_errors

        # 逻辑关系验证（如入党时间 vs 转正时间）
        logical_errors = self.validators.validate_logical_relations(data)
        result["logical"]["valid"] = len(logical_errors) == 0
        result["logical"]["errors"] = logical_errors

        return result
    
    def lock_template_data(self, template_id, basic_entry, template_entry):
        """锁定成员的模板数据，使其无法再修改（如导出后）"""
        member_info = self.load_data()
        if "template_data" not in member_info:
            member_info["template_data"] = {}
        member_info["template_data"][template_id] = {}
        
        member_info["template_data"][template_id]["basic_entry"] = basic_entry
        member_info["template_data"][template_id]["template_entry"] = template_entry
        member_info["template_data"][template_id]["locked"] = True
        return self.save_data(member_info)
