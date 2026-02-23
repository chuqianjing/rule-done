#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
进度对话框组件
用于显示操作进度，支持确定进度和不确定进度模式
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal


class ProgressDialog(QDialog):
    """进度对话框"""
    
    # 取消信号
    cancelled = pyqtSignal()

    def __init__(self, title: str = "处理中", parent=None, cancelable: bool = True):
        """
        初始化进度对话框
        
        Args:
            title: 对话框标题
            parent: 父窗口
            cancelable: 是否可取消
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(420, 160)
        self.setWindowFlags(
            Qt.WindowType.Dialog 
            | Qt.WindowType.CustomizeWindowHint 
            | Qt.WindowType.WindowTitleHint
        )
        self.setModal(True)
        
        self._is_cancelled = False
        self._cancelable = cancelable
        
        self._init_ui()

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 状态文本
        self.status_label = QLabel("正在处理...")
        self.status_label.setStyleSheet("font-size: 14px; color: #333;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                height: 22px;
                background-color: #f5f5f5;
            }
            QProgressBar::chunk {
                background-color: #1a73e8;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 详情文本
        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("font-size: 12px; color: #666;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #333;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setVisible(self._cancelable)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def set_progress(self, value: int, status: str = None, detail: str = None):
        """
        更新进度
        
        Args:
            value: 进度值 (0-100)
            status: 状态文本（可选）
            detail: 详情文本（可选）
        """
        self.progress_bar.setValue(value)
        if status is not None:
            self.status_label.setText(status)
        if detail is not None:
            self.detail_label.setText(detail)

    def set_indeterminate(self, status: str = "处理中..."):
        """
        设置为不确定进度模式（循环动画）
        
        Args:
            status: 状态文本
        """
        self.progress_bar.setRange(0, 0)  # 设置为不确定模式
        self.status_label.setText(status)
        self.progress_bar.setTextVisible(False)

    def set_determinate(self, max_value: int = 100):
        """
        设置为确定进度模式
        
        Args:
            max_value: 最大值
        """
        self.progress_bar.setRange(0, max_value)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

    def set_cancelable(self, cancelable: bool):
        """设置是否可取消"""
        self._cancelable = cancelable
        self.cancel_btn.setVisible(cancelable)

    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._is_cancelled

    def _on_cancel(self):
        """取消按钮点击处理"""
        self._is_cancelled = True
        self.cancelled.emit()
        self.reject()

    def complete(self, status: str = "完成"):
        """
        标记为完成状态
        
        Args:
            status: 完成状态文本
        """
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_label.setText(status)
        self.cancel_btn.setText("关闭")
        self.cancel_btn.setVisible(True)
        # 修改样式为成功样式
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                height: 22px;
                background-color: #f5f5f5;
            }
            QProgressBar::chunk {
                background-color: #34a853;
                border-radius: 3px;
            }
        """)

    def error(self, status: str = "出错"):
        """
        标记为错误状态
        
        Args:
            status: 错误状态文本
        """
        self.status_label.setText(status)
        self.status_label.setStyleSheet("font-size: 14px; color: #ea4335;")
        self.cancel_btn.setText("关闭")
        self.cancel_btn.setVisible(True)
        # 修改样式为错误样式
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                height: 22px;
                background-color: #f5f5f5;
            }
            QProgressBar::chunk {
                background-color: #ea4335;
                border-radius: 3px;
            }
        """)
