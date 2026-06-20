"""V2 习惯分析引擎 —— 更智能的模式识别。

检测策略：
1. 时间窗口模式：相同时段 + 相同应用 → 时间习惯
2. 窗口序列 N-gram：重复的窗口切换链 → 工作流习惯
3. 点击位置聚类：相同窗口内重复点击 → 宏习惯
4. 活跃时间段检测：每日固定时段的高频操作 → 时段习惯"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from . import database as db
from config import settings

logger = logging.getLogger(__name__)


class Analyzer:
    """习惯分析器。"""

    def __init__(self):
        self._pairs = []  # [(window, datetime)]

    def on_new_sequence(self, seq_id: int, summary: str,
                        window: str, start_ts: str):
        """录制器回调 —— 记录时间-窗口配对。"""
        try:
            dt = datetime.fromisoformat(start_ts)
            self._pairs.append((window, dt))
            if len(self._pairs) > 500:
                self._pairs = self._pairs[-500:]
        except Exception:
            pass

    def run(self):
        """执行全量分析。"""
        logger.info("开始习惯分析...")
        try:
            self._scan_time_patterns()
            self._scan_window_sequences()
            self._scan_click_patterns()
            self._scan_active_hours()
            db.update_daily_stats()
            logger.info("✅ 分析完成")
        except Exception as e:
            logger.error(f"分析异常: {e}", exc_info=True)

    # ── 策略 1：时间窗口 ──────────────────────────

    def _scan_time_patterns(self):
        sequences = db.get_recent_sequences(settings.get("analyzer.lookback_days", 7))
        if not sequences:
            return

        groups = defaultdict(lambda: {"count": 0, "windows": set()})
        for s in sequences:
            try:
                start = datetime.fromisoformat(s["start_ts"])
                hour = f"{start.hour:02d}:{start.minute // 15 * 15:02d}"
                key = (hour, s["window"])
                groups[key]["count"] += 1
                groups[key]["windows"].add(s["window"])
            except Exception:
                continue

        min_occ = settings.get("analyzer.min_occurrences", 3)
        for (hour_win, window), info in groups.items():
            if info["count"] < min_occ:
                continue

            conf = min(info["count"] / 10.0, 0.95)
            freq = "daily" if info["count"] >= 5 else "weekly"
            typical = hour_win[:5]

            actions = json.dumps([{"type": "window", "window": window, "wait_after": 1.0}],
                                 ensure_ascii=False)

            db.save_habit(
                name=f"打开 {window[:20]}",
                desc=f"在 {typical} 左右使用 {window[:30]}（{info['count']} 次）",
                pattern_type="time_window",
                confidence=conf, frequency=freq,
                typical_time=typical, window_context=window,
                actions_json=actions,
                triggers={"window_title": window}
            )

    # ── 策略 2：窗口序列 ──────────────────────────

    def _scan_window_sequences(self):
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        events = db.get_events_since(cutoff, 5000)
        focus = [e for e in events if e["type"] == "window_focus" and e.get("detail")]

        if len(focus) < 5:
            return

        paths = []
        for ev in focus:
            try:
                d = json.loads(ev["detail"])
                paths.append(d.get("to", ""))
            except (json.JSONDecodeError, KeyError):
                continue

        if len(paths) < 3:
            return

        # N-gram 3 检测
        ngrams = defaultdict(int)
        for i in range(len(paths) - 2):
            ngrams[tuple(paths[i:i+3])] += 1

        min_occ = settings.get("analyzer.min_occurrences", 3)
        for seq, count in ngrams.items():
            if count < min_occ:
                continue

            conf = min(count / 8.0, 0.9)
            actions = json.dumps(
                [{"type": "window", "window": w, "wait_after": 1.5} for w in seq],
                ensure_ascii=False
            )

            db.save_habit(
                name=f"工作流: {seq[0][:12]}→...",
                desc=f"{seq[0][:20]} → {seq[1][:20]} → {seq[2][:20]}（{count} 次）",
                pattern_type="window_sequence",
                confidence=conf,
                frequency="daily" if count >= 4 else "weekly",
                typical_time="", window_context=seq[0],
                actions_json=actions,
                triggers={"window_sequence": list(seq)}
            )

    # ── 策略 3：点击模式 ──────────────────────────

    def _scan_click_patterns(self):
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        events = db.get_events_since(cutoff, 5000)

        win_clicks = defaultdict(list)
        for ev in events:
            if ev["type"] == "click":
                win = ev.get("window", "")
                if win:
                    win_clicks[win].append(ev)

        min_occ = settings.get("analyzer.min_occurrences", 3)
        for window, evs in win_clicks.items():
            if len(evs) < 6:
                continue

            pos_counts = defaultdict(int)
            for ev in evs:
                try:
                    d = json.loads(ev["detail"])
                    gx = d.get("x", 0) // 20 * 20
                    gy = d.get("y", 0) // 20 * 20
                    pos_counts[(gx, gy)] += 1
                except Exception:
                    continue

            for (gx, gy), count in pos_counts.items():
                if count < min_occ:
                    continue

                conf = min(count / 8.0, 0.85)
                db.save_habit(
                    name=f"点击: {window[:15]}",
                    desc=f"在 ({gx},{gy}) 附近重复点击（{count} 次）",
                    pattern_type="click_pattern",
                    confidence=conf,
                    frequency="daily" if count >= 4 else "weekly",
                    typical_time="", window_context=window,
                    actions_json=json.dumps(
                        [{"type": "click", "x": gx + 10, "y": gy + 10, "wait_before": 0.5}],
                        ensure_ascii=False
                    ),
                    triggers={"window_title": window}
                )

    # ── 策略 4：活跃时段 ──────────────────────────

    def _scan_active_hours(self):
        """检测每日固定活跃时段。"""
        sequences = db.get_recent_sequences(7)
        hour_counts = defaultdict(int)

        for s in sequences:
            try:
                h = datetime.fromisoformat(s["start_ts"]).hour
                hour_counts[h] += 1
            except Exception:
                continue

        total = sum(hour_counts.values())
        if total < 10:
            return

        for hour, count in hour_counts.items():
            ratio = count / total
            if ratio < 0.12 or count < 3:
                continue

            conf = min(ratio * 2, 0.8)
            db.save_habit(
                name=f"{hour:02d}:00 活跃时段",
                desc=f"在 {hour:02d}:00 左右有高峰期（占全天 {ratio:.0%}）",
                pattern_type="active_hour",
                confidence=conf, frequency="daily",
                typical_time=f"{hour:02d}:00",
                window_context="",
                actions_json="[]",
                triggers={}
            )
