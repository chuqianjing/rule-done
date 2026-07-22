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
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QScrollArea,
    QFrame,
    QGroupBox,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFontMetrics, QResizeEvent
from src.application.template_engine import TemplateEngine
from src.utils.styles import ICONS


class ElidedLabel(QLabel):
    """可自动省略的标签：文本过长时末尾显示省略号，鼠标悬停显示全文。"""

    def __init__(self, full_text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = full_text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setWordWrap(False)
        self._update_elided()

    def set_full_text(self, text: str):
        self._full_text = text
        self._update_elided()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self):
        if not self._full_text:
            self.setText("")
            self.setToolTip("")
            return
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, self.width())
        self.setText(elided)
        self.setToolTip(self._full_text)


class ListPage(QWidget):
    """
    模板列表页面基类

    按阶段分组展示模板（QGroupBox），单击行切换选中状态，
    双击打开模板，描述信息以 tooltip 悬浮提示呈现。
    """

    open_template = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.template_engine = TemplateEngine()
        self._selected_ids: set[str] = set()
        self._template_rows: dict[str, QWidget] = {}
        self.init_ui()
        self.load_templates()

    def get_open_button_text(self) -> str:
        return "打开选中模板"

    def setup_extra_buttons(self, btn_layout: QHBoxLayout):
        pass

    def get_template_status_label(self, template_id: str) -> str:
        return ""

    def init_ui(self):
        """初始化 UI"""
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("list_page_root")

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("材料模板")
        title.setObjectName("title")
        layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setSpacing(10)
        self.scroll_layout.setContentsMargins(0, 0, 10, 0)
        self.scroll_content.setLayout(self.scroll_layout)
        scroll_area.setWidget(self.scroll_content)
        layout.addWidget(scroll_area, 1)

        # 操作提示（放在按钮上方，用户浏览完列表后自然看到）
        tip_label = QLabel(f"单击选中，双击打开，Ctrl+单击多选，")
        tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip_label.setStyleSheet("color: #999; font-size: 12px; padding: 2px 0;")
        layout.addWidget(tip_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.setup_extra_buttons(btn_layout)
        open_btn = QPushButton(self.get_open_button_text() + f" {ICONS['next']}")
        open_btn.clicked.connect(self.handle_open_selected)
        btn_layout.addWidget(open_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.setAutoFillBackground(True)

    # ===================== 选中状态管理 =====================

    def _toggle_selection(self, template_id: str, ctrl_held: bool = False):
        """切换选中状态。
        
        未按住 Ctrl 时为单选：选中当前项，取消其他所有选中。
        按住 Ctrl 时为多选：切换当前项的选中状态，不影响其他项。
        """
        if ctrl_held:
            # Ctrl+单击：切换当前项
            if template_id in self._selected_ids:
                self._selected_ids.discard(template_id)
            else:
                self._selected_ids.add(template_id)
        else:
            # 普通单击：单选
            self._selected_ids.clear()
            self._selected_ids.add(template_id)
        self._refresh_row_styles()

    def _refresh_row_styles(self):
        """刷新所有行的 selected 属性"""
        for tid, row in self._template_rows.items():
            row.setProperty("selected", tid in self._selected_ids)
            row.style().unpolish(row)
            row.style().polish(row)

    # ===================== 布局管理 =====================

    def _clear_scroll_layout(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def load_templates(self):
        """按阶段分组加载模板列表"""
        self._clear_scroll_layout()
        self._selected_ids.clear()
        self._template_rows.clear()

        grouped = self.template_engine.get_templates_grouped_by_stage()

        for group in grouped:
            stage_name = group.get("stage", "")
            templates = group.get("templates", [])
            if not templates:
                continue

            stage_group = QGroupBox(stage_name)
            stage_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    font-size: 13px;
                    border: 1px solid #dcdcdc;
                    border-radius: 5px;
                    margin-top: 8px;
                    padding-top: 14px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)
            group_layout = QVBoxLayout()
            group_layout.setSpacing(2)
            group_layout.setContentsMargins(6, 4, 6, 6)

            for tpl in templates:
                tpl_id = str(tpl.get("id", ""))
                tpl_name = str(tpl.get("name", ""))
                tpl_desc = str(tpl.get("description", ""))
                status_label = self.get_template_status_label(tpl_id)

                row = QWidget()
                row.setProperty("selected", False)
                row.setCursor(Qt.CursorShape.PointingHandCursor)

                # 用 [selected] 属性选择器控制样式
                row.setStyleSheet("""
                    QWidget[selected="false"] {
                        background-color: transparent;
                        border-radius: 4px;
                    }
                    QWidget[selected="false"]:hover {
                        background-color: #f0f4f8;
                    }
                    QWidget[selected="true"] {
                        background-color: #e2edfc;
                        border-radius: 4px;
                    }
                """)

                row_layout = QHBoxLayout()
                row_layout.setContentsMargins(8, 5, 8, 5)
                row_layout.setSpacing(10)

                name_label = QLabel(tpl_name)
                name_label.setStyleSheet("font-size: 13px; color: #333; background: transparent;")
                name_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
                row_layout.addWidget(name_label)

                # 描述（自动省略 + 全文 tooltip）
                desc_label = ElidedLabel(tpl_desc, self)
                desc_label.setStyleSheet("font-size: 12px; color: #999; background: transparent;")
                row_layout.addWidget(desc_label, 1)

                if status_label:
                    status = QLabel(f"[{status_label}]")
                    status.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
                    status.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
                    row_layout.addWidget(status)

                row.setLayout(row_layout)
                row.mousePressEvent = lambda e, tid=tpl_id: self._toggle_selection(
                    tid, ctrl_held=bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)
                )
                row.mouseDoubleClickEvent = lambda e, tid=tpl_id: self._on_template_double_clicked(tid)

                self._template_rows[tpl_id] = row
                group_layout.addWidget(row)

            group_layout.addStretch()
            stage_group.setLayout(group_layout)
            self.scroll_layout.addWidget(stage_group)

        self.scroll_layout.addStretch()

    # ===================== 交互处理 =====================

    def _get_selected_template_ids(self) -> list:
        return list(self._selected_ids)

    def handle_open_selected(self):
        ids = self._get_selected_template_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请先单击选择一个模板。")
            return
        self.open_template.emit(ids[0])

    def _on_template_double_clicked(self, template_id: str):
        if template_id:
            self.open_template.emit(template_id)