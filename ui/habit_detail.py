"""V2 习惯详情/编辑对话框。"""

import json
import logging

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QCheckBox, QGroupBox, QMessageBox,
    QFormLayout, QSlider, QComboBox, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from core import database as db
from core.executor import get_executor

logger = logging.getLogger(__name__)


class HabitDialog(QDialog):
    def __init__(self, habit_id: int, parent=None):
        super().__init__(parent)
        self._hid = habit_id
        self._h = db.get_habit(habit_id)
        if not self._h:
            raise ValueError(f"习惯 #{habit_id} 不存在")

        self.setWindowTitle(f"✏️ {self._h.get('name', '习惯编辑')}")
        self.setMinimumSize(560, 520)
        self.setModal(True)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── 标签页 1：基本信息 ────────────────────
        t1 = QWidget()
        tabs.addTab(t1, "📋 基本信息")
        fm = QFormLayout(t1)

        self._name_edit = QLineEdit()
        fm.addRow("名称:", self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(70)
        fm.addRow("描述:", self._desc_edit)

        self._type_label = QLabel()
        fm.addRow("类型:", self._type_label)

        self._freq_combo = QComboBox()
        self._freq_combo.addItems(["daily", "weekly", "occasional"])
        fm.addRow("频率:", self._freq_combo)

        self._time_edit = QLineEdit()
        self._time_edit.setPlaceholderText("HH:MM")
        fm.addRow("典型时间:", self._time_edit)

        self._window_label = QLabel()
        fm.addRow("关联窗口:", self._window_label)

        # 置信度
        hconf = QHBoxLayout()
        self._conf_slider = QSlider(Qt.Horizontal)
        self._conf_slider.setRange(0, 100)
        self._conf_label = QLabel("0%")
        self._conf_slider.valueChanged.connect(
            lambda v: self._conf_label.setText(f"{v}%"))
        hconf.addWidget(self._conf_slider)
        hconf.addWidget(self._conf_label)
        fm.addRow("置信度:", hconf)

        self._active_cb = QCheckBox("启用")
        fm.addRow("", self._active_cb)
        self._auto_cb = QCheckBox("自动执行（匹配时自动触发）")
        fm.addRow("", self._auto_cb)

        # ── 标签页 2：动作序列 ────────────────────
        t2 = QWidget()
        tabs.addTab(t2, "⚡ 动作序列")
        al = QVBoxLayout(t2)

        self._act_table = QTableWidget()
        self._act_table.setColumnCount(3)
        self._act_table.setHorizontalHeaderLabels(["#", "类型", "参数"])
        self._act_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        al.addWidget(self._act_table)

        self._act_raw = QTextEdit()
        self._act_raw.setMaximumHeight(100)
        al.addWidget(self._act_raw)

        # ── 标签页 3：执行历史 ────────────────────
        t3 = QWidget()
        tabs.addTab(t3, "📊 执行记录")
        hl = QVBoxLayout(t3)

        self._stats_label = QLabel()
        hl.addWidget(self._stats_label)

        self._hist_table = QTableWidget()
        self._hist_table.setColumnCount(4)
        self._hist_table.setHorizontalHeaderLabels(["时间", "结果", "耗时", "触发"])
        self._hist_table.horizontalHeader().setStretchLastSection(True)
        hl.addWidget(self._hist_table)

        # ── 底部按钮 ──────────────────────────────
        btn = QHBoxLayout()
        layout.addLayout(btn)

        self._exec_btn = QPushButton("▶ 执行")
        self._exec_btn.setStyleSheet(
            "background:#4CAF50;color:white;padding:8px 20px;border-radius:5px;font-weight:bold;")
        self._exec_btn.clicked.connect(self._do_exec)
        btn.addWidget(self._exec_btn)

        btn.addStretch()

        sv_btn = QPushButton("💾 保存")
        sv_btn.clicked.connect(self._do_save)
        btn.addWidget(sv_btn)

        dl_btn = QPushButton("🗑 删除")
        dl_btn.setStyleSheet("color:#c0392b;")
        dl_btn.clicked.connect(self._do_delete)
        btn.addWidget(dl_btn)

        cl_btn = QPushButton("关闭")
        cl_btn.clicked.connect(self.close)
        btn.addWidget(cl_btn)

    def _load(self):
        h = self._h
        self._name_edit.setText(h.get("name", ""))
        self._desc_edit.setText(h.get("desc", ""))
        self._type_label.setText({
            "time_window": "⏰ 时间型", "window_sequence": "🪟 窗口序列",
            "click_pattern": "🖱 点击型", "active_hour": "⏳ 活跃时段",
        }.get(h.get("pattern_type", ""), h.get("pattern_type", "")))
        self._freq_combo.setCurrentText(h.get("frequency", "daily"))
        self._time_edit.setText(h.get("typical_time", ""))
        self._window_label.setText(h.get("window_context", "") or "(无)")

        conf = int(float(h.get("confidence", 0)) * 100)
        self._conf_slider.setValue(conf)
        self._conf_label.setText(f"{conf}%")
        self._active_cb.setChecked(bool(h.get("is_active", 1)))
        self._auto_cb.setChecked(bool(h.get("is_auto", 0)))

        self._load_actions()
        self._load_history()

    def _load_actions(self):
        try:
            acts = json.loads(self._h.get("actions_json", "[]"))
            if isinstance(acts, dict):
                acts = [acts]
        except Exception:
            acts = []

        self._act_table.setRowCount(len(acts))
        for i, a in enumerate(acts):
            self._act_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self._act_table.setItem(i, 1, QTableWidgetItem(a.get("type", "")))
            params = {k: v for k, v in a.items() if k not in ("type", "wait_before", "wait_after")}
            self._act_table.setItem(i, 2, QTableWidgetItem(json.dumps(params, ensure_ascii=False)[:60]))

        self._act_raw.setText(json.dumps(acts, indent=2, ensure_ascii=False))

    def _load_history(self):
        stats = db.get_exec_stats(self._hid)
        self._stats_label.setText(
            f"总计 {stats['total']} 次 | ✅ {stats['success']} | ❌ {stats['fail']}")

        rows = db.get_exec_history(self._hid)
        self._hist_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self._hist_table.setItem(i, 0, QTableWidgetItem(r["ts"]))
            self._hist_table.setItem(i, 1, QTableWidgetItem("✅" if r["success"] else "❌"))
            self._hist_table.setItem(i, 2, QTableWidgetItem(f"{r['duration_ms']}ms"))
            m = {"manual": "手动", "auto": "自动"}
            self._hist_table.setItem(i, 3, QTableWidgetItem(m.get(r["triggered_by"], r["triggered_by"])))

    # ── 操作 ──────────────────────────────────────

    def _do_exec(self):
        ex = get_executor()
        if ex.is_busy:
            QMessageBox.warning(self, "忙碌", "正在执行中，请稍候。")
            return

        if QMessageBox.question(self, "确认执行", f"即将执行「{self._h.get('name','')}」\n倒计时后操作鼠标。",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        self._exec_btn.setEnabled(False)
        steps = [3, 2, 1]
        self._exec_btn.setText(f"⏳ {steps[0]}s...")

        def tick(i=0):
            if i >= len(steps):
                self._exec_btn.setText("▶ 执行中...")
                import threading
                threading.Thread(target=self._run_exec, daemon=True).start()
                return
            self._exec_btn.setText(f"⏳ {steps[i]}s...")
            QTimer.singleShot(1000, lambda: tick(i + 1))

        QTimer.singleShot(0, tick)

    def _run_exec(self):
        try:
            ok = get_executor().run(self._h.get("actions_json", "[]"), self._hid, "manual")
            self._exec_btn.setText("✅ 完成" if ok else "❌ 失败")
        except Exception as e:
            self._exec_btn.setText("❌ 异常")
        finally:
            self._exec_btn.setEnabled(True)
            QTimer.singleShot(2000, lambda: self._exec_btn.setText("▶ 执行"))

    def _do_save(self):
        db._update_habit(self._hid,
                         name=self._name_edit.text(),
                         desc=self._desc_edit.toPlainText(),
                         frequency=self._freq_combo.currentText(),
                         typical_time=self._time_edit.text(),
                         confidence=self._conf_slider.value() / 100.0,
                         is_active=1 if self._active_cb.isChecked() else 0,
                         is_auto=1 if self._auto_cb.isChecked() else 0,
                         actions_json=self._act_raw.toPlainText())
        QMessageBox.information(self, "已保存", "修改已保存。")
        self.accept()

    def _do_delete(self):
        if QMessageBox.question(self, "确认删除", "确定删除此习惯？",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            db.delete_habit(self._hid)
            self.accept()
