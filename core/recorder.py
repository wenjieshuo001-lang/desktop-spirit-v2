"""V2 事件录制器 —— 批量缓冲 + 智能序列分割。"""

import logging
import time
from collections import deque
from datetime import datetime

from . import database as db
from config import settings

logger = logging.getLogger(__name__)

IDLE_TIMEOUT = lambda: settings.get("monitor.idle_timeout", 30.0)
FLUSH_INTERVAL = lambda: settings.get("monitor.flush_interval", 5.0)


class Recorder:
    """录制器：缓冲 → 分组为序列 → 写库 → 通知分析器。"""

    def __init__(self, on_new_sequence=None):
        self._buffer = deque()
        self._seq_id = None
        self._seq_start = None
        self._seq_window = ""
        self._seq_app = ""
        self._seq_count = 0
        self._last_event = time.time()
        self._last_flush = time.time()
        self._on_new_sequence = on_new_sequence

    # ── 入口 ──────────────────────────────────────

    def handle(self, event_type: str, detail: dict, window: str):
        now = time.time()
        elapsed = now - self._last_event

        # 窗口切换或超时 → 结束当前序列
        if (event_type == "window_focus" and self._seq_id is not None) \
                or elapsed > IDLE_TIMEOUT():
            self._finalize()

        # 新序列
        if self._seq_id is None:
            self._seq_start = datetime.now().isoformat()
            self._seq_window = window
            self._seq_app = detail.get("exe", "")
            self._seq_count = 0
            try:
                self._seq_id = db.create_sequence(self._seq_start, window, self._seq_app)
            except Exception as e:
                logger.error(f"创建序列失败: {e}")
                self._seq_id = -1

        self._seq_count += 1
        self._buffer.append((event_type, detail, window, self._seq_id))
        self._last_event = now

        # 定时刷入
        if now - self._last_flush >= FLUSH_INTERVAL():
            self._flush()

    # ── 缓冲 ──────────────────────────────────────

    def _flush(self):
        if not self._buffer:
            return
        batch = [self._buffer.popleft() for _ in range(len(self._buffer))]
        try:
            with db.get_conn() as conn:
                conn.executemany(
                    "INSERT INTO events (type, detail, window, seq_id) VALUES (?, ?, ?, ?)",
                    [(e[0], e[1], e[2], e[3]) for e in batch]
                )
            self._last_flush = time.time()
        except Exception as e:
            logger.error(f"批量写入失败 ({len(batch)} 条): {e}")
            self._buffer.extendleft(reversed(batch))

    def _finalize(self):
        if self._seq_id is None or self._seq_id < 0:
            self._reset()
            return
        self._flush()
        summary = self._make_summary()
        try:
            db.update_sequence(self._seq_id, datetime.now().isoformat(),
                               self._seq_count, summary)
        except Exception as e:
            logger.error(f"更新序列失败: {e}")

        if self._on_new_sequence and self._seq_id > 0:
            try:
                self._on_new_sequence(self._seq_id, summary,
                                      self._seq_window, self._seq_start)
            except Exception as e:
                logger.error(f"通知分析器失败: {e}")

        self._reset()

    def _reset(self):
        self._seq_id = None
        self._seq_start = None
        self._seq_window = ""
        self._seq_app = ""
        self._seq_count = 0

    def _make_summary(self) -> str:
        t = self._seq_start or ""
        return f"[{t[11:19]}] {self._seq_window[:30]} — {self._seq_count} 个操作"

    def flush(self):
        self._finalize()
        self._flush()
