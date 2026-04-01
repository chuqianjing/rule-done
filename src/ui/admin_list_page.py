#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
管理员模板列表页面
"""

from PySide6.QtWidgets import QHBoxLayout
from src.ui.list_page import ListPage


class AdminListPage(ListPage):
    """
    管理员模式的模板列表页面
    
    用于配置模板字段
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def get_open_button_text(self) -> str:
        return "配置选中的材料"

    def setup_extra_buttons(self, btn_layout: QHBoxLayout):
        """管理员模式可以在这里添加额外的管理按钮"""
        # 预留扩展：如添加模板、删除模板等按钮
        pass
