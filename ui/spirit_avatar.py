"""V2 桌面精灵 —— 流畅动画、多表情、可换肤。"""

import math
from PyQt5.QtWidgets import QWidget, QLabel, QMenu, QAction
from PyQt5.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QBrush, QPainterPath,
    QLinearGradient, QRadialGradient,
)

# 表情库 (表情, 图标, 主色, 渐变色, 默认消息)
MOODS = {
    "idle":     ("◕‿◕", "💤", "#BBDEFB", "#90CAF9", "我在这里哦~"),
    "thinking": ("⊙_⊙", "🧠", "#FFF9C4", "#FFD54F", "正在学习..."),
    "learned":  ("☆⌒◕‿◕⌒☆", "✨", "#C8E6C9", "#81C784", "发现新习惯啦！"),
    "working":  ("•̀ᴗ•́", "⚡", "#FFE0B2", "#FFB74D", "正在执行..."),
    "happy":    ("◕‿◕✿", "🌟", "#E1BEE7", "#CE93D8", "今天学了很多！"),
    "error":    ("╯︵╰", "😅", "#FFCDD2", "#E57373", "出错了呢"),
    "busy":     (">_<", "⏰", "#FFE0B2", "#FF8A65", "你好忙呀"),
    "sleep":    ("∪｡∪", "💤", "#E3F2FD", "#BBDEFB", "休息中..."),
}


class SpiritAvatar(QWidget):
    """可拖动的桌面精灵。"""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._size = 140
        self._mood = "idle"
        self._message = ""
        self._breath = 0.0
        self._hover = False
        self._drag_pos = None
        self._habit_count = 0
        self._sparkle = 0  # 闪烁效果相位

        # 窗口属性
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(self._size, int(self._size * 1.35))
        self.setMouseTracking(True)

        # 标签
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setGeometry(4, 4, self._size - 8, self._size - 8)
        ft = QFont("Microsoft YaHei", 11)
        ft.setBold(False)
        self._label.setFont(ft)

        # 动画
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(33)  # ~30fps

        # 自动回到 idle
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(lambda: self.set_mood("idle"))
        self._idle_timer.setSingleShot(True)

        # 初始位置
        self._place()
        self.set_mood("idle", "你好！我是桌面精灵 ✨")

    def _place(self):
        from PyQt5.QtWidgets import QDesktopWidget
        d = QDesktopWidget().availableGeometry()
        self.move(d.width() - self._size - 30,
                  d.height() - int(self._size * 1.35) - 50)

    # ── 状态 ──────────────────────────────────────

    def set_mood(self, mood: str, msg: str = ""):
        mood = mood if mood in MOODS else "idle"
        face, icon, color1, color2, default = MOODS[mood]
        self._mood = mood
        self._message = msg or default
        self._label.setText(f"{icon}\n{face}\n{self._message}")
        self._label.setStyleSheet(
            f"color: #333; background: {color1}; "
            f"border-radius: 8px; padding: 5px; font-size: 11px;"
        )
        self.update()
        if mood != "idle":
            self._idle_timer.start(4000)

    def on_new_habit(self, n: int = 1):
        self._habit_count += n
        self.set_mood("learned", f"发现 {n} 个新习惯 ✨")

    def on_exec_start(self, name: str):
        self.set_mood("working", f"执行: {name[:12]}...")

    def on_exec_done(self, name: str, ok: bool):
        if ok:
            self.set_mood("happy", f"✅ {name[:12]}")
        else:
            self.set_mood("error", f"❌ {name[:12]}")

    # ── 动画 ──────────────────────────────────────

    def _tick(self):
        self._breath += 0.07
        self._sparkle += 0.04
        # 每 33ms 触发一次重绘（呼吸效果通过 paintEvent 实现）
        self.update()

    # ── 绘制 ──────────────────────────────────────

    def paintEvent(self, event):
        _, _, base_c, grad_c, _ = MOODS.get(self._mood, MOODS["idle"])
        w, h = self.width(), self.height()
        s = self._size

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # 呼吸偏移
        breathe = math.sin(self._breath) * 1.5

        # 渐变背景
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(base_c))
        grad.setColorAt(1, QColor(grad_c))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)

        # 主体：顶部圆形
        body = QPainterPath()
        body.addRoundedRect(QRectF(2, 2 + breathe, w - 4, h - 20 + breathe), 14, 14)
        p.drawPath(body)

        # 底部小尾巴（三角形）
        tail = QPainterPath()
        tail.moveTo(s // 2 - 8, h - 18 + breathe)
        tail.lineTo(s // 2, h - 6 + breathe)
        tail.lineTo(s // 2 + 8, h - 18 + breathe)
        tail.closeSubpath()
        color = QColor(grad_c)
        color.setAlpha(180)
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        p.drawPath(tail)

        # 顶部高光
        if not self._hover:
            glow = QRadialGradient(w // 2, 8, w // 3)
            glow.setColorAt(0, QColor(255, 255, 255, 120))
            glow.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(glow))
            highlight = QPainterPath()
            highlight.addRoundedRect(QRectF(8, 4, w - 16, h // 2), 10, 10)
            p.drawPath(highlight)

        p.end()

    # ── 交互 ──────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)
        self._hover = True

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._drag_pos:
            moved = (e.globalPos() - self._drag_pos - self.pos()).manhattanLength()
            if moved < 8:
                self.clicked.emit()
        self._drag_pos = None

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.addAction("📋 控制台", self.clicked.emit)
        menu.addSeparator()
        menu.addAction("🔍 立即分析", lambda: self.set_mood("thinking", "分析中..."))
        menu.addSeparator()
        menu.addAction("👋 隐藏", self.hide)
        menu.exec_(e.globalPos())
