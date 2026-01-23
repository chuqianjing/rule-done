#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生数据管理
"""

from pathlib import Path
from datetime import datetime

from src.utils.json_storage import JSONStorage
from src.utils.validators import Validators


class StudentManager:
    """学生数据管理器类"""
    
    def __init__(self):
        self.data_path = Path("data/student_data.json")
        self.json_storage = JSONStorage()
        self.validators = Validators()
    
    def load_data(self):
        """加载学生数据"""
        if not self.data_path.exists():
            return self._get_empty_data()
        
        try:
            return self.json_storage.read_json(str(self.data_path))
        except Exception:
            return self._get_empty_data()
    
    def save_data(self, data):
        """保存学生数据"""
        # 更新修改时间
        data['last_modified'] = datetime.now().isoformat()
        
        # 执行数据验证
        validation_result = self.validate_data(data)
        data['validation_status'] = validation_result
        
        self.json_storage.write_json(str(self.data_path), data)
        return True
    
    def update_basic_info(self, basic_info):
        """更新基础信息"""
        data = self.load_data()
        data['basic_info'] = basic_info
        return self.save_data(data)
    
    def update_template_data(self, template_id, template_data):
        """更新模板数据"""
        data = self.load_data()
        if 'template_data' not in data:
            data['template_data'] = {}
        
        if template_id not in data['template_data']:
            data['template_data'][template_id] = {}
        
        data['template_data'][template_id].update(template_data)
        data['template_data'][template_id]['last_modified'] = datetime.now().isoformat()
        
        return self.save_data(data)
    
    def validate_data(self, data):
        """执行数据验证（结合字段定义和逻辑关系）"""
        from pathlib import Path
        import json

        result = {
            "basic_info": {"valid": True, "errors": []},
            "template_data": {},
            "logical": {"valid": True, "errors": []},
        }

        # 加载字段定义
        fields_path = Path("resources/fields_definition.json")
        try:
            with open(fields_path, "r", encoding="utf-8") as f:
                fields_def = json.load(f)
        except Exception:
            # 如果字段定义异常，直接认为验证通过，避免阻塞使用
            return result

        basic_defs = fields_def.get("basic_info_fields", [])
        template_defs_map = fields_def.get("template_specific_fields", {})

        basic_info = data.get("basic_info", {})
        template_data = data.get("template_data", {})

        # 基本信息字段验证
        basic_errors = []
        for field_def in basic_defs:
            key = field_def.get("key")
            value = basic_info.get(key, "")
            ok, msg = self.validators.validate_field(field_def, value)
            if not ok and msg:
                basic_errors.append({"field": key, "message": msg})

            # 额外规则：身份证号、手机号做专项验证
            if key == "身份证号":
                ok2, msg2 = self.validators.validate_id_card(value)
                if not ok2 and msg2:
                    basic_errors.append({"field": key, "message": msg2})
            if key == "联系电话":
                ok3, msg3 = self.validators.validate_phone(value)
                if not ok3 and msg3:
                    basic_errors.append({"field": key, "message": msg3})

        result["basic_info"]["valid"] = len(basic_errors) == 0
        result["basic_info"]["errors"] = basic_errors

        # 模板特有字段验证
        for template_id, tpl_fields in template_defs_map.items():
            tpl_result = {"valid": True, "errors": []}
            tpl_data = template_data.get(template_id, {})
            for field_def in tpl_fields.get("fields", []):
                key = field_def.get("key")
                value = tpl_data.get(key, "")
                ok, msg = self.validators.validate_field(field_def, value)
                if not ok and msg:
                    tpl_result["errors"].append({"field": key, "message": msg})
            tpl_result["valid"] = len(tpl_result["errors"]) == 0
            result["template_data"][template_id] = tpl_result

        # 逻辑关系验证（如入党时间 vs 转正时间）
        logical_errors = self.validators.validate_logical_relations(data)
        result["logical"]["valid"] = len(logical_errors) == 0
        result["logical"]["errors"] = logical_errors

        return result
    
    def _get_empty_data(self):
        """获取空数据结构"""
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "basic_info": {},
            "template_data": {},
            "export_history": [],
            "validation_status": {}
        }

