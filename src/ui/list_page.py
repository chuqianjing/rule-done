#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
模板列表页面基类
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QAbstractItemView,
)
from PySide6.QtCore import Signal, Qt, QRect
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QStyledItemDelegate
from src.application.template_engine import TemplateEngine
from src.utils.styles import ICONS


# 自定义数据角色：存储状态标签文本
STATUS_LABEL_ROLE = Qt.UserRole + 1


class StatusAlignDelegate(QStyledItemDelegate):
    """自定义委托：模板名左对齐、状态标签右对齐"""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        status_label = index.data(STATUS_LABEL_ROLE)
        if not status_label:
            return

        painter.save()
        painter.setPen(option.palette.color(QPalette.ColorRole.Text))

        fm = painter.fontMetrics()
        status_text = f"[{status_label}]"
        status_width = fm.horizontalAdvance(status_text) + 10

        text_rect = option.rect
        status_rect = QRect(
            text_rect.right() - status_width - 4,
            text_rect.top(),
            status_width,
            text_rect.height()
        )
        painter.drawText(
            status_rect,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            status_text
        )
        painter.restore()


class ListPage(QWidget):
    """
    模板列表页面基类
    
    子类需要实现：
        - get_page_title(): 返回页面标题
        - get_open_button_text(): 返回打开按钮文字
        - setup_extra_buttons(btn_layout): 添加额外按钮（可选）
    """

    # 打开某个模板的信号
    open_template = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.template_engine = TemplateEngine()

        self.init_ui()
        self.load_templates()

    def get_open_button_text(self) -> str:
        """返回打开按钮文字，子类应重写此方法"""
        return "打开选中模板"

    def setup_extra_buttons(self, btn_layout: QHBoxLayout):
        """添加额外按钮，子类可重写此方法"""
        pass

    def get_template_status_label(self, template_id: str) -> str:
        """返回模板状态标签，子类可重写此方法"""
        return ""

    def init_ui(self):
        """初始化 UI"""
        # 显式启用样式背景绘制，避免在 QStackedWidget 切页时出现残影/透出
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("list_page_root")

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 页面标题
        title = QLabel("材料模板")
        title.setObjectName("title")
        layout.addWidget(title)

        # 模板列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setItemDelegate(StatusAlignDelegate(self.list_widget))
        layout.addWidget(self.list_widget)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.setup_extra_buttons(btn_layout)   # 子类可添加额外按钮
        open_btn = QPushButton(self.get_open_button_text()+f" {ICONS['next']}")
        open_btn.clicked.connect(self.handle_open_selected)
        btn_layout.addWidget(open_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 确保页面背景不透明
        self.setAutoFillBackground(True)

        self.list_widget.itemDoubleClicked.connect(self.handle_item_double_clicked)

    def load_templates(self):
        """从模板管理器加载模板列表"""
        self.list_widget.clear()
        templates = self.template_engine.get_templates()

        for tpl in templates:
            tpl_id = str(tpl.get("id", ""))
            tpl_name = str(tpl.get("name", ""))
            base_text = f"{tpl_id}、{tpl_name}"
            status_label = self.get_template_status_label(tpl_id)

            item = QListWidgetItem(base_text)
            item.setData(32, tpl_id)  # 32 = Qt.UserRole
            if status_label:
                item.setData(STATUS_LABEL_ROLE, status_label)
            self.list_widget.addItem(item)

    def _get_selected_template_ids(self) -> list:
        """获取当前选中的模板ID列表"""
        ids = []
        for item in self.list_widget.selectedItems():
            tpl_id = item.data(32)
            if tpl_id:
                ids.append(tpl_id)
        return ids

    def handle_open_selected(self):
        """处理打开选中模板"""
        ids = self._get_selected_template_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请先选择一个模板。")
            return
        # 只打开第一个选中的模板
        self.open_template.emit(ids[0])

    def handle_item_double_clicked(self, item: QListWidgetItem):
        """处理双击打开模板"""
        tpl_id = item.data(32)
        if tpl_id:
            self.open_template.emit(tpl_id)



