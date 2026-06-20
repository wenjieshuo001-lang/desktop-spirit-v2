"""V2 主控制台 —— 搜索、筛选、导出导入、统计看板。"""

import json
import os
import logging
from datetime import datetime, date

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QSplitter, QMessageBox, QFrame, QLineEdit,
    QAbstractItemView, QTabWidget, QStatusBar, QApplication,
    QFileDialog, QComboBox, QCheckBox,
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QColor

from core import database as db
from core.analyzer import Analyzer
from core.executor import get_executor
from core import codex_integration as cx
from ui.widgets import StatusBanner, StatCard
from ui.habit_detail import HabitDialog

logger = logging.getLogger(__name__)

COLOR_HIGH = QColor("#4CAF50")
COLOR_MED = QColor("#FF9800")
COLOR_LOW = QColor("#F44336")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._analyzer = Analyzer()
        self._spirit = None

        self.setWindowTitle("🧠 桌面精灵 V2 — 习惯学习中心")
        self.setMinimumSize(850, 600)
        self.resize(960, 680)

        self._build()
        self._setup_timers()
        self.refresh()

    def set_spirit(self, spirit):
        self._spirit = spirit

    # ── UI 构建 ──────────────────────────────────

    def _build(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)

        # 顶部横幅
        self._banner = StatusBanner("🧠 桌面精灵 V2 · 习惯学习中心")
        layout.addWidget(self._banner)

        # 标签页
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._build_habits_tab()
        self._build_stats_tab()

        # 底部工具栏
        tb = QFrame()
        tb.setStyleSheet("background:#f5f5f5;border-radius:5px;padding:4px;")
        tbb = QHBoxLayout(tb)
        tbb.setContentsMargins(5, 4, 5, 4)

        self._mon_btn = QPushButton("⏹ 停止监听")
        self._mon_btn.setStyleSheet("background:#e74c3c;color:white;padding:5px 14px;border-radius:4px;")
        self._mon_btn.clicked.connect(self._toggle_mon)
        tbb.addWidget(self._mon_btn)

        tbb.addWidget(QLabel("|"))

        QPushButton("🔍 分析", clicked=self._analyze_now).setParent(self)
        an_btn = QPushButton("🔍 分析")
        an_btn.clicked.connect(self._analyze_now)
        tbb.addWidget(an_btn)

        rf_btn = QPushButton("🔄 刷新")
        rf_btn.clicked.connect(self.refresh)
        tbb.addWidget(rf_btn)

        tbb.addWidget(QLabel("|"))

        cx_btn = QPushButton("🤖 Codex")
        cx_btn.setToolTip("向 Codex 同步精灵状态（进化/报错/升级）")
        cx_btn.clicked.connect(self._sync_codex)
        tbb.addWidget(cx_btn)

        tbb.addStretch()

        self._ev_label = QLabel("今日事件: 0")
        tbb.addWidget(self._ev_label)

        layout.addWidget(tb)

        self.statusBar().showMessage("就绪 | 双击习惯编辑 | 精灵正在学习...")

    # ── 习惯标签页 ───────────────────────────────

    def _build_habits_tab(self):
        tab = QWidget()
        self._tabs.addTab(tab, "📋 习惯")

        layout = QVBoxLayout(tab)

        # 搜索和筛选栏
        top = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索习惯...")
        self._search_input.textChanged.connect(self._load_habits)
        top.addWidget(self._search_input)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["全部", "时间型", "工作流", "点击型", "活跃时段"])
        self._filter_combo.currentTextChanged.connect(self._load_habits)
        top.addWidget(self._filter_combo)

        self._auto_filter = QCheckBox("仅自动")
        self._auto_filter.toggled.connect(self._load_habits)
        top.addWidget(self._auto_filter)

        top.addStretch()

        self._hc_label = QLabel("共 0 个习惯")
        self._hc_label.setStyleSheet("color:#667eea;font-weight:bold;")
        top.addWidget(self._hc_label)

        layout.addLayout(top)

        # 表格
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels(["名称", "类型", "置信度", "频率", "时间", "窗口", "自动", "操作"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_double)
        layout.addWidget(self._table)

    # ── 统计标签页 ───────────────────────────────

    def _build_stats_tab(self):
        tab = QWidget()
        self._tabs.addTab(tab, "📊 统计")

        layout = QVBoxLayout(tab)

        # 今日概览卡片
        cards = QHBoxLayout()
        self._card_clicks = StatCard("点击", "0", "#4CAF50")
        cards.addWidget(self._card_clicks)
        self._card_keys = StatCard("按键", "0", "#2196F3")
        cards.addWidget(self._card_keys)
        self._card_habits = StatCard("习惯", "0", "#9C27B0")
        cards.addWidget(self._card_habits)
        self._card_active = StatCard("活跃分钟", "0", "#FF9800")
        cards.addWidget(self._card_active)
        cards.addStretch()
        layout.addLayout(cards)

        # 应用排行
        app_g = QGroupBox("应用活跃（今日）")
        app_l = QVBoxLayout(app_g)
        self._app_table = QTableWidget()
        self._app_table.setColumnCount(2)
        self._app_table.setHorizontalHeaderLabels(["窗口", "事件数"])
        self._app_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._app_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        app_l.addWidget(self._app_table)
        layout.addWidget(app_g)

        # 导出/导入
        ex_btn = QPushButton("📤 导出习惯")
        ex_btn.clicked.connect(self._export)
        ex_btn.setFixedWidth(120)
        im_btn = QPushButton("📥 导入习惯")
        im_btn.clicked.connect(self._import_)
        im_btn.setFixedWidth(120)
        ex_im = QHBoxLayout()
        ex_im.addWidget(ex_btn)
        ex_im.addWidget(im_btn)
        ex_im.addStretch()
        layout.addLayout(ex_im)

    # ── 定时器 ───────────────────────────────────

    def _setup_timers(self):
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._tick)
        self._refresh_timer.start(10000)

    def _tick(self):
        try:
            db.update_daily_stats()
            self._update_stats()
            self._update_event_count()
        except Exception:
            pass

    # ── 数据加载 ─────────────────────────────────

    def refresh(self):
        self._load_habits()
        self._update_stats()
        self._update_event_count()

    def _load_habits(self):
        kw = self._search_input.text().strip()
        filter_type = self._filter_combo.currentText()
        only_auto = self._auto_filter.isChecked()

        if kw:
            habits = db.search_habits(kw)
        else:
            habits = db.get_habits(active_only=True)

        # 客户端筛选
        filtered = []
        for h in habits:
            if only_auto and not h.get("is_auto"):
                continue
            if filter_type != "全部":
                type_map = {"时间型": "time_window", "工作流": "window_sequence",
                            "点击型": "click_pattern", "活跃时段": "active_hour"}
                mapped = type_map.get(filter_type, "")
                if h.get("pattern_type") != mapped:
                    continue
            filtered.append(h)

        self._hc_label.setText(f"共 {len(filtered)} 个习惯")
        self._table.setRowCount(len(filtered))

        for i, h in enumerate(filtered):
            self._table.setItem(i, 0, self._mkitem(h.get("name", f"#{h['id']}"), h["id"]))
            self._table.setItem(i, 1, QTableWidgetItem({
                "time_window": "⏰", "window_sequence": "🪟",
                "click_pattern": "🖱", "active_hour": "⏳",
            }.get(h.get("pattern_type", ""), "📋")))

            conf = float(h.get("confidence", 0))
            ci = QTableWidgetItem(f"{conf:.0%}")
            ci.setForeground(COLOR_HIGH if conf >= 0.7 else COLOR_MED if conf >= 0.4 else COLOR_LOW)
            self._table.setItem(i, 2, ci)

            self._table.setItem(i, 3, QTableWidgetItem({
                "daily": "每天", "weekly": "每周", "occasional": "偶尔"
            }.get(h.get("frequency", ""), h.get("frequency", ""))))

            self._table.setItem(i, 4, QTableWidgetItem(h.get("typical_time", "") or "-"))
            self._table.setItem(i, 5, QTableWidgetItem((h.get("window_context", "") or "")[:25]))
            self._table.setItem(i, 6, QTableWidgetItem("⚡" if h.get("is_auto") else ""))

            # 操作列
            w = QWidget()
            bl = QHBoxLayout(w)
            bl.setContentsMargins(2, 2, 2, 2)
            b1 = QPushButton("▶")
            b1.setFixedSize(26, 26)
            b1.setToolTip("执行")
            b1.clicked.connect(lambda checked, hid=h["id"]: self._quick_exec(hid))
            bl.addWidget(b1)
            b2 = QPushButton("✏️")
            b2.setFixedSize(26, 26)
            b2.setToolTip("编辑")
            b2.clicked.connect(lambda checked, hid=h["id"]: self._open_habit(hid))
            bl.addWidget(b2)
            self._table.setCellWidget(i, 7, w)

    @staticmethod
    def _mkitem(text, hid):
        item = QTableWidgetItem(text)
        item.setData(Qt.UserRole, hid)
        return item

    def _update_stats(self):
        try:
            rows = db.get_daily_stats(1)
        except Exception:
            return
        if rows:
            r = rows[0]
            self._card_clicks.set_value(str(r.get("clicks", 0)))
            self._card_keys.set_value(str(r.get("keys", 0)))
            self._card_habits.set_value(str(r.get("habits_new", 0)))

            # 应用排行
            try:
                app_data = json.loads(r.get("app_usage", "{}"))
            except Exception:
                app_data = {}
            sorted_apps = sorted(app_data.items(), key=lambda x: x[1], reverse=True)[:10]
            self._app_table.setRowCount(len(sorted_apps))
            for i, (app, cnt) in enumerate(sorted_apps):
                self._app_table.setItem(i, 0, QTableWidgetItem(app[:40]))
                self._app_table.setItem(i, 1, QTableWidgetItem(str(cnt)))

    def _update_event_count(self):
        try:
            evs = db.get_today_events()
            self._ev_label.setText(f"今日事件: {len(evs)}")
        except Exception:
            pass

    # ── 操作 ──────────────────────────────────────

    def _toggle_mon(self):
        if self._mon_btn.text().startswith("⏹"):
            self._mon_btn.setText("▶ 开始监听")
            self._mon_btn.setStyleSheet("background:#4CAF50;color:white;padding:5px 14px;border-radius:4px;")
            self._banner.set_text("⏸ 监听已暂停")
        else:
            self._mon_btn.setText("⏹ 停止监听")
            self._mon_btn.setStyleSheet("background:#e74c3c;color:white;padding:5px 14px;border-radius:4px;")
            self._banner.set_text("🧠 桌面精灵 V2 · 习惯学习中心")

    def is_monitoring(self) -> bool:
        return self._mon_btn.text().startswith("⏹")

    def _analyze_now(self):
        self._banner.set_text("🧠 分析中...")
        QApplication.processEvents()
        if self._spirit:
            self._spirit.set_mood("thinking")
        try:
            before = len(db.get_habits())
            self._analyzer.run()
            after = len(db.get_habits())
            n = after - before
            self.refresh()
            if n > 0 and self._spirit:
                self._spirit.on_new_habit(n)
            self._banner.set_text(f"✅ 分析完成，发现 {n} 个新习惯" if n else "✅ 分析完成，无新发现")
            self.statusBar().showMessage(f"分析完成 {'🎉 发现'+str(n)+'个新习惯' if n else '📭 无新发现'}")
        except Exception as e:
            logger.error(f"分析异常: {e}", exc_info=True)
            self._banner.set_text("❌ 分析失败")
        finally:
            QTimer.singleShot(3000, lambda: self._banner.set_text("🧠 桌面精灵 V2 · 习惯学习中心"))

    def _sync_codex(self):
        """向 Codex 同步精灵状态。"""
        self._banner.set_text("🤖 正在同步 Codex...")
        QApplication.processEvents()
        try:
            habits = db.get_habits(active_only=True)
            stats = db.get_exec_stats(0)
            error_count = len([f for f in (os.listdir(cx.ERRORS_DIR) if os.path.exists(cx.ERRORS_DIR) else [])
                              if f.endswith('.md') and f != '_latest.md'])

            response = cx.sync_with_codex(
                habit_count=len(habits),
                analysis_ran=True,
                execution_count=stats.get("total", 0),
                error_count=error_count,
            )

            if response and response["commands"]:
                self._banner.set_text(f"✅ Codex 已响应: {len(response['commands'])} 条指令")
                self.statusBar().showMessage(f"Codex 指令已执行: {[c.get('action','') for c in response['commands']]}")
            else:
                self._banner.set_text("✅ Codex 同步完成（无新指令）")
                self.statusBar().showMessage("精灵状态已同步到 Codex")

            if self._spirit:
                if response and response["commands"]:
                    self._spirit.set_mood("happy", "Codex 有回复！✨")
                else:
                    self._spirit.set_mood("happy", "已同步到 Codex 📮")
        except Exception as e:
            logger.error(f"Codex 同步失败: {e}")
            self._banner.set_text("❌ Codex 同步失败")
            self.statusBar().showMessage(f"❌ {e}")
        finally:
            QTimer.singleShot(3000, lambda: self._banner.set_text("🧠 桌面精灵 V2 · 习惯学习中心"))

    def _open_habit(self, hid: int):
        try:
            HabitDialog(hid, self).exec_()
            self._load_habits()
        except Exception as e:
            logger.error(f"打开习惯失败: {e}")

    def _on_double(self, idx):
        item = self._table.item(idx.row(), 0)
        if item:
            self._open_habit(item.data(Qt.UserRole))

    def _quick_exec(self, hid: int):
        ex = get_executor()
        if ex.is_busy:
            QMessageBox.warning(self, "忙碌", "已有任务在执行。")
            return
        h = db.get_habit(hid)
        if not h:
            return
        if QMessageBox.question(self, "执行", f"执行「{h['name']}」？",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if self._spirit:
            self._spirit.on_exec_start(h["name"])
        import threading

        def run():
            ok = ex.run(h.get("actions_json", "[]"), hid, "click")
            if self._spirit:
                self._spirit.on_exec_done(h["name"], ok)
        threading.Thread(target=run, daemon=True).start()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出习惯", "habits.json",
                                                "JSON (*.json)")
        if not path:
            return
        try:
            data = db.export_habits()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "导出成功", f"已导出 {len(data)} 个习惯")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _import_(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入习惯", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            n = db.import_habits(data)
            self._load_habits()
            QMessageBox.information(self, "导入成功", f"已导入 {n} 个习惯")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
