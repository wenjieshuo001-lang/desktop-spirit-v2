#!/usr/bin/env python3
"""桌面精灵 V2 — 入口。"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPainterPath

from config import settings
from core.database import init_db, clean_old_data
from core.monitor import ActivityMonitor
from core.recorder import Recorder
from core.analyzer import Analyzer
from ui.main_window import MainWindow
from ui.spirit_avatar import SpiritAvatar

# ── 日志 ────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "spirit.log",), encoding="utf-8"),
    ]
)
logger = logging.getLogger("main")


def main():
    logger.info("=" * 40)
    logger.info("🧠 桌面精灵 V2")
    logger.info("=" * 40)

    # 1. DB
    try:
        init_db()
        clean_old_data(settings.get("privacy.retention_days", 30))
        logger.info("✅ 数据库就绪")
    except Exception as e:
        logger.critical(f"数据库失败: {e}")
        return 1

    # 2. 引擎组件
    analyzer = Analyzer()
    recorder = Recorder(on_new_sequence=analyzer.on_new_sequence)
    monitor = ActivityMonitor(on_event=recorder.handle)

    # 3. Qt App
    app = QApplication(sys.argv)
    app.setApplicationName("桌面精灵 V2")
    app.setQuitOnLastWindowClosed(False)

    # 4. UI
    window = MainWindow()
    spirit = SpiritAvatar()
    window.set_spirit(spirit)
    spirit.clicked.connect(window.show)
    spirit.clicked.connect(window.raise_)

    # 5. 启动监控
    if settings.get("monitor.enabled", True):
        monitor.start()
        window._monitor = monitor
        window._recorder = recorder

    # 6. 覆盖监听切换
    orig_toggle = window._toggle_mon
    def toggled():
        orig_toggle()
        if window.is_monitoring():
            monitor.start()
        else:
            monitor.stop()
    window._toggle_mon = toggled

    # 7. 首次延迟分析
    QTimer.singleShot(60000, lambda: _first_analysis(window, analyzer))

    # 8. 定时分析
    def schedule():
        from datetime import datetime
        now = datetime.now()
        for h in [12, 18]:
            sec = (h - now.hour) * 3600 - now.minute * 60 - now.second
            if sec > 0:
                QTimer.singleShot(sec * 1000, lambda: window._analyze_now())
    schedule()

    # 9. 关闭事件 → 隐藏
    window.closeEvent = lambda e: (window.hide(), e.ignore())

    # 10. 托盘
    _setup_tray(app, window, spirit)

    # 11. 启动
    spirit.show()
    spirit.set_mood("happy", "V2 来啦！✨")
    QTimer.singleShot(800, window.show)

    logger.info("🎉 桌面精灵 V2 就绪！")
    return app.exec_()


def _first_analysis(window, analyzer):
    logger.info("首次分析...")
    try:
        window._analyze_now()
    except Exception as e:
        logger.error(f"首次分析失败: {e}")


def _setup_tray(app, window, spirit):
    tray = QSystemTrayIcon()
    tray.setToolTip("🧠 桌面精灵 V2")
    # 生成图标
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor("#667eea")))
    path = QPainterPath()
    path.addRoundedRect(2, 2, 28, 28, 8, 8)
    p.drawPath(path)
    p.setPen(QColor("white"))
    p.drawText(pm.rect(), Qt.AlignCenter, "🧠")
    p.end()
    tray.setIcon(QIcon(pm))

    menu = QMenu()
    menu.addAction("📋 控制台", window.show).triggered.connect(window.raise_)
    menu.addSeparator()
    menu.addAction("👋 隐藏精灵", spirit.hide)
    menu.addAction("✨ 显示精灵", spirit.show)
    menu.addSeparator()
    menu.addAction("🔍 立即分析", window._analyze_now)
    menu.addSeparator()
    menu.addAction("❌ 退出", app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda r: window.show() if r == QSystemTrayIcon.DoubleClick else None)
    tray.show()


if __name__ == "__main__":
    sys.exit(main())
