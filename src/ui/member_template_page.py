#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
成员模板填写页面
"""

from datetime import datetime
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QMessageBox,
    QHBoxLayout,
    QFormLayout,
    QFileDialog,
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtGui import QPixmap, QIcon
from pathlib import Path
from src.ui.template_page import TemplatePage
from src.utils.widget_binding import create_widget, set_widget_value
from src.utils.styles import ICONS


class MemberTemplatePage(TemplatePage):
    """成员模板填写页面"""

    mode = "member"
    lock_document_signal = Signal()

    def __init__(self, template_id: str = "template_001", parent=None):
        self._is_initialized = False      # 用于showEvent()，在widget完全初始化后才执行检查逻辑
        super().__init__(template_id=template_id, parent=parent)
        self._is_initialized = True
    
    def tip_message(self) -> str:
        """成员模式的提示信息"""
        return """成员可根据字段旁的提示完善相关信息：
    - 已锁定：管理员已为该字段设置固定值，成员无需修改
    - 待确认：管理员已为该字段填写相应值以用于提示，成员可根据自身情况完善信息或保持原值
    - 无提示：管理员未配置该字段，成员需根据自身情况来填写"""


    def _show_basic_info_error(self):
        QMessageBox.critical(self, "错误", "请先完善基本信息")
        
    def check_basic_info(self):
        """专门负责检查数据的逻辑（仅成员模式）"""
        if self.basic_form is None:
            return
        for row in range(self.basic_form.rowCount()):
            item = self.basic_form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if item and item.widget() and not item.widget().text():
                QTimer.singleShot(100, lambda: self._show_basic_info_error())
                break

    def showEvent(self, event):
        """每次页面显示时都会运行"""
        super().showEvent(event)
        if self._is_initialized and self.mode == "member":
            self.check_basic_info()

    def _add_field_to_form(self, field_def: dict):
        """添加成员字段到表单"""
        key = field_def.get("key")
        widget = create_widget(field_def)
        self.field_widgets[key] = widget

        data_src = self.placeholder_mapping.get(key, {}).get("source")
        is_tip = self.placeholder_mapping.get(key, {}).get("is_tip", False)

        if data_src == "admin_template_data" and not is_tip:
            field_container = QWidget()
            field_layout = QHBoxLayout()
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(10)
            # 锁定提示
            lock_label = QLabel(f"{ICONS['lock']} 已锁定")
            lock_label.setStyleSheet("color: #888; font-size: 12px;")
            lock_label.setToolTip("此字段由管理员统一配置，不可修改")
            field_layout.addWidget(lock_label)
             # 表单
            field_layout.addWidget(widget, 1)

            field_container.setLayout(field_layout)
            self.template_form.addRow(f"{key}：", field_container)

            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(True)
            elif hasattr(widget, "setEnabled"):
                widget.setEnabled(False)
        elif is_tip:
            field_container = QWidget()
            field_layout = QHBoxLayout()
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(10)
            # 填写提示
            lock_label = QLabel(f"{ICONS['pen']} 待确认")
            lock_label.setStyleSheet("color: #888; font-size: 12px;")
            lock_label.setToolTip("此字段管理员已统一配置，但可修改")
            field_layout.addWidget(lock_label)
            # 表单
            field_layout.addWidget(widget, 1)

            field_container.setLayout(field_layout)
            self.template_form.addRow(f"{key}：", field_container)
        elif data_src == "member_template_data":
            self.template_form.addRow(f"{key}：", widget)

    def _render_basic_data(self):
        """根据字段定义动态显示只读基础信息"""
        while self.basic_form.rowCount():
            self.basic_form.removeRow(0)

        member_template_data = self.data_manager.get_member_info("template_data", self.template_id) or {}
        member_template_locked = member_template_data.get("locked", False)
        if member_template_locked:
            member_template_basic_entry = member_template_data.get("basic_entry", {})
            for key, value in member_template_basic_entry.items():
                label = QLabel(str(value))
                label.setObjectName(key)
                label.setStyleSheet("color: #555;")
                self.basic_form.addRow(f"{key}：", label)
            return
        
        member_basic_data = self.data_manager.get_member_info("basic_data") or {}
        admin_basic_data = self.data_manager.get_admin_config("basic_data") or {}

        display_priority = {"member_basic_data": 1}
        sorted_placeholder_mapping = dict(sorted(
            self.placeholder_mapping.items(),
            key=lambda item: (display_priority.get(item[1].get("source"), 999),
                              item[1].get("order", 999))))
        for placeholder, mapping in sorted_placeholder_mapping.items():
            if mapping.get("source") not in ["member_basic_data", "admin_basic_data"]:
                continue
            key = mapping.get("key", "")
            group = mapping.get("group", "")
            format = mapping.get("format", "")
            if mapping.get("source") == "member_basic_data":
                value = member_basic_data.get(key)
                if format == "YYYY年MM月" and value:
                    try:
                        dt = datetime.strptime(value, "%Y年%m月%d日")
                        value = f"{dt.year}年{dt.month}月"
                    except ValueError:
                        pass  # 日期格式不匹配时保持原值
            elif mapping.get("source") == "admin_basic_data":
                value = admin_basic_data.get(group, {}).get(key)
            label = QLabel(str(value))
            label.setObjectName(placeholder)
            label.setStyleSheet("color: #555;")
            self.basic_form.addRow(f"{placeholder}：", label)

    def load_data(self):
        """加载成员模板填写数据"""
        self._render_basic_data()

        member_template_data = self.data_manager.get_member_info("template_data", self.template_id) or {}
        admin_template_data = self.data_manager.get_admin_config("template_data", self.template_id) or {}

        for key, widget in self.field_widgets.items():
            data_src = self.placeholder_mapping.get(key, {}).get("source")
            if data_src == "member_template_data":
                value = member_template_data.get(key, "")
            elif data_src == "admin_template_data":
                value = admin_template_data.get(key, {}).get("value", "")

            field_def = self.get_field_def(key)
            set_widget_value(widget, value, field_def)

    def save_data(self):
        """保存成员模板填写数据"""
        try:
            template_data = self._collect_template_data_from_form()
            self.data_manager.save_member_info("template_page", template_data, self.template_id)
            # 成员模板页的数据保存操作会影响placeholder_mapping，故需要重新加载字段、表单、数据
            self.load_fields()
            self.build_template_forms()
            self.load_data()
            QMessageBox.information(self, "提示", "材料数据已保存。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def export_document(self):
        """导出 Word 文档"""
        try:
            self.save_data()
            output_path = self.template_engine.generate_document(self.template_id)
            QMessageBox.information(self, "提示", f"文档已导出：\n{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败：{e}")

    def lock_document(self):
        """锁定材料，禁止修改"""
        try:
            # 先弹出确认框，确认后再执行锁定操作
            reply = QMessageBox.question(self, "确认锁定", "锁定后将无法修改材料，是否继续？", QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
            basic_entry = self._collect_basic_data_from_form()
            template_entry = self._collect_template_data_from_form()
            self.data_manager.lock_member_template(self.template_id, basic_entry, template_entry)
            self.lock_document_signal.emit()
            QMessageBox.information(self, "提示", "材料已锁定，无法修改。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"锁定失败：{e}")

    def _collect_basic_data_from_form(self) -> dict:
        """从表单采集基本信息数据"""
        data: dict[str, str] = {}
        for i in range(self.basic_form.rowCount()):
            # itemAt(row, role) 获取指定行和角色的项
            # QFormLayout.FieldRole 指的是右侧的输入框/显示控件列
            item = self.basic_form.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if item:
                widget = item.widget()
                if isinstance(widget, QLabel):
                    data[widget.objectName()] = widget.text()
        return data

    def _get_archive_image_path(self, relative_path: str) -> Path:
        """获取档案图片路径"""
        return Path(relative_path)

    def _show_image_preview(self, relative_path: str):
        """预览档案图片"""
        image_path = self._get_archive_image_path(relative_path)
        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle("图片预览")
        preview_dialog.resize(900, 700)

        layout = QVBoxLayout(preview_dialog)
        scroll_area = QScrollArea(preview_dialog)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setMinimumSize(760, 560)

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            image_label.setText("图片加载失败")
        else:
            image_label.setPixmap(
                pixmap.scaled(
                    820,
                    620,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        scroll_area.setWidget(image_label)
        layout.addWidget(scroll_area)

        close_btn = QPushButton("关闭", preview_dialog)
        close_btn.clicked.connect(preview_dialog.accept)
        layout.addWidget(close_btn)

        preview_dialog.exec()
    
    def _upload_archive_image(self, parent: QWidget | None = None) -> bool:
        """上传档案图片，成功返回 True。"""
        file_path, _ = QFileDialog.getOpenFileName(
            parent or self,
            "选择档案图片",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.webp);;所有文件 (*)",
        )
        if not file_path:
            return False

        try:
            image_meta = self.data_manager.save_member_archive_image(
                source_file_path=file_path,
                template_id=self.template_id,
            )
            QMessageBox.information(
                parent or self,
                "提示",
                f"档案图片已保存：\n{image_meta.get('relative_path', '')}",
            )
            return True
        except FileExistsError:
            reply = QMessageBox.question(
                parent or self,
                "文件已存在",
                "检测到同名图片。\n选择“是”覆盖，选择“否”自动重命名保存，选择“取消”放弃上传。",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Cancel:
                return False

            overwrite = reply == QMessageBox.Yes
            auto_rename = reply == QMessageBox.No

            try:
                image_meta = self.data_manager.save_member_archive_image(
                    source_file_path=file_path,
                    template_id=self.template_id,
                    overwrite=overwrite,
                    auto_rename=auto_rename,
                )
                QMessageBox.information(
                    parent or self,
                    "提示",
                    f"档案图片已保存：\n{image_meta.get('relative_path', '')}",
                )
                return True
            except Exception as e:
                QMessageBox.critical(parent or self, "错误", f"上传失败：{e}")
                return False
        except Exception as e:
            QMessageBox.critical(parent or self, "错误", f"上传失败：{e}")
            return False
        
    def manage_archive(self):
        """查看并删除已上传的档案图片"""
        dialog = QDialog(self)
        dialog.setWindowTitle("档案图片管理")
        dialog.resize(640, 460)

        layout = QVBoxLayout(dialog)
        image_list = QListWidget(dialog)
        layout.addWidget(image_list)

        btn_layout = QHBoxLayout()
        upload_btn = QPushButton("上传图片", dialog)
        delete_btn = QPushButton("删除选中", dialog)
        preview_btn = QPushButton("预览选中", dialog)
        btn_layout.addStretch()
        btn_layout.addWidget(upload_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(preview_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        def load_images():
            image_list.clear()
            images = self.data_manager.get_member_archive_images(self.template_id)
            if not images:
                placeholder = QListWidgetItem("暂无已上传图片")
                placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
                image_list.addItem(placeholder)
                return

            for image in images:
                file_name = image.get("file_name", "未知文件")
                # size_bytes = image.get("size_bytes", 0)
                uploaded_at = image.get("uploaded_at", "")
                dt = datetime.fromisoformat(uploaded_at)
                uploaded_at = dt.strftime("%Y-%m-%d %H:%M")
                relative_path = image.get("relative_path", "")
                # size_kb = round(size_bytes / 1024, 2) if isinstance(size_bytes, (int, float)) else 0
                image_path = self._get_archive_image_path(relative_path)

                item_text = f"{file_name} | {uploaded_at}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, relative_path)
                if image_path.exists():
                    pixmap = QPixmap(str(image_path))
                    if not pixmap.isNull():
                        item.setIcon(
                            QIcon(
                                pixmap.scaled(
                                    56,
                                    56,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
                            )
                        )
                image_list.addItem(item)

        def preview_selected_image():
            current_item = image_list.currentItem()
            if not current_item:
                QMessageBox.warning(dialog, "提示", "请先选择要预览的图片")
                return

            relative_path = current_item.data(Qt.ItemDataRole.UserRole)
            if not relative_path:
                return

            self._show_image_preview(relative_path)

        def delete_selected_image():
            current_item = image_list.currentItem()
            if not current_item:
                QMessageBox.warning(dialog, "提示", "请先选择要删除的图片")
                return

            relative_path = current_item.data(Qt.ItemDataRole.UserRole)
            if not relative_path:
                return

            reply = QMessageBox.question(
                dialog,
                "确认删除",
                "删除后无法恢复，是否继续？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

            try:
                self.data_manager.remove_member_archive_image(
                    template_id=self.template_id,
                    relative_path=relative_path,
                    delete_file=True,
                )
                QMessageBox.information(dialog, "提示", "图片已删除")
                load_images()
            except Exception as e:
                QMessageBox.critical(dialog, "错误", f"删除失败：{e}")

        def upload_new_image():
            if self._upload_archive_image(parent=dialog):
                load_images()

        upload_btn.clicked.connect(upload_new_image)
        delete_btn.clicked.connect(delete_selected_image)
        preview_btn.clicked.connect(preview_selected_image)
        image_list.itemDoubleClicked.connect(lambda item: self._show_image_preview(item.data(Qt.ItemDataRole.UserRole)))

        load_images()
        dialog.exec()
        


