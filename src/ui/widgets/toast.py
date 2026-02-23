#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
轻提示组件（Toast）
用于显示临时性的提示信息，会自动消失
"""

from PyQt6.QtWidgets import QLabel, QWidget, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont


class Toast(QLabel):
    """轻提示组件"""
    
    # 预设样式
    STYLES = {
        "info": {
            "bg": "#333333",
            "color": "#ffffff",
            "icon": "ℹ️",
        },
        "success": {
            "bg": "#34a853",
            "color": "#ffffff",
            "icon": "✓",
        },
        "warning": {
            "bg": "#fbbc04",
            "color": "#333333",
            "icon": "⚠️",
        },
        "error": {
            "bg": "#ea4335",
            "color": "#ffffff",
            "icon": "✗",
        },
    }

    def __init__(
        self,
        message: str,
        parent: QWidget = None,
        duration: int = 3000,
        style: str = "info",
        show_icon: bool = True,
    ):
        """
        初始化 Toast
        
        Args:
            message: 提示信息
            parent: 父组件
            duration: 显示时长（毫秒）
            style: 样式类型 (info, success, warning, error)
            show_icon: 是否显示图标
        """
        super().__init__(parent)
        
        self._duration = duration
        self._style_type = style
        
        # 设置内容
        style_config = self.STYLES.get(style, self.STYLES["info"])
        text = f"{style_config['icon']} {message}" if show_icon else message
        self.setText(text)
        
        # 设置样式
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {style_config['bg']};
                color: {style_config['color']};
                padding: 12px 20px;
                border-radius: 6px;
                font-size: 14px;
            }}
        """)
        
        # 设置属性
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        
        # 透明度效果
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        
        # 调整大小
        self.adjustSize()

    def show_toast(self):
        """显示 Toast"""
        if self.parent():
            # 计算位置（居中显示在父窗口底部）
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            y = parent_rect.height() - self.height() - 50
            self.move(x, y)
        
        self.show()
        self.raise_()
        
        # 设置自动隐藏定时器
        QTimer.singleShot(self._duration, self._start_fade_out)

    def _start_fade_out(self):
        """开始淡出动画"""
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(300)
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._fade_animation.finished.connect(self._on_fade_finished)
        self._fade_animation.start()

    def _on_fade_finished(self):
        """淡出动画完成"""
        self.hide()
        self.deleteLater()

    @staticmethod
    def show_message(
        parent: QWidget,
        message: str,
        duration: int = 3000,
        style: str = "info",
        show_icon: bool = True,
    ):
        """
        便捷方法：显示一个 Toast
        
        Args:
            parent: 父组件
            message: 提示信息
            duration: 显示时长（毫秒）
            style: 样式类型
            show_icon: 是否显示图标
        """
        toast = Toast(message, parent, duration, style, show_icon)
        toast.show_toast()
        return toast

    @staticmethod
    def info(parent: QWidget, message: str, duration: int = 3000):
        """显示信息提示"""
        return Toast.show_message(parent, message, duration, "info")

    @staticmethod
    def success(parent: QWidget, message: str, duration: int = 3000):
        """显示成功提示"""
        return Toast.show_message(parent, message, duration, "success")

    @staticmethod
    def warning(parent: QWidget, message: str, duration: int = 3000):
        """显示警告提示"""
        return Toast.show_message(parent, message, duration, "warning")

    @staticmethod
    def error(parent: QWidget, message: str, duration: int = 3000):
        """显示错误提示"""
        return Toast.show_message(parent, message, duration, "error")
