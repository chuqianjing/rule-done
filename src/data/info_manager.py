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
            "validation_status": {},
            "export_history": []
        }
    
    def save_data(self, data):
        """保存成员数据"""
        # 更新修改时间
        data['last_modified'] = datetime.now().isoformat()
        # 执行数据验证
        validation_result = self.validate_data(data)
        data['validation_status'] = validation_result
        self.json_storage.write_json(str(self.data_path), data)
        return True
    
    def validate_data(self, data):
        """执行数据验证（结合字段定义和逻辑关系）"""

        result = {
            "basic_data": {"valid": True, "errors": []},
            # "template_data": {},   目前不需要template_data的验证
            "logical": {"valid": True, "errors": []},
        }

        # 加载字段定义
        fields_def = self.field_manager.load_fields_definition()
        member_fields = fields_def.get("member_fields", [])
        basic_data = data.get("basic_data", {})

        # 基本信息字段验证
        basic_errors = []
        for field_def in member_fields:
            key = field_def.get("key")
            value = basic_data.get(key, "")
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

        result["basic_data"]["valid"] = len(basic_errors) == 0
        result["basic_data"]["errors"] = basic_errors

        # 逻辑关系验证（如入党时间 vs 转正时间）
        logical_errors = self.validators.validate_logical_relations(data)
        result["logical"]["valid"] = len(logical_errors) == 0
        result["logical"]["errors"] = logical_errors

        return result
    

