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
    QFileDialog,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt

from src.business.data_manager import DataManager
from src.business.permission_controller import PermissionController
from src.data.config_manager import ConfigManager
from src.utils.field_utils import create_widget, set_widget_value, get_widget_value
from src.utils.data_paths import get_value_by_path
from src.utils.fields_loader import load_fields_definition
from src.ui.styles import TIP_STYLE, SAVE_STATUS_SAVED, SAVE_STATUS_UNSAVED, SAVE_STATUS_NEUTRAL, ICONS


class BasicInfoPage(QWidget):
    """基本信息页面类"""

    # 进入模板列表/填写的信号，由 MainWindow 连接
    go_to_template_list = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.data_manager = DataManager()
        self.permission_controller = PermissionController()
        self.config_manager = ConfigManager()

        # 缓存字段定义与控件
        self.basic_field_defs: list[dict] = []
        self.field_widgets: dict[str, QWidget] = {}

        # 管理员配置缓存（用于日期格式等）
        self.admin_config = self.data_manager.get_admin_config()

        self.init_ui()
        self.load_field_definitions()
        self.build_student_form()
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

        # 保存状态指示
        self.save_status = QLabel(f"{ICONS['info']} 尚未保存")
        self.save_status.setStyleSheet(SAVE_STATUS_NEUTRAL)
        header_layout.addWidget(self.save_status)

        self.main_layout.addLayout(header_layout)

        # 提示信息
        tip_label = QLabel(f"{ICONS['info']} 请先填写基本信息，这些信息将自动填充到各个模板中")
        tip_label.setStyleSheet(TIP_STYLE)
        tip_label.setWordWrap(True)
        self.main_layout.addWidget(tip_label)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        # 滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(0, 0, 10, 0)

        # 管理员配置字段（只读）
        self.admin_group = QGroupBox(f"{ICONS['pin']} 本支部公共信息（管理员配置，只读）")
        self.admin_form = QFormLayout()
        self.admin_form.setSpacing(10)
        self.admin_form.setContentsMargins(15, 20, 15, 15)
        self.admin_group.setLayout(self.admin_form)
        scroll_layout.addWidget(self.admin_group)

        # 学生填写字段（可编辑）
        self.student_group = QGroupBox(f"{ICONS['edit']} 个人基本信息（请如实填写）")
        self.student_form = QFormLayout()
        self.student_form.setSpacing(10)
        self.student_form.setContentsMargins(15, 20, 15, 15)
        self.student_group.setLayout(self.student_form)
        scroll_layout.addWidget(self.student_group)

        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)

        self.main_layout.addWidget(scroll_area, 1)  # 拉伸占满剩余空间

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        import_config_btn = QPushButton(f"{ICONS['import']} 导入支部配置")
        import_config_btn.setObjectName("secondary")
        import_config_btn.clicked.connect(self.import_admin_config)
        btn_layout.addWidget(import_config_btn)

        btn_layout.addStretch()

        save_btn = QPushButton(f"{ICONS['save']} 保存")
        save_btn.clicked.connect(self.save_data)
        btn_layout.addWidget(save_btn)

        goto_tpl_btn = QPushButton(f"下一步：选择模板 {ICONS['next']}")
        goto_tpl_btn.clicked.connect(self.go_to_template_list.emit)
        btn_layout.addWidget(goto_tpl_btn)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)

    def _update_save_status(self, saved: bool):
        """更新保存状态显示"""
        if saved:
            self.save_status.setText(f"{ICONS['success']} 已保存")
            self.save_status.setStyleSheet(SAVE_STATUS_SAVED)
        else:
            self.save_status.setText(f"{ICONS['warning']} 有未保存的更改")
            self.save_status.setStyleSheet(SAVE_STATUS_UNSAVED)

    def load_field_definitions(self):
        """加载字段定义（来自 resources/fields_definition.json）"""
        try:
            config = load_fields_definition()
        except FileNotFoundError:
            QMessageBox.critical(self, "错误", "缺少字段定义文件：resources/fields_definition.json")
            return
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取字段定义失败：{e}")
            return

        # 加载学生基础信息字段定义
        self.basic_field_defs = sorted(
            config.get("basic_info_fields", []),
            key=lambda x: x.get("display", {}).get("order", 0),
        )

        # 加载管理员字段定义（用于只读显示）
        admin_groups = sorted(
            config.get("admin_fields", []),
            key=lambda x: x.get("group_order", 0),
        )
        # 展平所有管理员字段，排除"系统设置"分组（不显示给学生）
        self.admin_field_defs = []
        for group in admin_groups:
            if group.get("group", "") != "系统设置":
                for field in group.get("fields", []):
                    self.admin_field_defs.append(field)

    def build_student_form(self):
        """根据字段定义动态生成学生填写表单"""
        # 清空旧表单
        while self.student_form.rowCount():
            self.student_form.removeRow(0)
        self.field_widgets.clear()

        for field_def in self.basic_field_defs:
            key = field_def.get("key")
            display = field_def.get("display", {}) or {}
            label_text = display.get("label", key)

            widget = create_widget(field_def, self.admin_config)
            self.field_widgets[key] = widget
            self.student_form.addRow(f"{label_text}：", widget)

    def load_data(self):
        """加载管理员配置和学生数据"""
        # 管理员配置（只读显示）
        admin_config = self.data_manager.get_admin_config()
        self._render_admin_config(admin_config)

        # 学生数据
        student_data = self.data_manager.get_student_data()
        basic_info = student_data.get("basic_info", {})

        for key, widget in self.field_widgets.items():
            value = basic_info.get(key, "")
            # 查找该 key 对应的字段定义，以便 set_widget_value 使用 format 等信息
            field_def = next((f for f in self.basic_field_defs if f.get("key") == key), None)
            set_widget_value(widget, value, field_def, self.admin_config)

    def _render_admin_config(self, config: dict):
        """根据字段定义动态渲染管理员配置为只读信息"""
        # 清空旧行
        while self.admin_form.rowCount():
            self.admin_form.removeRow(0)

        # 如果没有加载字段定义，使用空列表
        if not hasattr(self, "admin_field_defs"):
            self.admin_field_defs = []

        # 按 order 排序字段
        sorted_fields = sorted(
            self.admin_field_defs,
            key=lambda x: x.get("display", {}).get("order", 0),
        )

        # 根据字段定义动态渲染
        for field_def in sorted_fields:
            path = field_def.get("path", "")
            display = field_def.get("display", {}) or {}
            label_text = display.get("label", field_def.get("key", ""))

            # 根据 path 从嵌套结构中获取值
            value = get_value_by_path(config, path, "")

            label = QLabel(str(value))
            label.setStyleSheet("color: #555;")
            self.admin_form.addRow(f"{label_text}：", label)

    def _collect_basic_info_from_form(self) -> dict:
        """从表单采集学生基础信息"""
        basic_info: dict[str, str] = {}
        for key, widget in self.field_widgets.items():
            field_def = next((f for f in self.basic_field_defs if f.get("key") == key), None)
            basic_info[key] = get_widget_value(widget, field_def, self.admin_config)
        return basic_info

    def save_data(self):
        """保存数据"""
        try:
            student_data = self.data_manager.get_student_data()
            student_data["basic_info"] = self._collect_basic_info_from_form()
            self.data_manager.save_student_data(student_data)
            self._update_save_status(True)
            QMessageBox.information(self, "提示", "基本信息已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def import_admin_config(self):
        """学生端导入支部管理员配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入支部配置",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        is_success, message = self.data_manager.import_admin_config(file_path, mode='student')
        if is_success:
            # 重新加载配置并刷新显示
            self.admin_config = self.data_manager.get_admin_config()
            self.load_data()
            QMessageBox.information(self, "提示", f"支部配置已导入并锁定。\n\n{message}")
        else:
            QMessageBox.warning(self, "错误", f"导入失败：{message}")