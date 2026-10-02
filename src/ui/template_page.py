#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
模板填写页面基类
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QFormLayout,
    QPushButton,
    QHBoxLayout,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from src.application.data_manager import DataManager
from src.application.template_engine import TemplateEngine
from src.persistence.review_table_fields import (
    EXEC_STATE_APPROVED,
    EXEC_STATE_FILLING,
    EXEC_STATE_PENDING,
    EXEC_STATE_REJECTED,
    EXEC_STATE_UNFILLED,
)
from src.utils.widget_binding import get_widget_value, configure_selectable_label
from src.utils.styles import ICONS, TIP_STYLE


class TemplatePage(QWidget):
    """模板填写页面基类"""

    back_to_list_page = Signal()
    mode: str = ""

    def __init__(self, template_id: str = "template_001", parent=None):
        super().__init__(parent)

        self.template_id = template_id

        self.data_manager = DataManager()
        self.template_engine = TemplateEngine()

        self.field_widgets: dict[str, QWidget] = {}
        self.placeholder_defs: dict[str, dict] = {}        # 模板占位符对应的字段定义

        self.init_ui()
        self.load_mapping()
        self.build_template_forms()
        self.load_data()
        self._update_review_ui()

    def init_ui(self):
        """初始化 UI 布局"""
        # 显式启用样式背景绘制，避免在 QStackedWidget 切页时出现残影/透出
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("template_page_root")
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        template_info = self.template_engine.get_templates(self.template_id)
        title_text = template_info.get("name")

        self.title_label = QLabel(f"{title_text}")
        self.title_label.setObjectName("title")
        self.main_layout.addWidget(self.title_label)

        # 提示信息
        tip_label = QLabel(f"{ICONS['info']} "+self.tip_message())
        tip_label.setStyleSheet(TIP_STYLE)
        tip_label.setWordWrap(True)
        self.main_layout.addWidget(tip_label)

        # 头部固定附加区（位于提示下方、**不随内容滚动**）：子类按需填充；
        # 无内容时隐藏，避免多出一个间距
        self.header_extra = QWidget()
        self.header_extra_layout = QVBoxLayout()
        self.header_extra_layout.setContentsMargins(0, 0, 0, 0)
        self.header_extra_layout.setSpacing(8)
        self.header_extra.setLayout(self.header_extra_layout)
        self.header_extra.setVisible(False)
        self.main_layout.addWidget(self.header_extra)

        # 审核状态条（仅成员端；默认隐藏，未开启审核机制时始终隐藏）
        self.review_status_bar = None
        self.review_status_label = None
        self.review_comment_label = None
        if self.mode == "member":
            self._build_review_status_bar()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(0, 0, 10, 0)

        if self.mode == "member":
            self.basic_group = QGroupBox("基本项")
            self.basic_form = QFormLayout()
            self.basic_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            self.basic_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            self.basic_form.setSpacing(10)
            self.basic_form.setContentsMargins(15, 20, 15, 15)
            self.basic_group.setLayout(self.basic_form)
            scroll_layout.addWidget(self.basic_group)
        else:
            self.basic_group = None
            self.basic_form = None

        self.template_group = QGroupBox("专有项")
        self.template_form = QFormLayout()
        self.template_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.template_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.template_form.setSpacing(10)
        self.template_form.setContentsMargins(15, 20, 15, 15)
        self.template_group.setLayout(self.template_form)
        scroll_layout.addWidget(self.template_group)

        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)

        self.main_layout.addWidget(scroll_area, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        back_btn = QPushButton("← 返回")
        back_btn.clicked.connect(self.back_to_list_page.emit)
        btn_layout.addWidget(back_btn)

        btn_layout.addStretch()

        member_template_data = self.data_manager.get_member_info("template_data", self.template_id) or {}
        self.member_template_locked = member_template_data.get("locked", False)

        # 按钮均为实例属性：审核机制开启时需按状态动态切换可见性
        self.save_btn = None
        self.manage_btn = None
        self.export_btn = None
        self.lock_btn = None
        self.submit_btn = None
        self.renew_btn = None

        if not (self.mode == "member" and self.member_template_locked):
            self.save_btn = QPushButton("保存")
            self.save_btn.clicked.connect(self.save_data)
            btn_layout.addWidget(self.save_btn)
        else:
            self.manage_btn = QPushButton("存档管理")
            self.manage_btn.clicked.connect(self.manage_archive)
            btn_layout.addWidget(self.manage_btn)

        if self.mode == "member" and not self.member_template_locked:
            self.export_btn = QPushButton("导出材料")
            self.export_btn.setToolTip("导出前会先自动保存你当前的修改，再生成 Word 文档")
            self.export_btn.clicked.connect(self.export_document)
            btn_layout.addWidget(self.export_btn)

            self.lock_btn = QPushButton("锁定材料")
            self.lock_btn.setToolTip("锁定时会一并保存你当前填写的内容；锁定后无法修改，也无法解锁")
            self.lock_btn.clicked.connect(self.lock_document)
            btn_layout.addWidget(self.lock_btn)

            self.submit_btn = QPushButton("提交审核")
            self.submit_btn.setToolTip("把本材料中由你填写的项目提交给管理员审核（会先自动保存你当前的修改）")
            self.submit_btn.clicked.connect(self.submit_for_review)
            self.submit_btn.setVisible(False)
            btn_layout.addWidget(self.submit_btn)

            self.renew_btn = QPushButton("重新开始工作期")
            self.renew_btn.setToolTip("使本材料重新进入配置快照有效期，重新接受支部配置引导")
            self.renew_btn.clicked.connect(self.renew_work_window)
            self.renew_btn.setVisible(False)
            btn_layout.addWidget(self.renew_btn)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)
        self.setAutoFillBackground(True)

    def load_mapping(self):
        """从字段定义配置中加载通用模板字段定义和管理员字段定义"""
        self.placeholder_mapping = self.template_engine.map_placeholders_to_data(self.template_id, self.mode)

    def refresh(self):
        """按最新字段定义/模板资源重建页面：清缓存 → 重载字段 → 重建表单 → 加载数据。"""
        # 资源同步可能同时替换 templates_config.json 与 fields_definition.json，
        # 两者均由 DataManager 共享实例持有，必须显式失效后再重建（否则仍是旧结构）。
        self.template_engine.template_manager.refresh()
        self.template_engine.reload_fields()
        self._refresh_title()
        self.load_mapping()
        self.build_template_forms()
        self.load_data()
        self._update_review_ui()

    def refresh_basic_entry(self):
        """数据源变化后（如信息同步回填）仅重算映射并刷新“基本项”只读展示。

        与 refresh() 的区别：不重建专有项控件、不回填其值，
        因此不会丢弃用户尚未保存的编辑内容。
        """
        self.load_mapping()
        if self.basic_form is not None:
            self._render_basic_data()
        # 信息同步可能刚回写了审核结果，同步刷新状态条与按钮闸门
        self._update_review_ui()

    # ===================== 材料审核状态与按钮闸门 =====================

    def _build_review_status_bar(self):
        """构建材料审核状态条（仅成员端；默认隐藏）。"""
        container = QFrame()
        container.setObjectName("review_status_bar")
        container.setStyleSheet("""
            QFrame#review_status_bar {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        self.review_status_label = QLabel("")
        self.review_status_label.setWordWrap(True)
        self.review_status_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; background: transparent;")
        layout.addWidget(self.review_status_label)

        self.review_comment_label = QLabel("")
        self.review_comment_label.setWordWrap(True)
        self.review_comment_label.setStyleSheet(
            "font-size: 13px; color: #555; background: transparent;")
        layout.addWidget(self.review_comment_label)

        container.setLayout(layout)
        container.setVisible(False)
        # 顺序由插入顺序决定：title → tip → header_extra → 状态条
        self.main_layout.addWidget(container)
        self.review_status_bar = container

    def _update_review_ui(self):
        """按最新审核状态刷新状态条与「提交 / 导出 / 锁定」按钮闸门。

        只作用于成员端**已开启审核机制**的模板：
        - 未开启审核：完全不干预原有按钮可见性（向后兼容）；
        - 已锁定：隐藏状态条（锁定态由既有只读呈现表达）。
        """
        if self.mode != "member":
            return
        if self.review_status_bar is not None:
            self.review_status_bar.setVisible(False)
        if getattr(self, "member_template_locked", False):
            return

        review_enabled = self.data_manager.is_template_review_enabled(self.template_id)
        if self.submit_btn is not None:
            self.submit_btn.setVisible(False)
        if not review_enabled:
            return

        state = self.data_manager.get_template_execution_state(self.template_id)
        info = self.data_manager.get_template_review_info(self.template_id)

        # 提交按钮：待审核 / 已通过 时无需再次提交
        if self.submit_btn is not None:
            self.submit_btn.setVisible(state not in (EXEC_STATE_PENDING, EXEC_STATE_APPROVED))
        # 交付侧闸门（R4）：仅「已通过」可导出与锁定
        approved = state == EXEC_STATE_APPROVED
        if self.export_btn is not None:
            self.export_btn.setVisible(approved)
        if self.lock_btn is not None:
            self.lock_btn.setVisible(approved)

        if self.review_status_bar is None:
            return
        color, text = self._review_status_text(state, info)
        self.review_status_label.setText(text)
        self.review_status_label.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {color}; background: transparent;")

        comment = str(info.get("comment") or "").strip()
        show_comment = bool(comment) and state in (EXEC_STATE_REJECTED, EXEC_STATE_APPROVED)
        self.review_comment_label.setVisible(show_comment)
        if show_comment:
            self.review_comment_label.setText(f"审核意见：{comment}")
        self.review_status_bar.setVisible(True)

    @staticmethod
    def _review_status_text(state: str, info: dict) -> tuple:
        """返回（颜色, 文案），供审核状态条使用。"""
        if state == EXEC_STATE_PENDING:
            submitted_at = str(info.get("submitted_at") or "").strip().replace("T", " ")
            suffix = f"（提交时间：{submitted_at}）" if submitted_at else ""
            return "#1a73e8", f"{ICONS['export']} 已提交审核，等待管理员处理{suffix}"
        if state == EXEC_STATE_REJECTED:
            return "#e67e22", f"{ICONS['edit']} 审核未通过，请按下方意见修改后重新提交"
        if state == EXEC_STATE_APPROVED:
            return "#34a853", f"{ICONS['success']} 已通过审核，可导出与锁定本材料"
        if state == EXEC_STATE_UNFILLED:
            return "#888", f"{ICONS['info']} 尚未填写：填写完成后请点击「提交审核」"
        if state == EXEC_STATE_FILLING:
            return "#888", f"{ICONS['info']} 尚未提交审核：填写完成后请点击「提交审核」"
        return "#888", ""

    def _refresh_title(self):
        """按最新模板元数据刷新页面标题（资源同步可能改名）。"""
        try:
            template_info = self.template_engine.get_templates(self.template_id)
            self.title_label.setText(str(template_info.get("name", "")))
        except Exception:
            pass

    def build_template_forms(self):
        """构建模板想字段表单（基于模板文件中的占位符和通用字段库）"""
        while self.template_form.rowCount():
            self.template_form.removeRow(0)
        self.field_widgets.clear()
        self.placeholder_defs.clear()

        # 成员模式&&锁定档案：专有项表单区域直接呈现为数据的只读格式
        if self.mode == "member" and self.member_template_locked:
            member_template_entry = self.data_manager.get_member_info("template_data", self.template_id, "template_entry") or {}
            for key, value in member_template_entry.items():
                label = configure_selectable_label(QLabel(str(value)))
                label.setWordWrap(True)
                label.setStyleSheet("color: #555;")
                self.template_form.addRow(f"{key}：", label)
            return

        self.template_specific_placeholders = [
            placeholder for placeholder, mapping in sorted(
                self.placeholder_mapping.items(),
                key=lambda item: item[1].get("doc_order", 999),
            )
            if mapping.get("type") == "template_entry"
        ]

        for placeholder in self.template_specific_placeholders:
            field_def = self.template_engine.match_placehoder_def(placeholder, self.template_id)
            self.placeholder_defs[placeholder] = field_def
            self._add_field_to_form(field_def)

    def _add_field_to_form(self, field_def: dict):
        raise NotImplementedError

    def get_field_def(self, key: str) -> dict | None:
        return self.placeholder_defs.get(key)

    def _collect_template_data_from_form(self) -> dict:
        """从表单采集模板特有数据"""
        data: dict[str, str] = {}
        for key, widget in self.field_widgets.items():
            data[key] = get_widget_value(widget)
        return data

    def load_data(self):
        raise NotImplementedError

    def save_data(self):
        raise NotImplementedError

    def export_document(self):
        raise NotImplementedError
    
    def lock_document(self):
        raise NotImplementedError

    def submit_for_review(self):
        """把本材料的待填项提交给管理员审核（成员端实现）。"""
        raise NotImplementedError

    def renew_work_window(self):
        raise NotImplementedError

    def tip_message(self):
        raise NotImplementedError

    def manage_archive(self):
        raise NotImplementedError
