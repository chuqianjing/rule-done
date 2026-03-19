#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基本信息页面
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QScrollArea,
    QFrame,
    QStackedWidget,
    QButtonGroup,
)
from PyQt6.QtCore import pyqtSignal
from src.business.data_manager import DataManager
from src.business.permission_controller import PermissionController
from src.utils.field_utils import create_widget, set_widget_value, get_widget_value
from src.utils.data_paths import get_admin_value
from src.ui.styles import TIP_STYLE, SAVE_STATUS_SAVED, SAVE_STATUS_UNSAVED, SAVE_STATUS_NEUTRAL, ICONS


class MemberHomePage(QWidget):
    """基本信息页面类"""

    # 进入模板列表/填写的信号，由 MainWindow 连接
    go_to_template_list = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.data_manager = DataManager()
        self.permission_controller = PermissionController()

        # 缓存字段定义与控件
        self.member_fields: list[dict] = []
        self.field_widgets: dict[str, QWidget] = {}
        # 管理员字段分组定义（用于分组显示）
        self.admin_fields_groups: list[dict] = []

        # 管理员配置缓存（用于日期格式等）
        self.admin_config = self.data_manager.get_admin_config()

        # 编辑状态标志
        self.is_editing = False

        self.init_ui()
        self.load_field_definitions()
        self.build_member_form()
        self.load_data()

    def init_ui(self):
        """初始化 UI"""
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # 页面标题区域
        header_layout = QHBoxLayout()

        title = QLabel("基本信息填写")
        title.setObjectName("title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 保存状态指示（仅编辑模式下显示）
        self.save_status = QLabel(f"{ICONS['info']} 尚未保存")
        self.save_status.setStyleSheet(SAVE_STATUS_NEUTRAL)
        self.save_status.setVisible(False)
        header_layout.addWidget(self.save_status)

        self.main_layout.addLayout(header_layout)

        # 提示信息
        tip_label = QLabel(f"{ICONS['info']} 请先填写基本信息，这些信息将自动填充到各个模板中")
        tip_label.setStyleSheet(TIP_STYLE)
        tip_label.setWordWrap(True)
        self.main_layout.addWidget(tip_label)

        # 标签页切换按钮区域
        tab_btn_layout = QHBoxLayout()
        tab_btn_layout.setSpacing(0)
        tab_btn_layout.setContentsMargins(0, 10, 0, 10)

        self.tab_btn_group = QButtonGroup(self)
        self.tab_btn_group.setExclusive(True)

        # 管理员配置标签按钮
        self.admin_tab_btn = QPushButton(f"{ICONS['pin']} 支部公共信息")
        self.admin_tab_btn.setCheckable(True)
        self.admin_tab_btn.setChecked(True)
        self.admin_tab_btn.setStyleSheet(self._get_tab_btn_style(True))
        self.admin_tab_btn.clicked.connect(lambda: self._switch_tab(0))
        self.tab_btn_group.addButton(self.admin_tab_btn, 0)
        tab_btn_layout.addWidget(self.admin_tab_btn)

        # 成员信息标签按钮
        self.member_tab_btn = QPushButton(f"{ICONS['edit']} 个人基本信息")
        self.member_tab_btn.setCheckable(True)
        self.member_tab_btn.setStyleSheet(self._get_tab_btn_style(False))
        self.member_tab_btn.clicked.connect(lambda: self._switch_tab(1))
        self.tab_btn_group.addButton(self.member_tab_btn, 1)
        tab_btn_layout.addWidget(self.member_tab_btn)

        tab_btn_layout.addStretch()
        self.main_layout.addLayout(tab_btn_layout)

        # 堆叠视图（用于切换管理员配置和成员信息面板）
        self.stacked_widget = QStackedWidget()

        # === 管理员配置面板 ===
        admin_scroll_area = QScrollArea()
        admin_scroll_area.setWidgetResizable(True)
        admin_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        admin_scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        self.admin_scroll_content = QWidget()
        self.admin_scroll_layout = QVBoxLayout()
        self.admin_scroll_layout.setSpacing(15)
        self.admin_scroll_layout.setContentsMargins(0, 0, 10, 0)
        self.admin_scroll_layout.addStretch()
        self.admin_scroll_content.setLayout(self.admin_scroll_layout)
        admin_scroll_area.setWidget(self.admin_scroll_content)
        self.stacked_widget.addWidget(admin_scroll_area)

        # === 成员填写面板 ===
        member_scroll_area = QScrollArea()
        member_scroll_area.setWidgetResizable(True)
        member_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        member_scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        member_scroll_content = QWidget()
        member_scroll_layout = QVBoxLayout()
        member_scroll_layout.setSpacing(15)
        member_scroll_layout.setContentsMargins(0, 0, 10, 0)

        # 成员填写字段
        self.member_group = QGroupBox(f"{ICONS['info']} 个人基本信息（只读）")
        self.member_form = QFormLayout()
        self.member_form.setSpacing(10)
        self.member_form.setContentsMargins(15, 20, 15, 15)
        self.member_group.setLayout(self.member_form)
        member_scroll_layout.addWidget(self.member_group)

        # 编辑/保存按钮区域（在成员面板内）
        member_btn_layout = QHBoxLayout()
        member_btn_layout.setContentsMargins(0, 10, 0, 0)

        self.edit_btn = QPushButton(f"{ICONS['edit']} 编辑个人信息")
        self.edit_btn.setObjectName("secondary")
        self.edit_btn.clicked.connect(self._start_editing)
        member_btn_layout.addWidget(self.edit_btn)

        self.member_save_btn = QPushButton(f"{ICONS['save']} 保存个人信息")
        self.member_save_btn.clicked.connect(self._save_and_exit_editing)
        self.member_save_btn.setVisible(False)  # 默认隐藏
        member_btn_layout.addWidget(self.member_save_btn)

        self.cancel_edit_btn = QPushButton(f"{ICONS['prev']} 取消编辑")
        self.cancel_edit_btn.setObjectName("secondary")
        self.cancel_edit_btn.clicked.connect(self._cancel_editing)
        self.cancel_edit_btn.setVisible(False)  # 默认隐藏
        member_btn_layout.addWidget(self.cancel_edit_btn)

        member_btn_layout.addStretch()
        member_scroll_layout.addLayout(member_btn_layout)

        member_scroll_layout.addStretch()
        member_scroll_content.setLayout(member_scroll_layout)
        member_scroll_area.setWidget(member_scroll_content)
        self.stacked_widget.addWidget(member_scroll_area)

        self.main_layout.addWidget(self.stacked_widget, 1)  # 拉伸占满剩余空间

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_layout.addStretch()

        goto_tpl_btn = QPushButton(f"下一步：选择模板 {ICONS['next']}")
        goto_tpl_btn.clicked.connect(self.go_to_template_list.emit)
        btn_layout.addWidget(goto_tpl_btn)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)

        # 确保页面背景不透明，防止在 QStackedWidget 切换时"透出"
        self.setAutoFillBackground(True)

    def _get_tab_btn_style(self, active: bool) -> str:
        """获取标签按钮样式"""
        if active:
            return """
                QPushButton {
                    background-color: #1a73e8;
                    color: white;
                    border: none;
                    border-radius: 4px 4px 0 0;
                    padding: 10px 20px;
                    font-weight: bold;
                    min-width: 120px;
                }
                QPushButton:hover {
                    background-color: #1557b0;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #e8eaed;
                    color: #333;
                    border: 1px solid #ddd;
                    border-bottom: none;
                    border-radius: 4px 4px 0 0;
                    padding: 10px 20px;
                    font-weight: normal;
                    min-width: 120px;
                }
                QPushButton:hover {
                    background-color: #d2d4d6;
                }
            """

    def _switch_tab(self, index: int):
        """切换标签页"""
        self.stacked_widget.setCurrentIndex(index)
        # 更新按钮样式
        self.admin_tab_btn.setStyleSheet(self._get_tab_btn_style(index == 0))
        self.member_tab_btn.setStyleSheet(self._get_tab_btn_style(index == 1))

    def _set_form_editable(self, editable: bool):
        """设置表单的可编辑状态"""
        self.is_editing = editable
        for widget in self.field_widgets.values():
            widget.setEnabled(editable)
        
        # 更新分组框标题
        if editable:
            self.member_group.setTitle(f"{ICONS['edit']} 个人基本信息（请如实填写）")
        else:
            self.member_group.setTitle(f"{ICONS['info']} 个人基本信息（只读）")
        
        # 更新按钮显示状态
        self.edit_btn.setVisible(not editable)
        self.member_save_btn.setVisible(editable)
        self.cancel_edit_btn.setVisible(editable)
        self.save_status.setVisible(editable)

    def _start_editing(self):
        """开始编辑个人信息"""
        reply = QMessageBox.question(
            self,
            "确认编辑",
            "确定要编辑个人信息吗？\n\n请确保填写的信息真实准确。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._set_form_editable(True)
            self._update_save_status(False)

    def _save_and_exit_editing(self):
        """保存并退出编辑模式"""
        try:
            member_info = self.data_manager.get_member_info()
            member_info["basic_info"] = self._collect_basic_info_from_form()
            self.data_manager.save_member_info(member_info)
            self._set_form_editable(False)
            self._update_save_status(True)
            QMessageBox.information(self, "提示", "个人信息已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def _cancel_editing(self):
        """取消编辑，恢复原有数据"""
        reply = QMessageBox.question(
            self,
            "确认取消",
            "确定要取消编辑吗？\n\n未保存的更改将会丢失。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # 重新加载数据
            self.load_data()
            self._set_form_editable(False)

    def _update_save_status(self, saved: bool):
        """更新保存状态显示"""
        if saved:
            self.save_status.setText(f"{ICONS['success']} 已保存")
            self.save_status.setStyleSheet(SAVE_STATUS_SAVED)
        else:
            self.save_status.setText(f"{ICONS['warning']} 有未保存的更改")
            self.save_status.setStyleSheet(SAVE_STATUS_UNSAVED)

    def load_field_definitions(self):
        """加载字段定义"""
        try:
            self.admin_fields_groups, self.member_fields = self.data_manager.get_fields(src="member")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取字段定义失败：{e}")
            return

    def build_member_form(self):
        """根据字段定义动态生成成员填写表单"""
        # 清空旧表单
        while self.member_form.rowCount():
            self.member_form.removeRow(0)
        self.field_widgets.clear()

        for field_def in self.member_fields:
            key = field_def.get("key")
            widget = create_widget(field_def, self.admin_config)
            self.field_widgets[key] = widget
            self.member_form.addRow(f"{key}：", widget)

        # 默认设置为不可编辑状态
        self._set_form_editable(False)

    def load_data(self):
        """加载管理员配置和成员数据"""
        # 管理员配置（只读显示）
        admin_config = self.data_manager.get_admin_config()
        self._render_admin_config(admin_config)

        # 成员数据
        member_info = self.data_manager.get_member_info()
        basic_info = member_info.get("basic_info", {})

        for key, widget in self.field_widgets.items():
            value = basic_info.get(key, "")
            # 查找该 key 对应的字段定义，以便 set_widget_value 使用 format 等信息
            field_def = next((f for f in self.member_fields if f.get("key") == key), None)
            set_widget_value(widget, value, field_def, self.admin_config)

    def _render_admin_config(self, config: dict):
        """根据字段定义按分组动态渲染管理员配置为只读信息"""
        # 清空旧的分组框
        while self.admin_scroll_layout.count() > 1:  # 保留最后的 stretch
            child = self.admin_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 如果没有加载字段分组定义，使用空列表
        if not hasattr(self, "admin_fields_groups"):
            self.admin_fields_groups = []

        # 按分组渲染
        for group_def in self.admin_fields_groups:
            group_name = group_def.get("group", "未分组")
            fields = sorted(
                group_def.get("fields", []),
                key=lambda x: x.get("display", {}).get("order", 0),
            )

            # 创建分组框
            group_box = QGroupBox(f"{ICONS['pin']} {group_name}（只读）")
            group_form = QFormLayout()
            group_form.setSpacing(10)
            group_form.setContentsMargins(15, 20, 15, 15)

            for field_def in fields:
                key = field_def.get("key", "")
                # 直接使用 key 作为界面标签
                label_text = key

                # 根据 group + key 从配置中获取值
                value = get_admin_value(config, group_name, key, "")

                label = QLabel(str(value))
                label.setStyleSheet("color: #555;")
                group_form.addRow(f"{label_text}：", label)

            group_box.setLayout(group_form)
            # 插入到 stretch 之前
            self.admin_scroll_layout.insertWidget(self.admin_scroll_layout.count() - 1, group_box)

    def _collect_basic_info_from_form(self) -> dict:
        """从表单采集成员基础信息"""
        basic_info: dict[str, str] = {}
        for key, widget in self.field_widgets.items():
            field_def = next((f for f in self.member_fields if f.get("key") == key), None)
            basic_info[key] = get_widget_value(widget, field_def, self.admin_config)
        return basic_info
