"""V2 可复用 UI 组件。"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QTimer
from PyQt5.QtGui import QPainter, QColor, QBrush, QLinearGradient


class StatusBanner(QFrame):
    """顶部渐变状态条。"""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        self._label = QLabel(text)
        self._label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(self._label)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0, QColor("#667eea"))
        grad.setColorAt(1, QColor("#764ba2"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 8, 8)
        p.end()

    def set_text(self, text: str):
        self._label.setText(text)


class StatCard(QFrame):
    """统计卡片。"""

    def __init__(self, title: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(140, 70)
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        self._value = QLabel(value)
        self._value.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold;")
        self._value.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._value)
        self._title = QLabel(title)
        self._title.setStyleSheet("color: #888; font-size: 11px;")
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)

    def set_value(self, val: str):
        self._value.setText(val)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(self._color).lighter(180)))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 10, 10)
        p.end()
