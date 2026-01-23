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
        """执行数据验证"""
        # TODO: 实现完整的数据验证逻辑
        return {
            'basic_info': {'valid': True, 'errors': []},
            'template_data': {}
        }
    
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

